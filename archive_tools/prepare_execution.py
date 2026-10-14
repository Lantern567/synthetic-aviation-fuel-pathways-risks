import argparse
import gzip
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


CONFIGS = {
    'CCU-GH-FT': ('green_hydrogen_supply_chain_optimization', 'green_hydrogen_optimization_model.py', 'shared/data/GreenHydrogenSupplyChainOptimizer_config.yaml'),
    'CCU-GH-MTJ': ('green_hydrogen_supply_chain_optimization', 'green_hydrogen_optimization_model.py', 'shared/data/GreenHydrogenSupplyChainOptimizer_config_two_step.yaml'),
    'DAC-GH-FT': ('dac_hydrogen_saf_supply_chain_optimization', 'dac_hydrogen_optimization_model.py', 'shared/config/DACHydrogenSAFOptimizer_config.yaml'),
    'DAC-GH-MTJ': ('dac_hydrogen_saf_supply_chain_optimization', 'dac_hydrogen_optimization_model.py', 'shared/config/DACHydrogenSAFOptimizer_config_two_step.yaml'),
    'GTL-GH': ('natural_gas_supply_chain_optimization', 'natural_gas_optimization_model.py', 'shared/data/NaturalGasSupplyChainOptimizer_config.yaml'),
    'CTL': ('coal_hydrogen_saf_optimization', 'coal_hydrogen_optimization_model.py', 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/data/CoalHydrogenSAFOptimizer_config.yaml'),
}
LABELS = ('baseline', 'summer_fixed')


def filesystem_path(path):
    return Path('\\\\?\\' + str(path.resolve())) if sys.platform == 'win32' else path


def digest(path):
    checksum = hashlib.sha256()
    with filesystem_path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            checksum.update(chunk)
    return checksum.hexdigest()


def load_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def copy_checked(source, target):
    assert source.is_file(), f'Missing archived file: {source}'
    filesystem_path(target.parent).mkdir(parents=True, exist_ok=True)
    shutil.copy2(filesystem_path(source), filesystem_path(target))
    assert digest(source) == digest(target), target


def copy_tree_checked(source, target):
    assert source.is_dir(), f'Missing archived directory: {source}'
    assert not target.exists(), f'Workspace directory already exists: {target}'
    for item in source.rglob('*'):
        if item.is_file() and '__pycache__' not in item.parts:
            copy_checked(item, target / item.relative_to(source))


def load_packed_inputs(archive):
    data = load_json(archive / 'provenance/packed_inputs.json')
    lookup = {item['path']: item for item in data['files']}
    assert len(lookup) == len(data['files']), 'Duplicate packed input paths.'
    return lookup


def expand_archived_files(directory, original_directory, archive, packed_inputs):
    expanded = []
    sources = sorted(path for path in directory.rglob('*.gz') if path.name.endswith(('.csv.gz', '.db.gz', '.jsonl.gz')))
    for source in sources:
        target = source.with_suffix('')
        original = original_directory / source.relative_to(directory)
        relative = original.relative_to(archive).as_posix()
        assert relative in packed_inputs, f'Missing packed-file provenance: {relative}'
        metadata = packed_inputs[relative]
        assert digest(source) == metadata['sha256'], relative
        assert original.with_suffix('').relative_to(archive).as_posix() == metadata['unpacked_path'], relative
        assert not target.exists(), f'Duplicate compressed and plain file: {target}'
        with gzip.open(source, 'rb') as incoming, target.open('xb') as outgoing:
            shutil.copyfileobj(incoming, outgoing)
        assert target.stat().st_size == metadata['unpacked_bytes'], relative
        assert digest(target) == metadata['unpacked_sha256'], relative
        expanded.append({'compressed_path': source.relative_to(directory).as_posix(), 'compressed_sha256': digest(source), 'plain_path': target.relative_to(directory).as_posix(), 'plain_sha256': digest(target)})
    return expanded


def archived_table(folder, name):
    candidates = [folder / f'{name}.csv', folder / f'{name}.csv.gz']
    matches = [path for path in candidates if path.exists()]
    assert len(matches) == 1, f'Expected one archived table {name}: {folder}'
    return matches[0]


def prepare_one(archive, workspace, scenario, label):
    assert not workspace.exists(), f'Choose a new workspace path: {workspace}'
    compute = archive / 'compute'
    packed_inputs = load_packed_inputs(archive)
    snapshot = archive / 'source_snapshots' / scenario / label
    family, model_name, config_path = CONFIGS[scenario]
    workspace.mkdir(parents=True)
    copy_tree_checked(compute / 'project', workspace / 'project')
    expanded_project = expand_archived_files(workspace / 'project', compute / 'project', archive, packed_inputs)
    copy_tree_checked(compute / 'inputs', workspace / 'inputs')
    expanded_inputs = expand_archived_files(workspace / 'inputs', compute / 'inputs', archive, packed_inputs)
    copy_tree_checked(compute / 'routing', workspace / 'routing')
    expanded_routing = expand_archived_files(workspace / 'routing', compute / 'routing', archive, packed_inputs)
    for source in compute.iterdir():
        if source.is_file() and source.suffix in {'.py', '.json', '.csv', '.gz'}:
            copy_checked(source, workspace / source.name)
    for name in ('run_model.py', 'corrected_model.py'):
        copy_checked(snapshot / 'source' / name, workspace / name)
    core_target = workspace / 'project/products/supply_chain_optimization' / family / 'src/core' / model_name
    copy_checked(snapshot / 'source' / model_name, core_target)
    copy_checked(snapshot / 'config.yaml', workspace / 'project' / config_path)
    copy_checked(snapshot / 'config.yaml', workspace / 'archived_execution_config.yaml')
    summary = load_json(snapshot / 'summary.json')
    assert summary['scenario'] == scenario and summary['label'] == label
    if scenario == 'CTL':
        scope = summary['model_scope']
        assert scope['allow_ctl_shortage'] is True, scope
        (workspace / 'diagnostic_scope.json').write_text(json.dumps(scope, indent=2), encoding='utf-8')
    if label == 'summer_fixed':
        baseline = archive / 'validation_records' / scenario / 'baseline'
        target = workspace / 'verified_runs' / scenario / 'baseline'
        copy_checked(baseline / 'summary.json', target / 'summary.json')
        names = ['saf_capacity', 'saf_build', 'h2_capacity', 'h2_build']
        if scenario.startswith('DAC-'):
            names.append('variables')
        for name in names:
            source = archived_table(baseline, name)
            copy_checked(source, target / source.name)
        expand_archived_files(target, baseline, archive, packed_inputs)
    report = {
        'scenario': scenario,
        'label': label,
        'source_snapshot': str(snapshot.relative_to(archive)),
        'source_summary_sha256': digest(snapshot / 'summary.json'),
        'execution_sources': {
            name: digest(snapshot / 'source' / name)
            for name in ('run_model.py', 'corrected_model.py', model_name)
        },
        'archived_config_sha256': digest(snapshot / 'config.yaml'),
        'config_scope': 'Original configuration copied unchanged; archived run_model maps its airport input path to the newly prepared local inputs directory.',
        'model_scope': summary.get('model_scope'),
        'source_ledger_scope': 'Solver summary is retained unchanged; final manuscript accounting is provided separately under accompanying_data.',
        'prepared_files': {
            path.relative_to(workspace).as_posix(): digest(path)
            for path in sorted(workspace.rglob('*')) if path.is_file()
        },
        'command': [sys.executable, str(workspace / 'run_model.py'), scenario, label],
        'optimization_executed': False,
        'expanded_files': {'project': expanded_project, 'inputs': expanded_inputs, 'routing': expanded_routing},
    }
    (workspace / 'preparation_manifest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


def assert_close(actual, expected, absolute=1e-3, relative=1e-9):
    assert abs(actual - expected) <= max(absolute, relative * max(abs(actual), abs(expected))), (actual, expected)


def verify_source_ledger(folder, inputs):
    import pandas as pd
    import yaml

    summary = load_json(folder / 'summary.json')
    config = yaml.safe_load((folder / 'config.yaml').read_text(encoding='utf-8'))
    production = float(pd.read_csv(folder / 'saf_production.csv').value.sum())
    capacity = float(pd.read_csv(folder / 'saf_capacity.csv').value.sum())
    demand = float(pd.read_csv(inputs / 'airport_input.csv').weekly_total_fuel_kg_total.sum())
    delivered = float(pd.read_csv(folder / 'deliveries.csv').value.sum())
    assert_close(production, summary['production_kg'])
    assert_close(capacity, summary['saf_capacity_kg_h'])
    assert_close(demand, summary['demand_kg'])
    assert_close(delivered + summary['shortage_kg'], demand)
    assert_close(summary['demand_fulfillment_ratio'], 1 - summary['shortage_kg'] / demand, 1e-10)
    assert_close(summary['mean_utilization'], production / (capacity * 672), 1e-10)
    rate = config['economic_parameters']['discount_rate']
    years = config['economic_parameters']['project_lifespan']
    present_value = years if rate == 0 else (1 - (1 + rate) ** (-years)) / rate
    cost = summary['cost_breakdown']['total_cost_excluding_shortage'] / (production * 13 * present_value)
    assert_close(cost, summary['cost_per_kg_excluding_shortage'], 1e-9)
    return {'passed': True, 'source_summary_sha256': digest(folder / 'summary.json'), 'production_kg': production, 'demand_kg': demand, 'delivered_kg': delivered, 'source_solver_cost_per_kg_excluding_shortage': cost, 'scope': 'Recalculation of archived solver-summary ledger; final accounting adjustments are checked separately.'}


def verify_fixed_assets(records, scenario):
    import pandas as pd

    folders = [records / scenario / label for label in LABELS]
    errors = {}
    for name, keys in [('saf_capacity', ['location', 'technology']), ('saf_build', ['location', 'technology']), ('h2_capacity', ['location']), ('h2_build', ['location'])]:
        frames = [pd.read_csv(archived_table(folder, name)).set_index(keys).value.sort_index() for folder in folders]
        assert frames[0].index.equals(frames[1].index), (scenario, name)
        errors[name] = float((frames[0] - frames[1]).abs().max())
    if scenario.startswith('DAC-'):
        frames = [pd.read_csv(archived_table(folder, 'variables'), usecols=['variable', 'value']).set_index('variable').value for folder in folders]
        frames = [frame[frame.index.str.startswith('dac_facility_')].sort_index() for frame in frames]
        assert len(frames[0]) > 0 and frames[0].index.equals(frames[1].index), scenario
        errors['dac_build'] = float((frames[0] - frames[1]).abs().max())
    assert max(errors.values()) <= 1e-4, (scenario, errors)
    return {'scenario': scenario, 'passed': True, 'maximum_differences': errors, 'source_summary_sha256': [digest(folder / 'summary.json') for folder in folders], 'scope': 'SAF and electrolyzer build/capacity; DAC build where present. Inventory and transport decisions are free in the alternate-week run.'}


def verify_all(archive, workspace):
    assert not workspace.exists(), f'Choose a new workspace path: {workspace}'
    workspace.mkdir(parents=True)
    records = archive / 'validation_records'
    packed_inputs = load_packed_inputs(archive)
    copy_tree_checked(archive / 'compute/inputs', workspace / 'inputs')
    expand_archived_files(workspace / 'inputs', archive / 'compute/inputs', archive, packed_inputs)
    copy_checked(archive / 'compute/raw_profile_validation.json', workspace / 'raw_profile_validation.json')
    copy_checked(archive / 'compute/validate_physics.py', workspace / 'validate_physics.py')
    checks = []
    for scenario in CONFIGS:
        for label in LABELS:
            source = records / scenario / label
            target = workspace / 'runs' / scenario / label
            copy_tree_checked(source, target)
            expanded = expand_archived_files(target, source, archive, packed_inputs)
            source_digest = digest(source / 'summary.json')
            archived_check = load_json(source / 'physical_validation.json')
            assert archived_check['passed'] and archived_check['solution_summary_sha256'] == source_digest
            inputs = workspace / 'inputs' / ('baseline' if label == 'baseline' else 'summer')
            ledger = verify_source_ledger(target, inputs)
            subprocess.run([sys.executable, str(workspace / 'validate_physics.py'), scenario, label], cwd=workspace, check=True)
            checked = load_json(target / 'physical_validation.json')
            assert checked['passed'] and checked['solution_summary_sha256'] == source_digest
            assert digest(source / 'summary.json') == digest(target / 'summary.json')
            checks.append({'scenario': scenario, 'label': label, 'passed': True, 'source_summary_sha256': source_digest, 'physical_validation': checked, 'source_ledger': ledger, 'expanded_tables': expanded})
    assets = [verify_fixed_assets(records, scenario) for scenario in CONFIGS]
    report = {'passed': True, 'optimization_executed': False, 'solver_license_required': False, 'verified_solutions': len(checks), 'fixed_asset_pairs': len(assets), 'checks': checks, 'fixed_assets': assets, 'scope': 'Twelve archived COPT source solutions; seven archived comparison configurations and final inventory/emission accounting are outside these raw-physics/source-ledger checks.'}
    (workspace / 'verification_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description='Prepare exact archived model snapshots, or independently verify saved inputs and dispatch without optimization.')
    parser.add_argument('--archive-root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--scenario', choices=CONFIGS)
    parser.add_argument('--label', choices=LABELS)
    parser.add_argument('--verify-all', action='store_true')
    args = parser.parse_args()
    archive, workspace = args.archive_root.resolve(), args.workspace.resolve()
    assert archive.is_dir(), archive
    assert archive not in workspace.parents or not any(part in {'compute', 'source_snapshots', 'validation_records', 'accompanying_data'} for part in workspace.relative_to(archive).parts), 'Use a dedicated work directory.'
    if args.verify_all:
        assert args.scenario is None and args.label is None, '--verify-all processes all twelve records.'
        report = verify_all(archive, workspace)
        print(json.dumps({'passed': report['passed'], 'verified_solutions': report['verified_solutions'], 'fixed_asset_pairs': report['fixed_asset_pairs'], 'report': str(workspace / 'verification_report.json')}, ensure_ascii=False))
    else:
        assert args.scenario and args.label, 'Provide --scenario and --label.'
        report = prepare_one(archive, workspace, args.scenario, args.label)
        print(json.dumps({'prepared': True, 'optimization_executed': False, 'workspace': str(workspace), 'command': report['command'], 'manifest': str(workspace / 'preparation_manifest.json')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
