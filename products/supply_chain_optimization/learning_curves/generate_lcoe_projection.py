"""
13-Scenario SAF LCOE Projection (2026–2036)
Using technology learning curves (Wright's Law) applied to each cost component.

Cost categories:
  learnable_capex  → technology CAPEX (electrolyzer, CCS, SAF reactor, DAC)
  electricity      → operating electricity (follows renewable price decline, 4%/yr)
  fixed            → commodities, O&M, logistics (no learning)

Wright's Law:  C(X) = C0 · (X/X0)^(−b),   b = −log(1−LR)/log(2)
"""

import json, os, glob, sys
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
from matplotlib.ticker import FixedLocator, FuncFormatter

matplotlib.rcParams.update({
    'font.family': 'serif',
    'font.serif': ['Times New Roman', 'DejaVu Serif'],
    'mathtext.fontset': 'stix',
    'axes.spines.top': False,
    'axes.spines.right': False,
})

BASE = '/home/ljt/code_project/green_methanol_for_port_transportation-main/products/supply_chain_optimization'
OUT  = os.path.join(BASE, '../learning_curves/figures')
os.makedirs(OUT, exist_ok=True)

# ─── 1. File paths for the 13 latest results ─────────────────────────────────
RESULT_FILES = {
    'CTL':        f'{BASE}/coal_hydrogen_saf_optimization/results/complete_solution_20260201_205438.json',
    'CTL-BH':     f'{BASE}/coal_hydrogen_saf_optimization/results/byproduct_hydrogen/complete_solution_20260201_215450.json',
    'DAC-GH-MTJ': f'{BASE}/dac_hydrogen_saf_supply_chain_optimization/results/two_step/complete_solution_20260201_194439.json',
    'DAC-GH-FT':  f'{BASE}/dac_hydrogen_saf_supply_chain_optimization/results/one_step/complete_solution_20260201_194442.json',
    'CCU-GH-MTJ': f'{BASE}/green_hydrogen_supply_chain_optimization/results/two_step/complete_solution_20260201_215301.json',
    'CCU-GH-FT':  f'{BASE}/green_hydrogen_supply_chain_optimization/results/one_step/complete_solution_20260201_215531.json',
    'GTL-GH':     f'{BASE}/natural_gas_supply_chain_optimization/results/complete_solution_20260201_215938.json',
    'GTL':        f'{BASE}/natural_gas_supply_chain_optimization/results/ft_one_step/complete_solution_20260201_215354.json',
    'DAC-BH-MTJ': f'{BASE}/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/two_step/complete_solution_20260201_204929.json',
    'DAC-BH-FT':  f'{BASE}/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/one_step/complete_solution_20260201_205000.json',
    'GTL-BH':     f'{BASE}/natural_gas_supply_chain_optimization/results/byproduct_hydrogen/byproduct_hydrogen/two_step/complete_solution_20260201_220501.json',
    'CCU-BH-MTJ': f'{BASE}/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/two_step/complete_solution_20260201_221232.json',
    'CCU-BH-FT':  f'{BASE}/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/one_step/complete_solution_20260201_221438.json',
}

SAF_DENSITY = 0.775  # kg/L

# ─── 2. Load cost data ────────────────────────────────────────────────────────
# Aggregate / summary keys to exclude from cost fraction analysis
EXCLUDE_KEYS = {
    'total_investment_cost', 'total_operation_cost',
    'total_cost_excluding_shortage', 'shortage_cost',
    'final_inventory_cost',
}

def load_costs(path):
    with open(path) as f:
        d = json.load(f)
    cb_raw = d.get('cost_breakdown', {})
    # Remove aggregate summary keys and zero-value items
    cb = {k: v for k, v in cb_raw.items()
          if k not in EXCLUDE_KEYS and v != 0}
    lcoe_kg = d.get('lifecycle_levelized_cost_per_kg', 0)
    total   = d.get('objective_value_lifecycle_total', 0)
    return lcoe_kg, total, cb

raw = {}
for name, path in RESULT_FILES.items():
    lcoe_kg, total, cb = load_costs(path)
    raw[name] = {'lcoe_kg': lcoe_kg, 'total': total, 'cb': cb}
    print(f'{name:12s}  LCOE={lcoe_kg:.3f} CNY/kg = {lcoe_kg*SAF_DENSITY:.3f} CNY/L')

# ─── 3. Classify each cost item ──────────────────────────────────────────────
# Maps cost key → (category, technology_tag)
# categories: 'electrolyzer','synthesis','capture_dac','capture_coal','capture_gas','capture_ref','electricity','fixed'
COST_MAP = {
    'electrolyzer_investment_cost':  'electrolyzer',
    'facility_investment_cost':      'synthesis',     # SAF reactor CAPEX
    'h2_storage_investment':         'electrolyzer',  # small, lump with electrolyzer
    'dac_facility_investment':       'capture_dac',
    'dac_capture_cost':              'capture_dac',
    'co2_capture_cost':              'capture_ref',   # industrial CCU (refinery-like)
    'coal_gasification_cost':        'capture_coal',
    'electricity_cost':              'electricity',
    'dac_grid_electricity_cost':     'electricity',
    # fixed
    'facility_operation_cost':       'fixed',
    'production_cost':               'fixed',
    'transport_operation_cost':      'fixed',
    'storage_equipment_cost':        'fixed',
    'storage_operation_cost':        'fixed',
    'catalyst_cost':                 'fixed',
    'hydrogen_pipeline_operation':   'fixed',
    'hydrogen_transport_operation':  'fixed',
    'coal_purchase_cost':            'fixed',
    'natural_gas_cost':              'fixed',
    'ng_transport_investment':       'fixed',
    'methanol_production_cost':      'fixed',
    'methanol_storage_investment':   'fixed',
    'methanol_storage_equipment_cost':'fixed',
    'methanol_storage_operation_cost':'fixed',
    'co2_pipeline_transport_cost':   'fixed',
    'co2_truck_transport_cost':      'fixed',
    'co2_storage_investment':        'fixed',
    'co2_storage_operation':         'fixed',
}

# For GTL / CTL scenarios, synthesis is FT; for *-MTJ, synthesis is MTJ
# We'll handle this per-scenario when applying LR
FT_SCENARIOS  = {'CTL','DAC-GH-FT','CCU-GH-FT','GTL','DAC-BH-FT','CCU-BH-FT','GTL-BH','GTL-GH'}
MTJ_SCENARIOS = {'CTL-BH','DAC-GH-MTJ','CCU-GH-MTJ','DAC-BH-MTJ','CCU-BH-MTJ'}

# ─── 4. Compute cost fractions per scenario ───────────────────────────────────
fracs = {}
for name, data in raw.items():
    total = data['total']
    cb    = data['cb']
    cats  = {k: 0.0 for k in ['electrolyzer','synthesis','capture_dac','capture_coal','capture_gas','capture_ref','electricity','fixed']}
    for key, val in cb.items():
        cat = COST_MAP.get(key, 'fixed')
        cats[cat] += val
    # normalise
    total_mapped = sum(cats.values())
    f = {k: v/total for k, v in cats.items()}
    fracs[name] = f
    print(f"\n{name}: total={total/1e9:.1f}B  lcoe={data['lcoe_kg']:.2f} CNY/kg")
    for k,v in f.items():
        if v>0.005: print(f"  {k:20s}: {v:.3f}")

# ─── 5. Learning curve parameters ────────────────────────────────────────────
LR = {
    'electrolyzer':  0.21,
    'synthesis_ft':  0.18,
    'synthesis_mtj': 0.15,
    'capture_dac':   0.12,
    'capture_coal':  0.10,
    'capture_gas':   0.05,
    'capture_ref':   0.06,
    'electricity':   0.04,   # annual price decline (not Wright's Law, just compound)
}

def b(lr): return -np.log(1 - lr) / np.log(2)

# ─── 6. Global capacity trajectories 2026→2036 ───────────────────────────────
# (consistent with IEA NZE scenario, interpolated)
years = np.arange(2026, 2037)  # 2026–2036

# PEM electrolyzer (GW): 60 in 2025 → ramp to 850 by 2035
X_pem  = np.interp(years, [2025,2027,2030,2033,2036], [60, 100, 330, 600, 950])
X0_pem = 60.0

# DAC (Mt CO2/yr): 0.1 in 2025 → 10 by 2035
X_dac  = np.interp(years, [2025,2028,2031,2034,2036], [0.1, 1.0, 4.0, 8.0, 12.0])
X0_dac = 0.1

# Coal CCS (Mt CO2/yr): 10 in 2025 → 400 by 2035
X_coal = np.interp(years, [2025,2028,2031,2034,2036], [10, 60, 180, 350, 500])
X0_coal = 10.0

# Gas/Refinery CCS (Mt CO2/yr): 20 → 500
X_gas  = np.interp(years, [2025,2028,2031,2034,2036], [20, 90, 250, 430, 600])
X0_gas = 20.0

# FT / MTJ synthesis: proxy = electrolyzer GW (same trajectory)
X_synth  = X_pem
X0_synth = X0_pem

# Cost reduction factor relative to 2026 baseline
def cf(X_arr, X0, lr):
    """Wright's Law cost reduction factor array, normalised to CF=1 at first year."""
    X0_base = X_arr[0]         # capacity at 2026 (baseline year)
    return (X_arr / X0_base) ** (-b(lr))

CF = {
    'electrolyzer':  cf(X_pem,   X0_pem,   LR['electrolyzer']),
    'synthesis_ft':  cf(X_synth, X0_synth, LR['synthesis_ft']),
    'synthesis_mtj': cf(X_synth, X0_synth, LR['synthesis_mtj']),
    'capture_dac':   cf(X_dac,   X0_dac,   LR['capture_dac']),
    'capture_coal':  cf(X_coal,  X0_coal,  LR['capture_coal']),
    'capture_ref':   cf(X_gas,   X0_gas,   LR['capture_ref']),
    'electricity':   (1 - LR['electricity']) ** np.arange(len(years)),
    'fixed':         np.ones(len(years)),
}

# ─── 7. Project LCOE for each scenario ───────────────────────────────────────
projections = {}   # name → array of CNY/L over years

for name in raw:
    lcoe_kg_base = raw[name]['lcoe_kg']
    lcoe_l_base  = lcoe_kg_base * SAF_DENSITY
    f = fracs[name]

    syn_key = 'synthesis_ft' if name in FT_SCENARIOS else 'synthesis_mtj'

    # weighted cost reduction year by year
    proj = (
        f['electrolyzer']   * CF['electrolyzer']   +
        f['synthesis']      * CF[syn_key]           +
        f['capture_dac']    * CF['capture_dac']     +
        f['capture_coal']   * CF['capture_coal']    +
        f['capture_ref']    * CF['capture_ref']     +
        f['electricity']    * CF['electricity']     +
        f['fixed']          * CF['fixed']
    ) * lcoe_l_base

    projections[name] = proj

# ─── 8. Figure design ────────────────────────────────────────────────────────
SCENARIO_META = {
    # name: (short_label, CO2_family, H2_type, synthesis)
    'GTL-BH':     ('GTL-BH',     'ng',   'byproduct', 'mtj'),
    'GTL':        ('GTL',        'ng',   'none',      'ft'),
    'GTL-GH':     ('GTL-GH',     'ng',   'green',     'mtj'),
    'CTL-BH':     ('CTL-BH',     'coal', 'byproduct', 'mtj'),
    'CTL':        ('CTL',        'coal', 'green',     'mtj'),
    'CCU-BH-FT':  ('CCU-BH-FT', 'ccu',  'byproduct', 'ft'),
    'CCU-BH-MTJ': ('CCU-BH-MTJ','ccu',  'byproduct', 'mtj'),
    'CCU-GH-FT':  ('CCU-GH-FT', 'ccu',  'green',     'ft'),
    'CCU-GH-MTJ': ('CCU-GH-MTJ','ccu',  'green',     'mtj'),
    'DAC-BH-FT':  ('DAC-BH-FT', 'dac',  'byproduct', 'ft'),
    'DAC-BH-MTJ': ('DAC-BH-MTJ','dac',  'byproduct', 'mtj'),
    'DAC-GH-FT':  ('DAC-GH-FT', 'dac',  'green',     'ft'),
    'DAC-GH-MTJ': ('DAC-GH-MTJ','dac',  'green',     'mtj'),
}

FAMILY_COLORS = {
    'ng':   {'dark': '#BF360C', 'mid': '#FF7043'},   # deep orange
    'coal': {'dark': '#3E2723', 'mid': '#8D6E63'},   # brown
    'ccu':  {'dark': '#1B5E20', 'mid': '#43A047'},   # green
    'dac':  {'dark': '#0D47A1', 'mid': '#1E88E5'},   # blue
}

def get_style(meta):
    _, family, h2, synth = meta
    c = FAMILY_COLORS[family]
    color = c['dark'] if h2 in ('green','none') else c['mid']
    ls    = '-'  if synth == 'ft'  else '--'
    ms    = 'o'  if h2 in ('green','none') else 's'
    mfc   = color if h2 in ('green','none') else 'white'
    return color, ls, ms, mfc

# Sort scenarios by 2026 LCOE ascending
sorted_scenarios = sorted(projections.keys(), key=lambda n: projections[n][0])

fig, ax = plt.subplots(figsize=(12, 7.5))

# ── Fossil jet fuel band ──────────────────────────────────────────────────────
jf_lo = np.array([4.5]*len(years))
jf_hi = np.array([6.5]*len(years))
ax.fill_between(years, jf_lo, jf_hi, color='#CFD8DC', alpha=0.55, zorder=0)
ax.plot(years, 0.5*(jf_lo+jf_hi), color='#78909C', lw=1.2, ls=':', zorder=1)
ax.text(2026.2, 5.5, 'Fossil jet fuel  (4.5 – 6.5 CNY/L)',
        fontsize=7.5, color='#546E7A', va='center', style='italic')

# ── Plot 13 scenario curves ───────────────────────────────────────────────────
for name in sorted_scenarios:
    proj = projections[name]
    meta = SCENARIO_META[name]
    color, ls, ms, mfc = get_style(meta)
    ax.plot(years, proj, color=color, ls=ls, lw=1.8, zorder=3)
    ax.plot(years[::2], proj[::2], marker=ms, ms=5, color=color,
            mfc=mfc, mew=1.3, ls='none', zorder=4)

# ── End-of-line labels (staggered to avoid overlap) ──────────────────────────
# Compute end values and sort; apply minimum vertical gap of 0.7 CNY/L
end_vals = [(projections[n][-1], n) for n in sorted_scenarios]
end_vals.sort()

MIN_GAP = 0.70
# upward pass: push labels apart
positions = [v for v, _ in end_vals]
for i in range(1, len(positions)):
    if positions[i] - positions[i-1] < MIN_GAP:
        positions[i] = positions[i-1] + MIN_GAP

for pos, (_, name) in zip(positions, end_vals):
    meta = SCENARIO_META[name]
    color, ls, ms, mfc = get_style(meta)
    ax.annotate(
        name,
        xy=(years[-1], projections[name][-1]),
        xytext=(years[-1] + 0.2, pos),
        fontsize=7,
        color=color,
        va='center',
        arrowprops=dict(arrowstyle='-', color=color, lw=0.5,
                        connectionstyle='arc3,rad=0'),
    )

# ── Axes ──────────────────────────────────────────────────────────────────────
ax.set_yscale('log')
ax.set_ylim(2.5, 55)
ax.set_xlim(2026, 2038.5)
ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f'{y:.0f}'))
ax.yaxis.set_minor_formatter(FuncFormatter(lambda y, _: ''))
ax.set_yticks([3, 4, 5, 6, 8, 10, 15, 20, 25, 30, 40, 50])
ax.set_xticks(years)
ax.set_xticklabels([str(y) for y in years], fontsize=9, rotation=45)
ax.tick_params(axis='y', labelsize=9, which='both')
ax.set_xlabel('Year', fontsize=12)
ax.set_ylabel('SAF Production Cost  (CNY / L,  log scale)', fontsize=11)
ax.set_title(
    'Projected SAF Production Cost Trajectories under Technology Learning Curves\n'
    '13 Supply-Chain Pathways, 2026–2036  (Baseline Learning Scenario)',
    fontsize=11.5, pad=10
)

# Secondary y-axis: USD/L
ax2 = ax.twinx()
ax2.spines['top'].set_visible(False)
ax2.set_yscale('log')
ax2.set_ylim(2.5/7.1, 55/7.1)
ax2.set_yticks([t/7.1 for t in [3,5,8,15,25,40]])
ax2.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f'{y:.1f}'))
ax2.set_ylabel('SAF Production Cost  (USD / L)', fontsize=10, color='#555')
ax2.tick_params(axis='y', labelsize=8, colors='#555')

# ── Legend ────────────────────────────────────────────────────────────────────
lh = []
for fam, lbl in [('ng','Natural gas (GTL)'), ('coal','Coal (CTL)'),
                  ('ccu','Industrial CCU'),   ('dac','Direct air capture')]:
    lh.append(mpatches.Patch(facecolor=FAMILY_COLORS[fam]['dark'], label=lbl))
lh.append(Line2D([0],[0], color='#333', ls='-',  lw=1.5, label='FT one-step'))
lh.append(Line2D([0],[0], color='#333', ls='--', lw=1.5, label='MTJ two-step'))
lh.append(Line2D([0],[0], marker='o', color='#555', ms=5.5, mfc='#555',
                  ls='none', label='Green H2 / NG direct'))
lh.append(Line2D([0],[0], marker='s', color='#555', ms=5.5, mfc='white',
                  mew=1.2, ls='none', label='Byproduct H2'))
lh.append(mpatches.Patch(facecolor='#CFD8DC', alpha=0.7, label='Fossil jet fuel range'))
ax.legend(handles=lh, loc='upper right', fontsize=7.5,
          framealpha=0.92, edgecolor='#BDBDBD', ncol=2, borderpad=0.7)

ax.grid(axis='y', color='#EEEEEE', lw=0.7, which='major', zorder=0)
ax.grid(axis='x', color='#F5F5F5', lw=0.5, zorder=0)

plt.tight_layout(rect=[0, 0, 0.88, 1])

out_path = os.path.join(OUT, 'Fig_S_LCOE_Projection_13Scenarios.png')
fig.savefig(out_path, dpi=300, bbox_inches='tight')
print(f'\nSaved → {out_path}')
plt.close()

# ── Print summary table ───────────────────────────────────────────────────────
print('\n=== LCOE Projections Summary (CNY/L) ===')
print(f'{"Scenario":15s}  {"2026":>7s}  {"2030":>7s}  {"2036":>7s}  {"Δ2036/2026":>11s}')
print('-' * 55)
for name in sorted_scenarios:
    p = projections[name]
    idx = {y: i for i, y in enumerate(years)}
    print(f'{name:15s}  {p[0]:7.2f}  {p[idx[2030]]:7.2f}  {p[-1]:7.2f}  {(p[-1]/p[0]-1)*100:+10.1f}%')
