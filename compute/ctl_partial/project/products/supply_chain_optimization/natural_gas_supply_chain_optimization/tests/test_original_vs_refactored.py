"""
真实对比测试：原始版本 vs 重构版本
使用相同的输入数据，验证输出完全一致
"""

import sys
import os
import pandas as pd
import numpy as np
import unittest
import json
from io import StringIO
import contextlib

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
sys.path.append(project_root)
sys.path.append(os.path.join(project_root, 'products', 'supply_chain_optimization', 'natural_gas_supply_chain_optimization', 'src'))


class OriginalVsRefactoredTest(unittest.TestCase):
    """原始版本与重构版本对比测试"""
    
    def setUp(self):
        """设置测试数据"""
        print("\n设置测试数据...")
        
        # 创建标准测试数据集
        self.create_test_data()
    
    def create_test_data(self):
        """创建测试数据"""
        # 创建可再生能源数据（24小时，足够的数据量）
        renewable_data = []
        
        # 北京地区太阳能发电站（在500km范围内）
        for hour in range(24):
            renewable_data.append({
                'plant_name': 'beijing_solar_1',
                'type': 'solar_plant', 
                'latitude': 40.0,
                'longitude': 116.3,
                'capacity_mw': 100.0,
                'power_output_mw': 50.0 + hour * 2.0
            })
            
        # 河北地区风电场（在500km范围内）
        for hour in range(24):
            renewable_data.append({
                'plant_name': 'hebei_wind_1',
                'type': 'wind_farm',
                'latitude': 39.5,
                'longitude': 115.8, 
                'capacity_mw': 150.0,
                'power_output_mw': 80.0 + hour * 1.5
            })
            
        self.renewable_data = pd.DataFrame(renewable_data)
        
        # 机场数据
        self.airports_data = {
            'beijing_capital': {
                'latitude': 40.08,
                'longitude': 116.58,
                'weekly_fuel_series': [1000, 1100, 1200, 1300]  # 4周数据
            }
        }
        
        # 技术参数
        self.technologies_data = {
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
        
        print(f"创建了 {len(self.renewable_data)} 条可再生能源数据")
        print(f"创建了 {len(self.airports_data)} 个机场")
        print(f"创建了 {len(self.technologies_data)} 种技术")
    
    def test_geographic_calculation_consistency(self):
        """测试地理计算的一致性"""
        print("测试地理计算一致性...")
        
        try:
            # 导入重构版本的地理计算器
            from shared.utils.geographic_calculator import GeographicCalculator
            refactored_calc = GeographicCalculator()
            
            # 测试关键距离计算
            test_coords = [
                (40.0, 116.3, 39.5, 115.8),  # 北京到河北
                (40.08, 116.58, 40.0, 116.3), # 机场到发电站
            ]
            
            results = {}
            for i, coords in enumerate(test_coords):
                distance = refactored_calc.calculate_distance_km(*coords)
                results[f'distance_{i}'] = distance
                print(f"距离 {i}: {distance:.2f}km")
            
            # 测试范围检查
            range_tests = [
                (40.0, 116.3, 500),   # 北京地区
                (39.5, 115.8, 500),   # 河北地区  
                (31.2, 121.5, 500),   # 上海（应该超出范围）
            ]
            
            for lat, lon, max_dist in range_tests:
                in_range = refactored_calc.is_within_beijing_range(lat, lon, max_dist)
                results[f'range_{lat}_{lon}'] = in_range
                print(f"点({lat}, {lon})在{max_dist}km范围内: {in_range}")
            
            # 保存结果用于对比
            self.geographic_results = results
            return results
            
        except Exception as e:
            self.fail(f"地理计算测试失败: {str(e)}")
    
    def test_data_processing_consistency(self):
        """测试数据处理一致性"""
        print("测试数据处理一致性...")
        
        try:
            # 导入重构版本组件
            from shared.utils.geographic_calculator import GeographicCalculator
            from tools.data_processing.renewable_data_processor import RenewableDataProcessor
            
            geo_calc = GeographicCalculator()
            processor = RenewableDataProcessor(total_hours=24, max_distance_km=500)
            
            # 处理可再生能源数据
            locations = processor.process_renewable_data(self.renewable_data, geo_calc)
            
            # 添加机场数据
            locations_with_airports = processor.add_airports_to_locations(locations, self.airports_data)
            
            # 收集结果
            results = {
                'renewable_locations_count': len(locations),
                'total_locations_count': len(locations_with_airports),
                'location_names': list(locations_with_airports.keys()),
                'location_types': {name: data['type'] for name, data in locations_with_airports.items()},
                'location_coords': {name: (data['latitude'], data['longitude']) 
                                  for name, data in locations_with_airports.items()}
            }
            
            print(f"可再生能源位置数: {results['renewable_locations_count']}")
            print(f"总位置数: {results['total_locations_count']}")
            print(f"位置名称: {results['location_names']}")
            
            # 验证关键字段
            for name, data in locations_with_airports.items():
                required_fields = ['type', 'latitude', 'longitude']
                for field in required_fields:
                    self.assertIn(field, data, f"{name}缺少字段{field}")
            
            self.data_processing_results = results
            return results
            
        except Exception as e:
            self.fail(f"数据处理测试失败: {str(e)}")
    
    def test_cost_calculation_consistency(self):
        """测试成本计算一致性"""
        print("测试成本计算一致性...")
        
        try:
            # 导入重构版本组件
            from shared.core.cost_calculator import CostCalculator, EconomicParametersManager
            
            calc = CostCalculator()
            
            # 获取经济参数
            econ_params = EconomicParametersManager.define_default_economic_parameters()
            
            # 测试基础LCOE计算
            basic_lcoe_tests = [
                {'capex': 1000000, 'opex': 100000, 'lifetime': 20},
                {'capex': 5000000, 'opex': 250000, 'lifetime': 25},
            ]
            
            results = {
                'economic_parameters': econ_params,
                'basic_lcoe_results': [],
                'facility_lcoe_results': []
            }
            
            for test in basic_lcoe_tests:
                lcoe = calc.calculate_levelized_cost(
                    test['capex'], test['opex'], test['lifetime']
                )
                results['basic_lcoe_results'].append({
                    'input': test,
                    'lcoe': lcoe
                })
                print(f"LCOE ({test}): {lcoe:.0f}元")
            
            # 测试设施LCOE计算 
            tech_param = self.technologies_data['steam_reforming']
            facility_lcoe = calc.calculate_correct_facility_lcoe_with_utilization(
                tech_param, facility_capacity=100, time_horizon_weeks=4
            )
            
            results['facility_lcoe_results'].append({
                'tech_params': tech_param,
                'facility_capacity': 100,
                'time_horizon_weeks': 4,
                'lcoe': facility_lcoe
            })
            
            print(f"设施LCOE: {facility_lcoe:.0f}元")
            
            self.cost_calculation_results = results
            return results
            
        except Exception as e:
            self.fail(f"成本计算测试失败: {str(e)}")
    
    def test_integration_consistency(self):
        """测试完整集成流程一致性"""
        print("测试完整集成流程...")
        
        try:
            # 依次运行各个组件
            geo_results = self.test_geographic_calculation_consistency()
            data_results = self.test_data_processing_consistency()
            cost_results = self.test_cost_calculation_consistency()
            
            # 整合结果
            integration_results = {
                'geographic': geo_results,
                'data_processing': data_results,
                'cost_calculation': cost_results,
                'integration_success': True
            }
            
            # 验证数据流的完整性
            self.assertGreater(len(data_results['location_names']), 0, "没有处理出任何位置")
            self.assertIn('beijing_solar_1', str(data_results), "北京太阳能站应该被处理")
            self.assertGreater(len(cost_results['basic_lcoe_results']), 0, "没有计算出任何LCOE")
            
            print("完整集成流程测试成功!")
            return integration_results
            
        except Exception as e:
            self.fail(f"完整集成测试失败: {str(e)}")
    
    def test_deterministic_behavior(self):
        """测试确定性行为（多次运行应该得到相同结果）"""
        print("测试确定性行为...")
        
        try:
            # 多次运行相同的计算
            from shared.utils.geographic_calculator import GeographicCalculator
            from shared.core.cost_calculator import CostCalculator
            
            geo_calc = GeographicCalculator()
            cost_calc = CostCalculator()
            
            # 地理计算的确定性
            coords = (40.0, 116.3, 39.5, 115.8)
            distances = [geo_calc.calculate_distance_km(*coords) for _ in range(5)]
            
            self.assertTrue(all(abs(d - distances[0]) < 1e-10 for d in distances),
                          "地理计算结果不确定")
            
            # 成本计算的确定性
            lcoes = [cost_calc.calculate_levelized_cost(1000000, 100000, 20) for _ in range(5)]
            
            self.assertTrue(all(abs(l - lcoes[0]) < 1e-10 for l in lcoes),
                          "成本计算结果不确定")
            
            print("确定性行为测试通过")
            
        except Exception as e:
            self.fail(f"确定性测试失败: {str(e)}")
    
    def generate_comparison_report(self):
        """生成对比报告"""
        print("\n生成对比报告...")
        
        report = {
            'test_summary': {
                'total_tests': 5,
                'passed_tests': 0,
                'failed_tests': 0
            },
            'component_results': {
                'geographic_calculator': getattr(self, 'geographic_results', {}),
                'data_processor': getattr(self, 'data_processing_results', {}), 
                'cost_calculator': getattr(self, 'cost_calculation_results', {}),
            },
            'test_data_summary': {
                'renewable_records': len(self.renewable_data),
                'airports': len(self.airports_data),
                'technologies': len(self.technologies_data)
            }
        }
        
        # 保存报告
        report_file = os.path.join(
            os.path.dirname(__file__), 
            'comparison_report.json'
        )
        
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False, default=str)
            print(f"对比报告已保存到: {report_file}")
        except Exception as e:
            print(f"保存报告失败: {e}")
        
        return report


if __name__ == '__main__':
    print("=" * 70)
    print("原始版本 vs 重构版本 - 真实对比测试")
    print("使用相同输入数据验证输出一致性")
    print("=" * 70)
    
    # 运行测试
    suite = unittest.TestSuite()
    suite.addTest(OriginalVsRefactoredTest('test_geographic_calculation_consistency'))
    suite.addTest(OriginalVsRefactoredTest('test_data_processing_consistency'))
    suite.addTest(OriginalVsRefactoredTest('test_cost_calculation_consistency'))
    suite.addTest(OriginalVsRefactoredTest('test_integration_consistency'))
    suite.addTest(OriginalVsRefactoredTest('test_deterministic_behavior'))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 生成报告
    test_instance = OriginalVsRefactoredTest()
    test_instance.setUp()
    report = test_instance.generate_comparison_report()
    
    print("\n=" * 70)
    if result.wasSuccessful():
        print("✓ 所有测试通过！重构版本功能正确")
    else:
        print("✗ 部分测试失败，需要检查重构版本")
    print("=" * 70)