"""
Carbon-price-adjusted cost vs emission visualization for 13 SAF scenarios.

This script follows the visual style of the quadrant chart and evaluates three
SSP carbon-price scenarios:
- SSP2-4.5: 350 CNY/tCO2
- SSP1-2.6: 1000 CNY/tCO2
- SSP1-1.9: 2000 CNY/tCO2

For each carbon-price scenario, it:
- calculates cost with carbon price
- plots the scatter of all 13 pathways
- fits a polynomial trade-off curve using all scatter points
"""

from __future__ import annotations

import json
import glob
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.ticker import MultipleLocator

try:
    from adjustText import adjust_text
except ImportError:
    adjust_text = None

from quadrant_chart_visualization import QuadrantChartVisualizer


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


SSP_CARBON_PRICE_SCENARIOS = [
    {"name": "SSP2-4.5", "usd_per_t": 50.0, "cny_per_t": 350.0},
    {"name": "SSP1-2.6", "usd_per_t": 150.0, "cny_per_t": 1000.0},
    {"name": "SSP1-1.9", "usd_per_t": 300.0, "cny_per_t": 2000.0},
]


class CarbonPriceCostEmissionVisualizer(QuadrantChartVisualizer):
    """Scatter and all-point curve-fit visualization for carbon-price-adjusted cost."""

    def __init__(self, carbon_price_scenarios: Optional[List[Dict[str, float]]] = None):
        super().__init__(cost_threshold=8.0, carbon_threshold=0.0)
        original_session_dir = self.session_dir
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = self.output_dir / f"carbon_price_cost_emission_{timestamp}"
        self.session_dir.mkdir(parents=True, exist_ok=True)
        try:
            original_session_dir.rmdir()
        except OSError:
            pass

        self.carbon_price_scenarios = carbon_price_scenarios or SSP_CARBON_PRICE_SCENARIOS
        self.data: Dict[str, Dict[str, float]] = {}
        logger.info("Carbon-price chart output directory: %s", self.session_dir)

    def load_data(self):
        """Load base cost and emission data for all 13 pathways."""
        logger.info("=" * 60)
        logger.info("Loading scenario data for carbon-price analysis")
        logger.info("=" * 60)

        for module_name, config in self.modules.items():
            logger.info("\nLoading: %s (%s)", module_name, config["name_en"])

            try:
                solution_files = sorted(glob.glob(config["solution_pattern"]), reverse=True)
                if not solution_files:
                    logger.warning("  Solution file not found")
                    continue

                carbon_files = sorted(glob.glob(config["carbon_pattern"]), reverse=True)
                if not carbon_files:
                    logger.warning("  Carbon file not found")
                    continue

                solution_path = Path(solution_files[0])
                carbon_path = Path(carbon_files[0])

                with open(solution_path, "r", encoding="utf-8") as handle:
                    solution_data = json.load(handle)
                with open(carbon_path, "r", encoding="utf-8") as handle:
                    carbon_data = json.load(handle)

                lcoe = float(
                    solution_data.get("lifecycle_levelized_cost_excluding_shortage_per_kg", 0.0)
                )
                production = float(solution_data.get("lifecycle_total_production_kg", 0.0)) / 1e6

                traditional_jet_ci = float(
                    carbon_data.get("traditional_jet_ci_gco2e_per_mj", 89.0)
                )
                if self.traditional_jet_ci_gco2e_per_mj is None:
                    self.traditional_jet_ci_gco2e_per_mj = traditional_jet_ci

                carbon_intensity_mj = carbon_data.get("carbon_intensity_mj")
                carbon_diff = carbon_data.get("abs_diff_vs_traditional_jet_gco2e_per_mj")

                if carbon_intensity_mj is None and carbon_diff is not None:
                    carbon_intensity_mj = traditional_jet_ci + float(carbon_diff)
                if carbon_intensity_mj is None:
                    carbon_intensity_mj = 0.0
                carbon_intensity_mj = float(carbon_intensity_mj)

                if carbon_diff is None:
                    carbon_diff = carbon_intensity_mj - traditional_jet_ci
                carbon_diff = float(carbon_diff)

                carbon_intensity_kg = carbon_data.get("carbon_intensity_kg")
                if carbon_intensity_kg is None:
                    total_emissions = (
                        carbon_data.get("by_stage", {}).get("total_emissions")
                        if isinstance(carbon_data.get("by_stage"), dict)
                        else None
                    )
                    total_production = carbon_data.get("total_production_kg") or solution_data.get(
                        "lifecycle_total_production_kg"
                    )
                    if total_emissions is not None and total_production:
                        carbon_intensity_kg = float(total_emissions) / float(total_production)
                    else:
                        carbon_intensity_kg = 0.0
                carbon_intensity_kg = float(carbon_intensity_kg)

                self.data[module_name] = {
                    "name_en": config["name_en"],
                    "category": config["category"],
                    "color": config["color"],
                    "lcoe": lcoe,
                    "production": production,
                    "carbon_intensity_mj": carbon_intensity_mj,
                    "carbon_intensity_kg": carbon_intensity_kg,
                    "carbon_diff": carbon_diff,
                }

                logger.info("  Base LCOE: %.2f CNY/kg", lcoe)
                logger.info("  Carbon intensity: %.2f g CO2eq/MJ", carbon_intensity_mj)
                logger.info("  Carbon intensity: %.3f kg CO2eq/kg SAF", carbon_intensity_kg)

            except Exception as exc:
                logger.error("  Loading failed: %s", exc)

        logger.info("\nLoaded %s scenarios", len(self.data))

    @staticmethod
    def _carbon_price_adjustment_per_kg(
        carbon_intensity_kg: float,
        carbon_price_yuan_per_ton: float,
    ) -> float:
        return carbon_intensity_kg * carbon_price_yuan_per_ton / 1000.0

    @staticmethod
    def _fit_polynomial_curve(x: np.ndarray, y: np.ndarray) -> Optional[Dict[str, object]]:
        if len(x) < 3 or len(np.unique(x)) < 3:
            return None

        max_degree = min(3, len(x) - 1, len(np.unique(x)) - 1)
        best_fit: Optional[Dict[str, object]] = None
        best_score = -np.inf

        for degree in range(1, max_degree + 1):
            try:
                coeffs = np.polyfit(x, y, degree)
                prediction = np.polyval(coeffs, x)
                ss_res = float(np.sum((y - prediction) ** 2))
                ss_tot = float(np.sum((y - y.mean()) ** 2))
                r2 = 1.0 if ss_tot == 0 else 1.0 - ss_res / ss_tot

                if len(x) - degree - 1 > 0:
                    adjusted_r2 = 1.0 - (1.0 - r2) * (len(x) - 1) / (len(x) - degree - 1)
                else:
                    adjusted_r2 = r2

                if adjusted_r2 > best_score:
                    best_score = adjusted_r2
                    best_fit = {
                        "degree": degree,
                        "coefficients": coeffs.tolist(),
                        "r2": r2,
                        "adjusted_r2": adjusted_r2,
                    }
            except Exception:
                continue

        return best_fit

    @staticmethod
    def _format_polynomial(coefficients: List[float]) -> str:
        degree = len(coefficients) - 1
        pieces: List[str] = []

        for index, coefficient in enumerate(coefficients):
            power = degree - index
            if abs(coefficient) < 1e-10:
                continue

            sign = "-" if coefficient < 0 else "+"
            value = abs(coefficient)
            if power == 0:
                term = f"{value:.4f}"
            elif power == 1:
                term = f"{value:.4f}x"
            else:
                term = f"{value:.4f}x^{power}"
            pieces.append((sign, term))

        if not pieces:
            return "y = 0"

        first_sign, first_term = pieces[0]
        expression = first_term if first_sign == "+" else f"-{first_term}"
        for sign, term in pieces[1:]:
            expression += f" {sign} {term}"
        return f"y = {expression}"

    def build_summary_table(self) -> pd.DataFrame:
        rows: List[dict] = []
        baseline = float(self.traditional_jet_ci_gco2e_per_mj or 89.0)

        for carbon_scenario in self.carbon_price_scenarios:
            for data in self.data.values():
                carbon_price_adjustment = self._carbon_price_adjustment_per_kg(
                    data["carbon_intensity_kg"],
                    carbon_scenario["cny_per_t"],
                )
                adjusted_cost = data["lcoe"] + carbon_price_adjustment

                rows.append(
                    {
                        "Carbon Price Scenario": carbon_scenario["name"],
                        "Carbon Price (USD/tCO2)": carbon_scenario["usd_per_t"],
                        "Carbon Price (CNY/tCO2)": carbon_scenario["cny_per_t"],
                        "Scenario": data["name_en"],
                        "Category": data["category"],
                        "Emission Intensity (g CO2eq/MJ)": data["carbon_intensity_mj"],
                        "Emission Reduction vs Traditional Jet (g CO2eq/MJ)": (
                            baseline - data["carbon_intensity_mj"]
                        ),
                        "Emission Intensity (kg CO2eq/kg SAF)": data["carbon_intensity_kg"],
                        "Base LCOE (CNY/kg)": data["lcoe"],
                        "Carbon Price Adjustment (CNY/kg)": carbon_price_adjustment,
                        "Cost With Carbon Price (CNY/kg)": adjusted_cost,
                        "Production (kt)": data["production"],
                    }
                )

        df = pd.DataFrame(rows)
        return df.sort_values(
            by=[
                "Carbon Price (CNY/tCO2)",
                "Emission Reduction vs Traditional Jet (g CO2eq/MJ)",
                "Cost With Carbon Price (CNY/kg)",
            ]
        ).reset_index(drop=True)

    def _plot_relation_chart(
        self,
        summary_df: pd.DataFrame,
        x_column: str,
        x_label: str,
        baseline: float,
        left_region_label: str,
        right_region_label: str,
        left_region_color: str,
        right_region_color: str,
        output_filename: str,
        latest_filename: str,
        fit_scope: str,
        figure_title: str,
    ):
        logger.info("\nGenerating chart for %s...", x_column)

        plt.rcParams["font.family"] = ["Times New Roman", "DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False

        fig, axes = plt.subplots(1, 3, figsize=(26, 8.5), sharex=True, sharey=True)

        x_values = summary_df[x_column].to_numpy(dtype=float)
        y_values = summary_df["Cost With Carbon Price (CNY/kg)"].to_numpy(dtype=float)
        x_margin = max(20.0, (float(x_values.max()) - float(x_values.min())) * 0.10)
        y_margin = max(1.5, (float(y_values.max()) - float(y_values.min())) * 0.12)
        x_min = float(x_values.min()) - x_margin
        x_max = float(x_values.max()) + x_margin
        y_min = max(0.0, float(y_values.min()) - y_margin)
        y_max = float(y_values.max()) + y_margin

        fit_results: List[dict] = []
        pathway_order = {
            "Grey": ["CTL", "CTL-BH"],
            "Blue": [
                "DAC-BH-MTJ",
                "DAC-BH-FT",
                "GTL-BH",
                "GTL-GH",
                "GTL",
                "CCU-BH-MTJ",
                "CCU-BH-FT",
            ],
            "Green": ["DAC-GH-MTJ", "DAC-GH-FT", "CCU-GH-MTJ", "CCU-GH-FT"],
        }

        for ax, carbon_scenario in zip(axes, self.carbon_price_scenarios):
            scenario_df = summary_df[
                summary_df["Carbon Price Scenario"] == carbon_scenario["name"]
            ].copy()

            ax.fill_between(
                [x_min, baseline],
                y_min,
                y_max,
                color=left_region_color,
                alpha=0.55,
                zorder=0,
            )
            ax.fill_between(
                [baseline, x_max],
                y_min,
                y_max,
                color=right_region_color,
                alpha=0.55,
                zorder=0,
            )
            ax.axvline(
                x=baseline,
                color="#999999",
                linestyle="--",
                linewidth=1.5,
                zorder=1,
            )

            texts = []
            scatter_x = []
            scatter_y = []

            for _, row in scenario_df.iterrows():
                point_data = next(item for item in self.data.values() if item["name_en"] == row["Scenario"])
                x = float(row[x_column])
                y = float(row["Cost With Carbon Price (CNY/kg)"])
                scatter_x.append(x)
                scatter_y.append(y)

                ax.scatter(
                    x,
                    y,
                    s=360,
                    c=point_data["color"],
                    alpha=0.9,
                    edgecolors="none",
                    zorder=5,
                )
                texts.append(
                    ax.text(
                        x,
                        y,
                        row["Scenario"],
                        fontsize=10.5,
                        color="#333333",
                        zorder=10,
                    )
                )

            fit_result = self._fit_polynomial_curve(
                scenario_df[x_column].to_numpy(dtype=float),
                scenario_df["Cost With Carbon Price (CNY/kg)"].to_numpy(dtype=float),
            )

            fit_payload = {
                "carbon_price_scenario": carbon_scenario["name"],
                "carbon_price_usd_per_t": carbon_scenario["usd_per_t"],
                "carbon_price_cny_per_t": carbon_scenario["cny_per_t"],
                "fit_scope": fit_scope,
                "x_column": x_column,
                "fit_result": fit_result,
                "fit_equation": (
                    self._format_polynomial(fit_result["coefficients"])
                    if fit_result is not None
                    else None
                ),
            }
            fit_results.append(fit_payload)

            fit_label = "All-point trade-off fit unavailable"
            if fit_result is not None:
                x_curve = np.linspace(
                    float(scenario_df[x_column].min()),
                    float(scenario_df[x_column].max()),
                    400,
                )
                y_curve = np.polyval(np.array(fit_result["coefficients"]), x_curve)
                ax.plot(
                    x_curve,
                    y_curve,
                    color="#C62828",
                    linewidth=2.8,
                    zorder=4,
                )
                fit_label = (
                    f"All-point fit: degree {fit_result['degree']}, "
                    f"adj. R^2={fit_result['adjusted_r2']:.2f}"
                )

            if adjust_text:
                try:
                    adjust_text(
                        texts,
                        x=scatter_x,
                        y=scatter_y,
                        ax=ax,
                        arrowprops=dict(arrowstyle="-", color="#666666", lw=0.8),
                        force_text=(0.5, 1.0),
                        force_static=(1.0, 1.5),
                        force_pull=(0.1, 0.1),
                        expand=(1.2, 1.4),
                        ensure_inside_axes=True,
                        iter_lim=1000,
                    )
                except Exception as exc:
                    logger.warning("adjust_text failed for %s: %s", carbon_scenario["name"], exc)

            ax.set_title(
                f"{carbon_scenario['name']}\n"
                f"{carbon_scenario['cny_per_t']:.0f} CNY/tCO2 ({carbon_scenario['usd_per_t']:.0f} USD/tCO2)",
                fontsize=14,
                fontweight="bold",
                pad=12,
            )

            ax.text(
                0.03,
                0.05,
                fit_label,
                transform=ax.transAxes,
                fontsize=10.5,
                color="#444444",
                va="bottom",
                ha="left",
                bbox=dict(facecolor="white", edgecolor="#DDDDDD", alpha=0.88, pad=0.35),
            )

            ax.text(
                x_min + (baseline - x_min) / 2,
                y_max + 0.35,
                left_region_label,
                fontsize=12,
                ha="center",
                va="bottom",
                fontweight="bold",
                color="#555555",
            )
            ax.text(
                baseline + (x_max - baseline) / 2,
                y_max + 0.35,
                right_region_label,
                fontsize=12,
                ha="center",
                va="bottom",
                fontweight="bold",
                color="#555555",
            )

            ax.set_xlim(x_min, x_max)
            ax.set_ylim(y_min, y_max)
            ax.grid(True, linestyle="--", alpha=0.5, color="#AAAAAA", dashes=(4, 4))
            ax.tick_params(axis="both", which="major", labelsize=13)

            for spine in ax.spines.values():
                spine.set_visible(True)
                spine.set_linewidth(1.2)
                spine.set_color("#666666")

        if not adjust_text:
            logger.warning("adjustText not installed, skipping label adjustment")

        x_span = x_max - x_min
        y_span = y_max - y_min
        for ax in axes:
            if x_span > 600:
                ax.xaxis.set_major_locator(MultipleLocator(200))
            elif x_span > 250:
                ax.xaxis.set_major_locator(MultipleLocator(100))
            else:
                ax.xaxis.set_major_locator(MultipleLocator(50))

            if y_span > 50:
                ax.yaxis.set_major_locator(MultipleLocator(10))
            elif y_span > 20:
                ax.yaxis.set_major_locator(MultipleLocator(5))
            else:
                ax.yaxis.set_major_locator(MultipleLocator(2))

            ax.set_xlabel(x_label, fontsize=14, fontweight="bold")

        axes[0].set_ylabel("Cost with carbon price (CNY/kg)", fontsize=14, fontweight="bold")

        scenario_handles: List[Line2D] = []
        for group in ["Grey", "Blue", "Green"]:
            for name in pathway_order[group]:
                for data in self.data.values():
                    if data["name_en"] == name:
                        scenario_handles.append(
                            Line2D(
                                [0],
                                [0],
                                marker="o",
                                color="w",
                                markerfacecolor=data["color"],
                                markersize=9,
                                label=name,
                                linestyle="None",
                            )
                        )
                        break

        analysis_handles = [
            Line2D(
                [0],
                [0],
                color="#C62828",
                linewidth=2.8,
                label="All-point fitted curve",
            ),
            Line2D(
                [0],
                [0],
                color="#999999",
                linestyle="--",
                linewidth=1.5,
                label=f"Reference line ({baseline:.0f})",
            ),
        ]

        fig.legend(
            handles=scenario_handles,
            loc="center right",
            bbox_to_anchor=(0.995, 0.55),
            title="Scenarios",
            title_fontsize=11,
            fontsize=10,
            framealpha=0.85,
            edgecolor="#CCCCCC",
            facecolor="white",
        )
        fig.legend(
            handles=analysis_handles,
            loc="lower center",
            bbox_to_anchor=(0.5, -0.01),
            ncol=2,
            fontsize=11,
            framealpha=0.85,
            edgecolor="#CCCCCC",
            facecolor="white",
        )

        fig.suptitle(
            figure_title,
            fontsize=18,
            fontweight="bold",
            y=0.98,
        )
        fig.tight_layout(rect=(0.02, 0.04, 0.93, 0.94))

        output_path = self.session_dir / output_filename
        latest_path = self.output_dir / latest_filename
        plt.savefig(output_path, dpi=300, bbox_inches="tight", facecolor="white")
        plt.savefig(latest_path, dpi=300, bbox_inches="tight", facecolor="white")
        plt.close()

        logger.info("Saved chart: %s", output_path)
        return output_path, fit_results

    def plot_cost_emission_chart(self, summary_df: pd.DataFrame):
        baseline = float(self.traditional_jet_ci_gco2e_per_mj or 89.0)
        return self._plot_relation_chart(
            summary_df=summary_df,
            x_column="Emission Intensity (g CO2eq/MJ)",
            x_label="Carbon intensity (g CO2eq/MJ)",
            baseline=baseline,
            left_region_label="Lower emission",
            right_region_label="Higher emission",
            left_region_color="#F1F8E9",
            right_region_color="#FFF3E0",
            output_filename="carbon_price_cost_emission_ssp_scenarios.png",
            latest_filename="carbon_price_cost_emission_ssp_latest.png",
            fit_scope="all_points_by_emission_intensity",
            figure_title="Carbon-Price-Adjusted Cost vs Emission Across SSP Carbon Price Scenarios",
        )

    def plot_cost_reduction_chart(self, summary_df: pd.DataFrame):
        return self._plot_relation_chart(
            summary_df=summary_df,
            x_column="Emission Reduction vs Traditional Jet (g CO2eq/MJ)",
            x_label="Emission reduction vs traditional jet (g CO2eq/MJ)",
            baseline=0.0,
            left_region_label="Emission increase",
            right_region_label="Emission reduction",
            left_region_color="#FFF3E0",
            right_region_color="#F1F8E9",
            output_filename="carbon_price_cost_reduction_ssp_scenarios.png",
            latest_filename="carbon_price_cost_reduction_ssp_latest.png",
            fit_scope="all_points_by_emission_reduction",
            figure_title="Carbon-Price-Adjusted Cost vs Emission Reduction Across SSP Carbon Price Scenarios",
        )

    def save_summary(self, summary_df: pd.DataFrame):
        summary_path = self.session_dir / "carbon_price_cost_emission_summary.csv"
        summary_df.to_csv(summary_path, index=False, encoding="utf-8-sig")
        logger.info("Saved summary: %s", summary_path)
        print(summary_df.to_string(index=False))
        return summary_path

    def save_fit_metadata(self, fit_results: List[dict], filename: str):
        metadata_path = self.session_dir / filename
        with open(metadata_path, "w", encoding="utf-8") as handle:
            json.dump(fit_results, handle, ensure_ascii=False, indent=2)
        logger.info("Saved fit metadata: %s", metadata_path)
        return metadata_path

    def run(self):
        logger.info("=" * 60)
        logger.info("Carbon-price-adjusted cost vs emission visualization")
        logger.info("=" * 60)

        self.load_data()
        if len(self.data) < 2:
            logger.error("Not enough data: only %s scenarios loaded", len(self.data))
            return None

        summary_df = self.build_summary_table()
        chart_path, fit_results = self.plot_cost_emission_chart(summary_df)
        reduction_chart_path, reduction_fit_results = self.plot_cost_reduction_chart(summary_df)
        self.save_summary(summary_df)
        self.save_fit_metadata(fit_results, "carbon_price_cost_emission_fit.json")
        self.save_fit_metadata(reduction_fit_results, "carbon_price_cost_reduction_fit.json")

        logger.info("\n" + "=" * 60)
        logger.info("Visualization completed. Output directory: %s", self.session_dir)
        logger.info("=" * 60)
        return {
            "emission_chart": chart_path,
            "reduction_chart": reduction_chart_path,
        }


def main():
    visualizer = CarbonPriceCostEmissionVisualizer()
    visualizer.run()


if __name__ == "__main__":
    main()
