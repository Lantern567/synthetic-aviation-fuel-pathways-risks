import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

class ScheduleAwareWeeklyCalculator:
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
        
        # 映射排班字段到星期
        self.schedule_columns = {
            0: '周一排班',    # Monday
            1: '周二排班',    # Tuesday  
            2: '周三排班',    # Wednesday
            3: '周四排班',    # Thursday
            4: '周五排班',    # Friday
            5: '周六排班',    # Saturday
            6: '周日排班'     # Sunday
        }
    
    def extract_schedule_info(self, airport_data):
        """提取排班信息"""
        schedule_info = {}
        
        # 按flight_date分组
        grouped = airport_data.groupby('flight_date')
        
        for date, day_data in grouped:
            if pd.isna(date):
                continue
                
            weekday = date.weekday()  # 0=Monday, 6=Sunday
            schedule_col = self.schedule_columns[weekday]
            
            # 获取该日期的排班状态
            if schedule_col in day_data.columns:
                schedule_status = day_data[schedule_col].iloc[0]
                has_schedule = '有排班' in str(schedule_status)
            else:
                # 如果没有排班字段，根据是否有实际数据判断
                has_schedule = len(day_data) > 0
            
            schedule_info[date] = {
                'weekday': weekday,
                'weekday_name': date.strftime('%A'),
                'has_schedule': has_schedule,
                'has_actual_data': len(day_data) > 0,
                'flight_count': len(day_data)
            }
        
        return schedule_info
    
    def calculate_daily_parameters_with_schedule(self, airport_data):
        """基于排班信息计算每日参数"""
        schedule_info = self.extract_schedule_info(airport_data)
        daily_stats = []
        
        # 按日期分组处理
        grouped = airport_data.groupby('flight_date')
        
        for date, day_data in grouped:
            if pd.isna(date):
                continue
            
            date_info = schedule_info.get(date, {})
            weekday = date.weekday()
            schedule_col = self.schedule_columns[weekday]
            
            # 获取排班状态
            has_schedule = False
            if schedule_col in day_data.columns:
                schedule_status = day_data[schedule_col].iloc[0]
                has_schedule = '有排班' in str(schedule_status)
            
            day_params = {
                'date': date,
                'weekday': weekday,
                'weekday_name': date.strftime('%A'),
                'has_schedule': has_schedule,
                'has_actual_data': len(day_data) > 0,
                'flight_count': len(day_data),
                'schedule_status': day_data[schedule_col].iloc[0] if schedule_col in day_data.columns else 'unknown'
            }
            
            # 只有在有排班的情况下才计算参数
            if has_schedule:
                for param in self.parameter_columns:
                    if param in day_data.columns:
                        try:
                            numeric_data = pd.to_numeric(day_data[param], errors='coerce')
                            valid_data = numeric_data.dropna()
                            
                            if len(valid_data) > 0:
                                day_params[f'{param}_mean'] = valid_data.mean()
                                day_params[f'{param}_sum'] = valid_data.sum()
                                day_params[f'{param}_std'] = valid_data.std() if len(valid_data) > 1 else 0
                            else:
                                # 有排班但无数据，需要估算
                                day_params[f'{param}_mean'] = np.nan
                                day_params[f'{param}_sum'] = np.nan
                                day_params[f'{param}_std'] = np.nan
                                day_params['needs_estimation'] = True
                        except Exception as e:
                            self.logger.warning(f"Could not process parameter {param}: {str(e)}")
                            day_params[f'{param}_mean'] = np.nan
                            day_params[f'{param}_sum'] = np.nan
                            day_params[f'{param}_std'] = np.nan
            else:
                # 没有排班，所有参数为0
                for param in self.parameter_columns:
                    day_params[f'{param}_mean'] = 0
                    day_params[f'{param}_sum'] = 0
                    day_params[f'{param}_std'] = 0
            
            daily_stats.append(day_params)
        
        return pd.DataFrame(daily_stats)
    
    def estimate_missing_scheduled_days(self, daily_data):
        """为有排班但无数据的日子估算参数"""
        daily_data = daily_data.copy()
        
        # 找出需要估算的日子（有排班但无实际数据）
        needs_estimation = daily_data[
            (daily_data['has_schedule'] == True) & 
            (daily_data['has_actual_data'] == False)
        ]
        
        if len(needs_estimation) == 0:
            return daily_data
        
        # 找出有实际数据的日子用于估算
        has_data = daily_data[
            (daily_data['has_schedule'] == True) & 
            (daily_data['has_actual_data'] == True)
        ]
        
        if len(has_data) == 0:
            self.logger.warning("No actual data available for estimation")
            return daily_data
        
        self.logger.info(f"Estimating parameters for {len(needs_estimation)} scheduled days without data")
        
        # 对每个需要估算的日子
        for idx, row in needs_estimation.iterrows():
            target_date = row['date']
            target_weekday = row['weekday']
            
            # 优先使用同一星期几的数据
            same_weekday_data = has_data[has_data['weekday'] == target_weekday]
            
            if len(same_weekday_data) > 0:
                # 使用同星期几的平均值
                source_data = same_weekday_data
                estimation_method = f"same_weekday_{target_weekday}"
            else:
                # 使用最近日期的数据
                distances = np.abs((has_data['date'] - target_date).dt.days)
                nearest_idx = distances.idxmin()
                source_data = has_data.loc[[nearest_idx]]
                estimation_method = f"nearest_date_{distances.min()}_days"
            
            # 更新估算的参数
            for param in self.parameter_columns:
                mean_col = f'{param}_mean'
                sum_col = f'{param}_sum'
                std_col = f'{param}_std'
                
                if mean_col in source_data.columns:
                    daily_data.loc[idx, mean_col] = source_data[mean_col].mean()
                    daily_data.loc[idx, sum_col] = source_data[sum_col].mean()
                    daily_data.loc[idx, std_col] = source_data[std_col].mean()
            
            daily_data.loc[idx, 'estimation_method'] = estimation_method
            daily_data.loc[idx, 'estimated'] = True
            
            self.logger.info(f"Estimated parameters for {target_date.strftime('%Y-%m-%d')} using {estimation_method}")
        
        return daily_data
    
    def generate_2024_weeks(self):
        """生成2024年52周"""
        start_date = datetime(2024, 1, 1)
        weeks = []
        
        for week_num in range(1, 53):
            week_start = start_date + timedelta(weeks=week_num-1)
            week_end = week_start + timedelta(days=6)
            
            if week_end.year > 2024:
                week_end = datetime(2024, 12, 31)
            
            weeks.append({
                'week_number': week_num,
                'week_start': week_start,
                'week_end': week_end,
                'year': 2024
            })
            
            if week_end == datetime(2024, 12, 31):
                break
                
        return weeks
    
    def calculate_weekly_parameters_with_schedule(self, airport_data):
        """基于排班信息计算周度参数，对无数据周用最近周填充"""
        weeks = self.generate_2024_weeks()
        
        # 先计算每日参数
        daily_data = self.calculate_daily_parameters_with_schedule(airport_data)
        
        weekly_results = []
        
        for week in weeks:
            # 获取该周的数据
            week_data = daily_data[
                (daily_data['date'] >= week['week_start']) & 
                (daily_data['date'] <= week['week_end'])
            ]
            
            # 如果该周没有数据，寻找最近的有数据周
            if len(week_data) == 0:
                week_data, source_week = self.find_nearest_week_data(week, daily_data, weeks)
                if len(week_data) == 0:
                    self.logger.warning(f"No data available for week {week['week_number']}")
                    continue
            else:
                source_week = week['week_number']
            
            # 统计该周情况
            actual_data_days = week_data[week_data['has_actual_data'] == True] if 'has_actual_data' in week_data.columns else week_data
            
            week_params = {
                'week_number': week['week_number'],
                'week_start': week['week_start'],
                'week_end': week['week_end'],
                'source_week': source_week,
                'days_with_data': len(week_data),
                'actual_data_days': len(actual_data_days),
                'total_flights': week_data['flight_count'].sum(),
                'avg_daily_flights': week_data['flight_count'].mean()
            }
            
            # 计算周度参数（使用所有有数据的日子）
            for param in self.parameter_columns:
                mean_col = f'{param}_mean'
                sum_col = f'{param}_sum'
                
                if mean_col in week_data.columns:
                    valid_means = week_data[mean_col].dropna()
                    valid_sums = week_data[sum_col].dropna()
                    
                    if len(valid_means) > 0:
                        week_params[f'weekly_{param}_avg'] = valid_means.mean()
                        week_params[f'weekly_{param}_total'] = valid_sums.sum()
                        week_params[f'weekly_{param}_std'] = valid_means.std() if len(valid_means) > 1 else 0
                        week_params[f'weekly_{param}_min'] = valid_means.min()
                        week_params[f'weekly_{param}_max'] = valid_means.max()
                    else:
                        week_params[f'weekly_{param}_avg'] = np.nan
                        week_params[f'weekly_{param}_total'] = np.nan
                        week_params[f'weekly_{param}_std'] = np.nan
                        week_params[f'weekly_{param}_min'] = np.nan
                        week_params[f'weekly_{param}_max'] = np.nan
            
            weekly_results.append(week_params)
        
        return pd.DataFrame(weekly_results)
    
    def find_nearest_week_data(self, target_week, daily_data, weeks):
        """寻找最近的有数据周"""
        target_start = target_week['week_start']
        target_end = target_week['week_end']
        
        # 寻找距离最近的有数据的周
        distances = []
        for i, week in enumerate(weeks):
            week_data = daily_data[
                (daily_data['date'] >= week['week_start']) & 
                (daily_data['date'] <= week['week_end'])
            ]
            if len(week_data) > 0:
                distance = abs((week['week_start'] - target_start).days)
                distances.append((distance, i, week_data))
        
        if distances:
            distances.sort(key=lambda x: x[0])
            nearest_distance, nearest_week_idx, nearest_data = distances[0]
            self.logger.info(f"Using week {weeks[nearest_week_idx]['week_number']} data for week {target_week['week_number']} (distance: {nearest_distance} days)")
            return nearest_data, weeks[nearest_week_idx]['week_number']
        
        return pd.DataFrame(), None
    
    def process_all_airports_with_schedule(self, data_loader):
        """处理所有机场的排班感知计算"""
        airports = data_loader.get_unique_airports()
        all_results = {}
        
        for airport in airports:
            self.logger.info(f"Processing airport with schedule awareness: {airport}")
            airport_data = data_loader.filter_by_airport(airport)
            
            if airport_data is not None and len(airport_data) > 0:
                weekly_params = self.calculate_weekly_parameters_with_schedule(airport_data)
                weekly_params['airport'] = airport
                all_results[airport] = weekly_params
                
                # 输出排班统计信息
                self.log_schedule_statistics(airport, airport_data)
            else:
                self.logger.warning(f"No data found for airport: {airport}")
        
        return all_results
    
    def log_schedule_statistics(self, airport, airport_data):
        """记录排班统计信息"""
        schedule_info = self.extract_schedule_info(airport_data)
        
        total_days = len(schedule_info)
        scheduled_days = sum(1 for info in schedule_info.values() if info['has_schedule'])
        actual_data_days = sum(1 for info in schedule_info.values() if info['has_actual_data'])
        
        self.logger.info(f"{airport} 排班统计:")
        self.logger.info(f"  总天数: {total_days}")
        self.logger.info(f"  有排班天数: {scheduled_days}")
        self.logger.info(f"  有实际数据天数: {actual_data_days}")
        self.logger.info(f"  排班覆盖率: {scheduled_days/total_days*100:.1f}%")
        self.logger.info(f"  数据完整率: {actual_data_days/scheduled_days*100:.1f}%")