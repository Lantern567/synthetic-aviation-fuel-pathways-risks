"""
机场燃油量图表可视化模块单元测试
"""

import unittest
import os
import sys
import pandas as pd
import numpy as np
import tempfile
import shutil
from unittest.mock import patch, MagicMock
from datetime import datetime

# 添加源代码目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from airport_fuel_charts import AirportFuelCharts

class TestAirportFuelCharts(unittest.TestCase):
    """机场燃油量图表可视化功能测试"""
    
    def setUp(self):
        """测试前设置"""
        # 创建临时目录
        self.test_dir = tempfile.mkdtemp()
        self.data_dir = os.path.join(self.test_dir, 'data')
        self.results_dir = os.path.join(self.test_dir, 'results')
        
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.results_dir, exist_ok=True)
        
        # 创建测试数据
        self.create_test_data()
        
        # 初始化可视化器
        self.visualizer = AirportFuelCharts(data_dir=self.data_dir, results_dir=self.results_dir)
    
    def tearDown(self):
        """测试后清理"""
        # 删除临时目录
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def create_test_data(self):
        """创建测试数据"""
        # 创建燃油计算结果测试数据
        fuel_data = {
            '起飞机场': ['首都机场', '浦东机场', '白云机场', '深圳机场', '成都机场'] * 20,
            '燃油消耗_kg': np.random.normal(5000, 1000, 100),
            '日期': pd.date_range('2024-01-01', '2024-12-31', periods=100),
            '航班号': [f'CA{i:04d}' for i in range(100)]
        }
        
        fuel_df = pd.DataFrame(fuel_data)
        
        # 保存测试数据
        test_file = os.path.join(self.data_dir, '并行计算结果_20240101_000000.xlsx')
        fuel_df.to_excel(test_file, index=False)
    
    def test_init(self):
        """测试初始化"""
        self.assertIsNotNone(self.visualizer)
        self.assertEqual(self.visualizer.data_dir, self.data_dir)
        self.assertEqual(self.visualizer.results_dir, self.results_dir)
        self.assertTrue(os.path.exists(self.visualizer.charts_dir))
    
    def test_load_fuel_calculation_results(self):
        """测试加载燃油计算结果"""
        df = self.visualizer.load_fuel_calculation_results()
        
        self.assertIsInstance(df, pd.DataFrame)
        self.assertGreater(len(df), 0)
        self.assertIn('起飞机场', df.columns)
        self.assertIn('燃油消耗_kg', df.columns)
    
    def test_aggregate_fuel_by_airport_2024(self):
        """测试按机场聚合燃油量数据"""
        fuel_df = self.visualizer.load_fuel_calculation_results()
        aggregated = self.visualizer.aggregate_fuel_by_airport_2024(fuel_df)
        
        self.assertIsInstance(aggregated, pd.DataFrame)
        self.assertGreater(len(aggregated), 0)
        
        expected_columns = ['机场名称', '总燃油量', '航班数量', '平均燃油量']
        for col in expected_columns:
            self.assertIn(col, aggregated.columns)
        
        # 检查数据是否按总燃油量降序排列
        self.assertTrue(aggregated['总燃油量'].is_monotonic_decreasing)
    
    @patch('matplotlib.pyplot.savefig')
    @patch('matplotlib.pyplot.figure')
    def test_create_top_airports_bar_chart(self, mock_figure, mock_savefig):
        """测试创建柱状图"""
        fuel_df = self.visualizer.load_fuel_calculation_results()
        aggregated = self.visualizer.aggregate_fuel_by_airport_2024(fuel_df)
        
        # 模拟matplotlib
        mock_fig = MagicMock()
        mock_figure.return_value = mock_fig
        
        output_path = self.visualizer.create_top_airports_bar_chart(aggregated, top_n=5)
        
        self.assertIsNotNone(output_path)
        self.assertTrue(output_path.endswith('.png'))
        mock_savefig.assert_called_once()
    
    @patch('matplotlib.pyplot.savefig')
    @patch('matplotlib.pyplot.figure')
    def test_create_fuel_vs_flights_scatter(self, mock_figure, mock_savefig):
        """测试创建散点图"""
        fuel_df = self.visualizer.load_fuel_calculation_results()
        aggregated = self.visualizer.aggregate_fuel_by_airport_2024(fuel_df)
        
        mock_fig = MagicMock()
        mock_figure.return_value = mock_fig
        
        output_path = self.visualizer.create_fuel_vs_flights_scatter(aggregated)
        
        self.assertIsNotNone(output_path)
        self.assertTrue(output_path.endswith('.png'))
        mock_savefig.assert_called_once()
    
    @patch('matplotlib.pyplot.savefig')
    @patch('matplotlib.pyplot.figure')
    def test_create_fuel_distribution_pie_chart(self, mock_figure, mock_savefig):
        """测试创建饼图"""
        fuel_df = self.visualizer.load_fuel_calculation_results()
        aggregated = self.visualizer.aggregate_fuel_by_airport_2024(fuel_df)
        
        mock_fig = MagicMock()
        mock_figure.return_value = mock_fig
        
        output_path = self.visualizer.create_fuel_distribution_pie_chart(aggregated, top_n=3)
        
        self.assertIsNotNone(output_path)
        self.assertTrue(output_path.endswith('.png'))
        mock_savefig.assert_called_once()
    
    @patch('matplotlib.pyplot.savefig')
    @patch('matplotlib.pyplot.subplots')
    def test_create_fuel_boxplot(self, mock_subplots, mock_savefig):
        """测试创建箱型图"""
        fuel_df = self.visualizer.load_fuel_calculation_results()
        aggregated = self.visualizer.aggregate_fuel_by_airport_2024(fuel_df)
        
        # 模拟subplots返回值
        mock_fig = MagicMock()
        mock_axes = [[MagicMock(), MagicMock()], [MagicMock(), MagicMock()]]
        mock_subplots.return_value = (mock_fig, mock_axes)
        
        output_path = self.visualizer.create_fuel_boxplot(aggregated)
        
        self.assertIsNotNone(output_path)
        self.assertTrue(output_path.endswith('.png'))
        mock_savefig.assert_called_once()
    
    @patch('matplotlib.pyplot.savefig')
    @patch('matplotlib.pyplot.figure')
    def test_create_comprehensive_dashboard(self, mock_figure, mock_savefig):
        """测试创建综合仪表板"""
        fuel_df = self.visualizer.load_fuel_calculation_results()
        aggregated = self.visualizer.aggregate_fuel_by_airport_2024(fuel_df)
        
        mock_fig = MagicMock()
        mock_fig.add_gridspec.return_value = MagicMock()
        mock_fig.add_subplot.return_value = MagicMock()
        mock_figure.return_value = mock_fig
        
        output_path = self.visualizer.create_comprehensive_dashboard(aggregated)
        
        self.assertIsNotNone(output_path)
        self.assertTrue(output_path.endswith('.png'))
        mock_savefig.assert_called_once()
    
    def test_generate_fuel_analysis_report(self):
        """测试生成分析报告"""
        fuel_df = self.visualizer.load_fuel_calculation_results()
        aggregated = self.visualizer.aggregate_fuel_by_airport_2024(fuel_df)
        
        output_path = self.visualizer.generate_fuel_analysis_report(aggregated)
        
        self.assertIsNotNone(output_path)
        self.assertTrue(output_path.endswith('.txt'))
        self.assertTrue(os.path.exists(output_path))
        
        # 检查报告内容
        with open(output_path, 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertIn('2024年各机场航班燃油消耗分析报告', content)
            self.assertIn('总体统计', content)
            self.assertIn('前10名机场', content)

class TestAirportFuelChartsIntegration(unittest.TestCase):
    """机场燃油量图表可视化集成测试"""
    
    def setUp(self):
        """测试前设置"""
        self.test_dir = tempfile.mkdtemp()
        self.data_dir = os.path.join(self.test_dir, 'data')
        self.results_dir = os.path.join(self.test_dir, 'results')
        
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.results_dir, exist_ok=True)
        
        # 创建更复杂的测试数据
        self.create_comprehensive_test_data()
        
        self.visualizer = AirportFuelCharts(data_dir=self.data_dir, results_dir=self.results_dir)
    
    def tearDown(self):
        """测试后清理"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def create_comprehensive_test_data(self):
        """创建综合测试数据"""
        np.random.seed(42)  # 确保测试结果可重现
        
        airports = ['首都机场', '浦东机场', '白云机场', '深圳机场', '成都机场', 
                   '双流机场', '萧山机场', '天河机场', '江北机场', '禄口机场']
        
        # 生成1000条测试记录
        data = []
        for i in range(1000):
            airport = np.random.choice(airports)
            base_fuel = np.random.normal(4000, 800)  # 基础燃油量
            
            # 根据机场调整燃油量（模拟不同机场的特点）
            if airport in ['首都机场', '浦东机场']:
                fuel = base_fuel * np.random.uniform(1.5, 2.0)  # 大机场燃油量更高
            elif airport in ['白云机场', '深圳机场']:
                fuel = base_fuel * np.random.uniform(1.2, 1.8)
            else:
                fuel = base_fuel * np.random.uniform(0.8, 1.3)
            
            data.append({
                '起飞机场': airport,
                '燃油消耗_kg': max(fuel, 1000),  # 确保最小值
                '日期': pd.Timestamp('2024-01-01') + pd.Timedelta(days=i % 365),
                '航班号': f'CA{i:04d}',
                '机型': np.random.choice(['B737', 'A320', 'B777', 'A330']),
                '里程': np.random.normal(1500, 500)
            })
        
        fuel_df = pd.DataFrame(data)
        
        # 保存测试数据
        test_file = os.path.join(self.data_dir, '并行计算结果_20241201_120000.xlsx')
        fuel_df.to_excel(test_file, index=False)
    
    @patch('matplotlib.pyplot.figure')
    @patch('matplotlib.pyplot.subplots')
    @patch('matplotlib.pyplot.savefig')
    @patch('matplotlib.pyplot.close')
    def test_complete_analysis_workflow(self, mock_close, mock_savefig, mock_subplots, mock_figure):
        """测试完整分析工作流程"""
        # 模拟matplotlib对象
        mock_fig = MagicMock()
        mock_axes = [[MagicMock(), MagicMock()], [MagicMock(), MagicMock()]]
        
        mock_figure.return_value = mock_fig
        mock_subplots.return_value = (mock_fig, mock_axes)
        mock_fig.add_gridspec.return_value = MagicMock()
        mock_fig.add_subplot.return_value = MagicMock()
        
        # 运行完整分析
        results = self.visualizer.run_complete_analysis()
        
        # 验证返回结果
        self.assertIsInstance(results, dict)
        
        expected_keys = ['bar_chart', 'scatter_plot', 'pie_chart', 'boxplot', 'dashboard', 'report']
        for key in expected_keys:
            self.assertIn(key, results)
            self.assertIsNotNone(results[key])
        
        # 验证图表文件路径
        for key in expected_keys[:-1]:  # 除了report，其他都是图片
            self.assertTrue(results[key].endswith('.png'))
        
        # 验证报告文件路径
        self.assertTrue(results['report'].endswith('.txt'))
        
        # 验证matplotlib调用
        self.assertGreater(mock_savefig.call_count, 0)
        self.assertGreater(mock_close.call_count, 0)

def run_tests():
    """运行所有测试"""
    # 创建测试套件
    suite = unittest.TestSuite()
    
    # 添加功能测试
    suite.addTest(unittest.makeSuite(TestAirportFuelCharts))
    
    # 添加集成测试
    suite.addTest(unittest.makeSuite(TestAirportFuelChartsIntegration))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()

if __name__ == '__main__':
    success = run_tests()
    
    if success:
        print("\n✅ 所有测试通过！")
    else:
        print("\n❌ 部分测试失败！")
    
    exit(0 if success else 1) 