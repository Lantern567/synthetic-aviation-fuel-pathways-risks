# -*- coding: utf-8 -*-
"""
按“减排路径/场景”计算边际减排成本（MAC）并绘制柱状图。

口径（与象限图一致）：
- 碳强度差值：carbon_diff = (scheme - traditional) [g CO2eq/MJ]，负值表示减排
- 减排量：abatement = -carbon_diff [g CO2eq/MJ]，正值表示减排

MAC 定义（单位一致）：
- 成本差：ΔC_MJ = (LCOE - baseline_cost_per_kg) / energy_content_mj_per_kg  [CNY/MJ]
- MAC = ΔC_MJ / abatement * 1e6                                             [CNY/tCO2e]

注意：当 abatement<=0 或接近0 时，MAC 的“减排成本”含义不成立或数值不稳定，默认不绘制在柱状图中，
但仍会写入 CSV 供你进一步分析。

作者：Claude Code
创建时间：2026-01-11
"""

import glob
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class MacBarChartVisualizer:
    def __init__(
        self,
        baseline_cost_per_kg: float = 18.0,
        energy_content_mj_per_kg: float = 43.15,
    ):
        self.baseline_cost_per_kg = baseline_cost_per_kg
        self.energy_content_mj_per_kg = energy_content_mj_per_kg

        base_dir = Path(__file__).parent
        self.output_dir = base_dir / "results"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = self.output_dir / f"mac_bar_chart_{timestamp}"
        self.session_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"输出目录: {self.session_dir}")

        self.project_root = Path(__file__).parent.parent.parent.parent

        # 与象限图保持一致的场景配置（路径/场景）
        self.modules: Dict[str, Dict[str, str]] = {
            'Coal Hydrogen': {
                'name_en': 'CTL',
                'category': 'Grey',
                'color': '#616161',
                'solution_pattern': str(self.project_root / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/complete_solution_*.json'),
                'carbon_pattern': str(self.project_root / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/carbon_emissions_detailed_*.json')
            },
            'Byproduct H2 + Coal': {
                'name_en': 'CTL-BH',
                'category': 'Grey',
                'color': '#9E9E9E',
                'solution_pattern': str(self.project_root / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/byproduct_hydrogen/complete_solution_*.json'),
                'carbon_pattern': str(self.project_root / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/byproduct_hydrogen/carbon_emissions_detailed_*.json')
            },
            'DAC Two-Step': {
                'name_en': 'DAC-GH-MTJ',
                'category': 'Green',
                'color': '#2E7D32',
                'solution_pattern': str(self.project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/two_step/complete_solution_*.json'),
                'carbon_pattern': str(self.project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/two_step/carbon_emissions_detailed_*.json')
            },
            'DAC One-Step': {
                'name_en': 'DAC-GH-FT',
                'category': 'Green',
                'color': '#43A047',
                'solution_pattern': str(self.project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/one_step/complete_solution_*.json'),
                'carbon_pattern': str(self.project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/one_step/carbon_emissions_detailed_*.json')
            },
            'Green H2 Two-Step': {
                'name_en': 'CCU-GH-MTJ',
                'category': 'Green',
                'color': '#66BB6A',
                'solution_pattern': str(self.project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/two_step/complete_solution_*.json'),
                'carbon_pattern': str(self.project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/two_step/carbon_emissions_detailed_*.json')
            },
            'Green H2 One-Step': {
                'name_en': 'CCU-GH-FT',
                'category': 'Green',
                'color': '#81C784',
                'solution_pattern': str(self.project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/one_step/complete_solution_*.json'),
                'carbon_pattern': str(self.project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/one_step/carbon_emissions_detailed_*.json')
            },
            'Natural Gas Two-Step': {
                'name_en': 'GTL-GH-MTJ',
                'category': 'Blue',
                'color': '#1565C0',
                'solution_pattern': str(self.project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/complete_solution_*.json'),
                'carbon_pattern': str(self.project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/carbon_emissions_detailed_*.json')
            },
            'Natural Gas One-Step': {
                'name_en': 'GTL-GH-FT',
                'category': 'Blue',
                'color': '#1E88E5',
                'solution_pattern': str(self.project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/ft_one_step/complete_solution_*.json'),
                'carbon_pattern': str(self.project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/ft_one_step/carbon_emissions_detailed_*.json')
            },
            'Byproduct H2 + DAC Two-Step': {
                'name_en': 'DAC-BH-MTJ',
                'category': 'Blue',
                'color': '#42A5F5',
                'solution_pattern': str(self.project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/two_step/complete_solution_*.json'),
                'carbon_pattern': str(self.project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/two_step/carbon_emissions_detailed_*.json')
            },
            'Byproduct H2 + DAC One-Step': {
                'name_en': 'DAC-BH-FT',
                'category': 'Blue',
                'color': '#64B5F6',
                'solution_pattern': str(self.project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/one_step/complete_solution_*.json'),
                'carbon_pattern': str(self.project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/one_step/carbon_emissions_detailed_*.json')
            },
            'Byproduct H2 + NG Two-Step': {
                'name_en': 'GTL-BH-MTJ',
                'category': 'Blue',
                'color': '#90CAF9',
                'solution_pattern': str(self.project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/byproduct_hydrogen/byproduct_hydrogen/two_step/complete_solution_*.json'),
                'carbon_pattern': str(self.project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/byproduct_hydrogen/byproduct_hydrogen/two_step/carbon_emissions_detailed_*.json')
            },
            'Byproduct H2 Two-Step': {
                'name_en': 'CCU-BH-MTJ',
                'category': 'Blue',
                'color': '#BBDEFB',
                'solution_pattern': str(self.project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/two_step/complete_solution_*.json'),
                'carbon_pattern': str(self.project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/two_step/carbon_emissions_detailed_*.json')
            },
            'Byproduct H2 One-Step': {
                'name_en': 'CCU-BH-FT',
                'category': 'Blue',
                'color': '#E3F2FD',
                'solution_pattern': str(self.project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/one_step/complete_solution_*.json'),
                'carbon_pattern': str(self.project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/one_step/carbon_emissions_detailed_*.json')
            },
        }

    def _load_latest_json(self, pattern: str) -> Optional[dict]:
        files = sorted(glob.glob(pattern), reverse=True)
        if not files:
            return None
        path = Path(files[0])
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def compute_mac_table(self) -> pd.DataFrame:
        rows = []
        for module_key, cfg in self.modules.items():
            solution = self._load_latest_json(cfg["solution_pattern"])
            carbon = self._load_latest_json(cfg["carbon_pattern"])
            if solution is None or carbon is None:
                logger.warning(f"跳过 {module_key}: 未找到最新结果文件")
                continue

            lcoe_cny_per_kg = float(solution.get("lifecycle_levelized_cost_excluding_shortage_per_kg", 0.0))
            production_kt = float(solution.get("lifecycle_total_production_kg", 0.0)) / 1e6

            traditional_ci = float(carbon.get("traditional_jet_ci_gco2e_per_mj", 89.0))
            carbon_diff = carbon.get("abs_diff_vs_traditional_jet_gco2e_per_mj", None)
            if carbon_diff is None:
                if "carbon_intensity_mj" in carbon:
                    carbon_diff = float(carbon.get("carbon_intensity_mj", 0.0)) - traditional_ci
                else:
                    vs_traditional = float(carbon.get("vs_traditional_jet", 0.0))
                    carbon_diff = traditional_ci * (vs_traditional / 100.0)
            else:
                carbon_diff = float(carbon_diff)

            abatement_g_per_mj = -carbon_diff
            delta_cost_cny_per_mj = (lcoe_cny_per_kg - self.baseline_cost_per_kg) / self.energy_content_mj_per_kg

            if abs(abatement_g_per_mj) < 1e-9:
                mac_cny_per_tco2e = np.nan
            else:
                # abatement is in g CO2eq/MJ, delta_cost is in CNY/MJ
                # g to tonne: 1e6 g = 1 tonne
                # MAC = (CNY/MJ) / (g/MJ) = CNY/g
                # CNY/t = CNY/g * 1e6
                mac_cny_per_tco2e = (delta_cost_cny_per_mj / abatement_g_per_mj) * 1e6

            rows.append(
                {
                    "Scenario": cfg["name_en"],
                    "Pathway": module_key,
                    "Category": cfg["category"],
                    "LCOE (CNY/kg)": lcoe_cny_per_kg,
                    "Carbon Diff (g CO2eq/MJ)": carbon_diff,
                    "Abatement (g CO2eq/MJ)": abatement_g_per_mj,
                    "Delta Cost (CNY/MJ)": delta_cost_cny_per_mj,
                    "MAC (CNY/tCO2e)": mac_cny_per_tco2e,
                    "Production (kt)": production_kt,
                    "Color": cfg["color"],
                }
            )

        df = pd.DataFrame(rows)
        if df.empty:
            return df

        # 便于阅读：默认按 MAC 从小到大排
        df = df.sort_values(by="MAC (CNY/tCO2e)", ascending=True, na_position="last").reset_index(drop=True)
        return df

    def plot_mac_bar_chart(self, df: pd.DataFrame) -> Path:
        if df.empty:
            raise ValueError("MAC 表为空：没有可绘制的数据")

        # 只绘制真实“减排”的场景（abatement>0）且 MAC 有限
        plot_df = df[(df["Abatement (g CO2eq/MJ)"] > 0) & np.isfinite(df["MAC (CNY/tCO2e)"])].copy()
        if plot_df.empty:
            raise ValueError("没有满足 abatement>0 且 MAC 有限 的场景可绘制")

        # 定义类别顺序
        categories = ["Blue", "Green"]
        category_names = {
            "Blue": "Blue\n(BH/NG)",
            "Green": "Green\n(GH)"
        }
        
        # 准备绘图数据
        grouped_data = {}
        means = []
        stds = []
        x_indices = []
        
        for i, cat in enumerate(categories):
            cat_df = plot_df[plot_df["Category"] == cat]
            if not cat_df.empty:
                values = cat_df["MAC (CNY/tCO2e)"].astype(float).values
                grouped_data[i] = {
                    "values": values,
                    "names": cat_df["Scenario"].tolist(),
                    "color": cat_df.iloc[0]["Color"] # Assume same color for category or use map
                }
                means.append(np.mean(values))
                stds.append(np.std(values, ddof=1) if len(values) > 1 else 0.0)
                x_indices.append(i)
            else:
                means.append(np.nan)
                stds.append(np.nan)
                x_indices.append(i)

        # 字体设置 (Academic Style)
        plt.rcParams["font.family"] = ["Arial", "DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False

        # 创建图形
        fig, ax = plt.subplots(figsize=(10, 8))

        # 类别颜色
        category_colors = {
            "Blue": "#90CAF9",  # Light Blue
            "Green": "#A5D6A7"  # Light Green
        }
        bar_colors = [category_colors.get(c, "#cccccc") for c in categories]

        # 1. 绘制柱状图 (Mean)
        # 宽度 0.5, 透明度高一点; 增强误差棒视觉
        error_kw = dict(ecolor='black', elinewidth=2.5, capsize=12, capthick=2.5)
        bars = ax.bar(x_indices, means, yerr=stds, align='center', alpha=0.85, 
                      color=bar_colors, edgecolor='none', width=0.5, error_kw=error_kw)

        # 2. 绘制散点 (Jitter)
        np.random.seed(42) # 固定随机种子
        scatter_x_all = []
        scatter_y_all = []
        
        for i in x_indices:
            if i in grouped_data:
                vals = grouped_data[i]["values"]
                # 生成抖动 X
                jitter = np.random.uniform(-0.12, 0.12, size=len(vals))
                x_scatter = i + jitter
                
                # 绘制点 - 黑色，不透明度略微提升，带白色边缘以区分重叠
                ax.scatter(x_scatter, vals, s=60, color='black', alpha=0.7, zorder=10, linewidth=1.0, edgecolor='white')
                
                scatter_x_all.extend(x_scatter)
                scatter_y_all.extend(vals)

        # 3. 绘制趋势线 (Green Arrow)
        # 连接均值
        valid_indices = [i for i, m in zip(x_indices, means) if np.isfinite(m)]
        valid_means = [m for m in means if np.isfinite(m)]
        
        if len(valid_indices) > 1:
            # 绘制折线
            ax.plot(valid_indices, valid_means, color='#66BB6A', linewidth=4, alpha=0.8, zorder=5)
            # 添加箭头 (末端)
            last_idx = valid_indices[-1]
            prev_idx = valid_indices[-2]
            last_mean = valid_means[-1]
            prev_mean = valid_means[-2]
            
            # 计算方向
            dx = last_idx - prev_idx
            dy = last_mean - prev_mean
            
            ax.annotate("", 
                        xy=(last_idx, last_mean), 
                        xytext=(prev_idx, prev_mean),
                        arrowprops=dict(arrowstyle="->", color='#66BB6A', lw=4, alpha=0.8))

        # 样式调整
        # X轴标签
        ax.set_xticks(x_indices)
        ax.set_xticklabels([category_names[c] for c in categories], fontsize=28, fontweight='bold')
        
        # 标题和Y轴
        ax.set_ylabel("Marginal Abatement Cost\n(CNY/tCO2e)", fontsize=28, fontweight="bold", labelpad=20)
        # ax.set_title("MAC Distribution by Pathway Category", fontsize=32, fontweight="bold", pad=25) # Optional title if needed, maybe hide for paper
        
        # 移除上方和右侧边框
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_linewidth(2.0)
        ax.spines['bottom'].set_linewidth(2.0)
        
        # 网格 - 减少刻度
        from matplotlib.ticker import MaxNLocator
        ax.yaxis.set_major_locator(MaxNLocator(nbins=5)) # Reduce ticks
        ax.yaxis.grid(True, linestyle='--', alpha=0.3, color='gray')
        ax.set_axisbelow(True)

        # 调整Y轴刻度字体
        ax.tick_params(axis='y', labelsize=28, width=2.5, length=10)
        ax.tick_params(axis='x', width=2.5, length=10)
        
        # 强制设置Y轴刻度为粗体
        plt.setp(ax.get_yticklabels(), fontweight="bold")

        # 保存
        plt.tight_layout()
        output_path = self.session_dir / "mac_category_distribution.png"
        # 透明背景
        fig.savefig(output_path, dpi=300, bbox_inches="tight", transparent=True)
        
        latest_path = self.output_dir / "mac_bar_chart_latest.png"
        fig.savefig(latest_path, dpi=300, bbox_inches="tight", transparent=True)

        plt.close(fig)
        logger.info(f"保存类别分布柱状图: {output_path}")
        return output_path

    def run(self) -> Path:
        df = self.compute_mac_table()
        if df.empty:
            raise ValueError("未找到任何可用结果，MAC 表为空")

        csv_path = self.session_dir / "mac_summary.csv"
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        logger.info(f"保存汇总CSV: {csv_path}")

        return self.plot_mac_bar_chart(df)


def main():
    viz = MacBarChartVisualizer(
        baseline_cost_per_kg=18.0,
        energy_content_mj_per_kg=43.15,
    )
    viz.run()


if __name__ == "__main__":
    main()
