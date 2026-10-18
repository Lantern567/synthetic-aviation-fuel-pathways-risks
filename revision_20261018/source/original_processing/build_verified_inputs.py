import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

base = Path(__file__).resolve().parent
original = Path('/home/ljt/code_project/green_methanol_for_port_transportation-main')
reference = pd.read_csv(base.parent / 'copt_migration/full_trial/renewable_periods.csv').drop_duplicates('plant_name').set_index('plant_name')
weeks = [1,5,9,14,18,22,27,31,35,40,44,48]
mapping = json.loads((base / 'phase_mapping.json').read_text())
allowed = {phase for row in mapping if row['kind']=='wind' for phase in row['phase_ids']}
inventory = pd.read_csv(base / 'wind_inventory.csv').drop_duplicates('GEM_phase_ID')
inventory = inventory[inventory.GEM_phase_ID.isin(allowed)].rename(columns={'Project_Name':'plant_name','Latitude':'latitude','Longitude':'longitude','Capacity__MW_':'capacity_mw'})
identity = ['plant_name','latitude','longitude','capacity_mw']
counts = inventory.groupby(identity,as_index=False).size().rename(columns={'size':'phases'})
raw = pd.read_csv(base / 'wind_selected_raw.csv.gz')
stamp = pd.to_datetime(raw.timestamp)
raw['utc_hour'] = ((stamp-pd.Timestamp('2024-01-01'))/pd.Timedelta(hours=1)).astype(int)
print('WIND_TIMESTAMPS',str(stamp.min()),str(stamp.max()),int(stamp.nunique()),flush=True)
source_hours = int(raw.utc_hour.max())+3
assert np.array_equal(np.sort(raw.utc_hour.unique()),np.arange(0,source_hours,3))
assert raw.groupby(identity+['utc_hour']).power_output_mw.nunique().max() == 1
raw = raw.drop_duplicates(identity+['utc_hour']).merge(counts,on=identity,how='inner',validate='many_to_one')
raw['corrected_power_mw'] = raw.power_output_mw*raw.phases
raw['selected_capacity_mw'] = raw.capacity_mw*raw.phases
# 三小时平均功率展开为小时，统一到北京时间；年界使用同一气象年的周期边界。
hourly = pd.concat([raw.assign(local_hour=(raw.utc_hour+8+offset)%source_hours) for offset in range(3)],ignore_index=True)
hourly['source_week'] = hourly.local_hour//168+1
hourly = hourly[hourly.source_week.isin(weeks)].copy()
sizes = hourly.groupby(identity).size()
assert (sizes == 2016).all(), sizes[sizes != 2016].to_dict()
hourly = hourly.groupby(['plant_name','local_hour','source_week'],as_index=False).agg(power_output_mw=('corrected_power_mw','sum'),capacity_mw=('selected_capacity_mw','sum'))
hourly['source_period'] = hourly.local_hour%168//3
wind = hourly.groupby(['plant_name','source_week','source_period'],as_index=False).agg(power_output_mw=('power_output_mw','mean'),capacity_mw=('capacity_mw','first'))
solar = pd.read_csv(base / 'solar_corrected_periods.csv')
frames = []
for kind,period in [('solar',solar),('wind',wind)]:
    period['latitude'] = period.plant_name.map(reference.latitude)
    period['longitude'] = period.plant_name.map(reference.longitude)
    period['type'] = 'solar_plant' if kind=='solar' else 'wind_farm'
    assert np.isfinite(period.select_dtypes('number')).all().all()
    assert (period.power_output_mw >= 0).all()
    assert (period.power_output_mw <= period.capacity_mw+1e-7).all()
    assert (period.groupby('plant_name').size() == 672).all()
    frames.append(period)
all_data = pd.concat(frames,ignore_index=True)
assert all_data.plant_name.nunique() == 109
all_data.to_csv(base / 'renewable_12weeks.csv',index=False)
audit = {'solar':json.loads((base / 'solar_hdf5_validation.json').read_text()),'wind':{'source_rows':len(raw),'selected_phases':int(counts.phases.sum()),'periods':len(wind),'max_aggregation_error_mwh':float(abs(wind.power_output_mw.sum()*3-hourly.power_output_mw.sum())),'source_hours':source_hours,'first_timestamp':str(stamp.min()),'last_timestamp':str(stamp.max()),'time_boundary':'cyclic 8760-hour archived wind sequence; timestamps labelled 2024, last day December 30','unit':'raw mean MW, expanded over three hours and regrouped in local three-hour intervals'}}
assert audit['wind']['max_aggregation_error_mwh']<1e-6
(base / 'raw_profile_validation.json').write_text(json.dumps(audit,indent=2))
airport = pd.read_csv(base.parent / 'input_audit/twelve_week_demand.csv')
for label,selected in [('baseline',[1,5,14,44]),('summer',[1,14,27,44])]:
    out = base / 'inputs' / label
    out.mkdir(parents=True,exist_ok=True)
    subset = all_data[all_data.source_week.isin(selected)].copy()
    subset['period'] = subset.source_week.map({w:i*56 for i,w in enumerate(selected)})+subset.source_period
    subset['hour'] = subset.period
    subset.sort_values(['plant_name','period']).to_csv(out / 'renewable_periods.csv',index=False)
    demand = airport[airport.original_week.isin(selected)].copy()
    demand['week_number'] = demand.original_week.map({w:i+1 for i,w in enumerate(selected)})
    coords = pd.read_csv(original / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/one_step/airports_20260201_215531.csv').set_index('机场名称')
    demand['departure_airport_latitude'] = demand.departure_airport_name.map(coords['纬度'])
    demand['departure_airport_longitude'] = demand.departure_airport_name.map(coords['经度'])
    demand.sort_values(['departure_airport_name','week_number']).to_csv(out / 'airport_input.csv',index=False)
    demand.to_excel(out / 'airport_input.xlsx',sheet_name='All_Airports',index=False)
    manifest = {'weeks':selected,'plants':109,'periods':224,'hours_per_period':3,'energy_mwh':(subset.groupby('type').power_output_mw.sum()*3).to_dict(),'capacity_mw':subset.drop_duplicates('plant_name').groupby('type').capacity_mw.sum().to_dict(),'demand_kg':float(demand.weekly_total_fuel_kg_total.sum()),'solar_conversion':'Original effective factor 0.1632 retained; P=capacity_MW*(raw_radiation/36)/1000*0.1632','solar_coordinates':'Native HDF5 [longitude,latitude], nearest 0.05-degree cell, per inventory phase','wind_conversion':'Source mean MW; three-hour duration and distinct inventory phases retained','source':'https://download.pangaea.de/reference/117364/attachments/DataDescription2020.pdf','time_zone':'UTC+8, cyclic source weather year at year boundary','spatial_assumption':'Original project reference locations retained; generation summed over selected phase locations','candidate_status':'Retained planning candidates include planned and under-construction wind projects'}
    (out / 'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    print(label,json.dumps(manifest,ensure_ascii=False),flush=True)
files = [base / name for name in ['renewable_12weeks.csv','phase_mapping.json','solar_grid_mapping.csv','solar_hdf5_provenance.json','wind_selected_raw.csv.gz']]+list((base / 'inputs').rglob('*.*'))
(base / 'input_sha256.json').write_text(json.dumps({str(p.relative_to(base)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},indent=2))
