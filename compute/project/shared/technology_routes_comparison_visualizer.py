"""
Technology Routes Comparison Visualization Tool
Compare Coal-based, Natural Gas-based, and Green Hydrogen-based SAF optimization results
Generate comprehensive multi-dimensional comparison dashboard
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
import glob
warnings.filterwarnings('ignore')

# Set style with default fonts (no Chinese font configuration needed)
sns.set_style("whitegrid")
plt.rcParams['figure.dpi'] = 100
plt.rcParams['savefig.dpi'] = 300
plt.rcParams['font.size'] = 10
plt.rcParams['axes.unicode_minus'] = False


class TechnologyRoutesComparisonVisualizer:
    """Visualizer for comparing three SAF technology routes: Coal, Natural Gas, Green H2"""

    def __init__(self):
        """Initialize visualizer"""
        self.coal_data = None
        self.ng_data = None
        self.green_h2_data = None
        self.comparison_metrics = {}

        # Color scheme
        self.colors = {
            'coal': '#8B4513',        # Brown - Coal
            'natural_gas': '#FF7F0E',  # Orange - Natural Gas
            'green_h2': '#2CA02C',    # Green - Green Hydrogen
            'background': '#f5f5f5',
            'card': '#ffffff',
            'text': '#333333',
            'grid': '#e0e0e0'
        }

    def load_data(self, coal_file, ng_file, green_h2_file):
        """
        Load optimization result data for all three technology routes

        Args:
            coal_file: Coal-based result file path
            ng_file: Natural gas-based result file path
            green_h2_file: Green hydrogen-based result file path
        """
        print(f"Loading coal-based data: {coal_file}")
        self.coal_data = pd.read_csv(coal_file)

        print(f"Loading natural gas-based data: {ng_file}")
        self.ng_data = pd.read_csv(ng_file)

        print(f"Loading green hydrogen-based data: {green_h2_file}")
        self.green_h2_data = pd.read_csv(green_h2_file)

        print("Data loading completed!")

    def extract_comparison_metrics(self):
        """Extract key comparison metrics"""
        print("\nExtracting comparison metrics...")

        # Extract metrics for each technology route
        coal = self.coal_data.iloc[0]
        ng = self.ng_data.iloc[0]
        green_h2 = self.green_h2_data.iloc[0]

        self.comparison_metrics = {
            'coal': {
                # Core economic indicators
                'lcoe': coal['生命周期平准化成本(元/kg)'],
                'annual_cost': coal.get('年化平准化成本(元/kg)', coal['生命周期平准化成本(元/kg)']),
                'total_cost': coal['生命周期总成本(元)'],

                # Demand fulfillment
                'demand_fulfillment': coal['需求满足比例(%)'],

                # Production indicators
                'annual_production': coal['年产量(kg)'],
                'total_production': coal['20年总产量(kg)'],

                # Environmental indicators
                'carbon_intensity': coal['碳强度(kg CO2eq/kg SAF)'],
                'vs_jet_fuel': coal['相比传统航煤(%)'],
                'vs_corsia': coal['相比CORSIA标准(%)'],

                # Cost structure
                'saf_capex': coal.get('SAF工厂建设投资(元)', coal.get('MTJ工厂建设投资(元)', 0)),
                'saf_opex': coal.get('SAF生产运营成本(元)', coal.get('MTJ生产运营成本(元)', 0)),
                'electrolyzer_capex': coal.get('电解槽建设投资(元)', 0),
                'h2_cost': coal.get('氢气制取成本(元)', coal.get('氢气设备摊销成本(元/kg)', 0) * coal['20年总产量(kg)']),
                'co2_cost': coal.get('CO2捕获成本(元)', 0),
                'coal_cost': coal.get('煤炭原料成本(元)', 0),
                'transport_cost': coal.get('SAF运输运营成本(元)', coal.get('MTJ运输运营成本(元)', 0)),
            },
            'natural_gas': {
                # Core economic indicators
                'lcoe': ng['生命周期平准化成本(元/kg)'],
                'annual_cost': ng.get('年化平准化成本(元/kg)', ng['生命周期平准化成本(元/kg)']),
                'total_cost': ng['生命周期总成本(元)'],

                # Demand fulfillment
                'demand_fulfillment': ng['需求满足比例(%)'],

                # Production indicators
                'annual_production': ng['年产量(kg)'],
                'total_production': ng['20年总产量(kg)'],

                # Environmental indicators
                'carbon_intensity': ng['碳强度(kg CO2eq/kg SAF)'],
                'vs_jet_fuel': ng['相比传统航煤(%)'],
                'vs_corsia': ng['相比CORSIA标准(%)'],

                # Cost structure
                'saf_capex': ng.get('SAF工厂建设投资(元)', ng.get('MTJ工厂建设投资(元)', 0)),
                'saf_opex': ng.get('SAF生产运营成本(元)', ng.get('MTJ生产运营成本(元)', 0)),
                'electrolyzer_capex': ng.get('电解槽建设投资(元)', 0),
                'h2_cost': ng.get('氢气制取成本(元)', 0),
                'ng_cost': ng.get('天然气原料成本(元)', 0),
                'transport_cost': ng.get('SAF运输运营成本(元)', ng.get('MTJ运输运营成本(元)', 0)),
            },
            'green_h2': {
                # Core economic indicators
                'lcoe': green_h2['生命周期平准化成本(元/kg)'],
                'annual_cost': green_h2.get('年化平准化成本(元/kg)', green_h2['生命周期平准化成本(元/kg)']),
                'total_cost': green_h2['生命周期总成本(元)'],

                # Demand fulfillment
                'demand_fulfillment': green_h2['需求满足比例(%)'],

                # Production indicators
                'annual_production': green_h2['年产量(kg)'],
                'total_production': green_h2['20年总产量(kg)'],

                # Environmental indicators
                'carbon_intensity': green_h2['碳强度(kg CO2eq/kg SAF)'],
                'vs_jet_fuel': green_h2['相比传统航煤(%)'],
                'vs_corsia': green_h2['相比CORSIA标准(%)'],

                # Cost structure
                'saf_capex': green_h2.get('SAF工厂建设投资(元)', 0),
                'saf_opex': green_h2.get('SAF生产运营成本(元)', 0),
                'electrolyzer_capex': green_h2.get('电解槽建设投资(元)', 0),
                'h2_cost': green_h2.get('氢气制取成本(元)', 0),
                'co2_cost': green_h2.get('CO2捕获成本(元)', 0),
                'electricity_cost': green_h2.get('电力成本(元)', 0),
                'transport_cost': green_h2.get('SAF运输运营成本(元)', 0),
            }
        }

        print("Comparison metrics extraction completed!")
        print(f"  Coal-based LCOE: {self.comparison_metrics['coal']['lcoe']:.3f} yuan/kg")
        print(f"  Natural gas-based LCOE: {self.comparison_metrics['natural_gas']['lcoe']:.3f} yuan/kg")
        print(f"  Green hydrogen-based LCOE: {self.comparison_metrics['green_h2']['lcoe']:.3f} yuan/kg")

    def create_dashboard(self, output_dir):
        """
        Create comprehensive comparison dashboard

        Args:
            output_dir: Output directory path
        """
        print("\nCreating comprehensive comparison dashboard...")

        # Create large canvas
        fig = plt.figure(figsize=(22, 14))
        fig.suptitle('Coal-based vs Natural Gas-based vs Green H2-based SAF Technology Comparison',
                     fontsize=26, fontweight='bold', y=0.98)

        # Set background color
        fig.patch.set_facecolor(self.colors['background'])

        # Create grid layout
        gs = gridspec.GridSpec(3, 3, figure=fig, hspace=0.35, wspace=0.35,
                              left=0.05, right=0.95, top=0.93, bottom=0.05)

        # 1. Core metrics comparison (top left, span 2 columns)
        ax1 = fig.add_subplot(gs[0, :2])
        self._plot_core_metrics_comparison(ax1)

        # 2. Radar chart (top right)
        ax2 = fig.add_subplot(gs[0, 2], projection='polar')
        self._plot_radar_chart(ax2)

        # 3. Cost structure comparison (middle row, span 3 columns)
        ax3 = fig.add_subplot(gs[1, :])
        self._plot_cost_structure(ax3)

        # 4. Environmental impact comparison (bottom left)
        ax4 = fig.add_subplot(gs[2, 0])
        self._plot_environmental_impact(ax4)

        # 5. KPI cards (bottom middle)
        ax5 = fig.add_subplot(gs[2, 1])
        self._plot_kpi_cards(ax5)

        # 6. Technology features comparison (bottom right)
        ax6 = fig.add_subplot(gs[2, 2])
        self._plot_technology_features(ax6)

        # Save chart
        output_path = Path(output_dir) / f'technology_routes_comparison_dashboard_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
        plt.savefig(output_path, dpi=300, bbox_inches='tight',
                   facecolor=self.colors['background'])
        print(f"Dashboard saved to: {output_path}")

        plt.close()

        return output_path

    def _plot_core_metrics_comparison(self, ax):
        """Plot core metrics comparison bar chart"""
        metrics = ['LCOE\n(yuan/kg)', 'Demand\nFulfillment (%)', 'Annual Output\n(10k tons)']
        coal_values = [
            self.comparison_metrics['coal']['lcoe'],
            self.comparison_metrics['coal']['demand_fulfillment'],
            self.comparison_metrics['coal']['annual_production'] / 1e7  # Convert to 10k tons
        ]
        ng_values = [
            self.comparison_metrics['natural_gas']['lcoe'],
            self.comparison_metrics['natural_gas']['demand_fulfillment'],
            self.comparison_metrics['natural_gas']['annual_production'] / 1e7
        ]
        green_h2_values = [
            self.comparison_metrics['green_h2']['lcoe'],
            self.comparison_metrics['green_h2']['demand_fulfillment'],
            self.comparison_metrics['green_h2']['annual_production'] / 1e7
        ]

        x = np.arange(len(metrics))
        width = 0.25

        bars1 = ax.bar(x - width, coal_values, width, label='Coal-based',
                      color=self.colors['coal'], alpha=0.8, edgecolor='black', linewidth=1.5)
        bars2 = ax.bar(x, ng_values, width, label='Natural Gas-based',
                      color=self.colors['natural_gas'], alpha=0.8, edgecolor='black', linewidth=1.5)
        bars3 = ax.bar(x + width, green_h2_values, width, label='Green H2-based',
                      color=self.colors['green_h2'], alpha=0.8, edgecolor='black', linewidth=1.5)

        ax.set_xlabel('Metrics', fontsize=13, fontweight='bold')
        ax.set_ylabel('Value', fontsize=13, fontweight='bold')
        ax.set_title('Core Metrics Comparison', fontsize=15, fontweight='bold', pad=15)
        ax.set_xticks(x)
        ax.set_xticklabels(metrics, fontsize=12)
        ax.legend(fontsize=12, loc='upper right', framealpha=0.9)
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        ax.set_facecolor('white')

        # Add value labels
        for bar in bars1 + bars2 + bars3:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height:.2f}',
                   ha='center', va='bottom', fontsize=10, fontweight='bold')

    def _plot_radar_chart(self, ax):
        """Plot multi-dimensional performance radar chart"""
        categories = ['Economics', 'Environmental', 'Efficiency', 'Demand\nFulfillment', 'Resource\nUtilization']

        # Normalize indicators (0-100 score)
        coal_scores = [
            100 - (self.comparison_metrics['coal']['lcoe'] - 5) * 15,  # Lower cost is better
            100 - self.comparison_metrics['coal']['carbon_intensity'] * 20,  # Lower carbon intensity is better
            75,  # Coal gasification efficiency baseline
            self.comparison_metrics['coal']['demand_fulfillment'],
            70  # Coal resource utilization efficiency assumption
        ]

        ng_scores = [
            100 - (self.comparison_metrics['natural_gas']['lcoe'] - 5) * 15,
            100 - self.comparison_metrics['natural_gas']['carbon_intensity'] * 20,
            80,  # Natural gas conversion efficiency higher
            self.comparison_metrics['natural_gas']['demand_fulfillment'],
            75  # Natural gas utilization efficiency assumption
        ]

        green_h2_scores = [
            100 - (self.comparison_metrics['green_h2']['lcoe'] - 5) * 15,
            100 - self.comparison_metrics['green_h2']['carbon_intensity'] * 20,
            68,  # Green hydrogen comprehensive electricity conversion efficiency
            self.comparison_metrics['green_h2']['demand_fulfillment'],
            85  # Renewable energy utilization efficiency
        ]

        # Close radar chart
        angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
        coal_scores += coal_scores[:1]
        ng_scores += ng_scores[:1]
        green_h2_scores += green_h2_scores[:1]
        angles += angles[:1]

        ax.plot(angles, coal_scores, 'o-', linewidth=2, label='Coal-based',
               color=self.colors['coal'], markersize=8)
        ax.fill(angles, coal_scores, alpha=0.25, color=self.colors['coal'])

        ax.plot(angles, ng_scores, 'o-', linewidth=2, label='Natural Gas-based',
               color=self.colors['natural_gas'], markersize=8)
        ax.fill(angles, ng_scores, alpha=0.25, color=self.colors['natural_gas'])

        ax.plot(angles, green_h2_scores, 'o-', linewidth=2, label='Green H2-based',
               color=self.colors['green_h2'], markersize=8)
        ax.fill(angles, green_h2_scores, alpha=0.25, color=self.colors['green_h2'])

        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(categories, fontsize=11)
        ax.set_ylim(0, 100)
        ax.set_title('Multi-Dimensional Performance', fontsize=15, fontweight='bold', pad=20)
        ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1), fontsize=11)
        ax.grid(True, linestyle='--', alpha=0.5)

    def _plot_cost_structure(self, ax):
        """Plot cost structure comparison stacked bar chart"""
        # Coal-based cost structure
        coal_costs = {
            'SAF Plant CAPEX': self.comparison_metrics['coal']['saf_capex'],
            'SAF OPEX': self.comparison_metrics['coal']['saf_opex'],
            'Electrolyzer CAPEX': self.comparison_metrics['coal']['electrolyzer_capex'],
            'H2 Production': self.comparison_metrics['coal']['h2_cost'],
            'CO2 Capture': self.comparison_metrics['coal']['co2_cost'],
            'Coal Feedstock': self.comparison_metrics['coal']['coal_cost'],
            'Transport': self.comparison_metrics['coal']['transport_cost'],
        }

        # Natural gas-based cost structure
        ng_costs = {
            'SAF Plant CAPEX': self.comparison_metrics['natural_gas']['saf_capex'],
            'SAF OPEX': self.comparison_metrics['natural_gas']['saf_opex'],
            'Electrolyzer CAPEX': self.comparison_metrics['natural_gas']['electrolyzer_capex'],
            'H2 Production': self.comparison_metrics['natural_gas']['h2_cost'],
            'Natural Gas Feedstock': self.comparison_metrics['natural_gas']['ng_cost'],
            'Transport': self.comparison_metrics['natural_gas']['transport_cost'],
        }

        # Green hydrogen-based cost structure
        green_h2_costs = {
            'SAF Plant CAPEX': self.comparison_metrics['green_h2']['saf_capex'],
            'SAF OPEX': self.comparison_metrics['green_h2']['saf_opex'],
            'Electrolyzer CAPEX': self.comparison_metrics['green_h2']['electrolyzer_capex'],
            'H2 Production': self.comparison_metrics['green_h2']['h2_cost'],
            'CO2 Capture': self.comparison_metrics['green_h2']['co2_cost'],
            'Electricity': self.comparison_metrics['green_h2']['electricity_cost'],
            'Transport': self.comparison_metrics['green_h2']['transport_cost'],
        }

        # Calculate total costs and percentages
        coal_total = sum(coal_costs.values())
        ng_total = sum(ng_costs.values())
        green_h2_total = sum(green_h2_costs.values())

        # Convert to percentages
        coal_pcts = {k: v/coal_total*100 for k, v in coal_costs.items() if v > 0}
        ng_pcts = {k: v/ng_total*100 for k, v in ng_costs.items() if v > 0}
        green_h2_pcts = {k: v/green_h2_total*100 for k, v in green_h2_costs.items() if v > 0}

        # Prepare data
        methods = ['Coal-based', 'Natural Gas-based', 'Green H2-based']

        # Plot stacked bar chart
        colors_palette = plt.cm.Set3(np.linspace(0, 1, 12))

        # Collect all cost categories
        all_categories = set(list(coal_pcts.keys()) + list(ng_pcts.keys()) + list(green_h2_pcts.keys()))
        category_colors = {cat: colors_palette[i] for i, cat in enumerate(sorted(all_categories))}

        # Coal-based
        bottom = 0
        for category in sorted(coal_pcts.keys()):
            pct = coal_pcts[category]
            ax.barh(0, pct, left=bottom, height=0.6,
                   label=category if category not in ng_pcts and category not in green_h2_pcts else '',
                   color=category_colors[category], alpha=0.8, edgecolor='black', linewidth=0.5)
            if pct > 4:  # Only label if > 4%
                ax.text(bottom + pct/2, 0, f'{pct:.1f}%',
                       ha='center', va='center', fontsize=9, fontweight='bold')
            bottom += pct

        # Natural gas-based
        bottom = 0
        for category in sorted(ng_pcts.keys()):
            pct = ng_pcts[category]
            ax.barh(1, pct, left=bottom, height=0.6,
                   label=category if category not in coal_pcts and category not in green_h2_pcts else '',
                   color=category_colors[category], alpha=0.8, edgecolor='black', linewidth=0.5)
            if pct > 4:
                ax.text(bottom + pct/2, 1, f'{pct:.1f}%',
                       ha='center', va='center', fontsize=9, fontweight='bold')
            bottom += pct

        # Green hydrogen-based
        bottom = 0
        for category in sorted(green_h2_pcts.keys()):
            pct = green_h2_pcts[category]
            ax.barh(2, pct, left=bottom, height=0.6,
                   label=category if category not in coal_pcts and category not in ng_pcts else '',
                   color=category_colors[category], alpha=0.8, edgecolor='black', linewidth=0.5)
            if pct > 4:
                ax.text(bottom + pct/2, 2, f'{pct:.1f}%',
                       ha='center', va='center', fontsize=9, fontweight='bold')
            bottom += pct

        ax.set_yticks([0, 1, 2])
        ax.set_yticklabels(methods, fontsize=13, fontweight='bold')
        ax.set_xlabel('Cost Share (%)', fontsize=13, fontweight='bold')
        ax.set_title('Lifecycle Cost Structure Comparison', fontsize=15, fontweight='bold', pad=15)
        ax.set_xlim(0, 100)
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=10,
                 framealpha=0.9, ncol=1)
        ax.grid(axis='x', alpha=0.3, linestyle='--')
        ax.set_facecolor('white')

        # Add total cost annotations
        ax.text(102, 0, f'Total:\n{coal_total/1e8:.1f}B yuan',
               ha='left', va='center', fontsize=11, fontweight='bold',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))
        ax.text(102, 1, f'Total:\n{ng_total/1e8:.1f}B yuan',
               ha='left', va='center', fontsize=11, fontweight='bold',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))
        ax.text(102, 2, f'Total:\n{green_h2_total/1e8:.1f}B yuan',
               ha='left', va='center', fontsize=11, fontweight='bold',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))

    def _plot_environmental_impact(self, ax):
        """Plot environmental impact comparison"""
        categories = ['Carbon Intensity\n(kg CO2eq/kg)', 'vs Jet Fuel\n(%)', 'vs CORSIA\nStandard (%)']
        coal_values = [
            self.comparison_metrics['coal']['carbon_intensity'],
            self.comparison_metrics['coal']['vs_jet_fuel'],
            self.comparison_metrics['coal']['vs_corsia']
        ]
        ng_values = [
            self.comparison_metrics['natural_gas']['carbon_intensity'],
            self.comparison_metrics['natural_gas']['vs_jet_fuel'],
            self.comparison_metrics['natural_gas']['vs_corsia']
        ]
        green_h2_values = [
            self.comparison_metrics['green_h2']['carbon_intensity'],
            self.comparison_metrics['green_h2']['vs_jet_fuel'],
            self.comparison_metrics['green_h2']['vs_corsia']
        ]

        x = np.arange(len(categories))
        width = 0.25

        bars1 = ax.bar(x - width, coal_values, width, label='Coal-based',
                      color=self.colors['coal'], alpha=0.8, edgecolor='black', linewidth=1.5)
        bars2 = ax.bar(x, ng_values, width, label='Natural Gas-based',
                      color=self.colors['natural_gas'], alpha=0.8, edgecolor='black', linewidth=1.5)
        bars3 = ax.bar(x + width, green_h2_values, width, label='Green H2-based',
                      color=self.colors['green_h2'], alpha=0.8, edgecolor='black', linewidth=1.5)

        ax.set_xlabel('Environmental Metrics', fontsize=12, fontweight='bold')
        ax.set_ylabel('Value', fontsize=12, fontweight='bold')
        ax.set_title('Environmental Impact Comparison', fontsize=14, fontweight='bold', pad=12)
        ax.set_xticks(x)
        ax.set_xticklabels(categories, fontsize=10)
        ax.legend(fontsize=10, loc='upper right', framealpha=0.9)
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        ax.set_facecolor('white')

        # Add value labels
        for bar in bars1 + bars2 + bars3:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height:.2f}',
                   ha='center', va='bottom', fontsize=9, fontweight='bold')

    def _plot_kpi_cards(self, ax):
        """Plot KPI cards"""
        ax.axis('off')

        # Find best options
        lcoes = {
            'Coal-based': self.comparison_metrics['coal']['lcoe'],
            'Natural Gas-based': self.comparison_metrics['natural_gas']['lcoe'],
            'Green H2-based': self.comparison_metrics['green_h2']['lcoe']
        }
        carbon_intensities = {
            'Coal-based': self.comparison_metrics['coal']['carbon_intensity'],
            'Natural Gas-based': self.comparison_metrics['natural_gas']['carbon_intensity'],
            'Green H2-based': self.comparison_metrics['green_h2']['carbon_intensity']
        }

        best_lcoe = min(lcoes, key=lcoes.get)
        best_carbon = min(carbon_intensities, key=carbon_intensities.get)

        # KPI information
        kpis = [
            {
                'title': 'Cost Advantage',
                'winner': best_lcoe,
                'values': lcoes,
                'unit': 'yuan/kg'
            },
            {
                'title': 'Carbon Advantage',
                'winner': best_carbon,
                'values': carbon_intensities,
                'unit': 'kg CO2eq/kg'
            }
        ]

        y_pos = 0.85
        for kpi in kpis:
            # Title
            ax.text(0.5, y_pos, kpi['title'], ha='center', va='top',
                   fontsize=14, fontweight='bold',
                   bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.5))

            # Display each technology route value
            y_offset = 0.15
            for tech, value in kpi['values'].items():
                color = 'green' if tech == kpi['winner'] else 'gray'
                marker = ' ★' if tech == kpi['winner'] else ''
                ax.text(0.5, y_pos - y_offset, f"{tech}: {value:.2f} {kpi['unit']}{marker}",
                       ha='center', va='top', fontsize=11, color=color, fontweight='bold')
                y_offset += 0.12

            y_pos -= 0.5

        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_title('Key Performance Indicators', fontsize=14, fontweight='bold')

    def _plot_technology_features(self, ax):
        """Plot technology features comparison"""
        ax.axis('off')

        features = {
            'Coal-based': [
                'Feedstock: Coal',
                'Process: Gasification + Green H2 + CO2',
                'Advantage: Abundant coal resources',
                'Challenge: Carbon capture cost',
            ],
            'Natural Gas-based': [
                'Feedstock: Natural gas',
                'Process: Reforming + Synthesis',
                'Advantage: Mature technology',
                'Challenge: Natural gas price volatility',
            ],
            'Green H2-based': [
                'Feedstock: Renewable electricity',
                'Process: Electrolysis + CO2 synthesis',
                'Advantage: Zero carbon emissions',
                'Challenge: High electricity cost',
            ]
        }

        y_pos = 0.9
        for tech, items in features.items():
            color = self.colors[tech.replace('Coal-based', 'coal').replace('Natural Gas-based', 'natural_gas').replace('Green H2-based', 'green_h2')]
            ax.text(0.5, y_pos, tech, ha='center', va='top',
                   fontsize=13, fontweight='bold', color=color,
                   bbox=dict(boxstyle='round', facecolor=color, alpha=0.2))

            y_offset = 0.1
            for item in items:
                ax.text(0.5, y_pos - y_offset, item,
                       ha='center', va='top', fontsize=9)
                y_offset += 0.06

            y_pos -= 0.32

        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_title('Technology Features Comparison', fontsize=14, fontweight='bold')


def find_latest_result_files():
    """
    Automatically find the latest optimization result files for all three technology routes

    Returns:
        (coal_file, ng_file, green_h2_file): Latest coal, natural gas, green hydrogen result files
    """
    base_dir = Path(__file__).parent.parent / 'products' / 'supply_chain_optimization'

    # Find result directories for each technology route
    coal_dir = base_dir / 'coal_hydrogen_saf_optimization' / 'results'
    ng_dir = base_dir / 'natural_gas_supply_chain_optimization' / 'results'
    green_h2_dir = base_dir / 'green_hydrogen_supply_chain_optimization' / 'results'

    # Find latest files
    coal_files = sorted(glob.glob(str(coal_dir / 'optimization_summary_*.csv')),
                       key=lambda x: Path(x).stat().st_mtime, reverse=True)
    ng_files = sorted(glob.glob(str(ng_dir / 'optimization_summary_*.csv')),
                     key=lambda x: Path(x).stat().st_mtime, reverse=True)
    green_h2_files = sorted(glob.glob(str(green_h2_dir / 'optimization_summary_*.csv')),
                           key=lambda x: Path(x).stat().st_mtime, reverse=True)

    if not coal_files:
        raise FileNotFoundError(f"Coal-based optimization result file not found: {coal_dir}")
    if not ng_files:
        raise FileNotFoundError(f"Natural gas-based optimization result file not found: {ng_dir}")
    if not green_h2_files:
        raise FileNotFoundError(f"Green hydrogen-based optimization result file not found: {green_h2_dir}")

    coal_file = Path(coal_files[0])
    ng_file = Path(ng_files[0])
    green_h2_file = Path(green_h2_files[0])

    print(f"\nLatest result files found:")
    print(f"  Coal-based: {coal_file.name}")
    print(f"  Natural gas-based: {ng_file.name}")
    print(f"  Green hydrogen-based: {green_h2_file.name}")

    return coal_file, ng_file, green_h2_file


def main():
    """Main function"""
    print("="*70)
    print("Coal-based vs Natural Gas-based vs Green H2-based SAF Technology Comparison")
    print("="*70)

    # Initialize visualizer
    visualizer = TechnologyRoutesComparisonVisualizer()

    # Automatically find latest result files
    try:
        coal_file, ng_file, green_h2_file = find_latest_result_files()
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return

    # Load data
    visualizer.load_data(coal_file, ng_file, green_h2_file)

    # Extract comparison metrics
    visualizer.extract_comparison_metrics()

    # Create output directory
    output_dir = Path(__file__).parent / 'comparison_results'
    output_dir.mkdir(exist_ok=True)

    # Generate comparison dashboard
    dashboard_path = visualizer.create_dashboard(output_dir)

    print("\n" + "="*70)
    print("Visualization completed!")
    print(f"Dashboard saved to: {dashboard_path}")
    print("="*70)


if __name__ == '__main__':
    main()
