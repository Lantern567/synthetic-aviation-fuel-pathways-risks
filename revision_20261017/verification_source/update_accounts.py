import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


SOURCE_TYPES = {'solar_plant', 'wind_farm', 'byproduct_hydrogen_steel', 'byproduct_hydrogen_refinery'}
COST_EXCLUSIONS = {'total_investment_cost', 'total_operation_cost', 'total_cost_excluding_shortage',
                   'total_cost', 'shortage_cost', 'shortage_penalty_cost', 'demand_fulfillment_ratio'}
CATEGORIES = {
    'Feedstock': {'carbon': ['coal_mining', 'ng_extraction'], 'cost': ['coal_purchase_cost', 'natural_gas_cost']},
    'Hydrogen': {'carbon': ['h2_production', 'electrolyzer_facility'], 'cost': ['hydrogen_production_cost', 'electrolyzer_investment_cost']},
    'CO2 Capture': {'carbon': ['co2_capture_energy', 'dac_equipment'], 'cost': ['co2_capture_cost', 'dac_capture_cost', 'dac_facility_investment']},
    'Conversion': {'carbon': ['coal_gasification_direct', 'coal_co2_fugitive', 'coal_gasification_energy', 'ng_to_methanol', 'methanol_to_saf', 'saf_synthesis_energy', 'ft_production'],
                   'cost': ['coal_gasification_cost', 'production_cost', 'methanol_production_cost', 'ft_production_cost', 'ft_reactor_operation_cost', 'ft_energy_cost', 'catalyst_cost', 'ft_catalyst_cost']},
    'Power': {'carbon': ['dac_grid_electricity'], 'cost': ['electricity_cost', 'dac_grid_electricity_cost']},
    'Facility': {'carbon': ['saf_facility'], 'cost': ['facility_investment_cost', 'facility_operation_cost', 'ft_reactor_investment_cost']},
    'Transport': {'carbon': ['coal_transport', 'ng_transport', 'h2_pipeline_transport', 'h2_truck_transport', 'h2_transport', 'co2_pipeline_transport', 'co2_truck_transport', 'co2_transport', 'mtj_transport', 'saf_transport'],
                  'cost': ['transport_operation_cost', 'hydrogen_transport_investment', 'hydrogen_transport_operation', 'hydrogen_pipeline_operation', 'ng_transport_investment', 'ng_transport_operation', 'co2_pipeline_transport_cost', 'co2_truck_transport_cost', 'saf_transport_investment', 'saf_transport_operation']},
    'Storage': {'carbon': ['h2_storage', 'mtj_storage', 'saf_storage'],
                'cost': ['storage_equipment_cost', 'storage_operation_cost', 'h2_storage_investment', 'h2_storage_operation', 'methanol_storage_equipment_cost', 'methanol_storage_investment', 'methanol_storage_operation', 'methanol_storage_operation_cost', 'co2_storage_investment', 'co2_storage_operation', 'final_inventory_cost']},
}


def native(path):
    resolved = Path(path).resolve()
    value = str(resolved)
    return Path('\\\\?\\' + value) if sys.platform == 'win32' and not value.startswith('\\\\?\\') else resolved


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def close(actual, expected, label, atol=1e-4, rtol=1e-9):
    if not np.isfinite(actual) or not np.isfinite(expected) or not np.isclose(actual, expected, rtol=rtol, atol=atol):
        raise ValueError(f'{label}: calculated={actual}, source={expected}')
    return float(actual - expected)


def carbon_leaves(components):
    result = {key: float(value) for key, value in components.items()}
    for aggregate, children in [('h2_transport', ['h2_pipeline_transport', 'h2_truck_transport']),
                                ('co2_transport', ['co2_pipeline_transport', 'co2_truck_transport'])]:
        if aggregate in result and any(child in result for child in children):
            close(result[aggregate], sum(result.get(child, 0) for child in children), aggregate)
            result.pop(aggregate)
    return result


def category_values(components, kind):
    result = {category: sum(components.get(key, 0) for key in fields[kind]) for category, fields in CATEGORIES.items()}
    mapped = {key for fields in CATEGORIES.values() for key in fields[kind]}
    excluded = {'co2_utilization_credit'} if kind == 'carbon' else set()
    unknown = {key: value for key, value in components.items() if key not in mapped | excluded and abs(value) > 1e-6}
    if unknown:
        raise ValueError(f'Unmapped {kind} components: {unknown}')
    return result


def coal_and_synthesis_accounts(scenario, config, parameters, production, raw_carbon, cost_components,
                                lifecycle_factor, read_csv, read_json, run):
    if scenario not in ('CTL', 'CTL-BH'):
        return {}, {}, []
    purchase = read_csv('coal_purchases.csv')
    if not {'location', 'week', 'value'} <= set(purchase.columns):
        raise ValueError('Coal purchases require location, week and value columns')
    if purchase.duplicated(['location', 'week']).any() or not np.isfinite(purchase.value).all() or purchase.value.min() < -1e-5:
        raise ValueError('Invalid actual coal purchase ledger')
    coal_mass = float(purchase.value.sum())
    coal = config['coal_parameters']
    process = config['carbon_emission_parameters']['production_process']
    price = float(coal['coal_price_yuan_per_ton']) / 1000
    coal_cost_error = close(coal_mass * price * lifecycle_factor, cost_components['coal_purchase_cost'], 'actual coal purchase cost', atol=.02, rtol=1e-8)
    gasification_cost = float(coal['gasification_energy_mj_per_kg']) * float(coal['gasification_energy_cost_yuan_per_mj'])
    gasification_cost_error = close(coal_mass * gasification_cost * lifecycle_factor, cost_components['coal_gasification_cost'], 'actual coal gasification cost', atol=.02, rtol=1e-8)
    factors = {
        'coal_mining': float(process['coal_mining_emission']),
        'coal_transport': float(process['coal_transport_emission']),
        'coal_gasification_direct': float(process['coal_gasification_direct_emission']),
        'coal_gasification_energy': float(process['coal_gasification_energy_kwh_per_kg']) * float(process['gasification_electricity_intensity']),
        'coal_co2_fugitive': float(process['coal_co2_yield_kg_per_kg']) * (1 - float(process['co2_capture_efficiency'])),
        'co2_capture_energy': float(process['coal_co2_yield_kg_per_kg']) * float(process['co2_capture_efficiency']) * float(process['co2_capture_energy_kwh_per_ton']) / 1000 * float(process['gasification_electricity_intensity']),
    }
    if not all(np.isfinite(factor) and factor >= 0 for factor in factors.values()):
        raise ValueError(f'Invalid coal carbon coefficients: {factors}')
    replacements = {name: coal_mass * factor for name, factor in factors.items()}
    renewable = config['carbon_emission_parameters']['renewable_energy']
    mean_ci = (float(renewable['wind_power_intensity']) + float(renewable['solar_power_intensity'])) / 2
    grid_ci = float(config.get('carbon_intensity', {}).get('grid_electricity_intensity', renewable['grid_electricity_intensity']))
    synthesis_rows = []
    for (location, technology), rows in production.groupby(['location', 'technology'], sort=True):
        energy = float(config['technologies'][technology]['energy_consumption_kwh_per_kg_saf'])
        location_type = parameters['locations'][location]['type']
        ci = mean_ci if location_type in ('solar_plant', 'wind_farm') else grid_ci
        if not np.isfinite(energy) or energy < 0 or not np.isfinite(ci) or ci < 0:
            raise ValueError(f'Invalid synthesis energy or electricity intensity: {(location, technology, energy, ci)}')
        mass = float(rows.value.sum())
        synthesis_rows.append({'location': location, 'technology': technology, 'location_type': location_type,
                               'production_kg': mass, 'energy_kwh_per_kg': energy,
                               'electricity_ci_kg_co2e_kwh': ci, 'electricity_kwh': mass * energy,
                               'emissions_kg_co2e': mass * energy * ci})
    replacements['saf_synthesis_energy'] = sum(row['emissions_kg_co2e'] for row in synthesis_rows)
    if any(config['technologies'][technology]['process_mode'] != 'one_step' for technology in production.technology.unique()):
        raise ValueError('CTL carbon accounts require the configured one-step synthesis pathway')
    replacements['methanol_to_saf'] = 0.0
    records = {name: {'raw_kg': raw_carbon[name], 'final_kg': result, 'change_kg': result - raw_carbon[name]}
               for name, result in replacements.items()}
    if (run / 'coal_accounting_parameters.json').exists():
        read_json('coal_accounting_parameters.json')
    metadata = {'quantity_basis': 'Actual sum of the model coal purchase variables over all represented weeks',
                'coal_purchased_kg': coal_mass, 'coal_kg_per_kg_fuel': coal_mass / float(production.value.sum()),
                'cost_reconstruction_residual_cny': coal_cost_error,
                'gasification_cost_reconstruction_residual_cny': gasification_cost_error,
                'carbon_kg_co2e_per_kg_coal': factors,
                'carbon_parameter_source': 'carbon_emission_parameters.production_process',
                'synthesis_energy_source': 'technologies[technology].energy_consumption_kwh_per_kg_saf',
                'methanol_stage': 'No separate methanol-to-jet stage in the configured one-step CTL pathway',
                'components': records}
    return replacements, metadata, synthesis_rows


def conversion_synthesis_accounts(scenario, config, parameters, production, hydrogen, raw_carbon,
                                   cost_components, lifecycle_factor, read_json):
    if not scenario.startswith(('CCU-', 'DAC-')) or not scenario.endswith(('-FT', '-MTJ')):
        return {}, {}, []
    carbon = config['carbon_emission_parameters']
    renewable = carbon['renewable_energy']
    mean_ci = (float(renewable['wind_power_intensity']) + float(renewable['solar_power_intensity'])) / 2
    grid_ci = float(renewable['grid_electricity_intensity'])
    renewable_price = float(parameters['costs']['renewable_electricity_cost_yuan_per_mwh']) / 1000
    grid_price = float(config['cost_parameters']['renewable_energy']['grid_electricity_price_yuan_per_kwh'])
    byproduct = '-BH-' in scenario
    if byproduct:
        hydrogen_parameters = read_json('byproduct_accounting_parameters.json')
        h2_energy = float(hydrogen_parameters['conditioning_kwh_per_kg'])
        h2_price = float(hydrogen_parameters['grid_electricity_cny_per_kwh'])
        close(float(hydrogen_parameters['grid_electricity_kg_co2e_per_kwh']), grid_ci, 'CCU/DAC industrial grid carbon intensity')
    else:
        h2_energy = float(parameters['costs']['electrolysis_power_consumption'])
        h2_price = renewable_price
    rows = []
    for (location, technology), values in production.groupby(['location', 'technology'], sort=True):
        technology_parameters = config['technologies'][technology]
        if scenario.endswith('-FT') and technology_parameters['process_mode'] != 'one_step':
            raise ValueError(f'FT synthesis requires one_step technology configuration: {technology}')
        energy = float(technology_parameters['energy_consumption_kwh_per_kg_saf'])
        close(energy, 7.6, 'CCU/DAC physical and cost synthesis energy coefficient')
        mass = float(values.value.sum())
        location_type = parameters['locations'][location]['type']
        on_renewable = location_type in ('solar_plant', 'wind_farm')
        ci, price = (mean_ci, renewable_price) if on_renewable else (grid_ci, grid_price)
        rows.append({'location': location, 'technology': technology, 'location_type': location_type,
                     'production_kg': mass, 'energy_kwh_per_kg': energy,
                     'electricity_ci_kg_co2e_kwh': ci, 'electricity_price_cny_per_kwh': price,
                     'electricity_kwh': mass * energy, 'emissions_kg_co2e': mass * energy * ci,
                     'discounted_electricity_cost_cny': mass * energy * price * lifecycle_factor})
    synthesis_carbon = sum(row['emissions_kg_co2e'] for row in rows)
    synthesis_residual = close(synthesis_carbon, raw_carbon['saf_synthesis_energy'], 'CCU/DAC configured synthesis carbon', atol=.02, rtol=1e-8)
    electricity_cost = sum(row['discounted_electricity_cost_cny'] for row in rows)
    electricity_cost += float(hydrogen.value.sum()) * h2_energy * h2_price * lifecycle_factor
    electricity_residual = close(electricity_cost, cost_components['electricity_cost'], 'CCU/DAC synthesis plus hydrogen electricity cost', atol=.02, rtol=1e-8)
    legacy_mtj_energy = float(carbon['production_process']['mtj_process_energy']) / 1000
    legacy_mtj_ci = grid_ci if byproduct else mean_ci
    legacy_mtj = float(production.value.sum()) * legacy_mtj_energy * legacy_mtj_ci
    mtj_residual = close(legacy_mtj, raw_carbon['methanol_to_saf'], 'CCU/DAC separate methanol carbon ledger reconstruction', atol=.02, rtol=1e-8)
    replacements = {'saf_synthesis_energy': synthesis_carbon, 'methanol_to_saf': 0.0}
    metadata = {
        'quantity_basis': 'Actual production at every site and technology in the three-hour saved solution',
        'synthesis_energy_source': 'technologies[technology].energy_consumption_kwh_per_kg_saf',
        'synthesis_energy_kwh_per_kg_fuel': 7.6,
        'synthesis_scope': 'Common FT/MTJ route-level model electricity assumption per kg final fuel, used consistently in physical demand, objective cost and emissions',
        'conversion_mode': 'FT' if scenario.endswith('-FT') else 'MTJ',
        'energy_parameter_interpretation': 'Scenario input assumption; not an independently calibrated MTJ process intensity',
        'methanol_stage': 'No additional stage electricity beyond the common route-level coefficient; MTJ intermediate material and inventory balances retain their executed formulation',
        'hydrogen_electricity_kwh_per_kg': h2_energy,
        'hydrogen_electricity_cny_per_kwh': h2_price,
        'synthesis_carbon_reconstruction_residual_kg': synthesis_residual,
        'electricity_cost_reconstructed_cny': electricity_cost,
        'electricity_cost_reconstruction_residual_cny': electricity_residual,
        'raw_separate_methanol_carbon_reconstructed_kg': legacy_mtj,
        'raw_separate_methanol_carbon_reconstruction_residual_kg': mtj_residual,
        'components': {name: {'raw_kg': raw_carbon[name], 'final_kg': value,
                              'change_kg': value - raw_carbon[name]} for name, value in replacements.items()},
    }
    return replacements, metadata, rows


def update(run_directory, output_directory):
    run, output = native(run_directory), native(output_directory)
    if output == run or run in output.parents:
        raise ValueError('Accounting outputs must be separate from the source run')
    if (run / 'EXPORT_IN_PROGRESS').exists():
        raise ValueError(f'Run export is incomplete: {run}')
    source_hashes = {}

    def read_json(name):
        path = run / name
        source_hashes[name] = digest(path)
        return json.loads(path.read_text(encoding='utf-8'))

    def read_csv(name):
        path = run / name
        source_hashes[name] = digest(path)
        return pd.read_csv(path)

    summary = read_json('summary.json')
    if 'inventory_accounting' in summary or 'final_carbon' in summary:
        raise ValueError('Expected an unmodified solver summary, received an accounted result')
    if not summary['has_solution'] or not summary['algebraic_validation']['passed']:
        raise ValueError('A complete algebraically validated real solution is required')
    scenario, label = summary['scenario'], summary['label']
    config_path = run / 'config.yaml'
    source_hashes['config.yaml'] = digest(config_path)
    config = yaml.safe_load(config_path.read_text(encoding='utf-8'))
    parameters = read_json('model_parameters.json')
    production = read_csv('saf_production.csv')
    hydrogen = read_csv('h2_production.csv')
    if production.duplicated(['location', 'technology', 'period']).any():
        raise ValueError('Duplicate SAF production records')
    basic = config['basic_parameters']
    weeks, periods_per_week, duration = int(basic['time_horizon_weeks']), int(basic['periods_per_week']), float(basic['hours_per_period'])
    periods, hours = weeks * periods_per_week, weeks * periods_per_week * duration
    if duration != 3 or periods_per_week * duration != 168:
        raise ValueError('Expected the archived three-hour representative-week time basis')
    economics = config['economic_parameters']
    years, rate = int(economics['project_lifespan']), float(economics['discount_rate'])
    present_value = years if rate == 0 else (1 - (1 + rate) ** (-years)) / rate
    annual_factor, lifecycle_factor = 52 / weeks, 52 / weeks * present_value
    actual_production = float(production.value.sum())
    production_residual = close(actual_production, summary['production_kg'], 'production')
    denominator = actual_production * lifecycle_factor
    if denominator <= 0:
        raise ValueError('Positive discounted production is required')
    raw_cost_ledger = {key: float(value) for key, value in summary['cost_breakdown'].items()}
    cost_components = {key: value for key, value in raw_cost_ledger.items() if key not in COST_EXCLUSIONS}
    if 'ft_production_cost' in cost_components:
        cost_components.pop('ft_energy_cost', None)
        cost_components.pop('ft_catalyst_cost', None)
    cost_residual = close(sum(cost_components.values()), raw_cost_ledger['total_cost_excluding_shortage'], 'cost leaf sum', atol=.01, rtol=1e-8)
    close(raw_cost_ledger['total_investment_cost'] + raw_cost_ledger['total_operation_cost'], raw_cost_ledger['total_cost_excluding_shortage'], 'cost aggregates', atol=.01)
    unit_cost = raw_cost_ledger['total_cost_excluding_shortage'] / denominator
    close(unit_cost, summary['cost_per_kg_excluding_shortage'], 'unit cost', atol=1e-8)
    raw_carbon_components = carbon_leaves(summary['carbon_expressions'])
    raw_carbon_aggregates = {key: float(value) for key, value in summary['carbon_aggregates'].items()}
    carbon_residual = close(sum(raw_carbon_components.values()), raw_carbon_aggregates['total_emissions'], 'carbon leaf sum')
    carbon_config = config['carbon_emission_parameters']
    renewable = carbon_config['renewable_energy']
    if scenario.startswith('DAC-BH-'):
        electricity_ci = float(renewable['grid_electricity_intensity'])
        inventory_ci_rule = 'Configured grid electricity intensity at every DAC-BH location'
    elif 'byproduct_accounting' in config:
        electricity_ci = float(config['byproduct_accounting']['grid_electricity_kg_co2e_per_kwh'])
        inventory_ci_rule = 'Explicit byproduct_accounting grid electricity intensity at every industrial-hydrogen scenario location'
    else:
        electricity_ci = (float(renewable['wind_power_intensity']) + float(renewable['solar_power_intensity'])) / 2
        inventory_ci_rule = 'Retained model wind/solar mean intensity'
    energy = float(carbon_config['benchmarks']['saf_energy_content'])
    storage_energy = carbon_config['storage_handling']
    storage_config = config.get('objective_coefficients', {}).get('storage', {})
    direct = storage_config.get('direct_costs', {})
    density = float(direct.get('storage_density_kg_per_m3', 500))
    if density <= 0:
        raise ValueError('Storage density must be positive')
    holding_rate = float(direct.get('warehouse_rent_per_m3_hour', .01)) / density + float(direct.get('handling_cost_per_kg_hour', .001))
    unified = config.get('unified_costs', {}).get('storage', {})
    equipment_units = {
        'saf': float(unified.get('mtj_equipment_cost_yuan_per_kg') or storage_config.get('equipment_unit_cost_yuan_per_kg', 10)),
        'h2': float(unified.get('hydrogen_equipment_cost_yuan_per_kg') or storage_config.get('hydrogen_equipment_unit_cost_yuan_per_kg', 20)),
    }
    inventory_parameters = read_json('inventory_cost_parameters.json') if (run / 'inventory_cost_parameters.json').exists() else None
    site_rows, inventory_accounts, inventories = [], {}, {}
    for commodity, field in [('saf', 'mtj_storage'), ('h2', 'h2_storage')]:
        inventory = read_csv(f'{commodity}_inventory.csv')
        inventories[commodity] = inventory
        if inventory.duplicated(['location', 'period']).any():
            raise ValueError(f'Duplicate {commodity} inventory records')
        pivot = inventory.pivot(index='location', columns='period', values='value').reindex(columns=range(periods + 1))
        values = pivot.to_numpy(dtype=float)
        if not np.isfinite(values).all() or values.min() < -1e-4:
            raise ValueError(f'Incomplete or invalid {commodity} stock array')
        types = pd.Series({location: parameters['locations'][location]['type'] for location in pivot.index})
        source_scope = types.isin(SOURCE_TYPES)
        charged_scope = source_scope if commodity == 'h2' and scenario.startswith('CCU-') else pd.Series(True, index=pivot.index)
        peak = pivot.max(axis=1)
        integral = pd.Series(((values[:, :-1] + values[:, 1:]) / 2).sum(axis=1) * duration, index=pivot.index)
        state_sum = pivot.sum(axis=1)
        divisor = 1000 if commodity == 'saf' else 1
        intensity = float(storage_energy['mtj_storage_energy' if commodity == 'saf' else 'h2_storage_energy'])
        raw_scope = pd.Series(True, index=pivot.index) if commodity == 'saf' else source_scope
        reconstructed_raw_carbon = float(state_sum[raw_scope].sum()) * intensity / 24 * electricity_ci
        raw_carbon_error = close(reconstructed_raw_carbon, raw_carbon_components[field], f'{commodity} original stock carbon', atol=1e-4, rtol=1e-8)
        accounted_by_site = integral * intensity / 24 / divisor * electricity_ci
        corrected_carbon = float(accounted_by_site.sum())
        equipment_field, operation_field = ('storage_equipment_cost', 'storage_operation_cost') if commodity == 'saf' else ('h2_storage_investment', 'h2_storage_operation')
        reconstructed_equipment = float(peak[charged_scope].sum()) * equipment_units[commodity]
        equipment_error = close(reconstructed_equipment, cost_components[equipment_field], f'{commodity} storage equipment', atol=.02, rtol=1e-8)
        source_hours = periods_per_week * duration if commodity == 'h2' and scenario.startswith('CCU-') else periods
        billed_hours = hours if inventory_parameters is not None else source_hours
        reconstructed_operation = float(peak[charged_scope].sum()) / 2 * holding_rate * billed_hours * lifecycle_factor
        operation_error = close(reconstructed_operation, cost_components[operation_field], f'{commodity} storage operation', atol=.02, rtol=1e-8)
        if inventory_parameters is not None:
            record = inventory_parameters['records'][commodity]
            if not inventory_parameters['applied_in_optimization']:
                raise ValueError('Inventory time conversion was not applied in optimization')
            close(record['represented_hours'], hours, f'{commodity} represented hours')
            close(record['final_expression_cost_cny'], cost_components[operation_field], f'{commodity} inventory parameter ledger', atol=.02)
            close(record['operation_cny_per_kg_hour'], holding_rate, f'{commodity} holding rate', atol=1e-12)
        for location in pivot.index:
            site_rows.append({'commodity': commodity, 'location': location, 'location_type': types[location],
                             'charged_in_model_cost': bool(charged_scope[location]), 'source_scope_in_raw_carbon': bool(raw_scope[location]),
                             'peak_inventory_kg': float(peak[location]), 'state_sum_inventory_kg': float(state_sum[location]),
                             'trapezoidal_inventory_kg_hour': float(integral[location]),
                             'final_inventory_emissions_kg_co2e': float(accounted_by_site[location]),
                             'initial_inventory_kg': float(pivot.loc[location, 0]), 'terminal_inventory_kg': float(pivot.loc[location, periods])})
        inventory_accounts[commodity] = {
            'field': field, 'location_count': len(pivot), 'state_count_per_location': periods + 1,
            'period_count': periods, 'integration_hours': periods * duration,
            'integration_rule': 'Sum over the 224 three-hour intervals of (opening stock + closing stock) / 2 times three hours',
            'boundary_weights': 'Initial and terminal states have weight 0.5; each interior state has weight 1',
            'source_location_count': int(source_scope.sum()), 'cost_charged_location_count': int(charged_scope.sum()),
            'inventory_state_sum_kg': float(state_sum.sum()), 'peak_inventory_sum_kg': float(peak.sum()),
            'inventory_integral_kg_hour': float(integral.sum()),
            'endpoint_mean_weighted_state_sum_kg': float(integral.sum()) / duration,
            'cost_charged_peak_inventory_sum_kg': float(peak[charged_scope].sum()),
            'raw_carbon_kg': raw_carbon_components[field], 'raw_carbon_reconstructed_kg': reconstructed_raw_carbon,
            'raw_carbon_reconstruction_residual_kg': raw_carbon_error,
            'final_carbon_kg': corrected_carbon, 'carbon_change_kg': corrected_carbon - raw_carbon_components[field],
            'period_hours': duration, 'energy_coefficient': intensity,
            'energy_coefficient_unit': 'kWh/(t day)' if commodity == 'saf' else 'kWh/(kg day)',
            'electricity_ci_kg_co2e_kwh': electricity_ci,
            'model_cost_billed_hours': billed_hours, 'represented_physical_hours': hours,
            'holding_cost_cny_per_kg_hour': holding_rate, 'equipment_cny_per_kg_capacity': equipment_units[commodity],
            'raw_equipment_cost_cny': cost_components[equipment_field], 'reconstructed_equipment_cost_cny': reconstructed_equipment,
            'equipment_cost_reconstruction_residual_cny': equipment_error,
            'raw_operation_cost_cny': cost_components[operation_field], 'reconstructed_operation_cost_cny': reconstructed_operation,
            'operation_cost_reconstruction_residual_cny': operation_error,
            'trapezoidal_operation_diagnostic_cny': float(integral[charged_scope].sum()) * holding_rate * lifecycle_factor,
            'initial_inventory_sum_kg': float(pivot[0].sum()), 'terminal_inventory_sum_kg': float(pivot[periods].sum()),
        }
    final_carbon_components = dict(raw_carbon_components)
    for commodity, record in inventory_accounts.items():
        final_carbon_components[record['field']] = record['final_carbon_kg']
    process_replacements, process_accounts, synthesis_rows = coal_and_synthesis_accounts(
        scenario, config, parameters, production, raw_carbon_components, cost_components,
        lifecycle_factor, read_csv, read_json, run)
    conversion_replacements, conversion_accounts, conversion_rows = conversion_synthesis_accounts(
        scenario, config, parameters, production, hydrogen, raw_carbon_components,
        cost_components, lifecycle_factor, read_json)
    if conversion_accounts:
        if process_accounts:
            raise ValueError('Overlapping process accounting scopes')
        process_replacements, process_accounts, synthesis_rows = conversion_replacements, conversion_accounts, conversion_rows
    final_carbon_components.update(process_replacements)
    carbon_change = sum(final_carbon_components[key] - value for key, value in raw_carbon_components.items())
    final_carbon_aggregates = dict(raw_carbon_aggregates)
    final_carbon_aggregates['storage_emissions'] = sum(record['final_carbon_kg'] for record in inventory_accounts.values())
    if process_accounts:
        final_carbon_aggregates['raw_material_emissions'] += sum(
            process_replacements[key] - raw_carbon_components[key]
            for key in process_replacements if key not in ('saf_synthesis_energy', 'methanol_to_saf'))
        final_carbon_aggregates['production_emissions'] += sum(
            process_replacements[key] - raw_carbon_components[key] for key in ('saf_synthesis_energy', 'methanol_to_saf'))
    final_carbon_aggregates['total_emissions'] = sum(final_carbon_components.values())
    final_carbon_aggregates['annual_emissions'] = final_carbon_aggregates['total_emissions'] * annual_factor
    close(final_carbon_aggregates['total_emissions'], raw_carbon_aggregates['total_emissions'] + carbon_change, 'final carbon replacement total')
    categories = category_values(final_carbon_components, 'carbon')
    cost_categories = category_values(cost_components, 'cost')
    credit = final_carbon_components.get('co2_utilization_credit', 0)
    close(sum(categories.values()) + credit, final_carbon_aggregates['total_emissions'], 'carbon categories')
    close(sum(cost_categories.values()), raw_cost_ledger['total_cost_excluding_shortage'], 'cost categories', atol=.01, rtol=1e-8)
    final_ci = final_carbon_aggregates['total_emissions'] / actual_production * 1000 / energy
    cost_aggregates = {key: raw_cost_ledger[key] for key in ['total_investment_cost', 'total_operation_cost', 'total_cost_excluding_shortage']}
    accounts = {
        'schema_version': 1, 'scenario': scenario, 'label': label,
        'processor_sha256': digest(Path(__file__)),
        'source_run': str(run), 'source_summary_sha256': source_hashes['summary.json'],
        'production': {'production_kg': actual_production, 'hydrogen_kg': float(hydrogen.value.sum()),
                       'demand_kg': summary['demand_kg'], 'shortage_kg': summary['shortage_kg'],
                       'demand_fulfillment_ratio': summary['demand_fulfillment_ratio'],
                       'annual_expansion': annual_factor, 'discounted_production_kg': denominator,
                       'project_lifespan_years': years, 'discount_rate': rate, 'present_value_factor': present_value},
        'raw_cost': {'components': cost_components, 'aggregates': cost_aggregates, 'unit_cost_cny_kg': unit_cost},
        'final_cost': {'components': cost_components, 'aggregates': cost_aggregates, 'unit_cost_cny_kg': unit_cost,
                       'postprocess_change_cny': 0.0, 'inventory_hours_applied_in_optimization': inventory_parameters is not None},
        'raw_carbon': {'components': raw_carbon_components, 'aggregates': raw_carbon_aggregates,
                       'intensity_g_mj': raw_carbon_aggregates['total_emissions'] / actual_production * 1000 / energy},
        'final_carbon': {'components': final_carbon_components, 'aggregates': final_carbon_aggregates,
                         'intensity_g_mj': final_ci, 'intensity_kg_per_kg': final_ci * energy / 1000,
                         'categories_kg': categories, 'co2_utilization_credit_kg': credit},
        'inventory_adjustments': inventory_accounts,
        'process_adjustments': process_accounts,
        'accounting_policy': {'inventory_carbon': 'Three-hour endpoint-mean stocks integrated over 224 intervals (672 hours); 225 states with half weight at initial and terminal boundaries; SAF kg converted to tonnes and H2 retained in kg',
                              'inventory_cost': 'Keep the model site-peak/2 proxy and its optimized cost components; do not apply a second time multiplier',
                              'electricity_ci_rule': inventory_ci_rule,
                              'coal_and_synthesis': 'For CTL scenarios, reconstruct coal emissions from actual purchased coal and synthesis emissions from configured technology energy at each production site',
                              'ccu_dac_synthesis': 'CCU and DAC FT/MTJ use the common configured route-level input assumption of 7.6 kWh/kg final fuel for physical demand, electricity cost and emissions; no additional methanol-stage electricity is added',
                              'meoh_co2_stock_energy': 'No separate energy coefficients in the model; no new coefficients inserted',
                              'carbon_categories': 'Original eight categories with aggregate transport aliases removed; utilization credit separate'},
        'checks': {'passed': True, 'scope': 'Production sum, nonduplicate source cost/carbon closure, inventory equipment/operation reconstruction and all-site inventory carbon; CTL actual coal purchase/gasification costs; CCU/DAC FT/MTJ configured synthesis energy, carbon and electricity cost; physical feasibility validated separately',
                   'production_residual_kg': production_residual, 'cost_leaf_residual_cny': cost_residual,
                   'raw_carbon_leaf_residual_kg': carbon_residual, 'source_algebraic_validation_passed': True},
    }
    carbon = {'detailed': final_carbon_components, 'detailed_raw': summary['carbon_expressions'],
              'by_stage': final_carbon_aggregates, 'total_production_kg': actual_production,
              'carbon_intensity_kg': final_ci * energy / 1000, 'carbon_intensity_mj': final_ci,
              'traditional_jet_ci_gco2e_per_mj': float(carbon_config['benchmarks']['traditional_jet_fuel']),
              'carbon_accounting': accounts['accounting_policy'], 'source_summary_sha256': source_hashes['summary.json']}
    benchmark = carbon['traditional_jet_ci_gco2e_per_mj']
    carbon.update(abs_diff_vs_traditional_jet_gco2e_per_mj=final_ci - benchmark,
                  vs_traditional_jet=(final_ci / benchmark - 1) * 100)
    facilities = {}
    for prefix, capacity_file, build_file, dispatch in [('saf', 'saf_capacity.csv', 'saf_build.csv', production),
                                                      ('electrolyzer', 'h2_capacity.csv', 'h2_build.csv', hydrogen)]:
        capacities, builds = read_csv(capacity_file), read_csv(build_file)
        keys = ['location', 'technology'] if 'technology' in capacities.columns else ['location']
        builds = builds.set_index(keys).value
        for record in capacities.to_dict('records'):
            if record['value'] <= 1e-5:
                continue
            location, technology = record['location'], record.get('technology', 'electrolyzer')
            key = (location, technology) if len(keys) == 2 else location
            mask = dispatch.location.eq(location)
            if 'technology' in dispatch.columns:
                mask &= dispatch.technology.eq(technology)
            volume, geo = float(dispatch.loc[mask, 'value'].sum()), parameters['locations'][location]
            facilities[f'{prefix}_{location}_{technology}'] = {
                'location': location, 'technology': technology, 'built': bool(builds.loc[key] > .5),
                'capacity_kg_per_hour': record['value'], 'max_annual_capacity_kg': record['value'] * 8760,
                'actual_annual_production_kg': volume * annual_factor,
                'utilization_rate': volume / (record['value'] * hours), 'location_type': geo['type'],
                'latitude': geo['latitude'], 'longitude': geo['longitude']}
    normalized = {
        'optimization_status': summary['status'], 'optimization_time': summary['seconds'],
        'objective_value_lifecycle_total': cost_aggregates['total_cost_excluding_shortage'],
        'source_solver_objective': summary['objective'], 'project_lifespan_years': years,
        'time_window_weeks': weeks, 'period_hours': duration,
        'demand_fulfillment_ratio': summary['demand_fulfillment_ratio'],
        'annual_production_kg': actual_production * annual_factor,
        'lifecycle_total_production_kg': actual_production * annual_factor * years,
        'lifecycle_levelized_cost_per_kg': unit_cost, 'lifecycle_levelized_cost_excluding_shortage_per_kg': unit_cost,
        'cost_breakdown': cost_components, 'cost_breakdown_raw': raw_cost_ledger,
        'facilities': facilities, 'hydrogen_facilities': {key: record for key, record in facilities.items() if record['technology'] == 'electrolyzer'},
        'hourly_production_summary': {'period_hours': duration,
                                      'saf_kg': production.groupby('period').value.sum().reindex(range(periods), fill_value=0).tolist(),
                                      'hydrogen_kg': hydrogen.groupby('period').value.sum().reindex(range(periods), fill_value=0).tolist()},
        'weekly': summary['weekly'], 'carbon_emissions': carbon, 'source_sha256': source_hashes['summary.json'],
        'cost_accounting': accounts['accounting_policy']['inventory_cost'], 'carbon_accounting': accounts['accounting_policy'],
        'revision_scope': 'New real model solution with independently reconstructed final stock-energy accounting',
    }
    for name in ['physical_validation.json', 'byproduct_physical_validation.json', 'byproduct_accounting_parameters.json']:
        if (run / name).exists():
            read_json(name)
    for path in sorted((run / 'source').glob('*.py')):
        source_hashes[path.relative_to(run).as_posix()] = digest(path)
    accounts['source_hashes'] = source_hashes
    output.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(site_rows).to_csv(output / 'inventory_site_accounts.csv', index=False)
    if synthesis_rows:
        pd.DataFrame(synthesis_rows).to_csv(output / 'synthesis_energy_accounts.csv', index=False)
    pd.DataFrame([{'component': key, 'raw_cny': value, 'final_cny': value, 'cny_per_kg_fuel': value / denominator} for key, value in cost_components.items()]).to_csv(output / 'cost_components.csv', index=False)
    pd.DataFrame([{'component': key, 'raw_kg_co2e': raw_carbon_components[key], 'final_kg_co2e': value,
                   'final_g_co2e_per_mj': value / actual_production * 1000 / energy} for key, value in final_carbon_components.items()]).to_csv(output / 'carbon_components.csv', index=False)
    pd.DataFrame([{'scenario': scenario, 'category': key, 'emissions_kg': value,
                   'g_co2e_per_mj': value / actual_production * 1000 / energy} for key, value in categories.items()]).to_csv(output / 'carbon_categories.csv', index=False)
    for name, payload in [('accounts.json', accounts), ('normalized_complete_solution.json', normalized), ('normalized_carbon_emissions.json', carbon)]:
        write_json(output / name, payload)
    for name, expected in source_hashes.items():
        if digest(run / name) != expected:
            raise ValueError(f'Source changed during accounting: {name}')
    write_json(output / 'SHA256.json', {path.name: digest(path) for path in sorted(output.iterdir()) if path.is_file() and path.name != 'SHA256.json'})
    print(json.dumps({'scenario': scenario, 'label': label, 'passed': True, 'cost_cny_kg': unit_cost,
                      'raw_ci_g_mj': accounts['raw_carbon']['intensity_g_mj'], 'final_ci_g_mj': final_ci,
                      'source_summary_sha256': source_hashes['summary.json'], 'output': str(output)}, ensure_ascii=False))
    return accounts


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    parser.add_argument('--out', required=True)
    arguments = parser.parse_args()
    update(arguments.run, arguments.out)
