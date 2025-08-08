"""
燃油需求数据处理器单元测试
"""
import unittest
import pandas as pd
import numpy as np
import os
import tempfile
from pathlib import Path
import sys

# 添加src目录到Python路径
current_dir = Path(__file__).parent
project_root = current_dir.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

from fuel_demand_data_processor import FuelDemandDataProcessor


class TestFuelDemandDataProcessor(unittest.TestCase):
    """燃油需求数据处理器测试类"""
    
    def setUp(self):
        """设置测试环境"""
        # 创建测试数据
        self.test_data = pd.DataFrame({
            'airport_name': ['机场A', '机场A', '机场A', '机场A', '机场B', '机场B', '机场B', '机场B'],
            'longitude': [116.0, 116.0, 116.0, 116.0, 117.0, 117.0, 117.0, 117.0],
            'latitude': [39.0, 39.0, 39.0, 39.0, 38.0, 38.0, 38.0, 38.0],
            'week': ['2024_W01', '2024_W02', '2024_W03', '2024_W04', '2024_W01', '2024_W02', '2024_W03', '2024_W04'],
            'fuel_demand_kg': [100.0, 0.0, 200.0, 0.0, 0.0, 150.0, 0.0, 0.0]
        })
        
        # 创建临时文件
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', encoding='utf-8')
        self.test_data.to_csv(self.temp_file.name, index=False, encoding='utf-8')
        self.temp_file.close()
        
        # 创建处理器实例
        self.processor = FuelDemandDataProcessor(self.temp_file.name)
    
    def tearDown(self):
        """清理测试环境"""
        # 删除临时文件
        os.unlink(self.temp_file.name)
    
    def test_load_data(self):
        """测试数据加载功能"""
        data = self.processor.load_data()
        
        # 验证数据加载正确
        self.assertIsNotNone(data)
        self.assertEqual(len(data), 8)  # 8行数据
        self.assertTrue('airport_name' in data.columns)
        self.assertTrue('fuel_demand_kg' in data.columns)
        
        # 验证数据内容
        expected_airports = ['机场A', '机场B']
        actual_airports = sorted(data['airport_name'].unique())
        self.assertEqual(actual_airports, expected_airports)
    
    def test_analyze_data_structure(self):
        """测试数据结构分析功能"""
        self.processor.load_data()
        analysis = self.processor.analyze_data_structure()
        
        # 验证分析结果
        self.assertEqual(analysis['airport_count'], 2)
        self.assertEqual(analysis['week_count'], 4)
        self.assertEqual(analysis['total_records'], 8)
        self.assertEqual(analysis['zero_values'], 5)  # 5个零值
        self.assertAlmostEqual(analysis['zero_percentage'], 62.5)  # 62.5%的零值
    
    def test_forward_fill_fuel_demand(self):
        """测试前向填充功能"""
        self.processor.load_data()
        processed_data = self.processor.forward_fill_fuel_demand()
        
        # 验证处理结果
        self.assertIsNotNone(processed_data)
        
        # 验证机场A的填充结果
        airport_a_data = processed_data[processed_data['airport_name'] == '机场A'].sort_values('week')
        expected_values_a = [100.0, 100.0, 200.0, 200.0]  # W02用W01填充，W04用W03填充
        actual_values_a = airport_a_data['fuel_demand_kg'].tolist()
        self.assertEqual(actual_values_a, expected_values_a)
        
        # 验证机场B的填充结果
        airport_b_data = processed_data[processed_data['airport_name'] == '机场B'].sort_values('week')
        expected_values_b = [0.0, 150.0, 150.0, 150.0]  # W01保持0（没有前值），W03和W04用W02填充
        actual_values_b = airport_b_data['fuel_demand_kg'].tolist()
        self.assertEqual(actual_values_b, expected_values_b)
    
    def test_get_processing_summary(self):
        """测试处理总结功能"""
        self.processor.load_data()
        self.processor.forward_fill_fuel_demand()
        summary = self.processor.get_processing_summary()
        
        # 验证总结结果
        self.assertEqual(summary['original_zero_count'], 5)
        self.assertEqual(summary['processed_zero_count'], 1)  # 机场B的W01仍为0
        self.assertEqual(summary['filled_count'], 4)  # 填充了4个值
        self.assertAlmostEqual(summary['fill_rate'], 80.0)  # 80%填充率
    
    def test_save_processed_data(self):
        """测试数据保存功能"""
        self.processor.load_data()
        self.processor.forward_fill_fuel_demand()
        
        # 测试自动生成文件名保存
        output_path = self.processor.save_processed_data()
        
        # 验证文件已创建
        self.assertTrue(os.path.exists(output_path))
        
        # 验证保存的数据内容
        saved_data = pd.read_csv(output_path, encoding='utf-8')
        self.assertEqual(len(saved_data), 8)
        
        # 清理生成的文件
        os.unlink(output_path)
    
    def test_edge_cases(self):
        """测试边界情况"""
        # 测试空数据处理
        empty_processor = FuelDemandDataProcessor("nonexistent.csv")
        
        # 测试在未加载数据时调用其他方法
        with self.assertRaises(ValueError):
            empty_processor.analyze_data_structure()
        
        with self.assertRaises(ValueError):
            empty_processor.forward_fill_fuel_demand()
    
    def test_all_zero_data(self):
        """测试全零数据的处理"""
        # 创建全零数据
        all_zero_data = pd.DataFrame({
            'airport_name': ['机场C', '机场C', '机场C'],
            'longitude': [116.0, 116.0, 116.0],
            'latitude': [39.0, 39.0, 39.0],
            'week': ['2024_W01', '2024_W02', '2024_W03'],
            'fuel_demand_kg': [0.0, 0.0, 0.0]
        })
        
        # 创建临时文件
        temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', encoding='utf-8')
        all_zero_data.to_csv(temp_file.name, index=False, encoding='utf-8')
        temp_file.close()
        
        try:
            processor = FuelDemandDataProcessor(temp_file.name)
            processor.load_data()
            processed_data = processor.forward_fill_fuel_demand()
            
            # 全零数据应该保持不变
            self.assertEqual(processed_data['fuel_demand_kg'].sum(), 0.0)
            
        finally:
            os.unlink(temp_file.name)
    
    def test_no_zero_data(self):
        """测试无零值数据的处理"""
        # 创建无零值数据
        no_zero_data = pd.DataFrame({
            'airport_name': ['机场D', '机场D', '机场D'],
            'longitude': [116.0, 116.0, 116.0],
            'latitude': [39.0, 39.0, 39.0],
            'week': ['2024_W01', '2024_W02', '2024_W03'],
            'fuel_demand_kg': [100.0, 200.0, 300.0]
        })
        
        # 创建临时文件
        temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', encoding='utf-8')
        no_zero_data.to_csv(temp_file.name, index=False, encoding='utf-8')
        temp_file.close()
        
        try:
            processor = FuelDemandDataProcessor(temp_file.name)
            processor.load_data()
            processed_data = processor.forward_fill_fuel_demand()
            summary = processor.get_processing_summary()
            
            # 无零值数据应该保持不变
            self.assertEqual(summary['original_zero_count'], 0)
            self.assertEqual(summary['filled_count'], 0)
            
        finally:
            os.unlink(temp_file.name)


def run_tests():
    """运行所有测试"""
    unittest.main(verbosity=2)


if __name__ == '__main__':
    run_tests()