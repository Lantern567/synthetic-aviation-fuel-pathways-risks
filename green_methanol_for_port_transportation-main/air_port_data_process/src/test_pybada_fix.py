#!/usr/bin/env python3
"""
测试修复后的pyBADA燃油计算功能
"""

import pandas as pd
import logging
import sys
import os

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_pybada_calculator():
    """测试PyBADA计算器的各种情况"""
    print("=" * 60)
    print("测试修复后的pyBADA燃油计算功能")
    print("=" * 60)
    
    try:
        from pybada_fuel_calculator import PyBADAFuelCalculator, PYBADA_AVAILABLE
        
        if not PYBADA_AVAILABLE:
            print("❌ pyBADA库不可用，测试终止")
            return
        
        print("✅ 正在初始化PyBADA计算器...")
        calculator = PyBADAFuelCalculator()
        
        # 测试数据：包含原始航班数据中的各种机型
        test_flights = [
            {"aircraft_type": "空客320(中)", "distance_km": 1200, "passengers": 150},
            {"aircraft_type": "波音737(中)", "distance_km": 800, "passengers": 140},
            {"aircraft_type": "空客319(中)", "distance_km": 600, "passengers": 130},
            {"aircraft_type": "ERJ-190(中)", "distance_km": 500, "passengers": 90},
            {"aircraft_type": "庞巴迪CRJ900", "distance_km": 400, "passengers": 80},
            {"aircraft_type": "未知机型XYZ", "distance_km": 1000, "passengers": 160},  # 测试未知机型
        ]
        
        print(f"\n🧪 开始测试 {len(test_flights)} 个航班...")
        
        successful_calculations = 0
        failed_calculations = 0
        
        for i, flight in enumerate(test_flights, 1):
            print(f"\n--- 测试 {i}/{len(test_flights)} ---")
            print(f"机型: {flight['aircraft_type']}")
            print(f"距离: {flight['distance_km']}km")
            print(f"乘客: {flight['passengers']}人")
            
            try:
                result = calculator.calculate_single_flight(
                    aircraft_type=flight['aircraft_type'],
                    distance_km=flight['distance_km'],
                    passengers=flight['passengers']
                )
                
                if result and result.get('calculation_successful', False):
                    successful_calculations += 1
                    print(f"✅ 计算成功:")
                    print(f"   燃油消耗: {result['total_fuel_kg']:.1f} kg")
                    print(f"   CO2排放: {result['co2_direct_kg']:.1f} kg")
                    print(f"   每公里燃油: {result['fuel_per_km']:.2f} kg/km")
                    print(f"   每乘客CO2: {result['co2_per_passenger_kg']:.1f} kg/人")
                    print(f"   计算方法: {result.get('calculation_method', 'N/A')}")
                    print(f"   使用TCL: {result.get('used_tcl', False)}")
                    if 'bada_code_used' in result:
                        print(f"   BADA代码: {result['bada_code_used']}")
                else:
                    failed_calculations += 1
                    print("❌ 计算失败")
                    
            except Exception as e:
                failed_calculations += 1
                print(f"❌ 计算异常: {e}")
        
        # 总结测试结果
        print(f"\n" + "=" * 60)
        print("测试结果总结:")
        print(f"✅ 成功: {successful_calculations}/{len(test_flights)}")
        print(f"❌ 失败: {failed_calculations}/{len(test_flights)}")
        print(f"成功率: {successful_calculations/len(test_flights)*100:.1f}%")
        
        if successful_calculations > 0:
            print("🎉 修复成功！pyBADA可以正常计算燃油消耗了。")
        else:
            print("😞 修复未完全成功，仍有问题需要解决。")
            
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

def test_batch_processing():
    """测试批量处理功能"""
    print(f"\n" + "=" * 60)
    print("测试批量处理功能")
    print("=" * 60)
    
    try:
        from pybada_fuel_calculator import process_flight_data_with_pybada
        
        # 创建测试数据
        test_data = pd.DataFrame([
            {"aircraft_type": "空客320(中)", "distance_km": 1200, "passengers": 150},
            {"aircraft_type": "波音737(中)", "distance_km": 800, "passengers": 140},
            {"aircraft_type": "ERJ-190(中)", "distance_km": 500, "passengers": 90},
        ])
        
        print(f"📊 处理 {len(test_data)} 条测试数据...")
        
        results = process_flight_data_with_pybada(test_data)
        
        if results is not None and not results.empty:
            successful = len(results[results.get('calculation_successful', False) == True])
            print(f"✅ 批量处理完成:")
            print(f"   总记录数: {len(results)}")
            print(f"   成功计算: {successful}")
            print(f"   成功率: {successful/len(results)*100:.1f}%")
            
            # 显示部分结果
            if 'total_fuel_kg' in results.columns:
                print(f"   平均燃油消耗: {results['total_fuel_kg'].mean():.1f} kg")
            if 'co2_direct_kg' in results.columns:
                print(f"   平均CO2排放: {results['co2_direct_kg'].mean():.1f} kg")
        else:
            print("❌ 批量处理失败")
            
    except Exception as e:
        print(f"❌ 批量处理测试失败: {e}")

if __name__ == "__main__":
    # 运行测试
    test_pybada_calculator()
    test_batch_processing()
    
    print(f"\n" + "=" * 60)
    print("测试完成")
    print("=" * 60) 