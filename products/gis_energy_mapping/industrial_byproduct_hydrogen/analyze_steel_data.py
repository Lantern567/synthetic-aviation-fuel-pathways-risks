#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析钢铁行业数据集
Global Iron and Steel Tracker数据分析
"""

import pandas as pd
import os

# 设置路径
data_dir = r'D:\Green methanol\green_methanol_for_port_transportation-main\green_methanol_for_port_transportation-main\products\gis_energy_mapping\industrial_byproduct_hydrogen\data'
os.chdir(data_dir)

print("="*80)
print("钢铁行业数据集分析")
print("="*80)

# 1. 分析Plant-level数据
print("\n" + "="*80)
print("1. Plant-level Data 分析")
print("="*80)

plant_file = 'Plant-level-data-Global-Iron-and-Steel-Tracker-September-2025-V1.xlsx'
xls_plant = pd.ExcelFile(plant_file)
print(f"\nSheet数量: {len(xls_plant.sheet_names)}")
print(f"Sheet名称: {xls_plant.sheet_names}")

# 读取工厂数据
df_plants = pd.read_excel(plant_file, sheet_name='Plant data')
print(f"\n总工厂数量: {len(df_plants)}")
print(f"中国工厂数量: {len(df_plants[df_plants['Country/Area'] == 'China'])}")

print("\n工厂数据列名 (前25列):")
for i, col in enumerate(df_plants.columns[:25], 1):
    print(f"  {i:2d}. {col}")

# 中国工厂示例
china_plants = df_plants[df_plants['Country/Area'] == 'China']
print(f"\n中国工厂示例 (前3个):")
for idx, plant in china_plants.head(3).iterrows():
    print(f"\n  工厂名: {plant['Plant name (English)']}")
    print(f"  省份: {plant['Subnational unit (province/state)']}")
    print(f"  坐标: {plant['Coordinates']}")

# 2. 分析Iron Unit数据
print("\n" + "="*80)
print("2. Iron Unit Data 分析")
print("="*80)

iron_file = 'Iron-unit-data-Global-Iron-and-Steel-Tracker-September-2025-V1.xlsx'
xls_iron = pd.ExcelFile(iron_file)
print(f"\nSheet数量: {len(xls_iron.sheet_names)}")
print(f"Sheet名称: {xls_iron.sheet_names}")

# 读取高炉数据
df_bf = pd.read_excel(iron_file, sheet_name='Blast furnaces')
print(f"\n全球高炉总数: {len(df_bf)}")

# 先查看列名中是否有Country相关字段
country_cols = [col for col in df_bf.columns if 'country' in col.lower() or 'area' in col.lower()]
print(f"Country相关列: {country_cols}")

# 使用正确的列名
country_col = 'Country' if 'Country' in df_bf.columns else (country_cols[0] if country_cols else None)
if country_col:
    print(f"中国高炉数量: {len(df_bf[df_bf[country_col] == 'China'])}")
else:
    print("未找到Country列，显示所有列名")

print("\n高炉数据列名 (前25列):")
for i, col in enumerate(df_bf.columns[:25], 1):
    print(f"  {i:2d}. {col}")

# 中国高炉示例
if country_col:
    china_bf = df_bf[df_bf[country_col] == 'China']
    print(f"\n中国高炉示例 (前3个):")
    for idx, bf in china_bf.head(3).iterrows():
        print(f"\n  高炉: {bf.get('Unit name', 'N/A')}")
        print(f"  工厂: {bf.get('Plant name (English)', 'N/A')}")
        print(f"  省份: {bf.get('Subnational unit (province/state)', 'N/A')}")
        if 'Capacity (ttpa)' in bf.index:
            print(f"  产能: {bf['Capacity (ttpa)']} 万吨/年")
        if 'Status' in bf.index:
            print(f"  状态: {bf['Status']}")

    # 统计中国高炉运营状态
    if 'Status' in df_bf.columns:
        print(f"\n中国高炉运营状态统计:")
        status_counts = china_bf['Status'].value_counts()
        for status, count in status_counts.items():
            print(f"  {status}: {count}")

    # 统计中国高炉产能分布
    if 'Capacity (ttpa)' in df_bf.columns:
        china_capacity = china_bf['Capacity (ttpa)'].dropna()
        print(f"\n中国高炉产能统计:")
        print(f"  总产能: {china_capacity.sum():.2f} 万吨/年")
        print(f"  平均产能: {china_capacity.mean():.2f} 万吨/年")
        print(f"  最大产能: {china_capacity.max():.2f} 万吨/年")
        print(f"  最小产能: {china_capacity.min():.2f} 万吨/年")

print("\n" + "="*80)
print("数据分析完成!")
print("="*80)
