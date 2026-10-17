import json
import time
from pathlib import Path

import highspy
import numpy as np
from scipy import sparse

base = Path(__file__).resolve().parent
out = base / 'decomposed_runs/GTL-GH/baseline'
data = np.load(out / 'master_data.npz')
matrix = sparse.load_npz(out / 'master_matrix.npz').tocsc()
model = highspy.HighsLp()
model.num_col_,model.num_row_ = matrix.shape[1],matrix.shape[0]
model.col_cost_,model.col_lower_,model.col_upper_ = data['c'],data['lb'],data['ub']
model.row_lower_,model.row_upper_ = data['lhs'],data['rhs']
model.integrality_ = [highspy.HighsVarType.kInteger if kind!='C' else highspy.HighsVarType.kContinuous for kind in data['vtype']]
model.a_matrix_.format_ = highspy.MatrixFormat.kColwise
model.a_matrix_.start_,model.a_matrix_.index_,model.a_matrix_.value_ = matrix.indptr,matrix.indices,matrix.data
solver = highspy.Highs()
for name,value in {'threads':8,'time_limit':1800.0,'mip_rel_gap':0.005,'mip_lp_solver':'ipm','mip_ipm_solver':'ipx','small_matrix_value':1e-12,'mip_feasibility_tolerance':1e-7,'log_file':str(out / 'highs_projection.log')}.items():
    assert solver.setOptionValue(name,value)==highspy.HighsStatus.kOk,(name,value)
assert solver.passModel(model)==highspy.HighsStatus.kOk
initial = highspy.HighsSolution()
initial.col_value = np.load(out / 'rounded_t003_lp_values.npz')['values']
initial.value_valid = True
assert solver.setSolution(initial)==highspy.HighsStatus.kOk
started = time.time()
status = solver.run()
assert status!=highspy.HighsStatus.kError,status
solution,info = solver.getSolution(),solver.getInfo()
assert solution.value_valid
values = np.asarray(solution.col_value)
activity = matrix@values
row_error = float(np.maximum(np.maximum(data['lhs']-activity,activity-data['rhs']),0).max())
bound_error = float(np.maximum(np.maximum(data['lb']-values,values-data['ub']),0).max())
integer_error = float(np.abs(values[data['vtype']!='C']-np.rint(values[data['vtype']!='C'])).max())
assert row_error<=1e-3 and bound_error<=1e-5 and integer_error<=1e-6,(row_error,bound_error,integer_error)
root = json.loads((out / 'root_lp_status.json').read_text())
objective = float(data['c']@values)*1e6
lower = max(info.mip_dual_bound*1e6,root['objective'])
report = {'status':solver.modelStatusToString(solver.getModelStatus()),'solver':'HiGHS','version':solver.version(),'objective':objective,'lower_bound':lower,'gap':max(0,(objective-lower)/abs(objective)),'seconds':time.time()-started,'max_constraint_residual':row_error,'max_bound_residual':bound_error,'max_integer_violation':integer_error}
np.savez_compressed(out / 'mip_highs_values.npz',values=values)
(out / 'mip_highs_status.json').write_text(json.dumps(report,indent=2))
print('HIGHS_PROJECTED_COMPLETE',json.dumps(report),flush=True)
