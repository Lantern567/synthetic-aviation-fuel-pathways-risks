from pathlib import Path
import argparse
import hashlib
import json

import numpy as np
import pandas as pd
import yaml


PAIRED = ["CCU-GH-FT", "CCU-GH-MTJ", "DAC-GH-FT", "DAC-GH-MTJ", "GTL-GH", "CTL"]
BASELINE_ONLY = ["DAC-BH-FT", "DAC-BH-MTJ", "CCU-BH-FT", "CCU-BH-MTJ", "CTL-BH", "GTL-BH"]
CASES = [(scenario, label) for scenario in PAIRED for label in ["baseline", "summer_fixed"]] + [(scenario, "baseline") for scenario in BASELINE_ONLY]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def scalar_items(record, prefix=""):
    result = {}
    for key, value in record.items():
        name = f"{prefix}{key}"
        if isinstance(value, dict):
            result.update(scalar_items(value, name + "."))
        elif isinstance(value, (str, int, float, bool)) or value is None:
            result[name] = value
    return result


def collect(results, output, accounts_root=None, selected=None):
    cases = selected or CASES
    if any(case not in CASES for case in cases) or len(cases) != len(set(cases)):
        raise ValueError("Unknown or duplicate requested case")
    missing = [str(results / scenario / label / "summary.json") for scenario, label in cases if not (results / scenario / label / "summary.json").is_file()]
    if missing:
        raise FileNotFoundError("Missing real run summaries:\n" + "\n".join(missing))
    tracked, summary_rows, weekly_rows = [], [], []
    costs, carbon, certificates, physics_rows, co2_rows, hydrogen_rows, inventory_rows, account_rows = [], [], [], [], [], [], [], []
    directories, summaries = {}, {}

    def track(path, scenario, label, role):
        tracked.append({"scenario": scenario, "label": label, "role": role, "path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": digest(path)})

    def validation(path, scenario, label, summary_hash):
        report = read_json(path)
        if report.get("passed") is not True:
            raise ValueError(f"Validation has not passed: {path}")
        hashes = report.get("input_sha256", {})
        summary_hashes = [value for name, value in hashes.items() if name == "summary.json" or name.endswith("/summary.json") or name.endswith("\\summary.json")]
        if report.get("solution_summary_sha256") != summary_hash and summary_hashes != [summary_hash]:
            raise ValueError(f"Validation does not identify current summary bytes: {path}")
        track(path, scenario, label, "independent_validation")
        return {"scenario": scenario, "label": label, "summary_sha256": summary_hash, **scalar_items(report)}

    for scenario, label in cases:
        directory = results / scenario / label
        directories[scenario, label] = directory
        if (directory / "EXPORT_IN_PROGRESS").exists():
            raise ValueError(f"Export is incomplete: {directory}")
        summary_path = directory / "summary.json"
        summary = read_json(summary_path)
        summaries[scenario, label] = summary
        if (summary["scenario"], summary["label"]) != (scenario, label):
            raise ValueError(f"Scenario mismatch: {directory}")
        if summary["has_solution"] is not True or summary["algebraic_validation"]["passed"] is not True:
            raise ValueError(f"No accepted feasible result: {directory}")
        if not -1e-10 <= float(summary["gap"]) <= 0.01:
            raise ValueError(f"Objective certificate exceeds one percent: {directory}")
        summary_hash = digest(summary_path)
        config_path = directory / "config.yaml"
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        parameters_path = directory / "model_parameters.json"
        parameters = read_json(parameters_path)
        periods, weeks, hours = int(parameters["periods"]), int(parameters["weeks"]), float(parameters["hours_per_period"])
        if periods % weeks or periods * hours != weeks * 168:
            raise ValueError("Inconsistent model time units")
        fields = ["production_kg", "demand_kg", "shortage_kg", "demand_fulfillment_ratio", "cost_per_kg_excluding_shortage", "saf_capacity_kg_h", "h2_capacity_kg_h", "mean_utilization", "worst_week_retention", "objective", "lower_bound", "gap", "seconds"]
        row = {"scenario": scenario, "label": label, **{name: summary[name] for name in fields}}
        row["raw_total_emissions_kg"] = summary["carbon_aggregates"]["total_emissions"]
        row["raw_carbon_intensity_g_mj"] = float(row["raw_total_emissions_kg"]) / float(summary["production_kg"]) / float(config["carbon_emission_parameters"]["benchmarks"]["saf_energy_content"]) * 1000
        row.update(source_summary_sha256=summary_hash, source_directory=str(directory), accounting_stage="raw_solver_ledger")
        row.update(periods=periods, weeks=weeks, hours_per_period=hours,
                   model_scope_json=json.dumps(summary["model_scope"], ensure_ascii=False))
        summary_rows.append(row)
        production_path = directory / "saf_production.csv"
        production = pd.read_csv(production_path)
        production["week"] = production["period"] // (periods // weeks)
        actual_weekly = production.groupby("week")["value"].sum()
        if {record["week"] for record in summary["weekly"]} != set(range(weeks)):
            raise ValueError("Summary has incomplete weekly output")
        for record in summary["weekly"]:
            if not np.isclose(record["production_kg"], actual_weekly.get(record["week"], 0.0), rtol=1e-10, atol=1e-3):
                raise ValueError(f"Weekly production differs from saved periods: {directory}")
            weekly_rows.append({"scenario": scenario, "label": label, **record, "source_summary_sha256": summary_hash, "source_production_sha256": digest(production_path)})
        for component, amount in summary["cost_breakdown"].items():
            costs.append({"scenario": scenario, "label": label, "component": component, "amount": amount, "accounting_stage": "raw_solver_ledger", "source_summary_sha256": summary_hash})
        for component, amount in summary["carbon_expressions"].items():
            carbon.append({"scenario": scenario, "label": label, "component": component, "emissions_kg_co2e": amount, "accounting_stage": "raw_solver_ledger", "source_summary_sha256": summary_hash})
        certificates.append({"scenario": scenario, "label": label, **{name: summary[name] for name in ["solver", "version", "status", "has_solution", "rows", "columns", "seconds", "objective", "lower_bound", "gap"]}, **{f"algebraic.{key}": value for key, value in summary["algebraic_validation"].items()}, "source_summary_sha256": summary_hash})
        physical_name = "byproduct_physical_validation.json" if "-BH" in scenario else "physical_validation.json"
        physics_rows.append(validation(directory / physical_name, scenario, label, summary_hash))
        hydrogen_rows.append(validation(directory / "independent_hydrogen_transport/hydrogen_transport_validation.json", scenario, label, summary_hash))
        inventory_rows.append(validation(directory / "independent_inventory_cost/inventory_cost_validation.json", scenario, label, summary_hash))
        if scenario.startswith("DAC-"):
            co2_rows.append(validation(directory / "independent_co2/co2_validation.json", scenario, label, summary_hash))
        for path in [summary_path, config_path, parameters_path, production_path]:
            track(path, scenario, label, "original_run_source")
        if accounts_root is not None:
            path = accounts_root / scenario / label / "accounts.json"
            accounts = read_json(path)
            if accounts["schema_version"] != 1 or (accounts["scenario"], accounts["label"]) != (scenario, label):
                raise ValueError(f"Unsupported account schema or scenario: {path}")
            if accounts["source_summary_sha256"] != summary_hash or accounts["checks"]["passed"] is not True:
                raise ValueError(f"Accounts have not passed for current source summary: {path}")
            account_rows.append({"scenario": scenario, "label": label, "final_cost_cny_kg": accounts["final_cost"]["unit_cost_cny_kg"], "final_carbon_intensity_g_mj": accounts["final_carbon"]["intensity_g_mj"], "source_summary_sha256": summary_hash, "accounts_sha256": digest(path), "accounts_path": str(path)})
            track(path, scenario, label, "final_inventory_account")

    fixed_rows = []
    for scenario in PAIRED:
        if not {(scenario, "baseline"), (scenario, "summer_fixed")}.issubset(directories):
            continue
        differences = {}
        pair_directories = [directories[scenario, label] for label in ["baseline", "summer_fixed"]]
        for name, keys in [("saf_capacity", ["location", "technology"]), ("saf_build", ["location", "technology"]), ("h2_capacity", ["location"]), ("h2_build", ["location"])]:
            paths = [folder / f"{name}.csv" for folder in pair_directories]
            tables = [pd.read_csv(path).set_index(keys)["value"].sort_index() for path in paths]
            if not tables[0].index.equals(tables[1].index):
                raise ValueError(f"Fixed-asset identifiers differ: {scenario}/{name}")
            differences[name] = float((tables[0] - tables[1]).abs().max())
            for path, label in zip(paths, ["baseline", "summer_fixed"]):
                track(path, scenario, label, "fixed_asset_source")
        if scenario.startswith("DAC-"):
            paths = [folder / "dac_build.csv" for folder in pair_directories]
            if all(path.exists() for path in paths):
                tables = [pd.read_csv(path).set_index("location")["value"].sort_index() for path in paths]
            else:
                paths = [folder / "variables.csv" for folder in pair_directories]
                tables = [pd.read_csv(path, usecols=["variable", "value"]).set_index("variable")["value"] for path in paths]
                tables = [table[table.index.str.startswith("dac_facility_")].sort_index() for table in tables]
            if not len(tables[0]) or not tables[0].index.equals(tables[1].index):
                raise ValueError(f"DAC build variables do not identify an equal asset set: {scenario}")
            differences["dac_build"] = float((tables[0] - tables[1]).abs().max())
            for path, label in zip(paths, ["baseline", "summer_fixed"]):
                track(path, scenario, label, "fixed_dac_asset_source")
        if max(differences.values()) > 1e-4:
            raise ValueError(f"Alternative weeks changed fixed production assets: {scenario}/{differences}")
        fixed_rows.append({"scenario": scenario, **differences, "passed": True, "baseline_summary_sha256": digest(pair_directories[0] / "summary.json"), "summer_summary_sha256": digest(pair_directories[1] / "summary.json")})

    output.mkdir(parents=True, exist_ok=True)
    outputs = {"new_summary_raw.csv": summary_rows, "new_weekly_metrics.csv": weekly_rows,
               "new_cost_components_raw.csv": costs, "new_carbon_components_raw.csv": carbon,
               "solver_certificates.csv": certificates, "physical_validation_summary.csv": physics_rows,
               "co2_validation_summary.csv": co2_rows, "hydrogen_transport_validation_summary.csv": hydrogen_rows,
               "inventory_cost_validation_summary.csv": inventory_rows,
               "fixed_asset_validation.csv": fixed_rows, "source_hashes.csv": tracked}
    if accounts_root is not None:
        outputs["final_accounts_summary.csv"] = account_rows
    for name, records in outputs.items():
        pd.DataFrame(records).to_csv(output / name, index=False)
    report = {"scope": "Verified real run summaries and validation evidence; inventory accounts are consumed separately without recalculation.",
              "revision_expected_runs": len(CASES), "collected_runs": len(summary_rows), "collected_baselines": sum(row["label"] == "baseline" for row in summary_rows),
              "collected_fixed_asset_pairs": len(fixed_rows), "full_revision_set_collected": set(cases) == set(CASES),
              "final_accounts_included": accounts_root is not None, "source_files_tracked": len(tracked),
              "outputs": {name: {"rows": len(records), "sha256": digest(output / name)} for name, records in outputs.items()}, "passed": True}
    (output / "collection_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--accounts-root", type=Path)
    parser.add_argument("--case", action="append", help="Optional exact scenario/label for a bounded real-data check")
    args = parser.parse_args()
    selected = None if args.case is None else [tuple(case.split("/")) for case in args.case]
    report = collect(args.results.resolve(), args.out.resolve(), None if args.accounts_root is None else args.accounts_root.resolve(), selected)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
