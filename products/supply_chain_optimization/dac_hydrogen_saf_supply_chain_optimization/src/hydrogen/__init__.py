"""
氢气生产和运输优化模块
包含氢气聚类优化、CO2聚类优化、管道距离计算、运输可视化等功能
"""

import sys

# 提前导入numpy和pandas来加载NumPy兼容层
import numpy as np
import pandas as pd

from .hydrogen_clustering_optimizer import HydrogenClusteringOptimizer, ClusteringResult
from .hydrogen_pipeline_distance_calculator import HydrogenPipelineDistanceCalculator, ClusteredPipelineRoute

# 可视化模块导入（可选，允许失败）
try:
    from .hydrogen_transport_visualizer import HydrogenTransportVisualizer
    _has_visualizer = True
except ImportError as viz_err:
    print(f"WARNING: 氢气运输可视化器导入失败: {viz_err}", file=sys.stderr)
    print("WARNING: 可视化功能将不可用，但不影响优化计算", file=sys.stderr)
    HydrogenTransportVisualizer = None
    _has_visualizer = False

# DAC版本不需要CO2聚类优化器（工业点源聚类），已移除导入

__all__ = [
    'HydrogenClusteringOptimizer',
    'ClusteringResult',
    'HydrogenPipelineDistanceCalculator',
    'ClusteredPipelineRoute',
    'HydrogenTransportVisualizer'
]
