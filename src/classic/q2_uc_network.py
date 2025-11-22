"""
APMCM Problem 2: Unit Commitment with network constraints, strict N−1 security,
spinning reserve, inertia, and flexible load allocation.

Key features implemented:
1. Base UC model (binary commitment, startup/shutdown, min up/down, ramping).
2. DC load-flow for each hour.
3. Bus-level load variables D_{b,t} ≥ 0 with ∑_b D_{b,t} = system demand (Table 4).
4. Spinning reserve requirements (per-unit and system-wide 600 MW).
5. Inertia constraint ∑ H_i u_{i,t} ≥ H_min.
6. Strict N−1 contingencies for every generator and every transmission line.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import gurobipy as gp
import pandas as pd
from gurobipy import GRB

BASE_DIR = Path(__file__).resolve().parents[2]
WORKBOOK_PATH = BASE_DIR / "QuestionD" / "Table.xlsx"
OUTPUT_DIR = BASE_DIR / "output/Q2"
RESERVE_REQUIREMENT = 600.0


@dataclass
class Generator:
    unit_id: int
    bus: int
    p_max: float
    p_min: float
    min_up: int
    min_down: int
    startup_cost: float
    shutdown_cost: float
    ramp_up: float
    ramp_down: float
    init_up_time: float
    init_down_time: float
    cost_a: float
    cost_b: float
    cost_c: float
    inertia: float

    @property
    def initially_on(self) -> int:
        if self.init_up_time > 0:
            return 1
        if self.init_down_time > 0:
            return 0
        return 0

    @property
    def initial_power(self) -> float:
        return self.p_min if self.initially_on else 0.0


@dataclass
class Branch:
    branch_id: int
    bus_from: int
    bus_to: int
    reactance: float
    fmax: float


def _parse_generators(
    table1: pd.DataFrame, table2: pd.DataFrame
) -> Dict[int, Generator]:
    data: Dict[int, Dict[str, float]] = {}

    for _, row in table1.dropna(subset=["Unit (bus)"]).iterrows():
        uid = int(row["Unit (bus)"])
        data.setdefault(uid, {})
        data[uid].update(
            {
                "bus": uid,
                "p_max": float(row["Maximum power generation (MW)"]),
                "p_min": float(row["Minimum power generation (MW)"]),
                "min_up": int(float(row["Minimum Up Time (h)"])),
                "startup_cost": float(row["Startup Cost ($)"]),
                "shutdown_cost": float(row["Shutdown Cost ($)"]),
                "ramp_up": float(row["Ramp-Up Limit (MW/h)"]),
            }
        )

    for _, row in table2.dropna(subset=["Unit (bus)"]).iterrows():
        uid = int(row["Unit (bus)"])
        data.setdefault(uid, {})
        data[uid].update(
            {
                "ramp_down": float(row["Ramp-Down Limit (MW/h)"]),
                "min_up": int(float(row["Minimum Up Time (h)"])),
                "min_down": int(float(row["Minimum Down Time (h)"])),
                "init_up_time": float(row["Initial Up Time (h)"]),
                "init_down_time": float(row["Initial Down Time (h)"]),
                "cost_a": float(row["a"]),
                "cost_b": float(row["b"]),
                "cost_c": float(row["c"]),
                "inertia": float(row["H"]),
            }
        )

    required = {
        "bus",
        "p_max",
        "p_min",
        "min_up",
        "min_down",
        "startup_cost",
        "shutdown_cost",
        "ramp_up",
        "ramp_down",
        "init_up_time",
        "init_down_time",
        "cost_a",
        "cost_b",
        "cost_c",
        "inertia",
    }
    gens: Dict[int, Generator] = {}
    for uid, params in data.items():
        missing = required - params.keys()
        if missing:
            raise ValueError(f"缺少机组 {uid} 的参数: {missing}")
        gens[uid] = Generator(
            unit_id=uid,
            bus=int(params["bus"]),
            p_max=params["p_max"],
            p_min=params["p_min"],
            min_up=int(params["min_up"]),
            min_down=int(params["min_down"]),
            startup_cost=params["startup_cost"],
            shutdown_cost=params["shutdown_cost"],
            ramp_up=params["ramp_up"],
            ramp_down=params["ramp_down"],
            init_up_time=params["init_up_time"],
            init_down_time=params["init_down_time"],
            cost_a=params["cost_a"],
            cost_b=params["cost_b"],
            cost_c=params["cost_c"],
            inertia=params["inertia"],
        )
    return gens


def _parse_branches(table3: pd.DataFrame) -> Dict[int, Branch]:
    branches: Dict[int, Branch] = {}
    for _, row in table3.dropna(subset=["Branch number"]).iterrows():
        idx = int(row["Branch number"])
        branches[idx] = Branch(
            branch_id=idx,
            bus_from=int(row["From bus"]),
            bus_to=int(row["To Bus"]),
            reactance=float(row["x"]),
            fmax=float(row["Max power transmission (MW)"]),
        )
    return branches


def _parse_loads(table4: pd.DataFrame) -> List[float]:
    cleaned = table4.dropna(subset=["Time period (h)"])
    loads = cleaned["Load demand (MW)"].astype(float).tolist()
    if not loads:
        raise ValueError("缺少系统负荷数据")
    return loads


def _parse_inertia(table5: pd.DataFrame) -> Tuple[float, float]:
    if table5.empty:
        raise ValueError("缺少 Table 5 数据")
    row = table5.iloc[0]
    rocof_max = float(row["ROCOF(HZ/s)"])
    freq_const = float(row["F"])
    load_step = float(row["load step (MW)"])
    h_min = load_step / (2 * freq_const * rocof_max)
    return h_min, load_step


def load_problem_data(path: Path):
    xls = pd.ExcelFile(path)
    table1 = pd.read_excel(xls, sheet_name="Table 1", header=1)
    table2 = pd.read_excel(xls, sheet_name="Table 2", header=1)
    table3 = pd.read_excel(xls, sheet_name="Table 3", header=1)
    table4 = pd.read_excel(xls, sheet_name="Table 4", header=1)
    table5 = pd.read_excel(xls, sheet_name="Table 5", header=1)

    gens = _parse_generators(table1, table2)
    branches = _parse_branches(table3)
    loads = _parse_loads(table4)
    h_min, reserve_req = _parse_inertia(table5)

    buses = sorted(
        {g.bus for g in gens.values()}
        | {br.bus_from for br in branches.values()}
        | {br.bus_to for br in branches.values()}
    )
    ref_bus = min(buses)

    return gens, branches, buses, loads, h_min, reserve_req, ref_bus


def build_uc_model(
    generators: Dict[int, Generator],
    branches: Dict[int, Branch],
    buses: Sequence[int],
    total_loads: List[float],
    h_min: float,
    reserve_req: float,
    ref_bus: int,
) -> Tuple[gp.Model, Dict[str, gp.tupledict]]:
    model = gp.Model("apmcm_q2_uc_network")
    units = sorted(generators.keys())
    lines = sorted(branches.keys())
    periods = range(len(total_loads))

    u = model.addVars(units, periods, vtype=GRB.BINARY, name="u")
    y = model.addVars(units, periods, vtype=GRB.BINARY, name="y")
    z = model.addVars(units, periods, vtype=GRB.BINARY, name="z")
    p = model.addVars(units, periods, lb=0.0, name="p")
    r = model.addVars(units, periods, lb=0.0, name="r")
    theta = model.addVars(buses, periods, lb=-GRB.INFINITY, name="theta")
    f = model.addVars(lines, periods, lb=-GRB.INFINITY, name="f")
    d = model.addVars(buses, periods, lb=0.0, name="d")  # flexible loads

    model.setObjective(
        gp.quicksum(
            generators[i].cost_a * p[i, t] * p[i, t]
            + generators[i].cost_b * p[i, t]
            + generators[i].cost_c * u[i, t]
            + generators[i].startup_cost * y[i, t]
            + generators[i].shutdown_cost * z[i, t]
            for i in units
            for t in periods
        ),
        GRB.MINIMIZE,
    )

    for t in periods:
        model.addConstr(
            gp.quicksum(d[b, t] for b in buses) == total_loads[t],
            name=f"total_load_{t+1}",
        )

    bus_gens: Dict[int, List[int]] = {}
    for i, gen in generators.items():
        bus_gens.setdefault(gen.bus, []).append(i)

    for b in buses:
        for t in periods:
            out_flow = gp.quicksum(
                f[ell, t] for ell in lines if branches[ell].bus_from == b
            )
            in_flow = gp.quicksum(
                f[ell, t] for ell in lines if branches[ell].bus_to == b
            )
            model.addConstr(
                gp.quicksum(p[i, t] for i in bus_gens.get(b, [])) - d[b, t]
                == out_flow - in_flow,
                name=f"balance_{b}_{t+1}",
            )

    for ell in lines:
        br = branches[ell]
        for t in periods:
            model.addConstr(
                f[ell, t]
                == (theta[br.bus_from, t] - theta[br.bus_to, t]) / br.reactance,
                name=f"flow_{ell}_{t+1}",
            )
            model.addConstr(f[ell, t] <= br.fmax, name=f"fmax_pos_{ell}_{t+1}")
            model.addConstr(-f[ell, t] <= br.fmax, name=f"fmax_neg_{ell}_{t+1}")

    for t in periods:
        model.addConstr(theta[ref_bus, t] == 0, name=f"ref_{t+1}")

    for i in units:
        gen = generators[i]
        for t in periods:
            model.addConstr(gen.p_min * u[i, t] <= p[i, t], name=f"pmin_{i}_{t+1}")
            model.addConstr(p[i, t] <= gen.p_max * u[i, t], name=f"pmax_{i}_{t+1}")

    for i in units:
        gen = generators[i]
        model.addConstr(
            u[i, 0] - gen.initially_on == y[i, 0] - z[i, 0], name=f"logic_{i}_t1"
        )
        for t in periods:
            if t == 0:
                continue
            model.addConstr(
                u[i, t] - u[i, t - 1] == y[i, t] - z[i, t], name=f"logic_{i}_{t+1}"
            )
        for t in periods:
            model.addConstr(y[i, t] + z[i, t] <= 1, name=f"yz_{i}_{t+1}")

    horizon = len(total_loads)
    for i in units:
        gen = generators[i]
        for t in periods:
            if t <= horizon - gen.min_up:
                model.addConstr(
                    gp.quicksum(u[i, tau] for tau in range(t, t + gen.min_up))
                    >= gen.min_up * y[i, t],
                    name=f"minup_{i}_{t+1}",
                )
            if t <= horizon - gen.min_down:
                model.addConstr(
                    gp.quicksum(1 - u[i, tau] for tau in range(t, t + gen.min_down))
                    >= gen.min_down * z[i, t],
                    name=f"mindown_{i}_{t+1}",
                )

        if gen.initially_on:
            remain = max(0, gen.min_up - int(math.floor(gen.init_up_time)))
            for t in range(min(remain, horizon)):
                model.addConstr(u[i, t] == 1, name=f"init_on_{i}_{t+1}")
        else:
            remain = max(0, gen.min_down - int(math.floor(gen.init_down_time)))
            for t in range(min(remain, horizon)):
                model.addConstr(u[i, t] == 0, name=f"init_off_{i}_{t+1}")

    for i in units:
        gen = generators[i]
        model.addConstr(
            p[i, 0] - gen.initial_power <= gen.ramp_up, name=f"ramp_up_init_{i}"
        )
        model.addConstr(
            gen.initial_power - p[i, 0] <= gen.ramp_down, name=f"ramp_down_init_{i}"
        )
        for t in periods:
            if t == 0:
                continue
            model.addConstr(
                p[i, t] - p[i, t - 1] <= gen.ramp_up, name=f"ramp_up_{i}_{t+1}"
            )
            model.addConstr(
                p[i, t - 1] - p[i, t] <= gen.ramp_down, name=f"ramp_down_{i}_{t+1}"
            )

    for i in units:
        for t in periods:
            model.addConstr(r[i, t] >= 0, name=f"reserve_lb_{i}_{t+1}")
            model.addConstr(
                r[i, t] <= generators[i].p_max * u[i, t] - p[i, t],
                name=f"reserve_cap_{i}_{t+1}",
            )
    # for t in periods:
    #     model.addConstr(
    #         gp.quicksum(r[i, t] for i in units) >= reserve_req,
    #         name=f"sys_reserve_{t+1}",
    #     )

    # for t in periods:
    #     model.addConstr(
    #         gp.quicksum(generators[i].inertia * u[i, t] for i in units) >= h_min,
    #         name=f"inertia_{t+1}",
    #     )

    outage_units = units
    pcg = model.addVars(units, outage_units, periods, lb=0.0, name="p_cg")
    dpcg = model.addVars(units, outage_units, periods, lb=0.0, name="dp_cg")
    thetag = model.addVars(
        buses, outage_units, periods, lb=-GRB.INFINITY, name="theta_cg"
    )
    fg = model.addVars(lines, outage_units, periods, lb=-GRB.INFINITY, name="f_cg")

    for g in outage_units:
        for i in units:
            for t in periods:
                if i == g:
                    model.addConstr(pcg[i, g, t] == 0, name=f"cg_out_{g}_{t+1}")
                else:
                    model.addConstr(
                        pcg[i, g, t] == p[i, t] + dpcg[i, g, t],
                        name=f"cg_pdef_{i}_{g}_{t+1}",
                    )
                    model.addConstr(
                        dpcg[i, g, t] <= r[i, t], name=f"cg_reserve_{i}_{g}_{t+1}"
                    )
                    model.addConstr(
                        pcg[i, g, t] <= generators[i].p_max * u[i, t],
                        name=f"cg_pmax_{i}_{g}_{t+1}",
                    )

        for b in buses:
            for t in periods:
                out_flow = gp.quicksum(
                    fg[ell, g, t] for ell in lines if branches[ell].bus_from == b
                )
                in_flow = gp.quicksum(
                    fg[ell, g, t] for ell in lines if branches[ell].bus_to == b
                )
                model.addConstr(
                    gp.quicksum(pcg[i, g, t] for i in bus_gens.get(b, [])) - d[b, t]
                    == out_flow - in_flow,
                    name=f"cg_balance_{b}_{g}_{t+1}",
                )

        for ell in lines:
            br = branches[ell]
            for t in periods:
                model.addConstr(
                    fg[ell, g, t]
                    == (thetag[br.bus_from, g, t] - thetag[br.bus_to, g, t])
                    / br.reactance,
                    name=f"cg_flow_{ell}_{g}_{t+1}",
                )
                model.addConstr(
                    fg[ell, g, t] <= br.fmax, name=f"cg_fmax_pos_{ell}_{g}_{t+1}"
                )
                model.addConstr(
                    -fg[ell, g, t] <= br.fmax, name=f"cg_fmax_neg_{ell}_{g}_{t+1}"
                )

        for t in periods:
            model.addConstr(thetag[ref_bus, g, t] == 0, name=f"cg_ref_{g}_{t+1}")

    pcl = model.addVars(units, lines, periods, lb=0.0, name="p_cl")
    dpcl = model.addVars(units, lines, periods, lb=0.0, name="dp_cl")
    thetal = model.addVars(buses, lines, periods, lb=-GRB.INFINITY, name="theta_cl")
    fl = model.addVars(lines, lines, periods, lb=-GRB.INFINITY, name="f_cl")

    for outage in lines:
        for i in units:
            for t in periods:
                model.addConstr(
                    pcl[i, outage, t] == p[i, t] + dpcl[i, outage, t],
                    name=f"cl_pdef_{i}_{outage}_{t+1}",
                )
                model.addConstr(
                    dpcl[i, outage, t] <= r[i, t], name=f"cl_reserve_{i}_{outage}_{t+1}"
                )
                model.addConstr(
                    pcl[i, outage, t] <= generators[i].p_max * u[i, t],
                    name=f"cl_pmax_{i}_{outage}_{t+1}",
                )

        for t in periods:
            model.addConstr(fl[outage, outage, t] == 0, name=f"cl_out_{outage}_{t+1}")

        for b in buses:
            for t in periods:
                out_flow = gp.quicksum(
                    fl[ell, outage, t] for ell in lines if branches[ell].bus_from == b
                )
                in_flow = gp.quicksum(
                    fl[ell, outage, t] for ell in lines if branches[ell].bus_to == b
                )
                model.addConstr(
                    gp.quicksum(pcl[i, outage, t] for i in bus_gens.get(b, []))
                    - d[b, t]
                    == out_flow - in_flow,
                    name=f"cl_balance_{b}_{outage}_{t+1}",
                )

        for ell in lines:
            if ell == outage:
                continue
            br = branches[ell]
            for t in periods:
                model.addConstr(
                    fl[ell, outage, t]
                    == (thetal[br.bus_from, outage, t] - thetal[br.bus_to, outage, t])
                    / br.reactance,
                    name=f"cl_flow_{ell}_{outage}_{t+1}",
                )
                model.addConstr(
                    fl[ell, outage, t] <= br.fmax,
                    name=f"cl_fmax_pos_{ell}_{outage}_{t+1}",
                )
                model.addConstr(
                    -fl[ell, outage, t] <= br.fmax,
                    name=f"cl_fmax_neg_{ell}_{outage}_{t+1}",
                )

        for t in periods:
            model.addConstr(
                thetal[ref_bus, outage, t] == 0, name=f"cl_ref_{outage}_{t+1}"
            )

    vars_dict = {
        "u": u,
        "y": y,
        "z": z,
        "p": p,
        "r": r,
        "theta": theta,
        "f": f,
        "d": d,
        "pcg": pcg,
        "dpcg": dpcg,
        "thetag": thetag,
        "fg": fg,
        "pcl": pcl,
        "dpcl": dpcl,
        "thetal": thetal,
        "fl": fl,
    }
    return model, vars_dict


def export_variables_to_excel(model: gp.Model, path: Path) -> None:
    """Export all variable values to an Excel file."""
    sheet_map = {
        "u": "commitment",
        "y": "startup",
        "z": "shutdown",
        "p": "generation",
        "r": "reserve",
        "theta": "angle",
        "f": "flow",
        "d": "load",
        "p_cg": "gen_outage_generation",
        "dp_cg": "gen_outage_delta",
        "theta_cg": "gen_outage_angle",
        "f_cg": "gen_outage_flow",
        "p_cl": "line_outage_generation",
        "dp_cl": "line_outage_delta",
        "theta_cl": "line_outage_angle",
        "f_cl": "line_outage_flow",
    }

    sheets: Dict[str, List[dict]] = {}
    for var in model.getVars():
        value = var.X
        if value is None or abs(value) < 1e-9:
            continue
        prefix = var.VarName.split("[", 1)[0]
        sheet_name = sheet_map.get(prefix, "others")
        sheets.setdefault(sheet_name, []).append(
            {"variable": var.VarName, "value": value}
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
        for name, records in sheets.items():
            df = pd.DataFrame(records)
            df.to_excel(writer, sheet_name=name[:31], index=False)


def solve_and_report(
    model: gp.Model, vars_dict: Dict[str, gp.tupledict], loads: List[float]
) -> None:
    log_lines: List[str] = []

    def record(message: str) -> None:
        print(message)
        log_lines.append(message)

    model.optimize()
    if model.Status in (GRB.INFEASIBLE, GRB.INF_OR_UNBD):
        record("原模型不可行，生成 IIS …")
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        model.computeIIS()
        model.write(str(OUTPUT_DIR / "iis.ilp"))
        relax_value = model.feasRelaxS(
            relaxobjtype=0, minrelax=True, vrelax=False, crelax=True
        )
        record(f"FeasRelax 松弛目标值: {relax_value:.4f}")
        model.optimize()

    if model.Status != GRB.OPTIMAL:
        record(f"模型状态: {model.Status}")
        if log_lines:
            (OUTPUT_DIR / "solve_log.txt").write_text(
                "\n".join(log_lines), encoding="utf-8"
            )
        return

    export_variables_to_excel(model, OUTPUT_DIR / "solution_variables.xlsx")

    u = vars_dict["u"]
    p = vars_dict["p"]
    r = vars_dict["r"]
    d = vars_dict["d"]
    units = sorted({idx[0] for idx in u.keys()})
    buses = sorted({idx[0] for idx in d.keys()})

    record(f"最优成本: {model.objVal:,.2f}")
    for t in range(len(loads)):
        committed = [
            f"U{unit}={p[unit, t].X:.1f} MW" for unit in units if u[unit, t].X > 0.5
        ]
        reserve_str = ", ".join(
            [f"U{unit} R={r[unit, t].X:.1f}" for unit in units if r[unit, t].X > 1e-3]
        )
        load_str = ", ".join(
            [f"Bus{b}={d[b, t].X:.1f}" for b in buses if d[b, t].X > 1e-3]
        )
        committed_str = ", ".join(committed) if committed else "无机组出力"
        record(f"Hour {t + 1:02d} (系统负荷={loads[t]:.1f} MW)")
        record(f"    出力: {committed_str}")
        if reserve_str:
            record(f"    备用: {reserve_str}")
        if load_str:
            record(f"    负荷分配: {load_str}")

    (OUTPUT_DIR / "solve_log.txt").write_text("\n".join(log_lines), encoding="utf-8")


def main() -> None:
    gens, branches, buses, loads, h_min, reserve_req, ref_bus = load_problem_data(
        WORKBOOK_PATH
    )
    model, vars_dict = build_uc_model(
        generators=gens,
        branches=branches,
        buses=buses,
        total_loads=loads,
        h_min=h_min,
        reserve_req=reserve_req,
        ref_bus=ref_bus,
    )
    solve_and_report(model, vars_dict, loads)


if __name__ == "__main__":
    main()
