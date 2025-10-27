#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工业副产氢潜力评估
评估钢铁行业焦化副产氢和石化行业催化重整副产氢的潜力
"""

import pandas as pd
import json
from datetime import datetime
import os

# 设置路径
base_dir = r'D:\Green methanol\green_methanol_for_port_transportation-main\green_methanol_for_port_transportation-main'
data_dir = os.path.join(base_dir, 'products', 'gis_energy_mapping', 'industrial_byproduct_hydrogen', 'data')
log_dir = os.path.join(base_dir, 'products', 'gis_energy_mapping', 'industrial_byproduct_hydrogen', 'logs')
os.makedirs(log_dir, exist_ok=True)

# 创建日志文件
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
log_file = os.path.join(log_dir, f'byproduct_hydrogen_analysis_{timestamp}.txt')

def log_print(msg):
    """同时打印到控制台和日志文件"""
    print(msg)
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(msg + '\n')

log_print("="*100)
log_print(f"工业副产氢潜力评估 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
log_print("="*100)

# ==================== 1. 读取钢铁行业数据 ====================
log_print("\n" + "="*100)
log_print("第一部分：钢铁行业焦化副产氢潜力评估")
log_print("="*100)

plant_file = os.path.join(data_dir, 'Plant-level-data-Global-Iron-and-Steel-Tracker-September-2025-V1.xlsx')
iron_file = os.path.join(data_dir, 'Iron-unit-data-Global-Iron-and-Steel-Tracker-September-2025-V1.xlsx')

# 读取工厂数据
log_print("\n1.1 读取钢铁工厂数据...")
df_plants = pd.read_excel(plant_file, sheet_name='Plant data')
china_plants = df_plants[df_plants['Country/Area'] == 'China'].copy()
log_print(f"  - 全球钢铁工厂总数: {len(df_plants)}")
log_print(f"  - 中国钢铁工厂数量: {len(china_plants)}")

# 读取高炉数据
log_print("\n1.2 读取高炉数据...")
df_bf = pd.read_excel(iron_file, sheet_name='Blast furnaces')
log_print(f"  - 全球高炉总数: {len(df_bf)}")

# 通过Plant ID关联
log_print("\n1.3 关联工厂和高炉数据...")
df_bf_merged = df_bf.merge(
    china_plants[['Plant ID', 'Country/Area', 'Subnational unit (province/state)', 'Coordinates']],
    left_on='GEM Plant ID',
    right_on='Plant ID',
    how='inner'
)
log_print(f"  - 中国高炉数量: {len(df_bf_merged)}")

# 统计运营状态
if 'Unit Status' in df_bf_merged.columns:
    log_print("\n1.4 中国高炉运营状态:")
    status_counts = df_bf_merged['Unit Status'].value_counts()
    for status, count in status_counts.items():
        log_print(f"  - {status}: {count}")

# 计算焦化副产氢潜力
log_print("\n1.5 焦化副产氢潜力计算...")
log_print("\n  参数设置:")
log_print("  - 焦比 (kg焦炭/t铁水): 350")
log_print("  - 焦炉煤气产率 (Nm3/t焦炭): 420")
log_print("  - 焦炉煤气含氢量: 57%")
log_print("  - 氢提纯率: 90%")
log_print("  - 氢气密度 (kg/Nm3): 0.0899")

# 焦化副产氢计算参数
coke_ratio = 350  # kg焦炭/t铁水
cog_yield = 420   # Nm³焦炉煤气/t焦炭
h2_content = 0.57  # 焦炉煤气含氢量
h2_recovery = 0.90  # 氢提纯率
h2_density = 0.0899  # kg/Nm³

# 计算副产氢量
if 'Current Capacity (ttpa)' in df_bf_merged.columns:
    # 筛选运营中的高炉
    operating_bf = df_bf_merged[df_bf_merged['Unit Status'] == 'operating'].copy()
    log_print(f"\n  运营中的高炉数量: {len(operating_bf)}")

    # 计算副产氢
    operating_bf['iron_capacity_t'] = operating_bf['Current Capacity (ttpa)'] * 10000  # 万吨转吨
    operating_bf['coke_demand_t'] = operating_bf['iron_capacity_t'] * (coke_ratio / 1000)  # 焦炭需求（吨）
    operating_bf['cog_volume_nm3'] = operating_bf['coke_demand_t'] * cog_yield  # 焦炉煤气量（Nm³）
    operating_bf['h2_volume_nm3'] = operating_bf['cog_volume_nm3'] * h2_content * h2_recovery  # 氢气量（Nm³）
    operating_bf['h2_mass_kg'] = operating_bf['h2_volume_nm3'] * h2_density  # 氢气量（kg）
    operating_bf['h2_mass_t'] = operating_bf['h2_mass_kg'] / 1000  # 氢气量（吨）

    total_h2_steel = operating_bf['h2_mass_t'].sum()

    log_print(f"\n  焦化副产氢总量: {total_h2_steel:,.0f} 吨/年")
    log_print(f"  平均单厂副产氢: {total_h2_steel/len(operating_bf):,.0f} 吨/年")

    # 按省份统计
    log_print("\n1.6 焦化副产氢省份分布（Top 10）:")
    province_h2 = operating_bf.groupby('Subnational unit (province/state)')['h2_mass_t'].sum().sort_values(ascending=False)
    for i, (province, h2) in enumerate(province_h2.head(10).items(), 1):
        log_print(f"  {i:2d}. {province}: {h2:,.0f} 吨/年")
else:
    log_print("  警告: 未找到产能数据列")
    total_h2_steel = 0

# ==================== 2. 读取石化行业数据 ====================
log_print("\n" + "="*100)
log_print("第二部分：石化行业催化重整副产氢潜力评估")
log_print("="*100)

oil_refinery_file = os.path.join(base_dir, 'products', 'gis_energy_mapping', 'gis_data_scraper', 'scraped_gis_data', 'oil_refineries.geojson')

log_print("\n2.1 读取炼油厂数据...")
import geopandas as gpd
df_refineries = gpd.read_file(oil_refinery_file)

# 筛选中国炼油厂
china_refineries = df_refineries[df_refineries['Province'].notna()].copy()
log_print(f"  - 中国炼油厂数量: {len(china_refineries)}")

# 计算催化重整副产氢潜力
log_print("\n2.2 催化重整副产氢潜力计算...")
log_print("\n  参数设置:")
log_print("  - 催化重整装置比例: 20%")
log_print("  - 氢气产率 (kg H2/t 原油): 3.5")
log_print("  - 运营率: 85%")

# 催化重整副产氢参数
reforming_ratio = 0.20  # 催化重整装置占比
h2_yield = 3.5  # kg H₂/t原油
capacity_factor = 0.85  # 运营率

# 转换产能单位 (KBD to t/year)
# 1 barrel = 0.136 tonnes (crude oil density ~0.85)
barrel_to_tonne = 0.136
days_per_year = 365

if 'Capacity' in china_refineries.columns:
    # 筛选运营中的炼油厂
    operating_refineries = china_refineries[china_refineries['Status'] == 'Operating'].copy()
    log_print(f"\n  运营中的炼油厂数量: {len(operating_refineries)}")

    # 转换产能并计算副产氢
    operating_refineries['capacity_kbd'] = pd.to_numeric(operating_refineries['Capacity'], errors='coerce')
    operating_refineries = operating_refineries[operating_refineries['capacity_kbd'].notna()]

    operating_refineries['capacity_tpy'] = operating_refineries['capacity_kbd'] * barrel_to_tonne * days_per_year * 1000  # 吨/年
    operating_refineries['reforming_capacity_tpy'] = operating_refineries['capacity_tpy'] * reforming_ratio * capacity_factor
    operating_refineries['h2_mass_t'] = operating_refineries['reforming_capacity_tpy'] * (h2_yield / 1000)  # 吨H₂/年

    total_h2_refinery = operating_refineries['h2_mass_t'].sum()

    log_print(f"\n  催化重整副产氢总量: {total_h2_refinery:,.0f} 吨/年")
    log_print(f"  平均单厂副产氢: {total_h2_refinery/len(operating_refineries):,.0f} 吨/年")

    # 按省份统计
    log_print("\n2.3 催化重整副产氢省份分布（Top 10）:")
    province_h2_refinery = operating_refineries.groupby('Province')['h2_mass_t'].sum().sort_values(ascending=False)
    for i, (province, h2) in enumerate(province_h2_refinery.head(10).items(), 1):
        log_print(f"  {i:2d}. {province}: {h2:,.0f} 吨/年")
else:
    log_print("  警告: 未找到产能数据列")
    total_h2_refinery = 0

# ==================== 3. 总结 ====================
log_print("\n" + "="*100)
log_print("第三部分：工业副产氢潜力总结")
log_print("="*100)

total_h2_all = total_h2_steel + total_h2_refinery

log_print(f"\n3.1 副产氢总量汇总:")
log_print(f"  - 钢铁行业焦化副产氢: {total_h2_steel:,.0f} 吨/年")
log_print(f"  - 石化行业催化重整副产氢: {total_h2_refinery:,.0f} 吨/年")
log_print(f"  - 工业副产氢总计: {total_h2_all:,.0f} 吨/年")

log_print(f"\n3.2 副产氢占比:")
if total_h2_all > 0:
    log_print(f"  - 钢铁行业: {total_h2_steel/total_h2_all*100:.1f}%")
    log_print(f"  - 石化行业: {total_h2_refinery/total_h2_all*100:.1f}%")

log_print(f"\n3.3 与绿氢对比:")
log_print(f"  - 假设风电制氢成本: 15元/kg H2")
log_print(f"  - 副产氢提纯成本: 5元/kg H2")
log_print(f"  - 成本优势: 10元/kg H2 (67%)")
log_print(f"  - 副产氢年度成本节约: {total_h2_all * 10 / 10000:.2f} 亿元")

# 保存结果到JSON
result_json = {
    'timestamp': datetime.now().isoformat(),
    'steel_industry': {
        'total_plants': int(len(china_plants)),
        'total_blast_furnaces': int(len(df_bf_merged)),
        'operating_blast_furnaces': int(len(operating_bf)) if 'Current Capacity (ttpa)' in df_bf_merged.columns else 0,
        'byproduct_h2_tonnes_per_year': float(total_h2_steel)
    },
    'petrochemical_industry': {
        'total_refineries': int(len(china_refineries)),
        'operating_refineries': int(len(operating_refineries)) if 'Capacity' in china_refineries.columns else 0,
        'byproduct_h2_tonnes_per_year': float(total_h2_refinery)
    },
    'total': {
        'byproduct_h2_tonnes_per_year': float(total_h2_all),
        'steel_percentage': float(total_h2_steel/total_h2_all*100) if total_h2_all > 0 else 0,
        'petrochemical_percentage': float(total_h2_refinery/total_h2_all*100) if total_h2_all > 0 else 0
    }
}

json_file = os.path.join(log_dir, f'byproduct_hydrogen_summary_{timestamp}.json')
with open(json_file, 'w', encoding='utf-8') as f:
    json.dump(result_json, f, ensure_ascii=False, indent=2)

log_print("\n" + "="*100)
log_print("分析完成!")
log_print(f"日志已保存: {log_file}")
log_print(f"结果JSON已保存: {json_file}")
log_print("="*100)
