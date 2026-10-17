import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(run_directory, output_path=None):
    run = Path(run_directory).resolve()
    if (run / 'EXPORT_IN_PROGRESS').exists():
        raise ValueError(f'Incomplete run export: {run}')
    hashes = {}

    def read(name, kind):
        path = run / name
        hashes[name] = digest(path)
        if kind == 'csv':
            return pd.read_csv(path)
        if kind == 'yaml':
            return yaml.safe_load(path.read_text(encoding='utf-8'))
        return json.loads(path.read_text(encoding='utf-8'))

    summary = read('summary.json', 'json')
    if not summary['scenario'].startswith('CCU-') or not summary['has_solution'] or not summary['algebraic_validation']['passed']:
        raise ValueError('A real algebraically validated CCU run is required')
    config = read('config.yaml', 'yaml')
    routes = read('ccu_co2_transport_accounting.csv', 'csv')
    inventory = read('ccu_co2_inventory.csv', 'csv')
    exported = read('ccu_co2_transport_parameters.json', 'json')
    if routes.duplicated(['source', 'destination']).any() or inventory.duplicated(['location', 'period']).any():
        raise ValueError('Duplicate CO2 route or stock records')
    numerical = routes[['weekly_contract_kg', 'representative_window_transport_kg', 'pipeline_distance_km']].to_numpy()
    if not np.isfinite(numerical).all() or numerical.min() < -1e-4:
        raise ValueError('Invalid CO2 routes')
    basis = config['basic_parameters']
    weeks = int(basis['time_horizon_weeks'])
    hours = weeks * int(basis['periods_per_week']) * float(basis['hours_per_period'])
    economics = config['economic_parameters']
    years, rate = int(economics['project_lifespan']), float(economics['discount_rate'])
    pv = years if rate == 0 else (1 - (1 + rate) ** (-years)) / rate
    lifecycle = 52 / weeks * pv
    pipeline = config.get('unified_costs', {}).get('co2_transport', {}).get('pipeline', {})
    price = float(pipeline.get('transport_cost_yuan_per_kg_km', .0001))
    carbon = float(config['carbon_emission_parameters']['transportation'].get('co2_pipeline_intensity', .01))
    mass = routes.weekly_contract_kg.to_numpy() * weeks
    distances = routes.pipeline_distance_km.to_numpy()
    same = routes.source.eq(routes.destination).to_numpy()
    expected_cost = float(np.sum(mass * distances * price)) * lifecycle
    expected_carbon = float(np.sum(mass * distances / 100 * carbon))
    storage = config.get('unified_costs', {}).get('co2_storage', {})
    equipment = float(storage.get('equipment_cost_yuan_per_kg', 5))
    hourly = float(storage['storage_cost_yuan_per_kg_per_day']) / 24 if 'storage_cost_yuan_per_kg_per_day' in storage else float(storage.get('operation_cost_yuan_per_kg_hour', .0002083))
    capacity = float(summary['cost_breakdown']['co2_storage_investment']) / equipment
    peak_lower_bound = float(inventory.groupby('location').value.max().sum())
    expected_storage = capacity / 2 * hourly * hours * lifecycle
    residuals = {
        'four_week_mass_kg': float(np.abs(mass - routes.representative_window_transport_kg.to_numpy()).max()),
        'self_supply_distance_km': float(np.abs(distances[same]).max()) if same.any() else 0.0,
        'co2_transport_cost_cny': expected_cost - summary['cost_breakdown']['co2_pipeline_transport_cost'],
        'co2_transport_carbon_kg': expected_carbon - summary['carbon_expressions']['co2_pipeline_transport'],
        'co2_transport_carbon_alias_kg': expected_carbon - summary['carbon_expressions']['co2_transport'],
        'co2_stock_operation_cost_cny': expected_storage - summary['cost_breakdown']['co2_storage_operation'],
        'co2_stock_capacity_shortfall_kg': max(0.0, peak_lower_bound - capacity),
        'export_transport_price_cny_kg_km': price - exported['cost_cny_per_kg_km'],
        'export_transport_carbon_kg_kg_100km': carbon - exported['carbon_kg_co2e_per_kg_100km'],
        'export_represented_hours': hours - exported['storage']['represented_hours'],
    }
    references = {'co2_transport_cost_cny': expected_cost, 'co2_transport_carbon_kg': expected_carbon,
                  'co2_transport_carbon_alias_kg': expected_carbon, 'co2_stock_operation_cost_cny': expected_storage,
                  'co2_stock_capacity_shortfall_kg': capacity}
    checks = {name: {'residual': value, 'tolerance': .0001 + 1e-8 * abs(references.get(name, 0.0)),
                     'passed': bool(np.isfinite(value) and abs(value) <= .0001 + 1e-8 * abs(references.get(name, 0.0)))}
              for name, value in residuals.items()}
    report = {'scenario': summary['scenario'], 'label': summary['label'], 'passed': all(record['passed'] for record in checks.values()),
              'scope': 'Actual weekly CO2 transport quantities, independent configured route price and per-100-km carbon factors; all-hour peak/2 stock operating cost and stock-capacity lower bound. Physical process balances are validated separately.',
              'solution_summary_sha256': hashes['summary.json'], 'input_sha256': hashes,
              'expected': {'co2_pipeline_transport_cost_cny': expected_cost, 'co2_pipeline_transport_kg_co2e': expected_carbon,
                           'co2_stock_operation_cost_cny': expected_storage, 'represented_hours': hours,
                           'cost_charged_inventory_capacity_kg': capacity, 'actual_stock_peak_sum_kg': peak_lower_bound},
              'checks': checks}
    output = Path(output_path) if output_path else run / 'ccu_co2_accounting_validation.json'
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    for name, expected_hash in hashes.items():
        if digest(run / name) != expected_hash:
            raise ValueError(f'Input changed during validation: {name}')
    if not report['passed']:
        raise ValueError(f'CCU CO2 accounting failed: {output}')
    print(json.dumps({'scenario': summary['scenario'], 'label': summary['label'], 'passed': True, 'output': str(output)}, ensure_ascii=False))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    parser.add_argument('--out')
    arguments = parser.parse_args()
    validate(arguments.run, arguments.out)
