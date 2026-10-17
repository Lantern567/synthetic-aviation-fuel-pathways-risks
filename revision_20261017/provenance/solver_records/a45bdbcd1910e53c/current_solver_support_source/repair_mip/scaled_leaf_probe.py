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
parser.add_argument('--leaf', type=int, default=2)
args = parser.parse_args()
out = Path(args.runtime) / 'decomposed_runs' / args.scenario / 'baseline'
data = np.load(out / 'master_data.npz')
matrix = sparse.load_npz(out / 'master_matrix.npz')
proof = json.loads((out / 'partition_bound' / 'proof.json').read_text())
node = next(row for row in proof['nodes'] if row['id'] == args.leaf)
lower, upper = data['lb'].copy(), data['ub'].copy()
outside = sorted(set(proof['saf_build_columns']) - set(node['domain']))
lower[outside] = upper[outside] = 0
for column, value in node['fixed'].items():
    lower[int(column)] = upper[int(column)] = value
extra = sparse.coo_matrix((np.ones(len(node['domain'])), (np.zeros(len(node['domain']), dtype=int), node['domain'])), shape=(1, matrix.shape[1]))
matrix = sparse.vstack([matrix, extra], format='csc')
lhs, rhs = np.r_[data['lhs'], node['count_lower']], np.r_[data['rhs'], node['count_upper']]
column_factor = np.where(data['vtype'] == cp.COPT.CONTINUOUS, 1000., 1.)
continuous_rows = np.asarray((abs(matrix[:, data['vtype'] == cp.COPT.CONTINUOUS]).sum(axis=1) > 0)).ravel()
row_factor = np.where(continuous_rows, 1000., 1.)
scaled = sparse.diags(1 / row_factor) @ matrix @ sparse.diags(column_factor)
low_row = np.where(lhs > -1e29, lhs / row_factor, -cp.COPT.INFINITY)
high_row = np.where(rhs < 1e29, rhs / row_factor, cp.COPT.INFINITY)
low_col = np.where(lower > -1e29, lower / column_factor, -cp.COPT.INFINITY)
high_col = np.where(upper < 1e29, upper / column_factor, cp.COPT.INFINITY)
environment = cp.Envr()
model = environment.createModel('same_leaf_in_scaled_continuous_units')
model.loadMatrix(data['c'] * column_factor, scaled.tocsc(), low_row, high_row, low_col, high_col)
for name, value in {'LpMethod': 2, 'Crossover': 1, 'Threads': 4, 'TimeLimit': 120,
                    'FeasTol': 1e-8, 'DualTol': 1e-8}.items():
    model.setParam(name, value)
model.setLogFile(str(out / f'scaled_leaf_{args.leaf}.log'))
started = time.time()
model.solveLP()
record = dict(status=model.status, seconds=time.time() - started, has_solution=bool(model.getAttr('HasSol')),
              numerical_scaling='Original x = 1000*z for continuous columns; physical rows divided by 1000; integer columns/count rows unchanged',
              original_node=node, source_sha256={name: hashlib.sha256((out / name).read_bytes()).hexdigest() for name in ['master_data.npz', 'master_matrix.npz']})
if record['has_solution']:
    values = np.asarray(model.getValues()) * column_factor
    activity = matrix @ values
    record.update(objective_cny=float(model.ObjVal * 1e6),
                  constraint_residual=float(np.maximum(np.maximum(lhs - activity, activity - rhs), 0).max()),
                  bound_residual=float(np.maximum(np.maximum(lower - values, values - upper), 0).max()))
    np.savez_compressed(out / f'scaled_leaf_{args.leaf}_values.npz', values=values)
(out / f'scaled_leaf_{args.leaf}_status.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
print('REAL_EQUIVALENT_SCALING_RESULT', json.dumps(record), flush=True)
