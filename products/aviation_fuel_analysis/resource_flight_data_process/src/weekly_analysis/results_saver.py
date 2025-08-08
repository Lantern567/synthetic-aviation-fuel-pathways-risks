import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
from datetime import datetime
import logging

class ResultsSaver:
    def __init__(self, results_dir):
        self.results_dir = results_dir
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.logger = logging.getLogger(__name__)
        
        os.makedirs(os.path.join(results_dir, 'tables'), exist_ok=True)
        os.makedirs(os.path.join(results_dir, 'charts'), exist_ok=True)
    
    def save_weekly_results_tables(self, all_results):
        tables_dir = os.path.join(self.results_dir, 'tables')
        
        for airport, weekly_data in all_results.items():
            if len(weekly_data) > 0:
                filename = f"{airport}_weekly_parameters_{self.timestamp}.xlsx"
                filepath = os.path.join(tables_dir, filename)
                
                with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                    weekly_data.to_excel(writer, sheet_name='Weekly_Parameters', index=False)
                    
                    summary_data = self.create_summary_statistics(weekly_data)
                    summary_data.to_excel(writer, sheet_name='Summary_Statistics', index=False)
                
                self.logger.info(f"Saved weekly parameters for {airport} to {filepath}")
        
        combined_df = pd.concat(all_results.values(), ignore_index=True)
        combined_filepath = os.path.join(tables_dir, f"all_airports_weekly_parameters_{self.timestamp}.xlsx")
        
        with pd.ExcelWriter(combined_filepath, engine='openpyxl') as writer:
            combined_df.to_excel(writer, sheet_name='All_Airports', index=False)
            
            for airport in combined_df['airport'].unique():
                airport_data = combined_df[combined_df['airport'] == airport]
                sheet_name = f"{airport}"[:31]  # Excel sheet名称限制
                airport_data.to_excel(writer, sheet_name=sheet_name, index=False)
        
        self.logger.info(f"Saved combined results to {combined_filepath}")
        return combined_filepath
    
    def create_summary_statistics(self, weekly_data):
        summary_stats = []
        
        numeric_columns = weekly_data.select_dtypes(include=['float64', 'int64']).columns
        
        for col in numeric_columns:
            if 'weekly_' in col and '_avg' in col:
                param_name = col.replace('weekly_', '').replace('_avg', '')
                valid_data = weekly_data[col].dropna()
                
                if len(valid_data) > 0:
                    stats = {
                        'parameter': param_name,
                        'mean': valid_data.mean(),
                        'std': valid_data.std(),
                        'min': valid_data.min(),
                        'max': valid_data.max(),
                        'median': valid_data.median(),
                        'count': len(valid_data),
                        'missing_weeks': 52 - len(valid_data)
                    }
                    summary_stats.append(stats)
        
        return pd.DataFrame(summary_stats)
    
    def create_weekly_trend_charts(self, all_results):
        charts_dir = os.path.join(self.results_dir, 'charts')
        
        key_parameters = [
            'weekly_total_fuel_kg_avg',
            'weekly_co2_direct_kg_avg', 
            'weekly_fuel_cost_yuan_avg_avg',
            'weekly_passengers_avg',
            'total_flights'
        ]
        
        parameter_names = {
            'weekly_total_fuel_kg_avg': 'Average Fuel Consumption (kg)',
            'weekly_co2_direct_kg_avg': 'Average CO2 Emissions (kg)',
            'weekly_fuel_cost_yuan_avg_avg': 'Average Fuel Cost (Yuan)',
            'weekly_passengers_avg': 'Average Passengers',
            'total_flights': 'Total Flights'
        }
        
        plt.rcParams['font.sans-serif'] = ['SimHei']
        plt.rcParams['axes.unicode_minus'] = False
        
        for airport, weekly_data in all_results.items():
            if len(weekly_data) == 0:
                continue
                
            fig, axes = plt.subplots(2, 3, figsize=(18, 12))
            fig.suptitle(f'{airport} - 2024年52周参数趋势分析', fontsize=16)
            
            axes = axes.flatten()
            
            for i, param in enumerate(key_parameters):
                if param in weekly_data.columns:
                    valid_data = weekly_data[['week_number', param]].dropna()
                    
                    if len(valid_data) > 0:
                        axes[i].plot(valid_data['week_number'], valid_data[param], 
                                   marker='o', linewidth=2, markersize=4)
                        axes[i].set_title(parameter_names.get(param, param))
                        axes[i].set_xlabel('周数')
                        axes[i].set_ylabel('数值')
                        axes[i].grid(True, alpha=0.3)
                        axes[i].set_xlim(1, 52)
                    else:
                        axes[i].text(0.5, 0.5, '无数据', ha='center', va='center', 
                                   transform=axes[i].transAxes)
                        axes[i].set_title(parameter_names.get(param, param))
            
            if len(key_parameters) < len(axes):
                axes[-1].axis('off')
            
            plt.tight_layout()
            chart_filename = f"{airport}_weekly_trends_{self.timestamp}.png"
            chart_filepath = os.path.join(charts_dir, chart_filename)
            plt.savefig(chart_filepath, dpi=300, bbox_inches='tight')
            plt.close()
            
            self.logger.info(f"Saved trend chart for {airport} to {chart_filepath}")
    
    def create_comparison_charts(self, all_results):
        charts_dir = os.path.join(self.results_dir, 'charts')
        
        if len(all_results) < 2:
            self.logger.info("Less than 2 airports, skipping comparison charts")
            return
        
        combined_df = pd.concat(all_results.values(), ignore_index=True)
        
        key_metrics = [
            'weekly_total_fuel_kg_avg',
            'weekly_co2_direct_kg_avg',
            'weekly_fuel_cost_yuan_avg_avg'
        ]
        
        metric_names = {
            'weekly_total_fuel_kg_avg': '平均燃油消耗 (kg)',
            'weekly_co2_direct_kg_avg': '平均CO2排放 (kg)',
            'weekly_fuel_cost_yuan_avg_avg': '平均燃油成本 (元)'
        }
        
        plt.rcParams['font.sans-serif'] = ['SimHei']
        plt.rcParams['axes.unicode_minus'] = False
        
        fig, axes = plt.subplots(1, 3, figsize=(18, 6))
        fig.suptitle('机场间参数对比分析 - 2024年平均值', fontsize=16)
        
        for i, metric in enumerate(key_metrics):
            if metric in combined_df.columns:
                airport_avg = combined_df.groupby('airport')[metric].mean()
                
                axes[i].bar(airport_avg.index, airport_avg.values)
                axes[i].set_title(metric_names.get(metric, metric))
                axes[i].set_ylabel('数值')
                axes[i].tick_params(axis='x', rotation=45)
                
                for j, v in enumerate(airport_avg.values):
                    if not pd.isna(v):
                        axes[i].text(j, v, f'{v:.1f}', ha='center', va='bottom')
        
        plt.tight_layout()
        comparison_filepath = os.path.join(charts_dir, f"airports_comparison_{self.timestamp}.png")
        plt.savefig(comparison_filepath, dpi=300, bbox_inches='tight')
        plt.close()
        
        self.logger.info(f"Saved comparison chart to {comparison_filepath}")
    
    def save_all_results(self, all_results):
        table_filepath = self.save_weekly_results_tables(all_results)
        self.create_weekly_trend_charts(all_results)
        self.create_comparison_charts(all_results)
        
        return {
            'table_file': table_filepath,
            'charts_dir': os.path.join(self.results_dir, 'charts'),
            'timestamp': self.timestamp
        }