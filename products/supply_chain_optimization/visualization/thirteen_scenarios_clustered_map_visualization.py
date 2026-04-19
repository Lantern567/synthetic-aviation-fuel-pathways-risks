"""
十三场景聚类运输路线地图可视化（包含聚类和管道接入点）
Thirteen Scenarios Clustered Transport Route Map Visualization (with clustering and pipeline access points)

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
7. 十三场景对比地图 (Thirteen scenarios comparison maps)

支持场景 | Supported Scenarios:

绿氢场景 (Green Hydrogen Scenarios):
1. 煤制氢 (Coal Hydrogen)
2. DAC制氢两步法 (DAC Hydrogen Two-Step)
3. DAC制氢一步法 (DAC Hydrogen One-Step)
4. 天然气两步法 (Natural Gas Two-Step)
5. 天然气一步法 (Natural Gas One-Step)
6. 绿氢+工业捕获CO₂两步法 (Green H2 + Industrial CO2 Two-Step)
7. 绿氢+工业捕获CO₂一步法 (Green H2 + Industrial CO2 One-Step)

副产氢场景 (Byproduct Hydrogen Scenarios):
8. 副产氢+煤制氢 (Byproduct H2 + Coal)
9. 副产氢+DAC两步法 (Byproduct H2 + DAC Two-Step)
10. 副产氢+DAC一步法 (Byproduct H2 + DAC One-Step)
11. 副产氢+天然气两步法 (Byproduct H2 + NG Two-Step)
12. 副产氢+工业CO₂两步法 (Byproduct H2 Two-Step)
13. 副产氢+工业CO₂一步法 (Byproduct H2 One-Step)

注意 | Note:
- 天然气一步法不包含副产氢场景，因为一步法不需要外部氢气
- Natural Gas One-Step does not have a byproduct hydrogen scenario because it does not require external hydrogen

作者 | Author: Claude Code
创建时间 | Created: 2025-11-06
最后更新 | Last Updated: 2025-11-23
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

# 全局视觉缩放：按需求将字体和指北针统一放大一倍
FONT_SCALE = 2.0
NORTH_ARROW_SCALE = 2.0
OUTPUT_DPI = 1200

# 配置科学期刊风格字体 (Applied Energy Standard)
# 优先使用 Helvetica/Arial (无衬线), 备选 Times New Roman (虽然是衬线，但图表常用)

# ===== 使用 Times New Roman =====
matplotlib.rcParams['font.family'] = 'serif'
matplotlib.rcParams['font.serif'] = ['Times New Roman']
matplotlib.rcParams['mathtext.fontset'] = 'stix'   # 数学公式风格接近TNR
matplotlib.rcParams['axes.unicode_minus'] = False
matplotlib.rcParams['xtick.direction'] = 'in'
matplotlib.rcParams['ytick.direction'] = 'in'
matplotlib.rcParams['font.size'] = 10 * FONT_SCALE
matplotlib.rcParams['xtick.labelsize'] = 20 * FONT_SCALE
matplotlib.rcParams['ytick.labelsize'] = 20 * FONT_SCALE
matplotlib.rcParams['axes.labelsize'] = 18 * FONT_SCALE
matplotlib.rcParams['axes.titlesize'] = 22 * FONT_SCALE
matplotlib.rcParams['legend.fontsize'] = 8 * FONT_SCALE

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

# 添加管道计算器路径（需要在logger定义之后）
# 添加src目录到路径，这样cache.xxx和hydrogen.xxx都能找到
sys.path.insert(0, str(Path(__file__).parent.parent / "coal_hydrogen_saf_optimization" / "src"))
try:
    from hydrogen.hydrogen_pipeline_distance_calculator import HydrogenPipelineDistanceCalculator
    PIPELINE_CALCULATOR_AVAILABLE = True
except ImportError as e:
    PIPELINE_CALCULATOR_AVAILABLE = False
    logger.warning(f"管道计算器导入失败，CO2路径将使用直线可视化: {e}")



from matplotlib.path import Path as MplPath
import matplotlib.patches as patches

# SVG图标解析库
try:
    from svgpath2mpl import parse_path as svg_parse_path
    SVG_PARSER_AVAILABLE = True
except ImportError:
    SVG_PARSER_AVAILABLE = False
    logger.warning("svgpath2mpl 未安装，将使用备用图标。请运行: pip install svgpath2mpl")

class CustomMarkers:
    """自定义SVG路径标记集合 - 使用专业SVG图标（Material Design / Font Awesome）"""

    # SVG 图标路径定义（来自 Material Design Icons）
    _SVG_AIRPLANE = "M21 16v-2l-8-5V3.5c0-.83-.67-1.5-1.5-1.5S10 2.67 10 3.5V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5l8 2.5z"
    _SVG_FACTORY = "M18.5 12.5V6H17v6.5l-5 2.5V9h-1.5v6l-5-2.5V6H4v6.5L2 14v8h20v-8l-3.5-1.5z"
    _SVG_FLAME = "M13.5.67s.74 2.65.74 4.8c0 2.06-1.35 3.73-3.41 3.73-2.07 0-3.63-1.67-3.63-3.73l.03-.36C5.21 7.51 4 10.62 4 14c0 4.42 3.58 8 8 8s8-3.58 8-8C20 8.61 17.41 3.8 13.5.67zM11.71 19c-1.78 0-3.22-1.4-3.22-3.14 0-1.62 1.05-2.76 2.81-3.12 1.77-.36 3.6-1.21 4.62-2.58.39 1.29.59 2.65.59 4.04 0 2.65-2.15 4.8-4.8 4.8z"
    _SVG_H2 = "M12 2c-5.33 4.55-8 8.48-8 11.8 0 4.98 3.8 8.2 8 8.2s8-3.22 8-8.2c0-3.32-2.67-7.25-8-11.8z"
    _SVG_CLOUD = "M19.35 10.04C18.67 6.59 15.64 4 12 4 9.11 4 6.6 5.64 5.35 8.04 2.34 8.36 0 10.91 0 14c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5 0-2.64-2.05-4.78-4.65-4.96z"
    _SVG_STAR = "M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z"

    @staticmethod
    def _svg_to_marker(svg_path_str, flip_y=True):
        """将 SVG 路径字符串转换为 matplotlib marker"""
        import numpy as np
        if not SVG_PARSER_AVAILABLE:
            return None
        try:
            marker = svg_parse_path(svg_path_str)
            # 居中
            marker.vertices -= marker.vertices.mean(axis=0)
            # 归一化到 [-1, 1]
            max_val = np.abs(marker.vertices).max()
            if max_val > 0:
                marker.vertices /= max_val
            # 翻转 Y 轴（SVG 坐标系 Y 轴向下）
            if flip_y:
                marker.vertices[:, 1] *= -1
            return marker
        except Exception as e:
            logger.warning(f"SVG解析错误: {e}")
            return None

    @staticmethod
    def _fallback_airplane():
        """备用飞机图标（简单多边形）"""
        verts = [
            (0.0, 1.0), (0.15, 0.5), (1.0, 0.1), (0.15, -0.1),
            (0.15, -0.5), (0.5, -0.9), (0.1, -0.6), (0.0, -1.0),
            (-0.1, -0.6), (-0.5, -0.9), (-0.15, -0.5), (-0.15, -0.1),
            (-1.0, 0.1), (-0.15, 0.5), (0.0, 1.0)
        ]
        codes = [MplPath.MOVETO] + [MplPath.LINETO] * 13 + [MplPath.CLOSEPOLY]
        return MplPath(verts, codes)

    @staticmethod
    def _fallback_factory():
        """备用工厂图标（简单多边形）"""
        verts = [
            (-0.9, -0.9), (0.9, -0.9), (0.9, -0.3), (0.5, -0.3), (0.5, 0.5),
            (0.1, -0.3), (0.1, 0.7), (-0.3, -0.3), (-0.3, 0.3), (-0.7, -0.3),
            (-0.9, -0.3), (-0.9, -0.9)
        ]
        codes = [MplPath.MOVETO] + [MplPath.LINETO] * 10 + [MplPath.CLOSEPOLY]
        return MplPath(verts, codes)

    @staticmethod
    def _fallback_simple():
        """备用简单圆形"""
        return MplPath.unit_circle()

    @staticmethod
    def airplane():
        """飞机图标 (Consumption/Airport) - Material Design 风格"""
        marker = CustomMarkers._svg_to_marker(CustomMarkers._SVG_AIRPLANE)
        return marker if marker is not None else CustomMarkers._fallback_airplane()

    @staticmethod
    def factory():
        """工厂图标 (SAF Production) - Material Design 风格，带烟囱"""
        marker = CustomMarkers._svg_to_marker(CustomMarkers._SVG_FACTORY)
        return marker if marker is not None else CustomMarkers._fallback_factory()

    @staticmethod
    def flame():
        """火焰图标 (Natural Gas) - Material Design 风格"""
        marker = CustomMarkers._svg_to_marker(CustomMarkers._SVG_FLAME)
        return marker if marker is not None else CustomMarkers._fallback_simple()

    @staticmethod
    def h2_icon():
        """H2图标 (Hydrogen) - 同心圆原子结构"""
        marker = CustomMarkers._svg_to_marker(CustomMarkers._SVG_H2)
        return marker if marker is not None else CustomMarkers._fallback_simple()

    @staticmethod
    def co2_cloud():
        """CO2云图标 - Material Design 云朵"""
        marker = CustomMarkers._svg_to_marker(CustomMarkers._SVG_CLOUD)
        return marker if marker is not None else CustomMarkers._fallback_simple()

    @staticmethod
    def star_hub():
        """聚类中心星形 - Material Design 五角星"""
        marker = CustomMarkers._svg_to_marker(CustomMarkers._SVG_STAR)
        if marker is not None:
            return marker
        # 备用：使用内置五角星
        return MplPath.unit_regular_star(5)


class ThirteenScenariosClusteredMapVisualizer:
    """十三场景聚类运输路线地图可视化器"""

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
        self.session_dir = self.output_dir / f"clustered_transport_maps_13scenarios_{timestamp}"
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

        # 初始化管道计算器（用于获取CO2管道路径坐标）
        self.pipeline_calculator = None
        if PIPELINE_CALCULATOR_AVAILABLE:
            try:
                # 获取管道数据路径（使用GIS数据目录）
                project_root = Path(__file__).parent.parent.parent.parent
                pipeline_data_dir = project_root / "products" / "gis_energy_mapping" / "gis_data_scraper" / "scraped_gis_data"
                self.pipeline_calculator = HydrogenPipelineDistanceCalculator(
                    gis_data_path=str(pipeline_data_dir),
                    mixed_link_distance_km=20.0,
                    max_bridge_distance_km=10.0
                )
                self.pipeline_calculator.load_pipeline_data()
                logger.info("✓ 管道计算器初始化成功")
            except Exception as e:
                logger.warning(f"管道计算器初始化失败: {e}，CO2路径将使用直线可视化")
                self.pipeline_calculator = None

        # 管道路径缓存（避免重复计算）
        self.pipeline_route_cache = {}

        # 过滤阈值：非聚类H2路线最低周运输量（kg）
        # 用于去掉非常小或噪声路线
        self.min_h2_noncluster_weekly_kg = 1000

        # 严格匹配模式：只显示“有线路连接”的设施点
        # 说明：会先收集线路端点，再仅绘制这些端点对应的设施
        self.strict_match_mode = True
        self.collect_only = False
        self.route_endpoint_coords = set()
        self.strict_match_coord_keys = None
        # 严格匹配模式的例外：机场有生产时也显示（即便无运输线路）
        self.strict_match_keep_airport_production = True

        # 统一范围模式：所有场景使用同一地图范围（取最大边界）
        self.uniform_extent_mode = True
        self.uniform_extent = None
        # 自动收缩地图范围（仅保留点和线）
        self.tight_extent_mode = False
        self.drawn_bounds = None
        self.ignore_extent_filter = False

        # 单独图例输出（每个图不再显示图例）
        self.render_individual_legends = False
        self.global_facility_legend = {}
        self.global_route_legend = {
            'h2': False,
            'co2': False,
            'ng': False,
            'saf': False
        }
        self.global_pipeline_legend = {
            'crude': False,
            'refined': False,
            'natural_gas': False
        }

        # 模块配置 - 使用自动查找最新文件
        # 获取项目根目录
        project_root = Path(__file__).parent.parent.parent.parent

        self.modules = {
            'Coal Hydrogen': {
                'name_cn': '煤制氢',
                'color': '#E74C3C',
                'h2_clustering_file': str(project_root / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/clustering_results.json'),
                'co2_clustering_file': None,  # v3.0煤炭气化路线不需要CO2运输
                'ng_clustering_file': None,
                'transport_summary_pattern': str(project_root / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/transport_summary_*.csv'),
                'complete_solution_pattern': str(project_root / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/complete_solution_*.json')
            },
            'DAC Two-Step': {
                'name_cn': 'DAC制氢两步法',
                'color': '#3498DB',
                'h2_clustering_file': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/clustering_results.json'),
                'co2_clustering_file': None,  # DAC从空气中捕获CO2，无需CO2运输
                'ng_clustering_file': None,
                'transport_summary_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/two_step/transport_summary_*.csv'),
                'complete_solution_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/two_step/complete_solution_*.json')
            },
            'DAC One-Step': {
                'name_cn': 'DAC制氢一步法',
                'color': '#5DADE2',
                'h2_clustering_file': None,  # 一步法不需要氢气聚类
                'co2_clustering_file': None,  # DAC从空气中捕获CO2，无需CO2运输
                'ng_clustering_file': None,
                'transport_summary_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/one_step/transport_summary_*.csv'),
                'complete_solution_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/one_step/complete_solution_*.json')
            },
            'Natural Gas Two-Step': {
                'name_cn': '天然气两步法',
                'color': '#2ECC71',
                'h2_clustering_file': str(project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/clustering_results.json'),
                'co2_clustering_file': None,  # 天然气制氢过程中CO2作为副产物，无独立运输
                'ng_clustering_file': None,
                'transport_summary_pattern': str(project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/transport_summary_*.csv'),
                'complete_solution_pattern': str(project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/complete_solution_*.json')
            },
            'Natural Gas One-Step': {
                'name_cn': '天然气一步法',
                'color': '#F39C12',
                'h2_clustering_file': None,  # 一步法不需要氢气聚类
                'co2_clustering_file': None,
                'ng_clustering_file': None,  # 一步法目前没有天然气聚类文件
                # 一步法的transport_summary保存在results/ft_one_step/子目录
                'transport_summary_pattern': str(project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/ft_one_step/transport_summary_*.csv'),
                'complete_solution_pattern': str(project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/ft_one_step/complete_solution_*.json')
            },
            'Green H2 Two-Step': {
                'name_cn': '绿氢两步法',
                'color': '#9B59B6',
                'h2_clustering_file': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/clustering_results.json'),
                'co2_clustering_file': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/co2_clustering_results.json'),
                'ng_clustering_file': None,
                'transport_summary_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/two_step/transport_summary_*.csv'),
                'complete_solution_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/two_step/complete_solution_*.json')
            },
            'Green H2 One-Step': {
                'name_cn': '绿氢一步法',
                'color': '#C39BD3',
                'h2_clustering_file': None,  # 一步法不需要氢气聚类
                'co2_clustering_file': None,  # 一步法不需要CO2聚类
                'ng_clustering_file': None,
                'transport_summary_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/one_step/transport_summary_*.csv'),
                'complete_solution_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/one_step/complete_solution_*.json')
            },

            # ========== 副产氢场景 (6个) ==========
            # 注意：天然气一步法不包含副产氢场景（一步法不需要外部氢气）
            'Byproduct H2 + Coal': {
                'name_cn': '副产氢+煤',
                'color': '#FF6B6B',
                'h2_clustering_file': str(project_root / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/byproduct_clustering_results.json'),
                'co2_clustering_file': None,  # v3.0煤炭气化路线不需要CO2运输
                'ng_clustering_file': None,
                'transport_summary_pattern': str(project_root / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/byproduct_hydrogen/transport_summary_*.csv'),
                'complete_solution_pattern': str(project_root / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/byproduct_hydrogen/complete_solution_*.json')
            },
            'Byproduct H2 + DAC Two-Step': {
                'name_cn': '副产氢+DAC两步',
                'color': '#4ECDC4',
                'h2_clustering_file': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/byproduct_clustering_results.json'),
                'co2_clustering_file': None,  # DAC从空气中捕获CO2
                'ng_clustering_file': None,
                'transport_summary_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/two_step/transport_summary_*.csv'),
                'complete_solution_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/two_step/complete_solution_*.json')
            },
            'Byproduct H2 + DAC One-Step': {
                'name_cn': '副产氢+DAC一步',
                'color': '#95E1D3',
                'h2_clustering_file': None,  # 一步法不需要氢气聚类
                'co2_clustering_file': None,  # DAC从空气中捕获CO2
                'ng_clustering_file': None,
                'transport_summary_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/one_step/transport_summary_*.csv'),
                'complete_solution_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/one_step/complete_solution_*.json')
            },
            'Byproduct H2 + NG Two-Step': {
                'name_cn': '副产氢+天然气两步',
                'color': '#26DE81',
                'h2_clustering_file': str(project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/byproduct_clustering_results.json'),
                'co2_clustering_file': None,
                'ng_clustering_file': None,
                'transport_summary_pattern': str(project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/byproduct_hydrogen/byproduct_hydrogen/two_step/transport_summary_*.csv'),
                'complete_solution_pattern': str(project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/byproduct_hydrogen/byproduct_hydrogen/two_step/complete_solution_*.json')
            },
            'Byproduct H2 Two-Step': {
                'name_cn': '副产氢两步法',
                'color': '#A29BFE',
                'h2_clustering_file': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/byproduct_clustering_results.json'),  # 修复：使用副产氢专用聚类文件
                'co2_clustering_file': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/co2_clustering_results.json'),
                'ng_clustering_file': None,
                'transport_summary_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/two_step/transport_summary_*.csv'),
                'complete_solution_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/two_step/complete_solution_*.json')
            },
            'Byproduct H2 One-Step': {
                'name_cn': '副产氢一步法',
                'color': '#DFE4EA',
                'h2_clustering_file': None,  # 一步法不需要氢气聚类
                'co2_clustering_file': None,
                'ng_clustering_file': None,
                'transport_summary_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/one_step/transport_summary_*.csv'),
                'complete_solution_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/one_step/complete_solution_*.json')
            }
        }

        # 地图投影设置
        self.map_crs = fplt.CN_AZIMUTHAL_EQUIDISTANT
        self.data_crs = fplt.PLATE_CARREE

        # 运输类型颜色 - SCI期刊配色方案 (Nature/Applied Energy Style)
        # 使用更深沉、对比度更高的专业配色，避免高饱和度霓虹色
        self.transport_colors = {
            'H2': '#0072B2',          # 氢气 - 深蓝 (Blue)
            'H2_cluster': '#56B4E9',  # 氢气聚类 - 天蓝 (Sky Blue)
            'CO2': '#663300',         # CO2 - 深褐 (Dark Brown)
            'CO2_cluster': '#A6761D', # CO2聚类 - 赭石 (Ocher)
            'SAF': '#D55E00',         # SAF - 朱红 (Vermilion) - 突出显示
            'NG': '#009E73',          # 天然气 - 青绿 (Bluish Green)
            'Route_Alpha': 0.7,       # 路线透明度
            'Route_Width_Main': 1.5,  # 主干路线宽
            'Route_Width_Feeder': 0.8 # 支线路线宽
        }

        # 聚类颜色方案 - 使用Set2/Pastel等更柔和的色盘，或者Tableau 10
        self.cluster_colors = plt.cm.tab20.colors

        # 数据存储
        self.clustering_data = {}
        self.transport_data = {}
        # 可视化过滤：已绘制设施坐标集合
        self.visible_facility_coords = None

    def load_data(self):
        """加载十三个场景的聚类数据和运输数据"""
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
                'transport_summary': None,
                'complete_solution': None  # 新增：完整解决方案数据（包含设施决策）
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

                # 【新增】加载完整解决方案数据（包含设施决策）
                if 'complete_solution_pattern' in config:
                    solution_pattern = config['complete_solution_pattern']
                    solution_files = sorted(glob.glob(solution_pattern), reverse=True)

                    if solution_files:
                        solution_file = Path(solution_files[0])
                        logger.info(f"  使用最新的完整解决方案文件: {solution_file.name}")
                        with open(solution_file, 'r', encoding='utf-8') as f:
                            module_data['complete_solution'] = json.load(f)

                        # 统计设施决策信息
                        facilities = module_data['complete_solution'].get('facilities', {})
                        if facilities:
                            built_facilities = sum(1 for f in facilities.values() if f.get('built', False))
                            total_production = sum(f.get('actual_annual_production_kg', 0) for f in facilities.values() if f.get('built', False))
                            logger.info(f"  ✓ 设施决策数据: {built_facilities} 个已建设设施, 总产量 {total_production/1e6:.2f} 百万kg/年")

                            # 统计机场建设的设施（用于后续可视化）
                            airport_facilities = [f for f in facilities.values()
                                                if f.get('built', False) and
                                                (f.get('location_type', '').startswith('airport') or
                                                 'airport' in f.get('source_type', '').lower())]
                            if airport_facilities:
                                logger.info(f"    - 其中机场SAF工厂: {len(airport_facilities)} 个")
                    else:
                        logger.info(f"  - 未找到完整解决方案文件（不影响基本可视化）")

                self.transport_data[module_name] = module_data

            except Exception as e:
                logger.error(f"  ✗ 加载失败: {e}")
                import traceback
                traceback.print_exc()
                # 不抛出异常，继续加载其他场景
                continue

        logger.info("\n" + "=" * 60)
        logger.info(f"数据加载完成 - 成功加载 {len(self.transport_data)} 个场景")
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
        def _integer_ticks(min_val, max_val):
            span = max_val - min_val
            if span <= 6:
                step = 1
            elif span <= 12:
                step = 2
            else:
                step = 4
            tick_min = int(np.floor(min_val))
            tick_max = int(np.ceil(max_val))
            return np.arange(tick_min, tick_max + 1, step)

        fig = plt.figure(figsize=figsize)
        ax = fig.add_subplot(projection=self.map_crs)

        # 设置地图范围 - 京津冀及周边地区（全覆盖端点/设施）
        if extent is None:
            extent = [112.0, 119.0, 37.5, 41.7]

        min_lon, max_lon, min_lat, max_lat = extent
        # 记录当前可视范围，用于过滤路线/点
        self.current_extent = (min_lon, max_lon, min_lat, max_lat)

        # 设置刻度
        xticks = _integer_ticks(min_lon, max_lon)
        yticks = _integer_ticks(min_lat, max_lat)

        fplt.set_map_ticks(ax, (min_lon, max_lon, min_lat, max_lat), xticks, yticks)
        
        # 优化网格线 - 灰色虚线，更细更淡
        ax.gridlines(xlocs=xticks, ylocs=yticks, lw=0.5, ls=":", color="#B0B0B0", alpha=0.4)

        # 设置刻度样式
        ax.tick_params(
            length=8, width=1.2, labelsize=20 * FONT_SCALE,
            top=True, right=True, labeltop=False, labelright=False,  # 只在左下显示标签，符合期刊习惯
            direction='in'
        )

        # 添加地图要素 - 期刊风格：极简、高对比
        # 陆地使用纯白或极淡灰，海洋使用极淡蓝
        ax.set_facecolor("#F0F8FF")  # AliceBlue 极淡蓝
        from cartopy.feature import LAND, OCEAN, BORDERS
        
        # 陆地颜色
        ax.add_feature(LAND, fc="#FFFFFF", ec="#808080", lw=0.3, zorder=0)

        # 使用frykit添加中国地图底图
        # 省界：深灰，细线
        fplt.add_cn_city(ax, lw=0.2, edgecolor='#D3D3D3', linestyle='-', zorder=1) # 市界极淡
        fplt.add_cn_province(ax, lw=0.6, edgecolor='#606060', zorder=1.5) # 省界加深
        fplt.add_cn_line(ax, lw=1.0, edgecolor='#000000', zorder=2.5) # 九段线/国界
        
        return fig, ax

    def add_decorations(self, ax):
        """添加指北针和比例尺"""
        try:
            fplt.add_compass(ax, 0.92, 0.85, size=36 * NORTH_ARROW_SCALE, style="star")
            scale_bar = fplt.add_scale_bar(ax, 0.05, 0.95, length=400)
            scale_bar.set_xticks([0, 200, 400])
            scale_bar.xaxis.get_label().set_fontsize(16 * FONT_SCALE)
            scale_bar.tick_params(labelsize=16 * FONT_SCALE)
        except Exception as e:
            logger.warning(f"无法添加装饰元素: {e}")

    def _format_legend_label(self, attrs: Dict) -> str:
        """格式化图例标签（不含数量）"""
        if 'combined_label' in attrs:
            label = attrs['combined_label']
        else:
            label = attrs.get('full_label', '')

        formal_label = label \
            .replace('H2 Production', 'Hydrogen Production') \
            .replace('CO2 Capture', 'Carbon Dioxide Capture') \
            .replace('Natural Gas Supply', 'Natural Gas Supply') \
            .replace('No Raw Material', 'No Raw Material Production') \
            .replace('SAF Plant', 'SAF Production Facility') \
            .replace('SAF Production', 'SAF Production') \
            .replace('No SAF Production', 'No SAF Production') \
            .replace('Consumer', 'Consumption Site') \
            .replace('Non-Consumer', 'Non-Consumption Site') \
            .replace('Airport/Consumer', 'Airport (Consumption Site)') \
            .replace('Standard Node', 'General Node')

        return formal_label

    def create_global_legend(self):
        """生成综合十三场景的单独图例图"""
        route_handles = []
        facility_handles = []
        pipeline_handles = []

        # === 路线图例 ===
        if self.global_route_legend.get('h2'):
            route_handles.append(Line2D([0], [0], color=self.transport_colors['H2'], linewidth=1.5,
                                        label='Hydrogen Transport Route'))
        if self.global_route_legend.get('co2'):
            route_handles.append(Line2D([0], [0], color=self.transport_colors['CO2'], linewidth=1.5,
                                        label='Carbon Dioxide Transport Route'))
        if self.global_route_legend.get('ng'):
            route_handles.append(Line2D([0], [0], color=self.transport_colors['NG'], linewidth=2,
                                        label='Natural Gas Transport Route'))
        if self.global_route_legend.get('saf'):
            route_handles.append(Line2D([0], [0], color=self.transport_colors['SAF'], linewidth=2,
                                        label='SAF Truck Transport Route'))

        # === 设施分类图例 ===
        if self.global_facility_legend:
            for (material_label, saf_production, consumption), attrs in sorted(self.global_facility_legend.items()):
                short_label = self._format_legend_label(attrs)

                legend_marker = attrs.get('marker', 'o')
                legend_edge = attrs.get('edgecolor', '#000000')
                legend_width = attrs.get('linewidth', 1.0)
                # 图例图标统一放大；机场/自定义SVG图标额外放大
                legend_size = 22
                if attrs.get('multi_material'):
                    has_saf = bool(attrs.get('has_saf'))
                    legend_marker = 'P' if has_saf else 'X'
                    legend_edge = '#000000'
                    legend_width = max(1.5, legend_width)
                    legend_size = 24 if has_saf else 22

                # 对机场与复杂路径标记做可读性增强
                if 'Airport' in short_label:
                    # 飞机图标横向细节较多，legend里需要更大尺寸才清晰
                    legend_size = max(legend_size, 40)
                    legend_width = max(2.6, legend_width)
                    if legend_edge in ('white', '#FFFFFF', '#ffffff'):
                        legend_edge = '#333333'
                elif not isinstance(legend_marker, str):
                    # 自定义SVG Path标记（如飞机、工厂）在legend里偏小，额外放大
                    legend_size = max(legend_size, 30)
                    legend_width = max(1.8, legend_width)

                facility_handles.append(
                    Line2D([0], [0], marker=legend_marker, color='w',
                           markerfacecolor=attrs.get('color', '#808080'),
                           markersize=legend_size,
                           markeredgecolor=legend_edge,
                           markeredgewidth=legend_width,
                           label=short_label)
                )

        # === 管道网络图例 ===
        if any(self.global_pipeline_legend.values()):
            pipeline_names_en = {
                'crude': 'Crude Oil',
                'refined': 'Product Oil',
                'natural_gas': 'Natural Gas'
            }
            pipeline_colors_legend = {
                'crude': '#8c510a',
                'refined': '#d8b365',
                'natural_gas': '#5ab4ac'
            }

            for pipeline_type, enabled in self.global_pipeline_legend.items():
                if enabled:
                    pipeline_handles.append(
                        Line2D([0], [0], color=pipeline_colors_legend[pipeline_type],
                               linewidth=1.5, alpha=1.0,
                               label=f'{pipeline_names_en[pipeline_type]}')
                    )

        if not (route_handles or facility_handles or pipeline_handles):
            logger.warning("全局图例为空，未生成")
            return

        # 横向排布，宽度为原图(6)的四倍：24；
        # 中间设施分类列更宽，避免两列图例文本与左右列重叠
        fig = plt.figure(figsize=(48, 9.5))
        gs = fig.add_gridspec(1, 3, width_ratios=[0.85, 1.35, 0.85], wspace=0.06)
        ax_route = fig.add_subplot(gs[0, 0])
        ax_facility = fig.add_subplot(gs[0, 1])
        ax_pipeline = fig.add_subplot(gs[0, 2])
        for ax in (ax_route, ax_facility, ax_pipeline):
            ax.axis('off')
        fig.subplots_adjust(left=0.02, right=0.98, top=0.95, bottom=0.08)

        title_font = {'family': 'Times New Roman', 'size': 18 * FONT_SCALE, 'weight': 'bold'}
        item_font = {'family': 'Times New Roman', 'size': 13 * FONT_SCALE}

        if route_handles:
            ax_route.text(0.02, 1.0, 'Transport Routes', transform=ax_route.transAxes,
                          ha='left', va='top', fontdict=title_font)
            route_legend = ax_route.legend(
                handles=route_handles, loc='upper left', bbox_to_anchor=(0.02, 0.92),
                prop=item_font, ncol=1, frameon=False, borderpad=0.2, labelspacing=0.9
            )
            ax_route.add_artist(route_legend)

        if facility_handles:
            ax_facility.text(0.5, 1.0, 'Facility Classification', transform=ax_facility.transAxes,
                             ha='center', va='top', fontdict=title_font)
            facility_legend = ax_facility.legend(
                handles=facility_handles, loc='upper center', bbox_to_anchor=(0.5, 0.92),
                prop=item_font, ncol=3, frameon=False, borderpad=0.2, labelspacing=0.9,
                columnspacing=1.0, handletextpad=0.7
            )
            ax_facility.add_artist(facility_legend)

        if pipeline_handles:
            ax_pipeline.text(0.98, 1.0, 'Pipeline Network', transform=ax_pipeline.transAxes,
                             ha='right', va='top', fontdict=title_font)
            pipeline_legend = ax_pipeline.legend(
                handles=pipeline_handles, loc='upper right', bbox_to_anchor=(0.98, 0.92),
                prop=item_font, ncol=1, frameon=False, borderpad=0.2, labelspacing=0.9
            )
            ax_pipeline.add_artist(pipeline_legend)

        output_path = self.session_dir / "legend_overview.png"
        plt.savefig(output_path, dpi=OUTPUT_DPI, bbox_inches='tight')
        logger.info(f"  ✓ 保存总图例: {output_path}")
        plt.close(fig)

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

    @staticmethod
    def _normalize_path_coords(path_coords):
        """
        统一路径坐标为[(lon, lat), ...]格式，兼容[lon, lat]与[lat, lon]两种顺序
        """
        if not path_coords:
            return []

        lonlat_votes = 0
        latlon_votes = 0

        for coord in path_coords:
            if not isinstance(coord, (list, tuple)) or len(coord) < 2:
                continue
            try:
                a = float(coord[0])
                b = float(coord[1])
            except (ValueError, TypeError):
                continue

            # 通过数值范围判断顺序（中国经度>90，纬度<90）
            if abs(a) > 90 and abs(b) <= 90:
                lonlat_votes += 1
            elif abs(a) <= 90 and abs(b) > 90:
                latlon_votes += 1

        normalized = []
        if latlon_votes > lonlat_votes:
            # 输入为[lat, lon]，转换为[lon, lat]
            for coord in path_coords:
                if isinstance(coord, (list, tuple)) and len(coord) >= 2:
                    try:
                        lat = float(coord[0])
                        lon = float(coord[1])
                        normalized.append((lon, lat))
                    except (ValueError, TypeError):
                        continue
        else:
            # 默认按[lon, lat]处理
            for coord in path_coords:
                if isinstance(coord, (list, tuple)) and len(coord) >= 2:
                    try:
                        lon = float(coord[0])
                        lat = float(coord[1])
                        normalized.append((lon, lat))
                    except (ValueError, TypeError):
                        continue

        return normalized

    def _get_pipeline_route_coords(self, start_lat: float, start_lon: float, end_lat: float, end_lon: float):
        """
        获取管道路径坐标（用于CO2运输可视化）

        Args:
            start_lat: 起点纬度
            start_lon: 起点经度
            end_lat: 终点纬度
            end_lon: 终点经度

        Returns:
            路径坐标列表 [(lon, lat), ...] 或 None
        """
        if self.pipeline_calculator is None:
            return None

        # 检查缓存
        cache_key = (round(start_lat, 4), round(start_lon, 4), round(end_lat, 4), round(end_lon, 4))
        if cache_key in self.pipeline_route_cache:
            return self.pipeline_route_cache[cache_key]

        try:
            route = self.pipeline_calculator.calculate_pipeline_distance(
                start_lat, start_lon, end_lat, end_lon
            )
            if hasattr(route, 'route_geometry') and route.route_geometry:
                # 转换为 [(lon, lat), ...] 格式
                path_coords = [(coord[1], coord[0]) for coord in route.route_geometry]
                self.pipeline_route_cache[cache_key] = path_coords
                return path_coords
        except Exception as e:
            logger.debug(f"获取管道路径失败 ({start_lat:.4f}, {start_lon:.4f}) -> ({end_lat:.4f}, {end_lon:.4f}): {e}")

        # 缓存失败结果
        self.pipeline_route_cache[cache_key] = None
        return None

    def _coord_key(self, lon: float, lat: float, precision: int = 4):
        """统一坐标key（用于可视化过滤）"""
        return (round(lon, precision), round(lat, precision))

    def _in_extent(self, lon: float, lat: float) -> bool:
        """判断坐标是否在当前地图范围内"""
        if getattr(self, 'ignore_extent_filter', False):
            return True
        extent = getattr(self, 'current_extent', None)
        if not extent:
            return True
        min_lon, max_lon, min_lat, max_lat = extent
        return (min_lon <= lon <= max_lon) and (min_lat <= lat <= max_lat)

    def _should_draw_route(self, start_lon, start_lat, end_lon, end_lat, precision: int = 4) -> bool:
        """仅在起终点都为已标注点（含设施/聚类中心）时才绘制路线"""
        if start_lon is None or start_lat is None or end_lon is None or end_lat is None:
            return False
        # 起终点必须在当前可视范围内
        if not self._in_extent(start_lon, start_lat) or not self._in_extent(end_lon, end_lat):
            return False
        # 严格匹配收集阶段：只做范围检查，不依赖可见点集合
        if getattr(self, 'collect_only', False):
            return True
        visible = getattr(self, 'visible_facility_coords', None)
        if visible is None:
            return True
        return (
            self._coord_key(start_lon, start_lat, precision) in visible
            and self._coord_key(end_lon, end_lat, precision) in visible
        )

    def _mark_visible(self, lon: float, lat: float, precision: int = 4):
        """将已标注点加入可见集合（用于后续路线过滤）"""
        if lon is None or lat is None:
            return
        if not self._in_extent(lon, lat):
            return
        if getattr(self, 'visible_facility_coords', None) is None:
            self.visible_facility_coords = set()
        self.visible_facility_coords.add(self._coord_key(lon, lat, precision))

    def _record_route_endpoints(self, start_lon, start_lat, end_lon, end_lat, precision: int = 4):
        """记录线路端点坐标（用于严格匹配模式过滤设施点）"""
        if getattr(self, 'route_endpoint_coords', None) is None:
            self.route_endpoint_coords = set()
        if start_lon is not None and start_lat is not None:
            self.route_endpoint_coords.add(self._coord_key(start_lon, start_lat, precision))
        if end_lon is not None and end_lat is not None:
            self.route_endpoint_coords.add(self._coord_key(end_lon, end_lat, precision))

    def _reset_drawn_bounds(self):
        """重置本次绘图的边界记录"""
        self.drawn_bounds = None

    def _update_drawn_bounds(self, lons, lats):
        """更新绘制对象的地理边界（用于自动收缩范围）"""
        if getattr(self, 'collect_only', False):
            return
        if lons is None or lats is None:
            return
        if len(lons) == 0 or len(lats) == 0:
            return
        lon_min = float(np.nanmin(lons))
        lon_max = float(np.nanmax(lons))
        lat_min = float(np.nanmin(lats))
        lat_max = float(np.nanmax(lats))

        if self.drawn_bounds is None:
            self.drawn_bounds = [lon_min, lon_max, lat_min, lat_max]
            return
        self.drawn_bounds[0] = min(self.drawn_bounds[0], lon_min)
        self.drawn_bounds[1] = max(self.drawn_bounds[1], lon_max)
        self.drawn_bounds[2] = min(self.drawn_bounds[2], lat_min)
        self.drawn_bounds[3] = max(self.drawn_bounds[3], lat_max)

    def _apply_tight_extent(self, ax):
        """根据已绘制的点/线自动收缩地图范围"""
        if not getattr(self, 'tight_extent_mode', False):
            return
        if self.drawn_bounds is None:
            return

        min_lon, max_lon, min_lat, max_lat = self.drawn_bounds
        lon_span = max_lon - min_lon
        lat_span = max_lat - min_lat

        # 动态边距：至少0.1度，或跨度的5%
        pad_lon = max(0.1, lon_span * 0.05)
        pad_lat = max(0.1, lat_span * 0.05)

        min_lon -= pad_lon
        max_lon += pad_lon
        min_lat -= pad_lat
        max_lat += pad_lat

        ax.set_extent([min_lon, max_lon, min_lat, max_lat], crs=self.data_crs)
        self.current_extent = (min_lon, max_lon, min_lat, max_lat)

        # 重新设置刻度与网格（整数刻度）
        span_lon = max_lon - min_lon
        span_lat = max_lat - min_lat
        x_step = 1 if span_lon <= 6 else 2
        y_step = 1 if span_lat <= 6 else 2
        xticks = np.arange(np.floor(min_lon), np.ceil(max_lon) + 1, x_step)
        yticks = np.arange(np.floor(min_lat), np.ceil(max_lat) + 1, y_step)
        fplt.set_map_ticks(ax, (min_lon, max_lon, min_lat, max_lat), xticks, yticks)
        ax.gridlines(xlocs=xticks, ylocs=yticks, lw=0.5, ls=":", color="#B0B0B0", alpha=0.4)

    @staticmethod
    def _get_transport_volume(row, volume_type='kg'):
        """
        统一的运输量获取方法，支持自动降级

        优先级：周运输量 > 日运输量 × 7

        Args:
            row: DataFrame行对象
            volume_type: 'kg' 或 'm³'

        Returns:
            运输量（float），如果无有效值则返回0
        """
        # 优先尝试周运输量
        weekly_key = f'周运输量({volume_type})'
        if weekly_key in row:
            weekly_vol = row.get(weekly_key, 0)
            # 处理空字符串、NaN等情况
            if pd.notna(weekly_vol) and weekly_vol not in ('', ' '):
                try:
                    weekly_vol_float = float(weekly_vol)
                    if weekly_vol_float > 0.01:
                        return weekly_vol_float
                except (ValueError, TypeError):
                    pass

        # 降级到日运输量
        daily_key = f'日运输量({volume_type})'
        if daily_key in row:
            daily_vol = row.get(daily_key, 0)
            # 处理空字符串、NaN等情况
            if pd.notna(daily_vol) and daily_vol not in ('', ' '):
                try:
                    daily_vol_float = float(daily_vol)
                    if daily_vol_float > 0.01:
                        # 转换为周运输量
                        return daily_vol_float * 7
                except (ValueError, TypeError):
                    pass

        # 都没有有效值，返回0
        return 0.0

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
        # 维度1: 形状映射 (使用自定义SVG Path)
        shape_map = {
            'h2': (CustomMarkers.h2_icon(), 'Hydrogen Production'),
            'co2': (CustomMarkers.co2_cloud(), 'Carbon Dioxide Capture'),
            'natural_gas': (CustomMarkers.flame(), 'Natural Gas Supply'),
        }

        # 维度2: 颜色映射 (Applied Energy Style - Refined)
        # 调整颜色以适应新图标
        color_map = {
            'yes': ('#005AB5', '#002040', 'SAF Production'),  # Deep Blue fill
            'no': ('#E0E0E0', '#606060', 'No SAF Production')    # Light Grey fill
        }

        # 维度3: 边框粗细映射
        linewidth_map = {
            'yes': (1.5, 'Consumer'),   
            'no': (0.8, 'Non-Consumer')
        }

        # 获取维度2、3的属性
        color, edgecolor, saf_label = color_map.get(saf_production, ('#808080', '#404040', 'Unknown'))
        linewidth, consumption_label = linewidth_map.get(consumption, (1.0, 'Unknown'))

        # 特殊处理：如果是消纳地（机场），且没有原材料生产，使用飞机图标
        # 特殊处理：如果有SAF生产，叠加工厂图标

        markers = []
        base_size = 240  # 放大图标大小

        # 1. 基础图标逻辑
        if consumption == 'yes':
            # 机场/消纳地 -> 飞机图标
            markers.append({
                'marker': CustomMarkers.airplane(),
                'color': '#D55E00' if saf_production == 'yes' else '#808080', # 如果产SAF则是橙红色，否则灰色
                'edgecolor': 'white', # 飞机内部填充色，边缘白色
                # 注意：matplotlib scatter marker facecolor 是 'c'/'color', edgecolor 是 'edgecolors'
                # 飞机图标比较特殊，我们希望它是实心的
                'size': base_size * 4.0, # 飞机大一点
                'linewidth': 1.0,
                'raw_material_label': 'Airport (Consumption Site)',
                'saf_production_label': saf_label,
                'consumption_label': consumption_label,
                'full_label': f"Airport{' (SAF Production Facility)' if saf_production == 'yes' else ''}"
            })
            
            # 如果机场同时产SAF（上面颜色已区分，但也可以叠加工厂标，这里暂不叠加以免混乱）
            return markers

        # 2. 生产设施逻辑
        if not raw_materials:
            # 无原材料生产，但可能是SAF工厂
            if saf_production == 'yes':
                markers.append({
                    'marker': CustomMarkers.factory(),
                    'color': color,
                    'edgecolor': edgecolor,
                'size': base_size * 1.35,
                    'linewidth': linewidth,
                    'raw_material_label': 'SAF Production Facility',
                    'saf_production_label': saf_label,
                    'consumption_label': consumption_label,
                    'full_label': "SAF Production Facility"
                })
            else:
                # 既无原材料也无SAF，普通点
                markers.append({
                    'marker': 'o',
                    'color': color,
                    'edgecolor': edgecolor,
                    'size': 50,
                    'linewidth': linewidth,
                    'raw_material_label': 'General Node',
                    'saf_production_label': saf_label,
                    'consumption_label': consumption_label,
                    'full_label': "General Node"
                })
        else:
            # 有原材料生产
            material_labels = []
            
            # 如果同时有SAF生产，先加一个工厂底标? 或者颜色区分
            # 策略：如果有SAF生产，使用工厂图标作为主标；原材料作为角标或者组合？
            # 简化策略：如果有SAF生产，优先显示工厂；原材料图标单独显示（如果有多个角色，画多个偏移点？或者同心？）
            
            # 目前代码逻辑是scatter不支持多图标混合在同一点（除非多次调用plot）。
            # `plot_facilities` 实际上会对每个marker dict调用一次scatter。
            # 所以我们可以返回多个marker dict，它们会画在同一个坐标上。
            
            # 2.1 如果有SAF生产，先画一个大的工厂背景
            if saf_production == 'yes':
                 markers.append({
                    'marker': CustomMarkers.factory(),
                    'color': '#E0E0E0', # 浅灰背景
                    'edgecolor': '#404040',
                    'size': base_size * 2.6, # 大工厂背景
                    'linewidth': 1.0,
                    'raw_material_label': 'SAF Production Facility',
                    'saf_production_label': saf_label,
                    'consumption_label': consumption_label,
                    'full_label': "SAF Production Facility"
                })

            # 2.2 叠加原材料图标
            for material in sorted(raw_materials):
                marker, material_label = shape_map.get(material, ('o', 'Unknown'))
                material_labels.append(material_label)

                # 颜色：原材料使用特定颜色
                mat_color = '#FFFFFF' # 默认白色填充
                mat_edge = '#333333'
                if material == 'h2':
                    mat_color = '#0072B2' # 蓝
                    mat_edge = '#0072B2'  # 边框同色，避免白边遮挡细节
                elif material == 'co2':
                    mat_color = '#663300' # 褐/黑
                    mat_edge = '#663300'  # 边框同色
                elif material == 'natural_gas':
                    mat_color = '#009E73' # 绿
                    mat_edge = '#009E73'  # 边框同色

                markers.append({
                    'marker': marker,
                    'color': mat_color,
                    'edgecolor': mat_edge,
                    'size': base_size * 1.3,
                    'linewidth': 1.2,
                    'raw_material_label': material_label,
                    'saf_production_label': saf_label,
                    'consumption_label': consumption_label,
                    'full_label': f"{material_label}"
                })

            # 【修复】如果有多个标记（工厂背景+原材料），将原材料标记放到第一位用于图例显示
            # 这样图例会显示原材料的颜色和图标，而不是工厂背景
            if len(markers) > 1 and saf_production == 'yes':
                # 交换顺序：原材料标记放第一位
                factory_marker = markers[0]  # 工厂背景
                material_marker = markers[1]  # 原材料标记
                markers[0] = material_marker
                markers[1] = factory_marker

                # 更新组合标签
                combined_label = '+'.join(material_labels)
                combined_label += "+SAF Production Facility"
                markers[0]['combined_label'] = combined_label
                # 【修复】使用工厂图标作为图例标记，但保留原材料的颜色
                markers[0]['marker'] = CustomMarkers.factory()
            elif len(markers) > 1:
                combined_label = '+'.join(material_labels)
                markers[0]['combined_label'] = combined_label

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

        # 检查是否有氢气运输数据
        if len(h2_data) == 0:
            logger.info(f"    无氢气运输数据，跳过聚类路线绘制")
            return

        # 检查是否有 '聚类信息' 列
        if '聚类信息' not in h2_data.columns:
            logger.info(f"    数据中没有 '聚类信息' 列，跳过聚类路线绘制")
            logger.info(f"    可用列名: {list(h2_data.columns)}")
            return

        # 筛选聚类数据（有聚类信息的行）
        h2_cluster_data = h2_data[h2_data['聚类信息'].notna() & (h2_data['聚类信息'] != '')].copy()
        # 非聚类（孤立点）数据
        h2_non_cluster_data = h2_data[~(h2_data['聚类信息'].notna() & (h2_data['聚类信息'] != ''))].copy()
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

        # 记录已绘制的聚类中心到终点路径（去重用）
        drawn_cluster_to_end = set()

        # 统计计数
        layer1_count = 0
        layer2_count = 0
        layer3_count = 0
        non_cluster_count = 0

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
            # 【修复】使用统一的运输量获取方法（支持自动降级：周运输量 -> 日运输量×7）
            volume = self._get_transport_volume(row, volume_type='kg')
            if volume <= 0.01:
                continue

            # 解析聚类信息 "聚类0_(中心:36.2153,114.4731)"
            cluster_info = row.get('聚类信息', '')
            if not cluster_info or pd.isna(cluster_info):
                continue

            # 【修复】优先从聚类信息字符串中提取嵌入的聚类中心坐标
            # 因为JSON文件可能与transport_summary不同步
            try:
                import re
                cluster_id = int(cluster_info.split('聚类')[1].split('_')[0])

                # 尝试从聚类信息中提取中心坐标 "聚类0_(中心:37.2003,118.4270)"
                center_match = re.search(r'中心:([\d.]+),([\d.]+)', str(cluster_info))
                if center_match:
                    # 使用嵌入的坐标（更准确，与实际优化结果一致）
                    center_lat = float(center_match.group(1))
                    center_lon = float(center_match.group(2))
                elif cluster_id in all_cluster_centers:
                    # 回退：使用JSON文件中的坐标
                    center_lat, center_lon = all_cluster_centers[cluster_id]
                else:
                    continue

            except:
                continue

            # 解析起点/终点坐标
            start_lat, start_lon = parse_coord(row.get('起点坐标'))
            end_lat, end_lon = parse_coord(row.get('终点坐标'))
            if start_lat is None or start_lon is None:
                continue
            if end_lat is None or end_lon is None:
                continue

            # 仅绘制起终点均为已标注设施的路线
            if not self._should_draw_route(start_lon, start_lat, end_lon, end_lat):
                continue

            # 严格匹配收集阶段：仅记录端点，不做路径计算与绘制
            if self.collect_only:
                # Layer1: 起点 -> 聚类中心
                if self._should_draw_route(start_lon, start_lat, center_lon, center_lat):
                    if self.haversine(start_lon, start_lat, center_lon, center_lat) > 0.01:
                        self._record_route_endpoints(start_lon, start_lat, None, None)
                # Layer2/3: 聚类中心 -> 终点
                layer2_dist = row.get('Layer2距离(km)', 0)
                layer3_dist = row.get('Layer3距离(km)', 0)
                if (layer2_dist > 0 or layer3_dist > 0) and self._should_draw_route(center_lon, center_lat, end_lon, end_lat):
                    self._record_route_endpoints(None, None, end_lon, end_lat)
                continue

            # 通过过滤后再标记聚类中心、起点和终点为已使用
            used_cluster_centers[cluster_id] = (center_lat, center_lon)
            self._mark_visible(center_lon, center_lat)
            self._mark_visible(start_lon, start_lat)  # 标记起点为可见，以便绘制Layer1
            self._mark_visible(end_lon, end_lat)  # 标记终点为可见，以便绘制Layer2+Layer3

            # Layer1: 可再生能源站 → 聚类中心
            layer1_dist = row.get('Layer1距离(km)', 0)

            # Layer1 使用直线连接（不使用管道路径）
            if self._should_draw_route(start_lon, start_lat, center_lon, center_lat):
                if self.haversine(start_lon, start_lat, center_lon, center_lat) > 0.01:
                    # 直线连接起点到聚类中心
                    ax.plot(
                        [start_lon, center_lon],
                        [start_lat, center_lat],
                        color=self.transport_colors['H2'],
                        alpha=0.7,
                        linewidth=1.2,
                        linestyle='-',
                        zorder=18,  # 提高zorder，在设施点下方但在其他路径上方
                        transform=self.data_crs
                    )
                    self._update_drawn_bounds([start_lon, center_lon], [start_lat, center_lat])
                    if not self.collect_only:
                        self.global_route_legend['h2'] = True
                    layer1_count += 1

            # Layer2 + Layer3: 聚类中心 → 终点 (蓝色路径) - 每个聚类只画一次
            layer2_dist = row.get('Layer2距离(km)', 0)
            layer3_dist = row.get('Layer3距离(km)', 0)

            # 去重：每个聚类中心到终点的路径只画一次
            cluster_end_key = (cluster_id, round(end_lat, 4), round(end_lon, 4))
            if cluster_end_key not in drawn_cluster_to_end:
                if (layer2_dist > 0 or layer3_dist > 0) and self._should_draw_route(center_lon, center_lat, end_lon, end_lat):
                    # 使用管道计算器计算聚类中心到终点的路径
                    center_to_end_path = self._get_pipeline_route_coords(center_lat, center_lon, end_lat, end_lon)
                    if center_to_end_path and len(center_to_end_path) >= 2:
                        lons = [coord[0] for coord in center_to_end_path]
                        lats = [coord[1] for coord in center_to_end_path]
                        ax.plot(
                            lons, lats,
                            color=self.transport_colors['H2'],
                            alpha=0.7,
                            linewidth=1.2,
                            linestyle='-',
                            zorder=7,
                            transform=self.data_crs
                        )
                        self._update_drawn_bounds(lons, lats)
                        if not self.collect_only:
                            self.global_route_legend['h2'] = True
                    else:
                        # 回退：直线
                        ax.plot(
                            [center_lon, end_lon],
                            [center_lat, end_lat],
                            color=self.transport_colors['H2'],
                            alpha=0.7,
                            linewidth=1.2,
                            linestyle='-',
                            zorder=7,
                            transform=self.data_crs
                        )
                        self._update_drawn_bounds([center_lon, end_lon], [center_lat, end_lat])
                        if not self.collect_only:
                            self.global_route_legend['h2'] = True
                    # 标记已绘制
                    drawn_cluster_to_end.add(cluster_end_key)
                    # 统计
                    if layer2_dist > 0:
                        layer2_count += 1
                    if layer3_dist > 0:
                        layer3_count += 1

        # 绘制非聚类（孤立点）H2线路：直接按路径坐标绘制
        if len(h2_non_cluster_data) > 0:
            for idx, row in h2_non_cluster_data.iterrows():
                # 运输量过滤
                volume = self._get_transport_volume(row, volume_type='kg')
                if volume <= 0.01:
                    continue
                if volume < self.min_h2_noncluster_weekly_kg:
                    continue

                start_lat, start_lon = parse_coord(row.get('起点坐标'))
                end_lat, end_lon = parse_coord(row.get('终点坐标'))
                if start_lat is None or start_lon is None or end_lat is None or end_lon is None:
                    continue

                # 仅绘制起终点均为已标注设施的路线
                if not self._should_draw_route(start_lon, start_lat, end_lon, end_lat):
                    continue

                if self.collect_only:
                    self._record_route_endpoints(start_lon, start_lat, end_lon, end_lat)
                    non_cluster_count += 1
                    continue

                # 【修改】直接使用管道计算器现场计算路径，不使用预存的路径坐标
                route_coords = None
                pipeline_path = self._get_pipeline_route_coords(start_lat, start_lon, end_lat, end_lon)
                if pipeline_path and len(pipeline_path) >= 2:
                    route_coords = pipeline_path
                    logger.debug(f"    H2非聚类路径使用管道计算器: {start_lat:.4f},{start_lon:.4f} -> {end_lat:.4f},{end_lon:.4f}")

                # 最后回退：使用起终点直线（仅当管道计算器也失败时）
                if route_coords is None or len(route_coords) < 2:
                    route_coords = [(start_lon, start_lat), (end_lon, end_lat)]
                    logger.debug(f"    H2非聚类路径使用直线: {start_lat:.4f},{start_lon:.4f} -> {end_lat:.4f},{end_lon:.4f}")

                lons = [coord[0] for coord in route_coords]
                lats = [coord[1] for coord in route_coords]
                ax.plot(
                    lons, lats,
                    color=self.transport_colors['H2'],
                    alpha=0.7,
                    linewidth=1.2,
                    linestyle='-',
                    zorder=6,
                    transform=self.data_crs
                )
                self._update_drawn_bounds(lons, lats)
                if not self.collect_only:
                    self.global_route_legend['h2'] = True
                non_cluster_count += 1

        logger.info(f"    ✓ Layer1: {layer1_count} 条（源点→聚类中心）")
        logger.info(f"    ✓ Layer2: {layer2_count} 条（聚类中心→管道接入点）")
        logger.info(f"    ✓ Layer3: {layer3_count} 条（管道网络→目的地）")
        logger.info(f"    ✓ 非聚类H2线路: {non_cluster_count} 条（直接绘制）")
        logger.info(f"    ✓ 实际使用的聚类中心: {len(used_cluster_centers)} 个（总共{len(all_cluster_centers)}个）")

    def plot_co2_routes(self, ax, co2_clustering, transport_summary, module_name):
        """
        绘制CO2运输路线（支持聚类与直达）

        Args:
            ax: matplotlib axes对象
            co2_clustering: CO2聚类JSON数据
            transport_summary: 运输汇总DataFrame（包含Layer信息）
            module_name: 模块名称
        """
        if transport_summary is None or len(transport_summary) == 0:
            return

        if '货物类型' not in transport_summary.columns:
            return

        co2_df = transport_summary[
            transport_summary['货物类型'].astype(str).str.contains(r'CO2|CO₂|二氧化碳', case=False, na=False)
        ].copy()

        if len(co2_df) == 0:
            return

        logger.info(f"  绘制CO2运输路线...")
        used_cluster_centers = {}

        all_cluster_centers = {}
        if co2_clustering:
            for cluster in co2_clustering.get('clusters', []):
                cluster_id = cluster.get('cluster_id')
                center = cluster.get('geo_center') or cluster.get('center_coord')
                if center and len(center) >= 2 and cluster_id is not None:
                    all_cluster_centers[cluster_id] = (center[0], center[1])

        # 统计计数
        layer1_count = 0
        layer2_count = 0
        layer3_count = 0

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

        for _, row in co2_df.iterrows():
            volume = self._get_transport_volume(row, volume_type='kg')
            if volume <= 0.01:
                continue

            cluster_info = row.get('聚类信息', '')
            center_lat = None
            center_lon = None

            if cluster_info and pd.notna(cluster_info):
                try:
                    import re
                    id_match = re.search(r'聚类(\\d+)', str(cluster_info))
                    cluster_id = int(id_match.group(1)) if id_match else None

                    center_match = re.search(r'中心:([\\d.]+),([\\d.]+)', str(cluster_info))
                    if center_match:
                        center_lat = float(center_match.group(1))
                        center_lon = float(center_match.group(2))
                    elif cluster_id in all_cluster_centers:
                        center_lat, center_lon = all_cluster_centers[cluster_id]
                except:
                    pass

            start_lat, start_lon = parse_coord(row.get('起点坐标'))
            end_lat, end_lon = parse_coord(row.get('终点坐标'))

            # 仅绘制起终点均为已标注设施的路线
            if not self._should_draw_route(start_lon, start_lat, end_lon, end_lat):
                continue

            # 严格匹配收集阶段：仅记录端点，不做路径计算与绘制
            if self.collect_only:
                layer1_dist = row.get('Layer1距离(km)', 0)
                layer3_dist = row.get('Layer3距离(km)', 0)
                if layer1_dist > 0 and center_lat is not None and center_lon is not None \
                        and self._should_draw_route(start_lon, start_lat, center_lon, center_lat):
                    self._record_route_endpoints(start_lon, start_lat, None, None)
                if layer3_dist > 0:
                    if center_lat is not None and center_lon is not None:
                        if self._should_draw_route(center_lon, center_lat, end_lon, end_lat):
                            self._record_route_endpoints(None, None, end_lon, end_lat)
                    else:
                        if self._should_draw_route(start_lon, start_lat, end_lon, end_lat):
                            self._record_route_endpoints(start_lon, start_lat, end_lon, end_lat)
                continue

            # 记录CO2聚类中心为可见点（避免“无点有线”）
            if center_lat is not None and center_lon is not None:
                used_cluster_centers[(center_lon, center_lat)] = (center_lat, center_lon)
                self._mark_visible(center_lon, center_lat)

            # Layer1: CO2源 -> 聚类中心
            layer1_dist = row.get('Layer1距离(km)', 0)
            if (layer1_dist > 0 and center_lat is not None and center_lon is not None and start_lat is not None
                    and self._should_draw_route(start_lon, start_lat, center_lon, center_lat)):
                ax.plot(
                    [start_lon, center_lon],
                    [start_lat, center_lat],
                    color=self.transport_colors['CO2'],
                    alpha=0.6,
                    linewidth=0.9,
                    linestyle='--',
                    zorder=6,
                    transform=self.data_crs
                )
                self._update_drawn_bounds([start_lon, center_lon], [start_lat, center_lat])
                if not self.collect_only:
                    self.global_route_legend['co2'] = True
                layer1_count += 1

            # 【修改】直接使用管道计算器现场计算路径，不使用预存的路径坐标
            path_coords = None
            if start_lat is not None and start_lon is not None and end_lat is not None and end_lon is not None:
                # 如果有聚类中心，从聚类中心到终点获取管道路径
                if center_lat is not None and center_lon is not None:
                    path_coords = self._get_pipeline_route_coords(center_lat, center_lon, end_lat, end_lon)
                else:
                    # 没有聚类中心，从起点到终点获取管道路径
                    path_coords = self._get_pipeline_route_coords(start_lat, start_lon, end_lat, end_lon)

            # Layer2: 聚类中心 -> 管道接入点
            pipeline_access_point = None
            access_point_idx = 0
            if path_coords and len(path_coords) >= 2 and center_lat is not None and center_lon is not None:
                min_dist_to_center = float('inf')
                start_idx = 0
                for i, coord in enumerate(path_coords):
                    dist = self.haversine(center_lon, center_lat, coord[0], coord[1])
                    if dist < min_dist_to_center:
                        min_dist_to_center = dist
                        start_idx = i

                access_point_idx = start_idx
                layer2_dist = row.get('Layer2距离(km)', 0)
                if layer2_dist > 0:
                    cumulative_dist = 0
                    for i in range(start_idx + 1, len(path_coords)):
                        seg_dist = self.haversine(
                            path_coords[i-1][0], path_coords[i-1][1],
                            path_coords[i][0], path_coords[i][1]
                        )
                        cumulative_dist += seg_dist
                        if abs(cumulative_dist - layer2_dist) < 1:
                            pipeline_access_point = path_coords[i]
                            access_point_idx = i
                            break

                    if pipeline_access_point and self._should_draw_route(
                        center_lon, center_lat, pipeline_access_point[0], pipeline_access_point[1]
                    ):
                        ax.plot(
                            [center_lon, pipeline_access_point[0]],
                            [center_lat, pipeline_access_point[1]],
                            color=self.transport_colors['CO2'],
                            alpha=0.7,
                            linewidth=1.0,
                            linestyle='-',
                            zorder=7,
                            transform=self.data_crs
                        )
                        self._update_drawn_bounds([center_lon, pipeline_access_point[0]], [center_lat, pipeline_access_point[1]])
                        if not self.collect_only:
                            self.global_route_legend['co2'] = True
                        layer2_count += 1

            # Layer3: 管道网络 -> 目的地（沿路径或直连）
            layer3_dist = row.get('Layer3距离(km)', 0)
            if layer3_dist > 0:
                if path_coords and len(path_coords) >= 2:
                    if pipeline_access_point:
                        segment_coords = path_coords[access_point_idx:]
                    else:
                        segment_coords = path_coords

                    if len(segment_coords) >= 2 and self._should_draw_route(
                        segment_coords[0][0], segment_coords[0][1],
                        segment_coords[-1][0], segment_coords[-1][1]
                    ):
                        lons = [coord[0] for coord in segment_coords]
                        lats = [coord[1] for coord in segment_coords]
                        ax.plot(
                            lons, lats,
                            color=self.transport_colors['CO2'],
                            alpha=0.7,
                            linewidth=1.1,
                            linestyle='-',
                            zorder=7,
                            transform=self.data_crs
                        )
                        self._update_drawn_bounds(lons, lats)
                        if not self.collect_only:
                            self.global_route_legend['co2'] = True
                        layer3_count += 1
                else:
                    if pipeline_access_point and end_lon is not None and end_lat is not None and self._should_draw_route(
                        pipeline_access_point[0], pipeline_access_point[1], end_lon, end_lat
                    ):
                        ax.plot(
                            [pipeline_access_point[0], end_lon],
                            [pipeline_access_point[1], end_lat],
                            color=self.transport_colors['CO2'],
                            alpha=0.7,
                            linewidth=1.1,
                            linestyle='-',
                            zorder=7,
                            transform=self.data_crs
                        )
                        self._update_drawn_bounds([pipeline_access_point[0], end_lon], [pipeline_access_point[1], end_lat])
                        if not self.collect_only:
                            self.global_route_legend['co2'] = True
                        layer3_count += 1
                    elif center_lon is not None and end_lon is not None and center_lat is not None and end_lat is not None \
                            and self._should_draw_route(center_lon, center_lat, end_lon, end_lat):
                        ax.plot(
                            [center_lon, end_lon],
                            [center_lat, end_lat],
                            color=self.transport_colors['CO2'],
                            alpha=0.7,
                            linewidth=1.1,
                            linestyle='-',
                            zorder=7,
                            transform=self.data_crs
                        )
                        self._update_drawn_bounds([center_lon, end_lon], [center_lat, end_lat])
                        if not self.collect_only:
                            self.global_route_legend['co2'] = True
                        layer3_count += 1
                    elif start_lon is not None and end_lon is not None and start_lat is not None and end_lat is not None \
                            and self._should_draw_route(start_lon, start_lat, end_lon, end_lat):
                        ax.plot(
                            [start_lon, end_lon],
                            [start_lat, end_lat],
                            color=self.transport_colors['CO2'],
                            alpha=0.7,
                            linewidth=1.1,
                            linestyle='-',
                            zorder=7,
                            transform=self.data_crs
                        )
                        self._update_drawn_bounds([start_lon, end_lon], [start_lat, end_lat])
                        if not self.collect_only:
                            self.global_route_legend['co2'] = True
                        layer3_count += 1

        # 标注CO2聚类中心（用于避免“无点有线”）
        # 聚类中心点不再绘制

        logger.info(f"    ✓ CO2 Layer1: {layer1_count} 条（源点→聚类中心）")
        logger.info(f"    ✓ CO2 Layer2: {layer2_count} 条（聚类中心→管道接入点）")
        logger.info(f"    ✓ CO2 Layer3: {layer3_count} 条（管道网络→目的地）")

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
                'color': '#8c510a',  # 土褐色
                'alpha': 0.3,        # 很淡
                'linewidth': 0.8,
                'file': 'crude_pipelines.geojson'
            },
            'refined': {
                'name': '成品油管道',
                'color': '#d8b365',  # 浅褐色
                'alpha': 0.3,
                'linewidth': 0.8,
                'file': 'refined_product_pipelines.geojson'
            },
            'natural_gas': {
                'name': '天然气管道',
                'color': '#5ab4ac',  # 浅青色
                'alpha': 0.4,
                'linewidth': 1.0,
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
                if not getattr(self, 'collect_only', False) and segments_count > 0:
                    if pipeline_type in self.global_pipeline_legend:
                        self.global_pipeline_legend[pipeline_type] = True

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
            # 【修复】使用统一的运输量获取方法（支持自动降级：周运输量 -> 日运输量×7）
            volume = self._get_transport_volume(row, volume_type='kg')
            if volume <= 0.01:
                continue

            # 解析起点和终点坐标
            start_lat, start_lon = parse_coord(row.get('起点坐标'))
            end_lat, end_lon = parse_coord(row.get('终点坐标'))

            if start_lat is None or start_lon is None or end_lat is None or end_lon is None:
                continue

            # 严格匹配收集阶段：仅记录端点，不做路径计算与绘制
            if self.collect_only:
                if not self._should_draw_route(start_lon, start_lat, end_lon, end_lat):
                    continue
                self._record_route_endpoints(start_lon, start_lat, end_lon, end_lat)
                route_count += 1
                continue

            # 仅绘制起终点均为已标注设施的路线
            if not self._should_draw_route(start_lon, start_lat, end_lon, end_lat):
                continue

            # 仅绘制起终点均为已标注设施的路线
            if not self._should_draw_route(start_lon, start_lat, end_lon, end_lat):
                continue

            # 仅绘制起终点均为已标注设施的路线
            if not self._should_draw_route(start_lon, start_lat, end_lon, end_lat):
                continue

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
                       alpha=0.9, # 提高不透明度
                       transform=self.data_crs,
                       zorder=20) # 提高层级，覆盖在管道和聚类路线上
                self._update_drawn_bounds(lons, lats)
                if not self.collect_only:
                    self.global_route_legend['saf'] = True
            else:
                # 降级为直线
                ax.plot([start_lon, end_lon], [start_lat, end_lat],
                       color=self.transport_colors['SAF'],
                       linewidth=linewidth,
                       alpha=0.8,
                       transform=self.data_crs,
                       zorder=15)
                self._update_drawn_bounds([start_lon, end_lon], [start_lat, end_lat])
                if not self.collect_only:
                    self.global_route_legend['saf'] = True
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
            # 【修复】使用统一的运输量获取方法（支持自动降级：周运输量 -> 日运输量×7）
            # 天然气优先尝试kg，降级到m³
            volume = self._get_transport_volume(row, volume_type='kg')
            if volume <= 0.01:
                volume = self._get_transport_volume(row, volume_type='m³')

            if volume <= 0.01:
                continue

            # 解析起点和终点坐标
            start_lat, start_lon = parse_coord(row.get('起点坐标'))
            end_lat, end_lon = parse_coord(row.get('终点坐标'))

            if start_lat is None or start_lon is None or end_lat is None or end_lon is None:
                continue

            # 严格匹配收集阶段：仅记录端点，不做路径计算与绘制
            if self.collect_only:
                if not self._should_draw_route(start_lon, start_lat, end_lon, end_lat):
                    continue
                self._record_route_endpoints(start_lon, start_lat, end_lon, end_lat)
                route_count += 1
                continue

            # 严格匹配模式下，确保起终点已可见
            if self.strict_match_mode and not self._should_draw_route(start_lon, start_lat, end_lon, end_lat):
                continue

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
                self._update_drawn_bounds(lons, lats)
                if not self.collect_only:
                    self.global_route_legend['ng'] = True
            else:
                # 降级为直线
                ax.plot([start_lon, end_lon], [start_lat, end_lat],
                       color=self.transport_colors['NG'],
                       linewidth=linewidth,
                       alpha=0.8,
                       transform=self.data_crs,
                       zorder=14)
                self._update_drawn_bounds([start_lon, end_lon], [start_lat, end_lat])
                if not self.collect_only:
                    self.global_route_legend['ng'] = True
                direct_line_count += 1

            route_count += 1

        logger.info(f"    ✓ 天然气路线: {route_count} 条")
        if self.graphhopper is not None:
            logger.info(f"    ✓ GraphHopper详细路径: {graphhopper_success_count} 条")
            logger.info(f"    ✓ 直线路径: {direct_line_count} 条")

    def plot_h2_direct_routes(self, ax, transport_summary):
        """
        绘制氢气直接运输路线（用于一步法场景，不需要聚类数据）

        Args:
            ax: matplotlib axes对象
            transport_summary: 运输汇总DataFrame
        """
        if transport_summary is None or len(transport_summary) == 0:
            return

        # 筛选出氢气运输数据
        h2_df = transport_summary[transport_summary['货物类型'] == '氢气'].copy()
        if len(h2_df) == 0:
            logger.info(f"  氢气运输数据为空，跳过氢气路线绘制")
            return

        logger.info(f"  绘制氢气直接运输路线...")

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

        route_count = 0

        for idx, row in h2_df.iterrows():
            # 运输量过滤
            volume = self._get_transport_volume(row, volume_type='kg')
            if volume <= 0.01:
                continue

            # 解析起点和终点坐标
            start_lat, start_lon = parse_coord(row.get('起点坐标'))
            end_lat, end_lon = parse_coord(row.get('终点坐标'))

            if start_lat is None or start_lon is None or end_lat is None or end_lon is None:
                continue

            # 仅绘制起终点均为已标注设施的路线
            if not self._should_draw_route(start_lon, start_lat, end_lon, end_lat):
                continue

            # 严格匹配收集阶段：仅记录端点，不做路径计算与绘制
            if self.collect_only:
                self._record_route_endpoints(start_lon, start_lat, end_lon, end_lat)
                route_count += 1
                continue

            # 【修改】直接使用管道计算器现场计算路径，不使用预存的路径坐标
            route_coords = None
            pipeline_path = self._get_pipeline_route_coords(start_lat, start_lon, end_lat, end_lon)
            if pipeline_path and len(pipeline_path) >= 2:
                route_coords = pipeline_path

            # 回退：使用起终点直线
            if route_coords is None:
                route_coords = [(start_lon, start_lat), (end_lon, end_lat)]

            lons = [coord[0] for coord in route_coords]
            lats = [coord[1] for coord in route_coords]
            ax.plot(
                lons, lats,
                color=self.transport_colors['H2'],
                alpha=0.6,
                linewidth=1.2,
                linestyle='-',
                zorder=7,
                transform=self.data_crs
            )
            self._update_drawn_bounds(lons, lats)
            if not self.collect_only:
                self.global_route_legend['h2'] = True
            route_count += 1

        logger.info(f"    ✓ 氢气直接运输路线: {route_count} 条")

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
            # 【修复】使用统一的运输量获取方法（支持自动降级：周运输量 -> 日运输量×7）
            # 天然气优先尝试kg，降级到m³
            volume = self._get_transport_volume(row, volume_type='kg')
            if volume <= 0.01:
                volume = self._get_transport_volume(row, volume_type='m³')

            if volume <= 0.01:
                continue

            # 解析聚类信息 "聚类0_(中心:36.2153,114.4731)"
            cluster_info = row.get('聚类信息', '')
            if not cluster_info or pd.isna(cluster_info):
                continue

            # 【修复】优先从聚类信息字符串中提取嵌入的聚类中心坐标
            # 因为JSON文件可能与transport_summary不同步
            try:
                import re
                cluster_id = int(cluster_info.split('聚类')[1].split('_')[0])

                # 尝试从聚类信息中提取中心坐标 "聚类0_(中心:37.2003,118.4270)"
                center_match = re.search(r'中心:([\d.]+),([\d.]+)', str(cluster_info))
                if center_match:
                    # 使用嵌入的坐标（更准确，与实际优化结果一致）
                    center_lat = float(center_match.group(1))
                    center_lon = float(center_match.group(2))
                elif cluster_id in all_cluster_centers:
                    # 回退：使用JSON文件中的坐标
                    center_lat, center_lon = all_cluster_centers[cluster_id]
                else:
                    continue

            except:
                continue

            # 解析起点和终点坐标
            start_lat, start_lon = parse_coord(row.get('起点坐标'))
            end_lat, end_lon = parse_coord(row.get('终点坐标'))

            if start_lat is None or start_lon is None:
                continue
            if end_lat is None or end_lon is None:
                continue

            # 仅绘制起终点均为已标注设施的路线
            if not self._should_draw_route(start_lon, start_lat, end_lon, end_lat):
                continue

            # 严格匹配收集阶段：仅记录端点，不做路径计算与绘制
            if self.collect_only:
                layer1_dist = row.get('Layer1距离(km)', 0)
                if layer1_dist > 0 and self._should_draw_route(start_lon, start_lat, center_lon, center_lat):
                    self._record_route_endpoints(start_lon, start_lat, None, None)
                layer2_dist = row.get('Layer2距离(km)', 0)
                if layer2_dist > 0 and self._should_draw_route(center_lon, center_lat, end_lon, end_lat):
                    self._record_route_endpoints(None, None, end_lon, end_lat)
                continue

            # 通过过滤后再标记聚类中心为已使用
            used_cluster_centers[cluster_id] = (center_lat, center_lon)

            # Layer1: 天然气管道节点 → 天然气聚类中心 (lime green虚线)
            layer1_dist = row.get('Layer1距离(km)', 0)
            if layer1_dist > 0 and self._should_draw_route(start_lon, start_lat, center_lon, center_lat):
                ax.plot(
                    [start_lon, center_lon],
                    [start_lat, center_lat],
                    color=self.transport_colors['NG'],
                    alpha=0.4,
                    linewidth=0.8,
                    linestyle='--',
                    zorder=10,
                    transform=self.data_crs
                )
                self._update_drawn_bounds([start_lon, center_lon], [start_lat, center_lat])
                if not self.collect_only:
                    self.global_route_legend['ng'] = True
                layer1_count += 1

            # Layer2: 天然气聚类中心 → SAF工厂 (lime green实线)
            layer2_dist = row.get('Layer2距离(km)', 0)
            if layer2_dist > 0 and end_lat is not None and end_lon is not None \
                    and self._should_draw_route(center_lon, center_lat, end_lon, end_lat):
                ax.plot(
                    [center_lon, end_lon],
                    [center_lat, end_lat],
                    color=self.transport_colors['NG'],
                    alpha=0.8,
                    linewidth=2.0,
                    linestyle='-',
                    zorder=14,
                    transform=self.data_crs
                )
                self._update_drawn_bounds([center_lon, end_lon], [center_lat, end_lat])
                if not self.collect_only:
                    self.global_route_legend['ng'] = True
                layer2_count += 1

        # 【关键修改】只绘制实际使用的天然气聚类中心
        # 聚类中心点不再绘制

        logger.info(f"    ✓ Layer1: {layer1_count} 条（管道节点→聚类中心）")
        logger.info(f"    ✓ Layer2: {layer2_count} 条（聚类中心→SAF工厂）")
        logger.info(f"    ✓ 实际使用的聚类中心: {len(used_cluster_centers)} 个（总共{len(all_cluster_centers)}个）")


    def plot_facilities(self, ax, transport_summary, module_name, complete_solution=None):
        """
        绘制设施位置（三维张量分类: 原材料类型 × SAF生产 × 消纳地）

        Args:
            ax: matplotlib axes对象
            transport_summary: 运输汇总数据
            module_name: 模块名称
            complete_solution: 完整解决方案数据（包含设施决策，可选）

        Returns:
            facility_classification: 设施分类统计字典
        """
        if transport_summary is None:
            logger.warning("  运输汇总数据为None，跳过设施绘制")
            self.visible_facility_coords = set()
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
        # 第一步: 统计每个设施的总产量（作为起点发出的货物总量）
        facility_production = {}  # {(lon, lat): {'氢气': total_kg, 'CO2': total_kg, ...}}
        facility_info = {}  # {(lon, lat): {'names': set(), 'types': set(), 'cargos_as_source': set(), 'cargos_as_dest': set()}}

        total_rows = len(transport_summary)

        # 第一遍：统计每个设施作为起点的货物总产量
        for _, row in transport_summary.iterrows():
            # 【修复】使用统一的运输量获取方法（支持自动降级：周运输量 -> 日运输量×7）
            # 优先尝试kg，降级到m³
            volume = self._get_transport_volume(row, volume_type='kg')
            if volume <= 0.01:
                volume = self._get_transport_volume(row, volume_type='m³')

            # 跳过运输量≤0.01或NaN的记录
            if volume <= 0.01:
                continue

            cargo_type = row.get('货物类型', '')
            start_lat, start_lon = parse_coord(row.get('起点坐标'))

            # 统计起点的产量
            if start_lat is not None and start_lon is not None and cargo_type:
                coord_key = (start_lon, start_lat)
                if coord_key not in facility_production:
                    facility_production[coord_key] = {}
                if cargo_type not in facility_production[coord_key]:
                    facility_production[coord_key][cargo_type] = 0
                facility_production[coord_key][cargo_type] += volume

        # 第二遍：收集设施信息，只收集有产量的设施
        filtered_rows = 0
        for _, row in transport_summary.iterrows():
            # 【修复】使用统一的运输量获取方法（支持自动降级：周运输量 -> 日运输量×7）
            # 优先尝试kg，降级到m³
            volume = self._get_transport_volume(row, volume_type='kg')
            if volume <= 0.01:
                volume = self._get_transport_volume(row, volume_type='m³')

            # 跳过运输量≤0.01或NaN的记录
            if volume <= 0.01:
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
            # 【关键】只收集有产量的设施（在facility_production中存在）
            if start_lat is not None and start_lon is not None and start_name:
                coord_key = (start_lon, start_lat)

                # 只有该设施有产量才收集
                if coord_key in facility_production:
                    if coord_key not in facility_info:
                        facility_info[coord_key] = {'names': set(), 'types': set(), 'cargos_as_source': set(), 'cargos_as_dest': set()}

                    facility_info[coord_key]['names'].add(start_name)
                    if start_type:
                        facility_info[coord_key]['types'].add(start_type)
                    # 只有作为起点发出的货物才记录到cargos_as_source（用于判断原材料生产能力）
                    if cargo_type:
                        facility_info[coord_key]['cargos_as_source'].add(cargo_type)

            # 收集终点：使用纯坐标作为key
            # 【修改】也检查终点是否有产量，如果没有产量则作为纯消纳地
            if end_lat is not None and end_lon is not None and end_name:
                coord_key = (end_lon, end_lat)

                # 如果终点也有产量（既是消纳地也是生产地），或者是纯消纳地，都收集
                # 纯消纳地的判断：不在facility_production中，或者在但所有产量都为0
                is_pure_consumer = coord_key not in facility_production

                # 无论是否有产量，终点都要收集（消纳地也需要显示）
                if coord_key not in facility_info:
                    facility_info[coord_key] = {'names': set(), 'types': set(), 'cargos_as_source': set(), 'cargos_as_dest': set()}

                facility_info[coord_key]['names'].add(end_name)
                if end_type:
                    facility_info[coord_key]['types'].add(end_type)
                # 记录作为终点接收的货物（用于判断是否为消纳地）
                if cargo_type:
                    facility_info[coord_key]['cargos_as_dest'].add(cargo_type)

        logger.info(f"    运输记录总数: {total_rows}, 过滤掉运输量为0的记录: {filtered_rows} 条")
        logger.info(f"    统计到的有产量设施数: {len(facility_production)}")
        logger.info(f"    收集到的唯一坐标位置数（包括消纳地）: {len(facility_info)}")

        # 【新增】从complete_solution中提取机场建设的SAF工厂（产量>1kg）
        # 这些设施可能不在transport_summary中，因为SAF直接在机场消纳，无需运输
        if complete_solution is not None:
            facilities = complete_solution.get('facilities', {})
            added_airport_facilities = 0
            for facility_id, facility_data in facilities.items():
                # 只处理已建设的设施
                if not facility_data.get('built', False):
                    continue

                # 检查是否为机场建设的SAF工厂
                location_type = facility_data.get('location_type', '')
                source_type = facility_data.get('source_type', '')
                actual_production = facility_data.get('actual_annual_production_kg', 0)

                # 判断是否为机场SAF工厂（产量>1kg）
                is_airport_facility = (
                    'airport' in location_type.lower() or
                    'airport' in source_type.lower()
                )

                if is_airport_facility and actual_production > 1:
                    lat = facility_data.get('latitude')
                    lon = facility_data.get('longitude')

                    if lat is not None and lon is not None:
                        coord_key = (lon, lat)

                        # 如果该坐标还没有被记录，添加到facility_info中
                        if coord_key not in facility_info:
                            facility_name = facility_data.get('name', f'机场SAF工厂_{facility_id}')
                            source_id = facility_data.get('source_id', '')

                            facility_info[coord_key] = {
                                'names': {facility_name},
                                'types': {'airport', location_type},
                                'cargos_as_source': {'MTJ'},  # 生产SAF/MTJ
                                'cargos_as_dest': {'MTJ'}  # 同时消纳SAF（机场就地消纳）
                            }

                            # 同时添加到facility_production中
                            # 将年产量转换为周产量（假设均匀生产）
                            weekly_production = actual_production / 52
                            facility_production[coord_key] = {'MTJ': weekly_production}

                            added_airport_facilities += 1
                            logger.info(f"    + 添加机场SAF工厂: {facility_name} @ ({lat:.4f}, {lon:.4f}), "
                                       f"年产量: {actual_production/1e6:.2f} 百万kg")
                        else:
                            # 如果坐标已存在，确保标记为SAF生产地和消纳地
                            facility_info[coord_key]['cargos_as_source'].add('MTJ')
                            facility_info[coord_key]['cargos_as_dest'].add('MTJ')

            if added_airport_facilities > 0:
                logger.info(f"    从complete_solution添加了 {added_airport_facilities} 个机场SAF工厂")

        # 【关键修复】从complete_solution中提取所有已建设的electrolyzer设施
        # 这些设施可能本地生产本地消耗氢气，不在transport_summary中体现
        built_electrolyzers = {}  # {(lon, lat): {'h2_production_kg_year': X, 'location_name': Y}}
        if complete_solution is not None:
            facilities = complete_solution.get('facilities', {})

            # 首先从transport_summary中提取所有位置的坐标映射
            location_coords = {}  # {location_name: (lat, lon)}
            for _, row in transport_summary.iterrows():
                start_name = row.get('起点', '')
                start_coord_str = row.get('起点坐标', '')
                if start_name and start_coord_str:
                    lat, lon = parse_coord(start_coord_str)
                    if lat is not None and lon is not None:
                        location_coords[start_name] = (lat, lon)

                end_name = row.get('终点', '')
                end_coord_str = row.get('终点坐标', '')
                if end_name and end_coord_str:
                    lat, lon = parse_coord(end_coord_str)
                    if lat is not None and lon is not None:
                        location_coords[end_name] = (lat, lon)

            for facility_id, facility_data in facilities.items():
                # 只处理已建设的电解槽设施
                if not facility_data.get('built', False):
                    continue

                tech = facility_data.get('technology', '')
                if tech == 'electrolyzer':
                    h2_production = facility_data.get('actual_annual_production_kg', 0)
                    location_name = facility_data.get('location', facility_id)

                    # 从location_coords映射中查找坐标
                    if location_name in location_coords:
                        lat, lon = location_coords[location_name]
                        coord_key = (lon, lat)

                        if h2_production > 1:
                            built_electrolyzers[coord_key] = {
                                'h2_production_kg_year': h2_production,
                                'location_name': location_name
                            }

                            # 如果该坐标还不在facility_info中，添加进去
                            if coord_key not in facility_info:
                                facility_info[coord_key] = {
                                    'names': {location_name},
                                    'types': {'wind_farm', 'solar_plant'},  # 电解槽通常在可再生能源站
                                    'cargos_as_source': set(),  # 本地消耗，不作为运输起点
                                    'cargos_as_dest': set()
                                }
                                logger.info(f"    + 添加本地生产氢气设施: {location_name[:60]} @ ({lat:.4f}, {lon:.4f}), "
                                           f"年产量: {h2_production/1e6:.2f} M kg H2/年")
                            else:
                                # 如果坐标已存在，确保名称被添加
                                facility_info[coord_key]['names'].add(location_name)

            if len(built_electrolyzers) > 0:
                logger.info(f"    从complete_solution提取了 {len(built_electrolyzers)} 个电解槽设施（含本地生产本地消耗）")

        # 【特殊处理】天然气两步法：过滤掉纯SAF生产点且产量≤10kg的设施
        if module_name == 'Natural Gas Two-Step':
            filtered_facility_info = {}
            filtered_count = 0
            for coord, info in facility_info.items():
                # 使用facility_production检查SAF产量
                saf_volume = 0
                if coord in facility_production and 'MTJ' in facility_production[coord]:
                    saf_volume = facility_production[coord]['MTJ']

                # 【修复】检查是否为纯SAF生产点（只生产SAF，不生产氢气、CO2等其他货物）
                is_pure_saf_producer = (info['cargos_as_source'] == {'MTJ'})

                # 保留条件：
                # 1. SAF产量>10kg，或
                # 2. 不是纯SAF生产点（还生产氢气/CO2等其他货物），或
                # 3. 不生产SAF（原材料供应点、消纳地）
                if saf_volume > 10 or not is_pure_saf_producer:
                    filtered_facility_info[coord] = info
                else:
                    filtered_count += 1

            logger.info(f"    天然气两步法筛选：过滤掉纯SAF生产点（产量≤10kg）{filtered_count} 个")
            logger.info(f"    保留的设施数: {len(filtered_facility_info)}")
            facility_info = filtered_facility_info

        # 【严格匹配模式】仅保留与线路端点匹配的设施
        if self.strict_match_mode and self.strict_match_coord_keys is not None:
            def _is_airport_production(info):
                if not self.strict_match_keep_airport_production:
                    return False
                cargos = info.get('cargos_as_source', set())
                if 'MTJ' not in cargos and 'SAF' not in cargos:
                    return False
                types_lower = {str(t).lower() for t in info.get('types', set())}
                names_lower = {str(n).lower() for n in info.get('names', set())}
                if any('airport' in t or '机场' in t for t in types_lower):
                    return True
                if any('airport' in n or '机场' in n for n in names_lower):
                    return True
                return False

            before_count = len(facility_info)
            facility_info = {
                coord: info for coord, info in facility_info.items()
                if self._coord_key(coord[0], coord[1]) in self.strict_match_coord_keys
                or _is_airport_production(info)
            }
            logger.info(f"    严格匹配模式：仅保留与线路端点匹配的设施 {len(facility_info)}/{before_count}")

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
            self.visible_facility_coords = set()
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

            # 【关键修复】如果该坐标有electrolyzer建设，强制添加'h2'到原材料类型
            # 这样本地生产本地消耗的氢气设施也能正确显示为氢气生产设施
            coord_key = (lon, lat)
            if coord_key in built_electrolyzers:
                raw_materials_set = set(raw_materials)
                if 'h2' not in raw_materials_set:
                    raw_materials_set.add('h2')
                    raw_materials = frozenset(raw_materials_set)
                    h2_prod = built_electrolyzers[coord_key]['h2_production_kg_year']
                    logger.info(f"    修正设施分类 ({lon:.4f}, {lat:.4f}): 添加H2生产能力 "
                              f"({h2_prod/1e6:.2f} M kg/年，本地生产本地消耗）")

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
        skipped_outside = 0
        plotted_coords = []

        # 用于统计分类组合（用于图例）
        classification_stats = {}

        for (lon, lat), (raw_materials, saf_production, consumption) in facility_classifications.items():
            # 仅绘制当前可视范围内的设施
            if not self._in_extent(lon, lat):
                skipped_outside += 1
                continue
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
            self._update_drawn_bounds([lon], [lat])

            total_facilities_plotted += 1
            plotted_coords.append((lon, lat))

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
                combined_attrs['multi_material'] = len(raw_materials) > 1
                combined_attrs['has_saf'] = (saf_production == 'yes')

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
                classification_stats[classification_key]['attrs']['has_saf'] = (saf_production == 'yes')
                classification_stats[classification_key]['count'] += 1

        if skipped_outside > 0:
            logger.info(f"    跳过可视范围外设施: {skipped_outside} 个")
        logger.info(f"    总共绘制设施数（唯一坐标位置）: {total_facilities_plotted}")
        logger.info(f"    设施三维张量分类统计（共{len(classification_stats)}种组合）：")
        for (material, saf, cons), stats in sorted(classification_stats.items()):
            logger.info(f"      [{material} × {saf} × {cons}] {stats['count']}个设施")

        # 记录已绘制设施坐标，用于过滤路线（仅保留有点的路线）
        self.visible_facility_coords = {
            self._coord_key(lon, lat) for (lon, lat) in plotted_coords
        }

        # 记录到全局图例（跨场景汇总）
        if not getattr(self, 'collect_only', False):
            for key, stats in classification_stats.items():
                if key not in self.global_facility_legend:
                    self.global_facility_legend[key] = stats['attrs']

        return classification_stats

    def create_individual_module_map(self, module_name: str, collect_bounds_only: bool = False):
        """
        创建单个模块的聚类运输路线地图

        Args:
            module_name: 模块名称
        """
        logger.info(f"\n生成 {module_name} 聚类运输路线地图...")

        config = self.modules[module_name]
        data = self.transport_data[module_name]

        # 若仅收集边界，不保存图片且不绘制图例/装饰
        if collect_bounds_only:
            logger.info(f"  仅收集绘图边界（不保存）")

        # 增加地图尺寸，使其更大更清晰
        base_extent = None
        if self.uniform_extent_mode and self.uniform_extent and not collect_bounds_only:
            base_extent = self.uniform_extent
        fig, ax = self.create_base_map(figsize=(24, 20), extent=base_extent)
        self._reset_drawn_bounds()

        # 先绘制管道网络（作为底层，增加透明度）
        pipeline_stats = {}
        if not collect_bounds_only:
            logger.info(f"  绘制管道网络...")
            pipeline_stats = self.plot_pipeline_networks(ax)

        # 【特殊处理】一步法场景：只画机场和直接运输路线，不绘制聚类路线
        # 包括所有一步法场景：绿氢一步法、DAC一步法、天然气一步法、副产氢一步法、副产氢+DAC一步法
        one_step_scenarios = [
            'Natural Gas One-Step', 'DAC One-Step', 'Green H2 One-Step',
            'Byproduct H2 One-Step', 'Byproduct H2 + DAC One-Step'
        ]

        # 【严格匹配模式】先收集线路端点，再绘制设施与线路
        if self.strict_match_mode:
            logger.info(f"  严格匹配模式：先收集线路端点")
            self.collect_only = True
            self.route_endpoint_coords = set()
            self.strict_match_coord_keys = None
            self.visible_facility_coords = None

            if module_name in one_step_scenarios:
                self.plot_h2_direct_routes(ax, data['transport_summary'])
                self.plot_ng_routes(ax, data['transport_summary'])
                self.plot_co2_routes(ax, data.get('co2_clustering'), data['transport_summary'], module_name)
                self.plot_saf_routes(ax, data['transport_summary'])
            else:
                if data['h2_clustering']:
                    self.plot_h2_clustered_routes(ax, data['h2_clustering'], data['transport_summary'], module_name)
                self.plot_co2_routes(ax, data.get('co2_clustering'), data['transport_summary'], module_name)
                if data['ng_clustering']:
                    self.plot_ng_clustered_routes(ax, data['ng_clustering'], data['transport_summary'], module_name)
                else:
                    self.plot_ng_routes(ax, data['transport_summary'])
                self.plot_saf_routes(ax, data['transport_summary'])

            self.collect_only = False
            self.strict_match_coord_keys = set(self.route_endpoint_coords)
            logger.info(f"  严格匹配模式：收集到线路端点 {len(self.strict_match_coord_keys)} 个")

        # 先绘制设施（并建立可见点集合），用于过滤后续路线绘制
        facility_classification = self.plot_facilities(
            ax, data['transport_summary'], module_name, data.get('complete_solution')
        )

        if module_name in one_step_scenarios:
            logger.info(f"  {module_name}场景：一步法工艺，只绘制直接运输路线和机场设施")
            # 绘制氢气直接运输路线（如果有）
            self.plot_h2_direct_routes(ax, data['transport_summary'])

            # 绘制天然气运输路线（如果有）
            self.plot_ng_routes(ax, data['transport_summary'])

            # 绘制CO2运输路线（如果有）
            self.plot_co2_routes(ax, data.get('co2_clustering'), data['transport_summary'], module_name)

            # 绘制SAF运输路线
            self.plot_saf_routes(ax, data['transport_summary'])
        else:
            # 其他场景的正常处理流程
            # 绘制H2聚类运输路线（如果有H2聚类数据）
            if data['h2_clustering']:
                self.plot_h2_clustered_routes(ax, data['h2_clustering'], data['transport_summary'], module_name)

            # 绘制CO2运输路线（如果有）
            self.plot_co2_routes(ax, data.get('co2_clustering'), data['transport_summary'], module_name)

            # 绘制天然气聚类运输路线（如果有天然气聚类数据）
            if data['ng_clustering']:
                self.plot_ng_clustered_routes(ax, data['ng_clustering'], data['transport_summary'], module_name)
            else:
                # 如果没有天然气聚类，绘制普通天然气运输路线
                self.plot_ng_routes(ax, data['transport_summary'])

            # 绘制SAF运输路线
            self.plot_saf_routes(ax, data['transport_summary'])

        # 自动收缩范围（仅保留点和线）
        self._apply_tight_extent(ax)

        if collect_bounds_only:
            plt.close(fig)
            return self.drawn_bounds

        # 添加装饰元素
        self.add_decorations(ax)

        # 添加图例（分三部分：路线、设施三维分类矩阵、管道网络）
        # 优化：使用 Custom Legend Handler 或 更好的布局
        
        legend_elements = [
            # === 路线图例 ===
            Line2D([0], [0], color=self.transport_colors['H2'], linewidth=1.5,
                   label='Hydrogen Transport Route'),
            Line2D([0], [0], color=self.transport_colors['CO2'], linewidth=1.5,
                   label='Carbon Dioxide Transport Route'),
            Line2D([0], [0], color=self.transport_colors['NG'], linewidth=2,
                   label='Natural Gas Transport Route'),
            Line2D([0], [0], color=self.transport_colors['SAF'], linewidth=2,
                   label='SAF Truck Transport Route'),
        ]

        # === 设施三维张量分类矩阵图例 ===
        legend_elements.append(Line2D([0], [0], marker='', color='w', label=''))  # 空行
        legend_elements.append(Line2D([0], [0], marker='', color='w',
                                     label=r'$\bf{Facility\ Classification}$', markerfacecolor='w')) # Bold styling
        # legend_elements.append(Line2D([0], [0], marker='', color='w',
        #                              label='Raw Material × SAF Prod × Consumer', markerfacecolor='w')) # Too long

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
                    label = f"{attrs['combined_label']}"
                else:
                    label = f"{attrs['full_label']}"

                short_label = self._format_legend_label(attrs)

                legend_marker = attrs['marker']
                legend_edge = attrs['edgecolor']
                legend_width = attrs['linewidth']
                legend_size = 24
                if attrs.get('multi_material'):
                    # 多原材料组合：按是否包含SAF生产区分
                    has_saf = bool(attrs.get('has_saf'))
                    legend_marker = 'P' if has_saf else 'X'
                    legend_edge = '#000000'
                    legend_width = max(1.5, attrs['linewidth'])
                    legend_size = 24 if has_saf else 22

                # 机场和自定义图标在legend中容易偏小，额外放大并增强边界对比
                if 'Airport' in short_label:
                    # 飞机图标横向细节较多，legend里需要更大尺寸才清晰
                    legend_size = max(legend_size, 40)
                    legend_width = max(2.6, legend_width)
                    if legend_edge in ('white', '#FFFFFF', '#ffffff'):
                        legend_edge = '#333333'
                elif not isinstance(legend_marker, str):
                    legend_size = max(legend_size, 30)
                    legend_width = max(1.8, legend_width)

                legend_elements.append(
                    Line2D([0], [0], marker=legend_marker, color='w',
                          markerfacecolor=attrs['color'],
                          markersize=legend_size,  # 增加图例标记大小
                          markeredgecolor=legend_edge,
                          markeredgewidth=legend_width,
                          label=short_label)
                )

        # 添加管道网络图例
        legend_elements.append(Line2D([0], [0], marker='', color='w', label=''))  # 空行
        legend_elements.append(Line2D([0], [0], marker='', color='w',
                                     label=r'$\bf{Pipeline\ Network}$', markerfacecolor='w'))

        pipeline_names_en = {
            'crude': 'Crude Oil',
            'refined': 'Product Oil',
            'natural_gas': 'Natural Gas'
        }
        
        # 稍微加深图例颜色以便可见
        pipeline_colors_legend = {
            'crude': '#8c510a',
            'refined': '#d8b365',
            'natural_gas': '#5ab4ac'
        }

        for pipeline_type, count in pipeline_stats.items():
            if count > 0:
                legend_elements.append(
                    Line2D([0], [0], color=pipeline_colors_legend[pipeline_type],
                          linewidth=1.5, alpha=1.0, # 图例中完全不透明
                          label=f'{pipeline_names_en[pipeline_type]}')
                )

        # 将图例放到图外右侧，且样式更加精简
        # 调整bbox_to_anchor以适应新的图片尺寸
        if self.render_individual_legends:
            ax.legend(
                handles=legend_elements,
                loc='upper left', bbox_to_anchor=(1.01, 0.95),
                fontsize=5.5 * FONT_SCALE,   # 你要缩小一半就用 5.5*FONT_SCALE（原来是11*FONT_SCALE）
                framealpha=0.9,
                edgecolor='#D3D3D3',
                ncol=1, borderpad=1.0, labelspacing=0.8
)
        # 按需求移除单图标题，标题信息由论文图注承载

        # 调整布局
        if self.render_individual_legends:
            plt.tight_layout(rect=[0, 0, 0.85, 1])  # 为右侧图例留出空间
        else:
            plt.tight_layout()

        # 保存图片
        output_path = self.session_dir / f"clustered_map_{module_name.replace(' ', '_').lower()}.png"
        plt.savefig(output_path, dpi=OUTPUT_DPI, bbox_inches='tight')
        logger.info(f"  ✓ 保存图片: {output_path}")
        plt.close()

    def run_all_visualizations(self):
        """运行所有可视化"""
        logger.info("\n" + "=" * 60)
        logger.info("开始生成聚类地图可视化")
        logger.info("=" * 60)

        try:
            # 统一范围模式：先收集全局边界
            if self.uniform_extent_mode:
                logger.info("\n收集全局显示范围（用于统一所有场景）...")
                global_bounds = None
                self.ignore_extent_filter = True
                for module_name in self.modules.keys():
                    bounds = self.create_individual_module_map(module_name, collect_bounds_only=True)
                    if bounds is None:
                        continue
                    if global_bounds is None:
                        global_bounds = bounds[:]
                    else:
                        global_bounds[0] = min(global_bounds[0], bounds[0])
                        global_bounds[1] = max(global_bounds[1], bounds[1])
                        global_bounds[2] = min(global_bounds[2], bounds[2])
                        global_bounds[3] = max(global_bounds[3], bounds[3])

                self.ignore_extent_filter = False

                if global_bounds is not None:
                    min_lon, max_lon, min_lat, max_lat = global_bounds
                    lon_span = max_lon - min_lon
                    lat_span = max_lat - min_lat
                    pad_lon = max(0.1, lon_span * 0.05)
                    pad_lat = max(0.1, lat_span * 0.05)
                    self.uniform_extent = [
                        min_lon - pad_lon, max_lon + pad_lon,
                        min_lat - pad_lat, max_lat + pad_lat
                    ]
                    logger.info(f"  ✓ 统一范围: {self.uniform_extent}")
                else:
                    logger.warning("  未能收集到全局范围，使用默认范围")

            # 生成各模块独立地图
            for module_name in self.modules.keys():
                self.create_individual_module_map(module_name)

            # 生成综合图例
            self.create_global_legend()

            logger.info("\n" + "=" * 60)
            logger.info("✓ 所有聚类地图可视化生成完成")
            logger.info(f"✓ 输出目录: {self.session_dir}")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"\n✗ 聚类地图可视化生成失败: {e}")
            raise


    def run_four_key_zoom_comparison(self) -> Path:
        """
        仅针对 CCU-GH-FT、GTL、GTL-BH、DAC-BH-FT 四个场景，
        重新计算这4个场景的紧凑地理范围（而非全13场景的大范围），
        以更小的地理范围生成各场景地图，再拼合为2×2对比图。
        """
        FOUR_MODULE_NAMES = [
            'Green H2 One-Step',          # CCU-GH-FT
            'Natural Gas One-Step',        # GTL
            'Byproduct H2 + NG Two-Step',  # GTL-BH
            'Byproduct H2 + DAC One-Step', # DAC-BH-FT
        ]
        FOUR_LABELS = ['(a)  CCU-GH-FT', '(b)  GTL', '(c)  GTL-BH', '(d)  DAC-BH-FT']

        # ── 1. 仅针对这4个场景收集绘图边界 ──────────────────────────────
        logger.info("\n收集四场景紧凑地理范围...")
        saved_extent       = self.uniform_extent
        saved_extent_mode  = self.uniform_extent_mode
        self.uniform_extent_mode  = False   # 临时关闭，让每张图自适应
        self.ignore_extent_filter = True

        global_bounds = None
        for module_name in FOUR_MODULE_NAMES:
            if module_name not in self.transport_data:
                logger.warning("场景 %s 数据未加载，跳过", module_name)
                continue
            bounds = self.create_individual_module_map(module_name, collect_bounds_only=True)
            if bounds is None:
                continue
            if global_bounds is None:
                global_bounds = bounds[:]
            else:
                global_bounds[0] = min(global_bounds[0], bounds[0])
                global_bounds[1] = max(global_bounds[1], bounds[1])
                global_bounds[2] = min(global_bounds[2], bounds[2])
                global_bounds[3] = max(global_bounds[3], bounds[3])

        self.ignore_extent_filter = False

        if global_bounds is None:
            logger.warning("未能收集到四场景边界，回退到全局范围")
            self.uniform_extent      = saved_extent
            self.uniform_extent_mode = saved_extent_mode
        else:
            min_lon, max_lon, min_lat, max_lat = global_bounds
            lon_span = max_lon - min_lon
            lat_span = max_lat - min_lat
            pad_lon  = max(0.1, lon_span * 0.04)
            pad_lat  = max(0.1, lat_span * 0.04)
            self.uniform_extent = [
                min_lon - pad_lon, max_lon + pad_lon,
                min_lat - pad_lat, max_lat + pad_lat,
            ]
            self.uniform_extent_mode = True
            logger.info("四场景紧凑范围: %s", self.uniform_extent)

        # ── 2. 生成各场景地图，保存到独立子目录 ──────────────────────────
        timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir     = self.output_dir / f"four_key_zoom_{timestamp}"
        out_dir.mkdir(parents=True, exist_ok=True)

        # 临时重定向 session_dir
        saved_session_dir    = self.session_dir
        self.session_dir     = out_dir

        png_paths = []
        for module_name in FOUR_MODULE_NAMES:
            if module_name not in self.transport_data:
                continue
            self.create_individual_module_map(module_name)
            slug = module_name.replace(' ', '_').lower()
            png_paths.append(out_dir / f"clustered_map_{slug}.png")

        # 恢复原始状态
        self.session_dir         = saved_session_dir
        self.uniform_extent      = saved_extent
        self.uniform_extent_mode = saved_extent_mode

        # ── 3. 拼合2×2 ──────────────────────────────────────────────────
        comp_path = create_four_key_comparison(out_dir, out_dir)
        logger.info("四场景缩放对比图已生成: %s", comp_path)
        return comp_path


def create_four_key_comparison(source_dir: Path, output_dir: Path | None = None) -> Path:
    """
    将 CCU-GH-FT、GTL、GTL-BH、DAC-BH-FT 四个关键场景的地图
    拼合为 2×2 对比大图（统一地理范围）。

    Args:
        source_dir : 包含 clustered_map_*.png 的目录（已含统一 extent）
        output_dir : 输出目录，默认与 source_dir 相同
    Returns:
        输出 PNG 路径
    """
    from PIL import Image, ImageDraw, ImageFont
    Image.MAX_IMAGE_PIXELS = None   # 关闭像素炸弹检查，允许大图

    # 每个面板的目标宽度（px）；原图可能超 1 亿像素，缩到此宽度后再拼合
    TARGET_PANEL_W = 4800   # ≈ 16" at 300 DPI

    FOUR_SCENARIOS = [
        ("(a)  CCU-GH-FT", "clustered_map_green_h2_one-step.png"),
        ("(b)  GTL",        "clustered_map_natural_gas_one-step.png"),
        ("(c)  GTL-BH",     "clustered_map_byproduct_h2_+_ng_two-step.png"),
        ("(d)  DAC-BH-FT",  "clustered_map_byproduct_h2_+_dac_one-step.png"),
    ]

    source_dir = Path(source_dir)
    if output_dir is None:
        output_dir = source_dir
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    imgs = []
    for label, fname in FOUR_SCENARIOS:
        p = source_dir / fname
        if not p.exists():
            raise FileNotFoundError(f"找不到场景地图文件: {p}")
        imgs.append((label, Image.open(p).convert("RGBA")))

    # 统一缩放：以 TARGET_PANEL_W 为目标宽度，保持宽高比
    raw_w, raw_h = imgs[0][1].size
    scale  = TARGET_PANEL_W / raw_w
    W      = TARGET_PANEL_W
    H      = int(raw_h * scale)
    resized = []
    for label, img in imgs:
        if img.size != (W, H):
            img = img.resize((W, H), Image.LANCZOS)
        resized.append((label, img))
    imgs = resized

    # 面板标签参数
    PAD        = 40          # 面板间距（px）
    LABEL_H    = 120         # 顶部标签区高度（px）
    FONT_SIZE  = 96          # 标签字号（px）

    # 尝试加载 Times New Roman，fallback 到默认字体
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/msttcorefonts/Times_New_Roman_Bold.ttf", FONT_SIZE)
    except Exception:
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Times.ttc", FONT_SIZE)
        except Exception:
            font = ImageFont.load_default()

    # 每个面板总高度 = 标签区 + 地图区
    PANEL_W = W
    PANEL_H = LABEL_H + H

    # 合成图尺寸：2 列 2 行 + 间距
    composite_w = 2 * PANEL_W + 3 * PAD
    composite_h = 2 * PANEL_H + 3 * PAD

    composite = Image.new("RGBA", (composite_w, composite_h), (255, 255, 255, 255))

    positions = [
        (PAD,             PAD),
        (2 * PAD + W,     PAD),
        (PAD,             2 * PAD + PANEL_H),
        (2 * PAD + W,     2 * PAD + PANEL_H),
    ]

    draw = ImageDraw.Draw(composite)

    for idx, ((label, img), (px, py)) in enumerate(zip(imgs, positions)):
        # 白色标签背景
        draw.rectangle([px, py, px + PANEL_W, py + LABEL_H], fill=(255, 255, 255, 255))

        # 标签文字
        try:
            bbox = draw.textbbox((0, 0), label, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
        except AttributeError:
            tw, th = draw.textsize(label, font=font)
        tx = px + (PANEL_W - tw) // 2
        ty = py + (LABEL_H - th) // 2
        draw.text((tx, ty), label, fill=(30, 30, 30, 255), font=font)

        # 地图图像
        composite.paste(img, (px, py + LABEL_H))

    out_path = output_dir / "four_key_scenarios_comparison.png"
    composite.convert("RGB").save(out_path, dpi=(300, 300))
    logger.info("已保存四场景对比图: %s", out_path)
    return out_path


def main():
    """主函数"""
    import sys
    logger.info("=" * 60)
    logger.info("十三场景聚类运输路线地图可视化脚本")
    logger.info("Thirteen Scenarios Clustered Transport Route Map Visualization Script")
    logger.info("=" * 60)

    # 若传入已有目录路径，则只做四场景拼图，不重新跑全量可视化
    if len(sys.argv) > 1 and Path(sys.argv[1]).is_dir():
        source_dir = Path(sys.argv[1])
        logger.info(f"仅生成四场景对比图，源目录: {source_dir}")
        create_four_key_comparison(source_dir)
        logger.info("\n✓ 程序执行成功")
        return

    try:
        # 创建可视化器
        visualizer = ThirteenScenariosClusteredMapVisualizer()

        # 加载数据
        visualizer.load_data()

        # 运行所有可视化
        visualizer.run_all_visualizations()

        # 生成四场景缩放对比图（使用紧凑地理范围）
        visualizer.run_four_key_zoom_comparison()

        logger.info("\n✓ 程序执行成功")

    except Exception as e:
        logger.error(f"\n✗ 程序执行失败: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
