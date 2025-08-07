#!/usr/bin/env python3
"""
测试修复后的pyBADA燃油消耗计算器
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../src'))

from pybada_fuel_calculator import PyBADAFuelCalculator

def test_pybada_calculator():
    """测试pyBADA计算器的基本功能"""
    print("=== 测试修复后的pyBADA计算器 ===")
    
    try:
        # 初始化计算器
        calculator = PyBADAFuelCalculator()
        print("✅ 计算器初始化成功")
        
        # 测试参数
        aircraft_type = "A320"
        distance_km = 800
        passengers = 150
        
        print(f"\n测试参数:")
        print(f"  机型: {aircraft_type}")
        print(f"  距离: {distance_km} km")
        print(f"  乘客: {passengers} 人")
        
        # 执行计算
        print(f"\n开始计算...")
        result = calculator.calculate_single_flight(aircraft_type, distance_km, passengers)
        
        # 显示结果
        print(f"\n=== 计算结果 ===")
        print(f"计算成功: {result.get('calculation_successful', False)}")
        print(f"计算方法: {result.get('calculation_method', 'N/A')}")
        
        if result.get('calculation_successful'):
            print(f"总燃油消耗: {result.get('total_fuel_kg', 0):.1f} kg")
            print(f"CO2直接排放: {result.get('co2_direct_kg', 0):.1f} kg")
            print(f"CO2当量排放: {result.get('co2_equivalent_kg', 0):.1f} kg")
            print(f"每旅客CO2排放: {result.get('co2_per_passenger_kg', 0):.2f} kg")
            print(f"每公里CO2排放: {result.get('co2_per_km_kg', 0):.3f} kg")
            print(f"总飞行时间: {result.get('total_time_minutes', 0):.1f} 分钟")
            print(f"环境评级: {result.get('environmental_impact_score', 'N/A')}")
            
            # 阶段性结果
            print(f"\n=== 各阶段结果 ===")
            print(f"爬升燃油: {result.get('climb_fuel_kg', 0):.1f} kg")
            print(f"巡航燃油: {result.get('cruise_fuel_kg', 0):.1f} kg")
            print(f"下降燃油: {result.get('descent_fuel_kg', 0):.1f} kg")
            
            print(f"爬升时间: {result.get('climb_time_minutes', 0):.1f} 分钟")
            print(f"巡航时间: {result.get('cruise_time_minutes', 0):.1f} 分钟")
            print(f"下降时间: {result.get('descent_time_minutes', 0):.1f} 分钟")
            
            print(f"\n✅ 测试成功完成!")
        else:
            print(f"❌ 计算失败: {result.get('error_message', '未知错误')}")
            
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_pybada_calculator() 