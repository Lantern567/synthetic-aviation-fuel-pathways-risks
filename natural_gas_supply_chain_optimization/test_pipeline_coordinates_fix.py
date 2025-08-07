"""
测试天然气管道坐标修复效果
验证新的坐标数据是否正确应用到优化模型中
"""

import sys
import os
import pandas as pd
import numpy as np
from pathlib import Path

# 添加项目路径到系统路径
project_root = Path(__file__).parent
sys.path.append(str(project_root / "src"))

from natural_gas_optimization_model import NaturalGasSupplyChainOptimizer

def test_pipeline_coordinates():
    """测试管道坐标数据"""
    
    print("=== 天然气管道坐标修复测试 ===")
    
    # 创建模型实例
    try:
        model = NaturalGasSupplyChainOptimizer()
        print("✓ 模型创建成功")
    except Exception as e:
        print(f"✗ 模型创建失败: {e}")
        return False
    
    # 检查locations中的管道坐标
    pipeline_locations = {k: v for k, v in model.locations.items() if v.get('type') == 'ng_pipeline'}
    
    print(f"\n总共加载了 {len(pipeline_locations)} 个天然气管道位置")
    
    # 检查坐标分布
    unique_coords = set()
    valid_coords = 0
    default_coords = 0
    
    for location_name, location_data in pipeline_locations.items():
        lat = location_data['latitude']
        lon = location_data['longitude']
        
        # 检查是否是默认坐标
        if lat == 39.0 and lon == 116.0:
            default_coords += 1
        else:
            valid_coords += 1
            unique_coords.add((lat, lon))
    
    print(f"\n坐标统计:")
    print(f"使用真实坐标: {valid_coords}")
    print(f"使用默认坐标: {default_coords}")
    print(f"唯一坐标点数: {len(unique_coords)}")
    print(f"坐标覆盖率: {valid_coords/(valid_coords+default_coords)*100:.1f}%")
    
    # 显示前10个管道的坐标信息
    print(f"\n前10个管道的坐标信息:")
    print("-" * 100)
    print(f"{'管道名称':<50} {'纬度':<12} {'经度':<12} {'状态'}")
    print("-" * 100)
    
    count = 0
    for location_name, location_data in pipeline_locations.items():
        if count >= 10:
            break
        
        lat = location_data['latitude']
        lon = location_data['longitude']
        pipeline_name = location_data.get('pipeline_name', 'Unknown')
        
        status = "真实坐标" if not (lat == 39.0 and lon == 116.0) else "默认坐标"
        
        print(f"{pipeline_name[:48]:<50} {lat:<12.6f} {lon:<12.6f} {status}")
        count += 1
    
    # 检查管道数据文件
    print(f"\n=== 检查管道数据源文件 ===")
    try:
        # 检查新文件
        new_file_path = project_root / "data" / "integrated_gas_pipeline_price_data_with_coords.csv"
        if new_file_path.exists():
            df = pd.read_csv(new_file_path)
            total_pipelines = len(df)
            with_lat_lon = df['lat'].notna().sum()
            
            print(f"✓ 新坐标文件存在: {new_file_path}")
            print(f"  总管道数: {total_pipelines}")
            print(f"  有坐标信息: {with_lat_lon}")
            print(f"  坐标覆盖率: {with_lat_lon/total_pipelines*100:.1f}%")
            
            # 显示坐标范围
            valid_coords_df = df[df['lat'].notna()]
            if len(valid_coords_df) > 0:
                print(f"  纬度范围: {valid_coords_df['lat'].min():.2f} ~ {valid_coords_df['lat'].max():.2f}")
                print(f"  经度范围: {valid_coords_df['lon'].min():.2f} ~ {valid_coords_df['lon'].max():.2f}")
        else:
            print(f"✗ 新坐标文件不存在: {new_file_path}")
            
    except Exception as e:
        print(f"✗ 读取坐标文件失败: {e}")
    
    # 测试优化模型功能
    print(f"\n=== 测试模型功能 ===")
    try:
        # 尝试生成管道输出文件
        model._generate_ng_pipeline_results()
        print("✓ 管道结果生成成功")
        
        # 检查输出文件
        results_dir = project_root / "results"
        ng_files = list(results_dir.glob("ng_pipelines_*.csv"))
        if ng_files:
            latest_file = max(ng_files, key=lambda x: x.stat().st_mtime)
            print(f"✓ 找到管道结果文件: {latest_file.name}")
            
            # 检查输出文件中的坐标
            ng_df = pd.read_csv(latest_file)
            unique_output_coords = ng_df[['纬度', '经度']].drop_duplicates()
            default_in_output = ((ng_df['纬度'] == 39.0) & (ng_df['经度'] == 116.0)).sum()
            
            print(f"  输出文件中唯一坐标数: {len(unique_output_coords)}")
            print(f"  输出文件中默认坐标数: {default_in_output}")
            print(f"  输出文件坐标改善: {'是' if default_in_output < len(ng_df) else '否'}")
        else:
            print("✗ 未找到管道结果文件")
            
    except Exception as e:
        print(f"✗ 模型功能测试失败: {e}")
    
    # 总结
    print(f"\n=== 测试总结 ===")
    if valid_coords > default_coords:
        print("✓ 坐标修复成功！大部分管道现在使用真实坐标")
        return True
    elif valid_coords > 0:
        print("⚠ 坐标部分修复，仍有管道使用默认坐标")
        return True
    else:
        print("✗ 坐标修复失败，所有管道仍使用默认坐标")
        return False

if __name__ == "__main__":
    success = test_pipeline_coordinates()
    if success:
        print("\n天然气管道坐标修复测试通过！")
    else:
        print("\n天然气管道坐标修复测试失败！")