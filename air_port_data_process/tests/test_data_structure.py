#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查数据文件的实际结构，确认数据的时间分布
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

def check_data_structure():
    """检查数据文件的实际结构"""
    print("🔍 === 检查数据文件结构 ===")
    print("开始时间:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    
    data_file_path = os.path.join(parent_dir, "data", "22年1月1日至24年12月31日航班数据.xlsx")
    
    if not os.path.exists(data_file_path):
        print(f"❌ 数据文件不存在: {data_file_path}")
        return
    
    print(f"📁 数据文件: {os.path.basename(data_file_path)}")
    
    # 1. 检查文件信息
    file_size_mb = os.path.getsize(data_file_path) / (1024*1024)
    print(f"   文件大小: {file_size_mb:.1f} MB")
    
    # 2. 读取不同位置的数据样本
    sample_positions = [
        {"name": "开头", "skip": 0, "rows": 1000},
        {"name": "中间1", "skip": 50000, "rows": 1000}, 
        {"name": "中间2", "skip": 100000, "rows": 1000},
        {"name": "中间3", "skip": 200000, "rows": 1000},
        {"name": "末尾", "skip": 300000, "rows": 1000}
    ]
    
    for position in sample_positions:
        try:
            print(f"\n📊 检查{position['name']}数据 (跳过{position['skip']}行)...")
            
            # 读取数据
            df_sample = pd.read_excel(
                data_file_path, 
                skiprows=position['skip'], 
                nrows=position['rows']
            )
            
            print(f"   读取成功: {len(df_sample)} 行")
            
            # 查找日期列
            date_columns = [col for col in df_sample.columns if '日期' in col]
            
            if date_columns:
                date_col = date_columns[0]
                print(f"   日期列: {date_col}")
                
                # 转换日期
                df_sample[date_col] = pd.to_datetime(df_sample[date_col], errors='coerce')
                df_sample['year_month'] = df_sample[date_col].dt.strftime('%Y-%m')
                
                # 统计年月分布
                month_counts = df_sample['year_month'].value_counts().sort_index()
                print(f"   年月分布:")
                for month, count in month_counts.items():
                    print(f"     {month}: {count} 条")
                
                # 显示日期范围
                valid_dates = df_sample[df_sample[date_col].notna()]
                if len(valid_dates) > 0:
                    min_date = valid_dates[date_col].min()
                    max_date = valid_dates[date_col].max()
                    print(f"   日期范围: {min_date.strftime('%Y-%m-%d')} 至 {max_date.strftime('%Y-%m-%d')}")
                else:
                    print(f"   ⚠️ 没有有效日期")
                    
            else:
                print(f"   ⚠️ 没有找到日期列")
                print(f"   可用列: {list(df_sample.columns)}")
                
        except Exception as e:
            print(f"   ❌ 读取失败: {e}")
    
    # 3. 尝试使用更大的样本来分析整体结构
    print(f"\n🔍 分析整体数据结构...")
    try:
        # 使用chunk方式读取，避免内存问题
        chunk_size = 10000
        all_months = set()
        total_rows = 0
        chunk_count = 0
        
        print(f"正在分块读取数据 (每块{chunk_size}行)...")
        
        for chunk in pd.read_excel(data_file_path, chunksize=chunk_size):
            chunk_count += 1
            total_rows += len(chunk)
            
            # 查找日期列
            date_columns = [col for col in chunk.columns if '日期' in col]
            
            if date_columns:
                date_col = date_columns[0]
                
                # 转换日期
                chunk[date_col] = pd.to_datetime(chunk[date_col], errors='coerce')
                chunk['year_month'] = chunk[date_col].dt.strftime('%Y-%m')
                
                # 收集月份
                chunk_months = set(chunk['year_month'].dropna().unique())
                all_months.update(chunk_months)
                
                print(f"   块 {chunk_count}: {len(chunk)} 行, 月份: {sorted(chunk_months)}")
            
            # 限制读取块数，避免太慢
            if chunk_count >= 20:  # 最多读取20块
                print(f"   (为节省时间，只读取前{chunk_count}块)")
                break
        
        print(f"\n📊 整体统计:")
        print(f"   已读取行数: {total_rows:,}")
        print(f"   发现的月份数: {len(all_months)}")
        print(f"   月份列表: {sorted(all_months)}")
        
        # 按年份分组
        years = {}
        for month in all_months:
            if month and '-' in month:
                year = month.split('-')[0]
                if year not in years:
                    years[year] = []
                years[year].append(month)
        
        print(f"\n📅 按年份分组:")
        for year, months in sorted(years.items()):
            print(f"   {year}年: {len(months)} 个月 - {sorted(months)}")
        
    except Exception as e:
        print(f"❌ 整体分析失败: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\n🎉 === 检查完成 ===")
    print("结束时间:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

if __name__ == "__main__":
    check_data_structure() 