import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from cartopy.feature import LAND, RIVERS
from scipy.ndimage import gaussian_filter
import frykit.plot as fplt
import os
import matplotlib
from matplotlib.colors import LinearSegmentedColormap
import seaborn as sns
from datetime import datetime
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 设置全局字体为微软雅黑
matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei']
matplotlib.rcParams['axes.unicode_minus'] = False

class FuelDensityVisualizer:
    """燃油量密度图可视化类"""
    
    def __init__(self, data_dir=None, results_dir=None):
        """
        初始化可视化器
        
        Args:
            data_dir: 数据目录路径
            results_dir: 结果目录路径
        """
        if data_dir is None:
            self.data_dir = os.path.join(os.path.dirname(__file__), '../data')
        else:
            self.data_dir = data_dir
            
        if results_dir is None:
            self.results_dir = os.path.join(os.path.dirname(__file__), '../results')
        else:
            self.results_dir = results_dir
            
        # 地图投影设置
        self.map_crs = fplt.CN_AZIMUTHAL_EQUIDISTANT
        self.data_crs = fplt.PLATE_CARREE
        
        # 设置刻度
        self.xticks = np.arange(-180, 181, 10)
        self.yticks = np.arange(-90, 91, 10)
        
    def load_fuel_calculation_results(self):
        """加载燃油计算结果数据"""
        try:
            # 查找最新的并行计算结果文件
            parallel_results_dir = os.path.join(self.results_dir, 'parallel_calculation')
            
            if not os.path.exists(parallel_results_dir):
                raise FileNotFoundError(f"并行计算结果目录不存在: {parallel_results_dir}")
            
            # 获取所有Excel文件，排除统计文件
            excel_files = [f for f in os.listdir(parallel_results_dir) 
                          if f.endswith('.xlsx') and not f.startswith('处理统计')]
            
            if not excel_files:
                raise FileNotFoundError(f"在{parallel_results_dir}中未找到Excel结果文件")
            
            # 选择最新的文件
            latest_file = max(excel_files, key=lambda x: os.path.getctime(os.path.join(parallel_results_dir, x)))
            file_path = os.path.join(parallel_results_dir, latest_file)
            
            logger.info(f"加载燃油计算结果文件: {file_path}")
            
            # 读取Excel文件
            df = pd.read_excel(file_path)
            
            logger.info(f"加载了 {len(df)} 条燃油计算记录")
            logger.info(f"数据列: {list(df.columns)}")
            
            return df
        
        except Exception as e:
            logger.error(f"加载燃油计算结果时出错: {str(e)}")
            raise
    
    def load_airport_data(self):
        """加载机场数据"""
        try:
            excel_path = os.path.join(self.data_dir, '22年1月1日至24年12月31日航班数据.xlsx')
            
            if not os.path.exists(excel_path):
                raise FileNotFoundError(f"航班数据文件不存在: {excel_path}")
            
            logger.info(f"加载航班数据文件: {excel_path}")
            df = pd.read_excel(excel_path)
            
            # 提取起飞机场及其坐标，去重
            airports = df[['起飞机场', '起飞机场y', '起飞机场x']].drop_duplicates()
            
            logger.info(f"加载了 {len(airports)} 个独特的起飞机场")
            
            return airports
        
        except Exception as e:
            logger.error(f"加载机场数据时出错: {str(e)}")
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
                # 转换日期格式
                fuel_df['日期'] = pd.to_datetime(fuel_df['日期'], errors='coerce')
                # 筛选2024年数据
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
            
            fuel_col = fuel_columns[0]  # 使用第一个找到的燃油量列
            logger.info(f"使用燃油量列: {fuel_col}")
            
            # 查找起飞机场列
            airport_columns = [col for col in fuel_2024.columns if '起飞机场' in col]
            
            if not airport_columns:
                raise ValueError("未找到起飞机场列")
            
            airport_col = airport_columns[0]
            logger.info(f"使用起飞机场列: {airport_col}")
            
            # 按起飞机场聚合燃油量
            aggregated = fuel_2024.groupby(airport_col)[fuel_col].agg(['sum', 'count', 'mean']).reset_index()
            aggregated.columns = ['起飞机场', '总燃油量', '航班数量', '平均燃油量']
            
            logger.info(f"聚合后得到 {len(aggregated)} 个机场的燃油量数据")
            logger.info(f"总燃油量范围: {aggregated['总燃油量'].min():.2f} - {aggregated['总燃油量'].max():.2f}")
            
            return aggregated
        
        except Exception as e:
            logger.error(f"聚合燃油量数据时出错: {str(e)}")
            raise
    
    def merge_fuel_with_coordinates(self, fuel_aggregated, airports):
        """
        将燃油量数据与机场坐标合并
        
        Args:
            fuel_aggregated: 聚合的燃油量数据
            airports: 机场坐标数据
            
        Returns:
            DataFrame: 合并后的数据
        """
        try:
            merged = pd.merge(fuel_aggregated, airports, on='起飞机场', how='inner')
            
            logger.info(f"合并后得到 {len(merged)} 个机场的完整数据")
            
            # 检查是否有坐标为空的数据
            missing_coords = merged[merged['起飞机场x'].isna() | merged['起飞机场y'].isna()]
            if len(missing_coords) > 0:
                logger.warning(f"有 {len(missing_coords)} 个机场缺少坐标信息")
            
            # 移除坐标为空的数据
            merged_clean = merged.dropna(subset=['起飞机场x', '起飞机场y'])
            
            return merged_clean
        
        except Exception as e:
            logger.error(f"合并数据时出错: {str(e)}")
            raise
    
    def create_base_map(self, figsize=(12, 8)):
        """
        创建基础地图（基于visualize_departure_airports.py）
        
        Args:
            figsize: 图形大小
            
        Returns:
            tuple: (fig, main_ax, mini_ax)
        """
        # 准备大地图
        fig = plt.figure(figsize=figsize)
        main_ax = fig.add_subplot(projection=self.map_crs)
        fplt.set_map_ticks(main_ax, (74, 136, 13, 57), self.xticks, self.yticks)
        main_ax.gridlines(xlocs=self.xticks, ylocs=self.yticks, lw=0.5, ls="--", color="gray")
        
        # 类似 NCL 的刻度风格
        main_ax.tick_params(
            length=8,
            width=0.9,
            labelsize=8,
            top=True,
            right=True,
            labeltop=True,
            labelright=True,
        )
        
        # 准备小地图
        mini_ax = fplt.add_mini_axes(main_ax)
        mini_ax.set_extent((105, 122, 2, 25), self.data_crs)
        mini_ax.gridlines(xlocs=self.xticks, ylocs=self.yticks, lw=0.5, ls="--", color="gray")
        
        # 添加要素
        for ax in [main_ax, mini_ax]:
            ax.set_facecolor("skyblue")
            ax.add_feature(LAND, fc="floralwhite", ec="k", lw=0.5)
            fplt.add_cn_city(ax, lw=0.2, edgecolor='lightgreen', linestyle='--', zorder=2)
            fplt.add_cn_line(ax, lw=1.2, edgecolor='dimgray', zorder=2.5)
            fplt.add_cn_border(ax, lw=0.75, edgecolor='black', zorder=3)
        
        return fig, main_ax, mini_ax
    
    def create_density_visualization(self, merged_data, output_filename=None):
        """
        创建燃油量密度图可视化
        
        Args:
            merged_data: 合并后的数据（包含坐标和燃油量）
            output_filename: 输出文件名
        """
        try:
            # 创建基础地图
            fig, main_ax, mini_ax = self.create_base_map(figsize=(14, 10))
            
            # 准备数据
            x = merged_data['起飞机场x'].values
            y = merged_data['起飞机场y'].values
            fuel = merged_data['总燃油量'].values
            
            # 标准化燃油量用于颜色映射
            fuel_normalized = (fuel - fuel.min()) / (fuel.max() - fuel.min())
            
            # 创建自定义颜色映射（从蓝色到红色）
            colors = ['#0000FF', '#0080FF', '#00FFFF', '#00FF80', '#00FF00', 
                     '#80FF00', '#FFFF00', '#FF8000', '#FF4000', '#FF0000']
            n_bins = 256
            cmap = LinearSegmentedColormap.from_list('fuel_density', colors, N=n_bins)
            
            # 在主地图上绘制散点图，点的大小根据燃油量调整
            sizes = 20 + (fuel_normalized * 100)  # 基础大小20，最大增加100
            
            scatter = main_ax.scatter(
                x, y, 
                c=fuel, 
                s=sizes,
                cmap=cmap,
                alpha=0.7,
                edgecolors='black',
                linewidth=0.5,
                transform=self.data_crs, 
                zorder=10
            )
            
            # 在小地图上绘制南海区域的点
            mini_mask = (x >= 105) & (x <= 122) & (y >= 2) & (y <= 25)
            if np.any(mini_mask):
                mini_x = x[mini_mask]
                mini_y = y[mini_mask]
                mini_fuel = fuel[mini_mask]
                mini_sizes = 10 + (fuel_normalized[mini_mask] * 30)
                
                mini_ax.scatter(
                    mini_x, mini_y,
                    c=mini_fuel,
                    s=mini_sizes,
                    cmap=cmap,
                    alpha=0.7,
                    edgecolors='black',
                    linewidth=0.3,
                    transform=self.data_crs,
                    zorder=10
                )
            
            # 添加颜色条
            cbar = plt.colorbar(scatter, ax=main_ax, shrink=0.8, pad=0.02)
            cbar.set_label('总燃油量 (单位)', fontsize=12)
            cbar.ax.tick_params(labelsize=10)
            
            # 添加图例和标题
            plt.suptitle('2024年各起飞机场航班总燃油量密度图', fontsize=16, fontweight='bold')
            
            # 添加指北针和比例尺
            fplt.add_compass(main_ax, 0.92, 0.85, size=15, style="star")
            scale_bar = fplt.add_scale_bar(main_ax, 0.05, 0.95, length=1000)
            scale_bar.set_xticks([0, 500, 1000])
            scale_bar.xaxis.get_label().set_fontsize("small")
            
            # 小地图比例尺
            scale_bar2 = fplt.add_scale_bar(mini_ax, 0.4, 0.15, length=500)
            scale_bar2.set_xticks([0, 500])
            scale_bar2.xaxis.get_label().set_fontsize("small")
            
            # 添加统计信息文本框
            stats_text = f"""统计信息:
机场数量: {len(merged_data)}
总燃油量: {fuel.sum():.0f}
平均燃油量: {fuel.mean():.0f}
最大燃油量: {fuel.max():.0f}"""
            
            main_ax.text(0.02, 0.02, stats_text, transform=main_ax.transAxes,
                        bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8),
                        fontsize=10, verticalalignment='bottom')
            
            # 保存图像
            if output_filename is None:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                output_filename = f'fuel_density_map_2024_{timestamp}.png'
            
            output_path = os.path.join(self.results_dir, 'figures', output_filename)
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            fplt.savefig(output_path, dpi=300, bbox_inches='tight')
            logger.info(f"密度图已保存到: {output_path}")
            
            plt.close(fig)
            
            return output_path
        
        except Exception as e:
            logger.error(f"创建密度图时出错: {str(e)}")
            raise
    
    def generate_fuel_density_report(self, merged_data, output_filename=None):
        """
        生成燃油量密度分析报告
        
        Args:
            merged_data: 合并后的数据
            output_filename: 输出文件名
        """
        try:
            if output_filename is None:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                output_filename = f'fuel_density_report_2024_{timestamp}.txt'
            
            output_path = os.path.join(self.results_dir, 'tables', output_filename)
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write("2024年各起飞机场航班总燃油量密度分析报告\n")
                f.write("=" * 50 + "\n\n")
                
                f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                f.write("总体统计:\n")
                f.write(f"机场数量: {len(merged_data)}\n")
                f.write(f"总燃油量: {merged_data['总燃油量'].sum():.2f}\n")
                f.write(f"平均燃油量: {merged_data['总燃油量'].mean():.2f}\n")
                f.write(f"燃油量标准差: {merged_data['总燃油量'].std():.2f}\n")
                f.write(f"最大燃油量: {merged_data['总燃油量'].max():.2f}\n")
                f.write(f"最小燃油量: {merged_data['总燃油量'].min():.2f}\n\n")
                
                f.write("燃油量分位数分析:\n")
                percentiles = [25, 50, 75, 90, 95, 99]
                for p in percentiles:
                    value = np.percentile(merged_data['总燃油量'], p)
                    f.write(f"{p}%分位数: {value:.2f}\n")
                f.write("\n")
                
                f.write("燃油量前10名机场:\n")
                top_10 = merged_data.nlargest(10, '总燃油量')[['起飞机场', '总燃油量', '航班数量', '平均燃油量']]
                for idx, row in top_10.iterrows():
                    f.write(f"{row['起飞机场']}: 总量={row['总燃油量']:.2f}, 航班数={row['航班数量']}, 平均={row['平均燃油量']:.2f}\n")
                f.write("\n")
                
                f.write("航班数量前10名机场:\n")
                top_flights = merged_data.nlargest(10, '航班数量')[['起飞机场', '航班数量', '总燃油量', '平均燃油量']]
                for idx, row in top_flights.iterrows():
                    f.write(f"{row['起飞机场']}: 航班数={row['航班数量']}, 总量={row['总燃油量']:.2f}, 平均={row['平均燃油量']:.2f}\n")
            
            logger.info(f"分析报告已保存到: {output_path}")
            return output_path
        
        except Exception as e:
            logger.error(f"生成分析报告时出错: {str(e)}")
            raise
    
    def run_complete_analysis(self):
        """运行完整的燃油量密度分析"""
        try:
            logger.info("开始燃油量密度分析...")
            
            # 1. 加载数据
            logger.info("1. 加载燃油计算结果...")
            fuel_df = self.load_fuel_calculation_results()
            
            logger.info("2. 加载机场数据...")
            airports = self.load_airport_data()
            
            # 2. 数据处理
            logger.info("3. 聚合2024年燃油量数据...")
            fuel_aggregated = self.aggregate_fuel_by_airport_2024(fuel_df)
            
            logger.info("4. 合并燃油量与坐标数据...")
            merged_data = self.merge_fuel_with_coordinates(fuel_aggregated, airports)
            
            # 3. 生成可视化
            logger.info("5. 创建密度图可视化...")
            map_path = self.create_density_visualization(merged_data)
            
            # 4. 生成报告
            logger.info("6. 生成分析报告...")
            report_path = self.generate_fuel_density_report(merged_data)
            
            logger.info("燃油量密度分析完成!")
            logger.info(f"密度图保存在: {map_path}")
            logger.info(f"分析报告保存在: {report_path}")
            
            return {
                'map_path': map_path,
                'report_path': report_path,
                'data': merged_data
            }
        
        except Exception as e:
            logger.error(f"运行完整分析时出错: {str(e)}")
            raise

def main():
    """主函数"""
    try:
        # 创建可视化器实例
        visualizer = FuelDensityVisualizer()
        
        # 运行完整分析
        results = visualizer.run_complete_analysis()
        
        print("燃油量密度分析已完成!")
        print(f"结果文件:")
        print(f"  - 密度图: {results['map_path']}")
        print(f"  - 分析报告: {results['report_path']}")
        
    except Exception as e:
        print(f"程序运行出错: {str(e)}")
        raise

if __name__ == "__main__":
    main() 