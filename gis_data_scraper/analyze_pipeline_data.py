#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析天然气管道数据文件
检查是否能够完成可视化
"""

import pandas as pd
import json
from pathlib import Path

def analyze_pipeline_data():
    """分析天然气管道数据文件"""
    
    data_dir = Path("scraped_gis_data")
    
    print("=" * 60)
    print("天然气管道数据分析")
    print("=" * 60)
    
    # 1. 分析CSV文件
    print("\n1. 分析CSV文件:")
    csv_file = data_dir / "natural_gas_pipelines.csv"
    
    if csv_file.exists():
        try:
            df = pd.read_csv(csv_file)
            print(f"   ✓ CSV文件存在: {len(df)} 行数据")
            print(f"   ✓ 列数: {len(df.columns)}")
            print(f"   ✓ 列名: {list(df.columns)}")
            
            # 检查是否有几何信息
            geometry_columns = [col for col in df.columns if any(keyword in col.lower() 
                              for keyword in ['geometry', 'shape', 'coordinates', 'lat', 'lon', 'x', 'y'])]
            
            if geometry_columns:
                print(f"   ✓ 发现几何相关列: {geometry_columns}")
                
                # 查看几何数据样例
                for col in geometry_columns:
                    sample_data = df[col].dropna().head(3).tolist()
                    print(f"   ✓ {col} 样例数据: {sample_data}")
            else:
                print("   ⚠️  未发现明显的几何坐标列")
            
            # 查看前几行数据
            print(f"\n   前3行数据预览:")
            print(df.head(3).to_string())
            
        except Exception as e:
            print(f"   ✗ 读取CSV文件失败: {e}")
    else:
        print("   ✗ CSV文件不存在")
    
    # 2. 分析元数据文件
    print(f"\n2. 分析元数据文件:")
    metadata_files = [
        "natural_gas_pipelines_metadata.json",
        "natural_gas_pipelines_layer_0_metadata.json"
    ]
    
    for metadata_file in metadata_files:
        file_path = data_dir / metadata_file
        if file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                
                print(f"   ✓ {metadata_file} 存在")
                
                # 提取关键信息
                if 'geometryType' in metadata:
                    print(f"   ✓ 几何类型: {metadata['geometryType']}")
                
                if 'spatialReference' in metadata:
                    spatial_ref = metadata['spatialReference']
                    print(f"   ✓ 空间参考: WKID {spatial_ref.get('wkid', 'N/A')}")
                
                if 'fields' in metadata:
                    field_names = [field['name'] for field in metadata['fields']]
                    print(f"   ✓ 字段列表: {field_names}")
                
                if 'extent' in metadata:
                    extent = metadata['extent']
                    print(f"   ✓ 数据范围: X({extent.get('xmin', 'N/A')} - {extent.get('xmax', 'N/A')}), Y({extent.get('ymin', 'N/A')} - {extent.get('ymax', 'N/A')})")
                    
            except Exception as e:
                print(f"   ✗ 读取 {metadata_file} 失败: {e}")
        else:
            print(f"   ✗ {metadata_file} 不存在")
    
    # 3. 分析Excel文件
    print(f"\n3. 分析Excel文件:")
    excel_file = data_dir / "natural_gas_pipelines.xlsx"
    
    if excel_file.exists():
        try:
            df_excel = pd.read_excel(excel_file)
            print(f"   ✓ Excel文件存在: {len(df_excel)} 行数据")
            print(f"   ✓ 与CSV文件数据量比较: {'一致' if len(df_excel) == len(df) else '不一致'}")
            
        except Exception as e:
            print(f"   ✗ 读取Excel文件失败: {e}")
    else:
        print("   ✗ Excel文件不存在")
    
    # 4. 可视化可行性评估
    print(f"\n4. 可视化可行性评估:")
    
    has_geometry = False
    if csv_file.exists():
        try:
            df = pd.read_csv(csv_file)
            # 检查是否有几何信息的更深入分析
            if any(col for col in df.columns if 'geometry' in col.lower()):
                has_geometry = True
                print("   ✓ 发现几何信息列")
            elif 'Shape__Length' in df.columns:
                print("   ✓ 发现Shape__Length列，表明原始数据有几何信息")
                print("   ⚠️  但可能需要重新爬取GeoJSON格式数据")
            else:
                print("   ✗ 未发现几何信息")
                
        except:
            pass
    
    # 5. 建议
    print(f"\n5. 建议:")
    
    if has_geometry:
        print("   ✅ 现有文件可以直接用于可视化")
        print("   💡 建议使用pandas + geopandas读取数据进行可视化")
    else:
        print("   ⚠️  现有CSV/Excel文件缺乏几何坐标信息")
        print("   💡 建议方案:")
        print("      1. 重新爬取数据，保存为GeoJSON格式")
        print("      2. 或者使用ArcGIS REST API直接获取几何数据")
        print("      3. 或者根据管道端点信息重建几何线条")

if __name__ == "__main__":
    analyze_pipeline_data()
