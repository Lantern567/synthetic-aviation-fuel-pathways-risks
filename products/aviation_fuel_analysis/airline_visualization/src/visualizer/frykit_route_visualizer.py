"""
基于frykit库的航线可视化器
使用与departure_airports相同的底图风格，添加航线绘制功能
"""

import matplotlib.pyplot as plt
import numpy as np
from cartopy.feature import LAND, RIVERS
import frykit.plot as fplt
import os
import pandas as pd
import matplotlib
from datetime import datetime
import logging

class FrykitRouteVisualizer:
    """使用frykit库的航线可视化器"""
    
    def __init__(self):
        """初始化可视化器"""
        # 设置全局字体为微软雅黑
        matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei']
        matplotlib.rcParams['axes.unicode_minus'] = False
        
        # 设置投影
        self.map_crs = fplt.CN_AZIMUTHAL_EQUIDISTANT
        self.data_crs = fplt.PLATE_CARREE
        
        # 设置刻度
        self.xticks = np.arange(-180, 181, 10)
        self.yticks = np.arange(-90, 91, 10)
        
        self.logger = logging.getLogger(__name__)
    
    def create_base_map(self, figsize=(12, 8)):
        """创建基础地图"""
        # 准备大地图
        fig = plt.figure(figsize=figsize)
        main_ax = fig.add_subplot(projection=self.map_crs)
        fplt.set_map_ticks(main_ax, (74, 136, 13, 57), self.xticks, self.yticks)
        main_ax.gridlines(xlocs=self.xticks, ylocs=self.yticks, lw=0.5, ls="--", color="gray")
        
        # 类似 NCL 的刻度风格
        main_ax.tick_params(
            length=8,
            width=0.9,
            labelsize=8,
            top=True,
            right=True,
            labeltop=True,
            labelright=True,
        )
        
        # 准备小地图
        mini_ax = fplt.add_mini_axes(main_ax)
        mini_ax.set_extent((105, 122, 2, 25), self.data_crs)
        mini_ax.gridlines(xlocs=self.xticks, ylocs=self.yticks, lw=0.5, ls="--", color="gray")
        
        # 添加要素
        for ax in [main_ax, mini_ax]:
            ax.set_facecolor("skyblue")
            ax.add_feature(LAND, fc="floralwhite", ec="k", lw=0.5)
            fplt.add_cn_city(ax, lw=0.2, edgecolor='lightgreen', linestyle='--', zorder=2)
            fplt.add_cn_line(ax, lw=1.2, edgecolor='dimgray', zorder=2.5)
            fplt.add_cn_border(ax, lw=0.75, edgecolor='black', zorder=3)
        
        return fig, main_ax, mini_ax
    
    def add_decorations(self, main_ax, mini_ax):
        """添加指北针和比例尺"""
        # 添加指北针和比例尺
        fplt.add_compass(main_ax, 0.92, 0.85, size=15, style="star")
        scale_bar = fplt.add_scale_bar(main_ax, 0.05, 0.95, length=1000)
        scale_bar.set_xticks([0, 500, 1000])
        scale_bar.xaxis.get_label().set_fontsize("small")
        
        # 小地图比例尺
        scale_bar2 = fplt.add_scale_bar(mini_ax, 0.4, 0.15, length=500)
        scale_bar2.set_xticks([0, 500])
        scale_bar2.xaxis.get_label().set_fontsize("small")
    
    def create_route_visualization(self, flight_data, max_routes=200, sample_size=1000):
        """
        创建航线可视化
        
        Args:
            flight_data: 航班数据DataFrame
            max_routes: 最大显示航线数
            sample_size: 数据采样大小
        """
        print("🗺️ 正在创建frykit航线地图...")
        
        # 数据采样和清洗
        if len(flight_data) > sample_size:
            df_sample = flight_data.sample(n=sample_size, random_state=42)
        else:
            df_sample = flight_data.copy()
        
        # 检查必要的列
        required_cols = ['出发城市', '到达城市', '出发城市x', '出发城市y', '到达城市x', '到达城市y']
        missing_cols = [col for col in required_cols if col not in df_sample.columns]
        if missing_cols:
            self.logger.error(f"缺少必要列: {missing_cols}")
            return None
        
        # 清洗坐标数据
        df_clean = df_sample.dropna(subset=['出发城市x', '出发城市y', '到达城市x', '到达城市y'])
        df_clean = df_clean[(df_clean['出发城市x'] >= 73) & (df_clean['出发城市x'] <= 135)]
        df_clean = df_clean[(df_clean['出发城市y'] >= 18) & (df_clean['出发城市y'] <= 54)]
        df_clean = df_clean[(df_clean['到达城市x'] >= 73) & (df_clean['到达城市x'] <= 135)]
        df_clean = df_clean[(df_clean['到达城市y'] >= 18) & (df_clean['到达城市y'] <= 54)]
        
        if len(df_clean) == 0:
            self.logger.error("没有有效数据")
            return None
        
        print(f"✅ 处理了 {len(df_clean)} 条有效航班数据")
        
        # 限制航线数量
        if len(df_clean) > max_routes:
            df_routes = df_clean.head(max_routes)
        else:
            df_routes = df_clean
        
        # 创建基础地图
        fig, main_ax, mini_ax = self.create_base_map()
        
        # 绘制航线
        print(f"🛫 正在绘制 {len(df_routes)} 条航线...")
        
        # 主地图航线
        for idx, row in df_routes.iterrows():
            # 航线颜色基于距离或随机
            if '里程（公里）' in row and pd.notna(row['里程（公里）']):
                # 根据距离设置颜色
                distance = row['里程（公里）']
                if distance < 1000:
                    color = 'blue'
                    alpha = 0.4
                elif distance < 2000:
                    color = 'green'
                    alpha = 0.5
                else:
                    color = 'red'
                    alpha = 0.6
            else:
                # 默认颜色
                color = 'orange'
                alpha = 0.4
            
            # 绘制航线
            main_ax.plot([row['出发城市x'], row['到达城市x']], 
                        [row['出发城市y'], row['到达城市y']], 
                        color=color, alpha=alpha, linewidth=0.8, 
                        transform=self.data_crs, zorder=4)
        
        # 小地图航线（南海区域）
        mini_routes = df_routes[
            (df_routes['出发城市x'] >= 105) & (df_routes['出发城市x'] <= 122) & 
            (df_routes['出发城市y'] >= 2) & (df_routes['出发城市y'] <= 25) &
            (df_routes['到达城市x'] >= 105) & (df_routes['到达城市x'] <= 122) & 
            (df_routes['到达城市y'] >= 2) & (df_routes['到达城市y'] <= 25)
        ]
        
        for idx, row in mini_routes.iterrows():
            mini_ax.plot([row['出发城市x'], row['到达城市x']], 
                        [row['出发城市y'], row['到达城市y']], 
                        color='orange', alpha=0.6, linewidth=0.5, 
                        transform=self.data_crs, zorder=4)
        
        # 绘制机场点
        # 出发机场
        departure_airports = df_clean[['起飞机场', '起飞机场y', '起飞机场x']].drop_duplicates()
        if not departure_airports.empty:
            main_ax.scatter(departure_airports['起飞机场x'], departure_airports['起飞机场y'], 
                           color='red', s=20, marker='o', transform=self.data_crs, 
                           zorder=10, label='起飞机场', alpha=0.8)
            
            # 小地图机场
            mini_departure = departure_airports[
                (departure_airports['起飞机场x'] >= 105) & (departure_airports['起飞机场x'] <= 122) & 
                (departure_airports['起飞机场y'] >= 2) & (departure_airports['起飞机场y'] <= 25)
            ]
            if not mini_departure.empty:
                mini_ax.scatter(mini_departure['起飞机场x'], mini_departure['起飞机场y'], 
                               color='red', s=12, marker='o', transform=self.data_crs, zorder=10)
        
        # 到达机场
        arrival_airports = df_clean[['降落机场', '降落机场y', '降落机场x']].drop_duplicates()
        if not arrival_airports.empty:
            main_ax.scatter(arrival_airports['降落机场x'], arrival_airports['降落机场y'], 
                           color='blue', s=15, marker='^', transform=self.data_crs, 
                           zorder=10, label='降落机场', alpha=0.7)
        
        # 添加图例
        legend_elements = [
            plt.Line2D([0], [0], color='blue', alpha=0.6, label='短程航线(<1000km)'),
            plt.Line2D([0], [0], color='green', alpha=0.6, label='中程航线(1000-2000km)'),
            plt.Line2D([0], [0], color='red', alpha=0.6, label='长程航线(>2000km)'),
            plt.scatter([], [], color='red', s=20, label='起飞机场'),
            plt.scatter([], [], color='blue', s=15, marker='^', label='降落机场')
        ]
        main_ax.legend(handles=legend_elements, loc='lower left', fontsize=9)
        
        # 添加标题
        plt.suptitle(f'中国民航航线网络图\n(显示{len(df_routes)}条航线)', fontsize=14, y=0.95)
        
        # 添加装饰
        self.add_decorations(main_ax, mini_ax)
        
        # 统计信息
        stats_text = f"""数据统计:
总航线: {len(df_routes)}条
机场数: {len(departure_airports)}个
覆盖城市: {len(df_clean['出发城市'].unique())}个"""
        
        main_ax.text(0.02, 0.02, stats_text, transform=main_ax.transAxes, 
                    fontsize=8, bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8))
        
        return fig, main_ax, mini_ax
    
    def save_visualization(self, fig, filename=None, output_dir='results/charts'):
        """保存可视化结果"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f'frykit_route_network_{timestamp}.png'
        
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, filename)
        
        fplt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close(fig)
        
        print(f"✅ 航线地图已保存: {output_path}")
        return output_path 