"""
燃油消耗计算模块的单元测试
"""

import unittest
import sys
import os

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))

from aircraft_mapping import get_icao_code, get_aircraft_capacity, calculate_load_factor
from fuel_consumption_calculator import estimate_fuel_consumption_simple

class TestFuelCalculator(unittest.TestCase):
    
    def test_aircraft_mapping(self):
        """测试机型映射功能"""
        # 测试中文机型到ICAO代码的转换
        self.assertEqual(get_icao_code('波音737(中)'), 'B737')
        self.assertEqual(get_icao_code('空客320(中)'), 'A320')
        self.assertEqual(get_icao_code('不存在的机型'), 'B737')  # 默认值
        
    def test_aircraft_capacity(self):
        """测试机型载客量获取"""
        self.assertEqual(get_aircraft_capacity('B737'), 160)
        self.assertEqual(get_aircraft_capacity('A380'), 550)
        self.assertEqual(get_aircraft_capacity('未知机型'), 160)  # 默认值
        
    def test_load_factor_calculation(self):
        """测试载客率计算"""
        # 测试正常载客率
        load_factor = calculate_load_factor(80, 'B737')  # 80/160 = 0.5
        self.assertAlmostEqual(load_factor, 0.5, places=2)
        
        # 测试超载情况
        load_factor = calculate_load_factor(200, 'B737')  # 200/160 > 1, 应该被限制为1.0
        self.assertEqual(load_factor, 1.0)
        
    def test_fuel_consumption_calculation(self):
        """测试燃油消耗计算"""
        # 测试短距离航班
        fuel = estimate_fuel_consumption_simple(500, 'B737', 150)
        self.assertGreater(fuel, 0)
        self.assertIsInstance(fuel, float)
        
        # 测试长距离航班
        fuel_long = estimate_fuel_consumption_simple(2000, 'B737', 150)
        self.assertGreater(fuel_long, fuel)  # 长距离应该消耗更多燃油
        
        # 测试不同机型
        fuel_a380 = estimate_fuel_consumption_simple(1000, 'A380', 400)
        fuel_b737 = estimate_fuel_consumption_simple(1000, 'B737', 150)
        self.assertGreater(fuel_a380, fuel_b737)  # A380应该比B737消耗更多燃油
        
    def test_edge_cases(self):
        """测试边界情况"""
        # 测试零距离
        fuel = estimate_fuel_consumption_simple(0, 'B737', 100)
        self.assertEqual(fuel, 0)
        
        # 测试零载客
        fuel = estimate_fuel_consumption_simple(1000, 'B737', 0)
        self.assertGreater(fuel, 0)  # 即使零载客也要消耗燃油
        
        # 测试极大距离
        fuel = estimate_fuel_consumption_simple(15000, 'B777', 300)
        self.assertGreater(fuel, 0)
        
def run_sample_calculation():
    """运行样例计算以验证整体功能"""
    print("\n=== 样例计算测试 ===")
    
    # 测试几个典型航班
    test_flights = [
        {'机型': '波音737(中)', '距离': 1200, '载客': 150, '描述': '国内中程航班'},
        {'机型': '空客320(中)', '距离': 800, '载客': 140, '描述': '国内短程航班'},
        {'机型': '波音777(大)', '距离': 8000, '载客': 300, '描述': '国际长程航班'},
        {'机型': 'JET', '距离': 600, '载客': 80, '描述': '通用机型'},
    ]
    
    for flight in test_flights:
        icao_code = get_icao_code(flight['机型'])
        load_factor = calculate_load_factor(flight['载客'], icao_code)
        fuel_consumption = estimate_fuel_consumption_simple(
            flight['距离'], icao_code, flight['载客']
        )
        
        print(f"\n{flight['描述']}:")
        print(f"  机型: {flight['机型']} -> {icao_code}")
        print(f"  距离: {flight['距离']} km")
        print(f"  载客: {flight['载客']} 人")
        print(f"  载客率: {load_factor:.2%}")
        print(f"  燃油消耗: {fuel_consumption} kg")

if __name__ == '__main__':
    # 运行单元测试
    print("运行单元测试...")
    unittest.main(argv=[''], exit=False, verbosity=2)
    
    # 运行样例计算
    run_sample_calculation()
    
    print("\n=== 测试完成 ===") 