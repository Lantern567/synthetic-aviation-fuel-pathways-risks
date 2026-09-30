# -*- coding: utf-8 -*-
"""
Weekly factory efficiency visualization for 13 scenarios.
Shows per-week utilization for SAF plants (derived from production data) and
average hydrogen plant utilization (flat across weeks due to lack of weekly H2 dispatch).
"""
import csv
import glob
import json
import logging
import math
from collections import defaultdict
from pathlib import Path
import matplotlib.pyplot as plt

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

SCENARIOS = {
    'Coal Hydrogen': {
        'color': '#E74C3C',
        'solution_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/complete_solution_*.json',
    },
    'DAC Two-Step': {
        'color': '#3498DB',
        'solution_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/two_step/complete_solution_*.json',
    },
    'DAC One-Step': {
        'color': '#5DADE2',
        'solution_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/one_step/complete_solution_*.json',
    },
    'Natural Gas Two-Step': {
        'color': '#2ECC71',
        'solution_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/complete_solution_*.json',
    },
    'Natural Gas One-Step': {
        'color': '#F39C12',
        'solution_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/ft_one_step/complete_solution_*.json',
    },
    'Green H2 Two-Step': {
        'color': '#9B59B6',
        'solution_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/two_step/complete_solution_*.json',
    },
    'Green H2 One-Step': {
        'color': '#C39BD3',
        'solution_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/one_step/complete_solution_*.json',
    },
    'Byproduct H2 + Coal': {
        'color': '#FF6B6B',
        'solution_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/byproduct_hydrogen/complete_solution_*.json',
    },
    'Byproduct H2 + DAC Two-Step': {
        'color': '#4ECDC4',
        'solution_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/two_step/complete_solution_*.json',
    },
    'Byproduct H2 + DAC One-Step': {
        'color': '#95E1D3',
        'solution_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/one_step/complete_solution_*.json',
    },
    'Byproduct H2 + NG Two-Step': {
        'color': '#26DE81',
        'solution_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/byproduct_hydrogen/byproduct_hydrogen/two_step/complete_solution_*.json',
    },
    'Byproduct H2 Two-Step': {
        'color': '#A29BFE',
        'solution_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/two_step/complete_solution_*.json',
    },
    'Byproduct H2 One-Step': {
        'color': '#DFE4EA',
        'solution_pattern': PROJECT_ROOT / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/one_step/complete_solution_*.json',
    },
}


def pick_latest(pattern: Path):
    files = glob.glob(str(pattern))
    if not files:
        return None
    files.sort(key=lambda p: Path(p).stat().st_mtime, reverse=True)
    return Path(files[0])


def infer_hourly_pattern(solution_pattern: Path) -> Path:
    return Path(str(solution_pattern).replace('complete_solution_', 'hourly_production_summary_').replace('.json', '.csv'))


def load_weekly_production_from_hourly(path: Path) -> dict:
    weekly_output = defaultdict(float)
    if not path:
        return weekly_output
    try:
        with path.open(newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader, [])
            header = [h.lstrip('\ufeff') for h in header]
            period_idx = None
            saf_idx = None
            for i, col in enumerate(header):
                col_lower = col.lower()
                if period_idx is None and ('时段' in col or 'period' in col_lower):
                    period_idx = i
                if saf_idx is None and ('saf' in col_lower or 'SAF' in col):
                    saf_idx = i
            if saf_idx is None:
                logger.warning(f"未找到SAF产出列: {path.name}")
                return weekly_output
            periods_per_week = 56
            for row_idx, row in enumerate(reader):
                if not row:
                    continue
                if period_idx is not None and period_idx < len(row):
                    try:
                        period = int(float(row[period_idx]))
                    except ValueError:
                        period = row_idx
                else:
                    period = row_idx
                week = period // periods_per_week
                try:
                    saf_val = float(row[saf_idx]) if saf_idx < len(row) else 0.0
                except ValueError:
                    saf_val = 0.0
                weekly_output[week] += saf_val
    except Exception as e:
        logger.warning(f"读取hourly_production_summary失败: {path} ({e})")
    return weekly_output


def compute_saf_weekly_utilization(data, hourly_path=None):
    facilities = data.get('facilities', {})
    capacity_per_loc = {}
    for name, info in facilities.items():
        cap = info.get('capacity_kg_per_hour')
        if cap is not None:
            capacity_per_loc[info.get('location', name)] = cap
    total_capacity = sum(capacity_per_loc.values())
    if total_capacity <= 0:
        return []

    weekly_output = defaultdict(float)
    if hourly_path:
        weekly_output = load_weekly_production_from_hourly(hourly_path)
    else:
        # 回退：使用transport_plan作为产量代理
        for tp in data.get('transport_plan', {}).values():
            w = tp.get('week')
            kg = tp.get('transport_kg', 0.0)
            if w is None:
                continue
            weekly_output[int(w)] += float(kg)

    if not weekly_output:
        return []
    util = []
    for w in range(4):
        kg = weekly_output.get(w, 0.0)
        max_week_kg = total_capacity * 168.0
        util.append(kg / max_week_kg if max_week_kg > 0 else 0.0)
    return util


def compute_h2_weekly_utilization(data):
    facilities = data.get('hydrogen_facilities', {})
    total_cap = 0.0
    total_prod = 0.0
    for _, info in facilities.items():
        cap = info.get('capacity_kg_h2_per_hour')
        prod = info.get('actual_annual_h2_production_kg')
        if cap is None or prod is None:
            continue
        total_cap += cap
        total_prod += prod
    if total_cap <= 0:
        return []
    # Average utilization over a year, repeated for weeks in horizon (4)
    util_avg = total_prod / (total_cap * 8760.0)
    return [util_avg] * 4


def main():
    results = {}
    for name, cfg in SCENARIOS.items():
        f = pick_latest(cfg['solution_pattern'])
        if not f:
            logger.warning(f"Missing solution file for {name}")
            continue
        hourly_pattern = infer_hourly_pattern(cfg['solution_pattern'])
        hourly_file = pick_latest(hourly_pattern)
        try:
            data = json.load(f.open())
        except Exception as e:
            logger.error(f"Failed to load {f}: {e}")
            continue
        saf_util = compute_saf_weekly_utilization(data, hourly_path=hourly_file)
        h2_util = compute_h2_weekly_utilization(data)
        results[name] = {
            'color': cfg['color'],
            'saf_util': saf_util,
            'h2_util': h2_util,
        }
        logger.info(f"{name}: SAF weeks={len(saf_util)}, H2 weeks={len(h2_util)}")

    if not results:
        logger.error("No data to plot")
        return

    # Build plots
    fig, axes = plt.subplots(2, 1, figsize=(14, 10), sharex=True)
    ax = axes[0]
    for name, info in results.items():
        util = info['h2_util']
        if not util:
            continue
        w_axis = list(range(len(util)))
        ax.plot(w_axis, util, label=name, color=info['color'], linewidth=1.4)
    ax.set_ylabel('H2 Plant Utilization')
    ax.set_title('Weekly Utilization of Hydrogen Plants')
    ax.grid(True, linestyle=':', alpha=0.6)

    ax = axes[1]
    for name, info in results.items():
        util = info['saf_util']
        if not util:
            continue
        w_axis = list(range(len(util)))
        ax.plot(w_axis, util, label=name, color=info['color'], linewidth=1.4)
    ax.set_ylabel('SAF Plant Utilization')
    ax.set_xlabel('Week (0-3)')
    ax.set_title('Weekly Utilization of SAF Plants')
    ax.grid(True, linestyle=':', alpha=0.6)

    handles, labels = axes[1].get_legend_handles_labels()
    if handles:
        fig.legend(handles, labels, loc='upper center', ncol=4, frameon=False)

    fig.tight_layout(rect=[0, 0, 1, 0.93])
    out_dir = PROJECT_ROOT / 'products/supply_chain_optimization/visualization/results'
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f'weekly_factory_efficiency.png'
    plt.savefig(out_path, dpi=300)
    logger.info(f"Saved plot: {out_path}")


if __name__ == '__main__':
    main()
