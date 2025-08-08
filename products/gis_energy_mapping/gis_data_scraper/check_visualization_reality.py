#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查天然气管道可视化的真实情况
"""

import pandas as pd
from pathlib import Path
import os

def check_visualization_reality():
    """检查可视化的真实情况"""
    
    print("=" * 60)
    print("天然气管道可视化真实性检查")
    print("=" * 60)
    
    # 1. 检查CSV数据
    csv_file = Path("scraped_gis_data/natural_gas_pipelines.csv")
    if csv_file.exists():
        df = pd.read_csv(csv_file)
        print(f"1. CSV数据检查:")
        print(f"   ✓ 数据行数: {len(df)}")
        print(f"   ✓ 列名: {list(df.columns)}")
        
        # 检查是否有几何相关的数据
        has_coords = False
        for col in df.columns:
            if any(keyword in col.lower() for keyword in ['geometry', 'coordinates', 'x', 'y', 'lat', 'lon', 'wkt']):
                print(f"   ✓ 发现几何列: {col}")
                sample = df[col].dropna().head(3).tolist()
                print(f"   ✓ 样例数据: {sample}")
                has_coords = True
        
        if not has_coords:
            print(f"   ❌ 未发现坐标数据列")
            print(f"   ❌ 仅有属性数据，无法绘制管道线条")
    
    # 2. 检查可视化图片大小
    print(f"\n2. 可视化图片检查:")
    viz_dir = Path("visualization_results")
    if viz_dir.exists():
        pipeline_images = [
            "01_能源基础设施总览图.png",
            "05_能源管道网络分布图.png", 
            "08_天然气产业链专题分析.png"
        ]
        
        for img_name in pipeline_images:
            img_path = viz_dir / img_name
            if img_path.exists():
                size_mb = img_path.stat().st_size / (1024 * 1024)
                print(f"   ✓ {img_name}: {size_mb:.2f} MB")
            else:
                print(f"   ❌ {img_name}: 不存在")
    
    # 3. 真相揭示
    print(f"\n3. 真相分析:")
    print(f"   🔍 如果CSV文件没有坐标数据:")
    print(f"      - 可视化图片可能显示了空白或错误的内容")
    print(f"      - 管道线条无法正确绘制") 
    print(f"      - 需要重新爬取包含几何信息的数据")
    
    print(f"\n4. 解决方案:")
    print(f"   💡 需要重新爬取数据，确保包含几何坐标:")
    print(f"      - 使用GeoJSON格式")
    print(f"      - 或者直接从ArcGIS REST API获取几何数据")
    print(f"      - 确保返回geometry字段")

if __name__ == "__main__":
    check_visualization_reality()
