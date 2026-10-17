from pathlib import Path
import argparse
import copy
import json
import os
import sys

HERE = Path(__file__).resolve().parent
os.environ["MPLCONFIGDIR"] = str(HERE / "mplconfig")
sys.path.insert(0, str(HERE / "source"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from build_inputs import BASELINES, digest, read_json, write_json
from temporal_robustness_space_visualization import TemporalRobustnessSpaceVisualizer as Robustness
from pareto_temporal_distribution_visualization import ParetoTemporalDistributionVisualizer as Distribution
from pareto_penalty_visualization import ParetoPenaltyVisualizer as Penalty
from pareto_penalty_driver_heatmap_visualization import ParetoPenaltyDriverHeatmapVisualizer as Fingerprint
from temporal_efficiency_visualization import TemporalEfficiencyVisualizer as Efficiency
from supplementary_panels import draw_overview, draw_weekly_comparison
from compose_figure3 import compose


SELECTED = ["GTL-BH", "GTL", "CCU-GH-FT"]


def verify_inputs(manifest):
    for name, meta in manifest["configurations"].items():
        for kind, artifact in meta["adapted_files"].items():
            if digest(Path(artifact["path"])) != artifact["sha256"]:
                raise ValueError(f"Adapted input changed: {name}/{kind}")
        for source, expected in meta["source_hashes"].items():
            if digest(Path(source)) != expected:
                raise ValueError(f"Real source changed since adaptation: {source}")


def configure_templates(manifest):
    names = list(manifest["configurations"])
    for cls, attribute in [(Robustness, "SCENARIOS"), (Distribution, "PARETO_SCENARIOS"), (Efficiency, "SCENARIOS")]:
        original = getattr(cls, attribute)
        selected = {name: copy.deepcopy(original[name]) for name in names}
        for name, config in selected.items():
            artifacts = manifest["configurations"][name]["adapted_files"]
            config["solution_pattern"] = artifacts["solution"]["path"]
            config["hourly_pattern"] = artifacts["hourly"]["path"]
            if "carbon_pattern" in config:
                config["carbon_pattern"] = artifacts["carbon"]["path"]
        setattr(cls, attribute, selected)


def verify_metrics(metrics, manifest):
    if set(metrics.Scenario) != set(manifest["configurations"]) or metrics.Scenario.duplicated().any():
        raise ValueError("Metric table differs from actual adapted configurations")
    mapping = {"SAFMean": ("mean_synaf_utilization", 100), "H2Mean": ("mean_hydrogen_utilization", 100),
               "WorstWeekRetention": ("worst_week_retention", 100),
               "ChronicPenaltyPct": ("mean_utilization_capacity_premium_pct", 1),
               "RobustnessPenaltyPct": ("additional_worst_week_capacity_premium_pct", 1),
               "TotalPenaltyPct": ("total_capacity_premium_pct", 1),
               "LowLoadEpisodes6h": ("low_load_episode_count_over_6h", 1),
               "LowLoadEpisodes12h": ("low_load_episode_count_over_12h", 1),
               "MeanLowRunHours": ("mean_low_load_run_hours", 1), "MaxLowRunHours": ("max_low_load_run_hours", 1),
               "RenewPowerMeanMW": ("renewable_mean_mw", 1), "RenewPowerCV": ("renewable_cv_pct", 1),
               "RenewZeroPct": ("renewable_zero_pct", 1), "RenewRampPct": ("renewable_within_week_ramp_pct", 1)}
    for row in metrics.to_dict("records"):
        reference = manifest["configurations"][row["Scenario"]]["independent_metrics"]
        for column, (key, scale) in mapping.items():
            expected = reference[key]
            if expected is None:
                if not pd.isna(row[column]):
                    raise ValueError(f"Inapplicable metric has a numeric value: {row['Scenario']}/{column}")
            elif not np.isclose(row[column], expected * scale, rtol=1e-7, atol=1e-5):
                raise ValueError(f"Template metric differs from independent period calculation: {row['Scenario']}/{column}: {row[column]} != {expected * scale}")
        for week, expected in enumerate(reference["weekly_synaf_utilization"], start=1):
            if not np.isclose(row[f"W{week}Mean"], expected * 100, rtol=1e-7, atol=1e-5):
                raise ValueError(f"Weekly utilization differs: {row['Scenario']}/W{week}")


def omission_tables(metrics):
    records = []
    for row in metrics.to_dict("records"):
        weekly = np.asarray([row[f"W{week}Mean"] / 100 for week in range(1, 5)])
        for omitted in range(4):
            retained = np.delete(weekly, omitted)
            mean, worst = float(retained.mean()), float(retained.min())
            if mean <= 0 or worst <= 0:
                raise ValueError("Week-omission metrics require positive actual utilization")
            records.append({"scenario": row["Scenario"], "omitted_week": omitted + 1,
                            "mean_utilization_pct": mean * 100, "mean_premium_pct": (1 / mean - 1) * 100,
                            "additional_premium_pct": (1 / worst - 1 / mean) * 100, "retention_pct": worst / mean * 100})
    frame = pd.DataFrame(records)
    columns = ["mean_utilization_pct", "mean_premium_pct", "additional_premium_pct", "retention_pct"]
    ranges = frame.groupby("scenario")[columns].agg(["min", "max"])
    ranges.columns = ["_".join(column) for column in ranges.columns]
    return frame, ranges.reset_index()


def render(inputs, output, metrics_only=False):
    manifest = read_json(inputs / "manifest.json")
    if not metrics_only and (manifest["full_thirteen_baselines"] is not True or set(manifest["configurations"]) != set(BASELINES)):
        raise ValueError("Figure rendering requires twelve new real baselines and the retained actual GTL record")
    verify_inputs(manifest)
    configure_templates(manifest)
    output.mkdir(parents=True, exist_ok=True)
    builder = Robustness(output_dir=output)
    metrics = builder.build_metric_table()
    verify_metrics(metrics, manifest)
    metrics["MeanSAFUtilization"] = metrics.SAFMean / 100
    metrics["MeanSynAFUtilization"] = metrics.SAFMean / 100
    metrics["MeanUtilizationCapacityPremiumPct"] = metrics.ChronicPenaltyPct
    metrics["AdditionalWorstWeekCapacityPremiumPct"] = metrics.RobustnessPenaltyPct
    metrics["CapacityPremiumClass"] = np.where(metrics.TotalPenaltyPct < 50, "Lower total premium",
                                                np.where(metrics.RobustnessPenaltyPct > metrics.ChronicPenaltyPct,
                                                         "Larger worst-week component", "Larger mean-utilization component"))
    metrics["DemandFulfillmentRatio"] = metrics.Scenario.map({name: meta["demand_fulfillment_ratio"] for name, meta in manifest["configurations"].items()})
    metrics["SourceKind"] = metrics.Scenario.map({name: meta["source_kind"] for name, meta in manifest["configurations"].items()})
    temporal_data = HERE / "temporal_data" if manifest["full_thirteen_baselines"] else output / "temporal_data"
    temporal_data.mkdir(exist_ok=True)
    metrics.to_csv(output / "temporal_robustness_metrics_latest.csv", index=False)
    metrics.to_csv(temporal_data / "all_pathway_temporal_metrics.csv", index=False)
    omissions, ranges = omission_tables(metrics)
    omissions.to_csv(temporal_data / "week_omission_metrics.csv", index=False)
    ranges.to_csv(temporal_data / "week_omission_ranges.csv", index=False)
    report = {"schema_version": 1, "full_thirteen_baselines": manifest["full_thirteen_baselines"],
              "independent_period_metrics_match": True, "input_manifest_sha256": digest(inputs / "manifest.json"),
              "selection_scope": "Three fixed reference configurations; selection does not assert a new Pareto frontier.",
              "within_week_ramps_and_low_load_episodes": True,
              "figure_script_sha256": {str(path.relative_to(HERE)): digest(path)
                                       for path in sorted(list(HERE.glob("*.py")) + list((HERE / "source").glob("*.py")))},
              "metric_output_sha256": {str(path): digest(path) for path in [output / "temporal_robustness_metrics_latest.csv",
                                                                           temporal_data / "all_pathway_temporal_metrics.csv",
                                                                           temporal_data / "week_omission_metrics.csv", temporal_data / "week_omission_ranges.csv"]},
              "all_configurations": json.loads(metrics.to_json(orient="records"))}
    if not metrics_only:
        distribution = Distribution(output_dir=output)
        distribution.selected_pareto = SELECTED.copy()
        distribution.load_selected_temporal_data()
        if set(distribution.data) != set(SELECTED):
            raise ValueError("Reference utilization distributions are incomplete")
        distribution.create_figure()
        distribution.export_summary()
        Penalty(output_dir=output).run()
        Fingerprint(output_dir=output).create_figure()
        efficiency = Efficiency(output_dir=str(output))
        efficiency.load_data()
        if set(efficiency.data) != set(BASELINES):
            raise ValueError("The thirteen configuration time series are incomplete")
        efficiency.plot_h2_saf_vertical_layout()
        draw_overview(metrics, output)
        draw_weekly_comparison(metrics, output, SELECTED)
        compose(output)
        report["figure_files"] = {path.name: {"bytes": path.stat().st_size, "sha256": digest(path)}
                                  for path in sorted(output.iterdir()) if path.is_file() and path.suffix in [".png", ".pdf", ".svg"]}
    verify_inputs(manifest)
    write_json(output / "temporal_verification.json", report)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, default=HERE / "inputs")
    parser.add_argument("--out", type=Path, default=HERE / "outputs")
    parser.add_argument("--metrics-only", action="store_true")
    args = parser.parse_args()
    report = render(args.inputs.resolve(), args.out.resolve(), args.metrics_only)
    print(json.dumps({"configurations": len(report["all_configurations"]), "full_thirteen_baselines": report["full_thirteen_baselines"],
                      "independent_period_metrics_match": report["independent_period_metrics_match"], "figures_rendered": not args.metrics_only}))


if __name__ == "__main__":
    main()
