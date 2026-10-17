import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def pack(runtime, output):
    runtime = Path('\\\\?\\' + str(runtime)) if sys.platform == 'win32' else runtime
    required = runtime / 'project/products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/src/core/green_hydrogen_optimization_model.py'
    if not required.is_file():
        raise FileNotFoundError(required)
    with tarfile.open(output, 'x:gz', format=tarfile.PAX_FORMAT, compresslevel=6) as archive:
        for source in sorted(runtime.rglob('*')):
            relative = source.relative_to(runtime)
            if source.is_file() and not set(relative.parts) & {'verified_runs', 'runs', '__pycache__'}:
                if 'license' in source.name.lower() or source.suffix in {'.lic', '.key', '.pem'}:
                    raise ValueError(f'Unexpected licence/private file: {source}')
                archive.add(source, relative.as_posix(), recursive=False)
    print(json.dumps({'path': str(output), 'sha256': digest(output), 'bytes': output.stat().st_size}))


def check(runtime, launcher, out, original):
    out.mkdir(parents=True, exist_ok=False)
    route = runtime / 'routing/new_routes.jsonl'
    before = digest(route)
    with (out / 'model_construction.log').open('w', encoding='utf-8') as log:
        subprocess.run(['bash', str(launcher), str(runtime / 'run_model.py'), 'CCU-GH-FT', 'baseline', '--export-model', '--threads', '2'], stdout=log, stderr=subprocess.STDOUT, check=True)
    exported = runtime / 'runs/CCU-GH-FT/baseline'
    if not (exported / 'MODEL_EXPORTED').is_file() or digest(route) != before:
        raise ValueError('The restored model must construct using its archived route records')
    with gzip.open(exported / 'model.mps.gz', 'rb') as stream:
        matrix_hash = hashlib.file_digest(stream, 'sha256').hexdigest()
    with gzip.open(original, 'rb') as stream:
        original_hash = hashlib.file_digest(stream, 'sha256').hexdigest()
    report = {'passed': True, 'scope': 'Real COPT model construction from the archive-prepared exact source and inputs; no optimization',
              'optimization_executed': False, 'scenario': 'CCU-GH-FT', 'label': 'baseline',
              'model_mps_payload_sha256': matrix_hash, 'original_model_mps_payload_sha256': original_hash,
              'mps_payload_byte_identical': matrix_hash == original_hash,
              'route_cache_sha256_before_and_after': before,
              'run_model_sha256': digest(runtime / 'run_model.py'),
              'configuration_sha256': digest(runtime / 'archived_execution_config.yaml')}
    (out / 'model_construction_check.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--pack', action='store_true')
    parser.add_argument('--launcher', type=Path)
    parser.add_argument('--original-model', type=Path)
    args = parser.parse_args()
    if args.pack:
        pack(args.runtime.resolve(), args.out.resolve())
    else:
        check(args.runtime.resolve(), args.launcher.resolve(), args.out.resolve(), args.original_model.resolve())
