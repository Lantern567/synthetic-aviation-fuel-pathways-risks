import json
from pathlib import Path

import coptpy as cp
import numpy as np
import pandas as pd


class ByproductHydrogenMixin:
    def _byproduct_active_parameters(self):
        supply = self.config['green_hydrogen_supply']
        electricity = self.config['cost_parameters']['renewable_energy']
        carbon = self.config['carbon_emission_parameters']['renewable_energy']
        parameters = {
            'accounting_mode': 'component_cost',
            'feedstock_charge_scope': 'no_separate_feedstock_charge',
            'hydrogen_internal_cny_per_kg': float(
                self.config.get('unified_costs', {}).get('production', {}).get('hydrogen_internal_cost_yuan_per_kg', 0)
            ),
            'conditioning_kwh_per_kg': float(supply['production_energy_kwh_per_kg']),
            'grid_electricity_cny_per_kwh': float(electricity['grid_electricity_price_yuan_per_kwh']),
            'grid_electricity_kg_co2e_per_kwh': float(carbon['grid_electricity_intensity']),
            'upstream_kg_co2e_per_kg': {
                'byproduct_hydrogen_steel': float(supply['steel_upstream_carbon_intensity']),
                'byproduct_hydrogen_refinery': float(supply['refinery_upstream_carbon_intensity']),
            },
        }
        for key in ['hydrogen_internal_cny_per_kg', 'conditioning_kwh_per_kg',
                    'grid_electricity_cny_per_kwh', 'grid_electricity_kg_co2e_per_kwh']:
            assert np.isfinite(parameters[key]) and parameters[key] >= 0, (key, parameters[key])
        assert all(np.isfinite(value) and value >= 0 for value in parameters['upstream_kg_co2e_per_kg'].values())
        return parameters

    def _process_renewable_data(self, renewable_data):
        assert self.scenario.startswith('DAC-BH-'), self.scenario
        self.byproduct_available_kg_per_hour = {}
        required = {'plant_name', 'period', 'type', 'latitude', 'longitude', 'capacity_mw',
                    'power_output_mw', 'h2_available_kg_per_hour'}
        assert required <= set(renewable_data.columns), sorted(required - set(renewable_data.columns))
        for name, rows in renewable_data.groupby('plant_name', sort=False):
            rows = rows.sort_values('period')
            assert np.array_equal(rows.period.to_numpy(), np.arange(self.total_hours)), name
            assert rows.type.nunique() == 1, name
            first = rows.iloc[0]
            assert first['type'] in ('byproduct_hydrogen_steel', 'byproduct_hydrogen_refinery'), name
            supply = rows.h2_available_kg_per_hour.to_numpy(dtype=float)
            assert np.isfinite(supply).all() and (supply >= 0).all(), name
            # 旧文件名沿用发电字段；其数值由原模型定义为副产氢的 kg/h。
            assert np.allclose(supply, rows.power_output_mw, rtol=0, atol=1e-12), name
            self.byproduct_available_kg_per_hour[name] = supply
            self.locations[name] = {
                'type': first['type'], 'latitude': float(first.latitude),
                'longitude': float(first.longitude), 'capacity_mw': float(first.capacity_mw),
                'hourly_generation': supply.tolist(),
                'byproduct_supply_unit': 'kg H2 per hour',
            }
        assert self.byproduct_available_kg_per_hour
        self._add_airports_to_locations()

    def _add_byproduct_hydrogen_supply_constraints(self, location, hour):
        rate = float(self.byproduct_available_kg_per_hour[location][hour])
        assert np.isfinite(rate) and rate >= 0, (location, hour, rate)
        self.model.addConstr(
            self.hydrogen_production_vars[location, hour] <= rate * self.hours_per_period,
            name=f'byproduct_h2_supply_{location}_{hour}'
        )

    def _add_hydrogen_production_constraints(self):
        maximum = float(self.config['capacity_limits']['electrolyzer_max_capacity_kg_per_hour'])
        assert np.isfinite(maximum) and maximum > 0, maximum
        for location, capacity in self.electrolyzer_capacity_vars.items():
            assert location in self.byproduct_available_kg_per_hour, location
            self.model.addConstr(
                capacity <= maximum * self.electrolyzer_facility_vars[location],
                name=f'electrolyzer_capacity_{location}'
            )
            for period in range(self.total_hours):
                self.model.addConstr(
                    self.hydrogen_production_vars[location, period] <= capacity * self.hours_per_period,
                    name=f'h2_production_capacity_{location}_{period}'
                )

    def _create_cost_expressions(self):
        super()._create_cost_expressions()
        parameters = self._byproduct_active_parameters()
        rate, years = self.economic_params['discount_rate'], self.economic_params['project_lifespan']
        present_value = years if rate == 0 else (1 - (1 + rate) ** (-years)) / rate
        lifecycle_factor = 52 / self.time_horizon_weeks * present_value
        supply = cp.quicksum(self.hydrogen_production_vars.values())
        internal_cost = supply * parameters['hydrogen_internal_cny_per_kg'] * lifecycle_factor
        conditioning = supply * parameters['conditioning_kwh_per_kg']
        old_hydrogen_electricity_cny_per_kg = (
            self.costs['electrolysis_power_consumption']
            * self.costs['renewable_electricity_cost_yuan_per_mwh'] / 1000
        )
        hydrogen_electricity_change = (
            conditioning * parameters['grid_electricity_cny_per_kwh']
            - supply * old_hydrogen_electricity_cny_per_kg
        ) * lifecycle_factor
        synthesis_energy = float(self.config['technologies']['green_h2_co2_to_saf']['energy_consumption_kwh_per_kg_saf'])
        synthesis_at_source = cp.quicksum(
            production * synthesis_energy
            for (location, technology, period), production in self.production_vars.items()
            if location in self.byproduct_available_kg_per_hour
        )
        renewable_price = float(self.config['cost_parameters']['renewable_energy']['wind_power_price_yuan_per_kwh'])
        synthesis_electricity_change = synthesis_at_source * (
            parameters['grid_electricity_cny_per_kwh'] - renewable_price
        ) * lifecycle_factor
        electricity_change = hydrogen_electricity_change + synthesis_electricity_change
        change = internal_cost - self.cost_expressions['hydrogen_production_cost'] + electricity_change
        self.cost_expressions['hydrogen_production_cost'] = internal_cost
        self.cost_expressions['electricity_cost'] += electricity_change
        self.cost_aggregates['total_operation_cost'] += change
        self.cost_aggregates['total_cost_excluding_shortage'] += change
        self.byproduct_conditioning_electricity_kwh = conditioning
        self.byproduct_source_synthesis_electricity_kwh = synthesis_at_source

    def _calculate_dynamic_renewable_intensity(self, location, hour):
        if not self.scenario.startswith('DAC-BH-'):
            return super()._calculate_dynamic_renewable_intensity(location, hour)
        # 这些来源只供应副产氢，净化、合成及库存处理使用配置的市电碳强度。
        return self._byproduct_active_parameters()['grid_electricity_kg_co2e_per_kwh']

    def _create_carbon_emission_expressions(self):
        super()._create_carbon_emission_expressions()
        parameters = self._byproduct_active_parameters()
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
        # 副产氢来源的 kg/h 不构成可再生能源发电功率，DAC 用电继续单独平衡。
        super()._add_joint_electricity_constraints()
        self.electricity_scope = (
            'Byproduct hydrogen is limited by the archived kg/h source availability and selected '
            'conditioning capacity in every three-hour interval; it provides no renewable electricity. '
            'DAC grid purchases cover DAC only. Hydrogen component costs include selected '
            'conditioning equipment and grid electricity; conditioning and synthesis use grid '
            'electricity, and hydrogen carbon includes '
            'the configured industrial-source upstream allocation plus conditioning electricity.'
        )

    def export_byproduct_supply_audit(self, output_directory, value):
        output = Path(output_directory)
        assert output.is_dir(), output
        rows = [
            {'location': location, 'period': period, 'source_type': self.locations[location]['type'],
             'available_h2_kg': float(rate) * self.hours_per_period,
             'available_h2_kg_per_hour': float(rate)}
            for location, rates in self.byproduct_available_kg_per_hour.items()
            for period, rate in enumerate(rates)
        ]
        pd.DataFrame(rows).to_csv(output / 'byproduct_hydrogen_availability.csv', index=False)
        parameters = {
            **self._byproduct_active_parameters(),
            'source_unit': 'kg H2 per hour', 'hours_per_period': self.hours_per_period,
            'period_supply_unit': 'kg H2 per three-hour interval',
            'legacy_input_fields': {'power_output_mw': 'kg H2 per hour', 'capacity_mw': 'kg H2 per hour'},
            'conditioning_capacity_unit': 'kg H2 per hour',
            'hydrogen_ledger_energy_kwh_per_kg': self._byproduct_active_parameters()['conditioning_kwh_per_kg'],
            'hydrogen_ledger_electricity_cny_per_mwh': self._byproduct_active_parameters()['grid_electricity_cny_per_kwh'] * 1000,
            'hydrogen_internal_cny_per_kg': self._byproduct_active_parameters()['hydrogen_internal_cny_per_kg'],
            'hydrogen_internal_cost_source': 'unified_costs.production.hydrogen_internal_cost_yuan_per_kg; absent value is zero',
            'electrolysis_process_emissions_applied': False,
            'conditioning_capacity_capex_rule': 'Original source-type capital coefficient times selected kg/h capacity times configured equipment capacity factor',
            'source_equipment_capex_cny_per_kg_h': {
                location: float(self._get_electrolyzer_capex(location))
                for location in self.byproduct_available_kg_per_hour
            },
            'configured_green_hydrogen_supply': self.config['green_hydrogen_supply'],
            'configured_raw_materials': self.config['cost_parameters']['raw_materials'],
            'conditioning_electricity_kwh': float(value(self.byproduct_conditioning_electricity_kwh)),
            'source_synthesis_electricity_kwh': float(value(self.byproduct_source_synthesis_electricity_kwh)),
            'ledger': {
                'hydrogen_production_cost': float(value(self.cost_expressions['hydrogen_production_cost'])),
                'electricity_cost': float(value(self.cost_expressions['electricity_cost'])),
                'h2_production_carbon': float(value(self.carbon_expressions['h2_production'])),
            },
        }
        (output / 'byproduct_accounting_parameters.json').write_text(
            json.dumps(parameters, ensure_ascii=False, indent=2), encoding='utf-8'
        )
