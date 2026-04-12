"""
敏感性分析可视化模块
生成5个学术发表级图表，英文用Times New Roman，中文用宋体。
"""
import os
import sys
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger(__name__)

# 图表输出目录
FIGURES_DIR = Path(__file__).parent / "figures"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================================
# 字体配置（英文 Times New Roman，中文 宋体）
# ============================================================================
matplotlib.rcParams.update({
    "font.family": ["Times New Roman", "SimSun"],
    "mathtext.fontset": "stix",
    "axes.unicode_minus": False,
    "figure.dpi": 150,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
})

# 场景颜色映射
SCENARIO_COLORS = {
    "GTL-GH":    "#1f77b4",
    "GTL":       "#aec7e8",
    "GTL-BH":    "#2ca02c",
    "CTL":       "#8c564b",
    "CTL-BH":    "#c49c94",
    "CCU-GH-MTJ":"#ff7f0e",
    "CCU-GH-FT": "#ffbb78",
    "CCU-BH-MTJ":"#17becf",
    "CCU-BH-FT": "#9edae5",
    "DAC-GH-MTJ":"#9467bd",
    "DAC-GH-FT": "#c5b0d5",
    "DAC-BH-MTJ":"#e377c2",
    "DAC-BH-FT": "#f7b6d2",
}

# 参考线：基准场景 LCO（来自优化结果）
BASELINE_LCO = {
    "GTL-GH": 6.50,   # 近似参考值，待替换为实际优化结果
    "GTL": 6.50,
    "GTL-BH": 5.23,
    "CTL": None,
    "CTL-BH": None,
    "CCU-GH-MTJ": None,
    "CCU-GH-FT": 18.56,
    "CCU-BH-MTJ": None,
    "CCU-BH-FT": None,
    "DAC-GH-MTJ": None,
    "DAC-GH-FT": None,
    "DAC-BH-MTJ": None,
    "DAC-BH-FT": None,
}


def _save_fig(fig, filename: str):
    """保存图表为PNG"""
    out = FIGURES_DIR / filename
    fig.savefig(out, dpi=300, bbox_inches="tight")
    logger.info(f"图表已保存: {out}")
    plt.close(fig)


def plot_ng_price_sensitivity(
    df: pd.DataFrame,
    scenarios: Optional[List[str]] = None,
    output_filename: str = "fig_ng_price_sensitivity.png",
):
    """
    图1: 天然气价格敏感性 - LCO vs NG价格折线图
    GTL-GH, GTL, GTL-BH三条线
    """
    if scenarios is None:
        scenarios = ["GTL-GH", "GTL", "GTL-BH"]

    sub = df[(df["param_name"] == "ng_price") & (df["scenario_name"].isin(scenarios))].copy()
    if sub.empty:
        logger.warning("无NG价格敏感性数据")
        return

    sub["lco"] = pd.to_numeric(sub["lco_excluding_shortage_per_kg"], errors="coerce")
    sub["ng_price"] = pd.to_numeric(sub["param_value"], errors="coerce")

    fig, ax = plt.subplots(figsize=(7, 5))

    for sc in scenarios:
        data = sub[sub["scenario_name"] == sc].dropna(subset=["ng_price", "lco"])
        data = data.sort_values("ng_price")
        if data.empty:
            continue
        ax.plot(data["ng_price"], data["lco"],
                marker="o", label=sc,
                color=SCENARIO_COLORS.get(sc, "gray"),
                linewidth=2, markersize=6)

    # 当前基准价格参考线
    ax.axvline(x=4.2, color="gray", linestyle="--", alpha=0.6, linewidth=1.2)
    ax.text(4.2 + 0.05, ax.get_ylim()[0] * 1.02, "Base\n4.2 ¥/m³",
            fontsize=9, color="gray", va="bottom")

    ax.set_xlabel("Natural Gas Price (¥/m³)", fontsize=12)
    ax.set_ylabel("LCO-SynAF (¥/kg)", fontsize=12)
    ax.set_title("Sensitivity of LCO-SynAF to Natural Gas Price", fontsize=13)
    ax.legend(fontsize=10, framealpha=0.8)
    ax.grid(True, alpha=0.3)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.1f"))

    _save_fig(fig, output_filename)


def plot_coal_price_sensitivity(
    df: pd.DataFrame,
    scenarios: Optional[List[str]] = None,
    output_filename: str = "fig_coal_price_sensitivity.png",
):
    """
    图2: 煤炭价格敏感性 - LCO vs 煤价折线图
    CTL, CTL-BH
    """
    if scenarios is None:
        scenarios = ["CTL", "CTL-BH"]

    sub = df[(df["param_name"] == "coal_price") & (df["scenario_name"].isin(scenarios))].copy()
    if sub.empty:
        logger.warning("无煤价敏感性数据")
        return

    sub["lco"] = pd.to_numeric(sub["lco_excluding_shortage_per_kg"], errors="coerce")
    sub["coal_price"] = pd.to_numeric(sub["param_value"], errors="coerce")

    fig, ax = plt.subplots(figsize=(7, 5))

    for sc in scenarios:
        data = sub[sub["scenario_name"] == sc].dropna(subset=["coal_price", "lco"])
        data = data.sort_values("coal_price")
        if data.empty:
            continue
        ax.plot(data["coal_price"], data["lco"],
                marker="s", label=sc,
                color=SCENARIO_COLORS.get(sc, "gray"),
                linewidth=2, markersize=6)

    ax.axvline(x=525, color="gray", linestyle="--", alpha=0.6, linewidth=1.2)
    ax.text(525 + 5, ax.get_ylim()[0] * 1.02, "Base\n525 ¥/t",
            fontsize=9, color="gray", va="bottom")

    ax.set_xlabel("Coal Price (¥/ton)", fontsize=12)
    ax.set_ylabel("LCO-SynAF (¥/kg)", fontsize=12)
    ax.set_title("Sensitivity of LCO-SynAF to Coal Price", fontsize=13)
    ax.legend(fontsize=10, framealpha=0.8)
    ax.grid(True, alpha=0.3)

    _save_fig(fig, output_filename)


def plot_bh_capex_sensitivity(
    df: pd.DataFrame,
    output_filename: str = "fig_bh_capex_sensitivity.png",
):
    """
    图3: 副产氢PSA设备CAPEX敏感性 - LCO vs CAPEX折线图
    全部BH场景 (GTL-BH, CTL-BH, CCU-BH-FT, CCU-BH-MTJ, DAC-BH-FT, DAC-BH-MTJ)
    """
    bh_scenarios = ["GTL-BH", "CTL-BH", "CCU-BH-FT", "CCU-BH-MTJ", "DAC-BH-FT", "DAC-BH-MTJ"]

    sub = df[(df["param_name"] == "bh_capex") & (df["scenario_name"].isin(bh_scenarios))].copy()
    if sub.empty:
        logger.warning("无BH CAPEX敏感性数据")
        return

    sub["lco"] = pd.to_numeric(sub["lco_excluding_shortage_per_kg"], errors="coerce")
    sub["capex"] = pd.to_numeric(sub["param_value"], errors="coerce")

    fig, ax = plt.subplots(figsize=(8, 5))

    for sc in bh_scenarios:
        data = sub[sub["scenario_name"] == sc].dropna(subset=["capex", "lco"])
        data = data.sort_values("capex")
        if data.empty:
            continue
        ax.plot(data["capex"] / 1000, data["lco"],
                marker="^", label=sc,
                color=SCENARIO_COLORS.get(sc, "gray"),
                linewidth=2, markersize=6)

    # 基准CAPEX参考线（钢铁280k）
    ax.axvline(x=280, color="gray", linestyle="--", alpha=0.6, linewidth=1.2)
    ax.text(282, ax.get_ylim()[0] * 1.02, "Steel baseline\n280 k¥/(kg/h)",
            fontsize=8, color="gray", va="bottom")

    ax.set_xlabel("Byproduct H₂ PSA CAPEX (k¥ per kg/h)", fontsize=12)
    ax.set_ylabel("LCO-SynAF (¥/kg)", fontsize=12)
    ax.set_title("Sensitivity of LCO-SynAF to Byproduct H₂ Purification CAPEX", fontsize=13)
    ax.legend(fontsize=9, framealpha=0.8, ncol=2)
    ax.grid(True, alpha=0.3)

    _save_fig(fig, output_filename)


def plot_electricity_capex_heatmap(
    df: pd.DataFrame,
    scenario: str = "CCU-GH-FT",
    output_filename: Optional[str] = None,
):
    """
    图4: 电价×电解槽CAPEX二维热图 - LCO等高线/热力图
    为 CCU-GH-FT/MTJ 和 DAC-GH-FT/MTJ 各生成一张热图
    """
    if output_filename is None:
        output_filename = f"fig_electricity_capex_heatmap_{scenario}.png"

    sub = df[
        (df["param_name"] == "electricity_capex_grid") &
        (df["scenario_name"] == scenario)
    ].copy()

    if sub.empty:
        logger.warning(f"无 {scenario} 的电价×CAPEX数据")
        return

    sub["lco"] = pd.to_numeric(sub["lco_excluding_shortage_per_kg"], errors="coerce")
    sub["elec"] = pd.to_numeric(sub["electricity_price"], errors="coerce")
    sub["capex"] = pd.to_numeric(sub["electrolyzer_capex"], errors="coerce")

    pivot = sub.pivot_table(index="elec", columns="capex", values="lco", aggfunc="mean")
    pivot = pivot.sort_index(ascending=False)
    pivot_cols = sorted(pivot.columns)
    pivot = pivot[pivot_cols]

    fig, ax = plt.subplots(figsize=(8, 5))
    im = ax.imshow(
        pivot.values,
        aspect="auto",
        cmap="RdYlGn_r",
        interpolation="bilinear"
    )

    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels([f"{c/1000:.0f}k" for c in pivot.columns], fontsize=10)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels([f"{e:.2f}" for e in pivot.index], fontsize=10)

    ax.set_xlabel("Electrolyzer CAPEX (k¥ per kg/h)", fontsize=12)
    ax.set_ylabel("Grid Electricity Price (¥/kWh)", fontsize=12)
    ax.set_title(f"LCO-SynAF Heat Map: {scenario}\n(Electricity Price × Electrolyzer CAPEX)", fontsize=12)

    # 添加数值标注
    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            val = pivot.values[i, j]
            if not np.isnan(val):
                ax.text(j, i, f"{val:.1f}", ha="center", va="center",
                        fontsize=8, color="black" if val < pivot.values.max() * 0.7 else "white")

    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("LCO-SynAF (¥/kg)", fontsize=11)

    _save_fig(fig, output_filename)


def plot_dac_cost_sensitivity(
    df: pd.DataFrame,
    scenarios: Optional[List[str]] = None,
    output_filename: str = "fig_dac_cost_sensitivity.png",
):
    """
    图5: DAC捕获成本敏感性 - LCO vs DAC成本折线图
    DAC-GH-MTJ, DAC-GH-FT, DAC-BH-MTJ, DAC-BH-FT
    """
    if scenarios is None:
        scenarios = ["DAC-GH-MTJ", "DAC-GH-FT", "DAC-BH-MTJ", "DAC-BH-FT"]

    sub = df[(df["param_name"] == "dac_cost") & (df["scenario_name"].isin(scenarios))].copy()
    if sub.empty:
        logger.warning("无DAC成本敏感性数据")
        return

    sub["lco"] = pd.to_numeric(sub["lco_excluding_shortage_per_kg"], errors="coerce")
    sub["dac_cost"] = pd.to_numeric(sub["param_value"], errors="coerce")

    fig, ax = plt.subplots(figsize=(8, 5))

    for sc in scenarios:
        data = sub[sub["scenario_name"] == sc].dropna(subset=["dac_cost", "lco"])
        data = data.sort_values("dac_cost")
        if data.empty:
            continue
        ax.plot(data["dac_cost"], data["lco"],
                marker="D", label=sc,
                color=SCENARIO_COLORS.get(sc, "gray"),
                linewidth=2, markersize=6)

    # 当前基准4500 元/ton参考线
    ax.axvline(x=4500, color="gray", linestyle="--", alpha=0.6, linewidth=1.2)
    ax.text(4500 + 30, ax.get_ylim()[0] * 1.02, "Base\n4500 ¥/t",
            fontsize=9, color="gray", va="bottom")

    ax.set_xlabel("DAC Capture Cost (¥/ton CO₂)", fontsize=12)
    ax.set_ylabel("LCO-SynAF (¥/kg)", fontsize=12)
    ax.set_title("Sensitivity of LCO-SynAF to DAC Capture Cost", fontsize=13)
    ax.legend(fontsize=10, framealpha=0.8)
    ax.grid(True, alpha=0.3)
    ax.invert_xaxis()  # 从高成本（左）到低成本（右）展示降本路径

    _save_fig(fig, output_filename)


def generate_all_figures(df: Optional[pd.DataFrame] = None):
    """
    生成所有敏感性分析图表。
    如果df为None则从results目录自动加载。
    """
    if df is None:
        from products.supply_chain_optimization.sensitivity_analysis.result_collector import collect_all_results
        df = collect_all_results()

    if df.empty:
        logger.error("无可用数据，无法生成图表")
        return

    logger.info(f"开始生成图表，数据行数: {len(df)}")

    # 图1: NG价格敏感性
    plot_ng_price_sensitivity(df)

    # 图2: 煤价敏感性
    plot_coal_price_sensitivity(df)

    # 图3: BH CAPEX敏感性
    plot_bh_capex_sensitivity(df)

    # 图4: 电价×CAPEX热图（为4个相关场景各生成一张）
    for sc in ["CCU-GH-FT", "CCU-GH-MTJ", "DAC-GH-FT", "DAC-GH-MTJ"]:
        plot_electricity_capex_heatmap(df, scenario=sc)

    # 图5: DAC成本敏感性
    plot_dac_cost_sensitivity(df)

    logger.info(f"全部图表已保存到: {FIGURES_DIR}")


if __name__ == "__main__":
    generate_all_figures()
