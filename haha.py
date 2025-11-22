import json
from pathlib import Path

import numpy as np

from src.QUBO.Q1_QUBO_tmp import (
    UCQUBOBuilder,
    build_demo_uc_data,
    default_penalty_config,
    evaluate_constraint_residuals,
    print_decoded_solution,
    recompute_uc_cost,
)


def load_solution_vector(
    log_path: str, record_idx: int = 0
) -> tuple[np.ndarray, float]:
    data = json.loads(Path(log_path).read_text())
    record = data[record_idx]
    ising_vec = np.asarray(record["solutionVector"], dtype=float)
    # Kaiwu 返回的是 ±1 的 Ising 量，换算成 QUBO 的 0/1
    qubo_vec = (ising_vec + 1.0) / 2.0
    return qubo_vec, float(record["Hamiltonian"])


def analyze_log(log_path: str, record_idx: int = 0) -> None:
    data = build_demo_uc_data(k_bits=4)
    penalty = default_penalty_config(data)
    builder = UCQUBOBuilder(data, penalty)
    builder.build()  # 生成 Q 矩阵并初始化变量索引

    sol_vec, energy = load_solution_vector(log_path, record_idx)
    print(f"读取记录 {record_idx} 的 Hamiltonian: {energy}")

    # 打印 u、P、成本以及约束残差
    print_decoded_solution(sol_vec, builder, data)
    uc_cost = recompute_uc_cost(sol_vec, builder, data)
    print(f"UC 目标成本: {uc_cost:.2f}")
    report = evaluate_constraint_residuals(sol_vec, builder, data)
    for item in report:
        print(
            f"{item['name']}: count={item['count']}, "
            f"max|res|={item['max_abs']:.3e} @ {item['max_case']}"
        )


if __name__ == "__main__":
    analyze_log("output/Q4/result.log", record_idx=0)
