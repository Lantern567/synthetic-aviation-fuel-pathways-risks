import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys


def native(path):
    return Path('\\\\?\\' + str(path.resolve())) if sys.platform == 'win32' else path


def digest(path):
    with native(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive-root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    archive = args.archive_root.resolve()
    manifest = json.loads((archive / 'SHA256SUMS.json').read_text(encoding='utf-8'))
    assert len(manifest) > 400
    for relative, expected in manifest.items():
        path = archive / relative
        assert native(path).is_file(), f'Download the complete release ZIP: {relative} is missing'
        assert digest(path) == expected, f'File hash mismatch: {relative}'
    source = json.loads((archive / 'provenance/run_sources.json').read_text(encoding='utf-8'))
    assert len(source['records']) == 12 and source['source_snapshots'] == 36
    for record in source['records']:
        root = archive / record['source_snapshot']
        for collection in ('source_snapshots', 'validation_records', 'accompanying_data/runs'):
            summary = archive / collection / record['scenario'] / record['label'] / 'summary.json'
            assert digest(summary) == record['summary_sha256'], (collection, record['scenario'], record['label'])
        for item in record['files']:
            assert digest(archive / item['path']) == item['sha256']
        assert len(list((root / 'source').glob('*.py'))) == 3
    packed = json.loads((archive / 'provenance/packed_inputs.json').read_text(encoding='utf-8'))
    for record in packed['files']:
        assert digest(archive / record['path']) == record['sha256']
        with gzip.open(native(archive / record['path']), 'rb') as stream:
            assert hashlib.file_digest(stream, 'sha256').hexdigest() == record['unpacked_sha256'], record['path']
    count = len([p for p in (archive / 'accompanying_data').rglob('*') if p.is_file()])
    assert count == 303
    args.output.mkdir(parents=True, exist_ok=True)
    report = {'passed': True, 'files_verified': len(manifest), 'original_execution_sources': 36,
              'source_summaries_matched': 12, 'lossless_compressed_files': len(packed['files']),
              'accompanying_data_files': count, 'optimization_executed': False,
              'scope': 'Distributed file integrity, exact execution-source/result linkage and lossless compression.'}
    (args.output / 'archive_verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
