import hashlib
import json
import sys
import time
from pathlib import Path

import coptpy as cp
import numpy as np
import pandas as pd

base = Path(__file__).resolve().parent
scenario,label,iteration = sys.argv[1:4]
out = base / 'decomposed_runs' / scenario / label
environment = cp.Envr()
model = environment.createModel('complete_route_dispatch')
source_model = base / 'runs' / scenario / label / 'model.mps.gz'
model.read(str(source_model))
variables,rows = model.getVars(),model.getConstrs()
names = [v.getName() for v in variables]
if iteration.startswith('closure'):
    threshold = float(iteration.removeprefix('closure'))
    proposal = np.load(out / 'values.npz')['values'].copy()
    meta = json.loads((out / 'certificate.json').read_text())
    dispatch = pd.read_csv(base / 'verified_runs' / scenario / label / 'saf_production.csv')
    totals = dispatch.groupby(['location','technology']).value.sum()
    closed = [(location,technology) for (location,technology),amount in totals.items() if amount<threshold]
    closed_facilities = {f'facility_{location}_{technology}'.replace(' ','_') for location,technology in closed}
    closed_set = set(closed)
    closed_locations = {location for location in totals.index.get_level_values(0).unique() if all((location,technology) in closed_set for technology in totals.loc[location].index)}
    suffixes = tuple(('_'+location+'_week').replace(' ','_') for location in closed_locations)
    for i,name in enumerate(names):
        if name in closed_facilities or (name.startswith('h2_pipeline_transport_') and name.endswith(suffixes)):
            proposal[i] = 0
    print('CLOSURE_DESIGN',len(closed),threshold,flush=True)
elif iteration.startswith('rounded') or iteration.startswith('mip'):
    retained = np.asarray([not name.startswith('corrected_h2_flow_') for name in names])
    proposal = np.zeros(len(names))
    prefix = iteration+'_lp' if iteration.startswith('rounded') else iteration
    proposal[retained] = np.load(out / f'{prefix}_values.npz')['values'][:int(retained.sum())]
    meta = json.loads((out / f'{prefix}_status.json').read_text())
    meta.update(column_name_sha256=hashlib.sha256('\n'.join(names).encode()).hexdigest(),source_sha256=hashlib.sha256(source_model.read_bytes()).hexdigest())
else:
    proposal = np.load(out / f'candidate_{iteration}.npz')['values']
    meta = json.loads((out / f'candidate_{iteration}.json').read_text())
assert hashlib.sha256('\n'.join(names).encode()).hexdigest()==meta['column_name_sha256']
original_lower = np.asarray(model.getInfo(cp.COPT.Info.LB,variables))
original_upper = np.asarray(model.getInfo(cp.COPT.Info.UB,variables))
fixed = [i for i,v in enumerate(variables) if v.getType()!=cp.COPT.CONTINUOUS or names[i].startswith('h2_pipeline_transport_')]
model.setInfo(cp.COPT.Info.LB,[variables[i] for i in fixed],proposal[fixed].tolist())
model.setInfo(cp.COPT.Info.UB,[variables[i] for i in fixed],proposal[fixed].tolist())
model.setObjective(model.getObjective()*1e-6)
for name,value in {'LpMethod':2,'Crossover':1,'Threads':8,'TimeLimit':1200,'FeasTol':1e-7,'DualTol':1e-7}.items():
    model.setParam(name,value)
model.setLogFile(str(out / f'repair_{iteration}.log'))
model.solveLP()
status = {'status':model.status,'has_solution':bool(model.getAttr('HasSol')),'source_iteration':iteration,'seconds':model.getAttr('SolvingTime')}
(out / f'repair_status_{iteration}.json').write_text(json.dumps(status,indent=2))
assert model.getAttr('HasSol'),status
values = np.asarray(model.getValues())
activity = model.getA()@values
lhs = np.asarray(model.getInfo(cp.COPT.Info.LB,rows))
rhs = np.asarray(model.getInfo(cp.COPT.Info.UB,rows))
status.update(objective=model.ObjVal*1e6,lower_bound=meta['lower_bound'],max_constraint_residual=float(np.maximum(np.maximum(lhs-activity,activity-rhs),0).max()),max_bound_residual=float(np.maximum(np.maximum(original_lower-values,values-original_upper),0).max()),max_integer_violation=float(max(abs(values[i]-round(values[i])) for i,v in enumerate(variables) if v.getType()!=cp.COPT.CONTINUOUS)))
status['gap'] = max(0,(status['objective']-status['lower_bound'])/status['objective'])
status['physically_feasible_algebraically'] = status['max_constraint_residual']<=1e-3 and status['max_bound_residual']<=1e-5 and status['max_integer_violation']<=1e-6
status.update(source_sha256=meta['source_sha256'],column_name_sha256=meta['column_name_sha256'],method='Feasible full-model dispatch with fixed candidate binaries and weekly routes; global lower bound from routing projection')
for key in ['bound_source','global_bound_method']:
    if key in meta:
        status[key] = meta[key]
np.savez_compressed(out / f'repaired_values_{iteration}.npz',values=values)
(out / f'repair_status_{iteration}.json').write_text(json.dumps(status,indent=2))
print('REPAIR_COMPLETE',json.dumps(status),flush=True)
del variables,rows,model
del environment
