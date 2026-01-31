"""
SAF场景象限图可视化
Quadrant Chart Visualization for SAF Scenarios

功能：
- X轴：碳强度差值（方案 - 传统航煤，g CO2eq/MJ），以0为分界点（负值表示减排）
- Y轴：LCOE成本（元/kg），以8元/kg（SAF市场售价）为分界点
- 四象限背景色区分不同区域
- 点颜色表示场景类型

作者：Claude Code
创建时间：2026-01-05
"""

import json
import glob
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.font_manager import FontProperties
from matplotlib.ticker import MultipleLocator
try:
    from adjustText import adjust_text
except ImportError:
    adjust_text = None

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class QuadrantChartVisualizer:
    """SAF场景象限图可视化器"""

    def __init__(self, cost_threshold: float = 8.0, carbon_threshold: float = 0.0):
        """
        初始化可视化器

        Args:
            cost_threshold: 成本分界点（元/kg），默认8元（SAF市场售价）
            carbon_threshold: 碳强度差值分界点（g CO2eq/MJ），默认0
        """
        self.cost_threshold = cost_threshold
        self.carbon_threshold = carbon_threshold

        # 传统航煤基准碳强度（g CO2eq/MJ），用于参考线与回退计算
        self.traditional_jet_ci_gco2e_per_mj = None

        # 输出目录
        base_dir = Path(__file__).parent
        self.output_dir = base_dir / "results"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 创建带时间戳的子目录
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = self.output_dir / f"quadrant_chart_{timestamp}"
        self.session_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"输出目录: {self.session_dir}")

        # 项目根目录
        self.project_root = Path(__file__).parent.parent.parent.parent

        # 场景配置 - 使用新命名规范（Grey/Blue/Green三色系）
        # 颜色需与 Polar Charts 保持一致 (Pastel/Soft tones)
        self.modules = {
            # ========== Grey灰色系 - 煤基路径 (2个) ==========
            'Coal Hydrogen': {
                'name_en': 'CTL',
                'category': 'Grey',
                'color': '#616161',  # Deeper Grey
                'solution_pattern': str(self.project_root / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/complete_solution_*.json'),
                'carbon_pattern': str(self.project_root / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/carbon_emissions_detailed_*.json')
            },
            'Byproduct H2 + Coal': {
                'name_en': 'CTL-BH',
                'category': 'Grey',
                'color': '#9E9E9E',  # Grey
                'solution_pattern': str(self.project_root / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/byproduct_hydrogen/complete_solution_*.json'),
                'carbon_pattern': str(self.project_root / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/byproduct_hydrogen/carbon_emissions_detailed_*.json')
            },
            # ========== Green绿色系 - 绿氢路径 (4个) ==========
            'DAC Two-Step': {
                'name_en': 'DAC-GH-MTJ',
                'category': 'Green',
                'color': '#2E7D32',  # Deeper Green
                'solution_pattern': str(self.project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/two_step/complete_solution_*.json'),
                'carbon_pattern': str(self.project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/two_step/carbon_emissions_detailed_*.json')
            },
            'DAC One-Step': {
                'name_en': 'DAC-GH-FT',
                'category': 'Green',
                'color': '#43A047',  # Green
                'solution_pattern': str(self.project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/one_step/complete_solution_*.json'),
                'carbon_pattern': str(self.project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/one_step/carbon_emissions_detailed_*.json')
            },
            'Green H2 Two-Step': {
                'name_en': 'CCU-GH-MTJ',
                'category': 'Green',
                'color': '#66BB6A',  # Medium Green
                'solution_pattern': str(self.project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/two_step/complete_solution_*.json'),
                'carbon_pattern': str(self.project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/two_step/carbon_emissions_detailed_*.json')
            },
            'Green H2 One-Step': {
                'name_en': 'CCU-GH-FT',
                'category': 'Green',
                'color': '#81C784',  # Light Green
                'solution_pattern': str(self.project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/one_step/complete_solution_*.json'),
                'carbon_pattern': str(self.project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/one_step/carbon_emissions_detailed_*.json')
            },
            # ========== Blue蓝色系 - 副产氢/天然气路径 (7个) ==========
            'Natural Gas Two-Step': {
                'name_en': 'GTL-GH-MTJ',
                'category': 'Blue',
                'color': '#1565C0',  # Deeper Blue
                'solution_pattern': str(self.project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/complete_solution_*.json'),
                'carbon_pattern': str(self.project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/carbon_emissions_detailed_*.json')
            },
            'Natural Gas One-Step': {
                'name_en': 'GTL-GH-FT',
                'category': 'Blue',
                'color': '#1E88E5',  # Blue
                'solution_pattern': str(self.project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/ft_one_step/complete_solution_*.json'),
                'carbon_pattern': str(self.project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/ft_one_step/carbon_emissions_detailed_*.json')
            },
            'Byproduct H2 + DAC Two-Step': {
                'name_en': 'DAC-BH-MTJ',
                'category': 'Blue',
                'color': '#42A5F5',  # Medium Blue
                'solution_pattern': str(self.project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/two_step/complete_solution_*.json'),
                'carbon_pattern': str(self.project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/two_step/carbon_emissions_detailed_*.json')
            },
            'Byproduct H2 + DAC One-Step': {
                'name_en': 'DAC-BH-FT',
                'category': 'Blue',
                'color': '#64B5F6',  # Light Blue
                'solution_pattern': str(self.project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/one_step/complete_solution_*.json'),
                'carbon_pattern': str(self.project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/one_step/carbon_emissions_detailed_*.json')
            },
            'Byproduct H2 + NG Two-Step': {
                'name_en': 'GTL-BH-MTJ',
                'category': 'Blue',
                'color': '#90CAF9',  # Pale Blue
                'solution_pattern': str(self.project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/byproduct_hydrogen/byproduct_hydrogen/two_step/complete_solution_*.json'),
                'carbon_pattern': str(self.project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/byproduct_hydrogen/byproduct_hydrogen/two_step/carbon_emissions_detailed_*.json')
            },
            'Byproduct H2 Two-Step': {
                'name_en': 'CCU-BH-MTJ',
                'category': 'Blue',
                'color': '#BBDEFB',  # Very Pale Blue
                'solution_pattern': str(self.project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/two_step/complete_solution_*.json'),
                'carbon_pattern': str(self.project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/two_step/carbon_emissions_detailed_*.json')
            },
            'Byproduct H2 One-Step': {
                'name_en': 'CCU-BH-FT',
                'category': 'Blue',
                'color': '#E3F2FD',  # Very Light Blue
                'solution_pattern': str(self.project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/one_step/complete_solution_*.json'),
                'carbon_pattern': str(self.project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/one_step/carbon_emissions_detailed_*.json')
            }
        }

        # 类别颜色映射（三色系）
        self.category_colors = {
            'Grey': '#616161',
            'Blue': '#1565C0',
            'Green': '#2E7D32'
        }

        # 数据存储
        self.data = {}

    def load_data(self):
        """加载所有场景数据"""
        logger.info("=" * 60)
        logger.info("加载场景数据")
        logger.info("=" * 60)

        for module_name, config in self.modules.items():
            logger.info(f"\nLoading: {module_name} ({config['name_en']})")

            try:
                # 查找最新的解决方案文件
                solution_files = sorted(glob.glob(config['solution_pattern']), reverse=True)
                if not solution_files:
                    logger.warning(f"  未找到解决方案文件")
                    continue

                solution_path = Path(solution_files[0])
                with open(solution_path, 'r', encoding='utf-8') as f:
                    solution_data = json.load(f)

                # 查找最新的碳排放文件
                carbon_files = sorted(glob.glob(config['carbon_pattern']), reverse=True)
                if not carbon_files:
                    logger.warning(f"  未找到碳排放文件")
                    continue

                carbon_path = Path(carbon_files[0])
                with open(carbon_path, 'r', encoding='utf-8') as f:
                    carbon_data = json.load(f)

                # 提取关键数据
                lcoe = solution_data.get('lifecycle_levelized_cost_excluding_shortage_per_kg', 0)
                production = solution_data.get('lifecycle_total_production_kg', 0) / 1e6  # 转换为千吨

                # X轴：碳强度差值（方案 - 传统航煤），负值=减排
                traditional_jet_ci = carbon_data.get('traditional_jet_ci_gco2e_per_mj', 89)
                if self.traditional_jet_ci_gco2e_per_mj is None:
                    self.traditional_jet_ci_gco2e_per_mj = traditional_jet_ci

                carbon_diff = carbon_data.get('abs_diff_vs_traditional_jet_gco2e_per_mj', None)
                if carbon_diff is None:
                    if 'carbon_intensity_mj' in carbon_data:
                        carbon_diff = carbon_data.get('carbon_intensity_mj', 0) - traditional_jet_ci
                    else:
                        vs_traditional = carbon_data.get('vs_traditional_jet', 0)
                        carbon_diff = traditional_jet_ci * (vs_traditional / 100.0)

                self.data[module_name] = {
                    'name_en': config['name_en'],
                    'category': config['category'],
                    'color': config['color'],
                    'lcoe': lcoe,
                    'carbon_diff': carbon_diff,
                    'production': production,
                }

                logger.info(f"  LCOE: {lcoe:.2f} 元/kg")
                logger.info(f"  碳强度差值: {carbon_diff:.2f} g CO2eq/MJ")
                logger.info(f"  产量: {production:.1f} 千吨")

            except Exception as e:
                logger.error(f"  加载失败: {e}")
                continue

        logger.info(f"\n成功加载 {len(self.data)} 个场景")

    def plot_quadrant_chart(self):
        """绑制象限图 - 统一风格版"""
        logger.info("\n生成象限图...")

        # 设置字体
        plt.rcParams['font.family'] = ['Times New Roman', 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False

        # 创建图形
        fig = plt.figure(figsize=(14, 11)) # 稍大一点用以容纳大字体

        # 使用gridspec创建布局：主图占满
        gs = fig.add_gridspec(1, 1, left=0.10, right=0.95, top=0.92, bottom=0.10)
        ax = fig.add_subplot(gs[0, 0])

        # 获取数据范围
        x_values = [d['carbon_diff'] for d in self.data.values()]
        y_values = [d['lcoe'] for d in self.data.values()]

        # X轴范围
        x_data_min = min(x_values)
        x_data_max = max(x_values)
        x_margin = max(10, (x_data_max - x_data_min) * 0.15)
        x_min = x_data_min - x_margin
        x_max = x_data_max + x_margin

        # Y轴范围
        y_data_min = min(y_values)
        y_margin = 4
        y_min = max(0, y_data_min - y_margin)
        y_max = max(y_values) + y_margin

        # ========== 绘制四象限背景色 (更淡雅的颜色) ==========
        # ========== 绘制四象限背景色 (更淡雅的颜色) ==========
        # 左下：浅绿（低排+低成本 -> 理想区域）
        ax.fill_between([x_min, self.carbon_threshold], y_min, self.cost_threshold,
                color='#F1F8E9', alpha=0.6, zorder=0)
        # 左上：白色（低排+高成本 -> 技术可行但贵）
        ax.fill_between([x_min, self.carbon_threshold], self.cost_threshold, y_max,
            color='#FFFFFF', alpha=1.0, zorder=0)
        # 右下：浅橙（高排+低成本 -> 经济但不够环保）
        ax.fill_between([self.carbon_threshold, x_max], y_min, self.cost_threshold,
                color='#FFF3E0', alpha=0.6, zorder=0)
        # 右上：浅红（高排+高成本 -> 需避免）
        ax.fill_between([self.carbon_threshold, x_max], self.cost_threshold, y_max,
                color='#FFEBEE', alpha=0.6, zorder=0)

        # ========== 绘制分界线（灰色虚线） ==========
        ax.axvline(x=self.carbon_threshold, color='#999999', linestyle='--', linewidth=1.5, zorder=1)
        ax.axhline(y=self.cost_threshold, color='#999999', linestyle='--', linewidth=1.5, zorder=1)

        # ========== 象限标注（大字体） ==========
        # 顶部标注（图外）
        ax.text(x_min + (self.carbon_threshold - x_min) / 2, y_max + 0.5,
                'Lower emission', fontsize=14, ha='center', va='bottom', fontweight='bold', color='#555555')
        ax.text(self.carbon_threshold + (x_max - self.carbon_threshold) / 2, y_max + 0.5,
                'Higher emission', fontsize=14, ha='center', va='bottom', fontweight='bold', color='#555555')
        # 右侧标注（图外）
        text_x_pos = x_max + 2
        ax.text(text_x_pos, self.cost_threshold + (y_max - self.cost_threshold)/2, 'Higher\ncost', 
                fontsize=14, ha='left', va='center', fontweight='bold', color='#555555')
        ax.text(text_x_pos, y_min + (self.cost_threshold - y_min)/2, 'Lower\ncost', 
                fontsize=14, ha='left', va='center', fontweight='bold', color='#555555')

        # ========== 绘制气泡散点 ==========
        # 收集所有散点坐标和标签文本
        texts = []
        scatter_x = []
        scatter_y = []

        # 固定点大小（不再使用MAC映射）
        fixed_size = 420

        for module_name, data in self.data.items():
            x = data['carbon_diff']
            y = data['lcoe']
            scatter_x.append(x)
            scatter_y.append(y)

            size = fixed_size
            
            # 颜色
            fill_color = data['color']
            
            # 绘点 - 去除边缘黑色
            ax.scatter(x, y, s=size, c=fill_color, alpha=0.9,
                      edgecolors='none', zorder=5)

            # 添加标签文本对象
            text = ax.text(x, y, data['name_en'], fontsize=12, color='#333333', fontweight='normal', zorder=10)
            texts.append(text)

        # ========== 设置轴标签（大字体） ==========
        ax.set_xlabel('Carbon intensity difference vs traditional jet fuel (g CO2eq/MJ)',
                      fontsize=16, labelpad=15, fontweight='bold')
        ax.set_ylabel('Levelized cost of energy (CNY/kg)',
                      fontsize=16, labelpad=15, fontweight='bold')

        # ========== 设置轴范围和网格 ==========
        ax.set_xlim(x_min, x_max - 5) 
        ax.set_ylim(y_min, y_max)

        # 设置网格
        ax.xaxis.set_major_locator(MultipleLocator(200))
        ax.yaxis.set_major_locator(MultipleLocator(20))
        ax.grid(True, linestyle='--', alpha=0.5, color='#aaaaaa', dashes=(4, 4))

        # ========== 使用adjustText自动调整标签位置 ==========
        if adjust_text:
            try:
                adjust_text(texts,
                           x=scatter_x,
                           y=scatter_y,
                           ax=ax,
                           arrowprops=dict(arrowstyle='-', color='#666666', lw=0.8),
                           force_text=(0.5, 1.0),
                           force_static=(1.0, 1.5),
                           force_pull=(0.1, 0.1),
                           expand=(1.2, 1.4),
                           ensure_inside_axes=True,
                           iter_lim=1000)
            except Exception as e:
                logger.warning(f"adjust_text running failed: {e}")
        else:
             logger.warning("adjustText module not found, skipping label adjustment.")

        # ========== 设置刻度字体 ==========
        ax.tick_params(axis='both', which='major', labelsize=16)

        # 显示四周边框
        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_linewidth(1.2)
            spine.set_color('#666666')

        # ========== 创建图例 ==========
        # 1. Scenarios Legend
        from matplotlib.lines import Line2D
        
        # 顺序
        pathway_order = {
            'Grey': ['CTL', 'CTL-BH'],
            'Blue': ['DAC-BH-MTJ', 'DAC-BH-FT', 'GTL-BH-MTJ', 'GTL-GH-MTJ', 'GTL-GH-FT', 'CCU-BH-MTJ', 'CCU-BH-FT'],
            'Green': ['DAC-GH-MTJ', 'DAC-GH-FT', 'CCU-GH-MTJ', 'CCU-GH-FT']
        }

        scenario_handles = []
        # 按Grey, Blue, Green顺序添加
        for group in ['Grey', 'Blue', 'Green']:
            for name in pathway_order[group]:
                for d in self.data.values():
                    if d['name_en'] == name:
                        # 圆形图标
                        h = Line2D([0], [0], marker='o', color='w', markerfacecolor=d['color'],
                                  markersize=10, label=name, linestyle='None')
                        scenario_handles.append(h)
                        break

        # Legend 1: Scenarios (Inside Top-Right, Far Right)
        # 放在红色区域内，靠右。
        # bbox_to_anchor=(x, y) where x,y are in axes coordinates.
        # Top-Right is (1, 1). To be inside, use e.g. (0.98, 0.98).
        legend_scenarios = ax.legend(handles=scenario_handles, loc='upper right',
                           title='Scenarios', title_fontsize=12,
                           fontsize=11, framealpha=0.8, edgecolor='#cccccc',
                           facecolor='white',
                           bbox_to_anchor=(0.99, 0.99), # Inside, Top-Right
                           ncol=1, 
                           handletextpad=0.5,
                           labelspacing=0.5)
        legend_scenarios.get_title().set_fontweight('bold')
        ax.add_artist(legend_scenarios) 

        # 不再绘制“点大小”图例（MAC相关）
        
        # Quadrant Explanations Legend (Optional, simplify visually)
        # 可以省略背景色图例，因为已经有大字标注了

        # ========== 添加阈值标注 ==========
        ax.text(self.carbon_threshold + 2, y_min + 0.5, f'Baseline: {self.carbon_threshold} g CO2eq/MJ',
                fontsize=12, color='#666666', va='bottom', fontweight='bold')
        ax.text(x_min + 5, self.cost_threshold + 0.2, f'Market Price: {self.cost_threshold} CNY/kg',
                fontsize=12, color='#666666', va='bottom', fontweight='bold')

        # 添加 -10% 和 -70% 的参考线（映射到绝对差值：diff = -ratio * traditional_jet_ci）
        traditional_jet_ci = self.traditional_jet_ci_gco2e_per_mj or 89
        ref_10 = -0.10 * traditional_jet_ci
        ref_70 = -0.70 * traditional_jet_ci
        ax.axvline(x=ref_10, color='#AAAAAA', linestyle='-.', linewidth=1.2, alpha=0.8)
        ax.axvline(x=ref_70, color='#AAAAAA', linestyle='-.', linewidth=1.2, alpha=0.8)
        
        # 添加参考线标注：放在图内稍靠中间（点/标签下方一点）以减少遮挡
        # 使用x轴坐标变换：x用数据坐标，y用轴坐标(0-1)
        label_bbox = dict(facecolor='white', edgecolor='none', alpha=0.7, pad=0.2)
        label_y_ax = 0.90
        ax.text(ref_10 - 1, label_y_ax, f'{ref_10:.1f} g/MJ (10% reduction)', rotation=90,
            fontsize=14, color='#555555', va='top', ha='right',
            transform=ax.get_xaxis_transform(), bbox=label_bbox)
        ax.text(ref_70 - 1, label_y_ax, f'{ref_70:.1f} g/MJ (70% reduction)', rotation=90,
            fontsize=14, color='#555555', va='top', ha='right',
            transform=ax.get_xaxis_transform(), bbox=label_bbox)

        # 保存图片
        output_path = self.session_dir / "quadrant_chart.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
        
        # 保存Latest
        latest_path = self.output_dir / "quadrant_chart_latest.png"
        plt.savefig(latest_path, dpi=300, bbox_inches='tight', facecolor='white')
        logger.info(f"保存图片: {output_path}")

        plt.close()

        return output_path

    def generate_summary(self):
        """生成数据汇总表"""
        logger.info("\nGenerating summary...")

        # 三色系类别标签映射
        category_labels = {
            'Grey': 'Grey (Coal-based)',
            'Blue': 'Blue (BH/NG)',
            'Green': 'Green (GH)'
        }

        summary_data = []
        for module_name, data in self.data.items():
            # 判断所属象限
            is_green = data['carbon_diff'] < self.carbon_threshold
            is_economic = data['lcoe'] < self.cost_threshold

            if is_green and is_economic:
                quadrant = 'I-Green&Economic'
            elif not is_green and is_economic:
                quadrant = 'II-Economic'
            elif is_green and not is_economic:
                quadrant = 'III-Green'
            else:
                quadrant = 'IV-Neither'

            summary_data.append({
                'Scenario': data['name_en'],
                'Category': category_labels.get(data['category'], data['category']),
                'LCOE (CNY/kg)': f"{data['lcoe']:.2f}",
                'Carbon Diff (g CO2eq/MJ)': f"{data['carbon_diff']:.2f}",
                'Production (kt)': f"{data['production']:.1f}",
                'Quadrant': quadrant
            })

        df = pd.DataFrame(summary_data)

        # 保存CSV
        csv_path = self.session_dir / "quadrant_summary.csv"
        df.to_csv(csv_path, index=False, encoding='utf-8-sig')
        logger.info(f"Saved summary: {csv_path}")

        # 打印表格
        logger.info("\n" + "=" * 80)
        logger.info("Quadrant Analysis Summary")
        logger.info("=" * 80)
        print(df.to_string(index=False))

        return df

    def run(self):
        """运行可视化"""
        logger.info("=" * 60)
        logger.info("SAF场景象限图可视化")
        logger.info("=" * 60)

        # 加载数据
        self.load_data()

        if len(self.data) < 2:
            logger.error(f"数据不足：只找到 {len(self.data)} 个场景")
            return None

        # 生成象限图
        chart_path = self.plot_quadrant_chart()

        # 生成汇总
        self.generate_summary()

        logger.info("\n" + "=" * 60)
        logger.info(f"可视化完成！输出目录: {self.session_dir}")
        logger.info("=" * 60)

        return chart_path


def main():
    """主函数"""
    visualizer = QuadrantChartVisualizer(
        cost_threshold=8.0,  # SAF市场售价
        carbon_threshold=0.0   # 碳排放分界点
    )
    visualizer.run()


if __name__ == "__main__":
    main()
