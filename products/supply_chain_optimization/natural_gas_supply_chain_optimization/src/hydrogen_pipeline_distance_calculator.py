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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PipelineRouteNotFoundError(Exception):
    """管道路径未找到异常"""

    def __init__(self, start_lat: float, start_lon: float, end_lat: float, end_lon: float,
                 max_access_distance_km: float, pipeline_types_tried: List[str]):
        self.start_lat = start_lat
        self.start_lon = start_lon
        self.end_lat = end_lat
        self.end_lon = end_lon
        self.max_access_distance_km = max_access_distance_km
        self.pipeline_types_tried = pipeline_types_tried

        message = (f"未找到管道运输路径: "
                  f"起点({start_lat:.6f}, {start_lon:.6f}) -> "
                  f"终点({end_lat:.6f}, {end_lon:.6f}), "
                  f"最大接入距离: {max_access_distance_km}km, "
                  f"尝试的管道类型: {', '.join(pipeline_types_tried)}")
        super().__init__(message)

@dataclass
class PipelineRoute:
    """管道路径结果数据类"""
    total_distance_km: float
    access_distance_km: float  # 起点吸附距离
    pipeline_distance_km: float  # 管道网络距离
    egress_distance_km: float  # 终点吸附距离
    pipeline_types_used: List[str]  # 使用的管道类型
    route_found: bool
    calculation_method: str
    # 新增几何信息字段
    route_geometry: Optional[List[Tuple[float, float]]] = None  # 路径几何坐标序列 [(lat, lon), ...]
    access_point_coords: Optional[Tuple[float, float]] = None  # 起点接入管道的坐标
    egress_point_coords: Optional[Tuple[float, float]] = None  # 终点离开管道的坐标
    start_coords: Optional[Tuple[float, float]] = None  # 起点原始坐标
    end_coords: Optional[Tuple[float, float]] = None  # 终点原始坐标

@dataclass
class PipelinePoint:
    """管道点数据类"""
    lat: float
    lon: float
    pipeline_id: str
    pipeline_type: str  # 'crude', 'refined', 'natural_gas'
    segment_id: int  # 在管道中的线段编号

class HydrogenPipelineDistanceCalculator:
    """氢气管道运输距离计算器"""

    def __init__(self, gis_data_path: str, enable_cache: bool = True):
        """
        初始化计算器

        Args:
            gis_data_path: GIS数据目录路径
            enable_cache: 是否启用计算缓存
        """
        self.gis_data_path = Path(gis_data_path)
        self.enable_cache = enable_cache

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
            'natural_gas': None
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
                'natural_gas': 0
            }
        }

        logger.info(f"氢气管道距离计算器初始化完成，GIS数据路径: {gis_data_path}")

    def load_pipeline_data(self) -> Dict[str, Dict]:
        """
        加载所有管道数据

        Returns:
            Dict: 包含三种管道数据的字典
        """
        logger.info("开始加载管道数据...")

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
                logger.info(f"成功加载{pipeline_type}管道数据: {feature_count} 个要素")

            except Exception as e:
                logger.error(f"加载{pipeline_type}管道数据失败: {e}")
                self.pipeline_data[pipeline_type] = {'features': []}

        # 构建管道网络图
        self._build_pipeline_networks()

        total_pipelines = sum(len(data['features']) for data in self.pipeline_data.values())
        logger.info(f"管道数据加载完成，总管道数: {total_pipelines}")

        return self.pipeline_data

    def _build_pipeline_networks(self):
        """构建管道网络图"""
        logger.info("构建管道网络图...")

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
            logger.info(f"{pipeline_type}管道网络: {graph.number_of_nodes()} 节点, "
                       f"{graph.number_of_edges()} 边")

    def calculate_pipeline_distance(self, start_lat: float, start_lon: float,
                                  end_lat: float, end_lon: float,
                                  max_access_distance_km: float = 100.0) -> PipelineRoute:
        """
        计算基于管道网络的氢气运输距离
        注意：max_access_distance_km参数保留用于向后兼容，但不再限制搜索距离

        Args:
            start_lat, start_lon: 起点坐标
            end_lat, end_lon: 终点坐标
            max_access_distance_km: 保留参数，不再限制距离

        Returns:
            PipelineRoute: 管道路径结果
        """
        self.stats['total_calculations'] += 1

        if not any(self.pipeline_data.values()):
            self.load_pipeline_data()

        logger.info(f"计算管道运输距离: ({start_lat:.6f},{start_lon:.6f}) -> "
                   f"({end_lat:.6f},{end_lon:.6f})")

        best_route = None
        best_distance = float('inf')

        # 尝试每种管道类型
        for pipeline_type in ['crude', 'refined', 'natural_gas']:
            try:
                route = self._calculate_single_pipeline_route(
                    start_lat, start_lon, end_lat, end_lon,
                    pipeline_type, float('inf')  # 移除距离限制
                )

                if route.route_found and route.total_distance_km < best_distance:
                    best_distance = route.total_distance_km
                    best_route = route

            except Exception as e:
                logger.warning(f"{pipeline_type}管道路径计算失败: {e}")
                continue

        if best_route and best_route.route_found:
            self.stats['successful_routes'] += 1
            # 更新管道类型使用统计
            for pipeline_type in best_route.pipeline_types_used:
                self.stats['pipeline_type_usage'][pipeline_type] += 1

            logger.info(f"找到最优管道路径: {best_route.total_distance_km:.3f}km "
                       f"(使用{best_route.pipeline_types_used}管道)")
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
        计算单一管道类型的路径

        Args:
            start_lat, start_lon: 起点坐标
            end_lat, end_lon: 终点坐标
            pipeline_type: 管道类型
            max_access_distance_km: 最大接入距离

        Returns:
            PipelineRoute: 单一管道类型的路径结果
        """
        # 1. 找到起点最近的管道接入点
        start_access_point, start_access_distance = self._find_nearest_pipeline_point(
            start_lat, start_lon, pipeline_type, float('inf')  # 移除距离限制
        )

        if start_access_point is None:
            return PipelineRoute(
                total_distance_km=0.0,
                access_distance_km=0.0,
                pipeline_distance_km=0.0,
                egress_distance_km=0.0,
                pipeline_types_used=[],
                route_found=False,
                calculation_method=f'{pipeline_type}_start_access_failed'
            )

        # 2. 找到终点最近的管道接入点
        end_access_point, end_access_distance = self._find_nearest_pipeline_point(
            end_lat, end_lon, pipeline_type, float('inf')  # 移除距离限制
        )

        if end_access_point is None:
            return PipelineRoute(
                total_distance_km=0.0,
                access_distance_km=0.0,
                pipeline_distance_km=0.0,
                egress_distance_km=0.0,
                pipeline_types_used=[],
                route_found=False,
                calculation_method=f'{pipeline_type}_end_access_failed'
            )

        # 3. 计算管道网络距离和路径
        network_result = self._calculate_network_distance(
            start_access_point, end_access_point, pipeline_type
        )

        if network_result is None:
            return PipelineRoute(
                total_distance_km=0.0,
                access_distance_km=0.0,
                pipeline_distance_km=0.0,
                egress_distance_km=0.0,
                pipeline_types_used=[],
                route_found=False,
                calculation_method=f'{pipeline_type}_network_path_failed'
            )

        pipeline_distance, pipeline_coords = network_result

        # 检查网络路径是否有效
        if pipeline_distance == 0.0 or not pipeline_coords:
            return PipelineRoute(
                total_distance_km=0.0,
                access_distance_km=0.0,
                pipeline_distance_km=0.0,
                egress_distance_km=0.0,
                pipeline_types_used=[],
                route_found=False,
                calculation_method=f'{pipeline_type}_network_no_path'
            )

        # 4. 计算总距离
        total_distance = start_access_distance + pipeline_distance + end_access_distance

        # 5. 构建完整的路径几何信息
        complete_route_geometry = []
        # 添加起点
        complete_route_geometry.append((start_lat, start_lon))
        # 添加起点接入坐标
        if start_access_point != (start_lat, start_lon):
            complete_route_geometry.append(start_access_point)
        # 添加管道路径坐标
        complete_route_geometry.extend(pipeline_coords)
        # 添加终点离开坐标
        if end_access_point != (end_lat, end_lon):
            complete_route_geometry.append(end_access_point)
        # 添加终点
        complete_route_geometry.append((end_lat, end_lon))

        return PipelineRoute(
            total_distance_km=total_distance,
            access_distance_km=start_access_distance,
            pipeline_distance_km=pipeline_distance,
            egress_distance_km=end_access_distance,
            pipeline_types_used=[pipeline_type],
            route_found=True,
            calculation_method=f'{pipeline_type}_success',
            # 添加几何信息
            route_geometry=complete_route_geometry,
            access_point_coords=start_access_point,
            egress_point_coords=end_access_point,
            start_coords=(start_lat, start_lon),
            end_coords=(end_lat, end_lon)
        )

    def _find_nearest_pipeline_point(self, lat: float, lon: float,
                                   pipeline_type: str,
                                   max_distance_km: float) -> Tuple[Optional[Tuple[float, float]], float]:
        """
        找到最近的管道点（点到管线的吸附算法）
        注意：max_distance_km参数保留用于向后兼容，但实际不再限制搜索距离

        Args:
            lat, lon: 查询点坐标
            pipeline_type: 管道类型
            max_distance_km: 最大搜索距离（已移除限制，保留参数用于兼容性）

        Returns:
            Tuple: (最近管道点坐标, 距离) 或 (None, 0)
        """
        if pipeline_type not in self.pipeline_data or not self.pipeline_data[pipeline_type]:
            return None, 0.0

        nearest_point = None
        min_distance = float('inf')

        for feature in self.pipeline_data[pipeline_type]['features']:
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
                logger.warning(f"无法重建详细路径，使用简化节点路径")
                for node in path_nodes:
                    lat_str, lon_str = node.split(',')
                    path_coords.append((float(lat_str), float(lon_str)))

            return path_length, path_coords

        except (nx.NetworkXNoPath, nx.NodeNotFound):
            # 如果没有路径，检查是否是网络连通性问题
            logger.warning(f"管道网络中找不到路径: 起点{start_point} -> 终点{end_point}")

            # 尝试使用直线距离作为连接断开片段的桥梁
            try:
                # 检查起点和终点是否在不同的连通分量中
                if pipeline_type in self.pipeline_networks:
                    graph = self.pipeline_networks[pipeline_type]
                    components = list(nx.connected_components(graph))

                    if len(components) > 1:
                        # 网络不连通，使用直线距离连接，但尝试收集沿途的管道几何信息
                        logger.info(f"{pipeline_type}管道网络有{len(components)}个连通分量，使用直线距离桥接")

                        # 计算直线距离
                        straight_distance = self._calculate_haversine_distance(
                            start_point[0], start_point[1],
                            end_point[0], end_point[1]
                        )

                        # 尝试收集直线路径附近的管道几何信息
                        enhanced_path = self._collect_nearby_pipeline_geometry(
                            start_point, end_point, pipeline_type, max_distance_km=50.0
                        )

                        if enhanced_path and len(enhanced_path) > 2:
                            logger.info(f"直线桥接路径增强：从2个点扩展到{len(enhanced_path)}个点")
                            return straight_distance, enhanced_path
                        else:
                            # 如果无法增强，返回简单的直线路径
                            return straight_distance, [start_point, end_point]

                return 0.0, []

            except Exception as e:
                logger.warning(f"连通性检查失败: {e}")
                return 0.0, []

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

        if pipeline_type not in self.pipeline_data or not self.pipeline_data[pipeline_type]:
            return []

        features = self.pipeline_data[pipeline_type].get('features', [])
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
                logger.warning(f"未找到边 {i+1}/{len(path_nodes)-1} 的原始几何信息，使用节点坐标")

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
        if pipeline_type not in self.pipeline_data or not self.pipeline_data[pipeline_type]:
            return []

        features = self.pipeline_data[pipeline_type].get('features', [])
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