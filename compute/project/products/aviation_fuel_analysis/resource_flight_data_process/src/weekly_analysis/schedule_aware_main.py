import os
import sys
from datetime import datetime
import logging

from data_loader import AirportDataLoader
from schedule_aware_calculator import ScheduleAwareWeeklyCalculator
from results_saver import ResultsSaver

class ScheduleAwareWeeklyAnalyzer:
    def __init__(self, data_path, results_dir):
        self.data_path = data_path
        self.results_dir = results_dir
        self.setup_logging()
        
    def setup_logging(self):
        log_dir = os.path.join(self.results_dir, '..', 'logs')
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f'schedule_aware_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def run_schedule_aware_analysis(self):
        try:
            self.logger.info("Starting schedule-aware weekly airport analysis")
            self.logger.info(f"Input data: {self.data_path}")
            self.logger.info(f"Output directory: {self.results_dir}")
            
            # Step 1: Load data
            self.logger.info("Step 1: Loading airport data")
            data_loader = AirportDataLoader(self.data_path)
            df = data_loader.load_data()
            
            if df is None or len(df) == 0:
                raise ValueError("No data loaded")
            
            # 检查排班字段是否存在
            self.check_schedule_fields(df)
            
            # Step 2: Calculate weekly parameters with schedule awareness
            self.logger.info("Step 2: Calculating weekly parameters with schedule awareness")
            calculator = ScheduleAwareWeeklyCalculator()
            all_results = calculator.process_all_airports_with_schedule(data_loader)
            
            if not all_results:
                raise ValueError("No results generated")
            
            # Step 3: Save results
            self.logger.info("Step 3: Saving schedule-aware results")
            results_saver = ResultsSaver(self.results_dir)
            output_info = results_saver.save_all_results(all_results)
            
            # Step 4: Generate detailed schedule analysis report
            self.logger.info("Step 4: Generating schedule analysis report")
            self.generate_schedule_analysis_report(all_results, output_info, df)
            
            self.logger.info("Schedule-aware weekly analysis completed successfully")
            return output_info
            
        except Exception as e:
            self.logger.error(f"Analysis failed: {str(e)}")
            raise
    
    def check_schedule_fields(self, df):
        """检查排班字段是否存在"""
        expected_schedule_fields = ['周一排班', '周二排班', '周三排班', '周四排班', '周五排班', '周六排班', '周日排班']
        
        missing_fields = []
        for field in expected_schedule_fields:
            if field not in df.columns:
                missing_fields.append(field)
        
        if missing_fields:
            self.logger.warning(f"Missing schedule fields: {missing_fields}")
        else:
            self.logger.info("All schedule fields found in data")
            
            # 显示排班字段的统计信息
            for field in expected_schedule_fields:
                value_counts = df[field].value_counts()
                self.logger.info(f"{field}: {value_counts.to_dict()}")
    
    def generate_schedule_analysis_report(self, all_results, output_info, original_data):
        """生成排班分析报告"""
        report_lines = [
            "=== 2024年机场周度参数分析报告（排班感知版本）===",
            f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"数据源: {os.path.basename(self.data_path)}",
            "",
            "=== 排班数据分析 ===",
        ]
        
        # 分析原始数据中的排班分布
        schedule_fields = ['周一排班', '周二排班', '周三排班', '周四排班', '周五排班', '周六排班', '周日排班']
        weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
        
        for i, field in enumerate(schedule_fields):
            if field in original_data.columns:
                has_schedule = original_data[field].str.contains('有排班', na=False).sum()
                total = len(original_data)
                percentage = has_schedule / total * 100
                report_lines.append(f"{weekdays[i]}: {has_schedule:,}/{total:,} ({percentage:.1f}%) 有排班")
        
        report_lines.extend([
            "",
            "=== 机场数据概览 ===",
            f"分析机场数量: {len(all_results)}",
        ])
        
        for airport, data in all_results.items():
            if len(data) > 0:
                # 计算排班相关统计
                total_weeks = len(data)
                scheduled_weeks = data['scheduled_days'].notna().sum()
                total_scheduled_days = data['scheduled_days'].sum()
                total_actual_days = data['actual_data_days'].sum()
                total_flights = data['total_flights'].sum()
                
                report_lines.extend([
                    f"",
                    f"机场: {airport}",
                    f"  - 分析周数: {total_weeks}/52",
                    f"  - 总排班日数: {total_scheduled_days:.0f}",
                    f"  - 有实际数据日数: {total_actual_days:.0f}",
                    f"  - 数据完整率: {total_actual_days/total_scheduled_days*100:.1f}%" if total_scheduled_days > 0 else "  - 数据完整率: N/A",
                    f"  - 总航班数: {total_flights:,.0f}",
                    f"  - 平均每排班日航班数: {total_flights/total_scheduled_days:.1f}" if total_scheduled_days > 0 else "  - 平均每排班日航班数: N/A"
                ])
        
        report_lines.extend([
            "",
            "=== 输出文件 ===",
            f"数据表格: {output_info['table_file']}",
            f"图表目录: {output_info['charts_dir']}",
            "",
            "=== 改进的分析方法说明 ===",
            "1. 读取每周每日的排班计划（周一到周日）",
            "2. 区分'有排班'和'无排班'日期",
            "3. 对有排班但无实际数据的日期进行智能估算",
            "   - 优先使用相同星期几的历史数据",
            "   - 其次使用时间最接近的数据",
            "4. 周度参数聚合时只考虑有排班的日期",
            "5. 提供排班覆盖率和数据完整率统计",
            "6. 每周参数包含排班日数、实际数据日数等维度",
        ])
        
        report_file = os.path.join(self.results_dir, f"schedule_aware_analysis_summary_{output_info['timestamp']}.txt")
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report_lines))
        
        self.logger.info(f"Schedule analysis report saved to {report_file}")
        
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
    
    analyzer = ScheduleAwareWeeklyAnalyzer(data_path, results_dir)
    
    try:
        output_info = analyzer.run_schedule_aware_analysis()
        print(f"\n排班感知分析完成! 结果保存在: {output_info['table_file']}")
        
    except Exception as e:
        print(f"分析失败: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()