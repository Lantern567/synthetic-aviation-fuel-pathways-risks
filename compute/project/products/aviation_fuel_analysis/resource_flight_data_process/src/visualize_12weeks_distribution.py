#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
可视化12周典型数据在全年中的分布
Visualize the distribution of 12 typical weeks across the year
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from datetime import datetime
import numpy as np
from pathlib import Path

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['Noto Sans CJK SC', 'WenQuanYi Zen Hei', 'Droid Sans Fallback', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# 读取数据
data_file = Path('products/aviation_fuel_analysis/resource_flight_data_process/results/typical_weeks_data/typical_12weeks_demand_20251129_163442.xlsx')
df = pd.read_excel(data_file)

# 提取唯一周信息
weeks_info = df.groupby('week_number').first()[['week_start', 'week_end', 'original_week']].reset_index()
weeks_info['week_start'] = pd.to_datetime(weeks_info['week_start'])
weeks_info['week_end'] = pd.to_datetime(weeks_info['week_end'])
weeks_info['month'] = weeks_info['week_start'].dt.month
weeks_info['day_of_year'] = weeks_info['week_start'].dt.dayofyear

# 创建图形
fig = plt.figure(figsize=(20, 12))

# ==================== 图1: 全年时间轴分布 ====================
ax1 = plt.subplot(3, 1, 1)

# 绘制全年背景
months = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']
month_days = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]  # 2024是闰年
month_starts = [0] + list(np.cumsum(month_days)[:-1])

# 绘制月份背景
for i, (start, days, month) in enumerate(zip(month_starts, month_days, months)):
    color = '#E8F4F8' if i % 2 == 0 else '#F0F8FF'
    ax1.barh(0, days, left=start, height=1, color=color, edgecolor='gray', linewidth=0.5, alpha=0.3)
    # 添加月份标签
    ax1.text(start + days/2, 0, month, ha='center', va='center', fontsize=10, fontweight='bold')

# 绘制选中的12周
colors = plt.cm.Set3(np.linspace(0, 1, 12))
for idx, row in weeks_info.iterrows():
    start_day = row['day_of_year']
    duration = 7
    week_num = row['week_number']
    original_week = int(row['original_week'])

    # 绘制周条
    ax1.barh(1, duration, left=start_day, height=0.5,
             color=colors[idx], edgecolor='black', linewidth=1.5)

    # 添加周标签
    ax1.text(start_day + duration/2, 1, f'{week_num}',
             ha='center', va='center', fontsize=9, fontweight='bold')

ax1.set_xlim(0, 366)
ax1.set_ylim(-0.5, 1.5)
ax1.set_yticks([0, 1])
ax1.set_yticklabels(['全年12个月', '选中的12周'], fontsize=11)
ax1.set_xlabel('天数（从1月1日起）', fontsize=12)
ax1.set_title('12周典型数据在2024年全年中的分布', fontsize=16, fontweight='bold', pad=20)
ax1.grid(axis='x', alpha=0.3, linestyle='--')

# ==================== 图2: 月份分布柱状图 ====================
ax2 = plt.subplot(3, 2, 3)

month_counts = weeks_info['month'].value_counts().sort_index()
all_months = list(range(1, 13))
month_counts_full = [month_counts.get(m, 0) for m in all_months]

bars = ax2.bar(all_months, month_counts_full, color='steelblue', edgecolor='black', linewidth=1.5)

# 为有数据的月份添加颜色
for i, (month, count) in enumerate(zip(all_months, month_counts_full)):
    if count > 0:
        bars[i].set_color('#FF6B6B')
    else:
        bars[i].set_color('#E0E0E0')

ax2.set_xlabel('月份', fontsize=12)
ax2.set_ylabel('周数', fontsize=12)
ax2.set_title('各月份包含的典型周数量', fontsize=14, fontweight='bold')
ax2.set_xticks(all_months)
ax2.set_xticklabels([f'{m}月' for m in all_months], rotation=45)
ax2.grid(axis='y', alpha=0.3, linestyle='--')

# 添加数值标签
for i, (month, count) in enumerate(zip(all_months, month_counts_full)):
    if count > 0:
        ax2.text(month, count + 0.1, str(int(count)), ha='center', va='bottom', fontsize=10, fontweight='bold')

# ==================== 图3: 周次对照表 ====================
ax3 = plt.subplot(3, 2, 4)
ax3.axis('off')

# 创建表格数据
table_data = []
for idx, row in weeks_info.iterrows():
    week_num = row['week_number']
    original_week = int(row['original_week'])
    start = row['week_start'].strftime('%m月%d日')
    end = row['week_end'].strftime('%m月%d日')
    table_data.append([f'第{week_num}周', f'原第{original_week}周', f'{start}-{end}'])

# 分两列显示
col1_data = table_data[:6]
col2_data = table_data[6:]

# 创建表格
table1 = ax3.table(cellText=col1_data,
                   colLabels=['新编号', '原编号', '时间范围'],
                   cellLoc='center',
                   loc='upper left',
                   bbox=[0, 0.5, 0.45, 0.5],
                   colWidths=[0.15, 0.15, 0.15])
table1.auto_set_font_size(False)
table1.set_fontsize(9)
table1.scale(1, 2)

# 设置表头样式
for (i, j), cell in table1.get_celld().items():
    if i == 0:
        cell.set_facecolor('#4472C4')
        cell.set_text_props(weight='bold', color='white')
    else:
        cell.set_facecolor('#E8F4F8' if i % 2 == 0 else 'white')

table2 = ax3.table(cellText=col2_data,
                   colLabels=['新编号', '原编号', '时间范围'],
                   cellLoc='center',
                   loc='upper right',
                   bbox=[0.55, 0.5, 0.45, 0.5],
                   colWidths=[0.15, 0.15, 0.15])
table2.auto_set_font_size(False)
table2.set_fontsize(9)
table2.scale(1, 2)

# 设置表头样式
for (i, j), cell in table2.get_celld().items():
    if i == 0:
        cell.set_facecolor('#4472C4')
        cell.set_text_props(weight='bold', color='white')
    else:
        cell.set_facecolor('#E8F4F8' if i % 2 == 0 else 'white')

ax3.set_title('周次对照表', fontsize=14, fontweight='bold', pad=10)

# ==================== 图4: 节假日覆盖情况 ====================
ax4 = plt.subplot(3, 1, 3)

# 定义节假日
holidays = {
    '元旦': (1, 1),
    '春节': (2, 10),  # 2024年春节
    '清明': (4, 4),
    '五一': (5, 1),
    '端午': (6, 10),
    '国庆': (10, 1),
}

# 计算节假日的day_of_year
holiday_days = {}
for name, (month, day) in holidays.items():
    date = pd.Timestamp(f'2024-{month:02d}-{day:02d}')
    holiday_days[name] = date.dayofyear

# 绘制全年背景
ax4.barh(0, 366, left=0, height=0.3, color='lightgray', alpha=0.3)

# 标记节假日
for name, day in holiday_days.items():
    ax4.plot([day, day], [-0.2, 0.5], 'r--', linewidth=2, alpha=0.6)
    ax4.text(day, 0.6, name, ha='center', va='bottom', fontsize=10, fontweight='bold', color='red')

# 标记选中的周
for idx, row in weeks_info.iterrows():
    start_day = row['day_of_year']
    ax4.barh(0, 7, left=start_day, height=0.3, color=colors[idx], edgecolor='black', linewidth=1)

    # 检查这周是否覆盖节假日
    week_range = range(start_day, start_day + 7)
    for holiday_name, holiday_day in holiday_days.items():
        if holiday_day in week_range:
            ax4.text(start_day + 3.5, -0.3, f'含{holiday_name}',
                    ha='center', va='top', fontsize=8,
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7))
            break

ax4.set_xlim(0, 366)
ax4.set_ylim(-0.8, 1.0)
ax4.set_yticks([])
ax4.set_xlabel('天数（从1月1日起）', fontsize=12)
ax4.set_title('典型周与重要节假日的覆盖情况', fontsize=14, fontweight='bold')
ax4.grid(axis='x', alpha=0.3, linestyle='--')

# 添加图例
legend_elements = [
    mpatches.Patch(color='red', alpha=0.3, label='重要节假日'),
    mpatches.Patch(color='steelblue', label='选中的典型周')
]
ax4.legend(handles=legend_elements, loc='upper right', fontsize=10)

# 调整布局
plt.tight_layout()

# 保存图片
output_dir = Path('products/aviation_fuel_analysis/resource_flight_data_process/results/typical_weeks_data/visualizations')
output_dir.mkdir(parents=True, exist_ok=True)

timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
output_file = output_dir / f'12weeks_distribution_{timestamp}.png'
plt.savefig(output_file, dpi=300, bbox_inches='tight')
print(f"✓ 可视化图片已保存: {output_file}")

plt.show()
