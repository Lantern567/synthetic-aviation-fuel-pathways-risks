import unittest
import pandas as pd
import numpy as np
import os
import sys
import tempfile
import shutil
from unittest.mock import patch, MagicMock

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))

from fuel_density_visualizer import FuelDensityVisualizer

class TestFuelDensityVisualizer(unittest.TestCase):
    """燃油量密度可视化器测试类"""
    
    def setUp(self):
        """设置测试环境"""
        # 创建临时目录
        self.temp_dir = tempfile.mkdtemp()
        self.data_dir = os.path.join(self.temp_dir, 'data')
        self.results_dir = os.path.join(self.temp_dir, 'results')
        os.makedirs(self.data_dir)
        os.makedirs(self.results_dir)
        os.makedirs(os.path.join(self.results_dir, 'parallel_fuel_calculation'))
        os.makedirs(os.path.join(self.results_dir, 'figures'))
        os.makedirs(os.path.join(self.results_dir, 'tables'))
        
        # 创建测试实例
        self.visualizer = FuelDensityVisualizer(self.data_dir, self.results_dir)
        
        # 创建测试数据
        self.create_test_data()
    
    def tearDown(self):
        """清理测试环境"""
        shutil.rmtree(self.temp_dir)
    
    def create_test_data(self):
        """创建测试数据"""
        # 创建测试燃油计算结果
        fuel_data = {
            '起飞机场': ['北京首都机场', '上海浦东机场', '广州白云机场', '深圳宝安机场', '成都双流机场'] * 20,
            '日期': pd.date_range('2024-01-01', periods=100, freq='D'),
            '总燃油量': np.random.uniform(1000, 10000, 100),
            '航班编号': [f'CA{i:04d}' for i in range(100)]
        }
        fuel_df = pd.DataFrame(fuel_data)
        
        # 保存燃油计算结果
        fuel_path = os.path.join(self.results_dir, 'parallel_fuel_calculation', 'test_fuel_results.xlsx')
        fuel_df.to_excel(fuel_path, index=False)
        
        # 创建测试机场数据
        airport_data = {
            '起飞机场': ['北京首都机场', '上海浦东机场', '广州白云机场', '深圳宝安机场', '成都双流机场'],
            '起飞机场x': [116.5853, 121.8053, 113.0968, 113.8106, 103.9487],
            '起飞机场y': [40.0803, 31.1434, 23.3924, 22.6390, 30.5785]
        }
        airport_df = pd.DataFrame(airport_data)
        
        # 创建完整的航班数据（模拟原始数据文件）
        full_flight_data = []
        for _ in range(1000):
            airport = np.random.choice(airport_data['起飞机场'])
            idx = airport_data['起飞机场'].index(airport)
            full_flight_data.append({
                '起飞机场': airport,
                '起飞机场x': airport_data['起飞机场x'][idx],
                '起飞机场y': airport_data['起飞机场y'][idx],
                '日期': pd.Timestamp('2024-01-01') + pd.Timedelta(days=np.random.randint(0, 365))
            })
        
        full_df = pd.DataFrame(full_flight_data)
        
        # 保存机场数据
        airport_path = os.path.join(self.data_dir, '22年1月1日至24年12月31日航班数据.xlsx')
        full_df.to_excel(airport_path, index=False)
    
    def test_init(self):
        """测试初始化"""
        self.assertIsNotNone(self.visualizer.data_dir)
        self.assertIsNotNone(self.visualizer.results_dir)
        self.assertIsNotNone(self.visualizer.map_crs)
        self.assertIsNotNone(self.visualizer.data_crs)
    
    def test_load_fuel_calculation_results(self):
        """测试加载燃油计算结果"""
        df = self.visualizer.load_fuel_calculation_results()
        
        self.assertIsInstance(df, pd.DataFrame)
        self.assertGreater(len(df), 0)
        self.assertIn('起飞机场', df.columns)
        self.assertIn('总燃油量', df.columns)
    
    def test_load_airport_data(self):
        """测试加载机场数据"""
        airports = self.visualizer.load_airport_data()
        
        self.assertIsInstance(airports, pd.DataFrame)
        self.assertGreater(len(airports), 0)
        self.assertIn('起飞机场', airports.columns)
        self.assertIn('起飞机场x', airports.columns)
        self.assertIn('起飞机场y', airports.columns)
    
    def test_aggregate_fuel_by_airport_2024(self):
        """测试按机场聚合2024年燃油量数据"""
        fuel_df = self.visualizer.load_fuel_calculation_results()
        aggregated = self.visualizer.aggregate_fuel_by_airport_2024(fuel_df)
        
        self.assertIsInstance(aggregated, pd.DataFrame)
        self.assertGreater(len(aggregated), 0)
        self.assertIn('起飞机场', aggregated.columns)
        self.assertIn('总燃油量', aggregated.columns)
        self.assertIn('航班数量', aggregated.columns)
        self.assertIn('平均燃油量', aggregated.columns)
        
        # 检查聚合结果
        self.assertTrue(all(aggregated['总燃油量'] >= 0))
        self.assertTrue(all(aggregated['航班数量'] >= 0))
        self.assertTrue(all(aggregated['平均燃油量'] >= 0))
    
    def test_merge_fuel_with_coordinates(self):
        """测试合并燃油量与坐标数据"""
        fuel_df = self.visualizer.load_fuel_calculation_results()
        airports = self.visualizer.load_airport_data()
        fuel_aggregated = self.visualizer.aggregate_fuel_by_airport_2024(fuel_df)
        merged = self.visualizer.merge_fuel_with_coordinates(fuel_aggregated, airports)
        
        self.assertIsInstance(merged, pd.DataFrame)
        self.assertGreater(len(merged), 0)
        self.assertIn('起飞机场', merged.columns)
        self.assertIn('总燃油量', merged.columns)
        self.assertIn('起飞机场x', merged.columns)
        self.assertIn('起飞机场y', merged.columns)
        
        # 检查没有空坐标
        self.assertFalse(merged['起飞机场x'].isna().any())
        self.assertFalse(merged['起飞机场y'].isna().any())
    
    @patch('matplotlib.pyplot.figure')
    @patch('frykit.plot.savefig')
    def test_create_base_map(self, mock_savefig, mock_figure):
        """测试创建基础地图"""
        mock_fig = MagicMock()
        mock_ax = MagicMock()
        mock_mini_ax = MagicMock()
        mock_figure.return_value = mock_fig
        mock_fig.add_subplot.return_value = mock_ax
        
        with patch('frykit.plot.add_mini_axes', return_value=mock_mini_ax):
            with patch('frykit.plot.set_map_ticks'):
                with patch('frykit.plot.add_cn_city'):
                    with patch('frykit.plot.add_cn_line'):
                        with patch('frykit.plot.add_cn_border'):
                            fig, main_ax, mini_ax = self.visualizer.create_base_map()
                            
                            self.assertEqual(fig, mock_fig)
                            self.assertEqual(main_ax, mock_ax)
                            self.assertEqual(mini_ax, mock_mini_ax)
    
    def test_generate_fuel_density_report(self):
        """测试生成燃油量密度分析报告"""
        # 创建测试数据
        test_data = pd.DataFrame({
            '起飞机场': ['测试机场1', '测试机场2', '测试机场3'],
            '总燃油量': [1000, 2000, 3000],
            '航班数量': [10, 20, 30],
            '平均燃油量': [100, 100, 100],
            '起飞机场x': [116.0, 121.0, 113.0],
            '起飞机场y': [40.0, 31.0, 23.0]
        })
        
        report_path = self.visualizer.generate_fuel_density_report(test_data)
        
        self.assertTrue(os.path.exists(report_path))
        
        # 检查报告内容
        with open(report_path, 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertIn('2024年各起飞机场航班总燃油量密度分析报告', content)
            self.assertIn('总体统计', content)
            self.assertIn('机场数量', content)
            self.assertIn('燃油量前10名机场', content)
    
    def test_file_not_found_errors(self):
        """测试文件不存在时的错误处理"""
        # 测试燃油计算结果文件不存在
        empty_visualizer = FuelDensityVisualizer('/nonexistent/data', '/nonexistent/results')
        
        with self.assertRaises(FileNotFoundError):
            empty_visualizer.load_fuel_calculation_results()
        
        with self.assertRaises(FileNotFoundError):
            empty_visualizer.load_airport_data()
    
    def test_data_validation(self):
        """测试数据验证"""
        # 测试空数据框
        empty_df = pd.DataFrame()
        
        with self.assertRaises((ValueError, IndexError)):
            self.visualizer.aggregate_fuel_by_airport_2024(empty_df)
        
        # 测试缺少必要列的数据框
        invalid_df = pd.DataFrame({'无关列': [1, 2, 3]})
        
        with self.assertRaises((ValueError, KeyError)):
            self.visualizer.aggregate_fuel_by_airport_2024(invalid_df)

class TestFuelDensityVisualizerIntegration(unittest.TestCase):
    """燃油量密度可视化器集成测试"""
    
    def setUp(self):
        """设置集成测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.data_dir = os.path.join(self.temp_dir, 'data')
        self.results_dir = os.path.join(self.temp_dir, 'results')
        os.makedirs(self.data_dir)
        os.makedirs(self.results_dir)
        os.makedirs(os.path.join(self.results_dir, 'parallel_fuel_calculation'))
        os.makedirs(os.path.join(self.results_dir, 'figures'))
        os.makedirs(os.path.join(self.results_dir, 'tables'))
        
        self.visualizer = FuelDensityVisualizer(self.data_dir, self.results_dir)
        self.create_comprehensive_test_data()
    
    def tearDown(self):
        """清理集成测试环境"""
        shutil.rmtree(self.temp_dir)
    
    def create_comprehensive_test_data(self):
        """创建全面的测试数据"""
        # 创建更真实的测试数据
        np.random.seed(42)  # 确保可重现的结果
        
        airports = ['北京首都机场', '上海浦东机场', '广州白云机场', '深圳宝安机场', '成都双流机场',
                   '西安咸阳机场', '昆明长水机场', '重庆江北机场', '杭州萧山机场', '南京禄口机场']
        
        coordinates = [
            (116.5853, 40.0803), (121.8053, 31.1434), (113.0968, 23.3924),
            (113.8106, 22.6390), (103.9487, 30.5785), (108.7569, 34.4478),
            (102.7419, 25.1019), (106.6417, 29.7192), (120.4342, 30.2295),
            (118.8619, 31.7420)
        ]
        
        # 创建2024年的燃油计算结果
        fuel_data = []
        for i in range(500):
            airport = np.random.choice(airports)
            date = pd.Timestamp('2024-01-01') + pd.Timedelta(days=np.random.randint(0, 365))
            fuel_amount = np.random.uniform(500, 15000)
            
            fuel_data.append({
                '起飞机场': airport,
                '日期': date,
                '总燃油量': fuel_amount,
                '航班编号': f'TEST{i:04d}'
            })
        
        fuel_df = pd.DataFrame(fuel_data)
        fuel_path = os.path.join(self.results_dir, 'parallel_fuel_calculation', 'comprehensive_test_results.xlsx')
        fuel_df.to_excel(fuel_path, index=False)
        
        # 创建机场坐标数据
        airport_data = []
        for airport, (x, y) in zip(airports, coordinates):
            # 为每个机场创建多条记录（模拟原始数据）
            for _ in range(50):
                airport_data.append({
                    '起飞机场': airport,
                    '起飞机场x': x,
                    '起飞机场y': y,
                    '日期': pd.Timestamp('2024-01-01') + pd.Timedelta(days=np.random.randint(0, 365))
                })
        
        airport_df = pd.DataFrame(airport_data)
        airport_path = os.path.join(self.data_dir, '22年1月1日至24年12月31日航班数据.xlsx')
        airport_df.to_excel(airport_path, index=False)
    
    @patch('matplotlib.pyplot.figure')
    @patch('frykit.plot.savefig')
    @patch('matplotlib.pyplot.close')
    def test_complete_analysis_workflow(self, mock_close, mock_savefig, mock_figure):
        """测试完整的分析工作流程"""
        # Mock matplotlib components
        mock_fig = MagicMock()
        mock_ax = MagicMock()
        mock_mini_ax = MagicMock()
        mock_scatter = MagicMock()
        
        mock_figure.return_value = mock_fig
        mock_fig.add_subplot.return_value = mock_ax
        mock_ax.scatter.return_value = mock_scatter
        
        with patch('frykit.plot.add_mini_axes', return_value=mock_mini_ax):
            with patch('frykit.plot.set_map_ticks'):
                with patch('frykit.plot.add_cn_city'):
                    with patch('frykit.plot.add_cn_line'):
                        with patch('frykit.plot.add_cn_border'):
                            with patch('frykit.plot.add_compass'):
                                with patch('frykit.plot.add_scale_bar'):
                                    with patch('matplotlib.pyplot.colorbar'):
                                        with patch('matplotlib.pyplot.suptitle'):
                                            # 运行完整分析
                                            results = self.visualizer.run_complete_analysis()
                                            
                                            # 验证返回结果
                                            self.assertIn('map_path', results)
                                            self.assertIn('report_path', results)
                                            self.assertIn('data', results)
                                            
                                            # 验证文件创建
                                            self.assertTrue(os.path.exists(results['report_path']))
                                            
                                            # 验证数据质量
                                            data = results['data']
                                            self.assertIsInstance(data, pd.DataFrame)
                                            self.assertGreater(len(data), 0)
                                            
                                            # 验证必要的列存在
                                            required_columns = ['起飞机场', '总燃油量', '航班数量', '平均燃油量', '起飞机场x', '起飞机场y']
                                            for col in required_columns:
                                                self.assertIn(col, data.columns)

def run_tests():
    """运行所有测试"""
    # 创建测试套件
    test_suite = unittest.TestSuite()
    
    # 添加单元测试
    test_suite.addTest(unittest.makeSuite(TestFuelDensityVisualizer))
    test_suite.addTest(unittest.makeSuite(TestFuelDensityVisualizerIntegration))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    return result

if __name__ == '__main__':
    result = run_tests()
    
    # 输出测试结果摘要
    print(f"\n{'='*50}")
    print("测试结果摘要:")
    print(f"运行测试数: {result.testsRun}")
    print(f"失败数: {len(result.failures)}")
    print(f"错误数: {len(result.errors)}")
    print(f"成功率: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    
    if result.failures:
        print("\n失败的测试:")
        for test, traceback in result.failures:
            print(f"  - {test}: {traceback}")
    
    if result.errors:
        print("\n错误的测试:")
        for test, traceback in result.errors:
            print(f"  - {test}: {traceback}")
    
    if result.wasSuccessful():
        print("\n所有测试通过! ✅")
    else:
        print("\n部分测试失败! ❌") 