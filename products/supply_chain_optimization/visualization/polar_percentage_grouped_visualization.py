"""
分组百分比极坐标堆叠柱状图可视化脚本
Grouped Percentage Polar Stacked Bar Chart Visualization Script

功能 | Features:
- 为13个SAF供应链优化场景创建分组百分比极坐标堆叠柱状图
- 按Grey/Blue/Green三组进行分组显示
- 成本组成归一化为百分比（100%）

作者 | Author: Claude Code
创建时间 | Created: 2026-01-06
"""

import json
import glob
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, OrderedDict
from collections import OrderedDict as OD
import logging

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib import rcParams
from matplotlib.patches import Patch, Arc
import matplotlib.patches as mpatches

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class GroupedPolarPercentageVisualizer:
    """分组百分比极坐标堆叠柱状图可视化器"""

    def __init__(self, output_dir: str = None):
        """初始化可视化器"""
        if output_dir is None:
            base_dir = Path(__file__).parent.parent.parent.parent
            output_dir = base_dir / "products" / "supply_chain_optimization" / "visualization" / "results"

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = self.output_dir / f"polar_grouped_{timestamp}"
        self.session_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"输出目录: {self.session_dir}")

        project_root = Path(__file__).parent.parent.parent.parent

        # 定义场景映射：新标签 -> 数据源路径
        # 按Grey/Blue/Green三组组织
        self.scenario_groups = OD([
            ('Grey', OD([
                ('CTL', {
                    'full_name': 'Coal-to-Liquids Baseline',
                    'solution_pattern': str(project_root / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/complete_solution_*.json')
                }),
                ('CTL-BH', {
                    'full_name': 'Coal-to-Liquids with By-product H2',
                    'solution_pattern': str(project_root / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/byproduct_hydrogen/complete_solution_*.json')
                }),
            ])),
            ('Blue', OD([
                ('CCU-BH-MTJ', {
                    'full_name': 'CCU with By-product H2 – MTJ',
                    'solution_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/two_step/complete_solution_*.json')
                }),
                ('CCU-BH-FT', {
                    'full_name': 'CCU with By-product H2 – FT',
                    'solution_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/one_step/complete_solution_*.json')
                }),
                ('DAC-BH-MTJ', {
                    'full_name': 'DAC with By-product H2 – MTJ',
                    'solution_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/two_step/complete_solution_*.json')
                }),
                ('DAC-BH-FT', {
                    'full_name': 'DAC with By-product H2 – FT',
                    'solution_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/one_step/complete_solution_*.json')
                }),
                ('GTL-BH-MTJ', {
                    'full_name': 'GTL with By-product H2 – MTJ',
                    'solution_pattern': str(project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/byproduct_hydrogen/byproduct_hydrogen/two_step/complete_solution_*.json')
                }),
                ('GTL-GH-MTJ', {
                    'full_name': 'GTL with Green H2 – MTJ',
                    'solution_pattern': str(project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/complete_solution_*.json')
                }),
                ('GTL-GH-FT', {
                    'full_name': 'GTL with Green H2 – FT',
                    'solution_pattern': str(project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/ft_one_step/complete_solution_*.json')
                }),
            ])),
            ('Green', OD([
                ('DAC-GH-MTJ', {
                    'full_name': 'DAC with Green H2 – MTJ',
                    'solution_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/two_step/complete_solution_*.json')
                }),
                ('DAC-GH-FT', {
                    'full_name': 'DAC with Green H2 – FT',
                    'solution_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/one_step/complete_solution_*.json')
                }),
                ('CCU-GH-MTJ', {
                    'full_name': 'CCU with Green H2 – MTJ',
                    'solution_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/two_step/complete_solution_*.json')
                }),
                ('CCU-GH-FT', {
                    'full_name': 'CCU with Green H2 – FT',
                    'solution_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/one_step/complete_solution_*.json')
                }),
            ])),
        ])

        # 12个成本分类配置
        self.cost_categories = OD([
            ('Facility Inv.', {
                'keys': ['facility_investment_cost'],
                'color': '#1f77b4'
            }),
            ('Storage Equip.', {
                'keys': ['storage_equipment_cost', 'h2_storage_investment'],
                'color': '#2ca02c'
            }),
            ('Electrolyzer', {
                'keys': ['electrolyzer_investment_cost'],
                'color': '#9467bd'
            }),
            ('DAC Equip.', {
                'keys': ['dac_facility_investment'],
                'color': '#17becf'
            }),
            ('Raw Material', {
                'keys': ['coal_purchase_cost', 'coal_gasification_cost', 'natural_gas_cost', 'dac_capture_cost'],
                'color': '#ff7f0e'
            }),
            ('CO2 Capture', {
                'keys': ['co2_capture_cost'],
                'color': '#bcbd22'
            }),
            ('Production', {
                'keys': ['production_cost', 'facility_operation_cost'],
                'color': '#e377c2'
            }),
            ('FT Production', {
                'keys': ['ft_production_cost'],
                'color': '#7f7f7f'
            }),
            ('Catalyst', {
                'keys': ['catalyst_cost'],
                'color': '#8c564b'
            }),
            ('Electricity', {
                'keys': ['electricity_cost'],
                'color': '#d62728'
            }),
            ('Transport', {
                'keys': ['transport_operation_cost', 'ng_transport_operation', 'hydrogen_pipeline_operation', 'co2_pipeline_transport_cost'],
                'color': '#aec7e8'
            }),
            ('Storage Op.', {
                'keys': ['storage_operation_cost', 'h2_storage_operation'],
                'color': '#98df8a'
            }),
        ])

        # 分组颜色
        self.group_colors = {
            'Grey': '#808080',
            'Blue': '#4169E1',
            'Green': '#228B22'
        }

        self.data = {}

    def load_data(self):
        """加载所有场景数据"""
        logger.info("=" * 80)
        logger.info("加载场景数据")
        logger.info("=" * 80)

        for group_name, scenarios in self.scenario_groups.items():
            logger.info(f"\n--- {group_name} 组 ---")
            for scenario_label, config in scenarios.items():
                logger.info(f"加载: {scenario_label} ({config['full_name']})")

                solution_files = sorted(glob.glob(config['solution_pattern']), reverse=True)

                if not solution_files:
                    logger.warning(f"  ⚠ 未找到文件: {config['solution_pattern']}")
                    continue

                solution_path = Path(solution_files[0])
                with open(solution_path, 'r', encoding='utf-8') as f:
                    solution_data = json.load(f)

                self.data[scenario_label] = {
                    'solution': solution_data,
                    'group': group_name,
                    'config': config
                }

                total_cost = solution_data.get('cost_breakdown', {}).get('total_cost_excluding_shortage', 0) / 1e9
                logger.info(f"  ✓ 总成本: {total_cost:.2f} 亿元")

        logger.info(f"\n成功加载 {len(self.data)} 个场景")

    def extract_percentage_data(self) -> Tuple[List[str], List[str], Dict[str, List[float]]]:
        """提取百分比数据"""
        labels = []
        groups = []
        cost_data = {cat: [] for cat in self.cost_categories.keys()}

        for group_name, scenarios in self.scenario_groups.items():
            for scenario_label in scenarios.keys():
                if scenario_label not in self.data:
                    continue

                labels.append(scenario_label)
                groups.append(group_name)

                cost_breakdown = self.data[scenario_label]['solution'].get('cost_breakdown', {})

                # 计算各成本类别的绝对值
                category_values = {}
                total = 0
                for cat, cat_config in self.cost_categories.items():
                    val = sum(cost_breakdown.get(key, 0) for key in cat_config['keys'])
                    category_values[cat] = val
                    total += val

                # 转换为百分比
                for cat in self.cost_categories.keys():
                    if total > 0:
                        percentage = (category_values[cat] / total) * 100
                    else:
                        percentage = 0
                    cost_data[cat].append(percentage)

        return labels, groups, cost_data

    def create_grouped_polar_chart(self):
        """创建分组百分比极坐标堆叠柱状图 - 参考图样式"""
        logger.info("\n生成分组百分比极坐标堆叠柱状图（参考图样式）...")

        # 配置字体
        plt.rcParams['font.family'] = ['Times New Roman', 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False

        # 提取数据
        labels, groups, cost_data = self.extract_percentage_data()
        n_scenarios = len(labels)

        if n_scenarios == 0:
            logger.error("没有可用的场景数据")
            return

        # 创建图形
        fig, ax = plt.subplots(figsize=(14, 14), subplot_kw=dict(projection='polar'))
        fig.patch.set_facecolor('white')
        ax.set_facecolor('white')

        # 计算角度 - 按组分配，组间留间隙
        gap_angle = np.pi / 12  # 组间间隙 (15度)
        total_gap = gap_angle * 3  # 3个间隙
        available_angle = 2 * np.pi - total_gap  # 可用角度

        # 按场景数量分配角度
        angle_per_scenario = available_angle / n_scenarios

        # 计算每个场景的角度位置
        angles = []
        group_boundaries = []  # 记录组边界角度
        current_angle = np.pi / 2  # 从顶部开始

        current_group = None
        for i, (label, group) in enumerate(zip(labels, groups)):
            if current_group is not None and group != current_group:
                group_boundaries.append(current_angle + angle_per_scenario / 2)
                current_angle -= gap_angle  # 添加组间间隙

            angles.append(current_angle)
            current_angle -= angle_per_scenario
            current_group = group

        # 添加最后一个边界（回到起点）
        group_boundaries.append(current_angle + angle_per_scenario / 2)

        angles = np.array(angles)

        # 柱子宽度
        width = angle_per_scenario * 0.9

        # 绘制堆叠柱状图
        bottom = np.zeros(n_scenarios)

        for cat_name, cat_config in self.cost_categories.items():
            values = np.array(cost_data[cat_name])
            ax.bar(
                angles,
                values,
                width=width,
                bottom=bottom,
                label=cat_name,
                color=cat_config['color'],
                edgecolor='white',
                linewidth=0.5,
                alpha=0.95
            )
            bottom += values

        # 设置径向范围
        ax.set_ylim(0, 120)

        # 隐藏默认的径向刻度标签
        ax.set_yticks([25, 50, 75, 100])
        ax.set_yticklabels([])

        # 设置网格线 - 灰色同心圆
        ax.yaxis.grid(True, linestyle='-', alpha=0.5, color='#cccccc', linewidth=0.8)
        ax.xaxis.grid(False)

        # 隐藏默认角度刻度
        ax.set_xticks([])

        # 只在顶部显示刻度数字（垂直排列）
        tick_angle = np.pi / 2  # 顶部位置
        for tick_val in [25, 50, 75, 100]:
            ax.text(
                tick_angle, tick_val, str(tick_val),
                ha='center', va='bottom',
                fontsize=8, color='#666666'
            )

        # 添加轴标签（垂直书写）- "Species threatened (%)" 改为 "Cost breakdown (%)"
        ax.text(
            tick_angle + 0.08, 55, 'Cost\nbreakdown\n(%)',
            ha='left', va='center',
            fontsize=9, color='#666666',
            linespacing=0.9
        )

        # 添加场景标签 - 沿径向方向旋转
        label_radius = 108
        for angle, label in zip(angles, labels):
            # 计算旋转角度（使标签沿径向方向）
            rotation_deg = np.degrees(angle) - 90

            # 调整旋转角度，使文字始终可读
            if -90 < rotation_deg < 90:
                rotation = rotation_deg
                ha = 'left'
            else:
                rotation = rotation_deg + 180
                ha = 'right'

            ax.text(
                angle, label_radius, label,
                ha=ha, va='center',
                fontsize=9,
                fontweight='normal',
                fontstyle='italic',
                color='#333333',
                rotation=rotation,
                rotation_mode='anchor'
            )

        # 计算分组标签位置（在组的中心，靠近内侧）
        group_label_radius = 18  # 靠近中心
        group_info = {}

        current_group = None
        group_start_idx = 0
        for i, group in enumerate(groups):
            if group != current_group:
                if current_group is not None:
                    # 计算上一组的中心角度
                    group_end_idx = i - 1
                    center_angle = (angles[group_start_idx] + angles[group_end_idx]) / 2
                    group_info[current_group] = {
                        'center': center_angle,
                        'start': angles[group_start_idx],
                        'end': angles[group_end_idx]
                    }
                group_start_idx = i
                current_group = group

        # 处理最后一组
        if current_group is not None:
            center_angle = (angles[group_start_idx] + angles[-1]) / 2
            group_info[current_group] = {
                'center': center_angle,
                'start': angles[group_start_idx],
                'end': angles[-1]
            }

        # 绘制分组标签 - 沿弧线方向书写
        for group_name, info in group_info.items():
            center_angle = info['center']
            # 计算旋转角度（使标签沿弧线方向）
            rotation_deg = np.degrees(center_angle) - 90

            if -90 < rotation_deg < 90:
                rotation = rotation_deg
            else:
                rotation = rotation_deg + 180

            ax.text(
                center_angle, group_label_radius, group_name,
                ha='center', va='center',
                fontsize=11, fontweight='bold',
                color='#333333',
                rotation=rotation,
                rotation_mode='anchor'
            )

        # 绘制分组分隔弧线
        for boundary_angle in group_boundaries:
            # 绘制从中心到外侧的灰色分隔线
            ax.plot(
                [boundary_angle, boundary_angle],
                [0, 105],
                color='#aaaaaa',
                linewidth=1,
                linestyle='-',
                alpha=0.6
            )

        # 设置方向
        ax.set_theta_offset(0)
        ax.set_theta_direction(-1)

        # 添加图例 - 右上角
        legend = ax.legend(
            loc='upper right',
            bbox_to_anchor=(1.32, 1.02),
            fontsize=9,
            title='Cost Components',
            title_fontsize=10,
            frameon=True,
            fancybox=False,
            edgecolor='#666666',
            framealpha=1.0
        )
        legend.get_title().set_fontweight('bold')

        plt.tight_layout()

        # 保存图片
        output_path = self.session_dir / "polar_grouped_percentage_chart.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
        logger.info(f"  ✓ 保存图片: {output_path}")

        # 保存最新版本
        root_output = self.output_dir / "polar_grouped_percentage_chart_latest.png"
        plt.savefig(root_output, dpi=300, bbox_inches='tight', facecolor='white')
        logger.info(f"  ✓ 保存最新版本: {root_output}")

        plt.close()

        return output_path

    def run_all_visualizations(self):
        """运行所有可视化"""
        logger.info("\n" + "=" * 80)
        logger.info("开始生成可视化")
        logger.info("=" * 80)

        self.create_grouped_polar_chart()

        logger.info("\n" + "=" * 80)
        logger.info("✓ 所有可视化生成完成")
        logger.info(f"✓ 输出目录: {self.session_dir}")
        logger.info("=" * 80)


def main():
    """主函数"""
    logger.info("=" * 80)
    logger.info("分组百分比极坐标堆叠柱状图可视化脚本")
    logger.info("Grouped Percentage Polar Stacked Bar Chart")
    logger.info("=" * 80)

    visualizer = GroupedPolarPercentageVisualizer()
    visualizer.load_data()

    if len(visualizer.data) < 2:
        logger.error(f"✗ 数据不足：只找到 {len(visualizer.data)} 个场景的数据")
        return

    visualizer.run_all_visualizations()

    logger.info("\n✓ 程序执行成功")


if __name__ == "__main__":
    main()
