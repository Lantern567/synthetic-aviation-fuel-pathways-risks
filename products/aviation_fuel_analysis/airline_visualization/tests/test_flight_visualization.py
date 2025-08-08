"""
航线可视化单元测试
"""

import unittest
import os
import sys
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock

# 添加路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.data_loader.flight_data_loader import FlightDataLoader
from src.visualizer.pydeck_flight_visualizer import PyDeckFlightVisualizer

class TestFlightDataLoader(unittest.TestCase):
    """测试航班数据加载器"""
    
    def setUp(self):
        """设置测试数据"""
        self.test_data = pd.DataFrame({
            '出发城市': ['北京', '上海', '广州'],
            '出发城市x': [116.4, 121.5, 113.3],
            '出发城市y': [39.9, 31.2, 23.1],
            '到达城市': ['上海', '广州', '深圳'],
            '到达城市x': [121.5, 113.3, 114.1],
            '到达城市y': [31.2, 23.1, 22.5],
            '起飞机场': ['首都机场', '浦东机场', '白云机场'],
            '起飞机场x': [116.6, 121.8, 113.3],
            '起飞机场y': [40.1, 31.1, 23.4],
            '降落机场': ['浦东机场', '白云机场', '宝安机场'],
            '降落机场x': [121.8, 113.3, 114.1],
            '降落机场y': [31.1, 23.4, 22.6],
            '里程（公里）': [1200, 1400, 150],
            '机型': ['波音737(中)', '空客320(中)', 'JET'],
            '人数': [180, 160, 90],
            '航空公司': ['中国国航', '东方航空', '南方航空'],
            '航班班次': ['CA001', 'MU001', 'CZ001'],
            '价格(元)': [800, 900, 400]
        })
        
        self.loader = FlightDataLoader()
    
    def test_clean_and_validate_data(self):
        """测试数据清洗和验证"""
        # 设置测试数据
        self.loader.raw_data = self.test_data.copy()
        
        # 执行清洗
        cleaned_data = self.loader.clean_and_validate_data()
        
        # 验证结果
        self.assertIsInstance(cleaned_data, pd.DataFrame)
        self.assertGreater(len(cleaned_data), 0)
        
        # 验证必要字段存在
        required_fields = ['出发城市x', '出发城市y', '到达城市x', '到达城市y']
        for field in required_fields:
            self.assertIn(field, cleaned_data.columns)
    
    def test_prepare_for_visualization(self):
        """测试可视化数据准备"""
        # 设置测试数据
        self.loader.raw_data = self.test_data.copy()
        cleaned_data = self.loader.clean_and_validate_data()
        
        # 执行数据准备
        processed_data = self.loader.prepare_for_visualization(cleaned_data)
        
        # 验证结果结构
        self.assertIsInstance(processed_data, dict)
        expected_keys = ['routes', 'airports', 'airport_stats', 'cities', 'aircraft_stats']
        for key in expected_keys:
            self.assertIn(key, processed_data)
            self.assertIsInstance(processed_data[key], pd.DataFrame)
        
        # 验证航线数据
        routes_data = processed_data['routes']
        self.assertIn('start_lon', routes_data.columns)
        self.assertIn('start_lat', routes_data.columns)
        self.assertIn('end_lon', routes_data.columns)
        self.assertIn('end_lat', routes_data.columns)
    
    def test_get_data_summary(self):
        """测试数据摘要生成"""
        # 设置测试数据
        self.loader.raw_data = self.test_data.copy()
        cleaned_data = self.loader.clean_and_validate_data()
        self.loader.processed_data = self.loader.prepare_for_visualization(cleaned_data)
        
        # 生成摘要
        summary = self.loader.get_data_summary()
        
        # 验证摘要结构
        self.assertIsInstance(summary, dict)
        expected_keys = ['total_routes', 'total_cities', 'total_passengers', 
                        'total_distance', 'coordinate_bounds']
        for key in expected_keys:
            self.assertIn(key, summary)

class TestPyDeckFlightVisualizer(unittest.TestCase):
    """测试pydeck可视化器"""
    
    def setUp(self):
        """设置测试数据"""
        self.visualizer = PyDeckFlightVisualizer()
        
        # 创建模拟的处理后数据
        self.routes_data = pd.DataFrame({
            'start_lon': [116.4, 121.5],
            'start_lat': [39.9, 31.2],
            'end_lon': [121.5, 113.3],
            'end_lat': [31.2, 23.1],
            'start_city': ['北京', '上海'],
            'end_city': ['上海', '广州'],
            'distance': [1200, 1400],
            'passengers': [180, 160],
            'aircraft_type': ['波音737(中)', '空客320(中)']
        })
        
        self.airport_stats = pd.DataFrame({
            'airport_name': ['首都机场', '浦东机场'],
            'lon': [116.6, 121.8],
            'lat': [40.1, 31.1],
            'total_flights': [100, 80]
        })
        
        self.cities_data = pd.DataFrame({
            'city': ['北京', '上海'],
            'lon': [116.4, 121.5],
            'lat': [39.9, 31.2],
            'total_passengers': [5000, 4000],
            'total_distance': [10000, 8000]
        })
    
    def test_calculate_view_state(self):
        """测试视图状态计算"""
        bounds = {
            'min_lon': 113.0,
            'max_lon': 122.0,
            'min_lat': 23.0,
            'max_lat': 40.0
        }
        
        view_state = self.visualizer.calculate_view_state(bounds)
        
        # 验证视图状态
        self.assertIsNotNone(view_state)
        self.assertAlmostEqual(view_state.longitude, 117.5, places=1)
        self.assertAlmostEqual(view_state.latitude, 31.5, places=1)
    
    @patch('pydeck.Layer')
    def test_create_route_layer(self, mock_layer):
        """测试航线图层创建"""
        # 配置mock
        mock_layer.return_value = MagicMock()
        
        # 创建图层
        layer = self.visualizer.create_route_layer(self.routes_data)
        
        # 验证Layer被调用
        mock_layer.assert_called_once()
        self.assertIsNotNone(layer)
    
    @patch('pydeck.Layer')
    def test_create_airport_layer(self, mock_layer):
        """测试机场图层创建"""
        # 配置mock
        mock_layer.return_value = MagicMock()
        
        # 创建图层
        layer = self.visualizer.create_airport_layer(self.airport_stats)
        
        # 验证Layer被调用
        mock_layer.assert_called_once()
        self.assertIsNotNone(layer)
    
    @patch('pydeck.Layer')
    def test_create_city_heatmap_layer(self, mock_layer):
        """测试城市热力图层创建"""
        # 配置mock
        mock_layer.return_value = MagicMock()
        
        # 创建图层
        layer = self.visualizer.create_city_heatmap_layer(self.cities_data)
        
        # 验证Layer被调用
        mock_layer.assert_called_once()
        self.assertIsNotNone(layer)

class TestVisualizationIntegration(unittest.TestCase):
    """集成测试"""
    
    def setUp(self):
        """设置集成测试"""
        # 创建测试数据文件路径（如果需要的话）
        self.test_data_file = None
    
    def test_color_conversion_methods(self):
        """测试颜色转换方法"""
        visualizer = PyDeckFlightVisualizer()
        
        # 测试距离转颜色
        color = visualizer._distance_to_color(0.5)
        self.assertIsInstance(color, list)
        self.assertEqual(len(color), 4)  # RGBA
        
        # 测试乘客数量转颜色
        color = visualizer._passengers_to_color(0.3)
        self.assertIsInstance(color, list)
        self.assertEqual(len(color), 4)
        
        # 测试机型转颜色
        color = visualizer._aircraft_type_to_color('波音737(中)')
        self.assertIsInstance(color, list)
        self.assertEqual(len(color), 4)
        
        # 测试未知机型
        color = visualizer._aircraft_type_to_color('未知机型')
        self.assertIsInstance(color, list)
        self.assertEqual(len(color), 4)

class TestDataValidation(unittest.TestCase):
    """数据验证测试"""
    
    def test_invalid_coordinates(self):
        """测试无效坐标处理"""
        loader = FlightDataLoader()
        
        # 创建包含无效坐标的测试数据
        invalid_data = pd.DataFrame({
            '出发城市': ['测试城市'],
            '出发城市x': [200],  # 超出有效经度范围
            '出发城市y': [90],   # 超出有效纬度范围
            '到达城市': ['测试城市2'],
            '到达城市x': [-200], # 超出有效经度范围
            '到达城市y': [-90],  # 超出有效纬度范围
            '起飞机场': ['测试机场'],
            '起飞机场x': [116.0],
            '起飞机场y': [40.0],
            '降落机场': ['测试机场2'],
            '降落机场x': [121.0],
            '降落机场y': [31.0],
            '里程（公里）': [1000],
            '机型': ['测试机型'],
            '人数': [100]
        })
        
        loader.raw_data = invalid_data
        cleaned_data = loader.clean_and_validate_data()
        
        # 验证无效坐标被过滤掉
        self.assertEqual(len(cleaned_data), 0)
    
    def test_negative_values(self):
        """测试负值处理"""
        loader = FlightDataLoader()
        
        # 创建包含负值的测试数据
        negative_data = pd.DataFrame({
            '出发城市': ['北京', '上海'],
            '出发城市x': [116.4, 121.5],
            '出发城市y': [39.9, 31.2],
            '到达城市': ['上海', '广州'],
            '到达城市x': [121.5, 113.3],
            '到达城市y': [31.2, 23.1],
            '起飞机场': ['首都机场', '浦东机场'],
            '起飞机场x': [116.6, 121.8],
            '起飞机场y': [40.1, 31.1],
            '降落机场': ['浦东机场', '白云机场'],
            '降落机场x': [121.8, 113.3],
            '降落机场y': [31.1, 23.4],
            '里程（公里）': [-1000, 1400],  # 负里程
            '机型': ['波音737(中)', '空客320(中)'],
            '人数': [180, -50]  # 负人数
        })
        
        loader.raw_data = negative_data
        cleaned_data = loader.clean_and_validate_data()
        
        # 验证只保留有效记录
        self.assertEqual(len(cleaned_data), 0)  # 两条记录都应该被过滤

def run_tests():
    """运行所有测试"""
    print("🧪 开始运行航线可视化测试...")
    
    # 创建测试套件
    test_suite = unittest.TestSuite()
    
    # 添加测试类
    test_classes = [
        TestFlightDataLoader,
        TestPyDeckFlightVisualizer,
        TestVisualizationIntegration,
        TestDataValidation
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # 输出结果摘要
    print(f"\n📊 测试结果摘要:")
    print(f"运行测试数: {result.testsRun}")
    print(f"失败数: {len(result.failures)}")
    print(f"错误数: {len(result.errors)}")
    
    if result.failures:
        print("\n❌ 失败的测试:")
        for test, traceback in result.failures:
            print(f"- {test}: {traceback}")
    
    if result.errors:
        print("\n⚠️ 错误的测试:")
        for test, traceback in result.errors:
            print(f"- {test}: {traceback}")
    
    if result.wasSuccessful():
        print("\n✅ 所有测试通过！")
        return True
    else:
        print("\n❌ 测试未通过，请检查代码")
        return False

if __name__ == "__main__":
    run_tests() 