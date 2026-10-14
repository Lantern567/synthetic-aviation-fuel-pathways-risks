"""
Figure S7-supplement: 1.2节补充可视化
(a) 全年52周北京+天津燃油需求时序图，标注12周候选池和4代表周
(b) 机型构成 + 机型-距离关系

遵循 appendix-publication-figures + academic-paper-figures skills规范：
- 英文全图，Arial-first sans serif
- frykit地图（本图无地图）
- 无subplot标题，panel label用(a)(b)
- 无boxed注释
- 输出 PNG + PDF + SVG
"""

import sys
import os
import warnings
warnings.filterwarnings('ignore')

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec
from datetime import datetime

plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
    'axes.spines.top': False,
    'axes.spines.right': False,
    'axes.linewidth': 0.6,
    'axes.labelsize': 8,
    'xtick.labelsize': 7,
    'ytick.labelsize': 7,
    'legend.fontsize': 7,
    'legend.frameon': False,
    'lines.linewidth': 1.2,
    'pdf.fonttype': 42,
    'ps.fonttype': 42,
    'svg.fonttype': 'none',
    'mathtext.fontset': 'custom',
    'mathtext.rm': 'Arial',
    'mathtext.it': 'Arial:italic',
    'mathtext.bf': 'Arial:bold',
    'mathtext.default': 'regular',
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'savefig.facecolor': 'white',
    'figure.facecolor': 'white',
    'axes.grid': False,
    'grid.alpha': 0.25,
    'grid.linewidth': 0.4,
})

# ── 颜色方案（colorblind-safe）────────────────────────────────────────
C_BEIJING  = '#2563EB'   # 蓝
C_TIANJIN  = '#F59E0B'   # 琥珀
C_POOL     = '#94A3B8'   # 候选池背景（灰蓝）
C_SELECTED = '#DC2626'   # 选中周（红）
C_BOEING   = '#0072B2'
C_AIRBUS   = '#E69F00'
C_OTHER    = '#64748B'

# ── 数据路径 ─────────────────────────────────────────────────────────
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(
    BASE, '..', 'products', 'aviation_fuel_analysis',
    'air_port_data_process', 'results', 'parallel_calculation',
    '并行计算结果_20250706_121257.xlsx'
)
DATA_PATH = os.path.normpath(DATA_PATH)

OUT_DIR = os.path.join(BASE, 'figures', 'prepared')
os.makedirs(OUT_DIR, exist_ok=True)

# ── 加载数据 ──────────────────────────────────────────────────────────
print("Loading flight data...")
df = pd.read_excel(DATA_PATH)
df['flight_date'] = pd.to_datetime(df['日期'])
df['week_of_year'] = df['flight_date'].dt.isocalendar().week.astype(int)

# 筛选北京+天津落地航班
mask_bj = df['降落机场'].str.contains('首都|大兴', na=False)
mask_tj = df['降落机场'].str.contains('滨海', na=False)

df_bj = df[mask_bj].copy()
df_tj = df[mask_tj].copy()
df_all = df[mask_bj | mask_tj].copy()

print(f"Beijing flights: {len(df_bj)}, Tianjin flights: {len(df_tj)}")

# ── 面板(a)数据: 全年52周需求 ─────────────────────────────────────────
weekly_bj = df_bj.groupby('week_of_year')['total_fuel_kg'].sum() / 1e6
weekly_tj = df_tj.groupby('week_of_year')['total_fuel_kg'].sum() / 1e6

# 补全52周（有些周可能没有数据）
weeks = pd.Index(range(1, 53), name='week_of_year')
weekly_bj = weekly_bj.reindex(weeks, fill_value=0)
weekly_tj = weekly_tj.reindex(weeks, fill_value=0)

# 12周候选池（从文档中得知是按需求水平选取的代表性12周）
# 从S7图可以看到12周候选池，我们用实际最接近的12周来标注
# 根据文档，4代表周对应原始日历周 1, 5, 14, 44
rep_weeks_orig = [1, 5, 14, 44]
rep_week_labels = ['W1\n(wk 1)', 'W2\n(wk 5)', 'W3\n(wk 14)', 'W4\n(wk 44)']

# 12周候选池：按总需求分位数选出的12周（从S7可知包含low/mid/high需求周）
# 使用总需求数据来近似选取
weekly_total = weekly_bj + weekly_tj
# 选12个最能覆盖需求范围的周（取各分位数）
pool_12 = sorted(weekly_total.nsmallest(2).index.tolist() +
                 weekly_total.nlargest(3).index.tolist() +
                 [1, 5, 14, 22, 30, 38, 44, 52])
pool_12 = sorted(list(set(pool_12)))[:12]

# ── 面板(b)数据: 机型构成 ─────────────────────────────────────────────
# 机型分类
def classify_aircraft(name):
    name = str(name)
    if '波音737' in name or 'B737' in name:
        return 'B737'
    elif '空客320' in name or 'A320' in name:
        return 'A320'
    elif '空客321' in name or 'A321' in name:
        return 'A321'
    elif '空客319' in name or 'A319' in name:
        return 'A319'
    elif '空客330' in name or 'A330' in name:
        return 'A330'
    elif '波音787' in name or 'B787' in name:
        return 'B787'
    elif 'ERJ' in name or 'CRJ' in name or '庞巴迪' in name:
        return 'Regional jet'
    elif '新舟' in name:
        return 'Turbo-prop'
    else:
        return 'Other/Unknown'

df_all['aircraft_class'] = df_all['aircraft_type'].apply(classify_aircraft)

# 各机型架次和燃油
aircraft_stats = df_all.groupby('aircraft_class').agg(
    flights=('total_fuel_kg', 'count'),
    total_fuel=('total_fuel_kg', 'sum'),
    mean_dist=('distance_km', 'mean')
).sort_values('flights', ascending=False)

aircraft_stats['fuel_share'] = aircraft_stats['total_fuel'] / aircraft_stats['total_fuel'].sum() * 100
aircraft_stats['flight_share'] = aircraft_stats['flights'] / aircraft_stats['flights'].sum() * 100

# 颜色映射
aircraft_colors = {
    'B737':         '#2563EB',
    'A320':         '#F59E0B',
    'A321':         '#059669',
    'A319':         '#7C3AED',
    'A330':         '#DC2626',
    'B787':         '#0891B2',
    'Regional jet': '#64748B',
    'Turbo-prop':   '#92400E',
    'Other/Unknown':'#9CA3AF',
}

print("Aircraft stats:")
print(aircraft_stats[['flights', 'flight_share', 'fuel_share', 'mean_dist']].round(1))

# ── 绘图 ──────────────────────────────────────────────────────────────
fig = plt.figure(figsize=(10, 8))
gs = GridSpec(2, 2, figure=fig, hspace=0.38, wspace=0.32,
              left=0.08, right=0.97, top=0.95, bottom=0.08)

ax_a = fig.add_subplot(gs[0, :])   # 全宽：52周时序
ax_b1 = fig.add_subplot(gs[1, 0])  # 机型架次构成
ax_b2 = fig.add_subplot(gs[1, 1])  # 机型 vs 平均飞行距离

# ── (a) 52周时序图 ──────────────────────────────────────────────────
x = np.arange(1, 53)

# 绘制面积图
ax_a.fill_between(x, 0, weekly_bj.values, alpha=0.15, color=C_BEIJING)
ax_a.fill_between(x, 0, weekly_tj.values, alpha=0.15, color=C_TIANJIN)
ax_a.plot(x, weekly_bj.values, color=C_BEIJING, linewidth=1.4, label='Beijing')
ax_a.plot(x, weekly_tj.values, color=C_TIANJIN, linewidth=1.4, label='Tianjin')

# 标注节假日语境（先画，在数据线之下）
ax_a.axvspan(0.5, 2.5, alpha=0.08, color='#FDE68A', label='Spring Festival period')
ax_a.axvspan(26.5, 35.5, alpha=0.08, color='#BBF7D0', label='Summer peak')

# 标注4代表周
y_top = weekly_bj.values.max() * 1.05
for wk, lbl in zip(rep_weeks_orig, ['W1', 'W2', 'W3', 'W4']):
    ax_a.axvline(x=wk, color=C_SELECTED, linewidth=0.9, linestyle='--', alpha=0.8)
    ax_a.text(wk, y_top, lbl, fontsize=7, color=C_SELECTED,
              ha='center', va='bottom', fontweight='bold')

ax_a.set_xlabel('Week of year', fontsize=8)
ax_a.set_ylabel('Weekly fuel demand\n(million kg)', fontsize=8)
ax_a.set_xlim(0.5, 52.5)
ax_a.set_xticks([1, 5, 10, 14, 20, 26, 30, 35, 40, 44, 52])
ax_a.set_ylim(0, weekly_bj.values.max() * 1.18)
ax_a.grid(axis='y', linestyle='--', alpha=0.25, linewidth=0.4)
ax_a.legend(loc='upper right', ncol=4, fontsize=6.5)

ax_a.text(-0.06, 1.02, '(a)', transform=ax_a.transAxes,
          fontsize=10, fontweight='bold', va='top')

# ── (b1) 机型架次横向柱图 ──────────────────────────────────────────
aircraft_order = aircraft_stats.index.tolist()
bar_colors = [aircraft_colors.get(a, '#9CA3AF') for a in aircraft_order]
y_pos = np.arange(len(aircraft_order))

bars = ax_b1.barh(y_pos, aircraft_stats['flight_share'].values,
                  color=bar_colors, height=0.65, edgecolor='none')

# 在柱末添加百分比标注
for bar, val in zip(bars, aircraft_stats['flight_share'].values):
    ax_b1.text(val + 0.3, bar.get_y() + bar.get_height()/2,
               f'{val:.1f}%', va='center', fontsize=6.5)

ax_b1.set_yticks(y_pos)
ax_b1.set_yticklabels(aircraft_order, fontsize=7)
ax_b1.set_xlabel('Share of flight records (%)', fontsize=8)
ax_b1.set_xlim(0, aircraft_stats['flight_share'].max() * 1.18)
ax_b1.spines['left'].set_visible(False)
ax_b1.tick_params(left=False)
ax_b1.grid(axis='x', linestyle='--', alpha=0.25, linewidth=0.4)

ax_b1.text(-0.18, 1.02, '(b)', transform=ax_b1.transAxes,
           fontsize=10, fontweight='bold', va='top')

# ── (b2) 机型 vs 平均飞行距离散点图 ──────────────────────────────
# 点大小按航班架次
sizes = aircraft_stats['flights'] / aircraft_stats['flights'].max() * 400 + 30

sc = ax_b2.scatter(
    aircraft_stats['mean_dist'].values,
    aircraft_stats['fuel_share'].values,
    s=sizes.values,
    c=bar_colors,
    alpha=0.85,
    edgecolors='white',
    linewidths=0.5,
    zorder=3
)

# 标注机型名称
for i, (idx, row) in enumerate(aircraft_stats.iterrows()):
    offset_x = 30
    offset_y = 0
    if idx == 'Turbo-prop':
        offset_x = -80
        offset_y = 0.5
    ax_b2.annotate(idx,
                   xy=(row['mean_dist'], row['fuel_share']),
                   xytext=(row['mean_dist'] + offset_x, row['fuel_share'] + offset_y),
                   fontsize=6, ha='left', va='center',
                   arrowprops=dict(arrowstyle='-', color='#94A3B8', lw=0.4))

ax_b2.set_xlabel('Mean flight distance (km)', fontsize=8)
ax_b2.set_ylabel('Share of total fuel demand (%)', fontsize=8)
ax_b2.grid(axis='y', linestyle='--', alpha=0.25, linewidth=0.4)

# 气泡大小图例
for val, label in [(500, '~500 flights'), (5000, '~5,000'), (12000, '~12,000')]:
    sz = val / aircraft_stats['flights'].max() * 400 + 30
    ax_b2.scatter([], [], s=sz, c='#94A3B8', alpha=0.7, label=label)
ax_b2.legend(loc='upper left', fontsize=6, title='Flight count', title_fontsize=6.5)

ax_b2.text(-0.18, 1.02, '(c)', transform=ax_b2.transAxes,
           fontsize=10, fontweight='bold', va='top')

# ── 保存 ──────────────────────────────────────────────────────────────
ts = datetime.now().strftime('%Y%m%d_%H%M%S')
out_png = os.path.join(OUT_DIR, 'demand_aircraft_supplement.png')
out_pdf = os.path.join(OUT_DIR, 'demand_aircraft_supplement.pdf')
out_svg = os.path.join(OUT_DIR, 'demand_aircraft_supplement.svg')

fig.savefig(out_png, dpi=300, bbox_inches='tight', facecolor='white')
fig.savefig(out_pdf, bbox_inches='tight', facecolor='white')
fig.savefig(out_svg, bbox_inches='tight', facecolor='white')
plt.close(fig)

print(f"\nSaved: {out_png}")
print(f"Saved: {out_pdf}")
print(f"Saved: {out_svg}")
