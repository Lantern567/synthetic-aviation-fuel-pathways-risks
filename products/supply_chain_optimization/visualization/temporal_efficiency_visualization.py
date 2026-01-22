# -*- coding: utf-8 -*-
"""
时间维度效率可视化模块
Temporal Efficiency Visualization Module

功能 | Features:
1. 图T-Ely: 电解槽效率状态散点图 - 展示周度电解槽利用率（叠加产量折线）
2. 图T-SAF: SAF工厂效率分布箱线图 - 按周展示SAF工厂利用率分布（叠加产量折线）

核心指标 | Key Metrics:
- U_w^ely = H_w^prod / (Cap_ely × T_w)  电解槽周度利用率
- η_w^SAF = Q_w^SAF / (Cap_SAF × T_w)   SAF工厂周度利用率
- P_w^SAF = 周度SAF产量（直接生产数据）

作者 | Author: Claude Code
创建时间 | Created: 2026-01-22
"""

import glob
import json
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import matplotlib as mpl
import numpy as np
import pandas as pd
import seaborn as sns

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


def setup_fonts():
    """设置字体：英文Times New Roman，中文宋体"""
    plt.rcParams['font.family'] = ['serif']
    plt.rcParams['font.serif'] = ['Times New Roman', 'DejaVu Serif', 'SimSun']
    plt.rcParams['font.sans-serif'] = ['SimSun', 'SimHei', 'Noto Sans CJK SC', 'Microsoft YaHei']
    plt.rcParams['axes.unicode_minus'] = False
    plt.rcParams['mathtext.fontset'] = 'stix'


def pick_latest(pattern: Path) -> Optional[Path]:
    """获取匹配模式的最新文件（按修改时间排序）"""
    files = glob.glob(str(pattern))
    if not files:
        return None
    files.sort(key=lambda p: Path(p).stat().st_mtime, reverse=True)
    return Path(files[0])


class TemporalEfficiencyVisualizer:
    """时间维度效率可视化器"""

    # 13场景配置
    SCENARIOS = {
        # ========== 绿氢场景 (7个) ==========
        'Coal Hydrogen': {
            'name_cn': '煤制氢',
            'category': 'Grey',
            'pathway': 'Two-Step',
            'color': '#E74C3C',
            'solution_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/complete_solution_*.json',
            'hourly_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/hourly_production_summary_*.csv',
        },
        'DAC Two-Step': {
            'name_cn': 'DAC两步法',
            'category': 'Green',
            'pathway': 'Two-Step',
            'color': '#3498DB',
            'solution_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/two_step/complete_solution_*.json',
            'hourly_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/two_step/hourly_production_summary_*.csv',
        },
        'DAC One-Step': {
            'name_cn': 'DAC一步法',
            'category': 'Green',
            'pathway': 'One-Step',
            'color': '#5DADE2',
            'solution_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/one_step/complete_solution_*.json',
            'hourly_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/one_step/hourly_production_summary_*.csv',
        },
        'Natural Gas Two-Step': {
            'name_cn': '天然气两步法',
            'category': 'Blue',
            'pathway': 'Two-Step',
            'color': '#2ECC71',
            'solution_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/complete_solution_*.json',
            'hourly_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/hourly_production_summary_*.csv',
        },
        'Natural Gas One-Step': {
            'name_cn': '天然气一步法',
            'category': 'Blue',
            'pathway': 'One-Step',
            'color': '#F39C12',
            'solution_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/ft_one_step/complete_solution_*.json',
            'hourly_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/ft_one_step/hourly_production_summary_*.csv',
        },
        'Green H2 Two-Step': {
            'name_cn': '绿氢两步法',
            'category': 'Green',
            'pathway': 'Two-Step',
            'color': '#9B59B6',
            'solution_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/two_step/complete_solution_*.json',
            'hourly_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/two_step/hourly_production_summary_*.csv',
        },
        'Green H2 One-Step': {
            'name_cn': '绿氢一步法',
            'category': 'Green',
            'pathway': 'One-Step',
            'color': '#C39BD3',
            'solution_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/one_step/complete_solution_*.json',
            'hourly_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/one_step/hourly_production_summary_*.csv',
        },
        # ========== 副产氢场景 (6个) ==========
        'Byproduct H2 + Coal': {
            'name_cn': '副产氢+煤',
            'category': 'Grey',
            'pathway': 'Two-Step',
            'color': '#FF6B6B',
            'solution_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/byproduct_hydrogen/complete_solution_*.json',
            'hourly_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/byproduct_hydrogen/hourly_production_summary_*.csv',
        },
        'Byproduct H2 + DAC Two-Step': {
            'name_cn': '副产氢+DAC两步',
            'category': 'Green',
            'pathway': 'Two-Step',
            'color': '#4ECDC4',
            'solution_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/two_step/complete_solution_*.json',
            'hourly_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/two_step/hourly_production_summary_*.csv',
        },
        'Byproduct H2 + DAC One-Step': {
            'name_cn': '副产氢+DAC一步',
            'category': 'Green',
            'pathway': 'One-Step',
            'color': '#95E1D3',
            'solution_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/one_step/complete_solution_*.json',
            'hourly_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/one_step/hourly_production_summary_*.csv',
        },
        'Byproduct H2 + NG Two-Step': {
            'name_cn': '副产氢+天然气两步',
            'category': 'Blue',
            'pathway': 'Two-Step',
            'color': '#26DE81',
            'solution_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/byproduct_hydrogen/byproduct_hydrogen/two_step/complete_solution_*.json',
            'hourly_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/byproduct_hydrogen/byproduct_hydrogen/two_step/hourly_production_summary_*.csv',
        },
        'Byproduct H2 Two-Step': {
            'name_cn': '副产氢两步法',
            'category': 'Green',
            'pathway': 'Two-Step',
            'color': '#A29BFE',
            'solution_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/two_step/complete_solution_*.json',
            'hourly_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/two_step/hourly_production_summary_*.csv',
        },
        'Byproduct H2 One-Step': {
            'name_cn': '副产氢一步法',
            'category': 'Green',
            'pathway': 'One-Step',
            'color': '#DFE4EA',
            'solution_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/one_step/complete_solution_*.json',
            'hourly_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/one_step/hourly_production_summary_*.csv',
        },
    }

    # 类别颜色映射
    CATEGORY_COLORS = {
        'Grey': '#616161',   # 灰色系 - 煤基路径
        'Blue': '#1565C0',   # 蓝色系 - 天然气/副产氢路径
        'Green': '#2E7D32',  # 绿色系 - 绿氢/DAC路径
    }

    # 路径类型标记
    PATHWAY_MARKERS = {
        'One-Step': '^',  # FT路线 - 三角形
        'Two-Step': 'o',  # MTJ路线 - 圆形
    }

    def __init__(self, output_dir: str = None):
        """
        初始化可视化器

        Args:
            output_dir: 输出目录，默认为 visualization/results
        """
        if output_dir is None:
            output_dir = PROJECT_ROOT / "products" / "supply_chain_optimization" / "visualization" / "results"

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 创建带时间戳的子目录
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = self.output_dir / f"temporal_efficiency_{timestamp}"
        self.session_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"输出目录: {self.session_dir}")

        # 数据存储
        self.data = {}

        # 设置字体
        setup_fonts()

    def load_data(self):
        """加载所有场景的数据"""
        logger.info("=" * 80)
        logger.info("加载13场景数据")
        logger.info("=" * 80)

        for scenario_name, config in self.SCENARIOS.items():
            logger.info(f"\n正在加载: {scenario_name} ({config['name_cn']})")

            # 加载complete_solution JSON
            solution_file = pick_latest(config['solution_pattern'])
            if not solution_file:
                logger.warning(f"  未找到解决方案文件: {config['solution_pattern']}")
                continue

            logger.info(f"  解决方案文件: {solution_file.name}")

            with open(solution_file, 'r', encoding='utf-8') as f:
                solution_data = json.load(f)

            # 加载hourly_production_summary CSV
            hourly_file = pick_latest(config['hourly_pattern'])
            hourly_df = None
            if hourly_file:
                logger.info(f"  小时级生产文件: {hourly_file.name}")
                hourly_df = pd.read_csv(hourly_file)
            else:
                logger.warning(f"  未找到小时级生产文件: {config['hourly_pattern']}")

            # 计算每3小时时段的指标
            hourly_metrics = self.compute_hourly_metrics(
                solution_data, hourly_df, scenario_name, config
            )

            if hourly_metrics:
                self.data[scenario_name] = {
                    'config': config,
                    'solution': solution_data,
                    'hourly_metrics': hourly_metrics,
                }
                logger.info(f"  成功加载 {len(hourly_metrics)} 个时段数据（4周×56时段）")
            else:
                logger.warning(f"  无法计算周度指标")

        logger.info("\n" + "=" * 80)
        logger.info(f"数据加载完成 - 成功加载 {len(self.data)} 个场景")
        logger.info("=" * 80)

    def compute_hourly_metrics(
        self,
        solution_data: dict,
        hourly_df: Optional[pd.DataFrame],
        scenario_name: str,
        config: dict
    ) -> List[dict]:
        """
        计算每3小时时段的指标（不做周度聚合）

        公式:
        - U_t^ely = H_t^prod / Cap_ely   每时段电解槽利用率
        - η_t^SAF = Q_t^SAF / Cap_SAF    每时段SAF工厂利用率

        注意：hourly_production_summary中的产出数据是每小时的产出率，
        因此分母直接使用装机容量（kg/h），不需要乘以时段小时数。

        Args:
            solution_data: complete_solution JSON数据
            hourly_df: hourly_production_summary DataFrame
            scenario_name: 场景名称
            config: 场景配置

        Returns:
            List[dict]: 每个时段的指标列表
        """
        # 获取电解槽总容量
        h2_facilities = solution_data.get('hydrogen_facilities', {})
        total_h2_cap = sum(
            f.get('capacity_kg_h2_per_hour', 0)
            for f in h2_facilities.values()
        )

        # 获取SAF工厂总容量
        facilities = solution_data.get('facilities', {})
        total_saf_cap = sum(
            f.get('capacity_kg_per_hour', 0)
            for f in facilities.values()
        )

        hourly_metrics = []

        # 如果有hourly_df，从中计算每个时段的利用率
        if hourly_df is not None and not hourly_df.empty:
            # 确保列名正确 - 精确匹配列名
            h2_col = None
            saf_col = None
            period_col = None

            for col in hourly_df.columns:
                col_clean = col.strip().lstrip('\ufeff')
                # 精确匹配"时段"列（不包含其他文字）
                if col_clean == '时段' or col_clean.lower() == 'period':
                    period_col = col
                if '氢气产出' in col or 'hydrogen' in col.lower():
                    h2_col = col
                if 'SAF产出' in col or 'saf' in col.lower():
                    saf_col = col

            # 如果没有找到时段列，使用第一列
            if period_col is None:
                period_col = hourly_df.columns[0]
                logger.warning(f"  未找到'时段'列，使用第一列: {period_col}")

            periods_per_week = 56  # 每周56个3小时时段

            # 遍历每一行（每个3小时时段）
            for _, row in hourly_df.iterrows():
                period = int(row[period_col])
                week = period // periods_per_week

                # 只处理前4周的数据
                if week >= 4:
                    continue

                # 获取该时段的产量（实际是每小时产出率）
                h2_prod = float(row[h2_col]) if h2_col and pd.notna(row[h2_col]) else 0
                saf_prod = float(row[saf_col]) if saf_col and pd.notna(row[saf_col]) else 0

                # 计算该时段的利用率
                # 利用率 = 实际产出率 / 装机容量
                # 注意：产出数据是每小时的产出率，所以直接除以容量即可
                h2_util = h2_prod / total_h2_cap if total_h2_cap > 0 else 0
                saf_util = saf_prod / total_saf_cap if total_saf_cap > 0 else 0

                hourly_metrics.append({
                    'period': period,
                    'week': week,
                    'h2_production_kg': h2_prod,
                    'saf_production_kg': saf_prod,
                    'h2_capacity_kg_per_hour': total_h2_cap,
                    'saf_capacity_kg_per_hour': total_saf_cap,
                    'h2_utilization': min(h2_util, 1.0),  # 限制最大为1
                    'saf_utilization': min(saf_util, 1.0),
                    'scenario': scenario_name,
                    'category': config['category'],
                    'pathway': config['pathway'],
                })

        return hourly_metrics

    def compute_weekly_production_series(self, weeks: int = 4, reference_scenario: Optional[str] = None) -> Tuple[List[int], List[float]]:
        """计算4周产量折线数据（吨），默认使用参考场景的真实周度产量"""
        if reference_scenario and reference_scenario in self.data:
            metrics = self.data[reference_scenario]['weekly_metrics']
            weekly_vals = {int(m['week']): float(m['production_kg']) for m in metrics}
            production_ton = [weekly_vals.get(week, 0.0) / 1000.0 for week in range(weeks)]
            week_labels = [week + 1 for week in range(weeks)]
            return week_labels, production_ton

        if self.data:
            first_scenario = next(iter(self.data.keys()))
            metrics = self.data[first_scenario]['weekly_metrics']
            weekly_vals = {int(m['week']): float(m['production_kg']) for m in metrics}
            production_ton = [weekly_vals.get(week, 0.0) / 1000.0 for week in range(weeks)]
            week_labels = [week + 1 for week in range(weeks)]
            logger.info(f"产量折线使用参考场景: {first_scenario}")
            return week_labels, production_ton

        week_labels = [week + 1 for week in range(weeks)]
        return week_labels, [0.0] * weeks

    def plot_electrolyzer_efficiency_scatter(self):
        """
        绘制图T-Ely：电解槽效率时序图（使用每3小时时段数据）

        采用4个子图（每周一个），折线图展示各场景的利用率变化
        按类别(Grey/Blue/Green)分组，使用不同线型区分
        """
        logger.info("\n生成图T-Ely：电解槽效率时序图（3小时时段数据）...")

        # 收集所有数据点
        all_points = []
        for scenario_name, scenario_data in self.data.items():
            config = scenario_data['config']
            for metric in scenario_data['hourly_metrics']:
                if metric['h2_capacity_kg_per_hour'] > 0:  # 只绘制有电解槽的场景
                    all_points.append({
                        'period': metric['period'],
                        'week': metric['week'],
                        'period_in_week': metric['period'] % 56,  # 周内时段（0-55）
                        'h2_utilization': metric['h2_utilization'],
                        'scenario': scenario_name,
                        'category': config['category'],
                        'pathway': config['pathway'],
                        'color': config['color'],
                    })

        if not all_points:
            logger.warning("没有电解槽数据可绘制")
            return

        df = pd.DataFrame(all_points)

        # 创建2x2子图布局（4周）
        fig, axes = plt.subplots(2, 2, figsize=(16, 12), sharey=True)
        axes = axes.flatten()

        # 线型映射（按类别）
        linestyle_map = {
            'Grey': '-',
            'Blue': '--',
            'Green': ':',
        }

        # 为每周创建子图
        for week in range(4):
            ax = axes[week]
            week_df = df[df['week'] == week]

            # 按场景绘制折线
            for scenario_name in week_df['scenario'].unique():
                scenario_df = week_df[week_df['scenario'] == scenario_name].sort_values('period_in_week')
                config = self.data[scenario_name]['config']

                linestyle = linestyle_map.get(config['category'], '-')

                ax.plot(
                    scenario_df['period_in_week'] * 3,  # 转换为小时
                    scenario_df['h2_utilization'],
                    color=config['color'],
                    linestyle=linestyle,
                    linewidth=1.5,
                    alpha=0.8,
                    label=scenario_name if week == 0 else None  # 只在第一个子图添加图例
                )

            # 设置子图标题和标签
            ax.set_title(f'Week {week + 1}', fontsize=14, fontweight='bold')
            ax.set_xlabel('Hour in Week', fontsize=11)
            ax.set_ylabel('Electrolyzer Utilization', fontsize=11)
            ax.set_xlim(0, 168)
            ax.set_ylim(0, 1.05)
            ax.set_xticks([0, 42, 84, 126, 168])
            ax.grid(True, linestyle='--', alpha=0.3)

            # 添加利用率参考线
            ax.axhline(y=0.5, color='red', linestyle=':', alpha=0.4, linewidth=1)

        # 总标题
        fig.suptitle('T-Ely: Electrolyzer Utilization by Week (3-hour Resolution)',
                     fontsize=16, fontweight='bold', y=1.02)

        # 图例放在图外右侧
        handles, labels = axes[0].get_legend_handles_labels()
        fig.legend(handles, labels, loc='center left', bbox_to_anchor=(1.02, 0.5),
                   fontsize=9, title='Scenarios', title_fontsize=10, frameon=True)

        # 添加类别线型说明
        legend_elements = [
            plt.Line2D([0], [0], color='gray', linestyle='-', linewidth=2, label='Grey (Coal)'),
            plt.Line2D([0], [0], color='gray', linestyle='--', linewidth=2, label='Blue (NG)'),
            plt.Line2D([0], [0], color='gray', linestyle=':', linewidth=2, label='Green (H2/DAC)'),
        ]
        fig.legend(handles=legend_elements, loc='lower center', bbox_to_anchor=(0.5, -0.02),
                   ncol=3, fontsize=10, title='Category Line Style', title_fontsize=10)

        plt.tight_layout()

        # 保存
        output_path = self.session_dir / "electrolyzer_efficiency_scatter.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        logger.info(f"  保存图片: {output_path}")

        # 同时保存到results根目录（覆盖最新版本）
        latest_path = self.output_dir / "electrolyzer_efficiency_scatter_latest.png"
        plt.savefig(latest_path, dpi=300, bbox_inches='tight')
        logger.info(f"  保存最新版本: {latest_path}")

        plt.close()

    def plot_saf_efficiency_boxplot(self):
        """
        绘制图T-SAF：SAF工厂效率分布箱线图（使用每3小时时段数据）

        X轴：周度（4周）
        Y轴：SAF利用率 η_t^SAF（每个时段的利用率）
        按类别分组的箱线图，每周一个箱线图
        """
        logger.info("\n生成图T-SAF：SAF工厂效率分布箱线图（3小时时段数据）...")

        # 收集所有数据点
        all_records = []
        for scenario_name, scenario_data in self.data.items():
            config = scenario_data['config']
            for metric in scenario_data['hourly_metrics']:
                if metric['saf_capacity_kg_per_hour'] > 0:  # 只绘制有SAF工厂的场景
                    all_records.append({
                        'scenario': scenario_name,
                        'category': config['category'],
                        'pathway': config['pathway'],
                        'period': metric['period'],
                        'week': metric['week'],
                        'saf_production_kg': metric['saf_production_kg'],
                        'saf_utilization': metric['saf_utilization'],
                    })

        if not all_records:
            logger.warning("没有SAF工厂数据可绘制")
            return

        df = pd.DataFrame(all_records)
        df = df[df['week'].between(0, 3)]
        df['week_label'] = df['week'].apply(lambda w: f"W{int(w) + 1}")
        week_order = [f"W{i}" for i in range(1, 5)]

        # 创建图形
        fig, ax = plt.subplots(figsize=(14, 8))

        # 使用seaborn绘制箱线图
        palette = self.CATEGORY_COLORS

        sns.boxplot(
            data=df, x='week_label', y='saf_utilization',
            hue='category', palette=palette, ax=ax,
            width=0.6,
            flierprops={'marker': 'o', 'markersize': 4, 'alpha': 0.5},
            order=week_order
        )

        # 叠加散点（显示个体数据，使用较小的点）
        sns.stripplot(
            data=df, x='week_label', y='saf_utilization',
            hue='category', palette=palette, ax=ax,
            dodge=True, alpha=0.3, size=3, jitter=True, legend=False,
            order=week_order
        )

        # 设置标签
        ax.set_xlabel('Week', fontsize=14, fontweight='bold')
        ax.set_ylabel('SAF Plant Utilization Rate (per 3-hour period)', fontsize=14, fontweight='bold')
        ax.set_title('T-SAF: SAF Plant Utilization Distribution by Week (3-hour data)',
                     fontsize=16, fontweight='bold', pad=15)

        ax.set_ylim(0, 1.05)
        ax.set_xticks(range(len(week_order)))
        ax.set_xticklabels(week_order)
        ax.grid(True, axis='y', linestyle='--', alpha=0.4)

        # 图例
        handles, labels = ax.get_legend_handles_labels()
        # 只保留前3个（Grey, Blue, Green）
        ax.legend(handles[:3], labels[:3], title='Pathway Category',
                  loc='upper right', fontsize=11)

        # 添加类别说明文字框
        textstr = 'Grey: Coal-based\nBlue: Natural Gas\nGreen: Green H2/DAC'
        props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
        ax.text(0.02, 0.98, textstr, transform=ax.transAxes, fontsize=10,
                verticalalignment='top', bbox=props)

        plt.tight_layout()

        # 保存
        output_path = self.session_dir / "saf_efficiency_boxplot.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        logger.info(f"  保存图片: {output_path}")

        # 同时保存到results根目录（覆盖最新版本）
        latest_path = self.output_dir / "saf_efficiency_boxplot_latest.png"
        plt.savefig(latest_path, dpi=300, bbox_inches='tight')
        logger.info(f"  保存最新版本: {latest_path}")

        plt.close()

    def generate_summary_table(self):
        """生成汇总表格（使用每3小时时段数据）"""
        logger.info("\n生成汇总表格...")

        all_records = []
        for scenario_name, scenario_data in self.data.items():
            config = scenario_data['config']
            for metric in scenario_data['hourly_metrics']:
                all_records.append({
                    'Scenario': scenario_name,
                    'Scenario_CN': config['name_cn'],
                    'Category': config['category'],
                    'Pathway': config['pathway'],
                    'Period': metric['period'],
                    'Week': metric['week'],
                    'H2_Production_kg': metric['h2_production_kg'],
                    'SAF_Production_kg': metric['saf_production_kg'],
                    'H2_Capacity_kg_h': metric['h2_capacity_kg_per_hour'],
                    'SAF_Capacity_kg_h': metric['saf_capacity_kg_per_hour'],
                    'H2_Utilization': metric['h2_utilization'],
                    'SAF_Utilization': metric['saf_utilization'],
                })

        df = pd.DataFrame(all_records)

        # 保存CSV
        csv_path = self.session_dir / "temporal_efficiency_summary.csv"
        df.to_csv(csv_path, index=False, encoding='utf-8-sig')
        logger.info(f"  保存CSV: {csv_path}")

        # 打印统计信息
        logger.info("\n" + "=" * 80)
        logger.info("汇总统计")
        logger.info("=" * 80)
        logger.info(f"总数据点: {len(df)} (13场景 × 224时段)")
        logger.info(f"场景数: {df['Scenario'].nunique()}")
        logger.info(f"H2利用率范围: {df['H2_Utilization'].min():.2%} - {df['H2_Utilization'].max():.2%}")
        logger.info(f"SAF利用率范围: {df['SAF_Utilization'].min():.2%} - {df['SAF_Utilization'].max():.2%}")
        logger.info(f"SAF产量范围（每3小时）: {df['SAF_Production_kg'].min():.0f} - {df['SAF_Production_kg'].max():.0f} kg")

        return df

    def run_all_visualizations(self):
        """运行所有可视化"""
        logger.info("\n" + "=" * 80)
        logger.info("开始生成时间维度可视化")
        logger.info("=" * 80)

        # 生成图表
        self.plot_electrolyzer_efficiency_scatter()
        self.plot_saf_efficiency_boxplot()
        self.generate_summary_table()

        logger.info("\n" + "=" * 80)
        logger.info("所有可视化生成完成")
        logger.info(f"输出目录: {self.session_dir}")
        logger.info("=" * 80)


def main():
    """主函数"""
    logger.info("=" * 80)
    logger.info("时间维度效率可视化脚本")
    logger.info("Temporal Efficiency Visualization Script")
    logger.info("=" * 80)

    # 创建可视化器
    visualizer = TemporalEfficiencyVisualizer()

    # 加载数据
    visualizer.load_data()

    # 检查是否有数据
    if len(visualizer.data) < 1:
        logger.error(f"数据不足：只找到 {len(visualizer.data)} 个场景的数据")
        logger.error("请先运行各场景的优化器生成结果文件")
        return

    # 运行所有可视化
    visualizer.run_all_visualizations()

    logger.info("\n程序执行成功")


if __name__ == "__main__":
    main()
