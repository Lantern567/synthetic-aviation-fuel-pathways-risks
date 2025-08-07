#!/usr/bin/env python3
"""
检查GraphHopper服务状态
"""

import requests
import sys
import time

def check_service_status():
    """检查服务状态"""
    print("检查GraphHopper服务状态...")
    
    try:
        # 检查服务健康状态
        health_url = "http://localhost:8989/health"
        print(f"尝试连接: {health_url}")
        
        response = requests.get(health_url, timeout=5)
        
        if response.status_code == 200:
            print("✓ GraphHopper服务运行正常")
            return True
        else:
            print(f"✗ 服务返回异常状态码: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("✗ 无法连接到GraphHopper服务")
        print("  服务可能未启动")
        return False
    except requests.exceptions.Timeout:
        print("✗ 连接超时")
        return False
    except Exception as e:
        print(f"✗ 连接失败: {e}")
        return False

def test_route_calculation():
    """测试路径计算"""
    print("\n测试路径计算功能...")
    
    try:
        route_url = "http://localhost:8989/route"
        params = {
            'point': ['39.9042,116.4074', '31.2304,121.4737'],  # 北京到上海
            'vehicle': 'car'
        }
        
        response = requests.get(route_url, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            if 'paths' in data and len(data['paths']) > 0:
                path = data['paths'][0]
                distance_km = path.get('distance', 0) / 1000
                time_hours = path.get('time', 0) / (1000 * 3600)
                
                print("✓ 路径计算成功")
                print(f"  北京到上海距离: {distance_km:.1f} 公里")
                print(f"  预估时间: {time_hours:.1f} 小时")
                return True
            else:
                print("✗ 路径计算返回空结果")
                return False
        else:
            print(f"✗ 路径计算失败，状态码: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"✗ 路径计算测试失败: {e}")
        return False

def main():
    """主函数"""
    print("GraphHopper服务状态检查")
    print("=" * 40)
    
    # 检查服务运行状态
    service_ok = check_service_status()
    
    if service_ok:
        # 测试路径计算功能
        route_ok = test_route_calculation()
        
        print("\n" + "=" * 40)
        if route_ok:
            print("🎉 GraphHopper服务完全正常！")
            print("   可以正常使用路径规划功能")
        else:
            print("⚠️  服务运行但路径计算有问题")
    else:
        print("\n" + "=" * 40)
        print("❌ GraphHopper服务未运行")
        print("\n启动服务的方法:")
        print("1. 双击运行 start_graphhopper_service.bat")
        print("2. 或在命令提示符中运行:")
        print("   java -jar natural_gas_supply_chain_optimization/data/graphhopper-web-10.2.jar server config.yml")
    
    print("=" * 40)

if __name__ == "__main__":
    main()