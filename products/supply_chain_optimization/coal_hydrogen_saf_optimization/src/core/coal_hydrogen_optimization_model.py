"""
Coal + green hydrogen two-step SAF supply chain optimizer (simplified MILP).

This variant removes the CO₂ capture logistics present in the green hydrogen
baseline and derives CO₂ directly from coal gasification via
``CoalSupplyManager``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence

from ..modules.coal_supply_manager import CoalSupplyManager

try:  # pragma: no cover - optional dependency
    import gurobipy as gp
    from gurobipy import GRB
except ImportError:  # pragma: no cover
    gp = None
    GRB = None


@dataclass
class OptimizationResult:
    objective_value: float
    coal_purchase: List[float]
    saf_production: List[float]
    co2_inventory: List[float]
    status: int


class CoalHydrogenSAFOptimizer:
    """
    Minimal optimizer capturing the coal-based SAF route requirements.

    Parameters
    ----------
    config:
        Parsed configuration dictionary (matching CoalHydrogenSAFOptimizer_config.yaml).
    """

    def __init__(self, config: Mapping[str, Any]):
        self.config = dict(config)
        self.coal_supply = CoalSupplyManager(self.config)
        self.model: Optional[gp.Model] = None
        self._coal_purchase = None
        self._saf_production = None
        self._co2_inventory = None
        self._demand_profile: Optional[List[float]] = None

    def build_model(self, demand_profile: Sequence[float]) -> None:
        """
        Construct a reduced MILP focusing on coal procurement decisions.

        The model minimises coal purchase + gasification energy cost subject to:
        - Meeting SAF demand (in kg) each time step.
        - Balancing CO₂ inventory derived from coal gasification.
        """
        if gp is None or GRB is None:  # pragma: no cover - runtime guard
            raise ImportError(
                "gurobipy is required to build the optimization model. "
                "Install Gurobi and ensure a valid license is available."
            )

        hours = list(range(len(demand_profile)))
        model = gp.Model("coal_hydrogen_saf")
        model.Params.OutputFlag = 0

        coal_purchase = model.addVars(hours, lb=0.0, name="coal_purchase")
        saf_production = model.addVars(hours, lb=0.0, name="saf_production")
        co2_inventory = model.addVars(hours, lb=0.0, name="co2_inventory")

        co2_per_kg_coal = self.coal_supply.co2_per_kg_coal
        co2_per_kg_saf = self.coal_supply.base_co2_yield_kg_per_kg_saf

        operational = self.config.get("operational_parameters", {})
        initial_inventory = float(operational.get("initial_co2_inventory_kg", 0.0))
        inventory_target = float(operational.get("final_co2_inventory_target_kg", 0.0))

        for idx, demand in enumerate(demand_profile):
            demand_value = float(demand)
            if demand_value < 0:
                raise ValueError("Demand profile values must be non-negative.")

            production_expr = saf_production[idx]
            purchase_expr = coal_purchase[idx]
            inventory_expr = co2_inventory[idx]

            if idx == 0:
                model.addConstr(
                    inventory_expr
                    == initial_inventory
                    + purchase_expr * co2_per_kg_coal
                    - production_expr * co2_per_kg_saf,
                    name=f"inventory_balance_{idx}",
                )
            else:
                model.addConstr(
                    inventory_expr
                    == co2_inventory[idx - 1]
                    + purchase_expr * co2_per_kg_coal
                    - production_expr * co2_per_kg_saf,
                    name=f"inventory_balance_{idx}",
                )

            model.addConstr(
                production_expr >= demand_value, name=f"saf_demand_{idx}"
            )

        if hours:
            model.addConstr(
                co2_inventory[hours[-1]] >= inventory_target, name="final_inventory"
            )

        price = self.coal_supply.coal_price_yuan_per_kg
        gas_energy_per_kg = self.coal_supply.gasification_energy_mj_per_kg
        gas_energy_cost = self.coal_supply.gasification_energy_cost_yuan_per_mj

        objective = gp.quicksum(
            coal_purchase[h] * (price + gas_energy_per_kg * gas_energy_cost)
            for h in hours
        )
        model.setObjective(objective, GRB.MINIMIZE)

        self.model = model
        self._coal_purchase = coal_purchase
        self._saf_production = saf_production
        self._co2_inventory = co2_inventory
        self._demand_profile = list(demand_profile)

    def solve(self, time_limit: Optional[int] = None) -> OptimizationResult:
        """Optimize the model and return structured results."""
        if self.model is None:
            raise RuntimeError("Model has not been built. Call build_model first.")

        if time_limit is not None:
            self.model.Params.TimeLimit = int(time_limit)

        self.model.optimize()

        status = self.model.Status
        objective_value = float(self.model.ObjVal) if status == GRB.OPTIMAL else float(
            "nan"
        )

        coal_values = self._extract_values(self._coal_purchase)
        saf_values = self._extract_values(self._saf_production)
        inventory_values = self._extract_values(self._co2_inventory)

        return OptimizationResult(
            objective_value=objective_value,
            coal_purchase=coal_values,
            saf_production=saf_values,
            co2_inventory=inventory_values,
            status=status,
        )

    @staticmethod
    def _extract_values(
        var_container: Optional[gp.tupledict],
    ) -> List[float]:  # pragma: no cover - linear extraction
        if var_container is None:
            return []
        return [float(var_container[key].X) for key in sorted(var_container.keys())]

    def compute_cost_per_kg_saf(self) -> float:
        """
        Helper using ``CoalSupplyManager`` to provide marginal coal cost for SAF.
        """
        per_kg = self.coal_supply.calculate_cost_per_kg_saf()
        return per_kg.total_cost

    def summarize_parameters(self) -> Dict[str, Any]:
        """Return a snapshot of the parameters controlling coal supply."""
        return self.coal_supply.as_dict()
