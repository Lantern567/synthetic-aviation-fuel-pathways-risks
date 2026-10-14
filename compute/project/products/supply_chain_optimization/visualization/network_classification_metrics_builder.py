"""
Recompute scenario network metrics from transport_summary CSVs and (optionally) cluster them.

Default output matches the existing network_classification_20260127_210416 results by:
- Using weekly flow column (周运输量(kg)) for weighting
- Cross-region share defined as distance > 100 km
- Key node concentration based on source (起点) outflow only
- Key route concentration based on top-3 aggregated routes
- Excluding pipeline nodes (type contains '管道' or 'pipeline') from node count and source flow

Usage:
  python3 network_classification_metrics_builder.py \
    --input /path/to/scenario_network_metrics.csv
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Tuple

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

DEFAULT_MANIFEST = PROJECT_ROOT / (
    "products/supply_chain_optimization/visualization/results/"
    "network_classification_20260127_210416/scenario_network_metrics.csv"
)

DEFAULT_RESULTS_DIR = PROJECT_ROOT / (
    "products/supply_chain_optimization/visualization/results"
)

PIPELINE_KEYWORDS = ("管道", "pipeline")


@dataclass
class MetricRow:
    scenario: str
    node_count: float
    key_node_share: float
    key_route_share: float
    avg_distance: float
    cross_region_share: float
    single_point_share: float
    transport_summary: str


def _is_pipeline_type(value: object) -> bool:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return False
    text = str(value).lower()
    return any(k in text for k in PIPELINE_KEYWORDS)


def _pick_flow_series(df: pd.DataFrame) -> pd.Series:
    """Pick a weekly flow series. Falls back to daily flow * 7 if needed."""
    candidates = [
        ("周运输量(kg)", 1.0),
        ("周运输量(m3)", 1.0),
        ("周运输量(m³)", 1.0),
        ("日运输量(kg)", 7.0),
        ("日运输量(m3)", 7.0),
        ("日运输量(m³)", 7.0),
    ]
    for col, factor in candidates:
        if col in df.columns:
            series = pd.to_numeric(df[col], errors="coerce")
            if series.notna().any():
                return series.fillna(0.0) * factor
    return pd.Series([0.0] * len(df))


def _node_count(df: pd.DataFrame) -> int:
    nodes = set()
    for name, ntype in zip(df.get("起点", []), df.get("起点类型", [])):
        if pd.isna(name) or _is_pipeline_type(ntype):
            continue
        nodes.add(str(name))
    for name, ntype in zip(df.get("终点", []), df.get("终点类型", [])):
        if pd.isna(name) or _is_pipeline_type(ntype):
            continue
        nodes.add(str(name))
    return len(nodes)


def _source_flow(df: pd.DataFrame, flow: pd.Series) -> List[float]:
    flows = {}
    for idx, row in df.iterrows():
        f = float(flow.iloc[idx])
        if f <= 0:
            continue
        if _is_pipeline_type(row.get("起点类型")):
            continue
        name = row.get("起点")
        if pd.isna(name):
            continue
        key = str(name)
        flows[key] = flows.get(key, 0.0) + f
    return sorted(flows.values(), reverse=True)


def _key_node_share(source_flows: List[float], total_flow: float) -> Tuple[float, float]:
    if total_flow <= 0 or not source_flows:
        return 0.0, 0.0
    k = max(1, int(np.ceil(0.1 * len(source_flows))))
    top10 = sum(source_flows[:k]) / total_flow * 100.0
    max_share = source_flows[0] / total_flow * 100.0
    return top10, max_share


def _key_route_share(df: pd.DataFrame, flow: pd.Series, total_flow: float) -> float:
    if total_flow <= 0:
        return 0.0
    df_route = df.copy()
    df_route["flow"] = flow
    group_cols = ["起点", "终点", "货物类型", "运输方式"]
    for col in group_cols:
        if col not in df_route.columns:
            df_route[col] = ""
    route_flow = (
        df_route.groupby(group_cols, dropna=False)["flow"].sum().sort_values(ascending=False)
    )
    return float(route_flow.head(3).sum() / total_flow * 100.0)


def _avg_distance(df: pd.DataFrame, flow: pd.Series, total_flow: float) -> float:
    if total_flow <= 0:
        return 0.0
    dist = pd.to_numeric(df.get("距离(km)"), errors="coerce").fillna(0.0)
    return float((dist * flow).sum() / total_flow)


def _cross_region_share(
    df: pd.DataFrame,
    flow: pd.Series,
    total_flow: float,
    distance_threshold_km: float,
) -> float:
    if total_flow <= 0:
        return 0.0
    dist = pd.to_numeric(df.get("距离(km)"), errors="coerce").fillna(0.0)
    return float(flow[dist > distance_threshold_km].sum() / total_flow * 100.0)


def _compute_metrics(transport_path: Path, distance_threshold_km: float) -> MetricRow:
    df = pd.read_csv(transport_path)
    flow = _pick_flow_series(df)
    total_flow = float(flow.sum())

    node_count = float(_node_count(df))
    source_flows = _source_flow(df, flow)
    key_node_share, single_point_share = _key_node_share(source_flows, total_flow)
    key_route_share = _key_route_share(df, flow, total_flow)
    avg_distance = _avg_distance(df, flow, total_flow)
    cross_region_share = _cross_region_share(df, flow, total_flow, distance_threshold_km)

    return MetricRow(
        scenario="",
        node_count=node_count,
        key_node_share=key_node_share,
        key_route_share=key_route_share,
        avg_distance=avg_distance,
        cross_region_share=cross_region_share,
        single_point_share=single_point_share,
        transport_summary=str(transport_path),
    )


def _scale_features(X: np.ndarray, scale: str) -> np.ndarray:
    if scale == "none":
        return X
    if scale == "minmax":
        mins = X.min(axis=0)
        maxs = X.max(axis=0)
        span = np.where((maxs - mins) == 0, 1.0, (maxs - mins))
        return (X - mins) / span
    if scale == "zscore":
        mean = X.mean(axis=0)
        std = X.std(axis=0, ddof=0)
        std = np.where(std == 0, 1.0, std)
        return (X - mean) / std
    raise ValueError(f"Unknown scale: {scale}")


def _kmeans(
    X: np.ndarray,
    k: int,
    seed: int,
    n_init: int,
    max_iter: int,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    best_labels = None
    best_inertia = None
    for _ in range(n_init):
        if k > len(X):
            raise ValueError("k cannot be larger than number of samples")
        init_idx = rng.choice(len(X), size=k, replace=False)
        centers = X[init_idx].copy()
        for _ in range(max_iter):
            dists = ((X[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
            labels = dists.argmin(axis=1)
            new_centers = np.array([
                X[labels == j].mean(axis=0) if np.any(labels == j) else centers[j]
                for j in range(k)
            ])
            if np.allclose(new_centers, centers):
                break
            centers = new_centers
        inertia = ((X - centers[labels]) ** 2).sum()
        if best_inertia is None or inertia < best_inertia:
            best_inertia = inertia
            best_labels = labels.copy()
    return best_labels


def _build_metrics_table(
    manifest: pd.DataFrame,
    distance_threshold_km: float,
) -> pd.DataFrame:
    rows: List[dict] = []
    for _, row in manifest.iterrows():
        scenario = row.get("Scenario", "")
        transport_summary = row.get("TransportSummary", "")
        if not isinstance(transport_summary, str) or not transport_summary:
            continue
        path = Path(transport_summary)
        if not path.exists():
            continue
        metrics = _compute_metrics(path, distance_threshold_km)
        metrics.scenario = str(scenario)
        rows.append({
            "Scenario": metrics.scenario,
            "节点数量": metrics.node_count,
            "关键节点集中度": metrics.key_node_share,
            "关键通道集中度": metrics.key_route_share,
            "平均运输距离": metrics.avg_distance,
            "跨区域物流比例": metrics.cross_region_share,
            "单点失效影响": metrics.single_point_share,
            "TransportSummary": metrics.transport_summary,
        })
    return pd.DataFrame(rows)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recompute network classification metrics.")
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="CSV containing Scenario and TransportSummary columns.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory. Default is results/network_classification_recomputed_<timestamp>.",
    )
    parser.add_argument(
        "--distance-threshold-km",
        type=float,
        default=100.0,
        help="Cross-region threshold (km). Default 100.",
    )
    parser.add_argument(
        "--cluster-k",
        type=int,
        default=4,
        help="Number of clusters for k-means. Use 0 to skip clustering.",
    )
    parser.add_argument(
        "--cluster-scale",
        type=str,
        choices=["none", "minmax", "zscore"],
        default="none",
        help="Feature scaling before clustering.",
    )
    parser.add_argument(
        "--cluster-seed",
        type=int,
        default=191,
        help="Random seed for k-means initialization.",
    )
    parser.add_argument(
        "--cluster-n-init",
        type=int,
        default=1,
        help="Number of k-means initializations.",
    )
    parser.add_argument(
        "--cluster-max-iter",
        type=int,
        default=300,
        help="Max iterations for k-means.",
    )
    return parser.parse_args()


def main() -> Path:
    args = _parse_args()
    manifest_path = args.input
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")
    manifest = pd.read_csv(manifest_path)
    if "Scenario" not in manifest.columns or "TransportSummary" not in manifest.columns:
        raise ValueError("Input CSV must include Scenario and TransportSummary columns.")

    metrics_df = _build_metrics_table(manifest, args.distance_threshold_km)
    if metrics_df.empty:
        raise ValueError("No metrics computed. Check TransportSummary paths.")

    if args.cluster_k and args.cluster_k > 0:
        features = metrics_df[[
            "节点数量",
            "关键节点集中度",
            "关键通道集中度",
            "平均运输距离",
            "跨区域物流比例",
            "单点失效影响",
        ]].values.astype(float)
        features = _scale_features(features, args.cluster_scale)
        labels = _kmeans(
            features,
            k=args.cluster_k,
            seed=args.cluster_seed,
            n_init=args.cluster_n_init,
            max_iter=args.cluster_max_iter,
        )
        metrics_df["Cluster"] = labels.astype(int)
    else:
        metrics_df["Cluster"] = -1

    # Match the precision/ordering used by the existing metrics CSV
    metric_cols = [
        "节点数量",
        "关键节点集中度",
        "关键通道集中度",
        "平均运输距离",
        "跨区域物流比例",
        "单点失效影响",
    ]
    metrics_df[metric_cols] = metrics_df[metric_cols].round(4)
    ordered_cols = [
        "Scenario",
        *metric_cols,
        "Cluster",
        "TransportSummary",
    ]
    metrics_df = metrics_df[ordered_cols]

    out_dir = args.output_dir
    if out_dir is None:
        out_dir = DEFAULT_RESULTS_DIR / f"network_classification_recomputed_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_csv = out_dir / "scenario_network_metrics.csv"
    metrics_df.to_csv(out_csv, index=False, encoding="utf-8-sig")

    print(f"Saved: {out_csv}")
    return out_csv


if __name__ == "__main__":
    main()
