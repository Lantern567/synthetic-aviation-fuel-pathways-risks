import argparse
import json
from pathlib import Path
import subprocess
import sys

from revision_20261017_common import copy_checked, digest, expand_subtree, native, read_json, require_complete, revision_paths, write_json


def prepare(archive, workspace, render, supporting_artifacts=False, render_supporting=False, resource_python=None):
    _, revision, manifest = revision_paths(archive)
    require_complete(manifest)
    workspace = Path(workspace).resolve()
    if native(workspace).exists() or workspace.is_relative_to(revision):
        raise ValueError('Choose a new figure workspace outside revision_20261017')
    native(workspace).mkdir(parents=True)
    for record in manifest['runs']:
        scenario, label = record['scenario'], record['label']
        run, account = workspace / 'results' / scenario / label, workspace / 'postprocess/accounts' / scenario / label
        expand_subtree(revision, run, manifest['packed_files'], 'saved_results/' + scenario + '/' + label)
        expand_subtree(revision, account, manifest['packed_files'], 'final_accounts/' + scenario + '/' + label)
        if digest(run / 'summary.json') != record['summary_sha256']:
            raise ValueError('The figure source summary differs from its actual saved record')
    source = revision / 'postprocess_source/figures_cost'
    scripts = workspace / 'figures_cost'
    for path in native(source).iterdir():
        if path.is_file():
            copy_checked(path, scripts / path.name)
    source_manifest = revision / 'postprocess_source/figures_cost/archive_sources.json'
    data, figures = scripts / 'adapted_data', scripts / 'figures'
    commands = [[sys.executable, '-X', 'utf8', str(native(scripts / 'build_inputs.py')), '--results', str(native(workspace / 'results')),
                 '--accounts', str(native(workspace / 'postprocess/accounts')), '--out', str(native(data)), '--source-manifest', str(native(source_manifest))],
                [sys.executable, '-X', 'utf8', str(native(scripts / 'render_figures.py')), '--data', str(native(data)),
                 '--out', str(native(figures)), '--source-manifest', str(native(source_manifest))]]
    if render:
        for index, command in enumerate(commands):
            with native(workspace / f'figure_stage_{index + 1}.log').open('w', encoding='utf-8') as output:
                subprocess.run(command, stdout=output, stderr=subprocess.STDOUT, check=True)
    report = {'prepared': True, 'new_runs': 18, 'preserved_GTL': True, 'optimization_executed': False,
              'rendering_executed': render, 'commands': commands,
              'revision_manifest_sha256': digest(revision / 'revision_manifest.json'),
              'source_manifest_sha256': digest(source_manifest),
              'note': 'The renderer rebuilds all data from exact saved results and accounts. Times New Roman and the recorded figure dependencies are required for matching typography.'}
    if supporting_artifacts:
        source_manifest_path = revision / 'artifacts/source_manifest.json'
        if digest(source_manifest_path) != manifest['artifact_source_manifest_sha256']:
            raise ValueError('The supporting figure and PV-input source manifest changed')
        supporting = read_json(source_manifest_path)
        roots = {name: workspace / 'supporting_artifacts' / name for name in supporting['original_roots']}
        for name, target in roots.items():
            expand_subtree(revision, target, manifest['packed_files'], 'artifacts/' + name)
        for item in supporting['files']:
            target = roots[item['restore_root']] / item['relative_path']
            if digest(target) != item['source_sha256']:
                raise ValueError(f'A restored supporting scientific source differs: {target}')
        project = roots['workspace']
        scientific = project / 'work/nexus_targeted_revision/scientific_revision_20261017'
        temporal = scientific / 'figures_temporal'
        old_gtl = project / 'work/nexus_targeted_revision/github_archive/repository/archived_outputs/products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/ft_one_step'
        old_adapted = project / 'work/nexus_targeted_revision/revision_20261007/figures_cost/adapted_data'
        commands = [[sys.executable, '-X', 'utf8', str(temporal / 'build_inputs.py'),
                     '--results', str(workspace / 'results'), '--accounts-root', str(workspace / 'postprocess/accounts'),
                     '--out', str(temporal / 'rebuilt_inputs'), '--renewable-input', str(scientific / 'pv_inputs/inputs/baseline/renewable_periods.csv'),
                     '--gtl-source-dir', str(old_gtl), '--gtl-adapted-dir', str(old_adapted)],
                    [sys.executable, '-X', 'utf8', str(temporal / 'render_temporal.py'), '--inputs', str(temporal / 'rebuilt_inputs'),
                     '--out', str(temporal / 'rebuilt_figures')],
                    [sys.executable, '-X', 'utf8', str(temporal / 'export_aliases.py'), '--out', str(temporal / 'rebuilt_figures')]]
        portable = scientific / 'figures_spatial/reproducibility_source'
        legacy = project / 'work/nexus_targeted_revision/revision_20261007/figures_space_time'
        rebuilt = workspace / 'supporting_rebuilt'
        supporting_commands = [[sys.executable, '-X', 'utf8', str(portable / 'build_pv_inputs.py'),
                                '--source-compute', str(portable / 'pv_source_compute'),
                                '--raw-solar', str(scientific / 'pv_inputs/sources/solar_hdf5_extracted.csv.gz'),
                                '--source-twelve-weeks', str(scientific / 'pv_inputs/source_renewable_12weeks.csv'),
                                '--parameters', str(scientific / 'pv_inputs/pv_parameters.json'), '--output', str(rebuilt / 'pv_inputs')]]
        resource_arguments = ['--workspace-root', str(project), '--pv-inputs', str(scientific / 'pv_inputs'),
                              '--legacy-figures', str(legacy), '--external-project', str(roots['external_project']),
                              '--output-root', str(rebuilt / 'resource')]
        for name in ['redraw_s9_s10.py', 'update_resource_quality.py']:
            supporting_commands.append([str(resource_python.resolve()) if resource_python else sys.executable,
                                        '-X', 'utf8', str(portable / name), *resource_arguments])
        supporting_commands.append([sys.executable, '-X', 'utf8', str(portable / 'render_spatial.py'),
                                    '--workspace-root', str(project), '--legacy-figures', str(legacy),
                                    '--external-project', str(scientific / 'runtime/compute/project'),
                                    '--accounting-root', str(workspace / 'postprocess/accounts'),
                                    '--data', str(scientific / 'figures_spatial/network_data'),
                                    '--templates', str(scientific / 'figures_spatial/templates'),
                                    '--output', str(rebuilt / 'spatial'),
                                    '--temporal-data', str(temporal / 'temporal_data'),
                                    '--temporal-inputs', str(temporal / 'inputs')])
        supporting_commands.append([*supporting_commands[-1], '--joint-only'])
        supporting_commands.extend(commands)
        if render_supporting:
            for index, command in enumerate(supporting_commands):
                with native(workspace / f'supporting_stage_{index + 1}.log').open('w', encoding='utf-8') as output:
                    subprocess.run(command, stdout=output, stderr=subprocess.STDOUT, check=True)
        report['supporting_artifacts'] = {'restored_files': len(supporting['files']),
                                          'manifest_sha256': manifest['artifact_source_manifest_sha256'],
                                          'original_to_prepared_roots': {supporting['original_roots'][name]: str(path) for name, path in roots.items()},
                                          'rebuild_commands': supporting_commands,
                                          'rendering_executed': render_supporting,
                                          'scientific_workspace': str(scientific), 'external_project': str(roots['external_project'])}
    write_json(workspace / 'figure_preparation_manifest.json', report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive-root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--render', action='store_true')
    parser.add_argument('--supporting-artifacts', action='store_true')
    parser.add_argument('--render-supporting', action='store_true')
    parser.add_argument('--resource-python', type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args.archive_root, args.workspace, args.render,
                             args.supporting_artifacts or args.render_supporting, args.render_supporting,
                             args.resource_python), ensure_ascii=False, indent=2))
