from pathlib import Path
import argparse
import json

import numpy as np
import pandas as pd
import yaml

from validate_co2 import checksum, comparison, read_json, read_table


def validate_inventory(run, out):
    summary = read_json(run / "summary.json")
    parameters = read_json(run / "model_parameters.json")
    metadata = read_json(run / "inventory_cost_parameters.json")
    configuration = yaml.safe_load((run / "config.yaml").read_text(encoding="utf-8"))
    if metadata["applied_in_optimization"] is not True:
        raise ValueError("Inventory-hour correction was not applied in the optimization objective")
    periods, weeks = int(parameters["periods"]), int(parameters["weeks"])
    hours = float(parameters["hours_per_period"])
    represented_hours = periods * hours
    if represented_hours != weeks * 168:
        raise ValueError("Represented physical hours disagree with representative weeks")
    storage = configuration.get("objective_coefficients", {}).get("storage", {})
    direct = storage.get("direct_costs", {})
    rent = float(direct.get("warehouse_rent_per_m3_hour", 0.01))
    density = float(direct.get("storage_density_kg_per_m3", 500))
    handling = float(direct.get("handling_cost_per_kg_hour", 0.001))
    if density <= 0 or not np.isfinite([rent, density, handling]).all():
        raise ValueError("Invalid configured inventory holding-charge components")
    hourly_charge = rent / density + handling
    unified = configuration.get("unified_costs", {}).get("storage", {})
    unit_equipment_cost = {
        "saf": float(unified.get("mtj_equipment_cost_yuan_per_kg") or storage.get("equipment_unit_cost_yuan_per_kg", 10)),
        "h2": float(unified.get("hydrogen_equipment_cost_yuan_per_kg") or storage.get("hydrogen_equipment_unit_cost_yuan_per_kg", 20)),
    }
    economics = configuration["economic_parameters"]
    years, discount = int(economics["project_lifespan"]), float(economics["discount_rate"])
    lifecycle_factor = 52 / weeks * float(np.sum((1 + discount) ** -np.arange(1, years + 1)))
    source_types = {name: info["type"] for name, info in parameters["locations"].items()}
    rows, checks = [], {}
    input_files = ["summary.json", "model_parameters.json", "inventory_cost_parameters.json", "config.yaml"]
    for commodity, operation_field, equipment_field in [("saf", "storage_operation_cost", "storage_equipment_cost"), ("h2", "h2_storage_operation", "h2_storage_investment")]:
        filename = f"{commodity}_inventory.csv"
        input_files.append(filename)
        stocks = read_table(run / filename, ["location", "period"])
        if not stocks["period"].between(0, periods).all() or not stocks.groupby("location")["period"].agg(lambda series: set(series) == set(range(periods + 1))).all():
            raise ValueError(f"Incomplete saved inventory boundaries: {filename}")
        if not set(stocks["location"]).issubset(source_types):
            raise ValueError(f"Inventory has unknown node types: {filename}")
        peaks = stocks.groupby("location")["value"].max()
        charged = pd.Series(True, index=peaks.index)
        if commodity == "h2" and summary["scenario"].startswith("CCU-"):
            charged = peaks.index.map(source_types).isin(["solar_plant", "wind_farm", "byproduct_hydrogen_steel", "byproduct_hydrogen_refinery"])
        charged_peak = float(peaks[charged].sum())
        expected_operation = charged_peak / 2 * represented_hours * hourly_charge * lifecycle_factor
        expected_equipment = charged_peak * unit_equipment_cost[commodity]
        record = metadata["records"][commodity]
        checks[f"{commodity}.operation_cost_cny"] = comparison(float(summary["cost_breakdown"][operation_field]), expected_operation)
        checks[f"{commodity}.equipment_cost_cny"] = comparison(float(summary["cost_breakdown"][equipment_field]), expected_equipment)
        checks[f"{commodity}.hourly_charge_cny_per_kg_hour"] = comparison(float(record["operation_cny_per_kg_hour"]), hourly_charge, absolute=1e-12)
        checks[f"{commodity}.represented_hours"] = comparison(float(record["represented_hours"]), represented_hours, absolute=1e-12)
        checks[f"{commodity}.recorded_expression_cost_cny"] = comparison(float(record["final_expression_cost_cny"]), expected_operation)
        for location, peak in peaks.items():
            in_scope = bool(charged.loc[location]) if isinstance(charged, pd.Series) else bool(charged[peaks.index.get_loc(location)])
            rows.append({"commodity": commodity, "location": location, "type": source_types[location],
                         "saved_peak_inventory_kg": float(peak), "charged_location": in_scope,
                         "average_proxy_kg": float(peak) / 2 if in_scope else 0.0,
                         "represented_hours": represented_hours,
                         "independent_holding_cost_cny": float(peak) / 2 * represented_hours * hourly_charge * lifecycle_factor if in_scope else 0.0,
                         "independent_equipment_cost_cny": float(peak) * unit_equipment_cost[commodity] if in_scope else 0.0})
    report = {"scenario": summary["scenario"], "label": summary["label"], "run": str(run),
              "average_inventory_proxy": "Half the sum of charged site-specific saved peaks",
              "represented_hours": represented_hours, "holding_charge_cny_per_kg_hour": hourly_charge,
              "lifecycle_operation_factor": lifecycle_factor,
              "scope": "Independent saved-stock maxima and configured direct holding/equipment costs, with original location scopes and corrected physical hours. Costs are already in the optimized objective and are not added again.",
              "checks": checks, "passed": all(check["passed"] for check in checks.values()),
              "input_sha256": {name: checksum(run / name) for name in input_files}}
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out / "inventory_cost_site_reconciliation.csv", index=False)
    (out / "inventory_cost_validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = validate_inventory(args.run.resolve(), args.out.resolve())
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
