"""
FT一步法 vs 两步法优化结果对比可视化工具
生成精美的多维度对比仪表盘
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import seaborn as sns
from pathlib import Path
from datetime import datetime
import warnings
import matplotlib as mpl
from matplotlib.font_manager import FontProperties
warnings.filterwarnings('ignore')

# 设置中文字体 - 完整的字体配置方案
import matplotlib.font_manager as fm
import os

# 清除matplotlib字体缓存(如果需要)
# import shutil
# cache_dir = mpl.get_cachedir()
# if os.path.exists(cache_dir):
#     shutil.rmtree(cache_dir)

# 多种字体路径尝试
font_paths = [
    r'C:\Windows\Fonts\msyh.ttc',      # 微软雅黑
    r'C:\Windows\Fonts\msyhbd.ttc',    # 微软雅黑粗体
    r'C:\Windows\Fonts\simhei.ttf',    # 黑体
    r'C:\Windows\Fonts\simsun.ttc',    # 宋体
]

font_loaded = False
for font_path in font_paths:
    if os.path.exists(font_path):
        try:
            # 注册字体
            fm.fontManager.addfont(font_path)
            font_prop = FontProperties(fname=font_path)
            font_name = font_prop.get_name()

            # 设置为默认字体
            plt.rcParams['font.family'] = 'sans-serif'
            plt.rcParams['font.sans-serif'] = [font_name] + plt.rcParams['font.sans-serif']

            print(f"成功加载字体: {font_name} (路径: {font_path})")
            font_loaded = True
            break
        except Exception as e:
            print(f"字体加载失败 {font_path}: {e}")
            continue

if not font_loaded:
    print("使用默认字体配置")
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS', 'DejaVu Sans']

plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题
mpl.rcParams['font.size'] = 10

# 验证字体设置
print(f"当前字体族: {plt.rcParams['font.family']}")
print(f"当前sans-serif字体列表: {plt.rcParams['font.sans-serif'][:3]}")

# 设置样式
sns.set_style("whitegrid")
plt.rcParams['figure.dpi'] = 100
plt.rcParams['savefig.dpi'] = 300


class MethodComparisonVisualizer:
    """FT一步法与两步法对比可视化器"""

    def __init__(self):
        """初始化可视化器"""
        self.one_step_data = None
        self.two_step_data = None
        self.comparison_metrics = {}

        # 配色方案
        self.colors = {
            'one_step': '#1f77b4',  # 专业蓝
            'two_step': '#ff7f0e',  # 活力橙
            'background': '#f5f5f5',
            'card': '#ffffff',
            'text': '#333333',
            'grid': '#e0e0e0'
        }

    def load_data(self, one_step_file, two_step_file):
        """
        加载一步法和两步法的优化结果数据

        Args:
            one_step_file: FT一步法结果文件路径
            two_step_file: 两步法结果文件路径
        """
        print(f"正在加载FT一步法数据: {one_step_file}")
        self.one_step_data = pd.read_csv(one_step_file)

        print(f"正在加载两步法数据: {two_step_file}")
        self.two_step_data = pd.read_csv(two_step_file)

        print("数据加载完成!")

    def extract_comparison_metrics(self):
        """提取关键对比指标"""
        print("\n正在提取对比指标...")

        # 一步法指标
        one_step = self.one_step_data.iloc[0]
        two_step = self.two_step_data.iloc[0]

        self.comparison_metrics = {
            'one_step': {
                # 核心经济指标
                'lcoe': one_step['生命周期平准化成本(元/kg)'],
                'annual_cost': one_step['年化平准化成本(元/kg)'],
                'total_cost': one_step['生命周期总成本(元)'],

                # 需求满足
                'demand_fulfillment': one_step['需求满足比例(%)'],

                # 生产指标
                'annual_production': one_step['年产量(kg)'],
                'total_production': one_step['20年总产量(kg)'],

                # 环境指标
                'carbon_intensity': one_step['碳强度(kg CO2eq/kg SAF)'],
                'vs_jet_fuel': one_step['相比传统航煤(%)'],
                'vs_corsia': one_step['相比CORSIA标准(%)'],

                # 成本结构
                'capex_mtj': one_step['MTJ工厂建设投资(元)'],
                'opex_mtj': one_step['MTJ生产运营成本(元)'],
                'ng_cost': one_step['天然气原料成本(元)'],
                'transport_cost': one_step['MTJ运输运营成本(元)'],
            },
            'two_step': {
                # 核心经济指标
                'lcoe': two_step['生命周期平准化成本(元/kg)'],
                'annual_cost': two_step['年化平准化成本(元/kg)'],
                'total_cost': two_step['生命周期总成本(元)'],

                # 需求满足
                'demand_fulfillment': two_step['需求满足比例(%)'],

                # 生产指标
                'annual_production': two_step['年产量(kg)'],
                'total_production': two_step['20年总产量(kg)'],

                # 环境指标
                'carbon_intensity': two_step['碳强度(kg CO2eq/kg SAF)'],
                'vs_jet_fuel': two_step['相比传统航煤(%)'],
                'vs_corsia': two_step['相比CORSIA标准(%)'],

                # 能源效率
                'h2_efficiency': two_step.get('电解制氢实际效率(%)', 80.0),
                'mtj_efficiency': two_step.get('MTJ转化效率(%)', 85.0),
                'overall_efficiency': two_step.get('综合电力转MTJ效率(%)', 68.0),

                # 成本结构
                'capex_mtj': two_step['MTJ工厂建设投资(元)'],
                'capex_electrolyzer': two_step['电解槽建设投资(元)'],
                'opex_mtj': two_step['MTJ生产运营成本(元)'],
                'h2_cost': two_step['氢气制取成本(元)'],
                'electricity_cost': two_step['电力成本(元)'],
                'transport_cost': two_step['MTJ运输运营成本(元)'],
            }
        }

        # 计算对比差异
        self.comparison_metrics['difference'] = {
            'lcoe_diff': self.comparison_metrics['one_step']['lcoe'] - self.comparison_metrics['two_step']['lcoe'],
            'lcoe_pct': (self.comparison_metrics['one_step']['lcoe'] / self.comparison_metrics['two_step']['lcoe'] - 1) * 100,
            'carbon_diff': self.comparison_metrics['one_step']['carbon_intensity'] - self.comparison_metrics['two_step']['carbon_intensity'],
            'carbon_pct': (self.comparison_metrics['one_step']['carbon_intensity'] / self.comparison_metrics['two_step']['carbon_intensity'] - 1) * 100,
        }

        print("对比指标提取完成!")
        print(f"  FT一步法平准化成本: {self.comparison_metrics['one_step']['lcoe']:.3f} 元/kg")
        print(f"  两步法平准化成本: {self.comparison_metrics['two_step']['lcoe']:.3f} 元/kg")
        print(f"  成本差异: {self.comparison_metrics['difference']['lcoe_diff']:.3f} 元/kg ({self.comparison_metrics['difference']['lcoe_pct']:.1f}%)")

    def create_dashboard(self, output_dir):
        """
        创建综合对比仪表盘

        Args:
            output_dir: 输出目录路径
        """
        print("\n正在创建综合对比仪表盘...")

        # 创建大画布
        fig = plt.figure(figsize=(20, 12))
        fig.suptitle('FT一步法 vs 两步法优化结果对比仪表盘',
                     fontsize=24, fontweight='bold', y=0.98)

        # 设置背景色
        fig.patch.set_facecolor(self.colors['background'])

        # 创建网格布局
        gs = gridspec.GridSpec(3, 3, figure=fig, hspace=0.3, wspace=0.3,
                              left=0.05, right=0.95, top=0.93, bottom=0.05)

        # 1. 核心指标对比 (左上, 占2列)
        ax1 = fig.add_subplot(gs[0, :2])
        self._plot_core_metrics_comparison(ax1)

        # 2. 综合评分雷达图 (右上)
        ax2 = fig.add_subplot(gs[0, 2], projection='polar')
        self._plot_radar_chart(ax2)

        # 3. 成本结构对比 (中间行, 占3列)
        ax3 = fig.add_subplot(gs[1, :])
        self._plot_cost_structure(ax3)

        # 4. 环境影响对比 (左下)
        ax4 = fig.add_subplot(gs[2, 0])
        self._plot_environmental_impact(ax4)

        # 5. KPI卡片 (中下和右下)
        ax5 = fig.add_subplot(gs[2, 1])
        self._plot_kpi_cards(ax5)

        # 6. 能源效率对比 (右下)
        ax6 = fig.add_subplot(gs[2, 2])
        self._plot_energy_efficiency(ax6)

        # 保存图表
        output_path = Path(output_dir) / f'method_comparison_dashboard_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
        plt.savefig(output_path, dpi=300, bbox_inches='tight',
                   facecolor=self.colors['background'])
        print(f"仪表盘已保存至: {output_path}")

        plt.close()

        return output_path

    def _plot_core_metrics_comparison(self, ax):
        """绘制核心指标对比柱状图"""
        metrics = ['平准化成本\n(元/kg)', '需求满足率\n(%)', '年产量\n(万吨)']
        one_step_values = [
            self.comparison_metrics['one_step']['lcoe'],
            self.comparison_metrics['one_step']['demand_fulfillment'],
            self.comparison_metrics['one_step']['annual_production'] / 1e7  # 转换为万吨
        ]
        two_step_values = [
            self.comparison_metrics['two_step']['lcoe'],
            self.comparison_metrics['two_step']['demand_fulfillment'],
            self.comparison_metrics['two_step']['annual_production'] / 1e7
        ]

        x = np.arange(len(metrics))
        width = 0.35

        bars1 = ax.bar(x - width/2, one_step_values, width, label='FT一步法',
                      color=self.colors['one_step'], alpha=0.8, edgecolor='black', linewidth=1.5)
        bars2 = ax.bar(x + width/2, two_step_values, width, label='两步法',
                      color=self.colors['two_step'], alpha=0.8, edgecolor='black', linewidth=1.5)

        ax.set_xlabel('指标类别', fontsize=12, fontweight='bold')
        ax.set_ylabel('数值', fontsize=12, fontweight='bold')
        ax.set_title('核心指标对比', fontsize=14, fontweight='bold', pad=15)
        ax.set_xticks(x)
        ax.set_xticklabels(metrics, fontsize=11)
        ax.legend(fontsize=11, loc='upper right', framealpha=0.9)
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        ax.set_facecolor('white')

        # 添加数值标签
        for bar in bars1 + bars2:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height:.2f}',
                   ha='center', va='bottom', fontsize=10, fontweight='bold')

    def _plot_radar_chart(self, ax):
        """绘制雷达图展示多维度性能"""
        categories = ['经济性', '环保性', '生产效率', '需求满足', '能源利用']

        # 归一化指标 (0-100分)
        one_step_scores = [
            100 - (self.comparison_metrics['one_step']['lcoe'] - 5) * 20,  # 成本越低越好
            100 - self.comparison_metrics['one_step']['carbon_intensity'] * 20,  # 碳强度越低越好
            80,  # 生产效率基准分
            self.comparison_metrics['one_step']['demand_fulfillment'],
            75  # 天然气利用效率假设
        ]

        two_step_scores = [
            100 - (self.comparison_metrics['two_step']['lcoe'] - 5) * 20,
            100 - self.comparison_metrics['two_step']['carbon_intensity'] * 20,
            85,  # 两步法转化效率略高
            self.comparison_metrics['two_step']['demand_fulfillment'],
            self.comparison_metrics['two_step'].get('overall_efficiency', 68)
        ]

        # 闭合雷达图
        angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
        one_step_scores += one_step_scores[:1]
        two_step_scores += two_step_scores[:1]
        angles += angles[:1]

        ax.plot(angles, one_step_scores, 'o-', linewidth=2, label='FT一步法',
               color=self.colors['one_step'], markersize=8)
        ax.fill(angles, one_step_scores, alpha=0.25, color=self.colors['one_step'])

        ax.plot(angles, two_step_scores, 'o-', linewidth=2, label='两步法',
               color=self.colors['two_step'], markersize=8)
        ax.fill(angles, two_step_scores, alpha=0.25, color=self.colors['two_step'])

        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(categories, fontsize=10)
        ax.set_ylim(0, 100)
        ax.set_title('多维度性能雷达图', fontsize=14, fontweight='bold', pad=20)
        ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1), fontsize=10)
        ax.grid(True, linestyle='--', alpha=0.5)

    def _plot_cost_structure(self, ax):
        """绘制成本结构对比堆叠柱状图"""
        # 一步法成本结构
        one_step_costs = {
            'MTJ工厂建设': self.comparison_metrics['one_step']['capex_mtj'],
            'MTJ运营': self.comparison_metrics['one_step']['opex_mtj'],
            '天然气原料': self.comparison_metrics['one_step']['ng_cost'],
            '运输': self.comparison_metrics['one_step']['transport_cost'],
        }

        # 两步法成本结构
        two_step_costs = {
            'MTJ工厂建设': self.comparison_metrics['two_step']['capex_mtj'],
            '电解槽建设': self.comparison_metrics['two_step']['capex_electrolyzer'],
            'MTJ运营': self.comparison_metrics['two_step']['opex_mtj'],
            '氢气制取': self.comparison_metrics['two_step']['h2_cost'],
            '电力': self.comparison_metrics['two_step']['electricity_cost'],
            '运输': self.comparison_metrics['two_step']['transport_cost'],
        }

        # 计算总成本和占比
        one_step_total = sum(one_step_costs.values())
        two_step_total = sum(two_step_costs.values())

        # 转换为亿元并计算占比
        one_step_pcts = {k: v/one_step_total*100 for k, v in one_step_costs.items()}
        two_step_pcts = {k: v/two_step_total*100 for k, v in two_step_costs.items()}

        # 准备数据
        methods = ['FT一步法', '两步法']

        # 绘制堆叠柱状图
        colors_palette = plt.cm.Set3(np.linspace(0, 1, 10))

        # 一步法
        bottom = 0
        for i, (category, pct) in enumerate(one_step_pcts.items()):
            ax.barh(0, pct, left=bottom, height=0.5,
                   label=category if i < len(one_step_pcts) else '',
                   color=colors_palette[i], alpha=0.8, edgecolor='black', linewidth=0.5)
            if pct > 5:  # 只标注占比大于5%的
                ax.text(bottom + pct/2, 0, f'{pct:.1f}%',
                       ha='center', va='center', fontsize=9, fontweight='bold')
            bottom += pct

        # 两步法
        bottom = 0
        for i, (category, pct) in enumerate(two_step_pcts.items()):
            ax.barh(1, pct, left=bottom, height=0.5,
                   label=category if category not in one_step_pcts else '',
                   color=colors_palette[i + len(one_step_pcts) if category not in one_step_pcts else list(one_step_pcts.keys()).index(category)],
                   alpha=0.8, edgecolor='black', linewidth=0.5)
            if pct > 5:
                ax.text(bottom + pct/2, 1, f'{pct:.1f}%',
                       ha='center', va='center', fontsize=9, fontweight='bold')
            bottom += pct

        ax.set_yticks([0, 1])
        ax.set_yticklabels(methods, fontsize=12, fontweight='bold')
        ax.set_xlabel('成本占比 (%)', fontsize=12, fontweight='bold')
        ax.set_title('生命周期成本结构对比', fontsize=14, fontweight='bold', pad=15)
        ax.set_xlim(0, 100)
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=9,
                 framealpha=0.9, ncol=1)
        ax.grid(axis='x', alpha=0.3, linestyle='--')
        ax.set_facecolor('white')

        # 添加总成本标注
        ax.text(102, 0, f'总成本:\n{one_step_total/1e8:.1f}亿元',
               ha='left', va='center', fontsize=10, fontweight='bold',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))
        ax.text(102, 1, f'总成本:\n{two_step_total/1e8:.1f}亿元',
               ha='left', va='center', fontsize=10, fontweight='bold',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))

    def _plot_environmental_impact(self, ax):
        """绘制环境影响对比"""
        categories = ['碳强度\n(kg CO2eq/kg)', '相比传统\n航煤(%)', '相比CORSIA\n标准(%)']
        one_step_values = [
            self.comparison_metrics['one_step']['carbon_intensity'],
            self.comparison_metrics['one_step']['vs_jet_fuel'],
            self.comparison_metrics['one_step']['vs_corsia']
        ]
        two_step_values = [
            self.comparison_metrics['two_step']['carbon_intensity'],
            self.comparison_metrics['two_step']['vs_jet_fuel'],
            self.comparison_metrics['two_step']['vs_corsia']
        ]

        x = np.arange(len(categories))
        width = 0.35

        bars1 = ax.bar(x - width/2, one_step_values, width, label='FT一步法',
                      color=self.colors['one_step'], alpha=0.8, edgecolor='black', linewidth=1.5)
        bars2 = ax.bar(x + width/2, two_step_values, width, label='两步法',
                      color=self.colors['two_step'], alpha=0.8, edgecolor='black', linewidth=1.5)

        ax.set_xlabel('环境指标', fontsize=11, fontweight='bold')
        ax.set_ylabel('数值', fontsize=11, fontweight='bold')
        ax.set_title('环境影响对比', fontsize=13, fontweight='bold', pad=12)
        ax.set_xticks(x)
        ax.set_xticklabels(categories, fontsize=9)
        ax.legend(fontsize=9, loc='upper right', framealpha=0.9)
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        ax.set_facecolor('white')

        # 添加数值标签
        for bar in bars1 + bars2:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height:.2f}',
                   ha='center', va='bottom', fontsize=8, fontweight='bold')

    def _plot_kpi_cards(self, ax):
        """绘制KPI卡片"""
        ax.axis('off')

        # 关键KPI
        kpis = [
            {
                'title': '成本优势',
                'one_step': f"{self.comparison_metrics['one_step']['lcoe']:.2f}元/kg",
                'two_step': f"{self.comparison_metrics['two_step']['lcoe']:.2f}元/kg",
                'diff': f"{self.comparison_metrics['difference']['lcoe_pct']:.1f}%",
                'winner': 'one_step' if self.comparison_metrics['difference']['lcoe_diff'] < 0 else 'two_step'
            },
            {
                'title': '碳排放优势',
                'one_step': f"{self.comparison_metrics['one_step']['carbon_intensity']:.2f}",
                'two_step': f"{self.comparison_metrics['two_step']['carbon_intensity']:.2f}",
                'diff': f"{self.comparison_metrics['difference']['carbon_pct']:.1f}%",
                'winner': 'two_step' if self.comparison_metrics['difference']['carbon_diff'] > 0 else 'one_step'
            }
        ]

        y_pos = 0.8
        for kpi in kpis:
            # 标题
            ax.text(0.5, y_pos, kpi['title'], ha='center', va='top',
                   fontsize=13, fontweight='bold',
                   bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.5))

            # FT一步法
            color1 = 'green' if kpi['winner'] == 'one_step' else 'gray'
            ax.text(0.25, y_pos - 0.12, f"FT: {kpi['one_step']}",
                   ha='center', va='top', fontsize=11, color=color1, fontweight='bold')

            # 两步法
            color2 = 'green' if kpi['winner'] == 'two_step' else 'gray'
            ax.text(0.75, y_pos - 0.12, f"两步: {kpi['two_step']}",
                   ha='center', va='top', fontsize=11, color=color2, fontweight='bold')

            # 差异
            ax.text(0.5, y_pos - 0.24, f"差异: {kpi['diff']}",
                   ha='center', va='top', fontsize=10, style='italic')

            y_pos -= 0.45

        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_title('关键KPI对比', fontsize=13, fontweight='bold')

    def _plot_energy_efficiency(self, ax):
        """绘制能源效率对比"""
        # 两步法能源效率数据
        two_step_efficiency = [
            self.comparison_metrics['two_step'].get('h2_efficiency', 80),
            self.comparison_metrics['two_step'].get('mtj_efficiency', 85),
            self.comparison_metrics['two_step'].get('overall_efficiency', 68)
        ]

        # FT一步法假设天然气转化效率
        one_step_efficiency = [75, 0, 0]  # 只有一步转化

        categories = ['氢气制取\n效率(%)', 'MTJ转化\n效率(%)', '综合\n效率(%)']
        x = np.arange(len(categories))
        width = 0.35

        # 只显示两步法的完整数据
        bars1 = ax.bar(x - width/2, one_step_efficiency, width, label='FT一步法',
                      color=self.colors['one_step'], alpha=0.8, edgecolor='black', linewidth=1.5)
        bars2 = ax.bar(x + width/2, two_step_efficiency, width, label='两步法',
                      color=self.colors['two_step'], alpha=0.8, edgecolor='black', linewidth=1.5)

        ax.set_xlabel('效率指标', fontsize=11, fontweight='bold')
        ax.set_ylabel('效率 (%)', fontsize=11, fontweight='bold')
        ax.set_title('能源转换效率对比', fontsize=13, fontweight='bold', pad=12)
        ax.set_xticks(x)
        ax.set_xticklabels(categories, fontsize=9)
        ax.set_ylim(0, 100)
        ax.legend(fontsize=9, loc='upper right', framealpha=0.9)
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        ax.set_facecolor('white')

        # 添加数值标签
        for bars in [bars1, bars2]:
            for bar in bars:
                height = bar.get_height()
                if height > 0:
                    ax.text(bar.get_x() + bar.get_width()/2., height,
                           f'{height:.0f}%',
                           ha='center', va='bottom', fontsize=9, fontweight='bold')


def find_latest_result_files(results_dir):
    """
    自动查找最新的优化结果文件

    Args:
        results_dir: 结果目录路径

    Returns:
        (one_step_file, two_step_file): 最新的一步法和两步法结果文件
    """
    import glob

    # 查找所有优化结果文件
    all_files = glob.glob(str(results_dir / 'optimization_summary_*.csv'))

    if not all_files:
        raise FileNotFoundError(f"未找到任何优化结果文件: {results_dir}")

    # 按修改时间排序(最新的在前)
    all_files.sort(key=lambda x: Path(x).stat().st_mtime, reverse=True)

    print(f"\n找到 {len(all_files)} 个优化结果文件:")

    one_step_file = None
    two_step_file = None

    # 检查每个文件以判断是一步法还是两步法
    for file_path in all_files:
        df = pd.read_csv(file_path, nrows=0)  # 只读取列名
        columns = df.columns.tolist()

        # 两步法特征: 包含电解槽和氢气相关列
        is_two_step = '电解槽建设投资(元)' in columns and '氢气制取成本(元)' in columns
        # 一步法特征: 包含天然气原料成本但不包含电解槽
        is_one_step = '天然气原料成本(元)' in columns and '电解槽建设投资(元)' not in columns

        file_name = Path(file_path).name
        timestamp = file_name.replace('optimization_summary_', '').replace('.csv', '')

        if is_two_step and two_step_file is None:
            two_step_file = Path(file_path)
            print(f"  [*] 两步法 (最新): {file_name}")
        elif is_one_step and one_step_file is None:
            one_step_file = Path(file_path)
            print(f"  [*] 一步法 (最新): {file_name}")
        else:
            method = "两步法" if is_two_step else "一步法" if is_one_step else "未知"
            print(f"      {method}: {file_name}")

        # 如果两种文件都找到了,就退出循环
        if one_step_file and two_step_file:
            break

    if not one_step_file:
        raise FileNotFoundError("未找到FT一步法结果文件")
    if not two_step_file:
        raise FileNotFoundError("未找到两步法结果文件")

    return one_step_file, two_step_file


def main():
    """主函数"""
    print("="*60)
    print("FT一步法 vs 两步法优化结果对比可视化")
    print("="*60)

    # 初始化可视化器
    visualizer = MethodComparisonVisualizer()

    # 设置文件路径
    base_dir = Path(__file__).parent.parent.parent
    results_dir = base_dir / 'results'

    # 自动查找最新结果文件
    try:
        one_step_file, two_step_file = find_latest_result_files(results_dir)
    except FileNotFoundError as e:
        print(f"错误: {e}")
        return

    # 加载数据
    visualizer.load_data(one_step_file, two_step_file)

    # 提取对比指标
    visualizer.extract_comparison_metrics()

    # 创建输出目录
    output_dir = results_dir / 'comparisons'
    output_dir.mkdir(exist_ok=True)

    # 生成对比仪表盘
    dashboard_path = visualizer.create_dashboard(output_dir)

    print("\n" + "="*60)
    print("可视化完成!")
    print(f"仪表盘保存至: {dashboard_path}")
    print("="*60)


if __name__ == '__main__':
    main()
