import json
from collections import defaultdict
from pathlib import Path

import coptpy as cp
import numpy as np
import pandas as pd


class HistoricalByproductMixin:
    def _process_renewable_data(self, renewable_data):
        self.byproduct_available_kg_per_hour = {}
        for name, rows in renewable_data.groupby('plant_name', sort=False):
            rows = rows.sort_values('period')
            np.testing.assert_array_equal(rows.period, np.arange(self.total_hours))
            assert rows.type.nunique() == 1
            first = rows.iloc[0]
            assert first['type'] in ('byproduct_hydrogen_steel', 'byproduct_hydrogen_refinery')
            rates = rows.h2_available_kg_per_hour.to_numpy(dtype=float)
            assert np.isfinite(rates).all() and (rates >= 0).all()
            np.testing.assert_allclose(rates, rows.power_output_mw, rtol=0, atol=1e-12)
            self.byproduct_available_kg_per_hour[name] = rates
            self.locations[name] = {
                'type': first['type'], 'latitude': float(first.latitude),
                'longitude': float(first.longitude), 'capacity_mw': float(first.capacity_mw),
                'hourly_generation': rates.tolist(), 'byproduct_supply_unit': 'kg H2/hour',
            }
        assert len(self.byproduct_available_kg_per_hour) == 64
        self._add_airports_to_locations()
        if self.scenario == 'GTL-BH':
            self._add_lng_terminals_to_locations()
            self._add_ng_pipelines_to_locations()

    def _add_hydrogen_production_constraints(self):
        maximum = float(self.config['capacity_limits']['electrolyzer_max_capacity_kg_per_hour'])
        for location, capacity in self.electrolyzer_capacity_vars.items():
            assert location in self.byproduct_available_kg_per_hour, location
            rates = self.byproduct_available_kg_per_hour[location]
            limit = min(maximum, float(rates.max()))
            self.model.addConstr(capacity <= limit * self.electrolyzer_facility_vars[location],
                                 name=f'electrolyzer_capacity_{location}')
            for period, rate in enumerate(rates):
                production = self.hydrogen_production_vars[location, period]
                self.model.addConstr(production <= capacity * self.hours_per_period,
                                     name=f'h2_production_capacity_{location}_{period}')
                self.model.addConstr(production <= rate * self.hours_per_period,
                                     name=f'byproduct_h2_available_{location}_{period}')

    def _add_byproduct_hydrogen_supply_constraints(self, location, hour):
        self.model.addConstr(
            self.hydrogen_production_vars[location, hour]
            <= float(self.byproduct_available_kg_per_hour[location][hour]) * self.hours_per_period,
            name=f'byproduct_h2_supply_{location}_{hour}'
        )

    def _calculate_dynamic_renewable_intensity(self, location, hour):
        assert self.locations[location]['type'] not in ('solar_plant', 'wind_farm'), location
        return float(self.config['byproduct_accounting']['grid_electricity_kg_co2e_per_kwh'])

    def _create_cost_expressions(self):
        super()._create_cost_expressions()
        parameters = self.config['byproduct_accounting']
        rate, years = self.economic_params['discount_rate'], self.economic_params['project_lifespan']
        present_value = years if rate == 0 else (1 - (1 + rate) ** (-years)) / rate
        lifecycle = 52 / self.time_horizon_weeks * present_value
        supply = cp.quicksum(self.hydrogen_production_vars.values())
        if self.scenario.startswith('CCU-'):
            previous_electricity = (
                self.config['green_hydrogen_supply']['production_energy_kwh_per_kg']
                * self.config['cost_parameters']['renewable_energy']['grid_electricity_price_yuan_per_kwh']
            )
        else:
            previous_electricity = self.costs['electrolysis_power_consumption'] * self.costs['renewable_electricity_cost_yuan_per_mwh'] / 1000
        final_electricity = parameters['conditioning_kwh_per_kg'] * parameters['grid_electricity_cny_per_kwh']
        electricity_change = supply * (final_electricity - previous_electricity) * lifecycle
        internal = float(self.config.get('unified_costs', {}).get('production', {}).get('hydrogen_internal_cost_yuan_per_kg', 0))
        internal_cost = supply * internal * lifecycle
        change = electricity_change + internal_cost - self.cost_expressions['hydrogen_production_cost']
        self.cost_expressions['electricity_cost'] += electricity_change
        self.cost_expressions['hydrogen_production_cost'] = internal_cost
        self.cost_aggregates['total_operation_cost'] += change
        self.cost_aggregates['total_cost_excluding_shortage'] += change
        self.byproduct_conditioning_electricity_kwh = supply * parameters['conditioning_kwh_per_kg']

    def _create_carbon_emission_expressions(self):
        super()._create_carbon_emission_expressions()
        parameters = self.config['byproduct_accounting']
        expression = cp.quicksum(
            production * (
                parameters['upstream_kg_co2e_per_kg'][self.locations[location]['type']]
                + parameters['conditioning_kwh_per_kg'] * parameters['grid_electricity_kg_co2e_per_kwh']
            )
            for (location, period), production in self.hydrogen_production_vars.items()
        )
        change = expression - self.carbon_expressions['h2_production']
        self.carbon_expressions['h2_production'] = expression
        self.carbon_aggregates['production_emissions'] += change
        self.carbon_aggregates['total_emissions'] += change
        self.carbon_aggregates['annual_emissions'] += change * 52 / self.time_horizon_weeks

    def _add_joint_electricity_constraints(self):
        # 工业副产氢数据只定义 kg/h 供给；其净化与当地合成使用市电。
        if self.scenario == 'GTL-BH':
            production = defaultdict(list)
            for (location, technology, period), variable in self.production_vars.items():
                production[location, period].append(variable)
            energy = float(self.config['carbon_emission_parameters']['production_process']['mtj_process_energy']) / 1e6
            for (location, period), grid in self.mtj_grid_electricity_vars.items():
                renewable = self.mtj_renewable_electricity_vars[location, period]
                self.model.addConstr(renewable == 0, name=f'byproduct_no_renewable_power_{location}_{period}')
                self.model.addConstr(grid == cp.quicksum(production[location, period]) * energy,
                                     name=f'byproduct_mtj_grid_balance_{location}_{period}')
        self.electricity_scope = (
            'Industrial byproduct supply is measured in kg H2/hour, with each interval limited '
            'by the selected conditioning capacity and the actual three-hour source availability. '
            'Conditioning and synthesis use grid electricity; no renewable power is assigned to industrial sources.'
        )

    def export_byproduct_supply_audit(self, output_directory, value):
        output = Path(output_directory)
        rows = [
            {'location': location, 'period': period, 'source_type': self.locations[location]['type'],
             'available_h2_kg': float(rate) * self.hours_per_period,
             'available_h2_kg_per_hour': float(rate)}
            for location, rates in self.byproduct_available_kg_per_hour.items()
            for period, rate in enumerate(rates)
        ]
        pd.DataFrame(rows).to_csv(output / 'byproduct_hydrogen_availability.csv', index=False)
        parameters = dict(self.config['byproduct_accounting'])
        parameters.update(
            source_unit='kg H2/hour', hours_per_period=self.hours_per_period,
            hydrogen_internal_cny_per_kg=float(self.config.get('unified_costs', {}).get('production', {}).get('hydrogen_internal_cost_yuan_per_kg', 0)),
            conditioning_electricity_kwh=float(value(self.byproduct_conditioning_electricity_kwh)),
            source_equipment_capex_cny_per_kg_h={name: float(self._get_electrolyzer_capex(name)) for name in self.byproduct_available_kg_per_hour},
            hydrogen_ledger_energy_kwh_per_kg=self.config['byproduct_accounting']['conditioning_kwh_per_kg'],
            hydrogen_ledger_electricity_cny_per_mwh=self.config['byproduct_accounting']['grid_electricity_cny_per_kwh'] * 1000,
            economic_parameters=self.economic_params,
            ledger={
                'hydrogen_production_cost': float(value(self.cost_expressions['hydrogen_production_cost'])),
                'electricity_cost': float(value(self.cost_expressions['electricity_cost'])),
                'h2_production_carbon': float(value(self.carbon_expressions['h2_production'])),
            },
        )
        (output / 'byproduct_accounting_parameters.json').write_text(json.dumps(parameters, ensure_ascii=False, indent=2), encoding='utf-8')
