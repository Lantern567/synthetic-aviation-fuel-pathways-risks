import json
from pathlib import Path

import coptpy as cp
import numpy as np
import pandas as pd


class CcuCO2AccountingMixin:
    def _ccu_co2_route_parameters(self):
        if hasattr(self, 'ccu_co2_route_parameters'):
            return self.ccu_co2_route_parameters
        price = float(self.config.get('unified_costs', {}).get('co2_transport', {}).get('pipeline', {}).get('transport_cost_yuan_per_kg_km', .0001))
        if not np.isfinite(price) or price < 0:
            raise ValueError(f'Invalid CO2 pipeline unit cost: {price}')
        routes = {}
        for source, destination in self.co2_pipeline_transport_vars:
            if source == destination:
                distance = 0.0
            else:
                cached = self.co2_distance_cache[source, destination]
                distance = float(cached['total_distance_km'] if isinstance(cached, dict) else cached)
            if not np.isfinite(distance) or distance < 0:
                raise ValueError(f'Invalid CO2 pipeline route distance: {(source, destination, distance)}')
            routes[source, destination] = {'pipeline_distance_km': distance,
                                          'transport_cny_per_kg_km': price,
                                          'transport_cny_per_kg': price * distance}
        self.ccu_co2_route_parameters = routes
        return routes

    def _create_cost_expressions(self):
        super()._create_cost_expressions()
        if not self.scenario.startswith('CCU-'):
            return
        parameters = self._ccu_co2_route_parameters()
        rate, years = self.economic_params['discount_rate'], self.economic_params['project_lifespan']
        present_value = years if rate == 0 else (1 - (1 + rate) ** (-years)) / rate
        lifecycle_factor = 52 / self.time_horizon_weeks * present_value
        expression = cp.quicksum(
            weekly * self.time_horizon_weeks * parameters[source, destination]['transport_cny_per_kg']
            for (source, destination), weekly in self.co2_pipeline_transport_vars.items()
        ) * lifecycle_factor
        self.ccu_co2_original_cost_expression = self.cost_expressions['co2_pipeline_transport_cost']
        change = expression - self.ccu_co2_original_cost_expression
        self.cost_expressions['co2_pipeline_transport_cost'] = expression
        self.cost_aggregates['total_operation_cost'] += change
        self.cost_aggregates['total_cost_excluding_shortage'] += change
        represented_hours = self.total_hours * self.hours_per_period
        source_hours = self.periods_per_week * self.hours_per_period
        self.ccu_co2_original_storage_expression = self.cost_expressions['co2_storage_operation']
        storage_expression = self.ccu_co2_original_storage_expression * represented_hours / source_hours
        storage_change = storage_expression - self.ccu_co2_original_storage_expression
        self.cost_expressions['co2_storage_operation'] = storage_expression
        self.cost_aggregates['total_operation_cost'] += storage_change
        self.cost_aggregates['total_cost_excluding_shortage'] += storage_change

    def _create_carbon_emission_expressions(self):
        if not self.scenario.startswith('CCU-'):
            return super()._create_carbon_emission_expressions()
        parameters = self._ccu_co2_route_parameters()
        # 基类碳表达式读取数值距离；此处保留已核验缓存的真实路线。
        self.co2_distance_cache = {key: record['pipeline_distance_km'] for key, record in parameters.items()}
        super()._create_carbon_emission_expressions()
        intensity = float(self.carbon_params['transportation'].get('co2_pipeline_intensity', .01))
        if not np.isfinite(intensity) or intensity < 0:
            raise ValueError(f'Invalid CO2 pipeline carbon intensity: {intensity}')
        expression = cp.quicksum(
            weekly * self.time_horizon_weeks * parameters[source, destination]['pipeline_distance_km'] / 100 * intensity
            for (source, destination), weekly in self.co2_pipeline_transport_vars.items()
        )
        self.ccu_co2_original_carbon_expression = self.carbon_expressions['co2_pipeline_transport']
        change = expression - self.ccu_co2_original_carbon_expression
        self.carbon_expressions['co2_pipeline_transport'] = expression
        self.carbon_expressions['co2_transport'] = expression
        self.carbon_aggregates['transport_emissions'] += change
        self.carbon_aggregates['total_emissions'] += change
        self.carbon_aggregates['annual_emissions'] += change * 52 / self.time_horizon_weeks

    def export_ccu_co2_transport_audit(self, output_directory, value):
        if not self.scenario.startswith('CCU-'):
            return
        output = Path(output_directory)
        if not output.is_dir():
            raise NotADirectoryError(output)
        parameters = self._ccu_co2_route_parameters()
        rows = [{'source': source, 'destination': destination,
                 'weekly_contract_kg': float(value(weekly)),
                 'representative_window_transport_kg': float(value(weekly)) * self.time_horizon_weeks,
                 **parameters[source, destination]}
                for (source, destination), weekly in self.co2_pipeline_transport_vars.items()]
        columns = ['source', 'destination', 'weekly_contract_kg', 'representative_window_transport_kg',
                   'pipeline_distance_km', 'transport_cny_per_kg_km', 'transport_cny_per_kg']
        pd.DataFrame(rows, columns=columns).to_csv(output / 'ccu_co2_transport_accounting.csv', index=False)
        pd.DataFrame([{'location': location, 'period': period, 'value': float(value(stock))}
                      for (location, period), stock in self.co2_inventory_vars.items()],
                     columns=['location', 'period', 'value']).to_csv(output / 'ccu_co2_inventory.csv', index=False)
        metadata = {'scenario': self.scenario, 'weeks': self.time_horizon_weeks,
                    'periods_per_week': self.periods_per_week, 'hours_per_period': self.hours_per_period,
                    'quantity_basis': 'Each weekly CO2 supply contract is delivered once in every representative week',
                    'distance_scope': 'Existing CO2 pipeline route cache; self-supply has zero transport distance',
                    'transport_loss_fraction': 0.0,
                    'cost_cny_per_kg_km': float(self.config.get('unified_costs', {}).get('co2_transport', {}).get('pipeline', {}).get('transport_cost_yuan_per_kg_km', .0001)),
                    'carbon_kg_co2e_per_kg_100km': float(self.carbon_params['transportation'].get('co2_pipeline_intensity', .01)),
                    'economic_parameters': self.economic_params,
                    'storage': {'average_inventory_proxy': 'Half the sum of site-specific CO2 peak inventory variables',
                                'source_hours': self.periods_per_week * self.hours_per_period,
                                'represented_hours': self.total_hours * self.hours_per_period,
                                'factor': self.time_horizon_weeks,
                                'parameters': self.config.get('unified_costs', {}).get('co2_storage', {}),
                                'operation_cost_cny': float(value(self.cost_expressions['co2_storage_operation']))},
                    'ledger': {'co2_pipeline_transport_cost': float(value(self.cost_expressions['co2_pipeline_transport_cost'])),
                               'co2_pipeline_transport': float(value(self.carbon_expressions['co2_pipeline_transport'])),
                               'co2_storage_investment': float(value(self.cost_expressions['co2_storage_investment'])),
                               'co2_storage_operation': float(value(self.cost_expressions['co2_storage_operation']))}}
        (output / 'ccu_co2_transport_parameters.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
