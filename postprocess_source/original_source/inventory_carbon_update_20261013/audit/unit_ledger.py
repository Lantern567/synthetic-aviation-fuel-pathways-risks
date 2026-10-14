import ast
import csv
import hashlib
import json
from pathlib import Path

import yaml


out = Path(__file__).resolve().parent
base = out.parents[1]
project = base.parents[1]
data = project / 'Nexus系统提交文件_库存成本修正20261013/Accompanying_Data'
normalized = data / 'figure_data/normalized_pathway_records'
archive = base / 'github_archive/repository/model_source'
corrected = base / 'corrected_runs_20261006/project'
source_models = {
    'CCU': 'green_hydrogen_supply_chain_optimization/src/core/green_hydrogen_optimization_model.py',
    'DAC': 'dac_hydrogen_saf_supply_chain_optimization/src/core/dac_hydrogen_optimization_model.py',
    'CTL': 'coal_hydrogen_saf_optimization/src/core/coal_hydrogen_optimization_model.py',
    'GTL': 'natural_gas_supply_chain_optimization/src/core/natural_gas_optimization_model.py',
}
archive_configs = {
    'CCU-BH-FT': 'ByproductHydrogenSupplyChainOptimizer_config.yaml',
    'CCU-BH-MTJ': 'ByproductHydrogenSupplyChainOptimizer_config_two_step.yaml',
    'DAC-BH-FT': 'DACByproductHydrogenSAFOptimizer_config_one_step.yaml',
    'DAC-BH-MTJ': 'DACByproductHydrogenSAFOptimizer_config_two_step.yaml',
    'CTL-BH': 'CoalByproductHydrogenSAFOptimizer_config.yaml',
    'GTL-BH': 'NaturalGasByproductHydrogenOptimizer_config.yaml',
    'GTL': 'NaturalGasSupplyChainOptimizer_config_one_step.yaml',
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evidence(path):
    text = path.read_text(encoding='utf-8-sig')
    tree = ast.parse(text)
    assignments = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Attribute) and target.value.attr == 'carbon_expressions' and isinstance(target.slice, ast.Constant):
                    key = target.slice.value
                    if 'storage' in key:
                        assignments[key] = {'line': node.lineno, 'expression': ast.unparse(node.value)}
    notes = [{'line': number, 'text': line.strip()} for number, line in enumerate(text.splitlines(), 1) if 'mtj_storage_energy = ' in line or 'h2_storage_energy = ' in line]
    return {'file': str(path), 'sha256': digest(path), 'parameter_unit_lines': notes, 'storage_expressions': assignments}


models = {}
for origin, folder in [('archived', archive), ('COPT', corrected)]:
    for group, relative in source_models.items():
        models[f'{origin}_{group}'] = evidence(folder / 'products/supply_chain_optimization' / relative)
models['archived_GTL_FT'] = evidence(archive / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/src/core/natural_gas_optimization_model_one_step.py')
manifest = json.loads((normalized / 'manifest.json').read_text(encoding='utf-8'))
rows = []
details = []
for file in sorted(normalized.glob('*_carbon_emissions.json')):
    scenario = file.name.replace('_carbon_emissions.json', '')
    carbon = json.loads(file.read_text(encoding='utf-8'))
    solution_path = normalized / f'{scenario}_complete_solution.json'
    solution = json.loads(solution_path.read_text(encoding='utf-8'))
    assert solution['carbon_emissions']['detailed'] == carbon['detailed'], scenario
    prefix = scenario.split('-')[0]
    origin = 'archived' if scenario in archive_configs else 'COPT'
    config_path = archive / 'shared/data' / archive_configs[scenario] if origin == 'archived' else data / f'runs/{scenario}/baseline/config.yaml'
    config = yaml.safe_load(config_path.read_text(encoding='utf-8'))
    period = config['basic_parameters']['hours_per_period']
    assert period == 3 and solution['period_hours'] == period, scenario
    energy = config['carbon_emission_parameters']['benchmarks']['saf_energy_content']
    storage_config = config['carbon_emission_parameters']['storage_handling']
    model_key = f'{origin}_{prefix}' if scenario != 'GTL' else 'archived_GTL_FT'
    storage_fields = {key: value for key, value in carbon['detailed'].items() if 'storage' in key}
    if scenario == 'GTL':
        assert storage_fields == {'saf_storage': 0.0}
        factors = {'saf_storage': 1.0}
    else:
        assert set(storage_fields) == {'mtj_storage', 'h2_storage'}, (scenario, storage_fields)
        factors = {'mtj_storage': period / 1000, 'h2_storage': period}
        formulas = models[model_key]['storage_expressions']
        assert set(formulas) == {'mtj_storage', 'h2_storage'}
        assert 'self.hours_per_period' not in formulas['mtj_storage']['expression']
        assert '/ 1000' not in formulas['mtj_storage']['expression']
        assert 'self.hours_per_period' not in formulas['h2_storage']['expression']
    corrected_fields = {key: value * factors[key] for key, value in storage_fields.items()}
    old_storage = sum(storage_fields.values())
    assert abs(old_storage - carbon['by_stage']['storage_emissions']) < 1e-5
    new_storage = sum(corrected_fields.values())
    old_total = carbon['by_stage']['total_emissions']
    new_total = old_total - old_storage + new_storage
    production = carbon['total_production_kg']
    scale = 1000 / production / energy
    row = {'scenario': scenario, 'label': 'baseline', 'origin': origin, 'period_hours': period,
           'saf_factor': factors.get('mtj_storage', factors.get('saf_storage')),
           'h2_factor': factors.get('h2_storage'), 'original_ci_g_mj': carbon['carbon_intensity_mj'],
           'unit_corrected_ci_g_mj': new_total * scale, 'old_storage_g_mj': old_storage * scale,
           'unit_corrected_storage_g_mj': new_storage * scale, 'cost_cny_kg_unchanged': solution['lifecycle_levelized_cost_excluding_shortage_per_kg']}
    rows.append(row)
    details.append({**row, 'source_carbon_file': str(file), 'source_carbon_sha256': digest(file),
                    'source_solution_sha256': digest(solution_path), 'original_optimization_source_sha256': manifest[scenario]['source_sha256'],
                    'model_evidence_key': model_key, 'config_file': str(config_path), 'config_sha256': digest(config_path),
                    'storage_energy_parameters': storage_config, 'energy_content_mj_kg': energy,
                    'original_storage_fields_kg_co2e': storage_fields, 'unit_corrected_storage_fields_kg_co2e': corrected_fields,
                    'field_factors': factors, 'original_total_kg_co2e': old_total, 'unit_corrected_total_kg_co2e': new_total,
                    'coverage_status': '仅已报告库存项的单位/时长更正；H2非来源地点与未独立列入的MeOH/CO2库存范围另核查'})
    if origin == 'COPT':
        for label in ['baseline', 'summer_fixed']:
            run_path = data / f'runs/{scenario}/{label}/summary.json'
            summary = json.loads(run_path.read_text(encoding='utf-8'))
            terms = summary['carbon_expressions']
            run_config_path = data / f'runs/{scenario}/{label}/config.yaml'
            run_config = yaml.safe_load(run_config_path.read_text(encoding='utf-8'))
            assert run_config['basic_parameters']['hours_per_period'] == period
            run_energy = run_config['carbon_emission_parameters']['benchmarks']['saf_energy_content']
            before_storage = terms['mtj_storage'] + terms['h2_storage']
            after_storage = terms['mtj_storage'] * period / 1000 + terms['h2_storage'] * period
            before_total = summary['carbon_aggregates']['total_emissions']
            after_total = before_total - before_storage + after_storage
            if label == 'baseline':
                assert abs(after_total - new_total) < 1e-5
                continue
            run_scale = 1000 / summary['production_kg'] / run_energy
            row = {'scenario': scenario, 'label': label, 'origin': origin, 'period_hours': period,
                   'saf_factor': period / 1000, 'h2_factor': period, 'original_ci_g_mj': before_total * run_scale,
                   'unit_corrected_ci_g_mj': after_total * run_scale, 'old_storage_g_mj': before_storage * run_scale,
                   'unit_corrected_storage_g_mj': after_storage * run_scale, 'cost_cny_kg_unchanged': summary['cost_per_kg_excluding_shortage']}
            rows.append(row)
            details.append({**row, 'source_summary_file': str(run_path), 'source_summary_sha256': digest(run_path),
                            'config_file': str(run_config_path), 'config_sha256': digest(run_config_path), 'model_evidence_key': model_key,
                            'field_factors': factors, 'original_storage_fields_kg_co2e': {key: terms[key] for key in ['mtj_storage', 'h2_storage']},
                            'unit_corrected_storage_fields_kg_co2e': {'mtj_storage': terms['mtj_storage'] * period / 1000, 'h2_storage': terms['h2_storage'] * period},
                            'original_total_kg_co2e': before_total, 'unit_corrected_total_kg_co2e': after_total,
                            'coverage_status': '仅已报告库存项单位/时长更正；完整库存范围另核查'})
with (out / 'unit_corrected_inventory_carbon.csv').open('w', encoding='utf-8-sig', newline='') as stream:
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
(out / 'unit_corrected_inventory_carbon.json').write_text(json.dumps({'input_version': str(data), 'scope': '已报告项静态碳核算，不重新优化，不更改经济成本，尚未声称全部库存能源范围已核查', 'records': details, 'code_evidence': models}, ensure_ascii=False, indent=2), encoding='utf-8')
for row in rows:
    print(row['scenario'], row['label'], f"{row['original_ci_g_mj']:.9f} -> {row['unit_corrected_ci_g_mj']:.9f}", 'Storage', f"{row['unit_corrected_storage_g_mj']:.9f}")
