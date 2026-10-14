from pathlib import Path
import shutil

from update_carbon import HERE, STAGE, read_json, write_json, sha


before = {p.relative_to(STAGE).as_posix(): sha(p) for p in STAGE.rglob('*') if p.is_file()}
audit = read_json(HERE.parent/'audit/all_site_inventory_carbon.json')['records']
assert len(audit) == 12
destination = STAGE/'figure_data/inventory_records'
records = []
for item in audit:
    summary = Path('runs')/item['scenario']/item['label']/'summary.json'
    summary_sha = sha(STAGE/summary)
    assert summary_sha == item['summary_sha256'] == item['matching_inventory_summary_sha256']
    for stock in ('saf', 'h2'):
        evidence = item[stock]
        source = Path(evidence['raw_file'])
        assert sha(source) == evidence['sha256'], source
        relative = Path(item['scenario'])/item['label']/f'{stock}_inventory.csv'
        target = destination/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        assert sha(target) == evidence['sha256']
        records.append({
            'scenario': item['scenario'], 'label': item['label'], 'stock': stock,
            'csv': relative.as_posix(), 'sha256': evidence['sha256'],
            'source_summary': summary.as_posix(), 'source_summary_sha256': summary_sha,
            'period_hours': 3, 'inventory_state_count': item['inventory_state_count'],
            'location_count': evidence['total_locations'],
            'coverage': 'All saved locations, including hydrogen supply and receiving locations.'
        })
index = {
    'period_hours': 3, 'represented_hours': 672, 'stock_unit': 'kg',
    'columns': {'location': 'Model location identifier', 'period': 'Saved stock-state index, 0 through 224', 'value': 'Inventory in kilograms'},
    'inventory_state_count': 225,
    'scope': {
        'electricity_dependent_configurations': 'Six configurations, each with baseline and summer_fixed schedules. Original SAF and hydrogen inventory arrays cover all saved locations, including hydrogen supply and receiving locations.',
        'archived_byproduct_hydrogen_comparators': 'Six comparators use their saved SAF inventory ledger and the hydrogen-supply locations represented in the archived hydrogen inventory expressions. Receiving-location hydrogen arrays are unavailable and are outside that archived accounting coverage; no replacement arrays are supplied.',
        'GTL': 'The reported SAF inventory-emission term is zero.'
    },
    'accounting_files_relative_to_data_root': ['inventory_carbon_accounting.csv', 'run_carbon_accounting.csv', 'inventory_energy_accounting_details.json'],
    'records': records
}
write_json(destination/'index.json', index)
readme_path = STAGE/'README.txt'
readme = readme_path.read_text(encoding='utf-8')
line = 'Original SAF and hydrogen stock records for the twelve electricity-dependent schedules are in figure_data/inventory_records/; index.json identifies their source summaries and checksums, and inventory_carbon_accounting.csv, run_carbon_accounting.csv and inventory_energy_accounting_details.json provide the corresponding final carbon accounts.'
if line not in readme:
    readme_path.write_text(readme.rstrip()+'\n\n'+line+'\n', encoding='utf-8')
for name, digest in before.items():
    if name not in ('README.txt', 'SHA256.json') and not name.startswith('figure_data/inventory_records/'):
        assert sha(STAGE/name) == digest, name
integrity = {p.relative_to(STAGE).as_posix(): sha(p) for p in sorted(STAGE.rglob('*')) if p.is_file() and p.name != 'SHA256.json'}
write_json(STAGE/'SHA256.json', integrity)
impact_path = HERE/'dependency_impact.json'
impact = read_json(impact_path)
impact['stage_integrity_sha256'] = sha(STAGE/'SHA256.json')
write_json(impact_path, impact)
write_json(HERE/'inventory_records_delivery.json', {
    'status': 'passed', 'inventory_csv_count': len(records), 'inventory_index_sha256': sha(destination/'index.json'),
    'stage_integrity_sha256': sha(STAGE/'SHA256.json'), 'stage_file_count': len(integrity)+1,
    'existing_data_preserved_except_readme_and_integrity_manifest': True,
    'inputs_and_runs_bytes_preserved': True,
    'records': records
})
print('Copied', len(records), 'inventory CSV files; total stage files:', len(integrity)+1)
print('SHA256.json:', sha(STAGE/'SHA256.json'))
