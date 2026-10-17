import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path


base = Path(__file__).resolve().parent
scenario, label = sys.argv[1:3]
assert label == 'baseline'
output = base / 'job_records' / scenario / label
output.mkdir(parents=True, exist_ok=True)
source_paths = sorted(base.glob('*.py')) + sorted((base / 'inputs').rglob('*.*'))
sources = {str(path.relative_to(base)): hashlib.sha256(path.read_bytes()).hexdigest() for path in source_paths}
(output / 'input_source_sha256.json').write_text(json.dumps(sources, indent=2), encoding='utf-8')
run = base / 'verified_runs' / scenario / label
stages = [
    ('model', ['run_model.py', scenario, label, '--export-model']),
    ('projection', ['decompose_routes.py', scenario, label, '--export-only']),
    ('design', ['solve_master_lp.py', scenario, label, '0.001']),
    ('dispatch', ['repair_candidate.py', scenario, label, 'rounded']),
    ('certificate', ['accept_repaired.py', scenario, label, 'rounded']),
    ('export', ['run_model.py', scenario, label, '--certificate']),
    ('physics', ['validate_historical.py', scenario, label]),
    ('hydrogen_transport', ['validate_hydrogen_transport.py', str(run), '--out', str(run / 'hydrogen_transport_check')]),
    ('inventory_cost', ['validate_inventory_cost.py', str(run), '--out', str(run / 'inventory_cost_check')]),
]
if scenario.startswith('CCU-'):
    stages.append(('ccu_accounting', ['validate_ccu_accounts.py', '--run', str(run)]))
start = 'model'
if '--from-stage' in sys.argv:
    start = sys.argv[sys.argv.index('--from-stage') + 1]
names = [name for name, _ in stages]
assert start in names, start
history = []
for stage, command in stages[names.index(start):]:
    before = time.time()
    status = {'scenario': scenario, 'label': label, 'stage': stage, 'state': 'running', 'history': history}
    (output / 'status.json').write_text(json.dumps(status, indent=2), encoding='utf-8')
    print('REVISION_STAGE_STARTED', scenario, label, stage, flush=True)
    with (output / (stage + '.log')).open('w', encoding='utf-8') as stream:
        result = subprocess.run(['bash', str(base / 'python_copt.sh'), str(base / command[0]), *command[1:]],
                                cwd=base, stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT)
    history.append({'stage': stage, 'exit_code': result.returncode, 'seconds': time.time() - before})
    if result.returncode:
        status.update(state='failed', history=history)
        (output / 'status.json').write_text(json.dumps(status, indent=2), encoding='utf-8')
        raise RuntimeError(f'{scenario}/{label}: {stage} failed; inspect {output / (stage + ".log")}')
current = {str(path.relative_to(base)): hashlib.sha256(path.read_bytes()).hexdigest() for path in source_paths}
assert current == sources, 'Execution sources or inputs changed during the job'
status.update(state='complete', history=history)
(output / 'status.json').write_text(json.dumps(status, indent=2), encoding='utf-8')
print('REVISION_JOB_COMPLETE', scenario, label, flush=True)
