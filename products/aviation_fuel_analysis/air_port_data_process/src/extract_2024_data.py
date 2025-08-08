#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
提取2024年数据到单独的Excel文件
"""

import os
import pandas as pd
from datetime import datetime
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def extract_2024_data():
    """提取2024年数据到单独文件"""
    print("🔍 === 提取2024年数据 ===")
    print("开始时间:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    
    # 文件路径
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, '../data')
    source_file = os.path.join(data_dir, '22年1月1日至24年12月31日航班数据.xlsx')
    output_file = os.path.join(data_dir, '2024年航班数据.xlsx')
    
    if not os.path.exists(source_file):
        print(f"❌ 源数据文件不存在: {source_file}")
        return False
    
    print(f"📁 源文件: {os.path.basename(source_file)}")
    print(f"📁 输出文件: {os.path.basename(output_file)}")
    
    try:
        # 根据您提供的信息，2024年数据从第693361行开始
        start_row = 693361
        print(f"从第 {start_row:,} 行开始读取2024年数据...")
        
        # 先读取列头
        print("读取列头信息...")
        df_header = pd.read_excel(source_file, nrows=1)
        columns = list(df_header.columns)
        print(f"列数: {len(columns)}")
        print(f"列名: {columns}")
        
        # 查找日期列
        date_col_index = None
        for i, col in enumerate(columns):
            if '日期' in str(col):
                date_col_index = i
                print(f"找到日期列: '{col}' (第{i+1}列)")
                break
        
        if date_col_index is None:
            print("❌ 未找到日期列")
            return False
        
        # 读取2024年数据
        # 从693361行开始读取，直到文件结束
        print(f"正在读取2024年数据...")
        df_2024 = pd.read_excel(
            source_file, 
            skiprows=start_row,  # 跳过前693361行
            header=None,  # 不使用数据行作为标题
            names=columns  # 使用之前获取的列名
        )
        
        print(f"成功读取 {len(df_2024):,} 行数据")
        
        if len(df_2024) == 0:
            print("❌ 未读取到任何数据")
            return False
        
        # 验证日期列
        date_col = columns[date_col_index]
        print(f"转换日期列: {date_col}")
        df_2024[date_col] = pd.to_datetime(df_2024[date_col], errors='coerce')
        
        # 检查日期分布
        valid_dates = df_2024[df_2024[date_col].notna()]
        if len(valid_dates) > 0:
            min_date = valid_dates[date_col].min()
            max_date = valid_dates[date_col].max()
            
            print(f"日期范围: {min_date.strftime('%Y-%m-%d')} 至 {max_date.strftime('%Y-%m-%d')}")
            
            # 统计年份分布
            years = valid_dates[date_col].dt.year.value_counts().sort_index()
            print(f"年份分布: {dict(years)}")
            
            # 筛选确实是2024年的数据
            df_2024_filtered = df_2024[df_2024[date_col].dt.year == 2024]
            print(f"筛选后2024年数据: {len(df_2024_filtered):,} 行")
            
            if len(df_2024_filtered) > 0:
                # 保存到Excel文件
                print(f"正在保存到 {output_file}...")
                df_2024_filtered.to_excel(output_file, index=False)
                
                file_size_mb = os.path.getsize(output_file) / (1024*1024)
                print(f"✅ 2024年数据保存成功!")
                print(f"   文件大小: {file_size_mb:.1f} MB")
                print(f"   数据行数: {len(df_2024_filtered):,}")
                
                # 显示月份分布
                months_2024 = df_2024_filtered[date_col].dt.strftime('%Y-%m').value_counts().sort_index()
                print(f"   月份分布:")
                for month, count in months_2024.items():
                    print(f"     {month}: {count:,} 条")
                
                return True
            else:
                print("❌ 筛选后没有2024年数据")
                return False
        else:
            print("❌ 没有有效的日期数据")
            return False
            
    except Exception as e:
        print(f"❌ 提取2024年数据失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def verify_2024_data():
    """验证提取的2024年数据"""
    print(f"\n🔍 === 验证2024年数据 ===")
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, '../data')
    output_file = os.path.join(data_dir, '2024年航班数据.xlsx')
    
    if not os.path.exists(output_file):
        print(f"❌ 2024年数据文件不存在: {output_file}")
        return False
    
    try:
        # 读取并验证
        df_verify = pd.read_excel(output_file, nrows=1000)  # 读取前1000行进行验证
        
        print(f"文件验证:")
        print(f"   行数: {len(df_verify):,}")
        print(f"   列数: {len(df_verify.columns)}")
        
        # 查找日期列
        date_columns = [col for col in df_verify.columns if '日期' in col]
        if date_columns:
            date_col = date_columns[0]
            df_verify[date_col] = pd.to_datetime(df_verify[date_col], errors='coerce')
            
            valid_dates = df_verify[df_verify[date_col].notna()]
            if len(valid_dates) > 0:
                min_date = valid_dates[date_col].min()
                max_date = valid_dates[date_col].max()
                print(f"   日期范围: {min_date.strftime('%Y-%m-%d')} 至 {max_date.strftime('%Y-%m-%d')}")
                
                # 检查是否都是2024年
                non_2024 = valid_dates[valid_dates[date_col].dt.year != 2024]
                if len(non_2024) == 0:
                    print(f"   ✅ 验证通过：所有数据都是2024年")
                else:
                    print(f"   ⚠️ 发现非2024年数据: {len(non_2024)} 条")
            
        return True
        
    except Exception as e:
        print(f"❌ 验证失败: {e}")
        return False

if __name__ == "__main__":
    # 提取2024年数据
    success = extract_2024_data()
    
    if success:
        # 验证提取的数据
        verify_2024_data()
        
        print(f"\n🎉 === 完成 ===")
        print("2024年数据已成功提取到单独的Excel文件中")
    else:
        print(f"\n❌ === 失败 ===")
        print("2024年数据提取失败") 