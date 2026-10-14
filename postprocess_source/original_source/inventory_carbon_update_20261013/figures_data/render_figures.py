import ast
import logging
import os
from pathlib import Path
import re
import shutil
import sys

HERE = Path(__file__).resolve().parent
os.environ['MPLCONFIGDIR'] = str(HERE/'mplconfig')
sys.path.insert(0,str(HERE.parents[1]/'inventory_cost_update_20261013/figures_data/dependencies'))

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

from update_carbon import WORK, PACKET, OLD_FIG, VIZ, STAGE, module, read_json, write_json, sha

OUT = HERE/'figures'
OUT.mkdir(exist_ok=True)
DATA = STAGE/'figure_data/normalized_pathway_records'
CURRENT_MAIN = PACKET/'Figures/Figure_1.png'
SPACE = WORK/'revision_20261007/figures_space_time'
sys.path.insert(0,str(VIZ))
logging.getLogger('fontTools').setLevel(logging.WARNING)
box = module('carbon_updated_box',VIZ/'quadrant_chart_box_visualization.py')
polar = module('carbon_updated_polar',VIZ/'pareto_three_breakdown_visualization.py')
si = module('carbon_updated_si',WORK/'corrected_runs_20261006/project/appendix_saf_workspace/scripts/pareto_three_breakdown_visualization.py')
compose = module('carbon_updated_composite',OLD_FIG/'compose_learning_panels.py')
box.FT_SCENARIOS = set(read_json(STAGE/'figure_data/learning_assumptions.json')['FT_learning_group'])
polar.SAF_LHV_MJ_PER_KG = 43.15
solutions = {p.name.removesuffix('_complete_solution.json'):read_json(p) for p in DATA.glob('*_complete_solution.json')}
carbons = {name:read_json(DATA/f'{name}_carbon_emissions.json') for name in solutions}
summary = pd.read_csv(HERE/'pathway_summary.csv').set_index('scenario')
learning = pd.read_csv(STAGE/'figure_data/figures_cost/learning_projections.csv')
input_images = {r['figure']:Path(r['path']) for r in read_json(HERE/'input_figure_manifest.json')}


def category_trajectories(costs,lcoe,scenario):
    total = sum(costs.values())
    result = {category:np.zeros(11) for category in polar.CATEGORIES}
    for key,value in costs.items():
        category = next((c for c,v in polar.CATEGORIES.items() if key in v['cost_keys']),None)
        assert category is not None or abs(value)<1e-5,key
        if category is None:
            continue
        factor = box.COST_MAP.get(key,'fixed')
        if factor=='synthesis':
            factor = 'synthesis_ft' if scenario in box.FT_SCENARIOS else 'synthesis_mtj'
        result[category] += value/total*lcoe*box.CF_ARRAY[factor]
    assert np.allclose(sum(result.values()),box.compute_lcoe_projection(solutions[scenario],scenario),atol=1e-12)
    return result


polar.compute_category_trajectories = category_trajectories
green_positions = {'DAC-GH-MTJ':(-37,58.8),'CCU-GH-MTJ':(12,45.0),'DAC-GH-FT':(12,39.0),'CCU-GH-FT':(-35,25.3)}
adjust_original = box.adjust_text
box.adjust_text = lambda texts,*a,**kw:adjust_original([t for t in texts if t.get_text() not in green_positions],*a,**kw)
save_original = Figure.savefig
checked = set()
widths = {}
text_map = {'Pareto-optimal region':'Descriptive cost–carbon envelope','Lower emission':'Below reference',
    'Higher emission':'Above reference','Carbon intensity difference vs traditional jet fuel (g CO₂eq/MJ)':r'Supply-chain intensity − 89 g CO$_2$e/MJ reference',
    'Baseline: 0.0 g CO2eq/MJ':r'Reference difference: 0.0 g CO$_2$e/MJ',
    'Representative frontier':'Selected pathway','Cost composition of representative Pareto pathways':'Cost composition of selected pathways',
    'Positive emissions composition of representative Pareto pathways':'Positive supply-chain emissions of selected pathways',
    'Deep decarbonization':'Renewable-coupled case','Transition pathway':'GTL comparison case','Lowest cost':'GTL-BH comparison case'}


def save_figure(fig,filename,*args,**kwargs):
    name = Path(filename).name
    for text in fig.findobj(Text):
        value = text.get_text()
        if 'LCOE' in value:
            text.set_text(value.replace('LCOE','LCO-SAF'))
        if value in text_map:
            text.set_text(text_map[value])
        elif value.endswith('g/MJ (−10%)') or value.endswith('g/MJ (−70%)'):
            text.set_text(value+' reference')
        if value=='Carbon (g CO2e/MJ)':
            text.set_text('Gross carbon\n(g CO2e/MJ)')
            text.set_fontsize(12)
        if 'Delta vs jet:' in value:
            text.set_text(value.replace('Delta vs jet:','Ledger − 89:'))
        if name.startswith('quadrant_chart_box'):
            if value in green_positions:
                text.set_position(green_positions[value])
                text.set_ha('left')
                text.set_va('center')
            elif value in {'2026','2028','2030','2032','2034','2036'}:
                text.set_x(-36)
            elif value.startswith('-62.3 g/MJ'):
                text.set_x(-75.5)
    if name.startswith('quadrant_chart_box') and 'leaders' not in checked:
        for data in quad.data.values():
            if data['name_en'] in green_positions:
                x,y = green_positions[data['name_en']]
                fig.axes[0].annotate('',xy=(data['carbon_diff'],data['lcoe']),xytext=(x-1,y),
                    arrowprops={'arrowstyle':'-','color':'#666666','lw':.7},zorder=11)
        checked.add('leaders')
    if name.startswith('quadrant_chart_box') and 'widths' not in checked:
        for axis,fraction,side in [(fig.axes[0],.018,'left'),(fig.axes[1],.044,'right')]:
            span = axis.get_xlim()[1]-axis.get_xlim()[0]
            patches = [p for p in axis.patches if hasattr(p,'get_width') and p.get_alpha()==.85]
            assert patches and all(np.isclose(p.get_width(),2*span*fraction,atol=1e-9) for p in patches)
            widths[side] = {'axis_limits':list(axis.get_xlim()),'half_width_fraction':fraction,'box_width':2*span*fraction}
        checked.add('widths')
    if name.startswith('pareto_') and 'appendix' in name:
        for legend in fig.legends:
            legend.set_bbox_to_anchor((.5,.008))
    save_original(fig,filename,*args,**kwargs)
    if Path(filename).suffix=='.png':
        options = dict(kwargs)
        options.pop('dpi',None)
        save_original(fig,Path(filename).with_suffix('.pdf'),*args,**options)


Figure.savefig = save_figure
quad = box.QuadrantBoxVisualizer()
assert quad.BOX_X_FRACTION_L==.018 and quad.BOX_X_FRACTION_R==.044
quad.output_dir = quad.session_dir = OUT
for key,cfg in quad.modules.items():
    name = cfg['name_en']
    costs = learning.loc[learning.scenario.eq(name)].sort_values('year').cost_cny_kg.to_numpy()
    quad.data[key] = {'name_en':name,'category':cfg['category'],'color':cfg['color'],
        'lcoe':costs[0],'lcoe_2036':costs[-1],'lcoe_proj':costs,'carbon_diff':float(summary.loc[name,'carbon_g_mj'])-89}
quad.traditional_jet_ci_gco2e_per_mj = 89.0
quad.pareto_optimal_names = quad._identify_pareto_optimal(quad.data)
plt.rcParams.update({'font.family':'serif','font.serif':['Times New Roman','DejaVu Serif'],'mathtext.fontset':'stix','legend.frameon':True})
quad.plot_quadrant_chart()

scenario_numbers = {name:36+i for i,name in enumerate(['CTL','CTL-BH','GTL-GH','GTL','GTL-BH',
    'CCU-GH-MTJ','CCU-GH-FT','CCU-BH-MTJ','CCU-BH-FT','DAC-GH-MTJ','DAC-GH-FT','DAC-BH-MTJ','DAC-BH-FT'])}
category_records = []
for name,number in scenario_numbers.items():
    solution,carbon = solutions[name],carbons[name]
    values = polar._aggregate(carbon['detailed'],'carbon_keys')
    assert np.isclose(sum(values.values()),sum(max(v,0) for v in carbon['detailed'].values()),atol=1e-3)
    for category,value in values.items():
        category_records.append({'scenario':name,'category':category,'emissions_kg':value,'g_co2e_per_mj':value/carbon['total_production_kg']*1000/43.15})
    polar.draw_concentric_rings(name,solution['cost_breakdown'],values,solution['lifecycle_levelized_cost_excluding_shortage_per_kg'],
        OUT/f'{name}_polar.png',total_production_kg=carbon['total_production_kg'])
    polar.draw_donut(polar._aggregate(solution['cost_breakdown'],'cost_keys'),'Cost\nShare',OUT/f'{name}_cost.png')
    polar.draw_donut(values,'Carbon\nShare',OUT/f'{name}_carbon.png')
    compose.stitch_white(OUT/f'{name}_polar.png',OUT/f'{name}_cost.png',OUT/f'{name}_carbon.png',OUT/f'Figure_S{number}.png')
    print('POLAR',name,flush=True)
pd.DataFrame(category_records).to_csv(HERE/'carbon_categories.csv',index=False)

breakdown = si.ParetoBreakdownVisualizer(OUT,OUT)
for key,cfg in breakdown.scenarios.items():
    name = cfg.get('name_en',key)
    cfg['solution_pattern'] = str(DATA/f'{name}_complete_solution.json')
    cfg['carbon_pattern'] = str(DATA/f'{name}_carbon_emissions.json')
breakdown.load_data()
breakdown.selected_pareto = ['CCU-GH-FT','GTL','GTL-BH']
breakdown.pathway_roles = {'CCU-GH-FT':'43.84% demand served','GTL':'100% demand served; archived','GTL-BH':'100% demand served; archived'}
for record in breakdown.data.values():
    record['total_cost'] = sum(record['cost_breakdown'].values())
breakdown.create_appendix_metric_figure('carbon')
for suffix in ['.png','.pdf']:
    shutil.copy2(OUT/('pareto_carbon_appendix'+suffix),OUT/('Figure_S29'+suffix))
Figure.savefig = save_original

# 组合图只更新对应面板，市场费用面板与共用图例保持输入像素。
canvas = Image.open(CURRENT_MAIN).convert('RGB')
original = np.asarray(canvas).copy()
rectangles = [(70,15,2535,1795),(35,1970,1460,1450),(1515,1970,1460,1450),(2980,1970,1460,1450)]
for filename,(x,y,w,h) in zip(['quadrant_chart_box.png','CCU-GH-FT_polar.png','GTL_polar.png','GTL-BH_polar.png'],rectangles):
    picture = compose.flatten_white(OUT/filename)
    if filename.endswith('_polar.png'):
        side = min(picture.size)
        picture = picture.crop((0,0,side,side))
    canvas.paste(picture.resize((w,h),Image.Resampling.LANCZOS),(x,y))
ImageDraw.Draw(canvas).text((120,33),'(a)',font=ImageFont.truetype('C:/Windows/Fonts/timesbd.ttf',74),fill='black')
mask = np.ones((canvas.height,canvas.width),dtype=bool)
for x,y,w,h in rectangles:
    mask[y:y+h,x:x+w] = False
assert np.array_equal(np.asarray(canvas)[mask],original[mask])
canvas.save(OUT/'Figure_1.png',dpi=(300,300))
pdf = pymupdf.open()
page = pdf.new_page(width=1160.64,height=829.68)
page.insert_image(page.rect,filename=str(OUT/'Figure_1.png'))
pdf.save(OUT/'Figure_1.pdf',garbage=4,deflate=True)
pdf.close()
preview = canvas.copy()
preview.thumbnail((1880,1500))
preview.save(OUT/'Figure_1_preview.png')
print('MAIN_READY',flush=True)

plt.rcdefaults()
source_tree = ast.parse((OLD_FIG/'derive_sensitivity.py').read_text(encoding='utf-8'))
save_node = next(n for n in source_tree.body if isinstance(n,ast.FunctionDef) and n.name=='save')
save_env = {'plt':plt,'Text':Text,'OUT':OUT}
exec(compile(ast.Module(body=[save_node],type_ignores=[]),str(OLD_FIG/'derive_sensitivity.py'),'exec'),save_env)
start = next(i for i,n in enumerate(source_tree.body) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='metrics' for t in n.targets))
env = {'pd':pd,'plt':plt,'Line2D':Line2D,'DATA':HERE,'save':save_env['save']}
exec(compile(ast.Module(body=source_tree.body[start:],type_ignores=[]),str(OLD_FIG/'derive_sensitivity.py'),'exec'),env)

sys.path.insert(0,str(SPACE/'source'))
draw = module('carbon_efficiency_appendix',SPACE/'source/generate_appendix_docx.py')
draw.PREP_DIR = draw.REDRAWN_DIR = OUT
translate_site,translate_material = draw.translate_site_share_label,draw.translate_material_label
draw.translate_site_share_label = lambda value:translate_site(value).replace('₂','2')
draw.translate_material_label = lambda value:translate_material(value).replace('₂','2')
integrated = pd.read_csv(STAGE/'figure_data/figures_space_time_network_data/scenario_integrated_metrics.csv')
draw.build_scenario_metrics_table = lambda:integrated.copy()
draw.create_efficiency_analysis_figure(OUT/'Figure_S26.png')

old_images = {'Figure_1':CURRENT_MAIN,**input_images}
mapping = []
for name,old_image in old_images.items():
    new_image = OUT/(name+'.png')
    assert new_image.exists(),name
    old_size,new_size = Image.open(old_image).size,Image.open(new_image).size
    assert old_size==new_size,(name,old_size,new_size)
    mapping.append({'figure':name,'old_image':str(old_image),'old_sha256':sha(old_image),
        'new_image':str(new_image),'new_sha256':sha(new_image),'new_pdf':str(new_image.with_suffix('.pdf')),
        'pixels':list(new_size)})
write_json(HERE/'image_replacements.json',{'image_replacements':mapping})
write_json(HERE/'render_verification.json',{'box_widths':widths,'figure1_unchanged_pixels_preserved':True,
    'colors':{k:v['color'] for k,v in polar.CATEGORIES.items()},'lhv_mj_kg':43.15,
    'pareto_names':quad.pareto_optimal_names,'all_figure_dimensions_preserved':True,
    'affected_figures':list(old_images)})
print('COMPLETE',len(mapping),flush=True)
