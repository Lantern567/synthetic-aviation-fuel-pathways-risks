import json
import sys
from pathlib import Path

import coptpy as cp
import numpy as np
from scipy import sparse

base = Path(__file__).resolve().parent
out = base / 'decomposed_runs/GTL-GH/baseline'
decision = int(sys.argv[1])
assert decision in (0,1)
count_branch = sys.argv[2] if len(sys.argv)>2 else None
assert count_branch in (None,'low','high')
suffix = str(decision)+(f'_count_{count_branch}' if count_branch else '')
environment = cp.Envr()
original = environment.createModel('mapping')
original.read(str(base / 'runs/GTL-GH/baseline/model.mps.gz'))
names = [v.getName() for v in original.getVars() if not v.getName().startswith('corrected_h2_flow_')]
branch_name = 'facility_airport_北京_airport_integrated_conversion'
index = names.index(branch_name)
data = np.load(out / 'strengthened3_master_data.npz')
assert data['vtype'][index]==cp.COPT.BINARY and data['lb'][index]==0 and data['ub'][index]==1
lower,upper = data['lb'].copy(),data['ub'].copy()
lower[index] = upper[index] = decision
model = environment.createModel('airport_binary_partition')
model.loadMatrix(data['c'],sparse.load_npz(out / 'strengthened3_master_matrix.npz'),data['lhs'],data['rhs'],lower,upper)
if count_branch:
    assert decision==1
    variables = model.getVars()
    count = cp.quicksum(variables[i] for i,name in enumerate(names) if name.startswith('facility_'))
    model.addConstr(count<=2 if count_branch=='low' else count>=3,name='integer_facility_count_partition')
for name,value in {'LpMethod':2,'Crossover':1,'Threads':8,'TimeLimit':1200,'FeasTol':1e-7,'DualTol':1e-7}.items():
    model.setParam(name,value)
model.setLogFile(str(out / f'branch_airport_{suffix}.log'))
model.solveLP()
assert model.status in (cp.COPT.OPTIMAL,cp.COPT.INFEASIBLE),model.status
report = {'status':model.status,'branch_variable':branch_name,'branch_value':decision,'count_branch':count_branch,'count_partition':'sum synthesis build binaries <= 2 or >= 3' if count_branch else None,'seconds':model.getAttr('SolvingTime'),'lower_bound':model.ObjVal*1e6 if model.status==cp.COPT.OPTIMAL else None,'scope':'LP relaxation of an exhaustive integer partition of the strengthened route projection.'}
(out / f'branch_airport_{suffix}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
if model.status==cp.COPT.OPTIMAL:
    np.savez_compressed(out / f'branch_airport_{suffix}_values.npz',values=np.asarray(model.getValues()))
print('BRANCH_BOUND_COMPLETE',json.dumps(report,ensure_ascii=False),flush=True)
