import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--revision', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    revision = args.revision.resolve()
    archive = revision.parent
    derived = revision / 'demand_cases/derived'
    sources = json.loads((revision / 'source_map.json').read_text(encoding='utf-8'))['sources']
    for row in sources:
        assert sha(archive / row['path_from_archive_root']) == row['sha256'], row['path_from_archive_root']
    manifest = json.loads((derived / 'manifest.json').read_text(encoding='utf-8'))
    for row in manifest['files']:
        assert sha(derived / row['path']) == row['sha256'], row['path']
    summary = json.loads((derived / 'summary.json').read_text(encoding='utf-8'))
    assert sha(derived / 'manifest.json') == summary['manifest_sha256']
    source_by_role = {row['source_role_index']: archive / row['path_from_archive_root'] for row in sources}
    raw = pd.read_excel(source_by_role[0])
    cases = pd.read_csv(derived / 'case_values.csv', float_precision='round_trip')
    saved = pd.read_excel(source_by_role[1])
    source_records = pd.read_csv(derived / 'case_source_records.csv.gz', float_precision='round_trip')
    assert len(raw) == len(source_records) == 28967 and len(cases) == len(saved) == 24
    valid = raw.total_fuel_kg.notna()
    assert int(valid.sum()) == 28852 and int((~valid).sum()) == 115
    assert raw.loc[~valid, 'flight_date'].isna().all()
    keys = ['departure_airport_name', 'week_number']
    joined = cases.merge(saved[keys + ['weekly_total_fuel_kg_total']], on=keys, validate='one_to_one', suffixes=('', '_original'))
    assert np.array_equal(joined.weekly_total_fuel_kg_total, joined.weekly_total_fuel_kg_total_original)
    airport = raw['起飞机场'].map({'首都机场': '北京', '滨海机场': '天津'})
    for row in cases.to_dict('records'):
        selected = valid & airport.eq(row['departure_airport_name']) & raw.flight_date.eq(row['source_month_label'])
        assert int(selected.sum()) == row['valid_fuel_record_count']
        assert np.isclose(raw.loc[selected, 'total_fuel_kg'].sum(), row['weekly_total_fuel_kg_total'], rtol=0, atol=1e-6)
    mapping = pd.read_csv(derived / 'A_B_case_mapping.csv', float_precision='round_trip')
    assert len(mapping) == 16
    totals = {}
    for label in ('baseline', 'summer'):
        inputs = revision / 'demand_cases/model_inputs' / label
        frame = pd.read_csv(inputs / 'airport_input.csv', float_precision='round_trip')
        for name, expected in summary['A_B'][label]['input_files_sha256'].items():
            assert sha(inputs / name) == expected, (label, name)
        selected = mapping[mapping.schedule.eq(label)]
        assert len(selected) == len(frame) == 8
        for row in frame.to_dict('records'):
            matching = selected[selected.model_airport.eq(row['departure_airport_name']) & selected.model_week_number.eq(row['week_number'])]
            assert len(matching) == 1 and float(matching.saved_fuel_kg.iloc[0]) == row['weekly_total_fuel_kg_total']
        totals[label] = float(frame.weekly_total_fuel_kg_total.sum())
        assert totals[label] == summary['A_B'][label]['demand_kg']
    records = json.loads((derived / 'result_preservation.json').read_text(encoding='utf-8'))['runs']
    frozen = json.loads((archive / 'revision_20261017/revision_manifest.json').read_text(encoding='utf-8'))['runs']
    frozen_sha = {(run['scenario'], run['label']): run['summary_sha256'] for run in frozen}
    assert len(records) == len(frozen_sha) == 18
    for row in records:
        expected = frozen_sha[(row['scenario'], row['label'])]
        source = revision / 'demand_cases/reference_results' / row['scenario'] / row['label'] / 'summary.json'
        assert sha(source) == row['summary_sha256'] == expected
    result = {'passed': True, 'retained_case_values': len(cases), 'source_records': len(raw),
              'valid_fuel_records': int(valid.sum()), 'selected_model_entries': len(mapping),
              'demand_kg': totals, 'unchanged_result_summaries': len(records),
              'model_inputs_changed': False, 'optimization_run': False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
