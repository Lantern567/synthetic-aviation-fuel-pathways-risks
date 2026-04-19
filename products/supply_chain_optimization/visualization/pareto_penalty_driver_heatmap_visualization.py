# -*- coding: utf-8 -*-
"""
三个帕累托最优路径的 penalty driver fingerprint heatmap

设计思路：
- 不对 3 个样本直接计算相关系数
- 使用 13 条路径的全局分布做标准化
- 仅展示 3 条帕累托路径在关键 driver/outcome 上的相对位置
"""

import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

MPL_CONFIG_DIR = Path("/tmp") / f"matplotlib-cache-{os.getuid()}"
MPL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
os.environ["MPLCONFIGDIR"] = str(MPL_CONFIG_DIR)

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from temporal_robustness_space_visualization import TemporalRobustnessSpaceVisualizer


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)
logging.getLogger("fontTools").setLevel(logging.WARNING)


PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
RESULT_DIR = PROJECT_ROOT / "products" / "supply_chain_optimization" / "visualization" / "results"


def setup_fonts():
    plt.rcParams["font.family"] = ["serif"]
    plt.rcParams["font.serif"] = ["Times New Roman", "DejaVu Serif", "SimSun"]
    plt.rcParams["font.sans-serif"] = ["Times New Roman", "DejaVu Serif", "SimSun"]
    plt.rcParams["font.size"] = 12.0
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["pdf.fonttype"] = 42
    plt.rcParams["ps.fonttype"] = 42
    plt.rcParams["mathtext.fontset"] = "stix"


class ParetoPenaltyDriverHeatmapVisualizer:
    DEFAULT_SCENARIOS = ["GTL-BH", "GTL", "CCU-GH-FT"]
    FIGURE_FONT_SIZE = 12.0
    CELL_FONT_SIZE = 17
    GROUP_FONT_SIZE = 12.4
    COLORBAR_TICK_SIZE = 14.0
    SCENARIO_ALIASES = {
        "GTL-BH-MTJ": "GTL-BH",
        "GTL-GH-FT": "GTL",
    }

    DRIVER_GROUPS: List[Tuple[str, List[Tuple[str, str, str]]]] = [
        (
            "Low-utilization drivers",
            [
                ("SAFMean", "Mean SAF", "percent_inv"),
                ("LowLoadEpisodes12h", "Episodes\n>12h", "count"),
                ("MeanLowRunHours", "Mean run h", "hours"),
            ],
        ),
        (
            "Instability drivers",
            [
                ("WorstWeekRetention", "Worst-week\nret.", "percent_inv"),
                ("WeekCV", "Week CV", "percent"),
                ("MaxLowRunHours", "Max run h", "hours"),
            ],
        ),
        (
            "Renewable shock",
            [
                ("RenewPowerCV", "Power CV", "percent"),
                ("RenewZeroPct", "Zero-\noutput", "percent"),
                ("RenewRampPct", "Ramp\nintensity", "percent"),
            ],
        ),
        (
            "Penalty outcome",
            [
                ("ChronicPenaltyPct", "Chronic", "percent"),
                ("RobustnessPenaltyPct", "Robustness", "percent"),
                ("TotalPenaltyPct", "Total", "percent"),
            ],
        ),
    ]

    def __init__(self, output_dir: Path = None):
        self.output_dir = Path(output_dir) if output_dir is not None else RESULT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = self.output_dir / f"pareto_penalty_driver_heatmap_{timestamp}"
        self.session_dir.mkdir(parents=True, exist_ok=True)

        setup_fonts()
        logger.info("输出目录: %s", self.session_dir)

    def _load_selected_scenarios(self) -> List[str]:
        summary_path = self.output_dir / "pareto_temporal_distribution_summary_latest.csv"
        if summary_path.exists():
            df = pd.read_csv(summary_path)
            scenarios = [
                self.SCENARIO_ALIASES.get(str(item), str(item))
                for item in df["scenario"].tolist()
                if pd.notna(item)
            ]
            if scenarios:
                return scenarios
        return self.DEFAULT_SCENARIOS.copy()

    def _load_metrics(self) -> pd.DataFrame:
        metrics_path = self.output_dir / "temporal_robustness_metrics_latest.csv"
        if metrics_path.exists():
            logger.info("读取现有稳健性指标表: %s", metrics_path)
            return pd.read_csv(metrics_path)

        logger.info("未找到现有稳健性指标表，开始重新计算")
        builder = TemporalRobustnessSpaceVisualizer()
        return builder.build_metric_table()

    @staticmethod
    def _risk_oriented_zscore(series: pd.Series, mode: str) -> pd.Series:
        clean = pd.to_numeric(series, errors="coerce")
        mean_val = clean.mean()
        std_val = clean.std(ddof=0)
        if not np.isfinite(std_val) or std_val <= 1e-12:
            z = pd.Series(np.zeros(len(clean)), index=clean.index)
        else:
            z = (clean - mean_val) / std_val

        # *_inv 表示“数值越高越好”，因此风险方向取反
        if mode.endswith("_inv"):
            z = -z
        return z.clip(-2.0, 2.0)

    @staticmethod
    def _format_value(value: float, mode: str) -> str:
        if not np.isfinite(value):
            return "NA"
        if mode.startswith("percent"):
            return f"{value:.0f}%"
        if mode == "hours":
            return f"{value:.0f}h"
        if mode == "count":
            return f"{value:.0f}"
        return f"{value:.2f}"

    def _build_matrices(self) -> Tuple[pd.DataFrame, pd.DataFrame, List[str], List[str], Dict[str, str]]:
        selected = self._load_selected_scenarios()
        all_metrics = self._load_metrics()

        all_metrics = all_metrics.copy()
        all_metrics["Scenario"] = all_metrics["Scenario"].astype(str).replace(self.SCENARIO_ALIASES)
        selected_frame = all_metrics[all_metrics["Scenario"].isin(selected)].copy()
        if selected_frame.empty:
            raise RuntimeError("未找到三个帕累托路径对应的 driver 指标")

        selected_frame["Scenario"] = pd.Categorical(selected_frame["Scenario"], categories=selected, ordered=True)
        selected_frame = selected_frame.sort_values("Scenario").reset_index(drop=True)

        column_keys: List[str] = []
        column_labels: List[str] = []
        column_modes: Dict[str, str] = {}
        for _, items in self.DRIVER_GROUPS:
            for key, label, mode in items:
                column_keys.append(key)
                column_labels.append(label)
                column_modes[key] = mode

        risk_matrix = pd.DataFrame(index=selected_frame["Scenario"].tolist(), columns=column_keys, dtype=float)
        value_matrix = pd.DataFrame(index=selected_frame["Scenario"].tolist(), columns=column_keys, dtype=float)

        for key in column_keys:
            risk_series = self._risk_oriented_zscore(all_metrics[key], column_modes[key])
            risk_lookup = dict(zip(all_metrics["Scenario"], risk_series))
            value_lookup = dict(zip(all_metrics["Scenario"], pd.to_numeric(all_metrics[key], errors="coerce")))

            for scenario in selected_frame["Scenario"].astype(str):
                risk_matrix.loc[scenario, key] = risk_lookup.get(scenario, np.nan)
                value_matrix.loc[scenario, key] = value_lookup.get(scenario, np.nan)

        color_lookup = dict(zip(all_metrics["Scenario"], all_metrics["Color"]))
        return risk_matrix, value_matrix, column_keys, column_labels, color_lookup

    def create_figure(self):
        risk_matrix, value_matrix, column_keys, column_labels, color_lookup = self._build_matrices()

        fig = plt.figure(figsize=(16.2, 7.2))
        grid = fig.add_gridspec(nrows=2, ncols=1, height_ratios=[12.0, 1.75], hspace=0.30)
        ax = fig.add_subplot(grid[0, 0])
        group_ax = fig.add_subplot(grid[1, 0], sharex=ax)
        n_rows = len(risk_matrix.index)
        n_cols = len(column_keys)
        display_risk = (risk_matrix / 2.0).clip(-1.0, 1.0)
        mode_lookup = {
            key: mode
            for _, items in self.DRIVER_GROUPS
            for key, _, mode in items
        }

        ax.set_facecolor("white")

        start = 0
        for group_name, items in self.DRIVER_GROUPS:
            end = start + len(items)
            group_ax.text(
                (start + end - 1) / 2.0,
                0.36,
                group_name,
                ha="center",
                va="center",
                fontsize=self.GROUP_FONT_SIZE,
                fontweight="bold",
                color="black",
            )
            start = end

        for boundary in range(3, n_cols, 3):
            ax.axvline(
                boundary - 0.5,
                color="#B8BDC7",
                linestyle="--",
                linewidth=1.15,
                dashes=(4, 4),
                alpha=0.95,
                zorder=1,
            )

        x_coords, y_coords, colors, sizes = [], [], [], []
        for i, scenario in enumerate(risk_matrix.index):
            for j, key in enumerate(column_keys):
                risk = display_risk.loc[scenario, key]
                if not np.isfinite(risk):
                    continue
                x_coords.append(j)
                y_coords.append(i)
                colors.append(risk)
                sizes.append(480 + (abs(risk) ** 1.15) * 3300)

        scatter = ax.scatter(
            x_coords,
            y_coords,
            c=colors,
            s=sizes,
            cmap="RdBu_r",
            vmin=-1.0,
            vmax=1.0,
            alpha=0.94,
            edgecolors="none",
            zorder=3,
        )

        # 单元格数字直接覆盖在气泡上
        for i, scenario in enumerate(risk_matrix.index):
            for j, key in enumerate(column_keys):
                value = value_matrix.loc[scenario, key]
                risk = display_risk.loc[scenario, key]
                text_color = "white" if np.isfinite(risk) and abs(risk) >= 0.58 else "#111111"
                ax.text(
                    j,
                    i,
                    self._format_value(value, mode_lookup[key]),
                    ha="center",
                    va="center",
                    fontsize=self.CELL_FONT_SIZE,
                    color=text_color,
                    zorder=4,
                )

        ax.set_xlim(-0.5, n_cols - 0.5)
        ax.set_ylim(n_rows - 0.5, -0.5)
        ax.set_xticks(np.arange(n_cols))
        ax.set_xticklabels(column_labels, fontsize=self.FIGURE_FONT_SIZE, rotation=0, ha="center", color="black")
        ax.set_yticks(np.arange(n_rows))
        ax.set_yticklabels(risk_matrix.index.tolist(), fontsize=self.FIGURE_FONT_SIZE)
        for tick_label in ax.get_yticklabels():
            tick_label.set_color("black")
            tick_label.set_fontweight("bold")
        ax.tick_params(axis="x", bottom=False, top=False, labelbottom=True, pad=14, colors="black")
        ax.tick_params(axis="y", left=False)

        for spine in ax.spines.values():
            spine.set_visible(False)

        group_ax.set_ylim(0.0, 1.0)
        group_ax.set_xlim(-0.5, n_cols - 0.5)
        group_ax.axis("off")

        ax.set_title(
            "(d) Penalty driver fingerprint",
            fontsize=14.0,
            fontweight="bold",
            loc="left",
            pad=18,
            color="black",
        )

        cbar = plt.colorbar(scatter, ax=ax, fraction=0.034, pad=0.018)
        cbar.set_label("Normalized penalty-proneness", fontsize=self.FIGURE_FONT_SIZE, color="black")
        cbar.set_ticks([-1.0, 0.0, 1.0])
        cbar.ax.tick_params(labelsize=self.COLORBAR_TICK_SIZE, colors="black")
        cbar.outline.set_visible(False)

        fig.text(
            0.5,
            0.01,
            "Red indicates a stronger penalty-prone driver profile relative to the 13-pathway baseline; blue indicates a milder profile. Mean SAF utilization and worst-week retention are reverse-oriented so that lower values appear redder.",
            ha="center",
            va="bottom",
            fontsize=10.8,
            color="black",
        )

        fig.subplots_adjust(left=0.075, right=0.935, top=0.875, bottom=0.135)

        output_path = self.session_dir / "pareto_penalty_driver_heatmap.png"
        latest_path = self.output_dir / "pareto_penalty_driver_heatmap_latest.png"
        for suffix in (".png", ".pdf", ".svg"):
            current_output = output_path.with_suffix(suffix)
            current_latest = latest_path.with_suffix(suffix)
            fig.savefig(current_output, dpi=600, bbox_inches="tight", pad_inches=0.035)
            shutil.copy2(current_output, current_latest)
        plt.close(fig)
        logger.info("保存图片: %s", output_path)

        summary_path = self.session_dir / "pareto_penalty_driver_heatmap_values.csv"
        latest_summary_path = self.output_dir / "pareto_penalty_driver_heatmap_values_latest.csv"
        value_matrix.reset_index(names="Scenario").to_csv(summary_path, index=False, encoding="utf-8-sig")
        value_matrix.reset_index(names="Scenario").to_csv(latest_summary_path, index=False, encoding="utf-8-sig")
        logger.info("保存汇总: %s", summary_path)

    def run(self):
        self.create_figure()


def main():
    visualizer = ParetoPenaltyDriverHeatmapVisualizer()
    visualizer.run()


if __name__ == "__main__":
    main()
