import argparse
import hashlib
import json
import time
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from pathlib import Path

import coptpy as cp
import numpy as np
from scipy import sparse


WORKER = {}


def initialize_worker(runtime, scenario, parameters):
    out = Path(runtime) / 'decomposed_runs' / scenario / 'baseline'
    data = dict(np.load(out / 'master_data.npz'))
    matrix = sparse.load_npz(out / 'master_matrix.npz')
    diagnostic = json.loads((out / 'binary_design_diagnostics.json').read_text())
    saf = [record['column'] for record in diagnostic if record['name'].startswith('facility_')]
    column_factor = np.where(data['vtype'] == cp.COPT.CONTINUOUS, parameters['continuous_unit'], 1.)
    row_factor = np.where(np.asarray(abs(matrix[:, data['vtype'] == cp.COPT.CONTINUOUS]).sum(axis=1)).ravel() > 0,
                          parameters['continuous_unit'], 1.)
    transformed = (sparse.diags(1 / row_factor) @ matrix @ sparse.diags(column_factor)).tocsc()
    WORKER.update(out=out, data=data, matrix=matrix, saf=saf, parameters=parameters,
                  column_factor=column_factor, row_factor=row_factor, transformed=transformed,
                  environment=cp.Envr())


def solve_leaf(node):
    out, data, matrix, saf = [WORKER[key] for key in ['out', 'data', 'matrix', 'saf']]
    parameters, column_factor, row_factor = [WORKER[key] for key in ['parameters', 'column_factor', 'row_factor']]
    proof = out / 'partition_bound'
    lower, upper = data['lb'].copy(), data['ub'].copy()
    domain = node['domain']
    outside = sorted(set(saf) - set(domain))
    if outside:
        lower[outside] = upper[outside] = 0
    for column, value in node['fixed'].items():
        lower[int(column)] = upper[int(column)] = value
    extra = sparse.coo_matrix((np.ones(len(domain)), (np.zeros(len(domain), dtype=int), domain)), shape=(1, matrix.shape[1])).tocsc()
    transformed = sparse.vstack([WORKER['transformed'], extra], format='csc')
    scaled_lhs = np.r_[np.where(data['lhs'] > -1e29, data['lhs'] / row_factor, -cp.COPT.INFINITY), node['count_lower']]
    scaled_rhs = np.r_[np.where(data['rhs'] < 1e29, data['rhs'] / row_factor, cp.COPT.INFINITY), node['count_upper']]
    model = WORKER['environment'].createModel('count_partition_' + str(node['id']))
    model.loadMatrix(data['c'] * column_factor, transformed, scaled_lhs, scaled_rhs,
                     np.where(lower > -1e29, lower / column_factor, -cp.COPT.INFINITY),
                     np.where(upper < 1e29, upper / column_factor, cp.COPT.INFINITY))
    for name, value in {'LpMethod': parameters['lp_method'], 'Crossover': parameters['crossover'],
                        'Threads': parameters['threads'], 'TimeLimit': 180 if parameters['crossover'] else 60,
                        'FeasTol': 1e-8, 'DualTol': 1e-8}.items():
        model.setParam(name, value)
    if parameters['lp_method'] == 4:
        model.setParam('ConcurrentLpMode', 0)
    model.setLogFile(str(proof / ('leaf_' + str(node['id']) + '.log')))
    started = time.time()
    model.solveLP()
    node.update(solver_status=model.status, seconds=time.time() - started,
                continuous_column_unit=parameters['continuous_unit'], physical_row_unit=parameters['continuous_unit'],
                numerical_transformation='x=D*z, A_new=R^-1*A*D, c_new=c*D; integer columns and pure integer rows unchanged')
    children = []
    if model.status == cp.COPT.INFEASIBLE:
        node.update(state='proved_infeasible', lower_bound_cny=1e100)
    elif model.status == cp.COPT.OPTIMAL:
        values = np.asarray(model.getValues()) * column_factor
        activity = matrix @ values
        count = values[domain].sum()
        residual = max(float(np.maximum(np.maximum(data['lhs'] - activity, activity - data['rhs']), 0).max()),
                       float(max(node['count_lower'] - count, count - node['count_upper'], 0)))
        bound_residual = float(np.maximum(np.maximum(lower - values, values - upper), 0).max())
        solver_bound = float(model.getAttr('ObjBound') * 1e6)
        assert np.isfinite(solver_bound) and solver_bound < 1e29
        assert solver_bound <= model.ObjVal * 1e6 + 1e4
        node.update(state='optimal_lp', lower_bound_cny=max(node['lower_bound_cny'], solver_bound),
                    solver_bound_attribute='ObjBound', solver_bound_cny=solver_bound,
                    solver_primal_objective_cny=float(model.ObjVal * 1e6),
                    max_constraint_residual=residual, max_bound_residual=bound_residual)
        np.savez_compressed(proof / ('leaf_' + str(node['id']) + '_values.npz'), values=values)
        integers = np.flatnonzero(data['vtype'] != cp.COPT.CONTINUOUS)
        if node['lower_bound_cny'] >= parameters['cutoff']:
            node['state'] = 'certified_lower_bound'
        elif np.max(np.abs(values[integers] - np.rint(values[integers]))) <= 1e-6:
            node['state'] = 'integer_master_optimal'
        else:
            fixed_ones = {int(column) for column, value in node['fixed'].items() if value == 1 and int(column) in saf}
            free_domain = sorted(set(domain) - {int(column) for column in node['fixed']})
            remaining_count = node['count_lower'] - len(fixed_ones)
            if node['count_lower'] == node['count_upper'] and remaining_count == 1 and len(free_domain) > 1:
                # 剩余一处地点的整数选择由两个互斥完整子集覆盖。
                left, right, weights = [], [], [0., 0.]
                for column in sorted(free_domain, key=lambda column: values[column], reverse=True):
                    index = 0 if weights[0] <= weights[1] else 1
                    (left if index == 0 else right).append(column)
                    weights[index] += max(values[column], 1e-15)
                assert left and right and not set(left) & set(right) and set(left + right) == set(free_domain)
                children = [dict(domain=sorted(fixed_ones | set(part)), fixed=dict(node['fixed'])) for part in [left, right]]
                node['branch_rule'] = dict(kind='remaining_single_site_domain', fixed_ones=sorted(fixed_ones),
                                           free_domain=free_domain, allowed_subsets=[left, right])
            else:
                fraction = np.abs(values[integers] - np.rint(values[integers]))
                column = int(integers[np.argmax(fraction)])
                assert fraction.max() > 1e-6
                children = [dict(domain=list(domain), fixed={**node['fixed'], str(column): value}) for value in [0, 1]]
                node['branch_rule'] = dict(binary_column=column, allowed_values=[0, 1])
            node['state'] = 'exhaustively_partitioned'
    else:
        node.update(state='solver_stopped_with_parent_bound', reported_bound_cny=float(model.getAttr('ObjBound') * 1e6))
    del model
    return node, children


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('runtime')
    parser.add_argument('scenario')
    parser.add_argument('--candidate', default='mip_greedy_1_1')
    parser.add_argument('--maximum-nodes', type=int, default=200)
    parser.add_argument('--target-gap', type=float, default=.0099)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--crossover', type=int, choices=[-1, 0, 1], default=1)
    parser.add_argument('--threads', type=int, default=4)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--lp-method', type=int, choices=[1, 2, 4], default=2)
    parser.add_argument('--continuous-unit', type=float, default=1000.)
    args = parser.parse_args()
    assert 1 <= args.workers <= 4 and args.workers * args.threads <= 16
    out = Path(args.runtime) / 'decomposed_runs' / args.scenario / 'baseline'
    proof = out / 'partition_bound'
    proof.mkdir(exist_ok=True)
    data = np.load(out / 'master_data.npz')
    diagnostics = json.loads((out / 'binary_design_diagnostics.json').read_text())
    saf = [record['column'] for record in diagnostics if record['name'].startswith('facility_')]
    assert len(saf) > 5 and all(data['vtype'][column] != cp.COPT.CONTINUOUS for column in saf)
    constant_check = json.loads((out / 'objective_constant_check.json').read_text())
    assert constant_check['retained_coefficient_check'] and constant_check['omitted_flow_zero_objective_check']
    assert constant_check['objective_constant_cny'] == 0
    root = json.loads((out / 'root_lp_status.json').read_text())
    assert root['status'] == cp.COPT.OPTIMAL and root['has_solution']
    candidate = json.loads((out / (args.candidate + '_status.json')).read_text())
    cutoff = candidate['objective'] * (1 - args.target_gap)
    fingerprint = {name: hashlib.sha256((out / name).read_bytes()).hexdigest()
                   for name in ['master_data.npz', 'master_matrix.npz', 'root_lp_status.json',
                                'binary_design_diagnostics.json', 'objective_constant_check.json']}
    nodes = [dict(id=i, parent=None, count_lower=i, count_upper=i, domain=saf, fixed={},
                  lower_bound_cny=root['objective'], state='unexplored') for i in range(5)]
    nodes.append(dict(id=5, parent=None, count_lower=5, count_upper=len(saf), domain=saf,
                      fixed={}, lower_bound_cny=root['objective'], state='unexplored'))
    if args.resume:
        previous = json.loads((proof / 'proof.json').read_text())
        assert previous['source_sha256'] == fingerprint
        assert candidate['objective'] <= previous['candidate_objective_cny'] + 1
        nodes = previous['nodes']
        for node in nodes:
            if node.get('solver_status') not in (None, cp.COPT.OPTIMAL, cp.COPT.INFEASIBLE):
                node['state'] = 'unexplored'
                parent = nodes[node['parent']] if node['parent'] is not None else None
                node['lower_bound_cny'] = parent['lower_bound_cny'] if parent else root['objective']
                for key in ['solver_bound_attribute', 'solver_bound_cny', 'solver_primal_objective_cny', 'solver_status']:
                    node.pop(key, None)

    def save():
        leaves = [node for node in nodes if 'children' not in node]
        bound = min(node['lower_bound_cny'] for node in leaves)
        report = dict(scenario=args.scenario, source_sha256=fingerprint, original_objective=constant_check,
                      candidate=args.candidate, candidate_objective_cny=candidate['objective'], target_lower_bound_cny=cutoff,
                      global_lower_bound_cny=bound, bound_source='Minimum of all exhaustive integer-design leaf LP lower bounds',
                      certified_gap_for_candidate=max(0, (candidate['objective'] - bound) / candidate['objective']),
                      partition_covers_all_integer_designs=True,
                      initial_partition='SAF build count equals 0,1,2,3,4 or is at least 5',
                      saf_build_columns=saf, all_leaf_ids=[node['id'] for node in leaves], nodes=nodes,
                      parallel_workers=args.workers, threads_per_worker=args.threads,
                      single_proof_controller=True)
        temporary = proof / 'proof.pending.json'
        temporary.write_text(json.dumps(report, indent=2), encoding='utf-8')
        temporary.replace(proof / 'proof.json')
        return report

    parameters = dict(crossover=args.crossover, threads=args.threads, lp_method=args.lp_method,
                      continuous_unit=args.continuous_unit, cutoff=cutoff)
    submitted, active = 0, {}
    with ProcessPoolExecutor(max_workers=args.workers, initializer=initialize_worker,
                             initargs=(args.runtime, args.scenario, parameters)) as executor:
        while True:
            report = save()
            if report['global_lower_bound_cny'] < cutoff and submitted < args.maximum_nodes:
                available = sorted([node for node in nodes if node['state'] == 'unexplored' and node['id'] not in active.values()],
                                   key=lambda item: item['lower_bound_cny'])
                for node in available[:min(args.workers - len(active), args.maximum_nodes - submitted)]:
                    future = executor.submit(solve_leaf, dict(node))
                    active[future] = node['id']
                    submitted += 1
            if not active:
                break
            completed, _ = wait(active, return_when=FIRST_COMPLETED)
            for future in completed:
                identity = active.pop(future)
                node, children = future.result()
                assert node['id'] == identity and 'children' not in nodes[identity]
                nodes[identity] = node
                if children:
                    node['children'] = []
                    for child in children:
                        child.update(id=len(nodes), parent=identity, count_lower=node['count_lower'], count_upper=node['count_upper'],
                                     lower_bound_cny=node['lower_bound_cny'], state='unexplored')
                        node['children'].append(child['id'])
                        nodes.append(child)
                print('REAL_PARTITION_LEAF', json.dumps(node), flush=True)
                save()
    report = save()
    assert fingerprint == {name: hashlib.sha256((out / name).read_bytes()).hexdigest() for name in fingerprint}
    print('REAL_PARTITION_FINISHED', report['global_lower_bound_cny'], report['certified_gap_for_candidate'], flush=True)


if __name__ == '__main__':
    main()
