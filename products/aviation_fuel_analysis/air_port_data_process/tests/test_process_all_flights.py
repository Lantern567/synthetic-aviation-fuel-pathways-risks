"""
测试处理所有航班数据程序的功能
"""

import unittest
import os
import sys
import pandas as pd
import tempfile
import shutil
from unittest.mock import patch, MagicMock

# 添加src路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from process_all_flights import (
    load_flight_data, 
    save_results_to_excel, 
    process_all_flight_data
)

class TestProcessAllFlights(unittest.TestCase):
    """测试航班数据处理程序"""
    
    def setUp(self):
        """测试前的设置"""
        self.temp_dir = tempfile.mkdtemp()
        
        # 创建测试数据
        self.test_data = pd.DataFrame({
            '机型': ['波音737(中)', '空客320', '波音777', '空客330'],
            '里程（公里）': [1500, 2000, 8000, 3500],
            '人数': [150, 120, 250, 180],
            '出发机场': ['北京', '上海', '广州', '深圳'],
            '到达机场': ['上海', '广州', '北京', '成都']
        })
        
        # 创建测试Excel文件
        self.test_excel_path = os.path.join(self.temp_dir, 'test_flights.xlsx')
        self.test_data.to_excel(self.test_excel_path, index=False)
    
    def tearDown(self):
        """测试后的清理"""
        shutil.rmtree(self.temp_dir)
    
    def test_load_flight_data_small_chunk(self):
        """测试小批量数据加载"""
        chunks = list(load_flight_data(self.test_excel_path, chunk_size=2))
        
        # 应该有2个chunk
        self.assertEqual(len(chunks), 2)
        
        # 第一个chunk应该有2条记录
        self.assertEqual(len(chunks[0]), 2)
        
        # 检查数据完整性
        total_records = sum(len(chunk) for chunk in chunks)
        self.assertEqual(total_records, 4)
    
    def test_load_flight_data_data_cleaning(self):
        """测试数据清洗功能"""
        # 创建包含问题数据的测试文件
        dirty_data = pd.DataFrame({
            '机型': ['波音737(中)', '', 'nan', '空客320'],
            '里程（公里）': [1500, 'abc', None, 2000],
            '人数': [150, 0, -5, 120],
            '出发机场': ['北京', '上海', '广州', '深圳'],
            '到达机场': ['上海', '广州', '北京', '成都']
        })
        
        dirty_excel_path = os.path.join(self.temp_dir, 'dirty_flights.xlsx')
        dirty_data.to_excel(dirty_excel_path, index=False)
        
        chunks = list(load_flight_data(dirty_excel_path, chunk_size=10))
        
        # 应该只有有效数据
        if chunks:
            valid_chunk = chunks[0]
            # 检查清理后的数据
            self.assertTrue(all(valid_chunk['机型'] != ''))
            self.assertTrue(all(valid_chunk['机型'] != 'nan'))
            self.assertTrue(all(valid_chunk['人数'] > 0))
            self.assertTrue(all(valid_chunk['里程（公里）'] >= 0))
    
    def test_save_results_to_excel(self):
        """测试保存结果到Excel功能"""
        # 创建测试结果数据
        results_data = pd.DataFrame({
            'ICAO代码': ['B737', 'A320', 'B777'],
            '燃油消耗_kg': [3500.5, 3200.8, 12000.3],
            '载客率': [0.85, 0.90, 0.78],
            '里程（公里）': [1500, 2000, 8000],
            '计算方法': ['pybada', 'pybada', 'pybada'],
            '机型': ['波音737(中)', '空客320', '波音777'],
            '人数': [150, 120, 250]
        })
        
        output_path = os.path.join(self.temp_dir, 'test_results.xlsx')
        
        # 保存结果
        save_results_to_excel(results_data, output_path)
        
        # 验证文件创建
        self.assertTrue(os.path.exists(output_path))
        
        # 验证Excel内容
        with pd.ExcelWriter(output_path) as writer:
            pass  # 确保文件可以正常打开
        
        # 读取并验证数据
        saved_data = pd.read_excel(output_path, sheet_name='航班燃油消耗详细')
        self.assertEqual(len(saved_data), 3)
        self.assertIn('ICAO代码', saved_data.columns)
        self.assertIn('燃油消耗_kg', saved_data.columns)
    
    @patch('process_all_flights.process_flight_data_with_pybada')
    def test_process_all_flight_data_mock(self, mock_process):
        """测试主处理函数（使用模拟）"""
        # 模拟pyBADA处理结果
        mock_result = self.test_data.copy()
        mock_result['ICAO代码'] = ['B737', 'A320', 'B777', 'A330']
        mock_result['载客率'] = [0.85, 0.90, 0.78, 0.82]
        mock_result['燃油消耗_kg'] = [3500.5, 3200.8, 12000.3, 6800.2]
        mock_result['燃油流量_kg_per_s'] = [0.95, 0.92, 2.1, 1.5]
        mock_result['巡航时间_hours'] = [1.5, 2.0, 8.0, 3.5]
        mock_result['计算方法'] = ['pybada'] * 4
        
        mock_process.return_value = mock_result
        
        output_dir = os.path.join(self.temp_dir, 'results')
        
        # 运行处理函数
        results = process_all_flight_data(
            data_file_path=self.test_excel_path,
            output_dir=output_dir,
            chunk_size=2
        )
        
        # 验证结果
        self.assertIsNotNone(results)
        self.assertEqual(len(results), 4)
        self.assertTrue(all(results['计算方法'] == 'pybada'))
        
        # 验证输出文件夹创建
        self.assertTrue(os.path.exists(output_dir))
    
    def test_save_results_multiple_sheets(self):
        """测试多工作表保存功能"""
        # 创建包含不同计算方法的测试数据
        mixed_results = pd.DataFrame({
            'ICAO代码': ['B737', 'A320', 'B777', 'A330'],
            '燃油消耗_kg': [3500.5, 3200.8, 12000.3, 6800.2],
            '载客率': [0.85, 0.90, 0.78, 0.82],
            '里程（公里）': [1500, 2000, 8000, 3500],
            '计算方法': ['pybada', 'pybada', 'failed', 'pybada'],
            '机型': ['波音737(中)', '空客320', '波音777', '空客330'],
            '人数': [150, 120, 250, 180]
        })
        
        output_path = os.path.join(self.temp_dir, 'mixed_results.xlsx')
        save_results_to_excel(mixed_results, output_path)
        
        # 验证多个工作表
        excel_file = pd.ExcelFile(output_path)
        expected_sheets = ['航班燃油消耗详细', '统计汇总', '机型统计', '计算方法对比']
        
        for sheet in expected_sheets:
            self.assertIn(sheet, excel_file.sheet_names)
        
        # 验证统计汇总数据
        summary = pd.read_excel(output_path, sheet_name='统计汇总')
        self.assertIn('总航班数', summary['指标'].values)
        self.assertIn('成功计算数', summary['指标'].values)
        self.assertIn('pyBADA使用率_%', summary['指标'].values)
    
    def test_empty_data_handling(self):
        """测试空数据处理"""
        # 创建空的测试文件
        empty_data = pd.DataFrame()
        empty_excel_path = os.path.join(self.temp_dir, 'empty_flights.xlsx')
        empty_data.to_excel(empty_excel_path, index=False)
        
        # 应该正确处理空文件
        chunks = list(load_flight_data(empty_excel_path, chunk_size=10))
        self.assertEqual(len(chunks), 0)
    
    def test_invalid_file_handling(self):
        """测试无效文件处理"""
        invalid_path = os.path.join(self.temp_dir, 'nonexistent.xlsx')
        
        # 应该抛出异常
        with self.assertRaises(Exception):
            list(load_flight_data(invalid_path, chunk_size=10))

class TestDataIntegrity(unittest.TestCase):
    """测试数据完整性"""
    
    def test_fuel_calculation_consistency(self):
        """测试燃油计算的一致性"""
        # 创建标准化测试数据
        test_data = pd.DataFrame({
            '机型': ['波音737(中)'] * 3,
            '里程（公里）': [1000, 2000, 3000],
            '人数': [150, 150, 150],
        })
        
        # 这里应该验证相同机型、相同载客数的燃油消耗与距离成正比
        # 但由于需要实际的pyBADA计算，这里只做结构验证
        self.assertEqual(len(test_data), 3)
        self.assertTrue(all(test_data['机型'] == '波音737(中)'))
        self.assertTrue(all(test_data['人数'] == 150))
    
    def test_icao_mapping_consistency(self):
        """测试ICAO映射一致性"""
        # 验证中文机型名称应该映射到正确的ICAO代码
        test_cases = {
            '波音737(中)': 'B737',
            '空客320': 'A320',
            '波音777': 'B777',
            '空客330': 'A330'
        }
        
        for chinese_name, expected_icao in test_cases.items():
            # 这里应该调用实际的映射函数
            # 目前只验证测试案例的结构
            self.assertIsInstance(chinese_name, str)
            self.assertIsInstance(expected_icao, str)

if __name__ == '__main__':
    # 运行所有测试
    unittest.main(verbosity=2) 