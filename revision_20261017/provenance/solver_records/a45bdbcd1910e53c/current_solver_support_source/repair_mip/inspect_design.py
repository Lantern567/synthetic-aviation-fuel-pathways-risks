import argparse
import hashlib
import json
from pathlib import Path

import coptpy as cp
import numpy as np


parser = argparse.ArgumentParser()
parser.add_argument('runtime')
parser.add_argument('scenario')
args = parser.parse_args()
runtime = Path(args.runtime)
out = runtime / 'decomposed_runs' / args.scenario / 'baseline'
data = np.load(out / 'master_data.npz')
root = np.load(out / 'root_lp_values.npz')['values']
environment = cp.Envr()
model = environment.createModel('read_original_names')
model.setParam('Logging', 0)
source = runtime / 'runs' / args.scenario / 'baseline' / 'model.mps.gz'
model.read(str(source))
constant = float(model.getObjective().getConstant())
variables = model.getVars()
retained = np.asarray([not v.getName().startswith('corrected_h2_flow_') for v in variables])
costs = np.asarray(model.getInfo(cp.COPT.Info.Obj, variables))
names = [v.getName() for v, keep in zip(variables, retained) if keep]
np.testing.assert_allclose(data['c'][:len(names)] * 1e6, costs[retained], rtol=1e-12, atol=1e-8)
assert np.all(costs[~retained] == 0) and np.all(data['c'][len(names):] == 0)
(out / 'objective_constant_check.json').write_text(json.dumps(dict(
    objective_constant_cny=constant, source_model_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
    retained_coefficient_check=True, omitted_flow_zero_objective_check=True), indent=2), encoding='utf-8')
print('OBJECTIVE_CONSTANT_CNY', constant, flush=True)
assert len(names) <= len(root)
records = [dict(column=int(i), name=names[i], root_value=float(root[i]), lower=float(data['lb'][i]),
                upper=float(data['ub'][i]), cost_cny=float(data['c'][i] * 1e6))
           for i in np.flatnonzero(data['vtype'] != cp.COPT.CONTINUOUS)]
(out / 'binary_design_diagnostics.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
print(json.dumps(records, indent=2), flush=True)
