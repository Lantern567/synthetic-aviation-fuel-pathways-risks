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

        # 13个场景配置 - 使用英文缩写标签
        self.scenarios = {
            'Coal Hydrogen': {
                'name_cn': '煤制氢',
                'label': 'CH',
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/complete_solution_*.json')
            },
            'DAC Two-Step': {
                'name_cn': 'DAC两步法',
                'label': 'DAC-2S',
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/two_step/complete_solution_*.json')
            },
            'DAC One-Step': {
                'name_cn': 'DAC一步法',
                'label': 'DAC-1S',
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/one_step/complete_solution_*.json')
            },
            'Natural Gas Two-Step': {
                'name_cn': '天然气两步法',
                'label': 'NG-2S',
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/complete_solution_*.json')
            },
            'Natural Gas One-Step': {
                'name_cn': '天然气一步法',
                'label': 'NG-1S',
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/ft_one_step/complete_solution_*.json')
            },
            'Green H2 Two-Step': {
                'name_cn': '绿氢两步法',
                'label': 'GH-2S',
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/two_step/complete_solution_*.json')
            },
            'Green H2 One-Step': {
                'name_cn': '绿氢一步法',
                'label': 'GH-1S',
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/one_step/complete_solution_*.json')
            },
            'Byproduct H2 + Coal': {
                'name_cn': '副产氢+煤',
                'label': 'BH-CH',
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/byproduct_hydrogen/complete_solution_*.json')
            },
            'Byproduct H2 + DAC Two-Step': {
                'name_cn': '副产氢+DAC两步',
                'label': 'BH-DAC2',
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/two_step/complete_solution_*.json')
            },
            'Byproduct H2 + DAC One-Step': {
                'name_cn': '副产氢+DAC一步',
                'label': 'BH-DAC1',
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/one_step/complete_solution_*.json')
            },
            'Byproduct H2 + NG Two-Step': {
                'name_cn': '副产氢+天然气两步',
                'label': 'BH-NG',
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/byproduct_hydrogen/byproduct_hydrogen/two_step/complete_solution_*.json')
            },
            'Byproduct H2 Two-Step': {
                'name_cn': '副产氢两步法',
                'label': 'BH-2S',
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/two_step/complete_solution_*.json')
            },
            'Byproduct H2 One-Step': {
                'name_cn': '副产氢一步法',
                'label': 'BH-1S',
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/one_step/complete_solution_*.json')
            }
        }

        # 12个成本分类配置 - 使用高区分度的颜色
        self.cost_categories = {
            'Facility Inv.': {
                'name_en': 'Facility Inv.',
                'keys': ['facility_investment_cost'],
                'color': '#1f77b4'  # 深蓝
            },
            'Storage Equip.': {
                'name_en': 'Storage Equip.',
                'keys': ['storage_equipment_cost', 'h2_storage_investment'],
                'color': '#2ca02c'  # 绿色
            },
            'Electrolyzer': {
                'name_en': 'Electrolyzer',
                'keys': ['electrolyzer_investment_cost'],
                'color': '#9467bd'  # 紫色
            },
            'DAC Equip.': {
                'name_en': 'DAC Equip.',
                'keys': ['dac_facility_investment'],
                'color': '#17becf'  # 青色
            },
            'Raw Material': {
                'name_en': 'Raw Material',
                'keys': ['coal_purchase_cost', 'coal_gasification_cost', 'natural_gas_cost', 'dac_capture_cost'],
                'color': '#ff7f0e'  # 橙色
            },
            'CO2 Capture': {
                'name_en': 'CO2 Capture',
                'keys': ['co2_capture_cost'],
                'color': '#bcbd22'  # 黄绿
            },
            'Production': {
                'name_en': 'Production',
                'keys': ['production_cost', 'facility_operation_cost'],
                'color': '#e377c2'  # 粉色
            },
            'FT Production': {
                'name_en': 'FT Production',
                'keys': ['ft_production_cost'],
                'color': '#7f7f7f'  # 灰色
            },
            'Catalyst': {
                'name_en': 'Catalyst',
                'keys': ['catalyst_cost'],
                'color': '#8c564b'  # 棕色
            },
            'Electricity': {
                'name_en': 'Electricity',
                'keys': ['electricity_cost'],
                'color': '#d62728'  # 红色
            },
            'Transport': {
                'name_en': 'Transport',
                'keys': ['transport_operation_cost', 'ng_transport_operation', 'hydrogen_pipeline_operation', 'co2_pipeline_transport_cost'],
                'color': '#aec7e8'  # 浅蓝
            },
            'Storage Op.': {
                'name_en': 'Storage Op.',
                'keys': ['storage_operation_cost', 'h2_storage_operation'],
                'color': '#98df8a'  # 浅绿
            }
        }

        # 数据存储
        self.data = {}

    def load_data(self):
        """加载13个场景的数据"""
        logger.info("=" * 80)
        logger.info("加载场景数据")
        logger.info("=" * 80)

        for scenario_name, config in self.scenarios.items():
            logger.info(f"\n正在加载: {scenario_name} ({config['name_cn']})")

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

        logger.info("\n" + "=" * 80)
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

        return labels, cost_data

    def create_polar_stacked_bar_chart(self):
        """创建极坐标堆叠柱状图"""
        logger.info("\n生成极坐标堆叠柱状图...")

        # 配置字体 - 使用Times New Roman和DejaVu Sans
        plt.rcParams['font.family'] = ['Times New Roman', 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False

        # 提取数据
        labels, cost_data = self.extract_cost_data()
        n_scenarios = len(labels)

        if n_scenarios == 0:
            logger.error("没有可用的场景数据")
            return

        # 创建图形
        fig, ax = plt.subplots(figsize=(14, 14), subplot_kw=dict(projection='polar'))

        # 计算角度 - 均匀分布在圆周上
        angles = np.linspace(0, 2 * np.pi, n_scenarios, endpoint=False)

        # 柱子宽度
        width = 2 * np.pi / n_scenarios * 0.75

        # 绘制堆叠柱状图
        bottom = np.zeros(n_scenarios)

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
                linewidth=0.5,
                alpha=0.9
            )
            bottom += values

        # 设置角度刻度（场景标签）
        ax.set_xticks(angles)
        ax.set_xticklabels(labels, fontsize=11, fontweight='bold')

        # 调整标签位置到柱子外侧
        ax.tick_params(axis='x', pad=15)

        # 设置径向刻度（成本值）
        max_value = max(bottom)
        r_ticks = np.linspace(0, max_value, 6)
        ax.set_yticks(r_ticks)
        ax.set_yticklabels([f'{int(v)}' for v in r_ticks], fontsize=9)
        ax.set_ylim(0, max_value * 1.1)

        # 设置网格线样式
        ax.yaxis.grid(True, linestyle='-', alpha=0.3, color='gray')
        ax.xaxis.grid(True, linestyle='-', alpha=0.2, color='gray')

        # 设置起始角度（从顶部开始）
        ax.set_theta_offset(np.pi / 2)
        ax.set_theta_direction(-1)  # 顺时针方向

        # 添加图例
        legend = ax.legend(
            loc='upper left',
            bbox_to_anchor=(1.15, 1.0),
            fontsize=10,
            title='Cost Components',
            title_fontsize=12,
            frameon=True,
            fancybox=True,
            shadow=True
        )

        # 添加标题
        plt.title(
            'Cost Breakdown Comparison of 13 SAF Supply Chain Scenarios',
            fontsize=14,
            fontweight='bold',
            pad=30
        )

        # 添加单位说明
        fig.text(
            0.5, 0.02,
            'Unit: 100 Million CNY',
            ha='center',
            fontsize=11,
            style='italic'
        )

        plt.tight_layout()

        # 保存图片
        output_path = self.session_dir / "polar_stacked_bar_chart.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
        logger.info(f"  ✓ 保存图片: {output_path}")

        # 同时保存到visualization目录根目录（方便查看）
        root_output = self.output_dir / "polar_stacked_bar_chart_latest.png"
        plt.savefig(root_output, dpi=300, bbox_inches='tight', facecolor='white')
        logger.info(f"  ✓ 保存最新版本: {root_output}")

        plt.close()

        return output_path

    def create_polar_stacked_bar_chart_v2(self):
        """创建改进版极坐标堆叠柱状图 - 更接近参考图风格"""
        logger.info("\n生成改进版极坐标堆叠柱状图...")

        # 配置字体 - 使用Times New Roman和DejaVu Sans
        plt.rcParams['font.family'] = ['Times New Roman', 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False

        # 提取数据
        labels, cost_data = self.extract_cost_data()
        n_scenarios = len(labels)

        if n_scenarios == 0:
            logger.error("没有可用的场景数据")
            return

        # 创建图形 - 使用白色背景
        fig, ax = plt.subplots(figsize=(14, 12), subplot_kw=dict(projection='polar'))
        fig.patch.set_facecolor('white')
        ax.set_facecolor('white')

        # 计算角度 - 从顶部开始，顺时针排列
        angles = np.linspace(0, 2 * np.pi, n_scenarios, endpoint=False)
        # 调整起始位置
        angles = angles + np.pi / 2

        # 柱子宽度 - 略微缩小以留出间隙
        width = 2 * np.pi / n_scenarios * 0.7

        # 绘制堆叠柱状图
        bottom = np.zeros(n_scenarios)

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
                alpha=0.95
            )
            bottom += values

        # 获取最大值用于设置刻度
        max_value = max(bottom)

        # 设置径向刻度
        r_ticks = np.linspace(0, max_value, 6)
        ax.set_yticks(r_ticks[1:])  # 跳过0
        ax.set_yticklabels([f'{int(v)}' for v in r_ticks[1:]], fontsize=8, color='gray')
        ax.set_ylim(0, max_value * 1.25)  # 留出空间放标签

        # 设置网格线样式 - 灰色同心圆
        ax.yaxis.grid(True, linestyle='-', alpha=0.4, color='#cccccc', linewidth=0.8)
        ax.xaxis.grid(False)  # 关闭角度网格线

        # 隐藏默认的角度刻度
        ax.set_xticks([])

        # 在柱子外侧添加场景标签
        label_radius = max_value * 1.15
        for angle, label in zip(angles, labels):
            # 计算标签角度（弧度转角度）
            angle_deg = np.degrees(angle)

            # 根据位置调整文本对齐方式
            if 45 < angle_deg < 135:
                ha = 'center'
                va = 'bottom'
            elif 135 <= angle_deg < 225:
                ha = 'right'
                va = 'center'
            elif 225 <= angle_deg < 315:
                ha = 'center'
                va = 'top'
            else:
                ha = 'left'
                va = 'center'

            ax.text(
                angle, label_radius, label,
                ha=ha, va=va,
                fontsize=11, fontweight='bold',
                color='#333333'
            )

        # 设置起始角度和方向
        ax.set_theta_offset(0)
        ax.set_theta_direction(-1)

        # 添加图例 - 放在右上角
        legend = ax.legend(
            loc='upper right',
            bbox_to_anchor=(1.35, 1.05),
            fontsize=9,
            title='Cost Components',
            title_fontsize=11,
            frameon=True,
            fancybox=True,
            edgecolor='#cccccc'
        )

        # 设置图例标题样式
        legend.get_title().set_fontweight('bold')

        plt.tight_layout()

        # 保存图片
        output_path = self.session_dir / "polar_stacked_bar_chart_v2.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
        logger.info(f"  ✓ 保存图片: {output_path}")

        plt.close()

        return output_path

    def run_all_visualizations(self):
        """运行所有可视化"""
        logger.info("\n" + "=" * 80)
        logger.info("开始生成可视化")
        logger.info("=" * 80)

        # 生成两个版本的极坐标图
        self.create_polar_stacked_bar_chart()
        self.create_polar_stacked_bar_chart_v2()

        logger.info("\n" + "=" * 80)
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

    logger.info("\n✓ 程序执行成功")


if __name__ == "__main__":
    main()
