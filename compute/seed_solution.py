import json
import sys
from pathlib import Path

import coptpy as cp
import numpy as np
import pandas as pd

base = Path(__file__).resolve().parent
scenario = sys.argv[1]
fixed = '--fixed' in sys.argv
out = base / 'solver_probes' / scenario / ('seed_fixed' if fixed else 'seed')
out.mkdir(parents=True,exist_ok=True)
environment = cp.Envr()
model = environment.createModel('feasible_seed')
model.read(str(base / 'runs' / scenario / 'baseline/model.mps.gz'))
original = pd.read_csv(base / 'original_saf_facilities.csv')
selected = set(original.loc[original.scenario==scenario,'location'])
airports = pd.read_csv(base / 'inputs/baseline/airport_input.csv')
selected.update('airport_'+name for name in airports.departure_airport_name.unique())
power = pd.read_csv(base / 'inputs/baseline/renewable_periods.csv').groupby('plant_name').power_output_mw.sum()
selected.update(power.nlargest(4).index)
technology = set(original.loc[original.scenario==scenario,'technology'])
facility_names = {f'facility_{location}_{tech}' for location in selected for tech in technology}
destinations = tuple('_'+location+'_week' for location in selected)
variables = model.getVars()
names = [var.getName() for var in variables]
closed,opened = [],[]
for var,name in zip(variables,names):
    if name.startswith('facility_') and name not in facility_names:
        closed.append(var)
    elif name.startswith('h2_pipeline_transport_') and not name.endswith(destinations):
        closed.append(var)
    elif name.startswith('electrolyzer_facility_'):
        opened.append(var)
    elif fixed and name in facility_names:
        opened.append(var)
model.setInfo(cp.COPT.Info.UB,closed,0)
model.setInfo(cp.COPT.Info.LB,opened,1)
model.setObjective(model.getObjective()*1e-6,cp.COPT.MINIMIZE)
for name,value in {'TimeLimit':1800,'Threads':8,'LpMethod':2,'RelGap':1e-5,'FeasTol':1e-8,'IntTol':1e-8,'Crossover':0}.items():
    model.setParam(name,value)
model.setLogFile(str(out / 'copt.log'))
print('SEED_READY',scenario,sorted(selected),len(closed),len(opened),flush=True)
model.solve()
status = {'scenario':scenario,'status':model.status,'has_solution':bool(model.getAttr('HasSol')),'scope':'Restricted-site feasible starting solution; not a final optimized result'}
(out / 'status.json').write_text(json.dumps(status,indent=2))
assert status['has_solution'],status
values = np.asarray(model.getValues())
production = sum(value for name,value in zip(names,values) if name.startswith('prod_'))
assert production>1,production
np.savez_compressed(out / 'values.npz',values=values)
model.write(str(out / 'solution.sol'))
status.update(production_kg=production,objective_original_scale=model.ObjVal*1e6,gap=model.getAttr('BestGap'))
matrix = model.getA()
constraints = model.getConstrs()
activity = matrix@values
lower = np.asarray(model.getInfo(cp.COPT.Info.LB,constraints))
upper = np.asarray(model.getInfo(cp.COPT.Info.UB,constraints))
violations = np.maximum(np.maximum(lower-activity,activity-upper),0)
status['max_constraint_residual'] = float(violations.max())
status['max_bound_residual'] = float(np.maximum(np.maximum(np.asarray(model.getInfo(cp.COPT.Info.LB,variables))-values,values-np.asarray(model.getInfo(cp.COPT.Info.UB,variables))),0).max())
status['max_integer_violation'] = max(abs(value-round(value)) for var,value in zip(variables,values) if var.getType()!=cp.COPT.CONTINUOUS)
(out / 'status.json').write_text(json.dumps(status,indent=2))
print('SEED_COMPLETE',json.dumps(status),flush=True)
del closed,opened,variables,constraints,var,model
del environment
