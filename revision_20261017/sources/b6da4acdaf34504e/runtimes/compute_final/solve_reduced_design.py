import json
import sys
from pathlib import Path

import coptpy as cp
import numpy as np
from scipy import sparse

base = Path(__file__).resolve().parent
out = base / 'decomposed_runs/GTL-GH/baseline'
data = np.load(out / 'strengthened3_master_data.npz')
root = json.loads((out / 'strengthened3_root_status.json').read_text())
selection = sys.argv[1] if len(sys.argv)>1 else 'both'
prefix = 'mip_reduced_'+selection
environment = cp.Envr()
mapping = environment.createModel('names')
mapping.read(str(base / 'runs/GTL-GH/baseline/model.mps.gz'))
names = [v.getName() for v in mapping.getVars() if not v.getName().startswith('corrected_h2_flow_')]
values = np.load(out / 'rounded_t003_lp_values.npz')['values'].copy()
closed = [i for i,name in enumerate(names) if name.startswith('facility_') and name.endswith('_lng_to_hplant_conversion') and values[i]>0.5 and (selection=='both' or selection in name)]
assert closed
values[closed] = 0
print('CLOSED_TECH_MODULES',[names[i] for i in closed],flush=True)
integers = data['vtype']!=cp.COPT.CONTINUOUS
lower,upper = data['lb'].copy(),data['ub'].copy()
lower[integers] = upper[integers] = np.rint(values[integers])
model = environment.createModel('reduced_design')
model.loadMatrix(data['c'],sparse.load_npz(out / 'strengthened3_master_matrix.npz'),data['lhs'],data['rhs'],lower,upper)
for name,value in {'LpMethod':2,'Crossover':1,'Threads':8,'TimeLimit':1200,'FeasTol':1e-7,'DualTol':1e-7}.items():
    model.setParam(name,value)
model.setLogFile(str(out / f'{prefix}.log'))
model.solveLP()
assert model.status==cp.COPT.OPTIMAL,model.status
values = np.asarray(model.getValues())
objective = model.ObjVal*1e6
status = {'objective':objective,'lower_bound':root['objective'],'gap':max(0,(objective-root['objective'])/objective),'seconds':model.getAttr('SolvingTime'),'bound_source':'strengthened3_root_status.json','closed_technology_modules':[names[i] for i in closed]}
np.savez_compressed(out / f'{prefix}_values.npz',values=values)
(out / f'{prefix}_status.json').write_text(json.dumps(status,indent=2))
print('REDUCED_DESIGN_COMPLETE',json.dumps(status),flush=True)
