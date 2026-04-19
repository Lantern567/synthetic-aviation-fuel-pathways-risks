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
    # 13场景配置
    SCENARIOS = {
        # ========== 灰色路径 (Grey) ==========
        'CTL': {
            'name_cn': '煤制油基线',
            'abbr': 'CTL',
            'description': 'Conventional coal-to-liquid process using fossil-based hydrogen.',
            'category': 'Grey',
            'pathway': 'Two-Step',
            'color': '#616161', # Grey Dark
            'solution_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/complete_solution_*.json',
            'hourly_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/hourly_production_summary_*.csv',
        },
        'CTL-BH': {
            'name_cn': '煤液化并副产氢气',
            'abbr': 'CTL-BH',
            'description': 'Coal-to-liquid process integrated with industrial by-product hydrogen.',
            'category': 'Grey',
            'pathway': 'Two-Step',
            'color': '#9E9E9E', # Grey Light
            'solution_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/byproduct_hydrogen/complete_solution_*.json',
            'hourly_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/byproduct_hydrogen/hourly_production_summary_*.csv',
        },

        # ========== 蓝色路径 (Blue) ==========
        'CCU-BH-MTJ': {
            'name_cn': '碳捕获和副产品氢的利用 – MTJ',
            'abbr': 'CCU-BH-MTJ',
            'description': 'Industrial carbon capture coupled with by-product hydrogen via Methanol-to-Jet.',
            'category': 'Blue',
            'pathway': 'Two-Step',
            'color': '#0D47A1', # Blue Dark
            'solution_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/two_step/complete_solution_*.json',
            'hourly_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/two_step/hourly_production_summary_*.csv',
        },
        'CCU-BH-FT': {
            'name_cn': '碳捕获和副产品氢的利用 – FT',
            'abbr': 'CCU-BH-FT',
            'description': 'Industrial carbon capture coupled with by-product hydrogen via Fischer-Tropsch.',
            'category': 'Blue',
            'pathway': 'One-Step',
            'color': '#1565C0',
            'solution_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/one_step/complete_solution_*.json',
            'hourly_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/one_step/hourly_production_summary_*.csv',
        },
        'GTL-BH': {
            'name_cn': 'GTL-BH',
            'abbr': 'GTL-BH',
            'description': 'Natural gas-to-liquid process enhanced by industrial by-product hydrogen (MTJ).',
            'category': 'Blue',
            'pathway': 'Two-Step',
            'color': '#1976D2',
            'solution_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/byproduct_hydrogen/byproduct_hydrogen/two_step/complete_solution_*.json',
            'hourly_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/byproduct_hydrogen/byproduct_hydrogen/two_step/hourly_production_summary_*.csv',
        },
        'DAC-BH-MTJ': {
            'name_cn': '利用副产品氢气直接捕获 – MTJ',
            'abbr': 'DAC-BH-MTJ',
            'description': 'Negative carbon technology (DAC) coupled with by-product hydrogen via Methanol-to-Jet.',
            'category': 'Blue',
            'pathway': 'Two-Step',
            'color': '#1E88E5',
            'solution_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/two_step/complete_solution_*.json',
            'hourly_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/two_step/hourly_production_summary_*.csv',
        },
        'DAC-BH-FT': {
            'name_cn': '利用副产品氢气直接捕获 – FT',
            'abbr': 'DAC-BH-FT',
            'description': 'Negative carbon technology (DAC) coupled with by-product hydrogen via Fischer-Tropsch.',
            'category': 'Blue',
            'pathway': 'One-Step',
            'color': '#42A5F5',
            'solution_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/one_step/complete_solution_*.json',
            'hourly_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/one_step/hourly_production_summary_*.csv',
        },
        'GTL-GH': {
            'name_cn': 'GTL-GH',
            'abbr': 'GTL-GH',
            'description': 'Natural gas-to-liquid process integrated with low-carbon hydrogen via Methanol-to-Jet.',
            'category': 'Blue',
            'pathway': 'Two-Step',
            'color': '#64B5F6',
            'solution_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/complete_solution_*.json',
            'hourly_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/hourly_production_summary_*.csv',
        },
        'GTL': {
            'name_cn': 'GTL',
            'abbr': 'GTL',
            'description': 'Natural gas-to-liquid via Fischer-Tropsch.',
            'category': 'Blue',
            'pathway': 'One-Step',
            'color': '#90CAF9',
            'solution_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/ft_one_step/complete_solution_*.json',
            'hourly_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/ft_one_step/hourly_production_summary_*.csv',
        },

        # ========== 绿色路径 (Green) ==========
        'DAC-GH-MTJ': {
            'name_cn': '使用绿色氢气直接捕获 – MTJ',
            'abbr': 'DAC-GH-MTJ',
            'description': 'Net-zero closed-loop Power-to-Liquid pathway using DAC and green hydrogen (MTJ).',
            'category': 'Green',
            'pathway': 'Two-Step',
            'color': '#1B5E20', # Green Dark
            'solution_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/two_step/complete_solution_*.json',
            'hourly_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/two_step/hourly_production_summary_*.csv',
        },
        'DAC-GH-FT': {
            'name_cn': '使用绿色氢气直接捕获 – FT',
            'abbr': 'DAC-GH-FT',
            'description': 'Net-zero closed-loop Power-to-Liquid pathway using DAC and green hydrogen (FT).',
            'category': 'Green',
            'pathway': 'One-Step',
            'color': '#2E7D32',
            'solution_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/one_step/complete_solution_*.json',
            'hourly_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/one_step/hourly_production_summary_*.csv',
        },
        'CCU-GH-MTJ': {
            'name_cn': '碳捕获与绿色氢利用 – MTJ',
            'abbr': 'CCU-GH-MTJ',
            'description': 'Industrial waste CO₂ utilization coupled with electrolyzed green hydrogen via Methanol-to-Jet.',
            'category': 'Green',
            'pathway': 'Two-Step',
            'color': '#388E3C',
            'solution_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/two_step/complete_solution_*.json',
            'hourly_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/two_step/hourly_production_summary_*.csv',
        },
        'CCU-GH-FT': {
            'name_cn': '碳捕获和绿色氢利用 – FT',
            'abbr': 'CCU-GH-FT',
            'description': 'Industrial waste CO₂ utilization coupled with electrolyzed green hydrogen via Fischer-Tropsch.',
            'category': 'Green',
            'pathway': 'One-Step',
            'color': '#4CAF50',
            'solution_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/one_step/complete_solution_*.json',
            'hourly_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/one_step/hourly_production_summary_*.csv',
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

    @staticmethod
    def _sum_saf_capacity(facilities: dict) -> float:
        """统计SAF产能（排除电解槽）"""
        total = 0.0
        for info in facilities.values():
            tech = str(info.get('technology', '')).strip().lower()
            mode = str(info.get('transport_mode', '')).strip().lower()
            if tech == 'electrolyzer' or mode == 'hydrogen_pipeline':
                continue
            cap = info.get('capacity_kg_per_hour', 0)
            try:
                total += float(cap)
            except (TypeError, ValueError):
                continue
        return total

    @staticmethod
    def _set_util_ylim(ax, values, pad: float = 0.05):
        """根据数据自适应设置y轴范围"""
        vals = np.asarray(values, dtype=float)
        vals = vals[np.isfinite(vals)]
        if vals.size == 0:
            return
        vmin = float(vals.min())
        vmax = float(vals.max())
        if vmin == vmax:
            if vmax == 0:
                vmin, vmax = 0.0, 1.0
            else:
                vmin = vmax * 0.9
                vmax = vmax * 1.1
        span = vmax - vmin
        ymin = vmin - pad * span
        ymax = vmax + pad * span
        if ymin < 0:
            ymin = 0.0
        ax.set_ylim(ymin, ymax)

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
        计算每3小时时段的指标（每时段单独计算）

        公式:
        - U_t^ely = H_t^prod / Cap_ely         每时段电解槽利用率
        - η_t^SAF = Q_t^SAF / Cap_SAF          每时段SAF工厂利用率
        - 周度利用率 = 周产量 / (总产能 × 56)  （56个3小时时段）

        注意：hourly_production_summary中的产出数据为“每时段产量”，
        因此每小时利用率用“(时段产量 / 时段小时数) / 总产能”计算。

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
        # 避免极小数值导致“看似有产能”的情况
        if total_h2_cap < 1e-6:
            total_h2_cap = 0.0

        # 获取SAF工厂总容量
        facilities = solution_data.get('facilities', {})
        total_saf_cap = self._sum_saf_capacity(facilities)

        hourly_metrics = []

        # 如果有hourly_df，从中计算每个时段的利用率
        if hourly_df is not None and not hourly_df.empty:
            # 确保列名正确 - 精确匹配列名
            h2_col = None
            saf_col = None
            period_col = None
            length_col = None

            for col in hourly_df.columns:
                col_clean = col.strip().lstrip('\ufeff')
                # 精确匹配"时段"列（不包含其他文字）
                if col_clean == '时段' or col_clean.lower() == 'period':
                    period_col = col
                if '时段长度' in col_clean or 'period_length' in col_clean.lower():
                    length_col = col
                if '氢气产出' in col or 'hydrogen' in col.lower():
                    h2_col = col
                if 'SAF产出' in col or 'saf' in col.lower():
                    saf_col = col

            # 如果没有找到时段列，使用第一列
            if period_col is None:
                period_col = hourly_df.columns[0]
                logger.warning(f"  未找到'时段'列，使用第一列: {period_col}")

            periods_per_week = 56  # 每周56个3小时时段

            # 若电解槽产能为0（典型BH路径），用副产氢“供给能力”作为分母
            # 这里用4周内的最大小时供给量作为供给能力上限
            if total_h2_cap <= 0 and h2_col is not None:
                h2_hourly_series = []
                for _, row in hourly_df.iterrows():
                    try:
                        period = int(row[period_col])
                    except Exception:
                        continue
                    week = period // periods_per_week
                    if week >= 4:
                        continue
                    h2_prod = float(row[h2_col]) if h2_col and pd.notna(row[h2_col]) else 0
                    hours_per_period = float(row[length_col]) if length_col and pd.notna(row[length_col]) else 3.0
                    if hours_per_period <= 0:
                        hours_per_period = 3.0
                    h2_hourly_series.append(h2_prod / hours_per_period)
                if h2_hourly_series:
                    total_h2_cap = max(h2_hourly_series)

            for _, row in hourly_df.iterrows():
                period = int(row[period_col])
                week = period // periods_per_week

                if week >= 4:
                    continue

                h2_prod = float(row[h2_col]) if h2_col and pd.notna(row[h2_col]) else 0
                saf_prod = float(row[saf_col]) if saf_col and pd.notna(row[saf_col]) else 0
                hours_per_period = float(row[length_col]) if length_col and pd.notna(row[length_col]) else 3.0
                if hours_per_period <= 0:
                    hours_per_period = 3.0

                h2_hourly = h2_prod / hours_per_period
                saf_hourly = saf_prod / hours_per_period

                h2_util = h2_hourly / total_h2_cap if total_h2_cap > 0 else 0
                saf_util = saf_hourly / total_saf_cap if total_saf_cap > 0 else 0

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

    def plot_combined_efficiency_analysis(self):
        """
        绘制组合效率分析图 (Applied Energy Style)

        Subplot (a): Electrolyzer Utilization (Time Series)
        - X-axis: Time (0-672 hours, 4 weeks)
        - Y-axis: Utilization
        - Style: Line plot (Mean) with shaded area (Min-Max range) grouped by Category

        Subplot (b): SAF Plant Utilization (Distribution)
        - X-axis: Category
        - Y-axis: Utilization
        - Style: Boxplot/Violin plot with individual points
        """
        logger.info("\n生成组合效率分析图 (Applied Energy Style)...")

        # 准备数据
        # 1. Electrolyzer Data (TimeSeries) - 完整4周672小时
        ely_data = []
        for scenario_name, scenario_data in self.data.items():
            config = scenario_data['config']
            for metric in scenario_data['hourly_metrics']:
                if metric['h2_capacity_kg_per_hour'] > 0:
                    ely_data.append({
                        'hour': metric['period'] * 3,  # 完整时间轴 0-672小时
                        'week': metric['week'],
                        'utilization': metric['h2_utilization'],
                        'category': config['category']
                    })

        if not ely_data:
            logger.warning("无电解槽数据")
            return

        df_ely = pd.DataFrame(ely_data)

        # 2. SAF Data (Distribution)
        saf_data = []
        for scenario_name, scenario_data in self.data.items():
            config = scenario_data['config']
            for metric in scenario_data['hourly_metrics']:
                if metric['saf_capacity_kg_per_hour'] > 0:
                    saf_data.append({
                        'utilization': metric['saf_utilization'],
                        'category': config['category'],
                        'scenario': scenario_name
                    })

        if not saf_data:
            logger.warning("无SAF数据")
            return

        df_saf = pd.DataFrame(saf_data)

        # 设置绘图风格
        plt.rcParams['font.family'] = 'serif'
        plt.rcParams['font.serif'] = ['Times New Roman']
        plt.rcParams['font.size'] = 12

        # 创建图形 1x2
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6), sharey=True)

        # 颜色映射
        colors = {
            'Grey': '#7f7f7f',    # Neutral Gray
            'Blue': '#1f77b4',    # Muted Blue
            'Green': '#2ca02c'    # Muted Green
        }

        categories = ['Grey', 'Blue', 'Green']
        labels = ['Fossil Fuel', 'Blue Hydrogen', 'Green Hydrogen']

        # ==================== Subplot (a): Electrolyzer Time Series (4 weeks) ====================

        for idx, cat in enumerate(categories):
            cat_df = df_ely[df_ely['category'] == cat]
            if cat_df.empty:
                continue

            # 计算每个小时的均值和范围（跨场景）
            # Use IQR (25th and 75th percentile) instead of Min-Max to reduce noise
            stats = cat_df.groupby('hour')['utilization'].agg([
                'mean', 
                lambda x: x.quantile(0.25), 
                lambda x: x.quantile(0.75)
            ]).reset_index()
            stats.columns = ['hour', 'mean', 'q25', 'q75']
            stats = stats.sort_values('hour')

            # Applying rolling mean to smooth the curve (window=24 hours for daily trend)
            stats['mean_smooth'] = stats['mean'].rolling(window=8, center=True, min_periods=1).mean()
            stats['q25_smooth'] = stats['q25'].rolling(window=8, center=True, min_periods=1).mean()
            stats['q75_smooth'] = stats['q75'].rolling(window=8, center=True, min_periods=1).mean()

            # 绘制均值线和范围带
            # Plot smoothed mean and IQR area
            ax1.plot(stats['hour'], stats['mean_smooth'], color=colors[cat], label=labels[idx], linewidth=2)
            ax1.fill_between(stats['hour'], stats['q25_smooth'], stats['q75_smooth'], color=colors[cat], alpha=0.15)

        # 添加周分隔线
        for week in range(1, 4):
            ax1.axvline(x=week * 168, color='gray', linestyle='--', alpha=0.3, linewidth=0.8)

        ax1.set_xlabel('Time (h)', fontsize=14, fontweight='bold')
        ax1.set_ylabel('Utilization', fontsize=14, fontweight='bold')
        ax1.set_xlim(0, 672)  # 4周 = 672小时
        ax1.set_xticks([0, 168, 336, 504, 672])
        ax1.set_xticklabels(['0', '168\n(W1)', '336\n(W2)', '504\n(W3)', '672\n(W4)'])
        ax1.grid(True, linestyle=(0, (5, 10)), alpha=0.5)
        ax1.set_title('(a) Electrolyzer Utilization (4 Weeks)', y=-0.22, fontsize=14)

        combined_vals = np.concatenate([df_ely['utilization'].values, df_saf['utilization'].values])
        self._set_util_ylim(ax1, combined_vals)

        # 添加图例
        ax1.legend(loc='upper right', frameon=False, fontsize=11)

        # ==================== Subplot (b): SAF Distribution ====================

        # 准备绘图数据顺序
        plot_data = [df_saf[df_saf['category'] == cat]['utilization'].values for cat in categories]

        # Violin plot
        parts = ax2.violinplot(plot_data, showmeans=False, showmedians=False, showextrema=False)

        for i, pc in enumerate(parts['bodies']):
            pc.set_facecolor(colors[categories[i]])
            pc.set_edgecolor('black')
            pc.set_alpha(0.3)

        # Add boxplots inside violins
        for i, data in enumerate(plot_data):
            if len(data) > 0:
                ax2.boxplot(data, positions=[i+1], widths=0.1,
                           patch_artist=True,
                           boxprops=dict(facecolor='white', color='black'),
                           capprops=dict(color='black'),
                           whiskerprops=dict(color='black'),
                           medianprops=dict(color='black'),
                           showfliers=False)

        ax2.set_xlabel('Pathway Category', fontsize=14, fontweight='bold')
        ax2.set_xticks([1, 2, 3])
        ax2.set_xticklabels(labels, fontsize=12)
        ax2.grid(True, axis='y', linestyle=(0, (5, 10)), alpha=0.5)
        ax2.set_title('(b) SAF Plant Utilization', y=-0.22, fontsize=14)

        # 调整布局
        plt.subplots_adjust(bottom=0.22, wspace=0.08)

        # 保存
        output_path = self.session_dir / "combined_efficiency_analysis.png"
        plt.savefig(output_path, dpi=600, bbox_inches='tight')
        logger.info(f"  保存图片: {output_path}")

        latest_path = self.output_dir / "combined_efficiency_analysis_latest.png"
        plt.savefig(latest_path, dpi=600, bbox_inches='tight')

        plt.close()

    def plot_13_scenarios_efficiency_analysis(self):
        """
        绘制13场景效率分析图

        Subplot (a): Electrolyzer Utilization - 13 scenarios as separate lines
        Subplot (b): SAF Plant Utilization - 13 scenarios as separate lines
        """
        logger.info("\n生成13场景效率分析图...")

        # 准备数据
        ely_data = []
        saf_data = []

        for scenario_name, scenario_data in self.data.items():
            config = scenario_data['config']
            for metric in scenario_data['hourly_metrics']:
                hour = metric['period'] * 3

                if metric['h2_capacity_kg_per_hour'] > 0:
                    ely_data.append({
                        'hour': hour,
                        'week': metric['week'],
                        'utilization': metric['h2_utilization'],
                        'scenario': scenario_name,
                        'scenario_cn': config['name_cn'],
                        'category': config['category'],
                        'pathway': config['pathway']
                    })

                if metric['saf_capacity_kg_per_hour'] > 0:
                    saf_data.append({
                        'hour': hour,
                        'week': metric['week'],
                        'utilization': metric['saf_utilization'],
                        'scenario': scenario_name,
                        'scenario_cn': config['name_cn'],
                        'category': config['category'],
                        'pathway': config['pathway']
                    })

        df_ely = pd.DataFrame(ely_data)
        df_saf = pd.DataFrame(saf_data)

        # 设置绘图风格
        plt.rcParams['font.family'] = 'serif'
        plt.rcParams['font.serif'] = ['Times New Roman']
        plt.rcParams['font.size'] = 10

        # 13场景颜色配置 - 使用SCENARIOS中定义的颜色
        scenario_colors = {}
        for name, cfg in self.SCENARIOS.items():
            scenario_colors[name] = cfg['color']

        # 创建2x1图形
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 12), sharex=True)

        # ==================== Subplot (a): Electrolyzer Utilization ====================
        scenarios_with_h2 = df_ely['scenario'].unique()

        for scenario in scenarios_with_h2:
            scenario_df = df_ely[df_ely['scenario'] == scenario].sort_values('hour')
            color = scenario_colors.get(scenario, '#666666')

            # 平滑处理
            util_smooth = scenario_df['utilization'].rolling(window=4, center=True, min_periods=1).mean()

            ax1.plot(scenario_df['hour'], util_smooth,
                    color=color, label=scenario, linewidth=1.5, alpha=0.8)

        # 添加周分隔线
        for week in range(1, 4):
            ax1.axvline(x=week * 168, color='gray', linestyle='--', alpha=0.3, linewidth=0.8)

        ax1.set_ylabel('H2 Utilization', fontsize=14, fontweight='bold')
        ax1.set_xlim(0, 672)
        ax1.grid(True, linestyle=':', alpha=0.4)
        ax1.set_title('(a) Electrolyzer Utilization by Scenario (4 Weeks)', fontsize=14, fontweight='bold')

        self._set_util_ylim(ax1, df_ely['utilization'].values if not df_ely.empty else [])

        # 图例放在右侧
        ax1.legend(loc='upper left', bbox_to_anchor=(1.01, 1), frameon=True,
                   fontsize=9, ncol=1, borderaxespad=0)

        # ==================== Subplot (b): SAF Plant Utilization ====================
        scenarios_with_saf = df_saf['scenario'].unique()

        for scenario in scenarios_with_saf:
            scenario_df = df_saf[df_saf['scenario'] == scenario].sort_values('hour')
            color = scenario_colors.get(scenario, '#666666')

            # 平滑处理
            util_smooth = scenario_df['utilization'].rolling(window=4, center=True, min_periods=1).mean()

            ax2.plot(scenario_df['hour'], util_smooth,
                    color=color, label=scenario, linewidth=1.5, alpha=0.8)

        # 添加周分隔线
        for week in range(1, 4):
            ax2.axvline(x=week * 168, color='gray', linestyle='--', alpha=0.3, linewidth=0.8)

        ax2.set_xlabel('Time (h)', fontsize=14, fontweight='bold')
        ax2.set_ylabel('SAF Utilization', fontsize=14, fontweight='bold')
        ax2.set_xlim(0, 672)
        ax2.set_xticks([0, 168, 336, 504, 672])
        ax2.set_xticklabels(['0', '168\n(Week 1)', '336\n(Week 2)', '504\n(Week 3)', '672\n(Week 4)'])
        ax2.grid(True, linestyle=':', alpha=0.4)
        ax2.set_title('(b) SAF Plant Utilization by Scenario (4 Weeks)', fontsize=14, fontweight='bold')

        self._set_util_ylim(ax2, df_saf['utilization'].values if not df_saf.empty else [])

        # 图例放在右侧
        ax2.legend(loc='upper left', bbox_to_anchor=(1.01, 1), frameon=True,
                   fontsize=9, ncol=1, borderaxespad=0)

        # 调整布局
        plt.tight_layout()
        plt.subplots_adjust(right=0.78)  # 给右侧图例留空间

        # 保存
        output_path = self.session_dir / "13_scenarios_efficiency_analysis.png"
        plt.savefig(output_path, dpi=600, bbox_inches='tight')
        logger.info(f"  保存图片: {output_path}")

        latest_path = self.output_dir / "13_scenarios_efficiency_analysis_latest.png"
        plt.savefig(latest_path, dpi=600, bbox_inches='tight')

        plt.close()

    def plot_four_panel_efficiency(self):
        """
        绘制四面板效率分析图 (2x2 Grid)
        
        (a) Fossil Fuel Scenarios (Grey) - Electrolyzer Utilization (Time Series)
        (b) Blue Hydrogen Scenarios (Blue) - Electrolyzer Utilization (Time Series)
        (c) Green Hydrogen Scenarios (Green) - Electrolyzer Utilization (Time Series)
        (d) SAF Plant Efficiency (Distribution) - Boxplot Grouped by Category
        """
        logger.info("\n生成四面板效率分析图 (Split Group Layout)...")

        # 准备时序数据
        ely_data = []
        for scenario_name, scenario_data in self.data.items():
            config = scenario_data['config']
            for metric in scenario_data['hourly_metrics']:
                if metric['h2_capacity_kg_per_hour'] > 0:
                    ely_data.append({
                        'hour': metric['period'] * 3,
                        'utilization': metric['h2_utilization'],
                        'scenario': scenario_name,
                        'category': config['category'],
                        'color': config['color']
                    })
        df_ely = pd.DataFrame(ely_data)

        # 准备SAF分布数据
        saf_data = []
        for scenario_name, scenario_data in self.data.items():
            config = scenario_data['config']
            for metric in scenario_data['hourly_metrics']:
                if metric['saf_capacity_kg_per_hour'] > 0:
                    saf_data.append({
                        'utilization': metric['saf_utilization'],
                        'category': config['category'],
                        'scenario': scenario_name
                    })
        df_saf = pd.DataFrame(saf_data)

        # 设置字体
        plt.rcParams['font.family'] = 'serif'
        plt.rcParams['font.serif'] = ['Times New Roman']
        plt.rcParams['font.size'] = 11

        # 创建2x2布局
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        axes = axes.flatten()  # 0,1,2,3

        # 定义前三个面板的配置
        panel_configs = [
            {'cat': 'Grey', 'title': '(a) Fossil Fuel Pathways (Electrolyzer)', 'ax': axes[0]},
            {'cat': 'Blue', 'title': '(b) Blue Hydrogen Pathways (Electrolyzer)', 'ax': axes[1]},
            {'cat': 'Green', 'title': '(c) Green Hydrogen Pathways (Electrolyzer)', 'ax': axes[2]},
        ]

        # 绘制 (a), (b), (c) - 各类别的时序图
        for panel in panel_configs:
            ax = panel['ax']
            category = panel['cat']
            
            # 筛选该类别的数据
            cat_df = df_ely[df_ely['category'] == category]
            
            if cat_df.empty:
                ax.text(0.5, 0.5, 'No Data', ha='center')
                continue

            # 获取该类别下的所有场景
            scenarios = cat_df['scenario'].unique()
            
            for scenario in scenarios:
                scenario_df = cat_df[cat_df['scenario'] == scenario].sort_values('hour')
                # 获取场景特定颜色
                color = scenario_df['color'].iloc[0]
                
                # 平滑处理 (Window=8 hours approx)
                util_smooth = scenario_df['utilization'].rolling(window=4, center=True, min_periods=1).mean()
                
                ax.plot(scenario_df['hour'], util_smooth, 
                       color=color, label=scenario, linewidth=1.5, alpha=0.9)

            # 设置轴标签和网格
            ax.set_title(panel['title'], fontsize=12, fontweight='bold', loc='left')
            ax.set_ylabel('Utilization', fontsize=11)
            # 仅在底部子图显示X轴标签 (c和d)
            if panel['cat'] == 'Green': 
                ax.set_xlabel('Time (h)', fontsize=11)
            else:
                pass # ax.set_xlabel('')

            ax.set_xlim(0, 672)
            self._set_util_ylim(ax, cat_df['utilization'].values)
            # 标注周
            ax.set_xticks([0, 168, 336, 504, 672])
            ax.set_xticklabels(['0', '168\n(W1)', '336\n(W2)', '504\n(W3)', '672\n(W4)'])
            ax.grid(True, linestyle='--', alpha=0.3)
            
            # 图例放在图内最佳位置或外部
            # 由于面板较小，尝试放在图例上方或右上角
            ax.legend(loc='upper right', fontsize=8, framealpha=0.9, ncol=1)

        # ==================== (d) SAF Distribution ====================
        ax_d = axes[3]
        
        # 颜色映射 (Category Colors)
        cat_colors = {'Grey': '#7f7f7f', 'Blue': '#1f77b4', 'Green': '#2ca02c'}
        labels = ['Fossil Fuel', 'Blue Hydrogen', 'Green Hydrogen']
        categories_ord = ['Grey', 'Blue', 'Green']

        # 准备绘图数据
        plot_data = [df_saf[df_saf['category'] == cat]['utilization'].values for cat in categories_ord]
        
        # Violin Plot
        parts = ax_d.violinplot(plot_data, showmeans=False, showmedians=False, showextrema=False)
        
        for i, pc in enumerate(parts['bodies']):
            pc.set_facecolor(cat_colors[categories_ord[i]])
            pc.set_edgecolor('black')
            pc.set_alpha(0.5)
            
        # Box Plot inside
        for i, data in enumerate(plot_data):
            ax_d.boxplot(data, positions=[i+1], widths=0.15, 
                       patch_artist=True,
                       boxprops=dict(facecolor='white', color='black'),
                       capprops=dict(color='black'),
                       whiskerprops=dict(color='black'),
                       medianprops=dict(color='black'),
                       showfliers=False)

        ax_d.set_title('(d) SAF Plant Utilization Distribution', fontsize=12, fontweight='bold', loc='left')
        ax_d.set_xticks([1, 2, 3])
        ax_d.set_xticklabels(labels, fontsize=10)
        ax_d.set_ylabel('Utilization', fontsize=11)
        ax_d.grid(True, axis='y', linestyle='--', alpha=0.3)
        dist_vals = np.concatenate([v for v in plot_data if len(v) > 0]) if plot_data else []
        self._set_util_ylim(ax_d, dist_vals)

        plt.tight_layout()
        
        # 保存
        output_path = self.session_dir / "four_panel_efficiency_analysis.png"
        plt.savefig(output_path, dpi=600, bbox_inches='tight')
        logger.info(f"  保存图片: {output_path}")

        latest_path = self.output_dir / "four_panel_efficiency_analysis_latest.png"
        plt.savefig(latest_path, dpi=600, bbox_inches='tight')
        
        plt.close()

    def plot_split_timeseries_efficiency(self):
        """
        绘制分层时序效率分析图 (GridSpec Layout - Refined Aesthetics)
        
        Improvements:
        1. Unified Legend at Top (No internal legends).
        2. Distinct Line Styles for sub-groups (Solid, Dashed, Dotted).
        3. Spines clean-up (removed top/right).
        4. Adjusted aspect ratios.
        """
        logger.info("\n生成分层时序效率分析图 (Refined)...")

        # 定义分组映射
        GROUP_MAPPING = {
            'CTL': 'Grey',
            'CTL-BH': 'Grey',

            'GTL-BH': 'Blue-GTL',
            'GTL-GH': 'Blue-GTL',
            'GTL': 'Blue-GTL',

            'DAC-BH-MTJ': 'Blue-DAC-BH',
            'DAC-BH-FT': 'Blue-DAC-BH',

            'CCU-BH-MTJ': 'Blue-CCU-BH',
            'CCU-BH-FT': 'Blue-CCU-BH',

            'DAC-GH-MTJ': 'Green-DAC',
            'DAC-GH-FT': 'Green-DAC',

            'CCU-GH-MTJ': 'Green-CCU',
            'CCU-GH-FT': 'Green-CCU',
        }
        
        GROUPS_ORDER = ['Grey', 'Blue-GTL', 'Blue-DAC-BH', 'Blue-CCU-BH', 'Green-DAC', 'Green-CCU']
        
        # 定义时序图的3个大类
        TS_CATEGORIES = {
            'Grey': ['Grey'],
            'Blue': ['Blue-GTL', 'Blue-DAC-BH', 'Blue-CCU-BH'],
            'Green': ['Green-DAC', 'Green-CCU']
        }
        TS_CAT_ORDER = ['Grey', 'Blue', 'Green']
        
        GROUP_LABELS = {
            'Grey': 'Grey (Coal)',
            'Blue-GTL': 'Blue (GTL)',
            'Blue-DAC-BH': 'Blue (DAC-BH)',
            'Blue-CCU-BH': 'Blue (CCU-BH)',
            'Green-DAC': 'Green (DAC)',
            'Green-CCU': 'Green (CCU)'
        }
        GROUP_COLORS = {
            'Grey': '#7f7f7f',
            'Blue-GTL': '#1f77b4',
            'Blue-DAC-BH': '#6baed6',
            'Blue-CCU-BH': '#08519c',
            'Green-DAC': '#74c476', 
            'Green-CCU': '#238b45'
        }
        
        # 线型映射 - 用于区分同色系下的不同子组
        GROUP_STYLES = {
            'Grey': '-',
            'Blue-GTL': '-',          # Solid
            'Blue-DAC-BH': '--',      # Dashed
            'Blue-CCU-BH': ':',       # Dotted
            'Green-DAC': '-',         # Solid
            'Green-CCU': '--'         # Dashed
        }

        # 准备数据
        data_rows = []
        for scenario_name, scenario_data in self.data.items():
            group = GROUP_MAPPING.get(scenario_name, 'Other')
            for metric in scenario_data['hourly_metrics']:
                data_rows.append({
                    'scenario': scenario_name,
                    'group': group,
                    'hour': metric['period'] * 3,
                    'h2_util': metric['h2_utilization'] if metric['h2_capacity_kg_per_hour'] > 0 else np.nan,
                    'saf_util': metric['saf_utilization'] if metric['saf_capacity_kg_per_hour'] > 0 else np.nan
                })
        
        df = pd.DataFrame(data_rows)
        
        # 设置字体
        plt.rcParams['font.family'] = 'serif'
        plt.rcParams['font.serif'] = ['Times New Roman']
        plt.rcParams['font.size'] = 11

        # 创建GridSpec布局
        fig = plt.figure(figsize=(16, 12)) # Slightly wider, less tall
        # 增加hspace让Stacked plot之间有点呼吸感
        gs = fig.add_gridspec(6, 2, width_ratios=[1.3, 1], wspace=0.15, hspace=0.15)
        
        # Helper to style axes
        def style_axis(ax, is_bottom=False, is_left_col=True):
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.grid(True, linestyle=':', alpha=0.4)
            if not is_bottom:
                ax.set_xticklabels([])
                ax.tick_params(axis='x', length=0)
            if is_left_col:
                ax.set_ylabel('Utilization', fontsize=10)
            
        
        # =================================================================================
        # SECTION 1: Hydrogen (Rows 0-2)
        # =================================================================================
        
        # --- Right: H2 Distribution ---
        ax_h2_dist = fig.add_subplot(gs[0:3, 1])
        
        h2_violin_data = []
        h2_violin_colors = []
        h2_violin_labels = []
        
        for group in GROUPS_ORDER:
            vals = df[df['group'] == group]['h2_util'].dropna().values
            if len(vals) > 0:
                h2_violin_data.append(vals)
                h2_violin_labels.append(group)
                h2_violin_colors.append(GROUP_COLORS[group])

        if h2_violin_data:
            parts = ax_h2_dist.violinplot(h2_violin_data, showmeans=False, showmedians=False, showextrema=False)
            for i, pc in enumerate(parts['bodies']):
                pc.set_facecolor(h2_violin_colors[i])
                pc.set_edgecolor('black')
                pc.set_alpha(0.6)
            for i, d in enumerate(h2_violin_data):
                ax_h2_dist.boxplot(d, positions=[i+1], widths=0.12, patch_artist=True,
                           boxprops=dict(facecolor='white', color='black', linewidth=0.8),
                           capprops=dict(color='black', linewidth=0.8), 
                           whiskerprops=dict(color='black', linewidth=0.8),
                           medianprops=dict(color='black', linewidth=0.8), showfliers=False)
                           
        ax_h2_dist.set_title('(b) H2 Electrolyzer Utilization (Distribution)', fontsize=12, fontweight='bold', loc='left')
        ax_h2_dist.set_xticks(range(1, len(h2_violin_labels)+1))
        # Cleaner labels: remove prefix
        clean_labels = [l.replace('Blue-', '').replace('Green-', '') for l in h2_violin_labels]
        ax_h2_dist.set_xticklabels(clean_labels, rotation=0, fontsize=9)
        h2_dist_vals = np.concatenate([v for v in h2_violin_data if len(v) > 0]) if h2_violin_data else []
        self._set_util_ylim(ax_h2_dist, h2_dist_vals)
        style_axis(ax_h2_dist, is_bottom=True, is_left_col=False) # Keep bottom ticks
        
        # --- Left: H2 Time Series (Stacked) ---
        for i, ts_cat in enumerate(TS_CAT_ORDER):
            ax = fig.add_subplot(gs[i, 0])
            
            subgroups = TS_CATEGORIES[ts_cat]
            for group in subgroups:
                group_df = df[df['group'] == group].dropna(subset=['h2_util'])
                if group_df.empty: continue
                
                stats = group_df.groupby('hour')['h2_util'].agg(['mean', 'min', 'max']).reset_index()
                # Window=12
                stats['mean_s'] = stats['mean'].rolling(window=12, center=True, min_periods=1).mean()
                stats['min_s'] = stats['min'].rolling(window=12, center=True, min_periods=1).mean()
                stats['max_s'] = stats['max'].rolling(window=12, center=True, min_periods=1).mean()
                
                # Plot with style
                linestyle = GROUP_STYLES.get(group, '-')
                ax.plot(stats['hour'], stats['mean_s'], color=GROUP_COLORS[group], 
                        linestyle=linestyle, linewidth=2, label=None) # No label here
                ax.fill_between(stats['hour'], stats['min_s'], stats['max_s'], color=GROUP_COLORS[group], alpha=0.15)
            
            style_axis(ax, is_bottom=(i==2), is_left_col=True)
            
            if i == 0:
                ax.set_title('(a) H2 Electrolyzer Utilization (Time Series)', fontsize=12, fontweight='bold', loc='left')
                
            cat_vals = df[df['group'].isin(subgroups)]['h2_util'].dropna().values
            self._set_util_ylim(ax, cat_vals)
            ax.set_xlim(0, 672)
            
            # Label Inside (Category Name)
            ax.text(0.015, 0.88, ts_cat.upper(), transform=ax.transAxes, 
                   fontweight='bold', fontsize=9, color='#444', 
                   bbox=dict(facecolor='white', alpha=0.8, edgecolor='none', pad=1))
            
            if i == 2:
                # Custom X ticks for bottom only
                ax.set_xticks([0, 168, 336, 504, 672])
                ax.set_xticklabels(['0', '168\n(W1)', '336\n(W2)', '504\n(W3)', '672\n(W4)'])

        # =================================================================================
        # SECTION 2: SAF (Rows 3-5)
        # =================================================================================

        # --- Right: SAF Distribution ---
        ax_saf_dist = fig.add_subplot(gs[3:6, 1])
        
        saf_violin_data = []
        saf_violin_colors = []
        saf_violin_labels = []
        
        for group in GROUPS_ORDER:
            vals = df[df['group'] == group]['saf_util'].dropna().values
            if len(vals) > 0:
                saf_violin_data.append(vals)
                saf_violin_labels.append(group)
                saf_violin_colors.append(GROUP_COLORS[group])

        if saf_violin_data:
            parts = ax_saf_dist.violinplot(saf_violin_data, showmeans=False, showmedians=False, showextrema=False)
            for i, pc in enumerate(parts['bodies']):
                pc.set_facecolor(saf_violin_colors[i])
                pc.set_edgecolor('black')
                pc.set_alpha(0.6)
            for i, d in enumerate(saf_violin_data):
                ax_saf_dist.boxplot(d, positions=[i+1], widths=0.12, patch_artist=True,
                           boxprops=dict(facecolor='white', color='black', linewidth=0.8),
                           capprops=dict(color='black', linewidth=0.8), 
                           whiskerprops=dict(color='black', linewidth=0.8),
                           medianprops=dict(color='black', linewidth=0.8), showfliers=False)

        ax_saf_dist.set_title('(d) SAF Plant Utilization (Distribution)', fontsize=12, fontweight='bold', loc='left')
        ax_saf_dist.set_xticks(range(1, len(saf_violin_labels)+1))
        # Use clean labels
        clean_labels_saf = [l.replace('Blue-', '').replace('Green-', '') for l in saf_violin_labels]
        ax_saf_dist.set_xticklabels(clean_labels_saf, rotation=0, fontsize=9)
        saf_dist_vals = np.concatenate([v for v in saf_violin_data if len(v) > 0]) if saf_violin_data else []
        self._set_util_ylim(ax_saf_dist, saf_dist_vals)
        style_axis(ax_saf_dist, is_bottom=True, is_left_col=False)

        # --- Left: SAF Time Series (Stacked) ---
        for i, ts_cat in enumerate(TS_CAT_ORDER):
            row_idx = i + 3
            ax = fig.add_subplot(gs[row_idx, 0])
            
            subgroups = TS_CATEGORIES[ts_cat]
            for group in subgroups:
                group_df = df[df['group'] == group].dropna(subset=['saf_util'])
                if group_df.empty: continue
                
                stats = group_df.groupby('hour')['saf_util'].agg(['mean', 'min', 'max']).reset_index()
                stats['mean_s'] = stats['mean'].rolling(window=12, center=True, min_periods=1).mean()
                stats['min_s'] = stats['min'].rolling(window=12, center=True, min_periods=1).mean()
                stats['max_s'] = stats['max'].rolling(window=12, center=True, min_periods=1).mean()
                
                linestyle = GROUP_STYLES.get(group, '-')
                ax.plot(stats['hour'], stats['mean_s'], color=GROUP_COLORS[group], 
                        linestyle=linestyle, linewidth=2)
                ax.fill_between(stats['hour'], stats['min_s'], stats['max_s'], color=GROUP_COLORS[group], alpha=0.15)
            
            style_axis(ax, is_bottom=(i==2), is_left_col=True)
            
            if i == 0:
                ax.set_title('(c) SAF Plant Utilization (Time Series)', fontsize=12, fontweight='bold', loc='left')
                
            cat_vals = df[df['group'].isin(subgroups)]['saf_util'].dropna().values
            self._set_util_ylim(ax, cat_vals)
            ax.set_xlim(0, 672)
            ax.text(0.015, 0.88, ts_cat.upper(), transform=ax.transAxes, 
                   fontweight='bold', fontsize=9, color='#444', 
                   bbox=dict(facecolor='white', alpha=0.8, edgecolor='none', pad=1))
            
            if i == 2:
                ax.set_xlabel('Time (h)', fontsize=11)
                ax.set_xticks([0, 168, 336, 504, 672])
                ax.set_xticklabels(['0', '168\n(W1)', '336\n(W2)', '504\n(W3)', '672\n(W4)'])

        # Create Unified Legend
        # Create dummy lines for legend
        legend_lines = []
        for group in GROUPS_ORDER:
            # Combo of color + line style
            line = getattr(mpl.lines, 'Line2D')([0], [0], color=GROUP_COLORS[group], 
                                                linestyle=GROUP_STYLES.get(group, '-'), 
                                                linewidth=2, label=GROUP_LABELS[group])
            legend_lines.append(line)
            
        fig.legend(handles=legend_lines, loc='upper center', bbox_to_anchor=(0.5, 0.98), 
                  ncol=6, fontsize=10, frameon=False, columnspacing=1.5)

        # Main Layout adjust
        plt.subplots_adjust(left=0.06, right=0.96, top=0.92, bottom=0.06, hspace=0.15, wspace=0.15)
        
        # 保存
        output_path = self.session_dir / "split_timeseries_efficiency.png"
        plt.savefig(output_path, dpi=600, bbox_inches='tight')
        logger.info(f"  保存图片: {output_path}")

        latest_path = self.output_dir / "split_timeseries_efficiency_latest.png"
        plt.savefig(latest_path, dpi=600, bbox_inches='tight')
        
        plt.close()

    def generate_summary_table(self):
        """生成汇总表格（使用每3小时时段数据）"""
        logger.info("\n生成汇总表格...")
        # ... (Existing code)
        
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

        return df

    def plot_h2_saf_vertical_layout(self):
        """
        绘制最终竖向布局图 (3 cols x 3 rows) - 左侧分布 + 右侧时序 (H2 vs SAF)
        Features:
        - 左侧：13情境效率分布（中间一分为二：H2 vs SAF）
        - 右侧：时序曲线（H2/SAF）
        - 语义化配色：Grey/Blue/Green
        - 坐标轴：Open Axis, 右侧Y轴, 0-100% 刻度, 严格截断 (Spine Bounds)
        - 图例：嵌入子图内部 (自适应位置)
        """
        logger.info("\n生成H2与SAF竖向利用率分布图 (Final Percentage)...")
        import matplotlib.ticker as ticker
        from matplotlib.colors import to_rgba

        # 底色（可按需微调）
        h2_bg = '#EAF2FF'   # H2 背景色（原浅蓝）
        saf_bg = '#FFECEC'  # SAF 背景色（原浅红）

        # 1. 定义色系生成器
        def get_palette(category, n):
            if n == 0: return []
            if category == 'Grey':
                base = sns.color_palette("Greys", n + 2)[2:]
                return base[::-1]
            elif category == 'Blue':
                base = sns.color_palette("Blues", n + 2)[2:]
                return base[::-1]
            elif category == 'Green':
                base = sns.color_palette("Greens", n + 2)[2:]
                return base[::-1]
            return sns.color_palette("husl", n)

        # 2. 准备数据
        categories = ['Grey', 'Blue', 'Green']
        data_map = {cat: {'h2': [], 'saf': []} for cat in categories}
        cat_scenarios = defaultdict(set)
        for name, data in self.data.items():
            cat_scenarios[data['config']['category']].add(name)
        
        scenario_colors = {}
        for cat in categories:
            scenarios = sorted(list(cat_scenarios[cat]))
            palette = get_palette(cat, len(scenarios))
            for i, name in enumerate(scenarios):
                scenario_colors[name] = palette[i]

        def infer_line_style(scenario_name, scenario_cfg):
            # Preserve category color while using linestyles to distinguish pathway/subtype
            if scenario_name == 'CTL':
                return '-'
            if scenario_name == 'CTL-BH':
                return (0, (4, 1.8))
            if '-FT' in scenario_name or scenario_cfg.get('pathway') == 'One-Step':
                return (0, (6, 2.2))
            if '-MTJ' in scenario_name or scenario_cfg.get('pathway') == 'Two-Step':
                return '-'
            return '-'

        for name, data in self.data.items():
            cat = data['config']['category']
            line_style = infer_line_style(name, data['config'])
            line_width = 1.9 if line_style == '-' else 1.7
            df = pd.DataFrame(data['hourly_metrics'])
            if df.empty: continue
            
            df = df.sort_values('period')
            hours = df['period'] * 3
            
            if df['h2_capacity_kg_per_hour'].max() > 0:
                y_smooth = df['h2_utilization'].rolling(window=8, center=True, min_periods=1).mean()
                data_map[cat]['h2'].append({
                    'label': name,
                    'x': hours,
                    'y': y_smooth,
                    'color': scenario_colors[name],
                    'linestyle': line_style,
                    'linewidth': line_width
                })

            if df['saf_capacity_kg_per_hour'].max() > 0:
                y_smooth = df['saf_utilization'].rolling(window=8, center=True, min_periods=1).mean()
                data_map[cat]['saf'].append({
                    'label': name,
                    'x': hours,
                    'y': y_smooth,
                    'color': scenario_colors[name],
                    'linestyle': line_style,
                    'linewidth': line_width
                })

        # 2.1 分布数据（用于左侧分布图 - ridgeline）
        dist_map = {cat: {'h2': {}, 'saf': {}} for cat in categories}
        for name, data in self.data.items():
            cat = data['config']['category']
            df = pd.DataFrame(data['hourly_metrics'])
            if df.empty:
                continue
            if df['h2_capacity_kg_per_hour'].max() > 0:
                vals = df['h2_utilization'].astype(float).clip(0, 1).dropna()
                if not vals.empty:
                    dist_map[cat]['h2'][name] = vals.values
            if df['saf_capacity_kg_per_hour'].max() > 0:
                vals = df['saf_utilization'].astype(float).clip(0, 1).dropna()
                if not vals.empty:
                    dist_map[cat]['saf'][name] = vals.values

        # 3. 设置绘图
        fig, axes = plt.subplots(
            3, 3,
            figsize=(13.5, 12),
            sharex=False,
            sharey=False,
            gridspec_kw={'width_ratios': [1, 1, 1]}
        )
        # 按列自上而下编号（竖向排列）
        subplot_letters = [['a', 'd', 'g'], ['b', 'e', 'h'], ['c', 'f', 'i']]

        # 分布图绘制函数（每一行一张：ridgeline，中间一分为二，左H2右SAF）
        def plot_distribution_axis(ax, cat, scenario_order):
            # 背景分区 + 中线
            ax.axvspan(-1.0, 0, color=h2_bg, alpha=0.7, zorder=0)
            ax.axvspan(0, 1.0, color=saf_bg, alpha=0.6, zorder=0)
            ax.axvline(0, color='#666666', linestyle='--', linewidth=0.9, zorder=1)

            if not scenario_order:
                ax.text(0.5, 0.5, 'No Data', ha='center', va='center', fontsize=9)
                ax.set_axis_off()
                return

            def _kde_1d(samples, grid):
                samples = np.asarray(samples, dtype=float)
                samples = samples[np.isfinite(samples)]
                n = samples.size
                if n < 2:
                    return np.zeros_like(grid)
                std = samples.std(ddof=1)
                if std <= 0:
                    return np.zeros_like(grid)
                bw = 1.06 * std * (n ** (-1 / 5))
                if not np.isfinite(bw) or bw <= 0:
                    bw = max(std, 1e-3)
                diff = (grid[:, None] - samples[None, :]) / bw
                dens = np.exp(-0.5 * diff ** 2).sum(axis=1) / (n * bw * np.sqrt(2 * np.pi))
                return dens

            y_positions = np.arange(len(scenario_order), 0, -1)
            ridge_height = 0.8
            grid = np.linspace(0, 1.0, 220)

            for y, scenario in zip(y_positions, scenario_order):
                color = scenario_colors.get(scenario, self.CATEGORY_COLORS.get(cat, '#666666'))

                h2_vals = dist_map[cat]['h2'].get(scenario)
                saf_vals = dist_map[cat]['saf'].get(scenario)

                def _draw_side(vals, sign):
                    if vals is None or len(vals) == 0:
                        return
                    dens = _kde_1d(vals, grid)
                    if dens.max() <= 0:
                        return
                    dens_scaled = dens / dens.max() * ridge_height
                    x = sign * grid
                    y_curve = y + dens_scaled
                    ax.fill_between(x, y, y_curve, color=color, alpha=0.55, linewidth=0.6, zorder=2)
                    ax.plot(x, y_curve, color=color, linewidth=1.0, zorder=3)

                    mean = float(np.mean(vals))
                    median = float(np.median(vals))
                    mean_y = y + np.interp(mean, grid, dens_scaled)
                    median_y = y + np.interp(median, grid, dens_scaled)

                    # 垂直线 + 点（贴在密度曲线上）
                    ax.vlines(sign * mean, y, mean_y, color='black', linewidth=1.2, zorder=4)
                    ax.scatter(sign * mean, mean_y, s=26, color='black', zorder=6)

                    # 白色bar（用黑色描边增强可见性）
                    ax.vlines(sign * median, y, median_y, color='black', linewidth=2.4, zorder=4)
                    ax.vlines(sign * median, y, median_y, color='white', linewidth=1.4, zorder=5)
                    ax.scatter(sign * median, median_y, s=26, facecolor='white', edgecolor='black', zorder=7)

                # H2 (left, mirrored) / SAF (right)
                _draw_side(h2_vals, sign=-1.0)
                _draw_side(saf_vals, sign=1.0)

            ax.set_yticks(y_positions)
            ax.set_yticklabels(scenario_order, fontsize=8)
            ax.set_ylim(0.5, len(scenario_order) + 1)
            ax.set_xlim(-1.0, 1.0)
            ax.set_xticks([-1.0, -0.5, 0, 0.5, 1.0])
            ax.set_xticklabels(['100%', '50%', '0', '50%', '100%'], fontsize=8)
            ax.grid(True, axis='x', linestyle='--', alpha=0.25)
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['left'].set_visible(False)
            ax.tick_params(axis='y', length=0)

        for row_idx, cat in enumerate(categories):
            # --- 左侧分布图 ---
            scenario_order = sorted(list(cat_scenarios[cat]))
            ax_dist = axes[row_idx, 0]
            plot_distribution_axis(ax_dist, cat, scenario_order)

            # --- 右侧时序 (H2 & SAF) ---
            for col_idx, key in enumerate(['h2', 'saf']):
                ax = axes[row_idx, col_idx + 1]
                ax.set_facecolor(to_rgba(h2_bg if col_idx == 0 else saf_bg, 0.35))
                items = sorted(data_map[cat][key], key=lambda x: x['label'])
                
                if items:
                    # Shadow
                    ys_df = pd.concat([item['y'] for item in items], axis=1)
                    shadow_color = scenario_colors[items[0]['label']]
                    ax.fill_between(items[0]['x'], ys_df.min(axis=1), ys_df.max(axis=1), 
                                    color=shadow_color, alpha=0.1, edgecolor='none')
                    # Lines
                    for item in items:
                        ax.plot(
                            item['x'],
                            item['y'],
                            color=item['color'],
                            linestyle=item.get('linestyle', '-'),
                            linewidth=item.get('linewidth', 1.8),
                            label=item['label']
                        )
                    
                    # In-plot Legend (Adaptive)
                    ax.legend(loc='best', fontsize=8, frameon=False, labelspacing=0.4, handlelength=2.2)

            # --- Axis Styling (分布图) ---
            if row_idx == 2:
                ax_dist.spines['bottom'].set_visible(True)
                ax_dist.spines['bottom'].set_position(('outward', 10))
            else:
                ax_dist.spines['bottom'].set_visible(False)
            if row_idx < 2:
                ax_dist.tick_params(axis='x', bottom=False, labelbottom=False)
            letter = subplot_letters[row_idx][0]
            ax_dist.text(0.0, 1.05, f'({letter}) {cat} – Distribution', transform=ax_dist.transAxes, 
                         fontsize=11, fontweight='bold', va='bottom', ha='left')
            if row_idx == 0:
                ax_dist.text(0.25, 1.01, 'H2', transform=ax_dist.transAxes,
                             fontsize=9, fontweight='bold', ha='center', va='bottom')
                ax_dist.text(0.75, 1.01, 'SAF', transform=ax_dist.transAxes,
                             fontsize=9, fontweight='bold', ha='center', va='bottom')

            # --- Axis Styling (时序图) ---
            for col_idx, ax in enumerate([axes[row_idx, 1], axes[row_idx, 2]]):
                target_type = 'H2' if col_idx == 0 else 'SAF'
                
                # Hide Left/Top
                ax.spines['left'].set_visible(False)
                ax.spines['top'].set_visible(False)
                
                # Right Spine: Offset & Bounded
                ax.spines['right'].set_visible(True)
                ax.spines['right'].set_position(('outward', 10))
                ax.spines['right'].set_bounds(0, 1.0) # Strictly 0 to 1
                
                # Bottom Spine: Only last row
                if row_idx == 2:
                    ax.spines['bottom'].set_visible(True)
                    ax.spines['bottom'].set_position(('outward', 10))
                else:
                    ax.spines['bottom'].set_visible(False)
                    ax.tick_params(bottom=False, labelbottom=False)
                
                # Y Ticks & Format
                ax.set_ylim(0, 1.0)
                ax.yaxis.set_major_formatter(ticker.PercentFormatter(xmax=1.0, decimals=0))
                
                # Show ticks only for Right Column (col_idx == 1)
                show_yticks = (col_idx == 1)
                ax.tick_params(axis='y', left=False, right=show_yticks, labelleft=False, labelright=show_yticks, direction='out', width=1)
                ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0]) # Clean ticks
                
                # If hidden, hide spine as well? Or keep line but no ticks? 
                # User asked "去掉y轴", usually means axis line + ticks.
                if not show_yticks:
                     ax.spines['right'].set_visible(False)

                # X Ticks
                ax.set_xlim(0, 672)
                
                # Subplot Title (Internal Top-Left)
                letter = subplot_letters[row_idx][col_idx + 1]
                ax.text(0.0, 1.05, f'({letter}) {cat} – {target_type}', transform=ax.transAxes, 
                       fontsize=11, fontweight='bold', va='bottom', ha='left')

                # Y Label: keep a single right-side label to reduce repetition in publication figure
                if col_idx == 1 and row_idx == 1:
                    ax.set_ylabel('Utilization (%)', fontsize=11, rotation=270, labelpad=28)
                    ax.yaxis.set_label_position("right")

                # Week separators for better temporal reading in paper body
                for week_x in (168, 336, 504):
                    ax.axvline(week_x, color='#8A8A8A', linestyle=':', linewidth=0.7, alpha=0.30, zorder=0)

        # X Axis Labels (Bottom Row Only for Time Series)
        for ax in axes[2, 1:]:
            ax.set_xticks([0, 168, 336, 504, 672])
            ax.set_xticklabels(['0', '168\nW1', '336\nW2', '504\nW3', '672\nW4'], fontsize=10)

        # 分布图X轴标签（左侧列底部）
        label_fontsize = 11

        plt.subplots_adjust(top=0.92, bottom=0.12, left=0.07, right=0.94, wspace=0.25, hspace=0.25)

        # 对齐底部标签位置（Utilization 与 Time）
        left_pos = axes[2, 0].get_position()
        right_pos_l = axes[2, 1].get_position()
        right_pos_r = axes[2, 2].get_position()
        left_center_x = (left_pos.x0 + left_pos.x1) / 2
        right_center_x = (right_pos_l.x0 + right_pos_r.x1) / 2
        label_y = 0.038
        fig.text(left_center_x, label_y, 'Utilization (%)', ha='center', va='center',
                 fontsize=label_fontsize, fontweight='bold')
        fig.text(right_center_x, label_y, 'Time (h)', ha='center', va='center',
                 fontsize=label_fontsize, fontweight='bold')
        
        # Save
        filename = "h2_saf_2col_3row_by_category.png"
        path = self.session_dir / filename
        plt.savefig(path, dpi=600, bbox_inches='tight')
        logger.info(f"保存: {path}")
        
        latest_path = self.output_dir / filename
        plt.savefig(latest_path, dpi=600, bbox_inches='tight')
        plt.close()

    def run_all_visualizations(self):
        """运行所有可视化"""
        logger.info("\n" + "=" * 80)
        logger.info("开始生成时间维度可视化")
        logger.info("=" * 80)

        # 生成图表
        # self.plot_electrolyzer_efficiency_scatter()
        # self.plot_saf_efficiency_boxplot()
        # self.plot_four_panel_efficiency() 
        # self.plot_grouped_efficiency_2x2()
        self.plot_h2_saf_vertical_layout()
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
