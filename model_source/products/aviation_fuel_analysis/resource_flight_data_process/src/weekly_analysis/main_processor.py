import os
import sys
from datetime import datetime
import logging

from data_loader import AirportDataLoader
from weekly_calculator import WeeklyParameterCalculator
from results_saver import ResultsSaver

class WeeklyAirportAnalyzer:
    def __init__(self, data_path, results_dir):
        self.data_path = data_path
        self.results_dir = results_dir
        self.setup_logging()
        
    def setup_logging(self):
        log_dir = os.path.join(self.results_dir, '..', 'logs')
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f'weekly_analysis_main_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def run_analysis(self):
        try:
            self.logger.info("Starting weekly airport analysis")
            self.logger.info(f"Input data: {self.data_path}")
            self.logger.info(f"Output directory: {self.results_dir}")
            
            # Step 1: Load data
            self.logger.info("Step 1: Loading airport data")
            data_loader = AirportDataLoader(self.data_path)
            df = data_loader.load_data()
            
            if df is None or len(df) == 0:
                raise ValueError("No data loaded")
            
            # Step 2: Calculate weekly parameters
            self.logger.info("Step 2: Calculating weekly parameters")
            calculator = WeeklyParameterCalculator()
            all_results = calculator.process_all_airports(data_loader)
            
            if not all_results:
                raise ValueError("No results generated")
            
            # Step 3: Save results
            self.logger.info("Step 3: Saving results")
            results_saver = ResultsSaver(self.results_dir)
            output_info = results_saver.save_all_results(all_results)
            
            # Step 4: Generate summary report
            self.logger.info("Step 4: Generating summary report")
            self.generate_summary_report(all_results, output_info)
            
            self.logger.info("Weekly analysis completed successfully")
            return output_info
            
        except Exception as e:
            self.logger.error(f"Analysis failed: {str(e)}")
            raise
    
    def generate_summary_report(self, all_results, output_info):
        report_lines = [
            "=== 2024年机场周度参数分析报告 ===",
            f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"数据源: {os.path.basename(self.data_path)}",
            "",
            "=== 数据概览 ===",
            f"分析机场数量: {len(all_results)}",
        ]
        
        for airport, data in all_results.items():
            if len(data) > 0:
                weeks_with_data = data['source_week'].notna().sum()
                total_flights = data['total_flights'].sum()
                report_lines.extend([
                    f"",
                    f"机场: {airport}",
                    f"  - 有数据的周数: {weeks_with_data}/52",
                    f"  - 总航班数: {total_flights:,.0f}",
                    f"  - 平均周航班数: {total_flights/weeks_with_data:.1f}" if weeks_with_data > 0 else "  - 平均周航班数: N/A"
                ])
        
        report_lines.extend([
            "",
            "=== 输出文件 ===",
            f"数据表格: {output_info['table_file']}",
            f"图表目录: {output_info['charts_dir']}",
            "",
            "=== 分析说明 ===",
            "1. 每周参数计算基于该周的实际排班数据",
            "2. 如果某周无排班数据，使用最近周的数据进行估算",
            "3. 所有参数包括燃油消耗、CO2排放、成本等多个维度",
            "4. 结果包含周度趋势图和机场对比图",
        ])
        
        report_file = os.path.join(self.results_dir, f"analysis_summary_{output_info['timestamp']}.txt")
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report_lines))
        
        self.logger.info(f"Summary report saved to {report_file}")
        
        # Print summary to console
        print('\n'.join(report_lines))

def main():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.join(current_dir, '..', '..')
    
    data_path = os.path.join(project_root, 'data', 'capital_binhai_airports_data_20250726_123415.xlsx')
    results_dir = os.path.join(project_root, 'results')
    
    if not os.path.exists(data_path):
        print(f"Error: Data file not found: {data_path}")
        sys.exit(1)
    
    analyzer = WeeklyAirportAnalyzer(data_path, results_dir)
    
    try:
        output_info = analyzer.run_analysis()
        print(f"\n分析完成! 结果保存在: {output_info['table_file']}")
        
    except Exception as e:
        print(f"分析失败: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()