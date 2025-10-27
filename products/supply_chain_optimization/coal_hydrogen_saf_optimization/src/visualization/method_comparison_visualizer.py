"""
FT One-Step vs Two-Step Optimization Results Comparison Visualization Tool
Generate beautiful multi-dimensional comparison dashboard with automatic file detection
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
import glob
warnings.filterwarnings('ignore')

# Font configuration
import matplotlib.font_manager as fm
import os

# Try multiple font paths
font_paths = [
    r'C:\Windows\Fonts\msyh.ttc',      # Microsoft YaHei
    r'C:\Windows\Fonts\msyhbd.ttc',    # Microsoft YaHei Bold
    r'C:\Windows\Fonts\simhei.ttf',    # SimHei
    r'C:\Windows\Fonts\simsun.ttc',    # SimSun
]

font_loaded = False
for font_path in font_paths:
    if os.path.exists(font_path):
        try:
            fm.fontManager.addfont(font_path)
            font_prop = FontProperties(fname=font_path)
            font_name = font_prop.get_name()

            plt.rcParams['font.family'] = 'sans-serif'
            plt.rcParams['font.sans-serif'] = [font_name] + plt.rcParams['font.sans-serif']

            print(f"Font loaded successfully: {font_name} (path: {font_path})")
            font_loaded = True
            break
        except Exception as e:
            print(f"Font loading failed {font_path}: {e}")
            continue

if not font_loaded:
    print("Using default font configuration")
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS', 'DejaVu Sans']

plt.rcParams['axes.unicode_minus'] = False
mpl.rcParams['font.size'] = 10

# Verify font settings
print(f"Current font family: {plt.rcParams['font.family']}")
print(f"Current sans-serif font list: {plt.rcParams['font.sans-serif'][:3]}")

# Set style
sns.set_style("whitegrid")
plt.rcParams['figure.dpi'] = 100
plt.rcParams['savefig.dpi'] = 300


class MethodComparisonVisualizer:
    """FT One-Step vs Two-Step Comparison Visualizer"""

    def __init__(self):
        """Initialize visualizer"""
        self.one_step_data = None
        self.two_step_data = None
        self.comparison_metrics = {}

        # Color scheme
        self.colors = {
            'one_step': '#1f77b4',  # Professional blue
            'two_step': '#ff7f0e',  # Vibrant orange
            'background': '#f5f5f5',
            'card': '#ffffff',
            'text': '#333333',
            'grid': '#e0e0e0'
        }

    def load_data(self, one_step_file, two_step_file):
        """
        Load optimization results data for one-step and two-step methods

        Args:
            one_step_file: FT One-Step result file path
            two_step_file: Two-Step result file path
        """
        print(f"Loading FT One-Step data: {one_step_file}")
        self.one_step_data = pd.read_csv(one_step_file)

        print(f"Loading Two-Step data: {two_step_file}")
        self.two_step_data = pd.read_csv(two_step_file)

        print("Data loading completed!")

    def extract_comparison_metrics(self):
        """Extract key comparison metrics"""
        print("\nExtracting comparison metrics...")

        # One-step metrics
        one_step = self.one_step_data.iloc[0]
        two_step = self.two_step_data.iloc[0]

        self.comparison_metrics = {
            'one_step': {
                # Core economic indicators
                'lcoe': one_step['生命周期平准化成本(元/kg)'],
                'annual_cost': one_step['年化平准化成本(元/kg)'],
                'total_cost': one_step['生命周期总成本(元)'],

                # Demand
                'demand_fulfillment': one_step['需求满足比例(%)'],

                # Production indicators
                'annual_production': one_step['年产量(kg)'],
                'total_production': one_step['20年总产量(kg)'],

                # Environmental metrics
                'carbon_intensity': one_step['碳强度(kg CO2eq/kg SAF)'],
                'vs_jet_fuel': one_step['相比传统航煤(%)'],
                'vs_corsia': one_step['相比CORSIA标准(%)'],

                # Cost structure
                'capex_mtj': one_step['MTJ工厂建设投资(元)'],
                'opex_mtj': one_step['MTJ生产运营成本(元)'],
                'ng_cost': one_step['天然气原料成本(元)'],
                'transport_cost': one_step['MTJ运输运营成本(元)'],
            },
            'two_step': {
                # Core economic indicators
                'lcoe': two_step['生命周期平准化成本(元/kg)'],
                'annual_cost': two_step['年化平准化成本(元/kg)'],
                'total_cost': two_step['生命周期总成本(元)'],

                # Demand
                'demand_fulfillment': two_step['需求满足比例(%)'],

                # Production indicators
                'annual_production': two_step['年产量(kg)'],
                'total_production': two_step['20年总产量(kg)'],

                # Environmental metrics
                'carbon_intensity': two_step['碳强度(kg CO2eq/kg SAF)'],
                'vs_jet_fuel': two_step['相比传统航煤(%)'],
                'vs_corsia': two_step['相比CORSIA标准(%)'],

                # Energy efficiency
                'h2_efficiency': two_step.get('电解制氢实际效率(%)', 80.0),
                'mtj_efficiency': two_step.get('MTJ转化效率(%)', 85.0),
                'overall_efficiency': two_step.get('综合电力转MTJ效率(%)', 68.0),

                # Cost structure
                'capex_mtj': two_step['MTJ工厂建设投资(元)'],
                'capex_electrolyzer': two_step['电解槽建设投资(元)'],
                'opex_mtj': two_step['MTJ生产运营成本(元)'],
                'h2_cost': two_step['氢气制取成本(元)'],
                'electricity_cost': two_step['电力成本(元)'],
                'transport_cost': two_step['MTJ运输运营成本(元)'],
            }
        }

        # Calculate comparison difference
        self.comparison_metrics['difference'] = {
            'lcoe_diff': self.comparison_metrics['one_step']['lcoe'] - self.comparison_metrics['two_step']['lcoe'],
            'lcoe_pct': (self.comparison_metrics['one_step']['lcoe'] / self.comparison_metrics['two_step']['lcoe'] - 1) * 100,
            'carbon_diff': self.comparison_metrics['one_step']['carbon_intensity'] - self.comparison_metrics['two_step']['carbon_intensity'],
            'carbon_pct': (self.comparison_metrics['one_step']['carbon_intensity'] / self.comparison_metrics['two_step']['carbon_intensity'] - 1) * 100,
        }

        print("Comparison metrics extraction completed!")
        print(f"  FT One-Step LCOE: {self.comparison_metrics['one_step']['lcoe']:.3f} CNY/kg")
        print(f"  Two-Step LCOE: {self.comparison_metrics['two_step']['lcoe']:.3f} CNY/kg")
        print(f"  Cost difference: {self.comparison_metrics['difference']['lcoe_diff']:.3f} CNY/kg ({self.comparison_metrics['difference']['lcoe_pct']:.1f}%)")

    def create_dashboard(self, output_dir):
        """
        Create comprehensive comparison dashboard

        Args:
            output_dir: Output directory path
        """
        print("\nCreating comprehensive comparison dashboard...")

        # Create large canvas
        fig = plt.figure(figsize=(20, 12))
        fig.suptitle('FT One-Step vs Two-Step Method Comparison Dashboard',
                     fontsize=24, fontweight='bold', y=0.98)

        # Set background color
        fig.patch.set_facecolor(self.colors['background'])

        # Create grid layout
        gs = gridspec.GridSpec(3, 3, figure=fig, hspace=0.3, wspace=0.3,
                              left=0.05, right=0.95, top=0.93, bottom=0.05)

        # 1. Core Metrics Comparison (top left, spans 2 columns)
        ax1 = fig.add_subplot(gs[0, :2])
        self._plot_core_metrics_comparison(ax1)

        # 2. Overall radar chart (top right)
        ax2 = fig.add_subplot(gs[0, 2], projection='polar')
        self._plot_radar_chart(ax2)

        # 3. Cost structure comparison (middle row, spans 3 columns)
        ax3 = fig.add_subplot(gs[1, :])
        self._plot_cost_structure(ax3)

        # 4. Environmental impact comparison (bottom left)
        ax4 = fig.add_subplot(gs[2, 0])
        self._plot_environmental_impact(ax4)

        # 5. KPI cards (bottom middle and right)
        ax5 = fig.add_subplot(gs[2, 1])
        self._plot_kpi_cards(ax5)

        # 6. Energy efficiency comparison (bottom right)
        ax6 = fig.add_subplot(gs[2, 2])
        self._plot_energy_efficiency(ax6)

        # Save chart
        output_path = Path(output_dir) / f'method_comparison_dashboard_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
        plt.savefig(output_path, dpi=300, bbox_inches='tight',
                   facecolor=self.colors['background'])
        print(f"Dashboard saved to: {output_path}")

        plt.close()

        return output_path

    def _plot_core_metrics_comparison(self, ax):
        """Plot core metrics comparison bar chart"""
        metrics = ['LCOE\n(CNY/kg)', 'Demand Fulfillment\n(%)', 'Annual Production\n(10kt)']
        one_step_values = [
            self.comparison_metrics['one_step']['lcoe'],
            self.comparison_metrics['one_step']['demand_fulfillment'],
            self.comparison_metrics['one_step']['annual_production'] / 1e7  # Convert to 10kt
        ]
        two_step_values = [
            self.comparison_metrics['two_step']['lcoe'],
            self.comparison_metrics['two_step']['demand_fulfillment'],
            self.comparison_metrics['two_step']['annual_production'] / 1e7
        ]

        x = np.arange(len(metrics))
        width = 0.35

        bars1 = ax.bar(x - width/2, one_step_values, width, label='FT One-Step',
                      color=self.colors['one_step'], alpha=0.8, edgecolor='black', linewidth=1.5)
        bars2 = ax.bar(x + width/2, two_step_values, width, label='Two-Step',
                      color=self.colors['two_step'], alpha=0.8, edgecolor='black', linewidth=1.5)

        ax.set_xlabel('Metrics', fontsize=12, fontweight='bold')
        ax.set_ylabel('Value', fontsize=12, fontweight='bold')
        ax.set_title('Core Metrics Comparison', fontsize=14, fontweight='bold', pad=15)
        ax.set_xticks(x)
        ax.set_xticklabels(metrics, fontsize=11)
        ax.legend(fontsize=11, loc='upper right', framealpha=0.9)
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        ax.set_facecolor('white')

        # Add value labels
        for bar in bars1 + bars2:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height:.2f}',
                   ha='center', va='bottom', fontsize=10, fontweight='bold')

    def _plot_radar_chart(self, ax):
        """Plot radar chart showing multi-dimensional performance"""
        categories = ['Economics', 'Environment', 'Efficiency', 'Demand', 'Energy Use']

        # Normalize metrics (0-100 score)
        one_step_scores = [
            100 - (self.comparison_metrics['one_step']['lcoe'] - 5) * 20,  # Lower cost is better
            100 - self.comparison_metrics['one_step']['carbon_intensity'] * 20,  # Lower carbon intensity is better
            80,  # Efficiency baseline score
            self.comparison_metrics['one_step']['demand_fulfillment'],
            75  # Natural gas utilization efficiency assumption
        ]

        two_step_scores = [
            100 - (self.comparison_metrics['two_step']['lcoe'] - 5) * 20,
            100 - self.comparison_metrics['two_step']['carbon_intensity'] * 20,
            85,  # Two-step conversion efficiency slightly higher
            self.comparison_metrics['two_step']['demand_fulfillment'],
            self.comparison_metrics['two_step'].get('overall_efficiency', 68)
        ]

        # Close radar chart
        angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
        one_step_scores += one_step_scores[:1]
        two_step_scores += two_step_scores[:1]
        angles += angles[:1]

        ax.plot(angles, one_step_scores, 'o-', linewidth=2, label='FT One-Step',
               color=self.colors['one_step'], markersize=8)
        ax.fill(angles, one_step_scores, alpha=0.25, color=self.colors['one_step'])

        ax.plot(angles, two_step_scores, 'o-', linewidth=2, label='Two-Step',
               color=self.colors['two_step'], markersize=8)
        ax.fill(angles, two_step_scores, alpha=0.25, color=self.colors['two_step'])

        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(categories, fontsize=10)
        ax.set_ylim(0, 100)
        ax.set_title('Multi-Dimensional Performance', fontsize=14, fontweight='bold', pad=20)
        ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1), fontsize=10)
        ax.grid(True, linestyle='--', alpha=0.5)

    def _plot_cost_structure(self, ax):
        """Plot cost structure comparison stacked bar chart"""
        # One-step cost structure
        one_step_costs = {
            'MTJ Plant CAPEX': self.comparison_metrics['one_step']['capex_mtj'],
            'MTJ OPEX': self.comparison_metrics['one_step']['opex_mtj'],
            'Natural Gas': self.comparison_metrics['one_step']['ng_cost'],
            'Transport': self.comparison_metrics['one_step']['transport_cost'],
        }

        # Two-step cost structure
        two_step_costs = {
            'MTJ Plant CAPEX': self.comparison_metrics['two_step']['capex_mtj'],
            'Electrolyzer CAPEX': self.comparison_metrics['two_step']['capex_electrolyzer'],
            'MTJ OPEX': self.comparison_metrics['two_step']['opex_mtj'],
            'H2 Production': self.comparison_metrics['two_step']['h2_cost'],
            'Electricity': self.comparison_metrics['two_step']['electricity_cost'],
            'Transport': self.comparison_metrics['two_step']['transport_cost'],
        }

        # Calculate total cost and percentage
        one_step_total = sum(one_step_costs.values())
        two_step_total = sum(two_step_costs.values())

        # Convert to billion CNY and calculate percentage
        one_step_pcts = {k: v/one_step_total*100 for k, v in one_step_costs.items()}
        two_step_pcts = {k: v/two_step_total*100 for k, v in two_step_costs.items()}

        # Prepare data
        methods = ['FT One-Step', 'Two-Step']

        # Plot stacked bar chart
        colors_palette = plt.cm.Set3(np.linspace(0, 1, 10))

        # One-step
        bottom = 0
        for i, (category, pct) in enumerate(one_step_pcts.items()):
            ax.barh(0, pct, left=bottom, height=0.5,
                   label=category if i < len(one_step_pcts) else '',
                   color=colors_palette[i], alpha=0.8, edgecolor='black', linewidth=0.5)
            if pct > 5:  # Only label percentages greater than 5%
                ax.text(bottom + pct/2, 0, f'{pct:.1f}%',
                       ha='center', va='center', fontsize=9, fontweight='bold')
            bottom += pct

        # Two-step
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
        ax.set_xlabel('Cost Share (%)', fontsize=12, fontweight='bold')
        ax.set_title('Lifecycle Cost Structure Comparison', fontsize=14, fontweight='bold', pad=15)
        ax.set_xlim(0, 100)
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=9,
                 framealpha=0.9, ncol=1)
        ax.grid(axis='x', alpha=0.3, linestyle='--')
        ax.set_facecolor('white')

        # Add total cost annotation
        ax.text(102, 0, f'Total Cost:\n{one_step_total/1e8:.1f} Billion CNY',
               ha='left', va='center', fontsize=10, fontweight='bold',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))
        ax.text(102, 1, f'Total Cost:\n{two_step_total/1e8:.1f} Billion CNY',
               ha='left', va='center', fontsize=10, fontweight='bold',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))

    def _plot_environmental_impact(self, ax):
        """Plot environmental impact comparison"""
        categories = ['Carbon Intensity\n(kg CO2eq/kg)', 'vs Jet Fuel\n(%)', 'vs CORSIA\nStandard(%)']
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

        bars1 = ax.bar(x - width/2, one_step_values, width, label='FT One-Step',
                      color=self.colors['one_step'], alpha=0.8, edgecolor='black', linewidth=1.5)
        bars2 = ax.bar(x + width/2, two_step_values, width, label='Two-Step',
                      color=self.colors['two_step'], alpha=0.8, edgecolor='black', linewidth=1.5)

        ax.set_xlabel('Environmental Metrics', fontsize=11, fontweight='bold')
        ax.set_ylabel('Value', fontsize=11, fontweight='bold')
        ax.set_title('Environmental Impact Comparison', fontsize=13, fontweight='bold', pad=12)
        ax.set_xticks(x)
        ax.set_xticklabels(categories, fontsize=9)
        ax.legend(fontsize=9, loc='upper right', framealpha=0.9)
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        ax.set_facecolor('white')

        # Add value labels
        for bar in bars1 + bars2:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height:.2f}',
                   ha='center', va='bottom', fontsize=8, fontweight='bold')

    def _plot_kpi_cards(self, ax):
        """Plot KPI cards"""
        ax.axis('off')

        # Key KPIs
        kpis = [
            {
                'title': 'Cost Advantage',
                'one_step': f"{self.comparison_metrics['one_step']['lcoe']:.2f} CNY/kg",
                'two_step': f"{self.comparison_metrics['two_step']['lcoe']:.2f} CNY/kg",
                'diff': f"{self.comparison_metrics['difference']['lcoe_pct']:.1f}%",
                'winner': 'one_step' if self.comparison_metrics['difference']['lcoe_diff'] < 0 else 'two_step'
            },
            {
                'title': 'Carbon Advantage',
                'one_step': f"{self.comparison_metrics['one_step']['carbon_intensity']:.2f}",
                'two_step': f"{self.comparison_metrics['two_step']['carbon_intensity']:.2f}",
                'diff': f"{self.comparison_metrics['difference']['carbon_pct']:.1f}%",
                'winner': 'two_step' if self.comparison_metrics['difference']['carbon_diff'] > 0 else 'one_step'
            }
        ]

        y_pos = 0.8
        for kpi in kpis:
            # Title
            ax.text(0.5, y_pos, kpi['title'], ha='center', va='top',
                   fontsize=13, fontweight='bold',
                   bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.5))

            # FT One-Step
            color1 = 'green' if kpi['winner'] == 'one_step' else 'gray'
            ax.text(0.25, y_pos - 0.12, f"FT: {kpi['one_step']}",
                   ha='center', va='top', fontsize=11, color=color1, fontweight='bold')

            # Two-Step
            color2 = 'green' if kpi['winner'] == 'two_step' else 'gray'
            ax.text(0.75, y_pos - 0.12, f"Two: {kpi['two_step']}",
                   ha='center', va='top', fontsize=11, color=color2, fontweight='bold')

            # Difference
            ax.text(0.5, y_pos - 0.24, f"Difference: {kpi['diff']}",
                   ha='center', va='top', fontsize=10, style='italic')

            y_pos -= 0.45

        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_title('Key KPI Comparison', fontsize=13, fontweight='bold')

    def _plot_energy_efficiency(self, ax):
        """Plot energy efficiency comparison"""
        # Two-step energy efficiency data
        two_step_efficiency = [
            self.comparison_metrics['two_step'].get('h2_efficiency', 80),
            self.comparison_metrics['two_step'].get('mtj_efficiency', 85),
            self.comparison_metrics['two_step'].get('overall_efficiency', 68)
        ]

        # FT one-step assumes natural gas conversion efficiency
        one_step_efficiency = [75, 0, 0]  # Only one-step conversion

        categories = ['H2 Production\nEfficiency(%)', 'MTJ Conversion\nEfficiency(%)', 'Overall\nEfficiency(%)']
        x = np.arange(len(categories))
        width = 0.35

        # Only show two-step full data
        bars1 = ax.bar(x - width/2, one_step_efficiency, width, label='FT One-Step',
                      color=self.colors['one_step'], alpha=0.8, edgecolor='black', linewidth=1.5)
        bars2 = ax.bar(x + width/2, two_step_efficiency, width, label='Two-Step',
                      color=self.colors['two_step'], alpha=0.8, edgecolor='black', linewidth=1.5)

        ax.set_xlabel('Efficiency Metrics', fontsize=11, fontweight='bold')
        ax.set_ylabel('Efficiency (%)', fontsize=11, fontweight='bold')
        ax.set_title('Energy Conversion Efficiency Comparison', fontsize=13, fontweight='bold', pad=12)
        ax.set_xticks(x)
        ax.set_xticklabels(categories, fontsize=9)
        ax.set_ylim(0, 100)
        ax.legend(fontsize=9, loc='upper right', framealpha=0.9)
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        ax.set_facecolor('white')

        # Add value labels
        for bars in [bars1, bars2]:
            for bar in bars:
                height = bar.get_height()
                if height > 0:
                    ax.text(bar.get_x() + bar.get_width()/2., height,
                           f'{height:.0f}%',
                           ha='center', va='bottom', fontsize=9, fontweight='bold')


def find_latest_result_files(results_dir):
    """
    Automatically find latest optimization result files

    Args:
        results_dir: Results directory path

    Returns:
        (one_step_file, two_step_file): Latest one-step and two-step result files
    """
    # Find all optimization result files
    all_files = glob.glob(str(results_dir / 'optimization_summary_*.csv'))

    if not all_files:
        raise FileNotFoundError(f"No optimization result files found in: {results_dir}")

    # Sort by modification time (newest first)
    all_files.sort(key=lambda x: Path(x).stat().st_mtime, reverse=True)

    print(f"\nFound {len(all_files)} optimization result files:")

    one_step_file = None
    two_step_file = None

    # Check each file to determine if it's one-step or two-step
    for file_path in all_files:
        df = pd.read_csv(file_path, nrows=0)  # Only read column names
        columns = df.columns.tolist()

        # Two-step features: contains electrolyzer and hydrogen related columns
        is_two_step = '电解槽建设投资(元)' in columns and '氢气制取成本(元)' in columns
        # One-step feature: contains natural gas cost but no electrolyzer
        is_one_step = '天然气原料成本(元)' in columns and '电解槽建设投资(元)' not in columns

        file_name = Path(file_path).name

        if is_two_step and two_step_file is None:
            two_step_file = Path(file_path)
            print(f"  [*] Two-Step (latest): {file_name}")
        elif is_one_step and one_step_file is None:
            one_step_file = Path(file_path)
            print(f"  [*] One-Step (latest): {file_name}")
        else:
            method = "Two-Step" if is_two_step else "One-Step" if is_one_step else "Unknown"
            print(f"      {method}: {file_name}")

        # Exit loop if both files found
        if one_step_file and two_step_file:
            break

    if not one_step_file:
        raise FileNotFoundError("FT One-Step result file not found")
    if not two_step_file:
        raise FileNotFoundError("Two-Step result file not found")

    return one_step_file, two_step_file


def main():
    """Main function"""
    print("="*60)
    print("FT One-Step vs Two-Step Optimization Results Comparison")
    print("="*60)

    # Initialize visualizer
    visualizer = MethodComparisonVisualizer()

    # Set file paths
    base_dir = Path(__file__).parent.parent.parent
    results_dir = base_dir / 'results'

    # Automatically find latest result files
    try:
        one_step_file, two_step_file = find_latest_result_files(results_dir)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return

    # Load data
    visualizer.load_data(one_step_file, two_step_file)

    # Extract comparison metrics
    visualizer.extract_comparison_metrics()

    # Create output directory
    output_dir = results_dir / 'comparisons'
    output_dir.mkdir(exist_ok=True)

    # Generate comparison dashboard
    dashboard_path = visualizer.create_dashboard(output_dir)

    print("\n" + "="*60)
    print("Visualization completed!")
    print(f"Dashboard saved to: {dashboard_path}")
    print("="*60)


if __name__ == '__main__':
    main()
