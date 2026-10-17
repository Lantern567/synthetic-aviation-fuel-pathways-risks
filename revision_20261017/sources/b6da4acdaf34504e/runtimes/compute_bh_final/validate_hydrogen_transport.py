from pathlib import Path
import argparse
import json

import numpy as np
import pandas as pd
import yaml

from validate_co2 import checksum, comparison, read_json, read_table


def validate_transport(run, out):
    summary = read_json(run / "summary.json")
    configuration = yaml.safe_load((run / "config.yaml").read_text(encoding="utf-8"))
    metadata = read_json(run / "hydrogen_transport_parameters.json")
    parameters = read_json(run / "model_parameters.json")
    weeks, periods = int(parameters["weeks"]), int(parameters["periods"])
    if periods % weeks:
        raise ValueError("Incomplete representative weeks")
    periods_per_week = periods // weeks
    flows = read_table(run / "h2_flows.csv", ["source", "destination", "period"])
    if not flows["period"].between(0, periods - 1).all():
        raise ValueError("Transport period outside represented horizon")
    route_table = pd.read_csv(run / "hydrogen_transport_accounting.csv")
    route_keys = ["source", "destination"]
    route_fields = ["weekly_contract_kg", "representative_window_transport_kg", "pipeline_distance_km", "transport_cny_per_kg"]
    if not set(route_keys + route_fields).issubset(route_table) or route_table.duplicated(route_keys).any():
        raise ValueError("Invalid route accounting identifiers")
    if not np.isfinite(route_table[route_fields].to_numpy(dtype=float)).all():
        raise ValueError("Nonfinite route accounting quantity")
    routes = route_table.set_index(route_keys)
    flow_index = pd.MultiIndex.from_frame(flows[route_keys])
    if not flow_index.isin(routes.index).all():
        raise ValueError("Actual flow has no declared route")
    flows["week"] = flows["period"] // periods_per_week
    expected_index = pd.MultiIndex.from_tuples([(*route, week) for route in routes.index for week in range(weeks)], names=["source", "destination", "week"])
    weekly_actual = flows.groupby(["source", "destination", "week"])["value"].sum().reindex(expected_index, fill_value=0.0)
    weekly = weekly_actual.rename("actual_kg").to_frame()
    weekly["contract_kg"] = np.repeat(routes["weekly_contract_kg"].to_numpy(), weeks)
    weekly["residual_kg"] = weekly["actual_kg"] - weekly["contract_kg"]
    actual_window = flows.groupby(route_keys)["value"].sum().reindex(routes.index, fill_value=0.0)
    routes["actual_window_kg"] = actual_window
    routes["window_export_error_kg"] = routes["representative_window_transport_kg"] - actual_window
    curve = np.array(configuration["costs"]["hydrogen_pipeline_costs"]["transport_cost_function"]["data_points"], dtype=float)
    if curve.ndim != 2 or curve.shape[1] != 2 or not (np.diff(curve[:, 0]) > 0).all():
        raise ValueError("Hydrogen cost curve must have increasing distance/coefficient pairs")
    distances = routes["pipeline_distance_km"].to_numpy(dtype=float)
    if (distances < 0).any():
        raise ValueError("Negative route distance")
    routes["independent_cny_per_kg"] = np.interp(distances, curve[:, 0], curve[:, 1]) * distances / 100
    routes["unit_cost_error_cny_per_kg"] = routes["transport_cny_per_kg"] - routes["independent_cny_per_kg"]
    economics = configuration["economic_parameters"]
    years, discount = int(economics["project_lifespan"]), float(economics["discount_rate"])
    lifecycle_factor = 52 / weeks * float(np.sum((1 + discount) ** -np.arange(1, years + 1)))
    cost = float((actual_window * routes["independent_cny_per_kg"]).sum() * lifecycle_factor)
    carbon_per_100km = float(configuration["carbon_emission_parameters"]["transportation"]["h2_pipeline_intensity"])
    carbon = float((actual_window * routes["pipeline_distance_km"] / 100 * carbon_per_100km).sum())
    if "carbon_kg_co2e_per_kg_100km" not in metadata:
        raise ValueError("Hydrogen transport metadata must explicitly declare kg CO2e/(kg H2 * 100 km)")
    max_contract = float(weekly["residual_kg"].abs().max()) if len(weekly) else 0.0
    max_window = float(routes["window_export_error_kg"].abs().max()) if len(routes) else 0.0
    max_unit = float(routes["unit_cost_error_cny_per_kg"].abs().max()) if len(routes) else 0.0
    checks = {
        "max_week_contract_error_kg": comparison(max_contract, 0.0, absolute=1e-3),
        "max_window_transport_export_error_kg": comparison(max_window, 0.0, absolute=1e-3),
        "max_route_unit_cost_error_cny_per_kg": comparison(max_unit, 0.0, absolute=1e-10),
        "pipeline_cost_cny": comparison(float(summary["cost_breakdown"]["hydrogen_pipeline_operation"]), cost),
        "pipeline_carbon_kg_co2e": comparison(float(summary["carbon_expressions"]["h2_pipeline_transport"]), carbon),
        "declared_carbon_coefficient": comparison(float(metadata["carbon_kg_co2e_per_kg_100km"]), carbon_per_100km, absolute=1e-12),
    }
    report = {"scenario": summary["scenario"], "label": summary["label"], "run": str(run),
              "weeks": weeks, "actual_representative_window_transport_kg": float(flows["value"].sum()),
              "carbon_coefficient_unit": "kg CO2e / (kg H2 * 100 km)",
              "distance_scope": "Exported pipeline routes used jointly for cost and emissions; independent route geometry reconstruction is outside this check.",
              "independent_transport_cost_cny": cost, "independent_transport_carbon_kg_co2e": carbon,
              "checks": checks, "passed": all(check["passed"] for check in checks.values())}
    filenames = ["config.yaml", "model_parameters.json", "summary.json", "h2_flows.csv", "hydrogen_transport_accounting.csv", "hydrogen_transport_parameters.json"]
    report["input_sha256"] = {name: checksum(run / name) for name in filenames}
    out.mkdir(parents=True, exist_ok=True)
    weekly.to_csv(out / "hydrogen_weekly_contract_checks.csv")
    routes.to_csv(out / "hydrogen_route_ledger_reconciliation.csv")
    (out / "hydrogen_transport_validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = validate_transport(args.run.resolve(), args.out.resolve())
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
