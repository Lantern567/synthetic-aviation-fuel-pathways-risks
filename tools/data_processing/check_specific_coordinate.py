#!/usr/bin/env python3
"""
检查特定坐标点的情况
"""

import requests
from natural_gas_supply_chain_optimization.src.natural_gas_optimization_model import calculate_distance_km

def check_coordinate():
    # 问题坐标
    problem_lat = 41.811705224
    problem_lon = 117.17910677
    
    # 计算到北京的距离
    beijing_lat = 39.9042
    beijing_lon = 116.4074
    
    distance = calculate_distance_km(problem_lat, problem_lon, beijing_lat, beijing_lon)
    
    print(f"问题坐标: {problem_lat}, {problem_lon}")
    print(f"距离北京: {distance:.1f} km")
    print(f"是否在500km范围内: {'是' if distance <= 500 else '否'}")
    print()
    
    # 测试GraphHopper是否能找到这个点
    try:
        # 测试最近点查询
        nearest_url = "http://localhost:8989/nearest"
        params = {
            'point': f'{problem_lat},{problem_lon}',
            'profile': 'truck'
        }
        
        response = requests.get(nearest_url, params=params, timeout=10)
        print("GraphHopper最近点查询结果:")
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if 'coordinates' in data and data['coordinates']:
                coords = data['coordinates']
                print(f"找到最近的道路点: {coords[1]}, {coords[0]}")
                nearest_distance = calculate_distance_km(problem_lat, problem_lon, coords[1], coords[0])
                print(f"到最近道路的距离: {nearest_distance*1000:.0f} 米")
            else:
                print("未找到最近的道路点")
        else:
            print(f"查询失败: {response.text}")
            
    except Exception as e:
        print(f"GraphHopper查询失败: {e}")

if __name__ == "__main__":
    check_coordinate()