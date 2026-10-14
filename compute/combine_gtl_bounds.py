import json
from pathlib import Path

import numpy as np

base = Path(__file__).resolve().parent
out = base / 'decomposed_runs/GTL-GH/baseline'
branches = [json.loads((out / f'branch_airport_{value}.json').read_text()) for value in [0,1]]
assert {row['branch_value'] for row in branches}=={0,1}
assert len({row['branch_variable'] for row in branches})==1
assert all(row['status'] in [1,2] for row in branches)
sources = ['branch_airport_0.json','branch_airport_1.json']
if all((out / f'branch_airport_1_count_{name}.json').exists() for name in ['low','high']):
    children = [json.loads((out / f'branch_airport_1_count_{name}.json').read_text()) for name in ['low','high']]
    assert {child['count_branch'] for child in children}=={'low','high'}
    assert all(child['branch_value']==1 and child['status'] in [1,2] and child['count_partition']=='sum synthesis build binaries <= 2 or >= 3' for child in children)
    branches = [branches[0]]+children
    sources = ['branch_airport_0.json','branch_airport_1_count_low.json','branch_airport_1_count_high.json']
lower = min(row['lower_bound'] for row in branches if row['status']==1)
parent = json.loads((out / 'strengthened3_root_status.json').read_text())
lower = max(lower,parent['objective'])
prior = json.loads((out / 'rounded_t003_lp_status.json').read_text())
prior.update(lower_bound=lower,gap=max(0,(prior['objective']-lower)/prior['objective']),bound_source=sources,global_bound_method='Minimum of all exhaustive integer-partition LP bounds, each using valid routing and electricity projections')
np.savez_compressed(out / 'mip_branch_values.npz',values=np.load(out / 'rounded_t003_lp_values.npz')['values'])
(out / 'mip_branch_status.json').write_text(json.dumps(prior,indent=2))
print('PARTITION_GLOBAL_BOUND',json.dumps(prior),flush=True)
