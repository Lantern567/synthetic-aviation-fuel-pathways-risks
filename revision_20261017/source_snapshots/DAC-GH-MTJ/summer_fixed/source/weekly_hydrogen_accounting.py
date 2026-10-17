import json
from pathlib import Path

import coptpy as cp
import numpy as np
import pandas as pd


class WeeklyHydrogenAccountingMixin:
    def _weekly_hydrogen_route_parameters(self):
        if hasattr(self, 'h2_accounting_route_parameters'):
            return self.h2_accounting_route_parameters
        self.h2_accounting_route_parameters = {}
        for source, destination in self.hydrogen_pipeline_transport_vars:
            if source == destination:
                distance = 0.0
            elif self.scenario == 'GTL-GH':
                distance = float(self._get_hydrogen_transport_distance_with_clustering(source, destination))
            else:
                distance = float(self.hydrogen_distance_cache[source, destination])
            unit_cost = float(self._calculate_hydrogen_pipeline_cost_by_distance(distance))
            assert np.isfinite(distance) and distance >= 0, (source, destination, distance)
            assert np.isfinite(unit_cost) and unit_cost >= 0, (source, destination, unit_cost)
            self.h2_accounting_route_parameters[source, destination] = {
                'pipeline_distance_km': distance,
                'transport_cny_per_kg': unit_cost,
            }
        return self.h2_accounting_route_parameters

    def _create_cost_expressions(self):
        super()._create_cost_expressions()
        parameters = self._weekly_hydrogen_route_parameters()
        rate, years = self.economic_params['discount_rate'], self.economic_params['project_lifespan']
        present_value = years if rate == 0 else (1 - (1 + rate) ** (-years)) / rate
        expression = cp.quicksum(
            weekly * self.time_horizon_weeks * parameters[source, destination]['transport_cny_per_kg']
            for (source, destination), weekly in self.hydrogen_pipeline_transport_vars.items()
        ) * 52 / self.time_horizon_weeks * present_value
        change = expression - self.cost_expressions['hydrogen_pipeline_operation']
        self.cost_expressions['hydrogen_pipeline_operation'] = expression
        self.cost_aggregates['total_operation_cost'] += change
        self.cost_aggregates['total_cost_excluding_shortage'] += change

    def _create_carbon_emission_expressions(self):
        super()._create_carbon_emission_expressions()
        parameters = self._weekly_hydrogen_route_parameters()
        intensity = float(self.carbon_params['transportation']['h2_pipeline_intensity'])
        assert np.isfinite(intensity) and intensity >= 0, intensity
        expression = cp.quicksum(
            weekly * self.time_horizon_weeks
            * parameters[source, destination]['pipeline_distance_km'] / 100 * intensity
            for (source, destination), weekly in self.hydrogen_pipeline_transport_vars.items()
        )
        change = expression - self.carbon_expressions['h2_pipeline_transport']
        self.carbon_expressions['h2_pipeline_transport'] = expression
        self.carbon_expressions['h2_transport'] = expression + self.carbon_expressions['h2_truck_transport']
        self.carbon_aggregates['transport_emissions'] += change
        self.carbon_aggregates['total_emissions'] += change
        self.carbon_aggregates['annual_emissions'] += change * 52 / self.time_horizon_weeks

    def export_hydrogen_transport_audit(self, output_directory, value):
        output = Path(output_directory)
        assert output.is_dir(), output
        parameters = self._weekly_hydrogen_route_parameters()
        rows = []
        for (source, destination), weekly in self.hydrogen_pipeline_transport_vars.items():
            rows.append({
                'source': source, 'destination': destination,
                'weekly_contract_kg': float(value(weekly)),
                'representative_window_transport_kg': float(value(weekly)) * self.time_horizon_weeks,
                **parameters[source, destination],
            })
        columns = ['source', 'destination', 'weekly_contract_kg', 'representative_window_transport_kg',
                   'pipeline_distance_km', 'transport_cny_per_kg']
        pd.DataFrame(rows, columns=columns).to_csv(output / 'hydrogen_transport_accounting.csv', index=False)
        metadata = {
            'weeks': self.time_horizon_weeks,
            'periods_per_week': self.periods_per_week,
            'hours_per_period': self.hours_per_period,
            'contract_rule': 'Each representative week actual route flow equals its fixed weekly contract',
            'transport_loss_fraction': 0.0,
            'distance_scope': 'Hydrogen pipeline route distance used for both cost and transport carbon',
            'carbon_kg_co2e_per_kg_100km': float(self.carbon_params['transportation']['h2_pipeline_intensity']),
            'economic_parameters': self.economic_params,
            'cost_curve': self.config.get('costs', {}).get('hydrogen_pipeline_costs', {}).get('transport_cost_function', {}),
            'ledger': {
                'hydrogen_pipeline_operation': float(value(self.cost_expressions['hydrogen_pipeline_operation'])),
                'h2_pipeline_transport': float(value(self.carbon_expressions['h2_pipeline_transport'])),
            },
        }
        (output / 'hydrogen_transport_parameters.json').write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8'
        )
