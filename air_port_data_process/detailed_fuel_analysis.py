#!/usr/bin/env python
"""
详细的燃油量分析
"""

import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from airport_fuel_charts import AirportFuelCharts

def main():
    """主函数"""
    print("="*60)
    print("🔍 详细燃油量分析")
    print("="*60)
    
    # 初始化可视化器
    visualizer = AirportFuelCharts()
    
    # 加载和聚合数据
    fuel_df = visualizer.load_fuel_calculation_results()
    aggregated = visualizer.aggregate_fuel_by_airport_2024(fuel_df)
    
    print(f"📊 数据概览:")
    print(f"  - 机场总数: {len(aggregated)}")
    print(f"  - 最大燃油量: {aggregated['总燃油量'].max()/1e6:.2f} 百万kg")
    print(f"  - 最小燃油量: {aggregated['总燃油量'].min()/1e3:.2f} 千kg") 
    print(f"  - 平均燃油量: {aggregated['总燃油量'].mean()/1e6:.2f} 百万kg")
    print(f"  - 中位燃油量: {aggregated['总燃油量'].median()/1e6:.2f} 百万kg")
    
    # 检查燃油量分布
    print(f"\n📈 燃油量分布分析:")
    
    # 按燃油量大小分组
    bins = [0, 1e5, 5e5, 1e6, 5e6, 1e7, 5e7, 1e8, float('inf')]
    labels = ['<10万', '10-50万', '50-100万', '100-500万', '500-1000万', '1000-5000万', '5000万-1亿', '>1亿']
    
    aggregated['燃油量分组'] = pd.cut(aggregated['总燃油量'], bins=bins, labels=labels, include_lowest=True)
    distribution = aggregated['燃油量分组'].value_counts().sort_index()
    
    print("机场数量分布（按燃油量）:")
    for group, count in distribution.items():
        percentage = count / len(aggregated) * 100
        print(f"  {group}kg: {count:2d}个机场 ({percentage:5.1f}%)")
    
    # 显示最小燃油量的机场
    print(f"\n🔍 燃油量最小的10个机场:")
    bottom_10 = aggregated.tail(10)
    for i, (_, row) in enumerate(bottom_10.iterrows(), 1):
        print(f"  {i:2d}. {row['机场名称']:12s}: {row['总燃油量']/1e3:8.1f}千kg ({row['航班数量']:4d}班次)")
    
    # 显示燃油量最大的机场
    print(f"\n🔝 燃油量最大的10个机场:")
    top_10 = aggregated.head(10)
    for i, (_, row) in enumerate(top_10.iterrows(), 1):
        print(f"  {i:2d}. {row['机场名称']:12s}: {row['总燃油量']/1e6:8.1f}百万kg ({row['航班数量']:5d}班次)")
    
    # 分析平均燃油量
    print(f"\n⚡ 平均燃油量分析:")
    print(f"  - 最高平均燃油量: {aggregated['平均燃油量'].max():.2f}kg/班次")
    print(f"  - 最低平均燃油量: {aggregated['平均燃油量'].min():.2f}kg/班次")
    print(f"  - 全体平均燃油量: {aggregated['平均燃油量'].mean():.2f}kg/班次")
    
    # 平均燃油量最高和最低的机场
    highest_avg = aggregated.loc[aggregated['平均燃油量'].idxmax()]
    lowest_avg = aggregated.loc[aggregated['平均燃油量'].idxmin()]
    
    print(f"\n  最高平均燃油量机场: {highest_avg['机场名称']} ({highest_avg['平均燃油量']:.2f}kg/班次)")
    print(f"  最低平均燃油量机场: {lowest_avg['机场名称']} ({lowest_avg['平均燃油量']:.2f}kg/班次)")
    
    # 保存详细分析报告
    output_file = 'results/tables/detailed_fuel_analysis.txt'
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("详细燃油量分析报告\n")
        f.write("="*50 + "\n\n")
        
        f.write("所有机场燃油量数据：\n")
        f.write("-" * 80 + "\n")
        f.write(f"{'排名':>4} {'机场名称':12} {'总燃油量(千kg)':>15} {'航班数量':>8} {'平均燃油量(kg)':>15}\n")
        f.write("-" * 80 + "\n")
        
        for i, (_, row) in enumerate(aggregated.iterrows(), 1):
            f.write(f"{i:4d} {row['机场名称']:12s} {row['总燃油量']/1e3:13.1f} {row['航班数量']:8d} {row['平均燃油量']:13.2f}\n")
    
    print(f"\n💾 详细分析已保存到: {output_file}")
    
    # 创建分布可视化
    plt.figure(figsize=(12, 8))
    
    # 子图1: 燃油量分布直方图
    plt.subplot(2, 2, 1)
    plt.hist(aggregated['总燃油量']/1e6, bins=20, alpha=0.7, color='skyblue', edgecolor='black')
    plt.xlabel('总燃油量 (百万kg)')
    plt.ylabel('机场数量')
    plt.title('机场燃油量分布直方图')
    plt.grid(True, alpha=0.3)
    
    # 子图2: 箱型图
    plt.subplot(2, 2, 2)
    plt.boxplot(aggregated['总燃油量']/1e6, vert=True)
    plt.ylabel('总燃油量 (百万kg)')
    plt.title('燃油量分布箱型图')
    plt.grid(True, alpha=0.3)
    
    # 子图3: 航班数量vs燃油量散点图
    plt.subplot(2, 2, 3)
    plt.scatter(aggregated['航班数量'], aggregated['总燃油量']/1e6, alpha=0.6, color='coral')
    plt.xlabel('航班数量')
    plt.ylabel('总燃油量 (百万kg)')
    plt.title('航班数量 vs 燃油量')
    plt.grid(True, alpha=0.3)
    
    # 子图4: 燃油量分组饼图
    plt.subplot(2, 2, 4)
    plt.pie(distribution.values, labels=distribution.index, autopct='%1.1f%%', startangle=90)
    plt.title('机场燃油量分组分布')
    
    plt.tight_layout()
    plt.savefig('results/charts/detailed_fuel_distribution.png', dpi=300, bbox_inches='tight')
    print(f"📊 分布图表已保存到: results/charts/detailed_fuel_distribution.png")
    
    plt.close()

if __name__ == "__main__":
    main() 