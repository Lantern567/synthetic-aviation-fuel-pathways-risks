#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析数据粒度并生成每日副产氢供应量
检查GIS数据完整性
"""

import pandas as pd
import geopandas as gpd
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
log_file = os.path.join(log_dir, f'data_granularity_analysis_{timestamp}.txt')

def log_print(msg):
    """同时打印到控制台和日志文件"""
    print(msg)
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(msg + '\n')

log_print("="*100)
log_print(f"数据粒度分析与每日副产氢供应量计算 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
log_print("="*100)

# ==================== 1. 数据粒度分析 ====================
log_print("\n" + "="*100)
log_print("第一部分数据粒度分析")
log_print("="*100)

log_print("\n1.1 钢铁行业数据粒度")
log_print("  - 工厂级别 (Plant-level):")
log_print("    * 每个钢铁厂的基本信息名称位置所有权等")
log_print("    * 粒度: 工厂")
log_print("  - 设备级别 (Unit-level):")
log_print("    * 每座高炉的详细信息产能运营状态投产时间等")
log_print("    * 粒度: 高炉")
log_print("  - 时间维度:")
log_print("    * 产能数据: 年产能 (ttpa - thousand tonnes per annum)")
log_print("    * 运营状态: 静态快照截至2025年9月")
log_print("    *  没有小时级或日级的动态数据")

log_print("\n1.2 石化行业数据粒度")
log_print("  - 工厂级别:")
log_print("    * 每个炼油厂的基本信息")
log_print("    * 产能单位: KBD (Thousand Barrels per Day)")
log_print("  - 时间维度:")
log_print("    * 产能数据: 日产能 (但为设计产能非实际产量)")
log_print("    * 运营状态: 静态快照")
log_print("    *  没有实际生产波动数据")

# ==================== 2. 读取并分析GIS数据 ====================
log_print("\n" + "="*100)
log_print("第二部分GIS数据完整性检查")
log_print("="*100)

plant_file = os.path.join(data_dir, 'Plant-level-data-Global-Iron-and-Steel-Tracker-September-2025-V1.xlsx')
iron_file = os.path.join(data_dir, 'Iron-unit-data-Global-Iron-and-Steel-Tracker-September-2025-V1.xlsx')
oil_refinery_file = os.path.join(base_dir, 'products', 'gis_energy_mapping', 'gis_data_scraper', 'scraped_gis_data', 'oil_refineries.geojson')

# 读取钢铁工厂数据
log_print("\n2.1 检查钢铁工厂GIS数据...")
df_plants = pd.read_excel(plant_file, sheet_name='Plant data')
china_plants = df_plants[df_plants['Country/Area'] == 'China'].copy()

# 解析坐标
def parse_coordinates(coord_str):
    """解析坐标字符串"""
    if pd.isna(coord_str):
        return None, None
    try:
        parts = str(coord_str).split(',')
        if len(parts) == 2:
            lat = float(parts[0].strip())
            lon = float(parts[1].strip())
            return lat, lon
    except:
        pass
    return None, None

china_plants[['latitude', 'longitude']] = china_plants['Coordinates'].apply(
    lambda x: pd.Series(parse_coordinates(x))
)

plants_with_coords = china_plants[china_plants['latitude'].notna()].copy()
plants_without_coords = china_plants[china_plants['latitude'].isna()].copy()

log_print(f"  - 中国钢铁工厂总数: {len(china_plants)}")
log_print(f"  - 有坐标数据: {len(plants_with_coords)} ({len(plants_with_coords)/len(china_plants)*100:.1f}%)")
log_print(f"  - 缺失坐标: {len(plants_without_coords)} ({len(plants_without_coords)/len(china_plants)*100:.1f}%)")

if len(plants_without_coords) > 0:
    log_print(f"\n  缺失坐标的工厂示例 (前5个):")
    for idx, plant in plants_without_coords.head(5).iterrows():
        log_print(f"    - {plant['Plant name (English)']} ({plant.get('Subnational unit (province/state)', 'N/A')})")

# 读取高炉数据并关联坐标
log_print("\n2.2 检查高炉级别GIS数据...")
df_bf = pd.read_excel(iron_file, sheet_name='Blast furnaces')
df_bf_merged = df_bf.merge(
    china_plants[['Plant ID', 'Country/Area', 'Subnational unit (province/state)', 'latitude', 'longitude', 'Plant name (English)']],
    left_on='GEM Plant ID',
    right_on='Plant ID',
    how='inner'
)

bf_with_coords = df_bf_merged[df_bf_merged['latitude'].notna()].copy()
bf_without_coords = df_bf_merged[df_bf_merged['latitude'].isna()].copy()

log_print(f"  - 中国高炉总数: {len(df_bf_merged)}")
log_print(f"  - 有坐标数据: {len(bf_with_coords)} ({len(bf_with_coords)/len(df_bf_merged)*100:.1f}%)")
log_print(f"  - 缺失坐标: {len(bf_without_coords)} ({len(bf_without_coords)/len(df_bf_merged)*100:.1f}%)")

# 检查炼油厂GIS数据
log_print("\n2.3 检查炼油厂GIS数据...")
df_refineries = gpd.read_file(oil_refinery_file)
china_refineries = df_refineries[df_refineries['Province'].notna()].copy()

# GeoDataFrame已经包含geometry
refineries_with_coords = china_refineries[china_refineries.geometry.notna()].copy()
refineries_without_coords = china_refineries[china_refineries.geometry.isna()].copy()

log_print(f"  - 中国炼油厂总数: {len(china_refineries)}")
log_print(f"  - 有坐标数据: {len(refineries_with_coords)} ({len(refineries_with_coords)/len(china_refineries)*100:.1f}%)")
log_print(f"  - 缺失坐标: {len(refineries_without_coords)} ({len(refineries_without_coords)/len(china_refineries)*100:.1f}%)")

# ==================== 3. 计算每日副产氢供应量 ====================
log_print("\n" + "="*100)
log_print("第三部分计算每日最大副产氢供应量按地点")
log_print("="*100)

log_print("\n3.1 计算方法说明:")
log_print("  - 时间转换: 年产能  365 = 日产能")
log_print("  - 假设: 装置全年连续运行实际运营率可能更低")
log_print("  - 地点粒度: 工厂级同一工厂的多座高炉合并")

# 3.1 钢铁行业每日副产氢
log_print("\n3.2 钢铁行业焦化副产氢每日:")

# 焦化副产氢计算参数
coke_ratio = 350  # kg焦炭/t铁水
cog_yield = 420   # Nm3焦炉煤气/t焦炭
h2_content = 0.57  # 焦炉煤气含氢量
h2_recovery = 0.90  # 氢提纯率
h2_density = 0.0899  # kg/Nm3

# 筛选运营中的高炉
if 'Current Capacity (ttpa)' in df_bf_merged.columns:
    operating_bf = df_bf_merged[df_bf_merged['Unit Status'] == 'operating'].copy()
    operating_bf = operating_bf[operating_bf['latitude'].notna()].copy()  # 只保留有坐标的

    # 计算副产氢
    operating_bf['iron_capacity_t_year'] = operating_bf['Current Capacity (ttpa)'] * 10000  # 万吨转吨
    operating_bf['iron_capacity_t_day'] = operating_bf['iron_capacity_t_year'] / 365  # 日产能

    operating_bf['coke_demand_t_day'] = operating_bf['iron_capacity_t_day'] * (coke_ratio / 1000)
    operating_bf['cog_volume_nm3_day'] = operating_bf['coke_demand_t_day'] * cog_yield
    operating_bf['h2_volume_nm3_day'] = operating_bf['cog_volume_nm3_day'] * h2_content * h2_recovery
    operating_bf['h2_mass_kg_day'] = operating_bf['h2_volume_nm3_day'] * h2_density
    operating_bf['h2_mass_t_day'] = operating_bf['h2_mass_kg_day'] / 1000

    # 按工厂汇总同一工厂多座高炉
    plant_daily_h2 = operating_bf.groupby('GEM Plant ID').agg({
        'Plant name (English)': 'first',
        'Subnational unit (province/state)': 'first',
        'latitude': 'first',
        'longitude': 'first',
        'h2_mass_t_day': 'sum',
        'Unit Name': 'count'  # 高炉数量
    }).reset_index()

    plant_daily_h2.columns = ['plant_id', 'plant_name', 'province', 'latitude', 'longitude', 'h2_daily_tonnes', 'num_blast_furnaces']

    log_print(f"  - 有效工厂数量有坐标+运营中: {len(plant_daily_h2)}")
    log_print(f"  - 总日产氢量: {plant_daily_h2['h2_daily_tonnes'].sum():,.1f} 吨/日")
    log_print(f"  - 平均单厂日产氢: {plant_daily_h2['h2_daily_tonnes'].mean():,.1f} 吨/日")
    log_print(f"  - 最大单厂日产氢: {plant_daily_h2['h2_daily_tonnes'].max():,.1f} 吨/日")
    log_print(f"  - 最小单厂日产氢: {plant_daily_h2['h2_daily_tonnes'].min():,.1f} 吨/日")

    log_print(f"\n  Top 10 钢铁厂每日副产氢量:")
    for i, row in plant_daily_h2.nlargest(10, 'h2_daily_tonnes').iterrows():
        log_print(f"    {i+1:2d}. {row['plant_name'][:40]:40s} | {row['province']:15s} | {row['h2_daily_tonnes']:8.1f} t/day | {int(row['num_blast_furnaces'])} BFs")

# 3.2 石化行业每日副产氢
log_print("\n3.3 石化行业催化重整副产氢每日:")

reforming_ratio = 0.20
h2_yield = 3.5  # kg H2/t原油
capacity_factor = 0.85
barrel_to_tonne = 0.136

if 'Capacity' in china_refineries.columns:
    operating_refineries = china_refineries[china_refineries['Status'] == 'Operating'].copy()
    operating_refineries = operating_refineries[operating_refineries.geometry.notna()].copy()

    operating_refineries['capacity_kbd'] = pd.to_numeric(operating_refineries['Capacity'], errors='coerce')
    operating_refineries = operating_refineries[operating_refineries['capacity_kbd'].notna()].copy()

    # 计算每日副产氢
    operating_refineries['capacity_t_day'] = operating_refineries['capacity_kbd'] * barrel_to_tonne * 1000
    operating_refineries['reforming_capacity_t_day'] = operating_refineries['capacity_t_day'] * reforming_ratio * capacity_factor
    operating_refineries['h2_mass_t_day'] = operating_refineries['reforming_capacity_t_day'] * (h2_yield / 1000)

    # 提取经纬度
    operating_refineries['latitude'] = operating_refineries.geometry.y
    operating_refineries['longitude'] = operating_refineries.geometry.x

    refinery_daily_h2 = operating_refineries[['Name', 'ChineseName', 'Province', 'latitude', 'longitude', 'h2_mass_t_day', 'Capacity']].copy()
    refinery_daily_h2.columns = ['refinery_name', 'refinery_name_cn', 'province', 'latitude', 'longitude', 'h2_daily_tonnes', 'capacity_kbd']

    log_print(f"  - 有效炼油厂数量有坐标+运营中: {len(refinery_daily_h2)}")
    log_print(f"  - 总日产氢量: {refinery_daily_h2['h2_daily_tonnes'].sum():,.1f} 吨/日")
    log_print(f"  - 平均单厂日产氢: {refinery_daily_h2['h2_daily_tonnes'].mean():,.1f} 吨/日")
    log_print(f"  - 最大单厂日产氢: {refinery_daily_h2['h2_daily_tonnes'].max():,.1f} 吨/日")
    log_print(f"  - 最小单厂日产氢: {refinery_daily_h2['h2_daily_tonnes'].min():,.1f} 吨/日")

    log_print(f"\n  Top 10 炼油厂每日副产氢量:")
    for i, row in refinery_daily_h2.nlargest(10, 'h2_daily_tonnes').iterrows():
        log_print(f"    {i+1:2d}. {row['refinery_name'][:40]:40s} | {row['province']:15s} | {row['h2_daily_tonnes']:6.1f} t/day")

# ==================== 4. 保存结果 ====================
log_print("\n" + "="*100)
log_print("第四部分保存结果数据")
log_print("="*100)

# 保存钢铁厂每日副产氢数据
steel_output = os.path.join(data_dir, f'steel_daily_byproduct_h2_{timestamp}.csv')
plant_daily_h2.to_csv(steel_output, index=False, encoding='utf-8-sig')
log_print(f"\n 钢铁厂每日副产氢数据已保存: {steel_output}")

# 保存炼油厂每日副产氢数据
refinery_output = os.path.join(data_dir, f'refinery_daily_byproduct_h2_{timestamp}.csv')
refinery_daily_h2.to_csv(refinery_output, index=False, encoding='utf-8-sig')
log_print(f" 炼油厂每日副产氢数据已保存: {refinery_output}")

# 生成GeoJSON格式
log_print("\n4.1 生成GeoJSON格式数据...")

# 钢铁厂GeoJSON
import geopandas as gpd
from shapely.geometry import Point

steel_gdf = gpd.GeoDataFrame(
    plant_daily_h2,
    geometry=[Point(xy) for xy in zip(plant_daily_h2['longitude'], plant_daily_h2['latitude'])],
    crs='EPSG:4326'
)
steel_geojson = os.path.join(data_dir, f'steel_daily_byproduct_h2_{timestamp}.geojson')
steel_gdf.to_file(steel_geojson, driver='GeoJSON')
log_print(f" 钢铁厂GeoJSON已保存: {steel_geojson}")

# 炼油厂GeoJSON
refinery_gdf = gpd.GeoDataFrame(
    refinery_daily_h2,
    geometry=[Point(xy) for xy in zip(refinery_daily_h2['longitude'], refinery_daily_h2['latitude'])],
    crs='EPSG:4326'
)
refinery_geojson = os.path.join(data_dir, f'refinery_daily_byproduct_h2_{timestamp}.geojson')
refinery_gdf.to_file(refinery_geojson, driver='GeoJSON')
log_print(f" 炼油厂GeoJSON已保存: {refinery_geojson}")

# 保存汇总统计
summary = {
    'timestamp': datetime.now().isoformat(),
    'data_granularity': {
        'spatial': 'plant-level (facility)',
        'temporal': 'annual capacity converted to daily',
        'note': 'No hourly or real-time production data available'
    },
    'gis_coverage': {
        'steel_plants': {
            'total': int(len(china_plants)),
            'with_coordinates': int(len(plants_with_coords)),
            'coverage_rate': f"{len(plants_with_coords)/len(china_plants)*100:.1f}%"
        },
        'blast_furnaces': {
            'total': int(len(df_bf_merged)),
            'with_coordinates': int(len(bf_with_coords)),
            'coverage_rate': f"{len(bf_with_coords)/len(df_bf_merged)*100:.1f}%"
        },
        'refineries': {
            'total': int(len(china_refineries)),
            'with_coordinates': int(len(refineries_with_coords)),
            'coverage_rate': f"{len(refineries_with_coords)/len(china_refineries)*100:.1f}%"
        }
    },
    'daily_production': {
        'steel_industry': {
            'num_plants': int(len(plant_daily_h2)),
            'total_tonnes_per_day': float(plant_daily_h2['h2_daily_tonnes'].sum()),
            'avg_tonnes_per_plant_per_day': float(plant_daily_h2['h2_daily_tonnes'].mean())
        },
        'petrochemical_industry': {
            'num_refineries': int(len(refinery_daily_h2)),
            'total_tonnes_per_day': float(refinery_daily_h2['h2_daily_tonnes'].sum()),
            'avg_tonnes_per_refinery_per_day': float(refinery_daily_h2['h2_daily_tonnes'].mean())
        },
        'total_tonnes_per_day': float(plant_daily_h2['h2_daily_tonnes'].sum() + refinery_daily_h2['h2_daily_tonnes'].sum())
    }
}

summary_file = os.path.join(log_dir, f'daily_h2_summary_{timestamp}.json')
with open(summary_file, 'w', encoding='utf-8') as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)
log_print(f" 汇总统计已保存: {summary_file}")

log_print("\n" + "="*100)
log_print("分析完成!")
log_print(f"日志已保存: {log_file}")
log_print("="*100)
