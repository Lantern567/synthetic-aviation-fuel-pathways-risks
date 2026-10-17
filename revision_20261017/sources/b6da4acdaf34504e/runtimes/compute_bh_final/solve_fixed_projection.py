import json
import sys
from pathlib import Path

import coptpy as cp
import numpy as np
from scipy import sparse

base = Path(__file__).resolve().parent
out = base / 'decomposed_runs' / sys.argv[1] / sys.argv[2]
data = np.load(out / 'master_data.npz')
root = json.loads((out / 'root_lp_status.json').read_text())
assert root['status']==cp.COPT.OPTIMAL
root_values = np.load(out / 'root_lp_values.npz')['values']
threshold = float(sys.argv[3]) if len(sys.argv)>3 else 0.001
prefix = sys.argv[4] if len(sys.argv)>4 else 'rounded_lp'
integers = data['vtype']!=cp.COPT.CONTINUOUS
lower, upper = data['lb'].copy(), data['ub'].copy()
lower[integers] = upper[integers] = (root_values[integers]>threshold).astype(float)
environment = cp.Envr()
model = environment.createModel('fixed_projection_candidate')
model.loadMatrix(data['c'],sparse.load_npz(out / 'master_matrix.npz'),data['lhs'],data['rhs'],lower,upper)
for name,value in {'LpMethod':2,'Crossover':1,'Threads':8,'TimeLimit':1200,'FeasTol':1e-6,'DualTol':1e-7}.items():
    model.setParam(name,value)
model.setLogFile(str(out / f'{prefix}_retry.log'))
model.solveLP()
assert model.status==cp.COPT.OPTIMAL,model.status
values = np.asarray(model.getValues())
activity = sparse.load_npz(out / 'master_matrix.npz')@values
row_error = float(np.maximum(np.maximum(data['lhs']-activity,activity-data['rhs']),0).max())
assert row_error<=1e-3,row_error
objective = model.ObjVal*1e6
lower_bound = root['objective']
bound_source = 'root_lp_status.json'
for path in out.glob('strengthened*_root_status.json'):
    strengthened = json.loads(path.read_text())
    assert strengthened['status']==cp.COPT.OPTIMAL
    if strengthened['objective']>lower_bound:
        lower_bound,bound_source = strengthened['objective'],path.name
status = {'objective':objective,'lower_bound':lower_bound,'gap':max(0,(objective-lower_bound)/objective),'binary_rounding_threshold':threshold,'seconds':model.getAttr('SolvingTime'),'max_constraint_residual':row_error,'bound_source':bound_source}
np.savez_compressed(out / f'{prefix}_values.npz',values=values)
(out / f'{prefix}_status.json').write_text(json.dumps(status,indent=2))
print('FIXED_PROJECTION_COMPLETE',json.dumps(status),flush=True)
