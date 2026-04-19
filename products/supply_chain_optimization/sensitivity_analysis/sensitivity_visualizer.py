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
import matplotlib.patches
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

    # 6–8 yuan/kg 市场价格窗口色带
    ax.axhspan(6.0, 8.0, color="#d9ead3", alpha=0.45, zorder=0)
    ax.axhline(y=6.0, color="#6aa84f", linestyle=":", linewidth=0.8, alpha=0.7)
    ax.axhline(y=8.0, color="#6aa84f", linestyle=":", linewidth=0.8, alpha=0.7)

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
    ax.text(4.35, 5.0, "Baseline\n4.2 ¥/m³",
            fontsize=8.5, color="#555555", va="bottom")

    # 市场窗口标注
    ax.text(8.08, 7.0, "Market\nwindow\n6–8 ¥/kg",
            fontsize=8, color="#4a7c3f", va="center", ha="left")

    ax.set_xlabel("Natural Gas Price (¥/m³)", fontsize=12)
    ax.set_ylabel("LCO-SynAF (¥/kg)", fontsize=12)
    ax.set_title("Sensitivity of LCO-SynAF to Natural Gas Price\n(GTL, GTL-GH, GTL-BH)", fontsize=12)
    ax.legend(fontsize=10, framealpha=0.8)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(1.8, 8.5)
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

    ax.set_xlabel(r"Byproduct H$_2$ PSA CAPEX (k¥ per kg/h)", fontsize=12)
    ax.set_ylabel("LCO-SynAF (¥/kg)", fontsize=12)
    ax.set_title(r"Sensitivity of LCO-SynAF to Byproduct H$_2$ Purification CAPEX", fontsize=13)
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

    ax.set_xlabel(r"DAC Capture Cost (¥/ton CO$_2$)", fontsize=12)
    ax.set_ylabel("LCO-SynAF (¥/kg)", fontsize=12)
    ax.set_title(r"Sensitivity of LCO-SynAF to DAC Capture Cost", fontsize=13)
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


# ============================================================================
# 附录专用发表级图表（Times New Roman + SimSun）
# ============================================================================

def _apply_pub_style(ax, xlabel: str, ylabel: str, title: str = ""):
    """统一附录图表样式"""
    ax.set_xlabel(xlabel, fontsize=12, fontfamily="Times New Roman")
    ax.set_ylabel(ylabel, fontsize=12, fontfamily="Times New Roman")
    if title:
        ax.set_title(title, fontsize=12, fontfamily="Times New Roman")
    ax.tick_params(labelsize=10)
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_fontfamily("Times New Roman")
    ax.grid(True, alpha=0.3, linewidth=0.6)


def plot_ng_price_sensitivity_appendix(
    vals: dict = None,
    output_filename: str = "fig_ng_price_sensitivity_appendix.png",
):
    """
    附录图：GTL 和 GTL-BH 天然气价格敏感性
    标注：市场窗口色带、GTL阈值线、GTL-BH上界线、基准线
    """
    if vals is None:
        from products.supply_chain_optimization.sensitivity_analysis.sensitivity_data_analyzer import get_all_appendix_values
        vals = get_all_appendix_values()

    ng = vals["_ng"]["per_scenario"]
    gtl_threshold   = vals["gtl_ng_threshold"]
    gtlbh_upper     = vals["gtlbh_ng_upper_threshold"]
    gtl_eff_ng      = vals.get("gtl_effective_baseline_ng", 2.53)
    gtlbh_eff_ng    = vals.get("gtlbh_effective_baseline_ng", 2.47)
    gtl_lco_base    = vals["gtl_lco_at_baseline"]
    gtlbh_lco_base  = vals["gtlbh_lco_at_baseline"]

    fig, ax = plt.subplots(figsize=(7, 5))

    # 市场窗口色带
    ax.axhspan(6.0, 8.0, color="#d9ead3", alpha=0.5, zorder=0, label="Market window (6–8 ¥/kg)")
    ax.axhline(y=6.0, color="#6aa84f", linestyle=":", linewidth=0.9, alpha=0.8)
    ax.axhline(y=8.0, color="#6aa84f", linestyle=":", linewidth=0.9, alpha=0.8)

    colors = {"GTL": "#1f77b4", "GTL-GH": "#aec7e8", "GTL-BH": "#2ca02c"}
    markers = {"GTL": "o", "GTL-GH": "s", "GTL-BH": "^"}
    for sc in ["GTL", "GTL-GH", "GTL-BH"]:
        if sc not in ng:
            continue
        x = np.array(ng[sc]["ng_values"])
        y = np.array(ng[sc]["lco_values"])
        ax.plot(x, y, marker=markers[sc], label=sc,
                color=colors.get(sc, "gray"), linewidth=2, markersize=6)

    # 有效基准点（主结果对应的 NG 价格和 LCO）
    ax.scatter([gtl_eff_ng], [gtl_lco_base], s=80, color="#1f77b4",
               marker="D", zorder=5, label=f"GTL baseline ({gtl_eff_ng:.2f} ¥/m³)")
    ax.scatter([gtlbh_eff_ng], [gtlbh_lco_base], s=80, color="#2ca02c",
               marker="D", zorder=5, label=f"GTL-BH baseline ({gtlbh_eff_ng:.2f} ¥/m³)")

    # 有效基准竖线（主模型实际使用的管道价格）
    ax.axvline(x=gtl_eff_ng, color="gray", linestyle=":", linewidth=1.0, alpha=0.7)
    ax.text(gtl_eff_ng + 0.06, 15.5,
            f"Effective baseline\n{gtl_eff_ng:.2f} ¥/m³\n(pipeline avg.)",
            fontsize=7.5, color="gray", va="top", fontfamily="Times New Roman")

    # GTL 阈值竖线（LCO=8.0 处）
    if not np.isnan(gtl_threshold):
        ax.axvline(x=gtl_threshold, color="#1f77b4", linestyle="--", linewidth=1.2, alpha=0.8)
        ax.text(gtl_threshold + 0.08, 4.8,
                f"GTL exits window\n{gtl_threshold:.2f} ¥/m³\n(+{vals['gtl_ng_pct_from_baseline']:.0f}%)",
                fontsize=8, color="#1f77b4", va="bottom",
                fontfamily="Times New Roman")

    # GTL-BH 上界竖线（仅当在图范围内时显示）
    if not np.isnan(gtlbh_upper) and gtlbh_upper <= 8.5:
        ax.axvline(x=gtlbh_upper, color="#2ca02c", linestyle="--", linewidth=1.2, alpha=0.8)
        ax.text(gtlbh_upper + 0.08, 9.5,
                f"GTL-BH exits\n{gtlbh_upper:.2f} ¥/m³",
                fontsize=8, color="#2ca02c", va="bottom",
                fontfamily="Times New Roman")

    _apply_pub_style(ax,
                     "Natural Gas Price (¥/m³)",
                     "LCO-SynAF (¥/kg)",
                     "Natural-Gas Price Sensitivity: GTL and GTL-BH")
    ax.legend(fontsize=8.5, framealpha=0.8, loc="upper left")
    ax.set_xlim(1.8, 8.5)
    ax.set_ylim(3.5, 18.0)

    _save_fig(fig, output_filename)
    logger.info(f"附录图已保存: {FIGURES_DIR / output_filename}")


def plot_bh_capex_sensitivity_appendix(
    vals: dict = None,
    output_filename: str = "fig_bh_capex_sensitivity_appendix.png",
):
    """
    附录图：GTL-BH 副产氢 CAPEX 敏感性
    标注：市场窗口、钢铁/炼油基准线、斜率注释、GTL基准LCO参考线
    """
    if vals is None:
        from products.supply_chain_optimization.sensitivity_analysis.sensitivity_data_analyzer import get_all_appendix_values
        vals = get_all_appendix_values()

    bh = vals["_bh"]["per_scenario"].get("GTL-BH", {})
    gtl_lco = vals["bh_gtl_baseline_lco"]
    slope = vals["bh_slope_per_100k"]

    x = np.array(bh.get("capex_values", []))
    y = np.array(bh.get("lco_values", []))

    if len(x) == 0:
        logger.warning("GTL-BH BH CAPEX数据为空，跳过附录图")
        return

    fig, ax = plt.subplots(figsize=(7, 5))

    # 市场窗口
    ax.axhspan(6.0, 8.0, color="#d9ead3", alpha=0.5, zorder=0, label="Market window (6–8 ¥/kg)")
    ax.axhline(y=6.0, color="#6aa84f", linestyle=":", linewidth=0.9, alpha=0.8)
    ax.axhline(y=8.0, color="#6aa84f", linestyle=":", linewidth=0.9, alpha=0.8)

    # GTL 主结果 LCO 参考线（来自主优化，不受 BH CAPEX 影响）
    if not np.isnan(gtl_lco):
        ax.axhline(y=gtl_lco, color="#1f77b4", linestyle="--", linewidth=1.2, alpha=0.7)
        ax.text(155, gtl_lco + 0.06,
                f"GTL baseline LCO: {gtl_lco:.3f} ¥/kg\n(main result)",
                fontsize=8, color="#1f77b4", va="bottom", fontfamily="Times New Roman")

    # GTL-BH 折线
    ax.plot(x / 1000, y, marker="^", color="#2ca02c", linewidth=2, markersize=7,
            label="GTL-BH")

    # 钢铁/炼油基准垂线
    ax.axvline(x=280, color="gray", linestyle="--", linewidth=1.0, alpha=0.7)
    ax.axvline(x=224, color="gray", linestyle=":", linewidth=1.0, alpha=0.7)
    ax.text(282, 5.0, "Steel\n280k", fontsize=8, color="gray",
            va="bottom", fontfamily="Times New Roman")
    ax.text(226, 5.0, "Refinery\n224k", fontsize=8, color="gray",
            va="bottom", fontfamily="Times New Roman")

    # 斜率注释
    mid_x = (x.min() + x.max()) / 2 / 1000
    mid_y = float(np.interp(mid_x * 1000, x, y))
    ax.annotate(f"Slope ≈ {slope:.3f} ¥/kg\nper 100k ¥/(kg/h)",
                xy=(mid_x, mid_y),
                xytext=(mid_x + 50, mid_y - 0.15),
                fontsize=8, color="#2ca02c",
                fontfamily="Times New Roman",
                arrowprops=dict(arrowstyle="->", color="#2ca02c", lw=0.8))

    _apply_pub_style(ax,
                     r"PSA+Compression CAPEX (k¥ per kg H$_2$/h)",
                     "LCO-SynAF (¥/kg)",
                     r"Byproduct H$_2$ Purification CAPEX Sensitivity: GTL-BH")
    ax.legend(fontsize=9, framealpha=0.8)
    ax.set_xlim(120, 420)

    _save_fig(fig, output_filename)
    logger.info(f"附录图已保存: {FIGURES_DIR / output_filename}")


def plot_electricity_capex_heatmap_appendix(
    vals: dict = None,
    scenario: str = "CCU-GH-MTJ",
    output_filename: str = "fig_electricity_capex_heatmap_appendix.png",
):
    """
    附录图：CCU-GH-MTJ 电价×电解槽CAPEX热图
    注：实际数据显示电价对LCO无影响，仅CAPEX有效，图中标注说明。
    """
    if vals is None:
        from products.supply_chain_optimization.sensitivity_analysis.sensitivity_data_analyzer import get_all_appendix_values
        vals = get_all_appendix_values()

    pivots = vals["_ec"].get("pivots", {})
    pivot = pivots.get(scenario)
    if pivot is None or pivot.empty:
        logger.warning(f"无 {scenario} 热图数据，跳过")
        return

    pivot_sorted = pivot.sort_index(ascending=False)
    col_order = sorted(pivot_sorted.columns.astype(float))
    pivot_sorted = pivot_sorted[[c for c in col_order]]

    fig, ax = plt.subplots(figsize=(8, 5))
    im = ax.imshow(pivot_sorted.values, aspect="auto",
                   cmap="YlOrRd", interpolation="bilinear")

    capex_labels = [f"{int(c/1000)}k" for c in col_order]
    elec_labels = [f"{e:.2f}" for e in pivot_sorted.index]
    ax.set_xticks(range(len(col_order)))
    ax.set_xticklabels(capex_labels, fontsize=10, fontfamily="Times New Roman")
    ax.set_yticks(range(len(pivot_sorted.index)))
    ax.set_yticklabels(elec_labels, fontsize=10, fontfamily="Times New Roman")

    # 数值标注
    for i in range(len(pivot_sorted.index)):
        for j in range(len(col_order)):
            val = pivot_sorted.values[i, j]
            if not np.isnan(val):
                ax.text(j, i, f"{val:.1f}", ha="center", va="center",
                        fontsize=8.5, color="black",
                        fontfamily="Times New Roman")

    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("LCO-SynAF (¥/kg)", fontsize=11, fontfamily="Times New Roman")
    cbar.ax.tick_params(labelsize=9)

    ax.set_xlabel(r"Electrolyzer CAPEX (k¥ per kg H$_2$/h)", fontsize=12,
                  fontfamily="Times New Roman")
    ax.set_ylabel("Grid Electricity Price (¥/kWh)", fontsize=12,
                  fontfamily="Times New Roman")
    ax.set_title(
        f"LCO-SynAF Heat Map: {scenario}\n"
        "(Note: LCO is insensitive to grid electricity price in this range;\n"
        " only electrolyzer CAPEX drives cost variation)",
        fontsize=10, fontfamily="Times New Roman"
    )

    _save_fig(fig, output_filename)
    logger.info(f"附录图已保存: {FIGURES_DIR / output_filename}")


def plot_dac_breakeven_appendix(
    vals: dict = None,
    output_filename: str = "fig_dac_breakeven_appendix.png",
):
    """
    附录图：DAC-GH-FT LCO 对 DAC 成本的敏感性
    注：市场窗口（8元/kg）在扫描范围内无法触达，图中标注差距。
    """
    if vals is None:
        from products.supply_chain_optimization.sensitivity_analysis.sensitivity_data_analyzer import get_all_appendix_values
        vals = get_all_appendix_values()

    dac_data = vals["_dac"]["per_scenario"]
    scenarios = ["DAC-GH-FT", "DAC-BH-FT", "DAC-GH-MTJ", "DAC-BH-MTJ"]
    colors_dac = {
        "DAC-GH-FT": "#9467bd",
        "DAC-BH-FT": "#f7b6d2",
        "DAC-GH-MTJ": "#c5b0d5",
        "DAC-BH-MTJ": "#e377c2",
    }
    markers_dac = {"DAC-GH-FT": "D", "DAC-BH-FT": "v",
                   "DAC-GH-MTJ": "s", "DAC-BH-MTJ": "o"}

    fig, ax = plt.subplots(figsize=(8, 5))

    # 市场窗口水平线
    ax.axhline(y=8.0, color="#6aa84f", linestyle="--", linewidth=1.5,
               label="Market window upper (8 ¥/kg)", alpha=0.9)

    for sc in scenarios:
        d = dac_data.get(sc)
        if not d:
            continue
        x = np.array(d["dac_values"])
        y = np.array(d["lco_values"])
        ax.plot(x, y, marker=markers_dac[sc], label=sc,
                color=colors_dac.get(sc, "gray"), linewidth=2, markersize=6)

    # IEA 2030 目标线
    ax.axvline(x=100, color="darkorange", linestyle=":", linewidth=1.2, alpha=0.8)
    ax.text(110, 15, "IEA 2030\ntarget\n~100 ¥/t",
            fontsize=8, color="darkorange", va="bottom",
            fontfamily="Times New Roman")

    # 基准线
    ax.axvline(x=4500, color="gray", linestyle=":", linewidth=1.0, alpha=0.6)
    ax.text(4520, 15, "Baseline\n4,500 ¥/t",
            fontsize=8, color="gray", va="bottom", fontfamily="Times New Roman")

    # 标注 DAC-GH-FT 的最小LCO与市场窗口差距
    min_lco = vals["dac_ghft_lco_min"]
    ax.annotate(
        f"Min LCO (DAC-GH-FT): {min_lco:.1f} ¥/kg\nGap from market: {min_lco - 8.0:.1f} ¥/kg",
        xy=(300, min_lco),
        xytext=(900, min_lco - 6),
        fontsize=8, color="#9467bd",
        fontfamily="Times New Roman",
        arrowprops=dict(arrowstyle="->", color="#9467bd", lw=0.8),
    )

    _apply_pub_style(ax,
                     r"DAC Capture Cost (¥/ton CO$_2$)",
                     "LCO-SynAF (¥/kg)",
                     r"DAC Cost Sensitivity: LCO-SynAF vs DAC Unit Cost")
    ax.legend(fontsize=9, framealpha=0.8, ncol=2)

    _save_fig(fig, output_filename)
    logger.info(f"附录图已保存: {FIGURES_DIR / output_filename}")


def plot_tornado_appendix(
    vals: dict = None,
    output_filename: str = "fig_pareto_tornado_appendix.png",
):
    """
    附录图：跨场景 LCO 敏感性范围图
    每条路径在其关键参数扫描下的 LCO 变动范围（lco_min → lco_max），
    按基准 LCO 从低到高排序，颜色按路径族区分，市场窗口标注为参考带。
    """
    if vals is None:
        from products.supply_chain_optimization.sensitivity_analysis.sensitivity_data_analyzer import get_all_appendix_values
        vals = get_all_appendix_values()

    rob = vals["_rob"]
    tornado_df = rob["tornado_df"]
    min_margin = vals["min_margin_gtlbh_vs_gtl"]

    # 主结果基准 LCO（精确值，已知场景）
    MAIN_LCOS = {"GTL": 6.502, "GTL-BH": 5.225}

    # 参数标签（斜体标注于 bar 左端）
    PARAM_LABELS = {
        "ng_price":              "NG price",
        "bh_capex":              "BH CAPEX",
        "coal_price":            "Coal price",
        "electricity_capex_grid":"Elec.×CAPEX",
        "dac_cost":              "DAC cost",
    }

    # 每个场景取 LCO range 最大的参数（主导驱动因素）
    idx_max = tornado_df.groupby("scenario")["lco_range"].idxmax()
    plot_df = tornado_df.loc[idx_max].copy().reset_index(drop=True)

    # 排序键：已知主结果 LCO 优先，其余按 lco_min
    def _sort_key(row):
        sc = row["scenario"]
        return MAIN_LCOS.get(sc, row["lco_min"])

    plot_df["_sk"] = plot_df.apply(_sort_key, axis=1)
    plot_df = plot_df.sort_values("_sk", ascending=False).reset_index(drop=True)  # 低成本在上

    scenarios  = plot_df["scenario"].values
    lco_mins   = plot_df["lco_min"].values
    lco_maxs   = plot_df["lco_max"].values
    lco_ranges = plot_df["lco_range"].values
    params     = [PARAM_LABELS.get(p, p) for p in plot_df["param"].values]
    colors     = [SCENARIO_COLORS.get(sc, "#aaaaaa") for sc in scenarios]

    n = len(scenarios)
    fig_h = max(4.5, 0.52 * n + 1.5)
    fig, ax = plt.subplots(figsize=(11, fig_h))

    # ── 市场窗口背景带 ──────────────────────────────────────────────────────
    ax.axvspan(6.0, 8.0, alpha=0.12, color="#2ca02c", zorder=0,
               label="Market window (6–8 ¥/kg)")
    ax.axvline(x=6.0, color="#2ca02c", linestyle="--", linewidth=0.9, alpha=0.75, zorder=1)
    ax.axvline(x=8.0, color="#2ca02c", linestyle="--", linewidth=0.9, alpha=0.75, zorder=1)

    # ── 范围条 ──────────────────────────────────────────────────────────────
    for i, (sc, lmin, lmax, lrange, color, param) in enumerate(
        zip(scenarios, lco_mins, lco_maxs, lco_ranges, colors, params)
    ):
        ax.barh(i, lrange, left=lmin, color=color, alpha=0.75,
                edgecolor="white", linewidth=0.6, height=0.62, zorder=2)

        # Δ 值标注（右端）
        ax.text(lmax + 0.3, i, f"Δ{lrange:.1f}",
                va="center", ha="left", fontsize=8,
                fontfamily="Times New Roman", color="dimgray")

        # 参数名标注（左端，斜体）
        ax.text(lmin - 0.3, i, param,
                va="center", ha="right", fontsize=7,
                fontfamily="Times New Roman", color="dimgray",
                style="italic")

        # 已知基准 LCO 菱形标记
        if sc in MAIN_LCOS:
            ax.scatter([MAIN_LCOS[sc]], [i], s=55, color="black",
                       marker="D", zorder=5, linewidths=0.0)

    # ── GTL-BH vs GTL 最小边距注释 ──────────────────────────────────────────
    if not np.isnan(min_margin):
        gtl_idx = list(scenarios).index("GTL") if "GTL" in scenarios else None
        if gtl_idx is not None:
            ax.annotate(
                f"Min GTL-BH/GTL gap\n{min_margin:.2f} ¥/kg",
                xy=(MAIN_LCOS["GTL"], gtl_idx),
                xytext=(MAIN_LCOS["GTL"] + 2.5, gtl_idx - 0.8),
                fontsize=7.5, fontfamily="Times New Roman", color="darkred",
                arrowprops=dict(arrowstyle="->", color="darkred", lw=0.7),
                va="center",
                bbox=dict(boxstyle="round,pad=0.2", fc="lightyellow", ec="darkred", lw=0.5),
            )

    # ── 坐标轴 & 样式 ────────────────────────────────────────────────────────
    ax.set_yticks(range(n))
    ax.set_yticklabels(scenarios, fontfamily="Times New Roman", fontsize=9.5)
    ax.set_ylim(-0.6, n - 0.4)

    x_right = max(lco_maxs) + 3.0
    ax.set_xlim(left=max(0.0, lco_mins.min() - 3.0), right=x_right)

    # 基准标记图例条目
    baseline_handle = plt.scatter([], [], s=55, color="black", marker="D")
    window_patch    = matplotlib.patches.Patch(fc="#2ca02c", alpha=0.25, label="Market window (6–8 ¥/kg)")
    ax.legend(
        handles=[window_patch, baseline_handle],
        labels=["Market window (6–8 ¥/kg)", "Baseline LCO (main result)"],
        fontsize=8, loc="lower right", framealpha=0.85,
    )

    _apply_pub_style(ax, "LCO-SynAF (¥/kg)", "",
                     "Scenario LCO sensitivity range (dominant-parameter sweep)")

    plt.tight_layout()
    _save_fig(fig, output_filename)
    logger.info(f"附录图已保存: {FIGURES_DIR / output_filename}")


def generate_appendix_figures(vals: dict = None) -> dict:
    """
    生成附录 Section 4 所需的全部5张发表级图表。
    返回各图表的 Path 对象字典。
    """
    if vals is None:
        from products.supply_chain_optimization.sensitivity_analysis.sensitivity_data_analyzer import get_all_appendix_values
        vals = get_all_appendix_values()

    logger.info("生成附录图1：NG价格敏感性...")
    plot_ng_price_sensitivity_appendix(vals)

    logger.info("生成附录图2：BH CAPEX敏感性（GTL-BH）...")
    plot_bh_capex_sensitivity_appendix(vals)

    logger.info("生成附录图3：CCU-GH-MTJ 电价×CAPEX热图...")
    plot_electricity_capex_heatmap_appendix(vals, scenario="CCU-GH-MTJ")

    logger.info("生成附录图4：DAC成本敏感性...")
    plot_dac_breakeven_appendix(vals)

    logger.info("生成附录图5：Tornado图...")
    plot_tornado_appendix(vals)

    paths = {
        "fossil_price": FIGURES_DIR / "fig_ng_price_sensitivity_appendix.png",
        "bh_capex": FIGURES_DIR / "fig_bh_capex_sensitivity_appendix.png",
        "green_h2_joint": FIGURES_DIR / "fig_electricity_capex_heatmap_appendix.png",
        "dac_breakeven": FIGURES_DIR / "fig_dac_breakeven_appendix.png",
        "pareto_tornado": FIGURES_DIR / "fig_pareto_tornado_appendix.png",
    }
    logger.info(f"全部5张附录图已保存到: {FIGURES_DIR}")
    return paths
