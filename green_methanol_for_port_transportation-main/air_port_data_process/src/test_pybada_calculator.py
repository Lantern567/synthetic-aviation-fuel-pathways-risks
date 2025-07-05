#!/usr/bin/env python3
"""
测试修改后的pyBADA计算器
"""

import logging
from pybada_fuel_calculator import PyBADAFuelCalculator

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_pybada_calculator():
    """测试pyBADA计算器"""
    print("🧪 测试pyBADA计算器")
    print("=" * 50)
    
    try:
        # 创建计算器实例
        calculator = PyBADAFuelCalculator()
        print("✅ 计算器创建成功")
        
        # 测试几个航班
        test_flights = [
            {'aircraft_type': '波音737', 'distance_km': 1000, 'passengers': 150},
            {'aircraft_type': 'A320', 'distance_km': 1500, 'passengers': 160},
            {'aircraft_type': 'A319', 'distance_km': 800, 'passengers': 120},
            {'aircraft_type': 'B777', 'distance_km': 8000, 'passengers': 300},
            {'aircraft_type': 'ERJ-190', 'distance_km': 500, 'passengers': 90},
        ]
        
        print("\n📊 测试结果:")
        print("-" * 100)
        print(f"{'机型':<12} {'距离(km)':<10} {'乘客':<8} {'燃油(kg)':<12} {'CO2(kg)':<12} {'状态':<15} {'方法':<20}")
        print("-" * 100)
        
        for i, flight in enumerate(test_flights):
            print(f"\n🔍 测试航班 {i+1}: {flight['aircraft_type']}")
            
            try:
                result = calculator.calculate_single_flight(
                    flight['aircraft_type'], 
                    flight['distance_km'], 
                    flight['passengers']
                )
                
                status = "✅ 成功" if result['calculation_successful'] else "❌ 失败"
                method = result.get('calculation_method', 'N/A')
                
                print(f"{flight['aircraft_type']:<12} {flight['distance_km']:<10} {flight['passengers']:<8} "
                      f"{result['total_fuel_kg']:<12.1f} {result['co2_direct_kg']:<12.1f} "
                      f"{status:<15} {method:<20}")
                
                if result['calculation_successful']:
                    print(f"  └─ 每乘客CO2: {result['co2_per_passenger_kg']:.1f}kg")
                    print(f"  └─ 每公里CO2: {result['co2_per_km_kg']:.2f}kg")
                    print(f"  └─ NOx排放: {result['nox_kg']:.2f}kg")
                    print(f"  └─ H2O排放: {result['h2o_kg']:.1f}kg")
                else:
                    print(f"  └─ 错误: {result.get('error_message', 'N/A')}")
                    
            except Exception as e:
                print(f"❌ 测试航班 {i+1} 失败: {e}")
                print(f"{'ERROR':<12} {'ERROR':<10} {'ERROR':<8} {'ERROR':<12} {'ERROR':<12} {'❌ 异常':<15} {'ERROR':<20}")
        
        print("\n" + "=" * 50)
        print("🎯 测试完成！")
        
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_pybada_calculator() 