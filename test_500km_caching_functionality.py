#!/usr/bin/env python3
"""
测试500km过滤数据缓存功能
Test the 500km filtered data caching functionality
"""

import sys
import os
import time
import logging
from datetime import datetime

# 添加项目路径到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, "natural_gas_supply_chain_optimization", "src"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_cache_functionality():
    """测试缓存功能"""
    print("=" * 80)
    print("测试500km过滤数据缓存功能")
    print("=" * 80)
    
    try:
        # 导入必要的模块
        from natural_gas_supply_chain_optimization.src.data_cache_manager import cache_manager
        from natural_gas_supply_chain_optimization.src.cache_management_utility import CacheManagementUtility
        
        utility = CacheManagementUtility()
        
        print("\n1. 显示初始缓存状态")
        print("-" * 50)
        utility.show_cache_status()
        
        print("\n2. 清理现有缓存")
        print("-" * 50)
        utility.clear_cache()
        print("缓存已清理")
        
        print("\n3. 测试优化模型数据加载（将创建缓存）")
        print("-" * 50)
        
        # 导入优化模型
        from natural_gas_supply_chain_optimization.src.natural_gas_optimization_model import NaturalGasSupplyChainOptimizer
        
        # 创建优化器实例
        optimizer = NaturalGasSupplyChainOptimizer(
            time_horizon_weeks=1,
            use_graphhopper_routing=True
        )
        
        # 创建测试用的可再生能源数据
        import pandas as pd
        import numpy as np
        
        # 生成测试数据：几个在北京500km范围内的电站
        test_renewable_data = []
        
        # 北京附近的电站（在500km内）
        beijing_nearby_plants = [
            {"name": "北京太阳能电站1", "lat": 39.5, "lon": 116.2, "type": "solar_plant"},
            {"name": "天津风电场1", "lat": 39.1, "lon": 117.2, "type": "wind_farm"},
            {"name": "河北太阳能电站1", "lat": 38.8, "lon": 115.5, "type": "solar_plant"},
        ]
        
        # 远离北京的电站（在500km外，会被过滤掉）
        distant_plants = [
            {"name": "上海太阳能电站1", "lat": 31.2, "lon": 121.5, "type": "solar_plant"},
            {"name": "广州风电场1", "lat": 23.1, "lon": 113.3, "type": "wind_farm"},
        ]
        
        all_test_plants = beijing_nearby_plants + distant_plants
        
        # 为每个电站生成168小时（1周）的数据
        for plant_info in all_test_plants:
            for hour in range(168):
                # 生成模拟的发电数据
                if plant_info["type"] == "solar_plant":
                    # 太阳能：白天高，晚上低
                    base_power = 50 if 6 <= (hour % 24) <= 18 else 5
                    power_output = base_power + np.random.normal(0, 10)
                else:
                    # 风电：随机变化
                    power_output = 30 + np.random.normal(0, 15)
                
                power_output = max(0, power_output)  # 确保非负
                
                test_renewable_data.append({
                    'plant_name': plant_info["name"],
                    'latitude': plant_info["lat"],
                    'longitude': plant_info["lon"],
                    'type': plant_info["type"],
                    'capacity_mw': 100,
                    'power_output_mw': power_output,
                    'hour': hour
                })
        
        renewable_df = pd.DataFrame(test_renewable_data)
        
        print(f"生成测试数据: {len(renewable_df)} 条记录，{renewable_df['plant_name'].nunique()} 个电站")
        print(f"电站列表: {list(renewable_df['plant_name'].unique())}")
        
        # 创建测试机场数据
        airport_data = pd.DataFrame([
            {'airport_name': '北京首都国际机场', 'latitude': 40.0801, 'longitude': 116.5846, 'weekly_fuel_demand': 1000},
            {'airport_name': '天津滨海国际机场', 'latitude': 39.1244, 'longitude': 117.3460, 'weekly_fuel_demand': 500},
        ])
        
        print(f"机场数据: {len(airport_data)} 个机场")
        
        # 记录开始时间
        start_time = time.time()
        
        # 加载数据（第一次，会创建缓存）
        print("\n执行数据加载（第一次，会创建缓存）...")
        optimizer.load_data(renewable_df, airport_data)
        
        first_load_time = time.time() - start_time
        print(f"第一次数据加载耗时: {first_load_time:.2f} 秒")
        
        print("\n4. 显示缓存创建后的状态")
        print("-" * 50)
        utility.show_cache_status()
        
        print("\n5. 验证缓存有效性")
        print("-" * 50)
        utility.validate_cache()
        
        print("\n6. 测试缓存加载（第二次加载）")
        print("-" * 50)
        
        # 创建新的优化器实例来测试缓存加载
        optimizer2 = NaturalGasSupplyChainOptimizer(
            time_horizon_weeks=1,
            use_graphhopper_routing=True
        )
        
        # 记录第二次加载时间
        start_time = time.time()
        
        # 再次加载数据（第二次，应该使用缓存）
        print("执行数据加载（第二次，应该使用缓存）...")
        optimizer2.load_data(renewable_df, airport_data)
        
        second_load_time = time.time() - start_time
        print(f"第二次数据加载耗时: {second_load_time:.2f} 秒")
        
        # 计算性能改进
        if first_load_time > 0:
            speed_improvement = (first_load_time - second_load_time) / first_load_time * 100
            print(f"性能改进: {speed_improvement:.1f}%")
        
        print("\n7. 数据加载结果对比")
        print("-" * 50)
        
        print("第一次加载:")
        print(f"  可再生能源电站: {len(optimizer.locations)} 个")
        print(f"  LNG接收站: {len(optimizer.lng_terminals)} 个") 
        print(f"  天然气管道: {len(optimizer.ng_pipeline_sources)} 个")
        
        print("第二次加载:")
        print(f"  可再生能源电站: {len(optimizer2.locations)} 个")
        print(f"  LNG接收站: {len(optimizer2.lng_terminals)} 个")
        print(f"  天然气管道: {len(optimizer2.ng_pipeline_sources)} 个")
        
        # 验证数据一致性
        locations_match = len(optimizer.locations) == len(optimizer2.locations)
        lng_match = len(optimizer.lng_terminals) == len(optimizer2.lng_terminals)
        pipeline_match = len(optimizer.ng_pipeline_sources) == len(optimizer2.ng_pipeline_sources)
        
        print(f"\n数据一致性检查:")
        print(f"  可再生能源电站: {'OK' if locations_match else 'ERROR'}")
        print(f"  LNG接收站: {'OK' if lng_match else 'ERROR'}")
        print(f"  天然气管道: {'OK' if pipeline_match else 'ERROR'}")
        
        if locations_match and lng_match and pipeline_match:
            print("\n[SUCCESS] 缓存功能测试成功！数据完全一致")
        else:
            print("\n[ERROR] 缓存功能测试失败！数据不一致")
        
        print("\n8. 最终缓存状态")
        print("-" * 50)
        utility.show_cache_status()
        
    except ImportError as e:
        print(f"❌ 导入错误: {e}")
        print("请确保所有必要的模块都已正确安装和配置")
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

def main():
    """主函数"""
    test_cache_functionality()

if __name__ == "__main__":
    main()