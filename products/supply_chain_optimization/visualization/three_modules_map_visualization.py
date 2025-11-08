"""
三模块运输路线地图可视化
Three Modules Transport Route Map Visualization

使用frykit库生成地理地图可视化
Using frykit library for geographical map visualization

功能 | Features:
1. 氢气运输路线可视化 (Hydrogen transport routes visualization)
2. SAF运输路线可视化 (SAF transport routes visualization)
3. 设施位置标注 (Facility location marking)
4. 三模块对比地图 (Three modules comparison maps)

作者 | Author: Claude Code
创建时间 | Created: 2025-11-06
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple
import logging

import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
from matplotlib import rcParams
from matplotlib.lines import Line2D

# 配置中文字体 - 支持Linux和Windows系统,移除DejaVu Sans避免回退
matplotlib.rcParams['font.sans-serif'] = ['Noto Sans CJK SC', 'Noto Sans CJK TC', 'WenQuanYi Zen Hei', 'Microsoft YaHei', 'SimHei']
matplotlib.rcParams['axes.unicode_minus'] = False

# 添加frykit路径
sys.path.append(str(Path(__file__).parent.parent.parent.parent.parent / "shared"))
import frykit.plot as fplt

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ThreeModulesMapVisualizer:
    """三模块运输路线地图可视化器"""

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
        self.session_dir = self.output_dir / f"transport_maps_{timestamp}"
        self.session_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"输出目录: {self.session_dir}")

        # 模块配置 - 使用自动查找最新文件
        self.modules = {
            'Coal Hydrogen': {
                'name_cn': '煤制氢',
                'color': '#E74C3C',
                'h2_transport_pattern': '../coal_hydrogen_saf_optimization/results/hydrogen_transport_plan_*.csv',
                'mtj_transport_pattern': '../coal_hydrogen_saf_optimization/results/mtj_transport_plan_*.csv'
            },
            'DAC Hydrogen': {
                'name_cn': 'DAC制氢',
                'color': '#3498DB',
                'h2_transport_pattern': '../dac_hydrogen_saf_supply_chain_optimization/results/two_step/hydrogen_transport_plan_*.csv',
                'mtj_transport_pattern': '../dac_hydrogen_saf_supply_chain_optimization/results/two_step/mtj_transport_plan_*.csv'
            },
            'Natural Gas': {
                'name_cn': '天然气',
                'color': '#2ECC71',
                'h2_transport_pattern': '../natural_gas_supply_chain_optimization/results/hydrogen_transport_plan_*.csv',
                'mtj_transport_pattern': '../natural_gas_supply_chain_optimization/results/mtj_transport_plan_*.csv'
            }
        }

        # 地图投影设置
        self.map_crs = fplt.CN_AZIMUTHAL_EQUIDISTANT
        self.data_crs = fplt.PLATE_CARREE

        # 运输类型颜色
        self.transport_colors = {
            'H2': '#1E90FF',       # 氢气 - 道奇蓝
            'SAF': '#FF4500'       # SAF - 橙红色
        }

        # 数据存储
        self.transport_data = {}

    def load_data(self):
        """加载三个模块的运输数据"""
        logger.info("=" * 60)
        logger.info("加载运输数据")
        logger.info("=" * 60)

        base_dir = Path(__file__).parent

        for module_name, config in self.modules.items():
            logger.info(f"\n正在加载: {module_name} ({config['name_cn']})")

            module_data = {
                'h2_transport': None,
                'mtj_transport': None
            }

            try:
                # 加载氢气运输数据（自动查找最新文件）
                import glob
                if 'h2_transport_pattern' in config:
                    h2_pattern = (base_dir / config['h2_transport_pattern']).resolve()
                    h2_files = sorted(glob.glob(str(h2_pattern)), reverse=True)

                    if h2_files:
                        h2_file = Path(h2_files[0])
                        logger.info(f"  使用最新的氢气运输文件: {h2_file.name}")
                        module_data['h2_transport'] = pd.read_csv(h2_file, encoding='utf-8')
                        logger.info(f"  ✓ 氢气运输路线: {len(module_data['h2_transport'])} 条")
                    else:
                        logger.warning(f"  ⚠ 未找到氢气运输文件: {config['h2_transport_pattern']}")

                # 加载SAF运输数据（自动查找最新文件）
                mtj_pattern = (base_dir / config['mtj_transport_pattern']).resolve()
                mtj_files = sorted(glob.glob(str(mtj_pattern)), reverse=True)

                if mtj_files:
                    mtj_file = Path(mtj_files[0])
                    logger.info(f"  使用最新的SAF运输文件: {mtj_file.name}")
                    module_data['mtj_transport'] = pd.read_csv(mtj_file, encoding='utf-8')
                    logger.info(f"  ✓ SAF运输路线: {len(module_data['mtj_transport'])} 条")
                else:
                    logger.warning(f"  ⚠ 未找到SAF运输文件: {config['mtj_transport_pattern']}")

                self.transport_data[module_name] = module_data

            except Exception as e:
                logger.error(f"  ✗ 加载失败: {e}")
                import traceback
                traceback.print_exc()
                raise

        logger.info("\n" + "=" * 60)
        logger.info("数据加载完成")
        logger.info("=" * 60)

    def create_base_map(self, figsize=(16, 12), extent=None):
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

    def plot_transport_routes(self, ax, h2_df, mtj_df, module_name, module_color):
        """
        绘制运输路线（使用直线，因为CSV没有详细路径坐标）

        Args:
            ax: matplotlib axes对象
            h2_df: 氢气运输数据
            mtj_df: SAF运输数据
            module_name: 模块名称
            module_color: 模块颜色
        """
        # 绘制氢气运输路线
        if h2_df is not None and len(h2_df) > 0:
            volumes = h2_df['氢气运输量(kg)'].values
            max_volume = volumes.max()
            min_volume = volumes.min()

            for idx, row in h2_df.iterrows():
                start_lon, start_lat = row['起点经度'], row['起点纬度']
                end_lon, end_lat = row['终点经度'], row['终点纬度']
                volume = row['氢气运输量(kg)']

                # 跳过无效坐标
                if pd.isna(start_lon) or pd.isna(start_lat) or pd.isna(end_lon) or pd.isna(end_lat):
                    continue

                # 计算线宽（基于运输量）
                if max_volume > min_volume:
                    linewidth = 0.5 + 1.5 * (volume - min_volume) / (max_volume - min_volume)
                else:
                    linewidth = 1.0

                # 绘制路线（虚线表示管道运输）
                transport_mode = row.get('运输方式', 'pipeline')
                linestyle = '--' if transport_mode == 'pipeline' else '-'

                ax.plot([start_lon, end_lon], [start_lat, end_lat],
                       color=self.transport_colors['H2'],
                       linewidth=linewidth,
                       alpha=0.7,
                       linestyle=linestyle,
                       transform=self.data_crs,
                       zorder=4)

        # 绘制SAF运输路线
        if mtj_df is not None and len(mtj_df) > 0:
            volumes = mtj_df['运输量(kg)'].values
            max_volume = volumes.max()
            min_volume = volumes.min()

            for idx, row in mtj_df.iterrows():
                start_lon, start_lat = row['起点经度'], row['起点纬度']
                end_lon, end_lat = row['终点经度'], row['终点纬度']
                volume = row['运输量(kg)']

                # 跳过无效坐标
                if pd.isna(start_lon) or pd.isna(start_lat) or pd.isna(end_lon) or pd.isna(end_lat):
                    continue

                # 计算线宽（基于运输量）
                if max_volume > min_volume:
                    linewidth = 0.5 + 1.5 * (volume - min_volume) / (max_volume - min_volume)
                else:
                    linewidth = 1.0

                # 绘制路线（实线表示卡车运输）
                ax.plot([start_lon, end_lon], [start_lat, end_lat],
                       color=self.transport_colors['SAF'],
                       linewidth=linewidth,
                       alpha=0.7,
                       transform=self.data_crs,
                       zorder=4)

    def plot_facilities(self, ax, h2_df, mtj_df):
        """
        绘制设施位置

        Args:
            ax: matplotlib axes对象
            h2_df: 氢气运输数据
            mtj_df: SAF运输数据
        """
        # 从运输数据中提取所有唯一位置
        all_locations = set()

        if h2_df is not None:
            for _, row in h2_df.iterrows():
                if not pd.isna(row['起点经度']) and not pd.isna(row['起点纬度']):
                    all_locations.add((row['起点经度'], row['起点纬度'], row['起点']))
                if not pd.isna(row['终点经度']) and not pd.isna(row['终点纬度']):
                    all_locations.add((row['终点经度'], row['终点纬度'], row['终点']))

        if mtj_df is not None:
            for _, row in mtj_df.iterrows():
                if not pd.isna(row['起点经度']) and not pd.isna(row['起点纬度']):
                    all_locations.add((row['起点经度'], row['起点纬度'], row['起点']))
                if not pd.isna(row['终点经度']) and not pd.isna(row['终点纬度']):
                    all_locations.add((row['终点经度'], row['终点纬度'], row['终点']))

        # 绘制所有设施点
        if all_locations:
            lons = [loc[0] for loc in all_locations]
            lats = [loc[1] for loc in all_locations]

            ax.scatter(lons, lats,
                      marker='o',
                      c='red',
                      s=50,
                      alpha=0.8,
                      edgecolors='black',
                      linewidth=0.5,
                      transform=self.data_crs,
                      zorder=5)

    def plot_pipeline_networks(self, ax):
        """
        绘制管道网络（从GeoJSON文件加载）

        Args:
            ax: matplotlib axes对象
        """
        # 管道类型配置
        pipeline_types = {
            'crude': {
                'name': '原油管道',
                'color': '#8B4513',  # 棕色
                'alpha': 0.6,
                'linewidth': 1.5,
                'file': 'crude_pipelines.geojson'
            },
            'refined': {
                'name': '成品油管道',
                'color': '#FF6B35',  # 橙红色
                'alpha': 0.6,
                'linewidth': 1.5,
                'file': 'refined_product_pipelines.geojson'
            },
            'natural_gas': {
                'name': '天然气管道',
                'color': '#4169E1',  # 皇家蓝
                'alpha': 0.8,
                'linewidth': 2.0,
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

    def create_individual_module_map(self, module_name: str):
        """
        创建单个模块的运输路线地图（包含管道网络）

        Args:
            module_name: 模块名称
        """
        logger.info(f"\n生成 {module_name} 运输路线地图...")

        config = self.modules[module_name]
        data = self.transport_data[module_name]

        fig, ax = self.create_base_map(figsize=(16, 12))

        # 先绘制管道网络（作为底层）
        logger.info(f"  绘制管道网络...")
        pipeline_stats = self.plot_pipeline_networks(ax)

        # 绘制运输路线
        self.plot_transport_routes(ax, data['h2_transport'], data['mtj_transport'],
                                   module_name, config['color'])

        # 绘制设施位置
        self.plot_facilities(ax, data['h2_transport'], data['mtj_transport'])

        # 添加装饰元素（指北针和比例尺）
        self.add_decorations(ax)

        # 添加图例
        legend_elements = [
            Line2D([0], [0], color=self.transport_colors['H2'], linewidth=2,
                   linestyle='--', label='氢气管道运输 H₂ Pipeline'),
            Line2D([0], [0], color=self.transport_colors['SAF'], linewidth=2,
                   label='SAF卡车运输 SAF Truck'),
            Line2D([0], [0], marker='o', color='w', markerfacecolor='red',
                   markersize=8, label='设施 Facilities'),
        ]

        # 添加管道网络图例
        pipeline_names = {
            'crude': '原油管道 Crude Oil',
            'refined': '成品油管道 Refined Products',
            'natural_gas': '天然气管道 Natural Gas'
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
                          linewidth=2, alpha=0.7,
                          label=f'{pipeline_names[pipeline_type]} ({count}段)')
                )

        # 将图例放到图外右侧
        ax.legend(handles=legend_elements, loc='center left', bbox_to_anchor=(1.02, 0.5),
                 fontsize=10, framealpha=0.9)

        # 添加标题
        h2_count = len(data['h2_transport']) if data['h2_transport'] is not None else 0
        mtj_count = len(data['mtj_transport']) if data['mtj_transport'] is not None else 0
        total_pipelines = sum(pipeline_stats.values())

        title = (f"{config['name_cn']} SAF供应链运输路线图\n"
                f"{module_name} SAF Supply Chain Transport Routes\n"
                f"H₂路线: {h2_count} 条 | SAF路线: {mtj_count} 条 | 管道: {total_pipelines} 段")
        ax.set_title(title, fontsize=14, fontweight='bold', pad=20)

        # 调整布局以容纳外部图例
        plt.tight_layout(rect=[0, 0, 0.85, 1])  # 为右侧图例留出空间

        # 保存图片
        output_path = self.session_dir / f"transport_map_{module_name.replace(' ', '_').lower()}.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        logger.info(f"  ✓ 保存图片: {output_path}")
        plt.close()

    def create_comparison_map(self):
        """创建三模块对比地图"""
        logger.info("\n生成三模块对比地图...")

        # 创建2x2子图,为图例留出专门空间
        fig = plt.figure(figsize=(22, 16))

        # 为每个模块创建子图
        for idx, (module_name, config) in enumerate(self.modules.items(), 1):
            ax = fig.add_subplot(2, 2, idx, projection=self.map_crs)

            # 设置地图范围 - 扩大到44°N
            ax.set_extent([111, 121, 35, 44], crs=self.data_crs)

            # 添加中国地图底图
            fplt.add_cn_province(ax, lw=0.5, ec='gray', fc='none', alpha=0.5)

            # 添加网格
            gl = ax.gridlines(draw_labels=True, linewidth=0.5, color='gray',
                            alpha=0.3, linestyle='--', crs=self.data_crs)
            gl.top_labels = False
            gl.right_labels = False

            # 绘制运输路线
            data = self.transport_data[module_name]
            self.plot_transport_routes(ax, data['h2_transport'], data['mtj_transport'],
                                      module_name, config['color'])
            self.plot_facilities(ax, data['h2_transport'], data['mtj_transport'])

            # 添加子图标题
            h2_count = len(data['h2_transport']) if data['h2_transport'] is not None else 0
            mtj_count = len(data['mtj_transport']) if data['mtj_transport'] is not None else 0
            subtitle = f"{config['name_cn']} | H₂: {h2_count} 条, SAF: {mtj_count} 条"
            ax.set_title(subtitle, fontsize=12, fontweight='bold', pad=10)

        # 添加总标题
        fig.suptitle('三模块SAF供应链运输路线对比\nThree Modules SAF Supply Chain Transport Routes Comparison',
                    fontsize=16, fontweight='bold', y=0.98)

        # 添加图例（放在第四个子图位置）
        ax_legend = fig.add_subplot(2, 2, 4)
        ax_legend.axis('off')

        legend_elements = [
            Line2D([0], [0], color=self.transport_colors['H2'], linewidth=3,
                   label='氢气运输 H₂ Transport'),
            Line2D([0], [0], color=self.transport_colors['SAF'], linewidth=3,
                   linestyle='--', label='SAF运输 SAF Transport'),
            Line2D([0], [0], marker='o', color='w', markerfacecolor='red',
                   markersize=10, label='设施 Facilities'),
            Line2D([0], [0], color=self.modules['Coal Hydrogen']['color'], linewidth=3,
                   label=f"煤制氢 {self.modules['Coal Hydrogen']['name_cn']}"),
            Line2D([0], [0], color=self.modules['DAC Hydrogen']['color'], linewidth=3,
                   label=f"DAC制氢 {self.modules['DAC Hydrogen']['name_cn']}"),
            Line2D([0], [0], color=self.modules['Natural Gas']['color'], linewidth=3,
                   label=f"天然气 {self.modules['Natural Gas']['name_cn']}")
        ]

        ax_legend.legend(handles=legend_elements, loc='center', fontsize=12,
                        framealpha=0.9, title='图例 Legend', title_fontsize=14)

        plt.tight_layout()

        # 保存图片
        output_path = self.session_dir / "transport_map_comparison.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        logger.info(f"  ✓ 保存图片: {output_path}")
        plt.close()

    def create_combined_map(self):
        """创建所有模块叠加的综合地图"""
        logger.info("\n生成综合叠加地图...")

        fig, ax = self.create_base_map(figsize=(18, 14))

        # 为每个模块绘制路线（使用模块专属颜色）
        for module_name, config in self.modules.items():
            data = self.transport_data[module_name]

            # 绘制氢气运输路线（使用模块颜色）
            if data['h2_transport'] is not None and len(data['h2_transport']) > 0:
                for idx, row in data['h2_transport'].iterrows():
                    start_lon, start_lat = row['起点经度'], row['起点纬度']
                    end_lon, end_lat = row['终点经度'], row['终点纬度']

                    ax.plot([start_lon, end_lon], [start_lat, end_lat],
                           color=config['color'],
                           linewidth=1.0,
                           alpha=0.5,
                           transform=self.data_crs,
                           zorder=3)

            # 绘制SAF运输路线（使用模块颜色，虚线）
            if data['mtj_transport'] is not None and len(data['mtj_transport']) > 0:
                for idx, row in data['mtj_transport'].iterrows():
                    start_lon, start_lat = row['起点经度'], row['起点纬度']
                    end_lon, end_lat = row['终点经度'], row['终点纬度']

                    ax.plot([start_lon, end_lon], [start_lat, end_lat],
                           color=config['color'],
                           linewidth=1.0,
                           alpha=0.5,
                           transform=self.data_crs,
                           zorder=3,
                           linestyle='--')

        # 绘制所有设施点
        all_locations = set()
        for module_name, data in self.transport_data.items():
            if data['h2_transport'] is not None:
                for _, row in data['h2_transport'].iterrows():
                    all_locations.add((row['起点经度'], row['起点纬度']))
                    all_locations.add((row['终点经度'], row['终点纬度']))
            if data['mtj_transport'] is not None:
                for _, row in data['mtj_transport'].iterrows():
                    all_locations.add((row['起点经度'], row['起点纬度']))
                    all_locations.add((row['终点经度'], row['终点纬度']))

        if all_locations:
            lons = [loc[0] for loc in all_locations]
            lats = [loc[1] for loc in all_locations]
            ax.scatter(lons, lats, marker='o', c='black', s=30, alpha=0.8,
                      edgecolors='white', linewidth=0.5, transform=self.data_crs, zorder=5)

        # 添加装饰元素（指北针和比例尺）
        self.add_decorations(ax)

        # 添加图例
        legend_elements = [
            Line2D([0], [0], color=self.modules['Coal Hydrogen']['color'], linewidth=2,
                   label=f"煤制氢 H₂ (实线) | SAF (虚线)"),
            Line2D([0], [0], color=self.modules['DAC Hydrogen']['color'], linewidth=2,
                   label=f"DAC制氢 H₂ (实线) | SAF (虚线)"),
            Line2D([0], [0], color=self.modules['Natural Gas']['color'], linewidth=2,
                   label=f"天然气 H₂ (实线) | SAF (虚线)"),
            Line2D([0], [0], marker='o', color='w', markerfacecolor='black',
                   markersize=8, label='设施 Facilities')
        ]
        # 将图例放到图外右侧
        ax.legend(handles=legend_elements, loc='center left', bbox_to_anchor=(1.02, 0.5),
                 fontsize=10, framealpha=0.9)

        # 添加标题
        ax.set_title('三模块SAF供应链综合运输网络\nThree Modules SAF Supply Chain Integrated Transport Network',
                    fontsize=14, fontweight='bold', pad=20)

        # 调整布局以容纳外部图例
        plt.tight_layout(rect=[0, 0, 0.85, 1])  # 为右侧图例留出空间

        # 保存图片
        output_path = self.session_dir / "transport_map_combined.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        logger.info(f"  ✓ 保存图片: {output_path}")
        plt.close()

    def run_all_visualizations(self):
        """运行所有可视化"""
        logger.info("\n" + "=" * 60)
        logger.info("开始生成地图可视化")
        logger.info("=" * 60)

        try:
            # 生成各模块独立地图
            for module_name in self.modules.keys():
                self.create_individual_module_map(module_name)

            # 生成对比地图
            self.create_comparison_map()

            # 生成综合叠加地图
            self.create_combined_map()

            logger.info("\n" + "=" * 60)
            logger.info("✓ 所有地图可视化生成完成")
            logger.info(f"✓ 输出目录: {self.session_dir}")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"\n✗ 地图可视化生成失败: {e}")
            raise


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("三模块运输路线地图可视化脚本")
    logger.info("Three Modules Transport Route Map Visualization Script")
    logger.info("=" * 60)

    try:
        # 创建可视化器
        visualizer = ThreeModulesMapVisualizer()

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
