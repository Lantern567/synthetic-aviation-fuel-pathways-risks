# -*- coding: utf-8 -*-
"""
三个帕累托最优路径的低利用率惩罚 / 不稳健性惩罚可视化

图形结构：
- (a) 横向堆叠条形图：分解 chronic low-utilization penalty 与 robustness penalty
- (b) penalty space：横轴 chronic，纵轴 robustness，点大小表示 total penalty
"""

import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import List

MPL_CONFIG_DIR = Path("/tmp") / f"matplotlib-cache-{os.getuid()}"
MPL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
os.environ["MPLCONFIGDIR"] = str(MPL_CONFIG_DIR)

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch

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
    plt.rcParams["font.size"] = 11.0
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["pdf.fonttype"] = 42
    plt.rcParams["ps.fonttype"] = 42
    plt.rcParams["mathtext.fontset"] = "stix"


class ParetoPenaltyVisualizer:
    DEFAULT_SCENARIOS = ["GTL-BH", "GTL", "CCU-GH-FT"]
    FIGURE_FONT_SIZE = 12.0
    SCENARIO_ALIASES = {
        "GTL-BH-MTJ": "GTL-BH",
        "GTL-GH-FT": "GTL",
    }

    def __init__(self, output_dir: Path = None):
        self.output_dir = Path(output_dir) if output_dir is not None else RESULT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = self.output_dir / f"pareto_penalty_{timestamp}"
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
    def _bubble_size(values: pd.Series) -> np.ndarray:
        values = values.astype(float)
        vmin = float(values.min())
        vmax = float(values.max())
        if vmax - vmin <= 1e-12:
            return np.full(len(values), 520.0)
        norm = (values - vmin) / (vmax - vmin)
        return 140.0 + np.power(norm, 1.15) * 900.0

    def _build_frame(self) -> pd.DataFrame:
        selected = self._load_selected_scenarios()
        metrics = self._load_metrics()
        metrics["Scenario"] = metrics["Scenario"].astype(str).replace(self.SCENARIO_ALIASES)

        frame = metrics[metrics["Scenario"].isin(selected)].copy()
        if frame.empty:
            raise RuntimeError("未找到三个帕累托路径对应的 penalty 指标")

        frame["Scenario"] = pd.Categorical(frame["Scenario"], categories=selected, ordered=True)
        frame = frame.sort_values("Scenario").reset_index(drop=True)
        frame["BubbleSize"] = self._bubble_size(frame["TotalPenaltyPct"])
        return frame

    def _export_transparent_legend(self, handles):
        legend_fig, legend_ax = plt.subplots(figsize=(5.6, 0.9))
        legend_ax.axis("off")
        legend_fig.patch.set_alpha(0.0)
        legend_ax.patch.set_alpha(0.0)
        legend_ax.legend(
            handles=handles,
            loc="center",
            ncol=2,
            frameon=False,
            fontsize=self.FIGURE_FONT_SIZE,
            columnspacing=1.8,
            handlelength=2.3,
        )

        legend_path = self.session_dir / "pareto_penalty_legend_transparent.png"
        latest_legend_path = self.output_dir / "pareto_penalty_legend_transparent_latest.png"
        legend_fig.savefig(
            legend_path,
            dpi=600,
            bbox_inches="tight",
            pad_inches=0.02,
            transparent=True,
        )
        legend_fig.savefig(
            latest_legend_path,
            dpi=600,
            bbox_inches="tight",
            pad_inches=0.02,
            transparent=True,
        )
        plt.close(legend_fig)
        logger.info("保存透明图例: %s", legend_path)

    @staticmethod
    def _annotate_points(ax, frame: pd.DataFrame):
        label_offsets = {
            "GTL-BH": (8, 5, "left", "bottom"),
            "GTL": (7, 7, "left", "bottom"),
            "CCU-GH-FT": (-9, 8, "right", "bottom"),
        }
        for _, row in frame.iterrows():
            dx, dy, ha, va = label_offsets.get(
                str(row["Scenario"]),
                (8, 6, "left", "bottom"),
            )
            ax.annotate(
                row["Scenario"],
                (float(row["ChronicPenaltyPct"]), float(row["RobustnessPenaltyPct"])),
                xytext=(dx, dy),
                textcoords="offset points",
                ha=ha,
                va=va,
                fontsize=ParetoPenaltyVisualizer.FIGURE_FONT_SIZE,
                color="black",
            )

    @staticmethod
    def _save_figure_bundle(fig: plt.Figure, session_path: Path, latest_path: Path) -> None:
        for suffix in (".png", ".pdf", ".svg"):
            current_session_path = session_path.with_suffix(suffix)
            current_latest_path = latest_path.with_suffix(suffix)
            fig.savefig(current_session_path, dpi=600, bbox_inches="tight", pad_inches=0.035)
            shutil.copy2(current_session_path, current_latest_path)

    @staticmethod
    def _style_axes(ax: plt.Axes) -> None:
        ax.tick_params(axis="both", labelsize=ParetoPenaltyVisualizer.FIGURE_FONT_SIZE, colors="black")
        ax.grid(True, linestyle="--", linewidth=0.65, alpha=0.18, dashes=(4, 4))
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        for spine in ax.spines.values():
            spine.set_linewidth(0.9)
            spine.set_color("black")

    def create_figure(self, frame: pd.DataFrame):
        chronic_color = "#9DB7CE"
        robustness_color = "#3F6F8F"
        dominance_shade = "#E8EEF4"

        fig, (ax1, ax2) = plt.subplots(
            1, 2,
            figsize=(11.2, 5.2),
            gridspec_kw={"width_ratios": [1.18, 1.0]},
        )

        # (a) stacked penalty decomposition
        y_pos = np.arange(len(frame))
        x_max = max(160.0, float(np.nanmax(frame["TotalPenaltyPct"])) + 16.0)
        ax1.axvspan(0, 40, color="#F3F7FA", alpha=0.22, zorder=0)
        ax1.axvspan(40, 80, color="#EEF3F7", alpha=0.18, zorder=0)
        ax1.axvspan(80, x_max, color="#E8EEF4", alpha=0.18, zorder=0)
        ax1.axvline(100, color="#64748B", linestyle="--", linewidth=0.9, alpha=0.70, zorder=1)

        for idx, row in frame.iterrows():
            chronic = float(row["ChronicPenaltyPct"])
            robustness = float(row["RobustnessPenaltyPct"])
            total = float(row["TotalPenaltyPct"])
            share = float(row["RobustnessSharePct"])

            ax1.barh(idx, chronic, height=0.64, color=chronic_color, edgecolor="white", linewidth=1.0, zorder=2)
            ax1.barh(
                idx,
                robustness,
                left=chronic,
                height=0.64,
                color=robustness_color,
                edgecolor="white",
                linewidth=1.0,
                zorder=2,
            )
            ax1.scatter(
                total,
                idx,
                s=64,
                color=row["Color"],
                edgecolors="white",
                linewidths=1.0,
                zorder=4,
            )
            ax1.text(
                total + 2.2,
                idx,
                f"{total:.1f}%",
                va="center",
                ha="left",
                fontsize=self.FIGURE_FONT_SIZE,
                color="black",
            )
            ax1.text(
                max(total * 0.52, chronic + robustness * 0.48),
                idx,
                f"{share:.0f}%",
                va="center",
                ha="center",
                fontsize=self.FIGURE_FONT_SIZE,
                color="black",
                zorder=5,
            )

        ax1.set_yticks(y_pos)
        ax1.set_yticklabels(frame["Scenario"].tolist(), fontsize=self.FIGURE_FONT_SIZE)
        for tick_label in ax1.get_yticklabels():
            tick_label.set_color("black")
        ax1.invert_yaxis()
        ax1.set_xlim(0, x_max)
        ax1.grid(True, axis="x", linestyle="--", linewidth=0.65, alpha=0.18, dashes=(4, 4))
        ax1.set_title("(b) Penalty decomposition", fontsize=self.FIGURE_FONT_SIZE, fontweight="bold", loc="left", pad=10, color="black")
        ax1.set_xlabel("Implied cost penalty relative to full utilization (%)", fontsize=self.FIGURE_FONT_SIZE, fontweight="bold", color="black")
        self._style_axes(ax1)

        # (b) penalty space
        x_max2 = max(118.0, float(np.nanmax(frame["ChronicPenaltyPct"])) + 18.0)
        y_max2 = max(65.0, float(np.nanmax(frame["RobustnessPenaltyPct"])) + 8.0)
        diag_max = min(x_max2, y_max2)
        x_fill = np.linspace(0.0, diag_max, 300)
        ax2.fill_between(x_fill, x_fill, np.full_like(x_fill, y_max2), color=dominance_shade, alpha=0.32, zorder=0)
        ax2.plot([0, diag_max], [0, diag_max], linestyle="--", linewidth=1.0, color="#64748B", zorder=1)

        for _, row in frame.iterrows():
            ax2.scatter(
                float(row["ChronicPenaltyPct"]),
                float(row["RobustnessPenaltyPct"]),
                s=float(row["BubbleSize"]),
                color=row["Color"],
                edgecolors="white",
                linewidths=1.2,
                alpha=0.88,
                zorder=4,
            )

        self._annotate_points(ax2, frame)

        ax2.set_title("(c) Penalty space", fontsize=self.FIGURE_FONT_SIZE, fontweight="bold", loc="left", pad=10, color="black")
        ax2.set_xlabel("Chronic low-utilization penalty (%)", fontsize=self.FIGURE_FONT_SIZE, fontweight="bold", color="black")
        ax2.set_ylabel("Additional instability penalty (%)", fontsize=self.FIGURE_FONT_SIZE, fontweight="bold", color="black")
        ax2.set_xlim(0, x_max2)
        ax2.set_ylim(0, y_max2)
        self._style_axes(ax2)
        ax2.text(0.96, 0.96, "Instability-dominant", transform=ax2.transAxes, ha="right", va="top", fontsize=self.FIGURE_FONT_SIZE, color="black")
        ax2.text(0.96, 0.04, "Low-utilization-dominant", transform=ax2.transAxes, ha="right", va="bottom", fontsize=self.FIGURE_FONT_SIZE, color="black")

        handles = [
            Patch(facecolor=chronic_color, edgecolor="none", label="Chronic low-utilization penalty"),
            Patch(facecolor=robustness_color, edgecolor="none", label="Robustness penalty"),
        ]
        fig.legend(
            handles=handles,
            loc="upper center",
            bbox_to_anchor=(0.5, 1.01),
            ncol=2,
            frameon=False,
            fontsize=self.FIGURE_FONT_SIZE,
            columnspacing=1.5,
            handlelength=2.3,
        )

        fig.text(
            0.5,
            0.01,
            "Chronic penalty = (100 / mean SAF utilization - 1) x 100%; robustness penalty = (100 / worst-week SAF utilization - 100 / mean SAF utilization) x 100%.",
            ha="center",
            va="bottom",
            fontsize=10.0,
            color="black",
        )

        fig.tight_layout(rect=[0.02, 0.05, 0.98, 0.93])

        output_path = self.session_dir / "pareto_penalty_comparison.png"
        latest_path = self.output_dir / "pareto_penalty_comparison_latest.png"
        self._save_figure_bundle(fig, output_path, latest_path)
        self._export_transparent_legend(handles)
        plt.close(fig)
        logger.info("保存图片: %s", output_path)

    def export_summary(self, frame: pd.DataFrame):
        summary_cols = [
            "Scenario",
            "Category",
            "Pathway",
            "LCOE",
            "SAFMean",
            "WorstWeekMean",
            "ChronicPenaltyPct",
            "RobustnessPenaltyPct",
            "TotalPenaltyPct",
            "RobustnessSharePct",
        ]
        summary = frame[summary_cols].copy()
        output_path = self.session_dir / "pareto_penalty_summary.csv"
        latest_path = self.output_dir / "pareto_penalty_summary_latest.csv"
        summary.to_csv(output_path, index=False, encoding="utf-8-sig")
        summary.to_csv(latest_path, index=False, encoding="utf-8-sig")
        logger.info("保存汇总: %s", output_path)

    def run(self):
        frame = self._build_frame()
        self.create_figure(frame)
        self.export_summary(frame)


def main():
    visualizer = ParetoPenaltyVisualizer()
    visualizer.run()


if __name__ == "__main__":
    main()
