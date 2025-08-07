#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试最终修复后的数据日期提取器
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

from data_date_extractor import DataDateExtractor

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_final_date_extractor():
    """测试最终修复后的日期提取器"""
    print("🧪 === 测试最终修复后的数据日期提取器 ===")
    print("开始时间:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    print()
    
    # 创建日期提取器
    extractor = DataDateExtractor()
    
    # 提取可用日期
    print("📊 提取可用日期信息...")
    date_info = extractor.extract_available_dates()
    
    print(f"\n📋 === 提取结果 ===")
    print(f"✅ 可用月份数量: {len(date_info['available_months'])}")
    print(f"✅ 完整日期范围: {date_info['min_date'].strftime('%Y-%m-%d')} 至 {date_info['max_date'].strftime('%Y-%m-%d')}")
    print(f"✅ 最早月份: {date_info['earliest_month']}")
    print(f"✅ 最新月份: {date_info['latest_month']}")
    
    # 显示前10个和后10个月份
    available_months = date_info['available_months']
    print(f"\n📅 月份列表（前10个）:")
    for month in available_months[:10]:
        print(f"   {month}")
    
    if len(available_months) > 20:
        print(f"   ... (省略 {len(available_months) - 20} 个月份) ...")
    
    print(f"\n📅 月份列表（后10个）:")
    for month in available_months[-10:]:
        print(f"   {month}")
    
    # 测试各年份的覆盖情况
    print(f"\n📊 === 年份覆盖分析 ===")
    years_coverage = {}
    for month in available_months:
        year = month.split('-')[0]
        if year not in years_coverage:
            years_coverage[year] = []
        years_coverage[year].append(month)
    
    for year, months in sorted(years_coverage.items()):
        print(f"{year}年: {len(months)} 个月份 ({months[0]} 至 {months[-1]})")
        if len(months) == 12:
            print(f"   ✅ 完整覆盖全年")
        else:
            print(f"   ⚠️  覆盖不完整，缺少 {12 - len(months)} 个月")
    
    # 测试关键月份的可用性
    print(f"\n🔍 === 关键月份测试 ===")
    test_months = [
        '2022-01', '2022-12', 
        '2023-01', '2023-12',
        '2024-01', '2024-12'
    ]
    
    for month in test_months:
        available = extractor.is_month_available(month)
        closest = extractor.get_closest_available_month(month)
        status = "✅" if available else "❌"
        print(f"   {month}: {status} 可用={available}, 最接近月份={closest}")
    
    # 测试获取当前月份
    print(f"\n📆 === 当前月份测试 ===")
    current_month = extractor.get_current_month_from_data()
    print(f"数据中的当前月份: {current_month}")
    
    # 最终验证：检查是否修复了原始问题
    print(f"\n🎯 === 原始问题验证 ===")
    if '2024-01' in available_months and '2024-12' in available_months:
        print("✅ 已成功识别2024年数据，原始问题已修复！")
        print("✅ 燃油价格计算器现在可以使用正确的2024年月份而不是默认的2022-01")
    else:
        print("❌ 2024年数据识别仍有问题")
    
    if len(years_coverage) >= 3:  # 应该有2022、2023、2024三年
        print("✅ 成功识别了多个年份的数据")
    else:
        print("❌ 年份识别不完整")
    
    print(f"\n🎉 === 测试完成 ===")
    return date_info

if __name__ == "__main__":
    test_final_date_extractor() 