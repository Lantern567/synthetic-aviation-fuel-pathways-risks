"""
极坐标堆叠柱状图可视化脚本
Polar Stacked Bar Chart Visualization Script

功能 | Features:
- 为13个SAF供应链优化场景创建极坐标堆叠柱状图
- 展示各场景的12个详细成本组成对比
- 参考学术论文风格设计

作者 | Author: Claude Code
创建时间 | Created: 2026-01-06
"""

import json
import glob
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple
import logging

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib import rcParams
from matplotlib.patches import Patch
import matplotlib.patches as mpatches

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PolarStackedBarVisualizer:
    """极坐标堆叠柱状图可视化器"""

    def __init__(self, output_dir: str = None):
        """
        初始化可视化器

        Args:
            output_dir: 输出目录
        """
        if output_dir is None:
            base_dir = Path(__file__).parent.parent.parent.parent
            output_dir = base_dir / "products" / "supply_chain_optimization" / "visualization" / "results"

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 创建带时间戳的子目录
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = self.output_dir / f"polar_chart_{timestamp}"
        self.session_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"输出目录: {self.session_dir}")

        # 获取项目根目录
        project_root = Path(__file__).parent.parent.parent.parent

        # 13个场景配置 - 命名规范化 (参考 polar_percentage_grouped_visualization.py)
        # 按 Grey -> Blue -> Green 顺序排列
        self.scenarios = {
            # === Grey Group ===
            'CTL': {
                'name_cn': '煤制氢',
                'label': 'CTL',
                'group': 'Grey',
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/complete_solution_*.json')
            },
            'CTL-BH': {
                'name_cn': '煤制氢+副产氢',
                'label': 'CTL-BH',
                'group': 'Grey',
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/byproduct_hydrogen/complete_solution_*.json')
            },

            # === Blue Group ===
            'CCU-BH-MTJ': {
                'name_cn': 'CCU副产氢-MTJ',
                'label': 'CCU-BH-MTJ',
                'group': 'Blue',
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/two_step/complete_solution_*.json')
            },
            'CCU-BH-FT': {
                'name_cn': 'CCU副产氢-FT',
                'label': 'CCU-BH-FT',
                'group': 'Blue',
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/one_step/complete_solution_*.json')
            },
            'DAC-BH-MTJ': {
                'name_cn': 'DAC副产氢-MTJ',
                'label': 'DAC-BH-MTJ',
                'group': 'Blue',
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/two_step/complete_solution_*.json')
            },
            'DAC-BH-FT': {
                'name_cn': 'DAC副产氢-FT',
                'label': 'DAC-BH-FT',
                'group': 'Blue',
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/one_step/complete_solution_*.json')
            },
            'GTL-BH': {
                'name_cn': 'GTL-BH',
                'label': 'GTL-BH',
                'group': 'Blue',
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/byproduct_hydrogen/byproduct_hydrogen/two_step/complete_solution_*.json')
            },
            'GTL-GH': {
                'name_cn': 'GTL-GH',
                'label': 'GTL-GH',
                'group': 'Blue',
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/complete_solution_*.json')
            },
            'GTL': {
                'name_cn': 'GTL',
                'label': 'GTL',
                'group': 'Blue',
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/ft_one_step/complete_solution_*.json')
            },

            # === Green Group ===
            'DAC-GH-MTJ': {
                'name_cn': 'DAC绿氢-MTJ',
                'label': 'DAC-GH-MTJ',
                'group': 'Green',
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/two_step/complete_solution_*.json')
            },
            'DAC-GH-FT': {
                'name_cn': 'DAC绿氢-FT',
                'label': 'DAC-GH-FT',
                'group': 'Green',
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/one_step/complete_solution_*.json')
            },
            'CCU-GH-MTJ': {
                'name_cn': 'CCU绿氢-MTJ',
                'label': 'CCU-GH-MTJ',
                'group': 'Green',
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/two_step/complete_solution_*.json')
            },
            'CCU-GH-FT': {
                'name_cn': 'CCU绿氢-FT',
                'label': 'CCU-GH-FT',
                'group': 'Green',
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/one_step/complete_solution_*.json')
            },
        }

        # 12个成本分类配置 - 使用柔和的Pastel色系 (参考图风格)
        self.cost_categories = {
            'Facility Inv.': {
                'name_en': 'Facility Inv.',
                'keys': ['facility_investment_cost'],
                'color': '#8DD3C7'  # Teal
            },
            'Storage Equip.': {
                'name_en': 'Storage Equip.',
                'keys': ['storage_equipment_cost', 'h2_storage_investment'],
                'color': '#FFFFB3'  # Light Yellow
            },
            'Electrolyzer': {
                'name_en': 'Electrolyzer',
                'keys': ['electrolyzer_investment_cost'],
                'color': '#BEBADA'  # Pastel Purple
            },
            'DAC Equip.': {
                'name_en': 'DAC Equip.',
                'keys': ['dac_facility_investment'],
                'color': '#FB8072'  # Salmon
            },
            'Raw Material': {
                'name_en': 'Raw Material',
                'keys': ['coal_purchase_cost', 'coal_gasification_cost', 'natural_gas_cost', 'dac_capture_cost'],
                'color': '#80B1D3'  # Pastel Blue
            },
            'CO2 Capture': {
                'name_en': 'CO2 Capture',
                'keys': ['co2_capture_cost'],
                'color': '#FDB462'  # Pastel Orange
            },
            'Production': {
                'name_en': 'Production',
                'keys': ['production_cost', 'facility_operation_cost'],
                'color': '#B3DE69'  # Pastel Green
            },
            'FT Production': {
                'name_en': 'FT Production',
                'keys': ['ft_production_cost'],
                'color': '#FCCDE5'  # Pastel Pink
            },
            'Catalyst': {
                'name_en': 'Catalyst',
                'keys': ['catalyst_cost'],
                'color': '#D9D9D9'  # Light Grey
            },
            'Electricity': {
                'name_en': 'Electricity',
                'keys': ['electricity_cost'],
                'color': '#BC80BD'  # Pastel Violet
            },
            'Transport': {
                'name_en': 'Transport',
                'keys': ['transport_operation_cost', 'ng_transport_operation', 'hydrogen_pipeline_operation', 'co2_pipeline_transport_cost'],
                'color': '#CCEBC5'  # Pale Green
            },
            'Storage Op.': {
                'name_en': 'Storage Op.',
                'keys': ['storage_operation_cost', 'h2_storage_operation'],
                'color': '#FFED6F'  # Soft Yellow
            }
        }

        # 分组颜色 - 参考图外圈颜色
        self.group_colors = {
            'Grey': '#9E9E9E',   # Grey
            'Blue': '#5C9BD5',   # Soft Blue
            'Green': '#70AD47'   # Soft Green
        }

        # 数据存储
        self.data = {}

    def draw_curved_text(self, ax, text, radius, center_angle, fontsize=20, color='#333333'):
        """
        绘制沿圆弧弯曲的文字
        """
        # 估算字符宽度 (heuristic)
        # 假设平均字符宽高比，根据半径计算角度跨度
        # 在半径 ~140 (approx max_cost + spacing) 的位置
        # 这是一个粗略的估计，为了更好的效果可能需要微调系数
        
        # 规范化中心角度到 0-2pi
        center_angle = center_angle % (2 * np.pi)
        
        # 判断是否需要翻转文字 (左半圆/下半圆)
        # 通常：
        # - 右半圆 (-90 to 90): 顺时针，字底朝内，从上往下读 (or normal left-to-right look)
        # - 左半圆 (90 to 270): 逆时针，字底朝内? 
        # 为了最佳的“环绕”阅读体验：
        # - Right/Top (315 to 135 deg): Normal, base inward
        # - Left/Bottom (135 to 225 deg): Flipped? 
        
        # 简单策略：严格的“脚朝圆心” (Base pointing center)
        # 实际上用户抱怨之前的切向不对，可能是想让每个字母都垂直于半径
        
        # 计算总跨度
        # 假设每个字符大概宽 0.5 * fontsize (point)
        # 换算成 data coordinates? Plot coords are roughly values (e.g. 100).
        # We need to map fontsize to data scale. Hard without renderer.
        # Trial and error factor.
        
        # 粗调系数
        # 增加间距系数，避免重叠
        # Calculate angle per character: Width / Radius
        # Width approx 0.6 * fontsize (for typical fonts)
        # Using 0.08 angle spacing factor (keep consistent with polar_carbon_stacked_bar_visualization.py)
        char_angle_width = 0.04 * (20 / radius) * fontsize * 0.8
        
        total_angle = len(text) * char_angle_width
        start_angle = center_angle + total_angle / 2
        
        # 检查是否在左侧 (90 ~ 270度)，为了可读性，通常希望字头朝圆心？
        # 或者严格遵循“环绕” (字底朝圆心)
        # 用户之前的抱怨暗示他想要“贴合”，通常意味着字底朝圆心 (Arch effect)
        
        # 如果在下半圆/左侧，为了防止字是倒着的，也可以翻转顺序
        # 但“环绕”效果通常要求字底统一朝内或朝外
        # Let's stick to Base Inward (Arch) for Top, and Base Outward (Smiley) for Bottom?
        # Or Base Inward everywhere?
        # User said "每个字体按照弧度走".
        
        # Let's try: Base Inward everywhere.
        # Exception: Left side might look Upside Down. 
        # But this is the truest "Wrapping".
        
        # Dynamic Flip for readability:
        is_flipped = False
        if 90 < np.degrees(center_angle) < 270:
            is_flipped = True
            
        if is_flipped:
            # Flip: Text drawn clockwise, Base Outward (so it's readable from outside)
            # Or Counter-Clockwise, Base Inward?
            # Usually:
            # Top: Arch (Base Inward)
            # Bottom: Smiley (Base Inward? No, Base Inward at bottom is upside down)
            # Bottom: Smiley (Base Outward - readable)
            
            # Use Base Outward for Left/Bottom
            # Start from left, move right
            start_angle = center_angle - total_angle / 2
            char_step = char_angle_width 
            # Rotation: angle + 90 (Base Outward)
            base_rotation = 90
        else:
            # Normal: Arch (Base Inward)
            # Start from Left (higher angle), move Right (lower angle)
            start_angle = center_angle + total_angle / 2
            char_step = -char_angle_width
            # Rotation: angle - 90 (Base Inward)
            base_rotation = -90
            
        curr_angle = start_angle
        
        for char in text:
            # Calculate rotation
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
        """加载13个场景的数据"""
        logger.info("=" * 80)
        logger.info("加载场景数据")
        logger.info("=" * 80)

        for scenario_name, config in self.scenarios.items():
            logger.info(f"\\n正在加载: {scenario_name} ({config['name_cn']})")

            solution_files = sorted(glob.glob(config['solution_pattern']), reverse=True)

            if not solution_files:
                logger.warning(f"  ⚠ 未找到解决方案文件: {config['solution_pattern']}")
                continue

            solution_path = Path(solution_files[0])
            logger.info(f"  使用文件: {solution_path.name}")

            with open(solution_path, 'r', encoding='utf-8') as f:
                solution_data = json.load(f)

            self.data[scenario_name] = {
                'solution': solution_data,
                'config': config
            }

            total_cost = solution_data.get('cost_breakdown', {}).get('total_cost_excluding_shortage', 0) / 1e9
            logger.info(f"  ✓ 总成本: {total_cost:.2f} 亿元")

        logger.info("\\n" + "=" * 80)
        logger.info(f"数据加载完成 - 成功加载 {len(self.data)} 个场景")
        logger.info("=" * 80)

    def extract_cost_data(self) -> Tuple[List[str], Dict[str, List[float]]]:
        """
        提取成本数据

        Returns:
            场景标签列表和各成本类别的数据字典
        """
        scenarios_list = list(self.data.keys())
        labels = [self.data[s]['config']['label'] for s in scenarios_list]

        # 提取各成本类别的数据（单位：亿元）
        cost_data = {cat: [] for cat in self.cost_categories.keys()}

        for scenario in scenarios_list:
            cost_breakdown = self.data[scenario]['solution'].get('cost_breakdown', {})

            for cat, cat_config in self.cost_categories.items():
                total = sum(cost_breakdown.get(key, 0) for key in cat_config['keys']) / 1e9
                cost_data[cat].append(total)

        return labels, cost_data, scenarios_list

    def get_scenario_groups(self, scenarios_list: List[str]) -> List[str]:
         """获取场景的分组列表"""
         return [self.scenarios[s]['group'] for s in scenarios_list]

    def create_polar_stacked_bar_chart(self):
        """创建极坐标堆叠柱状图 - 统一风格版"""
        logger.info("\\n生成极坐标堆叠柱状图 (Unified Style)...")

        # 配置字体
        plt.rcParams['font.family'] = ['Times New Roman', 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False

        # 提取数据
        labels, cost_data, scenarios_list = self.extract_cost_data()
        groups = self.get_scenario_groups(scenarios_list)
        n_scenarios = len(labels)

        if n_scenarios == 0:
            logger.error("没有可用的场景数据")
            return

        # 创建图形
        # 增加尺寸以容纳大字体
        fig, ax = plt.subplots(figsize=(16, 16), subplot_kw=dict(projection='polar'))
        fig.patch.set_facecolor('white')
        ax.set_facecolor('white')

        # 计算最大值以确定scaling
        # 预先计算总高度
        total_costs = np.zeros(n_scenarios)
        for cat_name in self.cost_categories:
            total_costs += np.array(cost_data[cat_name])
        max_cost = max(total_costs)
        
        # 几何参数
        INNER_RADIUS = max_cost * 0.35  # 内圈半径
        
        # === 新的分组角度计算 logic (参考 polar_percentage_grouped_visualization.py) ===
        gap_angle = np.pi / 20  # 组间间隙 (9度左右)
        
        # 统计组数
        unique_groups = []
        for g in groups:
            if g not in unique_groups:
                unique_groups.append(g)
        n_groups = len(unique_groups)
        
        total_gap = gap_angle * n_groups
        available_angle = 2 * np.pi - total_gap  # 可用角度
        
        # 按场景数量分配角度
        angle_per_scenario = available_angle / n_scenarios
        
        # 柱子宽度
        width = angle_per_scenario * 0.95 

        # 计算每个场景的角度位置
        angles = []
        current_angle = np.pi / 2  # 从顶部开始 (90度)
        
        # 记录每组的起始和结束角度（用于画外圈）
        group_angular_ranges = {}
        
        current_group = None
        temp_angles = [] # 临时存储当前组的角度

        for i, (label, group) in enumerate(zip(labels, groups)):
            # 检测新组 (排除第一次迭代)
            if current_group is not None and group != current_group:
                # 记录上一组的范围
                max_ang = max(temp_angles) + angle_per_scenario/2
                min_ang = min(temp_angles) - angle_per_scenario/2
                group_angular_ranges[current_group] = (min_ang, max_ang)
                temp_angles = []

                # 添加组间间隙
                current_angle -= gap_angle

            if current_group != group:
                current_group = group
            
            angles.append(current_angle)
            temp_angles.append(current_angle)
            
            current_angle -= angle_per_scenario

        # 处理最后一组
        if temp_angles:
             max_ang = max(temp_angles) + angle_per_scenario/2
             min_ang = min(temp_angles) - angle_per_scenario/2
             group_angular_ranges[current_group] = (min_ang, max_ang)

        angles = np.array(angles)
        
        # 绘制堆叠柱状图
        bottom = np.zeros(n_scenarios) + INNER_RADIUS

        for cat_name, cat_config in self.cost_categories.items():
            values = np.array(cost_data[cat_name])
            bars = ax.bar(
                angles,
                values,
                width=width,
                bottom=bottom,
                label=cat_config['name_en'],
                color=cat_config['color'],
                edgecolor='white',
                linewidth=0.3,
                alpha=0.9
            )
            bottom += values

        # === 绘制外圈 (Group Ring) ===
        RING_GAP = max_cost * 0.02 # 缩小间隙
        RING_WIDTH = max_cost * 0.12 # 加宽以容纳大字体
        outer_ring_start = max(bottom) + RING_GAP
        
        # 绘制
        for group_name, (min_ang, max_ang) in group_angular_ranges.items():
            # 计算这一组的跨度
            center_angle = (min_ang + max_ang) / 2
            span_angle = max_ang - min_ang
            
            # 绘制弧形
            ax.bar(
                x=center_angle,
                height=RING_WIDTH,
                bottom=outer_ring_start,
                width=span_angle, # 紧凑对齐
                color=self.group_colors.get(group_name, '#999999'),
                alpha=0.8,
                edgecolor='none'
            )
            
            # 添加组标签(在环的中间)
            # 计算旋转: Tangential (Tangent to the circle)
            # 0度(Right) -> Vertical (-90)
            # 90度(Top) -> Horizontal (0)
            deg = np.degrees(center_angle)
            if deg < 0: deg += 360
            
            # Tangential rotation
            rotation = deg - 90
            
            # Flip text on the left/bottom side to be readable
            # Range: 90 to 270 degrees
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

        # 样式设置
        # 1. 移除默认的角度刻度
        ax.set_xticks([])
        
        # 2. 设置径向刻度 (虚线网格)
        # 生成漂亮的刻度值
        tick_max = max(bottom) - INNER_RADIUS
        # 选取几个合适的整数刻度
        n_ticks = 5
        tick_step = np.ceil(tick_max / n_ticks)
        simple_ticks = np.arange(0, tick_max + tick_step, tick_step)
        
        # 映射回实际半径
        actual_ticks = simple_ticks + INNER_RADIUS
        
        ax.set_yticks(actual_ticks)
        ax.set_yticklabels([]) # 不显示默认标签
        
        ax.yaxis.grid(True, linestyle='--', alpha=0.5, color='#aaaaaa', linewidth=0.8, dashes=(4, 4))
        ax.xaxis.grid(False)
        ax.spines['polar'].set_visible(False)

        # 3. 添加径向刻度标签 (在顶部)
        tick_angle = np.pi / 2 # 顶部
        for val, radius in zip(simple_ticks[1:], actual_ticks[1:]): # 跳过0
            ax.text(
                tick_angle, radius, f"{int(val)}",
                ha='center', va='center',
                fontsize=22, color='#666666',
                fontweight='bold',
                bbox=dict(facecolor='white', edgecolor='none', alpha=0.7, pad=0.5)
            )

        # 4. 场景标签 (最外侧) -> 使用弯曲文字
        label_radius = outer_ring_start + RING_WIDTH * 1.5
        
        for angle, label in zip(angles, labels):
            self.draw_curved_text(ax, label, label_radius, angle, fontsize=24, color='#333333')

        # 5. 图例
        # Cost Components Legend - Right Side
        handles, _ = ax.get_legend_handles_labels()
        
        cost_legend = ax.legend(
            handles=handles[:len(self.cost_categories)],
            labels=list(self.cost_categories.keys()), 
            loc='upper left',
            bbox_to_anchor=(1.15, 1.0), # Right side
            fontsize=24,
            title='Cost Components',
            title_fontsize=26,
            frameon=False,
            labelspacing=0.8
        )
        cost_legend.get_title().set_fontweight('bold')
        # 移除 Group Legend，因为标签已经在环上了

        # 6. 中心标题/单位
        ax.text(
            0, 0, 'Cost\n(100M CNY)',
            ha='center', va='center',
            fontsize=24, fontweight='bold',
            color='#555555'
        )

        plt.tight_layout()

        # 保存图片
        output_path = self.session_dir / "polar_stacked_bar_chart.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
        logger.info(f"  ✓ 保存图片: {output_path}")

        # 同时保存到visualization目录根目录
        root_output = self.output_dir / "polar_stacked_bar_chart_latest.png"
        plt.savefig(root_output, dpi=300, bbox_inches='tight', facecolor='white')
        logger.info(f"  ✓ 保存最新版本: {root_output}")

        plt.close()

        return output_path

    def run_all_visualizations(self):
        """运行所有可视化"""
        logger.info("\\n" + "=" * 80)
        logger.info("开始生成可视化")
        logger.info("=" * 80)

        # 生成极坐标图
        self.create_polar_stacked_bar_chart()

        logger.info("\\n" + "=" * 80)
        logger.info("✓ 所有可视化生成完成")
        logger.info(f"✓ 输出目录: {self.session_dir}")
        logger.info("=" * 80)


def main():
    """主函数"""
    logger.info("=" * 80)
    logger.info("极坐标堆叠柱状图可视化脚本")
    logger.info("Polar Stacked Bar Chart Visualization Script")
    logger.info("=" * 80)

    # 创建可视化器
    visualizer = PolarStackedBarVisualizer()

    # 加载数据
    visualizer.load_data()

    # 检查是否有足够的数据
    if len(visualizer.data) < 2:
        logger.error(f"✗ 数据不足：只找到 {len(visualizer.data)} 个场景的数据")
        logger.error("  请先运行各场景的优化器生成结果文件")
        return

    # 运行所有可视化
    visualizer.run_all_visualizations()

    logger.info("\\n✓ 程序执行成功")


if __name__ == "__main__":
    main()
