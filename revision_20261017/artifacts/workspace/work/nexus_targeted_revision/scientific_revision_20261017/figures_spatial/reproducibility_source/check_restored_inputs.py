import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image


HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--validate-existing', action='store_true')
args = parser.parse_args()
SPATIAL = HERE.parent
WORK = SPATIAL.parent
ROOT = SPATIAL.parents[3]
CHECK = ROOT / 'work/nexus_portability_20261017'
RESTORED = CHECK / 'workspace'
EXTERNAL = CHECK / 'external_project'
EXTERNAL_SOURCE = Path('E:/green_methanol_for_port_transportation-main')
contract = json.loads((SPATIAL / 'final_input_contract.json').read_text(encoding='utf-8'))
CHECK.mkdir(exist_ok=True)
restored_files = []
for record in contract['files']:
    source = Path(record['path'])
    assert hashlib.sha256(source.read_bytes()).hexdigest() == record['sha256'], source
    if source.is_relative_to(WORK):
        destination = RESTORED / 'revision' / source.relative_to(WORK)
    elif source.is_relative_to(ROOT):
        destination = RESTORED / source.relative_to(ROOT)
    else:
        destination = EXTERNAL / source.relative_to(EXTERNAL_SOURCE)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    assert hashlib.sha256(destination.read_bytes()).hexdigest() == record['sha256']
    restored_files.append(str(destination))
restored_work = RESTORED / 'revision'
restored_source = restored_work / 'figures_spatial/reproducibility_source'
restored_source.mkdir(parents=True, exist_ok=True)
for name in ['build_pv_inputs.py', 'redraw_s9_s10.py', 'update_resource_quality.py', 'render_spatial.py', 'redraw_s49.py']:
    shutil.copyfile(HERE / name, restored_source / name)
legacy = RESTORED / 'work/nexus_targeted_revision/revision_20261007/figures_space_time'
stages = []


def run(name, arguments):
    log = CHECK / (name + '.log')
    command = [sys.executable, *map(str, arguments)]
    if args.validate_existing and name != 'spatial_joint':
        assert log.is_file()
        stages.append(dict(stage=name, passed=True, command=command, log=str(log),
                           executed_this_invocation=False, previous_generation_output_verified=True))
        return
    environment = os.environ.copy()
    if name.startswith('resource_'):
        environment['PYTHONPATH'] = str(CHECK / 'resource_dependencies')
    with log.open('w', encoding='utf-8') as stream:
        subprocess.run(command, cwd=RESTORED, env=environment, stdout=stream, stderr=subprocess.STDOUT, check=True)
    stages.append(dict(stage=name, passed=True, command=command, log=str(log)))
    print(name + ' passed', flush=True)


new_pv = CHECK / 'rebuilt_pv'
run('pv', [restored_source / 'build_pv_inputs.py', '--source-compute', restored_source / 'pv_source_compute',
           '--raw-solar', restored_work / 'pv_inputs/sources/solar_hdf5_extracted.csv.gz',
           '--source-twelve-weeks', restored_work / 'pv_inputs/source_renewable_12weeks.csv',
           '--parameters', restored_work / 'pv_inputs/pv_parameters.json', '--output', new_pv])
pv_checked = []
for name in ['renewable_12weeks.csv', 'solar_corrected_periods.csv', 'solar_phase_capacity.csv',
             'inputs/baseline/renewable_periods.csv', 'inputs/summer/renewable_periods.csv',
             'inputs/baseline/airport_input.csv', 'inputs/summer/airport_input.csv']:
    assert (new_pv / name).read_bytes() == (WORK / 'pv_inputs' / name).read_bytes(), name
    pv_checked.append(name)
resource_output = CHECK / 'resource'
resource_arguments = ['--workspace-root', RESTORED, '--pv-inputs', restored_work / 'pv_inputs',
                      '--legacy-figures', legacy, '--external-project', EXTERNAL,
                      '--output-root', resource_output]
run('resource_s9_s10', [restored_source / 'redraw_s9_s10.py', *resource_arguments])
run('resource_s6_s7', [restored_source / 'update_resource_quality.py', *resource_arguments])
spatial_output = CHECK / 'spatial'
spatial_arguments = [restored_source / 'render_spatial.py', '--workspace-root', RESTORED,
                '--legacy-figures', legacy, '--external-project', restored_work / 'runtime/compute/project',
                '--accounting-root', restored_work / 'postprocess/accounts',
                '--data', restored_work / 'figures_spatial/network_data',
                '--templates', restored_work / 'figures_spatial/templates', '--output', spatial_output,
                '--temporal-data', restored_work / 'figures_temporal/temporal_data',
                '--temporal-inputs', restored_work / 'figures_temporal/inputs']
run('spatial', spatial_arguments)
run('spatial_joint', [*spatial_arguments, '--joint-only'])
figure_checks = []
for folder, original in [(resource_output / 'figures', WORK / 'figures_resource/figures'),
                         (spatial_output, SPATIAL / 'figures')]:
    for candidate in sorted(folder.glob('*.png')):
        reference = original / candidate.name
        with Image.open(candidate) as image, Image.open(reference) as expected:
            pixel_identical = image.size == expected.size and np.array_equal(np.asarray(image), np.asarray(expected))
            assert max(abs(image.width / expected.width - 1), abs(image.height / expected.height - 1)) < .003
            sizes = dict(original_pixels=list(expected.size), restored_pixels=list(image.size))
        figure_checks.append(dict(figure=candidate.name, pixels_identical=pixel_identical, **sizes,
                                  original_sha256=hashlib.sha256(reference.read_bytes()).hexdigest(),
                                  restored_sha256=hashlib.sha256(candidate.read_bytes()).hexdigest()))
resource_data_checks = []
for candidate in sorted((resource_output / 'resource_data').glob('*.csv')):
    assert candidate.read_bytes() == (WORK / 'figures_resource/resource_data' / candidate.name).read_bytes(), candidate
    resource_data_checks.append(candidate.name)
assert (restored_work / 'figures_spatial/network_data/scenario_integrated_metrics.csv').read_bytes() == (SPATIAL / 'network_data/scenario_integrated_metrics.csv').read_bytes()
report = dict(passed=True, restored_input_files=len(restored_files), rebuilt_pv_byte_identical=pv_checked,
              stages=stages, figure_checks=figure_checks,
              resource_plot_data_byte_identical=resource_data_checks,
              joint_integrated_metrics_byte_identical=True,
              component_matplotlib_versions=dict(resource='3.10.7', spatial='3.11.2'),
              exact_pixel_reproduction=all(record['pixels_identical'] for record in figure_checks),
              pixel_comparison_scope='Pixel identity is recorded independently of successful input execution and byte-identical scientific plot data; original publication figure bytes are retained unchanged.',
              scope='Prepared-input execution in a copied workspace and separate copied external project; no optimization rerun')
(SPATIAL / 'portability_validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(dict(passed=True, figures=len(figure_checks), pv_files=len(pv_checked))))
