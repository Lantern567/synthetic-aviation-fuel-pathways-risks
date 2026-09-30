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
                ('GTL-BH', {
                    'full_name': 'GTL-BH',
                    'solution_pattern': str(project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/byproduct_hydrogen/byproduct_hydrogen/two_step/complete_solution_*.json')
                }),
                ('GTL-GH', {
                    'full_name': 'GTL-GH',
                    'solution_pattern': str(project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/complete_solution_*.json')
                }),
                ('GTL', {
                    'full_name': 'GTL',
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

        # 12个成本分类配置 - 使用柔和的Pastel色系 (参考图风格)
        self.cost_categories = OD([
            ('Facility Inv.', {
                'keys': ['facility_investment_cost'],
                'color': '#8DD3C7'  # Teal
            }),
            ('Storage Equip.', {
                'keys': ['storage_equipment_cost', 'h2_storage_investment'],
                'color': '#FFFFB3'  # Light Yellow
            }),
            ('Electrolyzer', {
                'keys': ['electrolyzer_investment_cost'],
                'color': '#BEBADA'  # Pastel Purple
            }),
            ('DAC Equip.', {
                'keys': ['dac_facility_investment'],
                'color': '#FB8072'  # Salmon
            }),
            ('Raw Material', {
                'keys': ['coal_purchase_cost', 'coal_gasification_cost', 'natural_gas_cost', 'dac_capture_cost'],
                'color': '#80B1D3'  # Pastel Blue
            }),
            ('CO2 Capture', {
                'keys': ['co2_capture_cost'],
                'color': '#FDB462'  # Pastel Orange
            }),
            ('Production', {
                'keys': ['production_cost', 'facility_operation_cost'],
                'color': '#B3DE69'  # Pastel Green
            }),
            ('FT Production', {
                'keys': ['ft_production_cost'],
                'color': '#FCCDE5'  # Pastel Pink
            }),
            ('Catalyst', {
                'keys': ['catalyst_cost'],
                'color': '#D9D9D9'  # Light Grey
            }),
            ('Electricity', {
                'keys': ['electricity_cost'],
                'color': '#BC80BD'  # Pastel Violet
            }),
            ('Transport', {
                'keys': ['transport_operation_cost', 'ng_transport_operation', 'hydrogen_pipeline_operation', 'co2_pipeline_transport_cost'],
                'color': '#CCEBC5'  # Pale Green
            }),
            ('Storage Op.', {
                'keys': ['storage_operation_cost', 'h2_storage_operation'],
                'color': '#FFED6F'  # Soft Yellow
            }),
        ])

        # 分组颜色 - 参考图外圈颜色
        self.group_colors = {
            'Grey': '#9E9E9E',   # Grey
            'Blue': '#5C9BD5',   # Soft Blue
            'Green': '#70AD47'   # Soft Green
        }

        self.data = {}
        
    def draw_curved_text(self, ax, text, radius, center_angle, fontsize=20, color='#333333'):
        """
        绘制沿圆弧弯曲的文字
        """
        # 规范化中心角度到 0-2pi
        center_angle = center_angle % (2 * np.pi)
        
        # 粗调系数 - Percentage图通常半径是固定的(~100+something), 但坐标系是0-100? No, polar coordinates.
        # Check radius range:
        # INNER_RADIUS=35, BAR=100, RING=12, GAP=3. Total ~150.
        # radius will be around 160-170.
        # Use same heuristic
        
        char_angle_width = 0.06 * (20 / radius) * fontsize * 0.8 # Spacing adjusted to 0.06 as requested
        
        total_angle = len(text) * char_angle_width
        
        # Dynamic Flip for readability:
        is_flipped = False
        if 90 < np.degrees(center_angle) < 270:
            is_flipped = True
            
        if is_flipped:
            start_angle = center_angle - total_angle / 2
            char_step = char_angle_width 
            base_rotation = 90
        else:
            start_angle = center_angle + total_angle / 2
            char_step = -char_angle_width
            base_rotation = -90
            
        curr_angle = start_angle
        
        for char in text:
            deg = np.degrees(curr_angle)
            rotation = deg + base_rotation
            
            ax.text(
                curr_angle, radius, char,
                ha='center', va='center',
                fontsize=fontsize,
                fontweight='normal',
                color=color,
                rotation=rotation,
                rotation_mode='anchor'
            )
            curr_angle += char_step

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
        fig, ax = plt.subplots(figsize=(16, 16), subplot_kw=dict(projection='polar'))
        # === 几何参数 (Scaled to match Stacked Chart Dimensions) ===
        # Target 'Max Cost' equivalent = 400 (approx matching the other chart)
        EQUIV_MAX_COST = 400.0
        scale_factor = EQUIV_MAX_COST / 100.0 # 4.0
        
        # 使用与 Stacked Chart 相同的比例系数
        INNER_RADIUS = EQUIV_MAX_COST * 0.35      # 140
        BAR_LIMIT = EQUIV_MAX_COST                # 400
        RING_GAP = EQUIV_MAX_COST * 0.02          # 8
        RING_WIDTH = EQUIV_MAX_COST * 0.12        # 48
        LABEL_GAP = RING_WIDTH * 0.5              # 24
        
        # 径向位置计算
        outer_ring_start = INNER_RADIUS + BAR_LIMIT + RING_GAP
        outer_ring_end = outer_ring_start + RING_WIDTH
        label_radius = outer_ring_end + LABEL_GAP

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
        
        # 记录每组的起始和结束角度（用于画外圈）
        group_angular_ranges = {}
        
        current_group = None
        group_start_angle = current_angle
        
        temp_angles = [] # 临时存储当前组的角度

        for i, (label, group) in enumerate(zip(labels, groups)):
            # 检测新组
            if current_group is not None and group != current_group:
                # 记录上一组的范围
                group_end_angle = current_angle + angle_per_scenario/2 # 修正为最后一个柱子的右边缘
                group_start_actual = group_start_angle + angle_per_scenario/2 # 第一个柱子的左边缘
                
                # 简单的范围计算：覆盖该组所有柱子
                # max角度(左) 到 min角度(右) (注意方向是逆时针还是顺时针，这里current_angle在减小)
                # start_angle是较大的值，end_angle是较小的值
                
                # 记录上一组范围
                # 此时 temp_angles 包含上一组的所有中心角度
                max_ang = max(temp_angles) + angle_per_scenario/2
                min_ang = min(temp_angles) - angle_per_scenario/2
                group_angular_ranges[current_group] = (min_ang, max_ang)
                temp_angles = []

                group_boundaries.append(current_angle + angle_per_scenario / 2)
                current_angle -= gap_angle  # 添加组间间隙
                group_start_angle = current_angle # 更新由于gap产生的新起点

            if current_group != group:
                current_group = group
                # 开始新组，重新记录第一根柱子导致的起始边缘?
                # 实际上上面已经处理了gap，这里只是重置状态
            
            angles.append(current_angle)
            temp_angles.append(current_angle)
            
            current_angle -= angle_per_scenario

        # 处理最后一组
        if temp_angles:
             max_ang = max(temp_angles) + angle_per_scenario/2
             min_ang = min(temp_angles) - angle_per_scenario/2
             group_angular_ranges[current_group] = (min_ang, max_ang)

        # 添加最后一个边界（回到起点）
        group_boundaries.append(current_angle + angle_per_scenario / 2)

        angles = np.array(angles)

        # 柱子宽度
        width = angle_per_scenario * 0.95 # 稍微加宽一点

        # === 绘制堆叠柱状图 ===
        bottom = np.zeros(n_scenarios) + INNER_RADIUS # 每个柱子从INNER_RADIUS开始

        for cat_name, cat_config in self.cost_categories.items():
            # Scale data values to match the new BAR_LIMIT (300)
            # Original percentage is 0-100. New max is 300.
            # So multiply percentage by scale_factor
            values = np.array(cost_data[cat_name]) * scale_factor
            ax.bar(
                angles,
                values,
                width=width,
                bottom=bottom,
                label=cat_name,
                color=cat_config['color'],
                edgecolor='white',
                linewidth=0.3,
                alpha=0.9
            )
            bottom += values

        # === 绘制外圈 (Group Ring) ===
        for group_name, (min_ang, max_ang) in group_angular_ranges.items():
            # 计算中心和跨度
            center = (min_ang + max_ang) / 2
            span = max_ang - min_ang
            
            # 使用bar绘制弧形段
            ax.bar(
                x=center,
                height=RING_WIDTH,
                bottom=outer_ring_start,
                width=span,
                color=self.group_colors.get(group_name, '#999999'),
                alpha=0.8,
                edgecolor='none'
            )

        # === 设置径向范围和样式 ===
        # 范围包含：内孔 + 数据(100) + 间隙 + 外圈 + 标签留白
        ax.set_ylim(0, label_radius + 15)

        # 设置网格线 - 虚线
        # 只显示数据区域的网格 (20, 40, 60, 80, 100)
        # 实际位置 = (value * scale_factor) + INNER_RADIUS
        grid_values = [20, 40, 60, 80, 100]
        actual_grid_pos = [(v * scale_factor) + INNER_RADIUS for v in grid_values]
        
        ax.set_yticks(actual_grid_pos)
        ax.set_yticklabels([]) # 不使用默认标签
        
        # 手动画虚线网格
        ax.yaxis.grid(True, linestyle='--', alpha=0.5, color='#aaaaaa', linewidth=0.8, dashes=(4, 4))
        ax.xaxis.grid(False) # 不要径向的线
        
        # 隐藏默认角度刻度
        ax.set_xticks([])
        ax.spines['polar'].set_visible(False) # 隐藏最外圈的大圆

        # === 添加垂直轴刻度标签 ===
        # 在顶部开口处或第一个间隙处显示
        # 找最大的gap位置显示刻度
        tick_angle = np.pi / 2 # 默认顶部
        
        for val, radius in zip(grid_values, actual_grid_pos):
            ax.text(
                tick_angle, radius, f"{val}",
                ha='center', va='center',
                fontsize=22, color='#666666',
                fontweight='bold',
                bbox=dict(facecolor='white', edgecolor='none', alpha=0.7, pad=0.5)
            )

        # === 添加Y轴标题 "Species threatened (%)" -> "Cost Breakdown (%)"
        ax.text(
            0, 0, 'Cost\nBreakdown\n(%)',
            ha='center', va='center',
            fontsize=24, color='#333333',
            fontweight='bold',
            rotation=0,
            rotation_mode='anchor',
            bbox=dict(facecolor='white', edgecolor='none', alpha=0.8)
        )

        # === 添加场景标签 (最外层) -> 使用弯曲文字
        for angle, label in zip(angles, labels):
             self.draw_curved_text(ax, label, label_radius, angle, fontsize=24, color='#333333')




        # Add labels to outer ring (Correct logic)
        for group_name, (min_ang, max_ang) in group_angular_ranges.items():
            center_angle = (min_ang + max_ang) / 2
            
            deg = np.degrees(center_angle)
            if deg < 0: deg += 360
            
            rotation = deg - 90
            if 90 < deg < 270:
                rotation += 180

            ax.text(
                center_angle, outer_ring_start + RING_WIDTH/2, group_name,
                ha='center', va='center',
                fontsize=28, fontweight='bold',
                color='white',
                rotation=rotation,
                rotation_mode='anchor'
            )

        # === 图例 ===
        # 图例1：Cost Components (Right Side)
        handles, _ = ax.get_legend_handles_labels()
        cost_handles = handles[:len(self.cost_categories)]
        cost_labels = list(self.cost_categories.keys())
        
        legend1 = ax.legend(
            cost_handles, cost_labels,
            loc='upper left',
            bbox_to_anchor=(1.15, 1.0), # Right side
            fontsize=24,
            title='Cost Components',
            title_fontsize=26,
            frameon=False,
            labelspacing=0.8
        )
        legend1.get_title().set_fontweight('bold')
        # 移除 Group Legend

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
