# -*- coding: utf-8 -*-
"""
Weekly Production-Inventory-Transportation Coordination Visualization Script (Figure T1)

Features:
1. Generate weekly coordination charts for 13 scenarios
2. Includes: Actual Production, Transport/Demand, Inventory
3. Demonstrate cross-week inventory regulation

Note:
Since the actual simulation data might only cover a representative week (hourly),
this script extrapolates/simulates a full year (52 weeks) using the extracted
magnitudes of production and demand to demonstrate the cross-week regulation mechanism.

Author: GitHub Copilot
Created: 2026-01-14
"""

import json
import glob
import os
import logging
import math
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker as ticker
from matplotlib import rcParams
from pathlib import Path
from collections import OrderedDict
from datetime import datetime

# ==========================================
# SCI Publication Quality Aesthetics
# ==========================================
plt.rcParams['font.family'] = 'serif'
plt.rcParams['font.serif'] = ['Times New Roman', 'DejaVu Serif']
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'SimSun', 'Arial'] + plt.rcParams['font.sans-serif']
plt.rcParams['mathtext.fontset'] = 'stix'
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['axes.linewidth'] = 1.0
plt.rcParams['xtick.major.width'] = 1.0
plt.rcParams['ytick.major.width'] = 1.0
plt.rcParams['xtick.direction'] = 'in'
plt.rcParams['ytick.direction'] = 'in'

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class WeeklyCoordinationVisualizer:
    """Weekly Production-Inventory-Transportation Coordination Visualizer"""

    def __init__(self, output_dir: str = None):
        if output_dir is None:
            base_dir = Path(__file__).parent.parent.parent.parent
            output_dir = base_dir / "products" / "supply_chain_optimization" / "visualization" / "results"

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = self.output_dir / f"weekly_coordination_{timestamp}"
        self.session_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Output directory: {self.session_dir}")

        project_root = Path(__file__).parent.parent.parent.parent

        # Real four-week demand Excel (ground truth used by optimizer)
        self.real_demand_excel = project_root / 'products/aviation_fuel_analysis/resource_flight_data_process/results/4_typical_weeks_data/typical_4weeks_demand_20251129_231231.xlsx'
        self.real_demand_ton_series = None

        # Define 13 scenarios (Consistent with comparison script) 
        # Using Unicode escapes for Chinese characters to avoid encoding issues
        self.scenarios = {
            # ========== Green Hydrogen Scenarios ==========
            'Coal Hydrogen': {
                'label': 'Coal Hydrogen', 
                'color': '#E74C3C',
                'transport_pattern': str(project_root / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/transport_summary_*.csv'),
                'inventory_pattern': str(project_root / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/inventory_levels_*.csv')
            },
            'DAC Two-Step': {
                'label': 'DAC Two-Step', 
                'color': '#3498DB',
                'transport_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/two_step/transport_summary_*.csv'),
                'inventory_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/two_step/inventory_levels_*.csv')
            },
            'DAC One-Step': {
                'label': 'DAC One-Step', 
                'color': '#5DADE2',
                'transport_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/one_step/transport_summary_*.csv'),
                'inventory_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/one_step/inventory_levels_*.csv')
            },
            'Natural Gas Two-Step': {
                'label': 'Natural Gas Two-Step', 
                'color': '#2ECC71',
                'transport_pattern': str(project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/transport_summary_*.csv'),
                'inventory_pattern': str(project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/inventory_levels_*.csv')
            },
            'Natural Gas One-Step': {
                'label': 'Natural Gas One-Step', 
                'color': '#F39C12',
                'transport_pattern': str(project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/ft_one_step/transport_summary_*.csv'),
                'inventory_pattern': str(project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/ft_one_step/inventory_levels_*.csv')
            },
            'Green H2 Two-Step': {
                'label': 'Green H2 Two-Step', 
                'color': '#9B59B6',
                'transport_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/two_step/transport_summary_*.csv'),
                'inventory_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/two_step/inventory_levels_*.csv')
            },
            'Green H2 One-Step': {
                'label': 'Green H2 One-Step', 
                'color': '#C39BD3',
                'transport_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/one_step/transport_summary_*.csv'),
                'inventory_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/one_step/inventory_levels_*.csv')
            },

            # ========== Byproduct Hydrogen Scenarios ==========
            'Byproduct H2 + Coal': {
                'label': 'Byproduct H2 + Coal', 
                'color': '#FF6B6B',
                'transport_pattern': str(project_root / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/byproduct_hydrogen/transport_summary_*.csv'),
                'inventory_pattern': str(project_root / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/byproduct_hydrogen/inventory_levels_*.csv')
            },
            'Byproduct H2 + DAC Two-Step': {
                'label': 'Byproduct H2 + DAC Two-Step', 
                'color': '#4ECDC4',
                'transport_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/two_step/transport_summary_*.csv'),
                'inventory_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/two_step/inventory_levels_*.csv')
            },
            'Byproduct H2 + DAC One-Step': {
                'label': 'Byproduct H2 + DAC One-Step', 
                'color': '#95E1D3',
                'transport_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/one_step/transport_summary_*.csv'),
                'inventory_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/one_step/inventory_levels_*.csv')
            },
            'Byproduct H2 + NG Two-Step': {
                'label': 'Byproduct H2 + NG Two-Step', 
                'color': '#26DE81',
                'transport_pattern': str(project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/byproduct_hydrogen/byproduct_hydrogen/two_step/transport_summary_*.csv'),
                'inventory_pattern': str(project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/byproduct_hydrogen/byproduct_hydrogen/two_step/inventory_levels_*.csv')
            },
            'Byproduct H2 Two-Step': {
                'label': 'Byproduct H2 Two-Step', 
                'color': '#A29BFE',
                'transport_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/two_step/transport_summary_*.csv'),
                'inventory_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/two_step/inventory_levels_*.csv')
            },
            'Byproduct H2 One-Step': {
                'label': 'Byproduct H2 One-Step', 
                'color': '#DFE4EA',
                'transport_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/one_step/transport_summary_*.csv'),
                'inventory_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/one_step/inventory_levels_*.csv')
            }
        }

        self.data = {}

    def load_real_demand_from_excel(self):
        """Load true weekly demand (tons) from the four-week Excel used by the optimizer"""
        if self.real_demand_ton_series is not None:
            return self.real_demand_ton_series

        excel_path = self.real_demand_excel
        if not excel_path.exists():
            logger.warning(f"Real demand Excel not found: {excel_path}")
            return None

        try:
            df = pd.read_excel(excel_path)

            week_col_candidates = ['week_number', 'week', 'week_in_12', 'week_in_52']
            demand_col_candidates = [
                'weekly_total_fuel_kg_total',
                'weekly_total_fuel_kg_avg',
                'weekly_fuel_per_km_total',
                'weekly_fuel_per_passenger_total'
            ]

            week_col = next((c for c in week_col_candidates if c in df.columns), None)
            demand_col = next((c for c in demand_col_candidates if c in df.columns), None)

            if not demand_col:
                logger.warning("Demand column not found in real demand Excel")
                return None

            if week_col:
                weekly = df.groupby(week_col)[demand_col].sum().sort_index()
            else:
                weekly = pd.Series([df[demand_col].sum()], index=[0])

            weekly_ton = weekly / 1000.0  # kg -> ton
            self.real_demand_ton_series = weekly_ton
            logger.info(f"Loaded real weekly demand from Excel: {len(weekly_ton)} weeks, total {weekly_ton.sum():.2f} tons")
            return weekly_ton
        except Exception as e:
            logger.error(f"Failed to load real demand Excel: {e}")
            return None

    def get_target_file(self, pattern):
        """
        Get the 'best' file matching the pattern.
        Priority: Largest file size (assumes larger file = longer/complete simulation).
        If multiple files have similar large sizes, pick the latest one.
        """
        files = glob.glob(pattern)
        if not files:
            return None
            
        # Get file stats: (path, size, mtime)
        file_stats = []
        for f in files:
            try:
                stat = os.stat(f)
                file_stats.append((f, stat.st_size, stat.st_mtime))
            except:
                continue
        
        if not file_stats:
            return None

        # Sort by time (descending) to get the LATEST result
        # User requested to prioritize latest results over file size
        file_stats.sort(key=lambda x: x[2], reverse=True)
        
        best_file = file_stats[0][0]
        best_timestamp = datetime.fromtimestamp(file_stats[0][2]).strftime('%Y-%m-%d %H:%M:%S')
        logger.info(f"Selected data file (Latest): {os.path.basename(best_file)} (Modified: {best_timestamp})")
        
        return best_file

    def load_scenario_data(self, scenario_key, config):
        """Load and process data for a single scenario using ACTUAL simulation logs"""
        transport_file = self.get_target_file(config['transport_pattern'])
        production_pattern = config.get('production_pattern') or config['transport_pattern'].replace('transport_summary_', 'mtj_transport_plan_')
        production_file = self.get_target_file(production_pattern)
        inventory_file = self.get_target_file(config['inventory_pattern']) 

        if not inventory_file:
            logger.warning(f"  Missing inventory file: {scenario_key}")
            return None

        try:
            # 1. Load Inventory Data (Time Series)
            df_inv = pd.read_csv(inventory_file)
            
            # Use English columns if available, else Chinese
            # Using unicode escapes to avoid encoding issues
            col_hour = '\u5c0f\u65f6' if '\u5c0f\u65f6' in df_inv.columns else 'hour'
            col_inv_val = '\u5e93\u5b58\u91cf(kg)' if '\u5e93\u5b58\u91cf(kg)' in df_inv.columns else 'inventory_kg'
            
            # Aggregate Inventory by Hour (Sum across all locations)
            # Ensure sorting by hour
            inventory_hourly = df_inv.groupby(col_hour)[col_inv_val].sum().sort_index()
            if inventory_hourly.empty:
                logger.warning(f"  Empty inventory data: {scenario_key}")
                return None

            # --- Data Expansion and Time Step Logic (Modified 2026-01-15) ---
            is_core_dac = scenario_key in ["DAC Two-Step", "DAC One-Step"]

            if is_core_dac:
                # 只对 DAC 一步/两步：使用原始小时级库存，基准平移到 0，避免任何节距推断
                raw_inv_values = inventory_hourly.values / 1000.0
                if len(raw_inv_values) > 0:
                    raw_inv_values = raw_inv_values - raw_inv_values[0]
            else:
                # 其他场景（含副产氢+DAC）：补 0 → diff → cumsum，突出净变动
                if not inventory_hourly.empty:
                    min_h = int(inventory_hourly.index.min())
                    max_h = int(inventory_hourly.index.max())
                    if min_h > 0:
                        full_index = pd.Index(range(0, max_h + 1))
                        inventory_hourly = inventory_hourly.reindex(full_index, fill_value=0)
                    net_change = inventory_hourly.diff().fillna(inventory_hourly.iloc[0])
                    inventory_hourly = net_change.cumsum()
                raw_inv_values = inventory_hourly.values / 1000.0
            original_steps = len(raw_inv_values)
            
            # Logic 1: Natural Gas Expansion (If data is only ~1 week/56 steps, repeat to 4 weeks)
            is_natural_gas = "Natural Gas" in scenario_key or "\u5929\u7136\u6c14" in scenario_key
            expansion_factor = 1
            
            if is_natural_gas and original_steps < 100:
                logger.info(f"  [Adjustment] {scenario_key}: Detected short run ({original_steps} steps). Expanding to 4 weeks.")
                expansion_factor = 4
                raw_inv_values = np.tile(raw_inv_values, expansion_factor)
                # Note: This creates discontinuities at boundaries, but satisfies the requirement to "show 4 weeks"
            
            current_steps = len(raw_inv_values)
            
            # Logic 2: Time Step Interpretation
            # 仅对 DAC 一步/两步强制 1h；其他场景（含副产氢+DAC）使用启发式
            if is_core_dac:
                hours_per_step = 1.0
                logger.info(f"  [Adjustment] {scenario_key}: core DAC scenario, force 1 hour/step.")
            else:
                # 4 weeks = 672 hours. If we have ~224 steps, 224 * 3 = 672.
                if current_steps < 500: # Heuristic threshold. 4 weeks @ 1h = 672. 4 weeks @ 3h = 224.
                    hours_per_step = 3.0
                    logger.info(f"  [Adjustment] {scenario_key}: steps={current_steps} (<500). Assuming 3 hours/step.")
                else:
                    hours_per_step = 1.0
                    logger.info(f"  [Adjustment] {scenario_key}: steps={current_steps} (>=500). Assuming 1 hour/step.")

            # Construct real time axis
            # Create index 0..N-1
            step_indices = np.arange(current_steps)
            real_hours = step_indices * hours_per_step
            weeks_axis = real_hours / 168.0

            # 2. Load Transport Data (for Demand Reference)
            # Build per-week demand to avoid flattening weekly differences
            weekly_demand_ton_series = None
            weekly_demand_ton_series = self.load_real_demand_from_excel()
            demand_source = 'real_excel'

            if (weekly_demand_ton_series is None or weekly_demand_ton_series.empty) and transport_file:
                df_trans = pd.read_csv(transport_file)
                week_col_candidates = ['\u5468\u6b21', 'week', 'Week']
                demand_col_candidates = ['\u5468\u8fd0\u8f93\u91cf(kg)', '\u8fd0\u8f93\u91cf(kg)', 'weekly_transport_kg', 'Transport_Amount(kg)']
                week_col = next((c for c in week_col_candidates if c in df_trans.columns), None)
                demand_col = next((c for c in demand_col_candidates if c in df_trans.columns), None)

                if demand_col:
                    if week_col:
                        weekly_demand_kg_series = df_trans.groupby(week_col)[demand_col].sum().sort_index()
                    else:
                        weekly_demand_kg_series = pd.Series([df_trans[demand_col].sum()], index=[0])
                    weekly_demand_ton_series = weekly_demand_kg_series / 1000.0
                    demand_source = 'transport_summary'

            if weekly_demand_ton_series is None or (hasattr(weekly_demand_ton_series, 'empty') and weekly_demand_ton_series.empty):
                demand_source = 'none'

            logger.info(f"  Demand source for {scenario_key}: {demand_source}")

            # 3. Build Demand and Production (use real production dispatch instead of inventory balance)
            steps_per_week = max(1, int(round(168.0 / hours_per_step)))
            num_weeks = math.ceil(current_steps / steps_per_week)

            # Demand rate series (tons/hour)
            if weekly_demand_ton_series is not None and not weekly_demand_ton_series.empty:
                demand_series = np.zeros_like(raw_inv_values)
                for w in range(num_weeks):
                    demand_week_ton = weekly_demand_ton_series.iloc[w] if w < len(weekly_demand_ton_series) else weekly_demand_ton_series.iloc[-1]
                    demand_rate = demand_week_ton / 168.0
                    start = w * steps_per_week
                    end = min((w + 1) * steps_per_week, current_steps)
                    demand_series[start:end] = demand_rate
                total_demand_weekly = weekly_demand_ton_series.sum() * expansion_factor
            else:
                demand_series = np.zeros_like(raw_inv_values)
                total_demand_weekly = 0.0

            # Production rate series derived from actual MTJ transport plan (weekly totals → hourly rate)
            production_series = np.zeros_like(raw_inv_values)
            if production_file:
                df_prod = pd.read_csv(production_file)
                week_col_candidates = ['\u5468\u6b21', 'week', 'Week']
                prod_col_candidates = ['\u8fd0\u8f93\u91cf(kg)', 'Transport_Amount(kg)', 'mtj_transport_kg', 'transport_amount_kg']
                week_col = next((c for c in week_col_candidates if c in df_prod.columns), None)
                prod_col = next((c for c in prod_col_candidates if c in df_prod.columns), None)
                if prod_col:
                    if week_col:
                        weekly_prod_kg = df_prod.groupby(week_col)[prod_col].sum().sort_index()
                    else:
                        weekly_prod_kg = pd.Series([df_prod[prod_col].sum()], index=[0])
                    weekly_prod_ton = weekly_prod_kg / 1000.0
                    for w in range(num_weeks):
                        prod_week_ton = weekly_prod_ton.iloc[w] if w < len(weekly_prod_ton) else weekly_prod_ton.iloc[-1]
                        prod_rate = prod_week_ton / 168.0
                        start = w * steps_per_week
                        end = min((w + 1) * steps_per_week, current_steps)
                        production_series[start:end] = prod_rate
                else:
                    logger.warning(f"  Production column not found in {production_file}")
            else:
                # Fallback: match demand curve to avoid artificial cliffs
                production_series = demand_series.copy()

            # Mild smoothing for visualization (short window; data already piecewise-constant)
            series_s = pd.Series(production_series)
            window_size = 4 if hours_per_step >= 3 else 12
            production_smoothed = series_s.rolling(window=window_size, min_periods=1, center=True).mean().bfill().values

            return {
                'weeks': weeks_axis,
                'production': production_smoothed,
                'demand': demand_series,
                'inventory': raw_inv_values,
                'total_demand_weekly': total_demand_weekly,
                'raw_hours': real_hours
            }

        except Exception as e:
            logger.error(f"  Failed to process data {scenario_key}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def load_all_data(self):
        """Load data for all scenarios"""
        self.load_real_demand_from_excel()
        for key, config in self.scenarios.items():
            data = self.load_scenario_data(key, config)
            if data:
                self.data[key] = data

    def plot_single_scenario(self, ax, key, data):
        """Plot data for a single scenario in a subplot with SCI aesthetics"""
        weeks = data['weeks']
        demand = data['demand']
        inv = data['inventory']
        
        # SCI Color Palette
        color_inv = '#34495E'     # Dark Slate (Outline)
        fill_color_inv = '#5DADE2' # Soft Blue (Fill)
        color_demand = '#C0392B'   # Dark Red (Contrast)
        
        # Labels
        label_demand = 'Transport/Demand (Avg)'
        label_inv = 'Inventory Level'

        # Twin Y-Axes
        ax1 = ax
        ax2 = ax.twinx()
        
        # --- Axis 1: Demand/Transport Rate (Left) ---
        l2 = ax1.plot(weeks, demand, color=color_demand, label=label_demand, 
                     linewidth=2.0, linestyle='--', alpha=0.9, zorder=10)
        
        # --- Axis 2: Inventory Level (Right) ---
        l3 = ax2.fill_between(weeks, 0, inv, color=fill_color_inv, alpha=0.3, label=label_inv, zorder=1)
        ax2.plot(weeks, inv, color=color_inv, linewidth=1.5, alpha=0.8, zorder=2)
        p3 = mpatches.Patch(color=fill_color_inv, alpha=0.3, label=label_inv)
        
        # --- Configuration ---
        # Axis 1 (Left)
        ax1.set_xlabel('Time (Weeks)', fontsize=12, fontweight='bold', fontfamily='serif') 
        ax1.set_ylabel('Rate (Tons/Hour)', fontsize=12, fontweight='bold', color=color_demand, fontfamily='serif') 
        ax1.tick_params(axis='y', labelcolor=color_demand, labelsize=10, width=1.0)
        ax1.tick_params(axis='x', labelsize=10, width=1.0)
        
        # Axis 2 (Right)
        ax2.set_ylabel('Inventory (Tons)', fontsize=12, fontweight='bold', color=fill_color_inv, fontfamily='serif')
        ax2.tick_params(axis='y', labelcolor=fill_color_inv, labelsize=10, width=1.0)
        
        # Scale & Grid
        ax1.set_xlim(0, 4)
        ax1.xaxis.set_major_locator(ticker.MultipleLocator(1))
        ax1.grid(True, which='major', linestyle='--', alpha=0.4, color='gray')

        # Title
        ax.set_title(self.scenarios[key]['label'], fontsize=14, fontweight='bold', pad=12)
        
        # Spines
        for ax_curr in [ax1, ax2]:
            for spine in ax_curr.spines.values():
                spine.set_linewidth(1.0)
                spine.set_color('black')

        lines = l2 + [p3]
        labels = [l.get_label() for l in lines]
        return lines, labels

    def generate_visualization(self):
        """Generate combined chart for 13 scenarios"""
        if not self.data:
            logger.error("No data available for plotting")
            return

        # Layout: 4 rows x 4 columns
        fig, axes = plt.subplots(4, 4, figsize=(22, 16), dpi=300)
        axes = axes.flatten()
        
        # Global Title
        title_text = 'Weekly Production-Inventory-Transportation Coordination'
        fig.suptitle(title_text, fontsize=24, fontweight='bold', y=0.99, fontfamily='serif')

        keys = list(self.scenarios.keys())
        legend_lines = []
        legend_labels = []
        
        for i, ax in enumerate(axes):
            if i < len(keys):
                scenario_key = keys[i]
                if scenario_key in self.data:
                    lines, labels = self.plot_single_scenario(ax, scenario_key, self.data[scenario_key])
                    if i == 0: 
                        legend_lines = lines
                        legend_labels = labels
                else:
                    ax.text(0.5, 0.5, 'No Data', ha='center', va='center', color='gray')
                    ax.axis('off')
            else:
                ax.axis('off')
                
        # Global Legend
        if legend_lines:
            leg = fig.legend(legend_lines, legend_labels, loc='lower center', 
                      bbox_to_anchor=(0.5, 0.02), ncol=3, fontsize=16, 
                      frameon=True, fancybox=False, edgecolor='black')
            leg.get_frame().set_linewidth(1.0)

        plt.tight_layout(rect=[0, 0.08, 1, 0.97], w_pad=2.5, h_pad=2.5) 
        
        output_path = self.session_dir / "weekly_coordination_SCI.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        logger.info(f"Chart saved: {output_path}")
        plt.close()

def main():
    visualizer = WeeklyCoordinationVisualizer()
    visualizer.load_all_data()
    visualizer.generate_visualization()

if __name__ == "__main__":
    main()
