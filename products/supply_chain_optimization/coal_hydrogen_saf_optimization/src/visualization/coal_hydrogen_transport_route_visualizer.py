"""
Coal Hydrogen SAF供应链运输路线可视化
Coal Hydrogen SAF Supply Chain Transport Route Visualization

功能 | Features:
1. 氢气管道运输可视化 (Hydrogen pipeline transport visualization)
2. SAF卡车运输可视化 (SAF truck transport visualization)
3. 设施位置标注 (Facility location marking)
4. 运输流量分析 (Transport flow analysis)

作者 | Author: Claude Code
创建时间 | Created: 2025-11-06
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple
import logging

import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib import rcParams
import seaborn as sns
import cartopy
import cartopy.crs as ccrs
import cartopy.feature as cfeature

# 配置中文字体
matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS']
matplotlib.rcParams['axes.unicode_minus'] = False

# 添加frykit路径
sys.path.append(str(Path(__file__).parent.parent.parent.parent.parent.parent / "shared"))
import frykit.plot as fplt

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CoalHydrogenTransportRouteVisualizer:
    """Coal Hydrogen运输路线可视化器"""

    def __init__(self, output_dir: str = None):
        """
        初始化可视化器

        Args:
            output_dir: 输出目录，默认为 coal_hydrogen_saf_optimization/results/visualization
        """
        if output_dir is None:
            base_dir = Path(__file__).parent.parent.parent
            output_dir = base_dir / "results" / "visualization"

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 创建带时间戳的子目录
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = self.output_dir / f"transport_routes_{timestamp}"
        self.session_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"输出目录: {self.session_dir}")

        # 设置地图投影
        self.map_crs = fplt.CN_AZIMUTHAL_EQUIDISTANT
        self.data_crs = fplt.PLATE_CARREE

        # 设施类型标记映射
        self.facility_markers = {
            'solar': 'v',       # 太阳能电站 - 下三角
            'wind': '^',        # 风电场 - 上三角
            'airport': 'o',     # 机场 - 圆形
            'mtj': 's'          # MTJ工厂 - 方形
        }

        # 设施类型颜色
        self.facility_colors = {
            'solar': '#FFD700',    # 金色
            'wind': '#87CEEB',     # 天蓝色
            'airport': '#FF6347',  # 番茄红
            'mtj': '#32CD32'       # 绿色
        }

        # 运输类型颜色
        self.transport_colors = {
            'H2': '#1E90FF',       # 氢气 - 道奇蓝
            'MTJ': '#FF4500'       # SAF - 橙红色
        }

        # 数据存储
        self.solution_data = None
        self.h2_transport_df = None
        self.mtj_transport_df = None

    def load_data(self, solution_file: str, h2_transport_file: str, mtj_transport_file: str):
        """
        加载数据

        Args:
            solution_file: 优化解决方案JSON文件路径
            h2_transport_file: 氢气运输CSV文件路径
            mtj_transport_file: SAF运输CSV文件路径
        """
        logger.info("=" * 60)
        logger.info("加载数据")
        logger.info("=" * 60)

        # 加载解决方案
        logger.info(f"加载解决方案文件: {solution_file}")
        with open(solution_file, 'r', encoding='utf-8') as f:
            self.solution_data = json.load(f)
        logger.info(f"  ✓ 设施数量: {len(self.solution_data.get('facilities', {}))}")

        # 加载氢气运输数据
        logger.info(f"加载氢气运输文件: {h2_transport_file}")
        self.h2_transport_df = pd.read_csv(h2_transport_file, encoding='utf-8')
        logger.info(f"  ✓ 氢气运输路线数: {len(self.h2_transport_df)}")

        # 加载SAF运输数据
        logger.info(f"加载SAF运输文件: {mtj_transport_file}")
        self.mtj_transport_df = pd.read_csv(mtj_transport_file, encoding='utf-8')
        logger.info(f"  ✓ SAF运输路线数: {len(self.mtj_transport_df)}")

        logger.info("=" * 60)

    def create_base_map(self, figsize=(14, 10)):
        """创建基础地图"""
        fig = plt.figure(figsize=figsize)
        main_ax = fig.add_subplot(projection=self.map_crs)

        # 设置地图范围 - 京津冀及周边地区
        main_ax.set_extent([111, 119, 35, 43], crs=self.data_crs)

        # 添加地理特征
        main_ax.add_feature(cfeature.LAND, facecolor='#F5F5DC', alpha=0.3)
        main_ax.add_feature(cfeature.OCEAN, facecolor='#E0F2F7')
        main_ax.add_feature(cfeature.COASTLINE, linewidth=0.5)
        main_ax.add_feature(cfeature.BORDERS, linewidth=0.5, linestyle=':')

        # 添加省界
        provinces = cfeature.NaturalEarthFeature(
            category='cultural',
            name='admin_1_states_provinces_lines',
            scale='10m',
            facecolor='none',
            edgecolor='gray',
            linewidth=0.3
        )
        main_ax.add_feature(provinces)

        # 添加网格
        gl = main_ax.gridlines(draw_labels=True, linewidth=0.5, color='gray', alpha=0.3, linestyle='--')
        gl.top_labels = False
        gl.right_labels = False

        return fig, main_ax

    def plot_facilities(self, ax):
        """绘制设施位置"""
        logger.info("绘制设施位置...")

        facilities = self.solution_data.get('facilities', {})
        facility_types = {
            'solar': [],
            'wind': [],
            'airport': [],
            'mtj': []
        }

        # 分类设施
        for facility_name, facility_info in facilities.items():
            if not facility_info.get('built', False):
                continue

            location_type = facility_info.get('location_type', '')
            technology = facility_info.get('technology', '')

            # 获取坐标 - 从氢气运输数据或SAF运输数据中提取
            coords = self._get_facility_coordinates(facility_info.get('location'))

            if coords is None:
                continue

            lat, lon = coords

            # 分类
            if 'solar' in location_type.lower():
                facility_types['solar'].append((lon, lat, facility_name))
            elif 'wind' in location_type.lower():
                facility_types['wind'].append((lon, lat, facility_name))
            elif 'airport' in location_type.lower():
                facility_types['airport'].append((lon, lat, facility_name))
                facility_types['mtj'].append((lon, lat, facility_name))  # 机场也是MTJ工厂

        # 绘制各类设施
        for ftype, facilities_list in facility_types.items():
            if not facilities_list:
                continue

            lons = [f[0] for f in facilities_list]
            lats = [f[1] for f in facilities_list]

            ax.scatter(lons, lats,
                      marker=self.facility_markers[ftype],
                      c=self.facility_colors[ftype],
                      s=100 if ftype == 'airport' else 50,
                      alpha=0.8,
                      edgecolors='black',
                      linewidth=0.5,
                      transform=self.data_crs,
                      zorder=5,
                      label=self._get_facility_label(ftype))

        logger.info(f"  ✓ 绘制了 {sum(len(f) for f in facility_types.values())} 个设施")

    def _get_facility_coordinates(self, location_name: str) -> Tuple[float, float]:
        """从运输数据中获取设施坐标"""
        # 先从氢气运输数据中查找
        if self.h2_transport_df is not None:
            h2_start = self.h2_transport_df[self.h2_transport_df['起点'] == location_name]
            if not h2_start.empty:
                return (h2_start.iloc[0]['起点纬度'], h2_start.iloc[0]['起点经度'])

            h2_end = self.h2_transport_df[self.h2_transport_df['终点'] == location_name]
            if not h2_end.empty:
                return (h2_end.iloc[0]['终点纬度'], h2_end.iloc[0]['终点经度'])

        # 从SAF运输数据中查找
        if self.mtj_transport_df is not None:
            mtj_start = self.mtj_transport_df[self.mtj_transport_df['起点'] == location_name]
            if not mtj_start.empty:
                return (mtj_start.iloc[0]['起点纬度'], mtj_start.iloc[0]['起点经度'])

            mtj_end = self.mtj_transport_df[self.mtj_transport_df['终点'] == location_name]
            if not mtj_end.empty:
                return (mtj_end.iloc[0]['终点纬度'], mtj_end.iloc[0]['终点经度'])

        return None

    def _get_facility_label(self, ftype: str) -> str:
        """获取设施类型标签"""
        labels = {
            'solar': '太阳能电站 Solar Plant',
            'wind': '风电场 Wind Farm',
            'airport': '机场 Airport',
            'mtj': 'MTJ工厂 MTJ Plant'
        }
        return labels.get(ftype, ftype)

    def plot_h2_transport_routes(self, ax):
        """绘制氢气运输路线"""
        logger.info("绘制氢气运输路线...")

        if self.h2_transport_df is None or len(self.h2_transport_df) == 0:
            logger.warning("  ⚠ 无氢气运输数据")
            return

        # 归一化运输量用于线宽
        volumes = self.h2_transport_df['氢气运输量(kg)'].values
        max_volume = volumes.max()
        min_volume = volumes.min()

        for idx, row in self.h2_transport_df.iterrows():
            start_lon, start_lat = row['起点经度'], row['起点纬度']
            end_lon, end_lat = row['终点经度'], row['终点纬度']
            volume = row['氢气运输量(kg)']

            # 计算线宽（基于运输量）
            linewidth = 0.5 + 2.5 * (volume - min_volume) / (max_volume - min_volume) if max_volume > min_volume else 1.5

            # 绘制路线
            ax.plot([start_lon, end_lon], [start_lat, end_lat],
                   color=self.transport_colors['H2'],
                   linewidth=linewidth,
                   alpha=0.6,
                   transform=self.data_crs,
                   zorder=3)

            # 添加箭头指示方向
            self._add_arrow(ax, start_lon, start_lat, end_lon, end_lat, self.transport_colors['H2'])

        logger.info(f"  ✓ 绘制了 {len(self.h2_transport_df)} 条氢气运输路线")

    def plot_mtj_transport_routes(self, ax):
        """绘制SAF运输路线"""
        logger.info("绘制SAF运输路线...")

        if self.mtj_transport_df is None or len(self.mtj_transport_df) == 0:
            logger.warning("  ⚠ 无SAF运输数据")
            return

        # 归一化运输量用于线宽
        volumes = self.mtj_transport_df['运输量(kg)'].values
        max_volume = volumes.max()
        min_volume = volumes.min()

        for idx, row in self.mtj_transport_df.iterrows():
            start_lon, start_lat = row['起点经度'], row['起点纬度']
            end_lon, end_lat = row['终点经度'], row['终点纬度']
            volume = row['运输量(kg)']

            # 计算线宽（基于运输量）
            linewidth = 0.5 + 2.5 * (volume - min_volume) / (max_volume - min_volume) if max_volume > min_volume else 1.5

            # 绘制路线
            ax.plot([start_lon, end_lon], [start_lat, end_lat],
                   color=self.transport_colors['MTJ'],
                   linewidth=linewidth,
                   alpha=0.6,
                   transform=self.data_crs,
                   zorder=3,
                   linestyle='--')  # 虚线区分SAF运输

            # 添加箭头指示方向
            self._add_arrow(ax, start_lon, start_lat, end_lon, end_lat, self.transport_colors['MTJ'])

        logger.info(f"  ✓ 绘制了 {len(self.mtj_transport_df)} 条SAF运输路线")

    def _add_arrow(self, ax, start_lon, start_lat, end_lon, end_lat, color):
        """添加箭头指示运输方向"""
        # 在路线中点添加箭头
        mid_lon = (start_lon + end_lon) / 2
        mid_lat = (start_lat + end_lat) / 2

        # 计算方向
        dx = end_lon - start_lon
        dy = end_lat - start_lat

        # 归一化
        length = np.sqrt(dx**2 + dy**2)
        if length > 0:
            dx = dx / length * 0.2
            dy = dy / length * 0.2

            ax.arrow(mid_lon, mid_lat, dx, dy,
                    head_width=0.15, head_length=0.1,
                    fc=color, ec=color,
                    alpha=0.7,
                    transform=self.data_crs,
                    zorder=4)

    def create_comprehensive_map(self):
        """创建综合运输路线地图"""
        logger.info("\n生成综合运输路线地图...")

        fig, ax = self.create_base_map(figsize=(16, 12))

        # 绘制运输路线（先绘制，作为背景）
        self.plot_h2_transport_routes(ax)
        self.plot_mtj_transport_routes(ax)

        # 绘制设施（后绘制，覆盖在路线上）
        self.plot_facilities(ax)

        # 添加图例
        handles, labels = ax.get_legend_handles_labels()

        # 添加运输路线图例
        from matplotlib.lines import Line2D
        transport_handles = [
            Line2D([0], [0], color=self.transport_colors['H2'], linewidth=2, label='氢气管道 H₂ Pipeline'),
            Line2D([0], [0], color=self.transport_colors['MTJ'], linewidth=2, linestyle='--', label='SAF卡车 SAF Truck')
        ]
        handles.extend(transport_handles)
        labels.extend([h.get_label() for h in transport_handles])

        ax.legend(handles, labels, loc='upper left', fontsize=9, framealpha=0.9)

        # 添加标题
        ax.set_title('Coal Hydrogen SAF供应链运输路线图\nCoal Hydrogen SAF Supply Chain Transport Routes',
                    fontsize=14, fontweight='bold', pad=20)

        # 添加统计信息
        stats_text = f"氢气路线: {len(self.h2_transport_df)} 条\nSAF路线: {len(self.mtj_transport_df)} 条"
        ax.text(0.02, 0.98, stats_text,
               transform=ax.transAxes,
               verticalalignment='top',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8),
               fontsize=10)

        plt.tight_layout()

        # 保存图片
        output_path = self.session_dir / "comprehensive_transport_map.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        logger.info(f"  ✓ 保存图片: {output_path}")
        plt.close()

    def create_transport_flow_analysis(self):
        """创建运输流量分析图"""
        logger.info("\n生成运输流量分析图...")

        fig, axes = plt.subplots(1, 2, figsize=(16, 6))
        fig.suptitle('Coal Hydrogen运输流量分析 | Transport Flow Analysis',
                    fontsize=14, fontweight='bold')

        # === 子图1: 氢气运输量Top 10 ===
        ax1 = axes[0]

        if self.h2_transport_df is not None and len(self.h2_transport_df) > 0:
            h2_sorted = self.h2_transport_df.sort_values('氢气运输量(kg)', ascending=True).tail(10)

            # 创建标签（起点 → 终点）
            labels = [f"{row['起点']}\n→\n{row['终点']}" for _, row in h2_sorted.iterrows()]
            volumes = h2_sorted['氢气运输量(kg)'].values / 1000  # 转换为吨

            y_pos = np.arange(len(labels))
            bars = ax1.barh(y_pos, volumes, color=self.transport_colors['H2'], alpha=0.7)

            # 添加数值标签
            for i, bar in enumerate(bars):
                width = bar.get_width()
                ax1.text(width, bar.get_y() + bar.get_height()/2,
                        f'{width:.1f}',
                        ha='left', va='center', fontsize=8)

            ax1.set_yticks(y_pos)
            ax1.set_yticklabels(labels, fontsize=7)
            ax1.set_xlabel('氢气运输量（吨）| H₂ Transport Volume (tons)', fontsize=10)
            ax1.set_title('氢气运输量Top 10 | Top 10 H₂ Transport Routes', fontsize=11, fontweight='bold')
            ax1.grid(axis='x', alpha=0.3)

        # === 子图2: SAF运输量 ===
        ax2 = axes[1]

        if self.mtj_transport_df is not None and len(self.mtj_transport_df) > 0:
            mtj_sorted = self.mtj_transport_df.sort_values('运输量(kg)', ascending=True)

            # 创建标签（起点 → 终点）
            labels = [f"{row['起点']}\n→\n{row['终点']}" for _, row in mtj_sorted.iterrows()]
            volumes = mtj_sorted['运输量(kg)'].values / 1000  # 转换为吨

            y_pos = np.arange(len(labels))
            bars = ax2.barh(y_pos, volumes, color=self.transport_colors['MTJ'], alpha=0.7)

            # 添加数值标签
            for i, bar in enumerate(bars):
                width = bar.get_width()
                ax2.text(width, bar.get_y() + bar.get_height()/2,
                        f'{width:.1f}',
                        ha='left', va='center', fontsize=8)

            ax2.set_yticks(y_pos)
            ax2.set_yticklabels(labels, fontsize=8)
            ax2.set_xlabel('SAF运输量（吨）| SAF Transport Volume (tons)', fontsize=10)
            ax2.set_title('SAF运输路线 | SAF Transport Routes', fontsize=11, fontweight='bold')
            ax2.grid(axis='x', alpha=0.3)

        plt.tight_layout()

        # 保存图片
        output_path = self.session_dir / "transport_flow_analysis.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        logger.info(f"  ✓ 保存图片: {output_path}")
        plt.close()

    def generate_summary_report(self):
        """生成汇总报告"""
        logger.info("\n生成汇总报告...")

        # 统计信息
        summary = {
            '氢气运输路线数': len(self.h2_transport_df) if self.h2_transport_df is not None else 0,
            'SAF运输路线数': len(self.mtj_transport_df) if self.mtj_transport_df is not None else 0,
            '氢气总运输量(吨)': self.h2_transport_df['氢气运输量(kg)'].sum() / 1000 if self.h2_transport_df is not None else 0,
            'SAF总运输量(吨)': self.mtj_transport_df['运输量(kg)'].sum() / 1000 if self.mtj_transport_df is not None else 0,
            '平均氢气运输距离(km)': self.h2_transport_df['距离(km)'].mean() if self.h2_transport_df is not None else 0,
            '平均SAF运输距离(km)': self.mtj_transport_df['距离(km)'].mean() if self.mtj_transport_df is not None else 0
        }

        # 保存为JSON
        json_path = self.session_dir / "transport_summary.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        logger.info(f"  ✓ 保存JSON: {json_path}")

        # 打印汇总
        logger.info("\n" + "=" * 60)
        logger.info("运输汇总 | Transport Summary")
        logger.info("=" * 60)
        for key, value in summary.items():
            logger.info(f"  {key}: {value:.2f}")
        logger.info("=" * 60)

    def run_all_visualizations(self):
        """运行所有可视化"""
        logger.info("\n" + "=" * 60)
        logger.info("开始生成可视化")
        logger.info("=" * 60)

        try:
            # 生成各类可视化
            self.create_comprehensive_map()
            self.create_transport_flow_analysis()
            self.generate_summary_report()

            logger.info("\n" + "=" * 60)
            logger.info("✓ 所有可视化生成完成")
            logger.info(f"✓ 输出目录: {self.session_dir}")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"\n✗ 可视化生成失败: {e}")
            raise


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("Coal Hydrogen运输路线可视化脚本")
    logger.info("Coal Hydrogen Transport Route Visualization Script")
    logger.info("=" * 60)

    try:
        # 创建可视化器
        visualizer = CoalHydrogenTransportRouteVisualizer()

        # 设置文件路径（使用最新结果）
        base_dir = Path(__file__).parent.parent.parent / "results"
        solution_file = base_dir / "complete_solution_20251106_113130.json"
        h2_transport_file = base_dir / "hydrogen_transport_plan_20251106_113130.csv"
        mtj_transport_file = base_dir / "mtj_transport_plan_20251106_113130.csv"

        # 加载数据
        visualizer.load_data(solution_file, h2_transport_file, mtj_transport_file)

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
