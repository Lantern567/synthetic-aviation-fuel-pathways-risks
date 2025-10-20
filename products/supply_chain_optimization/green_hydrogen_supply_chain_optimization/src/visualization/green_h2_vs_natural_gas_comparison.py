"""
绿氢+CO₂制SAF vs 天然气制SAF方法对比可视化器
Green Hydrogen + CO₂ to SAF vs Natural Gas to SAF Method Comparison Visualizer

对比绿氢+CO₂制SAF与天然气制SAF的成本和性能指标
Compares green hydrogen + CO₂ to SAF vs natural gas to SAF costs and performance metrics

基于 natural_gas_supply_chain_optimization/src/visualization/method_comparison_visualizer_en.py
Based on the natural gas method comparison visualizer template
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec
import numpy as np
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import re
from datetime import datetime
import glob

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class GreenH2VsNaturalGasComparison:
    """绿氢+CO₂ vs 天然气制SAF对比可视化器"""

    def __init__(self, green_h2_results_dir: str, natural_gas_results_dir: str):
        """
        初始化可视化器

        Args:
            green_h2_results_dir: 绿氢优化结果目录
            natural_gas_results_dir: 天然气优化结果目录
        """
        self.green_h2_results_dir = Path(green_h2_results_dir)
        self.natural_gas_results_dir = Path(natural_gas_results_dir)

        # 配置中文字体
        self._configure_chinese_font()

        # 定义配色方案
        self.colors = {
            'green_h2': '#2ecc71',  # 绿色 - 绿氢
            'natural_gas': '#3498db',  # 蓝色 - 天然气
            'cost': '#e74c3c',  # 红色 - 成本
            'carbon': '#95a5a6',  # 灰色 - 碳排放
            'efficiency': '#f39c12',  # 橙色 - 效率
            'background': '#f5f5f5',
            'card': '#ffffff'
        }

        logger.info(f"初始化绿氢vs天然气方法对比可视化器")
        logger.info(f"绿氢结果目录: {self.green_h2_results_dir}")
        logger.info(f"天然气结果目录: {self.natural_gas_results_dir}")

    def _configure_chinese_font(self):
        """配置中文字体"""
        try:
            # Windows系统字体路径
            font_paths = [
                'C:/Windows/Fonts/simhei.ttf',  # 黑体
                'C:/Windows/Fonts/msyh.ttc',  # 微软雅黑
                'C:/Windows/Fonts/simsun.ttc'  # 宋体
            ]

            for font_path in font_paths:
                if Path(font_path).exists():
                    from matplotlib.font_manager import FontProperties
                    self.chinese_font = FontProperties(fname=font_path)
                    plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'SimSun']
                    plt.rcParams['axes.unicode_minus'] = False
                    logger.info(f"成功配置中文字体: {font_path}")
                    return

            logger.warning("未找到中文字体，使用默认字体")
            plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS']
            plt.rcParams['axes.unicode_minus'] = False
        except Exception as e:
            logger.warning(f"配置中文字体失败: {e}")

    def load_data(self) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame]]:
        """
        加载绿氢和天然气的优化结果数据

        Returns:
            (green_h2_summary, natural_gas_summary): 两个方法的汇总数据
        """
        logger.info("开始加载优化结果数据...")

        # 加载绿氢结果
        green_h2_summary = None
        summary_files = list(self.green_h2_results_dir.glob('optimization_summary_*.csv'))
        if summary_files:
            # 选择最新的文件
            latest_file = max(summary_files, key=lambda p: p.stat().st_mtime)
            logger.info(f"找到绿氢汇总文件: {latest_file.name}")
            green_h2_summary = pd.read_csv(latest_file, encoding='utf-8-sig')
            logger.info(f"绿氢汇总数据行数: {len(green_h2_summary)}")
        else:
            logger.warning(f"未找到绿氢优化汇总文件: {self.green_h2_results_dir}")

        # 加载天然气结果
        natural_gas_summary = None
        summary_files = list(self.natural_gas_results_dir.glob('optimization_summary_*.csv'))
        if summary_files:
            # 选择最新的文件
            latest_file = max(summary_files, key=lambda p: p.stat().st_mtime)
            logger.info(f"找到天然气汇总文件: {latest_file.name}")
            natural_gas_summary = pd.read_csv(latest_file, encoding='utf-8-sig')
            logger.info(f"天然气汇总数据行数: {len(natural_gas_summary)}")
        else:
            logger.warning(f"未找到天然气优化汇总文件: {self.natural_gas_results_dir}")

        return green_h2_summary, natural_gas_summary

    def extract_comparison_metrics(
        self,
        green_h2_summary: pd.DataFrame,
        natural_gas_summary: pd.DataFrame
    ) -> Dict:
        """
        提取对比指标

        Args:
            green_h2_summary: 绿氢汇总数据
            natural_gas_summary: 天然气汇总数据

        Returns:
            对比指标字典
        """
        logger.info("提取对比指标...")

        metrics = {
            'green_h2': {},
            'natural_gas': {}
        }

        # 提取绿氢指标
        if green_h2_summary is not None and len(green_h2_summary) > 0:
            row = green_h2_summary.iloc[0]
            metrics['green_h2'] = {
                # 经济指标
                'total_cost': row.get('生命周期总成本(元)', row.get('总成本(元)', 0)),
                'lcoe': row.get('生命周期平准化成本(元/kg)', row.get('平准化成本(元/kg)', 0)),
                'annual_cost': row.get('年化平准化成本(元/kg)', 0),

                # 需求满足
                'demand_fulfillment': row.get('需求满足比例(%)', row.get('需求满足率(%)', 0)),

                # 生产指标
                'saf_production': row.get('20年总产量(kg)', row.get('SAF总产量(kg)', 0)),
                'annual_production': row.get('年产量(kg)', 0),

                # 环境指标
                'carbon_intensity': row.get('碳强度(kg CO2eq/kg SAF)', row.get('碳强度(gCO2e/MJ)', 0)),
                'vs_jet_fuel': row.get('相比传统航煤(%)', 0),
                'vs_corsia': row.get('相比CORSIA标准(%)', 0),

                # 成本结构
                'h2_cost': row.get('氢气制取成本(元)', row.get('氢气总成本(元)', 0)),
                'co2_cost': row.get('CO2捕获成本(元)', row.get('CO2总成本(元)', 0)),
                'electricity_cost': row.get('电力成本(元)', 0),
                'capex_electrolyzer': row.get('电解槽建设投资(元)', 0),
                'capex_mtj': row.get('MTJ工厂建设投资(元)', 0),
                'opex_mtj': row.get('MTJ生产运营成本(元)', 0),

                # 运输成本细分
                'h2_transport_cost': row.get('氢能管道运输成本(元)', 0),
                'co2_transport_cost': row.get('CO₂管道运输成本(元)', 0),
                'mtj_transport_cost': row.get('MTJ运输运营成本(元)', 0),

                # 总运输成本（所有运输成本之和）
                'transport_cost': (
                    row.get('氢能管道运输成本(元)', 0) +
                    row.get('CO₂管道运输成本(元)', 0) +
                    row.get('MTJ运输运营成本(元)', 0)
                ),

                # 效率指标
                'electrolyzer_efficiency': row.get('电解制氢实际效率(%)', 70.0),
                'mtj_efficiency': row.get('MTJ转化效率(%)', 85.0),
                'overall_efficiency': row.get('综合电力转MTJ效率(%)', 60.0),
            }
            logger.info(f"绿氢指标: LCOE={metrics['green_h2']['lcoe']:.2f}元/kg, "
                       f"碳强度={metrics['green_h2']['carbon_intensity']:.2f}")

        # 提取天然气指标
        if natural_gas_summary is not None and len(natural_gas_summary) > 0:
            row = natural_gas_summary.iloc[0]
            metrics['natural_gas'] = {
                # 经济指标
                'total_cost': row.get('生命周期总成本(元)', row.get('总成本(元)', 0)),
                'lcoe': row.get('生命周期平准化成本(元/kg)', row.get('平准化成本(元/kg)', 0)),
                'annual_cost': row.get('年化平准化成本(元/kg)', 0),

                # 需求满足
                'demand_fulfillment': row.get('需求满足比例(%)', row.get('需求满足率(%)', 0)),

                # 生产指标
                'saf_production': row.get('20年总产量(kg)', row.get('SAF总产量(kg)', 0)),
                'annual_production': row.get('年产量(kg)', 0),

                # 环境指标
                'carbon_intensity': row.get('碳强度(kg CO2eq/kg SAF)', row.get('碳强度(gCO2e/MJ)', 0)),
                'vs_jet_fuel': row.get('相比传统航煤(%)', 0),
                'vs_corsia': row.get('相比CORSIA标准(%)', 0),

                # 成本结构
                'lng_cost': row.get('LNG总成本(元)', row.get('天然气原料成本(元)', 0)),
                'capex_mtj': row.get('MTJ工厂建设投资(元)', 0),
                'opex_mtj': row.get('MTJ生产运营成本(元)', 0),

                # 运输成本细分
                'lng_transport_cost': row.get('天然气运输成本(元)', 0),
                'mtj_transport_cost': row.get('MTJ运输运营成本(元)', 0),

                # 总运输成本（所有运输成本之和）
                'transport_cost': (
                    row.get('天然气运输成本(元)', 0) +
                    row.get('MTJ运输运营成本(元)', 0)
                ),

                # 天然气消耗
                'lng_consumption': row.get('天然气消耗量(kg)', 0),
            }
            logger.info(f"天然气指标: LCOE={metrics['natural_gas']['lcoe']:.2f}元/kg, "
                       f"碳强度={metrics['natural_gas']['carbon_intensity']:.2f}")

        # 计算差异
        if metrics['green_h2'] and metrics['natural_gas']:
            metrics['difference'] = {
                'lcoe_diff': metrics['green_h2']['lcoe'] - metrics['natural_gas']['lcoe'],
                'lcoe_pct': ((metrics['green_h2']['lcoe'] / metrics['natural_gas']['lcoe'] - 1) * 100
                            if metrics['natural_gas']['lcoe'] > 0 else 0),
                'carbon_diff': metrics['green_h2']['carbon_intensity'] - metrics['natural_gas']['carbon_intensity'],
                'carbon_pct': ((metrics['green_h2']['carbon_intensity'] / metrics['natural_gas']['carbon_intensity'] - 1) * 100
                              if metrics['natural_gas']['carbon_intensity'] > 0 else 0),
            }
            logger.info(f"成本差异: {metrics['difference']['lcoe_diff']:.2f}元/kg ({metrics['difference']['lcoe_pct']:.1f}%)")
            logger.info(f"碳排放差异: {metrics['difference']['carbon_diff']:.2f} ({metrics['difference']['carbon_pct']:.1f}%)")

        return metrics

    def create_dashboard(
        self,
        metrics: Dict,
        output_path: Optional[str] = None
    ) -> str:
        """
        创建对比仪表板

        Args:
            metrics: 对比指标字典
            output_path: 输出路径（可选）

        Returns:
            保存的文件路径
        """
        logger.info("开始创建对比仪表板...")

        # 创建大图：4行3列布局
        fig = plt.figure(figsize=(20, 16))
        gs = GridSpec(4, 3, figure=fig, hspace=0.3, wspace=0.3)

        # 1. 关键指标卡片（第一行）
        self._create_metric_cards(fig, gs, metrics)

        # 2. 成本对比柱状图（第二行左）
        ax_cost = fig.add_subplot(gs[1, 0])
        self._create_cost_comparison(ax_cost, metrics)

        # 3. 碳排放对比（第二行中）
        ax_carbon = fig.add_subplot(gs[1, 1])
        self._create_carbon_comparison(ax_carbon, metrics)

        # 4. 效率对比（第二行右）
        ax_efficiency = fig.add_subplot(gs[1, 2])
        self._create_efficiency_comparison(ax_efficiency, metrics)

        # 5. 成本结构饼图（第三行左右）
        ax_pie_green = fig.add_subplot(gs[2, 0])
        ax_pie_ng = fig.add_subplot(gs[2, 1])
        self._create_cost_structure_pies(ax_pie_green, ax_pie_ng, metrics)

        # 6. 单位成本对比（第三行右）
        ax_unit_cost = fig.add_subplot(gs[2, 2])
        self._create_unit_cost_comparison(ax_unit_cost, metrics)

        # 7. 综合雷达图（第四行，占据两列）
        ax_radar = fig.add_subplot(gs[3, :2], projection='polar')
        self._create_comprehensive_radar(ax_radar, metrics)

        # 8. 结论文本（第四行右）
        ax_conclusion = fig.add_subplot(gs[3, 2])
        self._create_conclusion_text(ax_conclusion, metrics)

        # 添加标题
        fig.suptitle(
            '绿氢+CO₂制SAF vs 天然气制SAF 方法对比分析\n'
            'Green Hydrogen + CO₂ to SAF vs Natural Gas to SAF Comparison',
            fontsize=20,
            fontweight='bold',
            y=0.98
        )

        # 保存图表
        if output_path is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            figures_dir = self.green_h2_results_dir / 'figures'
            figures_dir.mkdir(parents=True, exist_ok=True)
            output_path = figures_dir / f'green_h2_vs_ng_comparison_{timestamp}.png'

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        logger.info(f"对比仪表板已保存: {output_path}")

        plt.close()

        return str(output_path)

    def _create_metric_cards(self, fig, gs, metrics: Dict):
        """创建关键指标卡片"""
        green_h2 = metrics.get('green_h2', {})
        natural_gas = metrics.get('natural_gas', {})

        # 卡片1: LCOE对比
        ax1 = fig.add_subplot(gs[0, 0])
        ax1.axis('off')
        lcoe_green = green_h2.get('lcoe', 0)
        lcoe_ng = natural_gas.get('lcoe', 0)
        diff_pct = ((lcoe_green - lcoe_ng) / lcoe_ng * 100) if lcoe_ng > 0 else 0

        ax1.text(0.5, 0.7, 'LCOE 平准化成本', ha='center', va='center', fontsize=16, fontweight='bold')
        ax1.text(0.5, 0.5, f'绿氢: {lcoe_green:.2f} 元/kg', ha='center', va='center', fontsize=14, color=self.colors['green_h2'])
        ax1.text(0.5, 0.3, f'天然气: {lcoe_ng:.2f} 元/kg', ha='center', va='center', fontsize=14, color=self.colors['natural_gas'])
        ax1.text(0.5, 0.1, f'差异: {diff_pct:+.1f}%', ha='center', va='center', fontsize=12,
                color='red' if diff_pct > 0 else 'green')
        ax1.add_patch(mpatches.Rectangle((0.05, 0.05), 0.9, 0.9, fill=False, edgecolor='black', linewidth=2))

        # 卡片2: 碳强度对比
        ax2 = fig.add_subplot(gs[0, 1])
        ax2.axis('off')
        carbon_green = green_h2.get('carbon_intensity', 0)
        carbon_ng = natural_gas.get('carbon_intensity', 0)
        carbon_reduction = ((carbon_ng - carbon_green) / carbon_ng * 100) if carbon_ng > 0 else 0

        ax2.text(0.5, 0.7, '碳强度', ha='center', va='center', fontsize=16, fontweight='bold')
        ax2.text(0.5, 0.5, f'绿氢: {carbon_green:.2f}', ha='center', va='center', fontsize=14, color=self.colors['green_h2'])
        ax2.text(0.5, 0.3, f'天然气: {carbon_ng:.2f}', ha='center', va='center', fontsize=14, color=self.colors['natural_gas'])
        ax2.text(0.5, 0.1, f'减排: {carbon_reduction:.1f}%', ha='center', va='center', fontsize=12, color='green')
        ax2.add_patch(mpatches.Rectangle((0.05, 0.05), 0.9, 0.9, fill=False, edgecolor='black', linewidth=2))

        # 卡片3: 需求满足率对比
        ax3 = fig.add_subplot(gs[0, 2])
        ax3.axis('off')
        demand_green = green_h2.get('demand_fulfillment', 0)
        demand_ng = natural_gas.get('demand_fulfillment', 0)

        ax3.text(0.5, 0.7, '需求满足率', ha='center', va='center', fontsize=16, fontweight='bold')
        ax3.text(0.5, 0.5, f'绿氢: {demand_green:.1f}%', ha='center', va='center', fontsize=14, color=self.colors['green_h2'])
        ax3.text(0.5, 0.3, f'天然气: {demand_ng:.1f}%', ha='center', va='center', fontsize=14, color=self.colors['natural_gas'])
        ax3.add_patch(mpatches.Rectangle((0.05, 0.05), 0.9, 0.9, fill=False, edgecolor='black', linewidth=2))

    def _create_cost_comparison(self, ax, metrics: Dict):
        """创建成本对比柱状图"""
        green_h2 = metrics.get('green_h2', {})
        natural_gas = metrics.get('natural_gas', {})

        categories = ['总成本', 'LCOE', '运输成本']
        green_values = [
            green_h2.get('total_cost', 0) / 1e8,  # 转换为亿元
            green_h2.get('lcoe', 0),
            green_h2.get('transport_cost', 0) / 1e6  # 转换为百万元
        ]
        ng_values = [
            natural_gas.get('total_cost', 0) / 1e8,
            natural_gas.get('lcoe', 0),
            natural_gas.get('transport_cost', 0) / 1e6
        ]

        x = np.arange(len(categories))
        width = 0.35

        ax.bar(x - width/2, green_values, width, label='绿氢+CO₂', color=self.colors['green_h2'], alpha=0.8, edgecolor='black')
        ax.bar(x + width/2, ng_values, width, label='天然气', color=self.colors['natural_gas'], alpha=0.8, edgecolor='black')

        ax.set_xlabel('成本类别', fontsize=12)
        ax.set_ylabel('成本 (亿元 / 元/kg / 百万元)', fontsize=12)
        ax.set_title('成本对比', fontsize=14, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(categories)
        ax.legend()
        ax.grid(axis='y', alpha=0.3)

        # 添加数值标签
        for bars in [ax.patches[:len(categories)], ax.patches[len(categories):]]:
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{height:.2f}',
                       ha='center', va='bottom', fontsize=9)

    def _create_carbon_comparison(self, ax, metrics: Dict):
        """创建碳排放对比横向柱状图"""
        green_h2 = metrics.get('green_h2', {})
        natural_gas = metrics.get('natural_gas', {})

        carbon_green = green_h2.get('carbon_intensity', 0)
        carbon_ng = natural_gas.get('carbon_intensity', 0)
        corsia_limit = 30  # CORSIA限值

        methods = ['绿氢+CO₂', '天然气', 'CORSIA限值']
        values = [carbon_green, carbon_ng, corsia_limit]
        colors = [self.colors['green_h2'], self.colors['natural_gas'], '#e74c3c']

        y_pos = np.arange(len(methods))
        ax.barh(y_pos, values, color=colors, alpha=0.8, edgecolor='black')

        ax.set_xlabel('碳强度', fontsize=12)
        ax.set_title('碳排放强度对比', fontsize=14, fontweight='bold')
        ax.set_yticks(y_pos)
        ax.set_yticklabels(methods)
        ax.grid(axis='x', alpha=0.3)

        # 添加数值标签
        for i, v in enumerate(values):
            ax.text(v + 0.5, i, f'{v:.1f}', va='center', fontsize=10)

    def _create_efficiency_comparison(self, ax, metrics: Dict):
        """创建效率对比（绿氢特有）"""
        green_h2 = metrics.get('green_h2', {})

        electrolyzer_eff = green_h2.get('electrolyzer_efficiency', 70.0)
        mtj_eff = green_h2.get('mtj_efficiency', 85.0)
        overall_eff = green_h2.get('overall_efficiency', 60.0)

        categories = ['电解槽效率(%)', 'MTJ转化效率(%)', '综合效率(%)']
        values = [electrolyzer_eff, mtj_eff, overall_eff]

        ax.bar(categories, values, color=[self.colors['green_h2'], self.colors['efficiency'], '#9b59b6'],
               alpha=0.8, edgecolor='black')

        ax.set_ylabel('效率 (%)', fontsize=12)
        ax.set_title('绿氢生产效率指标', fontsize=14, fontweight='bold')
        ax.grid(axis='y', alpha=0.3)
        ax.set_ylim(0, 100)

        # 添加数值标签
        for i, v in enumerate(values):
            ax.text(i, v + 2, f'{v:.1f}%', ha='center', va='bottom', fontsize=10)

    def _create_cost_structure_pies(self, ax_green, ax_ng, metrics: Dict):
        """创建成本结构饼图"""
        green_h2 = metrics.get('green_h2', {})
        natural_gas = metrics.get('natural_gas', {})

        # 绿氢成本结构
        h2_cost = green_h2.get('h2_cost', 0)
        co2_cost = green_h2.get('co2_cost', 0)
        transport_cost = green_h2.get('transport_cost', 0)
        capex = green_h2.get('capex_mtj', 0) + green_h2.get('capex_electrolyzer', 0)
        opex = green_h2.get('opex_mtj', 0)
        other_cost = max(0, green_h2.get('total_cost', 0) - h2_cost - co2_cost - transport_cost - capex - opex)

        green_labels = ['氢气成本', 'CO₂成本', '运输成本', 'CAPEX', 'OPEX', '其他']
        green_sizes = [h2_cost, co2_cost, transport_cost, capex, opex, other_cost]
        green_colors = ['#2ecc71', '#3498db', '#e74c3c', '#9b59b6', '#f39c12', '#95a5a6']

        # 过滤掉为0的项
        green_filtered = [(label, size, color) for label, size, color in zip(green_labels, green_sizes, green_colors) if size > 0]
        if green_filtered:
            labels, sizes, colors = zip(*green_filtered)
            ax_green.pie(sizes, labels=labels, autopct='%1.1f%%', colors=colors, startangle=90)
        ax_green.set_title('绿氢+CO₂成本结构', fontsize=14, fontweight='bold')

        # 天然气成本结构
        lng_cost = natural_gas.get('lng_cost', 0)
        ng_transport_cost = natural_gas.get('transport_cost', 0)
        ng_capex = natural_gas.get('capex_mtj', 0)
        ng_opex = natural_gas.get('opex_mtj', 0)
        ng_other_cost = max(0, natural_gas.get('total_cost', 0) - lng_cost - ng_transport_cost - ng_capex - ng_opex)

        ng_labels = ['天然气成本', '运输成本', 'CAPEX', 'OPEX', '其他']
        ng_sizes = [lng_cost, ng_transport_cost, ng_capex, ng_opex, ng_other_cost]
        ng_colors = ['#3498db', '#e74c3c', '#9b59b6', '#f39c12', '#95a5a6']

        # 过滤掉为0的项
        ng_filtered = [(label, size, color) for label, size, color in zip(ng_labels, ng_sizes, ng_colors) if size > 0]
        if ng_filtered:
            labels, sizes, colors = zip(*ng_filtered)
            ax_ng.pie(sizes, labels=labels, autopct='%1.1f%%', colors=colors, startangle=90)
        ax_ng.set_title('天然气成本结构', fontsize=14, fontweight='bold')

    def _create_unit_cost_comparison(self, ax, metrics: Dict):
        """创建单位成本对比"""
        green_h2 = metrics.get('green_h2', {})
        natural_gas = metrics.get('natural_gas', {})

        saf_prod_green = green_h2.get('saf_production', 1)
        saf_prod_ng = natural_gas.get('saf_production', 1)

        # 计算单位成本
        h2_unit_cost = green_h2.get('h2_cost', 0) / saf_prod_green if saf_prod_green > 0 else 0
        co2_unit_cost = green_h2.get('co2_cost', 0) / saf_prod_green if saf_prod_green > 0 else 0
        green_transport_unit = green_h2.get('transport_cost', 0) / saf_prod_green if saf_prod_green > 0 else 0

        lng_unit_cost = natural_gas.get('lng_cost', 0) / saf_prod_ng if saf_prod_ng > 0 else 0
        ng_transport_unit = natural_gas.get('transport_cost', 0) / saf_prod_ng if saf_prod_ng > 0 else 0

        categories = ['H₂/LNG\n原料成本', 'CO₂成本', '运输成本']
        green_values = [h2_unit_cost, co2_unit_cost, green_transport_unit]
        ng_values = [lng_unit_cost, 0, ng_transport_unit]  # 天然气无CO₂成本

        x = np.arange(len(categories))
        width = 0.35

        ax.bar(x - width/2, green_values, width, label='绿氢+CO₂', color=self.colors['green_h2'], alpha=0.8, edgecolor='black')
        ax.bar(x + width/2, ng_values, width, label='天然气', color=self.colors['natural_gas'], alpha=0.8, edgecolor='black')

        ax.set_xlabel('成本类型', fontsize=12)
        ax.set_ylabel('单位成本 (元/kg SAF)', fontsize=12)
        ax.set_title('单位SAF生产成本对比', fontsize=14, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(categories)
        ax.legend()
        ax.grid(axis='y', alpha=0.3)

    def _create_comprehensive_radar(self, ax, metrics: Dict):
        """创建综合雷达图"""
        green_h2 = metrics.get('green_h2', {})
        natural_gas = metrics.get('natural_gas', {})

        # 归一化指标 (0-100)
        categories = ['成本\n竞争力', '碳排放\n优势', '需求\n满足率', '技术\n成熟度', '基础设施\n完善度']

        # 绿氢指标（越高越好）
        lcoe_green_norm = max(0, 100 - (green_h2.get('lcoe', 50) / 50 * 100))  # 50元/kg为参考
        carbon_green_norm = max(0, 100 - (green_h2.get('carbon_intensity', 0) / 89 * 100))  # 89为传统燃料
        demand_green_norm = green_h2.get('demand_fulfillment', 0)
        tech_maturity_green = 60  # 估算：绿氢技术成熟度60%
        infra_green = 50  # 估算：基础设施完善度50%

        green_values = [lcoe_green_norm, carbon_green_norm, demand_green_norm, tech_maturity_green, infra_green]

        # 天然气指标
        lcoe_ng_norm = max(0, 100 - (natural_gas.get('lcoe', 50) / 50 * 100))
        carbon_ng_norm = max(0, 100 - (natural_gas.get('carbon_intensity', 0) / 89 * 100))
        demand_ng_norm = natural_gas.get('demand_fulfillment', 0)
        tech_maturity_ng = 90  # 估算：天然气技术成熟度90%
        infra_ng = 85  # 估算：基础设施完善度85%

        ng_values = [lcoe_ng_norm, carbon_ng_norm, demand_ng_norm, tech_maturity_ng, infra_ng]

        # 计算角度
        angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
        green_values += green_values[:1]
        ng_values += ng_values[:1]
        angles += angles[:1]

        # 绘制雷达图
        ax.plot(angles, green_values, 'o-', linewidth=2, label='绿氢+CO₂', color=self.colors['green_h2'])
        ax.fill(angles, green_values, alpha=0.25, color=self.colors['green_h2'])

        ax.plot(angles, ng_values, 'o-', linewidth=2, label='天然气', color=self.colors['natural_gas'])
        ax.fill(angles, ng_values, alpha=0.25, color=self.colors['natural_gas'])

        # 设置标签
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(categories, fontsize=11)
        ax.set_ylim(0, 100)
        ax.set_yticks([20, 40, 60, 80, 100])
        ax.set_yticklabels(['20', '40', '60', '80', '100'])
        ax.grid(True)
        ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1))
        ax.set_title('综合性能雷达图', fontsize=14, fontweight='bold', pad=20)

    def _create_conclusion_text(self, ax, metrics: Dict):
        """创建结论文本"""
        ax.axis('off')

        green_h2 = metrics.get('green_h2', {})
        natural_gas = metrics.get('natural_gas', {})
        diff = metrics.get('difference', {})

        lcoe_green = green_h2.get('lcoe', 0)
        lcoe_ng = natural_gas.get('lcoe', 0)
        carbon_green = green_h2.get('carbon_intensity', 0)
        carbon_ng = natural_gas.get('carbon_intensity', 0)

        cost_diff_pct = diff.get('lcoe_pct', 0)
        carbon_reduction = diff.get('carbon_pct', 0)

        # 构建多段文本，使用较小的字体
        conclusion = f"""对比分析结论
Comparison Conclusions

1. 成本差异 Cost Difference
   绿氢LCOE比天然气
   {'高' if cost_diff_pct > 0 else '低'} {abs(cost_diff_pct):.1f}%

2. 碳排放优势 Carbon Advantage
   绿氢碳强度
   {'减少' if carbon_reduction < 0 else '增加'} {abs(carbon_reduction):.1f}%

3. 环保价值 Environmental Value
   {'绿氢符合CORSIA标准' if carbon_green < 30 else '接近CORSIA标准'}
   助力碳中和目标

4. 未来趋势 Future Trend
   技术进步和规模化
   将缩小成本差距

5. 政策建议 Policy
   加大绿氢补贴力度
   加快基础设施建设"""

        # 使用更小的字体，调整位置，确保文本在可见区域内
        ax.text(0.08, 0.95, conclusion, ha='left', va='top',
                fontsize=7, family='sans-serif', linespacing=1.3)

        # 绘制更大的边框，确保完全覆盖文本区域
        ax.add_patch(mpatches.Rectangle((0.02, 0.02), 0.96, 0.96,
                                       fill=False, edgecolor='black', linewidth=2))


def main():
    """主函数：生成对比仪表板"""
    print("=" * 80)
    print("绿氢+CO₂制SAF vs 天然气制SAF 方法对比分析")
    print("Green Hydrogen + CO₂ to SAF vs Natural Gas to SAF Comparison")
    print("=" * 80)

    # 定义结果目录
    base_dir = Path(__file__).parent.parent.parent.parent
    green_h2_results_dir = base_dir / 'green_hydrogen_supply_chain_optimization' / 'results'
    natural_gas_results_dir = base_dir / 'natural_gas_supply_chain_optimization' / 'results'

    # 创建可视化器
    visualizer = GreenH2VsNaturalGasComparison(
        green_h2_results_dir=str(green_h2_results_dir),
        natural_gas_results_dir=str(natural_gas_results_dir)
    )

    # 加载数据
    green_h2_summary, natural_gas_summary = visualizer.load_data()

    if green_h2_summary is None or natural_gas_summary is None:
        logger.error("无法加载数据，请检查结果文件是否存在")
        print("\n❌ 错误: 未找到优化结果文件")
        print(f"   绿氢结果目录: {green_h2_results_dir}")
        print(f"   天然气结果目录: {natural_gas_results_dir}")
        return

    # 提取对比指标
    metrics = visualizer.extract_comparison_metrics(green_h2_summary, natural_gas_summary)

    # 创建仪表板
    output_path = visualizer.create_dashboard(metrics)

    print("\n" + "=" * 80)
    print("对比仪表板生成完成!")
    print(f"保存路径: {output_path}")
    print("=" * 80)


if __name__ == '__main__':
    main()
