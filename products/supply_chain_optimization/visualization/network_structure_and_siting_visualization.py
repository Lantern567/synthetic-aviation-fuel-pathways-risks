# -*- coding: utf-8 -*-
"""
Combined visualization of Network Structure Radar Charts and Facility Siting Counts.
Generates a 2-row x 4-column figure:
- Top Row: Radar charts for Clusters 0-3 (Network Metrics).
- Bottom Row: Combined bar charts for Clusters 0-3 (Co-location & Facility Counts).
Adheres to Applied Energy aesthetic standards.
"""
from __future__ import annotations

import csv
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd

# -----------------------------------------------------------------------------
# CONSTANTS & CONFIGURATION
# -----------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
VIS_ROOT = PROJECT_ROOT / "products/supply_chain_optimization/visualization"

# Metrics CSV (Shared)
DEFAULT_METRICS_CSV = VIS_ROOT / (
    "results/network_classification_20260127_210416/scenario_network_metrics.csv"
)

# Solutions Directory (for Siting Counts)
DEFAULT_SOLUTIONS_DIR = VIS_ROOT / "results/collected_latest_data"

# Co-location Classification CSV
DEFAULT_CLASSIFICATION_CSV = VIS_ROOT / (
    "results/network_siting_clusters_20260128_002014/scenario_decision_point_classification_counts.csv"
)

# Scenario Name Mapping
SCENARIO_NAME_MAP: Dict[str, str] = {
    "Coal Hydrogen": "CTL",
    "Byproduct H2 + Coal": "CTL-BH",
    "Natural Gas Two-Step": "GTL-GH-MTJ",
    "Natural Gas One-Step": "GTL-GH-FT",
    "Byproduct H2 + NG Two-Step": "GTL-BH-MTJ",
    "DAC Two-Step": "DAC-GH-MTJ",
    "DAC One-Step": "DAC-GH-FT",
    "Green H2 Two-Step": "CCU-GH-MTJ",
    "Green H2 One-Step": "CCU-GH-FT",
    "Byproduct H2 Two-Step": "CCU-BH-MTJ",
    "Byproduct H2 One-Step": "CCU-BH-FT",
    "Byproduct H2 + DAC Two-Step": "DAC-BH-MTJ",
    "Byproduct H2 + DAC One-Step": "DAC-BH-FT",
}

# Cluster display names for better readability
CLUSTER_NAMES = {
    0: "Hyper-Centralized",      # 极端集中型
    1: "Dispersed Long-Chain",   # 分散长链型
    2: "Proximal Centralized",   # 近域集中型
    3: "Scale-Expanded",         # 规模扩展型
}

# Radar Chart Axis Labels (Short version for display)
RADAR_LABELS_SHORT = [
    "Nodes",
    "Node\nConcentration",
    "Route\nConcentration",
    "Transport\nDistance",
    "Cross-Region\nRatio",
    "Failure\nImpact",
]

# Co-location Classification Categories (Simplified)
COLOCATION_CATEGORIES = [
    "Raw Material Only",
    "Raw Material + SAF",
    "SAF Only",
    "Consumption Only",
    "SAF + Consumption",
]

# Professional color palette for co-location (Tableau-inspired)
COLOCATION_COLORS = {
    "Raw Material Only": "#4C78A8",      # Steel Blue
    "Raw Material + SAF": "#F58518",     # Orange
    "SAF Only": "#E45756",               # Coral Red
    "Consumption Only": "#72B7B2",       # Teal
    "SAF + Consumption": "#54A24B",      # Green
}

# Professional color palette for radar charts (distinct, colorblind-friendly)
RADAR_COLORS = [
    "#1B9E77",  # Teal
    "#D95F02",  # Orange
    "#7570B3",  # Purple
    "#E7298A",  # Pink
    "#66A61E",  # Green
    "#E6AB02",  # Gold
    "#A6761D",  # Brown
    "#666666",  # Gray
]

# Line colors for facility counts
LINE_COLORS = {
    "electrolyzer": "#2166AC",  # Dark Blue
    "saf_plant": "#B2182B",     # Dark Red
}

# -----------------------------------------------------------------------------
# APPLIED ENERGY STYLE SETTINGS
# -----------------------------------------------------------------------------

def setup_plot_style():
    """Configure matplotlib for Applied Energy journal standards."""
    plt.rcParams.update({
        # Font settings - Times New Roman for English
        'font.family': 'serif',
        'font.serif': ['Times New Roman', 'DejaVu Serif'],
        'font.size': 10,

        # Axes settings
        'axes.linewidth': 0.8,
        'axes.titlesize': 11,
        'axes.titleweight': 'bold',
        'axes.labelsize': 10,
        'axes.labelweight': 'normal',
        'axes.spines.top': False,
        'axes.spines.right': False,

        # Tick settings
        'xtick.labelsize': 9,
        'ytick.labelsize': 9,
        'xtick.major.width': 0.8,
        'ytick.major.width': 0.8,
        'xtick.major.size': 4,
        'ytick.major.size': 4,
        'xtick.direction': 'out',
        'ytick.direction': 'out',

        # Legend settings
        'legend.fontsize': 8,
        'legend.frameon': False,
        'legend.borderpad': 0.4,
        'legend.labelspacing': 0.3,

        # Figure settings
        'figure.dpi': 150,
        'savefig.dpi': 300,
        'savefig.bbox': 'tight',
        'savefig.pad_inches': 0.1,

        # Grid settings
        'grid.linewidth': 0.5,
        'grid.alpha': 0.4,

        # Math text
        'mathtext.fontset': 'stix',
    })


# -----------------------------------------------------------------------------
# HELPER FUNCTIONS - DATA LOADING & PROCESSING
# -----------------------------------------------------------------------------

def _load_metrics(csv_path: Path) -> List[dict]:
    rows = []
    if not csv_path.exists():
        raise FileNotFoundError(f"Metrics file not found: {csv_path}")
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows

def _normalize_metrics(metrics: np.ndarray) -> np.ndarray:
    mins = metrics.min(axis=0)
    maxs = metrics.max(axis=0)
    span = np.where((maxs - mins) == 0, 1.0, (maxs - mins))
    return (metrics - mins) / span

def _iter_facility_entries(container) -> Iterable[dict]:
    if isinstance(container, dict):
        return [v for v in container.values() if isinstance(v, dict)]
    if isinstance(container, list):
        return [v for v in container if isinstance(v, dict)]
    return []

def _load_complete_solution(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def _get_facility_counts(official_name: str, solutions_dir: Path) -> Tuple[int, int]:
    """Returns (electrolyzer_count, saf_plant_count) for a given scenario."""
    solution_path = solutions_dir / f"{official_name}_complete_solution.json"
    if not solution_path.exists():
        # Fallback if specific file is missing, return 0,0 or try logging
        print(f"Warning: Solution file missing for {official_name}")
        return 0, 0

    data = _load_complete_solution(solution_path)
    
    saf_count = 0
    saf_seen = set()
    electrolyzer_locations = set()

    SAF_TECH = {
        "ft_direct_conversion",
        "green_h2_co2_to_saf",
        "airport_integrated_conversion",
        "pipeline_direct_conversion",
    }

    # Iterate facilities
    for info in _iter_facility_entries(data.get("facilities", {})):
        tech = info.get("technology")
        location = info.get("location") or info.get("name") or info.get("source_id")
        
        if tech == "electrolyzer" and location:
            electrolyzer_locations.add(str(location))
        
        if tech in SAF_TECH:
            # Unique key for SAF plant to avoid double counting if multiple units at same loc
            key = (str(location), tech, str(info.get("location_type")))
            if key not in saf_seen:
                saf_seen.add(key)
                saf_count += 1

    # Iterate separate hydrogen facilities list if present
    for info in _iter_facility_entries(data.get("hydrogen_facilities", {})):
        if info.get("technology") == "electrolyzer":
            location = info.get("location") or info.get("name") or info.get("source_id")
            if location:
                electrolyzer_locations.add(str(location))

    return len(electrolyzer_locations), saf_count


def _load_classification_data(csv_path: Path) -> pd.DataFrame:
    """Load co-location classification data from CSV."""
    if not csv_path.exists():
        raise FileNotFoundError(f"Classification file not found: {csv_path}")
    return pd.read_csv(csv_path, encoding="utf-8-sig")


def _aggregate_colocation_counts(df: pd.DataFrame, official_name: str) -> Dict[str, int]:
    """
    Aggregate detailed classification into simplified 5 categories for a scenario.

    Categories:
    - Raw Material Only: 有原材料生产，无SAF，无消费
    - Raw Material + SAF: 有原材料生产，有SAF生产
    - SAF Only: 无原材料生产，有SAF生产，无消费
    - Consumption Only: 无原材料/SAF生产，仅消费
    - SAF + Consumption: 有SAF生产，有消费
    """
    scenario_df = df[df["OfficialName"] == official_name]

    counts = {cat: 0 for cat in COLOCATION_CATEGORIES}

    for _, row in scenario_df.iterrows():
        material_label = row["MaterialLabel"]
        saf_prod = row["SAF_Production"]
        consumption = row["Consumption"]
        count = int(row["Count"])

        has_raw_material = (material_label != "No raw material production")
        has_saf = (saf_prod == "yes")
        has_consumption = (consumption == "yes")

        if has_saf and has_consumption:
            counts["SAF + Consumption"] += count
        elif has_raw_material and has_saf:
            counts["Raw Material + SAF"] += count
        elif has_raw_material and not has_saf and not has_consumption:
            counts["Raw Material Only"] += count
        elif not has_raw_material and has_saf and not has_consumption:
            counts["SAF Only"] += count
        elif not has_raw_material and not has_saf and has_consumption:
            counts["Consumption Only"] += count
        else:
            # 其他情况归入原材料类别（如有原材料但无SAF无消费）
            if has_raw_material:
                counts["Raw Material Only"] += count

    return counts

# -----------------------------------------------------------------------------
# PLOTTING FUNCTIONS
# -----------------------------------------------------------------------------

def plot_radar_subplot(ax, metrics_norm, scenario_indices, scenario_names, colors):
    """
    Plots a single radar chart on the given polar axes.
    Applied Energy style: clean, professional, readable.
    """
    n_vars = len(RADAR_LABELS_SHORT)
    angles = np.linspace(0, 2 * np.pi, n_vars, endpoint=False).tolist()
    angles += angles[:1]  # Close the loop

    # Draw circular grid lines manually for better control
    for r in [0.25, 0.5, 0.75, 1.0]:
        circle_angles = np.linspace(0, 2 * np.pi, 100)
        ax.plot(circle_angles, [r] * 100, color='#CCCCCC', linewidth=0.5, linestyle='-', zorder=1)

    # Draw radial lines
    for angle in angles[:-1]:
        ax.plot([angle, angle], [0, 1], color='#CCCCCC', linewidth=0.5, linestyle='-', zorder=1)

    # Plot each scenario in the cluster
    for j, idx in enumerate(scenario_indices):
        vals = metrics_norm[idx].tolist()
        vals += vals[:1]
        color = colors[j % len(colors)]

        # Plot line with markers
        ax.plot(angles, vals, linewidth=1.8, label=scenario_names[idx],
                color=color, marker='o', markersize=4, markerfacecolor=color,
                markeredgecolor='white', markeredgewidth=0.5, zorder=3)

        # Subtle fill
        ax.fill(angles, vals, color=color, alpha=0.08, zorder=2)

    # Configure axes
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_rlabel_position(30)

    # Set axis labels
    ax.set_thetagrids(np.degrees(angles[:-1]), RADAR_LABELS_SHORT, fontsize=8)

    # Set radial limits and hide default grid
    ax.set_ylim(0, 1.05)
    ax.set_yticks([0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels(['0.25', '0.50', '0.75', '1.00'], fontsize=7, color='#666666')
    ax.grid(False)

    # Clean polar spine
    ax.spines['polar'].set_visible(False)


def plot_colocation_bar_subplot(ax, scenario_names_cluster, colocation_data: List[Dict[str, int]],
                                el_counts: List[int], saf_counts: List[int]):
    """
    Plots a combined visualization with Applied Energy styling:
    - Stacked bar chart for co-location classification counts (left Y-axis)
    - Line plots for Electrolyzer and SAF plant counts (right Y-axis)
    """
    x = np.arange(len(scenario_names_cluster))
    width = 0.65

    # Prepare data for stacking
    bottom = np.zeros(len(scenario_names_cluster))

    # Draw stacked bars with refined styling
    for cat in COLOCATION_CATEGORIES:
        values = [data.get(cat, 0) for data in colocation_data]
        color = COLOCATION_COLORS[cat]
        ax.bar(x, values, width, label=cat, bottom=bottom, color=color,
               alpha=0.9, edgecolor='white', linewidth=0.8, zorder=2)
        bottom += np.array(values)

    # Style left Y-axis
    ax.set_ylabel('Decision Points', fontsize=10, fontweight='normal', color='#333333')
    ax.set_xticks(x)
    ax.set_xticklabels(scenario_names_cluster, rotation=30, ha='right', fontsize=9)

    # Clean spines
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_linewidth(0.8)
    ax.spines['bottom'].set_linewidth(0.8)

    # Subtle grid
    ax.yaxis.grid(True, linestyle='--', alpha=0.4, color='#CCCCCC', zorder=1)
    ax.set_axisbelow(True)

    # Create secondary Y-axis for facility counts
    ax2 = ax.twinx()

    # Plot lines with distinct markers
    ax2.plot(x, el_counts, 'o-', color=LINE_COLORS['electrolyzer'],
             linewidth=2.0, markersize=7, markerfacecolor=LINE_COLORS['electrolyzer'],
             markeredgecolor='white', markeredgewidth=1.2, label='Electrolyzers', zorder=4)
    ax2.plot(x, saf_counts, 's-', color=LINE_COLORS['saf_plant'],
             linewidth=2.0, markersize=7, markerfacecolor=LINE_COLORS['saf_plant'],
             markeredgecolor='white', markeredgewidth=1.2, label='SAF Plants', zorder=4)

    # Style right Y-axis
    ax2.set_ylabel('Facility Count', fontsize=10, fontweight='normal', color='#333333')
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_linewidth(0.8)

    # Set y-axis limits with padding
    max_decision = max(bottom) if len(bottom) > 0 else 1
    ax.set_ylim(0, max_decision * 1.15)

    max_facility = max(max(el_counts) if el_counts else 0, max(saf_counts) if saf_counts else 0)
    if max_facility > 0:
        ax2.set_ylim(0, max_facility * 1.35)
    else:
        ax2.set_ylim(0, 10)

    return ax2


# -----------------------------------------------------------------------------
# MAIN EXECUTION
# -----------------------------------------------------------------------------

def create_combined_legend(fig, bar_axes, secondary_axes):
    """Create a unified legend at the bottom of the figure."""
    # Co-location category legend items
    colocation_handles = [
        mpatches.Patch(facecolor=COLOCATION_COLORS[cat], edgecolor='white',
                       linewidth=0.8, label=cat)
        for cat in COLOCATION_CATEGORIES
    ]

    # Facility count line legend items
    line_handles = [
        Line2D([0], [0], color=LINE_COLORS['electrolyzer'], marker='o',
               markersize=7, markerfacecolor=LINE_COLORS['electrolyzer'],
               markeredgecolor='white', markeredgewidth=1.2, linewidth=2,
               label='Electrolyzers'),
        Line2D([0], [0], color=LINE_COLORS['saf_plant'], marker='s',
               markersize=7, markerfacecolor=LINE_COLORS['saf_plant'],
               markeredgecolor='white', markeredgewidth=1.2, linewidth=2,
               label='SAF Plants'),
    ]

    # Combine all handles
    all_handles = colocation_handles + line_handles

    # Create legend at the bottom
    fig.legend(handles=all_handles, loc='lower center', ncol=7,
               fontsize=9, frameon=False, bbox_to_anchor=(0.5, -0.05),
               columnspacing=1.5, handletextpad=0.5)


def main():
    # Setup plot style
    setup_plot_style()

    print("Loading data...")
    rows = _load_metrics(DEFAULT_METRICS_CSV)

    # Load co-location classification data
    print("Loading co-location classification data...")
    classification_df = _load_classification_data(DEFAULT_CLASSIFICATION_CSV)

    # Extract basic info
    scenarios = [r["Scenario"] for r in rows]
    official_names = [SCENARIO_NAME_MAP.get(s, s) for s in scenarios]
    clusters = [int(r["Cluster"]) for r in rows]

    # 1. Prepare Radar Data
    metrics_raw = np.array([
        [
            float(r["节点数量"]),
            float(r["关键节点集中度"]),
            float(r["关键通道集中度"]),
            float(r["平均运输距离"]),
            float(r["跨区域物流比例"]),
            float(r["单点失效影响"]),
        ]
        for r in rows
    ], dtype=float)
    metrics_norm = _normalize_metrics(metrics_raw)

    # 2. Prepare Siting Data
    siting_counts = []
    for name in official_names:
        el, saf = _get_facility_counts(name, DEFAULT_SOLUTIONS_DIR)
        siting_counts.append((el, saf))

    # 3. Prepare Co-location Data
    colocation_counts = []
    for name in official_names:
        counts = _aggregate_colocation_counts(classification_df, name)
        colocation_counts.append(counts)

    # Group by Cluster
    cluster_map: Dict[int, List[int]] = {}
    for idx, c in enumerate(clusters):
        cluster_map.setdefault(c, []).append(idx)

    # Sort clusters to ensure order 0, 1, 2, 3
    sorted_cluster_ids = sorted(cluster_map.keys())
    target_clusters = sorted_cluster_ids[:4]

    if len(target_clusters) < 4:
        print(f"Warning: Only found {len(target_clusters)} clusters. Grid will have empty columns.")

    # -------------------------------------------------------------------------
    # Visualisation Construction
    # -------------------------------------------------------------------------

    # Create figure with refined dimensions
    fig = plt.figure(figsize=(18, 10))

    # Use GridSpec for better control over spacing
    from matplotlib.gridspec import GridSpec
    gs = GridSpec(2, 4, figure=fig, height_ratios=[1, 0.9],
                  hspace=0.35, wspace=0.38,
                  left=0.05, right=0.95, top=0.92, bottom=0.08)

    # --- ROW 1: RADAR CHARTS ---
    radar_axes = []
    for i, cid in enumerate(target_clusters):
        if i >= 4:
            break

        ax = fig.add_subplot(gs[0, i], polar=True)
        radar_axes.append(ax)

        idxs = cluster_map[cid]
        idxs.sort(key=lambda x: official_names[x])

        plot_radar_subplot(ax, metrics_norm, idxs, official_names, RADAR_COLORS)

        # Individual legend for each radar (positioned below the chart)
        legend = ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.1),
                          fontsize=7, frameon=False, handlelength=1.5,
                          labelspacing=0.3, ncol=2)
        for text in legend.get_texts():
            text.set_fontsize(7)

    # --- ROW 2: COMBINED SITING & CO-LOCATION ---
    bar_axes = []
    secondary_axes = []
    for i, cid in enumerate(target_clusters):
        if i >= 4:
            break

        ax = fig.add_subplot(gs[1, i])
        bar_axes.append(ax)

        idxs = cluster_map[cid]
        idxs.sort(key=lambda x: official_names[x])

        names_cluster = [official_names[ix] for ix in idxs]
        el_counts_cluster = [siting_counts[ix][0] for ix in idxs]
        saf_counts_cluster = [siting_counts[ix][1] for ix in idxs]
        colocation_cluster = [colocation_counts[ix] for ix in idxs]

        ax2 = plot_colocation_bar_subplot(ax, names_cluster, colocation_cluster,
                                          el_counts_cluster, saf_counts_cluster)
        secondary_axes.append(ax2)

    # Create unified legend at bottom
    create_combined_legend(fig, bar_axes, secondary_axes)

    # Add subplot labels (e)-(l) for each subplot
    # Row 1: radar charts (e), (f), (g), (h)
    row1_labels = ['(e)', '(f)', '(g)', '(h)']
    for i, ax in enumerate(radar_axes):
        if i < len(row1_labels):
            # Get the position of the axes in figure coordinates
            pos = ax.get_position()
            fig.text(pos.x0 - 0.02, pos.y1 + 0.02, row1_labels[i],
                    fontsize=12, fontweight='bold', va='bottom')

    # Row 2: bar charts (i), (j), (k), (l)
    row2_labels = ['(i)', '(j)', '(k)', '(l)']
    for i, ax in enumerate(bar_axes):
        if i < len(row2_labels):
            pos = ax.get_position()
            fig.text(pos.x0 - 0.02, pos.y1 + 0.02, row2_labels[i],
                    fontsize=12, fontweight='bold', va='bottom')

    # Save
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = VIS_ROOT / f"results/combined_cluster_vis_{timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "combined_cluster_visualization.png"

    fig.savefig(out_path, dpi=300, bbox_inches='tight', facecolor='white', edgecolor='none')
    print(f"Visualization saved to: {out_path}")
    plt.close(fig)


if __name__ == "__main__":
    main()
