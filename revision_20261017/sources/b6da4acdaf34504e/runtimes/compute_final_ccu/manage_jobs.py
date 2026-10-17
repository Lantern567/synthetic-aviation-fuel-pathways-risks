import argparse
import json
import subprocess
import time
from pathlib import Path

import psutil


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--launch', nargs='*', default=[])
    parser.add_argument('--label', choices=['baseline', 'summer_fixed'], default='baseline')
    parser.add_argument('--from-stage', default='model')
    parser.add_argument('--restart', action='store_true')
    args = parser.parse_args()
    base = Path(__file__).resolve().parent
    records = base / 'job_records'
    records.mkdir(exist_ok=True)
    active = []
    for process in psutil.process_iter(['pid', 'cmdline']):
        command = process.info['cmdline'] or []
        if str(base / 'execute_job.py') in command:
            active.append(process.info['pid'])
    if len(active) + len(args.launch) > 3:
        raise RuntimeError(f'At most three concurrent revision jobs: {active}')
    if args.launch and psutil.virtual_memory().available < 60 * 1024**3:
        raise RuntimeError('Less than 60 GiB memory available before launch')
    if args.launch:
        inputs = base / 'inputs' / ('baseline' if args.label == 'baseline' else 'summer')
        manifest = json.loads((inputs / 'manifest.json').read_text())
        if '0.1632' in manifest['solar_conversion']:
            raise RuntimeError('Unrevised solar input selected')
    for scenario in args.launch:
        output = records / scenario / args.label
        if (output / 'status.json').exists() and args.from_stage == 'model':
            previous = json.loads((output / 'status.json').read_text())
            if not args.restart or previous['state'] != 'failed':
                raise RuntimeError(f'Existing job requires an explicit failed-job restart decision: {output}')
            attempt = output / 'attempts' / str(time.time_ns())
            attempt.mkdir(parents=True)
            for path in output.glob('*.json'):
                (attempt / path.name).write_bytes(path.read_bytes())
            for path in output.glob('*.log'):
                (attempt / path.name).write_bytes(path.read_bytes())
        if args.label == 'summer_fixed':
            parent = json.loads((records / scenario / 'baseline/status.json').read_text())
            if parent['state'] != 'complete':
                raise RuntimeError(f'Baseline is not verified: {scenario}')
        output.mkdir(parents=True, exist_ok=True)
        with (output / 'console.log').open('a') as stream:
            process = subprocess.Popen(['bash', str(base / 'python_copt.sh'), str(base / 'execute_job.py'), scenario, args.label, '--from-stage', args.from_stage], cwd=base, stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
        (output / 'launch.json').write_text(json.dumps({'pid': process.pid, 'scenario': scenario, 'label': args.label, 'launched_unix': time.time(), 'from_stage': args.from_stage}, indent=2))
        print('LAUNCHED', scenario, args.label, process.pid)
    states = []
    for path in sorted(records.glob('*/*/status.json')):
        record = json.loads(path.read_text())
        record['log_directory'] = str(path.parent)
        record['last_stage_result'] = record.pop('history', [])[-1:]
        states.append(record)
    print(json.dumps({'jobs': states, 'available_memory_gib': round(psutil.virtual_memory().available / 1024**3, 1), 'load': psutil.getloadavg()}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
