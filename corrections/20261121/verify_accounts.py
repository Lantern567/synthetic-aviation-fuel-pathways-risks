import argparse
import csv
import json
import math
import shutil
from pathlib import Path

from build_capture_input import digest
from update_spatial import load_module


def verify(archive,data,scratch):
    revision=archive/"revision_20261017"
    case="CCU-BH-FT"
    original=revision/"saved_results"/case/"baseline"
    updated=data/"runs"/case/"baseline"
    scratch.mkdir(parents=True,exist_ok=True)
    for name in ("summary.json","config.yaml","ccu_co2_inventory.csv","ccu_co2_transport_parameters.json"):
        shutil.copyfile(original/name,scratch/name)
    shutil.copyfile(updated/"ccu_co2_transport_accounting.csv",scratch/"ccu_co2_transport_accounting.csv")
    validator=load_module("archived_ccu_accounts",revision/"verification_source/validate_ccu_accounts.py")
    report=validator.validate(scratch,updated/"ccu_co2_accounting_validation.json")
    old=json.loads((original/"ccu_co2_accounting_validation.json").read_text(encoding="utf-8-sig"))
    for key,value in old["expected"].items():
        if not math.isclose(value,report["expected"][key],rel_tol=1e-11,abs_tol=1e-7):
            raise ValueError(f"The {key} account changed")
    totals=revision/"final_accounts"/case/"baseline"
    account=json.loads((totals/"accounts.json").read_text(encoding="utf-8-sig"))
    with (totals/"cost_components.csv").open(encoding="utf-8-sig",newline="") as f:
        costs=math.fsum(float(r["final_cny"]) for r in csv.DictReader(f))
    with (totals/"carbon_components.csv").open(encoding="utf-8-sig",newline="") as f:
        carbon=math.fsum(float(r["final_kg_co2e"]) for r in csv.DictReader(f))
    production=account["production"]
    prices=costs/production["discounted_production_kg"]
    ci=carbon*1000/(production["production_kg"]*43.15)
    assert report["passed"] and round(prices,2)==9.69 and round(ci,3)==271.063
    results={"scenario":case,"label":"baseline","cost_cny_kg":prices,"carbon_g_co2e_mj":ci,"fuel_kg":production["production_kg"],
             "fraction_of_demand":production["demand_fulfillment_ratio"],"validator_sha256":digest(revision/"verification_source/validate_ccu_accounts.py"),
             "corrected_route_validation_sha256":digest(updated/"ccu_co2_accounting_validation.json"),"same_four_week_transport_and_storage_accounts":True}
    (updated/"final_account_checks.json").write_text(json.dumps(results,indent=2)+"\n",encoding="utf-8")
    return results


if __name__=="__main__":
    p=argparse.ArgumentParser()
    for k in ("archive","data","scratch"):p.add_argument("--"+k,type=Path,required=True)
    args=p.parse_args()
    print(json.dumps(verify(args.archive,args.data,args.scratch),indent=2))
