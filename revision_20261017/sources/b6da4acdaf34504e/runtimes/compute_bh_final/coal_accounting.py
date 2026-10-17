import json
from pathlib import Path

import coptpy as cp
import pandas as pd


class CoalAccountingMixin:
    def _create_carbon_emission_expressions(self):
        super()._create_carbon_emission_expressions()
        if self.scenario not in ('CTL', 'CTL-BH'):
            return
        parameters = self.config['carbon_emission_parameters']['production_process']
        coal = cp.quicksum(self.coal_purchase_vars.values())
        yield_co2 = float(parameters['coal_co2_yield_kg_per_kg'])
        capture = float(parameters['co2_capture_efficiency'])
        grid = float(parameters['gasification_electricity_intensity'])
        coefficients = {
            'coal_mining': float(parameters['coal_mining_emission']),
            'coal_transport': float(parameters['coal_transport_emission']),
            'coal_gasification_direct': float(parameters['coal_gasification_direct_emission']),
            'coal_gasification_energy': float(parameters['coal_gasification_energy_kwh_per_kg']) * grid,
            'coal_co2_fugitive': yield_co2 * (1 - capture),
            'co2_capture_energy': yield_co2 * capture * float(parameters['co2_capture_energy_kwh_per_ton']) / 1000 * grid,
        }
        raw_change = cp.LinExpr(0)
        for field, coefficient in coefficients.items():
            after = coal * coefficient
            raw_change += after - self.carbon_expressions[field]
            self.carbon_expressions[field] = after
        synthesis = cp.quicksum(
            variable * float(self.config['technologies'][technology]['energy_consumption_kwh_per_kg_saf'])
            * (
                self.dynamic_carbon_intensity[location, period]
                if self.locations[location]['type'] in ('solar_plant', 'wind_farm')
                else float(self.config['carbon_emission_parameters']['renewable_energy']['grid_electricity_intensity'])
            )
            for (location, technology, period), variable in self.production_vars.items()
        )
        production_change = synthesis - self.carbon_expressions['saf_synthesis_energy'] - self.carbon_expressions['methanol_to_saf']
        self.carbon_expressions['saf_synthesis_energy'] = synthesis
        self.carbon_expressions['methanol_to_saf'] = cp.LinExpr(0)
        self.carbon_aggregates['raw_material_emissions'] += raw_change
        self.carbon_aggregates['production_emissions'] += production_change
        self.carbon_aggregates['total_emissions'] += raw_change + production_change
        self.carbon_aggregates['annual_emissions'] += (raw_change + production_change) * 52 / self.time_horizon_weeks
        self.coal_carbon_coefficients = coefficients

    def export_coal_accounting_audit(self, output_directory, value):
        assert self.scenario in ('CTL', 'CTL-BH'), self.scenario
        output = Path(output_directory)
        pd.DataFrame([
            {'location': location, 'week': week, 'value': float(value(variable))}
            for (location, week), variable in self.coal_purchase_vars.items()
        ]).to_csv(output / 'coal_purchases.csv', index=False)
        pd.DataFrame([
            {'location': location, 'period': period, 'value': float(value(variable))}
            for (location, period), variable in self.co2_inventory_vars.items()
        ]).to_csv(output / 'coal_co2_inventory.csv', index=False)
        metadata = {
            'accounting_mode': 'Actual coal procurement and one-step synthesis electricity',
            'coal_mass_scope': 'Sum of actual location-week coal purchases over all four represented weeks',
            'configured_coal_parameters': self.config['coal_parameters'],
            'co2_available_kg_per_kg_coal': float(self.coal_supply.co2_per_kg_coal),
            'purchase_cny_per_kg_coal': float(self.coal_supply.calculate_coal_purchase_cost(1.0)),
            'gasification_cny_per_kg_coal': float(self.coal_supply.calculate_gasification_energy_cost(1.0)),
            'carbon_coefficients_kg_co2e_per_kg_coal': self.coal_carbon_coefficients,
            'configured_production_process': self.config['carbon_emission_parameters']['production_process'],
            'synthesis_kwh_per_kg_saf': {
                technology: float(self.config['technologies'][technology]['energy_consumption_kwh_per_kg_saf'])
                for technology in self.technologies
            },
            'co2_consumption_kg_per_kg_saf': {
                technology: float(parameters['co2_consumption_ratio'])
                for technology, parameters in self.technologies.items()
            },
            'co2_supply_timing': 'Each actual location-week coal purchase releases its configured CO2 yield uniformly over that week of 56 three-hour intervals',
            'additional_mtj_electricity': 'The one-step pathway has no separate methanol-to-jet stage',
            'actual_coal_purchase_kg': sum(float(value(variable)) for variable in self.coal_purchase_vars.values()),
            'ledger': {field: float(value(self.carbon_expressions[field])) for field in [*self.coal_carbon_coefficients, 'saf_synthesis_energy', 'methanol_to_saf']},
        }
        (output / 'coal_accounting_parameters.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
