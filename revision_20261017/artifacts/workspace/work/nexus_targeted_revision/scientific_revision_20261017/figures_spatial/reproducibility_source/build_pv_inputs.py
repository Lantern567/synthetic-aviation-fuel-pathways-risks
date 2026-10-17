import argparse
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path):
    return pd.read_csv(path, float_precision='round_trip')


parser = argparse.ArgumentParser()
parser.add_argument('--source-compute', required=True, type=Path)
parser.add_argument('--raw-solar', required=True, type=Path)
parser.add_argument('--source-twelve-weeks', required=True, type=Path)
parser.add_argument('--parameters', type=Path, default=Path(__file__).resolve().parents[2] / 'pv_inputs/pv_parameters.json')
parser.add_argument('--output', required=True, type=Path)
args = parser.parse_args()
out = args.output.resolve()
out.mkdir(parents=True, exist_ok=True)
source = args.source_compute.resolve()
assert source != out
parameters = json.loads(args.parameters.read_text(encoding='utf-8'))
if args.parameters.resolve() != out / 'pv_parameters.json':
    shutil.copyfile(args.parameters, out / 'pv_parameters.json')
inventory_path = source / 'solar_grid_mapping.csv'
inventory = read_csv(inventory_path)
assert len(inventory) == 66 and inventory.GEM_phase_ID.nunique() == 66
assert inventory.Project_Name.nunique() == 65
assert abs(inventory.Capacity__MW_.sum() - 748.6) < 1e-8
assert set(inventory.Capacity_Rating) == {'MWp/dc', 'MWac', 'unknown'}

# 保留原始容量标注；未知标注统一采用已声明的 DC 假设。
phase_capacity = inventory[['GEM_phase_ID', 'Project_Name', 'Capacity__MW_', 'Capacity_Rating', 'Latitude', 'Longitude', 'longitude_index', 'latitude_index', 'grid_longitude', 'grid_latitude']].rename(columns={'GEM_phase_ID': 'phase_id', 'Project_Name': 'plant_name', 'Capacity__MW_': 'capacity_raw_mw', 'Capacity_Rating': 'capacity_rating_raw'})
phase_capacity['capacity_rating_assumed'] = phase_capacity.capacity_rating_raw.replace({'unknown': 'MWp/dc'})
phase_capacity['capacity_dc_mw'] = phase_capacity.capacity_raw_mw * np.where(phase_capacity.capacity_rating_raw.eq('MWac'), parameters['dc_ac_ratio'], 1.0)
phase_capacity['capacity_ac_mw'] = phase_capacity.capacity_dc_mw / parameters['dc_ac_ratio']
phase_capacity.loc[phase_capacity.capacity_rating_raw.eq('MWac'), 'capacity_ac_mw'] = phase_capacity.loc[phase_capacity.capacity_rating_raw.eq('MWac'), 'capacity_raw_mw']
phase_capacity['capacity_rule'] = np.where(phase_capacity.capacity_rating_raw.eq('unknown'), 'Unknown source rating; assumed DC for this study', np.where(phase_capacity.capacity_rating_raw.eq('MWac'), 'Reported AC retained; DC inferred using DC/AC = 1.2', 'Reported DC retained; AC inferred using DC/AC = 1.2'))
phase_capacity.to_csv(out / 'solar_phase_capacity.csv', index=False)

raw = read_csv(args.raw_solar)
assert len(raw) == 66 * 2016
assert not raw.duplicated(['phase_id', 'source_week', 'source_hour_in_week']).any()
assert (raw.groupby('phase_id').size() == 2016).all()
assert set(raw.phase_id) == set(phase_capacity.phase_id)
assert np.allclose(raw.irradiance_wm2, raw.radiation_raw / 36, rtol=0, atol=2e-12)
assert np.allclose(raw.power_output_mw, raw.capacity_mw * raw.irradiance_wm2 / 1000 * 0.1632, rtol=1e-12, atol=1e-12)
raw = raw.merge(phase_capacity.drop(columns='plant_name'), on='phase_id', validate='many_to_one')
assert np.array_equal(raw.capacity_mw, raw.capacity_raw_mw)
old_hourly = raw.groupby(['plant_name', 'source_week', 'source_hour_in_week'], as_index=False).power_output_mw.sum()
old_hourly['source_period'] = old_hourly.source_hour_in_week // 3
old_period = old_hourly.groupby(['plant_name', 'source_week', 'source_period']).power_output_mw.mean()

# 输出 AC 功率；逆变器效率只在 DC 转 AC 时使用一次。
raw['unclipped_ac_power_mw'] = raw.capacity_dc_mw * raw.irradiance_wm2 / parameters['reference_irradiance_wm2'] * (1 - parameters['system_loss_fraction']) * parameters['inverter_efficiency']
raw['corrected_ac_power_mw'] = np.minimum(raw.unclipped_ac_power_mw, raw.capacity_ac_mw)
assert np.isfinite(raw.corrected_ac_power_mw).all() and (raw.corrected_ac_power_mw >= 0).all()
assert (raw.corrected_ac_power_mw <= raw.capacity_ac_mw + 1e-12).all()
assert (raw.loc[raw.radiation_raw.eq(0), 'corrected_ac_power_mw'] == 0).all()
clipped = raw.unclipped_ac_power_mw > raw.capacity_ac_mw
hourly = raw.groupby(['plant_name', 'source_week', 'source_hour_in_week'], as_index=False).agg(power_output_mw=('corrected_ac_power_mw', 'sum'), capacity_raw_mw=('capacity_raw_mw', 'sum'), capacity_dc_mw=('capacity_dc_mw', 'sum'), capacity_ac_mw=('capacity_ac_mw', 'sum'))
hourly['source_period'] = hourly.source_hour_in_week // 3
period = hourly.groupby(['plant_name', 'source_week', 'source_period'], as_index=False).agg(power_output_mw=('power_output_mw', 'mean'), capacity_raw_mw=('capacity_raw_mw', 'first'), capacity_dc_mw=('capacity_dc_mw', 'first'), capacity_ac_mw=('capacity_ac_mw', 'first'))
assert abs(period.power_output_mw.sum() * 3 - hourly.power_output_mw.sum()) < 1e-8
period['capacity_mw'] = period.capacity_ac_mw
period.to_csv(out / 'solar_corrected_periods.csv', index=False)

twelve = read_csv(args.source_twelve_weeks)
solar_mask = twelve.type.eq('solar_plant')
index_columns = ['plant_name', 'source_week', 'source_period']
solar_index = pd.MultiIndex.from_frame(twelve.loc[solar_mask, index_columns])
assert not solar_index.duplicated().any()
assert np.allclose(twelve.loc[solar_mask, 'power_output_mw'], old_period.reindex(solar_index), rtol=1e-12, atol=1e-12)
updated = period.set_index(index_columns).reindex(solar_index)
twelve['capacity_raw_mw'] = twelve.capacity_mw
twelve['capacity_dc_mw'] = 0.0
twelve['capacity_ac_mw'] = twelve.capacity_mw
for column in ['power_output_mw', 'capacity_mw', 'capacity_raw_mw', 'capacity_dc_mw', 'capacity_ac_mw']:
    twelve.loc[solar_mask, column] = updated[column].to_numpy()
assert twelve.plant_name.nunique() == 109 and len(twelve) == 109 * 12 * 56
assert np.isfinite(twelve.select_dtypes('number')).all().all()
assert (twelve.power_output_mw <= twelve.capacity_mw + 1e-12).all()
twelve.to_csv(out / 'renewable_12weeks.csv', index=False)

schedule_report = {}
for label in ['baseline', 'summer']:
    old_input = source / 'inputs' / label
    schedule = read_csv(old_input / 'renewable_periods.csv')
    schedule_solar = schedule.type.eq('solar_plant')
    target_index = pd.MultiIndex.from_frame(schedule.loc[schedule_solar, index_columns])
    assert np.allclose(schedule.loc[schedule_solar, 'power_output_mw'], old_period.reindex(target_index), rtol=1e-12, atol=1e-12)
    before_wind = schedule.loc[~schedule_solar].copy()
    schedule['capacity_raw_mw'] = schedule.capacity_mw
    schedule['capacity_dc_mw'] = 0.0
    schedule['capacity_ac_mw'] = schedule.capacity_mw
    new_values = period.set_index(index_columns).reindex(target_index)
    assert not new_values.isna().any().any()
    for column in ['power_output_mw', 'capacity_mw', 'capacity_raw_mw', 'capacity_dc_mw', 'capacity_ac_mw']:
        schedule.loc[schedule_solar, column] = new_values[column].to_numpy()
    assert schedule.loc[~schedule_solar, before_wind.columns].equals(before_wind)
    assert len(schedule) == 109 * 224
    destination = out / 'inputs' / label
    destination.mkdir(parents=True, exist_ok=True)
    schedule_path = destination / 'renewable_periods.csv'
    schedule.to_csv(schedule_path, index=False)
    roundtrip = read_csv(schedule_path)
    assert np.array_equal(roundtrip.loc[~schedule_solar, 'power_output_mw'], before_wind.power_output_mw)
    for demand_name in ['airport_input.csv', 'airport_input.xlsx']:
        shutil.copyfile(old_input / demand_name, destination / demand_name)
        assert sha256(old_input / demand_name) == sha256(destination / demand_name)
    manifest = json.loads((old_input / 'manifest.json').read_text())
    old_solar_energy = manifest['energy_mwh']['solar_plant']
    manifest['energy_mwh'] = (schedule.groupby('type').power_output_mw.sum() * 3).to_dict()
    manifest['capacity_mw'] = schedule.drop_duplicates('plant_name').groupby('type').capacity_mw.sum().to_dict()
    manifest['solar_capacity_raw_mw'] = float(phase_capacity.capacity_raw_mw.sum())
    manifest['solar_capacity_dc_mw'] = float(phase_capacity.capacity_dc_mw.sum())
    manifest['solar_capacity_ac_mw'] = float(phase_capacity.capacity_ac_mw.sum())
    manifest['solar_conversion'] = parameters['power_formula']
    manifest['solar_capacity_mapping'] = parameters['dc_capacity_mapping']
    manifest['solar_engineering_parameters'] = {key: parameters[key] for key in ['system_loss_fraction', 'inverter_efficiency', 'dc_ac_ratio', 'unknown_capacity_rating_assumption']}
    manifest['solar_model_scope'] = parameters['scope']
    manifest['solar_parameter_sources'] = parameters['primary_sources']
    manifest['source_input_sha256'] = sha256(old_input / 'renewable_periods.csv')
    (destination / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    schedule_report[label] = {
        'weeks': manifest['weeks'],
        'periods': 224,
        'hours': 672,
        'solar_energy_mwh': manifest['energy_mwh']['solar_plant'],
        'solar_energy_before_mwh': old_solar_energy,
        'wind_energy_mwh': manifest['energy_mwh']['wind_farm'],
        'solar_capacity_factor_ac': manifest['energy_mwh']['solar_plant'] / manifest['solar_capacity_ac_mw'] / 672,
        'solar_capacity_factor_dc': manifest['energy_mwh']['solar_plant'] / manifest['solar_capacity_dc_mw'] / 672,
        'renewable_periods_sha256': sha256(schedule_path),
        'demand_preserved_byte_for_byte': True,
        'wind_values_preserved_exactly': True,
    }

shutil.copyfile(source / 'solar_hdf5_provenance.json', out / 'solar_hdf5_provenance.json')
solar_validation = {
    'periods': len(period),
    'hdf5_files': 2016,
    'phases': 66,
    'projects': 65,
    'capacity_raw_mw': float(phase_capacity.capacity_raw_mw.sum()),
    'capacity_dc_mw': float(phase_capacity.capacity_dc_mw.sum()),
    'capacity_ac_mw': float(phase_capacity.capacity_ac_mw.sum()),
    'maximum_ac_capacity_factor': float((period.power_output_mw / period.capacity_ac_mw).max()),
    'unit': 'raw*0.0001 MJ/m2/hour; raw/36 W/m2; resulting power in MWac',
    'formula': parameters['power_formula'],
    'system_loss_fraction': parameters['system_loss_fraction'],
    'inverter_efficiency': parameters['inverter_efficiency'],
    'dc_ac_ratio': parameters['dc_ac_ratio'],
    'unknown_capacity_rating_assumption': 'DC',
    'clipped_phase_hours': int(clipped.sum()),
    'clipping_loss_mwh': float((raw.unclipped_ac_power_mw - raw.corrected_ac_power_mw).sum()),
    'time': 'UTC+8 local weeks; cyclic source weather year for the first eight hours',
    'coordinate_mapping': 'native HDF5 array[longitude_index,latitude_index]; 71.025+0.05*x,59.975-0.05*y',
    'source_raw_sha256': sha256(args.raw_solar),
}
(out / 'solar_hdf5_validation.json').write_text(json.dumps(solar_validation, indent=2), encoding='utf-8')
raw_validation = json.loads((source / 'raw_profile_validation.json').read_text())
raw_validation['solar'] = solar_validation
(out / 'raw_profile_validation.json').write_text(json.dumps(raw_validation, indent=2), encoding='utf-8')
source_records = {
    'raw_solar': {'path': str(args.raw_solar.resolve()), 'sha256': sha256(args.raw_solar)},
    'solar_inventory_with_grid': {'path': str(inventory_path), 'sha256': sha256(inventory_path)},
    'source_twelve_weeks': {'path': str(args.source_twelve_weeks.resolve()), 'sha256': sha256(args.source_twelve_weeks)},
    'hdf5_provenance': {'path': str(source / 'solar_hdf5_provenance.json'), 'sha256': sha256(source / 'solar_hdf5_provenance.json')},
    'original_factor_provenance': 'The archived 0.1632 multiplier was hardcoded. No component decomposition was established; the new parameters do not assume it equals 0.20*0.85*0.96.',
    'engineering_parameters': parameters,
}
retained_sources = out / 'sources'
retained_sources.mkdir(exist_ok=True)
for source_path, retained_name in [(args.raw_solar, 'solar_hdf5_extracted.csv.gz'), (inventory_path, 'solar_grid_mapping.csv')]:
    retained_path = retained_sources / retained_name
    if source_path.resolve() != retained_path.resolve():
        shutil.copyfile(source_path, retained_path)
    assert sha256(source_path) == sha256(retained_path)
source_records['retained_source_files'] = {str(path.relative_to(out)).replace('\\', '/'): sha256(path) for path in sorted(retained_sources.iterdir()) if path.is_file()}
(out / 'source_records.json').write_text(json.dumps(source_records, ensure_ascii=False, indent=2), encoding='utf-8')
report = {
    'solar': solar_validation,
    'schedules': schedule_report,
    'capacity_rating_counts': phase_capacity.groupby('capacity_rating_raw').agg(phases=('phase_id', 'count'), capacity_raw_mw=('capacity_raw_mw', 'sum')).reset_index().to_dict('records'),
    'upstream_reconstruction_verified_against_original_solar_periods': True,
    'wind_and_demand_preserved': True,
    'all_output_power_finite_nonnegative_and_at_most_ac_capacity': True,
    'twelve_week_rows': len(twelve),
    'twelve_week_projects': 109,
}
(out / 'validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
hashes = {str(path.relative_to(out)).replace('\\', '/'): sha256(path) for path in sorted(out.rglob('*')) if path.is_file() and path.name != 'input_sha256.json'}
(out / 'input_sha256.json').write_text(json.dumps(hashes, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False, indent=2))
