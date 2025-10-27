"""
基于frykit库的运输路径可视化器
根据transport_summary数据可视化天然气供应链运输路径
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
from cartopy.feature import LAND, RIVERS
import json

class TransportRouteVisualizer:
    """运输路径可视化器"""
    
    def __init__(self):
        """初始化可视化器"""
        # 设置日志（需要最先设置）
        self.logger = logging.getLogger(__name__)
        
        # 设置中文字体支持（按优先级排序）
        matplotlib.rcParams['font.sans-serif'] = [
            'Noto Sans CJK SC',     # Noto Sans 中文简体
            'WenQuanYi Zen Hei',    # 文泉驿正黑
            'AR PL UKai CN',        # AR PL 楷体
            'AR PL UMing CN',       # AR PL 明体
            'DejaVu Sans',          # 备用西文字体
            'SimHei',               # Windows 黑体（如果存在）
            'sans-serif'            # 系统默认
        ]
        matplotlib.rcParams['axes.unicode_minus'] = False
        
        # 验证字体设置
        self._verify_font_setup()
        
        # 设置投影
        self.map_crs = fplt.CN_AZIMUTHAL_EQUIDISTANT
        self.data_crs = fplt.PLATE_CARREE
        
        # 设置华北地区范围和刻度
        self.map_extent = (110, 120, 35, 45)  # 110E-120E, 35N-45N
        self.xticks = np.arange(110, 121, 2)  # 每2度一个刻度
        self.yticks = np.arange(35, 46, 2)    # 每2度一个刻度
        
        # 设施间连接线颜色映射（基于起点和终点设施类型）- 更鲜明的颜色
        self.connection_colors = {
            'solar_to_lng': '#FF8C00',       # 深橙色 - 太阳能电站到LNG终端
            'wind_to_lng': '#00FF00',        # 鲜绿色 - 风电站到LNG终端
            'lng_to_pipeline': '#0000FF',    # 蓝色 - LNG终端到管段
            'pipeline_to_airport': '#FF0000', # 红色 - 管段到机场
            'lng_to_airport': '#8A2BE2',     # 蓝紫色 - LNG终端到机场
            'solar_to_airport': '#FF1493',   # 深粉色 - 太阳能到机场
            'wind_to_airport': '#32CD32',    # 酸橙绿 - 风电到机场
            'renewable_to_pipeline': '#FF69B4', # 热粉色 - 可再生能源到管段
            'pipeline_to_pipeline': '#FFA500',  # 橙色 - 管段间连接
            'default': '#000000'             # 黑色 - 默认连接
        }
        
        # 设施类型标记映射（更清晰的区分）
        self.facility_markers = {
            'solar': 'v',            # 下三角形 - 太阳能电站
            'wind': '^',             # 上三角形 - 风电站
            'pipeline': 'D',         # 菱形 - 管段
            'lng': 's',              # 方形 - LNG终端
            'airport': 'o',          # 圆形 - 机场
            'default': 'o'           # 默认圆形
        }
        
        # 设施类型颜色映射（专门针对这5种设施）
        self.facility_colors = {
            'solar': '#FFD700',          # 金黄色 - 太阳能电站
            'wind': '#32CD32',           # 绿色 - 风电站
            'pipeline': '#FF6347',       # 橙红色 - 管段
            'lng': '#4169E1',            # 蓝色 - LNG终端
            'airport': '#9370DB',        # 紫色 - 机场
            'cluster_center': '#FF1493', # 深粉色 - 聚类中心
            'default': '#95A5A6'         # 灰色 - 默认
        }

        # 聚类路径颜色方案
        self.cluster_colors = plt.cm.tab20.colors  # 使用20种不同颜色

        # 聚类路径线型
        self.cluster_line_styles = {
            'layer1': '--',  # 虚线 - 氢气点到聚类中心
            'layer2': '-',   # 实线 - 聚类中心到管道接入点
            'layer3': '-',   # 实线 - 管道网络到目的地
            'noise': ':'     # 点线 - 独立点直连
        }
        
        # GraphHopper缓存路径
        self.graphhopper_cache_path = Path(__file__).parent / 'cache' / 'graphhopper_routes.db'
    
    def _verify_font_setup(self):
        """验证字体设置是否正确"""
        try:
            import matplotlib.font_manager as fm
            
            # 简化字体设置，避免复杂的字体检测逻辑
            available_fonts = [f.name for f in fm.fontManager.ttflist]
            
            # 优先使用常见的中文字体
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
                # 使用默认字体配置，避免中文显示问题
                matplotlib.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'sans-serif']
                self.logger.warning("未找到合适的中文字体，使用默认字体")
                
        except Exception as e:
            self.logger.warning(f"字体设置失败: {e}")
            matplotlib.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'sans-serif']
        
        # 运输类型颜色映射
        self.transport_type_colors = {
            'MTJ': '#E67E22',        # 橙色 - 绿色甲醇航空燃料(MTJ)运输
            'H2': '#9B59B6',         # 紫色 - 氢气运输
            'NG': '#3498DB',         # 蓝色 - 天然气运输
            '氢气': '#9B59B6',       # 紫色 - 氢气运输(中文)
            'default': '#95A5A6'     # 灰色 - 默认
        }

    
    def parse_coordinates(self, coord_str):
        """解析坐标字符串"""
        try:
            if pd.isna(coord_str) or coord_str == '':
                return None, None
            
            # 去除首尾空格和引号
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
        """从数据行中获取真实路径坐标，根据运输方式选择合适的路径数据"""
        try:
            # 获取运输方式
            transport_mode = row.get('运输方式', 'truck').lower()

            # 优先从数据中读取路径坐标
            if '路径坐标' in row and row['路径坐标'] and row['路径坐标'] != '[]':
                try:
                    coordinates = json.loads(row['路径坐标'])

                    if transport_mode == 'pipeline':
                        # 管道运输：使用数据中的管道路径坐标
                        if coordinates and len(coordinates) >= 2:  # 管道路径至少需要起点和终点
                            self.logger.debug(f"使用管道路径坐标: {len(coordinates)}个点")
                            return coordinates
                    elif transport_mode == 'truck':
                        # 罐车运输：如果有详细路径坐标就使用，否则fallback到GraphHopper
                        if coordinates and len(coordinates) > 2:  # 确保有真实路径点
                            self.logger.debug(f"使用罐车路径坐标: {len(coordinates)}个点")
                            return coordinates

                except (json.JSONDecodeError, ValueError) as e:
                    self.logger.warning(f"路径坐标解析失败: {row['路径坐标']}, 错误: {e}")

            # 根据运输方式决定fallback策略
            if transport_mode == 'pipeline':
                # 管道运输：如果没有管道路径坐标，不使用GraphHopper（因为GraphHopper是针对罐车的）
                self.logger.warning(f"管道运输缺少路径坐标，无法获取详细路径")
                return None
            else:
                # 罐车运输：尝试从GraphHopper缓存获取
                self.logger.debug(f"罐车运输：尝试从GraphHopper缓存获取路径坐标")
                return self.get_real_route_coordinates_from_cache(
                    row['起点纬度'], row['起点经度'],
                    row['终点纬度'], row['终点经度']
                )

        except Exception as e:
            self.logger.debug(f"获取路径坐标失败: {e}")
            return None

    def get_real_route_coordinates_using_graphhopper(self, start_lat, start_lon, end_lat, end_lon):
        """使用GraphHopper API直接获取详细路径坐标"""
        try:
            # 导入GraphHopper路径规划引擎
            from graphhopper_routing_engine import GraphHopperRoutingEngine
            
            # 创建临时的GraphHopper引擎实例
            routing_engine = GraphHopperRoutingEngine(
                osm_pbf_path="data/china-latest.osm.pbf",  # 假设OSM数据在这个位置
                graphhopper_host="localhost",
                graphhopper_port=8989,
                cache_dir=str(self.graphhopper_cache_path.parent),
                enable_cache=False  # 禁用数据库缓存（查询比计算更慢）
            )
            
            # 获取详细路径（包含路径坐标）
            route_result = routing_engine.get_route_details(
                start_lat=start_lat,
                start_lon=start_lon, 
                end_lat=end_lat,
                end_lon=end_lon,
                vehicle='car'
            )
            
            if route_result and route_result.get('route_found'):
                coordinates = route_result.get('route_coordinates')
                if coordinates and len(coordinates) > 2:
                    # 转换坐标格式：GraphHopper返回[lon, lat]，我们需要[lat, lon]
                    formatted_coords = [[coord[1], coord[0]] for coord in coordinates]
                    return formatted_coords
                    
            return None
            
        except Exception as e:
            self.logger.debug(f"使用GraphHopper获取路径坐标失败: {e}")
            return None
    
    def get_real_route_coordinates_from_cache(self, start_lat, start_lon, end_lat, end_lon):
        """从GraphHopper缓存获取真实路径坐标"""
        try:
            if not self.graphhopper_cache_path.exists():
                return None
                
            # 计算缓存键（与GraphHopper引擎保持一致）
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
                    if coordinates and len(coordinates) > 2:  # 确保有真实路径点
                        return coordinates
                except json.JSONDecodeError:
                    pass
                    
            return None
            
        except Exception as e:
            self.logger.debug(f"从缓存获取真实路径坐标失败: {e}")
            return None
    
    def parse_cluster_info(self, cluster_str, cluster_type='H2'):
        """解析聚类信息字符串

        Args:
            cluster_str: 聚类信息字符串，格式如 "聚类0_(中心:36.3358,114.6340)" 或 "CO2聚类0_(中心:36.3358,114.6340)"
            cluster_type: 聚类类型 ('H2' for 氢气, 'CO2' for CO2)

        Returns:
            tuple: (cluster_id, center_lat, center_lon, is_co2_cluster) 或 (None, None, None, False)
        """
        if pd.isna(cluster_str) or not cluster_str:
            return None, None, None, False

        try:
            # 提取聚类ID和中心坐标
            # 格式1: "聚类0_(中心:36.3358,114.6340)" - 氢气聚类
            # 格式2: "CO2聚类0_(中心:36.3358,114.6340)" - CO2聚类

            # 尝试匹配CO2聚类
            co2_match = re.match(r'CO2聚类(\d+)_\(中心:([\d.]+),([\d.]+)\)', str(cluster_str))
            if co2_match:
                cluster_id = int(co2_match.group(1))
                center_lat = float(co2_match.group(2))
                center_lon = float(co2_match.group(3))
                return cluster_id, center_lat, center_lon, True

            # 尝试匹配氢气聚类
            h2_match = re.match(r'聚类(\d+)_\(中心:([\d.]+),([\d.]+)\)', str(cluster_str))
            if h2_match:
                cluster_id = int(h2_match.group(1))
                center_lat = float(h2_match.group(2))
                center_lon = float(h2_match.group(3))
                return cluster_id, center_lat, center_lon, False

        except Exception as e:
            self.logger.debug(f"解析聚类信息失败: {cluster_str}, 错误: {e}")

        return None, None, None, False

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

            # 检查并标记聚类数据
            if '聚类信息' in china_data.columns:
                has_cluster = china_data['聚类信息'].notna().sum()
                self.logger.info(f"数据中包含 {has_cluster} 条聚类路径记录")

            self.logger.info(f"最终有效数据: {len(china_data)} 条")
            return china_data
            
        except Exception as e:
            self.logger.error(f"加载运输数据失败: {e}")
            return None
    
    def load_renewable_energy_data(self, csv_file_path):
        """加载可再生能源设施数据"""
        try:
            if not csv_file_path or not Path(csv_file_path).exists():
                self.logger.warning("可再生能源设施文件不存在")
                return None
                
            df = pd.read_csv(csv_file_path, encoding='utf-8')
            self.logger.info(f"成功加载可再生能源数据，共 {len(df)} 个设施")
            
            # 确保坐标在中国范围内
            china_data = df[
                (df['纬度'] >= 18) & (df['纬度'] <= 54) &
                (df['经度'] >= 73) & (df['经度'] <= 135)
            ]
            
            outside_china = len(df) - len(china_data)
            if outside_china > 0:
                self.logger.warning(f"过滤掉 {outside_china} 个中国范围外的可再生能源设施")
            
            return china_data
            
        except Exception as e:
            self.logger.error(f"加载可再生能源数据失败: {e}")
            return None
    
    def load_hydrogen_transport_data(self, csv_file_path):
        """加载氢能运输数据"""
        try:
            if not csv_file_path or not Path(csv_file_path).exists():
                self.logger.warning("氢能运输文件不存在")
                return None
                
            df = pd.read_csv(csv_file_path, encoding='utf-8')
            self.logger.info(f"成功加载氢能运输数据，共 {len(df)} 条记录")
            
            # 过滤掉无效坐标
            valid_data = df.dropna(subset=['起点纬度', '起点经度', '终点纬度', '终点经度'])
            
            # 确保坐标在中国范围内
            china_data = valid_data[
                (valid_data['起点纬度'] >= 18) & (valid_data['起点纬度'] <= 54) &
                (valid_data['起点经度'] >= 73) & (valid_data['起点经度'] <= 135) &
                (valid_data['终点纬度'] >= 18) & (valid_data['终点纬度'] <= 54) &
                (valid_data['终点经度'] >= 73) & (valid_data['终点经度'] <= 135)
            ]
            
            return china_data
            
        except Exception as e:
            self.logger.error(f"加载氢能运输数据失败: {e}")
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
    
    def load_ng_transport_data(self, csv_file_path):
        """加载天然气运输数据"""
        try:
            if not csv_file_path or not Path(csv_file_path).exists():
                self.logger.warning("天然气运输文件不存在")
                return None
                
            df = pd.read_csv(csv_file_path, encoding='utf-8')
            self.logger.info(f"成功加载天然气运输数据，共 {len(df)} 条记录")
            
            # 过滤掉无效坐标
            valid_data = df.dropna(subset=['起点纬度', '起点经度', '终点纬度', '终点经度'])
            
            # 确保坐标在中国范围内
            china_data = valid_data[
                (valid_data['起点纬度'] >= 18) & (valid_data['起点纬度'] <= 54) &
                (valid_data['起点经度'] >= 73) & (valid_data['起点经度'] <= 135) &
                (valid_data['终点纬度'] >= 18) & (valid_data['终点纬度'] <= 54) &
                (valid_data['终点经度'] >= 73) & (valid_data['终点经度'] <= 135)
            ]
            
            return china_data
            
        except Exception as e:
            self.logger.error(f"加载天然气运输数据失败: {e}")
            return None

    def load_hydrogen_pipeline_transport_data(self, csv_file_path):
        """加载氢气管道运输数据"""
        try:
            if not csv_file_path or not Path(csv_file_path).exists():
                self.logger.warning("氢气管道运输文件不存在")
                return None

            df = pd.read_csv(csv_file_path, encoding='utf-8')
            self.logger.info(f"成功加载氢气管道运输数据，共 {len(df)} 条记录")

            # 过滤掉无效坐标
            valid_data = df.dropna(subset=['起点纬度', '起点经度', '终点纬度', '终点经度'])

            # 确保坐标在中国范围内
            china_data = valid_data[
                (valid_data['起点纬度'] >= 18) & (valid_data['起点纬度'] <= 54) &
                (valid_data['起点经度'] >= 73) & (valid_data['起点经度'] <= 135) &
                (valid_data['终点纬度'] >= 18) & (valid_data['终点纬度'] <= 54) &
                (valid_data['终点经度'] >= 73) & (valid_data['终点经度'] <= 135)
            ]

            self.logger.info(f"有效氢气管道运输数据: {len(china_data)} 条记录")
            return china_data

        except Exception as e:
            self.logger.error(f"加载氢气管道运输数据失败: {e}")
            return None

    def load_co2_clustering_data(self):
        """加载CO2聚类数据和CO2源点数据"""
        try:
            import json

            # 路径: src/visualization/ -> src/ -> green_hydrogen_supply_chain_optimization/
            current_dir = Path(__file__).parent
            project_root = current_dir.parent.parent

            # 加载CO2聚类结果
            co2_clustering_file = project_root / 'co2_clustering_results.json'
            co2_sources_file = project_root / 'data' / 'co2_capture_sources.csv'

            if not co2_clustering_file.exists():
                self.logger.warning(f"CO2聚类结果文件不存在: {co2_clustering_file}")
                return None, None

            if not co2_sources_file.exists():
                self.logger.warning(f"CO2源点数据文件不存在: {co2_sources_file}")
                return None, None

            # 读取聚类结果
            with open(co2_clustering_file, 'r', encoding='utf-8') as f:
                clustering_results = json.load(f)

            # 读取CO2源点数据
            co2_sources_df = pd.read_csv(co2_sources_file, encoding='utf-8')

            self.logger.info(f"成功加载CO2聚类数据: {clustering_results.get('total_clusters', 0)} 个聚类")
            self.logger.info(f"成功加载CO2源点数据: {len(co2_sources_df)} 个源点")

            return clustering_results, co2_sources_df

        except Exception as e:
            self.logger.error(f"加载CO2聚类数据失败: {e}")
            return None, None
    
    def load_lng_terminal_data(self, csv_file_path):
        """加载LNG终端数据"""
        try:
            if not csv_file_path or not Path(csv_file_path).exists():
                self.logger.warning("LNG终端文件不存在") 
                return None
                
            df = pd.read_csv(csv_file_path, encoding='utf-8')
            self.logger.info(f"成功加载LNG终端数据，共 {len(df)} 个终端")
            
            # 确保坐标在中国范围内
            china_data = df[
                (df['纬度'] >= 18) & (df['纬度'] <= 54) &
                (df['经度'] >= 73) & (df['经度'] <= 135)
            ]
            
            return china_data
            
        except Exception as e:
            self.logger.error(f"加载LNG终端数据失败: {e}")
            return None
    
    def create_base_map(self, figsize=(14, 10)):
        """创建基础地图（华北地区）"""
        try:
            # 尝试使用完整的frykit功能
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

            # 不创建南海小地图，因为华北地区不需要
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

    def create_simple_base_map(self, figsize=(14, 10)):
        """创建简化的基础地图（不依赖frykit）"""
        fig = plt.figure(figsize=figsize)
        main_ax = fig.add_subplot()

        # 设置华北地区范围
        main_ax.set_xlim(110, 120)
        main_ax.set_ylim(35, 45)
        main_ax.set_xlabel('经度 (°E)', fontsize=12)
        main_ax.set_ylabel('纬度 (°N)', fontsize=12)
        main_ax.grid(True, alpha=0.3)
        main_ax.set_aspect('equal', adjustable='box')

        # 设置标题
        main_ax.set_title('华北地区能源基础设施网络图 (35°N-45°N, 110°E-120°E)',
                         fontsize=14, fontweight='bold', pad=20)

        # 不创建小地图
        mini_ax = None

        return fig, main_ax, mini_ax

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
            
        # 确保坐标在华北地区范围内
        filtered_data = data[
            (data[lat_col] >= min_lat) & (data[lat_col] <= max_lat) &
            (data[lon_col] >= min_lon) & (data[lon_col] <= max_lon)
        ]
        
        outside_region = len(data) - len(filtered_data)
        if outside_region > 0:
            self.logger.info(f"过滤掉 {outside_region} 个华北地区范围外的设施")
        
        return filtered_data
    
    def get_connection_color(self, origin_name, destination_name):
        """根据起点和终点设施类型确定连接线颜色"""
        origin_type = self.classify_facility_type(origin_name)
        dest_type = self.classify_facility_type(destination_name)
        
        # 根据设施类型组合确定颜色
        connection_key = f"{origin_type}_to_{dest_type}"
        
        # 检查是否有预定义的连接颜色
        if connection_key in self.connection_colors:
            return self.connection_colors[connection_key]
        
        # 特殊情况处理 - 更详细的连接类型
        if origin_type == 'solar' and dest_type == 'lng':
            return self.connection_colors['solar_to_lng']
        elif origin_type == 'wind' and dest_type == 'lng':
            return self.connection_colors['wind_to_lng']
        elif origin_type == 'solar' and dest_type == 'airport':
            return self.connection_colors['solar_to_airport']
        elif origin_type == 'wind' and dest_type == 'airport':
            return self.connection_colors['wind_to_airport']
        elif origin_type == 'lng' and dest_type == 'airport':
            return self.connection_colors['lng_to_airport']
        elif origin_type == 'lng' and dest_type == 'pipeline':
            return self.connection_colors['lng_to_pipeline']
        elif origin_type == 'pipeline' and dest_type == 'airport':
            return self.connection_colors['pipeline_to_airport']
        elif origin_type == 'pipeline' and dest_type == 'pipeline':
            return self.connection_colors['pipeline_to_pipeline']
        elif origin_type in ['solar', 'wind'] and dest_type == 'pipeline':
            return self.connection_colors['renewable_to_pipeline']
        else:
            return self.connection_colors['default']
    
    def classify_facility_type(self, facility_name, facility_type=None):
        """根据设施名称和类型确定具体的设施分类"""
        facility_name = str(facility_name).lower()
        facility_type = str(facility_type).lower() if facility_type else ""
        
        # DEBUG: 打印分类信息
        # print(f"DEBUG classify: '{facility_name}' -> ", end="")
        
        # 太阳能电站
        if any(keyword in facility_name or keyword in facility_type 
               for keyword in ['solar', '光伏', '太阳能', 'pv']):
            # print("solar")
            return 'solar'
        
        # 风电站
        elif any(keyword in facility_name or keyword in facility_type 
                 for keyword in ['wind', '风电', '风力', '风能']):
            # print("wind") 
            return 'wind'
        
        # LNG终端
        elif any(keyword in facility_name or keyword in facility_type 
                 for keyword in ['lng', '液化天然气', 'terminal']):
            # print("lng")
            return 'lng'
        
        # 管段/管道
        elif any(keyword in facility_name or keyword in facility_type 
                 for keyword in ['pipeline', '管道', '管段', 'pipe']):
            # print("pipeline")
            return 'pipeline'
        
        # 机场
        elif any(keyword in facility_name or keyword in facility_type 
                 for keyword in ['airport', '机场', '航空']):
            # print("airport")
            return 'airport'
        
        else:
            # print("default")
            return 'default'
    
    def map_facility_type(self, facility_type):
        """将设施类型映射为连接系统使用的标准名称"""
        if not facility_type:
            return 'unknown'
            
        facility_type = str(facility_type).strip()
        
        # 更精确的类型识别
        if '太阳能' in facility_type or 'solar' in facility_type.lower():
            return 'solar'
        elif '风电' in facility_type or 'wind' in facility_type.lower():
            return 'wind'  
        elif '储氢' in facility_type or 'hydrogen' in facility_type.lower() or 'storage' in facility_type.lower():
            return 'storage'
        elif '机场' in facility_type or 'airport' in facility_type.lower():
            return 'airport'
        elif 'lng' in facility_type.lower() or '天然气' in facility_type:
            return 'lng'
        elif '可再生' in facility_type:
            return 'solar'  # 默认为太阳能
        elif '生产' in facility_type:
            return 'production'
        else:
            # 返回小写的原始类型
            return facility_type.lower().replace(' ', '_')
    
    def normalize_transport_volume(self, volumes, min_width=0.5, max_width=4.0):
        """标准化运输量为线条宽度"""
        volumes = pd.to_numeric(volumes, errors='coerce')
        volumes = volumes.fillna(0)
        
        if volumes.max() == volumes.min():
            return np.full(len(volumes), (min_width + max_width) / 2)
        
        normalized = (volumes - volumes.min()) / (volumes.max() - volumes.min())
        return min_width + normalized * (max_width - min_width)
    
    def create_north_china_facilities_with_connections_visualization(self, all_data):
        """创建华北地区能源设施分布图，包含设施间连接线"""
        print("正在创建华北地区能源设施及连接网络图...")
        
        # 创建基础地图
        fig, main_ax, mini_ax = self.create_base_map(figsize=(14, 10))

        # 使用完整模式，不再支持简化模式
        legend_elements = []
        facility_stats = {
            'solar': 0,
            'wind': 0,
            'lng': 0,
            'airport': 0
        }
        connection_stats = {}

        # 1. 绘制可再生能源电站（区分聚类和独立）
        clustered_stations = set()
        standalone_stations = set()

        # 从运输数据获取聚类和独立电站信息
        if all_data.get('transport_summary') is not None:
            transport_data = all_data['transport_summary']
            region_transport = transport_data[
                (transport_data['起点纬度'] >= self.map_extent[2]) &
                (transport_data['起点纬度'] <= self.map_extent[3]) &
                (transport_data['起点经度'] >= self.map_extent[0]) &
                (transport_data['起点经度'] <= self.map_extent[1])
            ]

            # 收集聚类电站
            cluster_data = region_transport[region_transport['聚类信息'].notna()]
            for _, row in cluster_data.iterrows():
                clustered_stations.add(row['起点'])

            # 收集独立电站
            standalone_data = region_transport[
                (region_transport['聚类信息'].isna()) &
                (region_transport['起点类型'] == '氢气生产站')
            ]
            for _, row in standalone_data.iterrows():
                standalone_stations.add(row['起点'])

        if all_data.get('renewable_energy') is not None:
            renewable_data = self.filter_data_by_region(all_data['renewable_energy'])

            if renewable_data is not None and len(renewable_data) > 0:
                print(f"正在绘制 {len(renewable_data)} 个可再生能源电站...")
                cluster_count = 0
                standalone_count = 0

                for _, facility in renewable_data.iterrows():
                    facility_name = facility.get('位置ID', '')

                    # 判断是聚类还是独立
                    is_clustered = facility_name in clustered_stations
                    is_standalone = facility_name in standalone_stations

                    if is_clustered:
                        # 聚类电站 - 实心圆
                        main_ax.scatter(
                            facility['经度'], facility['纬度'],
                            c='orange', s=80,
                            marker='o',
                            edgecolors='black', linewidth=1,
                            transform=self.data_crs, zorder=20, alpha=0.9
                        )
                        cluster_count += 1
                    elif is_standalone:
                        # 独立电站 - 空心圆
                        main_ax.scatter(
                            facility['经度'], facility['纬度'],
                            c='white', s=80,
                            marker='o',
                            edgecolors='orange', linewidth=2,
                            transform=self.data_crs, zorder=20, alpha=0.9
                        )
                        standalone_count += 1
                    else:
                        # 其他电站 - 默认样式
                        main_ax.scatter(
                            facility['经度'], facility['纬度'],
                            c='gold', s=60,
                            marker='v',
                            edgecolors='black', linewidth=0.8,
                            transform=self.data_crs, zorder=20, alpha=0.9
                        )

                facility_stats['solar'] = cluster_count + standalone_count
                print(f"  聚类电站: {cluster_count}个, 独立电站: {standalone_count}个")
        
        # 3. 绘制天然气管段 - 已移除管段点标记，只保留管道网络线条
        # if all_data.get('ng_pipelines') is not None:
        #     pipeline_data = self.filter_data_by_region(all_data['ng_pipelines'])
        #
        #     if pipeline_data is not None and len(pipeline_data) > 0:
        #         print(f"正在绘制 {len(pipeline_data)} 个管段...")
        #         for _, pipeline in pipeline_data.iterrows():
        #             main_ax.scatter(
        #                 pipeline['经度'], pipeline['纬度'],
        #                 c=self.facility_colors['pipeline'], s=60,
        #                 marker=self.facility_markers['pipeline'],
        #                 edgecolors='black', linewidth=0.8,
        #                 transform=self.data_crs, zorder=10, alpha=0.9  # zorder=10，高于连接线
        #             )
        #             facility_stats['pipeline'] += 1
        
        # 4. 绘制LNG终端
        # LNG终端已被用户要求移除，不进行可视化
        # if all_data.get('lng_terminals') is not None:
        #     lng_data = self.filter_data_by_region(all_data['lng_terminals'])
        #
        #     if lng_data is not None and len(lng_data) > 0:
        #         print(f"正在绘制 {len(lng_data)} 个LNG终端...")
        #         for _, terminal in lng_data.iterrows():
        #             main_ax.scatter(
        #                 terminal['经度'], terminal['纬度'],
        #                 c=self.facility_colors['lng'], s=80,
        #                 marker=self.facility_markers['lng'],
        #                 edgecolors='black', linewidth=0.8,
        #                 transform=self.data_crs, zorder=10, alpha=0.9
        #             )
        #             facility_stats['lng'] += 1
        
        # 5. 绘制机场（从运输数据中提取）
        airports_data = []
        if all_data.get('transport_summary') is not None:
            transport_data = all_data['transport_summary']
            
            # 过滤华北地区的运输数据
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
                # 提取机场终点
                airports = region_transport[
                    region_transport['终点'].str.contains('机场|airport', case=False, na=False)
                ][['终点', '终点纬度', '终点经度']].drop_duplicates()
                
                if len(airports) > 0:
                    print(f"正在绘制 {len(airports)} 个机场...")
                    for _, airport in airports.iterrows():
                        # 完整模式：始终使用transform，机场显示在最上层
                        main_ax.scatter(
                            airport['终点经度'], airport['终点纬度'],
                            c=self.facility_colors['airport'], s=100,
                            marker=self.facility_markers['airport'],
                            edgecolors='white', linewidth=1.0,
                            transform=self.data_crs, zorder=25, alpha=0.9  # 最上层显示
                        )
                        facility_stats['airport'] += 1
                
                airports_data = airports
                
        
        # 创建设施类型图例
        # 添加电站类型图例
        if cluster_count > 0:
            legend_elements.append(
                plt.scatter([], [], c='orange', s=80, marker='o',
                          edgecolors='black', linewidth=1,
                          label=f'聚类电站 ({cluster_count}个)')
            )
        if standalone_count > 0:
            legend_elements.append(
                plt.scatter([], [], c='white', s=80, marker='o',
                          edgecolors='orange', linewidth=2,
                          label=f'独立电站 ({standalone_count}个)')
            )

        # 机场
        if facility_stats.get('airport', 0) > 0:
            legend_elements.append(
                plt.scatter([], [], c=self.facility_colors['airport'], s=100,
                          marker=self.facility_markers['airport'],
                          edgecolors='white', linewidth=1.0,
                          label=f'机场 ({facility_stats["airport"]}个)')
            )
        
        # 创建连接类型图例
        connection_names = {
            'solar_to_lng': '太阳能→LNG',
            'wind_to_lng': '风电→LNG',
            'solar_to_airport': '太阳能→机场',
            'wind_to_airport': '风电→机场',
            'lng_to_pipeline': 'LNG→管段',
            'pipeline_to_airport': '管段→机场',
            'lng_to_airport': 'LNG→机场',
            'renewable_to_pipeline': '可再生能源→管段',
            'pipeline_to_pipeline': '管段间连接'
        }
        
        # 添加路径类型图例
        if 'real_route_lines' in locals() and 'straight_lines' in locals():
            if real_route_lines > 0:
                legend_elements.append(
                    plt.Line2D([0], [0], color='gray', linewidth=3, alpha=0.95,
                              solid_capstyle='round', solid_joinstyle='round',
                              label=f'详细道路路径 ({real_route_lines}条)')
                )
            
            if straight_lines > 0:
                legend_elements.append(
                    plt.Line2D([0], [0], color='gray', linewidth=3, alpha=0.7, linestyle='--',
                              label=f'直线估算路径 ({straight_lines}条)')
                )
        
        # 添加分隔线
        if legend_elements and connection_stats:
            legend_elements.append(plt.Line2D([0], [0], color='none', label='─── 连接类型 ───'))
        
        for connection_type, count in connection_stats.items():
            if count > 0 and connection_type in connection_names:
                color = self.connection_colors.get(connection_type, self.connection_colors['default'])
                legend_elements.append(
                    plt.Line2D([0], [0], color=color, linewidth=3, 
                              label=f'{connection_names[connection_type]} ({count}条)')
                )
        
        # 添加图例
        if legend_elements:
            main_ax.legend(handles=legend_elements, loc='upper right', 
                          fontsize=9, framealpha=0.9, ncol=1)
        
        # 添加标题
        total_facilities = sum(facility_stats.values())
        total_connections = sum(connection_stats.values())
        plt.suptitle(
            f'华北地区能源基础设施网络图 (35°N-45°N, 110°E-120°E)\n'
            f'设施: {total_facilities}个 | 连接: {total_connections}条', 
            fontsize=14, y=0.95, fontweight='bold'
        )
        
        # 添加统计信息
        stats_text = "网络统计:\n设施分布:\n"
        if cluster_count > 0:
            stats_text += f"  聚类电站: {cluster_count}个\n"
        if standalone_count > 0:
            stats_text += f"  独立电站: {standalone_count}个\n"
        if facility_stats.get('airport', 0) > 0:
            stats_text += f"  机场: {facility_stats['airport']}个\n"
        
        if connection_stats:
            stats_text += "\n连接分布:\n"
            for connection_type, count in connection_stats.items():
                if count > 0 and connection_type in connection_names:
                    stats_text += f"  {connection_names[connection_type]}: {count}条\n"

        # 添加三种管道网络连接（不同颜色），只显示与氢能运输相关的管道
        print("\n正在添加管道网络连接...")
        hydrogen_transport = all_data.get('hydrogen_transport')
        pipeline_stats = self._add_pipeline_networks_to_existing_map(main_ax, hydrogen_transport)

        # 添加设施到管道的简单直线连接
        print("正在添加设施到管道的直线连接...")
        self._add_simple_facility_to_pipeline_connections(main_ax, all_data)

        # 更新统计文本以包含管道信息
        if pipeline_stats and any(pipeline_stats.values()):
            stats_text += "\n管道网络:\n"
            pipeline_names = {
                'crude': '原油管道',
                'refined': '成品油管道',
                'natural_gas': '天然气管道'
            }
            for pipeline_type, count in pipeline_stats.items():
                if count > 0:
                    stats_text += f"  {pipeline_names[pipeline_type]}: {count}段\n"

        main_ax.text(0.02, 0.02, stats_text, transform=main_ax.transAxes,
                    fontsize=8, bbox=dict(boxstyle="round,pad=0.3",
                    facecolor="white", alpha=0.9), verticalalignment='bottom')

        # 更新图例以包含管道类型
        if pipeline_stats and any(pipeline_stats.values()):
            pipeline_colors = {
                'crude': '#8B4513',      # 棕色
                'refined': '#FF6B35',    # 橙红色
                'natural_gas': '#4169E1' # 皇家蓝
            }

            for pipeline_type, count in pipeline_stats.items():
                if count > 0:
                    legend_elements.append(
                        plt.Line2D([0], [0], color=pipeline_colors[pipeline_type],
                                  linewidth=2, label=f"{pipeline_names[pipeline_type]} ({count}段)")
                    )

            # 更新图例
            main_ax.legend(handles=legend_elements, loc='upper right',
                          fontsize=9, frameon=True, fancybox=True, shadow=True, framealpha=0.9)

        # 绘制氢气运输路径（区分聚类和独立点）
        print("\n正在添加氢气运输路径...")
        if all_data.get('transport_summary') is not None:
            transport_data = all_data['transport_summary']

            # 过滤华北地区的运输数据
            region_transport = transport_data[
                (transport_data['起点纬度'] >= self.map_extent[2]) &
                (transport_data['起点纬度'] <= self.map_extent[3]) &
                (transport_data['起点经度'] >= self.map_extent[0]) &
                (transport_data['起点经度'] <= self.map_extent[1])
            ]

            # 分离H2聚类数据、CO2聚类数据和独立点数据
            h2_cluster_data = []
            co2_cluster_data = []
            for idx, row in region_transport[region_transport['聚类信息'].notna()].iterrows():
                _, _, _, is_co2 = self.parse_cluster_info(row.get('聚类信息'))
                if is_co2:
                    co2_cluster_data.append(row)
                else:
                    h2_cluster_data.append(row)

            h2_cluster_data = pd.DataFrame(h2_cluster_data) if h2_cluster_data else pd.DataFrame()
            co2_cluster_data = pd.DataFrame(co2_cluster_data) if co2_cluster_data else pd.DataFrame()

            standalone_data = region_transport[
                (region_transport['聚类信息'].isna()) &
                (region_transport['起点类型'] == '氢气生产站')
            ]

            # 绘制H2聚类路径
            cluster_data = h2_cluster_data  # 保持原变量名兼容性
            if len(cluster_data) > 0:
                print(f"找到 {len(cluster_data)} 条H2聚类路径")

                # 收集聚类中心
                cluster_centers = {}
                for _, row in cluster_data.iterrows():
                    cluster_id, center_lat, center_lon, is_co2_cluster = self.parse_cluster_info(row.get('聚类信息'))
                    if cluster_id is not None and not is_co2_cluster:  # 只收集H2聚类中心
                        cluster_centers[cluster_id] = (center_lat, center_lon)

                print(f"收集到 {len(cluster_centers)} 个聚类中心")

                # 绘制聚类路径（三层）
                layer1_count = 0
                layer2_count = 0
                layer3_count = 0

                for idx, row in cluster_data.iterrows():
                    cluster_id, center_lat, center_lon, is_co2_cluster = self.parse_cluster_info(row.get('聚类信息'))

                    if cluster_id is not None and not is_co2_cluster:  # 只处理H2聚类
                        cluster_color = self.cluster_colors[cluster_id % len(self.cluster_colors)]

                        # Layer1: 可再生能源站 -> 聚类中心 (灰色虚线，与独立电站相同)
                        layer1_dist = row.get('Layer1距离(km)', 0)
                        print(f"  行{idx}: Layer1距离={layer1_dist}, Layer2距离={row.get('Layer2距离(km)', 0)}, Layer3距离={row.get('Layer3距离(km)', 0)}")

                        if layer1_dist > 0:
                            main_ax.plot(
                                [row['起点经度'], center_lon],
                                [row['起点纬度'], center_lat],
                                color='gray',
                                alpha=0.6,
                                linewidth=2,
                                linestyle=':',
                                zorder=20,
                                transform=self.data_crs
                            )
                            layer1_count += 1

                        # Layer2: 聚类中心 -> 管道接入点 (实线)
                        # 需要从路径坐标中找到管道接入点
                        layer2_dist = row.get('Layer2距离(km)', 0)
                        if layer2_dist > 0 and '路径坐标' in row and row['路径坐标'] and row['路径坐标'] != '[]':
                            try:
                                import json
                                from math import radians, cos, sin, asin, sqrt

                                path_coords = json.loads(row['路径坐标'])

                                # 计算两点间的距离（Haversine公式）
                                def haversine(lon1, lat1, lon2, lat2):
                                    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
                                    dlon = lon2 - lon1
                                    dlat = lat2 - lat1
                                    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
                                    c = 2 * asin(sqrt(a))
                                    r = 6371  # 地球半径，单位：公里
                                    return c * r

                                # 从聚类中心开始，累计距离找到Layer2终点（管道接入点）
                                cumulative_dist = 0
                                pipeline_access_point = None

                                # 注意：路径坐标的第一个点可能不是聚类中心，而是可再生能源站
                                # 我们需要找到离聚类中心最近的点，然后从那里开始计算Layer2

                                # 简化方法：使用Layer2距离在路径中找到对应的点
                                # Layer1终点 = 聚类中心位置
                                # Layer2起点 = 聚类中心，终点 = Layer1+Layer2距离对应的路径点

                                prev_point = (center_lon, center_lat)
                                target_dist = layer2_dist

                                # 从路径坐标中找最接近聚类中心的点作为起点
                                min_dist_to_center = float('inf')
                                start_idx = 0
                                for i, coord in enumerate(path_coords):
                                    dist = haversine(center_lon, center_lat, coord[0], coord[1])
                                    if dist < min_dist_to_center:
                                        min_dist_to_center = dist
                                        start_idx = i

                                # 从起点开始累计距离
                                cumulative_dist = 0
                                for i in range(start_idx + 1, len(path_coords)):
                                    seg_dist = haversine(
                                        path_coords[i-1][0], path_coords[i-1][1],
                                        path_coords[i][0], path_coords[i][1]
                                    )
                                    cumulative_dist += seg_dist

                                    # 如果累计距离接近Layer2距离，这就是管道接入点
                                    if abs(cumulative_dist - target_dist) < 1:  # 1km容差
                                        pipeline_access_point = path_coords[i]
                                        break

                                # 绘制Layer2：聚类中心 -> 管道接入点 (灰色虚线，与独立电站相同)
                                if pipeline_access_point:
                                    main_ax.plot(
                                        [center_lon, pipeline_access_point[0]],
                                        [center_lat, pipeline_access_point[1]],
                                        color='gray',
                                        alpha=0.6,
                                        linewidth=2,
                                        linestyle=':',
                                        zorder=20,
                                        transform=self.data_crs
                                    )
                                    layer2_count += 1
                                else:
                                    print(f"    警告：行{idx}无法找到管道接入点")

                            except Exception as e:
                                print(f"    错误：解析路径坐标失败 - {e}")

                print(f"绘制了 Layer1:{layer1_count}条, Layer2:{layer2_count}条, Layer3:{layer3_count}条")

                # 绘制聚类中心
                if cluster_centers:
                    print(f"正在绘制 {len(cluster_centers)} 个聚类中心...")
                    for cluster_id, (center_lat, center_lon) in cluster_centers.items():
                        cluster_color = self.cluster_colors[cluster_id % len(self.cluster_colors)]

                        # 绘制聚类中心点（星形标记，小尺寸）
                        main_ax.scatter(
                            center_lon, center_lat,
                            c=cluster_color, s=80, marker='*',
                            edgecolors='black', linewidth=1.5,
                            transform=self.data_crs, zorder=30, alpha=1.0
                        )

            # 绘制独立点路径
            if len(standalone_data) > 0:
                print(f"找到 {len(standalone_data)} 条独立点路径")
                for _, row in standalone_data.iterrows():
                    # 独立点用灰色虚线直连
                    main_ax.plot(
                        [row['起点经度'], row['终点经度']],
                        [row['起点纬度'], row['终点纬度']],
                        color='gray',
                        alpha=0.6,
                        linewidth=2,
                        linestyle=':',
                        zorder=20
                    )

            # 绘制CO2聚类数据（从单独文件加载）
            print("\n正在绘制CO2聚类数据...")

            # ========== 新增：从transport_summary提取实际运输的CO2源点和聚类 ==========
            active_co2_source_coords = set()  # 实际运输的CO2源点坐标 (lat, lon)
            active_co2_clusters = set()  # 实际运输的CO2聚类ID

            print(f"\n从transport_summary提取实际运输的CO2源点和聚类...")
            print(f"CO2聚类路径数据条数: {len(co2_cluster_data)}")

            for _, row in co2_cluster_data.iterrows():
                # 提取源点坐标 (从'起点坐标'字段)
                source_coords_str = row.get('起点坐标', '')
                if source_coords_str:
                    try:
                        # 解析 "(39.8894, 116.2726)" 格式
                        import re
                        match = re.search(r'\(([\d.]+),\s*([\d.]+)\)', str(source_coords_str))
                        if match:
                            lat = float(match.group(1))
                            lon = float(match.group(2))
                            active_co2_source_coords.add((lat, lon))
                    except:
                        pass

                # 提取聚类ID
                cluster_id, _, _, is_co2 = self.parse_cluster_info(row.get('聚类信息'))
                if cluster_id is not None and is_co2:
                    active_co2_clusters.add(cluster_id)

            print(f"提取到 {len(active_co2_source_coords)} 个活跃CO2源点坐标")
            print(f"活跃CO2源点坐标: {active_co2_source_coords}")
            print(f"提取到 {len(active_co2_clusters)} 个活跃CO2聚类")
            # ========== 新增部分结束 ==========

            if all_data.get('co2_clustering') is not None and all_data.get('co2_sources') is not None:
                co2_clustering = all_data['co2_clustering']
                co2_sources_df = all_data['co2_sources']

                # 过滤华北地区的CO2源点
                north_china_co2_sources = co2_sources_df[
                    (co2_sources_df['latitude'] >= 35.0) &
                    (co2_sources_df['latitude'] <= 45.0) &
                    (co2_sources_df['longitude'] >= 110.0) &
                    (co2_sources_df['longitude'] <= 120.0)
                ]

                print(f"华北地区CO2源点总数: {len(north_china_co2_sources)}")
                print(f"CO2聚类总数: {co2_clustering.get('total_clusters', 0)}")

                # 提取聚类信息（只保留活跃的聚类）
                co2_cluster_centers = {}
                # 保存所有聚类成员的坐标及其对应的聚类信息
                co2_cluster_members = []  # [(lat, lon, cluster_info), ...]

                for cluster in co2_clustering.get('clusters', []):
                    cluster_id = cluster['cluster_id']

                    # ========== 修改：只处理活跃的聚类 ==========
                    if cluster_id not in active_co2_clusters:
                        continue  # 跳过不活跃的聚类
                    # ========== 修改结束 ==========

                    # 使用 'geo_center' 字段,格式为 [lat, lon]
                    center_lat, center_lon = cluster['geo_center']
                    co2_cluster_centers[cluster_id] = (center_lat, center_lon)

                    # 保存聚类成员坐标和对应的聚类信息
                    # member_coords格式: [[lat1, lon1], [lat2, lon2], ...]
                    for member_coord in cluster.get('member_coords', []):
                        member_lat, member_lon = member_coord[0], member_coord[1]
                        co2_cluster_members.append({
                            'lat': member_lat,
                            'lon': member_lon,
                            'cluster_id': cluster_id,
                            'center_lat': center_lat,
                            'center_lon': center_lon
                        })

                print(f"收集到 {len(co2_cluster_centers)} 个活跃CO2聚类中心（过滤后）")
                print(f"收集到 {len(co2_cluster_members)} 个活跃聚类成员坐标（过滤后）")

                # 绘制CO2源点（只绘制实际运输的源点）
                co2_sources_in_clusters = set()
                co2_lines_drawn = 0

                print(f"\n开始绘制CO2源点和Layer1连线...")

                # 定义坐标匹配函数（允许小误差）
                def coords_match(lat1, lon1, lat2, lon2, tolerance=0.001):  # 增加容差到0.001度（约100米）
                    return abs(lat1 - lat2) < tolerance and abs(lon1 - lon2) < tolerance

                for _, source in north_china_co2_sources.iterrows():
                    source_lat = source['latitude']
                    source_lon = source['longitude']

                    # ========== 修改：用坐标匹配活跃的CO2源点 ==========
                    is_active = False
                    for active_lat, active_lon in active_co2_source_coords:
                        if coords_match(source_lat, source_lon, active_lat, active_lon):
                            is_active = True
                            break

                    if not is_active:
                        continue  # 跳过不活跃的源点
                    # ========== 修改结束 ==========

                    # 查找匹配的聚类成员
                    matched_cluster = None
                    for member in co2_cluster_members:
                        if coords_match(source_lat, source_lon, member['lat'], member['lon'], tolerance=0.001):
                            matched_cluster = member
                            break

                    # 只绘制在聚类中的源点
                    if matched_cluster:
                        # CO2源点用棕色下三角形标记（缩小尺寸）
                        main_ax.scatter(
                            source_lon, source_lat,
                            c='#8B4513',  # 棕色
                            s=40,  # 从80缩小到40
                            marker='v',  # 下三角形
                            edgecolors='black',
                            linewidth=0.8,  # 从1缩小到0.8
                            transform=self.data_crs,
                            zorder=20,
                            alpha=0.9
                        )

                        co2_sources_in_clusters.add((source_lat, source_lon))

                        # 绘制CO2源点到聚类中心的连线（Layer1，棕色虚线）
                        main_ax.plot(
                            [source_lon, matched_cluster['center_lon']],
                            [source_lat, matched_cluster['center_lat']],
                            color='#8B4513',
                            alpha=0.5,
                            linewidth=1.5,
                            linestyle='--',
                            zorder=19,
                            transform=self.data_crs
                        )
                        co2_lines_drawn += 1

                print(f"绘制了 {len(co2_sources_in_clusters)} 个活跃CO2源点（过滤后）")
                print(f"绘制了 {co2_lines_drawn} 条Layer1连线（源点->聚类中心）")

                # 绘制CO2聚类中心（已经过滤为活跃的聚类）
                north_china_co2_cluster_centers = {
                    cid: (clat, clon)
                    for cid, (clat, clon) in co2_cluster_centers.items()
                    if 35.0 <= clat <= 45.0 and 110.0 <= clon <= 120.0
                }

                if north_china_co2_cluster_centers:
                    print(f"正在绘制 {len(north_china_co2_cluster_centers)} 个活跃CO2聚类中心（过滤后）...")
                    for cluster_id, (center_lat, center_lon) in north_china_co2_cluster_centers.items():
                        # CO2聚类中心用方形标记（缩小尺寸）
                        main_ax.scatter(
                            center_lon, center_lat,
                            c='#8B4513',  # 棕色
                            s=60,  # 从100缩小到60
                            marker='s',  # 方形标记
                            edgecolors='black',
                            linewidth=1.0,  # 从1.5缩小到1.0
                            transform=self.data_crs,
                            zorder=30,
                            alpha=1.0
                        )

                # 用于图例统计
                co2_layer1_count = len(co2_sources_in_clusters)
                co2_layer2_count = 0  # 这里暂时设为0,因为还没有Layer2数据
            else:
                print("未找到CO2聚类数据")
                co2_layer1_count = 0
                co2_layer2_count = 0
                north_china_co2_sources = pd.DataFrame()
                north_china_co2_cluster_centers = {}
                co2_cluster_centers = {}  # 初始化CO2聚类中心字典
                co2_cluster_members = []  # 初始化聚类成员列表

            # 绘制CO2聚类路径（从transport_summary中读取,如果存在）
            if len(co2_cluster_data) > 0:
                print(f"\n找到 {len(co2_cluster_data)} 条CO2聚类路径")

                # 收集CO2聚类中心
                co2_cluster_centers_from_transport = {}
                for _, row in co2_cluster_data.iterrows():
                    cluster_id, center_lat, center_lon, is_co2_cluster = self.parse_cluster_info(row.get('聚类信息'))
                    if cluster_id is not None and is_co2_cluster:  # 只收集CO2聚类中心
                        co2_cluster_centers_from_transport[cluster_id] = (center_lat, center_lon)

                print(f"从transport_summary收集到 {len(co2_cluster_centers_from_transport)} 个CO2聚类中心")

                # 绘制CO2聚类路径（三层结构，使用不同颜色）
                co2_layer1_count = 0
                co2_layer2_count = 0

                for idx, row in co2_cluster_data.iterrows():
                    cluster_id, center_lat, center_lon, is_co2_cluster = self.parse_cluster_info(row.get('聚类信息'))

                    if cluster_id is not None and is_co2_cluster:  # 只处理CO2聚类
                        # CO2聚类使用不同的颜色（棕色系）
                        co2_color = '#8B4513'  # 棕色，区别于H2的紫色/灰色

                        # Layer1: CO2源 -> 聚类中心 (棕色虚线)
                        layer1_dist = row.get('Layer1距离(km)', 0)
                        print(f"  CO2聚类{cluster_id} 行{idx}: Layer1距离={layer1_dist}, Layer2距离={row.get('Layer2距离(km)', 0)}")

                        if layer1_dist > 0:
                            main_ax.plot(
                                [row['起点经度'], center_lon],
                                [row['起点纬度'], center_lat],
                                color=co2_color,
                                alpha=0.7,
                                linewidth=2,
                                linestyle='--',  # 虚线
                                zorder=20,
                                transform=self.data_crs
                            )
                            co2_layer1_count += 1

                        # Layer2: 聚类中心 -> 管道接入点 (棕色实线)
                        layer2_dist = row.get('Layer2距离(km)', 0)
                        if layer2_dist > 0 and '路径坐标' in row and row['路径坐标'] and row['路径坐标'] != '[]':
                            try:
                                import json
                                from math import radians, cos, sin, asin, sqrt

                                path_coords = json.loads(row['路径坐标'])

                                def haversine(lon1, lat1, lon2, lat2):
                                    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
                                    dlon = lon2 - lon1
                                    dlat = lat2 - lat1
                                    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
                                    c = 2 * asin(sqrt(a))
                                    r = 6371
                                    return c * r

                                # 找最接近聚类中心的点作为起点
                                min_dist_to_center = float('inf')
                                start_idx = 0
                                for i, coord in enumerate(path_coords):
                                    dist = haversine(center_lon, center_lat, coord[0], coord[1])
                                    if dist < min_dist_to_center:
                                        min_dist_to_center = dist
                                        start_idx = i

                                # 从起点开始累计距离找Layer2终点
                                cumulative_dist = 0
                                pipeline_access_point = None
                                for i in range(start_idx + 1, len(path_coords)):
                                    seg_dist = haversine(
                                        path_coords[i-1][0], path_coords[i-1][1],
                                        path_coords[i][0], path_coords[i][1]
                                    )
                                    cumulative_dist += seg_dist

                                    if abs(cumulative_dist - layer2_dist) < 1:  # 1km容差
                                        pipeline_access_point = path_coords[i]
                                        break

                                # 绘制Layer2：聚类中心 -> 管道接入点 (棕色实线)
                                if pipeline_access_point:
                                    main_ax.plot(
                                        [center_lon, pipeline_access_point[0]],
                                        [center_lat, pipeline_access_point[1]],
                                        color=co2_color,
                                        alpha=0.7,
                                        linewidth=2,
                                        linestyle='-',  # 实线
                                        zorder=20,
                                        transform=self.data_crs
                                    )
                                    co2_layer2_count += 1

                            except Exception as e:
                                print(f"    错误：解析CO2路径坐标失败 - {e}")


                print(f"绘制了 CO2 Layer1:{co2_layer1_count}条（聚类结果）, Layer2:{co2_layer2_count}条（聚类中心->管道）")

            # 绘制独立CO2点（噪声点）到管道的连线
            # 从transport_summary中提取独立CO2点（没有聚类信息的CO2运输）
            co2_standalone_data = region_transport[
                (region_transport['聚类信息'].isna()) &
                (region_transport['起点类型'].str.contains('co2|CO2', case=False, na=False))
            ] if len(region_transport) > 0 else pd.DataFrame()

            if len(co2_standalone_data) > 0:
                print(f"\n找到 {len(co2_standalone_data)} 条独立CO2点路径（噪声点）")

                # 收集独立CO2点
                co2_standalone_sources = set()
                for _, row in co2_standalone_data.iterrows():
                    co2_standalone_sources.add((row['起点'], row['起点纬度'], row['起点经度']))

                # 绘制独立CO2源点
                for source_name, source_lat, source_lon in co2_standalone_sources:
                    main_ax.scatter(
                        source_lon, source_lat,
                        c='#A0522D',  # 稍浅的棕色（与聚类成员区分）
                        s=35,  # 从70缩小到35
                        marker='v',
                        edgecolors='black',
                        linewidth=0.8,
                        transform=self.data_crs,
                        zorder=20,
                        alpha=0.8
                    )

                # 绘制独立CO2点到管道的连线
                for _, row in co2_standalone_data.iterrows():
                    main_ax.plot(
                        [row['起点经度'], row['终点经度']],
                        [row['起点纬度'], row['终点纬度']],
                        color='#8B4513',
                        alpha=0.4,
                        linewidth=1.5,
                        linestyle=':',  # 点线（与聚类路径区分）
                        zorder=18,
                        transform=self.data_crs
                    )

                print(f"绘制了 {len(co2_standalone_sources)} 个独立CO2源点（噪声点）")
                print(f"绘制了 {len(co2_standalone_data)} 条独立CO2点到管道的连线")

            # 更新图例
            if len(cluster_data) > 0 or len(standalone_data) > 0:
                legend_elements.append(plt.Line2D([0], [0], color='none', label='─── 氢气运输 ───'))

                if len(cluster_data) > 0:
                    legend_elements.append(
                        plt.scatter([], [], c='purple', s=80, marker='*',
                                  edgecolors='black', linewidth=1.5,
                                  label=f'H2聚类中心 ({len(cluster_centers)}个)')
                    )

                total_paths = len(cluster_data) * 2 + len(standalone_data)  # 聚类有2条线(Layer1+Layer2)
                if total_paths > 0:
                    legend_elements.append(
                        plt.Line2D([0], [0], color='gray', linewidth=2, linestyle=':',
                                  alpha=0.6, label=f'氢气运输路径 ({total_paths}条)')
                    )

            # 添加CO2聚类图例
            if len(co2_cluster_data) > 0 or (all_data.get('co2_clustering') is not None and len(north_china_co2_sources) > 0):
                legend_elements.append(plt.Line2D([0], [0], color='none', label='─── CO2运输 ───'))

                # CO2源点图例
                if len(north_china_co2_sources) > 0:
                    legend_elements.append(
                        plt.scatter([], [], c='#8B4513', s=80, marker='v',
                                  edgecolors='black', linewidth=1,
                                  label=f'CO2源点 ({len(north_china_co2_sources)}个)')
                    )

                # CO2聚类中心图例
                if len(north_china_co2_cluster_centers) > 0:
                    legend_elements.append(
                        plt.scatter([], [], c='#8B4513', s=100, marker='s',
                                  edgecolors='black', linewidth=1.5,
                                  label=f'CO2聚类中心 ({len(north_china_co2_cluster_centers)}个)')
                    )

                # CO2运输路径图例
                if co2_layer1_count > 0:
                    legend_elements.append(
                        plt.Line2D([0], [0], color='#8B4513', linewidth=2, linestyle='--',
                                  alpha=0.7, label=f'CO2→聚类中心 ({co2_layer1_count}条)')
                    )
                if co2_layer2_count > 0:
                    legend_elements.append(
                        plt.Line2D([0], [0], color='#8B4513', linewidth=2, linestyle='-',
                                  alpha=0.7, label=f'CO2 Layer2路径 ({co2_layer2_count}条)')
                    )

            # 更新图例
            if legend_elements:
                main_ax.legend(handles=legend_elements, loc='upper right',
                              fontsize=9, frameon=True, fancybox=True, shadow=True, framealpha=0.9)

        # 添加装饰
        self.add_decorations(main_ax, mini_ax)

        print(f"华北地区设施统计: {facility_stats}")
        print(f"连接统计: {connection_stats}")

        return fig, main_ax, mini_ax, facility_stats, connection_stats
        """创建华北地区能源设施可视化（太阳能电站、风电站、管段、LNG终端、机场）"""
        print("正在创建华北地区能源设施分布图...")
        
        # 创建基础地图
        fig, main_ax, mini_ax = self.create_base_map(figsize=(12, 10))
        
        legend_elements = []
        facility_stats = {
            'solar': 0,
            'wind': 0, 
            'pipeline': 0,
            'lng': 0,
            'airport': 0
        }
        
        # 1. 绘制太阳能电站
        if all_data.get('renewable_energy') is not None:
            renewable_data = self.filter_data_by_region(all_data['renewable_energy'])
            
            if renewable_data is not None and len(renewable_data) > 0:
                solar_facilities = renewable_data[renewable_data['发电站类型'].str.contains('光伏|太阳能|solar', case=False, na=False)]
                
                if len(solar_facilities) > 0:
                    print(f"正在绘制 {len(solar_facilities)} 个太阳能电站...")
                    for _, facility in solar_facilities.iterrows():
                        capacity = facility.get('装机容量(MW)', 50)
                        size = min(max(capacity / 2, 30), 150)
                        
                        main_ax.scatter(
                            facility['经度'], facility['纬度'],
                            c=self.facility_colors['solar'], s=size,
                            marker=self.facility_markers['solar'],
                            edgecolors='black', linewidth=0.8,
                            transform=self.data_crs, zorder=8, alpha=0.9,
                            label='太阳能电站' if facility_stats['solar'] == 0 else ""
                        )
                        facility_stats['solar'] += 1
                
                # 2. 绘制风电站
                wind_facilities = renewable_data[renewable_data['发电站类型'].str.contains('风电|风力|wind', case=False, na=False)]
                
                if len(wind_facilities) > 0:
                    print(f"正在绘制 {len(wind_facilities)} 个风电站...")
                    for _, facility in wind_facilities.iterrows():
                        capacity = facility.get('装机容量(MW)', 50)
                        size = min(max(capacity / 2, 30), 150)
                        
                        main_ax.scatter(
                            facility['经度'], facility['纬度'],
                            c=self.facility_colors['wind'], s=size,
                            marker=self.facility_markers['wind'],
                            edgecolors='black', linewidth=0.8,
                            transform=self.data_crs, zorder=8, alpha=0.9,
                            label='风电站' if facility_stats['wind'] == 0 else ""
                        )
                        facility_stats['wind'] += 1
        
        # 3. 绘制天然气管段（注释掉，改用管道网络线条显示）
        # if all_data.get('ng_pipelines') is not None:
        #     pipeline_data = self.filter_data_by_region(all_data['ng_pipelines'])
        #
        #     if pipeline_data is not None and len(pipeline_data) > 0:
        #         print(f"正在绘制 {len(pipeline_data)} 个管段...")
        #         for _, pipeline in pipeline_data.iterrows():
        #             main_ax.scatter(
        #                 pipeline['经度'], pipeline['纬度'],
        #                 c=self.facility_colors['pipeline'], s=60,
        #                 marker=self.facility_markers['pipeline'],
        #                 edgecolors='black', linewidth=0.8,
        #                 transform=self.data_crs, zorder=7, alpha=0.9,
        #                 label='天然气管段' if facility_stats['pipeline'] == 0 else ""
        #             )
        #             facility_stats['pipeline'] += 1
        
        # 4. 绘制LNG终端（已禁用）
        # if all_data.get('lng_terminals') is not None:
        #     lng_data = self.filter_data_by_region(all_data['lng_terminals'])
        #
        #     if lng_data is not None and len(lng_data) > 0:
        #         print(f"正在绘制 {len(lng_data)} 个LNG终端...")
        #         for _, terminal in lng_data.iterrows():
        #             transform_kwargs = self._get_transform_kwargs(main_ax)
        #             main_ax.scatter(
        #                 terminal['经度'], terminal['纬度'],
        #                 c=self.facility_colors['lng'], s=80,
        #                 marker=self.facility_markers['lng'],
        #                 edgecolors='black', linewidth=0.8,
        #                 zorder=9, alpha=0.9,
        #                 label='LNG终端' if facility_stats['lng'] == 0 else "",
        #                 **transform_kwargs
        #             )
        #             facility_stats['lng'] += 1
        
        # 5. 绘制机场（从运输数据中提取）
        if all_data.get('transport_summary') is not None:
            transport_data = all_data['transport_summary']
            
            # 过滤华北地区的运输数据
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
                            transform=self.data_crs, zorder=25, alpha=0.9,  # 最上层显示
                            label='机场' if facility_stats['airport'] == 0 else ""
                        )
                        facility_stats['airport'] += 1
        
        # 创建图例
        for facility_type, count in facility_stats.items():
            if count > 0:
                facility_name = {
                    'solar': '太阳能电站',
                    'wind': '风电站',
                    'pipeline': '天然气管段',
                    'lng': 'LNG终端',
                    'airport': '机场'
                }[facility_type]
                
                legend_elements.append(
                    plt.scatter([], [], 
                              c=self.facility_colors[facility_type], 
                              s=80, 
                              marker=self.facility_markers[facility_type],
                              edgecolors='black', linewidth=0.8,
                              label=f'{facility_name} ({count}个)')
                )
        
        # 添加图例
        if legend_elements:
            main_ax.legend(handles=legend_elements, loc='upper right', 
                          fontsize=10, framealpha=0.9)
        
        # 添加标题
        total_facilities = sum(facility_stats.values())
        plt.suptitle(
            f'华北地区能源基础设施分布图 (35°N-45°N, 110°E-120°E)\n'
            f'总设施数: {total_facilities}个', 
            fontsize=14, y=0.95, fontweight='bold'
        )
        
        # 添加统计信息
        stats_text = "设施统计:\n"
        facility_names = {
            'solar': '太阳能电站',
            'wind': '风电站',
            'lng': 'LNG终端',
            'airport': '机场'
        }
        
        for facility_type, count in facility_stats.items():
            if count > 0:
                stats_text += f"{facility_names[facility_type]}: {count}个\n"
        
        main_ax.text(0.02, 0.02, stats_text, transform=main_ax.transAxes, 
                    fontsize=9, bbox=dict(boxstyle="round,pad=0.3", 
                    facecolor="white", alpha=0.9), verticalalignment='bottom')
        
        # 添加装饰
        self.add_decorations(main_ax, mini_ax)
        
        print(f"华北地区设施统计: {facility_stats}")
        
        return fig, main_ax, mini_ax, facility_stats
    
    def create_transport_visualization(self, transport_data, max_routes=1000):
        """创建运输路径可视化"""
        if transport_data is None or len(transport_data) == 0:
            self.logger.error("没有有效的运输数据")
            return None
        
        print("正在创建天然气运输路径地图...")
        print(f"数据统计: {len(transport_data)} 条运输路径")
        
        # 限制显示的路径数量
        if len(transport_data) > max_routes:
            display_data = transport_data.head(max_routes)
            print(f"限制显示前 {max_routes} 条路径")
        else:
            display_data = transport_data.copy()
        
        # 创建基础地图
        fig, main_ax, mini_ax = self.create_base_map()
        
        return self._create_route_focused_visualization(fig, main_ax, mini_ax, display_data)
    
    def _create_route_focused_visualization(self, fig, main_ax, mini_ax, display_data):
        """创建专注于运输路径的可视化，只显示涉及的设施"""
        
        # 计算线条宽度（基于运输量）
        if '周运输量(kg)' in display_data.columns:
            line_widths = self.normalize_transport_volume(display_data['周运输量(kg)'])
        elif '日运输量(kg)' in display_data.columns:
            line_widths = self.normalize_transport_volume(display_data['日运输量(kg)'])
        elif '日运输量(m3)' in display_data.columns:
            line_widths = self.normalize_transport_volume(display_data['日运输量(m3)'])
        else:
            line_widths = np.ones(len(display_data)) * 1.5
        
        # 收集聚类中心信息
        cluster_centers = {}
        print(f"\n[调试] 检查聚类信息列...")
        print(f"[调试] display_data列名: {list(display_data.columns)}")

        if '聚类信息' in display_data.columns:
            print(f"[调试] 找到'聚类信息'列")
            print(f"[调试] 聚类信息列样本: {display_data['聚类信息'].head()}")

            for idx, row in display_data.iterrows():
                cluster_info_value = row.get('聚类信息')
                print(f"[调试] 行{idx} 聚类信息值: {cluster_info_value} (类型: {type(cluster_info_value)})")

                cluster_id, center_lat, center_lon, is_co2_cluster = self.parse_cluster_info(cluster_info_value)
                if cluster_id is not None and not is_co2_cluster:  # 只收集H2聚类中心
                    cluster_centers[cluster_id] = (center_lat, center_lon)
                    print(f"[调试] 解析到聚类{cluster_id}, 中心: ({center_lat}, {center_lon})")

            print(f"[调试] 共收集到 {len(cluster_centers)} 个聚类中心: {cluster_centers}")
        else:
            print(f"[调试] 未找到'聚类信息'列")

        # 绘制运输路径
        print("\n[调试] 正在绘制运输路径...")
        route_stats = {'truck': 0, 'pipeline': 0, 'ship': 0, 'rail': 0, 'other': 0, 'cluster': 0, 'noise': 0}
        real_route_count = 0

        for idx, row in display_data.iterrows():
            line_width = line_widths[idx] if hasattr(line_widths, '__getitem__') else line_widths

            # 检查是否为聚类路径
            cluster_id, center_lat, center_lon, is_co2_cluster = self.parse_cluster_info(row.get('聚类信息'))

            if cluster_id is not None and not is_co2_cluster:  # H2聚类路径
                # 绘制聚类路径（三层结构）
                route_stats['cluster'] += 1
                cluster_color = self.cluster_colors[cluster_id % len(self.cluster_colors)]

                print(f"[调试-聚类路径] 聚类{cluster_id}: {row['起点']} -> {row['终点']}")
                print(f"[调试-聚类路径]   起点: ({row['起点纬度']}, {row['起点经度']})")
                print(f"[调试-聚类路径]   中心: ({center_lat}, {center_lon})")
                print(f"[调试-聚类路径]   终点: ({row['终点纬度']}, {row['终点经度']})")

                # Layer1: 氢气点 -> 聚类中心 (虚线)
                layer1_dist = row.get('Layer1距离(km)', 0)
                print(f"[调试-聚类路径]   Layer1距离: {layer1_dist} km")

                if layer1_dist > 0:
                    main_ax.plot(
                        [row['起点经度'], center_lon],
                        [row['起点纬度'], center_lat],
                        color=cluster_color,
                        alpha=0.9,
                        linewidth=line_width * 2.5,
                        linestyle=self.cluster_line_styles['layer1'],
                        zorder=5
                    )
                    print(f"[调试-聚类路径]   [OK] 绘制Layer1虚线")

                # Layer2: 聚类中心 -> 管道接入点 (实线，推断位置)
                # 由于CSV中没有管道接入点坐标，我们用中心到终点的中点来近似
                layer2_dist = row.get('Layer2距离(km)', 0)
                print(f"[调试-聚类路径]   Layer2距离: {layer2_dist} km")

                if layer2_dist > 0:
                    # 推断管道接入点在中心和终点之间
                    pipeline_lon = (center_lon + row['终点经度']) / 2
                    pipeline_lat = (center_lat + row['终点纬度']) / 2

                    main_ax.plot(
                        [center_lon, pipeline_lon],
                        [center_lat, pipeline_lat],
                        color=cluster_color,
                        alpha=0.9,
                        linewidth=line_width * 2.5,
                        linestyle=self.cluster_line_styles['layer2'],
                        zorder=6
                    )
                    print(f"[调试-聚类路径]   [OK] 绘制Layer2实线: 中心 -> 管道点({pipeline_lat}, {pipeline_lon})")

                    # Layer3: 管道网络 -> 目的地 (实线)
                    layer3_dist = row.get('Layer3距离(km)', 0)
                    print(f"[调试-聚类路径]   Layer3距离: {layer3_dist} km")

                    if layer3_dist > 0:
                        main_ax.plot(
                            [pipeline_lon, row['终点经度']],
                            [pipeline_lat, row['终点纬度']],
                            color=cluster_color,
                            alpha=0.9,
                            linewidth=line_width * 2.5,
                            linestyle=self.cluster_line_styles['layer3'],
                            zorder=6
                        )
                        print(f"[调试-聚类路径]   [OK] 绘制Layer3实线: 管道点 -> 终点")
            else:
                # 非聚类路径（独立点或其他类型）
                if row.get('起点类型') == '氢气生产站':
                    route_stats['noise'] += 1

                # 确定运输方式和颜色
                transport_mode = row.get('运输方式', 'truck').lower()
                color = self.transport_type_colors.get(transport_mode, self.transport_type_colors.get('default', 'gray'))

                # 统计运输方式
                if transport_mode in route_stats:
                    route_stats[transport_mode] += 1
                else:
                    route_stats['other'] += 1

                # 尝试获取真实路径坐标
                real_coordinates = self.get_real_route_coordinates_from_data(row)

                if real_coordinates and len(real_coordinates) > 2:
                    # 使用真实路径坐标绘制
                    real_route_count += 1
                    lons = [coord[0] for coord in real_coordinates]
                    lats = [coord[1] for coord in real_coordinates]

                    # 绘制主地图路径
                    main_ax.plot(
                        lons, lats,
                        color=color,
                        alpha=0.8,
                        linewidth=line_width,
                        zorder=4
                    )

                    # 绘制小地图路径（南海区域）
                    if any(105 <= lon <= 122 and 2 <= lat <= 25 for lon, lat in zip(lons, lats)):
                        mini_ax.plot(
                            lons, lats,
                            color=color,
                            alpha=0.8,
                            linewidth=line_width * 0.7,
                            zorder=4
                        )
                else:
                    # 使用直线路径（后备方案）
                    # 独立点使用点线
                    linestyle = self.cluster_line_styles['noise'] if row.get('起点类型') == '氢气生产站' else '--'

                    main_ax.plot(
                        [row['起点经度'], row['终点经度']],
                        [row['起点纬度'], row['终点纬度']],
                        color=color,
                        alpha=0.5,
                        linewidth=line_width,
                        linestyle=linestyle,
                        zorder=3
                    )

                    # 绘制小地图路径（南海区域）
                    if (105 <= row['起点经度'] <= 122 and 2 <= row['起点纬度'] <= 25 and
                        105 <= row['终点经度'] <= 122 and 2 <= row['终点纬度'] <= 25):
                        mini_ax.plot(
                            [row['起点经度'], row['终点经度']],
                            [row['起点纬度'], row['终点纬度']],
                            color=color,
                            alpha=0.5,
                            linewidth=line_width * 0.7,
                            linestyle=linestyle,
                            zorder=3
                        )

        print(f"使用真实路径: {real_route_count}/{len(display_data)} 条")
        print(f"聚类路径: {route_stats['cluster']} 条, 独立点路径: {route_stats['noise']} 条")
        
        # 绘制聚类中心
        print(f"\n[调试] 检查聚类中心绘制...")
        print(f"[调试] cluster_centers字典: {cluster_centers}")
        print(f"[调试] cluster_centers是否为空: {len(cluster_centers) == 0}")

        if cluster_centers:
            print(f"[调试] 正在绘制 {len(cluster_centers)} 个聚类中心...")
            for cluster_id, (center_lat, center_lon) in cluster_centers.items():
                cluster_color = self.cluster_colors[cluster_id % len(self.cluster_colors)]

                print(f"[调试-聚类中心] 聚类{cluster_id}:")
                print(f"[调试-聚类中心]   位置: ({center_lat}, {center_lon})")
                print(f"[调试-聚类中心]   颜色: {cluster_color}")

                # 绘制聚类中心点（星形标记）
                main_ax.scatter(
                    center_lon, center_lat,
                    c=cluster_color, s=400, marker='*',
                    edgecolors='black', linewidth=3,
                    transform=self.data_crs, zorder=15, alpha=1.0,
                    label=f'聚类{cluster_id}中心' if cluster_id < 3 else None  # 只标注前3个避免图例过长
                )
                print(f"[调试-聚类中心]   [OK] 绘制星形标记")

                # 添加聚类ID标签
                main_ax.text(
                    center_lon, center_lat + 0.15,
                    f'C{cluster_id}',
                    fontsize=12, fontweight='bold',
                    ha='center', va='bottom',
                    bbox=dict(boxstyle='round,pad=0.4', facecolor=cluster_color, alpha=0.9, edgecolor='black', linewidth=1.5),
                    transform=self.data_crs, zorder=16
                )
                print(f"[调试-聚类中心]   [OK] 添加标签 C{cluster_id}")
        else:
            print(f"[调试] ⚠️ cluster_centers为空，不绘制聚类中心")

        # 绘制设施点（只显示涉及运输路径的设施）
        print("正在绘制设施点...")

        # 收集所有涉及运输的设施点
        transport_facilities = []

        # 起点设施
        origins = display_data[['起点', '起点纬度', '起点经度']].drop_duplicates()
        for _, facility in origins.iterrows():
            transport_facilities.append({
                'name': facility['起点'],
                'lat': facility['起点纬度'],
                'lon': facility['起点经度'],
                'type': 'origin'
            })

        # 终点设施
        destinations = display_data[['终点', '终点纬度', '终点经度']].drop_duplicates()
        for _, facility in destinations.iterrows():
            transport_facilities.append({
                'name': facility['终点'],
                'lat': facility['终点纬度'],
                'lon': facility['终点经度'],
                'type': 'destination'
            })
        
        # 去重设施点（基于坐标）
        unique_facilities = {}
        for facility in transport_facilities:
            coord_key = f"{facility['lat']:.6f},{facility['lon']:.6f}"
            if coord_key not in unique_facilities:
                unique_facilities[coord_key] = facility
            else:
                # 如果既是起点又是终点，标记为hub
                if unique_facilities[coord_key]['type'] != facility['type']:
                    unique_facilities[coord_key]['type'] = 'hub'
        
        # 绘制设施点
        facility_counts = {'origin': 0, 'destination': 0, 'hub': 0}
        
        for facility in unique_facilities.values():
            # 根据设施名称和类型确定显示样式
            facility_type = self.map_facility_type(facility['name'])
            
            if facility['type'] == 'hub':
                # 枢纽设施使用特殊样式
                marker = 'h'  # 六边形
                color = '#FF6B6B'  # 红色
                size = 80
                edge_color = 'darkred'
            elif facility['type'] == 'origin':
                # 起点设施
                marker = self.facility_markers.get(facility_type, 'o')
                color = self.facility_colors.get(facility_type, self.facility_colors['default'])
                size = 60
                edge_color = 'black'
            else:  # destination
                # 终点设施
                marker = self.facility_markers.get(facility_type, 's')
                color = self.facility_colors.get(facility_type, self.facility_colors['default'])
                size = 50
                edge_color = 'white'
            
            facility_counts[facility['type']] += 1
            
            # 绘制主地图设施点
            main_ax.scatter(
                facility['lon'], facility['lat'], 
                c=color, s=size, marker=marker, 
                edgecolors=edge_color, linewidth=0.8,
                transform=self.data_crs, zorder=10, alpha=0.9
            )
            
            # 绘制小地图设施点（南海区域）
            if 105 <= facility['lon'] <= 122 and 2 <= facility['lat'] <= 25:
                mini_ax.scatter(
                    facility['lon'], facility['lat'], 
                    c=color, s=size*0.6, marker=marker, 
                    edgecolors=edge_color, linewidth=0.5,
                    transform=self.data_crs, zorder=10, alpha=0.9
                )
        
        print(f"设施统计: 起点{facility_counts['origin']}个, 终点{facility_counts['destination']}个, 枢纽{facility_counts['hub']}个")
        
        # 创建图例
        legend_elements = []

        # 聚类路径图例
        if route_stats.get('cluster', 0) > 0:
            legend_elements.append(
                plt.Line2D([0], [0], color='purple', linewidth=2, linestyle='--',
                          label=f'Layer1-氢气点→中心 ({route_stats["cluster"]}条)')
            )
            legend_elements.append(
                plt.Line2D([0], [0], color='purple', linewidth=3, linestyle='-',
                          label=f'Layer2-中心→管道')
            )
            legend_elements.append(
                plt.Line2D([0], [0], color='purple', linewidth=3, linestyle='-',
                          label=f'Layer3-管道→目的地')
            )

        if route_stats.get('noise', 0) > 0:
            legend_elements.append(
                plt.Line2D([0], [0], color='gray', linewidth=2, linestyle=':',
                          label=f'独立点直连 ({route_stats["noise"]}条)')
            )

        # 聚类中心图例
        if cluster_centers:
            legend_elements.append(
                plt.scatter([], [], c='purple', s=200, marker='*',
                           edgecolors='black', linewidth=2,
                           label=f'聚类中心 ({len(cluster_centers)}个)')
            )

        # 运输方式图例
        for mode, color in self.transport_type_colors.items():
            if mode != 'default' and route_stats.get(mode, 0) > 0:
                mode_name = {
                    'truck': '卡车运输',
                    'pipeline': '管道运输',
                    'ship': '船舶运输',
                    'rail': '铁路运输'
                }.get(mode, mode)
                legend_elements.append(
                    plt.Line2D([0], [0], color=color, linewidth=3,
                              label=f'{mode_name} ({route_stats[mode]}条)')
                )

        # 路径类型图例
        if real_route_count > 0:
            legend_elements.append(
                plt.Line2D([0], [0], color='gray', linewidth=2, alpha=0.8,
                          label=f'真实路径 ({real_route_count}条)')
            )

        estimated_routes = len(display_data) - real_route_count - route_stats.get('cluster', 0) - route_stats.get('noise', 0)
        if estimated_routes > 0:
            legend_elements.append(
                plt.Line2D([0], [0], color='gray', linewidth=2, alpha=0.5, linestyle='--',
                          label=f'估算路径 ({estimated_routes}条)')
            )
        
        # 设施类型图例
        if facility_counts['hub'] > 0:
            legend_elements.append(
                plt.scatter([], [], c='#FF6B6B', s=80, marker='h', 
                           edgecolors='darkred', linewidth=0.8,
                           label=f'运输枢纽 ({facility_counts["hub"]}个)')
            )
        
        if facility_counts['origin'] > 0:
            legend_elements.append(
                plt.scatter([], [], c=self.facility_colors['default'], s=60, marker='o', 
                           edgecolors='black', linewidth=0.5,
                           label=f'起点设施 ({facility_counts["origin"]}个)')
            )
            
        if facility_counts['destination'] > 0:
            legend_elements.append(
                plt.scatter([], [], c=self.facility_colors['airport'], s=50, marker='s', 
                           edgecolors='white', linewidth=0.8,
                           label=f'终点设施 ({facility_counts["destination"]}个)')
            )
        
        # 添加图例
        main_ax.legend(handles=legend_elements, loc='lower left', 
                      fontsize=9, framealpha=0.9)
        
        # 添加标题
        total_volume = display_data['周运输量(kg)'].sum() if '周运输量(kg)' in display_data.columns else 0
        plt.suptitle(
            f'天然气供应链运输路径网络图 (真实路径显示)\n'
            f'运输路径: {len(display_data)}条 | 真实路径: {real_route_count}条 | 总运输量: {total_volume/1e6:.1f}万吨/周', 
            fontsize=14, y=0.95
        )
        
        # 添加统计信息
        total_facilities = sum(facility_counts.values())
        stats_text = f"""路径统计:
总路径: {len(display_data)}条
真实路径: {real_route_count}条
估算路径: {len(display_data) - real_route_count}条
运输设施: {total_facilities}个
总运输量: {total_volume/1e6:.1f}万吨/周"""
        
        main_ax.text(0.02, 0.02, stats_text, transform=main_ax.transAxes, 
                    fontsize=8, bbox=dict(boxstyle="round,pad=0.3", 
                    facecolor="white", alpha=0.9))
        
        # 添加装饰
        self.add_decorations(main_ax, mini_ax)
        
        return fig, main_ax, mini_ax, display_data
    
    def create_pipeline_network_topology_visualization(self):
        """创建管道网络拓扑可视化，显示三种管道类型的连接"""
        print("=== 创建管道网络拓扑可视化 ===")

        # 定义管道类型和颜色
        pipeline_types = {
            'crude': {
                'name': '原油管道',
                'color': '#8B4513',  # 棕色
                'alpha': 0.8,
                'linewidth': 2.0,
                'file': 'crude_pipelines.geojson'
            },
            'refined': {
                'name': '成品油管道',
                'color': '#FF6B35',  # 橙红色
                'alpha': 0.8,
                'linewidth': 2.0,
                'file': 'refined_product_pipelines.geojson'
            },
            'natural_gas': {
                'name': '天然气管道',
                'color': '#4169E1',  # 皇家蓝
                'alpha': 0.8,
                'linewidth': 1.5,
                'file': 'natural_gas_pipelines.geojson'
            }
        }

        # 创建简单地图（不使用frykit以避免依赖问题）
        fig, main_ax = plt.subplots(1, 1, figsize=(16, 12))

        # 设置中国区域的地理范围
        main_ax.set_xlim(73, 135)  # 中国经度范围
        main_ax.set_ylim(18, 54)   # 中国纬度范围
        main_ax.set_xlabel('经度 (°E)', fontsize=12)
        main_ax.set_ylabel('纬度 (°N)', fontsize=12)
        main_ax.grid(True, alpha=0.3)
        main_ax.set_aspect('equal', adjustable='box')

        # GIS数据路径 (使用绝对路径)
        current_dir = Path(__file__).parent
        gis_data_path = current_dir.parent.parent.parent / "gis_energy_mapping" / "gis_data_scraper" / "scraped_gis_data"

        total_segments = 0
        legend_elements = []
        pipeline_stats = {}
        node_stats = {}

        # 绘制每种管道类型
        for pipeline_type, config in pipeline_types.items():
            file_path = gis_data_path / config['file']

            if not file_path.exists():
                print(f"警告: {config['name']}数据文件不存在: {file_path}")
                pipeline_stats[pipeline_type] = 0
                node_stats[pipeline_type] = 0
                continue

            try:
                # 加载GeoJSON数据
                import json
                with open(file_path, 'r', encoding='utf-8') as f:
                    geojson_data = json.load(f)

                features = geojson_data.get('features', [])
                segments_count = 0

                print(f"绘制{config['name']}: {len(features)}个管道段")

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

                    # 绘制管道段 (不使用transform以避免投影问题)
                    main_ax.plot(
                        lons, lats,
                        color=config['color'],
                        alpha=config['alpha'],
                        linewidth=config['linewidth'],
                        zorder=3
                    )

                    segments_count += 1

                total_segments += segments_count

                # 添加图例元素
                legend_elements.append(
                    plt.Line2D([0], [0],
                              color=config['color'],
                              linewidth=config['linewidth']*2,
                              alpha=config['alpha'],
                              label=f"{config['name']} ({segments_count}段)")
                )

                # 更新统计信息
                pipeline_stats[pipeline_type] = segments_count
                total_segments += segments_count

                print(f"  成功绘制 {segments_count} 个{config['name']}段")

            except Exception as e:
                print(f"错误: 无法加载{config['name']}数据: {e}")
                pipeline_stats[pipeline_type] = 0
                node_stats[pipeline_type] = 0
                continue

        # 跳过网络节点可视化（避免GeoAxes问题）
        print("\n跳过管道网络节点绘制（简化模式）")
        # returned_node_stats = self._add_pipeline_network_nodes(main_ax, gis_data_path, pipeline_types)
        # if returned_node_stats:
        #     node_stats.update(returned_node_stats)

        # 设置图例
        if legend_elements:
            main_ax.legend(
                handles=legend_elements,
                loc='upper right',
                fontsize=10,
                frameon=True,
                fancybox=True,
                shadow=True,
                framealpha=0.9
            )

        # 设置标题
        main_ax.set_title(
            f'中国管道网络拓扑图\n总计 {total_segments} 个管道段',
            fontsize=16,
            fontweight='bold',
            pad=20
        )

        plt.tight_layout()

        print(f"\n管道网络拓扑可视化完成")

        return fig, pipeline_stats, node_stats

    def _add_pipeline_networks_to_existing_map(self, ax, hydrogen_transport_data=None):
        """在现有地图上添加与氢能运输相关的管道网络连接（兼容简化模式）"""

        # 如果没有氢能运输数据，不绘制任何管道
        if hydrogen_transport_data is None or len(hydrogen_transport_data) == 0:
            print("没有氢能运输数据，跳过管道网络绘制")
            return {}

        # 管道类型配置
        pipeline_types = {
            'crude': {'name': '原油管道', 'color': '#8B4513', 'file': 'crude_pipelines.geojson'},
            'refined': {'name': '成品油管道', 'color': '#FF6B35', 'file': 'refined_product_pipelines.geojson'},
            'natural_gas': {'name': '天然气管道', 'color': '#4169E1', 'file': 'natural_gas_pipelines.geojson'}
        }

        # GIS数据路径
        current_dir = Path(__file__).parent
        # 路径: src/visualization/ -> src/ -> green_hydrogen_supply_chain_optimization/ -> supply_chain_optimization/ -> products/
        gis_data_path = current_dir.parent.parent.parent.parent / "gis_energy_mapping" / "gis_data_scraper" / "scraped_gis_data"

        pipeline_stats = {}

        # 华北地区范围
        north_china_bounds = {'lat_min': 35.0, 'lat_max': 45.0, 'lon_min': 110.0, 'lon_max': 120.0}

        # 提取氢能运输路径（只考虑管道运输方式）
        h2_pipeline_routes = []
        for _, transport in hydrogen_transport_data.iterrows():
            if transport.get('运输方式') == 'pipeline' and transport.get('运输类型') == 'H2':
                route = {
                    'start_lon': transport['起点经度'],
                    'start_lat': transport['起点纬度'],
                    'end_lon': transport['终点经度'],
                    'end_lat': transport['终点纬度'],
                    'start_name': transport['起点'],
                    'end_name': transport['终点']
                }
                h2_pipeline_routes.append(route)

        print(f"找到 {len(h2_pipeline_routes)} 条氢能管道运输路径")

        def is_pipeline_relevant_to_h2_transport(coordinates, h2_routes, tolerance_km=50):
            """判断管道段是否与氢能运输路径相关"""
            if not h2_routes:
                return False

            import math

            def distance_km(lat1, lon1, lat2, lon2):
                """计算两点间距离（公里）"""
                R = 6371  # 地球半径
                lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
                dlat = lat2 - lat1
                dlon = lon2 - lon1
                a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
                return 2 * R * math.asin(math.sqrt(a))

            def point_to_line_distance(px, py, x1, y1, x2, y2):
                """计算点到直线的距离（简化版本）"""
                return distance_km(py, px, (y1+y2)/2, (x1+x2)/2)

            # 检查管道段的每个点是否接近任何氢能运输路径
            for coord in coordinates:
                lon, lat = coord[0], coord[1]
                for route in h2_routes:
                    # 检查点是否接近氢能运输路径的起点或终点
                    dist_to_start = distance_km(lat, lon, route['start_lat'], route['start_lon'])
                    dist_to_end = distance_km(lat, lon, route['end_lat'], route['end_lon'])

                    # 或检查点是否在起点和终点之间的路径上
                    dist_to_route = point_to_line_distance(lon, lat,
                                                         route['start_lon'], route['start_lat'],
                                                         route['end_lon'], route['end_lat'])

                    if min(dist_to_start, dist_to_end, dist_to_route) <= tolerance_km:
                        return True
            return False

        # 绘制每种管道类型
        for pipeline_type, config in pipeline_types.items():
            file_path = gis_data_path / config['file']

            if not file_path.exists():
                print(f"警告: {config['name']}数据文件不存在: {file_path}")
                pipeline_stats[pipeline_type] = 0
                continue

            try:
                # 加载GeoJSON数据
                import json
                with open(file_path, 'r', encoding='utf-8') as f:
                    geojson_data = json.load(f)

                features = geojson_data.get('features', [])
                segments_count = 0

                print(f"绘制{config['name']}: {len(features)}个管道段")

                for feature in features:
                    if not feature.get('geometry') or feature['geometry'].get('type') != 'LineString':
                        continue

                    coordinates = feature['geometry']['coordinates']
                    if not coordinates or len(coordinates) < 2:
                        continue

                    # 检查管道段是否在华北地区范围内
                    in_region = False
                    for coord in coordinates:
                        lon, lat = coord[0], coord[1]
                        if (north_china_bounds['lat_min'] <= lat <= north_china_bounds['lat_max'] and
                            north_china_bounds['lon_min'] <= lon <= north_china_bounds['lon_max']):
                            in_region = True
                            break

                    if not in_region:
                        continue

                    # 检查管道段是否与氢能运输路径相关
                    if not is_pipeline_relevant_to_h2_transport(coordinates, h2_pipeline_routes):
                        continue

                    # 提取经纬度
                    lons = [coord[0] for coord in coordinates]
                    lats = [coord[1] for coord in coordinates]

                    # 尝试不同的绘制方式以确保可见性
                    try:
                        # 首先尝试使用transform（适用于GeoAxes）
                        if hasattr(ax, 'projection'):
                            ax.plot(lons, lats, color=config['color'], alpha=1.0, linewidth=4.0,
                                   zorder=15, transform=self.data_crs)
                        else:
                            # 简化模式：直接绘制
                            ax.plot(lons, lats, color=config['color'], alpha=1.0, linewidth=4.0, zorder=15)
                    except:
                        # 后备方案：强制直接绘制
                        ax.plot(lons, lats, color=config['color'], alpha=1.0, linewidth=4.0, zorder=15)
                    segments_count += 1

                    # 显示前3个段的调试信息
                    if segments_count <= 3:
                        print(f"  {config['name']}段{segments_count}: {len(lons)}个点, 起点({lons[0]:.2f}, {lats[0]:.2f})")

                pipeline_stats[pipeline_type] = segments_count
                print(f"  成功绘制 {segments_count} 个{config['name']}段")

            except Exception as e:
                print(f"错误: 无法加载{config['name']}数据: {e}")
                pipeline_stats[pipeline_type] = 0
                import traceback
                traceback.print_exc()

        return pipeline_stats

    def _add_simple_facility_to_pipeline_connections(self, ax, all_data):
        """添加设施到最近管道的简单直线连接（排除聚类电站）"""

        # 华北地区范围
        north_china_bounds = {
            'lat_min': 35.0, 'lat_max': 45.0,
            'lon_min': 110.0, 'lon_max': 120.0
        }

        # 获取聚类电站名称（需要排除）
        clustered_stations = set()
        if all_data.get('transport_summary') is not None:
            transport_data = all_data['transport_summary']
            region_transport = transport_data[
                (transport_data['起点纬度'] >= north_china_bounds['lat_min']) &
                (transport_data['起点纬度'] <= north_china_bounds['lat_max']) &
                (transport_data['起点经度'] >= north_china_bounds['lon_min']) &
                (transport_data['起点经度'] <= north_china_bounds['lon_max'])
            ]
            cluster_data = region_transport[region_transport['聚类信息'].notna()]
            for _, row in cluster_data.iterrows():
                clustered_stations.add(row['起点'])

        # 收集所有设施点（排除聚类电站）
        facilities = []

        # 收集太阳能电站（非聚类）
        if all_data.get('renewable_energy') is not None:
            renewable_data = self.filter_data_by_region(all_data['renewable_energy'])
            if renewable_data is not None and len(renewable_data) > 0:
                solar_facilities = renewable_data[renewable_data['发电站类型'].str.contains('光伏|太阳能|solar', case=False, na=False)]
                for _, facility in solar_facilities.iterrows():
                    facility_name = facility.get('位置ID', '')
                    # 排除聚类电站
                    if facility_name not in clustered_stations:
                        facilities.append({
                            'lon': facility['经度'],
                            'lat': facility['纬度'],
                            'type': 'solar',
                            'name': facility.get('电站名称', '太阳能电站')
                        })

                # 收集风电站（非聚类）
                wind_facilities = renewable_data[renewable_data['发电站类型'].str.contains('风电|风力|wind', case=False, na=False)]
                for _, facility in wind_facilities.iterrows():
                    facility_name = facility.get('位置ID', '')
                    # 排除聚类电站
                    if facility_name not in clustered_stations:
                        facilities.append({
                            'lon': facility['经度'],
                            'lat': facility['纬度'],
                            'type': 'wind',
                            'name': facility.get('电站名称', '风电站')
                        })

        # 收集LNG终端
        if all_data.get('lng_terminals') is not None:
            lng_data = self.filter_data_by_region(all_data['lng_terminals'])
            if lng_data is not None and len(lng_data) > 0:
                for _, terminal in lng_data.iterrows():
                    facilities.append({
                        'lon': terminal['经度'],
                        'lat': terminal['纬度'],
                        'type': 'lng',
                        'name': terminal.get('终端名称', 'LNG终端')
                    })

        # 收集管道节点（作为连接目标）
        pipeline_points = []
        current_dir = Path(__file__).parent
        # 路径: src/visualization/ -> src/ -> green_hydrogen_supply_chain_optimization/ -> supply_chain_optimization/ -> products/
        gis_data_path = current_dir.parent.parent.parent.parent / "gis_energy_mapping" / "gis_data_scraper" / "scraped_gis_data"

        # 从天然气管道文件提取管道点
        ng_pipeline_file = gis_data_path / "natural_gas_pipelines.geojson"
        if ng_pipeline_file.exists():
            try:
                import json
                with open(ng_pipeline_file, 'r', encoding='utf-8') as f:
                    geojson_data = json.load(f)

                for feature in geojson_data.get('features', []):
                    if feature.get('geometry', {}).get('type') == 'LineString':
                        coordinates = feature['geometry']['coordinates']
                        for coord in coordinates:
                            lon, lat = coord[0], coord[1]
                            if (north_china_bounds['lat_min'] <= lat <= north_china_bounds['lat_max'] and
                                north_china_bounds['lon_min'] <= lon <= north_china_bounds['lon_max']):
                                pipeline_points.append((lon, lat))

                # 去重管道点（基于距离）
                unique_pipeline_points = []
                for point in pipeline_points:
                    is_duplicate = False
                    for existing in unique_pipeline_points:
                        distance = ((point[0] - existing[0])**2 + (point[1] - existing[1])**2)**0.5
                        if distance < 0.1:  # 0.1度阈值
                            is_duplicate = True
                            break
                    if not is_duplicate:
                        unique_pipeline_points.append(point)

                pipeline_points = unique_pipeline_points[:50]  # 限制数量避免过多连接线

            except Exception as e:
                print(f"警告: 无法加载管道点数据: {e}")

        # 绘制设施到最近管道的连接线
        connection_count = 0
        if facilities and pipeline_points:
            for facility in facilities:
                # 找到最近的管道点
                min_distance = float('inf')
                nearest_pipeline = None

                for pipeline_point in pipeline_points:
                    distance = ((facility['lon'] - pipeline_point[0])**2 +
                              (facility['lat'] - pipeline_point[1])**2)**0.5
                    if distance < min_distance:
                        min_distance = distance
                        nearest_pipeline = pipeline_point

                # 绘制连接线（如果距离合理）
                if nearest_pipeline and min_distance < 2.0:  # 2度阈值
                    # 完整模式：始终使用transform
                    ax.plot(
                        [facility['lon'], nearest_pipeline[0]],
                        [facility['lat'], nearest_pipeline[1]],
                        color='gray', alpha=0.6, linewidth=1.0,
                        linestyle='-', transform=self.data_crs, zorder=4  # 连接线在管道下方
                    )
                    connection_count += 1

        print(f"  成功绘制 {connection_count} 条设施到管道的连接线")
        return connection_count

    def _add_pipeline_network_nodes(self, ax, gis_data_path, pipeline_types):
        """添加管道网络节点的可视化"""
        try:
            # 初始化氢气管道距离计算器以获取网络拓扑
            from hydrogen_pipeline_distance_calculator import HydrogenPipelineDistanceCalculator

            calculator = HydrogenPipelineDistanceCalculator(str(gis_data_path))

            # 构建网络图
            calculator._build_pipeline_networks()

            node_colors = {
                'crude': '#654321',      # 深棕色
                'refined': '#CC5500',    # 深橙色
                'natural_gas': '#000080' # 深蓝色
            }

            total_nodes = 0

            # 绘制每种管道类型的网络节点
            for pipeline_type, graph in calculator.pipeline_networks.items():
                if graph is None or graph.number_of_nodes() == 0:
                    continue

                nodes = list(graph.nodes())
                node_coords = []

                # 解析节点坐标
                for node in nodes:
                    try:
                        lat_str, lon_str = node.split(',')
                        lat, lon = float(lat_str), float(lon_str)
                        node_coords.append((lon, lat))
                    except (ValueError, AttributeError):
                        continue

                if node_coords:
                    lons, lats = zip(*node_coords)

                    # 绘制节点 (不使用transform以避免投影问题)
                    ax.scatter(
                        lons, lats,
                        c=node_colors.get(pipeline_type, 'gray'),
                        s=8,  # 小尺寸节点
                        alpha=0.6,
                        zorder=4,
                        edgecolors='white',
                        linewidths=0.5
                    )

                    total_nodes += len(node_coords)
                    print(f"  {pipeline_type}网络: {len(node_coords)}个节点")

            print(f"总计绘制 {total_nodes} 个网络节点")

            # 返回节点统计信息
            node_stats = {}
            for pipeline_type, graph in calculator.pipeline_networks.items():
                if graph is not None:
                    node_stats[pipeline_type] = graph.number_of_nodes()
                else:
                    node_stats[pipeline_type] = 0
            return node_stats

        except Exception as e:
            print(f"警告: 无法绘制网络节点: {e}")
            return {'crude': 0, 'refined': 0, 'natural_gas': 0}

    def create_comprehensive_visualization(self, all_data, max_routes=2000):
        """创建包含所有基础设施和运输线路的综合可视化"""
        print("正在创建综合能源基础设施地图...")
        print(f"最大显示线路数: {max_routes}")
        
        # 输出数据概览
        print("\n=== 数据概览 ===")
        data_overview = {}
        for key, data in all_data.items():
            if data is not None:
                data_len = len(data) if hasattr(data, '__len__') else 1
                data_overview[key] = data_len
                print(f"{key}: {data_len} 条记录")
        
        if not data_overview:
            print("警告: 没有可用的数据进行可视化！")
            return None, None, None, {}
        
        # 创建基础地图
        fig, main_ax, mini_ax = self.create_base_map(figsize=(16, 12))
        
        legend_elements = []
        connection_stats = {}
        stats_info = {"设施统计": {}, "运输统计": {}}
        
        # 1. 绘制可再生能源设施（氢能生产点）
        if all_data.get('renewable_energy') is not None:
            renewable_data = all_data['renewable_energy']
            print(f"正在绘制 {len(renewable_data)} 个可再生能源设施...")
            
            for _, facility in renewable_data.iterrows():
                facility_type = 'wind' if '风电' in str(facility['发电站类型']) else 'solar'
                color = self.facility_colors.get(facility_type, self.facility_colors['renewable'])
                marker = '^' if facility_type == 'wind' else 'v'
                
                # 根据装机容量调整点大小
                capacity = facility.get('装机容量(MW)', 50)
                size = min(max(capacity / 5, 20), 120)
                
                main_ax.scatter(
                    facility['经度'], facility['纬度'], 
                    c=color, s=size, marker=marker, 
                    edgecolors='black', linewidth=0.5,
                    transform=self.data_crs, zorder=8, alpha=0.8
                )
                
                # 小地图
                if 105 <= facility['经度'] <= 122 and 2 <= facility['纬度'] <= 25:
                    mini_ax.scatter(
                        facility['经度'], facility['纬度'], 
                        c=color, s=size*0.5, marker=marker, 
                        edgecolors='black', linewidth=0.3,
                        transform=self.data_crs, zorder=8, alpha=0.8
                    )
            
            wind_count = len(renewable_data[renewable_data['发电站类型'].str.contains('风电', na=False)])
            solar_count = len(renewable_data) - wind_count
            stats_info["设施统计"]["风电场"] = wind_count
            stats_info["设施统计"]["光伏电站"] = solar_count
            
            if wind_count > 0:
                legend_elements.append(
                    plt.scatter([], [], c=self.facility_colors['wind'], s=60, marker='^', 
                               edgecolors='black', linewidth=0.5,
                               label=f'风电场 ({wind_count}个)')
                )
            if solar_count > 0:
                legend_elements.append(
                    plt.scatter([], [], c=self.facility_colors['solar'], s=60, marker='v', 
                               edgecolors='black', linewidth=0.5,
                               label=f'光伏电站 ({solar_count}个)')
                )
        
        # 2. 绘制LNG终端
        if all_data.get('lng_terminals') is not None:
            lng_data = all_data['lng_terminals']
            print(f"正在绘制 {len(lng_data)} 个LNG终端...")
            
            for _, terminal in lng_data.iterrows():
                main_ax.scatter(
                    terminal['经度'], terminal['纬度'], 
                    c=self.facility_colors['lng'], s=80, marker='s', 
                    edgecolors='black', linewidth=0.8,
                    transform=self.data_crs, zorder=9, alpha=0.9
                )
                
                # 小地图
                if 105 <= terminal['经度'] <= 122 and 2 <= terminal['纬度'] <= 25:
                    mini_ax.scatter(
                        terminal['经度'], terminal['纬度'], 
                        c=self.facility_colors['lng'], s=40, marker='s', 
                        edgecolors='black', linewidth=0.5,
                        transform=self.data_crs, zorder=9, alpha=0.9
                    )
            
            stats_info["设施统计"]["LNG终端"] = len(lng_data)
            legend_elements.append(
                plt.scatter([], [], c=self.facility_colors['lng'], s=80, marker='s', 
                           edgecolors='black', linewidth=0.8,
                           label=f'LNG终端 ({len(lng_data)}个)')
            )
        
        # 3. 绘制天然气管道设施
        if all_data.get('ng_pipelines') is not None:
            pipeline_data = all_data['ng_pipelines']
            print(f"正在绘制 {len(pipeline_data)} 个天然气管道节点...")
            
            for _, pipeline in pipeline_data.iterrows():
                main_ax.scatter(
                    pipeline['经度'], pipeline['纬度'], 
                    c=self.facility_colors['pipeline'], s=50, marker='D', 
                    edgecolors='black', linewidth=0.5,
                    transform=self.data_crs, zorder=7, alpha=0.8
                )
            
            stats_info["设施统计"]["天然气管道节点"] = len(pipeline_data)
            legend_elements.append(
                plt.scatter([], [], c=self.facility_colors['pipeline'], s=50, marker='D', 
                           edgecolors='black', linewidth=0.5,
                           label=f'天然气管道 ({len(pipeline_data)}个)')
            )
        
        # 4. [已禁用] 绘制氢能运输线路（罐车）- 避免与transport_summary重复
        # 注意：氢气运输数据已在transport_summary中统一绘制，此处跳过独立数据源
        if False and all_data.get('hydrogen_transport') is not None:
            h2_transport = all_data['hydrogen_transport']  # 显示全部氢气罐车运输
            print(f"正在绘制 {len(h2_transport)} 条氢能罐车运输线路...")
            
            for _, route in h2_transport.iterrows():
                volume = route.get('氢气运输量(kg)', 100)
                line_width = min(max(volume / 200, 0.5), 3.0)
                
                main_ax.plot(
                    [route['起点经度'], route['终点经度']], 
                    [route['起点纬度'], route['终点纬度']], 
                    color=self.transport_type_colors['H2'], 
                    alpha=0.6, linewidth=line_width,
                    transform=self.data_crs, zorder=4
                )
            
            stats_info["运输统计"]["氢能罐车运输"] = len(h2_transport)
            legend_elements.append(
                plt.Line2D([0], [0], color=self.transport_type_colors['H2'], linewidth=3, 
                          label=f'氢能罐车运输 ({len(h2_transport)}条)')
            )

        # 4.1. [已禁用] 绘制氢能管道运输线路 - 避免与transport_summary重复
        if False and all_data.get('hydrogen_pipeline_transport') is not None:
            h2_pipeline_transport = all_data['hydrogen_pipeline_transport']  # 显示全部氢能管道运输
            print(f"[已跳过] {len(h2_pipeline_transport) if h2_pipeline_transport is not None else 0} 条氢能管道运输线路（避免重复）")
        else:
            print("注意: hydrogen_pipeline_transport 数据未找到或为空")
        
        # 5. [已禁用] 绘制天然气运输线路 - 避免与transport_summary重复  
        if False and all_data.get('ng_transport') is not None:
            ng_transport = all_data['ng_transport']  # 显示全部天然气运输
            print(f"正在绘制 {len(ng_transport)} 条天然气运输线路...")
            
            for _, route in ng_transport.iterrows():
                volume = route.get('天然气运输量(m3)', 1000)
                line_width = min(max(volume / 5000, 0.5), 3.0)
                
                main_ax.plot(
                    [route['起点经度'], route['终点经度']], 
                    [route['起点纬度'], route['终点纬度']], 
                    color=self.transport_type_colors['NG'], 
                    alpha=0.6, linewidth=line_width,
                    transform=self.data_crs, zorder=5
                )
            
            stats_info["运输统计"]["天然气运输"] = len(ng_transport)
            legend_elements.append(
                plt.Line2D([0], [0], color=self.transport_type_colors['NG'], linewidth=3, 
                          label=f'天然气运输 ({len(ng_transport)}条)')
            )
        
        # 6. 绘制运输线路（按货物类型区分）
        if all_data.get('transport_summary') is not None:
            transport_data = all_data['transport_summary']  # 显示全部运输路径
            print(f"正在绘制 {len(transport_data)} 条运输线路（全部数据）...")
            
            # 按货物类型分类运输数据
            mtj_routes = transport_data[transport_data['货物类型'] == 'MTJ']
            h2_routes = transport_data[transport_data['货物类型'] == '氢气']
            ng_routes = transport_data[transport_data['货物类型'] == '天然气']
            
            print(f"  - MTJ运输: {len(mtj_routes)} 条")
            print(f"  - 氢气运输: {len(h2_routes)} 条")
            print(f"  - 天然气运输: {len(ng_routes)} 条")
            
            # 6.1. 绘制MTJ运输线路
            if len(mtj_routes) > 0:
                # 计算线条宽度
                if '周运输量(kg)' in mtj_routes.columns:
                    line_widths = self.normalize_transport_volume(mtj_routes['周运输量(kg)'])
                else:
                    line_widths = np.ones(len(mtj_routes)) * 1.5
                
                for idx, route in mtj_routes.iterrows():
                    main_ax.plot(
                        [route['起点经度'], route['终点经度']], 
                        [route['起点纬度'], route['终点纬度']], 
                        color=self.transport_type_colors['MTJ'], 
                        alpha=0.7, linewidth=line_widths[idx] if hasattr(line_widths, '__getitem__') else line_widths,
                        transform=self.data_crs, zorder=6
                    )
                    
                    # 更新连接统计（用于图例）
                    origin_type = self.map_facility_type(route.get('起点类型', ''))
                    dest_type = self.map_facility_type(route.get('终点类型', ''))
                    connection_type = f"{origin_type}_to_{dest_type}"
                    connection_stats[connection_type] = connection_stats.get(connection_type, 0) + 1
                
                stats_info["运输统计"]["绿色甲醇航空燃料运输"] = len(mtj_routes)
                # 注意：不添加独立的图例，使用连接统计系统
            
            # 6.2. 绘制氢气运输线路（from transport_summary）
            if len(h2_routes) > 0:
                for _, route in h2_routes.iterrows():
                    # 根据运输方式选择样式
                    transport_mode = route.get('运输方式', 'truck')
                    volume = route.get('日运输量(kg)', 100)
                    
                    if transport_mode == 'pipeline':
                        # 管道运输：紫色虚线
                        line_width = min(max(volume / 100, 1.0), 4.0)
                        main_ax.plot(
                            [route['起点经度'], route['终点经度']], 
                            [route['起点纬度'], route['终点纬度']], 
                            color='purple', alpha=0.8, linewidth=line_width,
                            linestyle='--', transform=self.data_crs, zorder=5
                        )
                    else:
                        # 罐车运输：紫色实线
                        line_width = min(max(volume / 200, 0.5), 3.0)
                        main_ax.plot(
                            [route['起点经度'], route['终点经度']], 
                            [route['起点纬度'], route['终点纬度']], 
                            color=self.transport_type_colors['H2'], 
                            alpha=0.6, linewidth=line_width,
                            transform=self.data_crs, zorder=4
                        )
                    
                    # 更新连接统计（用于图例）
                    origin_type = self.map_facility_type(route.get('起点类型', ''))
                    dest_type = self.map_facility_type(route.get('终点类型', ''))
                    connection_type = f"{origin_type}_to_{dest_type}"
                    connection_stats[connection_type] = connection_stats.get(connection_type, 0) + 1
                
                # 统计管道和罐车运输
                h2_pipeline_count = len(h2_routes[h2_routes['运输方式'] == 'pipeline'])
                h2_truck_count = len(h2_routes[h2_routes['运输方式'] == 'truck'])
                
                stats_info["运输统计"]["氢能管道运输"] = h2_pipeline_count
                stats_info["运输统计"]["氢能罐车运输"] = h2_truck_count
                # 注意：不添加独立的图例，使用连接统计系统
            
            # 6.3. 绘制天然气运输线路（from transport_summary）
            if len(ng_routes) > 0:
                for _, route in ng_routes.iterrows():
                    volume = route.get('日运输量(m3)', 100)
                    line_width = min(max(volume / 1000, 0.5), 3.0)
                    
                    main_ax.plot(
                        [route['起点经度'], route['终点经度']], 
                        [route['起点纬度'], route['终点纬度']], 
                        color=self.transport_type_colors['NG'], 
                        alpha=0.6, linewidth=line_width,
                        transform=self.data_crs, zorder=4
                    )
                    
                    # 更新连接统计（用于图例）
                    origin_type = self.map_facility_type(route.get('起点类型', ''))
                    dest_type = self.map_facility_type(route.get('终点类型', ''))
                    connection_type = f"{origin_type}_to_{dest_type}"
                    connection_stats[connection_type] = connection_stats.get(connection_type, 0) + 1
                
                stats_info["运输统计"]["天然气罐车运输"] = len(ng_routes)
                # 注意：不添加独立的图例，使用连接统计系统
            
            # 绘制机场（MTJ运输的终点）- 只统计真正的机场名称，不包括生产设施
            # 过滤出真正的机场终点（北京、天津等机场名称）
            if len(mtj_routes) > 0:
                airport_terminals = mtj_routes[
                    (mtj_routes['终点类型'] == '机场') & 
                    (~mtj_routes['终点'].str.contains('lng_|airport_', na=False))
                ][['终点', '终点纬度', '终点经度']].drop_duplicates()
            else:
                airport_terminals = pd.DataFrame()
            
            for _, airport in airport_terminals.iterrows():
                main_ax.scatter(
                    airport['终点经度'], airport['终点纬度'], 
                    c=self.facility_colors['airport'], s=80, marker='o', 
                    edgecolors='white', linewidth=1.0,
                    transform=self.data_crs, zorder=12, alpha=0.9
                )
            
            stats_info["设施统计"]["机场"] = len(airport_terminals)
            if len(airport_terminals) > 0:
                legend_elements.append(
                    plt.scatter([], [], c=self.facility_colors['airport'], s=80, marker='o', 
                               edgecolors='white', linewidth=1.0,
                               label=f'机场 ({len(airport_terminals)}个)')
                )
        
        # 添加图例
        main_ax.legend(handles=legend_elements, loc='lower left', 
                      fontsize=9, framealpha=0.9, ncol=2)
        
        # 添加标题
        plt.suptitle(
            '中国天然气-氢能-甲醇综合能源基础设施网络图', 
            fontsize=16, y=0.95, fontweight='bold'
        )
        
        # 添加统计信息
        stats_text = "基础设施统计:\n"
        for category, items in stats_info.items():
            stats_text += f"{category}:\n"
            for item, count in items.items():
                stats_text += f"  {item}: {count}个/条\n"
        
        main_ax.text(0.02, 0.02, stats_text, transform=main_ax.transAxes, 
                    fontsize=8, bbox=dict(boxstyle="round,pad=0.3", 
                    facecolor="white", alpha=0.9), verticalalignment='bottom')
        
        # 添加装饰
        self.add_decorations(main_ax, mini_ax)
        
        return fig, main_ax, mini_ax, all_data
    
    def find_latest_files(self, results_dir=None):
        """查找最新的所有相关数据文件"""
        if results_dir is None:
            # 路径: src/visualization/ -> src/ -> green_hydrogen_supply_chain_optimization/ -> results/
            results_dir = Path(__file__).parent.parent.parent / 'results'
        
        results_dir = Path(results_dir)
        
        # 需要查找的文件类型
        file_patterns = {
            'transport_summary': 'transport_summary_*.csv',
            'renewable_energy': 'renewable_energy_plants_*.csv', 
            'hydrogen_transport': 'hydrogen_transport_plan_*.csv',
            'ng_pipelines': 'ng_pipelines_*.csv',
            'ng_transport': 'ng_transport_plan_*.csv',
            'lng_terminals': 'lng_terminals_*.csv'
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
    
    def find_latest_transport_file(self, results_dir=None):
        """查找最新的transport_summary文件"""
        if results_dir is None:
            # 路径: src/visualization/ -> src/ -> green_hydrogen_supply_chain_optimization/ -> results/
            results_dir = Path(__file__).parent.parent.parent / 'results'
        
        results_dir = Path(results_dir)
        
        # 查找所有transport_summary文件
        pattern = 'transport_summary_*.csv'
        files = list(results_dir.glob(pattern))
        
        if not files:
            self.logger.error(f"在 {results_dir} 中未找到任何transport_summary文件")
            return None
        
        # 按文件修改时间排序，返回最新的
        latest_file = max(files, key=lambda x: x.stat().st_mtime)
        self.logger.info(f"找到最新的transport_summary文件: {latest_file}")
        
        return str(latest_file)
    
    def save_visualization(self, fig, filename=None, output_dir=None):
        """保存可视化结果"""
        if output_dir is None:
            # 路径: src/visualization/ -> src/ -> green_hydrogen_supply_chain_optimization/ -> results/
            output_dir = Path(__file__).parent.parent.parent / 'results' / 'visualizations'
        
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f'transport_route_network_{timestamp}.png'
        
        output_path = output_dir / filename
        
        fplt.savefig(str(output_path), dpi=300, bbox_inches='tight', 
                    facecolor='white', edgecolor='none')
        plt.close(fig)
        
        print(f"运输路径地图已保存: {output_path}")
        return str(output_path)
    
    def create_analysis_report(self, transport_data, display_data, output_dir=None):
        """创建分析报告"""
        if output_dir is None:
            # 路径: src/visualization/ -> src/ -> green_hydrogen_supply_chain_optimization/ -> results/
            output_dir = Path(__file__).parent.parent.parent / 'results' / 'reports'
        
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = output_dir / f'transport_analysis_report_{timestamp}.md'
        
        # 统计分析
        total_routes = len(transport_data)
        displayed_routes = len(display_data)
        
        # 运输方式统计
        transport_mode_stats = display_data['运输方式'].value_counts()
        
        # 距离统计
        distance_stats = display_data['距离(km)'].describe() if '距离(km)' in display_data.columns else None
        
        # 运输量统计
        volume_stats = display_data['周运输量(kg)'].describe() if '周运输量(kg)' in display_data.columns else None
        
        # 生成报告
        report_content = f"""# 天然气供应链运输路径分析报告

**生成时间**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## 数据概览

- **总运输路径数**: {total_routes}条
- **可视化路径数**: {displayed_routes}条
- **起点设施数**: {len(display_data['起点'].unique())}个
- **终点设施数**: {len(display_data['终点'].unique())}个

## 运输方式分布

"""
        
        for mode, count in transport_mode_stats.items():
            percentage = (count / displayed_routes) * 100
            report_content += f"- **{mode}**: {count}条 ({percentage:.1f}%)\n"
        
        if distance_stats is not None:
            report_content += f"""
## 运输距离统计

- **平均距离**: {distance_stats['mean']:.2f} km
- **最短距离**: {distance_stats['min']:.2f} km  
- **最长距离**: {distance_stats['max']:.2f} km
- **距离中位数**: {distance_stats['50%']:.2f} km
"""
        
        if volume_stats is not None:
            total_volume = display_data['周运输量(kg)'].sum()
            report_content += f"""
## 运输量统计

- **总运输量**: {total_volume/1e6:.2f} 万吨/周
- **平均运输量**: {volume_stats['mean']/1e3:.2f} 吨/周
- **最大运输量**: {volume_stats['max']/1e3:.2f} 吨/周
- **运输量中位数**: {volume_stats['50%']/1e3:.2f} 吨/周
"""
        
        report_content += f"""
## 主要运输枢纽

### 起点设施（按运输量排序）
"""
        
        # 按起点统计运输量
        if '周运输量(kg)' in display_data.columns:
            origin_volume = display_data.groupby('起点')['周运输量(kg)'].sum().sort_values(ascending=False).head(10)
            for origin, volume in origin_volume.items():
                report_content += f"- **{origin}**: {volume/1e3:.2f} 吨/周\n"
        
        # 保存报告
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        print(f"分析报告已保存: {report_path}")
        return str(report_path)

def main():
    """主函数"""
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    visualizer = TransportRouteVisualizer()
    
    # 查找所有最新数据文件
    latest_files = visualizer.find_latest_files()
    
    print("[INFO] 正在加载最新数据文件...")
    all_data = {}
    
    # 加载所有可用的数据
    if latest_files['transport_summary']:
        print(f"加载甲醇运输数据: {latest_files['transport_summary']}")
        all_data['transport_summary'] = visualizer.load_transport_data(latest_files['transport_summary'])
    
    if latest_files['renewable_energy']:
        print(f"加载可再生能源数据: {latest_files['renewable_energy']}")
        all_data['renewable_energy'] = visualizer.load_renewable_energy_data(latest_files['renewable_energy'])
    
    if latest_files['hydrogen_transport']:
        print(f"加载氢能运输数据: {latest_files['hydrogen_transport']}")
        all_data['hydrogen_transport'] = visualizer.load_hydrogen_transport_data(latest_files['hydrogen_transport'])
    
    if latest_files['ng_pipelines']:
        print(f"加载天然气管道数据: {latest_files['ng_pipelines']}")
        all_data['ng_pipelines'] = visualizer.load_ng_pipeline_data(latest_files['ng_pipelines'])
    
    if latest_files['ng_transport']:
        print(f"加载天然气运输数据: {latest_files['ng_transport']}")
        all_data['ng_transport'] = visualizer.load_ng_transport_data(latest_files['ng_transport'])
    
    if latest_files['lng_terminals']:
        print(f"加载LNG终端数据: {latest_files['lng_terminals']}")
        all_data['lng_terminals'] = visualizer.load_lng_terminal_data(latest_files['lng_terminals'])

    # 加载CO2聚类数据
    print("加载CO2聚类数据...")
    co2_clustering_results, co2_sources_df = visualizer.load_co2_clustering_data()
    if co2_clustering_results is not None:
        all_data['co2_clustering'] = co2_clustering_results
        all_data['co2_sources'] = co2_sources_df
        print(f"  - CO2聚类数: {co2_clustering_results.get('total_clusters', 0)} 个")
        print(f"  - CO2源点数: {len(co2_sources_df)} 个")

    # 检查是否有任何数据加载成功
    valid_data = {k: v for k, v in all_data.items() if v is not None and (isinstance(v, dict) or len(v) > 0)}
    
    if not valid_data:
        print("[ERROR] 未找到任何有效的数据文件")
        print("请确保已运行优化模型生成相关数据文件")
        return
    
    print(f"\n[SUCCESS] 成功加载 {len(valid_data)} 类数据:")
    for data_type, data in valid_data.items():
        print(f"  - {data_type}: {len(data)} 条记录")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 创建华北地区能源设施网络可视化
    print("\n[INFO] 尝试创建华北地区能源设施网络图...")
    print("显示设施类型: 太阳能电站、风电站、LNG终端、机场")
    print("显示管道网络: 原油管道(棕色)、成品油管道(橙红色)、天然气管道(蓝色)")
    print("显示连接关系: 不同设施类型间的连接用不同颜色表示")
    print("地图范围: 35°N-45°N, 110°E-120°E (华北地区)")

    result = visualizer.create_north_china_facilities_with_connections_visualization(valid_data)

    if result is not None:
        fig, main_ax, mini_ax, facility_stats, connection_stats = result

        # 保存可视化
        filename = f'north_china_energy_network_{timestamp}.png'
        viz_path = visualizer.save_visualization(fig, filename)

        print(f"\n{'='*60}")
        print(f"[SUCCESS] 华北地区能源设施网络可视化完成!")
        print(f"[OUTPUT] 图表文件已生成: {filename}")
        print(f"[PATH] 完整路径: {viz_path}")
        print(f"[REGION] 地图范围: 35°N-45°N, 110°E-120°E")
        print(f"[FACILITIES] 设施统计: {facility_stats}")
        print(f"[CONNECTIONS] 连接统计: {connection_stats}")
        print(f"{'='*60}")
        print(f"+ 文件生成成功! 请查看: {filename}")
    else:
        print("[WARNING] 华北地区设施网络可视化创建失败")

    # 显示详细统计（仅当设施统计存在时）
    if 'facility_stats' in locals() and facility_stats:
        total_facilities = sum(facility_stats.values())
        total_connections = sum(connection_stats.values())

        if total_facilities > 0:
            print(f"[SUMMARY] 总共显示了 {total_facilities} 个能源基础设施")
            facility_names = {
                'solar': '太阳能电站',
                'wind': '风电站',
                'lng': 'LNG终端',
                'airport': '机场'
            }
            for facility_type, count in facility_stats.items():
                if count > 0:
                    percentage = (count / total_facilities) * 100
                    print(f"  - {facility_names[facility_type]}: {count}个 ({percentage:.1f}%)")

        if total_connections > 0:
            print(f"[CONNECTIONS] 总共显示了 {total_connections} 条设施间连接")
            connection_names = {
                'solar_to_lng': '太阳能→LNG',
                'wind_to_lng': '风电→LNG',
                'lng_to_pipeline': 'LNG→管段',
                'pipeline_to_airport': '管段→机场',
                'lng_to_airport': 'LNG→机场',
                'renewable_to_pipeline': '可再生能源→管段',
                'pipeline_to_pipeline': '管段间连接'
            }
            for connection_type, count in connection_stats.items():
                if count > 0 and connection_type in connection_names:
                    percentage = (count / total_connections) * 100
                    print(f"  - {connection_names[connection_type]}: {count}条 ({percentage:.1f}%)")

        if total_facilities == 0:
            print("[WARNING] 在指定的华北地区范围内未找到任何设施")
            print("请检查数据文件或调整地图范围")

if __name__ == "__main__":
    main()