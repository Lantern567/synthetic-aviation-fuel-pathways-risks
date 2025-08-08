"""
地理计算工具类
提供距离计算和坐标验证等地理相关功能
"""

from math import radians, sin, cos, sqrt, atan2
from typing import Tuple
import logging

logger = logging.getLogger(__name__)


class GeographicCalculator:
    """地理计算工具类"""
    
    # 地球半径(公里)
    EARTH_RADIUS_KM = 6371
    
    # 北京市中心坐标（天安门）
    BEIJING_CENTER_LAT = 39.9042
    BEIJING_CENTER_LON = 116.4074
    
    @staticmethod
    def calculate_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        计算两点间的Haversine距离（公里）
        
        Args:
            lat1, lon1: 第一个点的纬度经度
            lat2, lon2: 第二个点的纬度经度
            
        Returns:
            float: 距离（公里）
        """
        # 转换为弧度
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        
        # Haversine公式
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        distance = GeographicCalculator.EARTH_RADIUS_KM * c
        
        return distance
    
    @classmethod
    def is_within_beijing_range(cls, lat: float, lon: float, max_distance_km: float = 500) -> bool:
        """
        检查坐标是否在北京指定范围内
        
        Args:
            lat, lon: 检查点的纬度经度
            max_distance_km: 最大距离（公里），默认500公里
            
        Returns:
            bool: 是否在范围内
        """
        distance = cls.calculate_distance_km(lat, lon, cls.BEIJING_CENTER_LAT, cls.BEIJING_CENTER_LON)
        return distance <= max_distance_km
    
    @staticmethod
    def validate_coordinates(lat: float, lon: float) -> bool:
        """
        验证坐标是否有效
        
        Args:
            lat: 纬度
            lon: 经度
            
        Returns:
            bool: 坐标是否有效
        """
        return -90 <= lat <= 90 and -180 <= lon <= 180
    
    @classmethod
    def get_coordinate_bounds(cls, coordinates_list: list) -> dict:
        """
        获取坐标列表的边界
        
        Args:
            coordinates_list: 坐标列表，每个元素为(lat, lon)
            
        Returns:
            dict: 包含min_lat, max_lat, min_lon, max_lon的边界信息
        """
        if not coordinates_list:
            return {}
            
        lats = [coord[0] for coord in coordinates_list]
        lons = [coord[1] for coord in coordinates_list]
        
        return {
            'min_lat': min(lats),
            'max_lat': max(lats),
            'min_lon': min(lons),
            'max_lon': max(lons)
        }