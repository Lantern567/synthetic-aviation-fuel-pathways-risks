"""
副产氢+煤 场景：按设施点逐一输出其相关运输路径图
Byproduct H2 + Coal: one map per facility with its connected routes
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import matplotlib
import matplotlib.pyplot as plt

BASE_DIR = Path(__file__).resolve().parents[3]
sys.path.append(str(BASE_DIR))

from products.supply_chain_optimization.visualization.thirteen_scenarios_clustered_map_visualization import (
    ThirteenScenariosClusteredMapVisualizer,
)


def _parse_coord(coord_str):
    if pd.isna(coord_str) or not coord_str:
        return None, None
    try:
        import re

        match = re.search(r"\(([^,]+),\s*([^)]+)\)", str(coord_str))
        if match:
            lat = float(match.group(1))
            lon = float(match.group(2))
            return lat, lon
    except Exception:
        pass
    return None, None


def _safe_name(text: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in text)


def main():
    base = BASE_DIR
    results_dir = base / "products/supply_chain_optimization/visualization/results"

    # locate latest transport_summary for byproduct h2 + coal
    csv_dir = base / "products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/byproduct_hydrogen"
    csv_candidates = sorted(csv_dir.glob("transport_summary_*.csv"), reverse=True)
    if not csv_candidates:
        raise FileNotFoundError("未找到 transport_summary_*.csv")
    transport_csv = csv_candidates[0]

    # locate latest complete_solution (optional)
    solution_candidates = sorted(csv_dir.glob("complete_solution_*.json"), reverse=True)
    complete_solution = None
    if solution_candidates:
        complete_solution = solution_candidates[0]

    # output dir
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = results_dir / f"byproduct_h2_coal_facility_routes_{timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # load data
    transport = pd.read_csv(transport_csv)
    solution_data = None
    if complete_solution and complete_solution.exists():
        with open(complete_solution, "r", encoding="utf-8") as f:
            solution_data = json.load(f)

    # init visualizer (reuses map style and colors)
    vis = ThirteenScenariosClusteredMapVisualizer(output_dir=results_dir)

    # build facility set by reusing plot_facilities
    fig, ax = vis.create_base_map(figsize=(6, 4))
    vis.plot_facilities(ax, transport, "Byproduct H2 + Coal", solution_data)
    facility_keys = sorted(list(vis.visible_facility_coords))
    plt.close(fig)

    # gather routes (volume>0 only)
    route_rows = []
    for _, row in transport.iterrows():
        volume = vis._get_transport_volume(row, volume_type="kg")
        if volume <= 0.01:
            volume = vis._get_transport_volume(row, volume_type="m³")
        if volume <= 0.01:
            continue

        start_lat, start_lon = _parse_coord(row.get("起点坐标"))
        end_lat, end_lon = _parse_coord(row.get("终点坐标"))
        if start_lat is None or start_lon is None or end_lat is None or end_lon is None:
            continue

        if not vis._in_extent(start_lon, start_lat) or not vis._in_extent(end_lon, end_lat):
            continue

        route_rows.append((row, start_lon, start_lat, end_lon, end_lat))

    # colors
    colors = vis.transport_colors
    default_color = "#56B4E9"

    # one map per facility
    for idx, key in enumerate(facility_keys, start=1):
        focus_lon, focus_lat = key

        fig, ax = vis.create_base_map(figsize=(18, 14))
        vis.plot_pipeline_networks(ax)
        vis.plot_facilities(ax, transport, "Byproduct H2 + Coal", solution_data)

        # highlight focus facility
        ax.scatter(
            focus_lon,
            focus_lat,
            s=220,
            marker="o",
            facecolors="none",
            edgecolors="#FF0000",
            linewidth=2.0,
            transform=vis.data_crs,
            zorder=40,
        )

        # draw routes connected to focus facility
        connected = 0
        for row, slon, slat, elon, elat in route_rows:
            sk = vis._coord_key(slon, slat)
            ek = vis._coord_key(elon, elat)
            if sk != key and ek != key:
                continue

            cargo = str(row.get("货物类型", ""))
            if cargo == "氢气":
                color = colors.get("H2_cluster", default_color)
                linestyle = ":"
                lw = 1.2
            elif "CO2" in cargo or "CO₂" in cargo or "二氧化碳" in cargo:
                color = colors.get("CO2", "#E41A1C")
                linestyle = "-"
                lw = 1.2
            elif cargo == "天然气":
                color = colors.get("NG", "#2CA02C")
                linestyle = "-"
                lw = 1.2
            elif cargo in ("MTJ", "SAF"):
                color = colors.get("SAF", "#FF7F0E")
                linestyle = "-"
                lw = 1.5
            else:
                color = default_color
                linestyle = "-"
                lw = 1.1

            route_coords = None
            if "路径坐标" in row and row["路径坐标"] and row["路径坐标"] != "[]":
                try:
                    route_coords = json.loads(row["路径坐标"])
                    route_coords = vis._normalize_path_coords(route_coords)
                except Exception:
                    route_coords = None

            if route_coords and len(route_coords) >= 2:
                lons = [c[0] for c in route_coords]
                lats = [c[1] for c in route_coords]
                ax.plot(
                    lons,
                    lats,
                    color=color,
                    linestyle=linestyle,
                    linewidth=lw,
                    alpha=0.8,
                    transform=vis.data_crs,
                    zorder=20,
                )
            else:
                ax.plot(
                    [slon, elon],
                    [slat, elat],
                    color=color,
                    linestyle=linestyle,
                    linewidth=lw,
                    alpha=0.8,
                    transform=vis.data_crs,
                    zorder=20,
                )

            connected += 1

        title = f"Byproduct H2 + Coal | Facility {idx}/{len(facility_keys)} | Routes {connected}"
        ax.set_title(title, fontsize=14)

        filename = f"facility_{idx:03d}_{_safe_name(f'{focus_lon:.4f}_{focus_lat:.4f}')}.png"
        fig.savefig(out_dir / filename, dpi=300, bbox_inches="tight")
        plt.close(fig)

    print(f"完成：{len(facility_keys)} 个设施图已输出到 {out_dir}")


if __name__ == "__main__":
    main()
