import argparse
import ast
import json
from pathlib import Path
import shutil
import sys

from revision_20261017_common import CASES, copy_checked, digest, expand_subtree, native, read_json, revision_paths, verify_input_files, write_json


def execution_setting(source, scenario):
    tree = ast.parse(native(source).read_text(encoding='utf-8'))
    candidates = [node.value for node in tree.body if isinstance(node, ast.Assign)
                  and any(isinstance(target, ast.Name) and target.id == 'settings' for target in node.targets)]
    if len(candidates) != 1:
        raise ValueError('The archived execution settings must be one literal dictionary')
    return ast.literal_eval(candidates[0])[scenario]


def prepare(archive_root, workspace, scenario, label):
    archive, revision, manifest = revision_paths(archive_root)
    workspace = Path(workspace).resolve()
    if native(workspace).exists() or workspace.is_relative_to(revision):
        raise ValueError('Choose a new working directory outside revision_20261017')
    matches = [record for record in manifest['runs'] if (record['scenario'], record['label']) == (scenario, label)]
    if len(matches) != 1:
        raise ValueError(f'The completed actual run is not archived: {scenario}/{label}')
    record = matches[0]
    sources = revision / manifest['runtime_sources_directory']
    source_manifest = read_json(sources / 'runtime_sources_manifest.json')
    if digest(sources / 'runtime_sources_manifest.json') != manifest['runtime_sources_manifest_sha256']:
        raise ValueError('Runtime source manifest changed')
    runtime = workspace / 'runtime'
    native(runtime).mkdir(parents=True)
    expand_subtree(sources, runtime / 'project', source_manifest['files'], 'shared_project')
    expand_subtree(sources, runtime, source_manifest['files'], 'runtimes/' + record['runtime'])
    verify_input_files(runtime, record['input_files_sha256'])
    snapshot = revision / record['source_snapshot']
    if digest(snapshot / 'summary.json') != record['summary_sha256']:
        raise ValueError('Original saved summary changed')
    family, model_name, _, configuration, _ = execution_setting(snapshot / 'source/run_model.py', scenario)
    restored_sources = []

    def restore(source, target):
        previous = digest(target) if native(target).is_file() else None
        native(target.parent).mkdir(parents=True, exist_ok=True)
        shutil.copyfile(native(source), native(target))
        if digest(source) != digest(target):
            raise ValueError(f'The prepared source differs from its actual run snapshot: {source}')
        restored_sources.append({'path': target.relative_to(runtime).as_posix(),
                                 'sha256': digest(source), 'shared_snapshot_sha256': previous})

    core_files = []
    for source in native(snapshot / 'source').glob('*.py'):
        if source.name.endswith('_optimization_model.py'):
            target = runtime / 'project/products/supply_chain_optimization' / family / 'src/core' / source.name
            core_files.append(source.name)
        else:
            target = runtime / source.name
        restore(source, target)
    if core_files != [model_name + '.py']:
        raise ValueError('Exactly one actual core-model source snapshot is required')
    restore(snapshot / 'config.yaml', runtime / 'project' / configuration)
    copy_checked(snapshot / 'config.yaml', runtime / 'archived_execution_config.yaml')
    prepared_run = runtime / 'verified_runs' / scenario / label
    expand_subtree(revision, prepared_run, manifest['packed_files'], 'saved_results/' + scenario + '/' + label)
    if digest(prepared_run / 'summary.json') != record['summary_sha256']:
        raise ValueError('Prepared solver summary differs from the original saved summary')
    if label == 'summer_fixed':
        baseline = [item for item in manifest['runs'] if (item['scenario'], item['label']) == (scenario, 'baseline')]
        if len(baseline) != 1:
            raise ValueError('The actual baseline production assets are required for a fixed-design alternate-week model')
        expand_subtree(revision, runtime / 'verified_runs' / scenario / 'baseline', manifest['packed_files'], 'saved_results/' + scenario + '/baseline')
    report = {'scenario': scenario, 'label': label, 'runtime': record['runtime'],
              'source_summary_sha256': record['summary_sha256'], 'original_summary_preserved': True,
              'runtime_sources_manifest_sha256': manifest['runtime_sources_manifest_sha256'],
              'restored_exact_execution_sources': restored_sources,
              'optimization_executed': False, 'license_files_distributed': False,
              'model_build_command': [sys.executable, str(runtime / 'run_model.py'), scenario, label, '--export-model'],
              'new_optimization_command': [sys.executable, str(runtime / 'run_model.py'), scenario, label],
              'note': 'Model construction and a new solve require COPT 8.0.7 and a user-supplied license. The commands use the archived actual runtime and cached road routes.'}
    write_json(workspace / 'preparation_manifest.json', report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive-root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--scenario', required=True)
    parser.add_argument('--label', choices=['baseline', 'summer_fixed'], required=True)
    args = parser.parse_args()
    if (args.scenario, args.label) not in CASES:
        raise ValueError('Unknown revision scenario/label')
    print(json.dumps(prepare(args.archive_root, args.workspace, args.scenario, args.label), ensure_ascii=False, indent=2))
