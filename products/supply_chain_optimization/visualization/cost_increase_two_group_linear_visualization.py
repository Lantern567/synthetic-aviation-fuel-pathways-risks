"""
Visualize emission-increase vs carbon-price-adjusted cost with two group-wise
linear fits:
- Green pathways
- Blue + Grey pathways

X-axis definition:
    emission_increase = pathway_carbon_intensity - traditional_jet_baseline
"""

from __future__ import annotations

import json
import logging
import math
from datetime import datetime
from functools import lru_cache
from typing import Dict, List, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import FancyBboxPatch, Patch
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


@lru_cache(maxsize=None)
def _student_t_critical(df: int, confidence: float = 0.95) -> float:
    if df <= 0:
        return 1.96

    target = 0.5 + confidence / 2.0
    lower = 0.0
    upper = 20.0
    while _student_t_cdf(upper, df) < target:
        upper *= 2.0

    for _ in range(80):
        midpoint = (lower + upper) / 2.0
        if _student_t_cdf(midpoint, df) < target:
            lower = midpoint
        else:
            upper = midpoint
    return (lower + upper) / 2.0


def _student_t_pdf(x: float, df: int) -> float:
    log_coeff = (
        math.lgamma((df + 1.0) / 2.0)
        - math.lgamma(df / 2.0)
        - 0.5 * (math.log(df) + math.log(math.pi))
    )
    return math.exp(log_coeff) * (1.0 + (x * x) / df) ** (-(df + 1.0) / 2.0)


def _student_t_cdf(x: float, df: int) -> float:
    if df <= 0:
        raise ValueError("degrees of freedom must be positive")
    if x == 0.0:
        return 0.5

    x_abs = abs(x)
    interval_count = max(400, int(x_abs * 400))
    if interval_count % 2 == 1:
        interval_count += 1

    step = x_abs / interval_count
    total = _student_t_pdf(0.0, df) + _student_t_pdf(x_abs, df)
    for idx in range(1, interval_count):
        total += (4.0 if idx % 2 == 1 else 2.0) * _student_t_pdf(idx * step, df)
    integral = total * step / 3.0

    if x > 0:
        return min(1.0, 0.5 + integral)
    return max(0.0, 0.5 - integral)


def _two_sided_t_p_value(t_stat: float, df: int) -> float:
    if df <= 0:
        return float("nan")
    cdf_value = _student_t_cdf(abs(t_stat), df)
    return max(0.0, min(1.0, 2.0 * (1.0 - cdf_value)))


class CostIncreaseTwoGroupLinearVisualizer(CarbonPriceCostEmissionVisualizer):
    """Standalone chart with separate linear fits for Green and Blue+Grey."""

    def __init__(
        self,
        carbon_price_scenarios: Optional[List[Dict[str, float]]] = None,
    ):
        super().__init__(carbon_price_scenarios=carbon_price_scenarios)
        original_session_dir = self.session_dir
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = self.output_dir / f"cost_increase_two_group_linear_{timestamp}"
        self.session_dir.mkdir(parents=True, exist_ok=True)
        try:
            original_session_dir.rmdir()
        except OSError:
            pass

        self.fit_group_colors = {
            "Green": "#2E7D32",
            "Blue+Grey": "#455A64",
        }
        logger.info("Two-group linear chart output directory: %s", self.session_dir)

    @staticmethod
    def _fit_linear(x: np.ndarray, y: np.ndarray) -> Optional[Dict[str, float]]:
        if len(x) < 2 or len(np.unique(x)) < 2:
            return None

        X = np.column_stack([np.ones_like(x), x])
        xtx_inv = np.linalg.inv(X.T @ X)
        beta = xtx_inv @ X.T @ y
        prediction = X @ beta
        ss_res = float(np.sum((y - prediction) ** 2))
        ss_tot = float(np.sum((y - y.mean()) ** 2))
        r2 = 1.0 if ss_tot == 0 else 1.0 - ss_res / ss_tot
        n = len(x)
        df = n - 2
        adjusted_r2 = r2 if n <= 2 else 1.0 - (1.0 - r2) * (n - 1) / (n - 2)
        rmse = float(np.sqrt(ss_res / n))
        sigma2 = ss_res / df if df > 0 else 0.0
        covariance = sigma2 * xtx_inv
        standard_errors = np.sqrt(np.diag(covariance))
        t_critical = _student_t_critical(df) if df > 0 else 1.96

        intercept = float(beta[0])
        slope = float(beta[1])
        intercept_se = float(standard_errors[0])
        slope_se = float(standard_errors[1])
        intercept_t = intercept / intercept_se if intercept_se > 0 else float("inf")
        slope_t = slope / slope_se if slope_se > 0 else float("inf")
        intercept_p = _two_sided_t_p_value(intercept_t, df) if df > 0 else float("nan")
        slope_p = _two_sided_t_p_value(slope_t, df) if df > 0 else float("nan")

        return {
            "intercept": intercept,
            "slope": slope,
            "r2": r2,
            "adjusted_r2": adjusted_r2,
            "rmse": rmse,
            "df": df,
            "sigma2": sigma2,
            "covariance": covariance.tolist(),
            "intercept_se": intercept_se,
            "slope_se": slope_se,
            "intercept_t": intercept_t,
            "slope_t": slope_t,
            "intercept_p_value": intercept_p,
            "slope_p_value": slope_p,
            "intercept_ci_95": [
                intercept - t_critical * intercept_se,
                intercept + t_critical * intercept_se,
            ],
            "slope_ci_95": [
                slope - t_critical * slope_se,
                slope + t_critical * slope_se,
            ],
            "equation": f"y = {intercept:.4f} + {slope:.4f}x",
        }

    @staticmethod
    def _predict_mean_ci(
        fit: Dict[str, object],
        line_x: np.ndarray,
    ) -> Dict[str, np.ndarray]:
        beta = np.array([fit["intercept"], fit["slope"]], dtype=float)
        covariance = np.array(fit["covariance"], dtype=float)
        X_new = np.column_stack([np.ones_like(line_x), line_x])
        prediction = X_new @ beta
        se_mean = np.sqrt(np.einsum("ij,jk,ik->i", X_new, covariance, X_new))
        t_critical = _student_t_critical(int(fit["df"])) if int(fit["df"]) > 0 else 1.96

        return {
            "prediction": prediction,
            "lower": prediction - t_critical * se_mean,
            "upper": prediction + t_critical * se_mean,
        }

    @staticmethod
    def _fit_interaction_model(
        x: np.ndarray,
        y: np.ndarray,
        fit_group: np.ndarray,
    ) -> Dict[str, object]:
        is_green = (fit_group == "Green").astype(float)
        X = np.column_stack([np.ones_like(x), x, is_green, x * is_green])
        xtx_inv = np.linalg.inv(X.T @ X)
        beta = xtx_inv @ X.T @ y
        prediction = X @ beta

        n = len(y)
        p = X.shape[1]
        df = n - p
        ss_res = float(np.sum((y - prediction) ** 2))
        ss_tot = float(np.sum((y - y.mean()) ** 2))
        r2 = 1.0 if ss_tot == 0 else 1.0 - ss_res / ss_tot
        adjusted_r2 = 1.0 - (1.0 - r2) * (n - 1) / (n - p) if n > p else r2
        sigma2 = ss_res / df if df > 0 else 0.0
        covariance = sigma2 * xtx_inv
        standard_errors = np.sqrt(np.diag(covariance))
        t_critical = _student_t_critical(df) if df > 0 else 1.96

        coefficient_names = [
            "bluegrey_intercept",
            "bluegrey_slope",
            "intercept_gap_green",
            "slope_gap_green",
        ]
        coefficients: Dict[str, Dict[str, float]] = {}
        for idx, name in enumerate(coefficient_names):
            coef = float(beta[idx])
            se = float(standard_errors[idx])
            t_stat = coef / se if se > 0 else float("inf")
            p_value = _two_sided_t_p_value(t_stat, df) if df > 0 else float("nan")
            coefficients[name] = {
                "coefficient": coef,
                "standard_error": se,
                "t_stat": t_stat,
                "p_value": p_value,
                "ci_95": [
                    coef - t_critical * se,
                    coef + t_critical * se,
                ],
            }

        return {
            "r2": r2,
            "adjusted_r2": adjusted_r2,
            "df": df,
            "sigma2": sigma2,
            "coefficients": coefficients,
        }

    @staticmethod
    def _format_p_value(p_value: float) -> str:
        if math.isnan(p_value):
            return "NA"
        if p_value < 0.001:
            return "<0.001"
        return f"{p_value:.3f}"

    @staticmethod
    def _significance_mark(p_value: float) -> str:
        if math.isnan(p_value):
            return "NA"
        if p_value < 0.001:
            return "***"
        if p_value < 0.01:
            return "**"
        if p_value < 0.05:
            return "*"
        if p_value < 0.10:
            return "†"
        return "ns"

    @staticmethod
    def _draw_stat_panel(
        ax,
        x_left: float,
        y_top: float,
        width: float,
        rows: List[Dict[str, str]],
    ):
        row_heights = []
        for row in rows:
            row_heights.append(0.056 if not row.get("value") else 0.096)

        height = sum(row_heights) + 0.030
        y_bottom = y_top - height
        panel = FancyBboxPatch(
            (x_left, y_bottom),
            width,
            height,
            transform=ax.transAxes,
            boxstyle="round,pad=0.012,rounding_size=0.03",
            linewidth=0.8,
            edgecolor=(1.0, 1.0, 1.0, 0.35),
            facecolor=(1.0, 1.0, 1.0, 0.64),
            zorder=8,
        )
        ax.add_patch(panel)

        cursor_y = y_top - 0.018
        icon_x0 = x_left + 0.028
        icon_x1 = x_left + 0.082
        text_x = x_left + 0.102

        for row, row_height in zip(rows, row_heights):
            icon_y = cursor_y - row_height * 0.42
            if row["icon_style"] == "line":
                ax.plot(
                    [icon_x0, icon_x1],
                    [icon_y, icon_y],
                    transform=ax.transAxes,
                    color=row["accent_color"],
                    linewidth=2.8,
                    solid_capstyle="round",
                    zorder=9,
                    clip_on=False,
                )
                ax.plot(
                    [x_left + 0.055],
                    [icon_y],
                    transform=ax.transAxes,
                    marker="o",
                    markersize=4.8,
                    color=row["accent_color"],
                    markeredgewidth=0.0,
                    zorder=10,
                    clip_on=False,
                )
            else:
                ax.plot(
                    [x_left + 0.055],
                    [icon_y],
                    transform=ax.transAxes,
                    marker="D",
                    markersize=5.0,
                    color=row["accent_color"],
                    markeredgewidth=0.0,
                    zorder=10,
                    clip_on=False,
                )

            ax.text(
                text_x,
                cursor_y - 0.010,
                row["label"],
                transform=ax.transAxes,
                fontsize=9.4,
                fontweight="bold",
                color="#5B6570",
                va="top",
                ha="left",
                zorder=10,
            )
            if row.get("value"):
                ax.text(
                    text_x,
                    cursor_y - row_height * 0.48,
                    row["value"],
                    transform=ax.transAxes,
                    fontsize=10.2,
                    color="#2F343A",
                    va="top",
                    ha="left",
                    linespacing=1.18,
                    zorder=10,
                )
            cursor_y -= row_height

        return panel

    def build_increase_summary_table(self) -> pd.DataFrame:
        summary_df = self.build_summary_table().copy()
        baseline = float(self.traditional_jet_ci_gco2e_per_mj or 89.0)
        summary_df["Emission Increase vs Traditional Jet (g CO2eq/MJ)"] = (
            summary_df["Emission Intensity (g CO2eq/MJ)"] - baseline
        )
        summary_df["Fit Group"] = np.where(
            summary_df["Category"] == "Green",
            "Green",
            "Blue+Grey",
        )
        return summary_df.sort_values(
            by=[
                "Carbon Price (CNY/tCO2)",
                "Fit Group",
                "Emission Increase vs Traditional Jet (g CO2eq/MJ)",
            ]
        ).reset_index(drop=True)

    def plot_two_group_linear_chart(self, summary_df: pd.DataFrame):
        logger.info("\nGenerating two-group linear-fit chart on emission-increase axis...")

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
        fit_group_order = ["Blue+Grey", "Green"]
        panel_label_offsets = {
            2: {
                "DAC-BH-FT": (-85.0, 3.0),
                "CTL-BH": (-72.0, -2.0),
                "CCU-BH-MTJ": (12.0, -2.0),
            }
        }

        for panel_idx, (ax, carbon_scenario) in enumerate(zip(axes, self.carbon_price_scenarios)):
            scenario_df = summary_df[
                summary_df["Carbon Price Scenario"] == carbon_scenario["name"]
            ].copy()

            ax.fill_between([x_min, 0.0], y_min, y_max, color="#F1F8E9", alpha=0.55, zorder=0)
            ax.fill_between([0.0, x_max], y_min, y_max, color="#FFF3E0", alpha=0.55, zorder=0)
            ax.axvline(0.0, color="#999999", linestyle="--", linewidth=1.5, zorder=1)

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
                    alpha=0.92,
                    edgecolors="none",
                    zorder=5,
                )
                offset_x, offset_y = panel_label_offsets.get(panel_idx, {}).get(
                    row["Scenario"],
                    (0.0, 0.0),
                )
                texts.append(
                    ax.text(
                        x + offset_x,
                        y + offset_y,
                        row["Scenario"],
                        fontsize=10.5,
                        color="#333333",
                        zorder=10,
                    )
                )

            scenario_fit_results = {
                "carbon_price_scenario": carbon_scenario["name"],
                "carbon_price_usd_per_t": carbon_scenario["usd_per_t"],
                "carbon_price_cny_per_t": carbon_scenario["cny_per_t"],
                "x_column": x_column,
                "groups": {},
            }

            for fit_group in fit_group_order:
                group_df = scenario_df[scenario_df["Fit Group"] == fit_group]
                x = group_df[x_column].to_numpy(dtype=float)
                y = group_df["Cost With Carbon Price (CNY/kg)"].to_numpy(dtype=float)
                fit = self._fit_linear(x, y)
                if fit is None:
                    continue

                local_span = float(x.max() - x.min())
                padding = max(8.0, local_span * 0.14)
                line_x = np.linspace(float(x.min()) - padding, float(x.max()) + padding, 100)
                band = self._predict_mean_ci(fit, line_x)
                ax.fill_between(
                    line_x,
                    band["lower"],
                    band["upper"],
                    color=self.fit_group_colors[fit_group],
                    alpha=0.13,
                    linewidth=0.0,
                    zorder=2,
                )
                ax.plot(
                    line_x,
                    band["prediction"],
                    color=self.fit_group_colors[fit_group],
                    linewidth=2.8,
                    zorder=4,
                )

                scenario_fit_results["groups"][fit_group] = fit
            interaction_fit = self._fit_interaction_model(
                scenario_df[x_column].to_numpy(dtype=float),
                scenario_df["Cost With Carbon Price (CNY/kg)"].to_numpy(dtype=float),
                scenario_df["Fit Group"].to_numpy(dtype=str),
            )
            scenario_fit_results["interaction_test"] = interaction_fit
            intercept_gap = interaction_fit["coefficients"]["intercept_gap_green"]
            slope_gap = interaction_fit["coefficients"]["slope_gap_green"]

            panel_x_left = 0.24 if panel_idx == 2 else 0.56
            stat_panel = self._draw_stat_panel(
                ax=ax,
                x_left=panel_x_left,
                y_top=0.94,
                width=0.40,
                rows=[
                    {
                        "label": "Blue+Grey pathway",
                        "value": "",
                        "accent_color": self.fit_group_colors["Blue+Grey"],
                        "icon_style": "line",
                    },
                    {
                        "label": "Green pathway",
                        "value": "",
                        "accent_color": self.fit_group_colors["Green"],
                        "icon_style": "line",
                    },
                    {
                        "label": f"Gap test  |  adj. R^2 {interaction_fit['adjusted_r2']:.2f}",
                        "value": (
                            f"level@x=0  {self._format_p_value(intercept_gap['p_value'])} "
                            f"{self._significance_mark(intercept_gap['p_value'])}\n"
                            f"slope gap  {self._format_p_value(slope_gap['p_value'])} "
                            f"{self._significance_mark(slope_gap['p_value'])}"
                        ),
                        "accent_color": "#C6852D",
                        "icon_style": "diamond",
                    },
                ],
            )

            if adjust_text and panel_idx != 2:
                try:
                    adjust_text(
                        texts,
                        objects=[stat_panel],
                        ax=ax,
                        arrowprops=dict(arrowstyle="-", color="#666666", lw=0.8),
                        force_text=(0.5, 1.0),
                        force_static=(1.0, 1.5),
                        force_pull=(0.1, 0.1),
                        force_explode=(0.1, 0.5),
                        expand=(1.2, 1.4),
                        max_move=(40, 40),
                        ensure_inside_axes=True,
                        iter_lim=1200,
                    )
                except Exception as exc:
                    logger.warning("adjust_text failed for %s: %s", carbon_scenario["name"], exc)

            fit_results.append(scenario_fit_results)

            ax.text(
                x_min / 2.0,
                y_max + 0.35,
                "Relative reduction vs traditional jet",
                fontsize=12,
                ha="center",
                va="bottom",
                fontweight="bold",
                color="#555555",
            )
            ax.text(
                x_max / 2.0,
                y_max + 0.35,
                "Relative increase vs traditional jet",
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
                pad=22,
                y=1.03,
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
                color=self.fit_group_colors["Blue+Grey"],
                linewidth=2.8,
                label="Blue+Grey linear fit",
            ),
            Line2D(
                [0],
                [0],
                color=self.fit_group_colors["Green"],
                linewidth=2.8,
                label="Green linear fit",
            ),
            Patch(
                facecolor="#90A4AE",
                edgecolor="none",
                alpha=0.18,
                label="95% confidence band",
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
            ncol=4,
            fontsize=11,
            framealpha=0.85,
            edgecolor="#CCCCCC",
            facecolor="white",
        )

        fig.suptitle(
            "Two Group-wise Linear Fits with 95% Confidence Bands: Green vs Blue+Grey",
            fontsize=18,
            fontweight="bold",
            y=0.98,
        )
        fig.supxlabel(
            "Emission increase vs traditional jet (g CO2eq/MJ)",
            fontsize=14,
            fontweight="bold",
            y=0.058,
        )
        fig.text(
            0.5,
            0.015,
            "Significance codes: *** p<0.001, ** p<0.01, * p<0.05, † p<0.10",
            ha="center",
            va="bottom",
            fontsize=10,
            color="#666666",
        )
        fig.tight_layout(rect=(0.02, 0.08, 0.93, 0.94))

        output_path = self.session_dir / "cost_increase_two_group_linear.png"
        latest_path = self.output_dir / "cost_increase_two_group_linear_latest.png"
        plt.savefig(output_path, dpi=300, bbox_inches="tight", facecolor="white")
        plt.savefig(latest_path, dpi=300, bbox_inches="tight", facecolor="white")
        plt.close()

        logger.info("Saved two-group linear chart: %s", output_path)
        return output_path, fit_results

    def save_summary(self, summary_df: pd.DataFrame):
        summary_path = self.session_dir / "cost_increase_two_group_linear_summary.csv"
        summary_df.to_csv(summary_path, index=False, encoding="utf-8-sig")
        logger.info("Saved two-group linear summary: %s", summary_path)
        return summary_path

    def save_metadata(self, fit_results: List[dict]):
        metadata = {
            "x_definition": "emission_increase = pathway_carbon_intensity - traditional_jet_baseline",
            "fit_group_definition": {
                "Green": "original Green category only",
                "Blue+Grey": "original Blue and Grey categories combined",
            },
            "confidence_band": "95% confidence interval for mean fitted line",
            "significance_test": (
                "interaction model: cost = beta0 + beta1*x + beta2*Green + beta3*(x*Green); "
                "beta2 tests level gap at x=0, beta3 tests slope gap"
            ),
            "fit_results": fit_results,
        }
        metadata_path = self.session_dir / "cost_increase_two_group_linear_metadata.json"
        with open(metadata_path, "w", encoding="utf-8") as handle:
            json.dump(metadata, handle, ensure_ascii=False, indent=2)
        logger.info("Saved two-group linear metadata: %s", metadata_path)
        return metadata_path

    def run(self):
        self.load_data()
        summary_df = self.build_increase_summary_table()
        chart_path, fit_results = self.plot_two_group_linear_chart(summary_df)
        summary_path = self.save_summary(summary_df)
        metadata_path = self.save_metadata(fit_results)
        return {
            "chart_path": chart_path,
            "summary_path": summary_path,
            "metadata_path": metadata_path,
            "fit_results": fit_results,
        }


def main():
    visualizer = CostIncreaseTwoGroupLinearVisualizer(
        carbon_price_scenarios=SSP_CARBON_PRICE_SCENARIOS
    )
    result = visualizer.run()

    logger.info("=" * 60)
    logger.info("Two-group linear visualization completed")
    logger.info("Chart: %s", result["chart_path"])
    logger.info("Summary: %s", result["summary_path"])
    logger.info("Metadata: %s", result["metadata_path"])
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
