import argparse
import json
from pathlib import Path

import numpy as np
from scipy import sparse


parser = argparse.ArgumentParser()
parser.add_argument('runtime')
parser.add_argument('scenario')
args = parser.parse_args()
out = Path(args.runtime) / 'decomposed_runs' / args.scenario / 'baseline'
data = np.load(out / 'master_data.npz')
matrix = sparse.load_npz(out / 'master_matrix.npz')
choices = []
for path in out.glob('mip*_values.npz'):
    if path.stem in ['mip_best_search_values', 'mip_partition_values']:
        continue
    status_path = path.with_name(path.name.replace('_values.npz', '_status.json'))
    if not status_path.exists():
        continue
    values = np.load(path)['values']
    activity = matrix @ values
    row_error = float(np.maximum(np.maximum(data['lhs'] - activity, activity - data['rhs']), 0).max())
    bound_error = float(np.maximum(np.maximum(data['lb'] - values, values - data['ub']), 0).max())
    integer = data['vtype'] != 'C'
    integer_error = float(np.abs(values[integer] - np.rint(values[integer])).max())
    assert row_error <= 1e-3 and bound_error <= 1e-5 and integer_error <= 1e-6, path
    status = json.loads(status_path.read_text())
    objective = float(data['c'] @ values * 1e6)
    assert abs(objective - status['objective']) <= 1, (path, objective, status['objective'])
    choices.append((objective, path, values, status))
assert choices
objective, path, values, metadata = min(choices, key=lambda item: item[0])
metadata['candidate_source'] = path.name
np.savez_compressed(out / 'mip_best_search_values.npz', values=values)
(out / 'mip_best_search_status.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
print('REAL_MINIMUM_VERIFIED_CANDIDATE', path.name, objective, flush=True)
