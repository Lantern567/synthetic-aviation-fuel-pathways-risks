"""
氢气管道运输距离计算器
基于现有管道基础设施（原油、成品油、天然气管道）计算氢气管道运输距离

功能:
1. 加载三种管道数据（原油、成品油、天然气管道）
2. 实现点到管线的最短距离吸附算法
3. 实现基于管线网络的路径搜索算法
4. 选择三种管道中的最短路径

算法逻辑:
总距离 = 起点吸附距离 + 管道网络距离 + 终点吸附距离
"""

import json
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Union
import logging
import networkx as nx
from math import radians, sin, cos, sqrt, atan2
import heapq
from dataclasses import dataclass
from functools import lru_cache
import time

# 🚀 性能优化：导入scipy空间索引
try:
    from scipy.spatial import cKDTree
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    logger.warning("scipy不可用，将使用传统查找方法（性能较慢）。建议: pip install scipy")

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 交叉点连通需要的几何工具
try:
    from shapely.geometry import LineString, Point
    from shapely.strtree import STRtree
    SHAPELY_AVAILABLE = True
except Exception:
    SHAPELY_AVAILABLE = False

# 导入数据类型定义
try:
    from ..cache.pipeline_route_types import (
        PipelineRoute, ClusteredPipelineRoute, PipelinePoint,
        PipelineRouteNotFoundError
    )
except ImportError:
    from cache.pipeline_route_types import (
        PipelineRoute, ClusteredPipelineRoute, PipelinePoint,
        PipelineRouteNotFoundError
    )

# 集成新的缓存系统
try:
    from ..cache.pipeline_route_cache_manager import PipelineRouteCacheManager
    from ..cache.unified_cache_configuration import UnifiedCacheConfiguration
    ADVANCED_CACHE_AVAILABLE = True
except ImportError:
    try:
        from cache.pipeline_route_cache_manager import PipelineRouteCacheManager
        from cache.unified_cache_configuration import UnifiedCacheConfiguration
        ADVANCED_CACHE_AVAILABLE = True
    except ImportError as e:
        pass  # 静默降级处理
        ADVANCED_CACHE_AVAILABLE = False

class HydrogenPipelineDistanceCalculator:
    """氢气管道运输距离计算器"""

    def __init__(self, gis_data_path: str, enable_cache: bool = False,
                 cache_dir: str = None, use_unified_config: bool = True,
                 mixed_link_distance_km: float = 20.0,
                 max_bridge_distance_km: float = 10.0):
        """
        初始化计算器

        Args:
            gis_data_path: GIS数据目录路径
            enable_cache: 是否启用计算缓存（默认False，数据库缓存查询比计算更慢）
            cache_dir: 缓存目录路径
            use_unified_config: 是否使用统一配置系统
            mixed_link_distance_km: 近邻接驳距离（km），默认20.0
            max_bridge_distance_km: 跨连通分量桥接最大距离（km），默认10.0
        """
        self.gis_data_path = Path(gis_data_path)
        self.enable_cache = enable_cache
        self.use_unified_config = use_unified_config
        # mixed管网的近邻接驳距离（km）
        self.mixed_link_distance_km = mixed_link_distance_km
        # 跨连通分量桥接最大距离（km）
        self.max_bridge_distance_km = max_bridge_distance_km

        # 初始化高级缓存系统
        self.pipeline_cache_manager = None
        if ADVANCED_CACHE_AVAILABLE and enable_cache:
            try:
                if use_unified_config:
                    # 使用统一配置
                    config = UnifiedCacheConfiguration()
                    cache_config = config.get_pipeline_config()
                    self.pipeline_cache_manager = PipelineRouteCacheManager(
                        cache_dir=cache_dir,
                        enable_cache=cache_config.enabled,
                        ttl_hours=cache_config.ttl_hours,
                        max_cache_size_mb=cache_config.max_cache_size_mb,
                        max_entries=cache_config.max_entries
                    )
                else:
                    # 使用默认配置
                    self.pipeline_cache_manager = PipelineRouteCacheManager(
                        cache_dir=cache_dir,
                        enable_cache=enable_cache
                    )

                logger.debug("高级管道路径缓存系统已初始化")
            except Exception as e:
                pass  # 静默降级处理
                self.pipeline_cache_manager = None

        # 管道数据存储
        self.pipeline_data = {
            'crude': None,       # 原油管道
            'refined': None,     # 成品油管道
            'natural_gas': None  # 天然气管道
        }

        # 管道网络图
        self.pipeline_networks = {
            'crude': None,
            'refined': None,
            'natural_gas': None,
            'mixed': None
        }

        # 🚀 性能优化：空间索引，用于快速查找最近管道点
        self.pipeline_spatial_indexes = {
            'crude': None,
            'refined': None,
            'natural_gas': None,
            'mixed': None
        }

        # 统计信息
        self.stats = {
            'total_calculations': 0,
            'cache_hits': 0,
            'successful_routes': 0,
            'failed_routes': 0,
            'pipeline_type_usage': {
                'crude': 0,
                'refined': 0,
                'natural_gas': 0,
                'mixed': 0
            },
            'advanced_cache_stats': {}
        }

        cache_status = "高级缓存" if self.pipeline_cache_manager else "基础缓存"
        logger.debug(f"氢气管道距离计算器初始化完成，GIS数据路径: {gis_data_path}，缓存模式: {cache_status}")

    def load_pipeline_data(self) -> Dict[str, Dict]:
        """
        加载所有管道数据

        Returns:
            Dict: 包含三种管道数据的字典
        """
        logger.debug("开始加载管道数据...")

        pipeline_files = {
            'crude': 'crude_pipelines.geojson',
            'refined': 'refined_product_pipelines.geojson',
            'natural_gas': 'natural_gas_pipelines.geojson'
        }

        for pipeline_type, filename in pipeline_files.items():
            file_path = self.gis_data_path / filename

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.pipeline_data[pipeline_type] = json.load(f)

                feature_count = len(self.pipeline_data[pipeline_type]['features'])
                logger.debug(f"成功加载{pipeline_type}管道数据: {feature_count} 个要素")

            except Exception as e:
                logger.error(f"加载{pipeline_type}管道数据失败: {e}")
                self.pipeline_data[pipeline_type] = {'features': []}

        # 构建管道网络图
        self._build_pipeline_networks()

        # 🚀 性能优化：构建空间索引
        if SCIPY_AVAILABLE:
            self._build_spatial_indexes()
            logger.debug("管道空间索引构建完成")

        total_pipelines = sum(len(data['features']) for data in self.pipeline_data.values())
        logger.debug(f"管道数据加载完成，总管道数: {total_pipelines}")

        return self.pipeline_data

    def _get_pipeline_features(self, pipeline_type: str) -> List[Dict]:
        """获取指定管道类型的GIS要素列表，支持mixed合并类型"""
        if pipeline_type == 'mixed':
            features: List[Dict] = []
            for t in ['crude', 'refined', 'natural_gas']:
                data = self.pipeline_data.get(t)
                if data and 'features' in data:
                    features.extend(data['features'])
            return features

        data = self.pipeline_data.get(pipeline_type)
        if data and 'features' in data:
            return data['features']
        return []

    def _build_pipeline_networks(self):
        """构建管道网络图"""
        logger.debug("构建管道网络图...")

        for pipeline_type, data in self.pipeline_data.items():
            if not data or 'features' not in data:
                continue

            # 创建networkx图
            graph = nx.Graph()
            # 存储边的几何信息
            edge_geometry = {}

            for feature in data['features']:
                # 检查geometry字段是否存在且不为None
                if not feature.get('geometry') or feature['geometry'].get('type') != 'LineString':
                    continue

                coordinates = feature['geometry']['coordinates']
                if not coordinates:  # 检查坐标是否为空
                    continue

                pipeline_name = feature['properties'].get('Name', '')

                # 方法1：每个坐标点对作为边（保持原有逻辑）
                for i in range(len(coordinates) - 1):
                    start_coord = coordinates[i]
                    end_coord = coordinates[i + 1]

                    start_node = f"{start_coord[1]:.6f},{start_coord[0]:.6f}"
                    end_node = f"{end_coord[1]:.6f},{end_coord[0]:.6f}"

                    # 计算线段距离
                    distance = self._calculate_haversine_distance(
                        start_coord[1], start_coord[0],
                        end_coord[1], end_coord[0]
                    )

                    # 存储边的几何信息（只包含起点和终点）
                    edge_key = (start_node, end_node)
                    edge_geometry[edge_key] = [
                        (start_coord[1], start_coord[0]),  # lat, lon
                        (end_coord[1], end_coord[0])       # lat, lon
                    ]

                    # 添加边
                    graph.add_edge(start_node, end_node,
                                 weight=distance,
                                 pipeline_name=pipeline_name,
                                 pipeline_type=pipeline_type,
                                 geometry=edge_geometry[edge_key])

                # 方法2：如果管道有多个点，还要添加完整管道段的几何信息
                if len(coordinates) > 2:
                    # 管道的首尾节点
                    start_coord = coordinates[0]
                    end_coord = coordinates[-1]
                    start_node = f"{start_coord[1]:.6f},{start_coord[0]:.6f}"
                    end_node = f"{end_coord[1]:.6f},{end_coord[0]:.6f}"

                    # 计算完整管道的总距离
                    total_distance = 0
                    for i in range(len(coordinates) - 1):
                        segment_dist = self._calculate_haversine_distance(
                            coordinates[i][1], coordinates[i][0],
                            coordinates[i+1][1], coordinates[i+1][0]
                        )
                        total_distance += segment_dist

                    # 存储完整管道段的几何信息
                    pipeline_edge_key = (start_node, end_node, 'full_pipeline')
                    pipeline_geometry = [(coord[1], coord[0]) for coord in coordinates]  # 转换为(lat, lon)
                    edge_geometry[pipeline_edge_key] = pipeline_geometry

                    # 如果首尾节点不直接相连，添加完整管道边
                    if not graph.has_edge(start_node, end_node):
                        graph.add_edge(start_node, end_node,
                                     weight=total_distance,
                                     pipeline_name=f"{pipeline_name}_full",
                                     pipeline_type=pipeline_type,
                                     geometry=pipeline_geometry,
                                     is_full_pipeline=True)

            self.pipeline_networks[pipeline_type] = graph
            # 存储边几何信息
            if not hasattr(self, 'edge_geometries'):
                self.edge_geometries = {}
            self.edge_geometries[pipeline_type] = edge_geometry

            # 分析连通性
            components = list(nx.connected_components(graph))
            num_components = len(components)
            largest_component_size = max(len(c) for c in components) if components else 0

            logger.info(f"{pipeline_type}管道网络构建完成: "
                       f"{graph.number_of_nodes()}节点, "
                       f"{graph.number_of_edges()}边, "
                       f"{num_components}个连通分量 "
                       f"(最大分量{largest_component_size}节点)")

            if num_components > 1:
                # 显示各连通分量大小
                component_sizes = sorted([len(c) for c in components], reverse=True)
                logger.warning(f"{pipeline_type}管道网络不连通! "
                             f"分量大小: {component_sizes[:5]}")
            else:
                logger.debug(f"{pipeline_type}管道网络完全连通")

        # 构建混合管道网络（允许跨类型连通）
        mixed_graph = nx.Graph()
        mixed_edge_geometries: Dict = {}
        for pipeline_type in ['crude', 'refined', 'natural_gas']:
            graph = self.pipeline_networks.get(pipeline_type)
            if graph:
                mixed_graph = nx.compose(mixed_graph, graph)

            if hasattr(self, 'edge_geometries') and pipeline_type in self.edge_geometries:
                mixed_edge_geometries.update(self.edge_geometries[pipeline_type])

        self.pipeline_networks['mixed'] = mixed_graph if mixed_graph.number_of_nodes() > 0 else None
        if not hasattr(self, 'edge_geometries'):
            self.edge_geometries = {}
        self.edge_geometries['mixed'] = mixed_edge_geometries

        if self.pipeline_networks['mixed']:
            # 交叉点即联通：在mixed图上补充交叉节点
            self._add_mixed_intersections()
            # 在mixed图中添加近邻接驳，尽量连成一个大图
            self._add_mixed_connectors()
            components = list(nx.connected_components(self.pipeline_networks['mixed']))
            num_components = len(components)
            largest_component_size = max(len(c) for c in components) if components else 0
            logger.info(
                f"mixed管道网络构建完成: "
                f"{self.pipeline_networks['mixed'].number_of_nodes()}节点, "
                f"{self.pipeline_networks['mixed'].number_of_edges()}边, "
                f"{num_components}个连通分量 "
                f"(最大分量{largest_component_size}节点)"
            )
            # 强制连接所有孤立的连通分量
            if num_components > 1:
                self._force_bridge_components(self.max_bridge_distance_km)
                # 重新统计连通性
                components = list(nx.connected_components(self.pipeline_networks['mixed']))
                num_components = len(components)
                largest_component_size = max(len(c) for c in components) if components else 0
                logger.info(
                    f"桥接后mixed管道网络: "
                    f"{self.pipeline_networks['mixed'].number_of_nodes()}节点, "
                    f"{self.pipeline_networks['mixed'].number_of_edges()}边, "
                    f"{num_components}个连通分量 "
                    f"(最大分量{largest_component_size}节点)"
                )

    def _add_mixed_intersections(self):
        """在混合管网中补充交叉点节点，使交叉处可联通"""
        if not SHAPELY_AVAILABLE:
            logger.warning("shapely不可用，跳过交叉点联通增强")
            return

        graph = self.pipeline_networks.get('mixed')
        if not graph:
            return

        # 收集所有管道线段
        segments = []
        for pipeline_type in ['crude', 'refined', 'natural_gas']:
            data = self.pipeline_data.get(pipeline_type)
            if not data or 'features' not in data:
                continue
            for feature in data['features']:
                if not feature.get('geometry') or feature['geometry'].get('type') != 'LineString':
                    continue
                coords = feature['geometry']['coordinates']
                if not coords or len(coords) < 2:
                    continue
                for i in range(len(coords) - 1):
                    x1, y1 = coords[i][0], coords[i][1]  # lon, lat
                    x2, y2 = coords[i + 1][0], coords[i + 1][1]
                    line = LineString([(x1, y1), (x2, y2)])
                    segments.append({
                        'geom': line,
                        'start': (y1, x1),  # lat, lon
                        'end': (y2, x2),    # lat, lon
                        'pipeline_type': pipeline_type
                    })

        if not segments:
            return

        geoms = [seg['geom'] for seg in segments]
        tree = STRtree(geoms)
        geom_index = {id(geom): idx for idx, geom in enumerate(geoms)}

        # 收集每条线段上的交叉点
        intersections_by_seg = {}

        for i, seg in enumerate(segments):
            geom = seg['geom']
            candidates = tree.query(geom)
            for cand in candidates:
                j = geom_index.get(id(cand))
                if j is None or j <= i:
                    continue
                inter = geom.intersection(cand)
                if inter.is_empty:
                    continue
                points = []
                if isinstance(inter, Point):
                    points = [inter]
                elif inter.geom_type == 'MultiPoint':
                    points = list(inter.geoms)
                else:
                    # 线重叠等情况跳过
                    continue

                for p in points:
                    lon, lat = p.x, p.y
                    # 跳过靠近端点的交叉点（已有节点）
                    if (abs(lat - seg['start'][0]) < 1e-6 and abs(lon - seg['start'][1]) < 1e-6) or \
                       (abs(lat - seg['end'][0]) < 1e-6 and abs(lon - seg['end'][1]) < 1e-6):
                        continue
                    if (abs(lat - segments[j]['start'][0]) < 1e-6 and abs(lon - segments[j]['start'][1]) < 1e-6) or \
                       (abs(lat - segments[j]['end'][0]) < 1e-6 and abs(lon - segments[j]['end'][1]) < 1e-6):
                        continue

                    intersections_by_seg.setdefault(i, []).append((lat, lon))
                    intersections_by_seg.setdefault(j, []).append((lat, lon))

        if not intersections_by_seg:
            return

        # 为每条线段添加交叉点节点和边
        added_nodes = 0
        added_edges = 0
        edge_geometries = self.edge_geometries.get('mixed') if hasattr(self, 'edge_geometries') else None
        if edge_geometries is None:
            if not hasattr(self, 'edge_geometries'):
                self.edge_geometries = {}
            edge_geometries = {}
            self.edge_geometries['mixed'] = edge_geometries

        for idx, seg in enumerate(segments):
            points = intersections_by_seg.get(idx)
            if not points:
                continue

            line = seg['geom']
            # 去重并排序
            uniq = {}
            for lat, lon in points:
                key = (round(lat, 6), round(lon, 6))
                uniq[key] = (lat, lon)
            points = list(uniq.values())
            points.sort(key=lambda pt: line.project(Point(pt[1], pt[0])))

            chain = [seg['start']] + points + [seg['end']]
            # 连成分段边
            for a, b in zip(chain, chain[1:]):
                a_node = f"{a[0]:.6f},{a[1]:.6f}"
                b_node = f"{b[0]:.6f},{b[1]:.6f}"
                if a_node == b_node:
                    continue
                if not graph.has_node(a_node):
                    graph.add_node(a_node)
                    added_nodes += 1
                if not graph.has_node(b_node):
                    graph.add_node(b_node)
                    added_nodes += 1
                if graph.has_edge(a_node, b_node):
                    continue
                dist = self._calculate_haversine_distance(a[0], a[1], b[0], b[1])
                graph.add_edge(
                    a_node, b_node,
                    weight=dist,
                    pipeline_name='intersection',
                    pipeline_type='mixed',
                    geometry=[a, b],
                    is_intersection=True
                )
                edge_geometries[(a_node, b_node)] = [a, b]
                added_edges += 1

        if added_nodes or added_edges:
            logger.info(f"mixed管网交叉点联通增强: 新增节点{added_nodes}个, 新增边{added_edges}条")

        # 近似交叉/近距离穿越的snap连接（更激进）
        self._add_mixed_snap_connectors()

    def _add_mixed_snap_connectors(self, snap_km: float = 0.2):
        """将节点与邻近线段做snap连接（近似交叉/近距离穿越）"""
        if not SHAPELY_AVAILABLE:
            return

        graph = self.pipeline_networks.get('mixed')
        if not graph:
            return

        max_km = float(snap_km or 0)
        if max_km <= 0:
            return

        # 收集线段
        segments = []
        for pipeline_type in ['crude', 'refined', 'natural_gas']:
            data = self.pipeline_data.get(pipeline_type)
            if not data or 'features' not in data:
                continue
            for feature in data['features']:
                if not feature.get('geometry') or feature['geometry'].get('type') != 'LineString':
                    continue
                coords = feature['geometry']['coordinates']
                if not coords or len(coords) < 2:
                    continue
                for i in range(len(coords) - 1):
                    x1, y1 = coords[i][0], coords[i][1]
                    x2, y2 = coords[i + 1][0], coords[i + 1][1]
                    line = LineString([(x1, y1), (x2, y2)])
                    segments.append((line, (y1, x1), (y2, x2)))

        if not segments:
            return

        geoms = [s[0] for s in segments]
        tree = STRtree(geoms)
        geom_index = {id(geom): idx for idx, geom in enumerate(geoms)}

        # 简单的经纬度缓冲（用度近似）
        snap_deg = max_km / 111.0

        added_nodes = 0
        added_edges = 0
        edge_geometries = self.edge_geometries.get('mixed') if hasattr(self, 'edge_geometries') else None
        if edge_geometries is None:
            if not hasattr(self, 'edge_geometries'):
                self.edge_geometries = {}
            edge_geometries = {}
            self.edge_geometries['mixed'] = edge_geometries

        # 遍历节点，吸附到附近线段
        for node in list(graph.nodes):
            try:
                lat, lon = map(float, node.split(','))
            except Exception:
                continue
            pt = Point(lon, lat)
            # 查询附近线段
            candidates = tree.query(pt.buffer(snap_deg))
            for cand in candidates:
                idx = geom_index.get(id(cand))
                if idx is None:
                    continue
                line, start, end = segments[idx]
                # 跳过线段端点附近
                if (abs(lat - start[0]) < 1e-6 and abs(lon - start[1]) < 1e-6) or \
                   (abs(lat - end[0]) < 1e-6 and abs(lon - end[1]) < 1e-6):
                    continue

                # 投影最近点
                proj = line.interpolate(line.project(pt))
                snap_lon, snap_lat = proj.x, proj.y

                # 距离检查
                dist = self._calculate_haversine_distance(lat, lon, snap_lat, snap_lon)
                if dist > max_km:
                    continue

                snap_node = f"{snap_lat:.6f},{snap_lon:.6f}"
                if not graph.has_node(snap_node):
                    graph.add_node(snap_node)
                    added_nodes += 1

                if not graph.has_edge(node, snap_node):
                    graph.add_edge(
                        node, snap_node,
                        weight=dist,
                        pipeline_name='snap',
                        pipeline_type='mixed',
                        geometry=[(lat, lon), (snap_lat, snap_lon)],
                        is_snap=True
                    )
                    edge_geometries[(node, snap_node)] = [(lat, lon), (snap_lat, snap_lon)]
                    added_edges += 1

        if added_nodes or added_edges:
            logger.info(f"mixed管网近似交叉snap增强: 新增节点{added_nodes}个, 新增边{added_edges}条 (<= {max_km}km)")

    def _add_mixed_connectors(self):
        """在混合管网中添加近邻接驳边，提升连通性"""
        graph = self.pipeline_networks.get('mixed')
        if not graph:
            return

        max_km = float(self.mixed_link_distance_km or 0)
        if max_km <= 0:
            return

        # 以近似纬度换算建立网格索引
        cell_size = max_km / 111.0  # 1度纬度约111km
        buckets = {}

        nodes = list(graph.nodes)
        for node in nodes:
            try:
                lat, lon = map(float, node.split(','))
            except Exception:
                continue
            ix = int(lon / cell_size)
            iy = int(lat / cell_size)
            buckets.setdefault((ix, iy), []).append((node, lat, lon))

        added = 0
        bucket_keys = sorted(buckets.keys())

        for idx, key in enumerate(bucket_keys):
            lst = buckets[key]
            ix, iy = key
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    nkey = (ix + dx, iy + dy)
                    if nkey not in buckets:
                        continue
                    # 避免重复处理
                    if nkey < key:
                        continue

                    lst2 = buckets[nkey]
                    if nkey == key:
                        # 同桶内两两配对
                        for i in range(len(lst)):
                            n1, lat1, lon1 = lst[i]
                            for j in range(i + 1, len(lst)):
                                n2, lat2, lon2 = lst[j]
                                if graph.has_edge(n1, n2):
                                    continue
                                dist = self._calculate_haversine_distance(lat1, lon1, lat2, lon2)
                                if dist <= max_km:
                                    graph.add_edge(
                                        n1, n2,
                                        weight=dist,
                                        pipeline_name='connector',
                                        pipeline_type='connector',
                                        geometry=[(lat1, lon1), (lat2, lon2)],
                                        is_connector=True
                                    )
                                    added += 1
                    else:
                        # 不同桶之间两两配对
                        for n1, lat1, lon1 in lst:
                            for n2, lat2, lon2 in lst2:
                                if graph.has_edge(n1, n2):
                                    continue
                                dist = self._calculate_haversine_distance(lat1, lon1, lat2, lon2)
                                if dist <= max_km:
                                    graph.add_edge(
                                        n1, n2,
                                        weight=dist,
                                        pipeline_name='connector',
                                        pipeline_type='connector',
                                        geometry=[(lat1, lon1), (lat2, lon2)],
                                        is_connector=True
                                    )
                                    added += 1

        logger.info(f"mixed管网近邻接驳完成: 新增{added}条接驳边 (<= {max_km}km)")

    def _force_bridge_components(self, max_bridge_km: float = 100.0):
        """
        强制连接所有孤立的连通分量，确保管道网络完全连通

        Args:
            max_bridge_km: 允许的最大桥接距离（km）
        """
        graph = self.pipeline_networks.get('mixed')
        if not graph:
            return

        components = list(nx.connected_components(graph))
        if len(components) <= 1:
            logger.info("管道网络已完全连通，无需桥接")
            return

        # 找到最大分量作为主干
        main_comp = max(components, key=len)
        main_nodes = set(main_comp)

        # 预解析所有节点坐标
        node_coords = {}
        for node in graph.nodes:
            try:
                lat, lon = map(float, node.split(','))
                node_coords[node] = (lat, lon)
            except Exception:
                continue

        added_bridges = 0
        failed_bridges = 0

        for comp in components:
            if comp == main_comp:
                continue

            # 找到comp和main_comp之间最近的节点对
            min_dist = float('inf')
            best_pair = None

            for node1 in comp:
                if node1 not in node_coords:
                    continue
                lat1, lon1 = node_coords[node1]

                for node2 in main_nodes:
                    if node2 not in node_coords:
                        continue
                    lat2, lon2 = node_coords[node2]

                    dist = self._calculate_haversine_distance(lat1, lon1, lat2, lon2)
                    if dist < min_dist:
                        min_dist = dist
                        best_pair = (node1, node2, lat1, lon1, lat2, lon2)

            if best_pair and min_dist <= max_bridge_km:
                node1, node2, lat1, lon1, lat2, lon2 = best_pair
                graph.add_edge(
                    node1, node2,
                    weight=min_dist,
                    pipeline_name='bridge',
                    pipeline_type='bridge',
                    geometry=[(lat1, lon1), (lat2, lon2)],
                    is_bridge=True
                )
                # 将该分量加入主干
                main_nodes.update(comp)
                added_bridges += 1
                logger.debug(f"添加桥接边: {node1} <-> {node2}, 距离 {min_dist:.2f}km")
            else:
                failed_bridges += 1
                logger.warning(
                    f"无法桥接分量（{len(comp)}节点），"
                    f"最近距离 {min_dist:.2f}km 超过阈值 {max_bridge_km}km"
                )

        logger.info(
            f"连通分量桥接完成: 成功 {added_bridges} 个, 失败 {failed_bridges} 个"
        )

    def _build_spatial_indexes(self):
        """
        🚀 性能优化：构建管道的空间索引（KDTree）
        用于快速查找最近管道点，复杂度从O(N×M)降至O(logN)
        """
        logger.debug("开始构建管道空间索引...")

        for pipeline_type, data in self.pipeline_data.items():
            if not data or 'features' not in data:
                continue

            points = []  # 存储线段中点坐标
            segment_info = []  # 存储对应的线段信息

            for feat_idx, feature in enumerate(data['features']):
                if not feature.get('geometry') or feature['geometry'].get('type') != 'LineString':
                    continue

                coordinates = feature['geometry']['coordinates']
                if not coordinates or len(coordinates) < 2:
                    continue

                # 对每个线段，存储其中点用于快速查询
                for seg_idx in range(len(coordinates) - 1):
                    start_coord = coordinates[seg_idx]
                    end_coord = coordinates[seg_idx + 1]

                    # 计算线段中点（lat, lon）
                    mid_lat = (start_coord[1] + end_coord[1]) / 2
                    mid_lon = (start_coord[0] + end_coord[0]) / 2

                    points.append([mid_lat, mid_lon])

                    # 存储原始线段信息，用于精确计算
                    segment_info.append({
                        'feature_idx': feat_idx,
                        'segment_idx': seg_idx,
                        'start': (start_coord[1], start_coord[0]),  # (lat, lon)
                        'end': (end_coord[1], end_coord[0])
                    })

            if points:
                # 构建KDTree
                tree = cKDTree(np.array(points))

                self.pipeline_spatial_indexes[pipeline_type] = {
                    'tree': tree,
                    'segments': segment_info,
                    'points': np.array(points)
                }

                logger.debug(f"{pipeline_type}管道空间索引: {len(points)}个线段中点")
            else:
                self.pipeline_spatial_indexes[pipeline_type] = None

        # 构建混合管道空间索引（合并三类管道）
        points = []
        segment_info = []
        for pipeline_type in ['crude', 'refined', 'natural_gas']:
            data = self.pipeline_data.get(pipeline_type)
            if not data or 'features' not in data:
                continue

            for feat_idx, feature in enumerate(data['features']):
                if not feature.get('geometry') or feature['geometry'].get('type') != 'LineString':
                    continue

                coordinates = feature['geometry']['coordinates']
                if not coordinates or len(coordinates) < 2:
                    continue

                for seg_idx in range(len(coordinates) - 1):
                    start_coord = coordinates[seg_idx]
                    end_coord = coordinates[seg_idx + 1]

                    mid_lat = (start_coord[1] + end_coord[1]) / 2
                    mid_lon = (start_coord[0] + end_coord[0]) / 2

                    points.append([mid_lat, mid_lon])
                    segment_info.append({
                        'feature_idx': feat_idx,
                        'segment_idx': seg_idx,
                        'start': (start_coord[1], start_coord[0]),
                        'end': (end_coord[1], end_coord[0])
                    })

        if points:
            tree = cKDTree(np.array(points))
            self.pipeline_spatial_indexes['mixed'] = {
                'tree': tree,
                'segments': segment_info,
                'points': np.array(points)
            }
        else:
            self.pipeline_spatial_indexes['mixed'] = None

    def calculate_pipeline_distance(self, start_lat: float, start_lon: float,
                                  end_lat: float, end_lon: float,
                                  max_access_distance_km: float = 100.0,
                                  route_type: str = "single",
                                  additional_params: Dict = None) -> PipelineRoute:
        """
        计算基于管道网络的氢气运输距离
        注意：max_access_distance_km参数保留用于向后兼容，但不再限制搜索距离

        Args:
            start_lat, start_lon: 起点坐标
            end_lat, end_lon: 终点坐标
            max_access_distance_km: 保留参数，不再限制距离
            route_type: 路径类型 ("single")
            additional_params: 额外参数字典

        Returns:
            PipelineRoute: 管道路径结果
        """
        start_time = time.time()  # 记录开始时间
        self.stats['total_calculations'] += 1

        # 首先检查高级缓存
        if self.pipeline_cache_manager:
            cached_result = self.pipeline_cache_manager.get_cached_route(
                start_lat, start_lon, end_lat, end_lon,
                max_access_distance_km, route_type, additional_params
            )

            if cached_result:
                self.stats['cache_hits'] += 1
                logger.debug(f"管道路径缓存命中: ({start_lat:.6f},{start_lon:.6f}) -> ({end_lat:.6f},{end_lon:.6f})")
                return cached_result

        if not any(self.pipeline_data.values()):
            self.load_pipeline_data()

        logger.debug(f"计算管道运输距离: ({start_lat:.6f},{start_lon:.6f}) -> "
                   f"({end_lat:.6f},{end_lon:.6f})")

        best_route = None
        route_mode = None
        if additional_params:
            route_mode = additional_params.get('route_mode')

        # 使用混合管道网络（允许跨类型）
        try:
            if route_mode == 'graph_only':
                best_route = self._calculate_graph_only_route(
                    start_lat, start_lon, end_lat, end_lon, 'mixed'
                )
            else:
                best_route = self._calculate_single_pipeline_route(
                    start_lat, start_lon, end_lat, end_lon,
                    'mixed', float('inf')  # 移除距离限制
                )
        except Exception as e:
            logger.debug(f"mixed管道路径计算失败: {e}")
            best_route = None

        if best_route and best_route.route_found:
            self.stats['successful_routes'] += 1
            # 更新管道类型使用统计
            for pipeline_type in best_route.pipeline_types_used:
                self.stats['pipeline_type_usage'][pipeline_type] += 1

            logger.debug(f"找到最优管道路径: {best_route.total_distance_km:.3f}km "
                       f"(使用{best_route.pipeline_types_used}管道)")

            # 保存到高级缓存
            if self.pipeline_cache_manager:
                self.pipeline_cache_manager.cache_route(
                    start_lat, start_lon, end_lat, end_lon,
                    best_route, max_access_distance_km, route_type,
                    calculation_time_ms=(time.time() - start_time) * 1000,
                    additional_params=additional_params
                )
            return best_route
        else:
            self.stats['failed_routes'] += 1
            logger.error("所有管道类型都无法找到有效路径，抛出异常")

            # 抛出自定义异常而不是返回失败结果
            raise PipelineRouteNotFoundError(
                start_lat=start_lat,
                start_lon=start_lon,
                end_lat=end_lat,
                end_lon=end_lon,
                max_access_distance_km=max_access_distance_km,
                pipeline_types_tried=['crude', 'refined', 'natural_gas']
            )

    def _calculate_single_pipeline_route(self, start_lat: float, start_lon: float,
                                       end_lat: float, end_lon: float,
                                       pipeline_type: str,
                                       max_access_distance_km: float) -> PipelineRoute:
        """
        计算单一管道类型的路径（改进版：起点和终点都使用多候选策略，支持跳跃逻辑）

        Args:
            start_lat, start_lon: 起点坐标
            end_lat, end_lon: 终点坐标
            pipeline_type: 管道类型
            max_access_distance_km: 最大接入距离

        Returns:
            PipelineRoute: 单一管道类型的路径结果
        """
        # 1. 起点也使用多候选策略（取最近5个候选点）
        start_candidates = self._find_nearest_pipeline_points(
            start_lat, start_lon, pipeline_type, k=5
        )

        if not start_candidates:
            return PipelineRoute(
                total_distance_km=0.0,
                access_distance_km=0.0,
                pipeline_distance_km=0.0,
                egress_distance_km=0.0,
                pipeline_types_used=[],
                route_found=False,
                calculation_method=f'{pipeline_type}_start_access_failed'
            )

        # 2. 终点也取最近5个候选点
        end_candidates = self._find_nearest_pipeline_points(
            end_lat, end_lon, pipeline_type, k=5
        )

        if not end_candidates:
            return PipelineRoute(
                total_distance_km=0.0,
                access_distance_km=0.0,
                pipeline_distance_km=0.0,
                egress_distance_km=0.0,
                pipeline_types_used=[],
                route_found=False,
                calculation_method=f'{pipeline_type}_end_access_failed'
            )

        # 3. 可达性预检查：过滤不在同一连通分量的候选对，并实现跳跃逻辑
        graph = self.pipeline_networks.get(pipeline_type)
        valid_pairs = []
        jump_pairs = []  # 需要跳跃的候选对

        if graph:
            for start_access_point, start_access_distance in start_candidates:
                start_node = f"{start_access_point[0]:.6f},{start_access_point[1]:.6f}"
                # 如果节点不在图中，找最近的图节点
                if start_node not in graph:
                    start_node = self._find_nearest_graph_node(start_access_point, graph)
                if not start_node:
                    continue

                for end_access_point, end_access_distance in end_candidates:
                    end_node = f"{end_access_point[0]:.6f},{end_access_point[1]:.6f}"
                    if end_node not in graph:
                        end_node = self._find_nearest_graph_node(end_access_point, graph)
                    if not end_node:
                        continue

                    # 检查是否在同一连通分量
                    try:
                        if nx.has_path(graph, start_node, end_node):
                            valid_pairs.append((
                                start_access_point, start_access_distance,
                                end_access_point, end_access_distance,
                                None  # 不需要跳跃
                            ))
                        else:
                            # 不在同一连通分量，尝试跳跃逻辑
                            # 在起点所在连通分量中找到距离终点接入点最近的边界节点
                            nearest_node, jump_distance = self._find_nearest_node_in_component(
                                start_node, end_access_point, graph
                            )

                            if nearest_node and jump_distance <= self.max_bridge_distance_km:
                                # 跳跃距离满足条件，记录跳跃段
                                try:
                                    nearest_lat, nearest_lon = map(float, nearest_node.split(','))
                                    jump_segment = ((nearest_lat, nearest_lon), end_access_point)
                                    jump_pairs.append((
                                        start_access_point, start_access_distance,
                                        end_access_point, end_access_distance,
                                        jump_segment
                                    ))
                                except (ValueError, AttributeError):
                                    continue
                            # 如果跳跃距离 > 10km，跳过该候选对（不添加到任何列表）
                    except (nx.NetworkXError, nx.NodeNotFound):
                        continue
        else:
            # 如果没有图，使用所有组合
            for start_access_point, start_access_distance in start_candidates:
                for end_access_point, end_access_distance in end_candidates:
                    valid_pairs.append((
                        start_access_point, start_access_distance,
                        end_access_point, end_access_distance,
                        None
                    ))

        # 合并有效候选对和跳跃候选对
        all_pairs = valid_pairs + jump_pairs

        if not all_pairs:
            # 如果可达性检查过滤掉了所有候选，回退到不检查可达性的模式
            logger.debug("可达性检查过滤了所有候选对，回退到全量搜索")
            for start_access_point, start_access_distance in start_candidates:
                for end_access_point, end_access_distance in end_candidates:
                    all_pairs.append((
                        start_access_point, start_access_distance,
                        end_access_point, end_access_distance,
                        None
                    ))

        best = None
        best_pipeline_coords = None
        best_start_access_point = None
        best_start_access_distance = None
        best_end_access_point = None
        best_end_access_distance = None
        best_jump_segment = None

        # 4. 笛卡尔积搜索：对所有有效候选对计算网络路径，选择总距离最短的
        for start_access_point, start_access_distance, end_access_point, end_access_distance, jump_segment in all_pairs:
            if jump_segment:
                # 有跳跃段：计算起点到跳跃起点的管道距离
                network_result = self._calculate_network_distance(
                    start_access_point, jump_segment[0], pipeline_type
                )
                if network_result is None:
                    continue
                pipeline_distance, pipeline_coords = network_result
                if pipeline_distance == 0.0 or not pipeline_coords:
                    continue

                # 计算跳跃距离
                jump_distance = self._calculate_haversine_distance(
                    jump_segment[0][0], jump_segment[0][1],
                    jump_segment[1][0], jump_segment[1][1]
                )

                # 总距离 = 起点接入 + 管道距离 + 跳跃距离 + 终点离开
                total_distance = start_access_distance + pipeline_distance + jump_distance + end_access_distance
            else:
                # 无跳跃段：正常计算
                network_result = self._calculate_network_distance(
                    start_access_point, end_access_point, pipeline_type
                )
                if network_result is None:
                    continue
                pipeline_distance, pipeline_coords = network_result
                if pipeline_distance == 0.0 or not pipeline_coords:
                    continue
                total_distance = start_access_distance + pipeline_distance + end_access_distance

            if best is None or total_distance < best:
                best = total_distance
                best_pipeline_coords = pipeline_coords
                best_start_access_point = start_access_point
                best_start_access_distance = start_access_distance
                best_end_access_point = end_access_point
                best_end_access_distance = end_access_distance
                best_jump_segment = jump_segment

        if best is None:
            return PipelineRoute(
                total_distance_km=0.0,
                access_distance_km=0.0,
                pipeline_distance_km=0.0,
                egress_distance_km=0.0,
                pipeline_types_used=[],
                route_found=False,
                calculation_method=f'{pipeline_type}_network_path_failed'
            )

        # 计算各段距离
        if best_jump_segment:
            pipeline_distance = best - best_start_access_distance - best_end_access_distance - self._calculate_haversine_distance(
                best_jump_segment[0][0], best_jump_segment[0][1],
                best_jump_segment[1][0], best_jump_segment[1][1]
            )
        else:
            pipeline_distance = best - best_start_access_distance - best_end_access_distance

        pipeline_coords = best_pipeline_coords
        start_access_point = best_start_access_point
        start_access_distance = best_start_access_distance
        end_access_point = best_end_access_point
        end_access_distance = best_end_access_distance

        # 5. 构建完整的路径几何信息
        complete_route_geometry = []
        # 添加起点
        complete_route_geometry.append((start_lat, start_lon))
        # 添加起点接入坐标
        if start_access_point != (start_lat, start_lon):
            complete_route_geometry.append(start_access_point)
        # 添加管道路径坐标
        complete_route_geometry.extend(pipeline_coords)
        # 如果有跳跃段，添加跳跃段
        if best_jump_segment:
            complete_route_geometry.append(best_jump_segment[0])
            complete_route_geometry.append(best_jump_segment[1])
        # 添加终点离开坐标
        if end_access_point != (end_lat, end_lon):
            complete_route_geometry.append(end_access_point)
        # 添加终点
        complete_route_geometry.append((end_lat, end_lon))

        return PipelineRoute(
            total_distance_km=best,
            access_distance_km=start_access_distance,
            pipeline_distance_km=pipeline_distance,
            egress_distance_km=end_access_distance,
            pipeline_types_used=[pipeline_type],
            route_found=True,
            calculation_method=f'{pipeline_type}_success' + ('_with_jump' if best_jump_segment else ''),
            # 添加几何信息
            route_geometry=complete_route_geometry,
            access_point_coords=start_access_point,
            egress_point_coords=end_access_point,
            start_coords=(start_lat, start_lon),
            end_coords=(end_lat, end_lon),
            jump_segments=[best_jump_segment] if best_jump_segment else None
        )

    def _calculate_graph_only_route(self, start_lat: float, start_lon: float,
                                    end_lat: float, end_lon: float,
                                    pipeline_type: str) -> PipelineRoute:
        """
        使用图方法直接计算路径（不进行点到管线的吸附）
        仅在图上寻找最短路径，必要时回退直线距离
        """
        network_result = self._calculate_network_distance(
            (start_lat, start_lon),
            (end_lat, end_lon),
            pipeline_type
        )

        if network_result is None:
            straight_distance = self._calculate_haversine_distance(
                start_lat, start_lon, end_lat, end_lon
            )
            return PipelineRoute(
                total_distance_km=straight_distance,
                access_distance_km=0.0,
                pipeline_distance_km=straight_distance,
                egress_distance_km=0.0,
                pipeline_types_used=[pipeline_type],
                route_found=True,
                calculation_method=f'{pipeline_type}_graph_only_fallback',
                route_geometry=[(start_lat, start_lon), (end_lat, end_lon)],
                start_coords=(start_lat, start_lon),
                end_coords=(end_lat, end_lon)
            )

        pipeline_distance, path_coords = network_result
        route_geometry = [(start_lat, start_lon)]
        for coord in path_coords:
            if coord != route_geometry[-1]:
                route_geometry.append(coord)
        if route_geometry[-1] != (end_lat, end_lon):
            route_geometry.append((end_lat, end_lon))

        return PipelineRoute(
            total_distance_km=pipeline_distance,
            access_distance_km=0.0,
            pipeline_distance_km=pipeline_distance,
            egress_distance_km=0.0,
            pipeline_types_used=[pipeline_type],
            route_found=True,
            calculation_method=f'{pipeline_type}_graph_only',
            route_geometry=route_geometry,
            start_coords=(start_lat, start_lon),
            end_coords=(end_lat, end_lon)
        )

    def _find_nearest_pipeline_point(self, lat: float, lon: float,
                                   pipeline_type: str,
                                   max_distance_km: float) -> Tuple[Optional[Tuple[float, float]], float]:
        """
        找到最近的管道点（点到管线的吸附算法）
        🚀 性能优化：使用KDTree空间索引加速查找，从O(N×M)降至O(logN)
        注意：max_distance_km参数保留用于向后兼容，但实际不再限制搜索距离

        Args:
            lat, lon: 查询点坐标
            pipeline_type: 管道类型
            max_distance_km: 最大搜索距离（已移除限制，保留参数用于兼容性）

        Returns:
            Tuple: (最近管道点坐标, 距离) 或 (None, 0)
        """
        features = self._get_pipeline_features(pipeline_type)
        if not features:
            return None, 0.0

        # 🚀 性能优化：优先使用KDTree空间索引
        if SCIPY_AVAILABLE and self.pipeline_spatial_indexes.get(pipeline_type):
            return self._find_nearest_pipeline_point_fast(lat, lon, pipeline_type)

        # 降级方案：使用传统线性搜索
        nearest_point = None
        min_distance = float('inf')

        for feature in features:
            # 检查geometry字段是否存在且不为None
            if not feature.get('geometry') or feature['geometry'].get('type') != 'LineString':
                continue

            coordinates = feature['geometry']['coordinates']
            if not coordinates:  # 检查坐标是否为空
                continue

            # 遍历管道的每个线段
            for i in range(len(coordinates) - 1):
                start_coord = coordinates[i]
                end_coord = coordinates[i + 1]

                # 计算点到线段的最短距离和最近点
                closest_point, distance = self._point_to_line_segment_distance(
                    lat, lon,
                    start_coord[1], start_coord[0],  # 转换为 (lat, lon)
                    end_coord[1], end_coord[0]
                )

                if distance < min_distance:
                    min_distance = distance
                    nearest_point = closest_point

        if nearest_point:
            return (nearest_point[0], nearest_point[1]), min_distance
        else:
            return None, 0.0

    def _find_nearest_pipeline_point_fast(self, lat: float, lon: float,
                                         pipeline_type: str) -> Tuple[Optional[Tuple[float, float]], float]:
        """
        🚀 性能优化：使用KDTree空间索引快速查找最近管道点
        复杂度从O(N×M)降至O(logN)，预期50倍加速

        Args:
            lat, lon: 查询点坐标
            pipeline_type: 管道类型

        Returns:
            Tuple: (最近管道点坐标, 距离) 或 (None, 0)
        """
        index_data = self.pipeline_spatial_indexes[pipeline_type]
        if not index_data:
            return None, 0.0

        tree = index_data['tree']
        segments = index_data['segments']

        # Step 1: KDTree查询最近的k个线段中点（O(logN)）
        k = min(30, len(segments))  # 查询最近30个候选线段
        distances, indices = tree.query([lat, lon], k=k)

        # Step 2: 对这k个候选线段进行精确距离计算
        nearest_point = None
        min_distance = float('inf')

        # 处理单个结果和多个结果的情况
        if k == 1:
            distances = [distances]
            indices = [indices]

        for idx in indices:
            if idx >= len(segments):
                continue

            segment_info = segments[idx]
            start = segment_info['start']  # (lat, lon)
            end = segment_info['end']      # (lat, lon)

            # 计算查询点到该线段的精确距离
            closest_point, distance = self._point_to_line_segment_distance(
                lat, lon,
                start[0], start[1],  # start lat, lon
                end[0], end[1]       # end lat, lon
            )

            if distance < min_distance:
                min_distance = distance
                nearest_point = closest_point

        if nearest_point:
            return (nearest_point[0], nearest_point[1]), min_distance
        else:
            return None, 0.0

    def _find_nearest_pipeline_points(self, lat: float, lon: float,
                                     pipeline_type: str,
                                     k: int = 5) -> List[Tuple[Tuple[float, float], float]]:
        """
        返回距离最近的前k个管道接入点（点到线段的最近点）
        """
        features = self._get_pipeline_features(pipeline_type)
        if not features or k <= 0:
            return []

        candidates: List[Tuple[Tuple[float, float], float]] = []

        # 优先使用KDTree加速
        if SCIPY_AVAILABLE and self.pipeline_spatial_indexes.get(pipeline_type):
            index_data = self.pipeline_spatial_indexes[pipeline_type]
            tree = index_data['tree']
            segments = index_data['segments']

            # 取更多候选线段，避免重复点
            k_candidates = min(max(k * 5, 10), len(segments))
            distances, indices = tree.query([lat, lon], k=k_candidates)
            if k_candidates == 1:
                distances = [distances]
                indices = [indices]

            for idx in indices:
                if idx >= len(segments):
                    continue
                segment_info = segments[idx]
                start = segment_info['start']
                end = segment_info['end']
                closest_point, distance = self._point_to_line_segment_distance(
                    lat, lon,
                    start[0], start[1],
                    end[0], end[1]
                )
                candidates.append(((closest_point[0], closest_point[1]), distance))
        else:
            # 线性搜索全部线段
            for feature in features:
                if not feature.get('geometry') or feature['geometry'].get('type') != 'LineString':
                    continue
                coordinates = feature['geometry']['coordinates']
                if not coordinates:
                    continue
                for i in range(len(coordinates) - 1):
                    start_coord = coordinates[i]
                    end_coord = coordinates[i + 1]
                    closest_point, distance = self._point_to_line_segment_distance(
                        lat, lon,
                        start_coord[1], start_coord[0],
                        end_coord[1], end_coord[0]
                    )
                    candidates.append(((closest_point[0], closest_point[1]), distance))

        if not candidates:
            return []

        # 去重并取最近k个
        uniq = {}
        for point, dist in candidates:
            key = (round(point[0], 6), round(point[1], 6))
            if key not in uniq or dist < uniq[key][1]:
                uniq[key] = (point, dist)

        sorted_points = sorted(uniq.values(), key=lambda x: x[1])
        return sorted_points[:k]

    def _point_to_line_segment_distance(self, px: float, py: float,
                                      ax: float, ay: float,
                                      bx: float, by: float) -> Tuple[Tuple[float, float], float]:
        """
        计算点到线段的最短距离和最近点

        Args:
            px, py: 查询点坐标
            ax, ay: 线段起点坐标
            bx, by: 线段终点坐标

        Returns:
            Tuple: ((最近点lat, 最近点lon), 距离km)
        """
        # 将地理坐标转换为平面坐标进行计算（使用简化投影）
        # 对于相对较小的距离，这种近似是可接受的

        # 计算线段向量
        ab_x = bx - ax
        ab_y = by - ay

        # 计算点到起点的向量
        ap_x = px - ax
        ap_y = py - ay

        # 计算投影长度比例
        ab_length_sq = ab_x * ab_x + ab_y * ab_y

        if ab_length_sq == 0:
            # 线段退化为点，返回点到点的距离
            closest_point = (ax, ay)
        else:
            # 计算投影比例 t
            t = max(0, min(1, (ap_x * ab_x + ap_y * ab_y) / ab_length_sq))

            # 计算最近点
            closest_x = ax + t * ab_x
            closest_y = ay + t * ab_y
            closest_point = (closest_x, closest_y)

        # 计算地理距离
        distance = self._calculate_haversine_distance(px, py, closest_point[0], closest_point[1])

        return closest_point, distance

    def _calculate_haversine_distance(self, lat1: float, lon1: float,
                                    lat2: float, lon2: float) -> float:
        """
        使用Haversine公式计算两点间的大圆距离

        Args:
            lat1, lon1: 起点纬度经度
            lat2, lon2: 终点纬度经度

        Returns:
            距离(公里)
        """
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

    def _find_nearest_node_in_component(self, start_node: str, target_coord: Tuple[float, float],
                                       graph: nx.Graph) -> Tuple[Optional[str], float]:
        """
        在start_node所在的连通分量中，找到距离target_coord最近的节点

        Args:
            start_node: 起始节点（必须在图中）
            target_coord: 目标坐标 (lat, lon)
            graph: NetworkX图

        Returns:
            Tuple[Optional[str], float]: (最近节点, 最小距离km)，如果未找到返回(None, inf)
        """
        if start_node not in graph:
            return None, float('inf')

        # 获取start_node所在的连通分量
        component = nx.node_connected_component(graph, start_node)

        min_distance = float('inf')
        nearest_node = None

        for node in component:
            try:
                node_lat, node_lon = map(float, node.split(','))
                distance = self._calculate_haversine_distance(
                    target_coord[0], target_coord[1], node_lat, node_lon
                )

                if distance < min_distance:
                    min_distance = distance
                    nearest_node = node

            except (ValueError, AttributeError):
                continue

        return nearest_node, min_distance

    def _calculate_network_distance(self, start_point: Tuple[float, float],
                                    end_point: Tuple[float, float],
                                    pipeline_type: str) -> Optional[Tuple[float, List[Tuple[float, float]]]]:
        """
        计算管道网络中两点间的最短路径距离和路径坐标

        Args:
            start_point: 起点坐标 (lat, lon)
            end_point: 终点坐标 (lat, lon)
            pipeline_type: 管道类型

        Returns:
            Tuple[距离(km), 路径坐标列表]，如果路径不存在返回None
        """
        # 特殊场景：起点终点重合时直接返回零距离，避免被判定为噪声点
        if (
            abs(start_point[0] - end_point[0]) < 1e-6
            and abs(start_point[1] - end_point[1]) < 1e-6
        ):
            return 0.0, [start_point, end_point]

        graph = self.pipeline_networks.get(pipeline_type)
        if not graph:
            return None

        # 将坐标转换为图节点格式
        start_node = f"{start_point[0]:.6f},{start_point[1]:.6f}"
        end_node = f"{end_point[0]:.6f},{end_point[1]:.6f}"

        # 如果起点或终点不在图中，找到最近的节点
        if start_node not in graph:
            start_node = self._find_nearest_graph_node(start_point, graph)
        if end_node not in graph:
            end_node = self._find_nearest_graph_node(end_point, graph)

        if not start_node or not end_node:
            return None

        # 使用NetworkX计算最短路径
        try:
            # 获取路径和距离
            path_nodes = nx.shortest_path(graph, start_node, end_node, weight='weight')
            path_length = nx.shortest_path_length(graph, start_node, end_node, weight='weight')

            # 重建完整的几何路径，从原始GIS数据中提取每条边对应的完整管道段几何
            path_coords = []

            # 获取NetworkX路径中每条边对应的完整原始几何信息
            detailed_path_coords = self._rebuild_detailed_path_from_original_data(
                path_nodes, pipeline_type
            )

            if detailed_path_coords:
                path_coords = detailed_path_coords
                logger.debug(f"成功重建详细路径，包含{len(path_coords)}个几何点")
            else:
                # 如果重建失败，使用简化的节点路径
                pass  # 静默处理路径重建失败
                for node in path_nodes:
                    lat_str, lon_str = node.split(',')
                    path_coords.append((float(lat_str), float(lon_str)))

            return path_length, path_coords

        except (nx.NetworkXNoPath, nx.NodeNotFound) as e:
            # 如果没有路径，检查是否是网络连通性问题
            logger.debug(f"NetworkX路径查找失败: {e}, 尝试使用直线距离连接不连通子图")

            # 尝试使用直线距离作为连接断开片段的桥梁
            try:
                # 检查起点和终点是否在不同的连通分量中
                if pipeline_type in self.pipeline_networks:
                    graph = self.pipeline_networks[pipeline_type]
                    components = list(nx.connected_components(graph))

                    if len(components) > 1:
                        # 网络不连通，使用直线距离连接，但尝试收集沿途的管道几何信息
                        logger.debug(f"{pipeline_type}管道网络有{len(components)}个不连通分量，使用直线距离连接")

                        # 计算直线距离
                        straight_distance = self._calculate_haversine_distance(
                            start_point[0], start_point[1],
                            end_point[0], end_point[1]
                        )

                        # 回退策略：使用“起点 → 接入点 → 终点”的三段式可视化
                        # 这里的 start_point/end_point 对应接入点坐标，上层会补充实际起终点
                        logger.debug(f"使用直线回退路径，距离{straight_distance:.3f}km")
                        return straight_distance, [start_point, end_point]
                    else:
                        # 网络连通但找不到路径（不应该发生，但作为降级处理）
                        logger.warning(f"{pipeline_type}管道网络连通但找不到路径，使用直线距离")
                        straight_distance = self._calculate_haversine_distance(
                            start_point[0], start_point[1],
                            end_point[0], end_point[1]
                        )
                        return straight_distance, [start_point, end_point]

                # 如果没有管道网络，返回None让上层处理
                logger.error(f"{pipeline_type}管道网络不存在")
                return None

            except Exception as ex:
                logger.error(f"连通性检查失败: {ex}, 返回None")
                return None

    def _find_nearest_graph_node(self, point: Tuple[float, float],
                                graph: nx.Graph) -> Optional[str]:
        """
        在图中找到最近的节点

        Args:
            point: 查询点坐标 (lat, lon)
            graph: NetworkX图

        Returns:
            最近节点的字符串标识
        """
        min_distance = float('inf')
        nearest_node = None

        for node in graph.nodes():
            # 解析节点坐标
            try:
                node_lat, node_lon = map(float, node.split(','))
                distance = self._calculate_haversine_distance(
                    point[0], point[1], node_lat, node_lon
                )

                if distance < min_distance:
                    min_distance = distance
                    nearest_node = node

            except (ValueError, AttributeError):
                continue

        return nearest_node

    def get_pipeline_coverage_info(self) -> Dict[str, Dict]:
        """
        获取管道覆盖范围信息

        Returns:
            Dict: 各类型管道的覆盖范围信息
        """
        if not any(self.pipeline_data.values()):
            self.load_pipeline_data()

        coverage_info = {}

        for pipeline_type, data in self.pipeline_data.items():
            if not data or 'features' not in data:
                coverage_info[pipeline_type] = {
                    'feature_count': 0,
                    'total_length_km': 0,
                    'lat_range': (0, 0),
                    'lon_range': (0, 0)
                }
                continue

            features = data['features']
            total_length = 0
            all_lats = []
            all_lons = []

            for feature in features:
                # 检查geometry字段是否存在且不为None
                if not feature.get('geometry') or feature['geometry'].get('type') != 'LineString':
                    continue

                coordinates = feature['geometry']['coordinates']
                if not coordinates:  # 检查坐标是否为空
                    continue

                # 计算管道长度
                for i in range(len(coordinates) - 1):
                    start_coord = coordinates[i]
                    end_coord = coordinates[i + 1]
                    segment_length = self._calculate_haversine_distance(
                        start_coord[1], start_coord[0],
                        end_coord[1], end_coord[0]
                    )
                    total_length += segment_length

                # 收集所有坐标
                for coord in coordinates:
                    all_lons.append(coord[0])
                    all_lats.append(coord[1])

            coverage_info[pipeline_type] = {
                'feature_count': len(features),
                'total_length_km': total_length,
                'lat_range': (min(all_lats) if all_lats else 0, max(all_lats) if all_lats else 0),
                'lon_range': (min(all_lons) if all_lons else 0, max(all_lons) if all_lons else 0)
            }

        return coverage_info

    def get_stats(self) -> Dict:
        """获取计算统计信息"""
        return self.stats.copy()

    def clear_cache(self):
        """清除缓存（如果有的话）"""
        if hasattr(self, '_calculation_cache'):
            self._calculation_cache.clear()

    def _rebuild_detailed_path_from_original_data(self, path_nodes: List[str],
                                                pipeline_type: str) -> List[Tuple[float, float]]:
        """
        从原始GIS数据中重建NetworkX路径的完整几何信息

        Args:
            path_nodes: NetworkX路径的节点序列
            pipeline_type: 管道类型

        Returns:
            完整的几何坐标序列，包含所有原始管道段的中间点
        """
        if not path_nodes or len(path_nodes) < 2:
            return []

        features = self._get_pipeline_features(pipeline_type)
        if not features:
            return []
        detailed_coords = []

        logger.debug(f"开始重建路径几何，路径节点数: {len(path_nodes)}")

        # 处理路径中的每条边
        for i in range(len(path_nodes) - 1):
            prev_node = path_nodes[i]
            curr_node = path_nodes[i + 1]

            # 解析节点坐标
            prev_lat, prev_lon = map(float, prev_node.split(','))
            curr_lat, curr_lon = map(float, curr_node.split(','))

            # 在原始GIS数据中查找包含这条边的管道段
            edge_geometry = self._find_original_pipeline_geometry(
                (prev_lat, prev_lon), (curr_lat, curr_lon), features
            )

            if edge_geometry:
                logger.debug(f"找到边 {i+1}/{len(path_nodes)-1} 的原始几何信息，包含{len(edge_geometry)}个点")

                if i == 0:
                    # 第一条边，添加所有点
                    detailed_coords.extend(edge_geometry)
                else:
                    # 后续边，跳过第一个点避免重复
                    detailed_coords.extend(edge_geometry[1:])
            else:
                pass  # 静默处理几何信息缺失

                if i == 0:
                    # 第一条边，添加起点
                    detailed_coords.append((prev_lat, prev_lon))
                # 总是添加终点
                detailed_coords.append((curr_lat, curr_lon))

        logger.debug(f"路径重建完成，总几何点数: {len(detailed_coords)}")
        return detailed_coords

    def _find_original_pipeline_geometry(self, start_point: Tuple[float, float],
                                       end_point: Tuple[float, float],
                                       features: List[Dict]) -> List[Tuple[float, float]]:
        """
        在原始GIS数据中查找包含指定两点的管道段的完整几何信息

        Args:
            start_point: 起点坐标 (lat, lon)
            end_point: 终点坐标 (lat, lon)
            features: GIS特征列表

        Returns:
            管道段的完整几何坐标序列
        """
        tolerance = 1e-5  # 坐标匹配容差

        for feature in features:
            if not feature.get('geometry') or feature['geometry'].get('type') != 'LineString':
                continue

            coordinates = feature['geometry']['coordinates']
            if not coordinates or len(coordinates) < 2:
                continue

            # 检查该管道段是否包含起点和终点
            start_found = False
            end_found = False
            start_idx = -1
            end_idx = -1

            for idx, coord in enumerate(coordinates):
                coord_lat, coord_lon = coord[1], coord[0]  # GeoJSON格式是[lon, lat]

                # 检查是否匹配起点
                if (abs(coord_lat - start_point[0]) < tolerance and
                    abs(coord_lon - start_point[1]) < tolerance):
                    start_found = True
                    start_idx = idx

                # 检查是否匹配终点
                if (abs(coord_lat - end_point[0]) < tolerance and
                    abs(coord_lon - end_point[1]) < tolerance):
                    end_found = True
                    end_idx = idx

            # 如果找到包含两个端点的管道段
            if start_found and end_found:
                # 确保索引顺序正确
                if start_idx > end_idx:
                    start_idx, end_idx = end_idx, start_idx

                # 提取该段的完整几何信息
                segment_coords = []
                for idx in range(start_idx, end_idx + 1):
                    coord = coordinates[idx]
                    segment_coords.append((coord[1], coord[0]))  # 转换为(lat, lon)格式

                logger.debug(f"找到匹配的管道段，提取{len(segment_coords)}个几何点")
                return segment_coords

        return []  # 未找到匹配的管道段

    def _collect_nearby_pipeline_geometry(self, start_point: Tuple[float, float],
                                        end_point: Tuple[float, float],
                                        pipeline_type: str,
                                        max_distance_km: float = 50.0) -> List[Tuple[float, float]]:
        """
        收集直线路径附近的管道几何信息，用于增强直线桥接路径

        Args:
            start_point: 起点坐标 (lat, lon)
            end_point: 终点坐标 (lat, lon)
            pipeline_type: 管道类型
            max_distance_km: 搜索管道的最大距离

        Returns:
            增强的路径坐标序列
        """
        features = self._get_pipeline_features(pipeline_type)
        if not features:
            return []
        enhanced_path = []

        logger.debug(f"收集直线路径附近的{pipeline_type}管道几何信息")

        # 在直线路径上生成采样点
        num_samples = 10  # 在直线上采样10个点
        sample_points = []

        for i in range(num_samples + 1):
            ratio = i / num_samples
            sample_lat = start_point[0] + ratio * (end_point[0] - start_point[0])
            sample_lon = start_point[1] + ratio * (end_point[1] - start_point[1])
            sample_points.append((sample_lat, sample_lon))

        logger.debug(f"生成{len(sample_points)}个采样点，搜索半径{max_distance_km}km")

        # 为每个采样点查找附近的管道段
        collected_segments = []

        for sample_point in sample_points:
            nearby_segments = self._find_nearby_pipeline_segments(
                sample_point, features, max_distance_km
            )

            for segment in nearby_segments:
                # 避免重复添加相同的管道段
                segment_id = id(segment)  # 使用对象ID作为唯一标识
                if segment_id not in [id(s) for s in collected_segments]:
                    collected_segments.append(segment)

        logger.debug(f"找到{len(collected_segments)}个附近的管道段")

        # 从收集的管道段中提取几何信息并按距离排序
        if collected_segments:
            # 按照管道段到起点的距离排序
            def distance_to_start(segment):
                coords = segment['geometry']['coordinates']
                if coords:
                    # 计算管道段中心点到起点的距离
                    center_idx = len(coords) // 2
                    center_coord = coords[center_idx]
                    return self._calculate_haversine_distance(
                        start_point[0], start_point[1],
                        center_coord[1], center_coord[0]
                    )
                return float('inf')

            sorted_segments = sorted(collected_segments, key=distance_to_start)

            # 提取几何信息
            enhanced_path = [start_point]  # 添加起点

            for segment in sorted_segments:
                coords = segment['geometry']['coordinates']
                if coords and len(coords) > 2:
                    # 添加管道段的所有中间点（跳过首尾点避免重复）
                    for coord in coords[1:-1]:
                        enhanced_path.append((coord[1], coord[0]))  # 转换为(lat, lon)

            enhanced_path.append(end_point)  # 添加终点

            # 去除重复的连续坐标点
            filtered_path = []
            prev_coord = None
            tolerance = 1e-6

            for coord in enhanced_path:
                if (prev_coord is None or
                    abs(coord[0] - prev_coord[0]) > tolerance or
                    abs(coord[1] - prev_coord[1]) > tolerance):
                    filtered_path.append(coord)
                    prev_coord = coord

            logger.debug(f"路径增强完成：{len(enhanced_path)}个原始点 -> {len(filtered_path)}个过滤后的点")
            return filtered_path

        return []

    def _find_nearby_pipeline_segments(self, point: Tuple[float, float],
                                     features: List[Dict],
                                     max_distance_km: float) -> List[Dict]:
        """
        查找指定点附近的管道段

        Args:
            point: 查询点坐标 (lat, lon)
            features: GIS特征列表
            max_distance_km: 最大搜索距离

        Returns:
            附近的管道段列表
        """
        nearby_segments = []

        for feature in features:
            if not feature.get('geometry') or feature['geometry'].get('type') != 'LineString':
                continue

            coordinates = feature['geometry']['coordinates']
            if not coordinates or len(coordinates) < 2:
                continue

            # 检查管道段是否在搜索范围内
            min_distance = float('inf')

            for coord in coordinates:
                coord_lat, coord_lon = coord[1], coord[0]  # GeoJSON格式
                distance = self._calculate_haversine_distance(
                    point[0], point[1], coord_lat, coord_lon
                )
                if distance < min_distance:
                    min_distance = distance

            # 如果管道段在搜索范围内，添加到结果中
            if min_distance <= max_distance_km:
                nearby_segments.append(feature)

        return nearby_segments

    @lru_cache(maxsize=1000)
    def _cached_haversine_distance(self, lat1: float, lon1: float,
                                  lat2: float, lon2: float) -> float:
        """缓存版本的Haversine距离计算"""
        return self._calculate_haversine_distance(lat1, lon1, lat2, lon2)

    def export_route_to_geojson(self, route: PipelineRoute, route_name: str = "氢气运输路径") -> Dict:
        """
        将氢气运输路径导出为GeoJSON格式

        Args:
            route: PipelineRoute对象
            route_name: 路径名称

        Returns:
            Dict: GeoJSON格式的路径数据
        """
        if not route.route_found or not route.route_geometry:
            return {"type": "FeatureCollection", "features": []}

        features = []

        # 1. 创建路径线要素
        if len(route.route_geometry) >= 2:
            line_coords = [[lon, lat] for lat, lon in route.route_geometry]  # GeoJSON使用[lon, lat]格式

            line_feature = {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": line_coords
                },
                "properties": {
                    "name": route_name,
                    "route_type": "hydrogen_transport",
                    "total_distance_km": round(route.total_distance_km, 2),
                    "access_distance_km": round(route.access_distance_km, 2),
                    "pipeline_distance_km": round(route.pipeline_distance_km, 2),
                    "egress_distance_km": round(route.egress_distance_km, 2),
                    "pipeline_types_used": route.pipeline_types_used,
                    "calculation_method": route.calculation_method
                }
            }
            features.append(line_feature)

        # 2. 创建起点要素
        if route.start_coords:
            start_feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [route.start_coords[1], route.start_coords[0]]  # [lon, lat]
                },
                "properties": {
                    "name": f"{route_name}_起点",
                    "point_type": "start",
                    "route_name": route_name
                }
            }
            features.append(start_feature)

        # 3. 创建终点要素
        if route.end_coords:
            end_feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [route.end_coords[1], route.end_coords[0]]  # [lon, lat]
                },
                "properties": {
                    "name": f"{route_name}_终点",
                    "point_type": "end",
                    "route_name": route_name
                }
            }
            features.append(end_feature)

        # 4. 创建管道接入点要素
        if route.access_point_coords:
            access_feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [route.access_point_coords[1], route.access_point_coords[0]]  # [lon, lat]
                },
                "properties": {
                    "name": f"{route_name}_管道接入点",
                    "point_type": "access",
                    "route_name": route_name,
                    "access_distance_km": round(route.access_distance_km, 2)
                }
            }
            features.append(access_feature)

        # 5. 创建管道离开点要素
        if route.egress_point_coords:
            egress_feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [route.egress_point_coords[1], route.egress_point_coords[0]]  # [lon, lat]
                },
                "properties": {
                    "name": f"{route_name}_管道离开点",
                    "point_type": "egress",
                    "route_name": route_name,
                    "egress_distance_km": round(route.egress_distance_km, 2)
                }
            }
            features.append(egress_feature)

        return {
            "type": "FeatureCollection",
            "features": features
        }

    def export_multiple_routes_to_geojson(self, routes: List[Tuple[PipelineRoute, str]]) -> Dict:
        """
        将多条氢气运输路径导出为GeoJSON格式

        Args:
            routes: List of (PipelineRoute, route_name) tuples

        Returns:
            Dict: GeoJSON格式的多路径数据
        """
        all_features = []

        for route, route_name in routes:
            route_geojson = self.export_route_to_geojson(route, route_name)
            all_features.extend(route_geojson["features"])

        return {
            "type": "FeatureCollection",
            "features": all_features
        }

    def calculate_clustered_pipeline_route(self,
                                          cluster_id: int,
                                          cluster_members: List[Tuple[str, Tuple[float, float]]],
                                          cluster_center: Tuple[float, float],
                                          destination: Tuple[float, float]) -> ClusteredPipelineRoute:
        pass  # 静默处理聚类计算信息

        layer1_distances = {}
        for member_name, member_coord in cluster_members:
            distance = self._calculate_haversine_distance(
                member_coord[0], member_coord[1],
                cluster_center[0], cluster_center[1]
            )
            layer1_distances[member_name] = distance
            logger.debug(f"Layer1: {member_name} -> 聚类中心: {distance:.2f}km")

        center_access_point, layer2_distance = self._find_nearest_pipeline_point(
            cluster_center[0], cluster_center[1], 'mixed', float('inf')
        )

        if center_access_point is None:
            logger.error(f"聚类{cluster_id}中心点无法找到管道接入点")
            return ClusteredPipelineRoute(
                cluster_id=cluster_id,
                layer1_distances=layer1_distances,
                layer2_distance=0.0,
                layer3_distance=0.0,
                total_distance_per_member={},
                route_found=False
            )

        logger.debug(f"Layer2: 聚类中心 -> 管道接入点: {layer2_distance:.2f}km")

        network_result = self._calculate_network_distance(
            center_access_point, destination, 'mixed'
        )

        if network_result is None:
            layer3_distance = self._calculate_haversine_distance(
                center_access_point[0], center_access_point[1],
                destination[0], destination[1]
            )
            pipeline_coords = [center_access_point, destination]
            pass  # 静默处理直线距离降级
        else:
            layer3_distance, pipeline_coords = network_result
            logger.debug(f"Layer3: 管道网络距离: {layer3_distance:.2f}km")

        total_distance_per_member = {}
        for member_name in layer1_distances:
            total_distance_per_member[member_name] = (
                layer1_distances[member_name] + layer2_distance + layer3_distance
            )

        # 构建每个成员的独立路径几何
        route_geometry_per_member = {}
        for member_name, member_coord in cluster_members:
            # 每个成员的路径：成员坐标 -> 聚类中心 -> 管道接入点 -> 管道网络路径
            member_route = [
                member_coord,
                cluster_center,
                center_access_point
            ]
            member_route.extend(pipeline_coords)
            route_geometry_per_member[member_name] = member_route

        # 保留旧的route_geometry字段以兼容（但不再使用）
        route_geometry = []
        for member_name, member_coord in cluster_members:
            route_geometry.append(member_coord)
        route_geometry.append(cluster_center)
        route_geometry.append(center_access_point)
        route_geometry.extend(pipeline_coords)

        return ClusteredPipelineRoute(
            cluster_id=cluster_id,
            layer1_distances=layer1_distances,
            layer2_distance=layer2_distance,
            layer3_distance=layer3_distance,
            total_distance_per_member=total_distance_per_member,
            route_geometry=route_geometry,
            route_geometry_per_member=route_geometry_per_member,
            cluster_center=cluster_center,
            pipeline_access_point=center_access_point,
            pipeline_types_used=['mixed'],
            route_found=True
        )

    def save_route_geojson(self, route: PipelineRoute, output_file: str, route_name: str = "氢气运输路径") -> bool:
        """
        保存氢气运输路径为GeoJSON文件

        Args:
            route: PipelineRoute对象
            output_file: 输出文件路径
            route_name: 路径名称

        Returns:
            bool: 保存是否成功
        """
        try:
            geojson_data = self.export_route_to_geojson(route, route_name)

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(geojson_data, f, ensure_ascii=False, indent=2)

            logger.info(f"氢气运输路径已保存为GeoJSON文件: {output_file}")
            return True

        except Exception as e:
            logger.error(f"保存GeoJSON文件失败: {e}")
            return False

    # ======= 缓存管理方法 =======

    def get_cache_statistics(self) -> Dict:
        """获取缓存统计信息"""
        if self.pipeline_cache_manager:
            advanced_stats = self.pipeline_cache_manager.get_cache_statistics()
            self.stats['advanced_cache_stats'] = advanced_stats
        else:
            self.stats['advanced_cache_stats'] = {"status": "基础缓存模式"}

        return {
            'basic_stats': {
                'total_calculations': self.stats['total_calculations'],
                'cache_hits': self.stats['cache_hits'],
                'successful_routes': self.stats['successful_routes'],
                'failed_routes': self.stats['failed_routes'],
                'cache_hit_rate': (self.stats['cache_hits'] / max(self.stats['total_calculations'], 1)) * 100
            },
            'pipeline_usage': self.stats['pipeline_type_usage'],
            'advanced_cache_stats': self.stats['advanced_cache_stats']
        }

    def clear_cache(self) -> Dict:
        """清理所有缓存"""
        result = {
            'basic_cache_cleared': False,
            'advanced_cache_cleared': False,
            'lru_cache_cleared': False
        }

        # 清理基础缓存统计
        old_hits = self.stats['cache_hits']
        self.stats.update({
            'cache_hits': 0,
            'advanced_cache_stats': {}
        })
        result['basic_cache_cleared'] = True

        # 清理LRU缓存
        if hasattr(self, '_calculation_cache'):
            self._calculation_cache.clear()

        # 清理haversine距离缓存
        if hasattr(self.__class__, '_cached_haversine_distance'):
            self.__class__._cached_haversine_distance.cache_clear()
        result['lru_cache_cleared'] = True

        # 清理高级缓存
        if self.pipeline_cache_manager:
            advanced_result = self.pipeline_cache_manager.clear_all_cache()
            result['advanced_cache_result'] = advanced_result
            result['advanced_cache_cleared'] = advanced_result.get('success', False)

        result['total_cleared_hits'] = old_hits
        logger.info(f"缓存清理完成，清除了{old_hits}个基础缓存命中记录")

        return result

    def cleanup_expired_cache(self) -> Dict:
        """清理过期的缓存条目"""
        if self.pipeline_cache_manager:
            return self.pipeline_cache_manager.cleanup_expired_cache()
        else:
            return {"message": "基础缓存模式，无过期缓存清理功能"}

    def optimize_cache_performance(self) -> Dict:
        """优化缓存性能"""
        if self.pipeline_cache_manager:
            return self.pipeline_cache_manager.optimize_cache_performance()
        else:
            # 对基础缓存进行简单优化
            if hasattr(self.__class__, '_cached_haversine_distance'):
                cache_info = self.__class__._cached_haversine_distance.cache_info()
                if cache_info.misses > cache_info.hits * 2:  # 如果miss次数是hit的2倍以上
                    self.__class__._cached_haversine_distance.cache_clear()
                    return {
                        "optimization": "LRU缓存已清理（低命中率）",
                        "cache_info_before": cache_info._asdict()
                    }
                else:
                    return {
                        "optimization": "LRU缓存性能良好，无需清理",
                        "cache_info": cache_info._asdict()
                    }
            return {"message": "基础缓存模式，优化功能有限"}

    def validate_cache_data_sources(self) -> Dict:
        """验证缓存数据源有效性"""
        result = {
            'pipeline_data_files': {},
            'cache_validation': {}
        }

        # 检查管道数据文件
        pipeline_files = {
            'crude': 'crude_pipelines.geojson',
            'refined': 'refined_product_pipelines.geojson',
            'natural_gas': 'natural_gas_pipelines.geojson'
        }

        for pipeline_type, filename in pipeline_files.items():
            file_path = self.gis_data_path / filename
            result['pipeline_data_files'][pipeline_type] = {
                'file_path': str(file_path),
                'exists': file_path.exists(),
                'size_bytes': file_path.stat().st_size if file_path.exists() else 0
            }

        # 验证高级缓存
        if self.pipeline_cache_manager:
            result['cache_validation'] = self.pipeline_cache_manager.validate_pipeline_data_files()
        else:
            result['cache_validation'] = {"status": "基础缓存模式，数据验证功能有限"}

        return result

def main():
    """主函数，用于测试"""
    import sys
    from pathlib import Path

    # 设置数据路径
    current_dir = Path(__file__).parent
    gis_data_path = current_dir.parent.parent.parent / "gis_energy_mapping" / "gis_data_scraper" / "scraped_gis_data"

    print("初始化氢气管道距离计算器...")
    calculator = HydrogenPipelineDistanceCalculator(str(gis_data_path))

    print("加载管道数据...")
    calculator.load_pipeline_data()

    print("获取管道覆盖范围信息...")
    coverage_info = calculator.get_pipeline_coverage_info()
    for pipeline_type, info in coverage_info.items():
        print(f"{pipeline_type}管道: {info['feature_count']}条, "
              f"总长度{info['total_length_km']:.1f}km")

    # 测试距离计算（使用北京和上海的大概坐标）
    print("\n测试路径计算...")
    beijing_lat, beijing_lon = 39.9042, 116.4074
    shanghai_lat, shanghai_lon = 31.2304, 121.4737

    result = calculator.calculate_pipeline_distance(
        beijing_lat, beijing_lon, shanghai_lat, shanghai_lon
    )

    print(f"北京到上海的管道运输距离计算结果:")
    print(f"  路径找到: {result.route_found}")
    print(f"  总距离: {result.total_distance_km:.1f}km")
    print(f"  接入距离: {result.access_distance_km:.1f}km")
    print(f"  管道距离: {result.pipeline_distance_km:.1f}km")
    print(f"  接出距离: {result.egress_distance_km:.1f}km")
    print(f"  使用管道: {result.pipeline_types_used}")
    print(f"  计算方法: {result.calculation_method}")

    print(f"\n统计信息:")
    stats = calculator.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")

if __name__ == "__main__":
    main()
