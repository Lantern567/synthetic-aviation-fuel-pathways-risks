"""
CO2捕获源聚类优化器
基于DBSCAN算法对CO2捕获源（煤电厂）进行地理聚类
优化聚类中心点位置以最小化管道运输成本
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass
from math import radians, sin, cos, sqrt, atan2
import logging
import json
from pathlib import Path
import time

try:
    from numba import jit, prange
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
    logger.warning("Numba不可用，将使用NumPy实现（速度较慢）。建议: pip install numba")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# Numba加速函数（编译为机器码，实现并行计算）
# ============================================================================

if NUMBA_AVAILABLE:
    @jit(nopython=True, parallel=True, cache=True)
    def _compute_haversine_distances_numba(lats: np.ndarray, lons: np.ndarray,
                                          eps_rad: float) -> np.ndarray:
        """
        使用Numba JIT并行计算Haversine距离并生成邻接矩阵

        Args:
            lats: 纬度数组（弧度）, shape (n,)
            lons: 经度数组（弧度）, shape (n,)
            eps_rad: 距离阈值（弧度）

        Returns:
            adjacency_matrix: 布尔邻接矩阵, shape (n, n)
        """
        n = len(lats)
        adjacency_matrix = np.zeros((n, n), dtype=np.bool_)

        # 并行计算：每个核心处理一部分行
        for i in prange(n):
            lat1 = lats[i]
            lon1 = lons[i]

            for j in range(n):
                lat2 = lats[j]
                lon2 = lons[j]

                # Haversine公式
                dlat = lat2 - lat1
                dlon = lon2 - lon1
                a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
                c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))

                # 判断是否在邻域内
                if c <= eps_rad:
                    adjacency_matrix[i, j] = True

        return adjacency_matrix

def _compute_haversine_distances_numpy(coords_rad: np.ndarray,
                                      eps_rad: float) -> np.ndarray:
    """
    使用NumPy向量化计算Haversine距离（备用方案）

    Args:
        coords_rad: 坐标数组（弧度）, shape (n, 2)
        eps_rad: 距离阈值（弧度）

    Returns:
        adjacency_matrix: 布尔邻接矩阵, shape (n, n)
    """
    lats = coords_rad[:, 0]
    lons = coords_rad[:, 1]

    # 向量化计算
    dlat = lats[:, np.newaxis] - lats[np.newaxis, :]
    dlon = lons[:, np.newaxis] - lons[np.newaxis, :]

    a = np.sin(dlat/2)**2 + np.cos(lats[:, np.newaxis]) * np.cos(lats[np.newaxis, :]) * np.sin(dlon/2)**2
    distance_rad = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))

    adjacency_matrix = distance_rad <= eps_rad
    return adjacency_matrix

@dataclass
class CO2Cluster:
    cluster_id: int
    member_locations: List[str]
    member_coords: List[Tuple[float, float]]
    center_coord: Tuple[float, float]
    geo_center: Tuple[float, float]
    pipeline_optimized_center: Optional[Tuple[float, float]]
    total_capacity_kg_per_week: float

@dataclass
class CO2ClusteringResult:
    clusters: List[CO2Cluster]
    noise_points: List[Tuple[str, Tuple[float, float]]]
    total_clusters: int
    total_noise_points: int
    clustering_params: Dict

class CO2ClusteringOptimizer:
    """CO2捕获源聚类优化器"""

    def __init__(self, config: Dict, pipeline_distance_calculator=None):
        """
        初始化CO2聚类优化器

        Args:
            config: 配置字典
            pipeline_distance_calculator: 管道距离计算器（可选）
        """
        self.config = config
        self.clustering_params = config.get('co2_clustering_parameters', {})
        self.pipeline_calculator = pipeline_distance_calculator

        # CO2聚类参数（使用更大的eps因为CO2源分布更广）
        self.eps_km = self.clustering_params.get('eps_distance_km', 60.0)  # 60km
        self.min_samples = self.clustering_params.get('min_samples', 3)
        self.pipeline_weight = self.clustering_params.get('pipeline_weight', 0.3)
        self.enable_pipeline_opt = self.clustering_params.get('enable_pipeline_optimization', True)
        self.max_clusters = self.clustering_params.get('max_clusters', 200)  # CO2源更多，允许更多聚类

        # 🚀 性能优化：管道距离缓存
        self._pipeline_distance_cache = {}

        logger.info(f"初始化CO2聚类优化器: eps={self.eps_km}km, min_samples={self.min_samples}, max_clusters={self.max_clusters}")

    def _calculate_haversine_distance(self, lat1: float, lon1: float,
                                     lat2: float, lon2: float) -> float:
        """计算两点间的Haversine距离（公里）"""
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        return 6371 * c

    def _dbscan_cluster(self, coords_rad: np.ndarray, eps_rad: float, min_samples: int) -> np.ndarray:
        """
        手写DBSCAN聚类算法（基于Haversine距离）- 极速优化版本

        优化措施:
        1. Numba JIT并行计算距离矩阵（利用所有CPU核心，5-8倍加速）
        2. 移除分块逻辑，直接全量矩阵计算（内存充足模式）
        3. 使用set进行邻居管理（O(1)查找 vs O(n)查找）
        4. 详细性能监控日志

        Args:
            coords_rad: 坐标数组（弧度），shape (n, 2) - [lat_rad, lon_rad]
            eps_rad: 邻域半径（弧度）
            min_samples: 核心点最小邻居数

        Returns:
            labels: 聚类标签数组，-1表示噪声点
        """
        t_start = time.time()
        n_points = len(coords_rad)
        labels = np.full(n_points, -1, dtype=int)  # -1表示未访问
        cluster_id = 0

        logger.info(f"开始DBSCAN聚类: {n_points}个点, eps={eps_rad*6371:.1f}km, min_samples={min_samples}")

        # 🚀 极速优化：使用Numba JIT并行计算距离矩阵
        t_dist_start = time.time()

        if NUMBA_AVAILABLE:
            logger.info(f"使用Numba JIT并行计算（利用所有CPU核心）...")
            lats = coords_rad[:, 0].copy()  # 确保连续内存
            lons = coords_rad[:, 1].copy()
            adjacency_matrix = _compute_haversine_distances_numba(lats, lons, eps_rad)
        else:
            logger.info(f"使用NumPy向量化计算...")
            adjacency_matrix = _compute_haversine_distances_numpy(coords_rad, eps_rad)

        # 转换为邻接表（set格式）以加速后续查找
        adjacency_list = {i: set(np.where(adjacency_matrix[i])[0].tolist())
                         for i in range(n_points)}
        avg_neighbors = adjacency_matrix.sum(axis=1).mean()

        t_dist_end = time.time()
        logger.info(f"✓ 距离矩阵计算完成: 耗时{t_dist_end-t_dist_start:.2f}秒, 平均邻居数{avg_neighbors:.1f}")

        # 🚀 优化2：使用set代替list进行邻居管理
        def get_neighbors(point_idx: int) -> Set[int]:
            """从邻接表获取邻居（O(1)查询）"""
            return adjacency_list[point_idx]

        def expand_cluster(point_idx: int, neighbors: Set[int], cluster_id: int):
            """扩展聚类（广度优先搜索 + set优化）"""
            labels[point_idx] = cluster_id

            # 使用set避免重复访问，大幅提升性能
            to_process = list(neighbors)
            processed = {point_idx}

            i = 0
            while i < len(to_process):
                neighbor_idx = to_process[i]
                i += 1

                # 跳过已处理的点
                if neighbor_idx in processed:
                    continue
                processed.add(neighbor_idx)

                # 如果是未分配或噪声点，标记为当前聚类
                if labels[neighbor_idx] <= -1:
                    labels[neighbor_idx] = cluster_id

                    # 如果是核心点，添加其邻居
                    neighbor_neighbors = get_neighbors(neighbor_idx)
                    if len(neighbor_neighbors) >= min_samples:
                        # 使用set差集快速找到新邻居
                        new_neighbors = neighbor_neighbors - processed
                        to_process.extend(new_neighbors)

        # 主循环：遍历所有点
        t_cluster_start = time.time()
        for point_idx in range(n_points):
            if point_idx % 100 == 0 and point_idx > 0:
                logger.debug(f"  聚类进度: {point_idx}/{n_points}")

            # 跳过已处理的点
            if labels[point_idx] >= 0:
                continue

            # 获取邻居
            neighbors = get_neighbors(point_idx)

            # 如果不是核心点，标记为噪声（-1）
            if len(neighbors) < min_samples:
                labels[point_idx] = -1
                continue

            # 是核心点，创建新聚类
            expand_cluster(point_idx, neighbors, cluster_id)
            cluster_id += 1

        t_cluster_end = time.time()
        t_total = time.time() - t_start

        logger.info(f"✓ DBSCAN聚类完成: 发现{cluster_id}个聚类")
        logger.info(f"  - 距离计算: {t_dist_end-t_dist_start:.2f}秒 ({(t_dist_end-t_dist_start)/t_total*100:.1f}%)")
        logger.info(f"  - 聚类扩展: {t_cluster_end-t_cluster_start:.2f}秒 ({(t_cluster_end-t_cluster_start)/t_total*100:.1f}%)")
        logger.info(f"  - 总耗时: {t_total:.2f}秒")

        return labels

    def cluster_co2_sources(self, co2_sources: Dict,
                           destination_coords: Optional[Tuple[float, float]] = None) -> CO2ClusteringResult:
        """
        对CO2捕获源进行聚类

        Args:
            co2_sources: CO2捕获源字典 {source_id: {latitude, longitude, capacity_ton_per_week}}
            destination_coords: 目标位置坐标（用于优化聚类中心）

        Returns:
            CO2ClusteringResult: 聚类结果
        """
        t_total_start = time.time()

        if not self.clustering_params.get('enable_clustering', False):
            logger.info("CO2聚类功能未启用，跳过聚类")
            noise_points = [(loc, (coords['latitude'], coords['longitude']))
                           for loc, coords in co2_sources.items()]
            return CO2ClusteringResult(
                clusters=[],
                noise_points=noise_points,
                total_clusters=0,
                total_noise_points=len(noise_points),
                clustering_params=self.clustering_params
            )

        logger.info(f"=" * 60)
        logger.info(f"开始CO2捕获源聚类分析: {len(co2_sources)}个CO2源")
        logger.info(f"=" * 60)

        # 🚀 阶段1：数据准备
        t_prep_start = time.time()
        location_names = list(co2_sources.keys())
        coords = np.array([(co2_sources[loc]['latitude'],
                           co2_sources[loc]['longitude'])
                          for loc in location_names])
        coords_rad = np.radians(coords)
        t_prep_end = time.time()
        logger.info(f"✓ 数据准备完成: {t_prep_end-t_prep_start:.2f}秒")

        # 🚀 阶段2：DBSCAN聚类（含距离矩阵计算）
        eps_rad = self.eps_km / 6371.0  # 转换为弧度
        labels = self._dbscan_cluster(coords_rad, eps_rad, self.min_samples)

        unique_labels = set(labels)
        n_clusters = len(unique_labels) - (1 if -1 in unique_labels else 0)
        n_noise = list(labels).count(-1)

        logger.info(f"✓ 聚类结果: {n_clusters}个聚类, {n_noise}个噪声点")

        # 🚀 阶段3：聚类后处理
        t_postproc_start = time.time()
        clusters = []
        noise_points = []

        # 处理每个聚类
        for label in unique_labels:
            if label == -1:
                # 噪声点
                noise_indices = np.where(labels == -1)[0]
                for idx in noise_indices:
                    noise_points.append((
                        location_names[idx],
                        (coords[idx][0], coords[idx][1])
                    ))
                continue

            # 聚类成员
            cluster_indices = np.where(labels == label)[0]
            cluster_members = [location_names[i] for i in cluster_indices]
            cluster_coords = [tuple(coords[i]) for i in cluster_indices]

            # 计算地理中心
            geo_center = self._calculate_geographic_center(cluster_coords)

            # 管道优化（如果启用）
            if self.enable_pipeline_opt and self.pipeline_calculator and destination_coords:
                optimized_center = self._optimize_cluster_center(
                    cluster_coords, geo_center, destination_coords
                )
            else:
                optimized_center = geo_center

            # 计算总产能
            total_capacity = sum(
                co2_sources[loc].get('co2_capture_capacity_ton_per_week', 0)
                for loc in cluster_members
            )

            cluster = CO2Cluster(
                cluster_id=int(label),
                member_locations=cluster_members,
                member_coords=cluster_coords,
                center_coord=optimized_center,
                geo_center=geo_center,
                pipeline_optimized_center=optimized_center if self.enable_pipeline_opt else None,
                total_capacity_kg_per_week=total_capacity * 1000  # 转换为kg
            )
            clusters.append(cluster)

        t_postproc_end = time.time()
        logger.info(f"✓ 后处理完成: {t_postproc_end-t_postproc_start:.2f}秒")

        # 管道优化缓存统计
        if self._pipeline_distance_cache:
            cache_size = len(self._pipeline_distance_cache)
            logger.info(f"  - 管道距离缓存: {cache_size}个坐标点")

        # 限制聚类数量
        if len(clusters) > self.max_clusters:
            logger.warning(f"CO2聚类数量({len(clusters)})超过限制({self.max_clusters})，保留最大的{self.max_clusters}个")
            clusters.sort(key=lambda c: c.total_capacity_kg_per_week, reverse=True)
            excess_clusters = clusters[self.max_clusters:]
            clusters = clusters[:self.max_clusters]

            # 将超出的聚类降级为噪声点
            for cluster in excess_clusters:
                for loc, coord in zip(cluster.member_locations, cluster.member_coords):
                    noise_points.append((loc, coord))

        result = CO2ClusteringResult(
            clusters=clusters,
            noise_points=noise_points,
            total_clusters=len(clusters),
            total_noise_points=len(noise_points),
            clustering_params=self.clustering_params
        )

        t_total_end = time.time()
        logger.info(f"=" * 60)
        logger.info(f"✓ CO2聚类全流程完成!")
        logger.info(f"  - 总耗时: {t_total_end-t_total_start:.2f}秒")
        logger.info(f"  - 最终聚类: {result.total_clusters}个, 独立点: {result.total_noise_points}个")
        logger.info(f"=" * 60)

        # 导出结果
        if self.clustering_params.get('export_clustering_results', False):
            self._export_results(result)

        return result

    def _calculate_geographic_center(self, coords: List[Tuple[float, float]]) -> Tuple[float, float]:
        """计算地理中心点（球面几何）"""
        if not coords:
            return (0.0, 0.0)

        x = y = z = 0
        for lat, lon in coords:
            lat_rad = radians(lat)
            lon_rad = radians(lon)
            x += cos(lat_rad) * cos(lon_rad)
            y += cos(lat_rad) * sin(lon_rad)
            z += sin(lat_rad)

        total = len(coords)
        x /= total
        y /= total
        z /= total

        lon_center = atan2(y, x)
        hyp = sqrt(x * x + y * y)
        lat_center = atan2(z, hyp)

        return (np.degrees(lat_center), np.degrees(lon_center))

    def _optimize_cluster_center(self, cluster_coords: List[Tuple[float, float]],
                                 geo_center: Tuple[float, float],
                                 destination: Tuple[float, float]) -> Tuple[float, float]:
        """
        优化聚类中心位置（考虑管道接入点）- 极速优化版

        优化措施：
        1. 使用缓存避免重复计算管道距离
        2. 减少候选点数量（地理中心 + 最多3个代表点）
        3. 跳过管道距离相近的点

        Args:
            cluster_coords: 聚类成员坐标
            geo_center: 地理中心
            destination: 目标位置

        Returns:
            优化后的中心坐标
        """
        if not self.pipeline_calculator:
            return geo_center

        try:
            # 🚀 性能优化：使用缓存避免重复计算管道距离
            def get_pipeline_distance_cached(lat: float, lon: float) -> float:
                """带缓存的管道距离查询（精度到0.01度）"""
                cache_key = (round(lat, 2), round(lon, 2))
                if cache_key not in self._pipeline_distance_cache:
                    _, pipeline_dist = self.pipeline_calculator._find_nearest_pipeline_point(
                        lat, lon, 'natural_gas', float('inf')
                    )
                    self._pipeline_distance_cache[cache_key] = pipeline_dist
                return self._pipeline_distance_cache[cache_key]

            # 🚀 极速优化：限制候选点数量
            # 候选点策略：地理中心 + 算术平均中心 + 最多3个成员点（均匀采样）
            sample_points = [geo_center]

            # 添加算术平均中心
            if len(cluster_coords) > 1:
                avg_lat = sum(p[0] for p in cluster_coords) / len(cluster_coords)
                avg_lon = sum(p[1] for p in cluster_coords) / len(cluster_coords)
                sample_points.append((avg_lat, avg_lon))

            # 只采样最多3个代表点（而不是所有成员点）
            if len(cluster_coords) <= 3:
                sample_points.extend(cluster_coords)
            else:
                # 均匀采样：第1个、中间、最后1个
                indices = [0, len(cluster_coords) // 2, len(cluster_coords) - 1]
                sample_points.extend([cluster_coords[i] for i in indices])

            best_point = geo_center
            best_score = float('inf')

            # 评估每个候选点
            for point in sample_points:
                pipeline_dist = get_pipeline_distance_cached(point[0], point[1])

                # 到成员点的总距离
                member_dist_sum = sum(
                    self._calculate_haversine_distance(point[0], point[1], c[0], c[1])
                    for c in cluster_coords
                )

                # 综合评分：成员距离 + 管道距离
                score = (1 - self.pipeline_weight) * member_dist_sum + \
                       self.pipeline_weight * pipeline_dist * len(cluster_coords)

                if score < best_score:
                    best_score = score
                    best_point = point

            logger.debug(f"CO2聚类中心优化: 地理中心{geo_center} -> 优化中心{best_point}")
            return best_point

        except Exception as e:
            logger.warning(f"CO2聚类中心优化失败: {e}，使用地理中心")
            return geo_center

    def _export_results(self, result: CO2ClusteringResult):
        """导出聚类结果到JSON文件"""
        output_path = self.clustering_params.get('clustering_output_path', 'co2_clustering_results.json')

        # 如果是相对路径，则保存到dac_hydrogen_saf_supply_chain_optimization目录
        # 确保可视化代码能找到文件
        output_file = Path(output_path)
        if not output_file.is_absolute():
            # 获取当前文件所在目录（src/hydrogen/）
            current_dir = Path(__file__).parent
            # 向上两级到dac_hydrogen_saf_supply_chain_optimization目录
            project_root = current_dir.parent.parent
            output_file = project_root / output_path

        export_data = {
            'total_clusters': result.total_clusters,
            'total_noise_points': result.total_noise_points,
            'clustering_params': result.clustering_params,
            'clusters': [
                {
                    'cluster_id': c.cluster_id,
                    'member_locations': c.member_locations,
                    'member_coords': c.member_coords,
                    'center_coord': c.center_coord,
                    'geo_center': c.geo_center,
                    'total_capacity_ton_per_week': c.total_capacity_kg_per_week / 1000,  # 转回吨
                    'member_count': len(c.member_locations)  # 添加成员数量
                }
                for c in result.clusters
            ],
            'noise_points': [
                {'location': loc, 'coords': coords}
                for loc, coords in result.noise_points
            ]
        }

        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

        logger.info(f"CO2聚类结果已导出到: {output_file.absolute()}")
