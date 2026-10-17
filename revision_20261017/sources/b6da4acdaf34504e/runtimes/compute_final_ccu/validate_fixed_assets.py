import hashlib
import json
from pathlib import Path

import pandas as pd

base = Path(__file__).resolve().parent
reports = []
for scenario in ['CCU-GH-FT','CCU-GH-MTJ','DAC-GH-FT','DAC-GH-MTJ','GTL-GH','CTL']:
    run_root = base.with_name(base.name+'_ctl_partial') if scenario=='CTL' else base
    directories = [run_root / 'verified_runs' / scenario / label for label in ['baseline','summer_fixed']]
    if not all((path / 'physical_validation.json').exists() and not (path / 'EXPORT_IN_PROGRESS').exists() for path in directories):
        continue
    hashes = [hashlib.sha256((path / 'summary.json').read_bytes()).hexdigest() for path in directories]
    for path,digest in zip(directories,hashes):
        check = json.loads((path / 'physical_validation.json').read_text())
        assert check['passed'] and check['solution_summary_sha256']==digest
    errors = {}
    for name,keys in [('saf_capacity',['location','technology']),('saf_build',['location','technology']),('h2_capacity',['location']),('h2_build',['location'])]:
        tables = [pd.read_csv(path / f'{name}.csv').set_index(keys).value.sort_index() for path in directories]
        assert tables[0].index.equals(tables[1].index),(scenario,name)
        errors[name] = float((tables[0]-tables[1]).abs().max())
    if scenario.startswith('DAC-'):
        tables = [pd.read_csv(path / 'variables.csv',usecols=['variable','value']).set_index('variable').value for path in directories]
        tables = [table[table.index.str.startswith('dac_facility_')].sort_index() for table in tables]
        assert len(tables[0])>0 and tables[0].index.equals(tables[1].index)
        errors['dac_build'] = float((tables[0]-tables[1]).abs().max())
    assert max(errors.values())<=1e-4,(scenario,errors)
    reports.append({'scenario':scenario,'passed':True,'maximum_differences':errors,'summary_sha256':hashes,'scope':'SAF and electrolyzer capacity/build; DAC build where applicable. Auxiliary inventory and routes reoptimized.'})
(base / 'fixed_asset_validation.json').write_text(json.dumps(reports,indent=2))
print(json.dumps(reports),flush=True)
