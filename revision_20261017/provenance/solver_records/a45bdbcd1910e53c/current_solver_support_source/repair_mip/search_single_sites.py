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
parser.add_argument('--maximum-sites', type=int, default=20)
parser.add_argument('--threads', type=int, default=8)
args = parser.parse_args()
out = Path(args.runtime) / 'decomposed_runs' / args.scenario / 'baseline'
data = np.load(out / 'master_data.npz')
matrix = sparse.load_npz(out / 'master_matrix.npz')
diagnostics = json.loads((out / 'binary_design_diagnostics.json').read_text())
facilities = {record['column']: record['name'] for record in diagnostics if record['name'].startswith('facility_')}
integers = np.flatnonzero(data['vtype'] != cp.COPT.CONTINUOUS)
proof = json.loads((out / 'partition_bound/proof.json').read_text())
leaves = sorted([node for node in proof['nodes'] if 'children' not in node and node['count_lower'] == node['count_upper'] == 1],
                key=lambda node: node['lower_bound_cny'])
pool = []
for leaf in leaves:
    ancestor = leaf
    while not (out / f'partition_bound/leaf_{ancestor["id"]}_values.npz').exists() and ancestor['parent'] is not None:
        ancestor = proof['nodes'][ancestor['parent']]
    values = np.load(out / f'partition_bound/leaf_{ancestor["id"]}_values.npz')['values']
    pool.extend(sorted(leaf['domain'], key=lambda column: values[column], reverse=True))
pool = list(dict.fromkeys(pool))[:args.maximum_sites]
fingerprint = {name: hashlib.sha256((out / name).read_bytes()).hexdigest()
               for name in ['master_data.npz', 'master_matrix.npz', 'root_lp_status.json']}
root_bound = json.loads((out / 'root_lp_status.json').read_text())['objective']
factor = np.where(data['vtype'] == cp.COPT.CONTINUOUS, 1000., 1.)
row_factor = np.where(np.asarray(abs(matrix[:, data['vtype'] == cp.COPT.CONTINUOUS]).sum(axis=1)).ravel() > 0, 1000., 1.)
transformed = (sparse.diags(1 / row_factor) @ matrix @ sparse.diags(factor)).tocsc()
lhs = np.where(data['lhs'] > -1e29, data['lhs'] / row_factor, -cp.COPT.INFINITY)
rhs = np.where(data['rhs'] < 1e29, data['rhs'] / row_factor, cp.COPT.INFINITY)
environment = cp.Envr()
history = []
for ordinal, opened in enumerate(pool):
    lower, upper = data['lb'].copy(), data['ub'].copy()
    lower[integers] = upper[integers] = 1
    lower[list(facilities)] = upper[list(facilities)] = 0
    lower[opened] = upper[opened] = 1
    prefix = f'mip_single_{ordinal}'
    model = environment.createModel(prefix)
    model.loadMatrix(data['c'] * factor, transformed, lhs, rhs,
                     np.where(lower > -1e29, lower / factor, -cp.COPT.INFINITY),
                     np.where(upper < 1e29, upper / factor, cp.COPT.INFINITY))
    for name, value in {'LpMethod': 2, 'Crossover': 1, 'Threads': args.threads, 'TimeLimit': 90,
                        'FeasTol': 1e-8, 'DualTol': 1e-8}.items():
        model.setParam(name, value)
    model.setLogFile(str(out / (prefix + '.log')))
    started = time.time()
    model.solveLP()
    status = dict(status=model.status, has_solution=bool(model.getAttr('HasSol')),
                  opened_facility=facilities[opened], seconds=time.time() - started,
                  lower_bound=root_bound, source_sha256=fingerprint)
    if status['has_solution']:
        values = np.asarray(model.getValues()) * factor
        activity = matrix @ values
        status.update(max_constraint_residual=float(np.maximum(np.maximum(data['lhs'] - activity, activity - data['rhs']), 0).max()),
                      max_bound_residual=float(np.maximum(np.maximum(lower - values, values - upper), 0).max()),
                      max_integer_violation=float(np.abs(values[integers] - np.rint(values[integers])).max()))
        if status['max_constraint_residual'] <= 1e-3 and status['max_bound_residual'] <= 1e-5 and status['max_integer_violation'] <= 1e-6:
            objective = float(data['c'] @ values * 1e6)
            status.update(objective=objective, gap=max(0, (objective - root_bound) / objective))
            np.savez_compressed(out / (prefix + '_values.npz'), values=values)
            (out / (prefix + '_status.json')).write_text(json.dumps(status, indent=2), encoding='utf-8')
    history.append(dict(prefix=prefix, **status))
    (out / 'single_site_status.json').write_text(json.dumps(history, indent=2), encoding='utf-8')
    print('REAL_SINGLE_SITE', json.dumps(dict(prefix=prefix, **status)), flush=True)
    del model
assert fingerprint == {name: hashlib.sha256((out / name).read_bytes()).hexdigest() for name in fingerprint}
