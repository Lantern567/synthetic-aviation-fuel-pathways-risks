"""
三模块聚类运输路线地图可视化（包含聚类和管道接入点）
Three Modules Clustered Transport Route Map Visualization (with clustering and pipeline access points)

基于聚类JSON文件和运输CSV文件生成完整的多层级运输可视化
Based on clustering JSON files and transport CSV files to generate comprehensive multi-layer transport visualization

功能 | Features:
1. 氢气聚类运输可视化 (H2 clustered transport visualization)
   - Layer1: 可再生能源站 → 聚类中心
   - Layer2: 聚类中心 → 管道接入点
   - Layer3: 管道网络 → 目的地
2. CO2聚类运输可视化 (CO2 clustered transport visualization)
3. SAF卡车运输可视化 (SAF truck transport visualization)
4. 管道网络底图 (Pipeline network basemap)
5. 三模块对比地图 (Three modules comparison maps)

作者 | Author: Claude Code
创建时间 | Created: 2025-11-06
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import logging

import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
from matplotlib import rcParams
from matplotlib.lines import Line2D
from math import radians, cos, sin, asin, sqrt

# 配置中文字体
matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS']
matplotlib.rcParams['axes.unicode_minus'] = False

# 添加frykit路径
sys.path.append(str(Path(__file__).parent.parent.parent.parent / "shared"))
import frykit.plot as fplt

# 添加GraphHopper路径
sys.path.append(str(Path(__file__).parent.parent / "coal_hydrogen_saf_optimization" / "src" / "routing"))
from graphhopper_routing_engine import GraphHopperRoutingEngine

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ThreeModulesClusteredMapVisualizer:
    """三模块聚类运输路线地图可视化器"""

    def __init__(self, output_dir: str = None):
        """
        初始化可视化器

        Args:
            output_dir: 输出目录，默认为 visualization/results
        """
        if output_dir is None:
            base_dir = Path(__file__).parent
            output_dir = base_dir / "results"

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 创建带时间戳的子目录
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = self.output_dir / f"clustered_transport_maps_{timestamp}"
        self.session_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"输出目录: {self.session_dir}")

        # 初始化GraphHopper路径规划引擎
        try:
            self.graphhopper = GraphHopperRoutingEngine(
                graphhopper_host="localhost",
                graphhopper_port=8989,
                enable_cache=True
            )
            logger.info("✓ GraphHopper路径规划引擎初始化成功")
        except Exception as e:
            logger.warning(f"GraphHopper初始化失败: {e}，将使用直线可视化")
            self.graphhopper = None

        # 模块配置
        self.modules = {
            'Coal Hydrogen': {
                'name_cn': '煤制氢',
                'color': '#E74C3C',
                'h2_clustering_file': '../coal_hydrogen_saf_optimization/clustering_results.json',
                'co2_clustering_file': '../coal_hydrogen_saf_optimization/co2_clustering_results.json',
                'transport_summary_file': '../coal_hydrogen_saf_optimization/results/transport_summary_20251106_113130.csv'
            },
            'DAC Hydrogen': {
                'name_cn': 'DAC制氢',
                'color': '#3498DB',
                'h2_clustering_file': '../dac_hydrogen_saf_supply_chain_optimization/clustering_results.json',
                'co2_clustering_file': None,  # DAC从空气中捕获CO2，无需CO2运输
                'transport_summary_file': '../dac_hydrogen_saf_supply_chain_optimization/results/two_step/transport_summary_20251106_015557.csv'
            },
            'Natural Gas': {
                'name_cn': '天然气',
                'color': '#2ECC71',
                'h2_clustering_file': '../natural_gas_supply_chain_optimization/clustering_results.json',
                'co2_clustering_file': None,  # 天然气制氢过程中CO2作为副产物，无独立运输
                'transport_summary_file': '../natural_gas_supply_chain_optimization/results/transport_summary_20251106_115306.csv'
            }
        }

        # 地图投影设置
        self.map_crs = fplt.CN_AZIMUTHAL_EQUIDISTANT
        self.data_crs = fplt.PLATE_CARREE

        # 运输类型颜色
        self.transport_colors = {
            'H2': '#1E90FF',          # 氢气 - 道奇蓝
            'H2_cluster': 'gray',     # 氢气聚类路径 - 灰色
            'CO2': '#8B4513',         # CO2 - 棕色
            'CO2_cluster': '#A0522D', # CO2聚类路径 - 赭色
            'SAF': '#FF4500'          # SAF - 橙红色
        }

        # 聚类颜色方案（用于区分不同聚类）
        self.cluster_colors = plt.cm.tab20.colors

        # 数据存储
        self.clustering_data = {}
        self.transport_data = {}

    def load_data(self):
        """加载三个模块的聚类数据和运输数据"""
        logger.info("=" * 60)
        logger.info("加载聚类和运输数据")
        logger.info("=" * 60)

        base_dir = Path(__file__).parent

        for module_name, config in self.modules.items():
            logger.info(f"\n正在加载: {module_name} ({config['name_cn']})")

            module_data = {
                'h2_clustering': None,
                'co2_clustering': None,
                'transport_summary': None
            }

            try:
                # 加载H2聚类数据
                h2_clustering_file = (base_dir / config['h2_clustering_file']).resolve()
                if h2_clustering_file.exists():
                    with open(h2_clustering_file, 'r', encoding='utf-8') as f:
                        module_data['h2_clustering'] = json.load(f)
                    logger.info(f"  ✓ H2聚类数据: {module_data['h2_clustering']['total_clusters']} 个聚类")
                else:
                    logger.warning(f"  ⚠ H2聚类文件不存在: {h2_clustering_file}")

                # 加载CO2聚类数据（如果有）
                if config['co2_clustering_file']:
                    co2_clustering_file = (base_dir / config['co2_clustering_file']).resolve()
                    if co2_clustering_file.exists():
                        with open(co2_clustering_file, 'r', encoding='utf-8') as f:
                            module_data['co2_clustering'] = json.load(f)
                        logger.info(f"  ✓ CO2聚类数据: {module_data['co2_clustering']['total_clusters']} 个聚类")
                    else:
                        logger.warning(f"  ⚠ CO2聚类文件不存在: {co2_clustering_file}")
                else:
                    logger.info(f"  - 无CO2聚类数据（不需要CO2运输）")

                # 加载运输汇总数据（包含H2、CO2、SAF所有运输信息）
                summary_file = (base_dir / config['transport_summary_file']).resolve()
                if summary_file.exists():
                    module_data['transport_summary'] = pd.read_csv(summary_file, encoding='utf-8')
                    logger.info(f"  ✓ 运输汇总数据: {len(module_data['transport_summary'])} 条")

                    # 按货物类型分组统计
                    if '货物类型' in module_data['transport_summary'].columns:
                        cargo_counts = module_data['transport_summary']['货物类型'].value_counts()
                        for cargo_type, count in cargo_counts.items():
                            logger.info(f"    - {cargo_type}: {count} 条")
                else:
                    logger.warning(f"  ⚠ 运输汇总文件不存在: {summary_file}")

                self.transport_data[module_name] = module_data

            except Exception as e:
                logger.error(f"  ✗ 加载失败: {e}")
                raise

        logger.info("\n" + "=" * 60)
        logger.info("数据加载完成")
        logger.info("=" * 60)

    def create_base_map(self, figsize=(18, 14), extent=None):
        """
        创建基础地图

        Args:
            figsize: 图片尺寸
            extent: 地图范围 [lon_min, lon_max, lat_min, lat_max]

        Returns:
            fig, ax: matplotlib figure和axes对象
        """
        fig = plt.figure(figsize=figsize)
        ax = fig.add_subplot(projection=self.map_crs)

        # 设置地图范围 - 京津冀及周边地区
        if extent is None:
            extent = [111, 121, 35, 43]

        min_lon, max_lon, min_lat, max_lat = extent

        # 设置刻度
        xticks = np.arange(min_lon, max_lon + 1, 2)
        yticks = np.arange(min_lat, max_lat + 1, 2)

        fplt.set_map_ticks(ax, (min_lon, max_lon, min_lat, max_lat), xticks, yticks)
        ax.gridlines(xlocs=xticks, ylocs=yticks, lw=0.5, ls="--", color="gray", alpha=0.5)

        # 设置刻度样式
        ax.tick_params(
            length=8, width=0.9, labelsize=10,
            top=True, right=True, labeltop=True, labelright=True
        )

        # 添加地图要素
        ax.set_facecolor("lightcyan")
        from cartopy.feature import LAND
        ax.add_feature(LAND, fc="floralwhite", ec="k", lw=0.5)

        # 使用frykit添加中国地图底图
        fplt.add_cn_city(ax, lw=0.3, edgecolor='lightgreen', linestyle='--', zorder=2)
        fplt.add_cn_line(ax, lw=1.2, edgecolor='dimgray', zorder=2.5)
        fplt.add_cn_border(ax, lw=0.75, edgecolor='black', zorder=3)

        return fig, ax

    def add_decorations(self, ax):
        """添加指北针和比例尺"""
        try:
            fplt.add_compass(ax, 0.92, 0.85, size=15, style="star")
            scale_bar = fplt.add_scale_bar(ax, 0.05, 0.95, length=200)
            scale_bar.set_xticks([0, 100, 200])
            scale_bar.xaxis.get_label().set_fontsize("small")
        except Exception as e:
            logger.warning(f"无法添加装饰元素: {e}")

    @staticmethod
    def haversine(lon1, lat1, lon2, lat2):
        """
        计算两点间的球面距离（Haversine公式）

        Args:
            lon1, lat1: 第一个点的经纬度
            lon2, lat2: 第二个点的经纬度

        Returns:
            距离（公里）
        """
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        r = 6371  # 地球半径，单位：公里
        return c * r

    def classify_energy_type(self, facility_name: str) -> str:
        """
        从设施名称识别能源类型

        Args:
            facility_name: 设施名称

        Returns:
            能源类型：'solar', 'wind', 'natural_gas', 'coal', 'airport', 'other'
        """
        name_lower = str(facility_name).lower()

        # 机场终端
        if 'airport' in name_lower or facility_name in ['天津', '北京']:
            return 'airport'

        # 光伏电站
        solar_keywords = ['solar', 'pv', '光伏', 'photovoltaic']
        if any(keyword in name_lower for keyword in solar_keywords):
            return 'solar'

        # 风电站
        wind_keywords = ['wind', '风能', '风电', '风力']
        if any(keyword in name_lower for keyword in wind_keywords):
            return 'wind'

        # 天然气
        gas_keywords = ['natural gas', 'ng_pipeline', '天然气', 'natural_gas']
        if any(keyword in name_lower for keyword in gas_keywords):
            return 'natural_gas'

        # 煤炭
        coal_keywords = ['coal', '煤炭', '煤制']
        if any(keyword in name_lower for keyword in coal_keywords):
            return 'coal'

        # 其他
        return 'other'

    def classify_co2_capture(self, module_name: str, roles: set) -> str:
        """
        判断CO2捕获方式

        Args:
            module_name: 模块名称
            roles: 设施的功能角色集合

        Returns:
            CO2捕获方式：'dac', 'industrial', 'none'
        """
        # 机场等终端设施无CO2捕获
        if '机场' in roles or roles == set():
            return 'none'

        # DAC模块
        if module_name == 'DAC Hydrogen':
            return 'dac'

        # 煤制氢和天然气模块 - 工业副产物
        if module_name in ['Coal Hydrogen', 'Natural Gas']:
            return 'industrial'

        return 'none'

    def get_visualization_attrs(self, energy_type: str, co2_capture: str, role_count: int) -> dict:
        """
        根据三维度分类获取可视化属性

        Args:
            energy_type: 能源类型
            co2_capture: CO2捕获方式
            role_count: 功能角色数量

        Returns:
            包含marker, color, size, linewidth的字典
        """
        # 形状编码（能源类型）
        marker_map = {
            'solar': '*',      # 光伏 - 星形
            'wind': '^',       # 风能 - 三角形
            'natural_gas': 'D',# 天然气 - 菱形
            'coal': 's',       # 煤炭 - 方形
            'airport': 'o',    # 机场 - 圆形
            'other': 'h'       # 其他 - 六边形
        }

        # 颜色编码（CO2捕获方式）
        color_map = {
            'dac': '#1E90FF',        # DAC - 道奇蓝
            'industrial': '#DC143C',  # 工业副产物 - 猩红色
            'none': '#696969'         # 无捕获 - 暗灰色
        }

        # 大小编码（功能角色数量）
        size_map = {
            4: 150,  # 四重角色
            3: 120,  # 三重角色
            2: 90,   # 双重角色
            1: 60    # 单一角色
        }

        # 边框宽度编码（功能复杂度）
        linewidth_map = {
            4: 2.5,  # 四重角色
            3: 2.0,  # 三重角色
            2: 1.5,  # 双重角色
            1: 1.0   # 单一角色
        }

        return {
            'marker': marker_map.get(energy_type, 'o'),
            'color': color_map.get(co2_capture, '#808080'),
            'size': size_map.get(role_count, 60),
            'linewidth': linewidth_map.get(role_count, 1.0)
        }

    def plot_h2_clustered_routes(self, ax, h2_clustering, transport_summary, module_name):
        """
        绘制氢气聚类运输路线（三层结构）

        Args:
            ax: matplotlib axes对象
            h2_clustering: H2聚类JSON数据
            transport_summary: 运输汇总DataFrame（包含Layer信息）
            module_name: 模块名称
        """
        if h2_clustering is None or transport_summary is None:
            return

        logger.info(f"  绘制H2聚类路线...")

        # 筛选出氢气运输数据
        h2_data = transport_summary[transport_summary['货物类型'] == '氢气'].copy()
        logger.info(f"    氢气运输数据: {len(h2_data)} 条")

        # 筛选聚类数据（有聚类信息的行）
        h2_cluster_data = h2_data[h2_data['聚类信息'].notna() & (h2_data['聚类信息'] != '')].copy()
        logger.info(f"    聚类运输数据: {len(h2_cluster_data)} 条")

        clusters = h2_clustering.get('clusters', [])
        cluster_centers = {}

        # 提取所有聚类中心
        for cluster in clusters:
            cluster_id = cluster['cluster_id']
            center_lat, center_lon = cluster['geo_center']
            cluster_centers[cluster_id] = (center_lat, center_lon)

        # 统计计数
        layer1_count = 0
        layer2_count = 0

        # 解析坐标字符串的辅助函数
        def parse_coord(coord_str):
            """解析 "(39.1244, 117.3462)" 格式的坐标字符串"""
            if pd.isna(coord_str) or not coord_str:
                return None, None
            try:
                import re
                match = re.search(r'\(([\d.]+),\s*([\d.]+)\)', str(coord_str))
                if match:
                    lat = float(match.group(1))
                    lon = float(match.group(2))
                    return lat, lon
            except:
                pass
            return None, None

        # 绘制三层运输路线
        for idx, row in h2_cluster_data.iterrows():
            # 解析聚类信息 "聚类0_(中心:36.2153,114.4731)"
            cluster_info = row.get('聚类信息', '')
            if not cluster_info or pd.isna(cluster_info):
                continue

            # 提取聚类ID
            try:
                cluster_id = int(cluster_info.split('聚类')[1].split('_')[0])
                if cluster_id not in cluster_centers:
                    continue
                center_lat, center_lon = cluster_centers[cluster_id]
            except:
                continue

            # 解析起点坐标
            start_lat, start_lon = parse_coord(row.get('起点坐标'))
            if start_lat is None or start_lon is None:
                continue

            # Layer1: 可再生能源站 → 聚类中心 (灰色虚线)
            layer1_dist = row.get('Layer1距离(km)', 0)
            if layer1_dist > 0:
                ax.plot(
                    [start_lon, center_lon],
                    [start_lat, center_lat],
                    color='gray',
                    alpha=0.6,
                    linewidth=1.5,
                    linestyle=':',
                    zorder=10,
                    transform=self.data_crs
                )
                layer1_count += 1

            # Layer2: 聚类中心 → 管道接入点 (灰色虚线)
            layer2_dist = row.get('Layer2距离(km)', 0)
            if layer2_dist > 0 and '路径坐标' in row and row['路径坐标'] and row['路径坐标'] != '[]':
                try:
                    path_coords = json.loads(row['路径坐标'])

                    # 从路径坐标中找最接近聚类中心的点作为起点
                    min_dist_to_center = float('inf')
                    start_idx = 0
                    for i, coord in enumerate(path_coords):
                        dist = self.haversine(center_lon, center_lat, coord[0], coord[1])
                        if dist < min_dist_to_center:
                            min_dist_to_center = dist
                            start_idx = i

                    # 从起点开始累计距离找到管道接入点
                    cumulative_dist = 0
                    pipeline_access_point = None
                    access_point_idx = start_idx

                    for i in range(start_idx + 1, len(path_coords)):
                        seg_dist = self.haversine(
                            path_coords[i-1][0], path_coords[i-1][1],
                            path_coords[i][0], path_coords[i][1]
                        )
                        cumulative_dist += seg_dist

                        # 如果累计距离接近Layer2距离，这就是管道接入点
                        if abs(cumulative_dist - layer2_dist) < 1:  # 1km容差
                            pipeline_access_point = path_coords[i]
                            access_point_idx = i
                            break

                    # 绘制Layer2：聚类中心 → 管道接入点
                    if pipeline_access_point:
                        ax.plot(
                            [center_lon, pipeline_access_point[0]],
                            [center_lat, pipeline_access_point[1]],
                            color='gray',
                            alpha=0.6,
                            linewidth=1.5,
                            linestyle=':',
                            zorder=10,
                            transform=self.data_crs
                        )
                        layer2_count += 1

                except Exception as e:
                    logger.warning(f"    解析路径坐标失败: {e}")

        # 绘制聚类中心
        if cluster_centers:
            for cluster_id, (center_lat, center_lon) in cluster_centers.items():
                cluster_color = self.cluster_colors[cluster_id % len(self.cluster_colors)]
                ax.scatter(
                    center_lon, center_lat,
                    c=cluster_color, s=100, marker='*',
                    edgecolors='black', linewidth=1.5,
                    transform=self.data_crs, zorder=25, alpha=1.0
                )

        logger.info(f"    ✓ Layer1: {layer1_count} 条（源点→聚类中心）")
        logger.info(f"    ✓ Layer2: {layer2_count} 条（聚类中心→管道接入点）")
        logger.info(f"    ✓ 聚类中心: {len(cluster_centers)} 个")

    def plot_pipeline_networks(self, ax):
        """
        绘制管道网络（从GeoJSON文件加载）

        Args:
            ax: matplotlib axes对象

        Returns:
            pipeline_stats: 各类型管道段数统计
        """
        # 管道类型配置
        pipeline_types = {
            'crude': {
                'name': '原油管道',
                'color': '#8B4513',  # 棕色
                'alpha': 0.5,
                'linewidth': 1.2,
                'file': 'crude_pipelines.geojson'
            },
            'refined': {
                'name': '成品油管道',
                'color': '#FF6B35',  # 橙红色
                'alpha': 0.5,
                'linewidth': 1.2,
                'file': 'refined_product_pipelines.geojson'
            },
            'natural_gas': {
                'name': '天然气管道',
                'color': '#4169E1',  # 皇家蓝
                'alpha': 0.6,
                'linewidth': 1.5,
                'file': 'natural_gas_pipelines.geojson'
            }
        }

        # GIS数据路径
        current_dir = Path(__file__).parent
        gis_data_path = current_dir.parent.parent / "gis_energy_mapping" / "gis_data_scraper" / "scraped_gis_data"

        pipeline_stats = {}

        for pipeline_type, config in pipeline_types.items():
            file_path = gis_data_path / config['file']

            if not file_path.exists():
                logger.warning(f"{config['name']}数据文件不存在: {file_path}")
                pipeline_stats[pipeline_type] = 0
                continue

            try:
                # 加载GeoJSON数据
                with open(file_path, 'r', encoding='utf-8') as f:
                    geojson_data = json.load(f)

                features = geojson_data.get('features', [])
                segments_count = 0

                logger.info(f"加载{config['name']}: {len(features)}个管道段")

                # 绘制每个管道段
                for feature in features:
                    if not feature.get('geometry') or feature['geometry'].get('type') != 'LineString':
                        continue

                    coordinates = feature['geometry']['coordinates']
                    if not coordinates or len(coordinates) < 2:
                        continue

                    # 提取经纬度
                    lons = [coord[0] for coord in coordinates]
                    lats = [coord[1] for coord in coordinates]

                    # 绘制管道段
                    ax.plot(
                        lons, lats,
                        color=config['color'],
                        alpha=config['alpha'],
                        linewidth=config['linewidth'],
                        transform=self.data_crs,
                        zorder=2  # 管道在运输路线下方
                    )

                    segments_count += 1

                pipeline_stats[pipeline_type] = segments_count
                logger.info(f"  ✓ 绘制 {segments_count} 个{config['name']}段")

            except Exception as e:
                logger.error(f"加载{config['name']}数据失败: {e}")
                pipeline_stats[pipeline_type] = 0

        return pipeline_stats

    def plot_saf_routes(self, ax, transport_summary):
        """
        绘制SAF卡车运输路线（使用GraphHopper获取详细路径）

        Args:
            ax: matplotlib axes对象
            transport_summary: 运输汇总DataFrame
        """
        if transport_summary is None or len(transport_summary) == 0:
            return

        # 筛选出SAF运输数据
        mtj_df = transport_summary[transport_summary['货物类型'] == 'MTJ'].copy()
        if len(mtj_df) == 0:
            return

        logger.info(f"  绘制SAF卡车路线...")

        # 解析坐标字符串的辅助函数
        def parse_coord(coord_str):
            """解析 "(39.1244, 117.3462)" 格式的坐标字符串"""
            if pd.isna(coord_str) or not coord_str:
                return None, None
            try:
                import re
                match = re.search(r'\(([\d.]+),\s*([\d.]+)\)', str(coord_str))
                if match:
                    lat = float(match.group(1))
                    lon = float(match.group(2))
                    return lat, lon
            except:
                pass
            return None, None

        # 使用周运输量计算线宽
        if '周运输量(kg)' in mtj_df.columns:
            volumes = mtj_df['周运输量(kg)'].values
        else:
            volumes = mtj_df.get('日运输量(kg)', pd.Series([1])).values

        max_volume = volumes.max()
        min_volume = volumes.min()

        route_count = 0
        graphhopper_success_count = 0
        direct_line_count = 0

        for idx, row in mtj_df.iterrows():
            # 解析起点和终点坐标
            start_lat, start_lon = parse_coord(row.get('起点坐标'))
            end_lat, end_lon = parse_coord(row.get('终点坐标'))

            if start_lat is None or start_lon is None or end_lat is None or end_lon is None:
                continue

            if '周运输量(kg)' in row:
                volume = row['周运输量(kg)']
            else:
                volume = row.get('日运输量(kg)', 1)

            # 计算线宽（基于运输量）
            if max_volume > min_volume:
                linewidth = 0.8 + 2.0 * (volume - min_volume) / (max_volume - min_volume)
            else:
                linewidth = 1.5

            # 尝试使用GraphHopper获取详细路径
            route_coords = None
            if self.graphhopper is not None:
                try:
                    result = self.graphhopper.calculate_route_distance(
                        start_lat=start_lat,
                        start_lon=start_lon,
                        end_lat=end_lat,
                        end_lon=end_lon,
                        vehicle='truck',
                        include_route_geometry=True
                    )

                    if result.get('route_found') and result.get('route_coordinates'):
                        route_coords = result['route_coordinates']
                        graphhopper_success_count += 1
                except Exception as e:
                    logger.debug(f"    GraphHopper路径获取失败: {e}")

            # 绘制路线
            if route_coords and len(route_coords) > 1:
                # 使用GraphHopper返回的详细路径
                lons = [coord[0] for coord in route_coords]
                lats = [coord[1] for coord in route_coords]
                ax.plot(lons, lats,
                       color=self.transport_colors['SAF'],
                       linewidth=linewidth,
                       alpha=0.8,
                       transform=self.data_crs,
                       zorder=15)
            else:
                # 降级为直线
                ax.plot([start_lon, end_lon], [start_lat, end_lat],
                       color=self.transport_colors['SAF'],
                       linewidth=linewidth,
                       alpha=0.8,
                       transform=self.data_crs,
                       zorder=15)
                direct_line_count += 1

            route_count += 1

        logger.info(f"    ✓ SAF路线: {route_count} 条")
        if self.graphhopper is not None:
            logger.info(f"    ✓ GraphHopper详细路径: {graphhopper_success_count} 条")
            logger.info(f"    ✓ 直线路径: {direct_line_count} 条")

    def plot_facilities(self, ax, transport_summary, module_name):
        """
        绘制设施位置（三维度分类：能源类型 × CO2捕获方式 × 功能角色）

        Args:
            ax: matplotlib axes对象
            transport_summary: 运输汇总数据
            module_name: 模块名称
        """
        if transport_summary is None:
            return

        # 解析坐标字符串的辅助函数
        def parse_coord(coord_str):
            """解析 "(39.1244, 117.3462)" 格式的坐标字符串"""
            if pd.isna(coord_str) or not coord_str:
                return None, None
            try:
                import re
                match = re.search(r'\(([\d.]+),\s*([\d.]+)\)', str(coord_str))
                if match:
                    lat = float(match.group(1))
                    lon = float(match.group(2))
                    return lat, lon
            except:
                pass
            return None, None

        # 收集所有设施及其角色：{(lon, lat, name): set(roles)}
        facility_roles = {}

        for _, row in transport_summary.iterrows():
            start_type = str(row.get('起点类型', '')).strip()
            end_type = str(row.get('终点类型', '')).strip()

            start_name = row.get('起点', '')
            end_name = row.get('终点', '')

            start_lat, start_lon = parse_coord(row.get('起点坐标'))
            end_lat, end_lon = parse_coord(row.get('终点坐标'))

            # 收集起点的角色
            if start_lat is not None and start_lon is not None:
                facility_key = (start_lon, start_lat, start_name)
                if facility_key not in facility_roles:
                    facility_roles[facility_key] = set()
                if start_type:
                    facility_roles[facility_key].add(start_type)

            # 收集终点的角色
            if end_lat is not None and end_lon is not None:
                facility_key = (end_lon, end_lat, end_name)
                if facility_key not in facility_roles:
                    facility_roles[facility_key] = set()
                if end_type:
                    facility_roles[facility_key].add(end_type)

        # 按三维度分类设施
        facility_classification = {}  # {(energy_type, co2_capture, role_count): [(lon, lat, name, roles), ...]}

        for (lon, lat, name), roles in facility_roles.items():
            # 维度1：能源类型
            energy_type = self.classify_energy_type(name)

            # 维度2：CO2捕获方式
            co2_capture = self.classify_co2_capture(module_name, roles)

            # 维度3：功能角色数量
            role_count = len(roles)

            # 组合键
            combo_key = (energy_type, co2_capture, role_count)
            if combo_key not in facility_classification:
                facility_classification[combo_key] = []

            facility_classification[combo_key].append((lon, lat, name, roles))

        # 按组合绘制设施
        logger.info(f"    设施分类统计（共{len(facility_classification)}种组合）：")

        for combo_key, facilities in sorted(facility_classification.items()):
            energy_type, co2_capture, role_count = combo_key

            # 获取可视化属性
            vis_attrs = self.get_visualization_attrs(energy_type, co2_capture, role_count)

            # 提取坐标
            lons = [f[0] for f in facilities]
            lats = [f[1] for f in facilities]

            # 绘制
            ax.scatter(
                lons, lats,
                marker=vis_attrs['marker'],
                c=vis_attrs['color'],
                s=vis_attrs['size'],
                alpha=0.9,
                edgecolors='black',
                linewidth=vis_attrs['linewidth'],
                transform=self.data_crs,
                zorder=30
            )

            # 日志输出
            energy_type_cn = {
                'solar': '光伏',
                'wind': '风能',
                'natural_gas': '天然气',
                'coal': '煤炭',
                'airport': '机场',
                'other': '其他'
            }.get(energy_type, energy_type)

            co2_capture_cn = {
                'dac': 'DAC捕获',
                'industrial': '工业副产物',
                'none': '无捕获'
            }.get(co2_capture, co2_capture)

            logger.info(f"      {energy_type_cn} + {co2_capture_cn} + {role_count}重角色: {len(facilities)} 个")

    def create_individual_module_map(self, module_name: str):
        """
        创建单个模块的聚类运输路线地图

        Args:
            module_name: 模块名称
        """
        logger.info(f"\n生成 {module_name} 聚类运输路线地图...")

        config = self.modules[module_name]
        data = self.transport_data[module_name]

        fig, ax = self.create_base_map(figsize=(18, 14))

        # 先绘制管道网络（作为底层）
        logger.info(f"  绘制管道网络...")
        pipeline_stats = self.plot_pipeline_networks(ax)

        # 绘制H2聚类运输路线
        self.plot_h2_clustered_routes(ax, data['h2_clustering'], data['transport_summary'], module_name)

        # 绘制SAF运输路线
        self.plot_saf_routes(ax, data['transport_summary'])

        # 绘制设施位置
        self.plot_facilities(ax, data['transport_summary'], module_name)

        # 添加装饰元素
        self.add_decorations(ax)

        # 添加图例（分三部分：路线、设施形状、设施颜色）
        legend_elements = [
            # === 路线图例 ===
            Line2D([0], [0], color='gray', linewidth=2, linestyle=':',
                   label='H₂ Layer1/2 (源点→聚类→管道接入点)'),
            Line2D([0], [0], marker='*', color='w', markerfacecolor='purple',
                   markersize=12, label='H₂聚类中心'),
            Line2D([0], [0], color=self.transport_colors['SAF'], linewidth=2.5,
                   label='SAF卡车运输'),
        ]

        # === 设施形状图例（能源类型）===
        legend_elements.append(Line2D([0], [0], marker='', color='w', label=''))  # 空行
        legend_elements.append(Line2D([0], [0], marker='', color='w',
                                     label='【设施形状 = 能源类型】', markerfacecolor='w'))

        energy_type_legend = [
            Line2D([0], [0], marker='*', color='w', markerfacecolor='gray',
                   markersize=12, markeredgecolor='black', markeredgewidth=1,
                   label='★ 光伏电站 Solar'),
            Line2D([0], [0], marker='^', color='w', markerfacecolor='gray',
                   markersize=10, markeredgecolor='black', markeredgewidth=1,
                   label='▲ 风电站 Wind'),
            Line2D([0], [0], marker='D', color='w', markerfacecolor='gray',
                   markersize=8, markeredgecolor='black', markeredgewidth=1,
                   label='◆ 天然气 Natural Gas'),
            Line2D([0], [0], marker='s', color='w', markerfacecolor='gray',
                   markersize=8, markeredgecolor='black', markeredgewidth=1,
                   label='■ 煤炭 Coal'),
            Line2D([0], [0], marker='o', color='w', markerfacecolor='gray',
                   markersize=10, markeredgecolor='black', markeredgewidth=1,
                   label='● 机场 Airport'),
        ]
        legend_elements.extend(energy_type_legend)

        # === 设施颜色图例（CO2捕获方式）===
        legend_elements.append(Line2D([0], [0], marker='', color='w', label=''))  # 空行
        legend_elements.append(Line2D([0], [0], marker='', color='w',
                                     label='【设施颜色 = CO2捕获】', markerfacecolor='w'))

        co2_capture_legend = [
            Line2D([0], [0], marker='o', color='w', markerfacecolor='#1E90FF',
                   markersize=10, markeredgecolor='black', markeredgewidth=1,
                   label='🔵 DAC捕获'),
            Line2D([0], [0], marker='o', color='w', markerfacecolor='#DC143C',
                   markersize=10, markeredgecolor='black', markeredgewidth=1,
                   label='🔴 工业副产物'),
            Line2D([0], [0], marker='o', color='w', markerfacecolor='#696969',
                   markersize=10, markeredgecolor='black', markeredgewidth=1,
                   label='⚫ 无CO2捕获'),
        ]
        legend_elements.extend(co2_capture_legend)

        # === 边框粗细图例（功能复杂度）===
        legend_elements.append(Line2D([0], [0], marker='', color='w', label=''))  # 空行
        legend_elements.append(Line2D([0], [0], marker='', color='w',
                                     label='【边框粗细 = 角色数】', markerfacecolor='w'))

        role_count_legend = [
            Line2D([0], [0], marker='o', color='w', markerfacecolor='gray',
                   markersize=10, markeredgecolor='black', markeredgewidth=2.5,
                   label='四重角色（粗边框）'),
            Line2D([0], [0], marker='o', color='w', markerfacecolor='gray',
                   markersize=10, markeredgecolor='black', markeredgewidth=2.0,
                   label='三重角色（中边框）'),
            Line2D([0], [0], marker='o', color='w', markerfacecolor='gray',
                   markersize=10, markeredgecolor='black', markeredgewidth=1.5,
                   label='双重角色（细边框）'),
            Line2D([0], [0], marker='o', color='w', markerfacecolor='gray',
                   markersize=10, markeredgecolor='black', markeredgewidth=1.0,
                   label='单一角色（最细）'),
        ]
        legend_elements.extend(role_count_legend)

        # 添加管道网络图例
        legend_elements.append(Line2D([0], [0], marker='', color='w', label=''))  # 空行
        legend_elements.append(Line2D([0], [0], marker='', color='w',
                                     label='【管道网络】', markerfacecolor='w'))

        pipeline_names = {
            'crude': '原油管道',
            'refined': '成品油管道',
            'natural_gas': '天然气管道'
        }
        pipeline_colors = {
            'crude': '#8B4513',
            'refined': '#FF6B35',
            'natural_gas': '#4169E1'
        }

        for pipeline_type, count in pipeline_stats.items():
            if count > 0:
                legend_elements.append(
                    Line2D([0], [0], color=pipeline_colors[pipeline_type],
                          linewidth=2, alpha=0.6,
                          label=f'{pipeline_names[pipeline_type]} ({count}段)')
                )

        ax.legend(handles=legend_elements, loc='upper left', fontsize=8, framealpha=0.95,
                 ncol=1, borderpad=1, labelspacing=0.5)

        # 添加标题
        h2_clusters = data['h2_clustering']['total_clusters'] if data['h2_clustering'] else 0

        # 统计SAF路线数量
        saf_routes = 0
        if data['transport_summary'] is not None:
            saf_routes = len(data['transport_summary'][data['transport_summary']['货物类型'] == 'MTJ'])

        total_pipelines = sum(pipeline_stats.values())

        title = (f"{config['name_cn']} SAF供应链聚类运输网络（两层结构）\n"
                f"{module_name} SAF Supply Chain Clustered Transport Network (Two Layers)\n"
                f"H₂聚类: {h2_clusters} 个 | SAF路线: {saf_routes} 条 | 管道: {total_pipelines} 段")
        ax.set_title(title, fontsize=14, fontweight='bold', pad=20)

        plt.tight_layout()

        # 保存图片
        output_path = self.session_dir / f"clustered_map_{module_name.replace(' ', '_').lower()}.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        logger.info(f"  ✓ 保存图片: {output_path}")
        plt.close()

    def run_all_visualizations(self):
        """运行所有可视化"""
        logger.info("\n" + "=" * 60)
        logger.info("开始生成聚类地图可视化")
        logger.info("=" * 60)

        try:
            # 生成各模块独立地图
            for module_name in self.modules.keys():
                self.create_individual_module_map(module_name)

            logger.info("\n" + "=" * 60)
            logger.info("✓ 所有聚类地图可视化生成完成")
            logger.info(f"✓ 输出目录: {self.session_dir}")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"\n✗ 聚类地图可视化生成失败: {e}")
            raise


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("三模块聚类运输路线地图可视化脚本")
    logger.info("Three Modules Clustered Transport Route Map Visualization Script")
    logger.info("=" * 60)

    try:
        # 创建可视化器
        visualizer = ThreeModulesClusteredMapVisualizer()

        # 加载数据
        visualizer.load_data()

        # 运行所有可视化
        visualizer.run_all_visualizations()

        logger.info("\n✓ 程序执行成功")

    except Exception as e:
        logger.error(f"\n✗ 程序执行失败: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
