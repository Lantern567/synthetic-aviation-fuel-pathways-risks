# -*- coding: utf-8 -*-
"""
Polar Stacked Bar Chart Visualization Script (CO2 Emissions)

Features:
- Create polar stacked bar charts for 13 SAF supply chain optimization scenarios
- Show detailed emission source breakdown for each scenario
- Designed with academic paper style

Author: Claude Code (Modified)
Created: 2026-01-14
"""

import json
import glob
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple
import logging

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib import rcParams
from matplotlib.patches import Patch
import matplotlib.patches as mpatches

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PolarCarbonStackedBarVisualizer:
    """Carbon Emissions Polar Stacked Bar Chart Visualizer"""

    def __init__(self, output_dir: str = None):
        """
        Initialize the visualizer

        Args:
            output_dir: Output directory
        """
        if output_dir is None:
            base_dir = Path(__file__).parent.parent.parent.parent
            output_dir = base_dir / "products" / "supply_chain_optimization" / "visualization" / "results"

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Create timestamped subdirectory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = self.output_dir / f"polar_carbon_chart_{timestamp}"
        self.session_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Output directory: {self.session_dir}")

        # Get project root directory
        project_root = Path(__file__).parent.parent.parent.parent

        # 13 Scenarios Configuration
        # Arranged in order: Grey -> Blue -> Green
        self.scenarios = {
            # === Grey Group ===
            'CTL': {
                'name_cn': 'CTL', # Kept simplified
                'label': 'CTL',
                'group': 'Grey',
                'carbon_pattern': str(project_root / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/carbon_emissions_detailed_*.json')
            },
            'CTL-BH': {
                'name_cn': 'CTL-BH',
                'label': 'CTL-BH',
                'group': 'Grey',
                'carbon_pattern': str(project_root / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/byproduct_hydrogen/carbon_emissions_detailed_*.json')
            },

            # === Blue Group ===
            'CCU-BH-MTJ': {
                'name_cn': 'CCU-BH-MTJ',
                'label': 'CCU-BH-MTJ',
                'group': 'Blue',
                'carbon_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/two_step/carbon_emissions_detailed_*.json')
            },
            'CCU-BH-FT': {
                'name_cn': 'CCU-BH-FT',
                'label': 'CCU-BH-FT',
                'group': 'Blue',
                'carbon_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/one_step/carbon_emissions_detailed_*.json')
            },
            'DAC-BH-MTJ': {
                'name_cn': 'DAC-BH-MTJ',
                'label': 'DAC-BH-MTJ',
                'group': 'Blue',
                'carbon_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/two_step/carbon_emissions_detailed_*.json')
            },
            'DAC-BH-FT': {
                'name_cn': 'DAC-BH-FT',
                'label': 'DAC-BH-FT',
                'group': 'Blue',
                'carbon_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/one_step/carbon_emissions_detailed_*.json')
            },
            'GTL-BH-MTJ': {
                'name_cn': 'GTL-BH-MTJ',
                'label': 'GTL-BH-MTJ',
                'group': 'Blue',
                'carbon_pattern': str(project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/byproduct_hydrogen/byproduct_hydrogen/two_step/carbon_emissions_detailed_*.json')
            },
            'GTL-GH-MTJ': {
                'name_cn': 'GTL-GH-MTJ',
                'label': 'GTL-GH-MTJ',
                'group': 'Blue',
                'carbon_pattern': str(project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/carbon_emissions_detailed_*.json')
            },
            'GTL-GH-FT': {
                'name_cn': 'GTL-GH-FT',
                'label': 'GTL-GH-FT',
                'group': 'Blue',
                'carbon_pattern': str(project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/ft_one_step/carbon_emissions_detailed_*.json')
            },

            # === Green Group ===
            'DAC-GH-MTJ': {
                'name_cn': 'DAC-GH-MTJ',
                'label': 'DAC-GH-MTJ',
                'group': 'Green',
                'carbon_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/two_step/carbon_emissions_detailed_*.json')
            },
            'DAC-GH-FT': {
                'name_cn': 'DAC-GH-FT',
                'label': 'DAC-GH-FT',
                'group': 'Green',
                'carbon_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/one_step/carbon_emissions_detailed_*.json')
            },
            'CCU-GH-MTJ': {
                'name_cn': 'CCU-GH-MTJ',
                'label': 'CCU-GH-MTJ',
                'group': 'Green',
                'carbon_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/two_step/carbon_emissions_detailed_*.json')
            },
            'CCU-GH-FT': {
                'name_cn': 'CCU-GH-FT',
                'label': 'CCU-GH-FT',
                'group': 'Green',
                'carbon_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/one_step/carbon_emissions_detailed_*.json')
            },
        }

        # 12 Emission Categories - Corresponding to positive emissions sources
        self.emission_categories = {
            'Raw Mat. & Mining': {
                'name_en': 'Raw Mat. & Mining',
                'keys': ['coal_mining'],
                'color': '#8DD3C7'  # Teal
            },
            'Process Direct': {
                'name_en': 'Process Direct',
                'keys': ['coal_gasification_direct', 'coal_co2_fugitive'],
                'color': '#FFFFB3'  # Light Yellow
            },
            'H2 Production': {
                'name_en': 'H2 Production',
                'keys': ['h2_production'],
                'color': '#BEBADA'  # Pastel Purple
            },
            'SAF/Fuel Prod.': {
                'name_en': 'SAF/Fuel Prod.',
                'keys': ['saf_synthesis_energy', 'methanol_to_saf', 'coal_gasification_energy'],
                'color': '#FB8072'  # Salmon
            },
            'CO2 Capture Op.': {
                'name_en': 'CO2 Capture Op.',
                'keys': ['co2_capture_energy'],
                'color': '#80B1D3'  # Pastel Blue
            },
            'Facility Embodied': {
                'name_en': 'Facility Embodied',
                'keys': ['saf_facility', 'electrolyzer_facility', 'dac_equipment'],
                'color': '#FDB462'  # Pastel Orange
            },
            'H2 Pipeline': {
                'name_en': 'H2 Pipeline',
                'keys': ['h2_pipeline_transport', 'hydrogen_pipeline_operation'],
                'color': '#B3DE69'  # Pastel Green
            },
            'H2 Storage': {
                'name_en': 'H2 Storage',
                'keys': ['h2_storage'],
                'color': '#FCCDE5'  # Pastel Pink
            },
            'CO2 Transport': {
                'name_en': 'CO2 Transport',
                'keys': ['co2_pipeline_transport', 'co2_truck_transport', 'co2_transport'],
                'color': '#D9D9D9'  # Light Grey
            },
            'Fuel Transport': {
                'name_en': 'Fuel Transport',
                'keys': ['mtj_transport', 'coal_transport'],
                'color': '#BC80BD'  # Pastel Violet
            },
            'Fuel Storage': {
                'name_en': 'Fuel Storage',
                'keys': ['mtj_storage'],
                'color': '#CCEBC5'  # Pale Green
            },
            'Other / Elec.': {
                'name_en': 'Other / Elec.',
                'keys': ['dac_grid_electricity', 'electricity_cost'],
                'color': '#FFED6F'  # Soft Yellow
            }
        }

        # Group Colors - Outer ring colors
        self.group_colors = {
            'Grey': '#9E9E9E',   # Grey
            'Blue': '#5C9BD5',   # Soft Blue
            'Green': '#70AD47'   # Soft Green
        }

        # Data storage
        self.data = {}

    def draw_curved_text(self, ax, text, radius, center_angle, fontsize=20, color='#333333'):
        """
        Draw text curved along an arc
        """
        center_angle = center_angle % (2 * np.pi)
        
        char_angle_width = 0.08 * (20 / radius) * fontsize * 0.8
        
        total_angle = len(text) * char_angle_width
        
        # Determine whether to flip text (left semicircle / bottom)
        is_flipped = False
        if 90 < np.degrees(center_angle) < 270:
            is_flipped = True
            
        if is_flipped:
            start_angle = center_angle - total_angle / 2
            char_step = char_angle_width 
            base_rotation = 90
        else:
            start_angle = center_angle + total_angle / 2
            char_step = -char_angle_width
            base_rotation = -90
            
        curr_angle = start_angle
        
        for char in text:
            # Calculate rotation
            deg = np.degrees(curr_angle)
            rotation = deg + base_rotation
            
            ax.text(
                curr_angle, radius, char,
                ha='center', va='center',
                fontsize=fontsize,
                fontweight='normal',
                color=color,
                rotation=rotation,
                rotation_mode='anchor'
            )
            curr_angle += char_step

    def load_data(self):
        """Load data for 13 scenarios"""
        logger.info("=" * 80)
        logger.info("Loading Scenario Data (Carbon)")
        logger.info("=" * 80)

        for scenario_name, config in self.scenarios.items():
            logger.info(f"\\nLoading: {scenario_name}")

            carbon_files = sorted(glob.glob(config['carbon_pattern']), reverse=True)

            if not carbon_files:
                logger.warning(f"  ? File not found: {config['carbon_pattern']}")
                continue

            solution_path = Path(carbon_files[0])
            logger.info(f"  Using file: {solution_path.name}")

            with open(solution_path, 'r', encoding='utf-8') as f:
                solution_data = json.load(f)

            self.data[scenario_name] = {
                'solution': solution_data, # Use 'solution' to store carbon data
                'config': config
            }

            total_emissions = solution_data.get('by_stage', {}).get('total_emissions', 0) / 1e6
            logger.info(f"  ? Net Emissions: {total_emissions:.2f} M kg")

        logger.info("\\n" + "=" * 80)
        logger.info(f"Data loading complete - Loaded {len(self.data)} scenarios")
        logger.info("=" * 80)

    def extract_emission_data(self) -> Tuple[List[str], Dict[str, List[float]], List[str]]:
        """
        Extract emission data

        Returns:
            Scenario labels, Emission data dictionary, Scenario list
        """
        scenarios_list = list(self.scenarios.keys()) # Keep consistent order defined in self.scenarios
        # Filter available
        scenarios_list = [s for s in scenarios_list if s in self.data]
        
        labels = [self.data[s]['config']['label'] for s in scenarios_list]

        # Extract data for each category (Unit: Million kg - M kg)
        emission_data = {cat: [] for cat in self.emission_categories.keys()}

        for scenario in scenarios_list:
            detailed = self.data[scenario]['solution'].get('detailed', {})

            for cat, cat_config in self.emission_categories.items():
                total = sum(detailed.get(key, 0) for key in cat_config['keys']) / 1e6 # Convert to Million kg
                if total < 0: total = 0
                emission_data[cat].append(total)

        return labels, emission_data, scenarios_list

    def get_scenario_groups(self, scenarios_list: List[str]) -> List[str]:
         """Get grouping list for scenarios"""
         return [self.scenarios[s]['group'] for s in scenarios_list]

    def create_polar_stacked_bar_chart(self):
        """Create Polar Stacked Bar Chart - Unified Style"""
        logger.info("\\nGenerating Polar Stacked Bar Chart (CO2)...")

        # Configure fonts
        plt.rcParams['font.family'] = ['Times New Roman', 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False

        # Extract data
        labels, emission_data, scenarios_list = self.extract_emission_data()
        groups = self.get_scenario_groups(scenarios_list)
        n_scenarios = len(labels)

        if n_scenarios == 0:
            logger.error("No scenario data available")
            return

        # Create figure
        # Increase size for large fonts
        fig, ax = plt.subplots(figsize=(16, 16), subplot_kw=dict(projection='polar'))
        fig.patch.set_facecolor('white')
        ax.set_facecolor('white')

        # Calculate max value for scaling
        # Calculate max value for scaling
        total_emissions = np.zeros(n_scenarios)
        for cat_name in self.emission_categories:
            total_emissions += np.array(emission_data[cat_name])
        real_max_val = max(total_emissions)
        if real_max_val == 0: real_max_val = 1
        
        # === Data Normalization ===
        # Scale data to a target geometry size (e.g. 500) so that generic text spacing parameters work consistently.
        TARGET_GEOMETRY_MAX = 500.0
        scale_factor = TARGET_GEOMETRY_MAX / real_max_val
        
        # Geometry Parameters (Scaled)
        INNER_RADIUS = real_max_val * scale_factor * 0.35  # Inner radius (approx 175)
        
        # === Group Angle Calculation Logic ===
        gap_angle = np.pi / 20  # Gap between groups (~9 deg)
        
        # Count groups
        unique_groups = []
        for g in groups:
            if g not in unique_groups:
                unique_groups.append(g)
        n_groups = len(unique_groups)
        
        total_gap = gap_angle * n_groups
        available_angle = 2 * np.pi - total_gap  # Available angle
        
        # Angle per scenario
        angle_per_scenario = available_angle / n_scenarios
        
        # Bar width
        width = angle_per_scenario * 0.95 

        # Calculate angle position for each scenario
        angles = []
        current_angle = np.pi / 2  # Start from top (90 deg)
        
        # Record start/end angles for each group (for outer ring)
        group_angular_ranges = {}
        
        current_group = None
        temp_angles = [] # Temp store angles for current group

        for i, (label, group) in enumerate(zip(labels, groups)):
            # Detect new group (exclude first iteration)
            if current_group is not None and group != current_group:
                # Record previous group range
                max_ang = max(temp_angles) + angle_per_scenario/2
                min_ang = min(temp_angles) - angle_per_scenario/2
                group_angular_ranges[current_group] = (min_ang, max_ang)
                temp_angles = []

                # Add gap
                current_angle -= gap_angle

            if current_group != group:
                current_group = group
            
            angles.append(current_angle)
            temp_angles.append(current_angle)
            
            current_angle -= angle_per_scenario

        # Handle last group
        if temp_angles:
             max_ang = max(temp_angles) + angle_per_scenario/2
             min_ang = min(temp_angles) - angle_per_scenario/2
             group_angular_ranges[current_group] = (min_ang, max_ang)

        angles = np.array(angles)
        
        # Draw stacked bars
        bottom = np.zeros(n_scenarios) + INNER_RADIUS

        for cat_name, cat_config in self.emission_categories.items():
            # Apply scaling to data values
            values = np.array(emission_data[cat_name]) * scale_factor
            bars = ax.bar(
                angles,
                values,
                width=width,
                bottom=bottom,
                label=cat_config['name_en'],
                color=cat_config['color'],
                edgecolor='white',
                linewidth=0.3,
                alpha=0.9
            )
            bottom += values

        # === Draw Outer Ring (Group Ring) ===
        # Use scaled maximum for geometry
        scaled_max = real_max_val * scale_factor
        
        RING_GAP = scaled_max * 0.02 # Gap
        RING_WIDTH = scaled_max * 0.12 # Width
        outer_ring_start = max(bottom) + RING_GAP
        
        # Draw
        for group_name, (min_ang, max_ang) in group_angular_ranges.items():
            # Calculate span
            center_angle = (min_ang + max_ang) / 2
            span_angle = max_ang - min_ang
            
            # Draw arc
            ax.bar(
                x=center_angle,
                height=RING_WIDTH,
                bottom=outer_ring_start,
                width=span_angle, 
                color=self.group_colors.get(group_name, '#999999'),
                alpha=0.8,
                edgecolor='none'
            )
            
            # Add Group Label
            deg = np.degrees(center_angle)
            if deg < 0: deg += 360
            
            # Tangential rotation
            rotation = deg - 90
            
            # Flip text on the left/bottom side to be readable
            # Range: 90 to 270 degrees
            if 90 < deg < 270:
                rotation += 180

            ax.text(
                center_angle, outer_ring_start + RING_WIDTH/2, group_name,
                ha='center', va='center',
                fontsize=28, fontweight='bold',
                color='white',
                rotation=rotation,
                rotation_mode='anchor'
            )

        # Styles
        # 1. Remove default ticks
        ax.set_xticks([])
        
        # 2. Set radial ticks
        # Calculate scale based on REAL values
        tick_max = real_max_val # Approx max data value
        
        # Dynamic tick step calculation (for Real Values)
        if tick_max > 1000:
             tick_step = 500
        elif tick_max > 100:
             tick_step = 100
        else:
             tick_step = 10 
             
        simple_ticks = np.arange(0, tick_max + tick_step, tick_step)
        if simple_ticks[-1] > tick_max * 1.2:
            simple_ticks = simple_ticks[:-1]
            
        # Map ticks to Scaled Radius
        # Real Value -> Scaled Value + Inner Radius
        actual_ticks = (simple_ticks * scale_factor) + INNER_RADIUS
        
        ax.set_yticks(actual_ticks)
        ax.set_yticklabels([])
        
        ax.yaxis.grid(True, linestyle='--', alpha=0.5, color='#aaaaaa', linewidth=0.8, dashes=(4, 4))
        ax.xaxis.grid(False)
        ax.spines['polar'].set_visible(False)

        # 3. Add radial tick labels (at top)
        tick_angle = np.pi / 2 
        for val, radius in zip(simple_ticks[1:], actual_ticks[1:]): 
            if val <= tick_max * 1.1:
                ax.text(
                    tick_angle, radius, f"{int(val)}",
                    ha='center', va='center',
                    fontsize=22, color='#666666',
                    fontweight='bold',
                    bbox=dict(facecolor='white', edgecolor='none', alpha=0.7, pad=0.5)
                )

        # 4. Scenario Labels (Outermost)
        label_radius = outer_ring_start + RING_WIDTH * 1.5
        
        for angle, label in zip(angles, labels):
            self.draw_curved_text(ax, label, label_radius, angle, fontsize=24, color='#333333')

        # 5. Legend
        handles, _ = ax.get_legend_handles_labels()
        emission_handles = handles[:len(self.emission_categories)]
        
        cost_legend = ax.legend(
            handles=emission_handles,
            labels=list(self.emission_categories.keys()), 
            loc='upper left',
            bbox_to_anchor=(1.15, 1.0), 
            fontsize=24,
            title='Emission Sources',
            title_fontsize=26,
            frameon=False,
            labelspacing=0.8
        )
        cost_legend.get_title().set_fontweight('bold')

        # 6. Title
        ax.text(
            0, 0, 'Emissions\n(M kg CO2)',
            ha='center', va='center',
            fontsize=24, fontweight='bold',
            color='#555555'
        )

        plt.tight_layout()

        # Save
        output_path = self.session_dir / "polar_carbon_stacked_bar_chart.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
        logger.info(f"  ? Saved image: {output_path}")

        # Save latest copy
        root_output = self.output_dir / "polar_carbon_stacked_bar_chart_latest.png"
        plt.savefig(root_output, dpi=300, bbox_inches='tight', facecolor='white')
        logger.info(f"  ? Saved latest version: {root_output}")

        plt.close()

        return output_path

    def run_all_visualizations(self):
        """Run all visualizations"""
        logger.info("\\n" + "=" * 80)
        logger.info("Starting Visualization Generation")
        logger.info("=" * 80)

        # Generate Polar Chart
        self.create_polar_stacked_bar_chart()

        logger.info("\\n" + "=" * 80)
        logger.info("? All visualizations completed")
        logger.info(f"? Output directory: {self.session_dir}")
        logger.info("=" * 80)


def main():
    """Main function"""
    logger.info("=" * 80)
    logger.info("Polar Stacked Bar Chart Visualization Script (CO2)")
    logger.info("=" * 80)

    # Create Visualizer
    visualizer = PolarCarbonStackedBarVisualizer()

    # Load Data
    visualizer.load_data()

    # Check data sufficiency
    if len(visualizer.data) < 2:
        logger.error(f"? Insufficient data: found {len(visualizer.data)} scenarios")
        logger.error("  Please run ecosystem optimizers first")
        return

    # Run
    visualizer.run_all_visualizations()

    logger.info("\\n? Execution Successful")


if __name__ == "__main__":
    main()
