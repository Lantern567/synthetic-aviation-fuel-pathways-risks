import json
from collections import defaultdict
from pathlib import Path

import coptpy as cp
import numpy as np
import pandas as pd


class DacCO2ConservationMixin:
    def _define_co2_transport_variables(self):
        if not self.scenario.startswith('DAC-'):
            return super()._define_co2_transport_variables()
        super()._define_co2_transport_variables()
        assert self.hours_per_period == 3, self.hours_per_period
        assert self.total_hours == self.time_horizon_weeks * self.periods_per_week
        assert self.periods_per_week * self.hours_per_period == 168
        self.co2_period_flow_vars = {}
        # 路线编号由名称排序决定，保证独立建模进程中的流量变量含义一致。
        for route_number, (source, destination) in enumerate(sorted(self.co2_pipeline_flow_vars)):
            assert source != destination, (source, destination)
            for period in range(self.total_hours):
                self.co2_period_flow_vars[source, destination, period] = self.model.addVar(
                    lb=0, name=f'corrected_co2_flow_{route_number}_p{period}'
                )

    def _define_co2_inventory_variables(self):
        if not self.scenario.startswith('DAC-'):
            return super()._define_co2_inventory_variables()
        super()._define_co2_inventory_variables()
        nodes = set(location for location, period in self.dac_co2_supply)
        nodes.update(location for location, period in self.co2_inventory_vars)
        nodes.update(source for source, destination in self.co2_pipeline_flow_vars)
        nodes.update(destination for source, destination in self.co2_pipeline_flow_vars)
        for location in sorted(nodes):
            assert location in self.locations, location
            for period in range(self.total_hours + 1):
                key = location, period
                if key not in self.co2_inventory_vars:
                    self.co2_inventory_vars[key] = self.model.addVar(
                        lb=0, name=f'corrected_co2_inventory_{location}_p{period}'
                    )
        self.co2_balance_nodes = sorted(nodes)
        self._co2_balances_added = False
        self._co2_contract_constraints_added = False

    def _add_co2_inventory_balance_constraints(self):
        if not self.scenario.startswith('DAC-'):
            return super()._add_co2_inventory_balance_constraints()
        # 基础模型会调用两次本方法，同一组守恒约束仅创建一次。
        if self._co2_balances_added:
            return
        incoming, outgoing, consumption = defaultdict(list), defaultdict(list), defaultdict(list)
        for (source, destination, period), flow in self.co2_period_flow_vars.items():
            outgoing[source, period].append(flow)
            incoming[destination, period].append(flow)
        for (location, technology, period), production in self.production_vars.items():
            if 'co2_consumption_ratio' in self.technologies[technology]:
                ratio = float(self.technologies[technology]['co2_consumption_ratio'])
                assert np.isfinite(ratio) and ratio > 0, (technology, ratio)
                consumption[location, period].append(production * ratio)
                assert location in self.co2_balance_nodes, (location, technology)
        self.co2_consumption_expressions = {}
        for location in self.co2_balance_nodes:
            self.model.addConstr(
                self.co2_inventory_vars[location, 0] == 0,
                name=f'corrected_co2_initial_{location}'
            )
            for period in range(self.total_hours):
                use = cp.quicksum(consumption[location, period])
                self.co2_consumption_expressions[location, period] = use
                self.model.addConstr(
                    self.co2_inventory_vars[location, period + 1]
                    == self.co2_inventory_vars[location, period]
                    + self.dac_co2_supply.get((location, period), 0)
                    + cp.quicksum(incoming[location, period])
                    - cp.quicksum(outgoing[location, period]) - use,
                    name=f'corrected_co2_balance_{location}_p{period}'
                )
        self._co2_balances_added = True

    def _add_co2_pipeline_flow_constraints(self):
        if not self.scenario.startswith('DAC-'):
            return super()._add_co2_pipeline_flow_constraints()
        assert self._co2_balances_added
        if self._co2_contract_constraints_added:
            return
        # 保留原模型固定周合同，实际流量在同一期间从源端扣除、向目的地加入。
        for route_number, (source, destination) in enumerate(sorted(self.co2_pipeline_flow_vars)):
            weekly = self.co2_pipeline_flow_vars[source, destination]
            for week in range(self.time_horizon_weeks):
                periods = range(week * self.periods_per_week, (week + 1) * self.periods_per_week)
                self.model.addConstr(
                    cp.quicksum(self.co2_period_flow_vars[source, destination, period] for period in periods)
                    == weekly,
                    name=f'corrected_co2_contract_{route_number}_w{week}'
                )
        outgoing_contracts = defaultdict(list)
        for (source, destination), weekly in self.co2_pipeline_flow_vars.items():
            outgoing_contracts[source].append(weekly)
        for source, contracts in outgoing_contracts.items():
            for week in range(self.time_horizon_weeks):
                periods = range(week * self.periods_per_week, (week + 1) * self.periods_per_week)
                self.model.addConstr(
                    cp.quicksum(contracts)
                    <= cp.quicksum(self.dac_co2_supply[source, period] for period in periods),
                    name=f'corrected_co2_source_capture_{source}_w{week}'
                )
        self._co2_contract_constraints_added = True

    def _add_co2_pipeline_transport_cost(self, lifecycle_operation_factor):
        if not self.scenario.startswith('DAC-'):
            return super()._add_co2_pipeline_transport_cost(lifecycle_operation_factor)
        self._ensure_co2_pipeline_distance_cache()
        self.co2_route_parameters = {}
        terms = []
        for (source, destination), weekly in self.co2_pipeline_flow_vars.items():
            info = self.co2_pipeline_distance_cache[source, destination]
            distance = float(info['total_distance_km'] if 'total_distance_km' in info else info['distance_km'])
            unit_cost = float(self._calculate_co2_pipeline_cost_by_distance(distance))
            assert np.isfinite(distance) and distance >= 0, (source, destination, distance)
            assert np.isfinite(unit_cost) and unit_cost >= 0, (source, destination, unit_cost)
            self.co2_route_parameters[source, destination] = {
                'distance_km': distance, 'transport_cny_per_kg': unit_cost
            }
            # 四个周合同分别执行一次，生命周期系数对应整个代表周窗口。
            terms.append(weekly * self.time_horizon_weeks * unit_cost)
        self.cost_expressions['co2_pipeline_transport_cost'] = cp.quicksum(terms) * lifecycle_operation_factor

    def _create_carbon_emission_expressions(self):
        super()._create_carbon_emission_expressions()
        if not self.scenario.startswith('DAC-'):
            return
        intensity = float(self.carbon_params['transportation']['co2_pipeline_intensity'])
        assert np.isfinite(intensity) and intensity >= 0, intensity
        expression = cp.quicksum(
            weekly * self.time_horizon_weeks
            * self.co2_route_parameters[source, destination]['distance_km'] / 100 * intensity
            for (source, destination), weekly in self.co2_pipeline_flow_vars.items()
        )
        change = expression - self.carbon_expressions['co2_pipeline_transport']
        self.carbon_expressions['co2_pipeline_transport'] = expression
        self.carbon_expressions['co2_transport'] = expression + self.carbon_expressions['co2_truck_transport']
        self.carbon_aggregates['transport_emissions'] += change
        self.carbon_aggregates['total_emissions'] += change
        self.carbon_aggregates['annual_emissions'] += change * 52 / self.time_horizon_weeks

    def export_co2_balance_audit(self, output_directory, value):
        if not self.scenario.startswith('DAC-'):
            return
        assert self._co2_balances_added and self._co2_contract_constraints_added
        output = Path(output_directory)
        assert output.is_dir(), output
        records = [
            ('co2_flows.csv', self.co2_period_flow_vars, ['source', 'destination', 'period']),
            ('co2_inventory_vars.csv', self.co2_inventory_vars, ['location', 'period']),
            ('co2_consumption.csv', self.co2_consumption_expressions, ['location', 'period']),
            ('co2_weekly_contracts.csv', self.co2_pipeline_flow_vars, ['source', 'destination']),
        ]
        for filename, mapping, columns in records:
            rows = []
            for key, expression in mapping.items():
                assert len(key) == len(columns), key
                rows.append(dict(zip(columns, key), value=float(value(expression))))
            pd.DataFrame(rows, columns=columns + ['value']).to_csv(output / filename, index=False)
        parameters = {
            'scenario': self.scenario,
            'hours_per_period': self.hours_per_period,
            'periods': self.total_hours,
            'periods_per_week': self.periods_per_week,
            'weeks': self.time_horizon_weeks,
            'capture_and_flow_unit': 'kg per three-hour interval',
            'weekly_contract_unit': 'kg per week; same contract quantity in every representative week',
            'transport_timing': 'Same three-hour interval at source and destination',
            'source_export_rule': 'Each source weekly outflow does not exceed its capture in the same week',
            'transport_loss_fraction': 0.0,
            'initial_co2_inventory_kg': 0.0,
            'terminal_inventory_rule': 'Nonnegative and endogenous; no terminal-zero constraint',
            'co2_storage_cost_scope': 'Original model storage-cost scope retained',
            'co2_consumption_kg_per_kg_fuel': {
                technology: float(info['co2_consumption_ratio'])
                for technology, info in self.technologies.items() if 'co2_consumption_ratio' in info
            },
            'capture_cost_cny_per_ton': float(self.config['dac_parameters']['capture_cost_yuan_per_ton']),
            'capture_energy_kwh_per_ton': float(self.config['dac_parameters']['energy_kwh_per_ton_co2']),
            'dac_equipment_kg_co2e_per_kg_capture': float(self.carbon_params['raw_materials']['dac_equipment_embodied']),
            'pipeline_kg_co2e_per_kg_100km': float(self.carbon_params['transportation']['co2_pipeline_intensity']),
            'project_lifespan_years': self.economic_params['project_lifespan'],
            'discount_rate': self.economic_params['discount_rate'],
            'routes': [dict(source=source, destination=destination, **record)
                       for (source, destination), record in self.co2_route_parameters.items()],
            'ledger': {
                'dac_capture_cost': float(value(self.cost_expressions['dac_capture_cost'])),
                'dac_equipment': float(value(self.carbon_expressions['dac_equipment'])),
                'co2_pipeline_transport_cost': float(value(self.cost_expressions['co2_pipeline_transport_cost'])),
                'co2_pipeline_transport': float(value(self.carbon_expressions['co2_pipeline_transport'])),
            },
        }
        (output / 'co2_balance_parameters.json').write_text(json.dumps(parameters, ensure_ascii=False, indent=2), encoding='utf-8')
