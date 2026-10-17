import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('scenario')
    parser.add_argument('label', choices=['baseline', 'summer_fixed'])
    parser.add_argument('--from-stage', default='model')
    args = parser.parse_args()
    base = Path(__file__).resolve().parent
    output = base / 'job_records' / args.scenario / args.label
    output.mkdir(parents=True, exist_ok=True)
    source_paths = sorted(base.glob('*.py')) + sorted((base / 'inputs').rglob('*.*'))
    sources = {str(path.relative_to(base)): digest(path) for path in source_paths}
    (output / 'input_source_sha256.json').write_text(json.dumps(sources, indent=2), encoding='utf-8')
    stages = [
        ('model', ['run_model.py', args.scenario, args.label, '--export-model']),
        ('projection', ['decompose_routes.py', args.scenario, args.label, '--export-only']),
        ('design', ['solve_master_lp.py', args.scenario, args.label, '0.001']),
        ('dispatch', ['repair_candidate.py', args.scenario, args.label, 'rounded']),
        ('certificate', ['accept_repaired.py', args.scenario, args.label, 'rounded']),
        ('export', ['run_model.py', args.scenario, args.label, '--certificate']),
        ('physics', ['validate_byproduct_physics.py' if args.scenario.startswith('DAC-BH-') else 'validate_physics.py', args.scenario, args.label]),
    ]
    if args.scenario.startswith('DAC-'):
        run = base / 'verified_runs' / args.scenario / args.label
        stages.append(('co2', ['validate_co2.py', str(run), '--out', str(run / 'co2_check')]))
    run = base / 'verified_runs' / args.scenario / args.label
    stages.append(('hydrogen_transport', ['validate_hydrogen_transport.py', str(run), '--out', str(run / 'hydrogen_transport_check')]))
    names = [name for name, _ in stages]
    if args.from_stage not in names:
        raise ValueError(args.from_stage)
    history = []
    for stage, command in stages[names.index(args.from_stage):]:
        before = time.time()
        status = {'scenario': args.scenario, 'label': args.label, 'stage': stage, 'state': 'running', 'history': history}
        (output / 'status.json').write_text(json.dumps(status, indent=2), encoding='utf-8')
        print('REVISION_STAGE_STARTED', args.scenario, args.label, stage, flush=True)
        with (output / (stage + '.log')).open('w', encoding='utf-8') as stream:
            result = subprocess.run(['bash', str(base / 'python_copt.sh'), str(base / command[0]), *command[1:]], cwd=base, stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT)
        history.append({'stage': stage, 'exit_code': result.returncode, 'seconds': time.time() - before})
        if result.returncode:
            status.update(state='failed', history=history)
            (output / 'status.json').write_text(json.dumps(status, indent=2), encoding='utf-8')
            raise RuntimeError(f'{args.scenario}/{args.label}: {stage} failed; inspect {output / (stage + ".log")}')
    current = {str(path.relative_to(base)): digest(path) for path in source_paths}
    if current != sources:
        raise RuntimeError('Inputs or execution sources changed during this job')
    status.update(state='complete', history=history)
    (output / 'status.json').write_text(json.dumps(status, indent=2), encoding='utf-8')
    print('REVISION_JOB_COMPLETE', args.scenario, args.label, flush=True)


if __name__ == '__main__':
    main()
