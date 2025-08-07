#!/usr/bin/env python3
"""
测试2024年数据筛选逻辑
检查筛选是否正确工作
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime

# 添加src目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

def test_2024_data_filter():
    """测试2024年数据筛选逻辑"""
    
    # 数据文件路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_file = os.path.join(current_dir, '..', 'data', '22年1月1日至24年12月31日航班数据.xlsx')
    
    print("🔍 === 测试2024年数据筛选逻辑 ===")
    print(f"数据文件: {data_file}")
    
    # 检查文件是否存在
    if not os.path.exists(data_file):
        print(f"❌ 数据文件不存在: {data_file}")
        return
    
    print(f"✅ 数据文件存在，大小: {os.path.getsize(data_file) / (1024*1024):.1f} MB")
    
    try:
        # 1. 读取数据
        print("\n📖 正在读取数据...")
        df = pd.read_excel(data_file)
        print(f"✅ 数据读取成功，总记录数: {len(df):,}")
        
        # 2. 查看列名
        print(f"\n📋 数据列信息 (共{len(df.columns)}列):")
        for i, col in enumerate(df.columns):
            print(f"  {i+1:2d}. {col}")
        
        # 3. 查找日期相关列
        print(f"\n📅 查找日期相关列...")
        date_related_columns = [col for col in df.columns if '日期' in col or '时间' in col or 'date' in col.lower()]
        print(f"找到 {len(date_related_columns)} 个日期相关列:")
        for col in date_related_columns:
            print(f"  - {col}")
        
        # 4. 分析每个日期列
        for col in date_related_columns:
            print(f"\n🔍 分析列 '{col}':")
            
            # 查看数据类型
            print(f"  数据类型: {df[col].dtype}")
            
            # 查看前几个值
            print(f"  前5个值:")
            for i, val in enumerate(df[col].head()):
                print(f"    {i+1}. {val} (类型: {type(val)})")
            
            # 查看唯一值数量
            unique_count = df[col].nunique()
            print(f"  唯一值数量: {unique_count}")
            
            # 查看是否有空值
            null_count = df[col].isnull().sum()
            print(f"  空值数量: {null_count}")
            
            # 尝试转换为日期格式
            try:
                date_series = pd.to_datetime(df[col], errors='coerce')
                valid_dates = date_series.dropna()
                
                if len(valid_dates) > 0:
                    print(f"  ✅ 成功转换为日期格式")
                    print(f"  有效日期数量: {len(valid_dates)}")
                    print(f"  日期范围: {valid_dates.min()} 到 {valid_dates.max()}")
                    
                    # 按年份统计
                    year_counts = valid_dates.dt.year.value_counts().sort_index()
                    print(f"  按年份统计:")
                    for year, count in year_counts.items():
                        print(f"    {year}: {count:,} 条记录")
                    
                    # 测试2024年筛选
                    data_2024 = df[date_series.dt.year == 2024]
                    print(f"  📊 2024年数据筛选结果: {len(data_2024):,} 条记录")
                    
                    if len(data_2024) > 0:
                        print(f"  ✅ 找到2024年数据")
                        # 查看2024年数据的日期分布
                        dates_2024 = pd.to_datetime(data_2024[col], errors='coerce')
                        month_counts = dates_2024.dt.month.value_counts().sort_index()
                        print(f"  2024年按月份统计:")
                        for month, count in month_counts.items():
                            print(f"    {month:2d}月: {count:,} 条记录")
                    else:
                        print(f"  ❌ 未找到2024年数据")
                        
                else:
                    print(f"  ❌ 无法转换为有效日期格式")
                    
            except Exception as e:
                print(f"  ❌ 日期转换失败: {e}")
        
        # 5. 测试原始筛选逻辑
        print(f"\n🧪 测试原始筛选逻辑...")
        
        # 查找包含'日期'的列
        date_columns = [col for col in df.columns if '日期' in col]
        print(f"找到包含'日期'的列: {date_columns}")
        
        if date_columns:
            date_col = date_columns[0]
            print(f"使用日期列: {date_col}")
            
            # 转换日期格式
            df_test = df.copy()
            df_test[date_col] = pd.to_datetime(df_test[date_col], errors='coerce')
            
            # 筛选2024年数据
            data_2024 = df_test[df_test[date_col].dt.year == 2024]
            
            print(f"原始筛选逻辑结果: {len(data_2024):,} 条记录")
            
            if len(data_2024) > 0:
                print(f"✅ 筛选成功!")
                
                # 验证数据有效性
                required_fields = ['机型', '里程（公里）', '人数']
                missing_fields = [field for field in required_fields if field not in data_2024.columns]
                
                if missing_fields:
                    print(f"❌ 缺少必要字段: {missing_fields}")
                else:
                    print(f"✅ 包含所有必要字段")
                    
                    # 统计有效数据
                    valid_data = data_2024[
                        (data_2024['机型'].notna()) & 
                        (data_2024['机型'] != '') &
                        (data_2024['里程（公里）'] > 0) &
                        (data_2024['人数'] > 0)
                    ]
                    
                    print(f"有效数据记录: {len(valid_data):,} 条")
                    print(f"有效数据比例: {len(valid_data)/len(data_2024)*100:.1f}%")
                    
                    # 显示机型统计
                    if len(valid_data) > 0:
                        print(f"\n📊 2024年机型统计 (前10):")
                        aircraft_counts = valid_data['机型'].value_counts().head(10)
                        for aircraft, count in aircraft_counts.items():
                            print(f"  {aircraft}: {count:,} 条")
                    
            else:
                print(f"❌ 筛选失败，未找到2024年数据")
                
                # 分析原因
                print(f"\n🔍 分析失败原因...")
                
                # 查看日期列的实际值
                print(f"日期列 '{date_col}' 的值分布:")
                date_values = df[date_col].value_counts().head(10)
                for val, count in date_values.items():
                    print(f"  {val}: {count} 条")
                    
                # 尝试不同的日期解析方式
                print(f"\n🔧 尝试不同的日期解析方式...")
                
                # 方式1：推断日期格式
                try:
                    dates_infer = pd.to_datetime(df[date_col], infer_datetime_format=True, errors='coerce')
                    valid_dates_infer = dates_infer.dropna()
                    if len(valid_dates_infer) > 0:
                        print(f"  方式1 - 推断格式: 成功解析 {len(valid_dates_infer)} 个日期")
                        year_counts = valid_dates_infer.dt.year.value_counts().sort_index()
                        print(f"  年份分布: {dict(year_counts)}")
                    else:
                        print(f"  方式1 - 推断格式: 失败")
                except Exception as e:
                    print(f"  方式1 - 推断格式: 异常 - {e}")
                
                # 方式2：指定格式
                for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%m/%d/%Y', '%d/%m/%Y']:
                    try:
                        dates_fmt = pd.to_datetime(df[date_col], format=fmt, errors='coerce')
                        valid_dates_fmt = dates_fmt.dropna()
                        if len(valid_dates_fmt) > 0:
                            print(f"  方式2 - 格式{fmt}: 成功解析 {len(valid_dates_fmt)} 个日期")
                            year_counts = valid_dates_fmt.dt.year.value_counts().sort_index()
                            print(f"  年份分布: {dict(year_counts)}")
                        else:
                            print(f"  方式2 - 格式{fmt}: 失败")
                    except Exception as e:
                        print(f"  方式2 - 格式{fmt}: 异常 - {e}")
        
        else:
            print(f"❌ 未找到包含'日期'的列")
        
        print(f"\n🎯 === 测试完成 ===")
        
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_2024_data_filter() 