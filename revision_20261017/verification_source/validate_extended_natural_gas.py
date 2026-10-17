import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


def maximum(values):
    values = np.asarray(values, dtype=float)
    return float(np.abs(values).max()) if values.size else 0.


def comparison(reported, expected):
    error = abs(float(reported) - float(expected))
    return dict(reported=float(reported), independently_recomputed=float(expected), absolute_error=error,
                passed=bool(np.isclose(reported, expected, rtol=1e-8, atol=1e-3)))


parser = argparse.ArgumentParser()
parser.add_argument('--run', type=Path, required=True)
args = parser.parse_args()
run = args.run.resolve()
names = ['summary.json', 'model_parameters.json', 'natural_gas_parameters.json', 'config.yaml',
         'ng_flows.csv', 'ng_technology_flows.csv', 'saf_production.csv']
hashes = {name: hashlib.sha256((run / name).read_bytes()).hexdigest() for name in names}
summary = json.loads((run / 'summary.json').read_text(encoding='utf-8'))
model = json.loads((run / 'model_parameters.json').read_text(encoding='utf-8'))
parameters = json.loads((run / 'natural_gas_parameters.json').read_text(encoding='utf-8'))
config = yaml.safe_load((run / 'config.yaml').read_text(encoding='utf-8'))
assert summary['scenario'] == 'GTL-BH' and summary['has_solution'] and summary['gap'] <= .01
assert not (run / 'EXPORT_IN_PROGRESS').exists()
ng, allocation, fuel = [pd.read_csv(run / name) for name in ['ng_flows.csv', 'ng_technology_flows.csv', 'saf_production.csv']]
assert not ng.duplicated(['source', 'destination', 'day']).any()
assert not allocation.duplicated(['source', 'destination', 'technology', 'day']).any()
assert all(np.isfinite(frame.value).all() and frame.value.ge(-1e-6).all() for frame in [ng, allocation, fuel])
assert model['periods'] == 224 and model['hours_per_period'] == 3 and model['weeks'] == 4
assert parameters['days'] == 28 and parameters['periods_per_day'] == 8
assert set(ng.day) == set(allocation.day) == set(range(28))
assert ng.groupby(['source', 'destination']).day.nunique().eq(28).all()
assert allocation.groupby(['source', 'destination', 'technology']).day.nunique().eq(28).all()
fuel['day'] = fuel.period // 8
ratios = {name: row['ng_consumption_ratio'] for name, row in model['technologies'].items()}
fuel['ng_required_m3'] = fuel.value * fuel.technology.map(ratios)
assert fuel.ng_required_m3.notna().all()
required = fuel.groupby(['location', 'technology', 'day']).ng_required_m3.sum()
routes = ng.set_index(['source', 'destination', 'day']).value
assigned = allocation.groupby(['source', 'destination', 'day']).value.sum()
incoming = allocation.groupby(['destination', 'technology', 'day']).value.sum()
incoming.index = incoming.index.set_names(['location', 'technology', 'day'])
explicit_demand = required[required.index.get_level_values('technology').isin(['pipeline_direct_conversion', 'lng_to_hplant_conversion'])]
has_route = explicit_demand.index.get_level_values('location').isin(set(allocation.destination))
unrouted_explicit_demand = explicit_demand[~has_route]
explicit_demand = explicit_demand[has_route]
incompatible = []
for row in allocation[['source', 'destination', 'technology']].drop_duplicates().itertuples(index=False):
    transport = config['technologies'][row.technology]['transport_mode']
    if model['locations'][row.source]['type'] not in config['transport_modes'][transport]['suitable_sources']:
        incompatible.append(dict(source=row.source, destination=row.destination, technology=row.technology))
truck = config['transport_constraints']['ng_truck_transport']
truck_limit = truck['max_trucks_per_day'] * truck['truck_capacity_m3']
assert truck_limit == parameters['truck_daily_limit_m3']
outgoing = ng.groupby(['source', 'day']).value.sum()
direct = fuel.groupby(['location', 'day']).ng_required_m3.sum()
source_rows = []
for source, capacity in parameters['lng_daily_capacities_m3'].items():
    assert model['locations'][source]['type'] == 'lng_terminal' and capacity > 0
    for day in range(28):
        local, transported = float(direct.get((source, day), 0)), float(outgoing.get((source, day), 0))
        source_rows.append(dict(source=source, day=day, onsite_m3=local, outbound_m3=transported,
                                capacity_m3=float(capacity), excess_m3=max(0, local + transported - capacity)))
distances = {(row['source'], row['destination']): row['distance_km'] for row in parameters['routes']}
distance = pd.MultiIndex.from_frame(ng[['source', 'destination']]).map(distances).to_numpy(dtype=float)
assert np.isfinite(distance).all() and (distance >= 0).all()
rate, years = config['economic_parameters']['discount_rate'], config['economic_parameters']['project_lifespan']
present = years if rate == 0 else float(np.sum((1 + rate) ** -np.arange(1, years + 1)))
lifecycle = 52 / model['weeks'] * present
carbon = config['carbon_emission_parameters']
extraction = carbon['raw_materials']['ng_extraction_intensity']
truck_carbon = carbon['transportation']['ng_truck_intensity'] / 100
assert extraction == parameters['extraction_kg_co2_per_m3']
assert truck_carbon == parameters['truck_kg_co2_per_m3_km']
transport_cost = float(np.sum(ng.value.to_numpy() * (.000452 * distance + .927))) * lifecycle
transport_emissions = float(np.sum(ng.value.to_numpy() * distance * truck_carbon))
upstream = float(fuel.ng_required_m3.sum()) * extraction
checks = dict(calendar_days=28, periods_per_day=8, complete_route_day_coverage=True,
              complete_technology_route_day_coverage=True, incompatible_technology_route_count=len(incompatible),
              route_technology_allocation_error_m3=maximum(routes - assigned.reindex(routes.index, fill_value=0)),
              technology_daily_supply_error_m3=maximum(incoming.reindex(explicit_demand.index, fill_value=0) - explicit_demand),
              unrouted_industrial_technology_demand_m3=maximum(unrouted_explicit_demand),
              daily_truck_capacity_excess_m3=maximum(np.maximum(routes.to_numpy() - truck_limit, 0)),
              lng_daily_source_capacity_excess_m3=max(row['excess_m3'] for row in source_rows))
ledger = dict(ng_transport_operation=comparison(summary['cost_breakdown']['ng_transport_operation'], transport_cost),
              ng_transport_carbon=comparison(summary['carbon_expressions']['ng_transport'], transport_emissions),
              ng_upstream_carbon=comparison(summary['carbon_expressions']['ng_extraction'], upstream))
airport = fuel[fuel.technology.eq('airport_integrated_conversion')]
report = dict(scenario='GTL-BH', passed=all(row['passed'] for row in ledger.values()) and not incompatible
              and all(checks[key] <= 1e-3 for key in ['route_technology_allocation_error_m3', 'technology_daily_supply_error_m3', 'unrouted_industrial_technology_demand_m3', 'daily_truck_capacity_excess_m3', 'lng_daily_source_capacity_excess_m3']),
              checks=checks, ledger_checks=ledger, incompatible_routes=incompatible,
              ng_required_m3=float(fuel.ng_required_m3.sum()), explicit_ng_transport_m3=float(ng.value.sum()),
              positive_explicit_ng_route_day_count=int(ng.value.gt(1e-5).sum()),
              airport_integrated_ng_m3=float(airport.ng_required_m3.sum()),
              airport_integrated_saf_kg=float(airport.value.sum()), lng_daily_accounts=source_rows,
              ng_transport_cost_curve=dict(intercept_cny_per_m3=.927, slope_cny_per_m3_km=.000452,
                                           lifecycle_factor=lifecycle, source='Frozen corrected_model.py NG transport expression'),
              scope='Explicit NG route allocation uses all 28 days and separates the two industrial conversion technologies. Airport-integrated NG is procured within its original integrated-supply boundary; zero explicit flow is recorded directly.',
              validator_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              solution_summary_sha256=hashes['summary.json'], input_sha256=hashes)
for name, value in hashes.items():
    assert hashlib.sha256((run / name).read_bytes()).hexdigest() == value
target = run / 'extended_natural_gas_validation.json'
target.write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps({key: value for key, value in report.items() if key != 'lng_daily_accounts'}, indent=2))
assert report['passed'], report
