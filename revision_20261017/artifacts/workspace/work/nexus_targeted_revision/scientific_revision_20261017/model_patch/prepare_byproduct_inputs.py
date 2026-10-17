import argparse
import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd


def prepare(archive_directory, output_directory):
    root = Path(archive_directory).resolve()
    if os.name == 'nt':
        root = Path('\\\\?\\' + str(root))
    relative = Path('archived_outputs/products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen')
    paths = [root / relative / 'one_step/renewable_energy_plants_20260201_205000.csv',
             root / relative / 'two_step/renewable_energy_plants_20260201_204929.csv']
    tables = [pd.read_csv(path, encoding='utf-8-sig').sort_values('位置ID').reset_index(drop=True) for path in paths]
    columns = ['位置ID', '发电站类型', '纬度', '经度', '装机容量(MW)', '平均发电量(MW)', '最大发电量(MW)', '最小发电量(MW)']
    assert all(set(columns) <= set(table.columns) for table in tables)
    pd.testing.assert_frame_equal(tables[0][columns], tables[1][columns], check_exact=False, rtol=1e-12, atol=1e-12)
    table = tables[0]
    assert table['位置ID'].is_unique
    assert set(table['发电站类型']) <= {'钢铁副产氢', '炼油副产氢'}
    for column in ['平均发电量(MW)', '最大发电量(MW)', '最小发电量(MW)']:
        assert np.allclose(table[column], table['装机容量(MW)'], rtol=1e-12, atol=1e-12), column
    assert np.isfinite(table[['纬度', '经度', '装机容量(MW)']].to_numpy()).all()
    assert (table['装机容量(MW)'] >= 0).all()
    rows = []
    for source in table.to_dict('records'):
        name = source['位置ID']
        kind = 'byproduct_hydrogen_steel' if source['发电站类型'] == '钢铁副产氢' else 'byproduct_hydrogen_refinery'
        rate = float(source['装机容量(MW)'])
        for period in range(224):
            rows.append({'plant_name': name, 'type': kind, 'latitude': source['纬度'], 'longitude': source['经度'],
                         'capacity_mw': rate, 'power_output_mw': rate, 'h2_available_kg_per_hour': rate,
                         'period': period, 'week': period // 56, 'hours_per_period': 3})
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    target = output / 'byproduct_hydrogen_periods.csv'
    pd.DataFrame(rows).to_csv(target, index=False)
    report = {
        'source_kind': 'Archived full candidate input-location table; not selected built facilities',
        'source_files': [{'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()} for path in paths],
        'source_export_function': 'dac_hydrogen_optimization_model.py:_save_infrastructure_locations iterates all self.locations; no built-facility filter',
        'unit_basis': 'Original _process_byproduct_h2_source stores h2_daily_tonnes * available_rate * 1000 / 24 in power_output_mw and capacity_mw',
        'constant_profile_verified': True,
        'ft_mtj_all_candidate_tables_match': True,
        'candidate_sites': len(table), 'three_hour_periods': 224,
        'source_types': table['发电站类型'].value_counts().to_dict(),
        'available_h2_kg_per_hour': float(table['装机容量(MW)'].sum()),
        'available_h2_kg_per_four_weeks': float(table['装机容量(MW)'].sum()) * 672,
        'raw_industrial_csv_scope': 'Not present in the supplied historical archive; original constant model inputs reconstructed from the saved full input-location tables',
        'output': str(target.resolve()), 'output_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
    }
    (output / 'byproduct_input_provenance.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('archive_directory')
    parser.add_argument('output_directory')
    arguments = parser.parse_args()
    prepare(arguments.archive_directory, arguments.output_directory)
