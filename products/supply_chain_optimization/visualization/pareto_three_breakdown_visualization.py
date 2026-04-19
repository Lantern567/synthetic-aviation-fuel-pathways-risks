# -*- coding: utf-8 -*-
"""
帕累托代表性场景分解可视化（堆叠面积图 + 两个 donut）
每个场景输出：
  pareto_NN_<name>_area.png       ← 堆叠面积图（2026→2036 学习曲线）
  pareto_NN_<name>_cost_donut.png
  pareto_NN_<name>_carbon_donut.png
"""

from __future__ import annotations

import glob
import json
import logging
import sys
from collections import OrderedDict as OD
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# ── 日志 ─────────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ── 路径 ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR   = Path(__file__).resolve().parent
REPO_ROOT    = SCRIPT_DIR.parent.parent.parent
OUTPUT_BASE  = SCRIPT_DIR / "results"

# ── 字体 ─────────────────────────────────────────────────────────────────────
FS_TITLE     = 20   # axes title / xlabel / ylabel
FS_TICK      = 18   # tick labels & y-category labels
FS_ANNOT     = 16   # bar value annotations
FS_DONUT_PCT = 40   # donut percentage labels
FS_DONUT_CTR = 44   # donut center text

matplotlib.rcParams.update({
    "font.family": "serif",
    "font.serif":  ["Times New Roman", "DejaVu Serif"],
    "axes.unicode_minus": False,
    "savefig.dpi": 300,
    "figure.facecolor": "none",
    "axes.facecolor": "none",
    "savefig.facecolor": "none",
    "text.color": "black",
    "axes.labelcolor": "black",
    "xtick.color": "black",
    "ytick.color": "black",
})

# ── 类别定义 ──────────────────────────────────────────────────────────────────
CATEGORIES = OD([
    ("Feedstock",   {"color": "#BDBDBD",   # Light Grey    — 原料
                     "carbon_keys": ["coal_mining", "ng_extraction"],
                     "cost_keys":   ["coal_purchase_cost", "natural_gas_cost"]}),
    ("Hydrogen",    {"color": "#42A5F5",   # Light Blue    — 制氢
                     "carbon_keys": ["h2_production", "electrolyzer_facility"],
                     "cost_keys":   ["hydrogen_production_cost", "electrolyzer_investment_cost"]}),
    ("CO2 Capture", {"color": "#90CAF9",   # Pale Blue     — 碳捕获
                     "carbon_keys": ["co2_capture_energy", "dac_equipment"],
                     "cost_keys":   ["co2_capture_cost", "dac_capture_cost", "dac_facility_investment"]}),
    ("Conversion",  {"color": "#64B5F6",   # Medium-Light Blue — 合成转化
                     "carbon_keys": ["coal_gasification_direct", "coal_co2_fugitive",
                                     "coal_gasification_energy", "ng_to_methanol",
                                     "methanol_to_saf", "saf_synthesis_energy", "ft_production"],
                     "cost_keys":   ["coal_gasification_cost", "production_cost",
                                     "methanol_production_cost", "ft_production_cost",
                                     "ft_reactor_operation_cost", "ft_energy_cost",
                                     "catalyst_cost", "ft_catalyst_cost"]}),
    ("Power",       {"color": "#BBDEFB",   # Very Pale Blue — 电力
                     "carbon_keys": ["dac_grid_electricity"],
                     "cost_keys":   ["electricity_cost", "dac_grid_electricity_cost"]}),
    ("Facility",    {"color": "#66BB6A",   # Medium Green  — 设施
                     "carbon_keys": ["saf_facility"],
                     "cost_keys":   ["facility_investment_cost", "facility_operation_cost",
                                     "ft_reactor_investment_cost"]}),
    ("Transport",   {"color": "#A5D6A7",   # Light Green   — 运输
                     "carbon_keys": ["coal_transport", "ng_transport", "h2_pipeline_transport",
                                     "h2_truck_transport", "h2_transport", "co2_pipeline_transport",
                                     "co2_truck_transport", "co2_transport", "mtj_transport", "saf_transport"],
                     "cost_keys":   ["transport_operation_cost", "hydrogen_transport_investment",
                                     "hydrogen_transport_operation", "hydrogen_pipeline_operation",
                                     "ng_transport_investment", "ng_transport_operation",
                                     "co2_pipeline_transport_cost", "co2_truck_transport_cost",
                                     "saf_transport_investment", "saf_transport_operation"]}),
    ("Storage",     {"color": "#C8E6C9",   # Very Light Green — 储存
                     "carbon_keys": ["h2_storage", "mtj_storage", "saf_storage"],
                     "cost_keys":   ["storage_equipment_cost", "storage_operation_cost",
                                     "h2_storage_investment", "h2_storage_operation",
                                     "methanol_storage_equipment_cost", "methanol_storage_investment",
                                     "methanol_storage_operation", "methanol_storage_operation_cost",
                                     "co2_storage_investment", "co2_storage_operation",
                                     "final_inventory_cost"]}),
])

SCENARIOS = OD([
    ("CTL",        {"solution_pattern": str(REPO_ROOT / "products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/complete_solution_*.json"),
                    "carbon_pattern":   str(REPO_ROOT / "products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/carbon_emissions_detailed_*.json")}),
    ("CTL-BH",     {"solution_pattern": str(REPO_ROOT / "products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/byproduct_hydrogen/complete_solution_*.json"),
                    "carbon_pattern":   str(REPO_ROOT / "products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/byproduct_hydrogen/carbon_emissions_detailed_*.json")}),
    ("CCU-BH-MTJ", {"solution_pattern": str(REPO_ROOT / "products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/two_step/complete_solution_*.json"),
                    "carbon_pattern":   str(REPO_ROOT / "products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/two_step/carbon_emissions_detailed_*.json")}),
    ("CCU-BH-FT",  {"solution_pattern": str(REPO_ROOT / "products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/one_step/complete_solution_*.json"),
                    "carbon_pattern":   str(REPO_ROOT / "products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/one_step/carbon_emissions_detailed_*.json")}),
    ("DAC-BH-MTJ", {"solution_pattern": str(REPO_ROOT / "products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/two_step/complete_solution_*.json"),
                    "carbon_pattern":   str(REPO_ROOT / "products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/two_step/carbon_emissions_detailed_*.json")}),
    ("DAC-BH-FT",  {"solution_pattern": str(REPO_ROOT / "products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/one_step/complete_solution_*.json"),
                    "carbon_pattern":   str(REPO_ROOT / "products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/one_step/carbon_emissions_detailed_*.json")}),
    ("GTL-BH",     {"solution_pattern": str(REPO_ROOT / "products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/byproduct_hydrogen/byproduct_hydrogen/two_step/complete_solution_*.json"),
                    "carbon_pattern":   str(REPO_ROOT / "products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/byproduct_hydrogen/byproduct_hydrogen/two_step/carbon_emissions_detailed_*.json")}),
    ("GTL-GH",     {"solution_pattern": str(REPO_ROOT / "products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/complete_solution_*.json"),
                    "carbon_pattern":   str(REPO_ROOT / "products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/carbon_emissions_detailed_*.json")}),
    ("GTL",        {"solution_pattern": str(REPO_ROOT / "products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/ft_one_step/complete_solution_*.json"),
                    "carbon_pattern":   str(REPO_ROOT / "products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/ft_one_step/carbon_emissions_detailed_*.json")}),
    ("DAC-GH-MTJ", {"solution_pattern": str(REPO_ROOT / "products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/two_step/complete_solution_*.json"),
                    "carbon_pattern":   str(REPO_ROOT / "products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/two_step/carbon_emissions_detailed_*.json")}),
    ("DAC-GH-FT",  {"solution_pattern": str(REPO_ROOT / "products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/one_step/complete_solution_*.json"),
                    "carbon_pattern":   str(REPO_ROOT / "products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/one_step/carbon_emissions_detailed_*.json")}),
    ("CCU-GH-MTJ", {"solution_pattern": str(REPO_ROOT / "products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/two_step/complete_solution_*.json"),
                    "carbon_pattern":   str(REPO_ROOT / "products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/two_step/carbon_emissions_detailed_*.json")}),
    ("CCU-GH-FT",  {"solution_pattern": str(REPO_ROOT / "products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/one_step/complete_solution_*.json"),
                    "carbon_pattern":   str(REPO_ROOT / "products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/one_step/carbon_emissions_detailed_*.json")}),
])


def _safe_float(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _find_latest(pattern: str) -> Path | None:
    files = sorted(glob.glob(pattern), reverse=True)
    return Path(files[0]) if files else None


def _aggregate(source: dict, key_field: str) -> dict[str, float]:
    """Return {category_name: value} using CATEGORIES key lists."""
    result = {}
    for cat_name, cfg in CATEGORIES.items():
        val = sum(_safe_float(source.get(k, 0)) for k in cfg[key_field])
        result[cat_name] = max(val, 0.0)
    return result


SAF_LHV_MJ_PER_KG = 43.2   # SAF 低位热值，用于 kg CO2e → g CO2e/MJ 换算

# ── Wright's Law 学习曲线 ──────────────────────────────────────────────────────

PROJ_YEARS = np.arange(2026, 2037)   # 11 步

_X_pem  = np.interp(PROJ_YEARS, [2025,2027,2030,2033,2036], [60,  100, 330, 600, 950])
_X_dac  = np.interp(PROJ_YEARS, [2025,2028,2031,2034,2036], [0.1, 1.0, 4.0, 8.0, 12.0])
_X_coal = np.interp(PROJ_YEARS, [2025,2028,2031,2034,2036], [10,  60,  180, 350, 500])
_X_gas  = np.interp(PROJ_YEARS, [2025,2028,2031,2034,2036], [20,  90,  250, 430, 600])

LR = {'electrolyzer':0.18,'synthesis_mtj':0.10,'synthesis_ft':0.12,
      'capture_dac':0.15,'capture_coal':0.08,'capture_ref':0.08,'electricity':0.05}

def _cf(X, lr):
    b = -np.log2(1 - lr)
    return (X / X[0]) ** (-b)

CF = {
    'electrolyzer':  _cf(_X_pem,  LR['electrolyzer']),
    'synthesis_mtj': _cf(_X_gas,  LR['synthesis_mtj']),
    'synthesis_ft':  _cf(_X_gas,  LR['synthesis_ft']),
    'capture_dac':   _cf(_X_dac,  LR['capture_dac']),
    'capture_coal':  _cf(_X_coal, LR['capture_coal']),
    'capture_ref':   _cf(_X_gas,  LR['capture_ref']),
    'electricity':   (1 - LR['electricity']) ** np.arange(len(PROJ_YEARS)),
    'fixed':         np.ones(len(PROJ_YEARS)),
}

# 每个成本 key → 对应哪条学习曲线
_KEY2CF = {
    'electrolyzer_investment_cost': 'electrolyzer',
    'hydrogen_production_cost':     'electrolyzer',
    'methanol_production_cost':     'synthesis_mtj',
    'production_cost':              'synthesis_mtj',
    'ft_production_cost':           'synthesis_ft',
    'ft_reactor_operation_cost':    'synthesis_ft',
    'ft_energy_cost':               'synthesis_ft',
    'catalyst_cost':                'synthesis_ft',
    'ft_catalyst_cost':             'synthesis_ft',
    'ft_reactor_investment_cost':   'synthesis_ft',
    'coal_gasification_cost':       'capture_coal',
    'dac_capture_cost':             'capture_dac',
    'dac_facility_investment':      'capture_dac',
    'co2_capture_cost':             'capture_ref',
    'electricity_cost':             'electricity',
    'dac_grid_electricity_cost':    'electricity',
}

FT_SCENARIOS = {'CTL','DAC-GH-FT','CCU-GH-FT','GTL','DAC-BH-FT','CCU-BH-FT','GTL-BH','GTL-GH'}

_EXCL = {'shortage_penalty_cost', 'total_cost', 'total_cost_excluding_shortage'}


def compute_category_trajectories(
    cost_breakdown: dict, lcoe_base: float, name_en: str
) -> dict[str, np.ndarray]:
    """
    返回 {category_name: shape-(11,) LCOE 贡献数组 (CNY/kg)}，
    各类别之和 = 逐年总 LCOE。
    """
    cb = {k: _safe_float(v) for k, v in cost_breakdown.items()
          if k not in _EXCL and _safe_float(v) > 0}
    total_mapped = sum(cb.values())
    if total_mapped == 0 or lcoe_base == 0:
        # 退化：所有类别固定不变
        n_cats = len(CATEGORIES)
        share = lcoe_base / n_cats if n_cats else 0
        return {c: np.full(len(PROJ_YEARS), share) for c in CATEGORIES}

    # 选 FT 还是 MTJ 合成路线
    syn_cf_key = 'synthesis_ft' if name_en in FT_SCENARIOS else 'synthesis_mtj'

    result = {c: np.zeros(len(PROJ_YEARS)) for c in CATEGORIES}

    for cost_key, base_val in cb.items():
        frac = base_val / total_mapped
        cf_key = _KEY2CF.get(cost_key, 'fixed')
        # synthesis_mtj / synthesis_ft 都统一用场景对应的 syn_cf_key
        if cf_key in ('synthesis_mtj', 'synthesis_ft'):
            cf_key = syn_cf_key

        trajectory = CF[cf_key] * frac * lcoe_base

        # 找到这个 cost_key 属于哪个 CATEGORY
        cat_match = None
        for cat_name, cfg in CATEGORIES.items():
            if cost_key in cfg['cost_keys']:
                cat_match = cat_name
                break
        if cat_match is None:
            cat_match = 'Facility'   # fallback

        result[cat_match] += trajectory

    return result


def load_data() -> dict[str, dict]:
    data = {}
    for label, cfg in SCENARIOS.items():
        sol_path = _find_latest(cfg["solution_pattern"])
        car_path = _find_latest(cfg["carbon_pattern"])
        if sol_path is None or car_path is None:
            logger.warning("跳过 %s，缺少结果文件", label)
            continue
        with sol_path.open() as f:
            sol = json.load(f)
        with car_path.open() as f:
            car = json.load(f)

        cost_breakdown = sol.get("cost_breakdown", {})
        detailed_emissions = car.get("detailed", {})

        trad_ci = _safe_float(car.get("traditional_jet_ci_gco2e_per_mj", 89))
        carbon_diff = car.get("abs_diff_vs_traditional_jet_gco2e_per_mj")
        if carbon_diff is None:
            if "carbon_intensity_mj" in car:
                carbon_diff = _safe_float(car["carbon_intensity_mj"]) - trad_ci
            else:
                carbon_diff = trad_ci * _safe_float(car.get("vs_traditional_jet", 0)) / 100.0
        else:
            carbon_diff = _safe_float(carbon_diff)

        data[label] = {
            "lcoe":               _safe_float(sol.get("lifecycle_levelized_cost_excluding_shortage_per_kg")),
            "carbon_diff":        carbon_diff,
            "cost_breakdown":     cost_breakdown,
            "detailed_emissions": detailed_emissions,
            "total_production_kg": _safe_float(car.get("total_production_kg", 1)),
        }
        logger.info("%s | cost=%.3f 元/kg | carbon diff=%.3f g CO2e/MJ",
                    label, data[label]["lcoe"], data[label]["carbon_diff"])

    logger.info("成功加载 %d 个场景", len(data))
    return data


def identify_pareto(data: dict[str, dict]) -> list[str]:
    items = sorted(data.items(), key=lambda x: (x[1]["carbon_diff"], x[1]["lcoe"]))
    pareto, best = [], float("inf")
    for label, rec in items:
        if rec["lcoe"] < best - 1e-9:
            pareto.append(label)
            best = rec["lcoe"]
    return pareto


def select_three(pareto: list[str], data: dict[str, dict]) -> list[str]:
    ordered = sorted(pareto, key=lambda l: data[l]["carbon_diff"])
    if len(ordered) <= 3:
        return ordered
    mid = len(ordered) // 2
    seen, result = set(), []
    for l in [ordered[0], ordered[mid], ordered[-1]]:
        if l not in seen:
            result.append(l)
            seen.add(l)
    return result


# ── 绘图函数 ──────────────────────────────────────────────────────────────────

def draw_concentric_rings(
    label: str,
    cost_breakdown: dict,
    carbon_vals: dict,
    lcoe_base: float,
    out_path: Path,
    total_production_kg: float = 1.0,
) -> None:
    """
    极坐标堆叠柱状图（完全仿 polar_carbon_stacked_bar 参考图风格）：
    - 内部：11 根成本堆叠柱（2026–2036），从固定内径出发，绝对 LCOE 值
    - 最外圈：碳排放分类弧形环（全 360°，按碳排比例分段）
    - 中心文字：工艺路线名称
    - 右侧图例
    - 辐射网格线 + 刻度数值
    """
    cat_traj    = compute_category_trajectories(cost_breakdown, lcoe_base, label)
    active_cats = [c for c in CATEGORIES if max(cat_traj[c]) > 0.01]
    n           = len(PROJ_YEARS)   # 11

    total_lcoe = np.array([
        sum(cat_traj[c][i] for c in active_cats) for i in range(n)
    ])
    r_max        = total_lcoe.max()
    INNER_RADIUS = r_max * 0.35

    # ── 极坐标图 ──────────────────────────────────────────────────────────
    fig = plt.figure(figsize=(16, 14), facecolor='none')
    ax  = fig.add_subplot(111, projection='polar')
    ax.set_facecolor('none')
    ax.set_theta_zero_location('N')
    ax.set_theta_direction(-1)

    bar_width = 2 * np.pi / n * 0.78
    angles    = np.linspace(0, 2 * np.pi, n, endpoint=False)

    # ── 成本堆叠柱 ────────────────────────────────────────────────────────
    bottoms = np.full(n, INNER_RADIUS)
    for cat in active_cats:
        heights = np.array([cat_traj[cat][i] for i in range(n)])
        ax.bar(
            angles, heights,
            width=bar_width, bottom=bottoms,
            color=CATEGORIES[cat]['color'], label=cat,
            alpha=0.90, edgecolor='white', linewidth=0.4,
        )
        bottoms += heights

    # ── 最外圈：碳排放弧形环 ──────────────────────────────────────────────
    bar_max    = bottoms.max()
    RING_GAP   = r_max * 0.12
    RING_WIDTH = r_max * 0.32
    ring_start = bar_max + RING_GAP

    carbon_active = [c for c in CATEGORIES if carbon_vals.get(c, 0) > 0]
    carbon_arr    = np.array([carbon_vals[c] for c in carbon_active], dtype=float)
    carbon_total  = carbon_arr.sum()
    carbon_fracs  = carbon_arr / carbon_total

    start_ang = 0.0
    for cat, frac, carbon_val in zip(carbon_active, carbon_fracs, carbon_arr):
        span = frac * 2 * np.pi
        if span < 0.01:
            start_ang += span
            continue
        center = start_ang + span / 2
        ax.bar(
            center, RING_WIDTH,
            width=span, bottom=ring_start,
            color=CATEGORIES[cat]['color'], alpha=0.88,
            edgecolor='white', linewidth=0.8,
        )
        # 旋转公式（CW-from-N 坐标系）
        deg = np.degrees(center) % 360
        rot = -deg + (180 if 90 < deg < 270 else 0)
        # 换算为 g CO2e/MJ
        carbon_gco2e = carbon_val / max(total_production_kg, 1) * 1000 / SAF_LHV_MJ_PER_KG
        val_str = f"{carbon_gco2e:.1f}"

        if frac > 0.04:
            # 只写数值，随弧度旋转
            ax.text(
                center, ring_start + RING_WIDTH / 2, val_str,
                ha='center', va='center',
                fontsize=(FS_ANNOT - 3) * 2, fontweight='bold', color='black',
                rotation=rot, rotation_mode='anchor',
            )
        start_ang += span

    # ── 年份标注：紧贴每根柱顶（各年独立定位，不随外圈移动）──────────────
    for i, (ang, yr) in enumerate(zip(angles, PROJ_YEARS)):
        bar_top = bottoms[i]          # 该年份柱子实际顶部
        year_r  = bar_top + r_max * 0.04
        deg = np.degrees(ang) % 360
        rot = -deg + (180 if 90 < deg < 270 else 0)
        ax.text(
            ang, year_r, str(yr),
            ha='center', va='center',
            fontsize=(FS_TICK - 2) * 2, fontweight='bold', color='#333333',
            rotation=rot, rotation_mode='anchor',
        )

    # ── 辐射网格线 + 刻度数值 ─────────────────────────────────────────────
    for step in [1, 2, 5, 10, 15, 20, 50]:
        if r_max / step <= 8:
            tick_step = step
            break
    else:
        tick_step = 50

    ticks_real   = np.arange(0, r_max + tick_step, tick_step)
    ticks_radius = ticks_real + INNER_RADIUS
    ax.set_yticks(ticks_radius)
    ax.set_yticklabels([])
    ax.yaxis.grid(True, linestyle='--', alpha=0.65, color='#888888',
                  linewidth=1.1, dashes=(4, 4))
    ax.xaxis.grid(False)
    ax.spines['polar'].set_visible(False)
    ax.set_xticks([])
    ax.set_rmin(0)
    ax.set_rmax(ring_start + RING_WIDTH * 1.08)

    # 刻度数值标在 2036→2026 间的空隙处
    tick_angle = (angles[-1] + 2 * np.pi) / 2
    for val, radius in zip(ticks_real[1:], ticks_radius[1:]):
        if val > r_max * 1.02:
            continue
        ax.text(
            tick_angle, radius, f"{val:.0f}",
            ha='center', va='center',
            fontsize=(FS_ANNOT - 3) * 2, color='#666666', fontweight='bold',
            bbox=dict(facecolor='white', edgecolor='none', alpha=0.7, pad=0.5),
        )

    # ── 中心：工艺名称 ────────────────────────────────────────────────────
    ax.text(
        0, 0, label,
        ha='center', va='center',
        fontsize=FS_TITLE + 4, fontweight='bold', color='#333333', zorder=10,
    )

    # ── 副标题文字（路径名下方两行，South 方向）─────────────────────────
    ax.text(
        np.pi, INNER_RADIUS * 0.30,
        "Cost (CNY/kg)",
        ha='center', va='center',
        fontsize=FS_ANNOT - 2, color='#666666', zorder=10,
    )
    ax.text(
        np.pi, INNER_RADIUS * 0.62,
        "Carbon (g CO2e/MJ)",
        ha='center', va='center',
        fontsize=FS_ANNOT - 2, color='#888888', zorder=10,
    )

    # ── 图例（右侧，仿参考图样式）────────────────────────────────────────
    patches = [
        mpatches.Patch(facecolor=CATEGORIES[c]['color'], alpha=0.90, label=c)
        for c in active_cats
    ]
    leg = ax.legend(
        handles=patches,
        fontsize=FS_ANNOT,
        loc='upper left',
        bbox_to_anchor=(1.08, 1.02),
        frameon=False,
        labelspacing=0.8,
        title='Cost / Carbon\nCategories',
        title_fontsize=FS_ANNOT + 2,
    )
    leg.get_title().set_fontweight('bold')

    fig.savefig(out_path, dpi=300, bbox_inches='tight',
                facecolor='none', transparent=True)
    plt.close(fig)
    logger.info("已保存极坐标堆叠图: %s", out_path)


def draw_donut(vals: dict, center_label: str, out_path: Path) -> None:
    cats   = [c for c in CATEGORIES if vals.get(c, 0) > 0]
    sizes  = [vals[c] for c in cats]
    colors = [CATEGORIES[c]["color"] for c in cats]
    total  = sum(sizes)
    pcts   = [v / total * 100 for v in sizes]

    fig, ax = plt.subplots(figsize=(7, 7))
    wedges, _ = ax.pie(
        sizes, colors=colors,
        wedgeprops=dict(width=0.52, edgecolor="white", linewidth=1.5),
        startangle=90,
    )

    # 只标注 ≥ 5% 的扇区
    for wedge, pct in zip(wedges, pcts):
        if pct < 5:
            continue
        angle = (wedge.theta1 + wedge.theta2) / 2
        r = 0.78
        x = r * np.cos(np.radians(angle))
        y_pos = r * np.sin(np.radians(angle))
        ax.text(x, y_pos, f"{pct:.0f}%",
                ha="center", va="center",
                fontsize=FS_DONUT_PCT, fontweight="bold", color="black")

    ax.text(0, 0, center_label, ha="center", va="center",
            fontsize=FS_DONUT_CTR, fontweight="bold", color="black",
            multialignment="center")

    ax.set_aspect("equal")
    plt.tight_layout()
    fig.savefig(out_path, dpi=300, bbox_inches="tight", facecolor="none", transparent=True)
    plt.close(fig)
    logger.info("已保存环形图: %s", out_path)


# ── 主流程 ────────────────────────────────────────────────────────────────────

def main() -> None:
    timestamp  = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = OUTPUT_BASE / f"pareto_breakdown_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    data   = load_data()
    pareto = identify_pareto(data)
    three  = select_three(pareto, data)

    logger.info("帕累托前沿场景: %s", ", ".join(pareto))
    logger.info("用于绘图的 3 个场景: %s", ", ".join(three))

    MARKET_LOW  = 6.0
    MARKET_HIGH = 8.0

    for rank, label in enumerate(three, start=1):
        rec    = data[label]
        slug   = label.lower().replace(" ", "-")
        prefix = output_dir / f"pareto_{rank:02d}_{slug}"

        cost_vals   = _aggregate(rec["cost_breakdown"],     "cost_keys")
        carbon_vals = _aggregate(rec["detailed_emissions"], "carbon_keys")

        draw_concentric_rings(
            label, rec["cost_breakdown"], carbon_vals, rec["lcoe"],
            Path(str(prefix) + "_area.png"),
            total_production_kg=rec.get("total_production_kg", 1.0),
        )
        draw_donut(cost_vals,   "Cost\nShare",   Path(str(prefix) + "_cost_donut.png"))
        draw_donut(carbon_vals, "Carbon\nShare", Path(str(prefix) + "_carbon_donut.png"))

    logger.info("全部完成，共生成 %d 张图", len(three) * 3)


def _stitch_composite(area_png: Path, cost_png: Path, carbon_png: Path, out_png: Path) -> None:
    """
    使用 PIL 将三张图拼合为一张合成图：
    左侧 60%：极坐标面积图；右上 40%：成本 donut；右下 40%：碳排 donut。
    同时生成 PDF（PIL raster）和 SVG（embedded base64）副本以满足 QA 导出检查。
    """
    import base64
    from PIL import Image

    area   = Image.open(area_png).convert("RGBA")
    cost   = Image.open(cost_png).convert("RGBA")
    carbon = Image.open(carbon_png).convert("RGBA")

    # 目标：area 高度为合成图高度，右侧 donuts 各占右半高度一半
    target_h  = area.height
    right_w   = int(area.width * 0.56)   # 右栏宽 ≈ 左栏宽 × 0.56
    total_w   = area.width + right_w

    donut_h = target_h // 2
    cost_r   = cost.resize((right_w, donut_h),   Image.LANCZOS)
    carbon_r = carbon.resize((right_w, donut_h), Image.LANCZOS)

    composite_rgba = Image.new("RGBA", (total_w, target_h), (255, 255, 255, 255))
    composite_rgba.paste(area,    (0,            0))
    composite_rgba.paste(cost_r,  (area.width,   0))
    composite_rgba.paste(carbon_r,(area.width,   donut_h))

    # PNG（RGB，避免透明度与 docx 不兼容）
    composite_rgb = composite_rgba.convert("RGB")
    composite_rgb.save(out_png, dpi=(300, 300))

    # PDF（PIL raster 嵌入）
    out_pdf = out_png.with_suffix(".pdf")
    composite_rgb.save(out_pdf, "PDF", resolution=300)

    # SVG（base64 raster 嵌入）
    with open(out_png, "rb") as _f:
        _b64 = base64.b64encode(_f.read()).decode()
    w_px, h_px = composite_rgb.size
    _dpi = 300
    w_mm = w_px / _dpi * 25.4
    h_mm = h_px / _dpi * 25.4
    svg_content = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{w_mm:.2f}mm" height="{h_mm:.2f}mm" '
        f'viewBox="0 0 {w_px} {h_px}">\n'
        f'  <image width="{w_px}" height="{h_px}" '
        f'xlink:href="data:image/png;base64,{_b64}"/>\n'
        '</svg>\n'
    )
    out_svg = out_png.with_suffix(".svg")
    out_svg.write_text(svg_content, encoding="utf-8")

    logger.info("已拼合合成图: %s (+ .pdf + .svg)", out_png)


# 场景显示顺序（附录用）
APPENDIX_SCENARIO_ORDER = [
    "CTL", "CTL-BH",
    "GTL-GH", "GTL", "GTL-BH",
    "CCU-GH-MTJ", "CCU-GH-FT",
    "CCU-BH-MTJ", "CCU-BH-FT",
    "DAC-GH-MTJ", "DAC-GH-FT",
    "DAC-BH-MTJ", "DAC-BH-FT",
]

APPENDIX_SCENARIO_GROUPS = {
    "Coal-based pathways":          ["CTL", "CTL-BH"],
    "Natural-gas-based pathways":   ["GTL-GH", "GTL", "GTL-BH"],
    "CCU Green-H₂ pathways":        ["CCU-GH-MTJ", "CCU-GH-FT"],
    "CCU By-product-H₂ pathways":   ["CCU-BH-MTJ", "CCU-BH-FT"],
    "DAC Green-H₂ pathways":        ["DAC-GH-MTJ", "DAC-GH-FT"],
    "DAC By-product-H₂ pathways":   ["DAC-BH-MTJ", "DAC-BH-FT"],
}


def generate_all_scenario_composites(
    output_dir: Path | None = None,
    prepared_dir: Path | None = None,
) -> dict[str, Path]:
    """
    为所有可用场景生成三合一合成图（极坐标面积 + 成本 donut + 碳排 donut）。

    返回值：{scenario_name: composite_png_path}
    """
    import tempfile

    timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    if output_dir is None:
        output_dir = OUTPUT_BASE / f"all_scenarios_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    if prepared_dir is None:
        prepared_dir = output_dir
    prepared_dir.mkdir(parents=True, exist_ok=True)

    data = load_data()
    if not data:
        raise RuntimeError("未能加载任何场景数据，请检查结果文件路径")

    results: dict[str, Path] = {}

    for rank, label in enumerate(APPENDIX_SCENARIO_ORDER, start=1):
        if label not in data:
            logger.warning("场景 %s 数据不存在，跳过", label)
            continue

        rec   = data[label]
        slug  = label.lower().replace(" ", "-")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            area_png   = tmp_path / f"{slug}_area.png"
            cost_png   = tmp_path / f"{slug}_cost.png"
            carbon_png = tmp_path / f"{slug}_carbon.png"

            cost_vals   = _aggregate(rec["cost_breakdown"],     "cost_keys")
            carbon_vals = _aggregate(rec["detailed_emissions"], "carbon_keys")

            draw_concentric_rings(
                label, rec["cost_breakdown"], carbon_vals, rec["lcoe"],
                area_png,
                total_production_kg=rec.get("total_production_kg", 1.0),
            )
            draw_donut(cost_vals,   "Cost\nShare",   cost_png)
            draw_donut(carbon_vals, "Carbon\nShare", carbon_png)

            composite_dst = prepared_dir / f"scenario_{rank:02d}_{slug}_composite.png"
            _stitch_composite(area_png, cost_png, carbon_png, composite_dst)

        results[label] = composite_dst
        logger.info("[%d/%d] %s → %s", rank, len(APPENDIX_SCENARIO_ORDER), label, composite_dst.name)

    logger.info("全场景合成图生成完毕，共 %d 张", len(results))
    return results


if __name__ == "__main__":
    main()
