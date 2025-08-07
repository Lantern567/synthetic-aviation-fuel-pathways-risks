#!/usr/bin/env python
"""
改进的机场燃油量可视化模块
解决数据显示和缩放问题
"""

import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import logging

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))
from airport_fuel_charts import AirportFuelCharts

class ImprovedAirportCharts:
    """改进的机场燃油量图表类"""
    
    def __init__(self):
        self.base_visualizer = AirportFuelCharts()
        self.charts_dir = self.base_visualizer.charts_dir
        
    def create_log_scale_bar_chart(self, fuel_data, output_filename=None):
        """创建对数刻度的柱状图"""
        if output_filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_filename = f'log_scale_fuel_bar_{timestamp}.png'
        
        plt.figure(figsize=(16, 10))
        
        # 前30名机场
        top_30 = fuel_data.head(30)
        
        # 创建柱状图
        bars = plt.bar(range(len(top_30)), top_30['总燃油量'], 
                      color=plt.cm.viridis(np.linspace(0, 1, len(top_30))))
        
        # 设置对数刻度
        plt.yscale('log')
        
        plt.xlabel('机场', fontsize=14)
        plt.ylabel('总燃油量 (kg) - 对数刻度', fontsize=14)
        plt.title('2024年机场燃油量排名（对数刻度）', fontsize=16, fontweight='bold')
        
        # 设置x轴标签
        plt.xticks(range(len(top_30)), top_30['机场名称'], rotation=45, ha='right')
        
        # 在柱子上添加数值标签
        for i, (bar, value) in enumerate(zip(bars, top_30['总燃油量'])):
            if value >= 1e6:
                label = f'{value/1e6:.1f}M'
            elif value >= 1e3:
                label = f'{value/1e3:.0f}K'
            else:
                label = f'{value:.0f}'
            plt.text(bar.get_x() + bar.get_width()/2, bar.get_height()*1.1,
                    label, ha='center', va='bottom', fontsize=9)
        
        plt.grid(True, alpha=0.3, which="both")
        plt.tight_layout()
        
        output_path = os.path.join(self.charts_dir, output_filename)
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return output_path
    
    def create_grouped_charts(self, fuel_data, output_filename=None):
        """创建分组图表"""
        if output_filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_filename = f'grouped_fuel_charts_{timestamp}.png'
        
        fig, axes = plt.subplots(2, 2, figsize=(20, 16))
        fig.suptitle('2024年机场燃油量分组分析', fontsize=20, fontweight='bold')
        
        # 分组数据
        large_airports = fuel_data[fuel_data['总燃油量'] >= 10e6]  # >=1000万kg
        medium_airports = fuel_data[(fuel_data['总燃油量'] >= 1e6) & (fuel_data['总燃油量'] < 10e6)]  # 100万-1000万kg
        small_airports = fuel_data[fuel_data['总燃油量'] < 1e6]  # <100万kg
        
        # 1. 大型机场 (>=1000万kg)
        ax1 = axes[0, 0]
        bars1 = ax1.bar(range(len(large_airports)), large_airports['总燃油量']/1e6,
                       color='red', alpha=0.7)
        ax1.set_title(f'大型机场 (>=1000万kg) - {len(large_airports)}个', fontweight='bold')
        ax1.set_xlabel('机场')
        ax1.set_ylabel('燃油量 (百万kg)')
        ax1.set_xticks(range(len(large_airports)))
        ax1.set_xticklabels(large_airports['机场名称'], rotation=45, ha='right')
        
        # 添加数值标签
        for bar, value in zip(bars1, large_airports['总燃油量']):
            ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                    f'{value/1e6:.1f}M', ha='center', va='bottom', fontsize=10)
        
        # 2. 中型机场 (100万-1000万kg)
        ax2 = axes[0, 1]
        bars2 = ax2.bar(range(len(medium_airports.head(20))), medium_airports.head(20)['总燃油量']/1e6,
                       color='orange', alpha=0.7)
        ax2.set_title(f'中型机场 (100万-1000万kg) - {len(medium_airports)}个 (显示前20)', fontweight='bold')
        ax2.set_xlabel('机场')
        ax2.set_ylabel('燃油量 (百万kg)')
        ax2.set_xticks(range(len(medium_airports.head(20))))
        ax2.set_xticklabels(medium_airports.head(20)['机场名称'], rotation=45, ha='right')
        
        # 3. 小型机场 (<100万kg)
        ax3 = axes[1, 0]
        bars3 = ax3.bar(range(len(small_airports.head(20))), small_airports.head(20)['总燃油量']/1e3,
                       color='green', alpha=0.7)
        ax3.set_title(f'小型机场 (<100万kg) - {len(small_airports)}个 (显示前20)', fontweight='bold')
        ax3.set_xlabel('机场')
        ax3.set_ylabel('燃油量 (千kg)')
        ax3.set_xticks(range(len(small_airports.head(20))))
        ax3.set_xticklabels(small_airports.head(20)['机场名称'], rotation=45, ha='right')
        
        # 添加数值标签
        for bar, value in zip(bars3, small_airports.head(20)['总燃油量']):
            ax3.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 10,
                    f'{value/1e3:.0f}K', ha='center', va='bottom', fontsize=9)
        
        # 4. 分组统计饼图
        ax4 = axes[1, 1]
        group_data = [len(large_airports), len(medium_airports), len(small_airports)]
        group_labels = [f'大型机场\n{len(large_airports)}个', f'中型机场\n{len(medium_airports)}个', f'小型机场\n{len(small_airports)}个']
        colors = ['red', 'orange', 'green']
        
        wedges, texts, autotexts = ax4.pie(group_data, labels=group_labels, colors=colors, 
                                          autopct='%1.1f%%', startangle=90)
        ax4.set_title('机场规模分布', fontweight='bold')
        
        plt.tight_layout()
        
        output_path = os.path.join(self.charts_dir, output_filename)
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return output_path
    
    def create_detailed_small_airports_chart(self, fuel_data, output_filename=None):
        """专门为小型机场创建详细图表"""
        if output_filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_filename = f'small_airports_detail_{timestamp}.png'
        
        # 获取燃油量<100万kg的机场
        small_airports = fuel_data[fuel_data['总燃油量'] < 1e6].copy()
        
        fig, axes = plt.subplots(2, 1, figsize=(16, 12))
        fig.suptitle(f'小型机场详细分析 (共{len(small_airports)}个)', fontsize=16, fontweight='bold')
        
        # 1. 水平柱状图 - 显示所有小型机场
        ax1 = axes[0]
        y_pos = np.arange(len(small_airports))
        bars = ax1.barh(y_pos, small_airports['总燃油量']/1e3, color='lightcoral', alpha=0.8)
        
        ax1.set_yticks(y_pos)
        ax1.set_yticklabels(small_airports['机场名称'], fontsize=8)
        ax1.set_xlabel('燃油量 (千kg)')
        ax1.set_title('所有小型机场燃油量排名', fontweight='bold')
        ax1.invert_yaxis()  # 最大的在上面
        
        # 添加数值标签
        for bar, value in zip(bars, small_airports['总燃油量']):
            ax1.text(bar.get_width() + 10, bar.get_y() + bar.get_height()/2,
                    f'{value/1e3:.0f}K', ha='left', va='center', fontsize=7)
        
        # 2. 散点图 - 燃油量 vs 航班数量
        ax2 = axes[1]
        scatter = ax2.scatter(small_airports['航班数量'], small_airports['总燃油量']/1e3,
                            s=80, alpha=0.7, c=small_airports['平均燃油量'], 
                            cmap='viridis', edgecolors='black', linewidth=0.5)
        
        ax2.set_xlabel('航班数量')
        ax2.set_ylabel('总燃油量 (千kg)')
        ax2.set_title('小型机场：航班数量 vs 燃油量关系', fontweight='bold')
        
        # 添加颜色条
        cbar = plt.colorbar(scatter, ax=ax2)
        cbar.set_label('平均燃油量 (kg/班次)')
        
        # 标注最小和最大的机场
        min_fuel_airport = small_airports.loc[small_airports['总燃油量'].idxmin()]
        max_fuel_airport = small_airports.loc[small_airports['总燃油量'].idxmax()]
        
        ax2.annotate(f'最小: {min_fuel_airport["机场名称"]}\\n{min_fuel_airport["总燃油量"]/1e3:.1f}K kg',
                    (min_fuel_airport['航班数量'], min_fuel_airport['总燃油量']/1e3),
                    xytext=(10, 10), textcoords='offset points',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7),
                    arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'))
        
        ax2.annotate(f'最大: {max_fuel_airport["机场名称"]}\\n{max_fuel_airport["总燃油量"]/1e3:.1f}K kg',
                    (max_fuel_airport['航班数量'], max_fuel_airport['总燃油量']/1e3),
                    xytext=(10, -20), textcoords='offset points',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='lightblue', alpha=0.7),
                    arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'))
        
        plt.tight_layout()
        
        output_path = os.path.join(self.charts_dir, output_filename)
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return output_path
    
    def create_comparison_table(self, fuel_data, output_filename=None):
        """创建对比表格图表"""
        if output_filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_filename = f'fuel_comparison_table_{timestamp}.png'
        
        fig, ax = plt.subplots(figsize=(14, 10))
        ax.axis('tight')
        ax.axis('off')
        
        # 选择有代表性的机场：前10名 + 中间10名 + 后10名
        top_10 = fuel_data.head(10)
        middle_10 = fuel_data.iloc[65:75]  # 中间位置
        bottom_10 = fuel_data.tail(10)
        
        combined = pd.concat([top_10, middle_10, bottom_10])
        
        # 准备表格数据
        table_data = []
        for i, (_, row) in enumerate(combined.iterrows()):
            rank = fuel_data.index[fuel_data['机场名称'] == row['机场名称']].tolist()[0] + 1
            
            if row['总燃油量'] >= 1e6:
                fuel_str = f"{row['总燃油量']/1e6:.1f}百万kg"
            else:
                fuel_str = f"{row['总燃油量']/1e3:.1f}千kg"
            
            table_data.append([
                rank,
                row['机场名称'],
                fuel_str,
                f"{row['航班数量']:,}",
                f"{row['平均燃油量']:.0f}kg"
            ])
        
        # 创建表格
        table = ax.table(cellText=table_data,
                        colLabels=['排名', '机场名称', '总燃油量', '航班数量', '平均燃油量'],
                        cellLoc='center',
                        loc='center')
        
        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1.2, 1.5)
        
        # 设置颜色
        for i in range(len(table_data)):
            if i < 10:  # 前10名
                color = '#ffcccc'  # 浅红色
            elif i < 20:  # 中间10名
                color = '#ffffcc'  # 浅黄色
            else:  # 后10名
                color = '#ccffcc'  # 浅绿色
            
            for j in range(5):
                table[(i+1, j)].set_facecolor(color)
        
        # 设置标题
        plt.title('2024年机场燃油量对比表\\n（前10名、中间10名、后10名）', 
                 fontsize=16, fontweight='bold', pad=20)
        
        # 添加图例
        legend_elements = [
            plt.Rectangle((0,0),1,1, facecolor='#ffcccc', label='前10名'),
            plt.Rectangle((0,0),1,1, facecolor='#ffffcc', label='中间10名'),
            plt.Rectangle((0,0),1,1, facecolor='#ccffcc', label='后10名')
        ]
        ax.legend(handles=legend_elements, loc='upper right', bbox_to_anchor=(1, 0.95))
        
        output_path = os.path.join(self.charts_dir, output_filename)
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return output_path
    
    def run_improved_analysis(self):
        """运行改进的分析"""
        print("🚀 开始改进的机场燃油量可视化分析")
        
        # 加载数据
        fuel_df = self.base_visualizer.load_fuel_calculation_results()
        aggregated = self.base_visualizer.aggregate_fuel_by_airport_2024(fuel_df)
        
        results = {}
        
        # 1. 对数刻度柱状图
        print("📊 生成对数刻度柱状图...")
        results['log_bar'] = self.create_log_scale_bar_chart(aggregated)
        
        # 2. 分组图表
        print("📊 生成分组图表...")
        results['grouped'] = self.create_grouped_charts(aggregated)
        
        # 3. 小型机场详细图表
        print("📊 生成小型机场详细图表...")
        results['small_detail'] = self.create_detailed_small_airports_chart(aggregated)
        
        # 4. 对比表格
        print("📊 生成对比表格...")
        results['comparison_table'] = self.create_comparison_table(aggregated)
        
        print("\n✅ 改进分析完成！")
        print("生成的文件:")
        for chart_type, file_path in results.items():
            print(f"  📈 {chart_type}: {os.path.basename(file_path)}")
        
        return results

def main():
    """主函数"""
    visualizer = ImprovedAirportCharts()
    return visualizer.run_improved_analysis()

if __name__ == "__main__":
    main() 