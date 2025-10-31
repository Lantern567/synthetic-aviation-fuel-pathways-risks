"""
核心优化模型模块
"""

# ===== v4.0变更: 导出DAC版本优化器 =====
from .dac_hydrogen_optimization_model import DACHydrogenSAFOptimizer

# 向后兼容：保留旧名称导出（指向DAC版本）
GreenHydrogenSupplyChainOptimizer = DACHydrogenSAFOptimizer

__all__ = ['DACHydrogenSAFOptimizer', 'GreenHydrogenSupplyChainOptimizer']