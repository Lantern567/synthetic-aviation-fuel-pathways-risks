import argparse
import gzip
import hashlib
import importlib.metadata
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tarfile
import time


RUNTIMES = ['compute_final', 'compute_final_ccu', 'compute_dac_projected', 'compute_configured_ctl', 'compute_bh_final']
SKIP_DIRECTORIES = {'__pycache__', '.git', 'venv', '.venv', 'node_modules'}
PACK_EXTENSIONS = {'.csv', '.db', '.sqlite', '.jsonl', '.json'}
STATIC_RUNTIME_JSON = {'input_sha256.json', 'raw_profile_validation.json', 'dependency_source_manifest.json', 'diagnostic_scope.json'}


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def selected(path, relative):
    return (not set(relative.parts) & SKIP_DIRECTORIES and path.suffix.lower() not in {'.pyc', '.log', '.lic', '.key', '.pem'}
            and 'license' not in path.name.lower() and path.name != '.env')


def collect(root, output):
    root, output = root.resolve(), output.resolve()
    if not output.is_relative_to(root / 'archive_staging'):
        raise ValueError('Choose an output under the revision archive_staging directory')
    stage = output.with_suffix('').with_suffix('')
    if stage.exists() or output.exists():
        raise FileExistsError('Choose a new source-snapshot name')
    stage.mkdir(parents=True)
    records = []

    def copy(source, relative, role):
        target = stage / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        source_hash = digest(source)
        database = source.suffix.lower() in {'.db', '.sqlite'}
        if database:
            with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as incoming, sqlite3.connect(target) as outgoing:
                incoming.backup(outgoing)
                if outgoing.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                    raise ValueError(f'Invalid SQLite snapshot: {source}')
            scope = 'SQLite online backup of the actual input database'
        else:
            shutil.copyfile(source, target)
            scope = 'Byte-identical copy of the actual runtime input or source'
        if digest(source) != source_hash:
            raise ValueError(f'Runtime input changed during collection: {source}')
        payload_hash, payload_bytes = digest(target), target.stat().st_size
        if not database and payload_hash != source_hash:
            raise ValueError(f'Source copy differs: {source}')
        if source.suffix.lower() == '.jsonl':
            with target.open('r', encoding='utf-8') as stream:
                for line in stream:
                    json.loads(line)
        packed = target.suffix.lower() in PACK_EXTENSIONS and payload_bytes >= 1024 * 1024
        if packed:
            compressed = target.with_name(target.name + '.gz')
            with target.open('rb') as incoming, compressed.open('xb') as raw:
                with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0, compresslevel=6) as outgoing:
                    shutil.copyfileobj(incoming, outgoing)
            with gzip.open(compressed, 'rb') as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() != payload_hash:
                    raise ValueError(f'Lossless compression failed: {relative}')
            target.unlink()
            stored = compressed
        else:
            stored = target
        records.append({'role': role, 'source_path': str(source), 'source_sha256': source_hash,
                        'original_path': relative.as_posix(), 'payload_sha256': payload_hash, 'payload_bytes': payload_bytes,
                        'stored_path': stored.relative_to(stage).as_posix(), 'stored_sha256': digest(stored),
                        'stored_bytes': stored.stat().st_size, 'compression': 'gzip' if packed else 'none', 'copy_scope': scope})

    projects = {str((root / runtime / 'project').resolve()) for runtime in RUNTIMES}
    if len(projects) != 1:
        raise ValueError(f'The five actual runtimes no longer share the same project source: {projects}')
    project = Path(next(iter(projects)))
    for source in sorted(project.rglob('*')):
        relative = source.relative_to(project)
        if source.is_file() and selected(source, relative):
            if source.suffix == '.gz' and source.with_suffix('').exists():
                continue
            copy(source, Path('shared_project') / relative, 'shared_actual_project_dependency')
    for runtime in RUNTIMES:
        directory = root / runtime
        if not directory.is_dir():
            raise FileNotFoundError(directory)
        for source in sorted(directory.iterdir()):
            if source.is_file() and (source.suffix == '.py' or source.name in STATIC_RUNTIME_JSON):
                copy(source, Path('runtimes') / runtime / source.name, 'actual_runtime_source')
        for part in ['inputs', 'routing']:
            folder = directory / part
            if not folder.is_dir():
                raise FileNotFoundError(folder)
            for source in sorted(folder.rglob('*')):
                relative = source.relative_to(folder)
                if source.is_file() and selected(source, relative):
                    if source.suffix == '.gz' and source.with_suffix('').exists():
                        continue
                    copy(source, Path('runtimes') / runtime / part / relative, 'actual_runtime_' + part)
    environment = {'python': sys.version, 'platform': sys.platform,
                   'packages': {name: importlib.metadata.version(name) for name in
                                ['coptpy', 'numpy', 'pandas', 'scipy', 'PyYAML', 'requests', 'openpyxl', 'psutil', 'scikit-learn', 'networkx', 'gurobipy']},
                   'license_distribution': 'Solver license files and the environment-specific license launcher are excluded'}
    if len({record['original_path'] for record in records}) != len(records) or len({record['stored_path'] for record in records}) != len(records):
        raise ValueError('Every collected source/input must have one distinct original and packed path')
    manifest = {'schema_version': 1, 'collected_unix': time.time(), 'runtime_names': RUNTIMES,
                'shared_project_source': str(project), 'file_count': len(records), 'files': records, 'environment': environment}
    write_json(stage / 'runtime_sources_manifest.json', manifest)
    with tarfile.open(output, 'w:gz', compresslevel=6, format=tarfile.PAX_FORMAT) as archive:
        for path in sorted(stage.rglob('*')):
            if path.is_file():
                archive.add(path, arcname=path.relative_to(stage).as_posix(), recursive=False)
    receipt = {'path': str(output), 'sha256': digest(output), 'bytes': output.stat().st_size,
               'files': len(records), 'manifest_sha256': digest(stage / 'runtime_sources_manifest.json')}
    write_json(output.with_suffix(output.suffix + '.json'), receipt)
    print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    collect(args.root, args.out)
