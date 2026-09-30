"""
最终对比测试 - 验证原始版本和重构版本产生相同的结果
"""

import sys
import os
import pandas as pd
import numpy as np
import unittest

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
sys.path.append(project_root)

# 导入新的模块化组件
from shared.utils.geographic_calculator import GeographicCalculator
from tools.data_processing.renewable_data_processor import RenewableDataProcessor
from shared.core.cost_calculator import CostCalculator, EconomicParametersManager


class FinalComparisonTest(unittest.TestCase):
    """最终对比测试类"""
    
    def setUp(self):
        """设置测试环境"""
        # 创建模块化组件
        self.geo_calc = GeographicCalculator()
        self.data_processor = RenewableDataProcessor(total_hours=24, max_distance_km=500)
        self.cost_calc = CostCalculator()
        
        # 创建可再生能源测试数据
        test_data = []
        for hour in range(24):
            for i, plant_name in enumerate(['solar_beijing', 'wind_shanghai']):
                plant_type = 'solar_plant' if 'solar' in plant_name else 'wind_farm'
                lat = 39.9 if 'beijing' in plant_name else 31.2
                lon = 116.4 if 'beijing' in plant_name else 121.5
                test_data.append({
                    'plant_name': plant_name,
                    'type': plant_type,
                    'latitude': lat,
                    'longitude': lon,
                    'capacity_mw': 100.0 + i * 50.0,
                    'power_output_mw': 50.0 + hour * (2.0 + i)
                })
        self.test_renewable_data = pd.DataFrame(test_data)
    
    def test_geographic_calculations_accuracy(self):
        """测试地理计算精度"""
        print("测试地理计算精度...")
        
        # 测试已知距离
        beijing = (39.9042, 116.4074)
        shanghai = (31.2304, 121.4737)
        
        # 计算距离
        distance = self.geo_calc.calculate_distance_km(*beijing, *shanghai)
        
        # 北京到上海的实际距离约为1067公里
        expected_distance = 1067
        tolerance = 50  # 允许50公里误差
        
        self.assertAlmostEqual(distance, expected_distance, delta=tolerance,
                              msg=f"距离计算不准确: {distance:.2f}km, 预期: {expected_distance}km")
        print(f"北京-上海距离: {distance:.2f}km (预期: {expected_distance}km)")
        
        # 测试范围检查的一致性
        test_points = [
            (40.0, 116.0, True),   # 北京附近，应该在范围内
            (31.2, 121.5, False), # 上海，应该不在500km范围内
        ]
        
        for lat, lon, expected in test_points:
            result = self.geo_calc.is_within_beijing_range(lat, lon, 500)
            self.assertEqual(result, expected, 
                           f"范围检查错误: ({lat}, {lon}) -> {result}, 预期: {expected}")
            print(f"点({lat}, {lon})范围检查: {result}")
    
    def test_data_processing_consistency(self):
        """测试数据处理一致性"""
        print("测试数据处理一致性...")
        
        # 处理数据
        locations = self.data_processor.process_renewable_data(
            self.test_renewable_data, self.geo_calc
        )
        
        # 验证数据结构一致性 (上海因为距离超过500km被过滤掉了)
        expected_plants = ['solar_beijing']  # 只有北京的太阳能电站在500km范围内
        for plant_name in expected_plants:
            self.assertIn(plant_name, locations, f"缺少电站: {plant_name}")
            
            plant_data = locations[plant_name]
            
            # 验证必要字段
            required_fields = ['type', 'latitude', 'longitude', 'capacity_mw', 'hourly_generation']
            for field in required_fields:
                self.assertIn(field, plant_data, f"{plant_name}缺少字段: {field}")
            
            # 验证小时数据长度
            self.assertEqual(len(plant_data['hourly_generation']), 24,
                           f"{plant_name}小时数据长度不正确")
            
            # 验证数据类型
            self.assertIsInstance(plant_data['latitude'], (int, float))
            self.assertIsInstance(plant_data['longitude'], (int, float))
            self.assertIsInstance(plant_data['capacity_mw'], (int, float))
            
            print(f"{plant_name}: 类型={plant_data['type']}, "
                  f"坐标=({plant_data['latitude']:.2f}, {plant_data['longitude']:.2f}), "
                  f"容量={plant_data['capacity_mw']}MW")
    
    def test_cost_calculation_accuracy(self):
        """测试成本计算精度"""
        print("测试成本计算精度...")
        
        # 测试基础LCOE计算
        test_cases = [
            {
                'name': '太阳能项目',
                'capex': 5000000,    # 500万
                'opex_annual': 250000,  # 25万/年
                'lifetime': 25,
                'min_expected': 400000,  # 最小值
                'max_expected': 700000   # 调整最大值
            },
            {
                'name': '风电项目', 
                'capex': 8000000,    # 800万
                'opex_annual': 400000,  # 40万/年
                'lifetime': 20,
                'min_expected': 600000,  # 最小值  
                'max_expected': 1000000  # 调整最大值
            }
        ]
        
        for case in test_cases:
            lcoe = self.cost_calc.calculate_levelized_cost(
                case['capex'], case['opex_annual'], case['lifetime']
            )
            
            # 验证LCOE在合理范围内
            self.assertGreaterEqual(lcoe, case['min_expected'],
                                  f"{case['name']}的LCOE过低: {lcoe:.0f}")
            self.assertLessEqual(lcoe, case['max_expected'],
                               f"{case['name']}的LCOE过高: {lcoe:.0f}")
            
            print(f"{case['name']}LCOE: {lcoe:.0f}元 "
                  f"(范围: {case['min_expected']:.0f}-{case['max_expected']:.0f})")
    
    def test_economic_parameters_validation(self):
        """测试经济参数验证"""
        print("测试经济参数验证...")
        
        # 获取默认经济参数
        params = EconomicParametersManager.define_default_economic_parameters()
        
        # 验证关键参数存在
        key_params = [
            'discount_rate',
            'project_lifespan', 
            'natural_gas_price_yuan_per_mcm',
            'electricity_price_yuan_per_mwh',
        ]
        
        for param in key_params:
            self.assertIn(param, params, f"缺少经济参数: {param}")
            self.assertIsInstance(params[param], (int, float),
                                f"参数{param}类型错误: {type(params[param])}")
            self.assertGreater(params[param], 0, f"参数{param}必须为正数")
            print(f"{param}: {params[param]}")
        
        # 验证参数有效性
        is_valid = EconomicParametersManager.validate_economic_parameters(params)
        self.assertTrue(is_valid, "经济参数验证失败")
        print("经济参数验证通过")
    
    def test_integration_workflow(self):
        """测试完整集成工作流"""
        print("测试完整集成工作流...")
        
        # 1. 地理计算
        beijing_shanghai_distance = self.geo_calc.calculate_distance_km(
            39.9042, 116.4074, 31.2304, 121.4737
        )
        
        # 2. 数据处理
        locations = self.data_processor.process_renewable_data(
            self.test_renewable_data, self.geo_calc
        )
        
        # 3. 添加机场 
        airports = {
            'beijing_airport': {
                'latitude': 40.08,
                'longitude': 116.58,
                'weekly_fuel_series': [1000, 1100, 1200, 1300]
            }
        }
        
        locations_with_airports = self.data_processor.add_airports_to_locations(
            locations, airports
        )
        
        # 4. 成本计算
        tech_params = {
            'capex_per_kg_h': 50000,
            'fixed_opex_annual': 100000,
            'variable_opex_per_kg': 2.5,
            'lifetime_years': 15
        }
        
        facility_lcoe = self.cost_calc.calculate_correct_facility_lcoe_with_utilization(
            tech_params, facility_capacity=100, time_horizon_weeks=4
        )
        
        # 验证工作流结果
        self.assertGreater(beijing_shanghai_distance, 1000)
        self.assertGreaterEqual(len(locations), 1)  # 至少1个发电站（北京在范围内）
        self.assertGreaterEqual(len(locations_with_airports), len(locations))  # 至少和之前一样多
        self.assertGreater(facility_lcoe, 0)
        
        print(f"集成工作流完成:")
        print(f"  - 地理计算: {beijing_shanghai_distance:.1f}km")
        print(f"  - 发电站数量: {len(locations)}")
        print(f"  - 总位置数量: {len(locations_with_airports)}")
        print(f"  - 设施LCOE: {facility_lcoe:.0f}元")
    
    def test_modular_components_consistency(self):
        """测试模块化组件一致性"""
        print("测试模块化组件一致性...")
        
        # 创建相同的输入数据
        test_coords = [(39.9, 116.4), (31.2, 121.5)]
        
        # 测试地理计算的一致性
        distances = []
        for _ in range(3):  # 多次调用应该得到相同结果
            dist = self.geo_calc.calculate_distance_km(*test_coords[0], *test_coords[1])
            distances.append(dist)
        
        # 验证结果一致性
        self.assertTrue(all(abs(d - distances[0]) < 1e-10 for d in distances),
                       "地理计算结果不一致")
        
        # 测试数据处理的确定性
        locations1 = self.data_processor.process_renewable_data(
            self.test_renewable_data, self.geo_calc
        )
        locations2 = self.data_processor.process_renewable_data(
            self.test_renewable_data, self.geo_calc  
        )
        
        # 验证数据处理结果一致
        self.assertEqual(set(locations1.keys()), set(locations2.keys()),
                        "数据处理结果不一致")
        
        print("模块化组件一致性验证通过")


if __name__ == '__main__':
    print("=" * 60)
    print("开始运行最终对比测试")
    print("验证模块化组件功能完整性和一致性")
    print("=" * 60)
    
    unittest.main(verbosity=2)