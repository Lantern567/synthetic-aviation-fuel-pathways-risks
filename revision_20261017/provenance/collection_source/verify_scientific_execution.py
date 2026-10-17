import argparse
import ast
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys

import numpy as np
import pandas as pd

from revision_20261017_common import PAIRED, copy_checked, digest, expand_subtree, native, read_json, require_complete, revision_paths, safe_path, verify_input_files, write_json
from verify_solver_records_revision_20261017 import verify_solver_records


def integrity(revision, manifest, workspace):
    for relative, expected in manifest['archive_tools_sha256'].items():
        if digest(safe_path(revision.parent, relative)) != expected:
            raise ValueError(f'Archive preparation or verification tool changed: {relative}')
    hashes = read_json(revision / 'SHA256SUMS.json')
    for relative, expected in hashes.items():
        source = safe_path(revision, relative)
        if digest(source) != expected:
            raise ValueError(f'Archive hash differs: {relative}')
    sources = revision / manifest['runtime_sources_directory']
    if digest(sources / 'runtime_sources_manifest.json') != manifest['runtime_sources_manifest_sha256']:
        raise ValueError('The actual-runtime source manifest changed')
    source_records = read_json(sources / 'runtime_sources_manifest.json')['files']
    for root, records in [(sources, source_records), (revision, manifest['packed_files'])]:
        for record in records:
            source = safe_path(root, record['stored_path'])
            if digest(source) != record['stored_sha256']:
                raise ValueError(f'Packed file changed: {source}')
            opener = gzip.open if record['compression'] == 'gzip' else open
            if record['compression'] not in {'gzip', 'none'}:
                raise ValueError('Unknown compression format')
            with opener(native(source), 'rb') as incoming:
                payload_hash = hashlib.file_digest(incoming, 'sha256').hexdigest()
            if payload_hash != record['payload_sha256']:
                raise ValueError(f'Lossless expansion does not reproduce source bytes: {source}')
            if Path(record['original_path']).suffix in {'.sqlite', '.db'}:
                database = workspace / 'sqlite_checks' / (record['payload_sha256'] + '.db')
                native(database.parent).mkdir(parents=True, exist_ok=True)
                with opener(native(source), 'rb') as incoming, native(database).open('wb') as output:
                    shutil.copyfileobj(incoming, output)
                with sqlite3.connect(str(native(database))) as connection:
                    if connection.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                        raise ValueError(f'The saved SQLite input is invalid: {source}')
            if Path(record['original_path']).suffix == '.py':
                ast.parse(native(source).read_bytes(), filename=record['original_path'])
    for path in native(revision / 'source_snapshots').rglob('*.py'):
        ast.parse(path.read_bytes(), filename=str(path))
    artifact_manifest = revision / 'artifacts/source_manifest.json'
    if digest(artifact_manifest) != manifest['artifact_source_manifest_sha256']:
        raise ValueError('The final supporting scientific input contract changed')
    artifacts = read_json(artifact_manifest)
    packed = {record['original_path']: record for record in manifest['packed_files']}
    for record in artifacts['files']:
        if packed[record['archived_original_path']]['payload_sha256'] != record['source_sha256']:
            raise ValueError('The supporting artifact no longer reproduces its executed scientific source')
    return {'passed': True, 'files': len(hashes), 'packed_records': len(source_records) + len(manifest['packed_files']),
            'python_source_syntax_checked': True, 'sqlite_integrity_checked': True,
            'supporting_scientific_sources': len(artifacts['files'])}


def execute(command, log):
    native(log.parent).mkdir(parents=True, exist_ok=True)
    with native(log).open('w', encoding='utf-8') as output:
        command = [str(native(value)) if isinstance(value, Path) else str(value) for value in command]
        if command[0] == sys.executable:
            command[1:1] = ['-X', 'utf8']
        subprocess.run(command, stdout=output, stderr=subprocess.STDOUT, check=True)


def numerical_equal(left, right, path):
    if isinstance(left, dict):
        if set(left) != set(right):
            raise ValueError(f'Account field names differ: {path}')
        for key in left:
            numerical_equal(left[key], right[key], path + '/' + key)
    elif isinstance(left, (int, float)) and not isinstance(left, bool):
        if not np.isclose(left, right, rtol=1e-10, atol=1e-5):
            raise ValueError(f'Recomputed account differs: {path}: {left}, {right}')
    elif left != right:
        raise ValueError(f'Recomputed account metadata differs: {path}')


def fixed_assets(directories, scenario):
    before, after = [directories[scenario, label] for label in ['baseline', 'summer_fixed']]
    differences = {}
    for name, keys in [('saf_build', ['location', 'technology']), ('saf_capacity', ['location', 'technology']),
                       ('h2_build', ['location']), ('h2_capacity', ['location'])]:
        values = [pd.read_csv(native(folder / (name + '.csv'))).set_index(keys).value.sort_index() for folder in [before, after]]
        if not values[0].index.equals(values[1].index):
            raise ValueError(f'Fixed production-asset keys differ: {scenario}/{name}')
        differences[name] = float((values[0] - values[1]).abs().max())
    if scenario.startswith('DAC-'):
        selected = []
        for folder in [before, after]:
            pieces = []
            for chunk in pd.read_csv(native(folder / 'variables.csv'), usecols=['variable', 'value'], chunksize=200000):
                pieces.append(chunk[chunk.variable.str.startswith('dac_facility_')])
            selected.append(pd.concat(pieces).set_index('variable').value.sort_index())
        if selected[0].empty or not selected[0].index.equals(selected[1].index):
            raise ValueError(f'Fixed DAC build keys differ: {scenario}')
        differences['dac_build'] = float((selected[0] - selected[1]).abs().max())
    if max(differences.values()) > 1e-4:
        raise ValueError(f'Production assets changed in the alternate-week case: {scenario}: {differences}')
    return {'scenario': scenario, 'passed': True, 'maximum_differences': differences,
            'summary_sha256': [digest(folder / 'summary.json') for folder in [before, after]]}


def verify(archive, workspace, scenario, label, integrity_only):
    _, revision, manifest = revision_paths(archive)
    workspace = Path(workspace).resolve()
    if native(workspace).exists() or workspace.is_relative_to(revision):
        raise ValueError('Choose a new verification workspace outside revision_20261017')
    native(workspace).mkdir(parents=True)
    file_check = integrity(revision, manifest, workspace)
    if integrity_only:
        report = {'passed': True, 'integrity': file_check, 'optimization_executed': False}
        write_json(workspace / 'verification_report.json', report)
        return report
    if scenario is None:
        require_complete(manifest)
        records = manifest['runs']
    else:
        records = [item for item in manifest['runs'] if (item['scenario'], item['label']) == (scenario, label)]
        if len(records) != 1:
            raise ValueError('The selected completed actual case has not been archived')
    sources = revision / manifest['runtime_sources_directory']
    source_records = read_json(sources / 'runtime_sources_manifest.json')['files']
    tool_manifest = read_json(revision / 'verification_source/source_manifest.json')
    if digest(revision / 'verification_source/source_manifest.json') != manifest['verification_source_manifest_sha256']:
        raise ValueError('Independent verification source manifest changed')
    directories, checks = {}, []
    for record in records:
        scenario, label = record['scenario'], record['label']
        runtime = workspace / 'runtimes' / record['runtime']
        if not native(runtime).exists():
            expand_subtree(sources, runtime, source_records, 'runtimes/' + record['runtime'])
            for tool in tool_manifest:
                source = revision / 'verification_source' / tool['name']
                if digest(source) != tool['sha256']:
                    raise ValueError(f'Independent verification source changed: {tool["name"]}')
                target = runtime / tool['name']
                native(target.parent).mkdir(parents=True, exist_ok=True)
                shutil.copyfile(native(source), native(target))
        run = runtime / 'verified_runs' / scenario / label
        directories[scenario, label] = run
        expand_subtree(revision, run, manifest['packed_files'], 'saved_results/' + scenario + '/' + label)
        snapshot = revision / record['source_snapshot']
        verify_input_files(runtime, record['input_files_sha256'])
        if digest(run / 'summary.json') != record['summary_sha256'] or digest(snapshot / 'summary.json') != record['summary_sha256']:
            raise ValueError('The saved run summary differs from its actual execution snapshot')
        for name, expected in record['actual_execution_sources'].items():
            if digest(snapshot / 'source' / name) != expected or digest(run / 'source' / name) != expected:
                raise ValueError(f'Per-run actual execution source changed: {name}')
        logs = workspace / 'logs' / scenario / label
        if record['runtime'] == 'compute_bh_final':
            execute([sys.executable, runtime / 'validate_historical.py', scenario, label, '--runtime', runtime], logs / 'physics.log')
            physical = 'physical_validation.json'
        elif '-BH' in scenario:
            execute([sys.executable, runtime / 'validate_byproduct_physics.py', scenario, label, '--base', runtime], logs / 'physics.log')
            physical = 'byproduct_physical_validation.json'
        else:
            execute([sys.executable, runtime / 'validate_physics.py', scenario, label], logs / 'physics.log')
            physical = 'physical_validation.json'
        execute([sys.executable, runtime / 'validate_hydrogen_transport.py', run, '--out', run / 'recheck_hydrogen_transport'], logs / 'hydrogen_transport.log')
        execute([sys.executable, runtime / 'validate_inventory_cost.py', run, '--out', run / 'recheck_inventory_cost'], logs / 'inventory_cost.log')
        if scenario.startswith('DAC-'):
            execute([sys.executable, runtime / 'validate_co2.py', run, '--out', run / 'recheck_co2'], logs / 'co2.log')
        if scenario.startswith('CCU-'):
            execute([sys.executable, runtime / 'validate_ccu_accounts.py', '--run', run, '--out', run / 'recheck_ccu_co2.json'], logs / 'ccu_co2.log')
        if scenario == 'GTL-BH':
            execute([sys.executable, runtime / 'validate_extended_natural_gas.py', '--run', run], logs / 'extended_natural_gas.log')
        archived_accounts = workspace / 'archived_accounts' / scenario / label
        expand_subtree(revision, archived_accounts, manifest['packed_files'], 'final_accounts/' + scenario + '/' + label)
        if digest(archived_accounts / 'accounts.json') != record['account_sha256']:
            raise ValueError('Archived final account changed')
        recomputed = workspace / 'recomputed_accounts' / scenario / label
        execute([sys.executable, runtime / 'update_accounts.py', '--run', run, '--out', recomputed], logs / 'accounts.log')
        previous, current = read_json(archived_accounts / 'accounts.json'), read_json(recomputed / 'accounts.json')
        for name in ['production', 'raw_cost', 'final_cost', 'raw_carbon', 'final_carbon']:
            numerical_equal(previous[name], current[name], name)
        if not current['checks']['passed'] or digest(run / 'summary.json') != record['summary_sha256']:
            raise ValueError('The independent account check failed or changed the raw summary')
        checks.append({'scenario': scenario, 'label': label, 'passed': True, 'source_summary_sha256': record['summary_sha256'],
                       'physical_report': physical, 'final_cost_cny_kg': current['final_cost']['unit_cost_cny_kg'],
                       'final_carbon_g_mj': current['final_carbon']['intensity_g_mj'],
                       'current_independent_verifier_sources': tool_manifest,
                       'saved_execution_report_sha256': record['saved_validation_report_sha256']})
    assets = [fixed_assets(directories, name) for name in PAIRED] if len(records) == 18 else []
    solver_workspace = workspace / 'solver_record_checks'
    native(solver_workspace).mkdir(parents=True)
    solver_proofs = verify_solver_records(revision, manifest, solver_workspace,
                                         {(item['scenario'], item['label']) for item in records})
    report = {'passed': True, 'optimization_executed': False, 'solver_license_required': False, 'integrity': file_check,
              'verified_actual_runs': len(checks), 'fixed_production_asset_pairs': assets, 'checks': checks,
              'saved_solver_proof_checks': solver_proofs,
              'revision_manifest_sha256': digest(revision / 'revision_manifest.json')}
    write_json(workspace / 'verification_report.json', report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive-root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--scenario')
    parser.add_argument('--label', choices=['baseline', 'summer_fixed'])
    parser.add_argument('--integrity-only', action='store_true')
    args = parser.parse_args()
    if bool(args.scenario) != bool(args.label):
        raise ValueError('Provide both --scenario and --label, or neither for all eighteen cases')
    result = verify(args.archive_root, args.workspace, args.scenario, args.label, args.integrity_only)
    print(json.dumps({name: result[name] for name in ['passed', 'optimization_executed']} | {'verified_actual_runs': result.get('verified_actual_runs', 0)}, indent=2))
