"""
工业副产氢源可视化器 - 基于frykit
使用frykit库创建符合学术规范的中国工业副产氢源分布地图
"""

import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import logging
from pathlib import Path
from datetime import datetime
import matplotlib
import frykit.plot as fplt
from cartopy.feature import LAND

class ByproductHydrogenVisualizerFrykit:
    """工业副产氢源可视化器 - frykit版本"""

    def __init__(self):
        """初始化可视化器"""
        # 设置日志
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )

        # 设置中文字体支持
        matplotlib.rcParams['font.sans-serif'] = [
            'Microsoft YaHei', 'SimHei', 'SimSun',
            'WenQuanYi Zen Hei', 'Noto Sans CJK SC',
            'DejaVu Sans', 'Arial Unicode MS', 'sans-serif'
        ]
        matplotlib.rcParams['axes.unicode_minus'] = False

        # 验证字体设置
        self._verify_font_setup()

        # 设置投影
        self.map_crs = fplt.CN_AZIMUTHAL_EQUIDISTANT
        self.data_crs = fplt.PLATE_CARREE

        # 设置全国地图范围
        self.map_extent = (73, 135, 18, 54)  # 73E-135E, 18N-54N
        self.xticks = np.arange(75, 136, 10)
        self.yticks = np.arange(20, 55, 10)

        # 颜色映射（用于表示产量深浅）
        # 钢铁：橙红色系 (Oranges colormap)
        # 石化：绿色系 (Greens colormap)
        self.colormaps = {
            'steel': 'Oranges',      # 橙色系 - 钢铁焦化
            'refinery': 'Greens'     # 绿色系 - 石化炼厂
        }

        # 固定的圆圈大小
        self.marker_size = 80

        # 数据目录
        self.data_dir = Path(__file__).parent / 'data'
        self.results_dir = Path(__file__).parent / 'results' / 'figures'

    def _verify_font_setup(self):
        """验证字体设置是否正确"""
        try:
            import matplotlib.font_manager as fm

            available_fonts = [f.name for f in fm.fontManager.ttflist]
            preferred_fonts = [
                'Microsoft YaHei', 'SimHei', 'SimSun',
                'WenQuanYi Zen Hei', 'Noto Sans CJK SC',
                'DejaVu Sans', 'Arial Unicode MS'
            ]

            found_font = None
            for font_name in preferred_fonts:
                if font_name in available_fonts:
                    found_font = font_name
                    break

            if found_font:
                matplotlib.rcParams['font.sans-serif'] = [found_font, 'DejaVu Sans', 'Arial', 'sans-serif']
                self.logger.info(f"使用字体: {found_font}")
            else:
                matplotlib.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'sans-serif']
                self.logger.warning("未找到合适的中文字体，使用默认字体")

        except Exception as e:
            self.logger.warning(f"字体设置失败: {e}")
            matplotlib.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'sans-serif']

    def find_latest_data_files(self):
        """查找最新的数据文件"""
        self.logger.info("正在查找最新的数据文件...")

        steel_files = list(self.data_dir.glob('steel_daily_byproduct_h2_*.csv'))
        refinery_files = list(self.data_dir.glob('refinery_daily_byproduct_h2_*.csv'))

        if not steel_files or not refinery_files:
            raise FileNotFoundError("未找到数据文件，请先运行 analyze_data_granularity.py 生成数据")

        latest_steel = max(steel_files, key=lambda x: x.stat().st_mtime)
        latest_refinery = max(refinery_files, key=lambda x: x.stat().st_mtime)

        self.logger.info(f"钢铁数据: {latest_steel.name}")
        self.logger.info(f"石化数据: {latest_refinery.name}")

        return latest_steel, latest_refinery

    def load_data(self, steel_file, refinery_file):
        """加载数据文件"""
        self.logger.info("正在加载数据...")

        # 加载钢铁数据
        steel_df = pd.read_csv(steel_file, encoding='utf-8')
        self.logger.info(f"加载钢铁设施数据: {len(steel_df)} 条")

        # 加载石化数据
        refinery_df = pd.read_csv(refinery_file, encoding='utf-8')
        self.logger.info(f"加载石化设施数据: {len(refinery_df)} 条")

        # 检查坐标完整性
        steel_df = steel_df.dropna(subset=['latitude', 'longitude', 'h2_daily_tonnes'])
        refinery_df = refinery_df.dropna(subset=['latitude', 'longitude', 'h2_daily_tonnes'])

        self.logger.info(f"有效钢铁设施: {len(steel_df)} 个")
        self.logger.info(f"有效石化设施: {len(refinery_df)} 个")

        return steel_df, refinery_df

    def normalize_capacity_for_color(self, capacities, vmin=None, vmax=None):
        """
        将产能标准化到[0, 1]范围用于颜色映射
        使用对数缩放以更好地显示差异
        """
        log_capacities = np.log10(capacities + 1)

        if vmin is None:
            vmin = log_capacities.min()
        if vmax is None:
            vmax = log_capacities.max()

        # 标准化到 [0, 1]，并确保最小值至少为0.3（避免太浅的颜色）
        normalized = (log_capacities - vmin) / (vmax - vmin)
        normalized = 0.3 + normalized * 0.7  # 映射到 [0.3, 1.0] 范围

        return normalized

    def create_base_map(self, figsize=(18, 14)):
        """创建中国地图底图"""
        self.logger.info("正在创建地图底图...")

        fig = plt.figure(figsize=figsize)
        ax = fig.add_subplot(projection=self.map_crs)

        # 设置地图范围
        min_lon, max_lon, min_lat, max_lat = self.map_extent
        fplt.set_map_ticks(ax, (min_lon, max_lon, min_lat, max_lat),
                          self.xticks, self.yticks)

        # 添加网格线
        ax.gridlines(xlocs=self.xticks, ylocs=self.yticks,
                     lw=0.5, ls="--", color="gray", alpha=0.4)

        # 设置刻度样式
        ax.tick_params(
            length=8, width=0.9, labelsize=10,
            top=True, right=True, labeltop=True, labelright=True
        )

        # 添加地图要素
        ax.set_facecolor("lightcyan")
        ax.add_feature(LAND, fc="floralwhite", ec="k", lw=0.5)
        fplt.add_cn_city(ax, lw=0.3, edgecolor='lightgreen',
                       linestyle='--', zorder=2)
        fplt.add_cn_line(ax, lw=1.2, edgecolor='dimgray', zorder=2.5)
        fplt.add_cn_border(ax, lw=0.75, edgecolor='black', zorder=3)

        self.logger.info("地图底图创建完成")
        return fig, ax

    def plot_facilities(self, ax, steel_df, refinery_df):
        """绘制设施点位（使用颜色深浅表示产量）"""
        self.logger.info("正在绘制设施点位...")

        # 导入colormap
        from matplotlib import cm

        # 获取颜色映射
        steel_cmap = cm.get_cmap(self.colormaps['steel'])
        refinery_cmap = cm.get_cmap(self.colormaps['refinery'])

        # 标准化钢铁产能（用于颜色映射）
        steel_capacities = steel_df['h2_daily_tonnes'].values
        steel_colors_normalized = self.normalize_capacity_for_color(steel_capacities)

        # 标准化石化产能（用于颜色映射）
        refinery_capacities = refinery_df['h2_daily_tonnes'].values
        refinery_colors_normalized = self.normalize_capacity_for_color(refinery_capacities)

        # 绘制钢铁焦化设施
        self.logger.info(f"绘制 {len(steel_df)} 个钢铁焦化设施...")
        steel_scatter = ax.scatter(
            steel_df['longitude'].values,
            steel_df['latitude'].values,
            c=steel_colors_normalized,
            cmap=self.colormaps['steel'],
            s=self.marker_size,
            marker='o',
            edgecolors='black',
            linewidth=0.5,
            transform=self.data_crs,
            zorder=10,
            alpha=0.85,
            vmin=0.3,
            vmax=1.0
        )

        # 绘制石化炼厂设施
        self.logger.info(f"绘制 {len(refinery_df)} 个石化炼厂设施...")
        refinery_scatter = ax.scatter(
            refinery_df['longitude'].values,
            refinery_df['latitude'].values,
            c=refinery_colors_normalized,
            cmap=self.colormaps['refinery'],
            s=self.marker_size,
            marker='o',
            edgecolors='black',
            linewidth=0.5,
            transform=self.data_crs,
            zorder=10,
            alpha=0.85,
            vmin=0.3,
            vmax=1.0
        )

        self.logger.info("设施点位绘制完成")

        # 返回scatter对象用于添加colorbar
        return steel_scatter, refinery_scatter, steel_df, refinery_df

    def add_colorbars(self, fig, ax, steel_scatter, refinery_scatter, steel_df, refinery_df):
        """添加颜色条显示产量范围"""
        self.logger.info("正在添加颜色条...")

        # 为钢铁设施添加颜色条
        steel_cbar = plt.colorbar(steel_scatter, ax=ax, fraction=0.03, pad=0.08,
                                  orientation='vertical', label='钢铁焦化 - 日产氢量(吨/天)')

        # 设置钢铁colorbar的刻度标签（从归一化值转换回实际值）
        steel_min = steel_df['h2_daily_tonnes'].min()
        steel_max = steel_df['h2_daily_tonnes'].max()
        steel_ticks = [100, 500, 1000, 2000, 3000]
        steel_ticks_filtered = [t for t in steel_ticks if steel_min <= t <= steel_max]

        if not steel_ticks_filtered:
            steel_ticks_filtered = [steel_min, steel_max]

        # 将实际值转换为归一化的colorbar位置
        steel_tick_positions = self.normalize_capacity_for_color(
            np.array(steel_ticks_filtered)
        )
        steel_cbar.set_ticks(steel_tick_positions)
        steel_cbar.set_ticklabels([f'{int(t):,}' for t in steel_ticks_filtered])
        steel_cbar.ax.tick_params(labelsize=9)

        # 为石化设施添加颜色条
        refinery_cbar = plt.colorbar(refinery_scatter, ax=ax, fraction=0.03, pad=0.14,
                                     orientation='vertical', label='石化炼厂 - 日产氢量(吨/天)')

        # 设置石化colorbar的刻度标签
        refinery_min = refinery_df['h2_daily_tonnes'].min()
        refinery_max = refinery_df['h2_daily_tonnes'].max()
        refinery_ticks = [10, 20, 50, 100]
        refinery_ticks_filtered = [t for t in refinery_ticks if refinery_min <= t <= refinery_max]

        if not refinery_ticks_filtered:
            refinery_ticks_filtered = [refinery_min, refinery_max]

        refinery_tick_positions = self.normalize_capacity_for_color(
            np.array(refinery_ticks_filtered)
        )
        refinery_cbar.set_ticks(refinery_tick_positions)
        refinery_cbar.set_ticklabels([f'{int(t):,}' for t in refinery_ticks_filtered])
        refinery_cbar.ax.tick_params(labelsize=9)

        self.logger.info("颜色条添加完成")

    def add_statistics_box(self, ax, steel_df, refinery_df):
        """添加统计信息面板"""
        self.logger.info("正在添加统计信息...")

        # 计算统计数据
        steel_total = steel_df['h2_daily_tonnes'].sum()
        refinery_total = refinery_df['h2_daily_tonnes'].sum()
        total = steel_total + refinery_total

        steel_percent = (steel_total / total) * 100
        refinery_percent = (refinery_total / total) * 100

        # 创建统计文本
        stats_text = (
            f"副产氢源统计\n"
            f"{'─'*20}\n"
            f"设施总数：{len(steel_df) + len(refinery_df)}个\n"
            f"  ├─ 钢铁焦化：{len(steel_df)}个\n"
            f"  └─ 石化炼厂：{len(refinery_df)}个\n\n"
            f"日产氢总量：{total:,.0f}吨/天\n"
            f"  ├─ 钢铁焦化：{steel_total:,.0f}吨/天 ({steel_percent:.1f}%)\n"
            f"  └─ 石化炼厂：{refinery_total:,.0f}吨/天 ({refinery_percent:.1f}%)"
        )

        # 添加文本框
        ax.text(0.02, 0.02, stats_text, transform=ax.transAxes,
               fontsize=9, bbox=dict(boxstyle="round,pad=0.5",
               facecolor="white", alpha=0.95, edgecolor='black', linewidth=1),
               verticalalignment='bottom', family='monospace')

        self.logger.info("统计信息添加完成")

    def add_decorations(self, ax):
        """添加制图装饰元素"""
        self.logger.info("正在添加制图装饰...")

        try:
            # 添加指北针
            fplt.add_compass(ax, 0.92, 0.88, size=15, style="star")

            # 添加比例尺
            scale_bar = fplt.add_scale_bar(ax, 0.05, 0.95, length=500)
            scale_bar.set_xticks([0, 250, 500])
            scale_bar.xaxis.get_label().set_fontsize("small")

            self.logger.info("制图装饰添加完成")
        except Exception as e:
            self.logger.warning(f"添加装饰元素失败: {e}")

    def add_title(self, ax, steel_df, refinery_df):
        """添加标题"""
        total_facilities = len(steel_df) + len(refinery_df)
        total_production = steel_df['h2_daily_tonnes'].sum() + refinery_df['h2_daily_tonnes'].sum()

        plt.suptitle(
            f'中国工业副产氢源分布图\n'
            f'设施总数: {total_facilities}个 | 日产氢总量: {total_production:,.0f}吨/天',
            fontsize=16, y=0.96, fontweight='bold'
        )

    def create_visualization(self):
        """创建完整的可视化地图"""
        self.logger.info("="*60)
        self.logger.info("开始创建工业副产氢源可视化地图（frykit版本 - 颜色深浅表示产量）")
        self.logger.info("="*60)

        # 1. 查找并加载数据
        steel_file, refinery_file = self.find_latest_data_files()
        steel_df, refinery_df = self.load_data(steel_file, refinery_file)

        # 2. 创建地图底图
        fig, ax = self.create_base_map()

        # 3. 绘制设施点位（返回scatter对象）
        steel_scatter, refinery_scatter, steel_df, refinery_df = self.plot_facilities(ax, steel_df, refinery_df)

        # 4. 添加颜色条
        self.add_colorbars(fig, ax, steel_scatter, refinery_scatter, steel_df, refinery_df)

        # 5. 添加统计信息
        self.add_statistics_box(ax, steel_df, refinery_df)

        # 6. 添加制图装饰
        self.add_decorations(ax)

        # 7. 添加标题
        self.add_title(ax, steel_df, refinery_df)

        # 8. 保存图表
        self.results_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f'byproduct_hydrogen_sources_frykit_{timestamp}.png'
        output_path = self.results_dir / filename

        fplt.savefig(str(output_path), dpi=300, bbox_inches='tight',
                    facecolor='white', edgecolor='none')
        plt.close(fig)

        self.logger.info("="*60)
        self.logger.info(f"✓ 可视化地图创建成功!")
        self.logger.info(f"✓ 输出文件: {filename}")
        self.logger.info(f"✓ 完整路径: {output_path}")
        self.logger.info(f"✓ 钢铁设施: {len(steel_df)}个")
        self.logger.info(f"✓ 石化设施: {len(refinery_df)}个")
        self.logger.info(f"✓ 设施总数: {len(steel_df) + len(refinery_df)}个")
        self.logger.info(f"✓ 可视化方式: 颜色深浅表示产量大小")
        self.logger.info("="*60)

        return str(output_path)


def main():
    """主函数"""
    visualizer = ByproductHydrogenVisualizerFrykit()
    output_path = visualizer.create_visualization()
    print(f"\n[SUCCESS] 地图已保存至: {output_path}")


if __name__ == "__main__":
    main()
