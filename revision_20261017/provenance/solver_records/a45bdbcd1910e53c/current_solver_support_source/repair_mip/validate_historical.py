import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

RUNTIME = Path(sys.argv[sys.argv.index('--runtime') + 1]).resolve() if '--runtime' in sys.argv else Path(__file__).resolve().parent
sys.path.insert(0, str(RUNTIME))
from validate_co2 import comparison


def largest(values):
    values = np.asarray(values, dtype=float)
    return float(np.abs(values).max()) if values.size else 0.0


def indexed(path, columns):
    table = pd.read_csv(path)
    assert not table.duplicated(columns).any(), path
    assert np.isfinite(table.value).all(), path
    assert (table.value >= -1e-6).all(), path
    return table.set_index(columns).value


def balance(stock, supply, consumption, periods):
    rows = []
    for (location, period), before in stock.items():
        if period == periods:
            continue
        after = stock.loc[location, period + 1]
        residual = after - before - supply.get((location, period), 0) + consumption.get((location, period), 0)
        rows.append({'location': location, 'period': period, 'residual_kg': residual})
    return pd.DataFrame(rows)


def main():
    base = RUNTIME
    scenario, label = sys.argv[1:3]
    run = base / 'verified_runs' / scenario / label
    inputs = base / 'inputs' / scenario / label
    assert not (run / 'EXPORT_IN_PROGRESS').exists()
    summary = json.loads((run / 'summary.json').read_text())
    model = json.loads((run / 'model_parameters.json').read_text())
    config = yaml.safe_load((run / 'config.yaml').read_text())
    accounting = json.loads((run / 'byproduct_accounting_parameters.json').read_text())
    periods, hours, weeks = model['periods'], model['hours_per_period'], model['weeks']
    assert (periods, hours, weeks) == (224, 3, 4)
    source = pd.read_csv(inputs / 'byproduct_hydrogen_periods.csv').rename(columns={'plant_name': 'location'})
    available = source.set_index(['location', 'period']).h2_available_kg_per_hour * hours
    h2 = indexed(run / 'h2_production.csv', ['location', 'period'])
    h2stock = indexed(run / 'h2_inventory.csv', ['location', 'period'])
    capacity = indexed(run / 'h2_capacity.csv', ['location'])
    built = indexed(run / 'h2_build.csv', ['location'])
    fuel = pd.read_csv(run / 'saf_production.csv')
    fuel_total = fuel.groupby(['location', 'period']).value.sum()
    ratios = {name: parameters['h2_consumption_ratio'] for name, parameters in model['technologies'].items()}
    fuel['h2_used_kg'] = fuel.value * fuel.technology.map(ratios)
    assert fuel.h2_used_kg.notna().all()
    use = fuel.groupby(['location', 'period']).h2_used_kg.sum()
    flows = pd.read_csv(run / 'h2_flows.csv')
    incoming = flows.groupby(['destination', 'period']).value.sum()
    outgoing = flows.groupby(['source', 'period']).value.sum()
    incoming.index = incoming.index.set_names(['location', 'period'])
    outgoing.index = outgoing.index.set_names(['location', 'period'])
    hydrogen_balance = balance(h2stock, h2.add(incoming, fill_value=0), use.add(outgoing, fill_value=0), periods)
    delivered = pd.read_csv(run / 'deliveries.csv')
    outgoing_fuel = delivered.groupby(['location', 'week']).value.sum()
    outgoing_fuel.index = pd.MultiIndex.from_tuples([(location, week * 56 + 55) for location, week in outgoing_fuel.index], names=['location', 'period'])
    fuelstock = indexed(run / 'saf_inventory.csv', ['location', 'period'])
    fuel_balance = balance(fuelstock, fuel_total, outgoing_fuel, periods)
    saf_capacity = indexed(run / 'saf_capacity.csv', ['location', 'technology'])
    saf_built = indexed(run / 'saf_build.csv', ['location', 'technology'])
    installed = pd.MultiIndex.from_frame(fuel[['location', 'technology']]).map(saf_capacity)
    fuel_capacity_excess = np.maximum(fuel.value.to_numpy() - np.asarray(installed) * hours, 0)
    demand = pd.read_csv(inputs / 'airport_input.csv')
    original_weeks = sorted(demand.week_number.unique())
    assert len(original_weeks) == weeks
    assert demand.groupby('departure_airport_name').week_number.nunique().eq(weeks).all()
    demand['week'] = demand.week_number.map(dict(zip(original_weeks, range(weeks))))
    assert not demand.duplicated(['departure_airport_name', 'week']).any()
    demand = demand.set_index(['departure_airport_name', 'week']).weekly_total_fuel_kg_total
    demand.index = demand.index.set_names(['airport', 'week'])
    shortages = indexed(run / 'shortages.csv', ['airport', 'week'])
    delivery = delivered.groupby(['airport', 'week']).value.sum()
    demand_residual = delivery.reindex(demand.index, fill_value=0) + shortages.reindex(demand.index) - demand
    assert demand_residual.notna().all()
    maximum_saf_capacity = config['capacity_limits']['mtj_max_capacity_kg_per_hour'] if scenario == 'GTL-BH' else config['capacity_limits']['saf_reactor_max_capacity_kg_per_hour']
    checks = {
        'h2_source_availability_excess_kg': largest(np.maximum(h2 - available.reindex(h2.index), 0)),
        'h2_conditioning_capacity_excess_kg': largest(np.maximum(h2 - h2.index.get_level_values('location').map(capacity).to_numpy() * hours, 0)),
        'h2_build_capacity_excess_kg_h': largest(np.maximum(capacity - built * config['capacity_limits']['electrolyzer_max_capacity_kg_per_hour'], 0)),
        'h2_node_period_balance_error_kg': largest(hydrogen_balance.residual_kg),
        'h2_initial_inventory_kg': largest(h2stock.xs(0, level='period')),
        'fuel_node_period_balance_error_kg': largest(fuel_balance.residual_kg),
        'fuel_initial_inventory_kg': largest(fuelstock.xs(0, level='period')),
        'fuel_capacity_excess_kg': largest(fuel_capacity_excess),
        'fuel_build_capacity_excess_kg_h': largest(np.maximum(saf_capacity - saf_built * maximum_saf_capacity, 0)),
        'demand_shortage_accounting_error_kg': largest(demand_residual),
        'reported_fuel_production_error_kg': abs(float(fuel.value.sum()) - summary['production_kg']),
    }
    parameters = config['byproduct_accounting']
    type_map = {name: row['type'] for name, row in model['locations'].items()}
    coefficients = h2.index.get_level_values('location').map(type_map).map(parameters['upstream_kg_co2e_per_kg']).to_numpy(dtype=float)
    assert np.isfinite(coefficients).all()
    h2_carbon = float(np.sum(h2.to_numpy() * (coefficients + parameters['conditioning_kwh_per_kg'] * parameters['grid_electricity_kg_co2e_per_kwh'])))
    if scenario == 'GTL-BH':
        synthesis_kwh = float(fuel.value.sum()) * config['carbon_emission_parameters']['production_process']['mtj_process_energy'] / 1000
    else:
        synthesis_kwh = float(fuel.value.sum()) * config['technologies']['green_h2_co2_to_saf']['energy_consumption_kwh_per_kg_saf']
    rate = config['economic_parameters']['discount_rate']
    years = config['economic_parameters']['project_lifespan']
    lifecycle = 52 / weeks * float(np.sum((1 + rate) ** -np.arange(1, years + 1)))
    electricity = (float(h2.sum()) * parameters['conditioning_kwh_per_kg'] + synthesis_kwh) * parameters['grid_electricity_cny_per_kwh'] * lifecycle
    internal = config.get('unified_costs', {}).get('production', {}).get('hydrogen_internal_cost_yuan_per_kg', 0)
    ledger = {
        'h2_upstream_and_conditioning_carbon': comparison(summary['carbon_expressions']['h2_production'], h2_carbon),
        'conditioning_and_synthesis_grid_electricity_cost': comparison(summary['cost_breakdown']['electricity_cost'], electricity),
        'hydrogen_internal_component_cost': comparison(summary['cost_breakdown']['hydrogen_production_cost'], float(h2.sum()) * internal * lifecycle),
        'reported_levelized_fuel_cost': comparison(summary['cost_per_kg_excluding_shortage'], summary['cost_breakdown']['total_cost_excluding_shortage'] / (float(fuel.value.sum()) * lifecycle)),
        'conditioning_electricity_kwh': comparison(accounting['conditioning_electricity_kwh'], float(h2.sum()) * parameters['conditioning_kwh_per_kg']),
    }
    if scenario == 'GTL-BH':
        ng = pd.read_csv(run / 'ng_flows.csv')
        allocation = pd.read_csv(run / 'ng_technology_flows.csv')
        ng_parameters = json.loads((run / 'natural_gas_parameters.json').read_text())
        assert ng_parameters['days'] == 28 and ng_parameters['periods_per_day'] == 8
        assert ng.day.between(0, 27).all() and allocation.day.between(0, 27).all()
        route_total = ng.set_index(['source', 'destination', 'day']).value
        allocated = allocation.groupby(['source', 'destination', 'day']).value.sum()
        checks['ng_route_allocation_error_m3'] = largest(route_total - allocated.reindex(route_total.index, fill_value=0))
        fuel['day'] = fuel.period // 8
        fuel['ng_needed_m3'] = fuel.value * fuel.technology.map({name: row['ng_consumption_ratio'] for name, row in model['technologies'].items()})
        demand_ng = fuel.groupby(['location', 'technology', 'day']).ng_needed_m3.sum()
        incoming_ng = allocation.groupby(['destination', 'technology', 'day']).value.sum()
        incoming_ng.index = incoming_ng.index.set_names(['location', 'technology', 'day'])
        transported_locations = set(allocation.destination)
        transported = demand_ng.index.get_level_values('location').isin(transported_locations)
        need = demand_ng[transported]
        checks['ng_technology_daily_material_balance_error_m3'] = largest(incoming_ng.reindex(need.index, fill_value=0) - need)
        checks['ng_daily_truck_capacity_excess_m3'] = largest(np.maximum(route_total - ng_parameters['truck_daily_limit_m3'], 0))
        raw_carbon = float(fuel.ng_needed_m3.sum()) * ng_parameters['extraction_kg_co2_per_m3']
        distance = {(row['source'], row['destination']): row['distance_km'] for row in ng_parameters['routes']}
        ng_distance = pd.MultiIndex.from_frame(ng[['source', 'destination']]).map(distance).to_numpy(dtype=float)
        assert np.isfinite(ng_distance).all()
        ng_carbon = float(np.sum(ng.value.to_numpy() * ng_distance)) * ng_parameters['truck_kg_co2_per_m3_km']
        ledger['ng_upstream_carbon'] = comparison(summary['carbon_expressions']['ng_extraction'], raw_carbon)
        ledger['ng_transport_carbon'] = comparison(summary['carbon_expressions']['ng_transport'], ng_carbon)
        ledger['mtj_grid_synthesis_carbon'] = comparison(summary['carbon_expressions']['methanol_to_saf'], synthesis_kwh * parameters['grid_electricity_kg_co2e_per_kwh'])
    if scenario == 'CTL-BH':
        coal = indexed(run / 'coal_purchases.csv', ['location', 'week'])
        carbon_stock = indexed(run / 'coal_co2_inventory.csv', ['location', 'period'])
        coal_parameters = json.loads((run / 'coal_accounting_parameters.json').read_text())
        supply = pd.Series({
            (location, period): coal.get((location, period // 56), 0)
            * coal_parameters['co2_available_kg_per_kg_coal'] / 56
            for location in carbon_stock.index.get_level_values('location').unique()
            for period in range(periods)
        })
        supply.index = supply.index.set_names(['location', 'period'])
        co2_fuel = fuel.value * fuel.technology.map(coal_parameters['co2_consumption_kg_per_kg_saf'])
        co2_use = fuel.assign(co2_use_kg=co2_fuel).groupby(['location', 'period']).co2_use_kg.sum()
        coal_balance = balance(carbon_stock, supply, co2_use, periods)
        checks['coal_co2_node_period_balance_error_kg'] = largest(coal_balance.residual_kg)
        checks['coal_co2_initial_inventory_kg'] = largest(carbon_stock.xs(0, level='period'))
        for field, coefficient in coal_parameters['carbon_coefficients_kg_co2e_per_kg_coal'].items():
            ledger[field + '_from_actual_coal'] = comparison(summary['carbon_expressions'][field], float(coal.sum()) * coefficient)
        ledger['coal_purchase_cost'] = comparison(summary['cost_breakdown']['coal_purchase_cost'], float(coal.sum()) * coal_parameters['purchase_cny_per_kg_coal'] * lifecycle)
        ledger['coal_gasification_cost'] = comparison(summary['cost_breakdown']['coal_gasification_cost'], float(coal.sum()) * coal_parameters['gasification_cny_per_kg_coal'] * lifecycle)
        ledger['single_stage_synthesis_carbon'] = comparison(summary['carbon_expressions']['saf_synthesis_energy'], synthesis_kwh * parameters['grid_electricity_kg_co2e_per_kwh'])
        ledger['no_additional_mtj_stage'] = comparison(summary['carbon_expressions']['methanol_to_saf'], 0)
        coal_balance.to_csv(run / 'physical_coal_co2_balance.csv', index=False)
    hydrogen_balance.to_csv(run / 'physical_hydrogen_balance.csv', index=False)
    fuel_balance.to_csv(run / 'physical_fuel_balance.csv', index=False)
    tracked = list(inputs.iterdir()) + [run / filename for filename in [
        'summary.json', 'config.yaml', 'model_parameters.json', 'byproduct_accounting_parameters.json',
        'saf_production.csv', 'h2_production.csv', 'h2_inventory.csv', 'h2_flows.csv',
        'saf_inventory.csv', 'deliveries.csv', 'shortages.csv', 'saf_capacity.csv', 'saf_build.csv',
        'h2_capacity.csv', 'h2_build.csv'
    ]]
    report = {'scenario': scenario, 'label': label, 'checks': checks, 'ledger_checks': ledger,
              'demand_week_mapping': {str(original): index for index, original in enumerate(original_weeks)},
              'validator_source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'validator_source_path': str(Path(__file__).resolve()),
              'physical_checks_passed': all(value <= 1e-3 for value in checks.values()),
              'ledger_checks_passed': all(row['passed'] for row in ledger.values()),
              'h2_total_production_kg': float(h2.sum()), 'fuel_total_production_kg': float(fuel.value.sum()),
              'solution_summary_sha256': hashlib.sha256((run / 'summary.json').read_bytes()).hexdigest(),
              'input_sha256': {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in tracked if path.is_file()},
              'scope': 'Independent material balances, source/capacity limits, industrial conditioning costs and carbon, fuel output cost; separate route and inventory validators check their full ledgers.'}
    report['passed'] = report['physical_checks_passed'] and report['ledger_checks_passed']
    (run / 'physical_validation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
    assert report['passed'], report


if __name__ == '__main__':
    main()
