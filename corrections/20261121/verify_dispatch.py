import argparse
import csv
import gzip
import hashlib
import json
import math
import shutil
import time
from collections import defaultdict
from pathlib import Path

import highspy
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import csc_matrix

from build_capture_input import digest


CASES = [(case, label) for case in ("CCU-BH-FT", "CCU-BH-MTJ", "CCU-GH-FT", "CCU-GH-MTJ")
         for label in (("baseline", "summer_fixed") if "-GH-" in case else ("baseline",))]
PROOF_ROOT = "provenance/solver_records/a45bdbcd1910e53c"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")


def route_records(path):
    with path.open(encoding="utf-8-sig", newline="") as fp:
        reader = csv.DictReader(fp)
        rows = list(reader)
        return reader.fieldnames, rows


def weekly_sums(rows):
    sources, destinations = defaultdict(list), defaultdict(list)
    for r in rows:
        amount = float(r["weekly_contract_kg"])
        sources[r["source"]].append(amount)
        destinations[r["destination"]].append(amount)
        if not math.isclose(4*amount, float(r["representative_window_transport_kg"]), abs_tol=1e-6):
            raise ValueError("Weekly and four-week route amounts are inconsistent")
    return ({s: math.fsum(v) for s, v in sources.items()}, {d: math.fsum(v) for d, v in destinations.items()})


def route_repair(rows, regional):
    original, received = weekly_sums(rows)
    limits = {k: 1000*v["corrected_t_week"] for k, v in regional.items()}
    excesses = {s: q-limits[s] for s, q in original.items() if q-limits[s] > 1e-4}
    if not excesses:
        return rows, []
    alternatives = []
    by_route = {(r["source"], r["destination"]): r for r in rows}
    for source, excess in excesses.items():
        site = regional[source]
        for other, used in original.items():
            peer = regional[other]
            if other == source or used <= 1e-5 or limits[other]-used <= 1e-5:
                continue
            if any(site[k] != peer[k] for k in ("kind", "latitude", "longitude", "price_cny_t")):
                continue
            for (s, dest), r in by_route.items():
                if s != source or float(r["weekly_contract_kg"]) <= 1e-5 or (other, dest) not in by_route:
                    continue
                alternative = by_route[other, dest]
                if all(r[k] == alternative[k] for k in ("pipeline_distance_km","transport_cny_per_kg_km","transport_cny_per_kg")):
                    alternatives.append((source,other,dest,float(r["weekly_contract_kg"])))
    if not alternatives:
        raise ValueError("No interchangeable, previously used unit at the affected site")
    alternatives.sort(key=lambda r: (-r[3], r[0], r[1], r[2]))
    constraints = []
    right = []
    for source, excess in excesses.items():
        constraints.append([-int(a[0] == source) for a in alternatives])
        right.append(-excess)
    for other in sorted({a[1] for a in alternatives}):
        constraints.append([int(a[1] == other) for a in alternatives])
        right.append(limits[other]-original[other])
    for source, dest in sorted({(a[0], a[2]) for a in alternatives}):
        constraints.append([int(a[0]==source and a[2]==dest) for a in alternatives])
        right.append(float(by_route[source,dest]["weekly_contract_kg"]))
    ones = np.ones(len(alternatives))
    first = linprog(ones, A_ub=constraints, b_ub=right, bounds=(0,None), method="highs")
    if not first.success:
        raise RuntimeError(first.message)
    second = linprog(np.arange(len(alternatives), dtype=float), A_ub=constraints, b_ub=right,
                     A_eq=[ones], b_eq=[first.fun], bounds=(0,None), method="highs")
    if not second.success:
        raise RuntimeError(second.message)
    updated = {k: dict(r) for k,r in by_route.items()}
    changes = []
    for (old,new,dest,_), quantity in zip(alternatives, second.x, strict=True):
        if quantity <= 1e-4:
            continue
        for source,diff in ((old,-quantity),(new,quantity)):
            r = updated[source,dest]
            value = float(r["weekly_contract_kg"])+diff
            r["weekly_contract_kg"] = format(value,".17g")
            r["representative_window_transport_kg"] = format(4*value,".17g")
        changes.append({"from":old,"to":new,"destination":dest,"kg_week":float(quantity),
                        "distance_km":float(by_route[old,dest]["pipeline_distance_km"])})
    updated = list(updated.values())
    new_sources, new_receipts = weekly_sums(updated)
    assert max(abs(q-new_receipts[s]) for s,q in received.items()) < 1e-5
    assert all(q <= limits[s]+1e-4 for s,q in new_sources.items())
    return updated, changes


def full_model(proof, case, label, original_certificate, regional, original_rows, corrected_rows, changes, output, scratch):
    archive = proof/"original_models"/case/label/"model.mps.gz"
    if digest(archive) != original_certificate["source_sha256"]:
        raise ValueError("Wrong full model for the published certificate")
    matrix_path = scratch/(case+".mps")
    with gzip.open(archive,"rb") as f, matrix_path.open("wb") as g:
        shutil.copyfileobj(f,g,length=4*1024*1024)
    h = highspy.Highs()
    h.setOptionValue("output_flag", False)
    h.setOptionValue("threads", 2)
    ok = highspy.HighsStatus.kOk
    if h.readModel(str(matrix_path)) != ok:
        raise ValueError("HiGHS could not read the original MPS")
    lp = h.getLp()
    names, row_names = lp.col_names_, lp.row_names_
    column_hash = hashlib.sha256("\n".join(names).encode()).hexdigest()
    assert column_hash == original_certificate["column_name_sha256"]
    old = np.load(proof/"records"/case/label/"values.npz")["values"]
    assert len(old)==lp.num_col_
    lhs, rhs = np.asarray(lp.row_lower_), np.asarray(lp.row_upper_).copy()
    lower, upper = np.asarray(lp.col_lower_), np.asarray(lp.col_upper_)
    cost = np.asarray(lp.col_cost_)
    integer_columns = np.flatnonzero(np.asarray(lp.integrality_,dtype=np.int8)!=0).astype(np.int32)
    a = lp.a_matrix_
    assert a.format_ == highspy.MatrixFormat.kColwise
    matrix = csc_matrix((np.asarray(a.value_), np.asarray(a.index_), np.asarray(a.start_)),shape=(len(row_names),len(names)))
    activity = matrix @ old
    old_row_error = float(np.maximum(np.maximum(lhs-activity,activity-rhs),0).max())
    assert old_row_error<=1e-3
    row_map = {n:i for i,n in enumerate(row_names) if n.startswith("co2_capture_capacity_")}
    assert len(row_map)==len(regional)==31
    replaced = []
    for source,record in regional.items():
        i = row_map["co2_capture_capacity_"+source]
        previous, revised = 1000*record["previous_t_week"],1000*record["corrected_t_week"]
        assert math.isclose(rhs[i],previous,rel_tol=2e-12,abs_tol=1e-5) and revised<=previous+1e-5
        if abs(revised-previous)>1e-5:
            replaced.append(i)
            rhs[i]=revised
            assert h.changeRowBounds(i,lhs[i],revised)==ok
    assert len(replaced)==16
    candidate = old.copy()
    route_columns = {n:i for i,n in enumerate(names) if n.startswith("co2_pipeline_") and n.endswith("_week")}
    def column_name(r):
        return "co2_pipeline_"+r["source"]+"_"+r["destination"].replace(" ","_")+"_week"
    assert len(original_rows)==len(route_columns)
    delta_columns=[]
    for r,s in zip(original_rows,corrected_rows,strict=True):
        key=column_name(r);assert key==column_name(s)
        i=route_columns[key]
        assert abs(old[i]-float(r["weekly_contract_kg"]))<1e-4
        v=float(s["weekly_contract_kg"])
        if abs(v-old[i])>1e-5:
            candidate[i]=v;delta_columns.append(i)
    for transfer in changes:
        dest=transfer["destination"].replace(" ","_")
        col1=route_columns[f"co2_pipeline_{transfer['from']}_{dest}_week"]
        col2=route_columns[f"co2_pipeline_{transfer['to']}_{dest}_week"]
        difference=(matrix[:,col1]-matrix[:,col2]).tocoo()
        assert set(difference.row)=={row_map["co2_capture_capacity_"+transfer["from"]],row_map["co2_capture_capacity_"+transfer["to"]]}
        assert cost[col1]==cost[col2]
    values = matrix @ candidate
    row_error = float(np.maximum(np.maximum(lhs-values,values-rhs),0).max())
    bound_error = float(np.maximum(np.maximum(lower-candidate,candidate-upper),0).max())
    integer_error = float(np.abs(candidate[integer_columns]-np.rint(candidate[integer_columns])).max())
    objective=float(cost @ candidate+lp.offset_)
    original_mps_objective=float(cost @ old+lp.offset_)
    lower_bound=float(original_certificate["lower_bound"])
    gap=(objective-lower_bound)/abs(objective)
    assert row_error<=1e-3 and bound_error<=1e-5 and integer_error<=1e-5 and 0<=gap<=.01
    assert math.isclose(objective,original_mps_objective,rel_tol=1e-12,abs_tol=.01)
    result={"rows":lp.num_row_,"columns":lp.num_col_,"changed_upper_bound_rows":len(replaced),
            "changed_primal_columns":[names[i] for i in delta_columns],"column_name_sha256":column_hash,
            "original_mps_gzip_sha256":digest(archive),"original_full_primal_sha256":digest(proof/"records"/case/label/"values.npz"),
            "max_constraint_absolute_residual":row_error,"max_bound_violation":bound_error,"max_integer_violation":integer_error,
            "archived_objective_CNY":float(original_certificate["objective"]),"corrected_objective_CNY":objective,
            "valid_global_lower_bound_CNY":lower_bound,"certified_total_objective_gap":gap}
    if changes:
        weekly=np.fromiter((i for i,n in enumerate(names) if n.endswith("_week") and n.startswith(("h2_pipeline_transport_","co2_pipeline_"))),dtype=np.int32)
        fixed=np.union1d(integer_columns,weekly).astype(np.int32)
        fixed_values=candidate[fixed].copy()
        fixed_values[np.isin(fixed,integer_columns)]=np.rint(fixed_values[np.isin(fixed,integer_columns)])
        assert h.changeColsBounds(len(fixed),fixed,fixed_values,fixed_values)==ok
        assert h.changeColsIntegrality(len(integer_columns),integer_columns,np.zeros(len(integer_columns),dtype=np.uint8))==ok
        scale=1e6
        priced=np.flatnonzero(cost).astype(np.int32)
        assert h.changeColsCost(len(priced),priced,cost[priced]/scale)==ok
        assert abs(lp.offset_)<1e-10
        h.setOptionValue("solver","simplex")
        h.setOptionValue("presolve","on")
        h.setOptionValue("primal_feasibility_tolerance",1e-7)
        h.setOptionValue("dual_feasibility_tolerance",1e-9)
        h.setOptionValue("log_file",str(scratch/"full_dispatch.log"))
        h.setOptionValue("log_to_console",False);h.setOptionValue("output_flag",True)
        started=time.perf_counter()
        status=h.run()
        elapsed=time.perf_counter()-started
        if status!=ok or h.getModelStatus()!=highspy.HighsModelStatus.kOptimal:
            raise RuntimeError(f"Full corrected economic dispatch failed: {h.modelStatusToString(h.getModelStatus())}")
        sol=np.asarray(h.getSolution().col_value)
        independent_objective=float(cost @ sol+lp.offset_)
        actual = matrix @ sol
        optimum_resid=float(np.maximum(np.maximum(lhs-actual,actual-rhs),0).max())
        optimum_cost=float(h.getObjectiveValue()*scale)
        assert optimum_resid<=.001 and abs(independent_objective-optimum_cost)<1 and abs(objective-optimum_cost)<1
        assert float(np.max(np.abs(sol[fixed]-fixed_values)))<=1e-5
        result.update({"dispatch_solver":"HiGHS "+h.version(),"full_fixed_design_dispatch_status":"Optimal",
                       "economic_dispatch_optimum_CNY":optimum_cost,"retained_solution_minus_independent_optimum_CNY":objective-optimum_cost,
                       "independent_solve_max_row_residual":optimum_resid,"fixed_design_and_weekly_variables":len(fixed),"full_dispatch_seconds":elapsed,
                       "selection":"An economically equivalent dispatch retains all archived non-CO2 variables. Among previously used co-located units, minimize the weekly tonnage reassigned, using larger original contracts first in a tie."})
        np.savez_compressed(output/"full_dispatch_values.npz",values=candidate)
        result["full_primal_sha256"]=digest(output/"full_dispatch_values.npz")
    return result


def verify(archive,limits,output,scratch,case,label):
    regional = {r["source"]:r for r in read_json(limits)["regional_sources"]}
    source=archive/"revision_20261017"/"saved_results"/case/label
    proof=archive/"revision_20261017"/PROOF_ROOT
    certificate=read_json(source/"certificate.json")
    assert certificate["passed"]
    csv_path=source/"ccu_co2_transport_accounting.csv"
    fields,rows=route_records(csv_path)
    result,changes=route_repair(rows,regional)
    out=output/case/label;out.mkdir(parents=True,exist_ok=True);scratch.mkdir(parents=True,exist_ok=True)
    flows,_=weekly_sums(result)
    used={s: {"weekly_t":q/1000,"corrected_t_week":regional[s]["corrected_t_week"]} for s,q in flows.items()}
    if set(used)!=set(regional) or any(r["weekly_t"]>r["corrected_t_week"]+1e-6 for r in used.values()):
        raise RuntimeError("A corrected regional capacity constraint is violated")
    record={"scenario":case,"label":label,"new_supply_limits_checked":len(used),"regional_flows":used,"transfers":changes,
            "original_certificate_sha256":digest(source/"certificate.json"),"original_contracts_sha256":digest(csv_path),
            "original_full_model_feasible":certificate["passed"],"valid_global_lower_bound_CNY":certificate["lower_bound"],
            "original_total_objective_CNY":certificate["objective"],"certified_total_objective_gap":certificate["gap"],
            "bound_argument":"The 16 regional coal-source ceilings decrease. The other 15 ceilings, remaining constraint rows, objective and variable domains are identical. The preceding global lower bound remains valid for the restriction."}
    if changes:
        with (out/csv_path.name).open("w",encoding="utf-8",newline="") as f:
            writer=csv.DictWriter(f,fields);writer.writeheader();writer.writerows(result)
        record["corrected_contracts_sha256"]=digest(out/csv_path.name)
    if case.startswith("CCU-BH"):
        record["full_matrix"]=full_model(proof,case,label,certificate,regional,rows,result,changes,out,scratch)
    else:
        assert not changes
        record["unchanged_primal_sha256"]=digest(proof/"records"/case/label/"values.npz")
    record["passed"]=True
    save_json(out/"capture_dispatch_certificate.json",record)
    print(case,label,"certified gap",record["certified_total_objective_gap"],"reassigned",changes,flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--archive",type=Path,required=True)
    parser.add_argument("--limits",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--scratch",type=Path,required=True)
    parser.add_argument("--case",choices=sorted({c for c,_ in CASES}))
    parser.add_argument("--label",choices=("baseline","summer_fixed"))
    options=parser.parse_args()
    selected=[(c,l) for c,l in CASES if (not options.case or c==options.case) and (not options.label or l==options.label)]
    if not selected:
        parser.error("This configuration has no archived solution")
    for scenario,period in selected:
        verify(options.archive,options.limits,options.output,options.scratch,scenario,period)
