#!/usr/bin/env python3
"""
氢气运输路径可视化专用模块
Hydrogen Transport Route Visualization Module

作者: AI Assistant
日期: 2025-09-20
功能: 集成氢气管道距离计算和可视化功能
"""

import sys
import json
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path
from typing import List, Tuple, Dict, Optional
import logging

# 添加项目路径
current_dir = Path(__file__).parent
sys.path.append(str(current_dir))
sys.path.append(str(current_dir.parent.parent.parent / "gis_energy_mapping" / "gis_data_scraper"))

from .hydrogen_pipeline_distance_calculator import HydrogenPipelineDistanceCalculator, PipelineRoute, PipelineRouteNotFoundError
from ...gis_energy_mapping.gis_data_scraper.visualize_energy_infrastructure import EnergyInfrastructureVisualizer

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HydrogenTransportVisualizer:
    """氢气运输路径可视化器"""

    def __init__(self, gis_data_path: Optional[str] = None):
        """
        初始化氢气运输可视化器

        Args:
            gis_data_path: GIS数据路径，如果不指定将自动推断
        """
        if gis_data_path is None:
            # 自动推断GIS数据路径
            gis_data_path = current_dir.parent.parent.parent / "gis_energy_mapping" / "gis_data_scraper" / "scraped_gis_data"

        self.gis_data_path = Path(gis_data_path)
        self.output_dir = current_dir / "visualization_results"
        self.output_dir.mkdir(exist_ok=True)

        # 初始化氢气管道距离计算器
        self.pipeline_calculator = HydrogenPipelineDistanceCalculator(
            gis_data_path=str(self.gis_data_path),
            enable_cache=False  # 禁用数据库缓存（查询比计算更慢）
        )

        # 初始化能源基础设施可视化器
        self.energy_visualizer = EnergyInfrastructureVisualizer(
            data_dir=str(self.gis_data_path)
        )

        # 存储计算的路径
        self.calculated_routes = []

    def calculate_and_visualize_route(self, start_lat: float, start_lon: float,
                                    end_lat: float, end_lon: float,
                                    start_name: str = "起点", end_name: str = "终点",
                                    max_access_distance_km: float = 100.0) -> Optional[PipelineRoute]:
        """
        计算并可视化单条氢气运输路径

        Args:
            start_lat, start_lon: 起点坐标
            end_lat, end_lon: 终点坐标
            start_name: 起点名称
            end_name: 终点名称
            max_access_distance_km: 最大接入距离

        Returns:
            PipelineRoute对象，如果失败返回None
        """
        try:
            # 计算路径
            route = self.pipeline_calculator.calculate_pipeline_distance(
                start_lat, start_lon, end_lat, end_lon, max_access_distance_km
            )

            route_name = f"{start_name}_to_{end_name}"
            logger.info(f"成功计算路径 {route_name}: {route.total_distance_km:.1f}km")

            # 导出为GeoJSON格式
            geojson_data = self.pipeline_calculator.export_route_to_geojson(route, route_name)

            # 可视化
            self.energy_visualizer.visualize_hydrogen_transport_routes(
                geojson_data, f"氢气运输路径_{route_name}"
            )

            # 保存GeoJSON文件
            geojson_file = self.output_dir / f"hydrogen_route_{route_name}.geojson"
            self.pipeline_calculator.save_route_geojson(route, str(geojson_file), route_name)

            # 保存路径信息
            self.calculated_routes.append((route, route_name))

            return route

        except PipelineRouteNotFoundError as e:
            logger.error(f"无法找到路径 {start_name} -> {end_name}: {e}")
            return None

        except Exception as e:
            logger.error(f"路径计算失败 {start_name} -> {end_name}: {e}")
            return None

    def calculate_multiple_routes(self, route_specifications: List[Dict]) -> List[Tuple[PipelineRoute, str]]:
        """
        计算多条氢气运输路径

        Args:
            route_specifications: 路径规格列表，每项包含start_lat, start_lon, end_lat, end_lon, start_name, end_name

        Returns:
            成功计算的路径列表
        """
        successful_routes = []

        for spec in route_specifications:
            try:
                route = self.calculate_and_visualize_route(
                    spec['start_lat'], spec['start_lon'],
                    spec['end_lat'], spec['end_lon'],
                    spec.get('start_name', '起点'),
                    spec.get('end_name', '终点'),
                    spec.get('max_access_distance_km', 100.0)
                )

                if route:
                    route_name = f"{spec.get('start_name', '起点')}_to_{spec.get('end_name', '终点')}"
                    successful_routes.append((route, route_name))

            except Exception as e:
                logger.error(f"计算路径失败: {e}")
                continue

        return successful_routes

    def visualize_multiple_routes(self, routes: Optional[List[Tuple[PipelineRoute, str]]] = None):
        """
        可视化多条氢气运输路径

        Args:
            routes: 路径列表，如果不指定则使用已计算的路径
        """
        if routes is None:
            routes = self.calculated_routes

        if not routes:
            logger.warning("没有可用的路径进行可视化")
            return

        # 导出所有路径为GeoJSON
        geojson_data = self.pipeline_calculator.export_multiple_routes_to_geojson(routes)

        # 可视化
        self.energy_visualizer.visualize_hydrogen_transport_routes(
            geojson_data, f"氢气运输网络_{len(routes)}条路径"
        )

        # 保存综合GeoJSON文件
        geojson_file = self.output_dir / f"hydrogen_transport_network_{len(routes)}_routes.geojson"
        with open(geojson_file, 'w', encoding='utf-8') as f:
            json.dump(geojson_data, f, ensure_ascii=False, indent=2)

        logger.info(f"多路径可视化完成，共{len(routes)}条路径")

    def create_route_statistics_report(self, routes: Optional[List[Tuple[PipelineRoute, str]]] = None):
        """
        创建路径统计报告

        Args:
            routes: 路径列表，如果不指定则使用已计算的路径
        """
        if routes is None:
            routes = self.calculated_routes

        if not routes:
            logger.warning("没有可用的路径进行统计")
            return

        # 收集统计数据
        stats_data = []
        for route, route_name in routes:
            stats_data.append({
                '路径名称': route_name,
                '总距离(km)': round(route.total_distance_km, 2),
                '接入距离(km)': round(route.access_distance_km, 2),
                '管道距离(km)': round(route.pipeline_distance_km, 2),
                '离开距离(km)': round(route.egress_distance_km, 2),
                '使用管道类型': ', '.join(route.pipeline_types_used),
                '计算方法': route.calculation_method
            })

        df = pd.DataFrame(stats_data)

        # 创建统计图表
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))

        # 1. 总距离分布
        df['总距离(km)'].hist(bins=10, ax=ax1, alpha=0.7, color='skyblue')
        ax1.set_title('氢气运输路径距离分布', fontsize=14, fontweight='bold')
        ax1.set_xlabel('距离(km)')
        ax1.set_ylabel('路径数量')
        ax1.grid(True, alpha=0.3)

        # 2. 距离组成分析
        distance_components = ['接入距离(km)', '管道距离(km)', '离开距离(km)']
        avg_components = [df[col].mean() for col in distance_components]
        colors = ['orange', 'lightgreen', 'lightcoral']

        ax2.pie(avg_components, labels=distance_components, colors=colors, autopct='%1.1f%%')
        ax2.set_title('平均距离组成分析', fontsize=14, fontweight='bold')

        # 3. 管道类型使用统计
        pipeline_types = {}
        for route, _ in routes:
            for pipeline_type in route.pipeline_types_used:
                pipeline_types[pipeline_type] = pipeline_types.get(pipeline_type, 0) + 1

        if pipeline_types:
            types = list(pipeline_types.keys())
            counts = list(pipeline_types.values())
            bars = ax3.bar(types, counts, color=['brown', 'red', 'green'], alpha=0.8)
            ax3.set_title('管道类型使用统计', fontsize=14, fontweight='bold')
            ax3.set_ylabel('使用次数')

            # 添加数值标签
            for bar in bars:
                height = bar.get_height()
                ax3.text(bar.get_x() + bar.get_width()/2., height + height*0.01,
                        f'{int(height)}', ha='center', va='bottom')

        # 4. 距离效率分析
        df['接入比例'] = df['接入距离(km)'] / df['总距离(km)'] * 100
        df['管道比例'] = df['管道距离(km)'] / df['总距离(km)'] * 100
        df['离开比例'] = df['离开距离(km)'] / df['总距离(km)'] * 100

        ax4.scatter(df['总距离(km)'], df['管道比例'], alpha=0.7, s=100, color='blue')
        ax4.set_title('路径长度vs管道利用率', fontsize=14, fontweight='bold')
        ax4.set_xlabel('总距离(km)')
        ax4.set_ylabel('管道距离占比(%)')
        ax4.grid(True, alpha=0.3)

        plt.tight_layout()

        # 保存统计图表
        stats_chart_file = self.output_dir / '氢气运输路径统计分析.png'
        plt.savefig(stats_chart_file, dpi=300, bbox_inches='tight')
        plt.show()

        # 保存统计数据表
        stats_excel_file = self.output_dir / '氢气运输路径统计数据.xlsx'
        df.to_excel(stats_excel_file, index=False, encoding='utf-8')

        logger.info(f"统计报告完成: 图表保存至 {stats_chart_file}, 数据保存至 {stats_excel_file}")

    def visualize_clustered_routes(self, clustering_result, clustered_routes: Dict, destination: Tuple[float, float], destination_name: str = "目的地"):
        try:
            from .hydrogen_clustering_optimizer import ClusteringResult
            from .hydrogen_pipeline_distance_calculator import ClusteredPipelineRoute
        except ImportError:
            logger.error("无法导入聚类相关模块")
            return

        if not hasattr(clustering_result, 'clusters'):
            logger.error("clustering_result缺少clusters属性")
            return

        logger.info(f"开始可视化聚类路径: {clustering_result.total_clusters}个聚类, {clustering_result.total_noise_points}个独立点")

        fig, ax = plt.subplots(figsize=(20, 16))

        colors = plt.cm.tab20(range(20))
        color_idx = 0

        for cluster in clustering_result.clusters:
            cluster_id = cluster.cluster_id
            color = colors[color_idx % 20]
            color_idx += 1

            if cluster_id not in clustered_routes:
                continue

            route = clustered_routes[cluster_id]

            for member_name, member_coord in zip(cluster.member_locations, cluster.member_coords):
                ax.plot(member_coord[1], member_coord[0], 'o', color=color, markersize=8, label=f'聚类{cluster_id}成员' if member_name == cluster.member_locations[0] else "")

            center_coord = cluster.center_coord
            ax.plot(center_coord[1], center_coord[0], '*', color=color, markersize=20, markeredgecolor='black', markeredgewidth=2, label=f'聚类{cluster_id}中心')

            for member_coord in cluster.member_coords:
                ax.plot([member_coord[1], center_coord[1]], [member_coord[0], center_coord[0]], '--', color=color, linewidth=1.5, alpha=0.6)

            logger.info(f"聚类{cluster_id} - pipeline_access_point: {route.pipeline_access_point}, hasattr: {hasattr(route, 'pipeline_access_point')}")

            if hasattr(route, 'pipeline_access_point') and route.pipeline_access_point:
                access_point = route.pipeline_access_point
                ax.plot(access_point[1], access_point[0], 's', color=color, markersize=12, label=f'聚类{cluster_id}管道接入点')

                ax.plot([center_coord[1], access_point[1]], [center_coord[0], access_point[0]], '-', color=color, linewidth=3, alpha=0.8, label=f'聚类{cluster_id}→管道')

            cluster_label_pos = (center_coord[1] + 0.1, center_coord[0] + 0.1)
            ax.text(cluster_label_pos[0], cluster_label_pos[1], f'C{cluster_id}', fontsize=12, fontweight='bold', bbox=dict(boxstyle='round,pad=0.3', facecolor=color, alpha=0.7))

        for noise_loc, noise_coord in clustering_result.noise_points:
            ax.plot(noise_coord[1], noise_coord[0], 'x', color='red', markersize=12, markeredgewidth=3, label='独立点' if noise_loc == clustering_result.noise_points[0][0] else "")

        ax.plot(destination[1], destination[0], 'D', color='darkgreen', markersize=20, markeredgecolor='black', markeredgewidth=2, label=destination_name)

        ax.set_xlabel('经度', fontsize=14)
        ax.set_ylabel('纬度', fontsize=14)
        ax.set_title(f'氢气生产厂聚类与管道运输路径可视化\n{clustering_result.total_clusters}个聚类 + {clustering_result.total_noise_points}个独立点', fontsize=16, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.legend(loc='best', fontsize=10)

        plt.tight_layout()

        chart_file = self.output_dir / f'氢气聚类运输网络_C{clustering_result.total_clusters}_N{clustering_result.total_noise_points}.png'
        plt.savefig(chart_file, dpi=300, bbox_inches='tight')
        plt.close()

        logger.info(f"聚类路径可视化完成: {chart_file}")

        stats_data = []
        for cluster in clustering_result.clusters:
            if cluster.cluster_id in clustered_routes:
                route = clustered_routes[cluster.cluster_id]
                stats_data.append({
                    '聚类ID': cluster.cluster_id,
                    '成员数量': len(cluster.member_locations),
                    'Layer1总距离(km)': round(sum(route.layer1_distances.values()), 2),
                    'Layer2距离(km)': round(route.layer2_distance, 2),
                    'Layer3距离(km)': round(route.layer3_distance, 2),
                    '总产能(kg/h)': round(cluster.total_capacity_kg_per_hour, 2)
                })

        if stats_data:
            df = pd.DataFrame(stats_data)
            stats_file = self.output_dir / '氢气聚类运输统计.xlsx'
            df.to_excel(stats_file, index=False)
            logger.info(f"聚类统计数据已保存: {stats_file}")

    def run_demo_analysis(self):
        """运行演示分析"""
        print("=" * 60)
        print("氢气运输路径可视化演示分析")
        print("=" * 60)

        # 定义演示路径
        demo_routes = [
            {
                'start_lat': 39.9042, 'start_lon': 116.4074,
                'end_lat': 31.2304, 'end_lon': 121.4737,
                'start_name': '北京', 'end_name': '上海'
            },
            {
                'start_lat': 39.9042, 'start_lon': 116.4074,
                'end_lat': 39.3434, 'end_lon': 117.3616,
                'start_name': '北京', 'end_name': '天津'
            },
            {
                'start_lat': 23.1291, 'start_lon': 113.2644,
                'end_lat': 22.5431, 'end_lon': 114.0579,
                'start_name': '广州', 'end_name': '深圳'
            },
            {
                'start_lat': 30.5728, 'start_lon': 104.0668,
                'end_lat': 29.5647, 'end_lon': 106.5507,
                'start_name': '成都', 'end_name': '重庆'
            }
        ]

        try:
            # 计算多条路径
            successful_routes = self.calculate_multiple_routes(demo_routes)

            if successful_routes:
                # 可视化多条路径
                self.visualize_multiple_routes(successful_routes)

                # 创建统计报告
                self.create_route_statistics_report(successful_routes)

                print(f"\nOK 演示分析完成！成功计算{len(successful_routes)}条路径")
                print(f"OK 结果保存在: {self.output_dir}")
            else:
                print("ERROR 没有成功计算出任何路径")

        except Exception as e:
            logger.error(f"演示分析失败: {e}")

def main():
    """主函数"""
    # 创建可视化器
    visualizer = HydrogenTransportVisualizer()

    # 运行演示分析
    visualizer.run_demo_analysis()

if __name__ == "__main__":
    main()