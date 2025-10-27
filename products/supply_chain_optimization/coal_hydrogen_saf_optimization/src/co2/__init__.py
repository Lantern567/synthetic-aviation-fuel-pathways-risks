"""
CO₂捕获与排放计算模块 (CO2 Capture and Emission Calculation Module)

本模块用于绿氢供应链优化项目，提供以下功能：
1. 从GIS数据计算各类设施的CO₂捕获量
2. 计算全生命周期碳排放

主要类：
- CO2CaptureCalculator: CO₂捕获量计算器
- CO2EmissionCalculator: CO₂排放计算器（待实现）

作者：Claude Code
创建日期：2025-10-13
版本：v1.0
"""

from .co2_capture_calculator import CO2CaptureCalculator

__all__ = ['CO2CaptureCalculator']

__version__ = '1.0.0'
