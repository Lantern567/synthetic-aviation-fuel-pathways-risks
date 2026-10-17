import json
import sys
from pathlib import Path

base = Path(__file__).resolve().parent
scenario,label,iteration = sys.argv[1:4]
out = base / 'decomposed_runs' / scenario / label
report = json.loads((out / f'repair_status_{iteration}.json').read_text())
assert report['physically_feasible_algebraically'],report
report.update(scenario=scenario,label=label,relative_gap_tolerance=0.01,passed=report['gap']<=0.010001)
assert report['passed'],report
if (out / 'certificate.json').exists():
    previous = json.loads((out / 'certificate.json').read_text())
    if report['objective']>previous['objective']+1e-3:
        print('PREVIOUS_CERTIFICATE_RETAINED',scenario,label,previous['objective'],report['objective'],flush=True)
        sys.exit(0)
    archive = out / 'accepted_history'
    archive.mkdir(exist_ok=True)
    number = len(list(archive.glob('certificate_*.json')))
    (archive / f'certificate_{number}.json').write_bytes((out / 'certificate.json').read_bytes())
    (archive / f'values_{number}.npz').write_bytes((out / 'values.npz').read_bytes())
(out / 'certificate.json').write_text(json.dumps(report,indent=2))
(out / 'values.npz').write_bytes((out / f'repaired_values_{iteration}.npz').read_bytes())
print('CERTIFICATE_ACCEPTED',scenario,label,report['gap'],flush=True)
