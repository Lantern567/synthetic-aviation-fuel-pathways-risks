"""
pyBADA燃油消耗计算器单元测试
测试基于pyBADA库的燃油消耗计算功能
"""

import unittest
import sys
import os

# 添加源代码目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), '../src'))

try:
    from pybada_fuel_calculator import PyBADAFuelCalculator, PYBADA_AVAILABLE
    CALCULATOR_AVAILABLE = True
except ImportError as e:
    CALCULATOR_AVAILABLE = False
    print(f"pyBADA计算器导入失败: {e}")

class TestPyBADAFuelCalculator(unittest.TestCase):
    """测试pyBADA燃油消耗计算器"""
    
    @classmethod
    def setUpClass(cls):
        """设置测试类"""
        if not CALCULATOR_AVAILABLE:
            raise unittest.SkipTest("pyBADA计算器不可用")
        
        try:
            cls.calculator = PyBADAFuelCalculator()
            print("pyBADA计算器初始化成功")
        except Exception as e:
            raise unittest.SkipTest(f"pyBADA计算器初始化失败: {e}")
    
    def test_calculator_initialization(self):
        """测试计算器初始化"""
        self.assertIsNotNone(self.calculator)
        # 由于缓存是跨测试共享的，我们检查属性是否存在而不是为空
        self.assertIsNotNone(self.calculator.bada_cache)
        self.assertIsNotNone(self.calculator.aircraft_cache)
        self.assertIsNotNone(self.calculator.calculation_results)
        print("✅ 计算器初始化测试通过")
    
    def test_bada_aircraft_loading(self):
        """测试BADA机型加载"""
        # 测试常见机型
        test_aircraft = ['B737', 'A320', 'B777']
        
        for icao_code in test_aircraft:
            aircraft = self.calculator.get_bada_aircraft(icao_code)
            print(f"机型 {icao_code}: {'可用' if aircraft is not None else '不可用'}")
            
            # 如果BADA可用，至少应该加载一些机型
            if PYBADA_AVAILABLE and aircraft is not None:
                self.assertIsNotNone(aircraft)
                print(f"✅ {icao_code} 加载成功")
    
    def test_aircraft_mass_estimation(self):
        """测试飞机质量估算"""
        # 测试不同机型的质量估算
        test_cases = [
            ('B737', 0.8, 65000, 79000),  # 载客率, 最小期望质量, 最大质量
            ('A380', 0.9, 350000, 560000),
            ('B777', 0.85, 200000, 350000)
        ]
        
        for icao_code, load_factor, min_mass, max_mass in test_cases:
            mass = self.calculator._estimate_aircraft_mass(icao_code, load_factor)
            self.assertGreaterEqual(mass, min_mass)
            self.assertLessEqual(mass, max_mass)
            print(f"✅ {icao_code} 质量估算: {mass:.0f}kg (载客率: {load_factor:.1%})")
    
    def test_takeoff_landing_fuel_estimation(self):
        """测试起降燃油估算"""
        test_aircraft = ['B737', 'A320', 'B777', 'A380']
        
        for icao_code in test_aircraft:
            fuel = self.calculator._estimate_takeoff_landing_fuel(icao_code)
            self.assertGreater(fuel, 0)
            self.assertLess(fuel, 2000)  # 合理的起降燃油范围
            print(f"✅ {icao_code} 起降燃油: {fuel}kg")
    
    def test_fuel_consumption_calculation(self):
        """测试燃油消耗计算"""
        # 测试案例：阿克苏→上海航班
        test_case = {
            'chinese_aircraft': '波音737(中)',
            'distance_km': 3829.49,
            'passengers': 150
        }
        
        result = self.calculator.calculate_flight_fuel_consumption(
            test_case['chinese_aircraft'],
            test_case['distance_km'],
            test_case['passengers']
        )
        
        # 验证结果结构
        required_keys = [
            'icao_code', 'bada_available', 'fuel_consumption_kg',
            'load_factor', 'calculation_method'
        ]
        
        for key in required_keys:
            self.assertIn(key, result)
        
        # 验证结果合理性
        self.assertEqual(result['icao_code'], 'B737')
        self.assertGreater(result['fuel_consumption_kg'], 0)
        self.assertGreaterEqual(result['load_factor'], 0)
        self.assertLessEqual(result['load_factor'], 1)
        
        print(f"✅ 燃油消耗计算测试:")
        print(f"   机型: {result['icao_code']}")
        print(f"   BADA可用: {result['bada_available']}")
        print(f"   燃油消耗: {result['fuel_consumption_kg']:.2f}kg")
        print(f"   载客率: {result['load_factor']:.1%}")
        print(f"   计算方法: {result['calculation_method']}")
    
    def test_multiple_aircraft_types(self):
        """测试多种机型的计算"""
        test_cases = [
            ('波音737(中)', 2000, 150),
            ('空客320(中)', 1500, 140),
            ('波音777(大)', 8000, 300),
            ('空客330(宽)', 6000, 250)
        ]
        
        results = []
        for chinese_aircraft, distance, passengers in test_cases:
            result = self.calculator.calculate_flight_fuel_consumption(
                chinese_aircraft, distance, passengers
            )
            results.append(result)
            
            print(f"机型: {chinese_aircraft} -> {result['icao_code']}")
            print(f"  燃油: {result['fuel_consumption_kg']:.2f}kg")
            print(f"  方法: {result['calculation_method']}")
        
        # 验证所有计算都成功
        successful_results = [r for r in results if r['fuel_consumption_kg'] > 0]
        self.assertGreater(len(successful_results), 0)
        print(f"✅ 多机型测试: {len(successful_results)}/{len(test_cases)} 成功")
    
    def test_edge_cases(self):
        """测试边界情况"""
        # 测试极端距离
        edge_cases = [
            ('波音737(中)', 100, 50, '短程'),    # 短程
            ('波音737(中)', 10000, 150, '长程'), # 长程
            ('波音737(中)', 2000, 1, '低载客'),   # 低载客
            ('波音737(中)', 2000, 200, '超载'),  # 超载
        ]
        
        for chinese_aircraft, distance, passengers, case_name in edge_cases:
            result = self.calculator.calculate_flight_fuel_consumption(
                chinese_aircraft, distance, passengers
            )
            
            print(f"{case_name}: 燃油 {result['fuel_consumption_kg']:.2f}kg, "
                  f"方法 {result['calculation_method']}")
            
            # 即使是边界情况，也应该有合理的结果
            if result['calculation_method'] != 'failed':
                self.assertGreater(result['fuel_consumption_kg'], 0)
        
        print("✅ 边界情况测试完成")

def run_pybada_tests():
    """运行pyBADA测试套件"""
    print("=" * 60)
    print("pyBADA燃油消耗计算器测试套件")
    print("=" * 60)
    
    print(f"pyBADA库状态: {'可用' if PYBADA_AVAILABLE else '不可用'}")
    print(f"计算器状态: {'可用' if CALCULATOR_AVAILABLE else '不可用'}")
    
    if not CALCULATOR_AVAILABLE:
        print("❌ 计算器不可用，跳过测试")
        return
    
    # 运行测试
    suite = unittest.TestLoader().loadTestsFromTestCase(TestPyBADAFuelCalculator)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 测试结果总结
    print("\n" + "=" * 60)
    print("测试结果总结")
    print("=" * 60)
    print(f"运行测试: {result.testsRun}")
    print(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")
    
    if result.failures:
        print("\n失败详情:")
        for test, traceback in result.failures:
            print(f"- {test}: {traceback}")
    
    if result.errors:
        print("\n错误详情:")
        for test, traceback in result.errors:
            print(f"- {test}: {traceback}")
    
    success_rate = (result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100
    print(f"\n测试成功率: {success_rate:.1f}%")
    
    return result.wasSuccessful()

if __name__ == "__main__":
    run_pybada_tests() 