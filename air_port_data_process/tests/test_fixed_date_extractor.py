#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试修复后的数据日期提取器
验证是否能正确读取整个文件的日期范围
"""

import os
import sys
from datetime import datetime
import logging

# 添加父目录到路径以导入模块
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)
sys.path.insert(0, os.path.join(parent_dir, 'src'))

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_fixed_date_extractor():
    """测试修复后的数据日期提取器"""
    print("🧪 === 测试修复后的数据日期提取器 ===")
    print("开始时间:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    
    try:
        # 导入修复后的数据日期提取器
        from data_date_extractor import DataDateExtractor
        
        print("\n📅 1. 初始化数据日期提取器...")
        extractor = DataDateExtractor()
        
        print("\n🔍 2. 提取日期信息...")
        date_info = extractor.extract_available_dates()
        
        print("\n📊 3. 分析结果:")
        print(f"   可用月份数量: {len(date_info['available_months'])}")
        print(f"   最早月份: {date_info['earliest_month']}")
        print(f"   最晚月份: {date_info['latest_month']}")
        print(f"   日期范围: {date_info['min_date'].strftime('%Y-%m-%d')} 至 {date_info['max_date'].strftime('%Y-%m-%d')}")
        
        # 按年份统计
        years = {}
        for month in date_info['available_months']:
            year = month.split('-')[0]
            if year not in years:
                years[year] = []
            years[year].append(month)
        
        print(f"\n📅 按年份分布:")
        for year, months in sorted(years.items()):
            print(f"   {year}年: {len(months)} 个月")
            if len(months) <= 12:  # 只显示月份少的年份的详细信息
                print(f"     月份: {sorted(months)}")
        
        # 检查2024年数据
        months_2024 = [m for m in date_info['available_months'] if m.startswith('2024-')]
        if months_2024:
            print(f"\n✅ 找到2024年数据: {len(months_2024)} 个月")
            print(f"   2024年月份: {sorted(months_2024)}")
        else:
            print(f"\n❌ 未找到2024年数据")
        
        # 检查是否还有2022-01问题
        if '2022-01' in date_info['available_months']:
            print(f"\n📝 2022-01在可用月份中 (这是正常的，因为数据确实包含这个月份)")
        
        return date_info
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_fuel_calculator_with_fixed_extractor():
    """测试使用修复后提取器的燃油价格计算器"""
    print("\n🔧 === 测试燃油价格计算器 ===")
    
    try:
        from fuel_price_calculator import FuelPriceCalculator
        
        print("初始化燃油价格计算器...")
        fuel_calc = FuelPriceCalculator()
        
        print(f"燃油价格计算器默认月份: {fuel_calc.current_month}")
        
        # 测试不同月份的燃油价格计算
        test_months = ['2024-01', '2024-06', '2024-12', '2022-01']
        
        for month in test_months:
            try:
                cost = fuel_calc.calculate_fuel_cost(1000, year_month=month)
                print(f"  {month}: 1000kg燃油成本 = {cost}")
            except Exception as e:
                print(f"  {month}: 计算失败 - {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ 燃油价格计算器测试失败: {e}")
        return False

if __name__ == "__main__":
    # 测试修复后的日期提取器
    date_info = test_fixed_date_extractor()
    
    if date_info:
        # 测试燃油价格计算器
        test_fuel_calculator_with_fixed_extractor()
        
        print(f"\n🎉 === 测试完成 ===")
        print("结束时间:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        
        # 总结关键信息
        print(f"\n📋 关键结论:")
        if date_info['latest_month'].startswith('2024-'):
            print(f"✅ 成功识别到2024年数据，最新月份: {date_info['latest_month']}")
            print(f"✅ 修复成功：数据日期提取器现在能正确读取整个文件")
        else:
            print(f"❌ 仍未正确识别2024年数据")
    else:
        print(f"\n❌ 测试失败，需要进一步调试") 