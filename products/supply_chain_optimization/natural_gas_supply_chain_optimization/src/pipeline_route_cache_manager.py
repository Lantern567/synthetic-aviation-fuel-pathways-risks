"""
Pipeline Route Cache Manager
管道路径缓存管理器 - 为管道路径规划提供专门的缓存功能
"""

import os
import sqlite3
import json
import pickle
import hashlib
import logging
import time
from typing import Dict, List, Tuple, Optional, Any, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import threading
from pathlib import Path

from pipeline_route_types import PipelineRoute, ClusteredPipelineRoute
from unified_cache_configuration import get_cache_config, PipelineCacheConfig
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class CacheEntry:
    """缓存条目数据类"""
    cache_key: str
    route_data: Union[PipelineRoute, ClusteredPipelineRoute]
    created_at: datetime
    last_accessed: datetime
    access_count: int
    data_hash: str  # 用于检测管道数据文件变化
    calculation_time_ms: float  # 原始计算耗时

@dataclass
class CacheStatistics:
    """缓存统计信息数据类"""
    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    total_entries: int = 0
    cache_size_bytes: int = 0
    hit_ratio: float = 0.0
    average_calculation_time_saved_ms: float = 0.0
    total_time_saved_seconds: float = 0.0
    last_cleanup_time: Optional[datetime] = None
    last_update_time: Optional[datetime] = None

class PipelineRouteCacheManager:
    """
    管道路径缓存管理器

    功能:
    1. 缓存PipelineRoute和ClusteredPipelineRoute计算结果
    2. 基于参数组合生成缓存键（起点、终点、最大接入距离等）
    3. 检测管道数据文件变更，自动失效相关缓存
    4. 支持分层缓存（单管道类型 + 最优路径选择）
    5. 提供缓存统计和性能监控
    6. 支持异步缓存写入和自动维护
    """

    def __init__(self, config: Optional[PipelineCacheConfig] = None):
        """
        初始化管道路径缓存管理器

        Args:
            config: 缓存配置，如果为None则使用全局配置
        """
        self.config = config or get_cache_config().get_pipeline_config()
        self.cache_db_path = self.config.database_path
        self.cache_dir = os.path.dirname(self.cache_db_path)

        # 创建缓存目录
        os.makedirs(self.cache_dir, exist_ok=True)

        # 线程安全
        self.lock = threading.RLock()

        # 统计信息
        self.stats = CacheStatistics()

        # 管道数据文件监控
        self.pipeline_data_hashes = {}
        self.last_pipeline_check = None

        # 内存缓存（可选的第一层缓存）
        self.memory_cache = {}
        self.memory_cache_max_size = 1000

        # 初始化数据库
        self._init_database()

        # 加载统计信息
        self._load_statistics()

        logger.debug(f"管道路径缓存管理器初始化完成")
        logger.debug(f"缓存数据库: {self.cache_db_path}")
        logger.debug(f"缓存设置: TTL={self.config.settings.ttl_hours}小时, "
                   f"最大大小={self.config.settings.max_cache_size_mb}MB, "
                   f"最大条目={self.config.settings.max_entries}")

    def _init_database(self):
        """初始化缓存数据库"""
        try:
            # 确保缓存目录存在
            cache_dir = os.path.dirname(self.cache_db_path)
            os.makedirs(cache_dir, exist_ok=True)
            logger.debug(f"确保缓存目录存在: {cache_dir}")

            conn = sqlite3.connect(self.cache_db_path)
            cursor = conn.cursor()

            # 创建路径缓存表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS pipeline_route_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cache_key TEXT UNIQUE NOT NULL,
                    start_lat REAL NOT NULL,
                    start_lon REAL NOT NULL,
                    end_lat REAL NOT NULL,
                    end_lon REAL NOT NULL,
                    max_access_distance REAL,
                    route_type TEXT,  -- 'single' or 'clustered'
                    route_data BLOB NOT NULL,  -- 序列化的路径数据
                    data_hash TEXT NOT NULL,   -- 管道数据文件哈希
                    calculation_time_ms REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    access_count INTEGER DEFAULT 1,
                    expires_at TIMESTAMP
                )
            ''')

            # 创建缓存统计表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cache_statistics (
                    id INTEGER PRIMARY KEY,
                    total_requests INTEGER DEFAULT 0,
                    cache_hits INTEGER DEFAULT 0,
                    cache_misses INTEGER DEFAULT 0,
                    total_entries INTEGER DEFAULT 0,
                    cache_size_bytes INTEGER DEFAULT 0,
                    total_time_saved_seconds REAL DEFAULT 0.0,
                    last_cleanup_time TIMESTAMP,
                    last_update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 创建索引
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_cache_key ON pipeline_route_cache(cache_key)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_coordinates ON pipeline_route_cache(start_lat, start_lon, end_lat, end_lon)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_expires_at ON pipeline_route_cache(expires_at)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_last_accessed ON pipeline_route_cache(last_accessed)
            ''')

            # 初始化统计记录
            cursor.execute('INSERT OR IGNORE INTO cache_statistics (id) VALUES (1)')

            conn.commit()
            conn.close()
            logger.debug("缓存数据库初始化完成")

        except Exception as e:
            logger.error(f"缓存数据库初始化失败: {e}")
            raise

    def _generate_cache_key(self, start_lat: float, start_lon: float,
                          end_lat: float, end_lon: float,
                          max_access_distance: float = None,
                          route_type: str = "single",
                          additional_params: Dict = None) -> str:
        """
        生成缓存键

        Args:
            start_lat, start_lon: 起点坐标
            end_lat, end_lon: 终点坐标
            max_access_distance: 最大接入距离
            route_type: 路径类型 ('single', 'clustered')
            additional_params: 额外参数

        Returns:
            缓存键字符串
        """
        # 构建基础键内容
        key_components = [
            f"{start_lat:.6f}",
            f"{start_lon:.6f}",
            f"{end_lat:.6f}",
            f"{end_lon:.6f}",
            f"{max_access_distance or 'unlimited'}",
            route_type
        ]

        # 添加配置哈希（确保配置变更时缓存失效）
        config_hash = self._calculate_config_hash()
        key_components.append(config_hash[:8])

        # 添加管道数据哈希（确保数据文件变更时缓存失效）
        data_hash = self._get_current_pipeline_data_hash()
        key_components.append(data_hash[:8])

        # 添加额外参数
        if additional_params:
            sorted_params = sorted(additional_params.items())
            param_str = "_".join([f"{k}:{v}" for k, v in sorted_params])
            key_components.append(param_str)

        # 生成MD5哈希
        key_string = "|".join(key_components)
        cache_key = hashlib.md5(key_string.encode('utf-8')).hexdigest()

        logger.debug(f"生成缓存键: {cache_key[:12]}... (来源: {key_string[:100]}...)")
        return cache_key

    def _calculate_config_hash(self) -> str:
        """计算配置哈希值"""
        config_data = {
            'max_access_distance_km': self.config.max_access_distance_km,
            'enable_geometry_caching': self.config.enable_geometry_caching,
            'enable_multi_pipeline_caching': self.config.enable_multi_pipeline_caching,
            'ttl_hours': self.config.settings.ttl_hours
        }
        config_str = json.dumps(config_data, sort_keys=True)
        return hashlib.md5(config_str.encode('utf-8')).hexdigest()

    def _get_current_pipeline_data_hash(self) -> str:
        """获取当前管道数据文件的哈希值"""
        # 检查是否需要更新管道数据哈希
        now = datetime.now()
        if (self.last_pipeline_check is None or
            (now - self.last_pipeline_check).total_seconds() > self.config.pipeline_data_check_interval_hours * 3600):

            self._update_pipeline_data_hashes()
            self.last_pipeline_check = now

        # 合并所有管道数据的哈希值
        all_hashes = sorted(self.pipeline_data_hashes.values())
        combined_hash = hashlib.md5("|".join(all_hashes).encode('utf-8')).hexdigest()
        return combined_hash

    def _update_pipeline_data_hashes(self):
        """更新管道数据文件哈希值"""
        try:
            # 获取项目GIS数据目录
            # 这里使用相对路径，实际应用中需要根据项目结构调整
            gis_data_dir = Path("../../gis_energy_mapping/gis_data_scraper/scraped_gis_data")
            if not gis_data_dir.exists():
                # 备用路径
                gis_data_dir = Path("../../../gis_energy_mapping/gis_data_scraper/scraped_gis_data")

            pipeline_files = [
                "crude_pipelines.geojson",
                "refined_product_pipelines.geojson",
                "natural_gas_pipelines.geojson"
            ]

            new_hashes = {}
            for filename in pipeline_files:
                file_path = gis_data_dir / filename
                if file_path.exists():
                    new_hashes[filename] = self._calculate_file_hash(str(file_path))
                else:
                    pass  # 静默处理文件不存在
                    new_hashes[filename] = "missing"

            # 检查是否有文件发生变化
            if self.pipeline_data_hashes:
                changed_files = []
                for filename, new_hash in new_hashes.items():
                    old_hash = self.pipeline_data_hashes.get(filename)
                    if old_hash and old_hash != new_hash:
                        changed_files.append(filename)

                if changed_files:
                    logger.debug(f"检测到管道数据文件变更: {', '.join(changed_files)}")
                    logger.debug("相关缓存条目将在下次访问时失效")

            self.pipeline_data_hashes = new_hashes

        except Exception as e:
            logger.error(f"更新管道数据文件哈希失败: {e}")

    def _calculate_file_hash(self, file_path: str) -> str:
        """计算文件哈希值"""
        try:
            hasher = hashlib.md5()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception as e:
            pass  # 静默处理哈希计算失败
            return "error"

    def get_cached_route(self, start_lat: float, start_lon: float,
                        end_lat: float, end_lon: float,
                        max_access_distance: float = None,
                        route_type: str = "single",
                        additional_params: Dict = None) -> Optional[Union[PipelineRoute, ClusteredPipelineRoute]]:
        """
        从缓存获取路径数据

        Args:
            start_lat, start_lon: 起点坐标
            end_lat, end_lon: 终点坐标
            max_access_distance: 最大接入距离
            route_type: 路径类型
            additional_params: 额外参数

        Returns:
            缓存的路径数据，如果不存在或过期返回None
        """
        if not self.config.settings.enabled:
            return None

        with self.lock:
            self.stats.total_requests += 1

            cache_key = self._generate_cache_key(
                start_lat, start_lon, end_lat, end_lon,
                max_access_distance, route_type, additional_params
            )

            # 首先检查内存缓存
            start_memory_check = time.time()
            if cache_key in self.memory_cache:
                entry = self.memory_cache[cache_key]
                if self._is_cache_entry_valid(entry):
                    entry.last_accessed = datetime.now()
                    entry.access_count += 1
                    self.stats.cache_hits += 1
                    read_time_ms = (time.time() - start_memory_check) * 1000
                    print(f"[管道路径缓存] 🟢 内存缓存命中: {cache_key[:8]}..., 耗时: {read_time_ms:.1f}ms")
                    return entry.route_data
                else:
                    # 内存缓存过期，删除
                    del self.memory_cache[cache_key]
                    print(f"[管道路径缓存] ⚠️ 内存缓存过期已删除: {cache_key[:8]}...")

            # 检查数据库缓存
            try:
                start_db_check = time.time()
                conn = sqlite3.connect(self.cache_db_path)
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT route_data, data_hash, calculation_time_ms, expires_at, access_count
                    FROM pipeline_route_cache
                    WHERE cache_key = ?
                ''', (cache_key,))

                result = cursor.fetchone()
                if result:
                    route_data_blob, data_hash, calc_time_ms, expires_at_str, access_count = result

                    # 检查是否过期
                    expires_at = datetime.fromisoformat(expires_at_str)
                    if datetime.now() > expires_at:
                        print(f"[管道路径缓存] ⏰ 数据库缓存已过期: {cache_key[:8]}..., 已删除")
                        cursor.execute('DELETE FROM pipeline_route_cache WHERE cache_key = ?', (cache_key,))
                        conn.commit()
                        conn.close()
                        self.stats.cache_misses += 1
                        return None

                    # 检查数据哈希是否匹配（检测数据文件变更）
                    current_data_hash = self._get_current_pipeline_data_hash()
                    if data_hash != current_data_hash:
                        print(f"[管道路径缓存] 🔄 管道数据已变更，缓存失效: {cache_key[:8]}..., 已删除")
                        cursor.execute('DELETE FROM pipeline_route_cache WHERE cache_key = ?', (cache_key,))
                        conn.commit()
                        conn.close()
                        self.stats.cache_misses += 1
                        return None

                    # 反序列化路径数据
                    try:
                        route_data = pickle.loads(route_data_blob)

                        # 更新访问统计
                        cursor.execute('''
                            UPDATE pipeline_route_cache
                            SET last_accessed = CURRENT_TIMESTAMP, access_count = access_count + 1
                            WHERE cache_key = ?
                        ''', (cache_key,))
                        conn.commit()

                        # 添加到内存缓存
                        if len(self.memory_cache) < self.memory_cache_max_size:
                            cache_entry = CacheEntry(
                                cache_key=cache_key,
                                route_data=route_data,
                                created_at=datetime.now(),
                                last_accessed=datetime.now(),
                                access_count=access_count + 1,
                                data_hash=current_data_hash,
                                calculation_time_ms=calc_time_ms
                            )
                            self.memory_cache[cache_key] = cache_entry

                        self.stats.cache_hits += 1
                        self.stats.total_time_saved_seconds += (calc_time_ms or 0) / 1000.0

                        read_time_ms = (time.time() - start_db_check) * 1000
                        print(f"[管道路径缓存] 🟡 数据库缓存命中: {cache_key[:8]}..., 耗时: {read_time_ms:.1f}ms, 原计算时间: {calc_time_ms or 0:.0f}ms")
                        conn.close()
                        return route_data

                    except Exception as e:
                        logger.error(f"反序列化缓存数据失败: {e}")
                        cursor.execute('DELETE FROM pipeline_route_cache WHERE cache_key = ?', (cache_key,))
                        conn.commit()

                conn.close()
                self.stats.cache_misses += 1
                print(f"[管道路径缓存] 🔴 缓存未命中: {cache_key[:8]}..., 需要重新计算")
                return None

            except Exception as e:
                print(f"[管道路径缓存] 🔴 缓存查询失败: {cache_key[:8]}..., 错误: {e}")
                self.stats.cache_misses += 1
                return None

    def cache_route(self, start_lat: float, start_lon: float,
                   end_lat: float, end_lon: float,
                   route_data: Union[PipelineRoute, ClusteredPipelineRoute],
                   max_access_distance: float = None,
                   route_type: str = "single",
                   calculation_time_ms: float = 0.0,
                   additional_params: Dict = None):
        """
        缓存路径数据

        Args:
            start_lat, start_lon: 起点坐标
            end_lat, end_lon: 终点坐标
            route_data: 路径数据
            max_access_distance: 最大接入距离
            route_type: 路径类型
            calculation_time_ms: 原始计算耗时
            additional_params: 额外参数
        """
        if not self.config.settings.enabled or not route_data:
            return

        with self.lock:
            try:
                start_cache_time = time.time()
                cache_key = self._generate_cache_key(
                    start_lat, start_lon, end_lat, end_lon,
                    max_access_distance, route_type, additional_params
                )

                # 计算过期时间
                expires_at = datetime.now() + timedelta(hours=self.config.settings.ttl_hours)
                current_data_hash = self._get_current_pipeline_data_hash()

                # 序列化路径数据
                route_data_blob = pickle.dumps(route_data)
                data_size = len(route_data_blob)

                # 存储到数据库
                conn = sqlite3.connect(self.cache_db_path)
                cursor = conn.cursor()

                cursor.execute('''
                    INSERT OR REPLACE INTO pipeline_route_cache
                    (cache_key, start_lat, start_lon, end_lat, end_lon, max_access_distance,
                     route_type, route_data, data_hash, calculation_time_ms, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    cache_key, start_lat, start_lon, end_lat, end_lon,
                    max_access_distance, route_type, route_data_blob,
                    current_data_hash, calculation_time_ms, expires_at.isoformat()
                ))

                conn.commit()
                conn.close()

                # 添加到内存缓存
                if len(self.memory_cache) < self.memory_cache_max_size:
                    cache_entry = CacheEntry(
                        cache_key=cache_key,
                        route_data=route_data,
                        created_at=datetime.now(),
                        last_accessed=datetime.now(),
                        access_count=1,
                        data_hash=current_data_hash,
                        calculation_time_ms=calculation_time_ms
                    )
                    self.memory_cache[cache_key] = cache_entry

                write_time_ms = (time.time() - start_cache_time) * 1000
                print(f"[管道路径缓存] 🟢 缓存保存成功: {cache_key[:8]}..., 大小: {data_size}字节, 耗时: {write_time_ms:.1f}ms")

            except Exception as e:
                print(f"[管道路径缓存] 🔴 缓存保存失败: {cache_key[:8] if 'cache_key' in locals() else '未知'}..., 错误: {e}")

    def _is_cache_entry_valid(self, entry: CacheEntry) -> bool:
        """检查缓存条目是否有效"""
        # 检查TTL
        age = datetime.now() - entry.created_at
        if age.total_seconds() > self.config.settings.ttl_hours * 3600:
            return False

        # 检查数据哈希
        current_hash = self._get_current_pipeline_data_hash()
        if entry.data_hash != current_hash:
            return False

        return True

    def cleanup_expired_cache(self) -> int:
        """
        清理过期缓存

        Returns:
            清理的条目数量
        """
        if not self.config.settings.auto_cleanup_enabled:
            return 0

        with self.lock:
            try:
                # 清理内存缓存中的过期条目
                memory_removed = 0
                expired_keys = []
                for key, entry in self.memory_cache.items():
                    if not self._is_cache_entry_valid(entry):
                        expired_keys.append(key)

                for key in expired_keys:
                    del self.memory_cache[key]
                    memory_removed += 1

                # 清理数据库中的过期条目
                conn = sqlite3.connect(self.cache_db_path)
                cursor = conn.cursor()

                # 删除过期条目
                cursor.execute('DELETE FROM pipeline_route_cache WHERE expires_at < ?',
                             (datetime.now().isoformat(),))
                db_removed = cursor.rowcount

                # 如果缓存条目过多，清理最少使用的条目
                cursor.execute('SELECT COUNT(*) FROM pipeline_route_cache')
                total_entries = cursor.fetchone()[0]

                if total_entries > self.config.settings.max_entries:
                    excess = total_entries - int(self.config.settings.max_entries * 0.8)  # 清理到80%
                    cursor.execute('''
                        DELETE FROM pipeline_route_cache
                        WHERE id IN (
                            SELECT id FROM pipeline_route_cache
                            ORDER BY access_count ASC, last_accessed ASC
                            LIMIT ?
                        )
                    ''', (excess,))
                    db_removed += cursor.rowcount

                # 更新统计信息
                cursor.execute('''
                    UPDATE cache_statistics
                    SET last_cleanup_time = CURRENT_TIMESTAMP
                    WHERE id = 1
                ''')

                conn.commit()
                conn.close()

                total_removed = memory_removed + db_removed
                if total_removed > 0:
                    pass  # 静默处理缓存清理

                self.stats.last_cleanup_time = datetime.now()
                return total_removed

            except Exception as e:
                logger.error(f"清理缓存失败: {e}")
                return 0

    def get_cache_statistics(self) -> CacheStatistics:
        """获取缓存统计信息"""
        with self.lock:
            try:
                conn = sqlite3.connect(self.cache_db_path)
                cursor = conn.cursor()

                # 获取当前统计
                cursor.execute('SELECT COUNT(*) FROM pipeline_route_cache')
                current_entries = cursor.fetchone()[0]

                cursor.execute('SELECT SUM(LENGTH(route_data)) FROM pipeline_route_cache')
                result = cursor.fetchone()
                current_size = result[0] or 0

                conn.close()

                # 更新统计信息
                self.stats.total_entries = current_entries
                self.stats.cache_size_bytes = current_size
                self.stats.hit_ratio = (self.stats.cache_hits / max(self.stats.total_requests, 1)) * 100
                if self.stats.cache_hits > 0:
                    self.stats.average_calculation_time_saved_ms = (
                        self.stats.total_time_saved_seconds * 1000 / self.stats.cache_hits
                    )
                self.stats.last_update_time = datetime.now()

                return self.stats

            except Exception as e:
                logger.error(f"获取缓存统计失败: {e}")
                return self.stats

    def _load_statistics(self):
        """从数据库加载统计信息"""
        try:
            conn = sqlite3.connect(self.cache_db_path)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT total_requests, cache_hits, cache_misses, total_time_saved_seconds,
                       last_cleanup_time FROM cache_statistics WHERE id = 1
            ''')
            result = cursor.fetchone()

            if result:
                total_req, hits, misses, time_saved, cleanup_time_str = result
                self.stats.total_requests = total_req or 0
                self.stats.cache_hits = hits or 0
                self.stats.cache_misses = misses or 0
                self.stats.total_time_saved_seconds = time_saved or 0.0
                if cleanup_time_str:
                    self.stats.last_cleanup_time = datetime.fromisoformat(cleanup_time_str)

            conn.close()
        except Exception as e:
            pass  # 静默处理统计加载失败

    def save_statistics(self):
        """保存统计信息到数据库"""
        try:
            with self.lock:
                conn = sqlite3.connect(self.cache_db_path)
                cursor = conn.cursor()

                cursor.execute('''
                    UPDATE cache_statistics
                    SET total_requests = ?, cache_hits = ?, cache_misses = ?,
                        total_time_saved_seconds = ?, last_update_time = CURRENT_TIMESTAMP
                    WHERE id = 1
                ''', (
                    self.stats.total_requests,
                    self.stats.cache_hits,
                    self.stats.cache_misses,
                    self.stats.total_time_saved_seconds
                ))

                conn.commit()
                conn.close()
        except Exception as e:
            logger.error(f"保存统计信息失败: {e}")

    def clear_cache(self, route_type: str = None):
        """
        清理缓存

        Args:
            route_type: 路径类型，如果为None则清理所有缓存
        """
        with self.lock:
            try:
                # 清理内存缓存
                if route_type:
                    keys_to_remove = []
                    for key, entry in self.memory_cache.items():
                        # 这里简化处理，实际中可能需要存储更多元信息来精确匹配
                        keys_to_remove.append(key)
                    for key in keys_to_remove:
                        if key in self.memory_cache:
                            del self.memory_cache[key]
                else:
                    self.memory_cache.clear()

                # 清理数据库缓存
                conn = sqlite3.connect(self.cache_db_path)
                cursor = conn.cursor()

                if route_type:
                    cursor.execute('DELETE FROM pipeline_route_cache WHERE route_type = ?', (route_type,))
                    pass  # 静默处理缓存清理信息
                else:
                    cursor.execute('DELETE FROM pipeline_route_cache')
                    pass  # 静默处理所有缓存清理信息

                conn.commit()
                conn.close()

            except Exception as e:
                logger.error(f"清理缓存失败: {e}")

    def get_cache_summary(self) -> str:
        """获取缓存摘要信息"""
        stats = self.get_cache_statistics()

        summary = []
        summary.append("=== 管道路径缓存统计摘要 ===")
        summary.append(f"缓存状态: {'启用' if self.config.settings.enabled else '禁用'}")
        summary.append(f"总请求数: {stats.total_requests:,}")
        summary.append(f"缓存命中: {stats.cache_hits:,}")
        summary.append(f"缓存未命中: {stats.cache_misses:,}")
        summary.append(f"命中率: {stats.hit_ratio:.1f}%")
        summary.append(f"当前条目: {stats.total_entries:,}")
        summary.append(f"缓存大小: {stats.cache_size_bytes / 1024 / 1024:.1f} MB")
        summary.append(f"内存缓存: {len(self.memory_cache)}/{self.memory_cache_max_size}")
        summary.append(f"平均节省计算时间: {stats.average_calculation_time_saved_ms:.1f} ms")
        summary.append(f"总节省时间: {stats.total_time_saved_seconds:.1f} 秒")

        if stats.last_cleanup_time:
            summary.append(f"上次清理: {stats.last_cleanup_time.strftime('%Y-%m-%d %H:%M:%S')}")
        if stats.last_update_time:
            summary.append(f"统计更新: {stats.last_update_time.strftime('%Y-%m-%d %H:%M:%S')}")

        summary.append(f"\n配置信息:")
        summary.append(f"TTL: {self.config.settings.ttl_hours} 小时")
        summary.append(f"最大条目: {self.config.settings.max_entries:,}")
        summary.append(f"最大大小: {self.config.settings.max_cache_size_mb} MB")
        summary.append(f"自动清理: {'是' if self.config.settings.auto_cleanup_enabled else '否'}")
        summary.append(f"几何缓存: {'是' if self.config.enable_geometry_caching else '否'}")
        summary.append(f"多管道缓存: {'是' if self.config.enable_multi_pipeline_caching else '否'}")

        return '\n'.join(summary)

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口，保存统计信息"""
        self.save_statistics()

# 全局管道路径缓存管理器实例
pipeline_cache_manager = PipelineRouteCacheManager()

def get_pipeline_cache_manager() -> PipelineRouteCacheManager:
    """获取全局管道路径缓存管理器实例"""
    return pipeline_cache_manager

if __name__ == "__main__":
    # 测试管道路径缓存管理器
    from pipeline_route_types import PipelineRoute

    print("=== 管道路径缓存管理器测试 ===")

    cache_manager = PipelineRouteCacheManager()

    # 模拟路径数据
    test_route = PipelineRoute(
        total_distance_km=150.5,
        access_distance_km=5.2,
        pipeline_distance_km=140.1,
        egress_distance_km=5.2,
        pipeline_types_used=['natural_gas'],
        route_found=True,
        calculation_method='test_method'
    )

    # 测试缓存存储和获取
    start_time = time.time()
    cache_manager.cache_route(
        39.9042, 116.4074,  # 北京
        31.2304, 121.4737,  # 上海
        test_route,
        max_access_distance=100.0,
        calculation_time_ms=1500.0
    )
    print(f"缓存存储耗时: {(time.time() - start_time) * 1000:.2f} ms")

    # 测试缓存获取
    start_time = time.time()
    cached_route = cache_manager.get_cached_route(
        39.9042, 116.4074,
        31.2304, 121.4737,
        max_access_distance=100.0
    )
    print(f"缓存获取耗时: {(time.time() - start_time) * 1000:.2f} ms")

    if cached_route:
        print("✅ 缓存命中!")
        print(f"总距离: {cached_route.total_distance_km} km")
    else:
        print("❌ 缓存未命中")

    # 显示统计信息
    print("\n" + cache_manager.get_cache_summary())