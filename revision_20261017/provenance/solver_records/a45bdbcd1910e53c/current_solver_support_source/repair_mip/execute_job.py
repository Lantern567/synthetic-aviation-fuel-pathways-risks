import argparse
import hashlib
import json
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('scenario')
    parser.add_argument('label', choices=['baseline'])
    parser.add_argument('--warm-probe-mip', action='store_true')
    parser.add_argument('--partition-existing', action='store_true')
    parser.add_argument('--verify-existing', action='store_true')
    parser.add_argument('--partition-search', action='store_true')
    parser.add_argument('--threshold-search', action='store_true')
    parser.add_argument('--candidate', default='mip_threshold_0p05')
    args = parser.parse_args()
    task = Path(__file__).resolve().parent
    runtime = task.parents[1] / 'compute_bh_final'
    results = runtime / 'decomposed_runs' / args.scenario / args.label
    records = task / 'job_records' / args.scenario / args.label
    records.mkdir(parents=True, exist_ok=True)
    original_status = runtime / 'job_records' / args.scenario / args.label / 'status.json'
    if original_status.exists():
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        shutil.copy2(original_status, records / f'prior_attempt_{stamp}.json')
    tracked = [runtime / 'runs' / args.scenario / args.label / 'model.mps.gz',
               results / 'master_data.npz', results / 'master_matrix.npz',
               results / 'root_lp_status.json'] + sorted(runtime.glob('*.py'))
    hashes = {str(path.relative_to(runtime)): hashlib.sha256(path.read_bytes()).hexdigest() for path in tracked}
    (records / 'input_source_sha256.json').write_text(json.dumps(hashes, indent=2), encoding='utf-8')
    assert sum([args.warm_probe_mip, args.partition_existing, args.verify_existing, args.partition_search, args.threshold_search]) <= 1
    prefix = 'mip_partition' if args.partition_existing else ('mip_no_root_cuts' if args.warm_probe_mip else 'mip')
    if args.partition_existing:
        design_command = [str(task / 'validate_partition.py'), str(runtime), args.scenario, '--adopt']
    elif args.warm_probe_mip:
        design_command = [str(task / 'solve_probe_mip.py'), str(runtime), args.scenario]
    else:
        design_command = ['solve_master_mip.py', args.scenario, args.label]
    stages = [
        ('integer_design', design_command),
        ('full_dispatch', ['repair_candidate.py', args.scenario, args.label, prefix]),
        ('certificate', ['accept_repaired.py', args.scenario, args.label, prefix]),
        ('export_and_validation', ['execute_job.py', args.scenario, args.label, '--from-stage', 'export']),
    ]
    if args.verify_existing:
        run = runtime / 'verified_runs' / args.scenario / args.label
        assert (run / 'summary.json').exists() and not (run / 'EXPORT_IN_PROGRESS').exists()
        prefix = 'verify_existing'
        stages = [
            ('physics', [str(task / 'validate_historical.py'), args.scenario, args.label, '--runtime', str(runtime)]),
            ('hydrogen_transport', ['validate_hydrogen_transport.py', str(run), '--out', str(run / 'hydrogen_transport_check')]),
            ('inventory_cost', ['validate_inventory_cost.py', str(run), '--out', str(run / 'inventory_cost_check')]),
        ]
        if args.scenario.startswith('CCU-'):
            stages.append(('ccu_accounting', ['validate_ccu_accounts.py', '--run', str(run)]))
    if args.partition_search or args.threshold_search or args.partition_existing:
        prefix = 'mip_partition'
        stages = []
        candidate = 'mip_best_search' if args.threshold_search else args.candidate
        if args.threshold_search:
            stages.extend([
                ('binary_metadata', [str(task / 'inspect_design.py'), str(runtime), args.scenario]),
                ('threshold_designs', [str(task / 'probe_thresholds.py'), str(runtime), args.scenario,
                                       '--thresholds', '.003', '.01', '.03', '.05', '.1', '.2']),
                ('candidate_selection', [str(task / 'choose_candidate.py'), str(runtime), args.scenario]),
            ])
        bound = [str(task / 'partition_parallel.py'), str(runtime), args.scenario, '--candidate', candidate,
                 '--maximum-nodes', '200', '--target-gap', '.0099', '--workers', '4', '--threads', '4', '--lp-method', '2', '--crossover', '1', '--continuous-unit', '1000']
        if args.partition_search and (results / 'partition_bound' / 'proof.json').exists():
            bound.append('--resume')
        run = runtime / 'verified_runs' / args.scenario / args.label
        if not args.partition_existing:
            stages.append(('exhaustive_integer_bound', bound))
        stages.extend([
            ('partition_validation', [str(task / 'validate_partition.py'), str(runtime), args.scenario, '--adopt']),
            ('full_dispatch', ['repair_candidate.py', args.scenario, args.label, prefix]),
            ('certificate', ['accept_repaired.py', args.scenario, args.label, prefix]),
            ('export', ['run_model.py', args.scenario, args.label, '--certificate']),
            ('physics', [str(task / 'validate_historical.py'), args.scenario, args.label, '--runtime', str(runtime)]),
            ('hydrogen_transport', ['validate_hydrogen_transport.py', str(run), '--out', str(run / 'hydrogen_transport_check')]),
            ('inventory_cost', ['validate_inventory_cost.py', str(run), '--out', str(run / 'inventory_cost_check')]),
        ])
        if args.scenario.startswith('CCU-'):
            stages.append(('ccu_accounting', ['validate_ccu_accounts.py', '--run', str(run)]))
    history = []

    def write_status(state, stage):
        status = {'scenario': args.scenario, 'label': args.label, 'state': state, 'stage': stage,
                  'source_runtime': str(runtime), 'attempt': prefix, 'history': history}
        text = json.dumps(status, indent=2)
        (records / 'status.json').write_text(text, encoding='utf-8')
        original_status.write_text(text, encoding='utf-8')
        return status

    for stage, command in stages:
        write_status('running', stage)
        start = time.time()
        print('REVISION_STAGE_STARTED', args.scenario, args.label, stage, flush=True)
        with (records / (stage + '.log')).open('w', encoding='utf-8') as log:
            result = subprocess.run(['bash', str(runtime / 'python_copt.sh'), str(runtime / command[0]), *command[1:]],
                                    cwd=runtime, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
        history.append({'stage': stage, 'exit_code': result.returncode, 'seconds': time.time() - start})
        if result.returncode:
            write_status('failed', stage)
            raise RuntimeError(f'{args.scenario}: {stage} failed; inspect {records / (stage + ".log")}')
    current = {str(path.relative_to(runtime)): hashlib.sha256(path.read_bytes()).hexdigest() for path in tracked}
    assert current == hashes, 'The frozen model or sources changed during the comparison solve'
    status = write_status('complete', 'export_and_validation')
    print('REVISION_JOB_COMPLETE', args.scenario, args.label, json.dumps(status), flush=True)


if __name__ == '__main__':
    main()
