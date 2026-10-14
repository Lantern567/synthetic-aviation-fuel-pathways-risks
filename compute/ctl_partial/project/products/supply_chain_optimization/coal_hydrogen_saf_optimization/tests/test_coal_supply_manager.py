import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
PROJECT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_DIR / "src"

for path in (PROJECT_ROOT, PROJECT_DIR, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from src.modules.coal_supply_manager import CoalSupplyManager, CoalCostBreakdown


class TestCoalSupplyManager(unittest.TestCase):
    def setUp(self) -> None:
        self.config = {
            "coal_parameters": {
                "coal_type": "bituminous",
                "carbon_content": 0.75,
                "co2_per_kg_coal": 2.44,
                "coal_price_yuan_per_ton": 525,
                "gasification_efficiency": 0.75,
                "gasification_energy_mj_per_kg": 8.0,
                "gasification_energy_cost_yuan_per_mj": 0.5,
                "coal_consumption_kg_per_kg_saf": 1.8,
                "base_co2_yield_kg_per_kg_saf": 3.5,
            }
        }
        self.manager = CoalSupplyManager(self.config)

    def test_co2_calculation(self) -> None:
        coal_mass = 1_000.0
        co2_output = self.manager.calculate_co2_from_coal(coal_mass)
        self.assertAlmostEqual(co2_output, 2_440.0, places=6)

    def test_coal_required_for_target_co2(self) -> None:
        target_co2 = 4_880.0
        coal_required = self.manager.calculate_coal_for_co2_demand(target_co2)
        self.assertAlmostEqual(coal_required, 2_000.0, places=6)

    def test_cost_breakdown(self) -> None:
        coal_mass = 1_000.0
        breakdown = self.manager.calculate_total_coal_cost(coal_mass)

        self.assertIsInstance(breakdown, CoalCostBreakdown)
        self.assertAlmostEqual(breakdown.purchase_cost, 525.0, places=6)
        self.assertAlmostEqual(breakdown.gasification_cost, 4_000.0, places=6)
        self.assertAlmostEqual(breakdown.total_cost, 4_525.0, places=6)

    def test_cost_per_kg_saf_uses_default_ratio(self) -> None:
        per_kg_cost = self.manager.calculate_cost_per_kg_saf()
        self.assertAlmostEqual(per_kg_cost.purchase_cost, 0.945, places=6)
        self.assertAlmostEqual(per_kg_cost.gasification_cost, 7.2, places=6)
        self.assertAlmostEqual(per_kg_cost.total_cost, 8.145, places=6)

    def test_overridden_ratio_applied(self) -> None:
        ratio = 2.0
        per_kg_cost = self.manager.calculate_cost_per_kg_saf(ratio)
        self.assertAlmostEqual(
            per_kg_cost.purchase_cost, ratio * 0.525, places=6
        )

    def test_negative_inputs_raise(self) -> None:
        with self.assertRaises(ValueError):
            self.manager.calculate_co2_from_coal(-1)
        with self.assertRaises(ValueError):
            self.manager.calculate_cost_per_kg_saf(0)

    def test_missing_parameters_raise(self) -> None:
        incomplete = {"coal_parameters": {"coal_type": "bituminous"}}
        with self.assertRaises(KeyError):
            CoalSupplyManager(incomplete)


if __name__ == "__main__":
    unittest.main()
