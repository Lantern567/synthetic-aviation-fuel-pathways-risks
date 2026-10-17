import argparse
import importlib.util
import importlib.metadata
import json
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'python_dependencies'))

from adjustText import adjust_text
import fitz
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib import font_manager
from matplotlib.lines import Line2D
from matplotlib.text import Text
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

from build_inputs import BASELINES, TEMPLATES, configure_sources, digest, read_json, write_json


def source_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.__file__ = str(HERE / (name + '.py'))
    return module


def verify_inputs(data):
    manifest = read_json(data / 'figure_inputs.json')
    if manifest['ready'] is not True or manifest['new_run_count'] != 18 or manifest['baseline_pathway_count'] != 13:
        raise ValueError('Eighteen new verified runs and the preserved GTL record are required')
    for name, expected in read_json(data / 'SHA256.json').items():
        if digest(data / name) != expected:
            raise ValueError(f'Figure input changed: {name}')
    for record in manifest['sources']:
        if digest(Path(record['path'])) != record['sha256']:
            raise ValueError(f'Bound source changed: {record["path"]}')
    if set(read_json(data / 'manifest.json')) != set(BASELINES):
        raise ValueError('Baseline pathway set differs from the figure contract')


def redirect(configurations, data):
    for key, record in configurations.items():
        scenario = record.get('name_en', key)
        record['solution_pattern'] = str(data / f'{scenario}_complete_solution.json')
        record['carbon_pattern'] = str(data / f'{scenario}_carbon_emissions.json')


def compose_main(output):
    canvas = Image.new('RGB', (4836, 3457), 'white')
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.truetype(font_manager.findfont(font_manager.FontProperties(family='Times New Roman', weight='bold'), fallback_to_default=False), 74)

    def panel(path, rectangle, crop=None):
        picture = Image.open(path).convert('RGBA')
        if crop is not None:
            picture = picture.crop(crop)
        background = Image.new('RGB', picture.size, 'white')
        background.paste(picture, mask=picture.getchannel('A'))
        x, y, width, height = rectangle
        canvas.paste(background.resize((width, height), Image.Resampling.LANCZOS), (x, y))

    panel(output / 'quadrant_chart_box.png', (70, 15, 2535, 1795))
    panel(output / 'market_price_gap_lollipop.png', (2800, 125, 1910, 1760))
    draw.text((120, 33), '(a)', font=font, fill='black')
    draw.text((2650, 33), '(b)', font=font, fill='black')
    for scenario, tag, rectangle in zip(['CCU-GH-FT', 'GTL', 'GTL-BH'], 'cde', [(35, 1970, 1460, 1450), (1515, 1970, 1460, 1450), (2980, 1970, 1460, 1450)]):
        picture = Image.open(output / f'{scenario}_polar.png')
        side = min(picture.height, picture.width)
        panel(output / f'{scenario}_polar.png', rectangle, (0, 0, side, side))
        draw.text((rectangle[0] + 80, 1870), f'({tag})  {scenario}', font=font, fill='black')
    legend = [('Feedstock', '#BDBDBD'), ('Hydrogen', '#42A5F5'), ('CO2 Capture', '#90CAF9'),
              ('Conversion', '#64B5F6'), ('Power', '#BBDEFB'), ('Facility', '#66BB6A'),
              ('Transport', '#A5D6A7'), ('Storage', '#C8E6C9')]
    legend_font = ImageFont.truetype(font_manager.findfont(font_manager.FontProperties(family='Times New Roman'), fallback_to_default=False), 45)
    for index, (label, color) in enumerate(legend):
        y = 1960 + 86 * index
        draw.rectangle((4410, y + 8, 4508, y + 50), fill=color)
        draw.text((4540, y), label, font=legend_font, fill='black')
    canvas.save(output / 'Figure_1.png', dpi=(300, 300))
    pdf = fitz.open()
    page = pdf.new_page(width=1160.64, height=829.68)
    page.insert_image(page.rect, filename=str(output / 'Figure_1.png'))
    pdf.save(output / 'Figure_1.pdf', deflate=True)
    pdf.close()
    canvas.thumbnail((1880, 1500))
    canvas.save(output / 'Figure_1_preview.png')


def render_sensitivity(data, output, source, save):
    render_fossil_sensitivity(data, output, source, save)
    grid = pd.read_csv(data / 'S22_fixed_design_grid.csv')
    pivot = grid.pivot(index='grid_price_cny_kwh', columns='electrolyzer_capex_cny_kg_h', values='cost_cny_kg')
    source._save_fig = lambda figure, name: save(figure, output / name, dpi=300, bbox_inches='tight')
    source.FIGURES_DIR = output
    source.plot_electricity_capex_heatmap_appendix({'_ec': {'pivots': {'CCU-GH-MTJ': pivot}}}, output_filename='Figure_S22.png')
    frame = pd.read_csv(data / 'S23_fixed_design_dac.csv')
    dac = {scenario: {'dac_values': rows.dac_cost_cny_t_co2.tolist(), 'lco_values': rows.cost_cny_kg.tolist()}
           for scenario, rows in frame.groupby('scenario', sort=False)}
    source.plot_dac_breakeven_appendix({'_dac': {'per_scenario': dac}, 'dac_ghft_lco_min': min(dac['DAC-GH-FT']['lco_values'])}, output_filename='Figure_S23.png')
    # 原模板的两条路径基线是局部常量；全部基线与排序由真实记录提供。
    components = pd.read_csv(data / 'S24_fixed_design_component_sensitivity.csv')
    components['range'] = components.cost_high_cny_kg - components.cost_low_cny_kg
    frame = components.loc[components.groupby('scenario')['range'].idxmax()].sort_values('cost_baseline_cny_kg', ascending=False).reset_index(drop=True)
    figure, axis = plt.subplots(figsize=(11, max(4.5, .52 * len(frame) + 1.5)))
    axis.axvspan(6, 8, alpha=.12, color='#2ca02c', zorder=0)
    for value in [6, 8]:
        axis.axvline(value, color='#2ca02c', linestyle='--', linewidth=.9, alpha=.75, zorder=1)
    names = {'electricity_cost': 'Power cost', 'natural_gas_cost': 'NG cost', 'electrolyzer_investment_cost': 'H2 CAPEX',
             'facility_operation_cost': 'Facility OPEX', 'facility_investment_cost': 'Facility CAPEX',
             'coal_purchase_cost': 'Coal cost', 'dac_capture_cost': 'DAC cost', 'hydrogen_production_cost': 'H2 production'}
    for index, row in enumerate(frame.itertuples()):
        color = source.SCENARIO_COLORS.get(row.scenario, '#aaaaaa')
        axis.barh(index, row.range, left=row.cost_low_cny_kg, color=color, alpha=.75, edgecolor='white', linewidth=.6, height=.62, zorder=2)
        axis.text(row.cost_high_cny_kg + .3, index, f'Δ{row.range:.1f}', va='center', fontsize=8, fontfamily='Times New Roman', color='dimgray')
        axis.text(row.cost_low_cny_kg - .3, index, names.get(row.component, row.component.replace('_', ' ')), va='center', ha='right', fontsize=7, fontfamily='Times New Roman', color='dimgray', style='italic')
        axis.scatter(row.cost_baseline_cny_kg, index, s=55, color='black', marker='D', zorder=5, linewidths=0)
    axis.set_yticks(range(len(frame)), frame.scenario, fontfamily='Times New Roman', fontsize=9.5)
    axis.set_ylim(-.6, len(frame) - .4)
    axis.set_xlim(max(0, frame.cost_low_cny_kg.min() - 3), frame.cost_high_cny_kg.max() + 3)
    axis.legend(handles=[matplotlib.patches.Patch(fc='#2ca02c', alpha=.25), Line2D([], [], marker='D', color='black', linestyle='None')],
                labels=['Market window (6–8 CNY/kg)', 'Baseline unit cost'], fontsize=8, loc='upper right', framealpha=.85)
    source._apply_pub_style(axis, 'LCO-SynAF (CNY/kg)', '', 'Fixed-design sensitivity: largest component cost ±20%')
    figure.tight_layout()
    save(figure, output / 'Figure_S24.png', dpi=300, bbox_inches='tight')
    metrics = pd.read_csv(data / 'pathway_summary.csv')
    metrics['category'] = metrics.scenario.map(lambda scenario: 'Grey' if scenario.startswith('CTL') else 'Green' if '-GH-' in scenario else 'Blue')
    ft = set(read_json(data / 'learning_assumptions.json')['FT_learning_group'])
    metrics['route'] = metrics.scenario.map(lambda scenario: 'FT' if scenario in ft else 'MTJ')
    colors = {'Grey': '#8491B4', 'Blue': '#3C5488', 'Green': '#00A087'}
    plt.rcParams.update({'font.family': 'Arial', 'font.size': 8, 'axes.labelsize': 8.5, 'xtick.labelsize': 7,
                         'ytick.labelsize': 7, 'legend.fontsize': 6.8, 'axes.linewidth': .7, 'pdf.fonttype': 42})
    figure = plt.figure(figsize=(7.2, 5), dpi=300)
    grid = figure.add_gridspec(1, 2, left=.08, right=.985, top=.88, bottom=.18, wspace=.30)
    left, right = figure.add_subplot(grid[0, 0]), figure.add_subplot(grid[0, 1])
    for route, marker in {'FT': 'o', 'MTJ': 's'}.items():
        rows = metrics[metrics.route.eq(route)]
        left.scatter(rows.carbon_g_mj, rows.cost_cny_kg, marker=marker, s=42, c=rows.category.map(colors), edgecolors='white', linewidth=.7, zorder=3)
    rows = pd.read_csv(data / 'nondominated_envelope.csv').sort_values('carbon_g_mj')
    left.plot(rows.carbon_g_mj, rows.cost_cny_kg, color='#333333', linewidth=1, linestyle='--', zorder=2)
    left.set_xlim(0, metrics.carbon_g_mj.max() * 1.07)
    left.set_ylim(0, metrics.cost_cny_kg.max() * 1.10)
    for index, row in enumerate(rows.itertuples()):
        left.annotate(row.scenario, (row.carbon_g_mj, row.cost_cny_kg),
                      xytext=(12, 14 if index % 2 else -14), textcoords='offset points',
                      fontsize=6.4, color='#334155',
                      arrowprops={'arrowstyle': '-', 'color': '#666666', 'lw': .5})
    left.set_xlabel(r'Supply-chain intensity (g CO$_2$e/MJ)')
    left.set_ylabel('LCO-SynAF (CNY/kg)')
    handles = [Line2D([], [], marker='o', linestyle='None', markerfacecolor=color, markeredgecolor='white', markersize=6, label=category) for category, color in colors.items()]
    handles += [Line2D([], [], marker=marker, linestyle='None', markerfacecolor='#475569', markeredgecolor='white', markersize=6, label=route) for route, marker in {'FT': 'o', 'MTJ': 's'}.items()]
    left.legend(handles=handles, ncol=3, loc='upper center', bbox_to_anchor=(.5, 1.23), frameon=False)
    ordered = metrics.sort_values('cost_cny_kg')
    right.barh(ordered.scenario, ordered.cost_cny_kg, color=ordered.category.map(colors), height=.68)
    right.invert_yaxis()
    right.set_xlabel('LCO-SynAF (CNY/kg)')
    right.set_xlim(0, metrics.cost_cny_kg.max() * 1.13)
    for index, row in enumerate(ordered.itertuples()):
        right.text(row.cost_cny_kg + .4, index, f'{row.carbon_g_mj:.0f}', va='center', fontsize=6.5, color='#334155')
    for index, axis in enumerate([left, right]):
        axis.spines[['top', 'right']].set_visible(False)
        axis.grid(axis='x', color='#CBD5E1', linewidth=.5, alpha=.4)
        axis.set_axisbelow(True)
        axis.text(-.12, 1.03, f'({chr(97 + index)})', transform=axis.transAxes, fontweight='bold', fontsize=9)
    save(figure, output / 'Figure_S25.png', dpi=300, bbox_inches='tight')


def render_fossil_sensitivity(data, output, source, save):
    gas = pd.read_csv(data / 'S20_fixed_design_ng.csv')
    capex = pd.read_csv(data / 'S21_fixed_design_conditioning_capex.csv')
    checks = read_json(data / 'sensitivity_verification.json')
    ng = {name: {'ng_values': rows.gas_price_cny_m3.tolist(), 'lco_values': rows.cost_cny_kg.tolist()}
          for name, rows in gas.groupby('scenario', sort=False)}
    baseline = checks['S20']
    upper = {name: values['effective_ng_price_cny_m3'] + (8 - values['baseline_cost_cny_kg']) / values['ng_m3_per_kg_fuel']
             for name, values in baseline.items()}
    values = {'_ng': {'per_scenario': ng}, 'gtl_ng_threshold': upper['GTL'], 'gtlbh_ng_upper_threshold': upper['GTL-BH'],
              'gtl_effective_baseline_ng': baseline['GTL']['effective_ng_price_cny_m3'],
              'gtlbh_effective_baseline_ng': baseline['GTL-BH']['effective_ng_price_cny_m3'],
              'gtl_lco_at_baseline': baseline['GTL']['baseline_cost_cny_kg'],
              'gtlbh_lco_at_baseline': baseline['GTL-BH']['baseline_cost_cny_kg'],
              'gtl_ng_pct_from_baseline': (upper['GTL'] / baseline['GTL']['effective_ng_price_cny_m3'] - 1) * 100,
              '_bh': {'per_scenario': {'GTL-BH': {'capex_values': capex.steel_capex_cny_kg_h.tolist(), 'lco_values': capex.cost_cny_kg.tolist()}}},
              'bh_gtl_baseline_lco': baseline['GTL']['baseline_cost_cny_kg'],
              'bh_slope_per_100k': checks['S21']['cost_slope_cny_kg_per_100k']}

    def save_fossil(figure, name):
        for item in figure.findobj(Text):
            if '(pipeline avg.)' in item.get_text():
                item.set_text(item.get_text().replace('(pipeline avg.)', '(cost-ledger price)'))
                item.set_position((baseline['GTL']['effective_ng_price_cny_m3'] + .06, 13.3))
            if name == 'Figure_S21.png' and item.get_text() in ['Steel\n280k', 'Refinery\n224k']:
                item.set_y(6.02)
        save(figure, output / name, dpi=300, bbox_inches='tight')

    source._save_fig, source.FIGURES_DIR = save_fossil, output
    source.plot_ng_price_sensitivity_appendix(values, output_filename='Figure_S20.png')
    source.plot_bh_capex_sensitivity_appendix(values, output_filename='Figure_S21.png')
    write_json(output / 'S20_S21_fixed_design_plot_values.json', values)


def format_sensitivity_figure(figure, name):
    if name == 'Figure_S22.png':
        axis = figure.axes[0]
        axis.set_xticklabels([item.get_text().removesuffix('k') for item in axis.get_xticklabels()])


def render(data, output):
    verify_inputs(data)
    output.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(TEMPLATES['polar'].parent))
    box, lollipop, polar, breakdown, sensitivity, stitch = [source_module('new_cost_' + key, TEMPLATES[key]) for key in ['quadrant', 'lollipop', 'polar', 'breakdown', 'sensitivity', 'stitch']]
    solutions = {scenario: read_json(data / f'{scenario}_complete_solution.json') for scenario in BASELINES}
    carbons = {scenario: read_json(data / f'{scenario}_carbon_emissions.json') for scenario in BASELINES}
    learning = pd.read_csv(data / 'learning_projections.csv')
    categories = pd.read_csv(data / 'learning_categories.csv')
    projection = lambda solution, scenario: learning.loc[learning.scenario.eq(scenario)].sort_values('year').cost_cny_kg.to_numpy()
    box.compute_lcoe_projection = projection
    lollipop.compute_lcoe_projection = projection
    polar.compute_category_trajectories = lambda costs, cost, scenario: {category: categories.loc[categories.scenario.eq(scenario) & categories.category.eq(category)].sort_values('year').cost_cny_kg.to_numpy() for category in polar.CATEGORIES}
    polar.SAF_LHV_MJ_PER_KG = 43.15
    original_save, saved, text_audit = Figure.savefig, set(), {}

    def save(figure, filename, *args, **kwargs):
        path = Path(filename)
        format_sensitivity_figure(figure, path.name)
        quadrant = path.name.startswith('quadrant_chart_box')
        for text in list(figure.findobj(Text)):
            value = text.get_text()
            if quadrant and (value in ('Lower emission', 'Higher emission') or value.startswith('Baseline:') or 'g/MJ (−10%)' in value or 'g/MJ (−70%)' in value):
                text.remove()
                continue
            value = value.replace('LCOE', 'LCO-SynAF').replace('LCO-SAF', 'LCO-SynAF').replace('Levelized cost of SAF', 'LCO-SynAF')
            value = value.replace('SAF pathways', 'SynAF pathways')
            if 'Carbon intensity difference vs traditional jet fuel' in value:
                value = r'Supply-chain intensity (g CO$_2$e/MJ)'
            value = value.replace('Pareto-optimal region', 'Cost–carbon envelope').replace('Representative frontier', 'Selected pathway')
            value = value.replace('Cost composition of representative Pareto pathways', 'Cost composition of selected pathways')
            value = value.replace('Positive emissions composition of representative Pareto pathways', 'Positive supply-chain emissions of selected pathways')
            if value.startswith('LCO-SynAF Heat Map:'):
                value = 'CCU-GH-MTJ: fixed-design cost sensitivity'
            if value.startswith('IEA 2030'):
                value = 'Illustrative\n100 CNY/t'
            if value == 'Cost (CNY/kg)':
                value = 'LCO-SynAF\n(CNY/kg)'
                text.set_fontsize(12)
            if value == 'Carbon (g CO2e/MJ)':
                value = 'Gross carbon\n(g CO2e/MJ)'
                text.set_fontsize(12)
            text.set_text(value)
            if path.name.startswith('market_price_gap_lollipop'):
                text.set_color('#222222')
        if quadrant:
            for axis in figure.axes[:2]:
                for line in list(axis.lines):
                    x = np.asarray(line.get_xdata(), dtype=float)
                    if len(x) == 2 and x[0] == x[1] and line.get_color() == '#AAAAAA' and line.get_linestyle() == '-.':
                        line.remove()
        if path.name == 'Figure_S23.png':
            axis = figure.axes[0]
            ymin, ymax = axis.get_ylim()
            for text in axis.texts:
                if text.get_text() == 'Illustrative\n100 CNY/t':
                    text.set_position((110, 8.4))
                elif text.get_text() == 'Baseline\n4,500 ¥/t':
                    text.set_position((4440, ymin + .08 * (ymax - ymin)))
                    text.set_horizontalalignment('right')
            axis.get_legend().set_loc('upper left')
        if path.name.startswith(('pareto_cost_appendix', 'pareto_cost_breakdown_appendix',
                                 'pareto_carbon_appendix', 'pareto_carbon_breakdown_appendix')):
            if not getattr(figure, '_revision_legend_spacing', False):
                for axis in figure.axes:
                    bounds = axis.get_position()
                    axis.set_position([bounds.x0, bounds.y0 + .06, bounds.width, bounds.height - .06])
                for legend in figure.legends:
                    legend.set_bbox_to_anchor((.5, .04))
                figure._revision_legend_spacing = True
        if path.suffix == '.png':
            text_audit[path.name] = [text.get_text() for text in figure.findobj(Text) if text.get_text()]
        original_save(figure, filename, *args, **kwargs)
        if path.suffix == '.png':
            pdf_kwargs = dict(kwargs)
            pdf_kwargs.pop('dpi', None)
            original_save(figure, path.with_suffix('.pdf'), *args, **pdf_kwargs)
            saved.add(path.name)

    Figure.savefig = save
    quadrant = box.QuadrantBoxVisualizer()
    quadrant.output_dir = quadrant.session_dir = output
    quadrant.BOX_X_FRACTION_L = .004
    redirect(quadrant.modules, data)
    quadrant.load_data()
    if len(quadrant.data) != 13:
        raise ValueError('Quadrant did not load all thirteen real baseline records')
    for record in quadrant.data.values():
        record['carbon_diff'] = carbons[record['name_en']]['carbon_intensity_mj']
    points = np.unique(sorted(record['carbon_diff'] for record in quadrant.data.values()))
    if len(points) < 2:
        raise ValueError('Broken axes require distinct actual carbon intensities')
    split = int(np.argmax(np.diff(points)))
    gap = points[split + 1] - points[split]
    quadrant.X_BREAK_LEFT = float(points[split] + .3 * gap)
    quadrant.X_BREAK_RIGHT = float(points[split + 1] - .3 * gap)
    quadrant.pareto_optimal_names = pd.read_csv(data / 'nondominated_envelope.csv').scenario.tolist()

    def background(axis, xmin, xmax, ymin, ymax):
        axis.fill_between([xmin, xmax], ymin, quadrant.market_price_low, color='#FFF3E0', alpha=.6, zorder=0)
        axis.fill_between([xmin, xmax], quadrant.cost_threshold, ymax, color='#F2F2F2', alpha=.6, zorder=0)
        axis.fill_between([xmin, xmax], quadrant.market_price_low, quadrant.cost_threshold, color='#FFF8E1', alpha=.55, zorder=0)
        for price in [quadrant.market_price_low, quadrant.cost_threshold]:
            axis.axhline(price, color='#999999', linestyle='--', lw=1.2, zorder=1)

    quadrant._apply_shared_background = background
    quadrant.plot_quadrant_chart()
    gap_plot = lollipop.MarketPriceGapLollipopVisualizer()
    gap_plot.output_dir = gap_plot.session_dir = output
    redirect(gap_plot.modules, data)
    table = gap_plot.build_gap_table()
    gap_plot.plot_lollipop_chart(table)
    for extension in ['png', 'pdf']:
        shutil.copyfile(output / f'market_price_gap_lollipop.{extension}', output / f'Figure_1b.{extension}')
    table.to_csv(output / 'cost_gap_2026_2036.csv', index=False)
    for index, scenario in enumerate(BASELINES, start=36):
        solution, carbon = solutions[scenario], carbons[scenario]
        emissions = polar._aggregate(carbon['detailed'], 'carbon_keys')
        positive = sum(max(value, 0) for value in carbon['detailed'].values())
        if not np.isclose(sum(emissions.values()), positive, rtol=1e-9, atol=1e-3):
            raise ValueError(f'Carbon donut component closure failed: {scenario}')
        polar.draw_concentric_rings(scenario, solution['cost_breakdown'], emissions, solution['lifecycle_levelized_cost_excluding_shortage_per_kg'], output / f'{scenario}_polar.png', total_production_kg=carbon['total_production_kg'])
        polar.draw_donut(polar._aggregate(solution['cost_breakdown'], 'cost_keys'), 'Cost\nShare', output / f'{scenario}_cost.png')
        polar.draw_donut(emissions, 'Carbon\nShare', output / f'{scenario}_carbon.png')
        stitch.stitch_white(output / f'{scenario}_polar.png', output / f'{scenario}_cost.png', output / f'{scenario}_carbon.png', output / f'Figure_S{index}.png')
    si = breakdown.ParetoBreakdownVisualizer(output, output)
    redirect(si.scenarios, data)
    si.load_data()
    si.selected_pareto = ['CCU-GH-FT', 'GTL', 'GTL-BH']
    si.pathway_roles = {scenario: f'{solutions[scenario]["demand_fulfillment_ratio"]:.2%} demand served' for scenario in si.selected_pareto}
    original_card = si._scenario_card_text

    def scenario_card(scenario, metric_type):
        if metric_type != 'carbon':
            return original_card(scenario, metric_type)
        record = si.data[scenario]
        return '\n'.join([scenario, si.pathway_roles[scenario],
                          f'Supply-chain CI: {carbons[scenario]["carbon_intensity_mj"]:.1f} gCO2e/MJ',
                          f'Net emissions: {record["net_emissions"] / 1e6:.2f} Mkg CO2e',
                          f'Credits: {record["credit_emissions"] / 1e6:.2f} Mkg CO2e'])

    si._scenario_card_text = scenario_card
    for scenario, record in si.data.items():
        record['total_cost'] = sum(record['cost_breakdown'].values())
    si.create_appendix_metric_figure('cost')
    si.create_appendix_metric_figure('carbon')
    for source_name, target_name in [('pareto_cost_appendix', 'Figure_S28'), ('pareto_carbon_appendix', 'Figure_S29')]:
        for extension in ['png', 'pdf']:
            shutil.copyfile(output / f'{source_name}.{extension}', output / f'{target_name}.{extension}')
    render_sensitivity(data, output, sensitivity, save)
    compose_main(output)
    Figure.savefig = original_save
    write_json(output / 'figure_text_audit.json', text_audit)
    write_json(output / 'render_manifest.json', {'input_manifest_sha256': digest(data / 'figure_inputs.json'),
                                               'renderer_sha256': digest(Path(__file__)),
                                               'templates_sha256': {name: digest(path) for name, path in TEMPLATES.items()},
                                               'figures': ['Figure_1', 'Figure_1b'] + [f'Figure_S{number}' for number in [20, 21, 22, 23, 24, 25, 28, 29] + list(range(36, 49))],
                                               'Figure1_x_coordinate': 'Direct supply-chain carbon intensity, without reference subtraction or percentage-reduction lines',
                                               'product_cost_label': 'LCO-SynAF', 'visual_qa_completed': False})
    write_json(output / 'render_environment.json', {'python': sys.version, 'platform': sys.platform,
               'packages': {name: importlib.metadata.version(name) for name in ['numpy', 'pandas', 'PyYAML', 'matplotlib', 'Pillow', 'PyMuPDF', 'adjustText']},
               'font_family': 'Times New Roman',
               'regular_font_sha256': digest(Path(font_manager.findfont(font_manager.FontProperties(family='Times New Roman'), fallback_to_default=False))),
               'bold_font_sha256': digest(Path(font_manager.findfont(font_manager.FontProperties(family='Times New Roman', weight='bold'), fallback_to_default=False)))})
    print(json.dumps({'rendered': True, 'output': str(output.resolve()), 'visual_qa_completed': False}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=Path, default=HERE / 'adapted_data')
    parser.add_argument('--out', type=Path, default=HERE / 'figures')
    parser.add_argument('--source-manifest', type=Path)
    args = parser.parse_args()
    if args.source_manifest:
        configure_sources(args.source_manifest)
    render(args.data.resolve(), args.out.resolve())
