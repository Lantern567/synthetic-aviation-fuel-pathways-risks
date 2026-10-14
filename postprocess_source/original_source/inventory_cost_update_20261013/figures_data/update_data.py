import copy
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
WORK = HERE.parents[1]
SOURCE = WORK / 'submission_final_20261012/data_stage'
STAGE = HERE / 'data_stage'
OLD_FIG = WORK / 'revision_20261007/figures_cost'
VIZ = WORK / 'corrected_runs_20261006/project/products/supply_chain_optimization/visualization'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    result.__file__ = str(HERE / (name + '.py'))
    return result


def update_csv(relative, transform):
    path = STAGE / relative
    with path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        columns, rows = reader.fieldnames, list(reader)
    before = copy.deepcopy(rows)
    transform(rows)
    if rows != before:
        with path.open('w', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)


def main():
    assert STAGE.resolve().parent == HERE.resolve()
    source_hashes = {str(p.relative_to(SOURCE)).replace('\\', '/'): sha(p)
                     for p in SOURCE.rglob('*') if p.is_file()}
    shutil.copytree(SOURCE, STAGE, dirs_exist_ok=True)
    records = STAGE / 'figure_data/normalized_pathway_records'
    old = read_json(records / 'GTL-BH_complete_solution.json')
    new = copy.deepcopy(old)
    keys = ['storage_operation_cost', 'h2_storage_operation']
    delta_total = 2 * sum(old[k] for k in keys)
    denominator = old['total_cost_excluding_shortage'] / old['lifecycle_levelized_cost_excluding_shortage_per_kg']
    delta_unit = delta_total / denominator
    assert np.isclose(delta_unit, 0.06509024900796437, rtol=0, atol=1e-13)
    for key in keys:
        new[key] = old[key] * 3
        new['cost_breakdown'][key] = old['cost_breakdown'][key] * 3
    for key in ['total_operation_cost', 'total_cost_excluding_shortage', 'objective_value_lifecycle_total']:
        new[key] = old[key] + delta_total
    new['source_cost_breakdown_raw'] = copy.deepcopy(old['cost_breakdown_raw'])
    new['source_solver_objective'] = old['objective_value_lifecycle_total']
    for key in keys + ['total_operation_cost', 'total_cost_excluding_shortage']:
        new['cost_breakdown_raw'][key] = new[key]
    for key in ['lifecycle_levelized_cost_per_kg', 'lifecycle_levelized_cost_excluding_shortage_per_kg']:
        new[key] = old[key] + delta_unit
    new['annual_levelized_cost_per_kg'] = new['objective_value_lifecycle_total'] / old['lifecycle_total_production_kg']
    new['levelized_cost_margin_or_violation'] = new['levelized_cost_threshold'] - new['lifecycle_levelized_cost_excluding_shortage_per_kg']
    new['cost_accounting'] = {
        'scope': 'Archived facility design and dispatch; SAF and hydrogen inventory operating charges use half the sum of site-specific peak inventories as the average-stock proxy and 672 represented hours.',
        'inventory_periods': 224, 'period_hours': 3, 'inventory_hours': 672,
        'inventory_proxy': 'peak inventory / 2',
        'ledger': 'cost_breakdown_raw',
        'reported_unit_cost_field': 'lifecycle_levelized_cost_excluding_shortage_per_kg',
        'no_new_optimization': True,
        'source_solver_objective_cny': old['objective_value_lifecycle_total'],
        'discounted_actual_production_kg': denominator,
        'source_cost_breakdown': 'source_cost_breakdown_raw',
        'objective_value_lifecycle_total_scope': 'Cost accounting for the retained archived design, using the three-hour inventory time basis',
        'unchanged_scope': 'Production, supply coverage, capacities, siting, dispatch, transport and carbon accounts'
    }
    write_json(records / 'GTL-BH_complete_solution.json', new)
    box = module('inventory_learning', VIZ / 'quadrant_chart_box_visualization.py')
    polar = module('inventory_categories', VIZ / 'pareto_three_breakdown_visualization.py')
    assumptions = read_json(STAGE / 'figure_data/learning_assumptions.json')
    box.FT_SCENARIOS = set(assumptions['FT_learning_group'])
    old_projection = box.compute_lcoe_projection(old, 'GTL-BH')
    projection = box.compute_lcoe_projection(new, 'GTL-BH')
    assert np.allclose(projection - old_projection, delta_unit, rtol=0, atol=1e-12)
    assert all(box.COST_MAP.get(key, 'fixed') == 'fixed' for key in keys)
    prefix = 'figure_data/figures_cost/'

    def baseline_rows(rows):
        for row in rows:
            if row.get('scenario') == 'GTL-BH':
                row['cost_per_kg_excluding_shortage'] = str(new['lifecycle_levelized_cost_excluding_shortage_per_kg'])
    update_csv('archived_comparator_metrics.csv', baseline_rows)

    def learning_rows(rows):
        for row in rows:
            if row['scenario'] == 'GTL-BH':
                row['cost_cny_kg'] = str(float(projection[int(row['year'])-2026]))
    update_csv(prefix + 'learning_projections.csv', learning_rows)

    def category_rows(rows):
        for row in rows:
            if row['scenario'] == 'GTL-BH' and row['category'] == 'Storage':
                row['cost_cny_kg'] = str(float(row['cost_cny_kg']) + delta_unit)
    update_csv(prefix + 'learning_categories.csv', category_rows)

    def gap_rows(rows):
        for row in rows:
            if row['Scenario'] == 'GTL-BH':
                for field, value in [('LCOE 2026', projection[0]), ('LCOE 2036', projection[-1]),
                                     ('Gap 2026', projection[0]-8), ('Gap 2036', projection[-1]-8)]:
                    row[field] = str(float(value))
                row['Gap reduction'] = str(float(projection[0]-projection[-1]))
    update_csv(prefix + 'cost_gap_2026_2036.csv', gap_rows)

    def sensitivity_rows(rows):
        total = sum(new['cost_breakdown'].values())
        baseline = new['lifecycle_levelized_cost_excluding_shortage_per_kg']
        for row in rows:
            if row['scenario'] == 'GTL-BH':
                contribution = new['cost_breakdown'][row['component']] / total * baseline
                row['cost_baseline_cny_kg'] = str(baseline)
                row['cost_low_cny_kg'] = str(baseline-.2*contribution)
                row['cost_high_cny_kg'] = str(baseline+.2*contribution)
    update_csv(prefix + 'S24_fixed_design_component_sensitivity.csv', sensitivity_rows)

    def integrated_rows(rows):
        for row in rows:
            if row.get('scenario', row.get('Scenario')) == 'GTL-BH':
                for field in ['lcoe', 'LCOE', 'cost_cny_kg', 'cost_per_kg_excluding_shortage']:
                    if field in row:
                        row[field] = str(new['lifecycle_levelized_cost_excluding_shortage_per_kg'])
                if 'InvestmentShare' in row:
                    row['InvestmentShare'] = str(new['total_investment_cost'] / new['total_cost_excluding_shortage'])
                if 'WorstWeekCostLift' in row:
                    row['WorstWeekCostLift'] = str(float(row['WorstWeekCostLift']) * new['lifecycle_levelized_cost_excluding_shortage_per_kg'] / old['lifecycle_levelized_cost_excluding_shortage_per_kg'])
    update_csv('figure_data/figures_space_time_network_data/scenario_integrated_metrics.csv', integrated_rows)
    update_csv('figure_data/figures_space_time_temporal_data/all_pathway_temporal_metrics.csv', integrated_rows)

    manifest = read_json(records / 'manifest.json')
    manifest['GTL-BH']['scope'] = 'Archived comparator design and dispatch; three-hour inventory cost accounting; outside the independent validation of the twelve COPT solutions'
    manifest['GTL-BH']['cost_component_residual_cny'] = sum(new['cost_breakdown'].values()) - new['total_cost_excluding_shortage']
    manifest['GTL-BH']['normalized_solution_sha256'] = sha(records / 'GTL-BH_complete_solution.json')
    manifest['GTL-BH']['cost_accounting'] = new['cost_accounting']
    write_json(records / 'manifest.json', manifest)

    def mapping_rows(rows):
        for row in rows:
            if row['scenario'] == 'GTL-BH':
                row['independent_validation'] = 'Archived design and dispatch; three-hour inventory cost accounting; outside the twelve-solution validation'
    update_csv('result_version_mapping.csv', mapping_rows)
    verification = read_json(STAGE / 'figure_data/figure_verification.json')
    verification['pathways']['GTL-BH'].update({'cost_2026': float(projection[0]), 'cost_2036': float(projection[-1]),
        'source_scope': manifest['GTL-BH']['scope'], 'cost_accounting': new['cost_accounting']})
    write_json(STAGE / 'figure_data/figure_verification.json', verification)
    readme = STAGE / 'README.txt'
    readme.write_text(readme.read_text(encoding='utf-8') + '\nGTL-BH costs are evaluated for its archived facility design and dispatch, using half the sum of site-specific peak inventories as the average-stock proxy and 672 represented hours. The reported cost is 5.290539354389216 CNY per kg of actual output. source_cost_breakdown_raw and source_solver_objective record the source ledger and solve objective; cost_accounting identifies the ledger used for the reported unit cost and fixed-design learning/sensitivity tables.\n', encoding='utf-8')
    summary = HERE / 'pathway_summary.csv'
    shutil.copy2(OLD_FIG / 'adapted_data/pathway_summary.csv', summary)
    with summary.open(encoding='utf-8', newline='') as stream:
        reader = csv.DictReader(stream)
        columns, rows = reader.fieldnames, list(reader)
    for row in rows:
        if row['scenario'] == 'GTL-BH':
            row['cost_cny_kg'] = str(new['lifecycle_levelized_cost_excluding_shortage_per_kg'])
    with summary.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    storage_keys = polar.CATEGORIES['Storage']['cost_keys']
    before_storage = sum(old['cost_breakdown'].get(k, 0) for k in storage_keys) / sum(old['cost_breakdown'].values()) * old['lifecycle_levelized_cost_excluding_shortage_per_kg']
    after_storage = sum(new['cost_breakdown'].get(k, 0) for k in storage_keys) / sum(new['cost_breakdown'].values()) * new['lifecycle_levelized_cost_excluding_shortage_per_kg']
    impact = {'scenario': 'GTL-BH', 'source_stage': str(SOURCE), 'stage': str(STAGE),
        'old_cost_cny_kg': old['lifecycle_levelized_cost_excluding_shortage_per_kg'],
        'new_cost_cny_kg': new['lifecycle_levelized_cost_excluding_shortage_per_kg'],
        'difference_cny_kg': delta_unit, 'difference_percent': delta_unit / old['lifecycle_levelized_cost_excluding_shortage_per_kg'] * 100,
        'old_storage_cny_kg': before_storage, 'new_storage_cny_kg': after_storage,
        'discounted_actual_production_kg': denominator, 'additional_lifecycle_cost_cny': delta_total,
        'old_2036_cost_cny_kg': float(old_projection[-1]), 'new_2036_cost_cny_kg': float(projection[-1]),
        'annual_learning_increment_cny_kg': [float(x) for x in projection-old_projection],
        'old_inventory_operating_costs': {k: old[k] for k in keys},
        'new_inventory_operating_costs': {k: new[k] for k in keys},
        'unchanged_cost_order': True, 'no_new_optimization': True}
    write_json(HERE / 'cost_impact.json', impact)
    write_json(HERE / 'source_hashes.json', source_hashes)
    write_json(STAGE / 'SHA256.json', {str(p.relative_to(STAGE)).replace('\\', '/'): sha(p)
        for p in sorted(STAGE.rglob('*')) if p.is_file() and p.name != 'SHA256.json'})
    print(json.dumps(impact, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
