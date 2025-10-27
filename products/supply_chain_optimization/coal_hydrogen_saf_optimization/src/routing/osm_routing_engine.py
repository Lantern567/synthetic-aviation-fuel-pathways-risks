"""
OSM路径规划引擎
使用OSMnx库获取真实公路路网数据并计算最短路径和实际距离
"""

import osmnx as ox
import networkx as nx
import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Tuple, Optional, Union
import pickle
import os
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OSMRoutingEngine:
    """
    基于OSM数据的路径规划引擎
    
    功能:
    1. 下载并缓存指定区域的路网数据
    2. 计算两点间的最短路径
    3. 计算真实道路距离和预估行驶时间
    4. 支持多种运输方式(汽车、卡车等)
    """
    
    def __init__(self, cache_dir: str = "cache/osm_networks", network_type: str = "drive"):
        """
        初始化OSM路径规划引擎
        
        Args:
            cache_dir: 路网数据缓存目录
            network_type: 网络类型 ('drive', 'drive_service', 'all', 'bike', 'walk')
        """
        self.cache_dir = cache_dir
        self.network_type = network_type
        self.networks = {}  # 存储已加载的路网图
        self.network_bounds = {}  # 存储路网边界信息
        
        # 创建缓存目录
        os.makedirs(cache_dir, exist_ok=True)
        
        # 配置OSMnx设置
        ox.settings.use_cache = True
        ox.settings.cache_folder = cache_dir
        ox.settings.log_console = False  # 减少日志输出
        
        logger.info(f"OSM路径规划引擎初始化完成，网络类型: {network_type}")
    
    def load_network_for_region(self, region_name: str, buffer_km: float = 10) -> str:
        """
        为指定区域加载路网数据
        
        Args:
            region_name: 区域名称 (如 "Beijing, China", "Shanghai, China")
            buffer_km: 缓冲区域大小(公里)
            
        Returns:
            network_id: 网络标识符
        """
        network_id = f"{region_name}_{self.network_type}_{buffer_km}km"
        cache_file = os.path.join(self.cache_dir, f"{network_id.replace(' ', '_').replace(',', '')}.pkl")
        
        if network_id in self.networks:
            logger.info(f"网络 {network_id} 已存在于内存中")
            return network_id
            
        # 尝试从缓存加载
        if os.path.exists(cache_file):
            try:
                logger.info(f"从缓存加载网络: {cache_file}")
                with open(cache_file, 'rb') as f:
                    network_data = pickle.load(f)
                    self.networks[network_id] = network_data['graph']
                    self.network_bounds[network_id] = network_data['bounds']
                logger.info(f"成功从缓存加载网络 {network_id}")
                return network_id
            except Exception as e:
                logger.warning(f"缓存加载失败: {e}，将重新下载")
        
        # 从OSM下载网络数据
        try:
            logger.info(f"==== 开始下载OSM网络数据 ====")
            logger.info(f"目标区域: {region_name}")
            logger.info(f"缓冲区域: {buffer_km} km")
            logger.info(f"网络类型: {self.network_type}")
            logger.info("此过程可能需要几分钟到几十分钟，请耐心等待...")
            
            import time
            start_time = time.time()
            
            # 第1步：下载指定区域的路网（兼容不同版本的OSMnx）
            logger.info("步骤 1/4: 正在查询区域边界...")
            try:
                # 尝试使用buffer_dist参数（新版本）
                logger.info("尝试使用新版OSMnx API参数...")
                G = ox.graph_from_place(
                    region_name, 
                    network_type=self.network_type,
                    buffer_dist=buffer_km * 1000  # 转换为米
                )
                logger.info("成功使用新版API下载网络数据")
            except TypeError as e:
                if "buffer_dist" in str(e):
                    # 回退到不使用buffer_dist参数（旧版本）
                    logger.info("新版API不支持，使用兼容的OSMnx API参数...")
                    G = ox.graph_from_place(
                        region_name, 
                        network_type=self.network_type
                    )
                    logger.info("成功使用兼容API下载网络数据")
                else:
                    raise e
            
            download_time = time.time() - start_time
            logger.info(f"步骤 1/4 完成 - 网络下载耗时: {download_time:.1f}秒")
            logger.info(f"原始网络: {G.number_of_nodes()}个节点, {G.number_of_edges()}条边")
            
            # 第2步：添加边长度信息
            logger.info("步骤 2/4: 正在计算道路长度...")
            process_start = time.time()
            G = ox.add_edge_speeds(G)
            speed_time = time.time() - process_start
            logger.info(f"步骤 2/4 完成 - 速度计算耗时: {speed_time:.1f}秒")
            
            # 第3步：添加行驶时间信息
            logger.info("步骤 3/4: 正在计算行驶时间...")
            process_start = time.time()
            G = ox.add_edge_travel_times(G)
            time_calc_time = time.time() - process_start
            logger.info(f"步骤 3/4 完成 - 时间计算耗时: {time_calc_time:.1f}秒")
            
            # 第4步：计算网络边界和保存
            logger.info("步骤 4/4: 正在计算网络边界和保存数据...")
            process_start = time.time()
            
            gdf_nodes = ox.graph_to_gdfs(G, edges=False)
            bounds = {
                'north': gdf_nodes.geometry.y.max(),
                'south': gdf_nodes.geometry.y.min(),
                'east': gdf_nodes.geometry.x.max(),
                'west': gdf_nodes.geometry.x.min()
            }
            
            # 存储到内存
            self.networks[network_id] = G
            self.network_bounds[network_id] = bounds
            logger.info("网络数据已存储到内存")
            
            # 缓存到文件
            try:
                logger.info("正在保存网络数据到磁盘缓存...")
                network_data = {
                    'graph': G,
                    'bounds': bounds,
                    'created_at': datetime.now(),
                    'region_name': region_name,
                    'network_type': self.network_type,
                    'buffer_km': buffer_km
                }
                
                # 估算文件大小
                import sys
                estimated_size_mb = sys.getsizeof(str(G)) / (1024 * 1024)
                logger.info(f"预计缓存文件大小: {estimated_size_mb:.1f} MB")
                
                with open(cache_file, 'wb') as f:
                    pickle.dump(network_data, f)
                
                # 检查实际文件大小
                actual_size_mb = os.path.getsize(cache_file) / (1024 * 1024)
                logger.info(f"实际缓存文件大小: {actual_size_mb:.1f} MB")
                logger.info(f"网络数据已缓存到: {cache_file}")
            except Exception as e:
                logger.warning(f"缓存保存失败: {e}")
            
            save_time = time.time() - process_start
            total_time = time.time() - start_time
            
            logger.info(f"步骤 4/4 完成 - 保存耗时: {save_time:.1f}秒")
            logger.info(f"==== OSM网络数据下载完成 ====")
            logger.info(f"总耗时: {total_time:.1f}秒 ({total_time/60:.1f}分钟)")
            logger.info(f"最终网络规模: {G.number_of_nodes()}个节点, {G.number_of_edges()}条边")
            logger.info(f"网络边界: 北{bounds['north']:.4f}° 南{bounds['south']:.4f}° 东{bounds['east']:.4f}° 西{bounds['west']:.4f}°")
            
            return network_id
            
        except Exception as e:
            logger.error(f"加载网络失败: {e}")
            raise
    
    def load_network_for_coordinates(self, lat: float, lon: float, radius_km: float = 50) -> str:
        """
        为指定坐标点周围区域加载路网数据
        
        Args:
            lat: 纬度
            lon: 经度
            radius_km: 半径(公里)
            
        Returns:
            network_id: 网络标识符
        """
        network_id = f"coord_{lat:.4f}_{lon:.4f}_{radius_km}km_{self.network_type}"
        cache_file = os.path.join(self.cache_dir, f"{network_id}.pkl")
        
        if network_id in self.networks:
            logger.info(f"网络 {network_id} 已存在于内存中")
            return network_id
            
        # 尝试从缓存加载
        if os.path.exists(cache_file):
            try:
                logger.info(f"从缓存加载网络: {cache_file}")
                with open(cache_file, 'rb') as f:
                    network_data = pickle.load(f)
                    self.networks[network_id] = network_data['graph']
                    self.network_bounds[network_id] = network_data['bounds']
                logger.info(f"成功从缓存加载网络 {network_id}")
                return network_id
            except Exception as e:
                logger.warning(f"缓存加载失败: {e}，将重新下载")
        
        # 从OSM下载网络数据
        try:
            logger.info(f"==== 开始下载坐标点周围的OSM网络数据 ====")
            logger.info(f"中心坐标: ({lat:.4f}, {lon:.4f})")
            logger.info(f"下载半径: {radius_km:.1f} km")
            logger.info(f"网络类型: {self.network_type}")
            logger.info("此过程可能需要几分钟到几十分钟，请耐心等待...")
            
            import time
            start_time = time.time()
            
            # 第1步：下载指定坐标周围的路网
            logger.info("步骤 1/4: 正在查询和下载路网数据...")
            logger.info(f"预计下载区域面积: {3.14159 * radius_km * radius_km:.1f} 平方公里")
            
            G = ox.graph_from_point(
                (lat, lon),
                dist=radius_km * 1000,  # 转换为米
                network_type=self.network_type
            )
            
            download_time = time.time() - start_time
            logger.info(f"步骤 1/4 完成 - 网络下载耗时: {download_time:.1f}秒")
            logger.info(f"原始网络: {G.number_of_nodes()}个节点, {G.number_of_edges()}条边")
            
            # 第2步：添加边长度信息
            logger.info("步骤 2/4: 正在计算道路长度...")
            process_start = time.time()
            G = ox.add_edge_speeds(G)
            speed_time = time.time() - process_start
            logger.info(f"步骤 2/4 完成 - 速度计算耗时: {speed_time:.1f}秒")
            
            # 第3步：添加行驶时间信息
            logger.info("步骤 3/4: 正在计算行驶时间...")
            process_start = time.time()
            G = ox.add_edge_travel_times(G)
            time_calc_time = time.time() - process_start
            logger.info(f"步骤 3/4 完成 - 时间计算耗时: {time_calc_time:.1f}秒")
            
            # 第4步：计算网络边界和保存
            logger.info("步骤 4/4: 正在计算网络边界和保存数据...")
            process_start = time.time()
            
            gdf_nodes = ox.graph_to_gdfs(G, edges=False)
            bounds = {
                'north': gdf_nodes.geometry.y.max(),
                'south': gdf_nodes.geometry.y.min(),
                'east': gdf_nodes.geometry.x.max(),
                'west': gdf_nodes.geometry.x.min()
            }
            
            # 存储到内存
            self.networks[network_id] = G
            self.network_bounds[network_id] = bounds
            logger.info("网络数据已存储到内存")
            
            # 缓存到文件
            try:
                logger.info("正在保存网络数据到磁盘缓存...")
                network_data = {
                    'graph': G,
                    'bounds': bounds,
                    'created_at': datetime.now(),
                    'center_lat': lat,
                    'center_lon': lon,
                    'radius_km': radius_km,
                    'network_type': self.network_type
                }
                
                # 估算文件大小
                import sys
                estimated_size_mb = sys.getsizeof(str(G)) / (1024 * 1024)
                logger.info(f"预计缓存文件大小: {estimated_size_mb:.1f} MB")
                
                with open(cache_file, 'wb') as f:
                    pickle.dump(network_data, f)
                
                # 检查实际文件大小
                actual_size_mb = os.path.getsize(cache_file) / (1024 * 1024)
                logger.info(f"实际缓存文件大小: {actual_size_mb:.1f} MB")
                logger.info(f"网络数据已缓存到: {cache_file}")
            except Exception as e:
                logger.warning(f"缓存保存失败: {e}")
            
            save_time = time.time() - process_start
            total_time = time.time() - start_time
            
            logger.info(f"步骤 4/4 完成 - 保存耗时: {save_time:.1f}秒")
            logger.info(f"==== OSM坐标点网络数据下载完成 ====")
            logger.info(f"总耗时: {total_time:.1f}秒 ({total_time/60:.1f}分钟)")
            logger.info(f"最终网络规模: {G.number_of_nodes()}个节点, {G.number_of_edges()}条边")
            logger.info(f"网络边界: 北{bounds['north']:.4f}° 南{bounds['south']:.4f}° 东{bounds['east']:.4f}° 西{bounds['west']:.4f}°")
            logger.info(f"覆盖区域: 中心({lat:.4f}, {lon:.4f}), 半径{radius_km}km")
            
            return network_id
            
        except Exception as e:
            logger.error(f"加载网络失败: {e}")
            raise
    
    def find_suitable_network(self, lat: float, lon: float) -> Optional[str]:
        """
        查找包含指定坐标点的已加载网络
        
        Args:
            lat: 纬度
            lon: 经度
            
        Returns:
            network_id: 合适的网络标识符，如果没有找到则返回None
        """
        for network_id, bounds in self.network_bounds.items():
            if (bounds['south'] <= lat <= bounds['north'] and 
                bounds['west'] <= lon <= bounds['east']):
                return network_id
        return None
    
    def calculate_route_distance(self, 
                               start_lat: float, start_lon: float,
                               end_lat: float, end_lon: float,
                               network_id: Optional[str] = None) -> Dict:
        """
        计算两点间的路径距离和行驶时间
        
        Args:
            start_lat: 起点纬度
            start_lon: 起点经度
            end_lat: 终点纬度
            end_lon: 终点经度
            network_id: 指定使用的网络，如果不指定则自动选择
            
        Returns:
            Dict包含distance_km, travel_time_hours, route_found等信息
        """
        # 如果没有指定网络，尝试找到合适的网络
        if network_id is None:
            # 先检查现有网络
            network_id = self.find_suitable_network(start_lat, start_lon)
            if network_id is None:
                network_id = self.find_suitable_network(end_lat, end_lon)
            
            # 如果都没有找到，尝试加载中国整体网络
            if network_id is None:
                try:
                    logger.info("加载中国整体路网数据...")
                    network_id = self.load_network_for_region("China", buffer_km=100)
                except Exception as e:
                    logger.warning(f"中国路网加载失败，尝试加载区域网络: {e}")
                    # 回退到区域网络
                    try:
                        center_lat = (start_lat + end_lat) / 2
                        center_lon = (start_lon + end_lon) / 2
                        straight_distance = ((start_lat - end_lat)**2 + (start_lon - end_lon)**2)**0.5 * 111
                        radius_km = max(straight_distance * 1.2 + 50, 100)  # 至少100km半径
                        
                        network_id = self.load_network_for_coordinates(center_lat, center_lon, radius_km)
                    except Exception as e2:
                        logger.error(f"区域网络加载也失败: {e2}，使用近似计算")
                        haversine_dist = self._calculate_haversine_distance(start_lat, start_lon, end_lat, end_lon)
                        return {
                            'distance_km': haversine_dist * 1.3,
                            'travel_time_hours': haversine_dist * 1.3 / 60,
                            'route_found': True,
                            'method': 'haversine_fallback',
                            'error': f"Network loading failed: {e2}"
                        }
        
        if network_id not in self.networks:
            logger.error(f"网络 {network_id} 不存在")
            return {
                'distance_km': None,
                'travel_time_hours': None,
                'route_found': False,
                'error': f'Network {network_id} not found'
            }
        
        G = self.networks[network_id]
        
        try:
            # 找到最近的路网节点
            start_node = ox.distance.nearest_nodes(G, start_lon, start_lat)
            end_node = ox.distance.nearest_nodes(G, end_lon, end_lat)
            
            if start_node == end_node:
                return {
                    'distance_km': 0.0,
                    'travel_time_hours': 0.0,
                    'route_found': True,
                    'network_id': network_id
                }
            
            # 计算最短路径（基于距离）
            try:
                route = nx.shortest_path(G, start_node, end_node, weight='length')
                
                # 计算路径总距离
                total_distance_m = 0
                total_time_s = 0
                
                for u, v in zip(route[:-1], route[1:]):
                    # 获取边数据（可能有多条平行边）
                    edge_data = G[u][v]
                    if isinstance(edge_data, dict):
                        # 单条边
                        total_distance_m += edge_data.get('length', 0)
                        total_time_s += edge_data.get('travel_time', 0)
                    else:
                        # 多条平行边，选择最短的
                        min_length = min(data.get('length', float('inf')) for data in edge_data.values())
                        min_time = min(data.get('travel_time', float('inf')) for data in edge_data.values() 
                                     if data.get('length', float('inf')) == min_length)
                        total_distance_m += min_length
                        total_time_s += min_time
                
                return {
                    'distance_km': total_distance_m / 1000,
                    'travel_time_hours': total_time_s / 3600,
                    'route_found': True,
                    'network_id': network_id,
                    'route_nodes': len(route)
                }
                
            except nx.NetworkXNoPath:
                logger.warning(f"在网络 {network_id} 中找不到从 ({start_lat}, {start_lon}) 到 ({end_lat}, {end_lon}) 的路径")
                return {
                    'distance_km': None,
                    'travel_time_hours': None,
                    'route_found': False,
                    'error': 'No path found',
                    'network_id': network_id
                }
                
        except Exception as e:
            logger.error(f"路径计算失败: {e}")
            return {
                'distance_km': None,
                'travel_time_hours': None,
                'route_found': False,
                'error': str(e),
                'network_id': network_id
            }
    
    def calculate_distance_matrix(self, locations: List[Tuple[float, float]], 
                                location_names: Optional[List[str]] = None) -> pd.DataFrame:
        """
        计算位置点之间的距离矩阵
        
        Args:
            locations: 位置列表，每个位置为(lat, lon)元组
            location_names: 位置名称列表
            
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
                        locations[j][0], locations[j][1]
                    )
                    
                    if result['route_found']:
                        distance = result['distance_km']
                    else:
                        # 如果找不到路径，使用直线距离的1.3倍作为近似
                        lat1, lon1 = locations[i]
                        lat2, lon2 = locations[j]
                        straight_distance = ((lat1 - lat2)**2 + (lon1 - lon2)**2)**0.5 * 111
                        distance = straight_distance * 1.3
                        logger.warning(f"使用近似距离: {location_names[i]} -> {location_names[j]}: {distance:.2f}km")
                    
                    distance_matrix[i][j] = distance
                    distance_matrix[j][i] = distance  # 对称矩阵
        
        # 转换为DataFrame
        df = pd.DataFrame(distance_matrix, index=location_names, columns=location_names)
        return df
    
    def get_network_stats(self, network_id: str) -> Dict:
        """
        获取网络统计信息
        
        Args:
            network_id: 网络标识符
            
        Returns:
            网络统计信息字典
        """
        if network_id not in self.networks:
            return {}
        
        G = self.networks[network_id]
        bounds = self.network_bounds.get(network_id, {})
        
        # 计算基本统计信息
        stats = {
            'network_id': network_id,
            'nodes': G.number_of_nodes(),
            'edges': G.number_of_edges(),
            'network_type': self.network_type,
            'bounds': bounds
        }
        
        try:
            # 计算边长度统计
            edge_lengths = []
            for u, v, data in G.edges(data=True):
                if isinstance(data, dict):
                    edge_lengths.append(data.get('length', 0))
                else:
                    # 多条平行边的情况
                    for edge_data in data.values():
                        edge_lengths.append(edge_data.get('length', 0))
            
            if edge_lengths:
                stats.update({
                    'total_length_km': sum(edge_lengths) / 1000,
                    'avg_edge_length_m': np.mean(edge_lengths),
                    'median_edge_length_m': np.median(edge_lengths),
                    'max_edge_length_m': max(edge_lengths),
                    'min_edge_length_m': min(edge_lengths)
                })
        except Exception as e:
            logger.warning(f"计算边长度统计失败: {e}")
        
        return stats
    
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
    
    def clear_cache(self):
        """清理内存中的网络缓存"""
        self.networks.clear()
        self.network_bounds.clear()
        logger.info("已清理内存缓存")
    
    def list_cached_networks(self) -> List[str]:
        """列出所有缓存的网络文件"""
        cache_files = []
        if os.path.exists(self.cache_dir):
            for file in os.listdir(self.cache_dir):
                if file.endswith('.pkl'):
                    cache_files.append(file)
        return cache_files


class DistanceCalculator:
    """
    距离计算器 - 结合OSM路径规划和直线距离计算
    """
    
    def __init__(self, routing_engine: Optional[OSMRoutingEngine] = None):
        """
        初始化距离计算器
        
        Args:
            routing_engine: OSM路径规划引擎实例
        """
        self.routing_engine = routing_engine or OSMRoutingEngine()
    
    def calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float, 
                         method: str = "osm") -> float:
        """
        计算两点间距离
        
        Args:
            lat1, lon1: 起点纬度经度
            lat2, lon2: 终点纬度经度
            method: 计算方法 ("osm", "haversine", "euclidean")
            
        Returns:
            距离(公里)
        """
        if method == "osm":
            result = self.routing_engine.calculate_route_distance(lat1, lon1, lat2, lon2)
            if result['route_found']:
                return result['distance_km']
            else:
                # 回退到直线距离
                logger.warning("OSM路径计算失败，使用直线距离")
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
    
    def calculate_euclidean_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        计算两点间的欧几里得距离（近似）
        
        Args:
            lat1, lon1: 起点纬度经度
            lat2, lon2: 终点纬度经度
            
        Returns:
            距离(公里)
        """
        # 简单的欧几里得距离，1度约等于111公里
        distance = ((lat1 - lat2)**2 + (lon1 - lon2)**2)**0.5 * 111
        return distance