#!/usr/bin/env python3
"""
测试多个机型的pyBADA燃油消耗计算器
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../src'))

from pybada_fuel_calculator import PyBADAFuelCalculator

def test_multiple_aircraft():
    """测试多个机型的燃油计算"""
    print("=== 测试多个机型的pyBADA计算器 ===")
    
    # 测试机型列表
    test_cases = [
        {"aircraft": "A320", "distance": 800, "passengers": 150},
        {"aircraft": "A319", "distance": 600, "passengers": 120},
        {"aircraft": "A321", "distance": 1000, "passengers": 180},
        {"aircraft": "B737", "distance": 700, "passengers": 140},
        {"aircraft": "B738", "distance": 900, "passengers": 160},
        {"aircraft": "B777", "distance": 2000, "passengers": 300},
        {"aircraft": "E190", "distance": 500, "passengers": 90},
    ]
    
    try:
        # 初始化计算器
        calculator = PyBADAFuelCalculator()
        print("✅ 计算器初始化成功\n")
        
        results = []
        
        for i, test_case in enumerate(test_cases, 1):
            aircraft = test_case["aircraft"]
            distance = test_case["distance"]
            passengers = test_case["passengers"]
            
            print(f"[{i}/{len(test_cases)}] 测试 {aircraft}: {distance}km, {passengers}人")
            
            try:
                result = calculator.calculate_single_flight(aircraft, distance, passengers)
                
                if result.get('success', False):
                    fuel_kg = result.get('total_fuel_kg', 0)
                    co2_kg = result.get('co2_direct_kg', 0)
                    time_min = result.get('total_time_minutes', 0)
                    method = result.get('calculation_method', 'unknown')
                    
                    print(f"  ✅ 成功 ({method})")
                    print(f"     燃油: {fuel_kg:.1f} kg")
                    print(f"     CO2: {co2_kg:.1f} kg")
                    print(f"     时间: {time_min:.1f} 分钟")
                    
                    results.append({
                        'aircraft': aircraft,
                        'distance': distance,
                        'passengers': passengers,
                        'fuel_kg': fuel_kg,
                        'co2_kg': co2_kg,
                        'time_min': time_min,
                        'method': method,
                        'success': True
                    })
                else:
                    print(f"  ❌ 失败: {result.get('error', 'Unknown error')}")
                    results.append({
                        'aircraft': aircraft,
                        'success': False,
                        'error': result.get('error', 'Unknown error')
                    })
                    
            except Exception as e:
                print(f"  ❌ 异常: {e}")
                results.append({
                    'aircraft': aircraft,
                    'success': False,
                    'error': str(e)
                })
            
            print()
        
        # 汇总结果
        print("=== 测试汇总 ===")
        successful = [r for r in results if r.get('success', False)]
        failed = [r for r in results if not r.get('success', False)]
        
        print(f"成功: {len(successful)}/{len(results)} 个测试")
        print(f"失败: {len(failed)}/{len(results)} 个测试")
        
        if successful:
            print("\n成功的测试:")
            for result in successful:
                print(f"  {result['aircraft']}: {result['fuel_kg']:.1f}kg燃油, {result['co2_kg']:.1f}kg CO2 ({result['method']})")
        
        if failed:
            print("\n失败的测试:")
            for result in failed:
                print(f"  {result['aircraft']}: {result['error']}")
        
        # 计算平均效率
        if successful:
            print("\n=== 效率分析 ===")
            for result in successful:
                fuel_per_km = result['fuel_kg'] / result['distance']
                fuel_per_passenger = result['fuel_kg'] / result['passengers']
                co2_per_passenger = result['co2_kg'] / result['passengers']
                
                print(f"{result['aircraft']}:")
                print(f"  燃油效率: {fuel_per_km:.2f} kg/km")
                print(f"  人均燃油: {fuel_per_passenger:.1f} kg/人")
                print(f"  人均CO2: {co2_per_passenger:.1f} kg/人")
        
        return len(successful) == len(results)
        
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_multiple_aircraft()
    if success:
        print("\n🎉 所有测试通过!")
    else:
        print("\n⚠️  部分测试失败") 