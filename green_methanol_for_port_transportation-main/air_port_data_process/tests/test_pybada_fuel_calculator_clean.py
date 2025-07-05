"""
清理版pyBADA燃油计算器的单元测试
仅测试BADA模型计算功能
"""

import unittest
import sys
import os

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    from pybada_fuel_calculator import PyBADAFuelCalculator, process_flight_data_with_pybada
    import pandas as pd
    PYBADA_CLEAN_AVAILABLE = True
except ImportError as e:
    print(f"❌ 导入清理版模块失败: {e}")
    PYBADA_CLEAN_AVAILABLE = False

class TestPyBADACleanCalculator(unittest.TestCase):
    """测试清理版pyBADA燃油计算器"""
    
    def setUp(self):
        """测试前准备"""
        if not PYBADA_CLEAN_AVAILABLE:
            self.skipTest("清理版pyBADA模块不可用")
        
        self.calculator = PyBADAFuelCalculator()
    
    def test_calculator_initialization(self):
        """测试计算器初始化"""
        self.assertIsNotNone(self.calculator)
        self.assertIsInstance(self.calculator.bada_cache, dict)
        self.assertIsInstance(self.calculator.aircraft_cache, dict)
    
    def test_bada_aircraft_creation(self):
        """测试BADA机型对象创建"""
        aircraft = self.calculator.get_bada_aircraft('B737')
        self.assertIsNotNone(aircraft, "应该成功创建B737的BADA对象")
        
        # 测试缓存功能
        aircraft2 = self.calculator.get_bada_aircraft('B737')
        self.assertIs(aircraft, aircraft2, "应该从缓存中获取相同的对象")
    
    def test_aircraft_mass_estimation(self):
        """测试飞机质量估算"""
        mass = self.calculator.estimate_aircraft_mass('B737', 0.8)
        self.assertGreater(mass, 0, "飞机质量应该大于0")
        self.assertLess(mass, 100000, "B737质量应该小于100吨")
        
        # 测试不同载客率
        mass_low = self.calculator.estimate_aircraft_mass('B737', 0.5)
        mass_high = self.calculator.estimate_aircraft_mass('B737', 1.0)
        self.assertLess(mass_low, mass_high, "高载客率应该有更大的质量")
    
    def test_takeoff_landing_fuel_estimation(self):
        """测试起降燃油估算"""
        fuel = self.calculator.estimate_takeoff_landing_fuel('B737')
        self.assertGreater(fuel, 0, "起降燃油应该大于0")
        self.assertEqual(fuel, 300, "B737起降燃油应该是300kg")
        
        # 测试大型机型
        fuel_777 = self.calculator.estimate_takeoff_landing_fuel('B777')
        self.assertGreater(fuel_777, fuel, "B777起降燃油应该比B737更多")
    
    def test_fuel_flow_calculation(self):
        """测试燃油流量计算"""
        aircraft = self.calculator.get_bada_aircraft('B737')
        self.assertIsNotNone(aircraft, "需要有效的BADA对象")
        
        fuel_flow = self.calculator.calculate_cruise_fuel_flow(
            aircraft, 35000, 0.8, 70000, 220
        )
        
        self.assertGreater(fuel_flow, 0, "燃油流量应该大于0")
        self.assertLess(fuel_flow, 5, "B737燃油流量应该小于5 kg/s")
        print(f"✅ B737燃油流量: {fuel_flow:.4f} kg/s")
    
    def test_flight_fuel_consumption(self):
        """测试完整的航班燃油消耗计算"""
        result = self.calculator.calculate_flight_fuel_consumption(
            "波音737(中)", 3000, 150
        )
        
        # 验证返回结果结构
        required_keys = ['icao_code', 'fuel_consumption_kg', 'fuel_flow_kg_per_s', 
                        'cruise_time_hours', 'aircraft_mass_kg', 'load_factor', 'calculation_method']
        
        for key in required_keys:
            self.assertIn(key, result, f"结果应包含{key}")
        
        # 验证计算结果合理性
        self.assertEqual(result['icao_code'], 'B737')
        self.assertEqual(result['calculation_method'], 'pybada')
        self.assertGreater(result['fuel_consumption_kg'], 0, "燃油消耗应该大于0")
        self.assertGreater(result['load_factor'], 0, "载客率应该大于0")
        
        print(f"✅ 航班燃油消耗计算: {result['fuel_consumption_kg']} kg")
    
    def test_different_aircraft_types(self):
        """测试不同机型的计算"""
        test_cases = [
            {"aircraft": "波音737(中)", "expected_icao": "B737"},
            {"aircraft": "空客320", "expected_icao": "A320"},
            {"aircraft": "波音777", "expected_icao": "B777"},
        ]
        
        for case in test_cases:
            with self.subTest(aircraft=case["aircraft"]):
                result = self.calculator.calculate_flight_fuel_consumption(
                    case["aircraft"], 2000, 100
                )
                
                self.assertEqual(result['icao_code'], case["expected_icao"])
                self.assertEqual(result['calculation_method'], 'pybada')
                self.assertGreater(result['fuel_consumption_kg'], 0)
                
                print(f"✅ {case['aircraft']} -> {result['icao_code']}: {result['fuel_consumption_kg']} kg")
    
    def test_dataframe_processing(self):
        """测试DataFrame批量处理"""
        # 创建测试数据
        test_data = {
            '机型': ['波音737(中)', '空客320', '波音777'],
            '里程（公里）': [1500, 2000, 5000],
            '人数': [120, 140, 250]
        }
        df = pd.DataFrame(test_data)
        
        # 处理数据
        result_df = process_flight_data_with_pybada(df)
        
        # 验证结果
        self.assertEqual(len(result_df), 3, "应该处理3条记录")
        
        required_columns = ['ICAO代码', '载客率', '燃油消耗_kg', '燃油流量_kg_per_s', 
                           '巡航时间_hours', '计算方法']
        
        for col in required_columns:
            self.assertIn(col, result_df.columns, f"应该包含列{col}")
        
        # 验证所有记录都使用pyBADA计算
        for method in result_df['计算方法']:
            self.assertEqual(method, 'pybada', "所有记录都应使用pyBADA计算")
        
        print(f"✅ 批量处理成功: {len(result_df)} 条记录")

def run_clean_tests():
    """运行清理版测试"""
    print("=== 清理版pyBADA计算器测试 ===")
    
    if not PYBADA_CLEAN_AVAILABLE:
        print("❌ 清理版pyBADA模块不可用，跳过测试")
        return
    
    # 创建测试套件
    suite = unittest.TestLoader().loadTestsFromTestCase(TestPyBADACleanCalculator)
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 输出测试结果
    if result.wasSuccessful():
        print(f"\n✅ 所有测试通过! 运行了 {result.testsRun} 个测试")
    else:
        print(f"\n❌ 测试失败! {len(result.failures)} 个失败, {len(result.errors)} 个错误")
        
        for failure in result.failures:
            print(f"失败: {failure[0]}")
            print(f"原因: {failure[1]}")
        
        for error in result.errors:
            print(f"错误: {error[0]}")
            print(f"原因: {error[1]}")

if __name__ == "__main__":
    run_clean_tests() 