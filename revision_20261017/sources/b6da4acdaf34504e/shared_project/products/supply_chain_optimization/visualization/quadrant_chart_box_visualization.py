"""
SAF场景象限图可视化 - 箱式版 v2（含逐年刻度线 + 断裂X轴 + 渐变色）

每个场景以矩形箱体表示：
  - 顶边   = 2026年优化基准LCOE（现有结果）
  - 底边   = 2036年学习曲线投影LCOE（Wright定律基准场景）
  - 内部   = 每年一条水平刻度线（2027–2035），2030年加粗高亮
  - 颜色   = 由深（2026）到浅（2036）的渐变填充，体现成本下行趋势
  - 宽度   = X轴宽度的约2%（纯视觉）

优化要点：
  1. 断裂X轴（broken axis）：压缩右侧高碳空白区
  2. 2030年加粗参考线：对应政策目标节点
  3. 渐变填充：深→浅直观表达成本下降方向
  4. 最高箱体（DAC-GH-MTJ）右侧标注年份刻度，作为全图解读参考

作者：Claude Code
创建时间：2026-04-12
"""

import json
import glob
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
from matplotlib.ticker import MultipleLocator

matplotlib.rcParams.update({
    'font.family': ['Times New Roman', 'DejaVu Sans'],
    'axes.unicode_minus': False,
})

try:
    from adjustText import adjust_text
except ImportError:
    adjust_text = None

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)


# ─── 学习曲线常量（与 generate_lcoe_projection.py 保持一致） ─────────────────

EXCLUDE_KEYS = {
    'total_investment_cost', 'total_operation_cost',
    'total_cost_excluding_shortage', 'shortage_cost', 'final_inventory_cost',
}

COST_MAP = {
    'electrolyzer_investment_cost':  'electrolyzer',
    'facility_investment_cost':      'synthesis',
    'h2_storage_investment':         'electrolyzer',
    'dac_facility_investment':       'capture_dac',
    'dac_capture_cost':              'capture_dac',
    'co2_capture_cost':              'capture_ref',
    'coal_gasification_cost':        'capture_coal',
    'electricity_cost':              'electricity',
    'dac_grid_electricity_cost':     'electricity',
    # 其余 → 'fixed'
}

LR = {
    'electrolyzer':  0.21,
    'synthesis_ft':  0.18,
    'synthesis_mtj': 0.15,
    'capture_dac':   0.12,
    'capture_coal':  0.10,
    'capture_ref':   0.06,
    'electricity':   0.04,   # 年化电价下降率（复利，非Wright定律）
}

# 全球累计装机容量轨迹 2026→2036（11个时间步）
PROJ_YEARS = np.arange(2026, 2037)          # shape (11,)
_X_pem     = np.interp(PROJ_YEARS, [2025, 2027, 2030, 2033, 2036], [60,  100, 330, 600, 950])
_X_dac     = np.interp(PROJ_YEARS, [2025, 2028, 2031, 2034, 2036], [0.1, 1.0, 4.0, 8.0, 12.0])
_X_coal    = np.interp(PROJ_YEARS, [2025, 2028, 2031, 2034, 2036], [10,  60,  180, 350, 500])
_X_gas     = np.interp(PROJ_YEARS, [2025, 2028, 2031, 2034, 2036], [20,  90,  250, 430, 600])


def _b(lr: float) -> float:
    return -np.log(1 - lr) / np.log(2)


def _cf_array(X_arr: np.ndarray, lr: float) -> np.ndarray:
    """Wright定律：返回2026→2036各年相对2026的成本系数数组（第0项恒为1）。"""
    return (X_arr / X_arr[0]) ** (-_b(lr))


# 各技术全年成本系数数组（shape 11，index 0 = 2026）
CF_ARRAY = {
    'electrolyzer':  _cf_array(_X_pem,  LR['electrolyzer']),
    'synthesis_ft':  _cf_array(_X_pem,  LR['synthesis_ft']),
    'synthesis_mtj': _cf_array(_X_pem,  LR['synthesis_mtj']),
    'capture_dac':   _cf_array(_X_dac,  LR['capture_dac']),
    'capture_coal':  _cf_array(_X_coal, LR['capture_coal']),
    'capture_ref':   _cf_array(_X_gas,  LR['capture_ref']),
    'electricity':   (1 - LR['electricity']) ** np.arange(len(PROJ_YEARS)),
    'fixed':         np.ones(len(PROJ_YEARS)),
}

FT_SCENARIOS = {
    'CTL', 'DAC-GH-FT', 'CCU-GH-FT', 'GTL',
    'DAC-BH-FT', 'CCU-BH-FT', 'GTL-BH', 'GTL-GH',
}


def compute_lcoe_projection(solution_data: dict, name_en: str) -> np.ndarray:
    """
    基于当前优化结果和基准学习曲线，计算2026→2036逐年LCOE数组（CNY/kg）。

    返回 shape=(11,) 的数组，index 0 = 2026，index 10 = 2036。
    """
    lcoe_base = solution_data.get(
        'lifecycle_levelized_cost_excluding_shortage_per_kg', 0
    )
    total = solution_data.get('objective_value_lifecycle_total', 0)
    if total == 0 or lcoe_base == 0:
        return np.full(len(PROJ_YEARS), lcoe_base)

    cb_raw = solution_data.get('cost_breakdown', {})
    cb = {k: v for k, v in cb_raw.items() if k not in EXCLUDE_KEYS and v != 0}

    cats = {
        k: 0.0
        for k in ['electrolyzer', 'synthesis', 'capture_dac',
                  'capture_coal', 'capture_ref', 'electricity', 'fixed']
    }
    for key, val in cb.items():
        cats[COST_MAP.get(key, 'fixed')] += val

    total_mapped = sum(cats.values())
    if total_mapped == 0:
        return np.full(len(PROJ_YEARS), lcoe_base)

    fracs = {k: v / total_mapped for k, v in cats.items()}
    syn_key = 'synthesis_ft' if name_en in FT_SCENARIOS else 'synthesis_mtj'

    proj = (
        fracs['electrolyzer'] * CF_ARRAY['electrolyzer'] +
        fracs['synthesis']    * CF_ARRAY[syn_key]         +
        fracs['capture_dac']  * CF_ARRAY['capture_dac']   +
        fracs['capture_coal'] * CF_ARRAY['capture_coal']  +
        fracs['capture_ref']  * CF_ARRAY['capture_ref']   +
        fracs['electricity']  * CF_ARRAY['electricity']   +
        fracs['fixed']        * CF_ARRAY['fixed']
    ) * lcoe_base

    return proj


# ─── 主类 ─────────────────────────────────────────────────────────────────────

class QuadrantBoxVisualizer:
    """SAF场景象限图可视化器（箱式区间版）"""

    # 箱体X方向半宽度（相对于各自轴数据范围的比例）
    # 左轴（70%宽、数据范围小）→ 视觉偏宽，用较小分数
    # 右轴（30%宽、数据范围大）→ 视觉偏细，用较大分数
    # 目标：两侧视觉宽度尽量接近（各占各轴物理宽度约2.5%）
    BOX_X_FRACTION_L = 0.018   # 左轴：2.5% × (70%/70%) ≈ 2.5% 图宽
    BOX_X_FRACTION_R = 0.044   # 右轴：经校准使视觉宽度≈1.8% 图宽（右轴场景聚集限制了上限）

    def __init__(
        self,
        cost_threshold: float = 8.0,
        carbon_threshold: float = 0.0,
        market_price_low: float = 6.0,
    ):
        self.cost_threshold   = cost_threshold
        self.market_price_low = market_price_low
        self.market_price_mid = (market_price_low + cost_threshold) / 2.0
        self.carbon_threshold = carbon_threshold
        self.traditional_jet_ci_gco2e_per_mj = None

        base_dir = Path(__file__).parent
        self.output_dir = base_dir / 'results'
        self.output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.session_dir = self.output_dir / f'quadrant_box_{timestamp}'
        self.session_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f'输出目录: {self.session_dir}')

        self.project_root = Path(__file__).parent.parent.parent.parent

        # 场景配置（与原象限图完全一致）
        self.modules = {
            'Coal Hydrogen': {
                'name_en': 'CTL',
                'category': 'Grey',
                'color': '#616161',
                'solution_pattern': str(self.project_root / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/complete_solution_*.json'),
                'carbon_pattern':   str(self.project_root / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/carbon_emissions_detailed_*.json'),
            },
            'Byproduct H2 + Coal': {
                'name_en': 'CTL-BH',
                'category': 'Grey',
                'color': '#9E9E9E',
                'solution_pattern': str(self.project_root / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/byproduct_hydrogen/complete_solution_*.json'),
                'carbon_pattern':   str(self.project_root / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/byproduct_hydrogen/carbon_emissions_detailed_*.json'),
            },
            'DAC Two-Step': {
                'name_en': 'DAC-GH-MTJ',
                'category': 'Green',
                'color': '#2E7D32',
                'solution_pattern': str(self.project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/two_step/complete_solution_*.json'),
                'carbon_pattern':   str(self.project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/two_step/carbon_emissions_detailed_*.json'),
            },
            'DAC One-Step': {
                'name_en': 'DAC-GH-FT',
                'category': 'Green',
                'color': '#43A047',
                'solution_pattern': str(self.project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/one_step/complete_solution_*.json'),
                'carbon_pattern':   str(self.project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/one_step/carbon_emissions_detailed_*.json'),
            },
            'Green H2 Two-Step': {
                'name_en': 'CCU-GH-MTJ',
                'category': 'Green',
                'color': '#66BB6A',
                'solution_pattern': str(self.project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/two_step/complete_solution_*.json'),
                'carbon_pattern':   str(self.project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/two_step/carbon_emissions_detailed_*.json'),
            },
            'Green H2 One-Step': {
                'name_en': 'CCU-GH-FT',
                'category': 'Green',
                'color': '#81C784',
                'solution_pattern': str(self.project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/one_step/complete_solution_*.json'),
                'carbon_pattern':   str(self.project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/one_step/carbon_emissions_detailed_*.json'),
            },
            'Natural Gas Two-Step': {
                'name_en': 'GTL-GH',
                'category': 'Blue',
                'color': '#1565C0',
                'solution_pattern': str(self.project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/complete_solution_*.json'),
                'carbon_pattern':   str(self.project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/carbon_emissions_detailed_*.json'),
            },
            'Natural Gas One-Step': {
                'name_en': 'GTL',
                'category': 'Blue',
                'color': '#1E88E5',
                'solution_pattern': str(self.project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/ft_one_step/complete_solution_*.json'),
                'carbon_pattern':   str(self.project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/ft_one_step/carbon_emissions_detailed_*.json'),
            },
            'Byproduct H2 + DAC Two-Step': {
                'name_en': 'DAC-BH-MTJ',
                'category': 'Blue',
                'color': '#42A5F5',
                'solution_pattern': str(self.project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/two_step/complete_solution_*.json'),
                'carbon_pattern':   str(self.project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/two_step/carbon_emissions_detailed_*.json'),
            },
            'Byproduct H2 + DAC One-Step': {
                'name_en': 'DAC-BH-FT',
                'category': 'Blue',
                'color': '#64B5F6',
                'solution_pattern': str(self.project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/one_step/complete_solution_*.json'),
                'carbon_pattern':   str(self.project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/one_step/carbon_emissions_detailed_*.json'),
            },
            'Byproduct H2 + NG Two-Step': {
                'name_en': 'GTL-BH',
                'category': 'Blue',
                'color': '#90CAF9',
                'solution_pattern': str(self.project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/byproduct_hydrogen/byproduct_hydrogen/two_step/complete_solution_*.json'),
                'carbon_pattern':   str(self.project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/byproduct_hydrogen/byproduct_hydrogen/two_step/carbon_emissions_detailed_*.json'),
            },
            'Byproduct H2 Two-Step': {
                'name_en': 'CCU-BH-MTJ',
                'category': 'Blue',
                'color': '#BBDEFB',
                'solution_pattern': str(self.project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/two_step/complete_solution_*.json'),
                'carbon_pattern':   str(self.project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/two_step/carbon_emissions_detailed_*.json'),
            },
            'Byproduct H2 One-Step': {
                'name_en': 'CCU-BH-FT',
                'category': 'Blue',
                'color': '#E3F2FD',
                'solution_pattern': str(self.project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/one_step/complete_solution_*.json'),
                'carbon_pattern':   str(self.project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/one_step/carbon_emissions_detailed_*.json'),
            },
        }

        self.data: Dict[str, dict] = {}
        self.pareto_optimal_names: List[str] = []

    # ── 数据加载 ──────────────────────────────────────────────────────────────

    def load_data(self):
        """加载所有场景数据，并为每个场景计算2036年投影LCOE。"""
        logger.info('=' * 60)
        logger.info('加载场景数据（含学习曲线投影）')
        logger.info('=' * 60)

        for module_name, config in self.modules.items():
            logger.info(f'\nLoading: {module_name} ({config["name_en"]})')

            solution_files = sorted(glob.glob(config['solution_pattern']), reverse=True)
            if not solution_files:
                logger.warning('  未找到解决方案文件')
                continue

            carbon_files = sorted(glob.glob(config['carbon_pattern']), reverse=True)
            if not carbon_files:
                logger.warning('  未找到碳排放文件')
                continue

            with open(solution_files[0], 'r', encoding='utf-8') as f:
                solution_data = json.load(f)
            with open(carbon_files[0], 'r', encoding='utf-8') as f:
                carbon_data = json.load(f)

            name_en = config['name_en']
            lcoe_proj = compute_lcoe_projection(solution_data, name_en)
            lcoe_now  = lcoe_proj[0]    # 2026
            lcoe_2036 = lcoe_proj[-1]   # 2036
            production = solution_data.get('lifecycle_total_production_kg', 0) / 1e6

            traditional_jet_ci = carbon_data.get('traditional_jet_ci_gco2e_per_mj', 89)
            if self.traditional_jet_ci_gco2e_per_mj is None:
                self.traditional_jet_ci_gco2e_per_mj = traditional_jet_ci

            carbon_diff = carbon_data.get('abs_diff_vs_traditional_jet_gco2e_per_mj', None)
            if carbon_diff is None:
                if 'carbon_intensity_mj' in carbon_data:
                    carbon_diff = carbon_data.get('carbon_intensity_mj', 0) - traditional_jet_ci
                else:
                    vs_trad = carbon_data.get('vs_traditional_jet', 0)
                    carbon_diff = traditional_jet_ci * (vs_trad / 100.0)

            self.data[module_name] = {
                'name_en':    name_en,
                'category':   config['category'],
                'color':      config['color'],
                'lcoe':       lcoe_now,        # 箱体顶边（2026基准）
                'lcoe_2036':  lcoe_2036,       # 箱体底边（2036投影）
                'lcoe_proj':  lcoe_proj,        # 逐年数组（11值）
                'carbon_diff': carbon_diff,
                'production': production,
            }

            logger.info(f'  LCOE 2026: {lcoe_now:.2f} CNY/kg')
            logger.info(f'  LCOE 2036: {lcoe_2036:.2f} CNY/kg  (降幅 {(lcoe_2036/lcoe_now - 1)*100:+.1f}%)')
            logger.info(f'  碳强度差值: {carbon_diff:.2f} g CO2eq/MJ')

        logger.info(f'\n成功加载 {len(self.data)} 个场景')
        self.pareto_optimal_names = self._identify_pareto_optimal(self.data)
        logger.info('帕累托最优场景: %s', ', '.join(self.pareto_optimal_names))

    # ── 帕累托识别 ────────────────────────────────────────────────────────────

    @staticmethod
    def _identify_pareto_optimal(data: Dict[str, dict]) -> List[str]:
        """基于当前LCOE（箱体顶边）识别帕累托最优解。"""
        sorted_items = sorted(
            data.items(),
            key=lambda item: (item[1]['carbon_diff'], item[1]['lcoe'])
        )
        pareto_names: List[str] = []
        best_cost = float('inf')
        for _, scenario in sorted_items:
            cost = float(scenario['lcoe'])
            if cost < best_cost - 1e-9:
                pareto_names.append(scenario['name_en'])
                best_cost = cost
        return pareto_names

    # ── 帕累托连线（连接箱体顶边中心点） ─────────────────────────────────────

    @staticmethod
    def _draw_pareto_region(ax, pareto_points: List[dict],
                            color: str, linewidth: float, zorder: int,
                            dot_size: float = 60,
                            fill_alpha: float = 0.18):
        """
        将帕累托最优箱体的"顶边中心连线"与"底边中心连线"围成一个带状区域：

          顶线（实线）：各箱体 2026 年 LCOE 顶边中心相连 → 当前帕累托前沿
          底线（虚线）：各箱体 2036 年投影 LCOE 底边中心相连 → 2036 年预期前沿
          填充区域：两条线之间，表示学习曲线带来的降本空间
        """
        # 按碳强度从小到大排序
        pts = sorted(pareto_points, key=lambda p: float(p['carbon_diff']))
        if len(pts) < 2:
            return

        tops    = [(float(p['carbon_diff']), float(p['lcoe']))          for p in pts]
        bottoms = [(float(p['carbon_diff']), float(p['lcoe_proj'][-1])) for p in pts]

        top_x = [t[0] for t in tops]
        top_y = [t[1] for t in tops]
        bot_x = [b[0] for b in bottoms]
        bot_y = [b[1] for b in bottoms]

        # ── 填充带状区域（顶线左→右，底线右→左，围成多边形）──────────────
        poly_x = top_x + list(reversed(bot_x))
        poly_y = top_y + list(reversed(bot_y))
        ax.fill(poly_x, poly_y,
                facecolor=color, edgecolor='none',
                alpha=fill_alpha, zorder=zorder)

        # ── 顶线（虚线，2026年帕累托前沿）────────────────────────────────
        ax.plot(top_x, top_y, color=color, lw=linewidth,
                linestyle='--', dashes=(6, 3), solid_capstyle='round',
                zorder=zorder + 2)

        # ── 底线（虚线，2036年投影前沿）──────────────────────────────────
        ax.plot(bot_x, bot_y, color=color, lw=linewidth * 0.85,
                linestyle='--', dashes=(3, 3), solid_capstyle='round',
                alpha=0.80, zorder=zorder + 2)

        # ── 顶边圆点（当前2026基准节点）──────────────────────────────────
        if dot_size > 0:
            ax.scatter(top_x, top_y,
                       s=dot_size, color=color,
                       edgecolors='white', linewidths=1.3,
                       zorder=zorder + 3)
            # 底边较小圆点（2036投影节点）
            ax.scatter(bot_x, bot_y,
                       s=dot_size * 0.45, color=color,
                       edgecolors='white', linewidths=1.0,
                       alpha=0.80, zorder=zorder + 3)

    # ── 颜色工具 ──────────────────────────────────────────────────────────────

    @staticmethod
    def _darken(hex_color: str, factor: float = 0.55) -> str:
        """将十六进制颜色按比例加深。"""
        r = max(0, min(255, int(int(hex_color[1:3], 16) * factor)))
        g = max(0, min(255, int(int(hex_color[3:5], 16) * factor)))
        b = max(0, min(255, int(int(hex_color[5:7], 16) * factor)))
        return f'#{r:02x}{g:02x}{b:02x}'

    @staticmethod
    def _hex_to_rgb01(hex_color: str):
        return (int(hex_color[1:3], 16) / 255,
                int(hex_color[3:5], 16) / 255,
                int(hex_color[5:7], 16) / 255)

    # ── 箱体绘制（含渐变填充 + 年份刻度线） ──────────────────────────────────

    def _draw_box(self, ax, x_center: float, lcoe_proj: np.ndarray,
                  x_hw: float, color: str, zorder: int = 5,
                  show_year_labels: bool = False):
        """
        绘制带渐变填充和逐年刻度的箱体。

        lcoe_proj : shape (11,) 数组，index 0 = 2026，index 10 = 2036。
        color     : 场景基色（深色对应2026年顶部）。
        show_year_labels : 若为True，在箱体右侧标注年份刻度（用于最高箱体）。
        """
        y_top = float(lcoe_proj[0])   # 2026
        y_bot = float(lcoe_proj[-1])  # 2036
        height = y_top - y_bot

        # ── 渐变填充（用多个细长矩形叠加模拟渐变）──────────────────────────
        n_steps = 60
        r, g, b = self._hex_to_rgb01(color)
        # 浅色（2036端）= 混入白色，RGB各加 (1-c)*0.55
        r2 = min(1.0, r + (1 - r) * 0.60)
        g2 = min(1.0, g + (1 - g) * 0.60)
        b2 = min(1.0, b + (1 - b) * 0.60)
        step_h = height / n_steps
        for i in range(n_steps):
            t = i / (n_steps - 1)            # 0 = 顶（深），1 = 底（浅）
            rc = r * (1 - t) + r2 * t
            gc = g * (1 - t) + g2 * t
            bc = b * (1 - t) + b2 * t
            strip = mpatches.Rectangle(
                (x_center - x_hw, y_top - (i + 1) * step_h),
                2 * x_hw, step_h,
                facecolor=(rc, gc, bc), edgecolor='none',
                alpha=0.85, zorder=zorder,
            )
            ax.add_patch(strip)

        # ── 逐年刻度线（只在箱体高度足够时绘制）─────────────────────────────
        MIN_HEIGHT_FOR_MARKS = 1.5   # CNY/kg，低于此高度不画刻度（避免重叠）
        if height >= MIN_HEIGHT_FOR_MARKS:
            for idx, year in enumerate(PROJ_YEARS[1:-1], start=1):  # 2027–2035
                y_yr = float(lcoe_proj[idx])
                is_2030 = (year == 2030)
                ax.plot(
                    [x_center - x_hw, x_center + x_hw],
                    [y_yr, y_yr],
                    color='#444444' if is_2030 else '#888888',
                    lw=1.1 if is_2030 else 0.5,
                    alpha=0.75 if is_2030 else 0.40,
                    linestyle='--' if is_2030 else '-',
                    zorder=zorder + 2,
                    solid_capstyle='butt',
                )

        # ── 年份标注（仅最高箱体）──────────────────────────────────────────
        if show_year_labels and height >= MIN_HEIGHT_FOR_MARKS:
            label_years = [2026, 2028, 2030, 2032, 2034, 2036]
            label_idx   = [0, 2, 4, 6, 8, 10]
            for li, yi in zip(label_years, label_idx):
                y_yr = float(lcoe_proj[yi])
                is_2030 = (li == 2030)
                ax.text(
                    x_center + x_hw * 1.25, y_yr,
                    str(li),
                    fontsize=20,
                    color='#222222' if is_2030 else '#555555',
                    fontweight='bold' if is_2030 else 'normal',
                    va='center', ha='left', zorder=zorder + 5,
                )

    @staticmethod
    def _draw_pareto_box_highlight(ax, x_center: float, y_top: float,
                                   y_bottom: float, x_hw: float, zorder: int = 8):
        """在帕累托最优箱体上叠加橙色外边框高亮。"""
        pad_x = x_hw * 0.30
        pad_y = (y_top - y_bottom) * 0.04 if y_top > y_bottom else 0.15
        for col, lw in [('white', 4.5), ('#D97706', 2.0)]:
            r = mpatches.Rectangle(
                (x_center - x_hw - pad_x, y_bottom - pad_y),
                2 * (x_hw + pad_x),
                (y_top - y_bottom) + 2 * pad_y,
                facecolor='none', edgecolor=col,
                linewidth=lw, zorder=zorder if col == 'white' else zorder + 1,
            )
            ax.add_patch(r)

    # ── 主绘图方法（断裂X轴版）────────────────────────────────────────────────

    # 断裂X轴分割点：左侧主区（−250~150）和右侧高碳区（200~800），宽度比例 7:3
    X_BREAK_LEFT  = 150    # 左侧区间上界（数据坐标）
    X_BREAK_RIGHT = 200    # 右侧区间下界（数据坐标）
    AXIS_RATIO    = (0.70, 0.30)  # 左:右宽度比例

    def _setup_broken_axes(self, fig):
        """
        创建断裂X轴：左侧 gs_l（主要场景区），右侧 gs_r（高碳场景区）。
        返回 (ax_l, ax_r)。
        """
        left_w, right_w = self.AXIS_RATIO
        gap = 0.012   # 两子图间隔（保留断裂视觉）
        L, R, T, B = 0.09, 0.93, 0.91, 0.10

        ax_l = fig.add_axes([L, B, (R - L) * left_w - gap / 2, T - B])
        ax_r = fig.add_axes([L + (R - L) * left_w + gap / 2, B,
                             (R - L) * right_w - gap / 2, T - B])
        return ax_l, ax_r

    @staticmethod
    def _draw_break_marks(fig, ax_l, ax_r):
        """在断裂边绘制斜线标记——使用 figure 级别 artist，始终渲染在最顶层。"""
        from matplotlib.lines import Line2D as FigLine
        pos_l = ax_l.get_position()
        pos_r = ax_r.get_position()
        d_x = pos_l.width  * 0.018
        d_y = pos_l.height * 0.018
        for x_edge in [pos_l.x1, pos_r.x0]:
            for y_edge in [pos_l.y0, pos_l.y1]:
                fig.add_artist(FigLine(
                    [x_edge - d_x, x_edge + d_x],
                    [y_edge - d_y, y_edge + d_y],
                    transform=fig.transFigure,
                    color='#666666', lw=1.5, clip_on=False,
                ))

    def _apply_shared_background(self, ax, x_min, x_max, y_min, y_max):
        """在给定axes上绘制象限背景色块和参考线。"""
        ct  = self.carbon_threshold
        mpl = self.market_price_low
        mpu = self.cost_threshold

        ax.fill_between([x_min, ct],   y_min, mpl,   color='#F1F8E9', alpha=0.6, zorder=0)
        ax.fill_between([x_min, ct],   mpu,   y_max,  color='#FFFFFF', alpha=1.0, zorder=0)
        ax.fill_between([ct,    x_max], y_min, mpl,   color='#FFF3E0', alpha=0.6, zorder=0)
        ax.fill_between([ct,    x_max], mpu,   y_max,  color='#F2F2F2', alpha=0.6, zorder=0)
        ax.fill_between([x_min, x_max], mpl,   mpu,   color='#FFF8E1', alpha=0.55, zorder=0)

        ax.axvline(x=ct,  color='#999999', linestyle='--', lw=1.5, zorder=1)
        ax.axhline(y=mpl, color='#999999', linestyle='--', lw=1.2, zorder=1)
        ax.axhline(y=mpu, color='#999999', linestyle='--', lw=1.5, zorder=1)

    def plot_quadrant_chart(self):
        """绘制箱式象限图（断裂X轴版，含逐年刻度线和渐变填充）。"""
        logger.info('\n生成箱式象限图（断裂X轴版）...')

        # ── 数据整理 ────────────────────────────────────────────────────────
        x_values   = [d['carbon_diff']  for d in self.data.values()]
        y_top_vals = [d['lcoe']          for d in self.data.values()]
        y_bot_vals = [d['lcoe_2036']     for d in self.data.values()]

        y_margin = 4
        y_min = max(0, min(y_bot_vals) - y_margin)
        y_max = max(y_top_vals) + y_margin

        # 左轴范围：包含所有 carbon_diff <= X_BREAK_LEFT 的场景，加适量margin
        left_vals  = [x for x in x_values if x <= self.X_BREAK_LEFT]
        right_vals = [x for x in x_values if x >  self.X_BREAK_LEFT]
        xl_min = min(left_vals)  - max(10, abs(min(left_vals)) * 0.12)
        xl_max = self.X_BREAK_LEFT
        xr_min = self.X_BREAK_RIGHT
        xr_max = max(right_vals) + max(20, abs(max(right_vals)) * 0.08)

        # 箱体宽度：左右轴分别按各自范围的约2%计算
        hw_l = (xl_max - xl_min) * self.BOX_X_FRACTION_L
        hw_r = (xr_max - xr_min) * self.BOX_X_FRACTION_R

        # 最高箱体（用于年份标注）
        tallest_name = max(self.data, key=lambda k: self.data[k]['lcoe'])

        # ── 创建图形 + 断裂子图 ──────────────────────────────────────────────
        fig = plt.figure(figsize=(16, 11))
        ax_l, ax_r = self._setup_broken_axes(fig)

        # ── 断裂缝隙处补充背景填充（保持象限色连续）─────────────────────────
        _gap = 0.012
        _L, _R, _T, _B = 0.09, 0.93, 0.91, 0.10
        _left_w = self.AXIS_RATIO[0]
        _gap_x = _L + (_R - _L) * _left_w - _gap / 2
        ax_gap = fig.add_axes([_gap_x, _B, _gap, _T - _B])
        ax_gap.set_xlim(0, 1)
        ax_gap.set_ylim(y_min, y_max)
        ax_gap.axis('off')
        ax_gap.set_zorder(0)
        # 缝隙处 x 均在 ct=0 右侧（Higher emission 区域）
        ax_gap.fill_between([0, 1], y_min, self.market_price_low,
                            color='#FFF3E0', alpha=0.6)
        ax_gap.fill_between([0, 1], self.cost_threshold, y_max,
                            color='#F2F2F2', alpha=0.6)
        ax_gap.fill_between([0, 1], self.market_price_low, self.cost_threshold,
                            color='#FFF8E1', alpha=0.55)

        for ax, x_min, x_max in [(ax_l, xl_min, xl_max), (ax_r, xr_min, xr_max)]:
            self._apply_shared_background(ax, x_min, x_max, y_min, y_max)
            ax.set_xlim(x_min, x_max)
            ax.set_ylim(y_min, y_max)
            ax.yaxis.set_major_locator(MultipleLocator(10))
            ax.grid(True, linestyle='--', alpha=0.40, color='#aaaaaa', dashes=(4, 4))
            # Y轴刻度加入市场价格边界
            y_ticks = sorted(
                {round(float(t), 6) for t in ax.get_yticks() if y_min <= t <= y_max}
                | {float(self.market_price_low), float(self.cost_threshold)}
            )
            ax.set_yticks(y_ticks)
            ax.tick_params(axis='both', which='major', labelsize=26)
            for spine in ax.spines.values():
                spine.set_visible(True)
                spine.set_linewidth(1.2)
                spine.set_color('#666666')

        # 右轴隐藏Y轴刻度标签（共享Y轴）
        ax_r.tick_params(labelleft=False)
        ax_r.spines['left'].set_visible(False)
        ax_l.spines['right'].set_visible(False)

        # 断轴斜线标记（figure 级别，始终在最顶层）
        self._draw_break_marks(fig, ax_l, ax_r)

        # ── 绘制所有场景箱体 ──────────────────────────────────────────────
        texts_l, texts_r = [], []
        for module_name, d in self.data.items():
            x      = d['carbon_diff']
            proj   = d['lcoe_proj']
            color  = d['color']
            is_left = (x <= self.X_BREAK_LEFT)
            ax_cur  = ax_l if is_left else ax_r
            hw_cur  = hw_l if is_left else hw_r
            texts_list = texts_l if is_left else texts_r

            is_tallest     = (module_name == tallest_name)
            self._draw_box(ax_cur, x, proj, hw_cur, color,
                           zorder=5, show_year_labels=is_tallest)

            # CCU-BH-FT 和 DAC-GH-MTJ 标签放在箱体底部，避免遮挡
            LABEL_BELOW = {'CCU-BH-FT'}
            LABEL_ABOVE = {'DAC-GH-MTJ'}
            LABEL_LEFT  = {'DAC-BH-MTJ'}
            if d['name_en'] in LABEL_BELOW:
                t = ax_cur.text(
                    x + hw_cur * 1.4, float(proj[-1]),
                    d['name_en'],
                    fontsize=20, color='#333333', va='top', ha='left', zorder=12,
                )
            elif d['name_en'] in LABEL_ABOVE:
                t = ax_cur.text(
                    x + hw_cur * 1.4, float(proj[0]) + 1.0,
                    d['name_en'],
                    fontsize=20, color='#333333', va='bottom', ha='left', zorder=12,
                )
            elif d['name_en'] in LABEL_LEFT:
                t = ax_cur.text(
                    x - hw_cur * 1.4, float(proj[0]),
                    d['name_en'],
                    fontsize=20, color='#333333', va='center', ha='right', zorder=12,
                )
            else:
                t = ax_cur.text(
                    x + hw_cur * 1.4, float(proj[0]),
                    d['name_en'],
                    fontsize=20, color='#333333', va='center', ha='left', zorder=12,
                )
            texts_list.append(t)

        # ── 帕累托最优箱体（仅用于后续连线，不绘制高亮外框） ────────────────
        pareto_points = sorted(
            [d for d in self.data.values() if d['name_en'] in self.pareto_optimal_names],
            key=lambda item: item['carbon_diff'],
        )

        # ── 帕累托前沿连线（只在左轴绘制，右轴一般无帕累托点） ────────────
        pareto_left = [d for d in pareto_points if d['carbon_diff'] <= self.X_BREAK_LEFT]
        if len(pareto_left) >= 2:
            self._draw_pareto_region(ax_l, pareto_left, color='#D97706',
                                     linewidth=1.8, zorder=9, dot_size=62, fill_alpha=0.13)
        pareto_right = [d for d in pareto_points if d['carbon_diff'] > self.X_BREAK_LEFT]
        if len(pareto_right) >= 2:
            self._draw_pareto_region(ax_r, pareto_right, color='#D97706',
                                     linewidth=1.8, zorder=9, dot_size=62, fill_alpha=0.13)

        # ── 传统航煤基准星形 ──────────────────────────────────────────────

        # ── 碳减排参考竖线 ────────────────────────────────────────────────
        trad_ci = self.traditional_jet_ci_gco2e_per_mj or 89
        ref_10  = -0.10 * trad_ci
        ref_70  = -0.70 * trad_ci
        bbox_cfg = dict(facecolor='white', edgecolor='none', alpha=0.7, pad=0.2)
        ax_l.axvline(x=ref_10, color='#AAAAAA', linestyle='-.', lw=1.2, alpha=0.8, zorder=1)
        ax_l.text(ref_10 + 1, 0.90, f'{ref_10:.1f} g/MJ (−10%)', rotation=90, fontsize=20,
                  color='#555555', va='top', ha='left',
                  transform=ax_l.get_xaxis_transform(), bbox=bbox_cfg)
        ax_l.axvline(x=ref_70, color='#AAAAAA', linestyle='-.', lw=1.2, alpha=0.8, zorder=1)
        ax_l.text(ref_70 - 1, 0.90, f'{ref_70:.1f} g/MJ (−70%)', rotation=90, fontsize=20,
                  color='#555555', va='top', ha='right',
                  transform=ax_l.get_xaxis_transform(), bbox=bbox_cfg)

        # ── 市场价格区间标注（左轴） ──────────────────────────────────────
        ax_l.text(0.01, self.market_price_mid, 'Market price',
                  transform=ax_l.get_yaxis_transform(),
                  fontsize=20, color='#666666', va='center', ha='left')
        ax_l.text(self.carbon_threshold + 2, y_min + 0.5,
                  f'Baseline: {self.carbon_threshold} g CO2eq/MJ',
                  fontsize=20, color='#555555', va='bottom')

        # ── 象限标注 ──────────────────────────────────────────────────────
        ax_l.text((xl_min + self.carbon_threshold) / 2, y_max + 0.3,
                  'Lower emission', fontsize=26, ha='center', va='bottom',
                  fontweight='bold', color='#555555')
        ax_l.text((self.carbon_threshold + xl_max) / 2, y_max + 0.3,
                  'Higher emission', fontsize=26, ha='center', va='bottom',
                  fontweight='bold', color='#555555')

        # ── 自动调整标签（左轴） ──────────────────────────────────────────
        if adjust_text and texts_l:
            scatter_x = [d['carbon_diff'] for d in self.data.values()
                         if d['carbon_diff'] <= self.X_BREAK_LEFT]
            scatter_y = [d['lcoe']         for d in self.data.values()
                         if d['carbon_diff'] <= self.X_BREAK_LEFT]
            try:
                adjust_text(texts_l, x=scatter_x, y=scatter_y, ax=ax_l,
                            arrowprops=dict(arrowstyle='-', color='#666666', lw=0.7),
                            force_text=(0.4, 0.9), force_static=(0.8, 1.2),
                            expand=(1.15, 1.3), ensure_inside_axes=True, iter_lim=800)
            except Exception as e:
                logger.warning(f'adjust_text (left) 失败: {e}')

        # ── 轴标签（只在左轴设Y轴标签，共享X轴标签放在fig底部） ──────────
        ax_l.set_ylabel('Levelized cost of SAF (CNY/kg)', fontsize=28, labelpad=12, fontweight='bold')
        # 共享X轴标签：用fig.text居中放置
        fig.text(0.51, 0.02,
                 'Carbon intensity difference vs traditional jet fuel (g CO\u2082eq/MJ)',
                 ha='center', va='bottom', fontsize=26, fontweight='bold')

        # ── X轴刻度 ───────────────────────────────────────────────────────
        ax_l.xaxis.set_major_locator(MultipleLocator(100))
        ax_r.xaxis.set_major_locator(MultipleLocator(200))

        # ── 图例（合并为一个框，放右侧子图右上角） ───────────────────────────
        LEGEND_FS = 20   # 字体大小

        # 场景分组 handles
        pathway_order = {
            'Grey':  ['CTL', 'CTL-BH'],
            'Blue':  ['DAC-BH-MTJ', 'DAC-BH-FT', 'GTL-BH', 'GTL-GH', 'GTL',
                      'CCU-BH-MTJ', 'CCU-BH-FT'],
            'Green': ['DAC-GH-MTJ', 'DAC-GH-FT', 'CCU-GH-MTJ', 'CCU-GH-FT'],
        }
        scenario_handles = []
        for group in ['Grey', 'Blue', 'Green']:
            for name in pathway_order[group]:
                for d in self.data.values():
                    if d['name_en'] == name:
                        h = Line2D([0], [0], marker='s', color='w',
                                   markerfacecolor=d['color'],
                                   markersize=LEGEND_FS, label=name, linestyle='None')
                        scenario_handles.append(h)
                        break

        # 说明 handles
        box_top  = mpatches.Patch(facecolor='#90CAF9', edgecolor='#1565C0',
                                   alpha=0.85, label='Box top: 2026 LCOE (baseline)')
        box_bot  = mpatches.Patch(facecolor='#DDEEFF', edgecolor='#1565C0',
                                   alpha=0.85, label='Box bottom: 2036 projected LCOE')
        yr_2030  = Line2D([0], [0], color='#444444', lw=1.8, linestyle='--',
                          label='2030 cost level (key target year)')
        yr_other = Line2D([0], [0], color='#888888', lw=1.0, linestyle='-',
                          label='Annual cost marks (2027–2035)')
        pareto_l = Line2D([0], [0], color='#D97706', lw=2.5, linestyle='--',
                          label='Pareto-optimal region')


        # 只保留右侧说明项，去掉场景列和分隔标题
        all_handles = [box_top, box_bot, yr_2030, yr_other, pareto_l]

        # 用 fig.transFigure 定位 + fig.add_artist 提升到 figure 最顶层
        # 这样 legend 不受任何 axes（包括 ax_gap）遮挡
        leg = ax_r.legend(
            handles=all_handles,
            loc='upper right',
            bbox_to_anchor=(0.921, 0.875),
            bbox_transform=fig.transFigure,
            fontsize=LEGEND_FS,
            framealpha=0.95, edgecolor='#aaaaaa', facecolor='white',
            ncol=1,
            handletextpad=0.6, labelspacing=0.45,
        )
        # 提升为 figure 级别，始终在最顶层
        leg.remove()
        fig.add_artist(leg)

        # ── 保存 ──────────────────────────────────────────────────────────
        out_path    = self.session_dir / 'quadrant_chart_box.png'
        latest_path = self.output_dir  / 'quadrant_chart_box_latest.png'
        for p in [out_path, latest_path]:
            fig.savefig(p, dpi=300, bbox_inches='tight', facecolor='white')
        logger.info(f'保存图片: {out_path}')
        plt.close(fig)
        return out_path

    # ── 汇总表 ────────────────────────────────────────────────────────────────

    def generate_summary(self):
        """输出各场景数据汇总。"""
        category_labels = {
            'Grey':  'Grey (Coal-based)',
            'Blue':  'Blue (BH/NG)',
            'Green': 'Green (GH)',
        }
        rows = []
        for _, d in self.data.items():
            is_green    = d['carbon_diff'] < self.carbon_threshold
            is_economic = d['lcoe'] < self.cost_threshold
            if is_green and is_economic:
                quadrant = 'I-Green&Economic'
            elif not is_green and is_economic:
                quadrant = 'II-Economic'
            elif is_green and not is_economic:
                quadrant = 'III-Green'
            else:
                quadrant = 'IV-Neither'

            lcoe_2036 = d['lcoe_proj'][-1]
            pct_drop = (lcoe_2036 / d['lcoe'] - 1) * 100
            rows.append({
                'Scenario':              d['name_en'],
                'Category':              category_labels.get(d['category'], d['category']),
                'LCOE 2026 (CNY/kg)':    f"{d['lcoe']:.2f}",
                'LCOE 2030 (CNY/kg)':    f"{d['lcoe_proj'][4]:.2f}",
                'LCOE 2036 (CNY/kg)':    f"{lcoe_2036:.2f}",
                'Cost drop 2026→2036':   f"{pct_drop:+.1f}%",
                'Carbon Diff (g/MJ)':    f"{d['carbon_diff']:.2f}",
                'Quadrant':              quadrant,
                'Pareto Optimal':        'Yes' if d['name_en'] in self.pareto_optimal_names else 'No',
            })
        df = pd.DataFrame(rows)
        csv_path = self.session_dir / 'quadrant_box_summary.csv'
        df.to_csv(csv_path, index=False, encoding='utf-8-sig')
        logger.info(f'保存汇总: {csv_path}')
        print(df.to_string(index=False))
        return df

    # ── 入口 ──────────────────────────────────────────────────────────────────

    def run(self):
        logger.info('=' * 60)
        logger.info('SAF场景象限图可视化（箱式区间版）')
        logger.info('=' * 60)

        self.load_data()
        if len(self.data) < 2:
            logger.error(f'数据不足：只找到 {len(self.data)} 个场景')
            return None

        chart_path = self.plot_quadrant_chart()
        self.generate_summary()

        logger.info('\n' + '=' * 60)
        logger.info(f'完成！输出目录: {self.session_dir}')
        logger.info('=' * 60)
        return chart_path


def main():
    visualizer = QuadrantBoxVisualizer(
        cost_threshold=8.0,
        market_price_low=6.0,
        carbon_threshold=0.0,
    )
    visualizer.run()


if __name__ == '__main__':
    main()
