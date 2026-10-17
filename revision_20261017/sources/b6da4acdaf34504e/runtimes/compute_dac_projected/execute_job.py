import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


parser = argparse.ArgumentParser()
parser.add_argument('scenario')
parser.add_argument('label', choices=['baseline', 'summer_fixed'])
parser.add_argument('--from-stage', default='model')
args = parser.parse_args()
base = Path(__file__).resolve().parent
record = base / 'job_records' / args.scenario / args.label
record.mkdir(parents=True, exist_ok=True)
run = base / 'verified_runs' / args.scenario / args.label
mps = base / 'runs' / args.scenario / args.label / 'model.mps.gz'
proof = base / 'decomposed_runs' / args.scenario / args.label
source_paths = sorted(base.glob('*.py')) + sorted(path for path in (base / 'inputs').rglob('*') if path.is_file())
hashes = {str(path.relative_to(base)): digest(path) for path in source_paths}
(record / 'input_source_sha256.json').write_text(json.dumps(hashes, indent=2), encoding='utf-8')
stages = [
    ('model', ['run_model.py', args.scenario, args.label, '--export-model']),
    ('projection', ['project_routes.py', '--source', str(mps), '--out', str(proof),
                    '--stage', 'all', '--lp-time', '900', '--repair-time', '1200',
                    '--threads', '4', '--round-threshold', '0.001']),
    ('export', ['run_model.py', args.scenario, args.label, '--certificate']),
    ('physics', ['validate_byproduct_physics.py' if args.scenario.startswith('DAC-BH-') else 'validate_physics.py', args.scenario, args.label]),
    ('co2', ['validate_co2.py', str(run), '--out', str(run / 'independent_co2')]),
    ('hydrogen_transport', ['validate_hydrogen_transport.py', str(run), '--out', str(run / 'independent_hydrogen_transport')]),
    ('inventory_cost', ['validate_inventory_cost.py', str(run), '--out', str(run / 'independent_inventory_cost')]),
]
names = [name for name, _ in stages]
if args.from_stage not in names:
    raise ValueError(args.from_stage)
history = []
for stage, command in stages[names.index(args.from_stage):]:
    start = time.time()
    status = {'scenario': args.scenario, 'label': args.label, 'stage': stage, 'state': 'running', 'history': history}
    (record / 'status.json').write_text(json.dumps(status, indent=2), encoding='utf-8')
    reused = False
    if stage == 'model' and mps.exists() and (mps.parent / 'MODEL_EXPORTED').exists():
        reused = True
    if stage == 'projection' and (proof / 'certificate.json').exists():
        certificate = json.loads((proof / 'certificate.json').read_text())
        if not certificate['passed'] or certificate['gap'] > .01 or certificate['source_sha256'] != digest(mps):
            raise ValueError('Reused proof does not certify the selected full model')
        reused = True
    print('REVISION_STAGE', args.scenario, args.label, stage, 'reused' if reused else 'started', flush=True)
    code = 0
    if not reused:
        with (record / (stage + '.log')).open('w', encoding='utf-8') as stream:
            result = subprocess.run(['bash', str(base / 'python_copt.sh'), str(base / command[0]), *command[1:]],
                                    cwd=base, stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT)
        code = result.returncode
    history.append({'stage': stage, 'exit_code': code, 'seconds': time.time() - start, 'reused_verified_artifact': reused})
    if code:
        status.update(state='failed', history=history)
        (record / 'status.json').write_text(json.dumps(status, indent=2), encoding='utf-8')
        raise RuntimeError(f'{args.scenario}/{args.label}: {stage} failed')
if {str(path.relative_to(base)): digest(path) for path in source_paths} != hashes:
    raise RuntimeError('Execution sources or inputs changed during the job')
status.update(state='complete', history=history)
(record / 'status.json').write_text(json.dumps(status, indent=2), encoding='utf-8')
print('REVISION_JOB_COMPLETE', args.scenario, args.label, flush=True)
