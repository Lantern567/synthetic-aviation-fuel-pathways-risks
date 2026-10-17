import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tarfile


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


parser = argparse.ArgumentParser()
parser.add_argument('--root', type=Path, required=True)
parser.add_argument('--cases', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
root, output = args.root.resolve(), args.out.resolve()
if not output.is_relative_to(root / 'archive_staging'):
    raise ValueError('The solver-record bundle must remain within archive_staging')
stage = output.with_suffix('').with_suffix('')
stage.mkdir(parents=True, exist_ok=False)
records, cases = [], []


def collect(source, relative):
    if not source.resolve().is_relative_to(root):
        raise ValueError(f'Solver record is outside the scientific revision: {source}')
    before = digest(source)
    target = stage / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    if digest(source) != before or digest(target) != before:
        raise ValueError(f'Solver record changed during collection: {source}')
    records.append({'path': relative.as_posix(), 'sha256': before, 'bytes': target.stat().st_size,
                    'source_path': str(source)})


for item in json.loads(args.cases.read_text(encoding='utf-8'))['runs']:
    scenario, label, runtime_name = item['scenario'], item['label'], item['runtime']
    runtime = root / runtime_name
    run = runtime / 'verified_runs' / scenario / label
    source_summary = run / 'summary.json'
    if (run / 'EXPORT_IN_PROGRESS').exists() or digest(source_summary) != item['summary_sha256']:
        raise ValueError(f'The completed original result changed: {scenario}/{label}')
    certificate = json.loads((run / 'certificate.json').read_text(encoding='utf-8'))
    if not certificate['passed'] or certificate['gap'] > .01:
        raise ValueError(f'The real full-model certificate is not accepted: {scenario}/{label}')
    source = runtime / 'decomposed_runs' / scenario / label
    if digest(source / 'certificate.json') != digest(run / 'certificate.json'):
        raise ValueError(f'The projection certificate differs from the actual saved result: {scenario}/{label}')
    for path in sorted(source.rglob('*')):
        if path.is_file() and path.suffix in {'.json', '.npz', '.log'}:
            collect(path, Path('records') / scenario / label / path.relative_to(source))
    proof = source / 'partition_bound/proof.json'
    if proof.exists():
        model = runtime / 'runs' / scenario / label / 'model.mps.gz'
        expected = json.loads(proof.read_text(encoding='utf-8'))['original_objective']['source_model_sha256']
        if digest(model) != expected or expected != certificate['source_sha256']:
            raise ValueError('The integer-partition proof must bind the complete original MPS')
        collect(model, Path('original_models') / scenario / label / 'model.mps.gz')
    job = runtime / 'job_records' / scenario / label
    for path in sorted(job.rglob('*')):
        if path.is_file() and path.suffix in {'.json', '.log'}:
            collect(path, Path('job_records') / scenario / label / path.relative_to(job))
    cases.append(item | {'certificate_sha256': digest(run / 'certificate.json'), 'original_mps_sha256': certificate['source_sha256'],
                         'partition_proof_archived': proof.exists()})
for path in sorted((root / 'tools/repair_mip').glob('*.py')):
    collect(path, Path('current_solver_support_source/repair_mip') / path.name)
for path in sorted((root / 'tools').glob('*.py')):
    if path.name in {'project_routes.py', 'validate_partition.py', 'solve_master_mip.py', 'gtl_design_probe.py'}:
        collect(path, Path('current_solver_support_source') / path.name)
manifest = {'schema_version': 1, 'cases': cases, 'files': records, 'optimization_executed': False,
            'dual_values_scope': 'Only actually saved primal LP values are included; independent dual vectors were not saved by the original computation',
            'solver_support_source_scope': 'Current support programs are recorded separately from actual per-run model snapshots and saved proof-source hashes'}
(stage / 'solver_records_manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
with tarfile.open(output, 'x:gz', format=tarfile.PAX_FORMAT, compresslevel=6) as archive:
    for path in sorted(stage.rglob('*')):
        if path.is_file():
            archive.add(path, path.relative_to(stage).as_posix(), recursive=False)
receipt = {'path': str(output), 'sha256': digest(output), 'bytes': output.stat().st_size,
           'cases': len(cases), 'manifest_sha256': digest(stage / 'solver_records_manifest.json')}
output.with_suffix(output.suffix + '.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
print(json.dumps(receipt), flush=True)
