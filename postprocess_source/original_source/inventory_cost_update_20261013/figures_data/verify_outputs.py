import csv
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
WORK = HERE.parents[1]
ROOT = WORK.parents[1]
SOURCE = WORK / 'submission_final_20261012/data_stage'
STAGE = HERE / 'data_stage'
PACKET = ROOT / 'Nexus系统提交文件_结果段必要修改20261012'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def nondominated(records):
    selected, best = [], float('inf')
    for name, cost, carbon in sorted(records, key=lambda x: (x[2], x[1])):
        if cost < best:
            selected.append(name)
            best = cost
    return selected


source_hashes = read_json(HERE / 'source_hashes.json')
assert all(sha(SOURCE / name) == digest for name, digest in source_hashes.items())
record = 'figure_data/normalized_pathway_records/GTL-BH_complete_solution.json'
old, new = read_json(SOURCE / record), read_json(STAGE / record)
cost_keys = ['storage_operation_cost', 'h2_storage_operation']
delta = 2 * sum(old[key] for key in cost_keys)
mass = old['total_cost_excluding_shortage'] / old['lifecycle_levelized_cost_excluding_shortage_per_kg']
assert np.isclose(new['lifecycle_levelized_cost_excluding_shortage_per_kg'], 5.290539354389216, rtol=0, atol=1e-14)
assert np.isclose(new['total_cost_excluding_shortage'] - old['total_cost_excluding_shortage'], delta, atol=1e-5)
assert new['source_cost_breakdown_raw'] == old['cost_breakdown_raw']
assert new['source_solver_objective'] == old['objective_value_lifecycle_total']
assert new['cost_accounting']['source_solver_objective_cny'] == old['objective_value_lifecycle_total']
assert new['cost_accounting']['ledger'] == 'cost_breakdown_raw'
assert new['cost_accounting']['no_new_optimization'] is True
for key in cost_keys:
    assert new[key] == old[key] * 3 == new['cost_breakdown'][key] == new['cost_breakdown_raw'][key]
for key in ['total_operation_cost', 'total_cost_excluding_shortage']:
    assert new[key] == new['cost_breakdown_raw'][key]
assert abs(sum(new['cost_breakdown'].values()) - new['total_cost_excluding_shortage']) < 1e-3
allowed = set(cost_keys + ['cost_breakdown', 'cost_breakdown_raw', 'total_operation_cost', 'total_cost_excluding_shortage',
    'objective_value_lifecycle_total', 'lifecycle_levelized_cost_per_kg', 'lifecycle_levelized_cost_excluding_shortage_per_kg',
    'annual_levelized_cost_per_kg', 'levelized_cost_margin_or_violation'])
assert all(new[key] == value for key, value in old.items() if key not in allowed)
assert all(new['cost_breakdown'][key] == value for key, value in old['cost_breakdown'].items() if key not in cost_keys)
assert np.isclose(new['annual_levelized_cost_per_kg'], new['objective_value_lifecycle_total']/new['lifecycle_total_production_kg'])

normalized = Path('figure_data/normalized_pathway_records')
carbon_preserved, other_pathways = [], []
before_records, after_records = [], []
for path in sorted((SOURCE / normalized).glob('*_carbon_emissions.json')):
    relative = path.relative_to(SOURCE)
    assert sha(path) == sha(STAGE / relative)
    carbon_preserved.append(path.name)
for path in sorted((SOURCE / normalized).glob('*_complete_solution.json')):
    relative = path.relative_to(SOURCE)
    name = path.name.removesuffix('_complete_solution.json')
    a, b = read_json(path), read_json(STAGE / relative)
    if name != 'GTL-BH':
        assert sha(path) == sha(STAGE / relative)
        other_pathways.append(name)
    carbon = read_json(SOURCE / normalized / f'{name}_carbon_emissions.json')['carbon_intensity_mj']
    before_records.append((name, a['lifecycle_levelized_cost_excluding_shortage_per_kg'], carbon))
    after_records.append((name, b['lifecycle_levelized_cost_excluding_shortage_per_kg'], carbon))
assert [r[0] for r in sorted(before_records, key=lambda x: x[1])] == [r[0] for r in sorted(after_records, key=lambda x: x[1])]
assert nondominated(before_records) == nondominated(after_records)
gtl = read_json(SOURCE / normalized / 'GTL_complete_solution.json')
assert all(gtl.get(key, 0) == 0 for key in cost_keys)

changed_csv = []
for path in SOURCE.rglob('*.csv'):
    relative = path.relative_to(SOURCE)
    if sha(path) == sha(STAGE / relative):
        continue
    a, b = read_csv(path), read_csv(STAGE / relative)
    assert len(a) == len(b), relative
    edits = []
    for index, (old_row, row) in enumerate(zip(a, b)):
        if old_row == row:
            continue
        scenario = row.get('scenario', row.get('Scenario'))
        assert scenario == 'GTL-BH', (relative, index, scenario)
        columns = [key for key in row if row[key] != old_row[key]]
        edits.append({'row': index + 2, 'scenario': scenario, 'columns': columns})
    changed_csv.append({'file': str(relative), 'edits': edits})

learning_path = Path('figure_data/figures_cost/learning_projections.csv')
before_learning, after_learning = read_csv(SOURCE / learning_path), read_csv(STAGE / learning_path)
for a, b in zip(before_learning, after_learning):
    if b['scenario'] == 'GTL-BH':
        assert np.isclose(float(b['cost_cny_kg']) - float(a['cost_cny_kg']), delta/mass, rtol=0, atol=2e-14)
    else:
        assert a == b
category_path = Path('figure_data/figures_cost/learning_categories.csv')
categories = read_csv(STAGE / category_path)
for row in after_learning:
    if row['scenario'] == 'GTL-BH':
        total = sum(float(c['cost_cny_kg']) for c in categories if c['scenario'] == row['scenario'] and c['year'] == row['year'])
        assert np.isclose(total, float(row['cost_cny_kg']), rtol=0, atol=2e-14)

mapping = read_json(HERE / 'image_replacements.json')['image_replacements']
matches = []
for path in PACKET.rglob('*.docx'):
    with ZipFile(path) as document:
        for name in document.namelist():
            if not name.startswith('word/media/'):
                continue
            digest = hashlib.sha256(document.read(name)).hexdigest()
            for item in mapping:
                if digest == item['old_sha256']:
                    matches.append({'document': str(path.relative_to(PACKET)), 'part': name,
                                    'figure': item['figure'], 'old_sha256': digest})
assert {m['figure'] for m in matches} == {m['figure'] for m in mapping}
for item in mapping:
    assert sha(Path(item['new_image'])) == item['new_sha256']
    assert Image.open(item['new_image']).size == Image.open(item['old_image']).size

integrity = read_json(STAGE / 'SHA256.json')
assert all(sha(STAGE / name) == digest for name, digest in integrity.items())
modified = [name for name, digest in source_hashes.items() if sha(STAGE / name) != digest]
result = {'status': 'passed', 'scope': 'GTL-BH inventory operating cost and dependent figures/tables; retained design and dispatch',
    'source_files_unchanged': len(source_hashes), 'other_pathway_json_bytes_preserved': other_pathways,
    'carbon_json_bytes_preserved': carbon_preserved, 'gtl_inventory_operating_cost_zero_and_unchanged': True,
    'raw_and_leaf_ledgers_consistent': True, 'original_raw_and_solver_objective_retained': True,
    'only_gtlbh_csv_rows_modified': changed_csv, 'unchanged_pathway_results': sha(SOURCE/'pathway_results.csv') == sha(STAGE/'pathway_results.csv'),
    'cost_order_preserved': True, 'nondominated_set_preserved': nondominated(after_records),
    'fixed_learning_increment_cny_kg': delta/mass, 'image_replacement_matches': matches,
    'image_replacement_count': len(mapping), 'embed_match_count': len(matches), 'modified_data_files': modified,
    'stage_integrity_manifest_passed': True, 'image_dimensions_preserved': True, 'new_optimization_performed': False}
dump(HERE / 'data_verification.json', result)
print(json.dumps({'status': 'passed', 'modified_data_files': len(modified), 'embed_match_count': len(matches),
                  'nondominated_set': result['nondominated_set_preserved']}, ensure_ascii=False))
