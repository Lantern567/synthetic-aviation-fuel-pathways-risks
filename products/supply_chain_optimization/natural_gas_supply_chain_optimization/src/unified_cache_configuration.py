"""
Unified Cache Configuration Manager
统一缓存配置管理器 - 为所有缓存模块提供统一的配置管理
"""

import os
import json
import logging
from typing import Dict, Any, Optional, Union, List
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class CacheSettings:
    """缓存设置数据类"""
    enabled: bool = True
    ttl_hours: int = 24
    max_cache_size_mb: int = 500
    max_entries: int = 10000
    compression_enabled: bool = True
    auto_cleanup_enabled: bool = True
    cleanup_threshold_ratio: float = 0.8
    backup_enabled: bool = False

@dataclass
class GraphHopperCacheConfig:
    """GraphHopper路径规划缓存配置"""
    database_path: str = "cache/graphhopper_routes/route_cache.db"
    settings: CacheSettings = None
    request_timeout: int = 30
    max_retries: int = 3
    enable_batch_processing: bool = True
    preload_popular_routes: bool = False

    def __post_init__(self):
        if self.settings is None:
            self.settings = CacheSettings(
                ttl_hours=48,  # GraphHopper缓存保持较长时间
                max_cache_size_mb=1000,
                max_entries=50000
            )

@dataclass
class PipelineCacheConfig:
    """管道路径规划缓存配置"""
    database_path: str = "cache/pipeline_routes/pipeline_cache.db"
    settings: CacheSettings = None
    max_access_distance_km: float = 100.0
    enable_geometry_caching: bool = True
    enable_multi_pipeline_caching: bool = True
    pipeline_data_check_interval_hours: int = 6

    def __post_init__(self):
        if self.settings is None:
            self.settings = CacheSettings(
                ttl_hours=72,  # 管道基础设施变化较少，缓存更久
                max_cache_size_mb=2000,
                max_entries=100000
            )

@dataclass
class DataCacheConfig:
    """数据缓存配置（扩展现有data_cache_manager.py的配置）"""
    base_directory: str = "cache"
    settings: CacheSettings = None
    geographic_filter_radius_km: float = 500.0
    enable_file_hash_validation: bool = True
    enable_metadata_tracking: bool = True

    def __post_init__(self):
        if self.settings is None:
            self.settings = CacheSettings(
                ttl_hours=24,
                max_cache_size_mb=500,
                max_entries=1000
            )

class UnifiedCacheConfiguration:
    """
    统一缓存配置管理器
    提供所有缓存模块的统一配置管理功能
    """

    def __init__(self, config_file: Optional[str] = None):
        """
        初始化缓存配置管理器

        Args:
            config_file: 配置文件路径，如果为None则使用默认路径
        """
        self.config_file = config_file or "cache/cache_configuration.json"
        self.config_dir = os.path.dirname(self.config_file)

        # 默认配置
        self.graphhopper_config = GraphHopperCacheConfig()
        self.pipeline_config = PipelineCacheConfig()
        self.data_config = DataCacheConfig()

        # 全局设置
        self.global_settings = {
            "cache_root_directory": "cache",
            "enable_performance_monitoring": True,
            "enable_cache_statistics": True,
            "log_cache_operations": True,
            "enable_cache_warmup": False,
            "warmup_schedule": "daily",
            "maintenance_schedule": "weekly"
        }

        # 创建配置目录
        os.makedirs(self.config_dir, exist_ok=True)

        # 加载现有配置（如果存在）
        self.load_configuration()

        pass  # 静默初始化完成

    def load_configuration(self) -> bool:
        """
        从配置文件加载配置

        Returns:
            是否成功加载配置
        """
        if not os.path.exists(self.config_file):
            pass  # 静默使用默认配置
            return False

        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)

            # 加载GraphHopper配置
            if 'graphhopper' in config_data:
                gh_config = config_data['graphhopper']
                self.graphhopper_config.database_path = gh_config.get('database_path',
                                                                    self.graphhopper_config.database_path)
                self.graphhopper_config.request_timeout = gh_config.get('request_timeout',
                                                                       self.graphhopper_config.request_timeout)
                self.graphhopper_config.max_retries = gh_config.get('max_retries',
                                                                   self.graphhopper_config.max_retries)
                self.graphhopper_config.enable_batch_processing = gh_config.get('enable_batch_processing',
                                                                               self.graphhopper_config.enable_batch_processing)
                self.graphhopper_config.preload_popular_routes = gh_config.get('preload_popular_routes',
                                                                              self.graphhopper_config.preload_popular_routes)

                # 加载设置
                if 'settings' in gh_config:
                    self._load_cache_settings(gh_config['settings'], self.graphhopper_config.settings)

            # 加载管道配置
            if 'pipeline' in config_data:
                pipe_config = config_data['pipeline']
                self.pipeline_config.database_path = pipe_config.get('database_path',
                                                                   self.pipeline_config.database_path)
                self.pipeline_config.max_access_distance_km = pipe_config.get('max_access_distance_km',
                                                                             self.pipeline_config.max_access_distance_km)
                self.pipeline_config.enable_geometry_caching = pipe_config.get('enable_geometry_caching',
                                                                              self.pipeline_config.enable_geometry_caching)
                self.pipeline_config.enable_multi_pipeline_caching = pipe_config.get('enable_multi_pipeline_caching',
                                                                                    self.pipeline_config.enable_multi_pipeline_caching)
                self.pipeline_config.pipeline_data_check_interval_hours = pipe_config.get('pipeline_data_check_interval_hours',
                                                                                         self.pipeline_config.pipeline_data_check_interval_hours)

                if 'settings' in pipe_config:
                    self._load_cache_settings(pipe_config['settings'], self.pipeline_config.settings)

            # 加载数据配置
            if 'data' in config_data:
                data_config_dict = config_data['data']
                self.data_config.base_directory = data_config_dict.get('base_directory',
                                                                     self.data_config.base_directory)
                self.data_config.geographic_filter_radius_km = data_config_dict.get('geographic_filter_radius_km',
                                                                                   self.data_config.geographic_filter_radius_km)
                self.data_config.enable_file_hash_validation = data_config_dict.get('enable_file_hash_validation',
                                                                                   self.data_config.enable_file_hash_validation)
                self.data_config.enable_metadata_tracking = data_config_dict.get('enable_metadata_tracking',
                                                                                self.data_config.enable_metadata_tracking)

                if 'settings' in data_config_dict:
                    self._load_cache_settings(data_config_dict['settings'], self.data_config.settings)

            # 加载全局设置
            if 'global_settings' in config_data:
                self.global_settings.update(config_data['global_settings'])

            pass  # 静默配置加载成功
            return True

        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            return False

    def _load_cache_settings(self, settings_dict: Dict, cache_settings: CacheSettings):
        """加载缓存设置"""
        if 'enabled' in settings_dict:
            cache_settings.enabled = settings_dict['enabled']
        if 'ttl_hours' in settings_dict:
            cache_settings.ttl_hours = settings_dict['ttl_hours']
        if 'max_cache_size_mb' in settings_dict:
            cache_settings.max_cache_size_mb = settings_dict['max_cache_size_mb']
        if 'max_entries' in settings_dict:
            cache_settings.max_entries = settings_dict['max_entries']
        if 'compression_enabled' in settings_dict:
            cache_settings.compression_enabled = settings_dict['compression_enabled']
        if 'auto_cleanup_enabled' in settings_dict:
            cache_settings.auto_cleanup_enabled = settings_dict['auto_cleanup_enabled']
        if 'cleanup_threshold_ratio' in settings_dict:
            cache_settings.cleanup_threshold_ratio = settings_dict['cleanup_threshold_ratio']
        if 'backup_enabled' in settings_dict:
            cache_settings.backup_enabled = settings_dict['backup_enabled']

    def save_configuration(self) -> bool:
        """
        保存配置到文件

        Returns:
            是否成功保存配置
        """
        try:
            config_data = {
                'graphhopper': {
                    'database_path': self.graphhopper_config.database_path,
                    'request_timeout': self.graphhopper_config.request_timeout,
                    'max_retries': self.graphhopper_config.max_retries,
                    'enable_batch_processing': self.graphhopper_config.enable_batch_processing,
                    'preload_popular_routes': self.graphhopper_config.preload_popular_routes,
                    'settings': asdict(self.graphhopper_config.settings)
                },
                'pipeline': {
                    'database_path': self.pipeline_config.database_path,
                    'max_access_distance_km': self.pipeline_config.max_access_distance_km,
                    'enable_geometry_caching': self.pipeline_config.enable_geometry_caching,
                    'enable_multi_pipeline_caching': self.pipeline_config.enable_multi_pipeline_caching,
                    'pipeline_data_check_interval_hours': self.pipeline_config.pipeline_data_check_interval_hours,
                    'settings': asdict(self.pipeline_config.settings)
                },
                'data': {
                    'base_directory': self.data_config.base_directory,
                    'geographic_filter_radius_km': self.data_config.geographic_filter_radius_km,
                    'enable_file_hash_validation': self.data_config.enable_file_hash_validation,
                    'enable_metadata_tracking': self.data_config.enable_metadata_tracking,
                    'settings': asdict(self.data_config.settings)
                },
                'global_settings': self.global_settings,
                'config_version': '1.0',
                'last_updated': datetime.now().isoformat()
            }

            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)

            pass  # 静默配置保存成功
            return True

        except Exception as e:
            logger.error(f"保存配置文件失败: {e}")
            return False

    def get_graphhopper_config(self) -> GraphHopperCacheConfig:
        """获取GraphHopper缓存配置"""
        return self.graphhopper_config

    def get_pipeline_config(self) -> PipelineCacheConfig:
        """获取管道路径缓存配置"""
        return self.pipeline_config

    def get_data_config(self) -> DataCacheConfig:
        """获取数据缓存配置"""
        return self.data_config

    def get_global_settings(self) -> Dict[str, Any]:
        """获取全局设置"""
        return self.global_settings.copy()

    def update_graphhopper_config(self, **kwargs):
        """更新GraphHopper配置"""
        for key, value in kwargs.items():
            if hasattr(self.graphhopper_config, key):
                setattr(self.graphhopper_config, key, value)
            elif hasattr(self.graphhopper_config.settings, key):
                setattr(self.graphhopper_config.settings, key, value)

    def update_pipeline_config(self, **kwargs):
        """更新管道路径配置"""
        for key, value in kwargs.items():
            if hasattr(self.pipeline_config, key):
                setattr(self.pipeline_config, key, value)
            elif hasattr(self.pipeline_config.settings, key):
                setattr(self.pipeline_config.settings, key, value)

    def update_data_config(self, **kwargs):
        """更新数据缓存配置"""
        for key, value in kwargs.items():
            if hasattr(self.data_config, key):
                setattr(self.data_config, key, value)
            elif hasattr(self.data_config.settings, key):
                setattr(self.data_config.settings, key, value)

    def update_global_settings(self, **kwargs):
        """更新全局设置"""
        self.global_settings.update(kwargs)

    def reset_to_defaults(self):
        """重置所有配置为默认值"""
        self.graphhopper_config = GraphHopperCacheConfig()
        self.pipeline_config = PipelineCacheConfig()
        self.data_config = DataCacheConfig()
        self.global_settings = {
            "cache_root_directory": "cache",
            "enable_performance_monitoring": True,
            "enable_cache_statistics": True,
            "log_cache_operations": True,
            "enable_cache_warmup": False,
            "warmup_schedule": "daily",
            "maintenance_schedule": "weekly"
        }
        pass  # 静默配置重置

    def validate_configuration(self) -> Dict[str, List[str]]:
        """
        验证配置的有效性

        Returns:
            Dict包含验证错误信息，按模块分组
        """
        errors = {
            'graphhopper': [],
            'pipeline': [],
            'data': [],
            'global': []
        }

        # 验证GraphHopper配置
        gh_config = self.graphhopper_config
        if gh_config.settings.ttl_hours < 1:
            errors['graphhopper'].append("TTL必须大于1小时")
        if gh_config.settings.max_cache_size_mb < 10:
            errors['graphhopper'].append("缓存大小必须至少10MB")
        if gh_config.settings.max_entries < 100:
            errors['graphhopper'].append("最大条目数必须至少100")
        if not (0.1 <= gh_config.settings.cleanup_threshold_ratio <= 1.0):
            errors['graphhopper'].append("清理阈值比例必须在0.1到1.0之间")

        # 验证管道配置
        pipe_config = self.pipeline_config
        if pipe_config.max_access_distance_km < 1:
            errors['pipeline'].append("最大接入距离必须大于1km")
        if pipe_config.pipeline_data_check_interval_hours < 1:
            errors['pipeline'].append("管道数据检查间隔必须至少1小时")
        if pipe_config.settings.ttl_hours < 1:
            errors['pipeline'].append("TTL必须大于1小时")

        # 验证数据配置
        data_config = self.data_config
        if data_config.geographic_filter_radius_km < 10:
            errors['data'].append("地理过滤半径必须至少10km")

        # 验证全局设置
        valid_schedules = ['daily', 'weekly', 'monthly']
        if self.global_settings.get('warmup_schedule') not in valid_schedules:
            errors['global'].append("预热计划必须是daily、weekly或monthly")
        if self.global_settings.get('maintenance_schedule') not in valid_schedules:
            errors['global'].append("维护计划必须是daily、weekly或monthly")

        return errors

    def get_cache_directories(self) -> Dict[str, str]:
        """
        获取所有缓存目录路径

        Returns:
            缓存目录路径字典
        """
        root_dir = self.global_settings.get('cache_root_directory', 'cache')

        directories = {
            'root': root_dir,
            'graphhopper': os.path.dirname(self.graphhopper_config.database_path),
            'pipeline': os.path.dirname(self.pipeline_config.database_path),
            'data': self.data_config.base_directory,
            'metadata': os.path.join(root_dir, 'cache_metadata'),
            'performance': os.path.join(root_dir, 'performance_logs'),
            'backups': os.path.join(root_dir, 'backups')
        }

        return directories

    def ensure_directories_exist(self):
        """确保所有缓存目录存在"""
        directories = self.get_cache_directories()

        for dir_type, dir_path in directories.items():
            try:
                os.makedirs(dir_path, exist_ok=True)
                pass  # 静默目录创建成功
            except Exception as e:
                logger.error(f"创建缓存目录失败 {dir_type} ({dir_path}): {e}")

    def get_configuration_summary(self) -> str:
        """
        获取配置摘要信息

        Returns:
            配置摘要字符串
        """
        summary = []
        summary.append("=== 统一缓存配置摘要 ===")

        # GraphHopper配置
        gh = self.graphhopper_config
        summary.append(f"\n[GraphHopper路径规划缓存]")
        summary.append(f"  启用状态: {'是' if gh.settings.enabled else '否'}")
        summary.append(f"  TTL: {gh.settings.ttl_hours}小时")
        summary.append(f"  最大大小: {gh.settings.max_cache_size_mb}MB")
        summary.append(f"  最大条目: {gh.settings.max_entries:,}")
        summary.append(f"  数据库路径: {gh.database_path}")
        summary.append(f"  批量处理: {'是' if gh.enable_batch_processing else '否'}")

        # 管道配置
        pipe = self.pipeline_config
        summary.append(f"\n[管道路径规划缓存]")
        summary.append(f"  启用状态: {'是' if pipe.settings.enabled else '否'}")
        summary.append(f"  TTL: {pipe.settings.ttl_hours}小时")
        summary.append(f"  最大大小: {pipe.settings.max_cache_size_mb}MB")
        summary.append(f"  最大条目: {pipe.settings.max_entries:,}")
        summary.append(f"  数据库路径: {pipe.database_path}")
        summary.append(f"  几何信息缓存: {'是' if pipe.enable_geometry_caching else '否'}")
        summary.append(f"  多管道缓存: {'是' if pipe.enable_multi_pipeline_caching else '否'}")

        # 数据配置
        data = self.data_config
        summary.append(f"\n[数据缓存]")
        summary.append(f"  启用状态: {'是' if data.settings.enabled else '否'}")
        summary.append(f"  TTL: {data.settings.ttl_hours}小时")
        summary.append(f"  基础目录: {data.base_directory}")
        summary.append(f"  地理过滤半径: {data.geographic_filter_radius_km}km")
        summary.append(f"  文件哈希验证: {'是' if data.enable_file_hash_validation else '否'}")

        # 全局设置
        summary.append(f"\n[全局设置]")
        summary.append(f"  缓存根目录: {self.global_settings.get('cache_root_directory')}")
        summary.append(f"  性能监控: {'是' if self.global_settings.get('enable_performance_monitoring') else '否'}")
        summary.append(f"  缓存统计: {'是' if self.global_settings.get('enable_cache_statistics') else '否'}")
        summary.append(f"  缓存预热: {'是' if self.global_settings.get('enable_cache_warmup') else '否'}")
        summary.append(f"  预热计划: {self.global_settings.get('warmup_schedule')}")
        summary.append(f"  维护计划: {self.global_settings.get('maintenance_schedule')}")

        return '\n'.join(summary)

# 全局统一缓存配置实例
unified_cache_config = UnifiedCacheConfiguration()

def get_cache_config() -> UnifiedCacheConfiguration:
    """获取全局缓存配置实例"""
    return unified_cache_config

if __name__ == "__main__":
    # 测试统一缓存配置
    config = UnifiedCacheConfiguration()

    print("=== 默认配置测试 ===")
    print(config.get_configuration_summary())

    print("\n=== 配置验证测试 ===")
    errors = config.validate_configuration()
    if any(errors.values()):
        print("发现配置错误:")
        for module, error_list in errors.items():
            if error_list:
                print(f"  {module}: {', '.join(error_list)}")
    else:
        print("配置验证通过")

    print("\n=== 缓存目录测试 ===")
    directories = config.get_cache_directories()
    for dir_type, dir_path in directories.items():
        print(f"  {dir_type}: {dir_path}")

    print("\n=== 保存配置测试 ===")
    if config.save_configuration():
        print("配置保存成功")
    else:
        print("配置保存失败")