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
kw.license.init(user_id="125012037452476418", sdk_code="FEVy7M279FBaHJUcFsnduZKOKK1HVo")

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
    lam_logic: float
    lam_UT: float
    lam_DT: float
    lam_RU: float
    lam_RD: float
    lam_p_limit: float
    lam_startstop: float


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
                self._add(("y", i, t))
                self._add(("z", i, t))

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
        self.slack_bits = {
            "p_up": 8,
            "p_low": 8,
            "ru": 8,
            "rd": 8,
            "ut": 4,
            "dt": 4,
            "yz": 1,
        }
        self.slack_weights: Dict[Tuple, float] = {}
        self._register_slack_variables()
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

    def _register_slack_variables(self) -> None:
        units = self.data.units
        times = self.data.times
        for i in units:
            p = self.data.params[i]
            for t in times:
                self._add_slack_block("p_up", i, t, p.P_max)
                span = max(p.P_max - p.P_min, 0.0)
                self._add_slack_block("p_low", i, t, span)
                self._add_slack_block("yz", i, t, 1.0)
        for i in units:
            UT_i = self.data.params[i].UT
            DT_i = self.data.params[i].DT
            for idx_t, t in enumerate(times):
                end_idx = idx_t + UT_i - 1
                if UT_i > 0 and end_idx < len(times):
                    self._add_slack_block("ut", i, t, float(UT_i))
                end_idx_dt = idx_t + DT_i - 1
                if DT_i > 0 and end_idx_dt < len(times):
                    self._add_slack_block("dt", i, t, float(DT_i))
        for i in units:
            RU_i = self.data.params[i].RU
            RD_i = self.data.params[i].RD
            p = self.data.params[i]
            span = max(p.P_max - p.P_min, 0.0)
            for idx_t in range(1, len(times)):
                t = times[idx_t]
                self._add_slack_block("ru", i, t, span + RU_i)
                self._add_slack_block("rd", i, t, span + RD_i)

    def _add_slack_block(
        self, name: str, unit: int, time: int, max_value: float
    ) -> None:
        bits = self.slack_bits.get(name, 0)
        if bits <= 0 or max_value <= 0:
            return
        weights = self._binary_weights(max_value, bits)
        if not weights:
            return
        for k, weight in enumerate(weights):
            key = ("s", name, unit, time, k)
            self.var_index.add_auxiliary(key)
            self.slack_weights[(name, unit, time, k)] = weight

    @staticmethod
    def _binary_weights(max_value: float, bits: int) -> List[float]:
        if bits <= 0 or max_value <= 0:
            return []
        denom = 2**bits - 1
        if denom <= 0:
            return []
        step = max_value / denom
        return [step * (2**k) for k in range(bits)]

    def _slack_expr(self, name: str, unit: int, time: int) -> Dict[Tuple, float]:
        expr: Dict[Tuple, float] = {}
        for k in range(self.slack_bits.get(name, 0)):
            weight = self.slack_weights.get((name, unit, time, k))
            if weight is None:
                continue
            key = ("s", name, unit, time, k)
            expr[key] = weight
        return expr

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
        for i in self.data.units:
            p = self.data.params[i]
            for t in self.data.times:
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
                self._add_linear(("y", i, t), -p.SU)
                self._add_linear(("z", i, t), p.SD)

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

    def add_power_limit_penalty(self) -> None:
        lam = self.penalty.lam_p_limit
        if lam <= 0:
            return
        for i in self.data.units:
            params = self.data.params[i]
            for t in self.data.times:
                key_u = ("u", i, t)
                P_coef = self.P_expr(i, t)

                coef_up = dict(P_coef)
                coef_up[key_u] = coef_up.get(key_u, 0.0) - params.P_max
                for key, weight in self._slack_expr("p_up", i, t).items():
                    coef_up[key] = coef_up.get(key, 0.0) + weight
                self._add_squared_penalty(coef_up, 0.0, lam)

                coef_low: Dict[Tuple, float] = {key_u: params.P_min}
                for key, value in P_coef.items():
                    coef_low[key] = coef_low.get(key, 0.0) - value
                for key, weight in self._slack_expr("p_low", i, t).items():
                    coef_low[key] = coef_low.get(key, 0.0) + weight
                self._add_squared_penalty(coef_low, 0.0, lam)

    def add_logic_penalty(self) -> None:
        lam = self.penalty.lam_logic
        for i in self.data.units:
            for idx_t in range(1, len(self.data.times)):
                t = self.data.times[idx_t]
                t_prev = self.data.times[idx_t - 1]
                coef = {
                    ("u", i, t): 1.0,
                    ("u", i, t_prev): -1.0,
                    ("y", i, t): -1.0,
                    ("z", i, t): 1.0,
                }
                for key_j, a_j in coef.items():
                    self._add_quadratic(key_j, key_j, lam * a_j * a_j)
                    for key_k, a_k in coef.items():
                        if key_k <= key_j:
                            continue
                        self._add_quadratic(key_j, key_k, lam * 2 * a_j * a_k)

    def add_start_stop_penalty(self) -> None:
        """限制同一时段不能同时启停：y_{i,t}+z_{i,t}≤1。"""

        lam = self.penalty.lam_startstop
        if lam <= 0:
            return
        for i in self.data.units:
            for t in self.data.times:
                coef = {("y", i, t): 1.0, ("z", i, t): 1.0}
                for key, weight in self._slack_expr("yz", i, t).items():
                    coef[key] = coef.get(key, 0.0) + weight
                self._add_squared_penalty(coef, -1.0, lam)

    def add_min_up_time_penalty(self) -> None:
        lam = self.penalty.lam_UT
        T = self.data.times
        for i in self.data.units:
            UT_i = self.data.params[i].UT
            for idx_t in range(len(T)):
                t = T[idx_t]
                end_idx = idx_t + UT_i - 1
                if end_idx >= len(T):
                    continue
                coef: Dict[Tuple, float] = {("y", i, t): float(UT_i)}
                for idx_tau in range(idx_t, end_idx + 1):
                    tau = T[idx_tau]
                    key_u = ("u", i, tau)
                    coef[key_u] = coef.get(key_u, 0.0) - 1.0
                for key, weight in self._slack_expr("ut", i, t).items():
                    coef[key] = coef.get(key, 0.0) + weight
                self._add_squared_penalty(coef, 0.0, lam)

    def add_min_down_time_penalty(self) -> None:
        lam = self.penalty.lam_DT
        T = self.data.times
        for i in self.data.units:
            DT_i = self.data.params[i].DT
            for idx_t in range(len(T)):
                t = T[idx_t]
                end_idx = idx_t + DT_i - 1
                if end_idx >= len(T):
                    continue
                coef: Dict[Tuple, float] = {("z", i, t): float(DT_i)}
                window = end_idx - idx_t + 1
                const = -float(window)
                for idx_tau in range(idx_t, end_idx + 1):
                    tau = T[idx_tau]
                    key_u = ("u", i, tau)
                    coef[key_u] = coef.get(key_u, 0.0) + 1.0
                for key, weight in self._slack_expr("dt", i, t).items():
                    coef[key] = coef.get(key, 0.0) + weight
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
                for key, weight in self._slack_expr("ru", i, t).items():
                    coef_RU[key] = coef_RU.get(key, 0.0) + weight
                for key, weight in self._slack_expr("rd", i, t).items():
                    coef_RD[key] = coef_RD.get(key, 0.0) + weight
                self._add_squared_penalty(coef_RU, const_RU, lam_RU)
                self._add_squared_penalty(coef_RD, const_RD, lam_RD)

    def build(self) -> np.ndarray:
        self.add_cost_terms()
        self.add_power_balance_penalty()
        self.add_power_limit_penalty()
        self.add_logic_penalty()
        self.add_start_stop_penalty()
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
        lam_logic=heavy,
        lam_startstop=heavy,
        lam_UT=medium,
        lam_DT=medium,
        lam_RU=light,
        lam_RD=light,
        lam_p_limit=heavy,
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


def slack_value(
    builder: UCQUBOBuilder, sol_vec: np.ndarray, name: str, unit: int, time: int
) -> float:
    """把 slack 比特解码成实际的非负余量。"""

    total = 0.0
    vi = builder.var_index
    for k in range(builder.slack_bits.get(name, 0)):
        weight = builder.slack_weights.get((name, unit, time, k))
        if weight is None:
            continue
        key = ("s", name, unit, time, k)
        total += weight * sol_vec[vi.idx(key)]
    return total


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
            s_up = slack_value(builder, sol_vec, "p_up", i, t)
            residues_up.append(
                (p_val - params.P_max * u_val + s_up, f"i={i},t={t:02d}")
            )
            s_low = slack_value(builder, sol_vec, "p_low", i, t)
            residues_low.append(
                (params.P_min * u_val - p_val + s_low, f"i={i},t={t:02d}")
            )
    reports.append(summarize("出力上限", residues_up))
    reports.append(summarize("出力下限", residues_low))

    # 启停逻辑 + 启停互斥
    residues_logic = []
    residues_startstop = []
    for i in data.units:
        for idx_t, t in enumerate(data.times):
            if idx_t > 0:
                t_prev = data.times[idx_t - 1]
                expr = (
                    val(("u", i, t))
                    - val(("u", i, t_prev))
                    - val(("y", i, t))
                    + val(("z", i, t))
                )
                residues_logic.append((expr, f"i={i},t={t:02d}"))
            s_yz = slack_value(builder, sol_vec, "yz", i, t)
            expr_yz = val(("y", i, t)) + val(("z", i, t)) - 1.0 + s_yz
            residues_startstop.append((expr_yz, f"i={i},t={t:02d}"))
    reports.append(summarize("启停逻辑", residues_logic))
    reports.append(summarize("启停互斥", residues_startstop))

    # 最小开停机时间
    residues_ut = []
    residues_dt = []
    for i in data.units:
        params = data.params[i]
        T = data.times
        for idx_t, t in enumerate(T):
            end_idx = idx_t + params.UT - 1
            if params.UT > 0 and end_idx < len(T):
                total_on = sum(val(("u", i, T[k])) for k in range(idx_t, end_idx + 1))
                expr_ut = (
                    params.UT * val(("y", i, t))
                    - total_on
                    + slack_value(builder, sol_vec, "ut", i, t)
                )
                residues_ut.append((expr_ut, f"i={i},t={t:02d}"))
            end_idx_dt = idx_t + params.DT - 1
            if params.DT > 0 and end_idx_dt < len(T):
                window = end_idx_dt - idx_t + 1
                total_on = sum(
                    val(("u", i, T[k])) for k in range(idx_t, end_idx_dt + 1)
                )
                expr_dt = (
                    params.DT * val(("z", i, t))
                    - (window - total_on)
                    + slack_value(builder, sol_vec, "dt", i, t)
                )
                residues_dt.append((expr_dt, f"i={i},t={t:02d}"))
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
            expr_ru = (
                p_t
                - p_prev
                - data.params[i].RU
                + slack_value(builder, sol_vec, "ru", i, t)
            )
            expr_rd = (
                p_prev
                - p_t
                - data.params[i].RD
                + slack_value(builder, sol_vec, "rd", i, t)
            )
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
    for t in data.times:
        for i in data.units:
            params = data.params[i]
            u = _binary_from_solution(sol_vec[vi.idx(("u", i, t))])
            y = _binary_from_solution(sol_vec[vi.idx(("y", i, t))])
            z = _binary_from_solution(sol_vec[vi.idx(("z", i, t))])
            p_val = compute_power_output(builder, sol_vec, i, t)
            total_cost += params.a * (p_val**2) + params.b * p_val + params.c * u
            total_cost += params.SU * y + params.SD * z
    return total_cost


def export_solution_to_excel(
    sol_vec: np.ndarray,
    builder: UCQUBOBuilder,
    data: UCData,
    constraint_report: List[Dict[str, object]],
    uc_cost: float,
    qubo_cost: float,
    output_path: Path,
) -> None:
    """把求解结果与约束统计写入 Excel，便于分析与归档。"""

    units = data.units
    times = data.times
    vi = builder.var_index

    status_rows = []
    power_rows = []
    for t in times:
        status_row = {"t": t}
        power_row = {"t": t}
        total = 0.0
        for i in units:
            u_val = _binary_from_solution(sol_vec[vi.idx(("u", i, t))])
            status_row[f"U{i}"] = u_val
            p_val = compute_power_output(builder, sol_vec, i, t)
            power_row[f"U{i}"] = p_val
            total += p_val
        power_row["total"] = total
        power_row["demand"] = data.demand[t]
        status_rows.append(status_row)
        power_rows.append(power_row)

    status_df = pd.DataFrame(status_rows)
    power_df = pd.DataFrame(power_rows)
    constraint_df = pd.DataFrame(constraint_report)
    summary_df = pd.DataFrame(
        [
            {"metric": "UC_cost", "value": uc_cost},
            {"metric": "QUBO_energy", "value": qubo_cost},
            {"metric": "variables", "value": builder.var_index.n_vars},
        ]
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
        status_df.to_excel(writer, sheet_name="status", index=False)
        power_df.to_excel(writer, sheet_name="power", index=False)
        constraint_df.to_excel(writer, sheet_name="constraints", index=False)
        summary_df.to_excel(writer, sheet_name="summary", index=False)
    print(f"已写入求解结果: {output_path}")


def main() -> None:
    # 构造数据
    data = build_demo_uc_data(k_bits=6)
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
        print("未检测到 Kaiwu SDK，跳过本地求解，仅导出 CSV。")
        return

    helper = KaiwuQuboSolver(precision_bits=8)
    sol_dict = None
    energy = None

    # 先尝试提交到 CIM 真机
    try:
        print("尝试调用 Kaiwu CIM 真机...")
        sol_dict, energy = helper.solve(Q_int8)
        if sol_dict is not None:
            print("真机返回解。")
    except Exception as err:  # pragma: no cover - 真机连接异常
        print(f"真机调用失败：{err}")

    # 若真机失败，再回退到本地模拟退火
    if sol_dict is None:
        print("改用模拟退火求解。")
        optimizer = kw.classical.SimulatedAnnealingOptimizer(
            initial_temperature=100,
            alpha=0.99,
            cutoff_temperature=0.001,
            iterations_per_t=10,
            size_limit=1000,
        )
        model = helper._build_model(Q_int8.astype(float))
        solver = kw.solver.SimpleSolver(optimizer)
        sol_dict, energy = solver.solve_qubo(model)

    if energy is not None:
        print("QUBO 能量:", energy)

    if sol_dict is None:
        print("模拟退火未返回可行解。")
        return

    sol_vec = solution_vector_from_dict(sol_dict, builder.var_index.n_vars)
    print_decoded_solution(sol_vec, builder, data)
    uc_cost = recompute_uc_cost(sol_vec, builder, data)
    qubo_cost = float(sol_vec @ (Q_original @ sol_vec))
    print(f"最优成本 (UC 目标)：{uc_cost:.2f}")
    print(f"QUBO 能量 (含常数偏移)：{qubo_cost:.2f}")
    report = evaluate_constraint_residuals(sol_vec, builder, data)
    print_constraint_report(report)
    export_path = Path("./output/Q3/solution.xlsx")
    export_solution_to_excel(
        sol_vec, builder, data, report, uc_cost, qubo_cost, export_path
    )


if __name__ == "__main__":
    main()
