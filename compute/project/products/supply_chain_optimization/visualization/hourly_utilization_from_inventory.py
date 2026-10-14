# -*- coding: utf-8 -*-
"""
Approximate hourly utilization for 13 scenarios by differencing inventory.
Usage: python hourly_utilization_from_inventory.py

Assumptions:
- Inventory levels reflect net stock; positive hour-to-hour increase is treated as production inflow.
- Negative inventory deltas (outflow/demand) are ignored for utilization.
- Capacity is total plant capacity (kg/hour) from complete_solution facilities.
- Hours axis limited to first 4 weeks (0-672h if available).
"""
import glob
import json
import logging
from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
RESULT_DIR = PROJECT_ROOT / 'products/supply_chain_optimization/visualization/results'
RESULT_DIR.mkdir(parents=True, exist_ok=True)

SCENARIOS = {
    'Coal Hydrogen': {
        'color': '#E74C3C',
        'inventory_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/inventory_levels_*.csv',
        'solution_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/complete_solution_*.json',
    },
    'DAC Two-Step': {
        'color': '#3498DB',
        'inventory_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/two_step/inventory_levels_*.csv',
        'solution_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/two_step/complete_solution_*.json',
    },
    'DAC One-Step': {
        'color': '#5DADE2',
        'inventory_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/one_step/inventory_levels_*.csv',
        'solution_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/one_step/complete_solution_*.json',
    },
    'Natural Gas Two-Step': {
        'color': '#2ECC71',
        'inventory_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/inventory_levels_*.csv',
        'solution_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/complete_solution_*.json',
    },
    'Natural Gas One-Step': {
        'color': '#F39C12',
        'inventory_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/ft_one_step/inventory_levels_*.csv',
        'solution_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/ft_one_step/complete_solution_*.json',
    },
    'Green H2 Two-Step': {
        'color': '#9B59B6',
        'inventory_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/two_step/inventory_levels_*.csv',
        'solution_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/two_step/complete_solution_*.json',
    },
    'Green H2 One-Step': {
        'color': '#C39BD3',
        'inventory_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/one_step/inventory_levels_*.csv',
        'solution_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/one_step/complete_solution_*.json',
    },
    'Byproduct H2 + Coal': {
        'color': '#FF6B6B',
        'inventory_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/byproduct_hydrogen/inventory_levels_*.csv',
        'solution_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/byproduct_hydrogen/complete_solution_*.json',
    },
    'Byproduct H2 + DAC Two-Step': {
        'color': '#4ECDC4',
        'inventory_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/two_step/inventory_levels_*.csv',
        'solution_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/two_step/complete_solution_*.json',
    },
    'Byproduct H2 + DAC One-Step': {
        'color': '#95E1D3',
        'inventory_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/one_step/inventory_levels_*.csv',
        'solution_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/one_step/complete_solution_*.json',
    },
    'Byproduct H2 + NG Two-Step': {
        'color': '#26DE81',
        'inventory_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/byproduct_hydrogen/byproduct_hydrogen/two_step/inventory_levels_*.csv',
        'solution_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/byproduct_hydrogen/byproduct_hydrogen/two_step/complete_solution_*.json',
    },
    'Byproduct H2 Two-Step': {
        'color': '#A29BFE',
        'inventory_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/two_step/inventory_levels_*.csv',
        'solution_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/two_step/complete_solution_*.json',
    },
    'Byproduct H2 One-Step': {
        'color': '#DFE4EA',
        'inventory_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/one_step/inventory_levels_*.csv',
        'solution_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/one_step/complete_solution_*.json',
    },
}


def pick_latest(pattern: Path):
    files = glob.glob(str(pattern))
    if not files:
        return None
    files.sort(key=lambda p: Path(p).stat().st_mtime, reverse=True)
    return Path(files[0])


def load_capacity(solution_file: Path) -> float:
    try:
        data = json.load(solution_file.open())
    except Exception as e:
        logger.error(f"Failed to read {solution_file}: {e}")
        return 0.0
    facilities = data.get('facilities', {})
    total_cap = 0.0
    for _, info in facilities.items():
        cap = info.get('capacity_kg_per_hour')
        if cap is not None:
            total_cap += float(cap)
    return total_cap


def load_hourly_inventory(inv_file: Path):
    df = pd.read_csv(inv_file)
    col_hour = '\u5c0f\u65f6' if '\u5c0f\u65f6' in df.columns else 'hour'
    col_inv = '\u5e93\u5b58\u91cf(kg)' if '\u5e93\u5b58\u91cf(kg)' in df.columns else 'inventory_kg'
    series = df.groupby(col_hour)[col_inv].sum().sort_index()
    if series.empty:
        return pd.Series(dtype=float)
    min_h, max_h = int(series.index.min()), int(series.index.max())
    full_index = pd.Index(range(min_h, max_h + 1))
    series = series.reindex(full_index, method='ffill').fillna(0)
    return series


def compute_hourly_util(inv_series: pd.Series, capacity: float):
    if inv_series.empty or capacity <= 0:
        return pd.Series(dtype=float)
    delta = inv_series.diff().fillna(0)
    prod = delta.clip(lower=0)  # treat only positive inventory change as production inflow
    util = prod / capacity
    # Limit to first 4 weeks (0-672h) relative to start
    hours_relative = util.index - util.index.min()
    mask = hours_relative <= 672
    util = util.loc[mask]
    util.index = hours_relative[mask]
    return util


def main():
    records = {}
    for name, cfg in SCENARIOS.items():
        inv_file = pick_latest(cfg['inventory_pattern'])
        sol_file = pick_latest(cfg['solution_pattern'])
        if not inv_file or not sol_file:
            logger.warning(f"Skip {name}: missing inventory or solution file")
            continue
        cap = load_capacity(sol_file)
        inv_series = load_hourly_inventory(inv_file)
        util = compute_hourly_util(inv_series, cap)
        logger.info(f"{name}: hours={len(util)} cap={cap:.2f}")
        records[name] = {
            'util': util,
            'color': cfg['color'],
        }

    if not records:
        logger.error("No data to plot")
        return

    # Plot grid 4x4
    fig, axes = plt.subplots(4, 4, figsize=(24, 16), sharex=False)
    axes = axes.flatten()
    keys = list(SCENARIOS.keys())

    for i, ax in enumerate(axes):
        if i >= len(keys):
            ax.axis('off')
            continue
        name = keys[i]
        info = records.get(name)
        if not info:
            ax.text(0.5, 0.5, 'No Data', ha='center', va='center')
            ax.axis('off')
            continue
        util = info['util']
        ax.plot(util.index / 168.0, util.values, color=info['color'], linewidth=1.1)
        ax.set_title(name, fontsize=11)
        ax.set_ylabel('Utilization (proxy)')
        ax.set_xlabel('Week (hourly)')
        ax.grid(True, linestyle=':', alpha=0.5)

    fig.suptitle('Hourly Utilization (Proxy from Inventory Delta)', fontsize=18, fontweight='bold')
    fig.tight_layout(rect=[0, 0.02, 1, 0.96])
    out_path = RESULT_DIR / 'hourly_utilization_from_inventory.png'
    plt.savefig(out_path, dpi=300)
    logger.info(f"Saved: {out_path}")


if __name__ == '__main__':
    main()
