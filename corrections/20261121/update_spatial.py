import argparse
import csv
import importlib.util
import json
import math
import sys
from pathlib import Path

from build_capture_input import digest


CASE="CCU-BH-FT"


def load_module(name,file):
    spec=importlib.util.spec_from_file_location(name,file)
    module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module
    spec.loader.exec_module(module)
    return module


def json_read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def json_save(path,data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


def read_csv(file):
    with file.open(encoding="utf-8-sig",newline="") as f:
        reader=csv.DictReader(f)
        return reader.fieldnames,list(reader)


def update(archive,published,contracts,certificate,output):
    root=archive/"revision_20261017"
    legacy=root/"artifacts/workspace/work/nexus_targeted_revision"
    builder=load_module("nexus_spatial_inputs",legacy/"scientific_revision_20261017/figures_spatial/build_inputs.py")
    metrics_module=load_module("nexus_network_metrics",legacy/"revision_20261007/figures_space_time/source/network_classification_metrics_builder.py")
    report=json_read(certificate)
    assert report["passed"] and report["corrected_contracts_sha256"]==digest(contracts)
    solution=json_read(root/"final_accounts"/CASE/"baseline"/"normalized_complete_solution.json")
    routes=json_read(published/(CASE+"_routes.json"))
    params=json_read(root/"saved_results"/CASE/"baseline"/"model_parameters.json")
    original_co2=[r for r in routes if r["cargo"]=="CO2"]
    assert len({r["distance_source"] for r in original_co2})==1
    _,rows=read_csv(contracts)
    revised_co2=[builder.route_record(CASE,r["source"],r["destination"],"CO2",float(r["weekly_contract_kg"]),
                  float(r["pipeline_distance_km"]),params["locations"],original_co2[0]["distance_source"])
                 for r in rows if float(r["weekly_contract_kg"])>1e-5]
    first=routes.index(original_co2[0]);last=routes.index(original_co2[-1])+1
    assert routes[first:last]==original_co2
    new_routes=routes[:first]+revised_co2+routes[last:]
    output.mkdir(parents=True,exist_ok=True)
    metrics,siting,decisions,modules=builder.network_tables(CASE,solution,new_routes,output,metrics_module)
    header,all_metrics=read_csv(published/"network_metrics.csv")
    comparison={}
    for row in all_metrics:
        if row["Scenario"]!=CASE:continue
        for key in builder.METRIC_NAMES+["H2_distance_km","H2_weekly_quantity","SAF_distance_km","SAF_weekly_quantity","CO2_distance_km","CO2_weekly_quantity","NG_distance_km","NG_weekly_quantity"]:
            old=float(row[key]);new=float(metrics[key])
            if not math.isclose(old,new,abs_tol=1e-9,rel_tol=1e-10):
                row[key]=repr(new)
                comparison[key]={"previous":old,"corrected":new}
        assert all(math.isclose(float(row[k]),float(v),abs_tol=1e-9) for k,v in siting.items() if k not in ("Scenario","OfficialName","Cluster"))
    assert set(comparison)=={"关键通道集中度","单点失效影响"},comparison
    with (output/"network_metrics.csv").open("w",encoding="utf-8",newline="") as f:
        writer=csv.DictWriter(f,header,lineterminator="\n")
        writer.writeheader();writer.writerows(all_metrics)
    nodes=CASE+"_nodes.json"
    assert json_read(output/nodes)==json_read(published/nodes)
    map_checks=json_read(published/"map_checks.json")
    found=[r for r in map_checks if r["scenario"]==CASE and r["variant"]=="supplement"]
    assert len(found)==1 and found[0]["routes"]==len(routes)
    found[0]["routes"]=len(new_routes)
    json_save(output/"map_checks.json",map_checks)
    provenance=json_read(published/"provenance.json")
    checked_members=[CASE+s for s in ("_nodes.json","_routes.json","_transport_summary.csv","_mass_transport.csv")]+["network_metrics.csv"]
    for member in checked_members:
        assert provenance["output_sha256"][member]==digest(published/member)
        provenance["output_sha256"][member]=digest(output/member)
    for key, record in provenance.items():
        if isinstance(record,dict) and "normalized_solution_sha256" in record:
            record["run"]=f"revision_20261017/saved_results/{key}/baseline"
            record["accounts"]=f"revision_20261017/final_accounts/{key}/baseline/accounts.json"
        if key=="GTL" and isinstance(record,dict):
            for field in ("archive","packet"):
                if field in record:record[field]=Path(record[field]).name
    provenance[CASE]["corrected_contracts_sha256"]=digest(contracts)
    provenance[CASE]["capture_dispatch_certificate_sha256"]=digest(certificate)
    provenance[CASE]["correction_builder_sha256"]=digest(Path(__file__))
    json_save(output/"provenance.json",provenance)
    joint=json_read(published/"joint_metrics_provenance.json")
    joint["temporal_metrics"]["path"]="figure_data/temporal/all_pathway_temporal_metrics.csv"
    joint["network_metrics_sha256"]=digest(output/"network_metrics.csv")
    assert joint["metrics_sha256"]==digest(published/"scenario_integrated_metrics.csv")
    json_save(output/"joint_metrics_provenance.json",joint)
    record={"scenario":CASE,"scope":"Positive mass-flow records with original study definitions, grouping and distances",
            "old_positive_routes":len(routes),"corrected_positive_routes":len(new_routes),"changed_metrics":comparison,
            "site_and_module_counts_unchanged":True,"corrected_network_metrics_sha256":digest(output/"network_metrics.csv")}
    json_save(output/"spatial_correction_checks.json",record)
    print(json.dumps(record,ensure_ascii=False,indent=1))


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    for key in ("archive","published","contracts","certificate","output"):
        parser.add_argument("--"+key,type=Path,required=True)
    opts=parser.parse_args()
    update(opts.archive,opts.published,opts.contracts,opts.certificate,opts.output)
