"""
运输路径可视化器测试单元
"""

import unittest
import pandas as pd
import numpy as np
import tempfile
import os
from pathlib import Path
import sys

# 添加src目录到路径
sys.path.append(str(Path(__file__).parent.parent / 'src'))

from transport_route_visualizer import TransportRouteVisualizer

class TestTransportRouteVisualizer(unittest.TestCase):
    """运输路径可视化器测试类"""
    
    def setUp(self):
        """设置测试环境"""
        self.visualizer = TransportRouteVisualizer()
        self.test_data = self.create_test_data()
        
    def create_test_data(self):
        """创建测试数据"""
        test_data = {
            '路径ID': ['test_1', 'test_2', 'test_3'],
            '起点': ['lng_terminal_1', 'airport_beijing', 'renewable_plant_1'],
            '终点': ['beijing', 'shanghai', 'tianjin'],
            '起点类型': ['生产设施', '生产设施', '生产设施'],
            '终点类型': ['机场', '机场', '机场'],
            '距离(km)': [500.5, 1200.3, 800.7],
            '起点坐标': ['(39.9042, 116.4074)', '(39.9042, 116.4074)', '(39.1439, 117.2108)'],
            '终点坐标': ['(39.9300, 116.3956)', '(31.2304, 121.4737)', '(39.1439, 117.2108)'],
            '货物类型': ['MTJ', 'MTJ', 'MTJ'],
            '运输方式': ['truck', 'truck', 'pipeline'],
            '周运输量(kg)': [1000000, 2000000, 1500000],
            '时间单位': ['周', '周', '周']
        }
        return pd.DataFrame(test_data)
    
    def create_test_csv(self):
        """创建测试CSV文件"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
            self.test_data.to_csv(f.name, index=False)
            return f.name
    
    def test_parse_coordinates(self):
        """测试坐标解析功能"""
        # 测试正常坐标
        lat, lon = self.visualizer.parse_coordinates('(39.9042, 116.4074)')
        self.assertAlmostEqual(lat, 39.9042, places=4)
        self.assertAlmostEqual(lon, 116.4074, places=4)
        
        # 测试无效坐标
        lat, lon = self.visualizer.parse_coordinates('invalid')
        self.assertIsNone(lat)
        self.assertIsNone(lon)
        
        # 测试空值
        lat, lon = self.visualizer.parse_coordinates(None)
        self.assertIsNone(lat)
        self.assertIsNone(lon)
    
    def test_load_transport_data(self):
        """测试数据加载功能"""
        csv_file = self.create_test_csv()
        
        try:
            data = self.visualizer.load_transport_data(csv_file)
            self.assertIsNotNone(data)
            self.assertGreater(len(data), 0)
            
            # 检查坐标列是否已添加
            required_cols = ['起点纬度', '起点经度', '终点纬度', '终点经度']
            for col in required_cols:
                self.assertIn(col, data.columns)
            
            # 检查坐标值是否有效
            self.assertFalse(data['起点纬度'].isna().all())
            self.assertFalse(data['起点经度'].isna().all())
            
        finally:
            os.unlink(csv_file)
    
    def test_get_facility_type(self):
        """测试设施类型识别"""
        self.assertEqual(self.visualizer.get_facility_type('airport_beijing'), 'airport')
        self.assertEqual(self.visualizer.get_facility_type('lng_terminal_1'), 'lng')
        self.assertEqual(self.visualizer.get_facility_type('renewable_plant'), 'renewable')
        self.assertEqual(self.visualizer.get_facility_type('pipeline_station'), 'pipeline')
        self.assertEqual(self.visualizer.get_facility_type('unknown_facility'), 'default')
    
    def test_normalize_transport_volume(self):
        """测试运输量标准化"""
        volumes = [1000, 2000, 3000, 4000, 5000]
        normalized = self.visualizer.normalize_transport_volume(volumes)
        
        # 检查结果长度
        self.assertEqual(len(normalized), len(volumes))
        
        # 检查范围
        self.assertTrue(all(0.5 <= x <= 4.0 for x in normalized))
        
        # 检查单调性
        self.assertTrue(all(normalized[i] <= normalized[i+1] for i in range(len(normalized)-1)))
    
    def test_create_base_map(self):
        """测试基础地图创建"""
        fig, main_ax, mini_ax = self.visualizer.create_base_map()
        
        self.assertIsNotNone(fig)
        self.assertIsNotNone(main_ax)
        self.assertIsNotNone(mini_ax)
        
        # 清理
        import matplotlib.pyplot as plt
        plt.close(fig)
    
    def test_create_transport_visualization(self):
        """测试运输可视化创建"""
        csv_file = self.create_test_csv()
        
        try:
            data = self.visualizer.load_transport_data(csv_file)
            result = self.visualizer.create_transport_visualization(data)
            
            self.assertIsNotNone(result)
            self.assertEqual(len(result), 4)
            
            fig, main_ax, mini_ax, display_data = result
            self.assertIsNotNone(fig)
            self.assertIsNotNone(main_ax)
            self.assertIsNotNone(mini_ax)
            self.assertIsNotNone(display_data)
            
            # 清理
            import matplotlib.pyplot as plt
            plt.close(fig)
            
        finally:
            os.unlink(csv_file)
    
    def test_save_visualization(self):
        """测试可视化保存功能"""
        csv_file = self.create_test_csv()
        
        try:
            data = self.visualizer.load_transport_data(csv_file)
            result = self.visualizer.create_transport_visualization(data)
            
            if result is not None:
                fig, main_ax, mini_ax, display_data = result
                
                # 创建临时目录
                with tempfile.TemporaryDirectory() as temp_dir:
                    saved_path = self.visualizer.save_visualization(
                        fig, filename='test_visualization.png', output_dir=temp_dir
                    )
                    
                    # 检查文件是否存在
                    self.assertTrue(os.path.exists(saved_path))
                    self.assertTrue(saved_path.endswith('.png'))
            
        finally:
            os.unlink(csv_file)
    
    def test_create_analysis_report(self):
        """测试分析报告创建"""
        csv_file = self.create_test_csv()
        
        try:
            data = self.visualizer.load_transport_data(csv_file)
            
            with tempfile.TemporaryDirectory() as temp_dir:
                report_path = self.visualizer.create_analysis_report(
                    data, data, output_dir=temp_dir
                )
                
                # 检查报告文件是否存在
                self.assertTrue(os.path.exists(report_path))
                self.assertTrue(report_path.endswith('.md'))
                
                # 检查报告内容
                with open(report_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    self.assertIn('天然气供应链运输路径分析报告', content)
                    self.assertIn('数据概览', content)
                    self.assertIn('运输方式分布', content)
            
        finally:
            os.unlink(csv_file)

class TestTransportVisualizerIntegration(unittest.TestCase):
    """运输可视化器集成测试"""
    
    def setUp(self):
        """设置集成测试环境"""
        self.visualizer = TransportRouteVisualizer()
        
    def test_real_data_file_exists(self):
        """测试真实数据文件是否存在"""
        data_file = Path(__file__).parent.parent / 'results' / 'transport_summary_20250802_220255.csv'
        if data_file.exists():
            # 如果真实数据文件存在，测试加载
            data = self.visualizer.load_transport_data(str(data_file))
            if data is not None and len(data) > 0:
                print(f"✅ 真实数据文件加载成功: {len(data)} 条记录")
                
                # 测试小规模可视化
                small_data = data.head(10)  # 只使用前10条数据进行测试
                result = self.visualizer.create_transport_visualization(small_data)
                
                if result is not None:
                    fig, main_ax, mini_ax, display_data = result
                    print(f"✅ 小规模可视化测试成功: {len(display_data)} 条路径")
                    
                    # 清理
                    import matplotlib.pyplot as plt
                    plt.close(fig)
            else:
                print("⚠️ 真实数据文件为空或无效")
        else:
            print("⚠️ 真实数据文件不存在，跳过集成测试")

def run_tests():
    """运行所有测试"""
    # 基础功能测试
    print("🧪 开始运行基础功能测试...")
    unittest.main(module='__main__', argv=[''], exit=False, verbosity=2)
    
    # 集成测试
    print("\n🔗 开始运行集成测试...")
    suite = unittest.TestLoader().loadTestsFromTestCase(TestTransportVisualizerIntegration)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)

if __name__ == '__main__':
    run_tests()