import argparse
import csv
import gzip
import hashlib
import json
import math
from collections import Counter
from decimal import Decimal
from pathlib import Path

import yaml


BASE_COMMIT = "e24a85cf9a131e45be6808ace2e3b7cb140cdac9"
REGULATOR = "https://hbj.nea.gov.cn/xxgk/fdzdgknr/scxxgk/202403/P020240318557794789706.pdf#page=18"
YANG_UNITS = {f"G10000010457{i}" for i in (3, 4, 5, 6)}
PROVINCE_NAMES = {"Nanjing": "Jiangsu", "Ningxiz": "Ningxia"}


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def numeric_string(value):
    return format(value.normalize(), "f")


def fraction(value):
    text = value.strip()
    result = Decimal(text.removesuffix("%"))
    if text.endswith("%"):
        result /= 100
    if not Decimal(0) <= result <= 1:
        raise ValueError(f"Capacity factor outside [0, 1]: {value}")
    return result


def distance_from_beijing(row):
    lat, lon = map(math.radians, (float(row["latitude"]), float(row["longitude"])))
    north, east = map(math.radians, (39.9042, 116.4074))
    angle = math.sin((lat - north) / 2) ** 2 + math.cos(lat) * math.cos(north) * math.sin((lon - east) / 2) ** 2
    return 6371 * 2 * math.atan2(math.sqrt(angle), math.sqrt(1 - angle))


def build(raw, original, configuration, output):
    config = yaml.safe_load(configuration.read_text(encoding="utf-8-sig"))
    coal_parameters = config["co2_parameters"]["capture_sources"]
    hours = Decimal(str(config["basic_parameters"]["periods_per_week"] * config["basic_parameters"]["hours_per_period"]))
    emission = Decimal(str(coal_parameters["coal_power_emission_factor"]))
    capture = Decimal(str(coal_parameters["coal_power_capture_rate"]))
    with gzip.open(raw, "rt", encoding="utf-8-sig", newline="") as source:
        coal_units = {f"coal_power_{i}": row for i, row in enumerate(csv.DictReader(source))
                      if row["Status"].lower() == "operating" and row["Capacity__MW_"].strip()
                      and 10 <= Decimal(row["Capacity__MW_"]) <= 5000}
    with original.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        fields = reader.fieldnames
        rows = list(reader)
    if set(coal_units) != {r["location_id"] for r in rows if r["facility_type"] == "coal_power"}:
        raise ValueError("Power-unit and capture-source records do not correspond")
    output.mkdir(parents=True, exist_ok=True)
    unit_records = []
    regional = []
    totals = Counter()
    previous_totals = Counter()
    reidentified = set()
    for r in rows:
        kind = r["facility_type"]
        previous = Decimal(r["co2_capture_capacity_ton_per_week"])
        previous_totals[kind] += previous
        r["province"] = PROVINCE_NAMES.get(r["province"], r["province"])
        capacity = previous
        if kind == "coal_power":
            unit = coal_units[r["location_id"]]
            unit_id = unit["GEM_unit_phase_ID"]
            archived_mw = Decimal(unit["Capacity__MW_"])
            factor = fraction(unit["Capacity_factor"])
            if archived_mw != Decimal(r["capacity_original"]) or unit["Plant_name"] != r["location_name"]:
                raise ValueError(f"Unit identity mismatch for {unit_id}")
            mw = archived_mw
            if unit_id in YANG_UNITS:
                if unit["Plant_name"] != "Yangliuqing power station":
                    raise ValueError(f"Unexpected identity for regulatory override {unit_id}")
                mw = Decimal(300)
                reidentified.add(unit_id)
            capacity = mw * hours * factor * emission * capture
            r["capacity_original"] = numeric_string(mw)
            r["capacity_factor"] = numeric_string(factor)
            r["co2_capture_capacity_ton_per_week"] = numeric_string(capacity)
            r["total_capture_cost_yuan_per_week"] = numeric_string(capacity * Decimal(r["capture_cost_yuan_per_ton"]))
            unit_records.append([unit_id, r["location_id"], unit["Plant_name"], unit["Unit_name"],
                                 str(archived_mw), str(mw), numeric_string(factor), numeric_string(capacity)])
        totals[kind] += capacity
        if distance_from_beijing(r) <= 100:
            regional.append({"source": f"co2_source_{len(regional)+1}", "location_id": r["location_id"],
                             "plant": r["location_name"], "kind": kind, "latitude": float(r["latitude"]),
                             "longitude": float(r["longitude"]), "price_cny_t": float(r["capture_cost_yuan_per_ton"]),
                             "previous_t_week": float(previous), "corrected_t_week": float(capacity)})
    if reidentified != YANG_UNITS or len(coal_units) != 3146 or len(regional) != 31:
        raise ValueError("The source snapshot does not match the accession in the paper")
    if any(r["corrected_t_week"] > r["previous_t_week"] + 1e-6 for r in regional):
        raise ValueError("A regional limit increased; the archived global lower bounds require a new proof")
    with (output / "co2_capture_sources.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fields)
        writer.writeheader()
        writer.writerows(rows)
    with (output / "coal_unit_inputs.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["GEM_unit_phase_ID","location_id","plant","unit","archive_MW","applied_MW","capacity_factor","weekly_ceiling_t"])
        writer.writerows(unit_records)
    record = {"base_commit": BASE_COMMIT, "regulatory_source": REGULATOR, "scope": "National inventory and the archived Beijing 100-km industrial CO2 screen",
              "unit_count": len(unit_records), "nameplate_overrides": sorted(YANG_UNITS), "hours_per_week": float(hours),
              "emission_t_per_mwh": float(emission), "capture_fraction": float(capture),
              "previous_Mt_week": {k: float(v/10**6) for k, v in previous_totals.items()},
              "corrected_Mt_week": {k: float(v/10**6) for k, v in totals.items()},
              "sha256": {"unit_snapshot": digest(raw), "previous_inventory": digest(original), "configuration": digest(configuration),
                         "corrected_inventory": digest(output / "co2_capture_sources.csv")},
              "regional_sources": regional}
    (output / "capture_input_checks.json").write_text(json.dumps(record, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    return record


if __name__ == "__main__":
    args = argparse.ArgumentParser()
    args.add_argument("--raw-coal", type=Path, required=True)
    args.add_argument("--old-inventory", type=Path, required=True)
    args.add_argument("--configuration", type=Path, required=True)
    args.add_argument("--output", type=Path, required=True)
    options = args.parse_args()
    report = build(options.raw_coal, options.old_inventory, options.configuration, options.output)
    print("Corrected weekly ceilings (Mt CO2)", report["corrected_Mt_week"])
