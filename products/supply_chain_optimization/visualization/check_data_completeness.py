# -*- coding: utf-8 -*-
import json
import glob
import os
import pandas as pd
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

project_root = Path(__file__).parent.parent.parent.parent

scenarios = {
    'Coal Hydrogen': {
        'inventory_pattern': str(project_root / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/inventory_levels_*.csv')
    },
    'DAC Two-Step': {
        'inventory_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/two_step/inventory_levels_*.csv')
    },
    'DAC One-Step': {
        'inventory_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/one_step/inventory_levels_*.csv')
    },
    'Natural Gas Two-Step': {
        'inventory_pattern': str(project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/inventory_levels_*.csv')
    },
    'Natural Gas One-Step': {
        'inventory_pattern': str(project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/ft_one_step/inventory_levels_*.csv')
    },
    'Green H2 Two-Step': {
        'inventory_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/two_step/inventory_levels_*.csv')
    },
    'Green H2 One-Step': {
        'inventory_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/one_step/inventory_levels_*.csv')
    },
    'Byproduct H2 + Coal': {
        'inventory_pattern': str(project_root / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/byproduct_hydrogen/inventory_levels_*.csv')
    },
    'Byproduct H2 + DAC Two-Step': {
        'inventory_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/two_step/inventory_levels_*.csv')
    },
    'Byproduct H2 + DAC One-Step': {
        'inventory_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/one_step/inventory_levels_*.csv')
    },
    'Byproduct H2 + NG Two-Step': {
        'inventory_pattern': str(project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/byproduct_hydrogen/byproduct_hydrogen/two_step/inventory_levels_*.csv')
    },
    'Byproduct H2 Two-Step': {
        'inventory_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/two_step/inventory_levels_*.csv')
    },
    'Byproduct H2 One-Step': {
        'inventory_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/one_step/inventory_levels_*.csv')
    }
}

def get_target_file(pattern):
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

    # Sort by time (descending), latest first
    file_stats.sort(key=lambda x: x[2], reverse=True)
    
    best_file = file_stats[0][0]
    best_size_mb = file_stats[0][1] / (1024*1024)
    # logger.info(f"Selected LATEST file: {os.path.basename(best_file)} ({best_size_mb:.2f} MB)")
    
    return best_file

def check_scenario(name, config):
    inventory_file = get_target_file(config['inventory_pattern'])
    if not inventory_file:
        logger.warning(f"  Missing inventory file: {name}")
        return
    
    file_name = os.path.basename(inventory_file)
    try:
        df_inv = pd.read_csv(inventory_file)
        # Use English columns if available, else Chinese
        # Unicode escapes
        col_hour = '\u5c0f\u65f6' if '\u5c0f\u65f6' in df_inv.columns else 'hour'
        
        if col_hour not in df_inv.columns:
            logger.info(f"{name:<35} | Missing '{col_hour}' column | File: {file_name}")
            return

        max_hour = df_inv[col_hour].max()
        weeks = max_hour / 168.0
        
        status = "OK" if weeks >= 3.8 else "SHORT"
        logger.info(f"{name:<35} | Weeks: {weeks:.2f} | Status: {status} | File: {file_name}")

    except Exception as e:
        logger.error(f"{name:<35} | Error reading file | File: {file_name}")

print(f"{'Scenario':<35} | {'Duration':<12} | {'Status':<6} | {'File'}")
print("-" * 100)

for name, config in scenarios.items():
    check_scenario(name, config)
