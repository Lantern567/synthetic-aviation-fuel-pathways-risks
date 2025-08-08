"""
基于pydeck的航班数据可视化器
支持多种可视化图层：航线、机场、城市热力图等
"""

import pydeck as pdk
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import logging
import colorsys

class PyDeckFlightVisualizer:
    """
    基于pydeck的航班可视化器
    """
    
    def __init__(self):
        """
        初始化可视化器
        """
        self.logger = logging.getLogger(__name__)
        self.default_view_state = None
        
    def calculate_view_state(self, data_bounds: Dict) -> pdk.ViewState:
        """
        根据数据边界计算合适的视图状态
        
        Args:
            data_bounds: 数据边界字典，包含min_lon, max_lon, min_lat, max_lat
            
        Returns:
            pydeck ViewState对象
        """
        center_lon = (data_bounds['min_lon'] + data_bounds['max_lon']) / 2
        center_lat = (data_bounds['min_lat'] + data_bounds['max_lat']) / 2
        
        # 计算缩放级别
        lon_range = data_bounds['max_lon'] - data_bounds['min_lon']
        lat_range = data_bounds['max_lat'] - data_bounds['min_lat']
        max_range = max(lon_range, lat_range)
        
        # 根据范围确定缩放级别
        if max_range > 30:
            zoom = 3
        elif max_range > 15:
            zoom = 4
        elif max_range > 8:
            zoom = 5
        elif max_range > 4:
            zoom = 6
        else:
            zoom = 7
        
        view_state = pdk.ViewState(
            longitude=center_lon,
            latitude=center_lat,
            zoom=zoom,
            pitch=0,
            bearing=0
        )
        
        self.default_view_state = view_state
        return view_state
    
    def create_route_layer(self, routes_data: pd.DataFrame, 
                          color_by: str = 'distance',
                          line_width_scale: int = 1) -> pdk.Layer:
        """
        创建航线图层
        
        Args:
            routes_data: 航线数据
            color_by: 颜色映射字段 ('distance', 'passengers', 'aircraft_type')
            line_width_scale: 线宽缩放因子
            
        Returns:
            pydeck Layer对象
        """
        self.logger.info(f"创建航线图层，颜色映射字段: {color_by}")
        
        # 准备航线数据
        routes_for_layer = []
        
        for _, row in routes_data.iterrows():
            # 创建路径坐标
            path = [
                [row['start_lon'], row['start_lat']],
                [row['end_lon'], row['end_lat']]
            ]
            
            # 根据映射字段确定颜色
            if color_by == 'distance':
                # 根据距离分配颜色（蓝色到红色）
                normalized_value = min(row['distance'] / 5000, 1.0)  # 假设最大距离5000km
                color = self._distance_to_color(normalized_value)
            elif color_by == 'passengers':
                # 根据乘客数量分配颜色
                normalized_value = min(row['passengers'] / 500, 1.0)  # 假设最大乘客500人
                color = self._passengers_to_color(normalized_value)
            elif color_by == 'aircraft_type':
                # 根据机型分配颜色
                color = self._aircraft_type_to_color(row['aircraft_type'])
            else:
                color = [100, 150, 200, 160]  # 默认蓝色
            
            # 根据乘客数量确定线宽
            line_width = max(1, (row['passengers'] / 100) * line_width_scale)
            
            routes_for_layer.append({
                'path': path,
                'color': color,
                'width': line_width,
                'start_city': row['start_city'],
                'end_city': row['end_city'],
                'distance': row['distance'],
                'passengers': row['passengers'],
                'aircraft_type': row['aircraft_type']
            })
        
        # 创建路径图层
        layer = pdk.Layer(
            'PathLayer',
            routes_for_layer,
            get_path='path',
            get_color='color',
            get_width='width',
            width_scale=1,
            width_min_pixels=1,
            get_tooltip_text="航线: {start_city} → {end_city}\n距离: {distance}公里\n乘客: {passengers}人\n机型: {aircraft_type}",
            pickable=True
        )
        
        return layer
    
    def create_airport_layer(self, airport_stats: pd.DataFrame, 
                           size_scale: int = 1000) -> pdk.Layer:
        """
        创建机场散点图层
        
        Args:
            airport_stats: 机场统计数据
            size_scale: 大小缩放因子
            
        Returns:
            pydeck Layer对象
        """
        self.logger.info("创建机场散点图层")
        
        # 准备机场数据
        airports_for_layer = []
        
        for _, row in airport_stats.iterrows():
            # 根据航班数量确定大小和颜色
            flight_count = row['total_flights']
            size = max(50, min(flight_count * size_scale / 100, 1000))
            
            # 颜色根据航班数量（从绿色到红色）
            normalized_count = min(flight_count / 100, 1.0)
            color = self._flight_count_to_color(normalized_count)
            
            airports_for_layer.append({
                'lon': row['lon'],
                'lat': row['lat'],
                'airport_name': row['airport_name'],
                'total_flights': flight_count,
                'size': size,
                'color': color
            })
        
        # 创建散点图层
        layer = pdk.Layer(
            'ScatterplotLayer',
            airports_for_layer,
            get_position=['lon', 'lat'],
            get_color='color',
            get_radius='size',
            radius_scale=1,
            radius_min_pixels=3,
            radius_max_pixels=50,
            get_tooltip_text="机场: {airport_name}\n航班数: {total_flights}",
            pickable=True
        )
        
        return layer
    
    def create_city_heatmap_layer(self, cities_data: pd.DataFrame, 
                                 weight_by: str = 'total_passengers') -> pdk.Layer:
        """
        创建城市热力图层
        
        Args:
            cities_data: 城市数据
            weight_by: 权重字段 ('total_passengers', 'total_distance')
            
        Returns:
            pydeck Layer对象
        """
        self.logger.info(f"创建城市热力图层，权重字段: {weight_by}")
        
        # 准备热力图数据
        heatmap_data = []
        
        for _, row in cities_data.iterrows():
            weight = row[weight_by] if weight_by in row else 1
            
            heatmap_data.append({
                'lon': row['lon'],
                'lat': row['lat'],
                'weight': weight,
                'city': row['city']
            })
        
        # 创建热力图层
        layer = pdk.Layer(
            'HeatmapLayer',
            heatmap_data,
            get_position=['lon', 'lat'],
            get_weight='weight',
            radius_pixels=100,
            intensity=1,
            threshold=0.1,
            pickable=False
        )
        
        return layer
    
    def create_arc_layer(self, routes_data: pd.DataFrame, 
                        color_by: str = 'distance') -> pdk.Layer:
        """
        创建弧线图层（3D效果的航线）
        
        Args:
            routes_data: 航线数据
            color_by: 颜色映射字段
            
        Returns:
            pydeck Layer对象
        """
        self.logger.info("创建弧线图层")
        
        # 准备弧线数据
        arcs_for_layer = []
        
        for _, row in routes_data.iterrows():
            # 根据映射字段确定颜色
            if color_by == 'distance':
                normalized_value = min(row['distance'] / 5000, 1.0)
                color = self._distance_to_color(normalized_value)
            elif color_by == 'passengers':
                normalized_value = min(row['passengers'] / 500, 1.0)
                color = self._passengers_to_color(normalized_value)
            else:
                color = [100, 150, 200, 160]
            
            # 根据乘客数量确定弧线宽度
            width = max(1, row['passengers'] / 50)
            
            arcs_for_layer.append({
                'source_position': [row['start_lon'], row['start_lat']],
                'target_position': [row['end_lon'], row['end_lat']],
                'color': color,
                'width': width,
                'start_city': row['start_city'],
                'end_city': row['end_city'],
                'distance': row['distance'],
                'passengers': row['passengers']
            })
        
        # 创建弧线图层
        layer = pdk.Layer(
            'ArcLayer',
            arcs_for_layer,
            get_source_position='source_position',
            get_target_position='target_position',
            get_source_color='color',
            get_target_color='color',
            get_width='width',
            width_scale=1,
            width_min_pixels=1,
            get_tooltip_text="航线: {start_city} → {end_city}\n距离: {distance}公里\n乘客: {passengers}人",
            pickable=True
        )
        
        return layer
    
    def create_comprehensive_visualization(self, processed_data: Dict[str, pd.DataFrame],
                                         visualization_type: str = 'routes_and_airports',
                                         **kwargs) -> pdk.Deck:
        """
        创建综合可视化
        
        Args:
            processed_data: 处理后的数据字典
            visualization_type: 可视化类型
                - 'routes_and_airports': 航线和机场
                - 'heatmap': 城市热力图
                - 'arc_routes': 3D弧线航线
                - 'comprehensive': 综合视图
            **kwargs: 其他参数
            
        Returns:
            pydeck Deck对象
        """
        self.logger.info(f"创建综合可视化，类型: {visualization_type}")
        
        layers = []
        
        # 根据可视化类型创建图层
        if visualization_type == 'routes_and_airports':
            # 航线和机场视图
            route_layer = self.create_route_layer(
                processed_data['routes'], 
                color_by=kwargs.get('route_color_by', 'distance')
            )
            airport_layer = self.create_airport_layer(
                processed_data['airport_stats'],
                size_scale=kwargs.get('airport_size_scale', 1000)
            )
            layers = [route_layer, airport_layer]
            
        elif visualization_type == 'heatmap':
            # 热力图视图
            heatmap_layer = self.create_city_heatmap_layer(
                processed_data['cities'],
                weight_by=kwargs.get('heatmap_weight_by', 'total_passengers')
            )
            layers = [heatmap_layer]
            
        elif visualization_type == 'arc_routes':
            # 3D弧线视图
            arc_layer = self.create_arc_layer(
                processed_data['routes'],
                color_by=kwargs.get('arc_color_by', 'distance')
            )
            layers = [arc_layer]
            
        elif visualization_type == 'comprehensive':
            # 综合视图
            route_layer = self.create_route_layer(
                processed_data['routes'], 
                color_by='distance',
                line_width_scale=0.5
            )
            airport_layer = self.create_airport_layer(
                processed_data['airport_stats'],
                size_scale=500
            )
            heatmap_layer = self.create_city_heatmap_layer(
                processed_data['cities'],
                weight_by='total_passengers'
            )
            layers = [heatmap_layer, route_layer, airport_layer]
        
        # 计算视图状态
        routes_data = processed_data['routes']
        bounds = {
            'min_lon': min(routes_data['start_lon'].min(), routes_data['end_lon'].min()),
            'max_lon': max(routes_data['start_lon'].max(), routes_data['end_lon'].max()),
            'min_lat': min(routes_data['start_lat'].min(), routes_data['end_lat'].min()),
            'max_lat': max(routes_data['start_lat'].max(), routes_data['end_lat'].max())
        }
        
        view_state = self.calculate_view_state(bounds)
        
        # 创建deck对象
        deck = pdk.Deck(
            layers=layers,
            initial_view_state=view_state,
            tooltip={"html": "<b>{object}</b>", "style": {"backgroundColor": "steelblue", "color": "white"}},
            map_style='mapbox://styles/mapbox/light-v9'
        )
        
        return deck
    
    def _distance_to_color(self, normalized_value: float) -> List[int]:
        """距离值转颜色（蓝色到红色）"""
        # 蓝色(短距离) -> 绿色 -> 红色(长距离)
        if normalized_value < 0.5:
            # 蓝色到绿色
            r = int(255 * (normalized_value * 2))
            g = 255
            b = int(255 * (1 - normalized_value * 2))
        else:
            # 绿色到红色
            r = 255
            g = int(255 * (2 - normalized_value * 2))
            b = 0
        
        return [r, g, b, 160]
    
    def _passengers_to_color(self, normalized_value: float) -> List[int]:
        """乘客数量转颜色（绿色到橙色）"""
        r = int(255 * normalized_value)
        g = 200
        b = int(100 * (1 - normalized_value))
        return [r, g, b, 160]
    
    def _aircraft_type_to_color(self, aircraft_type: str) -> List[int]:
        """机型转颜色"""
        # 为不同机型定义颜色
        aircraft_colors = {
            'JET': [255, 100, 100, 160],           # 红色
            '波音737(中)': [100, 255, 100, 160],   # 绿色
            '空客320(中)': [100, 100, 255, 160],   # 蓝色
            '空客321(中)': [255, 255, 100, 160],   # 黄色
            '空客330(宽体机)': [255, 100, 255, 160], # 紫色
            '空客319(中)': [100, 255, 255, 160],   # 青色
            'ERJ-190(中)': [255, 150, 100, 160],   # 橙色
            '波音777(大)': [150, 100, 255, 160],   # 蓝紫色
            '空客380(大)': [255, 200, 100, 160]    # 金色
        }
        
        return aircraft_colors.get(aircraft_type, [128, 128, 128, 160])  # 默认灰色
    
    def _flight_count_to_color(self, normalized_value: float) -> List[int]:
        """航班数量转颜色（绿色到红色）"""
        r = int(255 * normalized_value)
        g = int(255 * (1 - normalized_value))
        b = 50
        return [r, g, b, 180] 