import argparse
import hashlib
import importlib.util
import json
import logging
import os
import shutil
import sys
import textwrap
from pathlib import Path, PureWindowsPath

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[3]
OLD = ROOT / 'work/nexus_targeted_revision/revision_20261007/figures_space_time'
os.environ['MPLCONFIGDIR'] = str(HERE / 'mplconfig')
sys.path.insert(0, str(HERE / 'dependencies'))
sys.path.insert(0, str(HERE))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.text import Text
import numpy as np
import pandas as pd
import pymupdf
from PIL import Image
import frykit.plot as fplt
from svgpath2mpl import parse_path

from build_inputs import GROUPS, METRIC_NAMES, SCENARIOS


REPRESENTATIVES = ['CCU-GH-FT', 'GTL', 'GTL-BH', 'DAC-BH-FT']
FIGURE_NUMBERS = dict(zip(SCENARIOS, range(51, 64)))
LINE_COLORS = {'H2': '#0072B2', 'CO2': '#663300', 'SAF': '#D55E00', 'NG': '#009E73'}


def configure_sources(workspace_root, legacy_figures, external_project):
    global ROOT, OLD, panels, symbols
    ROOT = workspace_root.resolve()
    OLD = (legacy_figures or ROOT / 'work/nexus_targeted_revision/revision_20261007/figures_space_time').resolve()
    project = external_project or ROOT / 'work/nexus_targeted_revision/scientific_revision_20261017/runtime/compute/project'
    visualization = project.resolve() / 'products/supply_chain_optimization/visualization'
    sys.path.insert(0, str(OLD / 'source'))
    sys.path.insert(0, str(visualization))
    panels = importlib.import_module('network_structure_and_siting_visualization')
    symbols = importlib.import_module('thirteen_scenarios_clustered_map_visualization')
    assert symbols.SVG_PARSER_AVAILABLE and panels.SVG_PARSER_AVAILABLE


def checksum(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def publication_terms(figure):
    for label in figure.findobj(Text):
        label.set_text(label.get_text().replace('SAF', 'SynAF'))


def shared_legends(output):
    supplement_legend(output)
    visualizer = symbols.ThirteenScenariosClusteredMapVisualizer.__new__(symbols.ThirteenScenariosClusteredMapVisualizer)
    entries = [
        (frozenset(), False, True, 'Airport'),
        (frozenset(), True, True, 'Airport (SynAF Production Facility)'),
        (frozenset({'co2'}), False, False, 'Carbon Dioxide Capture'),
        (frozenset({'natural_gas'}), False, False, 'Natural Gas Supply'),
        (frozenset({'co2', 'h2'}), False, False, 'Carbon Dioxide Capture+Hydrogen Production'),
        (frozenset({'co2', 'h2'}), True, False, 'Carbon Dioxide Capture+Hydrogen Production+SynAF Production Facility'),
        (frozenset({'co2'}), True, False, 'Carbon Dioxide Capture+SynAF Production Facility'),
        (frozenset({'h2'}), False, False, 'Hydrogen Production'),
        (frozenset({'h2'}), True, False, 'Hydrogen Production+SynAF Production Facility'),
        (frozenset(), True, False, 'SynAF Production Facility'),
    ]
    for variant, width, height, title_size, item_size in [('main', 4360, 428, 18, 13)]:
        factor = width / 4360
        figure = plt.figure(figsize=(width / 200, height / 200), dpi=200)
        axis = figure.add_axes([0, 0, 1, 1])
        axis.set(xlim=(0, width), ylim=(height, 0))
        axis.axis('off')
        title_y = 45 if variant == 'main' else 35
        rows = [150, 225, 300, 375] if variant == 'main' else [145, 230, 315]
        for x, label in [(460, 'Transport Routes'), (2360, 'Facility Classification'), (4140, 'Pipeline Network')]:
            axis.text(x * factor, title_y, label, fontfamily='Times New Roman', fontsize=title_size,
                      fontweight='bold', ha='center', va='center')
        route_rows = [('H2', 'Hydrogen Transport Route'), ('CO2', 'Carbon Dioxide Transport Route'),
                      ('SAF', 'SynAF Truck Transport Route')]
        if variant == 'main':
            route_rows.append(('NG', 'Natural Gas Transport Route'))
        for y, (kind, label) in zip(rows, route_rows):
            axis.plot(np.array([85, 175]) * factor, [y, y], color=LINE_COLORS[kind], linewidth=1)
            axis.text(205 * factor, y, label, fontsize=item_size, fontfamily='Times New Roman', va='center')
        locations = [(860, 935, rows[0]), (860, 935, rows[1]), (860, 935, rows[2])]
        if variant == 'main':
            locations.append((860, 935, rows[3]))
        else:
            locations.append(None)
        locations += [(1605, 1680, y) for y in rows[:3]] + [(3015, 3090, y) for y in rows[:3]]
        for (raw, synthesis, airport, label), location in zip(entries, locations):
            if location is None:
                continue
            marker_x, text_x, y = location
            attributes = visualizer.get_facility_visualization_attrs(raw, 'yes' if synthesis else 'no', 'yes' if airport else 'no')
            values = dict(attributes[0])
            if len(raw) > 1:
                values.update(marker='P' if synthesis else 'X', edgecolor='#000000')
            axis.scatter([marker_x * factor], [y], marker=values['marker'], s=600 if airport else 320,
                         c=values['color'], edgecolors=values['edgecolor'], linewidths=.8, zorder=5)
            axis.text(text_x * factor, y, label, fontsize=item_size, fontfamily='Times New Roman', va='center')
        for y, label, color in zip(rows[:3], ['Crude Oil', 'Product Oil', 'Natural Gas'], ['#8c510a', '#d8b365', '#5ab4ac']):
            axis.plot(np.array([3970, 4060]) * factor, [y, y], color=color, linewidth=1)
            axis.text(4095 * factor, y, label, fontsize=item_size, fontfamily='Times New Roman', va='center')
        stem = 'main_shared_legend' if variant == 'main' else 'Figure_S49'
        figure.savefig(output / (stem + '.png'), dpi=200, facecolor='white')
        figure.savefig(output / (stem + '.pdf'), facecolor='white')
        plt.close(figure)


def supplement_legend(output):
    visualizer = symbols.ThirteenScenariosClusteredMapVisualizer.__new__(symbols.ThirteenScenariosClusteredMapVisualizer)
    figure = plt.figure(figsize=(7.2, 3.1), dpi=300)
    axis = figure.add_axes([0, 0, 1, 1])
    axis.set(xlim=(0, 518.4), ylim=(223.2, 0))
    axis.axis('off')
    style = dict(fontfamily='Times New Roman', fontsize=10, va='center')
    axis.text(9, 13, 'Transport Routes', fontweight='bold', **style)
    axis.text(275, 13, 'Pipeline Network', fontweight='bold', **style)
    for y, (kind, label) in zip([30, 45, 60], [('H2', 'Hydrogen'), ('CO2', 'Carbon dioxide'), ('SAF', 'SynAF truck')]):
        axis.plot([9, 30], [y, y], color=LINE_COLORS[kind], linewidth=1.1)
        axis.text(37, y, label, **style)
    for y, label, color in zip([30, 45, 60], ['Crude oil', 'Product oil', 'Natural gas'], ['#8c510a', '#d8b365', '#5ab4ac']):
        axis.plot([275, 296], [y, y], color=color, linewidth=1.1)
        axis.text(303, y, label, **style)
    axis.text(9, 82, 'Facility Classification', fontweight='bold', **style)
    entries = [
        (frozenset(), False, True, 'Airport'),
        (frozenset(), True, True, 'Airport + SynAF production'),
        (frozenset({'co2'}), False, False, 'CO2 capture'),
        (frozenset({'co2', 'h2'}), False, False, 'CO2 capture + H2 production'),
        (frozenset({'co2', 'h2'}), True, False, 'CO2 capture + H2 production + SynAF production'),
        (frozenset({'co2'}), True, False, 'CO2 capture + SynAF production'),
        (frozenset({'h2'}), False, False, 'H2 production'),
        (frozenset({'h2'}), True, False, 'H2 production + SynAF production'),
        (frozenset(), True, False, 'SynAF production'),
    ]
    for index, (raw, synthesis, airport, label) in enumerate(entries):
        x, y = 15 + index % 3 * 173, 112 + index // 3 * 44
        attributes = visualizer.get_facility_visualization_attrs(raw, 'yes' if synthesis else 'no', 'yes' if airport else 'no')
        values = dict(attributes[0])
        if len(raw) > 1:
            values.update(marker='P' if synthesis else 'X', edgecolor='#000000')
        axis.scatter([x], [y], marker=values['marker'], s=155 if airport else 105,
                     c=values['color'], edgecolors=values['edgecolor'], linewidths=.7, zorder=5)
        axis.text(x + 13, y, textwrap.fill(label, width=25), linespacing=1.05, **style)
    for suffix in ['png', 'pdf']:
        figure.savefig(output / ('Figure_S49.' + suffix), dpi=300, facecolor='white')
    plt.close(figure)


def load_appendix_template(name):
    sys.path.insert(0, str(OLD / 'source'))
    dependency = importlib.util.spec_from_file_location('pareto_three_breakdown_visualization',
        OLD / 'source/pareto_three_breakdown_visualization.py')
    module = importlib.util.module_from_spec(dependency)
    sys.modules[dependency.name] = module
    dependency.loader.exec_module(module)
    spec = importlib.util.spec_from_file_location(name, OLD / 'source/generate_appendix_docx.py')
    draw = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = draw
    spec.loader.exec_module(draw)
    return draw


def image_pdf(png, pdf, dpi=300):
    with Image.open(png) as image:
        width, height = image.size
    document = pymupdf.open()
    page = document.new_page(width=width * 72 / dpi, height=height * 72 / dpi)
    page.insert_image(page.rect, filename=str(png))
    document.save(pdf, garbage=4, deflate=True)
    document.close()


def plot_maps(data, output, templates, names):
    visualizer = symbols.ThirteenScenariosClusteredMapVisualizer.__new__(symbols.ThirteenScenariosClusteredMapVisualizer)
    checks = []
    for variant in ['main', 'supplement']:
        registration = json.loads((templates / 'current_archive_registration.json').read_text())
        if variant == 'main':
            # 四个主图面板共用原附图的区域范围，包含所有真实西部工业节点。
            original = Image.open(templates / 'original_S54.png').convert('RGB')
            factor = 1020 / original.width
            resized = original.resize((1020, round(original.height * factor)), Image.Resampling.LANCZOS)
            top = (840 - resized.height) // 2 + 16
            background = Image.new('RGB', (1020, 840), 'white')
            background.paste(resized, (0, top))
            registration['scale_x'] *= factor
            registration['scale_y'] *= factor
            registration['offset_x'] *= factor
            registration['offset_y'] = registration['offset_y'] * factor + top
            frame = [registration['frame'][0] * factor, registration['frame'][1] * factor + top,
                     registration['frame'][2] * factor, registration['frame'][3] * factor + top]
            selected = [name for name in REPRESENTATIVES if name in names]
            dpi, marker_scale, line_width = 200, .08, .55
        else:
            background = Image.open(templates / 'original_S54.png').convert('RGB')
            frame = registration['frame']
            selected = names
            dpi, marker_scale, line_width = 300, .16, .65
        width, height = background.size

        def xy(coordinates):
            coordinates = np.asarray(coordinates, dtype=float)
            projected = fplt.CN_AZIMUTHAL_EQUIDISTANT.transform_points(fplt.PLATE_CARREE, coordinates[:, 0], coordinates[:, 1])
            return np.column_stack([projected[:, 0] * registration['scale_x'] + registration['offset_x'],
                                    projected[:, 1] * registration['scale_y'] + registration['offset_y']])

        for name in selected:
            nodes = json.loads((data / f'{name}_nodes.json').read_text(encoding='utf-8'))
            routes = json.loads((data / f'{name}_routes.json').read_text(encoding='utf-8'))
            positions = xy([[node['longitude'], node['latitude']] for node in nodes])
            inside = ((positions[:, 0] >= frame[0]) & (positions[:, 0] <= frame[2]) &
                      (positions[:, 1] >= frame[1]) & (positions[:, 1] <= frame[3]))
            assert inside.all(), (name, variant, 'Selected physical sites outside the retained map frame',
                                  [node for node, valid in zip(nodes, inside) if not valid])
            if variant == 'supplement' and name == 'GTL':
                png = output / 'Figure_S54.png'
                shutil.copy2(templates / 'original_S54.png', png)
                image_pdf(png, output / 'Figure_S54.pdf', dpi)
                checks.append({'scenario': name, 'variant': variant, 'nodes': len(nodes), 'routes': len(routes),
                               'retained_original_gtl_map': True, 'all_selected_sites_inside_frame': True})
                print('Figure_S54', flush=True)
                continue
            pixels = np.asarray(background).copy()
            fig = plt.figure(figsize=(width / dpi, height / dpi), dpi=dpi)
            axis = fig.add_axes([0, 0, 1, 1])
            axis.imshow(pixels, origin='upper', interpolation='none')
            axis.set_xlim(0, width)
            axis.set_ylim(height, 0)
            axis.axis('off')
            clip = patches.Rectangle((frame[0], frame[1]), frame[2] - frame[0], frame[3] - frame[1], transform=axis.transData)
            for route in routes:
                assert route['geometry_basis'] == 'endpoint_schematic'
                if route['source'] == route['destination']:
                    continue
                coordinates = xy(route['coordinates'])
                artist, = axis.plot(coordinates[:, 0], coordinates[:, 1], color=LINE_COLORS[route['cargo']], linewidth=line_width, alpha=.8, zorder=4)
                artist.set_clip_path(clip)
            for node, position in zip(nodes, positions):
                raw = frozenset({'H2': 'h2', 'CO2': 'co2', 'NG': 'natural_gas'}[kind] for kind in node['raw'])
                attributes = visualizer.get_facility_visualization_attrs(raw, 'yes' if node['saf'] else 'no', 'yes' if node['airport'] else 'no')
                for values in reversed(attributes):
                    if node['airport']:
                        axis.scatter([position[0]], [position[1]], marker=values['marker'], s=values['size'] * marker_scale * 3,
                                     c='white', edgecolors='white', linewidths=1.2, zorder=6)
                    artist = axis.scatter([position[0]], [position[1]], marker=values['marker'], s=values['size'] * marker_scale,
                                          c=values['color'], edgecolors=values['edgecolor'], linewidths=values['linewidth'] * .35, zorder=6)
                    artist.set_clip_path(clip)
            if variant == 'main':
                axis.text(510, 20, name, ha='center', va='center', fontfamily='Times New Roman', fontweight='bold', fontsize=12.5,
                          zorder=10, bbox={'facecolor': 'white', 'edgecolor': 'none', 'pad': .5})
            stem = f'Main_Map_{name}' if variant == 'main' else f'Figure_S{FIGURE_NUMBERS[name]}'
            png = output / (stem + '.png')
            fig.savefig(png, dpi=dpi, facecolor='white')
            plt.close(fig)
            image_pdf(png, output / (stem + '.pdf'), dpi)
            checks.append({'scenario': name, 'variant': variant, 'nodes': len(nodes), 'routes': len(routes),
                           'all_selected_sites_inside_frame': True, 'geometry_basis': 'endpoint_schematic',
                           'background_source': 'Original Supplementary Figure S54; shared geographic range across the four main map panels' if variant == 'main' else 'Original Supplementary Figure S54',
                           'registration_max_tick_error_pixels': registration.get('max_tick_error_pixels', registration.get('tick_max_pixel_error'))})
            print(stem, flush=True)
    (data / 'map_checks.json').write_text(json.dumps(checks, indent=2), encoding='utf-8')


def network_panels(data, output):
    metrics = pd.read_csv(data / 'network_metrics.csv')
    decisions = pd.read_csv(data / 'decision_classification.csv')
    assert set(metrics.Scenario) == set(SCENARIOS)
    names = metrics.Scenario.tolist()
    normalized = panels._normalize_metrics(metrics[METRIC_NAMES].to_numpy())
    colors = dict(zip(['CTL', 'DAC-GH-MTJ', 'DAC-GH-FT', 'GTL-GH', 'GTL', 'CCU-GH-MTJ', 'CCU-GH-FT',
                       'CTL-BH', 'DAC-BH-MTJ', 'DAC-BH-FT', 'GTL-BH', 'CCU-BH-MTJ', 'CCU-BH-FT'], panels.PROCESS_COLOR_PALETTE))
    panels.setup_plot_style()
    panels.RADAR_LABELS_SHORT[-1] = 'Largest-source\nflow share'
    panels.ABS_STACK_INDICATORS[5] = ('electrolyzer', 'Selected H2 production or purification modules')
    panels.ABS_STACK_INDICATORS[6] = ('saf_plant', 'Selected SAF conversion modules')
    fig = plt.figure(figsize=(36, 18))
    grid = fig.add_gridspec(2, 4, left=.055, right=.98, bottom=.16, top=.95, hspace=.15, wspace=.18, height_ratios=[1, 1.1])
    for column, group in enumerate([3, 2, 0, 1]):
        indices = sorted(metrics.index[metrics.Cluster == group], key=lambda item: names[item])
        axis = fig.add_subplot(grid[0, column], polar=True)
        panels.plot_radar_subplot(axis, normalized, indices, panels.CLUSTER_THEMES[group], names, colors)
        axis.text(-.03, 1.05, '(' + chr(ord('e') + column) + ')', transform=axis.transAxes, fontsize=30, fontweight='bold')
        axis = fig.add_subplot(grid[1, column])
        ordered = [names[item] for item in indices]
        counts = [panels._aggregate_colocation_counts(decisions, name) for name in ordered]
        panels.plot_dot_matrix_subplot(axis, ordered, counts, metrics.loc[indices, 'h2_supply_module_count'].tolist(),
                                      metrics.loc[indices, 'saf_module_count'].tolist(), colors, show_ylabels=column == 0)
        axis.set_xticklabels([])
        axis.text(-.03, 1.06, '(' + chr(ord('i') + column) + ')', transform=axis.transAxes, fontsize=30, fontweight='bold')
        handles = [plt.Line2D([0], [0], color=colors[name], linewidth=8, label=name) for name in ordered]
        axis.legend(handles=handles, loc='upper center', bbox_to_anchor=(.5, -.08), ncol=3 if len(ordered) > 2 else len(ordered),
                    frameon=False, fontsize=23, handlelength=.65, columnspacing=.7, handletextpad=.4)
    publication_terms(fig)
    fig.savefig(output / 'network_panels.png', dpi=200)
    fig.savefig(output / 'network_panels.pdf')
    plt.close(fig)


def figure_s27(data, output):
    draw = load_appendix_template('spatial_supplement_template')
    metrics = pd.read_csv(data / 'network_metrics.csv')
    siting = pd.read_csv(data / 'siting_metrics.csv')
    decisions = pd.read_csv(data / 'decision_classification.csv')
    draw.load_latest_network_metrics = lambda: (metrics.copy(), siting.copy(), decisions.copy())
    original_site_label, original_material_label = draw.translate_site_share_label, draw.translate_material_label
    draw.translate_site_share_label = lambda value: original_site_label(value).replace('₂', '2')
    draw.translate_material_label = lambda value: original_material_label(value).replace('₂', '2')

    def export(figure, path):
        publication_terms(figure)
        for axis in figure.axes:
            for layer in axis.images:
                values = np.asarray(layer.get_array())
                if values.ndim != 2:
                    continue
                for label in axis.texts:
                    x, y = label.get_position()
                    if float(x).is_integer() and float(y).is_integer() and 0 <= int(y) < values.shape[0] and 0 <= int(x) < values.shape[1]:
                        label.set_color('white' if layer.norm(values[int(y), int(x)]) > .6 else '#17243a')
        for suffix in ['png', 'pdf']:
            figure.savefig(path.with_suffix('.' + suffix), dpi=300, bbox_inches='tight', pad_inches=.04, facecolor=figure.get_facecolor())
        plt.close(figure)
        return path

    draw.save_matplotlib_figure = export
    draw.create_cluster_archetype_figure(output / 'Figure_S27.png')


def figure_s26(data, output, temporal_data, temporal_inputs, accounting_root=None):
    draw = load_appendix_template('spatial_joint_template')
    source = temporal_data / 'all_pathway_temporal_metrics.csv'
    manifest = json.loads((temporal_inputs / 'manifest.json').read_text(encoding='utf-8'))
    assert manifest['full_thirteen_baselines']
    assert set(manifest['configurations']) == set(SCENARIOS)
    for name, record in manifest['configurations'].items():
        for path, expected in record['source_hashes'].items():
            if PureWindowsPath(path).name in ['accounts.json', 'normalized_carbon_emissions.json']:
                resolved = accounting_root / name / 'baseline' / PureWindowsPath(path).name if accounting_root else Path(path)
                assert checksum(resolved) == expected, (name, resolved, 'Temporal inputs require the current final accounts')
        carbon_path = temporal_inputs / f'{name}_carbon.json'
        assert checksum(carbon_path) == record['adapted_files']['carbon']['sha256']
    metrics = pd.read_csv(source)
    assert metrics.Scenario.is_unique and set(metrics.Scenario) == set(SCENARIOS)
    network = draw.translate_network_metric_columns(pd.read_csv(data / 'network_metrics.csv'))
    columns = ['Scenario', 'NodeCount', 'MeanTransportDistance', 'saf_module_count'] + [column for _, column in draw.SITE_SHARE_COLUMNS]
    metrics = metrics.merge(network[columns], on='Scenario', validate='one_to_one')
    metrics['MeanSAFUtilization'] = metrics.SAFMean / 100
    metrics['Route'] = metrics.Pathway
    metrics['SAF_Plants'] = metrics.saf_module_count
    carbon_paths = [temporal_inputs / f'{name}_carbon.json' for name in metrics.Scenario]
    carbon = [json.loads(path.read_text(encoding='utf-8')) for path in carbon_paths]
    metrics['CarbonIntensity'] = [row['carbon_intensity_mj'] for row in carbon]
    assert np.isfinite(metrics.CarbonIntensity).all()
    metrics.to_csv(data / 'scenario_integrated_metrics.csv', index=False)
    with plt.rc_context(draw.get_publication_rc()):
        figure = draw.create_template_figure('quad_multi')
        grid = figure.add_gridspec(2, 2, left=.08, right=.985, top=.88, bottom=.22, wspace=.28, hspace=.42)
        axis = figure.add_subplot(grid[0, 0])
        draw.apply_scatter_template(axis, metrics.WorstWeekRetention, metrics.MeanSAFUtilization * 100,
                                    marker='o', s=np.clip(metrics.LCOE * 2.2, 18, 120),
                                    c=metrics.Category.map(draw.category_color), edgecolors='white', linewidth=.7)
        axis.set_xlabel('Worst-week retention (%)')
        axis.set_ylabel('Mean SAF utilization (%)')
        draw.style_chart_axes(axis)
        draw.add_panel_label(axis, 'A')
        axis = figure.add_subplot(grid[0, 1])
        for route, marker in draw.ROUTE_MARKERS.items():
            selected = metrics[metrics.Route.eq(route)]
            draw.apply_scatter_template(axis, selected.NodeCount, selected.MeanTransportDistance,
                                        label=route, marker=marker, s=np.clip(selected.SAF_Plants * 2.8, 20, 130),
                                        c=selected.Category.map(draw.category_color), edgecolors='white', linewidth=.7)
        axis.set_xlabel('Active mass-flow network nodes')
        axis.set_ylabel('Mean transport distance (km)')
        draw.style_chart_axes(axis)
        draw.add_publication_legend(axis, loc='upper center', bbox_to_anchor=(.5, 1.24), ncol=2)
        draw.add_panel_label(axis, 'B')
        axis = figure.add_subplot(grid[1, 0])
        ordered = metrics.sort_values('Scenario', key=lambda values: values.map(draw.scenario_sort_key))
        colors = [draw.PUBLICATION_COLORS[key] for key in ['blue', 'sky', 'orange', 'green', 'gray']]
        series = [(draw.translate_site_share_label(label).replace('₂', '2'), ordered[column].to_numpy(), color)
                  for (label, column), color in zip(draw.SITE_SHARE_COLUMNS, colors)]
        draw.apply_stacked_bar_template(axis, ordered.Scenario.tolist(), series,
                                        xlabel='Share of SAF production siting (%)', orientation='h', legend=True,
                                        legend_kwargs={'ncol': 3, 'loc': 'upper center', 'bbox_to_anchor': (.5, -.22)})
        draw.add_panel_label(axis, 'C')
        axis = figure.add_subplot(grid[1, 1])
        draw.apply_horizontal_bar_template(axis, ordered.Scenario.tolist(), ordered.LCOE.to_numpy(),
                                           colors=ordered.Category.map(draw.category_color).tolist(),
                                           xlabel='Fuel cost (CNY/kg)', invert=True)
        intensity_axis = axis.twiny()
        intensity_axis.scatter(ordered.CarbonIntensity, ordered.Scenario, color=draw.PUBLICATION_COLORS['black'],
                               s=18, edgecolors='none', label='Supply-chain CI')
        intensity_axis.set_xlabel('Supply-chain CI (g CO2e/MJ)')
        intensity_axis.tick_params(labelsize=6.5, width=.6, length=2)
        draw.add_panel_label(axis, 'D')
        publication_terms(figure)
        for suffix in ['png', 'pdf']:
            figure.savefig(output / ('Figure_S26.' + suffix), dpi=300, bbox_inches='tight', pad_inches=.04, facecolor=figure.get_facecolor())
        plt.close(figure)
    (data / 'joint_metrics_provenance.json').write_text(json.dumps(dict(
        temporal_metrics=dict(path=str(source), sha256=checksum(source)),
        network_metrics_sha256=checksum(data / 'network_metrics.csv'),
        carbon_sources={path.name: checksum(path) for path in carbon_paths},
        plotted_carbon='Direct supply-chain carbon intensity in g CO2e/MJ',
        metrics_sha256=checksum(data / 'scenario_integrated_metrics.csv')), indent=2), encoding='utf-8')


def compose_main(output, templates):
    document = pymupdf.open()
    page = document.new_page(width=1046.4, height=880.32)
    page.insert_image(page.rect, filename=str(templates / 'main_composite_template.png'))
    scale = .24
    page.draw_rect(pymupdf.Rect(0, 145 * scale, 1046.4, 3240 * scale), color=None, fill=(1, 1, 1))
    page.insert_image(pymupdf.Rect(0, 3240 * scale, 1046.4, 3668 * scale), filename=str(output / 'main_shared_legend.png'))
    for column, (name, x) in enumerate(zip(REPRESENTATIVES, [142, 1176, 2215, 3234])):
        page.insert_image(pymupdf.Rect(x * scale, 155 * scale, (x + 1020) * scale, 995 * scale), filename=str(output / f'Main_Map_{name}.png'))
        page.insert_text((x * scale, 195 * scale), '(' + chr(ord('a') + column) + ')', fontname='tibo', fontsize=12)
    components = pymupdf.open(output / 'network_panels.pdf')
    page.show_pdf_page(pymupdf.Rect(0, 995 * scale, 1046.4, 3175 * scale), components, 0)
    document.save(output / 'Figure_2.pdf', garbage=4, deflate=True)
    page.get_pixmap(dpi=300, alpha=False).save(output / 'Figure_2.png')
    components.close()
    document.close()
    document = pymupdf.open()
    page = document.new_page(width=900, height=725)
    for index, name in enumerate(REPRESENTATIVES):
        x, y = index % 2 * 450, index // 2 * 362.5
        page.insert_image(pymupdf.Rect(x, y + 16, x + 450, y + 362.5), filename=str(output / f'Figure_S{FIGURE_NUMBERS[name]}.png'))
        title = '(' + chr(ord('a') + index) + ')  ' + name
        width = pymupdf.get_text_length(title, fontname='tibo', fontsize=10)
        page.insert_text((x + (450 - width) / 2, y + 11), title, fontname='tibo', fontsize=10)
    document.save(output / 'Figure_S50.pdf', garbage=4, deflate=True)
    page.get_pixmap(dpi=300, alpha=False).save(output / 'Figure_S50.png')
    document.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace-root', type=Path, default=ROOT)
    parser.add_argument('--legacy-figures', type=Path)
    parser.add_argument('--external-project', type=Path)
    parser.add_argument('--accounting-root', type=Path)
    parser.add_argument('--data', type=Path, default=HERE / 'network_data')
    parser.add_argument('--templates', type=Path, default=HERE / 'templates')
    parser.add_argument('--output', type=Path, default=HERE / 'figures')
    parser.add_argument('--scenarios', nargs='+', choices=SCENARIOS, default=SCENARIOS)
    parser.add_argument('--maps-only', action='store_true')
    parser.add_argument('--skip-joint', action='store_true')
    parser.add_argument('--joint-only', action='store_true')
    parser.add_argument('--layout-only', action='store_true')
    parser.add_argument('--temporal-data', type=Path, default=HERE.parent / 'figures_temporal/temporal_data')
    parser.add_argument('--temporal-inputs', type=Path, default=HERE.parent / 'figures_temporal/inputs')
    args = parser.parse_args()
    configure_sources(args.workspace_root, args.legacy_figures, args.external_project)
    assert not (args.skip_joint and args.joint_only)
    assert not (args.maps_only and args.joint_only)
    args.output.mkdir(parents=True, exist_ok=True)
    logging.getLogger('fontTools.subset').setLevel(logging.WARNING)
    if not args.maps_only:
        provenance = json.loads((args.data / 'provenance.json').read_text(encoding='utf-8'))
        assert provenance['complete_network_set'] and set(args.scenarios) == set(SCENARIOS)
    if args.joint_only:
        figure_s26(args.data, args.output, args.temporal_data, args.temporal_inputs, args.accounting_root)
    else:
        if not args.layout_only:
            plot_maps(args.data, args.output, args.templates, args.scenarios)
        shared_legends(args.output)
        if not args.maps_only:
            network_panels(args.data, args.output)
            if not args.skip_joint:
                figure_s26(args.data, args.output, args.temporal_data, args.temporal_inputs, args.accounting_root)
            figure_s27(args.data, args.output)
            compose_main(args.output, args.templates)
    records = {path.name: {'sha256': checksum(path), 'bytes': path.stat().st_size}
               for path in sorted(args.output.iterdir()) if path.suffix in ('.png', '.pdf')}
    (args.output / 'render_manifest.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
    (args.output / 'render_provenance.json').write_text(json.dumps(dict(
        renderer_sha256=checksum(Path(__file__)),
        network_provenance_sha256=checksum(args.data / 'provenance.json'),
        map_calibration=dict(path=str(args.templates / 'current_archive_registration.json'),
                             sha256=checksum(args.templates / 'current_archive_registration.json')),
        retained_template_provenance_sha256=checksum(args.templates / 'provenance.json'),
        output_manifest_sha256=checksum(args.output / 'render_manifest.json')), indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
