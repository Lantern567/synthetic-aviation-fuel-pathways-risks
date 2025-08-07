#!/usr/bin/env python3
"""
测试日期传递修复
验证修复后的代码是否正确传递日期参数给燃油价格计算器
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime

# 添加src目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from parallel_flight_processor import load_and_split_data, process_flight_data_with_pybada_enhanced

def test_date_fix_verification():
    """测试日期传递修复"""
    
    # 数据文件路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_file = os.path.join(current_dir, '..', 'data', '22年1月1日至24年12月31日航班数据.xlsx')
    
    print("🧪 === 测试日期传递修复 ===")
    print(f"数据文件: {data_file}")
    
    # 检查文件是否存在
    if not os.path.exists(data_file):
        print(f"❌ 数据文件不存在: {data_file}")
        return
    
    try:
        # 1. 加载和分割数据（测试筛选）
        print("\n🔍 测试数据加载和筛选...")
        chunks = load_and_split_data(data_file, chunk_size=100)  # 使用小chunk测试
        
        if not chunks:
            print("❌ 没有数据块")
            return
            
        print(f"✅ 数据分割完成，共 {len(chunks)} 个数据块")
        
        # 2. 取第一个数据块进行测试
        print(f"\n🧪 测试第一个数据块（chunk_id: {chunks[0][0]}）...")
        test_chunk_id, test_chunk_df = chunks[0]
        
        # 检查数据块内容
        print(f"数据块大小: {len(test_chunk_df)} 条记录")
        print(f"数据块列名: {list(test_chunk_df.columns)}")
        
        # 检查日期列
        date_columns = [col for col in test_chunk_df.columns if '日期' in col]
        if date_columns:
            date_col = date_columns[0]
            print(f"找到日期列: '{date_col}'")
            
            # 显示日期样本
            print("日期样本:")
            sample_dates = test_chunk_df[date_col].head(3)
            for i, date_val in enumerate(sample_dates):
                print(f"  {i+1}. {date_val}")
        
        # 3. 测试增强的处理函数
        print(f"\n🚀 测试增强的处理函数...")
        
        # 准备测试数据
        test_df = test_chunk_df.head(5).copy()  # 只取前5条记录进行测试
        
        # 添加必要的字段映射
        test_df['aircraft_type'] = test_df['机型']
        test_df['distance_km'] = test_df['里程（公里）']
        test_df['passengers'] = test_df['人数']
        
        # 添加日期信息处理
        if date_columns:
            date_col = date_columns[0]
            test_df[date_col] = pd.to_datetime(test_df[date_col], errors='coerce')
            test_df['flight_year_month'] = test_df[date_col].dt.strftime('%Y-%m')
            print(f"✅ 添加日期信息字段 'flight_year_month'")
            
            # 显示日期分布
            date_counts = test_df['flight_year_month'].value_counts().sort_index()
            print(f"📅 测试数据日期分布: {dict(date_counts)}")
        else:
            test_df['flight_year_month'] = '2024-12'
            print(f"⚠️ 未找到日期列，使用默认日期")
        
        # 调用增强的处理函数
        print(f"\n⚡ 开始处理 {len(test_df)} 条测试数据...")
        result_df = process_flight_data_with_pybada_enhanced(test_df)
        
        # 检查结果
        print(f"\n📊 处理结果分析:")
        print(f"输入记录数: {len(test_df)}")
        print(f"输出记录数: {len(result_df)}")
        
        # 检查是否有成功的计算结果
        if 'calculation_successful' in result_df.columns:
            success_count = len(result_df[result_df['calculation_successful'] == True])
            print(f"成功计算: {success_count}/{len(result_df)} 条记录")
        
        # 检查日期和燃油价格信息
        if 'flight_date' in result_df.columns:
            date_info = result_df['flight_date'].value_counts()
            print(f"航班日期分布: {dict(date_info)}")
        
        if 'pricing_month' in result_df.columns:
            price_month_info = result_df['pricing_month'].value_counts()
            print(f"燃油价格月份分布: {dict(price_month_info)}")
            
            # 检查是否还有2022-01的问题
            if '2022-01' in price_month_info.index:
                print(f"⚠️ 仍然发现2022-01燃油价格: {price_month_info['2022-01']} 条记录")
            else:
                print(f"✅ 没有发现2022-01燃油价格问题")
        
        # 显示详细结果样本
        print(f"\n📝 结果样本:")
        if len(result_df) > 0:
            sample_columns = ['aircraft_type', 'distance_km', 'passengers', 'flight_date', 
                            'pricing_month', 'fuel_cost_yuan_avg', 'calculation_successful']
            available_columns = [col for col in sample_columns if col in result_df.columns]
            
            if available_columns:
                print(f"显示列: {available_columns}")
                sample_result = result_df[available_columns].head(3)
                for idx, row in sample_result.iterrows():
                    print(f"  记录 {idx}:")
                    for col in available_columns:
                        print(f"    {col}: {row[col]}")
                    print()
            
        print(f"✅ 日期传递修复测试完成")
        
    except Exception as e:
        print(f"❌ 测试过程中出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_date_fix_verification() 