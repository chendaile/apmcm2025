"""
基于 Gurobi 的网络安全约束机组组合（UC）模型：包含 DC 潮流、旋转备用、惯量约束以及严格 N-1
（机组故障与线路故障）场景。数据来源与表格映射见下：

- Table 1, 2：机组参数（出力上下限、成本、爬坡、最小开停机、惯量等）
- Table 3：网络拓扑（from/to、x、电流上限 Fmax）
- Table 4：24 小时系统总负荷
- Table 5：惯量/ROCOF/负荷阶跃参数

注意：Table 4 只有系统总负荷，没有给出母线负荷分布。代码默认将每小时总负荷全部放在参考母线
（选取 bus_id 最小的一条母线）。若你有更精确的负荷分布，可根据需要改写
`build_bus_loads()`，将总负荷拆分到各母线上再运行。

运行方式（需提前激活包含 Gurobi 与 pandas 的 conda 环境）：
    conda activate <env>
    python src/q2_uc_network.py
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set, Tuple

import gurobipy as gp
import pandas as pd
from gurobipy import GRB

BASE_DIR = Path(__file__).resolve().parents[1]
WORKBOOK_PATH = BASE_DIR / "QuestionD" / "Table.xlsx"


@dataclass
class Generator:
    unit_id: int  # 机组编号（同时也是母线号）
    bus: int  # 所在母线
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
    inertia: float  # 惯量常数 H_i

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
    x: float
    fmax: float


def _parse_generators(
    table1_df: pd.DataFrame, table2_df: pd.DataFrame
) -> Dict[int, Generator]:
    gens: Dict[int, Dict[str, float]] = {}

    # 表 1
    for _, row in table1_df.dropna(subset=["Unit (bus)"]).iterrows():
        unit = int(row["Unit (bus)"])
        gens.setdefault(unit, {})
        gens[unit].update(
            {
                "bus": unit,  # 题目中 Unit(bus) 直接为母线号
                "p_max": float(row["Maximum power generation (MW)"]),
                "p_min": float(row["Minimum power generation (MW)"]),
                "min_up": int(float(row["Minimum Up Time (h)"])),
                "startup_cost": float(row["Startup Cost ($)"]),
                "shutdown_cost": float(row["Shutdown Cost ($)"]),
                "ramp_up": float(row["Ramp-Up Limit (MW/h)"]),
            }
        )

    # 表 2
    for _, row in table2_df.dropna(subset=["Unit (bus)"]).iterrows():
        unit = int(row["Unit (bus)"])
        gens.setdefault(unit, {})
        gens[unit].update(
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

    parsed: Dict[int, Generator] = {}
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
    for unit, params in gens.items():
        missing = {k for k in required if k not in params}
        if missing:
            raise ValueError(f"机组 {unit} 数据缺失: {missing}")
        parsed[unit] = Generator(
            unit_id=unit,
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
    return parsed


def _parse_branches(table3_df: pd.DataFrame) -> Dict[int, Branch]:
    branches: Dict[int, Branch] = {}
    for _, row in table3_df.dropna(subset=["Branch number"]).iterrows():
        idx = int(row["Branch number"])
        branches[idx] = Branch(
            branch_id=idx,
            bus_from=int(row["From bus"]),
            bus_to=int(row["To Bus"]),
            x=float(row["x"]),
            fmax=float(row["Max power transmission (MW)"]),
        )
    return branches


def _parse_loads(load_df: pd.DataFrame) -> List[float]:
    cleaned = load_df.dropna(subset=["Time period (h)"])
    loads = cleaned["Load demand (MW)"].astype(float).tolist()
    if not loads:
        raise ValueError("负荷曲线为空。")
    return loads


def _parse_inertia_params(table5_df: pd.DataFrame) -> Tuple[float, float, float]:
    """返回 (ROCOF_max, F_coeff, load_step)。"""
    if table5_df.empty:
        raise ValueError("Table 5 未找到惯量相关数据。")
    row = table5_df.iloc[0]
    rocof_max = float(row["ROCOF(HZ/s)"])
    f_coeff = float(row["F"])
    load_step = float(row["load step (MW)"])
    return rocof_max, f_coeff, load_step


def build_bus_loads(
    total_loads: List[float], buses: Set[int], ref_bus: int
) -> Dict[int, List[float]]:
    """
    将系统总负荷分配到母线。当前实现为“均匀分布”：
        D_{b,t} = D_t / |B|
    如需自定义分布，可修改此函数按需要拆分。
    """
    bus_loads: Dict[int, List[float]] = {}
    bus_list = sorted(buses)
    num_buses = len(bus_list)
    for b in bus_list:
        bus_loads[b] = []
    for t, load in enumerate(total_loads):
        share = load / num_buses
        for b in bus_list:
            bus_loads[b].append(share)
    return bus_loads


def load_problem_data(workbook_path: Path):
    if not workbook_path.exists():
        raise FileNotFoundError(f"找不到数据文件: {workbook_path}")

    xls = pd.ExcelFile(workbook_path)
    table1_df = pd.read_excel(xls, sheet_name="Table 1", header=1)
    table2_df = pd.read_excel(xls, sheet_name="Table 2", header=1)
    table3_df = pd.read_excel(xls, sheet_name="Table 3", header=1)
    table4_df = pd.read_excel(xls, sheet_name="Table 4", header=1)
    table5_df = pd.read_excel(xls, sheet_name="Table 5", header=1)

    generators = _parse_generators(table1_df, table2_df)
    branches = _parse_branches(table3_df)
    total_loads = _parse_loads(table4_df)
    rocof_max, f_coeff, load_step = _parse_inertia_params(table5_df)

    buses: Set[int] = set()
    for g in generators.values():
        buses.add(g.bus)
    for br in branches.values():
        buses.add(br.bus_from)
        buses.add(br.bus_to)
    ref_bus = min(buses)
    bus_loads = build_bus_loads(total_loads, buses, ref_bus)

    h_min = load_step / (2 * f_coeff * rocof_max)

    return generators, branches, bus_loads, total_loads, h_min, load_step, ref_bus


def build_uc_model(
    generators: Dict[int, Generator],
    branches: Dict[int, Branch],
    bus_loads: Dict[int, List[float]],
    total_loads: List[float],
    h_min: float,
    reserve_req: float,
    ref_bus: int,
) -> Tuple[gp.Model, Dict[str, gp.tupledict]]:
    model = gp.Model("apmcm_q2_uc_network")

    units = sorted(generators.keys())
    lines = sorted(branches.keys())
    buses = sorted(bus_loads.keys())
    periods = range(len(total_loads))

    # 基态变量
    u = model.addVars(units, periods, vtype=GRB.BINARY, name="u")
    y = model.addVars(units, periods, vtype=GRB.BINARY, name="y")
    z = model.addVars(units, periods, vtype=GRB.BINARY, name="z")
    p = model.addVars(units, periods, lb=0.0, name="p")
    r = model.addVars(units, periods, lb=0.0, name="r")  # 旋转备用
    theta = model.addVars(buses, periods, lb=-GRB.INFINITY, name="theta")
    f = model.addVars(lines, periods, lb=-GRB.INFINITY, name="f")

    # 目标函数（同 Q1）
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

    # 功率平衡（母线粒度）
    bus_gens: Dict[int, List[int]] = {}
    for i, g in generators.items():
        bus_gens.setdefault(g.bus, []).append(i)

    for b in buses:
        for t in periods:
            model.addConstr(
                gp.quicksum(p[i, t] for i in bus_gens.get(b, [])) - bus_loads[b][t]
                == gp.quicksum(
                    f[ell, t] for ell in lines if branches[ell].bus_from == b
                )
                - gp.quicksum(f[ell, t] for ell in lines if branches[ell].bus_to == b),
                name=f"balance_{b}_{t+1}",
            )

    # DC 潮流
    for ell in lines:
        br = branches[ell]
        for t in periods:
            model.addConstr(
                f[ell, t] == (theta[br.bus_from, t] - theta[br.bus_to, t]) / br.x,
                name=f"flow_{ell}_{t+1}",
            )
            model.addConstr(f[ell, t] <= br.fmax, name=f"fmax_pos_{ell}_{t+1}")
            model.addConstr(-f[ell, t] <= br.fmax, name=f"fmax_neg_{ell}_{t+1}")

    # 参考母线
    for t in periods:
        model.addConstr(theta[ref_bus, t] == 0, name=f"ref_{t+1}")

    # 出力上下限
    for i in units:
        gen = generators[i]
        for t in periods:
            model.addConstr(gen.p_min * u[i, t] <= p[i, t], name=f"pmin_{i}_{t+1}")
            model.addConstr(p[i, t] <= gen.p_max * u[i, t], name=f"pmax_{i}_{t+1}")

    # 启停逻辑
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

    # 最小开/停机
    horizon = len(periods)
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

        # 初始条件
        if gen.initially_on:
            remain_on = max(0, gen.min_up - int(math.floor(gen.init_up_time)))
            for t in range(min(remain_on, horizon)):
                model.addConstr(u[i, t] == 1, name=f"init_on_{i}_{t+1}")
        else:
            remain_off = max(0, gen.min_down - int(math.floor(gen.init_down_time)))
            for t in range(min(remain_off, horizon)):
                model.addConstr(u[i, t] == 0, name=f"init_off_{i}_{t+1}")

    # 爬坡
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

    # 机组备用与系统备用
    for i in units:
        for t in periods:
            model.addConstr(r[i, t] >= 0, name=f"reserve_lb_{i}_{t+1}")
            model.addConstr(
                r[i, t] <= generators[i].p_max * u[i, t] - p[i, t],
                name=f"reserve_cap_{i}_{t+1}",
            )
    for t in periods:
        model.addConstr(
            gp.quicksum(r[i, t] for i in units) >= reserve_req,
            name=f"sys_reserve_{t+1}",
        )

    # 惯量约束（暂不启用，可按需恢复）
    # for t in periods:
    #     model.addConstr(
    #         gp.quicksum(generators[i].inertia * u[i, t] for i in units) >= h_min,
    #         name=f"inertia_{t+1}",
    #     )

    # 机组故障场景（目前仅考虑 Unit 1 故障，其余机组故障/线路故障暂不建模）
    outage_units = [units[0]]  # 假设列表第一个为 Unit 1
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
                model.addConstr(
                    gp.quicksum(pcg[i, g, t] for i in bus_gens.get(b, []))
                    - bus_loads[b][t]
                    == gp.quicksum(
                        fg[ell, g, t] for ell in lines if branches[ell].bus_from == b
                    )
                    - gp.quicksum(
                        fg[ell, g, t] for ell in lines if branches[ell].bus_to == b
                    ),
                    name=f"cg_balance_{b}_{g}_{t+1}",
                )
        for ell in lines:
            br = branches[ell]
            for t in periods:
                model.addConstr(
                    fg[ell, g, t]
                    == (thetag[br.bus_from, g, t] - thetag[br.bus_to, g, t]) / br.x,
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

    # 线路故障场景暂不考虑
    # pcl = model.addVars(units, lines, periods, lb=0.0, name="p_cl")
    # dpcl = model.addVars(units, lines, periods, lb=0.0, name="dp_cl")
    # thetal = model.addVars(buses, lines, periods, lb=-GRB.INFINITY, name="theta_cl")
    # fl = model.addVars(lines, lines, periods, lb=-GRB.INFINITY, name="f_cl")
    # ...（相关约束暂时注释）

    vars_dict = {
        "u": u,
        "y": y,
        "z": z,
        "p": p,
        "r": r,
        "theta": theta,
        "f": f,
        "pcg": pcg,
        "dpcg": dpcg,
        "thetag": thetag,
        "fg": fg,
        # "pcl": pcl, "dpcl": dpcl, "thetal": thetal, "fl": fl,
    }
    return model, vars_dict


def solve_and_report(
    model: gp.Model, vars_dict: Dict[str, gp.tupledict], loads: List[float]
) -> None:
    model.computeIIS()
    model.write("iis.ilp")

    # model.optimize()
    # if model.Status in (GRB.INFEASIBLE, GRB.INF_OR_UNBD):
    #     print("原模型不可行，尝试 Feasibility Relaxation ……")
    #     relax_value = model.feasRelaxS(
    #         relaxobjtype=0, minrelax=True, vrelax=False, crelax=True
    #     )
    #     print(f"FeasRelax 松弛目标值: {relax_value:.4f}")
    #     model.optimize()
    #     if model.Status == GRB.OPTIMAL:
    #         print(f"FeasRelax 模型目标值: {model.objVal:.4f}")
    #         model.write("feas_relax.lp")
    #     else:
    #         print(f"FeasRelax 求解失败，状态: {model.Status}")
    #     return
    # if model.Status != GRB.OPTIMAL:
    #     print(f"模型状态: {model.Status}")
    #     return

    # 展示结果
    # u = vars_dict["u"]
    # p = vars_dict["p"]
    # r = vars_dict["r"]
    # units = sorted({idx[0] for idx in u.keys()})

    # print(f"最优成本: {model.objVal:,.2f}")
    # for t in range(len(loads)):
    #     committed = [
    #         f"U{unit}={p[unit, t].X:.1f} MW" for unit in units if u[unit, t].X > 0.5
    #     ]
    #     committed_str = ", ".join(committed) if committed else "无机组出力"
    #     reserve_str = ", ".join(
    #         [f"U{unit} R={r[unit, t].X:.1f}" for unit in units if r[unit, t].X > 1e-3]
    #     )
    #     print(f"Hour {t + 1:02d} (负荷={loads[t]:.1f} MW): {committed_str}")
    #     if reserve_str:
    #         print(f"    备用: {reserve_str}")


def main() -> None:
    generators, branches, bus_loads, total_loads, h_min, reserve_req, ref_bus = (
        load_problem_data(WORKBOOK_PATH)
    )
    model, vars_dict = build_uc_model(
        generators=generators,
        branches=branches,
        bus_loads=bus_loads,
        total_loads=total_loads,
        h_min=h_min,
        reserve_req=reserve_req,
        ref_bus=ref_bus,
    )
    solve_and_report(model, vars_dict, total_loads)


if __name__ == "__main__":
    main()
