import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('current_accounts', ROOT / 'postprocess/update_accounts.py')
processor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(processor)
cases = json.loads((ROOT / 'execution/queue.json').read_text(encoding='utf-8'))
records = []
for item in cases:
    scenario, label = item['scenario'], item['label']
    run = ROOT / 'results' / scenario / label
    summary_hash = processor.digest(run / 'summary.json')
    summary = json.loads((run / 'summary.json').read_text(encoding='utf-8'))
    current = processor.update(run, ROOT / 'postprocess/synthesis_check' / scenario / label)
    carbon = summary['carbon_expressions']
    scoped = scenario.startswith(('CCU-', 'DAC-'))
    if scoped:
        config = yaml.safe_load((run / 'config.yaml').read_text(encoding='utf-8'))
        renewable = config['carbon_emission_parameters']['renewable_energy']
        ci = float(renewable['grid_electricity_intensity']) if '-BH-' in scenario else np.mean([renewable['wind_power_intensity'], renewable['solar_power_intensity']])
        storage = config['carbon_emission_parameters']['storage_handling']
        final_storage = 0.0
        for kind, key, divisor in [('saf', 'mtj_storage_energy', 1000), ('h2', 'h2_storage_energy', 1)]:
            stocks = pd.read_csv(run / f'{kind}_inventory.csv').pivot(index='location', columns='period', values='value').sort_index(axis=1)
            if stocks.columns.tolist() != list(range(225)):
                raise ValueError('Expected 225 consecutive inventory boundary states')
            final_storage += float(np.trapezoid(stocks.to_numpy(), dx=3, axis=1).sum()) * float(storage[key]) / 24 / divisor * ci
        expected_carbon = float(summary['carbon_aggregates']['total_emissions']) - float(carbon['methanol_to_saf']) - float(carbon['h2_storage']) - float(carbon['mtj_storage']) + final_storage
        processor.close(current['final_carbon']['aggregates']['total_emissions'], expected_carbon, 'Independent total carbon', atol=.02, rtol=1e-10)
        processor.close(current['final_carbon']['components']['methanol_to_saf'], 0, 'Common route-level energy')
        processor.close(current['process_adjustments']['electricity_cost_reconstructed_cny'], summary['cost_breakdown']['electricity_cost'], 'Independent configured electricity cost', atol=.02, rtol=1e-10)
        processor.close(current['process_adjustments']['synthesis_carbon_reconstruction_residual_kg'], 0, 'Independent synthesis carbon', atol=.02)
    if current['raw_cost']['unit_cost_cny_kg'] != current['final_cost']['unit_cost_cny_kg']:
        raise ValueError('Cost changed in report accounting')
    if processor.digest(run / 'summary.json') != summary_hash or current['source_summary_sha256'] != summary_hash:
        raise ValueError('Raw solution summary changed')
    records.append({'scenario': scenario, 'label': label, 'summary_sha256': summary_hash,
                    'route_energy_reconstructed': scoped,
                    'cost_cny_kg': current['final_cost']['unit_cost_cny_kg'],
                    'final_ci_g_mj': current['final_carbon']['intensity_g_mj'],
                    'separate_stage_raw_carbon_kg': carbon.get('methanol_to_saf', 0),
                    'passed': True})
if len(records) != 18 or sum(row['route_energy_reconstructed'] for row in records) != 12:
    raise ValueError('Expected eighteen real results and twelve CCU/DAC route-energy checks')
processor.write_json(ROOT / 'postprocess/synthesis_check/verification.json',
                     {'passed': True, 'processor_sha256': processor.digest(ROOT / 'postprocess/update_accounts.py'),
                      'checks': records})
print(json.dumps(records, ensure_ascii=False, indent=2))
