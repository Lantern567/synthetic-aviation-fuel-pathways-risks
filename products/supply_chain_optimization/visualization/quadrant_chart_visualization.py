"""
SAF场景象限图可视化
Quadrant Chart Visualization for SAF Scenarios

功能：
- X轴：碳排放（相对减排百分比），以0为分界点
- Y轴：LCOE成本（元/kg），以18元/kg（SAF市场售价）为分界点
- 四象限背景色区分不同区域
- 点大小表示产量，颜色表示场景类型

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
from adjustText import adjust_text

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class QuadrantChartVisualizer:
    """SAF场景象限图可视化器"""

    def __init__(self, cost_threshold: float = 18.0, carbon_threshold: float = 0.0):
        """
        初始化可视化器

        Args:
            cost_threshold: 成本分界点（元/kg），默认18元（SAF市场售价）
            carbon_threshold: 碳排放分界点（%），默认0%
        """
        self.cost_threshold = cost_threshold
        self.carbon_threshold = carbon_threshold

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
        self.modules = {
            # ========== Grey灰色系 - 煤基路径 (2个) ==========
            'Coal Hydrogen': {
                'name_en': 'CTL',
                'category': 'Grey',
                'color': '#666666',  # 深灰
                'solution_pattern': str(self.project_root / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/complete_solution_*.json'),
                'carbon_pattern': str(self.project_root / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/carbon_emissions_detailed_*.json')
            },
            'Byproduct H2 + Coal': {
                'name_en': 'CTL-BH',
                'category': 'Grey',
                'color': '#999999',  # 浅灰
                'solution_pattern': str(self.project_root / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/byproduct_hydrogen/complete_solution_*.json'),
                'carbon_pattern': str(self.project_root / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/byproduct_hydrogen/carbon_emissions_detailed_*.json')
            },
            # ========== Green绿色系 - 绿氢路径 (4个) ==========
            'DAC Two-Step': {
                'name_en': 'DAC-GH-MTJ',
                'category': 'Green',
                'color': '#145a32',  # 深绿
                'solution_pattern': str(self.project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/two_step/complete_solution_*.json'),
                'carbon_pattern': str(self.project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/two_step/carbon_emissions_detailed_*.json')
            },
            'DAC One-Step': {
                'name_en': 'DAC-GH-FT',
                'category': 'Green',
                'color': '#1e8449',  # 绿
                'solution_pattern': str(self.project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/one_step/complete_solution_*.json'),
                'carbon_pattern': str(self.project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/one_step/carbon_emissions_detailed_*.json')
            },
            'Green H2 Two-Step': {
                'name_en': 'CCU-GH-MTJ',
                'category': 'Green',
                'color': '#27ae60',  # 标准绿
                'solution_pattern': str(self.project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/two_step/complete_solution_*.json'),
                'carbon_pattern': str(self.project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/two_step/carbon_emissions_detailed_*.json')
            },
            'Green H2 One-Step': {
                'name_en': 'CCU-GH-FT',
                'category': 'Green',
                'color': '#58d68d',  # 浅绿
                'solution_pattern': str(self.project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/one_step/complete_solution_*.json'),
                'carbon_pattern': str(self.project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/one_step/carbon_emissions_detailed_*.json')
            },
            # ========== Blue蓝色系 - 副产氢/天然气路径 (7个) ==========
            'Natural Gas Two-Step': {
                'name_en': 'GTL-GH-MTJ',
                'category': 'Blue',
                'color': '#5dade2',  # 浅蓝
                'solution_pattern': str(self.project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/complete_solution_*.json'),
                'carbon_pattern': str(self.project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/carbon_emissions_detailed_*.json')
            },
            'Natural Gas One-Step': {
                'name_en': 'GTL-GH-FT',
                'category': 'Blue',
                'color': '#85c1e9',  # 更浅蓝
                'solution_pattern': str(self.project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/ft_one_step/complete_solution_*.json'),
                'carbon_pattern': str(self.project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/ft_one_step/carbon_emissions_detailed_*.json')
            },
            'Byproduct H2 + DAC Two-Step': {
                'name_en': 'DAC-BH-MTJ',
                'category': 'Blue',
                'color': '#1a5276',  # 深蓝
                'solution_pattern': str(self.project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/two_step/complete_solution_*.json'),
                'carbon_pattern': str(self.project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/two_step/carbon_emissions_detailed_*.json')
            },
            'Byproduct H2 + DAC One-Step': {
                'name_en': 'DAC-BH-FT',
                'category': 'Blue',
                'color': '#2874a6',  # 蓝
                'solution_pattern': str(self.project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/one_step/complete_solution_*.json'),
                'carbon_pattern': str(self.project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/one_step/carbon_emissions_detailed_*.json')
            },
            'Byproduct H2 + NG Two-Step': {
                'name_en': 'GTL-BH-MTJ',
                'category': 'Blue',
                'color': '#3498db',  # 标准蓝
                'solution_pattern': str(self.project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/byproduct_hydrogen/byproduct_hydrogen/two_step/complete_solution_*.json'),
                'carbon_pattern': str(self.project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/byproduct_hydrogen/byproduct_hydrogen/two_step/carbon_emissions_detailed_*.json')
            },
            'Byproduct H2 Two-Step': {
                'name_en': 'CCU-BH-MTJ',
                'category': 'Blue',
                'color': '#aed6f1',  # 淡蓝
                'solution_pattern': str(self.project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/two_step/complete_solution_*.json'),
                'carbon_pattern': str(self.project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/two_step/carbon_emissions_detailed_*.json')
            },
            'Byproduct H2 One-Step': {
                'name_en': 'CCU-BH-FT',
                'category': 'Blue',
                'color': '#d4e6f1',  # 最淡蓝
                'solution_pattern': str(self.project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/one_step/complete_solution_*.json'),
                'carbon_pattern': str(self.project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/one_step/carbon_emissions_detailed_*.json')
            }
        }

        # 类别颜色映射（三色系）
        self.category_colors = {
            'Grey': '#808080',   # 灰色系代表色
            'Blue': '#3498db',   # 蓝色系代表色
            'Green': '#27ae60'   # 绿色系代表色
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
                vs_traditional = carbon_data.get('vs_traditional_jet', 0)
                production = solution_data.get('lifecycle_total_production_kg', 0) / 1e6  # 转换为千吨

                self.data[module_name] = {
                    'name_en': config['name_en'],
                    'category': config['category'],
                    'color': config['color'],
                    'lcoe': lcoe,
                    'carbon_reduction': vs_traditional,
                    'production': production
                }

                logger.info(f"  LCOE: {lcoe:.2f} 元/kg")
                logger.info(f"  碳排放: {vs_traditional:.1f}%")
                logger.info(f"  产量: {production:.1f} 千吨")

            except Exception as e:
                logger.error(f"  加载失败: {e}")
                continue

        logger.info(f"\n成功加载 {len(self.data)} 个场景")

    def plot_quadrant_chart(self):
        """绑制象限图 - 参考学术论文风格"""
        logger.info("\n生成象限图...")

        # 设置字体 - Arial
        plt.rcParams['font.family'] = 'Arial'
        plt.rcParams['axes.unicode_minus'] = False

        # 创建图形 - 图例放在图内，不需要额外空间
        fig = plt.figure(figsize=(12, 9))

        # 使用gridspec创建布局：主图占满
        gs = fig.add_gridspec(1, 1, left=0.10, right=0.95, top=0.92, bottom=0.10)
        ax = fig.add_subplot(gs[0, 0])

        # 获取数据范围
        x_values = [d['carbon_reduction'] for d in self.data.values()]
        y_values = [d['lcoe'] for d in self.data.values()]

        # X轴范围：让分界点0%不在边缘，使用非整数起始点
        x_data_min = min(x_values)
        x_data_max = max(x_values)
        x_margin = 30
        x_min = x_data_min - x_margin  # 非整数起始点
        x_max = x_data_max + x_margin  # 非整数结束点

        # Y轴范围：让分界点18不在边缘，使用非整数起始点
        y_data_min = min(y_values)
        y_margin = 3
        y_min = max(0, y_data_min - y_margin)  # 非整数起始点，但不小于0
        y_max = max(y_values) + y_margin

        # ========== 绘制四象限背景色（简洁优雅配色） ==========
        # 左下：淡绿色（低碳+低成本）- Green & Economic - 最佳区域
        ax.fill_between([x_min, self.carbon_threshold], y_min, self.cost_threshold,
                        color='#E8F5E9', alpha=0.8, label='_nolegend_')
        # 左上：白色（低碳+高成本）- Green but Costly
        ax.fill_between([x_min, self.carbon_threshold], self.cost_threshold, y_max,
                        color='#FFFFFF', alpha=1.0, label='_nolegend_')
        # 右下：淡灰色（高碳+低成本）- Economic but High-carbon
        ax.fill_between([self.carbon_threshold, x_max], y_min, self.cost_threshold,
                        color='#F5F5F5', alpha=0.8, label='_nolegend_')
        # 右上：淡粉色（高碳+高成本）- High-carbon & Costly - 最差区域
        ax.fill_between([self.carbon_threshold, x_max], self.cost_threshold, y_max,
                        color='#FFEBEE', alpha=0.8, label='_nolegend_')

        # ========== 绘制分界线（加粗虚线） ==========
        ax.axvline(x=self.carbon_threshold, color='#444444', linestyle='--', linewidth=1.5)
        ax.axhline(y=self.cost_threshold, color='#444444', linestyle='--', linewidth=1.5)

        # ========== 象限标注（放在图外边缘） ==========
        # 顶部标注（图外）
        ax.text(x_min + (self.carbon_threshold - x_min) / 2, y_max + 3,
                'Lower emission', fontsize=12, ha='center', va='bottom', style='italic', color='#333333')
        ax.text(self.carbon_threshold + (x_max - self.carbon_threshold) / 2, y_max + 3,
                'Higher emission', fontsize=12, ha='center', va='bottom', style='italic', color='#333333')
        # 右侧标注（图外）- 使用figure坐标
        fig.text(0.97, 0.65, 'Higher\ncost', fontsize=11, ha='left', va='center', style='italic', color='#333333')
        fig.text(0.97, 0.25, 'Lower\ncost', fontsize=11, ha='left', va='center', style='italic', color='#333333')

        # ========== 绘制气泡散点 ==========
        # 定义深色描边颜色
        def get_edge_color(fill_color):
            """根据填充色生成深色描边"""
            import matplotlib.colors as mcolors
            rgb = mcolors.to_rgb(fill_color)
            # 降低亮度作为描边色
            return tuple(max(0, c - 0.3) for c in rgb)

        # 收集所有散点坐标和标签文本
        texts = []
        scatter_x = []
        scatter_y = []

        for module_name, data in self.data.items():
            x = data['carbon_reduction']
            y = data['lcoe']
            scatter_x.append(x)
            scatter_y.append(y)
            # 产量映射到点大小（缩小气泡）
            size = max(80, min(400, data['production'] * 5))
            # 使用每个场景自己定义的颜色（深浅区分）
            fill_color = data['color']
            edge_color = get_edge_color(fill_color)

            ax.scatter(x, y, s=size, c=fill_color, alpha=0.85,
                      edgecolors=edge_color, linewidths=1.5, zorder=5)

            # 添加标签文本对象（稍后用adjustText调整，加大字体）
            text = ax.text(x, y, data['name_en'], fontsize=10, color='#333333', zorder=10)
            texts.append(text)

        # ========== 设置轴标签（加大字体） ==========
        ax.set_xlabel('Carbon emission change vs traditional jet fuel (%)',
                      fontsize=13, labelpad=10)
        ax.set_ylabel('Levelized cost of energy (CNY/kg)',
                      fontsize=13, labelpad=10)

        # ========== 设置轴范围（必须在adjust_text之前！） ==========
        ax.set_xlim(x_min, x_max)
        ax.set_ylim(y_min, y_max)

        # 设置x轴刻度间隔为100，确保-100刻度显示
        ax.xaxis.set_major_locator(MultipleLocator(100))

        # ========== 使用adjustText自动调整标签位置（必须在设置轴范围之后调用！） ==========
        # adjustText 1.3.0 新API参数 - 加大排斥力让标签远离气泡
        adjust_text(texts,
                   x=scatter_x,
                   y=scatter_y,
                   ax=ax,
                   arrowprops=dict(arrowstyle='->', color='#666666', lw=0.8),
                   force_text=(1.0, 2.0),        # 文本间排斥力（加大）
                   force_static=(5.0, 8.0),      # 点对文本的排斥力（大幅加大）
                   force_pull=(0.001, 0.001),    # 拉回原位的力（更小=允许移动更远）
                   force_explode=(2.0, 3.0),     # 初始爆炸力（加大）
                   expand=(1.5, 2.0),            # 文本边界框扩展（加大）
                   explode_radius=200,           # 爆炸半径（像素，加大）
                   ensure_inside_axes=True,
                   min_arrow_len=3,
                   iter_lim=1000)

        # ========== 添加子图标识 ==========
        ax.text(0.02, 0.98, 'a', transform=ax.transAxes, fontsize=14,
                fontweight='bold', va='top', ha='left')

        # ========== 设置刻度（加大字体） ==========
        ax.tick_params(axis='both', which='major', labelsize=12)

        # 显示四周边框
        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_linewidth(1.0)
            spine.set_color('#333333')

        # ========== 创建图例 ==========
        # 定义每组内场景的显示顺序
        pathway_order = {
            'Grey': ['CTL', 'CTL-BH'],
            'Blue': ['DAC-BH-MTJ', 'DAC-BH-FT', 'GTL-BH-MTJ', 'GTL-GH-MTJ', 'GTL-GH-FT', 'CCU-BH-MTJ', 'CCU-BH-FT'],
            'Green': ['DAC-GH-MTJ', 'DAC-GH-FT', 'CCU-GH-MTJ', 'CCU-GH-FT']
        }

        # ========== 添加图例（Quadrant和Pathway并排放在右上角） ==========
        # Quadrant图例（左侧）
        quadrant_handles = [
            mpatches.Patch(facecolor='#E8F5E9', alpha=0.8, edgecolor='gray',
                          linewidth=0.5, label='Green & Economic'),
            mpatches.Patch(facecolor='#FFFFFF', edgecolor='gray',
                          linewidth=0.5, label='Green but Costly'),
            mpatches.Patch(facecolor='#F5F5F5', alpha=0.8, edgecolor='gray',
                          linewidth=0.5, label='Economic but High-carbon'),
            mpatches.Patch(facecolor='#FFEBEE', alpha=0.8, edgecolor='gray',
                          linewidth=0.5, label='High-carbon & Costly'),
        ]
        legend1 = ax.legend(handles=quadrant_handles, loc='upper right',
                           title='Quadrant', title_fontsize=11,
                           fontsize=10, framealpha=0.95, edgecolor='gray',
                           facecolor='white',
                           bbox_to_anchor=(0.48, 0.99))
        ax.add_artist(legend1)

        # Pathway图例（右侧，三列显示，使用圆形点）
        from matplotlib.lines import Line2D

        grey_order = pathway_order['Grey']
        blue_order = pathway_order['Blue']
        green_order = pathway_order['Green']

        # 为每个色系创建handles列表（使用圆形标记）
        all_handles = []
        for name in grey_order:
            for d in self.data.values():
                if d['name_en'] == name:
                    h = Line2D([0], [0], marker='o', color='w', markerfacecolor=d['color'],
                              markeredgecolor=get_edge_color(d['color']), markersize=8,
                              markeredgewidth=1.0, label=name, linestyle='None')
                    all_handles.append(h)
                    break

        for name in blue_order:
            for d in self.data.values():
                if d['name_en'] == name:
                    h = Line2D([0], [0], marker='o', color='w', markerfacecolor=d['color'],
                              markeredgecolor=get_edge_color(d['color']), markersize=8,
                              markeredgewidth=1.0, label=name, linestyle='None')
                    all_handles.append(h)
                    break

        for name in green_order:
            for d in self.data.values():
                if d['name_en'] == name:
                    h = Line2D([0], [0], marker='o', color='w', markerfacecolor=d['color'],
                              markeredgecolor=get_edge_color(d['color']), markersize=8,
                              markeredgewidth=1.0, label=name, linestyle='None')
                    all_handles.append(h)
                    break

        # 创建三列图例
        legend2 = ax.legend(handles=all_handles, loc='upper right',
                           title='Pathway', title_fontsize=11,
                           fontsize=9, framealpha=0.95, edgecolor='gray',
                           facecolor='white',
                           bbox_to_anchor=(0.99, 0.99),
                           ncol=3,  # 三列
                           handletextpad=0.3,
                           labelspacing=0.4,
                           columnspacing=0.8)
        ax.add_artist(legend1)  # 重新添加第一个图例

        # ========== 添加阈值标注（加大字体） ==========
        ax.text(self.carbon_threshold + 5, y_min + 1, f'{self.carbon_threshold}%',
                fontsize=11, color='#444444', va='bottom', fontweight='bold')
        ax.text(x_min + 10, self.cost_threshold + 0.8, f'{self.cost_threshold} CNY/kg',
                fontsize=11, color='#444444', va='bottom', fontweight='bold')

        # 保存图片
        output_path = self.session_dir / "quadrant_chart.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
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
            is_green = data['carbon_reduction'] < self.carbon_threshold
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
                'Carbon Change (%)': f"{data['carbon_reduction']:.1f}",
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
        cost_threshold=18.0,  # SAF市场售价
        carbon_threshold=0.0   # 碳排放分界点
    )
    visualizer.run()


if __name__ == "__main__":
    main()
