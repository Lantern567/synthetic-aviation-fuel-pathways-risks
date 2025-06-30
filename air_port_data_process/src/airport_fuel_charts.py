"""
机场耗油量图表可视化模块
提供多种图表方式可视化各机场2024年的燃油消耗情况
"""

import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import logging
from typing import Optional, Tuple, List, Dict

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AirportFuelCharts:
    """机场燃油量图表可视化类"""
    
    def __init__(self, data_dir=None, results_dir=None):
        """
        初始化可视化器
        
        Args:
            data_dir: 数据目录路径
            results_dir: 结果输出目录路径
        """
        if data_dir is None:
            self.data_dir = os.path.join(os.path.dirname(__file__), '..', 'results', 'parallel_fuel_calculation')
        else:
            self.data_dir = data_dir
            
        if results_dir is None:
            self.results_dir = os.path.join(os.path.dirname(__file__), '..', 'results')
        else:
            self.results_dir = results_dir
        
        # 创建输出目录
        self.charts_dir = os.path.join(self.results_dir, 'charts')
        os.makedirs(self.charts_dir, exist_ok=True)
        
        logger.info(f"数据目录: {self.data_dir}")
        logger.info(f"图表输出目录: {self.charts_dir}")
    
    def load_fuel_calculation_results(self):
        """
        加载燃油计算结果数据
        
        Returns:
            DataFrame: 燃油计算结果数据
        """
        try:
            # 查找并行计算结果文件
            files = os.listdir(self.data_dir)
            fuel_files = [f for f in files if f.startswith('并行计算结果_') and f.endswith('.xlsx')]
            
            # 排除统计文件
            fuel_files = [f for f in fuel_files if not f.startswith('处理统计_')]
            
            if not fuel_files:
                raise FileNotFoundError("未找到燃油计算结果文件")
            
            # 选择最新的文件
            latest_file = max(fuel_files)
            file_path = os.path.join(self.data_dir, latest_file)
            
            logger.info(f"加载燃油计算结果: {latest_file}")
            
            # 加载数据
            df = pd.read_excel(file_path)
            logger.info(f"成功加载 {len(df)} 条燃油计算记录")
            
            return df
        
        except Exception as e:
            logger.error(f"加载燃油计算结果时出错: {str(e)}")
            raise
    
    def aggregate_fuel_by_airport_2024(self, fuel_df):
        """
        按起飞机场聚合2024年的燃油量数据
        
        Args:
            fuel_df: 燃油计算结果DataFrame
            
        Returns:
            DataFrame: 按起飞机场聚合的燃油量数据
        """
        try:
            # 确保有日期列
            if '日期' in fuel_df.columns:
                fuel_df['日期'] = pd.to_datetime(fuel_df['日期'], errors='coerce')
                fuel_2024 = fuel_df[fuel_df['日期'].dt.year == 2024]
            elif '航班日期' in fuel_df.columns:
                fuel_df['航班日期'] = pd.to_datetime(fuel_df['航班日期'], errors='coerce')
                fuel_2024 = fuel_df[fuel_df['航班日期'].dt.year == 2024]
            else:
                logger.warning("未找到日期列，使用全部数据")
                fuel_2024 = fuel_df
            
            # 查找燃油量列
            fuel_columns = [col for col in fuel_2024.columns if '燃油' in col or '油量' in col or 'fuel' in col.lower()]
            
            if not fuel_columns:
                raise ValueError("未找到燃油量相关列")
            
            fuel_col = fuel_columns[0]
            logger.info(f"使用燃油量列: {fuel_col}")
            
            # 查找起飞机场列
            airport_columns = [col for col in fuel_2024.columns if '起飞机场' in col]
            
            if not airport_columns:
                raise ValueError("未找到起飞机场列")
            
            airport_col = airport_columns[0]
            logger.info(f"使用起飞机场列: {airport_col}")
            
            # 按起飞机场聚合燃油量
            aggregated = fuel_2024.groupby(airport_col)[fuel_col].agg(['sum', 'count', 'mean']).reset_index()
            aggregated.columns = ['机场名称', '总燃油量', '航班数量', '平均燃油量']
            
            # 按总燃油量排序
            aggregated = aggregated.sort_values('总燃油量', ascending=False).reset_index(drop=True)
            
            logger.info(f"聚合后得到 {len(aggregated)} 个机场的燃油量数据")
            logger.info(f"总燃油量范围: {aggregated['总燃油量'].min():.2f} - {aggregated['总燃油量'].max():.2f}")
            
            return aggregated
        
        except Exception as e:
            logger.error(f"聚合燃油量数据时出错: {str(e)}")
            raise
    
    def create_top_airports_bar_chart(self, fuel_data, top_n=20, output_filename=None):
        """
        创建燃油量前N名机场的柱状图
        
        Args:
            fuel_data: 燃油量数据
            top_n: 显示前N名
            output_filename: 输出文件名
        """
        try:
            if output_filename is None:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                output_filename = f'top_{top_n}_airports_fuel_bar_{timestamp}.png'
            
            # 获取前N名数据
            top_data = fuel_data.head(top_n)
            
            # 创建图形
            plt.figure(figsize=(16, 10))
            
            # 创建柱状图
            bars = plt.bar(range(len(top_data)), top_data['总燃油量'], 
                          color=plt.cm.viridis(np.linspace(0, 1, len(top_data))))
            
            # 设置标签
            plt.xlabel('机场', fontsize=14)
            plt.ylabel('总燃油量 (kg)', fontsize=14)
            plt.title(f'2024年燃油量前{top_n}名机场', fontsize=16, fontweight='bold')
            
            # 设置x轴标签
            plt.xticks(range(len(top_data)), top_data['机场名称'], rotation=45, ha='right')
            
            # 在柱子上添加数值标签
            for i, (bar, value) in enumerate(zip(bars, top_data['总燃油量'])):
                plt.text(bar.get_x() + bar.get_width()/2, bar.get_height() + value*0.01,
                        f'{value/1e6:.1f}M', ha='center', va='bottom', fontsize=10)
            
            # 添加统计信息文本框
            total_fuel = top_data['总燃油量'].sum()
            total_flights = top_data['航班数量'].sum()
            stats_text = f'前{top_n}名机场统计:\n总燃油量: {total_fuel/1e6:.1f}M kg\n总航班数: {total_flights:,}'
            plt.text(0.02, 0.98, stats_text, transform=plt.gca().transAxes, 
                    bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8),
                    verticalalignment='top', fontsize=10)
            
            plt.tight_layout()
            
            # 保存图片
            output_path = os.path.join(self.charts_dir, output_filename)
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            logger.info(f"柱状图已保存到: {output_path}")
            
            plt.close()
            return output_path
        
        except Exception as e:
            logger.error(f"创建柱状图时出错: {str(e)}")
            raise
    
    def create_fuel_vs_flights_scatter(self, fuel_data, output_filename=None):
        """
        创建燃油量与航班数量的散点图
        
        Args:
            fuel_data: 燃油量数据
            output_filename: 输出文件名
        """
        try:
            if output_filename is None:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                output_filename = f'fuel_vs_flights_scatter_{timestamp}.png'
            
            plt.figure(figsize=(14, 10))
            
            # 创建散点图
            scatter = plt.scatter(fuel_data['航班数量'], fuel_data['总燃油量'], 
                                alpha=0.7, s=60, c=fuel_data['平均燃油量'], 
                                cmap='viridis', edgecolors='black', linewidth=0.5)
            
            # 设置标签
            plt.xlabel('航班数量', fontsize=14)
            plt.ylabel('总燃油量 (kg)', fontsize=14)
            plt.title('机场航班数量与总燃油量关系图', fontsize=16, fontweight='bold')
            
            # 添加颜色条
            cbar = plt.colorbar(scatter)
            cbar.set_label('平均燃油量 (kg)', fontsize=12)
            
            # 标注燃油量最高的几个机场
            top_5 = fuel_data.head(5)
            for _, row in top_5.iterrows():
                plt.annotate(row['机场名称'], 
                           (row['航班数量'], row['总燃油量']),
                           xytext=(10, 10), textcoords='offset points',
                           bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7),
                           arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'))
            
            # 添加趋势线
            z = np.polyfit(fuel_data['航班数量'], fuel_data['总燃油量'], 1)
            p = np.poly1d(z)
            plt.plot(fuel_data['航班数量'], p(fuel_data['航班数量']), 
                    "r--", alpha=0.8, linewidth=2, label='趋势线')
            
            # 计算相关系数
            correlation = fuel_data['航班数量'].corr(fuel_data['总燃油量'])
            plt.text(0.02, 0.98, f'相关系数: {correlation:.3f}', 
                    transform=plt.gca().transAxes,
                    bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8),
                    verticalalignment='top', fontsize=12)
            
            plt.legend()
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            
            # 保存图片
            output_path = os.path.join(self.charts_dir, output_filename)
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            logger.info(f"散点图已保存到: {output_path}")
            
            plt.close()
            return output_path
        
        except Exception as e:
            logger.error(f"创建散点图时出错: {str(e)}")
            raise
    
    def create_fuel_distribution_pie_chart(self, fuel_data: pd.DataFrame, 
                                         top_n: int = 10) -> str:
        """
        创建燃油量分布饼图
        
        Args:
            fuel_data: 聚合的燃油量数据
            top_n: 显示前N个机场
            
        Returns:
            str: 图表文件路径
        """
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = os.path.join(self.charts_dir, f'fuel_distribution_pie_{top_n}_airports_{timestamp}.png')
            
            # 准备数据 - 前N个机场 + 其他
            top_airports = fuel_data.head(top_n).copy()
            
            if len(fuel_data) > top_n:
                others_fuel = fuel_data.iloc[top_n:]['总燃油量'].sum()
                others_row = pd.DataFrame({
                    '机场名称': ['其他机场'],
                    '总燃油量': [others_fuel]
                })
                plot_data = pd.concat([top_airports[['机场名称', '总燃油量']], others_row], ignore_index=True)
            else:
                plot_data = top_airports[['机场名称', '总燃油量']].copy()
            
            pie_data = plot_data['总燃油量']
            pie_labels = plot_data['机场名称']
            
            # 创建图表
            plt.figure(figsize=(12, 8))
            
            # 使用不同的颜色
            colors = plt.cm.Set3(np.linspace(0, 1, len(pie_data)))
            
            # 创建饼图
            plt.pie(pie_data, labels=pie_labels, autopct='%1.1f%%',
                   colors=colors, startangle=90, textprops={'fontsize': 10})
            
            plt.title(f'2024年前{top_n}个机场燃油消耗占比', fontsize=16, fontweight='bold', pad=20)
            
            # 添加总燃油量信息
            total_fuel = fuel_data['总燃油量'].sum()
            plt.figtext(0.02, 0.02, f'总燃油量: {total_fuel:,.0f} kg', fontsize=10, style='italic')
            
            plt.tight_layout()
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"饼图已保存到: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"创建饼图时出错: {e}")
            return None
    
    def create_fuel_boxplot(self, fuel_data: pd.DataFrame) -> str:
        """
        创建燃油量分布箱型图
        
        Args:
            fuel_data: 聚合的燃油量数据
            
        Returns:
            str: 图表文件路径
        """
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = os.path.join(self.charts_dir, f'fuel_distribution_boxplot_{timestamp}.png')
            
            # 创建2x2子图
            fig, axes = plt.subplots(2, 2, figsize=(15, 12))
            fig.suptitle('2024年机场燃油消耗分布统计', fontsize=16, fontweight='bold')
            
            # 燃油量箱型图
            axes[0, 0].boxplot(fuel_data['总燃油量'], vert=True)
            axes[0, 0].set_title('总燃油量分布')
            axes[0, 0].set_ylabel('燃油量 (kg)')
            axes[0, 0].ticklabel_format(axis='y', style='scientific', scilimits=(0,0))
            
            # 航班数量箱型图
            axes[0, 1].boxplot(fuel_data['航班数量'], vert=True)
            axes[0, 1].set_title('航班数量分布')
            axes[0, 1].set_ylabel('航班数量')
            
            # 平均燃油量箱型图
            axes[1, 0].boxplot(fuel_data['平均燃油量'], vert=True)
            axes[1, 0].set_title('平均燃油量分布')
            axes[1, 0].set_ylabel('平均燃油量 (kg)')
            
            # 统计信息
            axes[1, 1].axis('off')
            stats_text = f'''
统计摘要:
机场总数: {len(fuel_data)}
总燃油量: {fuel_data['总燃油量'].sum():,.0f} kg
平均每机场燃油量: {fuel_data['总燃油量'].mean():,.0f} kg
燃油量标准差: {fuel_data['总燃油量'].std():,.0f} kg

最大燃油量机场: {fuel_data.iloc[0]['机场名称']}
({fuel_data.iloc[0]['总燃油量']:,.0f} kg)

最小燃油量机场: {fuel_data.iloc[-1]['机场名称']}
({fuel_data.iloc[-1]['总燃油量']:,.0f} kg)
            '''
            axes[1, 1].text(0.1, 0.9, stats_text, transform=axes[1, 1].transAxes,
                            fontsize=10, verticalalignment='top',
                            bbox=dict(boxstyle='round', facecolor='lightgray', alpha=0.5))
            
            plt.tight_layout()
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"箱型图已保存到: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"创建箱型图时出错: {e}")
            return None
    
    def create_comprehensive_dashboard(self, fuel_data, output_filename=None):
        """
        创建综合仪表板图表
        
        Args:
            fuel_data: 燃油量数据
            output_filename: 输出文件名
        """
        try:
            if output_filename is None:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                output_filename = f'comprehensive_dashboard_{timestamp}.png'
            
            # 创建子图
            fig = plt.figure(figsize=(20, 16))
            gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)
            
            # 1. 前15名柱状图
            ax1 = fig.add_subplot(gs[0, :2])
            top_15 = fuel_data.head(15)
            bars = ax1.bar(range(len(top_15)), top_15['总燃油量'], 
                          color=plt.cm.viridis(np.linspace(0, 1, len(top_15))))
            ax1.set_title('燃油量前15名机场', fontsize=14, fontweight='bold')
            ax1.set_ylabel('总燃油量 (kg)')
            ax1.set_xticks(range(len(top_15)))
            ax1.set_xticklabels(top_15['机场名称'], rotation=45, ha='right')
            
            # 2. 饼图 (前8名)
            ax2 = fig.add_subplot(gs[0, 2])
            top_8 = fuel_data.head(8)
            others = fuel_data.iloc[8:]['总燃油量'].sum()
            pie_data = top_8['总燃油量'].tolist() + [others]
            pie_labels = top_8['机场名称'].tolist() + [f'其他({len(fuel_data)-8}个)']
            ax2.pie(pie_data, labels=pie_labels, autopct='%1.1f%%', startangle=90, 
                   textprops={'fontsize': 8})
            ax2.set_title('燃油量占比分布', fontsize=14, fontweight='bold')
            
            # 3. 散点图
            ax3 = fig.add_subplot(gs[1, :2])
            scatter = ax3.scatter(fuel_data['航班数量'], fuel_data['总燃油量'], 
                                alpha=0.6, s=50, c=fuel_data['平均燃油量'], 
                                cmap='plasma', edgecolors='black', linewidth=0.3)
            ax3.set_xlabel('航班数量')
            ax3.set_ylabel('总燃油量 (kg)')
            ax3.set_title('航班数量与燃油量关系', fontsize=14, fontweight='bold')
            ax3.grid(True, alpha=0.3)
            
            # 添加颜色条
            cbar = plt.colorbar(scatter, ax=ax3)
            cbar.set_label('平均燃油量 (kg)', fontsize=10)
            
            # 4. 直方图
            ax4 = fig.add_subplot(gs[1, 2])
            ax4.hist(fuel_data['总燃油量'], bins=20, alpha=0.7, color='lightcoral', edgecolor='black')
            ax4.set_xlabel('总燃油量 (kg)')
            ax4.set_ylabel('机场数量')
            ax4.set_title('燃油量分布直方图', fontsize=14, fontweight='bold')
            
            # 5. 前20名水平柱状图
            ax5 = fig.add_subplot(gs[2, :])
            top_20 = fuel_data.head(20)
            y_pos = np.arange(len(top_20))
            bars = ax5.barh(y_pos, top_20['总燃油量'], 
                           color=plt.cm.coolwarm(np.linspace(0, 1, len(top_20))))
            ax5.set_yticks(y_pos)
            ax5.set_yticklabels(top_20['机场名称'])
            ax5.set_xlabel('总燃油量 (kg)')
            ax5.set_title('燃油量前20名机场 (水平柱状图)', fontsize=14, fontweight='bold')
            ax5.invert_yaxis()  # 倒序显示
            
            # 在柱子末端添加数值
            for i, (bar, value) in enumerate(zip(bars, top_20['总燃油量'])):
                ax5.text(bar.get_width() + value*0.01, bar.get_y() + bar.get_height()/2,
                        f'{value/1e6:.1f}M', ha='left', va='center', fontsize=8)
            
            # 添加总体统计信息
            total_fuel = fuel_data['总燃油量'].sum()
            total_flights = fuel_data['航班数量'].sum()
            avg_fuel = fuel_data['总燃油量'].mean()
            
            stats_text = f"""2024年机场燃油消耗总体统计
机场总数: {len(fuel_data)}
总燃油量: {total_fuel/1e9:.2f}B kg
总航班数: {total_flights:,}
平均燃油量: {avg_fuel/1e6:.2f}M kg"""
            
            plt.figtext(0.02, 0.98, stats_text, fontsize=12, fontweight='bold',
                       bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8),
                       verticalalignment='top')
            
            # 保存图片
            output_path = os.path.join(self.charts_dir, output_filename)
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            logger.info(f"综合仪表板已保存到: {output_path}")
            
            plt.close()
            return output_path
        
        except Exception as e:
            logger.error(f"创建综合仪表板时出错: {str(e)}")
            raise
    
    def generate_fuel_analysis_report(self, fuel_data, output_filename=None):
        """
        生成燃油量分析报告
        
        Args:
            fuel_data: 燃油量数据
            output_filename: 输出文件名
        """
        try:
            if output_filename is None:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                output_filename = f'airport_fuel_analysis_report_{timestamp}.txt'
            
            output_path = os.path.join(self.results_dir, 'tables', output_filename)
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write("2024年各机场航班燃油消耗分析报告\n")
                f.write("=" * 60 + "\n\n")
                
                f.write(f"报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                # 总体统计
                f.write("一、总体统计\n")
                f.write("-" * 30 + "\n")
                f.write(f"机场总数: {len(fuel_data)}\n")
                f.write(f"总燃油量: {fuel_data['总燃油量'].sum()/1e9:.2f} 亿 kg\n")
                f.write(f"总航班数: {fuel_data['航班数量'].sum():,}\n")
                f.write(f"平均每机场燃油量: {fuel_data['总燃油量'].mean()/1e6:.2f} 百万 kg\n")
                f.write(f"平均每机场航班数: {fuel_data['航班数量'].mean():.0f}\n")
                f.write(f"平均每航班燃油量: {fuel_data['平均燃油量'].mean():.2f} kg\n\n")
                
                # 分布统计
                f.write("二、分布统计\n")
                f.write("-" * 30 + "\n")
                f.write("燃油量分位数分析:\n")
                percentiles = [25, 50, 75, 90, 95, 99]
                for p in percentiles:
                    value = np.percentile(fuel_data['总燃油量'], p)
                    f.write(f"  {p}%分位数: {value/1e6:.2f} 百万 kg\n")
                
                f.write("\n航班数量分位数分析:\n")
                for p in percentiles:
                    value = np.percentile(fuel_data['航班数量'], p)
                    f.write(f"  {p}%分位数: {value:.0f}\n")
                f.write("\n")
                
                # Top 10分析
                f.write("三、燃油量前10名机场\n")
                f.write("-" * 30 + "\n")
                top_10 = fuel_data.head(10)
                for i, (_, row) in enumerate(top_10.iterrows(), 1):
                    f.write(f"{i:2d}. {row['机场名称']}\n")
                    f.write(f"     总燃油量: {row['总燃油量']/1e6:.2f} 百万 kg\n")
                    f.write(f"     航班数量: {row['航班数量']:,}\n")
                    f.write(f"     平均燃油: {row['平均燃油量']:.2f} kg/航班\n\n")
                
                # 航班数量Top 10
                f.write("四、航班数量前10名机场\n")
                f.write("-" * 30 + "\n")
                top_flights = fuel_data.nlargest(10, '航班数量')
                for i, (_, row) in enumerate(top_flights.iterrows(), 1):
                    f.write(f"{i:2d}. {row['机场名称']}\n")
                    f.write(f"     航班数量: {row['航班数量']:,}\n")
                    f.write(f"     总燃油量: {row['总燃油量']/1e6:.2f} 百万 kg\n")
                    f.write(f"     平均燃油: {row['平均燃油量']:.2f} kg/航班\n\n")
                
                # 效率分析
                f.write("五、燃油效率分析\n")
                f.write("-" * 30 + "\n")
                high_efficiency = fuel_data[fuel_data['平均燃油量'] < fuel_data['平均燃油量'].quantile(0.25)]
                low_efficiency = fuel_data[fuel_data['平均燃油量'] > fuel_data['平均燃油量'].quantile(0.75)]
                
                f.write("高效率机场 (平均燃油量前25%):\n")
                for _, row in high_efficiency.head(5).iterrows():
                    f.write(f"  {row['机场名称']}: {row['平均燃油量']:.2f} kg/航班\n")
                
                f.write("\n低效率机场 (平均燃油量后25%):\n")
                for _, row in low_efficiency.tail(5).iterrows():
                    f.write(f"  {row['机场名称']}: {row['平均燃油量']:.2f} kg/航班\n")
                
                # 集中度分析
                f.write("\n六、市场集中度分析\n")
                f.write("-" * 30 + "\n")
                total_fuel = fuel_data['总燃油量'].sum()
                
                f.write("燃油量集中度:\n")
                for n in [5, 10, 20]:
                    concentration = fuel_data.head(n)['总燃油量'].sum() / total_fuel * 100
                    f.write(f"  前{n}名机场占比: {concentration:.1f}%\n")
            
            logger.info(f"分析报告已保存到: {output_path}")
            return output_path
        
        except Exception as e:
            logger.error(f"生成分析报告时出错: {str(e)}")
            raise
    
    def run_complete_analysis(self):
        """
        运行完整的图表分析
        
        Returns:
            Dict: 包含所有生成文件路径的字典
        """
        try:
            logger.info("开始运行完整的机场燃油量图表分析")
            
            # 1. 加载数据
            fuel_df = self.load_fuel_calculation_results()
            
            # 2. 聚合数据
            aggregated_data = self.aggregate_fuel_by_airport_2024(fuel_df)
            
            # 3. 生成各种图表
            results = {}
            
            # 柱状图 - 前20名
            results['bar_chart'] = self.create_top_airports_bar_chart(aggregated_data, top_n=20)
            
            # 散点图 - 燃油量与航班数量关系
            results['scatter_plot'] = self.create_fuel_vs_flights_scatter(aggregated_data)
            
            # 饼图 - 燃油量分布
            results['pie_chart'] = self.create_fuel_distribution_pie_chart(aggregated_data, top_n=10)
            
            # 箱型图 - 分布统计
            results['boxplot'] = self.create_fuel_boxplot(aggregated_data)
            
            # 综合仪表板
            results['dashboard'] = self.create_comprehensive_dashboard(aggregated_data)
            
            # 分析报告
            results['report'] = self.generate_fuel_analysis_report(aggregated_data)
            
            logger.info("所有图表生成完成！")
            logger.info(f"生成的文件:")
            for chart_type, file_path in results.items():
                logger.info(f"  {chart_type}: {file_path}")
            
            return results
        
        except Exception as e:
            logger.error(f"运行完整分析时出错: {str(e)}")
            raise

def main():
    """主函数"""
    try:
        # 创建可视化器
        visualizer = AirportFuelCharts()
        
        # 运行完整分析
        results = visualizer.run_complete_analysis()
        
        print("\n" + "="*60)
        print("机场燃油量图表分析完成！")
        print("="*60)
        print("生成的文件:")
        for chart_type, file_path in results.items():
            print(f"  {chart_type}: {os.path.basename(file_path)}")
        
        return results
        
    except Exception as e:
        logger.error(f"主程序执行失败: {str(e)}")
        raise

if __name__ == "__main__":
    main() 