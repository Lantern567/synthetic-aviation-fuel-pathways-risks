import argparse
import hashlib
import json
from pathlib import Path


parser = argparse.ArgumentParser()
parser.add_argument('--proof', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
proof = json.loads(args.proof.read_text(encoding='utf-8'))
nodes = {item['id']: item for item in proof['nodes']}
if len(nodes) != len(proof['nodes']):
    raise ValueError('Duplicate proof node identifier')
saf = set(proof['saf_build_columns'])
roots = [item for item in nodes.values() if item['parent'] is None]
if sorted((item['count_lower'], item['count_upper']) for item in roots) != [(0, 0), (1, 1), (2, 2), (3, 3), (4, 4), (5, len(saf))]:
    raise ValueError('The factory-count roots do not cover all integer possibilities')
seen, special = set(), []


def visit(identifier):
    if identifier in seen:
        raise ValueError('A node is repeated or the proof graph has a cycle')
    seen.add(identifier)
    node = nodes[identifier]
    domain = set(node['domain'])
    fixed = {int(column): value for column, value in node['fixed'].items()}
    ones = {column for column, value in fixed.items() if value == 1 and column in saf}
    if not domain <= saf or not ones <= domain or any(value not in [0, 1] for value in fixed.values()):
        raise ValueError('An integer-domain node has incompatible fixed decisions')
    if 'children' not in node:
        return
    children = [nodes[index] for index in node['children']]
    if len(children) != 2 or any(child['parent'] != identifier for child in children):
        raise ValueError('The proof tree parent/child edges do not match')
    for child in children:
        if (child['count_lower'], child['count_upper']) != (node['count_lower'], node['count_upper']):
            raise ValueError('A child changed its inherited factory-count interval')
    rule = node['branch_rule']
    if isinstance(rule, dict) and rule.get('kind') == 'remaining_single_site_domain':
        free = domain - set(fixed)
        left, right = [set(part) for part in rule['allowed_subsets']]
        if node['count_lower'] != node['count_upper'] or node['count_lower'] != len(ones) + 1:
            raise ValueError('Exactly one remaining factory is required for a site-domain split')
        if set(rule['fixed_ones']) != ones or set(rule['free_domain']) != free or not left or not right or left & right or left | right != free:
            raise ValueError('The remaining-site subsets do not cover the parent domain disjointly')
        if any(child['fixed'] != node['fixed'] for child in children) or [set(child['domain']) for child in children] != [ones | left, ones | right]:
            raise ValueError('The remaining-site children lose fixed factories or free-site alternatives')
        special.append({'node': identifier, 'fixed_factories': len(ones), 'free_candidates': len(free), 'subset_sizes': [len(left), len(right)]})
    elif isinstance(rule, dict):
        column = rule['binary_column']
        if column in fixed or {child['fixed'][str(column)] for child in children} != {0, 1}:
            raise ValueError('The binary split does not cover both integer values')
        for child in children:
            if set(child['domain']) != domain or {key: value for key, value in child['fixed'].items() if key != str(column)} != node['fixed']:
                raise ValueError('The binary split changed an unrelated fixed decision')
    else:
        left, right = [set(child['domain']) for child in children]
        if node['count_lower'] != 1 or node['count_upper'] != 1 or left & right or left | right != domain or any(child['fixed'] != node['fixed'] for child in children):
            raise ValueError('The single-factory domain split is not exhaustive')
    for child in children:
        visit(child['id'])


for node in roots:
    if set(node['domain']) != saf or node['fixed']:
        raise ValueError('A root restricts the original factory domain')
    visit(node['id'])
if seen != set(nodes):
    raise ValueError('The proof contains unreachable domains')
report = {'passed': True, 'optimization_executed': False, 'proof_sha256': hashlib.sha256(args.proof.read_bytes()).hexdigest(),
          'scope': 'Read-only independent combinatorial audit of actual recorded proof domains; numerical LP validity is checked separately',
          'nodes': len(nodes), 'roots': len(roots), 'leaves': sum('children' not in item for item in nodes.values()),
          'remaining_site_splits': special, 'reported_gap': proof['certified_gap_for_candidate']}
args.out.write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report))
