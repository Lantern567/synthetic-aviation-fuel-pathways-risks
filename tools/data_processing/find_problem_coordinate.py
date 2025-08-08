#!/usr/bin/env python3
"""
查找特定的问题坐标来源
"""

import pandas as pd
import numpy as np
import os
import glob

def find_coordinate(target_lat=21.49594028857143, target_lon=95.78582466785714):
    print(f"查找问题坐标: {target_lat}, {target_lon}")
    print("(这个坐标位于缅甸北部，超出中国OSM数据范围)")
    print()
    
    # 搜索所有CSV文件
    csv_files = glob.glob("**/*.csv", recursive=True)
    
    tolerance = 0.001  # 坐标匹配容差
    
    for file_path in csv_files:
        if 'cache' in file_path or '__pycache__' in file_path:
            continue
            
        try:
            df = pd.read_csv(file_path)
            
            # 查找可能的坐标列
            possible_lat_cols = [col for col in df.columns if any(keyword in col.lower() for keyword in ['lat', '纬度', 'latitude'])]
            possible_lon_cols = [col for col in df.columns if any(keyword in col.lower() for keyword in ['lon', 'lng', '经度', 'longitude'])]
            
            for lat_col in possible_lat_cols:
                for lon_col in possible_lon_cols:
                    try:
                        # 查找匹配的坐标
                        lat_match = (df[lat_col] - target_lat).abs() < tolerance
                        lon_match = (df[lon_col] - target_lon).abs() < tolerance
                        
                        matches = lat_match & lon_match
                        
                        if matches.any():
                            print(f"找到匹配坐标在文件: {file_path}")
                            print(f"坐标列: {lat_col}, {lon_col}")
                            matching_rows = df[matches]
                            print(f"匹配行数: {len(matching_rows)}")
                            print("匹配的数据:")
                            print(matching_rows.to_string())
                            print()
                    except:
                        continue
        except Exception as e:
            continue
    
    print("查找完成。")
    print()
    print("解决方案:")
    print("1. 在代码中添加坐标范围验证")
    print("2. 过滤掉超出中国范围的坐标")
    print("3. 对无法路径规划的点使用Haversine距离估算")

if __name__ == "__main__":
    find_coordinate()