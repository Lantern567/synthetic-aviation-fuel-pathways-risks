import os
import sys
from datetime import datetime
import logging

from data_loader import AirportDataLoader
from correct_schedule_calculator import CorrectScheduleCalculator
from results_saver import ResultsSaver

class CorrectScheduleWeeklyAnalyzer:
    def __init__(self, data_path, results_dir):
        self.data_path = data_path
        self.results_dir = results_dir
        self.setup_logging()
        
    def setup_logging(self):
        log_dir = os.path.join(self.results_dir, '..', 'logs')
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f'correct_schedule_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def run_correct_schedule_analysis(self):
        try:
            self.logger.info("Starting correct schedule-aware weekly airport analysis")
            self.logger.info(f"Input data: {self.data_path}")
            self.logger.info(f"Output directory: {self.results_dir}")
            
            # Step 1: Load data
            self.logger.info("Step 1: Loading airport data")
            data_loader = AirportDataLoader(self.data_path)
            df = data_loader.load_data()
            
            if df is None or len(df) == 0:
                raise ValueError("No data loaded")
            
            # Step 2: Calculate weekly parameters with correct schedule logic
            self.logger.info("Step 2: Calculating weekly parameters with correct schedule logic")
            calculator = CorrectScheduleCalculator()
            all_results = calculator.process_all_airports_with_correct_schedule(data_loader)
            
            if not all_results:
                raise ValueError("No results generated")
            
            # Step 3: Save results
            self.logger.info("Step 3: Saving correct schedule results")
            results_saver = ResultsSaver(self.results_dir)
            output_info = results_saver.save_all_results(all_results)
            
            # Step 4: Generate detailed analysis report
            self.logger.info("Step 4: Generating correct schedule analysis report")
            self.generate_correct_schedule_report(all_results, output_info, df)
            
            self.logger.info("Correct schedule weekly analysis completed successfully")
            return output_info
            
        except Exception as e:
            self.logger.error(f"Analysis failed: {str(e)}")
            raise
    
    def generate_correct_schedule_report(self, all_results, output_info, original_data):
        """生成正确的排班分析报告"""
        report_lines = [
            "=== 2024年机场周度参数分析报告（正确排班版本）===",
            f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"数据源: {os.path.basename(self.data_path)}",
            "",
            "=== 排班逻辑说明 ===",
            "1. 读取每周的排班计划（周一到周日）",
            "2. 对有排班的日期：",
            "   - 有实际数据时，使用实际数据",
            "   - 无实际数据时，用相同星期几或最近日期估算",
            "3. 对无排班的日期：参数为0，不参与周度计算",
            "4. 对完全无排班数据的周：用最近有排班的周代替",
            "",
            "=== 机场数据概览 ===",
            f"分析机场数量: {len(all_results)}",
        ]
        
        for airport, data in all_results.items():
            if len(data) > 0:
                total_weeks = len(data)
                estimated_weeks = data['is_estimated'].sum() if 'is_estimated' in data.columns else 0
                actual_weeks = total_weeks - estimated_weeks
                
                # 计算统计信息
                total_scheduled_days = data['scheduled_days'].sum() if 'scheduled_days' in data.columns else 0
                total_flights = data['total_flights'].sum() if 'total_flights' in data.columns else 0
                avg_scheduled_days = data['scheduled_days'].mean() if 'scheduled_days' in data.columns else 0
                
                report_lines.extend([
                    f"",
                    f"机场: {airport}",
                    f"  - 分析周数: {total_weeks}/52",
                    f"  - 有原始排班数据周数: {actual_weeks}",
                    f"  - 估算周数: {estimated_weeks}",
                    f"  - 总排班天数: {total_scheduled_days:.0f}",
                    f"  - 平均每周排班天数: {avg_scheduled_days:.1f}",
                    f"  - 总航班数: {total_flights:,.0f}",
                    f"  - 平均每排班日航班数: {total_flights/total_scheduled_days:.1f}" if total_scheduled_days > 0 else "  - 平均每排班日航班数: N/A"
                ])
        
        report_lines.extend([
            "",
            "=== 输出文件 ===",
            f"数据表格: {output_info['table_file']}",
            f"图表目录: {output_info['charts_dir']}",
            "",
            "=== 与之前方法的区别 ===",
            "1. 正确读取和解析排班字段（周一排班~周日排班）",
            "2. 严格按照排班计划计算周度参数",
            "3. 区分有排班/无排班日期，避免无排班日期参与计算",
            "4. 为有排班但无数据的日期提供智能估算",
            "5. 对无排班数据的周使用最近周代替",
            "6. 提供排班覆盖率和数据完整性统计",
        ])
        
        report_file = os.path.join(self.results_dir, f"correct_schedule_analysis_summary_{output_info['timestamp']}.txt")
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report_lines))
        
        self.logger.info(f"Correct schedule analysis report saved to {report_file}")
        
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
    
    analyzer = CorrectScheduleWeeklyAnalyzer(data_path, results_dir)
    
    try:
        output_info = analyzer.run_correct_schedule_analysis()
        print(f"\n正确排班分析完成! 结果保存在: {output_info['table_file']}")
        
    except Exception as e:
        print(f"分析失败: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()