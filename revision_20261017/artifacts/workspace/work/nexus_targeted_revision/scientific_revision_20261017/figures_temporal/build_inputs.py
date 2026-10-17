from pathlib import Path
import argparse
import hashlib
import json

import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
WORK = HERE.parent
PROJECT = WORK.parents[2]
BASELINES = ["CTL", "CTL-BH", "GTL-GH", "GTL", "CCU-BH-MTJ", "CCU-BH-FT", "GTL-BH", "DAC-BH-MTJ", "DAC-BH-FT", "DAC-GH-MTJ", "DAC-GH-FT", "CCU-GH-MTJ", "CCU-GH-FT"]
NEW_BASELINES = [name for name in BASELINES if name != "GTL"]
PERIODS, HOURS, WEEK_PERIODS = 224, 3.0, 56
GTL_SOURCE_SHA256 = "600de5945d834feee140891dc11b50e9b40cca3972d9f5da21ebe43a4e3b3f08"
DEFAULT_RENEWABLE = WORK / "pv_inputs/inputs/baseline/renewable_periods.csv"
DEFAULT_GTL_SOURCE = WORK.parent / "github_archive/repository/archived_outputs/products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/ft_one_step"
DEFAULT_GTL_ADAPTED = WORK.parent / "revision_20261007/figures_cost/adapted_data"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def close(actual, expected, description, atol=1e-5):
    if not np.isclose(actual, expected, rtol=1e-8, atol=atol):
        raise ValueError(f"{description}: {actual} != {expected}")


def period_sum(path):
    frame = pd.read_csv(path)
    values = frame["value"].to_numpy(dtype=float)
    if not np.isfinite(values).all() or values.min(initial=0) < -1e-4:
        raise ValueError(f"Invalid physical quantity: {path}")
    periods = frame["period"].to_numpy()
    if not np.equal(periods, periods.astype(int)).all() or set(periods) != set(range(PERIODS)):
        raise ValueError(f"Incomplete or noninteger model periods: {path}")
    return frame.groupby("period")["value"].sum().reindex(range(PERIODS)).to_numpy(dtype=float)


def capacity(path):
    frame = pd.read_csv(path)
    values = frame["value"].to_numpy(dtype=float)
    if not np.isfinite(values).all() or values.min(initial=0) < -1e-5:
        raise ValueError(f"Invalid capacity: {path}")
    return float(values.sum()), frame


def physical_utilization(production, denominator, name):
    if denominator <= 0:
        if np.abs(production).max(initial=0) > 1e-4:
            raise ValueError(f"Positive production without an installed capacity: {name}")
        return None
    values = production / (HOURS * denominator)
    if values.min(initial=0) < -1e-7 or values.max(initial=0) > 1 + 1e-5:
        raise ValueError(f"Production exceeds saved capacity: {name}; range={values.min()}, {values.max()}")
    return values


def independent_metrics(saf, h2, saf_capacity, h2_capacity, power):
    utilization = physical_utilization(saf, saf_capacity, "SynAF")
    hydrogen = physical_utilization(h2, h2_capacity, "H2")
    weekly = utilization.reshape(4, WEEK_PERIODS).mean(axis=1)
    mean, worst = float(utilization.mean()), float(weekly.min())
    if mean <= 0 or worst <= 0:
        raise ValueError("Capacity premiums require positive mean and worst-week utilization")
    runs = []
    for week in utilization.reshape(4, WEEK_PERIODS):
        current = 0
        for flag in week < .70:
            if flag:
                current += 1
            elif current:
                runs.append(current * HOURS)
                current = 0
        if current:
            runs.append(current * HOURS)
    renew_mean = float(np.mean(power))
    within_week_changes = np.diff(power.reshape(4, WEEK_PERIODS), axis=1).reshape(-1)
    return {
        "mean_synaf_utilization": mean,
        "mean_hydrogen_utilization": None if hydrogen is None else float(hydrogen.mean()),
        "weekly_synaf_utilization": weekly.tolist(),
        "worst_week_retention": worst / mean,
        "mean_utilization_capacity_premium_pct": (1 / mean - 1) * 100,
        "additional_worst_week_capacity_premium_pct": (1 / worst - 1 / mean) * 100,
        "total_capacity_premium_pct": (1 / worst - 1) * 100,
        "low_load_episode_count_over_6h": sum(duration > 6 for duration in runs),
        "low_load_episode_count_over_12h": sum(duration > 12 for duration in runs),
        "mean_low_load_run_hours": float(np.mean(runs)) if runs else 0.0,
        "max_low_load_run_hours": max(runs, default=0.0),
        "renewable_mean_mw": renew_mean,
        "renewable_cv_pct": float(np.std(power) / renew_mean * 100) if renew_mean > 1e-12 else 0.0,
        "renewable_zero_pct": float(np.mean(power <= 1e-9) * 100) if renew_mean > 1e-12 else 0.0,
        "renewable_within_week_ramp_pct": float(np.mean(np.abs(within_week_changes)) / renew_mean * 100) if renew_mean > 1e-12 else 0.0,
    }


def prepare_new(name, results, accounts_root, resource):
    run, account_dir = results / name / "baseline", accounts_root / name / "baseline"
    summary_path, account_path = run / "summary.json", account_dir / "accounts.json"
    summary, accounts = read_json(summary_path), read_json(account_path)
    if (run / "EXPORT_IN_PROGRESS").exists():
        raise ValueError(f"Run export is incomplete: {run}")
    if (summary["scenario"], summary["label"]) != (name, "baseline") or summary["has_solution"] is not True:
        raise ValueError(f"Run identity or solution status is invalid: {run}")
    if summary["algebraic_validation"]["passed"] is not True or not 0 <= summary["gap"] <= .01:
        raise ValueError(f"Run has no accepted solution certificate: {run}")
    if (accounts["scenario"], accounts["label"]) != (name, "baseline") or accounts["schema_version"] != 1:
        raise ValueError(f"Unsupported final accounts: {account_path}")
    if accounts["source_summary_sha256"] != digest(summary_path) or accounts["checks"]["passed"] is not True:
        raise ValueError(f"Accounts do not certify current real summary: {account_path}")
    for source, expected in accounts["source_hashes"].items():
        if digest(run / source) != expected:
            raise ValueError(f"Account source bytes differ: {run / source}")
    parameters = read_json(run / "model_parameters.json")
    if (int(parameters["periods"]), float(parameters["hours_per_period"]), int(parameters["weeks"])) != (PERIODS, HOURS, 4):
        raise ValueError(f"Unexpected represented time: {run}")
    saf, h2 = period_sum(run / "saf_production.csv"), period_sum(run / "h2_production.csv")
    saf_capacity, _ = capacity(run / "saf_capacity.csv")
    h2_capacity, h2_sites = capacity(run / "h2_capacity.csv")
    close(saf.sum(), summary["production_kg"], f"{name} actual output", atol=.01)
    close(saf_capacity, summary["saf_capacity_kg_h"], f"{name} installed SynAF capacity")
    close(h2_capacity, summary["h2_capacity_kg_h"], f"{name} installed H2 capacity")
    solution_path, carbon_path = account_dir / "normalized_complete_solution.json", account_dir / "normalized_carbon_emissions.json"
    solution, carbon = read_json(solution_path), read_json(carbon_path)
    if solution["source_sha256"] != digest(summary_path) or carbon["source_summary_sha256"] != digest(summary_path):
        raise ValueError(f"Normalized records are stale: {account_dir}")
    for fuel, values in [("saf_kg", saf), ("hydrogen_kg", h2)]:
        if not np.allclose(solution["hourly_production_summary"][fuel], values, rtol=1e-9, atol=1e-4):
            raise ValueError(f"Normalized period dispatch differs: {name}/{fuel}")
    for facility in solution["hydrogen_facilities"].values():
        facility["capacity_kg_h2_per_hour"] = facility["capacity_kg_per_hour"]
    for key in ["total_investment_cost", "total_operation_cost", "total_cost_excluding_shortage"]:
        solution[key] = solution["cost_breakdown_raw"][key]
    power = np.zeros(PERIODS)
    active = set(h2_sites.loc[h2_sites.value > 1e-5, "location"])
    if "-BH" not in name:
        missing = active - set(resource.plant_name)
        if missing:
            raise ValueError(f"Active renewable H2 sites absent from corrected input: {name}/{sorted(missing)}")
        selected = resource[resource.plant_name.isin(active)]
        if selected.duplicated(["plant_name", "period"]).any():
            raise ValueError("Duplicate renewable site-period input")
        power = selected.groupby("period").power_output_mw.sum().reindex(range(PERIODS), fill_value=0).to_numpy()
    h2_basis = "conditioning_capacity" if "-BH" in name else "electrolyzer_capacity"
    solution["hydrogen_utilization_basis"] = h2_basis
    metrics = independent_metrics(saf, h2, saf_capacity, h2_capacity, power)
    close(metrics["mean_synaf_utilization"], summary["mean_utilization"], f"{name} mean utilization")
    close(metrics["worst_week_retention"], summary["worst_week_retention"], f"{name} worst-week retention")
    frame = pd.DataFrame({"时段": np.arange(PERIODS), "时段长度(h)": HOURS, "氢气产出(kg)": h2,
                          "SAF产出(kg)": saf, "电力产出(MWh)": power * HOURS})
    used = [summary_path, account_path, solution_path, carbon_path, run / "saf_production.csv", run / "h2_production.csv", run / "saf_capacity.csv", run / "h2_capacity.csv", run / "model_parameters.json"]
    meta = {"scenario": name, "source_kind": "new_real_baseline", "run": str(run),
            "demand_fulfillment_ratio": summary["demand_fulfillment_ratio"], "hydrogen_basis": h2_basis,
            "synaf_capacity_kg_h": saf_capacity, "hydrogen_capacity_kg_h": h2_capacity,
            "renewable_active_h2_sites": sorted(active) if "-BH" not in name else [],
            "independent_metrics": metrics, "source_hashes": {str(path): digest(path) for path in used}}
    return solution, carbon, frame, meta


def prepare_gtl(archive=DEFAULT_GTL_SOURCE, adapted=DEFAULT_GTL_ADAPTED):
    original = archive / "complete_solution_20260201_215354.json"
    hourly_path = archive / "hourly_production_summary_20260201_215354.csv"
    if digest(original) != GTL_SOURCE_SHA256:
        raise ValueError("Retained GTL source differs from the specified archived record")
    mapping = read_json(adapted / "manifest.json")["GTL"]
    if mapping["source_sha256"] != GTL_SOURCE_SHA256:
        raise ValueError("Retained GTL normalized record identifies another source")
    solution_path, carbon_path = adapted / "GTL_complete_solution.json", adapted / "GTL_carbon_emissions.json"
    solution, carbon = read_json(solution_path), read_json(carbon_path)
    hourly = pd.read_csv(hourly_path)
    period_column = "时段"
    if not hourly[period_column].tolist() == list(range(PERIODS)):
        raise ValueError("Retained GTL does not contain 224 ordered actual periods")
    length_column = next(column for column in hourly if "时段长度" in column)
    if not np.equal(hourly[length_column], HOURS).all():
        raise ValueError("Retained GTL period length differs from three hours")
    saf, h2 = hourly["SAF产出(kg)"].to_numpy(), hourly["氢气产出(kg)"].to_numpy()
    saf_capacity = sum(float(facility.get("capacity_kg_per_hour", 0)) for facility in solution["facilities"].values()
                       if facility.get("technology") != "electrolyzer" and facility.get("transport_mode") != "hydrogen_pipeline")
    h2_capacity = sum(float(facility.get("capacity_kg_h2_per_hour", facility.get("capacity_kg_per_hour", 0)))
                      for facility in solution.get("hydrogen_facilities", {}).values())
    power = hourly["电力产出(MWh)"].to_numpy() / HOURS
    metrics = independent_metrics(saf, h2, saf_capacity, h2_capacity, power)
    solution["hydrogen_utilization_basis"] = "none" if h2_capacity == 0 else "electrolyzer_capacity"
    meta = {"scenario": "GTL", "source_kind": "retained_actual_archived_baseline", "source": str(original),
            "hydrogen_basis": solution["hydrogen_utilization_basis"],
            "demand_fulfillment_ratio": solution["demand_fulfillment_ratio"],
            "synaf_capacity_kg_h": saf_capacity, "hydrogen_capacity_kg_h": h2_capacity,
            "independent_metrics": metrics,
            "source_hashes": {str(path): digest(path) for path in [original, hourly_path, solution_path, carbon_path, adapted / "manifest.json"]}}
    return solution, carbon, hourly, meta


def build(results, accounts_root, output, historical_only=False, selected=None,
          renewable_path=DEFAULT_RENEWABLE, gtl_source_dir=DEFAULT_GTL_SOURCE, gtl_adapted_dir=DEFAULT_GTL_ADAPTED):
    names = ["GTL"] if historical_only else ([selected] if selected else BASELINES)
    if not historical_only:
        required = [root / name / "baseline" / file for name in names if name != "GTL"
                    for root, file in [(results, "summary.json"), (accounts_root, "accounts.json")]]
        missing = [str(path) for path in required if not path.is_file()]
        if missing:
            raise FileNotFoundError("Temporal figures require twelve new real baselines and their final accounts:\n" + "\n".join(missing))
        resource = pd.read_csv(renewable_path)
    output.mkdir(parents=True, exist_ok=True)
    manifest = {"schema_version": 1, "full_thirteen_baselines": not historical_only and selected is None,
                "represented_periods": PERIODS, "hours_per_period": HOURS,
                "representative_weeks": 4, "low_load_threshold": .70,
                "ramp_definition": "Mean absolute three-hour renewable-power difference within each representative week, divided by mean power; noncontinuous week boundaries excluded.",
                "configurations": {}}
    if not historical_only:
        manifest["renewable_input"] = {"path": str(renewable_path), "sha256": digest(renewable_path)}
    for name in names:
        solution, carbon, hourly, meta = prepare_gtl(gtl_source_dir, gtl_adapted_dir) if name == "GTL" else prepare_new(name, results, accounts_root, resource)
        paths = {"solution": output / f"{name}_solution.json", "carbon": output / f"{name}_carbon.json", "hourly": output / f"{name}_hourly.csv"}
        write_json(paths["solution"], solution)
        write_json(paths["carbon"], carbon)
        hourly.to_csv(paths["hourly"], index=False, encoding="utf-8")
        meta["adapted_files"] = {key: {"path": str(path), "sha256": digest(path)} for key, path in paths.items()}
        manifest["configurations"][name] = meta
    write_json(output / "manifest.json", manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, default=WORK / "results")
    parser.add_argument("--accounts-root", type=Path, default=WORK / "postprocess/accounts")
    parser.add_argument("--out", type=Path, default=HERE / "inputs")
    parser.add_argument("--renewable-input", type=Path, default=DEFAULT_RENEWABLE)
    parser.add_argument("--gtl-source-dir", type=Path, default=DEFAULT_GTL_SOURCE)
    parser.add_argument("--gtl-adapted-dir", type=Path, default=DEFAULT_GTL_ADAPTED)
    parser.add_argument("--historical-only", action="store_true", help="Validate only the retained actual GTL data; no full-set rendering is permitted")
    parser.add_argument("--case", choices=BASELINES, help="Validate one real baseline; no full-set rendering is permitted")
    args = parser.parse_args()
    if args.historical_only and args.case:
        raise ValueError("Choose one bounded check scope")
    manifest = build(args.results.resolve(), args.accounts_root.resolve(), args.out.resolve(), args.historical_only, args.case,
                     args.renewable_input.resolve(), args.gtl_source_dir.resolve(), args.gtl_adapted_dir.resolve())
    print(json.dumps({"configurations": list(manifest["configurations"]), "full_thirteen_baselines": manifest["full_thirteen_baselines"]}))


if __name__ == "__main__":
    main()
