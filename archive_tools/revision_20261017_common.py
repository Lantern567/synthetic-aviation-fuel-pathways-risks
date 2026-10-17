import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sys


REVISION_DIRECTORY = 'revision_20261017'
RUNTIME_NAMES = ['compute_final', 'compute_final_ccu', 'compute_dac_projected', 'compute_configured_ctl', 'compute_bh_final']
PAIRED = ['CTL', 'GTL-GH', 'CCU-GH-FT', 'CCU-GH-MTJ', 'DAC-GH-FT', 'DAC-GH-MTJ']
BASELINES = ['CTL', 'CTL-BH', 'GTL-GH', 'GTL-BH', 'CCU-GH-FT', 'CCU-GH-MTJ',
             'CCU-BH-FT', 'CCU-BH-MTJ', 'DAC-GH-FT', 'DAC-GH-MTJ', 'DAC-BH-FT', 'DAC-BH-MTJ']
CASES = [(scenario, 'baseline') for scenario in BASELINES] + [(scenario, 'summer_fixed') for scenario in PAIRED]
FAMILIES = {'CCU': 'green_hydrogen_supply_chain_optimization', 'DAC': 'dac_hydrogen_saf_supply_chain_optimization',
            'GTL': 'natural_gas_supply_chain_optimization', 'CTL': 'coal_hydrogen_saf_optimization'}


def native(path):
    path = Path(path).resolve()
    return Path('\\\\?\\' + str(path)) if sys.platform == 'win32' and not str(path).startswith('\\\\?\\') else path


def digest(path):
    with native(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read_json(path):
    return json.loads(native(path).read_text(encoding='utf-8'))


def write_json(path, value):
    path = native(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def safe_path(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or path == root:
        raise ValueError(f'Path escapes the selected archive directory: {relative}')
    return path


def copy_checked(source, destination):
    source, destination = native(source), native(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    expected = digest(source)
    if destination.exists():
        if digest(destination) != expected:
            raise ValueError(f'Existing archived bytes differ: {destination}')
        return
    shutil.copyfile(source, destination)
    if digest(destination) != expected:
        raise ValueError(f'Archive copy differs: {destination}')


def expand_entry(source_root, target_root, record):
    source = safe_path(source_root, record['stored_path'])
    target = safe_path(target_root, record['original_path'])
    if digest(source) != record['stored_sha256']:
        raise ValueError(f'Packed archive file changed: {source}')
    if target.exists():
        if digest(target) != record['payload_sha256']:
            raise ValueError(f'Existing prepared file differs: {target}')
        return target
    native(target.parent).mkdir(parents=True, exist_ok=True)
    opener = gzip.open if record['compression'] == 'gzip' else open
    if record['compression'] not in ['gzip', 'none']:
        raise ValueError(f'Unsupported compression: {record["compression"]}')
    with opener(native(source), 'rb') as incoming, native(target).open('xb') as outgoing:
        shutil.copyfileobj(incoming, outgoing)
    if native(target).stat().st_size != record['payload_bytes'] or digest(target) != record['payload_sha256']:
        raise ValueError(f'Expanded archive file differs: {target}')
    return target


def expand_subtree(source_root, target_root, records, prefix):
    prefix = prefix.rstrip('/') + '/'
    selected = []
    for record in records:
        if not record['original_path'].startswith(prefix):
            continue
        relocated = dict(record, original_path=record['original_path'][len(prefix):])
        selected.append(expand_entry(source_root, target_root, relocated))
    if not selected:
        raise ValueError(f'No archived files for required subtree: {prefix}')
    return selected


def revision_paths(archive_root):
    archive = Path(archive_root).resolve()
    revision = archive / REVISION_DIRECTORY
    manifest = read_json(revision / 'revision_manifest.json')
    return archive, revision, manifest


def require_complete(manifest):
    actual = {(record['scenario'], record['label']) for record in manifest['runs']}
    if manifest['state'] != 'complete' or actual != set(CASES):
        raise ValueError('The complete eighteen-run revision archive is required for this command')


def verify_input_files(runtime, hashes):
    for relative, expected in hashes.items():
        source = safe_path(Path(runtime) / 'inputs', relative)
        if digest(source) != expected:
            raise ValueError(f'The restored input differs from the actual run input inventory: {relative}')
