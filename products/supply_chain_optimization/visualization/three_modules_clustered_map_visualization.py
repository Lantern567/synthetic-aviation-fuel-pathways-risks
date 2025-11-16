"""
五场景聚类运输路线地图可视化（包含聚类和管道接入点）
Five Scenarios Clustered Transport Route Map Visualization (with clustering and pipeline access points)

基于聚类JSON文件和运输CSV文件生成完整的多层级运输可视化
Based on clustering JSON files and transport CSV files to generate comprehensive multi-layer transport visualization

功能 | Features:
1. 氢气聚类运输可视化 (H2 clustered transport visualization)
   - Layer1: 可再生能源站 → 聚类中心
   - Layer2: 聚类中心 → 管道接入点
   - Layer3: 管道网络 → 目的地
2. CO2聚类运输可视化 (CO2 clustered transport visualization)
3. 天然气聚类运输可视化 (Natural gas clustered transport visualization)
   - Layer1: 天然气管道节点 → 聚类中心
   - Layer2: 聚类中心 → SAF工厂
4. 天然气直接运输可视化 (Natural gas direct transport visualization)
   - 天然气供应点 → SAF工厂
5. SAF卡车运输可视化 (SAF truck transport visualization)
6. 管道网络底图 (Pipeline network basemap)
7. 五场景对比地图 (Five scenarios comparison maps)

支持场景 | Supported Scenarios:
1. 煤制氢 (Coal Hydrogen)
2. DAC制氢 (DAC Hydrogen)
3. 天然气两步法 (Natural Gas Two-Step)
4. 天然气一步法 (Natural Gas One-Step)
5. 绿氢+工业捕获CO₂ (Green H2 + Industrial CO2)

作者 | Author: Claude Code
创建时间 | Created: 2025-11-06
最后更新 | Last Updated: 2025-11-09
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

# 配置中文字体 - 支持Linux和Windows系统,移除DejaVu Sans避免回退
matplotlib.rcParams['font.sans-serif'] = ['Noto Sans CJK SC', 'Noto Sans CJK TC', 'WenQuanYi Zen Hei', 'Microsoft YaHei', 'SimHei']
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


class FiveScenariosClusteredMapVisualizer:
    """五场景聚类运输路线地图可视化器"""

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

        # 模块配置 - 使用自动查找最新文件
        # 获取项目根目录
        project_root = Path(__file__).parent.parent.parent.parent

        self.modules = {
            'Coal Hydrogen': {
                'name_cn': '煤制氢',
                'color': '#E74C3C',
                'h2_clustering_file': str(project_root / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/clustering_results.json'),
                'co2_clustering_file': str(project_root / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/co2_clustering_results.json'),
                'ng_clustering_file': None,
                'transport_summary_pattern': str(project_root / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/transport_summary_*.csv')
            },
            'DAC Hydrogen': {
                'name_cn': 'DAC制氢',
                'color': '#3498DB',
                'h2_clustering_file': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/clustering_results.json'),
                'co2_clustering_file': None,  # DAC从空气中捕获CO2，无需CO2运输
                'ng_clustering_file': None,
                'transport_summary_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/two_step/transport_summary_*.csv')
            },
            'Natural Gas Two-Step': {
                'name_cn': '天然气两步法',
                'color': '#2ECC71',
                'h2_clustering_file': str(project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/clustering_results.json'),
                'co2_clustering_file': None,  # 天然气制氢过程中CO2作为副产物，无独立运输
                'ng_clustering_file': None,
                'transport_summary_pattern': str(project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/transport_summary_*.csv')
            },
            'Natural Gas One-Step': {
                'name_cn': '天然气一步法',
                'color': '#F39C12',
                'h2_clustering_file': None,  # 一步法不需要氢气聚类
                'co2_clustering_file': None,
                'ng_clustering_file': None,  # 一步法目前没有天然气聚类文件
                # 一步法的transport_summary直接保存在results/目录下，不在ft_one_step子目录
                'transport_summary_pattern': str(project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/transport_summary_*.csv')
            },
            'Green H2 Industrial CO2': {
                'name_cn': '绿氢+工业捕获CO₂',
                'color': '#9B59B6',
                'h2_clustering_file': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/clustering_results.json'),
                'co2_clustering_file': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/co2_clustering_results.json'),
                'ng_clustering_file': None,
                'transport_summary_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/two_step/transport_summary_*.csv')
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
            'SAF': '#FF4500',         # SAF - 橙红色
            'NG': '#32CD32'           # 天然气 - lime green 青柠绿
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

        # 不需要base_dir，所有路径都是绝对路径

        for module_name, config in self.modules.items():
            logger.info(f"\n正在加载: {module_name} ({config['name_cn']})")

            module_data = {
                'h2_clustering': None,
                'co2_clustering': None,
                'ng_clustering': None,
                'transport_summary': None
            }

            try:
                # 加载H2聚类数据（如果有）
                if config['h2_clustering_file']:
                    h2_clustering_file = Path(config['h2_clustering_file'])
                    if h2_clustering_file.exists():
                        with open(h2_clustering_file, 'r', encoding='utf-8') as f:
                            module_data['h2_clustering'] = json.load(f)
                        logger.info(f"  ✓ H2聚类数据: {module_data['h2_clustering']['total_clusters']} 个聚类")
                    else:
                        logger.warning(f"  ⚠ H2聚类文件不存在: {h2_clustering_file}")
                else:
                    logger.info(f"  - 无H2聚类数据（不需要氢气运输）")

                # 加载CO2聚类数据（如果有）
                if config['co2_clustering_file']:
                    co2_clustering_file = Path(config['co2_clustering_file'])
                    if co2_clustering_file.exists():
                        with open(co2_clustering_file, 'r', encoding='utf-8') as f:
                            module_data['co2_clustering'] = json.load(f)
                        logger.info(f"  ✓ CO2聚类数据: {module_data['co2_clustering']['total_clusters']} 个聚类")
                    else:
                        logger.warning(f"  ⚠ CO2聚类文件不存在: {co2_clustering_file}")
                else:
                    logger.info(f"  - 无CO2聚类数据（不需要CO2运输）")

                # 加载天然气聚类数据（如果有）
                if config['ng_clustering_file']:
                    ng_clustering_file = Path(config['ng_clustering_file'])
                    if ng_clustering_file.exists():
                        with open(ng_clustering_file, 'r', encoding='utf-8') as f:
                            module_data['ng_clustering'] = json.load(f)
                        logger.info(f"  ✓ 天然气聚类数据: {module_data['ng_clustering']['total_clusters']} 个聚类")
                    else:
                        logger.warning(f"  ⚠ 天然气聚类文件不存在: {ng_clustering_file}")
                else:
                    logger.info(f"  - 无天然气聚类数据（不需要天然气聚类运输）")

                # 加载运输汇总数据（自动查找最新文件）
                import glob
                summary_pattern = config['transport_summary_pattern']
                summary_files = sorted(glob.glob(summary_pattern), reverse=True)

                if summary_files:
                    summary_file = Path(summary_files[0])
                    logger.info(f"  使用最新的运输汇总文件: {summary_file.name}")
                    module_data['transport_summary'] = pd.read_csv(summary_file, encoding='utf-8')
                    logger.info(f"  ✓ 运输汇总数据: {len(module_data['transport_summary'])} 条")

                    # 显示数据列名（调试用）
                    logger.info(f"  数据列: {list(module_data['transport_summary'].columns)}")

                    # 按货物类型分组统计
                    if '货物类型' in module_data['transport_summary'].columns:
                        cargo_counts = module_data['transport_summary']['货物类型'].value_counts()
                        for cargo_type, count in cargo_counts.items():
                            logger.info(f"    - {cargo_type}: {count} 条")
                else:
                    logger.warning(f"  ⚠ 未找到运输汇总文件: {config['transport_summary_pattern']}")

                self.transport_data[module_name] = module_data

            except Exception as e:
                logger.error(f"  ✗ 加载失败: {e}")
                import traceback
                traceback.print_exc()
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

        # 设置地图范围 - 京津冀及周边地区,扩大到44°N
        if extent is None:
            extent = [111, 121, 35, 44]

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

    def classify_facility(self, facility_name: str, facility_types: set, cargo_types: set = None) -> Tuple[frozenset, str, str]:
        """
        三维张量分类系统: 每个设施在三个独立维度上进行分类
        维度1支持多选，因为一个设施可能同时生产多种原材料

        Args:
            facility_name: 设施名称
            facility_types: 设施类型集合（一个设施可能在不同运输记录中有不同类型）
            cargo_types: 该设施处理的货物类型集合（用于推断功能）

        Returns:
            (raw_material_types, has_saf_production, is_consumption):
                raw_material_types: frozenset of {'h2', 'co2', 'natural_gas'}, 可以是多个
                has_saf_production: 'yes' | 'no'
                is_consumption: 'yes' | 'no'
        """
        name_lower = str(facility_name).lower()

        if cargo_types is None:
            cargo_types = set()
        if facility_types is None:
            facility_types = set()

        # 将所有facility_type转为小写
        types_lower = {str(t).lower() for t in facility_types}

        # === 维度3: 是否为消纳地 ===
        is_consumption = 'no'
        if 'airport' in name_lower or facility_name in ['天津', '北京']:
            is_consumption = 'yes'
        if any('机场' in t for t in types_lower):
            is_consumption = 'yes'

        # === 维度2: 是否有SAF生产 ===
        has_saf_production = 'no'
        # 如果是工厂类型，或者处理MTJ货物（作为起点发出MTJ）
        if any('factory' in t or '工厂' in t for t in types_lower):
            has_saf_production = 'yes'
        elif 'saf' in name_lower:
            has_saf_production = 'yes'
        elif 'MTJ' in cargo_types:
            # 如果作为起点发出MTJ，说明有SAF生产能力
            has_saf_production = 'yes'

        # === 维度1: 原材料生产类型（可以是多个）===
        raw_material_types = set()

        # 【关键修改】优先根据实际发出的货物类型判断原材料生产能力
        # 只有当设施作为起点发出某种原材料时，才认为它生产该原材料
        if '氢气' in cargo_types:
            raw_material_types.add('h2')
        if 'CO2' in cargo_types:
            raw_material_types.add('co2')
        if '天然气' in cargo_types:
            raw_material_types.add('natural_gas')

        # 【降级判断】如果cargo_types为空（没有作为起点发货），才根据名称和类型推断
        # 这适用于某些设施可能在聚类过程中没有直接出现在起点的情况
        if not raw_material_types:
            # CO2捕获设施
            if any('co2' in t or '捕获' in t or 'capture' in t for t in types_lower):
                raw_material_types.add('co2')
            # 从名称判断CO2设施
            if any(keyword in name_lower for keyword in ['dac', 'carbon', 'co2', '碳', '捕获']):
                raw_material_types.add('co2')

            # 天然气供应点
            if any('天然气' in t or 'natural gas' in t or 'ng' in t for t in types_lower):
                raw_material_types.add('natural_gas')
            if 'ng_pipeline' in name_lower or ('天然气' in name_lower and '管道' in name_lower):
                raw_material_types.add('natural_gas')

            # H2生产设施（光伏、风电、煤炭等）
            # 注意：不匹配"生产设施"，因为"生产设施"可能是SAF工厂，不代表生产H2
            if any('氢气' in t or 'hydrogen' in t for t in types_lower):
                raw_material_types.add('h2')
            if any(keyword in name_lower for keyword in ['solar', 'wind', 'pv', 'photovoltaic', '光伏', '风能', '风电', 'coal', '煤炭', '煤制']):
                raw_material_types.add('h2')

        # 【关键规则】如果是消纳地（机场），强制清空原材料生产能力
        # 机场不能生产原材料（氢气、CO2、天然气），但可以有SAF工厂
        if is_consumption == 'yes':
            raw_material_types.clear()

        # 如果没有任何原材料生产，返回空集
        return (frozenset(raw_material_types), has_saf_production, is_consumption)

    def get_facility_visualization_attrs(self, raw_materials: frozenset, saf_production: str, consumption: str) -> list:
        """
        三维张量可视化属性映射，支持多角色设施

        维度1 - 原材料生产类型 (形状, 可多选):
            'h2' → '^' 三角形
            'co2' → 's' 方形
            'natural_gas' → 'D' 菱形
            空集 → 'o' 圆形

        维度2 - SAF生产 (颜色, 2种):
            'yes' → 蓝色系
            'no' → 灰色系

        维度3 - 消纳地 (边框粗细, 2种):
            'yes' → 粗边框 (linewidth=3.0)
            'no' → 细边框 (linewidth=1.5)

        Args:
            raw_materials: 原材料类型集合 frozenset({'h2', 'co2', 'natural_gas'})
            saf_production: SAF生产 ('yes', 'no')
            consumption: 消纳地 ('yes', 'no')

        Returns:
            可视化属性字典列表（多角色设施返回多个标记）
        """
        # 维度1: 形状映射
        shape_map = {
            'h2': ('^', 'H₂生产'),
            'co2': ('s', 'CO₂捕获'),
            'natural_gas': ('D', '天然气供应'),
        }

        # 维度2: 颜色映射
        color_map = {
            'yes': ('#4169E1', '#1E3A8A', '有SAF生产'),  # 蓝色系: (填充色, 边框色, 标签)
            'no': ('#A9A9A9', '#696969', '无SAF生产')   # 灰色系
        }

        # 维度3: 边框粗细映射
        linewidth_map = {
            'yes': (3.0, '是消纳地'),
            'no': (1.5, '非消纳地')
        }

        # 获取维度2、3的属性（对所有标记通用）
        color, edgecolor, saf_label = color_map.get(saf_production, ('#808080', '#404040', '未知'))
        linewidth, consumption_label = linewidth_map.get(consumption, (1.0, '未知'))

        # 生成标记列表
        markers = []

        if not raw_materials:
            # 无原材料生产 - 单一圆形标记
            markers.append({
                'marker': 'o',
                'color': color,
                'edgecolor': edgecolor,
                'size': 100,
                'linewidth': linewidth,
                'raw_material_label': '无原材料生产',
                'saf_production_label': saf_label,
                'consumption_label': consumption_label,
                'full_label': f"无原材料生产 × {saf_label} × {consumption_label}"
            })
        else:
            # 有原材料生产 - 为每种原材料生成一个标记
            material_labels = []
            for material in sorted(raw_materials):  # 排序保证顺序一致
                marker, material_label = shape_map.get(material, ('h', '未知'))
                material_labels.append(material_label)

                markers.append({
                    'marker': marker,
                    'color': color,
                    'edgecolor': edgecolor,
                    'size': 100,
                    'linewidth': linewidth,
                    'raw_material_label': material_label,
                    'saf_production_label': saf_label,
                    'consumption_label': consumption_label,
                    'full_label': f"{material_label} × {saf_label} × {consumption_label}"
                })

            # 如果是多角色，添加组合标签到第一个标记
            if len(markers) > 1:
                combined_label = '+'.join(material_labels)
                markers[0]['combined_label'] = f"{combined_label} × {saf_label} × {consumption_label}"

        return markers

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
        all_cluster_centers = {}

        # 提取所有聚类中心
        for cluster in clusters:
            cluster_id = cluster['cluster_id']
            center_lat, center_lon = cluster['geo_center']
            all_cluster_centers[cluster_id] = (center_lat, center_lon)

        # 【关键修改】只记录实际使用的聚类中心
        used_cluster_centers = {}

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
            # 【新增】过滤运输量为0的记录 - 支持周运输量和日运输量
            volume_weekly = row.get('周运输量(kg)', 0)
            volume_daily = row.get('日运输量(kg)', 0)
            # 只要有一个运输量>0就保留
            if (pd.isna(volume_weekly) or volume_weekly == 0) and (pd.isna(volume_daily) or volume_daily == 0):
                continue

            # 解析聚类信息 "聚类0_(中心:36.2153,114.4731)"
            cluster_info = row.get('聚类信息', '')
            if not cluster_info or pd.isna(cluster_info):
                continue

            # 提取聚类ID
            try:
                cluster_id = int(cluster_info.split('聚类')[1].split('_')[0])
                if cluster_id not in all_cluster_centers:
                    continue
                center_lat, center_lon = all_cluster_centers[cluster_id]

                # 【关键修改】只有运输量>0时才标记聚类中心为已使用
                used_cluster_centers[cluster_id] = (center_lat, center_lon)
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

        # 【关键修改】只绘制实际使用的聚类中心
        if used_cluster_centers:
            for cluster_id, (center_lat, center_lon) in used_cluster_centers.items():
                cluster_color = self.cluster_colors[cluster_id % len(self.cluster_colors)]
                ax.scatter(
                    center_lon, center_lat,
                    c=cluster_color, s=150, marker='P',  # 使用五角星'P',大小150
                    edgecolors='black', linewidth=2.0,
                    transform=self.data_crs, zorder=25, alpha=1.0
                )

        logger.info(f"    ✓ Layer1: {layer1_count} 条（源点→聚类中心）")
        logger.info(f"    ✓ Layer2: {layer2_count} 条（聚类中心→管道接入点）")
        logger.info(f"    ✓ 实际使用的聚类中心: {len(used_cluster_centers)} 个（总共{len(all_cluster_centers)}个）")

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

    def plot_ng_routes(self, ax, transport_summary):
        """
        绘制天然气运输路线（从天然气供应点到SAF工厂）

        Args:
            ax: matplotlib axes对象
            transport_summary: 运输汇总DataFrame
        """
        if transport_summary is None or len(transport_summary) == 0:
            return

        # 筛选出天然气运输数据
        ng_df = transport_summary[transport_summary['货物类型'] == '天然气'].copy()
        if len(ng_df) == 0:
            logger.info(f"  天然气运输数据为空，跳过天然气路线绘制")
            return

        logger.info(f"  绘制天然气运输路线...")

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
        if '周运输量(kg)' in ng_df.columns:
            volumes = ng_df['周运输量(kg)'].values
        elif '周运输量(m³)' in ng_df.columns:
            volumes = ng_df['周运输量(m³)'].values
        else:
            volumes = ng_df.get('日运输量(m³)', pd.Series([1])).values

        max_volume = volumes.max()
        min_volume = volumes.min()

        route_count = 0
        graphhopper_success_count = 0
        direct_line_count = 0

        for idx, row in ng_df.iterrows():
            # 解析起点和终点坐标
            start_lat, start_lon = parse_coord(row.get('起点坐标'))
            end_lat, end_lon = parse_coord(row.get('终点坐标'))

            if start_lat is None or start_lon is None or end_lat is None or end_lon is None:
                continue

            if '周运输量(kg)' in row:
                volume = row['周运输量(kg)']
            elif '周运输量(m³)' in row:
                volume = row['周运输量(m³)']
            else:
                volume = row.get('日运输量(m³)', 1)

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
                       color=self.transport_colors['NG'],
                       linewidth=linewidth,
                       alpha=0.8,
                       transform=self.data_crs,
                       zorder=14)
            else:
                # 降级为直线
                ax.plot([start_lon, end_lon], [start_lat, end_lat],
                       color=self.transport_colors['NG'],
                       linewidth=linewidth,
                       alpha=0.8,
                       transform=self.data_crs,
                       zorder=14)
                direct_line_count += 1

            route_count += 1

        logger.info(f"    ✓ 天然气路线: {route_count} 条")
        if self.graphhopper is not None:
            logger.info(f"    ✓ GraphHopper详细路径: {graphhopper_success_count} 条")
            logger.info(f"    ✓ 直线路径: {direct_line_count} 条")

    def plot_ng_clustered_routes(self, ax, ng_clustering, transport_summary, module_name):
        """
        绘制天然气聚类运输路线（两层结构，用于天然气一步法场景）

        Args:
            ax: matplotlib axes对象
            ng_clustering: 天然气聚类JSON数据
            transport_summary: 运输汇总DataFrame（包含Layer信息）
            module_name: 模块名称
        """
        if ng_clustering is None or transport_summary is None:
            return

        logger.info(f"  绘制天然气聚类路线...")

        # 筛选出天然气运输数据
        ng_data = transport_summary[transport_summary['货物类型'] == '天然气'].copy()
        logger.info(f"    天然气运输数据: {len(ng_data)} 条")

        # 筛选聚类数据（有聚类信息的行）
        ng_cluster_data = ng_data[ng_data['聚类信息'].notna() & (ng_data['聚类信息'] != '')].copy()
        logger.info(f"    聚类运输数据: {len(ng_cluster_data)} 条")

        clusters = ng_clustering.get('clusters', [])
        all_cluster_centers = {}

        # 提取所有聚类中心
        for cluster in clusters:
            cluster_id = cluster['cluster_id']
            center_lat, center_lon = cluster['geo_center']
            all_cluster_centers[cluster_id] = (center_lat, center_lon)

        # 【关键修改】只记录实际使用的聚类中心
        used_cluster_centers = {}

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

        # 绘制两层运输路线
        for idx, row in ng_cluster_data.iterrows():
            # 【新增】过滤运输量为0的记录
            volume = 0
            if '周运输量(kg)' in row:
                volume = row.get('周运输量(kg)', 0)
            elif '周运输量(m³)' in row:
                volume = row.get('周运输量(m³)', 0)

            if volume == 0 or pd.isna(volume):
                continue

            # 解析聚类信息 "聚类0_(中心:36.2153,114.4731)"
            cluster_info = row.get('聚类信息', '')
            if not cluster_info or pd.isna(cluster_info):
                continue

            # 提取聚类ID
            try:
                cluster_id = int(cluster_info.split('聚类')[1].split('_')[0])
                if cluster_id not in all_cluster_centers:
                    continue
                center_lat, center_lon = all_cluster_centers[cluster_id]

                # 【关键修改】只有运输量>0时才标记聚类中心为已使用
                used_cluster_centers[cluster_id] = (center_lat, center_lon)
            except:
                continue

            # 解析起点和终点坐标
            start_lat, start_lon = parse_coord(row.get('起点坐标'))
            end_lat, end_lon = parse_coord(row.get('终点坐标'))

            if start_lat is None or start_lon is None:
                continue

            # Layer1: 天然气管道节点 → 天然气聚类中心 (lime green虚线)
            layer1_dist = row.get('Layer1距离(km)', 0)
            if layer1_dist > 0:
                ax.plot(
                    [start_lon, center_lon],
                    [start_lat, center_lat],
                    color=self.transport_colors['NG'],
                    alpha=0.6,
                    linewidth=1.5,
                    linestyle=':',
                    zorder=10,
                    transform=self.data_crs
                )
                layer1_count += 1

            # Layer2: 天然气聚类中心 → SAF工厂 (lime green实线)
            layer2_dist = row.get('Layer2距离(km)', 0)
            if layer2_dist > 0 and end_lat is not None and end_lon is not None:
                ax.plot(
                    [center_lon, end_lon],
                    [center_lat, end_lat],
                    color=self.transport_colors['NG'],
                    alpha=0.7,
                    linewidth=2.0,
                    linestyle='-',
                    zorder=14,
                    transform=self.data_crs
                )
                layer2_count += 1

        # 【关键修改】只绘制实际使用的天然气聚类中心
        if used_cluster_centers:
            for cluster_id, (center_lat, center_lon) in used_cluster_centers.items():
                cluster_color = self.cluster_colors[cluster_id % len(self.cluster_colors)]
                ax.scatter(
                    center_lon, center_lat,
                    c=cluster_color, s=150, marker='D',  # 使用菱形'D',大小150
                    edgecolors='black', linewidth=2.0,
                    transform=self.data_crs, zorder=25, alpha=1.0
                )

        logger.info(f"    ✓ Layer1: {layer1_count} 条（管道节点→聚类中心）")
        logger.info(f"    ✓ Layer2: {layer2_count} 条（聚类中心→SAF工厂）")
        logger.info(f"    ✓ 实际使用的聚类中心: {len(used_cluster_centers)} 个（总共{len(all_cluster_centers)}个）")


    def plot_facilities(self, ax, transport_summary, module_name):
        """
        绘制设施位置（三维张量分类: 原材料类型 × SAF生产 × 消纳地）

        Args:
            ax: matplotlib axes对象
            transport_summary: 运输汇总数据
            module_name: 模块名称

        Returns:
            facility_classification: 设施分类统计字典
        """
        if transport_summary is None:
            logger.warning("  运输汇总数据为None，跳过设施绘制")
            return {}

        logger.info(f"  绘制设施位置...")
        logger.info(f"    运输汇总数据行数: {len(transport_summary)}")

        # 【特殊处理】天然气两步法：统计每个设施的SAF产量，用于筛选
        facility_saf_production = {}  # {coord: total_saf_volume}
        if module_name == 'Natural Gas Two-Step':
            logger.info(f"    天然气两步法场景：统计SAF产量用于筛选（只显示>10kg的生产地）")
            for _, row in transport_summary.iterrows():
                cargo_type = row.get('货物类型', '')
                if cargo_type == 'MTJ' or cargo_type == 'SAF':
                    # 提取起点坐标和产量
                    start_coord_str = row.get('起点坐标', '')
                    volume = 0
                    if '周运输量(kg)' in row:
                        volume = row.get('周运输量(kg)', 0)
                    elif '日运输量(kg)' in row:
                        volume = row.get('日运输量(kg)', 0) * 7  # 转换为周产量

                    if pd.notna(volume) and volume > 0:
                        if start_coord_str not in facility_saf_production:
                            facility_saf_production[start_coord_str] = 0
                        facility_saf_production[start_coord_str] += volume

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

        # 【关键修改】使用纯坐标作为key，确保每个地理位置只有一个点
        # 第一步: 收集每个坐标位置的所有信息（过滤运输量为0的记录）
        facility_info = {}  # {(lon, lat): {'names': set(), 'types': set(), 'cargos': set()}}

        total_rows = len(transport_summary)
        filtered_rows = 0

        for _, row in transport_summary.iterrows():
            # 【新增】过滤条件：跳过运输量为0的记录
            volume = 0
            if '周运输量(kg)' in row:
                volume = row.get('周运输量(kg)', 0)
            elif '周运输量(m³)' in row:
                volume = row.get('周运输量(m³)', 0)
            elif '日运输量(kg)' in row:
                volume = row.get('日运输量(kg)', 0)
            elif '日运输量(m³)' in row:
                volume = row.get('日运输量(m³)', 0)

            # 如果运输量为0或NaN，跳过这条记录
            if volume == 0 or pd.isna(volume):
                filtered_rows += 1
                continue

            start_name = row.get('起点', '')
            end_name = row.get('终点', '')
            start_type = str(row.get('起点类型', '')).strip()
            end_type = str(row.get('终点类型', '')).strip()
            cargo_type = row.get('货物类型', '')

            start_lat, start_lon = parse_coord(row.get('起点坐标'))
            end_lat, end_lon = parse_coord(row.get('终点坐标'))

            # 收集起点：使用纯坐标作为key
            # 【关键】只收集作为起点时发出的货物，用于判断该设施是否生产该原材料
            if start_lat is not None and start_lon is not None and start_name:
                coord_key = (start_lon, start_lat)

                if coord_key not in facility_info:
                    facility_info[coord_key] = {'names': set(), 'types': set(), 'cargos_as_source': set(), 'cargos_as_dest': set()}

                facility_info[coord_key]['names'].add(start_name)
                if start_type:
                    facility_info[coord_key]['types'].add(start_type)
                # 只有作为起点发出的货物才记录到cargos_as_source（用于判断原材料生产能力）
                if cargo_type:
                    facility_info[coord_key]['cargos_as_source'].add(cargo_type)

            # 收集终点：使用纯坐标作为key
            if end_lat is not None and end_lon is not None and end_name:
                coord_key = (end_lon, end_lat)

                if coord_key not in facility_info:
                    facility_info[coord_key] = {'names': set(), 'types': set(), 'cargos_as_source': set(), 'cargos_as_dest': set()}

                facility_info[coord_key]['names'].add(end_name)
                if end_type:
                    facility_info[coord_key]['types'].add(end_type)
                # 记录作为终点接收的货物（用于判断是否为消纳地）
                if cargo_type:
                    facility_info[coord_key]['cargos_as_dest'].add(cargo_type)

        logger.info(f"    运输记录总数: {total_rows}, 过滤掉运输量为0的记录: {filtered_rows} 条")
        logger.info(f"    收集到的唯一坐标位置数: {len(facility_info)}")

        # 【特殊处理】天然气两步法：过滤掉SAF产量≤10kg的设施
        if module_name == 'Natural Gas Two-Step' and facility_saf_production:
            filtered_facility_info = {}
            filtered_count = 0
            for coord, info in facility_info.items():
                # 检查这个坐标的SAF产量
                # 需要将coord转回字符串格式来查找
                coord_str = f"({coord[1]}, {coord[0]})"  # (lat, lon)
                saf_volume = facility_saf_production.get(coord_str, 0)

                # 只保留SAF产量>10kg的设施，或者不生产SAF的设施（如原材料供应点）
                if saf_volume > 10 or 'MTJ' not in info['cargos_as_source']:
                    filtered_facility_info[coord] = info
                else:
                    filtered_count += 1

            logger.info(f"    天然气两步法筛选：过滤掉SAF产量≤10kg的设施 {filtered_count} 个")
            logger.info(f"    保留的设施数: {len(filtered_facility_info)}")
            facility_info = filtered_facility_info

        # 【调试日志】报告同一坐标有多个名称的情况
        multi_name_coords = {coord: info['names'] for coord, info in facility_info.items() if len(info['names']) > 1}
        if multi_name_coords:
            logger.info(f"    发现 {len(multi_name_coords)} 个坐标有多个名称（这是正常的，将合并为一个点）：")
            for coord, names in list(multi_name_coords.items())[:3]:  # 只显示前3个
                logger.info(f"      坐标 {coord}: {names}")

        if len(facility_info) == 0:
            logger.warning("    未收集到任何设施，检查坐标解析和数据格式")
            logger.info("    运输汇总数据前5行:")
            logger.info(f"\n{transport_summary.head().to_string()}")
            return {}

        # 第二步: 对每个坐标位置进行三维分类
        facility_classifications = {}  # {(lon, lat): (raw_materials_frozenset, saf_production, consumption)}

        for (lon, lat), info in facility_info.items():
            # 使用所有名称中的第一个作为代表名称（仅用于分类判断）
            representative_name = list(info['names'])[0] if info['names'] else ''

            # 【关键修正】只传入作为起点发出的货物类型，用于判断原材料生产能力
            raw_materials, saf_production, consumption = self.classify_facility(
                representative_name, info['types'], info['cargos_as_source']
            )

            facility_classifications[(lon, lat)] = (raw_materials, saf_production, consumption)

            # 调试输出：显示多角色设施
            if len(raw_materials) > 1:
                names_str = ', '.join(list(info['names'])[:3])  # 最多显示3个名称
                logger.info(f"    多角色设施 ({lon:.4f}, {lat:.4f}) [{names_str}] -> {raw_materials}")

            # 【新增】调试输出：检查消纳地是否被误判为生产设施
            if consumption == 'yes' and len(raw_materials) > 0:
                names_str = ', '.join(list(info['names'])[:3])
                logger.info(f"    消纳地同时生产原材料 ({lon:.4f}, {lat:.4f}) [{names_str}]: "
                          f"发出={info['cargos_as_source']}, 接收={info['cargos_as_dest']}, "
                          f"原材料={raw_materials}")

        # 第三步: 绘制设施（每个地理位置只绘制一个点）
        logger.info(f"    设施三维张量分类统计：")

        total_facilities_plotted = 0

        # 用于统计分类组合（用于图例）
        classification_stats = {}

        for (lon, lat), (raw_materials, saf_production, consumption) in facility_classifications.items():
            # 获取可视化属性列表（多角色返回多个标记描述）
            markers = self.get_facility_visualization_attrs(raw_materials, saf_production, consumption)

            # 【关键】每个地理位置只绘制一个点
            # 策略：如果有多角色，使用第一个标记的属性，但增加尺寸表示复杂性
            primary_marker = markers[0]
            num_roles = len(raw_materials) if raw_materials else 1

            # 多角色设施使用更大的标记尺寸
            marker_size = primary_marker['size'] * (1 + 0.3 * (num_roles - 1))

            # 绘制单一标记（精确坐标，无偏移）
            ax.scatter(
                lon, lat,  # 精确坐标，不使用offset
                marker=primary_marker['marker'],
                c=primary_marker['color'],
                s=marker_size,
                alpha=0.9,
                edgecolors=primary_marker['edgecolor'],
                linewidth=primary_marker['linewidth'],
                transform=self.data_crs,
                zorder=30
            )

            total_facilities_plotted += 1

            # 统计分类（对于多角色设施，统计组合分类）
            if len(markers) > 1:
                # 多角色设施：生成组合标签
                material_labels = [m['raw_material_label'] for m in markers]
                combined_material_label = '+'.join(sorted(material_labels))
                classification_key = (combined_material_label, saf_production, consumption)

                # 记录组合标记属性
                combined_attrs = primary_marker.copy()
                combined_attrs['raw_material_label'] = combined_material_label
                combined_attrs['size'] = marker_size
                combined_attrs['full_label'] = f"{combined_material_label} × {primary_marker['saf_production_label']} × {primary_marker['consumption_label']}"

                if classification_key not in classification_stats:
                    classification_stats[classification_key] = {
                        'count': 0,
                        'attrs': combined_attrs
                    }
                classification_stats[classification_key]['count'] += 1

                logger.info(f"    多角色设施 ({lon:.4f}, {lat:.4f}) -> {sorted(raw_materials)}")
            else:
                # 单角色设施
                material_label = primary_marker['raw_material_label']
                classification_key = (material_label, saf_production, consumption)
                if classification_key not in classification_stats:
                    classification_stats[classification_key] = {
                        'count': 0,
                        'attrs': primary_marker
                    }
                classification_stats[classification_key]['count'] += 1

        logger.info(f"    总共绘制设施数（唯一坐标位置）: {total_facilities_plotted}")
        logger.info(f"    设施三维张量分类统计（共{len(classification_stats)}种组合）：")
        for (material, saf, cons), stats in sorted(classification_stats.items()):
            logger.info(f"      [{material} × {saf} × {cons}] {stats['count']}个设施")

        return classification_stats

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

        # 【特殊处理】天然气一步法：只画机场，不读取其他设施数据
        if module_name == 'Natural Gas One-Step':
            logger.info(f"  天然气一步法场景：只绘制机场（生产地在机场）")
            # 只绘制管道网络和机场
            logger.info(f"  绘制管道网络...")
            pipeline_stats = self.plot_pipeline_networks(ax)

            # 只绘制机场设施（从transport_summary中提取机场位置）
            facility_classification = self.plot_facilities(ax, data['transport_summary'], module_name)
        else:
            # 其他场景的正常处理流程
            # 先绘制管道网络（作为底层）
            logger.info(f"  绘制管道网络...")
            pipeline_stats = self.plot_pipeline_networks(ax)

            # 绘制H2聚类运输路线（如果有H2聚类数据）
            if data['h2_clustering']:
                self.plot_h2_clustered_routes(ax, data['h2_clustering'], data['transport_summary'], module_name)

            # 绘制天然气聚类运输路线（如果有天然气聚类数据）
            if data['ng_clustering']:
                self.plot_ng_clustered_routes(ax, data['ng_clustering'], data['transport_summary'], module_name)
            else:
                # 如果没有天然气聚类，绘制普通天然气运输路线
                self.plot_ng_routes(ax, data['transport_summary'])

            # 绘制SAF运输路线
            self.plot_saf_routes(ax, data['transport_summary'])

            # 绘制设施位置并获取分类统计
            facility_classification = self.plot_facilities(ax, data['transport_summary'], module_name)

        # 添加装饰元素
        self.add_decorations(ax)

        # 添加图例（分三部分：路线、设施三维分类矩阵、管道网络）
        legend_elements = [
            # === 路线图例 ===
            Line2D([0], [0], color='gray', linewidth=2, linestyle=':',
                   label='H₂ Layer1/2 (源点→聚类→管道)'),
            Line2D([0], [0], marker='P', color='w', markerfacecolor='purple',
                   markersize=12, markeredgecolor='black', markeredgewidth=1.5,
                   label='H₂聚类中心 Cluster Center'),
            Line2D([0], [0], color=self.transport_colors['NG'], linewidth=2.5,
                   label='天然气运输 NG Transport'),
            Line2D([0], [0], color=self.transport_colors['SAF'], linewidth=2.5,
                   label='SAF卡车运输 Truck Transport'),
        ]

        # === 设施三维张量分类矩阵图例 ===
        legend_elements.append(Line2D([0], [0], marker='', color='w', label=''))  # 空行
        legend_elements.append(Line2D([0], [0], marker='', color='w',
                                     label='【设施三维张量分类】', markerfacecolor='w'))
        legend_elements.append(Line2D([0], [0], marker='', color='w',
                                     label='原材料类型×SAF生产×消纳地', markerfacecolor='w'))

        # 定义三维张量的基础组合（单一原材料类型）
        # 维度1: H₂生产, CO₂捕获, 天然气供应, 无原材料生产
        # 维度2: yes, no
        # 维度3: yes, no
        base_material_labels = ['H₂生产', 'CO₂捕获', '天然气供应', '无原材料生产']
        saf_options = ['yes', 'no']
        consumption_options = ['yes', 'no']

        # 只添加实际存在的组合到图例
        for (material_label, saf_production, consumption), stats in sorted(facility_classification.items()):
            count = stats['count']
            attrs = stats['attrs']

            if count > 0:
                # 使用attrs中的full_label或组合标签
                if 'combined_label' in attrs:
                    label = f"{attrs['combined_label']} ({count})"
                else:
                    label = f"{attrs['full_label']} ({count})"

                legend_elements.append(
                    Line2D([0], [0], marker=attrs['marker'], color='w',
                          markerfacecolor=attrs['color'],
                          markersize=10,
                          markeredgecolor=attrs['edgecolor'],
                          markeredgewidth=attrs['linewidth'],
                          label=label)
                )

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

        # 将图例放到图外右侧
        ax.legend(handles=legend_elements, loc='center left', bbox_to_anchor=(1.02, 0.5),
                 fontsize=8, framealpha=0.95, ncol=1, borderpad=1, labelspacing=0.5)

        # 添加标题
        h2_clusters = data['h2_clustering']['total_clusters'] if data['h2_clustering'] else 0
        ng_clusters = data['ng_clustering']['total_clusters'] if data['ng_clustering'] else 0

        # 统计SAF路线数量
        saf_routes = 0
        if data['transport_summary'] is not None:
            saf_routes = len(data['transport_summary'][data['transport_summary']['货物类型'] == 'MTJ'])

        total_pipelines = sum(pipeline_stats.values())

        # 根据场景类型生成不同的标题
        if ng_clusters > 0:
            # 天然气一步法场景
            title = (f"{config['name_cn']} SAF供应链聚类运输网络（天然气聚类）\n"
                    f"{module_name} SAF Supply Chain Clustered Transport Network (NG Clustering)\n"
                    f"天然气聚类: {ng_clusters} 个 | SAF路线: {saf_routes} 条 | 管道: {total_pipelines} 段")
        elif h2_clusters > 0:
            # 氢气两步法场景
            title = (f"{config['name_cn']} SAF供应链聚类运输网络（两层结构）\n"
                    f"{module_name} SAF Supply Chain Clustered Transport Network (Two Layers)\n"
                    f"H₂聚类: {h2_clusters} 个 | SAF路线: {saf_routes} 条 | 管道: {total_pipelines} 段")
        else:
            # 其他场景
            title = (f"{config['name_cn']} SAF供应链运输网络\n"
                    f"{module_name} SAF Supply Chain Transport Network\n"
                    f"SAF路线: {saf_routes} 条 | 管道: {total_pipelines} 段")

        ax.set_title(title, fontsize=14, fontweight='bold', pad=20)

        # 调整布局以容纳外部图例
        plt.tight_layout(rect=[0, 0, 0.85, 1])  # 为右侧图例留出空间

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
    logger.info("五场景聚类运输路线地图可视化脚本")
    logger.info("Five Scenarios Clustered Transport Route Map Visualization Script")
    logger.info("=" * 60)

    try:
        # 创建可视化器
        visualizer = FiveScenariosClusteredMapVisualizer()

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
