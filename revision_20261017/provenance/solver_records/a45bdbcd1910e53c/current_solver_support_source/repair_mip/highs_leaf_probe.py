import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import scipy
from scipy import sparse
from scipy.optimize import linprog


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
saf = set(proof['saf_build_columns'])
outside = sorted(saf - set(node['domain']))
lower[outside] = upper[outside] = 0
for column, value in node['fixed'].items():
    lower[int(column)] = upper[int(column)] = value
extra = sparse.coo_matrix((np.ones(len(node['domain'])), (np.zeros(len(node['domain']), dtype=int), node['domain'])), shape=(1, matrix.shape[1]))
matrix = sparse.vstack([matrix, extra], format='csc')
lhs, rhs = np.r_[data['lhs'], node['count_lower']], np.r_[data['rhs'], node['count_upper']]
equality = lhs == rhs
low = ~equality & (lhs > -1e29)
up = ~equality & (rhs < 1e29)
a_eq, b_eq = matrix[equality], rhs[equality]
a_ub, b_ub = sparse.vstack([matrix[up], -matrix[low]], format='csc'), np.r_[rhs[up], -lhs[low]]
lower[lower <= -1e29] = -np.inf
upper[upper >= 1e29] = np.inf
started = time.time()
result = linprog(data['c'], A_ub=a_ub, b_ub=b_ub, A_eq=a_eq, b_eq=b_eq,
                 bounds=np.column_stack([lower, upper]), method='highs-ipm',
                 options={'time_limit': 180, 'threads': 4, 'disp': True, 'presolve': True,
                          'primal_feasibility_tolerance': 1e-7, 'dual_feasibility_tolerance': 1e-7,
                          'ipm_optimality_tolerance': 1e-10})
record = dict(solver='SciPy/HiGHS-IPM', scipy_version=scipy.__version__, status=result.status,
              message=result.message, success=result.success, seconds=time.time() - started, original_node=node,
              master_sha256={name: hashlib.sha256((out / name).read_bytes()).hexdigest() for name in ['master_data.npz', 'master_matrix.npz']})
if result.success:
    values = result.x
    activity = matrix @ values
    finite_l, finite_u = np.isfinite(lower), np.isfinite(upper)
    dual = float(b_ub @ result.ineqlin.marginals + b_eq @ result.eqlin.marginals
                 + lower[finite_l] @ result.lower.marginals[finite_l]
                 + upper[finite_u] @ result.upper.marginals[finite_u])
    stationarity = data['c'] - a_ub.T @ result.ineqlin.marginals - a_eq.T @ result.eqlin.marginals - result.lower.marginals - result.upper.marginals
    record.update(objective_cny=float(result.fun * 1e6), dual_objective_cny=dual * 1e6,
                  constraint_residual=float(np.maximum(np.maximum(lhs - activity, activity - rhs), 0).max()),
                  bound_residual=float(np.maximum(np.maximum(lower - values, values - upper), 0).max()),
                  dual_stationarity_error=float(np.abs(stationarity).max()))
    np.savez_compressed(out / f'highs_leaf_{args.leaf}_values.npz', values=values,
                        equality_marginals=result.eqlin.marginals, inequality_marginals=result.ineqlin.marginals,
                        lower_marginals=result.lower.marginals, upper_marginals=result.upper.marginals)
(out / f'highs_leaf_{args.leaf}_status.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
print('REAL_ALTERNATIVE_LP_RESULT', json.dumps(record), flush=True)
