import argparse
import ast
import hashlib
import importlib.util
import io
import json
import math
import sqlite3
from collections import Counter
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
OLD = ROOT / 'work/nexus_targeted_revision/revision_20261007/figures_space_time'
SCENARIOS = ['CTL', 'CTL-BH', 'GTL-GH', 'GTL', 'GTL-BH', 'CCU-GH-MTJ', 'CCU-GH-FT',
             'CCU-BH-MTJ', 'CCU-BH-FT', 'DAC-GH-MTJ', 'DAC-GH-FT', 'DAC-BH-MTJ', 'DAC-BH-FT']
GROUPS = {'CCU-BH-MTJ': 3, 'CCU-GH-FT': 3, 'CCU-GH-MTJ': 3, 'DAC-GH-FT': 3, 'DAC-GH-MTJ': 3,
          'CCU-BH-FT': 2, 'CTL': 2, 'CTL-BH': 2, 'GTL': 2, 'GTL-GH': 2,
          'GTL-BH': 0, 'DAC-BH-FT': 1, 'DAC-BH-MTJ': 1}
METRIC_NAMES = ['节点数量', '关键节点集中度', '关键通道集中度', '平均运输距离', '跨区域物流比例', '单点失效影响']


def checksum(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


class RoadDistances:
    def __init__(self, database, extensions):
        self.database = database
        with sqlite3.connect(f'file:{database.resolve().as_posix()}?mode=ro', uri=True) as connection:
            self.routes = {row[0]: (float(row[1]), row[2]) for row in connection.execute(
                'select cache_key,distance_km,method_used from route_cache')}
        for path in extensions:
            for line in path.read_text(encoding='utf-8').splitlines():
                row = json.loads(line)
                distance, _, _, method = row['route']
                self.routes[row['key']] = (float(distance), method)

    def lookup(self, source, destination):
        if np.allclose(source[:2], destination[:2], rtol=0, atol=1e-6):
            return 0.0
        key = hashlib.md5(f'{source[0]:.6f},{source[1]:.6f},{destination[0]:.6f},{destination[1]:.6f},truck'.encode()).hexdigest()
        distance, method = self.routes[key]
        assert method == 'graphhopper_api' and np.isfinite(distance) and distance >= 0, (key, method, distance)
        return distance


def route_record(scenario, source, destination, cargo, quantity, distance, locations, distance_source):
    a, b = locations[source], locations[destination]
    assert quantity > 1e-5 and np.isfinite(quantity)
    assert np.isfinite(distance) and distance >= 0
    return {'scenario': scenario, 'source': source, 'destination': destination, 'cargo': cargo,
            'mode': 'pipeline' if cargo in ('H2', 'CO2') else 'truck',
            'weekly_quantity': float(quantity), 'quantity_unit': 'm3' if cargo == 'NG' else 'kg',
            'distance_km': float(distance), 'distance_source': distance_source,
            'source_latitude': a['latitude'], 'source_longitude': a['longitude'],
            'destination_latitude': b['latitude'], 'destination_longitude': b['longitude'],
            'source_type': a['type'], 'destination_type': b['type'],
            'coordinates': [[a['longitude'], a['latitude']], [b['longitude'], b['latitude']]],
            'geometry_basis': 'endpoint_schematic'}


def current_routes(scenario, run, accounts, roads, provenance):
    summary_path = run / 'summary.json'
    summary = read_json(summary_path)
    assert summary['has_solution'] and summary['algebraic_validation']['passed'] and summary['gap'] <= .01
    assert not (run / 'EXPORT_IN_PROGRESS').exists()
    final = read_json(accounts / 'accounts.json')
    assert final['checks']['passed'] and final['source_summary_sha256'] == checksum(summary_path)
    solution = read_json(accounts / 'normalized_complete_solution.json')
    parameters = read_json(run / 'model_parameters.json')
    locations = dict(parameters['locations'])
    weeks = int(parameters['weeks'])
    assert weeks == 4
    deliveries = pd.read_csv(run / 'deliveries.csv')
    for airport in deliveries.airport.unique():
        if airport not in locations:
            location = locations['airport_' + airport]
            assert location['type'] == 'airport'
            locations[airport] = dict(location)
    routes = []
    h2 = pd.read_csv(run / 'hydrogen_transport_accounting.csv')
    for row in h2[h2.weekly_contract_kg > 1e-5].to_dict('records'):
        routes.append(route_record(scenario, row['source'], row['destination'], 'H2', row['weekly_contract_kg'],
                                   row['pipeline_distance_km'], locations, 'hydrogen_transport_accounting.csv'))
    for (source, airport), quantity in deliveries.groupby(['location', 'airport']).value.sum().items():
        if quantity / weeks <= 1e-5:
            continue
        a, b = locations[source], locations[airport]
        distance = roads.lookup((a['latitude'], a['longitude']), (b['latitude'], b['longitude']))
        routes.append(route_record(scenario, source, airport, 'SAF', quantity / weeks, distance, locations,
                                   'Actual model GraphHopper route cache'))
    if scenario.startswith('CCU-'):
        co2 = pd.read_csv(run / 'ccu_co2_transport_accounting.csv')
        for row in co2[co2.weekly_contract_kg > 1e-5].to_dict('records'):
            routes.append(route_record(scenario, row['source'], row['destination'], 'CO2', row['weekly_contract_kg'],
                                       row['pipeline_distance_km'], locations, 'ccu_co2_transport_accounting.csv'))
    elif scenario.startswith('DAC-'):
        co2 = pd.read_csv(run / 'co2_weekly_contracts.csv')
        metadata = read_json(run / 'co2_balance_parameters.json')
        distances = {(row['source'], row['destination']): row['distance_km'] for row in metadata['routes']}
        for row in co2[co2.value > 1e-5].to_dict('records'):
            routes.append(route_record(scenario, row['source'], row['destination'], 'CO2', row['value'],
                                       distances[row['source'], row['destination']], locations, 'co2_balance_parameters.json'))
    elif scenario in ('GTL-GH', 'GTL-BH'):
        ng = pd.read_csv(run / 'ng_flows.csv')
        metadata = read_json(run / 'natural_gas_parameters.json')
        distances = {(row['source'], row['destination']): row['distance_km'] for row in metadata['routes']}
        for (source, destination), quantity in ng.groupby(['source', 'destination']).value.sum().items():
            if quantity / weeks > 1e-5:
                routes.append(route_record(scenario, source, destination, 'NG', quantity / weeks,
                                           distances[source, destination], locations, 'natural_gas_parameters.json'))
    assert np.isclose(sum(row['weekly_quantity'] for row in routes if row['cargo'] == 'SAF') * weeks,
                      summary['production_kg'], rtol=1e-8, atol=1e-3)
    provenance[scenario] = {'run': str(run), 'summary_sha256': checksum(summary_path),
                            'accounts': str(accounts / 'accounts.json'), 'accounts_sha256': checksum(accounts / 'accounts.json'),
                            'normalized_solution_sha256': checksum(accounts / 'normalized_complete_solution.json'),
                            'demand_fulfillment_ratio': summary['demand_fulfillment_ratio']}
    return solution, routes


def retained_gtl(packet, provenance):
    with ZipFile(packet) as archive:
        solution_name = [name for name in archive.namelist() if name.endswith('normalized_pathway_records/GTL_complete_solution.json')]
        routes_name = [name for name in archive.namelist() if name.endswith('figures_space_time_network_data/GTL_transport_summary.csv')]
        assert len(solution_name) == 1 and len(routes_name) == 1
        solution = json.loads(archive.read(solution_name[0]))
        raw = pd.read_csv(io.BytesIO(archive.read(routes_name[0])))
        routes = []
        for row in raw.to_dict('records'):
            assert row['货物类型'] == 'MTJ'
            quantity = float(row['周运输量(kg)'])
            if quantity <= 1e-5:
                continue
            a, b = ast.literal_eval(row['起点坐标']), ast.literal_eval(row['终点坐标'])
            locations = {row['起点']: {'latitude': a[0], 'longitude': a[1], 'type': row['起点类型']},
                         row['终点']: {'latitude': b[0], 'longitude': b[1], 'type': row['终点类型']}}
            routes.append(route_record('GTL', row['起点'], row['终点'], 'SAF', quantity,
                                       float(row['距离(km)']), locations, 'Retained GTL archived transport records'))
        provenance['GTL'] = {'packet': str(packet), 'packet_sha256': checksum(packet),
                             'solution_member': solution_name[0], 'solution_sha256': hashlib.sha256(archive.read(solution_name[0])).hexdigest(),
                             'routes_member': routes_name[0], 'routes_sha256': hashlib.sha256(archive.read(routes_name[0])).hexdigest(),
                             'demand_fulfillment_ratio': solution['demand_fulfillment_ratio']}
    return solution, routes


def network_tables(name, solution, routes, output, metrics_module):
    standard = pd.DataFrame([{
        '起点': row['source'], '终点': row['destination'], '起点类型': row['source_type'], '终点类型': row['destination_type'],
        '距离(km)': row['distance_km'], '起点坐标': str((row['source_latitude'], row['source_longitude'])),
        '终点坐标': str((row['destination_latitude'], row['destination_longitude'])), '路径坐标': json.dumps(row['coordinates']),
        '货物类型': {'H2': '氢气', 'SAF': 'MTJ', 'NG': '天然气'}.get(row['cargo'], row['cargo']), '运输方式': row['mode'],
        '周运输量(kg)': row['weekly_quantity'] if row['quantity_unit'] == 'kg' else 0,
        '周运输量(m3)': row['weekly_quantity'] if row['quantity_unit'] == 'm3' else 0,
    } for row in routes])
    standard.to_csv(output / f'{name}_transport_summary.csv', index=False)
    mass = standard[standard['周运输量(kg)'] > 1e-5]
    mass.to_csv(output / f'{name}_mass_transport.csv', index=False)
    stats = metrics_module._compute_metrics(output / f'{name}_mass_transport.csv', 100)
    metrics = {'Scenario': name, 'OfficialName': name, 'Cluster': GROUPS[name], **dict(zip(METRIC_NAMES, [
        stats.node_count, stats.key_node_share, stats.key_route_share, stats.avg_distance,
        stats.cross_region_share, stats.single_point_share]))}
    for cargo in ['H2', 'SAF', 'CO2', 'NG']:
        rows = [row for row in routes if row['cargo'] == cargo]
        total = sum(row['weekly_quantity'] for row in rows)
        metrics[cargo + '_distance_km'] = sum(row['weekly_quantity'] * row['distance_km'] for row in rows) / total if total else 0.0
        metrics[cargo + '_weekly_quantity'] = total
    coordinates, names = {}, {}
    for row in routes:
        for role in ['source', 'destination']:
            coordinate = (round(row[role + '_latitude'], 6), round(row[role + '_longitude'], 6))
            names[row[role]] = coordinate
            entry = coordinates.setdefault(coordinate, {'raw': set(), 'saf': False, 'airport': False})
            if '机场' in row[role + '_type'] or row[role + '_type'] == 'airport':
                entry['airport'] = True
            if role == 'source' and row['cargo'] in ('H2', 'CO2', 'NG'):
                entry['raw'].add(row['cargo'])
    fuel = [row for row in solution['facilities'].values()
            if row.get('technology') != 'electrolyzer' and row.get('built') and row.get('capacity_kg_per_hour', 0) > 1e-5]
    hydrogen = [row for row in solution.get('hydrogen_facilities', {}).values()
                if row.get('built') and row.get('capacity_kg_h2_per_hour', row.get('capacity_kg_per_hour', 0)) > 1e-5]
    site_types, capacity_rows = Counter(), []
    for facility in fuel:
        location = facility['location']
        coordinate = (round(facility['latitude'], 6), round(facility['longitude'], 6)) if 'latitude' in facility else names[location]
        entry = coordinates.setdefault(coordinate, {'raw': set(), 'saf': False, 'airport': False})
        entry['saf'] = True
        kind = facility.get('location_type', '')
        if entry['airport'] or kind == 'airport':
            site = 'Airport site'
            entry['airport'] = True
        elif kind in ('solar_plant', 'wind_farm'):
            site = 'Renewable site'
        elif kind == 'co2_capture':
            site = 'CO2 capture site'
            entry['raw'].add('CO2')
        elif 'byproduct' in kind:
            site = 'Byproduct H2 site'
            entry['raw'].add('H2')
        else:
            site = 'Other site'
        site_types[site] += 1
        capacity_rows.append({'scenario': name, 'location': location, 'technology': facility['technology'],
                              'latitude': coordinate[0], 'longitude': coordinate[1],
                              'capacity_kg_h': facility['capacity_kg_per_hour']})
    for facility in hydrogen:
        location = facility['location']
        coordinate = (round(facility['latitude'], 6), round(facility['longitude'], 6)) if 'latitude' in facility else names[location]
        coordinates.setdefault(coordinate, {'raw': set(), 'saf': False, 'airport': False})['raw'].add('H2')
    counts = Counter()
    for entry in coordinates.values():
        raw = entry['raw']
        material = 'CO2 capture+H2 production' if {'H2', 'CO2'} <= raw else 'H2 production' if 'H2' in raw else 'CO2 capture' if 'CO2' in raw else 'NG source' if 'NG' in raw else 'No raw material production'
        counts[material, 'yes' if entry['saf'] else 'no', 'yes' if entry['airport'] else 'no'] += 1
    decision = [{'Scenario': name, 'OfficialName': name, 'Cluster': GROUPS[name],
                 'MaterialLabel': material, 'SAF_Production': saf, 'Consumption': airport, 'Count': count}
                for (material, saf, airport), count in counts.items()]
    siting = {'Scenario': name, 'OfficialName': name, 'Cluster': GROUPS[name],
              'h2_supply_module_count': len(hydrogen), 'electrolyzer_count': len(hydrogen) if '-GH-' in name or name in ('GTL-GH', 'CTL') else 0,
              'saf_module_count': len(fuel), 'saf_physical_sites': sum(entry['saf'] for entry in coordinates.values()),
              'all_physical_sites': len(coordinates)}
    for site in ['Renewable site', 'CO2 capture site', 'Airport site', 'Byproduct H2 site', 'Other site']:
        siting['SAF_Share_' + site] = 100 * site_types[site] / len(fuel) if fuel else 0
    metrics.update(siting)
    nodes = [{'latitude': coordinate[0], 'longitude': coordinate[1], 'raw': sorted(entry['raw']),
              'saf': entry['saf'], 'airport': entry['airport']} for coordinate, entry in coordinates.items()]
    (output / f'{name}_nodes.json').write_text(json.dumps(nodes, indent=2), encoding='utf-8')
    (output / f'{name}_routes.json').write_text(json.dumps(routes, ensure_ascii=False, indent=2), encoding='utf-8')
    return metrics, siting, decision, capacity_rows


def match_capacity(source, target, threshold):
    a, b = np.radians(source[['latitude', 'longitude']].to_numpy()), np.radians(target[['latitude', 'longitude']].to_numpy())
    delta = a[:, None, :] - b[None, :, :]
    haversine = np.sin(delta[:, :, 0] / 2) ** 2 + np.cos(a[:, None, 0]) * np.cos(b[None, :, 0]) * np.sin(delta[:, :, 1] / 2) ** 2
    distances = 6371.0088 * 2 * np.arcsin(np.sqrt(np.clip(haversine, 0, 1)))
    weights = np.minimum(source.capacity_kg_h.to_numpy()[:, None], target.capacity_kg_h.to_numpy()[None, :]) * (distances <= threshold)
    x, y = linear_sum_assignment(weights, maximize=True)
    total = float(weights[x, y].sum())
    return total, total / source.capacity_kg_h.sum() * 100, total / target.capacity_kg_h.sum() * 100


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runs', type=Path)
    parser.add_argument('--accounts', type=Path)
    parser.add_argument('--road-cache', type=Path)
    parser.add_argument('--route-extensions', type=Path, nargs='*', default=[])
    parser.add_argument('--packet', type=Path, default=ROOT / 'Nexus系统提交文件_代码归档同步20261015/Accompanying_Data.zip')
    parser.add_argument('--output', type=Path, default=HERE / 'network_data')
    parser.add_argument('--scenarios', nargs='+', choices=SCENARIOS, default=SCENARIOS)
    args = parser.parse_args()
    selected = args.scenarios
    if selected != ['GTL'] and not all(value is not None for value in (args.runs, args.accounts, args.road_cache)):
        raise ValueError('Real run, account and road-cache paths are required for the recomputed configurations')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    spec = importlib.util.spec_from_file_location('network_original_metrics', OLD / 'source/network_classification_metrics_builder.py')
    metric_module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[spec.name] = metric_module
    spec.loader.exec_module(metric_module)
    roads = RoadDistances(args.road_cache, args.route_extensions) if args.road_cache else None
    metric_rows, site_rows, decision_rows, capacity_rows, provenance = [], [], [], [], {}
    for name in selected:
        if name == 'GTL':
            solution, routes = retained_gtl(args.packet, provenance)
        else:
            solution, routes = current_routes(name, args.runs / name / 'baseline', args.accounts / name / 'baseline', roads, provenance)
        metrics, siting, decisions, capacities = network_tables(name, solution, routes, output, metric_module)
        metric_rows.append(metrics)
        site_rows.append(siting)
        decision_rows.extend(decisions)
        capacity_rows.extend(capacities)
    metrics = pd.DataFrame(metric_rows)
    assert metrics.Scenario.is_unique and set(metrics.Scenario) == set(selected)
    metrics.to_csv(output / 'network_metrics.csv', index=False)
    pd.DataFrame(site_rows).to_csv(output / 'siting_metrics.csv', index=False)
    pd.DataFrame(decision_rows).to_csv(output / 'decision_classification.csv', index=False)
    capacities = pd.DataFrame(capacity_rows)
    capacities.to_csv(output / 'synthesis_modules.csv', index=False)
    sites = capacities.groupby(['scenario', 'latitude', 'longitude'], as_index=False).capacity_kg_h.sum()
    sites.to_csv(output / 'synthesis_sites.csv', index=False)
    pairs = [('GTL-BH', 'GTL'), ('GTL-BH', 'CCU-GH-FT'), ('GTL', 'CCU-GH-FT')]
    matching = []
    for source, target in pairs:
        if source not in selected or target not in selected:
            continue
        for threshold in [1, 10, 25, 50, 100]:
            total, share_source, share_target = match_capacity(sites[sites.scenario.eq(source)], sites[sites.scenario.eq(target)], threshold)
            matching.append({'source': source, 'target': target, 'threshold_km': threshold,
                             'matched_capacity_kg_h': total, 'source_share_percent': share_source,
                             'target_share_percent': share_target})
    pd.DataFrame(matching).to_csv(output / 'Table_S24_matching.csv', index=False)
    provenance['schema'] = {'metric_units': 'Mean weekly H2, CO2 and SAF mass flows; natural gas volumes reported separately',
                             'comparison_groups': 'Retained group membership; no new clustering is asserted',
                             'geometry': 'Endpoint-only schematic connections; all distance statistics use authentic model distances',
                             'physical_coordinate_precision': 'Six decimal places, matching the retained coordinate aggregation rule'}
    provenance['complete_network_set'] = set(selected) == set(SCENARIOS)
    artifact_names = {'network_metrics.csv', 'siting_metrics.csv', 'decision_classification.csv',
                      'synthesis_modules.csv', 'synthesis_sites.csv', 'Table_S24_matching.csv'}
    artifact_names.update(name + suffix for name in selected
                          for suffix in ['_transport_summary.csv', '_mass_transport.csv', '_nodes.json', '_routes.json'])
    provenance['adapter_sha256'] = checksum(Path(__file__))
    provenance['output_sha256'] = {name: checksum(output / name) for name in sorted(artifact_names)}
    (output / 'provenance.json').write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding='utf-8')
    print(metrics[['Scenario', '节点数量', 'saf_module_count', 'saf_physical_sites', '平均运输距离']].to_string(index=False))


if __name__ == '__main__':
    main()
