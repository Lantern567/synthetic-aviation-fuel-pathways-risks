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
    parser.add_argument('--candidate', default='mip_subset_1_2_3')
    parser.add_argument('--maximum-nodes', type=int, default=40)
    parser.add_argument('--target-gap', type=float, default=.0095)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--crossover', type=int, choices=[-1, 0, 1], default=-1)
    parser.add_argument('--threads', type=int, default=2)
    parser.add_argument('--lp-method', type=int, choices=[1, 2, 4], default=2)
    parser.add_argument('--continuous-unit', type=float, default=1.)
    args = parser.parse_args()
    out = Path(args.runtime) / 'decomposed_runs' / args.scenario / 'baseline'
    proof = out / 'partition_bound'
    proof.mkdir(exist_ok=True)
    data = np.load(out / 'master_data.npz')
    matrix = sparse.load_npz(out / 'master_matrix.npz')
    diagnostic_path = out / 'binary_design_diagnostics.json'
    diagnostics = json.loads(diagnostic_path.read_text())
    saf = [record['column'] for record in diagnostics if record['name'].startswith('facility_')]
    assert len(saf) > 5 and all(data['vtype'][column] != cp.COPT.CONTINUOUS for column in saf)
    constant_check = json.loads((out / 'objective_constant_check.json').read_text())
    constant = constant_check['objective_constant_cny']
    assert constant_check['retained_coefficient_check'] and constant_check['omitted_flow_zero_objective_check']
    root = json.loads((out / 'root_lp_status.json').read_text())
    assert root['status'] == cp.COPT.OPTIMAL and root['has_solution']
    assert constant == 0, 'The frozen projected lower bound omits an original objective constant'
    candidate = json.loads((out / (args.candidate + '_status.json')).read_text())
    cutoff = candidate['objective'] * (1 - args.target_gap)
    fingerprint = {name: hashlib.sha256((out / name).read_bytes()).hexdigest()
                   for name in ['master_data.npz', 'master_matrix.npz', 'root_lp_status.json',
                                'binary_design_diagnostics.json', 'objective_constant_check.json']}
    integers = np.flatnonzero(data['vtype'] != cp.COPT.CONTINUOUS)
    nodes = [dict(id=i, parent=None, count_lower=i, count_upper=i,
                  domain=saf, fixed={}, lower_bound_cny=root['objective'], state='unexplored') for i in range(5)]
    nodes.append(dict(id=5, parent=None, count_lower=5, count_upper=len(saf),
                      domain=saf, fixed={}, lower_bound_cny=root['objective'], state='unexplored'))
    if args.resume:
        previous = json.loads((proof / 'proof.json').read_text())
        assert previous['source_sha256'] == fingerprint
        assert candidate['objective'] <= previous['candidate_objective_cny'] + 1
        nodes = previous['nodes']
        for node in nodes:
            if node.get('solver_status') not in (None, cp.COPT.OPTIMAL, cp.COPT.INFEASIBLE):
                node['state'] = 'unexplored'
                parent = next((entry for entry in nodes if entry['id'] == node['parent']), None)
                node['lower_bound_cny'] = parent['lower_bound_cny'] if parent else root['objective']
                for key in ['solver_bound_attribute', 'solver_bound_cny', 'solver_primal_objective_cny', 'solver_status']:
                    node.pop(key, None)
    environment = cp.Envr()

    def save():
        leaves = [node for node in nodes if 'children' not in node]
        bound = min(node['lower_bound_cny'] for node in leaves)
        report = dict(scenario=args.scenario, source_sha256=fingerprint,
                      original_objective=constant_check, candidate=args.candidate,
                      candidate_objective_cny=candidate['objective'], target_lower_bound_cny=cutoff,
                      global_lower_bound_cny=bound, bound_source='Minimum of all exhaustive integer-design leaf LP lower bounds',
                      certified_gap_for_candidate=max(0, (candidate['objective'] - bound) / candidate['objective']),
                      partition_covers_all_integer_designs=True,
                      initial_partition='SAF build count equals 0,1,2,3,4 or is at least 5',
                      saf_build_columns=saf, all_leaf_ids=[node['id'] for node in leaves], nodes=nodes)
        (proof / 'proof.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        return report

    for iteration in range(args.maximum_nodes):
        report = save()
        if report['global_lower_bound_cny'] >= cutoff:
            print('EXHAUSTIVE_PARTITION_BOUND_CERTIFIED', json.dumps({key: value for key, value in report.items() if key != 'nodes'}), flush=True)
            break
        open_nodes = [node for node in nodes if node['state'] == 'unexplored']
        if not open_nodes:
            break
        node = min(open_nodes, key=lambda item: item['lower_bound_cny'])
        lower, upper = data['lb'].copy(), data['ub'].copy()
        domain = node['domain']
        outside = sorted(set(saf) - set(domain))
        if outside:
            lower[outside] = upper[outside] = 0
        for column, value in node['fixed'].items():
            lower[int(column)] = upper[int(column)] = value
        extra = sparse.coo_matrix((np.ones(len(domain)), (np.zeros(len(domain), dtype=int), domain)), shape=(1, matrix.shape[1])).tocsc()
        augmented = sparse.vstack([matrix, extra], format='csc')
        lhs, rhs = np.r_[data['lhs'], node['count_lower']], np.r_[data['rhs'], node['count_upper']]
        model = environment.createModel('count_partition_' + str(node['id']))
        column_factor = np.where(data['vtype'] == cp.COPT.CONTINUOUS, args.continuous_unit, 1.)
        row_factor = np.where(np.asarray(abs(augmented[:, data['vtype'] == cp.COPT.CONTINUOUS]).sum(axis=1)).ravel() > 0,
                              args.continuous_unit, 1.)
        transformed = sparse.diags(1 / row_factor) @ augmented @ sparse.diags(column_factor)
        scaled_lhs = np.where(lhs > -1e29, lhs / row_factor, -cp.COPT.INFINITY)
        scaled_rhs = np.where(rhs < 1e29, rhs / row_factor, cp.COPT.INFINITY)
        scaled_lower = np.where(lower > -1e29, lower / column_factor, -cp.COPT.INFINITY)
        scaled_upper = np.where(upper < 1e29, upper / column_factor, cp.COPT.INFINITY)
        model.loadMatrix(data['c'] * column_factor, transformed.tocsc(), scaled_lhs, scaled_rhs, scaled_lower, scaled_upper)
        for name, value in {'LpMethod': args.lp_method, 'Crossover': args.crossover, 'Threads': args.threads, 'TimeLimit': 180 if args.crossover else 60,
                            'FeasTol': 1e-8 if args.continuous_unit > 1 else 1e-7, 'DualTol': 1e-8 if args.continuous_unit > 1 else 1e-7}.items():
            model.setParam(name, value)
        if args.lp_method == 4:
            model.setParam('ConcurrentLpMode', 0)
        model.setLogFile(str(proof / ('leaf_' + str(node['id']) + '.log')))
        started = time.time()
        model.solveLP()
        node.update(solver_status=model.status, seconds=time.time() - started,
                    continuous_column_unit=args.continuous_unit, physical_row_unit=args.continuous_unit,
                    numerical_transformation='x=D*z, A_new=R^-1*A*D, c_new=c*D; integer columns and pure integer rows unchanged')
        if model.status == cp.COPT.INFEASIBLE:
            node.update(state='proved_infeasible', lower_bound_cny=1e100)
        elif model.status == cp.COPT.OPTIMAL:
            values = np.asarray(model.getValues()) * column_factor
            activity = augmented @ values
            residual = float(np.maximum(np.maximum(lhs - activity, activity - rhs), 0).max())
            bound_residual = float(np.maximum(np.maximum(lower - values, values - upper), 0).max())
            solver_bound = float(model.getAttr('ObjBound') * 1e6 + constant)
            assert np.isfinite(solver_bound) and solver_bound < 1e29
            assert solver_bound <= model.ObjVal * 1e6 + constant + 1e4
            node.update(state='optimal_lp', lower_bound_cny=max(node['lower_bound_cny'], solver_bound),
                        solver_bound_attribute='ObjBound', solver_bound_cny=solver_bound,
                        solver_primal_objective_cny=float(model.ObjVal * 1e6 + constant),
                        max_constraint_residual=residual, max_bound_residual=bound_residual)
            np.savez_compressed(proof / ('leaf_' + str(node['id']) + '_values.npz'), values=values)
            if node['lower_bound_cny'] >= cutoff:
                node['state'] = 'certified_lower_bound'
            elif np.max(np.abs(values[integers] - np.rint(values[integers]))) <= 1e-6:
                node['state'] = 'integer_master_optimal'
            else:
                fixed_ones = {int(column) for column, value in node['fixed'].items() if value == 1 and int(column) in saf}
                free_domain = sorted(set(domain) - {int(column) for column in node['fixed']})
                remaining_count = node['count_lower'] - len(fixed_ones)
                if node['count_lower'] == node['count_upper'] and remaining_count == 1 and len(free_domain) > 1:
                    # 单厂分支按候选集合二分，全部整数地点选择均被覆盖。
                    left, right = [], []
                    weights = [0., 0.]
                    for column in sorted(free_domain, key=lambda column: values[column], reverse=True):
                        index = 0 if weights[0] <= weights[1] else 1
                        (left if index == 0 else right).append(column)
                        weights[index] += max(values[column], 1e-15)
                    assert left and right and set(left).isdisjoint(right) and set(left + right) == set(free_domain)
                    children = [dict(domain=sorted(fixed_ones | set(part)), fixed=dict(node['fixed'])) for part in [left, right]]
                    node['branch_rule'] = dict(kind='remaining_single_site_domain', fixed_ones=sorted(fixed_ones),
                                               free_domain=free_domain, allowed_subsets=[left, right])
                else:
                    fraction = np.abs(values[integers] - np.rint(values[integers]))
                    column = int(integers[np.argmax(fraction)])
                    assert fraction.max() > 1e-6
                    children = [dict(domain=list(domain), fixed={**node['fixed'], str(column): value}) for value in [0, 1]]
                    node['branch_rule'] = dict(binary_column=column, allowed_values=[0, 1])
                node['children'] = []
                for child in children:
                    child.update(id=len(nodes), parent=node['id'], count_lower=node['count_lower'], count_upper=node['count_upper'],
                                 lower_bound_cny=node['lower_bound_cny'], state='unexplored')
                    node['children'].append(child['id'])
                    nodes.append(child)
                node['state'] = 'exhaustively_partitioned'
        else:
            node.update(state='solver_stopped_with_parent_bound',
                        reported_bound_cny=float(model.getAttr('ObjBound') * 1e6 + constant))
        print('REAL_PARTITION_LEAF', json.dumps(node), flush=True)
        save()
        del model
    report = save()
    assert fingerprint == {name: hashlib.sha256((out / name).read_bytes()).hexdigest() for name in fingerprint}
    print('REAL_PARTITION_FINISHED', report['global_lower_bound_cny'], report['certified_gap_for_candidate'], flush=True)


if __name__ == '__main__':
    main()
