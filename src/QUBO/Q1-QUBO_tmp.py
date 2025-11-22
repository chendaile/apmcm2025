"""
基于 `.idea/Q1_QUBO.md` 的 QUBO 结构说明、`tmp/Q1-qubo-exacple.py` 的建模骨架以及
`tmp/qubo_example.py` 给出的 Kaiwu SDK 求解示例，整理得到的问题一 QUBO 脚本。

脚本职责：
1. 用 dataclass 管理机组参数与 UC 数据；
2. 把 UC 模型的目标与约束全部展开到 Q(=x^T Q x)；
3. 若本地可用 Kaiwu SDK，则把 Q 矩阵转成 Kaiwu QUBO 模型并调用 CIM 求解；
4. `main()` 内提供一个简单的演示数据，便于快速验证 QUBO 搭建流程。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

try:
    import kaiwu as kw
    from kaiwu.common import CheckpointManager as ckpt
except Exception:  # pragma: no cover - 环境可能未安装 Kaiwu SDK
    kw = None
    ckpt = None
kw.license.init(user_id="125012037452476418", sdk_code="4VyqcPuxUOehhARKZqysoqOMakDnr3")

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
WORKBOOK_PATH = WORKSPACE_ROOT / "QuestionD" / "Table.xlsx"


@dataclass
class UnitParam:
    """存放单个机组的原始参数。"""

    P_min: float
    P_max: float
    a: float
    b: float
    c: float
    SU: float
    SD: float
    UT: int
    DT: int
    RU: float
    RD: float


@dataclass
class UCData:
    """QUBO 构建所需的最小数据载体。"""

    units: List[int]
    times: List[int]
    demand: Dict[int, float]
    params: Dict[int, UnitParam]
    K_bits: int
    delta: Dict[Tuple[int, int], float]


@dataclass
class PenaltyConfig:
    """统一管理所有惩罚系数，方便调参。"""

    lam_bal: float
    lam_UT: float
    lam_DT: float
    lam_RU: float
    lam_RD: float


def _parse_generator_tables(
    table1_df: pd.DataFrame, table2_df: pd.DataFrame
) -> Dict[int, UnitParam]:
    """从 Excel 的表 1/表 2 中提取所有机组的参数。"""

    raw: Dict[int, Dict[str, float]] = {}

    for _, row in table1_df.dropna(subset=["Unit (bus)"]).iterrows():
        unit = int(row["Unit (bus)"])
        raw.setdefault(unit, {})
        raw[unit].update(
            {
                "p_max": float(row["Maximum power generation (MW)"]),
                "p_min": float(row["Minimum power generation (MW)"]),
                "min_up": float(row["Minimum Up Time (h)"]),
                "startup_cost": float(row["Startup Cost ($)"]),
                "shutdown_cost": float(row["Shutdown Cost ($)"]),
                "ramp_up": float(row["Ramp-Up Limit (MW/h)"]),
            }
        )

    for _, row in table2_df.dropna(subset=["Unit (bus)"]).iterrows():
        unit = int(row["Unit (bus)"])
        raw.setdefault(unit, {})
        raw[unit].update(
            {
                "min_up": float(row["Minimum Up Time (h)"]),
                "min_down": float(row["Minimum Down Time (h)"]),
                "ramp_down": float(row["Ramp-Down Limit (MW/h)"]),
                "cost_a": float(row["a"]),
                "cost_b": float(row["b"]),
                "cost_c": float(row["c"]),
            }
        )

    params: Dict[int, UnitParam] = {}
    required = {
        "p_max",
        "p_min",
        "min_up",
        "min_down",
        "startup_cost",
        "shutdown_cost",
        "ramp_up",
        "ramp_down",
        "cost_a",
        "cost_b",
        "cost_c",
    }
    for unit, values in raw.items():
        missing = required - values.keys()
        if missing:
            raise ValueError(f"机组 {unit} 数据缺失: {missing}")
        params[unit] = UnitParam(
            P_min=float(values["p_min"]),
            P_max=float(values["p_max"]),
            a=float(values["cost_a"]),
            b=float(values["cost_b"]),
            c=float(values["cost_c"]),
            SU=float(values["startup_cost"]),
            SD=float(values["shutdown_cost"]),
            UT=int(round(values["min_up"])),
            DT=int(round(values["min_down"])),
            RU=float(values["ramp_up"]),
            RD=float(values["ramp_down"]),
        )
    return params


def _parse_load_profile(load_df: pd.DataFrame) -> List[float]:
    """提取 24h 负荷曲线。"""

    cleaned = load_df.dropna(subset=["Time period (h)"])
    loads = cleaned["Load demand (MW)"].astype(float).tolist()
    if not loads:
        raise ValueError("负荷曲线为空，无法构建 UC 实例。")
    return loads


def load_uc_tables(workbook_path: Path) -> Tuple[Dict[int, UnitParam], List[float]]:
    """统一入口：从 QuestionD/Table.xlsx 读取机组与负荷数据。"""

    if not workbook_path.exists():
        raise FileNotFoundError(f"找不到数据文件: {workbook_path}")

    xls = pd.ExcelFile(workbook_path)
    table1_df = pd.read_excel(xls, sheet_name="Table 1", header=1)
    table2_df = pd.read_excel(xls, sheet_name="Table 2", header=1)
    load_df = pd.read_excel(xls, sheet_name="Table 4", header=1)

    params = _parse_generator_tables(table1_df, table2_df)
    loads = _parse_load_profile(load_df)
    return params, loads


class VarIndex:
    """把 (变量类型, 机组, 时段, 比特) 映射为 QUBO 向量索引。"""

    def __init__(self, data: UCData):
        self.data = data
        self.index: Dict[Tuple, int] = {}
        self._next = 0
        self._build_index()

    def _add(self, key: Tuple) -> None:
        self.index[key] = self._next
        self._next += 1

    def add_auxiliary(self, key: Tuple) -> None:
        """外部可用的变量注册接口，用于新增 slack 等辅助变量。"""

        self._add(key)

    def _build_index(self) -> None:
        I = self.data.units
        T = self.data.times
        K = self.data.K_bits

        for i in I:
            for t in T:
                self._add(("u", i, t))

        for i in I:
            for t in T:
                for k in range(K):
                    self._add(("x", i, t, k))

    def idx(self, key: Tuple) -> int:
        return self.index[key]

    @property
    def n_vars(self) -> int:
        return self._next


class UCQUBOBuilder:
    """负责把 UC 问题转成 QUBO 矩阵。"""

    def __init__(self, data: UCData, penalty: PenaltyConfig):
        self.data = data
        self.penalty = penalty
        self.var_index = VarIndex(data)
        n = self.var_index.n_vars
        self.Q = np.zeros((n, n), dtype=float)

    def _add_linear(self, key: Tuple, coeff: float) -> None:
        p = self.var_index.idx(key)
        self.Q[p, p] += coeff

    def _add_quadratic(self, key_p: Tuple, key_q: Tuple, coeff: float) -> None:
        p = self.var_index.idx(key_p)
        q = self.var_index.idx(key_q)
        if p == q:
            self.Q[p, p] += coeff
        else:
            self.Q[p, q] += coeff
            self.Q[q, p] += coeff

    def _add_squared_penalty(
        self, coeffs: Dict[Tuple, float], const: float, lam: float
    ) -> None:
        if lam <= 0 or not coeffs:
            return
        for key_j, a_j in coeffs.items():
            if const != 0.0:
                self._add_linear(key_j, lam * 2 * const * a_j)
            self._add_quadratic(key_j, key_j, lam * a_j * a_j)
            for key_k, a_k in coeffs.items():
                if key_k <= key_j:
                    continue
                self._add_quadratic(key_j, key_k, lam * 2 * a_j * a_k)

    def P_expr(self, i: int, t: int) -> Dict[Tuple, float]:
        coef: Dict[Tuple, float] = {}
        key_u = ("u", i, t)
        coef[key_u] = self.data.params[i].P_min
        for k in range(self.data.K_bits):
            key_x = ("x", i, t, k)
            coef[key_x] = self.data.delta[(i, k)]
        return coef

    def add_cost_terms(self) -> None:
        times = self.data.times
        for i in self.data.units:
            p = self.data.params[i]
            for idx_t, t in enumerate(times):
                P_coef = self.P_expr(i, t)
                for key_j, c_j in P_coef.items():
                    self._add_quadratic(key_j, key_j, p.a * c_j * c_j)
                    for key_k, c_k in P_coef.items():
                        if key_k <= key_j:
                            continue
                        self._add_quadratic(key_j, key_k, 2 * p.a * c_j * c_k)
                for key_j, c_j in P_coef.items():
                    self._add_linear(key_j, p.b * c_j)
                self._add_linear(("u", i, t), p.c)
                # 启动成本：-SU * (u_t - u_{t} u_{t-1})
                self._add_linear(("u", i, t), -p.SU)
                if idx_t > 0:
                    t_prev = times[idx_t - 1]
                    self._add_quadratic(("u", i, t), ("u", i, t_prev), p.SU)
                # 停机成本：SD * (u_{t-1} - u_t u_{t-1})
                if idx_t > 0:
                    t_prev = times[idx_t - 1]
                    self._add_linear(("u", i, t_prev), p.SD)
                    self._add_quadratic(("u", i, t), ("u", i, t_prev), -p.SD)

    def add_power_balance_penalty(self) -> None:
        lam = self.penalty.lam_bal
        for t in self.data.times:
            h_coef: Dict[Tuple, float] = {}
            const = -self.data.demand[t]
            for i in self.data.units:
                P_coef = self.P_expr(i, t)
                for key, c in P_coef.items():
                    h_coef[key] = h_coef.get(key, 0.0) + c
            self._add_squared_penalty(h_coef, const, lam)

    def add_min_up_time_penalty(self) -> None:
        lam = self.penalty.lam_UT
        T = self.data.times
        for i in self.data.units:
            UT_i = self.data.params[i].UT
            if UT_i <= 0:
                continue
            for idx_t in range(len(T)):
                t = T[idx_t]
                end_idx = idx_t + UT_i - 1
                if end_idx >= len(T):
                    continue
                coef: Dict[Tuple, float] = {("u", i, t): float(UT_i)}
                if idx_t > 0:
                    t_prev = T[idx_t - 1]
                    coef[("u", i, t_prev)] = coef.get(("u", i, t_prev), 0.0) - float(
                        UT_i
                    )
                for idx_tau in range(idx_t, end_idx + 1):
                    tau = T[idx_tau]
                    key_u = ("u", i, tau)
                    coef[key_u] = coef.get(key_u, 0.0) - 1.0
                self._add_squared_penalty(coef, 0.0, lam)

    def add_min_down_time_penalty(self) -> None:
        lam = self.penalty.lam_DT
        T = self.data.times
        for i in self.data.units:
            DT_i = self.data.params[i].DT
            if DT_i <= 0:
                continue
            for idx_t in range(1, len(T)):
                t = T[idx_t]
                end_idx = idx_t + DT_i - 1
                if end_idx >= len(T):
                    continue
                window = end_idx - idx_t + 1
                const = -float(window)
                coef: Dict[Tuple, float] = {}
                t_prev = T[idx_t - 1]
                coef[("u", i, t_prev)] = coef.get(("u", i, t_prev), 0.0) + float(DT_i)
                coef[("u", i, t)] = coef.get(("u", i, t), 0.0) - float(DT_i)
                for idx_tau in range(idx_t, end_idx + 1):
                    tau = T[idx_tau]
                    key_u = ("u", i, tau)
                    coef[key_u] = coef.get(key_u, 0.0) + 1.0
                self._add_squared_penalty(coef, const, lam)

    def add_ramp_penalty(self) -> None:
        lam_RU = self.penalty.lam_RU
        lam_RD = self.penalty.lam_RD
        T = self.data.times
        for i in self.data.units:
            RU_i = self.data.params[i].RU
            RD_i = self.data.params[i].RD
            for idx_t in range(1, len(T)):
                t = T[idx_t]
                t_prev = T[idx_t - 1]
                coef_RU: Dict[Tuple, float] = {}
                coef_RD: Dict[Tuple, float] = {}
                const_RU = -float(RU_i)
                const_RD = -float(RD_i)
                P_t = self.P_expr(i, t)
                P_prev = self.P_expr(i, t_prev)
                for key, c in P_t.items():
                    coef_RU[key] = coef_RU.get(key, 0.0) + c
                    coef_RD[key] = coef_RD.get(key, 0.0) - c
                for key, c in P_prev.items():
                    coef_RU[key] = coef_RU.get(key, 0.0) - c
                    coef_RD[key] = coef_RD.get(key, 0.0) + c
                self._add_squared_penalty(coef_RU, const_RU, lam_RU)
                self._add_squared_penalty(coef_RD, const_RD, lam_RD)

    def build(self) -> np.ndarray:
        self.add_cost_terms()
        self.add_power_balance_penalty()
        self.add_min_up_time_penalty()
        self.add_min_down_time_penalty()
        self.add_ramp_penalty()
        return self.Q


def derive_binary_weights(
    params: Dict[int, UnitParam], k_bits: int
) -> Dict[Tuple[int, int], float]:
    """根据 [P_min,P_max] 自动生成出力二进制编码权重。"""

    delta: Dict[Tuple[int, int], float] = {}
    for i, p in params.items():
        span = max(p.P_max - p.P_min, 1e-6)
        step = span / (2**k_bits - 1)
        for k in range(k_bits):
            delta[(i, k)] = step * (2**k)
    return delta


def default_penalty_config(data: UCData) -> PenaltyConfig:
    """根据机组最高成本估计惩罚规模，让约束违规代价远大于运行成本。"""

    unit_scales = []
    for params in data.params.values():
        gen_cost = params.a * (params.P_max**2) + params.b * params.P_max + params.c
        unit_scales.append(gen_cost + params.SU + params.SD)
    base = max(unit_scales) if unit_scales else 1.0
    # 把约束代价抬升到运行成本的数百倍，逼迫求解器优先满足约束
    heavy = base * 500
    medium = base * 200
    light = base * 80
    return PenaltyConfig(
        lam_bal=heavy * 2,
        lam_UT=medium,
        lam_DT=medium,
        lam_RU=light,
        lam_RD=light,
    )


class KaiwuQuboSolver:
    """把 Q 矩阵塞进 Kaiwu SDK 并调用 CIM 求解。"""

    def __init__(self, precision_bits: int = 8, checkpoint_dir: Path | None = None):
        if kw is None:
            raise ImportError("Kaiwu SDK 未安装，无法调用真机/模拟器。")
        self.precision_bits = precision_bits
        self.checkpoint_dir = checkpoint_dir or Path("./tmp")

    def _build_model(self, Q: np.ndarray):
        n = Q.shape[0]
        model = kw.qubo.QuboModel()
        x = kw.core.ndarray((n,), "x", kw.core.Binary)
        terms = []
        for i in range(n):
            coeff = float(Q[i, i])
            if abs(coeff) > 1e-12:
                terms.append(coeff * x[i])
            for j in range(i + 1, n):
                coeff = float(Q[i, j])
                if abs(coeff) < 1e-12:
                    continue
                terms.append(coeff * x[i] * x[j])
        model.set_objective(kw.core.quicksum(terms) if terms else 0)
        return model

    def solve(self, Q: np.ndarray):
        if ckpt is not None:
            ckpt.save_dir = str(self.checkpoint_dir)
        optimizer = kw.cim.CIMOptimizer(task_name_prefix="q1_uc_qubo")
        optimizer = kw.cim.PrecisionReducer(optimizer, self.precision_bits)
        solver = kw.solver.SimpleSolver(optimizer)
        model = self._build_model(Q)
        return solver.solve_qubo(model)


def solve_with_simulated_annealing(helper: KaiwuQuboSolver, Q: np.ndarray):
    optimizer = kw.classical.SimulatedAnnealingOptimizer(
        initial_temperature=100,
        alpha=0.99,
        cutoff_temperature=0.001,
        iterations_per_t=10,
        size_limit=1000,
    )
    solver = kw.solver.SimpleSolver(optimizer)
    model = helper._build_model(Q)
    return solver.solve_qubo(model)


def summarize_qubo(Q: np.ndarray) -> Dict[str, float]:
    """返回若干便于排查的统计信息。"""

    non_zero = np.count_nonzero(np.triu(Q))
    return {
        "dimension": int(Q.shape[0]),
        "non_zero_upper": int(non_zero),
        "density": float(non_zero / (Q.shape[0] * (Q.shape[0] + 1) / 2)),
        "max_abs_coeff": float(np.max(np.abs(Q))) if Q.size else 0.0,
    }


def build_demo_uc_data(workbook_path: Path | None = None, *, k_bits: int = 6) -> UCData:
    """从 QuestionD/Table.xlsx 读取真实参数，返回 UCData。"""

    path = Path(workbook_path) if workbook_path else WORKBOOK_PATH
    params, loads = load_uc_tables(path)

    units = sorted(params.keys())
    times = list(range(1, len(loads) + 1))
    demand = {t: loads[t - 1] for t in times}
    delta = derive_binary_weights(params, k_bits)

    return UCData(
        units=units,
        times=times,
        demand=demand,
        params=params,
        K_bits=k_bits,
        delta=delta,
    )


def solution_vector_from_dict(sol, n: int) -> np.ndarray:
    """将求解器输出统一转成长度 n 的向量。"""

    vec = np.zeros(n, dtype=float)
    if isinstance(sol, dict):
        for name, value in sol.items():
            try:
                idx = int(name.split("[", 1)[1].rstrip("]"))
            except Exception:
                continue
            vec[idx] = value
    else:
        arr = np.asarray(sol).flatten()
        vec[: min(len(arr), n)] = arr[: min(len(arr), n)]
    return vec


def _binary_from_solution(value: float) -> int:
    """把连续值投影到 {0,1}，避免数值噪声导致启停误判。"""

    return int(min(1.0, max(0.0, round(value))))


def compute_power_output(
    builder: UCQUBOBuilder, sol_vec: np.ndarray, unit: int, time: int
) -> float:
    """根据二进制出力比特解码某机组的实际出力。"""

    vi = builder.var_index
    p_val = 0.0
    for key, coeff in builder.P_expr(unit, time).items():
        p_val += coeff * sol_vec[vi.idx(key)]
    return p_val


def print_decoded_solution(
    sol_vec: np.ndarray, builder: UCQUBOBuilder, data: UCData
) -> None:
    """按照题目需求打印 u_{i,t} 与实际出力。"""

    vi = builder.var_index
    units = data.units
    times = data.times

    print("\n=== 机组开机状态 u_{i,t} ===")
    for t in times:
        states = []
        for i in units:
            idx = vi.idx(("u", i, t))
            states.append(_binary_from_solution(sol_vec[idx]))
        state_str = ", ".join(f"U{i}={state}" for i, state in zip(units, states))
        print(f"t={t:02d}: {state_str}")

    print("\n=== 机组出力 P_{i,t} (MW) ===")
    for t in times:
        outputs = []
        total = 0.0
        for i in units:
            p_val = compute_power_output(builder, sol_vec, i, t)
            total += p_val
            outputs.append(f"U{i}={p_val:.1f}")
        print(
            f"t={t:02d}: {'; '.join(outputs)} | 总出力={total:.1f}MW, 需求={data.demand[t]:.1f}MW"
        )


def evaluate_constraint_residuals(
    sol_vec: np.ndarray, builder: UCQUBOBuilder, data: UCData
) -> List[Dict[str, object]]:
    """计算所有约束的残差，方便判断惩罚是否足够大。"""

    vi = builder.var_index

    def val(key: Tuple) -> float:
        return sol_vec[vi.idx(key)]

    def summarize(name: str, residues: List[Tuple[float, str]]) -> Dict[str, object]:
        if not residues:
            return {
                "name": name,
                "count": 0,
                "max_abs": 0.0,
                "mean_abs": 0.0,
                "max_case": "N/A",
            }
        max_value, label = max(residues, key=lambda item: abs(item[0]))
        mean_abs = sum(abs(v) for v, _ in residues) / len(residues)
        return {
            "name": name,
            "count": len(residues),
            "max_abs": abs(max_value),
            "mean_abs": mean_abs,
            "max_case": f"{label} (res={max_value:.3e})",
        }

    reports: List[Dict[str, object]] = []

    # 功率平衡
    residues = []
    for t in data.times:
        total = sum(compute_power_output(builder, sol_vec, i, t) for i in data.units)
        residues.append((total - data.demand[t], f"t={t:02d}"))
    reports.append(summarize("功率平衡", residues))

    # 功率上下限
    residues_up = []
    residues_low = []
    for i in data.units:
        params = data.params[i]
        for t in data.times:
            p_val = compute_power_output(builder, sol_vec, i, t)
            u_val = val(("u", i, t))
            residues_up.append((p_val - params.P_max * u_val, f"i={i},t={t:02d}"))
            residues_low.append((params.P_min * u_val - p_val, f"i={i},t={t:02d}"))
    reports.append(summarize("出力上限", residues_up))
    reports.append(summarize("出力下限", residues_low))

    # 最小开停机时间
    residues_ut = []
    residues_dt = []
    for i in data.units:
        params = data.params[i]
        T = data.times
        if params.UT > 0:
            for idx_t, t in enumerate(T):
                end_idx = idx_t + params.UT - 1
                if end_idx >= len(T):
                    continue
                expr = params.UT * val(("u", i, t))
                if idx_t > 0:
                    t_prev = T[idx_t - 1]
                    expr -= params.UT * val(("u", i, t_prev))
                total_on = sum(val(("u", i, T[k])) for k in range(idx_t, end_idx + 1))
                expr -= total_on
                residues_ut.append((expr, f"i={i},t={t:02d}"))
        if params.DT > 0:
            for idx_t in range(1, len(T)):
                t = T[idx_t]
                end_idx_dt = idx_t + params.DT - 1
                if end_idx_dt >= len(T):
                    continue
                window = end_idx_dt - idx_t + 1
                t_prev = T[idx_t - 1]
                expr = params.DT * (val(("u", i, t_prev)) - val(("u", i, t)))
                total_on = sum(
                    val(("u", i, T[k])) for k in range(idx_t, end_idx_dt + 1)
                )
                expr += total_on - float(window)
                residues_dt.append((expr, f"i={i},t={t:02d}"))
    reports.append(summarize("最小开机时间", residues_ut))
    reports.append(summarize("最小停机时间", residues_dt))

    # 爬坡
    residues_ru = []
    residues_rd = []
    for i in data.units:
        T = data.times
        for idx_t in range(1, len(T)):
            t = T[idx_t]
            t_prev = T[idx_t - 1]
            p_t = compute_power_output(builder, sol_vec, i, t)
            p_prev = compute_power_output(builder, sol_vec, i, t_prev)
            expr_ru = p_t - p_prev - data.params[i].RU
            expr_rd = p_prev - p_t - data.params[i].RD
            residues_ru.append((expr_ru, f"i={i},t={t:02d}"))
            residues_rd.append((expr_rd, f"i={i},t={t:02d}"))
    reports.append(summarize("爬坡上限", residues_ru))
    reports.append(summarize("爬坡下限", residues_rd))

    return reports


def print_constraint_report(report: List[Dict[str, object]]) -> None:
    """美化输出约束残差。"""

    print("\n=== 约束残差统计 ===")
    for item in report:
        print(
            f"{item['name']}: count={item['count']}, "
            f"max|res|={item['max_abs']:.3e} @ {item['max_case']}, "
            f"mean|res|={item['mean_abs']:.3e}"
        )


def recompute_uc_cost(
    sol_vec: np.ndarray, builder: UCQUBOBuilder, data: UCData
) -> float:
    """用原始 UC 目标公式（发电成本 + 启停成本）评估解的真实代价。"""

    vi = builder.var_index
    total_cost = 0.0
    times = data.times
    for idx_t, t in enumerate(times):
        for i in data.units:
            params = data.params[i]
            u = _binary_from_solution(sol_vec[vi.idx(("u", i, t))])
            if idx_t > 0:
                t_prev = times[idx_t - 1]
                u_prev = _binary_from_solution(sol_vec[vi.idx(("u", i, t_prev))])
            else:
                u_prev = 0
            start = u * (1 - u_prev)
            stop = u_prev * (1 - u)
            p_val = compute_power_output(builder, sol_vec, i, t)
            total_cost += params.a * (p_val**2) + params.b * p_val + params.c * u
            total_cost += params.SU * start + params.SD * stop
    return total_cost


def export_qubo_matrix_to_csv(Q: np.ndarray, output_path: Path) -> None:
    """直接把 Q 矩阵写成 dense CSV（与官方模板一致），避免依赖缺失的 SDK API。"""

    dense = np.asarray(Q, dtype=float)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(dense).to_csv(output_path, index=False, header=False)
    print(f"已导出 QUBO CSV（尺寸 {dense.shape[0]}×{dense.shape[1]}）: {output_path}")


def main() -> None:
    # 构造数据
    data = build_demo_uc_data(k_bits=4)
    penalty = default_penalty_config(data)
    builder = UCQUBOBuilder(data, penalty)
    Q_original = builder.build().copy()
    Q = Q_original.copy()

    max_abs = float(np.max(np.abs(Q))) if Q.size else 0.0
    if max_abs > 0.0:
        Q = Q / max_abs * 100.0

    Q_clipped = np.clip(Q, -128, 127)
    Q_int8 = np.rint(Q_clipped).astype(np.int8)
    # 打印统计信息
    stats = summarize_qubo(Q_int8)
    print("QUBO 统计：", stats)
    print("变量个数（bit）=", builder.var_index.n_vars)
    print("矩阵最小值:", Q_int8.min())
    print("矩阵最大值:", Q_int8.max())
    print("矩阵类型:", Q_int8.dtype)

    if kw is None:
        print("未检测到 Kaiwu SDK，无法进行真机或模拟器求解。")
        return

    helper = KaiwuQuboSolver(precision_bits=8)
    sol_dict = None
    energy = None

    try:
        print("尝试调用 Kaiwu CIM 真机...")
        sol_dict, energy = helper.solve(Q_int8.astype(float))
        if sol_dict is not None:
            print("真机返回解。")
    except Exception as err:
        print(f"真机调用失败：{err}")

    # if sol_dict is None:
    #     print("改用模拟退火求解。")
    #     sol_dict, energy = solve_with_simulated_annealing(helper, Q_int8.astype(float))

    if sol_dict is None:
        print("求解器未返回可行解。")
        return

    if energy is not None:
        print("QUBO 能量:", energy)

    sol_vec = solution_vector_from_dict(sol_dict, builder.var_index.n_vars)
    print_decoded_solution(sol_vec, builder, data)
    uc_cost = recompute_uc_cost(sol_vec, builder, data)
    qubo_cost = float(sol_vec @ (Q_original @ sol_vec))
    print(f"最优成本 (UC 目标)：{uc_cost:.2f}")
    print(f"QUBO 能量 (含常数偏移)：{qubo_cost:.2f}")
    report = evaluate_constraint_residuals(sol_vec, builder, data)
    print_constraint_report(report)


if __name__ == "__main__":
    main()
