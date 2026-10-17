import argparse
import hashlib
import json
import time
from pathlib import Path

import coptpy as cp
import numpy as np
from scipy import sparse


parser = argparse.ArgumentParser()
parser.add_argument('runtime')
parser.add_argument('scenario')
parser.add_argument('--seed', default='mip_threshold_0p05')
args = parser.parse_args()
out = Path(args.runtime) / 'decomposed_runs' / args.scenario / 'baseline'
data = np.load(out / 'master_data.npz')
matrix = sparse.load_npz(out / 'master_matrix.npz')
diagnostics = json.loads((out / 'binary_design_diagnostics.json').read_text())
facilities = {record['column']: record['name'] for record in diagnostics if record['name'].startswith('facility_')}
integers = np.flatnonzero(data['vtype'] != cp.COPT.CONTINUOUS)
best_values = np.load(out / (args.seed + '_values.npz'))['values']
best_cost = float(data['c'] @ best_values * 1e6)
best_prefix = args.seed
root_bound = json.loads((out / 'root_lp_status.json').read_text())['objective']
fingerprint = {name: hashlib.sha256((out / name).read_bytes()).hexdigest()
               for name in ['master_data.npz', 'master_matrix.npz', 'root_lp_status.json']}
environment = cp.Envr()
history = []
for sweep in range(6):
    start_cost = best_cost
    active = [column for column in facilities if best_values[column] > .5]
    starting_values = best_values.copy()
    for ordinal, column in enumerate(active):
        selection = np.rint(starting_values[integers])
        selection[np.flatnonzero(integers == column)] = 0
        lower, upper = data['lb'].copy(), data['ub'].copy()
        lower[integers] = upper[integers] = selection
        prefix = f'mip_greedy_{sweep}_{ordinal}'
        model = environment.createModel(prefix)
        model.loadMatrix(data['c'], matrix, data['lhs'], data['rhs'], lower, upper)
        for name, value in {'LpMethod': 2, 'Crossover': 1, 'Threads': 2, 'TimeLimit': 180,
                            'FeasTol': 1e-7, 'DualTol': 1e-7}.items():
            model.setParam(name, value)
        model.setLogFile(str(out / (prefix + '.log')))
        started = time.time()
        model.solveLP()
        status = dict(status=model.status, has_solution=bool(model.getAttr('HasSol')),
                      closed_facility=facilities[column], seconds=time.time() - started,
                      lower_bound=root_bound, source_sha256=fingerprint)
        if status['has_solution']:
            values = np.asarray(model.getValues())
            activity = matrix @ values
            status.update(max_constraint_residual=float(np.maximum(np.maximum(data['lhs'] - activity, activity - data['rhs']), 0).max()),
                          max_bound_residual=float(np.maximum(np.maximum(data['lb'] - values, values - data['ub']), 0).max()),
                          max_integer_violation=float(np.abs(values[integers] - np.rint(values[integers])).max()))
            assert status['max_constraint_residual'] <= 1e-3 and status['max_bound_residual'] <= 1e-5 and status['max_integer_violation'] <= 1e-6, status
            objective = float(data['c'] @ values * 1e6)
            status.update(objective=objective, gap=max(0, (objective - root_bound) / objective))
            if objective < best_cost - 1:
                best_cost, best_values, best_prefix = objective, values.copy(), prefix
                np.savez_compressed(out / (prefix + '_values.npz'), values=values)
                (out / (prefix + '_status.json')).write_text(json.dumps(status, indent=2), encoding='utf-8')
                status['improved_best'] = True
        history.append(dict(prefix=prefix, **status))
        (out / 'greedy_design_status.json').write_text(json.dumps(dict(best_prefix=best_prefix, objective=best_cost, history=history), indent=2), encoding='utf-8')
        print('ACTUAL_GREEDY_DESIGN', json.dumps(dict(prefix=prefix, **status)), flush=True)
        del model
    if best_cost >= start_cost - 1:
        break
assert fingerprint == {name: hashlib.sha256((out / name).read_bytes()).hexdigest() for name in fingerprint}
print('ACTUAL_GREEDY_FINISHED', best_prefix, best_cost, flush=True)
