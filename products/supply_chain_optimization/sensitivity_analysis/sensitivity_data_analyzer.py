"""
敏感性分析数据分析模块
从215个批量运行结果中计算附录所需的全部派生量。
"""
import sys
import logging
from pathlib import Path
from typing import Dict, Any

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger(__name__)

# 市场窗口
MARKET_WINDOW_UPPER = 8.0   # 元/kg
MARKET_WINDOW_LOWER = 6.0   # 元/kg

# NG 价格：config 默认值仅作参考；主优化使用管道 GIS 实际价格（~2.53 元/m³ 均值）
# 有效基准通过从敏感性曲线反推"与主结果 LCO 匹配的 NG 价格"得到，不使用 config 默认值
NG_CONFIG_DEFAULT = 4.2      # 元/m³（仅供参考，主模型未用此值）

BH_CAPEX_STEEL_BASELINE = 280_000   # 元/(kg/h)
BH_CAPEX_REFINERY_BASELINE = 224_000
DAC_BASELINE = 4500          # 元/t CO₂（与 config capture_cost_yuan_per_ton 一致 ✓）
IEA_DAC_TARGET = 100         # 元/t CO₂（IEA 2030目标）

# 主结果基准 LCO（来自 pareto_breakdown_20260319_225126）
# GTL: ft_one_step/complete_solution_20260201_215354.json
# GTL-BH: byproduct_hydrogen/two_step/complete_solution_20260201_220501.json
MAIN_RESULT_LCO: Dict[str, float] = {
    "GTL":    6.502,
    "GTL-BH": 5.225,
}


def _load_df() -> pd.DataFrame:
    from products.supply_chain_optimization.sensitivity_analysis.result_collector import collect_all_results
    df = collect_all_results()
    df["lco"] = pd.to_numeric(df["lco_excluding_shortage_per_kg"], errors="coerce")
    df["pv"] = pd.to_numeric(df["param_value"], errors="coerce")
    return df


def _interpolate_threshold(x: np.ndarray, y: np.ndarray, target: float) -> float:
    """在折线上线性插值，找到 y=target 对应的 x 值。若超出范围返回 NaN。"""
    for i in range(len(y) - 1):
        y0, y1 = y[i], y[i + 1]
        if (y0 - target) * (y1 - target) <= 0:
            # 跨越目标值
            t = (target - y0) / (y1 - y0)
            return float(x[i] + t * (x[i + 1] - x[i]))
    return float("nan")


# ─────────────────────────────────────────────────────────────────────────────
# NG 价格分析
# ─────────────────────────────────────────────────────────────────────────────

def compute_ng_price_metrics(df: pd.DataFrame = None) -> Dict[str, Any]:
    """
    计算天然气价格敏感性相关派生量。

    主模型使用 GIS 管道数据的地理位置实际价格（非 config 默认值 4.2 元/m³）。
    通过将主结果 LCO 代入敏感性曲线反插，得到每个场景的"有效基准 NG 价格"。

    Returns:
        gtl_threshold_yuan_m3: GTL LCO=8 元/kg 时的NG价格（市场窗口上限对应的阈值）
        gtl_effective_baseline_ng: GTL 主结果对应的有效 NG 基准价格
        gtl_pct_from_baseline: 阈值相对有效基准的变化比例（正数=涨价仍在窗口内）
        gtlbh_upper_threshold: GTL-BH LCO=8 元/kg 时的NG价格上界
        gtl_lco_at_baseline: GTL 主结果基准 LCO
        gtlbh_lco_at_baseline: GTL-BH 主结果基准 LCO
        gtlbh_competitive_at_baseline: GTL-BH 在有效基准下是否低于市场窗口上限
    """
    if df is None:
        df = _load_df()

    ng = df[df["param_name"] == "ng_price"].copy()

    result = {}
    for sc in ["GTL", "GTL-GH", "GTL-BH"]:
        sub = ng[ng["scenario_name"] == sc][["pv", "lco"]].dropna().sort_values("pv")
        if sub.empty:
            continue
        x = sub["pv"].values
        y = sub["lco"].values

        threshold = _interpolate_threshold(x, y, MARKET_WINDOW_UPPER)

        # 有效基准：从主结果 LCO 反插得到与主优化对应的 NG 价格
        # 若无主结果则退回到 config 默认值
        main_lco = MAIN_RESULT_LCO.get(sc)
        if main_lco is not None:
            effective_ng = _interpolate_threshold(x, y, main_lco)
            lco_at_baseline = main_lco
        else:
            effective_ng = float(NG_CONFIG_DEFAULT)
            idx_base = np.argmin(np.abs(x - NG_CONFIG_DEFAULT))
            lco_at_baseline = float(y[idx_base])

        result[sc] = {
            "threshold_yuan_m3": threshold,
            "effective_ng_baseline": effective_ng,
            "lco_at_baseline": lco_at_baseline,
            "lco_min": float(y.min()),
            "lco_max": float(y.max()),
            "ng_values": x.tolist(),
            "lco_values": y.tolist(),
        }

    gtl_threshold   = result.get("GTL", {}).get("threshold_yuan_m3", float("nan"))
    gtl_eff_ng      = result.get("GTL", {}).get("effective_ng_baseline", float("nan"))
    gtl_lco_base    = result.get("GTL", {}).get("lco_at_baseline", float("nan"))
    gtlbh_lco_base  = result.get("GTL-BH", {}).get("lco_at_baseline", float("nan"))
    gtlbh_eff_ng    = result.get("GTL-BH", {}).get("effective_ng_baseline", float("nan"))
    gtlbh_threshold = result.get("GTL-BH", {}).get("threshold_yuan_m3", float("nan"))

    # 正值 = 价格可以上涨多少才会碰到阈值（对 GTL 而言约 +31%）
    pct_from_baseline = (gtl_threshold - gtl_eff_ng) / gtl_eff_ng * 100 if not np.isnan(gtl_eff_ng) else float("nan")

    return {
        "per_scenario": result,
        "gtl_threshold_yuan_m3": round(gtl_threshold, 2),
        "gtl_effective_baseline_ng": round(gtl_eff_ng, 2),
        "gtl_pct_from_baseline": round(pct_from_baseline, 1),   # 正数 = 涨价仍在窗口内
        "gtlbh_upper_threshold_yuan_m3": round(gtlbh_threshold, 2),
        "gtlbh_effective_baseline_ng": round(gtlbh_eff_ng, 2),
        "gtl_lco_at_baseline": round(gtl_lco_base, 3),
        "gtlbh_lco_at_baseline": round(gtlbh_lco_base, 3),
        "gtlbh_competitive_at_baseline": bool(gtlbh_lco_base < MARKET_WINDOW_UPPER),
    }


# ─────────────────────────────────────────────────────────────────────────────
# BH CAPEX 分析
# ─────────────────────────────────────────────────────────────────────────────

def compute_bh_capex_metrics(df: pd.DataFrame = None) -> Dict[str, Any]:
    """
    计算副产氢 CAPEX 敏感性相关派生量（GTL-BH为主）。
    Returns:
        gtlbh_slope_per_100k: GTL-BH LCO 对 CAPEX 的斜率（元/kg per 10万元/(kg/h)）
        gtlbh_lco_min/max: 扫描范围内 LCO 最小/最大值
        gtlbh_advantage_at_upper_capex: CAPEX上限时GTL-BH对GTL的成本优势
        crossover_occurs: 是否发生交叉（GTL-BH > GTL）
    """
    if df is None:
        df = _load_df()

    bh = df[df["param_name"] == "bh_capex"].copy()

    # GTL 基准 LCO：直接使用主结果值（主模型用 GIS 管道价格，与 config 默认值不同）
    gtl_baseline_lco = MAIN_RESULT_LCO.get("GTL", float("nan"))

    result = {}
    for sc in ["GTL-BH", "CTL-BH", "CCU-BH-MTJ", "CCU-BH-FT", "DAC-BH-MTJ", "DAC-BH-FT"]:
        sub = bh[bh["scenario_name"] == sc][["pv", "lco"]].dropna().sort_values("pv")
        if sub.empty:
            continue
        x = sub["pv"].values
        y = sub["lco"].values
        # 线性回归斜率
        if len(x) >= 2 and x.max() > x.min():
            slope = float(np.polyfit(x, y, 1)[0]) * 100_000  # per 100k
        else:
            slope = 0.0
        result[sc] = {
            "slope_per_100k": round(slope, 4),
            "lco_min": round(float(y.min()), 3),
            "lco_max": round(float(y.max()), 3),
            "capex_values": x.tolist(),
            "lco_values": y.tolist(),
        }

    gtlbh = result.get("GTL-BH", {})
    slope = gtlbh.get("slope_per_100k", 0.0)
    lco_max = gtlbh.get("lco_max", float("nan"))
    advantage = gtl_baseline_lco - lco_max if not np.isnan(gtl_baseline_lco) else float("nan")
    crossover = bool(lco_max >= gtl_baseline_lco) if not np.isnan(gtl_baseline_lco) else False

    return {
        "per_scenario": result,
        "gtlbh_slope_per_100k": round(abs(slope), 4),
        "gtlbh_lco_min": gtlbh.get("lco_min", float("nan")),
        "gtlbh_lco_max": lco_max,
        "gtl_baseline_lco": round(gtl_baseline_lco, 2),
        "gtlbh_advantage_at_upper_capex": round(advantage, 2),
        "crossover_occurs": crossover,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 电价 × CAPEX 二维分析
# ─────────────────────────────────────────────────────────────────────────────

def compute_electricity_capex_metrics(df: pd.DataFrame = None) -> Dict[str, Any]:
    """
    计算电价×电解槽CAPEX二维敏感性相关派生量。
    主要使用 CCU-GH-MTJ（CCU-GH-FT 全部为零，不使用）。
    """
    if df is None:
        df = _load_df()

    ec = df[df["param_name"] == "electricity_capex_grid"].copy()
    ec["ep"] = pd.to_numeric(ec["electricity_price"], errors="coerce")
    ec["capex"] = pd.to_numeric(ec["electrolyzer_capex"], errors="coerce")

    result = {}
    for sc in ["CCU-GH-MTJ", "DAC-GH-MTJ", "DAC-GH-FT"]:
        sub = ec[ec["scenario_name"] == sc].dropna(subset=["lco", "ep", "capex"])
        sub = sub[sub["lco"] > 0]
        if sub.empty:
            continue

        pivot = sub.pivot_table(index="ep", columns="capex", values="lco", aggfunc="mean")

        # 检查电价是否有影响：计算同一CAPEX下不同电价的LCO方差（axis=0 = 跨行/跨电价）
        elec_price_variance = float(pivot.var(axis=0).mean())
        elec_insensitive = elec_price_variance < 0.01

        # CAPEX 斜率（线性回归，对每个电价取均值列）
        capex_vals = np.array(sorted(pivot.columns.astype(float)))
        lco_mean_per_capex = np.array([pivot[c].mean() for c in capex_vals])
        slope_per_100k = float(np.polyfit(capex_vals, lco_mean_per_capex, 1)[0]) * 100_000

        lco_min = float(sub["lco"].min())
        lco_max = float(sub["lco"].max())
        gap_from_window = lco_min - MARKET_WINDOW_UPPER

        result[sc] = {
            "elec_insensitive": elec_insensitive,
            "capex_slope_per_100k": round(slope_per_100k, 2),
            "lco_min": round(lco_min, 1),
            "lco_max": round(lco_max, 1),
            "gap_from_market_window": round(gap_from_window, 1),
            "pivot": pivot,
        }

    # CCU-GH-MTJ 为主要分析对象
    ccu = result.get("CCU-GH-MTJ", {})
    return {
        "per_scenario": {k: {kk: vv for kk, vv in v.items() if kk != "pivot"} for k, v in result.items()},
        "representative_scenario": "CCU-GH-MTJ",
        "ccu_gh_mtj_elec_insensitive": ccu.get("elec_insensitive", True),
        "ccu_gh_mtj_capex_slope_per_100k": ccu.get("capex_slope_per_100k", float("nan")),
        "ccu_gh_mtj_lco_min": ccu.get("lco_min", float("nan")),
        "ccu_gh_mtj_lco_max": ccu.get("lco_max", float("nan")),
        "ccu_gh_mtj_gap_from_window": ccu.get("gap_from_market_window", float("nan")),
        "pivots": {sc: v["pivot"] for sc, v in result.items() if "pivot" in v},
    }


# ─────────────────────────────────────────────────────────────────────────────
# DAC 成本分析
# ─────────────────────────────────────────────────────────────────────────────

def compute_dac_cost_metrics(df: pd.DataFrame = None) -> Dict[str, Any]:
    """
    计算 DAC 成本敏感性相关派生量。
    DAC-GH-FT 是最具竞争力的 DAC 路径（最低 LCO），为主要分析对象。
    """
    if df is None:
        df = _load_df()

    dac = df[df["param_name"] == "dac_cost"].copy()
    result = {}
    for sc in ["DAC-GH-MTJ", "DAC-GH-FT", "DAC-BH-MTJ", "DAC-BH-FT"]:
        sub = dac[dac["scenario_name"] == sc][["pv", "lco"]].dropna().sort_values("pv")
        if sub.empty:
            continue
        x = sub["pv"].values
        y = sub["lco"].values
        lco_at_baseline = float(y[np.argmin(np.abs(x - DAC_BASELINE))])
        lco_min = float(y.min())

        # 尝试外推到IEA目标（100元/t）
        slope, intercept = np.polyfit(x, y, 1)
        lco_at_iea = float(slope * IEA_DAC_TARGET + intercept)

        breakeven = _interpolate_threshold(x, y, MARKET_WINDOW_UPPER)
        result[sc] = {
            "lco_at_baseline": round(lco_at_baseline, 2),
            "lco_min": round(lco_min, 2),
            "lco_at_iea_target": round(lco_at_iea, 2),
            "gap_from_window_at_min": round(lco_min - MARKET_WINDOW_UPPER, 2),
            "gap_from_window_at_iea": round(lco_at_iea - MARKET_WINDOW_UPPER, 2),
            "breakeven_dac_cost": round(breakeven, 0) if not np.isnan(breakeven) else None,
            "breakeven_reachable": not np.isnan(breakeven),
            "dac_values": x.tolist(),
            "lco_values": y.tolist(),
        }

    dac_gh_ft = result.get("DAC-GH-FT", {})
    return {
        "per_scenario": result,
        "representative_scenario": "DAC-GH-FT",
        "dac_ghft_lco_min": dac_gh_ft.get("lco_min", float("nan")),
        "dac_ghft_lco_at_baseline": dac_gh_ft.get("lco_at_baseline", float("nan")),
        "dac_ghft_lco_at_iea": dac_gh_ft.get("lco_at_iea_target", float("nan")),
        "dac_ghft_gap_from_window": dac_gh_ft.get("gap_from_window_at_min", float("nan")),
        "dac_ghft_breakeven_reachable": dac_gh_ft.get("breakeven_reachable", False),
        "dac_ghft_breakeven_cost": dac_gh_ft.get("breakeven_dac_cost", None),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tornado / 最小边距分析
# ─────────────────────────────────────────────────────────────────────────────

def compute_tornado_and_robustness(df: pd.DataFrame = None) -> Dict[str, Any]:
    """
    计算 Tornado 图所需数据及路径排序稳健性相关派生量。
    """
    if df is None:
        df = _load_df()

    # 对每个场景×参数组合，计算 LCO 范围
    records = []
    for (sc, param), grp in df.groupby(["scenario_name", "param_name"]):
        lco = grp["lco"].dropna()
        if len(lco) == 0:
            continue
        lco_vals = lco[lco > 0]  # 过滤零值（CCU-GH-FT等）
        if len(lco_vals) == 0:
            continue
        records.append({
            "scenario": sc,
            "param": param,
            "lco_min": float(lco_vals.min()),
            "lco_max": float(lco_vals.max()),
            "lco_range": float(lco_vals.max() - lco_vals.min()),
        })
    tornado_df = pd.DataFrame(records).sort_values("lco_range", ascending=False)

    # GTL-BH vs GTL 的最小边距（沿NG价格扫描）
    ng = df[df["param_name"] == "ng_price"].copy()
    gtl_ng = ng[ng["scenario_name"] == "GTL"][["pv", "lco"]].dropna().set_index("pv")["lco"]
    gtlbh_ng = ng[ng["scenario_name"] == "GTL-BH"][["pv", "lco"]].dropna().set_index("pv")["lco"]

    common_prices = sorted(set(gtl_ng.index) & set(gtlbh_ng.index))
    margins = []
    for p in common_prices:
        gap = float(gtl_ng.get(p, float("nan")) - gtlbh_ng.get(p, float("nan")))
        if not np.isnan(gap):
            margins.append((p, gap))

    if margins:
        min_margin_price, min_margin = min(margins, key=lambda x: x[1])
    else:
        min_margin_price, min_margin = float("nan"), float("nan")

    # 排序稳健性阈值：接近交叉的警戒值（1 元/kg）
    rank_reversal_flag_threshold = 1.0

    return {
        "tornado_df": tornado_df,
        "ng_margins": margins,
        "min_margin_gtlbh_vs_gtl": round(min_margin, 2),
        "min_margin_ng_price": min_margin_price,
        "rank_reversal_flag_threshold": rank_reversal_flag_threshold,
        "rank_reversal_occurs": bool(min_margin < 0),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 主入口：返回附录所有数值
# ─────────────────────────────────────────────────────────────────────────────

def get_all_appendix_values() -> Dict[str, Any]:
    """
    计算并返回附录 Section 4 所需的全部派生量，以字典形式提供。
    """
    logger.info("加载敏感性分析结果...")
    df = _load_df()

    logger.info("计算 NG 价格指标...")
    ng = compute_ng_price_metrics(df)
    logger.info("计算 BH CAPEX 指标...")
    bh = compute_bh_capex_metrics(df)
    logger.info("计算电价×CAPEX 指标...")
    ec = compute_electricity_capex_metrics(df)
    logger.info("计算 DAC 成本指标...")
    dac = compute_dac_cost_metrics(df)
    logger.info("计算 Tornado 及稳健性指标...")
    rob = compute_tornado_and_robustness(df)

    values = {
        # Section 4.2.1
        "gtl_ng_threshold": ng["gtl_threshold_yuan_m3"],
        "gtl_effective_baseline_ng": ng["gtl_effective_baseline_ng"],
        "gtl_ng_pct_from_baseline": ng["gtl_pct_from_baseline"],   # 正值 = 涨价余量
        "gtlbh_ng_upper_threshold": ng["gtlbh_upper_threshold_yuan_m3"],
        "gtlbh_effective_baseline_ng": ng["gtlbh_effective_baseline_ng"],
        "gtl_lco_at_baseline": ng["gtl_lco_at_baseline"],
        "gtlbh_lco_at_baseline": ng["gtlbh_lco_at_baseline"],
        "gtlbh_competitive_at_baseline": ng["gtlbh_competitive_at_baseline"],
        # Section 4.2.2
        "bh_slope_per_100k": bh["gtlbh_slope_per_100k"],
        "bh_gtlbh_lco_min": bh["gtlbh_lco_min"],
        "bh_gtlbh_lco_max": bh["gtlbh_lco_max"],
        "bh_gtl_baseline_lco": bh["gtl_baseline_lco"],
        "bh_advantage_at_upper_capex": bh["gtlbh_advantage_at_upper_capex"],
        "bh_crossover_occurs": bh["crossover_occurs"],
        # Section 4.3
        "ec_representative_scenario": ec["representative_scenario"],
        "ec_elec_insensitive": ec["ccu_gh_mtj_elec_insensitive"],
        "ec_capex_slope_per_100k": ec["ccu_gh_mtj_capex_slope_per_100k"],
        "ec_lco_min": ec["ccu_gh_mtj_lco_min"],
        "ec_lco_max": ec["ccu_gh_mtj_lco_max"],
        "ec_gap_from_window": ec["ccu_gh_mtj_gap_from_window"],
        # Section 4.4
        "dac_ghft_lco_min": dac["dac_ghft_lco_min"],
        "dac_ghft_lco_at_baseline": dac["dac_ghft_lco_at_baseline"],
        "dac_ghft_lco_at_iea": dac["dac_ghft_lco_at_iea"],
        "dac_ghft_gap_from_window": dac["dac_ghft_gap_from_window"],
        "dac_ghft_breakeven_reachable": dac["dac_ghft_breakeven_reachable"],
        # Section 4.5
        "min_margin_gtlbh_vs_gtl": rob["min_margin_gtlbh_vs_gtl"],
        "min_margin_ng_price": rob["min_margin_ng_price"],
        "rank_reversal_flag_threshold": rob["rank_reversal_flag_threshold"],
        "rank_reversal_occurs": rob["rank_reversal_occurs"],
        # 完整中间数据（供可视化使用）
        "_ng": ng,
        "_bh": bh,
        "_ec": ec,
        "_dac": dac,
        "_rob": rob,
        "_df": df,
    }

    logger.info("全部派生量计算完成。")
    return values


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    v = get_all_appendix_values()
    print("\n=== 附录派生量摘要 ===")
    print(f"[4.2.1] GTL 有效基准 NG: {v['gtl_effective_baseline_ng']} 元/m³, "
          f"基准LCO: {v['gtl_lco_at_baseline']} 元/kg")
    print(f"[4.2.1] GTL NG阈值(LCO=8): {v['gtl_ng_threshold']} 元/m³ "
          f"({v['gtl_ng_pct_from_baseline']:+.1f}% 相对有效基准, 正值=涨价余量)")
    print(f"[4.2.1] GTL-BH 有效基准 NG: {v['gtlbh_effective_baseline_ng']} 元/m³, "
          f"基准LCO: {v['gtlbh_lco_at_baseline']} 元/kg "
          f"({'低于窗口上限✓' if v['gtlbh_competitive_at_baseline'] else '超出市场窗口'})")
    print(f"[4.2.2] GTL-BH BH CAPEX斜率: {v['bh_slope_per_100k']} 元/kg per 10万元/(kg/h)")
    print(f"[4.2.2] 发生成本交叉: {v['bh_crossover_occurs']}, "
          f"上限CAPEX时优势: {v['bh_advantage_at_upper_capex']} 元/kg")
    print(f"[4.3]   CCU-GH-MTJ 电价不敏感: {v['ec_elec_insensitive']}, "
          f"CAPEX斜率: {v['ec_capex_slope_per_100k']} 元/kg per 10万")
    print(f"[4.3]   最低LCO: {v['ec_lco_min']} 元/kg, 距市场窗口: {v['ec_gap_from_window']} 元/kg")
    print(f"[4.4]   DAC-GH-FT 最低LCO: {v['dac_ghft_lco_min']} 元/kg "
          f"(at 300元/t), 距窗口: {v['dac_ghft_gap_from_window']} 元/kg")
    print(f"[4.4]   IEA 2030目标时 LCO: {v['dac_ghft_lco_at_iea']} 元/kg")
    print(f"[4.5]   GTL-BH vs GTL 最小边距: {v['min_margin_gtlbh_vs_gtl']} 元/kg "
          f"(NG={v['min_margin_ng_price']} 元/m³)")
