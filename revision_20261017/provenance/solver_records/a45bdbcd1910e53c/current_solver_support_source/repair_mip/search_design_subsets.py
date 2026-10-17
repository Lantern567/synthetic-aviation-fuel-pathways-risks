import argparse
import hashlib
import itertools
import json
import time
from pathlib import Path

import coptpy as cp
import numpy as np
from scipy import sparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('runtime')
    parser.add_argument('scenario')
    parser.add_argument('--seed', default='mip_threshold_0p1')
    args = parser.parse_args()
    out = Path(args.runtime) / 'decomposed_runs' / args.scenario / 'baseline'
    data = np.load(out / 'master_data.npz')
    matrix = sparse.load_npz(out / 'master_matrix.npz')
    diagnostics = json.loads((out / 'binary_design_diagnostics.json').read_text())
    initial = np.load(out / (args.seed + '_values.npz'))['values']
    root = json.loads((out / 'root_lp_status.json').read_text())
    binaries = np.flatnonzero(data['vtype'] != cp.COPT.CONTINUOUS)
    original_selection = np.rint(initial[binaries])
    positions = {int(column): position for position, column in enumerate(binaries)}
    active = [record for record in diagnostics if record['name'].startswith('facility_')
              and initial[record['column']] > .5]
    assert 1 < len(active) <= 6, active
    source_hash = {name: hashlib.sha256((out / name).read_bytes()).hexdigest()
                   for name in ['master_data.npz', 'master_matrix.npz', 'root_lp_status.json']}
    environment = cp.Envr()
    records = []
    best = float(np.dot(data['c'], initial) * 1e6)
    for number in range(1, len(active)):
        for retained in itertools.combinations(range(len(active)), number):
            prefix = 'mip_subset_' + '_'.join(str(value) for value in retained)
            lower, upper = data['lb'].copy(), data['ub'].copy()
            selection = original_selection.copy()
            for index, record in enumerate(active):
                selection[positions[record['column']]] = float(index in retained)
            lower[binaries] = upper[binaries] = selection
            model = environment.createModel(prefix)
            model.loadMatrix(data['c'], matrix, data['lhs'], data['rhs'], lower, upper)
            for name, value in {'LpMethod': 2, 'Crossover': 1, 'Threads': 2, 'TimeLimit': 180,
                                'FeasTol': 1e-7, 'DualTol': 1e-7}.items():
                model.setParam(name, value)
            model.setLogFile(str(out / (prefix + '.log')))
            started = time.time()
            model.solveLP()
            status = dict(status=model.status, has_solution=bool(model.getAttr('HasSol')),
                          selected_facilities=[active[index]['name'] for index in retained],
                          seconds=time.time() - started, bound_source='root_lp_status.json',
                          source_sha256=source_hash)
            if status['has_solution']:
                values = np.asarray(model.getValues())
                activity = matrix @ values
                status.update(max_row_error=float(np.maximum(np.maximum(data['lhs'] - activity, activity - data['rhs']), 0).max()),
                              max_bound_error=float(np.maximum(np.maximum(data['lb'] - values, values - data['ub']), 0).max()),
                              max_integer_error=float(np.abs(values[binaries] - np.rint(values[binaries])).max()))
                assert status['max_row_error'] <= 1e-3 and status['max_bound_error'] <= 1e-5 and status['max_integer_error'] <= 1e-6, status
                objective = float(model.ObjVal * 1e6)
                status.update(objective=objective, lower_bound=root['objective'],
                              gap=max(0, (objective - root['objective']) / objective))
                if objective < best:
                    best = objective
                    np.savez_compressed(out / (prefix + '_values.npz'), values=values)
                    status['saved_candidate'] = True
            (out / (prefix + '_status.json')).write_text(json.dumps(status, indent=2), encoding='utf-8')
            records.append(dict(prefix=prefix, **status))
            (out / 'subset_probe_status.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
            print('ACTUAL_SUBSET_DESIGN', json.dumps(dict(prefix=prefix, **status)), flush=True)
            del model
    assert source_hash == {name: hashlib.sha256((out / name).read_bytes()).hexdigest() for name in source_hash}


if __name__ == '__main__':
    main()
