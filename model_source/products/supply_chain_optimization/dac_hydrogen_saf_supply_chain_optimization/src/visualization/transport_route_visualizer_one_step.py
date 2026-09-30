"""
FT一步法运输路径可视化器
基于frykit库可视化FT一步法SAF供应链运输路径
- 天然气运输（管道/罐车）
- SAF运输（机场配送）
"""

import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import ast
import re
import os
import sqlite3
from datetime import datetime
import logging
from pathlib import Path
import matplotlib
import frykit.plot as fplt
from cartopy.feature import LAND
import json

class TransportRouteVisualizerOneStep:
    """FT一步法运输路径可视化器"""

    def __init__(self):
        """初始化可视化器"""
        # 设置日志
        self.logger = logging.getLogger(__name__)

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

        # 设置华北地区范围和刻度
        self.map_extent = (110, 120, 35, 45)  # 110E-120E, 35N-45N
        self.xticks = np.arange(110, 121, 2)
        self.yticks = np.arange(35, 46, 2)

        # 运输类型颜色映射 - FT一步法只有2种运输
        self.transport_type_colors = {
            'SAF': '#E67E22',        # 橙色 - SAF运输
            'NG': '#3498DB',         # 蓝色 - 天然气运输
            'default': '#95A5A6'     # 灰色 - 默认
        }

        # 设施类型标记映射
        self.facility_markers = {
            'ft_plant': 'h',        # 六边形 - FT工厂
            'airport': 'o',         # 圆形 - 机场
            'ng_source': 's',       # 方形 - 天然气供应点
            'default': 'o'
        }

        # 设施类型颜色映射
        self.facility_colors = {
            'ft_plant': '#FF6347',       # 橙红色 - FT工厂
            'airport': '#9370DB',        # 紫色 - 机场
            'ng_source': '#4169E1',      # 蓝色 - 天然气源
            'default': '#95A5A6'
        }

        # GraphHopper缓存路径
        self.graphhopper_cache_path = Path(__file__).parent / 'cache' / 'graphhopper_routes.db'

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

    def parse_coordinates(self, coord_str):
        """解析坐标字符串"""
        try:
            if pd.isna(coord_str) or coord_str == '':
                return None, None

            coord_str = str(coord_str).strip().strip('"').strip("'")

            # 尝试解析 "(lat, lon)" 格式
            if coord_str.startswith('(') and coord_str.endswith(')'):
                coord_str = coord_str[1:-1]
                parts = coord_str.split(',')
                if len(parts) == 2:
                    lat = float(parts[0].strip())
                    lon = float(parts[1].strip())
                    return lat, lon

            # 尝试用ast解析
            coords = ast.literal_eval(coord_str)
            if isinstance(coords, (list, tuple)) and len(coords) == 2:
                return float(coords[0]), float(coords[1])

            return None, None
        except Exception as e:
            self.logger.warning(f"无法解析坐标: {coord_str}, 错误: {e}")
            return None, None

    def get_real_route_coordinates_from_data(self, row):
        """从数据行中获取真实路径坐标"""
        try:
            transport_mode = row.get('运输方式', 'truck').lower()

            # 优先从数据中读取路径坐标
            if '路径坐标' in row and row['路径坐标'] and row['路径坐标'] != '[]':
                try:
                    coordinates = json.loads(row['路径坐标'])

                    if transport_mode == 'pipeline':
                        if coordinates and len(coordinates) >= 2:
                            self.logger.debug(f"使用管道路径坐标: {len(coordinates)}个点")
                            return coordinates
                    elif transport_mode == 'truck':
                        if coordinates and len(coordinates) > 2:
                            self.logger.debug(f"使用罐车路径坐标: {len(coordinates)}个点")
                            return coordinates

                except (json.JSONDecodeError, ValueError) as e:
                    self.logger.warning(f"路径坐标解析失败: {row['路径坐标']}, 错误: {e}")

            # 罐车运输：尝试从GraphHopper缓存获取
            if transport_mode != 'pipeline':
                self.logger.debug(f"罐车运输：尝试从GraphHopper缓存获取路径坐标")
                return self.get_real_route_coordinates_from_cache(
                    row['起点纬度'], row['起点经度'],
                    row['终点纬度'], row['终点经度']
                )

            return None

        except Exception as e:
            self.logger.debug(f"获取路径坐标失败: {e}")
            return None

    def get_real_route_coordinates_from_cache(self, start_lat, start_lon, end_lat, end_lon):
        """从GraphHopper缓存获取真实路径坐标"""
        try:
            if not self.graphhopper_cache_path.exists():
                return None

            import hashlib
            cache_key = hashlib.md5(f"{start_lat:.6f},{start_lon:.6f},{end_lat:.6f},{end_lon:.6f},car".encode()).hexdigest()

            conn = sqlite3.connect(str(self.graphhopper_cache_path))
            cursor = conn.cursor()

            cursor.execute('''
                SELECT route_coordinates
                FROM route_cache
                WHERE cache_key = ?
            ''', (cache_key,))

            result = cursor.fetchone()
            conn.close()

            if result and result[0]:
                try:
                    coordinates = json.loads(result[0])
                    if coordinates and len(coordinates) > 2:
                        return coordinates
                except json.JSONDecodeError:
                    pass

            return None

        except Exception as e:
            self.logger.debug(f"从缓存获取真实路径坐标失败: {e}")
            return None

    def load_transport_data(self, csv_file_path):
        """加载运输数据"""
        try:
            df = pd.read_csv(csv_file_path, encoding='utf-8')
            self.logger.info(f"成功加载运输数据，共 {len(df)} 条记录")

            # 解析起点和终点坐标
            df[['起点纬度', '起点经度']] = df['起点坐标'].apply(
                lambda x: pd.Series(self.parse_coordinates(x))
            )
            df[['终点纬度', '终点经度']] = df['终点坐标'].apply(
                lambda x: pd.Series(self.parse_coordinates(x))
            )

            # 过滤掉无效坐标
            valid_data = df.dropna(subset=['起点纬度', '起点经度', '终点纬度', '终点经度'])
            invalid_count = len(df) - len(valid_data)

            if invalid_count > 0:
                self.logger.warning(f"过滤掉 {invalid_count} 条无效坐标数据")

            # 确保坐标在中国范围内
            china_data = valid_data[
                (valid_data['起点纬度'] >= 18) & (valid_data['起点纬度'] <= 54) &
                (valid_data['起点经度'] >= 73) & (valid_data['起点经度'] <= 135) &
                (valid_data['终点纬度'] >= 18) & (valid_data['终点纬度'] <= 54) &
                (valid_data['终点经度'] >= 73) & (valid_data['终点经度'] <= 135)
            ]

            outside_china = len(valid_data) - len(china_data)
            if outside_china > 0:
                self.logger.warning(f"过滤掉 {outside_china} 条中国范围外的数据")

            self.logger.info(f"最终有效数据: {len(china_data)} 条")
            return china_data

        except Exception as e:
            self.logger.error(f"加载运输数据失败: {e}")
            return None

    def load_ft_plant_data(self, csv_file_path):
        """加载FT工厂数据"""
        try:
            if not csv_file_path or not Path(csv_file_path).exists():
                self.logger.warning("FT工厂数据文件不存在")
                return None

            df = pd.read_csv(csv_file_path, encoding='utf-8')
            self.logger.info(f"成功加载FT工厂数据，共 {len(df)} 个工厂")

            # 确保坐标在中国范围内
            china_data = df[
                (df['纬度'] >= 18) & (df['纬度'] <= 54) &
                (df['经度'] >= 73) & (df['经度'] <= 135)
            ]

            return china_data

        except Exception as e:
            self.logger.error(f"加载FT工厂数据失败: {e}")
            return None

    def load_ng_pipeline_data(self, csv_file_path):
        """加载天然气管道数据"""
        try:
            if not csv_file_path or not Path(csv_file_path).exists():
                self.logger.warning("天然气管道文件不存在")
                return None

            df = pd.read_csv(csv_file_path, encoding='utf-8')
            self.logger.info(f"成功加载天然气管道数据，共 {len(df)} 个管道")

            # 确保坐标在中国范围内
            china_data = df[
                (df['纬度'] >= 18) & (df['纬度'] <= 54) &
                (df['经度'] >= 73) & (df['经度'] <= 135)
            ]

            return china_data

        except Exception as e:
            self.logger.error(f"加载天然气管道数据失败: {e}")
            return None

    def create_base_map(self, figsize=(14, 10)):
        """创建基础地图（华北地区）"""
        try:
            fig = plt.figure(figsize=figsize)
            main_ax = fig.add_subplot(projection=self.map_crs)

            # 设置主地图范围为华北地区
            min_lon, max_lon, min_lat, max_lat = self.map_extent
            fplt.set_map_ticks(main_ax, (min_lon, max_lon, min_lat, max_lat),
                              self.xticks, self.yticks)
            main_ax.gridlines(xlocs=self.xticks, ylocs=self.yticks,
                             lw=0.5, ls="--", color="gray", alpha=0.5)

            # 设置刻度样式
            main_ax.tick_params(
                length=8, width=0.9, labelsize=10,
                top=True, right=True, labeltop=True, labelright=True
            )

            # 不创建南海小地图
            mini_ax = None

            # 添加地图要素
            main_ax.set_facecolor("lightcyan")
            main_ax.add_feature(LAND, fc="floralwhite", ec="k", lw=0.5)
            fplt.add_cn_city(main_ax, lw=0.3, edgecolor='lightgreen',
                           linestyle='--', zorder=2)
            fplt.add_cn_line(main_ax, lw=1.2, edgecolor='dimgray', zorder=2.5)
            fplt.add_cn_border(main_ax, lw=0.75, edgecolor='black', zorder=3)

            return fig, main_ax, mini_ax

        except Exception as e:
            raise RuntimeError(f"无法使用frykit创建完整地图: {e}。请确保正确安装了frykit[data]依赖。") from e

    def add_decorations(self, main_ax, mini_ax=None):
        """添加指北针和比例尺"""
        try:
            # 添加指北针
            fplt.add_compass(main_ax, 0.92, 0.85, size=15, style="star")

            # 添加比例尺（适合华北地区范围）
            scale_bar = fplt.add_scale_bar(main_ax, 0.05, 0.95, length=200)
            scale_bar.set_xticks([0, 100, 200])
            scale_bar.xaxis.get_label().set_fontsize("small")
        except Exception as e:
            print(f"警告: 无法添加装饰元素 ({e})，跳过装饰...")

    def filter_data_by_region(self, data, lat_col='纬度', lon_col='经度'):
        """过滤数据到华北地区范围"""
        min_lon, max_lon, min_lat, max_lat = self.map_extent

        if data is None or len(data) == 0:
            return data

        filtered_data = data[
            (data[lat_col] >= min_lat) & (data[lat_col] <= max_lat) &
            (data[lon_col] >= min_lon) & (data[lon_col] <= max_lon)
        ]

        outside_region = len(data) - len(filtered_data)
        if outside_region > 0:
            self.logger.info(f"过滤掉 {outside_region} 个华北地区范围外的设施")

        return filtered_data

    def normalize_transport_volume(self, volumes, min_width=0.5, max_width=4.0):
        """标准化运输量为线条宽度"""
        volumes = pd.to_numeric(volumes, errors='coerce')
        volumes = volumes.fillna(0)

        if volumes.max() == volumes.min():
            return np.full(len(volumes), (min_width + max_width) / 2)

        normalized = (volumes - volumes.min()) / (volumes.max() - volumes.min())
        return min_width + normalized * (max_width - min_width)

    def create_ft_one_step_network_visualization(self, all_data):
        """创建FT一步法供应链网络可视化"""
        print("正在创建FT一步法供应链网络图...")

        # 创建基础地图
        fig, main_ax, mini_ax = self.create_base_map(figsize=(14, 10))

        legend_elements = []
        facility_stats = {
            'ft_plant': 0,
            'airport': 0,
            'ng_source': 0
        }

        # 1. 绘制FT工厂
        if all_data.get('ft_plants') is not None:
            ft_plant_data = self.filter_data_by_region(all_data['ft_plants'])

            if ft_plant_data is not None and len(ft_plant_data) > 0:
                print(f"正在绘制 {len(ft_plant_data)} 个FT工厂...")
                for _, plant in ft_plant_data.iterrows():
                    main_ax.scatter(
                        plant['经度'], plant['纬度'],
                        c=self.facility_colors['ft_plant'], s=100,
                        marker=self.facility_markers['ft_plant'],
                        edgecolors='black', linewidth=1.0,
                        transform=self.data_crs, zorder=15, alpha=0.9
                    )
                    facility_stats['ft_plant'] += 1

        # 2. 绘制机场（从运输数据中提取）
        if all_data.get('transport_summary') is not None:
            transport_data = all_data['transport_summary']

            # 过滤华北地区的运输数据
            region_transport = transport_data[
                (transport_data['终点纬度'] >= self.map_extent[2]) &
                (transport_data['终点纬度'] <= self.map_extent[3]) &
                (transport_data['终点经度'] >= self.map_extent[0]) &
                (transport_data['终点经度'] <= self.map_extent[1])
            ]

            if len(region_transport) > 0:
                # 提取机场终点
                airports = region_transport[
                    region_transport['终点'].str.contains('机场|airport', case=False, na=False)
                ][['终点', '终点纬度', '终点经度']].drop_duplicates()

                if len(airports) > 0:
                    print(f"正在绘制 {len(airports)} 个机场...")
                    for _, airport in airports.iterrows():
                        main_ax.scatter(
                            airport['终点经度'], airport['终点纬度'],
                            c=self.facility_colors['airport'], s=100,
                            marker=self.facility_markers['airport'],
                            edgecolors='white', linewidth=1.0,
                            transform=self.data_crs, zorder=25, alpha=0.9
                        )
                        facility_stats['airport'] += 1

        # 3. 绘制运输路径
        if all_data.get('transport_summary') is not None:
            transport_data = all_data['transport_summary']

            # 过滤华北地区运输数据
            region_transport = transport_data[
                (transport_data['起点纬度'] >= self.map_extent[2]) &
                (transport_data['起点纬度'] <= self.map_extent[3]) &
                (transport_data['起点经度'] >= self.map_extent[0]) &
                (transport_data['起点经度'] <= self.map_extent[1]) &
                (transport_data['终点纬度'] >= self.map_extent[2]) &
                (transport_data['终点纬度'] <= self.map_extent[3]) &
                (transport_data['终点经度'] >= self.map_extent[0]) &
                (transport_data['终点经度'] <= self.map_extent[1])
            ]

            if len(region_transport) > 0:
                print(f"正在绘制 {len(region_transport)} 条运输路径...")

                # 按货物类型分类
                saf_routes = region_transport[region_transport['货物类型'].str.contains('SAF|MTJ', case=False, na=False)]
                ng_routes = region_transport[region_transport['货物类型'].str.contains('天然气|NG', case=False, na=False)]

                # 绘制SAF运输路径
                for _, route in saf_routes.iterrows():
                    main_ax.plot(
                        [route['起点经度'], route['终点经度']],
                        [route['起点纬度'], route['终点纬度']],
                        color=self.transport_type_colors['SAF'],
                        alpha=0.7, linewidth=2.5,
                        transform=self.data_crs, zorder=6
                    )

                # 绘制天然气运输路径
                for _, route in ng_routes.iterrows():
                    main_ax.plot(
                        [route['起点经度'], route['终点经度']],
                        [route['起点纬度'], route['终点纬度']],
                        color=self.transport_type_colors['NG'],
                        alpha=0.6, linewidth=2.0,
                        transform=self.data_crs, zorder=5
                    )

                print(f"  - SAF运输: {len(saf_routes)} 条")
                print(f"  - 天然气运输: {len(ng_routes)} 条")

        # 创建图例
        if facility_stats.get('ft_plant', 0) > 0:
            legend_elements.append(
                plt.scatter([], [], c=self.facility_colors['ft_plant'], s=100,
                          marker=self.facility_markers['ft_plant'],
                          edgecolors='black', linewidth=1.0,
                          label=f'FT工厂 ({facility_stats["ft_plant"]}个)')
            )

        if facility_stats.get('airport', 0) > 0:
            legend_elements.append(
                plt.scatter([], [], c=self.facility_colors['airport'], s=100,
                          marker=self.facility_markers['airport'],
                          edgecolors='white', linewidth=1.0,
                          label=f'机场 ({facility_stats["airport"]}个)')
            )

        # 添加运输类型图例
        legend_elements.append(
            plt.Line2D([0], [0], color=self.transport_type_colors['SAF'],
                      linewidth=3, label='SAF运输')
        )
        legend_elements.append(
            plt.Line2D([0], [0], color=self.transport_type_colors['NG'],
                      linewidth=3, label='天然气运输')
        )

        # 添加图例
        if legend_elements:
            main_ax.legend(handles=legend_elements, loc='upper right',
                          fontsize=9, framealpha=0.9, ncol=1)

        # 添加标题
        total_facilities = sum(facility_stats.values())
        plt.suptitle(
            f'FT一步法SAF供应链网络图 (35°N-45°N, 110°E-120°E)\n'
            f'设施: {total_facilities}个',
            fontsize=14, y=0.95, fontweight='bold'
        )

        # 添加统计信息
        stats_text = "设施统计:\n"
        if facility_stats.get('ft_plant', 0) > 0:
            stats_text += f"  FT工厂: {facility_stats['ft_plant']}个\n"
        if facility_stats.get('airport', 0) > 0:
            stats_text += f"  机场: {facility_stats['airport']}个\n"

        main_ax.text(0.02, 0.02, stats_text, transform=main_ax.transAxes,
                    fontsize=8, bbox=dict(boxstyle="round,pad=0.3",
                    facecolor="white", alpha=0.9), verticalalignment='bottom')

        # 添加装饰
        self.add_decorations(main_ax, mini_ax)

        print(f"设施统计: {facility_stats}")

        return fig, main_ax, mini_ax, facility_stats

    def find_latest_files(self, results_dir=None):
        """查找最新的所有相关数据文件"""
        if results_dir is None:
            # FT一步法结果目录
            results_dir = Path(__file__).parent.parent.parent / 'results' / 'ft_one_step'

        results_dir = Path(results_dir)

        # FT一步法需要的文件类型
        file_patterns = {
            'transport_summary': 'transport_summary_*.csv',
            'ft_plants': 'infrastructure_summary_*.csv',
            'ng_pipelines': 'ng_pipelines_*.csv'
        }

        latest_files = {}

        for file_type, pattern in file_patterns.items():
            files = list(results_dir.glob(pattern))
            if files:
                latest_file = max(files, key=lambda x: x.stat().st_mtime)
                latest_files[file_type] = str(latest_file)
                self.logger.info(f"找到最新的{file_type}文件: {latest_file}")
            else:
                self.logger.warning(f"未找到{file_type}文件: {pattern}")
                latest_files[file_type] = None

        return latest_files

    def save_visualization(self, fig, filename=None, output_dir=None):
        """保存可视化结果"""
        if output_dir is None:
            output_dir = Path(__file__).parent.parent.parent / 'results' / 'ft_one_step' / 'visualizations'

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f'ft_one_step_network_{timestamp}.png'

        output_path = output_dir / filename

        fplt.savefig(str(output_path), dpi=300, bbox_inches='tight',
                    facecolor='white', edgecolor='none')
        plt.close(fig)

        print(f"FT一步法网络地图已保存: {output_path}")
        return str(output_path)

def main():
    """主函数"""
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    visualizer = TransportRouteVisualizerOneStep()

    # 查找最新数据文件
    latest_files = visualizer.find_latest_files()

    print("[INFO] 正在加载FT一步法数据文件...")
    all_data = {}

    # 加载所有可用的数据
    if latest_files['transport_summary']:
        print(f"加载运输数据: {latest_files['transport_summary']}")
        all_data['transport_summary'] = visualizer.load_transport_data(latest_files['transport_summary'])

    if latest_files['ft_plants']:
        print(f"加载FT工厂数据: {latest_files['ft_plants']}")
        all_data['ft_plants'] = visualizer.load_ft_plant_data(latest_files['ft_plants'])

    if latest_files['ng_pipelines']:
        print(f"加载天然气管道数据: {latest_files['ng_pipelines']}")
        all_data['ng_pipelines'] = visualizer.load_ng_pipeline_data(latest_files['ng_pipelines'])

    # 检查是否有任何数据加载成功
    valid_data = {k: v for k, v in all_data.items() if v is not None and len(v) > 0}

    if not valid_data:
        print("[ERROR] 未找到任何有效的数据文件")
        print("请确保已运行FT一步法优化模型生成相关数据文件")
        return

    print(f"\n[SUCCESS] 成功加载 {len(valid_data)} 类数据:")
    for data_type, data in valid_data.items():
        print(f"  - {data_type}: {len(data)} 条记录")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 创建FT一步法网络可视化
    print("\n[INFO] 创建FT一步法供应链网络图...")
    result = visualizer.create_ft_one_step_network_visualization(valid_data)

    if result is not None:
        fig, main_ax, mini_ax, facility_stats = result

        # 保存可视化
        filename = f'ft_one_step_network_{timestamp}.png'
        viz_path = visualizer.save_visualization(fig, filename)

        print(f"\n{'='*60}")
        print(f"[SUCCESS] FT一步法供应链网络可视化完成!")
        print(f"[OUTPUT] 图表文件已生成: {filename}")
        print(f"[PATH] 完整路径: {viz_path}")
        print(f"[FACILITIES] 设施统计: {facility_stats}")
        print(f"{'='*60}")
    else:
        print("[WARNING] FT一步法网络可视化创建失败")

if __name__ == "__main__":
    main()
