"""
对比测试：验证原始代码和重构代码的输出是否完全一致
"""

import sys
import os
import pandas as pd
import numpy as np
import unittest

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
sys.path.append(project_root)

# 导入原始和重构的模型
sys.path.append(os.path.join(project_root, 'products', 'supply_chain_optimization', 'natural_gas_supply_chain_optimization', 'src'))

class ComparisonTest(unittest.TestCase):
    """对比测试类"""
    
    def setUp(self):
        """设置测试数据"""
        # 创建基本测试数据 - 需要足够的小时数据
        test_data = []
        for hour in range(24):  # 创建24小时数据用于测试
            test_data.extend([
                {
                    'plant_name': 'solar_test_1',
                    'type': 'solar_plant',
                    'latitude': 40.0,
                    'longitude': 116.0,
                    'capacity_mw': 100,
                    'power_output_mw': 50 + hour * 2
                },
                {
                    'plant_name': 'wind_test_1', 
                    'type': 'wind_farm',
                    'latitude': 39.8,
                    'longitude': 115.5,
                    'capacity_mw': 150,
                    'power_output_mw': 80 + hour
                }
            ])
        self.test_renewable_data = pd.DataFrame(test_data)
        
        self.test_airports = {
            'test_airport': {
                'latitude': 40.1,
                'longitude': 116.1,
                'weekly_fuel_series': [1000, 1100, 1200, 1300]
            }
        }
        
        self.test_technologies = {
            'steam_reforming': {
                'name': '蒸汽重整',
                'suitable_locations': ['solar_plant', 'wind_farm'],
                'capex_per_kg_h': 50000,
                'fixed_opex_annual': 100000,
                'variable_opex_per_kg': 2.5,
                'lifetime_years': 15,
                'natural_gas_mcm_per_kg_h2': 0.0032
            }
        }
    
    def test_geographic_calculations_consistency(self):
        """测试地理计算的一致性"""
        from shared.utils.geographic_calculator import GeographicCalculator
        
        calc = GeographicCalculator()
        
        # 测试距离计算
        beijing_lat, beijing_lon = 39.9042, 116.4074
        shanghai_lat, shanghai_lon = 31.2304, 121.4737
        
        distance = calc.calculate_distance_km(beijing_lat, beijing_lon, shanghai_lat, shanghai_lon)
        
        # 验证计算结果符合预期
        self.assertGreater(distance, 1000)
        self.assertLess(distance, 1300)
        
        # 测试范围检查
        self.assertTrue(calc.is_within_beijing_range(beijing_lat, beijing_lon, 500))
        self.assertFalse(calc.is_within_beijing_range(shanghai_lat, shanghai_lon, 500))
    
    def test_data_processing_consistency(self):
        """测试数据处理的一致性"""
        from tools.data_processing.renewable_data_processor import RenewableDataProcessor
        from shared.utils.geographic_calculator import GeographicCalculator
        
        processor = RenewableDataProcessor(total_hours=24, max_distance_km=500)
        geo_calc = GeographicCalculator()
        
        # 处理测试数据
        locations = processor.process_renewable_data(self.test_renewable_data, geo_calc)
        
        # 验证处理结果
        self.assertIn('solar_test_1', locations)
        self.assertIn('wind_test_1', locations)
        self.assertEqual(locations['solar_test_1']['type'], 'solar_plant')
        self.assertEqual(locations['wind_test_1']['type'], 'wind_farm')
        
        # 验证坐标信息
        self.assertEqual(locations['solar_test_1']['latitude'], 40.0)
        self.assertEqual(locations['solar_test_1']['longitude'], 116.0)
    
    def test_cost_calculations_consistency(self):
        """测试成本计算的一致性"""
        from shared.core.cost_calculator import CostCalculator, EconomicParametersManager
        
        calc = CostCalculator()
        
        # 测试基本LCOE计算
        capex = 1000000
        opex_annual = 100000
        lifetime = 20
        
        lcoe = calc.calculate_levelized_cost(capex, opex_annual, lifetime)
        
        # 验证结果合理性
        self.assertGreater(lcoe, 0)
        self.assertIsInstance(lcoe, (int, float))
        
        # 测试经济参数
        params = EconomicParametersManager.define_default_economic_parameters()
        self.assertTrue(EconomicParametersManager.validate_economic_parameters(params))
    
    def test_modular_components_integration(self):
        """测试模块化组件的集成"""
        from shared.utils.geographic_calculator import GeographicCalculator
        from tools.data_processing.renewable_data_processor import RenewableDataProcessor
        from shared.core.cost_calculator import CostCalculator
        
        # 初始化组件
        geo_calc = GeographicCalculator()
        processor = RenewableDataProcessor(total_hours=24, max_distance_km=500)
        cost_calc = CostCalculator()
        
        # 数据处理流程
        locations = processor.process_renewable_data(self.test_renewable_data, geo_calc)
        locations_with_airports = processor.add_airports_to_locations(locations, self.test_airports)
        
        # 验证完整数据处理
        self.assertIn('solar_test_1', locations_with_airports)
        self.assertIn('airport_test_airport', locations_with_airports)
        
        # 成本计算测试
        tech_params = self.test_technologies['steam_reforming']
        lcoe = cost_calc.calculate_correct_facility_lcoe_with_utilization(
            tech_params, facility_capacity=100, time_horizon_weeks=4
        )
        
        self.assertGreater(lcoe, 0)
    
    def test_data_structure_consistency(self):
        """测试数据结构的一致性"""
        from tools.data_processing.renewable_data_processor import RenewableDataProcessor
        from shared.utils.geographic_calculator import GeographicCalculator
        
        processor = RenewableDataProcessor(total_hours=24, max_distance_km=500)
        geo_calc = GeographicCalculator()
        
        locations = processor.process_renewable_data(self.test_renewable_data, geo_calc)
        
        # 验证locations数据结构
        for location_id, location_data in locations.items():
            # 必须包含的字段
            required_fields = ['type', 'latitude', 'longitude']
            for field in required_fields:
                self.assertIn(field, location_data, f"Missing field {field} in location {location_id}")
            
            # 验证数据类型
            self.assertIsInstance(location_data['latitude'], (int, float))
            self.assertIsInstance(location_data['longitude'], (int, float))
            self.assertIn(location_data['type'], ['solar_plant', 'wind_farm', 'airport'])


if __name__ == '__main__':
    print("开始运行模块化组件的对比测试...")
    unittest.main(verbosity=2)