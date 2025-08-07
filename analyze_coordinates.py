#!/usr/bin/env python3
"""
分析数据中的坐标范围，识别可能超出OSM覆盖范围的点
"""

import pandas as pd
import numpy as np
import os

def analyze_coordinates():
    print("分析数据坐标范围...")
    
    # 中国大陆的大致边界范围（用于参考）
    china_bounds = {
        'lat_min': 18.0,    # 海南南端
        'lat_max': 53.5,    # 黑龙江北端  
        'lon_min': 73.0,    # 新疆西端
        'lon_max': 135.0    # 黑龙江东端
    }
    
    print(f"中国大致边界范围:")
    print(f"  纬度: {china_bounds['lat_min']} ~ {china_bounds['lat_max']}")
    print(f"  经度: {china_bounds['lon_min']} ~ {china_bounds['lon_max']}")
    print()
    
    # 检查各个数据文件中的坐标
    data_files = [
        "natural_gas_supply_chain_optimization/data/integrated_gas_pipeline_price_data.csv",
        "gis_data_scraper/scraped_gis_data/lng_terminals.csv",
        "gis_data_scraper/scraped_gis_data/gas_power_plants.csv",
        "gis_data_scraper/scraped_gis_data/coal_power_plants.csv",
        "gis_data_scraper/scraped_gis_data/wind_power_plants.csv",
        "gis_data_scraper/scraped_gis_data/solar_power_plants.csv"
    ]
    
    total_out_of_bounds = 0
    
    for file_path in data_files:
        if os.path.exists(file_path):
            try:
                print(f"检查文件: {file_path}")
                df = pd.read_csv(file_path)
                
                # 查找纬度和经度列
                lat_cols = [col for col in df.columns if 'lat' in col.lower() or '纬度' in col]
                lon_cols = [col for col in df.columns if 'lon' in col.lower() or '经度' in col]
                
                if lat_cols and lon_cols:
                    lat_col = lat_cols[0]
                    lon_col = lon_cols[0]
                    
                    # 统计超出范围的点
                    out_of_bounds = (
                        (df[lat_col] < china_bounds['lat_min']) |
                        (df[lat_col] > china_bounds['lat_max']) |
                        (df[lon_col] < china_bounds['lon_min']) |
                        (df[lon_col] > china_bounds['lon_max'])
                    )
                    
                    out_count = out_of_bounds.sum()
                    total_count = len(df)
                    total_out_of_bounds += out_count
                    
                    print(f"  总数: {total_count}")
                    print(f"  超出中国范围: {out_count} ({out_count/total_count*100:.1f}%)")
                    
                    if out_count > 0:
                        print("  超出范围的坐标示例:")
                        out_points = df[out_of_bounds][[lat_col, lon_col]].head(5)
                        for idx, row in out_points.iterrows():
                            print(f"    {row[lat_col]:.6f}, {row[lon_col]:.6f}")
                    
                    # 检查是否有无效坐标
                    invalid = df[lat_col].isna() | df[lon_col].isna()
                    invalid_count = invalid.sum()
                    if invalid_count > 0:
                        print(f"  无效坐标: {invalid_count}")
                else:
                    print("  未找到坐标列")
                    
                print()
                
            except Exception as e:
                print(f"  读取文件失败: {e}")
                print()
        else:
            print(f"文件不存在: {file_path}")
            print()
    
    print(f"总结:")
    print(f"  总的超出中国范围的坐标数: {total_out_of_bounds}")
    print()
    print("建议:")
    print("1. 过滤掉超出OSM数据覆盖范围的坐标点")
    print("2. 对于超出范围的点，使用Haversine距离计算作为备选")
    print("3. 或者下载更大范围的OSM数据（如asia-latest.osm.pbf）")

if __name__ == "__main__":
    analyze_coordinates()