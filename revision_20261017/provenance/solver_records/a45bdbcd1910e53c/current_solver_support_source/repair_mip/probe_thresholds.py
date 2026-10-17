import argparse
import hashlib
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
    parser.add_argument('--label', default='baseline')
    parser.add_argument('--thresholds', nargs='+', type=float, default=[.003, .01, .03, .1])
    args = parser.parse_args()
    runtime = Path(args.runtime).resolve()
    out = runtime / 'decomposed_runs' / args.scenario / args.label
    data = np.load(out / 'master_data.npz')
    matrix = sparse.load_npz(out / 'master_matrix.npz')
    root = json.loads((out / 'root_lp_status.json').read_text())
    assert root['status'] == cp.COPT.OPTIMAL and root['has_solution']
    initial = np.load(out / 'root_lp_values.npz')['values']
    assert len(initial) == len(data['c'])
    binaries = data['vtype'] != cp.COPT.CONTINUOUS
    fingerprint = {filename: hashlib.sha256((out / filename).read_bytes()).hexdigest()
                   for filename in ['master_data.npz', 'master_matrix.npz', 'root_lp_status.json', 'root_lp_values.npz']}
    print('ACTUAL_ROOT_BINARY_DISTRIBUTION', json.dumps({
        'count': int(binaries.sum()), 'positive': int((initial[binaries] > 1e-8).sum()),
        'quantiles': np.quantile(initial[binaries], [0, .25, .5, .75, .9, .95, 1]).tolist(),
        'root_objective_cny': root['objective'], 'source_sha256': fingerprint,
    }), flush=True)
    environment = cp.Envr()
    records = []
    for threshold in args.thresholds:
        prefix = 'mip_threshold_' + str(threshold).replace('.', 'p')
        lower, upper = data['lb'].copy(), data['ub'].copy()
        selection = (initial[binaries] > threshold).astype(float)
        lower[binaries] = upper[binaries] = selection
        model = environment.createModel(prefix)
        model.loadMatrix(data['c'], matrix, data['lhs'], data['rhs'], lower, upper)
        for name, value in {'LpMethod': 2, 'Crossover': 1, 'Threads': 2, 'TimeLimit': 180,
                            'FeasTol': 1e-7, 'DualTol': 1e-7}.items():
            model.setParam(name, value)
        model.setLogFile(str(out / (prefix + '.log')))
        started = time.time()
        model.solveLP()
        status = {'threshold': threshold, 'status': model.status, 'has_solution': bool(model.getAttr('HasSol')),
                  'selected_binary_count': int(selection.sum()), 'seconds': time.time() - started,
                  'bound_source': 'root_lp_status.json', 'source_sha256': fingerprint}
        if status['has_solution']:
            values = np.asarray(model.getValues())
            activity = matrix @ values
            status.update(max_row_error=float(np.maximum(np.maximum(data['lhs'] - activity, activity - data['rhs']), 0).max()),
                          max_bound_error=float(np.maximum(np.maximum(data['lb'] - values, values - data['ub']), 0).max()),
                          max_integer_error=float(np.abs(values[binaries] - np.rint(values[binaries])).max()))
            assert status['max_row_error'] <= 1e-3 and status['max_bound_error'] <= 1e-5 and status['max_integer_error'] <= 1e-6, status
            objective = float(model.ObjVal * 1e6)
            status.update(objective=objective, lower_bound=root['objective'], gap=max(0, (objective - root['objective']) / objective))
            np.savez_compressed(out / (prefix + '_values.npz'), values=values)
        (out / (prefix + '_status.json')).write_text(json.dumps(status, indent=2), encoding='utf-8')
        records.append(status)
        (out / 'threshold_probe_status.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
        print('ACTUAL_THRESHOLD_DESIGN', json.dumps(status), flush=True)
        del model
    assert fingerprint == {filename: hashlib.sha256((out / filename).read_bytes()).hexdigest() for filename in fingerprint}


if __name__ == '__main__':
    main()
