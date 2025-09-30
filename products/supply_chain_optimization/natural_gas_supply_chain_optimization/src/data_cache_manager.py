"""
Data Cache Manager for 500km Filtered Geographic Data
用于管理500km过滤地理数据的缓存管理器
"""

import os
import json
import pandas as pd
import logging
from typing import Dict, Optional, List
from datetime import datetime, timedelta
import hashlib

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataCacheManager:
    """
    数据缓存管理器 - 管理500km过滤后的地理数据缓存
    """
    
    def __init__(self, cache_base_dir: str = "cache", cache_expiry_hours: int = 24):
        """
        初始化缓存管理器
        
        Args:
            cache_base_dir: 缓存根目录
            cache_expiry_hours: 缓存过期时间(小时)
        """
        self.cache_base_dir = cache_base_dir
        self.cache_expiry_hours = cache_expiry_hours
        
        # 创建缓存目录结构
        self.filtered_data_dir = os.path.join(cache_base_dir, "filtered_500km_data")
        self.metadata_dir = os.path.join(cache_base_dir, "cache_metadata")
        
        os.makedirs(self.filtered_data_dir, exist_ok=True)
        os.makedirs(self.metadata_dir, exist_ok=True)
        
        # 缓存文件路径
        self.cache_files = {
            'lng_terminals': os.path.join(self.filtered_data_dir, 'lng_terminals_500km.csv'),
            'ng_pipelines': os.path.join(self.filtered_data_dir, 'ng_pipelines_500km.csv'),
            'renewable_plants': os.path.join(self.filtered_data_dir, 'renewable_plants_500km.csv')
        }
        
        # 元数据文件路径
        self.metadata_files = {
            'lng_terminals': os.path.join(self.metadata_dir, 'lng_terminals_metadata.json'),
            'ng_pipelines': os.path.join(self.metadata_dir, 'ng_pipelines_metadata.json'),
            'renewable_plants': os.path.join(self.metadata_dir, 'renewable_plants_metadata.json')
        }
        
        logger.info(f"缓存管理器初始化完成，缓存目录: {self.filtered_data_dir}")
    
    def _generate_file_hash(self, file_path: str) -> str:
        """
        生成文件内容的哈希值
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件内容的MD5哈希值
        """
        if not os.path.exists(file_path):
            return ""
            
        try:
            hasher = hashlib.md5()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception as e:
            logger.warning(f"计算文件哈希失败 {file_path}: {e}")
            return ""
    
    def _save_cache_metadata(self, data_type: str, source_file: str, filtered_count: int):
        """
        保存缓存元数据
        
        Args:
            data_type: 数据类型 ('lng_terminals', 'ng_pipelines', 'renewable_plants')
            source_file: 源文件路径
            filtered_count: 过滤后的数据条数
        """
        metadata = {
            'created_at': datetime.now().isoformat(),
            'source_file': source_file,
            'source_file_hash': self._generate_file_hash(source_file),
            'filtered_count': filtered_count,
            'filter_criteria': '500km radius from Beijing (39.9042, 116.4074)',
            'cache_version': '1.0'
        }
        
        try:
            with open(self.metadata_files[data_type], 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            logger.info(f"缓存元数据已保存: {data_type}")
        except Exception as e:
            logger.error(f"保存缓存元数据失败 {data_type}: {e}")
    
    def _load_cache_metadata(self, data_type: str) -> Optional[Dict]:
        """
        加载缓存元数据
        
        Args:
            data_type: 数据类型
            
        Returns:
            缓存元数据字典，如果不存在或无效返回None
        """
        metadata_file = self.metadata_files[data_type]
        if not os.path.exists(metadata_file):
            return None
            
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            return metadata
        except Exception as e:
            logger.warning(f"加载缓存元数据失败 {data_type}: {e}")
            return None
    
    def is_cache_valid(self, data_type: str, source_file: str) -> bool:
        """
        检查缓存是否有效
        
        Args:
            data_type: 数据类型
            source_file: 源文件路径
            
        Returns:
            缓存是否有效
        """
        # 检查缓存文件是否存在
        cache_file = self.cache_files[data_type]
        if not os.path.exists(cache_file):
            logger.debug(f"缓存文件不存在: {cache_file}")
            return False
        
        # 检查元数据
        metadata = self._load_cache_metadata(data_type)
        if not metadata:
            logger.debug(f"缓存元数据不存在: {data_type}")
            return False
        
        # 检查缓存是否过期
        created_at = datetime.fromisoformat(metadata['created_at'])
        expiry_time = created_at + timedelta(hours=self.cache_expiry_hours)
        if datetime.now() > expiry_time:
            logger.info(f"缓存已过期: {data_type} (创建时间: {created_at})")
            return False
        
        # 检查源文件是否变更
        current_hash = self._generate_file_hash(source_file)
        cached_hash = metadata.get('source_file_hash', '')
        if current_hash != cached_hash:
            logger.info(f"源文件已变更: {data_type}")
            return False
        
        logger.debug(f"缓存有效: {data_type}")
        return True
    
    def save_filtered_data(self, data_type: str, filtered_df: pd.DataFrame, source_file: str):
        """
        保存过滤后的数据到缓存
        
        Args:
            data_type: 数据类型
            filtered_df: 过滤后的DataFrame
            source_file: 源文件路径
        """
        try:
            cache_file = self.cache_files[data_type]
            filtered_df.to_csv(cache_file, index=False, encoding='utf-8')
            
            # 保存元数据
            self._save_cache_metadata(data_type, source_file, len(filtered_df))
            
            logger.info(f"过滤数据已缓存: {data_type} ({len(filtered_df)} 条记录)")
        except Exception as e:
            logger.error(f"保存过滤数据失败 {data_type}: {e}")
    
    def load_filtered_data(self, data_type: str) -> Optional[pd.DataFrame]:
        """
        从缓存加载过滤后的数据
        
        Args:
            data_type: 数据类型
            
        Returns:
            过滤后的DataFrame，如果缓存不存在或无效返回None
        """
        cache_file = self.cache_files[data_type]
        if not os.path.exists(cache_file):
            return None
        
        try:
            df = pd.read_csv(cache_file, encoding='utf-8')
            logger.info(f"从缓存加载数据: {data_type} ({len(df)} 条记录)")
            return df
        except Exception as e:
            logger.error(f"从缓存加载数据失败 {data_type}: {e}")
            return None
    
    def clear_cache(self, data_type: str = None):
        """
        清理缓存
        
        Args:
            data_type: 数据类型，如果为None则清理所有缓存
        """
        if data_type:
            data_types = [data_type]
        else:
            data_types = list(self.cache_files.keys())
        
        for dt in data_types:
            # 删除缓存文件
            cache_file = self.cache_files[dt]
            if os.path.exists(cache_file):
                try:
                    os.remove(cache_file)
                    logger.info(f"已删除缓存文件: {cache_file}")
                except Exception as e:
                    logger.error(f"删除缓存文件失败 {cache_file}: {e}")
            
            # 删除元数据文件
            metadata_file = self.metadata_files[dt]
            if os.path.exists(metadata_file):
                try:
                    os.remove(metadata_file)
                    logger.info(f"已删除元数据文件: {metadata_file}")
                except Exception as e:
                    logger.error(f"删除元数据文件失败 {metadata_file}: {e}")
    
    def get_cache_info(self) -> Dict:
        """
        获取缓存信息
        
        Returns:
            缓存信息字典
        """
        cache_info = {}
        
        for data_type in self.cache_files.keys():
            cache_file = self.cache_files[data_type]
            metadata = self._load_cache_metadata(data_type)
            
            info = {
                'cache_exists': os.path.exists(cache_file),
                'metadata_exists': metadata is not None
            }
            
            if info['cache_exists']:
                try:
                    df = pd.read_csv(cache_file)
                    info['record_count'] = len(df)
                    info['file_size'] = os.path.getsize(cache_file)
                except:
                    info['record_count'] = 0
                    info['file_size'] = 0
            
            if metadata:
                info['created_at'] = metadata.get('created_at')
                info['source_file'] = metadata.get('source_file')
                info['filtered_count'] = metadata.get('filtered_count')
            
            cache_info[data_type] = info
        
        return cache_info

    # ======= 路径规划缓存扩展功能 =======

    def setup_path_planning_cache(self):
        """设置路径规划相关的缓存目录和文件结构"""
        # 创建路径规划缓存目录
        self.path_planning_dir = os.path.join(self.cache_base_dir, "path_planning_cache")
        os.makedirs(self.path_planning_dir, exist_ok=True)

        # GraphHopper路径缓存
        self.graphhopper_cache_dir = os.path.join(self.path_planning_dir, "graphhopper_routes")
        os.makedirs(self.graphhopper_cache_dir, exist_ok=True)

        # 管道路径缓存
        self.pipeline_cache_dir = os.path.join(self.path_planning_dir, "pipeline_routes")
        os.makedirs(self.pipeline_cache_dir, exist_ok=True)

        # 路径规划缓存文件
        self.path_planning_cache_files = {
            'graphhopper_routes': os.path.join(self.graphhopper_cache_dir, 'route_cache.db'),
            'pipeline_routes': os.path.join(self.pipeline_cache_dir, 'pipeline_cache.db'),
            'route_statistics': os.path.join(self.path_planning_dir, 'route_statistics.json')
        }

        # 路径规划元数据文件
        self.path_planning_metadata_files = {
            'graphhopper_config': os.path.join(self.metadata_dir, 'graphhopper_cache_metadata.json'),
            'pipeline_config': os.path.join(self.metadata_dir, 'pipeline_cache_metadata.json'),
            'unified_config': os.path.join(self.metadata_dir, 'unified_cache_config.json')
        }

        logger.info(f"路径规划缓存结构已设置，目录: {self.path_planning_dir}")

    def get_path_planning_cache_info(self) -> Dict:
        """获取路径规划缓存信息"""
        if not hasattr(self, 'path_planning_dir'):
            self.setup_path_planning_cache()

        cache_info = {}

        # GraphHopper缓存信息
        graphhopper_db = self.path_planning_cache_files.get('graphhopper_routes')
        cache_info['graphhopper_routes'] = {
            'cache_exists': os.path.exists(graphhopper_db) if graphhopper_db else False,
            'cache_file': graphhopper_db,
            'cache_type': 'SQLite数据库'
        }

        if cache_info['graphhopper_routes']['cache_exists']:
            try:
                import sqlite3
                conn = sqlite3.connect(graphhopper_db)
                cursor = conn.cursor()

                # 检查表是否存在
                cursor.execute("""
                    SELECT name FROM sqlite_master WHERE type='table' AND name='route_cache'
                """)
                table_exists = cursor.fetchone() is not None

                if table_exists:
                    cursor.execute("SELECT COUNT(*) FROM route_cache")
                    cache_info['graphhopper_routes']['route_count'] = cursor.fetchone()[0]

                    cursor.execute("SELECT MAX(created_at) FROM route_cache")
                    last_update = cursor.fetchone()[0]
                    cache_info['graphhopper_routes']['last_update'] = last_update
                else:
                    cache_info['graphhopper_routes']['route_count'] = 0

                conn.close()
            except Exception as e:
                cache_info['graphhopper_routes']['error'] = str(e)

        # 管道路径缓存信息
        pipeline_db = self.path_planning_cache_files.get('pipeline_routes')
        cache_info['pipeline_routes'] = {
            'cache_exists': os.path.exists(pipeline_db) if pipeline_db else False,
            'cache_file': pipeline_db,
            'cache_type': 'SQLite数据库'
        }

        if cache_info['pipeline_routes']['cache_exists']:
            try:
                import sqlite3
                conn = sqlite3.connect(pipeline_db)
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT name FROM sqlite_master WHERE type='table' AND name='pipeline_routes'
                """)
                table_exists = cursor.fetchone() is not None

                if table_exists:
                    cursor.execute("SELECT COUNT(*) FROM pipeline_routes")
                    cache_info['pipeline_routes']['route_count'] = cursor.fetchone()[0]

                    cursor.execute("SELECT MAX(created_at) FROM pipeline_routes")
                    last_update = cursor.fetchone()[0]
                    cache_info['pipeline_routes']['last_update'] = last_update
                else:
                    cache_info['pipeline_routes']['route_count'] = 0

                conn.close()
            except Exception as e:
                cache_info['pipeline_routes']['error'] = str(e)

        # 路径规划统计信息
        stats_file = self.path_planning_cache_files.get('route_statistics')
        cache_info['route_statistics'] = {
            'stats_exists': os.path.exists(stats_file) if stats_file else False,
            'stats_file': stats_file
        }

        if cache_info['route_statistics']['stats_exists']:
            try:
                with open(stats_file, 'r', encoding='utf-8') as f:
                    stats_data = json.load(f)
                cache_info['route_statistics']['data'] = stats_data
            except Exception as e:
                cache_info['route_statistics']['error'] = str(e)

        return cache_info

    def clear_path_planning_cache(self, cache_type: str = None) -> Dict:
        """
        清理路径规划缓存

        Args:
            cache_type: 缓存类型 ('graphhopper', 'pipeline', 'all', None=all)

        Returns:
            清理结果信息
        """
        if not hasattr(self, 'path_planning_dir'):
            self.setup_path_planning_cache()

        result = {
            'cleared_files': [],
            'errors': [],
            'total_freed_space_mb': 0
        }

        cache_types_to_clear = []
        if cache_type is None or cache_type == 'all':
            cache_types_to_clear = ['graphhopper_routes', 'pipeline_routes', 'route_statistics']
        elif cache_type == 'graphhopper':
            cache_types_to_clear = ['graphhopper_routes']
        elif cache_type == 'pipeline':
            cache_types_to_clear = ['pipeline_routes']
        elif cache_type == 'statistics':
            cache_types_to_clear = ['route_statistics']

        for cache_key in cache_types_to_clear:
            cache_file = self.path_planning_cache_files.get(cache_key)
            if cache_file and os.path.exists(cache_file):
                try:
                    file_size = os.path.getsize(cache_file)
                    os.remove(cache_file)
                    result['cleared_files'].append(cache_file)
                    result['total_freed_space_mb'] += file_size / (1024 * 1024)
                    logger.info(f"已清理路径规划缓存文件: {cache_file}")
                except Exception as e:
                    error_msg = f"清理缓存文件失败 {cache_file}: {e}"
                    result['errors'].append(error_msg)
                    logger.error(error_msg)

        # 清理元数据文件
        for metadata_key, metadata_file in self.path_planning_metadata_files.items():
            if os.path.exists(metadata_file):
                try:
                    os.remove(metadata_file)
                    result['cleared_files'].append(metadata_file)
                    logger.info(f"已清理路径规划元数据文件: {metadata_file}")
                except Exception as e:
                    error_msg = f"清理元数据文件失败 {metadata_file}: {e}"
                    result['errors'].append(error_msg)
                    logger.error(error_msg)

        logger.info(f"路径规划缓存清理完成，释放空间: {result['total_freed_space_mb']:.2f}MB")
        return result

    def save_route_planning_statistics(self, stats: Dict):
        """
        保存路径规划统计信息

        Args:
            stats: 统计信息字典
        """
        if not hasattr(self, 'path_planning_dir'):
            self.setup_path_planning_cache()

        stats_file = self.path_planning_cache_files['route_statistics']

        # 添加时间戳
        stats['saved_at'] = datetime.now().isoformat()
        stats['cache_manager_version'] = '2.0_extended'

        try:
            with open(stats_file, 'w', encoding='utf-8') as f:
                json.dump(stats, f, ensure_ascii=False, indent=2, default=str)
            logger.info(f"路径规划统计信息已保存: {stats_file}")
        except Exception as e:
            logger.error(f"保存路径规划统计信息失败: {e}")

    def load_route_planning_statistics(self) -> Optional[Dict]:
        """
        加载路径规划统计信息

        Returns:
            统计信息字典，如果不存在返回None
        """
        if not hasattr(self, 'path_planning_dir'):
            self.setup_path_planning_cache()

        stats_file = self.path_planning_cache_files['route_statistics']

        if not os.path.exists(stats_file):
            return None

        try:
            with open(stats_file, 'r', encoding='utf-8') as f:
                stats = json.load(f)
            return stats
        except Exception as e:
            logger.warning(f"加载路径规划统计信息失败: {e}")
            return None

    def validate_path_planning_cache_integrity(self) -> Dict:
        """
        验证路径规划缓存完整性

        Returns:
            验证结果信息
        """
        if not hasattr(self, 'path_planning_dir'):
            self.setup_path_planning_cache()

        validation_result = {
            'overall_status': 'healthy',
            'cache_files_status': {},
            'recommendations': []
        }

        # 检查GraphHopper缓存数据库
        graphhopper_db = self.path_planning_cache_files['graphhopper_routes']
        if os.path.exists(graphhopper_db):
            try:
                import sqlite3
                conn = sqlite3.connect(graphhopper_db)
                cursor = conn.cursor()

                # 检查表结构
                cursor.execute("PRAGMA table_info(route_cache)")
                columns = cursor.fetchall()

                expected_columns = ['start_lat', 'start_lon', 'end_lat', 'end_lon',
                                  'distance_km', 'time_hours', 'created_at', 'expires_at']
                actual_columns = [col[1] for col in columns]

                validation_result['cache_files_status']['graphhopper'] = {
                    'status': 'valid',
                    'table_exists': True,
                    'columns_valid': all(col in actual_columns for col in expected_columns)
                }

                conn.close()
            except Exception as e:
                validation_result['cache_files_status']['graphhopper'] = {
                    'status': 'error',
                    'error': str(e)
                }
                validation_result['overall_status'] = 'warning'
        else:
            validation_result['cache_files_status']['graphhopper'] = {
                'status': 'missing'
            }

        # 检查管道缓存数据库
        pipeline_db = self.path_planning_cache_files['pipeline_routes']
        if os.path.exists(pipeline_db):
            try:
                import sqlite3
                conn = sqlite3.connect(pipeline_db)
                cursor = conn.cursor()

                cursor.execute("PRAGMA table_info(pipeline_routes)")
                columns = cursor.fetchall()

                validation_result['cache_files_status']['pipeline'] = {
                    'status': 'valid',
                    'table_exists': len(columns) > 0
                }

                conn.close()
            except Exception as e:
                validation_result['cache_files_status']['pipeline'] = {
                    'status': 'error',
                    'error': str(e)
                }
                validation_result['overall_status'] = 'warning'
        else:
            validation_result['cache_files_status']['pipeline'] = {
                'status': 'missing'
            }

        # 生成建议
        if validation_result['cache_files_status']['graphhopper'].get('status') == 'missing':
            validation_result['recommendations'].append("GraphHopper缓存数据库不存在，首次使用时将自动创建")

        if validation_result['cache_files_status']['pipeline'].get('status') == 'missing':
            validation_result['recommendations'].append("管道路径缓存数据库不存在，首次使用时将自动创建")

        if any(status.get('status') == 'error' for status in validation_result['cache_files_status'].values()):
            validation_result['overall_status'] = 'error'
            validation_result['recommendations'].append("发现缓存文件错误，建议清理并重新构建缓存")

        return validation_result

    def get_comprehensive_cache_info(self) -> Dict:
        """获取包含路径规划缓存在内的综合缓存信息"""
        # 获取原有的地理数据缓存信息
        geo_cache_info = self.get_cache_info()

        # 获取路径规划缓存信息
        path_planning_info = self.get_path_planning_cache_info()

        # 获取验证结果
        validation_result = self.validate_path_planning_cache_integrity()

        return {
            'geo_data_cache': geo_cache_info,
            'path_planning_cache': path_planning_info,
            'cache_integrity': validation_result,
            'cache_manager_info': {
                'version': '2.0_extended_with_path_planning',
                'base_dir': self.cache_base_dir,
                'expiry_hours': self.cache_expiry_hours,
                'total_cache_types': len(geo_cache_info) + len(path_planning_info)
            }
        }


# 全局缓存管理器实例（扩展版本）
cache_manager = DataCacheManager()

# 自动设置路径规划缓存支持
cache_manager.setup_path_planning_cache()