"""根据求解输出自动生成论文插图与概要统计。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Tuple

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

matplotlib.use("Agg")

BASE_DIR = Path(__file__).resolve().parents[2]
OUTPUT_DIR = BASE_DIR / "output"
PAPER_FIG_DIR = BASE_DIR / "Paper" / "figures"
WORKBOOK_PATH = BASE_DIR / "QuestionD" / "Table.xlsx"

VarKey = Tuple[int, int]


def _load_sheet(path: Path, sheet: str, prefix: str) -> pd.DataFrame:
    """读取变量表并解析名称，如 p[1,0] -> unit=1, t=0。"""

    df = pd.read_excel(path, sheet_name=sheet)
    records = []
    for _, row in df.iterrows():
        raw = str(row["variable"]).strip()
        if not raw.startswith(f"{prefix}[") or not raw.endswith("]"):
            continue
        try:
            inside = raw.split("[", 1)[1].rstrip("]")
            idx1_str, idx2_str = inside.split(",")
            idx1, idx2 = int(idx1_str), int(idx2_str)
        except Exception:
            continue
        records.append({"idx1": idx1, "idx2": idx2, "value": float(row["value"])})
    return pd.DataFrame(records)


def _load_generation(path: Path) -> pd.DataFrame:
    gen_df = _load_sheet(path, "generation", "p")
    return gen_df.rename(columns={"idx1": "unit", "idx2": "t"})


def _load_reserve(path: Path) -> pd.DataFrame:
    res_df = _load_sheet(path, "reserve", "r")
    return res_df.rename(columns={"idx1": "unit", "idx2": "t"})


def _load_bus_load(path: Path) -> pd.DataFrame:
    load_df = _load_sheet(path, "load", "d")
    return load_df.rename(columns={"idx1": "bus", "idx2": "t"})


def _load_load_curve() -> pd.DataFrame:
    """读取 Table 4 的24小时总负荷。"""

    xls = pd.ExcelFile(WORKBOOK_PATH)
    load_df = pd.read_excel(xls, sheet_name="Table 4", header=1)
    cleaned = load_df.dropna(subset=["Time period (h)"])
    return pd.DataFrame(
        {"t": range(len(cleaned)), "load": cleaned["Load demand (MW)"].astype(float).tolist()}
    )


def _pivot(df: pd.DataFrame, index: str, columns: str) -> pd.DataFrame:
    """将长表转换为时间x实体矩阵，缺失值补0。"""

    wide = df.pivot_table(index=index, columns=columns, values="value", aggfunc="sum")
    return wide.fillna(0.0).sort_index()


def _plot_dispatch(gen_df: pd.DataFrame, load_curve: pd.DataFrame, title: str, output_path: Path) -> None:
    wide = _pivot(gen_df, index="t", columns="unit")
    t_hours = wide.index + 1

    plt.figure(figsize=(10, 5))
    plt.stackplot(t_hours, wide.T.values, labels=[f"U{u}" for u in wide.columns], alpha=0.85)
    plt.plot(load_curve["t"] + 1, load_curve["load"], color="k", linewidth=2.0, label="系统负荷")
    plt.xlabel("时段 (h)")
    plt.ylabel("出力 / MW")
    plt.title(title)
    plt.legend(loc="upper right", ncol=3, fontsize=8)
    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300)
    plt.close()


def _plot_reserve(reserve_df: pd.DataFrame, requirement: float, output_path: Path) -> None:
    total = reserve_df.groupby("t")["value"].sum().reset_index()
    plt.figure(figsize=(10, 4))
    plt.plot(total["t"] + 1, total["value"], marker="o", label="机组可用备用总量")
    plt.axhline(requirement, color="r", linestyle="--", label=f"需求 {requirement:.0f} MW")
    plt.xlabel("时段 (h)")
    plt.ylabel("备用容量 / MW")
    plt.title("旋转备用裕度与需求对比")
    plt.legend()
    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300)
    plt.close()


def _plot_bus_load_heatmap(bus_load: pd.DataFrame, output_path: Path) -> None:
    if bus_load.empty:
        return
    wide = _pivot(bus_load, index="bus", columns="t")
    plt.figure(figsize=(10, 6))
    sns.heatmap(wide, cmap="YlGnBu", cbar_kws={"label": "负荷 (MW)"})
    plt.xlabel("时段 (h)")
    plt.ylabel("母线编号")
    plt.title("各母线柔性负荷分配热力图")
    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300)
    plt.close()


def _describe_cost(log_path: Path) -> str:
    if not log_path.exists():
        return ""
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("最优成本"):
            return line.replace("最优成本:", "").strip()
    return ""


def generate_all_figures() -> Dict[str, Path]:
    figures: Dict[str, Path] = {}

    load_curve = _load_load_curve()

    q1_path = OUTPUT_DIR / "Q1" / "solution_variables.xlsx"
    q1_gen = _load_generation(q1_path)
    _plot_dispatch(q1_gen, load_curve, "问题1：经典机组组合出力曲线", PAPER_FIG_DIR / "q1_dispatch.png")
    figures["q1_dispatch"] = PAPER_FIG_DIR / "q1_dispatch.png"

    q2_path = OUTPUT_DIR / "Q2-no-inertia" / "solution_variables.xlsx"
    q2_gen = _load_generation(q2_path)
    _plot_dispatch(q2_gen, load_curve, "问题2：含潮流与备用的机组出力", PAPER_FIG_DIR / "q2_dispatch.png")
    figures["q2_dispatch"] = PAPER_FIG_DIR / "q2_dispatch.png"

    q2_res = _load_reserve(q2_path)
    _plot_reserve(q2_res, requirement=600.0, output_path=PAPER_FIG_DIR / "q2_reserve.png")
    figures["q2_reserve"] = PAPER_FIG_DIR / "q2_reserve.png"

    q2_bus_load = _load_bus_load(q2_path)
    if not q2_bus_load.empty:
        _plot_bus_load_heatmap(q2_bus_load, PAPER_FIG_DIR / "q2_bus_load.png")
        figures["q2_bus_load"] = PAPER_FIG_DIR / "q2_bus_load.png"

    # 写入文字概要，方便论文引用
    summary_lines = []
    q1_cost = _describe_cost(OUTPUT_DIR / "Q1" / "solve_log.txt")
    q2_cost = _describe_cost(OUTPUT_DIR / "Q2-no-inertia" / "solve_log.txt")
    if q1_cost:
        summary_lines.append(f"问题1最优成本: {q1_cost}")
    if q2_cost:
        summary_lines.append(f"问题2最优成本: {q2_cost}")
    if summary_lines:
        (PAPER_FIG_DIR / "summary.txt").write_text("\n".join(summary_lines), encoding="utf-8")

    return figures


if __name__ == "__main__":
    generate_all_figures()
