# -*- coding: utf-8 -*-
"""
三个帕累托最优方案的 H2/SAF 利用率镜像分布图

设计说明：
- 复用 temporal_efficiency_visualization.py 中的利用率计算口径
- 复用 pareto_three_breakdown_visualization.py 中的帕累托识别逻辑
- 仅输出 3 个代表性帕累托最优方案的镜像分布图
- 左侧为 H2 utilization distribution，右侧为 SAF utilization distribution
"""

import glob
import json
import logging
import os
import shutil
from collections import OrderedDict as OD
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

MPL_CONFIG_DIR = Path("/tmp") / f"matplotlib-cache-{os.getuid()}"
MPL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
os.environ["MPLCONFIGDIR"] = str(MPL_CONFIG_DIR)

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)
logging.getLogger("fontTools").setLevel(logging.WARNING)


PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


def setup_fonts():
    """Set Times New Roman-style fonts and vector embedding options."""
    plt.rcParams["font.family"] = ["serif"]
    plt.rcParams["font.serif"] = ["Times New Roman", "DejaVu Serif", "SimSun"]
    plt.rcParams["font.sans-serif"] = ["Times New Roman", "DejaVu Serif", "SimSun"]
    plt.rcParams["font.size"] = 9.2
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["pdf.fonttype"] = 42
    plt.rcParams["ps.fonttype"] = 42
    plt.rcParams["mathtext.fontset"] = "stix"


class ParetoTemporalDistributionVisualizer:
    """仅针对三个帕累托最优方案绘制镜像分布图。"""

    FIGURE_FONT_SIZE = 12.0

    PARETO_SCENARIOS = OD([
        ("CTL", {
            "category": "Grey",
            "pathway": "Two-Step",
            "color": "#616161",
            "solution_pattern": str(PROJECT_ROOT / "products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/complete_solution_*.json"),
            "hourly_pattern": str(PROJECT_ROOT / "products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/hourly_production_summary_*.csv"),
            "carbon_pattern": str(PROJECT_ROOT / "products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/carbon_emissions_detailed_*.json"),
        }),
        ("CTL-BH", {
            "category": "Grey",
            "pathway": "Two-Step",
            "color": "#9E9E9E",
            "solution_pattern": str(PROJECT_ROOT / "products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/byproduct_hydrogen/complete_solution_*.json"),
            "hourly_pattern": str(PROJECT_ROOT / "products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/byproduct_hydrogen/hourly_production_summary_*.csv"),
            "carbon_pattern": str(PROJECT_ROOT / "products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/byproduct_hydrogen/carbon_emissions_detailed_*.json"),
        }),
        ("CCU-BH-MTJ", {
            "category": "Blue",
            "pathway": "Two-Step",
            "color": "#0D47A1",
            "solution_pattern": str(PROJECT_ROOT / "products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/two_step/complete_solution_*.json"),
            "hourly_pattern": str(PROJECT_ROOT / "products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/two_step/hourly_production_summary_*.csv"),
            "carbon_pattern": str(PROJECT_ROOT / "products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/two_step/carbon_emissions_detailed_*.json"),
        }),
        ("CCU-BH-FT", {
            "category": "Blue",
            "pathway": "One-Step",
            "color": "#1565C0",
            "solution_pattern": str(PROJECT_ROOT / "products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/one_step/complete_solution_*.json"),
            "hourly_pattern": str(PROJECT_ROOT / "products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/one_step/hourly_production_summary_*.csv"),
            "carbon_pattern": str(PROJECT_ROOT / "products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/one_step/carbon_emissions_detailed_*.json"),
        }),
        ("DAC-BH-MTJ", {
            "category": "Blue",
            "pathway": "Two-Step",
            "color": "#1E88E5",
            "solution_pattern": str(PROJECT_ROOT / "products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/two_step/complete_solution_*.json"),
            "hourly_pattern": str(PROJECT_ROOT / "products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/two_step/hourly_production_summary_*.csv"),
            "carbon_pattern": str(PROJECT_ROOT / "products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/two_step/carbon_emissions_detailed_*.json"),
        }),
        ("DAC-BH-FT", {
            "category": "Blue",
            "pathway": "One-Step",
            "color": "#42A5F5",
            "solution_pattern": str(PROJECT_ROOT / "products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/one_step/complete_solution_*.json"),
            "hourly_pattern": str(PROJECT_ROOT / "products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/one_step/hourly_production_summary_*.csv"),
            "carbon_pattern": str(PROJECT_ROOT / "products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/one_step/carbon_emissions_detailed_*.json"),
        }),
        ("GTL-BH", {
            "category": "Blue",
            "pathway": "Two-Step",
            "color": "#1976D2",
            "solution_pattern": str(PROJECT_ROOT / "products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/byproduct_hydrogen/byproduct_hydrogen/two_step/complete_solution_*.json"),
            "hourly_pattern": str(PROJECT_ROOT / "products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/byproduct_hydrogen/byproduct_hydrogen/two_step/hourly_production_summary_*.csv"),
            "carbon_pattern": str(PROJECT_ROOT / "products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/byproduct_hydrogen/byproduct_hydrogen/two_step/carbon_emissions_detailed_*.json"),
        }),
        ("GTL-GH", {
            "category": "Blue",
            "pathway": "Two-Step",
            "color": "#64B5F6",
            "solution_pattern": str(PROJECT_ROOT / "products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/complete_solution_*.json"),
            "hourly_pattern": str(PROJECT_ROOT / "products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/hourly_production_summary_*.csv"),
            "carbon_pattern": str(PROJECT_ROOT / "products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/carbon_emissions_detailed_*.json"),
        }),
        ("GTL", {
            "category": "Blue",
            "pathway": "One-Step",
            "color": "#90CAF9",
            "solution_pattern": str(PROJECT_ROOT / "products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/ft_one_step/complete_solution_*.json"),
            "hourly_pattern": str(PROJECT_ROOT / "products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/ft_one_step/hourly_production_summary_*.csv"),
            "carbon_pattern": str(PROJECT_ROOT / "products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/ft_one_step/carbon_emissions_detailed_*.json"),
        }),
        ("DAC-GH-MTJ", {
            "category": "Green",
            "pathway": "Two-Step",
            "color": "#1B5E20",
            "solution_pattern": str(PROJECT_ROOT / "products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/two_step/complete_solution_*.json"),
            "hourly_pattern": str(PROJECT_ROOT / "products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/two_step/hourly_production_summary_*.csv"),
            "carbon_pattern": str(PROJECT_ROOT / "products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/two_step/carbon_emissions_detailed_*.json"),
        }),
        ("DAC-GH-FT", {
            "category": "Green",
            "pathway": "One-Step",
            "color": "#2E7D32",
            "solution_pattern": str(PROJECT_ROOT / "products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/one_step/complete_solution_*.json"),
            "hourly_pattern": str(PROJECT_ROOT / "products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/one_step/hourly_production_summary_*.csv"),
            "carbon_pattern": str(PROJECT_ROOT / "products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/one_step/carbon_emissions_detailed_*.json"),
        }),
        ("CCU-GH-MTJ", {
            "category": "Green",
            "pathway": "Two-Step",
            "color": "#388E3C",
            "solution_pattern": str(PROJECT_ROOT / "products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/two_step/complete_solution_*.json"),
            "hourly_pattern": str(PROJECT_ROOT / "products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/two_step/hourly_production_summary_*.csv"),
            "carbon_pattern": str(PROJECT_ROOT / "products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/two_step/carbon_emissions_detailed_*.json"),
        }),
        ("CCU-GH-FT", {
            "category": "Green",
            "pathway": "One-Step",
            "color": "#4CAF50",
            "solution_pattern": str(PROJECT_ROOT / "products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/one_step/complete_solution_*.json"),
            "hourly_pattern": str(PROJECT_ROOT / "products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/one_step/hourly_production_summary_*.csv"),
            "carbon_pattern": str(PROJECT_ROOT / "products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/one_step/carbon_emissions_detailed_*.json"),
        }),
    ])

    def __init__(self, output_dir: Optional[str] = None):
        if output_dir is None:
            output_dir = PROJECT_ROOT / "products" / "supply_chain_optimization" / "visualization" / "results"

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = self.output_dir / f"pareto_temporal_distribution_{timestamp}"
        self.session_dir.mkdir(parents=True, exist_ok=True)

        self.data: Dict[str, Dict] = {}
        self.pareto_screening_data: Dict[str, Dict] = {}
        self.selected_pareto: List[str] = []

        setup_fonts()
        logger.info("输出目录: %s", self.session_dir)

    @staticmethod
    def _find_latest_file(pattern: str) -> Optional[Path]:
        files = sorted(glob.glob(pattern), reverse=True)
        return Path(files[0]) if files else None

    @staticmethod
    def _safe_float(value) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _extract_carbon_diff(self, carbon_data: Dict) -> float:
        carbon_diff = carbon_data.get("abs_diff_vs_traditional_jet_gco2e_per_mj")
        if carbon_diff is not None:
            return self._safe_float(carbon_diff)

        traditional_jet_ci = self._safe_float(carbon_data.get("traditional_jet_ci_gco2e_per_mj", 89))
        if "carbon_intensity_mj" in carbon_data:
            return self._safe_float(carbon_data.get("carbon_intensity_mj")) - traditional_jet_ci

        return traditional_jet_ci * self._safe_float(carbon_data.get("vs_traditional_jet")) / 100.0

    def load_pareto_screening_data(self):
        """加载用于识别帕累托最优的成本与碳排数据。"""
        self.pareto_screening_data = {}
        for scenario_label, config in self.PARETO_SCENARIOS.items():
            solution_path = self._find_latest_file(config["solution_pattern"])
            carbon_path = self._find_latest_file(config["carbon_pattern"])
            if solution_path is None or carbon_path is None:
                logger.warning("跳过 %s，缺少成本/碳排结果文件", scenario_label)
                continue

            with open(solution_path, "r", encoding="utf-8") as file:
                solution_data = json.load(file)
            with open(carbon_path, "r", encoding="utf-8") as file:
                carbon_data = json.load(file)

            self.pareto_screening_data[scenario_label] = {
                "lcoe": self._safe_float(solution_data.get("lifecycle_levelized_cost_excluding_shortage_per_kg")),
                "carbon_diff": self._extract_carbon_diff(carbon_data),
            }

    @staticmethod
    def _identify_pareto_frontier(data: Dict[str, Dict]) -> List[str]:
        sorted_items = sorted(
            data.items(),
            key=lambda item: (item[1]["carbon_diff"], item[1]["lcoe"]),
        )

        pareto_labels: List[str] = []
        best_cost = float("inf")
        for label, scenario in sorted_items:
            current_cost = float(scenario["lcoe"])
            if current_cost < best_cost - 1e-9:
                pareto_labels.append(label)
                best_cost = current_cost
        return pareto_labels

    @staticmethod
    def _select_three_representative_pareto(pareto_labels: List[str], data: Dict[str, Dict]) -> List[str]:
        ordered = sorted(pareto_labels, key=lambda label: data[label]["carbon_diff"])
        if len(ordered) <= 3:
            return ordered

        middle_index = len(ordered) // 2
        selected = [ordered[0], ordered[middle_index], ordered[-1]]

        unique_selected: List[str] = []
        for label in selected:
            if label not in unique_selected:
                unique_selected.append(label)
        return unique_selected

    def identify_selected_pareto(self):
        self.load_pareto_screening_data()
        pareto_labels = self._identify_pareto_frontier(self.pareto_screening_data)
        selected = self._select_three_representative_pareto(pareto_labels, self.pareto_screening_data)

        # 图里按“低成本 -> 过渡 -> 深减排”的阅读顺序排列，更接近论文叙述
        self.selected_pareto = sorted(
            selected,
            key=lambda label: self.pareto_screening_data[label]["lcoe"],
        )

        logger.info("帕累托前沿场景: %s", ", ".join(pareto_labels))
        logger.info("用于绘图的 3 个场景: %s", ", ".join(self.selected_pareto))

    @staticmethod
    def _kde_1d(samples: np.ndarray, grid: np.ndarray) -> np.ndarray:
        samples = np.asarray(samples, dtype=float)
        samples = samples[np.isfinite(samples)]
        n = samples.size
        if n < 2:
            return np.zeros_like(grid)

        std = samples.std(ddof=1)
        if std <= 0:
            return np.zeros_like(grid)

        bw = 1.06 * std * (n ** (-1 / 5))
        if not np.isfinite(bw) or bw <= 0:
            bw = max(std, 1e-3)

        diff = (grid[:, None] - samples[None, :]) / bw
        density = np.exp(-0.5 * diff ** 2).sum(axis=1) / (n * bw * np.sqrt(2 * np.pi))
        return density

    @staticmethod
    def _sum_saf_capacity(facilities: dict) -> float:
        total = 0.0
        for info in facilities.values():
            tech = str(info.get("technology", "")).strip().lower()
            mode = str(info.get("transport_mode", "")).strip().lower()
            if tech == "electrolyzer" or mode == "hydrogen_pipeline":
                continue

            try:
                total += float(info.get("capacity_kg_per_hour", 0))
            except (TypeError, ValueError):
                continue
        return total

    def compute_hourly_metrics(
        self,
        solution_data: dict,
        hourly_df: Optional[pd.DataFrame],
        scenario_name: str,
        config: dict,
    ) -> List[dict]:
        h2_facilities = solution_data.get("hydrogen_facilities", {})
        total_h2_cap = sum(
            facility.get("capacity_kg_h2_per_hour", 0)
            for facility in h2_facilities.values()
        )
        if total_h2_cap < 1e-6:
            total_h2_cap = 0.0

        total_saf_cap = self._sum_saf_capacity(solution_data.get("facilities", {}))
        hourly_metrics = []

        if hourly_df is None or hourly_df.empty:
            return hourly_metrics

        h2_col = None
        saf_col = None
        period_col = None
        length_col = None
        for col in hourly_df.columns:
            clean = col.strip().lstrip("\ufeff")
            if clean == "时段" or clean.lower() == "period":
                period_col = col
            if "时段长度" in clean or "period_length" in clean.lower():
                length_col = col
            if "氢气产出" in clean or "hydrogen" in clean.lower():
                h2_col = col
            if "SAF产出" in clean or "saf" in clean.lower():
                saf_col = col

        if period_col is None:
            period_col = hourly_df.columns[0]

        periods_per_week = 56

        if total_h2_cap <= 0 and h2_col is not None:
            h2_hourly_series = []
            for _, row in hourly_df.iterrows():
                try:
                    period = int(row[period_col])
                except Exception:
                    continue
                week = period // periods_per_week
                if week >= 4:
                    continue
                h2_prod = float(row[h2_col]) if pd.notna(row[h2_col]) else 0.0
                hours_per_period = float(row[length_col]) if length_col and pd.notna(row[length_col]) else 3.0
                if hours_per_period <= 0:
                    hours_per_period = 3.0
                h2_hourly_series.append(h2_prod / hours_per_period)
            if h2_hourly_series:
                total_h2_cap = max(h2_hourly_series)

        for _, row in hourly_df.iterrows():
            try:
                period = int(row[period_col])
            except Exception:
                continue

            week = period // periods_per_week
            if week >= 4:
                continue

            h2_prod = float(row[h2_col]) if h2_col and pd.notna(row[h2_col]) else 0.0
            saf_prod = float(row[saf_col]) if saf_col and pd.notna(row[saf_col]) else 0.0
            hours_per_period = float(row[length_col]) if length_col and pd.notna(row[length_col]) else 3.0
            if hours_per_period <= 0:
                hours_per_period = 3.0

            h2_hourly = h2_prod / hours_per_period
            saf_hourly = saf_prod / hours_per_period
            h2_util = h2_hourly / total_h2_cap if total_h2_cap > 0 else np.nan
            saf_util = saf_hourly / total_saf_cap if total_saf_cap > 0 else 0.0
            h2_util = min(h2_util, 1.0) if np.isfinite(h2_util) else np.nan
            saf_util = min(saf_util, 1.0) if np.isfinite(saf_util) else np.nan

            hourly_metrics.append({
                "period": period,
                "week": week,
                "h2_production_kg": h2_prod,
                "saf_production_kg": saf_prod,
                "h2_capacity_kg_per_hour": total_h2_cap,
                "saf_capacity_kg_per_hour": total_saf_cap,
                "h2_utilization": h2_util,
                "saf_utilization": saf_util,
                "scenario": scenario_name,
                "category": config["category"],
                "pathway": config["pathway"],
            })

        return hourly_metrics

    def load_selected_temporal_data(self):
        self.data = {}
        for scenario_label in self.selected_pareto:
            config = self.PARETO_SCENARIOS.get(scenario_label)
            if config is None:
                logger.warning("跳过 %s，未找到时序配置", scenario_label)
                continue

            solution_path = self._find_latest_file(config["solution_pattern"])
            hourly_path = self._find_latest_file(config["hourly_pattern"])
            if solution_path is None or hourly_path is None:
                logger.warning("跳过 %s，缺少 complete_solution 或 hourly summary", scenario_label)
                continue

            with open(solution_path, "r", encoding="utf-8") as file:
                solution_data = json.load(file)
            hourly_df = pd.read_csv(hourly_path)

            hourly_metrics = self.compute_hourly_metrics(
                solution_data=solution_data,
                hourly_df=hourly_df,
                scenario_name=scenario_label,
                config=config,
            )
            if not hourly_metrics:
                logger.warning("跳过 %s，未计算出有效时段利用率", scenario_label)
                continue

            self.data[scenario_label] = {
                "config": config,
                "solution": solution_data,
                "hourly_metrics": hourly_metrics,
            }

            logger.info(
                "%s | 成功加载 %d 个 3 小时时段",
                scenario_label,
                len(hourly_metrics),
            )

    def _build_distribution_payload(self) -> List[Dict]:
        payload: List[Dict] = []
        for scenario_label in self.selected_pareto:
            scenario_data = self.data.get(scenario_label)
            if not scenario_data:
                continue

            metrics_df = pd.DataFrame(scenario_data["hourly_metrics"])
            if metrics_df.empty:
                continue

            h2_values = metrics_df["h2_utilization"].astype(float).clip(0, 1).dropna().values
            saf_values = metrics_df["saf_utilization"].astype(float).clip(0, 1).dropna().values
            config = scenario_data["config"]
            screening = self.pareto_screening_data.get(scenario_label, {})
            payload.append({
                "label": scenario_label,
                "category": config["category"],
                "pathway": config["pathway"],
                "color": config["color"],
                "lcoe": screening.get("lcoe", np.nan),
                "carbon_diff": screening.get("carbon_diff", np.nan),
                "h2": h2_values,
                "saf": saf_values,
            })

        return payload

    @staticmethod
    def _distribution_stats(values: np.ndarray) -> Dict[str, float]:
        clean = pd.Series(values, dtype=float).replace([np.inf, -np.inf], np.nan).dropna()
        if clean.empty:
            return {
                "n": 0,
                "mean": np.nan,
                "median": np.nan,
                "skew": np.nan,
                "kurt": np.nan,
            }
        return {
            "n": int(clean.size),
            "mean": float(clean.mean()) * 100.0,
            "median": float(clean.median()) * 100.0,
            "skew": float(clean.skew()) if clean.size >= 3 else np.nan,
            "kurt": float(clean.kurt()) if clean.size >= 4 else np.nan,
        }

    @staticmethod
    def _save_figure_bundle(fig: plt.Figure, session_path: Path, latest_path: Path) -> None:
        for suffix in (".png", ".pdf", ".svg"):
            current_session_path = session_path.with_suffix(suffix)
            current_latest_path = latest_path.with_suffix(suffix)
            fig.savefig(current_session_path, dpi=600, bbox_inches="tight", pad_inches=0.035)
            shutil.copy2(current_session_path, current_latest_path)

    @staticmethod
    def _marker_label_position(
        scenario_label: str,
        sign: float,
        statistic: str,
        default_dy: float,
    ) -> Dict[str, object]:
        layout = {
            "dx": -0.035 * sign,
            "dy": default_dy,
            "ha": "left" if sign < 0 else "right",
            "va": "center",
        }

        # The bottom CCU-GH-FT row has clustered markers, so place labels
        # directly around their own points instead of using the global rule.
        if scenario_label == "CCU-GH-FT" and sign < 0 and statistic == "mean":
            layout.update({"dx": -0.055, "dy": 0.000, "ha": "right", "va": "center"})
        elif scenario_label == "CCU-GH-FT" and sign < 0 and statistic == "median":
            layout.update({"dx": 0.000, "dy": 0.125, "ha": "center", "va": "bottom"})
        elif scenario_label == "CCU-GH-FT" and sign > 0 and statistic == "median":
            layout.update({"dx": 0.055, "dy": 0.105, "ha": "left", "va": "bottom"})

        return layout

    @classmethod
    def _annotate_marker_label(
        cls,
        ax,
        x_value: float,
        y_value: float,
        sign: float,
        scenario_label: str,
        statistic: str,
        label: str,
        default_dy: float,
    ):
        layout = cls._marker_label_position(scenario_label, sign, statistic, default_dy)
        ax.text(
            x_value + float(layout["dx"]),
            y_value + float(layout["dy"]),
            label,
            ha=str(layout["ha"]),
            va=str(layout["va"]),
            fontsize=cls.FIGURE_FONT_SIZE,
            color="black",
            zorder=8,
            clip_on=False,
        )

    def _create_distribution_figure(self, payload: List[Dict], *, stem: str):
        h2_bg = "#EEF3F7"
        saf_bg = "#F8F1E8"
        grid = np.linspace(0, 1.0, 240)
        ridge_height = 0.64
        y_positions = np.arange(len(payload), 0, -1)

        fig, ax = plt.subplots(figsize=(4.8, 7.4))
        ax.axvspan(-1.0, 0, color=h2_bg, alpha=0.42, zorder=0, linewidth=0)
        ax.axvspan(0, 1.0, color=saf_bg, alpha=0.36, zorder=0, linewidth=0)
        ax.axvline(0, color="#64748B", linestyle="--", linewidth=0.95, zorder=1)

        for x in (-0.5, 0.5):
            ax.axvline(x, color="#CBD5E1", linestyle="--", linewidth=0.7, alpha=0.60, zorder=1)

        for y, row in zip(y_positions, payload):
            color = row["color"]

            def draw_side(values: np.ndarray, sign: float):
                if values.size == 0:
                    ax.text(
                        sign * 0.50,
                        y + ridge_height * 0.45,
                        "n.a.",
                        ha="center",
                        va="center",
                        fontsize=self.FIGURE_FONT_SIZE,
                        fontstyle="italic",
                        color="black",
                        zorder=4,
                    )
                    return

                density = self._kde_1d(values, grid)
                mean_val = float(np.mean(values))
                median_val = float(np.median(values))

                if density.max() <= 0:
                    top = y + ridge_height * 0.62
                    ax.vlines(sign * mean_val, y, top, color=color, linewidth=1.35, alpha=0.85, zorder=3)
                    ax.scatter(sign * mean_val, top, s=26, color="#111827", zorder=6)
                    ax.scatter(
                        sign * median_val,
                        top,
                        s=28,
                        facecolor="white",
                        edgecolor="#111827",
                        linewidth=0.9,
                        zorder=7,
                    )
                    self._annotate_marker_label(
                        ax,
                        sign * mean_val,
                        top,
                        sign,
                        row["label"],
                        "mean",
                        f"mean {mean_val * 100:.1f}%",
                        0.095,
                    )
                    self._annotate_marker_label(
                        ax,
                        sign * median_val,
                        top,
                        sign,
                        row["label"],
                        "median",
                        f"median {median_val * 100:.1f}%",
                        -0.095,
                    )
                    return

                density_scaled = density / density.max() * ridge_height
                x = sign * grid
                y_curve = y + density_scaled

                ax.fill_between(x, y, y_curve, color=color, alpha=0.42, linewidth=0, zorder=2)
                ax.plot(x, y_curve, color=color, linewidth=1.25, zorder=3)

                mean_y = y + np.interp(mean_val, grid, density_scaled)
                median_y = y + np.interp(median_val, grid, density_scaled)

                ax.vlines(sign * mean_val, y, mean_y, color="#111827", linewidth=1.05, zorder=4)
                ax.scatter(sign * mean_val, mean_y, s=24, color="#111827", zorder=6)

                ax.vlines(sign * median_val, y, median_y, color="#111827", linewidth=2.0, zorder=4)
                ax.vlines(sign * median_val, y, median_y, color="white", linewidth=1.0, zorder=5)
                ax.scatter(
                    sign * median_val,
                    median_y,
                    s=26,
                    facecolor="white",
                    edgecolor="#111827",
                    linewidth=0.9,
                    zorder=7,
                )
                self._annotate_marker_label(
                    ax,
                    sign * mean_val,
                    mean_y,
                    sign,
                    row["label"],
                    "mean",
                    f"mean {mean_val * 100:.1f}%",
                    0.085,
                )
                self._annotate_marker_label(
                    ax,
                    sign * median_val,
                    median_y,
                    sign,
                    row["label"],
                    "median",
                    f"median {median_val * 100:.1f}%",
                    -0.085,
                )

            draw_side(row["h2"], sign=-1.0)
            draw_side(row["saf"], sign=1.0)

        ax.set_xlim(-1.0, 1.0)
        ax.set_ylim(0.62, len(payload) + 1.03)
        ax.set_yticks(y_positions)
        ax.set_yticklabels([row["label"] for row in payload], fontsize=self.FIGURE_FONT_SIZE)
        for tick_label in ax.get_yticklabels():
            tick_label.set_color("black")
            tick_label.set_fontweight("bold")

        ax.set_xticks([-1.0, -0.5, 0.0, 0.5, 1.0])
        ax.set_xticklabels(["100", "50", "0", "50", "100"], fontsize=self.FIGURE_FONT_SIZE)
        for tick_label in ax.get_xticklabels():
            tick_label.set_color("black")
        ax.tick_params(axis="y", length=0, pad=5)
        ax.tick_params(axis="x", direction="out", length=3.4, width=0.8, color="black")
        ax.grid(True, axis="x", linestyle="--", linewidth=0.65, alpha=0.12)

        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_visible(False)
        ax.spines["bottom"].set_linewidth(0.9)
        ax.spines["bottom"].set_color("black")

        ax.text(0.25, 1.025, r"H$_2$", transform=ax.transAxes, fontsize=self.FIGURE_FONT_SIZE, fontweight="bold", ha="center", va="bottom", color="black")
        ax.text(0.75, 1.025, "SAF", transform=ax.transAxes, fontsize=self.FIGURE_FONT_SIZE, fontweight="bold", ha="center", va="bottom", color="black")

        fig.text(0.5, 0.040, "Utilization (%)", ha="center", va="center", fontsize=self.FIGURE_FONT_SIZE, fontweight="bold", color="black")
        fig.subplots_adjust(left=0.17, right=0.965, top=0.925, bottom=0.105)

        output_path = self.session_dir / f"{stem}.png"
        latest_path = self.output_dir / f"{stem}_latest.png"
        self._save_figure_bundle(fig, output_path, latest_path)
        plt.close(fig)
        logger.info("保存图片: %s", output_path)

    def create_figure(self):
        payload = self._build_distribution_payload()
        if len(payload) == 0:
            raise RuntimeError("无可用于绘图的帕累托利用率数据")

        self._create_distribution_figure(
            payload,
            stem="pareto_temporal_distribution",
        )

    def export_summary(self):
        summary = []
        for scenario_label in self.selected_pareto:
            scenario_data = self.data.get(scenario_label)
            if scenario_data is None:
                continue

            metrics_df = pd.DataFrame(scenario_data["hourly_metrics"])
            if metrics_df.empty:
                continue

            screening = self.pareto_screening_data.get(scenario_label, {})
            h2_stats = self._distribution_stats(metrics_df["h2_utilization"].to_numpy(dtype=float))
            saf_stats = self._distribution_stats(metrics_df["saf_utilization"].to_numpy(dtype=float))
            summary.append({
                "scenario": scenario_label,
                "category": scenario_data["config"]["category"],
                "pathway": scenario_data["config"]["pathway"],
                "lcoe_cny_per_kg": screening.get("lcoe"),
                "carbon_diff_gco2e_per_mj": screening.get("carbon_diff"),
                "h2_applicable": bool(h2_stats["n"] > 0),
                "h2_mean_utilization": h2_stats["mean"] / 100.0 if np.isfinite(h2_stats["mean"]) else np.nan,
                "h2_median_utilization": h2_stats["median"] / 100.0 if np.isfinite(h2_stats["median"]) else np.nan,
                "saf_mean_utilization": saf_stats["mean"] / 100.0 if np.isfinite(saf_stats["mean"]) else np.nan,
                "saf_median_utilization": saf_stats["median"] / 100.0 if np.isfinite(saf_stats["median"]) else np.nan,
            })

        summary_df = pd.DataFrame(summary)
        summary_path = self.session_dir / "pareto_temporal_distribution_summary.csv"
        summary_df.to_csv(summary_path, index=False, encoding="utf-8-sig")
        logger.info("保存汇总: %s", summary_path)

        latest_summary_path = self.output_dir / "pareto_temporal_distribution_summary_latest.csv"
        shutil.copy2(summary_path, latest_summary_path)

    def run(self):
        logger.info("=" * 80)
        logger.info("开始生成三个帕累托最优方案的镜像分布图")
        logger.info("=" * 80)

        self.identify_selected_pareto()
        if len(self.selected_pareto) < 3:
            raise RuntimeError(f"仅识别到 {len(self.selected_pareto)} 个帕累托最优方案，无法输出 3 个代表方案")

        self.load_selected_temporal_data()
        if len(self.data) < 3:
            raise RuntimeError(f"利用率数据不足，当前仅加载到 {len(self.data)} 个帕累托场景")

        self.create_figure()
        self.export_summary()

        logger.info("全部完成，共生成 1 张图与 1 个汇总文件")


def main():
    visualizer = ParetoTemporalDistributionVisualizer()
    visualizer.run()


if __name__ == "__main__":
    main()
