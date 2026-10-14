import importlib.util
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.text import Text
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd
import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = HERE / 'adapted_data'
OUT = HERE / 'figures'
EVIDENCE = ROOT / 'corrected_runs_20261006/result_delivery/核算依据'
manifest = json.loads((DATA/'manifest.json').read_text(encoding='utf-8'))
solutions = {s:json.loads((DATA/f'{s}_complete_solution.json').read_text(encoding='utf-8')) for s in manifest}
spec = importlib.util.spec_from_file_location('sensitivity_original', HERE/'sensitivity_visualizer_original.py')
plot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plot)
plot.FIGURES_DIR = OUT


def save(fig, filename):
    for text in fig.findobj(Text):
        value = text.get_text()
        if value.startswith('LCO-SynAF Heat Map:'):
            text.set_text('CCU-GH-MTJ: fixed-design cost sensitivity')
        elif value.startswith('IEA 2030'):
            text.set_text('Illustrative\n100 CNY/t')
            text.set_position((110,12.5))
        elif value == 'Scenario LCO sensitivity range (dominant-parameter sweep)':
            text.set_text('Fixed-design sensitivity: largest component cost ±20%')
        elif value == 'Baseline LCO (main result)':
            text.set_text('Baseline unit cost')
        elif value.startswith('Electrolyzer CAPEX (k'):
            text.set_text(r'Electrolyzer CAPEX (CNY per kg H$_2$/h)')
        elif value == 'Baseline\n4,500 ¥/t':
            text.set_position((4440,15))
            text.set_horizontalalignment('right')
        if 'LCO-SynAF' in text.get_text():
            text.set_text(text.get_text().replace('LCO-SynAF','LCO-SAF'))
    if filename == 'Figure_S23.png':
        legend = fig.axes[0].get_legend()
        legend.set_loc('upper left')
        legend.set_bbox_to_anchor((.02,.83))
    if filename == 'Figure_S24.png':
        legend = fig.axes[0].get_legend()
        legend.set_loc('upper right')
        legend.set_bbox_to_anchor((.98,.98))
    fig.savefig(OUT/filename,dpi=300,bbox_inches='tight')
    fig.savefig((OUT/filename).with_suffix('.pdf'),bbox_inches='tight')
    plt.close(fig)


plot._save_fig = save
scenario = 'CCU-GH-MTJ'
sol = solutions[scenario]
config = yaml.safe_load((EVIDENCE/scenario/'baseline/config.yaml').read_text(encoding='utf-8'))
params = json.loads((EVIDENCE/scenario/'baseline/model_parameters.json').read_text(encoding='utf-8'))
production = pd.read_csv(EVIDENCE/scenario/'baseline/saf_production.csv')
hydrogen = pd.read_csv(EVIDENCE/scenario/'baseline/h2_production.csv')
production['location_type'] = production.location.map(lambda x:params['locations'][x]['type'])
grid_kg = production.loc[~production.location_type.isin(['solar_plant','wind_farm']),'value'].sum()
total_kg = production.value.sum()
energy = config['technologies']['green_h2_co2_to_saf']['energy_consumption_kwh_per_kg_saf']
base_grid = config['cost_parameters']['renewable_energy']['grid_electricity_price_yuan_per_kwh']
base_capex = config['equipment_raw_costs']['electrolyzer']['capex_raw']
base_cost = sol['lifecycle_levelized_cost_excluding_shortage_per_kg']
total_cost = sum(sol['cost_breakdown'].values())
discounted_production = total_cost/base_cost
capex_slope = sol['cost_breakdown']['electrolyzer_investment_cost']/discounted_production/base_capex
grid_slope = grid_kg*energy/total_kg
wind_price = config['cost_parameters']['renewable_energy']['wind_power_price_yuan_per_kwh']
expected_electricity = (hydrogen.value.sum()*params['costs']['electrolysis_power_consumption']*params['costs']['renewable_electricity_cost_yuan_per_mwh']/1000 + (total_kg-grid_kg)*energy*wind_price + grid_kg*energy*base_grid) / total_kg
reported_electricity = sol['cost_breakdown']['electricity_cost']/discounted_production
assert np.isclose(expected_electricity,reported_electricity,rtol=1e-8,atol=1e-7), (expected_electricity,reported_electricity)
rows = []
for price in [.25,.35,.50,.60,.80]:
    for capex in [200000,360000,500000,700000,1000000]:
        cost = base_cost+grid_slope*(price-base_grid)+capex_slope*(capex-base_capex)
        rows.append({'scenario':scenario,'grid_price_cny_kwh':price,'electrolyzer_capex_cny_kg_h':capex,'cost_cny_kg':cost,'fulfillment_ratio':sol['demand_fulfillment_ratio'],'scope':'Fixed production assets, dispatch and output; exact repricing of retained design'})
frame = pd.DataFrame(rows)
frame.to_csv(HERE/'S22_fixed_design_grid.csv',index=False)
pivot = frame.pivot(index='grid_price_cny_kwh',columns='electrolyzer_capex_cny_kg_h',values='cost_cny_kg')
plot.plot_electricity_capex_heatmap_appendix({'_ec':{'pivots':{scenario:pivot}}},output_filename='Figure_S22.png')

dac_rows, dac = [], {}
for sc in ['DAC-GH-FT','DAC-GH-MTJ','DAC-BH-FT','DAC-BH-MTJ']:
    sol = solutions[sc]
    baseline = sol['lifecycle_levelized_cost_excluding_shortage_per_kg']
    capture_contribution = sol['cost_breakdown']['dac_capture_cost']/sum(sol['cost_breakdown'].values())*baseline
    values, costs = [], []
    for unit_cost in [300,500,700,1000,1500,2500,3500,4500]:
        cost = baseline+capture_contribution*(unit_cost/4500-1)
        values.append(unit_cost)
        costs.append(cost)
        dac_rows.append({'scenario':sc,'dac_cost_cny_t_co2':unit_cost,'cost_cny_kg':cost,'fulfillment_ratio':sol.get('demand_fulfillment_ratio',1),'scope':'Fixed production assets, dispatch and output; DAC capture operating cost only'})
    dac[sc] = {'dac_values':values,'lco_values':costs}
pd.DataFrame(dac_rows).to_csv(HERE/'S23_fixed_design_dac.csv',index=False)
plot.plot_dac_breakeven_appendix({'_dac':{'per_scenario':dac},'dac_ghft_lco_min':min(dac['DAC-GH-FT']['lco_values'])},output_filename='Figure_S23.png')

names = {'electricity_cost':'Power cost','natural_gas_cost':'NG cost','electrolyzer_investment_cost':'H2 CAPEX','facility_operation_cost':'Facility OPEX','facility_investment_cost':'Facility CAPEX','coal_purchase_cost':'Coal cost','dac_capture_cost':'DAC cost','hydrogen_production_cost':'H2 production'}
sweeps, tornado = [], []
for sc, sol in solutions.items():
    baseline = sol['lifecycle_levelized_cost_excluding_shortage_per_kg']
    total = sum(sol['cost_breakdown'].values())
    for key, value in sol['cost_breakdown'].items():
        if value <= 1e-6:
            continue
        contribution = value/total*baseline
        low, high = baseline-.2*contribution,baseline+.2*contribution
        sweeps.append({'scenario':sc,'component':key,'multiplier_low':.8,'multiplier_high':1.2,'cost_low_cny_kg':low,'cost_baseline_cny_kg':baseline,'cost_high_cny_kg':high,'scope':'One component coefficient at a time; fixed design, dispatch, production and service fraction'})
        tornado.append({'scenario':sc,'param':names.get(key,key),'lco_min':low,'lco_max':high,'lco_range':high-low,'baseline':baseline})
pd.DataFrame(sweeps).to_csv(HERE/'S24_fixed_design_component_sensitivity.csv',index=False)
tdf = pd.DataFrame(tornado)
plot.plot_tornado_appendix({'_rob':{'tornado_df':tdf},'min_margin_gtlbh_vs_gtl':float('nan')},output_filename='Figure_S24.png')
report = {'S22':{'grid_electricity_slope_cny_kg_per_cny_kwh':grid_slope,'electrolyzer_capex_slope_cny_kg_per_100000':capex_slope*100000,'baseline_cny_kg':base_cost,'min_cny_kg':float(frame.cost_cny_kg.min()),'max_cny_kg':float(frame.cost_cny_kg.max()),'grid_synthesis_share':grid_kg/total_kg,'reconstructed_electricity_cny_kg':expected_electricity,'reported_electricity_cny_kg':reported_electricity,'baseline_grid_cny_kwh':base_grid,'baseline_capex_cny_kg_h':base_capex},'S23':{sc:{'at_300':d['lco_values'][0],'at_4500':d['lco_values'][-1]} for sc,d in dac.items()},'S24':tdf.loc[tdf.groupby('scenario').lco_range.idxmax()].to_dict('records'),'scope':'All sensitivities retain baseline facilities, flows, capacities and output. No scenario is reoptimized; conditional costs do not establish a common full-service ranking.'}
(HERE/'sensitivity_verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))

# S25沿用原来的双面板、路径形状及类别色。
metrics = pd.read_csv(DATA/'pathway_summary.csv')
metrics['category'] = metrics.scenario.map(lambda s:'Grey' if s.startswith('CTL') else ('Green' if ('-GH-' in s) else 'Blue'))
metrics['route'] = metrics.scenario.map(lambda s:'FT' if s in {'CTL','CTL-BH','GTL','DAC-GH-FT','CCU-GH-FT','DAC-BH-FT','CCU-BH-FT'} else 'MTJ')
metrics['delta'] = metrics.carbon_g_mj-89
colors = {'Grey':'#8491B4','Blue':'#3C5488','Green':'#00A087'}
plt.rcParams.update({'font.family':'Arial','font.size':8,'axes.labelsize':8.5,'xtick.labelsize':7,'ytick.labelsize':7,'legend.fontsize':6.8,'axes.linewidth':.7,'pdf.fonttype':42})
fig = plt.figure(figsize=(7.2,5.0),dpi=300)
gs = fig.add_gridspec(1,2,left=.08,right=.985,top=.88,bottom=.18,wspace=.30)
left = fig.add_subplot(gs[0,0])
for route,marker in {'FT':'o','MTJ':'s'}.items():
    subset = metrics[metrics.route.eq(route)]
    left.scatter(subset.delta,subset.cost_cny_kg,label=route,marker=marker,s=42,c=subset.category.map(colors),edgecolors='white',linewidth=.7,zorder=3)
ordered = metrics.sort_values(['delta','cost_cny_kg'])
frontier,best = [],float('inf')
for row in ordered.itertuples():
    if row.cost_cny_kg < best:
        frontier.append(row.scenario)
        best = row.cost_cny_kg
f = metrics[metrics.scenario.isin(frontier)].sort_values('delta')
left.plot(f.delta,f.cost_cny_kg,color='#333333',linewidth=1,linestyle='--',zorder=2)
left.axvline(0,color='#94A3B8',linestyle='--',linewidth=.8)
for row in f.itertuples():
    left.annotate(row.scenario,(row.delta,row.cost_cny_kg),xytext=(5,5),textcoords='offset points',fontsize=6.4,color='#334155')
left.set_xlabel('Supply-chain intensity − 89 (gCO2e/MJ)')
left.set_ylabel('LCO-SAF (CNY/kg)')
handles = [Line2D([0],[0],marker='o',linestyle='None',markerfacecolor=color,markeredgecolor='white',markersize=6,label=cat) for cat,color in colors.items()]
handles += [Line2D([0],[0],marker=mark,linestyle='None',markerfacecolor='#475569',markeredgecolor='white',markersize=6,label=route) for route,mark in {'FT':'o','MTJ':'s'}.items()]
left.legend(handles=handles,ncol=3,loc='upper center',bbox_to_anchor=(.5,1.23),frameon=False)
right = fig.add_subplot(gs[0,1])
ordered = metrics.sort_values('cost_cny_kg')
right.barh(ordered.scenario,ordered.cost_cny_kg,color=ordered.category.map(colors),height=.68)
right.invert_yaxis()
right.set_xlabel('LCO-SAF (CNY/kg)')
right.set_xlim(0,metrics.cost_cny_kg.max()*1.13)
for y,row in enumerate(ordered.itertuples()):
    right.text(row.cost_cny_kg+.4,y,f'{row.delta:+.0f}',va='center',fontsize=6.5,color='#334155')
for i,ax in enumerate([left,right]):
    ax.spines[['top','right']].set_visible(False)
    ax.grid(axis='x',color='#CBD5E1',linewidth=.5,alpha=.4)
    ax.set_axisbelow(True)
    ax.text(-.12,1.03,f'({chr(97+i)})',transform=ax.transAxes,fontweight='bold',fontsize=9)
save(fig,'Figure_S25.png')
