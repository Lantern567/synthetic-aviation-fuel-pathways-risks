from pathlib import Path
import argparse
import json

import numpy as np
import pandas as pd
import yaml

from validate_co2 import checksum, comparison, read_json, read_table, validate_run as validate_co2_run
from validate_hydrogen_transport import validate_transport


def maximum(values):
    values = np.asarray(values, dtype=float)
    return float(np.max(np.abs(values))) if values.size else 0.0


def validate(scenario, label, base):
    if scenario not in ("DAC-BH-FT", "DAC-BH-MTJ"):
        raise ValueError("This validator accepts DAC-BH-FT and DAC-BH-MTJ only")
    run = base / "verified_runs" / scenario / label
    inputs = base / "inputs" / ("baseline" if label == "baseline" else "summer")
    if (run / "EXPORT_IN_PROGRESS").exists():
        raise ValueError(f"Run export is incomplete: {run}")
    parameters = read_json(run / "model_parameters.json")
    summary = read_json(run / "summary.json")
    configuration = yaml.safe_load((run / "config.yaml").read_text(encoding="utf-8"))
    accounting = read_json(run / "byproduct_accounting_parameters.json")
    periods, weeks = int(parameters["periods"]), int(parameters["weeks"])
    hours = float(parameters["hours_per_period"])
    if hours != 3 or periods != weeks * 56:
        raise ValueError("Expected complete three-hour representative weeks")
    per_week = periods // weeks
    tables = {
        "h2": read_table(run / "h2_production.csv", ["location", "period"]),
        "h2_stock": read_table(run / "h2_inventory.csv", ["location", "period"]),
        "h2_flow": read_table(run / "h2_flows.csv", ["source", "destination", "period"]),
        "h2_capacity": read_table(run / "h2_capacity.csv", ["location"]),
        "h2_build": read_table(run / "h2_build.csv", ["location"]),
        "fuel": read_table(run / "saf_production.csv", ["location", "technology", "period"]),
        "fuel_stock": read_table(run / "saf_inventory.csv", ["location", "period"]),
        "fuel_capacity": read_table(run / "saf_capacity.csv", ["location", "technology"]),
        "fuel_build": read_table(run / "saf_build.csv", ["location", "technology"]),
        "deliveries": read_table(run / "deliveries.csv", ["location", "airport", "week"]),
        "shortages": read_table(run / "shortages.csv", ["airport", "week"]),
    }
    for name, table in tables.items():
        if "period" in table:
            upper = periods if name.endswith("stock") else periods - 1
            if not table["period"].between(0, upper).all():
                raise ValueError(f"{name}: period outside the represented horizon")
        if "week" in table:
            numeric = pd.to_numeric(table["week"], errors="raise")
            if not np.equal(numeric, np.floor(numeric)).all() or not numeric.between(0, weeks - 1).all():
                raise ValueError(f"{name}: invalid model week")
            table["week"] = numeric.astype(int)
    source_input = pd.read_csv(inputs / "byproduct_hydrogen_periods.csv")
    required_source = ["plant_name", "period", "type", "h2_available_kg_per_hour"]
    if not set(required_source).issubset(source_input):
        raise ValueError(f"Missing source input columns: {required_source}")
    if source_input.duplicated(["plant_name", "period"]).any():
        raise ValueError("Duplicate source input periods")
    source_input = source_input.rename(columns={"plant_name": "location"})
    source_index = pd.MultiIndex.from_product([sorted(source_input["location"].unique()), range(periods)], names=["location", "period"])
    source_input = source_input.set_index(["location", "period"])
    if len(source_input) != len(source_index) or not source_index.isin(source_input.index).all():
        raise ValueError("Source inputs must include all candidate source-periods")
    source_input = source_input.reindex(source_index)
    if not source_input["type"].isin(["byproduct_hydrogen_steel", "byproduct_hydrogen_refinery"]).all():
        raise ValueError("A hydrogen source has an unexpected physical type")
    rate = pd.to_numeric(source_input["h2_available_kg_per_hour"], errors="raise")
    if not np.isfinite(rate).all() or (rate < 0).any():
        raise ValueError("Invalid source hourly hydrogen availability")
    available = rate * hours
    model_available = pd.read_csv(run / "byproduct_hydrogen_availability.csv").set_index(["location", "period"])
    if not model_available.index.is_unique or len(model_available) != len(source_index) or not source_index.isin(model_available.index).all():
        raise ValueError("Exported source availability has incomplete identifiers")
    availability_export_error = maximum(model_available["available_h2_kg"].reindex(source_index) - available)
    h2 = tables["h2"].set_index(["location", "period"])["value"]
    if len(h2) != len(source_index) or not source_index.isin(h2.index).all():
        raise ValueError("Hydrogen production must explicitly cover all candidate source-periods")
    source_excess = max(0.0, float((h2.reindex(source_index) - available).max()))
    technology_ratios = {name: float(configuration["technologies"][name]["h2_consumption_ratio"])
                         for name in tables["fuel"]["technology"].unique()}
    tables["fuel"]["h2_consumed_kg"] = tables["fuel"]["value"] * tables["fuel"]["technology"].map(technology_ratios)

    def reconstruct_stock(stock_table, additions, removals):
        stock = stock_table.set_index(["location", "period"])["value"]
        nodes = sorted(set(stock_table["location"]) | set(additions.index.get_level_values(0)) | set(removals.index.get_level_values(0)))
        boundaries = pd.MultiIndex.from_product([nodes, range(periods + 1)], names=["location", "period"])
        index = pd.MultiIndex.from_product([nodes, range(periods)], names=["location", "period"])
        if len(stock) != len(boundaries) or not boundaries.isin(stock.index).all():
            raise ValueError("Incomplete inventory boundaries for independently reconstructed balance")
        matrix = stock.reindex(boundaries).to_numpy().reshape(len(nodes), periods + 1)
        result = pd.DataFrame(index=index)
        result["addition_kg"] = additions.reindex(index, fill_value=0.0)
        result["removal_kg"] = removals.reindex(index, fill_value=0.0)
        result["stock_change_kg"] = np.diff(matrix, axis=1).ravel()
        result["residual_kg"] = result["addition_kg"] - result["removal_kg"] - result["stock_change_kg"]
        return result, matrix

    h2_in = tables["h2_flow"].groupby(["destination", "period"])["value"].sum()
    h2_out = tables["h2_flow"].groupby(["source", "period"])["value"].sum()
    h2_use = tables["fuel"].groupby(["location", "period"])["h2_consumed_kg"].sum()
    h2_in.index = h2_in.index.set_names(["location", "period"])
    h2_out.index = h2_out.index.set_names(["location", "period"])
    h2_balance, h2_matrix = reconstruct_stock(tables["h2_stock"], h2.add(h2_in, fill_value=0.0), h2_use.add(h2_out, fill_value=0.0))
    h2_capacity = tables["h2_capacity"].set_index("location")["value"]
    h2_build = tables["h2_build"].set_index("location")["value"]
    if set(h2_capacity.index) != set(h2_build.index) or not set(h2.index.get_level_values("location")).issubset(h2_capacity.index):
        raise ValueError("Missing hydrogen conditioning capacity")
    h2_capacity_excess = max(0.0, float((h2 - h2.index.get_level_values("location").map(h2_capacity).to_numpy() * hours).max()))
    build_excess = max(0.0, float((h2_capacity - h2_build.reindex(h2_capacity.index) * configuration["capacity_limits"]["electrolyzer_max_capacity_kg_per_hour"]).max()))
    flows = tables["h2_flow"].copy()
    flows["week"] = flows["period"] // per_week
    routes = list(flows[["source", "destination"]].drop_duplicates().itertuples(index=False, name=None))
    route_week_index = pd.MultiIndex.from_tuples([(*route, week) for route in routes for week in range(weeks)], names=["source", "destination", "week"])
    weekly_flow = flows.groupby(["source", "destination", "week"])["value"].sum().reindex(route_week_index, fill_value=0.0)
    weekly_matrix = weekly_flow.unstack("week")
    weekly_uniform_error = maximum(weekly_matrix.max(axis=1) - weekly_matrix.min(axis=1))
    # 对应现有 CorrectedModelMixin 的明确配置默认值，单位是 kg/day。
    daily_h2_route_limit = float(configuration["capacity_limits"].get("hydrogen_pipeline_max_daily_capacity_kg", 50000))
    flow_limit = daily_h2_route_limit * hours / 24
    flow_excess = max(0.0, float(flows["value"].max()) - flow_limit) if len(flows) else 0.0

    fuel = tables["fuel"].groupby(["location", "period"])["value"].sum()
    shipments = tables["deliveries"].groupby(["location", "week"])["value"].sum().reset_index()
    shipments["period"] = (shipments["week"] + 1) * per_week - 1
    dispatched = shipments.set_index(["location", "period"])["value"]
    fuel_balance, fuel_matrix = reconstruct_stock(tables["fuel_stock"], fuel, dispatched)
    fuel_capacity = tables["fuel_capacity"].set_index(["location", "technology"])["value"]
    fuel_dispatch = tables["fuel"].set_index(["location", "technology", "period"])["value"]
    mapped_capacity = fuel_dispatch.index.droplevel("period").map(fuel_capacity).to_numpy(dtype=float)
    if not np.isfinite(mapped_capacity).all():
        raise ValueError("Missing fuel synthesis capacity")
    fuel_capacity_excess = max(0.0, float((fuel_dispatch.to_numpy() - mapped_capacity * hours).max()))
    fuel_build = tables["fuel_build"].set_index(["location", "technology"])["value"]
    if set(fuel_capacity.index) != set(fuel_build.index):
        raise ValueError("Fuel capacity and build identifiers differ")
    fuel_build_excess = max(0.0, float((fuel_capacity - fuel_build.reindex(fuel_capacity.index) * configuration["capacity_limits"]["saf_reactor_max_capacity_kg_per_hour"]).max()))
    demand_table = pd.read_csv(inputs / "airport_input.csv")
    demand_table["week"] = demand_table["week_number"].astype(int) - 1
    demand = demand_table.groupby(["departure_airport_name", "week"])["weekly_total_fuel_kg_total"].sum()
    demand.index = demand.index.set_names(["airport", "week"])
    shortages = tables["shortages"].set_index(["airport", "week"])["value"]
    delivered = tables["deliveries"].groupby(["airport", "week"])["value"].sum()
    if len(shortages) != len(demand) or not demand.index.isin(shortages.index).all():
        raise ValueError("Each airport-week must have an explicit shortage value")
    if not delivered.index.isin(demand.index).all():
        raise ValueError("Deliveries reference an unknown airport-week")
    demand_check = pd.DataFrame({"demand_kg": demand, "delivered_kg": delivered.reindex(demand.index, fill_value=0.0), "shortage_kg": shortages.reindex(demand.index)})
    demand_check["residual_kg"] = demand_check["delivered_kg"] + demand_check["shortage_kg"] - demand_check["demand_kg"]

    rate_discount = float(configuration["economic_parameters"]["discount_rate"])
    years = int(configuration["economic_parameters"]["project_lifespan"])
    factor = 52 / weeks * float(np.sum((1 + rate_discount) ** -np.arange(1, years + 1)))
    total_h2, total_fuel = float(h2.sum()), float(fuel.sum())
    active_h2_energy = float(accounting["hydrogen_ledger_energy_kwh_per_kg"])
    active_h2_price_mwh = float(accounting["hydrogen_ledger_electricity_cny_per_mwh"])
    active_internal_cost = float(accounting["hydrogen_internal_cny_per_kg"])
    configured_energy = float(configuration["green_hydrogen_supply"]["production_energy_kwh_per_kg"])
    configured_internal_cost = float(configuration.get("unified_costs", {}).get("production", {}).get("hydrogen_internal_cost_yuan_per_kg", 0))
    parameter_consistency = {"h2_energy_kwh_per_kg": comparison(active_h2_energy, configured_energy, absolute=1e-10),
                             "hydrogen_internal_cny_per_kg": comparison(active_internal_cost, configured_internal_cost, absolute=1e-10),
                             "conditioning_electricity_cny_per_kwh": comparison(active_h2_price_mwh / 1000, float(configuration["cost_parameters"]["renewable_energy"]["grid_electricity_price_yuan_per_kwh"]), absolute=1e-10)}
    source_types = {name: info["type"] for name, info in parameters["locations"].items()}
    synthesis_energy = tables["fuel"]["technology"].map({name: float(configuration["technologies"][name]["energy_consumption_kwh_per_kg_saf"]) for name in technology_ratios})
    mode = accounting["accounting_mode"]
    if mode != "component_cost" or accounting["feedstock_charge_scope"] != "no_separate_feedstock_charge":
        raise ValueError("Expected component-cost accounting with no separate feedstock charge")
    synthesis_prices = tables["fuel"]["location"].map({name: float(configuration["cost_parameters"]["renewable_energy"]["grid_electricity_price_yuan_per_kwh"]) for name in source_types})
    if synthesis_prices.isna().any():
        raise ValueError("Incomplete declared synthesis-electricity prices")
    synthesis_cost = float((tables["fuel"]["value"] * synthesis_energy * synthesis_prices).sum())
    expected_electricity = (total_h2 * active_h2_energy / 1000 * active_h2_price_mwh + synthesis_cost) * factor
    capex_coefficients = h2_capacity.index.map(accounting["source_equipment_capex_cny_per_kg_h"]).to_numpy(dtype=float)
    if not np.isfinite(capex_coefficients).all():
        raise ValueError("Missing hydrogen source equipment-capital coefficient")
    expected_capex = float(np.sum(h2_capacity.to_numpy() * capex_coefficients) * configuration["economic_parameters"]["capacity_factors"]["electrolyzer_capacity_factor"])
    expected_h2_cost = total_h2 * configured_internal_cost * factor
    costs = summary["cost_breakdown"]
    investment_names = ["facility_investment_cost", "storage_equipment_cost", "electrolyzer_investment_cost", "h2_storage_investment", "methanol_storage_equipment_cost", "dac_facility_investment"]
    operating_names = ["facility_operation_cost", "production_cost", "transport_operation_cost", "storage_operation_cost", "hydrogen_production_cost", "electricity_cost", "catalyst_cost", "h2_storage_operation", "hydrogen_transport_operation", "hydrogen_pipeline_operation", "dac_capture_cost", "dac_grid_electricity_cost", "co2_pipeline_transport_cost", "methanol_production_cost", "methanol_storage_operation_cost", "final_inventory_cost"]
    cost_checks = {"hydrogen_internal_cost_cny": comparison(float(costs["hydrogen_production_cost"]), expected_h2_cost),
                   "combined_hydrogen_and_synthesis_electricity_cny": comparison(float(costs["electricity_cost"]), expected_electricity),
                   "source_equipment_investment_cny": comparison(float(costs["electrolyzer_investment_cost"]), expected_capex),
                   "investment_component_sum_cny": comparison(float(costs["total_investment_cost"]), sum(float(costs[name]) for name in investment_names)),
                   "operating_component_sum_cny": comparison(float(costs["total_operation_cost"]), sum(float(costs[name]) for name in operating_names)),
                   "total_cost_excluding_shortage_cny": comparison(float(costs["total_cost_excluding_shortage"]), float(costs["total_investment_cost"]) + float(costs["total_operation_cost"])),
                   "reported_unit_cost_cny_per_kg": comparison(float(summary["cost_per_kg_excluding_shortage"]), float(costs["total_cost_excluding_shortage"]) / (total_fuel * factor))}
    grid_carbon = float(configuration["carbon_emission_parameters"]["renewable_energy"]["grid_electricity_intensity"])
    upstream_by_type = {"byproduct_hydrogen_steel": float(configuration["green_hydrogen_supply"]["steel_upstream_carbon_intensity"]),
                        "byproduct_hydrogen_refinery": float(configuration["green_hydrogen_supply"]["refinery_upstream_carbon_intensity"])}
    upstream_factors = h2.index.get_level_values("location").map(source_types).map(upstream_by_type).to_numpy(dtype=float)
    if not np.isfinite(upstream_factors).all():
        raise ValueError("Missing source-specific upstream hydrogen carbon coefficient")
    expected_h2_carbon = float(np.sum(h2.to_numpy() * (upstream_factors + configured_energy * grid_carbon)))
    expected_synthesis_carbon = float((tables["fuel"]["value"] * synthesis_energy).sum() * grid_carbon)
    carbon_checks = {"hydrogen_upstream_and_conditioning_kg_co2e": comparison(float(summary["carbon_expressions"]["h2_production"]), expected_h2_carbon),
                     "fuel_synthesis_grid_energy_kg_co2e": comparison(float(summary["carbon_expressions"]["saf_synthesis_energy"]), expected_synthesis_carbon),
                     "conditioning_electricity_kwh": comparison(float(accounting["conditioning_electricity_kwh"]), total_h2 * configured_energy),
                     "source_synthesis_electricity_kwh": comparison(float(accounting["source_synthesis_electricity_kwh"]), float((tables["fuel"]["value"] * synthesis_energy)[tables["fuel"]["location"].isin(source_input.index.get_level_values("location"))].sum()))}
    checks = {"max_availability_export_error_kg": availability_export_error,
              "max_h2_source_supply_excess_kg": source_excess,
              "max_h2_node_period_balance_error_kg": maximum(h2_balance["residual_kg"]),
              "h2_global_balance_error_kg": total_h2 - float(tables["fuel"]["h2_consumed_kg"].sum()) - float(h2_matrix[:, -1].sum() - h2_matrix[:, 0].sum()),
              "max_h2_initial_inventory_kg": maximum(h2_matrix[:, 0]),
              "max_h2_conditioning_capacity_excess_kg": h2_capacity_excess,
              "max_h2_build_capacity_excess_kg_per_hour": build_excess,
              "max_h2_period_route_capacity_excess_kg": flow_excess,
              "max_h2_week_contract_difference_kg": weekly_uniform_error,
              "max_fuel_node_period_balance_error_kg": maximum(fuel_balance["residual_kg"]),
              "max_fuel_initial_inventory_kg": maximum(fuel_matrix[:, 0]),
              "max_fuel_capacity_excess_kg": fuel_capacity_excess,
              "max_fuel_build_capacity_excess_kg_per_hour": fuel_build_excess,
              "max_airport_week_demand_balance_error_kg": maximum(demand_check["residual_kg"]),
              "minimum_material_kg": min(float(table["value"].min()) for table in tables.values() if len(table))}
    physics_passed = all(abs(value) <= 1e-3 for name, value in checks.items() if name != "minimum_material_kg") and checks["minimum_material_kg"] >= -1e-5
    summary_checks = {"production_kg": comparison(float(summary["production_kg"]), total_fuel),
                      "demand_kg": comparison(float(summary["demand_kg"]), float(demand.sum())),
                      "shortage_kg": comparison(float(summary["shortage_kg"]), float(shortages.sum())),
                      "demand_fulfillment_ratio": comparison(float(summary["demand_fulfillment_ratio"]), 1 - float(shortages.sum()) / float(demand.sum()), absolute=1e-10)}
    co2_report = validate_co2_run(run, run / "independent_co2")
    hydrogen_transport_report = validate_transport(run, run / "independent_hydrogen_transport")
    report = {"scenario": scenario, "label": label, "run": str(run), "independent_source_input": str(inputs / "byproduct_hydrogen_periods.csv"),
              "periods": periods, "weeks": weeks, "hours_per_period": hours, "source_candidates": len(source_input.index.get_level_values("location").unique()),
              "source_input_unit": "kg hydrogen per hour; multiplied by three hours for each period",
              "hydrogen_route_limit_kg_per_day": daily_h2_route_limit,
              "checks": checks, "summary_checks": summary_checks, "cost_ledger_checks": cost_checks,
              "source_carbon_checks": carbon_checks,
              "accounting_mode": mode, "configuration_consistency": parameter_consistency,
              "physics_passed": bool(physics_passed), "co2_validation_passed": co2_report["passed"],
              "hydrogen_transport_validation_passed": hydrogen_transport_report["passed"],
              "cost_ledger_recalculation_passed": all(check["passed"] for check in cost_checks.values()),
              "configured_component_costs_used": all(check["passed"] for check in parameter_consistency.values()),
              "h2_upstream_carbon_validated_here": all(check["passed"] for check in carbon_checks.values()),
              "cost_scope": "Component-cost accounting of selected conditioning equipment, grid energy and any explicitly configured internal charge; no separate hydrogen feedstock price is added. Source-specific upstream allocation is checked numerically; its external validity is outside this check.",
              "source_supply_provenance_scope": "Checks the full archived candidate input profile and its period expansion; raw industrial production observations are outside these supplied inputs."}
    report["passed"] = (report["physics_passed"] and report["co2_validation_passed"] and report["hydrogen_transport_validation_passed"]
                         and report["cost_ledger_recalculation_passed"] and report["configured_component_costs_used"]
                         and report["h2_upstream_carbon_validated_here"]
                         and all(check["passed"] for check in summary_checks.values()))
    tracked = [run / name for name in ["config.yaml", "model_parameters.json", "summary.json", "byproduct_accounting_parameters.json", "byproduct_hydrogen_availability.csv",
               "h2_production.csv", "h2_inventory.csv", "h2_flows.csv", "h2_capacity.csv", "h2_build.csv", "saf_production.csv", "saf_inventory.csv", "saf_capacity.csv", "saf_build.csv", "deliveries.csv", "shortages.csv"]]
    tracked.extend([inputs / "airport_input.csv", inputs / "byproduct_hydrogen_periods.csv"])
    report["input_sha256"] = {str(path): checksum(path) for path in tracked}
    h2_balance.to_csv(run / "physical_byproduct_hydrogen_balance.csv")
    fuel_balance.to_csv(run / "physical_byproduct_fuel_balance.csv")
    demand_check.to_csv(run / "physical_byproduct_airport_demand.csv")
    weekly_flow.to_csv(run / "physical_byproduct_weekly_h2_transport.csv")
    (run / "byproduct_physical_validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario")
    parser.add_argument("label", choices=["baseline", "summer_fixed"])
    parser.add_argument("--base", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    report = validate(args.scenario, args.label, args.base.resolve())
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
