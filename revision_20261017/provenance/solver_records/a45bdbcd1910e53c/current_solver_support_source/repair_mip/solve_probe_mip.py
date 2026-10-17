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
    parser.add_argument('--prefix', default='mip_no_root_cuts')
    parser.add_argument('--seconds', type=int, default=900)
    parser.add_argument('--threads', type=int, default=2)
    parser.add_argument('--no-strong-branching', action='store_true')
    parser.add_argument('--continuous-unit', type=float, default=1.)
    args = parser.parse_args()
    assert args.prefix.startswith('mip')
    out = Path(args.runtime) / 'decomposed_runs' / args.scenario / 'baseline'
    data = np.load(out / 'master_data.npz')
    matrix = sparse.load_npz(out / 'master_matrix.npz')
    root = json.loads((out / 'root_lp_status.json').read_text())
    names = ['rounded_lp_values.npz'] + [p.name for p in out.glob('mip*_values.npz')]
    candidates = []
    for name in names:
        values = np.load(out / name)['values']
        assert len(values) == len(data['c']), name
        activity = matrix @ values
        error = np.maximum(np.maximum(data['lhs'] - activity, activity - data['rhs']), 0).max()
        integrality = np.abs(values[data['vtype'] != cp.COPT.CONTINUOUS] - np.rint(values[data['vtype'] != cp.COPT.CONTINUOUS])).max()
        assert error <= 1e-3 and integrality <= 1e-6, (name, error, integrality)
        candidates.append((float(data['c'] @ values), name, values))
    cost, seed_name, seed = min(candidates, key=lambda item: item[0])
    fingerprint = {name: hashlib.sha256((out / name).read_bytes()).hexdigest()
                   for name in ['master_data.npz', 'master_matrix.npz', 'root_lp_status.json']}
    environment = cp.Envr()
    model = environment.createModel(args.prefix)
    column_factor = np.where(data['vtype'] == cp.COPT.CONTINUOUS, args.continuous_unit, 1.)
    row_factor = np.where(np.asarray(abs(matrix[:, data['vtype'] == cp.COPT.CONTINUOUS]).sum(axis=1)).ravel() > 0, args.continuous_unit, 1.)
    transformed = sparse.diags(1 / row_factor) @ matrix @ sparse.diags(column_factor)
    lhs = np.where(data['lhs'] > -1e29, data['lhs'] / row_factor, -cp.COPT.INFINITY)
    rhs = np.where(data['rhs'] < 1e29, data['rhs'] / row_factor, cp.COPT.INFINITY)
    lower = np.where(data['lb'] > -1e29, data['lb'] / column_factor, -cp.COPT.INFINITY)
    upper = np.where(data['ub'] < 1e29, data['ub'] / column_factor, cp.COPT.INFINITY)
    model.loadMatrix(data['c'] * column_factor, transformed.tocsc(), lhs, rhs, lower, upper, data['vtype'].tolist())
    variables = model.getVars()
    model.setMipStart(variables, (seed / column_factor).tolist())
    model.loadMipStart()
    for name, value in {'LpMethod': 2, 'Crossover': 1, 'Threads': args.threads, 'TimeLimit': args.seconds,
                        'RelGap': .0095, 'FeasTol': 1e-7, 'IntTol': 1e-7,
                        'RootCutRounds': 0, 'PreRootHeurLevel': 0, 'HeurLevel': 1}.items():
        model.setParam(name, value)
    if args.no_strong_branching:
        for name, value in {'StrongBranching': 0, 'HeurLevel': 0, 'RootCutLevel': 0,
                            'TreeCutLevel': 0, 'NodeCutRounds': 0}.items():
            model.setParam(name, value)
    model.setLogFile(str(out / (args.prefix + '_design.log')))
    print('TRUE_MIP_WARM_START', seed_name, cost * 1e6, flush=True)
    started = time.time()
    model.solve()
    status = dict(status=model.status, has_solution=bool(model.getAttr('HasSol')),
                  seed_name=seed_name, seconds=time.time() - started, source_sha256=fingerprint)
    if status['has_solution']:
        values = np.asarray(model.getValues()) * column_factor
        activity = matrix @ values
        integers = data['vtype'] != cp.COPT.CONTINUOUS
        status.update(max_constraint_residual=float(np.maximum(np.maximum(data['lhs'] - activity, activity - data['rhs']), 0).max()),
                      max_bound_residual=float(np.maximum(np.maximum(data['lb'] - values, values - data['ub']), 0).max()),
                      max_integer_violation=float(np.abs(values[integers] - np.rint(values[integers])).max()))
        assert status['max_constraint_residual'] <= 1e-3 and status['max_bound_residual'] <= 1e-5 and status['max_integer_violation'] <= 1e-6, status
        objective = float(model.ObjVal * 1e6)
        lower_bound = max(float(model.getAttr('ObjBound') * 1e6), root['objective'])
        status.update(objective=objective, lower_bound=lower_bound,
                      gap=max(0, (objective - lower_bound) / objective),
                      bound_source=args.prefix + '_design.log',
                      global_bound_method='Valid integer master lower bound for an outer projection of the original full model')
        np.savez_compressed(out / (args.prefix + '_values.npz'), values=values)
    (out / (args.prefix + '_status.json')).write_text(json.dumps(status, indent=2), encoding='utf-8')
    print('TRUE_MIP_COMPLETE', json.dumps(status), flush=True)
    assert fingerprint == {name: hashlib.sha256((out / name).read_bytes()).hexdigest() for name in fingerprint}


if __name__ == '__main__':
    main()
