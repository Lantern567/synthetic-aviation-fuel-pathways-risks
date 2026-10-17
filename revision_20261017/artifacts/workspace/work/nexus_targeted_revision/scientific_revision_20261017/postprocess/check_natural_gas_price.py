import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
reports = []
for scenario, label in [('GTL-GH', 'baseline'), ('GTL-GH', 'summer_fixed'), ('GTL-BH', 'baseline')]:
    run = ROOT / 'results' / scenario / label
    parameters = json.loads((run / 'model_parameters.json').read_text(encoding='utf-8'))
    account = json.loads((ROOT / 'postprocess/accounts' / scenario / label / 'accounts.json').read_text(encoding='utf-8'))
    production = pd.read_csv(run / 'saf_production.csv')
    ratios = production.technology.map({key: value['ng_consumption_ratio'] for key, value in parameters['technologies'].items()})
    gas = float((production.value * ratios).sum())
    factor = account['production']['annual_expansion'] * account['production']['present_value_factor']
    cost = float(account['raw_cost']['components']['natural_gas_cost'])
    price = cost / factor / gas
    if not np.isclose(price, 2.53, atol=1e-8, rtol=0):
        raise ValueError(f'The actual natural-gas price differs: {scenario}/{label}: {price}')
    reports.append({'scenario': scenario, 'label': label, 'gas_m3': gas, 'cost_present_value_cny': cost,
                    'lifecycle_factor': factor, 'actual_price_cny_m3': price,
                    'summary_sha256': hashlib.sha256((run / 'summary.json').read_bytes()).hexdigest(),
                    'formula': 'actual natural_gas_cost / lifecycle factor / sum(actual technology fuel kg * configured m3/kg)'})
out = ROOT / 'postprocess/natural_gas_price_verification.json'
out.write_text(json.dumps({'passed': True, 'checks': reports}, indent=2) + '\n', encoding='utf-8')
print(json.dumps(reports, indent=2))
