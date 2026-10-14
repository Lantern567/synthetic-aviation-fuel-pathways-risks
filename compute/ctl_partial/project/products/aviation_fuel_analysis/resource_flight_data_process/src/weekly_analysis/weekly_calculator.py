import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

class WeeklyParameterCalculator:
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
    
    def calculate_daily_parameters(self, airport_data):
        daily_stats = []
        
        if len(airport_data) == 0 or 'flight_date' not in airport_data.columns:
            return pd.DataFrame()
        
        grouped = airport_data.groupby('flight_date')
        
        for date, day_data in grouped:
            if pd.isna(date):
                continue
                
            day_params = {
                'date': date,
                'flight_count': len(day_data),
                'has_scheduled_flights': True
            }
            
            for param in self.parameter_columns:
                if param in day_data.columns:
                    try:
                        # Try to convert to numeric, skip if conversion fails
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
    
    def find_nearest_week_data(self, target_week, daily_data, weeks):
        target_start = target_week['week_start']
        target_end = target_week['week_end']
        
        scheduled_days = daily_data[
            (daily_data['date'] >= target_start) & 
            (daily_data['date'] <= target_end)
        ]
        
        if len(scheduled_days) > 0:
            return scheduled_days, target_week['week_number']
        
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
    
    def calculate_weekly_parameters(self, airport_data):
        weeks = self.generate_2024_weeks()
        daily_data = self.calculate_daily_parameters(airport_data)
        
        weekly_results = []
        
        for week in weeks:
            week_data, source_week = self.find_nearest_week_data(week, daily_data, weeks)
            
            if len(week_data) == 0:
                self.logger.warning(f"No data available for week {week['week_number']}")
                continue
            
            week_params = {
                'week_number': week['week_number'],
                'week_start': week['week_start'],
                'week_end': week['week_end'],
                'source_week': source_week,
                'days_with_data': len(week_data),
                'total_flights': week_data['flight_count'].sum(),
                'avg_daily_flights': week_data['flight_count'].mean()
            }
            
            for param in self.parameter_columns:
                mean_col = f'{param}_mean'
                sum_col = f'{param}_sum'
                std_col = f'{param}_std'
                
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
    
    def process_all_airports(self, data_loader):
        airports = data_loader.get_unique_airports()
        all_results = {}
        
        for airport in airports:
            self.logger.info(f"Processing airport: {airport}")
            airport_data = data_loader.filter_by_airport(airport)
            
            if airport_data is not None and len(airport_data) > 0:
                weekly_params = self.calculate_weekly_parameters(airport_data)
                weekly_params['airport'] = airport
                all_results[airport] = weekly_params
            else:
                self.logger.warning(f"No data found for airport: {airport}")
        
        return all_results