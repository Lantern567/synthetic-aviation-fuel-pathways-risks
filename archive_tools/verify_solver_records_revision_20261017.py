import argparse
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
from scipy import sparse

from revision_20261017_common import copy_checked, digest, native, read_json, revision_paths, safe_path, write_json


def verify_solver_records(revision, manifest, workspace, selected=None):
    source = revision / manifest['solver_records_directory']
    if digest(source / 'solver_records_manifest.json') != manifest['solver_records_manifest_sha256']:
        raise ValueError('The actual saved solver-record manifest changed')
    evidence = read_json(source / 'solver_records_manifest.json')
    for item in evidence['files']:
        if digest(safe_path(source, item['path'])) != item['sha256']:
            raise ValueError(f'An original proof record changed: {item["path"]}')
    actual = {(item['scenario'], item['label']): item for item in manifest['runs']}
    certificates = {item['original_path']: item['payload_sha256'] for item in manifest['packed_files']}
    records = evidence['cases'] if selected is None else [item for item in evidence['cases'] if (item['scenario'], item['label']) in selected]
    if selected is not None and len(records) != len(selected):
        raise ValueError('The actual saved bound evidence is missing for a selected result')
    checks = []
    for item in records:
        scenario, label = item['scenario'], item['label']
        run = source / 'records' / scenario / label
        original = actual[scenario, label]
        if item['summary_sha256'] != original['summary_sha256']:
            raise ValueError('The original proof belongs to another saved result')
        expected_certificate = certificates['saved_results/' + scenario + '/' + label + '/certificate.json']
        if digest(run / 'certificate.json') != expected_certificate or expected_certificate != item['certificate_sha256']:
            raise ValueError('The full-model certificate differs from the actual saved result')
        certificate, root = read_json(run / 'certificate.json'), read_json(run / 'root_lp_status.json')
        if root['status'] != 1 or not root['has_solution'] or not certificate['passed']:
            raise ValueError('The archived root LP and full-model dispatch must be accepted')
        data = np.load(native(run / 'master_data.npz'))
        matrix = sparse.load_npz(native(run / 'master_matrix.npz'))
        values = np.load(native(run / 'root_lp_values.npz'))['values']
        if matrix.shape != (len(data['lhs']), len(data['c'])) or len(values) != matrix.shape[1]:
            raise ValueError('The archived root LP dimensions differ')
        activity = matrix @ values
        row_error = float(np.maximum(np.maximum(data['lhs'] - activity, activity - data['rhs']), 0).max(initial=0))
        bound_error = float(np.maximum(np.maximum(data['lb'] - values, values - data['ub']), 0).max(initial=0))
        objective_error = abs(float(data['c'] @ values) * 1e6 - root['objective'])
        # LP目标曾缩放1e6，保存的原始变量和求解器内部目标在还原CNY后按相对精度核对。
        objective_match = bool(np.isclose(float(data['c'] @ values) * 1e6, root['objective'], rtol=1e-10, atol=1))
        if row_error > 1e-3 or bound_error > 1e-5 or not objective_match:
            raise ValueError(f'The archived root LP primal record does not reproduce its constraints/objective: {scenario}/{label}: {row_error}, {bound_error}, {objective_error}')
        gap = max(0, (certificate['objective'] - certificate['lower_bound']) / abs(certificate['objective']))
        if not np.isclose(gap, certificate['gap'], atol=1e-12, rtol=1e-12) or gap > .01:
            raise ValueError('The accepted solver gap does not reproduce the original full-model certificate')
        partition = None
        if item['partition_proof_archived']:
            runtime = workspace / scenario
            destination = runtime / 'decomposed_runs' / scenario / label
            for file in native(run).rglob('*'):
                if file.is_file():
                    copy_checked(file, destination / file.relative_to(native(run)))
            model = source / 'original_models' / scenario / label / 'model.mps.gz'
            if digest(model) != certificate['source_sha256']:
                raise ValueError('The complete original MPS differs from its partition proof')
            copy_checked(model, runtime / 'runs' / scenario / label / 'model.mps.gz')
            tool = revision / 'verification_source/validate_partition.py'
            log = workspace / (scenario + '_partition.log')
            domain_tool = revision / 'verification_source/review_partition_domains.py'
            domain_report = workspace / (scenario + '_domain_review.json')
            with native(log).open('w', encoding='utf-8') as output:
                subprocess.run([sys.executable, '-X', 'utf8', str(native(domain_tool)), '--proof', str(native(destination / 'partition_bound/proof.json')),
                                '--out', str(native(domain_report))], stdout=output, stderr=subprocess.STDOUT, check=True)
                subprocess.run([sys.executable, '-X', 'utf8', str(native(tool)), str(native(runtime)), scenario], stdout=output, stderr=subprocess.STDOUT, check=True)
            partition = read_json(destination / 'partition_bound/validation.json')
            partition['independent_domain_audit'] = read_json(domain_report)
            if not partition['passed'] or not np.isclose(partition['global_lower_bound_cny'], certificate['lower_bound'], rtol=1e-12, atol=1e-3):
                raise ValueError('The exhaustive partition bound differs from its accepted certificate')
            bound_source = 'Exhaustive integer-design partition with all saved optimal-LP leaf records'
        else:
            bound_sources = []
            if np.isclose(root['objective'], certificate['lower_bound'], rtol=1e-12, atol=1e-3):
                bound_sources.append('root_lp_status.json')
            for status_path in native(run).glob('*status*.json'):
                status = read_json(status_path)
                if 'lower_bound' in status and np.isclose(status['lower_bound'], certificate['lower_bound'], rtol=1e-12, atol=1e-3):
                    bound_sources.append(status_path.name)
            if not bound_sources:
                raise ValueError(f'The accepted lower bound is missing from its original saved solver-status evidence: {scenario}/{label}')
            bound_source = bound_sources
        checks.append({'scenario': scenario, 'label': label, 'passed': True,
                       'summary_sha256': item['summary_sha256'], 'certificate_sha256': expected_certificate,
                       'root_lp_primal_max_row_error': row_error, 'root_lp_primal_max_bound_error': bound_error,
                       'root_lp_objective_error_cny': objective_error, 'full_model_relative_gap': gap,
                       'root_lp_objective_relative_error': objective_error / abs(root['objective']),
                       'bound_status_sources': bound_source, 'partition_validation': partition})
    report = {'passed': True, 'optimization_executed': False, 'solver_license_required': False,
              'verified_actual_certificates': len(checks), 'checks': checks,
              'scope': 'Replay saved LP primal constraints and objectives, recorded optimal-LP/global-bound statuses, original full-model certificate gaps and exhaustive integer-partition coverage where used. Independent dual vectors were not saved.'}
    write_json(workspace / 'solver_records_verification.json', report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive-root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--workspace', type=Path, required=True)
    args = parser.parse_args()
    _, revision, manifest = revision_paths(args.archive_root)
    if native(args.workspace).exists() or args.workspace.resolve().is_relative_to(revision):
        raise ValueError('Choose a new solver-record verification workspace')
    native(args.workspace).mkdir(parents=True)
    result = verify_solver_records(revision, manifest, args.workspace.resolve())
    print(json.dumps({'passed': result['passed'], 'verified_actual_certificates': result['verified_actual_certificates']}))
