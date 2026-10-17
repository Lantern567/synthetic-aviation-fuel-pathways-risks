import hashlib
import importlib.metadata
import json
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
WORK = HERE.parent
ROOT = HERE.parents[3]
OLD = ROOT / 'work/nexus_targeted_revision/revision_20261007/figures_space_time'
COMPUTE = WORK / 'runtime/compute'
PV_SOURCE = HERE / 'reproducibility_source/pv_source_compute'
PV = WORK / 'pv_inputs'
RESOURCE = WORK / 'figures_resource'
sys.path.insert(0, str(HERE / 'dependencies'))
records = {}


def add(path, component, role, expected=None):
    path = Path(path).resolve()
    assert path.is_file(), path
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if expected is not None:
        assert digest == expected, path
    key = str(path)
    if key in records:
        records[key]['consumers'] = sorted(set(records[key]['consumers'] + [component]))
        return
    records[key] = dict(path=key, bytes=path.stat().st_size, sha256=digest,
                        consumers=[component], role=role)


for name in ['build_pv_inputs.py', 'pv_parameters.json', 'source_records.json', 'input_sha256.json',
             'raw_profile_validation.json', 'solar_hdf5_provenance.json', 'solar_hdf5_validation.json',
             'validation.json', 'source_renewable_12weeks.csv', 'renewable_12weeks.csv',
             'solar_corrected_periods.csv', 'solar_phase_capacity.csv']:
    add(PV / name, 'pv', 'Source, parameters, retained raw extract, final input or scientific provenance')
for path in sorted((PV / 'sources').glob('*')):
    add(path, 'pv', 'Retained raw HDF5 coordinate extract or phase inventory')
for label in ['baseline', 'summer']:
    for name in ['renewable_periods.csv', 'airport_input.csv', 'airport_input.xlsx', 'manifest.json']:
        original_path = PV_SOURCE / 'inputs' / label / name
        expected = json.loads((PV / 'inputs' / label / 'manifest.json').read_text())['source_input_sha256'] if name == 'renewable_periods.csv' else None
        add(original_path, 'pv', 'Original selected schedule or demand used by the PV input builder', expected)
        add(PV / 'inputs' / label / name, 'pv', 'Frozen model-ready inputs')
for name in ['solar_grid_mapping.csv', 'solar_hdf5_provenance.json', 'raw_profile_validation.json']:
    add(PV_SOURCE / name, 'pv', 'Original source-compute provenance consumed by the PV builder')
add(PV_SOURCE / 'source_origins.json', 'pv', 'Verified original-input locations and byte hashes before collection')

for name in ['redraw_s9_s10.py', 'update_resource_quality.py', 'verify_figure_outputs.py',
             'figure_manifest.json', 'resource_quality_manifest.json', 'resource_metrics.json',
             'updated_joint_week_ranges.json']:
    add(RESOURCE / name, 'resource', 'Executed source or final data provenance')
for path in sorted((RESOURCE / 'resource_data').iterdir()):
    if path.suffix in ['.csv', '.json']:
        add(path, 'resource', 'Prepared final plot data or representative-week diagnostic')
resource_manifest = json.loads((RESOURCE / 'figure_manifest.json').read_text(encoding='utf-8'))
quality_manifest = json.loads((RESOURCE / 'resource_quality_manifest.json').read_text(encoding='utf-8'))
for record in resource_manifest['wind_relationship_sources']:
    add(record['path'], 'resource', 'Selected genuine wind source; 550-row sample and seed recorded in figure_manifest', record['sha256'])
for record in quality_manifest['inventory_sources'].values():
    add(record['path'], 'resource', 'Unchanged national inventory supplying the background panels', record['sha256'])
add(ROOT / 'work/nexus_targeted_revision/static_supplement/twelve_week_joint_relative_states.csv',
    'resource', 'Original twelve-week airport demand diagnostic')
add(ROOT / 'Nexus系统提交文件_代码归档同步20261015/Supplementary_Information.docx',
    'resource', 'Original S9/S10 embedded-image provenance check')
for number in [9, 10]:
    add(OLD / f'outputs/Figure_S{number}.png', 'resource', 'Original scientific plot used for source-image integrity checks')
for number in [6, 7, 9, 10]:
    for suffix in ['png', 'pdf']:
        add(RESOURCE / f'figures/Figure_S{number}.{suffix}', 'resource', 'Final publication figure')

for name in ['build_inputs.py', 'render_spatial.py', 'check_registration.py', 'verify_outputs.py', 'build_input_contract.py']:
    add(HERE / name, 'spatial', 'Executed data, renderer, calibration or verification source')
for name in ['build_pv_inputs.py', 'redraw_s9_s10.py', 'update_resource_quality.py', 'render_spatial.py', 'redraw_s49.py']:
    add(HERE / 'reproducibility_source' / name, 'portable_entry', 'Explicit path parameters for restored-workspace execution; original executed source retained separately')
if (HERE / 'portability_validation.json').exists():
    add(HERE / 'portability_validation.json', 'portable_entry', 'Real copied-workspace PV/resource/spatial reproduction verification')
for name in ['main_composite_template.png', 'original_S54.png', 'current_archive_registration.json',
             'archive_registration.json', 'provenance.json']:
    add(HERE / 'templates' / name, 'spatial', 'Original map or composite template, registration or template provenance')
for path in sorted((HERE / 'network_data').iterdir()):
    if path.suffix in ['.csv', '.json']:
        add(path, 'spatial', 'Final thirteen-baseline metric, matching, endpoint geometry or joint-plot data')
for path in sorted((HERE / 'figures').iterdir()):
    if path.suffix in ['.png', '.pdf', '.json']:
        add(path, 'spatial', 'Final publication or required composition component with final integrity records')
for name in ['generate_appendix_docx.py', 'pareto_three_breakdown_visualization.py', 'network_classification_metrics_builder.py']:
    add(OLD / 'source' / name, 'spatial', 'Actual inherited scientific plotting or network-metric implementation')
    add(OLD / 'source' / name, 'resource', 'Actual inherited scientific plotting implementation')
visualization = COMPUTE / 'project/products/supply_chain_optimization/visualization'
for name in ['network_structure_and_siting_visualization.py', 'thirteen_scenarios_clustered_map_visualization.py']:
    add(visualization / name, 'spatial', 'Actual original panel styles and original SVG marker definitions')
add(COMPUTE / 'project/products/supply_chain_optimization/coal_hydrogen_saf_optimization/src/routing/graphhopper_routing_engine.py',
    'spatial', 'Import dependency of the original symbol module; rendering uses recorded endpoint geometry')
for path in [HERE / 'dependencies/svgpath2mpl.py', *(HERE / 'dependencies/svgpath2mpl-1.0.0.dist-info').glob('*')]:
    if path.is_file() and path.name not in ['RECORD', 'INSTALLER', 'REQUESTED']:
        add(path, 'spatial', 'SVG parser source or distribution metadata/license')
temporal = WORK / 'figures_temporal'
add(temporal / 'temporal_data/all_pathway_temporal_metrics.csv', 'spatial', 'Final thirteen-baseline independent temporal metrics')
add(temporal / 'inputs/manifest.json', 'spatial', 'Final temporal-source and carbon-input hash binding')
manifest = json.loads((temporal / 'inputs/manifest.json').read_text(encoding='utf-8'))
assert manifest['full_thirteen_baselines'] and len(manifest['configurations']) == 13
for name, record in manifest['configurations'].items():
    add(temporal / f'inputs/{name}_carbon.json', 'spatial', 'Final direct supply-chain CI input', record['adapted_files']['carbon']['sha256'])
    for source, expected in record['source_hashes'].items():
        if Path(source).name in ['accounts.json', 'normalized_carbon_emissions.json']:
            add(source, 'spatial', 'Final accounting provenance checked before S26 rendering', expected)

packages = ['numpy', 'pandas', 'scipy', 'matplotlib', 'PyMuPDF', 'Pillow', 'python-docx', 'openpyxl',
            'frykit', 'frykit_data', 'Cartopy', 'pyproj', 'shapely', 'requests', 'svgpath2mpl']
contract = dict(schema_version=1, scope='Final PV generation inputs and prepared resource/spatial figure inputs',
    final_accounting_assumption='CCU/DAC FT and MTJ use the shared configured route-level 7.6 kWh/kg final fuel input',
    excludes=['QA/contact previews', 'Superseded plot outputs', '__pycache__', 'matplotlib font caches', 'Installed environment trees'],
    input_levels={
        'pv_rebuild': 'build_pv_inputs.py consumes the original source-compute selected inputs, phase mapping, retained HDF5 coordinate extract and original twelve-week resource table; final frozen inputs are separately retained.',
        'resource_replot': 'The reproducibility_source entries accept explicit workspace, external-project, PV, legacy-template and output paths. The original executed sources and their hashes are separately retained. The selected genuine wind files retain their original names and lexicographic sampling order.',
        'spatial_replot': 'The final network_data, templates and final temporal/CI records are the complete prepared rendering inputs. Mass-flow metric CSVs retain genuine model distances; route geometry is explicitly endpoint-only.',
        'upstream_network_rebuild': 'Original verified model exports, final accounts and authentic routing cache are retained by the main execution archive; build_inputs.py records that upstream interface.'},
    runtime=dict(python=sys.version, packages={name: importlib.metadata.version(name) for name in packages},
                 component_overrides={'resource_figures': {'matplotlib': '3.10.7'}},
                 fonts=['Times New Roman', 'Arial'], cartographic_data='frykit_data package 0.0.1 for resource maps; spatial maps retain the original raster basemap'),
    portable_entries={
        'pv': 'reproducibility_source/build_pv_inputs.py --source-compute OLD_COMPUTE --raw-solar RAW_EXTRACT --source-twelve-weeks OLD_12W --parameters PV_PARAMETERS --output NEW_PV',
        'resource_s9_s10': 'reproducibility_source/redraw_s9_s10.py --workspace-root WORKSPACE --pv-inputs PV --legacy-figures LEGACY --external-project EXTERNAL_PROJECT --output-root OUTPUT',
        'resource_s6_s7': 'reproducibility_source/update_resource_quality.py --workspace-root WORKSPACE --pv-inputs PV --legacy-figures LEGACY --external-project EXTERNAL_PROJECT --output-root OUTPUT',
        'spatial': 'reproducibility_source/render_spatial.py --workspace-root WORKSPACE --legacy-figures LEGACY --external-project MODEL_PROJECT --accounting-root ACCOUNTS --data NETWORK_DATA --templates TEMPLATES --output OUTPUT --temporal-data TEMPORAL_DATA --temporal-inputs TEMPORAL_INPUTS; reproduce the final standalone S26 invocation in a fresh process by adding --joint-only after the full render'},
    files=sorted(records.values(), key=lambda record: record['path']))
destination = HERE / 'final_input_contract.json'
destination.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(dict(files=len(records), bytes=sum(record['bytes'] for record in records.values()),
                     contract=str(destination), sha256=hashlib.sha256(destination.read_bytes()).hexdigest())))
