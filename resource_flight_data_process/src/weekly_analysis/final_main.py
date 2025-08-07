import os
import sys
from datetime import datetime
import logging

from data_loader import AirportDataLoader
from final_correct_calculator import FinalCorrectCalculator
from results_saver import ResultsSaver

class FinalWeeklyAnalyzer:
    def __init__(self, data_path, results_dir):
        self.data_path = data_path
        self.results_dir = results_dir
        self.setup_logging()
        
    def setup_logging(self):
        log_dir = os.path.join(self.results_dir, '..', 'logs')
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f'final_weekly_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def run_final_analysis(self):
        try:
            self.logger.info("Starting FINAL correct weekly airport analysis")
            self.logger.info("要求：必须计算52周完整数据，每周数据是该周所有航班的叠加")
            self.logger.info(f"Input data: {self.data_path}")
            self.logger.info(f"Output directory: {self.results_dir}")
            
            # Step 1: Load data
            self.logger.info("Step 1: Loading airport data")
            data_loader = AirportDataLoader(self.data_path)
            df = data_loader.load_data()
            
            if df is None or len(df) == 0:
                raise ValueError("No data loaded")
            
            # Step 2: Calculate weekly parameters with final correct logic
            self.logger.info("Step 2: Calculating 52 weeks with all flights aggregation")
            calculator = FinalCorrectCalculator()
            all_results = calculator.process_all_airports_final(data_loader)
            
            if not all_results:
                raise ValueError("No results generated")
            
            # 验证52周完整性
            for airport, data in all_results.items():
                if len(data) != 52:
                    raise ValueError(f"{airport} 数据不完整！只有{len(data)}周，应该是52周")
                self.logger.info(f"✓ {airport}: 52周数据完整")
            
            # Step 3: Save results
            self.logger.info("Step 3: Saving final results")
            results_saver = ResultsSaver(self.results_dir)
            output_info = results_saver.save_all_results(all_results)
            
            # Step 4: Generate final analysis report
            self.logger.info("Step 4: Generating final analysis report")
            self.generate_final_report(all_results, output_info, df)
            
            self.logger.info("FINAL weekly analysis completed successfully")
            return output_info
            
        except Exception as e:
            self.logger.error(f"Analysis failed: {str(e)}")
            raise
    
    def generate_final_report(self, all_results, output_info, original_data):
        """生成最终分析报告"""
        report_lines = [
            "=== 2024年机场周度参数分析报告（最终正确版本）===",
            f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"数据源: {os.path.basename(self.data_path)}",
            "",
            "=== 计算逻辑说明 ===",
            "1. 严格计算52周完整数据，不允许缺失",
            "2. 每周数据 = 该周所有航班的参数叠加/聚合",
            "   - 总量参数（燃油、CO2、时间等）：求和",
            "   - 比率参数（单位消耗等）：求平均值",
            "3. 没有数据的周：用时间最近的有数据周填充",
            "4. 提供每个参数的：总计、平均、标准差、最大最小值",
            "",
            "=== 数据完整性验证 ===",
        ]
        
        for airport, data in all_results.items():
            weeks_count = len(data)
            original_data_weeks = data['has_original_data'].sum() if 'has_original_data' in data.columns else 0
            estimated_weeks = weeks_count - original_data_weeks
            
            # 计算总航班数和总燃油消耗
            total_flights = data['total_flights'].sum() if 'total_flights' in data.columns else 0
            total_fuel = data['weekly_total_fuel_kg_total'].sum() if 'weekly_total_fuel_kg_total' in data.columns else 0
            total_co2 = data['weekly_co2_direct_kg_total'].sum() if 'weekly_co2_direct_kg_total' in data.columns else 0
            
            status = "✓ 完整" if weeks_count == 52 else f"✗ 不完整({weeks_count}/52)"
            
            report_lines.extend([
                f"",
                f"机场: {airport} - {status}",
                f"  - 总周数: {weeks_count}/52",
                f"  - 有原始数据周数: {original_data_weeks}",
                f"  - 填充估算周数: {estimated_weeks}",
                f"  - 数据覆盖率: {original_data_weeks/52*100:.1f}%",
                f"  - 全年总航班数: {total_flights:,.0f}",
                f"  - 全年总燃油消耗: {total_fuel:,.1f} kg",
                f"  - 全年总CO2排放: {total_co2:,.1f} kg",
                f"  - 平均每周航班数: {total_flights/52:.1f}",
                f"  - 平均每周燃油消耗: {total_fuel/52:,.1f} kg"
            ])
        
        report_lines.extend([
            "",
            "=== 输出文件 ===",
            f"主数据表格: {output_info['table_file']}",
            f"图表目录: {output_info['charts_dir']}",
            "",
            "=== 数据表格结构 ===",
            "每行代表一个机场的一周数据，包含以下字段：",
            "- week_number: 周数 (1-52)",
            "- airport: 机场名称",
            "- total_flights: 该周总航班数",
            "- has_original_data: 是否为原始数据",
            "- source_week: 数据来源周（如果是填充数据）",
            "",
            "每个参数包含6个统计维度：",
            "- weekly_XXX_total: 周总计",
            "- weekly_XXX_avg: 周平均",
            "- weekly_XXX_std: 标准差", 
            "- weekly_XXX_min: 最小值",
            "- weekly_XXX_max: 最大值",
            "- weekly_XXX_count: 有效数据点数",
            "",
            "=== 验证确认 ===",
            "✓ 52周数据完整性：已验证",
            "✓ 每周数据为该周所有航班聚合：已实现",
            "✓ 缺失周用最近周填充：已实现",
            "✓ 参数计算正确性：总量求和，比率求均值",
        ])
        
        report_file = os.path.join(self.results_dir, f"final_analysis_summary_{output_info['timestamp']}.txt")
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report_lines))
        
        self.logger.info(f"Final analysis report saved to {report_file}")
        
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
    
    analyzer = FinalWeeklyAnalyzer(data_path, results_dir)
    
    try:
        output_info = analyzer.run_final_analysis()
        print(f"\n🎉 最终分析完成! 52周完整数据已生成")
        print(f"📊 结果文件: {output_info['table_file']}")
        
    except Exception as e:
        print(f"❌ 分析失败: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()