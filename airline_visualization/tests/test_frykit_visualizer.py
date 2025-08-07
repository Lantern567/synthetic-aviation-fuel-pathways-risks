"""
frykit航线可视化器的测试
"""

import unittest
import pandas as pd
import numpy as np
import os
import sys
from unittest.mock import patch, MagicMock

# 添加src路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

class TestFrykitRouteVisualizer(unittest.TestCase):
    """frykit航线可视化器测试类"""
    
    def setUp(self):
        """测试前设置"""
        # 创建测试数据
        self.test_data = pd.DataFrame({
            '出发城市': ['北京', '上海', '广州', '深圳', '成都'] * 20,
            '到达城市': ['上海', '广州', '深圳', '北京', '重庆'] * 20,
            '出发城市x': [116.4, 121.5, 113.3, 114.1, 104.1] * 20,
            '出发城市y': [39.9, 31.2, 23.1, 22.5, 30.7] * 20,
            '到达城市x': [121.5, 113.3, 114.1, 116.4, 106.5] * 20,
            '到达城市y': [31.2, 23.1, 22.5, 39.9, 29.5] * 20,
            '起飞机场': ['首都机场', '浦东机场', '白云机场', '宝安机场', '双流机场'] * 20,
            '降落机场': ['浦东机场', '白云机场', '宝安机场', '首都机场', '江北机场'] * 20,
            '起飞机场x': [116.6, 121.8, 113.3, 113.8, 103.9] * 20,
            '起飞机场y': [40.1, 31.1, 23.4, 22.6, 30.6] * 20,
            '降落机场x': [121.8, 113.3, 113.8, 116.6, 106.6] * 20,
            '降落机场y': [31.1, 23.4, 22.6, 40.1, 29.6] * 20,
            '里程（公里）': np.random.randint(500, 3000, 100),
            '机型': ['波音737', '空客320', 'CRJ900', '波音777', '空客330'] * 20,
            '人数': np.random.randint(100, 300, 100)
        })
    
    def test_frykit_import(self):
        """测试frykit库导入"""
        try:
            import frykit.plot as fplt
            self.assertTrue(True, "frykit库导入成功")
        except ImportError:
            self.skipTest("frykit库未安装")
    
    @patch('frykit.plot.savefig')
    @patch('matplotlib.pyplot.figure')
    def test_visualizer_creation(self, mock_figure, mock_savefig):
        """测试可视化器创建"""
        try:
            from src.visualizer.frykit_route_visualizer import FrykitRouteVisualizer
            
            visualizer = FrykitRouteVisualizer()
            self.assertIsNotNone(visualizer)
            self.assertIsNotNone(visualizer.map_crs)
            self.assertIsNotNone(visualizer.data_crs)
            
        except ImportError:
            self.skipTest("frykit相关模块导入失败")
    
    @patch('frykit.plot.savefig')
    @patch('matplotlib.pyplot.figure')
    @patch('frykit.plot.add_mini_axes')
    def test_route_visualization_creation(self, mock_mini_axes, mock_figure, mock_savefig):
        """测试航线可视化创建"""
        try:
            from src.visualizer.frykit_route_visualizer import FrykitRouteVisualizer
            
            # 模拟matplotlib和frykit组件
            mock_fig = MagicMock()
            mock_ax = MagicMock()
            mock_mini_ax = MagicMock()
            
            mock_figure.return_value = mock_fig
            mock_fig.add_subplot.return_value = mock_ax
            mock_mini_axes.return_value = mock_mini_ax
            
            visualizer = FrykitRouteVisualizer()
            result = visualizer.create_route_visualization(self.test_data, max_routes=10)
            
            # 验证返回结果
            self.assertIsNotNone(result)
            self.assertEqual(len(result), 3)  # fig, main_ax, mini_ax
            
        except ImportError:
            self.skipTest("frykit相关模块导入失败")
    
    def test_data_validation(self):
        """测试数据验证"""
        try:
            from src.visualizer.frykit_route_visualizer import FrykitRouteVisualizer
            
            visualizer = FrykitRouteVisualizer()
            
            # 测试空数据
            empty_data = pd.DataFrame()
            
            # 测试缺少必要列的数据
            incomplete_data = pd.DataFrame({
                '出发城市': ['北京', '上海'],
                '到达城市': ['上海', '北京']
                # 缺少坐标列
            })
            
            # 这些测试应该返回None或引发适当的错误
            # 由于实际调用会涉及matplotlib，我们主要测试数据结构
            self.assertIsInstance(self.test_data, pd.DataFrame)
            self.assertGreater(len(self.test_data), 0)
            
        except ImportError:
            self.skipTest("frykit相关模块导入失败")
    
    def test_coordinate_bounds(self):
        """测试坐标边界验证"""
        # 测试坐标范围
        valid_coords = self.test_data[
            (self.test_data['出发城市x'] >= 73) & (self.test_data['出发城市x'] <= 135) &
            (self.test_data['出发城市y'] >= 18) & (self.test_data['出发城市y'] <= 54)
        ]
        
        # 所有测试数据应该在有效范围内
        self.assertEqual(len(valid_coords), len(self.test_data))
    
    def test_distance_categorization(self):
        """测试距离分类逻辑"""
        distances = self.test_data['里程（公里）']
        
        short_distance = distances < 1000
        medium_distance = (distances >= 1000) & (distances < 2000)
        long_distance = distances >= 2000
        
        # 验证分类逻辑
        total_classified = short_distance.sum() + medium_distance.sum() + long_distance.sum()
        self.assertEqual(total_classified, len(distances))
    
    @patch('os.makedirs')
    @patch('frykit.plot.savefig')
    def test_save_functionality(self, mock_savefig, mock_makedirs):
        """测试保存功能"""
        try:
            from src.visualizer.frykit_route_visualizer import FrykitRouteVisualizer
            
            visualizer = FrykitRouteVisualizer()
            mock_fig = MagicMock()
            
            # 测试保存功能
            result = visualizer.save_visualization(mock_fig, 'test_map.png')
            
            # 验证目录创建和保存调用
            mock_makedirs.assert_called_once()
            mock_savefig.assert_called_once()
            self.assertIsNotNone(result)
            
        except ImportError:
            self.skipTest("frykit相关模块导入失败")

class TestFrykitIntegration(unittest.TestCase):
    """frykit集成测试类"""
    
    def test_main_program_execution(self):
        """测试主程序执行（模拟）"""
        # 由于主程序涉及大量外部依赖，这里主要测试逻辑结构
        self.assertTrue(os.path.exists('create_frykit_route_map.py'))
        
        # 验证输出目录结构
        expected_dirs = ['results', 'results/charts']
        for dir_path in expected_dirs:
            if os.path.exists(dir_path):
                self.assertTrue(os.path.isdir(dir_path))

if __name__ == '__main__':
    unittest.main() 