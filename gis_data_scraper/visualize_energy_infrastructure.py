#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
中国能源基础设施GIS数据可视化
Visualization of China Energy Infrastructure GIS Data

作者: AI Assistant
日期: 2025-07-14
功能: 对20个能源基础设施数据集进行地图可视化
"""

import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import seaborn as sns
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False

class EnergyInfrastructureVisualizer:
    """能源基础设施数据可视化类"""
    
    def __init__(self, data_dir="scraped_gis_data"):
        """初始化可视化器"""
        self.data_dir = Path(data_dir)
        self.output_dir = Path("visualization_results")
        self.output_dir.mkdir(exist_ok=True)
        
        # 数据集配置
        self.datasets = {
            # 电力基础设施
            'nuclear_power_plants': {'name': '核电站', 'color': '#FF6B35', 'marker': 'o', 'size': 100},
            'coal_power_plants': {'name': '燃煤电厂', 'color': '#2C2C2C', 'marker': 's', 'size': 20},
            'gas_power_plants': {'name': '燃气电厂', 'color': '#4CAF50', 'marker': '^', 'size': 60},
            
            # 可再生能源
            'solar_power_plants': {'name': '太阳能电站', 'color': '#FFD700', 'marker': 'D', 'size': 15},
            'wind_power_plants': {'name': '风电场', 'color': '#87CEEB', 'marker': 'v', 'size': 25},
            
            # 石油天然气
            'lng_terminals': {'name': 'LNG接收站', 'color': '#FF4500', 'marker': 'H', 'size': 150},
            'oil_ports': {'name': '石油港口', 'color': '#8B4513', 'marker': 'p', 'size': 120},
            'oil_refineries': {'name': '石油炼厂', 'color': '#800080', 'marker': '*', 'size': 100},
            'oil_storage': {'name': '石油储存设施', 'color': '#DC143C', 'marker': 'h', 'size': 80},
            'gas_storage': {'name': '天然气储存设施', 'color': '#32CD32', 'marker': 'X', 'size': 120},
            
            # 新能源技术
            'hydrogen_facilities': {'name': '氢能设施', 'color': '#00CED1', 'marker': 'P', 'size': 30},
            'ccs_projects': {'name': 'CCS项目', 'color': '#8A2BE2', 'marker': '+', 'size': 50},
            'ev_battery_factories': {'name': '电池工厂', 'color': '#FF1493', 'marker': '8', 'size': 80},
            'mining_properties': {'name': '采矿资产', 'color': '#A0522D', 'marker': '.', 'size': 10}
        }
        
        # 管道数据集
        self.pipeline_datasets = {
            'natural_gas_pipelines': {'name': '天然气管道', 'color': '#32CD32', 'linewidth': 2},
            'crude_pipelines': {'name': '原油管道', 'color': '#8B4513', 'linewidth': 3},
            'refined_product_pipelines': {'name': '成品油管道', 'color': '#FF6347', 'linewidth': 2},
            'hydrogen_pipelines': {'name': '氢气管道', 'color': '#00CED1', 'linewidth': 1}
        }
        
    def load_data(self, dataset_name):
        """加载数据集"""
        try:
            geojson_file = self.data_dir / f"{dataset_name}.geojson"
            if geojson_file.exists():
                gdf = gpd.read_file(geojson_file)
                print(f"✓ 加载 {dataset_name}: {len(gdf)} 个要素")
                return gdf
            else:
                print(f"✗ 文件不存在: {geojson_file}")
                return None
        except Exception as e:
            print(f"✗ 加载 {dataset_name} 失败: {e}")
            return None
    
    def load_china_boundaries(self):
        """加载中国边界数据"""
        try:
            boundaries = self.load_data('china_boundaries')
            if boundaries is not None:
                print(f"✓ 加载中国行政边界数据: {len(boundaries)} 个边界要素")
                return boundaries
            else:
                print("✗ 中国行政边界数据不可用")
                return None
        except Exception as e:
            print(f"✗ 加载中国边界数据失败: {e}")
            return None
    
    def load_urban_areas(self):
        """加载城市区域数据"""
        try:
            urban_areas = self.load_data('urban_areas')
            if urban_areas is not None:
                print(f"✓ 加载城市区域数据: {len(urban_areas)} 个城市区域")
                return urban_areas
            else:
                print("✗ 城市区域数据不可用")
                return None
        except Exception as e:
            print(f"✗ 加载城市区域数据失败: {e}")
            return None
    
    def setup_map_boundaries(self, ax, show_urban=True):
        """设置地图边界和背景"""
        # 加载边界数据
        china_bounds = self.load_china_boundaries()
        urban_areas = self.load_urban_areas()
        
        # 绘制行政边界
        if china_bounds is not None:
            china_bounds.plot(ax=ax, color='lightgray', edgecolor='darkgray', 
                             alpha=0.6, linewidth=0.8)
            # 根据边界数据设置地图范围
            bounds = china_bounds.total_bounds
            ax.set_xlim(bounds[0] - 1, bounds[2] + 1)
            ax.set_ylim(bounds[1] - 1, bounds[3] + 1)
        else:
            # 默认中国范围
            ax.set_xlim(73, 135)
            ax.set_ylim(18, 54)
        
        # 绘制城市区域（可选）
        if show_urban and urban_areas is not None:
            urban_areas.plot(ax=ax, color='lightyellow', edgecolor='orange', 
                           alpha=0.3, linewidth=0.3)
        
        return china_bounds, urban_areas
    
    def create_overview_map(self):
        """创建总览地图"""
        print("创建能源基础设施总览地图...")
        
        # 创建大图
        fig, ax = plt.subplots(1, 1, figsize=(20, 16))
        
        # 加载中国边界和城市区域
        china_bounds = self.load_china_boundaries()
        urban_areas = self.load_urban_areas()
        
        # 绘制边界数据
        if china_bounds is not None:
            china_bounds.plot(ax=ax, color='lightgray', edgecolor='darkgray', 
                             alpha=0.6, linewidth=0.8, label='行政边界')
        
        if urban_areas is not None:
            # 筛选中国境内的城市区域
            urban_areas.plot(ax=ax, color='lightyellow', edgecolor='orange', 
                           alpha=0.4, linewidth=0.5, label='城市区域')
        
        # 设置中国地图范围
        if china_bounds is not None:
            bounds = china_bounds.total_bounds
            ax.set_xlim(bounds[0] - 1, bounds[2] + 1)
            ax.set_ylim(bounds[1] - 1, bounds[3] + 1)
        else:
            ax.set_xlim(73, 135)
            ax.set_ylim(18, 54)
        
        # 收集图例元素
        legend_elements = []
        
        # 绘制点状设施
        for dataset_name, config in self.datasets.items():
            gdf = self.load_data(dataset_name)
            if gdf is not None and len(gdf) > 0:
                gdf.plot(ax=ax, 
                        color=config['color'], 
                        marker=config['marker'],
                        markersize=config['size'],
                        alpha=0.7,
                        label=config['name'])
                
                legend_elements.append(
                    plt.Line2D([0], [0], marker=config['marker'], color='w', 
                              markerfacecolor=config['color'], markersize=8, 
                              label=f"{config['name']} ({len(gdf)})")
                )
        
        # 绘制管道
        for dataset_name, config in self.pipeline_datasets.items():
            gdf = self.load_data(dataset_name)
            if gdf is not None and len(gdf) > 0:
                gdf.plot(ax=ax,
                        color=config['color'],
                        linewidth=config['linewidth'],
                        alpha=0.8,
                        label=config['name'])
                
                legend_elements.append(
                    plt.Line2D([0], [0], color=config['color'], 
                              linewidth=config['linewidth']*2,
                              label=f"{config['name']} ({len(gdf)}段)")
                )
        
        # 添加边界图例
        if china_bounds is not None:
            legend_elements.insert(0, 
                plt.Line2D([0], [0], color='darkgray', linewidth=2, 
                          label='中国行政边界'))
        if urban_areas is not None:
            legend_elements.insert(1 if china_bounds is not None else 0,
                plt.Rectangle((0, 0), 1, 1, facecolor='lightyellow', 
                            edgecolor='orange', alpha=0.4, label='城市区域'))
        
        # 设置图例
        ax.legend(handles=legend_elements, loc='upper left', bbox_to_anchor=(1.02, 1), 
                 fontsize=10, frameon=True)
        
        # 设置标题和标签
        ax.set_title('中国能源基础设施分布总览图\nChina Energy Infrastructure Overview', 
                    fontsize=20, fontweight='bold', pad=20)
        ax.set_xlabel('经度 (Longitude)', fontsize=12)
        ax.set_ylabel('纬度 (Latitude)', fontsize=12)
        
        # 添加网格
        ax.grid(True, alpha=0.3)
        ax.set_aspect('equal')
        
        plt.tight_layout()
        plt.savefig(self.output_dir / '01_能源基础设施总览图.png', 
                   dpi=300, bbox_inches='tight')
        plt.show()
        
    def create_category_maps(self):
        """创建分类地图"""
        
        # 1. 电力基础设施
        self.create_power_infrastructure_map()
        
        # 2. 可再生能源
        self.create_renewable_energy_map()
        
        # 3. 石油天然气
        self.create_oil_gas_map()
        
        # 4. 管道网络
        self.create_pipeline_map()
        
        # 5. 新兴技术
        self.create_emerging_tech_map()
    
    def create_power_infrastructure_map(self):
        """创建电力基础设施地图"""
        print("创建电力基础设施地图...")
        
        fig, ax = plt.subplots(1, 1, figsize=(16, 12))
        
        # 设置地图边界
        china_bounds, urban_areas = self.setup_map_boundaries(ax, show_urban=False)
        
        legend_elements = []
        
        # 电力设施
        power_datasets = ['nuclear_power_plants', 'coal_power_plants', 'gas_power_plants']
        
        for dataset_name in power_datasets:
            if dataset_name in self.datasets:
                config = self.datasets[dataset_name]
                gdf = self.load_data(dataset_name)
                if gdf is not None and len(gdf) > 0:
                    gdf.plot(ax=ax, 
                            color=config['color'], 
                            marker=config['marker'],
                            markersize=config['size'],
                            alpha=0.8,
                            label=config['name'])
                    
                    legend_elements.append(
                        plt.Line2D([0], [0], marker=config['marker'], color='w', 
                                  markerfacecolor=config['color'], markersize=10, 
                                  label=f"{config['name']} ({len(gdf)})")
                    )
        
        ax.legend(handles=legend_elements, loc='upper right', fontsize=12)
        ax.set_title('中国电力基础设施分布图\nChina Power Infrastructure', 
                    fontsize=18, fontweight='bold', pad=20)
        ax.set_xlabel('经度', fontsize=12)
        ax.set_ylabel('纬度', fontsize=12)
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / '02_电力基础设施分布图.png', 
                   dpi=300, bbox_inches='tight')
        plt.show()
    
    def create_renewable_energy_map(self):
        """创建可再生能源地图"""
        print("创建可再生能源地图...")
        
        fig, ax = plt.subplots(1, 1, figsize=(16, 12))
        
        # 设置地图边界
        china_bounds, urban_areas = self.setup_map_boundaries(ax, show_urban=True)
        
        legend_elements = []
        
        # 可再生能源设施
        renewable_datasets = ['solar_power_plants', 'wind_power_plants']
        
        for dataset_name in renewable_datasets:
            if dataset_name in self.datasets:
                config = self.datasets[dataset_name]
                gdf = self.load_data(dataset_name)
                if gdf is not None and len(gdf) > 0:
                    gdf.plot(ax=ax, 
                            color=config['color'], 
                            marker=config['marker'],
                            markersize=config['size'],
                            alpha=0.7,
                            label=config['name'])
                    
                    legend_elements.append(
                        plt.Line2D([0], [0], marker=config['marker'], color='w', 
                                  markerfacecolor=config['color'], markersize=10, 
                                  label=f"{config['name']} ({len(gdf)})")
                    )
        
        # 添加城市区域图例
        if urban_areas is not None:
            legend_elements.insert(0, 
                plt.Rectangle((0, 0), 1, 1, facecolor='lightyellow', 
                            edgecolor='orange', alpha=0.3, label='城市区域'))
        
        ax.legend(handles=legend_elements, loc='upper right', fontsize=12)
        ax.set_title('中国可再生能源设施分布图\nChina Renewable Energy Facilities', 
                    fontsize=18, fontweight='bold', pad=20)
        ax.set_xlabel('经度', fontsize=12)
        ax.set_ylabel('纬度', fontsize=12)
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / '03_可再生能源设施分布图.png', 
                   dpi=300, bbox_inches='tight')
        plt.show()
    
    def create_oil_gas_map(self):
        """创建石油天然气设施地图"""
        print("创建石油天然气设施地图...")
        
        fig, ax = plt.subplots(1, 1, figsize=(16, 12))
        
        # 设置地图边界
        china_bounds, urban_areas = self.setup_map_boundaries(ax, show_urban=False)
        
        legend_elements = []
        
        # 石油天然气设施
        oil_gas_datasets = ['lng_terminals', 'oil_ports', 'oil_refineries', 
                           'oil_storage', 'gas_storage']
        
        for dataset_name in oil_gas_datasets:
            if dataset_name in self.datasets:
                config = self.datasets[dataset_name]
                gdf = self.load_data(dataset_name)
                if gdf is not None and len(gdf) > 0:
                    gdf.plot(ax=ax, 
                            color=config['color'], 
                            marker=config['marker'],
                            markersize=config['size'],
                            alpha=0.8,
                            label=config['name'])
                    
                    legend_elements.append(
                        plt.Line2D([0], [0], marker=config['marker'], color='w', 
                                  markerfacecolor=config['color'], markersize=10, 
                                  label=f"{config['name']} ({len(gdf)})")
                    )
        
        ax.legend(handles=legend_elements, loc='upper right', fontsize=12)
        ax.set_title('中国石油天然气设施分布图\nChina Oil & Gas Facilities', 
                    fontsize=18, fontweight='bold', pad=20)
        ax.set_xlabel('经度', fontsize=12)
        ax.set_ylabel('纬度', fontsize=12)
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / '04_石油天然气设施分布图.png', 
                   dpi=300, bbox_inches='tight')
        plt.show()
        
        ax.legend(handles=legend_elements, loc='upper right', fontsize=12)
        ax.set_title('中国石油天然气设施分布图\nChina Oil & Gas Facilities', 
                    fontsize=18, fontweight='bold', pad=20)
        ax.set_xlabel('经度', fontsize=12)
        ax.set_ylabel('纬度', fontsize=12)
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / '04_石油天然气设施分布图.png', 
                   dpi=300, bbox_inches='tight')
        plt.show()
    
    def create_pipeline_map(self):
        """创建管道网络地图"""
        print("创建管道网络地图...")
        
        fig, ax = plt.subplots(1, 1, figsize=(16, 12))
        
        # 设置地图边界
        china_bounds, urban_areas = self.setup_map_boundaries(ax, show_urban=False)
        
        legend_elements = []
        
        # 管道网络
        for dataset_name, config in self.pipeline_datasets.items():
            gdf = self.load_data(dataset_name)
            if gdf is not None and len(gdf) > 0:
                gdf.plot(ax=ax,
                        color=config['color'],
                        linewidth=config['linewidth'],
                        alpha=0.8,
                        label=config['name'])
                
                legend_elements.append(
                    plt.Line2D([0], [0], color=config['color'], 
                              linewidth=config['linewidth']*2,
                              label=f"{config['name']} ({len(gdf)}段)")
                )
        
        ax.legend(handles=legend_elements, loc='upper right', fontsize=12)
        ax.set_title('中国能源管道网络分布图\nChina Energy Pipeline Network', 
                    fontsize=18, fontweight='bold', pad=20)
        ax.set_xlabel('经度', fontsize=12)
        ax.set_ylabel('纬度', fontsize=12)
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / '05_能源管道网络分布图.png', 
                   dpi=300, bbox_inches='tight')
        plt.show()
        ax.set_title('中国能源管道网络分布图\nChina Energy Pipeline Network', 
                    fontsize=18, fontweight='bold', pad=20)
        ax.set_xlabel('经度', fontsize=12)
        ax.set_ylabel('纬度', fontsize=12)
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / '05_能源管道网络分布图.png', 
                   dpi=300, bbox_inches='tight')
        plt.show()
    
    def create_emerging_tech_map(self):
        """创建新兴技术地图"""
        print("创建新兴技术设施地图...")
        
        fig, ax = plt.subplots(1, 1, figsize=(16, 12))
        
        # 设置地图边界
        china_bounds, urban_areas = self.setup_map_boundaries(ax, show_urban=True)
        
        legend_elements = []
        
        # 新兴技术设施
        emerging_datasets = ['hydrogen_facilities', 'ccs_projects', 'ev_battery_factories']
        
        for dataset_name in emerging_datasets:
            if dataset_name in self.datasets:
                config = self.datasets[dataset_name]
                gdf = self.load_data(dataset_name)
                if gdf is not None and len(gdf) > 0:
                    gdf.plot(ax=ax, 
                            color=config['color'], 
                            marker=config['marker'],
                            markersize=config['size'],
                            alpha=0.7,
                            label=config['name'])
                    
                    legend_elements.append(
                        plt.Line2D([0], [0], marker=config['marker'], color='w', 
                                  markerfacecolor=config['color'], markersize=10, 
                                  label=f"{config['name']} ({len(gdf)})")
                    )
        
        # 添加氢气管道
        if 'hydrogen_pipelines' in self.pipeline_datasets:
            config = self.pipeline_datasets['hydrogen_pipelines']
            gdf = self.load_data('hydrogen_pipelines')
            if gdf is not None and len(gdf) > 0:
                gdf.plot(ax=ax,
                        color=config['color'],
                        linewidth=config['linewidth'],
                        alpha=0.8)
                
                legend_elements.append(
                    plt.Line2D([0], [0], color=config['color'], 
                              linewidth=config['linewidth']*2,
                              label=f"{config['name']} ({len(gdf)}段)")
                )
        
        # 添加城市区域图例
        if urban_areas is not None:
            legend_elements.insert(0, 
                plt.Rectangle((0, 0), 1, 1, facecolor='lightyellow', 
                            edgecolor='orange', alpha=0.3, label='城市区域'))
        
        ax.legend(handles=legend_elements, loc='upper right', fontsize=12)
        ax.set_title('中国新兴能源技术设施分布图\nChina Emerging Energy Technologies', 
                    fontsize=18, fontweight='bold', pad=20)
        ax.set_xlabel('经度', fontsize=12)
        ax.set_ylabel('纬度', fontsize=12)
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / '06_新兴能源技术分布图.png', 
                   dpi=300, bbox_inches='tight')
        plt.show()
    
    def create_statistics_charts(self):
        """创建统计图表"""
        print("创建统计图表...")
        
        # 收集数据统计
        stats_data = []
        
        for dataset_name, config in self.datasets.items():
            gdf = self.load_data(dataset_name)
            if gdf is not None:
                stats_data.append({
                    'dataset': config['name'],
                    'count': len(gdf),
                    'category': self.get_category(dataset_name)
                })
        
        # 添加管道数据
        for dataset_name, config in self.pipeline_datasets.items():
            gdf = self.load_data(dataset_name)
            if gdf is not None:
                stats_data.append({
                    'dataset': config['name'],
                    'count': len(gdf),
                    'category': '管道基础设施'
                })
        
        df_stats = pd.DataFrame(stats_data)
        
        # 创建图表
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(20, 16))
        
        # 1. 按类别统计
        category_stats = df_stats.groupby('category')['count'].sum().sort_values(ascending=False)
        ax1.pie(category_stats.values, labels=category_stats.index, autopct='%1.1f%%', 
               startangle=90)
        ax1.set_title('各类别设施数量占比', fontsize=14, fontweight='bold')
        
        # 2. 前10大数据集
        top_datasets = df_stats.nlargest(10, 'count')
        bars = ax2.bar(range(len(top_datasets)), top_datasets['count'], 
                       color=plt.cm.Set3(np.linspace(0, 1, len(top_datasets))))
        ax2.set_title('前10大数据集规模', fontsize=14, fontweight='bold')
        ax2.set_xlabel('数据集')
        ax2.set_ylabel('设施数量')
        ax2.set_xticks(range(len(top_datasets)))
        ax2.set_xticklabels(top_datasets['dataset'], rotation=45, ha='right')
        
        # 添加数值标签
        for i, bar in enumerate(bars):
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height + height*0.01,
                    f'{int(height):,}', ha='center', va='bottom')
        
        # 3. 按类别详细统计
        category_colors = {'电力基础设施': '#FF6B6B', '可再生能源': '#4ECDC4', 
                          '石油天然气': '#45B7D1', '管道基础设施': '#96CEB4',
                          '新兴技术': '#FFEAA7', '其他': '#DDA0DD'}
        
        for category in df_stats['category'].unique():
            cat_data = df_stats[df_stats['category'] == category]
            bottom = 0
            for _, row in cat_data.iterrows():
                ax3.bar(category, row['count'], bottom=bottom, 
                       label=row['dataset'] if category == df_stats['category'].iloc[0] else "",
                       color=category_colors.get(category, '#gray'))
                bottom += row['count']
        
        ax3.set_title('各类别设施详细构成', fontsize=14, fontweight='bold')
        ax3.set_xlabel('类别')
        ax3.set_ylabel('设施数量')
        ax3.tick_params(axis='x', rotation=45)
        
        # 4. 数据集规模分布
        ax4.hist(df_stats['count'], bins=20, color='skyblue', alpha=0.7, edgecolor='black')
        ax4.set_title('数据集规模分布', fontsize=14, fontweight='bold')
        ax4.set_xlabel('设施数量')
        ax4.set_ylabel('数据集个数')
        ax4.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / '07_数据统计图表.png', 
                   dpi=300, bbox_inches='tight')
        plt.show()
    
    def get_category(self, dataset_name):
        """获取数据集类别"""
        if dataset_name in ['nuclear_power_plants', 'coal_power_plants', 'gas_power_plants']:
            return '电力基础设施'
        elif dataset_name in ['solar_power_plants', 'wind_power_plants']:
            return '可再生能源'
        elif dataset_name in ['lng_terminals', 'oil_ports', 'oil_refineries', 'oil_storage', 'gas_storage']:
            return '石油天然气'
        elif dataset_name in ['hydrogen_facilities', 'ccs_projects', 'ev_battery_factories']:
            return '新兴技术'
        else:
            return '其他'
    
    def create_natural_gas_analysis(self):
        """创建天然气产业链专题分析"""
        print("创建天然气产业链专题分析...")
        
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(20, 16))
        
        # 加载天然气相关数据
        gas_plants = self.load_data('gas_power_plants')
        lng_terminals = self.load_data('lng_terminals')
        gas_pipelines = self.load_data('natural_gas_pipelines')
        gas_storage = self.load_data('gas_storage')
        
        # 1. 天然气设施总览地图
        china_bounds, urban_areas = self.setup_map_boundaries(ax1, show_urban=False)
        
        if gas_plants is not None:
            gas_plants.plot(ax=ax1, color='green', marker='^', markersize=50, alpha=0.8, label='燃气电厂')
        if lng_terminals is not None:
            lng_terminals.plot(ax=ax1, color='red', marker='H', markersize=100, alpha=0.8, label='LNG接收站')
        if gas_storage is not None:
            gas_storage.plot(ax=ax1, color='blue', marker='X', markersize=80, alpha=0.8, label='储气设施')
        if gas_pipelines is not None:
            gas_pipelines.plot(ax=ax1, color='orange', linewidth=2, alpha=0.8, label='天然气管道')
        
        ax1.legend()
        ax1.set_title('中国天然气产业链设施分布', fontsize=14, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        
        # 2. 燃气电厂装机容量分析（如果有容量数据）
        if gas_plants is not None and 'Capacity__MW_' in gas_plants.columns:
            capacity_data = gas_plants['Capacity__MW_'].dropna()
            if len(capacity_data) > 0:
                ax2.hist(capacity_data, bins=20, color='green', alpha=0.7, edgecolor='black')
                ax2.set_title('燃气电厂装机容量分布', fontsize=14, fontweight='bold')
                ax2.set_xlabel('装机容量 (MW)')
                ax2.set_ylabel('电厂数量')
                ax2.grid(True, alpha=0.3)
        
        # 3. 省份分布
        gas_facilities_by_province = {}
        
        for name, data in [('燃气电厂', gas_plants), ('LNG接收站', lng_terminals), 
                          ('储气设施', gas_storage)]:
            if data is not None and 'Province' in data.columns:
                province_counts = data['Province'].value_counts().head(10)
                gas_facilities_by_province[name] = province_counts
        
        if gas_facilities_by_province:
            x_pos = np.arange(len(gas_facilities_by_province))
            width = 0.25
            
            for i, (facility_type, counts) in enumerate(gas_facilities_by_province.items()):
                if len(counts) > 0:
                    ax3.bar([p + width*i for p in x_pos[:len(counts)]], 
                           counts.values, width, label=facility_type, alpha=0.8)
            
            ax3.set_title('天然气设施省份分布(前10)', fontsize=14, fontweight='bold')
            ax3.set_xlabel('省份')
            ax3.set_ylabel('设施数量')
            ax3.set_xticks([p + width for p in x_pos])
            if len(gas_facilities_by_province) > 0:
                first_data = list(gas_facilities_by_province.values())[0]
                ax3.set_xticklabels(first_data.index, rotation=45, ha='right')
            ax3.legend()
            ax3.grid(True, alpha=0.3)
        
        # 4. 天然气设施统计
        ng_stats = []
        for name, data in [('燃气电厂', gas_plants), ('LNG接收站', lng_terminals), 
                          ('天然气管道', gas_pipelines), ('储气设施', gas_storage)]:
            if data is not None:
                ng_stats.append({'设施类型': name, '数量': len(data)})
        
        if ng_stats:
            df_ng = pd.DataFrame(ng_stats)
            bars = ax4.bar(df_ng['设施类型'], df_ng['数量'], 
                          color=['green', 'red', 'orange', 'blue'], alpha=0.8)
            ax4.set_title('天然气相关设施数量统计', fontsize=14, fontweight='bold')
            ax4.set_ylabel('数量')
            
            # 添加数值标签
            for bar in bars:
                height = bar.get_height()
                ax4.text(bar.get_x() + bar.get_width()/2., height + height*0.01,
                        f'{int(height)}', ha='center', va='bottom')
        
        plt.tight_layout()
        plt.savefig(self.output_dir / '08_天然气产业链专题分析.png', 
                   dpi=300, bbox_inches='tight')
        plt.show()
    
    def run_visualization(self):
        """运行完整的可视化流程"""
        print("=" * 60)
        print("开始中国能源基础设施GIS数据可视化")
        print("=" * 60)
        
        try:
            # 1. 创建总览地图
            self.create_overview_map()
            
            # 2. 创建分类地图
            self.create_category_maps()
            
            # 3. 创建统计图表
            self.create_statistics_charts()
            
            # 4. 创建天然气专题分析
            self.create_natural_gas_analysis()
            
            print("\n" + "=" * 60)
            print("✓ 可视化完成！所有图表已保存到 visualization_results 文件夹")
            print("=" * 60)
            
        except Exception as e:
            print(f"✗ 可视化过程中出现错误: {e}")

def main():
    """主函数"""
    # 创建可视化器
    visualizer = EnergyInfrastructureVisualizer()
    
    # 运行可视化
    visualizer.run_visualization()

if __name__ == "__main__":
    main()
