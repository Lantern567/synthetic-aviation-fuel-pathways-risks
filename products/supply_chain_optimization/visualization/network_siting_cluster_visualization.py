"""
Cluster-level visualization of siting choices, facility counts, and transport distances.
Each cluster produces one figure containing multiple scenarios (English labels).
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import re

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

DEFAULT_METRICS_CSV = PROJECT_ROOT / (
    "products/supply_chain_optimization/visualization/results/"
    "network_classification_20260127_210416/scenario_network_metrics.csv"
)

DEFAULT_SOLUTIONS_DIR = PROJECT_ROOT / (
    "products/supply_chain_optimization/visualization/results/collected_latest_data"
)

# Official scenario codes used across visualization scripts
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

SAF_TECH = {
    "ft_direct_conversion",
    "green_h2_co2_to_saf",
    "airport_integrated_conversion",
    "pipeline_direct_conversion",
}

ELECTROLYZER_TECH = "electrolyzer"

LOCATION_CATEGORY = {
    "solar_plant": "Renewable site",
    "wind_farm": "Renewable site",
    "co2_capture": "CO2 capture site",
    "airport": "Airport site",
    "airport_with_ng_supply": "Airport site",
    "byproduct_hydrogen_refinery": "Byproduct H2 site",
    "byproduct_hydrogen_steel": "Byproduct H2 site",
}

CATEGORY_ORDER = [
    "Renewable site",
    "CO2 capture site",
    "Airport site",
    "Byproduct H2 site",
    "Other site",
]

# Facility classification labels used in clustered map visualization
RAW_MATERIAL_LABELS = {
    "h2": "H2 production",
    "co2": "CO2 capture",
    "natural_gas": "Natural gas supply",
}


def _iter_facility_entries(container) -> Iterable[dict]:
    if isinstance(container, dict):
        return [v for v in container.values() if isinstance(v, dict)]
    if isinstance(container, list):
        return [v for v in container if isinstance(v, dict)]
    return []


def _weighted_avg_distance(df: pd.DataFrame, cargo_types: Iterable[str]) -> float:
    if df.empty:
        return float("nan")
    sub = df[df["货物类型"].isin(list(cargo_types))].copy()
    if sub.empty:
        return float("nan")
    dist = pd.to_numeric(sub["距离(km)"], errors="coerce")
    weight = pd.to_numeric(sub["周运输量(kg)"], errors="coerce")
    mask = dist.notna() & weight.notna()
    if mask.sum() == 0:
        return float("nan")
    total_weight = weight[mask].sum()
    if total_weight == 0:
        return float("nan")
    return float((dist[mask] * weight[mask]).sum() / total_weight)


def _parse_coord(coord_str: str) -> Tuple[float | None, float | None]:
    if coord_str is None or pd.isna(coord_str) or not str(coord_str).strip():
        return None, None
    match = re.search(r"\(([\d.]+),\s*([\d.]+)\)", str(coord_str))
    if not match:
        return None, None
    try:
        lat = float(match.group(1))
        lon = float(match.group(2))
    except ValueError:
        return None, None
    return lat, lon


def _get_transport_volume(row: pd.Series, volume_type: str = "kg") -> float:
    if volume_type == "kg":
        weekly = row.get("周运输量(kg)", None)
        if pd.notna(weekly):
            try:
                return float(weekly)
            except (ValueError, TypeError):
                pass
        daily = row.get("日运输量(kg)", None)
        if pd.notna(daily):
            try:
                return float(daily) * 7.0
            except (ValueError, TypeError):
                pass
    else:
        weekly = row.get("周运输量(m3)", None)
        if pd.notna(weekly):
            try:
                return float(weekly)
            except (ValueError, TypeError):
                pass
        weekly = row.get("周运输量(m³)", None)
        if pd.notna(weekly):
            try:
                return float(weekly)
            except (ValueError, TypeError):
                pass
        daily = row.get("日运输量(m3)", None)
        if pd.notna(daily):
            try:
                return float(daily) * 7.0
            except (ValueError, TypeError):
                pass
        daily = row.get("日运输量(m³)", None)
        if pd.notna(daily):
            try:
                return float(daily) * 7.0
            except (ValueError, TypeError):
                pass
    return 0.0


def _classify_facility(
    facility_name: str,
    facility_types: set,
    cargo_types: set | None,
) -> Tuple[frozenset, str, str]:
    name_lower = str(facility_name).lower()
    if cargo_types is None:
        cargo_types = set()
    if facility_types is None:
        facility_types = set()
    types_lower = {str(t).lower() for t in facility_types}

    # Dimension 3: consumption
    is_consumption = "no"
    if "airport" in name_lower or facility_name in ["天津", "北京"]:
        is_consumption = "yes"
    if any("机场" in t for t in types_lower):
        is_consumption = "yes"

    # Dimension 2: SAF production
    has_saf_production = "no"
    if any("factory" in t or "工厂" in t for t in types_lower):
        has_saf_production = "yes"
    elif "saf" in name_lower:
        has_saf_production = "yes"
    elif "MTJ" in cargo_types:
        has_saf_production = "yes"

    # Dimension 1: raw material production
    raw_material_types = set()
    if "氢气" in cargo_types:
        raw_material_types.add("h2")
    if "CO2" in cargo_types:
        raw_material_types.add("co2")
    if "天然气" in cargo_types:
        raw_material_types.add("natural_gas")

    if not raw_material_types:
        if any("co2" in t or "捕获" in t or "capture" in t for t in types_lower):
            raw_material_types.add("co2")
        if any(k in name_lower for k in ["dac", "carbon", "co2", "碳", "捕获"]):
            raw_material_types.add("co2")

        if any("天然气" in t or "natural gas" in t or "ng" in t for t in types_lower):
            raw_material_types.add("natural_gas")
        if "ng_pipeline" in name_lower or ("天然气" in name_lower and "管道" in name_lower):
            raw_material_types.add("natural_gas")

        if any("氢气" in t or "hydrogen" in t for t in types_lower):
            raw_material_types.add("h2")
        if any(k in name_lower for k in ["solar", "wind", "pv", "photovoltaic", "光伏", "风能", "风电", "coal", "煤炭", "煤制"]):
            raw_material_types.add("h2")

    if is_consumption == "yes":
        raw_material_types.clear()

    return frozenset(raw_material_types), has_saf_production, is_consumption


def _collect_facility_info(
    transport_summary: pd.DataFrame,
    module_name: str,
    complete_solution: dict | None,
) -> Tuple[Dict[Tuple[float, float], dict], Dict[Tuple[float, float], dict]]:
    # facility_production: {coord: {cargo: volume}}
    facility_production: Dict[Tuple[float, float], dict] = {}
    facility_info: Dict[Tuple[float, float], dict] = {}

    # First pass: production by source
    for _, row in transport_summary.iterrows():
        volume = _get_transport_volume(row, "kg")
        if volume <= 0.01:
            volume = _get_transport_volume(row, "m3")
        if volume <= 0.01:
            continue

        cargo_type = row.get("货物类型", "")
        start_lat, start_lon = _parse_coord(row.get("起点坐标"))
        if start_lat is None or start_lon is None or not cargo_type:
            continue
        coord_key = (start_lon, start_lat)
        if coord_key not in facility_production:
            facility_production[coord_key] = {}
        facility_production[coord_key][cargo_type] = facility_production[coord_key].get(cargo_type, 0) + volume

    # Second pass: collect facility info for sources and destinations
    for _, row in transport_summary.iterrows():
        volume = _get_transport_volume(row, "kg")
        if volume <= 0.01:
            volume = _get_transport_volume(row, "m3")
        if volume <= 0.01:
            continue

        start_name = row.get("起点", "")
        end_name = row.get("终点", "")
        start_type = str(row.get("起点类型", "")).strip()
        end_type = str(row.get("终点类型", "")).strip()
        cargo_type = row.get("货物类型", "")

        start_lat, start_lon = _parse_coord(row.get("起点坐标"))
        end_lat, end_lon = _parse_coord(row.get("终点坐标"))

        if start_lat is not None and start_lon is not None and start_name:
            coord_key = (start_lon, start_lat)
            if coord_key in facility_production:
                info = facility_info.setdefault(coord_key, {"names": set(), "types": set(),
                                                            "cargos_as_source": set(), "cargos_as_dest": set()})
                info["names"].add(start_name)
                if start_type:
                    info["types"].add(start_type)
                if cargo_type:
                    info["cargos_as_source"].add(cargo_type)

        if end_lat is not None and end_lon is not None and end_name:
            coord_key = (end_lon, end_lat)
            info = facility_info.setdefault(coord_key, {"names": set(), "types": set(),
                                                        "cargos_as_source": set(), "cargos_as_dest": set()})
            info["names"].add(end_name)
            if end_type:
                info["types"].add(end_type)
            if cargo_type:
                info["cargos_as_dest"].add(cargo_type)

    # Add airport SAF plants from complete_solution
    if complete_solution is not None:
        facilities = complete_solution.get("facilities", {})
        for _, facility_data in facilities.items():
            if not facility_data.get("built", False):
                continue
            location_type = str(facility_data.get("location_type", ""))
            source_type = str(facility_data.get("source_type", ""))
            actual_production = facility_data.get("actual_annual_production_kg", 0) or 0
            is_airport_facility = ("airport" in location_type.lower() or "airport" in source_type.lower())
            if is_airport_facility and actual_production > 1:
                lat = facility_data.get("latitude")
                lon = facility_data.get("longitude")
                if lat is None or lon is None:
                    continue
                coord_key = (lon, lat)
                if coord_key not in facility_info:
                    facility_name = facility_data.get("name", f"Airport SAF {coord_key}")
                    facility_info[coord_key] = {
                        "names": {facility_name},
                        "types": {"airport", location_type},
                        "cargos_as_source": {"MTJ"},
                        "cargos_as_dest": {"MTJ"},
                    }
                    facility_production[coord_key] = {"MTJ": actual_production / 52.0}
                else:
                    facility_info[coord_key]["cargos_as_source"].add("MTJ")
                    facility_info[coord_key]["cargos_as_dest"].add("MTJ")

    # Add electrolyzers from complete_solution
    built_electrolyzers: Dict[Tuple[float, float], dict] = {}
    if complete_solution is not None:
        facilities = complete_solution.get("facilities", {})
        location_coords = {}
        for _, row in transport_summary.iterrows():
            s_name = row.get("起点", "")
            s_coord = row.get("起点坐标", "")
            if s_name and s_coord:
                lat, lon = _parse_coord(s_coord)
                if lat is not None and lon is not None:
                    location_coords[s_name] = (lat, lon)
            e_name = row.get("终点", "")
            e_coord = row.get("终点坐标", "")
            if e_name and e_coord:
                lat, lon = _parse_coord(e_coord)
                if lat is not None and lon is not None:
                    location_coords[e_name] = (lat, lon)

        for _, facility_data in facilities.items():
            if not facility_data.get("built", False):
                continue
            if facility_data.get("technology") != "electrolyzer":
                continue
            h2_production = facility_data.get("actual_annual_production_kg", 0) or 0
            if h2_production <= 1:
                continue
            location_name = facility_data.get("location") or facility_data.get("name")
            if location_name in location_coords:
                lat, lon = location_coords[location_name]
                coord_key = (lon, lat)
                built_electrolyzers[coord_key] = {
                    "h2_production_kg_year": h2_production,
                    "location_name": location_name,
                }
                if coord_key not in facility_info:
                    facility_info[coord_key] = {
                        "names": {location_name},
                        "types": {"wind_farm", "solar_plant"},
                        "cargos_as_source": set(),
                        "cargos_as_dest": set(),
                    }
                else:
                    facility_info[coord_key]["names"].add(location_name)

    # Special filter: Natural Gas Two-Step
    if module_name == "Natural Gas Two-Step":
        filtered_info = {}
        for coord, info in facility_info.items():
            saf_volume = 0
            if coord in facility_production and "MTJ" in facility_production[coord]:
                saf_volume = facility_production[coord]["MTJ"]
            is_pure_saf_producer = (info["cargos_as_source"] == {"MTJ"})
            if saf_volume > 10 or not is_pure_saf_producer:
                filtered_info[coord] = info
        facility_info = filtered_info

    return facility_info, built_electrolyzers


def _count_facility_classes(
    transport_summary: pd.DataFrame,
    module_name: str,
    complete_solution: dict | None,
) -> Counter:
    facility_info, built_electrolyzers = _collect_facility_info(
        transport_summary, module_name, complete_solution
    )

    counts = Counter()
    for (lon, lat), info in facility_info.items():
        representative_name = list(info["names"])[0] if info["names"] else ""
        raw_materials, saf_production, consumption = _classify_facility(
            representative_name, info["types"], info["cargos_as_source"]
        )
        if (lon, lat) in built_electrolyzers and "h2" not in raw_materials:
            raw_materials = frozenset(set(raw_materials) | {"h2"})

        if not raw_materials:
            material_label = "No raw material production"
            key = (material_label, saf_production, consumption)
            counts[key] += 1
        elif len(raw_materials) == 1:
            material_label = RAW_MATERIAL_LABELS.get(next(iter(raw_materials)), "Unknown")
            key = (material_label, saf_production, consumption)
            counts[key] += 1
        else:
            labels = [RAW_MATERIAL_LABELS.get(m, "Unknown") for m in sorted(raw_materials)]
            material_label = "+".join(labels)
            key = (material_label, saf_production, consumption)
            counts[key] += 1

    return counts


def _load_complete_solution(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _compute_scenario_metrics(
    scenario: str,
    official_name: str,
    transport_summary: str,
    solutions_dir: Path,
) -> Dict[str, float]:
    solution_path = solutions_dir / f"{official_name}_complete_solution.json"
    if not solution_path.exists():
        raise FileNotFoundError(f"Missing complete solution: {solution_path}")

    data = _load_complete_solution(solution_path)

    saf_count = 0
    saf_counts_by_cat = Counter({c: 0 for c in CATEGORY_ORDER})
    saf_seen: set[Tuple[str, str, str]] = set()

    electrolyzer_locations: set[str] = set()

    for info in _iter_facility_entries(data.get("facilities", {})):
        tech = info.get("technology")
        location = info.get("location") or info.get("name") or info.get("source_id")
        if tech == ELECTROLYZER_TECH and location:
            electrolyzer_locations.add(str(location))
        if tech in SAF_TECH:
            key = (str(location), tech, str(info.get("location_type")))
            if key in saf_seen:
                continue
            saf_seen.add(key)
            saf_count += 1
            loc_type = info.get("location_type")
            category = LOCATION_CATEGORY.get(loc_type, "Other site")
            saf_counts_by_cat[category] += 1

    for info in _iter_facility_entries(data.get("hydrogen_facilities", {})):
        if info.get("technology") == ELECTROLYZER_TECH:
            location = info.get("location") or info.get("name") or info.get("source_id")
            if location:
                electrolyzer_locations.add(str(location))

    electrolyzer_count = len(electrolyzer_locations)

    saf_shares = {}
    for cat in CATEGORY_ORDER:
        if saf_count == 0:
            saf_shares[cat] = 0.0
        else:
            saf_shares[cat] = saf_counts_by_cat[cat] / saf_count * 100.0

    # Transport distances
    avg_h2_distance = float("nan")
    avg_saf_distance = float("nan")
    if transport_summary and Path(transport_summary).exists():
        tdf = pd.read_csv(transport_summary)
        avg_h2_distance = _weighted_avg_distance(tdf, ["氢气"])
        avg_saf_distance = _weighted_avg_distance(tdf, ["SAF", "MTJ"])

    metrics = {
        "Scenario": scenario,
        "OfficialName": official_name,
        "SAF_Plants": saf_count,
        "Electrolyzers": electrolyzer_count,
        "Avg_H2_Distance_km": avg_h2_distance,
        "Avg_SAF_Distance_km": avg_saf_distance,
    }
    for cat in CATEGORY_ORDER:
        metrics[f"SAF_Share_{cat}"] = saf_shares[cat]
        metrics[f"SAF_Count_{cat}"] = saf_counts_by_cat[cat]
    return metrics


def _plot_cluster(df_cluster: pd.DataFrame, cluster_id: int, out_path: Path) -> None:
    df_cluster = df_cluster.sort_values("OfficialName")
    scenarios = df_cluster["OfficialName"].tolist()
    x = np.arange(len(scenarios))

    fig, axes = plt.subplots(3, 1, figsize=(10, 12), constrained_layout=True)
    fig.suptitle(f"Cluster {cluster_id}: Siting, Scale and Transport", fontsize=14)

    # Panel 1: SAF plant siting shares
    bottom = np.zeros(len(scenarios))
    colors = plt.cm.Set2.colors
    for idx, cat in enumerate(CATEGORY_ORDER):
        vals = df_cluster[f"SAF_Share_{cat}"].values
        axes[0].bar(x, vals, bottom=bottom, label=cat, color=colors[idx % len(colors)])
        bottom += vals
    axes[0].set_ylabel("Share of SAF plants (%)")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(scenarios, rotation=25, ha="right")
    axes[0].legend(loc="upper right", fontsize=8, frameon=False, ncol=2)

    # Panel 2: facility counts
    width = 0.35
    axes[1].bar(x - width / 2, df_cluster["Electrolyzers"], width, label="Electrolyzers")
    axes[1].bar(x + width / 2, df_cluster["SAF_Plants"], width, label="SAF plants")
    axes[1].set_ylabel("Count")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(scenarios, rotation=25, ha="right")
    axes[1].legend(loc="upper right", fontsize=9, frameon=False)

    # Panel 3: transport distances
    h2_dist = df_cluster["Avg_H2_Distance_km"].fillna(0.0)
    saf_dist = df_cluster["Avg_SAF_Distance_km"].fillna(0.0)
    axes[2].bar(x - width / 2, h2_dist, width, label="H2 avg distance")
    axes[2].bar(x + width / 2, saf_dist, width, label="SAF avg distance")
    axes[2].set_ylabel("Distance (km)")
    axes[2].set_xticks(x)
    axes[2].set_xticklabels(scenarios, rotation=25, ha="right")
    axes[2].legend(loc="upper right", fontsize=9, frameon=False)

    fig.text(0.5, 0.01, "Note: 0 km means no corresponding flow in this scenario.",
             ha="center", fontsize=8)
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def main(
    metrics_csv: Path = DEFAULT_METRICS_CSV,
    solutions_dir: Path = DEFAULT_SOLUTIONS_DIR,
) -> Path:
    df = pd.read_csv(metrics_csv)
    records: List[Dict[str, float]] = []
    classification_rows: List[Dict[str, str]] = []

    for _, row in df.iterrows():
        scenario = row["Scenario"]
        official_name = SCENARIO_NAME_MAP.get(scenario, scenario)
        transport_summary = row.get("TransportSummary", "")
        metrics = _compute_scenario_metrics(
            scenario=scenario,
            official_name=official_name,
            transport_summary=transport_summary,
            solutions_dir=solutions_dir,
        )
        metrics["Cluster"] = int(row["Cluster"])
        records.append(metrics)

        if transport_summary and Path(transport_summary).exists():
            solution_path = solutions_dir / f"{official_name}_complete_solution.json"
            complete_solution = None
            if solution_path.exists():
                complete_solution = _load_complete_solution(solution_path)
            counts = _count_facility_classes(
                pd.read_csv(transport_summary),
                scenario,
                complete_solution,
            )
            for (material_label, saf_prod, consumption), count in counts.items():
                classification_rows.append({
                    "Scenario": scenario,
                    "OfficialName": official_name,
                    "Cluster": int(row["Cluster"]),
                    "MaterialLabel": material_label,
                    "SAF_Production": saf_prod,
                    "Consumption": consumption,
                    "Count": count,
                })

    metrics_df = pd.DataFrame(records)

    out_dir = PROJECT_ROOT / (
        "products/supply_chain_optimization/visualization/results/"
        f"network_siting_clusters_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    metrics_csv_out = out_dir / "scenario_siting_metrics.csv"
    metrics_df.to_csv(metrics_csv_out, index=False, encoding="utf-8-sig")

    if classification_rows:
        classification_df = pd.DataFrame(classification_rows)
        classification_csv = out_dir / "scenario_decision_point_classification_counts.csv"
        classification_df.to_csv(classification_csv, index=False, encoding="utf-8-sig")

        cluster_df = (
            classification_df
            .groupby(["Cluster", "MaterialLabel", "SAF_Production", "Consumption"], as_index=False)["Count"]
            .sum()
        )
        cluster_csv = out_dir / "cluster_decision_point_classification_counts.csv"
        cluster_df.to_csv(cluster_csv, index=False, encoding="utf-8-sig")

    for cluster_id in sorted(metrics_df["Cluster"].unique()):
        df_cluster = metrics_df[metrics_df["Cluster"] == cluster_id]
        out_path = out_dir / f"cluster_{cluster_id}_siting_summary.png"
        _plot_cluster(df_cluster, cluster_id, out_path)

    print(f"Saved cluster siting figures to: {out_dir}")
    return out_dir


if __name__ == "__main__":
    main()
