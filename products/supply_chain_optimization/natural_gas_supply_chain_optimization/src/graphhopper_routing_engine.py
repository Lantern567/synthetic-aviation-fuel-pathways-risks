"""
GraphHopper路径规划引擎
使用本地OSM数据和GraphHopper服务进行路径规划
"""

import requests
import json
import logging
import os
import sqlite3
import time
from typing import Dict, List, Tuple, Optional, Union
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import hashlib

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GraphHopperRoutingEngine:
    """
    基于GraphHopper的路径规划引擎
    
    功能:
    1. 使用本地OSM数据文件启动GraphHopper服务
    2. 通过HTTP API调用GraphHopper进行路径规划
    3. 计算真实道路距离和预估行驶时间
    4. 缓存路径规划结果
    5. 保存完整的路径坐标信息
    """
    
    def __init__(self, 
                 osm_pbf_path: str = "data/china-latest.osm.pbf",
                 graphhopper_host: str = "localhost",
                 graphhopper_port: int = 8989,
                 cache_dir: str = "cache/graphhopper_routes",
                 max_retries: int = 3,
                 request_timeout: int = 30,
                 enable_cache: bool = True):
        """
        初始化GraphHopper路径规划引擎
        
        Args:
            osm_pbf_path: OSM数据文件路径
            graphhopper_host: GraphHopper服务主机地址
            graphhopper_port: GraphHopper服务端口
            cache_dir: 缓存目录
            max_retries: 最大重试次数
            request_timeout: 请求超时时间(秒)
            enable_cache: 是否启用缓存
        """
        self.osm_pbf_path = osm_pbf_path
        self.graphhopper_host = graphhopper_host
        self.graphhopper_port = graphhopper_port
        self.base_url = f"http://{graphhopper_host}:{graphhopper_port}"
        self.cache_dir = cache_dir
        self.max_retries = max_retries
        self.request_timeout = request_timeout
        self.enable_cache = enable_cache
        
        # 创建缓存目录
        os.makedirs(cache_dir, exist_ok=True)
        
        # 初始化缓存数据库
        if enable_cache:
            self.cache_db_path = os.path.join(cache_dir, "route_cache.db")
            self._init_cache_db()
        
        # 统计信息
        self.stats = {
            'total_requests': 0,
            'cache_hits': 0,
            'api_calls': 0,
            'failed_requests': 0,
            'total_distance_calculated': 0.0,
            'total_time_calculated': 0.0
        }
        
        logger.info(f"GraphHopper路径规划引擎初始化完成")
        logger.info(f"OSM数据文件: {osm_pbf_path}")
        logger.info(f"服务地址: {self.base_url}")
        logger.info(f"缓存目录: {cache_dir}")
        logger.info(f"缓存启用: {enable_cache}")
    
    def _init_cache_db(self):
        """初始化缓存数据库"""
        try:
            conn = sqlite3.connect(self.cache_db_path)
            cursor = conn.cursor()
            
            # 创建路径缓存表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS route_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_lat REAL NOT NULL,
                    start_lon REAL NOT NULL,
                    end_lat REAL NOT NULL,
                    end_lon REAL NOT NULL,
                    distance_km REAL,
                    time_hours REAL,
                    route_coordinates TEXT,
                    vehicle_type TEXT DEFAULT 'car',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    cache_key TEXT UNIQUE
                )
            ''')
            
            # 创建索引
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_cache_key ON route_cache(cache_key)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_coordinates ON route_cache(start_lat, start_lon, end_lat, end_lon)
            ''')
            
            conn.commit()
            conn.close()
            logger.info("缓存数据库初始化完成")
        except Exception as e:
            logger.error(f"缓存数据库初始化失败: {e}")
    
    def _generate_cache_key(self, start_lat: float, start_lon: float, 
                           end_lat: float, end_lon: float, vehicle: str = "car") -> str:
        """生成缓存键"""
        key_string = f"{start_lat:.6f},{start_lon:.6f},{end_lat:.6f},{end_lon:.6f},{vehicle}"
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def _get_from_cache(self, cache_key: str) -> Optional[Dict]:
        """从缓存中获取路径数据"""
        if not self.enable_cache:
            return None
            
        try:
            conn = sqlite3.connect(self.cache_db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT distance_km, time_hours, route_coordinates, created_at
                FROM route_cache 
                WHERE cache_key = ?
            ''', (cache_key,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                distance_km, time_hours, route_coordinates_json, created_at = result
                
                # 解析路径坐标
                route_coordinates = None
                if route_coordinates_json:
                    try:
                        route_coordinates = json.loads(route_coordinates_json)
                    except json.JSONDecodeError:
                        route_coordinates = None
                
                self.stats['cache_hits'] += 1
                return {
                    'distance_km': distance_km,
                    'time_hours': time_hours,
                    'route_coordinates': route_coordinates,
                    'route_found': True,
                    'method': 'cache',
                    'cached_at': created_at
                }
        except Exception as e:
            logger.warning(f"缓存读取失败: {e}")
        
        return None
    
    def _save_to_cache(self, cache_key: str, start_lat: float, start_lon: float,
                      end_lat: float, end_lon: float, result: Dict, vehicle: str = "car"):
        """保存路径数据到缓存"""
        if not self.enable_cache or not result.get('route_found'):
            return
            
        try:
            conn = sqlite3.connect(self.cache_db_path)
            cursor = conn.cursor()
            
            # 序列化路径坐标
            route_coordinates_json = None
            if result.get('route_coordinates'):
                route_coordinates_json = json.dumps(result['route_coordinates'])
            
            cursor.execute('''
                INSERT OR REPLACE INTO route_cache 
                (start_lat, start_lon, end_lat, end_lon, distance_km, time_hours, 
                 route_coordinates, vehicle_type, cache_key)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                start_lat, start_lon, end_lat, end_lon,
                result.get('distance_km'), result.get('time_hours'),
                route_coordinates_json, vehicle, cache_key
            ))
            
            conn.commit()
            conn.close()
            logger.debug(f"路径结果已缓存: {cache_key}")
        except Exception as e:
            logger.warning(f"缓存保存失败: {e}")
    
    def check_service_health(self) -> bool:
        """检查GraphHopper服务状态"""
        try:
            health_url = f"{self.base_url}/health"
            response = requests.get(health_url, timeout=5)
            if response.status_code == 200:
                logger.info("GraphHopper服务运行正常")
                return True
            else:
                logger.warning(f"GraphHopper服务返回异常状态码: {response.status_code}")
                return False
        except requests.exceptions.ConnectionError:
            logger.warning(f"无法连接到GraphHopper服务 {self.base_url}")
            logger.info("请确保GraphHopper服务正在运行:")
            logger.info("1. 运行 start_graphhopper.bat 启动服务")
            logger.info("2. 或手动启动: java -jar graphhopper-web-*.jar server config.yml")
            return False
        except requests.exceptions.Timeout:
            logger.warning(f"GraphHopper服务连接超时: {self.base_url}")
            return False
        except Exception as e:
            logger.warning(f"GraphHopper服务健康检查失败: {e}")
            return False
    
    def calculate_route_distance(self, 
                               start_lat: float, start_lon: float,
                               end_lat: float, end_lon: float,
                               vehicle: str = "car",
                               include_route_geometry: bool = True) -> Dict:
        """
        计算两点间的路径距离和行驶时间
        
        Args:
            start_lat: 起点纬度
            start_lon: 起点经度
            end_lat: 终点纬度
            end_lon: 终点经度
            vehicle: 车辆类型 ("car", "truck", "bike", "foot")
            include_route_geometry: 是否包含路径几何信息
            
        Returns:
            Dict包含distance_km, time_hours, route_coordinates, route_found等信息
        """
        self.stats['total_requests'] += 1
        
        # 检查是否是同一点
        if abs(start_lat - end_lat) < 1e-6 and abs(start_lon - end_lon) < 1e-6:
            return {
                'distance_km': 0.0,
                'time_hours': 0.0,
                'route_coordinates': [[start_lon, start_lat]],
                'route_found': True,
                'method': 'same_point'
            }
        
        # 生成缓存键并检查缓存
        cache_key = self._generate_cache_key(start_lat, start_lon, end_lat, end_lon, vehicle)
        cached_result = self._get_from_cache(cache_key)
        if cached_result:
            return cached_result
        
        # 调用GraphHopper API
        for attempt in range(self.max_retries):
            try:
                # 构建请求参数
                # 映射vehicle类型到GraphHopper profile
                profile_map = {
                    'car': 'truck',      # 使用truck profile（我们配置的）
                    'truck': 'truck',
                    'bike': 'truck',     # 备用，使用truck
                    'foot': 'truck'      # 备用，使用truck
                }
                profile = profile_map.get(vehicle, 'truck')
                
                params = {
                    'point': [f'{start_lat},{start_lon}', f'{end_lat},{end_lon}'],
                    'profile': profile,  # 使用profile而不是vehicle
                    'calc_points': include_route_geometry,
                    'instructions': False,  # 不需要导航指令
                    'points_encoded': False  # 使用未编码的坐标
                }
                
                # 发送请求
                route_url = f"{self.base_url}/route"
                response = requests.get(route_url, params=params, timeout=self.request_timeout)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if 'paths' in data and len(data['paths']) > 0:
                        path = data['paths'][0]
                        
                        # 提取距离和时间
                        distance_m = path.get('distance', 0)
                        time_ms = path.get('time', 0)
                        
                        distance_km = distance_m / 1000.0
                        time_hours = time_ms / (1000.0 * 3600.0)
                        
                        # 提取路径坐标
                        route_coordinates = None
                        if include_route_geometry and 'points' in path:
                            points = path['points']
                            if 'coordinates' in points:
                                route_coordinates = points['coordinates']
                        
                        result = {
                            'distance_km': distance_km,
                            'time_hours': time_hours,
                            'route_coordinates': route_coordinates,
                            'route_found': True,
                            'method': 'graphhopper_api',
                            'vehicle': vehicle,
                            'response_time': response.elapsed.total_seconds()
                        }
                        
                        # 更新统计信息
                        self.stats['api_calls'] += 1
                        self.stats['total_distance_calculated'] += distance_km
                        self.stats['total_time_calculated'] += time_hours
                        
                        # 保存到缓存
                        self._save_to_cache(cache_key, start_lat, start_lon, end_lat, end_lon, result, vehicle)
                        
                        return result
                    
                    else:
                        logger.warning("GraphHopper API返回了空的路径结果")
                        
                elif response.status_code == 400:
                    if 'PointNotFoundException' in response.text:
                        logger.info(f"GraphHopper找不到道路点，尝试查找最近道路: 起点({start_lat:.6f},{start_lon:.6f}) 终点({end_lat:.6f},{end_lon:.6f})")
                        # 尝试使用最近道路点进行路径规划
                        nearest_route_result = self._calculate_route_with_nearest_points(start_lat, start_lon, end_lat, end_lon, vehicle, include_route_geometry)
                        if nearest_route_result:
                            return nearest_route_result
                    else:
                        logger.warning(f"GraphHopper API请求参数错误: {response.text}")
                    break  # 参数错误不需要重试
                    
                else:
                    logger.warning(f"GraphHopper API请求失败 (尝试 {attempt + 1}/{self.max_retries}): "
                                 f"状态码 {response.status_code}, 响应: {response.text}")
                
            except requests.exceptions.Timeout:
                logger.warning(f"GraphHopper API请求超时 (尝试 {attempt + 1}/{self.max_retries})")
            except requests.exceptions.ConnectionError:
                logger.warning(f"GraphHopper服务连接失败 (尝试 {attempt + 1}/{self.max_retries})")
            except Exception as e:
                logger.error(f"GraphHopper API调用异常 (尝试 {attempt + 1}/{self.max_retries}): {e}")
            
            # 等待后重试
            if attempt < self.max_retries - 1:
                time.sleep(2 ** attempt)  # 指数退避
        
        # 所有尝试都失败，返回错误结果
        self.stats['failed_requests'] += 1
        
        # 使用直线距离作为后备方案
        haversine_dist = self._calculate_haversine_distance(start_lat, start_lon, end_lat, end_lon)
        return {
            'distance_km': haversine_dist * 1.3,  # 道路系数
            'time_hours': haversine_dist * 1.3 / 60,  # 假设60km/h平均速度
            'route_coordinates': [[start_lon, start_lat], [end_lon, end_lat]],
            'route_found': True,
            'method': 'haversine_fallback',
            'error': 'GraphHopper API调用失败，使用直线距离估算'
        }
    
    def calculate_distance_matrix(self, locations: List[Tuple[float, float]], 
                                location_names: Optional[List[str]] = None,
                                vehicle: str = "car") -> pd.DataFrame:
        """
        计算位置点之间的距离矩阵
        
        Args:
            locations: 位置列表，每个位置为(lat, lon)元组
            location_names: 位置名称列表
            vehicle: 车辆类型
            
        Returns:
            距离矩阵DataFrame
        """
        n_locations = len(locations)
        if location_names is None:
            location_names = [f"Location_{i}" for i in range(n_locations)]
        
        # 创建距离矩阵
        distance_matrix = np.zeros((n_locations, n_locations))
        
        logger.info(f"计算 {n_locations} 个位置的距离矩阵")
        
        for i in range(n_locations):
            for j in range(i, n_locations):
                if i == j:
                    distance_matrix[i][j] = 0.0
                else:
                    result = self.calculate_route_distance(
                        locations[i][0], locations[i][1],
                        locations[j][0], locations[j][1],
                        vehicle=vehicle,
                        include_route_geometry=False  # 矩阵计算不需要路径几何信息
                    )
                    
                    distance = result.get('distance_km', 0)
                    distance_matrix[i][j] = distance
                    distance_matrix[j][i] = distance  # 对称矩阵
                    
                    if not result.get('route_found'):
                        logger.warning(f"路径计算失败: {location_names[i]} -> {location_names[j]}")
        
        # 转换为DataFrame
        df = pd.DataFrame(distance_matrix, index=location_names, columns=location_names)
        return df
    
    def get_route_details(self, 
                         start_lat: float, start_lon: float,
                         end_lat: float, end_lon: float,
                         vehicle: str = "car") -> Dict:
        """
        获取详细的路径信息，包括完整的路径坐标
        
        Args:
            start_lat: 起点纬度
            start_lon: 起点经度
            end_lat: 终点纬度
            end_lon: 终点经度
            vehicle: 车辆类型
            
        Returns:
            包含详细路径信息的字典
        """
        return self.calculate_route_distance(
            start_lat, start_lon, end_lat, end_lon,
            vehicle=vehicle, include_route_geometry=True
        )
    
    def save_route_to_file(self, route_result: Dict, filename: str):
        """
        将路径结果保存到文件
        
        Args:
            route_result: 路径计算结果
            filename: 保存的文件名
        """
        if not route_result.get('route_found'):
            logger.warning("没有有效的路径数据可保存")
            return
        
        try:
            output_dir = os.path.join(self.cache_dir, "saved_routes")
            os.makedirs(output_dir, exist_ok=True)
            
            output_file = os.path.join(output_dir, filename)
            
            # 保存为JSON格式
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(route_result, f, ensure_ascii=False, indent=2)
            
            logger.info(f"路径数据已保存到: {output_file}")
        except Exception as e:
            logger.error(f"保存路径数据失败: {e}")
    
    def _find_nearest_road_point(self, lat: float, lon: float, vehicle: str = "car") -> Optional[Tuple[float, float]]:
        """
        查找最近的道路点
        
        Args:
            lat, lon: 查询点坐标
            vehicle: 车辆类型
            
        Returns:
            最近道路点的坐标(lat, lon)，如果找不到返回None
        """
        try:
            profile_map = {
                'car': 'truck',
                'truck': 'truck', 
                'bike': 'truck',
                'foot': 'truck'
            }
            profile = profile_map.get(vehicle, 'truck')
            
            params = {
                'point': f'{lat},{lon}',
                'profile': profile
            }
            
            nearest_url = f"{self.base_url}/nearest"
            response = requests.get(nearest_url, params=params, timeout=self.request_timeout)
            
            if response.status_code == 200:
                data = response.json()
                if 'coordinates' in data and data['coordinates']:
                    # GraphHopper返回[lon, lat]格式
                    road_lon, road_lat = data['coordinates']
                    logger.debug(f"找到最近道路点: ({road_lat:.6f}, {road_lon:.6f})")
                    return (road_lat, road_lon)
                    
        except Exception as e:
            logger.debug(f"查找最近道路点失败: {e}")
            
        return None
    
    def _calculate_route_with_nearest_points(self, start_lat: float, start_lon: float, 
                                           end_lat: float, end_lon: float, 
                                           vehicle: str = "car", include_route_geometry: bool = True) -> Optional[Dict]:
        """
        通过查找最近道路点来计算路径
        
        Args:
            start_lat, start_lon: 起点坐标
            end_lat, end_lon: 终点坐标
            vehicle: 车辆类型
            include_route_geometry: 是否包含路径几何信息
            
        Returns:
            路径计算结果，如果失败返回None
        """
        try:
            # 查找起点最近的道路点
            start_road_point = self._find_nearest_road_point(start_lat, start_lon, vehicle)
            if not start_road_point:
                logger.debug(f"无法找到起点({start_lat:.6f},{start_lon:.6f})的最近道路")
                return None
                
            # 查找终点最近的道路点
            end_road_point = self._find_nearest_road_point(end_lat, end_lon, vehicle)
            if not end_road_point:
                logger.debug(f"无法找到终点({end_lat:.6f},{end_lon:.6f})的最近道路")
                return None
                
            start_road_lat, start_road_lon = start_road_point
            end_road_lat, end_road_lon = end_road_point
            
            # 计算到最近道路的距离
            start_to_road_dist = self._calculate_haversine_distance(start_lat, start_lon, start_road_lat, start_road_lon)
            road_to_end_dist = self._calculate_haversine_distance(end_road_lat, end_road_lon, end_lat, end_lon)
            
            # 使用道路点进行路径规划
            profile_map = {
                'car': 'truck',
                'truck': 'truck',
                'bike': 'truck',
                'foot': 'truck'
            }
            profile = profile_map.get(vehicle, 'truck')
            
            params = {
                'point': [f'{start_road_lat},{start_road_lon}', f'{end_road_lat},{end_road_lon}'],
                'profile': profile,
                'calc_points': include_route_geometry,
                'instructions': False,
                'points_encoded': False
            }
            
            route_url = f"{self.base_url}/route"
            response = requests.get(route_url, params=params, timeout=self.request_timeout)
            
            if response.status_code == 200:
                data = response.json()
                if 'paths' in data and len(data['paths']) > 0:
                    path = data['paths'][0]
                    
                    # 提取道路距离和时间
                    road_distance_m = path.get('distance', 0)
                    road_time_ms = path.get('time', 0)
                    
                    road_distance_km = road_distance_m / 1000.0
                    road_time_hours = road_time_ms / (1000.0 * 3600.0)
                    
                    # 总距离 = 起点到道路 + 道路距离 + 道路到终点
                    total_distance_km = start_to_road_dist + road_distance_km + road_to_end_dist
                    
                    # 总时间估算（假设接入道路的速度为30km/h）
                    access_time_hours = (start_to_road_dist + road_to_end_dist) / 30.0
                    total_time_hours = access_time_hours + road_time_hours
                    
                    # 构建路径坐标
                    route_coordinates = [[start_lon, start_lat]]
                    if include_route_geometry and 'points' in path and 'coordinates' in path['points']:
                        route_coordinates.extend(path['points']['coordinates'])
                    route_coordinates.append([end_lon, end_lat])
                    
                    logger.info(f"通过最近道路计算路径成功: 总距离{total_distance_km:.1f}km (接入{start_to_road_dist + road_to_end_dist:.1f}km + 道路{road_distance_km:.1f}km)")
                    
                    result = {
                        'distance_km': total_distance_km,
                        'time_hours': total_time_hours,
                        'route_coordinates': route_coordinates,
                        'route_found': True,
                        'method': 'nearest_road_access',
                        'vehicle': vehicle,
                        'start_to_road_km': start_to_road_dist,
                        'road_distance_km': road_distance_km,
                        'road_to_end_km': road_to_end_dist
                    }
                    
                    return result
                    
        except Exception as e:
            logger.debug(f"通过最近道路计算路径失败: {e}")
            
        return None
    
    def _calculate_haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        使用Haversine公式计算两点间的大圆距离
        
        Args:
            lat1, lon1: 起点纬度经度
            lat2, lon2: 终点纬度经度
            
        Returns:
            距离(公里)
        """
        from math import radians, sin, cos, sqrt, atan2
        
        # 转换为弧度
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        
        # Haversine公式
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        # 地球半径(公里)
        R = 6371
        distance = R * c
        
        return distance
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return self.stats.copy()
    
    def clear_cache(self):
        """清理缓存"""
        if self.enable_cache:
            try:
                conn = sqlite3.connect(self.cache_db_path)
                cursor = conn.cursor()
                cursor.execute('DELETE FROM route_cache')
                conn.commit()
                conn.close()
                logger.info("缓存已清理")
            except Exception as e:
                logger.error(f"清理缓存失败: {e}")


class GraphHopperDistanceCalculator:
    """
    GraphHopper距离计算器 - 结合GraphHopper路径规划和直线距离计算
    """
    
    def __init__(self, routing_engine: Optional[GraphHopperRoutingEngine] = None):
        """
        初始化距离计算器
        
        Args:
            routing_engine: GraphHopper路径规划引擎实例
        """
        self.routing_engine = routing_engine or GraphHopperRoutingEngine()
    
    def calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float, 
                         method: str = "graphhopper", vehicle: str = "car") -> float:
        """
        计算两点间距离
        
        Args:
            lat1, lon1: 起点纬度经度
            lat2, lon2: 终点纬度经度
            method: 计算方法 ("graphhopper", "haversine", "euclidean")
            vehicle: 车辆类型 (当method为"graphhopper"时使用)
            
        Returns:
            距离(公里)
        """
        if method == "graphhopper":
            result = self.routing_engine.calculate_route_distance(
                lat1, lon1, lat2, lon2, vehicle=vehicle, include_route_geometry=False
            )
            if result['route_found']:
                return result['distance_km']
            else:
                # 回退到直线距离
                logger.warning("GraphHopper路径计算失败，使用直线距离")
                return self.calculate_haversine_distance(lat1, lon1, lat2, lon2) * 1.3
        
        elif method == "haversine":
            return self.calculate_haversine_distance(lat1, lon1, lat2, lon2)
        
        elif method == "euclidean":
            return self.calculate_euclidean_distance(lat1, lon1, lat2, lon2)
        
        else:
            raise ValueError(f"不支持的计算方法: {method}")
    
    def calculate_haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        使用Haversine公式计算两点间的大圆距离
        """
        return self.routing_engine._calculate_haversine_distance(lat1, lon1, lat2, lon2)
    
    def calculate_euclidean_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        计算两点间的欧几里得距离（近似）
        """
        # 简单的欧几里得距离，1度约等于111公里
        distance = ((lat1 - lat2)**2 + (lon1 - lon2)**2)**0.5 * 111
        return distance


# 为了向后兼容，保持与原有接口一致的类名
DistanceCalculator = GraphHopperDistanceCalculator