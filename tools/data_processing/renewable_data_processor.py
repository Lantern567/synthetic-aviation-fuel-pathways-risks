"""
可再生能源数据处理器
处理太阳能和风能数据，包含地理过滤和缓存功能
"""

import pandas as pd
import numpy as np
import os
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class RenewableDataProcessor:
    """可再生能源数据处理器"""
    
    def __init__(self, total_hours: int = 168, max_distance_km: float = 500):
        """
        初始化处理器
        
        Args:
            total_hours: 需要处理的总小时数
            max_distance_km: 地理过滤的最大距离（公里）
        """
        self.total_hours = total_hours
        self.max_distance_km = max_distance_km
        self.processed_locations = {}
        
    def process_renewable_data(self, renewable_data: pd.DataFrame, 
                             geographic_calculator=None,
                             cache_manager=None) -> Dict[str, Any]:
        """
        处理可再生能源数据（包含太阳能和风能，支持缓存）
        
        Args:
            renewable_data: 可再生能源数据DataFrame
            geographic_calculator: 地理计算器实例
            cache_manager: 缓存管理器实例
            
        Returns:
            Dict: 处理后的位置数据字典
        """
        try:
            # 如果有缓存管理器，尝试使用缓存
            if cache_manager:
                renewable_cache_key = f"renewable_{len(renewable_data)}_{renewable_data['plant_name'].nunique()}"
                temp_renewable_file = f"temp_renewable_{renewable_cache_key}.csv"
                
                # 检查是否有缓存
                if cache_manager.is_cache_valid('renewable_plants', temp_renewable_file):
                    logger.info("使用缓存的可再生能源数据（500km过滤）")
                    cached_df = cache_manager.load_filtered_data('renewable_plants')
                    if cached_df is not None:
                        filtered_renewable_data = cached_df
                        logger.info(f"从缓存加载可再生能源数据: {len(filtered_renewable_data)} 条记录")
                    else:
                        logger.warning("缓存加载失败，执行完整处理")
                        filtered_renewable_data = self._filter_renewable_data(
                            renewable_data, geographic_calculator, cache_manager, temp_renewable_file)
                else:
                    logger.info("缓存无效或不存在，执行完整处理和过滤")
                    filtered_renewable_data = self._filter_renewable_data(
                        renewable_data, geographic_calculator, cache_manager, temp_renewable_file)
            else:
                # 无缓存管理器，直接处理
                filtered_renewable_data = self._filter_renewable_data(
                    renewable_data, geographic_calculator, None, None)
            
            # 按地点聚合小时级发电数据
            locations = {}
            plant_names = filtered_renewable_data['plant_name'].unique()
            for plant_name in plant_names:
                plant_data = filtered_renewable_data[filtered_renewable_data['plant_name'] == plant_name]
                
                # 取前total_hours小时数据
                if len(plant_data) >= self.total_hours:
                    hourly_data = plant_data.head(self.total_hours)
                    
                    # 确定电站类型
                    plant_type = hourly_data.iloc[0]['type'] if 'type' in hourly_data.columns else 'solar_plant'
                    
                    locations[plant_name] = {
                        'type': plant_type,  # 'solar_plant' 或 'wind_farm'
                        'latitude': hourly_data.iloc[0].get('latitude', 30.0),
                        'longitude': hourly_data.iloc[0].get('longitude', 104.0),
                        'capacity_mw': hourly_data.iloc[0]['capacity_mw'] if 'capacity_mw' in hourly_data.columns else hourly_data.iloc[0]['power_output_mw'],
                        'hourly_generation': hourly_data['power_output_mw'].tolist(),  # 每小时发电量 MWh (等价于平均功率 MW)
                    }
            
            logger.info(f"处理了 {len(locations)} 个可再生能源发电站")
            
            # 统计电站类型
            solar_count = sum(1 for loc in locations.values() if loc['type'] == 'solar_plant')
            wind_count = sum(1 for loc in locations.values() if loc['type'] == 'wind_farm')
            logger.info(f"  太阳能发电站: {solar_count} 个")
            logger.info(f"  风电场: {wind_count} 个")
            
            self.processed_locations = locations
            return locations
            
        except Exception as e:
            logger.error(f"处理可再生能源数据失败: {e}")
            # 降级到原有处理方法
            return self._process_renewable_data_fallback(renewable_data, geographic_calculator)
    
    def _filter_renewable_data(self, renewable_data: pd.DataFrame, 
                              geographic_calculator=None,
                              cache_manager=None, 
                              temp_file: Optional[str] = None) -> pd.DataFrame:
        """
        过滤可再生能源数据（指定范围内）
        
        Args:
            renewable_data: 原始可再生能源数据
            geographic_calculator: 地理计算器实例
            cache_manager: 缓存管理器实例
            temp_file: 临时文件名（用于缓存）
            
        Returns:
            pd.DataFrame: 过滤后的数据
        """
        logger.info(f"过滤可再生能源数据: {len(renewable_data)} 条原始记录")
        
        # 按电站分组过滤
        filtered_plants = []
        for plant_name in renewable_data['plant_name'].unique():
            plant_data = renewable_data[renewable_data['plant_name'] == plant_name]
            
            if len(plant_data) > 0:
                # 获取电站坐标（使用第一行数据）
                plant_lat = plant_data.iloc[0].get('latitude', 30.0)
                plant_lon = plant_data.iloc[0].get('longitude', 104.0)
                
                # 检查坐标是否在指定范围内
                if geographic_calculator:
                    is_in_range = geographic_calculator.is_within_beijing_range(
                        plant_lat, plant_lon, self.max_distance_km)
                else:
                    # 简单距离检查作为备用
                    from shared.utils.geographic_calculator import GeographicCalculator
                    is_in_range = GeographicCalculator.is_within_beijing_range(
                        plant_lat, plant_lon, self.max_distance_km)
                
                if is_in_range:
                    filtered_plants.append(plant_data)
                else:
                    if geographic_calculator:
                        distance = geographic_calculator.calculate_distance_km(
                            plant_lat, plant_lon, 39.9042, 116.4074)
                    else:
                        from shared.utils.geographic_calculator import GeographicCalculator
                        distance = GeographicCalculator.calculate_distance_km(
                            plant_lat, plant_lon, 39.9042, 116.4074)
                    logger.debug(f"可再生能源电站 {plant_name} 距离北京 {distance:.1f}km，超出{self.max_distance_km}km范围，跳过")
        
        # 合并过滤后的数据
        if filtered_plants:
            filtered_df = pd.concat(filtered_plants, ignore_index=True)
        else:
            filtered_df = pd.DataFrame()
        
        logger.info(f"{self.max_distance_km}km范围内的可再生能源数据: {len(filtered_df)} 条记录，{filtered_df['plant_name'].nunique() if len(filtered_df) > 0 else 0} 个电站")
        
        # 保存到缓存
        if cache_manager and len(filtered_df) > 0 and temp_file:
            cache_manager.save_filtered_data('renewable_plants', filtered_df, temp_file)
        
        return filtered_df
    
    def _process_renewable_data_fallback(self, renewable_data: pd.DataFrame, 
                                       geographic_calculator=None) -> Dict[str, Any]:
        """
        处理可再生能源数据的降级方法（原有逻辑）
        
        Args:
            renewable_data: 原始可再生能源数据
            geographic_calculator: 地理计算器实例
            
        Returns:
            Dict: 处理后的位置数据字典
        """
        logger.warning("使用降级方法处理可再生能源数据")
        
        locations = {}
        
        # 按地点聚合小时级发电数据
        for plant_name in renewable_data['plant_name'].unique():
            plant_data = renewable_data[renewable_data['plant_name'] == plant_name]
            
            # 取前total_hours小时数据
            if len(plant_data) >= self.total_hours:
                hourly_data = plant_data.head(self.total_hours)
                
                # 检查坐标是否在指定范围内
                plant_lat = hourly_data.iloc[0].get('latitude', 30.0)
                plant_lon = hourly_data.iloc[0].get('longitude', 104.0)
                
                if geographic_calculator:
                    is_in_range = geographic_calculator.is_within_beijing_range(
                        plant_lat, plant_lon, self.max_distance_km)
                    distance = geographic_calculator.calculate_distance_km(
                        plant_lat, plant_lon, 39.9042, 116.4074)
                else:
                    from shared.utils.geographic_calculator import GeographicCalculator
                    is_in_range = GeographicCalculator.is_within_beijing_range(
                        plant_lat, plant_lon, self.max_distance_km)
                    distance = GeographicCalculator.calculate_distance_km(
                        plant_lat, plant_lon, 39.9042, 116.4074)
                
                if not is_in_range:
                    logger.info(f"可再生能源电站 {plant_name} 距离北京 {distance:.1f}km，超出{self.max_distance_km}km范围，跳过")
                    continue
                
                # 确定电站类型
                plant_type = hourly_data.iloc[0]['type'] if 'type' in hourly_data.columns else 'solar_plant'
                
                locations[plant_name] = {
                    'type': plant_type,  # 'solar_plant' 或 'wind_farm'
                    'latitude': hourly_data.iloc[0].get('latitude', 30.0),
                    'longitude': hourly_data.iloc[0].get('longitude', 104.0),
                    'capacity_mw': hourly_data.iloc[0]['capacity_mw'] if 'capacity_mw' in hourly_data.columns else hourly_data.iloc[0]['power_output_mw'],
                    'hourly_generation': hourly_data['power_output_mw'].tolist(),  # 每小时发电量 MWh (等价于平均功率 MW)
                }
        
        logger.info(f"处理了 {len(locations)} 个可再生能源发电站（降级方法）")
        
        # 统计电站类型
        solar_count = sum(1 for loc in locations.values() if loc['type'] == 'solar_plant')
        wind_count = sum(1 for loc in locations.values() if loc['type'] == 'wind_farm')
        logger.info(f"  太阳能发电站: {solar_count} 个")
        logger.info(f"  风电场: {wind_count} 个")
        
        self.processed_locations = locations
        return locations
    
    def add_airports_to_locations(self, locations: Dict[str, Any], airports: Dict[str, Any]) -> Dict[str, Any]:
        """
        将机场位置添加到基础locations字典中，使其可以用于决策变量
        
        Args:
            locations: 现有的位置字典
            airports: 机场数据字典
            
        Returns:
            Dict: 更新后的位置字典
        """
        if airports:
            for airport_name, airport_info in airports.items():
                # 使用机场名称作为位置标识符
                location_id = f"airport_{airport_name}"
                
                # 添加到基础locations字典
                locations[location_id] = {
                    'type': 'airport',  # 新的位置类型
                    'latitude': airport_info['latitude'],
                    'longitude': airport_info['longitude'],
                    'capacity_mw': 0,  # 机场本身不发电
                    'hourly_generation': [0] * self.total_hours,  # 无发电
                    'original_airport_name': airport_name,  # 保留原始机场名称
                    'fuel_demand_weekly': airport_info.get('weekly_fuel_series', [])
                }
            
            airport_count = sum(1 for loc in locations.values() if loc['type'] == 'airport')
            logger.info(f"  添加了 {airport_count} 个机场位置到基础locations中")
        else:
            logger.warning("机场数据尚未加载，无法添加机场位置")
        
        return locations
    
    def add_lng_terminals_to_locations(self, locations: Dict[str, Any], lng_terminals: Dict[str, Any]) -> Dict[str, Any]:
        """
        将LNG接收站位置添加到基础locations字典中，使其可以用于决策变量
        
        Args:
            locations: 现有的位置字典
            lng_terminals: LNG接收站数据字典
            
        Returns:
            Dict: 更新后的位置字典
        """
        if lng_terminals:
            for terminal_id, terminal_info in lng_terminals.items():
                # 使用LNG接收站标识符作为位置标识符
                location_id = f"lng_{terminal_id}"
                
                # 检查坐标有效性
                lat = terminal_info.get('lat', None)
                lon = terminal_info.get('lon', None)
                
                if lat is None or lon is None or pd.isna(lat) or pd.isna(lon):
                    logger.error(f"LNG终端 {terminal_id} 缺少有效坐标信息，跳过")
                    continue
                
                try:
                    lat = float(lat)
                    lon = float(lon)
                except (ValueError, TypeError):
                    logger.error(f"LNG终端 {terminal_id} 坐标转换失败，跳过")
                    continue
                
                # 添加到基础locations字典
                locations[location_id] = {
                    'type': 'lng_terminal',  # 新的位置类型
                    'latitude': lat,
                    'longitude': lon,
                    'capacity_mw': 0,  # LNG接收站本身不发电
                    'hourly_generation': [0] * self.total_hours,  # 无发电
                    'original_terminal_id': terminal_id,  # 保留原始终端ID
                    'capacity_mcm_per_year': terminal_info.get('capacity_mcm_per_year', 1000)
                }
            
            lng_count = sum(1 for loc in locations.values() if loc['type'] == 'lng_terminal')
            logger.info(f"  添加了 {lng_count} 个LNG接收站位置到基础locations中")
        else:
            logger.warning("LNG接收站数据尚未加载，无法添加LNG位置")
        
        return locations