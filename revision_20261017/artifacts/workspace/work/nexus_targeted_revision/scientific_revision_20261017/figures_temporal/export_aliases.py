from pathlib import Path
import argparse
import hashlib
import json
import shutil


HERE = Path(__file__).resolve().parent
ALIASES = {30: "h2_saf_2col_3row_by_category", 33: "pareto_temporal_distribution_latest",
           34: "pareto_penalty_comparison_latest", 35: "pareto_penalty_driver_heatmap_latest"}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def export(output):
    verification = output / "temporal_verification.json"
    verified = json.loads(verification.read_text(encoding="utf-8"))
    if verified["full_thirteen_baselines"] is not True or verified["independent_period_metrics_match"] is not True:
        raise ValueError("Official aliases require the complete verified thirteen-baseline figures")
    records = []
    for number, stem in ALIASES.items():
        for suffix in [".png", ".pdf"]:
            source, target = output / (stem + suffix), output / f"Figure_S{number}{suffix}"
            source_hash = digest(source)
            if verified["figure_files"][source.name]["sha256"] != source_hash:
                raise ValueError(f"Temporal figure changed after verification: {source}")
            shutil.copyfile(source, target)
            if digest(target) != source_hash:
                raise ValueError(f"Official figure alias differs from source: {target}")
            records.append({"figure": f"S{number}", "source": source.name, "alias": target.name,
                            "sha256": source_hash, "bytes": source.stat().st_size})
    manifest = {"schema_version": 1, "passed": True, "byte_identical": True,
                "verification_sha256": digest(verification), "script_sha256": digest(Path(__file__)), "aliases": records}
    (output / "official_figure_aliases.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"passed": True, "aliases": len(records), "byte_identical": True}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=HERE / "outputs")
    export(parser.parse_args().out.resolve())
