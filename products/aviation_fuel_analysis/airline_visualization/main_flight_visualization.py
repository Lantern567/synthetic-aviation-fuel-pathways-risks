"""
航线数据可视化主程序
整合数据加载和pydeck可视化功能
"""

import os
import sys
import logging
import pandas as pd
from datetime import datetime
from typing import Optional, Dict

# 添加src目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.data_loader.flight_data_loader import FlightDataLoader
from src.visualizer.pydeck_flight_visualizer import PyDeckFlightVisualizer

class FlightVisualizationApp:
    """
    航班可视化应用主类
    """
    
    def __init__(self, data_file_path: Optional[str] = None):
        """
        初始化应用
        
        Args:
            data_file_path: 数据文件路径
        """
        # 设置日志
        self.setup_logging()
        self.logger = logging.getLogger(__name__)
        
        # 初始化组件
        self.data_loader = FlightDataLoader(data_file_path)
        self.visualizer = PyDeckFlightVisualizer()
        
        # 数据存储
        self.raw_data = None
        self.processed_data = None
        self.data_summary = None
        
        self.logger.info("航班可视化应用初始化完成")
    
    def setup_logging(self):
        """设置日志配置"""
        log_dir = os.path.join(os.path.dirname(__file__), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, f'flight_visualization_{datetime.now().strftime("%Y%m%d")}.log')
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
    
    def load_and_process_data(self, sample_size: Optional[int] = 1000):
        """
        加载和处理数据
        
        Args:
            sample_size: 样本大小，如果为None则加载全部数据
        """
        try:
            self.logger.info(f"开始加载数据，样本大小: {sample_size}")
            
            # 加载原始数据
            self.raw_data = self.data_loader.load_raw_data(sample_size)
            self.logger.info(f"原始数据加载完成，记录数: {len(self.raw_data)}")
            
            # 清洗数据
            cleaned_data = self.data_loader.clean_and_validate_data()
            self.logger.info(f"数据清洗完成，有效记录数: {len(cleaned_data)}")
            
            # 准备可视化数据
            self.processed_data = self.data_loader.prepare_for_visualization(cleaned_data)
            
            # 获取数据摘要
            self.data_summary = self.data_loader.get_data_summary()
            
            self.logger.info("数据加载和处理完成")
            self.print_data_summary()
            
        except Exception as e:
            self.logger.error(f"数据加载处理失败: {e}")
            raise
    
    def print_data_summary(self):
        """打印数据摘要"""
        if self.data_summary:
            print("\n" + "="*50)
            print("📊 数据摘要")
            print("="*50)
            print(f"总航线数: {self.data_summary['total_routes']:,}")
            print(f"总城市数: {self.data_summary['total_cities']:,}")
            print(f"总乘客数: {self.data_summary['total_passengers']:,}")
            print(f"总里程数: {self.data_summary['total_distance']:,.0f} 公里")
            print(f"机型种类: {self.data_summary['aircraft_types']}")
            print(f"平均航线距离: {self.data_summary['avg_route_distance']:.0f} 公里")
            print(f"平均航班乘客: {self.data_summary['avg_passengers_per_flight']:.0f} 人")
            
            bounds = self.data_summary['coordinate_bounds']
            print(f"\n🗺️ 地理范围:")
            print(f"经度范围: {bounds['min_lon']:.2f}° - {bounds['max_lon']:.2f}°")
            print(f"纬度范围: {bounds['min_lat']:.2f}° - {bounds['max_lat']:.2f}°")
            print("="*50)
    
    def create_visualization(self, visualization_type: str = 'routes_and_airports', 
                           save_html: bool = True, **kwargs):
        """
        创建可视化
        
        Args:
            visualization_type: 可视化类型
            save_html: 是否保存HTML文件
            **kwargs: 其他参数
            
        Returns:
            pydeck Deck对象
        """
        if self.processed_data is None:
            raise ValueError("请先加载和处理数据")
        
        self.logger.info(f"创建可视化，类型: {visualization_type}")
        
        # 创建可视化
        deck = self.visualizer.create_comprehensive_visualization(
            self.processed_data,
            visualization_type=visualization_type,
            **kwargs
        )
        
        # 保存HTML文件
        if save_html:
            self.save_visualization_html(deck, visualization_type)
        
        return deck
    
    def save_visualization_html(self, deck, visualization_type: str):
        """保存可视化为HTML文件"""
        try:
            # 确保输出目录存在
            output_dir = os.path.join(os.path.dirname(__file__), 'results', 'html_reports')
            os.makedirs(output_dir, exist_ok=True)
            
            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"flight_visualization_{visualization_type}_{timestamp}.html"
            filepath = os.path.join(output_dir, filename)
            
            # 保存HTML
            deck.to_html(filepath)
            
            self.logger.info(f"可视化已保存为HTML文件: {filepath}")
            print(f"✅ 可视化已保存: {filepath}")
            
        except Exception as e:
            self.logger.error(f"保存HTML文件失败: {e}")
            print(f"❌ 保存HTML文件失败: {e}")
    
    def create_multiple_visualizations(self, save_all: bool = True):
        """创建多种类型的可视化"""
        if self.processed_data is None:
            raise ValueError("请先加载和处理数据")
        
        visualizations = [
            ('routes_and_airports', '航线和机场视图'),
            ('heatmap', '城市热力图'),
            ('arc_routes', '3D弧线航线'),
            ('comprehensive', '综合视图')
        ]
        
        results = {}
        
        for viz_type, description in visualizations:
            try:
                self.logger.info(f"创建{description}...")
                print(f"📊 创建{description}...")
                
                deck = self.create_visualization(
                    visualization_type=viz_type,
                    save_html=save_all
                )
                
                results[viz_type] = deck
                print(f"✅ {description}创建完成")
                
            except Exception as e:
                self.logger.error(f"创建{description}失败: {e}")
                print(f"❌ 创建{description}失败: {e}")
        
        return results
    
    def generate_statistics_report(self):
        """生成统计报告"""
        if self.processed_data is None:
            raise ValueError("请先加载和处理数据")
        
        try:
            # 确保输出目录存在
            output_dir = os.path.join(os.path.dirname(__file__), 'results', 'tables')
            os.makedirs(output_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 1. 机型统计报告
            aircraft_stats = self.processed_data['aircraft_stats']
            aircraft_file = os.path.join(output_dir, f"aircraft_statistics_{timestamp}.xlsx")
            aircraft_stats.to_excel(aircraft_file, index=False)
            
            # 2. 机场统计报告
            airport_stats = self.processed_data['airport_stats']
            airport_file = os.path.join(output_dir, f"airport_statistics_{timestamp}.xlsx")
            airport_stats.to_excel(airport_file, index=False)
            
            # 3. 城市统计报告
            cities_stats = self.processed_data['cities']
            cities_file = os.path.join(output_dir, f"cities_statistics_{timestamp}.xlsx")
            cities_stats.to_excel(cities_file, index=False)
            
            # 4. 综合报告
            with pd.ExcelWriter(os.path.join(output_dir, f"comprehensive_report_{timestamp}.xlsx")) as writer:
                aircraft_stats.to_excel(writer, sheet_name='机型统计', index=False)
                airport_stats.to_excel(writer, sheet_name='机场统计', index=False)
                cities_stats.to_excel(writer, sheet_name='城市统计', index=False)
                
                # 添加摘要信息
                summary_df = pd.DataFrame([self.data_summary])
                summary_df.to_excel(writer, sheet_name='数据摘要', index=False)
            
            self.logger.info("统计报告生成完成")
            print("✅ 统计报告已生成并保存到results/tables/目录")
            
        except Exception as e:
            self.logger.error(f"生成统计报告失败: {e}")
            print(f"❌ 生成统计报告失败: {e}")
    
    def run_full_analysis(self, sample_size: Optional[int] = 1000):
        """运行完整分析流程"""
        print("🚀 开始航线数据可视化分析...")
        
        try:
            # 1. 加载和处理数据
            print("📊 步骤1: 加载和处理数据...")
            self.load_and_process_data(sample_size)
            
            # 2. 生成统计报告
            print("📈 步骤2: 生成统计报告...")
            self.generate_statistics_report()
            
            # 3. 创建可视化
            print("🗺️ 步骤3: 创建可视化...")
            visualizations = self.create_multiple_visualizations()
            
            print("\n🎉 分析完成！")
            print("📁 结果文件保存在:")
            print("   - HTML可视化: results/html_reports/")
            print("   - 统计表格: results/tables/")
            print("   - 日志文件: logs/")
            
            return visualizations
            
        except Exception as e:
            self.logger.error(f"完整分析失败: {e}")
            print(f"❌ 分析失败: {e}")
            raise

def main():
    """主函数"""
    print("🛩️ 航线数据可视化系统")
    print("基于pydeck的交互式航线可视化")
    print("-" * 40)
    
    try:
        # 创建应用实例
        app = FlightVisualizationApp()
        
        # 运行完整分析（使用样本数据，可以根据需要调整）
        sample_size = 1000  # 设置为None可加载全部数据
        app.run_full_analysis(sample_size)
        
    except Exception as e:
        print(f"❌ 程序执行失败: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main()) 