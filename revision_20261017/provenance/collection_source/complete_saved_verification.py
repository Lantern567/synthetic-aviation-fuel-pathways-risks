import argparse
import ast
import copy
import json
from pathlib import Path
import shutil
import sys

import seaborn


parser = argparse.ArgumentParser()
parser.add_argument('--archive', type=Path, required=True)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--original-manifest', type=Path, required=True)
parser.add_argument('--original-verifier', type=Path, required=True)
args = parser.parse_args()
archive, workspace = args.archive.resolve(), args.workspace.resolve()
sys.path.insert(0, str(archive / 'archive_tools'))
from revision_20261017_common import PAIRED, digest, native, read_json, verify_input_files, write_json
from verify_revision_20261017 import fixed_assets, integrity, numerical_equal
from verify_solver_records_revision_20261017 import verify_solver_records

revision = archive / 'revision_20261017'
previous = read_json(args.original_manifest)
manifest = read_json(revision / 'revision_manifest.json')
if manifest != previous:
    raise ValueError('The scientific manifest changed before completion of its checks')
if digest(args.original_verifier) != previous['archive_tools_sha256']['archive_tools/verify_revision_20261017.py']:
    raise ValueError('The original scientific-verification executable changed')

# 仅允许专用 DAC 建设表读取和绘图依赖声明发生变化。
old_ast = ast.parse(args.original_verifier.read_text(encoding='utf-8'))
new_ast = ast.parse((archive / 'archive_tools/verify_revision_20261017.py').read_text(encoding='utf-8'))
for tree in [old_ast, new_ast]:
    function = next(item for item in tree.body if isinstance(item, ast.FunctionDef) and item.name == 'fixed_assets')
    conditional = next(item for item in function.body if isinstance(item, ast.If)
                       and ast.unparse(item.test) == "scenario.startswith('DAC-')")
    conditional.body = [ast.Pass()]
if ast.dump(old_ast) != ast.dump(new_ast):
    raise ValueError('A verification function changed beyond the dedicated DAC asset reader')
allowed = {'archive_tools/verify_revision_20261017.py', 'archive_tools/requirements_revision_20261017_figures.txt'}
changed = {name for name, expected in manifest['archive_tools_sha256'].items() if digest(archive / name) != expected}
if changed != allowed:
    raise ValueError(f'Unexpected archive-tool changes: {changed}')
provenance = revision / 'provenance'
shutil.copyfile(args.original_manifest, provenance / 'physics_data_manifest.json')
shutil.copyfile(args.original_verifier, provenance / 'collection_source/verify_scientific_execution.py')
shutil.copyfile(Path(__file__), provenance / 'collection_source/complete_saved_verification.py')
for name in changed:
    manifest['archive_tools_sha256'][name] = digest(archive / name)
write_json(revision / 'revision_manifest.json', manifest)
binding = {'physics_data_manifest_sha256': digest(args.original_manifest),
           'final_revision_manifest_sha256': digest(revision / 'revision_manifest.json'),
           'scientific_sources_records_and_accounts_unchanged': True,
           'changed_archive_tools': {name: {'previous_sha256': previous['archive_tools_sha256'][name],
                                             'final_sha256': manifest['archive_tools_sha256'][name]}
                                     for name in sorted(changed)},
           'completed_case_check_scope_unchanged': True,
           'figure_dependency_import': {'passed': True, 'module': 'seaborn', 'version': seaborn.__version__}}
write_json(provenance / 'distribution_verification_binding.json', binding)

cached_hashes = {}


def checked_digest(path):
    path = Path(path).resolve()
    if path not in cached_hashes:
        cached_hashes[path] = digest(path)
    return cached_hashes[path]


def check_report(path, run, scenario, label, name):
    result = read_json(path)
    if result.get('passed') is not True:
        raise ValueError(f'A completed independent report did not pass: {path}')
    expected = checked_digest(run / 'summary.json')
    summary_bindings = [result[key] for key in ['solution_summary_sha256', 'source_summary_sha256'] if key in result]
    for source_name, source_hash in result.get('input_sha256', {}).items():
        source = Path(source_name)
        if not source.is_absolute():
            source = run / source
        if checked_digest(source) != source_hash:
            raise ValueError(f'A report input changed after its real verification: {source}')
        if source.name == 'summary.json':
            summary_bindings.append(source_hash)
    if not summary_bindings or any(item != expected for item in summary_bindings):
        raise ValueError(f'An independent report does not bind the exact raw solution: {path}')
    target = provenance / 'verification_replay' / scenario / label / (name + '.json')
    native(target.parent).mkdir(parents=True, exist_ok=True)
    shutil.copyfile(native(path), native(target))
    return {'report': target.relative_to(revision).as_posix(), 'sha256': digest(target), 'passed': True}


tools = read_json(revision / 'verification_source/source_manifest.json')
directories, checks = {}, []
for record in manifest['runs']:
    scenario, label = record['scenario'], record['label']
    runtime = workspace / 'runtimes' / record['runtime']
    run = runtime / 'verified_runs' / scenario / label
    directories[scenario, label] = run
    verify_input_files(runtime, record['input_files_sha256'])
    if checked_digest(run / 'summary.json') != record['summary_sha256']:
        raise ValueError('The completed case summary changed')
    for name, expected in record['actual_execution_sources'].items():
        if checked_digest(run / 'source' / name) != expected:
            raise ValueError(f'The completed actual execution source changed: {name}')
    for tool in tools:
        if checked_digest(runtime / tool['name']) != tool['sha256']:
            raise ValueError(f'The actually executed independent checker changed: {tool["name"]}')
    physical = 'byproduct_physical_validation.json' if '-BH' in scenario and record['runtime'] != 'compute_bh_final' else 'physical_validation.json'
    reports = [('physics', run / physical),
               ('hydrogen_transport', run / 'recheck_hydrogen_transport/hydrogen_transport_validation.json'),
               ('inventory_cost', run / 'recheck_inventory_cost/inventory_cost_validation.json')]
    if scenario.startswith('DAC-'):
        reports.append(('co2', run / 'recheck_co2/co2_validation.json'))
    if scenario.startswith('CCU-'):
        reports.append(('ccu_co2', run / 'recheck_ccu_co2.json'))
    if scenario == 'GTL-BH':
        reports.append(('extended_natural_gas', run / 'extended_natural_gas_validation.json'))
    evidence = {}
    for name, path in reports:
        log = workspace / 'logs' / scenario / label / (name + '.log')
        if not log.is_file() or log.stat().st_size == 0:
            raise ValueError(f'The real independent execution log is missing: {log}')
        evidence[name] = check_report(path, run, scenario, label, name)
        evidence[name]['executed_log_sha256'] = digest(log)
    earlier = workspace / 'archived_accounts' / scenario / label / 'accounts.json'
    recalculated = workspace / 'recomputed_accounts' / scenario / label / 'accounts.json'
    original, current = read_json(earlier), read_json(recalculated)
    if checked_digest(earlier) != record['account_sha256'] or current['checks']['passed'] is not True:
        raise ValueError('The completed account check failed or its original account changed')
    for name in ['production', 'raw_cost', 'final_cost', 'raw_carbon', 'final_carbon']:
        numerical_equal(original[name], current[name], name)
    checks.append({'scenario': scenario, 'label': label, 'passed': True,
                   'source_summary_sha256': record['summary_sha256'], 'physical_report': physical,
                   'final_cost_cny_kg': current['final_cost']['unit_cost_cny_kg'],
                   'final_carbon_g_mj': current['final_carbon']['intensity_g_mj'],
                   'current_independent_verifier_sources': tools, 'fresh_independent_reports': evidence,
                   'saved_execution_report_sha256': record['saved_validation_report_sha256'],
                   'recomputed_account_sha256': digest(recalculated)})
    print(json.dumps({'completed_verified_case': scenario, 'label': label}), flush=True)
if len(checks) != 18:
    raise ValueError('All eighteen actual completed case checks are required')
assets = [fixed_assets(directories, name) for name in PAIRED]
solver_workspace = workspace / 'solver_record_checks'
native(solver_workspace).mkdir(parents=True)
proofs = verify_solver_records(revision, manifest, solver_workspace, set(directories))
shutil.copyfile(solver_workspace / 'solver_records_verification.json', provenance / 'solver_records_verification.json')
hashes = {path.relative_to(native(revision)).as_posix(): digest(path)
          for path in sorted(native(revision).rglob('*'))
          if path.is_file() and path.name != 'SHA256SUMS.json' and '__pycache__' not in path.parts}
write_json(revision / 'SHA256SUMS.json', hashes)
tree = integrity(revision, manifest, workspace / 'final_integrity')
report = {'passed': True, 'optimization_executed': False, 'solver_license_required': False,
          'integrity': tree, 'verified_actual_runs': 18, 'fixed_production_asset_pairs': assets,
          'checks': checks, 'saved_solver_proof_checks': proofs,
          'revision_manifest_sha256': digest(revision / 'revision_manifest.json'),
          'physics_data_manifest_sha256': digest(args.original_manifest),
          'distribution_verification_binding': binding,
          'completion_scope': 'All eighteen independent case calculations completed in this workspace; their current report/input hashes and recomputed accounts are rechecked, followed by the six asset comparisons, all solver proofs and final distribution integrity.'}
write_json(workspace / 'verification_report.json', report)
print(json.dumps({'passed': True, 'verified_actual_runs': 18, 'revision_manifest_sha256': report['revision_manifest_sha256']}), flush=True)
