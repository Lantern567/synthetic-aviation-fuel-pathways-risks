"""
GraphHopper路径规划使用示例
演示如何使用本地OSM数据进行路径规划
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from graphhopper_routing_engine import GraphHopperRoutingEngine, GraphHopperDistanceCalculator
from natural_gas_optimization_model import NaturalGasSupplyChainOptimizer

def basic_graphhopper_example():
    """基本GraphHopper路径规划示例"""
    print("=" * 60)
    print("GraphHopper路径规划基本示例")
    print("=" * 60)
    
    # 创建GraphHopper路径规划引擎
    engine = GraphHopperRoutingEngine(
        osm_pbf_path="data/china-latest.osm.pbf",  # 您的OSM数据文件路径
        graphhopper_host="localhost",
        graphhopper_port=8989,
        enable_cache=True
    )
    
    print(f"GraphHopper服务地址: {engine.base_url}")
    print(f"OSM数据文件: {engine.osm_pbf_path}")
    print(f"缓存目录: {engine.cache_dir}")
    
    # 测试坐标（北京和上海）
    beijing_lat, beijing_lon = 39.9042, 116.4074
    shanghai_lat, shanghai_lon = 31.2304, 121.4737
    
    print(f"\n计算路径: 北京({beijing_lat}, {beijing_lon}) -> 上海({shanghai_lat}, {shanghai_lon})")
    
    # 计算路径距离
    result = engine.calculate_route_distance(
        beijing_lat, beijing_lon,
        shanghai_lat, shanghai_lon,
        vehicle="car",
        include_route_geometry=True
    )
    
    print(f"路径计算结果:")
    print(f"  - 是否找到路径: {result['route_found']}")
    print(f"  - 距离: {result.get('distance_km', 'N/A')} 公里")
    print(f"  - 行驶时间: {result.get('time_hours', 'N/A')} 小时")
    print(f"  - 计算方法: {result.get('method', 'N/A')}")
    
    if result.get('route_coordinates'):
        print(f"  - 路径坐标点数: {len(result['route_coordinates'])}")
        print(f"  - 起点坐标: {result['route_coordinates'][0]}")
        print(f"  - 终点坐标: {result['route_coordinates'][-1]}")
    
    # 保存路径到文件
    if result['route_found']:
        engine.save_route_to_file(result, "beijing_to_shanghai_route.json")
        print(f"  - 路径已保存到文件")
    
    # 显示统计信息
    stats = engine.get_stats()
    print(f"\n统计信息:")
    for key, value in stats.items():
        print(f"  - {key}: {value}")
    
    return engine

def distance_matrix_example():
    """距离矩阵计算示例"""
    print("\n" + "=" * 60)
    print("距离矩阵计算示例")
    print("=" * 60)
    
    engine = GraphHopperRoutingEngine(
        osm_pbf_path="data/china-latest.osm.pbf",
        enable_cache=True
    )
    
    # 定义多个城市坐标
    locations = [
        (39.9042, 116.4074),  # 北京
        (31.2304, 121.4737),  # 上海
        (23.1291, 113.2644),  # 广州
        (30.5728, 104.0668)   # 成都
    ]
    location_names = ["北京", "上海", "广州", "成都"]
    
    print(f"计算 {len(locations)} 个城市之间的距离矩阵...")
    
    # 计算距离矩阵
    distance_matrix = engine.calculate_distance_matrix(
        locations, 
        location_names, 
        vehicle="car"
    )
    
    print(f"\n距离矩阵 (单位: 公里):")
    print(distance_matrix.round(1))
    
    # 找出最短和最长距离
    print(f"\n距离统计:")
    for i, city1 in enumerate(location_names):
        for j, city2 in enumerate(location_names):
            if i < j:  # 避免重复
                distance = distance_matrix.loc[city1, city2]
                print(f"  {city1} -> {city2}: {distance:.1f} 公里")
    
    return distance_matrix

def optimization_model_example():
    """使用GraphHopper的优化模型示例"""
    print("\n" + "=" * 60)
    print("天然气供应链优化模型示例")
    print("=" * 60)
    
    # 创建优化器（使用GraphHopper路径规划）
    optimizer = NaturalGasSupplyChainOptimizer(
        time_horizon_weeks=1,
        use_graphhopper_routing=True,
        osm_pbf_path="data/china-latest.osm.pbf",
        graphhopper_host="localhost",
        graphhopper_port=8989,
        max_transport_distance_km=1000.0,
        use_routing_for_short_distance=True
    )
    
    print(f"优化器配置:")
    print(f"  - GraphHopper路径规划: {optimizer.use_graphhopper_routing}")
    print(f"  - OSM数据文件: {optimizer.osm_pbf_path}")
    print(f"  - GraphHopper服务: {optimizer.graphhopper_host}:{optimizer.graphhopper_port}")
    print(f"  - 最大运输距离: {optimizer.max_transport_distance_km} 公里")
    
    # 创建示例数据
    print(f"\n创建示例数据...")
    
    # 可再生能源数据
    hours = 24
    renewable_data = pd.DataFrame({
        'hour': range(hours),
        'solar_power_mw': np.random.uniform(0, 100, hours),
        'wind_power_mw': np.random.uniform(0, 80, hours),
        'location': ['Beijing'] * hours
    })
    
    # 机场数据
    airport_data = pd.DataFrame({
        'airport_code': ['PEK', 'PVG', 'CAN'],
        'airport_name': ['Beijing Capital', 'Shanghai Pudong', 'Guangzhou Baiyun'],
        'latitude': [40.0801, 31.1443, 23.3924],
        'longitude': [116.5844, 121.8083, 113.2988],
        'weekly_fuel_demand_tons': [1000, 1200, 800]
    })
    
    print(f"  - 可再生能源数据: {len(renewable_data)} 小时")
    print(f"  - 机场数据: {len(airport_data)} 个机场")
    
    # 加载数据到优化器
    try:
        print(f"\n加载数据到优化器...")
        optimizer.load_data(renewable_data, airport_data)
        
        print(f"数据加载完成:")
        print(f"  - 生产地点: {len(optimizer.locations)}")
        print(f"  - 机场: {len(optimizer.airports)}")
        print(f"  - 距离统计: {optimizer.distance_stats}")
        
    except Exception as e:
        print(f"数据加载过程中的错误（这在测试环境中是正常的）: {e}")
    
    return optimizer

def distance_calculator_example():
    """距离计算器使用示例"""
    print("\n" + "=" * 60)
    print("距离计算器使用示例")
    print("=" * 60)
    
    # 创建距离计算器
    routing_engine = GraphHopperRoutingEngine(
        osm_pbf_path="data/china-latest.osm.pbf"
    )
    calculator = GraphHopperDistanceCalculator(routing_engine)
    
    # 测试坐标
    beijing_lat, beijing_lon = 39.9042, 116.4074
    shanghai_lat, shanghai_lon = 31.2304, 121.4737
    
    print(f"测试坐标: 北京({beijing_lat}, {beijing_lon}) -> 上海({shanghai_lat}, {shanghai_lon})")
    
    # 不同计算方法的比较
    methods = ["graphhopper", "haversine", "euclidean"]
    
    print(f"\n不同计算方法结果比较:")
    for method in methods:
        try:
            distance = calculator.calculate_distance(
                beijing_lat, beijing_lon,
                shanghai_lat, shanghai_lon,
                method=method
            )
            print(f"  - {method:12}: {distance:.1f} 公里")
        except Exception as e:
            print(f"  - {method:12}: 计算失败 ({e})")
    
    return calculator

def performance_test():
    """性能测试示例"""
    print("\n" + "=" * 60)
    print("性能测试示例")
    print("=" * 60)
    
    engine = GraphHopperRoutingEngine(
        osm_pbf_path="data/china-latest.osm.pbf",
        enable_cache=True
    )
    
    # 测试坐标列表
    test_coordinates = [
        (39.9042, 116.4074),  # 北京
        (31.2304, 121.4737),  # 上海
        (23.1291, 113.2644),  # 广州
        (30.5728, 104.0668),  # 成都
        (22.3193, 114.1694)   # 香港
    ]
    
    print(f"进行 {len(test_coordinates)} 个城市之间的距离计算性能测试...")
    
    start_time = datetime.now()
    total_calculations = 0
    successful_calculations = 0
    
    for i, (lat1, lon1) in enumerate(test_coordinates):
        for j, (lat2, lon2) in enumerate(test_coordinates):
            if i != j:  # 不计算自身到自身的距离
                total_calculations += 1
                try:
                    result = engine.calculate_route_distance(
                        lat1, lon1, lat2, lon2,
                        vehicle="car",
                        include_route_geometry=False  # 不包含路径几何信息以提高性能
                    )
                    if result['route_found']:
                        successful_calculations += 1
                except Exception as e:
                    print(f"计算失败: {e}")
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    print(f"\n性能测试结果:")
    print(f"  - 总计算次数: {total_calculations}")
    print(f"  - 成功计算次数: {successful_calculations}")
    print(f"  - 成功率: {successful_calculations/total_calculations*100:.1f}%")
    print(f"  - 总耗时: {duration:.2f} 秒")
    print(f"  - 平均每次计算: {duration/total_calculations:.3f} 秒")
    
    # 显示最终统计
    stats = engine.get_stats()
    print(f"\n引擎统计:")
    for key, value in stats.items():
        print(f"  - {key}: {value}")

def main():
    """主函数 - 运行所有示例"""
    print("GraphHopper路径规划使用示例")
    print("注意：这些示例需要GraphHopper服务正在运行")
    print("请确保:")
    print("1. GraphHopper服务已启动并监听localhost:8989")
    print("2. OSM数据文件存在于指定路径")
    print("3. 安装了所有必要的依赖包")
    
    try:
        # 基本示例
        engine = basic_graphhopper_example()
        
        # 距离矩阵示例
        distance_matrix = distance_matrix_example()
        
        # 优化模型示例
        optimizer = optimization_model_example()
        
        # 距离计算器示例
        calculator = distance_calculator_example()
        
        # 性能测试
        performance_test()
        
        print("\n" + "=" * 60)
        print("所有示例运行完成！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n示例运行过程中发生错误: {e}")
        print("这可能是因为:")
        print("1. GraphHopper服务未运行")
        print("2. OSM数据文件不存在")
        print("3. 网络连接问题")
        print("4. 依赖包未正确安装")

if __name__ == "__main__":
    main()