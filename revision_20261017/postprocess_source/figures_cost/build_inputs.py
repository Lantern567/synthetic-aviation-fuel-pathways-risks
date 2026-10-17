import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


HERE = Path(__file__).resolve().parent
REVISION = HERE.parent
WORKSPACE = HERE.parents[3]
PUBLISHED = WORKSPACE / 'Nexus系统提交文件_代码归档同步20261015/Accompanying_Data/figure_data'
BASELINES = ['CTL', 'CTL-BH', 'GTL-GH', 'GTL', 'GTL-BH', 'CCU-GH-MTJ', 'CCU-GH-FT',
             'CCU-BH-MTJ', 'CCU-BH-FT', 'DAC-GH-MTJ', 'DAC-GH-FT', 'DAC-BH-MTJ', 'DAC-BH-FT']
PAIRED = ['CTL', 'GTL-GH', 'CCU-GH-FT', 'CCU-GH-MTJ', 'DAC-GH-FT', 'DAC-GH-MTJ']
CASES = [(scenario, 'baseline') for scenario in BASELINES if scenario != 'GTL'] + [(scenario, 'summer_fixed') for scenario in PAIRED]
TEMPLATE_ROOT = REVISION.parent
VIZ = TEMPLATE_ROOT / 'corrected_runs_20261006/project/products/supply_chain_optimization/visualization'
TEMPLATES = {
    'quadrant': VIZ / 'quadrant_chart_box_visualization.py',
    'polar': VIZ / 'pareto_three_breakdown_visualization.py',
    'lollipop': TEMPLATE_ROOT / 'reviewer_edits/figure_sources/panel_b_plot.py',
    'breakdown': TEMPLATE_ROOT / 'corrected_runs_20261006/project/appendix_saf_workspace/scripts/pareto_three_breakdown_visualization.py',
    'sensitivity': TEMPLATE_ROOT / 'revision_20261007/figures_cost/sensitivity_visualizer_original.py',
    'stitch': TEMPLATE_ROOT / 'revision_20261007/figures_cost/compose_learning_panels.py',
}
OLD_GTL_CONFIG = TEMPLATE_ROOT / 'github_archive/repository/model_source/shared/data/NaturalGasSupplyChainOptimizer_config_one_step.yaml'
OLD_GTL_CORE = TEMPLATE_ROOT / 'github_archive/repository/model_source/products/supply_chain_optimization/natural_gas_supply_chain_optimization/src/core/natural_gas_optimization_model_one_step.py'
SENSITIVITY_REGISTRY = TEMPLATE_ROOT / 'github_archive/repository/model_source/products/supply_chain_optimization/sensitivity_analysis/scenario_registry.py'
PROCESSOR = REVISION / 'postprocess/update_accounts.py'


def configure_sources(path):
    global PUBLISHED, OLD_GTL_CONFIG, OLD_GTL_CORE, SENSITIVITY_REGISTRY, PROCESSOR
    configuration = read_json(path)
    base = path.resolve().parent
    PUBLISHED = (base / configuration['published_root']).resolve()
    TEMPLATES.clear()
    TEMPLATES.update({name: (base / relative).resolve() for name, relative in configuration['templates'].items()})
    OLD_GTL_CONFIG = (base / configuration['old_gtl_config']).resolve()
    OLD_GTL_CORE = (base / configuration['old_gtl_core']).resolve()
    SENSITIVITY_REGISTRY = (base / configuration['sensitivity_registry']).resolve()
    PROCESSOR = (base / configuration['processor']).resolve()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def close(actual, expected, name, atol=1e-5):
    if not np.isfinite(actual) or not np.isfinite(expected) or not np.isclose(actual, expected, rtol=1e-8, atol=atol):
        raise ValueError(f'{name}: {actual} != {expected}')


def input_paths(results, accounts):
    for scenario, label in CASES:
        run, accounted = results / scenario / label, accounts / scenario / label
        for name in ['summary.json', 'config.yaml', 'model_parameters.json', 'saf_production.csv', 'h2_production.csv']:
            yield run / name
        for name in validation_paths(scenario):
            yield run / name
        if scenario.startswith('DAC-'):
            yield run / 'dac_co2_supply.csv'
        for name in ['accounts.json', 'normalized_complete_solution.json', 'normalized_carbon_emissions.json', 'SHA256.json']:
            yield accounted / name
    for path in TEMPLATES.values():
        yield path
    yield PUBLISHED / 'learning_assumptions.json'
    yield PUBLISHED / 'normalized_pathway_records/GTL_complete_solution.json'
    yield PUBLISHED / 'normalized_pathway_records/GTL_carbon_emissions.json'
    yield HERE / 'carbon_sensitivity_assumptions.json'
    yield OLD_GTL_CONFIG
    yield OLD_GTL_CORE
    yield SENSITIVITY_REGISTRY


def validation_paths(scenario):
    paths = ['byproduct_physical_validation.json' if '-BH' in scenario else 'physical_validation.json',
             'independent_hydrogen_transport/hydrogen_transport_validation.json',
             'independent_inventory_cost/inventory_cost_validation.json']
    if scenario.startswith('DAC-'):
        paths.append('independent_co2/co2_validation.json')
    if scenario.startswith('CCU-'):
        paths.append('ccu_co2_accounting_validation.json')
    if scenario == 'GTL-BH':
        paths.append('extended_natural_gas_validation.json')
    return paths


def collect(results, accounts):
    missing = [str(path.resolve()) for path in input_paths(results, accounts) if not path.is_file()]
    if missing:
        raise FileNotFoundError('Missing verified figure inputs:\n' + '\n'.join(missing))
    tracked, solutions, carbons, account_records, run_directories = [], {}, {}, {}, {}

    def track(path, role, scenario=None, label=None):
        tracked.append({'path': str(path.resolve()), 'role': role, 'scenario': scenario, 'label': label,
                        'bytes': path.stat().st_size, 'sha256': digest(path)})

    processor = PROCESSOR
    for scenario, label in CASES:
        run, account_dir = results / scenario / label, accounts / scenario / label
        if (run / 'EXPORT_IN_PROGRESS').exists():
            raise ValueError(f'Incomplete export: {run}')
        summary = read_json(run / 'summary.json')
        account = read_json(account_dir / 'accounts.json')
        hashes = read_json(account_dir / 'SHA256.json')
        source_hash = digest(run / 'summary.json')
        if not summary['has_solution'] or not summary['algebraic_validation']['passed'] or not 0 <= summary['gap'] <= .01:
            raise ValueError(f'Unaccepted real result: {scenario}/{label}')
        if (summary['scenario'], summary['label']) != (scenario, label) or (account['scenario'], account['label']) != (scenario, label):
            raise ValueError(f'Case identity mismatch: {scenario}/{label}')
        if account['schema_version'] != 1 or account['checks']['passed'] is not True or account['source_summary_sha256'] != source_hash:
            raise ValueError(f'Unverified accounts: {scenario}/{label}')
        if account['processor_sha256'] != digest(processor):
            raise ValueError(f'Accounts require current processor: {scenario}/{label}')
        if account['final_cost'].get('inventory_hours_applied_in_optimization') is not True:
            raise ValueError(f'Inventory hours absent from optimization: {scenario}/{label}')
        for name in validation_paths(scenario):
            path = run / name
            report = read_json(path)
            summary_hashes = [value for key, value in report.get('input_sha256', {}).items()
                              if key == 'summary.json' or key.endswith('/summary.json') or key.endswith('\\summary.json')]
            if report.get('passed') is not True or (report.get('solution_summary_sha256') != source_hash and summary_hashes != [source_hash]):
                raise ValueError(f'Independent validation does not bind this source: {path}')
            track(path, 'independent_validation', scenario, label)
        for name, expected in account['source_hashes'].items():
            if digest(run / name) != expected:
                raise ValueError(f'Account source changed: {run / name}')
        for name, expected in hashes.items():
            if digest(account_dir / name) != expected:
                raise ValueError(f'Account output changed: {account_dir / name}')
        solution = read_json(account_dir / 'normalized_complete_solution.json')
        carbon = read_json(account_dir / 'normalized_carbon_emissions.json')
        close(solution['lifecycle_levelized_cost_excluding_shortage_per_kg'], account['final_cost']['unit_cost_cny_kg'], 'normalized cost')
        close(carbon['carbon_intensity_mj'], account['final_carbon']['intensity_g_mj'], 'normalized carbon')
        close(sum(solution['cost_breakdown'].values()), account['final_cost']['aggregates']['total_cost_excluding_shortage'], 'cost leaves', atol=.02)
        close(sum(carbon['detailed'].values()), account['final_carbon']['aggregates']['total_emissions'], 'carbon leaves')
        solutions[scenario, label], carbons[scenario, label] = solution, carbon
        account_records[scenario, label], run_directories[scenario, label] = account, run
        for path in [run / name for name in ['summary.json', 'config.yaml', 'model_parameters.json', 'saf_production.csv', 'h2_production.csv']]:
            track(path, 'new_real_run', scenario, label)
        for path in [account_dir / name for name in ['accounts.json', 'normalized_complete_solution.json', 'normalized_carbon_emissions.json', 'SHA256.json']]:
            track(path, 'new_final_accounts', scenario, label)
        if scenario.startswith('DAC-'):
            track(run / 'dac_co2_supply.csv', 'actual_capture_for_fixed_design_repricing', scenario, label)
    for kind, store, name in [('solution', solutions, 'GTL_complete_solution.json'), ('carbon', carbons, 'GTL_carbon_emissions.json')]:
        path = PUBLISHED / 'normalized_pathway_records' / name
        store['GTL', 'baseline'] = read_json(path)
        track(path, 'preserved_original_GTL_' + kind, 'GTL', 'baseline')
    assumptions_path = PUBLISHED / 'learning_assumptions.json'
    assumptions = read_json(assumptions_path)
    track(assumptions_path, 'existing_learning_assumptions')
    for path in TEMPLATES.values():
        track(path, 'read_only_plot_template')
    track(processor, 'final_accounts_processor')
    for source in [OLD_GTL_CONFIG, OLD_GTL_CORE, SENSITIVITY_REGISTRY]:
        track(source, 'original_GTL_and_sensitivity_parameter_source')
    return solutions, carbons, account_records, run_directories, assumptions, tracked


def learning_data(solutions, assumptions, categories):
    totals, detailed = [], []
    years = assumptions['years']
    for (scenario, label), solution in solutions.items():
        if label != 'baseline':
            continue
        costs = solution['cost_breakdown']
        total, baseline = sum(costs.values()), solution['lifecycle_levelized_cost_excluding_shortage_per_kg']
        values = {category: np.zeros(len(years)) for category in categories}
        for key, amount in costs.items():
            category = next((name for name, spec in categories.items() if key in spec['cost']), None)
            if category is None:
                if abs(amount) > 1e-5:
                    raise ValueError(f'Unmapped learning component: {(scenario, key, amount)}')
                continue
            group = assumptions['mapping'].get(key, 'fixed')
            if group == 'synthesis':
                group = 'synthesis_ft' if scenario in assumptions['FT_learning_group'] else 'synthesis_mtj'
            values[category] += amount / total * baseline * np.asarray(assumptions['factors'][group])
        trajectory = sum(values.values())
        close(float(trajectory[0]), baseline, scenario + ' learning baseline')
        for year, value in zip(years, trajectory):
            totals.append({'scenario': scenario, 'year': year, 'cost_cny_kg': value,
                           'fulfillment_ratio': solution['demand_fulfillment_ratio'],
                           'scope': 'Fixed production assets, dispatch, output and demand service; existing component cost factors'})
        for category, trajectory in values.items():
            for year, value in zip(years, trajectory):
                detailed.append({'scenario': scenario, 'category': category, 'year': year, 'cost_cny_kg': value})
    return pd.DataFrame(totals), pd.DataFrame(detailed)


def sensitivity_data(solutions, accounts, directories):
    scenario = 'CCU-GH-MTJ'
    run, account, solution = directories[scenario, 'baseline'], accounts[scenario, 'baseline'], solutions[scenario, 'baseline']
    config = yaml.safe_load((run / 'config.yaml').read_text(encoding='utf-8'))
    parameters = read_json(run / 'model_parameters.json')
    fuel, hydrogen = pd.read_csv(run / 'saf_production.csv'), pd.read_csv(run / 'h2_production.csv')
    fuel['location_type'] = fuel.location.map({name: record['type'] for name, record in parameters['locations'].items()})
    if fuel.location_type.isna().any():
        raise ValueError('Missing CCU-GH-MTJ production site type')
    electricity = config['cost_parameters']['renewable_energy']
    energy_by_technology = {name: record['energy_consumption_kwh_per_kg_saf'] for name, record in config['technologies'].items() if 'energy_consumption_kwh_per_kg_saf' in record}
    fuel['synthesis_kwh'] = fuel.value * fuel.technology.map(energy_by_technology)
    if not np.isfinite(fuel.synthesis_kwh).all():
        raise ValueError('Missing configured synthesis electricity coefficient')
    on_grid = ~fuel.location_type.isin(['solar_plant', 'wind_farm'])
    grid_kwh = float(fuel.loc[on_grid, 'synthesis_kwh'].sum())
    renewable_kwh = float(fuel.loc[~on_grid, 'synthesis_kwh'].sum())
    denominator = account['production']['discounted_production_kg']
    mass = account['production']['production_kg']
    base_cost = account['final_cost']['unit_cost_cny_kg']
    base_grid = float(electricity['grid_electricity_price_yuan_per_kwh'])
    base_capex = float(config['equipment_raw_costs']['electrolyzer']['capex_raw'])
    reconstructed_power = (float(hydrogen.value.sum()) * parameters['costs']['electrolysis_power_consumption'] * parameters['costs']['renewable_electricity_cost_yuan_per_mwh'] / 1000 + renewable_kwh * float(electricity['wind_power_price_yuan_per_kwh']) + grid_kwh * base_grid) / mass
    close(reconstructed_power, account['final_cost']['components']['electricity_cost'] / denominator, 'S22 real electricity ledger', atol=1e-6)
    capex_slope = account['final_cost']['components']['electrolyzer_investment_cost'] / denominator / base_capex
    grid_slope = grid_kwh / mass
    grid_rows = [{'scenario': scenario, 'grid_price_cny_kwh': price, 'electrolyzer_capex_cny_kg_h': capex,
                  'cost_cny_kg': base_cost + grid_slope * (price - base_grid) + capex_slope * (capex - base_capex),
                  'fulfillment_ratio': solution['demand_fulfillment_ratio']}
                 for price in [.25, .35, .50, .60, .80] for capex in [200000, 360000, 500000, 700000, 1000000]]
    dac_rows, dac_checks = [], {}
    for scenario in ['DAC-GH-FT', 'DAC-GH-MTJ', 'DAC-BH-FT', 'DAC-BH-MTJ']:
        run, account = directories[scenario, 'baseline'], accounts[scenario, 'baseline']
        config = yaml.safe_load((run / 'config.yaml').read_text(encoding='utf-8'))
        captured = float(pd.read_csv(run / 'dac_co2_supply.csv').value.sum())
        base_capture = float(config['dac_parameters']['capture_cost_yuan_per_ton'])
        coal = account['production']
        lifecycle = coal['annual_expansion'] * coal['present_value_factor']
        close(captured * base_capture / 1000 * lifecycle, account['final_cost']['components']['dac_capture_cost'], scenario + ' real capture cost', atol=.02)
        slope = captured / 1000 / coal['production_kg']
        for unit_cost in [300, 500, 700, 1000, 1500, 2500, 3500, 4500]:
            dac_rows.append({'scenario': scenario, 'dac_cost_cny_t_co2': unit_cost,
                             'cost_cny_kg': account['final_cost']['unit_cost_cny_kg'] + slope * (unit_cost - base_capture),
                             'fulfillment_ratio': coal['demand_fulfillment_ratio']})
        dac_checks[scenario] = {'captured_co2_kg': captured, 'co2_kg_per_kg_fuel': captured / coal['production_kg'],
                                'baseline_capture_cny_t': base_capture, 'slope_cny_kg_fuel_per_cny_t_co2': slope}
    component_rows = []
    for (scenario, label), solution in solutions.items():
        if label != 'baseline':
            continue
        cost, total = solution['lifecycle_levelized_cost_excluding_shortage_per_kg'], sum(solution['cost_breakdown'].values())
        for key, value in solution['cost_breakdown'].items():
            if value <= 1e-6:
                continue
            contribution = value / total * cost
            component_rows.append({'scenario': scenario, 'component': key, 'cost_low_cny_kg': cost - .2 * contribution,
                                   'cost_baseline_cny_kg': cost, 'cost_high_cny_kg': cost + .2 * contribution,
                                   'component_contribution_cny_kg': contribution, 'multiplier_low': .8, 'multiplier_high': 1.2})
    report = {'scope': 'Exact coefficient repricing of each retained design, dispatch and output; no new optimization',
              'S22': {'grid_synthesis_kwh': grid_kwh, 'grid_price_cny_kwh': base_grid,
                      'nonrenewable_output_kg': float(fuel.loc[on_grid, 'value'].sum()),
                      'production_kg': mass,
                      'nonrenewable_output_share': float(fuel.loc[on_grid, 'value'].sum()) / mass,
                      'electrolyzer_capex_cny_kg_h': base_capex, 'grid_cost_slope': grid_slope, 'capex_cost_slope': capex_slope,
                      'reconstructed_electricity_cny_kg': reconstructed_power}, 'S23': dac_checks}
    return pd.DataFrame(grid_rows), pd.DataFrame(dac_rows), pd.DataFrame(component_rows), report


def carbon_sensitivity_data(solutions, carbons, directories):
    assumptions = read_json(HERE / 'carbon_sensitivity_assumptions.json')
    rows = []
    for (scenario, label), solution in solutions.items():
        if label != 'baseline':
            continue
        carbon = carbons[scenario, label]
        if scenario == 'GTL':
            energy = float(assumptions['archived_GTL_fuel_energy_mj_per_kg'])
        else:
            config = yaml.safe_load((directories[scenario, label] / 'config.yaml').read_text(encoding='utf-8'))
            energy = float(config['carbon_emission_parameters']['benchmarks']['saf_energy_content'])
        mass, baseline = float(carbon['total_production_kg']), float(carbon['carbon_intensity_mj'])
        credit = float(carbon['detailed'].get('co2_utilization_credit', 0))
        if mass <= 0 or energy <= 0 or credit > 1e-6:
            raise ValueError(f'Invalid actual carbon sensitivity inputs: {scenario}')
        combustion = float(assumptions['fuel_carbon_mass_fraction']) * float(assumptions['co2_to_carbon_molar_mass_ratio']) / energy * 1000
        attribution = credit / mass / energy * 1000
        positive = sum(value for name, value in carbon['detailed'].items() if name != 'co2_utilization_credit') / mass / energy * 1000
        close(baseline - attribution, positive, scenario + ' removal of actual capture attribution')
        rows.append({'scenario': scenario, 'baseline_g_mj': baseline,
                     'fulfillment_ratio': float(solution['demand_fulfillment_ratio']),
                     'fuel_carbon_mass_fraction': assumptions['fuel_carbon_mass_fraction'],
                     'co2_to_carbon_molar_mass_ratio': assumptions['co2_to_carbon_molar_mass_ratio'],
                     'fuel_energy_mj_kg': energy, 'production_kg': mass,
                     'combustion_addition_g_mj': combustion,
                     'capture_attribution_kg_co2e': credit, 'capture_attribution_g_mj': attribution,
                     'capture_attribution_removed_addition_g_mj': -attribution,
                     'with_combustion_g_mj': baseline + combustion,
                     'without_capture_attribution_g_mj': baseline - attribution,
                     'with_combustion_without_capture_attribution_g_mj': baseline + combustion - attribution,
                     'scope': 'Retained fuel-composition assumption; actual solution-specific captured-carbon attribution removed once'})
    return pd.DataFrame(rows)


def fossil_sensitivity_data(solutions, accounts, directories):
    historical = yaml.safe_load(OLD_GTL_CONFIG.read_text(encoding='utf-8'))
    reference = solutions['GTL', 'baseline']
    fuel = float(reference['carbon_emissions']['total_production_kg'])
    historical_ratio = float(historical['technologies']['ft_direct_conversion']['ng_consumption_ratio'])
    economics = historical['economic_parameters']
    rate, years = float(economics['discount_rate']), int(economics['project_lifespan'])
    pv = years if rate == 0 else (1 - (1 + rate) ** -years) / rate
    lifecycle = 13 * pv
    close(reference['annual_production_kg'], fuel * 13, 'Preserved GTL annual output')
    close(sum(reference['cost_breakdown'].values()) / (fuel * lifecycle),
          reference['lifecycle_levelized_cost_excluding_shortage_per_kg'], 'Preserved GTL discounted-output cost ledger')
    historical_cost = reference['cost_breakdown']['natural_gas_cost'] / (fuel * lifecycle)
    historical_price = historical_cost / historical_ratio
    close(historical_price, 2.53, 'Preserved GTL effective source-ledger NG price', atol=1e-8)
    cases = {'GTL': {'baseline_cost_cny_kg': reference['lifecycle_levelized_cost_excluding_shortage_per_kg'],
                      'production_kg': fuel, 'ng_consumed_m3': fuel * historical_ratio,
                      'effective_ng_price_cny_m3': historical_price, 'ng_m3_per_kg_fuel': historical_ratio,
                      'natural_gas_cost_cny_kg': historical_cost, 'source': 'Preserved original direct-FT design and source ledger'}}
    scenario = 'GTL-BH'
    run, account = directories[scenario, 'baseline'], accounts[scenario, 'baseline']
    config = yaml.safe_load((run / 'config.yaml').read_text(encoding='utf-8'))
    model = read_json(run / 'model_parameters.json')
    production = pd.read_csv(run / 'saf_production.csv')
    ratios = production.technology.map({name: float(record.get('ng_consumption_ratio', 0)) for name, record in model['technologies'].items()})
    if not np.isfinite(ratios).all() or (ratios < 0).any():
        raise ValueError('Missing or invalid configured GTL-BH NG consumption coefficient')
    gas = float((production.value * ratios).sum())
    allocated = pd.read_csv(run / 'ng_technology_flows.csv')
    routed = production.technology.isin(['pipeline_direct_conversion', 'lng_to_hplant_conversion'])
    close(float(allocated.value.sum()), float((production.loc[routed, 'value'] * ratios[routed]).sum()), 'Actual GTL-BH routed natural-gas procurement', atol=1e-3)
    mass, denominator = account['production']['production_kg'], account['production']['discounted_production_kg']
    lifecycle = denominator / mass
    gas_cost = account['final_cost']['components']['natural_gas_cost']
    effective_price = gas_cost / lifecycle / gas
    close(effective_price, 2.53, 'New GTL-BH effective source-ledger NG price', atol=1e-8)
    close(gas * effective_price * lifecycle, gas_cost, 'New GTL-BH natural-gas cost ledger', atol=.02)
    cases[scenario] = {'baseline_cost_cny_kg': account['final_cost']['unit_cost_cny_kg'],
                       'production_kg': mass, 'ng_consumed_m3': gas, 'routed_ng_procurement_m3': float(allocated.value.sum()),
                       'effective_ng_price_cny_m3': effective_price, 'ng_m3_per_kg_fuel': gas / mass,
                       'natural_gas_cost_cny_kg': gas_cost / denominator, 'source': 'New verified GTL-BH design, actual dispatch and NG procurement'}
    gas_rows = [{'scenario': name, 'gas_price_cny_m3': price,
                 'cost_cny_kg': values['baseline_cost_cny_kg'] + values['ng_m3_per_kg_fuel'] * (price - values['effective_ng_price_cny_m3']),
                 'fulfillment_ratio': solutions[name, 'baseline']['demand_fulfillment_ratio']}
                for name, values in cases.items() for price in [2, 2.5, 3, 3.5, 4.2, 5, 6, 7, 8]]
    capacities = pd.read_csv(run / 'h2_capacity.csv').set_index('location').value
    raw_capex = config['equipment_raw_costs']['electrolyzer']
    steel, refinery = float(raw_capex['byproduct_steel_capex_raw']), float(raw_capex['byproduct_refinery_capex_raw'])
    close(steel, 280000, 'GTL-BH configured steel conditioning CAPEX')
    close(refinery, 224000, 'GTL-BH configured refinery conditioning CAPEX')
    factors = capacities.index.map({name: steel if item['type'] == 'byproduct_hydrogen_steel' else refinery
                                   for name, item in model['locations'].items() if item['type'] in ['byproduct_hydrogen_steel', 'byproduct_hydrogen_refinery']})
    if not np.isfinite(factors).all():
        raise ValueError('GTL-BH conditioning capacity includes an unknown industrial source')
    capex_factor = float(config['economic_parameters']['capacity_factors']['electrolyzer_capacity_factor'])
    investment = float(np.sum(capacities.to_numpy() * factors) * capex_factor)
    close(investment, account['final_cost']['components']['electrolyzer_investment_cost'], 'GTL-BH source-specific conditioning CAPEX ledger', atol=.02)
    slope = investment / denominator / steel
    capex_rows = [{'scenario': scenario, 'steel_capex_cny_kg_h': amount, 'refinery_capex_cny_kg_h': amount * refinery / steel,
                   'cost_cny_kg': cases[scenario]['baseline_cost_cny_kg'] + slope * (amount - steel),
                   'fulfillment_ratio': account['production']['demand_fulfillment_ratio']}
                  for amount in [140000, 180000, 224000, 280000, 320000, 360000, 400000]]
    report = {'S20': cases, 'S21': {'steel_baseline_capex_cny_kg_h': steel, 'refinery_baseline_capex_cny_kg_h': refinery,
                                   'refinery_to_steel_ratio': refinery / steel, 'conditioning_investment_cny': investment,
                                   'conditioning_capacity_factor': capex_factor, 'cost_slope_cny_kg_per_100k': slope * 100000,
                                   'baseline_cost_cny_kg': cases[scenario]['baseline_cost_cny_kg'],
                                   'scope': 'Steel and refinery CAPEX move in the original 1.0:0.8 ratio; all production assets, dispatch and service are held fixed'}}
    return pd.DataFrame(gas_rows), pd.DataFrame(capex_rows), report


def build(results, accounts, output):
    solutions, carbons, account_records, directories, assumptions, tracked = collect(results, accounts)
    spec = importlib.util.spec_from_file_location('figure_account_categories', PROCESSOR)
    processor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(processor)
    learning, categories = learning_data(solutions, assumptions, processor.CATEGORIES)
    grid, dac, components, sensitivity = sensitivity_data(solutions, account_records, directories)
    carbon_sensitivity = carbon_sensitivity_data(solutions, carbons, directories)
    gas, conditioning_capex, fossil_checks = fossil_sensitivity_data(solutions, account_records, directories)
    sensitivity.update(fossil_checks)
    tracked.append({'path': str((HERE / 'carbon_sensitivity_assumptions.json').resolve()), 'role': 'retained_carbon_scope_assumptions',
                    'scenario': None, 'label': None, 'bytes': (HERE / 'carbon_sensitivity_assumptions.json').stat().st_size,
                    'sha256': digest(HERE / 'carbon_sensitivity_assumptions.json')})
    rows = [{'scenario': scenario, 'label': label,
             'cost_cny_kg': solution['lifecycle_levelized_cost_excluding_shortage_per_kg'],
             'carbon_g_mj': carbons[scenario, label]['carbon_intensity_mj'],
             'fulfillment_ratio': solution['demand_fulfillment_ratio'],
             'production_kg': carbons[scenario, label]['total_production_kg'],
             'provenance': 'Preserved original GTL' if scenario == 'GTL' else 'New verified model and final accounts'}
            for (scenario, label), solution in solutions.items()]
    baseline_rows = [row for row in rows if row['label'] == 'baseline']
    for row in baseline_rows:
        row['nondominated_baseline_envelope'] = not any(
            other['cost_cny_kg'] <= row['cost_cny_kg'] and other['carbon_g_mj'] <= row['carbon_g_mj']
            and (other['cost_cny_kg'] < row['cost_cny_kg'] or other['carbon_g_mj'] < row['carbon_g_mj'])
            for other in baseline_rows)
    output.mkdir(parents=True, exist_ok=True)
    for (scenario, label), solution in solutions.items():
        destination = output if label == 'baseline' else output / label
        destination.mkdir(exist_ok=True)
        write_json(destination / f'{scenario}_complete_solution.json', solution)
        write_json(destination / f'{scenario}_carbon_emissions.json', carbons[scenario, label])
    pd.DataFrame(rows).to_csv(output / 'all_run_summary.csv', index=False)
    pd.DataFrame(baseline_rows).to_csv(output / 'pathway_summary.csv', index=False)
    pd.DataFrame([row for row in baseline_rows if row['nondominated_baseline_envelope']]).sort_values(['carbon_g_mj', 'cost_cny_kg']).to_csv(output / 'nondominated_envelope.csv', index=False)
    learning.to_csv(output / 'learning_projections.csv', index=False)
    categories.to_csv(output / 'learning_categories.csv', index=False)
    grid.to_csv(output / 'S22_fixed_design_grid.csv', index=False)
    gas.to_csv(output / 'S20_fixed_design_ng.csv', index=False)
    conditioning_capex.to_csv(output / 'S21_fixed_design_conditioning_capex.csv', index=False)
    dac.to_csv(output / 'S23_fixed_design_dac.csv', index=False)
    components.to_csv(output / 'S24_fixed_design_component_sensitivity.csv', index=False)
    carbon_sensitivity.to_csv(output / 'S21_carbon_sensitivity.csv', index=False)
    write_json(output / 'carbon_sensitivity_assumptions.json', read_json(HERE / 'carbon_sensitivity_assumptions.json'))
    write_json(output / 'sensitivity_verification.json', sensitivity)
    assumptions['scope'] = 'Existing learning assumptions applied to twelve new baseline solutions and the preserved original GTL reference; fixed assets, dispatch, output and service fraction'
    write_json(output / 'learning_assumptions.json', assumptions)
    write_json(output / 'manifest.json', {scenario: {'scope': 'Preserved original GTL' if scenario == 'GTL' else 'New verified baseline',
                                                   'source_summary_sha256': None if scenario == 'GTL' else account_records[scenario, 'baseline']['source_summary_sha256']}
                                         for scenario in BASELINES})
    write_json(output / 'figure_inputs.json', {'schema_version': 1, 'ready': True, 'new_run_count': len(CASES),
                                              'baseline_pathway_count': len(BASELINES), 'sources': tracked,
                                              'builder_sha256': digest(Path(__file__)),
                                              'selected_representative_pathways': ['CCU-GH-FT', 'GTL', 'GTL-BH'],
                                              'envelope_scope': 'Actual thirteen baseline points at their respective demand-service fractions',
                                              'product_cost_label': 'LCO-SynAF', 'Figure1_x_axis': 'Direct supply-chain carbon intensity, g CO2e/MJ',
                                              'fixed_design_sensitivities': True})
    write_json(output / 'SHA256.json', {path.relative_to(output).as_posix(): digest(path) for path in sorted(output.rglob('*')) if path.is_file() and path.name != 'SHA256.json'})
    print(json.dumps({'ready': True, 'new_runs': len(CASES), 'baseline_pathways': len(BASELINES), 'output': str(output.resolve())}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--results', type=Path, default=REVISION / 'results')
    parser.add_argument('--accounts', type=Path, default=REVISION / 'postprocess/accounts')
    parser.add_argument('--out', type=Path, default=HERE / 'adapted_data')
    parser.add_argument('--check-inputs', action='store_true')
    parser.add_argument('--source-manifest', type=Path)
    args = parser.parse_args()
    if args.source_manifest:
        configure_sources(args.source_manifest)
    if args.check_inputs:
        missing = [str(path.resolve()) for path in input_paths(args.results, args.accounts) if not path.is_file()]
        report = {'schema_version': 1, 'ready': not missing, 'required_new_run_count': len(CASES),
                  'required_new_cases': [{'scenario': scenario, 'label': label} for scenario, label in CASES],
                  'missing': missing}
        HERE.mkdir(parents=True, exist_ok=True)
        write_json(HERE / 'input_readiness.json', report)
        print(json.dumps({'ready': report['ready'], 'missing_file_count': len(missing), 'report': str((HERE / 'input_readiness.json').resolve())}, ensure_ascii=False))
    else:
        build(args.results, args.accounts, args.out)
