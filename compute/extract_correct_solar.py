import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import h5py
import numpy as np
import pandas as pd

base = Path(__file__).resolve().parent
root = Path('E:/green_methanol_for_port_transportation-main/products/aviation_fuel_analysis/resource_flight_data_process/data/solar_radiation_2020')
inventory = pd.read_csv(base / 'solar_inventory.csv').drop_duplicates('GEM_phase_ID')
mapping = json.loads((base / 'phase_mapping.json').read_text())
allowed = {phase for row in mapping if row['kind']=='solar' for phase in row['phase_ids']}
inventory = inventory[inventory.GEM_phase_ID.isin(allowed)].copy()
assert len(inventory) == len(allowed)
x = np.rint((inventory.Longitude.to_numpy()-71.025)/0.05).astype(int)
y = np.rint((59.975-inventory.Latitude.to_numpy())/0.05).astype(int)
inventory['longitude_index'],inventory['latitude_index'] = x,y
inventory['grid_longitude'],inventory['grid_latitude'] = 71.025+x*0.05,59.975-y*0.05
assert np.max(abs(inventory.grid_longitude-inventory.Longitude))<=0.025001
assert np.max(abs(inventory.grid_latitude-inventory.Latitude))<=0.025001
inventory.to_csv(base / 'solar_grid_mapping.csv',index=False)
source_weeks = [1,5,9,14,18,22,27,31,35,40,44,48]
tasks = [(week,t) for week in source_weeks for t in range(168)]


def extract(task):
    week,t = task
    local_hour = (week-1)*168+t
    utc_hour = (local_hour-8)%8784
    timestamp = pd.Timestamp('2020-01-01')+pd.Timedelta(hours=utc_hour)
    filename = 'RAD_'+timestamp.strftime('%Y%m%d%H')+'.h5'
    path = root / ('China_HourlyRadiation'+timestamp.strftime('%Y%m')) / filename
    with h5py.File(path) as file:
        assert file['global radiation'].shape == (1401,901),filename
        grid = np.asarray(file['global radiation'],dtype=np.int32)
    grid[grid<0] += 65536
    values = grid[x,y]
    frame = pd.DataFrame({'plant_name':inventory.Project_Name.to_numpy(),'source_week':week,'source_hour_in_week':t,'phase_id':inventory.GEM_phase_ID.to_numpy(),'radiation_raw':values,'irradiance_wm2':values/36,'capacity_mw':inventory.Capacity__MW_.to_numpy(dtype=float)})
    frame['power_output_mw'] = frame.capacity_mw*frame.irradiance_wm2/1000*0.1632
    return frame,{'local_hour':local_hour,'utc_timestamp':str(timestamp),'source_file':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


frames,provenance = [],[]
with ThreadPoolExecutor(max_workers=4) as pool:
    for index,(frame,record) in enumerate(pool.map(extract,tasks)):
        frames.append(frame)
        provenance.append(record)
        if (index+1)%168 == 0:
            print('EXTRACTED_WEEKS',(index+1)//168,flush=True)
raw = pd.concat(frames,ignore_index=True)
raw.to_csv(base / 'solar_hdf5_extracted.csv.gz',index=False)
hourly = raw.groupby(['plant_name','source_week','source_hour_in_week'],as_index=False).agg(power_output_mw=('power_output_mw','sum'),capacity_mw=('capacity_mw','sum'))
hourly['source_period'] = hourly.source_hour_in_week//3
period = hourly.groupby(['plant_name','source_week','source_period'],as_index=False).agg(power_output_mw=('power_output_mw','mean'),capacity_mw=('capacity_mw','first'))
period.to_csv(base / 'solar_corrected_periods.csv',index=False)
(base / 'solar_hdf5_provenance.json').write_text(json.dumps(provenance,indent=2))
report = {'periods':len(period),'hdf5_files':len(provenance),'phases':len(inventory),'maximum_capacity_factor':float((period.power_output_mw/period.capacity_mw).max()),'unit':'raw*0.0001 MJ/m2/hour; raw/36 W/m2','effective_pv_factor':0.1632,'time':'UTC+8 local weeks; cyclic source weather year for the first eight hours','coordinate_mapping':'native HDF5 array[longitude_index,latitude_index]; 71.025+0.05*x,59.975-0.05*y'}
(base / 'solar_hdf5_validation.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report),flush=True)
