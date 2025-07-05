#!/usr/bin/env python3
"""
简单分析综合测试结果
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
import os
import glob

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False

def load_latest_results():
    """加载最新的测试结果"""
    result_files = glob.glob('results/comprehensive_test_results_*.csv')
    if not result_files:
        print("❌ 未找到测试结果文件")
        return None
    
    latest_file = max(result_files, key=os.path.getctime)
    print(f"📊 加载测试结果: {latest_file}")
    
    return pd.read_csv(latest_file)

def analyze_results(df):
    """分析测试结果"""
    print(f"\n📊 综合测试结果分析")
    print("=" * 60)
    
    # 基本统计
    print(f"总测试用例: {len(df):,}")
    print(f"成功计算: {df['success'].sum():,}")
    print(f"成功率: {df['success'].mean()*100:.1f}%")
    
    # 成功的测试用例分析
    successful_df = df[df['success'] == True]
    if len(successful_df) > 0:
        print(f"\n✅ 成功测试统计:")
        print(f"总燃油消耗: {successful_df['fuel_kg'].sum():,.1f} kg")
        print(f"总CO2排放: {successful_df['co2_kg'].sum():,.1f} kg")
        print(f"平均燃油效率: {successful_df['fuel_kg'].sum()/successful_df['distance_km'].sum():.3f} kg/km")
        print(f"平均人均CO2: {successful_df['co2_per_passenger'].mean():.1f} kg/人")
    
    # 按类别分析
    print(f"\n📈 各类别测试结果:")
    print("-" * 40)
    for category in df['category'].unique():
        cat_data = df[df['category'] == category]
        success_rate = cat_data['success'].mean() * 100
        print(f"{category}: {len(cat_data)} 个测试, 成功率 {success_rate:.1f}%")
    
    # 机型测试结果 (前10)
    print(f"\n✈️  主要机型测试结果:")
    print("-" * 40)
    aircraft_stats = df.groupby('aircraft_type').agg({
        'success': ['count', 'sum', 'mean'],
        'fuel_kg': 'mean',
        'co2_kg': 'mean'
    }).round(2)
    
    aircraft_stats.columns = ['测试次数', '成功次数', '成功率', '平均燃油kg', '平均CO2kg']
    top_aircraft = aircraft_stats.sort_values('测试次数', ascending=False).head(10)
    
    for aircraft, stats in top_aircraft.iterrows():
        print(f"{aircraft}: {stats['测试次数']} 次测试, 成功率 {stats['成功率']*100:.1f}%")
        if stats['平均燃油kg'] > 0:
            print(f"  平均燃油: {stats['平均燃油kg']:.1f} kg, 平均CO2: {stats['平均CO2kg']:.1f} kg")
    
    # 计算方法统计
    print(f"\n🔧 计算方法统计:")
    print("-" * 40)
    method_stats = df['method'].value_counts()
    for method, count in method_stats.items():
        percentage = count / len(df) * 100
        print(f"{method}: {count} 次 ({percentage:.1f}%)")
    
    # 距离范围分析
    print(f"\n📏 距离范围分析:")
    print("-" * 40)
    distance_ranges = [
        (0, 500, '短程'),
        (500, 1000, '中短程'),
        (1000, 2000, '中程'),
        (2000, 5000, '中长程'),
        (5000, 10000, '长程'),
        (10000, 50000, '超长程')
    ]
    
    for min_dist, max_dist, label in distance_ranges:
        range_data = df[(df['distance_km'] >= min_dist) & (df['distance_km'] < max_dist)]
        if len(range_data) > 0:
            success_rate = range_data['success'].mean() * 100
            print(f"{label} ({min_dist}-{max_dist}km): {len(range_data)} 个测试, 成功率 {success_rate:.1f}%")
    
    return successful_df

def create_simple_charts(df, successful_df):
    """创建简单的图表"""
    print(f"\n📈 生成分析图表...")
    
    # 创建图表目录
    os.makedirs('results/charts', exist_ok=True)
    
    # 创建2x2的图表
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    
    # 1. 成功率饼图
    success_counts = df['success'].value_counts()
    if len(success_counts) == 1:
        # 所有测试都成功的情况
        axes[0, 0].pie([100], labels=['成功'], autopct='%1.1f%%', 
                       colors=['lightgreen'], startangle=90)
        axes[0, 0].set_title('测试成功率分布 (100%成功)')
    else:
        # 有成功和失败的情况
        labels = ['成功' if idx else '失败' for idx in success_counts.index]
        axes[0, 0].pie(success_counts.values, labels=labels, autopct='%1.1f%%', 
                       colors=['lightgreen', 'lightcoral'], startangle=90)
        axes[0, 0].set_title('测试成功率分布')
    
    # 2. 各类别成功率柱状图
    category_success = df.groupby('category')['success'].mean() * 100
    axes[0, 1].bar(range(len(category_success)), category_success.values, 
                   color='skyblue', alpha=0.8)
    axes[0, 1].set_xticks(range(len(category_success)))
    axes[0, 1].set_xticklabels(category_success.index, rotation=45)
    axes[0, 1].set_ylabel('成功率 (%)')
    axes[0, 1].set_title('各类别测试成功率')
    axes[0, 1].set_ylim(0, 105)  # 设置y轴范围
    axes[0, 1].grid(axis='y', alpha=0.3)
    
    # 3. 燃油消耗分布直方图
    if len(successful_df) > 0:
        axes[1, 0].hist(successful_df['fuel_kg'], bins=20, alpha=0.7, 
                       color='orange', edgecolor='black')
        axes[1, 0].set_xlabel('燃油消耗 (kg)')
        axes[1, 0].set_ylabel('航班数量')
        axes[1, 0].set_title('燃油消耗分布')
        axes[1, 0].grid(axis='y', alpha=0.3)
    
    # 4. 计算方法统计
    method_counts = df['method'].value_counts()
    axes[1, 1].bar(range(len(method_counts)), method_counts.values, 
                   color='lightcoral', alpha=0.8)
    axes[1, 1].set_xticks(range(len(method_counts)))
    axes[1, 1].set_xticklabels(method_counts.index, rotation=45)
    axes[1, 1].set_ylabel('使用次数')
    axes[1, 1].set_title('计算方法使用统计')
    axes[1, 1].grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('results/charts/simple_analysis.png', dpi=300, bbox_inches='tight')
    plt.show()
    
    print("✅ 图表已保存到 results/charts/simple_analysis.png")

def main():
    """主函数"""
    print("🚀 开始简单分析综合测试结果...")
    
    # 加载数据
    df = load_latest_results()
    if df is None:
        return
    
    print(f"📊 数据加载完成，共{len(df)}条记录")
    
    # 分析结果
    successful_df = analyze_results(df)
    
    # 创建简单图表
    create_simple_charts(df, successful_df)
    
    print(f"\n✅ 分析完成!")

if __name__ == "__main__":
    main() 