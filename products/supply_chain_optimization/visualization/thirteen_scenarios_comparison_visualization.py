"""
十三场景对比可视化脚本
Thirteen Scenarios Comparison Visualization Script

功能 | Features:
1. 成本构成对比 (Cost breakdown comparison)
2. 需求满足程度对比 (Demand fulfillment comparison)
3. 碳排放三指标对比 (Carbon emissions three indicators comparison)
4. 生命周期平准化成本对比 (Levelized cost comparison)

支持场景 | Supported Scenarios:

绿氢场景 (Green Hydrogen Scenarios):
1. 煤制氢 (Coal Hydrogen)
2. DAC制氢两步法 (DAC Hydrogen Two-Step)
3. DAC制氢一步法 (DAC Hydrogen One-Step)
4. 天然气两步法 (Natural Gas Two-Step)
5. 天然气一步法 (Natural Gas One-Step)
6. 绿氢+工业捕获CO₂两步法 (Green H2 + Industrial CO2 Two-Step)
7. 绿氢+工业捕获CO₂一步法 (Green H2 + Industrial CO2 One-Step)

副产氢场景 (Byproduct Hydrogen Scenarios):
8. 副产氢+煤制氢 (Byproduct H2 + Coal)
9. 副产氢+DAC两步法 (Byproduct H2 + DAC Two-Step)
10. 副产氢+DAC一步法 (Byproduct H2 + DAC One-Step)
11. 副产氢+天然气两步法 (Byproduct H2 + NG Two-Step)
12. 副产氢+工业CO₂两步法 (Byproduct H2 Two-Step)
13. 副产氢+工业CO₂一步法 (Byproduct H2 One-Step)

注意 | Note:
- 天然气一步法不包含副产氢场景，因为一步法不需要绿氢，无法进行副产氢化
- Natural Gas One-Step does not have a byproduct hydrogen scenario because it doesn't require green hydrogen

作者 | Author: Claude Code
创建时间 | Created: 2025-11-19
最后更新 | Last Updated: 2025-11-23
"""

import json
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
import seaborn as sns

# 配置中文字体 - 支持Linux和Windows系统,移除DejaVu Sans避免回退
plt.rcParams['font.sans-serif'] = ['Noto Sans CJK SC', 'Noto Sans CJK TC', 'WenQuanYi Zen Hei', 'Microsoft YaHei', 'SimHei']
plt.rcParams['axes.unicode_minus'] = False

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ThirteenScenariosComparisonVisualizer:
    """十三场景对比可视化器"""

    def __init__(self, output_dir: str = None):
        """
        初始化可视化器

        Args:
            output_dir: 输出目录，默认为 products/supply_chain_optimization/visualization/results
        """
        if output_dir is None:
            base_dir = Path(__file__).parent.parent.parent.parent
            output_dir = base_dir / "products" / "supply_chain_optimization" / "visualization" / "results"

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 创建带时间戳的子目录
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = self.output_dir / f"comparison_13scenarios_{timestamp}"
        self.session_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"输出目录: {self.session_dir}")

        # 模块配置 - 使用绝对路径和自动查找最新文件
        # 获取项目根目录
        project_root = Path(__file__).parent.parent.parent.parent

        self.modules = {
            # ========== 绿氢场景 (7个) ==========
            'Coal Hydrogen': {
                'name_cn': '煤制氢',
                'color': '#E74C3C',  # 红色
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/complete_solution_*.json'),
                'carbon_pattern': str(project_root / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/carbon_emissions_detailed_*.json')
            },
            'DAC Two-Step': {
                'name_cn': 'DAC两步法',
                'color': '#3498DB',  # 蓝色
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/two_step/complete_solution_*.json'),
                'carbon_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/two_step/carbon_emissions_detailed_*.json')
            },
            'DAC One-Step': {
                'name_cn': 'DAC一步法',
                'color': '#5DADE2',  # 浅蓝色
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/one_step/complete_solution_*.json'),
                'carbon_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/one_step/carbon_emissions_detailed_*.json')
            },
            'Natural Gas Two-Step': {
                'name_cn': '天然气两步法',
                'color': '#2ECC71',  # 绿色
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/complete_solution_*.json'),
                'carbon_pattern': str(project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/carbon_emissions_detailed_*.json')
            },
            'Natural Gas One-Step': {
                'name_cn': '天然气一步法',
                'color': '#F39C12',  # 橙色
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/ft_one_step/complete_solution_*.json'),
                'carbon_pattern': str(project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/ft_one_step/carbon_emissions_detailed_*.json')
            },
            'Green H2 Two-Step': {
                'name_cn': '绿氢两步法',
                'color': '#9B59B6',  # 紫色
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/two_step/complete_solution_*.json'),
                'carbon_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/two_step/carbon_emissions_detailed_*.json')
            },
            'Green H2 One-Step': {
                'name_cn': '绿氢一步法',
                'color': '#C39BD3',  # 浅紫色
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/one_step/complete_solution_*.json'),
                'carbon_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/one_step/carbon_emissions_detailed_*.json')
            },

            # ========== 副产氢场景 (6个) ==========
            # 注意：天然气一步法不包含副产氢场景（一步法不需要绿氢，无法副产氢化）
            'Byproduct H2 + Coal': {
                'name_cn': '副产氢+煤',
                'color': '#FF6B6B',  # 亮红色
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/byproduct_hydrogen/complete_solution_*.json'),
                'carbon_pattern': str(project_root / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/byproduct_hydrogen/carbon_emissions_detailed_*.json')
            },
            'Byproduct H2 + DAC Two-Step': {
                'name_cn': '副产氢+DAC两步',
                'color': '#4ECDC4',  # 青色
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/two_step/complete_solution_*.json'),
                'carbon_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/two_step/carbon_emissions_detailed_*.json')
            },
            'Byproduct H2 + DAC One-Step': {
                'name_cn': '副产氢+DAC一步',
                'color': '#95E1D3',  # 浅青色
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/one_step/complete_solution_*.json'),
                'carbon_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/one_step/carbon_emissions_detailed_*.json')
            },
            'Byproduct H2 + NG Two-Step': {
                'name_cn': '副产氢+天然气两步',
                'color': '#26DE81',  # 亮绿色
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/byproduct_hydrogen/byproduct_hydrogen/two_step/complete_solution_*.json'),
                'carbon_pattern': str(project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/byproduct_hydrogen/byproduct_hydrogen/two_step/carbon_emissions_detailed_*.json')
            },
            'Byproduct H2 Two-Step': {
                'name_cn': '副产氢两步法',
                'color': '#A29BFE',  # 亮紫色
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/two_step/complete_solution_*.json'),
                'carbon_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/two_step/carbon_emissions_detailed_*.json')
            },
            'Byproduct H2 One-Step': {
                'name_cn': '副产氢一步法',
                'color': '#DFE4EA',  # 浅紫灰色
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/one_step/complete_solution_*.json'),
                'carbon_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/one_step/carbon_emissions_detailed_*.json')
            }
        }

        # 数据存储
        self.data = {}

    def load_data(self):
        """加载十三个场景的数据"""
        logger.info("=" * 80)
        logger.info("加载模块数据")
        logger.info("=" * 80)

        import glob

        for module_name, config in self.modules.items():
            logger.info(f"\n正在加载: {module_name} ({config['name_cn']})")

            try:
                # 加载解决方案文件（自动查找最新文件）
                solution_pattern = config['solution_pattern']
                solution_files = sorted(glob.glob(solution_pattern), reverse=True)

                if not solution_files:
                    logger.warning(f"  ⚠ 未找到解决方案文件: {solution_pattern}")
                    continue

                solution_path = Path(solution_files[0])
                logger.info(f"  使用最新的解决方案文件: {solution_path.name}")
                with open(solution_path, 'r', encoding='utf-8') as f:
                    solution_data = json.load(f)

                # 加载碳排放文件（自动查找最新文件）
                carbon_pattern = config['carbon_pattern']
                carbon_files = sorted(glob.glob(carbon_pattern), reverse=True)

                if not carbon_files:
                    logger.warning(f"  ⚠ 未找到碳排放文件: {carbon_pattern}")
                    continue

                carbon_path = Path(carbon_files[0])
                logger.info(f"  使用最新的碳排放文件: {carbon_path.name}")
                with open(carbon_path, 'r', encoding='utf-8') as f:
                    carbon_data = json.load(f)

                self.data[module_name] = {
                    'solution': solution_data,
                    'carbon': carbon_data,
                    'config': config
                }

                logger.info(f"  ✓ 解决方案文件: {solution_path.name}")
                logger.info(f"  ✓ 碳排放文件: {carbon_path.name}")
                logger.info(f"  ✓ 总成本: {solution_data.get('objective_value_lifecycle_total', 0) / 1e9:.2f} 亿元")
                logger.info(f"  ✓ 碳强度: {carbon_data.get('carbon_intensity_kg', 0):.2f} kg CO2/kg SAF")

            except Exception as e:
                logger.error(f"  ✗ 加载失败: {e}")
                # 不抛出异常，继续加载其他场景
                continue

        logger.info("\n" + "=" * 80)
        logger.info(f"数据加载完成 - 成功加载 {len(self.data)} 个场景")
        logger.info("=" * 80)

    def visualize_cost_breakdown(self):
        """可视化成本构成对比"""
        logger.info("\n生成成本构成对比图...")

        # 详细成本项
        detailed_costs = {
            'Facility Investment': ('设施投资', ['facility_investment_cost']),
            'Storage Equipment': ('储存设备', ['storage_equipment_cost', 'h2_storage_investment']),
            'Electrolyzer': ('电解槽', ['electrolyzer_investment_cost']),
            'DAC Equipment': ('DAC设备', ['dac_facility_investment']),
            'Raw Material': ('原料成本', ['coal_purchase_cost', 'coal_gasification_cost', 'natural_gas_cost', 'dac_capture_cost']),
            'CO2 Capture': ('CO₂捕获', ['co2_capture_cost']),
            'Production': ('生产成本', ['production_cost', 'facility_operation_cost']),
            'FT Production': ('FT生产', ['ft_production_cost']),
            'Catalyst': ('催化剂', ['catalyst_cost']),
            'Electricity': ('电力成本', ['electricity_cost']),
            'Transport': ('运输成本', ['transport_operation_cost', 'ng_transport_operation', 'hydrogen_pipeline_operation', 'co2_pipeline_transport_cost']),
            'Storage Operation': ('储存运营', ['storage_operation_cost', 'h2_storage_operation'])
        }

        # 创建图形（两个子图）- 调整宽度适配13个场景
        fig, axes = plt.subplots(1, 2, figsize=(26, 8))
        fig.suptitle('十三场景成本对比 | Thirteen Scenarios Cost Comparison', fontsize=18, fontweight='bold')

        # === 子图1: 总成本和投资/运营成本对比 ===
        ax1 = axes[0]

        modules_list = list(self.data.keys())
        x_pos = np.arange(len(modules_list))
        width = 0.25

        # 提取数据
        total_costs = []
        investment_costs = []
        operation_costs = []

        for module in modules_list:
            cost_data = self.data[module]['solution'].get('cost_breakdown', {})
            total_costs.append(cost_data.get('total_cost_excluding_shortage', 0) / 1e9)
            investment_costs.append(cost_data.get('total_investment_cost', 0) / 1e9)
            operation_costs.append(cost_data.get('total_operation_cost', 0) / 1e9)

        # 绘制柱状图
        bars1 = ax1.bar(x_pos - width, total_costs, width, label='总成本 Total', color='#95A5A6', alpha=0.8)
        bars2 = ax1.bar(x_pos, investment_costs, width, label='投资成本 Investment', color='#3498DB', alpha=0.8)
        bars3 = ax1.bar(x_pos + width, operation_costs, width, label='运营成本 Operation', color='#E74C3C', alpha=0.8)

        # 添加数值标签
        for bars in [bars1, bars2, bars3]:
            for bar in bars:
                height = bar.get_height()
                ax1.text(bar.get_x() + bar.get_width()/2., height,
                        f'{height:.0f}',
                        ha='center', va='bottom', fontsize=7)

        ax1.set_xlabel('场景 | Scenario', fontsize=13)
        ax1.set_ylabel('成本（亿元）| Cost (100M CNY)', fontsize=13)
        ax1.set_title('生命周期总成本对比 | Lifecycle Total Cost', fontsize=14, fontweight='bold')
        ax1.set_xticks(x_pos)
        ax1.set_xticklabels([self.modules[m]['name_cn'] for m in modules_list], rotation=45, ha='right', fontsize=8)
        ax1.legend(loc='upper left')
        ax1.grid(axis='y', alpha=0.3)

        # === 子图2: 详细成本构成堆叠柱状图 ===
        ax2 = axes[1]

        # 提取详细成本数据
        detailed_data = {cat: [] for cat in detailed_costs.keys()}

        for module in modules_list:
            cost_data = self.data[module]['solution'].get('cost_breakdown', {})

            for cat, (cn_name, keys) in detailed_costs.items():
                total = sum(cost_data.get(key, 0) for key in keys) / 1e9
                detailed_data[cat].append(total)

        # 绘制堆叠柱状图
        bottom = np.zeros(len(modules_list))
        colors = plt.cm.Set3(np.linspace(0, 1, len(detailed_costs)))

        x_positions = np.arange(len(modules_list))

        for (cat, (cn_name, _)), color in zip(detailed_costs.items(), colors):
            values = detailed_data[cat]
            bars = ax2.bar(x_positions, values, bottom=bottom, label=cn_name,
                          color=color, alpha=0.8, edgecolor='white', linewidth=1.5)

            # 添加数值标签（只显示大于15的值，避免拥挤）
            for i, (bar, val) in enumerate(zip(bars, values)):
                if val > 15:
                    ax2.text(bar.get_x() + bar.get_width()/2., bottom[i] + val/2.,
                            f'{val:.0f}',
                            ha='center', va='center', fontsize=6, fontweight='bold')

            bottom += values

        ax2.set_ylabel('成本（亿元）| Cost (100M CNY)', fontsize=13)
        ax2.set_title('详细成本构成 | Detailed Cost Breakdown', fontsize=14, fontweight='bold')
        ax2.set_xticks(x_positions)
        ax2.set_xticklabels([self.modules[m]['name_cn'] for m in modules_list], rotation=45, ha='right', fontsize=8)
        ax2.legend(loc='upper left', bbox_to_anchor=(1.02, 1), fontsize=8)
        ax2.grid(axis='y', alpha=0.3)

        plt.tight_layout()

        # 保存图片
        output_path = self.session_dir / "cost_breakdown_comparison.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        logger.info(f"  ✓ 保存图片: {output_path}")
        plt.close()

    def visualize_demand_fulfillment(self):
        """可视化需求满足程度"""
        logger.info("\n生成需求满足程度对比图...")

        # 创建图形 - 调整宽度适配13个场景
        fig, ax = plt.subplots(figsize=(15, 8))
        fig.suptitle('需求满足程度对比 | Demand Fulfillment Comparison', fontsize=18, fontweight='bold')

        modules_list = list(self.data.keys())
        x_pos = np.arange(len(modules_list))

        # 提取需求满足率和实际产量
        fulfillment_ratios = []
        actual_productions = []

        for module in modules_list:
            solution_data = self.data[module]['solution']

            fulfillment_ratios.append(solution_data.get('demand_fulfillment_ratio', 0) * 100)
            actual_productions.append(solution_data.get('lifecycle_total_production_kg', 0) / 1e6)

        # 绘制柱状图
        color_map = {m: self.modules[m]['color'] for m in modules_list}
        colors = [color_map[m] for m in modules_list]

        bars = ax.bar(x_pos, fulfillment_ratios, color=colors, alpha=0.7, edgecolor='black', linewidth=1.5)

        # 添加数值标签
        for bar, ratio, prod in zip(bars, fulfillment_ratios, actual_productions):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + 1,
                   f'{ratio:.1f}%\n({prod:.1f}kt)',
                   ha='center', va='bottom', fontsize=7, fontweight='bold')

        # 添加100%参考线
        ax.axhline(y=100, color='red', linestyle='--', linewidth=2, label='100% 满足线', alpha=0.7)

        ax.set_xlabel('场景 | Scenario', fontsize=13)
        ax.set_ylabel('需求满足率 (%) | Fulfillment Ratio (%)', fontsize=13)
        ax.set_title('SAF需求满足程度 | SAF Demand Fulfillment', fontsize=14, fontweight='bold')
        ax.set_xticks(x_pos)
        ax.set_xticklabels([self.modules[m]['name_cn'] for m in modules_list], rotation=45, ha='right', fontsize=9)
        ax.set_ylim([0, 110])
        ax.legend(loc='lower right')
        ax.grid(axis='y', alpha=0.3)

        plt.tight_layout()

        # 保存图片
        output_path = self.session_dir / "demand_fulfillment_comparison.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        logger.info(f"  ✓ 保存图片: {output_path}")
        plt.close()

    def visualize_carbon_emissions(self):
        """可视化碳排放三指标"""
        logger.info("\n生成碳排放三指标对比图...")

        # 创建图形（三个子图）- 调整宽度适配13个场景
        fig, axes = plt.subplots(1, 3, figsize=(28, 8))
        fig.suptitle('碳排放三指标对比 | Carbon Emissions Three Indicators Comparison',
                    fontsize=18, fontweight='bold')

        modules_list = list(self.data.keys())
        x_pos = np.arange(len(modules_list))

        # 提取碳排放数据
        carbon_intensity_kg = []
        carbon_intensity_mj = []
        vs_traditional = []

        for module in modules_list:
            carbon_data = self.data[module]['carbon']
            carbon_intensity_kg.append(carbon_data.get('carbon_intensity_kg', 0))
            carbon_intensity_mj.append(carbon_data.get('carbon_intensity_mj', 0))
            vs_traditional.append(carbon_data.get('vs_traditional_jet', 0))

        color_map = {m: self.modules[m]['color'] for m in modules_list}
        colors = [color_map[m] for m in modules_list]

        # === 子图1: 碳强度 (kg CO2/kg SAF) ===
        ax1 = axes[0]
        bars1 = ax1.bar(x_pos, carbon_intensity_kg, color=colors, alpha=0.7, edgecolor='black', linewidth=1.5)

        for bar, val in zip(bars1, carbon_intensity_kg):
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height,
                    f'{val:.2f}',
                    ha='center', va='bottom', fontsize=7, fontweight='bold')

        ax1.set_ylabel('碳强度 | Carbon Intensity\n(kg CO₂/kg SAF)', fontsize=12)
        ax1.set_title('质量基碳强度 | Mass-based CI', fontsize=13, fontweight='bold')
        ax1.set_xticks(x_pos)
        ax1.set_xticklabels([self.modules[m]['name_cn'] for m in modules_list], fontsize=8, rotation=45, ha='right')
        ax1.grid(axis='y', alpha=0.3)

        # === 子图2: 碳强度 (g CO2/MJ) ===
        ax2 = axes[1]
        bars2 = ax2.bar(x_pos, carbon_intensity_mj, color=colors, alpha=0.7, edgecolor='black', linewidth=1.5)

        for bar, val in zip(bars2, carbon_intensity_mj):
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height,
                    f'{val:.1f}',
                    ha='center', va='bottom', fontsize=7, fontweight='bold')

        ax2.set_ylabel('碳强度 | Carbon Intensity\n(g CO₂/MJ)', fontsize=12)
        ax2.set_title('能量基碳强度 | Energy-based CI', fontsize=13, fontweight='bold')
        ax2.set_xticks(x_pos)
        ax2.set_xticklabels([self.modules[m]['name_cn'] for m in modules_list], fontsize=8, rotation=45, ha='right')
        ax2.grid(axis='y', alpha=0.3)

        # === 子图3: 相对传统航油减排比例 ===
        ax3 = axes[2]

        # 区分正负值的颜色
        colors_vs = ['green' if v < 0 else 'red' for v in vs_traditional]
        bars3 = ax3.bar(x_pos, vs_traditional, color=colors_vs, alpha=0.7, edgecolor='black', linewidth=1.5)

        for bar, val in zip(bars3, vs_traditional):
            height = bar.get_height()
            va = 'top' if val < 0 else 'bottom'
            y_pos = height - 2 if val < 0 else height + 2
            ax3.text(bar.get_x() + bar.get_width()/2., y_pos,
                    f'{val:.1f}%',
                    ha='center', va=va, fontsize=7, fontweight='bold')

        # 添加0线
        ax3.axhline(y=0, color='black', linestyle='-', linewidth=1)

        ax3.set_ylabel('相对传统航油减排 (%)\nReduction vs Jet Fuel (%)', fontsize=12)
        ax3.set_title('减排效果 | Emission Reduction', fontsize=13, fontweight='bold')
        ax3.set_xticks(x_pos)
        ax3.set_xticklabels([self.modules[m]['name_cn'] for m in modules_list], fontsize=8, rotation=45, ha='right')
        ax3.grid(axis='y', alpha=0.3)

        # 添加减排效果说明
        ax3.text(0.02, 0.98, '负值 = 减排\n正值 = 增排',
                transform=ax3.transAxes,
                verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5),
                fontsize=9)

        plt.tight_layout()

        # 保存图片
        output_path = self.session_dir / "carbon_emissions_comparison.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        logger.info(f"  ✓ 保存图片: {output_path}")
        plt.close()

    def visualize_lcoe(self):
        """可视化生命周期平准化成本 (LCOE)"""
        logger.info("\n生成生命周期平准化成本对比图...")

        # 创建图形 - 调整宽度适配13个场景
        fig, ax = plt.subplots(figsize=(17, 8))
        fig.suptitle('生命周期平准化成本对比 | Levelized Cost of Energy (LCOE) Comparison',
                    fontsize=18, fontweight='bold')

        modules_list = list(self.data.keys())
        x_pos = np.arange(len(modules_list))

        # 读取LCOE（元/kg SAF）
        lcoe_values = []

        for module in modules_list:
            solution_data = self.data[module]['solution']
            lcoe = solution_data.get('lifecycle_levelized_cost_excluding_shortage_per_kg', 0)
            lcoe_values.append(lcoe)

        # 绘制柱状图
        color_map = {m: self.modules[m]['color'] for m in modules_list}
        colors = [color_map[m] for m in modules_list]

        bars = ax.bar(x_pos, lcoe_values, color=colors, alpha=0.7, edgecolor='black', linewidth=1.5)

        # 添加数值标签
        for bar, val in zip(bars, lcoe_values):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                    f'{val:.1f}',
                    ha='center', va='bottom', fontsize=8, fontweight='bold')

        ax.set_ylabel('LCOE（元/kg SAF）| LCOE (CNY/kg SAF)', fontsize=13)
        ax.set_title('SAF生产平准化成本 | SAF Production LCOE', fontsize=14, fontweight='bold')
        ax.set_xticks(x_pos)
        ax.set_xticklabels([self.modules[m]['name_cn'] for m in modules_list], rotation=45, ha='right', fontsize=9)
        ax.grid(axis='y', alpha=0.3)

        # 添加航油价格参考线（假设传统航油价格约8元/kg）
        traditional_price = 8.0
        ax.axhline(y=traditional_price, color='red', linestyle='--', linewidth=2,
                   label=f'传统航油参考价格 ~{traditional_price}元/kg', alpha=0.7)
        ax.legend(loc='upper left')

        plt.tight_layout()

        # 保存图片
        output_path = self.session_dir / "lcoe_comparison.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        logger.info(f"  ✓ 保存图片: {output_path}")
        plt.close()

    def generate_summary_table(self):
        """生成汇总表格"""
        logger.info("\n生成汇总表格...")

        # 创建汇总数据
        summary_data = []

        for module in self.data.keys():
            solution_data = self.data[module]['solution']
            carbon_data = self.data[module]['carbon']

            lcoe = solution_data.get('lifecycle_levelized_cost_excluding_shortage_per_kg', 0)
            total_cost = solution_data.get('total_cost_excluding_shortage', 0)
            production_kg = solution_data.get('lifecycle_total_production_kg', 0)

            summary_data.append({
                '场景 Scenario': f"{self.modules[module]['name_cn']}",
                '总成本 Total Cost (亿元)': f"{total_cost / 1e9:.2f}",
                '投资成本 Investment (亿元)': f"{solution_data.get('total_investment_cost', 0) / 1e9:.2f}",
                '运营成本 Operation (亿元)': f"{solution_data.get('total_operation_cost', 0) / 1e9:.2f}",
                '总产量 Production (千吨)': f"{production_kg / 1e6:.2f}",
                '需求满足率 Fulfillment (%)': f"{solution_data.get('demand_fulfillment_ratio', 0) * 100:.1f}",
                'LCOE (元/kg)': f"{lcoe:.2f}",
                '碳强度 CI (kg CO₂/kg SAF)': f"{carbon_data.get('carbon_intensity_kg', 0):.2f}",
                '碳强度 CI (g CO₂/MJ)': f"{carbon_data.get('carbon_intensity_mj', 0):.1f}",
                '相对减排 Reduction (%)': f"{carbon_data.get('vs_traditional_jet', 0):.1f}"
            })

        # 创建DataFrame
        df = pd.DataFrame(summary_data)

        # 保存为CSV
        csv_path = self.session_dir / "summary_table.csv"
        df.to_csv(csv_path, index=False, encoding='utf-8-sig')
        logger.info(f"  ✓ 保存CSV: {csv_path}")

        # 保存为Excel
        excel_path = self.session_dir / "summary_table.xlsx"
        df.to_excel(excel_path, index=False, engine='openpyxl')
        logger.info(f"  ✓ 保存Excel: {excel_path}")

        # 打印表格
        logger.info("\n" + "=" * 120)
        logger.info("汇总表格 | Summary Table")
        logger.info("=" * 120)
        try:
            print(df.to_string(index=False))
        except UnicodeEncodeError:
            logger.info("  (控制台编码限制，无法显示特殊字符，请查看CSV/Excel文件)")
        logger.info("=" * 120)

    def run_all_visualizations(self):
        """运行所有可视化"""
        logger.info("\n" + "=" * 80)
        logger.info("开始生成可视化")
        logger.info("=" * 80)

        try:
            # 生成各类可视化
            self.visualize_cost_breakdown()
            self.visualize_demand_fulfillment()
            self.visualize_carbon_emissions()
            self.visualize_lcoe()
            self.generate_summary_table()

            logger.info("\n" + "=" * 80)
            logger.info("✓ 所有可视化生成完成")
            logger.info(f"✓ 输出目录: {self.session_dir}")
            logger.info("=" * 80)

        except Exception as e:
            logger.error(f"\n✗ 可视化生成失败: {e}")
            raise


def main():
    """主函数"""
    logger.info("=" * 80)
    logger.info("十三场景对比可视化脚本")
    logger.info("Thirteen Scenarios Comparison Visualization Script")
    logger.info("=" * 80)

    try:
        # 创建可视化器
        visualizer = ThirteenScenariosComparisonVisualizer()

        # 加载数据
        visualizer.load_data()

        # 检查是否有足够的数据
        if len(visualizer.data) < 2:
            logger.error(f"✗ 数据不足：只找到 {len(visualizer.data)} 个场景的数据，至少需要2个")
            logger.error("  请先运行各场景的优化器生成结果文件")
            return

        # 运行所有可视化
        visualizer.run_all_visualizations()

        logger.info("\n✓ 程序执行成功")

    except Exception as e:
        logger.error(f"\n✗ 程序执行失败: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
