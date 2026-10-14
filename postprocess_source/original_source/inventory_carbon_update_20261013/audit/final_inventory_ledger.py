import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


out = Path(__file__).resolve().parent
base = out.parents[1]
project = base.parents[1]
data = project / 'Nexus系统提交文件_库存成本修正20261013/Accompanying_Data'
normalized = data / 'figure_data/normalized_pathway_records'
archive = Path('\\\\?\\' + str(base / 'github_archive/repository'))
units = json.loads((out / 'unit_corrected_inventory_carbon.json').read_text(encoding='utf-8'))
full = json.loads((out / 'all_site_inventory_carbon.json').read_text(encoding='utf-8'))
full_by_case = {(row['scenario'], row['label']): row for row in full['records']}
manifest = json.loads((normalized / 'manifest.json').read_text(encoding='utf-8'))
results = []
archive_inventory_checks = []


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


for row in units['records']:
    result = dict(row)
    case = row['scenario'], row['label']
    if case in full_by_case:
        checked = full_by_case[case]
        fields = {'mtj_storage': checked['saf']['all_site_unit_corrected_carbon_kg_co2e'], 'h2_storage': checked['h2']['all_site_unit_corrected_carbon_kg_co2e']}
        result.update(final_storage_fields_kg_co2e=fields, final_total_kg_co2e=checked['all_site_corrected_total_carbon_kg_co2e'],
                      final_ci_g_mj=checked['all_site_corrected_ci_g_mj'], final_storage_ci_g_mj=checked['all_site_corrected_storage_ci_g_mj'],
                      added_receiving_h2_kg_co2e=checked['h2']['additional_non_source_site_carbon_kg_co2e'],
                      added_receiving_h2_ci_g_mj=checked['additional_h2_non_source_site_ci_g_mj'],
                      storage_electricity_ci_kg_kwh=checked['storage_electricity_ci_kg_kwh'],
                      h2_storage_scope='All recorded hydrogen-supply and receiving locations',
                      raw_inventory_source_hashes={key: checked[key]['sha256'] for key in ['saf', 'h2']},
                      scope_evidence_file='all_site_inventory_carbon.json',
                      coverage_status='All saved SAF and H2 stock arrays included; the same storage-electricity factor rule and dispatch are retained')
    else:
        scenario = row['scenario']
        source = archive / 'archived_outputs/products/supply_chain_optimization' / manifest[scenario]['source']
        source_hash = digest(source)
        assert source_hash == manifest[scenario]['source_sha256'], (scenario, source_hash)
        original = json.loads(source.read_text(encoding='utf-8'))
        latest_solution = json.loads((normalized / f'{scenario}_complete_solution.json').read_text(encoding='utf-8'))
        assert original['inventory'] == latest_solution['inventory'], scenario
        source_carbon = original['carbon_emissions']
        for field, amount in row['original_storage_fields_kg_co2e'].items():
            assert source_carbon['detailed'][field] == amount, (scenario, field)
        config = yaml.safe_load(Path(row['config_file']).read_text(encoding='utf-8'))
        carbon_params = config['carbon_emission_parameters']
        renewable = carbon_params.get('renewable_energy', {})
        fallback = (renewable.get('wind_power_intensity', .015) + renewable.get('solar_power_intensity', .045)) / 2
        inventory = pd.DataFrame(original['inventory'].values())
        inventory_sum = float(inventory['inventory_kg'].sum())
        saf_parameter = carbon_params['storage_handling'].get('mtj_storage_energy', carbon_params['storage_handling'].get('saf_storage_energy'))
        reconstruction = inventory_sum * saf_parameter / 24 * fallback
        old_saf = row['original_storage_fields_kg_co2e'].get('mtj_storage', row['original_storage_fields_kg_co2e'].get('saf_storage'))
        if scenario != 'GTL':
            assert np.isclose(reconstruction, old_saf, rtol=1e-12, atol=1e-5), (scenario, reconstruction, old_saf)
        else:
            assert inventory_sum < 1e-6 and old_saf == 0
        entry = {'scenario': scenario, 'original_source_file': str(source), 'original_source_sha256': source_hash,
                 'normalized_inventory_identical_to_source': True, 'positive_record_count': len(inventory),
                 'inventory_sum_kg_states': inventory_sum, 'inventory_hours_kg_hour': inventory_sum * row['period_hours'],
                 'saf_energy_kwh_t_day': saf_parameter, 'configured_storage_electricity_ci_kg_kwh': fallback,
                 'original_saf_carbon_kg_co2e': old_saf, 'reconstructed_original_saf_carbon_kg_co2e': reconstruction,
                 'saf_reconstruction_residual_kg_co2e': reconstruction - old_saf,
                 'static_corrected_saf_carbon_kg_co2e': old_saf * row['saf_factor'],
                 'H2_stock_arrays_saved': False, 'MeOH_stock_arrays_saved': False,
                 'H2_reconstruction_identifiability': 'Aggregated annual production and aggregated transport do not determine period-level receiving inventories; none inferred or inserted',
                 'SAF_stock_scope': 'All positive saved final SAF inventories; mtj_storage is the final fuel stock, not intermediate methanol',
                 'GTL_zero_scope': 'Original FT report sets saf_storage to zero; actual saved stock is numerical roundoff only' if scenario == 'GTL' else None}
        archive_inventory_checks.append(entry)
        result.update(final_storage_fields_kg_co2e=row['unit_corrected_storage_fields_kg_co2e'],
                      final_total_kg_co2e=row['unit_corrected_total_kg_co2e'], final_ci_g_mj=row['unit_corrected_ci_g_mj'],
                      final_storage_ci_g_mj=row['unit_corrected_storage_g_mj'], added_receiving_h2_kg_co2e=None,
                      added_receiving_h2_ci_g_mj=None, storage_electricity_ci_kg_kwh=fallback,
                      h2_storage_scope='Source-location storage represented in the saved archived ledger' if scenario != 'GTL' else 'No standalone hydrogen stock item in GTL FT report',
                      raw_inventory_source_hashes={'original_complete_solution': source_hash}, scope_evidence_file='archive_inventory_reconstruction.json',
                      coverage_status='Saved SAF stock independently reconstructed; H2 source-location ledger corrected using documented period length; receiving stock not inferred')
    results.append(result)
assert len(results) == 19
gtlbh = next(row for row in results if row['scenario'] == 'GTL-BH')
assert abs(gtlbh['final_ci_g_mj'] - 87.34169131743451) < 1e-9
assert abs(gtlbh['cost_cny_kg_unchanged'] - 5.290539354389216) < 1e-12
payload = {
    'input_version': str(data),
    'method': 'Static inventory electricity account for retained capacities, output, dispatch and cost. SAF energy rates use tonnes and period hours/24 days; H2 rates use kilograms and the same duration. Emission weighting follows the configured storage-electricity rule.',
    'hydrogen_scope_definition': 'Archived BH comparators cover source-location storage represented in the saved ledger; electricity-dependent configurations include inventories at both supply and receiving locations.',
    'methanol_co2_scope': 'No separate MeOH/CO2 inventory electricity expression or storage-energy coefficient is defined in these source ledgers. The mtj_storage field represents final SAF stock. No unsupported new coefficients or stock values are inserted.',
    'time_stock_convention': 'The existing saved stock-state summation is retained, with each indexed state multiplied by 3 h. No transport-in-transit stock is added. H2 endpoint totals are documented in all_site_inventory_carbon.json.',
    'records': results,
}
(out / 'final_inventory_carbon_ledger.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
(out / 'archive_inventory_reconstruction.json').write_text(json.dumps({'records': archive_inventory_checks}, ensure_ascii=False, indent=2), encoding='utf-8')
simple = [{key: row.get(key) for key in ['scenario', 'label', 'origin', 'final_ci_g_mj', 'final_storage_ci_g_mj', 'cost_cny_kg_unchanged', 'storage_electricity_ci_kg_kwh', 'h2_storage_scope', 'added_receiving_h2_ci_g_mj']} for row in results]
with (out / 'final_inventory_carbon_ledger.csv').open('w', encoding='utf-8-sig', newline='') as stream:
    writer = csv.DictWriter(stream, fieldnames=list(simple[0]))
    writer.writeheader()
    writer.writerows(simple)
print(json.dumps(simple, ensure_ascii=False, indent=2))
