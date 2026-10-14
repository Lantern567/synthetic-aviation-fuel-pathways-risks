import json
import shutil
from pathlib import Path

import pandas as pd

base = Path(__file__).resolve().parent
bounds = pd.read_csv(base / 'resource_upper_bounds.csv')
bounds = bounds[bounds.scenario=='CTL'].to_dict('records')
assert len(bounds)==2 and all(row['fulfillment_upper_bound']<0.9 for row in bounds)
root = json.loads((base / 'decomposed_runs/CTL/baseline/root_lp_status.json').read_text())
assert root['status']==2
proof = {'scenario':'CTL','minimum_production_fraction':0.9,'constraint':'valid_ineq_min_production','bounds':bounds,'projection_lp_status':root,'verified':True,'conclusion':'Original minimum-production model is infeasible for both week sets. Partial-supply diagnostic has a separately identified model scope.'}
(base / 'ctl_infeasibility.json').write_text(json.dumps(proof,indent=2))
diagnostic = base.with_name(base.name+'_ctl_partial')
diagnostic.mkdir(exist_ok=True)
for name in ['project','inputs','routing','input_sha256.json','raw_profile_validation.json']:
    target = diagnostic / name
    if not target.exists():
        target.symlink_to(base / name, target_is_directory=(base / name).is_dir())
for name in ['run_model.py','corrected_model.py','validate_algebra.py','validate_physics.py','projected_pipeline.py','decompose_routes.py','solve_master_lp.py','repair_candidate.py','accept_repaired.py']:
    shutil.copy2(base / name, diagnostic / name)
(diagnostic / 'diagnostic_scope.json').write_text(json.dumps({'allow_ctl_shortage':True,'purpose':'Partial-supply diagnostic following infeasibility of the original 90% minimum-production model','change':'Only valid_ineq_min_production is omitted; all resource, mass, electricity, capacity, route and cost constraints are retained'},indent=2))
print(diagnostic,flush=True)
