import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def main():
    parser = argparse.ArgumentParser(description='Check the revision archive and reproduce archived summary tables.')
    parser.add_argument('--output', type=Path, default=Path('work/reproduced'))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if os.name == 'nt' and not str(root).startswith('\\\\?\\'):
        root = Path('\\\\?\\' + str(root))
    output = args.output.resolve()
    output.mkdir(parents=True,exist_ok=True)
    manifest = json.loads((root/'SHA256SUMS.json').read_text(encoding='utf-8'))
    for relative,expected in manifest.items():
        actual = hashlib.sha256((root/relative).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f'Archive hash mismatch: {relative}')
    index = json.loads((root/'provenance/archived_output_index.json').read_text(encoding='utf-8'))
    solver_rows = read_csv(root/'supplementary_data/solver_run_evidence.csv')
    if len(solver_rows) != 13 or len({r['scenario'] for r in solver_rows}) != 13:
        raise ValueError('The archive must contain exactly 13 distinct scenario records')
    summary = []
    for row in solver_rows:
        scenario = row['scenario']
        solution = json.loads((root/'archived_outputs'/index[scenario]['solution']).read_text(encoding='utf-8'))
        objective = solution['objective_value_lifecycle_total']
        if not math.isclose(objective,float(row['objective']),rel_tol=1e-10,abs_tol=1e-6):
            raise ValueError(f'Objective association failed: {scenario}')
        if solution['optimization_status'] != int(row['status']):
            raise ValueError(f'Termination association failed: {scenario}')
        if not math.isclose(solution['optimization_time'],float(row['solver_seconds']),rel_tol=0,abs_tol=1e-6):
            raise ValueError(f'Runtime association failed: {scenario}')
        summary.append({'scenario':scenario,
                        'archived_cost_cny_per_kg_excluding_shortage':solution['lifecycle_levelized_cost_excluding_shortage_per_kg'],
                        'annualized_production_kg':solution['annual_production_kg'],
                        'demand_fulfillment_ratio':solution['demand_fulfillment_ratio'],
                        'solver_status':row['status'],'relative_gap_percent':row['relative_gap_percent'],
                        'solver_seconds':row['solver_seconds']})
    mapping = read_csv(root/'supplementary_data/archived_temporal_mapping_check.csv')
    if len(mapping) != 109 or any(r['all_672_match'] != 'True' for r in mapping):
        raise ValueError('Archived resource-window association check failed')
    for name,records in [('pathway_summary.csv',summary),('solver_records.csv',solver_rows)]:
        with (output/name).open('w',encoding='utf-8',newline='') as stream:
            writer = csv.DictWriter(stream,fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(records)
    checks = {'scope':['file integrity','solver-to-output association','temporal indexing'],
              'files_verified':len(manifest),'scenario_records_matched':len(summary),
              'resource_window_records_matched':len(mapping),
              'gap_target_met':sum(r['status']=='2' for r in solver_rows),
              'time_limit_terminations':sum(r['status']=='9' for r in solver_rows),
              'physical_dispatch_feasibility_certified':False,
              'optimization_executed':False}
    (output/'archive_checks.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
    print(json.dumps(checks,indent=2))


if __name__ == '__main__':
    main()
