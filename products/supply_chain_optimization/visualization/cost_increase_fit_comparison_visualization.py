"""
Compare quadratic fit, one-break piecewise linear fit, and gap boundaries on
the emission-increase axis for three SSP carbon-price scenarios.

X-axis definition:
    emission_increase = pathway_carbon_intensity - traditional_jet_baseline

So:
    x < 0  -> lower emission than traditional jet
    x = 0  -> same as traditional jet
    x > 0  -> higher emission than traditional jet
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
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

from carbon_price_cost_emission_visualization import (
    CarbonPriceCostEmissionVisualizer,
    SSP_CARBON_PRICE_SCENARIOS,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class CostIncreaseFitComparisonVisualizer(CarbonPriceCostEmissionVisualizer):
    """Standalone comparison chart on emission-increase axis."""

    def __init__(
        self,
        carbon_price_scenarios: Optional[List[Dict[str, float]]] = None,
        top_gap_count: int = 3,
        min_gap_points_each_side: int = 2,
        min_break_points_each_side: int = 3,
    ):
        super().__init__(carbon_price_scenarios=carbon_price_scenarios)
        original_session_dir = self.session_dir
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = self.output_dir / f"cost_increase_fit_comparison_{timestamp}"
        self.session_dir.mkdir(parents=True, exist_ok=True)
        try:
            original_session_dir.rmdir()
        except OSError:
            pass

        self.top_gap_count = top_gap_count
        self.min_gap_points_each_side = min_gap_points_each_side
        self.min_break_points_each_side = min_break_points_each_side
        logger.info("Comparison chart output directory: %s", self.session_dir)

    @staticmethod
    def _fit_quadratic(x: np.ndarray, y: np.ndarray) -> Dict[str, object]:
        coeffs = np.polyfit(x, y, 2)
        prediction = np.polyval(coeffs, x)
        ss_res = float(np.sum((y - prediction) ** 2))
        ss_tot = float(np.sum((y - y.mean()) ** 2))
        r2 = 1.0 if ss_tot == 0 else 1.0 - ss_res / ss_tot
        adjusted_r2 = 1.0 - (1.0 - r2) * (len(x) - 1) / (len(x) - 3)
        vertex_x = float(-coeffs[1] / (2.0 * coeffs[0])) if coeffs[0] != 0 else None
        vertex_y = (
            float(np.polyval(coeffs, vertex_x))
            if vertex_x is not None
            else None
        )
        return {
            "coefficients": coeffs.tolist(),
            "prediction": prediction,
            "r2": r2,
            "adjusted_r2": adjusted_r2,
            "vertex_x": vertex_x,
            "vertex_y": vertex_y,
            "equation": CarbonPriceCostEmissionVisualizer._format_polynomial(coeffs.tolist()),
        }

    @staticmethod
    def _fit_piecewise_linear_one_break(
        x: np.ndarray,
        y: np.ndarray,
        min_points_each_side: int,
    ) -> Optional[Dict[str, object]]:
        order = np.argsort(x)
        xs = x[order]
        ys = y[order]
        unique_x = np.unique(xs)
        best_fit: Optional[Dict[str, object]] = None

        for breakpoint in unique_x:
            left_count = int(np.sum(xs <= breakpoint))
            right_count = int(np.sum(xs > breakpoint))
            if left_count < min_points_each_side or right_count < min_points_each_side:
                continue

            X = np.column_stack(
                [
                    np.ones_like(xs),
                    xs,
                    np.maximum(0.0, xs - breakpoint),
                ]
            )
            beta, *_ = np.linalg.lstsq(X, ys, rcond=None)
            prediction_sorted = X @ beta
            prediction = np.empty_like(prediction_sorted)
            prediction[order] = prediction_sorted

            ss_res = float(np.sum((y - prediction) ** 2))
            ss_tot = float(np.sum((y - y.mean()) ** 2))
            r2 = 1.0 if ss_tot == 0 else 1.0 - ss_res / ss_tot
            adjusted_r2 = 1.0 - (1.0 - r2) * (len(x) - 1) / (len(x) - 4)

            candidate = {
                "breakpoint_x": float(breakpoint),
                "beta": beta.tolist(),
                "prediction": prediction,
                "r2": r2,
                "adjusted_r2": adjusted_r2,
                "left_slope": float(beta[1]),
                "right_slope": float(beta[1] + beta[2]),
                "equation_hinge": (
                    f"y = {beta[0]:.4f} + {beta[1]:.4f}x "
                    f"+ {beta[2]:.4f}max(0, x - {breakpoint:.1f})"
                ),
                "ss_res": ss_res,
            }
            if best_fit is None or candidate["ss_res"] < best_fit["ss_res"]:
                best_fit = candidate

        return best_fit

    @staticmethod
    def _find_gap_boundaries(
        x: np.ndarray,
        top_gap_count: int,
        min_points_each_side: int,
    ) -> List[Dict[str, float]]:
        unique_x = np.unique(np.sort(x))
        candidates: List[Dict[str, float]] = []

        for idx in range(len(unique_x) - 1):
            left_count = idx + 1
            right_count = len(unique_x) - left_count
            if left_count < min_points_each_side or right_count < min_points_each_side:
                continue

            left_x = float(unique_x[idx])
            right_x = float(unique_x[idx + 1])
            gap = right_x - left_x
            candidates.append(
                {
                    "gap_size": gap,
                    "midpoint_x": (left_x + right_x) / 2.0,
                    "left_x": left_x,
                    "right_x": right_x,
                    "left_count": left_count,
                    "right_count": right_count,
                }
            )

        top_candidates = sorted(
            candidates,
            key=lambda item: item["gap_size"],
            reverse=True,
        )[:top_gap_count]
        return sorted(top_candidates, key=lambda item: item["midpoint_x"])

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

    def plot_comparison_chart(self, summary_df: pd.DataFrame):
        logger.info("\nGenerating fit comparison chart on emission-increase axis...")

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

        gap_boundaries = self._find_gap_boundaries(
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

            for gap_idx, gap_info in enumerate(gap_boundaries, start=1):
                ax.axvline(
                    gap_info["midpoint_x"],
                    color="#F9A825",
                    linestyle=":",
                    linewidth=1.5,
                    alpha=0.85,
                    zorder=2,
                )
                ax.text(
                    gap_info["midpoint_x"],
                    y_max + 0.15,
                    f"G{gap_idx}",
                    fontsize=11,
                    ha="center",
                    va="bottom",
                    color="#8D6E63",
                    fontweight="bold",
                )

            texts = []
            scatter_x: List[float] = []
            scatter_y: List[float] = []
            for _, row in scenario_df.iterrows():
                point_data = next(
                    item for item in self.data.values() if item["name_en"] == row["Scenario"]
                )
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

            x = scenario_df[x_column].to_numpy(dtype=float)
            y = scenario_df["Cost With Carbon Price (CNY/kg)"].to_numpy(dtype=float)

            quadratic_fit = self._fit_quadratic(x, y)
            quadratic_grid = np.linspace(float(x.min()), float(x.max()), 400)
            quadratic_curve = np.polyval(
                np.array(quadratic_fit["coefficients"]),
                quadratic_grid,
            )
            ax.plot(
                quadratic_grid,
                quadratic_curve,
                color="#C62828",
                linewidth=2.8,
                zorder=4,
            )

            piecewise_fit = self._fit_piecewise_linear_one_break(
                x,
                y,
                min_points_each_side=self.min_break_points_each_side,
            )
            if piecewise_fit is not None:
                piecewise_curve = (
                    piecewise_fit["beta"][0]
                    + piecewise_fit["beta"][1] * quadratic_grid
                    + piecewise_fit["beta"][2]
                    * np.maximum(0.0, quadratic_grid - piecewise_fit["breakpoint_x"])
                )
                ax.plot(
                    quadratic_grid,
                    piecewise_curve,
                    color="#1565C0",
                    linestyle="--",
                    linewidth=2.4,
                    zorder=4,
                )
                ax.axvline(
                    piecewise_fit["breakpoint_x"],
                    color="#1565C0",
                    linestyle="--",
                    linewidth=1.5,
                    alpha=0.9,
                    zorder=3,
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

            fit_results.append(
                {
                    "carbon_price_scenario": carbon_scenario["name"],
                    "carbon_price_usd_per_t": carbon_scenario["usd_per_t"],
                    "carbon_price_cny_per_t": carbon_scenario["cny_per_t"],
                    "x_column": x_column,
                    "quadratic_fit": {
                        key: value
                        for key, value in quadratic_fit.items()
                        if key != "prediction"
                    },
                    "piecewise_fit": (
                        {
                            key: value
                            for key, value in piecewise_fit.items()
                            if key not in {"prediction", "ss_res"}
                        }
                        if piecewise_fit is not None
                        else None
                    ),
                }
            )

            info_lines = [
                f"Quadratic adj. R^2 = {quadratic_fit['adjusted_r2']:.2f}",
                f"Quadratic vertex x* = {quadratic_fit['vertex_x']:.1f}",
            ]
            if piecewise_fit is not None:
                info_lines.extend(
                    [
                        f"1-break bp = {piecewise_fit['breakpoint_x']:.1f}",
                        (
                            f"Piecewise slopes = "
                            f"{piecewise_fit['left_slope']:.3f} | {piecewise_fit['right_slope']:.3f}"
                        ),
                    ]
                )

            ax.text(
                0.03,
                0.05,
                "\n".join(info_lines),
                transform=ax.transAxes,
                fontsize=10.5,
                color="#444444",
                va="bottom",
                ha="left",
                bbox=dict(facecolor="white", edgecolor="#DDDDDD", alpha=0.88, pad=0.35),
            )

            ax.text(
                x_min / 2.0,
                y_max + 0.35,
                "Emission reduction",
                fontsize=12,
                ha="center",
                va="bottom",
                fontweight="bold",
                color="#555555",
            )
            ax.text(
                x_max / 2.0,
                y_max + 0.35,
                "Emission increase",
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
                color="#C62828",
                linewidth=2.8,
                label="Quadratic fit",
            ),
            Line2D(
                [0],
                [0],
                color="#1565C0",
                linestyle="--",
                linewidth=2.4,
                label="1-break piecewise linear fit",
            ),
            Line2D(
                [0],
                [0],
                color="#F9A825",
                linestyle=":",
                linewidth=1.5,
                label="Gap boundary",
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
            ncol=4,
            fontsize=11,
            framealpha=0.85,
            edgecolor="#CCCCCC",
            facecolor="white",
        )

        fig.suptitle(
            "Quadratic Fit vs One-Break Piecewise Fit on Emission-Increase Axis",
            fontsize=18,
            fontweight="bold",
            y=0.98,
        )
        fig.tight_layout(rect=(0.02, 0.04, 0.93, 0.94))

        output_path = self.session_dir / "cost_increase_fit_comparison.png"
        latest_path = self.output_dir / "cost_increase_fit_comparison_latest.png"
        plt.savefig(output_path, dpi=300, bbox_inches="tight", facecolor="white")
        plt.savefig(latest_path, dpi=300, bbox_inches="tight", facecolor="white")
        plt.close()

        logger.info("Saved comparison chart: %s", output_path)
        return output_path, fit_results, gap_boundaries

    def save_summary(self, summary_df: pd.DataFrame):
        summary_path = self.session_dir / "cost_increase_fit_comparison_summary.csv"
        summary_df.to_csv(summary_path, index=False, encoding="utf-8-sig")
        logger.info("Saved comparison summary: %s", summary_path)
        return summary_path

    def save_metadata(self, fit_results: List[dict], gap_boundaries: List[dict]):
        metadata = {
            "x_definition": "emission_increase = pathway_carbon_intensity - traditional_jet_baseline",
            "gap_boundaries": gap_boundaries,
            "fit_results": fit_results,
        }
        metadata_path = self.session_dir / "cost_increase_fit_comparison_metadata.json"
        with open(metadata_path, "w", encoding="utf-8") as handle:
            json.dump(metadata, handle, ensure_ascii=False, indent=2)
        logger.info("Saved comparison metadata: %s", metadata_path)
        return metadata_path

    def run(self):
        logger.info("=" * 60)
        logger.info("Cost-increase fit comparison visualization")
        logger.info("=" * 60)

        self.load_data()
        if len(self.data) < 2:
            logger.error("Not enough data: only %s scenarios loaded", len(self.data))
            return None

        summary_df = self.build_increase_summary_table()
        chart_path, fit_results, gap_boundaries = self.plot_comparison_chart(summary_df)
        self.save_summary(summary_df)
        self.save_metadata(fit_results, gap_boundaries)

        logger.info("\n" + "=" * 60)
        logger.info("Comparison visualization completed. Output directory: %s", self.session_dir)
        logger.info("=" * 60)
        return chart_path


def main():
    visualizer = CostIncreaseFitComparisonVisualizer(
        carbon_price_scenarios=SSP_CARBON_PRICE_SCENARIOS
    )
    visualizer.run()


if __name__ == "__main__":
    main()
