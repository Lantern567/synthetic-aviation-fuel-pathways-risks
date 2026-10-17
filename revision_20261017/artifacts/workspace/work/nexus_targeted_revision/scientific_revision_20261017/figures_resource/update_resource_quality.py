import hashlib
import importlib.util
import json
import logging
import os
import sys
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PV = HERE.parent / 'pv_inputs'
OLD = ROOT / 'work/nexus_targeted_revision/revision_20261007/figures_space_time'
DATA = HERE / 'resource_data'
FIGURES = HERE / 'figures'
os.environ['MPLCONFIGDIR'] = str(HERE / 'mplconfig')
sys.path.insert(0, str(OLD / 'source'))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


spec = importlib.util.spec_from_file_location('resource_figure_source_20261017', OLD / 'source/generate_appendix_docx.py')
draw = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = draw
spec.loader.exec_module(draw)
logging.getLogger('fontTools.subset').setLevel(logging.WARNING)
draw.ROOT = Path('E:/green_methanol_for_port_transportation-main')
profiles = pd.read_csv(PV / 'renewable_12weeks.csv', float_precision='round_trip')
resource = profiles.groupby(['type', 'plant_name'], as_index=False).agg(capacity_mw=('capacity_ac_mw', 'first'), capacity_raw_mw=('capacity_raw_mw', 'first'), capacity_dc_mw=('capacity_dc_mw', 'first'), latitude=('latitude', 'first'), longitude=('longitude', 'first'), sum_power=('power_output_mw', 'sum'), periods=('source_period', 'size'))
resource['hours'] = resource.periods*3
resource['total_output_mwh'] = resource.sum_power*3
resource['capacity_factor'] = resource.total_output_mwh/resource.capacity_mw/resource.hours
resource['full_load_hours'] = resource.total_output_mwh/resource.capacity_mw
resource['plant_id'] = resource.plant_name
assert (resource.hours == 2016).all() and len(resource) == 109
assert resource.capacity_factor.between(0, 1).all()
resource.to_csv(DATA / 'selected_candidate_resource_metrics.csv', index=False)
weeks = sorted(profiles.source_week.unique())
for kind, type_name in [('solar', 'solar_plant'), ('wind', 'wind_farm')]:
    selected = profiles[profiles.type.eq(type_name)].copy()
    selected['hour'] = selected.source_week.map({week: i*168 for i, week in enumerate(weeks)}) + selected.source_period*3
    displayed = pd.concat([selected.assign(hour=selected.hour+offset) for offset in range(3)], ignore_index=True)
    displayed.to_csv(DATA / f'{kind}_12weeks.csv', index=False)
    retained = selected[selected.source_week.isin([1, 5, 14, 44])].copy()
    retained['hour'] = retained.source_week.map({week: i*168 for i, week in enumerate([1, 5, 14, 44])}) + retained.source_period*3
    pd.concat([retained.assign(hour=retained.hour+offset) for offset in range(3)], ignore_index=True).to_csv(DATA / f'{kind}_4weeks.csv', index=False)


def selected_resource(csv_path, **kwargs):
    kind = 'wind_farm' if 'wind' in str(csv_path) else 'solar_plant'
    return resource[resource.type.eq(kind)].copy()


def export(fig, path):
    for suffix in ['png', 'pdf']:
        fig.savefig(path.with_suffix('.'+suffix), dpi=300, bbox_inches='tight', pad_inches=0.04, facecolor=fig.get_facecolor())
    plt.close(fig)
    return path


# 适配原绘图函数的数据入口，绘图布局、全国清单和地图元素沿用原实现。
draw.load_cached_renewable_resource_frame = selected_resource
draw.save_matplotlib_figure = export
inventory_paths = {kind: draw.ROOT / f'products/gis_energy_mapping/gis_data_scraper/scraped_gis_data/{kind}_power_plants.csv' for kind in ['wind', 'solar']}
inventories = {kind: pd.read_csv(path) for kind, path in inventory_paths.items()}
summary = {}
for kind, type_name in [('wind', 'wind_farm'), ('solar', 'solar_plant')]:
    frame = resource[resource.type.eq(type_name)]
    summary[kind] = {'candidate_plants': len(frame), 'capacity_mw': float(frame.capacity_mw.sum()), 'capacity_ac_mw': float(frame.capacity_mw.sum()), 'hours': 2016, 'energy_mwh': float(frame.total_output_mwh.sum()), 'capacity_factor_median': float(frame.capacity_factor.median()), 'full_load_hours_median': float(frame.full_load_hours.median()), 'availability_percentiles_5_95': [float(frame.capacity_factor.quantile(0.05)*100), float(frame.capacity_factor.quantile(0.95)*100)]}
(DATA / 'resource_metrics.json').write_text(json.dumps({**summary, 'scope': '109 model candidate projects; twelve selected weeks (2016 h)', 'capacity_definition': 'AC nominal power', 'source': str(PV / 'renewable_12weeks.csv')}, indent=2), encoding='utf-8')
data = SimpleNamespace(transport_summary={kind+'_inventory_rows': len(frame) for kind, frame in inventories.items()}, renewable_summary={})
for kind in ['wind', 'solar']:
    data.renewable_summary[kind+'_resource'] = summary[kind]
    data.renewable_summary[kind] = {'unique_plants': summary[kind]['candidate_plants']}
draw.create_renewable_raw_summary(FIGURES / 'Figure_S6.png', data)
draw.create_renewable_resource_maps(FIGURES / 'Figure_S7.png', data)

# 代表周诊断继续使用原有四周，更新真实光伏供电量后重新计算范围覆盖。
demand_path = ROOT / 'work/nexus_targeted_revision/static_supplement/twelve_week_joint_relative_states.csv'
old_joint = pd.read_csv(demand_path)
demand = old_joint.set_index('original_week').demand
weekly = pd.read_csv(DATA / 'twelve_week_renewable_energy.csv').set_index('source_week')
joint = pd.DataFrame({'demand': demand, 'solar_mwh': weekly.solar_mwh, 'wind_mwh': weekly.wind_mwh})
assert len(joint) == 12 and not joint.isna().any().any()
baseline_demand = pd.read_csv(PV / 'inputs/baseline/airport_input.csv')
summer_demand = pd.read_csv(PV / 'inputs/summer/airport_input.csv')
assert np.isclose(joint.loc[[1, 5, 14, 44], 'demand'].sum(), baseline_demand.weekly_total_fuel_kg_total.sum(), rtol=1e-12)
assert np.isclose(joint.loc[[1, 14, 27, 44], 'demand'].sum(), summer_demand.weekly_total_fuel_kg_total.sum(), rtol=1e-12)
joint['demand_relative_index'] = joint.demand/joint.demand.mean()
joint['solar_relative_index'] = joint.solar_mwh/joint.solar_mwh.mean()
joint['wind_relative_index'] = joint.wind_mwh/joint.wind_mwh.mean()
joint['selected'] = joint.index.isin([1, 5, 14, 44])
features = ['demand_relative_index', 'solar_relative_index', 'wind_relative_index']
ranges = joint.loc[joint.selected, features].agg(['min', 'max'])
joint['inside_selected_marginal_box'] = ((joint[features] >= ranges.loc['min']-1e-12) & (joint[features] <= ranges.loc['max']+1e-12)).all(axis=1)
joint.index.name = 'original_week'
joint.to_csv(DATA / 'twelve_week_joint_relative_states.csv')
records = [{'week': int(week), 'demand': float(row.demand_relative_index), 'solar': float(row.solar_relative_index), 'wind': float(row.wind_relative_index), 'selected': bool(row.selected), 'inside': bool(row.inside_selected_marginal_box)} for week, row in joint.iterrows()]
(HERE / 'updated_joint_week_ranges.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
quality_manifest = {
    'source_plotting_script': {'path': str(OLD / 'source/generate_appendix_docx.py'), 'sha256': sha256(OLD / 'source/generate_appendix_docx.py'), 'functions': ['create_renewable_raw_summary', 'create_renewable_resource_maps']},
    'inventory_sources': {kind: {'path': str(path), 'sha256': sha256(path), 'rows': len(inventories[kind])} for kind, path in inventory_paths.items()},
    'frozen_input_sha256': sha256(PV / 'renewable_12weeks.csv'),
    'candidate_resource_metrics': summary,
    'joint_coverage': {'demand_source': str(demand_path), 'demand_source_sha256': sha256(demand_path), 'selected_weeks': [1, 5, 14, 44], 'inside_count': int(joint.inside_selected_marginal_box.sum()), 'outside_weeks': [int(week) for week in joint.index[~joint.inside_selected_marginal_box]], 'selection_algorithm_rerun': False, 'selection_scope': 'Original representative weeks retained. The marginal-range calculation is a descriptive coverage diagnostic.'},
    'sha256': {str(path.relative_to(HERE)).replace('\\', '/'): sha256(path) for path in [FIGURES / 'Figure_S6.png', FIGURES / 'Figure_S6.pdf', FIGURES / 'Figure_S7.png', FIGURES / 'Figure_S7.pdf', DATA / 'selected_candidate_resource_metrics.csv', DATA / 'twelve_week_joint_relative_states.csv']},
}
(HERE / 'resource_quality_manifest.json').write_text(json.dumps(quality_manifest, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(quality_manifest, ensure_ascii=False, indent=2))
