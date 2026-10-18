import argparse
import hashlib
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np
import pandas as pd
from PIL import Image

sys.stdout.reconfigure(encoding='utf-8')
HERE = Path(__file__).resolve().parent
WORK = HERE.parent
COLORS = {'blue': '#3C5488', 'orange': '#E64B35', 'green': '#00A087',
          'sky': '#4DBBD5', 'vermillion': '#F39B7F', 'magenta': '#8491B4',
          'black': '#333333', 'gray': '#6B7280', 'light_gray': '#D1D5DB'}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare_inputs(workspace):
    old = workspace.parent / 'scientific_revision_20261017'
    national = Path('E:/green_methanol_for_port_transportation-main/products/gis_energy_mapping/gis_data_scraper/scraped_gis_data')
    sources = {
        'cases': workspace / 'existing_demand_cases/case_values.csv',
        'case_contract': workspace / 'existing_demand_cases/summary.json',
        'case_mapping': workspace / 'existing_demand_cases/A_B_case_mapping.csv',
        'candidate_resources': old / 'figures_resource/resource_data/selected_candidate_resource_metrics.csv',
        'raw_solar_inventory': national / 'solar_power_plants.csv',
        'raw_wind_inventory': national / 'wind_power_plants.csv',
        'pipeline_inventory': national / 'natural_gas_pipelines.csv',
        'refinery_inventory': old / 'historical_runtime/industrial_inputs/refinery_daily_byproduct_h2_20251027_202950.csv',
        'steel_inventory': old / 'historical_runtime/industrial_inputs/steel_daily_byproduct_h2_20251027_202950.csv',
        'carbon_inventory': old / 'runtime/compute/project/products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/data/co2_capture_sources.csv',
        'original_generator': workspace.parent / 'minor_clarifications_20261018/qa/new_review_20261018/demand_sources/generate_appendix_docx.py',
    }
    for path in sources.values():
        if not path.is_file():
            raise FileNotFoundError(path)
    frame = pd.read_csv(sources['cases'], float_precision='round_trip')
    contract = json.loads(sources['case_contract'].read_text(encoding='utf-8'))
    if contract['passed'] is not True:
        raise AssertionError('现有需求合同未通过')
    if len(frame) != 24 or set(frame.airport) != {'北京', '天津'}:
        raise AssertionError('须为两机场各12个现有需求case')
    indices = [0, 1, 3, 10]
    baseline = frame[frame.case_index.isin(indices)].copy()
    if len(baseline) != 8:
        raise AssertionError('基线须保留8个机场-case值')
    baseline['model_week'] = baseline.case_index.map({value: i + 1 for i, value in enumerate(indices)})
    baseline['airport_en'] = baseline.airport.map({'北京': 'Beijing', '天津': 'Tianjin'})
    baseline = baseline[['model_week', 'airport_en', 'case_index', 'source_month_label',
                         'resource_source_week_label', 'weekly_total_fuel_kg_total']].sort_values(['model_week', 'airport_en'])
    mapping = pd.read_csv(sources['case_mapping'], float_precision='round_trip')
    expected = mapping[mapping.schedule.eq('baseline')].copy()
    expected['airport_en'] = expected.model_airport.map({'北京': 'Beijing', '天津': 'Tianjin'})
    expected = expected.sort_values(['model_week_number', 'airport_en'])
    if len(expected) != 8 or not np.array_equal(baseline.weekly_total_fuel_kg_total.to_numpy(), expected.saved_fuel_kg.to_numpy()):
        raise AssertionError('图S1八需求值须与现有A输入逐值一致')
    resources = pd.read_csv(sources['candidate_resources'])
    counts = {key: len(pd.read_csv(sources[key])) for key in
              ['raw_solar_inventory', 'raw_wind_inventory', 'pipeline_inventory',
               'refinery_inventory', 'steel_inventory', 'carbon_inventory']}
    candidates = resources.groupby('type').size().to_dict()
    if candidates != {'solar_plant': 65, 'wind_farm': 44}:
        raise AssertionError(f'候选项目范围不符: {candidates}')
    if not resources.hours.eq(2016).all():
        raise AssertionError('候选资源池须为2016小时')
    n_cases = int(frame.case_index.nunique())
    n_model_weeks = int(baseline.model_week.nunique())
    data = {
        'counts': counts, 'candidate_solar_projects': candidates['solar_plant'],
        'candidate_wind_projects': candidates['wind_farm'],
        'resource_pool': {'weeks': n_cases, 'three_hour_periods': n_cases * 56, 'hours': n_cases * 168},
        'model_horizon': {'weeks': n_model_weeks, 'three_hour_periods': n_model_weeks * 56, 'hours': n_model_weeks * 168},
        'source_files': {key: {'path': str(path), 'sha256': digest(path)} for key, path in sources.items()},
        'original_layout_source': 'create_raw_data_overview_panel; original four-panel layout and palette',
        'scope': 'Existing sample-demand cases and resource pool; no input values or model solutions changed',
    }
    target = HERE / 'data'
    target.mkdir(exist_ok=True)
    baseline.to_csv(target / 's1_baseline_demand.csv', index=False)
    data['baseline_demand_sha256'] = digest(target / 's1_baseline_demand.csv')
    (target / 's1_inputs.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'prepared': True, 'counts': counts, 'candidate_projects': candidates,
                      'resource_pool': data['resource_pool'], 'model_horizon': data['model_horizon'],
                      'baseline_total_kg': float(baseline.weekly_total_fuel_kg_total.sum())}, ensure_ascii=False))


def style_axes(axis, grid=None):
    axis.spines[['top', 'right']].set_visible(False)
    for side in ['left', 'bottom']:
        axis.spines[side].set_color('#CBD5E1')
    axis.tick_params(colors='#374151')
    if grid:
        axis.grid(axis=grid, color='#E2E8F0', linewidth=0.7, linestyle='--', zorder=0)
    axis.set_axisbelow(True)


def panel(axis, letter):
    axis.text(-0.11, 1.035, f'({letter})', transform=axis.transAxes,
              fontsize=10, fontweight='bold', ha='left', va='bottom', color=COLORS['black'])


def render(data_dir, out):
    inputs = data_dir / 's1_inputs.json'
    data = json.loads(inputs.read_text(encoding='utf-8'))
    demand_file = data_dir / 's1_baseline_demand.csv'
    if digest(demand_file) != data['baseline_demand_sha256']:
        raise AssertionError('需求图数据与准备记录SHA不一致')
    demand = pd.read_csv(demand_file, float_precision='round_trip')
    font_manager.findfont('Arial', fallback_to_default=False)
    rc = {'font.family': 'Arial', 'font.size': 8.5, 'axes.labelsize': 9,
          'xtick.labelsize': 8, 'ytick.labelsize': 8, 'legend.fontsize': 7.8,
          'legend.frameon': False, 'axes.linewidth': 0.7, 'pdf.fonttype': 42,
          'ps.fonttype': 42, 'axes.unicode_minus': False, 'figure.facecolor': 'white',
          'mathtext.fontset': 'custom', 'mathtext.rm': 'Arial', 'mathtext.default': 'regular'}
    out.mkdir(parents=True, exist_ok=True)
    with plt.rc_context(rc):
        fig = plt.figure(figsize=(8.0, 5.4))
        grid = fig.add_gridspec(2, 2, left=0.225, right=0.985, top=0.945,
                               bottom=0.105, wspace=0.43, hspace=0.46)
        ax = fig.add_subplot(grid[0, 0])
        count = data['counts']
        count_rows = [
            ('Solar inventory rows', count['raw_solar_inventory'], COLORS['orange']),
            ('Wind inventory rows', count['raw_wind_inventory'], COLORS['blue']),
            ('CO$_2$ capture sources', count['carbon_inventory'], COLORS['black']),
            ('Pipeline records', count['pipeline_inventory'], COLORS['gray']),
            ('Model 3-h periods', data['model_horizon']['three_hour_periods'], COLORS['sky']),
            ('Steel H$_2$ sites', count['steel_inventory'], COLORS['vermillion']),
            ('Refinery H$_2$ sites', count['refinery_inventory'], COLORS['magenta']),
            ('Renewable candidates', data['candidate_solar_projects'] + data['candidate_wind_projects'], COLORS['green']),
        ]
        count_rows.sort(key=lambda item: item[1], reverse=True)
        position = np.arange(len(count_rows))
        ax.barh(position, [row[1] for row in count_rows], color=[row[2] for row in count_rows],
                alpha=0.86, height=0.77, edgecolor='white', linewidth=0.6)
        ax.set_yticks(position, [row[0] for row in count_rows])
        ax.invert_yaxis()
        ax.set_xscale('log')
        ax.set_xlim(10, 25000)
        ax.set_xlabel('Records or periods (log scale)')
        style_axes(ax)
        panel(ax, 'a')

        ax = fig.add_subplot(grid[0, 1])
        pairs = [('Wind', count['raw_wind_inventory'], data['candidate_wind_projects'], COLORS['blue']),
                 ('Solar', count['raw_solar_inventory'], data['candidate_solar_projects'], COLORS['orange'])]
        for index, (label, raw, selected, color) in enumerate(pairs):
            y = 1 - index
            ax.plot([selected, raw], [y, y], color=COLORS['light_gray'], lw=2.1, zorder=1)
            ax.scatter(raw, y, s=40, facecolors='white', edgecolors=color, linewidth=1.4,
                       zorder=3, label='Raw inventory' if index == 0 else None)
            ax.scatter(selected, y, s=40, color=color, edgecolors='white', linewidth=0.5,
                       zorder=4, label='Model candidates' if index == 0 else None)
        ax.set_xscale('log')
        ax.set_xlim(20, 25000)
        ax.set_ylim(-0.6, 1.6)
        ax.set_yticks([1, 0], ['Wind', 'Solar'])
        ax.set_xlabel('Facility records or projects (log scale)')
        ax.legend(loc='lower right', handletextpad=0.5)
        style_axes(ax)
        panel(ax, 'b')

        ax = fig.add_subplot(grid[1, 0])
        x = np.arange(4)
        for shift, airport, color in [(-0.18, 'Beijing', COLORS['blue']), (0.18, 'Tianjin', COLORS['orange'])]:
            values = demand[demand.airport_en.eq(airport)].sort_values('model_week').weekly_total_fuel_kg_total.to_numpy() / 1e6
            ax.bar(x + shift, values, 0.36, label=airport, color=color, alpha=0.86,
                   edgecolor='white', linewidth=0.6)
        ax.set_xticks(x, ['1', '2', '3', '4'])
        ax.set_xlabel('Model week')
        ax.set_ylabel('Assigned sample demand (million kg)')
        ax.set_ylim(0, 13.5)
        ax.legend(ncol=2, loc='upper right', handlelength=1.2, columnspacing=1)
        style_axes(ax, 'y')
        panel(ax, 'c')

        ax = fig.add_subplot(grid[1, 1])
        categories = ['Weeks', '3-h periods', 'Hours']
        keys = ['weeks', 'three_hour_periods', 'hours']
        positions = np.arange(3)
        for shift, source, label, color in [(-0.18, 'resource_pool', 'Resource pool', COLORS['light_gray']),
                                            (0.18, 'model_horizon', 'Model horizon', COLORS['green'])]:
            ax.bar(positions + shift, [data[source][key] for key in keys], 0.36,
                   label=label, color=color, alpha=0.86, edgecolor='white', linewidth=0.6)
        ax.set_yscale('log')
        ax.set_ylim(1.5, 6000)
        ax.set_xticks(positions, categories)
        ax.set_ylabel('Resource-horizon units (log scale)')
        ax.legend(loc='upper left', handlelength=1.3)
        style_axes(ax, 'y')
        panel(ax, 'd')

        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        outside = []
        canvas = fig.bbox
        inactive_tick_labels = set()
        for axis in fig.axes:
            for coordinate, limits in [(axis.xaxis, axis.get_xlim()), (axis.yaxis, axis.get_ylim())]:
                lower, upper = sorted(limits)
                for tick in coordinate.get_major_ticks() + coordinate.get_minor_ticks():
                    if not lower <= tick.get_loc() <= upper:
                        inactive_tick_labels.update([tick.label1, tick.label2])
        for text in fig.findobj(matplotlib.text.Text):
            if not text.get_visible() or not text.get_text() or text in inactive_tick_labels:
                continue
            extent = text.get_window_extent(renderer)
            if extent.x0 < -0.5 or extent.y0 < -0.5 or extent.x1 > canvas.x1 + 0.5 or extent.y1 > canvas.y1 + 0.5:
                outside.append(text.get_text())
        if outside:
            raise AssertionError(f'文字超出图像画布: {outside}')
        outputs = []
        for suffix in ['png', 'pdf']:
            path = out / f'Figure_S1.{suffix}'
            fig.savefig(path, dpi=300, bbox_inches='tight', pad_inches=0.04, facecolor='white')
            outputs.append({'path': str(path), 'sha256': digest(path)})
        plt.close(fig)
    with Image.open(out / 'Figure_S1.png') as image:
        size = list(image.size)
    report = {'passed': True, 'data_sha256': digest(inputs), 'baseline_demand_sha256': digest(demand_file),
              'baseline_airport_case_values_kg': demand.to_dict('records'),
              'resource_pool': data['resource_pool'], 'model_horizon': data['model_horizon'],
              'renewable_candidates': 109, 'original_model_inputs_modified': False,
              'outputs': outputs, 'png_size': size, 'text_outside_canvas': outside,
              'visual_review_required': True}
    (out / 'Figure_S1_qa.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'passed': True, 'outputs': outputs, 'png_size': size}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--prepare-inputs', action='store_true')
    parser.add_argument('--workspace', type=Path, default=WORK)
    parser.add_argument('--data-dir', '--data', dest='data', type=Path, default=HERE / 'data')
    parser.add_argument('--out', type=Path, default=HERE)
    options = parser.parse_args()
    if options.prepare_inputs:
        prepare_inputs(options.workspace)
    render(options.data, options.out)
