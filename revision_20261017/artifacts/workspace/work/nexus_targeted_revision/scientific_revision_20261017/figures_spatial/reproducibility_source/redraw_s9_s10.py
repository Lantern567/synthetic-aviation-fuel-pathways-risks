import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from zipfile import ZipFile

SOURCE_HERE = Path(__file__).resolve().parents[2] / 'figures_resource'
parser = argparse.ArgumentParser()
parser.add_argument('--workspace-root', type=Path, default=SOURCE_HERE.parents[3])
parser.add_argument('--pv-inputs', type=Path, default=SOURCE_HERE.parent / 'pv_inputs')
parser.add_argument('--legacy-figures', type=Path)
parser.add_argument('--external-project', type=Path, default=Path('E:/green_methanol_for_port_transportation-main'))
parser.add_argument('--wind-source-directory', type=Path)
parser.add_argument('--original-docx', type=Path)
parser.add_argument('--output-root', type=Path, default=SOURCE_HERE)
args = parser.parse_args()
ROOT = args.workspace_root.resolve()
HERE = args.output_root.resolve()
HERE.mkdir(parents=True, exist_ok=True)
PV = args.pv_inputs.resolve()
OLD = (args.legacy_figures or ROOT / 'work/nexus_targeted_revision/revision_20261007/figures_space_time').resolve()
DATA = HERE / 'resource_data'
FIGURES = HERE / 'figures'
DATA.mkdir(exist_ok=True)
FIGURES.mkdir(exist_ok=True)
os.environ['MPLCONFIGDIR'] = str(HERE / 'mplconfig')

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch


COLORS = {'orange': '#E64B35', 'blue': '#3C5488', 'green': '#00A087', 'vermillion': '#F39B7F', 'black': '#333333', 'gray': '#6B7280'}
RC = {
    'font.family': 'sans-serif', 'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
    'axes.unicode_minus': False, 'font.size': 8, 'axes.titlesize': 8.5,
    'axes.labelsize': 8.5, 'xtick.labelsize': 7, 'ytick.labelsize': 7,
    'axes.linewidth': 0.7, 'xtick.major.width': 0.7, 'ytick.major.width': 0.7,
    'xtick.major.size': 3, 'ytick.major.size': 3, 'legend.fontsize': 6.8,
    'legend.frameon': False, 'figure.facecolor': 'white', 'axes.facecolor': 'white',
    'savefig.dpi': 300, 'pdf.fonttype': 42, 'ps.fonttype': 42, 'svg.fonttype': 'none',
}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path):
    return pd.read_csv(path, float_precision='round_trip')


def style_axes(ax):
    for side in ['top', 'right']:
        ax.spines[side].set_visible(False)
    for side in ['left', 'bottom']:
        ax.spines[side].set_color('#CBD5E1')
    ax.tick_params(axis='both', colors='#334155', labelsize=7, direction='out', length=4, width=0.8)
    ax.grid(axis='y', color='#CBD5E1', linewidth=0.8, linestyle='--', alpha=0.3)
    ax.xaxis.grid(False)
    ax.set_axisbelow(True)


def panel(ax, label):
    ax.text(-0.10, 1.02, f'({label})', transform=ax.transAxes, fontsize=10, fontweight='bold', color=COLORS['black'], va='bottom', ha='left', clip_on=False)


def save_figure(fig, stem):
    for suffix in ['png', 'pdf']:
        fig.savefig(FIGURES / f'{stem}.{suffix}', dpi=300, bbox_inches='tight', pad_inches=0.04, facecolor=fig.get_facecolor())
    plt.close(fig)


def workflow(ax):
    ax.set_axis_off()
    panel(ax, 'a')
    marker_x, text_x = 0.14, 0.23
    stage_y = [0.80, 0.52, 0.23]
    labels = ['Inventories + archived drivers', 'Hourly plant-level output', '12-week pool -> retained 4 weeks']
    for i, (y, text) in enumerate(zip(stage_y, labels), start=1):
        ax.scatter([marker_x], [y], s=72, transform=ax.transAxes, facecolor='#F8FAFC', edgecolor='#94A3B8', linewidth=0.9, zorder=3)
        ax.text(marker_x, y, str(i), transform=ax.transAxes, ha='center', va='center', fontsize=6.4, color=COLORS['black'], zorder=4)
        ax.text(text_x, y+0.01, text, transform=ax.transAxes, ha='left', va='center', fontsize=7.1, color=COLORS['black'])
    for start, end in zip(stage_y[:-1], stage_y[1:]):
        ax.annotate('', xy=(marker_x, end+0.07), xytext=(marker_x, start-0.07), xycoords='axes fraction', textcoords='axes fraction', arrowprops=dict(arrowstyle='->', lw=0.95, color='#94A3B8'))
    for y, text, color in [
        (stage_y[1]-0.09, 'Solar: GHI + rated DC -> AC', COLORS['orange']),
        (stage_y[1]-0.18, 'Wind: speed -> hub -> curve', COLORS['blue']),
        (stage_y[2]-0.10, 'Retained: W1, W2, W4, W11', COLORS['gray']),
        (stage_y[2]-0.18, '2,016 h -> 672 h', COLORS['gray']),
    ]:
        ax.text(text_x, y, text, transform=ax.transAxes, ha='left', va='center', fontsize=6.4, color=color)


def relationship(ax, frame, x_column, xlabel, ylabel, color, label):
    clean = frame[[x_column, 'power_output_mw', 'capacity_mw']].copy()
    assert np.isfinite(clean).all().all() and (clean.capacity_mw > 0).all()
    clean['normalized_output_pct'] = clean.power_output_mw / clean.capacity_mw * 100
    assert clean.normalized_output_pct.between(0, 100+1e-10).all()
    x_upper = float(clean[x_column].quantile(0.995))
    clean = clean[clean[x_column] <= x_upper]
    ax.scatter(clean[x_column], clean.normalized_output_pct, color=color, s=10, alpha=0.12, edgecolors='none', linewidths=0, rasterized=len(clean) > 3000)
    bins = np.linspace(clean[x_column].min(), clean[x_column].max(), 19)
    clean['bin'] = pd.cut(clean[x_column], bins=bins, include_lowest=True)
    curve = clean.groupby('bin', observed=True).agg(x_mid=(x_column, 'median'), y_median=('normalized_output_pct', 'median')).dropna()
    ax.plot(curve.x_mid, curve.y_median, color=COLORS['black'], linewidth=1.3, zorder=4)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_ylim(0, 105)
    style_axes(ax)
    panel(ax, label)
    return {'sample_rows': len(frame), 'displayed_rows': len(clean), 'display_x_quantile_limit': x_upper, 'display_x_quantile': 0.995}


inputs = {name: sha256(PV / name) for name in ['renewable_12weeks.csv', 'solar_phase_capacity.csv', 'pv_parameters.json', 'sources/solar_hdf5_extracted.csv.gz', 'inputs/baseline/renewable_periods.csv', 'inputs/summer/renewable_periods.csv']}
frozen_hashes = json.loads((PV / 'input_sha256.json').read_text())
assert all(frozen_hashes[name] == digest for name, digest in inputs.items())
parameters = json.loads((PV / 'pv_parameters.json').read_text())
profiles = read_csv(PV / 'renewable_12weeks.csv')
assert len(profiles) == 109*12*56 and profiles.plant_name.nunique() == 109
assert (profiles.groupby('plant_name').size() == 672).all()
assert np.isfinite(profiles.select_dtypes('number')).all().all()
assert (profiles.power_output_mw >= 0).all()
assert (profiles.power_output_mw <= profiles.capacity_ac_mw+1e-12).all()
weeks = sorted(profiles.source_week.unique())
profiles['pool_hour'] = profiles.source_week.map({w: i*168 for i, w in enumerate(weeks)}) + profiles.source_period*3
aggregated = profiles.groupby(['type', 'pool_hour'], as_index=False).agg(power_output_mw=('power_output_mw', 'sum'), capacity_ac_mw=('capacity_ac_mw', 'sum'))
aggregated['normalized_output_pct'] = aggregated.power_output_mw / aggregated.capacity_ac_mw * 100
pool_hourly = pd.concat([aggregated.assign(hour=aggregated.pool_hour+offset) for offset in range(3)], ignore_index=True).sort_values(['type', 'hour'])
pool_hourly.to_csv(DATA / 'twelve_week_profiles.csv', index=False)
baseline = read_csv(PV / 'inputs/baseline/renewable_periods.csv')
base_period = baseline.groupby(['type', 'period'], as_index=False).power_output_mw.sum()
base_hourly = pd.concat([base_period.assign(hour=base_period.period*3+offset) for offset in range(3)], ignore_index=True)
hourly = base_hourly.pivot(index='hour', columns='type', values='power_output_mw').rename(columns={'wind_farm': 'wind_mw', 'solar_plant': 'solar_mw'}).reset_index()
assert len(hourly) == 672
hourly['week'] = hourly.hour//168+1
hourly['hour_in_day'] = hourly.hour%24
hourly.to_csv(DATA / 'retained_week_profiles.csv', index=False)
diurnal = hourly.groupby(['week', 'hour_in_day'], as_index=False)[['wind_mw', 'solar_mw']].mean()
diurnal.to_csv(DATA / 'retained_diurnal_profiles.csv', index=False)
weekly = profiles.groupby(['source_week', 'type']).power_output_mw.sum().mul(3).unstack().rename(columns={'solar_plant': 'solar_mwh', 'wind_farm': 'wind_mwh'})
weekly['renewable_mwh'] = weekly.sum(axis=1)
weekly.to_csv(DATA / 'twelve_week_renewable_energy.csv')

# 逐分期原始辐射与已冻结容量映射生成散点，与输入构建使用同一公式。
phase = read_csv(PV / 'solar_phase_capacity.csv')
solar_raw = read_csv(PV / 'sources/solar_hdf5_extracted.csv.gz').merge(phase[['phase_id', 'capacity_dc_mw', 'capacity_ac_mw']], on='phase_id', validate='many_to_one')
solar_raw['power_output_mw'] = np.minimum(solar_raw.capacity_ac_mw, solar_raw.capacity_dc_mw*solar_raw.irradiance_wm2/1000*(1-parameters['system_loss_fraction'])*parameters['inverter_efficiency'])
solar_raw['capacity_mw'] = solar_raw.capacity_ac_mw
solar_sample = solar_raw.sample(n=12000, random_state=42).copy()
solar_sample.to_csv(DATA / 'solar_relationship_points.csv', index=False)

# 风电关系图沿用原脚本的文件等距抽样及随机种子。
wind_directory = args.wind_source_directory or args.external_project / 'products/aviation_fuel_analysis/resource_flight_data_process/results/3hourly_generation'
wind_files = sorted(wind_directory.glob('*.csv'))
assert wind_files
wind_files = [wind_files[int(i)] for i in np.unique(np.linspace(0, len(wind_files)-1, 18, dtype=int))]
wind_samples = []
wind_sources = []
for i, path in enumerate(wind_files):
    frame = pd.read_csv(path, usecols=['hub_wind_speed_ms', 'power_output_mw', 'capacity_mw'])
    assert len(frame) >= 550
    wind_samples.append(frame.sample(n=550, random_state=100+i))
    wind_sources.append({'path': str(path), 'sha256': sha256(path), 'sample_rows': 550, 'random_state': 100+i})
wind_sample = pd.concat(wind_samples, ignore_index=True)
assert wind_sample.power_output_mw.between(0, wind_sample.capacity_mw+1e-10).all()
wind_sample.to_csv(DATA / 'wind_relationship_points.csv', index=False)

with plt.rc_context(RC):
    fig = plt.figure(figsize=(7.4, 5.8), dpi=300)
    gs = fig.add_gridspec(2, 3, left=0.07, right=0.985, top=0.965, bottom=0.11, wspace=0.28, hspace=0.36, height_ratios=[0.86, 1.14])
    workflow(fig.add_subplot(gs[0, 0]))
    solar_plot = relationship(fig.add_subplot(gs[0, 1]), solar_sample, 'irradiance_wm2', 'Solar irradiance (W/m²)', 'AC output / AC capacity (%)', COLORS['orange'], 'b')
    wind_plot = relationship(fig.add_subplot(gs[0, 2]), wind_sample, 'hub_wind_speed_ms', 'Hub-height wind speed (m/s)', 'Plant output / capacity (%)', COLORS['blue'], 'c')
    ax = fig.add_subplot(gs[1, :])
    for week in [1, 2, 4, 11]:
        ax.axvspan((week-1)*168, week*168, facecolor='#E2E8F0', alpha=0.4, edgecolor='none', zorder=0)
    for type_name, color in [('wind_farm', COLORS['blue']), ('solar_plant', COLORS['orange'])]:
        frame = pool_hourly[pool_hourly.type.eq(type_name)]
        ax.plot(frame.hour, frame.normalized_output_pct, color=color, linewidth=1, alpha=0.4, zorder=2)
        for week in [1, 2, 4, 11]:
            retained = frame[frame.hour.between((week-1)*168, week*168-1)]
            ax.plot(retained.hour, retained.normalized_output_pct, color=color, linewidth=1.5, zorder=3)
    ax.set_xlim(0, 2015)
    ax.set_xticks([week*168+84 for week in range(12)], [f'W{week}' for week in range(1, 13)])
    ax.set_xlabel('Week in the 12-week pool')
    ax.set_ylabel('Aggregate output / AC capacity (%)')
    ax.set_ylim(0, math.ceil(pool_hourly.normalized_output_pct.max()/5)*5+5)
    style_axes(ax)
    ax.legend(handles=[Line2D([0], [0], color=COLORS['blue'], linewidth=1.5, label='Wind profile'), Line2D([0], [0], color=COLORS['orange'], linewidth=1.5, label='Solar profile'), Patch(facecolor='#E2E8F0', edgecolor='none', alpha=0.4, label='Retained week window')], loc='upper right', frameon=False, fontsize=6.6)
    panel(ax, 'd')
    save_figure(fig, 'Figure_S9')

    fig = plt.figure(figsize=(7.2, 5.4), dpi=300)
    gs = fig.add_gridspec(2, 2, left=0.08, right=0.985, top=0.965, bottom=0.12, wspace=0.24, hspace=0.46)
    week_colors = [COLORS['blue'], COLORS['orange'], COLORS['green'], COLORS['vermillion']]
    for col, (column, label, color) in enumerate([('wind_mw', 'wind', COLORS['blue']), ('solar_mw', 'solar AC', COLORS['orange'])]):
        limit = hourly[column].max()/1000*1.08
        ax = fig.add_subplot(gs[0, col])
        for i, (start, end) in enumerate(zip([0, 168, 336, 504], [168, 336, 504, 672])):
            if i%2 == 0:
                ax.axvspan(start, end, facecolor='#F8FAFC', alpha=0.95, edgecolor='none', zorder=0)
        for x in [168, 336, 504]:
            ax.axvline(x, color='#CBD5E1', linestyle='--', linewidth=0.8, zorder=0)
        ax.plot(hourly.hour, hourly[column]/1000, color=color, linewidth=1.2, zorder=3)
        ax.set_xlabel('Retained week (168 h each)')
        ax.set_ylabel(f'Aggregate {label} output (GW)')
        ax.set_xticks([84, 252, 420, 588], [f'Week {week}' for week in range(1, 5)])
        ax.set_ylim(0, limit)
        style_axes(ax)
        panel(ax, 'ab'[col])
        ax = fig.add_subplot(gs[1, col])
        for week, color in zip(range(1, 5), week_colors):
            frame = diurnal[diurnal.week.eq(week)]
            ax.plot(frame.hour_in_day, frame[column]/1000, color=color, linewidth=1.4, zorder=3)
        ax.set_xlabel('Hour of day')
        ax.set_ylabel(f'Mean {label} output (GW)')
        ax.set_xlim(0, 23)
        ax.set_xticks([0, 6, 12, 18, 23])
        ax.set_ylim(0, limit)
        style_axes(ax)
        panel(ax, 'cd'[col])
    handles = [Line2D([0], [0], color=color, linewidth=1.6, label=f'Week {week}') for week, color in zip(range(1, 5), week_colors)]
    fig.legend(handles, [handle.get_label() for handle in handles], frameon=False, loc='upper center', bbox_to_anchor=(0.5, 0.56), ncol=4, fontsize=6.8, columnspacing=1.2, handletextpad=0.5)
    save_figure(fig, 'Figure_S10')

docx_path = args.original_docx or ROOT / 'Nexus系统提交文件_代码归档同步20261015/Supplementary_Information.docx'
with ZipFile(docx_path) as document:
    original_image_hashes = {name: hashlib.sha256(document.read(f'word/media/{part}')).hexdigest() for name, part in [('Figure_S9', 'image6.png'), ('Figure_S10', 'image7.png')]}
assert all(original_image_hashes[name] == sha256(OLD / f'outputs/{name}.png') for name in original_image_hashes)
summary = {
    'solar_capacity_raw_mw': float(phase.capacity_raw_mw.sum()),
    'solar_capacity_dc_mw': float(phase.capacity_dc_mw.sum()),
    'solar_capacity_ac_mw': float(phase.capacity_ac_mw.sum()),
    'wind_capacity_ac_mw': float(profiles.loc[profiles.type.eq('wind_farm')].drop_duplicates('plant_name').capacity_ac_mw.sum()),
    'twelve_week_solar_mwh': float(weekly.solar_mwh.sum()),
    'twelve_week_wind_mwh': float(weekly.wind_mwh.sum()),
    'baseline_solar_mwh': float(hourly.solar_mw.sum()),
    'baseline_wind_mwh': float(hourly.wind_mw.sum()),
    'summer_solar_mwh': float(weekly.loc[[1, 14, 27, 44], 'solar_mwh'].sum()),
    'summer_wind_mwh': float(weekly.loc[[1, 14, 27, 44], 'wind_mwh'].sum()),
    'solar_panel_b_fraction_at_900_wm2': parameters['dc_ac_ratio']*0.9*(1-parameters['system_loss_fraction'])*parameters['inverter_efficiency'],
    'maximum_solar_output_gw_in_baseline': float(hourly.solar_mw.max()/1000),
    'figure_s9_solar_relationship': solar_plot,
    'figure_s9_wind_relationship': wind_plot,
}
(HERE / 'resource_metrics.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
manifest = {
    'source_plotting_script': {'path': str(OLD / 'source/generate_appendix_docx.py'), 'sha256': sha256(OLD / 'source/generate_appendix_docx.py'), 'adapted_functions': ['create_renewable_processing_figure', 'create_representative_renewable_profiles', 'draw_processing_workflow_panel', 'draw_raw_relationship_panel']},
    'original_figure_hashes_verified_against_latest_docx': original_image_hashes,
    'frozen_pv_inputs': inputs,
    'wind_relationship_sources': wind_sources,
    'plot_method': 'Original palette, figure dimensions, grids, panel labels, random sampling, quantile display and median-curve layout retained; AC power and capacity definitions follow the frozen inputs',
    'data_and_figure_sha256': {str(path.relative_to(HERE)).replace('\\', '/'): sha256(path) for folder in [DATA, FIGURES] for path in sorted(folder.iterdir()) if path.is_file()},
}
(HERE / 'figure_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
assert all(sha256(PV / name) == digest for name, digest in inputs.items())
print(json.dumps(summary, indent=2))
