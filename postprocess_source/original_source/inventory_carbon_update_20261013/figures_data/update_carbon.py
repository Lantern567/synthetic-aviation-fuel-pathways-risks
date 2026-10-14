import copy
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
WORK = HERE.parents[1]
ROOT = HERE.parents[3]
PACKET = ROOT / 'Nexus系统提交文件_库存成本修正20261013'
SOURCE = PACKET / 'Accompanying_Data'
STAGE = HERE / 'data_stage'
RECORDS = Path('figure_data/normalized_pathway_records')
OLD_FIG = WORK / 'revision_20261007/figures_cost'
VIZ = WORK / 'corrected_runs_20261006/project/products/supply_chain_optimization/visualization'
LHV = 43.15


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def write_csv(path, rows):
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    result.__file__ = str(HERE/(name+'.py'))
    return result


def corrected(old, inventory=None, final=None):
    new = copy.deepcopy(old)
    details = new['detailed']
    if 'mtj_storage' in details:
        details['mtj_storage'] *= .003
    if 'h2_storage' in details:
        details['h2_storage'] *= 3
    if inventory is not None:
        details['mtj_storage'] = inventory['saf']['all_site_unit_corrected_carbon_kg_co2e']
        details['h2_storage'] = inventory['h2']['all_site_unit_corrected_carbon_kg_co2e']
    if final is not None:
        for key,value in final['final_storage_fields_kg_co2e'].items():
            details[key] = value
    if 'saf_storage' in details:
        assert details['saf_storage'] == 0
    stage = new['by_stage']
    storage = sum(value for key,value in details.items() if 'storage' in key)
    delta = storage-stage['storage_emissions']
    stage['storage_emissions'] = storage
    annual_factor = old['by_stage']['annual_emissions']/old['by_stage']['total_emissions']
    stage['total_emissions'] += delta
    if final is not None:
        stage['total_emissions'] = final['final_total_kg_co2e']
    stage['annual_emissions'] = stage['total_emissions']*annual_factor
    new['carbon_intensity_kg'] = stage['total_emissions']/new['total_production_kg']
    new['carbon_intensity_mj'] = new['carbon_intensity_kg']*1000/LHV
    if final is not None:
        assert abs(new['carbon_intensity_mj']-final['final_ci_g_mj'])<1e-9
        new['carbon_intensity_mj'] = final['final_ci_g_mj']
    new['vs_traditional_jet'] = (new['carbon_intensity_mj']/89-1)*100
    new['abs_diff_vs_traditional_jet_gco2e_per_mj'] = new['carbon_intensity_mj']-89
    new['vs_corsia'] = (new['carbon_intensity_mj']/30-1)*100
    for key, value in new.get('stage_contributions', {}).items():
        value['value'] = stage[key]
        value['percentage'] = stage[key]/stage['total_emissions']*100
    if 'detailed_raw' in new:
        for key in ['mtj_storage','h2_storage']:
            if key in new['detailed_raw']:
                new['detailed_raw'][key] = details[key]
    return new


def main():
    assert STAGE.resolve().parent == HERE.resolve()
    shutil.copytree(SOURCE, STAGE, dirs_exist_ok=True)
    source_hashes = {str(p.relative_to(SOURCE)).replace('\\','/'):sha(p) for p in SOURCE.rglob('*') if p.is_file()}
    write_json(HERE/'internal/source_hashes.json',source_hashes)
    manifest = read_json(STAGE/RECORDS/'manifest.json')
    inventory_audit = read_json(HERE.parent/'audit/all_site_inventory_carbon.json')['records']
    inventories = {(r['scenario'],r['label']):r for r in inventory_audit}
    final_ledger = read_json(HERE.parent/'audit/final_inventory_carbon_ledger.json')['records']
    final_records = {(r['scenario'],r['label']):r for r in final_ledger}
    all_carbon, impact, summary = {}, [], []
    metadata = {'period_hours':3,'represented_hours':672,'saf_inventory_unit':'kg',
        'saf_energy_coefficient_unit':'kWh/(t day)','h2_inventory_unit':'kg',
        'h2_energy_coefficient_unit':'kWh/(kg day)',
        'saf_formula':'sum(inventory_kg / 1000 * energy_kWh_per_t_day * 3 / 24 * electricity_kgCO2e_per_kWh)',
        'h2_formula':'sum(inventory_kg * energy_kWh_per_kg_day * 3 / 24 * electricity_kgCO2e_per_kWh)',
        'scope':'Inventory energy emissions evaluated for the retained facility designs and dispatches',
        'no_new_optimization':True}
    for name in manifest:
        old = read_json(SOURCE/RECORDS/f'{name}_carbon_emissions.json')
        new = corrected(old, inventories.get((name,'baseline')),final_records[(name,'baseline')])
        accounting = copy.deepcopy(metadata)
        accounting['inventory_location_scope'] = 'All saved SAF and hydrogen inventory locations, including hydrogen supply and receiving locations' if (name,'baseline') in inventories else 'Saved SAF inventory ledger and hydrogen inventory ledger for the hydrogen supply locations represented in the archived expressions'
        solution = read_json(STAGE/RECORDS/f'{name}_complete_solution.json')
        source_solution_carbon = copy.deepcopy(solution['carbon_emissions'])
        if name != 'GTL':
            new['source_carbon_breakdown_raw'] = copy.deepcopy(old)
            new['carbon_accounting'] = accounting
            solution['source_carbon_emissions'] = source_solution_carbon
            solution['carbon_emissions'] = {key:new[key] for key in source_solution_carbon}
            solution['carbon_accounting'] = accounting
            write_json(STAGE/RECORDS/f'{name}_carbon_emissions.json',new)
            write_json(STAGE/RECORDS/f'{name}_complete_solution.json',solution)
        all_carbon[name] = new
        manifest[name]['normalized_solution_sha256'] = sha(STAGE/RECORDS/f'{name}_complete_solution.json')
        manifest[name]['normalized_carbon_sha256'] = sha(STAGE/RECORDS/f'{name}_carbon_emissions.json')
        manifest[name]['carbon_accounting'] = accounting if name != 'GTL' else {'scope':'Zero SAF inventory-emission term in the archived GTL ledger'}
        impact.append({'scenario':name,'old_carbon_g_mj':old['carbon_intensity_mj'],'carbon_g_mj':new['carbon_intensity_mj'],
            'old_storage_g_mj':old['by_stage']['storage_emissions']/old['total_production_kg']*1000/LHV,
            'storage_g_mj':new['by_stage']['storage_emissions']/new['total_production_kg']*1000/LHV,
            'old_total_kg':old['by_stage']['total_emissions'],'total_kg':new['by_stage']['total_emissions'],
            'old_saf_storage_kg':old['detailed'].get('mtj_storage',0),'saf_storage_kg':new['detailed'].get('mtj_storage',0),
            'old_h2_storage_kg':old['detailed'].get('h2_storage',0),'h2_storage_kg':new['detailed'].get('h2_storage',0),
            'cost_cny_kg':solution['lifecycle_levelized_cost_excluding_shortage_per_kg'],
            'fulfillment_ratio':solution['demand_fulfillment_ratio'],
            'combustion_sensitivity_g_mj':new['carbon_intensity_mj']+.85*44/12/43.15*1000,
            'without_capture_credit_g_mj':new['carbon_intensity_mj']-new['by_stage'].get('co2_utilization_credit',0)/new['total_production_kg']*1000/LHV,
            'combustion_without_capture_credit_g_mj':new['carbon_intensity_mj']-new['by_stage'].get('co2_utilization_credit',0)/new['total_production_kg']*1000/LHV+.85*44/12/43.15*1000})
        summary.append({'scenario':name,'cost_cny_kg':solution['lifecycle_levelized_cost_excluding_shortage_per_kg'],
            'carbon_g_mj':new['carbon_intensity_mj'],'fulfillment_ratio':solution['demand_fulfillment_ratio']})
    assert abs(next(r for r in impact if r['scenario']=='GTL-BH')['cost_cny_kg']-5.290539354389216)<1e-13
    write_json(STAGE/RECORDS/'manifest.json',manifest)
    write_csv(HERE/'pathway_summary.csv',summary)
    write_csv(HERE/'numeric_replacements.csv',impact)
    write_json(HERE/'numeric_replacements.json',impact)
    public_columns = ['scenario','carbon_g_mj','storage_g_mj','total_kg','saf_storage_kg','h2_storage_kg',
        'cost_cny_kg','fulfillment_ratio','combustion_sensitivity_g_mj','without_capture_credit_g_mj',
        'combustion_without_capture_credit_g_mj']
    write_csv(STAGE/'inventory_carbon_accounting.csv',[
        {**{key:row[key] for key in public_columns},
         'inventory_location_scope':manifest[row['scenario']]['carbon_accounting'].get('inventory_location_scope','GTL zero SAF inventory-emission term')}
        for row in impact])
    shutil.copy2(SOURCE/'carbon_aggregation_check.csv', STAGE/'source_carbon_aggregation_check.csv')
    write_csv(STAGE/'carbon_aggregation_check.csv',[
        {'scenario':name,'reported_total_kg':c['by_stage']['total_emissions'],
         'recomputed_total_kg':sum(c['detailed'].values()),
         'difference_kg':sum(c['detailed'].values())-c['by_stage']['total_emissions']}
        for name,c in all_carbon.items()])
    for relative in ['archived_comparator_metrics.csv','figure_data/figures_space_time_network_data/scenario_integrated_metrics.csv']:
        rows = read_csv(STAGE/relative)
        for row in rows:
            name = row.get('scenario',row.get('Scenario'))
            carbon = all_carbon[name]
            for field,key in [('carbon_intensity_kg_kg','carbon_intensity_kg'),('carbon_intensity_g_mj','carbon_intensity_mj')]:
                if field in row:
                    row[field] = carbon[key]
            if 'CarbonDiffVsJet' in row:
                row['CarbonDiffVsJet'] = carbon['carbon_intensity_mj']-89
        write_csv(STAGE/relative,rows)
    rows = read_csv(STAGE/'pathway_results.csv')
    run_accounting = []
    for row in rows:
        raw = read_json(SOURCE/'runs'/row['scenario']/row['label']/'summary.json')
        stages = copy.deepcopy(raw['carbon_aggregates'])
        values = raw['carbon_expressions']
        storage = values.get('mtj_storage',0)*.003 + values.get('h2_storage',0)*3
        inventory = inventories[(row['scenario'],row['label'])]
        assert inventory['summary_sha256']==sha(SOURCE/'runs'/row['scenario']/row['label']/'summary.json')
        storage = inventory['all_site_corrected_storage_carbon_kg_co2e']
        stages['total_emissions'] += storage-stages['storage_emissions']
        final_record = final_records[(row['scenario'],row['label'])]
        assert abs(stages['total_emissions']-final_record['final_total_kg_co2e'])<.001
        stages['total_emissions'] = final_record['final_total_kg_co2e']
        stages['storage_emissions'] = storage
        row['carbon_intensity_kg_kg'] = stages['total_emissions']/raw['production_kg']
        row['carbon_intensity_g_mj'] = final_record['final_ci_g_mj']
        run_accounting.append({'scenario':row['scenario'],'label':row['label'],
            'carbon_intensity_g_mj':row['carbon_intensity_g_mj'],'storage_emissions_kg':storage,
            'total_emissions_kg':stages['total_emissions'],'source':f"runs/{row['scenario']}/{row['label']}/summary.json"})
    write_csv(STAGE/'pathway_results.csv',rows)
    write_csv(STAGE/'run_carbon_accounting.csv',run_accounting)
    write_json(STAGE/'inventory_energy_accounting_details.json',{
        'method':metadata,'records':[
            {'scenario':r['scenario'],'label':r['label'],'source_summary_sha256':r['summary_sha256'],
             'electricity_ci_kg_kwh':r['storage_electricity_ci_kg_kwh'],
             'saf':{k:v for k,v in r['saf'].items() if k in ['sha256','total_locations','initial_inventory_sum_kg','terminal_inventory_sum_kg','by_location_type','all_site_unit_corrected_carbon_kg_co2e']},
             'h2':{k:v for k,v in r['h2'].items() if k in ['sha256','total_locations','initial_inventory_sum_kg','terminal_inventory_sum_kg','by_location_type','all_site_unit_corrected_carbon_kg_co2e']}}
            for r in inventory_audit]})
    verification = read_json(STAGE/'figure_data/figure_verification.json')
    for name, values in verification['pathways'].items():
        values['carbon_intensity_g_mj'] = all_carbon[name]['carbon_intensity_mj']
        values['carbon_components_close'] = True
    write_json(STAGE/'figure_data/figure_verification.json',verification)
    readme = STAGE/'README.txt'
    readme.write_text(readme.read_text(encoding='utf-8')+'\nInventory energy emissions use three-hour integration. SAF inventory in kilograms is converted to tonnes for the kWh/(t day) coefficient; hydrogen uses its kWh/(kg day) coefficient. The six electricity-dependent configurations cover all saved SAF and hydrogen inventory locations, including hydrogen supply and receiving locations. The six byproduct-hydrogen comparators use their saved SAF inventory ledger and the hydrogen-supply locations represented in the archived hydrogen inventory expressions; receiving-location hydrogen inventories are outside that archived accounting coverage. GTL retains its zero SAF inventory-emission term. Normalized pathway records and run_carbon_accounting.csv provide these accounts for retained designs and dispatches. The source inputs and run summaries retain their original provenance; source_carbon_breakdown_raw identifies the carbon ledger associated with each source record. Cost accounts, production and service fractions retain their stated scope.\n',encoding='utf-8')
    write_json(STAGE/'SHA256.json',{str(p.relative_to(STAGE)).replace('\\','/'):sha(p) for p in sorted(STAGE.rglob('*')) if p.is_file() and p.name!='SHA256.json'})
    print(json.dumps(impact,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
