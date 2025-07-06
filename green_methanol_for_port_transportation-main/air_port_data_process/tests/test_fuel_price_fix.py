"""
测试燃油价格计算器的日期修复
"""

import unittest
import sys
import os

# 添加src路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from fuel_price_calculator import FuelPriceCalculator

class TestFuelPriceFix(unittest.TestCase):
    """测试燃油价格计算器的日期修复"""
    
    def setUp(self):
        """测试前的设置"""
        self.calculator = FuelPriceCalculator()
    
    def test_current_month_from_data(self):
        """测试从数据中获取当前月份"""
        # 当前月份应该从实际数据中获取
        print(f"✅ 从数据中获取的当前月份: {self.calculator.current_month}")
        
        # 验证月份格式正确
        self.assertRegex(self.calculator.current_month, r'^\d{4}-\d{2}$')
        
        # 验证日期提取器已初始化
        self.assertIsNotNone(self.calculator.date_extractor)
    
    def test_fuel_cost_calculation_with_data_month(self):
        """测试使用数据中实际月份的燃油成本计算"""
        # 使用从数据中获取的月份
        current_month = self.calculator.current_month
        result = self.calculator.calculate_fuel_cost(1000, current_month, use_price_range=True)
        
        # 验证返回的数据
        self.assertGreater(result['fuel_cost_yuan_avg'], 0)
        self.assertIn('month', result)
        self.assertIn('market_trend', result)
        
        print(f"✅ 数据驱动的月份计算成功:")
        print(f"   使用月份: {current_month}")
        print(f"   实际月份: {result['month']}")
        print(f"   燃油成本: ¥{result['fuel_cost_yuan_avg']:.2f}")
        print(f"   市场趋势: {result['market_trend']}")
    
    def test_fuel_cost_calculation_with_invalid_month(self):
        """测试无效月份的燃油成本计算"""
        # 测试2025-07这样的无效月份
        result = self.calculator.calculate_fuel_cost(1000, '2025-07', use_price_range=True)
        
        # 应该返回有效的数据
        self.assertGreater(result['fuel_cost_yuan_avg'], 0)
        self.assertIn('month', result)
        self.assertIn('market_trend', result)
        
        print(f"✅ 无效月份处理成功:")
        print(f"   查询月份: 2025-07")
        print(f"   实际使用月份: {result['month']}")
        print(f"   燃油成本: ¥{result['fuel_cost_yuan_avg']:.2f}")
        print(f"   市场趋势: {result['market_trend']}")
    
    def test_fuel_cost_calculation_default_month(self):
        """测试默认月份的燃油成本计算"""
        result = self.calculator.calculate_fuel_cost(1000, use_price_range=True)
        
        # 应该使用从数据中获取的当前月份
        self.assertGreater(result['fuel_cost_yuan_avg'], 0)
        self.assertIn('month', result)
        
        print(f"✅ 默认月份计算成功:")
        print(f"   使用月份: {result['month']}")
        print(f"   燃油成本: ¥{result['fuel_cost_yuan_avg']:.2f}")
    
    def test_data_date_extractor_integration(self):
        """测试数据日期提取器集成"""
        # 测试日期提取器的功能
        extractor = self.calculator.date_extractor
        
        # 测试月份可用性检查
        available_months = extractor.available_months
        print(f"✅ 数据中可用的月份: {sorted(list(available_months))}")
        
        # 测试月份检查功能
        test_months = ['2022-01', '2024-12', '2025-07']
        for month in test_months:
            is_available = extractor.is_month_available(month)
            closest = extractor.get_closest_available_month(month)
            print(f"   月份 {month}: 可用={is_available}, 最近可用={closest}")
    
    def test_fuel_price_data_consistency(self):
        """测试燃油价格数据一致性"""
        # 测试所有2024年月份的价格数据
        for month in ['2024-01', '2024-06', '2024-12']:
            price_data = self.calculator.get_fuel_price_by_month(month)
            
            # 验证价格数据结构
            self.assertIn('base_price', price_data)
            self.assertIn('cost_range', price_data)
            self.assertIn('trend', price_data)
            
            # 验证价格数据合理性
            self.assertGreater(price_data['base_price'], 0)
            self.assertEqual(len(price_data['cost_range']), 2)
            self.assertGreater(price_data['cost_range'][1], price_data['cost_range'][0])
        
        print(f"✅ 燃油价格数据一致性验证通过")

if __name__ == '__main__':
    print("🧪 开始测试燃油价格计算器数据驱动修复...")
    unittest.main(verbosity=2) 