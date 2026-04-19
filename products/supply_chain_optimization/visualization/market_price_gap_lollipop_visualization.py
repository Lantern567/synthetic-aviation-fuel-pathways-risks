"""
Lollipop chart for cost gap versus market price range across 13 SAF pathways.
范围棒糖：空心圆=2026，实心圆=2036，棒身跨越技术进步区间。
"""

import glob
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
from matplotlib.ticker import MultipleLocator
from matplotlib.lines import Line2D


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# ── Wright's Law 学习曲线（与 quadrant_chart_box_visualization 保持一致） ──────

PROJ_YEARS = np.arange(2026, 2037)   # 2026–2036，共11步

_X_pem  = np.interp(PROJ_YEARS, [2025, 2027, 2030, 2033, 2036], [60,  100, 330, 600, 950])
_X_dac  = np.interp(PROJ_YEARS, [2025, 2028, 2031, 2034, 2036], [0.1, 1.0, 4.0, 8.0, 12.0])
_X_coal = np.interp(PROJ_YEARS, [2025, 2028, 2031, 2034, 2036], [10,  60,  180, 350, 500])
_X_gas  = np.interp(PROJ_YEARS, [2025, 2028, 2031, 2034, 2036], [20,  90,  250, 430, 600])

LR = {
    'electrolyzer':  0.18,
    'synthesis_mtj': 0.10,
    'synthesis_ft':  0.12,
    'capture_dac':   0.15,
    'capture_coal':  0.08,
    'capture_ref':   0.08,
    'electricity':   0.05,
}


def _b(lr: float) -> float:
    return -np.log2(1 - lr)


def _cf_array(X: np.ndarray, lr: float) -> np.ndarray:
    return (X / X[0]) ** (-_b(lr))


CF_ARRAY = {
    'electrolyzer':  _cf_array(_X_pem,  LR['electrolyzer']),
    'synthesis_mtj': _cf_array(_X_gas,  LR['synthesis_mtj']),
    'synthesis_ft':  _cf_array(_X_gas,  LR['synthesis_ft']),
    'capture_dac':   _cf_array(_X_dac,  LR['capture_dac']),
    'capture_coal':  _cf_array(_X_coal, LR['capture_coal']),
    'capture_ref':   _cf_array(_X_gas,  LR['capture_ref']),
    'electricity':   (1 - LR['electricity']) ** np.arange(len(PROJ_YEARS)),
    'fixed':         np.ones(len(PROJ_YEARS)),
}

EXCLUDE_KEYS = {'shortage_penalty_cost', 'total_cost', 'total_cost_excluding_shortage'}

COST_MAP = {
    'electrolyzer_investment_cost':    'electrolyzer',
    'hydrogen_production_cost':        'electrolyzer',
    'methanol_production_cost':        'synthesis_mtj',
    'production_cost':                 'synthesis_mtj',
    'ft_production_cost':              'synthesis_ft',
    'ft_reactor_operation_cost':       'synthesis_ft',
    'ft_energy_cost':                  'synthesis_ft',
    'catalyst_cost':                   'synthesis_ft',
    'ft_catalyst_cost':                'synthesis_ft',
    'ft_reactor_investment_cost':      'synthesis_ft',
    'coal_gasification_cost':          'capture_coal',
    'dac_capture_cost':                'capture_dac',
    'dac_facility_investment':         'capture_dac',
    'co2_capture_cost':                'capture_ref',
    'electricity_cost':                'electricity',
    'dac_grid_electricity_cost':       'electricity',
}

FT_SCENARIOS = {
    'CTL', 'DAC-GH-FT', 'CCU-GH-FT', 'GTL',
    'DAC-BH-FT', 'CCU-BH-FT', 'GTL-BH', 'GTL-GH',
}


def compute_lcoe_projection(solution_data: dict, name_en: str) -> np.ndarray:
    """返回 shape=(11,) LCOE 数组，index 0=2026，index 10=2036。"""
    lcoe_base = float(solution_data.get(
        'lifecycle_levelized_cost_excluding_shortage_per_kg', 0))
    total = float(solution_data.get('objective_value_lifecycle_total', 0))
    if total == 0 or lcoe_base == 0:
        return np.full(len(PROJ_YEARS), lcoe_base)

    cb_raw = solution_data.get('cost_breakdown', {})
    cb = {k: v for k, v in cb_raw.items() if k not in EXCLUDE_KEYS and v != 0}

    cats = {k: 0.0 for k in [
        'electrolyzer', 'synthesis_mtj', 'synthesis_ft',
        'capture_dac', 'capture_coal', 'capture_ref', 'electricity', 'fixed'
    ]}
    for key, val in cb.items():
        mapped = COST_MAP.get(key, 'fixed')
        cats[mapped] += float(val)

    # 合并 synthesis 子类
    syn_key = 'synthesis_ft' if name_en in FT_SCENARIOS else 'synthesis_mtj'
    cats['synthesis'] = cats.pop('synthesis_ft') + cats.pop('synthesis_mtj')

    total_mapped = sum(cats.values())
    if total_mapped == 0:
        return np.full(len(PROJ_YEARS), lcoe_base)

    fracs = {k: v / total_mapped for k, v in cats.items()}
    cf_syn = CF_ARRAY['synthesis_ft'] if name_en in FT_SCENARIOS else CF_ARRAY['synthesis_mtj']

    proj = (
        fracs['electrolyzer']  * CF_ARRAY['electrolyzer']  +
        fracs['synthesis']     * cf_syn                    +
        fracs['capture_dac']   * CF_ARRAY['capture_dac']   +
        fracs['capture_coal']  * CF_ARRAY['capture_coal']  +
        fracs['capture_ref']   * CF_ARRAY['capture_ref']   +
        fracs['electricity']   * CF_ARRAY['electricity']   +
        fracs['fixed']         * CF_ARRAY['fixed']
    ) * lcoe_base

    return proj


# ── 主可视化类 ──────────────────────────────────────────────────────────────────

class MarketPriceGapLollipopVisualizer:
    """范围棒糖图：空心圆=2026基准，实心圆=2036技术进步后。"""

    def __init__(
        self,
        market_price_low_cny_per_kg: float = 6.0,
        market_price_high_cny_per_kg: float = 8.0,
    ):
        self.market_price_low_cny_per_kg  = market_price_low_cny_per_kg
        self.market_price_high_cny_per_kg = market_price_high_cny_per_kg
        self.market_price_band_gap = (
            self.market_price_low_cny_per_kg - self.market_price_high_cny_per_kg
        )

        base_dir = Path(__file__).parent
        self.output_dir = base_dir / "results"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = self.output_dir / f"market_price_gap_lollipop_{timestamp}"
        self.session_dir.mkdir(parents=True, exist_ok=True)

        logger.info("输出目录: %s", self.session_dir)

        self.project_root = Path(__file__).parent.parent.parent.parent

        self.modules: Dict[str, Dict] = {
            "Coal Hydrogen": {
                "name_en": "CTL", "category": "Grey", "color": "#616161",
                "solution_pattern": str(self.project_root / "products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/complete_solution_*.json"),
            },
            "Byproduct H2 + Coal": {
                "name_en": "CTL-BH", "category": "Grey", "color": "#9E9E9E",
                "solution_pattern": str(self.project_root / "products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/byproduct_hydrogen/complete_solution_*.json"),
            },
            "DAC Two-Step": {
                "name_en": "DAC-GH-MTJ", "category": "Green", "color": "#2E7D32",
                "solution_pattern": str(self.project_root / "products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/two_step/complete_solution_*.json"),
            },
            "DAC One-Step": {
                "name_en": "DAC-GH-FT", "category": "Green", "color": "#43A047",
                "solution_pattern": str(self.project_root / "products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/one_step/complete_solution_*.json"),
            },
            "Green H2 Two-Step": {
                "name_en": "CCU-GH-MTJ", "category": "Green", "color": "#66BB6A",
                "solution_pattern": str(self.project_root / "products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/two_step/complete_solution_*.json"),
            },
            "Green H2 One-Step": {
                "name_en": "CCU-GH-FT", "category": "Green", "color": "#81C784",
                "solution_pattern": str(self.project_root / "products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/one_step/complete_solution_*.json"),
            },
            "Natural Gas Two-Step": {
                "name_en": "GTL-GH", "category": "Blue", "color": "#1565C0",
                "solution_pattern": str(self.project_root / "products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/complete_solution_*.json"),
            },
            "Natural Gas One-Step": {
                "name_en": "GTL", "category": "Blue", "color": "#1E88E5",
                "solution_pattern": str(self.project_root / "products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/ft_one_step/complete_solution_*.json"),
            },
            "Byproduct H2 + DAC Two-Step": {
                "name_en": "DAC-BH-MTJ", "category": "Blue", "color": "#42A5F5",
                "solution_pattern": str(self.project_root / "products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/two_step/complete_solution_*.json"),
            },
            "Byproduct H2 + DAC One-Step": {
                "name_en": "DAC-BH-FT", "category": "Blue", "color": "#64B5F6",
                "solution_pattern": str(self.project_root / "products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/one_step/complete_solution_*.json"),
            },
            "Byproduct H2 + NG Two-Step": {
                "name_en": "GTL-BH", "category": "Blue", "color": "#90CAF9",
                "solution_pattern": str(self.project_root / "products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/byproduct_hydrogen/byproduct_hydrogen/two_step/complete_solution_*.json"),
            },
            "Byproduct H2 Two-Step": {
                "name_en": "CCU-BH-MTJ", "category": "Blue", "color": "#BBDEFB",
                "solution_pattern": str(self.project_root / "products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/two_step/complete_solution_*.json"),
            },
            "Byproduct H2 One-Step": {
                "name_en": "CCU-BH-FT", "category": "Blue", "color": "#E3F2FD",
                "solution_pattern": str(self.project_root / "products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/one_step/complete_solution_*.json"),
            },
        }

    @staticmethod
    def _load_latest_json(pattern: str) -> Optional[dict]:
        files = sorted(glob.glob(pattern), reverse=True)
        if not files:
            return None
        with open(files[0], "r", encoding="utf-8") as f:
            return json.load(f)

    def build_gap_table(self) -> pd.DataFrame:
        rows = []
        for _, cfg in self.modules.items():
            solution = self._load_latest_json(cfg["solution_pattern"])
            if solution is None:
                logger.warning("未找到结果文件: %s", cfg["name_en"])
                continue

            lcoe_proj = compute_lcoe_projection(solution, cfg["name_en"])
            lcoe_2026 = float(lcoe_proj[0])   # index 0 = 2026
            lcoe_2036 = float(lcoe_proj[-1])  # index 10 = 2036

            gap_2026 = lcoe_2026 - self.market_price_high_cny_per_kg
            gap_2036 = lcoe_2036 - self.market_price_high_cny_per_kg

            rows.append({
                "Scenario":         cfg["name_en"],
                "Category":         cfg["category"],
                "LCOE 2026":        lcoe_2026,
                "LCOE 2036":        lcoe_2036,
                "Gap 2026":         gap_2026,
                "Gap 2036":         gap_2036,
                "Gap reduction":    gap_2026 - gap_2036,
                "Color":            cfg["color"],
            })

        df = pd.DataFrame(rows)
        if df.empty:
            return df

        # 按 2026 gap 升序排列（与原图一致）
        return df.sort_values("Gap 2026", ascending=True).reset_index(drop=True)

    def plot_lollipop_chart(self, df: pd.DataFrame) -> Path:
        if df.empty:
            raise ValueError("No data available for plotting.")

        plt.rcParams["font.family"] = ["Times New Roman", "DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False

        fig, ax = plt.subplots(figsize=(20, 20))

        x_pos   = np.arange(len(df))
        g26     = df["Gap 2026"].to_numpy()
        g36     = df["Gap 2036"].to_numpy()
        labels  = df["Scenario"].tolist()
        colors  = df["Color"].tolist()

        all_gaps = np.concatenate([g26, g36])
        min_gap  = float(np.floor((all_gaps.min() - 3.0) / 5.0) * 5.0)
        max_gap  = float(np.ceil((all_gaps.max() + 5.0)  / 5.0) * 5.0)

        # ── 背景色带 ────────────────────────────────────────────────────────
        ax.axhspan(min_gap, self.market_price_band_gap, color="#E8F3E8", alpha=0.72, zorder=0)
        ax.axhspan(self.market_price_band_gap, 0.0,     color="#FFF8E1", alpha=0.72, zorder=0)
        ax.axhspan(0.0, max_gap,                         color="#F2F2F2", alpha=0.72, zorder=0)
        ax.axhline(self.market_price_band_gap, color="#B0B0B0", linestyle="--", linewidth=1.2, zorder=1)
        ax.axhline(0.0,                        color="#999999", linestyle="--", linewidth=1.6, zorder=1)

        for idx, (gap26, gap36, color) in enumerate(zip(g26, g36, colors)):
            # ── 棒身：从 2026 gap 到 2036 gap ────────────────────────────────
            ax.vlines(x=idx, ymin=min(gap26, gap36), ymax=max(gap26, gap36),
                      color=color, linewidth=3.5, alpha=0.75, zorder=2)

            # ── 零线到 2026 的浅色参考棒 ────────────────────────────────────
            ax.vlines(x=idx, ymin=min(0.0, gap26), ymax=max(0.0, gap26),
                      color=color, linewidth=1.5, alpha=0.30, linestyle=":", zorder=2)

            # ── 空心圆 = 2026 ─────────────────────────────────────────────
            ax.scatter(idx, gap26, s=260, color="white",
                       edgecolors=color, linewidths=2.5, zorder=4)

            # ── 实心圆 = 2036 ─────────────────────────────────────────────
            ax.scatter(idx, gap36, s=260, color=color,
                       edgecolors="white", linewidths=1.6, zorder=5)

        # ── 数值标注：较大值标在上方，较小值标在下方，永不重叠 ────────────
        for idx, (gap26, gap36) in enumerate(zip(g26, g36)):
            offset = 1.4
            top_gap,  top_is_2026  = (gap26, True)  if gap26 >= gap36 else (gap36, False)
            bot_gap,  bot_is_2026  = (gap26, True)  if gap26 <  gap36 else (gap36, False)

            # 较大值 → 标在其上方
            top_label = f"{top_gap:+.1f}"
            top_fs    = 32 if top_is_2026 else 36
            top_color = "#888888" if top_is_2026 else "#333333"
            top_kw    = dict(fontstyle="italic") if top_is_2026 else dict(fontweight="bold")
            ax.text(idx, top_gap + offset, top_label,
                    va="bottom", ha="center", fontsize=top_fs, color=top_color, **top_kw)

            # 较小值 → 标在其下方
            bot_label = f"{bot_gap:+.1f}"
            bot_fs    = 32 if bot_is_2026 else 36
            bot_color = "#888888" if bot_is_2026 else "#333333"
            bot_kw    = dict(fontstyle="italic") if bot_is_2026 else dict(fontweight="bold")
            ax.text(idx, bot_gap - offset, bot_label,
                    va="top", ha="center", fontsize=bot_fs, color=bot_color, **bot_kw)

        # ── 坐标轴 ────────────────────────────────────────────────────────
        ax.set_xticks(x_pos)
        ax.set_xticklabels(labels, rotation=38, ha="right", fontsize=39)
        ax.set_xlim(-0.7, len(df) - 0.3)
        ax.set_ylim(min_gap, max_gap)
        ax.set_xlabel("SAF pathways", fontsize=44, labelpad=14, fontweight="bold")
        ax.set_ylabel("Cost gap relative to market price upper bound (CNY/kg)",
                      fontsize=46, labelpad=14, fontweight="bold")

        ax.yaxis.set_major_locator(MultipleLocator(10))
        ax.grid(True, axis="y", linestyle="--", alpha=0.45, color="#aaaaaa", dashes=(4, 4))
        ax.tick_params(axis="x", length=0)
        ax.tick_params(axis="y", labelsize=40)
        for spine in ax.spines.values():
            spine.set_linewidth(1.2)
            spine.set_color("#666666")

        # ── 区间文字标注 ──────────────────────────────────────────────────
        ax.text(0.988, (min_gap + self.market_price_band_gap) / 2.0,
                "Below market price range",
                transform=ax.get_yaxis_transform(), ha="right", va="center",
                fontsize=42, color="#4A6B4A", fontweight="bold")
        ax.text(0.012, (0.0 + max_gap) / 2.0,
                "Above market price range",
                transform=ax.get_yaxis_transform(), ha="left", va="center",
                fontsize=42, color="#666666", fontweight="bold")
        ax.text(0.988, self.market_price_band_gap / 2.0,
                f"Market price range: {self.market_price_low_cny_per_kg:.1f}"
                f"–{self.market_price_high_cny_per_kg:.1f} CNY/kg",
                transform=ax.get_yaxis_transform(), ha="right", va="center",
                fontsize=38, color="#555555")

        # ── 图例 ─────────────────────────────────────────────────────────
        legend_handles = [
            Line2D([0], [0], marker='o', color='gray', markerfacecolor='white',
                   markeredgecolor='gray', markeredgewidth=2.5,
                   markersize=14, linewidth=0, label='2026 (baseline)'),
            Line2D([0], [0], marker='o', color='gray', markerfacecolor='gray',
                   markeredgecolor='white', markeredgewidth=1.5,
                   markersize=14, linewidth=0, label='2036 (with learning)'),
            Line2D([0], [0], color='gray', linewidth=3.5, alpha=0.75,
                   label='Cost reduction range'),
        ]
        ax.legend(handles=legend_handles, fontsize=36, loc='upper left',
                  framealpha=0.85, edgecolor='#CCCCCC')

        fig.tight_layout(rect=[0.03, 0.08, 0.985, 1.0])

        output_path  = self.session_dir / "market_price_gap_lollipop.png"
        latest_path  = self.output_dir  / "market_price_gap_lollipop_latest.png"
        plt.savefig(output_path, dpi=300, bbox_inches="tight", facecolor="white")
        plt.savefig(latest_path, dpi=300, bbox_inches="tight", facecolor="white")
        plt.close(fig)

        logger.info("保存图片: %s", output_path)
        return output_path

    def save_summary(self, df: pd.DataFrame) -> Path:
        csv_path = self.session_dir / "market_price_gap_summary.csv"
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        logger.info("保存汇总表: %s", csv_path)
        return csv_path

    def run(self) -> Path:
        df = self.build_gap_table()
        if df.empty:
            raise ValueError("No pathway data loaded.")
        self.save_summary(df)
        chart_path = self.plot_lollipop_chart(df)
        logger.info("完成，可视化输出目录: %s", self.session_dir)
        return chart_path


def main() -> None:
    visualizer = MarketPriceGapLollipopVisualizer(
        market_price_low_cny_per_kg=6.0,
        market_price_high_cny_per_kg=8.0,
    )
    visualizer.run()


if __name__ == "__main__":
    main()
