import argparse
import gc
import hashlib
import json
from pathlib import Path

import coptpy as cp
import numpy as np
import pandas as pd


def load(environment, path):
    model = environment.createModel()
    model.read(str(path))
    variables, rows = model.getVars(), model.getConstrs()
    result = {'columns': [item.getName() for item in variables], 'rows': [item.getName() for item in rows],
              'matrix': model.getA().tocsr(), 'types': np.array([item.getType() for item in variables])}
    for key, field, selection in [('lb', cp.COPT.Info.LB, variables), ('ub', cp.COPT.Info.UB, variables),
                                   ('objective', cp.COPT.Info.Obj, variables), ('lhs', cp.COPT.Info.LB, rows), ('rhs', cp.COPT.Info.UB, rows)]:
        result[key] = np.asarray(model.getInfo(field, selection))
    del model, variables, rows
    gc.collect()
    return result


parser = argparse.ArgumentParser()
parser.add_argument('--original', type=Path, required=True)
parser.add_argument('--constructed', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
environment = cp.Envr()
left, right = [load(environment, path) for path in [args.original, args.constructed]]
indices = {}
for kind in ['columns', 'rows']:
    original, current = pd.Index(left[kind]), pd.Index(right[kind])
    if not original.is_unique or not current.is_unique or len(original) != len(current):
        raise ValueError(f'MPS names are duplicated or differ in size: {kind}')
    indices[kind] = current.get_indexer(original)
    if (indices[kind] < 0).any():
        raise ValueError(f'The constructed MPS omits original model names: {kind}')
matrix = right['matrix'][indices['rows'], :][:, indices['columns']].tocsr()
difference = left['matrix'] - matrix
error = float(np.max(np.abs(difference.data), initial=0))
checks = {'coefficient_matrix': {'maximum_absolute_error': error, 'passed': error <= 1e-9}}
for key in ['lb', 'ub', 'objective', 'lhs', 'rhs', 'types']:
    index = indices['rows' if key in ['lhs', 'rhs'] else 'columns']
    actual, expected = right[key][index], left[key]
    if key == 'types':
        checks[key] = {'mismatches': int(np.sum(actual != expected)), 'passed': bool(np.array_equal(actual, expected))}
    else:
        checks[key] = {'maximum_absolute_error': float(np.max(np.abs(actual - expected), initial=0)),
                       'passed': bool(np.allclose(actual, expected, rtol=1e-12, atol=1e-9))}
report = {'passed': all(item['passed'] for item in checks.values()), 'optimization_executed': False,
          'scope': 'COPT reads both complete MPS files; columns and rows are matched by their unique actual names before comparing coefficients, bounds, variable types and objective coefficients',
          'rows': len(left['rows']), 'columns': len(left['columns']), 'checks': checks,
          'original_column_order_sha256': hashlib.sha256('\n'.join(left['columns']).encode()).hexdigest(),
          'constructed_column_order_sha256': hashlib.sha256('\n'.join(right['columns']).encode()).hexdigest(),
          'original_row_order_sha256': hashlib.sha256('\n'.join(left['rows']).encode()).hexdigest(),
          'constructed_row_order_sha256': hashlib.sha256('\n'.join(right['rows']).encode()).hexdigest(),
          'comparison_source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
args.out.write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report), flush=True)
if not report['passed']:
    raise ValueError(report)
