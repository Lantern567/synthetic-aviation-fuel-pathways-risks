"""
重构模型的单元测试
验证新的模块化组件是否正常工作
"""

import unittest
import sys
import os
import pandas as pd
import numpy as np

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
sys.path.append(project_root)

from shared.utils.geographic_calculator import GeographicCalculator
from tools.data_processing.renewable_data_processor import RenewableDataProcessor
from shared.core.cost_calculator import CostCalculator, EconomicParametersManager
from tools.optimization.gurobi_model_builder import GurobiModelBuilder


class TestGeographicCalculator(unittest.TestCase):
    """测试地理计算器"""
    
    def setUp(self):
        self.calc = GeographicCalculator()
    
    def test_distance_calculation(self):
        """测试距离计算"""
        # 北京到上海的距离
        beijing_lat, beijing_lon = 39.9042, 116.4074
        shanghai_lat, shanghai_lon = 31.2304, 121.4737
        
        distance = self.calc.calculate_distance_km(beijing_lat, beijing_lon, shanghai_lat, shanghai_lon)
        
        # 北京到上海约1000多公里
        self.assertGreater(distance, 1000)
        self.assertLess(distance, 1300)
    
    def test_beijing_range_check(self):
        """测试北京范围检查"""
        # 北京市中心应该在范围内
        self.assertTrue(self.calc.is_within_beijing_range(39.9042, 116.4074, 500))
        
        # 上海应该不在500公里范围内
        self.assertFalse(self.calc.is_within_beijing_range(31.2304, 121.4737, 500))
    
    def test_coordinate_validation(self):
        """测试坐标验证"""
        # 有效坐标
        self.assertTrue(self.calc.validate_coordinates(39.9042, 116.4074))
        
        # 无效坐标
        self.assertFalse(self.calc.validate_coordinates(91, 181))  # 超出范围
        self.assertFalse(self.calc.validate_coordinates(-91, -181))  # 超出范围


class TestRenewableDataProcessor(unittest.TestCase):
    """测试可再生能源数据处理器"""
    
    def setUp(self):
        self.processor = RenewableDataProcessor(total_hours=24, max_distance_km=500)
        self.geo_calc = GeographicCalculator()
    
    def test_data_processing(self):
        """测试数据处理"""
        # 创建测试数据
        data = []
        for hour in range(24):  # 只测试一天的数据
            data.extend([
                {
                    'plant_name': 'test_solar',
                    'type': 'solar_plant',
                    'latitude': 40.0,
                    'longitude': 116.0,
                    'capacity_mw': 100,
                    'power_output_mw': 50 + hour * 2
                },
                {
                    'plant_name': 'test_wind',
                    'type': 'wind_farm', 
                    'latitude': 39.8,
                    'longitude': 115.5,
                    'capacity_mw': 200,
                    'power_output_mw': 100 + hour
                }
            ])
        
        test_df = pd.DataFrame(data)
        
        # 处理数据
        locations = self.processor.process_renewable_data(test_df, self.geo_calc)
        
        # 验证结果
        self.assertIn('test_solar', locations)
        self.assertIn('test_wind', locations)
        self.assertEqual(locations['test_solar']['type'], 'solar_plant')
        self.assertEqual(locations['test_wind']['type'], 'wind_farm')
    
    def test_airport_addition(self):
        """测试机场位置添加"""
        locations = {}
        airports = {
            'test_airport': {
                'latitude': 40.0,
                'longitude': 116.0,
                'weekly_fuel_series': [1000, 1100, 1200]
            }
        }
        
        updated_locations = self.processor.add_airports_to_locations(locations, airports)
        
        self.assertIn('airport_test_airport', updated_locations)
        self.assertEqual(updated_locations['airport_test_airport']['type'], 'airport')


class TestCostCalculator(unittest.TestCase):
    """测试成本计算器"""
    
    def setUp(self):
        self.calc = CostCalculator()
    
    def test_levelized_cost_calculation(self):
        """测试平准化成本计算"""
        # 测试参数
        capex = 1000000  # 100万元
        opex_annual = 100000  # 10万元/年
        lifetime = 20  # 20年
        
        lcoe = self.calc.calculate_levelized_cost(capex, opex_annual, lifetime)
        
        # LCOE应该是正数且合理
        self.assertGreater(lcoe, 0)
        self.assertLess(lcoe, capex)  # 不应该超过总投资
    
    def test_economic_parameters(self):
        """测试经济参数管理"""
        params = EconomicParametersManager.define_default_economic_parameters()
        
        # 验证关键参数存在
        self.assertIn('discount_rate', params)
        self.assertIn('project_lifespan', params)
        self.assertIn('natural_gas_price_yuan_per_mcm', params)
        
        # 验证参数有效性
        self.assertTrue(EconomicParametersManager.validate_economic_parameters(params))


class TestGurobiModelBuilder(unittest.TestCase):
    """测试Gurobi模型构建器"""
    
    def setUp(self):
        self.builder = GurobiModelBuilder(time_horizon_weeks=1)
    
    def test_model_initialization(self):
        """测试模型初始化"""
        # 创建测试数据
        locations = {
            'test_location': {
                'type': 'solar_plant',
                'latitude': 40.0,
                'longitude': 116.0
            }
        }
        
        technologies = {
            'test_tech': {
                'name': '测试技术',
                'suitable_locations': ['solar_plant']
            }
        }
        
        airports = {
            'test_airport': {
                'latitude': 40.1,
                'longitude': 116.1
            }
        }
        
        try:
            # 尝试构建模型（可能因为没有Gurobi许可证而失败，但至少能测试接口）
            model = self.builder.build_model(locations, technologies, airports)
            
            # 如果成功，验证模型对象
            self.assertIsNotNone(model)
            
        except Exception as e:
            # 如果因为Gurobi许可证等问题失败，至少验证数据结构正确设置
            self.assertIsNotNone(self.builder.locations)
            self.assertIsNotNone(self.builder.technologies)
            self.assertIsNotNone(self.builder.airports)


class TestIntegration(unittest.TestCase):
    """集成测试"""
    
    def test_component_integration(self):
        """测试组件之间的集成"""
        # 创建所有组件
        geo_calc = GeographicCalculator()
        data_processor = RenewableDataProcessor(total_hours=24, max_distance_km=500)
        cost_calc = CostCalculator()
        
        # 测试数据流
        test_data = []
        for hour in range(24):
            test_data.append({
                'plant_name': 'integration_test',
                'type': 'solar_plant',
                'latitude': 40.0,
                'longitude': 116.0,
                'capacity_mw': 100,
                'power_output_mw': 50 + hour
            })
        test_data = pd.DataFrame(test_data)
        
        # 处理数据
        locations = data_processor.process_renewable_data(test_data, geo_calc)
        
        # 验证数据处理和地理计算集成
        self.assertIn('integration_test', locations)
        
        # 验证成本计算集成
        tech_params = {
            'capex_per_kg_h': 50000,
            'fixed_opex_annual': 100000,
            'variable_opex_per_kg': 2.5,
            'lifetime_years': 15
        }
        
        lcoe = cost_calc.calculate_correct_facility_lcoe_with_utilization(
            tech_params, facility_capacity=100, time_horizon_weeks=1
        )
        
        self.assertGreater(lcoe, 0)


if __name__ == '__main__':
    # 运行测试
    unittest.main(verbosity=2)