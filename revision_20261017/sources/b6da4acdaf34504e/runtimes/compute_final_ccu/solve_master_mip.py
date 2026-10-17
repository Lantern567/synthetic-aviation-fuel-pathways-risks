import json
import sys
import time
from pathlib import Path

import coptpy as cp
import numpy as np
from scipy import sparse

base = Path(__file__).resolve().parent
out = base / 'decomposed_runs' / sys.argv[1] / sys.argv[2]
direct = '--direct' in sys.argv
warm = '--warm' in sys.argv
prefix = 'mip_warm' if warm else ('mip_direct' if direct else 'mip')
data = np.load(out / 'master_data.npz')
matrix = sparse.load_npz(out / 'master_matrix.npz')
environment = cp.Envr()
model = environment.createModel('projected_integer_design')
model.loadMatrix(data['c'], matrix, data['lhs'], data['rhs'], data['lb'], data['ub'], data['vtype'].tolist())
variables = model.getVars()
initial = np.load(out / ('rounded_t003_lp_values.npz' if direct or warm else 'rounded_lp_values.npz'))['values']
activity = matrix @ initial
assert np.maximum(np.maximum(data['lhs']-activity, activity-data['rhs']), 0).max() <= 1e-3
model.setMipStart(variables, initial.tolist())
model.loadMipStart()
for name, value in {'LpMethod':2, 'Crossover':1, 'Threads':8, 'TimeLimit':1800, 'RelGap':0.003, 'FeasTol':1e-7, 'IntTol':1e-7}.items():
    model.setParam(name, value)
if direct or warm:
    for name,value in {'Presolve':0,'PreRootHeurLevel':0,'RootCutRounds':0,'HeurLevel':1}.items():
        model.setParam(name,value)
model.setLogFile(str(out / (prefix+'_design.log')))
started = time.time()
if warm:
    model.setParam('Presolve',-1)
    model.solveLP()
    assert model.status==cp.COPT.OPTIMAL,model.status
    model.writeBasis(str(out / 'warm_root.bas'))
    model.setParam('Presolve',0)
    model.readBasis(str(out / 'warm_root.bas'))
    model.setParam('LpMethod',1)
model.solve()
assert model.getAttr('HasSol'), model.status
values = np.asarray(model.getValues())
activity = matrix @ values
row_error = float(np.maximum(np.maximum(data['lhs']-activity, activity-data['rhs']), 0).max())
bound_error = float(np.maximum(np.maximum(data['lb']-values, values-data['ub']), 0).max())
integers = data['vtype'] != cp.COPT.CONTINUOUS
integer_error = float(np.abs(values[integers]-np.rint(values[integers])).max())
assert row_error <= 1e-3 and bound_error <= 1e-5 and integer_error <= 1e-6, (row_error, bound_error, integer_error)
root = json.loads((out / 'root_lp_status.json').read_text())
objective = model.ObjVal*1e6
lower_bound = max(model.getAttr('ObjBound')*1e6, root['objective'])
status = {'status':model.status, 'objective':objective, 'lower_bound':lower_bound, 'gap':max(0, (objective-lower_bound)/abs(objective)), 'seconds':model.getAttr('SolvingTime'), 'wall_seconds':time.time()-started, 'max_constraint_residual':row_error, 'max_bound_residual':bound_error, 'max_integer_violation':integer_error}
np.savez_compressed(out / f'{prefix}_values.npz', values=values)
(out / f'{prefix}_status.json').write_text(json.dumps(status, indent=2))
print('PROJECTED_INTEGER_COMPLETE', json.dumps(status), flush=True)
