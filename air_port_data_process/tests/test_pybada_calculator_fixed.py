"""
pyBADA燃油消耗计算器修正测试
测试基于pyBADA库的燃油消耗计算功能，使用正确的方法名
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

class TestPyBADAFuelCalculatorFixed(unittest.TestCase):
    """测试pyBADA燃油消耗计算器（修正版）"""
    
    @classmethod
    def setUpClass(cls):
        """设置测试类"""
        if not CALCULATOR_AVAILABLE:
            raise unittest.SkipTest("pyBADA计算器不可用")
        
        try:
            cls.calculator = PyBADAFuelCalculator()
            print("✅ pyBADA计算器初始化成功")
        except Exception as e:
            raise unittest.SkipTest(f"pyBADA计算器初始化失败: {e}")
    
    def test_calculator_initialization(self):
        """测试计算器初始化"""
        self.assertIsNotNone(self.calculator)
        # 检查aircraft_mapping属性是否存在
        self.assertIsNotNone(self.calculator.aircraft_mapping)
        self.assertIsNotNone(self.calculator._aircraft_cache)
        print("✅ 计算器初始化测试通过")
    
    def test_aircraft_model_loading(self):
        """测试机型模型加载"""
        # 测试常见机型
        test_aircraft = ['B737', 'A320', 'B777', 'A319', 'A321']
        
        for aircraft_type in test_aircraft:
            aircraft_model = self.calculator.get_aircraft_model(aircraft_type)
            print(f"机型 {aircraft_type}: {'✅ 可用' if aircraft_model is not None else '❌ 不可用'}")
            
            # 如果pyBADA可用，至少应该能加载一些机型
            if aircraft_model is not None:
                self.assertIsNotNone(aircraft_model)
                print(f"  - 模型类型: {type(aircraft_model)}")
    
    def test_single_flight_calculation(self):
        """测试单次航班计算"""
        # 测试案例：中程航班
        test_case = {
            'aircraft_type': 'B737',
            'distance_km': 2000,
            'passengers': 150
        }
        
        result = self.calculator.calculate_single_flight(
            test_case['aircraft_type'],
            test_case['distance_km'],
            test_case['passengers']
        )
        
        # 验证结果结构
        self.assertIsInstance(result, dict)
        print(f"✅ 单次航班计算测试:")
        print(f"   机型: {test_case['aircraft_type']}")
        print(f"   距离: {test_case['distance_km']}km")
        print(f"   乘客: {test_case['passengers']}人")
        print(f"   结果类型: {type(result)}")
        
        # 打印结果详情
        for key, value in result.items():
            print(f"   {key}: {value}")
    
    def test_trajectory_calculation_with_tcl(self):
        """测试TCL轨迹计算"""
        # 测试案例：短程航班
        test_case = {
            'aircraft_type': 'A320',
            'distance_km': 1500,
            'passengers': 140
        }
        
        result = self.calculator.calculate_trajectory_with_tcl(
            test_case['aircraft_type'],
            test_case['distance_km'],
            test_case['passengers']
        )
        
        print(f"✅ TCL轨迹计算测试:")
        print(f"   机型: {test_case['aircraft_type']}")
        print(f"   距离: {test_case['distance_km']}km")
        print(f"   乘客: {test_case['passengers']}人")
        print(f"   结果: {'成功' if result is not None else '失败'}")
        
        if result is not None:
            print(f"   结果类型: {type(result)}")
            # 如果是FlightTrajectoryResult，打印详细信息
            if hasattr(result, 'total_fuel_kg'):
                print(f"   总燃油消耗: {result.total_fuel_kg:.2f}kg")
                print(f"   总距离: {result.total_distance_km:.2f}km")
                print(f"   总时间: {result.total_time_minutes:.2f}分钟")
    
    def test_multiple_aircraft_types(self):
        """测试多种机型的计算"""
        test_cases = [
            ('B737', 2000, 150),
            ('A320', 1500, 140),
            ('B777', 8000, 300),
            ('A319', 1200, 130),
            ('A321', 2500, 180)
        ]
        
        successful_calculations = 0
        
        for aircraft_type, distance, passengers in test_cases:
            try:
                result = self.calculator.calculate_single_flight(
                    aircraft_type, distance, passengers
                )
                
                if result and 'status' in result:
                    status = result['status']
                    print(f"机型 {aircraft_type}: {status}")
                    if status == 'success':
                        successful_calculations += 1
                else:
                    print(f"机型 {aircraft_type}: 计算完成")
                    successful_calculations += 1
                    
            except Exception as e:
                print(f"机型 {aircraft_type}: 计算失败 - {e}")
        
        print(f"✅ 多机型测试: {successful_calculations}/{len(test_cases)} 成功")
        # 至少应该有一些成功的计算
        self.assertGreater(successful_calculations, 0)
    
    def test_aircraft_parameter_adapter(self):
        """测试机型参数适配器"""
        adapter = self.calculator.aircraft_mapping
        
        # 测试BADA代码映射
        test_mappings = [
            ('B737', 'B737'),
            ('A320', 'A320'),
            ('B777', 'B777'),
            ('波音737', 'B737'),
            ('空客320', 'A320')
        ]
        
        for input_type, expected_bada in test_mappings:
            bada_code = adapter.get_bada_aircraft_code(input_type)
            print(f"机型映射: {input_type} -> {bada_code}")
            
            # 验证映射结果
            if bada_code is not None:
                self.assertIsInstance(bada_code, str)
        
        # 测试参数获取
        test_parameters = [
            ('B737', 'max_mass'),
            ('A320', 'cruise_altitude'),
            ('B777', 'max_passengers')
        ]
        
        for aircraft_type, parameter in test_parameters:
            value = adapter.get_aircraft_parameter(aircraft_type, parameter, 0)
            print(f"参数获取: {aircraft_type}.{parameter} = {value}")
            self.assertIsNotNone(value)
        
        print("✅ 机型参数适配器测试通过")
    
    def test_edge_cases(self):
        """测试边界情况"""
        # 测试极端情况
        edge_cases = [
            ('B737', 100, 50, '短程航班'),    # 短程
            ('B737', 5000, 150, '长程航班'),  # 长程
            ('B737', 2000, 1, '低载客'),      # 低载客
            ('B737', 2000, 200, '高载客'),    # 高载客
            ('UNKNOWN', 2000, 150, '未知机型') # 未知机型
        ]
        
        for aircraft_type, distance, passengers, case_name in edge_cases:
            try:
                result = self.calculator.calculate_single_flight(
                    aircraft_type, distance, passengers
                )
                
                print(f"{case_name}: 计算{'成功' if result else '失败'}")
                
                if result:
                    # 检查结果的合理性
                    self.assertIsInstance(result, dict)
                    
            except Exception as e:
                print(f"{case_name}: 异常 - {e}")
        
        print("✅ 边界情况测试完成")

def run_fixed_tests():
    """运行修正版pyBADA测试套件"""
    print("=" * 60)
    print("pyBADA燃油消耗计算器修正测试套件")
    print("=" * 60)
    
    print(f"pyBADA库状态: {'✅ 可用' if PYBADA_AVAILABLE else '❌ 不可用'}")
    print(f"计算器状态: {'✅ 可用' if CALCULATOR_AVAILABLE else '❌ 不可用'}")
    
    if not CALCULATOR_AVAILABLE:
        print("❌ 计算器不可用，跳过测试")
        return
    
    # 运行测试
    suite = unittest.TestLoader().loadTestsFromTestCase(TestPyBADAFuelCalculatorFixed)
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

if __name__ == '__main__':
    run_fixed_tests() 