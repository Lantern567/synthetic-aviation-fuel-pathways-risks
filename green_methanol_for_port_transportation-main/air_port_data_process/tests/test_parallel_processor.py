"""
测试并行航班数据处理程序的功能
"""

import unittest
import os
import sys
import pandas as pd
import tempfile
import shutil
import multiprocessing as mp
from unittest.mock import patch, MagicMock

# 添加src路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from parallel_flight_processor import (
    get_optimal_worker_count,
    process_chunk_worker,
    load_and_split_data,
    parallel_process_flight_data
)

class TestParallelProcessor(unittest.TestCase):
    """测试并行处理器"""
    
    def setUp(self):
        """测试前的设置"""
        self.temp_dir = tempfile.mkdtemp()
        
        # 创建测试数据
        self.test_data = pd.DataFrame({
            '机型': ['波音737(中)', '空客320', '波音777', '空客330', '波音737(中)', '空客320'],
            '里程（公里）': [1500, 2000, 8000, 3500, 1200, 1800],
            '人数': [150, 120, 250, 180, 140, 130],
            '出发机场': ['北京', '上海', '广州', '深圳', '成都', '杭州'],
            '到达机场': ['上海', '广州', '北京', '成都', '重庆', '西安']
        })
        
        # 创建测试Excel文件
        self.test_excel_path = os.path.join(self.temp_dir, 'test_flights.xlsx')
        self.test_data.to_excel(self.test_excel_path, index=False)
    
    def tearDown(self):
        """测试后的清理"""
        shutil.rmtree(self.temp_dir)
    
    def test_get_optimal_worker_count(self):
        """测试获取最佳工作进程数"""
        worker_count = get_optimal_worker_count()
        
        # 应该返回合理的工作进程数
        self.assertIsInstance(worker_count, int)
        self.assertGreaterEqual(worker_count, 1)
        self.assertLessEqual(worker_count, mp.cpu_count())
    
    def test_load_and_split_data(self):
        """测试数据加载和分割功能"""
        chunks = load_and_split_data(self.test_excel_path, chunk_size=2)
        
        # 应该分成3个块（6条记录，每块2条）
        self.assertEqual(len(chunks), 3)
        
        # 检查每个块的结构
        for chunk_id, chunk_df in chunks:
            self.assertIsInstance(chunk_id, int)
            self.assertIsInstance(chunk_df, pd.DataFrame)
            self.assertLessEqual(len(chunk_df), 2)
            
            # 检查必要字段存在
            required_fields = ['机型', '里程（公里）', '人数']
            for field in required_fields:
                self.assertIn(field, chunk_df.columns)
        
        # 检查总记录数保持一致
        total_records = sum(len(chunk_df) for _, chunk_df in chunks)
        self.assertEqual(total_records, len(self.test_data))
    
    @patch('parallel_flight_processor.process_flight_data_with_pybada')
    def test_process_chunk_worker(self, mock_process):
        """测试单个块处理工作函数"""
        # 准备测试数据
        test_chunk = self.test_data.iloc[:2].copy()
        chunk_data = (0, test_chunk)
        
        # 模拟处理结果
        mock_result = test_chunk.copy()
        mock_result['ICAO代码'] = ['B737', 'A320']
        mock_result['载客率'] = [0.85, 0.90]
        mock_result['燃油消耗_kg'] = [3500.5, 3200.8]
        mock_result['燃油流量_kg_per_s'] = [0.95, 0.92]
        mock_result['巡航时间_hours'] = [1.5, 2.0]
        mock_result['计算方法'] = ['pybada', 'pybada']
        
        mock_process.return_value = mock_result
        
        # 调用工作函数
        chunk_id, processed_data, stats = process_chunk_worker(chunk_data)
        
        # 验证结果
        self.assertEqual(chunk_id, 0)
        self.assertIsNotNone(processed_data)
        self.assertEqual(len(processed_data), 2)
        
        # 验证统计信息
        self.assertIn('chunk_id', stats)
        self.assertIn('total_records', stats)
        self.assertIn('success_count', stats)
        self.assertIn('failed_count', stats)
        self.assertIn('processing_time', stats)
        self.assertIn('success_rate', stats)
        
        self.assertEqual(stats['chunk_id'], 0)
        self.assertEqual(stats['total_records'], 2)
        self.assertEqual(stats['success_count'], 2)
        self.assertEqual(stats['failed_count'], 0)
        self.assertEqual(stats['success_rate'], 100.0)
    
    def test_process_chunk_worker_error_handling(self):
        """测试工作函数的错误处理"""
        # 准备错误的数据（缺少必要字段）
        bad_data = pd.DataFrame({
            '错误字段': ['test1', 'test2']
        })
        chunk_data = (1, bad_data)
        
        # 调用工作函数，应该正确处理错误
        chunk_id, processed_data, stats = process_chunk_worker(chunk_data)
        
        # 验证错误处理
        self.assertEqual(chunk_id, 1)
        self.assertIsNone(processed_data)
        self.assertIn('error', stats)
        self.assertEqual(stats['success_count'], 0)
        self.assertGreater(stats['failed_count'], 0)
    
    @patch('parallel_flight_processor.process_chunk_worker')
    def test_parallel_process_flight_data_mock(self, mock_worker):
        """测试并行处理主函数（使用模拟）"""
        # 模拟工作函数返回
        def mock_worker_func(chunk_data):
            chunk_id, chunk_df = chunk_data
            
            # 创建模拟处理结果
            result_df = chunk_df.copy()
            result_df['ICAO代码'] = ['B737'] * len(result_df)
            result_df['载客率'] = [0.85] * len(result_df)
            result_df['燃油消耗_kg'] = [3500.0] * len(result_df)
            result_df['计算方法'] = ['pybada'] * len(result_df)
            
            stats = {
                'chunk_id': chunk_id,
                'total_records': len(result_df),
                'success_count': len(result_df),
                'failed_count': 0,
                'processing_time': 1.0,
                'success_rate': 100.0
            }
            
            return chunk_id, result_df, stats
        
        mock_worker.side_effect = mock_worker_func
        
        output_dir = os.path.join(self.temp_dir, 'parallel_results')
        
        # 运行并行处理（使用少量工作进程进行测试）
        results = parallel_process_flight_data(
            data_file_path=self.test_excel_path,
            output_dir=output_dir,
            chunk_size=2,
            max_workers=2
        )
        
        # 验证结果
        self.assertIsNotNone(results)
        self.assertEqual(len(results), len(self.test_data))
        self.assertTrue(all(results['计算方法'] == 'pybada'))
        
        # 验证输出目录创建
        self.assertTrue(os.path.exists(output_dir))
        
        # 验证结果文件生成
        result_files = [f for f in os.listdir(output_dir) if f.endswith('.xlsx')]
        self.assertGreater(len(result_files), 0)
    
    def test_data_cleaning_in_load_and_split(self):
        """测试数据清洗功能"""
        # 创建包含问题数据的测试文件
        dirty_data = pd.DataFrame({
            '机型': ['波音737(中)', '', 'nan', '空客320', '  '],
            '里程（公里）': [1500, 'abc', None, 2000, -100],
            '人数': [150, 0, -5, 120, None],
            '出发机场': ['北京', '上海', '广州', '深圳', '成都'],
            '到达机场': ['上海', '广州', '北京', '成都', '重庆']
        })
        
        dirty_excel_path = os.path.join(self.temp_dir, 'dirty_flights.xlsx')
        dirty_data.to_excel(dirty_excel_path, index=False)
        
        chunks = load_and_split_data(dirty_excel_path, chunk_size=10)
        
        # 应该只保留有效数据
        if chunks:
            total_valid_records = sum(len(chunk_df) for _, chunk_df in chunks)
            # 只有第一条和第四条数据是有效的
            self.assertEqual(total_valid_records, 1)  # 只有'空客320'那一条数据有效
    
    def test_empty_file_handling(self):
        """测试空文件处理"""
        empty_data = pd.DataFrame()
        empty_excel_path = os.path.join(self.temp_dir, 'empty_flights.xlsx')
        empty_data.to_excel(empty_excel_path, index=False)
        
        # 应该正确处理空文件
        with self.assertRaises(ValueError):
            load_and_split_data(empty_excel_path, chunk_size=10)

class TestPerformanceOptimization(unittest.TestCase):
    """测试性能优化相关功能"""
    
    def test_worker_count_constraints(self):
        """测试工作进程数的约束条件"""
        worker_count = get_optimal_worker_count()
        cpu_count = mp.cpu_count()
        
        # 工作进程数不应该超过CPU核心数
        self.assertLessEqual(worker_count, cpu_count)
        
        # 至少应该有1个工作进程
        self.assertGreaterEqual(worker_count, 1)
    
    def test_chunk_size_impact(self):
        """测试不同块大小的影响"""
        # 创建较大的测试数据集
        large_data = pd.DataFrame({
            '机型': ['波音737(中)'] * 100,
            '里程（公里）': list(range(1000, 1100)),
            '人数': [150] * 100,
        })
        
        temp_file = tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False)
        large_data.to_excel(temp_file.name, index=False)
        
        try:
            # 测试不同的块大小
            for chunk_size in [10, 25, 50]:
                chunks = load_and_split_data(temp_file.name, chunk_size=chunk_size)
                
                # 验证块数量正确
                expected_chunks = (len(large_data) - 1) // chunk_size + 1
                self.assertEqual(len(chunks), expected_chunks)
                
                # 验证总记录数保持一致
                total_records = sum(len(chunk_df) for _, chunk_df in chunks)
                self.assertEqual(total_records, len(large_data))
        
        finally:
            os.unlink(temp_file.name)

if __name__ == '__main__':
    # 设置多进程启动方法（测试兼容性）
    mp.set_start_method('spawn', force=True)
    
    # 运行所有测试
    unittest.main(verbosity=2) 