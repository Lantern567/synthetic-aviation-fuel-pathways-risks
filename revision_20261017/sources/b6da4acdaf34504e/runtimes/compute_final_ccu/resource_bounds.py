import json
from pathlib import Path

import pandas as pd
import yaml

base = Path(__file__).resolve().parent
configs = {
    'CCU-GH-FT':'shared/data/GreenHydrogenSupplyChainOptimizer_config.yaml',
    'CCU-GH-MTJ':'shared/data/GreenHydrogenSupplyChainOptimizer_config_two_step.yaml',
    'DAC-GH-FT':'shared/config/DACHydrogenSAFOptimizer_config.yaml',
    'DAC-GH-MTJ':'shared/config/DACHydrogenSAFOptimizer_config_two_step.yaml',
    'GTL-GH':'shared/data/NaturalGasSupplyChainOptimizer_config.yaml',
    'CTL':'products/supply_chain_optimization/coal_hydrogen_saf_optimization/data/CoalHydrogenSAFOptimizer_config.yaml',
}
rows = []
for scenario,path in configs.items():
    config = yaml.safe_load((base / 'project' / path).read_text(encoding='utf-8'))
    techs = {name:info for name,info in config['technologies'].items() if isinstance(info,dict) and 'h2_consumption_ratio' in info}
    ratios = {name:info['h2_consumption_ratio'] for name,info in techs.items()}
    intensity = config['cost_parameters']['electrolysis']['electrolysis_power_consumption']
    assert ratios and min(ratios.values())>0
    for label in ['baseline','summer']:
        manifest = json.loads((base / 'inputs' / label / 'manifest.json').read_text())
        energy = sum(manifest['energy_mwh'].values())
        bound = energy*1000/intensity/min(ratios.values())
        rows.append({'scenario':scenario,'label':label,'renewable_energy_mwh':energy,'h2_intensity_kwh_kg':intensity,'minimum_h2_ratio_kg_kg':min(ratios.values()),'saf_energy_only_upper_bound_kg':bound,'demand_kg':manifest['demand_kg'],'fulfillment_upper_bound':min(1,bound/manifest['demand_kg']),'minimum_shortage_kg':max(0,manifest['demand_kg']-bound),'scope':'Necessary bound only; ignores synthesis/DAC electricity, all capacity, transport and operating restrictions; zero initial hydrogen stock; renewable electrolysis only'})
pd.DataFrame(rows).to_csv(base / 'resource_upper_bounds.csv',index=False)
print(pd.DataFrame(rows)[['scenario','label','fulfillment_upper_bound','minimum_shortage_kg']].to_string(index=False))
