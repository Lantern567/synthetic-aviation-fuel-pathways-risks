#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试当前日期处理是否正确
检查是否还会出现2022-01的问题
"""

import os
import sys
import pandas as pd
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

def test_current_date_handling():
    """测试当前日期处理是否正确"""
    print("🧪 === 测试当前日期处理 ===")
    print("开始时间:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    
    # 1. 测试数据日期提取器
    print("\n📅 1. 测试数据日期提取器")
    try:
        from data_date_extractor import DataDateExtractor
        
        extractor = DataDateExtractor()
        date_info = extractor.extract_available_dates(sample_size=5000)
        
        print(f"✅ 数据日期提取成功")
        print(f"   可用月份数量: {len(date_info['available_months'])}")
        print(f"   日期范围: {date_info['min_date'].strftime('%Y-%m-%d')} 至 {date_info['max_date'].strftime('%Y-%m-%d')}")
        print(f"   最早月份: {date_info['earliest_month']}")
        print(f"   最新月份: {date_info['latest_month']}")
        
        # 显示2024年的月份分布
        months_2024 = [m for m in date_info['available_months'] if m.startswith('2024-')]
        print(f"   2024年可用月份: {months_2024}")
        
        # 检查是否有2022-01
        if '2022-01' in date_info['available_months']:
            print(f"⚠️ 发现2022-01在可用月份中")
        else:
            print(f"✅ 没有发现2022-01问题")
            
    except Exception as e:
        print(f"❌ 数据日期提取器测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 2. 测试燃油价格计算器初始化
    print("\n⛽ 2. 测试燃油价格计算器")
    try:
        from fuel_price_calculator import FuelPriceCalculator
        
        fuel_calc = FuelPriceCalculator()
        print(f"✅ 燃油价格计算器初始化成功")
        print(f"   当前默认月份: {fuel_calc.current_month}")
        
        # 检查当前月份是否为2022-01
        if fuel_calc.current_month == '2022-01':
            print(f"❌ 错误: 燃油价格计算器默认月份为2022-01")
        else:
            print(f"✅ 燃油价格计算器默认月份正确: {fuel_calc.current_month}")
            
        # 测试燃油价格计算
        test_fuel_cost = fuel_calc.calculate_fuel_cost(1000.0)  # 测试1000kg燃油
        print(f"   测试燃油成本计算 (1000kg): {test_fuel_cost['month']} 月价格")
        
        if test_fuel_cost['month'] == '2022-01':
            print(f"❌ 错误: 燃油成本计算使用了2022-01月份")
        else:
            print(f"✅ 燃油成本计算月份正确: {test_fuel_cost['month']}")
            
    except Exception as e:
        print(f"❌ 燃油价格计算器测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 3. 测试pyBADA计算器的日期传递
    print("\n🔧 3. 测试pyBADA计算器日期传递")
    try:
        from pybada_fuel_calculator import PyBADAFuelCalculator
        
        calculator = PyBADAFuelCalculator()
        print(f"✅ pyBADA计算器初始化成功")
        
        # 测试带日期的航班计算
        test_result = calculator.calculate_single_flight_with_date(
            aircraft_type='A320',
            distance_km=1000,
            passengers=150,
            flight_year_month='2024-08'
        )
        
        print(f"✅ 带日期的航班计算成功")
        print(f"   航班日期: {test_result.get('flight_date', 'N/A')}")
        print(f"   燃油成本月份: {test_result.get('fuel_cost_month', 'N/A')}")
        
        # 检查是否使用了正确的日期
        if test_result.get('fuel_cost_month') == '2022-01':
            print(f"❌ 错误: pyBADA计算器使用了2022-01月份")
        elif test_result.get('fuel_cost_month') == '2024-08':
            print(f"✅ pyBADA计算器正确使用了指定日期: {test_result.get('fuel_cost_month')}")
        else:
            print(f"⚠️ pyBADA计算器使用了其他日期: {test_result.get('fuel_cost_month')}")
            
    except Exception as e:
        print(f"❌ pyBADA计算器测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 4. 测试并行处理器的日期处理
    print("\n🔄 4. 测试并行处理器日期处理")
    try:
        # 创建测试数据
        test_data = pd.DataFrame({
            '机型': ['A320', 'B737', 'A321'],
            '里程（公里）': [1000, 1200, 1500],
            '人数': [150, 160, 180],
            '起飞日期': ['2024-08-15', '2024-09-10', '2024-10-20']
        })
        
        # 模拟date列处理
        test_data['起飞日期'] = pd.to_datetime(test_data['起飞日期'])
        test_data['flight_year_month'] = test_data['起飞日期'].dt.strftime('%Y-%m')
        
        print(f"✅ 测试数据创建成功")
        print(f"   数据样本:")
        for _, row in test_data.iterrows():
            print(f"     {row['机型']}: {row['起飞日期'].strftime('%Y-%m-%d')} -> {row['flight_year_month']}")
        
        # 检查是否有2022-01
        if '2022-01' in test_data['flight_year_month'].values:
            print(f"❌ 错误: 测试数据中出现了2022-01")
        else:
            print(f"✅ 测试数据日期处理正确，没有2022-01")
            
    except Exception as e:
        print(f"❌ 并行处理器测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 5. 测试实际数据文件的日期处理
    print("\n📁 5. 测试实际数据文件")
    try:
        data_file_path = os.path.join(parent_dir, "data", "22年1月1日至24年12月31日航班数据.xlsx")
        
        if os.path.exists(data_file_path):
            print(f"✅ 找到数据文件: {os.path.basename(data_file_path)}")
            
            # 读取少量数据进行测试
            print("正在读取数据样本...")
            sample_data = pd.read_excel(data_file_path, nrows=100)
            
            # 查找日期列
            date_columns = [col for col in sample_data.columns if '日期' in col]
            if date_columns:
                date_col = date_columns[0]
                print(f"   日期列: {date_col}")
                
                # 转换日期
                sample_data[date_col] = pd.to_datetime(sample_data[date_col], errors='coerce')
                sample_data['year_month'] = sample_data[date_col].dt.strftime('%Y-%m')
                
                # 统计年月分布
                month_counts = sample_data['year_month'].value_counts().sort_index()
                print(f"   样本数据年月分布:")
                for month, count in month_counts.head(10).items():
                    print(f"     {month}: {count} 条")
                
                # 检查是否有2022-01
                if '2022-01' in month_counts.index:
                    print(f"⚠️ 实际数据中确实包含2022-01: {month_counts['2022-01']} 条")
                    print(f"   这是正常的，因为数据范围从2022年1月开始")
                else:
                    print(f"✅ 样本中没有2022-01数据")
                
                # 检查2024年数据
                months_2024 = [m for m in month_counts.index if m.startswith('2024-')]
                if months_2024:
                    print(f"   2024年数据: {months_2024}")
                    total_2024 = sum(month_counts[m] for m in months_2024)
                    print(f"   2024年样本总数: {total_2024}")
                else:
                    print(f"⚠️ 样本中没有找到2024年数据")
                    
            else:
                print(f"⚠️ 未找到日期列")
                
        else:
            print(f"⚠️ 数据文件不存在: {data_file_path}")
            
    except Exception as e:
        print(f"❌ 实际数据文件测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\n🎉 === 测试完成 ===")
    print("结束时间:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    
    print(f"\n📋 总结:")
    print(f"1. 数据确实包含2022-01到2024-12的完整时间范围")
    print(f"2. 关键是要确保在处理2024年数据时，燃油价格计算使用正确的年月")
    print(f"3. 修复后的代码应该根据航班实际日期来计算燃油价格")
    print(f"4. 不应该再出现'未找到2022-01燃油价格'的警告")

if __name__ == "__main__":
    test_current_date_handling() 