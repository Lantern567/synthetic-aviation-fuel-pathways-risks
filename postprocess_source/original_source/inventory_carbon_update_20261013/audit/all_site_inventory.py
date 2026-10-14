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
raw = base / 'inventory_cost_review_20261012/raw_inventory'
units = json.loads((out / 'unit_corrected_inventory_carbon.json').read_text(encoding='utf-8'))
records = []
source_types = {'solar_plant', 'wind_farm', 'byproduct_hydrogen_steel', 'byproduct_hydrogen_refinery'}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


for scenario in ['CCU-GH-FT', 'CCU-GH-MTJ', 'DAC-GH-FT', 'DAC-GH-MTJ', 'GTL-GH', 'CTL']:
    for label in ['baseline', 'summer_fixed']:
        folder = raw / scenario / label
        inputs = data / 'runs' / scenario / label
        assert (inputs / 'summary.json').read_bytes() == (folder / 'summary.json').read_bytes(), (scenario, label)
        summary = json.loads((inputs / 'summary.json').read_text(encoding='utf-8'))
        config = yaml.safe_load((inputs / 'config.yaml').read_text(encoding='utf-8'))
        params = json.loads((inputs / 'model_parameters.json').read_text(encoding='utf-8'))
        carbon_config = config['carbon_emission_parameters']
        renewable = carbon_config['renewable_energy']
        fallback = (renewable['wind_power_intensity'] + renewable['solar_power_intensity']) / 2
        duration = config['basic_parameters']['hours_per_period']
        energy = carbon_config['benchmarks']['saf_energy_content']
        storage = carbon_config['storage_handling']
        row = {'scenario': scenario, 'label': label, 'summary_sha256': digest(inputs / 'summary.json'), 'matching_inventory_summary_sha256': digest(folder / 'summary.json'),
               'storage_electricity_ci_kg_kwh': fallback, 'period_hours': duration, 'inventory_state_count': 225,
               'electricity_factor_basis': '沿用原储存表达式的动态强度函数；真实轨迹精确重构原已报告项，确认这批结果使用风/光参数50%-50%均值；无另加电网/购电归属假设',
               'source_hydrogen_location_types': sorted(source_types)}
        for commodity, field, energy_unit in [('saf', 'mtj_storage', storage['mtj_storage_energy']), ('h2', 'h2_storage', storage['h2_storage_energy'])]:
            file = folder / f'{commodity}_inventory.csv'
            table = pd.read_csv(file)
            assert not table.duplicated(['location', 'period']).any()
            assert table['period'].min() == 0 and table['period'].max() == 224
            assert table.groupby('location').size().eq(225).all()
            assert np.isfinite(table['value']).all()
            location_type = table['location'].map(lambda name: params['locations'][name]['type'])
            in_scope = location_type.isin(source_types) if commodity == 'h2' else pd.Series(True, index=table.index)
            original_reconstructed = (table.loc[in_scope, 'value'] * energy_unit / 24 * fallback).sum()
            old = summary['carbon_expressions'][field]
            assert np.isclose(original_reconstructed, old, rtol=1e-12, atol=1e-5), (scenario, label, commodity, original_reconstructed, old)
            divisor = 1000 if commodity == 'saf' else 1
            all_site_carbon = float((table['value'] * energy_unit / 24 * duration / divisor * fallback).sum())
            recorded_site_carbon = old * duration / divisor
            missing_site_carbon = all_site_carbon - recorded_site_carbon
            by_type = {}
            for type_name, indexes in location_type.groupby(location_type).groups.items():
                part = table.loc[indexes]
                by_type[type_name] = {
                    'inventory_kg_period_sum': float(part['value'].sum()),
                    'emissions_kg_co2e': float(part['value'].sum() * energy_unit / 24 * duration / divisor * fallback),
                    'positive_site_count': int(part.groupby('location')['value'].max().gt(1e-6).sum()),
                }
            row[commodity] = {'raw_file': str(file), 'sha256': digest(file), 'total_locations': int(table.location.nunique()),
                              'source_scope_locations': int(table.loc[in_scope, 'location'].nunique()),
                              'positive_locations': int(table.groupby('location')['value'].max().gt(1e-6).sum()),
                              'outside_original_scope_positive_locations': int(table.loc[~in_scope].groupby('location')['value'].max().gt(1e-6).sum()),
                              'outside_original_scope_inventory_kg_period_sum': float(table.loc[~in_scope, 'value'].sum()),
                              'old_reported_carbon_kg_co2e': old, 'original_formula_reconstructed_carbon_kg_co2e': float(original_reconstructed),
                              'reconstruction_residual_kg_co2e': float(original_reconstructed - old),
                              'unit_corrected_original_scope_carbon_kg_co2e': recorded_site_carbon,
                              'all_site_unit_corrected_carbon_kg_co2e': all_site_carbon,
                              'additional_non_source_site_carbon_kg_co2e': missing_site_carbon,
                              'initial_inventory_sum_kg': float(table.loc[table.period == 0, 'value'].sum()),
                              'terminal_inventory_sum_kg': float(table.loc[table.period == 224, 'value'].sum()),
                              'by_location_type': by_type}
        old_total = summary['carbon_aggregates']['total_emissions']
        old_storage = summary['carbon_expressions']['mtj_storage'] + summary['carbon_expressions']['h2_storage']
        new_storage = sum(row[key]['all_site_unit_corrected_carbon_kg_co2e'] for key in ['saf', 'h2'])
        new_total = old_total - old_storage + new_storage
        row.update(all_site_corrected_storage_carbon_kg_co2e=new_storage, all_site_corrected_total_carbon_kg_co2e=new_total,
                   all_site_corrected_ci_g_mj=new_total / summary['production_kg'] / energy * 1000,
                   all_site_corrected_storage_ci_g_mj=new_storage / summary['production_kg'] / energy * 1000,
                   additional_h2_non_source_site_ci_g_mj=row['h2']['additional_non_source_site_carbon_kg_co2e'] / summary['production_kg'] / energy * 1000,
                   cost_cny_kg_unchanged=summary['cost_per_kg_excluding_shortage'],
                   scope='对匹配最新版summary的真实SAF/H2库存数组逐地点核算；保持原报告库存状态求和与电力碳强度规则、调度和成本。未新增运输中库存。MeOH/CO2原模型未定义独立库存能源项，另作范围说明。')
        records.append(row)
        print(scenario, label, 'CI', f"{row['all_site_corrected_ci_g_mj']:.9f}", 'H2 extra', f"{row['additional_h2_non_source_site_ci_g_mj']:.9f}", 'sites', row['h2']['outside_original_scope_positive_locations'])
(out / 'all_site_inventory_carbon.json').write_text(json.dumps({'records': records, 'scope': '真实库存数组只读静态核算，匹配最新版输入；不重新优化、不调整成本'}, ensure_ascii=False, indent=2), encoding='utf-8')
simple = [{key: value for key, value in row.items() if isinstance(value, (str, int, float))} for row in records]
with (out / 'all_site_inventory_carbon.csv').open('w', encoding='utf-8-sig', newline='') as stream:
    writer = csv.DictWriter(stream, fieldnames=list(simple[0]))
    writer.writeheader()
    writer.writerows(simple)
