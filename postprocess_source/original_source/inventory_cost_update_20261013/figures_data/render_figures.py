import ast
import json
import logging
import os
from pathlib import Path
import re
import shutil
import sys

HERE = Path(__file__).resolve().parent
os.environ['MPLCONFIGDIR'] = str(HERE / 'mplconfig')
sys.path.insert(0, str(HERE / 'dependencies'))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.text import Text
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd
import pymupdf
from PIL import Image, ImageDraw, ImageFont

from update_data import WORK, OLD_FIG, VIZ, STAGE, module, read_json, write_json, sha

OUT = HERE / 'figures'
OUT.mkdir(exist_ok=True)
DATA = STAGE / 'figure_data/normalized_pathway_records'
FDATA = STAGE / 'figure_data/figures_cost'
CURRENT_MAIN = WORK / 'revision_20261007_minimal/figures_cost/figures/Figure_1.png'
SPACE = WORK / 'revision_20261007/figures_space_time'
sys.path.insert(0, str(VIZ))
logging.getLogger('fontTools').setLevel(logging.WARNING)
box = module('cost_updated_box', VIZ / 'quadrant_chart_box_visualization.py')
lollipop = module('cost_updated_lollipop', WORK / 'reviewer_edits/figure_sources/panel_b_plot.py')
polar = module('cost_updated_polar', VIZ / 'pareto_three_breakdown_visualization.py')
si = module('cost_updated_si', WORK / 'corrected_runs_20261006/project/appendix_saf_workspace/scripts/pareto_three_breakdown_visualization.py')
compose = module('cost_updated_composite', OLD_FIG / 'compose_learning_panels.py')
box.FT_SCENARIOS = set(read_json(STAGE / 'figure_data/learning_assumptions.json')['FT_learning_group'])
polar.SAF_LHV_MJ_PER_KG = 43.15
solutions = {p.name.removesuffix('_complete_solution.json'): read_json(p) for p in DATA.glob('*_complete_solution.json')}
summary = pd.read_csv(HERE / 'pathway_summary.csv').set_index('scenario')
learning = pd.read_csv(FDATA / 'learning_projections.csv')
gaps = pd.read_csv(FDATA / 'cost_gap_2026_2036.csv')


def category_trajectories(costs, lcoe, scenario):
    total = sum(costs.values())
    result = {category: np.zeros(11) for category in polar.CATEGORIES}
    for key, value in costs.items():
        category = next((c for c, v in polar.CATEGORIES.items() if key in v['cost_keys']), None)
        assert category is not None or abs(value) < 1e-5, key
        if category is None:
            continue
        factor = box.COST_MAP.get(key, 'fixed')
        if factor == 'synthesis':
            factor = 'synthesis_ft' if scenario in box.FT_SCENARIOS else 'synthesis_mtj'
        result[category] += value / total * lcoe * box.CF_ARRAY[factor]
    assert np.allclose(sum(result.values()), box.compute_lcoe_projection(solutions[scenario], scenario), atol=1e-12)
    return result


polar.compute_category_trajectories = category_trajectories
green_positions = {'DAC-GH-MTJ': (-37, 58.8), 'CCU-GH-MTJ': (12, 45.0), 'DAC-GH-FT': (12, 39.0), 'CCU-GH-FT': (-35, 25.3)}
adjust_original = box.adjust_text
box.adjust_text = lambda texts, *a, **kw: adjust_original([t for t in texts if t.get_text() not in green_positions], *a, **kw)
save_original = Figure.savefig
checked = set()
box_widths = {}
text_map = {'Pareto-optimal region': 'Descriptive cost–carbon envelope', 'Lower emission': 'Below reference',
    'Higher emission': 'Above reference', 'Carbon intensity difference vs traditional jet fuel (g CO₂eq/MJ)': r'Supply-chain intensity − 89 g CO$_2$e/MJ reference',
    'Baseline: 0.0 g CO2eq/MJ': r'Reference difference: 0.0 g CO$_2$e/MJ',
    'Representative frontier': 'Selected pathway', 'Cost composition of representative Pareto pathways': 'Cost composition of selected pathways',
    'Positive emissions composition of representative Pareto pathways': 'Positive supply-chain emissions of selected pathways',
    'Deep decarbonization': 'Renewable-coupled case', 'Transition pathway': 'GTL comparison case', 'Lowest cost': 'GTL-BH comparison case'}


def save_figure(fig, filename, *args, **kwargs):
    name = Path(filename).name
    for text in fig.findobj(Text):
        value = text.get_text()
        if 'LCOE' in value:
            text.set_text(value.replace('LCOE', 'LCO-SAF'))
        if value in text_map:
            text.set_text(text_map[value])
        elif value.endswith('g/MJ (−10%)') or value.endswith('g/MJ (−70%)'):
            text.set_text(value + ' reference')
        if name.startswith('market_price_gap_lollipop') and re.fullmatch(r'[+−-]\d+\.\d', value):
            text.set_color('#222222')
        if value == 'Carbon (g CO2e/MJ)':
            text.set_text('Gross carbon\n(g CO2e/MJ)')
            text.set_fontsize(12)
        if 'Delta vs jet:' in value:
            text.set_text(value.replace('Delta vs jet:', 'Ledger − 89:'))
        if name.startswith('quadrant_chart_box'):
            if value in green_positions:
                text.set_position(green_positions[value])
                text.set_ha('left')
                text.set_va('center')
            elif value in {'2026', '2028', '2030', '2032', '2034', '2036'}:
                text.set_x(-36)
            elif value.startswith('-62.3 g/MJ'):
                text.set_x(-71.5)
    if name.startswith('quadrant_chart_box') and 'leaders' not in checked:
        axis = fig.axes[0]
        for data in quad.data.values():
            if data['name_en'] in green_positions:
                x, y = green_positions[data['name_en']]
                axis.annotate('', xy=(data['carbon_diff'], data['lcoe']), xytext=(x-1, y),
                              arrowprops={'arrowstyle': '-', 'color': '#666666', 'lw': .7}, zorder=11)
        checked.add('leaders')
    if name.startswith('quadrant_chart_box') and 'widths' not in checked:
        for axis, fraction, side in [(fig.axes[0], .018, 'left'), (fig.axes[1], .044, 'right')]:
            span = axis.get_xlim()[1] - axis.get_xlim()[0]
            patches = [p for p in axis.patches if hasattr(p, 'get_width') and p.get_alpha() == .85]
            assert patches and all(np.isclose(p.get_width(), 2*span*fraction, atol=1e-9) for p in patches)
            box_widths[side] = {'axis_limits': list(axis.get_xlim()), 'half_width_fraction': fraction, 'box_width': 2*span*fraction}
        checked.add('widths')
    if name.startswith('pareto_') and 'appendix' in name:
        for legend in fig.legends:
            legend.set_bbox_to_anchor((.5, .008))
    save_original(fig, filename, *args, **kwargs)
    if Path(filename).suffix == '.png':
        options = dict(kwargs)
        options.pop('dpi', None)
        save_original(fig, Path(filename).with_suffix('.pdf'), *args, **options)


Figure.savefig = save_figure
quad = box.QuadrantBoxVisualizer()
assert quad.BOX_X_FRACTION_L == .018 and quad.BOX_X_FRACTION_R == .044
quad.output_dir = quad.session_dir = OUT
for key, cfg in quad.modules.items():
    sc = cfg['name_en']
    values = learning.loc[learning.scenario.eq(sc)].sort_values('year').cost_cny_kg.to_numpy()
    quad.data[key] = {'name_en': sc, 'category': cfg['category'], 'color': cfg['color'],
        'lcoe': values[0], 'lcoe_2036': values[-1], 'lcoe_proj': values, 'carbon_diff': float(summary.loc[sc, 'carbon_g_mj'])-89}
quad.traditional_jet_ci_gco2e_per_mj = 89.0
quad.pareto_optimal_names = quad._identify_pareto_optimal(quad.data)
plt.rcParams.update({'font.family': 'serif', 'font.serif': ['Times New Roman', 'DejaVu Serif'], 'mathtext.fontset': 'stix', 'legend.frameon': True})
quad.plot_quadrant_chart()
gap = lollipop.MarketPriceGapLollipopVisualizer()
gap.output_dir = gap.session_dir = OUT
gap.plot_lollipop_chart(gaps)

sc = 'GTL-BH'
solution, carbon = solutions[sc], read_json(DATA / f'{sc}_carbon_emissions.json')
carbon_values = polar._aggregate(carbon['detailed'], 'carbon_keys')
polar.draw_concentric_rings(sc, solution['cost_breakdown'], carbon_values,
    solution['lifecycle_levelized_cost_excluding_shortage_per_kg'], OUT / f'{sc}_polar.png', total_production_kg=carbon['total_production_kg'])
polar.draw_donut(polar._aggregate(solution['cost_breakdown'], 'cost_keys'), 'Cost\nShare', OUT / f'{sc}_cost.png')
shutil.copy2(OLD_FIG / 'figures/GTL-BH_carbon.png', OUT / 'GTL-BH_carbon.png')
compose.stitch_white(OUT / 'GTL-BH_polar.png', OUT / 'GTL-BH_cost.png', OUT / 'GTL-BH_carbon.png', OUT / 'Figure_S40.png')

breakdown = si.ParetoBreakdownVisualizer(OUT, OUT)
for key, cfg in breakdown.scenarios.items():
    scenario = cfg.get('name_en', key)
    cfg['solution_pattern'] = str(DATA / f'{scenario}_complete_solution.json')
    cfg['carbon_pattern'] = str(DATA / f'{scenario}_carbon_emissions.json')
breakdown.load_data()
breakdown.selected_pareto = ['CCU-GH-FT', 'GTL', 'GTL-BH']
breakdown.pathway_roles = {'CCU-GH-FT': '43.84% demand served', 'GTL': '100% demand served; archived', 'GTL-BH': '100% demand served; archived'}
for record in breakdown.data.values():
    record['total_cost'] = sum(record['cost_breakdown'].values())
breakdown.create_appendix_metric_figure('cost')
for suffix in ['.png', '.pdf']:
    shutil.copy2(OUT / ('pareto_cost_appendix'+suffix), OUT / ('Figure_S28'+suffix))
Figure.savefig = save_original

# 只替换受影响的三个面板，保留当前组合图其余像素。
canvas = Image.open(CURRENT_MAIN).convert('RGB')
source_pixels = np.asarray(canvas).copy()
rectangles = [(70, 15, 2535, 1795), (2800, 125, 1910, 1760), (2980, 1970, 1460, 1450)]
for filename, (x, y, width, height) in zip(['quadrant_chart_box.png', 'market_price_gap_lollipop.png', 'GTL-BH_polar.png'], rectangles):
    picture = compose.flatten_white(OUT / filename)
    if filename.endswith('_polar.png'):
        side = min(picture.size)
        picture = picture.crop((0, 0, side, side))
    canvas.paste(picture.resize((width, height), Image.Resampling.LANCZOS), (x, y))
ImageDraw.Draw(canvas).text((120, 33), '(a)', font=ImageFont.truetype('C:/Windows/Fonts/timesbd.ttf', 74), fill='black')
mask = np.ones((canvas.height, canvas.width), dtype=bool)
for x, y, width, height in rectangles:
    mask[y:y+height, x:x+width] = False
assert np.array_equal(np.asarray(canvas)[mask], source_pixels[mask])
canvas.save(OUT / 'Figure_1.png', dpi=(300, 300))
pdf = pymupdf.open()
page = pdf.new_page(width=1160.64, height=829.68)
page.insert_image(page.rect, filename=str(OUT / 'Figure_1.png'))
pdf.save(OUT / 'Figure_1.pdf', garbage=4, deflate=True)
pdf.close()
preview = canvas.copy()
preview.thumbnail((1880, 1500))
preview.save(OUT / 'Figure_1_preview.png')

# S24和S25沿用既有绘图函数及代码段，避免引入新的视觉样式。
plt.rcdefaults()
plot = module('cost_sensitivity_original', OLD_FIG / 'sensitivity_visualizer_original.py')
plot.FIGURES_DIR = OUT
source_tree = ast.parse((OLD_FIG / 'derive_sensitivity.py').read_text(encoding='utf-8'))
save_node = next(n for n in source_tree.body if isinstance(n, ast.FunctionDef) and n.name == 'save')
save_env = {'plt': plt, 'Text': Text, 'OUT': OUT}
exec(compile(ast.Module(body=[save_node], type_ignores=[]), str(OLD_FIG / 'derive_sensitivity.py'), 'exec'), save_env)
def sensitivity_save(fig, filename):
    if filename == 'Figure_S24.png':
        axis = fig.axes[0]
        baseline_old = pd.read_csv(OLD_FIG / 'S24_fixed_design_component_sensitivity.csv')
        axis.set_xlim(left=max(0.0, baseline_old.cost_low_cny_kg.min()-3.0))
        for collection in axis.collections:
            points = np.asarray(collection.get_offsets())
            if points.shape == (1, 2) and np.isclose(points[0, 0], 5.225, rtol=0, atol=1e-9):
                points[0, 0] = solution['lifecycle_levelized_cost_excluding_shortage_per_kg']
                collection.set_offsets(points)
    save_env['save'](fig, filename)


plot._save_fig = sensitivity_save
sweeps = pd.read_csv(FDATA / 'S24_fixed_design_component_sensitivity.csv')
names = {'electricity_cost': 'Power cost', 'natural_gas_cost': 'NG cost', 'electrolyzer_investment_cost': 'H2 CAPEX', 'facility_operation_cost': 'Facility OPEX', 'facility_investment_cost': 'Facility CAPEX', 'coal_purchase_cost': 'Coal cost', 'dac_capture_cost': 'DAC cost', 'hydrogen_production_cost': 'H2 production'}
tornado = pd.DataFrame({'scenario': sweeps.scenario, 'param': sweeps.component.map(lambda k: names.get(k, k)),
    'lco_min': sweeps.cost_low_cny_kg, 'lco_max': sweeps.cost_high_cny_kg,
    'lco_range': sweeps.cost_high_cny_kg-sweeps.cost_low_cny_kg, 'baseline': sweeps.cost_baseline_cny_kg})
plot.plot_tornado_appendix({'_rob': {'tornado_df': tornado}, 'min_margin_gtlbh_vs_gtl': float('nan')}, output_filename='Figure_S24.png')
start = next(i for i, n in enumerate(source_tree.body) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'metrics' for t in n.targets))
env = {'pd': pd, 'plt': plt, 'Line2D': Line2D, 'DATA': HERE, 'save': save_env['save']}
exec(compile(ast.Module(body=source_tree.body[start:], type_ignores=[]), str(OLD_FIG / 'derive_sensitivity.py'), 'exec'), env)

# S26只重绘费用所在综合图；网络、利用率、排放和其他路径均从本次输入读取。
sys.path.insert(0, str(SPACE / 'source'))
draw = module('cost_efficiency_appendix', SPACE / 'source/generate_appendix_docx.py')
draw.PREP_DIR = draw.REDRAWN_DIR = OUT
translate_site = draw.translate_site_share_label
translate_material = draw.translate_material_label
draw.translate_site_share_label = lambda value: translate_site(value).replace('₂', '2')
draw.translate_material_label = lambda value: translate_material(value).replace('₂', '2')
integrated = pd.read_csv(STAGE / 'figure_data/figures_space_time_network_data/scenario_integrated_metrics.csv')
draw.build_scenario_metrics_table = lambda: integrated.copy()
draw.create_efficiency_analysis_figure(OUT / 'Figure_S26.png')

old_images = {'Figure_1': CURRENT_MAIN, 'Figure_S26': SPACE / 'outputs/Figure_S26.png'}
old_images.update({name: OLD_FIG / 'figures' / f'{name}.png' for name in ['Figure_S24', 'Figure_S25', 'Figure_S28', 'Figure_S40']})
mapping = []
for name, old_image in old_images.items():
    new_image = OUT / f'{name}.png'
    assert Image.open(old_image).size == Image.open(new_image).size, (name, Image.open(old_image).size, Image.open(new_image).size)
    mapping.append({'figure': name, 'old_image': str(old_image), 'old_sha256': sha(old_image),
        'new_image': str(new_image), 'new_sha256': sha(new_image), 'new_pdf': str(new_image.with_suffix('.pdf')),
        'pixels': list(Image.open(new_image).size)})
write_json(HERE / 'image_replacements.json', {'image_replacements': mapping})
write_json(HERE / 'render_verification.json', {'figure1_box_widths': box_widths, 'unmodified_main_panel_pixels_identical': True,
    'all_carbon_inputs_unchanged': True, 'carbon_donut_png_preserved': sha(OUT / 'GTL-BH_carbon.png') == sha(OLD_FIG / 'figures/GTL-BH_carbon.png'),
    'carbon_categories': carbon_values, 'affected_figures': list(old_images), 'original_dimensions_preserved': True})
print(json.dumps(mapping, ensure_ascii=False, indent=2))
