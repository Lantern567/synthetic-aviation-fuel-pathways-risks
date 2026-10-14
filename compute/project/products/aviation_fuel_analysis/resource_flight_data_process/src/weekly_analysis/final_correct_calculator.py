import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

class FinalCorrectCalculator:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.parameter_columns = [
            'total_fuel_kg', 'fuel_per_km', 'fuel_per_passenger', 'total_time_minutes',
            'climb_time_minutes', 'cruise_time_minutes', 'descent_time_minutes',
            'climb_fuel_kg', 'cruise_fuel_kg', 'descent_fuel_kg', 'co2_direct_kg',
            'co2_equivalent_kg', 'co2_rf_equivalent_kg', 'co2_per_passenger_kg',
            'co2_per_km_kg', 'co2_per_pkm_kg', 'nox_kg', 'h2o_kg',
            'fuel_efficiency_l_per_100km', 'energy_intensity_mj_per_pkm',
            'carbon_intensity_kg_co2_per_pkm', 'environmental_impact_score',
            'fuel_cost_yuan_avg', 'fuel_cost_per_passenger', 'fuel_cost_per_km',
            'distance_km', 'passengers'
        ]
    
    def generate_2024_weeks(self):
        """生成2024年52周"""
        start_date = datetime(2024, 1, 1)
        weeks = []
        
        for week_num in range(1, 53):
            week_start = start_date + timedelta(weeks=week_num-1)
            # 确保周结束是该周的周日
            week_end = week_start + timedelta(days=6)
            
            if week_end.year > 2024:
                week_end = datetime(2024, 12, 31)
            
            weeks.append({
                'week_number': week_num,
                'week_start': week_start,
                'week_end': week_end
            })
            
            if week_end == datetime(2024, 12, 31):
                break
                
        return weeks
    
    def calculate_weekly_parameters_all_flights(self, airport_data):
        """计算每周所有航班的参数（正确版本）"""
        weeks = self.generate_2024_weeks()
        airport_data['flight_date'] = pd.to_datetime(airport_data['flight_date'])
        
        weekly_results = []
        weeks_with_data = {}  # 存储有数据的周
        
        # 第一步：计算所有有实际数据的周
        for week in weeks:
            week_num = week['week_number']
            week_start = week['week_start']
            week_end = week['week_end']
            
            # 获取该周的所有航班数据
            week_flights = airport_data[
                (airport_data['flight_date'] >= week_start) & 
                (airport_data['flight_date'] <= week_end)
            ]
            
            if len(week_flights) > 0:
                # 该周有数据，计算该周所有航班的聚合参数
                week_params = self.aggregate_week_flights(week_flights, week_num, week_start, week_end)
                week_params['has_original_data'] = True
                week_params['source_week'] = week_num
                weekly_results.append(week_params)
                weeks_with_data[week_num] = week_params
                
                self.logger.info(f"Week {week_num}: {len(week_flights)} flights, total fuel: {week_params.get('weekly_total_fuel_kg_total', 0):.1f} kg")
            else:
                # 该周没有数据，先记录，稍后填充
                week_params = {
                    'week_number': week_num,
                    'week_start': week_start,
                    'week_end': week_end,
                    'has_original_data': False,
                    'total_flights': 0
                }
                weekly_results.append(week_params)
        
        # 第二步：为没有数据的周填充最近周的数据
        for i, week_params in enumerate(weekly_results):
            if not week_params['has_original_data']:
                nearest_week_data = self.find_nearest_week_with_data(week_params['week_number'], weeks_with_data)
                if nearest_week_data:
                    # 用最近周的数据填充
                    for key, value in nearest_week_data.items():
                        if key not in ['week_number', 'week_start', 'week_end', 'has_original_data', 'source_week']:
                            week_params[key] = value
                    
                    week_params['has_original_data'] = False
                    week_params['source_week'] = nearest_week_data['source_week']
                    week_params['is_estimated'] = True
                    
                    self.logger.info(f"Week {week_params['week_number']}: Filled with data from week {nearest_week_data['source_week']}")
                else:
                    self.logger.warning(f"Week {week_params['week_number']}: No data available for filling")
        
        return pd.DataFrame(weekly_results)
    
    def aggregate_week_flights(self, week_flights, week_num, week_start, week_end):
        """聚合一周内所有航班的参数"""
        # 获取机场信息（使用第一条记录）
        first_record = week_flights.iloc[0]
        
        week_params = {
            'week_number': week_num,
            'week_start': week_start,
            'week_end': week_end,
            'total_flights': len(week_flights),
            'flight_days': week_flights['flight_date'].nunique(),
            # 添加出发机场信息
            'departure_airport_name': first_record.iloc[0] if len(week_flights.columns) > 0 else '',
            'departure_airport_latitude': first_record.iloc[1] if len(week_flights.columns) > 1 else '',
            'departure_airport_longitude': first_record.iloc[2] if len(week_flights.columns) > 2 else ''
        }
        
        # 计算每个参数的周度聚合值
        for param in self.parameter_columns:
            if param in week_flights.columns:
                try:
                    # 转换为数值类型
                    numeric_data = pd.to_numeric(week_flights[param], errors='coerce')
                    valid_data = numeric_data.dropna()
                    
                    if len(valid_data) > 0:
                        # 对于不同类型的参数采用不同聚合方式
                        if param in ['total_fuel_kg', 'climb_fuel_kg', 'cruise_fuel_kg', 'descent_fuel_kg', 
                                   'co2_direct_kg', 'co2_equivalent_kg', 'co2_rf_equivalent_kg', 'nox_kg', 'h2o_kg',
                                   'total_time_minutes', 'climb_time_minutes', 'cruise_time_minutes', 'descent_time_minutes',
                                   'distance_km', 'passengers', 'fuel_cost_yuan_avg']:
                            # 这些参数需要求和（总量）
                            week_params[f'weekly_{param}_total'] = valid_data.sum()
                            week_params[f'weekly_{param}_avg'] = valid_data.mean()
                        
                        elif param in ['fuel_per_km', 'fuel_per_passenger', 'co2_per_passenger_kg', 'co2_per_km_kg', 
                                     'co2_per_pkm_kg', 'fuel_efficiency_l_per_100km', 'energy_intensity_mj_per_pkm',
                                     'carbon_intensity_kg_co2_per_pkm', 'fuel_cost_per_passenger', 'fuel_cost_per_km']:
                            # 这些参数是比率，应该求平均
                            week_params[f'weekly_{param}_avg'] = valid_data.mean()
                            week_params[f'weekly_{param}_total'] = valid_data.sum()  # 也提供总和供参考
                        
                        else:
                            # 其他参数默认求平均
                            week_params[f'weekly_{param}_avg'] = valid_data.mean()
                            week_params[f'weekly_{param}_total'] = valid_data.sum()
                        
                        # 额外统计信息
                        week_params[f'weekly_{param}_std'] = valid_data.std() if len(valid_data) > 1 else 0
                        week_params[f'weekly_{param}_min'] = valid_data.min()
                        week_params[f'weekly_{param}_max'] = valid_data.max()
                        week_params[f'weekly_{param}_count'] = len(valid_data)
                    
                    else:
                        # 没有有效数据
                        week_params[f'weekly_{param}_total'] = 0
                        week_params[f'weekly_{param}_avg'] = 0
                        week_params[f'weekly_{param}_std'] = 0
                        week_params[f'weekly_{param}_min'] = 0
                        week_params[f'weekly_{param}_max'] = 0
                        week_params[f'weekly_{param}_count'] = 0
                
                except Exception as e:
                    self.logger.warning(f"Error processing parameter {param}: {str(e)}")
                    week_params[f'weekly_{param}_total'] = 0
                    week_params[f'weekly_{param}_avg'] = 0
                    week_params[f'weekly_{param}_std'] = 0
                    week_params[f'weekly_{param}_min'] = 0
                    week_params[f'weekly_{param}_max'] = 0
                    week_params[f'weekly_{param}_count'] = 0
        
        return week_params
    
    def find_nearest_week_with_data(self, target_week_num, weeks_with_data):
        """找到最近的有数据的周"""
        if not weeks_with_data:
            return None
        
        min_distance = float('inf')
        nearest_week = None
        
        for week_num, week_data in weeks_with_data.items():
            distance = abs(week_num - target_week_num)
            if distance < min_distance:
                min_distance = distance
                nearest_week = week_data
        
        return nearest_week
    
    def process_all_airports_final(self, data_loader):
        """处理所有机场的最终正确计算"""
        airports = data_loader.get_unique_airports()
        all_results = {}
        
        for airport in airports:
            self.logger.info(f"Processing airport with final correct logic: {airport}")
            airport_data = data_loader.filter_by_airport(airport)
            
            if airport_data is not None and len(airport_data) > 0:
                weekly_params = self.calculate_weekly_parameters_all_flights(airport_data)
                weekly_params['airport'] = airport
                all_results[airport] = weekly_params
                
                # 验证结果
                total_weeks = len(weekly_params)
                weeks_with_original_data = weekly_params['has_original_data'].sum()
                estimated_weeks = total_weeks - weeks_with_original_data
                
                self.logger.info(f"{airport} 最终统计:")
                self.logger.info(f"  总周数: {total_weeks}")
                self.logger.info(f"  有原始数据周数: {weeks_with_original_data}")
                self.logger.info(f"  估算填充周数: {estimated_weeks}")
                
                if total_weeks != 52:
                    self.logger.error(f"{airport} 周数不正确！应该是52周，实际是{total_weeks}周")
                else:
                    self.logger.info(f"{airport} ✓ 52周数据完整")
                    
            else:
                self.logger.warning(f"No data found for airport: {airport}")
        
        return all_results