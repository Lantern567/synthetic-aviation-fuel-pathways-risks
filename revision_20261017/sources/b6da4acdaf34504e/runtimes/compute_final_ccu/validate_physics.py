import json
import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

base = Path(__file__).resolve().parent


def validate_run(scenario, label):
    out = base / 'runs' / scenario / label
    if (base / 'verified_runs' / scenario / label / 'summary.json').exists():
        out = base / 'verified_runs' / scenario / label
    summary = json.loads((out / 'summary.json').read_text())
    assert not (out / 'EXPORT_IN_PROGRESS').exists(),out
    params = json.loads((out / 'model_parameters.json').read_text())
    inputs = base / 'inputs' / ('baseline' if label in ('baseline','warm_baseline') else 'summer')
    power = pd.read_csv(inputs / 'renewable_periods.csv').rename(columns={'plant_name':'location'}).set_index(['location','period']).power_output_mw
    h2 = pd.read_csv(out / 'h2_production.csv').set_index(['location','period']).value
    saf_table = pd.read_csv(out / 'saf_production.csv')
    saf = saf_table.groupby(['location','period']).value.sum()
    demand = pd.read_csv(inputs / 'airport_input.csv')
    deliveries = pd.read_csv(out / 'deliveries.csv')
    electric = power.rename('available_mw').to_frame()
    electric['available_mwh'] = electric.available_mw*3
    electric['hydrogen_mwh'] = h2.reindex(electric.index).fillna(0)*params['costs']['electrolysis_power_consumption']/1000
    if scenario == 'GTL-GH':
        renewable_saf = pd.read_csv(out / 'mtj_renewable_electricity_vars.csv').set_index(['location','period']).value
        grid_saf = pd.read_csv(out / 'mtj_grid_electricity_vars.csv').set_index(['location','period']).value
        config = yaml.safe_load((out / 'config.yaml').read_text())
        intensity = float(config.get('carbon_intensity',{}).get('production_process',{}).get('mtj_process_energy',4500))/1e6
        mtj_error = (renewable_saf+grid_saf-saf.reindex(renewable_saf.index).fillna(0)*intensity).abs().max()
        electric['synthesis_mwh'] = renewable_saf.reindex(electric.index).fillna(0)
    else:
        mtj_error = 0
        synthesis_intensity = float(config['technologies']['green_h2_co2_to_saf']['energy_consumption_kwh_per_kg_saf']) if scenario == 'CTL' else 7.6
        electric['synthesis_mwh'] = saf.reindex(electric.index).fillna(0)*synthesis_intensity/1000
    electric['dac_mwh'],electric['dac_grid_mwh'] = 0.0,0.0
    dac_grid_violation = 0
    if scenario.startswith('DAC-'):
        dac = pd.read_csv(out / 'dac_co2_supply.csv').set_index(['location','period']).value*params['dac_kwh_per_kg']/1000
        grid = pd.read_csv(out / 'dac_grid_electricity_vars.csv').set_index(['location','period']).value/1000
        electric['dac_mwh'] = dac.reindex(electric.index).fillna(0)
        electric['dac_grid_mwh'] = grid.reindex(electric.index).fillna(0)
        dac_grid_violation = max(0,float((grid-dac).max()))
        nonrenewable = dac.index.difference(electric.index)
        dac_grid_violation = max(dac_grid_violation,float((dac.loc[nonrenewable]-grid.loc[nonrenewable]).abs().max()) if len(nonrenewable) else 0)
    electric['renewable_deficit_mwh'] = (electric.hydrogen_mwh+electric.synthesis_mwh-electric.available_mwh).clip(lower=0)
    electric['joint_deficit_mwh'] = (electric.hydrogen_mwh+electric.synthesis_mwh+electric.dac_mwh-electric.dac_grid_mwh-electric.available_mwh).clip(lower=0)
    electric.to_csv(out / 'physical_electricity.csv')
    flows = pd.read_csv(out / 'h2_flows.csv')
    inbound = flows.groupby(['destination','period']).value.sum()
    outbound = flows.groupby(['source','period']).value.sum()
    inventory = pd.read_csv(out / 'h2_inventory.csv').set_index(['location','period']).value
    ratios = {name:info['h2_consumption_ratio'] for name,info in params['technologies'].items()}
    saf_table['h2_used'] = saf_table.value*saf_table.technology.map(ratios)
    consumption = saf_table.groupby(['location','period']).h2_used.sum()
    rows = []
    for (location,t),before in inventory.items():
        if t == 224:
            continue
        error = inventory.loc[location,t+1]-before-h2.get((location,t),0)-inbound.get((location,t),0)+outbound.get((location,t),0)+consumption.get((location,t),0)
        rows.append((location,t,error))
    balance = pd.DataFrame(rows,columns=['location','period','residual_kg'])
    balance.to_csv(out / 'physical_hydrogen_balance.csv',index=False)
    initial_h2 = inventory.xs(0,level='period')
    flow_limit = float(yaml.safe_load((out / 'config.yaml').read_text())['capacity_limits'].get('hydrogen_pipeline_max_daily_capacity_kg',50000))*3/24
    max_flow_violation = max(0,float(flows.value.max())-flow_limit)
    flows['week'] = flows.period//56
    weekly_flows = flows.groupby(['source','destination','week']).value.sum().unstack('week')
    weekly_flow_difference = float((weekly_flows.max(axis=1)-weekly_flows.min(axis=1)).max())
    saf_inventory = pd.read_csv(out / 'saf_inventory.csv').set_index(['location','period']).value
    dispatch = deliveries.groupby(['location','week']).value.sum()
    saf_rows = []
    for (location,t),before in saf_inventory.items():
        if t == 224:
            continue
        shipped = dispatch.get((location,t//56),0) if t%56 == 55 else 0
        residual = saf_inventory.loc[location,t+1]-before-saf.get((location,t),0)+shipped
        saf_rows.append((location,t,residual))
    saf_balance = pd.DataFrame(saf_rows,columns=['location','period','residual_kg'])
    saf_balance.to_csv(out / 'physical_saf_balance.csv',index=False)
    saf_capacity = pd.read_csv(out / 'saf_capacity.csv').set_index(['location','technology']).value
    production_capacity = saf_table.set_index(['location','technology','period']).value
    saf_capacity_error = max(0,float((production_capacity-production_capacity.index.droplevel('period').map(saf_capacity)*3).max()))
    min_material = min(float(h2.min()),float(flows.value.min()),float(inventory.min()),float(saf_inventory.min()),float(saf_table.value.min()),float(deliveries.value.min()))
    cap = pd.read_csv(out / 'h2_capacity.csv').set_index('location').value
    h2_capacity_violation = max(0,float((h2-h2.index.get_level_values(0).map(cap)*3).max()))
    delivered = deliveries.groupby('week').value.sum()
    needed = demand.groupby('week_number').weekly_total_fuel_kg_total.sum()
    delivery_error = max(abs(float(delivered.get(row['week'],0))+row['shortage_kg']-float(needed[row['week']+1])) for row in summary['weekly'])
    report = {'scenario':scenario,'label':label,'resource_site_periods':len(electric),'max_electricity_deficit_mwh':float(max(electric.renewable_deficit_mwh.max(),electric.joint_deficit_mwh.max())),
              'electricity_violations_over_1e_5_mwh':int(((electric.renewable_deficit_mwh>1e-5)|(electric.joint_deficit_mwh>1e-5)).sum()),
              'zero_supply_hydrogen_kg':float(h2.reindex(electric.index).fillna(0)[electric.available_mwh==0].abs().sum()),
              'hydrogen_site_periods':len(balance),'max_hydrogen_balance_residual_kg':float(balance.residual_kg.abs().max()),
              'max_hydrogen_capacity_violation_kg':h2_capacity_violation,'max_demand_balance_error_kg':delivery_error,
              'max_mtj_energy_error_mwh':float(mtj_error),'max_dac_grid_scope_violation_mwh':dac_grid_violation,
              'max_initial_hydrogen_inventory_kg':float(initial_h2.abs().max()),'max_hydrogen_flow_capacity_violation_kg':max_flow_violation,'max_weekly_pipeline_volume_difference_kg':weekly_flow_difference,
              'max_saf_balance_residual_kg':float(saf_balance.residual_kg.abs().max()),'max_initial_saf_inventory_kg':float(saf_inventory.xs(0,level='period').abs().max()),'max_saf_capacity_violation_kg':saf_capacity_error,'minimum_material_quantity_kg':min_material,
              'uniform_weekly_pipeline_volume':True,'transport_timing':'Same three-hour interval at both ends; zero initial hydrogen inventory',
              'input_profile_validation':json.loads((base / 'raw_profile_validation.json').read_text())}
    report['passed'] = (report['max_electricity_deficit_mwh']<=1e-5 and report['max_hydrogen_balance_residual_kg']<=1e-4 and h2_capacity_violation<=1e-4 and delivery_error<=1e-3 and mtj_error<=1e-5 and dac_grid_violation<=1e-5)
    report['passed'] = report['passed'] and all(report[key]<=1e-4 for key in ['max_initial_hydrogen_inventory_kg','max_hydrogen_flow_capacity_violation_kg','max_weekly_pipeline_volume_difference_kg','max_saf_balance_residual_kg','max_initial_saf_inventory_kg','max_saf_capacity_violation_kg']) and min_material>=-1e-5
    if scenario == 'GTL-GH':
        ng_params = json.loads((out / 'natural_gas_parameters.json').read_text())
        ng = pd.read_csv(out / 'ng_flows.csv')
        allocations = pd.read_csv(out / 'ng_technology_flows.csv')
        assert ng_params['days']==28 and ng_params['periods_per_day']==8
        assert set(ng.day)==set(range(28)) and set(allocations.day)==set(range(28))
        routes = ng.groupby(['source','destination','day']).value.sum()
        allocated = allocations.groupby(['source','destination','day']).value.sum()
        allocation_error = float((routes-allocated.reindex(routes.index).fillna(0)).abs().max())
        ng_ratios = {tech:info['ng_consumption_ratio'] for tech,info in params['technologies'].items()}
        saf_table['ng_m3'] = saf_table.value*saf_table.technology.map(ng_ratios)
        saf_table['day'] = saf_table.period//8
        consumption = saf_table.groupby(['location','technology','day']).ng_m3.sum()
        incoming = allocations.groupby(['destination','technology','day']).value.sum()
        routed_tech = ['pipeline_direct_conversion','lng_to_hplant_conversion']
        selected = consumption.index.get_level_values('technology').isin(routed_tech)
        residual = consumption[selected]-incoming.reindex(consumption[selected].index).fillna(0)
        residual.rename('residual_m3').to_csv(out / 'physical_natural_gas_balance.csv')
        source_type_errors = 0
        for row in allocations.itertuples():
            allowed = config['transport_modes'][params['technologies'][row.technology]['transport_mode']]['suitable_sources']
            source_type_errors += int(params['locations'][row.source]['type'] not in allowed)
        outbound = ng.groupby(['source','day']).value.sum()
        direct = saf_table.groupby(['location','day']).ng_m3.sum()
        lng_excess = max([0.0]+[float(outbound.get((loc,day),0)+direct.get((loc,day),0)-capacity) for loc,capacity in ng_params['lng_daily_capacities_m3'].items() for day in range(28)])
        route_distance = pd.DataFrame(ng_params['routes']).set_index(['source','destination']).distance_km
        flow_distance = pd.MultiIndex.from_frame(ng[['source','destination']]).map(route_distance)
        ng_transport_carbon = float((ng.value*flow_distance*ng_params['truck_kg_co2_per_m3_km']).sum())
        ng_extraction_carbon = float(saf_table.ng_m3.sum()*ng_params['extraction_kg_co2_per_m3'])
        economics = config['economic_parameters']
        rate,years = economics['discount_rate'],economics['project_lifespan']
        pv = years if rate==0 else (1-(1+rate)**(-years))/rate
        ng_transport_cost = float((ng.value*(4.52e-4*flow_distance+0.927)).sum()*13*pv)
        ng_report = {'days':28,'periods_per_day':8,'daily_technology_balances':len(residual),'max_ng_allocation_residual_m3':allocation_error,'max_ng_daily_balance_residual_m3':float(residual.abs().max()),'max_ng_truck_capacity_violation_m3':max(0,float(ng.value.max())-ng_params['truck_daily_limit_m3']),'max_lng_daily_capacity_violation_m3':lng_excess,'ng_source_type_errors':source_type_errors,'max_ng_carbon_recalculation_error_kg':max(abs(ng_transport_carbon-summary['carbon_expressions']['ng_transport']),abs(ng_extraction_carbon-summary['carbon_expressions']['ng_extraction'])),'minimum_ng_flow_m3':min(float(ng.value.min()),float(allocations.value.min()))}
        ng_report['ng_transport_cost_recalculation_error_yuan'] = abs(ng_transport_cost-summary['cost_breakdown']['ng_transport_operation'])
        ng_report['passed'] = all(ng_report[key]<=1e-3 for key in ['max_ng_allocation_residual_m3','max_ng_daily_balance_residual_m3','max_ng_truck_capacity_violation_m3','max_lng_daily_capacity_violation_m3','max_ng_carbon_recalculation_error_kg','ng_transport_cost_recalculation_error_yuan']) and source_type_errors==0 and ng_report['minimum_ng_flow_m3']>=-1e-5
        report['natural_gas_validation'] = ng_report
        report['passed'] = report['passed'] and ng_report['passed']
    report['solution_summary_sha256'] = hashlib.sha256((out / 'summary.json').read_bytes()).hexdigest()
    (out / 'physical_validation.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report),flush=True)
    assert report['passed'],report
    return report


if __name__ == '__main__':
    validate_run(*sys.argv[1:3])
