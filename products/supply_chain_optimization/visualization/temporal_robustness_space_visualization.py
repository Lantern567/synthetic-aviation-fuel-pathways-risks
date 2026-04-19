"""
Temporal robustness space visualization for 13 SAF pathways.

The figure compresses hourly utilization trajectories into three interpretable
metrics for each pathway:
1. Mean utilization
2. P10 utilization
3. Low-load exposure rate below 70%
"""

import glob
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle
from matplotlib.ticker import MultipleLocator

try:
    from adjustText import adjust_text
except ImportError:
    adjust_text = None


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


class TemporalRobustnessSpaceVisualizer:
    """Build a robustness-space preview figure from existing hourly results."""

    PERIODS_PER_WEEK = 56

    SCENARIOS: Dict[str, Dict[str, object]] = {
        "CTL": {
            "category": "Grey",
            "pathway": "MTJ",
            "color": "#616161",
            "solution_pattern": PROJECT_ROOT
            / "products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/complete_solution_*.json",
            "hourly_pattern": PROJECT_ROOT
            / "products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/hourly_production_summary_*.csv",
        },
        "CTL-BH": {
            "category": "Grey",
            "pathway": "MTJ",
            "color": "#9E9E9E",
            "solution_pattern": PROJECT_ROOT
            / "products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/byproduct_hydrogen/complete_solution_*.json",
            "hourly_pattern": PROJECT_ROOT
            / "products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/byproduct_hydrogen/hourly_production_summary_*.csv",
        },
        "GTL-GH": {
            "category": "Blue",
            "pathway": "MTJ",
            "color": "#1565C0",
            "solution_pattern": PROJECT_ROOT
            / "products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/complete_solution_*.json",
            "hourly_pattern": PROJECT_ROOT
            / "products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/hourly_production_summary_*.csv",
        },
        "GTL": {
            "category": "Blue",
            "pathway": "FT",
            "color": "#1E88E5",
            "solution_pattern": PROJECT_ROOT
            / "products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/ft_one_step/complete_solution_*.json",
            "hourly_pattern": PROJECT_ROOT
            / "products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/ft_one_step/hourly_production_summary_*.csv",
        },
        "DAC-BH-MTJ": {
            "category": "Blue",
            "pathway": "MTJ",
            "color": "#42A5F5",
            "solution_pattern": PROJECT_ROOT
            / "products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/two_step/complete_solution_*.json",
            "hourly_pattern": PROJECT_ROOT
            / "products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/two_step/hourly_production_summary_*.csv",
        },
        "DAC-BH-FT": {
            "category": "Blue",
            "pathway": "FT",
            "color": "#64B5F6",
            "solution_pattern": PROJECT_ROOT
            / "products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/one_step/complete_solution_*.json",
            "hourly_pattern": PROJECT_ROOT
            / "products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/one_step/hourly_production_summary_*.csv",
        },
        "GTL-BH": {
            "category": "Blue",
            "pathway": "MTJ",
            "color": "#90CAF9",
            "solution_pattern": PROJECT_ROOT
            / "products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/byproduct_hydrogen/byproduct_hydrogen/two_step/complete_solution_*.json",
            "hourly_pattern": PROJECT_ROOT
            / "products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/byproduct_hydrogen/byproduct_hydrogen/two_step/hourly_production_summary_*.csv",
        },
        "CCU-BH-MTJ": {
            "category": "Blue",
            "pathway": "MTJ",
            "color": "#0D47A1",
            "solution_pattern": PROJECT_ROOT
            / "products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/two_step/complete_solution_*.json",
            "hourly_pattern": PROJECT_ROOT
            / "products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/two_step/hourly_production_summary_*.csv",
        },
        "CCU-BH-FT": {
            "category": "Blue",
            "pathway": "FT",
            "color": "#1565C0",
            "solution_pattern": PROJECT_ROOT
            / "products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/one_step/complete_solution_*.json",
            "hourly_pattern": PROJECT_ROOT
            / "products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/one_step/hourly_production_summary_*.csv",
        },
        "DAC-GH-MTJ": {
            "category": "Green",
            "pathway": "MTJ",
            "color": "#2E7D32",
            "solution_pattern": PROJECT_ROOT
            / "products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/two_step/complete_solution_*.json",
            "hourly_pattern": PROJECT_ROOT
            / "products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/two_step/hourly_production_summary_*.csv",
        },
        "DAC-GH-FT": {
            "category": "Green",
            "pathway": "FT",
            "color": "#43A047",
            "solution_pattern": PROJECT_ROOT
            / "products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/one_step/complete_solution_*.json",
            "hourly_pattern": PROJECT_ROOT
            / "products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/one_step/hourly_production_summary_*.csv",
        },
        "CCU-GH-MTJ": {
            "category": "Green",
            "pathway": "MTJ",
            "color": "#66BB6A",
            "solution_pattern": PROJECT_ROOT
            / "products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/two_step/complete_solution_*.json",
            "hourly_pattern": PROJECT_ROOT
            / "products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/two_step/hourly_production_summary_*.csv",
        },
        "CCU-GH-FT": {
            "category": "Green",
            "pathway": "FT",
            "color": "#81C784",
            "solution_pattern": PROJECT_ROOT
            / "products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/one_step/complete_solution_*.json",
            "hourly_pattern": PROJECT_ROOT
            / "products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/one_step/hourly_production_summary_*.csv",
        },
    }

    CATEGORY_COLORS = {
        "Grey": "#616161",
        "Blue": "#1565C0",
        "Green": "#2E7D32",
    }

    FIT_COLORS = {
        "Blue/Grey": "#0F4C81",
        "Green": "#2E7D32",
    }

    PENALTY_CLASS_COLORS = {
        "Low-penalty": "#4E79A7",
        "Instability-dominant": "#E15759",
        "Low-utilization-dominant": "#59A14F",
        "Unclassified": "#6B7280",
    }

    def __init__(self, low_load_threshold: float = 0.70):
        self.low_load_threshold = float(low_load_threshold)

        self.output_dir = Path(__file__).parent / "results"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = self.output_dir / f"temporal_robustness_space_{timestamp}"
        self.session_dir.mkdir(parents=True, exist_ok=True)

        logger.info("输出目录: %s", self.session_dir)

    @staticmethod
    def _pick_latest(pattern: Path) -> Optional[Path]:
        files = glob.glob(str(pattern))
        if not files:
            return None
        files.sort(key=lambda item: Path(item).stat().st_mtime, reverse=True)
        return Path(files[0])

    @staticmethod
    def _sum_saf_capacity(facilities: dict) -> float:
        total = 0.0
        for facility in facilities.values():
            tech = str(facility.get("technology", "")).strip().lower()
            mode = str(facility.get("transport_mode", "")).strip().lower()
            if tech == "electrolyzer" or mode == "hydrogen_pipeline":
                continue
            try:
                total += float(facility.get("capacity_kg_per_hour", 0) or 0)
            except (TypeError, ValueError):
                continue
        return total

    @staticmethod
    def _find_column(columns: List[str], exact: Tuple[str, ...], contains: Tuple[str, ...]) -> Optional[str]:
        for column in columns:
            clean = str(column).strip().lstrip("\ufeff")
            if clean in exact or clean.lower() in exact:
                return column
        for column in columns:
            clean = str(column).strip().lstrip("\ufeff").lower()
            if any(token in clean for token in contains):
                return column
        return None

    def _build_utilization_series(self, solution_data: dict, hourly_df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, str]:
        total_h2_capacity = sum(
            float(item.get("capacity_kg_h2_per_hour", 0) or 0)
            for item in solution_data.get("hydrogen_facilities", {}).values()
        )
        total_saf_capacity = self._sum_saf_capacity(solution_data.get("facilities", {}))

        period_col = self._find_column(hourly_df.columns.tolist(), ("时段", "period"), ("period",))
        length_col = self._find_column(hourly_df.columns.tolist(), tuple(), ("时段长度", "period_length"))
        h2_col = self._find_column(hourly_df.columns.tolist(), tuple(), ("氢气产出", "hydrogen"))
        saf_col = self._find_column(hourly_df.columns.tolist(), tuple(), ("saf产出", "saf"))

        if period_col is None:
            period_col = hourly_df.columns[0]

        h2_basis = "electrolyzer_capacity"
        if total_h2_capacity <= 1e-6 and h2_col is not None:
            proxy_hourly_supply = []
            for _, row in hourly_df.iterrows():
                hours = float(row[length_col]) if length_col and pd.notna(row[length_col]) else 3.0
                if hours <= 0:
                    hours = 3.0
                h2_prod = float(row[h2_col]) if pd.notna(row[h2_col]) else 0.0
                proxy_hourly_supply.append(h2_prod / hours)
            if proxy_hourly_supply:
                total_h2_capacity = max(proxy_hourly_supply)
                h2_basis = "proxy_max_hourly_h2_supply"

        h2_values: List[float] = []
        saf_values: List[float] = []

        for _, row in hourly_df.iterrows():
            try:
                period = int(float(row[period_col]))
            except (TypeError, ValueError):
                continue
            if period >= 224:
                continue

            hours = float(row[length_col]) if length_col and pd.notna(row[length_col]) else 3.0
            if hours <= 0:
                hours = 3.0

            h2_prod = float(row[h2_col]) if h2_col and pd.notna(row[h2_col]) else 0.0
            saf_prod = float(row[saf_col]) if saf_col and pd.notna(row[saf_col]) else 0.0

            if total_h2_capacity > 0:
                h2_values.append(min(h2_prod / hours / total_h2_capacity, 1.0))
            if total_saf_capacity > 0:
                saf_values.append(min(saf_prod / hours / total_saf_capacity, 1.0))

        return np.asarray(h2_values, dtype=float), np.asarray(saf_values, dtype=float), h2_basis

    def _metric_block(self, values: np.ndarray) -> Dict[str, float]:
        clean = values[np.isfinite(values)]
        if clean.size == 0:
            return {
                "mean": np.nan,
                "p10": np.nan,
                "low_load": np.nan,
                "robustness_ratio": np.nan,
            }

        mean_value = float(clean.mean())
        p10_value = float(np.quantile(clean, 0.10))
        low_load = float((clean < self.low_load_threshold).mean())
        ratio = float(p10_value / mean_value) if mean_value > 0 else np.nan
        return {
            "mean": mean_value * 100.0,
            "p10": p10_value * 100.0,
            "low_load": low_load * 100.0,
            "robustness_ratio": ratio * 100.0,
        }

    def _renewable_shock_block(self, hourly_df: pd.DataFrame) -> Dict[str, float]:
        length_col = self._find_column(hourly_df.columns.tolist(), tuple(), ("时段长度", "period_length"))
        power_col = self._find_column(hourly_df.columns.tolist(), tuple(), ("电力产出", "power_output", "renew"))

        if power_col is None:
            return {
                "renew_power_mean": 0.0,
                "renew_power_cv": 0.0,
                "renew_zero_pct": 0.0,
                "renew_ramp_pct": 0.0,
            }

        power_series: List[float] = []
        for _, row in hourly_df.iterrows():
            hours = float(row[length_col]) if length_col and pd.notna(row[length_col]) else 3.0
            if hours <= 0:
                hours = 3.0
            power_value = float(row[power_col]) if pd.notna(row[power_col]) else 0.0
            power_series.append(max(power_value / hours, 0.0))

        clean = np.asarray(power_series, dtype=float)
        clean = clean[np.isfinite(clean)]
        if clean.size == 0:
            return {
                "renew_power_mean": 0.0,
                "renew_power_cv": 0.0,
                "renew_zero_pct": 0.0,
                "renew_ramp_pct": 0.0,
            }

        mean_value = float(np.mean(clean))
        if mean_value <= 1e-12:
            return {
                "renew_power_mean": 0.0,
                "renew_power_cv": 0.0,
                "renew_zero_pct": 0.0,
                "renew_ramp_pct": 0.0,
            }

        ramp_pct = 0.0
        if clean.size > 1:
            ramp_pct = float(np.mean(np.abs(np.diff(clean))) / mean_value * 100.0)

        return {
            "renew_power_mean": mean_value,
            "renew_power_cv": float(np.std(clean, ddof=0) / mean_value * 100.0),
            "renew_zero_pct": float((clean <= 1e-9).mean() * 100.0),
            "renew_ramp_pct": ramp_pct,
        }

    def _weekly_mean_series(self, values: np.ndarray) -> List[float]:
        clean = values[np.isfinite(values)]
        if clean.size == 0:
            return [np.nan, np.nan, np.nan, np.nan]

        weekly_means = []
        for week in range(4):
            start = week * self.PERIODS_PER_WEEK
            end = (week + 1) * self.PERIODS_PER_WEEK
            segment = clean[start:end]
            weekly_means.append(float(np.mean(segment)) * 100.0 if len(segment) > 0 else np.nan)
        return weekly_means

    def _weekly_renewable_block(self, hourly_df: pd.DataFrame) -> Dict[str, float]:
        length_col = self._find_column(hourly_df.columns.tolist(), tuple(), ("时段长度", "period_length"))
        power_col = self._find_column(hourly_df.columns.tolist(), tuple(), ("电力产出", "power_output", "renew"))

        if power_col is None:
            return {f"w{week}_{metric}": 0.0 for week in range(1, 5) for metric in ("cv", "zero_pct", "ramp_pct")}

        power_series: List[float] = []
        for _, row in hourly_df.iterrows():
            hours = float(row[length_col]) if length_col and pd.notna(row[length_col]) else 3.0
            if hours <= 0:
                hours = 3.0
            power_value = float(row[power_col]) if pd.notna(row[power_col]) else 0.0
            power_series.append(max(power_value / hours, 0.0))

        clean = np.asarray(power_series, dtype=float)
        clean = clean[np.isfinite(clean)]
        metrics: Dict[str, float] = {}
        for week in range(4):
            start = week * self.PERIODS_PER_WEEK
            end = (week + 1) * self.PERIODS_PER_WEEK
            segment = clean[start:end]
            prefix = f"w{week + 1}"
            if segment.size == 0:
                metrics[f"{prefix}_cv"] = 0.0
                metrics[f"{prefix}_zero_pct"] = 0.0
                metrics[f"{prefix}_ramp_pct"] = 0.0
                continue

            mean_value = float(np.mean(segment))
            if mean_value <= 1e-12:
                metrics[f"{prefix}_cv"] = 0.0
                metrics[f"{prefix}_zero_pct"] = 0.0
                metrics[f"{prefix}_ramp_pct"] = 0.0
                continue

            ramp_pct = 0.0
            if segment.size > 1:
                ramp_pct = float(np.mean(np.abs(np.diff(segment))) / mean_value * 100.0)

            metrics[f"{prefix}_cv"] = float(np.std(segment, ddof=0) / mean_value * 100.0)
            metrics[f"{prefix}_zero_pct"] = float((segment <= 1e-9).mean() * 100.0)
            metrics[f"{prefix}_ramp_pct"] = ramp_pct
        return metrics

    def _weekly_metric_block(self, values: np.ndarray) -> Dict[str, float]:
        clean = values[np.isfinite(values)]
        if clean.size == 0:
            return {
                "worst_week_mean": np.nan,
                "best_week_mean": np.nan,
                "week_spread": np.nan,
                "week_cv": np.nan,
                "w1_mean": np.nan,
                "w2_mean": np.nan,
                "w3_mean": np.nan,
                "w4_mean": np.nan,
            }

        weekly_means = []
        for week in range(4):
            start = week * self.PERIODS_PER_WEEK
            end = (week + 1) * self.PERIODS_PER_WEEK
            segment = clean[start:end]
            weekly_means.append(float(np.mean(segment)) * 100.0 if len(segment) > 0 else np.nan)

        weekly_arr = np.asarray(weekly_means, dtype=float)
        finite_weekly = weekly_arr[np.isfinite(weekly_arr)]
        week_cv = np.nan
        if finite_weekly.size > 0 and float(np.mean(finite_weekly)) > 1e-12:
            week_cv = float(np.std(finite_weekly, ddof=0) / np.mean(finite_weekly) * 100.0)

        return {
            "worst_week_mean": float(np.min(finite_weekly)) if finite_weekly.size else np.nan,
            "best_week_mean": float(np.max(finite_weekly)) if finite_weekly.size else np.nan,
            "week_spread": float(np.max(finite_weekly) - np.min(finite_weekly)) if finite_weekly.size else np.nan,
            "week_cv": week_cv,
            "w1_mean": weekly_means[0],
            "w2_mean": weekly_means[1],
            "w3_mean": weekly_means[2],
            "w4_mean": weekly_means[3],
        }

    def _weekly_coordination_block(self, h2_values: np.ndarray, saf_values: np.ndarray) -> Dict[str, float]:
        pair_count = min(len(h2_values), len(saf_values))
        if pair_count <= 0:
            return {
                "w1_coord": np.nan,
                "w2_coord": np.nan,
                "w3_coord": np.nan,
                "w4_coord": np.nan,
            }

        h2_pair = h2_values[:pair_count]
        saf_pair = saf_values[:pair_count]
        weekly_corrs: List[float] = []
        for week in range(4):
            start = week * self.PERIODS_PER_WEEK
            end = (week + 1) * self.PERIODS_PER_WEEK
            h2_seg = h2_pair[start:end]
            saf_seg = saf_pair[start:end]
            corr = np.nan
            if len(h2_seg) > 1 and len(saf_seg) > 1:
                if np.std(h2_seg) > 1e-12 and np.std(saf_seg) > 1e-12:
                    corr = float(np.corrcoef(h2_seg, saf_seg)[0, 1])
            weekly_corrs.append(corr)

        return {
            "w1_coord": weekly_corrs[0],
            "w2_coord": weekly_corrs[1],
            "w3_coord": weekly_corrs[2],
            "w4_coord": weekly_corrs[3],
        }

    def _low_load_event_block(self, values: np.ndarray) -> Dict[str, float]:
        clean = values[np.isfinite(values)]
        if clean.size == 0:
            return {
                "episodes_6h": np.nan,
                "episodes_12h": np.nan,
                "mean_run_h": np.nan,
                "max_run_h": np.nan,
            }

        low_flags = clean < self.low_load_threshold
        run_lengths: List[int] = []
        current_run = 0
        for flag in low_flags:
            if flag:
                current_run += 1
            elif current_run > 0:
                run_lengths.append(current_run)
                current_run = 0
        if current_run > 0:
            run_lengths.append(current_run)

        if not run_lengths:
            return {
                "episodes_6h": 0.0,
                "episodes_12h": 0.0,
                "mean_run_h": 0.0,
                "max_run_h": 0.0,
            }

        run_arr = np.asarray(run_lengths, dtype=float)
        return {
            "episodes_6h": float(np.sum(run_arr >= 2)),
            "episodes_12h": float(np.sum(run_arr >= 4)),
            "mean_run_h": float(np.mean(run_arr) * 3.0),
            "max_run_h": float(np.max(run_arr) * 3.0),
        }

    @staticmethod
    def _pair_metric_block(h2_values: np.ndarray, saf_values: np.ndarray, h2_basis: str) -> Dict[str, float]:
        if h2_basis != "electrolyzer_capacity":
            return {
                "h2_saf_mismatch": np.nan,
                "h2_saf_corr": np.nan,
            }

        h2_clean = h2_values[np.isfinite(h2_values)]
        saf_clean = saf_values[np.isfinite(saf_values)]
        pair_count = min(len(h2_clean), len(saf_clean))
        if pair_count == 0:
            return {
                "h2_saf_mismatch": np.nan,
                "h2_saf_corr": np.nan,
            }

        h2_pair = h2_clean[:pair_count]
        saf_pair = saf_clean[:pair_count]
        mismatch = float(np.mean(np.abs(h2_pair - saf_pair)) * 100.0)
        corr = np.nan
        if np.std(h2_pair) > 1e-12 and np.std(saf_pair) > 1e-12:
            corr = float(np.corrcoef(h2_pair, saf_pair)[0, 1])

        return {
            "h2_saf_mismatch": mismatch,
            "h2_saf_corr": corr,
        }

    @staticmethod
    def _cost_penalty_block(
        solution_data: dict,
        lcoe: float,
        saf_mean: float,
        worst_week_mean: float,
    ) -> Dict[str, float]:
        total_cost = float(solution_data.get("total_cost_excluding_shortage", 0) or 0)
        investment_cost = float(solution_data.get("total_investment_cost", 0) or 0)

        investment_share = np.nan
        if total_cost > 1e-12:
            investment_share = investment_cost / total_cost

        capex_lcoe = np.nan
        if np.isfinite(lcoe) and np.isfinite(investment_share):
            capex_lcoe = lcoe * investment_share

        utilization_ratio = np.nan
        if np.isfinite(saf_mean) and np.isfinite(worst_week_mean) and worst_week_mean > 1e-12:
            utilization_ratio = saf_mean / worst_week_mean

        worst_week_cost_lift = np.nan
        worst_week_cost_lift_pct = np.nan
        capex_worst_week_cost_lift = np.nan
        if np.isfinite(utilization_ratio):
            worst_week_cost_lift_pct = (utilization_ratio - 1.0) * 100.0
            if np.isfinite(lcoe):
                worst_week_cost_lift = lcoe * (utilization_ratio - 1.0)
            if np.isfinite(capex_lcoe):
                capex_worst_week_cost_lift = capex_lcoe * (utilization_ratio - 1.0)

        chronic_penalty_pct = np.nan
        robustness_penalty_pct = np.nan
        total_penalty_pct = np.nan
        robustness_share_pct = np.nan
        if np.isfinite(saf_mean) and saf_mean > 1e-12:
            chronic_penalty_pct = (100.0 / saf_mean - 1.0) * 100.0
            total_penalty_pct = chronic_penalty_pct
            if np.isfinite(worst_week_mean) and worst_week_mean > 1e-12:
                robustness_penalty_pct = (100.0 / worst_week_mean - 100.0 / saf_mean) * 100.0
                total_penalty_pct = chronic_penalty_pct + robustness_penalty_pct
            if np.isfinite(total_penalty_pct) and total_penalty_pct > 1e-12 and np.isfinite(robustness_penalty_pct):
                robustness_share_pct = robustness_penalty_pct / total_penalty_pct * 100.0

        return {
            "investment_share": investment_share,
            "capex_lcoe": capex_lcoe,
            "worst_week_cost_lift": worst_week_cost_lift,
            "worst_week_cost_lift_pct": worst_week_cost_lift_pct,
            "capex_worst_week_cost_lift": capex_worst_week_cost_lift,
            "chronic_penalty_pct": chronic_penalty_pct,
            "robustness_penalty_pct": robustness_penalty_pct,
            "total_penalty_pct": total_penalty_pct,
            "robustness_share_pct": robustness_share_pct,
        }

    def build_metric_table(self) -> pd.DataFrame:
        rows = []
        for scenario_name, config in self.SCENARIOS.items():
            solution_path = self._pick_latest(config["solution_pattern"])
            hourly_path = self._pick_latest(config["hourly_pattern"])

            if not solution_path or not hourly_path:
                logger.warning("缺少文件: %s", scenario_name)
                continue

            with open(solution_path, "r", encoding="utf-8") as file_obj:
                solution_data = json.load(file_obj)
            hourly_df = pd.read_csv(hourly_path)

            h2_values, saf_values, h2_basis = self._build_utilization_series(solution_data, hourly_df)
            h2_metrics = self._metric_block(h2_values)
            saf_metrics = self._metric_block(saf_values)
            weekly_metrics = self._weekly_metric_block(saf_values)
            h2_weekly_means = self._weekly_mean_series(h2_values)
            weekly_coord = self._weekly_coordination_block(h2_values, saf_values)
            low_load_metrics = self._low_load_event_block(saf_values)
            pair_metrics = self._pair_metric_block(h2_values, saf_values, h2_basis)
            renewable_shock_metrics = self._renewable_shock_block(hourly_df)
            renewable_weekly_metrics = self._weekly_renewable_block(hourly_df)
            lcoe = float(solution_data.get("lifecycle_levelized_cost_excluding_shortage_per_kg", np.nan))
            weekly_coord_values = np.asarray(
                [weekly_coord["w1_coord"], weekly_coord["w2_coord"], weekly_coord["w3_coord"], weekly_coord["w4_coord"]],
                dtype=float,
            )
            finite_weekly_coord = weekly_coord_values[np.isfinite(weekly_coord_values)]
            mean_weekly_coord = float(np.mean(finite_weekly_coord)) if finite_weekly_coord.size else np.nan
            cost_penalty_metrics = self._cost_penalty_block(
                solution_data=solution_data,
                lcoe=lcoe,
                saf_mean=saf_metrics["mean"],
                worst_week_mean=weekly_metrics["worst_week_mean"],
            )

            rows.append(
                {
                    "Scenario": scenario_name,
                    "Category": config["category"],
                    "FitGroup": "Green" if config["category"] == "Green" else "Blue/Grey",
                    "Pathway": config["pathway"],
                    "Color": config["color"],
                    "SolutionFile": solution_path.name,
                    "HourlyFile": hourly_path.name,
                    "LCOE": lcoe,
                    "H2Basis": h2_basis,
                    "H2Mean": h2_metrics["mean"],
                    "H2P10": h2_metrics["p10"],
                    "H2L70": h2_metrics["low_load"],
                    "H2H70": 100.0 - h2_metrics["low_load"] if np.isfinite(h2_metrics["low_load"]) else np.nan,
                    "H2R": h2_metrics["robustness_ratio"],
                    "SAFMean": saf_metrics["mean"],
                    "SAFP10": saf_metrics["p10"],
                    "SAFL70": saf_metrics["low_load"],
                    "SAFH70": 100.0 - saf_metrics["low_load"] if np.isfinite(saf_metrics["low_load"]) else np.nan,
                    "SAFR": saf_metrics["robustness_ratio"],
                    "WorstWeekMean": weekly_metrics["worst_week_mean"],
                    "BestWeekMean": weekly_metrics["best_week_mean"],
                    "WeekSpread": weekly_metrics["week_spread"],
                    "WeekCV": weekly_metrics["week_cv"],
                    "W1Mean": weekly_metrics["w1_mean"],
                    "W2Mean": weekly_metrics["w2_mean"],
                    "W3Mean": weekly_metrics["w3_mean"],
                    "W4Mean": weekly_metrics["w4_mean"],
                    "H2W1Mean": h2_weekly_means[0],
                    "H2W2Mean": h2_weekly_means[1],
                    "H2W3Mean": h2_weekly_means[2],
                    "H2W4Mean": h2_weekly_means[3],
                    "W1Coord": weekly_coord["w1_coord"],
                    "W2Coord": weekly_coord["w2_coord"],
                    "W3Coord": weekly_coord["w3_coord"],
                    "W4Coord": weekly_coord["w4_coord"],
                    "MeanWeeklyCoord": mean_weekly_coord,
                    "LowLoadEpisodes6h": low_load_metrics["episodes_6h"],
                    "LowLoadEpisodes12h": low_load_metrics["episodes_12h"],
                    "MeanLowRunHours": low_load_metrics["mean_run_h"],
                    "MaxLowRunHours": low_load_metrics["max_run_h"],
                    "H2SAFMismatch": pair_metrics["h2_saf_mismatch"],
                    "H2SAFCorr": pair_metrics["h2_saf_corr"],
                    "RenewPowerMeanMW": renewable_shock_metrics["renew_power_mean"],
                    "RenewPowerCV": renewable_shock_metrics["renew_power_cv"],
                    "RenewZeroPct": renewable_shock_metrics["renew_zero_pct"],
                    "RenewRampPct": renewable_shock_metrics["renew_ramp_pct"],
                    "RenewW1CV": renewable_weekly_metrics["w1_cv"],
                    "RenewW2CV": renewable_weekly_metrics["w2_cv"],
                    "RenewW3CV": renewable_weekly_metrics["w3_cv"],
                    "RenewW4CV": renewable_weekly_metrics["w4_cv"],
                    "RenewW1ZeroPct": renewable_weekly_metrics["w1_zero_pct"],
                    "RenewW2ZeroPct": renewable_weekly_metrics["w2_zero_pct"],
                    "RenewW3ZeroPct": renewable_weekly_metrics["w3_zero_pct"],
                    "RenewW4ZeroPct": renewable_weekly_metrics["w4_zero_pct"],
                    "RenewW1RampPct": renewable_weekly_metrics["w1_ramp_pct"],
                    "RenewW2RampPct": renewable_weekly_metrics["w2_ramp_pct"],
                    "RenewW3RampPct": renewable_weekly_metrics["w3_ramp_pct"],
                    "RenewW4RampPct": renewable_weekly_metrics["w4_ramp_pct"],
                    "WorstWeekRetention": (
                        weekly_metrics["worst_week_mean"] / saf_metrics["mean"] * 100.0
                        if np.isfinite(weekly_metrics["worst_week_mean"]) and np.isfinite(saf_metrics["mean"]) and saf_metrics["mean"] > 1e-12
                        else np.nan
                    ),
                    "InvestmentShare": cost_penalty_metrics["investment_share"],
                    "CapexLCOE": cost_penalty_metrics["capex_lcoe"],
                    "WorstWeekCostLift": cost_penalty_metrics["worst_week_cost_lift"],
                    "WorstWeekCostLiftPct": cost_penalty_metrics["worst_week_cost_lift_pct"],
                    "CapexWorstWeekCostLift": cost_penalty_metrics["capex_worst_week_cost_lift"],
                    "ChronicPenaltyPct": cost_penalty_metrics["chronic_penalty_pct"],
                    "RobustnessPenaltyPct": cost_penalty_metrics["robustness_penalty_pct"],
                    "TotalPenaltyPct": cost_penalty_metrics["total_penalty_pct"],
                    "RobustnessSharePct": cost_penalty_metrics["robustness_share_pct"],
                }
            )

        df = pd.DataFrame(rows)
        if df.empty:
            raise RuntimeError("未找到可用的13场景结果文件。")

        df = df.sort_values(["Category", "SAFMean", "Scenario"], ascending=[True, False, True]).reset_index(drop=True)
        df["PenaltyClass"] = df.apply(self._assign_penalty_class, axis=1)

        csv_path = self.session_dir / "temporal_robustness_metrics.csv"
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        df.to_csv(self.output_dir / "temporal_robustness_metrics_latest.csv", index=False, encoding="utf-8-sig")
        logger.info("指标表已保存: %s", csv_path)

        self._log_group_summary(df)
        return df

    @staticmethod
    def _assign_penalty_class(row: pd.Series) -> str:
        total_penalty = float(row.get("TotalPenaltyPct", np.nan))
        chronic_penalty = float(row.get("ChronicPenaltyPct", np.nan))
        instability_penalty = float(row.get("RobustnessPenaltyPct", np.nan))

        if not np.isfinite(total_penalty):
            return "Unclassified"
        if total_penalty < 50.0:
            return "Low-penalty"
        if np.isfinite(instability_penalty) and np.isfinite(chronic_penalty) and instability_penalty > chronic_penalty:
            return "Instability-dominant"
        return "Low-utilization-dominant"

    @staticmethod
    def _fit_line(frame: pd.DataFrame, x_col: str, y_col: str) -> Optional[Dict[str, np.ndarray]]:
        clean = frame[[x_col, y_col]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(clean) < 2 or clean[x_col].nunique() < 2:
            return None

        x = clean[x_col].to_numpy(dtype=float)
        y = clean[y_col].to_numpy(dtype=float)

        slope, intercept = np.polyfit(x, y, deg=1)
        x_fit = np.linspace(max(0.0, x.min() - 2.0), min(100.0, x.max() + 2.0), 100)
        y_fit = slope * x_fit + intercept

        y_hat = slope * x + intercept
        ss_res = float(np.sum((y - y_hat) ** 2))
        ss_tot = float(np.sum((y - y.mean()) ** 2))
        r_squared = np.nan if ss_tot <= 1e-12 else 1.0 - ss_res / ss_tot

        return {
            "x_fit": x_fit,
            "y_fit": y_fit,
            "slope": np.asarray([slope]),
            "intercept": np.asarray([intercept]),
            "r_squared": np.asarray([r_squared]),
        }

    @staticmethod
    def _style_axis(ax: plt.Axes) -> None:
        ax.set_xlim(0, 100)
        ax.set_ylim(0, 100)
        ax.xaxis.set_major_locator(MultipleLocator(20))
        ax.yaxis.set_major_locator(MultipleLocator(20))
        ax.grid(True, linestyle="--", linewidth=0.8, alpha=0.35, dashes=(4, 4))
        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_linewidth(1.0)
            spine.set_color("#666666")

    def _annotate_points(self, ax: plt.Axes, frame: pd.DataFrame, x_col: str, y_col: str) -> None:
        texts = []
        for _, row in frame.iterrows():
            x_value = row[x_col]
            y_value = row[y_col]
            if pd.isna(x_value) or pd.isna(y_value):
                continue
            texts.append(
                ax.text(
                    float(x_value),
                    float(y_value),
                    row["Scenario"],
                    fontsize=8.4,
                    color="#333333",
                    zorder=6,
                )
            )

        if adjust_text and texts:
            try:
                adjust_text(
                    texts,
                    ax=ax,
                    arrowprops=dict(arrowstyle="-", color="#777777", lw=0.6),
                    force_text=(0.4, 0.8),
                    force_static=(0.8, 1.0),
                    ensure_inside_axes=True,
                    expand=(1.08, 1.14),
                    only_move={"points": "xy", "text": "xy"},
                )
            except Exception as exc:  # pragma: no cover - best effort label layout
                logger.warning("adjustText 运行失败: %s", exc)

    def _plot_space_panel(
        self,
        ax: plt.Axes,
        frame: pd.DataFrame,
        x_col: str,
        y_col: str,
        title: str,
        x_label: str,
        y_label: str,
        summary_text: Optional[str] = None,
        note_text: Optional[str] = None,
    ) -> None:
        ax.axvspan(0, 60, color="#F3F4F6", alpha=0.65, zorder=0)
        ax.axvspan(60, 100, color="#EAF5EA", alpha=0.60, zorder=0)
        ax.axhspan(0, 40, color="#F7F3F0", alpha=0.38, zorder=0)
        ax.plot([0, 100], [0, 100], linestyle="--", linewidth=1.2, color="#9AA0A6", zorder=1)

        for _, row in frame.iterrows():
            x_value = row[x_col]
            y_value = row[y_col]
            if pd.isna(x_value) or pd.isna(y_value):
                continue
            marker = "^" if row["Pathway"] == "FT" else "o"
            ax.scatter(
                float(x_value),
                float(y_value),
                s=120,
                marker=marker,
                color=row["Color"],
                edgecolors="white",
                linewidths=1.5,
                alpha=0.95,
                zorder=5,
            )

        for fit_group in ("Blue/Grey", "Green"):
            fit_frame = frame[frame["FitGroup"] == fit_group]
            fit = self._fit_line(fit_frame, x_col, y_col)
            if fit is None:
                continue
            ax.plot(
                fit["x_fit"],
                np.clip(fit["y_fit"], 0, 100),
                color=self.FIT_COLORS[fit_group],
                linewidth=2.2,
                zorder=3,
                label=f"{fit_group} fit (R^2={float(fit['r_squared'][0]):.2f})",
            )

        self._annotate_points(ax, frame, x_col, y_col)

        if summary_text:
            ax.text(
                0.03,
                0.97,
                summary_text,
                transform=ax.transAxes,
                ha="left",
                va="top",
                fontsize=8.5,
                bbox=dict(boxstyle="round,pad=0.35", facecolor="white", edgecolor="#D0D5DD", alpha=0.92),
            )

        if note_text:
            ax.text(
                0.03,
                0.03,
                note_text,
                transform=ax.transAxes,
                ha="left",
                va="bottom",
                fontsize=8.0,
                color="#555555",
            )

        ax.set_title(title, fontsize=13, fontweight="bold", loc="left", pad=10)
        ax.set_xlabel(x_label, fontsize=11.5, fontweight="bold")
        ax.set_ylabel(y_label, fontsize=11.5, fontweight="bold")
        self._style_axis(ax)

    def _plot_quadrant_space_panel(
        self,
        ax: plt.Axes,
        frame: pd.DataFrame,
        x_col: str,
        y_col: str,
        title: str,
        x_label: str,
        y_label: str,
        x_threshold: float,
        y_threshold: float,
        summary_text: Optional[str] = None,
    ) -> None:
        ax.fill_between([0, x_threshold], 0, y_threshold, color="#F3F4F6", alpha=0.72, zorder=0)
        ax.fill_between([0, x_threshold], y_threshold, 100, color="#FFF7ED", alpha=0.62, zorder=0)
        ax.fill_between([x_threshold, 100], 0, y_threshold, color="#FEF2F2", alpha=0.62, zorder=0)
        ax.fill_between([x_threshold, 100], y_threshold, 100, color="#EAF5EA", alpha=0.72, zorder=0)

        ax.axvline(x_threshold, color="#999999", linestyle="--", linewidth=1.2, zorder=1)
        ax.axhline(y_threshold, color="#999999", linestyle="--", linewidth=1.2, zorder=1)

        for _, row in frame.iterrows():
            x_value = row[x_col]
            y_value = row[y_col]
            if pd.isna(x_value) or pd.isna(y_value):
                continue
            marker = "^" if row["Pathway"] == "FT" else "o"
            ax.scatter(
                float(x_value),
                float(y_value),
                s=120,
                marker=marker,
                color=row["Color"],
                edgecolors="white",
                linewidths=1.5,
                alpha=0.95,
                zorder=5,
            )

        for fit_group in ("Blue/Grey", "Green"):
            fit_frame = frame[frame["FitGroup"] == fit_group]
            fit = self._fit_line(fit_frame, x_col, y_col)
            if fit is None:
                continue
            ax.plot(
                fit["x_fit"],
                np.clip(fit["y_fit"], 0, 100),
                color=self.FIT_COLORS[fit_group],
                linewidth=2.2,
                zorder=3,
            )

        self._annotate_points(ax, frame, x_col, y_col)

        if summary_text:
            ax.text(
                0.03,
                0.97,
                summary_text,
                transform=ax.transAxes,
                ha="left",
                va="top",
                fontsize=8.5,
                bbox=dict(boxstyle="round,pad=0.35", facecolor="white", edgecolor="#D0D5DD", alpha=0.92),
            )

        ax.text(0.98, 0.98, "More deployable", transform=ax.transAxes, ha="right", va="top", fontsize=8.2, color="#2E7D32")
        ax.text(0.02, 0.02, "Less deployable", transform=ax.transAxes, ha="left", va="bottom", fontsize=8.2, color="#9A3412")

        ax.set_title(title, fontsize=13, fontweight="bold", loc="left", pad=10)
        ax.set_xlabel(x_label, fontsize=11.5, fontweight="bold")
        ax.set_ylabel(y_label, fontsize=11.5, fontweight="bold")
        self._style_axis(ax)

    def _plot_lollipop_panel(self, ax: plt.Axes, frame: pd.DataFrame) -> None:
        ordered = frame.sort_values(["SAFL70", "SAFMean"], ascending=[False, True]).reset_index(drop=True)
        y_pos = np.arange(len(ordered))

        ax.axvspan(0, 20, color="#EAF5EA", alpha=0.65, zorder=0)
        ax.axvspan(20, 40, color="#FFF3E0", alpha=0.55, zorder=0)
        ax.axvspan(40, 100, color="#FCE8E6", alpha=0.55, zorder=0)

        for idx, row in ordered.iterrows():
            value = float(row["SAFL70"])
            marker = "^" if row["Pathway"] == "FT" else "o"
            ax.hlines(y=idx, xmin=0, xmax=value, color=row["Color"], linewidth=2.6, alpha=0.85, zorder=2)
            ax.scatter(
                value,
                idx,
                s=100,
                marker=marker,
                color=row["Color"],
                edgecolors="white",
                linewidths=1.3,
                zorder=3,
            )
            ax.text(
                value + 1.2,
                idx,
                f"{value:.1f}%",
                va="center",
                ha="left",
                fontsize=8.6,
                color="#444444",
            )

        group_means = (
            frame.assign(FitGroup=np.where(frame["Category"] == "Green", "Green", "Blue/Grey"))
            .groupby("FitGroup")["SAFL70"]
            .mean()
            .to_dict()
        )
        for fit_group in ("Blue/Grey", "Green"):
            if fit_group not in group_means:
                continue
            ax.axvline(
                group_means[fit_group],
                color=self.FIT_COLORS[fit_group],
                linestyle="--",
                linewidth=1.7,
                zorder=1,
            )
            ax.text(
                group_means[fit_group] + 0.8,
                len(ordered) - 0.4 if fit_group == "Blue/Grey" else len(ordered) - 1.4,
                f"{fit_group} mean = {group_means[fit_group]:.1f}%",
                fontsize=8.4,
                color=self.FIT_COLORS[fit_group],
                va="center",
            )

        ax.set_yticks(y_pos)
        ax.set_yticklabels(ordered["Scenario"].tolist(), fontsize=9.5)
        ax.set_xlim(0, 100)
        ax.xaxis.set_major_locator(MultipleLocator(20))
        ax.grid(True, axis="x", linestyle="--", linewidth=0.8, alpha=0.35, dashes=(4, 4))
        ax.invert_yaxis()

        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_linewidth(1.0)
            spine.set_color("#666666")

        ax.set_title("(c) SAF low-load exposure", fontsize=13, fontweight="bold", loc="left", pad=10)
        ax.set_xlabel("L70 = share of time with utilization < 70% (%)", fontsize=11.5, fontweight="bold")

    @staticmethod
    def _style_axis_dynamic(
        ax: plt.Axes,
        x_min: float,
        x_max: float,
        y_min: float,
        y_max: float,
        x_major: float,
        y_major: float,
    ) -> None:
        ax.set_xlim(x_min, x_max)
        ax.set_ylim(y_min, y_max)
        ax.xaxis.set_major_locator(MultipleLocator(x_major))
        ax.yaxis.set_major_locator(MultipleLocator(y_major))
        ax.grid(True, linestyle="--", linewidth=0.8, alpha=0.35, dashes=(4, 4))
        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_linewidth(1.0)
            spine.set_color("#666666")

    def _plot_tradeoff_panel(self, ax: plt.Axes, frame: pd.DataFrame) -> None:
        x_threshold = 8.0
        y_threshold = 70.0
        x_max = max(60.0, float(np.nanmax(frame["LCOE"])) + 4.0)

        ax.fill_between([0, x_threshold], 0, y_threshold, color="#F3F4F6", alpha=0.72, zorder=0)
        ax.fill_between([0, x_threshold], y_threshold, 100, color="#EAF5EA", alpha=0.72, zorder=0)
        ax.fill_between([x_threshold, x_max], 0, y_threshold, color="#FEF2F2", alpha=0.60, zorder=0)
        ax.fill_between([x_threshold, x_max], y_threshold, 100, color="#FFF7ED", alpha=0.62, zorder=0)
        ax.axvline(x_threshold, color="#999999", linestyle="--", linewidth=1.2, zorder=1)
        ax.axhline(y_threshold, color="#999999", linestyle="--", linewidth=1.2, zorder=1)

        for _, row in frame.iterrows():
            marker = "^" if row["Pathway"] == "FT" else "o"
            ax.scatter(
                float(row["LCOE"]),
                float(row["WorstWeekMean"]),
                s=125,
                marker=marker,
                color=row["Color"],
                edgecolors="white",
                linewidths=1.5,
                alpha=0.95,
                zorder=5,
            )

        for fit_group in ("Blue/Grey", "Green"):
            fit_frame = frame[frame["FitGroup"] == fit_group]
            fit = self._fit_line(fit_frame, "LCOE", "WorstWeekMean")
            if fit is None:
                continue
            ax.plot(
                fit["x_fit"],
                np.clip(fit["y_fit"], 0, 100),
                color=self.FIT_COLORS[fit_group],
                linewidth=2.2,
                zorder=3,
            )

        self._annotate_points(ax, frame, "LCOE", "WorstWeekMean")

        grouped = frame.groupby("FitGroup")[["LCOE", "WorstWeekMean"]].mean()
        if {"Blue/Grey", "Green"}.issubset(grouped.index):
            bg = grouped.loc["Blue/Grey"]
            green = grouped.loc["Green"]
            summary_text = (
                f"Blue/Grey mean: LCOE={bg['LCOE']:.1f}, worst-week={bg['WorstWeekMean']:.1f}%\n"
                f"Green mean: LCOE={green['LCOE']:.1f}, worst-week={green['WorstWeekMean']:.1f}%\n"
                f"Gap: {green['LCOE'] - bg['LCOE']:+.1f} CNY/kg, "
                f"{green['WorstWeekMean'] - bg['WorstWeekMean']:+.1f} pp"
            )
            ax.text(
                0.03,
                0.97,
                summary_text,
                transform=ax.transAxes,
                ha="left",
                va="top",
                fontsize=8.5,
                bbox=dict(boxstyle="round,pad=0.35", facecolor="white", edgecolor="#D0D5DD", alpha=0.92),
            )

        ax.text(0.02, 0.98, "Robust but expensive", transform=ax.transAxes, ha="left", va="top", fontsize=8.2, color="#9A6700")
        ax.text(0.98, 0.02, "Cheap but fragile", transform=ax.transAxes, ha="right", va="bottom", fontsize=8.2, color="#B42318")
        ax.text(0.02, 0.02, "Uncompetitive", transform=ax.transAxes, ha="left", va="bottom", fontsize=8.2, color="#666666")
        ax.text(0.98, 0.98, "Most deployable", transform=ax.transAxes, ha="right", va="top", fontsize=8.2, color="#2E7D32")

        ax.set_title("(a) Cost vs worst-week deliverability", fontsize=13, fontweight="bold", loc="left", pad=10)
        ax.set_xlabel("LCOE (CNY/kg)", fontsize=11.5, fontweight="bold")
        ax.set_ylabel("Worst-week mean SAF utilization (%)", fontsize=11.5, fontweight="bold")
        self._style_axis_dynamic(ax, 0, x_max, 30, 100, 10, 10)

    def _plot_worst_week_cost_uplift_panel(self, ax: plt.Axes, frame: pd.DataFrame) -> None:
        clean = frame.dropna(subset=["WorstWeekMean", "WorstWeekCostLiftPct"]).copy()
        x_min = max(35.0, float(np.nanmin(clean["WorstWeekMean"])) - 3.0)
        x_max = min(100.0, float(np.nanmax(clean["WorstWeekMean"])) + 3.0)
        y_max = max(50.0, float(np.nanmax(clean["WorstWeekCostLiftPct"])) + 5.0)

        ax.axvspan(x_min, 55, color="#FCE8E6", alpha=0.58, zorder=0)
        ax.axvspan(55, 70, color="#FFF7ED", alpha=0.62, zorder=0)
        ax.axvspan(70, x_max, color="#EAF5EA", alpha=0.68, zorder=0)
        ax.axhspan(0, 10, color="#EAF5EA", alpha=0.22, zorder=0)
        ax.axvline(70, color="#999999", linestyle="--", linewidth=1.2, zorder=1)

        for _, row in clean.iterrows():
            marker = "^" if row["Pathway"] == "FT" else "o"
            ax.scatter(
                float(row["WorstWeekMean"]),
                float(row["WorstWeekCostLiftPct"]),
                s=130,
                marker=marker,
                color=row["Color"],
                edgecolors="white",
                linewidths=1.5,
                alpha=0.95,
                zorder=4,
            )

        fit = self._fit_line(clean, "WorstWeekMean", "WorstWeekCostLiftPct")
        if fit is not None:
            ax.plot(
                fit["x_fit"],
                np.clip(fit["y_fit"], 0, y_max),
                color="#111111",
                linewidth=2.3,
                linestyle="--",
                zorder=3,
            )

        self._annotate_points(ax, clean, "WorstWeekMean", "WorstWeekCostLiftPct")

        grouped = clean.groupby("FitGroup")[["WorstWeekMean", "WorstWeekCostLiftPct"]].mean()
        summary_lines = []
        if {"Blue/Grey", "Green"}.issubset(grouped.index):
            bg = grouped.loc["Blue/Grey"]
            green = grouped.loc["Green"]
            summary_lines.append(
                f"Blue/Grey mean: worst-week={bg['WorstWeekMean']:.1f}%, uplift={bg['WorstWeekCostLiftPct']:.1f}%"
            )
            summary_lines.append(
                f"Green mean: worst-week={green['WorstWeekMean']:.1f}%, uplift={green['WorstWeekCostLiftPct']:.1f}%"
            )
        if fit is not None:
            summary_lines.append(
                f"Global fit: uplift = {float(fit['intercept'][0]):.1f} {float(fit['slope'][0]):+.3f} x worst-week, R²={float(fit['r_squared'][0]):.2f}"
            )
        if summary_lines:
            ax.text(
                0.03,
                0.97,
                "\n".join(summary_lines),
                transform=ax.transAxes,
                ha="left",
                va="top",
                fontsize=8.5,
                bbox=dict(boxstyle="round,pad=0.35", facecolor="white", edgecolor="#D0D5DD", alpha=0.93),
            )

        ax.text(
            0.02,
            0.02,
            "Percent uplift = (SAFMean / WorstWeekMean - 1) x 100%\nIt measures how much the worst-week under-utilization would dilute average unit cost.",
            transform=ax.transAxes,
            ha="left",
            va="bottom",
            fontsize=8.0,
            color="#555555",
        )

        ax.set_title("(a) Worst-week utilization penalty on average cost", fontsize=13, fontweight="bold", loc="left", pad=10)
        ax.set_xlabel("Worst-week mean SAF utilization (%)", fontsize=11.5, fontweight="bold")
        ax.set_ylabel("Implied average-cost uplift from worst week (%)", fontsize=11.5, fontweight="bold")
        self._style_axis_dynamic(ax, x_min, x_max, 0, y_max, 10, 10)

    def _plot_cost_penalty_decomposition_panel(self, ax: plt.Axes, frame: pd.DataFrame) -> None:
        ordered = (
            frame.dropna(subset=["ChronicPenaltyPct", "RobustnessPenaltyPct", "TotalPenaltyPct"])
            .sort_values(["TotalPenaltyPct", "RobustnessPenaltyPct"], ascending=[False, False])
            .reset_index(drop=True)
        )
        y_pos = np.arange(len(ordered))
        x_max = max(160.0, float(np.nanmax(ordered["TotalPenaltyPct"])) + 15.0)

        chronic_color = "#F59E0B"
        unstable_color = "#B42318"

        ax.axvspan(0, 40, color="#EAF5EA", alpha=0.60, zorder=0)
        ax.axvspan(40, 80, color="#FFF7ED", alpha=0.58, zorder=0)
        ax.axvspan(80, x_max, color="#FCE8E6", alpha=0.55, zorder=0)

        for idx, row in ordered.iterrows():
            chronic = float(row["ChronicPenaltyPct"])
            unstable = float(row["RobustnessPenaltyPct"])
            total = float(row["TotalPenaltyPct"])
            marker = "^" if row["Pathway"] == "FT" else "o"

            ax.barh(idx, chronic, height=0.72, color=chronic_color, edgecolor="white", linewidth=1.0, zorder=2)
            ax.barh(
                idx,
                unstable,
                left=chronic,
                height=0.72,
                color=unstable_color,
                edgecolor="white",
                linewidth=1.0,
                zorder=2,
            )
            ax.scatter(
                total,
                idx,
                s=90,
                marker=marker,
                color=row["Color"],
                edgecolors="white",
                linewidths=1.2,
                zorder=4,
            )
            ax.text(total + 1.6, idx, f"{total:.0f}%", va="center", ha="left", fontsize=8.4, color="#333333")

        grouped = ordered.groupby("FitGroup")[["ChronicPenaltyPct", "RobustnessPenaltyPct", "TotalPenaltyPct"]].mean()
        for fit_group in ("Blue/Grey", "Green"):
            if fit_group not in grouped.index:
                continue
            mean_total = float(grouped.loc[fit_group, "TotalPenaltyPct"])
            ax.axvline(mean_total, color=self.FIT_COLORS[fit_group], linestyle="--", linewidth=1.8, zorder=1)

        summary_lines = []
        if {"Blue/Grey", "Green"}.issubset(grouped.index):
            bg = grouped.loc["Blue/Grey"]
            green = grouped.loc["Green"]
            summary_lines.append(
                f"Blue/Grey mean: {bg['TotalPenaltyPct']:.1f}% = {bg['ChronicPenaltyPct']:.1f}% low-util + {bg['RobustnessPenaltyPct']:.1f}% instability"
            )
            summary_lines.append(
                f"Green mean: {green['TotalPenaltyPct']:.1f}% = {green['ChronicPenaltyPct']:.1f}% low-util + {green['RobustnessPenaltyPct']:.1f}% instability"
            )
        if summary_lines:
            ax.text(
                0.03,
                0.97,
                "\n".join(summary_lines),
                transform=ax.transAxes,
                ha="left",
                va="top",
                fontsize=8.4,
                bbox=dict(boxstyle="round,pad=0.35", facecolor="white", edgecolor="#D0D5DD", alpha=0.93),
            )

        ax.set_yticks(y_pos)
        ax.set_yticklabels(ordered["Scenario"].tolist(), fontsize=9.4)
        for tick_label, (_, row) in zip(ax.get_yticklabels(), ordered.iterrows()):
            tick_label.set_color(row["Color"])
        ax.set_xlim(0, x_max)
        ax.xaxis.set_major_locator(MultipleLocator(20))
        ax.grid(True, axis="x", linestyle="--", linewidth=0.8, alpha=0.35, dashes=(4, 4))
        ax.invert_yaxis()
        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_linewidth(1.0)
            spine.set_color("#666666")

        ax.set_title("(a) Cost uplift decomposition", fontsize=13, fontweight="bold", loc="left", pad=10)
        ax.set_xlabel("Implied cost uplift relative to full utilization (%)", fontsize=11.5, fontweight="bold")

    def _plot_cost_penalty_space_panel(self, ax: plt.Axes, frame: pd.DataFrame) -> None:
        clean = frame.dropna(subset=["ChronicPenaltyPct", "RobustnessPenaltyPct", "TotalPenaltyPct"]).copy()
        x_max = max(100.0, float(np.nanmax(clean["ChronicPenaltyPct"])) + 10.0)
        y_max = max(65.0, float(np.nanmax(clean["RobustnessPenaltyPct"])) + 8.0)
        diag_max = min(x_max, y_max)

        x_fill = np.linspace(0.0, diag_max, 300)
        ax.fill_between(
            x_fill,
            x_fill,
            np.full_like(x_fill, y_max),
            color="#FCE8E6",
            alpha=0.50,
            zorder=0,
        )
        ax.plot([0, diag_max], [0, diag_max], linestyle="--", linewidth=1.2, color="#8A8F98", zorder=1)

        total_min = float(np.nanmin(clean["TotalPenaltyPct"]))
        total_max = float(np.nanmax(clean["TotalPenaltyPct"]))
        if total_max - total_min <= 1e-12:
            clean["BubbleSize"] = 520.0
        else:
            bubble_norm = (clean["TotalPenaltyPct"] - total_min) / (total_max - total_min)
            clean["BubbleSize"] = 90.0 + np.power(bubble_norm, 1.35) * 1800.0

        for _, row in clean.iterrows():
            ax.scatter(
                float(row["ChronicPenaltyPct"]),
                float(row["RobustnessPenaltyPct"]),
                s=float(row["BubbleSize"]),
                marker="o",
                color=row["Color"],
                edgecolors="none",
                linewidths=0.0,
                alpha=0.88,
                zorder=4,
            )

        self._annotate_points(ax, clean, "ChronicPenaltyPct", "RobustnessPenaltyPct")

        grouped = clean.groupby("FitGroup")[["ChronicPenaltyPct", "RobustnessPenaltyPct", "TotalPenaltyPct"]].mean()
        if {"Blue/Grey", "Green"}.issubset(grouped.index):
            bg = grouped.loc["Blue/Grey"]
            green = grouped.loc["Green"]
            summary_text = (
                f"Blue/Grey mean: low-util={bg['ChronicPenaltyPct']:.1f}%, instability={bg['RobustnessPenaltyPct']:.1f}%, total={bg['TotalPenaltyPct']:.1f}%\n"
                f"Green mean: low-util={green['ChronicPenaltyPct']:.1f}%, instability={green['RobustnessPenaltyPct']:.1f}%, total={green['TotalPenaltyPct']:.1f}%"
            )
            ax.text(
                0.03,
                0.97,
                summary_text,
                transform=ax.transAxes,
                ha="left",
                va="top",
                fontsize=8.4,
                bbox=dict(boxstyle="round,pad=0.35", facecolor="white", edgecolor="#D0D5DD", alpha=0.93),
            )

        ax.text(0.97, 0.97, "Instability-dominant", transform=ax.transAxes, ha="right", va="top", fontsize=8.2, color="#B42318")
        ax.text(0.97, 0.03, "Low-utilization-dominant", transform=ax.transAxes, ha="right", va="bottom", fontsize=8.2, color="#9A6700")

        ax.set_title("Penalty space: low utilization vs instability", fontsize=13, fontweight="bold", loc="left", pad=10)
        ax.set_xlabel("Chronic low-utilization penalty (%)", fontsize=11.5, fontweight="bold")
        ax.set_ylabel("Additional instability penalty (%)", fontsize=11.5, fontweight="bold")
        self._style_axis_dynamic(ax, 0, x_max, 0, y_max, 20, 10)

    def _plot_coordination_effect_panel(
        self,
        ax: plt.Axes,
        frame: pd.DataFrame,
        y_col: str,
        y_label: str,
        title: str,
        summary_key: str,
        y_threshold: float,
    ) -> None:
        clean = frame.dropna(subset=["MeanWeeklyCoord", y_col]).copy()
        x_min = min(0.0, float(np.nanmin(clean["MeanWeeklyCoord"])) - 0.05)
        x_max = min(1.02, max(0.9, float(np.nanmax(clean["MeanWeeklyCoord"])) + 0.05))
        y_min = max(0.0, float(np.nanmin(clean[y_col])) - 6.0)
        y_max = min(100.0, max(y_threshold + 8.0, float(np.nanmax(clean[y_col])) + 4.0))

        ax.axvspan(0.6, x_max, color="#EAF5EA", alpha=0.20, zorder=0)
        ax.axhspan(y_threshold, y_max, color="#F8FAFC", alpha=0.22, zorder=0)
        ax.axvline(0.6, color="#9AA0A6", linestyle="--", linewidth=1.1, zorder=1)
        ax.axhline(y_threshold, color="#9AA0A6", linestyle="--", linewidth=1.1, zorder=1)

        for _, row in clean.iterrows():
            ax.scatter(
                float(row["MeanWeeklyCoord"]),
                float(row[y_col]),
                s=190.0,
                marker="o",
                color=row["Color"],
                edgecolors="none",
                linewidths=0.0,
                alpha=0.88,
                zorder=3,
            )

        self._annotate_points(ax, clean, "MeanWeeklyCoord", y_col)

        grouped = clean.groupby("FitGroup")[["MeanWeeklyCoord", y_col]].mean()
        summary_lines = []
        if {"Blue/Grey", "Green"}.issubset(grouped.index):
            bg = grouped.loc["Blue/Grey"]
            green = grouped.loc["Green"]
            summary_lines.append(
                f"Blue/Grey mean: coord={bg['MeanWeeklyCoord']:.2f}, {summary_key}={bg[y_col]:.1f}%"
            )
            summary_lines.append(
                f"Green mean: coord={green['MeanWeeklyCoord']:.2f}, {summary_key}={green[y_col]:.1f}%"
            )
        omitted = frame["MeanWeeklyCoord"].isna().sum()
        if omitted:
            summary_lines.append(f"Omitted {omitted} pathway with undefined H2-SAF coordination.")
        if summary_lines:
            ax.text(
                0.03,
                0.97,
                "\n".join(summary_lines),
                transform=ax.transAxes,
                ha="left",
                va="top",
                fontsize=8.4,
                bbox=dict(boxstyle="round,pad=0.35", facecolor="white", edgecolor="#D0D5DD", alpha=0.93),
            )

        ax.text(0.97, 0.97, "Higher coordination + better outcome", transform=ax.transAxes, ha="right", va="top", fontsize=8.2, color="#2E7D32")

        ax.set_title(title, fontsize=13, fontweight="bold", loc="left", pad=10)
        ax.set_xlabel("Mean weekly H2-SAF coordination (Pearson r)", fontsize=11.5, fontweight="bold")
        ax.set_ylabel(y_label, fontsize=11.5, fontweight="bold")
        self._style_axis_dynamic(ax, x_min, x_max, y_min, y_max, 0.2, 10)

    def _plot_driver_mechanism_heatmap(self, ax: plt.Axes, frame: pd.DataFrame) -> None:
        driver_groups = [
            ("Hydrogen supply", [("H2Mean", "H2 mean"), ("H2P10", "H2 P10"), ("H2L70", "H2 low-load")]),
            ("Coordination", [("MeanWeeklyCoord", "Mean coord"), ("H2SAFCorr", "Pair corr"), ("H2SAFMismatch", "Mismatch")]),
            ("Renewable shock", [("RenewPowerCV", "Power CV"), ("RenewZeroPct", "Zero-output"), ("RenewRampPct", "Ramp intensity")]),
        ]
        outcomes = [
            ("SAFMean", "Mean SAF utilization"),
            ("WorstWeekRetention", "Worst-week retention"),
            ("TotalPenaltyPct", "Total cost penalty"),
        ]

        driver_keys = [item[0] for _, items in driver_groups for item in items]
        driver_labels = [item[1] for _, items in driver_groups for item in items]

        corr_values = np.full((len(outcomes), len(driver_keys)), np.nan, dtype=float)
        n_values = np.zeros((len(outcomes), len(driver_keys)), dtype=int)
        for i, (out_key, _) in enumerate(outcomes):
            for j, drv_key in enumerate(driver_keys):
                subset = frame[[out_key, drv_key]].replace([np.inf, -np.inf], np.nan).dropna()
                if len(subset) >= 3 and subset[drv_key].nunique() >= 2:
                    corr_values[i, j] = float(subset[out_key].corr(subset[drv_key]))
                    n_values[i, j] = int(len(subset))

        im = ax.imshow(corr_values, cmap="RdBu_r", vmin=-1.0, vmax=1.0, aspect="auto", zorder=1)

        for idx in range(len(driver_keys) + 1):
            ax.axvline(idx - 0.5, color="white", linewidth=1.0, alpha=0.85, zorder=2)
        for idx in range(len(outcomes) + 1):
            ax.axhline(idx - 0.5, color="white", linewidth=1.0, alpha=0.85, zorder=2)

        start = 0
        for group_name, items in driver_groups:
            end = start + len(items)
            ax.axvspan(start - 0.5, end - 0.5, ymin=0.92, ymax=1.0, color="#F3F4F6", zorder=3)
            ax.text(
                (start + end - 1) / 2,
                -0.95,
                group_name,
                ha="center",
                va="bottom",
                fontsize=10,
                fontweight="bold",
                color="#374151",
                clip_on=False,
            )
            if end < len(driver_keys):
                ax.axvline(end - 0.5, color="#6B7280", linewidth=1.6, zorder=3)
            start = end

        for i in range(len(outcomes)):
            for j in range(len(driver_keys)):
                value = corr_values[i, j]
                label = "NA" if not np.isfinite(value) else f"{value:+.2f}\n(n={n_values[i, j]})"
                text_color = "#111111" if not np.isfinite(value) or abs(value) < 0.55 else "white"
                ax.text(j, i, label, ha="center", va="center", fontsize=8.3, color=text_color, zorder=4)

        ax.set_xticks(np.arange(len(driver_keys)))
        ax.set_xticklabels(driver_labels, fontsize=9.5)
        ax.set_yticks(np.arange(len(outcomes)))
        ax.set_yticklabels([item[1] for item in outcomes], fontsize=10)
        ax.tick_params(axis="x", bottom=False, top=False, labelbottom=True)
        ax.tick_params(axis="y", left=False)

        for spine in ax.spines.values():
            spine.set_visible(False)

        ax.set_title("Mechanism screening: supply, coordination, and renewable shock drivers", fontsize=13, fontweight="bold", loc="left", pad=18)

        cbar = plt.colorbar(im, ax=ax, fraction=0.045, pad=0.025)
        cbar.set_label("Pearson correlation", fontsize=10)
        cbar.ax.tick_params(labelsize=9)

    @staticmethod
    def _build_class_weekly_table(frame: pd.DataFrame) -> pd.DataFrame:
        records: List[Dict[str, object]] = []
        for _, row in frame.iterrows():
            saf_mean = float(row.get("SAFMean", np.nan))
            for week in range(1, 5):
                saf_week = float(row.get(f"W{week}Mean", np.nan))
                if not np.isfinite(saf_week):
                    continue

                week_retention = np.nan
                week_penalty_lift = np.nan
                if np.isfinite(saf_mean) and saf_mean > 1e-12:
                    week_retention = saf_week / saf_mean * 100.0
                    if saf_week > 1e-12:
                        week_penalty_lift = (100.0 / saf_week - 100.0 / saf_mean) * 100.0

                records.append(
                    {
                        "Scenario": row["Scenario"],
                        "PenaltyClass": row["PenaltyClass"],
                        "Week": f"W{week}",
                        "H2WeekMean": float(row.get(f"H2W{week}Mean", np.nan)),
                        "WeekCoord": float(row.get(f"W{week}Coord", np.nan)),
                        "RenewWeekCV": float(row.get(f"RenewW{week}CV", np.nan)),
                        "RenewWeekZeroPct": float(row.get(f"RenewW{week}ZeroPct", np.nan)),
                        "RenewWeekRampPct": float(row.get(f"RenewW{week}RampPct", np.nan)),
                        "SAFWeekMean": saf_week,
                        "WeekRetention": week_retention,
                        "WeekPenaltyLift": week_penalty_lift,
                    }
                )

        return pd.DataFrame(records)

    @staticmethod
    def _penalty_driver_groups() -> List[Tuple[str, List[Tuple[str, str]]]]:
        return [
            ("Hydrogen supply", [("H2WeekMean", "H2 week mean")]),
            ("Coordination", [("WeekCoord", "Weekly coord")]),
            ("Renewable shock", [("RenewWeekCV", "Power CV"), ("RenewWeekZeroPct", "Zero-output"), ("RenewWeekRampPct", "Ramp intensity")]),
        ]

    def _plot_penalty_class_header_band(self, ax: plt.Axes) -> None:
        driver_groups = self._penalty_driver_groups()
        total_cols = sum(len(items) for _, items in driver_groups)

        ax.set_xlim(-0.5, total_cols - 0.5)
        ax.set_ylim(0.0, 1.0)
        ax.axis("off")

        start = 0
        for group_name, items in driver_groups:
            end = start + len(items)
            ax.add_patch(
                Rectangle(
                    (start - 0.5, 0.0),
                    len(items),
                    1.0,
                    facecolor="#F7F7F8",
                    edgecolor="#D1D5DB",
                    linewidth=0.9,
                )
            )
            ax.text(
                (start + end - 1) / 2,
                0.5,
                group_name,
                ha="center",
                va="center",
                fontsize=11.4,
                fontweight="bold",
                color="#374151",
            )
            if end < total_cols:
                ax.axvline(end - 0.5, color="#6B7280", linewidth=1.4)
            start = end

    def _plot_penalty_class_mechanism_panel(
        self,
        ax: plt.Axes,
        frame: pd.DataFrame,
        class_name: str,
        show_xlabels: bool = True,
        show_class_label: bool = True,
        vmin: float = -1.0,
        vmax: float = 1.0,
    ):
        driver_groups = self._penalty_driver_groups()
        outcomes = [
            ("SAFWeekMean", "Weekly SAF utilization"),
            ("WeekRetention", "Weekly retention"),
        ]

        driver_keys = [item[0] for _, items in driver_groups for item in items]
        driver_labels = [item[1] for _, items in driver_groups for item in items]
        class_frame = frame[frame["PenaltyClass"] == class_name].copy()
        border_color = self.PENALTY_CLASS_COLORS.get(class_name, self.PENALTY_CLASS_COLORS["Unclassified"])
        corr_values = np.full((len(outcomes), len(driver_keys)), np.nan, dtype=float)

        for i, (out_key, _) in enumerate(outcomes):
            for j, drv_key in enumerate(driver_keys):
                subset = class_frame[[out_key, drv_key]].replace([np.inf, -np.inf], np.nan).dropna()
                if len(subset) >= 4 and subset[drv_key].nunique() >= 2:
                    corr_values[i, j] = float(subset[out_key].corr(subset[drv_key]))

        im = ax.imshow(corr_values, cmap="RdBu_r", vmin=vmin, vmax=vmax, aspect="auto", zorder=1)

        for idx in range(len(driver_keys) + 1):
            ax.axvline(idx - 0.5, color="white", linewidth=1.0, alpha=0.85, zorder=2)
        for idx in range(len(outcomes) + 1):
            ax.axhline(idx - 0.5, color="white", linewidth=1.0, alpha=0.85, zorder=2)

        start = 0
        for group_name, items in driver_groups:
            end = start + len(items)
            if end < len(driver_keys):
                ax.axvline(end - 0.5, color="#6B7280", linewidth=1.4, zorder=3)
            start = end

        for i in range(len(outcomes)):
            for j in range(len(driver_keys)):
                value = corr_values[i, j]
                label = "NA" if not np.isfinite(value) else f"{value:+.2f}"
                text_color = "#111111" if not np.isfinite(value) or abs(value) < 0.55 else "white"
                ax.text(j, i, label, ha="center", va="center", fontsize=18.0, color=text_color, zorder=4)

        ax.set_xticks(np.arange(len(driver_keys)))
        ax.set_xticklabels(driver_labels if show_xlabels else [""] * len(driver_labels), fontsize=11.4)
        ax.set_yticks(np.arange(len(outcomes)))
        ax.set_yticklabels([item[1] for item in outcomes], fontsize=11.4)
        ax.tick_params(axis="x", bottom=False, top=False, labelbottom=show_xlabels, pad=2)
        ax.tick_params(axis="y", left=False)
        for spine in ax.spines.values():
            spine.set_visible(False)

        path_count = int(class_frame["Scenario"].nunique())
        week_count = int(len(class_frame))
        if show_class_label:
            panel_frame = Rectangle(
                (0.0, 0.0),
                1.0,
                1.0,
                transform=ax.transAxes,
                fill=False,
                edgecolor=border_color,
                linewidth=2.2,
                zorder=5,
                clip_on=False,
            )
            ax.add_patch(panel_frame)
            ax.text(
                -0.23,
                0.5,
                f"{class_name}\n{path_count} pathways / {week_count} week-points",
                transform=ax.transAxes,
                ha="right",
                va="center",
                fontsize=11.2,
                fontweight="bold",
                color=border_color,
                bbox=dict(boxstyle="round,pad=0.28", facecolor="white", edgecolor=border_color, linewidth=1.5),
            )
        return im

    def _plot_event_lollipop_panel(self, ax: plt.Axes, frame: pd.DataFrame) -> None:
        ordered = frame.sort_values(["LowLoadEpisodes6h", "MaxLowRunHours"], ascending=[False, False]).reset_index(drop=True)
        y_pos = np.arange(len(ordered))
        x_max = max(50.0, float(np.nanmax(ordered["LowLoadEpisodes6h"])) + 4.0)

        ax.axvspan(0, 5, color="#EAF5EA", alpha=0.65, zorder=0)
        ax.axvspan(5, 15, color="#FFF7ED", alpha=0.58, zorder=0)
        ax.axvspan(15, x_max, color="#FCE8E6", alpha=0.58, zorder=0)

        for idx, row in ordered.iterrows():
            value = float(row["LowLoadEpisodes6h"])
            marker = "^" if row["Pathway"] == "FT" else "o"
            ax.hlines(y=idx, xmin=0, xmax=value, color=row["Color"], linewidth=2.6, alpha=0.85, zorder=2)
            ax.scatter(
                value,
                idx,
                s=100,
                marker=marker,
                color=row["Color"],
                edgecolors="white",
                linewidths=1.3,
                zorder=3,
            )
            suffix = ""
            if float(row["MaxLowRunHours"]) >= 24:
                suffix = f" | max {int(row['MaxLowRunHours'])}h"
            ax.text(
                value + 0.6,
                idx,
                f"{int(round(value))}{suffix}",
                va="center",
                ha="left",
                fontsize=8.4,
                color="#444444",
            )

        group_means = frame.groupby("FitGroup")["LowLoadEpisodes6h"].mean().to_dict()
        for fit_group in ("Blue/Grey", "Green"):
            if fit_group not in group_means:
                continue
            ax.axvline(
                group_means[fit_group],
                color=self.FIT_COLORS[fit_group],
                linestyle="--",
                linewidth=1.7,
                zorder=1,
            )
            ax.text(
                group_means[fit_group] + 0.6,
                len(ordered) - 0.4 if fit_group == "Blue/Grey" else len(ordered) - 1.4,
                f"{fit_group} mean = {group_means[fit_group]:.1f}",
                fontsize=8.2,
                color=self.FIT_COLORS[fit_group],
                va="center",
            )

        ax.set_yticks(y_pos)
        ax.set_yticklabels(ordered["Scenario"].tolist(), fontsize=9.5)
        ax.set_xlim(0, x_max)
        ax.xaxis.set_major_locator(MultipleLocator(10))
        ax.grid(True, axis="x", linestyle="--", linewidth=0.8, alpha=0.35, dashes=(4, 4))
        ax.invert_yaxis()
        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_linewidth(1.0)
            spine.set_color("#666666")

        ax.set_title("(b) Frequency of sustained low-load events", fontsize=13, fontweight="bold", loc="left", pad=10)
        ax.set_xlabel("Number of SAF low-load events (<70% for >=6 h)", fontsize=11.5, fontweight="bold")

    def _plot_weekly_scatter_panel(self, ax: plt.Axes, frame: pd.DataFrame) -> None:
        ax.axvspan(-0.2, 0.2, color="#FCE8E6", alpha=0.58, zorder=0)
        ax.axvspan(0.2, 0.6, color="#FFF7ED", alpha=0.62, zorder=0)
        ax.axvspan(0.6, 1.0, color="#EAF5EA", alpha=0.72, zorder=0)
        ax.axhspan(0, 70, color="#F3F4F6", alpha=0.28, zorder=0)
        ax.axvline(0.6, color="#999999", linestyle="--", linewidth=1.2, zorder=1)
        ax.axhline(70, color="#999999", linestyle="--", linewidth=1.2, zorder=1)

        week_pairs = [
            ("W1Coord", "W1Mean"),
            ("W2Coord", "W2Mean"),
            ("W3Coord", "W3Mean"),
            ("W4Coord", "W4Mean"),
        ]
        scatter_rows = []
        for _, row in frame.iterrows():
            for coord_col, util_col in week_pairs:
                coord = row[coord_col]
                util = row[util_col]
                if pd.isna(coord) or pd.isna(util):
                    continue
                scatter_rows.append(
                    {
                        "Scenario": row["Scenario"],
                        "Category": row["Category"],
                        "FitGroup": row["FitGroup"],
                        "Pathway": row["Pathway"],
                        "Color": row["Color"],
                        "Coord": float(coord),
                        "Util": float(util),
                    }
                )

        scatter_df = pd.DataFrame(scatter_rows)
        for _, row in scatter_df.iterrows():
            ax.scatter(
                row["Coord"],
                row["Util"],
                s=90,
                marker="o",
                color=row["Color"],
                edgecolors="white",
                linewidths=1.1,
                alpha=0.88,
                zorder=3,
            )

        for fit_group in ("Blue/Grey", "Green"):
            fit_frame = scatter_df[scatter_df["FitGroup"] == fit_group]
            fit = None
            if not fit_frame.empty and fit_frame["Coord"].nunique() >= 2:
                x = fit_frame["Coord"].to_numpy(dtype=float)
                y = fit_frame["Util"].to_numpy(dtype=float)
                slope, intercept = np.polyfit(x, y, deg=1)
                x_fit = np.linspace(max(-0.2, x.min() - 0.03), min(1.0, x.max() + 0.03), 100)
                y_fit = slope * x_fit + intercept
                ax.plot(
                    x_fit,
                    np.clip(y_fit, 0, 100),
                    color=self.FIT_COLORS[fit_group],
                    linewidth=2.2,
                    zorder=2,
                )

        grouped = scatter_df.groupby("FitGroup")[["Coord", "Util"]].mean()
        if {"Blue/Grey", "Green"}.issubset(grouped.index):
            bg = grouped.loc["Blue/Grey"]
            green = grouped.loc["Green"]
            summary_text = (
                f"Blue/Grey weekly mean: coord={bg['Coord']:.2f}, SAF={bg['Util']:.1f}%\n"
                f"Green weekly mean: coord={green['Coord']:.2f}, SAF={green['Util']:.1f}%"
            )
            ax.text(
                0.03,
                0.97,
                summary_text,
                transform=ax.transAxes,
                ha="left",
                va="top",
                fontsize=8.4,
                bbox=dict(boxstyle="round,pad=0.35", facecolor="white", edgecolor="#D0D5DD", alpha=0.92),
            )

        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_linewidth(1.0)
            spine.set_color("#666666")

        ax.set_xlim(-0.2, 1.0)
        ax.set_ylim(35, 100)
        ax.xaxis.set_major_locator(MultipleLocator(0.2))
        ax.yaxis.set_major_locator(MultipleLocator(10))
        ax.grid(True, linestyle="--", linewidth=0.8, alpha=0.35, dashes=(4, 4))
        ax.set_title("(c) Weekly H2-SAF coordination vs SAF utilization", fontsize=13, fontweight="bold", loc="left", pad=10)
        ax.set_xlabel("Weekly H2-SAF coordination (Pearson r)", fontsize=11.5, fontweight="bold")
        ax.set_ylabel("Weekly SAF utilization (%)", fontsize=11.5, fontweight="bold")

    def _plot_mismatch_panel(self, ax: plt.Axes, frame: pd.DataFrame) -> None:
        comparable = frame.dropna(subset=["H2SAFMismatch", "H2SAFCorr"]).copy()
        comparable = comparable[comparable["H2Basis"] == "electrolyzer_capacity"]
        x_max = max(45.0, float(np.nanmax(comparable["H2SAFMismatch"])) + 4.0)

        ax.axvspan(0, 10, color="#EAF5EA", alpha=0.68, zorder=0)
        ax.axvspan(10, 20, color="#FFF7ED", alpha=0.60, zorder=0)
        ax.axvspan(20, x_max, color="#FCE8E6", alpha=0.60, zorder=0)

        for _, row in comparable.iterrows():
            marker = "^" if row["Pathway"] == "FT" else "o"
            ax.scatter(
                float(row["H2SAFMismatch"]),
                float(row["H2SAFCorr"]),
                s=125,
                marker=marker,
                color=row["Color"],
                edgecolors="white",
                linewidths=1.5,
                alpha=0.95,
                zorder=5,
            )

        for fit_group in ("Blue/Grey", "Green"):
            fit_frame = comparable[comparable["FitGroup"] == fit_group]
            fit = self._fit_line(fit_frame, "H2SAFMismatch", "H2SAFCorr")
            if fit is None:
                continue
            ax.plot(
                fit["x_fit"],
                np.clip(fit["y_fit"], 0, 1),
                color=self.FIT_COLORS[fit_group],
                linewidth=2.2,
                zorder=3,
            )

        self._annotate_points(ax, comparable, "H2SAFMismatch", "H2SAFCorr")

        grouped = comparable.groupby("FitGroup")[["H2SAFMismatch", "H2SAFCorr", "WorstWeekMean"]].mean()
        if {"Blue/Grey", "Green"}.issubset(grouped.index):
            bg = grouped.loc["Blue/Grey"]
            green = grouped.loc["Green"]
            summary_text = (
                f"Blue/Grey mean: mismatch={bg['H2SAFMismatch']:.1f} pp, corr={bg['H2SAFCorr']:.2f}\n"
                f"Green mean: mismatch={green['H2SAFMismatch']:.1f} pp, corr={green['H2SAFCorr']:.2f}\n"
                f"Worst-week gap: {green['WorstWeekMean'] - bg['WorstWeekMean']:+.1f} pp"
            )
            ax.text(
                0.03,
                0.97,
                summary_text,
                transform=ax.transAxes,
                ha="left",
                va="top",
                fontsize=8.5,
                bbox=dict(boxstyle="round,pad=0.35", facecolor="white", edgecolor="#D0D5DD", alpha=0.92),
            )

        ax.text(
            0.03,
            0.03,
            "Only pathways with explicit electrolyzer capacity are included.",
            transform=ax.transAxes,
            ha="left",
            va="bottom",
            fontsize=8.0,
            color="#555555",
        )
        ax.set_title("(c) Upstream-downstream mismatch mechanism", fontsize=13, fontweight="bold", loc="left", pad=10)
        ax.set_xlabel("Mean |H2 utilization - SAF utilization| (pp)", fontsize=11.5, fontweight="bold")
        ax.set_ylabel("H2-SAF temporal correlation", fontsize=11.5, fontweight="bold")
        self._style_axis_dynamic(ax, 0, x_max, 0, 1.02, 10, 0.2)

    @staticmethod
    def _summary_box(frame: pd.DataFrame, prefix: str) -> str:
        grouped = (
            frame.assign(FitGroup=np.where(frame["Category"] == "Green", "Green", "Blue/Grey"))
            .groupby("FitGroup")[[f"{prefix}Mean", f"{prefix}P10", f"{prefix}L70"]]
            .mean()
        )
        if "Blue/Grey" not in grouped.index or "Green" not in grouped.index:
            return ""

        bg = grouped.loc["Blue/Grey"]
        green = grouped.loc["Green"]
        exposure_ratio = np.nan
        if float(bg[f"{prefix}L70"]) > 1e-12:
            exposure_ratio = float(green[f"{prefix}L70"] / bg[f"{prefix}L70"])

        return (
            f"Blue/Grey mean: Mean={bg[f'{prefix}Mean']:.1f}%, P10={bg[f'{prefix}P10']:.1f}%, "
            f"L70={bg[f'{prefix}L70']:.1f}%\n"
            f"Green mean: Mean={green[f'{prefix}Mean']:.1f}%, P10={green[f'{prefix}P10']:.1f}%, "
            f"L70={green[f'{prefix}L70']:.1f}%\n"
            f"Gap: {green[f'{prefix}Mean'] - bg[f'{prefix}Mean']:+.1f} pp mean, "
            f"{green[f'{prefix}P10'] - bg[f'{prefix}P10']:+.1f} pp P10, "
            f"{exposure_ratio:.1f}x L70"
        )

    @staticmethod
    def _summary_box_alternative(frame: pd.DataFrame) -> Tuple[str, str]:
        grouped = (
            frame.assign(FitGroup=np.where(frame["Category"] == "Green", "Green", "Blue/Grey"))
            .groupby("FitGroup")[["SAFMean", "SAFR", "SAFH70", "SAFL70"]]
            .mean()
        )
        if "Blue/Grey" not in grouped.index or "Green" not in grouped.index:
            return "", ""

        bg = grouped.loc["Blue/Grey"]
        green = grouped.loc["Green"]

        box_a = (
            f"Blue/Grey mean: Mean={bg['SAFMean']:.1f}%, R={bg['SAFR']:.1f}%\n"
            f"Green mean: Mean={green['SAFMean']:.1f}%, R={green['SAFR']:.1f}%\n"
            f"Gap: {green['SAFMean'] - bg['SAFMean']:+.1f} pp mean, "
            f"{green['SAFR'] - bg['SAFR']:+.1f} pp R"
        )
        box_b = (
            f"Blue/Grey mean: Mean={bg['SAFMean']:.1f}%, H70={bg['SAFH70']:.1f}%\n"
            f"Green mean: Mean={green['SAFMean']:.1f}%, H70={green['SAFH70']:.1f}%\n"
            f"Gap: {green['SAFMean'] - bg['SAFMean']:+.1f} pp mean, "
            f"{green['SAFH70'] - bg['SAFH70']:+.1f} pp H70"
        )
        return box_a, box_b

    @staticmethod
    def _log_group_summary(frame: pd.DataFrame) -> None:
        summary = (
            frame.assign(FitGroup=np.where(frame["Category"] == "Green", "Green", "Blue/Grey"))
            .groupby("FitGroup")[["H2Mean", "H2P10", "H2L70", "SAFMean", "SAFP10", "SAFL70"]]
            .mean()
            .round(2)
        )
        logger.info("分组均值:\n%s", summary.to_string())

    def plot(self, frame: pd.DataFrame) -> Path:
        plt.rcParams["font.family"] = ["Times New Roman", "DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False

        fig, axes = plt.subplots(
            1,
            3,
            figsize=(21, 7.8),
            gridspec_kw={"width_ratios": [1.15, 1.05, 1.15]},
        )

        self._plot_space_panel(
            axes[0],
            frame,
            "SAFMean",
            "SAFP10",
            "(a) SAF robustness space",
            "Mean SAF utilization (%)",
            "P10 SAF utilization (%)",
            summary_text=self._summary_box(frame, "SAF"),
        )

        self._plot_space_panel(
            axes[1],
            frame.dropna(subset=["H2Mean", "H2P10"]),
            "H2Mean",
            "H2P10",
            "(b) H2 robustness space",
            "Mean H2 utilization (%)",
            "P10 H2 utilization (%)",
            summary_text=self._summary_box(frame.dropna(subset=["H2Mean", "H2P10"]), "H2"),
        )

        self._plot_lollipop_panel(axes[2], frame)

        category_handles = [
            Patch(facecolor=self.CATEGORY_COLORS[name], edgecolor="none", label=name)
            for name in ("Grey", "Blue", "Green")
        ]
        pathway_handles = [
            Line2D([0], [0], marker="o", color="w", markerfacecolor="#666666", markeredgecolor="white", markersize=9, label="MTJ / CTL"),
            Line2D([0], [0], marker="^", color="w", markerfacecolor="#666666", markeredgecolor="white", markersize=9, label="FT"),
        ]
        fit_handles = [
            Line2D([0], [0], color=self.FIT_COLORS["Blue/Grey"], linewidth=2.2, label="Blue/Grey fit"),
            Line2D([0], [0], color=self.FIT_COLORS["Green"], linewidth=2.2, label="Green fit"),
        ]

        fig.legend(
            handles=category_handles + pathway_handles + fit_handles,
            loc="upper center",
            bbox_to_anchor=(0.5, 1.02),
            ncol=7,
            frameon=False,
            fontsize=10,
            handlelength=2.2,
            columnspacing=1.5,
        )

        fig.suptitle(
            "Weekly operational robustness metrics across 13 SAF pathways",
            fontsize=15,
            fontweight="bold",
            y=1.06,
        )
        fig.text(
            0.5,
            0.01,
            "Metrics are computed from 224 three-hour periods (4 weeks). P10 captures the lower tail and L70 captures low-load exposure.",
            ha="center",
            va="bottom",
            fontsize=10,
            color="#555555",
        )

        fig.tight_layout(rect=[0.02, 0.06, 0.98, 0.95])

        output_path = self.session_dir / "temporal_robustness_space_preview.png"
        latest_path = self.output_dir / "temporal_robustness_space_latest.png"
        fig.savefig(output_path, dpi=600, bbox_inches="tight")
        fig.savefig(latest_path, dpi=600, bbox_inches="tight")
        plt.close(fig)

        logger.info("图已保存: %s", output_path)
        return output_path

    def plot_alternative(self, frame: pd.DataFrame) -> Path:
        plt.rcParams["font.family"] = ["Times New Roman", "DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False

        fig, axes = plt.subplots(
            1,
            3,
            figsize=(21, 7.8),
            gridspec_kw={"width_ratios": [1.1, 1.1, 1.15]},
        )

        summary_a, summary_b = self._summary_box_alternative(frame)

        self._plot_quadrant_space_panel(
            axes[0],
            frame,
            "SAFMean",
            "SAFR",
            "(a) SAF mean vs robustness ratio",
            "Mean SAF utilization (%)",
            "R = P10 / Mean (%)",
            x_threshold=70.0,
            y_threshold=70.0,
            summary_text=summary_a,
        )

        self._plot_quadrant_space_panel(
            axes[1],
            frame,
            "SAFMean",
            "SAFH70",
            "(b) SAF mean vs high-load share",
            "Mean SAF utilization (%)",
            "H70 = share of time with utilization >= 70% (%)",
            x_threshold=70.0,
            y_threshold=70.0,
            summary_text=summary_b,
        )

        self._plot_lollipop_panel(axes[2], frame)

        category_handles = [
            Patch(facecolor=self.CATEGORY_COLORS[name], edgecolor="none", label=name)
            for name in ("Grey", "Blue", "Green")
        ]
        pathway_handles = [
            Line2D([0], [0], marker="o", color="w", markerfacecolor="#666666", markeredgecolor="white", markersize=9, label="MTJ / CTL"),
            Line2D([0], [0], marker="^", color="w", markerfacecolor="#666666", markeredgecolor="white", markersize=9, label="FT"),
        ]
        fit_handles = [
            Line2D([0], [0], color=self.FIT_COLORS["Blue/Grey"], linewidth=2.2, label="Blue/Grey fit"),
            Line2D([0], [0], color=self.FIT_COLORS["Green"], linewidth=2.2, label="Green fit"),
        ]

        fig.legend(
            handles=category_handles + pathway_handles + fit_handles,
            loc="upper center",
            bbox_to_anchor=(0.5, 1.02),
            ncol=7,
            frameon=False,
            fontsize=10,
            handlelength=2.2,
            columnspacing=1.5,
        )

        fig.suptitle(
            "Alternative robustness view for 13 SAF pathways",
            fontsize=15,
            fontweight="bold",
            y=1.06,
        )
        fig.text(
            0.5,
            0.01,
            "R captures lower-tail retention and H70 captures the share of time that a pathway stays above 70% utilization.",
            ha="center",
            va="bottom",
            fontsize=10,
            color="#555555",
        )

        fig.tight_layout(rect=[0.02, 0.06, 0.98, 0.95])

        output_path = self.session_dir / "temporal_robustness_space_alternative_preview.png"
        latest_path = self.output_dir / "temporal_robustness_space_alternative_latest.png"
        fig.savefig(output_path, dpi=600, bbox_inches="tight")
        fig.savefig(latest_path, dpi=600, bbox_inches="tight")
        plt.close(fig)

        logger.info("替代图已保存: %s", output_path)
        return output_path

    def plot_operational_deployability(self, frame: pd.DataFrame) -> Path:
        plt.rcParams["font.family"] = ["Times New Roman", "DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False

        fig, axes = plt.subplots(
            1,
            3,
            figsize=(21.5, 7.8),
            gridspec_kw={"width_ratios": [1.15, 1.05, 1.15]},
        )

        self._plot_tradeoff_panel(axes[0], frame)
        self._plot_event_lollipop_panel(axes[1], frame)
        self._plot_weekly_scatter_panel(axes[2], frame)

        category_handles = [
            Patch(facecolor=self.CATEGORY_COLORS[name], edgecolor="none", label=name)
            for name in ("Grey", "Blue", "Green")
        ]
        pathway_handles = [
            Line2D([0], [0], marker="o", color="w", markerfacecolor="#666666", markeredgecolor="white", markersize=9, label="MTJ / CTL"),
            Line2D([0], [0], marker="^", color="w", markerfacecolor="#666666", markeredgecolor="white", markersize=9, label="FT"),
        ]
        fit_handles = [
            Line2D([0], [0], color=self.FIT_COLORS["Blue/Grey"], linewidth=2.2, label="Blue/Grey fit"),
            Line2D([0], [0], color=self.FIT_COLORS["Green"], linewidth=2.2, label="Green fit"),
        ]

        fig.legend(
            handles=category_handles + pathway_handles + fit_handles,
            loc="upper center",
            bbox_to_anchor=(0.5, 1.02),
            ncol=7,
            frameon=False,
            fontsize=10,
            handlelength=2.2,
            columnspacing=1.5,
        )

        fig.suptitle(
            "Operational deployability constraints across 13 SAF pathways",
            fontsize=15,
            fontweight="bold",
            y=1.06,
        )
        fig.text(
            0.5,
            0.01,
            "Worst-week mean captures minimum weekly deliverability; low-load events are defined as utilization below 70% for at least 6 hours; panel (c) plots one point per pathway-week.",
            ha="center",
            va="bottom",
            fontsize=10,
            color="#555555",
        )

        fig.tight_layout(rect=[0.02, 0.06, 0.98, 0.95])

        output_path = self.session_dir / "operational_deployability_preview.png"
        latest_path = self.output_dir / "operational_deployability_latest.png"
        fig.savefig(output_path, dpi=600, bbox_inches="tight")
        fig.savefig(latest_path, dpi=600, bbox_inches="tight")
        plt.close(fig)

        logger.info("运行可部署性图已保存: %s", output_path)
        return output_path

    def plot_worst_week_cost_impact(self, frame: pd.DataFrame) -> Path:
        plt.rcParams["font.family"] = ["Times New Roman", "DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False

        fig, ax = plt.subplots(1, 1, figsize=(10.2, 7.8))
        self._plot_worst_week_cost_uplift_panel(ax, frame)

        category_handles = [
            Patch(facecolor=self.CATEGORY_COLORS[name], edgecolor="none", label=name)
            for name in ("Grey", "Blue", "Green")
        ]
        pathway_handles = [
            Line2D([0], [0], marker="o", color="w", markerfacecolor="#666666", markeredgecolor="white", markersize=9, label="MTJ / CTL"),
            Line2D([0], [0], marker="^", color="w", markerfacecolor="#666666", markeredgecolor="white", markersize=9, label="FT"),
        ]
        fit_handles = [
            Line2D([0], [0], color="#111111", linewidth=2.3, linestyle="--", label="Global fit"),
        ]

        fig.legend(
            handles=category_handles + pathway_handles + fit_handles,
            loc="upper center",
            bbox_to_anchor=(0.5, 1.02),
            ncol=6,
            frameon=False,
            fontsize=10,
            handlelength=2.2,
            columnspacing=1.4,
        )

        fig.suptitle(
            "Worst-week utilization as a cost-uplift penalty across 13 SAF pathways",
            fontsize=15,
            fontweight="bold",
            y=1.05,
        )
        fig.text(
            0.5,
            0.01,
            "The uplift proxy converts worst-week under-utilization into an implied increase in average unit cost; larger values indicate a stronger throughput-dilution penalty.",
            ha="center",
            va="bottom",
            fontsize=10,
            color="#555555",
        )

        fig.tight_layout(rect=[0.02, 0.06, 0.98, 0.95])

        output_path = self.session_dir / "worst_week_cost_impact_preview.png"
        latest_path = self.output_dir / "worst_week_cost_impact_latest.png"
        fig.savefig(output_path, dpi=600, bbox_inches="tight")
        fig.savefig(latest_path, dpi=600, bbox_inches="tight")
        plt.close(fig)

        logger.info("最差周成本抬升图已保存: %s", output_path)
        return output_path

    def plot_cost_penalty_breakdown(self, frame: pd.DataFrame) -> Path:
        plt.rcParams["font.family"] = ["Times New Roman", "DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False

        fig, ax = plt.subplots(1, 1, figsize=(10.2, 8.2))
        self._plot_cost_penalty_space_panel(ax, frame)

        category_handles = [
            Patch(facecolor=self.CATEGORY_COLORS[name], edgecolor="none", label=name)
            for name in ("Grey", "Blue", "Green")
        ]
        size_values = [40.0, 80.0, 120.0]
        total_min = float(np.nanmin(frame["TotalPenaltyPct"]))
        total_max = float(np.nanmax(frame["TotalPenaltyPct"]))
        size_handles = []
        for value in size_values:
            if total_max - total_min <= 1e-12:
                bubble_area = 520.0
            else:
                clipped = min(max(value, total_min), total_max)
                bubble_norm = (clipped - total_min) / (total_max - total_min)
                bubble_area = 90.0 + bubble_norm**1.35 * 1800.0
            size_handles.append(
                plt.scatter([], [], s=bubble_area, color="#9AA4B2", alpha=0.65, edgecolors="none", linewidths=0.0, label=f"Total penalty {int(value)}%")
            )

        fig.legend(
            handles=category_handles + size_handles,
            loc="upper center",
            bbox_to_anchor=(0.5, 1.02),
            ncol=3,
            frameon=False,
            fontsize=10,
            handlelength=2.2,
            columnspacing=1.4,
        )

        fig.suptitle(
            "Cost penalty space from low utilization and temporal fragility",
            fontsize=15,
            fontweight="bold",
            y=1.05,
        )
        fig.text(
            0.5,
            0.01,
            "Bubble area scales with total penalty. Chronic penalty = (100 / Mean SAF utilization - 1) x 100%; instability penalty = (100 / Worst-week SAF utilization - 100 / Mean SAF utilization) x 100%.",
            ha="center",
            va="bottom",
            fontsize=10,
            color="#555555",
        )

        fig.tight_layout(rect=[0.02, 0.06, 0.98, 0.95])

        output_path = self.session_dir / "cost_penalty_breakdown_preview.png"
        latest_path = self.output_dir / "cost_penalty_breakdown_latest.png"
        fig.savefig(output_path, dpi=600, bbox_inches="tight")
        fig.savefig(latest_path, dpi=600, bbox_inches="tight")
        plt.close(fig)

        logger.info("成本惩罚分解图已保存: %s", output_path)
        return output_path

    def plot_coordination_utilization(self, frame: pd.DataFrame) -> Path:
        plt.rcParams["font.family"] = ["Times New Roman", "DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False

        fig, ax = plt.subplots(1, 1, figsize=(10.4, 8.2))
        self._plot_coordination_effect_panel(
            ax=ax,
            frame=frame,
            y_col="SAFMean",
            y_label="Mean SAF utilization (%)",
            title="H2-SAF coordination effect on utilization",
            summary_key="utilization",
            y_threshold=75.0,
        )

        category_handles = [
            Patch(facecolor=self.CATEGORY_COLORS[name], edgecolor="none", label=name)
            for name in ("Grey", "Blue", "Green")
        ]

        fig.legend(
            handles=category_handles,
            loc="upper center",
            bbox_to_anchor=(0.5, 1.02),
            ncol=3,
            frameon=False,
            fontsize=10,
            handlelength=2.2,
            columnspacing=1.4,
        )

        fig.suptitle(
            "Influence of H2-SAF coordination on utilization",
            fontsize=15,
            fontweight="bold",
            y=1.05,
        )
        fig.text(
            0.5,
            0.01,
            "One point per pathway. Higher values indicate that stronger weekly H2-SAF coordination is associated with higher average SAF utilization.",
            ha="center",
            va="bottom",
            fontsize=10,
            color="#555555",
        )

        fig.tight_layout(rect=[0.02, 0.06, 0.98, 0.95])

        output_path = self.session_dir / "coordination_utilization_preview.png"
        latest_path = self.output_dir / "coordination_utilization_latest.png"
        fig.savefig(output_path, dpi=600, bbox_inches="tight")
        fig.savefig(latest_path, dpi=600, bbox_inches="tight")
        plt.close(fig)

        logger.info("协同性-利用率图已保存: %s", output_path)
        return output_path

    def plot_coordination_robustness(self, frame: pd.DataFrame) -> Path:
        plt.rcParams["font.family"] = ["Times New Roman", "DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False

        fig, ax = plt.subplots(1, 1, figsize=(10.4, 8.2))
        self._plot_coordination_effect_panel(
            ax=ax,
            frame=frame,
            y_col="WorstWeekRetention",
            y_label="Worst-week retention (%)",
            title="H2-SAF coordination effect on robustness",
            summary_key="retention",
            y_threshold=80.0,
        )

        category_handles = [
            Patch(facecolor=self.CATEGORY_COLORS[name], edgecolor="none", label=name)
            for name in ("Grey", "Blue", "Green")
        ]

        fig.legend(
            handles=category_handles,
            loc="upper center",
            bbox_to_anchor=(0.5, 1.02),
            ncol=3,
            frameon=False,
            fontsize=10,
            handlelength=2.2,
            columnspacing=1.4,
        )

        fig.suptitle(
            "Influence of H2-SAF coordination on robustness",
            fontsize=15,
            fontweight="bold",
            y=1.05,
        )
        fig.text(
            0.5,
            0.01,
            "One point per pathway. Robustness is measured as worst-week retention = worst-week SAF utilization / mean SAF utilization.",
            ha="center",
            va="bottom",
            fontsize=10,
            color="#555555",
        )

        fig.tight_layout(rect=[0.02, 0.06, 0.98, 0.95])

        output_path = self.session_dir / "coordination_robustness_preview.png"
        latest_path = self.output_dir / "coordination_robustness_latest.png"
        fig.savefig(output_path, dpi=600, bbox_inches="tight")
        fig.savefig(latest_path, dpi=600, bbox_inches="tight")
        plt.close(fig)

        logger.info("协同性-稳健性图已保存: %s", output_path)
        return output_path

    def plot_driver_mechanism_screening(self, frame: pd.DataFrame) -> Path:
        plt.rcParams["font.family"] = ["Times New Roman", "DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False

        fig, ax = plt.subplots(1, 1, figsize=(13.2, 6.6))
        self._plot_driver_mechanism_heatmap(ax, frame)

        fig.suptitle(
            "Screening the main drivers behind utilization, robustness, and cost penalty",
            fontsize=15,
            fontweight="bold",
            y=1.03,
        )
        fig.text(
            0.5,
            0.01,
            "Correlations are computed from the latest pathway-level metrics table. Positive values indicate that the driver increases the outcome; negative values indicate the opposite.",
            ha="center",
            va="bottom",
            fontsize=10,
            color="#555555",
        )

        fig.tight_layout(rect=[0.02, 0.06, 0.98, 0.93])

        output_path = self.session_dir / "driver_mechanism_screening_preview.png"
        latest_path = self.output_dir / "driver_mechanism_screening_latest.png"
        fig.savefig(output_path, dpi=600, bbox_inches="tight")
        fig.savefig(latest_path, dpi=600, bbox_inches="tight")
        plt.close(fig)

        logger.info("根源筛查热图已保存: %s", output_path)
        return output_path

    def plot_penalty_class_mechanism_screening(self, frame: pd.DataFrame) -> Path:
        plt.rcParams["font.family"] = ["Times New Roman", "DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False

        weekly_frame = self._build_class_weekly_table(frame)
        weekly_csv = self.session_dir / "penalty_class_weekly_metrics.csv"
        weekly_frame.to_csv(weekly_csv, index=False, encoding="utf-8-sig")
        weekly_frame.to_csv(self.output_dir / "penalty_class_weekly_metrics_latest.csv", index=False, encoding="utf-8-sig")

        class_order = ["Low-penalty", "Instability-dominant", "Low-utilization-dominant"]
        fig = plt.figure(figsize=(13.0, 8.4))
        grid = fig.add_gridspec(4, 2, width_ratios=[24, 1.25], height_ratios=[0.28, 1, 1, 1], wspace=0.14, hspace=0.0)
        header_ax = fig.add_subplot(grid[0, 0])
        axes = [fig.add_subplot(grid[i, 0]) for i in range(1, 4)]
        cax = fig.add_subplot(grid[:, 1])
        self._plot_penalty_class_header_band(header_ax)
        im = None
        for idx, (ax, class_name) in enumerate(zip(axes, class_order)):
            im = self._plot_penalty_class_mechanism_panel(
                ax,
                weekly_frame,
                class_name,
                show_xlabels=(idx == len(class_order) - 1),
                show_class_label=False,
            )

        fig.suptitle(
            "Within-class driver screening after penalty-space classification",
            fontsize=14.5,
            fontweight="bold",
            y=0.985,
        )
        fig.text(
            0.5,
            0.028,
            "Classes are defined from the penalty space: total penalty < 50% = low-penalty; otherwise instability-dominant if instability penalty > chronic penalty, else low-utilization-dominant. Correlations use weekly observations within each class.",
            ha="center",
            va="bottom",
            fontsize=8.8,
            color="#555555",
        )

        if im is not None:
            cbar = fig.colorbar(im, cax=cax)
            cbar.set_label("Pearson correlation", fontsize=9.5)
            cbar.ax.tick_params(labelsize=8.6)

        fig.subplots_adjust(left=0.19, right=0.93, top=0.90, bottom=0.10)

        fig.canvas.draw()
        header_bbox = header_ax.get_position()
        for idx, (ax, class_name) in enumerate(zip(axes, class_order)):
            border_color = self.PENALTY_CLASS_COLORS.get(class_name, self.PENALTY_CLASS_COLORS["Unclassified"])
            heat_bbox = ax.get_position()
            class_subset = weekly_frame[weekly_frame["PenaltyClass"] == class_name]
            if idx == 0:
                x0 = min(header_bbox.x0, heat_bbox.x0)
                y0 = min(header_bbox.y0, heat_bbox.y0)
                x1 = max(header_bbox.x1, heat_bbox.x1)
                y1 = max(header_bbox.y1, heat_bbox.y1)
            else:
                x0, y0, x1, y1 = heat_bbox.x0, heat_bbox.y0, heat_bbox.x1, heat_bbox.y1

            fig.add_artist(
                Rectangle(
                    (x0, y0),
                    x1 - x0,
                    y1 - y0,
                    transform=fig.transFigure,
                    fill=False,
                    edgecolor=border_color,
                    linewidth=2.2,
                    zorder=10,
                )
            )

            fig.text(
                x0 - 0.022,
                (y0 + y1) / 2,
                f"{class_name}\n{class_subset['Scenario'].nunique()} pathways / {len(class_subset)} week-points",
                ha="right",
                va="center",
                fontsize=11.2,
                fontweight="bold",
                color=border_color,
                bbox=dict(boxstyle="round,pad=0.28", facecolor="white", edgecolor=border_color, linewidth=1.5),
                transform=fig.transFigure,
            )

        output_path = self.session_dir / "penalty_class_driver_screening_preview.png"
        latest_path = self.output_dir / "penalty_class_driver_screening_latest.png"
        fig.savefig(output_path, dpi=600, bbox_inches="tight")
        fig.savefig(latest_path, dpi=600, bbox_inches="tight")
        plt.close(fig)

        logger.info("分型后根源筛查图已保存: %s", output_path)
        return output_path


def main() -> None:
    visualizer = TemporalRobustnessSpaceVisualizer()
    metric_table = visualizer.build_metric_table()
    visualizer.plot(metric_table)
    visualizer.plot_alternative(metric_table)
    visualizer.plot_operational_deployability(metric_table)
    visualizer.plot_worst_week_cost_impact(metric_table)
    visualizer.plot_cost_penalty_breakdown(metric_table)
    visualizer.plot_coordination_utilization(metric_table)
    visualizer.plot_coordination_robustness(metric_table)
    visualizer.plot_driver_mechanism_screening(metric_table)
    visualizer.plot_penalty_class_mechanism_screening(metric_table)


if __name__ == "__main__":
    main()
