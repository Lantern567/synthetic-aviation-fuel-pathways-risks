from pathlib import Path
import argparse
import hashlib
import json

import numpy as np
import pandas as pd
import yaml


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def checksum(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_table(path, keys):
    table = pd.read_csv(path, dtype={key: str for key in keys if key != "period"})
    required = [*keys, "value"]
    if not set(required).issubset(table.columns):
        raise ValueError(f"{path}: required columns {required}")
    if table[keys].isna().any().any() or table.duplicated(keys).any():
        raise ValueError(f"{path}: missing or duplicate identifiers")
    if "period" in keys:
        periods = pd.to_numeric(table["period"], errors="raise")
        if not np.equal(periods, np.floor(periods)).all():
            raise ValueError(f"{path}: noninteger period")
        table["period"] = periods.astype(int)
    table["value"] = pd.to_numeric(table["value"], errors="raise")
    if not np.isfinite(table["value"]).all():
        raise ValueError(f"{path}: nonfinite quantity")
    return table


def comparison(actual, expected, absolute=1e-3, relative=1e-8):
    error = float(actual - expected)
    tolerance = max(absolute, relative * abs(expected))
    return {"actual": float(actual), "expected": float(expected), "error": error,
            "tolerance": tolerance, "passed": abs(error) <= tolerance}


def coefficients(run):
    config = yaml.safe_load((run / "config.yaml").read_text(encoding="utf-8"))
    parameters = read_json(run / "model_parameters.json")
    economics = config["economic_parameters"]
    weeks = int(parameters.get("weeks", len(read_json(run / "summary.json")["weekly"])))
    if weeks <= 0:
        raise ValueError("weeks must be positive")
    years = int(economics["project_lifespan"])
    discount = float(economics["discount_rate"])
    present_value = float(np.sum((1.0 + discount) ** -np.arange(1, years + 1)))
    capture_price = float(config["dac_parameters"]["capture_cost_yuan_per_ton"]) / 1000
    equipment_factor = float(config["carbon_emission_parameters"]["raw_materials"]["dac_equipment_embodied"])
    energy_factor = float(parameters["dac_kwh_per_kg"])
    configured_energy = float(config["dac_parameters"]["energy_kwh_per_ton_co2"]) / 1000
    if capture_price <= 0 or equipment_factor <= 0 or energy_factor <= 0:
        raise ValueError("DAC capture, energy and equipment factors must be positive")
    if not np.isclose(energy_factor, configured_energy, rtol=1e-10, atol=1e-12):
        raise ValueError("DAC energy factor differs between configuration and exported parameters")
    return {"weeks": weeks, "discount_rate": discount, "years": years,
            "annualization_factor": 52.0 / weeks,
            "present_value_factor": present_value,
            "lifecycle_operation_factor": 52.0 / weeks * present_value,
            "capture_cny_per_kg": capture_price,
            "equipment_kg_co2e_per_kg": equipment_factor,
            "dac_kwh_per_kg": energy_factor,
            "grid_cny_per_kwh": float(config["cost_parameters"]["renewable_energy"]["grid_electricity_price_yuan_per_kwh"]),
            "pipeline_cost_configuration": config["unified_costs"]["co2_transport"]["pipeline"],
            "pipeline_kg_co2e_per_kg_100km": float(config["carbon_emission_parameters"]["transportation"]["co2_pipeline_intensity"]),
            "technologies": config["technologies"], "parameters": parameters}


def independent_consumption(run, factors):
    production = read_table(run / "saf_production.csv", ["location", "technology", "period"])
    ratios = {name: float(factors["technologies"][name]["co2_consumption_ratio"])
              for name in production["technology"].unique()}
    if not set(production["technology"]).issubset(ratios):
        raise ValueError("unknown production technology")
    production["co2_kg"] = production["value"] * production["technology"].map(ratios)
    return production


def legacy_audit(run, out):
    factors = coefficients(run)
    summary = read_json(run / "summary.json")
    production = independent_consumption(run, factors)
    equipment_capture = (float(summary["carbon_expressions"]["dac_equipment"])
                         / factors["equipment_kg_co2e_per_kg"])
    cost_capture = (float(summary["cost_breakdown"]["dac_capture_cost"])
                    / factors["capture_cny_per_kg"] / factors["lifecycle_operation_factor"])
    required = float(production["co2_kg"].sum())
    report = {"mode": "legacy_saved_ledger_diagnostic", "run": str(run),
              "scenario": summary["scenario"], "label": summary["label"],
              "fuel_kg_from_period_records": float(production["value"].sum()),
              "co2_required_kg_from_fuel_and_configuration": required,
              "capture_kg_inferred_from_equipment_carbon": equipment_capture,
              "capture_kg_inferred_from_discounted_capture_cost": cost_capture,
              "independent_ledger_agreement": comparison(cost_capture, equipment_capture),
              "required_to_capture_ratio": required / equipment_capture,
              "minimum_capture_shortfall_kg_at_zero_initial_stock": required - equipment_capture,
              "period_node_balance_verified": False,
              "scope": "Independent configuration coefficients and saved production, cost and equipment-carbon ledgers. Capture is inferred; missing legacy period capture/inventory/transport exports are not treated as verified.",
              "input_sha256": {name: checksum(run / name) for name in ["config.yaml", "model_parameters.json", "summary.json", "saf_production.csv"]}}
    report["passed"] = (report["independent_ledger_agreement"]["passed"]
                         and equipment_capture + 1e-3 >= required)
    out.mkdir(parents=True, exist_ok=True)
    (out / "legacy_co2_diagnostic.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def validate_run(run, out, mass_tolerance=1e-3):
    factors = coefficients(run)
    parameters = factors["parameters"]
    summary = read_json(run / "summary.json")
    periods = int(parameters["periods"])
    weeks = factors["weeks"]
    if periods <= 0 or periods % weeks:
        raise ValueError("periods must be positive and divisible by weeks")
    per_week = periods // weeks
    consumption_columns = pd.read_csv(run / "co2_consumption.csv", nrows=0).columns
    consumption_keys = ["location", "technology", "period"] if "technology" in consumption_columns else ["location", "period"]
    tables = {
        "capture": read_table(run / "dac_co2_supply.csv", ["location", "period"]),
        "flow": read_table(run / "co2_flows.csv", ["source", "destination", "period"]),
        "contract": read_table(run / "co2_weekly_contracts.csv", ["source", "destination"]),
        "inventory": read_table(run / "co2_inventory_vars.csv", ["location", "period"]),
        "consumption": read_table(run / "co2_consumption.csv", consumption_keys),
        "grid": read_table(run / "dac_grid_electricity_vars.csv", ["location", "period"]),
    }
    production = independent_consumption(run, factors)
    for name, table in tables.items():
        if "period" in table.columns:
            upper = periods if name == "inventory" else periods - 1
            if not table["period"].between(0, upper).all():
                raise ValueError(f"{name}: period outside reported horizon")
    nodes = sorted(set(tables["capture"]["location"]) | set(production["location"])
                   | set(tables["inventory"]["location"])
                   | set(tables["flow"]["source"]) | set(tables["flow"]["destination"]))
    expected_stocks = pd.MultiIndex.from_product([nodes, range(periods + 1)], names=["location", "period"])
    stock = tables["inventory"].set_index(["location", "period"])["value"]
    if len(stock) != len(expected_stocks) or not expected_stocks.isin(stock.index).all():
        raise ValueError("inventory must explicitly cover every CO2 node at boundaries 0..periods, including zero stocks")
    grid_index = pd.MultiIndex.from_product([nodes, range(periods)], names=["location", "period"])

    def node_period(table, node, quantity="value"):
        values = table.groupby([node, "period"])[quantity].sum()
        values.index = values.index.set_names(["location", "period"])
        return values.reindex(grid_index, fill_value=0.0)

    captured = node_period(tables["capture"], "location")
    consumed = node_period(production, "location", "co2_kg")
    consumed_export = node_period(tables["consumption"], "location")
    incoming = node_period(tables["flow"], "destination")
    outgoing = node_period(tables["flow"], "source")
    stock_matrix = stock.reindex(expected_stocks).to_numpy().reshape(len(nodes), periods + 1)
    stock_change = pd.Series(np.diff(stock_matrix, axis=1).ravel(), index=grid_index)
    balances = pd.DataFrame({"captured_kg": captured, "received_kg": incoming,
                             "sent_kg": outgoing, "consumed_kg": consumed,
                             "stock_change_kg": stock_change})
    balances["residual_kg"] = captured + incoming - outgoing - consumed - stock_change
    balances["week"] = balances.index.get_level_values("period") // per_week
    weekly = balances.groupby("week").sum()
    node_totals = balances.groupby("location").sum(numeric_only=True).drop(columns="week")
    source_week = balances.reset_index().groupby(["location", "week"])[["captured_kg", "sent_kg"]].sum()
    source_week["export_over_local_capture_kg"] = (source_week["sent_kg"] - source_week["captured_kg"]).clip(lower=0.0)

    flows = tables["flow"].copy()
    flows["week"] = flows["period"] // per_week
    contracts = tables["contract"].set_index(["source", "destination"])["value"]
    flow_routes = pd.MultiIndex.from_frame(flows[["source", "destination"]].drop_duplicates())
    if not flow_routes.isin(contracts.index).all():
        raise ValueError("period flow contains an undeclared weekly contract")
    route_weeks = pd.MultiIndex.from_tuples([(*route, week) for route in contracts.index for week in range(weeks)], names=["source", "destination", "week"])
    actual_flows = flows.groupby(["source", "destination", "week"])["value"].sum().reindex(route_weeks, fill_value=0.0)
    contract_values = np.repeat(contracts.to_numpy(), weeks)
    route_check = pd.DataFrame({"actual_kg": actual_flows, "weekly_contract_kg": contract_values})
    route_check["residual_kg"] = route_check["actual_kg"] - route_check["weekly_contract_kg"]
    transport_parameters = read_json(run / "co2_balance_parameters.json")
    route_parameters = pd.DataFrame(transport_parameters["routes"]).set_index(["source", "destination"])
    if not contracts.index.isin(route_parameters.index).all():
        raise ValueError("transport distance and unit-cost metadata is incomplete")
    flow_index = pd.MultiIndex.from_frame(flows[["source", "destination"]])
    flow_distances = flow_index.map(route_parameters["distance_km"]).to_numpy(dtype=float)
    flow_unit_costs = flow_index.map(route_parameters["transport_cny_per_kg"]).to_numpy(dtype=float)
    if not np.isfinite(flow_distances).all() or not np.isfinite(flow_unit_costs).all():
        raise ValueError("nonfinite transport parameters")
    pipeline_config = factors["pipeline_cost_configuration"]
    curve = np.array(pipeline_config["transport_cost_function"]["data_points"], dtype=float)
    if curve.ndim != 2 or curve.shape[1] != 2 or not (np.diff(curve[:, 0]) > 0).all():
        raise ValueError("pipeline cost curve must contain increasing distance/coefficient pairs")
    independent_unit_costs = np.interp(flow_distances, curve[:, 0], curve[:, 1]) * flow_distances / 100 / 1000
    transport_cost = float(np.sum(flows["value"].to_numpy() * independent_unit_costs)
                           * factors["lifecycle_operation_factor"])
    transport_carbon = float(np.sum(flows["value"].to_numpy() * flow_distances / 100)
                             * factors["pipeline_kg_co2e_per_kg_100km"])

    capture_grid = tables["capture"].set_index(["location", "period"])["value"]
    grid_values = tables["grid"].set_index(["location", "period"])["value"]
    if not capture_grid.index.equals(grid_values.index):
        if len(capture_grid) != len(grid_values) or not capture_grid.index.isin(grid_values.index).all():
            raise ValueError("DAC grid records must cover exactly the capture site-periods")
        grid_values = grid_values.reindex(capture_grid.index)
    electricity = pd.DataFrame({"capture_kg": capture_grid, "grid_kwh": grid_values})
    electricity["required_kwh"] = electricity["capture_kg"] * factors["dac_kwh_per_kg"]
    electricity["renewable_requirement_kwh"] = electricity["required_kwh"] - electricity["grid_kwh"]
    node_types = {name: info["type"] for name, info in parameters["locations"].items()}
    if not set(nodes).issubset(node_types):
        raise ValueError("node type metadata is incomplete")
    renewable = electricity.index.get_level_values("location").map(node_types).isin(["solar_plant", "wind_farm"])
    nonrenewable_error = electricity.loc[~renewable, "renewable_requirement_kwh"].abs().max()
    if np.isnan(nonrenewable_error):
        nonrenewable_error = 0.0
    max_grid_excess = max(0.0, float((-electricity["renewable_requirement_kwh"]).max()))

    total_capture = float(captured.sum())
    total_consumption = float(consumed.sum())
    global_residual = total_capture - total_consumption - float(stock_change.sum())
    expected_capture_cost = total_capture * factors["capture_cny_per_kg"] * factors["lifecycle_operation_factor"]
    cross_checks = {
        "capture_cost_cny": comparison(float(summary["cost_breakdown"]["dac_capture_cost"]), expected_capture_cost),
        "equipment_carbon_kg_co2e": comparison(float(summary["carbon_expressions"]["dac_equipment"]), total_capture * factors["equipment_kg_co2e_per_kg"]),
        "grid_cost_cny": comparison(float(summary["cost_breakdown"]["dac_grid_electricity_cost"]), float(grid_values.sum()) * factors["grid_cny_per_kwh"] * factors["lifecycle_operation_factor"]),
        "production_total_kg": comparison(float(summary["production_kg"]), float(production["value"].sum())),
        "co2_pipeline_transport_cost_cny": comparison(float(summary["cost_breakdown"]["co2_pipeline_transport_cost"]), transport_cost),
        "co2_pipeline_transport_carbon_kg": comparison(float(summary["carbon_expressions"]["co2_pipeline_transport"]), transport_carbon),
        "co2_pipeline_unit_cost_max_error_cny_per_kg": comparison(float(np.max(np.abs(flow_unit_costs - independent_unit_costs))) if len(flows) else 0.0, 0.0, absolute=1e-10),
        "co2_pipeline_carbon_factor": comparison(float(transport_parameters["pipeline_kg_co2e_per_kg_100km"]), factors["pipeline_kg_co2e_per_kg_100km"], absolute=1e-12),
    }
    minimum_material = min(float(table["value"].min()) for table in tables.values() if not table.empty)
    checks = {
        "max_node_period_balance_residual_kg": float(balances["residual_kg"].abs().max()),
        "max_node_horizon_balance_residual_kg": float(node_totals["residual_kg"].abs().max()),
        "max_week_global_balance_residual_kg": float(weekly["residual_kg"].abs().max()),
        "global_balance_residual_kg": global_residual,
        "max_weekly_contract_residual_kg": float(route_check["residual_kg"].abs().max()) if len(route_check) else 0.0,
        "max_exported_consumption_error_kg": float((consumed_export - consumed).abs().max()),
        "max_week_source_export_over_local_capture_kg": float(source_week["export_over_local_capture_kg"].max()),
        "max_initial_inventory_kg": float(np.abs(stock_matrix[:, 0]).max()),
        "minimum_material_kg": minimum_material,
        "max_dac_grid_excess_kwh": max_grid_excess,
        "max_nonrenewable_dac_energy_error_kwh": float(nonrenewable_error),
    }
    passed = all(abs(checks[name]) <= mass_tolerance for name in [
        "max_node_period_balance_residual_kg", "max_node_horizon_balance_residual_kg",
        "max_week_global_balance_residual_kg", "global_balance_residual_kg",
        "max_weekly_contract_residual_kg", "max_exported_consumption_error_kg",
        "max_week_source_export_over_local_capture_kg",
        "max_initial_inventory_kg"])
    passed = passed and minimum_material >= -mass_tolerance
    passed = passed and max_grid_excess <= 1e-3 and nonrenewable_error <= 1e-3
    passed = passed and all(check["passed"] for check in cross_checks.values())
    report = {"mode": "independent_period_node_co2_accounting", "scenario": summary["scenario"],
              "label": summary["label"], "run": str(run), "nodes": len(nodes), "periods": periods,
              "weeks": weeks, "period_hours": float(parameters["hours_per_period"]),
              "node_period_balances": len(balances), "transport_loss_fraction": 0.0,
              "initial_inventory_rule": "zero", "terminal_inventory_rule": "nonnegative, unrestricted",
              "captured_kg": total_capture, "consumed_kg": total_consumption,
              "initial_inventory_kg": float(stock_matrix[:, 0].sum()),
              "terminal_inventory_kg": float(stock_matrix[:, -1].sum()),
              "actual_period_transport_kg": float(flows["value"].sum()),
              "dac_required_electricity_kwh": float(electricity["required_kwh"].sum()),
              "dac_grid_electricity_kwh": float(grid_values.sum()),
              "dac_renewable_requirement_kwh": float(electricity["renewable_requirement_kwh"].sum()),
              "joint_renewable_budget_verified_here": False,
              "energy_scope": "Capture electricity requirement, grid-only DAC allocation bound, exact grid equality at nonrenewable nodes and grid cost. The independent shared renewable-energy budget must additionally pass validate_physics.py.",
              "coefficient_basis": {key: value for key, value in factors.items() if key not in ["parameters", "technologies"]},
              "checks": checks, "ledger_cross_checks": cross_checks,
              "mass_absolute_tolerance_kg": mass_tolerance, "passed": bool(passed)}
    filenames = ["config.yaml", "model_parameters.json", "summary.json", "saf_production.csv",
                 "dac_co2_supply.csv", "co2_flows.csv", "co2_weekly_contracts.csv",
                 "co2_inventory_vars.csv", "co2_consumption.csv", "dac_grid_electricity_vars.csv", "co2_balance_parameters.json"]
    report["input_sha256"] = {name: checksum(run / name) for name in filenames}
    out.mkdir(parents=True, exist_ok=True)
    balances.to_csv(out / "co2_node_period_balances.csv")
    weekly.to_csv(out / "co2_week_global_balances.csv")
    source_week.to_csv(out / "co2_source_week_direct_supply_checks.csv")
    node_totals.to_csv(out / "co2_node_horizon_balances.csv")
    route_check.to_csv(out / "co2_weekly_contract_checks.csv")
    electricity.to_csv(out / "dac_electricity_reconciliation.csv")
    (out / "co2_validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--legacy-ledger", action="store_true")
    parser.add_argument("--mass-tolerance", type=float, default=1e-3)
    args = parser.parse_args()
    if args.legacy_ledger:
        report = legacy_audit(args.run.resolve(), args.out.resolve())
    else:
        report = validate_run(args.run.resolve(), args.out.resolve(), args.mass_tolerance)
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
