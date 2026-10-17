import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


COLORS = {"blue": "#3C5488", "green": "#00A087", "orange": "#E64B35", "vermillion": "#F39B7F", "gray": "#6B7280"}
CATEGORY = {"Grey": "#616161", "Blue": "#1565C0", "Green": "#2E7D32"}
RC = {"font.family": "sans-serif", "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
      "axes.unicode_minus": False, "font.size": 8, "axes.labelsize": 8.5, "xtick.labelsize": 7, "ytick.labelsize": 7,
      "axes.linewidth": .7, "legend.fontsize": 6.8, "legend.frameon": False,
      "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none", "figure.facecolor": "white"}


def style(axis, panel, grid="y"):
    for side in ["top", "right"]:
        axis.spines[side].set_visible(False)
    for side in ["left", "bottom"]:
        axis.spines[side].set_color("#CBD5E1")
    axis.tick_params(axis="both", colors="#334155", labelsize=7, direction="out", length=4, width=.8)
    axis.grid(axis=grid, color="#CBD5E1", linewidth=.8, linestyle="--", alpha=.3)
    axis.set_axisbelow(True)
    axis.text(-.12, 1.04, f"({panel})", transform=axis.transAxes, fontsize=10, fontweight="bold", va="bottom", clip_on=False)


def save(figure, output, stem):
    for suffix in [".png", ".pdf", ".svg"]:
        figure.savefig(output / (stem + suffix), dpi=300, bbox_inches="tight", pad_inches=.04, facecolor="white")
    plt.close(figure)


def draw_overview(metrics, output):
    with plt.rc_context(RC):
        figure = plt.figure(figsize=(7.2, 5.4), dpi=300)
        grid = figure.add_gridspec(2, 2, left=.08, right=.985, top=.965, bottom=.12, wspace=.30, hspace=.34)
        axis = figure.add_subplot(grid[0, 0])
        axis.scatter(metrics.WorstWeekRetention, metrics.TotalPenaltyPct, s=np.clip(metrics.LCOE * 2, 18, 120),
                     c=metrics.Category.map(CATEGORY), edgecolors="white", linewidth=.7)
        axis.set(xlabel="Worst-week retention (%)", ylabel="Total capacity premium (%)")
        style(axis, "a")
        axis = figure.add_subplot(grid[0, 1])
        ordered = metrics.sort_values("WorstWeekRetention")
        axis.barh(np.arange(len(ordered)), ordered.WorstWeekRetention, color=ordered.Category.map(CATEGORY), alpha=.85, edgecolor="white")
        axis.set_yticks(np.arange(len(ordered)), ordered.Scenario)
        axis.invert_yaxis()
        axis.set_xlabel("Worst-week retention (%)")
        style(axis, "b", "x")
        axis = figure.add_subplot(grid[1, 0])
        axis.scatter(metrics.ChronicPenaltyPct, metrics.RobustnessPenaltyPct, s=42, c=metrics.Category.map(CATEGORY), edgecolors="white", linewidth=.7)
        limit = max(metrics.ChronicPenaltyPct.max(), metrics.RobustnessPenaltyPct.max())
        axis.plot([0, limit], [0, limit], linestyle="--", color="#94A3B8", linewidth=.8)
        axis.set(xlabel="Mean-utilization capacity premium (%)", ylabel="Additional worst-week premium (%)")
        style(axis, "c")
        axis = figure.add_subplot(grid[1, 1])
        axis.scatter(metrics.MaxLowRunHours, metrics.SAFMean, s=np.clip(metrics.LowLoadEpisodes12h.fillna(0) * 8 + 18, 18, 130),
                     c=metrics.Category.map(CATEGORY), edgecolors="white", linewidth=.7)
        axis.set(xlabel="Longest low-load event (h)", ylabel="Mean SynAF utilization (%)")
        style(axis, "d")
        save(figure, output, "Figure_S31")


def draw_weekly_comparison(metrics, output, selected):
    data = metrics.set_index("Scenario").loc[selected]
    with plt.rc_context(RC):
        figure = plt.figure(figsize=(7.2, 4.1), dpi=300)
        grid = figure.add_gridspec(1, 2, left=.08, right=.985, top=.88, bottom=.18, wspace=.30)
        axis = figure.add_subplot(grid[0, 0])
        x = np.arange(len(data))
        axis.bar(x, data.ChronicPenaltyPct, color=COLORS["blue"], alpha=.85, edgecolor="white", label="Mean-utilization\npremium")
        axis.bar(x, data.RobustnessPenaltyPct, bottom=data.ChronicPenaltyPct, color=COLORS["orange"], alpha=.85, edgecolor="white", label="Additional worst-week\npremium")
        axis.set_xticks(x, selected)
        axis.set_ylabel("Capacity premium over full utilization (%)")
        axis.legend(loc="upper center", bbox_to_anchor=(.5, 1.22), ncol=2)
        for position, (_, row) in enumerate(data.iterrows()):
            axis.text(position, row.TotalPenaltyPct + 2, f"{row.TotalPenaltyPct:.1f}", ha="center", fontsize=6.8, color="#334155")
        style(axis, "a")
        axis = figure.add_subplot(grid[0, 1])
        palette = [COLORS["green"], COLORS["blue"], COLORS["vermillion"]]
        weekly_rows = []
        for name, color in zip(selected, palette):
            row = data.loc[name]
            premiums = [(100 / row[f"W{week}Mean"] - 100 / row.SAFMean) * 100 for week in range(1, 5)]
            axis.plot(range(4), premiums, marker="o", markersize=4, linewidth=1.4, color=color, label=name)
            weekly_rows.extend({"Scenario": name, "Week": f"W{week}", "WeekPenaltyLift": value} for week, value in enumerate(premiums, 1))
        axis.set_xticks(range(4), ["W1", "W2", "W3", "W4"])
        axis.set_ylabel("Capacity premium relative to mean (%)")
        axis.axhline(0, color="#94A3B8", linewidth=.8)
        axis.legend(loc="upper center", bbox_to_anchor=(.5, 1.22), ncol=3)
        style(axis, "b")
        save(figure, output, "Figure_S32")
        pd.DataFrame(weekly_rows).to_csv(output / "penalty_class_weekly_metrics_latest.csv", index=False)
