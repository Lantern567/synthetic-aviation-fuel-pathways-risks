import gc
import argparse
import hashlib
import importlib
import importlib.metadata
import json
import logging
import sqlite3
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import yaml

from corrected_model import CorrectedModelMixin
from dac_co2_conservation import DacCO2ConservationMixin
from weekly_hydrogen_accounting import WeeklyHydrogenAccountingMixin
from inventory_hours import InventoryHoursMixin

base = Path(__file__).resolve().parent
project = base / 'project'
parser = argparse.ArgumentParser()
parser.add_argument('scenario')
parser.add_argument('label', choices=['baseline', 'summer_fixed'])
parser.add_argument('--export-model', action='store_true')
parser.add_argument('--certificate', action='store_true')
parser.add_argument('--threads', type=int, default=16)
parser.add_argument('--time-limit', type=float, default=14400)
parser.add_argument('--gap', type=float, default=0.005)
args = parser.parse_args()
scenario, label = args.scenario, args.label
external_values = None
settings = {
    'CCU-GH-FT':('green_hydrogen_supply_chain_optimization','green_hydrogen_optimization_model','GreenHydrogenSupplyChainOptimizer','shared/data/GreenHydrogenSupplyChainOptimizer_config.yaml','one_step'),
    'CCU-GH-MTJ':('green_hydrogen_supply_chain_optimization','green_hydrogen_optimization_model','GreenHydrogenSupplyChainOptimizer','shared/data/GreenHydrogenSupplyChainOptimizer_config_two_step.yaml','two_step'),
    'DAC-GH-FT':('dac_hydrogen_saf_supply_chain_optimization','dac_hydrogen_optimization_model','DACHydrogenSAFOptimizer','shared/config/DACHydrogenSAFOptimizer_config.yaml','one_step'),
    'DAC-GH-MTJ':('dac_hydrogen_saf_supply_chain_optimization','dac_hydrogen_optimization_model','DACHydrogenSAFOptimizer','shared/config/DACHydrogenSAFOptimizer_config_two_step.yaml','two_step'),
    'DAC-BH-FT':('dac_hydrogen_saf_supply_chain_optimization','dac_hydrogen_optimization_model','DACHydrogenSAFOptimizer','shared/data/DACByproductHydrogenSAFOptimizer_config_one_step.yaml','one_step'),
    'DAC-BH-MTJ':('dac_hydrogen_saf_supply_chain_optimization','dac_hydrogen_optimization_model','DACHydrogenSAFOptimizer','shared/data/DACByproductHydrogenSAFOptimizer_config_two_step.yaml','two_step'),
    'GTL-GH':('natural_gas_supply_chain_optimization','natural_gas_optimization_model','NaturalGasSupplyChainOptimizer','shared/data/NaturalGasSupplyChainOptimizer_config.yaml',None),
    'CTL':('coal_hydrogen_saf_optimization','coal_hydrogen_optimization_model','CoalHydrogenSAFOptimizer','products/supply_chain_optimization/coal_hydrogen_saf_optimization/data/CoalHydrogenSAFOptimizer_config.yaml',None),
}
family, module_name, class_name, config_relative, mode = settings[scenario]
family_path = project / 'products/supply_chain_optimization' / family
sys.path[:0] = [str(project),str(family_path),str(family_path / 'src'),str(base.parent / 'copt_migration')]
module = importlib.import_module(f'core.{module_name}')
from validate_algebra import validate


class ArchivedRoadRoutes:
    def __init__(self):
        database = project / 'shared/data/cache/graphhopper_routes/route_cache.db'
        with sqlite3.connect(f'file:{database}?mode=ro',uri=True) as connection:
            self.routes = {row[0]:row[1:] for row in connection.execute('select cache_key,distance_km,time_hours,route_coordinates,method_used from route_cache')}
        self.calls = 0
        self.new_routes = base / 'routing/new_routes.jsonl'
        if self.new_routes.exists():
            for line in self.new_routes.read_text().splitlines():
                record = json.loads(line)
                self.routes[record['key']] = record['route']

    def calculate_route_distance(self,start_lat,start_lon,end_lat,end_lon,vehicle='truck',include_route_geometry=True):
        self.calls += 1
        if abs(start_lat-end_lat)<1e-6 and abs(start_lon-end_lon)<1e-6:
            return {'distance_km':0,'time_hours':0,'route_found':True,'route_coordinates':[[start_lon,start_lat]],'method':'same_point'}
        key = hashlib.md5(f'{start_lat:.6f},{start_lon:.6f},{end_lat:.6f},{end_lon:.6f},{vehicle}'.encode()).hexdigest()
        if key not in self.routes:
            response = requests.get('http://127.0.0.1:18989/route',params=[('point',f'{start_lat},{start_lon}'),('point',f'{end_lat},{end_lon}'),('profile',vehicle),('points_encoded','false'),('instructions','false')],timeout=60)
            if not response.ok:
                raise RuntimeError((start_lat,start_lon,end_lat,end_lon,response.status_code,response.text))
            response.raise_for_status()
            route = response.json()['paths'][0]
            self.routes[key] = [route['distance']/1000,route['time']/3600000,json.dumps(route['points']['coordinates']),'graphhopper_api']
            with self.new_routes.open('a') as stream:
                stream.write(json.dumps({'key':key,'start':[start_lat,start_lon],'end':[end_lat,end_lon],'route':self.routes[key],'snapped_waypoints':route['snapped_waypoints'],'source':'GraphHopper 10.2, original China OSM and truck profile; index.max_region_search=50'})+'\n')
        distance,hours,geometry,method = self.routes[key]
        assert method == 'graphhopper_api' and np.isfinite(distance) and distance >= 0, key
        return {'distance_km':distance,'time_hours':hours,'route_found':True,'route_coordinates':json.loads(geometry) if geometry and include_route_geometry else [],'method':'archived_graphhopper_api'}


if scenario.startswith('DAC-BH-'):
    from byproduct_hydrogen import ByproductHydrogenMixin

    class Optimizer(InventoryHoursMixin,WeeklyHydrogenAccountingMixin,DacCO2ConservationMixin,ByproductHydrogenMixin,CorrectedModelMixin,getattr(module,class_name)):
        pass
else:
    class Optimizer(InventoryHoursMixin,WeeklyHydrogenAccountingMixin,DacCO2ConservationMixin,CorrectedModelMixin,getattr(module,class_name)):
        pass


def value(item):
    if isinstance(item,(int,float)):
        return float(item)
    if external_values is None:
        return float(item.getValue() if hasattr(item,'getValue') else item.x)
    if hasattr(item,'getIdx'):
        return float(external_values[item.getIdx()])
    return float(item.getConstant()+sum(item.getCoeff(i)*external_values[item.getVar(i).getIdx()] for i in range(item.getSize())))


def export(mapping,path,columns):
    records = []
    for key,var in mapping.items():
        parts = key if isinstance(key,tuple) else (key,)
        assert len(parts) == len(columns)
        records.append(dict(zip(columns,parts),value=value(var)))
    pd.DataFrame(records).to_csv(path,index=False)


def main():
    global external_values
    import_certificate = '--certificate' in sys.argv
    out = base / ('verified_runs' if import_certificate else 'runs') / scenario / label
    out.mkdir(parents=True,exist_ok=True)
    (out / 'EXPORT_IN_PROGRESS').write_text('Building and verifying output files')
    inputs = base / 'inputs' / ('baseline' if label in ('baseline','warm_baseline') else 'summer')
    config = yaml.safe_load((project / config_relative).read_text())
    config['solver_parameters'].update(TimeLimit=args.time_limit,Threads=args.threads,MIPGap=args.gap,LpMethod=2)
    config['basic_parameters'].update(time_horizon_weeks=4,periods_per_week=56,hours_per_period=3)
    config['data_paths']['aviation_data']['airport_excel_path'] = str(inputs / 'airport_input.xlsx')
    snapshot = out / 'source'
    snapshot.mkdir(exist_ok=True)
    execution_sources = [Path(__file__),base / 'corrected_model.py',base / 'dac_co2_conservation.py',base / 'weekly_hydrogen_accounting.py',base / 'inventory_hours.py',family_path / 'src/core' / (module_name+'.py')]
    if scenario.startswith('DAC-BH-'):
        execution_sources.append(base / 'byproduct_hydrogen.py')
    for source in execution_sources:
        (snapshot / source.name).write_bytes(source.read_bytes())
    (out / 'input_sha256.json').write_bytes((base / 'input_sha256.json').read_bytes())
    (out / 'config.yaml').write_text(yaml.safe_dump(config,allow_unicode=True,sort_keys=False))
    logging.basicConfig(level=logging.INFO)
    kwargs = {'config_path':str(out / 'config.yaml'),'parallel_workers':4}
    if mode:
        kwargs['process_mode'] = mode
    opt = Optimizer(**kwargs)
    opt.corrected_input, opt.scenario = inputs, scenario
    scope_path = base / 'diagnostic_scope.json'
    opt.diagnostic_scope = json.loads(scope_path.read_text()) if scope_path.exists() else {}
    opt.initial_solution_mode = label.startswith('warm_')
    opt.routing_engine = ArchivedRoadRoutes()
    resource_file = 'byproduct_hydrogen_periods.csv' if scenario.startswith('DAC-BH-') else 'renewable_periods.csv'
    renewable = pd.read_csv(inputs / resource_file)
    opt.is_renewable_data_prefiltered = True
    opt.load_data_from_excel(renewable_data=renewable)
    assert opt.total_hours == 224 and opt.hours_per_period == 3
    for name,group in renewable.groupby('plant_name'):
        assert np.allclose(opt.locations[name]['hourly_generation'],group.sort_values('period').power_output_mw,rtol=1e-12,atol=1e-12),name
    print('DATA_READY',scenario,label,len(opt.locations),flush=True)
    opt.build_model()
    for name, parameter in {'TimeLimit':args.time_limit,'Threads':args.threads,'RelGap':args.gap}.items():
        opt.model.setParam(name,parameter)
    if label == 'summer_fixed':
        fixed_count = 0
        baseline = base / 'verified_runs' / scenario / 'baseline'
        if not (baseline / 'summary.json').exists():
            baseline = base / 'runs' / scenario / 'baseline'
        for file,mapping,columns in [('saf_capacity',opt.facility_capacity_vars,['location','technology']),('h2_capacity',opt.electrolyzer_capacity_vars,['location']),('saf_build',opt.facility_vars,['location','technology']),('h2_build',opt.electrolyzer_facility_vars,['location'])]:
            table = pd.read_csv(baseline / f'{file}.csv')
            for record in table.to_dict('records'):
                key = tuple(record[c] for c in columns) if len(columns)>1 else record[columns[0]]
                opt.model.addConstr(mapping[key] == record['value'],name=f'fixed_{file}_{fixed_count}')
                fixed_count += 1
        if hasattr(opt,'dac_facility_vars'):
            values = pd.read_csv(baseline / 'variables.csv',usecols=['variable','value']).set_index('variable').value
            for location,var in opt.dac_facility_vars.items():
                opt.model.addConstr(var==float(values.loc[var.getName()]),name=f'fixed_dac_build_{location}')
    opt.model.setLogFile(str(out / 'copt.log'))
    print('MODEL_READY',scenario,label,opt.model.getAttr('Cols'),opt.model.getAttr('Rows'),flush=True)
    if import_certificate:
        certificate_path = base / 'decomposed_runs' / scenario / label
        certificate = json.loads((certificate_path / 'certificate.json').read_text())
        assert certificate['passed'],certificate
        source_model = base / 'runs' / scenario / label / 'model.mps.gz'
        assert hashlib.sha256(source_model.read_bytes()).hexdigest()==certificate['source_sha256']
        archive_model = opt.solver_environment.createModel('certificate_variable_map')
        archive_model.read(str(source_model))
        archive_names = [var.getName() for var in archive_model.getVars()]
        assert hashlib.sha256('\n'.join(archive_names).encode()).hexdigest()==certificate['column_name_sha256']
        archive_values = np.load(certificate_path / 'values.npz')['values']
        archive_lookup = {name:i for i,name in enumerate(archive_names)}
        names = [var.getName().replace(' ','_') for var in opt.model.getVars()]
        assert len(set(names))==len(names) and set(names)==set(archive_names),{'new_only':list(set(names)-set(archive_names))[:10],'archived_only':list(set(archive_names)-set(names))[:10]}
        external_values = archive_values[[archive_lookup[name] for name in names]].copy()
        routes = [name for name in archive_names if name.startswith('h2_pipeline_transport_')]
        route_lookup = {name:i for i,name in enumerate(routes)}
        archived_flow_indices = [i for i,name in enumerate(archive_names) if name.startswith('corrected_h2_flow_')]
        archived_flow_indices.sort(key=lambda i:int(archive_names[i].rsplit('_',1)[1]))
        assert len(archived_flow_indices)==224*len(routes)
        for (source_name,destination,t),var in opt.hydrogen_period_flow_vars.items():
            route_name = f'h2_pipeline_transport_{source_name}_{destination}_week'.replace(' ','_')
            external_values[var.getIdx()] = archive_values[archived_flow_indices[route_lookup[route_name]*224+t]]
        del archive_model,archive_lookup,archive_names,archive_values,archived_flow_indices
        assert np.isclose(value(opt.model.getObjective()),certificate['objective'],rtol=1e-10,atol=1e-3)
        (out / 'certificate.json').write_bytes((certificate_path / 'certificate.json').read_bytes())
    else:
        opt.model.write(str(out / 'model.mps'))
        subprocess.run(['gzip','-1',str(out / 'model.mps')],check=True)
        if '--export-model' in sys.argv:
            (out / 'MODEL_EXPORTED').write_text('Full model exported for certified projected optimization')
            print('MODEL_EXPORTED',scenario,label,flush=True)
            return
        opt.model.solve()
    summary = {'scenario':scenario,'label':label,'solver':'COPT','version':importlib.metadata.version('coptpy'),'status':opt.model.status,'has_solution':bool(opt.model.getAttr('HasSol')),'seconds':opt.model.getAttr('SolvingTime'),'columns':opt.model.getAttr('Cols'),'rows':opt.model.getAttr('Rows'),'route_calls':opt.routing_engine.calls,'electricity_scope':opt.electricity_scope,'initial_solution_only':opt.initial_solution_mode,'fixed_production_assets':label=='summer_fixed','fixed_asset_scope':'SAF and electrolyzer build/capacity; DAC build where present. Auxiliary inventory/transport use retains original optimization rules.'}
    if import_certificate:
        summary.update(status='verified_decomposition_certificate',has_solution=True,seconds=certificate['seconds'],method=certificate['method'])
    summary['model_scope'] = opt.diagnostic_scope or {'original_minimum_service_constraints_retained':True}
    summary['seconds_scope'] = 'Final full-model dispatch solve only' if import_certificate else 'Native solver elapsed time'
    (out / 'solver_status.json').write_text(json.dumps(summary,indent=2))
    assert summary['has_solution'],summary
    if import_certificate:
        summary.update(objective=certificate['objective'],gap=certificate['gap'],lower_bound=certificate['lower_bound'])
    else:
        opt.model.write(str(out / 'solution.sol'))
        summary.update(objective=opt.model.ObjVal,gap=opt.model.getAttr('BestGap'),lower_bound=opt.model.getAttr('ObjBound'))
    manifest = json.loads((inputs / 'manifest.json').read_text())
    capacity = sum(value(v) for v in opt.facility_capacity_vars.values())
    production = sum(value(v) for v in opt.production_vars.values())
    assert production > 1, ('No usable production incumbent',summary)
    h2_capacity = sum(value(v) for v in opt.electrolyzer_capacity_vars.values())
    demand = sum(sum(info['weekly_demand_series'][:4]) for info in opt.airports.values())
    assert np.isclose(demand,manifest['demand_kg'],atol=1e-6)
    shortage = sum(value(v) for v in opt.shortage_vars.values())
    metrics = {key:value(expr) for key,expr in {**opt.cost_expressions,**opt.cost_aggregates}.items()}
    metrics['demand_fulfillment_ratio'] = 1-shortage/demand
    years,rate = opt.economic_params['project_lifespan'],opt.economic_params['discount_rate']
    pv = years if rate == 0 else (1-(1+rate)**(-years))/rate
    summary.update(production_kg=production,demand_kg=demand,shortage_kg=shortage,demand_fulfillment_ratio=1-shortage/demand,saf_capacity_kg_h=capacity,h2_capacity_kg_h=h2_capacity,cost_per_kg_excluding_shortage=metrics['total_cost_excluding_shortage']/(production*13*pv),cost_breakdown=metrics)
    summary['objective_gap_relative_to_cost_excluding_shortage'] = (summary['objective']-summary['lower_bound'])/metrics['total_cost_excluding_shortage']
    weekly = []
    for w in range(4):
        amount = sum(value(v) for (loc,tech,t),v in opt.production_vars.items() if t//56 == w)
        supplied = sum(value(v) for (loc,airport,week),v in opt.transport_vars.items() if week == w)
        weekly.append({'week':w,'source_week':manifest['weeks'][w],'production_kg':amount,'delivered_kg':supplied,'utilization':amount/(capacity*168),'shortage_kg':sum(value(v) for (airport,week),v in opt.shortage_vars.items() if week == w)})
    summary['weekly'] = weekly
    summary['mean_utilization'] = production/(capacity*672)
    summary['worst_week_retention'] = min(row['utilization'] for row in weekly)/summary['mean_utilization']
    summary['carbon_expressions'] = {name:value(expr) for name,expr in opt.carbon_expressions.items()}
    summary['carbon_aggregates'] = {name:value(expr) for name,expr in opt.carbon_aggregates.items()}
    (out / 'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    mappings = [
        ('saf_production',opt.production_vars,['location','technology','period']),('h2_production',opt.hydrogen_production_vars,['location','period']),
        ('saf_capacity',opt.facility_capacity_vars,['location','technology']),('h2_capacity',opt.electrolyzer_capacity_vars,['location']),
        ('saf_build',opt.facility_vars,['location','technology']),('h2_build',opt.electrolyzer_facility_vars,['location']),
        ('deliveries',opt.transport_vars,['location','airport','week']),('h2_inventory',opt.hydrogen_storage_vars,['location','period']),
        ('h2_flows',opt.hydrogen_period_flow_vars,['source','destination','period']),('saf_inventory',opt.storage_vars,['location','period']),
        ('shortages',opt.shortage_vars,['airport','week']),
    ]
    for name,mapping,columns in mappings:
        export(mapping,out / f'{name}.csv',columns)
    for attribute in ['dac_co2_supply','dac_grid_electricity_vars','mtj_renewable_electricity_vars','mtj_grid_electricity_vars']:
        if hasattr(opt,attribute):
            export(getattr(opt,attribute),out / f'{attribute}.csv',['location','period'])
    if scenario.startswith('DAC-'):
        opt.export_co2_balance_audit(out,value)
    opt.export_hydrogen_transport_audit(out,value)
    opt.export_inventory_cost_audit(out,value)
    if scenario.startswith('DAC-BH-'):
        opt.export_byproduct_supply_audit(out,value)
    if scenario == 'GTL-GH':
        export(opt.ng_transport_vars,out / 'ng_flows.csv',['source','destination','day'])
        export(opt.ng_transport_by_technology_vars,out / 'ng_technology_flows.csv',['source','destination','technology','day'])
        (out / 'natural_gas_parameters.json').write_text(json.dumps({'days':opt.ng_days,'periods_per_day':opt.ng_periods_per_day,'truck_daily_limit_m3':opt.ng_truck_daily_limit,'lng_daily_capacities_m3':opt.ng_daily_capacities,'extraction_kg_co2_per_m3':opt.carbon_params['raw_materials']['ng_extraction_intensity'],'truck_kg_co2_per_m3_km':opt.carbon_params['transportation']['ng_truck_intensity']/100,'routes':[{'source':s,'destination':d,'distance_km':distance} for (s,d),distance in opt.ng_route_distances.items()],'scope':'28 daily balances; technology-specific source allocation; each aggregate route counted once; configured truck capacities; airport city-pipeline supply retains implicit unlimited availability; overall pipeline withdrawal capacity remains disabled as in retained model; road routes retain unlimited distance.'},ensure_ascii=False,indent=2))
    (out / 'model_parameters.json').write_text(json.dumps({'technologies':opt.technologies,'costs':opt.costs,'carbon_parameters':opt.carbon_params,'economic_parameters':opt.economic_params,'periods':opt.total_hours,'hours_per_period':opt.hours_per_period,'weeks':opt.time_horizon_weeks,'locations':{name:{'type':info['type'],'latitude':info['latitude'],'longitude':info['longitude']} for name,info in opt.locations.items()},'dac_kwh_per_kg':getattr(opt,'corrected_dac_kwh_per_kg',None)},ensure_ascii=False,indent=2,default=float))
    summary['algebraic_validation'] = validate(opt.model,out,external_values)
    (out / 'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    print('RUN_COMPLETE',scenario,label,json.dumps({k:v for k,v in summary.items() if k not in ('carbon_expressions','cost_breakdown','weekly')}),flush=True)
    (out / 'EXPORT_IN_PROGRESS').unlink()
    model, environment = opt.model,opt.solver_environment
    del mappings,mapping
    opt.__dict__.clear()
    del opt
    gc.collect()
    del model
    gc.collect()
    del environment


if __name__ == '__main__':
    main()
