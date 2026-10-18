import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
from matplotlib import pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--data-dir', type=Path, default=HERE.parent / 'existing_demand_cases')
parser.add_argument('--out', type=Path, default=HERE)
args = parser.parse_args()
data_dir = args.data_dir.resolve()
out = args.out.resolve()
figures = out / 'figures'
data_out = out / 'data'
figures.mkdir(parents=True, exist_ok=True)
data_out.mkdir(parents=True, exist_ok=True)
colors = {'Beijing': '#3C5488', 'Tianjin': '#E64B35'}
airport_names = {'北京': 'Beijing', '天津': 'Tianjin'}
months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
cases = pd.read_csv(data_dir / 'case_values.csv', float_precision='round_trip')
selection = pd.read_csv(data_dir / 'A_B_case_mapping.csv', float_precision='round_trip')
sample = pd.read_csv(data_dir / 'valid_sample_records.csv.gz', float_precision='round_trip')
summary = json.loads((data_dir / 'summary.json').read_text(encoding='utf-8'))
assert summary['passed'] is True and len(cases) == 24 and len(selection) == 16
assert len(sample) == 28852 and sample.total_fuel_kg.gt(0).all()
assert set(sample['起飞机场']) == {'首都机场', '滨海机场'}
cases['airport_en'] = cases.departure_airport_name.map(airport_names)
selected = selection[selection.schedule.eq('baseline')].copy()
selected['airport_en'] = selected.model_airport.map(airport_names)
selected = selected.merge(cases, on=['case_index', 'airport_en'], how='left', validate='one_to_one', suffixes=('', '_case'))
assert np.array_equal(selected.saved_fuel_kg.to_numpy(), selected.weekly_total_fuel_kg_total.to_numpy())
assert float(selected.saved_fuel_kg.sum()) == summary['A_B']['baseline']['demand_kg']
chosen = sorted(selected.case_index.unique().tolist())
assert chosen == [0, 1, 3, 10]
plt.rcParams.update({'font.family': 'sans-serif', 'font.sans-serif': ['Arial'], 'font.size': 8,
    'axes.labelsize': 8.5, 'xtick.labelsize': 7, 'ytick.labelsize': 7, 'axes.linewidth': .7,
    'legend.fontsize': 6.8, 'legend.frameon': False, 'figure.facecolor': 'white', 'axes.facecolor': 'white',
    'pdf.fonttype': 42, 'ps.fonttype': 42, 'savefig.dpi': 300, 'axes.unicode_minus': False})


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def style(ax, label):
    for side in ['top', 'right']:
        ax.spines[side].set_visible(False)
    for side in ['left', 'bottom']:
        ax.spines[side].set_color('#CBD5E1')
    ax.tick_params(colors='#334155', direction='out', length=4, width=.8)
    ax.grid(axis='y', color='#CBD5E1', linewidth=.8, linestyle='--', alpha=.3)
    ax.set_axisbelow(True)
    ax.text(-.10, 1.02, f'({label})', transform=ax.transAxes, fontsize=10, fontweight='bold',
            color='#333333', va='bottom', ha='left', clip_on=False)


def save(fig, number):
    for extension in ['png', 'pdf']:
        fig.savefig(figures / f'Figure_S{number}.{extension}', dpi=300, bbox_inches='tight', pad_inches=.04, facecolor='white')
    plt.close(fig)


def handles():
    return [Line2D([0], [0], color=colors[name], marker='o', lw=1.6, markersize=3.8, label=name) for name in colors]


def selected_handle():
    return Line2D([0], [0], marker='D', color='none', markerfacecolor='white', markeredgecolor='#333333',
                  markersize=5, label='Selected demand case (A)')


def four_labels():
    rows = selected[selected.airport_en.eq('Beijing')].sort_values('model_week_number')
    return [f"M{int(row.model_week_number)} / C{int(row.case_index)}\n{months[int(row.case_index)]} / R{int(row.resource_source_week_label)}"
            for row in rows.itertuples(index=False)]


def bars(ax, column, scale=1, legend=False):
    x = np.arange(4)
    for offset, name in zip([-.2, .2], colors, strict=True):
        rows = selected[selected.airport_en.eq(name)].sort_values('model_week_number')
        ax.bar(x + offset, rows[column].to_numpy() / scale, .4, color=colors[name], alpha=.85, edgecolor='white', linewidth=.7, label=name)
    ax.set_xticks(x, four_labels())
    if legend:
        ax.legend(loc='upper right')


def series(ax, annotate=False):
    for name in colors:
        rows = cases[cases.airport_en.eq(name)].sort_values('case_index')
        x = rows.case_index.to_numpy()
        y = rows.weekly_total_fuel_kg_total.to_numpy() / 1e6
        ax.plot(x, y, color=colors[name], marker='o', markersize=3.8, lw=1.6, label=name)
        keep = rows.case_index.isin(chosen)
        ax.scatter(x[keep], y[keep], s=42, marker='D', facecolors='white', edgecolors='#333333', linewidth=.85, zorder=5)
        if annotate and name == 'Beijing':
            for pos, value in zip(x[keep], y[keep], strict=True):
                ax.annotate(f'C{pos}', (pos, value), xytext=(0, 8), textcoords='offset points', ha='center', fontsize=6.7)
    for case in chosen:
        ax.axvline(case, color='#CBD5E1', ls='--', lw=.8, zorder=0)
    ax.set(xlim=(-.35, 11.35), ylim=(0, 13.1), xlabel='Sample-based demand case', ylabel='Fuel demand (million kg)')
    ax.set_xticks(range(12))


fig = plt.figure(figsize=(7.2, 5.4), dpi=300)
grid = fig.add_gridspec(2, 2, left=.08, right=.985, top=.965, bottom=.14, wspace=.30, hspace=.44)
ax = fig.add_subplot(grid[0, 0]); bars(ax, 'saved_fuel_kg', 1e6, True)
ax.set_ylabel('Sample fuel demand (million kg)'); ax.set_ylim(0, 12.8); style(ax, 'a')
ax = fig.add_subplot(grid[0, 1])
markers = ['o', 's', '^', 'D']
for row in selected.itertuples(index=False):
    ax.scatter(row.weekly_distance_km_total / 1e6, row.saved_fuel_kg / 1e6, s=row.total_flights / 16,
               marker=markers[int(row.model_week_number)-1], facecolors='none', alpha=.8,
               edgecolors=colors[row.airport_en], linewidth=.95)
ax.set(xlabel='Sample distance sum (million km)', ylabel='Sample fuel demand (million kg)', xlim=(0, 3.1), ylim=(0, 12.8))
airport_legend = ax.legend(handles=handles(), loc='upper left'); ax.add_artist(airport_legend)
size_legend = ax.legend(handles=[ax.scatter([], [], s=count / 16, facecolors='none', edgecolors='#94A3B8',
                                          linewidth=.8, label=f'{count:,}') for count in [500, 1000, 2000]],
                        title='Record count', loc='center left', bbox_to_anchor=(0, .64), fontsize=5.8,
                        title_fontsize=6.1, labelspacing=.6)
ax.add_artist(size_legend)
ax.legend(handles=[Line2D([0], [0], marker=marker, color='none', markerfacecolor='#475569', markeredgecolor='white', markersize=5,
                          label=f'Model week {index+1}') for index, marker in enumerate(markers)], loc='lower right', ncol=2, fontsize=6)
style(ax, 'b')
ax = fig.add_subplot(grid[1, 0])
phase_columns = ['weekly_climb_fuel_kg_total', 'weekly_cruise_fuel_kg_total', 'weekly_descent_fuel_kg_total']
phase = selected.groupby('airport_en')[phase_columns].sum().reindex(colors)
phase = phase.div(phase.sum(axis=1), axis=0) * 100
bottom = np.zeros(2)
for column, label, color in zip(phase_columns, ['Climb', 'Cruise', 'Descent'], ['#4DBBD5', '#3C5488', '#E64B35'], strict=True):
    values = phase[column].to_numpy(); ax.bar(range(2), values, bottom=bottom, color=color, alpha=.85, edgecolor='white', label=label)
    bottom += values
ax.set_xticks(range(2), list(colors)); ax.set(ylabel='Fuel share (%)', ylim=(0, 105))
ax.legend(loc='lower center', bbox_to_anchor=(.5, 1.015), ncol=3, fontsize=6.2)
style(ax, 'c')
ax = fig.add_subplot(grid[1, 1])
selected['fuel_per_saved_record_kg'] = selected.saved_fuel_kg / selected.total_flights
bars(ax, 'fuel_per_saved_record_kg'); ax.set(ylabel='Mean fuel per sample record (kg)', ylim=(0, 6800)); style(ax, 'd')
save(fig, 2)


def aircraft_class(value):
    text = str(value)
    for code, fragments in [('B737', ['波音737', 'B737']), ('A320', ['空客320', 'A320']), ('A321', ['空客321', 'A321']),
                             ('A319', ['空客319', 'A319']), ('A330', ['空客330', 'A330']), ('B787', ['波音787', 'B787']),
                             ('Regional jet', ['ERJ', 'CRJ', '庞巴迪']), ('Turbo-prop', ['新舟', '涡桨'])]:
        if any(fragment in text for fragment in fragments):
            return code
    return 'Other/Unknown'


sample['aircraft_class'] = sample['机型'].map(aircraft_class)
aircraft = sample.groupby('aircraft_class', as_index=False).agg(records=('total_fuel_kg', 'size'), total_fuel_kg=('total_fuel_kg', 'sum'),
                                                              mean_distance_km=('distance_km', 'mean'))
aircraft['record_share_pct'] = aircraft.records / len(sample) * 100
aircraft['fuel_share_pct'] = aircraft.total_fuel_kg / sample.total_fuel_kg.sum() * 100
aircraft = aircraft.sort_values('records', ascending=False)
assert int(aircraft.records.sum()) == len(sample) and np.isclose(aircraft.fuel_share_pct.sum(), 100)
aircraft_colors = {'B737': '#3C5488', 'A320': '#E64B35', 'A321': '#00A087', 'A319': '#4DBBD5', 'A330': '#F39B7F',
                   'B787': '#2C7FB8', 'Regional jet': '#6B7280', 'Turbo-prop': '#A16207', 'Other/Unknown': '#D1D5DB'}
fig = plt.figure(figsize=(7.2, 5.4), dpi=300)
grid = fig.add_gridspec(2, 2, left=.10, right=.985, top=.89, bottom=.12, height_ratios=[1.02, 1], wspace=.33, hspace=.45)
ax = fig.add_subplot(grid[0, :]); series(ax, True); style(ax, 'a')
fig.legend(handles=handles() + [selected_handle()], loc='upper center', bbox_to_anchor=(.53, .99), ncol=3, fontsize=6.7)
ax = fig.add_subplot(grid[1, 0])
ax.barh(aircraft.aircraft_class, aircraft.record_share_pct, color=[aircraft_colors[name] for name in aircraft.aircraft_class], alpha=.85, edgecolor='white')
ax.invert_yaxis()
for pos, value in enumerate(aircraft.record_share_pct):
    ax.text(value + .7, pos, f'{value:.1f}%', va='center', fontsize=6.5)
ax.set(xlabel='Share of valid fuel records (%)', xlim=(0, float(aircraft.record_share_pct.max()) * 1.22)); style(ax, 'b')
ax = fig.add_subplot(grid[1, 1])
maximum = int(aircraft.records.max())
ax.scatter(aircraft.mean_distance_km, aircraft.fuel_share_pct, s=aircraft.records / maximum * 320,
           c=[aircraft_colors[name] for name in aircraft.aircraft_class], alpha=.85, edgecolor='white', linewidth=.8)
offsets = {'A321': (6, -7), 'A319': (6, 5), 'B787': (6, -5), 'Other/Unknown': (6, 5), 'Regional jet': (6, -5)}
for row in aircraft.itertuples(index=False):
    ax.annotate(row.aircraft_class, (row.mean_distance_km, row.fuel_share_pct), xytext=offsets.get(row.aircraft_class, (6, 1)),
                textcoords='offset points', ha='left', va='center', fontsize=6.1, color='#334155')
counts = sorted({int(round(maximum * fraction / 500) * 500) for fraction in [.2, .5, 1]})
ax.legend(handles=[ax.scatter([], [], s=count / maximum * 320, color='#94A3B8', alpha=.5, edgecolor='none', label=f'{count:,}') for count in counts],
          title='Record count', loc='upper left', fontsize=6, title_fontsize=6.3, labelspacing=.6)
ax.set(xlabel='Mean flight distance (km)', ylabel='Share of sample fuel demand (%)',
       xlim=(aircraft.mean_distance_km.min() - 100, aircraft.mean_distance_km.max() + 270), ylim=(-1, aircraft.fuel_share_pct.max() + 5))
style(ax, 'c'); save(fig, 3)


fig = plt.figure(figsize=(7.2, 5.0), dpi=300)
grid = fig.add_gridspec(1, 2, left=.08, right=.985, top=.96, bottom=.20, wspace=.27)
ax = fig.add_subplot(grid[0, 0]); ranks = []
for position, name in enumerate(colors):
    rows = cases[cases.airport_en.eq(name)].sort_values('case_index')
    jitter = np.linspace(-.30, .30, 12)
    ax.scatter(position + jitter, rows.weekly_total_fuel_kg_total / 1e6, s=16, facecolor='white', edgecolor=colors[name], linewidth=.8)
    kept = rows.case_index.isin(chosen)
    ax.scatter(position + jitter[kept], rows.loc[kept, 'weekly_total_fuel_kg_total'] / 1e6, marker='D', s=34, color=colors[name], edgecolor='white', zorder=5)
ax.set_xticks([0, 1], list(colors)); ax.set(ylabel='Sample fuel demand (million kg)', ylim=(0, 12.8), xlim=(-.45, 1.45)); style(ax, 'a')
ax = fig.add_subplot(grid[0, 1])
for name in colors:
    rows = cases[cases.airport_en.eq(name)].sort_values(['weekly_total_fuel_kg_total', 'case_index']).copy()
    rows['case_rank'] = np.arange(1, 13)
    rows['selected_in_A'] = rows.case_index.isin(chosen)
    ranks.extend(rows[['airport_en', 'case_index', 'case_rank', 'weekly_total_fuel_kg_total', 'selected_in_A']].to_dict('records'))
    ax.plot(rows.case_rank, rows.weekly_total_fuel_kg_total / 1e6, color=colors[name], marker='o', markersize=3, lw=1.5)
    for row in rows[rows.selected_in_A].itertuples(index=False):
        ax.scatter(row.case_rank, row.weekly_total_fuel_kg_total / 1e6, marker='D', s=34, color=colors[name], edgecolor='white', zorder=5)
        offset = (-10, 10) if name == 'Tianjin' and row.case_index == 0 else ((6, -13) if name == 'Tianjin' and row.case_index == 1 else (0, 9))
        ax.annotate(f'C{int(row.case_index)}', (row.case_rank, row.weekly_total_fuel_kg_total / 1e6), xytext=offset,
                    textcoords='offset points', fontsize=6.3, ha='center', color=colors[name])
ax.set(xlabel='Rank among 12 demand cases', ylabel='Sample fuel demand (million kg)', ylim=(0, 12.8), xlim=(.6, 12.4))
ax.set_xticks([1, 3, 6, 9, 12]); style(ax, 'b')
fig.legend(handles=handles() + [Line2D([0], [0], marker='o', color='none', markerfacecolor='white', markeredgecolor='#6B7280', markersize=4, label='12 demand cases'),
                             Line2D([0], [0], marker='D', color='none', markerfacecolor='#333333', markeredgecolor='white', markersize=5, label='Selected cases (A)')],
           loc='lower center', bbox_to_anchor=(.51, .015), ncol=4, fontsize=6.5)
save(fig, 4)


fig = plt.figure(figsize=(7.2, 5.0), dpi=300)
grid = fig.add_gridspec(1, 2, left=.09, right=.985, top=.86, bottom=.19, wspace=.28)
ax = fig.add_subplot(grid[0, 0]); series(ax, True); style(ax, 'a')
ax = fig.add_subplot(grid[0, 1]); bars(ax, 'saved_fuel_kg', 1e6); ax.set(ylabel='Sample fuel demand (million kg)', ylim=(0, 13.1)); style(ax, 'b')
fig.legend(handles=handles() + [selected_handle()], loc='upper center', bbox_to_anchor=(.53, .99), ncol=3, fontsize=6.8)
save(fig, 5)

cases.to_csv(data_out / 'case_series.csv', index=False)
selected.to_csv(data_out / 'selected_cases.csv', index=False)
aircraft.to_csv(data_out / 'aircraft_summary.csv', index=False)
pd.DataFrame(ranks).to_csv(data_out / 'case_ranks.csv', index=False)
captions = {
 'S2': 'Four selected sample-based demand cases. (a) Fuel demand assigned to model weeks M1–M4. (b) Fuel demand and summed sample flight distance; marker area represents record count and marker shape identifies model week. (c) Fuel shares of climb, cruise and descent across the four selected cases. (d) Mean fuel per included record. C denotes the zero-based demand-case index and R the paired resource block; the source month is also shown beneath each selected model week.',
 'S3': 'Demand-case magnitude and composition of the retained departure-airport sample. (a) The 12 demand cases; diamonds mark cases selected for A. (b) Aircraft-class shares among 28,852 valid fuel-estimation records departing Capital or Binhai. (c) Mean flight distance and fuel share by aircraft class; marker area represents record count. The 115 records lacking saved fuel estimates are excluded from composition statistics. Source records are retained without deduplication.',
 'S4': 'Distribution and ordering of the 12 retained sample-based demand cases. (a) Every case value is shown separately for each airport. (b) The same 12 values are ranked within airport, with ties ordered by case index. Diamonds identify the four cases selected for A. The display describes the finite case set.',
 'S5': 'Mapping from the retained demand-case pool to the four model weeks. (a) The original 12 case values, with selected cases highlighted. (b) The four selected case values assigned to M1–M4. C denotes zero-based case index and R the paired resource block; the source month is also stated beneath the selected model-week labels.'}
report = {'schema_version': 1, 'passed': True, 'case_contract_manifest_sha256': summary['manifest_sha256'],
          'source_sha256': {name: sha(data_dir / name) for name in ['case_values.csv', 'A_B_case_mapping.csv', 'valid_sample_records.csv.gz', 'summary.json']},
          'render_source_sha256': sha(__file__), 'retained_case_values': 24, 'selected_mapping_values': 16,
          'composition_valid_records': len(sample), 'composition_excluded_records': 115,
          'deduplication_applied': False, 'new_model_inputs_generated': False, 'captions': captions,
          'figures': [{'path': path.name, 'bytes': path.stat().st_size, 'sha256': sha(path)} for path in sorted(figures.glob('Figure_S[2345].*'))],
          'data': [{'path': name, 'sha256': sha(data_out / name)} for name in
                   ['case_series.csv', 'selected_cases.csv', 'aircraft_summary.csv', 'case_ranks.csv']]}
(out / 'render_manifest_S2_S5.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({key: report[key] for key in ['passed', 'retained_case_values', 'composition_valid_records', 'figures']}, ensure_ascii=False))
