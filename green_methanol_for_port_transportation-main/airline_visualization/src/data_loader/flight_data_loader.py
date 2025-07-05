"""
航班数据加载器
用于从Excel文件中读取航班数据并进行预处理
"""

import pandas as pd
import numpy as np
import os
from typing import Optional, Dict, List, Tuple
import logging

class FlightDataLoader:
    """
    航班数据加载器类
    """
    
    def __init__(self, data_file_path: str = None):
        """
        初始化数据加载器
        
        Args:
            data_file_path: 数据文件路径
        """
        self.data_file_path = data_file_path or "../air_port_data_process/data/22年1月1日至24年12月31日航班数据.xlsx"
        self.logger = logging.getLogger(__name__)
        self.raw_data = None
        self.processed_data = None
        
    def load_raw_data(self, sample_size: Optional[int] = None) -> pd.DataFrame:
        """
        加载原始数据
        
        Args:
            sample_size: 样本大小，如果为None则加载全部数据
            
        Returns:
            原始数据DataFrame
        """
        try:
            if not os.path.exists(self.data_file_path):
                raise FileNotFoundError(f"数据文件不存在: {self.data_file_path}")
            
            self.logger.info(f"开始加载数据文件: {self.data_file_path}")
            
            if sample_size:
                self.raw_data = pd.read_excel(self.data_file_path, nrows=sample_size)
                self.logger.info(f"已加载样本数据，数量: {len(self.raw_data)} 条")
            else:
                self.raw_data = pd.read_excel(self.data_file_path)
                self.logger.info(f"已加载全部数据，数量: {len(self.raw_data)} 条")
            
            return self.raw_data
            
        except Exception as e:
            self.logger.error(f"加载数据失败: {e}")
            raise
    
    def clean_and_validate_data(self) -> pd.DataFrame:
        """
        清洗和验证数据
        
        Returns:
            清洗后的数据DataFrame
        """
        if self.raw_data is None:
            raise ValueError("请先加载原始数据")
        
        self.logger.info("开始清洗和验证数据...")
        
        # 创建数据副本
        cleaned_data = self.raw_data.copy()
        
        # 检查必要字段
        required_fields = ['出发城市x', '出发城市y', '到达城市x', '到达城市y', 
                          '起飞机场x', '起飞机场y', '降落机场x', '降落机场y',
                          '里程（公里）', '机型', '人数', '出发城市', '到达城市']
        
        missing_fields = [field for field in required_fields if field not in cleaned_data.columns]
        if missing_fields:
            raise ValueError(f"缺少必要字段: {missing_fields}")
        
        # 删除坐标为空的记录
        coordinate_fields = ['出发城市x', '出发城市y', '到达城市x', '到达城市y']
        cleaned_data = cleaned_data.dropna(subset=coordinate_fields)
        
        # 删除里程为0或负数的记录
        cleaned_data = cleaned_data[cleaned_data['里程（公里）'] > 0]
        
        # 删除人数为0或负数的记录
        cleaned_data = cleaned_data[cleaned_data['人数'] > 0]
        
        # 验证坐标范围（中国境内大概范围）
        # 经度范围: 73°-135°E, 纬度范围: 18°-54°N
        cleaned_data = cleaned_data[
            (cleaned_data['出发城市x'] >= 70) & (cleaned_data['出发城市x'] <= 140) &
            (cleaned_data['出发城市y'] >= 15) & (cleaned_data['出发城市y'] <= 60) &
            (cleaned_data['到达城市x'] >= 70) & (cleaned_data['到达城市x'] <= 140) &
            (cleaned_data['到达城市y'] >= 15) & (cleaned_data['到达城市y'] <= 60)
        ]
        
        self.logger.info(f"数据清洗完成，保留记录: {len(cleaned_data)} 条")
        return cleaned_data
    
    def prepare_for_visualization(self, data: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        """
        为可视化准备数据
        
        Args:
            data: 清洗后的数据
            
        Returns:
            包含不同类型可视化数据的字典
        """
        self.logger.info("准备可视化数据...")
        
        # 1. 航线数据（用于绘制航线）
        routes_data = pd.DataFrame({
            'start_lon': data['出发城市x'],
            'start_lat': data['出发城市y'],
            'end_lon': data['到达城市x'],
            'end_lat': data['到达城市y'],
            'start_city': data['出发城市'],
            'end_city': data['到达城市'],
            'distance': data['里程（公里）'],
            'passengers': data['人数'],
            'aircraft_type': data['机型'],
            'airline': data.get('航空公司', ''),
            'flight_number': data.get('航班班次', ''),
            'price': data.get('价格(元)', 0)
        })
        
        # 2. 机场数据（用于绘制机场点）
        airports_departure = pd.DataFrame({
            'lon': data['起飞机场x'],
            'lat': data['起飞机场y'],
            'airport_name': data['起飞机场'],
            'city': data['出发城市'],
            'type': 'departure'
        })
        
        airports_arrival = pd.DataFrame({
            'lon': data['降落机场x'],
            'lat': data['降落机场y'],
            'airport_name': data['降落机场'],
            'city': data['到达城市'],
            'type': 'arrival'
        })
        
        # 合并机场数据并去重
        airports_data = pd.concat([airports_departure, airports_arrival], ignore_index=True)
        airports_data = airports_data.drop_duplicates(subset=['lon', 'lat', 'airport_name'])
        
        # 统计每个机场的航班数量
        airport_stats = data.groupby(['起飞机场', '起飞机场x', '起飞机场y']).size().reset_index(name='flight_count')
        airport_stats.columns = ['airport_name', 'lon', 'lat', 'flight_count']
        
        arrival_stats = data.groupby(['降落机场', '降落机场x', '降落机场y']).size().reset_index(name='arrival_count')
        arrival_stats.columns = ['airport_name', 'lon', 'lat', 'arrival_count']
        
        # 合并统计数据
        airport_stats = airport_stats.merge(arrival_stats, on=['airport_name', 'lon', 'lat'], how='outer').fillna(0)
        airport_stats['total_flights'] = airport_stats['flight_count'] + airport_stats['arrival_count']
        
        # 3. 城市数据（用于绘制城市热力图）
        cities_departure = data.groupby(['出发城市', '出发城市x', '出发城市y']).agg({
            '人数': 'sum',
            '里程（公里）': 'sum'
        }).reset_index()
        cities_departure.columns = ['city', 'lon', 'lat', 'total_passengers', 'total_distance']
        cities_departure['type'] = 'departure'
        
        cities_arrival = data.groupby(['到达城市', '到达城市x', '到达城市y']).agg({
            '人数': 'sum',
            '里程（公里）': 'sum'
        }).reset_index()
        cities_arrival.columns = ['city', 'lon', 'lat', 'total_passengers', 'total_distance']
        cities_arrival['type'] = 'arrival'
        
        # 合并城市数据
        cities_data = pd.concat([cities_departure, cities_arrival], ignore_index=True)
        cities_data = cities_data.groupby(['city', 'lon', 'lat']).agg({
            'total_passengers': 'sum',
            'total_distance': 'sum'
        }).reset_index()
        
        # 4. 机型统计数据
        aircraft_stats = data.groupby('机型').agg({
            '人数': ['count', 'sum', 'mean'],
            '里程（公里）': ['sum', 'mean'],
            '价格(元)': 'mean'
        }).reset_index()
        
        # 展平列名
        aircraft_stats.columns = ['aircraft_type', 'flight_count', 'total_passengers', 'avg_passengers',
                                 'total_distance', 'avg_distance', 'avg_price']
        
        self.processed_data = {
            'routes': routes_data,
            'airports': airports_data,
            'airport_stats': airport_stats,
            'cities': cities_data,
            'aircraft_stats': aircraft_stats,
            'raw_cleaned': data
        }
        
        self.logger.info("可视化数据准备完成")
        return self.processed_data
    
    def get_data_summary(self) -> Dict:
        """
        获取数据摘要信息
        
        Returns:
            数据摘要字典
        """
        if self.processed_data is None:
            raise ValueError("请先处理数据")
        
        routes_data = self.processed_data['routes']
        cities_data = self.processed_data['cities']
        aircraft_stats = self.processed_data['aircraft_stats']
        
        summary = {
            'total_routes': len(routes_data),
            'total_cities': len(cities_data),
            'total_passengers': routes_data['passengers'].sum(),
            'total_distance': routes_data['distance'].sum(),
            'aircraft_types': len(aircraft_stats),
            'avg_route_distance': routes_data['distance'].mean(),
            'avg_passengers_per_flight': routes_data['passengers'].mean(),
            'coordinate_bounds': {
                'min_lon': min(routes_data['start_lon'].min(), routes_data['end_lon'].min()),
                'max_lon': max(routes_data['start_lon'].max(), routes_data['end_lon'].max()),
                'min_lat': min(routes_data['start_lat'].min(), routes_data['end_lat'].min()),
                'max_lat': max(routes_data['start_lat'].max(), routes_data['end_lat'].max())
            }
        }
        
        return summary 