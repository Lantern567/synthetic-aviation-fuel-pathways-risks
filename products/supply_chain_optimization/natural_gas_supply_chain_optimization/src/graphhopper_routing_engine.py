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
from multiprocessing import Pool, cpu_count
from functools import partial

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
            'total_time_calculated': 0.0,
            # 方法使用统计
            'method_usage': {
                'direct_api': 0,        # 第1层：直接API成功
                'mixed_route': 0,       # 第2层：混合路径（网格搜索）
                'method_failures': 0    # 方法失败计数
            }
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

        # 坐标验证
        if not self._validate_coordinates(start_lat, start_lon, end_lat, end_lon):
            error_msg = f"无效的坐标输入: 起点({start_lat}, {start_lon}), 终点({end_lat}, {end_lon})"
            logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)

        # 服务状态检查（仅在第一次调用时检查）
        if self.stats['total_requests'] == 1:
            logger.info("🔍 检查GraphHopper服务状态...")
            if not self.check_service_health():
                error_msg = "GraphHopper服务不可用，请检查服务是否正在运行"
                logger.error(f"❌ {error_msg}")
                raise ConnectionError(error_msg)
            logger.info("✅ GraphHopper服务状态正常")

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
                    'ch.disable': 'true',  # 禁用快速算法，提高偏远点成功率
                    'calc_points': include_route_geometry,
                    'instructions': False,  # 不需要导航指令
                    'points_encoded': False,  # 使用未编码的坐标
                    'locale': 'zh_CN',  # 中文地区设置，改善中国路网质量
                    'optimize': 'true',  # 启用路径优化
                    'elevation': 'false'  # 禁用高程数据减少响应时间
                }
                
                # 发送请求 - 添加详细调试信息
                route_url = f"{self.base_url}/route"

                # 详细记录API请求信息
                logger.info(f"=== GraphHopper API请求调试 (尝试 {attempt + 1}/{self.max_retries}) ===")
                logger.info(f"请求URL: {route_url}")
                logger.info(f"请求参数详情:")
                for key, value in params.items():
                    logger.info(f"  {key}: {value}")
                logger.info(f"起点坐标: ({start_lat:.6f}, {start_lon:.6f})")
                logger.info(f"终点坐标: ({end_lat:.6f}, {end_lon:.6f})")
                logger.info(f"车辆类型: {vehicle} -> profile: {profile}")
                logger.info(f"请求超时设置: {self.request_timeout}秒")

                response = requests.get(route_url, params=params, timeout=self.request_timeout)

                # 详细记录响应信息
                logger.info(f"HTTP响应状态码: {response.status_code}")
                logger.info(f"响应头信息: {dict(response.headers)}")
                logger.info(f"响应时间: {response.elapsed.total_seconds():.3f}秒")
                
                if response.status_code == 200:
                    # 成功响应处理
                    try:
                        data = response.json()
                        logger.info(f"✅ JSON响应解析成功")
                        logger.info(f"响应数据结构: {list(data.keys()) if isinstance(data, dict) else type(data)}")

                        if isinstance(data, dict):
                            logger.info(f"响应包含字段: {list(data.keys())}")

                            # 检查和记录 snapped_waypoints 信息
                            if 'snapped_waypoints' in data:
                                snapped = data['snapped_waypoints']
                                logger.info(f"✨ 发现snapped_waypoints数据: {type(snapped)}")
                                if isinstance(snapped, dict) and 'coordinates' in snapped:
                                    coords = snapped['coordinates']
                                    logger.info(f"✨ 吸附坐标数量: {len(coords) if coords else 0}")
                                    if coords and len(coords) >= 2:
                                        start_snapped = coords[0]
                                        end_snapped = coords[-1]
                                        logger.info(f"✨ 吸附起点: ({start_snapped[1]:.6f}, {start_snapped[0]:.6f})")
                                        logger.info(f"✨ 吸附终点: ({end_snapped[1]:.6f}, {end_snapped[0]:.6f})")

                                        # 计算吸附距离
                                        start_snap_dist = self._calculate_haversine_distance(
                                            start_lat, start_lon, start_snapped[1], start_snapped[0]
                                        )
                                        end_snap_dist = self._calculate_haversine_distance(
                                            end_lat, end_lon, end_snapped[1], end_snapped[0]
                                        )
                                        logger.info(f"✨ 起点吸附距离: {start_snap_dist:.3f}km")
                                        logger.info(f"✨ 终点吸附距离: {end_snap_dist:.3f}km")
                                else:
                                    logger.info(f"✨ snapped_waypoints数据格式: {snapped}")
                            else:
                                logger.info(f"🔍 响应中没有snapped_waypoints字段")

                            if 'paths' in data:
                                paths_count = len(data['paths']) if data['paths'] else 0
                                logger.info(f"找到路径数量: {paths_count}")
                                if paths_count > 0:
                                    path = data['paths'][0]
                                    logger.info(f"第一条路径字段: {list(path.keys())}")
                                    logger.info(f"路径距离: {path.get('distance', 'N/A')}米")
                                    logger.info(f"路径时间: {path.get('time', 'N/A')}毫秒")

                                    # 检查path内的snapped_waypoints
                                    if 'snapped_waypoints' in path:
                                        path_snapped = path['snapped_waypoints']
                                        logger.info(f"✨ 路径内snapped_waypoints: {type(path_snapped)}")
                                        if isinstance(path_snapped, dict) and 'coordinates' in path_snapped:
                                            path_coords = path_snapped['coordinates']
                                            logger.info(f"✨ 路径内吸附坐标数量: {len(path_coords) if path_coords else 0}")
                            else:
                                logger.warning(f"响应中缺少'paths'字段")

                        # 保存完整响应用于调试（仅在调试级别为DEBUG时）
                        if logger.isEnabledFor(logging.DEBUG):
                            logger.debug(f"完整API响应: {json.dumps(data, indent=2, ensure_ascii=False)}")

                    except json.JSONDecodeError as e:
                        logger.error(f"❌ JSON响应解析失败: {e}")
                        logger.error(f"原始响应内容: {response.text[:1000]}...")
                        continue
                    
                    if 'paths' in data and len(data['paths']) > 0:
                        path = data['paths'][0]
                        
                        # 提取距离和时间
                        distance_m = path.get('distance', 0)
                        time_ms = path.get('time', 0)
                        
                        distance_km = distance_m / 1000.0
                        time_hours = time_ms / (1000.0 * 3600.0)
                        
                        # 提取路径坐标 - 增强版本支持多种响应格式
                        route_coordinates = None
                        if include_route_geometry:
                            # 尝试多种方式提取路径坐标
                            coordinate_sources = []

                            # 方式1: 检查path.points.coordinates (GeoJSON格式)
                            if 'points' in path:
                                points = path['points']
                                if isinstance(points, dict) and 'coordinates' in points:
                                    coordinate_sources.append(('points.coordinates', points['coordinates']))
                                elif isinstance(points, list):
                                    coordinate_sources.append(('points直接列表', points))

                            # 方式2: 检查path.geometry.coordinates (备用GeoJSON格式)
                            if 'geometry' in path:
                                geometry = path['geometry']
                                if isinstance(geometry, dict) and 'coordinates' in geometry:
                                    coordinate_sources.append(('geometry.coordinates', geometry['coordinates']))

                            # 方式3: 检查path.snapped_waypoints (吸附点格式)
                            if 'snapped_waypoints' in path:
                                snapped = path['snapped_waypoints']
                                if isinstance(snapped, dict) and 'coordinates' in snapped:
                                    coordinate_sources.append(('snapped_waypoints.coordinates', snapped['coordinates']))

                            # 尝试使用找到的坐标源
                            for source_name, coords in coordinate_sources:
                                if coords and len(coords) > 0:
                                    route_coordinates = coords
                                    logger.debug(f"成功从{source_name}解析坐标: 数量={len(route_coordinates)}")
                                    break

                            # 如果所有方式都失败，生成基本的起终点坐标
                            if not route_coordinates:
                                logger.warning("所有坐标解析方式都失败，生成基本起终点坐标")
                                route_coordinates = [[start_lon, start_lat], [end_lon, end_lat]]
                                logger.warning(f"完整路径响应: {json.dumps(path, indent=2, ensure_ascii=False)}")
                        else:
                            # 不请求坐标时，提供基本的起终点
                            route_coordinates = [[start_lon, start_lat], [end_lon, end_lat]]
                        
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
                        # 方法使用统计：直接API成功
                        self.stats['method_usage']['direct_api'] += 1
                        
                        # 保存到缓存
                        self._save_to_cache(cache_key, start_lat, start_lon, end_lat, end_lon, result, vehicle)
                        
                        return result
                    
                    else:
                        logger.warning("GraphHopper API返回了空的路径结果")
                        
                elif response.status_code == 400:
                    # 详细分析400错误
                    logger.error(f"❌ GraphHopper API返回400错误")
                    logger.error(f"完整错误响应: {response.text}")

                    if 'PointNotFoundException' in response.text:
                        logger.error(f"🔍 检测到PointNotFoundException - 无法找到道路点")
                        logger.error(f"问题坐标 - 起点: ({start_lat:.6f},{start_lon:.6f})")
                        logger.error(f"问题坐标 - 终点: ({end_lat:.6f},{end_lon:.6f})")
                        logger.error(f"当前ch.disable设置: {params.get('ch.disable', '未设置')}")
                        logger.error(f"当前snap_prevention设置: {params.get('snap_prevention', '未设置')}")

                        logger.info(f"🔄 尝试使用混合路径计算方法...")
                        logger.info(f"ℹ️ 这将通过网格搜索找到道路点，然后计算混合路径")
                        try:
                            mixed_route_result = self._calculate_mixed_route(start_lat, start_lon, end_lat, end_lon, vehicle, include_route_geometry)
                            logger.info(f"✅ 混合路径计算方法成功")
                            # 方法使用统计：混合路径成功
                            self.stats['method_usage']['mixed_route'] += 1
                            return mixed_route_result
                        except Exception as mixed_error:
                            logger.error(f"❌ 混合路径计算方法也失败: {mixed_error}")
                            logger.error(f"混合路径错误类型: {type(mixed_error).__name__}")

                            # 混合方法失败后，不再有其他后备方案，直接失败
                            logger.error(f"❌ 混合路径计算失败，没有更多后备方案")
                            break  # 直接跳出重试循环
                    else:
                        logger.error(f"❌ 其他400错误 (非PointNotFoundException)")
                        logger.error(f"错误内容: {response.text}")
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
        
        # 所有尝试都失败，直接抛出错误而不使用直线距离后备方案
        self.stats['failed_requests'] += 1
        self.stats['method_usage']['method_failures'] += 1

        error_msg = (
            f"GraphHopper路径规划完全失败: "
            f"起点({start_lat:.6f},{start_lon:.6f}) -> 终点({end_lat:.6f},{end_lon:.6f}), "
            f"尝试次数: {self.max_retries}, "
            f"车辆类型: {vehicle}"
        )
        logger.error(error_msg)
        raise Exception(error_msg)
    
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

    def calculate_distance_matrix_parallel(self, locations: List[Tuple[float, float]],
                                          location_names: Optional[List[str]] = None,
                                          vehicle: str = "car", max_workers: int = 14) -> pd.DataFrame:
        """
        并行计算位置点之间的距离矩阵（使用多核处理）

        Args:
            locations: 位置列表，每个位置为(lat, lon)元组
            location_names: 位置名称列表
            vehicle: 车辆类型
            max_workers: 最大并行工作进程数（默认14核）

        Returns:
            距离矩阵DataFrame
        """
        n_locations = len(locations)
        if location_names is None:
            location_names = [f"Location_{i}" for i in range(n_locations)]

        # 创建需要计算的任务列表（只计算上三角，因为矩阵是对称的）
        tasks = []
        for i in range(n_locations):
            for j in range(i + 1, n_locations):  # 只计算i < j的情况
                tasks.append((i, j, locations[i], locations[j]))

        logger.info(f"并行计算 {n_locations} 个位置的距离矩阵，使用 {max_workers} 个进程")
        logger.info(f"总计算任务数: {len(tasks)} 个（利用矩阵对称性）")

        # 创建距离矩阵
        distance_matrix = np.zeros((n_locations, n_locations))

        # 设置对角线为0
        for i in range(n_locations):
            distance_matrix[i][i] = 0.0

        if len(tasks) == 0:
            # 只有一个位置的情况
            df = pd.DataFrame(distance_matrix, index=location_names, columns=location_names)
            return df

        # 使用进程池并行计算
        try:
            with Pool(processes=min(max_workers, len(tasks), cpu_count())) as pool:
                # 创建部分函数，固定vehicle参数
                compute_func = partial(self._compute_single_distance, vehicle=vehicle)

                # 并行计算所有距离
                results = pool.map(compute_func, tasks)

                # 填充距离矩阵
                for task_idx, (i, j, _, _) in enumerate(tasks):
                    distance = results[task_idx]
                    distance_matrix[i][j] = distance
                    distance_matrix[j][i] = distance  # 对称矩阵

                    if distance == 0 and i != j:  # 可能是计算失败
                        logger.warning(f"路径计算可能失败: {location_names[i]} -> {location_names[j]}")

                logger.info(f"✅ 并行距离矩阵计算完成")

        except Exception as e:
            logger.error(f"❌ 并行计算失败，回退到串行计算: {e}")
            # 回退到串行计算
            return self.calculate_distance_matrix(locations, location_names, vehicle)

        # 转换为DataFrame
        df = pd.DataFrame(distance_matrix, index=location_names, columns=location_names)
        return df

    @staticmethod
    def _compute_single_distance(task_data: Tuple[int, int, Tuple[float, float], Tuple[float, float]],
                                vehicle: str = "car") -> float:
        """
        计算单个位置对的距离（用于并行处理）

        Args:
            task_data: (i, j, location_i, location_j) 元组
            vehicle: 车辆类型

        Returns:
            距离（km）
        """
        i, j, loc_i, loc_j = task_data

        # 为每个进程创建新的GraphHopper引擎实例
        # 注意：这是必要的，因为multiprocessing无法共享类实例
        engine = GraphHopperRoutingEngine(enable_cache=False)  # 并行计算时禁用缓存以避免冲突

        try:
            result = engine.calculate_route_distance(
                loc_i[0], loc_i[1],  # start_lat, start_lon
                loc_j[0], loc_j[1],  # end_lat, end_lon
                vehicle=vehicle,
                include_route_geometry=False  # 矩阵计算不需要路径几何信息
            )

            distance = result.get('distance_km', 0)
            return distance

        except Exception as e:
            logger.warning(f"位置对 ({i},{j}) 距离计算失败: {e}")
            return 0.0  # 返回0表示计算失败
    
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
                'profile': profile,
                'ch.disable': 'true',  # 禁用快速算法，提高偏远点成功率
                'locale': 'zh_CN'  # 中文地区设置
            }

            # 详细记录最近道路点查找请求
            logger.info(f"=== 查找最近道路点 API调试 ===")
            logger.info(f"查询坐标: ({lat:.6f}, {lon:.6f})")
            logger.info(f"车辆类型: {vehicle} -> profile: {profile}")
            logger.info(f"请求参数:")
            for key, value in params.items():
                logger.info(f"  {key}: {value}")

            nearest_url = f"{self.base_url}/nearest"
            logger.info(f"请求URL: {nearest_url}")

            response = requests.get(nearest_url, params=params, timeout=self.request_timeout)

            # 详细记录响应信息
            logger.info(f"HTTP响应状态码: {response.status_code}")
            logger.info(f"响应时间: {response.elapsed.total_seconds():.3f}秒")

            if response.status_code == 200:
                try:
                    data = response.json()
                    logger.info(f"✅ JSON响应解析成功")
                    logger.info(f"响应数据结构: {list(data.keys()) if isinstance(data, dict) else type(data)}")

                    # 保存完整响应用于调试
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug(f"完整nearest API响应: {json.dumps(data, indent=2, ensure_ascii=False)}")

                    if 'coordinates' in data and data['coordinates']:
                        # GraphHopper返回[lon, lat]格式
                        road_lon, road_lat = data['coordinates']
                        logger.info(f"✅ 找到最近道路点: ({road_lat:.6f}, {road_lon:.6f})")

                        # 计算距离差
                        distance_diff = ((lat - road_lat)**2 + (lon - road_lon)**2)**0.5 * 111  # 大概转换为km
                        logger.info(f"原始点与道路点距离差: {distance_diff:.2f}km")

                        if 'distance' in data:
                            logger.info(f"GraphHopper报告的精确距离: {data['distance']:.2f}米")

                        return (road_lat, road_lon)
                    else:
                        logger.warning(f"❌ 响应中没有找到坐标信息")
                        logger.warning(f"响应内容: {data}")
                        return None

                except json.JSONDecodeError as e:
                    logger.error(f"❌ nearest API JSON响应解析失败: {e}")
                    logger.error(f"原始响应内容: {response.text[:1000]}...")
                    return None
            else:
                logger.error(f"❌ nearest API请求失败: 状态码 {response.status_code}")
                logger.error(f"错误响应: {response.text}")

                # 如果direct nearest搜索失败，尝试网格搜索
                logger.info(f"🔄 direct nearest失败，尝试网格搜索...")
                grid_result = self._grid_search_nearest_road(lat, lon, vehicle)
                if grid_result:
                    logger.info(f"✅ 网格搜索成功找到道路点: ({grid_result[0]:.6f}, {grid_result[1]:.6f})")
                    return grid_result
                else:
                    logger.error(f"❌ 网格搜索也失败")
                    return None

        except Exception as e:
            logger.error(f"❌ 查找最近道路点异常: {e}")
            logger.error(f"异常类型: {type(e).__name__}")

            # 异常情况下也尝试网格搜索
            logger.info(f"🔄 异常情况下尝试网格搜索...")
            try:
                grid_result = self._grid_search_nearest_road(lat, lon, vehicle)
                if grid_result:
                    logger.info(f"✅ 网格搜索成功找到道路点: ({grid_result[0]:.6f}, {grid_result[1]:.6f})")
                    return grid_result
            except Exception as grid_error:
                logger.error(f"❌ 网格搜索也发生异常: {grid_error}")

        return None

    def _grid_search_nearest_road(self, lat: float, lon: float, vehicle: str = "car", max_radius_km: float = 50.0) -> Optional[Tuple[float, float]]:
        """
        使用网格搜索算法查找最近的可用道路点

        Args:
            lat, lon: 查询点坐标
            vehicle: 车辆类型
            max_radius_km: 最大搜索半径(公里)

        Returns:
            最近道路点的坐标(lat, lon)，如果找不到返回None
        """
        try:
            logger.info(f"🔍 开始{int(max_radius_km)}km网格搜索最近道路点: ({lat:.6f}, {lon:.6f})")

            # 定义搜索层级和网格密度（随最大半径自适应扩展）
            search_layers = [
                {"radius_km": 2, "grid_size": 3, "step_km": 1.5},      # 第1层：2km内，3×3网格
                {"radius_km": 5, "grid_size": 5, "step_km": 2.0},      # 第2层：5km内，5×5网格
                {"radius_km": 10, "grid_size": 7, "step_km": 3.0},     # 第3层：10km内，7×7网格
            ]
            if max_radius_km >= 20:
                search_layers.append({"radius_km": 20, "grid_size": 11, "step_km": 4.0})  # 第4层：20km内
            if max_radius_km >= 30:
                search_layers.append({"radius_km": 30, "grid_size": 13, "step_km": 5.0})  # 第5层：30km内
            if max_radius_km >= 40:
                search_layers.append({"radius_km": 40, "grid_size": 15, "step_km": 6.0})  # 第6层：40km内
            if max_radius_km >= 50:
                search_layers.append({"radius_km": 50, "grid_size": 17, "step_km": 7.0})  # 第7层：50km内

            best_road_point = None
            best_distance = float('inf')
            total_attempts = 0

            for layer_idx, layer in enumerate(search_layers):
                logger.info(f"🔍 搜索第{layer_idx + 1}层: 半径{layer['radius_km']}km, 网格{layer['grid_size']}×{layer['grid_size']}")

                radius_km = layer["radius_km"]
                grid_size = layer["grid_size"]
                step_km = layer["step_km"]

                # 将公里转换为大概的度数 (1度约等于111km)
                step_deg = step_km / 111.0

                # 生成网格搜索点
                grid_points = []
                center_offset = (grid_size - 1) // 2

                for i in range(grid_size):
                    for j in range(grid_size):
                        # 计算网格点相对于中心的偏移
                        lat_offset = (i - center_offset) * step_deg
                        lon_offset = (j - center_offset) * step_deg

                        search_lat = lat + lat_offset
                        search_lon = lon + lon_offset

                        # 检查是否在搜索半径内
                        distance_to_center = self._calculate_haversine_distance(lat, lon, search_lat, search_lon)
                        if distance_to_center <= radius_km:
                            grid_points.append((search_lat, search_lon, distance_to_center))

                # 按距离排序，优先搜索离原点近的
                grid_points.sort(key=lambda x: x[2])

                logger.info(f"📍 第{layer_idx + 1}层生成{len(grid_points)}个搜索点")

                # 逐个测试网格点
                for grid_lat, grid_lon, dist_to_center in grid_points:
                    total_attempts += 1

                    try:
                        # 调用GraphHopper nearest API
                        profile_map = {
                            'car': 'truck',
                            'truck': 'truck',
                            'bike': 'truck',
                            'foot': 'truck'
                        }
                        profile = profile_map.get(vehicle, 'truck')

                        params = {
                            'point': f'{grid_lat},{grid_lon}',
                            'profile': profile,
                            'ch.disable': 'true',
                            'locale': 'zh_CN'
                        }

                        nearest_url = f"{self.base_url}/nearest"
                        response = requests.get(nearest_url, params=params, timeout=10)

                        if response.status_code == 200:
                            data = response.json()
                            if 'coordinates' in data and data['coordinates']:
                                # 找到道路点
                                road_lon, road_lat = data['coordinates']

                                # 计算从原始点到道路点的真实距离
                                real_distance = self._calculate_haversine_distance(lat, lon, road_lat, road_lon)

                                logger.info(f"✅ 网格点({grid_lat:.4f}, {grid_lon:.4f})找到道路: ({road_lat:.6f}, {road_lon:.6f})")
                                logger.info(f"   原始点到道路距离: {real_distance:.3f}km")

                                # 更新最佳道路点
                                if real_distance < best_distance:
                                    best_distance = real_distance
                                    best_road_point = (road_lat, road_lon)
                                    logger.info(f"🎯 更新最佳道路点: 距离{best_distance:.3f}km")

                                # 如果找到足够近的点，可以提前返回
                                if real_distance < 2.0:  # 距离小于2km时提前返回
                                    logger.info(f"🎯 找到足够近的道路点，提前返回: {real_distance:.3f}km")
                                    return best_road_point

                        # 控制请求频率，避免过于频繁的API调用
                        if total_attempts % 10 == 0:
                            import time
                            time.sleep(0.1)  # 每10次请求后短暂暂停

                    except Exception as grid_error:
                        logger.debug(f"网格点({grid_lat:.4f}, {grid_lon:.4f})查询失败: {grid_error}")
                        continue

                # 如果在当前层找到了道路点，评估是否足够好
                if best_road_point and best_distance < radius_km * 0.8:
                    logger.info(f"✅ 在第{layer_idx + 1}层找到满意的道路点: 距离{best_distance:.3f}km")
                    break

                logger.info(f"第{layer_idx + 1}层搜索完成，当前最佳距离: {best_distance:.3f}km")

            if best_road_point:
                logger.info(f"🎯 网格搜索成功! 总尝试{total_attempts}次")
                logger.info(f"🎯 最终道路点: ({best_road_point[0]:.6f}, {best_road_point[1]:.6f})")
                logger.info(f"🎯 最终距离: {best_distance:.3f}km")
                return best_road_point
            else:
                logger.warning(f"❌ 网格搜索失败! 在{max_radius_km}km范围内未找到任何道路点")
                logger.warning(f"❌ 总共尝试了{total_attempts}个网格点")
                return None

        except Exception as e:
            logger.error(f"❌ 网格搜索异常: {e}")
            logger.error(f"异常类型: {type(e).__name__}")
            return None


    def _calculate_mixed_route(self, start_lat: float, start_lon: float,
                              end_lat: float, end_lon: float,
                              vehicle: str = "car", include_route_geometry: bool = True) -> Dict:
        """
        使用混合方法计算路径：直线距离 + 道路距离 + 直线距离

        当GraphHopper无法直接进行路径规划时，使用此方法:
        1. 通过网格搜索找到起点和终点的最近道路点
        2. 计算: 起点→起点道路 + 道路网络路径 + 终点道路→终点
        3. 生成完整的路径坐标

        Args:
            start_lat, start_lon: 起点坐标
            end_lat, end_lon: 终点坐标
            vehicle: 车辆类型
            include_route_geometry: 是否包含路径几何信息

        Returns:
            路径计算结果字典
        """
        try:
            logger.info(f"🚗 开始混合路径计算: ({start_lat:.6f},{start_lon:.6f}) -> ({end_lat:.6f},{end_lon:.6f})")

            # 1. 通过网格搜索找到起点最近道路
            logger.info(f"🔍 查找起点最近道路点...")
            start_road_point = self._grid_search_nearest_road(start_lat, start_lon, vehicle, max_radius_km=50.0)
            if not start_road_point:
                # 如果网格搜索失败，直接抛出异常
                error_msg = f"起点网格搜索失败: 无法在50km范围内找到起点({start_lat:.6f},{start_lon:.6f})的道路点"
                logger.error(f"❌ {error_msg}")
                raise Exception(error_msg)

            start_road_lat, start_road_lon = start_road_point
            logger.info(f"✅ 起点道路点: ({start_road_lat:.6f}, {start_road_lon:.6f})")

            # 2. 通过网格搜索找到终点最近道路
            logger.info(f"🔍 查找终点最近道路点...")
            end_road_point = self._grid_search_nearest_road(end_lat, end_lon, vehicle, max_radius_km=50.0)
            if not end_road_point:
                # 如果网格搜索失败，直接抛出异常
                error_msg = f"终点网格搜索失败: 无法在50km范围内找到终点({end_lat:.6f},{end_lon:.6f})的道路点"
                logger.error(f"❌ {error_msg}")
                raise Exception(error_msg)

            end_road_lat, end_road_lon = end_road_point
            logger.info(f"✅ 终点道路点: ({end_road_lat:.6f}, {end_road_lon:.6f})")

            # 3. 计算各段距离
            # 起点到起点道路的直线距离
            start_to_road_km = self._calculate_haversine_distance(start_lat, start_lon, start_road_lat, start_road_lon)
            # 终点道路到终点的直线距离
            road_to_end_km = self._calculate_haversine_distance(end_road_lat, end_road_lon, end_lat, end_lon)

            logger.info(f"📏 起点接入距离: {start_to_road_km:.3f}km")
            logger.info(f"📏 终点接出距离: {road_to_end_km:.3f}km")

            # 4. 计算道路网络距离 (道路点之间)
            logger.info(f"🛣️ 计算道路网络距离...")
            road_distance_km = 0.0
            road_time_hours = 0.0
            road_coordinates = []

            try:
                # 尝试在道路点之间进行路径规划
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
                    'ch.disable': 'true',
                    'calc_points': include_route_geometry,
                    'instructions': False,
                    'points_encoded': False,
                    'locale': 'zh_CN',
                    'optimize': 'true',
                    'elevation': 'false'
                }

                route_url = f"{self.base_url}/route"
                response = requests.get(route_url, params=params, timeout=self.request_timeout)

                if response.status_code == 200:
                    data = response.json()
                    if 'paths' in data and len(data['paths']) > 0:
                        path = data['paths'][0]
                        road_distance_km = path.get('distance', 0) / 1000.0
                        road_time_hours = path.get('time', 0) / (1000.0 * 3600.0)

                        # 提取道路路径坐标
                        if include_route_geometry:
                            if 'points' in path:
                                points = path['points']
                                if isinstance(points, dict) and 'coordinates' in points:
                                    road_coordinates = points['coordinates']
                                elif isinstance(points, list):
                                    road_coordinates = points

                        logger.info(f"✅ 道路网络距离: {road_distance_km:.3f}km")
                        logger.info(f"✅ 道路网络时间: {road_time_hours:.3f}小时")

                    else:
                        logger.warning(f"⚠️ 道路路径规划失败，使用直线距离估算")
                        road_distance_km = self._calculate_haversine_distance(start_road_lat, start_road_lon, end_road_lat, end_road_lon)
                        road_time_hours = road_distance_km / 60.0  # 假设60km/h平均速度

                else:
                    logger.warning(f"⚠️ 道路路径API失败，使用直线距离估算")
                    road_distance_km = self._calculate_haversine_distance(start_road_lat, start_road_lon, end_road_lat, end_road_lon)
                    road_time_hours = road_distance_km / 60.0

            except Exception as road_error:
                logger.warning(f"⚠️ 道路路径计算异常: {road_error}")
                road_distance_km = self._calculate_haversine_distance(start_road_lat, start_road_lon, end_road_lat, end_road_lon)
                road_time_hours = road_distance_km / 60.0

            # 5. 计算总距离和时间
            total_distance_km = start_to_road_km + road_distance_km + road_to_end_km

            # 估算接入和接出的时间（假设30km/h的接入速度）
            access_time_hours = (start_to_road_km + road_to_end_km) / 30.0
            total_time_hours = access_time_hours + road_time_hours

            logger.info(f"📊 混合路径计算结果:")
            logger.info(f"   接入距离: {start_to_road_km:.3f}km")
            logger.info(f"   道路距离: {road_distance_km:.3f}km")
            logger.info(f"   接出距离: {road_to_end_km:.3f}km")
            logger.info(f"   总距离: {total_distance_km:.3f}km")
            logger.info(f"   总时间: {total_time_hours:.3f}小时")

            # 6. 生成完整路径坐标
            route_coordinates = [[start_lon, start_lat]]

            if include_route_geometry:
                # 添加起点道路点
                route_coordinates.append([start_road_lon, start_road_lat])

                # 添加道路网络的详细坐标
                if road_coordinates:
                    route_coordinates.extend(road_coordinates)
                else:
                    # 如果没有详细坐标，生成简化路径
                    mid_points = self._generate_fallback_route_coordinates(
                        start_road_lat, start_road_lon, end_road_lat, end_road_lon
                    )[1:-1]  # 排除起终点
                    route_coordinates.extend(mid_points)

                # 添加终点道路点
                route_coordinates.append([end_road_lon, end_road_lat])

            # 添加最终终点
            route_coordinates.append([end_lon, end_lat])

            # 7. 构建结果
            result = {
                'distance_km': total_distance_km,
                'time_hours': total_time_hours,
                'route_coordinates': route_coordinates,
                'route_found': True,
                'method': 'mixed_grid_search',
                'vehicle': vehicle,
                'start_to_road_km': start_to_road_km,
                'road_distance_km': road_distance_km,
                'road_to_end_km': road_to_end_km,
                'start_road_point': start_road_point,
                'end_road_point': end_road_point
            }

            logger.info(f"✅ 混合路径计算完成: 总距离 {total_distance_km:.3f}km")
            return result

        except Exception as e:
            logger.error(f"❌ 混合路径计算异常: {e}")
            logger.error(f"异常类型: {type(e).__name__}")
            # 重新抛出异常，不使用后备方案
            raise

    
    def _generate_fallback_route_coordinates(self, start_lat: float, start_lon: float,
                                           end_lat: float, end_lon: float) -> List[List[float]]:
        """
        生成后备路径坐标，创建一个简化的多点路径

        Args:
            start_lat, start_lon: 起点坐标
            end_lat, end_lon: 终点坐标

        Returns:
            路径坐标列表 [[lon, lat], ...]
        """
        # 基本起终点
        coordinates = [[start_lon, start_lat]]

        # 计算距离，如果距离较远，添加中间点以模拟真实路径
        distance = self._calculate_haversine_distance(start_lat, start_lon, end_lat, end_lon)

        if distance > 50:  # 距离超过50km时添加中间点
            # 计算中间点数量（每50km一个点）
            num_intermediate = min(int(distance / 50), 10)  # 最多10个中间点

            for i in range(1, num_intermediate + 1):
                # 线性插值计算中间点
                ratio = i / (num_intermediate + 1)
                mid_lat = start_lat + (end_lat - start_lat) * ratio
                mid_lon = start_lon + (end_lon - start_lon) * ratio

                # 添加小的随机偏移以模拟真实道路的弯曲（最大0.01度约1km）
                import random
                offset_lat = (random.random() - 0.5) * 0.01
                offset_lon = (random.random() - 0.5) * 0.01

                coordinates.append([mid_lon + offset_lon, mid_lat + offset_lat])

        # 添加终点
        coordinates.append([end_lon, end_lat])

        return coordinates

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

    def get_method_usage_report(self) -> str:
        """获取方法使用统计报告"""
        method_stats = self.stats['method_usage']
        total_successful = method_stats['direct_api'] + method_stats['mixed_route']
        total_attempts = total_successful + method_stats['method_failures']

        if total_attempts == 0:
            return "暂无路径计算请求统计"

        # 计算百分比
        direct_api_percent = (method_stats['direct_api'] / total_attempts) * 100
        mixed_route_percent = (method_stats['mixed_route'] / total_attempts) * 100
        failure_percent = (method_stats['method_failures'] / total_attempts) * 100

        report = f"""
=== 路径计算方法使用统计报告 ===
📊 总计算请求: {total_attempts}次
✅ 成功计算: {total_successful}次 ({(total_successful/total_attempts)*100:.1f}%)
❌ 失败计算: {method_stats['method_failures']}次 ({failure_percent:.1f}%)

📈 方法使用详情:
🎯 第1层（直接API）: {method_stats['direct_api']}次 ({direct_api_percent:.1f}%)
🔀 第2层（混合路径）: {method_stats['mixed_route']}次 ({mixed_route_percent:.1f}%)

💡 统计说明:
• 第1层：GraphHopper API直接成功
• 第2层：通过20km网格搜索+混合路径计算
• 失败：所有方法都无法找到有效路径
"""
        return report

    def _validate_coordinates(self, start_lat: float, start_lon: float,
                             end_lat: float, end_lon: float) -> bool:
        """
        验证坐标的有效性

        Args:
            start_lat, start_lon: 起点坐标
            end_lat, end_lon: 终点坐标

        Returns:
            bool: 坐标是否有效
        """
        try:
            # 检查纬度范围 [-90, 90]
            if not (-90 <= start_lat <= 90) or not (-90 <= end_lat <= 90):
                logger.error(f"纬度超出有效范围[-90,90]: 起点纬度{start_lat}, 终点纬度{end_lat}")
                return False

            # 检查经度范围 [-180, 180]
            if not (-180 <= start_lon <= 180) or not (-180 <= end_lon <= 180):
                logger.error(f"经度超出有效范围[-180,180]: 起点经度{start_lon}, 终点经度{end_lon}")
                return False

            # 检查是否为数字
            if not all(isinstance(coord, (int, float)) for coord in [start_lat, start_lon, end_lat, end_lon]):
                logger.error(f"坐标必须为数字: 起点({start_lat}, {start_lon}), 终点({end_lat}, {end_lon})")
                return False

            # 检查是否为NaN或无穷大
            import math
            coords = [start_lat, start_lon, end_lat, end_lon]
            if any(math.isnan(coord) or math.isinf(coord) for coord in coords):
                logger.error(f"坐标包含NaN或无穷大值: 起点({start_lat}, {start_lon}), 终点({end_lat}, {end_lon})")
                return False

            # 特别检查中国境内坐标（推荐范围，但不强制）
            # 中国大致范围: 纬度 18-54, 经度 73-135
            china_lat_range = (18, 54)
            china_lon_range = (73, 135)

            coords_in_china = (
                china_lat_range[0] <= start_lat <= china_lat_range[1] and
                china_lon_range[0] <= start_lon <= china_lon_range[1] and
                china_lat_range[0] <= end_lat <= china_lat_range[1] and
                china_lon_range[0] <= end_lon <= china_lon_range[1]
            )

            if not coords_in_china:
                logger.warning(f"坐标可能超出中国境内范围（但仍会继续处理）:")
                logger.warning(f"  起点({start_lat:.6f}, {start_lon:.6f})")
                logger.warning(f"  终点({end_lat:.6f}, {end_lon:.6f})")
                logger.warning(f"  中国推荐范围: 纬度{china_lat_range}, 经度{china_lon_range}")

            logger.debug(f"坐标验证通过: 起点({start_lat:.6f}, {start_lon:.6f}), 终点({end_lat:.6f}, {end_lon:.6f})")
            return True

        except Exception as e:
            logger.error(f"坐标验证时发生异常: {e}")
            return False
    
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

    def calculate_distance_matrix_parallel(self, locations: List[Tuple[float, float]],
                                          location_names: Optional[List[str]] = None,
                                          method: str = "graphhopper", vehicle: str = "car",
                                          max_workers: int = 14) -> pd.DataFrame:
        """
        并行计算位置点之间的距离矩阵

        Args:
            locations: 位置列表，每个位置为(lat, lon)元组
            location_names: 位置名称列表
            method: 计算方法 ("graphhopper", "haversine", "euclidean")
            vehicle: 车辆类型 (当method为"graphhopper"时使用)
            max_workers: 最大并行工作进程数（默认14核）

        Returns:
            距离矩阵DataFrame
        """
        if method == "graphhopper":
            return self.routing_engine.calculate_distance_matrix_parallel(
                locations, location_names, vehicle, max_workers
            )
        else:
            # 对于haversine和euclidean方法，使用简单的并行计算
            return self._calculate_simple_distance_matrix_parallel(
                locations, location_names, method, max_workers
            )

    def _calculate_simple_distance_matrix_parallel(self, locations: List[Tuple[float, float]],
                                                  location_names: Optional[List[str]] = None,
                                                  method: str = "haversine",
                                                  max_workers: int = 14) -> pd.DataFrame:
        """
        使用简单距离方法（haversine, euclidean）并行计算距离矩阵
        """
        n_locations = len(locations)
        if location_names is None:
            location_names = [f"Location_{i}" for i in range(n_locations)]

        # 创建需要计算的任务列表
        tasks = []
        for i in range(n_locations):
            for j in range(i + 1, n_locations):
                tasks.append((i, j, locations[i], locations[j]))

        logger.info(f"并行计算 {n_locations} 个位置的{method}距离矩阵，使用 {max_workers} 个进程")

        # 创建距离矩阵
        distance_matrix = np.zeros((n_locations, n_locations))

        # 设置对角线为0
        for i in range(n_locations):
            distance_matrix[i][i] = 0.0

        if len(tasks) == 0:
            df = pd.DataFrame(distance_matrix, index=location_names, columns=location_names)
            return df

        # 使用进程池并行计算
        try:
            with Pool(processes=min(max_workers, len(tasks), cpu_count())) as pool:
                compute_func = partial(self._compute_simple_distance, method=method)
                results = pool.map(compute_func, tasks)

                # 填充距离矩阵
                for task_idx, (i, j, _, _) in enumerate(tasks):
                    distance = results[task_idx]
                    distance_matrix[i][j] = distance
                    distance_matrix[j][i] = distance

                logger.info(f"✅ 并行{method}距离矩阵计算完成")

        except Exception as e:
            logger.error(f"❌ 并行计算失败: {e}")
            # 回退到串行计算
            for i in range(n_locations):
                for j in range(i + 1, n_locations):
                    if method == "haversine":
                        distance = self.calculate_haversine_distance(
                            locations[i][0], locations[i][1],
                            locations[j][0], locations[j][1]
                        )
                    else:  # euclidean
                        distance = self.calculate_euclidean_distance(
                            locations[i][0], locations[i][1],
                            locations[j][0], locations[j][1]
                        )
                    distance_matrix[i][j] = distance
                    distance_matrix[j][i] = distance

        df = pd.DataFrame(distance_matrix, index=location_names, columns=location_names)
        return df

    @staticmethod
    def _compute_simple_distance(task_data: Tuple[int, int, Tuple[float, float], Tuple[float, float]],
                                method: str = "haversine") -> float:
        """
        计算单个位置对的简单距离（用于并行处理）
        """
        i, j, loc_i, loc_j = task_data

        if method == "haversine":
            # Haversine公式计算
            R = 6371  # 地球半径（公里）
            lat1, lon1 = np.radians(loc_i[0]), np.radians(loc_i[1])
            lat2, lon2 = np.radians(loc_j[0]), np.radians(loc_j[1])

            dlat = lat2 - lat1
            dlon = lon2 - lon1

            a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
            c = 2 * np.arcsin(np.sqrt(a))
            distance = R * c
            return distance

        elif method == "euclidean":
            # 欧几里得距离
            distance = ((loc_i[0] - loc_j[0])**2 + (loc_i[1] - loc_j[1])**2)**0.5 * 111
            return distance

        else:
            return 0.0


# 为了向后兼容，保持与原有接口一致的类名
DistanceCalculator = GraphHopperDistanceCalculator