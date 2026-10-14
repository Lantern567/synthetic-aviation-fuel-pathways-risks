"""
氢气生产厂聚类优化器
基于DBSCAN算法对可再生能源发电厂进行地理聚类
优化聚类中心点位置以最小化管道运输成本
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from sklearn.cluster import DBSCAN
from math import radians, sin, cos, sqrt, atan2
import logging
import json
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class HydrogenCluster:
    cluster_id: int
    member_locations: List[str]
    member_coords: List[Tuple[float, float]]
    center_coord: Tuple[float, float]
    geo_center: Tuple[float, float]
    pipeline_optimized_center: Optional[Tuple[float, float]]
    total_capacity_kg_per_hour: float

@dataclass
class ClusteringResult:
    clusters: List[HydrogenCluster]
    noise_points: List[Tuple[str, Tuple[float, float]]]
    total_clusters: int
    total_noise_points: int
    clustering_params: Dict

class HydrogenClusteringOptimizer:

    def __init__(self, config: Dict, pipeline_distance_calculator=None):
        self.config = config
        self.clustering_params = config.get('clustering_parameters', {})
        self.pipeline_calculator = pipeline_distance_calculator

        self.eps_km = self.clustering_params.get('eps_distance_km', 40.0)
        self.min_samples = self.clustering_params.get('min_samples', 2)
        self.pipeline_weight = self.clustering_params.get('pipeline_weight', 0.3)
        self.enable_pipeline_opt = self.clustering_params.get('enable_pipeline_optimization', True)
        self.max_clusters = self.clustering_params.get('max_clusters', 50)

        logger.info(f"初始化氢气聚类优化器: eps={self.eps_km}km, min_samples={self.min_samples}")

    def _calculate_haversine_distance(self, lat1: float, lon1: float,
                                     lat2: float, lon2: float) -> float:
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        return 6371 * c

    def cluster_hydrogen_plants(self, hydrogen_locations: Dict,
                                destination_coords: Optional[Tuple[float, float]] = None,
                                source_type: str = 'auto') -> ClusteringResult:
        """
        对氢气生产厂进行地理聚类

        Args:
            hydrogen_locations: 氢气生产位置字典 {location_id: {latitude, longitude, capacity_kg_per_hour}}
            destination_coords: 目标位置坐标 (lat, lon)，用于优化聚类中心
            source_type: 氢源类型 ('auto': 自动检测, 'renewable': 可再生能源, 'byproduct': 副产氢)
                        注意：当前版本通过位置名称自动检测副产氢，此参数暂时保留用于向后兼容

        Returns:
            ClusteringResult: 聚类结果
        """
        if not self.clustering_params.get('enable_clustering', False):
            logger.info("聚类功能未启用，跳过聚类")
            noise_points = [(loc, (coords['latitude'], coords['longitude']))
                           for loc, coords in hydrogen_locations.items()]
            return ClusteringResult(
                clusters=[],
                noise_points=noise_points,
                total_clusters=0,
                total_noise_points=len(noise_points),
                clustering_params=self.clustering_params
            )

        logger.info(f"开始对{len(hydrogen_locations)}个氢气生产厂进行聚类...")

        location_names = list(hydrogen_locations.keys())
        coords = np.array([(hydrogen_locations[loc]['latitude'],
                           hydrogen_locations[loc]['longitude'])
                          for loc in location_names])

        coords_rad = np.radians(coords)

        dbscan = DBSCAN(
            eps=self.eps_km / 6371.0,
            min_samples=self.min_samples,
            metric='haversine'
        )
        labels = dbscan.fit_predict(coords_rad)

        unique_labels = set(labels)
        n_clusters = len(unique_labels) - (1 if -1 in unique_labels else 0)
        n_noise = list(labels).count(-1)

        logger.info(f"聚类完成: {n_clusters}个聚类, {n_noise}个噪声点")

        clusters = []
        noise_points = []

        for label in unique_labels:
            if label == -1:
                noise_indices = np.where(labels == -1)[0]
                for idx in noise_indices:
                    noise_points.append((
                        location_names[idx],
                        (coords[idx][0], coords[idx][1])
                    ))
                continue

            cluster_indices = np.where(labels == label)[0]
            cluster_members = [location_names[i] for i in cluster_indices]
            cluster_coords = [tuple(coords[i]) for i in cluster_indices]

            geo_center = self._calculate_geographic_center(cluster_coords)

            if self.enable_pipeline_opt and self.pipeline_calculator and destination_coords:
                optimized_center = self._optimize_cluster_center(
                    cluster_coords, geo_center, destination_coords
                )
            else:
                optimized_center = geo_center

            total_capacity = sum(
                hydrogen_locations[loc].get('capacity_kg_per_hour', 0)
                for loc in cluster_members
            )

            cluster = HydrogenCluster(
                cluster_id=int(label),
                member_locations=cluster_members,
                member_coords=cluster_coords,
                center_coord=optimized_center,
                geo_center=geo_center,
                pipeline_optimized_center=optimized_center if self.enable_pipeline_opt else None,
                total_capacity_kg_per_hour=total_capacity
            )
            clusters.append(cluster)

        if len(clusters) > self.max_clusters:
            logger.warning(f"聚类数量({len(clusters)})超过限制({self.max_clusters})，保留最大的{self.max_clusters}个")
            clusters.sort(key=lambda c: c.total_capacity_kg_per_hour, reverse=True)
            excess_clusters = clusters[self.max_clusters:]
            clusters = clusters[:self.max_clusters]

            for cluster in excess_clusters:
                for loc, coord in zip(cluster.member_locations, cluster.member_coords):
                    noise_points.append((loc, coord))

        result = ClusteringResult(
            clusters=clusters,
            noise_points=noise_points,
            total_clusters=len(clusters),
            total_noise_points=len(noise_points),
            clustering_params=self.clustering_params
        )

        logger.info(f"最终聚类结果: {result.total_clusters}个聚类, {result.total_noise_points}个独立点")

        if self.clustering_params.get('export_clustering_results', False):
            self._export_results(result)

        return result

    def _calculate_geographic_center(self, coords: List[Tuple[float, float]]) -> Tuple[float, float]:
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
        if not self.pipeline_calculator:
            return geo_center

        try:
            _, geo_pipeline_dist = self.pipeline_calculator._find_nearest_pipeline_point(
                geo_center[0], geo_center[1], 'natural_gas', float('inf')
            )

            sample_points = []
            for lat, lon in cluster_coords:
                sample_points.append((lat, lon))

            if len(sample_points) > 1:
                avg_lat = sum(p[0] for p in sample_points) / len(sample_points)
                avg_lon = sum(p[1] for p in sample_points) / len(sample_points)
                sample_points.append((avg_lat, avg_lon))

            best_point = geo_center
            best_score = float('inf')

            for point in sample_points:
                _, pipeline_dist = self.pipeline_calculator._find_nearest_pipeline_point(
                    point[0], point[1], 'natural_gas', float('inf')
                )

                member_dist_sum = sum(
                    self._calculate_haversine_distance(point[0], point[1], c[0], c[1])
                    for c in cluster_coords
                )

                score = (1 - self.pipeline_weight) * member_dist_sum + \
                       self.pipeline_weight * pipeline_dist * len(cluster_coords)

                if score < best_score:
                    best_score = score
                    best_point = point

            logger.debug(f"聚类中心优化: 地理中心{geo_center} -> 优化中心{best_point}")
            return best_point

        except Exception as e:
            logger.warning(f"聚类中心优化失败: {e}，使用地理中心")
            return geo_center

    def _export_results(self, result: ClusteringResult):
        output_path = self.clustering_params.get('clustering_output_path', 'clustering_results.json')

        # 检测是否为副产品氢数据（根据成员位置名称判断）
        is_byproduct = False
        if result.clusters:
            # 检查第一个聚类的成员位置
            for cluster in result.clusters:
                for loc in cluster.member_locations:
                    loc_lower = loc.lower()
                    # 如果包含副产品氢标识（steel_、refinery_、byproduct）
                    if (loc.startswith('steel_') or loc.startswith('refinery_') or
                        'byproduct' in loc_lower):
                        is_byproduct = True
                        break
                if is_byproduct:
                    break

        # 根据数据类型修改输出文件名
        output_file = Path(output_path)
        if is_byproduct:
            # 副产品氢：添加byproduct_前缀
            # clustering_results.json -> byproduct_clustering_results.json
            stem = output_file.stem  # clustering_results
            suffix = output_file.suffix  # .json
            new_filename = f"byproduct_{stem}{suffix}"
            output_file = output_file.parent / new_filename

        # 如果是相对路径，则保存到dac_hydrogen_saf_supply_chain_optimization目录
        # 确保可视化代码能找到文件
        if not output_file.is_absolute():
            # 获取当前文件所在目录（src/hydrogen/）
            current_dir = Path(__file__).parent
            # 向上两级到dac_hydrogen_saf_supply_chain_optimization目录
            project_root = current_dir.parent.parent
            output_file = project_root / output_file

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
                    'total_capacity_kg_per_hour': c.total_capacity_kg_per_hour
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

        logger.info(f"聚类结果已导出到: {output_file.absolute()}")