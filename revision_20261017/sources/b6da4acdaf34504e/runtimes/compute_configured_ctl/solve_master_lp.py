import json
import sys
from pathlib import Path

import coptpy as cp
import numpy as np
from scipy import sparse

base = Path(__file__).resolve().parent
out = base / 'decomposed_runs' / sys.argv[1] / sys.argv[2]
threshold = float(sys.argv[3]) if len(sys.argv)>3 else 1e-7
data = np.load(out / 'master_data.npz')
environment = cp.Envr()
model = environment.createModel('master_root')
model.loadMatrix(data['c'],sparse.load_npz(out / 'master_matrix.npz'),data['lhs'],data['rhs'],data['lb'],data['ub'],data['vtype'].tolist())
for name,value in {'LpMethod':2,'Threads':8,'Crossover':1,'TimeLimit':900,'FeasTol':1e-7,'DualTol':1e-7}.items():
    model.setParam(name,value)
model.setLogFile(str(out / 'root_lp.log'))
model.solveLP()
status = {'status':model.status,'has_solution':bool(model.getAttr('HasSol')),'seconds':model.getAttr('SolvingTime')}
if status['has_solution']:
    status['objective'] = model.ObjVal*1e6
    np.savez_compressed(out / 'root_lp_values.npz',values=np.asarray(model.getValues()))
(out / 'root_lp_status.json').write_text(json.dumps(status,indent=2))
print('ROOT_LP_FINISHED',json.dumps(status),flush=True)
assert model.status==cp.COPT.OPTIMAL,status
bound = model.ObjVal*1e6
fixed = model.clone()
fixed.setLogFile(str(out / 'rounded_lp.log'))
fixed.setParam('Crossover',1)
fixed.setParam('FeasTol',1e-7)
fixed_vars = fixed.getVars()
indices = np.flatnonzero(data['vtype']!=cp.COPT.CONTINUOUS)
rounded = (np.asarray(model.getValues())[indices]>threshold).astype(float)
fixed.setInfo(cp.COPT.Info.LB,[fixed_vars[int(i)] for i in indices],rounded.tolist())
fixed.setInfo(cp.COPT.Info.UB,[fixed_vars[int(i)] for i in indices],rounded.tolist())
fixed.solveLP()
assert fixed.status==cp.COPT.OPTIMAL,('Rounded design LP',fixed.status)
values = np.asarray(fixed.getValues())
np.savez_compressed(out / 'rounded_lp_values.npz',values=values)
status = {'objective':fixed.ObjVal*1e6,'lower_bound':bound,'gap':(fixed.ObjVal*1e6-bound)/(fixed.ObjVal*1e6),'binary_rounding_threshold':threshold,'seconds':fixed.getAttr('SolvingTime')}
(out / 'rounded_lp_status.json').write_text(json.dumps(status,indent=2))
print('ROUNDED_LP_FINISHED',json.dumps(status),flush=True)
del fixed_vars,fixed
del model
del environment
