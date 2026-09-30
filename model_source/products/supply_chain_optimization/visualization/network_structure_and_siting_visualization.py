# -*- coding: utf-8 -*-
"""
Combined visualization of Network Structure Radar Charts and Facility Siting Counts.
Generates a 2-row x 4-column figure:
- Top Row: Radar charts for Clusters 0-3 (Network Metrics).
- Bottom Row: Combined bar charts for Clusters 0-3 (Co-location & Facility Counts).
Style: Matches user reference (Colored Headers per Cluster).
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
import matplotlib.gridspec as gridspec
import matplotlib.colors as mcolors
from matplotlib.path import Path as MplPath
import numpy as np
import pandas as pd
try:
    from svgpath2mpl import parse_path as svg_parse_path
    SVG_PARSER_AVAILABLE = True
except ImportError:
    SVG_PARSER_AVAILABLE = False

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

CLASSIFICATION_RESULTS_PATTERN = "network_siting_clusters_*/scenario_decision_point_classification_counts.csv"

CLASSIFICATION_NAME_ALIASES = {
    "GTL-GH": ["GTL-GH-MTJ"],
    "GTL": ["GTL-GH-FT"],
    "GTL-BH": ["GTL-BH-MTJ"],
}

SAF_TECH = {
    "ft_direct_conversion",
    "green_h2_co2_to_saf",
    "airport_integrated_conversion",
    "pipeline_direct_conversion",
    "lng_terminal_conversion",
    "lng_to_hplant_conversion",
    "integrated_supply_conversion",
}

# Scenario Name Mapping
SCENARIO_NAME_MAP: Dict[str, str] = {
    "Coal Hydrogen": "CTL",
    "Byproduct H2 + Coal": "CTL-BH",
    "Natural Gas Two-Step": "GTL-GH",
    "Natural Gas One-Step": "GTL",
    "Byproduct H2 + NG Two-Step": "GTL-BH",
    "DAC Two-Step": "DAC-GH-MTJ",
    "DAC One-Step": "DAC-GH-FT",
    "Green H2 Two-Step": "CCU-GH-MTJ",
    "Green H2 One-Step": "CCU-GH-FT",
    "Byproduct H2 Two-Step": "CCU-BH-MTJ",
    "Byproduct H2 One-Step": "CCU-BH-FT",
    "Byproduct H2 + DAC Two-Step": "DAC-BH-MTJ",
    "Byproduct H2 + DAC One-Step": "DAC-BH-FT",
}

# Cluster names
CLUSTER_NAMES = {
    0: "Hyper-Centralized",
    1: "Dispersed Long-Chain",
    2: "Proximal Centralized",
    3: "Scale-Expanded",
}

# Radar Chart Axis Labels (full text)
RADAR_LABELS_SHORT = [
    "Number of\nNodes",
    "Critical Node\nConcentration",
    "Critical Route\nConcentration",
    "Average Transport\nDistance",
    "Cross-Regional\nLogistics Ratio",
    "Single-Point\nFailure Impact",
]

# Co-location Classification Categories (Simplified)
COLOCATION_CATEGORIES = [
    "Raw Material Only",
    "Raw Material + SAF",
    "SAF Only",
    "Consumption Only",
    "SAF + Consumption",
]

# Display names aligned with thirteen_scenarios_clustered_map_visualization naming scheme
COLOCATION_DISPLAY_LABELS = {
    "Raw Material Only": "Raw Material Production Only",
    "Raw Material + SAF": "Raw Material Production + SAF Production",
    "SAF Only": "SAF Production Facility Only",
    "Consumption Only": "Consumption Site Only",
    "SAF + Consumption": "SAF Production Facility + Consumption Site",
}

# -----------------------------------------------------------------------------
# COLORS & THEMES
# -----------------------------------------------------------------------------

# Cluster Themes: (Header Background, Data Color / Border Info)
# Matching reference: Green, Blue, Orange, Red (Purple if 5th)
CLUSTER_THEMES = {
    0: {"header": "#C5E0B4", "stroke": "#548235"},  # Green
    1: {"header": "#BDD7EE", "stroke": "#2F5597"},  # Blue
    2: {"header": "#F8CBAD", "stroke": "#C65911"},  # Orange
    3: {"header": "#F4B183", "stroke": "#C00000"},  # Red (using a lighter red/peach for header) - adj to match ref red
}
# Adjust Theme 3 (Red) to better match reference "MC4" (Pinkish Red Header, Red Line)
CLUSTER_THEMES[3] = {"header": "#E69696", "stroke": "#C00000"} 


# Stacked Bar Colors (NPG / Professional)
COLOCATION_COLORS = {
    "Raw Material Only": "#4DBBD5",      # Blue
    "Raw Material + SAF": "#F39B7F",     # Orange
    "SAF Only": "#E64B35",               # Red
    "Consumption Only": "#8491B4",       # Purple
    "SAF + Consumption": "#00A087",      # Green
}

# Line colors for facility counts
LINE_COLORS = {
    "electrolyzer": "#2C3E50",  # Dark Slate (Neutral) to conflict less with themes
    "saf_plant": "#E74C3C",     # Bright Red
}

FACILITY_DISPLAY_LABELS = {
    "electrolyzer": "Electrolyzer Facilities",
    "saf_plant": "SAF Production Facilities",
}

# Row indicators for the absolute-value stacked bars in the second row.
ABS_STACK_INDICATORS = [
    ("Raw Material Only", "Feedstock-Providing Only Decision Points"),
    ("Raw Material + SAF", "Feedstock-Providing and SAF-Producing Decision Points"),
    ("SAF Only", "SAF-Producing Only Decision Points"),
    ("Consumption Only", "Demand-Only Decision Points"),
    ("SAF + Consumption", "Joint SAF-Producing and Demand Decision Points"),
    ("electrolyzer", "Built Electrolyzer Sites (Solution-Derived)"),
    ("saf_plant", "Built SAF Conversion Sites (Solution-Derived)"),
]

# Classification icons reused from thirteen_scenarios_clustered_map_visualization.py
SVG_ICON_PATHS = {
    "airplane": "M21 16v-2l-8-5V3.5c0-.83-.67-1.5-1.5-1.5S10 2.67 10 3.5V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5l8 2.5z",
    "factory": "M18.5 12.5V6H17v6.5l-5 2.5V9h-1.5v6l-5-2.5V6H4v6.5L2 14v8h20v-8l-3.5-1.5z",
    "flame": "M13.5.67s.74 2.65.74 4.8c0 2.06-1.35 3.73-3.41 3.73-2.07 0-3.63-1.67-3.63-3.73l.03-.36C5.21 7.51 4 10.62 4 14c0 4.42 3.58 8 8 8s8-3.58 8-8C20 8.61 17.41 3.8 13.5.67zM11.71 19c-1.78 0-3.22-1.4-3.22-3.14 0-1.62 1.05-2.76 2.81-3.12 1.77-.36 3.6-1.21 4.62-2.58.39 1.29.59 2.65.59 4.04 0 2.65-2.15 4.8-4.8 4.8z",
    "h2": "M12 2c-5.33 4.55-8 8.48-8 11.8 0 4.98 3.8 8.2 8 8.2s8-3.22 8-8.2c0-3.32-2.67-7.25-8-11.8z",
    "co2": "M19.35 10.04C18.67 6.59 15.64 4 12 4 9.11 4 6.6 5.64 5.35 8.04 2.34 8.36 0 10.91 0 14c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5 0-2.64-2.05-4.78-4.65-4.96z",
    "star": "M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z",
}

# Icon combinations aligned with ABS_STACK_INDICATORS order.
ABS_STACK_ICON_ROWS = [
    ["co2", "h2", "plus", "times"],
    ["factory_co2_saf", "factory_h2_saf"],
    ["factory_saf"],
    ["airplane_no_saf"],
    ["airplane_saf"],
    ["h2"],
    ["factory_saf"],
]

# Unified text style for the whole figure
UNIFORM_TEXT_SIZE = 26
UNIFORM_TEXT_COLOR = "#222222"
PANEL_LABEL_SIZE = 30
PANEL_LABEL_Y = 1.03
RADIAL_RING_LEVELS = [0.25, 0.50, 0.75, 1.00]
RADIAL_LABEL_LEVELS = [0.25, 0.50, 0.75, 1.00]
RADAR_RING_COLORS = [
    "#B7DEE8",  # Number of Nodes
    "#C5D9F1",  # Critical Node Concentration
    "#F4CCCC",  # Critical Route Concentration
    "#F9CB9C",  # Average Transport Distance
    "#FFE599",  # Cross-Regional Logistics Ratio
    "#D9EAD3",  # Single-Point Failure Impact
]
RADAR_RING_WIDTH = 0.55
# Distinct process colors for second-row stacked bars (legend shown outside).
PROCESS_COLOR_PALETTE = [
    "#1F77B4", "#FF7F0E", "#2CA02C", "#D62728", "#9467BD", "#8C564B", "#E377C2",
    "#7F7F7F", "#BCBD22", "#17BECF", "#393B79", "#637939", "#8C6D31",
]
# For crowded rows in specific second-row subplots:
# key = subplot index in second row (0-based: i,j,k,l -> 0,1,2,3)
# value = 1-based row numbers that should show only one average label.
MEAN_ONLY_ROWS_BY_SUBPLOT = {
    1: {3, 4, 5},          # second subplot
    2: {2, 3, 4, 5, 7},    # third subplot
    3: {2, 3, 4, 5, 7},    # fourth subplot
}
BOTTOM_LEGEND_SIZE = 24
# Physical width ratio for second-row subplots (shortens visible x-axis length without changing xlim).
ROW2_AXIS_WIDTH_RATIO = 0.82
# Font scaling for second-row stacked bars.
ROW2_BAR_VALUE_FONT_SCALE = 2.0
ROW2_X_AXIS_FONT_SCALE = 2.0
ROW2_LEGEND_FONT_SCALE = 2.0

# -----------------------------------------------------------------------------
# PLOTTING HELPERS
# -----------------------------------------------------------------------------

def setup_plot_style():
    """Configure matplotlib for Nature journal standards."""
    plt.rcParams.update({
        'font.family': 'serif',
        'font.serif': ['Times New Roman', 'Times', 'DejaVu Serif'],
        'font.size': UNIFORM_TEXT_SIZE,
        'axes.linewidth': 0.8,
        'axes.titlesize': UNIFORM_TEXT_SIZE,
        'axes.titleweight': 'bold',
        'axes.labelsize': UNIFORM_TEXT_SIZE,
        'xtick.labelsize': UNIFORM_TEXT_SIZE,
        'ytick.labelsize': UNIFORM_TEXT_SIZE,
        'legend.fontsize': UNIFORM_TEXT_SIZE,
        'text.color': UNIFORM_TEXT_COLOR,
        'axes.labelcolor': UNIFORM_TEXT_COLOR,
        'axes.titlecolor': UNIFORM_TEXT_COLOR,
        'xtick.color': UNIFORM_TEXT_COLOR,
        'ytick.color': UNIFORM_TEXT_COLOR,
        'figure.dpi': 300,
    })

def add_colored_title(ax, text, bg_color, text_color="black", pad=5, y_offset=1.25):
    """Adds a rectangular colored title box to the axes."""
    # For polar plots, coordinate systems are tricky. We use figure coords or relative axes coords.
    # relative 0-1 is easiest.
    # y_offset needs to be high enough to clear polar labels.
    
    rect_props = dict(boxstyle='square,pad=0.4', facecolor=bg_color, edgecolor='black', linewidth=1.0)
    
    ax.set_title(text, position=(0.5, y_offset), bbox=rect_props, 
                 fontsize=UNIFORM_TEXT_SIZE, fontweight='bold', color=text_color)


def _adjust_color(color, amount):
    """Lighten or darken a color by amount in [-0.5, 0.5]."""
    rgb = np.array(mcolors.to_rgb(color))
    if amount >= 0:
        rgb = rgb + (1.0 - rgb) * amount
    else:
        rgb = rgb * (1.0 + amount)
    return tuple(np.clip(rgb, 0.0, 1.0))


def _scenario_color_variants(base_color, count):
    if count <= 1:
        return [base_color]
    palette = plt.cm.tab10.colors if count <= 10 else plt.cm.tab20.colors
    mix = 0.7
    base = np.array(mcolors.to_rgb(base_color))
    colors = []
    for i in range(count):
        p = np.array(palette[i % len(palette)])
        colors.append(tuple((1.0 - mix) * base + mix * p))
    return colors


def _round_half_up(x: float, ndigits: int = 2) -> float:
    from decimal import Decimal, ROUND_HALF_UP

    if ndigits <= 0:
        q = Decimal("1")
    else:
        q = Decimal("0." + "0" * (ndigits - 1) + "1")
    return float(Decimal(str(x)).quantize(q, rounding=ROUND_HALF_UP))


def _format_count_label(v: float) -> str:
    return f"{int(_round_half_up(v, 0))}"


def _build_process_color_map(process_names: List[str]) -> Dict[str, tuple]:
    cmap = {}
    for i, name in enumerate(process_names):
        cmap[name] = mcolors.to_rgb(PROCESS_COLOR_PALETTE[i % len(PROCESS_COLOR_PALETTE)])
    return cmap


class CustomMarkers:
    """Reuse same icon construction logic as thirteen_scenarios_clustered_map_visualization.py."""

    @staticmethod
    def _svg_to_marker(svg_path_str, flip_y=True):
        if not SVG_PARSER_AVAILABLE:
            return None
        try:
            marker = svg_parse_path(svg_path_str)
            marker.vertices -= marker.vertices.mean(axis=0)
            max_val = np.abs(marker.vertices).max()
            if max_val > 0:
                marker.vertices /= max_val
            if flip_y:
                marker.vertices[:, 1] *= -1
            return marker
        except Exception:
            return None

    @staticmethod
    def _fallback_airplane():
        verts = [
            (0.0, 1.0), (0.15, 0.5), (1.0, 0.1), (0.15, -0.1),
            (0.15, -0.5), (0.5, -0.9), (0.1, -0.6), (0.0, -1.0),
            (-0.1, -0.6), (-0.5, -0.9), (-0.15, -0.5), (-0.15, -0.1),
            (-1.0, 0.1), (-0.15, 0.5), (0.0, 1.0)
        ]
        codes = [MplPath.MOVETO] + [MplPath.LINETO] * 13 + [MplPath.CLOSEPOLY]
        return MplPath(verts, codes)

    @staticmethod
    def _fallback_factory():
        verts = [
            (-0.9, -0.9), (0.9, -0.9), (0.9, -0.3), (0.5, -0.3), (0.5, 0.5),
            (0.1, -0.3), (0.1, 0.7), (-0.3, -0.3), (-0.3, 0.3), (-0.7, -0.3),
            (-0.9, -0.3), (-0.9, -0.9)
        ]
        codes = [MplPath.MOVETO] + [MplPath.LINETO] * 10 + [MplPath.CLOSEPOLY]
        return MplPath(verts, codes)

    @staticmethod
    def _fallback_simple():
        return MplPath.unit_circle()

    @staticmethod
    def _fallback_h2():
        # Triangle for H2 production in no-svg environment.
        return MplPath.unit_regular_polygon(3)

    @staticmethod
    def _fallback_co2():
        # Square for CO2 capture in no-svg environment.
        return MplPath.unit_regular_polygon(4)

    @staticmethod
    def _fallback_flame():
        # Diamond for natural gas/flame in no-svg environment.
        return 'D'

    @staticmethod
    def airplane():
        marker = CustomMarkers._svg_to_marker(SVG_ICON_PATHS["airplane"])
        return marker if marker is not None else CustomMarkers._fallback_airplane()

    @staticmethod
    def factory():
        marker = CustomMarkers._svg_to_marker(SVG_ICON_PATHS["factory"])
        return marker if marker is not None else CustomMarkers._fallback_factory()

    @staticmethod
    def flame():
        marker = CustomMarkers._svg_to_marker(SVG_ICON_PATHS["flame"])
        return marker if marker is not None else CustomMarkers._fallback_flame()

    @staticmethod
    def h2_icon():
        marker = CustomMarkers._svg_to_marker(SVG_ICON_PATHS["h2"])
        return marker if marker is not None else CustomMarkers._fallback_h2()

    @staticmethod
    def co2_cloud():
        marker = CustomMarkers._svg_to_marker(SVG_ICON_PATHS["co2"])
        return marker if marker is not None else CustomMarkers._fallback_co2()


def _build_abs_stack_icon_markers() -> Dict[str, object]:
    return {
        "airplane": CustomMarkers.airplane(),
        "factory": CustomMarkers.factory(),
        "flame": CustomMarkers.flame(),
        "h2": CustomMarkers.h2_icon(),
        "co2": CustomMarkers.co2_cloud(),
        "plus": "P",
        "times": "X",
    }


ABS_STACK_ICON_MARKERS = _build_abs_stack_icon_markers()


def _draw_abs_stack_icons(ax, y_values: np.ndarray, size_scale: float = 1.0):
    """Draw icon-only y-axis labels for publication-ready styling."""
    transform = ax.get_yaxis_transform()  # x in axes coords, y in data coords
    # Keep icon labels fully outside the y-axis (x=0) to avoid entering bars.
    icon_right_edge = -0.03
    x_step = 0.042
    for i, y_val in enumerate(y_values):
        icon_keys = ABS_STACK_ICON_ROWS[i] if i < len(ABS_STACK_ICON_ROWS) else ["o"]
        # Right-align icon groups so the rightmost marker never crosses into plot area.
        start_x = icon_right_edge - x_step * (len(icon_keys) - 1)
        for j, icon_key in enumerate(icon_keys):
            base_icon_key = icon_key
            if icon_key.startswith("factory_"):
                base_icon_key = "factory"
            elif icon_key.startswith("airplane_"):
                base_icon_key = "airplane"

            marker = ABS_STACK_ICON_MARKERS.get(base_icon_key, "o")
            # Keep visual style close to thirteen_scenarios marker semantics.
            face = "#808080"
            edge = "#2A2A2A"
            size = 108
            linewidth = 1.2
            if icon_key == "h2":
                face = "#0072B2"
                edge = "#0072B2"
                linewidth = 1.2
            elif icon_key == "co2":
                face = "#663300"
                edge = "#663300"
                linewidth = 1.2
            elif icon_key == "flame":
                face = "#009E73"
                edge = "#009E73"
                linewidth = 1.2
            elif icon_key == "airplane":
                face = "#808080"
                edge = "white"
                size = 130
                linewidth = 1.0
            elif icon_key == "airplane_no_saf":
                face = "#808080"
                edge = "white"
                size = 130
                linewidth = 1.0
            elif icon_key == "airplane_saf":
                face = "#D55E00"
                edge = "white"
                size = 130
                linewidth = 1.0
            elif icon_key == "factory":
                face = "#005AB5"
                edge = "#002040"
                size = 122
                linewidth = 1.0
            elif icon_key == "factory_no_saf":
                face = "#E0E0E0"
                edge = "#606060"
                size = 124
                linewidth = 1.0
            elif icon_key == "factory_saf":
                face = "#005AB5"
                edge = "#002040"
                size = 124
                linewidth = 1.0
            elif icon_key == "factory_co2_saf":
                face = "#663300"
                edge = "#663300"
                size = 124
                linewidth = 1.0
            elif icon_key == "factory_h2_saf":
                face = "#005AB5"
                edge = "#002040"
                size = 124
                linewidth = 1.0
            elif icon_key == "plus":
                # Match thirteen screenshot style for combined CO2+H2 classes.
                face = "#663300"
                edge = "#000000"
                size = 120
                linewidth = 1.5
            elif icon_key == "times":
                # Match thirteen screenshot style for combined CO2+H2 classes.
                face = "#663300"
                edge = "#000000"
                size = 120
                linewidth = 1.5
            _s = (size if len(icon_keys) <= 3 else max(92, size - 18)) * size_scale
            ax.scatter(
                [start_x + j * x_step],
                [y_val],
                transform=transform,
                marker=marker,
                s=_s,
                facecolors=face,
                edgecolors=edge,
                linewidths=linewidth,
                zorder=8,
                clip_on=False,
            )


def _draw_ring_label(ax, text, angle_rad, radius, fontsize=22):
    """Draw ring labels along tangent direction in polar axes."""
    display_theta = ax.get_theta_direction() * angle_rad + ax.get_theta_offset()
    angle_deg = (np.degrees(display_theta) + 360) % 360

    rotation = angle_deg - 90
    rotation = (rotation + 180) % 360 - 180
    if rotation < -90 or rotation > 90:
        rotation += 180
        rotation = (rotation + 180) % 360 - 180

    ax.text(
        angle_rad,
        radius,
        text,
        ha="center",
        va="center",
        rotation=rotation,
        rotation_mode="anchor",
        fontsize=fontsize,
        fontweight="semibold",
        color=UNIFORM_TEXT_COLOR,
        zorder=6,
    )


def plot_radar_subplot(ax, metrics_norm, scenario_indices, theme, legend_names, process_color_map):
    """
    Plots a single radar chart with cluster-specific theme.
    All scenarios in this cluster sharing the same color.
    """
    n_vars = len(RADAR_LABELS_SHORT)
    base_angles = np.linspace(0, 2 * np.pi, n_vars, endpoint=False)
    angles_closed = np.concatenate([base_angles, [base_angles[0]]])

    # Axes config first so ring-label rotation uses final polar settings.
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_rlabel_position(14)
    ax.set_xticks(base_angles)
    ax.set_xticklabels([""] * n_vars)
    ax.tick_params(axis="x", pad=8)

    r_grid_max = 1.0
    r_ring_inner = r_grid_max
    r_ring_width = RADAR_RING_WIDTH
    r_outer = r_ring_inner + r_ring_width
    r_ring_mid = r_ring_inner + r_ring_width / 2
    seg_width = 2 * np.pi / n_vars

    # Colored segmented outer ring + text labels on ring.
    for i, (ang, label) in enumerate(zip(base_angles, RADAR_LABELS_SHORT)):
        ring_color = RADAR_RING_COLORS[i % len(RADAR_RING_COLORS)]
        ax.bar(
            ang - seg_width / 2,
            r_ring_width,
            width=seg_width,
            bottom=r_ring_inner,
            align="edge",
            color=ring_color,
            edgecolor="white",
            linewidth=1.2,
            zorder=0,
        )
        # Slightly larger than the original size for readability.
        _draw_ring_label(ax, label, ang, radius=r_ring_mid, fontsize=22)

    # Radial spokes + circular grid (journal style).
    for angle in base_angles:
        ax.plot([angle, angle], [0, r_grid_max], color="#9C9C9C", linewidth=0.7, linestyle="--", alpha=0.6, zorder=1)
    circle_angles = np.linspace(0, 2 * np.pi, 360)
    for r in RADIAL_RING_LEVELS:
        ax.plot(circle_angles, [r] * len(circle_angles), color="#8A8A8A", linewidth=0.8, linestyle="--", alpha=0.65, zorder=1)

    # Plot Data: use the same process color system as second-row bars.
    colors = [
        process_color_map.get(legend_names[idx], mcolors.to_rgb("#4C78A8"))
        for idx in scenario_indices
    ]
    for local_i, idx in enumerate(scenario_indices):
        vals = metrics_norm[idx].tolist()
        vals = [min(1.0, max(0.0, v)) for v in vals]  # keep normalized values stable in [0,1]
        vals += vals[:1]
        color = colors[local_i]
        
        # Plot outline
        ax.plot(
            angles_closed,
            vals,
            linewidth=1.8,
            color=color,
            alpha=0.9,
            zorder=3,
            label=legend_names[idx]
        )
        # Fill
        ax.fill(angles_closed, vals, color=color, alpha=0.08, zorder=2)
        # Markers
        ax.plot(
            angles_closed,
            vals,
            linestyle="None",
            marker="o",
            markersize=3.8,
            markerfacecolor=color,
            markeredgecolor="white",
            markeredgewidth=0.7,
            color=color,
            zorder=4,
        )

    # Radial axis labels
    ax.set_ylim(0, r_outer + 0.02)
    ax.set_yticks(RADIAL_LABEL_LEVELS)
    r_labels = [f"{_round_half_up(v, 2):.2f}" for v in RADIAL_LABEL_LEVELS[:-1]]
    r_labels.append(f"{_round_half_up(RADIAL_LABEL_LEVELS[-1], 2):.2f}")
    ax.set_yticklabels(r_labels, fontsize=UNIFORM_TEXT_SIZE, color=UNIFORM_TEXT_COLOR)
    ax.grid(False)
    ax.spines['polar'].set_visible(True)
    ax.spines['polar'].set_color('#333333')
    ax.spines['polar'].set_linewidth(1.0)

    # Outer boundary line around the segmented ring.
    ax.plot(circle_angles, np.full_like(circle_angles, r_outer), color="#333333", linewidth=1.0, alpha=0.9, zorder=2)

    # Scenario-color legend is removed from middle; unified legend is shown under row 2.


def _build_absolute_indicator_matrix(colocation_data, el_counts, saf_counts):
    """Build indicator x process matrix for absolute stacked-row bars."""
    n_proc = len(colocation_data)
    matrix = np.zeros((len(ABS_STACK_INDICATORS), n_proc), dtype=float)

    for j in range(n_proc):
        for i, (key, _) in enumerate(ABS_STACK_INDICATORS):
            if key in COLOCATION_CATEGORIES:
                matrix[i, j] = float(colocation_data[j].get(key, 0))
            elif key == "electrolyzer":
                matrix[i, j] = float(el_counts[j])
            elif key == "saf_plant":
                matrix[i, j] = float(saf_counts[j])
    return matrix


def plot_absolute_indicator_stack_subplot(
    ax,
    scenario_names_cluster,
    colocation_data,
    el_counts,
    saf_counts,
    process_color_map,
    mean_only_rows=None,
    show_ylabels=False,
):
    """Plot absolute stacked horizontal rows with per-subplot max and blank remainder."""
    matrix = _build_absolute_indicator_matrix(colocation_data, el_counts, saf_counts)
    n_rows, n_proc = matrix.shape
    y = np.arange(n_rows)
    bar_value_fontsize = max(6, UNIFORM_TEXT_SIZE - 1) * ROW2_BAR_VALUE_FONT_SCALE
    x_axis_fontsize = UNIFORM_TEXT_SIZE * ROW2_X_AXIS_FONT_SCALE

    row_totals = np.sum(matrix, axis=1)
    local_max = float(np.max(row_totals)) if np.max(row_totals) > 0 else 1.0
    proc_base_colors = [process_color_map.get(name, (0.55, 0.55, 0.55)) for name in scenario_names_cluster]
    mean_only_rows = set(mean_only_rows or [])

    for i in range(n_rows):
        # Background track to visualize blank remainder up to per-subplot local max.
        ax.barh(
            y[i],
            local_max,
            left=0,
            height=0.78,
            color="#F3F3F3",
            edgecolor="#D8D8D8",
            linewidth=0.6,
            zorder=0,
        )

        row_vals = matrix[i, :]
        row_peak = float(np.max(row_vals)) if np.max(row_vals) > 0 else 1.0
        is_mean_only_row = (i + 1) in mean_only_rows
        left = 0.0
        for j, val in enumerate(row_vals):
            if val <= 0:
                continue
            ratio = val / row_peak
            color = _adjust_color(proc_base_colors[j], 0.35 - 0.55 * ratio)  # larger value -> darker
            ax.barh(
                y[i],
                val,
                left=left,
                height=0.78,
                color=color,
                edgecolor="white",
                linewidth=0.6,
                zorder=2,
            )
            # Always annotate non-zero values unless this row is set to "mean only".
            if val > 0 and not is_mean_only_row:
                mean_rgb = float(np.mean(mcolors.to_rgb(color)))
                txt_color = "white" if mean_rgb < 0.55 else "#1E1E1E"
                x_txt = left + val / 2.0
                ha = "center"
                if val < max(local_max * 0.035, 0.8):
                    x_txt = min(left + val + local_max * 0.008, local_max * 0.995)
                    ha = "left"
                ax.text(
                    x_txt,
                    y[i],
                    _format_count_label(val),
                    ha=ha,
                    va="center",
                    fontsize=bar_value_fontsize,
                    color=txt_color,
                    zorder=3,
                    clip_on=False,
                )
            left += val

        # For crowded rows, show only one average value label.
        if is_mean_only_row:
            nz = row_vals[row_vals > 0]
            avg_val = float(np.mean(nz)) if nz.size > 0 else 0.0
            row_sum = float(np.sum(row_vals))
            if row_sum >= local_max * 0.16:
                x_avg = row_sum / 2.0
                ha_avg = "center"
            else:
                x_avg = min(row_sum + local_max * 0.012, local_max * 0.992)
                ha_avg = "left"
            ax.text(
                x_avg,
                y[i],
                _format_count_label(avg_val),
                ha=ha_avg,
                va="center",
                fontsize=bar_value_fontsize,
                fontweight="bold",
                color="#111111",
                zorder=4,
                clip_on=False,
            )

    ax.set_xlim(0, local_max)
    ax.set_ylim(-0.6, n_rows - 0.4)
    ax.invert_yaxis()

    # Absolute count ticks.
    x_mid = _round_half_up(local_max * 0.5, 0) if local_max >= 10 else _round_half_up(local_max * 0.5, 2)
    x_max = _round_half_up(local_max, 0) if local_max >= 10 else _round_half_up(local_max, 2)
    ax.set_xticks([0, x_mid, x_max])
    ax.set_xticklabels([f"{0:g}", f"{x_mid:g}", f"{x_max:g}"], fontsize=x_axis_fontsize)
    ax.set_xlabel(
        "Counts",
        fontsize=x_axis_fontsize,
        color=UNIFORM_TEXT_COLOR
    )

    if show_ylabels:
        ax.set_yticks(y)
        ax.set_yticklabels([""] * n_rows)
        ax.tick_params(axis="y", length=0)
        _draw_abs_stack_icons(ax, y)
    else:
        ax.set_yticks(y)
        ax.set_yticklabels([""] * n_rows)
        ax.tick_params(axis="y", length=0)

    ax.xaxis.grid(True, linestyle="--", linewidth=0.6, alpha=0.35)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    return list(scenario_names_cluster)


# -----------------------------------------------------------------------------
# ALTERNATIVE ROW-2 VISUALIZATION FUNCTIONS
# -----------------------------------------------------------------------------

def plot_lollipop_subplot(
    ax,
    scenario_names_cluster,
    colocation_data,
    el_counts,
    saf_counts,
    process_color_map,
    show_ylabels=False,
):
    """方案一：棒棒糖图 (Lollipop / Cleveland Dot Plot)。

    每个指标行展示各场景的独立点（圆点+茎），x轴为绝对计数值。
    场景在同一行内垂直展开避免重叠，颜色与 process_color_map 一致。
    """
    matrix = _build_absolute_indicator_matrix(colocation_data, el_counts, saf_counts)
    n_rows, n_proc = matrix.shape
    bar_value_fontsize = max(6, UNIFORM_TEXT_SIZE - 2) * ROW2_BAR_VALUE_FONT_SCALE
    x_axis_fontsize = UNIFORM_TEXT_SIZE * ROW2_X_AXIS_FONT_SCALE

    proc_base_colors = [process_color_map.get(name, (0.55, 0.55, 0.55)) for name in scenario_names_cluster]
    local_max = float(np.max(matrix)) if np.max(matrix) > 0 else 1.0

    # 多个场景在同一行内垂直展开
    spread = 0.32
    if n_proc == 1:
        y_offsets = [0.0]
    else:
        y_offsets = np.linspace(-spread, spread, n_proc).tolist()

    for i in range(n_rows):
        # 浅色底纹带
        ax.axhspan(i - 0.48, i + 0.48, alpha=0.04, color='#888888', zorder=0)
        for j in range(n_proc):
            val = matrix[i, j]
            if val <= 0:
                continue
            y_pos = i + y_offsets[j]
            color = proc_base_colors[j]
            # 茎：从 0 到 val 的水平线
            ax.plot([0, val], [y_pos, y_pos],
                    color=color, linewidth=2.2, alpha=0.72, zorder=2,
                    solid_capstyle='round')
            # 端点圆点
            ax.scatter([val], [y_pos], color=color, s=100, zorder=3,
                       edgecolors='white', linewidths=0.9, alpha=0.96)
            # 数值标注
            x_lbl = val + local_max * 0.025
            ax.text(x_lbl, y_pos, _format_count_label(val),
                    ha='left', va='center',
                    fontsize=bar_value_fontsize * 0.75,
                    color=color, zorder=4, clip_on=False)

    ax.set_xlim(0, local_max * 1.30)
    ax.set_ylim(-0.6, n_rows - 0.4)
    ax.invert_yaxis()

    x_mid = _round_half_up(local_max * 0.5, 0) if local_max >= 10 else _round_half_up(local_max * 0.5, 2)
    x_max_tick = _round_half_up(local_max, 0) if local_max >= 10 else _round_half_up(local_max, 2)
    ax.set_xticks([0, x_mid, x_max_tick])
    ax.set_xticklabels([f"{0:g}", f"{x_mid:g}", f"{x_max_tick:g}"], fontsize=x_axis_fontsize)
    ax.set_xlabel("Counts", fontsize=x_axis_fontsize, color=UNIFORM_TEXT_COLOR)

    y_ticks = np.arange(n_rows)
    ax.set_yticks(y_ticks)
    ax.set_yticklabels([""] * n_rows)
    ax.tick_params(axis="y", length=0)
    if show_ylabels:
        _draw_abs_stack_icons(ax, y_ticks)

    ax.xaxis.grid(True, linestyle="--", linewidth=0.6, alpha=0.30)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    return list(scenario_names_cluster)


def plot_dot_matrix_subplot(
    ax,
    scenario_names_cluster,
    colocation_data,
    el_counts,
    saf_counts,
    process_color_map,
    show_ylabels=False,
):
    """方案二：气泡矩阵 (Bubble / Dot Matrix)。

    行 = 7个指标，列 = 各场景。气泡面积编码绝对计数，
    颜色与 process_color_map 一致，较大气泡内显示数值。
    """
    matrix = _build_absolute_indicator_matrix(colocation_data, el_counts, saf_counts)
    n_rows, n_proc = matrix.shape
    bar_value_fontsize = max(6, UNIFORM_TEXT_SIZE - 2) * ROW2_BAR_VALUE_FONT_SCALE
    x_axis_fontsize = UNIFORM_TEXT_SIZE * ROW2_X_AXIS_FONT_SCALE

    proc_base_colors = [process_color_map.get(name, (0.55, 0.55, 0.55)) for name in scenario_names_cluster]
    local_max = float(np.max(matrix)) if np.max(matrix) > 0 else 1.0

    MAX_BUBBLE_AREA = 2800   # pts^2
    MIN_BUBBLE_AREA = 55

    for i in range(n_rows):
        ax.axhspan(i - 0.45, i + 0.45, alpha=0.04, color='#888888', zorder=0)
        for j in range(n_proc):
            val = matrix[i, j]
            if val <= 0:
                continue
            color = proc_base_colors[j]
            ratio = val / local_max
            size = MIN_BUBBLE_AREA + ratio * (MAX_BUBBLE_AREA - MIN_BUBBLE_AREA)
            ax.scatter([j], [i], s=size, color=color, alpha=0.85, zorder=3,
                       edgecolors='white', linewidths=0.9)
            # 数值标注：大泡内白字，小泡旁侧彩字
            fs = bar_value_fontsize * 0.62
            if ratio > 0.22:
                ax.text(j, i, _format_count_label(val),
                        ha='center', va='center',
                        fontsize=fs, color='white',
                        fontweight='bold', zorder=4)
            else:
                offset = 0.12 + 0.06 * (n_proc > 2)
                ax.text(j + offset, i, _format_count_label(val),
                        ha='left', va='center',
                        fontsize=fs * 0.90, color=color, zorder=4, clip_on=False)

    # 垂直分隔线
    for j in range(n_proc):
        ax.axvline(x=j, color='#E8E8E8', linewidth=0.8, zorder=0)
    for i in range(n_rows):
        ax.axhline(y=i, color='#EBEBEB', linewidth=0.6, zorder=0)

    ax.set_xlim(-0.60, n_proc - 0.40)
    ax.set_ylim(-0.6, n_rows - 0.4)
    ax.invert_yaxis()

    # X轴：场景缩写名
    ax.set_xticks(range(n_proc))
    ax.set_xticklabels(
        scenario_names_cluster,
        fontsize=x_axis_fontsize * 0.82,
        rotation=40, ha='right', rotation_mode='anchor'
    )
    ax.tick_params(axis='x', length=0, pad=2)

    y_ticks = np.arange(n_rows)
    ax.set_yticks(y_ticks)
    ax.set_yticklabels([""] * n_rows)
    ax.tick_params(axis="y", length=0)
    if show_ylabels:
        _draw_abs_stack_icons(ax, y_ticks, size_scale=3.2)

    for spine in ax.spines.values():
        spine.set_visible(False)

    return list(scenario_names_cluster)


def plot_grouped_bar_subplot(
    ax,
    scenario_names_cluster,
    colocation_data,
    el_counts,
    saf_counts,
    process_color_map,
    show_ylabels=False,
):
    """方案三：分组并列横向条形图 (Grouped Horizontal Bars)。

    每个指标行内，各场景的条形并列显示（非堆叠），
    可直接读取各场景的绝对计数，颜色与 process_color_map 一致。
    """
    matrix = _build_absolute_indicator_matrix(colocation_data, el_counts, saf_counts)
    n_rows, n_proc = matrix.shape
    bar_value_fontsize = max(6, UNIFORM_TEXT_SIZE - 2) * ROW2_BAR_VALUE_FONT_SCALE
    x_axis_fontsize = UNIFORM_TEXT_SIZE * ROW2_X_AXIS_FONT_SCALE

    proc_base_colors = [process_color_map.get(name, (0.55, 0.55, 0.55)) for name in scenario_names_cluster]
    local_max = float(np.max(matrix)) if np.max(matrix) > 0 else 1.0

    row_band = 0.82                    # 每行占用的垂直范围
    bar_height = row_band / max(n_proc, 1)
    bar_gap = bar_height * 0.08

    for i in range(n_rows):
        # 灰色底条（显示最大值范围）
        ax.barh(i, local_max, left=0, height=0.80,
                color="#F3F3F3", edgecolor="#D8D8D8", linewidth=0.6, zorder=0)

        for j in range(n_proc):
            val = matrix[i, j]
            group_top = i - row_band / 2
            y_pos = group_top + j * bar_height + bar_height / 2
            color = proc_base_colors[j]

            ax.barh(y_pos, val,
                    height=bar_height - bar_gap,
                    color=color, edgecolor='white', linewidth=0.4,
                    alpha=0.88, zorder=2)

            if val > 0:
                x_lbl = val + local_max * 0.015
                ax.text(x_lbl, y_pos, _format_count_label(val),
                        ha='left', va='center',
                        fontsize=bar_value_fontsize * 0.65,
                        color=color, zorder=3, clip_on=False)

        # 行间细分隔线
        if i < n_rows - 1:
            ax.axhline(y=i + 0.5, color='#DEDEDE', linewidth=0.7, zorder=1)

    ax.set_xlim(0, local_max * 1.22)
    ax.set_ylim(-0.6, n_rows - 0.4)
    ax.invert_yaxis()

    x_mid = _round_half_up(local_max * 0.5, 0) if local_max >= 10 else _round_half_up(local_max * 0.5, 2)
    x_max_tick = _round_half_up(local_max, 0) if local_max >= 10 else _round_half_up(local_max, 2)
    ax.set_xticks([0, x_mid, x_max_tick])
    ax.set_xticklabels([f"{0:g}", f"{x_mid:g}", f"{x_max_tick:g}"], fontsize=x_axis_fontsize)
    ax.set_xlabel("Counts", fontsize=x_axis_fontsize, color=UNIFORM_TEXT_COLOR)

    y_ticks = np.arange(n_rows)
    ax.set_yticks(y_ticks)
    ax.set_yticklabels([""] * n_rows)
    ax.tick_params(axis="y", length=0)
    if show_ylabels:
        _draw_abs_stack_icons(ax, y_ticks)

    ax.xaxis.grid(True, linestyle="--", linewidth=0.6, alpha=0.30)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    return list(scenario_names_cluster)


def create_process_legend(fig, process_color_map: Dict[str, tuple], process_names: List[str]):
    """Create external legend for process-color mapping."""
    if not process_names:
        return
    handles = [
        mpatches.Patch(facecolor=process_color_map[name], edgecolor='none', label=name)
        for name in process_names
    ]
    fig.legend(
        handles=handles,
        loc='lower center',
        bbox_to_anchor=(0.5, 0.018),
        ncol=min(7, len(handles)),
        fontsize=max(7, UNIFORM_TEXT_SIZE) * ROW2_LEGEND_FONT_SCALE,
        frameon=False,
        handlelength=1.4,
        columnspacing=0.8,
    )


def add_subplot_process_legend(ax, process_color_map: Dict[str, tuple], process_names: List[str]):
    """Add per-subplot legend under each second-row panel."""
    if not process_names:
        return
    handles = [
        mpatches.Patch(facecolor=process_color_map.get(name, (0.55, 0.55, 0.55)), edgecolor='none', label=name)
        for name in process_names
    ]
    ax.legend(
        handles=handles,
        loc='upper center',
        bbox_to_anchor=(0.5, -0.45),
        ncol=min(3, len(handles)),
        fontsize=max(7, UNIFORM_TEXT_SIZE) * ROW2_LEGEND_FONT_SCALE,
        frameon=False,
        handlelength=1.2,
        columnspacing=0.7,
        handletextpad=0.4,
        borderaxespad=0.0,
    )


def create_column_process_legends(
    fig,
    bar_axes,
    process_color_map: Dict[str, tuple],
    process_names_by_col: List[List[str]],
):
    """Create one legend block per column, positioned below each (top+bottom) pair."""
    if not bar_axes or not process_names_by_col:
        return
    y_anchor = min(ax.get_position().y0 for ax in bar_axes) - 0.05
    for ax, names in zip(bar_axes, process_names_by_col):
        if not names:
            continue
        handles = [
            mpatches.Patch(facecolor=process_color_map.get(name, (0.55, 0.55, 0.55)), edgecolor='none', label=name)
            for name in names
        ]
        pos = ax.get_position()
        x_anchor = (pos.x0 + pos.x1) * 0.5
        fig.legend(
            handles=handles,
            loc='upper center',
            bbox_to_anchor=(x_anchor, y_anchor),
            bbox_transform=fig.transFigure,
            ncol=min(3, len(handles)),
            fontsize=max(7, UNIFORM_TEXT_SIZE) * ROW2_LEGEND_FONT_SCALE,
            frameon=False,
            handlelength=1.2,
            columnspacing=0.7,
            handletextpad=0.4,
            borderaxespad=0.0,
        )


def create_legends(fig, bar_axes, secondary_axes):
    """Creates a single-line centered legend for categories and facilities."""
    # Co-location categories
    handles1 = [
        mpatches.Patch(facecolor=COLOCATION_COLORS[c], label=COLOCATION_DISPLAY_LABELS.get(c, c))
        for c in COLOCATION_CATEGORIES
    ]

    # Facility count lines
    handles2 = [
        Line2D([0], [0], color=LINE_COLORS['electrolyzer'], marker='o',
               label=FACILITY_DISPLAY_LABELS['electrolyzer']),
        Line2D([0], [0], color=LINE_COLORS['saf_plant'], marker='s',
               label=FACILITY_DISPLAY_LABELS['saf_plant'])
    ]

    all_handles = handles1 + handles2
    fig.legend(
        handles=all_handles,
        loc='lower center',
        bbox_to_anchor=(0.5, 0.018),
        ncol=len(all_handles),
        fontsize=BOTTOM_LEGEND_SIZE,
        frameon=False,
        handlelength=1.5,
        columnspacing=0.9
    )


# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------

def _load_metrics(csv_path: Path) -> List[dict]:
    rows = []
    if not csv_path.exists(): raise FileNotFoundError(f"File not found: {csv_path}")
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader: rows.append(row)
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
    with path.open("r", encoding="utf-8") as f: return json.load(f)

def _get_facility_counts(official_name: str, solutions_dir: Path) -> Tuple[int, int]:
    solution_path = solutions_dir / f"{official_name}_complete_solution.json"
    if not solution_path.exists(): return 0, 0
    data = _load_complete_solution(solution_path)
    
    saf_locations = set()
    electrolyzer_locations = set()
    for info in _iter_facility_entries(data.get("facilities", {})):
        if not info.get("built", True):
            continue
        tech = info.get("technology")
        loc = info.get("location") or info.get("name") or info.get("source_id")
        if tech == "electrolyzer" and loc: electrolyzer_locations.add(str(loc))
        if tech in SAF_TECH:
            if loc:
                saf_locations.add(str(loc))

    for info in _iter_facility_entries(data.get("hydrogen_facilities", {})):
        if not info.get("built", True):
            continue
        if info.get("technology") == "electrolyzer":
            loc = info.get("location") or info.get("name") or info.get("source_id")
            if loc: electrolyzer_locations.add(str(loc))
            
    return len(electrolyzer_locations), len(saf_locations)

def _load_classification_data(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists(): raise FileNotFoundError(f"{csv_path}")
    return pd.read_csv(csv_path, encoding="utf-8-sig")

def _resolve_classification_csv(csv_path: Path = DEFAULT_CLASSIFICATION_CSV) -> Path:
    candidates = sorted((VIS_ROOT / "results").glob(CLASSIFICATION_RESULTS_PATTERN), reverse=True)
    if candidates:
        return candidates[0]
    return csv_path

def _aggregate_colocation_counts(df: pd.DataFrame, official_name: str) -> Dict[str, int]:
    scenario_df = df[df["OfficialName"] == official_name]
    if scenario_df.empty:
        aliases = CLASSIFICATION_NAME_ALIASES.get(official_name, [])
        if aliases:
            scenario_df = df[df["OfficialName"].isin(aliases)]

    counts = {cat: 0 for cat in COLOCATION_CATEGORIES}
    for _, row in scenario_df.iterrows():
        ml, sp, con, c = row["MaterialLabel"], row["SAF_Production"], row["Consumption"], int(row["Count"])
        hrm, hs, hc = (ml != "No raw material production"), (sp == "yes"), (con == "yes")
        
        if hs and hc: counts["SAF + Consumption"] += c
        elif hrm and hs: counts["Raw Material + SAF"] += c
        elif hrm and not hs and not hc: counts["Raw Material Only"] += c
        elif not hrm and hs and not hc: counts["SAF Only"] += c
        elif not hrm and not hs and hc: counts["Consumption Only"] += c
        else:
            if hrm: counts["Raw Material Only"] += c
    return counts

def main(row2_style: str = 'dot_matrix'):
    """生成完整的双行可视化图。

    Parameters
    ----------
    row2_style : str
        第二行可视化风格：'dot_matrix'（默认气泡矩阵）、'stacked'、
        'lollipop' 或 'grouped_bar'。
    """
    setup_plot_style()
    
    try:
        rows = _load_metrics(DEFAULT_METRICS_CSV)
        classification_df = _load_classification_data(_resolve_classification_csv())
    except FileNotFoundError as e:
        print(e); return

    scenarios = [r["Scenario"] for r in rows]
    official_names = [SCENARIO_NAME_MAP.get(s, s) for s in scenarios]
    clusters = [int(r["Cluster"]) for r in rows]

    metrics_raw = np.array([[float(r["节点数量"]), float(r["关键节点集中度"]), float(r["关键通道集中度"]),
                             float(r["平均运输距离"]), float(r["跨区域物流比例"]), float(r["单点失效影响"])] for r in rows], dtype=float)
    metrics_norm = _normalize_metrics(metrics_raw)

    siting_counts = []
    colocation_counts = []
    for name in official_names:
        el, saf = _get_facility_counts(name, DEFAULT_SOLUTIONS_DIR)
        siting_counts.append((el, saf))
        colocation_counts.append(_aggregate_colocation_counts(classification_df, name))

    cluster_map = {}
    for idx, c in enumerate(clusters): cluster_map.setdefault(c, []).append(idx)
    _sorted = sorted(cluster_map.keys())[:4]
    # 列顺序调整：原[1,2,3,4] → 新[4,3,1,2]（0-indexed: [3,2,0,1]）
    target_clusters = [_sorted[3], _sorted[2], _sorted[0], _sorted[1]]

    # Figure Layout
    _fig_w = 36.0 if row2_style == 'dot_matrix' else 28.0
    _fig_h = 22.0 if row2_style == 'dot_matrix' else 18.0
    fig = plt.figure(figsize=(_fig_w, _fig_h))
    # dot_matrix 不需要底部 legend 预留空间
    _bottom = 0.08 if row2_style == 'dot_matrix' else 0.18
    _h_ratios = [2.40, 2.20] if row2_style == 'dot_matrix' else [2.40, 1.40]
    gs = gridspec.GridSpec(
        2, 4,
        height_ratios=_h_ratios,
        hspace=0.30,
        wspace=0.18,
        top=0.93,
        bottom=_bottom,
        left=0.08,
        right=0.96,
    )

    radar_axes, bar_axes = [], []
    ordered_process_names = list(dict.fromkeys(official_names))
    process_color_map = _build_process_color_map(ordered_process_names)

    # Row 1: Radar
    for i, cid in enumerate(target_clusters):
        ax = fig.add_subplot(gs[0, i], polar=True)
        theme = CLUSTER_THEMES.get(cid, {"header": "#DDDDDD", "stroke": "#333333"})

        idxs = sorted(cluster_map[cid], key=lambda x: official_names[x])
        plot_radar_subplot(ax, metrics_norm, idxs, theme, official_names, process_color_map)
        add_colored_title(
            ax,
            f"MC{cid + 1}: {CLUSTER_NAMES.get(cid, f'Cluster {cid}')}",
            theme["header"],
            y_offset=1.24,
        )
        radar_axes.append(ax)

    # Row 2: Absolute stacked indicator rows (per-subplot max with blank remainder)
    cluster_indices_list = []
    for cid in target_clusters:
        idxs = sorted(cluster_map[cid], key=lambda x: official_names[x])
        cluster_indices_list.append(idxs)

    # Row 2: 根据 row2_style 选择可视化函数
    _ROW2_FNS = {
        'stacked':     plot_absolute_indicator_stack_subplot,
        'lollipop':    plot_lollipop_subplot,
        'dot_matrix':  plot_dot_matrix_subplot,
        'grouped_bar': plot_grouped_bar_subplot,
    }
    row2_fn = _ROW2_FNS.get(row2_style, plot_absolute_indicator_stack_subplot)

    process_names_by_col = []
    for i, cid in enumerate(target_clusters):
        ax = fig.add_subplot(gs[1, i])

        idxs = cluster_indices_list[i]
        names = [official_names[ix] for ix in idxs]
        el = [siting_counts[ix][0] for ix in idxs]
        saf = [siting_counts[ix][1] for ix in idxs]
        col = [colocation_counts[ix] for ix in idxs]

        extra_kwargs = {}
        if row2_style == 'stacked':
            extra_kwargs['mean_only_rows'] = MEAN_ONLY_ROWS_BY_SUBPLOT.get(i, set())

        row2_fn(
            ax,
            names,
            col,
            el,
            saf,
            process_color_map,
            show_ylabels=(i == 0),
            **extra_kwargs,
        )
        process_names_by_col.append(names)
        bar_axes.append(ax)

    # dot_matrix 需要完整宽度来显示场景名称，其他风格适当收窄
    if row2_style != 'dot_matrix':
        for ax in bar_axes:
            pos = ax.get_position()
            ax.set_position([pos.x0, pos.y0, pos.width * ROW2_AXIS_WIDTH_RATIO, pos.height])

    # dot_matrix 已在 x 轴显示场景名，不需要额外 legend
    if row2_style != 'dot_matrix':
        create_column_process_legends(fig, bar_axes, process_color_map, process_names_by_col)

    # Add Panel Labels (e-l): place in figure coordinates for strict column alignment.
    row1_labels = ['(e)', '(f)', '(g)', '(h)']
    row2_labels = ['(i)', '(j)', '(k)', '(l)']
    label_x_offset = 0.012
    label_y_offset = 0.008
    n_cols = min(len(radar_axes), len(bar_axes), len(row1_labels), len(row2_labels))
    for i in range(n_cols):
        col_x = bar_axes[i].get_position().x0 - label_x_offset
        top_y = radar_axes[i].get_position().y1 + label_y_offset
        bottom_y = bar_axes[i].get_position().y1 + label_y_offset
        fig.text(
            col_x,
            top_y,
            row1_labels[i],
            transform=fig.transFigure,
            fontsize=PANEL_LABEL_SIZE,
            fontweight='bold',
            color=UNIFORM_TEXT_COLOR,
            va='bottom',
            ha='left',
        )
        fig.text(
            col_x,
            bottom_y,
            row2_labels[i],
            transform=fig.transFigure,
            fontsize=PANEL_LABEL_SIZE,
            fontweight='bold',
            color=UNIFORM_TEXT_COLOR,
            va='bottom',
            ha='left',
        )


    # Save
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    style_suffix = f"_{row2_style}" if row2_style != 'stacked' else ""
    out_dir = VIS_ROOT / f"results/combined_cluster_vis_{timestamp}{style_suffix}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "combined_cluster_visualization_style_ref.png"
    out_path_pdf = out_dir / "combined_cluster_visualization_style_ref.pdf"
    
    # dot_matrix 使用 tight 防止旋转的 x 轴标签被裁剪
    _bbox = 'tight' if row2_style == 'dot_matrix' else None
    fig.savefig(out_path, dpi=600, bbox_inches=_bbox)
    fig.savefig(out_path_pdf, dpi=600, bbox_inches=_bbox)
    print(f"Saved: {out_path}")
    plt.close(fig)

def main_compare():
    """依次生成三种第二行可视化方案，供对比选择。"""
    for style in ['lollipop', 'dot_matrix', 'grouped_bar']:
        print(f"\n=== 生成方案: {style} ===")
        main(row2_style=style)


if __name__ == "__main__":
    import sys
    if '--compare' in sys.argv:
        main_compare()
    else:
        main()
