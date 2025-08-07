#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
专门查找2024年数据在文件中的位置
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

def find_2024_data_position():
    """查找2024年数据在文件中的位置"""
    print("🔍 === 查找2024年数据位置 ===")
    print("开始时间:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    
    data_file_path = os.path.join(parent_dir, "data", "22年1月1日至24年12月31日航班数据.xlsx")
    
    if not os.path.exists(data_file_path):
        print(f"❌ 数据文件不存在: {data_file_path}")
        return
    
    print(f"📁 数据文件: {os.path.basename(data_file_path)}")
    
    # 从文件结构检查我们知道总共有1,040,953行
    total_rows = 1040953
    print(f"总行数: {total_rows:,}")
    
    # 策略：在文件的不同位置进行二分查找来定位2024年数据
    positions_to_check = [
        400000, 500000, 600000, 700000, 800000, 900000, 1000000, 1030000
    ]
    
    found_2024_start = None
    
    for pos in positions_to_check:
        try:
            print(f"\n📍 检查位置 {pos:,}...")
            
            # 先读取一小样本来获取列结构
            df_header = pd.read_excel(data_file_path, nrows=1)
            date_col_index = None
            for i, col in enumerate(df_header.columns):
                if '日期' in str(col):
                    date_col_index = i
                    break
            
            if date_col_index is None:
                print("   未找到日期列")
                continue
            
            # 读取该位置的数据
            df_pos = pd.read_excel(data_file_path, skiprows=pos, nrows=100, header=None)
            
            # 获取日期列的数据
            if date_col_index < len(df_pos.columns):
                date_values = df_pos[date_col_index].dropna().head(10)
                print(f"   日期样本: {list(date_values)}")
                
                # 检查是否包含2024年数据
                for date_val in date_values:
                    date_str = str(date_val)
                    if '2024' in date_str:
                        print(f"   ✅ 找到2024年数据! 位置: {pos:,}")
                        found_2024_start = pos
                        break
                
                if found_2024_start:
                    break
            else:
                print(f"   列数不足，期望日期列在第{date_col_index}列")
                
        except Exception as e:
            print(f"   ❌ 位置 {pos:,} 检查失败: {e}")
    
    if found_2024_start:
        print(f"\n🎉 找到2024年数据开始位置: 约第 {found_2024_start:,} 行")
        
        # 进一步精确定位
        print(f"\n🔍 进一步精确定位...")
        for offset in range(-5000, 5001, 1000):
            check_pos = found_2024_start + offset
            if check_pos < 0:
                continue
                
            try:
                df_header = pd.read_excel(data_file_path, nrows=1)
                date_col_index = None
                for i, col in enumerate(df_header.columns):
                    if '日期' in str(col):
                        date_col_index = i
                        break
                
                df_check = pd.read_excel(data_file_path, skiprows=check_pos, nrows=10, header=None)
                if date_col_index < len(df_check.columns):
                    date_val = str(df_check[date_col_index].iloc[0])
                    print(f"   位置 {check_pos:,}: {date_val}")
                    
            except Exception as e:
                print(f"   位置 {check_pos:,}: 读取失败")
        
        return found_2024_start
    else:
        print(f"\n❌ 在检查的位置中未找到2024年数据")
        print(f"可能需要检查更后面的位置")
        return None

def test_large_sample_reading():
    """测试读取大样本数据来覆盖2024年"""
    print(f"\n📊 === 测试大样本读取 ===")
    
    data_file_path = os.path.join(parent_dir, "data", "22年1月1日至24年12月31日航班数据.xlsx")
    
    # 基于我们找到的2024年数据位置，计算需要读取的样本大小
    sample_sizes = [200000, 500000, 800000, 1000000]
    
    for sample_size in sample_sizes:
        try:
            print(f"\n尝试读取 {sample_size:,} 行...")
            df_sample = pd.read_excel(data_file_path, nrows=sample_size)
            
            # 查找日期列
            date_columns = [col for col in df_sample.columns if '日期' in col]
            if not date_columns:
                print(f"   未找到日期列")
                continue
            
            date_col = date_columns[0]
            df_sample[date_col] = pd.to_datetime(df_sample[date_col], errors='coerce')
            
            # 分析日期分布
            valid_dates = df_sample[df_sample[date_col].notna()]
            if len(valid_dates) > 0:
                min_date = valid_dates[date_col].min()
                max_date = valid_dates[date_col].max()
                
                # 统计年份分布
                years = valid_dates[date_col].dt.year.value_counts().sort_index()
                
                print(f"   日期范围: {min_date.strftime('%Y-%m-%d')} 至 {max_date.strftime('%Y-%m-%d')}")
                print(f"   年份分布: {dict(years)}")
                
                # 检查是否包含2024年
                if 2024 in years.index:
                    print(f"   ✅ 成功找到2024年数据: {years[2024]} 条")
                    return sample_size
                else:
                    print(f"   ❌ 未找到2024年数据")
            
        except Exception as e:
            print(f"   ❌ 读取 {sample_size:,} 行失败: {e}")
    
    return None

if __name__ == "__main__":
    # 查找2024年数据位置
    position_2024 = find_2024_data_position()
    
    # 测试大样本读取
    required_sample_size = test_large_sample_reading()
    
    print(f"\n📋 === 总结 ===")
    if position_2024:
        print(f"✅ 2024年数据大约从第 {position_2024:,} 行开始")
    if required_sample_size:
        print(f"✅ 需要读取至少 {required_sample_size:,} 行才能覆盖2024年数据")
        print(f"建议在数据日期提取器中使用 sample_size >= {required_sample_size}")
    else:
        print(f"❌ 需要进一步调查") 