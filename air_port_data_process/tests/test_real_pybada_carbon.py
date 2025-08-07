"""
真实pyBADA库碳排放计算模块的单元测试
测试实际pyBADA API的功能和计算准确性
"""

import unittest
import pandas as pd
import numpy as np
import os
import sys
import tempfile
import shutil

# 添加src目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from real_pybada_carbon_calculator import RealPyBADACarbonCalculator, process_carbon_emissions_with_real_pybada

class TestRealPyBADACarbonCalculator(unittest.TestCase):
    """测试真实pyBADA碳排放计算器"""
    
    def setUp(self):
        """设置测试环境"""
        self.calculator = RealPyBADACarbonCalculator(bada_version="DUMMY")
        
        # 创建测试数据
        self.test_route_data = pd.Series({
            '起飞机场': 'ZBAA',
            '降落机场': 'ZSHC', 
            'ICAO代码': 'A320',
            '机型': 'A320',
            '里程（公里）': 1200,
            '燃油消耗_kg': 4500.0,
            '人数': 180,
            '载客率': 0.85,
            '出发城市': '北京',
            '到达城市': '上海'
        })
        
        # 创建临时目录用于测试输出
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """清理测试环境"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_calculator_initialization(self):
        """测试计算器初始化"""
        self.assertIsNotNone(self.calculator)
        self.assertIsInstance(self.calculator.stats, dict)
        self.assertEqual(self.calculator.stats['routes_calculated'], 0)
        print("✅ 计算器初始化测试通过")
    
    def test_aircraft_mapping(self):
        """测试机型映射功能"""
        # 测试常见机型的映射
        test_aircraft = ['A320', 'B737', 'A330', 'B777']
        
        for aircraft in test_aircraft:
            bada_name = self.calculator.get_bada_aircraft_name(aircraft)
            if self.calculator.use_pybada and self.calculator.bada_data is not None:
                # 如果pyBADA可用，应该能找到映射
                print(f"机型 {aircraft} 映射到 BADA: {bada_name}")
            else:
                print(f"pyBADA不可用，跳过机型 {aircraft} 的映射测试")
        
        print("✅ 机型映射测试完成")
    
    def test_carbon_emission_calculation(self):
        """测试基本碳排放计算"""
        result = self.calculator.calculate_route_carbon_emissions(self.test_route_data)
        
        # 验证返回结果的结构
        required_keys = [
            'co2_emissions_kg', 'co2_emissions_tons', 
            'co2_per_passenger_kg', 'co2_per_passenger_tons',
            'fuel_consumption_kg', 'emission_factor_used',
            'calculation_method', 'effective_passengers', 'distance_km'
        ]
        
        for key in required_keys:
            self.assertIn(key, result)
        
        # 验证数值的合理性
        self.assertGreater(result['co2_emissions_kg'], 0)
        self.assertGreater(result['co2_per_passenger_kg'], 0)
        self.assertEqual(result['co2_emissions_tons'], result['co2_emissions_kg'] / 1000)
        
        print(f"✅ 碳排放计算测试通过")
        print(f"   总CO2排放: {result['co2_emissions_kg']:.2f} kg")
        print(f"   人均CO2排放: {result['co2_per_passenger_kg']:.2f} kg")
        print(f"   计算方法: {result['calculation_method']}")
    
    def test_pybada_availability(self):
        """测试pyBADA库的可用性"""
        print(f"pyBADA可用性: {self.calculator.use_pybada}")
        
        if self.calculator.use_pybada:
            self.assertIsNotNone(self.calculator.bada_data)
            print(f"BADA数据版本: {self.calculator.bada_version}")
            print(f"BADA数据族: {self.calculator.bada_family}")
            if self.calculator.bada_data is not None:
                print(f"包含机型数量: {len(self.calculator.bada_data)}")
        else:
            print("pyBADA不可用，将使用标准排放系数")
        
        print("✅ pyBADA可用性测试完成")
    
    def test_fuel_consumption_calculation(self):
        """测试燃油消耗计算"""
        if self.calculator.use_pybada:
            fuel = self.calculator.calculate_fuel_consumption_with_pybada(self.test_route_data)
            if fuel:
                self.assertGreater(fuel, 0)
                print(f"✅ pyBADA燃油计算: {fuel:.2f} kg")
            else:
                print("⚠️ pyBADA燃油计算未返回有效结果")
        
        # 测试经验公式估算
        estimated_fuel = self.calculator._estimate_fuel_consumption(self.test_route_data)
        self.assertGreater(estimated_fuel, 0)
        print(f"✅ 经验公式燃油估算: {estimated_fuel:.2f} kg")
    
    def test_emission_factors(self):
        """测试排放系数"""
        test_aircraft = ['A320', 'B737', 'A330', 'B777', 'UNKNOWN']
        
        for aircraft in test_aircraft:
            factor = self.calculator._get_emission_factor(aircraft)
            self.assertGreater(factor, 0)
            self.assertLess(factor, 5.0)  # 合理范围
            print(f"机型 {aircraft} 排放系数: {factor}")
        
        print("✅ 排放系数测试通过")
    
    def test_cache_functionality(self):
        """测试缓存功能"""
        # 第一次计算
        result1 = self.calculator.calculate_route_carbon_emissions(self.test_route_data)
        routes_calculated_1 = self.calculator.stats['routes_calculated']
        cache_hits_1 = self.calculator.stats['cache_hits']
        
        # 第二次计算相同路线
        result2 = self.calculator.calculate_route_carbon_emissions(self.test_route_data)
        routes_calculated_2 = self.calculator.stats['routes_calculated']
        cache_hits_2 = self.calculator.stats['cache_hits']
        
        # 验证缓存生效
        self.assertEqual(routes_calculated_1, routes_calculated_2)  # 路线计算数不变
        self.assertEqual(cache_hits_2, cache_hits_1 + 1)  # 缓存命中数增加
        
        # 结果应该相同
        self.assertEqual(result1['co2_emissions_kg'], result2['co2_emissions_kg'])
        
        print("✅ 缓存功能测试通过")
    
    def test_error_handling(self):
        """测试错误处理"""
        # 测试空数据
        empty_data = pd.Series({})
        result = self.calculator.calculate_route_carbon_emissions(empty_data)
        self.assertEqual(result['co2_emissions_kg'], 0.0)
        
        # 测试无效距离
        invalid_data = self.test_route_data.copy()
        invalid_data['里程（公里）'] = 0
        result = self.calculator.calculate_route_carbon_emissions(invalid_data)
        self.assertGreaterEqual(result['co2_emissions_kg'], 0.0)
        
        print("✅ 错误处理测试通过")

class TestRealPyBADAIntegration(unittest.TestCase):
    """测试真实pyBADA集成功能"""
    
    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        
        # 创建测试数据文件
        self.test_data = pd.DataFrame({
            '起飞机场': ['ZBAA', 'ZSHC', 'ZGSZ'] * 10,
            '降落机场': ['ZSHC', 'ZGSZ', 'ZBAA'] * 10,
            'ICAO代码': ['A320', 'B737', 'A330'] * 10,
            '机型': ['A320', 'B737', 'A330'] * 10,
            '里程（公里）': [1200, 1300, 2000] * 10,
            '燃油消耗_kg': [4500, 4800, 7200] * 10,
            '人数': [180, 160, 300] * 10,
            '载客率': [0.85, 0.80, 0.90] * 10,
            '出发城市': ['北京', '上海', '广州'] * 10,
            '到达城市': ['上海', '广州', '北京'] * 10,
            '日期': pd.date_range('2024-01-01', periods=30)
        })
        
        self.test_file = os.path.join(self.temp_dir, 'test_data.xlsx')
        self.test_data.to_excel(self.test_file, index=False)
    
    def tearDown(self):
        """清理测试环境"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_full_processing(self):
        """测试完整处理流程"""
        result_df = process_carbon_emissions_with_real_pybada(
            data_file_path=self.test_file,
            output_dir=self.temp_dir,
            chunk_size=10
        )
        
        self.assertIsNotNone(result_df)
        self.assertEqual(len(result_df), len(self.test_data))
        
        # 验证新添加的列
        expected_columns = [
            'co2_emissions_kg', 'co2_emissions_tons',
            'co2_per_passenger_kg', 'co2_per_passenger_tons',
            'carbon_calculation_method', 'emission_factor_used'
        ]
        
        for col in expected_columns:
            self.assertIn(col, result_df.columns)
            self.assertTrue(result_df[col].notna().all())
        
        # 验证碳排放值的合理性
        self.assertTrue((result_df['co2_emissions_kg'] > 0).all())
        self.assertTrue((result_df['co2_per_passenger_kg'] > 0).all())
        
        print("✅ 完整处理流程测试通过")
        print(f"   处理记录数: {len(result_df)}")
        print(f"   平均碳排放: {result_df['co2_emissions_kg'].mean():.2f} kg")
        print(f"   平均人均排放: {result_df['co2_per_passenger_kg'].mean():.2f} kg")

def run_real_pybada_tests():
    """运行真实pyBADA库的测试"""
    print("\n" + "="*60)
    print("🧪 开始真实pyBADA库碳排放计算测试")
    print("="*60)
    
    # 创建测试套件
    suite = unittest.TestSuite()
    
    # 添加基础测试
    suite.addTest(TestRealPyBADACarbonCalculator('test_calculator_initialization'))
    suite.addTest(TestRealPyBADACarbonCalculator('test_pybada_availability'))
    suite.addTest(TestRealPyBADACarbonCalculator('test_aircraft_mapping'))
    suite.addTest(TestRealPyBADACarbonCalculator('test_carbon_emission_calculation'))
    suite.addTest(TestRealPyBADACarbonCalculator('test_fuel_consumption_calculation'))
    suite.addTest(TestRealPyBADACarbonCalculator('test_emission_factors'))
    suite.addTest(TestRealPyBADACarbonCalculator('test_cache_functionality'))
    suite.addTest(TestRealPyBADACarbonCalculator('test_error_handling'))
    
    # 添加集成测试
    suite.addTest(TestRealPyBADAIntegration('test_full_processing'))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 输出测试总结
    print("\n" + "="*60)
    print("📊 测试总结:")
    print(f"✅ 成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"❌ 失败: {len(result.failures)}")
    print(f"⚠️  错误: {len(result.errors)}")
    print("="*60)
    
    return result.wasSuccessful()

if __name__ == "__main__":
    success = run_real_pybada_tests()
    if success:
        print("🎉 所有测试通过!")
        exit(0)
    else:
        print("❌ 有测试失败!")
        exit(1) 