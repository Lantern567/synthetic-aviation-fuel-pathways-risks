import argparse
import csv
import json
import math
import sys
from pathlib import Path

import numpy as np
import yaml

from build_capture_input import digest
from verify_dispatch import CASES, PROOF_ROOT, read_json, route_records, weekly_sums


def check(archive,data):
    revision=archive/"revision_20261017"
    source=data/"input"
    inputs=read_json(source/"capture_input_checks.json")
    assert inputs["sha256"]["corrected_inventory"]==digest(source/"co2_capture_sources.csv")
    regional={r["source"]:r for r in inputs["regional_sources"]}
    assert len(regional)==31 and sum(r["corrected_t_week"]<r["previous_t_week"]-1e-6 for r in regional.values())==16
    with (source/"coal_unit_inputs.csv").open(encoding="utf-8-sig",newline="") as f:
        units=list(csv.DictReader(f))
    assert len(units)==3146 and sum(float(r["applied_MW"]) for r in units)==1136634
    assert all(float(r["applied_MW"])==300 for r in units if r["plant"]=="Yangliuqing power station")
    assert math.isclose(math.fsum(float(r["weekly_ceiling_t"]) for r in units)/1e6,inputs["corrected_Mt_week"]["coal_power"],abs_tol=1e-10)
    cases=[]
    affected_rows=None
    for name,label in CASES:
        current=data/"runs"/name/label
        base=revision/"saved_results"/name/label
        certificate=read_json(current/"capture_dispatch_certificate.json")
        assert digest(base/"certificate.json")==certificate["original_certificate_sha256"] and certificate["passed"]
        cfg=yaml.safe_load((base/"config.yaml").read_text(encoding="utf-8-sig"))
        assert cfg["co2_clustering_parameters"]["max_clusters"]>=len(regional)
        assert certificate["original_contracts_sha256"]==digest(base/"ccu_co2_transport_accounting.csv")
        changed=bool(certificate["transfers"])
        file=(current if changed else base)/"ccu_co2_transport_accounting.csv"
        _,rows=route_records(file)
        actual,_=weekly_sums(rows)
        assert set(actual)==set(regional)
        for s,q in actual.items():
            assert q<=1000*regional[s]["corrected_t_week"]+1e-4
            assert math.isclose(q/1000,certificate["regional_flows"][s]["weekly_t"],abs_tol=1e-7)
        old=read_json(base/"certificate.json")
        if "full_matrix" in certificate:
            proof=certificate["full_matrix"]
            assert proof["max_constraint_absolute_residual"]<=1e-3 and proof["max_bound_violation"]<=1e-5 and proof["max_integer_violation"]<=1e-5
            assert proof["certified_total_objective_gap"]<=.01
        if changed:
            assert name=="CCU-BH-FT" and label=="baseline"
            affected_rows=proof["rows"]
            full=revision/PROOF_ROOT/"records"/name/label/"values.npz"
            new_values=np.load(current/"full_dispatch_values.npz")["values"]
            old_values=np.load(full)["values"]
            assert len(new_values)==1546263 and np.count_nonzero(new_values!=old_values)==2
            assert math.isclose(sum(abs(new_values-old_values))/2,7431621.542372808,rel_tol=1e-12)
            assert proof["full_fixed_design_dispatch_status"]=="Optimal" and abs(proof["retained_solution_minus_independent_optimum_CNY"])<1
            assert digest(current/"full_dispatch_values.npz")==proof["full_primal_sha256"]
            validation=read_json(current/"ccu_co2_accounting_validation.json")
            assert validation["passed"] and validation["input_sha256"][file.name]==digest(file)
            final=read_json(current/"final_account_checks.json")
            assert final["fraction_of_demand"]==1 and round(final["cost_cny_kg"],2)==9.69 and round(final["carbon_g_co2e_mj"],3)==271.063
        else:
            assert certificate["certified_total_objective_gap"]==old["gap"]
        cases.append({"scenario":name,"set":label,"valid_source_limits":len(actual),"changed_weekly_contracts":2 if changed else 0,
                      "original_global_lower_bound_CNY":old["lower_bound"],"certified_gap_pct":100*certificate["certified_total_objective_gap"],
                      "evidence_sha256":digest(current/"capture_dispatch_certificate.json")})
    spatial=data/"spatial"
    report=read_json(spatial/"spatial_correction_checks.json")
    _,routes=route_records(spatial/"CCU-BH-FT_mass_transport.csv")
    flows={};links={}
    for row in routes:
        kg=float(row["周运输量(kg)"]);s=row["起点"];t=row["终点"]
        flows[s]=flows.get(s,0)+kg
        links[s,t]=links.get((s,t),0)+kg
    total=math.fsum(flows.values())
    three=sum(sorted(links.values(),reverse=True)[:3])*100/total
    largest=max(flows.values())*100/total
    assert math.isclose(three,report["changed_metrics"]["关键通道集中度"]["corrected"],abs_tol=1e-8)
    assert math.isclose(largest,report["changed_metrics"]["单点失效影响"]["corrected"],abs_tol=1e-8)
    assert (round(three,2),round(largest,2))==(55.83,34.65)
    assert affected_rows==241974
    return {"passed":True,"coal_Mt_week":inputs["corrected_Mt_week"]["coal_power"],"industrial_configurations":cases,
            "affected_full_model_rows":affected_rows,"BH_FT_top_three_route_pct":three,"BH_FT_largest_source_pct":largest}


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--archive",type=Path,required=True)
    p.add_argument("--data",type=Path,default=Path(__file__).resolve().parent/"data")
    p.add_argument("--output",type=Path)
    p.add_argument("--bounds-workspace",type=Path,help="Replay the six archived projection/partition proofs in this directory")
    args=p.parse_args()
    result=check(args.archive,args.data)
    if args.bounds_workspace:
        sys.path.insert(0,str(args.archive/"archive_tools"))
        from revision_20261017_common import revision_paths
        from verify_solver_records_revision_20261017 import verify_solver_records
        _,revision,manifest=revision_paths(args.archive)
        args.bounds_workspace.mkdir(parents=True,exist_ok=True)
        evidence=verify_solver_records(revision,manifest,args.bounds_workspace,set(CASES))
        assert evidence["passed"] and evidence["verified_actual_certificates"]==6
        result["original_bound_replay"]=[{k:row[k] for k in ("scenario","label","certificate_sha256","root_lp_primal_max_row_error",
                                         "root_lp_primal_max_bound_error","root_lp_objective_error_cny","full_model_relative_gap","passed")}
                                         for row in evidence["checks"]]
    if args.output:args.output.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print("Verified six configurations; top-three route share",result["BH_FT_top_three_route_pct"],"largest-source share",result["BH_FT_largest_source_pct"])
