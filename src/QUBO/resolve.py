from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, List

import numpy as np

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_LOG_PATH = ROOT_DIR / "output" / "Q4" / "result.log"
Q_SCRIPT_PATH = Path(__file__).with_name("Q1-QUBO_tmp.py")


def load_q1_module():
    spec = importlib.util.spec_from_file_location("q1_qubo_tmp", Q_SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载 QUBO 构建脚本: {Q_SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["q1_qubo_tmp"] = module
    spec.loader.exec_module(module)
    return module


def read_records(log_path: Path) -> List[dict[str, Any]]:
    if not log_path.exists():
        raise FileNotFoundError(f"找不到 result.log: {log_path}")
    text = log_path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError("result.log 为空")
    return json.loads(text)


def ising_to_qubo(vec: List[float]) -> np.ndarray:
    arr = np.asarray(vec, dtype=float)
    return (arr + 1.0) / 2.0


def adjust_solution_length(vec: np.ndarray, target: int) -> np.ndarray:
    current = vec.size
    if current == target:
        return vec
    if current < target:
        padded = np.zeros(target, dtype=vec.dtype)
        padded[:current] = vec
        print(
            f"警告：solutionVector 长度 {current} < 期望 {target}，"
            "已在尾部补零。"
        )
        return padded
    print(
        f"警告：solutionVector 长度 {current} > 期望 {target}，"
        "已截断多余部分。"
    )
    return vec[:target]


def analyze(log_path: Path, record_idx: int) -> None:
    q1 = load_q1_module()
    records = read_records(log_path)
    if record_idx < 0 or record_idx >= len(records):
        raise IndexError(f"record_idx={record_idx} 超出范围 [0,{len(records)-1}]")
    record = records[record_idx]
    sol_vec = ising_to_qubo(record["solutionVector"])
    energy = record.get("Hamiltonian")
    print(f"解析 record={record_idx}, Hamiltonian={energy}")

    data = q1.build_demo_uc_data(k_bits=4)
    penalty = q1.default_penalty_config(data)
    builder = q1.UCQUBOBuilder(data, penalty)
    Q = builder.build()
    sol_vec = adjust_solution_length(sol_vec, builder.var_index.n_vars)

    q1.print_decoded_solution(sol_vec, builder, data)
    uc_cost = q1.recompute_uc_cost(sol_vec, builder, data)
    qubo_cost = float(sol_vec @ (Q @ sol_vec))
    print(f"UC 总成本: {uc_cost:.2f}")
    print(f"QUBO 能量(重算): {qubo_cost:.2f}")
    report = q1.evaluate_constraint_residuals(sol_vec, builder, data)
    print("\n约束残差：")
    for item in report:
        print(
            f"- {item['name']}: count={item['count']}, "
            f"max|res|={item['max_abs']:.3e} @ {item['max_case']}, "
            f"mean|res|={item['mean_abs']:.3e}"
        )


def main():
    parser = argparse.ArgumentParser(description="解析 Kaiwu result.log 并输出 UC 结果")
    parser.add_argument(
        "--log",
        type=Path,
        default=DEFAULT_LOG_PATH,
        help=f"result.log 路径 (默认: {DEFAULT_LOG_PATH})",
    )
    parser.add_argument(
        "--record",
        type=int,
        default=0,
        help="解析的记录索引（从 0 开始）",
    )
    args = parser.parse_args()
    analyze(args.log, args.record)


if __name__ == "__main__":
    main()
