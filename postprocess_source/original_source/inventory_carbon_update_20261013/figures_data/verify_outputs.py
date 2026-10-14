import hashlib
from pathlib import Path
from zipfile import ZipFile

import numpy as np
from PIL import Image

from update_carbon import HERE, PACKET, SOURCE, STAGE, RECORDS, read_json, read_csv, write_json, sha

source_hashes = read_json(HERE/'internal/source_hashes.json')
assert all(sha(SOURCE/name)==value for name,value in source_hashes.items())
unchanged_sources = [name for name in source_hashes if name.startswith(('inputs/','runs/'))]
assert all(sha(SOURCE/name)==sha(STAGE/name) for name in unchanged_sources)
audit = read_json(HERE.parent/'audit/all_site_inventory_carbon.json')['records']
all_sites = {(r['scenario'],r['label']):r for r in audit}
final_records = {(r['scenario'],r['label']):r for r in read_json(HERE.parent/'audit/final_inventory_carbon_ledger.json')['records']}
manifest = read_json(STAGE/RECORDS/'manifest.json')
pathway_checks = []
points = []
for name in manifest:
    old = read_json(SOURCE/RECORDS/f'{name}_carbon_emissions.json')
    new = read_json(STAGE/RECORDS/f'{name}_carbon_emissions.json')
    old_sol = read_json(SOURCE/RECORDS/f'{name}_complete_solution.json')
    new_sol = read_json(STAGE/RECORDS/f'{name}_complete_solution.json')
    assert abs(new['carbon_intensity_mj']-final_records[(name,'baseline')]['final_ci_g_mj'])<1e-10
    for key,value in old_sol.items():
        if key!='carbon_emissions':
            assert new_sol[key]==value,(name,key)
    for key,value in old['detailed'].items():
        if key not in ['mtj_storage','h2_storage']:
            assert new['detailed'][key]==value,(name,key)
    if name!='GTL':
        assert new['source_carbon_breakdown_raw']==old
        assert new_sol['source_carbon_emissions']==old_sol['carbon_emissions']
        assert all(new_sol['carbon_emissions'][key]==new[key] for key in old_sol['carbon_emissions'])
        if (name,'baseline') in all_sites:
            evidence = all_sites[(name,'baseline')]
            assert new['detailed']['h2_storage']==evidence['h2']['all_site_unit_corrected_carbon_kg_co2e']
            assert new['detailed']['mtj_storage']==evidence['saf']['all_site_unit_corrected_carbon_kg_co2e']
            assert np.isclose(new['carbon_intensity_mj'],evidence['all_site_corrected_ci_g_mj'],rtol=0,atol=1e-10)
        else:
            assert new['detailed']['mtj_storage']==old['detailed']['mtj_storage']*.003
            assert new['detailed']['h2_storage']==old['detailed']['h2_storage']*3
    else:
        assert sha(SOURCE/RECORDS/f'{name}_carbon_emissions.json')==sha(STAGE/RECORDS/f'{name}_carbon_emissions.json')
        assert sha(SOURCE/RECORDS/f'{name}_complete_solution.json')==sha(STAGE/RECORDS/f'{name}_complete_solution.json')
    assert abs(sum(new['detailed'].values())-new['by_stage']['total_emissions'])<.001,name
    assert np.isclose(new['carbon_intensity_mj'],new['by_stage']['total_emissions']/new['total_production_kg']*1000/43.15,rtol=0,atol=1e-10)
    assert np.isclose(new['abs_diff_vs_traditional_jet_gco2e_per_mj'],new['carbon_intensity_mj']-89,rtol=0,atol=1e-10)
    assert manifest[name]['normalized_carbon_sha256']==sha(STAGE/RECORDS/f'{name}_carbon_emissions.json')
    assert manifest[name]['normalized_solution_sha256']==sha(STAGE/RECORDS/f'{name}_complete_solution.json')
    pathway_checks.append({'scenario':name,'carbon_g_mj':new['carbon_intensity_mj'],
        'cost_cny_kg':new_sol['lifecycle_levelized_cost_excluding_shortage_per_kg'],'carbon_ledger_sum_passed':True,
        'all_cost_and_dispatch_fields_preserved':True,'inventory_location_scope':manifest[name]['carbon_accounting'].get('inventory_location_scope','GTL zero SAF storage')})
    points.append((name,new['carbon_intensity_mj'],new_sol['lifecycle_levelized_cost_excluding_shortage_per_kg']))
assert next(r['cost_cny_kg'] for r in pathway_checks if r['scenario']=='GTL-BH')==5.290539354389216
for path in (SOURCE/'figure_data/figures_cost').rglob('*'):
    if path.is_file():
        assert sha(path)==sha(STAGE/path.relative_to(SOURCE)),path
for path in (SOURCE/'figure_data/figures_space_time_temporal_data').rglob('*'):
    if path.is_file():
        assert sha(path)==sha(STAGE/path.relative_to(SOURCE)),path
run_checks = []
before,after = read_csv(SOURCE/'pathway_results.csv'),read_csv(STAGE/'pathway_results.csv')
for a,b in zip(before,after):
    assert all(a[k]==b[k] for k in a if k not in ['carbon_intensity_kg_kg','carbon_intensity_g_mj'])
    evidence = all_sites[(b['scenario'],b['label'])]
    assert np.isclose(float(b['carbon_intensity_g_mj']),evidence['all_site_corrected_ci_g_mj'],rtol=0,atol=1e-10)
    run_checks.append({'scenario':b['scenario'],'label':b['label'],'carbon_g_mj':float(b['carbon_intensity_g_mj'])})
for row in read_csv(STAGE/'figure_data/figures_space_time_network_data/scenario_integrated_metrics.csv'):
    ci = next(r['carbon_g_mj'] for r in pathway_checks if r['scenario']==row['Scenario'])
    assert np.isclose(float(row['CarbonDiffVsJet']),ci-89,rtol=0,atol=1e-10)
frontier,best = [],float('inf')
for name,carbon,cost in sorted(points,key=lambda x:(x[1],x[2])):
    if cost<best:
        frontier.append(name)
        best=cost
assert set(frontier)=={'CCU-GH-FT','GTL','GTL-BH'}
inventory_index_path = STAGE/'figure_data/inventory_records/index.json'
inventory_index = read_json(inventory_index_path)
assert len(inventory_index['records']) == 24
assert inventory_index['period_hours'] == 3
for item in inventory_index['records']:
    evidence = all_sites[(item['scenario'],item['label'])]
    assert sha(inventory_index_path.parent/item['csv']) == item['sha256'] == evidence[item['stock']]['sha256']
    assert sha(STAGE/item['source_summary']) == item['source_summary_sha256'] == evidence['summary_sha256']
    assert item['period_hours'] == 3
    assert item['inventory_state_count'] == 225
integrity = read_json(STAGE/'SHA256.json')
assert set(integrity) == {p.relative_to(STAGE).as_posix() for p in STAGE.rglob('*') if p.is_file() and p.name != 'SHA256.json'}
assert all(sha(STAGE/name)==value for name,value in integrity.items())
mapping = read_json(HERE/'image_replacements.json')['image_replacements']
embed_matches = []
for path in PACKET.rglob('*.docx'):
    with ZipFile(path) as archive:
        for part in archive.namelist():
            if not part.startswith('word/media/'):
                continue
            digest = hashlib.sha256(archive.read(part)).hexdigest()
            for item in mapping:
                if digest==item['old_sha256']:
                    embed_matches.append({'document':str(path.relative_to(PACKET)),'part':part,'figure':item['figure']})
for item in mapping:
    assert sha(Path(item['new_image']))==item['new_sha256']
    assert Image.open(item['old_image']).size==Image.open(item['new_image']).size,item['figure']
    assert any(m['figure']==item['figure'] for m in embed_matches),item['figure']
result = {'status':'passed','source_input_files_preserved':len(source_hashes),
    'inputs_and_runs_bytes_preserved':len(unchanged_sources),'pathways':pathway_checks,'copt_runs':run_checks,
    'cost_learning_and_sensitivity_data_bytes_preserved':True,'temporal_metrics_bytes_preserved':True,
    'selected_nondominated_set':frontier,'lhv_mj_per_kg':43.15,'stage_sha256_passed':True,
    'raw_inventory_csv_count':len(inventory_index['records']),'inventory_raw_and_summary_hashes_passed':True,
    'stage_integrity_sha256':sha(STAGE/'SHA256.json'),'stage_file_count':len(integrity)+1,
    'affected_image_count':len(mapping),'latest_document_image_matches':embed_matches,
    'all_image_dimensions_preserved':True,'new_optimization_performed':False}
write_json(HERE/'data_verification.json',result)
print('PASSED',len(pathway_checks),'pathways;',len(run_checks),'COPT accounts;',len(mapping),'figures;',len(embed_matches),'embedded image matches')
