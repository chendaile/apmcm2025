"""
基于 Gurobi 的经典机组组合（Unit Commitment）模型（Question D - Problem 1）。

脚本依赖 pandas 直接读取 `QuestionD/Table.xlsx` 中的机组参数与负荷曲线，搭建 UC 模型。

目标函数：
    min Σ_t Σ_i [ a_i P_it^2 + b_i P_it + c_i u_it + SU_i y_it + SD_i z_it ]

约束条件：
    - 各时段功率平衡；
    - 机组出力上下限；
    - 启停逻辑（含 y/z 互斥）；
    - 最小开/停机时间；
    - 爬坡速率限制（含初始状态处理）。

运行方式（需提前激活包含 Gurobi 与 pandas 的 conda 环境）：
    conda activate <env>
    python src/q1_uc_model.py
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import gurobipy as gp
import pandas as pd
from gurobipy import GRB

BASE_DIR = Path(__file__).resolve().parents[2]
WORKBOOK_PATH = BASE_DIR / "QuestionD" / "Table.xlsx"
OUTPUT_DIR = BASE_DIR / "output" / "Q1"


@dataclass
class Generator:
    """存放 UC 模型所需的单机参数。"""

    unit_id: int  # 机组编号
    p_max: float  # 最大出力（MW）
    p_min: float  # 最小出力（MW）
    min_up: int  # 最小开机时间（h）
    min_down: int  # 最小停机时间（h）
    startup_cost: float  # 启动成本
    shutdown_cost: float  # 停机成本
    ramp_up: float  # 爬坡上限（MW/h）
    ramp_down: float  # 下坡上限（MW/h）
    init_up_time: float  # 初始已开机时长（h）
    init_down_time: float  # 初始已停机时长（h）
    cost_a: float  # 燃料成本二次项系数
    cost_b: float  # 燃料成本一次项系数
    cost_c: float  # 燃料成本常数项

    @property
    def initially_on(self) -> int:
        """表示初始时刻机组是否带电的二元标志。"""
        if self.init_up_time > 0:
            return 1
        if self.init_down_time > 0:
            return 0
        # 若两个持续时间都为 0，则默认判定为停机
        return 0

    @property
    def initial_power(self) -> float:
        """用于爬坡约束的初始出力近似值。"""
        return self.p_min if self.initially_on else 0.0


def _parse_generator_tables(
    table1_df: pd.DataFrame, table2_df: pd.DataFrame
) -> Dict[int, Generator]:
    """将“表 1/表 2”中的机组参数合并至 Generator 对象。"""

    gens: Dict[int, Dict[str, float]] = {}

    # 表 1 的字段
    for _, row in table1_df.dropna(subset=["Unit (bus)"]).iterrows():
        unit = int(row["Unit (bus)"])
        gens.setdefault(unit, {})
        gens[unit].update(
            {
                "p_max": float(row["Maximum power generation (MW)"]),
                "p_min": float(row["Minimum power generation (MW)"]),
                "min_up": int(float(row["Minimum Up Time (h)"])),
                "startup_cost": float(row["Startup Cost ($)"]),
                "shutdown_cost": float(row["Shutdown Cost ($)"]),
                "ramp_up": float(row["Ramp-Up Limit (MW/h)"]),
            }
        )

    # 表 2 的字段
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
            }
        )

    parsed: Dict[int, Generator] = {}
    required_keys = {
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
    }
    for unit, params in gens.items():
        missing = {key for key in required_keys if key not in params}
        if missing:
            raise ValueError(f"机组 {unit} 数据缺失: {missing}")
        parsed[unit] = Generator(
            unit_id=unit,
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
        )
    return parsed


def _parse_load_profile(load_df: pd.DataFrame) -> List[float]:
    """读取 24 小时的系统负荷。"""

    cleaned = load_df.dropna(subset=["Time period (h)"])
    loads = cleaned["Load demand (MW)"].astype(float).tolist()
    if not loads:
        raise ValueError("负荷曲线为空。")
    return loads


def load_problem_data(workbook_path: Path) -> Tuple[Dict[int, Generator], List[float]]:
    """从 Excel 中读取机组参数与负荷数据。"""

    if not workbook_path.exists():
        raise FileNotFoundError(f"找不到数据文件: {workbook_path}")

    xls = pd.ExcelFile(workbook_path)
    table1_df = pd.read_excel(xls, sheet_name="Table 1", header=1)
    table2_df = pd.read_excel(xls, sheet_name="Table 2", header=1)
    load_df = pd.read_excel(xls, sheet_name="Table 4", header=1)

    generators = _parse_generator_tables(table1_df, table2_df)
    loads = _parse_load_profile(load_df)
    return generators, loads


def build_uc_model(
    generators: Dict[int, Generator], loads: List[float]
) -> Tuple[gp.Model, Dict[str, gp.tupledict]]:
    """创建并返回 UC 模型及变量字典。"""

    model = gp.Model("apmcm_q1_classical_uc")

    units = sorted(generators.keys())
    periods = range(len(loads))

    u = model.addVars(units, periods, vtype=GRB.BINARY, name="u")
    y = model.addVars(units, periods, vtype=GRB.BINARY, name="y")
    z = model.addVars(units, periods, vtype=GRB.BINARY, name="z")
    p = model.addVars(units, periods, lb=0.0, name="p")

    # 目标函数
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
        sense=GRB.MINIMIZE,
    )

    # 功率平衡
    for t in periods:
        model.addConstr(
            gp.quicksum(p[i, t] for i in units) == loads[t],
            name=f"power_balance_{t+1}",
        )

    # 出力上下限
    for i in units:
        gen = generators[i]
        for t in periods:
            model.addConstr(
                gen.p_min * u[i, t] <= p[i, t],
                name=f"pmin_{i}_{t+1}",
            )
            model.addConstr(
                p[i, t] <= gen.p_max * u[i, t],
                name=f"pmax_{i}_{t+1}",
            )

    # 启停逻辑
    for i in units:
        gen = generators[i]
        model.addConstr(
            u[i, 0] - gen.initially_on == y[i, 0] - z[i, 0],
            name=f"logic_{i}_t1",
        )
        for t in periods:
            if t == 0:
                continue
            model.addConstr(
                u[i, t] - u[i, t - 1] == y[i, t] - z[i, t],
                name=f"logic_{i}_{t+1}",
            )
        for t in periods:
            model.addConstr(
                y[i, t] + z[i, t] <= 1,
                name=f"no_simul_start_stop_{i}_{t+1}",
            )

    # 最小开/停机约束
    horizon = len(loads)
    for i in units:
        gen = generators[i]
        for t in periods:
            if t <= horizon - gen.min_up:
                model.addConstr(
                    gp.quicksum(u[i, tau] for tau in range(t, t + gen.min_up))
                    >= gen.min_up * y[i, t],
                    name=f"min_up_{i}_{t+1}",
                )
            if t <= horizon - gen.min_down:
                model.addConstr(
                    gp.quicksum(1 - u[i, tau] for tau in range(t, t + gen.min_down))
                    >= gen.min_down * z[i, t],
                    name=f"min_down_{i}_{t+1}",
                )

        # 满足初始条件带来的额外限制
        if gen.initially_on:
            remaining_on = max(0, gen.min_up - int(math.floor(gen.init_up_time)))
            for t in range(min(remaining_on, horizon)):
                model.addConstr(u[i, t] == 1, name=f"init_on_{i}_{t+1}")
        else:
            remaining_off = max(0, gen.min_down - int(math.floor(gen.init_down_time)))
            for t in range(min(remaining_off, horizon)):
                model.addConstr(u[i, t] == 0, name=f"init_off_{i}_{t+1}")

    # 爬坡约束（假设初始出力为 Pmin 或 0）
    for i in units:
        gen = generators[i]
        model.addConstr(
            p[i, 0] - gen.initial_power <= gen.ramp_up,
            name=f"ramp_up_init_{i}",
        )
        model.addConstr(
            gen.initial_power - p[i, 0] <= gen.ramp_down,
            name=f"ramp_down_init_{i}",
        )
        for t in periods:
            if t == 0:
                continue
            model.addConstr(
                p[i, t] - p[i, t - 1] <= gen.ramp_up,
                name=f"ramp_up_{i}_{t+1}",
            )
            model.addConstr(
                p[i, t - 1] - p[i, t] <= gen.ramp_down,
                name=f"ramp_down_{i}_{t+1}",
            )

    return model, {"u": u, "p": p, "y": y, "z": z}


def export_variables_to_excel(model: gp.Model, path: Path) -> None:
    """Export all variable values to an Excel file."""
    sheet_map = {"u": "commitment", "y": "startup", "z": "shutdown", "p": "generation"}

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
    """求解模型并输出每小时的机组出力，并记录日志/导出结果。"""

    log_lines: List[str] = []

    def record(msg: str) -> None:
        print(msg)
        log_lines.append(msg)

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
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUTPUT_DIR / "solve_log.txt").write_text(
            "\n".join(log_lines), encoding="utf-8"
        )
        return

    export_variables_to_excel(model, OUTPUT_DIR / "solution_variables.xlsx")

    u = vars_dict["u"]
    p = vars_dict["p"]
    y = vars_dict["y"]
    z = vars_dict["z"]
    units = sorted({idx[0] for idx in u.keys()})

    record(f"最优成本: {model.objVal:,.2f}")
    for t in range(len(loads)):
        committed = [
            f"U{unit}={p[unit, t].X:.1f} MW" for unit in units if u[unit, t].X > 0.5
        ]
        committed_str = ", ".join(committed) if committed else "无机组出力"
        record(f"Hour {t + 1:02d} (负荷={loads[t]:.1f} MW): {committed_str}")
        status_text = [
            f"U{unit}(u={int(round(u[unit, t].X))}, y={int(round(y[unit, t].X))}, z={int(round(z[unit, t].X))})"
            for unit in units
        ]
        record("    状态: " + ", ".join(status_text))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "solve_log.txt").write_text("\n".join(log_lines), encoding="utf-8")


def main() -> None:
    generators, loads = load_problem_data(WORKBOOK_PATH)
    model, vars_dict = build_uc_model(generators, loads)
    solve_and_report(model, vars_dict, loads)


if __name__ == "__main__":
    main()
