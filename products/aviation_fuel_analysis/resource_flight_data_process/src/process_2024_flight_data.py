#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2024年航班数据处理脚本
筛选五个机场数据并分析每日数据条数的时间序列
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import os
import warnings
warnings.filterwarnings('ignore')

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False

class FlightDataProcessor:
    def __init__(self, data_file_path):
        self.data_file_path = data_file_path
        self.raw_data = None
        self.filtered_data = {}
        
        # 定义五个主要机场的IATA代码和名称
        self.target_airports = {
            'PEK': '北京首都国际机场',
            'PKX': '北京大兴国际机场', 
            'TSN': '天津滨海国际机场',
            'SJW': '石家庄正定国际机场',
            'HDG': '邯郸机场'
        }
        
    def load_data(self):
        """加载Excel数据"""
        try:
            print(f"正在加载数据文件: {self.data_file_path}")
            
            # 尝试读取Excel文件的所有sheet
            excel_file = pd.ExcelFile(self.data_file_path)
            print(f"发现以下工作表: {excel_file.sheet_names}")
            
            # 读取第一个工作表（通常是主要数据）
            self.raw_data = pd.read_excel(self.data_file_path, sheet_name=0)
            
            print(f"数据形状: {self.raw_data.shape}")
            print(f"列名: {list(self.raw_data.columns)}")
            print("\n前5行数据预览:")
            print(self.raw_data.head())
            
            return True
            
        except Exception as e:
            print(f"加载数据时出错: {e}")
            return False
    
    def analyze_data_structure(self):
        """分析数据结构"""
        if self.raw_data is None:
            print("请先加载数据")
            return
            
        print("\n=== 数据结构分析 ===")
        print(f"总行数: {len(self.raw_data)}")
        print(f"总列数: {len(self.raw_data.columns)}")
        
        print("\n列信息:")
        for i, col in enumerate(self.raw_data.columns):
            dtype = self.raw_data[col].dtype
            null_count = self.raw_data[col].isnull().sum()
            print(f"{i+1}. {col} - 类型: {dtype}, 空值: {null_count}")
        
        # 查找可能的机场代码列
        print("\n查找机场相关列:")
        airport_related_cols = []
        for col in self.raw_data.columns:
            col_lower = str(col).lower()
            if any(keyword in col_lower for keyword in ['airport', 'iata', 'icao', '机场', '起飞', '降落', '出发', '到达']):
                airport_related_cols.append(col)
                unique_vals = self.raw_data[col].nunique()
                print(f"  - {col}: {unique_vals}个唯一值")
                if unique_vals < 20:  # 显示少量唯一值的样例
                    print(f"    样例值: {list(self.raw_data[col].dropna().unique()[:10])}")
        
        # 查找日期相关列
        print("\n查找日期相关列:")
        date_related_cols = []
        for col in self.raw_data.columns:
            col_lower = str(col).lower()
            if any(keyword in col_lower for keyword in ['date', 'time', '日期', '时间', '年', '月', '日']):
                date_related_cols.append(col)
                print(f"  - {col}")
                print(f"    样例值: {list(self.raw_data[col].dropna().head())}")
    
    def identify_airport_columns(self):
        """识别机场相关列"""
        if self.raw_data is None:
            return None, None
            
        # 常见的机场列名模式
        departure_patterns = ['departure', 'origin', 'dep', '出发', '起飞', 'from']
        arrival_patterns = ['arrival', 'destination', 'arr', '到达', '降落', 'to']
        
        dep_col = None
        arr_col = None
        
        for col in self.raw_data.columns:
            col_lower = str(col).lower()
            
            # 检查出发机场列
            if any(pattern in col_lower for pattern in departure_patterns):
                dep_col = col
                
            # 检查到达机场列  
            if any(pattern in col_lower for pattern in arrival_patterns):
                arr_col = col
        
        print(f"识别的出发机场列: {dep_col}")
        print(f"识别的到达机场列: {arr_col}")
        
        return dep_col, arr_col
    
    def identify_date_column(self):
        """识别日期列"""
        if self.raw_data is None:
            return None
            
        date_patterns = ['date', 'time', '日期', '时间', '年月日']
        
        for col in self.raw_data.columns:
            col_lower = str(col).lower()
            if any(pattern in col_lower for pattern in date_patterns):
                # 检查是否包含日期格式数据
                sample_data = self.raw_data[col].dropna().head()
                try:
                    pd.to_datetime(sample_data)
                    print(f"识别的日期列: {col}")
                    return col
                except:
                    continue
        
        # 如果没有明显的日期列，尝试查找包含2024的列
        for col in self.raw_data.columns:
            if self.raw_data[col].dtype == 'object':
                sample_str = str(self.raw_data[col].dropna().iloc[0]) if len(self.raw_data[col].dropna()) > 0 else ""
                if '2024' in sample_str:
                    print(f"可能的日期列: {col}")
                    return col
        
        return None
    
    def filter_airports(self, dep_col, arr_col):
        """筛选目标机场的数据"""
        if self.raw_data is None:
            print("请先加载数据")
            return
            
        target_codes = list(self.target_airports.keys())
        
        # 筛选涉及目标机场的航班（出发或到达）
        if dep_col and arr_col:
            mask = (self.raw_data[dep_col].isin(target_codes)) | (self.raw_data[arr_col].isin(target_codes))
            filtered_df = self.raw_data[mask].copy()
        elif dep_col:
            mask = self.raw_data[dep_col].isin(target_codes)
            filtered_df = self.raw_data[mask].copy()
        elif arr_col:
            mask = self.raw_data[arr_col].isin(target_codes)
            filtered_df = self.raw_data[mask].copy()
        else:
            print("未找到机场相关列")
            return
        
        print(f"\n筛选后数据行数: {len(filtered_df)}")
        
        # 按机场分组保存数据
        for airport_code in target_codes:
            if dep_col and arr_col:
                airport_mask = (filtered_df[dep_col] == airport_code) | (filtered_df[arr_col] == airport_code)
            elif dep_col:
                airport_mask = filtered_df[dep_col] == airport_code
            else:
                airport_mask = filtered_df[arr_col] == airport_code
                
            airport_data = filtered_df[airport_mask].copy()
            
            if len(airport_data) > 0:
                self.filtered_data[airport_code] = airport_data
                print(f"{self.target_airports[airport_code]} ({airport_code}): {len(airport_data)}条记录")
        
        return filtered_df
    
    def analyze_daily_time_series(self, date_col):
        """分析每个机场每日数据条数的时间序列"""
        if not self.filtered_data:
            print("请先筛选机场数据")
            return
            
        print(f"\n=== 每日数据条数时间序列分析 ===")
        
        # 创建结果目录
        results_dir = "results/2024_flight_analysis"
        os.makedirs(results_dir, exist_ok=True)
        
        all_daily_stats = {}
        
        for airport_code, data in self.filtered_data.items():
            airport_name = self.target_airports[airport_code]
            print(f"\n分析 {airport_name} ({airport_code}):")
            
            if date_col not in data.columns:
                print(f"  警告: 未找到日期列 {date_col}")
                continue
            
            # 转换日期列
            try:
                data['date_parsed'] = pd.to_datetime(data[date_col])
            except Exception as e:
                print(f"  日期解析错误: {e}")
                continue
            
            # 提取日期部分（去除时间）
            data['date_only'] = data['date_parsed'].dt.date
            
            # 统计每日数据条数
            daily_counts = data.groupby('date_only').size().reset_index(name='count')
            daily_counts['date'] = pd.to_datetime(daily_counts['date_only'])
            daily_counts = daily_counts.sort_values('date')
            
            print(f"  数据日期范围: {daily_counts['date'].min()} 至 {daily_counts['date'].max()}")
            print(f"  总天数: {len(daily_counts)}")
            print(f"  平均每日航班数: {daily_counts['count'].mean():.1f}")
            print(f"  最大每日航班数: {daily_counts['count'].max()}")
            print(f"  最小每日航班数: {daily_counts['count'].min()}")
            
            # 保存每日统计数据
            daily_counts.to_csv(f"{results_dir}/{airport_code}_daily_counts.csv", index=False, encoding='utf-8-sig')
            
            # 存储用于总体分析
            all_daily_stats[airport_code] = daily_counts
            
            # 绘制时间序列图
            plt.figure(figsize=(15, 6))
            plt.plot(daily_counts['date'], daily_counts['count'], marker='o', linewidth=1, markersize=3)
            plt.title(f'{airport_name} ({airport_code}) - 2024年每日航班数时间序列', fontsize=14, fontweight='bold')
            plt.xlabel('日期', fontsize=12)
            plt.ylabel('航班数量', fontsize=12)
            plt.grid(True, alpha=0.3)
            plt.xticks(rotation=45)
            plt.tight_layout()
            plt.savefig(f"{results_dir}/{airport_code}_daily_timeseries.png", dpi=300, bbox_inches='tight')
            plt.close()
            
            # 月度统计
            daily_counts['month'] = daily_counts['date'].dt.to_period('M')
            monthly_stats = daily_counts.groupby('month')['count'].agg(['sum', 'mean', 'std']).round(2)
            monthly_stats.to_csv(f"{results_dir}/{airport_code}_monthly_stats.csv", encoding='utf-8-sig')
            
            print(f"  已保存: {airport_code}_daily_counts.csv, {airport_code}_daily_timeseries.png, {airport_code}_monthly_stats.csv")
        
        # 创建所有机场对比图
        self.create_comparison_plots(all_daily_stats, results_dir)
        
        return all_daily_stats
    
    def create_comparison_plots(self, all_daily_stats, results_dir):
        """创建所有机场的对比图"""
        if not all_daily_stats:
            return
            
        # 1. 所有机场时间序列对比
        plt.figure(figsize=(16, 10))
        
        for i, (airport_code, daily_data) in enumerate(all_daily_stats.items()):
            airport_name = self.target_airports[airport_code]
            plt.subplot(3, 2, i+1)
            plt.plot(daily_data['date'], daily_data['count'], color=f'C{i}', linewidth=1)
            plt.title(f'{airport_name} ({airport_code})')
            plt.xlabel('日期')
            plt.ylabel('航班数量')
            plt.grid(True, alpha=0.3)
            plt.xticks(rotation=45)
        
        plt.tight_layout()
        plt.savefig(f"{results_dir}/all_airports_comparison.png", dpi=300, bbox_inches='tight')
        plt.close()
        
        # 2. 月度总量对比
        monthly_totals = {}
        for airport_code, daily_data in all_daily_stats.items():
            daily_data['month'] = daily_data['date'].dt.to_period('M')
            monthly_sum = daily_data.groupby('month')['count'].sum()
            monthly_totals[airport_code] = monthly_sum
        
        monthly_df = pd.DataFrame(monthly_totals)
        monthly_df.fillna(0, inplace=True)
        
        plt.figure(figsize=(14, 8))
        monthly_df.plot(kind='bar', stacked=False, figsize=(14, 8))
        plt.title('各机场月度航班总数对比', fontsize=14, fontweight='bold')
        plt.xlabel('月份', fontsize=12)
        plt.ylabel('航班总数', fontsize=12)
        plt.legend([self.target_airports[code] for code in monthly_df.columns], bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.xticks(rotation=45)
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(f"{results_dir}/monthly_comparison.png", dpi=300, bbox_inches='tight')
        plt.close()
        
        # 保存月度对比数据
        monthly_df.to_csv(f"{results_dir}/monthly_comparison.csv", encoding='utf-8-sig')
        
        print(f"\n已保存对比图表: all_airports_comparison.png, monthly_comparison.png, monthly_comparison.csv")
    
    def save_filtered_data(self):
        """保存筛选后的数据"""
        if not self.filtered_data:
            print("没有筛选后的数据可保存")
            return
            
        results_dir = "results/2024_flight_analysis"
        os.makedirs(results_dir, exist_ok=True)
        
        # 保存各机场单独数据
        for airport_code, data in self.filtered_data.items():
            airport_name = self.target_airports[airport_code]
            filename = f"{results_dir}/{airport_code}_{airport_name}_2024航班数据.xlsx"
            data.to_excel(filename, index=False, encoding='utf-8-sig')
            print(f"已保存: {filename} ({len(data)}条记录)")
        
        # 保存汇总数据
        all_filtered = pd.concat(self.filtered_data.values(), ignore_index=True)
        summary_filename = f"{results_dir}/五机场汇总_2024航班数据.xlsx"
        all_filtered.to_excel(summary_filename, index=False, encoding='utf-8-sig')
        print(f"已保存汇总数据: {summary_filename} ({len(all_filtered)}条记录)")
        
        # 创建数据统计报告
        self.create_summary_report(results_dir)
    
    def create_summary_report(self, results_dir):
        """创建数据统计报告"""
        report_lines = []
        report_lines.append("=== 2024年航班数据处理报告 ===")
        report_lines.append(f"处理时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"原始数据文件: {self.data_file_path}")
        report_lines.append(f"原始数据行数: {len(self.raw_data) if self.raw_data is not None else 0}")
        report_lines.append("")
        
        report_lines.append("目标机场:")
        for code, name in self.target_airports.items():
            report_lines.append(f"  {code}: {name}")
        report_lines.append("")
        
        report_lines.append("筛选结果:")
        total_filtered = 0
        for airport_code, data in self.filtered_data.items():
            airport_name = self.target_airports[airport_code]
            count = len(data)
            total_filtered += count
            report_lines.append(f"  {airport_name} ({airport_code}): {count:,}条记录")
        
        report_lines.append(f"\n总计筛选记录: {total_filtered:,}条")
        report_lines.append(f"筛选比例: {total_filtered/len(self.raw_data)*100:.2f}%" if self.raw_data is not None else "")
        
        # 保存报告
        report_file = f"{results_dir}/数据处理报告.txt"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report_lines))
        
        print(f"\n已生成数据处理报告: {report_file}")
        print('\n'.join(report_lines))

def main():
    # 数据文件路径
    data_file = r"D:\Green methanol\green_methanol_for_port_transportation-main\green_methanol_for_port_transportation-main\air_port_data_process\data\2024年航班数据.xlsx"
    
    # 创建处理器
    processor = FlightDataProcessor(data_file)
    
    # 1. 加载数据
    if not processor.load_data():
        return
    
    # 2. 分析数据结构
    processor.analyze_data_structure()
    
    # 3. 识别关键列
    dep_col, arr_col = processor.identify_airport_columns()
    date_col = processor.identify_date_column()
    
    print(f"\n使用的列:")
    print(f"  出发机场列: {dep_col}")
    print(f"  到达机场列: {arr_col}")
    print(f"  日期列: {date_col}")
    
    # 4. 筛选机场数据
    filtered_df = processor.filter_airports(dep_col, arr_col)
    
    # 5. 保存筛选后的数据
    processor.save_filtered_data()
    
    # 6. 分析每日时间序列
    if date_col:
        daily_stats = processor.analyze_daily_time_series(date_col)
    else:
        print("未找到日期列，跳过时间序列分析")
    
    print(f"\n=== 处理完成 ===")
    print(f"所有结果保存在: results/2024_flight_analysis/")
    
    # 显示完整的保存路径
    current_dir = os.getcwd()
    results_path = os.path.join(current_dir, "results", "2024_flight_analysis")
    print(f"完整保存路径: {results_path}")

if __name__ == "__main__":
    main()
