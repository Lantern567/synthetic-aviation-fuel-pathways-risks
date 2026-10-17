import json
import sys
from pathlib import Path

import coptpy as cp
import numpy as np
from scipy import sparse

base = Path(__file__).resolve().parent
out = base / 'decomposed_runs/GTL-GH/baseline'
data = np.load(out / 'strengthened_master_data.npz')
root = json.loads((out / 'strengthened_root_status.json').read_text())
assert root['status']==cp.COPT.OPTIMAL
values = np.load(out / 'strengthened_root_values.npz')['values']
threshold = float(sys.argv[1])
prefix = 'mip_strong_'+str(threshold).replace('.','p')
integers = data['vtype']!=cp.COPT.CONTINUOUS
print('STRONG_DESIGN',threshold,int((values[integers]>threshold).sum()),flush=True)
lower,upper = data['lb'].copy(),data['ub'].copy()
lower[integers] = upper[integers] = (values[integers]>threshold).astype(float)
environment = cp.Envr()
model = environment.createModel('strengthened_fixed_design')
model.loadMatrix(data['c'],sparse.load_npz(out / 'strengthened_master_matrix.npz'),data['lhs'],data['rhs'],lower,upper)
for name,value in {'LpMethod':2,'Crossover':1,'Threads':8,'TimeLimit':1200,'FeasTol':1e-7,'DualTol':1e-7}.items():
    model.setParam(name,value)
model.setLogFile(str(out / f'{prefix}.log'))
model.solveLP()
assert model.status==cp.COPT.OPTIMAL,model.status
values = np.asarray(model.getValues())
objective = model.ObjVal*1e6
status = {'objective':objective,'lower_bound':root['objective'],'gap':max(0,(objective-root['objective'])/objective),'threshold':threshold,'seconds':model.getAttr('SolvingTime'),'bound_source':'strengthened_root_status.json'}
np.savez_compressed(out / f'{prefix}_values.npz',values=values)
(out / f'{prefix}_status.json').write_text(json.dumps(status,indent=2))
print('STRONG_DESIGN_COMPLETE',json.dumps(status),flush=True)
