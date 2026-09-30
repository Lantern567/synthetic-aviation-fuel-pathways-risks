"""
Visualize emission-increase vs carbon-price-adjusted cost with:
- technology-cluster fixed-effect trend lines
- gap zones on the x-axis
- three SSP carbon-price scenarios

X-axis definition:
    emission_increase = pathway_carbon_intensity - traditional_jet_baseline
"""

from __future__ import annotations

import json
import logging
import math
from datetime import datetime
from typing import Dict, List, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import MultipleLocator

try:
    from adjustText import adjust_text
except ImportError:
    adjust_text = None

from carbon_price_cost_emission_visualization import (
    CarbonPriceCostEmissionVisualizer,
    SSP_CARBON_PRICE_SCENARIOS,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class CostIncreaseGroupEffectVisualizer(CarbonPriceCostEmissionVisualizer):
    """Standalone chart for group fixed effects and x-axis gap zones."""

    def __init__(
        self,
        carbon_price_scenarios: Optional[List[Dict[str, float]]] = None,
        top_gap_count: int = 3,
        min_gap_points_each_side: int = 2,
    ):
        super().__init__(carbon_price_scenarios=carbon_price_scenarios)
        original_session_dir = self.session_dir
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = self.output_dir / f"cost_increase_group_effect_{timestamp}"
        self.session_dir.mkdir(parents=True, exist_ok=True)
        try:
            original_session_dir.rmdir()
        except OSError:
            pass

        self.top_gap_count = top_gap_count
        self.min_gap_points_each_side = min_gap_points_each_side
        logger.info("Group-effect chart output directory: %s", self.session_dir)

    @staticmethod
    def _find_gap_regions(
        x: np.ndarray,
        top_gap_count: int,
        min_points_each_side: int,
    ) -> List[Dict[str, float]]:
        unique_x = np.unique(np.sort(x))
        gap_regions: List[Dict[str, float]] = []

        for idx in range(len(unique_x) - 1):
            left_count = idx + 1
            right_count = len(unique_x) - left_count
            if left_count < min_points_each_side or right_count < min_points_each_side:
                continue

            left_x = float(unique_x[idx])
            right_x = float(unique_x[idx + 1])
            gap_regions.append(
                {
                    "left_x": left_x,
                    "right_x": right_x,
                    "midpoint_x": (left_x + right_x) / 2.0,
                    "gap_size": right_x - left_x,
                    "left_count": left_count,
                    "right_count": right_count,
                }
            )

        top_regions = sorted(
            gap_regions,
            key=lambda item: item["gap_size"],
            reverse=True,
        )[:top_gap_count]
        return sorted(top_regions, key=lambda item: item["midpoint_x"])

    @staticmethod
    def _fit_group_fixed_effect_model(
        x: np.ndarray,
        y: np.ndarray,
        category: np.ndarray,
    ) -> Dict[str, object]:
        is_blue = (category == "Blue").astype(float)
        is_green = (category == "Green").astype(float)

        X = np.column_stack([np.ones_like(x), x, is_blue, is_green])
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        prediction = X @ beta

        n = len(y)
        k = X.shape[1]
        ss_res = float(np.sum((y - prediction) ** 2))
        ss_tot = float(np.sum((y - y.mean()) ** 2))
        r2 = 1.0 if ss_tot == 0 else 1.0 - ss_res / ss_tot
        adjusted_r2 = 1.0 - (1.0 - r2) * (n - 1) / (n - k)
        rmse = math.sqrt(ss_res / n)

        intercept = float(beta[0])
        slope = float(beta[1])
        group_intercepts = {
            "Grey": intercept,
            "Blue": intercept + float(beta[2]),
            "Green": intercept + float(beta[3]),
        }

        return {
            "beta": beta.tolist(),
            "prediction": prediction,
            "r2": r2,
            "adjusted_r2": adjusted_r2,
            "rmse": rmse,
            "common_slope": slope,
            "group_intercepts": group_intercepts,
            "equations": {
                group: f"y = {group_intercepts[group]:.4f} + {slope:.4f}x"
                for group in ["Grey", "Blue", "Green"]
            },
        }

    @staticmethod
    def _compute_loocv_rmse(
        x: np.ndarray,
        y: np.ndarray,
        category: np.ndarray,
    ) -> float:
        errors: List[float] = []
        for idx in range(len(x)):
            mask = np.ones(len(x), dtype=bool)
            mask[idx] = False
            fit = CostIncreaseGroupEffectVisualizer._fit_group_fixed_effect_model(
                x[mask],
                y[mask],
                category[mask],
            )
            intercept = fit["group_intercepts"][str(category[idx])]
            prediction = intercept + fit["common_slope"] * float(x[idx])
            errors.append((float(y[idx]) - prediction) ** 2)
        return math.sqrt(sum(errors) / len(errors))

    def build_increase_summary_table(self) -> pd.DataFrame:
        summary_df = self.build_summary_table().copy()
        baseline = float(self.traditional_jet_ci_gco2e_per_mj or 89.0)
        summary_df["Emission Increase vs Traditional Jet (g CO2eq/MJ)"] = (
            summary_df["Emission Intensity (g CO2eq/MJ)"] - baseline
        )
        return summary_df.sort_values(
            by=[
                "Carbon Price (CNY/tCO2)",
                "Emission Increase vs Traditional Jet (g CO2eq/MJ)",
                "Cost With Carbon Price (CNY/kg)",
            ]
        ).reset_index(drop=True)

    def plot_group_effect_chart(self, summary_df: pd.DataFrame):
        logger.info("\nGenerating group fixed-effect chart on emission-increase axis...")

        plt.rcParams["font.family"] = ["Times New Roman", "DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False

        fig, axes = plt.subplots(1, 3, figsize=(26, 8.8), sharex=True, sharey=True)
        x_column = "Emission Increase vs Traditional Jet (g CO2eq/MJ)"
        x_values = summary_df[x_column].to_numpy(dtype=float)
        y_values = summary_df["Cost With Carbon Price (CNY/kg)"].to_numpy(dtype=float)

        x_margin = max(20.0, (float(x_values.max()) - float(x_values.min())) * 0.10)
        y_margin = max(1.5, (float(y_values.max()) - float(y_values.min())) * 0.12)
        x_min = float(x_values.min()) - x_margin
        x_max = float(x_values.max()) + x_margin
        y_min = max(0.0, float(y_values.min()) - y_margin)
        y_max = float(y_values.max()) + y_margin

        gap_regions = self._find_gap_regions(
            x_values,
            top_gap_count=self.top_gap_count,
            min_points_each_side=self.min_gap_points_each_side,
        )

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

        fit_results: List[dict] = []

        for ax, carbon_scenario in zip(axes, self.carbon_price_scenarios):
            scenario_df = summary_df[
                summary_df["Carbon Price Scenario"] == carbon_scenario["name"]
            ].copy()

            ax.fill_between([x_min, 0.0], y_min, y_max, color="#F1F8E9", alpha=0.55, zorder=0)
            ax.fill_between([0.0, x_max], y_min, y_max, color="#FFF3E0", alpha=0.55, zorder=0)
            ax.axvline(0.0, color="#999999", linestyle="--", linewidth=1.5, zorder=1)

            for gap_idx, gap in enumerate(gap_regions, start=1):
                ax.axvspan(
                    gap["left_x"],
                    gap["right_x"],
                    facecolor="#FFF8E1",
                    edgecolor="#F9A825",
                    linewidth=1.0,
                    alpha=0.55,
                    zorder=1,
                )
                ax.text(
                    gap["midpoint_x"],
                    y_max + 0.15,
                    f"G{gap_idx}",
                    fontsize=11,
                    ha="center",
                    va="bottom",
                    color="#8D6E63",
                    fontweight="bold",
                )

            texts = []
            for _, row in scenario_df.iterrows():
                point_data = next(
                    item for item in self.data.values() if item["name_en"] == row["Scenario"]
                )
                x = float(row[x_column])
                y = float(row["Cost With Carbon Price (CNY/kg)"])
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

            x = scenario_df[x_column].to_numpy(dtype=float)
            y = scenario_df["Cost With Carbon Price (CNY/kg)"].to_numpy(dtype=float)
            category = scenario_df["Category"].to_numpy(dtype=str)
            fit = self._fit_group_fixed_effect_model(x, y, category)
            loocv_rmse = self._compute_loocv_rmse(x, y, category)

            for group in ["Grey", "Blue", "Green"]:
                group_df = scenario_df[scenario_df["Category"] == group]
                if group_df.empty:
                    continue

                observed_x = group_df[x_column].to_numpy(dtype=float)
                local_span = float(observed_x.max() - observed_x.min())
                padding = max(8.0, local_span * 0.12)
                line_x = np.linspace(
                    float(observed_x.min()) - padding,
                    float(observed_x.max()) + padding,
                    100,
                )
                line_y = fit["group_intercepts"][group] + fit["common_slope"] * line_x
                line_color = self.category_colors[group]
                ax.plot(
                    line_x,
                    line_y,
                    color=line_color,
                    linewidth=2.6,
                    zorder=4,
                )

            if adjust_text:
                try:
                    adjust_text(
                        texts,
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

            fit_results.append(
                {
                    "carbon_price_scenario": carbon_scenario["name"],
                    "carbon_price_usd_per_t": carbon_scenario["usd_per_t"],
                    "carbon_price_cny_per_t": carbon_scenario["cny_per_t"],
                    "x_column": x_column,
                    "fit_result": {
                        key: value
                        for key, value in fit.items()
                        if key != "prediction"
                    },
                    "loocv_rmse": loocv_rmse,
                }
            )

            info_lines = [
                f"FE adj. R^2 = {fit['adjusted_r2']:.2f}",
                f"LOOCV RMSE = {loocv_rmse:.2f}",
                f"Common slope = {fit['common_slope']:.3f}",
                (
                    f"x=0 costs: Grey {fit['group_intercepts']['Grey']:.1f}, "
                    f"Blue {fit['group_intercepts']['Blue']:.1f}, "
                    f"Green {fit['group_intercepts']['Green']:.1f}"
                ),
            ]
            ax.text(
                0.03,
                0.05,
                "\n".join(info_lines),
                transform=ax.transAxes,
                fontsize=10.4,
                color="#444444",
                va="bottom",
                ha="left",
                bbox=dict(facecolor="white", edgecolor="#DDDDDD", alpha=0.88, pad=0.35),
            )

            ax.text(
                x_min / 2.0,
                y_max + 0.35,
                "Emission reduction cluster",
                fontsize=12,
                ha="center",
                va="bottom",
                fontweight="bold",
                color="#555555",
            )
            ax.text(
                x_max / 2.0,
                y_max + 0.35,
                "Emission increase cluster",
                fontsize=12,
                ha="center",
                va="bottom",
                fontweight="bold",
                color="#555555",
            )

            ax.set_title(
                f"{carbon_scenario['name']}\n"
                f"{carbon_scenario['cny_per_t']:.0f} CNY/tCO2 ({carbon_scenario['usd_per_t']:.0f} USD/tCO2)",
                fontsize=14,
                fontweight="bold",
                pad=12,
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

            ax.set_xlabel(
                "Emission increase vs traditional jet (g CO2eq/MJ)",
                fontsize=14,
                fontweight="bold",
            )

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
                color="#616161",
                linewidth=2.6,
                label="Cluster fixed-effect trend",
            ),
            Patch(
                facecolor="#FFF8E1",
                edgecolor="#F9A825",
                label="Gap zone",
            ),
            Line2D(
                [0],
                [0],
                color="#999999",
                linestyle="--",
                linewidth=1.5,
                label="Traditional jet baseline (x=0)",
            ),
        ]

        fig.legend(
            handles=scenario_handles,
            loc="center right",
            bbox_to_anchor=(0.995, 0.56),
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
            ncol=3,
            fontsize=11,
            framealpha=0.85,
            edgecolor="#CCCCCC",
            facecolor="white",
        )

        fig.suptitle(
            "Technology-Cluster Fixed Effects and Gap Zones on Emission-Increase Axis",
            fontsize=18,
            fontweight="bold",
            y=0.98,
        )
        fig.tight_layout(rect=(0.02, 0.04, 0.93, 0.94))

        output_path = self.session_dir / "cost_increase_group_effect.png"
        latest_path = self.output_dir / "cost_increase_group_effect_latest.png"
        plt.savefig(output_path, dpi=300, bbox_inches="tight", facecolor="white")
        plt.savefig(latest_path, dpi=300, bbox_inches="tight", facecolor="white")
        plt.close()

        logger.info("Saved group-effect chart: %s", output_path)
        return output_path, fit_results, gap_regions

    def save_summary(self, summary_df: pd.DataFrame):
        summary_path = self.session_dir / "cost_increase_group_effect_summary.csv"
        summary_df.to_csv(summary_path, index=False, encoding="utf-8-sig")
        logger.info("Saved group-effect summary: %s", summary_path)
        return summary_path

    def save_metadata(self, fit_results: List[dict], gap_regions: List[dict]):
        metadata = {
            "x_definition": "emission_increase = pathway_carbon_intensity - traditional_jet_baseline",
            "gap_regions": gap_regions,
            "fit_results": fit_results,
        }
        metadata_path = self.session_dir / "cost_increase_group_effect_metadata.json"
        with open(metadata_path, "w", encoding="utf-8") as handle:
            json.dump(metadata, handle, ensure_ascii=False, indent=2)
        logger.info("Saved group-effect metadata: %s", metadata_path)
        return metadata_path

    def run(self):
        logger.info("=" * 60)
        logger.info("Cost-increase group-effect visualization")
        logger.info("=" * 60)

        self.load_data()
        if len(self.data) < 2:
            logger.error("Not enough data: only %s scenarios loaded", len(self.data))
            return None

        summary_df = self.build_increase_summary_table()
        chart_path, fit_results, gap_regions = self.plot_group_effect_chart(summary_df)
        self.save_summary(summary_df)
        self.save_metadata(fit_results, gap_regions)

        logger.info("\n" + "=" * 60)
        logger.info("Group-effect visualization completed. Output directory: %s", self.session_dir)
        logger.info("=" * 60)
        return chart_path


def main():
    visualizer = CostIncreaseGroupEffectVisualizer(
        carbon_price_scenarios=SSP_CARBON_PRICE_SCENARIOS
    )
    visualizer.run()


if __name__ == "__main__":
    main()
