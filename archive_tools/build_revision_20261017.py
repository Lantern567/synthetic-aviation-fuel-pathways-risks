import argparse
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tarfile
import zipfile

from revision_20261017_common import CASES, RUNTIME_NAMES, copy_checked, digest, native, read_json, safe_path, write_json


def validations(scenario):
    names = ['byproduct_physical_validation.json' if '-BH' in scenario else 'physical_validation.json',
             'independent_hydrogen_transport/hydrogen_transport_validation.json',
             'independent_inventory_cost/inventory_cost_validation.json']
    if scenario.startswith('DAC-'):
        names.append('independent_co2/co2_validation.json')
    if scenario.startswith('CCU-'):
        names.append('ccu_co2_accounting_validation.json')
    if scenario == 'GTL-BH':
        names.append('extended_natural_gas_validation.json')
    return names


def accepted(run, accounts, processor):
    if not native(run / 'summary.json').is_file() or not native(accounts / 'accounts.json').is_file():
        return False
    if native(run / 'EXPORT_IN_PROGRESS').exists():
        return False
    summary, account = read_json(run / 'summary.json'), read_json(accounts / 'accounts.json')
    sha = digest(run / 'summary.json')
    if not summary['has_solution'] or not summary['algebraic_validation']['passed'] or not 0 <= summary['gap'] <= .01:
        return False
    if not account['checks']['passed'] or account['source_summary_sha256'] != sha or account['processor_sha256'] != digest(processor):
        return False
    for filename in validations(summary['scenario']):
        if not native(run / filename).is_file():
            return False
        report = read_json(run / filename)
        hashes = [value for key, value in report.get('input_sha256', {}).items()
                  if Path(key).name == 'summary.json' or key.endswith('\\summary.json')]
        if report.get('passed') is not True or (report.get('solution_summary_sha256') != sha and hashes != [sha]):
            return False
    for filename, expected in account['source_hashes'].items():
        if digest(run / filename) != expected:
            raise ValueError(f'Actual account input changed: {run / filename}')
    for filename, expected in read_json(accounts / 'SHA256.json').items():
        if digest(accounts / filename) != expected:
            raise ValueError(f'Actual account output changed: {accounts / filename}')
    return True


def install_bundle(bundle, receipt, revision):
    receipt_data = read_json(receipt)
    bundle_hash = digest(bundle)
    if bundle_hash != receipt_data['sha256'] or native(bundle).stat().st_size != receipt_data['bytes']:
        raise ValueError('The downloaded actual-runtime bundle does not match its collection receipt')
    relative = 'sources/' + bundle_hash[:16]
    target = revision / relative
    if not native(target).exists():
        native(target).mkdir(parents=True)
        with tarfile.open(native(bundle), 'r:gz') as archive:
            for member in archive.getmembers():
                safe_path(target, member.name)
                if not member.isfile() or 'license' in Path(member.name).name.lower() or Path(member.name).suffix in {'.lic', '.key', '.pem'}:
                    raise ValueError(f'Unexpected archive member: {member.name}')
            archive.extractall(native(target), filter='data')
    manifest_path = target / 'runtime_sources_manifest.json'
    if digest(manifest_path) != receipt_data['manifest_sha256']:
        raise ValueError('Actual-runtime source inventory differs from its receipt')
    manifest = read_json(manifest_path)
    if manifest['runtime_names'] != RUNTIME_NAMES or manifest['file_count'] != len(manifest['files']):
        raise ValueError('The five actual source runtimes are required')
    for record in manifest['files']:
        path = safe_path(target, record['stored_path'])
        if digest(path) != record['stored_sha256']:
            raise ValueError(f'Actual runtime input/source changed: {path}')
    copy_checked(receipt, target / 'collection_receipt.json')
    return relative, digest(manifest_path), manifest


def pack(source, revision, relative):
    source = native(source)
    sha, size = digest(source), source.stat().st_size
    compressed = source.suffix.lower() in {'.csv', '.json', '.jsonl', '.npz'} and size >= 1024 * 1024
    stored_relative = relative + ('.gz' if compressed else '')
    target = native(safe_path(revision, stored_relative))
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file():
        opener = gzip.open if compressed else open
        with opener(target, 'rb') as current:
            current_hash = hashlib.file_digest(current, 'sha256').hexdigest()
        if current_hash == sha:
            return {'original_path': relative, 'stored_path': stored_relative,
                    'payload_sha256': sha, 'payload_bytes': size,
                    'stored_sha256': digest(target), 'stored_bytes': target.stat().st_size,
                    'compression': 'gzip' if compressed else 'none'}
    temporary = target.with_name(target.name + '.packing')
    if compressed:
        with source.open('rb') as incoming, temporary.open('wb') as raw:
            with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0, compresslevel=6) as outgoing:
                shutil.copyfileobj(incoming, outgoing)
        with gzip.open(temporary, 'rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != sha:
                raise ValueError(f'Packed result does not reproduce original bytes: {source}')
    else:
        shutil.copyfile(source, temporary)
        if digest(temporary) != sha:
            raise ValueError(f'Copied result differs: {source}')
    if digest(source) != sha:
        raise ValueError(f'Actual result changed during collection: {source}')
    temporary.replace(target)
    return {'original_path': relative, 'stored_path': stored_relative,
            'payload_sha256': sha, 'payload_bytes': size,
            'stored_sha256': digest(target), 'stored_bytes': target.stat().st_size,
            'compression': 'gzip' if compressed else 'none'}


def archive_file(source, destination):
    destination = native(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(native(source), destination)
    if digest(source) != digest(destination):
        raise ValueError(f'Archive generation changed source bytes: {source}')


def install_solver_records(bundle, receipt, revision):
    metadata = read_json(receipt)
    if digest(bundle) != metadata['sha256'] or native(bundle).stat().st_size != metadata['bytes']:
        raise ValueError('The solver-record bundle differs from its collection receipt')
    relative = 'provenance/solver_records/' + metadata['sha256'][:16]
    target = revision / relative
    if not native(target).exists():
        native(target).mkdir(parents=True)
        with tarfile.open(native(bundle), 'r:gz') as archive:
            for member in archive.getmembers():
                safe_path(target, member.name)
                if not member.isfile():
                    raise ValueError(f'Unexpected solver-record member: {member.name}')
            archive.extractall(native(target), filter='data')
    record_manifest = target / 'solver_records_manifest.json'
    if digest(record_manifest) != metadata['manifest_sha256']:
        raise ValueError('The solver-record source manifest changed')
    records = read_json(record_manifest)
    for item in records['files']:
        if digest(safe_path(target, item['path'])) != item['sha256']:
            raise ValueError(f'An original saved proof record changed: {item["path"]}')
    copy_checked(receipt, target / 'collection_receipt.json')
    return relative, digest(record_manifest), records


def collect_supporting_artifacts(work, revision):
    project_root = work.parents[2]
    external_root = Path('E:/green_methanol_for_port_transportation-main').resolve()
    contract_path = work / 'figures_spatial/final_input_contract.json'
    contract = read_json(contract_path)
    sources = {}

    def add(path, role, expected=None):
        path = Path(path).resolve()
        actual = digest(path)
        if expected is not None and actual != expected:
            raise ValueError(f'The final artifact source contract changed: {path}')
        previous = sources.get(path)
        if previous is not None:
            if previous['sha256'] != actual:
                raise ValueError(f'An artifact source changed during collection: {path}')
            previous['roles'].add(role)
            return
        sources[path] = {'sha256': actual, 'roles': {role}}

    for record in contract['files']:
        source = Path(record['path'])
        if native(source).stat().st_size != record['bytes']:
            raise ValueError(f'Artifact source bytes differ from the final input contract: {source}')
        add(source, record['role'], record['sha256'])
    add(contract_path, 'Final PV, resource and spatial source contract')
    add(work / 'figures_spatial/portability_validation.json', 'Executed independent restoration and scientific-input reproduction report')
    add(work / 'figures_spatial/reproducibility_source/check_restored_inputs.py', 'Actual independent restoration and comparison implementation')
    temporal = work / 'figures_temporal'
    for source in sorted(temporal.glob('*.py')):
        add(source, 'Executed temporal figure preparation, rendering or verification source')
    add(temporal / 'README.md', 'Temporal figure reproduction instructions')
    for folder in ['source', 'inputs', 'temporal_data']:
        for source in sorted((temporal / folder).rglob('*')):
            if source.is_file() and source.suffix in {'.py', '.json', '.csv'}:
                add(source, 'Final temporal template, prepared input or numerical contract')
    for source in sorted((temporal / 'outputs').iterdir()):
        if source.is_file() and source.suffix in {'.png', '.pdf', '.svg', '.json', '.csv'} and '_preview' not in source.name:
            add(source, 'Final temporal figure or saved verification record')
    gtl = work.parent / 'github_archive/repository/archived_outputs/products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/ft_one_step'
    for name in ['complete_solution_20260201_215354.json', 'hourly_production_summary_20260201_215354.csv']:
        add(gtl / name, 'Preserved original direct-FT GTL temporal source')
    for name in ['manifest.json', 'GTL_complete_solution.json', 'GTL_carbon_emissions.json']:
        add(work.parent / 'revision_20261007/figures_cost/adapted_data' / name, 'Preserved normalized direct-FT GTL temporal source')
    for name in ['check_synthesis_accounts.py', 'check_natural_gas_price.py', 'natural_gas_price_verification.json', 'synthesis_check/verification.json']:
        add(work / 'postprocess' / name, 'Independent final route-electricity or actual natural-gas price verification')
    for source in sorted((work / 'model_patch').glob('*.py')):
        add(source, 'Scientific revision model implementation')
    for source in sorted((work / 'result_tables').glob('*.py')):
        add(source, 'Actual result-table preparation source')
    for source in sorted((work / 'result_tables/output').glob('*.csv')):
        add(source, 'Final result-table numerical contract')
    for name in ['publication_values.json', 'main_result_replacements.json', 'si_result_replacements.json',
                 'si_result_table_updates.json', 'si_result_table_bindings.json', 'result_integration_check.json',
                 'saved_science_audit.json', 'main_result_replacements.py', 'si_result_replacements.py',
                 'update_si_results.py', 'integrate_result_plans.py', 'review_result_boundaries.py',
                 'audit_saved_science.py', 'result_update_workflow.md']:
        add(work / 'document_plan' / name, 'Final manuscript numerical binding source or saved scientific-content audit')
    for name in ['publish.py', 'publication_audit.json', 'source_presentation.json', 'build/edits.json',
                 'output/Figure_4_editable_02.pptx', 'output/Figure_4.pdf', 'output/Figure_4.png']:
        add(work / 'figures_architecture' / name, 'Editable conceptual figure, final export or publication provenance')
    records, packed = [], []
    for source, item in sorted(sources.items()):
        if source.is_relative_to(project_root):
            root_name, relative = 'workspace', source.relative_to(project_root)
        elif source.is_relative_to(external_root):
            root_name, relative = 'external_project', source.relative_to(external_root)
        else:
            raise ValueError(f'An artifact input needs an explicit archive root: {source}')
        stored = 'artifacts/' + root_name + '/' + relative.as_posix()
        packed.append(pack(source, revision, stored))
        records.append({'source_path': str(source), 'source_sha256': item['sha256'],
                        'restore_root': root_name, 'relative_path': relative.as_posix(),
                        'archived_original_path': stored, 'roles': sorted(item['roles'])})
    record_manifest = {'schema_version': 1, 'files': records,
                       'source_contract_sha256': digest(contract_path),
                       'original_roots': {'workspace': str(project_root), 'external_project': str(external_root)},
                       'scope': 'Actual PV input preparation, resource/spatial/temporal figures, their final input contracts, inherited templates and selected genuine upstream data; QA images and environment caches excluded'}
    write_json(revision / 'artifacts/source_manifest.json', record_manifest)
    return packed, digest(revision / 'artifacts/source_manifest.json')


def build(work, archive, bundle, receipt, final, release_zip, solver_bundle, solver_receipt, verification_report):
    work, archive = Path(work).resolve(), Path(archive).resolve()
    revision = archive / 'revision_20261017'
    native(revision).mkdir(parents=True, exist_ok=True)
    sources_directory, sources_hash, sources = install_bundle(bundle, receipt, revision)
    runtime_for = {(item['scenario'], item['label']): item['runtime'] for item in read_json(work / 'execution/queue.json')}
    source_lookup = {item['original_path']: item for item in sources['files']}
    if set(runtime_for) != set(CASES):
        raise ValueError('The actual execution queue must identify all eighteen cases')
    processor = work / 'postprocess/update_accounts.py'
    runs, missing, packed = [], [], []
    for scenario, label in CASES:
        run, accounts = work / 'results' / scenario / label, work / 'postprocess/accounts' / scenario / label
        if not accepted(run, accounts, processor):
            missing.append({'scenario': scenario, 'label': label})
            continue
        source_snapshot = 'source_snapshots/' + scenario + '/' + label
        for name in ['summary.json', 'config.yaml', 'model_parameters.json', 'input_sha256.json']:
            archive_file(run / name, revision / source_snapshot / name)
        source_files = list(native(run / 'source').glob('*.py'))
        if not source_files:
            raise ValueError(f'The actual execution source snapshot is missing: {run}')
        for source in source_files:
            archive_file(source, revision / source_snapshot / 'source' / source.name)
        source_hash = digest(run / 'summary.json')
        input_files = read_json(run / 'input_sha256.json')
        for relative, expected in input_files.items():
            source_record = source_lookup['runtimes/' + runtime_for[scenario, label] + '/inputs/' + relative]
            if source_record['payload_sha256'] != expected:
                raise ValueError(f'The collected actual input differs from this run inventory: {scenario}/{label}/{relative}')
        if digest(revision / source_snapshot / 'summary.json') != source_hash:
            raise ValueError('The source snapshot summary must be byte-identical to the actual saved result')
        for source in sorted(native(run).rglob('*')):
            relative = source.relative_to(native(run))
            if source.is_file() and source.suffix not in {'.log', '.pyc'} and '__pycache__' not in relative.parts:
                packed.append(pack(source, revision, 'saved_results/' + scenario + '/' + label + '/' + relative.as_posix()))
        for source in sorted(native(accounts).iterdir()):
            if source.is_file():
                packed.append(pack(source, revision, 'final_accounts/' + scenario + '/' + label + '/' + source.name))
        summary = read_json(run / 'summary.json')
        reports = {name: digest(run / name) for name in validations(scenario)}
        runs.append({'scenario': scenario, 'label': label, 'runtime': runtime_for[scenario, label],
                     'summary_sha256': source_hash, 'source_snapshot': source_snapshot,
                     'input_files_sha256': input_files,
                     'account_sha256': digest(accounts / 'accounts.json'), 'gap': summary['gap'],
                     'actual_execution_sources': {source.name: digest(source) for source in source_files},
                     'saved_validation_report_sha256': reports})
    verification_sources = [work / 'postprocess/update_accounts.py', work / 'postprocess/validate_ccu_accounts.py',
                            work / 'execution/validate_physics.py', work / 'historical_runtime/validate_historical.py',
                            work / 'historical_runtime/repair_mip/validate_extended_natural_gas.py',
                            work / 'historical_runtime/repair_mip/validate_partition.py',
                            work / 'archive_build/review_partition_domains.py']
    verification_sources += sorted((work / 'validation').glob('validate_*.py'))
    verification_manifest = []
    for source in verification_sources:
        destination = revision / 'verification_source' / source.name
        archive_file(source, destination)
        verification_manifest.append({'name': source.name, 'sha256': digest(source), 'source_path': str(source),
                                      'scope': 'Current independent saved-data verification; original execution tools remain in their actual source snapshots'})
    write_json(revision / 'verification_source/source_manifest.json', verification_manifest)
    for name in ['build_inputs.py', 'render_figures.py', 'verify_final_figures.py']:
        archive_file(work / 'figures_cost' / name, revision / 'postprocess_source/figures_cost' / name)
    specification = importlib.util.spec_from_file_location('archived_figure_contract', work / 'figures_cost/build_inputs.py')
    contract = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(contract)
    template_paths = {}
    for name, source in contract.TEMPLATES.items():
        target = revision / 'postprocess_source/original_templates' / (name + '.py')
        archive_file(source, target)
        template_paths[name] = '../original_templates/' + name + '.py'
    historical_paths = {}
    for name, source in [('old_gtl_config', contract.OLD_GTL_CONFIG), ('old_gtl_core', contract.OLD_GTL_CORE), ('sensitivity_registry', contract.SENSITIVITY_REGISTRY)]:
        target = revision / 'postprocess_source/original_parameters' / source.name
        archive_file(source, target)
        historical_paths[name] = '../original_parameters/' + source.name
    write_json(revision / 'postprocess_source/figures_cost/archive_sources.json',
               {'published_root': '../../preserved_GTL', 'templates': template_paths,
                'processor': '../../verification_source/update_accounts.py'} | historical_paths)
    for name in ['carbon_sensitivity_assumptions.json', 'TASK_STATE.md']:
        archive_file(work / 'figures_cost' / name, revision / 'postprocess_source/figures_cost' / name)
    for folder in ['adapted_data', 'figures']:
        directory = work / 'figures_cost' / folder
        if directory.is_dir():
            for source in directory.rglob('*'):
                if source.is_file():
                    packed.append(pack(source, revision, 'figure_data/' + folder + '/' + source.relative_to(directory).as_posix()))
    published = work.parents[2] / 'Nexus系统提交文件_代码归档同步20261015/Accompanying_Data/figure_data'
    for name in ['normalized_pathway_records/GTL_complete_solution.json', 'normalized_pathway_records/GTL_carbon_emissions.json', 'learning_assumptions.json']:
        source = published / name
        archive_file(source, revision / 'preserved_GTL' / name)
    supporting_files, supporting_hash = collect_supporting_artifacts(work, revision)
    packed.extend(supporting_files)
    state = 'complete' if not missing else 'collecting'
    if final and missing:
        raise ValueError(f'A complete release requires all eighteen verified actual runs; missing {missing}')
    if final:
        inputs = work / 'figures_cost/adapted_data/figure_inputs.json'
        render = read_json(work / 'figures_cost/figures/render_manifest.json')
        contract = read_json(inputs)
        if contract['ready'] is not True or contract['new_run_count'] != 18 or render['visual_qa_completed'] is not True or render['input_manifest_sha256'] != digest(inputs):
            raise ValueError('The final archive requires the complete verified figure contract and visual inspection record')
    manifest = {'schema_version': 1, 'state': state, 'expected_runs': 18, 'archived_runs': len(runs),
                'runtime_sources_directory': sources_directory, 'runtime_sources_manifest_sha256': sources_hash,
                'environment': sources['environment'], 'runs': runs, 'missing_runs': missing, 'packed_files': packed,
                'verification_source_manifest_sha256': digest(revision / 'verification_source/source_manifest.json'),
                'archive_tools_sha256': {path.relative_to(archive).as_posix(): digest(path)
                                         for path in sorted((archive / 'archive_tools').glob('*revision_20261017*')) if path.is_file()},
                'original_GTL_scope': 'Preserved original comparator; not included in the eighteen newly solved cases',
                'solver_gap_acceptance': .01, 'optimization_executed_by_archive_tools': False,
                'license_files_distributed': False,
                'source_snapshot_policy': 'Actual per-run source and config override the shared dependency snapshot when preparing a model',
                'verification_policy': 'Current independent verification source is recorded separately from original execution tools and reports'}
    manifest['artifact_source_manifest_sha256'] = supporting_hash
    if bool(solver_bundle) != bool(solver_receipt):
        raise ValueError('Both the actual solver-record bundle and receipt are required')
    if solver_bundle:
        solver_directory, solver_hash, solver_records = install_solver_records(solver_bundle, solver_receipt, revision)
        manifest.update(solver_records_directory=solver_directory, solver_records_manifest_sha256=solver_hash)
        actual = {(item['scenario'], item['label']): item for item in runs}
        for record in solver_records['cases']:
            item = actual[record['scenario'], record['label']]
            if record['summary_sha256'] != item['summary_sha256'] or digest(work / 'results' / item['scenario'] / item['label'] / 'certificate.json') != record['certificate_sha256']:
                raise ValueError('Saved solver proofs must bind the exact accepted result and certificate')
        if final and len(solver_records['cases']) != 18:
            raise ValueError('The final archive requires original certificate and bound records for all eighteen runs')
    elif final:
        raise ValueError('A final archive requires the actual saved solver proofs')
    for source in sorted((work / 'archive_build/model_construction_check').glob('*.json')):
        archive_file(source, revision / 'provenance/model_construction' / source.name)
    for name in ['collect_runtime_sources.py', 'collect_solver_records.py', 'check_model_construction.py', 'compare_constructed_mps.py']:
        archive_file(work / 'archive_build' / name, revision / 'provenance/collection_source' / name)
    manifest['archive_tools_sha256']['archive_tools/revision_20261017_common.py'] = digest(archive / 'archive_tools/revision_20261017_common.py')
    write_json(revision / 'revision_manifest.json', manifest)
    if verification_report:
        checked = read_json(verification_report)
        if checked.get('passed') is not True or checked.get('verified_actual_runs') != 18 or checked['revision_manifest_sha256'] != digest(revision / 'revision_manifest.json'):
            raise ValueError('The final saved-data verification must bind this exact eighteen-run archive manifest')
        archive_file(verification_report, revision / 'provenance/saved_data_verification.json')
    hashes = {path.relative_to(native(revision)).as_posix(): digest(path) for path in sorted(native(revision).rglob('*'))
              if path.is_file() and path.name != 'SHA256SUMS.json' and '__pycache__' not in path.parts}
    write_json(revision / 'SHA256SUMS.json', hashes)
    if release_zip:
        if not final or state != 'complete':
            raise ValueError('A release ZIP requires --final and eighteen verified actual runs')
        checked = read_json(revision / 'provenance/saved_data_verification.json')
        if checked.get('passed') is not True or checked.get('verified_actual_runs') != 18 or checked['revision_manifest_sha256'] != digest(revision / 'revision_manifest.json'):
            raise ValueError('A release ZIP requires the successful independent saved-data verification of this exact manifest')
        release_zip = Path(release_zip).resolve()
        if release_zip.is_relative_to(archive):
            raise ValueError('The release ZIP must be outside the repository')
        native(release_zip.parent).mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(native(release_zip), 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as output:
            for path in sorted(native(archive).rglob('*')):
                relative = path.relative_to(native(archive))
                if (path.is_file() and relative.parts[0] not in {'.git', 'work', 'validation_records', 'accompanying_data'}
                        and '__pycache__' not in relative.parts and relative.name != '.git'):
                    output.write(path, relative.as_posix())
        write_json(release_zip.with_suffix(release_zip.suffix + '.json'), {'sha256': digest(release_zip), 'bytes': native(release_zip).stat().st_size,
                                                                       'revision_manifest_sha256': digest(revision / 'revision_manifest.json'), 'runs': 18})
        native(release_zip.with_suffix(release_zip.suffix + '.sha256')).write_text(
            digest(release_zip) + '  ' + release_zip.name + '\n', encoding='utf-8')
    return {'state': state, 'archived_runs': len(runs), 'missing_runs': missing,
            'revision_manifest_sha256': digest(revision / 'revision_manifest.json')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--archive-root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--source-bundle', type=Path, required=True)
    parser.add_argument('--source-receipt', type=Path, required=True)
    parser.add_argument('--final', action='store_true')
    parser.add_argument('--release-zip', type=Path)
    parser.add_argument('--solver-bundle', type=Path)
    parser.add_argument('--solver-receipt', type=Path)
    parser.add_argument('--verification-report', type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.work, args.archive_root, args.source_bundle, args.source_receipt, args.final, args.release_zip, args.solver_bundle, args.solver_receipt, args.verification_report), ensure_ascii=False, indent=2))
