"""
Collection script to gather all latest visualization data into one folder.
"""
import glob
import shutil
import logging
import os
from pathlib import Path
from typing import Dict, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def get_latest_file(pattern: str) -> Optional[Path]:
    files = sorted(glob.glob(pattern), reverse=True)
    if not files:
        return None
    return Path(files[0])

def collect_latest_data():
    # Path definitions
    current_file = Path(__file__)
    project_root = current_file.parent.parent.parent.parent
    
    # Target output directory
    results_dir = current_file.parent / "results"
    dest_dir = results_dir / "collected_latest_data"
    
    # Clean and recreate target directory
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Target Directory: {dest_dir}")

    # Scenario definitions (matching visualization scripts)
    modules = {
        'CTL': {
            'base_path': 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results'
        },
        'CTL-BH': {
            'base_path': 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/byproduct_hydrogen'
        },
        'DAC-GH-MTJ': {
            'base_path': 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/two_step'
        },
        'DAC-GH-FT': {
            'base_path': 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/one_step'
        },
        'CCU-GH-MTJ': {
            'base_path': 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/two_step'
        },
        'CCU-GH-FT': {
            'base_path': 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/one_step'
        },
        'GTL-GH': {
            'base_path': 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results'
        },
        'GTL': {
            'base_path': 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/ft_one_step'
        },
        'DAC-BH-MTJ': {
            'base_path': 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/two_step'
        },
        'DAC-BH-One-Step': { # Note: This usually maps to DAC-BH-FT in other scripts, checking patterns
             # In visualization scripts: 'DAC-BH-FT' points to .../byproduct_hydrogen/one_step
             # Keeping key as DAC-BH-FT for consistency with file naming
            'base_path': 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/one_step'
        },
        'GTL-BH': {
            'base_path': 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/byproduct_hydrogen/byproduct_hydrogen/two_step'
        },
        'CCU-BH-MTJ': {
            'base_path': 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/two_step'
        },
        'CCU-BH-FT': {
            'base_path': 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/one_step'
        },
    }

    # Fix the key for DAC-BH-One-Step to match the standard code if needed, 
    # but the key in the dict above is just for iteration. I'll use it for filenames.
    # To be precise, I should rename 'DAC-BH-One-Step' key to 'DAC-BH-FT' to match others
    modules['DAC-BH-FT'] = modules.pop('DAC-BH-One-Step')

    success_count = 0
    
    for scenario_code, config in modules.items():
        base_path = project_root / config['base_path']
        
        # Define patterns
        sol_pattern = str(base_path / "complete_solution_*.json")
        carb_pattern = str(base_path / "carbon_emissions_detailed_*.json")
        
        # Find latest files
        latest_sol = get_latest_file(sol_pattern)
        latest_carb = get_latest_file(carb_pattern)
        
        if latest_sol:
            dest_sol = dest_dir / f"{scenario_code}_complete_solution.json"
            shutil.copy2(latest_sol, dest_sol)
            logger.info(f"[{scenario_code}] Copied Solution: {latest_sol.name}")
        else:
            logger.warning(f"[{scenario_code}] No solution file found in {base_path}")

        if latest_carb:
            dest_carb = dest_dir / f"{scenario_code}_carbon_emissions.json"
            shutil.copy2(latest_carb, dest_carb)
            logger.info(f"[{scenario_code}] Copied Carbon: {latest_carb.name}")
        else:
            logger.warning(f"[{scenario_code}] No carbon file found in {base_path}")
            
        if latest_sol and latest_carb:
            success_count += 1

    logger.info("-" * 50)
    logger.info(f"Summary: Processed {len(modules)} scenarios, {success_count} fully successful.")
    logger.info(f"All files collected in: {dest_dir}")

if __name__ == "__main__":
    collect_latest_data()
