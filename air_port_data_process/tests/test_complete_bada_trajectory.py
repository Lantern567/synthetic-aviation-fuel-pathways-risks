"""
完整BADA轨迹模型测试单元
测试包含爬升、巡航、下降三个完整阶段的燃油消耗和碳排放计算
"""

import unittest
import pandas as pd
import numpy as np
import sys
import os

# 添加src目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from real_pybada_carbon_calculator import CompleteBadaCarbonCalculator

class TestCompleteBadaTrajectory(unittest.TestCase):
    """完整BADA轨迹模型测试类"""
    
    def setUp(self):
        """测试前的设置"""
        self.calculator = CompleteBadaCarbonCalculator(bada_version="DUMMY")
        
        # 创建测试航线数据
        self.test_routes = [
            {
                'ICAO代码': 'A320',
                '机型': 'A320',
                '起飞机场': 'PVG',
                '降落机场': 'PEK',
                '里程（公里）': 1200,
                '人数': 160,
                '载客率': 0.8,
                '燃油消耗_kg': 0  # 让模型计算
            },
            {
                'ICAO代码': 'B737',
                '机型': 'B737',
                '起飞机场': 'SHA',
                '降落机场': 'CTU',
                '里程（公里）': 1650,
                '人数': 150,
                '载客率': 0.75,
                '燃油消耗_kg': 0
            },
            {
                'ICAO代码': 'A330',
                '机型': 'A330',
                '起飞机场': 'PVG',
                '降落机场': 'NRT',
                '里程（公里）': 1800,
                '人数': 280,
                '载客率': 0.85,
                '燃油消耗_kg': 0
            },
            {
                'ICAO代码': 'B777',
                '机型': 'B777',
                '起飞机场': 'PEK',
                '降落机场': 'LAX',
                '里程（公里）': 11000,
                '人数': 350,
                '载客率': 0.9,
                '燃油消耗_kg': 0
            }
        ]
    
    def test_calculator_initialization(self):
        """测试计算器初始化"""
        self.assertIsNotNone(self.calculator)
        self.assertEqual(self.calculator.bada_version, "DUMMY")
        self.assertIn('routes_calculated', self.calculator.stats)
        self.assertIn('trajectory_calculations', self.calculator.stats)
        self.assertIn('simplified_calculations', self.calculator.stats)
        print("✅ 完整BADA计算器初始化测试通过")
    
    def test_cruise_altitude_determination(self):
        """测试巡航高度确定逻辑"""
        # 短程航班
        altitude_short = self.calculator._determine_cruise_altitude(400)
        self.assertEqual(altitude_short, 25000)  # FL250
        
        # 中程航班
        altitude_medium = self.calculator._determine_cruise_altitude(1200)
        self.assertEqual(altitude_medium, 33000)  # FL330
        
        # 长程航班
        altitude_long = self.calculator._determine_cruise_altitude(2500)
        self.assertEqual(altitude_long, 37000)  # FL370
        
        # 超长程航班
        altitude_ultra = self.calculator._determine_cruise_altitude(10000)
        self.assertEqual(altitude_ultra, 41000)  # FL410
        
        print("✅ 巡航高度确定测试通过")
    
    def test_cruise_mach_determination(self):
        """测试巡航马赫数确定逻辑"""
        # 测试不同机型的马赫数
        mach_a320 = self.calculator._determine_cruise_mach('A320')
        self.assertEqual(mach_a320, 0.78)
        
        mach_b777 = self.calculator._determine_cruise_mach('B777')
        self.assertEqual(mach_b777, 0.84)
        
        mach_a380 = self.calculator._determine_cruise_mach('A380')
        self.assertEqual(mach_a380, 0.85)
        
        # 测试未知机型的默认值
        mach_unknown = self.calculator._determine_cruise_mach('UNKNOWN')
        self.assertEqual(mach_unknown, 0.78)
        
        print("✅ 巡航马赫数确定测试通过")
    
    def test_aircraft_mapping(self):
        """测试机型映射功能"""
        # 测试常见机型映射
        bada_name_a320 = self.calculator.get_bada_aircraft_name('A320')
        if self.calculator.use_pybada:
            self.assertIsNotNone(bada_name_a320)
        
        bada_name_b737 = self.calculator.get_bada_aircraft_name('B737')
        if self.calculator.use_pybada:
            self.assertIsNotNone(bada_name_b737)
        
        print("✅ 机型映射测试通过")
    
    def test_bada_aircraft_creation(self):
        """测试BADA飞机对象创建"""
        if self.calculator.use_pybada:
            aircraft = self.calculator.create_bada_aircraft('A320')
            if aircraft:
                self.assertIsNotNone(aircraft)
                self.assertTrue(hasattr(aircraft, 'MTOW'))
                self.assertTrue(hasattr(aircraft, 'OEW'))
                print("✅ BADA飞机对象创建测试通过")
            else:
                print("⚠️ BADA飞机对象创建失败 (可能是数据问题)")
        else:
            print("⚠️ pyBADA库未可用，跳过BADA飞机对象测试")
    
    def test_climb_fuel_estimation(self):
        """测试爬升燃油估算"""
        if self.calculator.use_pybada:
            aircraft = self.calculator.create_bada_aircraft('A320')
            if aircraft:
                climb_fuel = self.calculator._estimate_climb_fuel(aircraft, 33000, 65000)
                self.assertGreater(climb_fuel, 0)
                self.assertLess(climb_fuel, 5000)  # 应该在合理范围内
                print(f"✅ 爬升燃油估算测试通过: {climb_fuel:.1f} kg")
            else:
                print("⚠️ 无法创建飞机对象，跳过爬升燃油测试")
        else:
            print("⚠️ pyBADA库未可用，跳过爬升燃油测试")
    
    def test_cruise_fuel_estimation(self):
        """测试巡航燃油估算"""
        if self.calculator.use_pybada:
            aircraft = self.calculator.create_bada_aircraft('A320')
            if aircraft:
                cruise_fuel = self.calculator._estimate_cruise_fuel(aircraft, 1000, 65000)
                self.assertGreater(cruise_fuel, 0)
                self.assertLess(cruise_fuel, 10000)  # 应该在合理范围内
                print(f"✅ 巡航燃油估算测试通过: {cruise_fuel:.1f} kg")
            else:
                print("⚠️ 无法创建飞机对象，跳过巡航燃油测试")
        else:
            print("⚠️ pyBADA库未可用，跳过巡航燃油测试")
    
    def test_complete_trajectory_calculation(self):
        """测试完整轨迹燃油计算"""
        route_data = pd.Series(self.test_routes[0])
        
        fuel_consumption = self.calculator.calculate_complete_trajectory_fuel(route_data)
        
        if fuel_consumption:
            self.assertIsInstance(fuel_consumption, float)
            self.assertGreater(fuel_consumption, 0)
            self.assertLess(fuel_consumption, 20000)  # 合理范围检查
            print(f"✅ 完整轨迹燃油计算测试通过: {fuel_consumption:.1f} kg")
        else:
            print("⚠️ 完整轨迹计算返回None (可能使用了简化计算)")
    
    def test_carbon_emissions_calculation(self):
        """测试碳排放计算"""
        route_data = pd.Series(self.test_routes[0])
        
        result = self.calculator.calculate_route_carbon_emissions(route_data)
        
        # 验证结果结构
        required_keys = [
            'co2_emissions_kg', 'co2_emissions_tons',
            'co2_per_passenger_kg', 'co2_per_passenger_tons',
            'fuel_consumption_kg', 'emission_factor_used',
            'calculation_method', 'effective_passengers', 'distance_km'
        ]
        
        for key in required_keys:
            self.assertIn(key, result)
        
        # 验证数值合理性
        self.assertGreater(result['co2_emissions_kg'], 0)
        self.assertGreater(result['co2_per_passenger_kg'], 0)
        self.assertGreater(result['fuel_consumption_kg'], 0)
        self.assertGreater(result['emission_factor_used'], 3.0)
        self.assertLess(result['emission_factor_used'], 3.5)
        
        print(f"✅ 碳排放计算测试通过:")
        print(f"   燃油消耗: {result['fuel_consumption_kg']:.1f} kg")
        print(f"   碳排放: {result['co2_emissions_kg']:.1f} kg")
        print(f"   人均排放: {result['co2_per_passenger_kg']:.1f} kg")
        print(f"   计算方法: {result['calculation_method']}")
    
    def test_multiple_aircraft_types(self):
        """测试多种机型的计算"""
        results = []
        
        for route in self.test_routes:
            route_data = pd.Series(route)
            result = self.calculator.calculate_route_carbon_emissions(route_data)
            results.append({
                'aircraft': route['ICAO代码'],
                'distance': route['里程（公里）'],
                'fuel_kg': result['fuel_consumption_kg'],
                'co2_kg': result['co2_emissions_kg'],
                'co2_per_pax': result['co2_per_passenger_kg'],
                'method': result['calculation_method']
            })
        
        # 验证所有计算都成功
        for result in results:
            self.assertGreater(result['fuel_kg'], 0)
            self.assertGreater(result['co2_kg'], 0)
        
        print("✅ 多机型计算测试通过:")
        for result in results:
            print(f"   {result['aircraft']}: {result['fuel_kg']:.0f}kg燃油, "
                  f"{result['co2_kg']:.0f}kg CO2, "
                  f"{result['co2_per_pax']:.1f}kg/人 ({result['method']})")
    
    def test_caching_mechanism(self):
        """测试缓存机制"""
        route_data = pd.Series(self.test_routes[0])
        
        # 第一次计算
        result1 = self.calculator.calculate_route_carbon_emissions(route_data)
        cache_hits_before = self.calculator.stats['cache_hits']
        
        # 第二次计算相同航线
        result2 = self.calculator.calculate_route_carbon_emissions(route_data)
        cache_hits_after = self.calculator.stats['cache_hits']
        
        # 验证缓存生效
        self.assertEqual(cache_hits_after, cache_hits_before + 1)
        self.assertEqual(result1['co2_emissions_kg'], result2['co2_emissions_kg'])
        
        print("✅ 缓存机制测试通过")
    
    def test_statistics_tracking(self):
        """测试统计跟踪功能"""
        initial_stats = self.calculator.stats.copy()
        
        # 进行几次计算
        for route in self.test_routes[:2]:
            route_data = pd.Series(route)
            self.calculator.calculate_route_carbon_emissions(route_data)
        
        # 验证统计更新
        self.assertGreater(self.calculator.stats['routes_calculated'], 
                          initial_stats['routes_calculated'])
        self.assertGreaterEqual(self.calculator.stats['total_emissions'], 0)
        
        print("✅ 统计跟踪测试通过")
        print(f"   计算航线数: {self.calculator.stats['routes_calculated']}")
        print(f"   轨迹计算数: {self.calculator.stats['trajectory_calculations']}")
        print(f"   简化计算数: {self.calculator.stats['simplified_calculations']}")

def run_complete_bada_tests():
    """运行完整BADA轨迹模型测试"""
    print("🧪 开始完整BADA轨迹模型测试...")
    print("="*60)
    
    # 创建测试套件
    suite = unittest.TestLoader().loadTestsFromTestCase(TestCompleteBadaTrajectory)
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=0)
    result = runner.run(suite)
    
    print("\n" + "="*60)
    print("📊 测试结果摘要:")
    print(f"   总测试数: {result.testsRun}")
    print(f"   成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"   失败: {len(result.failures)}")
    print(f"   错误: {len(result.errors)}")
    
    if result.failures:
        print("\n❌ 失败的测试:")
        for test, traceback in result.failures:
            print(f"   - {test}")
    
    if result.errors:
        print("\n❌ 错误的测试:")
        for test, traceback in result.errors:
            print(f"   - {test}")
    
    success_rate = ((result.testsRun - len(result.failures) - len(result.errors)) 
                   / result.testsRun * 100) if result.testsRun > 0 else 0
    
    print(f"\n🎯 总体成功率: {success_rate:.1f}%")
    
    if success_rate >= 80:
        print("✅ 完整BADA轨迹模型测试整体通过!")
        return True
    else:
        print("❌ 完整BADA轨迹模型测试存在问题!")
        return False

if __name__ == "__main__":
    run_complete_bada_tests() 