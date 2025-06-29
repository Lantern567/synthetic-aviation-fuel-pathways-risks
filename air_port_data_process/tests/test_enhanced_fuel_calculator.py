"""
增强版燃油消耗计算器的单元测试
"""

import sys
import os
import unittest
import pandas as pd
import numpy as np

# 添加源代码目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), '../src'))

from enhanced_fuel_calculator import (
    haversine_distance, 
    fix_distance_data, 
    estimate_city_distance,
    process_enhanced_flight_data
)

class TestEnhancedFuelCalculator(unittest.TestCase):
    
    def setUp(self):
        """测试前的准备工作"""
        # 创建测试数据
        self.test_data = {
            '机型': ['波音737(中)', '空客320(中)', '波音777(大)', '空客A380(超大)'],
            '里程（公里）': [0, 1200, 2500, 0],  # 有些里程为0
            '人数': [150, 180, 300, 500],
            '出发城市': ['阿克苏', '北京', '上海', '广州'],
            '到达城市': ['上海', '上海', '北京', '北京'],
            '出发城市x': [80.2, 116.4, 121.5, 113.3],
            '出发城市y': [41.2, 39.9, 31.2, 23.1],
            '到达城市x': [121.5, 121.5, 116.4, 116.4],
            '到达城市y': [31.2, 31.2, 39.9, 39.9],
            '起飞机场x': [80.3, 116.6, 121.8, 113.5],
            '起飞机场y': [41.3, 40.1, 31.5, 23.3],
            '降落机场x': [121.8, 121.8, 116.6, 116.6],
            '降落机场y': [31.5, 31.5, 40.1, 40.1]
        }
        self.df = pd.DataFrame(self.test_data)
    
    def test_haversine_distance(self):
        """测试Haversine距离计算"""
        # 测试北京到上海的距离（大约1200公里）
        beijing_lat, beijing_lon = 39.9, 116.4
        shanghai_lat, shanghai_lon = 31.2, 121.5
        
        distance = haversine_distance(beijing_lat, beijing_lon, shanghai_lat, shanghai_lon)
        
        # 实际距离大约1200公里，允许一定误差
        self.assertGreater(distance, 1000)
        self.assertLess(distance, 1400)
        print(f"北京到上海距离: {distance:.2f} km")
    
    def test_estimate_city_distance(self):
        """测试城市距离估算"""
        # 测试已知城市对
        distance1 = estimate_city_distance('阿克苏', '上海')
        self.assertEqual(distance1, 3200)
        
        distance2 = estimate_city_distance('北京', '上海')
        self.assertEqual(distance2, 1200)
        
        # 测试未知城市对
        distance3 = estimate_city_distance('未知城市1', '未知城市2')
        self.assertGreater(distance3, 0)
        print(f"城市距离估算测试通过")
    
    def test_fix_distance_data(self):
        """测试距离修复功能"""
        # 测试正常距离（不需要修复）
        row1 = self.df.iloc[1]  # 北京到上海，里程1200
        fixed_distance1 = fix_distance_data(row1)
        self.assertEqual(fixed_distance1, 1200)
        
        # 测试需要修复的距离（里程为0）
        row2 = self.df.iloc[0]  # 阿克苏到上海，里程为0
        fixed_distance2 = fix_distance_data(row2)
        self.assertGreater(fixed_distance2, 0)
        print(f"阿克苏到上海修复后距离: {fixed_distance2:.2f} km")
        
        # 测试A380航班（广州到北京）
        row3 = self.df.iloc[3]  # 广州到北京，里程为0
        fixed_distance3 = fix_distance_data(row3)
        self.assertGreater(fixed_distance3, 0)
        print(f"广州到北京修复后距离: {fixed_distance3:.2f} km")
    
    def test_process_enhanced_flight_data(self):
        """测试增强版数据处理"""
        processed_df = process_enhanced_flight_data(self.df.copy())
        
        # 检查新增字段
        expected_columns = [
            '原始里程', '修复后里程', '距离修复状态', 
            'ICAO代码', '载客率', '燃油消耗_kg', '计算状态'
        ]
        for col in expected_columns:
            self.assertIn(col, processed_df.columns)
        
        # 检查处理结果
        success_count = (processed_df['计算状态'] == '成功').sum()
        self.assertEqual(success_count, len(self.df))  # 所有记录都应该成功
        
        # 检查燃油消耗不为0
        zero_fuel_count = (processed_df['燃油消耗_kg'] == 0).sum()
        self.assertEqual(zero_fuel_count, 0)  # 修复后应该没有燃油消耗为0的记录
        
        # 检查距离修复状态
        fixed_count = (processed_df['距离修复状态'] == '已修复').sum()
        self.assertGreater(fixed_count, 0)  # 应该有距离被修复
        
        print("增强版数据处理测试结果:")
        print(f"  总记录数: {len(processed_df)}")
        print(f"  成功处理: {success_count}")
        print(f"  距离修复: {fixed_count}")
        print(f"  燃油消耗为0: {zero_fuel_count}")
        
        # 显示修复的距离
        fixed_rows = processed_df[processed_df['距离修复状态'] == '已修复']
        for idx, row in fixed_rows.iterrows():
            print(f"  {row['出发城市']} -> {row['到达城市']}: "
                  f"{row['原始里程']} -> {row['修复后里程']:.2f} km, "
                  f"燃油: {row['燃油消耗_kg']:.2f} kg")
    
    def test_extreme_cases(self):
        """测试极端情况"""
        # 创建极端测试数据
        extreme_data = {
            '机型': ['波音737(中)', '空客320(中)'],
            '里程（公里）': [0, 0],
            '人数': [150, 180],
            '出发城市': ['未知城市', '测试城市'],
            '到达城市': ['另一未知城市', '另一测试城市'],
            '出发城市x': [np.nan, np.nan],
            '出发城市y': [np.nan, np.nan], 
            '到达城市x': [np.nan, np.nan],
            '到达城市y': [np.nan, np.nan],
            '起飞机场x': [np.nan, np.nan],
            '起飞机场y': [np.nan, np.nan],
            '降落机场x': [np.nan, np.nan],
            '降落机场y': [np.nan, np.nan]
        }
        extreme_df = pd.DataFrame(extreme_data)
        
        # 处理极端数据
        processed_df = process_enhanced_flight_data(extreme_df.copy())
        
        # 即使在极端情况下，也应该能够处理
        success_count = (processed_df['计算状态'] == '成功').sum()
        self.assertEqual(success_count, len(extreme_df))
        
        # 应该使用默认距离或估算距离
        for idx, row in processed_df.iterrows():
            self.assertGreater(row['修复后里程'], 0)
            self.assertGreater(row['燃油消耗_kg'], 0)
        
        print("极端情况测试通过")

def run_tests():
    """运行所有测试"""
    print("=== 增强版燃油消耗计算器单元测试 ===\n")
    
    unittest.main(verbosity=2, exit=False)

if __name__ == "__main__":
    run_tests() 