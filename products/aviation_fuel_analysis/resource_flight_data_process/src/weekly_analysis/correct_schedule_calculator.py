import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

class CorrectScheduleCalculator:
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
        
        # 实际的排班字段名称（基于数据检查）
        self.schedule_columns = {
            0: '周一排班',    # Monday
            1: '周二排班',    # Tuesday  
            2: '周三排班',    # Wednesday
            3: '周四排班',    # Thursday
            4: '周五排班',    # Friday
            5: '周六排班',    # Saturday
            6: '周日排班'     # Sunday
        }
    
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
    
    def extract_weekly_schedule_plan(self, airport_data):
        """从数据中提取周度排班计划"""
        weeks = self.generate_2024_weeks()
        weekly_schedules = {}
        
        for week in weeks:
            week_num = week['week_number']
            week_start = week['week_start']
            week_end = week['week_end']
            
            # 获取该周的任意一条数据来读取排班计划
            week_data = airport_data[
                (pd.to_datetime(airport_data['flight_date']) >= week_start) & 
                (pd.to_datetime(airport_data['flight_date']) <= week_end)
            ]
            
            if len(week_data) > 0:
                # 使用第一条记录获取该周的排班计划
                sample_record = week_data.iloc[0]
                
                schedule_plan = {}
                for weekday in range(7):  # 0=Monday, 6=Sunday
                    schedule_col = self.schedule_columns[weekday]
                    if schedule_col in sample_record:
                        has_schedule = '有排班' in str(sample_record[schedule_col])
                    else:
                        # 如果没有排班字段，根据该天是否有实际数据判断
                        day_date = week_start + timedelta(days=weekday)
                        day_data = airport_data[pd.to_datetime(airport_data['flight_date']) == day_date]
                        has_schedule = len(day_data) > 0
                    
                    schedule_plan[weekday] = has_schedule
                
                weekly_schedules[week_num] = {
                    'week_start': week_start,
                    'week_end': week_end,
                    'schedule_plan': schedule_plan,
                    'scheduled_days': sum(schedule_plan.values()),
                    'has_schedule_data': True
                }
            else:
                # 该周没有任何数据
                weekly_schedules[week_num] = {
                    'week_start': week_start,
                    'week_end': week_end,
                    'schedule_plan': {},
                    'scheduled_days': 0,
                    'has_schedule_data': False
                }
        
        return weekly_schedules
    
    def calculate_daily_parameters(self, airport_data):
        """计算每日参数"""
        daily_stats = []
        
        if len(airport_data) == 0 or 'flight_date' not in airport_data.columns:
            return pd.DataFrame()
        
        grouped = airport_data.groupby('flight_date')
        
        for date, day_data in grouped:
            if pd.isna(date):
                continue
                
            day_params = {
                'date': pd.to_datetime(date),
                'weekday': pd.to_datetime(date).weekday(),
                'flight_count': len(day_data)
            }
            
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
                            day_params[f'{param}_mean'] = np.nan
                            day_params[f'{param}_sum'] = np.nan
                            day_params[f'{param}_std'] = np.nan
                    except Exception as e:
                        self.logger.warning(f"Could not process parameter {param}: {str(e)}")
                        day_params[f'{param}_mean'] = np.nan
                        day_params[f'{param}_sum'] = np.nan
                        day_params[f'{param}_std'] = np.nan
            
            daily_stats.append(day_params)
        
        return pd.DataFrame(daily_stats)
    
    def calculate_weekly_parameters_with_correct_schedule(self, airport_data):
        """基于正确的排班逻辑计算周度参数"""
        weekly_schedules = self.extract_weekly_schedule_plan(airport_data)
        daily_data = self.calculate_daily_parameters(airport_data)
        
        weekly_results = []
        
        for week_num, schedule_info in weekly_schedules.items():
            week_start = schedule_info['week_start']
            week_end = schedule_info['week_end']
            schedule_plan = schedule_info['schedule_plan']
            
            if not schedule_info['has_schedule_data']:
                # 该周没有排班数据，需要用最近的周代替
                nearest_week_data = self.find_nearest_schedule_week(week_num, weekly_schedules, daily_data)
                if nearest_week_data is not None:
                    week_params = nearest_week_data.copy()
                    week_params['week_number'] = week_num
                    week_params['week_start'] = week_start
                    week_params['week_end'] = week_end
                    week_params['is_estimated'] = True
                    weekly_results.append(week_params)
                continue
            
            # 该周有排班数据，按排班计划计算
            week_params = {
                'week_number': week_num,
                'week_start': week_start,
                'week_end': week_end,
                'scheduled_days': schedule_info['scheduled_days'],
                'is_estimated': False
            }
            
            # 收集该周有排班的日子的数据
            scheduled_day_data = []
            for weekday in range(7):
                if schedule_plan.get(weekday, False):  # 该天有排班
                    day_date = week_start + timedelta(days=weekday)
                    day_data = daily_data[daily_data['date'] == day_date]
                    
                    if len(day_data) > 0:
                        # 有实际数据
                        scheduled_day_data.append(day_data.iloc[0])
                    else:
                        # 有排班但没有实际数据，需要估算
                        estimated_day = self.estimate_missing_day_data(day_date, daily_data)
                        if estimated_day is not None:
                            scheduled_day_data.append(estimated_day)
            
            # 基于有排班的日子计算周度参数
            if len(scheduled_day_data) > 0:
                scheduled_df = pd.DataFrame(scheduled_day_data)
                
                total_flights = scheduled_df['flight_count'].sum()
                week_params['total_flights'] = total_flights
                week_params['avg_daily_flights'] = total_flights / schedule_info['scheduled_days'] if schedule_info['scheduled_days'] > 0 else 0
                week_params['actual_data_days'] = len([d for d in scheduled_day_data if not d.get('estimated', False)])
                
                # 计算各项参数的周度值
                for param in self.parameter_columns:
                    mean_col = f'{param}_mean'
                    sum_col = f'{param}_sum'
                    
                    if mean_col in scheduled_df.columns:
                        valid_means = scheduled_df[mean_col].dropna()
                        valid_sums = scheduled_df[sum_col].dropna()
                        
                        if len(valid_means) > 0:
                            week_params[f'weekly_{param}_avg'] = valid_means.mean()
                            week_params[f'weekly_{param}_total'] = valid_sums.sum()
                            week_params[f'weekly_{param}_std'] = valid_means.std() if len(valid_means) > 1 else 0
                            week_params[f'weekly_{param}_min'] = valid_means.min()
                            week_params[f'weekly_{param}_max'] = valid_means.max()
                        else:
                            week_params[f'weekly_{param}_avg'] = 0
                            week_params[f'weekly_{param}_total'] = 0
                            week_params[f'weekly_{param}_std'] = 0
                            week_params[f'weekly_{param}_min'] = 0
                            week_params[f'weekly_{param}_max'] = 0
            
            weekly_results.append(week_params)
        
        return pd.DataFrame(weekly_results)
    
    def estimate_missing_day_data(self, target_date, daily_data):
        """为有排班但无数据的日期估算参数"""
        target_weekday = target_date.weekday()
        
        # 优先使用同一星期几的数据
        same_weekday_data = daily_data[daily_data['weekday'] == target_weekday]
        
        if len(same_weekday_data) > 0:
            # 使用同星期几的平均值
            estimated_data = same_weekday_data.mean(numeric_only=True).to_dict()
            estimated_data['date'] = target_date
            estimated_data['weekday'] = target_weekday
            estimated_data['estimated'] = True
            estimated_data['estimation_method'] = f'same_weekday_{target_weekday}'
            return estimated_data
        
        # 如果没有同星期几的数据，使用最近日期的数据
        if len(daily_data) > 0:
            distances = np.abs((daily_data['date'] - target_date).dt.days)
            nearest_idx = distances.idxmin()
            nearest_data = daily_data.loc[nearest_idx].to_dict()
            nearest_data['date'] = target_date
            nearest_data['weekday'] = target_weekday
            nearest_data['estimated'] = True
            nearest_data['estimation_method'] = f'nearest_date_{distances.min()}_days'
            return nearest_data
        
        return None
    
    def find_nearest_schedule_week(self, target_week_num, weekly_schedules, daily_data):
        """寻找最近的有排班数据的周"""
        distances = []
        
        for week_num, schedule_info in weekly_schedules.items():
            if schedule_info['has_schedule_data'] and week_num != target_week_num:
                distance = abs(week_num - target_week_num)
                distances.append((distance, week_num))
        
        if distances:
            distances.sort()
            nearest_week_num = distances[0][1]
            
            self.logger.info(f"Using week {nearest_week_num} schedule for week {target_week_num}")
            
            # 递归计算最近周的参数（如果还没计算过）
            nearest_schedule = weekly_schedules[nearest_week_num]
            # 这里简化处理，返回基本结构
            return {
                'scheduled_days': nearest_schedule['scheduled_days'],
                'source_week': nearest_week_num
            }
        
        return None
    
    def process_all_airports_with_correct_schedule(self, data_loader):
        """处理所有机场的正确排班计算"""
        airports = data_loader.get_unique_airports()
        all_results = {}
        
        for airport in airports:
            self.logger.info(f"Processing airport with correct schedule logic: {airport}")
            airport_data = data_loader.filter_by_airport(airport)
            
            if airport_data is not None and len(airport_data) > 0:
                weekly_params = self.calculate_weekly_parameters_with_correct_schedule(airport_data)
                weekly_params['airport'] = airport
                all_results[airport] = weekly_params
                
                # 输出排班统计信息
                self.log_schedule_statistics(airport, airport_data)
            else:
                self.logger.warning(f"No data found for airport: {airport}")
        
        return all_results
    
    def log_schedule_statistics(self, airport, airport_data):
        """记录排班统计信息"""
        weekly_schedules = self.extract_weekly_schedule_plan(airport_data)
        
        total_weeks = len(weekly_schedules)
        weeks_with_schedule = sum(1 for s in weekly_schedules.values() if s['has_schedule_data'])
        total_scheduled_days = sum(s['scheduled_days'] for s in weekly_schedules.values() if s['has_schedule_data'])
        
        self.logger.info(f"{airport} 排班统计:")
        self.logger.info(f"  总周数: {total_weeks}")
        self.logger.info(f"  有排班数据周数: {weeks_with_schedule}")
        self.logger.info(f"  排班覆盖率: {weeks_with_schedule/total_weeks*100:.1f}%")
        self.logger.info(f"  总排班天数: {total_scheduled_days}")
        self.logger.info(f"  平均每周排班天数: {total_scheduled_days/weeks_with_schedule:.1f}" if weeks_with_schedule > 0 else "  平均每周排班天数: 0")