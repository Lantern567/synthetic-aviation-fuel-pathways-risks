import argparse
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np


def native(path):
    # Windows 深目录使用扩展路径；科学源文件保持原样。
    resolved = path.resolve()
    value = str(resolved)
    return Path('\\\\?\\' + value) if sys.platform == 'win32' and not value.startswith('\\\\?\\') else resolved


HERE = native(Path(__file__).resolve().parent)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def close(actual, expected, label, atol=1e-9):
    assert np.isclose(actual, expected, rtol=1e-12, atol=atol), (label, actual, expected)


def copy_file(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    assert sha(source) == sha(destination)


def original_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def verify_all_site_inventory(data, output):
    # 原始脚本在隔离的真实输入目录中执行，保持源码和计算公式不变。
    workspace = output / 'x'
    base = workspace / 'w/n'
    audit = base / 'inventory_carbon_update_20261013/audit'
    audit.mkdir(parents=True, exist_ok=True)
    snapshot = HERE / 'original_source/inventory_carbon_update_20261013/audit/all_site_inventory.py'
    copy_file(snapshot, audit / snapshot.name)
    copy_file(HERE / 'accounting_reference/unit_corrected_inventory_carbon.json', audit / 'unit_corrected_inventory_carbon.json')
    local_data = workspace / 'Nexus系统提交文件_库存成本修正20261013/Accompanying_Data'
    index = read_json(data / 'figure_data/inventory_records/index.json')
    assert len(index['records']) == 24
    cases = set()
    for record in index['records']:
        relative = Path(record['scenario']) / record['label']
        source = data / 'figure_data/inventory_records' / record['csv']
        assert sha(source) == record['sha256']
        assert sha(data / record['source_summary']) == record['source_summary_sha256']
        raw = base / 'inventory_cost_review_20261012/raw_inventory' / relative
        copy_file(source, raw / f"{record['stock']}_inventory.csv")
        copy_file(data / record['source_summary'], raw / 'summary.json')
        cases.add(relative)
    for relative in cases:
        for name in ['summary.json', 'config.yaml', 'model_parameters.json']:
            copy_file(data / 'runs' / relative / name, local_data / 'runs' / relative / name)
    result = subprocess.run([sys.executable, str(audit / snapshot.name)], cwd=audit,
                            check=True, capture_output=True, text=True, encoding='utf-8')
    (output / 'original_inventory_execution.txt').write_text(result.stdout, encoding='utf-8')
    generated = read_json(audit / 'all_site_inventory_carbon.json')['records']
    assert len(generated) == 12
    by_case = {(r['scenario'], r['label']): r for r in generated}
    reference = read_json(HERE / 'accounting_reference/all_site_inventory_carbon.json')['records']
    for original in reference:
        current = by_case[(original['scenario'], original['label'])]
        assert original['summary_sha256'] == current['summary_sha256']
        for field in ['all_site_corrected_storage_carbon_kg_co2e', 'all_site_corrected_total_carbon_kg_co2e',
                      'all_site_corrected_ci_g_mj', 'storage_electricity_ci_kg_kwh']:
            close(current[field], original[field], (current['scenario'], current['label'], field), atol=1e-5)
        for stock in ['saf', 'h2']:
            assert current[stock]['sha256'] == original[stock]['sha256']
            close(current[stock]['all_site_unit_corrected_carbon_kg_co2e'],
                  original[stock]['all_site_unit_corrected_carbon_kg_co2e'], (current['scenario'], stock), atol=1e-5)
    for row in read_csv(data / 'run_carbon_accounting.csv'):
        computed = by_case[(row['scenario'], row['label'])]
        close(float(row['carbon_intensity_g_mj']), computed['all_site_corrected_ci_g_mj'], (row['scenario'], row['label']))
        close(float(row['storage_emissions_kg']), computed['all_site_corrected_storage_carbon_kg_co2e'], row['scenario'], atol=1e-5)
    return by_case


def main():
    parser = argparse.ArgumentParser(description='Verify delivered fixed-design inventory cost and carbon accounts using original processing sources.')
    parser.add_argument('--data', type=Path, required=True, help='Accompanying_Data directory from the current revision')
    parser.add_argument('--output', type=Path, default=HERE / 'verification_output')
    args = parser.parse_args()
    data, output = native(args.data), native(args.output)
    assert data.is_dir(), data
    assert output != data and data not in output.parents, output
    output.mkdir(parents=True, exist_ok=True)
    source_manifest = read_json(HERE / 'source_manifest.json')
    for record in source_manifest['sources'] + source_manifest['reference_records']:
        assert sha(HERE / record['archive_path']) == record['sha256'], record['archive_path']
    integrity = read_json(data / 'SHA256.json')
    actual = {p.relative_to(data).as_posix() for p in data.rglob('*') if p.is_file() and p.name != 'SHA256.json'}
    assert set(integrity) == actual
    for name, expected in integrity.items():
        assert sha(data / name) == expected, name
    computed_inventory = verify_all_site_inventory(data, output)
    final_ledger = read_json(HERE / 'accounting_reference/final_inventory_carbon_ledger.json')['records']
    final_by_case = {(r['scenario'], r['label']): r for r in final_ledger}
    assert len(final_by_case) == 19
    for case, current in computed_inventory.items():
        close(current['all_site_corrected_ci_g_mj'], final_by_case[case]['final_ci_g_mj'], (case, 'final ledger'))
    processor = original_module(HERE / 'original_source/inventory_carbon_update_20261013/figures_data/update_carbon.py', 'inventory_processor')
    box = original_module(HERE / 'original_source/corrected_runs_20261006/project/products/supply_chain_optimization/visualization/quadrant_chart_box_visualization.py', 'learning_processor')
    polar = original_module(HERE / 'original_source/corrected_runs_20261006/project/products/supply_chain_optimization/visualization/pareto_three_breakdown_visualization.py', 'category_processor')
    assumptions = read_json(data / 'figure_data/learning_assumptions.json')
    box.FT_SCENARIOS = set(assumptions['FT_learning_group'])
    learning_rows = read_csv(data / 'figure_data/figures_cost/learning_projections.csv')
    assert len(learning_rows) == 143
    learning_by_case = {(r['scenario'], int(r['year'])): float(r['cost_cny_kg']) for r in learning_rows}
    category_rows = read_csv(HERE / 'accounting_reference/carbon_categories.csv')
    category_by_case = {(r['scenario'], r['category']): float(r['emissions_kg']) for r in category_rows}
    normalized = data / 'figure_data/normalized_pathway_records'
    manifest = read_json(normalized / 'manifest.json')
    pathway_summary = read_csv(HERE / 'accounting_reference/pathway_summary.csv')
    summary_by_name = {r['scenario']: r for r in pathway_summary}
    checks = []
    for name in manifest:
        solution = read_json(normalized / f'{name}_complete_solution.json')
        carbon = read_json(normalized / f'{name}_carbon_emissions.json')
        source_carbon = carbon.get('source_carbon_breakdown_raw', carbon)
        final = final_by_case[(name, 'baseline')]
        rebuilt = processor.corrected(source_carbon, computed_inventory.get((name, 'baseline')), final)
        for field in ['carbon_intensity_kg', 'carbon_intensity_mj']:
            close(rebuilt[field], carbon[field], (name, field))
        for field, value in rebuilt['detailed'].items():
            close(value, carbon['detailed'][field], (name, field), atol=1e-5)
        close(sum(carbon['detailed'].values()), carbon['by_stage']['total_emissions'], (name, 'carbon ledger sum'), atol=.001)
        close(carbon['by_stage']['total_emissions'] / carbon['total_production_kg'] * 1000 / 43.15,
              carbon['carbon_intensity_mj'], (name, 'carbon denominator'))
        close(sum(solution['cost_breakdown'].values()), solution['cost_breakdown_raw']['total_cost_excluding_shortage'], (name, 'cost ledger sum'), atol=.001)
        close(float(summary_by_name[name]['cost_cny_kg']), solution['lifecycle_levelized_cost_excluding_shortage_per_kg'], (name, 'figure cost'))
        close(float(summary_by_name[name]['carbon_g_mj']), carbon['carbon_intensity_mj'], (name, 'figure carbon'))
        assert sha(normalized / f'{name}_complete_solution.json') == manifest[name]['normalized_solution_sha256']
        assert sha(normalized / f'{name}_carbon_emissions.json') == manifest[name]['normalized_carbon_sha256']
        projection = box.compute_lcoe_projection(solution, name)
        for year, value in zip(assumptions['years'], projection):
            close(value, learning_by_case[(name, year)], (name, year, 'learning projection'))
        categories = polar._aggregate(carbon['detailed'], 'carbon_keys')
        for category, value in categories.items():
            close(value, category_by_case[(name, category)], (name, category, 'carbon category'), atol=1e-5)
        close(sum(categories.values()), sum(max(value, 0) for value in carbon['detailed'].values()), (name, 'positive carbon total'), atol=.001)
        checks.append({'scenario': name, 'cost_cny_kg': solution['lifecycle_levelized_cost_excluding_shortage_per_kg'],
                       'carbon_g_mj': carbon['carbon_intensity_mj'], 'fulfillment_ratio': solution['demand_fulfillment_ratio']})
    assert len(checks) == 13
    old = read_json(HERE / 'accounting_reference/source_GTL-BH_complete_solution.json')
    current = read_json(normalized / 'GTL-BH_complete_solution.json')
    cost_keys = ['storage_operation_cost', 'h2_storage_operation']
    addition = 2 * sum(old[k] for k in cost_keys)
    production = old['total_cost_excluding_shortage'] / old['lifecycle_levelized_cost_excluding_shortage_per_kg']
    close(current['lifecycle_levelized_cost_excluding_shortage_per_kg'],
          old['lifecycle_levelized_cost_excluding_shortage_per_kg'] + addition / production, 'GTL-BH unit cost', atol=1e-13)
    assert current['source_cost_breakdown_raw'] == old['cost_breakdown_raw']
    assert current['source_solver_objective'] == old['objective_value_lifecycle_total']
    for key in cost_keys:
        assert current[key] == old[key] * 3 == current['cost_breakdown'][key] == current['cost_breakdown_raw'][key]
    allowed = set(cost_keys + ['cost_breakdown', 'cost_breakdown_raw', 'total_operation_cost', 'total_cost_excluding_shortage',
                             'objective_value_lifecycle_total', 'lifecycle_levelized_cost_per_kg',
                             'lifecycle_levelized_cost_excluding_shortage_per_kg', 'annual_levelized_cost_per_kg',
                             'levelized_cost_margin_or_violation', 'carbon_emissions'])
    assert all(current[key] == value for key, value in old.items() if key not in allowed), 'GTL-BH design/dispatch preservation'
    assert abs(current['lifecycle_levelized_cost_excluding_shortage_per_kg'] - 5.290539354389216) < 1e-13
    assert round(next(r['cost_cny_kg'] for r in checks if r['scenario'] == 'GTL'), 2) == 6.50
    assert round(next(r['cost_cny_kg'] for r in checks if r['scenario'] == 'CCU-GH-FT'), 2) == 26.06
    result = {'status': 'passed', 'source_files_checked': len(source_manifest['sources']),
              'source_reference_files_checked': len(source_manifest['reference_records']), 'data_files_checked': len(integrity),
              'raw_inventory_csv_count': 24, 'original_inventory_script_runs': 1, 'recomputed_inventory_case_count': len(computed_inventory),
              'normalized_pathway_count': len(checks), 'final_carbon_ledger_case_count': len(final_by_case),
              'learning_projection_rows_checked': len(learning_rows), 'carbon_category_rows_checked': len(category_rows),
              'no_optimization_performed': True, 'gtlbh_design_and_dispatch_preserved': True,
              'gtlbh_inventory_cost_increment_cny_kg': addition / production,
              'pathways': checks}
    (output / 'verification_report.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
