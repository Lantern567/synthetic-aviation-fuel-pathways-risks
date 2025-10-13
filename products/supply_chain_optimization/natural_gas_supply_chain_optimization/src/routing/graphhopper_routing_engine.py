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

# 导入统一缓存配置
try:
    from unified_cache_configuration import get_cache_config, GraphHopperCacheConfig
    UNIFIED_CONFIG_AVAILABLE = True
except ImportError:
    UNIFIED_CONFIG_AVAILABLE = False
    pass  # 静默降级处理

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
                 cache_dir: str = None,
                 max_retries: int = None,
                 request_timeout: int = None,
                 enable_cache: bool = None,
                 use_unified_config: bool = True):
        """
        初始化GraphHopper路径规划引擎

        Args:
            osm_pbf_path: OSM数据文件路径
            graphhopper_host: GraphHopper服务主机地址
            graphhopper_port: GraphHopper服务端口
            cache_dir: 缓存目录（如果为None且使用统一配置，则从配置中获取）
            max_retries: 最大重试次数（如果为None且使用统一配置，则从配置中获取）
            request_timeout: 请求超时时间(秒)（如果为None且使用统一配置，则从配置中获取）
            enable_cache: 是否启用缓存（如果为None且使用统一配置，则从配置中获取）
            use_unified_config: 是否使用统一缓存配置
        """
        # 加载统一配置（如果可用且启用）
        self.config = None
        if use_unified_config and UNIFIED_CONFIG_AVAILABLE:
            try:
                self.config = get_cache_config().get_graphhopper_config()
                logger.debug("使用统一缓存配置")
            except Exception as e:
                pass  # 静默降级处理
                self.config = None

        # 设置基础参数
        self.osm_pbf_path = osm_pbf_path
        self.graphhopper_host = graphhopper_host
        self.graphhopper_port = graphhopper_port
        self.base_url = f"http://{graphhopper_host}:{graphhopper_port}"

        # 从配置中获取参数（优先使用传入参数）
        if self.config:
            self.cache_dir = cache_dir or os.path.dirname(self.config.database_path)
            self.max_retries = max_retries or self.config.max_retries
            self.request_timeout = request_timeout or self.config.request_timeout
            self.enable_cache = enable_cache if enable_cache is not None else self.config.settings.enabled
            self.enable_batch_processing = self.config.enable_batch_processing
            self.preload_popular_routes = self.config.preload_popular_routes
            self.cache_ttl_hours = self.config.settings.ttl_hours
            self.max_cache_entries = self.config.settings.max_entries
            self.max_cache_size_mb = self.config.settings.max_cache_size_mb
            self.auto_cleanup_enabled = self.config.settings.auto_cleanup_enabled
            self.cleanup_threshold_ratio = self.config.settings.cleanup_threshold_ratio
        else:
            # 使用传统默认值
            self.cache_dir = cache_dir or "cache/graphhopper_routes"
            self.max_retries = max_retries or 3
            self.request_timeout = request_timeout or 30
            self.enable_cache = enable_cache if enable_cache is not None else True
            self.enable_batch_processing = False
            self.preload_popular_routes = False
            self.cache_ttl_hours = 48
            self.max_cache_entries = 50000
            self.max_cache_size_mb = 1000
            self.auto_cleanup_enabled = True
            self.cleanup_threshold_ratio = 0.8

        # 创建缓存目录
        os.makedirs(self.cache_dir, exist_ok=True)

        # 初始化缓存数据库
        if self.enable_cache:
            if self.config:
                self.cache_db_path = self.config.database_path
            else:
                self.cache_db_path = os.path.join(self.cache_dir, "route_cache.db")
            self._init_cache_db()

        # 扩展统计信息
        self.stats = {
            'total_requests': 0,
            'cache_hits': 0,
            'api_calls': 0,
            'failed_requests': 0,
            'total_distance_calculated': 0.0,
            'total_time_calculated': 0.0,
            'cache_misses': 0,
            'cache_writes': 0,
            'total_cache_size_bytes': 0,
            'cache_cleanup_count': 0,
            'average_response_time_ms': 0.0,
            'total_time_saved_seconds': 0.0,
            # 方法使用统计
            'method_usage': {
                'direct_api': 0,        # 第1层：直接API成功
                'mixed_route': 0,       # 第2层：混合路径（网格搜索）
                'method_failures': 0    # 方法失败计数
            },
            # 缓存性能统计
            'cache_performance': {
                'hit_ratio': 0.0,
                'average_cache_save_time_ms': 0.0,
                'average_cache_read_time_ms': 0.0,
                'cache_memory_usage_mb': 0.0
            }
        }

        # 内存缓存（热数据）
        self.memory_cache = {}
        self.memory_cache_max_size = 500  # 内存缓存最大条目数

        # 缓存维护
        self.last_cleanup_time = None
        self.cleanup_interval_hours = 24
        
        logger.debug(f"GraphHopper路径规划引擎初始化完成")
        logger.debug(f"OSM数据文件: {osm_pbf_path}")
        logger.debug(f"服务地址: {self.base_url}")
        logger.debug(f"缓存目录: {cache_dir}")
        logger.debug(f"缓存启用: {enable_cache}")

    def _migrate_database_if_needed(self, cursor):
        """迁移数据库架构（如果需要）"""
        try:
            # 检查是否存在旧表结构
            cursor.execute("PRAGMA table_info(route_cache)")
            columns = {row[1] for row in cursor.fetchall()}

            # 如果表存在但缺少新字段，进行迁移
            required_columns = {'expires_at', 'cache_key', 'access_count', 'data_size_bytes', 'calculation_time_ms', 'method_used', 'last_accessed'}
            missing_columns = required_columns - columns

            if missing_columns:
                logger.debug(f"数据库架构需要迁移，缺少字段: {missing_columns}")

                # 添加缺失的字段
                if 'expires_at' in missing_columns:
                    cursor.execute('ALTER TABLE route_cache ADD COLUMN expires_at TIMESTAMP')
                if 'cache_key' in missing_columns:
                    cursor.execute('ALTER TABLE route_cache ADD COLUMN cache_key TEXT')
                if 'access_count' in missing_columns:
                    cursor.execute('ALTER TABLE route_cache ADD COLUMN access_count INTEGER DEFAULT 1')
                if 'data_size_bytes' in missing_columns:
                    cursor.execute('ALTER TABLE route_cache ADD COLUMN data_size_bytes INTEGER DEFAULT 0')
                if 'calculation_time_ms' in missing_columns:
                    cursor.execute('ALTER TABLE route_cache ADD COLUMN calculation_time_ms REAL')
                if 'method_used' in missing_columns:
                    cursor.execute('ALTER TABLE route_cache ADD COLUMN method_used TEXT')
                if 'last_accessed' in missing_columns:
                    cursor.execute('ALTER TABLE route_cache ADD COLUMN last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP')

                logger.debug("数据库迁移完成")
        except Exception as e:
            logger.debug(f"数据库迁移检查: {e} (可能是新数据库)")

    def _init_cache_db(self):
        """初始化增强的缓存数据库"""
        try:
            # 确保缓存目录存在
            cache_dir = os.path.dirname(self.cache_db_path)
            os.makedirs(cache_dir, exist_ok=True)
            logger.debug(f"确保缓存目录存在: {cache_dir}")

            conn = sqlite3.connect(self.cache_db_path)
            cursor = conn.cursor()

            # 先检查是否需要数据库迁移
            self._migrate_database_if_needed(cursor)

            # 创建增强的路径缓存表
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
                    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    access_count INTEGER DEFAULT 1,
                    expires_at TIMESTAMP,
                    calculation_time_ms REAL,
                    method_used TEXT,
                    cache_key TEXT UNIQUE,
                    data_size_bytes INTEGER DEFAULT 0
                )
            ''')

            # 创建缓存统计表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cache_statistics (
                    id INTEGER PRIMARY KEY,
                    total_requests INTEGER DEFAULT 0,
                    cache_hits INTEGER DEFAULT 0,
                    cache_misses INTEGER DEFAULT 0,
                    total_cache_size_bytes INTEGER DEFAULT 0,
                    last_cleanup_time TIMESTAMP,
                    last_update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 创建缓存性能表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cache_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    operation_type TEXT NOT NULL,  -- 'read', 'write', 'cleanup'
                    execution_time_ms REAL NOT NULL,
                    data_size_bytes INTEGER,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 创建索引
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_cache_key ON route_cache(cache_key)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_coordinates ON route_cache(start_lat, start_lon, end_lat, end_lon)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_expires_at ON route_cache(expires_at)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_last_accessed ON route_cache(last_accessed)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_access_count ON route_cache(access_count)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_performance_timestamp ON cache_performance(timestamp)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_performance_operation ON cache_performance(operation_type)
            ''')

            # 初始化统计记录
            cursor.execute('INSERT OR IGNORE INTO cache_statistics (id) VALUES (1)')

            conn.commit()
            conn.close()
            logger.debug("增强缓存数据库初始化完成")

        except Exception as e:
            logger.error(f"缓存数据库初始化失败: {e}")
            raise
    
    def _generate_cache_key(self, start_lat: float, start_lon: float, 
                           end_lat: float, end_lon: float, vehicle: str = "car") -> str:
        """生成缓存键"""
        key_string = f"{start_lat:.6f},{start_lon:.6f},{end_lat:.6f},{end_lon:.6f},{vehicle}"
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def _get_from_cache(self, cache_key: str) -> Optional[Dict]:
        """从增强缓存中获取路径数据"""
        if not self.enable_cache:
            return None

        start_time = time.time()

        # 首先检查内存缓存
        if cache_key in self.memory_cache:
            cache_data = self.memory_cache[cache_key]
            cache_data['last_accessed'] = datetime.now()
            cache_data['access_count'] = cache_data.get('access_count', 0) + 1
            self.stats['cache_hits'] += 1
            read_time_ms = (time.time() - start_time) * 1000
            self.stats['cache_performance']['average_cache_read_time_ms'] = (
                (self.stats['cache_performance']['average_cache_read_time_ms'] * self.stats['cache_hits'] + read_time_ms) /
                (self.stats['cache_hits'] + 1)
            )
            try:
                print(f"[GraphHopper缓存] 🟢 内存缓存命中: {cache_key[:8]}..., 耗时: {read_time_ms:.1f}ms")
            except:
                pass  # 静默处理编码错误
            return cache_data

        try:
            conn = sqlite3.connect(self.cache_db_path)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT distance_km, time_hours, route_coordinates, created_at,
                       expires_at, calculation_time_ms, method_used, access_count
                FROM route_cache
                WHERE cache_key = ?
            ''', (cache_key,))

            result = cursor.fetchone()

            if result:
                (distance_km, time_hours, route_coordinates_json, created_at,
                 expires_at_str, calc_time_ms, method_used, access_count) = result

                # 检查是否过期
                if expires_at_str:
                    expires_at = datetime.fromisoformat(expires_at_str)
                    if datetime.now() > expires_at:
                        logger.debug(f"缓存条目已过期: {cache_key[:12]}...")
                        cursor.execute('DELETE FROM route_cache WHERE cache_key = ?', (cache_key,))
                        conn.commit()
                        conn.close()
                        self.stats['cache_misses'] += 1
                        return None

                # 解析路径坐标
                route_coordinates = None
                if route_coordinates_json:
                    try:
                        route_coordinates = json.loads(route_coordinates_json)
                    except json.JSONDecodeError:
                        route_coordinates = None

                # 更新访问统计
                cursor.execute('''
                    UPDATE route_cache
                    SET last_accessed = CURRENT_TIMESTAMP, access_count = access_count + 1
                    WHERE cache_key = ?
                ''', (cache_key,))

                # 记录读取性能
                read_time_ms = (time.time() - start_time) * 1000
                cursor.execute('''
                    INSERT INTO cache_performance (operation_type, execution_time_ms, data_size_bytes)
                    VALUES ('read', ?, ?)
                ''', (read_time_ms, len(route_coordinates_json or '')))

                conn.commit()
                conn.close()

                # 构建返回结果
                cache_result = {
                    'distance_km': distance_km,
                    'time_hours': time_hours,
                    'route_coordinates': route_coordinates,
                    'route_found': True,
                    'method': 'cache',
                    'cached_at': created_at,
                    'access_count': access_count + 1,
                    'original_calculation_time_ms': calc_time_ms,
                    'original_method': method_used
                }

                # 添加到内存缓存
                if len(self.memory_cache) < self.memory_cache_max_size:
                    cache_result['last_accessed'] = datetime.now()
                    self.memory_cache[cache_key] = cache_result

                self.stats['cache_hits'] += 1
                self.stats['total_time_saved_seconds'] += (calc_time_ms or 0) / 1000.0

                # 更新平均读取时间
                if self.stats['cache_hits'] > 0:
                    self.stats['cache_performance']['average_cache_read_time_ms'] = (
                        (self.stats['cache_performance']['average_cache_read_time_ms'] * (self.stats['cache_hits'] - 1) + read_time_ms) /
                        self.stats['cache_hits']
                    )

                try:
                    print(f"[GraphHopper缓存] 🟡 数据库缓存命中: {cache_key[:8]}..., 耗时: {read_time_ms:.1f}ms, 原计算时间: {calc_time_ms or 0:.0f}ms")
                except:
                    pass  # 静默处理编码错误
                return cache_result

            conn.close()
            self.stats['cache_misses'] += 1
            print(f"[GraphHopper缓存] 缓存未命中: {cache_key[:8]}..., 需要重新计算")
            return None

        except Exception as e:
            print(f"[GraphHopper缓存] 缓存查询失败: {cache_key[:8]}..., 错误: {e}")
            self.stats['cache_misses'] += 1
            return None
    
    def _save_to_cache(self, cache_key: str, start_lat: float, start_lon: float,
                      end_lat: float, end_lon: float, result: Dict, vehicle: str = "car"):
        """保存路径数据到增强缓存"""
        if not self.enable_cache or not result.get('route_found'):
            return

        start_time = time.time()

        try:
            conn = sqlite3.connect(self.cache_db_path)
            cursor = conn.cursor()

            # 序列化路径坐标
            route_coordinates_json = None
            data_size = 0
            if result.get('route_coordinates'):
                route_coordinates_json = json.dumps(result['route_coordinates'])
                data_size = len(route_coordinates_json.encode('utf-8'))

            # 计算过期时间
            expires_at = datetime.now() + timedelta(hours=self.cache_ttl_hours)

            # 获取原始计算信息
            calc_time_ms = result.get('response_time', 0) * 1000  # 转换为毫秒
            method_used = result.get('method', 'unknown')

            cursor.execute('''
                INSERT OR REPLACE INTO route_cache
                (start_lat, start_lon, end_lat, end_lon, distance_km, time_hours,
                 route_coordinates, vehicle_type, cache_key, expires_at,
                 calculation_time_ms, method_used, data_size_bytes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                start_lat, start_lon, end_lat, end_lon,
                result.get('distance_km'), result.get('time_hours'),
                route_coordinates_json, vehicle, cache_key,
                expires_at.isoformat(), calc_time_ms, method_used, data_size
            ))

            # 记录写入性能
            write_time_ms = (time.time() - start_time) * 1000
            cursor.execute('''
                INSERT INTO cache_performance (operation_type, execution_time_ms, data_size_bytes)
                VALUES ('write', ?, ?)
            ''', (write_time_ms, data_size))

            # 更新统计表
            cursor.execute('''
                UPDATE cache_statistics
                SET total_cache_size_bytes = total_cache_size_bytes + ?,
                    last_update_time = CURRENT_TIMESTAMP
                WHERE id = 1
            ''', (data_size,))

            conn.commit()
            conn.close()

            # 同时添加到内存缓存
            if len(self.memory_cache) < self.memory_cache_max_size:
                cache_data = {
                    'distance_km': result.get('distance_km'),
                    'time_hours': result.get('time_hours'),
                    'route_coordinates': result.get('route_coordinates'),
                    'route_found': True,
                    'method': 'cache',
                    'cached_at': datetime.now().isoformat(),
                    'access_count': 1,
                    'last_accessed': datetime.now(),
                    'original_calculation_time_ms': calc_time_ms,
                    'original_method': method_used
                }
                self.memory_cache[cache_key] = cache_data

            # 更新统计
            self.stats['cache_writes'] += 1
            self.stats['total_cache_size_bytes'] += data_size

            # 更新平均写入时间
            if self.stats['cache_writes'] > 0:
                self.stats['cache_performance']['average_cache_save_time_ms'] = (
                    (self.stats['cache_performance']['average_cache_save_time_ms'] * (self.stats['cache_writes'] - 1) + write_time_ms) /
                    self.stats['cache_writes']
                )

            print(f"[GraphHopper缓存] 🟢 缓存保存成功: {cache_key[:8]}..., 大小: {data_size}字节, 耗时: {write_time_ms:.1f}ms")

        except Exception as e:
            print(f"[GraphHopper缓存] 🔴 缓存保存失败: {cache_key[:8]}..., 错误: {e}")
            self.stats['cache_writes'] += 1  # 仍然计入尝试次数
    
    def check_service_health(self) -> bool:
        """检查GraphHopper服务状态"""
        try:
            health_url = f"{self.base_url}/health"
            response = requests.get(health_url, timeout=5)
            if response.status_code == 200:
                logger.debug("GraphHopper服务运行正常")
                return True
            else:
                pass  # 静默处理HTTP错误
                return False
        except requests.exceptions.ConnectionError:
            pass  # 静默处理连接失败
            return False
        except requests.exceptions.Timeout:
            pass  # 静默处理超时
            return False
        except Exception as e:
            pass  # 静默处理健康检查失败
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
            pass  # 移除状态检查信息
            if not self.check_service_health():
                error_msg = "GraphHopper服务不可用，请检查服务是否正在运行"
                logger.error(f"❌ {error_msg}")
                raise ConnectionError(error_msg)
            pass  # 移除服务正常信息

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

                # 静默API请求信息
                pass  # 静默API请求调试信息
                pass  # 静默请求URL
                pass  # 静默请求参数
                pass  # 静默参数循环
                pass  # 静默起点坐标
                pass  # 静默终点坐标
                pass  # 静默车辆类型
                pass  # 静默超时设置

                response = requests.get(route_url, params=params, timeout=self.request_timeout)

                # 静默响应信息
                pass  # 静默响应状态码
                pass  # 静默响应头信息
                pass  # 静默响应时间
                
                if response.status_code == 200:
                    # 成功响应处理
                    try:
                        data = response.json()
                        pass  # 静默JSON解析成功
                        pass  # 静默响应数据结构

                        if isinstance(data, dict):
                            pass  # 静默响应字段列表

                            # 检查和记录 snapped_waypoints 信息
                            if 'snapped_waypoints' in data:
                                snapped = data['snapped_waypoints']
                                pass  # 静默snapped_waypoints数据类型
                                if isinstance(snapped, dict) and 'coordinates' in snapped:
                                    coords = snapped['coordinates']
                                    pass  # 静默吸附坐标数量
                                    if coords and len(coords) >= 2:
                                        start_snapped = coords[0]
                                        end_snapped = coords[-1]
                                        pass  # 静默吸附起点坐标
                                        pass  # 静默吸附终点坐标

                                        # 计算吸附距离
                                        start_snap_dist = self._calculate_haversine_distance(
                                            start_lat, start_lon, start_snapped[1], start_snapped[0]
                                        )
                                        end_snap_dist = self._calculate_haversine_distance(
                                            end_lat, end_lon, end_snapped[1], end_snapped[0]
                                        )
                                        pass  # 静默起点吸附距离
                                        pass  # 静默终点吸附距离
                                else:
                                    pass  # 静默snapped_waypoints数据格式
                            else:
                                pass  # 静默没有snapped_waypoints字段

                            if 'paths' in data:
                                paths_count = len(data['paths']) if data['paths'] else 0
                                pass  # 静默路径数量
                                if paths_count > 0:
                                    path = data['paths'][0]
                                    pass  # 静默第一条路径字段
                                    pass  # 静默路径距离
                                    pass  # 静默路径时间

                                    # 检查path内的snapped_waypoints
                                    if 'snapped_waypoints' in path:
                                        path_snapped = path['snapped_waypoints']
                                        pass  # 静默路径内snapped_waypoints类型
                                        if isinstance(path_snapped, dict) and 'coordinates' in path_snapped:
                                            path_coords = path_snapped['coordinates']
                                            pass  # 静默路径内吸附坐标数量
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

                        pass  # 静默尝试混合路径计算
                        pass  # 静默混合路径计算说明
                        try:
                            mixed_route_result = self._calculate_mixed_route(start_lat, start_lon, end_lat, end_lon, vehicle, include_route_geometry)
                            pass  # 静默混合路径计算成功
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
                pass  # 静默网格搜索尝试
                grid_result = self._grid_search_nearest_road(lat, lon, vehicle)
                if grid_result:
                    pass  # 静默网格搜索成功
                    return grid_result
                else:
                    logger.error(f"❌ 网格搜索也失败")
                    return None

        except Exception as e:
            logger.error(f"❌ 查找最近道路点异常: {e}")
            logger.error(f"异常类型: {type(e).__name__}")

            # 异常情况下也尝试网格搜索
            pass  # 静默异常情况下网格搜索
            try:
                grid_result = self._grid_search_nearest_road(lat, lon, vehicle)
                if grid_result:
                    pass  # 静默网格搜索成功
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
            pass  # 静默开始网格搜索

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
                pass  # 静默搜索层信息

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

                pass  # 静默搜索点生成

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

                                pass  # 静默网格点找到道路
                                pass  # 静默原始点到道路距离

                                # 更新最佳道路点
                                if real_distance < best_distance:
                                    best_distance = real_distance
                                    best_road_point = (road_lat, road_lon)
                                    pass  # 静默更新最佳道路点

                                # 如果找到足够近的点，可以提前返回
                                if real_distance < 2.0:  # 距离小于2km时提前返回
                                    pass  # 静默找到足够近的道路点
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
                    pass  # 静默找到满意道路点
                    break

                pass  # 静默搜索层完成

            if best_road_point:
                pass  # 静默网格搜索成功
                pass  # 静默最终道路点
                pass  # 静默最终距离
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
            pass  # 静默开始混合路径计算

            # 1. 通过网格搜索找到起点最近道路
            pass  # 静默查找起点最近道路点
            start_road_point = self._grid_search_nearest_road(start_lat, start_lon, vehicle, max_radius_km=50.0)
            if not start_road_point:
                # 如果网格搜索失败，直接抛出异常
                error_msg = f"起点网格搜索失败: 无法在50km范围内找到起点({start_lat:.6f},{start_lon:.6f})的道路点"
                logger.error(f"❌ {error_msg}")
                raise Exception(error_msg)

            start_road_lat, start_road_lon = start_road_point
            pass  # 静默起点道路点坐标

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

            pass  # 静默起点接入距离
            pass  # 静默终点接出距离

            # 4. 计算道路网络距离 (道路点之间)
            pass  # 静默计算道路网络距离
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

                        pass  # 静默道路网络距离
                        pass  # 静默道路网络时间

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

            pass  # 静默混合路径计算结果
            pass  # 静默接入距离
            pass  # 静默道路距离
            pass  # 静默接出距离
            pass  # 静默总距离
            pass  # 静默总时间

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

            pass  # 静默混合路径计算完成
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
    
    def cleanup_expired_cache(self) -> int:
        """
        清理过期和不常用的缓存条目

        Returns:
            清理的条目数量
        """
        if not self.enable_cache or not self.auto_cleanup_enabled:
            return 0

        try:
            start_time = time.time()
            conn = sqlite3.connect(self.cache_db_path)
            cursor = conn.cursor()

            # 清理过期条目
            cursor.execute('DELETE FROM route_cache WHERE expires_at < ?',
                         (datetime.now().isoformat(),))
            expired_count = cursor.rowcount

            # 如果缓存条目过多，清理最少使用的条目
            cursor.execute('SELECT COUNT(*) FROM route_cache')
            total_entries = cursor.fetchone()[0]

            lru_count = 0
            if total_entries > self.max_cache_entries:
                excess = total_entries - int(self.max_cache_entries * self.cleanup_threshold_ratio)
                cursor.execute('''
                    DELETE FROM route_cache
                    WHERE id IN (
                        SELECT id FROM route_cache
                        ORDER BY access_count ASC, last_accessed ASC
                        LIMIT ?
                    )
                ''', (excess,))
                lru_count = cursor.rowcount

            # 更新统计信息
            cursor.execute('''
                UPDATE cache_statistics
                SET last_cleanup_time = ?
                WHERE id = 1
            ''', (datetime.now().isoformat(),))

            # 记录清理性能
            cleanup_time_ms = (time.time() - start_time) * 1000
            cursor.execute('''
                INSERT INTO cache_performance (operation_type, execution_time_ms, data_size_bytes)
                VALUES ('cleanup', ?, ?)
            ''', (cleanup_time_ms, expired_count + lru_count))

            conn.commit()
            conn.close()

            total_cleaned = expired_count + lru_count
            if total_cleaned > 0:
                logger.info(f"缓存清理完成: 过期{expired_count}条, LRU清理{lru_count}条, 耗时{cleanup_time_ms:.2f}ms")

            self.stats['cache_cleanup_count'] += 1
            self.last_cleanup_time = datetime.now()

            return total_cleaned

        except Exception as e:
            logger.error(f"缓存清理失败: {e}")
            return 0

    def get_enhanced_cache_statistics(self) -> Dict:
        """获取增强的缓存统计信息"""
        if not self.enable_cache:
            return {}

        try:
            conn = sqlite3.connect(self.cache_db_path)
            cursor = conn.cursor()

            # 获取基础统计
            cursor.execute('''
                SELECT COUNT(*), AVG(access_count), SUM(data_size_bytes),
                       MIN(created_at), MAX(last_accessed)
                FROM route_cache
            ''')
            basic_stats = cursor.fetchone()
            total_entries, avg_access, total_size, oldest_entry, newest_access = basic_stats

            # 获取过期条目数量
            cursor.execute('''
                SELECT COUNT(*) FROM route_cache WHERE expires_at < ?
            ''', (datetime.now().isoformat(),))
            expired_count = cursor.fetchone()[0]

            # 获取最热门的路径
            cursor.execute('''
                SELECT start_lat, start_lon, end_lat, end_lon, access_count, distance_km
                FROM route_cache
                ORDER BY access_count DESC
                LIMIT 5
            ''')
            popular_routes = cursor.fetchall()

            # 计算命中率
            total_requests = self.stats['total_requests']
            cache_hits = self.stats['cache_hits']
            hit_ratio = (cache_hits / max(total_requests, 1)) * 100

            # 更新内部统计
            self.stats['cache_performance']['hit_ratio'] = hit_ratio
            self.stats['total_cache_size_bytes'] = total_size or 0

            conn.close()

            return {
                'basic_stats': {
                    'total_entries': total_entries or 0,
                    'expired_entries': expired_count or 0,
                    'cache_size_mb': (total_size or 0) / 1024 / 1024,
                    'average_access_count': avg_access or 0,
                    'oldest_entry': oldest_entry,
                    'newest_access': newest_access
                },
                'performance_stats': {
                    'hit_ratio': hit_ratio,
                    'total_requests': total_requests,
                    'cache_hits': cache_hits,
                    'cache_misses': self.stats['cache_misses'],
                    'total_time_saved_seconds': self.stats['total_time_saved_seconds']
                },
                'popular_routes': popular_routes,
                'memory_cache_size': len(self.memory_cache),
                'last_cleanup': self.last_cleanup_time.isoformat() if self.last_cleanup_time else None
            }

        except Exception as e:
            logger.error(f"获取缓存统计失败: {e}")
            return {}

    def preload_popular_routes(self, route_list: List[Tuple[float, float, float, float]]):
        """
        预加载热门路径到缓存

        Args:
            route_list: 路径列表，每个路径为(start_lat, start_lon, end_lat, end_lon)元组
        """
        if not self.enable_cache or not self.preload_popular_routes:
            return

        logger.info(f"开始预加载{len(route_list)}条热门路径...")

        preloaded = 0
        for start_lat, start_lon, end_lat, end_lon in route_list:
            try:
                # 检查是否已经缓存
                cache_key = self._generate_cache_key(start_lat, start_lon, end_lat, end_lon)
                cached_result = self._get_from_cache(cache_key)

                if not cached_result:
                    # 计算并缓存路径
                    result = self.calculate_route_distance(
                        start_lat, start_lon, end_lat, end_lon,
                        include_route_geometry=True
                    )
                    if result.get('route_found'):
                        preloaded += 1

            except Exception as e:
                logger.warning(f"预加载路径失败 ({start_lat}, {start_lon}) -> ({end_lat}, {end_lon}): {e}")

        logger.info(f"预加载完成，成功预加载{preloaded}条路径")

    def optimize_cache_performance(self):
        """优化缓存性能"""
        if not self.enable_cache:
            return

        try:
            # 自动清理过期缓存
            if (self.last_cleanup_time is None or
                (datetime.now() - self.last_cleanup_time).total_seconds() > self.cleanup_interval_hours * 3600):
                self.cleanup_expired_cache()

            # 优化内存缓存
            if len(self.memory_cache) > self.memory_cache_max_size:
                # 清理内存缓存中访问次数最少的条目
                sorted_cache = sorted(self.memory_cache.items(),
                                    key=lambda x: (x[1].get('access_count', 0), x[1].get('last_accessed', '')))
                excess = len(self.memory_cache) - int(self.memory_cache_max_size * 0.8)
                for i in range(excess):
                    key, _ = sorted_cache[i]
                    del self.memory_cache[key]

            # 更新性能统计
            self.stats['cache_performance']['cache_memory_usage_mb'] = len(self.memory_cache) * 0.1  # 估算

            logger.debug("缓存性能优化完成")

        except Exception as e:
            logger.error(f"缓存性能优化失败: {e}")

    def get_cache_configuration_summary(self) -> str:
        """获取缓存配置摘要"""
        config_lines = [
            "=== GraphHopper缓存配置摘要 ===",
            f"缓存状态: {'启用' if self.enable_cache else '禁用'}",
            f"缓存数据库: {self.cache_db_path}",
            f"TTL: {self.cache_ttl_hours} 小时",
            f"最大条目数: {self.max_cache_entries:,}",
            f"最大大小: {self.max_cache_size_mb} MB",
            f"自动清理: {'是' if self.auto_cleanup_enabled else '否'}",
            f"清理阈值: {self.cleanup_threshold_ratio * 100}%",
            f"批量处理: {'是' if self.enable_batch_processing else '否'}",
            f"预加载热门路径: {'是' if self.preload_popular_routes else '否'}",
            f"内存缓存大小: {self.memory_cache_max_size}",
            f"统一配置: {'是' if self.config else '否'}",
        ]

        if self.config:
            config_lines.extend([
                f"\n=== 统一配置详情 ===",
                f"配置文件: {getattr(self.config, 'config_file', '未知')}",
                f"压缩启用: {'是' if self.config.settings.compression_enabled else '否'}",
                f"备份启用: {'是' if self.config.settings.backup_enabled else '否'}",
            ])

        return '\n'.join(config_lines)

    def clear_cache(self, cache_type: str = "all"):
        """
        清理缓存

        Args:
            cache_type: 缓存类型 ("all", "memory", "database", "expired")
        """
        if not self.enable_cache:
            return

        try:
            if cache_type in ["all", "memory"]:
                self.memory_cache.clear()
                logger.info("内存缓存已清理")

            if cache_type in ["all", "database"]:
                conn = sqlite3.connect(self.cache_db_path)
                cursor = conn.cursor()
                cursor.execute('DELETE FROM route_cache')
                cleared_count = cursor.rowcount
                cursor.execute('DELETE FROM cache_performance')
                cursor.execute('''
                    UPDATE cache_statistics
                    SET total_requests = 0, cache_hits = 0, cache_misses = 0,
                        total_cache_size_bytes = 0, last_cleanup_time = ?
                    WHERE id = 1
                ''', (datetime.now().isoformat(),))
                conn.commit()
                conn.close()
                logger.info(f"数据库缓存已清理，删除{cleared_count}条记录")

            if cache_type == "expired":
                cleared_count = self.cleanup_expired_cache()
                logger.info(f"过期缓存已清理，删除{cleared_count}条记录")

            # 重置统计信息
            if cache_type == "all":
                self.stats = {
                    'total_requests': 0, 'cache_hits': 0, 'api_calls': 0,
                    'failed_requests': 0, 'total_distance_calculated': 0.0,
                    'total_time_calculated': 0.0, 'cache_misses': 0,
                    'cache_writes': 0, 'total_cache_size_bytes': 0,
                    'cache_cleanup_count': 0, 'average_response_time_ms': 0.0,
                    'total_time_saved_seconds': 0.0,
                    'method_usage': {'direct_api': 0, 'mixed_route': 0, 'method_failures': 0},
                    'cache_performance': {'hit_ratio': 0.0, 'average_cache_save_time_ms': 0.0,
                                        'average_cache_read_time_ms': 0.0, 'cache_memory_usage_mb': 0.0}
                }

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

    def cleanup_expired_cache(self) -> Dict:
        """清理过期的缓存条目"""
        if not self.enable_cache:
            return {"removed_entries": 0, "space_freed_bytes": 0}

        start_time = time.time()
        removed_entries = 0
        space_freed = 0

        try:
            conn = sqlite3.connect(self.cache_db_path)
            cursor = conn.cursor()

            # 查询过期的条目信息
            cursor.execute('''
                SELECT cache_key, data_size_bytes FROM route_cache
                WHERE expires_at IS NOT NULL AND datetime(expires_at) < datetime('now')
            ''')
            expired_entries = cursor.fetchall()

            if expired_entries:
                # 计算释放的空间
                space_freed = sum(entry[1] or 0 for entry in expired_entries)
                removed_entries = len(expired_entries)

                # 从内存缓存中移除
                for cache_key, _ in expired_entries:
                    self.memory_cache.pop(cache_key, None)

                # 删除过期条目
                cursor.execute('''
                    DELETE FROM route_cache
                    WHERE expires_at IS NOT NULL AND datetime(expires_at) < datetime('now')
                ''')

                # 更新统计表
                cursor.execute('''
                    UPDATE cache_statistics
                    SET total_cache_size_bytes = CASE
                        WHEN total_cache_size_bytes > ? THEN total_cache_size_bytes - ?
                        ELSE 0
                    END,
                    last_update_time = CURRENT_TIMESTAMP
                    WHERE id = 1
                ''', (space_freed, space_freed))

            # 记录清理性能
            cleanup_time_ms = (time.time() - start_time) * 1000
            cursor.execute('''
                INSERT INTO cache_performance (operation_type, execution_time_ms, data_size_bytes)
                VALUES ('cleanup', ?, ?)
            ''', (cleanup_time_ms, space_freed))

            conn.commit()
            conn.close()

            # 更新内存统计
            self.stats['total_cache_size_bytes'] = max(0, self.stats['total_cache_size_bytes'] - space_freed)

            result = {
                "removed_entries": removed_entries,
                "space_freed_bytes": space_freed,
                "cleanup_time_ms": cleanup_time_ms
            }

            if removed_entries > 0:
                logger.info(f"缓存清理完成: 删除{removed_entries}个过期条目，释放{space_freed / 1024:.1f}KB空间")

            return result

        except Exception as e:
            logger.error(f"缓存清理失败: {e}")
            return {"removed_entries": 0, "space_freed_bytes": 0, "error": str(e)}

    def cleanup_lru_cache(self, max_entries: int = None) -> Dict:
        """基于LRU策略清理缓存"""
        if not self.enable_cache:
            return {"removed_entries": 0, "space_freed_bytes": 0}

        if max_entries is None:
            max_entries = getattr(self, 'max_cache_entries', 10000)

        start_time = time.time()

        try:
            conn = sqlite3.connect(self.cache_db_path)
            cursor = conn.cursor()

            # 计算当前条目数
            cursor.execute('SELECT COUNT(*) FROM route_cache')
            current_entries = cursor.fetchone()[0]

            if current_entries <= max_entries:
                conn.close()
                return {"removed_entries": 0, "space_freed_bytes": 0, "message": "无需清理"}

            # 计算需要删除的条目数
            entries_to_remove = current_entries - max_entries

            # 获取最少访问的条目
            cursor.execute('''
                SELECT cache_key, data_size_bytes FROM route_cache
                ORDER BY access_count ASC, last_accessed ASC
                LIMIT ?
            ''', (entries_to_remove,))

            lru_entries = cursor.fetchall()
            space_freed = sum(entry[1] or 0 for entry in lru_entries)

            # 从内存缓存和数据库中删除
            cache_keys_to_remove = [entry[0] for entry in lru_entries]

            for cache_key in cache_keys_to_remove:
                self.memory_cache.pop(cache_key, None)

            # 批量删除
            placeholders = ','.join('?' * len(cache_keys_to_remove))
            cursor.execute(f'''
                DELETE FROM route_cache WHERE cache_key IN ({placeholders})
            ''', cache_keys_to_remove)

            # 更新统计表
            cursor.execute('''
                UPDATE cache_statistics
                SET total_cache_size_bytes = CASE
                    WHEN total_cache_size_bytes > ? THEN total_cache_size_bytes - ?
                    ELSE 0
                END,
                last_update_time = CURRENT_TIMESTAMP
                WHERE id = 1
            ''', (space_freed, space_freed))

            # 记录清理性能
            cleanup_time_ms = (time.time() - start_time) * 1000
            cursor.execute('''
                INSERT INTO cache_performance (operation_type, execution_time_ms, data_size_bytes)
                VALUES ('lru_cleanup', ?, ?)
            ''', (cleanup_time_ms, space_freed))

            conn.commit()
            conn.close()

            # 更新内存统计
            self.stats['total_cache_size_bytes'] = max(0, self.stats['total_cache_size_bytes'] - space_freed)

            result = {
                "removed_entries": len(cache_keys_to_remove),
                "space_freed_bytes": space_freed,
                "cleanup_time_ms": cleanup_time_ms,
                "remaining_entries": max_entries
            }

            logger.info(f"LRU缓存清理完成: 删除{len(cache_keys_to_remove)}个条目，释放{space_freed / 1024:.1f}KB空间")
            return result

        except Exception as e:
            logger.error(f"LRU缓存清理失败: {e}")
            return {"removed_entries": 0, "space_freed_bytes": 0, "error": str(e)}

    def get_enhanced_cache_statistics(self) -> Dict:
        """获取增强的缓存统计信息"""
        try:
            conn = sqlite3.connect(self.cache_db_path)
            cursor = conn.cursor()

            # 基本统计
            cursor.execute('''
                SELECT
                    COUNT(*) as total_entries,
                    COUNT(CASE WHEN datetime(expires_at) > datetime('now') THEN 1 END) as active_entries,
                    COUNT(CASE WHEN datetime(expires_at) <= datetime('now') THEN 1 END) as expired_entries,
                    SUM(data_size_bytes) as total_size_bytes,
                    AVG(access_count) as avg_access_count,
                    MAX(access_count) as max_access_count,
                    AVG(calculation_time_ms) as avg_original_calc_time_ms
                FROM route_cache
            ''')

            basic_stats = cursor.fetchone()

            # 性能统计
            cursor.execute('''
                SELECT
                    operation_type,
                    COUNT(*) as operation_count,
                    AVG(execution_time_ms) as avg_time_ms,
                    MIN(execution_time_ms) as min_time_ms,
                    MAX(execution_time_ms) as max_time_ms,
                    SUM(data_size_bytes) as total_data_bytes
                FROM cache_performance
                WHERE timestamp > datetime('now', '-24 hours')
                GROUP BY operation_type
            ''')

            performance_stats = {row[0]: {
                'count': row[1],
                'avg_time_ms': row[2],
                'min_time_ms': row[3],
                'max_time_ms': row[4],
                'total_data_bytes': row[5]
            } for row in cursor.fetchall()}

            # 缓存命中率统计
            total_requests = self.stats['total_requests']
            cache_hits = self.stats['cache_hits']
            cache_misses = self.stats['cache_misses']

            hit_rate = (cache_hits / max(cache_hits + cache_misses, 1)) * 100

            # 最近访问的条目
            cursor.execute('''
                SELECT cache_key, start_lat, start_lon, end_lat, end_lon,
                       access_count, last_accessed, calculation_time_ms
                FROM route_cache
                ORDER BY last_accessed DESC
                LIMIT 5
            ''')

            recent_entries = [{
                'cache_key': row[0][:12] + '...',
                'start_coords': f"({row[1]:.4f}, {row[2]:.4f})",
                'end_coords': f"({row[3]:.4f}, {row[4]:.4f})",
                'access_count': row[5],
                'last_accessed': row[6],
                'original_calc_time_ms': row[7]
            } for row in cursor.fetchall()]

            conn.close()

            # 构建完整统计报告
            statistics = {
                'basic_stats': {
                    'total_entries': basic_stats[0],
                    'active_entries': basic_stats[1],
                    'expired_entries': basic_stats[2],
                    'total_size_bytes': basic_stats[3] or 0,
                    'total_size_mb': (basic_stats[3] or 0) / 1024 / 1024,
                    'avg_access_count': round(basic_stats[4] or 0, 2),
                    'max_access_count': basic_stats[5] or 0,
                    'avg_original_calc_time_ms': round(basic_stats[6] or 0, 2)
                },
                'performance_stats': performance_stats,
                'cache_efficiency': {
                    'hit_rate_percent': round(hit_rate, 2),
                    'total_requests': total_requests,
                    'cache_hits': cache_hits,
                    'cache_misses': cache_misses,
                    'total_time_saved_seconds': round(self.stats['total_time_saved_seconds'], 2)
                },
                'memory_cache_stats': {
                    'entries': len(self.memory_cache),
                    'max_size': self.memory_cache_max_size,
                    'usage_percent': round((len(self.memory_cache) / self.memory_cache_max_size) * 100, 2)
                },
                'recent_entries': recent_entries,
                'last_updated': datetime.now().isoformat()
            }

            return statistics

        except Exception as e:
            logger.error(f"获取缓存统计失败: {e}")
            return {
                'error': str(e),
                'basic_stats': self.stats,
                'last_updated': datetime.now().isoformat()
            }

    def clear_all_cache(self) -> Dict:
        """清空所有缓存数据"""
        start_time = time.time()

        try:
            # 清空内存缓存
            self.memory_cache.clear()

            # 清空数据库缓存
            conn = sqlite3.connect(self.cache_db_path)
            cursor = conn.cursor()

            # 获取清理前的统计
            cursor.execute('SELECT COUNT(*), COALESCE(SUM(data_size_bytes), 0) FROM route_cache')
            old_count, old_size = cursor.fetchone()

            # 删除所有缓存条目
            cursor.execute('DELETE FROM route_cache')
            cursor.execute('DELETE FROM cache_performance')
            cursor.execute('DELETE FROM cache_statistics')

            # 重新初始化统计记录
            cursor.execute('INSERT INTO cache_statistics (id) VALUES (1)')

            # 重置自增ID序列
            cursor.execute('DELETE FROM sqlite_sequence WHERE name IN ("route_cache", "cache_performance", "cache_statistics")')

            conn.commit()
            conn.close()

            # 重置内存统计
            self.stats.update({
                'cache_hits': 0,
                'cache_misses': 0,
                'cache_writes': 0,
                'total_cache_size_bytes': 0,
                'total_time_saved_seconds': 0.0,
                'cache_performance': {
                    'average_cache_read_time_ms': 0.0,
                    'average_cache_save_time_ms': 0.0
                }
            })

            clear_time_ms = (time.time() - start_time) * 1000

            result = {
                'cleared_entries': old_count,
                'freed_space_bytes': old_size,
                'clear_time_ms': clear_time_ms,
                'success': True
            }

            logger.info(f"缓存清空完成: 删除{old_count}个条目，释放{old_size / 1024:.1f}KB空间，耗时{clear_time_ms:.2f}ms")
            return result

        except Exception as e:
            logger.error(f"清空缓存失败: {e}")
            return {
                'cleared_entries': 0,
                'freed_space_bytes': 0,
                'success': False,
                'error': str(e)
            }

    def optimize_cache_performance(self) -> Dict:
        """优化缓存性能"""
        start_time = time.time()
        optimizations = []

        try:
            conn = sqlite3.connect(self.cache_db_path)
            cursor = conn.cursor()

            # 1. 清理过期条目
            expired_result = self.cleanup_expired_cache()
            if expired_result['removed_entries'] > 0:
                optimizations.append(f"清理{expired_result['removed_entries']}个过期条目")

            # 2. 检查缓存大小，必要时进行LRU清理
            cursor.execute('SELECT COUNT(*) FROM route_cache')
            current_entries = cursor.fetchone()[0]

            max_entries = getattr(self, 'max_cache_entries', 10000)
            if current_entries > max_entries:
                lru_result = self.cleanup_lru_cache(max_entries)
                if lru_result['removed_entries'] > 0:
                    optimizations.append(f"LRU清理{lru_result['removed_entries']}个条目")

            # 3. 数据库优化
            cursor.execute('VACUUM')
            cursor.execute('ANALYZE')
            optimizations.append("数据库压缩和分析完成")

            # 4. 更新索引统计
            cursor.execute('REINDEX')
            optimizations.append("索引重建完成")

            conn.close()

            optimize_time_ms = (time.time() - start_time) * 1000

            result = {
                'optimizations_applied': optimizations,
                'optimization_time_ms': optimize_time_ms,
                'current_entries': current_entries,
                'success': True
            }

            logger.info(f"缓存性能优化完成: {', '.join(optimizations)}，耗时{optimize_time_ms:.2f}ms")
            return result

        except Exception as e:
            logger.error(f"缓存性能优化失败: {e}")
            return {
                'optimizations_applied': optimizations,
                'success': False,
                'error': str(e)
            }


# 为了向后兼容，保持与原有接口一致的类名
DistanceCalculator = GraphHopperDistanceCalculator