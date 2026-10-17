import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy import sparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('runtime')
    parser.add_argument('scenario')
    parser.add_argument('--adopt', action='store_true')
    parser.add_argument('--candidate')
    args = parser.parse_args()
    out = Path(args.runtime) / 'decomposed_runs' / args.scenario / 'baseline'
    folder = out / 'partition_bound'
    proof = json.loads((folder / 'proof.json').read_text())
    data = np.load(out / 'master_data.npz')
    matrix = sparse.load_npz(out / 'master_matrix.npz')
    for name, expected in proof['source_sha256'].items():
        assert hashlib.sha256((out / name).read_bytes()).hexdigest() == expected, name
    source = Path(args.runtime) / 'runs' / args.scenario / 'baseline' / 'model.mps.gz'
    assert hashlib.sha256(source.read_bytes()).hexdigest() == proof['original_objective']['source_model_sha256']
    assert proof['original_objective']['objective_constant_cny'] == 0
    nodes = {node['id']: node for node in proof['nodes']}
    assert len(nodes) == len(proof['nodes'])
    saf = set(proof['saf_build_columns'])
    roots = [node for node in nodes.values() if node['parent'] is None]
    assert sorted((node['count_lower'], node['count_upper']) for node in roots) == [(0, 0), (1, 1), (2, 2), (3, 3), (4, 4), (5, len(saf))]
    assert all(set(node['domain']) == saf and not node['fixed'] for node in roots)
    verified_nodes = []
    root_bound = json.loads((out / 'root_lp_status.json').read_text())['objective']
    for node in nodes.values():
        if node['parent'] is not None:
            parent = nodes[node['parent']]
            assert node['id'] in parent['children']
            assert node['lower_bound_cny'] + 1e-3 >= parent['lower_bound_cny']
            assert (node['count_lower'], node['count_upper']) == (parent['count_lower'], parent['count_upper'])
        else:
            assert node['lower_bound_cny'] + 1e-3 >= root_bound
        if 'children' in node:
            children = [nodes[index] for index in node['children']]
            assert len(children) == 2 and all(child['parent'] == node['id'] for child in children)
            if isinstance(node['branch_rule'], str):
                a, b = (set(child['domain']) for child in children)
                assert node['count_lower'] == node['count_upper'] == 1
                assert not (a & b) and a | b == set(node['domain'])
                assert all(child['fixed'] == node['fixed'] for child in children)
            elif node['branch_rule'].get('kind') == 'remaining_single_site_domain':
                rule = node['branch_rule']
                fixed_ones = {int(column) for column, value in node['fixed'].items() if value == 1 and int(column) in saf}
                free_domain = set(node['domain']) - {int(column) for column in node['fixed']}
                assert set(rule['fixed_ones']) == fixed_ones and set(rule['free_domain']) == free_domain
                assert node['count_lower'] == node['count_upper'] == len(fixed_ones) + 1
                a, b = [set(part) for part in rule['allowed_subsets']]
                assert a and b and not a & b and a | b == free_domain
                assert all(child['fixed'] == node['fixed'] for child in children)
                assert [set(child['domain']) for child in children] == [fixed_ones | a, fixed_ones | b]
            else:
                column = str(node['branch_rule']['binary_column'])
                assert node['branch_rule']['allowed_values'] == [0, 1]
                assert column not in node['fixed']
                assert {child['fixed'][column] for child in children} == {0, 1}
                for child in children:
                    assert set(child['domain']) == set(node['domain'])
                    assert {key: value for key, value in child['fixed'].items() if key != column} == node['fixed']
        if node.get('solver_status') == 1:
            values = np.load(folder / ('leaf_' + str(node['id']) + '_values.npz'))['values']
            lower, upper = data['lb'].copy(), data['ub'].copy()
            outside = sorted(saf - set(node['domain']))
            lower[outside] = upper[outside] = 0
            for column, value in node['fixed'].items():
                lower[int(column)] = upper[int(column)] = value
            activity = matrix @ values
            residual = float(np.maximum(np.maximum(data['lhs'] - activity, activity - data['rhs']), 0).max())
            bound_residual = float(np.maximum(np.maximum(lower - values, values - upper), 0).max())
            count = float(values[list(node['domain'])].sum())
            objective = float(data['c'] @ values * 1e6)
            assert residual <= 1e-3 and bound_residual <= 1e-5, (node['id'], residual, bound_residual)
            assert node['count_lower'] - 1e-6 <= count <= node['count_upper'] + 1e-6, (node['id'], count)
            inherited = nodes[node['parent']]['lower_bound_cny'] if node['parent'] is not None else root_bound
            if node.get('solver_bound_attribute') == 'ObjBound':
                assert abs(objective - node['solver_primal_objective_cny']) <= 1
                assert node['solver_bound_cny'] <= objective + 1e4
                assert max(node['solver_bound_cny'], inherited) == node['lower_bound_cny']
            else:
                assert residual <= 1e-3 and bound_residual <= 1e-5
                assert node['count_lower'] - 1e-6 <= count <= node['count_upper'] + 1e-6
                assert abs(max(objective, inherited) - node['lower_bound_cny']) <= 1, (node['id'], objective, node['lower_bound_cny'])
            log = (folder / ('leaf_' + str(node['id']) + '.log')).read_text()
            assert 'Status: Optimal' in log, node['id']
            verified_nodes.append(dict(id=node['id'], objective_cny=objective,
                                       constraint_residual=residual, bound_residual=bound_residual,
                                       solver_optimality_record=True))
        elif node.get('solver_status') == 2:
            log = (folder / ('leaf_' + str(node['id']) + '.log')).read_text()
            assert 'Infeasible' in log and node['state'] == 'proved_infeasible'
        else:
            assert node['state'] in ['unexplored', 'time_limit_with_parent_bound', 'solver_stopped_with_parent_bound']
            inherited = nodes[node['parent']]['lower_bound_cny'] if node['parent'] is not None else root_bound
            assert node['lower_bound_cny'] == inherited
    leaves = [node for node in nodes.values() if 'children' not in node]
    assert {node['id'] for node in leaves} == set(proof['all_leaf_ids'])
    lower_bound = min(node['lower_bound_cny'] for node in leaves)
    assert lower_bound == proof['global_lower_bound_cny']
    result = dict(passed=True, full_integer_domain_covered=True, all_leaf_bounds_valid=True,
                  original_objective_constant_cny=0, global_lower_bound_cny=lower_bound,
                  proof_sha256=hashlib.sha256((folder / 'proof.json').read_bytes()).hexdigest(),
                  original_model_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                  leaf_count=len(leaves), node_count=len(nodes), checked_optimal_lp_nodes=verified_nodes)
    (folder / 'validation.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    if args.adopt:
        candidate = args.candidate or proof['candidate']
        values = np.load(out / (candidate + '_values.npz'))['values']
        metadata = json.loads((out / (candidate + '_status.json')).read_text())
        activity = matrix @ values
        assert np.maximum(np.maximum(data['lhs'] - activity, activity - data['rhs']), 0).max() <= 1e-3
        assert np.maximum(np.maximum(data['lb'] - values, values - data['ub']), 0).max() <= 1e-5
        integer = data['vtype'] != 'C'
        assert np.abs(values[integer] - np.rint(values[integer])).max() <= 1e-6
        assert abs(float(data['c'] @ values * 1e6) - metadata['objective']) <= 1
        metadata.update(lower_bound=lower_bound,
                        gap=max(0, (metadata['objective'] - lower_bound) / metadata['objective']),
                        bound_source='partition_bound/proof.json',
                        global_bound_method='Minimum of exhaustive integer-design partition LP bounds; all leaf domains and original objective independently checked')
        assert metadata['gap'] <= .01, metadata['gap']
        np.savez_compressed(out / 'mip_partition_values.npz', values=values)
        (out / 'mip_partition_status.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
        result['adopted_candidate'] = candidate
        result['candidate_gap'] = metadata['gap']
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
