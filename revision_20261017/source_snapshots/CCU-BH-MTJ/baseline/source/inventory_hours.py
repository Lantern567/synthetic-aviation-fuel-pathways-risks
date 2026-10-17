import json
from pathlib import Path

import numpy as np


class InventoryHoursMixin:
    def _create_cost_expressions(self):
        super()._create_cost_expressions()
        hours = self.total_hours * self.hours_per_period
        assert hours == self.time_horizon_weeks * 168, (hours, self.time_horizon_weeks)
        self.inventory_cost_hour_parameters = {}
        for commodity, field in [('saf', 'storage_operation_cost'), ('h2', 'h2_storage_operation')]:
            if field not in self.cost_expressions:
                continue
            source_hours = self.periods_per_week * self.hours_per_period if commodity == 'h2' and self.scenario.startswith('CCU-') else self.total_hours
            before = self.cost_expressions[field]
            after = before * hours / source_hours
            change = after - before
            self.cost_expressions[field] = after
            self.cost_aggregates['total_operation_cost'] += change
            self.cost_aggregates['total_cost_excluding_shortage'] += change
            self.inventory_cost_hour_parameters[commodity] = {
                'field': field, 'source_hour_multiplier': source_hours,
                'represented_hours': hours, 'factor': hours / source_hours,
                'average_inventory_proxy': 'Half the sum of site-specific inventory capacity variables',
                'charged_location_scope': 'Hydrogen source locations' if commodity == 'h2' and self.scenario.startswith('CCU-') else 'All inventory locations represented by the original model cost expression',
                'source_expression': before, 'final_expression': after,
            }

    def export_inventory_cost_audit(self, output_directory, value):
        output = Path(output_directory)
        assert output.is_dir(), output
        storage = self.config.get('objective_coefficients', {}).get('storage', {})
        direct = storage.get('direct_costs', {})
        rent = float(direct.get('warehouse_rent_per_m3_hour', 0.01))
        density = float(direct.get('storage_density_kg_per_m3', 500))
        handling = float(direct.get('handling_cost_per_kg_hour', 0.001))
        assert np.isfinite(density) and density > 0, density
        hourly_rate = rent / density + handling
        assert np.isfinite(hourly_rate) and hourly_rate >= 0, hourly_rate
        unified = self.config.get('unified_costs', {}).get('storage', {})
        equipment = {
            'saf': float(unified.get('mtj_equipment_cost_yuan_per_kg') or storage.get('equipment_unit_cost_yuan_per_kg', 10)),
            'h2': float(unified.get('hydrogen_equipment_cost_yuan_per_kg') or storage.get('hydrogen_equipment_unit_cost_yuan_per_kg', 20)),
        }
        records = {}
        for commodity, record in self.inventory_cost_hour_parameters.items():
            records[commodity] = {
                key: item for key, item in record.items()
                if key not in ('source_expression', 'final_expression')
            }
            records[commodity].update(
                source_expression_cost_cny=float(value(record['source_expression'])),
                final_expression_cost_cny=float(value(record['final_expression'])),
                operation_cny_per_kg_hour=hourly_rate,
                equipment_cny_per_kg_capacity=equipment[commodity],
            )
        metadata = {
            'accounting_mode': 'Site peak capacity / 2 proxy over all represented physical hours',
            'applied_in_optimization': True, 'periods': self.total_hours,
            'hours_per_period': self.hours_per_period,
            'represented_hours': self.total_hours * self.hours_per_period,
            'periods_per_week': self.periods_per_week, 'weeks': self.time_horizon_weeks,
            'economic_parameters': self.economic_params,
            'direct_cost_parameters': {'warehouse_rent_per_m3_hour': rent,
                                       'storage_density_kg_per_m3': density,
                                       'handling_cost_per_kg_hour': handling},
            'records': records,
            'ledger': {field: float(value(self.cost_expressions[field]))
                       for field in ['storage_equipment_cost', 'storage_operation_cost',
                                     'h2_storage_investment', 'h2_storage_operation']
                       if field in self.cost_expressions},
        }
        (output / 'inventory_cost_parameters.json').write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8'
        )
