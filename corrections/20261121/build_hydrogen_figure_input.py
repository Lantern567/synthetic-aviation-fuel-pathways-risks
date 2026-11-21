import argparse
import csv
import json
import math
from pathlib import Path

from build_capture_input import PROVINCE_NAMES, digest


def build(refinery,steel,output):
    output.mkdir(parents=True,exist_ok=True)
    plotted=output/"Figure_S23_byproduct_hydrogen.csv"
    sectors={}
    with plotted.open("w",encoding="utf-8",newline="") as f:
        writer=csv.writer(f,lineterminator="\n")
        writer.writerow(["sector","provincial_region","gross_hydrogen_t_day"])
        for name,source,external,regions in (("Refinery",refinery,.15,26),("Steel",steel,.30,28)):
            amounts=[]
            coverage=set()
            with source.open(encoding="utf-8-sig",newline="") as src:
                for row in csv.DictReader(src):
                    province=PROVINCE_NAMES.get(row["province"],row["province"])
                    coverage.add(province);amounts.append(float(row["h2_daily_tonnes"]))
                    writer.writerow([name,province,row["h2_daily_tonnes"]])
            if "" in coverage or len(coverage)!=regions:raise ValueError("Unexpected provincial coverage for "+name)
            sectors[name]={"sites":len(amounts),"provincial_level_regions":len(coverage),"gross_t_day":math.fsum(amounts),
                           "external_supply_fraction":external,"source_sha256":digest(source)}
    record={"sectors":sectors,"plotted_quantity":"Gross site-level estimates before regional screening and external supply fractions.",
            "figure_csv_sha256":digest(plotted)}
    (output/"Figure_S23_basis.json").write_text(json.dumps(record,indent=2)+"\n",encoding="utf-8")
    return record


if __name__=="__main__":
    p=argparse.ArgumentParser()
    for d in ("refinery","steel","output"):p.add_argument("--"+d,type=Path,required=True)
    options=p.parse_args()
    print(json.dumps(build(options.refinery,options.steel,options.output),indent=2))
