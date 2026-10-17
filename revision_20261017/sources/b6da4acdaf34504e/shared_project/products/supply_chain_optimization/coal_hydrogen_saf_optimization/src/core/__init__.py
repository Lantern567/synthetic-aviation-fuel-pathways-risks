"""Core optimizer exports."""

from .coal_hydrogen_optimization_model import CoalHydrogenSAFOptimizer

try:
    from .green_hydrogen_optimization_model import GreenHydrogenSupplyChainOptimizer
except ModuleNotFoundError:  # Optional dependency (Gurobi)
    GreenHydrogenSupplyChainOptimizer = None

__all__ = ["CoalHydrogenSAFOptimizer", "GreenHydrogenSupplyChainOptimizer"]

