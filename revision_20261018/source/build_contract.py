import argparse
import ast
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
import pandas as pd


SCRIPT = Path(__file__).resolve()
HERE = SCRIPT.parent
WORK = HERE.parent
TARGETED = WORK.parent
OLD = TARGETED / 'scientific_revision_20261017'
SOURCES = TARGETED / 'minor_clarifications_20261018/qa/new_review_20261018/demand_sources'
ARCHIVE = OLD / 'archive_repository'
REVISION = ARCHIVE / 'revision_20261017'
COMMIT = '8b4eac762b85bcccf510cba3a61174530d48e849'
parser = argparse.ArgumentParser()
parser.add_argument('--data-dir', type=Path, default=SOURCES)
parser.add_argument('--out', type=Path, default=HERE)
parser.add_argument('--input-root', type=Path, default=OLD / 'pv_inputs/inputs')
parser.add_argument('--resource-pool', type=Path, default=OLD / 'pv_inputs/renewable_12weeks.csv')
parser.add_argument('--lineage', type=Path, default=WORK / 'source_audit/raw_record_lineage_audit.csv.gz')
parser.add_argument('--processing-source-dir', type=Path)
parser.add_argument('--frozen-revision', type=Path, default=REVISION)
parser.add_argument('--results-root', type=Path, default=OLD / 'results')
parser.add_argument('--git-repository', type=Path, default=ARCHIVE)
args = parser.parse_args()
SOURCES = args.data_dir.resolve()
HERE = args.out.resolve()
HERE.mkdir(parents=True, exist_ok=True)
REVISION = args.frozen_revision.resolve()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save_json(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def csv(name, frame):
    frame.to_csv(HERE / name, index=False, encoding='utf-8', float_format=None)


raw_path = SOURCES / 'capital_binhai_airports_data_20250726_123415.xlsx'
twelve_path = SOURCES / 'typical_12weeks_demand_20251129_163442.xlsx'
fiftytwo_path = SOURCES / 'all_airports_weekly_parameters_20250726_142747.xlsx'
resource_path = args.resource_pool.resolve()
lineage_path = args.lineage.resolve()
project = OLD / 'runtime/compute/project/products/aviation_fuel_analysis/resource_flight_data_process'
extraction_path = project / 'src/extract_typical_weeks_data.py'
resource_builder = OLD / 'runtime/compute/build_verified_inputs.py'
month_builder = SOURCES / 'parallel_flight_processor.py'
data_loader = project / 'src/weekly_analysis/data_loader.py'
legacy_calculator = project / 'src/weekly_analysis/final_correct_calculator.py'
if args.processing_source_dir is not None:
    extraction_path = args.processing_source_dir / 'extract_typical_weeks_data.py'
    resource_builder = args.processing_source_dir / 'build_verified_inputs.py'
    month_builder = args.processing_source_dir / 'parallel_flight_processor.py'
    data_loader = args.processing_source_dir / 'data_loader.py'
    legacy_calculator = args.processing_source_dir / 'final_correct_calculator.py'
paths = [raw_path, twelve_path, fiftytwo_path, resource_path, lineage_path, extraction_path, resource_builder,
         month_builder, data_loader, legacy_calculator,
         SOURCES / 'final_analysis_summary_20250726_142747.txt', REVISION / 'revision_manifest.json', REVISION / 'SHA256SUMS.json']
before = {str(path): sha(path) for path in paths}
for name in ['revision_manifest.json', 'SHA256SUMS.json']:
    committed = subprocess.run(['git', '-C', str(args.git_repository), 'cat-file', 'blob', f'{COMMIT}:revision_20261017/{name}'], check=True, capture_output=True).stdout
    assert committed == (REVISION / name).read_bytes(), name

tree = ast.parse(extraction_path.read_text(encoding='utf-8-sig'))
declared = [ast.literal_eval(node.value) for node in ast.walk(tree) if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Attribute) and target.attr == 'typical_weeks' for target in node.targets)]
assert len(declared) == 1
storage_labels = declared[0]
resources = pd.read_csv(resource_path, usecols=['source_week', 'source_period'])
resource_labels = sorted(int(value) for value in resources.source_week.unique())
assert resource_labels == storage_labels and len(storage_labels) == 12
resource_tree = ast.parse(resource_builder.read_text(encoding='utf-8-sig'))
declared_resource = [ast.literal_eval(node.value) for node in ast.walk(resource_tree) if isinstance(node, ast.Assign)
                     and any(isinstance(target, ast.Name) and target.id == 'weeks' for target in node.targets)]
assert declared_resource == [resource_labels]

raw = pd.read_excel(raw_path)
raw.insert(0, 'filtered_calculated_excel_row', raw.index + 2)
lineage = pd.read_csv(lineage_path, usecols=['filtered_calculated_excel_row', 'raw_2024_excel_row'])
raw = raw.merge(lineage, on='filtered_calculated_excel_row', how='left', validate='one_to_one')
assert raw.raw_2024_excel_row.notna().all() and len(raw) == 28967
assert raw.loc[raw.flight_date.notna(), 'flight_date'].eq(raw.loc[raw.flight_date.notna(), 'flight_year_month']).all()
raw['source_bucket_date'] = pd.to_datetime(raw.flight_date, format='%Y-%m')
raw['original_date'] = pd.to_datetime(raw['日期'])
assert raw.loc[raw.flight_date.notna(), 'flight_date'].eq(raw.loc[raw.flight_date.notna(), 'original_date'].dt.strftime('%Y-%m')).all()
raw['demand_storage_label'] = raw.source_bucket_date.dt.isocalendar().week.astype('Int64')
raw['case_index'] = raw.demand_storage_label.map({label: index for index, label in enumerate(storage_labels)})
raw['model_airport'] = raw['起飞机场'].map({'首都机场': '北京', '滨海机场': '天津'})
assert raw.model_airport.notna().all()
raw['included_in_saved_fuel_sum'] = raw.total_fuel_kg.notna()
assert raw.loc[raw.included_in_saved_fuel_sum, 'total_fuel_kg'].gt(0).all()
assert raw.loc[raw.included_in_saved_fuel_sum, 'case_index'].notna().all()
assert raw.loc[~raw.included_in_saved_fuel_sum, 'case_index'].isna().all()
raw['original_iso_year'] = raw.original_date.dt.isocalendar().year.astype(int)
raw['original_iso_week'] = raw.original_date.dt.isocalendar().week.astype(int)
days = ['一', '二', '三', '四', '五', '六', '日']
raw['original_date_matches_weekday_flag'] = [row[f'周{days[date.weekday()]}班期'] == f'周{days[date.weekday()]}有班期'
    for row, date in zip(raw.to_dict('records'), raw.original_date, strict=True)]

twelve = pd.read_excel(twelve_path)
assert len(twelve) == 24
case_records, date_records = [], []
for row in twelve.to_dict('records'):
    case_index = int(row['week_number']) - 1
    storage = int(row['original_week'])
    assert storage == storage_labels[case_index]
    group = raw[(raw.model_airport == row['departure_airport_name']) & raw.case_index.eq(case_index)]
    original_fuel = float(row['weekly_total_fuel_kg_total'])
    rebuilt = float(group.total_fuel_kg.sum(min_count=1))
    assert np.isclose(original_fuel, rebuilt, rtol=0, atol=1e-7)
    assert int(row['weekly_total_fuel_kg_count']) == int(group.included_in_saved_fuel_sum.sum())
    record = {**row, 'case_index': case_index, 'demand_storage_label': storage,
              'resource_source_week_label': resource_labels[case_index],
              'source_month_label': str(group.flight_date.iloc[0]), 'source_bucket_date': str(group.source_bucket_date.iloc[0].date()),
              'source_record_count': len(group), 'valid_fuel_record_count': int(group.included_in_saved_fuel_sum.sum()),
              'missing_fuel_record_count': int((~group.included_in_saved_fuel_sum).sum()),
              'source_date_count': int(group.original_date.nunique()),
              'source_first_date': str(group.original_date.min().date()), 'source_last_date': str(group.original_date.max().date()),
              'distinct_advertised_flight_numbers': int(group['航班班次'].nunique()),
              'source_fuel_recomposition_kg': rebuilt, 'source_recomposition_error_kg': rebuilt - original_fuel}
    case_records.append(record)
    for date, day in group.groupby('original_date', sort=True):
        date_records.append({'case_index': case_index, 'model_airport': row['departure_airport_name'],
            'demand_storage_label': storage, 'resource_source_week_label': resource_labels[case_index],
            'source_month_label': record['source_month_label'], 'original_date': str(date.date()),
            'original_iso_year': int(day.original_iso_year.iloc[0]), 'original_iso_week': int(day.original_iso_week.iloc[0]),
            'record_count': len(day), 'valid_fuel_record_count': int(day.included_in_saved_fuel_sum.sum()),
            'missing_fuel_record_count': int((~day.included_in_saved_fuel_sum).sum()),
            'known_fuel_kg': float(day.total_fuel_kg.sum(min_count=1)),
            'original_date_matches_weekday_flag_count': int(day.original_date_matches_weekday_flag.sum())})
cases = pd.DataFrame(case_records).sort_values(['departure_airport_name', 'case_index'])
csv('case_values.csv', cases)
csv('case_date_composition.csv', pd.DataFrame(date_records))
raw.to_csv(HERE / 'case_source_records.csv.gz', index=False, encoding='utf-8', compression={'method': 'gzip', 'mtime': 0})
valid = raw[raw.included_in_saved_fuel_sum].copy()
valid.to_csv(HERE / 'valid_sample_records.csv.gz', index=False, encoding='utf-8', compression={'method': 'gzip', 'mtime': 0})

fiftytwo = pd.read_excel(fiftytwo_path, sheet_name='All_Airports')
legacy = []
for row in fiftytwo.to_dict('records'):
    matched = cases[(cases.departure_airport_name == row['departure_airport_name']) & cases.demand_storage_label.eq(int(row['source_week']))]
    assert len(matched) == 1 and float(row['weekly_total_fuel_kg_total']) == float(matched.weekly_total_fuel_kg_total.iloc[0])
    legacy.append({'model_airport': row['departure_airport_name'], 'legacy_storage_slot': int(row['week_number']),
                   'source_case_index': int(matched.case_index.iloc[0]), 'source_storage_label': int(row['source_week']),
                   'saved_direct_bucket_flag': bool(row['has_original_data']),
                   'saved_fuel_kg': float(row['weekly_total_fuel_kg_total']),
                   'description': 'Direct monthly sample bucket' if row['has_original_data'] else 'Nearest populated bucket copied by legacy procedure'})
csv('legacy_52_mapping.csv', pd.DataFrame(legacy))

frozen = json.loads((REVISION / 'revision_manifest.json').read_text(encoding='utf-8'))
checksums = json.loads((REVISION / 'SHA256SUMS.json').read_text(encoding='utf-8'))
byte_rows, selected_rows, input_summary = [], [], {}
for label in ['baseline', 'summer']:
    folder = args.input_root / label
    frame = pd.read_csv(folder / 'airport_input.csv', float_precision='round_trip')
    for name in ['airport_input.csv', 'airport_input.xlsx', 'manifest.json', 'renewable_periods.csv']:
        path = folder / name
        paths.append(path)
        before[str(path)] = sha(path)
        artifact_key = f'artifacts/workspace/work/nexus_targeted_revision/scientific_revision_20261017/pv_inputs/inputs/{label}/{name}'
        if name == 'renewable_periods.csv':
            archived_bytes = subprocess.run(['git', '-C', str(args.git_repository), 'cat-file', 'blob',
                f'{COMMIT}:revision_20261017/{artifact_key}.gz'], check=True, capture_output=True).stdout
            assert hashlib.sha256(archived_bytes).hexdigest() == checksums[artifact_key + '.gz']
            assert hashlib.sha256(gzip.decompress(archived_bytes)).hexdigest() == before[str(path)]
        else:
            assert checksums[artifact_key] == before[str(path)], (label, name)
        matches = sum(any((key == f'{label}/{name}' or key.endswith(f'/{label}/{name}')) and value == before[str(path)]
                          for key, value in item['input_files_sha256'].items()) for item in frozen['runs'])
        byte_rows.append({'schedule': label, 'filename': name, 'sha256': before[str(path)],
                          'matches_frozen_original_input_artifact': True, 'matching_archived_model_input_bindings': matches})
    for row in frame.to_dict('records'):
        match = cases[(cases.departure_airport_name == row['departure_airport_name']) & cases.demand_storage_label.eq(int(row['original_week']))]
        assert len(match) == 1 and float(match.weekly_total_fuel_kg_total.iloc[0]) == float(row['weekly_total_fuel_kg_total'])
        selected_rows.append({'schedule': label, 'model_airport': row['departure_airport_name'],
                              'model_week_index': int(row['week_number']) - 1, 'model_week_number': int(row['week_number']),
                              'case_index': int(match.case_index.iloc[0]), 'demand_storage_label': int(row['original_week']),
                              'resource_source_week_label': int(row['original_week']), 'source_month_label': match.source_month_label.iloc[0],
                              'saved_fuel_kg': float(row['weekly_total_fuel_kg_total'])})
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    assert float(frame.weekly_total_fuel_kg_total.sum()) == float(manifest['demand_kg'])
    input_summary[label] = {'demand_kg': float(manifest['demand_kg']), 'resource_week_labels': manifest['weeks'],
        'case_indices': [storage_labels.index(value) for value in manifest['weeks']],
        'input_files_sha256': {row['filename']: row['sha256'] for row in byte_rows if row['schedule'] == label}}
csv('A_B_case_mapping.csv', pd.DataFrame(selected_rows))
csv('input_byte_preservation.csv', pd.DataFrame(byte_rows))

result_rows = []
for run in frozen['runs']:
    path = args.results_root / run['scenario'] / run['label'] / 'summary.json'
    actual = sha(path)
    assert actual == run['summary_sha256'], (run['scenario'], run['label'])
    result_rows.append({'scenario': run['scenario'], 'label': run['label'], 'summary_sha256': actual, 'matches_frozen_release': True})
save_json('result_preservation.json', {'frozen_commit': COMMIT, 'checked_result_count': len(result_rows), 'passed': True, 'runs': result_rows})
assert all(sha(path) == before[str(path)] for path in paths)
manifest = {'schema_version': 1, 'scope': 'Description of the existing sample-aggregation demand cases; no new model inputs, weights, deduplication, calendar reconstruction, or optimization.',
    'case_index_definition': 'Zero-based position in the existing 12-case extraction list.',
    'demand_storage_label_definition': 'Existing week-number storage key created after month labels were parsed as month-start dates.',
    'resource_source_week_label_definition': 'Source-week block label read from the actual resource input and its execution builder; independent of original flight-record dates.',
    'legacy_52_scope': 'Stored case-copy mapping only; not an observed annual demand series.',
    'source_bucket_rule': 'The saved flight_date field equals flight_year_month (YYYY-MM), grouped by the ISO week of its parsed month-start date; original day-precision dates are retained separately.',
    'source_evidence': [{'filename': path.name, 'source_role_index': index, 'sha256': before[str(path)]} for index, path in enumerate(paths)],
    'frozen_commit': COMMIT, 'model_inputs_changed': False, 'optimization_results_changed': False,
    'files': [{'path': path.name, 'bytes': path.stat().st_size, 'sha256': sha(path)} for path in sorted(HERE.iterdir())
              if path.is_file() and path.name not in ['manifest.json', 'summary.json', 'source_locations.json']]}
save_json('manifest.json', manifest)
save_json('source_locations.json', {'source_locations': [{'source_role_index': index, 'actual_path': str(path.resolve())} for index, path in enumerate(paths)]})
save_json('summary.json', {'schema_version': 1, 'passed': True, 'retained_value_count': len(cases), 'source_record_count': len(raw),
    'valid_fuel_record_count': len(valid), 'missing_fuel_record_count': len(raw) - len(valid),
    'case_indices': list(range(12)), 'source_month_labels': sorted(raw.flight_date.dropna().unique().tolist()),
    'demand_storage_labels': storage_labels, 'resource_source_week_labels': resource_labels,
    'A_B': input_summary, 'retained_result_count': len(result_rows),
    'manifest_sha256': sha(HERE / 'manifest.json'), 'build_source_sha256': sha(SCRIPT),
    'model_inputs_changed': False, 'optimization_results_changed': False})
print(json.dumps(json.loads((HERE / 'summary.json').read_text(encoding='utf-8')), ensure_ascii=False))
