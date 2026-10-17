"""
缓存管理系统
包含数据缓存、路由缓存、管道路由缓存等功能
"""

# 优先导入pipeline_route_types（不依赖其他模块）
from .pipeline_route_types import PipelineRoute, ClusteredPipelineRoute, PipelinePoint, PipelineRouteNotFoundError

# 尝试导入其他模块（可能有依赖问题）
try:
    from .data_cache_manager import cache_manager
except ImportError as e:
    print(f"警告: data_cache_manager导入失败: {e}")
    cache_manager = None

try:
    from .cache_management_utility import CacheManagementUtility
except ImportError as e:
    print(f"警告: CacheManagementUtility导入失败: {e}")
    CacheManagementUtility = None

try:
    from .pipeline_route_cache_manager import PipelineRouteCacheManager
except ImportError as e:
    print(f"警告: PipelineRouteCacheManager导入失败: {e}")
    PipelineRouteCacheManager = None

try:
    from .unified_cache_configuration import UnifiedCacheConfiguration
except ImportError as e:
    print(f"警告: UnifiedCacheConfiguration导入失败: {e}")
    UnifiedCacheConfiguration = None

__all__ = [
    'cache_manager',
    'CacheManagementUtility',
    'PipelineRouteCacheManager',
    'UnifiedCacheConfiguration',
    'PipelineRoute',
    'ClusteredPipelineRoute',
    'PipelinePoint',
    'PipelineRouteNotFoundError'
]