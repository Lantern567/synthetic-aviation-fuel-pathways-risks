# -*- coding: utf-8 -*-
"""
Grouped Percentage Polar Stacked Bar Chart Visualization Script (CO2 Emissions)

Features:
- Create grouped percentage polar stacked bar charts for 13 SAF supply chain optimization scenarios
- Grouped by Grey/Blue/Green categories
- Emision composition normalized to percentages (100%)

Author: Claude Code (Modified)
Created: 2026-01-14
"""

import json
import glob
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, OrderedDict
from collections import OrderedDict as OD
import logging

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib import rcParams
from matplotlib.patches import Patch, Arc
import matplotlib.patches as mpatches

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class GroupedPolarCarbonPercentageVisualizer:
    """Grouped Percentage Polar Stacked Bar Chart Visualizer (Carbon Emissions)"""

    def __init__(self, output_dir: str = None):
        """Initialize the visualizer"""
        if output_dir is None:
            base_dir = Path(__file__).parent.parent.parent.parent
            output_dir = base_dir / "products" / "supply_chain_optimization" / "visualization" / "results"

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = self.output_dir / f"polar_carbon_grouped_{timestamp}"
        self.session_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Output directory: {self.session_dir}")

        project_root = Path(__file__).parent.parent.parent.parent

        # Define Scenario Mapping: Label -> Data path
        # Grouped by Grey/Blue/Green
        self.scenario_groups = OD([
            ('Grey', OD([
                ('CTL', {
                    'full_name': 'Coal-to-Liquids Baseline',
                    'carbon_pattern': str(project_root / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/carbon_emissions_detailed_*.json')
                }),
                ('CTL-BH', {
                    'full_name': 'Coal-to-Liquids with By-product H2',
                    'carbon_pattern': str(project_root / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/byproduct_hydrogen/carbon_emissions_detailed_*.json')
                }),
            ])),
            ('Blue', OD([
                ('CCU-BH-MTJ', {
                    'full_name': 'CCU with By-product H2 - MTJ',
                    'carbon_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/two_step/carbon_emissions_detailed_*.json')
                }),
                ('CCU-BH-FT', {
                    'full_name': 'CCU with By-product H2 - FT',
                    'carbon_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/one_step/carbon_emissions_detailed_*.json')
                }),
                ('DAC-BH-MTJ', {
                    'full_name': 'DAC with By-product H2 - MTJ',
                    'carbon_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/two_step/carbon_emissions_detailed_*.json')
                }),
                ('DAC-BH-FT', {
                    'full_name': 'DAC with By-product H2 - FT',
                    'carbon_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/one_step/carbon_emissions_detailed_*.json')
                }),
                ('GTL-BH-MTJ', {
                    'full_name': 'GTL with By-product H2 - MTJ',
                    'carbon_pattern': str(project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/byproduct_hydrogen/byproduct_hydrogen/two_step/carbon_emissions_detailed_*.json')
                }),
                ('GTL-GH-MTJ', {
                    'full_name': 'GTL with Green H2 - MTJ',
                    'carbon_pattern': str(project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/carbon_emissions_detailed_*.json')
                }),
                ('GTL-GH-FT', {
                    'full_name': 'GTL with Green H2 - FT',
                    'carbon_pattern': str(project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/ft_one_step/carbon_emissions_detailed_*.json')
                }),
            ])),
            ('Green', OD([
                ('DAC-GH-MTJ', {
                    'full_name': 'DAC with Green H2 - MTJ',
                    'carbon_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/two_step/carbon_emissions_detailed_*.json')
                }),
                ('DAC-GH-FT', {
                    'full_name': 'DAC with Green H2 - FT',
                    'carbon_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/one_step/carbon_emissions_detailed_*.json')
                }),
                ('CCU-GH-MTJ', {
                    'full_name': 'CCU with Green H2 - MTJ',
                    'carbon_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/two_step/carbon_emissions_detailed_*.json')
                }),
                ('CCU-GH-FT', {
                    'full_name': 'CCU with Green H2 - FT',
                    'carbon_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/one_step/carbon_emissions_detailed_*.json')
                }),
            ])),
        ])

        # 12 Emission Categories
        self.emission_categories = OD([
            ('Raw Mat. & Mining', {
                'keys': ['coal_mining'],
                'color': '#8DD3C7'  # Teal
            }),
            ('Process Direct', {
                'keys': ['coal_gasification_direct', 'coal_co2_fugitive'],
                'color': '#FFFFB3'  # Light Yellow
            }),
            ('H2 Production', {
                'keys': ['h2_production'],
                'color': '#BEBADA'  # Pastel Purple
            }),
            ('SAF/Fuel Prod.', {
                'keys': ['saf_synthesis_energy', 'methanol_to_saf', 'coal_gasification_energy'],
                'color': '#FB8072'  # Salmon
            }),
            ('CO2 Capture Op.', {
                'keys': ['co2_capture_energy'],
                'color': '#80B1D3'  # Pastel Blue
            }),
            ('Facility Embodied', {
                'keys': ['saf_facility', 'electrolyzer_facility', 'dac_equipment'],
                'color': '#FDB462'  # Pastel Orange
            }),
            ('H2 Pipeline', {
                'keys': ['h2_pipeline_transport', 'hydrogen_pipeline_operation'],
                'color': '#B3DE69'  # Pastel Green
            }),
            ('H2 Storage', {
                'keys': ['h2_storage'],
                'color': '#FCCDE5'  # Pastel Pink
            }),
            ('CO2 Transport', {
                'keys': ['co2_pipeline_transport', 'co2_truck_transport', 'co2_transport'],
                'color': '#D9D9D9'  # Light Grey
            }),
            ('Fuel Transport', {
                'keys': ['mtj_transport', 'coal_transport'],
                'color': '#BC80BD'  # Pastel Violet
            }),
            ('Fuel Storage', {
                'keys': ['mtj_storage'],
                'color': '#CCEBC5'  # Pale Green
            }),
            ('Other / Elec.', {
                'keys': ['dac_grid_electricity', 'electricity_cost'],
                'color': '#FFED6F'  # Soft Yellow
            }),
        ])

        # Group Colors
        self.group_colors = {
            'Grey': '#9E9E9E',   # Grey
            'Blue': '#5C9BD5',   # Soft Blue
            'Green': '#70AD47'   # Soft Green
        }

        self.data = {}
        
    def draw_curved_text(self, ax, text, radius, center_angle, fontsize=20, color='#333333'):
        """
        Draw text curved along an arc
        """
        center_angle = center_angle % (2 * np.pi)
        
        char_angle_width = 0.06 * (20 / radius) * fontsize * 0.8
        
        total_angle = len(text) * char_angle_width
        
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
        """Load data for all scenarios"""
        logger.info("=" * 80)
        logger.info("Loading Scenario Data (Carbon)")
        logger.info("=" * 80)

        for group_name, scenarios in self.scenario_groups.items():
            logger.info(f"\\n--- Group: {group_name} ---")
            for scenario_label, config in scenarios.items():
                logger.info(f"Loading: {scenario_label} ({config['full_name']})")

                carbon_files = sorted(glob.glob(config['carbon_pattern']), reverse=True)

                if not carbon_files:
                    logger.warning(f"  ? File not found: {config['carbon_pattern']}")
                    continue

                solution_path = Path(carbon_files[0])
                with open(solution_path, 'r', encoding='utf-8') as f:
                    solution_data = json.load(f)

                self.data[scenario_label] = {
                    'solution': solution_data, 
                    'group': group_name,
                    'config': config
                }

                total_emissions = solution_data.get('by_stage', {}).get('total_emissions', 0) / 1e6
                logger.info(f"  ? Net Emissions: {total_emissions:.2f} M kg CO2")

        logger.info(f"\\nSuccessfully loaded {len(self.data)} scenarios")

    def extract_percentage_data(self) -> Tuple[List[str], List[str], Dict[str, List[float]]]:
        """Extract percentage data"""
        labels = []
        groups = []
        emission_data = {cat: [] for cat in self.emission_categories.keys()}

        for group_name, scenarios in self.scenario_groups.items():
            for scenario_label in scenarios.keys():
                if scenario_label not in self.data:
                    continue

                labels.append(scenario_label)
                groups.append(group_name)

                detailed = self.data[scenario_label]['solution'].get('detailed', {})

                # Calculate absolute values for each emission category
                # Note: Only positive emissions counted for distribution, ignoring credits for chart
                category_values = {}
                total_gross = 0
                for cat, cat_config in self.emission_categories.items():
                    val = sum(detailed.get(key, 0) for key in cat_config['keys'])
                    if val < 0: val = 0 
                    category_values[cat] = val
                    total_gross += val

                # Convert to percentage
                for cat in self.emission_categories.keys():
                    if total_gross > 0:
                        percentage = (category_values[cat] / total_gross) * 100
                    else:
                        percentage = 0
                    emission_data[cat].append(percentage)

        return labels, groups, emission_data

    def create_grouped_polar_chart(self):
        """Create Grouped Percentage Polar Stacked Bar Chart"""
        logger.info("\\nGenerating Grouped Percentage Polar Stacked Bar Chart (CO2)...")

        # Config fonts
        plt.rcParams['font.family'] = ['Times New Roman', 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False

        labels, groups, emission_data = self.extract_percentage_data()
        n_scenarios = len(labels)

        if n_scenarios == 0:
            logger.error("No scenario data available")
            return

        # Figure setup
        fig, ax = plt.subplots(figsize=(16, 16), subplot_kw=dict(projection='polar'))
        fig.patch.set_facecolor('white')
        ax.set_facecolor('white')

        # Geometry Parameters
        # Geometry Parameters (Scaled to match Stacked Chart Dimensions)
        EQUIV_MAX_COST = 400.0
        scale_factor = EQUIV_MAX_COST / 100.0 # 4.0

        INNER_RADIUS = EQUIV_MAX_COST * 0.35      # 140
        BAR_LIMIT = EQUIV_MAX_COST                # 400
        RING_GAP = EQUIV_MAX_COST * 0.02          # 8
        RING_WIDTH = EQUIV_MAX_COST * 0.12        # 48
         
        # Radial positions
        outer_ring_start = INNER_RADIUS + BAR_LIMIT + RING_GAP
          
        # Angular calculations for groups
        gap_angle = np.pi / 20  # Gap between groups (~9 deg)
        n_groups = len(set(groups))
        
        # Calculate angular space
        total_gap = gap_angle * n_groups
        available_angle = 2 * np.pi - total_gap
        angle_per_scenario = available_angle / n_scenarios
        width = angle_per_scenario * 0.95

        # Calculate angles
        angles = []
        current_angle = np.pi / 2 # Top
        
        # Ranges for group ring
        group_angular_ranges = {}
        temp_angles = []
        current_group = None

        for i, (label, group) in enumerate(zip(labels, groups)):
            if current_group is not None and group != current_group:
                # Save previous group range
                max_ang = max(temp_angles) + angle_per_scenario/2
                min_ang = min(temp_angles) - angle_per_scenario/2
                group_angular_ranges[current_group] = (min_ang, max_ang)
                temp_angles = []
                
                # Add Group Gap
                current_angle -= gap_angle
                
            if current_group != group:
                current_group = group
            
            angles.append(current_angle)
            temp_angles.append(current_angle)
            current_angle -= angle_per_scenario

        # Last group
        if temp_angles:
             max_ang = max(temp_angles) + angle_per_scenario/2
             min_ang = min(temp_angles) - angle_per_scenario/2
             group_angular_ranges[current_group] = (min_ang, max_ang)

        angles = np.array(angles)
        
        # Draw Bars
        bottom = np.zeros(n_scenarios) + INNER_RADIUS

        for cat_name, cat_config in self.emission_categories.items():
            # Scale Percentage Value (0-100) -> (0-400)
            values = np.array(emission_data[cat_name]) * scale_factor
            bars = ax.bar(
                angles,
                values,
                width=width,
                bottom=bottom,
                label=cat_config['keys'][0], # Label key for now
                color=cat_config['color'],
                edgecolor='white',
                linewidth=0.3,
                alpha=0.9
            )
            bottom += values

        # Outer Group Ring
        # Using pre-calculated outer_ring_start based on scaled geometry
        
        
        for group_name, (min_ang, max_ang) in group_angular_ranges.items():
            center_angle = (min_ang + max_ang) / 2
            span_angle = max_ang - min_ang
            
            # Arc
            ax.bar(
                x=center_angle,
                height=RING_WIDTH,
                bottom=outer_ring_start,
                width=span_angle,
                color=self.group_colors.get(group_name, '#999999'),
                alpha=0.8,
                edgecolor='none'
            )
            
            # Label
            deg = np.degrees(center_angle)
            if deg < 0: deg += 360
            rotation = deg - 90
            if 90 < deg < 270: rotation += 180

            ax.text(
                center_angle, outer_ring_start + RING_WIDTH/2, group_name,
                ha='center', va='center',
                fontsize=28, fontweight='bold',
                color='white',
                rotation=rotation,
                rotation_mode='anchor'
            )

        # Ticks
        ax.set_xticks([])
        # Ticks
        ax.set_xticks([])
        
        # Grid values (Percentage)
        grid_percents = [25, 50, 75, 100]
        # Map to Scaled Radius: (percent * scale) + INNER
        actual_grid_pos = [(p * scale_factor) + INNER_RADIUS for p in grid_percents]
        
        ax.set_yticks(actual_grid_pos)
        ax.set_yticklabels([])
        
        # Grid
        ax.yaxis.grid(True, linestyle='--', alpha=0.5, color='#aaaaaa', linewidth=0.8, dashes=(4, 4))
        ax.xaxis.grid(False)
        ax.spines['polar'].set_visible(False)
        
        # Tick Labels (Percentages)
        tick_angle = np.pi / 2
        for val, radius in zip(grid_percents, actual_grid_pos):
            # radius already calculated
            pass # just use loop variable
            
            ax.text(
                tick_angle, radius, f"{val}%",
                ha='center', va='center',
                fontsize=20, color='#666666',
                fontweight='bold',
                bbox=dict(facecolor='white', edgecolor='none', alpha=0.7, pad=0.5)
            )

        # Scenario Labels
        label_radius = outer_ring_start + RING_WIDTH * 1.5
        for angle, label in zip(angles, labels):
            self.draw_curved_text(ax, label, label_radius, angle, fontsize=24, color='#333333')

        # Legend
        handles, _ = ax.get_legend_handles_labels()
        emission_handles = handles[:len(self.emission_categories)]
        legend_labels = list(self.emission_categories.keys())
        
        cost_legend = ax.legend(
            handles=emission_handles,
            labels=legend_labels,
            loc='upper left',
            bbox_to_anchor=(1.15, 1.0),
            fontsize=24,
            title='Emission Sources',
            title_fontsize=26,
            frameon=False,
            labelspacing=0.8
        )
        cost_legend.get_title().set_fontweight('bold')

        # Title
        ax.text(
            0, 0, 'Emissions\nStructure\n(%)',
            ha='center', va='center',
            fontsize=24, fontweight='bold',
            color='#555555'
        )

        plt.tight_layout()

        # Save
        output_path = self.session_dir / "polar_carbon_percentage_chart.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
        logger.info(f"  ? Saved image: {output_path}")

        root_output = self.output_dir / "polar_carbon_percentage_chart_latest.png"
        plt.savefig(root_output, dpi=300, bbox_inches='tight', facecolor='white')
        logger.info(f"  ? Saved latest version: {root_output}")

        plt.close()
        return output_path

    def run(self):
        """Run visualization"""
        logger.info("=" * 80)
        logger.info("Starting Grouped Percentage Viz")
        logger.info("=" * 80)
        
        self.load_data()
        
        if len(self.data) < 2:
            logger.error(f"Data insufficient: {len(self.data)} scenarios found")
            return
            
        self.create_grouped_polar_chart()
        logger.info("\\nSUCCESS")


def main():
    """Main function"""
    viz = GroupedPolarCarbonPercentageVisualizer()
    viz.run()


if __name__ == "__main__":
    main()
