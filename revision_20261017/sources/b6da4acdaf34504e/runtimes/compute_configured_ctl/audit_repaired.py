import hashlib
import json
import sys
from pathlib import Path

import coptpy as cp
import numpy as np

base = Path(__file__).resolve().parent
scenario,label,iteration = sys.argv[1:4]
out = base / 'decomposed_runs' / scenario / label
status = json.loads((out / f'repair_status_{iteration}.json').read_text())
values = np.load(out / f'repaired_values_{iteration}.npz')['values']
environment = cp.Envr()
model = environment.createModel('full_matrix_audit')
source = base / 'runs' / scenario / label / 'model.mps.gz'
model.read(str(source))
variables,rows = model.getVars(),model.getConstrs()
activity = model.getA()@values
lhs = np.asarray(model.getInfo(cp.COPT.Info.LB,rows))
rhs = np.asarray(model.getInfo(cp.COPT.Info.UB,rows))
lb = np.asarray(model.getInfo(cp.COPT.Info.LB,variables))
ub = np.asarray(model.getInfo(cp.COPT.Info.UB,variables))
names = [v.getName() for v in variables]
objective = float(np.asarray(model.getInfo(cp.COPT.Info.Obj,variables))@values)
root = json.loads((out / 'root_lp_status.json').read_text())
assert root['status']==cp.COPT.OPTIMAL,root
bound = float(root['objective'])
status.update(objective=objective,lower_bound=bound,gap=max(0,(objective-bound)/objective),max_constraint_residual=float(np.maximum(np.maximum(lhs-activity,activity-rhs),0).max()),max_bound_residual=float(np.maximum(np.maximum(lb-values,values-ub),0).max()),max_integer_violation=float(max(abs(values[i]-round(values[i])) for i,v in enumerate(variables) if v.getType()!=cp.COPT.CONTINUOUS)))
status['physically_feasible_algebraically'] = status['max_constraint_residual']<=1e-3 and status['max_bound_residual']<=1e-5 and status['max_integer_violation']<=1e-6
status.update(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),column_name_sha256=hashlib.sha256('\n'.join(names).encode()).hexdigest(),method='Feasible full-model dispatch with fixed candidate binaries and weekly routes; global lower bound from routing projection')
(out / f'repair_status_{iteration}.json').write_text(json.dumps(status,indent=2))
print('REPAIR_AUDITED',json.dumps(status),flush=True)
del variables,rows,model
del environment
