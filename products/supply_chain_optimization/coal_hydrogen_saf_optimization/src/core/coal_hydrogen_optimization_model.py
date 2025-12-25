"""
煤炭+绿氢制SAF供应链优化模型
基于Gurobi求解器的混合整数线性规划模型
工艺路线：煤炭气化产生CO₂ + 绿氢 → 甲醇 → SAF (两步法)
核心变更：CO₂来源从捕获改为煤炭气化，简化CO₂运输物流
包含时间尺度匹配：生产(1小时) vs 需求(1周)
集成OSM真实路网数据进行距离计算和路径规划
"""

# ============================================================================
# CRITICAL: 必须在导入gurobipy之前设置Gurobi许可证路径
# ============================================================================
import os
# 强制使用正确的许可证文件路径（无论环境变量如何设置）
os.environ['GRB_LICENSE_FILE'] = '/home/ljt/gurobi.lic'

import gurobipy as gp
from gurobipy import GRB
import pandas as pd
import numpy as np
import logging
import gc  # 用于显式垃圾回收，释放大数据对象内存
import psutil  # 用于监控内存使用情况
import time
from typing import Dict, List, Tuple, Optional
import json
import re
import traceback
import yaml
from datetime import datetime
from collections import defaultdict
from math import radians, sin, cos, sqrt, atan2
from multiprocessing import Pool, cpu_count
from functools import partial
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
try:
    from shared.utils.log_preserver import mount_file_logging
    # 移除对外部成本分析引擎的依赖，直接在优化模型内部计算成本
    create_cost_analyzer = None
except ModuleNotFoundError:
    import sys
    # 动态加入项目根目录到sys.path后重试
    current_file = os.path.abspath(__file__)
    # core/green_hydrogen_optimization_model.py -> core/ -> src/ -> green_hydrogen_supply_chain_optimization/ -> supply_chain_optimization/ -> products/ -> 项目根
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))))
    if project_root not in sys.path:
        sys.path.append(project_root)
    from shared.utils.log_preserver import mount_file_logging
    # 移除对外部成本分析引擎的依赖，直接在优化模型内部计算成本
    create_cost_analyzer = None

# 导入GraphHopper路径规划模块 - 必须可用
try:
    # 尝试相对导入（当作为包使用时）
    try:
        from ..routing.graphhopper_routing_engine import GraphHopperRoutingEngine, GraphHopperDistanceCalculator, DistanceCalculator
    except ImportError:
        from routing.graphhopper_routing_engine import GraphHopperRoutingEngine, GraphHopperDistanceCalculator, DistanceCalculator
except ImportError:
    # 当直接运行时，添加src目录到路径
    import sys
    current_file = os.path.abspath(__file__)
    # core/green_hydrogen_optimization_model.py -> core/ -> src/
    src_dir = os.path.dirname(os.path.dirname(current_file))
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
    try:
        from routing.graphhopper_routing_engine import GraphHopperRoutingEngine, GraphHopperDistanceCalculator, DistanceCalculator
    except ImportError as e:
        raise ImportError(f"GraphHopper路径规划模块不可用，必须安装相关依赖: {e}. 请运行: pip install requests")

try:
    try:
        from ..hydrogen.hydrogen_pipeline_distance_calculator import HydrogenPipelineDistanceCalculator, ClusteredPipelineRoute
        from ..cache.pipeline_route_types import PipelineRouteNotFoundError
    except ImportError:
        from hydrogen.hydrogen_pipeline_distance_calculator import HydrogenPipelineDistanceCalculator, ClusteredPipelineRoute
        from cache.pipeline_route_types import PipelineRouteNotFoundError
except ImportError:
    # 确保src目录在路径中
    import sys
    current_file = os.path.abspath(__file__)
    src_dir = os.path.dirname(os.path.dirname(current_file))
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
    try:
        from hydrogen.hydrogen_pipeline_distance_calculator import HydrogenPipelineDistanceCalculator, ClusteredPipelineRoute
        from cache.pipeline_route_types import PipelineRouteNotFoundError
    except ImportError as e:
        # logger还未定义，暂时使用print
        print(f"警告：氢气管道距离计算器模块不可用: {e}")
        HydrogenPipelineDistanceCalculator = None
        ClusteredPipelineRoute = None
        PipelineRouteNotFoundError = None

try:
    try:
        from ..hydrogen.hydrogen_clustering_optimizer import HydrogenClusteringOptimizer, ClusteringResult
    except ImportError:
        from hydrogen.hydrogen_clustering_optimizer import HydrogenClusteringOptimizer, ClusteringResult
except ImportError:
    # 确保src目录在路径中
    import sys
    current_file = os.path.abspath(__file__)
    src_dir = os.path.dirname(os.path.dirname(current_file))
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
    try:
        from hydrogen.hydrogen_clustering_optimizer import HydrogenClusteringOptimizer, ClusteringResult
    except ImportError as e:
        # logger还未定义，暂时使用print
        print(f"警告：氢气聚类优化器模块不可用: {e}")
        HydrogenClusteringOptimizer = None
        ClusteringResult = None

# 导入CO2聚类优化器
try:
    try:
        from ..hydrogen.co2_clustering_optimizer import CO2ClusteringOptimizer, CO2ClusteringResult
    except ImportError:
        from hydrogen.co2_clustering_optimizer import CO2ClusteringOptimizer, CO2ClusteringResult
except ImportError:
    # 确保src目录在路径中
    import sys
    current_file = os.path.abspath(__file__)
    src_dir = os.path.dirname(os.path.dirname(current_file))
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
    try:
        from hydrogen.co2_clustering_optimizer import CO2ClusteringOptimizer, CO2ClusteringResult
    except ImportError as e:
        # logger还未定义，暂时使用print
        print(f"警告：CO2聚类优化器模块不可用: {e}")
        CO2ClusteringOptimizer = None
        CO2ClusteringResult = None

# 导入煤炭供应管理器（v3.0新增）
try:
    try:
        from ..modules.coal_supply_manager import CoalSupplyManager
    except ImportError:
        from modules.coal_supply_manager import CoalSupplyManager
except ImportError:
    # 确保src目录在路径中
    import sys
    current_file = os.path.abspath(__file__)
    src_dir = os.path.dirname(os.path.dirname(current_file))
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
    try:
        from modules.coal_supply_manager import CoalSupplyManager
    except ImportError as e:
        # logger还未定义，暂时使用print
        print(f"警告：煤炭供应管理器模块不可用: {e}")
        CoalSupplyManager = None

# 导入超图优化器（新增）
try:
    # 首先尝试从共享模块导入
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
    sys.path.insert(0, project_root)
    from shared.optimizers.super_graph_optimizer import SuperGraphOptimizer, SuperGraphConfig
    from shared.types.pipeline_route_types import PipelineRouteNotFoundError as SharedPipelineRouteNotFoundError
    SUPER_GRAPH_AVAILABLE = True
except ImportError as e:
    print(f"警告：超图优化器模块不可用: {e}")
    SuperGraphOptimizer = None
    SuperGraphConfig = None
    SharedPipelineRouteNotFoundError = None
    SUPER_GRAPH_AVAILABLE = False


# 导入约束诊断工具
try:
    try:
        from ..diagnose_constraints import ConstraintDiagnostic
    except ImportError:
        from diagnose_constraints import ConstraintDiagnostic
except ImportError:
    # 确保src目录在路径中
    import sys
    current_file = os.path.abspath(__file__)
    src_dir = os.path.dirname(os.path.dirname(current_file))
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
    try:
        from diagnose_constraints import ConstraintDiagnostic
    except ImportError as e:
        # logger还未定义，暂时使用print
        print(f"警告：约束诊断工具不可用: {e}")
        ConstraintDiagnostic = None

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 确保至少有一个控制台处理器输出日志
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    logger.setLevel(logging.INFO)

def calculate_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    计算两点间的Haversine距离（公里）
    
    Args:
        lat1, lon1: 第一个点的纬度经度
        lat2, lon2: 第二个点的纬度经度
        
    Returns:
        float: 距离（公里）
    """
    from math import radians, sin, cos, sqrt, atan2
    
    # 转换为弧度
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    # Haversine公式
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    
    # 地球半径(公里)
    R = 6371
    distance = R * c
    
    return distance

def is_within_beijing_range(lat: float, lon: float, max_distance_km: float = 500) -> bool:
    """
    检查坐标是否在北京指定范围内
    
    Args:
        lat, lon: 检查点的纬度经度
        max_distance_km: 最大距离（公里），默认300公里
        
    Returns:
        bool: 是否在范围内
    """
    # 北京市中心坐标（天安门）
    beijing_lat = 39.9042
    beijing_lon = 116.4074
    
    distance = calculate_distance_km(lat, lon, beijing_lat, beijing_lon)
    return distance <= max_distance_km

# ==================== 并行计算辅助函数 ====================

def _process_plant_data_worker(args):
    """并行处理单个电站数据的worker函数

    Args:
        args: (plant_name, plant_data, total_hours) 元组

    Returns:
        tuple: (plant_name, location_dict) 或 None（如果数据不足）
    """
    plant_name, plant_data, total_hours = args

    # 处理数据不足的情况：循环扩展
    if len(plant_data) > 0:
        if len(plant_data) < total_hours:
            # 数据不足时循环重复扩展
            logger.warning(
                f"电站 {plant_name} 数据不足 "
                f"({len(plant_data)}小时 < {total_hours}小时)，将循环重复扩展"
            )
            num_repeats = (total_hours // len(plant_data)) + 1
            plant_data_extended = pd.concat([plant_data] * num_repeats, ignore_index=True)
            hourly_data = plant_data_extended.head(total_hours)
        else:
            hourly_data = plant_data.head(total_hours)

        # 确定电站类型
        plant_type = hourly_data.iloc[0]['type'] if 'type' in hourly_data.columns else 'solar_plant'

        # 🔧 类型名称标准化修正：确保与配置文件中的suitable_locations一致
        if plant_type == 'solar_farm':
            plant_type = 'solar_plant'

        location_dict = {
            'type': plant_type,
            'latitude': hourly_data.iloc[0].get('latitude', 30.0),
            'longitude': hourly_data.iloc[0].get('longitude', 104.0),
            'capacity_mw': hourly_data.iloc[0]['capacity_mw'] if 'capacity_mw' in hourly_data.columns else hourly_data.iloc[0]['power_output_mw'],
            'hourly_generation': hourly_data['power_output_mw'].tolist(),
        }

        return (plant_name, location_dict)
    else:
        return None


def _filter_renewable_plant_worker(args):
    """并行过滤单个可再生能源电站的worker函数

    Args:
        args: (plant_name, plant_data, max_distance_km) 元组

    Returns:
        pd.DataFrame or None: 过滤后的电站数据
    """
    plant_name, plant_data, max_distance_km = args

    if len(plant_data) > 0:
        # 获取电站坐标（使用第一行数据）
        plant_lat = plant_data.iloc[0].get('latitude', 30.0)
        plant_lon = plant_data.iloc[0].get('longitude', 104.0)

        # 检查坐标是否在北京指定范围内
        if is_within_beijing_range(plant_lat, plant_lon, max_distance_km):
            return plant_data

    return None


def _process_airport_data_worker(args):
    """并行处理单个机场数据的worker函数

    Args:
        args: (airport_name, airport_df) 元组

    Returns:
        tuple: (airport_name, airport_dict)
    """
    airport_name, airport_df = args

    # 排序确保周数据顺序正确
    airport_df = airport_df.sort_values('week_number')

    # 提取52周的燃油需求序列
    weekly_series = airport_df['weekly_total_fuel_kg_total'].tolist()

    # 获取机场地理位置（使用第一行数据）
    first_row = airport_df.iloc[0]
    latitude = first_row['departure_airport_latitude']
    longitude = first_row['departure_airport_longitude']

    # 计算统计信息
    total_flights = airport_df['total_flights'].sum()
    avg_weekly_demand = np.mean(weekly_series)
    max_weekly_demand = np.max(weekly_series)
    total_annual_demand = np.sum(weekly_series)

    airport_dict = {
        'latitude': latitude,
        'longitude': longitude,
        'weekly_demand_series': weekly_series,
        'avg_weekly_demand_kg': avg_weekly_demand,
        'max_weekly_demand_kg': max_weekly_demand,
        'total_annual_demand_kg': total_annual_demand,
        'flight_count': total_flights
    }

    return (airport_name, airport_dict)


def _calculate_distance_worker(args):
    """并行计算单对位置间距离的worker函数

    Args:
        args: (routing_engine, locations, loc1, loc2) 元组

    Returns:
        tuple: ((loc1, loc2), distance_km)
    """
    routing_engine, locations, loc1, loc2 = args

    # 辅助函数：从locations中获取位置坐标
    def get_location_coords(loc_name):
        """从locations中获取位置坐标（v3.0: 仅使用locations）"""
        if loc_name in locations:
            return locations[loc_name]['latitude'], locations[loc_name]['longitude']
        else:
            raise KeyError(f"位置 '{loc_name}' 不在 locations 中")

    try:
        # 获取两个位置的坐标
        loc1_lat, loc1_lon = get_location_coords(loc1)
        loc2_lat, loc2_lon = get_location_coords(loc2)

        # 使用GraphHopper路径规划计算真实距离
        result = routing_engine.calculate_route_distance(
            loc1_lat, loc1_lon, loc2_lat, loc2_lon, vehicle="truck", include_route_geometry=False
        )
        distance_km = result.get('distance_km', 0)

        # 如果路径规划失败，使用直线距离
        if not result.get('route_found', False):
            distance_km = calculate_distance_km(loc1_lat, loc1_lon, loc2_lat, loc2_lon)

        return ((loc1, loc2), max(distance_km, 5))  # 最小距离5km
    except Exception as e:
        # 出错时返回一个大值
        logger.warning(f"距离计算失败 {loc1} -> {loc2}: {e}, 使用默认值1000km")
        return ((loc1, loc2), 1000.0)


def get_project_base_dir():
    """
    获取项目根目录的绝对路径
    从当前文件位置向上找到项目根目录

    路径结构:
    project_root/products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/src/core/green_hydrogen_optimization_model.py
    需要向上6级目录到达项目根目录

    Returns:
        str: 项目根目录路径
    """
    # 当前文件的绝对路径
    current_file = os.path.abspath(__file__)
    # 向上6级目录: core -> src -> green_hydrogen_supply_chain_optimization -> supply_chain_optimization -> products -> project_root
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))))
    return project_root


# 在模块加载时挂载日志文件输出（仅作用于logging，不捕获print）
try:
    _base_dir = get_project_base_dir()
    _log_dir = os.path.join(
        _base_dir,
        "products",
        "supply_chain_optimization",
        "coal_hydrogen_saf_optimization",  # 修正路径：coal_hydrogen_saf_optimization
        "results",
        "logs",
    )
    mount_file_logging(_log_dir, filename_prefix="coal_h2_saf_supply_chain")  # 修正前缀
except Exception as e:
    # 如果文件日志挂载失败，输出警告但不中断程序
    print(f"警告：文件日志挂载失败: {e}")
    print("将继续使用控制台日志")

class CoalHydrogenSAFOptimizer:
    """
    煤炭+绿氢制SAF供应链优化器 (v3.0)

    基于Gurobi求解器的混合整数线性规划(MILP)模型,优化煤炭气化CO₂和绿氢制SAF的供应链网络。

    工艺路线:
        煤炭气化产生CO₂ + 绿氢 → 甲醇 → SAF (两步法)
        - 煤炭气化: 煤炭 → CO₂ (本地生成，无需运输)
        - Step 1: E-CRM电化学还原(H₂ + CO₂ → 甲醇)
        - Step 2: MTJ甲醇转化(甲醇 → SAF)

    核心变更(相对v2.0):
        - ✅ CO₂来源: 煤炭气化 (替代CCS捕获)
        - ✅ CO₂运输: 本地直接使用 (删除管道/罐车运输)
        - ✅ 决策变量: 减少约94% (600万 → 35万)
        - ✅ 约束条件: 减少约99.7% (580万 → 2万)
        - ✅ 求解时间: 减少约75% (30-60分钟 → 5-15分钟)

    主要功能:
        - 绿氢生产: 风电/光伏电解水制氢
        - 煤炭供应: 市场采购+气化产生CO₂ (新增v3.0)
        - 运输优化: 管道+罐车双模式运输(仅H₂，CO₂本地使用)
        - 时间尺度匹配: 生产调度(1小时) vs 需求计划(1周)
        - 设施选址: 甲醇厂和SAF厂选址优化
        - 碳排放追踪: 全生命周期碳强度计算(约60 gCO₂e/MJ)

    决策变量 (v3.1一步法):
        - saf_production_vars: SAF生产量(kg/h) [直接从H₂+CO₂生产]
        - coal_purchase_vars: 煤炭采购量(kg/周) [v3.0]
        - h2_pipeline/truck_transport_vars: H₂运输量(kg/h)
        - co2_inventory_vars: CO₂库存(kg,来源改为煤炭气化) [v3.0]
        - facility_build_vars: 设施建设二元变量

    约束系统 (v3.1一步法):
        1. 煤炭气化CO₂生成约束(周级) [v3.0]
        2. SAF生产约束(H₂+CO₂→SAF,小时级,一步法) [v3.1修改]
        3. CO₂库存平衡(小时级,来源为煤炭气化) [v3.0]
        4. H₂供应平衡(小时级)
        5. SAF需求满足(机场需求,周级)
        6. 运输能力约束(仅H₂) [v3.0简化]
        7. 设施能力约束

    目标函数:
        最小化总成本 = H₂生产成本 + 煤炭采购成本 [v3.0] + 煤炭气化成本 [v3.0]
                    + H₂运输成本 + SAF生产成本 + SAF运输成本 + 设施投资成本
                    + 缺货惩罚
                    # v3.1一步法: 无甲醇中间成本

    使用流程:
        1. 初始化: optimizer = CoalHydrogenSAFOptimizer(config_path)
        2. 加载数据: optimizer.load_data_from_excel(airport_excel_path, renewable_data)
        3. 运行优化: optimizer.optimize()
        4. 获取结果: results = optimizer.get_optimization_results()

    配置文件:
        products/supply_chain_optimization/coal_hydrogen_saf_optimization/data/CoalHydrogenSAFOptimizer_config.yaml
        - basic_parameters: 基础参数(时间范围、路径规划等)
        - coal_parameters: 煤炭供应和气化参数 (v3.0)
        - hydrogen_parameters: H₂生产和运输参数
        - technologies: 技术参数(green_h2_co2_to_saf)
        - cost_parameters: 成本参数
        - carbon_emission_parameters: 碳排放参数

    依赖组件:
        - Gurobi 11.0+: MILP求解器
        - GraphHopper: 真实路网路径规划(可选)
        - CO2CaptureCalculator: CO₂捕获计算
        - CO2EmissionCalculator: 碳排放计算
        - HydrogenPipelineDistanceCalculator: 氢气管道距离计算
        - HydrogenClusteringOptimizer: 氢气厂聚类优化

    输出结果:
        - results/tables/: CSV表格(优化汇总、设施决策、供应计划等)
        - results/figures/: 可视化图表(成本分解、碳排放对比、运输路径等)
        - results/reports/: 分析报告
        - results/logs/: 运行日志

    技术背景:
        - E-CRM技术: 电化学CO₂还原制甲醇
        - MTJ技术: 甲醇转化制航空燃料(Haldor Topsoe)
        - CCS技术: 碳捕获与封存
        - 绿氢技术: 可再生能源电解水制氢

    注意事项:
        - 需要Gurobi有效许可证
        - 时间范围建议从1周开始测试(计算量大)
        - GraphHopper可选但推荐使用(更精确的距离计算)
        - 大规模问题可能需要调整MIPGap和TimeLimit参数

    版本:
        v2.0.0 - 基于绿氢+CO₂的两步法工艺(2025-10-14)
        v1.0.0 - 基于天然气的单步法工艺(已废弃)

    作者:
        绿色甲醇港口运输研究组

    参考文献:
        - PRD v2.0: 产品需求文档
        - IEA Hydrogen Report 2024
        - IRENA Green Hydrogen Cost 2024
        - Global CCS Institute Report
    """

    def _get_data_path(self, path_key: str, fallback_path: str = None) -> str:
        """
        从配置文件获取数据路径，支持相对路径自动转换为绝对路径
        
        Args:
            path_key: 配置文件中的路径键，支持点号分隔的嵌套键（如'aviation_data.airport_excel_path'）
            fallback_path: 当配置中找不到路径时的后备路径
            
        Returns:
            绝对路径字符串
        """
        try:
            # 解析嵌套的配置键
            keys = path_key.split('.')
            current_config = self.config.get('data_paths', {})
            
            for key in keys:
                if isinstance(current_config, dict) and key in current_config:
                    current_config = current_config[key]
                else:
                    logger.warning(f"配置路径 '{path_key}' 未找到，使用后备路径")
                    if fallback_path is None:
                        raise ValueError(f"配置路径 '{path_key}' 不存在且未提供后备路径")
                    current_config = fallback_path
                    break
            
            if not isinstance(current_config, str):
                raise ValueError(f"配置路径 '{path_key}' 的值不是字符串类型")
            
            # 转换为绝对路径
            if os.path.isabs(current_config):
                return current_config
            else:
                project_root = get_project_base_dir()
                return os.path.join(project_root, current_config)
        except Exception as e:
            logger.error(f"获取数据路径失败: {e}")
            if fallback_path:
                project_root = get_project_base_dir()
                return os.path.join(project_root, fallback_path) if not os.path.isabs(fallback_path) else fallback_path
            raise

    def _log_memory_usage(self, stage_name: str):
        """
        记录当前内存使用情况

        Args:
            stage_name: 记录阶段名称（如"加载solar_data后"）
        """
        try:
            process = psutil.Process(os.getpid())
            mem_info = process.memory_info()
            mem_mb = mem_info.rss / 1024 / 1024
            logger.info(f"[内存监控] {stage_name}: {mem_mb:.2f} MB")
        except Exception as e:
            logger.warning(f"内存监控失败: {e}")

    def _get_output_path(self, file_type: str, timestamp: str = None) -> str:
        """
        获取结果输出文件的完整路径
        
        Args:
            file_type: 文件类型（如'optimization_summary'）
            timestamp: 时间戳，如果为None则生成当前时间戳
            
        Returns:
            完整的输出文件路径
        """
        if timestamp is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        try:
            # 获取结果基础目录
            results_dir = self._get_data_path('output_paths.results_base_dir',
                                            'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results')
            
            # 获取文件名模板
            file_templates = self.config.get('data_paths', {}).get('output_paths', {}).get('file_templates', {})
            template = file_templates.get(file_type, f"{file_type}_{timestamp}.csv")
            
            # 格式化文件名
            filename = template.format(timestamp=timestamp)
            
            return os.path.join(results_dir, filename)
        except Exception as e:
            logger.error(f"获取输出路径失败: {e}")
            # 使用默认路径
            project_root = get_project_base_dir()
            results_dir = os.path.join(project_root, "products", "supply_chain_optimization",
                                     "coal_hydrogen_saf_optimization", "results")
            return os.path.join(results_dir, f"{file_type}_{timestamp}.csv")

    def _load_config(self, config_path: str = None, override_params: dict = None) -> dict:
        """
        加载配置文件
        
        Args:
            config_path: 配置文件路径，如果为None则使用默认路径
            override_params: 用于覆盖配置文件中参数的字典
            
        Returns:
            配置字典
        """
        if config_path is None:
            # 使用默认配置文件路径 (v3.0煤炭气化路线)
            project_root = get_project_base_dir()
            config_path = os.path.join(
                project_root,
                "products",
                "supply_chain_optimization",
                "coal_hydrogen_saf_optimization",
                "data",
                "CoalHydrogenSAFOptimizer_config.yaml"
            )
        
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            # 应用参数覆盖
            if override_params:
                config = self._apply_config_overrides(config, override_params)
            
            logger.info(f"配置文件加载成功: {config_path}")
            return config
            
        except Exception as e:
            logger.error(f"配置文件加载失败: {e}")
            raise
    
    def _apply_config_overrides(self, config: dict, overrides: dict) -> dict:
        """
        应用配置覆盖参数
        
        Args:
            config: 原始配置字典
            overrides: 覆盖参数字典
            
        Returns:
            应用覆盖后的配置字典
        """
        import copy
        new_config = copy.deepcopy(config)
        
        # 支持扁平化的参数覆盖，如 'time_horizon_weeks': 2
        for key, value in overrides.items():
            if key in ['time_horizon_weeks', 'use_graphhopper_routing', 'graphhopper_host',
                      'graphhopper_port', 'max_transport_distance_km', 'use_routing_for_short_distance']:
                new_config['basic_parameters'][key] = value
            elif key in ['levelized_cost_threshold_yuan_per_kg', 'discount_rate', 'project_lifespan']:
                # 直接支持经济参数的覆盖
                new_config['economic_parameters'][key] = value
            elif key.startswith('basic_'):
                param_key = key.replace('basic_', '')
                new_config['basic_parameters'][param_key] = value
            elif key.startswith('economic_'):
                param_key = key.replace('economic_', '')
                new_config['economic_parameters'][param_key] = value
            elif key.startswith('cost_'):
                param_key = key.replace('cost_', '')
                new_config['cost_parameters'][param_key] = value
            elif key.startswith('facility_lcoe_'):
                # 允许通过 facility_lcoe_fixed_capex 等键覆盖
                param_key = key.replace('facility_lcoe_', '')
                if 'facility_lcoe_parameters' not in new_config:
                    new_config['facility_lcoe_parameters'] = {}
                new_config['facility_lcoe_parameters'][param_key] = value
            # 可以继续添加其他类别的参数覆盖逻辑
        
        return new_config

    def _build_mtj_locations(self):
        """根据每种技术的 suitable_locations 动态生成 mtj_locations 映射。"""
        self.mtj_locations = {}

        logger.info("=" * 60)
        logger.info("【位置类型匹配诊断】")
        logger.info("=" * 60)

        # 统计实际位置类型分布
        actual_types = {}
        for loc, info in self.locations.items():
            loc_type = info['type']
            actual_types[loc_type] = actual_types.get(loc_type, 0) + 1

        logger.info(f"实际位置类型分布: {actual_types}")
        logger.info(f"总位置数: {len(self.locations)}")

        for tech, tech_info in self.technologies.items():
            suitable_types = tech_info.get('suitable_locations', [])
            matched_locations = [
                loc for loc, info in self.locations.items()
                if info['type'] in suitable_types
            ]
            self.mtj_locations[tech] = matched_locations

            logger.info(f"\n技术 [{tech}]:")
            logger.info(f"  要求位置类型: {suitable_types}")
            logger.info(f"  匹配到的位置数: {len(matched_locations)}")

            if len(matched_locations) == 0:
                logger.error(f"  ❌ 没有匹配的位置！")
                logger.error(f"  → 检查suitable_locations配置是否与实际位置类型一致")
                logger.error(f"  → 实际可用类型: {list(actual_types.keys())}")
            else:
                logger.info(f"  ✅ 匹配位置示例: {matched_locations[:3]}")

        logger.info("=" * 60)

    def __init__(self, config_path: str = None, **override_params):
        """
        初始化绿氢+CO₂制SAF供应链优化器

        注意: __init__方法仅初始化配置和基础参数，不加载数据也不构建模型。
        必须显式调用load_data()或load_data_from_excel()方法来加载数据并构建优化模型。

        Args:
            config_path (str, optional): YAML配置文件路径。
                默认: products/supply_chain_optimization/coal_hydrogen_saf_optimization/data/CoalHydrogenSAFOptimizer_config.yaml

            **override_params: 关键字参数覆盖配置文件参数。
                常用覆盖参数:
                - time_horizon_weeks (int): 优化时间范围(周), 默认1
                - use_graphhopper_routing (bool): 是否使用GraphHopper路径规划, 默认True
                - solver_time_limit (float): Gurobi求解时间限制(秒), 默认3600
                - solver_mip_gap (float): MIP最优性间隙, 默认0.01 (1%)
                - osm_pbf_path (str): OSM地图数据文件路径
                - graphhopper_host (str): GraphHopper服务器地址
                - graphhopper_port (int): GraphHopper服务器端口

        Attributes (初始化后可用):
            config (dict): 完整配置字典
            time_horizon_weeks (int): 优化时间范围(周)
            hours_per_week (int): 每周小时数(168)
            total_hours (int): 总小时数
            model (gurobipy.Model): Gurobi模型对象(初始化后为None，需调用load_data后创建)
            routing_engine: GraphHopper路径规划引擎(如果启用)
            distance_calculator: 距离计算器

        示例:
            # 使用默认配置
            optimizer = CoalHydrogenSAFOptimizer()

            # 自定义时间范围和关闭GraphHopper
            optimizer = CoalHydrogenSAFOptimizer(
                time_horizon_weeks=4,
                use_graphhopper_routing=False
            )

            # 使用自定义配置文件
            optimizer = CoalHydrogenSAFOptimizer(
                config_path="/path/to/custom_config.yaml",
                solver_time_limit=7200,
                solver_mip_gap=0.05
            )

        Raises:
            FileNotFoundError: 配置文件不存在
            yaml.YAMLError: 配置文件格式错误
            KeyError: 配置文件缺少必需的参数

        后续步骤:
            1. 调用load_data_from_excel()加载机场数据和可再生能源数据
            2. 或调用load_data()加载DataFrame格式的数据
            3. 模型自动构建完成后，调用optimize()求解
            4. 调用get_optimization_results()获取结果
        """
        # 加载配置文件
        self.config = self._load_config(config_path, override_params)
        
        # 从配置中获取基础参数
        basic_params = self.config['basic_parameters']
        self.time_horizon_weeks = basic_params['time_horizon_weeks']

        # 时间粒度配置（3小时粒度）
        self.periods_per_week = basic_params.get('periods_per_week', 56)  # 每周56个3小时期间
        self.hours_per_period = basic_params.get('hours_per_period', 3)   # 每期间3小时
        self.total_periods = self.time_horizon_weeks * self.periods_per_week

        # 真实的每周小时数（用于天数计算等场景，始终为168）
        self.real_hours_per_week = self.periods_per_week * self.hours_per_period  # 56 × 3 = 168

        # 兼容性别名（保持向后兼容）
        # hours_per_week 用于期间索引计算时等于 periods_per_week
        # 用于天数计算时使用 real_hours_per_week
        self.hours_per_week = self.periods_per_week  # 用于期间索引
        self.total_hours = self.total_periods        # 用于期间循环
        
        # 模型组件
        self.model = None
        self.locations = {}
        self.technologies = {}
        self.airports = {}
        self.costs = {}

        # 并行计算配置
        import os
        self.parallel_workers = override_params.get('parallel_workers', None)
        if self.parallel_workers is None:
            # 自动检测: 使用所有CPU核心，但最多128个
            self.parallel_workers = min(os.cpu_count() or 4, 128)
        else:
            # 用户指定的worker数量也限制在128以内
            self.parallel_workers = min(self.parallel_workers, 128)
        logger.info(f"并行计算workers数量: {self.parallel_workers} (最大限制: 128)")

        # 煤炭供应管理器（v3.0煤炭气化路线）
        if CoalSupplyManager is not None:
            self.coal_supply = CoalSupplyManager(self.config)
            logger.info(f"煤炭供应管理器初始化完成: {self.coal_supply.coal_type}, "
                       f"CO₂产率={self.coal_supply.co2_per_kg_coal} kg/kg, "
                       f"价格={self.coal_supply.coal_price_yuan_per_ton} 元/吨")
        else:
            logger.error("CoalSupplyManager模块不可用，无法初始化煤炭供应管理器")
            raise ImportError("CoalSupplyManager模块导入失败")

        # 加载碳排放参数
        self.carbon_params = self.config.get('carbon_emission_parameters', {})
        logger.info(f"加载碳排放参数: {len(self.carbon_params)} 个类别")

        # 通过GraphHopper路径规划计算得出的距离统计值（用于模型中的参考）
        self.avg_hydrogen_transport_distance = None  # 将通过GraphHopper路径规划计算得出
        
        # 决策变量
        self.production_vars = {}  # 小时级生产变量
        self.facility_vars = {}    # 设施建设变量
        self.transport_vars = {}   # 运输变量
        self.storage_vars = {}     # 库存变量
        
        # 初始化GraphHopper路径规划引擎
        self.use_graphhopper_routing = basic_params['use_graphhopper_routing']
        
        # 设置OSM数据文件路径
        osm_pbf_path = override_params.get('osm_pbf_path')
        if osm_pbf_path is None:
            # 使用项目中的默认OSM数据文件
            project_root = get_project_base_dir()
            self.osm_pbf_path = os.path.join(project_root, "products", "supply_chain_optimization",
                                           "coal_hydrogen_saf_optimization", "data", "china-latest.osm.pbf")
        else:
            self.osm_pbf_path = osm_pbf_path
            
        if self.use_graphhopper_routing:
            # 从配置文件获取缓存根目录，然后添加graphhopper_routes子目录
            cache_base_dir = basic_params.get('cache_base_dir', 'shared/data/cache')

            # 如果是相对路径，转换为绝对路径
            if not os.path.isabs(cache_base_dir):
                cache_base_dir = os.path.join(get_project_base_dir(), cache_base_dir)

            cache_dir = os.path.join(cache_base_dir, "graphhopper_routes")
            logger.info(f"GraphHopper路径规划缓存目录: {cache_dir}")

            self.routing_engine = GraphHopperRoutingEngine(
                osm_pbf_path=self.osm_pbf_path,
                graphhopper_host=basic_params['graphhopper_host'],
                graphhopper_port=basic_params['graphhopper_port'],
                cache_dir=cache_dir,
                enable_cache=False  # 禁用数据库缓存（查询比计算更慢）
            )
            self.distance_calculator = GraphHopperDistanceCalculator(self.routing_engine)
            logger.info(f"GraphHopper路径规划引擎初始化完成，OSM数据文件: {self.osm_pbf_path}")
        else:
            # 使用简单的距离计算器作为备用方案
            self.distance_calculator = None
            self.routing_engine = None
            logger.warning("未启用GraphHopper路径规划，将使用直线距离计算，建议设置use_graphhopper_routing=True获得更精确的路径规划")
        
        # 距离缓存（避免重复计算）
        self.distance_cache = {}
        
        # GraphHopper路径规划和距离控制相关设置
        self.graphhopper_host = basic_params['graphhopper_host']
        self.graphhopper_port = basic_params['graphhopper_port']
        self.max_transport_distance_km = basic_params['max_transport_distance_km']
        self.use_routing_for_short_distance = basic_params['use_routing_for_short_distance']
        
        # 距离计算统计
        self.distance_stats = {
            'total_requests': 0,
            'routing_calls': 0,
            'cache_hits': 0,
            'haversine_fallback': 0,
            'exceeded_max_distance': 0
        }
        
        logger.info(f"初始化优化器: {self.time_horizon_weeks}周 ({self.total_hours}小时), GraphHopper路径规划: {self.use_graphhopper_routing}")
        logger.info(f"OSM数据文件: {self.osm_pbf_path}")
        logger.info(f"GraphHopper服务: {self.graphhopper_host}:{self.graphhopper_port}")
        logger.info(f"最大运输距离限制: {self.max_transport_distance_km} 公里")
        
        # 初始化成本分析器（需要在成本参数定义后创建）
        self.cost_analyzer = None
        logger.info(f"短距离路径规划精确计算: {self.use_routing_for_short_distance}")
        logger.info(f"配置文件加载完成: {len(self.config)} 个配置段")

        self.hydrogen_pipeline_calculator = None
        self.hydrogen_clustering_optimizer = None
        self.clustering_results = None
        self.clustered_routes = {}

        # CO2聚类相关属性
        self.co2_clustering_optimizer = None
        self.co2_clustering_results = None
        self.co2_clustered_routes = {}

        # 跳过路径统计（记录无法找到管道路径的位置对）
        self.skipped_routes = {
            'hydrogen_pipeline': [],  # 氢气管道路径跳过记录
            'co2_pipeline': []         # CO₂管道路径跳过记录
        }
    
    def load_data(self, renewable_data: pd.DataFrame, airport_data: pd.DataFrame):
        """
        加载数据

        Args:
            renewable_data: 可再生能源发电数据(小时级，包含太阳能和风能)
            airport_data: 机场需求数据(周级)
        """
        logger.info("加载优化数据...")

        # 处理机场数据
        self._process_airport_data(airport_data)

        # v3.0: 煤炭气化路线不需要加载CO₂捕获源数据

        # 处理可再生能源数据
        self._process_renewable_data(renewable_data)

        # 首先定义经济参数（平准化成本计算需要）
        self._define_economic_parameters()

        # 定义成本参数（使用平准化成本方法）
        self._define_costs()

        # 定义生产技术（使用平准化成本）
        self._define_technologies()

        # 定义运输相关的位置映射
        self._define_transport_locations()

        # 使用GraphHopper路径规划计算平均距离统计
        if self.use_graphhopper_routing:
            self._calculate_average_distances()

        logger.info(f"数据加载完成: {len(self.locations)}个生产地点, {len(self.airports)}个机场 (v3.0: CO₂来自煤炭气化)")
    
    def load_data_from_excel(self, airport_excel_path: str = None, renewable_data: pd.DataFrame = None):
        """
        从Excel文件加载机场数据（支持从配置文件自动获取路径）
        
        Args:
            airport_excel_path: 机场数据Excel文件路径，如果为None则从配置文件获取
            renewable_data: 可再生能源数据(如果为None，将创建示例数据)
        """
        
        # 如果未提供路径，从配置文件获取
        if airport_excel_path is None:
            try:
                airport_excel_path = self._get_data_path('aviation_data.airport_excel_path')
                logger.info(f"从配置文件获取机场数据路径: {airport_excel_path}")
            except Exception as e:
                logger.error(f"从配置文件获取机场数据路径失败: {e}")
                # 使用备用路径
                try:
                    airport_excel_path = self._get_data_path('aviation_data.backup_airport_excel_path')
                    logger.info(f"使用备用机场数据路径: {airport_excel_path}")
                except Exception as e2:
                    logger.error(f"获取备用机场数据路径也失败: {e2}")
                    logger.info("使用传统的airport_data数据")
                    self._load_traditional_airport_data()
                    return
        
        logger.info(f"从Excel文件加载数据: {airport_excel_path}")
        
        # 读取Excel数据 - 尝试读取All_Airports工作表，如果失败则读取默认工作表
        try:
            excel_data = pd.read_excel(airport_excel_path, sheet_name='All_Airports')
            logger.info(f"Excel文件读取成功(All_Airports)，包含 {len(excel_data)} 行数据")
        except Exception as e:
            logger.error(f"读取Excel文件失败（All_Airports）: {e}")
            try:
                logger.info("尝试使用传统方法读取airport_data...")
                excel_data = pd.read_excel(airport_excel_path)
                logger.info(f"Excel文件读取成功，包含 {len(excel_data)} 行数据")
            except Exception as e2:
                logger.error(f"读取Excel文件彻底失败: {e2}")
                raise
        
        # 处理机场数据
        airport_data = self._process_excel_airport_data(excel_data)

        # 立即释放Excel数据，避免内存占用
        del excel_data
        gc.collect()
        self._log_memory_usage("释放excel_data后")

        # 如果没有提供可再生能源数据，必须加载真实数据
        if renewable_data is None:
            renewable_data = self._load_real_renewable_data()
        
        # 处理机场数据
        self._process_airport_data(airport_data)

        # v3.0: 煤炭气化路线不需要加载CO₂捕获源数据

        # 处理可再生能源数据
        self._process_renewable_data(renewable_data)

        # 首先定义经济参数（平准化成本计算需要）
        self._define_economic_parameters()

        # 定义成本参数（使用平准化成本方法）
        self._define_costs()

        # 定义生产技术（使用平准化成本）
        self._define_technologies()

        # 定义运输相关的位置映射
        self._define_transport_locations()

        logger.info(f"数据加载完成: {len(self.locations)}个生产地点, {len(self.airports)}个机场 (v3.0: CO₂来自煤炭气化)")
    
    def _process_renewable_data(self, renewable_data: pd.DataFrame):
        """处理可再生能源数据（包含太阳能和风能，支持缓存）或副产氢数据"""
        try:
            # 检查数据类型：副产氢 vs 可再生能源
            # 副产氢数据的type列为 'byproduct_hydrogen_steel' 或 'byproduct_hydrogen_refinery'
            is_byproduct_h2 = False
            if 'type' in renewable_data.columns and len(renewable_data) > 0:
                first_type = renewable_data['type'].iloc[0]
                if 'byproduct_hydrogen' in str(first_type):
                    is_byproduct_h2 = True
                    logger.info("检测到副产氢数据，跳过可再生能源缓存逻辑")

            # 如果是副产氢数据，执行300km距离过滤，不使用缓存
            if is_byproduct_h2:
                logger.info("检测到副产氢数据，开始执行300km范围过滤")

                # 过滤300km范围内的副产氢设施
                plant_names = renewable_data['plant_name'].unique()
                logger.info(f"使用{self.parallel_workers}个并行workers过滤{len(plant_names)}个副产氢设施")

                # 准备并行处理的参数（使用300km作为筛选距离）
                plant_data_list = [
                    (plant_name, renewable_data[renewable_data['plant_name'] == plant_name], 300)
                    for plant_name in plant_names
                ]

                # 使用线程池并行过滤
                filtered_plants = []
                with ThreadPoolExecutor(max_workers=self.parallel_workers) as executor:
                    results = list(executor.map(_filter_renewable_plant_worker, plant_data_list))

                    for result in results:
                        if result is not None:
                            filtered_plants.append(result)

                # 合并过滤后的数据
                if filtered_plants:
                    filtered_renewable_data = pd.concat(filtered_plants, ignore_index=True)
                    del filtered_plants
                    gc.collect()
                else:
                    filtered_renewable_data = pd.DataFrame()

                logger.info(f"300km范围内的副产氢设施: {len(filtered_renewable_data)} 条记录，{filtered_renewable_data['plant_name'].nunique() if len(filtered_renewable_data) > 0 else 0} 个设施")

                # 立即释放原始renewable_data
                del renewable_data
                gc.collect()
                self._log_memory_usage("释放副产氢原始数据后")
            else:
                # 可再生能源数据，使用缓存机制
                # 导入缓存管理器
                try:
                    from ..cache.data_cache_manager import cache_manager
                except ImportError:
                    from cache.data_cache_manager import cache_manager

                # 为可再生能源数据创建临时文件路径用于缓存检查
                # （因为renewable_data是内存中的DataFrame，我们使用数据摘要作为标识）
                renewable_cache_key = f"renewable_{len(renewable_data)}_{renewable_data['plant_name'].nunique()}"
                temp_renewable_file = f"temp_renewable_{renewable_cache_key}.csv"

                # 检查是否有缓存
                use_cache = False
                if cache_manager.is_cache_valid('renewable_plants', temp_renewable_file):
                    logger.info("发现缓存文件，检查数据完整性...")
                    cached_df = cache_manager.load_filtered_data('renewable_plants')
                    if cached_df is not None:
                        # 检查缓存数据的完整性：每个电站应该有足够的小时数
                        if len(cached_df) > 0 and 'plant_name' in cached_df.columns:
                            cached_hours_per_plant = cached_df.groupby('plant_name').size()
                            min_hours = cached_hours_per_plant.min()
                            max_hours = cached_hours_per_plant.max()

                            logger.info(f"缓存数据: {len(cached_df)} 条记录, "
                                      f"{cached_df['plant_name'].nunique()} 个电站, "
                                      f"每站小时数范围: {min_hours}-{max_hours}")

                            # 检查缓存数据是否包含足够的小时数（应该是2016小时）
                            if min_hours >= self.total_hours:
                                filtered_renewable_data = cached_df
                                logger.info(f"✓ 缓存数据完整，使用缓存: {len(filtered_renewable_data)} 条记录")
                                use_cache = True
                            else:
                                logger.warning(f"✗ 缓存数据不完整 (最少{min_hours}小时 < 要求{self.total_hours}小时)，"
                                             f"将使用新加载的12周数据")
                        else:
                            logger.warning("缓存数据格式错误，执行完整处理")
                    else:
                        logger.warning("缓存加载失败，执行完整处理")
                else:
                    logger.info("缓存无效或不存在，执行完整处理和过滤")

                # 如果不使用缓存，则执行完整处理
                if not use_cache:
                    filtered_renewable_data = self._filter_renewable_data(renewable_data, cache_manager, temp_renewable_file)

                # 立即释放原始renewable_data，避免内存占用
                del renewable_data
                gc.collect()
                self._log_memory_usage("释放renewable_data后")

            # 按地点聚合小时级发电数据 - 使用并行处理
            plant_names = filtered_renewable_data['plant_name'].unique()
            logger.info(f"使用{self.parallel_workers}个并行workers处理{len(plant_names)}个电站的小时级数据")

            # 准备并行处理的参数
            plant_data_list = [
                (plant_name, filtered_renewable_data[filtered_renewable_data['plant_name'] == plant_name], self.total_hours)
                for plant_name in plant_names
            ]

            # 使用线程池并行处理电站数据
            with ThreadPoolExecutor(max_workers=self.parallel_workers) as executor:
                results = list(executor.map(_process_plant_data_worker, plant_data_list))

                for result in results:
                    if result is not None:
                        plant_name, location_dict = result
                        self.locations[plant_name] = location_dict

            # 统计电站/设施类型
            solar_count = sum(1 for loc in self.locations.values() if loc['type'] == 'solar_plant')
            wind_count = sum(1 for loc in self.locations.values() if loc['type'] == 'wind_farm')
            steel_count = sum(1 for loc in self.locations.values() if loc['type'] == 'byproduct_hydrogen_steel')
            refinery_count = sum(1 for loc in self.locations.values() if loc['type'] == 'byproduct_hydrogen_refinery')

            if is_byproduct_h2:
                logger.info(f"处理了 {len(self.locations)} 个副产氢设施")
                logger.info(f"  钢铁/焦化副产氢: {steel_count} 个")
                logger.info(f"  炼油/催化重整副产氢: {refinery_count} 个")
            else:
                logger.info(f"处理了 {len(self.locations)} 个可再生能源发电站")
                logger.info(f"  太阳能发电站: {solar_count} 个")
                logger.info(f"  风电场: {wind_count} 个")

            # 将机场位置添加到基础locations中
            self._add_airports_to_locations()

        except Exception as e:
            logger.error(f"处理可再生能源数据失败: {e}")
            # 降级到原有处理方法
            self._process_renewable_data_fallback(renewable_data)
    
    def _filter_renewable_data(self, renewable_data: pd.DataFrame, cache_manager, temp_file: str, max_distance_km: int = 100) -> pd.DataFrame:
        """过滤可再生能源数据（指定km范围内）- 使用并行处理

        Args:
            renewable_data: 原始数据
            cache_manager: 缓存管理器
            temp_file: 临时文件名
            max_distance_km: 最大距离（km），默认100km
        """
        logger.info(f"过滤可再生能源数据: {len(renewable_data)} 条原始记录，距离范围: {max_distance_km}km")

        plant_names = renewable_data['plant_name'].unique()
        logger.info(f"使用{self.parallel_workers}个并行workers处理{len(plant_names)}个电站")

        # 准备并行处理的参数（使用指定距离作为筛选距离）
        plant_data_list = [
            (plant_name, renewable_data[renewable_data['plant_name'] == plant_name], max_distance_km)
            for plant_name in plant_names
        ]

        # 使用线程池并行过滤（线程池更适合I/O密集型任务）
        filtered_plants = []
        with ThreadPoolExecutor(max_workers=self.parallel_workers) as executor:
            results = list(executor.map(_filter_renewable_plant_worker, plant_data_list))

            for result in results:
                if result is not None:
                    filtered_plants.append(result)

        # 合并过滤后的数据
        if filtered_plants:
            filtered_df = pd.concat(filtered_plants, ignore_index=True)

            # 立即释放filtered_plants列表，避免内存占用
            del filtered_plants
            gc.collect()
            self._log_memory_usage("释放filtered_plants后")
        else:
            filtered_df = pd.DataFrame()

        logger.info(f"{max_distance_km}km范围内的数据: {len(filtered_df)} 条记录，{filtered_df['plant_name'].nunique() if len(filtered_df) > 0 else 0} 个电站")

        # 保存到缓存
        if len(filtered_df) > 0:
            cache_manager.save_filtered_data('renewable_plants', filtered_df, temp_file)
        
        return filtered_df
    
    def _process_renewable_data_fallback(self, renewable_data: pd.DataFrame):
        """处理可再生能源数据的降级方法（原有逻辑）"""
        logger.warning("使用降级方法处理可再生能源数据")
        
        # 按地点聚合小时级发电数据
        for plant_name in renewable_data['plant_name'].unique():
            plant_data = renewable_data[renewable_data['plant_name'] == plant_name]
            
            # 取前total_hours小时数据
            if len(plant_data) >= self.total_hours:
                hourly_data = plant_data.head(self.total_hours)
                
                # 检查坐标是否在北京300公里范围内（与副产氢场景保持一致）
                plant_lat = hourly_data.iloc[0].get('latitude', 30.0)
                plant_lon = hourly_data.iloc[0].get('longitude', 104.0)

                if not is_within_beijing_range(plant_lat, plant_lon, 300):
                    distance = calculate_distance_km(plant_lat, plant_lon, 39.9042, 116.4074)
                    logger.info(f"可再生能源电站 {plant_name} 距离北京 {distance:.1f}km，超出300km范围，跳过")
                    continue
                
                # 确定电站类型
                plant_type = hourly_data.iloc[0]['type'] if 'type' in hourly_data.columns else 'solar_plant'
                
                self.locations[plant_name] = {
                    'type': plant_type,  # 'solar_plant' 或 'wind_farm'
                    'latitude': hourly_data.iloc[0].get('latitude', 30.0),
                    'longitude': hourly_data.iloc[0].get('longitude', 104.0),
                    'capacity_mw': hourly_data.iloc[0]['capacity_mw'] if 'capacity_mw' in hourly_data.columns else hourly_data.iloc[0]['power_output_mw'],
                    'hourly_generation': hourly_data['power_output_mw'].tolist(),  # 每小时发电量 MWh (等价于平均功率 MW)
                }
        
        logger.info(f"处理了 {len(self.locations)} 个可再生能源发电站（降级方法）")
        
        # 统计电站类型
        solar_count = sum(1 for loc in self.locations.values() if loc['type'] == 'solar_plant')
        wind_count = sum(1 for loc in self.locations.values() if loc['type'] == 'wind_farm')
        logger.info(f"  太阳能发电站: {solar_count} 个")
        logger.info(f"  风电场: {wind_count} 个")
        
        # 将机场位置添加到基础locations中
        self._add_airports_to_locations()
        

    def _add_airports_to_locations(self):
        """将机场位置添加到基础locations字典中，使其可以用于决策变量"""
        if hasattr(self, 'airports') and self.airports:
            for airport_name, airport_info in self.airports.items():
                # 使用机场名称作为位置标识符
                location_id = f"airport_{airport_name}"

                # 添加到基础locations字典
                self.locations[location_id] = {
                    'type': 'airport',  # 新的位置类型
                    'latitude': airport_info['latitude'],
                    'longitude': airport_info['longitude'],
                    'capacity_mw': 0,  # 机场本身不发电
                    'hourly_generation': [0] * self.total_periods,  # 无发电
                    'original_airport_name': airport_name,  # 保留原始机场名称
                    'fuel_demand_weekly': airport_info.get('weekly_fuel_series', [])
                }

            airport_count = sum(1 for loc in self.locations.values() if loc['type'] == 'airport')
            logger.info(f"  添加了 {airport_count} 个机场位置到基础locations中")
        else:
            logger.warning("机场数据尚未加载，无法添加机场位置")

    def _process_excel_airport_data(self, excel_data: pd.DataFrame) -> pd.DataFrame:
        """
        处理京津冀五个机场Excel格式的数据，转换为模型所需格式
        
        Args:
            excel_data: 从Excel读取的京津冀机场原始数据
            
        Returns:
            处理后的机场数据DataFrame
        """
        logger.info("处理京津冀五个机场Excel数据...")
        logger.info(f"Excel columns: {excel_data.columns.tolist()}")
        
        # 按机场分组，创建每个机场的周时间序列
        airport_list = []
        
        for airport_name in excel_data['departure_airport_name'].unique():
            airport_subset = excel_data[excel_data['departure_airport_name'] == airport_name].copy()
            
            # 按周数排序
            airport_subset = airport_subset.sort_values('week_number')
            
            # 提取周甲醇需求序列（使用总甲醇消耗_kg列）
            weekly_fuel_series = airport_subset['weekly_total_fuel_kg_total'].tolist()
            
            # 确保有52周的数据，如果不足则用平均值填充
            if len(weekly_fuel_series) < 52:
                # 计算现有数据的平均值
                if not weekly_fuel_series:
                    logger.error(f"机场 {airport_name} 没有有效的燃油需求数据")
                    raise ValueError(f"机场 {airport_name} 缺少燃油需求数据")
                avg_demand = np.mean(weekly_fuel_series)
                # 填充到52周
                weekly_fuel_series.extend([avg_demand] * (52 - len(weekly_fuel_series)))
            elif len(weekly_fuel_series) > 52:
                # 如果超过52周，只取前52周
                weekly_fuel_series = weekly_fuel_series[:52]
            
            # 计算统计指标
            avg_weekly_fuel = np.mean(weekly_fuel_series)
            max_weekly_fuel = np.max(weekly_fuel_series)
            total_annual_fuel = np.sum(weekly_fuel_series)
            
            # 获取机场位置信息（使用京津冀机场坐标）
            airport_coords = self._get_airport_coordinates(airport_name)
            
            airport_info = {
                'airport_name': airport_name,
                'latitude': airport_coords['latitude'],
                'longitude': airport_coords['longitude'],
                'weekly_fuel_series': weekly_fuel_series,
                'avg_weekly_fuel_kg': avg_weekly_fuel,
                'max_weekly_fuel_kg': max_weekly_fuel,
                'total_fuel_kg': total_annual_fuel
            }
            
            airport_list.append(airport_info)
        
        logger.info(f"处理了 {len(airport_list)} 个京津冀机场的数据")
        
        return pd.DataFrame(airport_list)
    
    def _process_csv_airport_data(self, csv_data: pd.DataFrame) -> pd.DataFrame:
        """
        处理CSV格式的机场数据，转换为模型所需格式
        
        Args:
            csv_data: 从CSV读取的机场数据
            
        Returns:
            处理后的机场数据DataFrame
        """
        logger.info("处理CSV格式的机场数据...")
        logger.info(f"CSV数据列名: {csv_data.columns.tolist()}")
        logger.info(f"CSV数据前5行预览:")
        logger.info(csv_data.head().to_string())
        
        # 检查CSV数据的基本结构
        airport_list = []
        
        # 根据实际CSV结构调整处理逻辑
        if '机场' in csv_data.columns:
            # 按机场分组处理
            for airport_name in csv_data['机场'].unique():
                airport_subset = csv_data[csv_data['机场'] == airport_name].copy()
                
                # 获取机场坐标
                airport_coords = self._get_airport_coordinates(airport_name)
                
                # 如果有周数和燃料消耗数据，提取时间序列
                if '周数' in airport_subset.columns and '总甲醇消耗_kg' in airport_subset.columns:
                    airport_subset = airport_subset.sort_values('周数')
                    weekly_fuel_series = airport_subset['总甲醇消耗_kg'].tolist()
                    
                    # 确保有52周的数据
                    if len(weekly_fuel_series) < 52:
                        if not weekly_fuel_series:
                            logger.error(f"机场 {airport_name} 没有有效的燃油需求数据")
                        raise ValueError(f"机场 {airport_name} 缺少燃油需求数据")
                        avg_demand = np.mean(weekly_fuel_series)
                        weekly_fuel_series.extend([avg_demand] * (52 - len(weekly_fuel_series)))

                    elif len(weekly_fuel_series) > 52:
                        weekly_fuel_series = weekly_fuel_series[:52]
                    
                        avg_weekly_fuel = np.mean(weekly_fuel_series)
                        max_weekly_fuel = np.max(weekly_fuel_series)
                        total_annual_fuel = np.sum(weekly_fuel_series)
                    
                else:
                    # 如果没有时间序列数据，数据不完整
                    logger.error(f"机场 {airport_name} 缺少必要的燃油需求数据")
                    raise ValueError(f"机场 {airport_name} 数据不完整，缺少燃油需求时间序列")
                
                airport_info = {
                    'airport_name': airport_name,
                    'latitude': airport_coords['latitude'],
                    'longitude': airport_coords['longitude'],
                    'weekly_fuel_series': weekly_fuel_series,
                    'avg_weekly_fuel_kg': avg_weekly_fuel,
                    'max_weekly_fuel_kg': max_weekly_fuel,
                    'total_fuel_kg': total_annual_fuel
                }
                
                airport_list.append(airport_info)
                
        else:
            # 如果CSV结构不符合预期，数据格式错误
            logger.error("CSV数据格式不符合预期，无法解析机场数据")
            raise ValueError("CSV数据格式不符合预期，请检查数据文件格式")
        
        logger.info(f"处理了 {len(airport_list)} 个机场的数据")
        
        return pd.DataFrame(airport_list)
    
    def _get_airport_coordinates(self, airport_name: str) -> dict:
        """
        获取京津冀机场坐标信息
        
        Args:
            airport_name: 机场名称
            
        Returns:
            包含经纬度的字典
        """
        # 从配置文件读取京津冀机场坐标映射表
        airport_coords_map = self.config.get('geographic_data', {}).get('airport_coordinates', {
            # 向后兼容的默认值
            '首都机场': {'latitude': 40.0801, 'longitude': 116.5846},
            '北京首都国际机场': {'latitude': 40.0801, 'longitude': 116.5846},
            '北京': {'latitude': 40.0801, 'longitude': 116.5846},
            '滨海机场': {'latitude': 39.1244, 'longitude': 117.3462},
            '天津滨海国际机场': {'latitude': 39.1244, 'longitude': 117.3462},
            '天津': {'latitude': 39.1244, 'longitude': 117.3462},
            '正定机场': {'latitude': 38.2807, 'longitude': 114.6956},
            '石家庄正定国际机场': {'latitude': 38.2807, 'longitude': 114.6956},
            '石家庄': {'latitude': 38.2807, 'longitude': 114.6956},
            '南苑机场': {'latitude': 39.7827, 'longitude': 116.3878},
            '北京南苑机场': {'latitude': 39.7827, 'longitude': 116.3878},
            '邯郸机场': {'latitude': 36.5258, 'longitude': 114.4253},
            '邯郸': {'latitude': 36.5258, 'longitude': 114.4253}
        })
        
        # 如果找到对应机场，返回实际坐标
        if airport_name in airport_coords_map:
            return airport_coords_map[airport_name]
        
        # 如果机场不在预定义列表中，抛出错误
        logger.error(f"未知的机场名称: {airport_name}，请检查数据")
        raise ValueError(f"未支持的机场: {airport_name}")
    
    

    def _load_preprocessed_renewable_data(self) -> Tuple[pd.DataFrame, bool]:
        """
        加载预处理后的可再生能源数据

        此方法直接加载预处理脚本生成的数据文件（CSV格式），
        跳过原始数据的加载和处理步骤，显著提升性能。
        直接加载已筛选100km范围的12周典型数据。

        Returns:
            Tuple[pd.DataFrame, bool]: (预处理后的可再生能源数据DataFrame, 是否已预筛选)

        Raises:
            FileNotFoundError: 如果未找到预处理数据文件
        """
        logger.info("="*80)
        logger.info("正在加载预处理后的可再生能源数据...")
        logger.info("="*80)

        # 获取预处理数据目录
        try:
            preprocessed_dir = self._get_data_path('aviation_data.preprocessed_data_dir')
            logger.info(f"预处理数据目录: {preprocessed_dir}")
        except Exception as e:
            error_msg = (
                f"无法从配置文件获取预处理数据路径: {e}\n"
                f"请先运行预处理脚本生成数据：\n"
                f"  cd products/supply_chain_optimization/coal_hydrogen_saf_optimization/scripts\n"
                f"  python preprocess_all_renewable_data.py --all"
            )
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)

        # 直接加载100km筛选后的CSV格式数据
        solar_100km_csv = os.path.join(preprocessed_dir, 'solar_hourly_100km.csv')
        wind_100km_csv = os.path.join(preprocessed_dir, 'wind_hourly_100km.csv')

        logger.info("✓ 加载100km筛选后的CSV格式数据")
        logger.info(f"加载太阳能数据: {solar_100km_csv}")
        solar_data = pd.read_csv(solar_100km_csv)
        # 修正类型名称: solar_farm -> solar_plant (与配置文件中的suitable_locations匹配)
        if 'type' in solar_data.columns:
            solar_data['type'] = 'solar_plant'
        logger.info(f"  太阳能数据: {len(solar_data):,} 条记录, {solar_data['plant_id'].nunique()} 个电站")

        logger.info(f"加载风电数据: {wind_100km_csv}")
        wind_data = pd.read_csv(wind_100km_csv)
        logger.info(f"  风电数据: {len(wind_data):,} 条记录, {wind_data['plant_id'].nunique()} 个电站")

        data_loaded = True
        is_prefiltered = True  # 100km已预筛选，无需再次筛选
        logger.info("✓ 数据已预筛选（100km范围），无需再次筛选")

        # 合并数据
        renewable_data = pd.concat([solar_data, wind_data], ignore_index=True)
        logger.info(f"合并后总计: {len(renewable_data):,} 条记录")

        # 截断到total_hours（如果需要）
        if 'hour' in renewable_data.columns:
            before_count = len(renewable_data)
            renewable_data = renewable_data[renewable_data['hour'] < self.total_hours]
            after_count = len(renewable_data)
            if before_count > after_count:
                logger.info(f"截断到前{self.total_hours}小时: {before_count:,} → {after_count:,} 条记录")

        # 释放源数据内存
        del solar_data, wind_data
        gc.collect()
        self._log_memory_usage("释放solar_data和wind_data后")

        # 统计信息
        solar_count = len(renewable_data[renewable_data['type'] == 'solar_plant'])
        wind_count = len(renewable_data[renewable_data['type'] == 'wind_farm'])
        logger.info(f"数据统计:")
        logger.info(f"  太阳能: {solar_count:,} 条记录")
        logger.info(f"  风电: {wind_count:,} 条记录")
        logger.info("="*80)

        return renewable_data, is_prefiltered

    def _load_real_renewable_data(self) -> pd.DataFrame:
        """
        加载真实的可再生能源数据或副产氢数据

        Returns:
            可再生能源/副产氢数据DataFrame
        """
        logger.info("加载真实的可再生能源数据...")

        # 首先检查是否配置了副产氢数据路径
        try:
            steel_h2_path = self._get_data_path('aviation_data.steel_h2_data_path')
            refinery_h2_path = self._get_data_path('aviation_data.refinery_h2_data_path')

            # 如果两个路径都配置了，说明是副产氢场景
            if steel_h2_path and refinery_h2_path:
                logger.info("检测到副产氢数据配置，将加载副产氢数据")
                return self._load_byproduct_h2_data()
        except Exception as e:
            logger.debug(f"未找到副产氢数据配置: {e}，将加载可再生能源数据")

        # 加载预处理后的可再生能源数据
        renewable_data, is_prefiltered = self._load_preprocessed_renewable_data()

        # 存储预筛选标记，供后续处理使用
        self.is_renewable_data_prefiltered = is_prefiltered

        return renewable_data

    def _load_byproduct_h2_data(self) -> pd.DataFrame:
        """
        直接加载副产氢原始数据（跳过convert脚本）

        Returns:
            副产氢数据DataFrame（格式与可再生能源数据一致）
        """
        logger.info("="*80)
        logger.info("加载副产氢原始数据（直接计算，无需convert）")
        logger.info("="*80)

        # 获取配置参数
        base_dir = get_project_base_dir()
        steel_h2_path = os.path.join(base_dir, self._get_data_path('aviation_data.steel_h2_data_path'))
        refinery_h2_path = os.path.join(base_dir, self._get_data_path('aviation_data.refinery_h2_data_path'))
        steel_available_rate = self.config['data_paths']['aviation_data']['steel_available_rate']
        refinery_available_rate = self.config['data_paths']['aviation_data']['refinery_available_rate']

        logger.info(f"钢铁副产氢数据: {steel_h2_path}")
        logger.info(f"炼油副产氢数据: {refinery_h2_path}")
        logger.info(f"钢铁可外供比例: {steel_available_rate*100:.0f}%")
        logger.info(f"炼油可外供比例: {refinery_available_rate*100:.0f}%")

        # 加载钢铁副产氢数据
        steel_df = pd.read_csv(steel_h2_path, encoding='utf-8-sig')
        logger.info(f"✓ 钢铁副产氢: {len(steel_df)} 个设施")
        logger.info(f"  总日产能: {steel_df['h2_daily_tonnes'].sum():.2f} 吨/天")

        # 加载炼油副产氢数据
        refinery_df = pd.read_csv(refinery_h2_path, encoding='utf-8-sig')
        logger.info(f"✓ 炼油副产氢: {len(refinery_df)} 个设施")
        logger.info(f"  总日产能: {refinery_df['h2_daily_tonnes'].sum():.2f} 吨/天")

        # 处理钢铁副产氢数据
        steel_time_series = self._process_byproduct_h2_source(
            df=steel_df,
            available_rate=steel_available_rate,
            plant_type='steel',
            plant_name_prefix='steel_',
            name_column='plant_name'
        )

        # 处理炼油副产氢数据
        refinery_time_series = self._process_byproduct_h2_source(
            df=refinery_df,
            available_rate=refinery_available_rate,
            plant_type='refinery',
            plant_name_prefix='refinery_',
            name_column='refinery_name'
        )

        # 保存统计信息以便后续使用
        steel_count = len(steel_df)
        refinery_count = len(refinery_df)

        # 立即释放原始数据，避免内存累积
        del steel_df, refinery_df
        gc.collect()
        self._log_memory_usage("释放steel_df和refinery_df后")

        # 合并数据
        byproduct_h2_data = pd.concat([steel_time_series, refinery_time_series], ignore_index=True, copy=False)
        byproduct_h2_data = byproduct_h2_data.sort_values(['plant_name', 'hour']).reset_index(drop=True)

        # 释放时间序列中间数据
        del steel_time_series, refinery_time_series
        gc.collect()
        self._log_memory_usage("释放副产氢时间序列数据后")

        # 输出统计信息（过滤前）
        logger.info("\n" + "="*80)
        logger.info("副产氢数据加载完成（过滤前统计）！")
        logger.info("="*80)
        logger.info(f"总记录数: {len(byproduct_h2_data):,}")
        logger.info(f"设施数量: {byproduct_h2_data['plant_name'].nunique()}")
        logger.info(f"  - 钢铁厂: {steel_count}")
        logger.info(f"  - 炼油厂: {refinery_count}")
        logger.info(f"总小时产能: {byproduct_h2_data.groupby('plant_name')['power_output_mw'].first().sum():.2f} kg H2/hour")
        logger.info("注意：以上统计为原始数据，300km地理范围过滤将在后续处理中执行")
        logger.info("="*80)

        return byproduct_h2_data

    def _process_byproduct_h2_source(
        self,
        df: pd.DataFrame,
        available_rate: float,
        plant_type: str,
        plant_name_prefix: str,
        name_column: str
    ) -> pd.DataFrame:
        """
        处理单一来源的副产氢数据

        Args:
            df: 副产氢原始数据
            available_rate: 可外供比例
            plant_type: 工厂类型（'steel' or 'refinery'）
            plant_name_prefix: 工厂名称前缀
            name_column: 工厂名称列名

        Returns:
            时间序列格式的DataFrame
        """
        # 1. 计算可外供的日产能（吨/天）
        df['available_daily_tonnes'] = df['h2_daily_tonnes'] * available_rate

        # 2. 转换为小时产能上限（kg/小时）
        df['hourly_capacity_kg'] = (df['available_daily_tonnes'] * 1000) / 24

        logger.info(f"  {plant_type.capitalize()} 可外供产能:")
        logger.info(f"    总可外供日产能: {df['available_daily_tonnes'].sum():.2f} 吨/天")
        logger.info(f"    总小时产能: {df['hourly_capacity_kg'].sum():.2f} kg/小时")

        # 3. 生成时间序列数据（168小时，恒定产能）
        time_series_data = []

        for _, row in df.iterrows():
            for hour in range(self.total_hours):
                time_series_data.append({
                    'plant_name': f"{plant_name_prefix}{row[name_column]}",
                    'type': f'byproduct_hydrogen_{plant_type}',
                    'latitude': row['latitude'],
                    'longitude': row['longitude'],
                    'capacity_mw': row['hourly_capacity_kg'],  # 暂存产能，字段名沿用
                    'power_output_mw': row['hourly_capacity_kg'],  # 存储氢气产量(kg/h)
                    'hour': hour
                })

        time_series_df = pd.DataFrame(time_series_data)
        logger.info(f"    生成时间序列记录: {len(time_series_df):,} 条（地理范围过滤将在后续统一处理）")

        return time_series_df

    def _load_wind_data(self, wind_data_dir: str) -> pd.DataFrame:
        """
        加载风电数据
        
        Args:
            wind_data_dir: 风电数据目录路径
            
        Returns:
            风电数据DataFrame
        """
        logger.info("正在加载风电数据...")
        
        wind_data_list = []
        
        # 读取前几个风电数据文件（避免内存过载）
        wind_files = [f for f in os.listdir(wind_data_dir) if f.endswith('.csv')][:10]  # 只读取前10个文件
        
        for file_name in wind_files:
            file_path = os.path.join(wind_data_dir, file_name)
            try:
                df = pd.read_csv(file_path)
                
                # 数据预处理
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                
                # 筛选2024年数据（完整一年）
                df = df[df['timestamp'].dt.year == 2024]

                # 从3小时发电量插值到每小时发电量
                df_hourly = self._interpolate_wind_to_hourly(df)
                
                wind_data_list.append(df_hourly)
                
            except Exception as e:
                logger.warning(f"读取风电文件 {file_name} 失败: {e}")
        
        if wind_data_list:
            wind_data = pd.concat(wind_data_list, ignore_index=True)
            logger.info(f"成功加载 {len(wind_data)} 条风电数据")
        else:
            logger.warning("没有成功读取任何风电数据")
            wind_data = pd.DataFrame()
        
        return wind_data
    
    def _load_solar_data(self, solar_data_dir: str) -> pd.DataFrame:
        """
        加载光伏数据 - 读取第一个月的所有批次数据
        
        Args:
            solar_data_dir: 光伏数据目录路径
            
        Returns:
            光伏数据DataFrame
        """
        logger.info("正在加载光伏数据...")
        
        solar_data_list = []

        # 读取全部12个月的所有批次文件
        all_files = os.listdir(solar_data_dir)

        # 收集所有月份的文件
        all_month_files = []
        for month in range(1, 13):  # 1到12月
            month_key = f'month{month:02d}'
            month_files = [f for f in all_files
                          if f.startswith(f'solar_generation_{month_key}_batch_')
                          and f.endswith('.csv')]
            all_month_files.extend(month_files)

        all_month_files.sort()  # 按文件名顺序排序

        logger.info(f"找到 {len(all_month_files)} 个批次文件，覆盖全年12个月")

        for file_name in all_month_files:
            file_path = os.path.join(solar_data_dir, file_name)
            try:
                df = pd.read_csv(file_path)

                # 数据预处理
                df['timestamp'] = pd.to_datetime(df['timestamp'])

                # 检查数据的年份（应该是2020年）
                available_years = df['timestamp'].dt.year.unique()
                logger.debug(f"文件 {file_name} 包含年份: {sorted(available_years)}")

                # 使用2020年完整一年的数据
                base_year = min(available_years)
                start_date = f"{base_year}-01-01"
                end_date = f"{base_year}-12-31 23:59:59"  # 完整一年

                df_filtered = df[(df['timestamp'] >= start_date) & (df['timestamp'] <= end_date)].copy()

                if len(df_filtered) == 0:
                    logger.warning(f"文件 {file_name} 在时间范围 {start_date} 到 {end_date} 内没有数据")
                    continue

                # 重命名列以统一格式
                df_processed = df_filtered.copy()
                df_processed['plant_name'] = df_filtered['plant_name']
                df_processed['type'] = 'solar_plant'
                df_processed['generation_mwh'] = df_filtered['generation_1h_mwh']  # 每小时发电量(MWh)
                df_processed['power_output_mw'] = df_filtered['generation_1h_mwh']  # 功率等于发电量/1小时 = MWh/h = MW

                # 创建hour列（从2020年1月1日开始计算）
                start_time = pd.to_datetime(f"{base_year}-01-01")
                df_processed['hour'] = (df_processed['timestamp'] - start_time).dt.total_seconds() // 3600
                df_processed['hour'] = df_processed['hour'].astype(int)

                # 只保留前total_hours（8760小时=52周）的数据
                df_processed = df_processed[df_processed['hour'] < self.total_hours]

                logger.debug(f"文件 {file_name} 处理后得到 {len(df_processed)} 条记录")
                solar_data_list.append(df_processed)

            except Exception as e:
                logger.warning(f"读取光伏文件 {file_name} 失败: {e}")

        if solar_data_list:
            solar_data = pd.concat(solar_data_list, ignore_index=True)
            logger.info(f"成功加载 {len(solar_data)} 条光伏数据，来自 {len(all_month_files)} 个批次文件")

            # 统计光伏电站数量
            unique_plants = solar_data['plant_name'].nunique()
            logger.info(f"包含 {unique_plants} 个不同的光伏电站")
            
        else:
            logger.warning("没有成功读取任何光伏数据")
            solar_data = pd.DataFrame()
        
        return solar_data
    
    def _interpolate_wind_to_hourly(self, wind_df: pd.DataFrame) -> pd.DataFrame:
        """
        将风电3小时数据插值到每小时
        使用最近邻插值：直接使用3小时的发电量作为每小时的发电量
        
        Args:
            wind_df: 3小时风电数据
            
        Returns:
            每小时风电数据
        """
        hourly_data = []
        
        for _, row in wind_df.iterrows():
            timestamp = row['timestamp']
            generation_3h = row['generation_3h_mwh']
            
            # 核心修改：直接使用3小时的发电量作为每小时的发电量
            # 而不是除以3进行平均分配
            hourly_generation = generation_3h  # 直接使用最近的发电量数据
            
            for i in range(3):
                hour_timestamp = timestamp + pd.Timedelta(hours=i)
                hour_from_start = (hour_timestamp - wind_df['timestamp'].min()).total_seconds() // 3600
                
                if hour_from_start < self.total_hours:
                    hourly_data.append({
                        'plant_name': row['farm_name'],
                        'type': 'wind_farm',
                        'latitude': row['latitude'],
                        'longitude': row['longitude'],
                        'capacity_mw': row['capacity_mw'],
                        'power_output_mw': hourly_generation,  # 每小时发电量（使用最近的3小时数据）
                        'hour': int(hour_from_start)
                    })
        
        return pd.DataFrame(hourly_data)
    
    
    def _process_airport_data(self, airport_data: pd.DataFrame):
        """处理机场周时间序列数据 - 使用并行处理"""
        # 直接从Excel文件读取真实的52周时间序列需求数据
        # 构建绝对路径 - 修正后的路径
        project_root = get_project_base_dir()
        excel_path = os.path.join(project_root, "products", "aviation_fuel_analysis",
                                "resource_flight_data_process", "data",
                                "capital_binhai_airports_data_20250726_123415.xlsx")

        try:
            # 读取Excel文件中的真实数据
            excel_df = pd.read_excel(excel_path, sheet_name='All_Airports')
            logger.info(f"成功读取Excel文件: {excel_path}")
            logger.info(f"Excel数据包含 {len(excel_df)} 行，{excel_df['departure_airport_name'].nunique()} 个机场")

            # 按机场分组处理数据 - 使用并行处理
            airport_names = excel_df['departure_airport_name'].unique()
            logger.info(f"使用{self.parallel_workers}个并行workers处理{len(airport_names)}个机场")

            # 准备并行处理的参数
            airport_data_list = [
                (airport_name, excel_df[excel_df['departure_airport_name'] == airport_name])
                for airport_name in airport_names
            ]

            # 使用线程池并行处理机场数据
            with ThreadPoolExecutor(max_workers=self.parallel_workers) as executor:
                results = list(executor.map(_process_airport_data_worker, airport_data_list))

                for airport_name, airport_dict in results:
                    self.airports[airport_name] = airport_dict
                    logger.info(f"处理机场 {airport_name}: {len(airport_dict['weekly_demand_series'])} 周真实数据，年需求 {airport_dict['total_annual_demand_kg']:,.0f} kg")

        except Exception as e:
            logger.error(f"读取Excel文件失败: {e}")
            logger.info("使用传统方法处理airport_data参数")

            # 如果Excel文件读取失败，使用传统方法处理airport_data参数（向后兼容）
            for _, airport in airport_data.iterrows():
                airport_name = airport['airport_name']

                if 'weekly_fuel_series' in airport and isinstance(airport['weekly_fuel_series'], list):
                    weekly_series = airport['weekly_fuel_series']
                    logger.info(f"使用真实数据：机场 {airport_name} 包含 {len(weekly_series)} 周的真实需求数据")
                else:
                    logger.error(f"机场 {airport_name} 缺少必要的燃油需求时间序列数据")
                    raise ValueError(f"机场 {airport_name} 数据不完整，缺少weekly_fuel_series字段")

                self.airports[airport_name] = {
                    'latitude': airport['latitude'],
                    'longitude': airport['longitude'],
                    'weekly_demand_series': weekly_series,
                    'avg_weekly_demand_kg': airport.get('avg_weekly_fuel_kg', sum(weekly_series) / len(weekly_series)),
                    'max_weekly_demand_kg': airport.get('max_weekly_fuel_kg', max(weekly_series)),
                    'total_annual_demand_kg': airport.get('total_fuel_kg', sum(weekly_series)),
                    'flight_count': airport.get('flight_count', 100)
                }

        logger.info(f"处理了 {len(self.airports)} 个机场，每个机场包含52周时间序列数据")

        # 统计需求信息
        total_annual_demand = sum(airport['total_annual_demand_kg'] for airport in self.airports.values())
        avg_weekly_demand = sum(airport['avg_weekly_demand_kg'] for airport in self.airports.values())
        logger.info(f"总年需求: {total_annual_demand:,.0f} kg")
        logger.info(f"平均周需求: {avg_weekly_demand:,.0f} kg/周")
    
    def _define_transport_locations(self):
        """定义运输相关的位置映射 - 现在基于统一的location系统"""
        # 氢气生产位置（可再生能源发电站）
        self.hydrogen_locations = [
            loc for loc, info in self.locations.items()
            if info['type'] in ['solar_plant', 'wind_farm', 'byproduct_hydrogen_steel', 'byproduct_hydrogen_refinery']
        ]
        
        # 机场位置（统一从locations获取）
        self.airport_locations = [
            loc for loc, info in self.locations.items() 
            if info['type'] == 'airport'
        ]

        # 所有可用于建设MTJ工厂的位置（现在统一从self.locations中获取）
        # 每种技术的适用位置由技术定义中的suitable_locations决定，不需要单独的mtj_locations映射
        
        logger.info(f"定义了运输位置映射:")
        logger.info(f"  氢气生产位置: {len(self.hydrogen_locations)} 个")
        logger.info(f"  机场位置: {len(self.airport_locations)} 个")
        logger.info(f"  总位置数: {len(self.locations)} 个")

        # 构建MTJ工厂位置映射（_initialize_hydrogen_clustering依赖此数据）
        self._build_mtj_locations()
        self._initialize_hydrogen_clustering()
        # v3.0: 煤炭气化路线不需要CO₂聚类
        # self._initialize_co2_clustering()

    def _initialize_hydrogen_clustering(self):
        if not self.config.get('basic_parameters', {}).get('use_hydrogen_pipeline_distance', False):
            logger.info("氢气管道距离计算未启用，跳过聚类初始化")
            return

        if HydrogenPipelineDistanceCalculator is None or HydrogenClusteringOptimizer is None:
            raise ImportError(
                "氢气管道距离计算器或聚类优化器模块导入失败！\n"
                "配置文件中启用了 use_hydrogen_pipeline_distance=true，但必需的模块不可用。\n"
                "缺失模块：\n"
                f"  - HydrogenPipelineDistanceCalculator: {'✓ 已导入' if HydrogenPipelineDistanceCalculator else '✗ 未导入'}\n"
                f"  - HydrogenClusteringOptimizer: {'✓ 已导入' if HydrogenClusteringOptimizer else '✗ 未导入'}\n"
                "请检查以下文件是否存在：\n"
                "  - src/hydrogen/hydrogen_pipeline_distance_calculator.py\n"
                "  - src/hydrogen/hydrogen_clustering_optimizer.py\n"
                "解决方法：\n"
                "  1. 确保上述文件存在且无语法错误\n"
                "  2. 或在配置文件中设置 use_hydrogen_pipeline_distance: false"
            )

        try:
            project_root = get_project_base_dir()
            gis_data_path = os.path.join(project_root, "products", "gis_energy_mapping",
                                        "gis_data_scraper", "scraped_gis_data")

            self.hydrogen_pipeline_calculator = HydrogenPipelineDistanceCalculator(
                gis_data_path,
                enable_cache=False  # 禁用数据库缓存（查询比计算更慢）
            )
            self.hydrogen_pipeline_calculator.load_pipeline_data()
            logger.info("氢气管道距离计算器初始化完成")

            self.hydrogen_clustering_optimizer = HydrogenClusteringOptimizer(
                self.config,
                pipeline_distance_calculator=self.hydrogen_pipeline_calculator
            )
            logger.info("氢气聚类优化器初始化完成")

            hydrogen_location_dict = {
                loc: self.locations[loc] for loc in self.hydrogen_locations
            }

            if len(hydrogen_location_dict) > 0:
                # 使用 source_type='auto' 自动检测氢源类型
                self.clustering_results = self.hydrogen_clustering_optimizer.cluster_hydrogen_plants(
                    hydrogen_location_dict,
                    source_type='auto'
                )

                # 🚀 性能优化：移除预计算循环，改为延迟计算
                # 路径将在_get_hydrogen_transport_distance_with_clustering()中按需计算和缓存
                # 这避免了计算大量从未使用的路径，显著减少数据加载时间
                logger.info(f"氢气聚类完成: {self.clustering_results.total_clusters}个聚类, "
                          f"{self.clustering_results.total_noise_points}个独立点")
                logger.info("管道路径将按需计算（延迟计算模式）")

                # 🚀🚀 超图优化器：预计算所有最短路径（如果启用）
                use_super_graph = self.config.get('basic_parameters', {}).get('use_super_graph_optimizer', False)
                if use_super_graph and SUPER_GRAPH_AVAILABLE and SuperGraphOptimizer is not None:
                    logger.info("=" * 70)
                    logger.info("🚀 启用超图优化器，开始构建超级图...")
                    logger.info("=" * 70)

                    # 准备CO2捕获源数据（Coal Hydrogen使用煤炭气化厂位置）
                    co2_capture_sources = {}
                    for loc_id in self.hydrogen_locations:
                        if loc_id in self.locations:
                            co2_capture_sources[loc_id] = {
                                'latitude': self.locations[loc_id]['latitude'],
                                'longitude': self.locations[loc_id]['longitude']
                            }

                    # 读取超图配置
                    super_graph_config_dict = self.config.get('super_graph_config', {})
                    super_graph_config = SuperGraphConfig(
                        k_connections=super_graph_config_dict.get('k_connections', 10),
                        algorithm=super_graph_config_dict.get('algorithm', 'johnson'),
                        include_route_geometry=super_graph_config_dict.get('include_route_geometry', False),
                        cache_to_disk=super_graph_config_dict.get('cache_to_disk', False)
                    )

                    # 初始化超图优化器
                    self.super_graph_optimizer = SuperGraphOptimizer(
                        pipeline_calculator=self.hydrogen_pipeline_calculator,
                        co2_clustering_results=self.clustering_results,
                        co2_capture_sources=co2_capture_sources,
                        locations=self.locations,  # SAF工厂位置
                        config=super_graph_config
                    )

                    # 构建超图并预计算所有距离
                    self.super_graph_optimizer.build_and_precompute()
                    logger.info("✓ 超图优化器初始化完成！后续距离查询将使用O(1)超图查找")
                else:
                    self.super_graph_optimizer = None
                    if use_super_graph:
                        logger.warning("配置启用了超图优化器，但模块不可用，将使用传统方法")

        except Exception as e:
            logger.error(f"初始化氢气聚类失败: {e}")
            import traceback
            traceback.print_exc()
            # 重新抛出异常，确保聚类初始化失败时立即终止程序
            # 避免clustering_results保持None导致后续调用时才报错
            raise RuntimeError(
                f"氢气管道距离计算器聚类初始化失败。\n"
                f"请检查以下内容：\n"
                f"1. GIS数据文件是否存在于 products/gis_energy_mapping/gis_data_scraper/scraped_gis_data/\n"
                f"2. 氢气生产位置数据是否正确\n"
                f"3. 配置文件中的 basic_parameters.use_hydrogen_pipeline_distance 是否正确设置\n"
                f"原始错误: {str(e)}"
            )

        # 验证聚类结果是否正确初始化（额外保险）
        if self.clustering_results is None:
            raise RuntimeError(
                "聚类初始化函数执行完成，但clustering_results仍为None！\n"
                "这可能是由于以下原因：\n"
                "  1. hydrogen_location_dict为空（没有氢气生产位置）\n"
                f"     当前氢气位置数量: {len(self.hydrogen_locations)}\n"
                "  2. cluster_hydrogen_plants函数返回了None\n"
                "请检查数据和聚类优化器实现。"
            )

    def _initialize_co2_clustering(self):
        """初始化CO2捕获源聚类（v3.0: 已禁用，煤炭气化路线不需要CO₂捕获和运输）"""
        logger.info("v3.0煤炭气化路线不需要CO₂聚类，跳过初始化")
        return

        # 以下代码在v3.0中不再使用（保留供参考）
        # 检查是否启用CO2管道距离计算
        if not self.config.get('basic_parameters', {}).get('use_co2_pipeline_distance', False):
            logger.info("CO2管道距离计算未启用，跳过CO2聚类初始化")
            return

        # 检查CO2聚类优化器是否可用
        if CO2ClusteringOptimizer is None:
            raise ImportError(
                "CO2聚类优化器模块不可用，无法进行CO2聚类。\n"
                "请检查以下内容：\n"
                "  1. co2_clustering_optimizer.py文件是否存在于hydrogen/目录下\n"
                "  2. CO2ClusteringOptimizer类是否正确实现\n"
                "  3. 模块导入路径是否正确"
            )

        try:
            logger.info("="*60)
            logger.info("开始初始化CO2捕获源聚类...")
            logger.info(f"CO2捕获源数量: {len(self.co2_capture_sources)}")

            # 初始化CO2聚类优化器（使用与氢气相同的管道距离计算器）
            self.co2_clustering_optimizer = CO2ClusteringOptimizer(
                self.config,
                pipeline_distance_calculator=self.hydrogen_pipeline_calculator
            )
            logger.info("CO2聚类优化器创建成功")

            # 准备CO2捕获源字典（格式：{location_id: {latitude, longitude, co2_capture_capacity_ton_per_week}}）
            co2_location_dict = {}
            for location_id, coords in self.co2_capture_sources.items():
                co2_location_dict[location_id] = {
                    'latitude': coords['latitude'],
                    'longitude': coords['longitude'],
                    'co2_capture_capacity_ton_per_week': coords.get('co2_capture_capacity_ton_per_week', 0)
                }

            logger.info(f"准备聚类CO2捕获源字典，共{len(co2_location_dict)}个位置")

            # 执行CO2聚类（可选：传入目标位置坐标用于优化聚类中心）
            # 这里使用机场的平均位置作为目标位置（与氢气运输目标一致）
            if len(self.airports) > 0:
                airport_lats = [airport['latitude'] for airport in self.airports.values()]
                airport_lons = [airport['longitude'] for airport in self.airports.values()]
                destination_coords = (
                    sum(airport_lats) / len(airport_lats),
                    sum(airport_lons) / len(airport_lons)
                )
            else:
                destination_coords = None

            # 调用聚类方法
            self.co2_clustering_results = self.co2_clustering_optimizer.cluster_co2_sources(
                co2_location_dict,
                destination_coords=destination_coords
            )

            logger.info(f"CO2聚类完成！")
            logger.info(f"  - 聚类数量: {self.co2_clustering_results.total_clusters}")
            logger.info(f"  - 独立点数量: {self.co2_clustering_results.total_noise_points}")
            logger.info(f"  - 总CO2捕获源: {len(co2_location_dict)}")
            logger.info("="*60)

            # 初始化聚类路径字典（用于存储聚类运输路径）
            self.co2_clustered_routes = {}

        except Exception as e:
            logger.error(f"初始化CO2聚类失败: {e}")
            import traceback
            traceback.print_exc()
            raise RuntimeError(
                f"CO2聚类初始化失败: {str(e)}\n"
                "请检查以下内容：\n"
                "  1. CO2捕获源数据是否正确加载\n"
                "  2. 聚类参数设置是否合理\n"
                "  3. 管道距离计算器是否正常工作\n"
                "  4. 查看完整错误堆栈信息"
            )

        # 验证聚类结果是否正确初始化
        if self.co2_clustering_results is None:
            raise RuntimeError(
                "CO2聚类初始化函数执行完成，但co2_clustering_results仍为None！\n"
                "这可能是由于以下原因：\n"
                "  1. co2_location_dict为空（没有CO2捕获源）\n"
                f"     当前CO2捕获源数量: {len(self.co2_capture_sources)}\n"
                "  2. cluster_co2_sources函数返回了None\n"
                "请检查数据和CO2聚类优化器实现。"
            )

    def _get_location_coordinates(self, location: str) -> tuple:
        """
        获取位置的经纬度坐标 - 现在统一从self.locations获取
        
        Args:
            location: 位置名称
            
        Returns:
            (纬度, 经度) 元组
        """
        # 统一从基础locations字典获取坐标
        if location in self.locations:
            return (self.locations[location]['latitude'], self.locations[location]['longitude'])

        # 兼容性处理：如果是旧的命名方式，尝试转换
        if location in self.airports:
            return (self.airports[location]['latitude'], self.airports[location]['longitude'])

        # 检查是否是机场集成位置（兼容性处理）
        if location.startswith('airport_integrated_'):
            airport_name = location.replace('airport_integrated_', '')
            if airport_name in self.airports:
                return (self.airports[airport_name]['latitude'], self.airports[airport_name]['longitude'])
        
        # 检查是否是综合供应位置 - 抛出错误而不是使用默认坐标
        if location.startswith('integrated_supply_'):
            raise ValueError(f"综合供应位置 {location} 缺少有效坐标信息")
        
        # 如果找不到位置，抛出错误而不是返回默认坐标
        raise ValueError(f"位置 {location} 不存在或缺少坐标信息")
    
    def _define_technologies(self):
        """定义MTJ航煤生产技术（使用统一的基础平准化成本，加上模式特定的复杂度调整）"""
        # 获取基础平准化产品成本 (元/kg)
        base_lcop = self.costs.get('mtj_base_lcop_yuan_per_kg', 808.0)
        
        # 从配置文件加载技术参数
        tech_config = self.config['technologies']
        
        # 定义各技术模式的复杂度调整因子
        complexity_factors = tech_config['complexity_factors']
        
        # 构建技术配置，从配置文件加载各个技术的详细参数
        self.technologies = {}

        # 绿氢+CO₂制SAF供应链：只使用两步法工艺（green_h2_co2_to_saf）
        # 第一步：H₂ + CO₂ → 甲醇 (E-CRM电化学还原)
        # 第二步：甲醇 → SAF (MTJ甲醇制航煤)
        for tech_key in ['green_h2_co2_to_saf']:
            if tech_key in tech_config:
                tech_info = tech_config[tech_key]
                # 读取碳消耗比参数(优先carbon_consumption_ratio,兼容旧的co2_consumption_ratio)
                # carbon_consumption_ratio: kg C / kg SAF (碳原子质量)
                # CO₂中碳含量: C/CO₂ = 12/44 ≈ 0.273
                carbon_ratio = tech_info.get('carbon_consumption_ratio', None)
                co2_ratio = tech_info.get('co2_consumption_ratio', None)

                if carbon_ratio is not None:
                    # 使用碳消耗比(kg C/kg SAF)
                    # 转换为CO₂消耗比: CO₂ = C × (44/12) = C × 3.667
                    carbon_consumption_ratio = carbon_ratio
                    co2_consumption_ratio = carbon_ratio * (44.0 / 12.0)  # kg CO₂/kg SAF
                elif co2_ratio is not None:
                    # 使用CO₂消耗比(向后兼容)
                    co2_consumption_ratio = co2_ratio
                    carbon_consumption_ratio = co2_ratio * (12.0 / 44.0)  # kg C/kg SAF
                else:
                    # 默认值
                    carbon_consumption_ratio = 0.75  # kg C/kg SAF
                    co2_consumption_ratio = 2.75  # kg CO₂/kg SAF

                self.technologies[tech_key] = {
                    'name': tech_info['name'],
                    'lcop_yuan_per_kg': base_lcop * complexity_factors.get(tech_key, 1.0),
                    'efficiency': tech_info['efficiency'],
                    'h2_consumption_ratio': tech_info['h2_consumption_ratio'],
                    'carbon_consumption_ratio': carbon_consumption_ratio,  # kg C / kg SAF (碳原子质量)
                    'co2_consumption_ratio': co2_consumption_ratio,  # kg CO₂ / kg SAF (向后兼容)
                    # ✅ v3.1.0: 删除两步法参数，使用一步法（煤制合成气+H₂→SAF）
                    # 'methanol_intermediate_ratio': 已删除
                    # 'methanol_to_saf_ratio': 已删除
                    'suitable_locations': tech_info['suitable_locations'],
                    'transport_mode': tech_info['transport_mode'],
                    'hydrogen_transport_required': tech_info['hydrogen_transport_required'],
                    'technology_type': tech_info['technology_type'],
                    'complexity_factor': complexity_factors.get(tech_key, 1.0)
                }

        logger.info(f"定义了 {len(self.technologies)} 种SAF生产技术（煤制合成气+绿氢一步法）")
        logger.info(f"基础平准化成本: {base_lcop:.0f} 元/kg")

        # 输出碳消耗比参数信息
        for tech_key, tech_data in self.technologies.items():
            logger.info(f"  技术 {tech_key}:")
            logger.info(f"    - 碳消耗比: {tech_data.get('carbon_consumption_ratio', 0):.3f} kg C/kg SAF")
            logger.info(f"    - CO₂消耗比: {tech_data.get('co2_consumption_ratio', 0):.3f} kg CO₂/kg SAF")
            logger.info(f"    - H₂消耗比: {tech_data.get('h2_consumption_ratio', 0):.3f} kg H₂/kg SAF")
        
        # 检查技术参数中的NaN值
        for tech, config in self.technologies.items():
            logger.info(f"  {config['name']}: {config['lcop_yuan_per_kg']:,.0f} 元/kg (复杂度因子: {config['complexity_factor']:.2f})")
            
            # 检查每个技术配置中的数值参数
            for param, value in config.items():
                if isinstance(value, (int, float)) and pd.isna(value):
                    print(f"ERROR: 技术 {tech} 的参数 {param} 包含NaN值: {value}")
                    raise ValueError(f"技术参数包含NaN值: {tech}.{param} = {value}")

    def _get_electrolyzer_capex(self, location: str) -> float:
        """
        根据location的plant_type返回对应的电解槽/副产氢设备CAPEX

        Args:
            location: 位置名称

        Returns:
            CAPEX (元/(kg H₂/hour))
        """
        plant_type = self.locations[location]['type']

        if plant_type == 'byproduct_hydrogen_refinery':
            # 炼油副产氢: 224,000元/(kg H₂/hour), 比钢铁低20%
            return 224000
        elif plant_type == 'byproduct_hydrogen_steel':
            # 钢铁副产氢: 280,000元/(kg H₂/hour)
            return 280000
        else:
            # 绿氢电解槽: 从配置文件读取
            return self.config['equipment_raw_costs']['electrolyzer']['capex_raw']

    def _get_electrolyzer_opex(self, location: str) -> float:
        """
        根据location的plant_type返回对应的电解槽/副产氢设备OPEX

        Args:
            location: 位置名称

        Returns:
            OPEX (元/年)
        """
        plant_type = self.locations[location]['type']

        if plant_type == 'byproduct_hydrogen_refinery':
            # 炼油副产氢: 110,000元/年, 比钢铁低15%
            return 110000
        elif plant_type == 'byproduct_hydrogen_steel':
            # 钢铁副产氢: 130,000元/年
            return 130000
        else:
            # 绿氢电解槽: 从配置文件读取
            return self.config['equipment_raw_costs']['electrolyzer']['opex_raw']

    def _calculate_levelized_cost(self, capex: float, opex_annual: float, lifetime_years: int, 
                                 discount_rate: float, capacity_factor: float = 1.0) -> float:
        """
        计算平准化成本 (LCOE - Levelized Cost of Energy)
        
        Args:
            capex: 初始资本支出 (元)
            opex_annual: 年运营成本 (元/年)
            lifetime_years: 设备使用寿命 (年)
            discount_rate: 贴现率 (年化)
            capacity_factor: 容量因子 (设备利用率)
            
        Returns:
            年化平准化成本 (元/年)
        """
        # 计算资本回收因子 (Capital Recovery Factor)
        if discount_rate == 0:
            crf = 1.0 / lifetime_years
        else:
            crf = (discount_rate * (1 + discount_rate)**lifetime_years) / \
                  ((1 + discount_rate)**lifetime_years - 1)
        
        # 年化资本成本
        annual_capex = capex * crf
        
        # 考虑容量因子的年化平准化成本
        annual_total_cost = annual_capex + opex_annual
        
        return annual_total_cost / capacity_factor

    def _calculate_levelized_product_cost(self, capex_per_unit, fixed_opex_annual, variable_opex_per_product, 
                                        lifetime_years, discount_rate, capacity_factor, actual_annual_production=None):
        """
        平准化产品成本计算 (LCOP - Levelized Cost of Product)
        基于实际优化结果的年产量进行计算
        
        Args:
            capex_per_unit: 初始资本支出，每单位产能 (元/单位产能)
            fixed_opex_annual: 年固定运营成本 (元/年)
            variable_opex_per_product: 单位产品变动运营成本 (元/产品)
            lifetime_years: 设备使用寿命 (年)
            discount_rate: 贴现率 (年化)
            capacity_factor: 容量因子 (设备利用率，仅在无实际产量时作为备用)
            actual_annual_production: 优化结果的实际年产量 (kg/年)，优先使用此值
            
        Returns:
            平准化产品成本 (元/产品)
        """
        # 计算资本回收因子 (Capital Recovery Factor)
        if discount_rate == 0:
            crf = 1.0 / lifetime_years
        else:
            crf = (discount_rate * (1 + discount_rate)**lifetime_years) / \
                  ((1 + discount_rate)**lifetime_years - 1)
        
        # 年化资本成本
        annual_capex = capex_per_unit * crf
        
        # 使用实际年产量（优先）或理论年产量（备用）
        if actual_annual_production is not None and actual_annual_production > 0:
            annual_production = actual_annual_production
            logger.info(f"使用实际优化结果年产量: {annual_production:.2f} kg/年")
        else:
            # 仅在没有实际产量时使用理论值作为备用
            annual_production = 1.0 * 8760 * capacity_factor  # 产品/年
            logger.warning(f"未提供实际产量，使用理论估算: {annual_production:.2f} kg/年")
        
        # 单位产品固定成本 = (年化CAPEX + 年固定OPEX) / 年实际产量
        fixed_cost_per_product = (annual_capex + fixed_opex_annual) / annual_production
        
        # 平准化产品成本 = 单位固定成本 + 单位变动成本
        lcop = fixed_cost_per_product + variable_opex_per_product
        
        return lcop
    
    def _calculate_project_levelized_cost_with_replacement(self, capex: float, opex_annual: float, 
                                                          equipment_lifetime: int, project_lifespan: int,
                                                          discount_rate: float, capacity_factor: float = 1.0) -> float:
        """
        计算考虑设备更换的项目期间平准化成本
        
        Args:
            capex: 初始资本支出 (元)
            opex_annual: 年运营成本 (元/年)
            equipment_lifetime: 设备使用寿命 (年)
            project_lifespan: 项目总寿命 (年)
            discount_rate: 贴现率 (年化)
            capacity_factor: 容量因子 (设备利用率)
            
        Returns:
            项目期间年化平准化成本 (元/年)
        """
        # 计算项目期间内需要的设备更换次数
        replacement_times = []
        current_year = equipment_lifetime
        while current_year < project_lifespan:
            replacement_times.append(current_year)
            current_year += equipment_lifetime
        
        # 计算所有CAPEX的净现值(包括初始投资和更换投资)
        total_capex_npv = capex  # 初始投资
        
        # 添加每次更换的折现成本
        for replacement_year in replacement_times:
            replacement_capex_npv = capex / ((1 + discount_rate) ** replacement_year)
            total_capex_npv += replacement_capex_npv
        
        # 计算运营成本的净现值
        if discount_rate == 0:
            present_value_factor_opex = project_lifespan
        else:
            present_value_factor_opex = (1 - (1 + discount_rate)**(-project_lifespan)) / discount_rate
        opex_npv = opex_annual * present_value_factor_opex
        
        # 计算项目期间总净现值
        total_project_npv = total_capex_npv + opex_npv
        
        # 计算项目期间资本回收因子
        if discount_rate == 0:
            project_crf = 1.0 / project_lifespan
        else:
            project_crf = (discount_rate * (1 + discount_rate)**project_lifespan) / \
                         ((1 + discount_rate)**project_lifespan - 1)
        
        # 年化成本
        annual_cost = total_project_npv * project_crf
        
        return annual_cost / capacity_factor
    
    def _calculate_lifecycle_production_from_optimization(self):
        """
        基于优化结果计算全生命周期实际产量
        这个方法在求解后调用，使用实际的production_vars值

        Returns:
            dict: 包含各设施全生命周期产量的字典
        """
        project_lifespan = self.economic_params['project_lifespan']
        discount_rate = self.economic_params.get('discount_rate', 0.08)

        # 计算现值系数（用于考虑折现的生命周期产量计算）
        if discount_rate == 0:
            present_value_factor = project_lifespan
        else:
            present_value_factor = (1 - (1 + discount_rate)**(-project_lifespan)) / discount_rate

        lifecycle_production = {}

        # 累计优化期间的实际产量
        for key in self.production_vars:
            location, tech, hour = key
            facility_key = (location, tech)
            
            if facility_key not in lifecycle_production:
                lifecycle_production[facility_key] = 0
            
            # 获取实际优化结果的产量值
            actual_production = self.production_vars[key].x if hasattr(self.production_vars[key], 'x') else 0
            lifecycle_production[facility_key] += actual_production
        
        # 基于优化时间范围推算全生命周期
        if self.time_horizon_weeks == 1:
            # 基于1周数据推算20年（假设每周产量模式重复）
            # 使用现值等效周数而不是简单的52*20
            weeks_in_lifecycle = 52 * present_value_factor
            for facility_key in lifecycle_production:
                lifecycle_production[facility_key] *= weeks_in_lifecycle
                
        elif self.time_horizon_weeks >= 52:
            # 基于年度数据推算20年
            years_in_optimization = self.time_horizon_weeks / 52
            years_in_lifecycle = project_lifespan
            scaling_factor = years_in_lifecycle / years_in_optimization
            for facility_key in lifecycle_production:
                lifecycle_production[facility_key] *= scaling_factor
        
        else:
            # 基于多周数据推算20年
            weeks_per_year = 52
            years_in_lifecycle = project_lifespan
            # 先年化，再乘以生命周期年数
            annual_scaling = weeks_per_year / self.time_horizon_weeks
            for facility_key in lifecycle_production:
                lifecycle_production[facility_key] *= annual_scaling * years_in_lifecycle
        
        return lifecycle_production
    
    def _estimate_lifecycle_production_for_lcoe(self, location, tech, facility_capacity):
        """
        为LCOE计算估算生命周期产量
        这个方法在优化前使用，基于设施容量和预期利用率估算
        
        Args:
            location: 设施位置
            tech: 技术类型
            facility_capacity: 设施容量 (kg/h)
            
        Returns:
            float: 估算的生命周期产量 (kg)
        """
        project_lifespan = self.economic_params['project_lifespan']
        
        # 估算年度产量（不再假设满负荷运行）
        # 基于历史数据或经验估算实际利用率
        if self.time_horizon_weeks == 1:
            # 基于1周优化估算：假设设施平均利用率为60%（考虑原材料约束等）
            estimated_utilization_rate = 0.60
        else:
            # 基于更长期优化：利用率可能更高
            estimated_utilization_rate = 0.75
        
        # 年产量 = 设施容量 × 年度小时数 × 实际利用率
        annual_hours = 8760
        annual_production = facility_capacity * annual_hours * estimated_utilization_rate
        
        # 生命周期产量
        # 使用现值系数计算生命周期等效产量
        if discount_rate == 0:
            present_value_factor_local = project_lifespan
        else:
            present_value_factor_local = (1 - (1 + discount_rate)**(-project_lifespan)) / discount_rate
        lifecycle_production = annual_production * present_value_factor_local
        
        return lifecycle_production
    
    
    def _define_economic_parameters(self):
        """定义经济参数"""
        # 从配置文件加载经济参数
        economic_config = self.config['economic_parameters']
        capacity_factors = economic_config['capacity_factors']
        
        # 平准化成本门槛值
        levelized_cost_threshold = economic_config.get('levelized_cost_threshold_yuan_per_kg', 5.62)

        # [DEBUG] 打印加载的平准化成本门槛值
        logger.info("="*80)
        logger.info("[敏感性分析-参数验证] 从配置文件读取的平准化成本门槛值:")
        logger.info(f"  economic_parameters.levelized_cost_threshold_yuan_per_kg = {levelized_cost_threshold} 元/kg")
        logger.info("="*80)

        self.economic_params = {
            'discount_rate': economic_config['discount_rate'],
            'project_lifespan': economic_config['project_lifespan'],
            'mtj_plant_lifetime': economic_config['saf_reactor_lifetime'],
            'electrolyzer_lifetime': economic_config['electrolyzer_lifetime'],
            'pipeline_lifetime': economic_config['pipeline_lifetime'],
            'storage_lifetime': economic_config['storage_lifetime'],
            'transport_vehicle_lifetime': economic_config['transport_vehicle_lifetime'],

            # 容量因子 (设备年利用率)
            'mtj_plant_capacity_factor': capacity_factors['saf_reactor_capacity_factor'],
            'electrolyzer_capacity_factor': capacity_factors['electrolyzer_capacity_factor'],
            'pipeline_capacity_factor': capacity_factors['pipeline_capacity_factor'],
            'storage_capacity_factor': capacity_factors['storage_capacity_factor'],
            'transport_capacity_factor': capacity_factors['transport_capacity_factor'],

            # 平准化成本门槛值
            'levelized_cost_threshold_yuan_per_kg': levelized_cost_threshold
        }
    
    def _define_costs(self):
        """定义成本参数（使用平准化成本方法考虑整个生命周期）"""
        # 首先定义经济参数
        self._define_economic_parameters()
        
        # 定义MTJ生产技术的基础工程成本数据
        mtj_base_costs = self._estimate_mtj_production_costs()
        
        # 从配置文件加载成本参数
        cost_config = self.config['cost_parameters']
        equipment_costs = self.config['equipment_raw_costs']

        # 定义原始资本和运营成本数据
        raw_costs = {
            # 原料成本 (元/单位) - 运营成本，无需平准化
            # 绿氢供应链：主要原料是可再生电力和氢气
            'hydrogen_market_price_yuan_per_kg': (
                cost_config.get('unified_costs', {}).get('raw_materials', {}).get('hydrogen_market_price_yuan_per_kg') or
                cost_config['raw_materials']['hydrogen_market_price_yuan_per_kg']
            ),
            'renewable_electricity_cost_yuan_per_mwh': cost_config['raw_materials']['renewable_electricity_cost_yuan_per_mwh'],

            # MTJ生产设施原始成本（基于工程估算）
            'mtj_plant_capex_raw': mtj_base_costs['capex_per_kg_hour'],         # 元/(kg/hour) 产能投资
            'mtj_plant_fixed_opex_raw': mtj_base_costs['fixed_opex_annual'],    # 元/年 固定运营成本
            'mtj_plant_variable_opex_raw': mtj_base_costs['variable_opex_per_kg'], # 元/kg 变动运营成本

            # 电解槽原始成本
            'electrolyzer_capex_raw': equipment_costs['electrolyzer']['capex_raw'],
            'electrolyzer_opex_raw': equipment_costs['electrolyzer']['opex_raw'],

            # 储存设施原始成本 - 优先使用统一成本配置
            'storage_capex_raw': (
                cost_config.get('unified_costs', {}).get('storage', {}).get('facility_investment_yuan_per_kg') or
                equipment_costs['storage']['capex_raw']
            ),
            'storage_opex_raw': (
                cost_config.get('unified_costs', {}).get('storage', {}).get('facility_operation_yuan_per_kg_year') or
                equipment_costs['storage']['opex_raw']
            )
        }

        # 计算平准化成本参数
        # 先检查raw_costs中的NaN值
        for key, value in raw_costs.items():
            if isinstance(value, (int, float)) and pd.isna(value):
                print(f"ERROR: raw_costs中的参数 {key} 包含NaN值: {value}")
                raise ValueError(f"原始成本参数包含NaN值: {key} = {value}")

        self.costs = {
            # 原料成本保持不变（运营成本）
            'hydrogen_market_price_yuan_per_kg': raw_costs['hydrogen_market_price_yuan_per_kg'],
            'renewable_electricity_cost_yuan_per_mwh': raw_costs['renewable_electricity_cost_yuan_per_mwh'],


            # 电解制氢参数
            'electrolysis_efficiency': cost_config['electrolysis']['electrolysis_efficiency'],
            'electrolysis_power_consumption': cost_config['electrolysis']['electrolysis_power_consumption'],
            
            
            # 短缺惩罚成本（提高到足够高的水平，使建厂更经济）
            'shortage_penalty_yuan_per_kg': cost_config['shortage_penalty_yuan_per_kg'],
        }
        
        # 计算平准化的设施成本（年化投资成本 + 运营成本）
        discount_rate = self.economic_params['discount_rate']
        
        # MTJ生产设施平准化成本（修正版 - 使用正确的LCOP计算）
        mtj_base_lcop = self._calculate_levelized_product_cost(
            capex_per_unit=mtj_base_costs['capex_per_kg_hour'],               # 元/(kg/hour)
            fixed_opex_annual=mtj_base_costs['fixed_opex_annual'],            # 元/年
            variable_opex_per_product=mtj_base_costs['variable_opex_per_kg'],  # 元/kg
            lifetime_years=self.economic_params['mtj_plant_lifetime'],
            discount_rate=discount_rate,
            capacity_factor=self.economic_params['mtj_plant_capacity_factor']
        )
        
        # 存储MTJ基础平准化产品成本 (元/kg)
        self.costs['mtj_base_lcop_yuan_per_kg'] = mtj_base_lcop
        logger.info(f"基础平准化成本: {mtj_base_lcop:.0f} 元/kg")
        
        # 电解槽平准化成本（考虑15年寿命内需要更换的成本）
        project_lifespan = self.economic_params['project_lifespan']
        electrolyzer_lifetime = self.economic_params['electrolyzer_lifetime']
        
        if electrolyzer_lifetime < project_lifespan:
            # 使用包含更换成本的计算方法
            electrolyzer_levelized_cost = self._calculate_project_levelized_cost_with_replacement(
                capex=raw_costs['electrolyzer_capex_raw'],
                opex_annual=raw_costs['electrolyzer_opex_raw'],
                equipment_lifetime=electrolyzer_lifetime,
                project_lifespan=project_lifespan,
                discount_rate=discount_rate,
                capacity_factor=self.economic_params['electrolyzer_capacity_factor']
            )
            logger.info(f"电解槽需在第{electrolyzer_lifetime}年更换，总项目期间平准化成本已计算更换费用")
        else:
            # 使用标准平准化成本计算
            electrolyzer_levelized_cost = self._calculate_levelized_cost(
                capex=raw_costs['electrolyzer_capex_raw'],
                opex_annual=raw_costs['electrolyzer_opex_raw'],
                lifetime_years=electrolyzer_lifetime,
                discount_rate=discount_rate,
                capacity_factor=self.economic_params['electrolyzer_capacity_factor']
            )
            
        self.costs['electrolyzer_capex_yuan_per_kg_h2_year'] = electrolyzer_levelized_cost
        self.costs['electrolyzer_opex_yuan_per_kg_h2'] = 0  # 已包含在平准化成本中
        
        # 储存设施平准化成本
        storage_levelized_cost = self._calculate_levelized_cost(
            capex=raw_costs['storage_capex_raw'],
            opex_annual=raw_costs['storage_opex_raw'],
            lifetime_years=self.economic_params['storage_lifetime'],
            discount_rate=discount_rate,
            capacity_factor=self.economic_params['storage_capacity_factor']
        )
        self.costs['storage_cost_yuan_per_kg_hour'] = storage_levelized_cost / 8760  # 小时成本
        self.costs['hydrogen_storage_cost_yuan_per_kg_hour'] = storage_levelized_cost / 8760  # 氢气储存
        
        # 移除对外部成本分析器的依赖，直接在优化模型内部计算成本
        # 成本分析功能已集成到 _calculate_unit_costs_from_optimization 方法中
        self.cost_analyzer = None
        logger.info("使用优化模型内部成本计算，不依赖外部成本分析器")
    
    def _estimate_mtj_production_costs(self):
        """
        基于facility_lcoe_parameters估算MTJ生产技术的基础成本
        （避免重复定义，统一使用facility_lcoe_parameters配置）
        
        Returns:
            dict: 包含CAPEX、固定OPEX、变动OPEX的基础成本估算
        """
        # 从统一的facility_lcoe_parameters配置获取成本参数
        fac_cfg = self.config.get('facility_lcoe_parameters', {}) or {}
        
        # 从配置获取成本参数 (避免重复定义)
        # variable_capex_per_capacity 相当于总CAPEX每单位产能
        total_capex = fac_cfg.get('variable_capex_per_capacity', 20000)  # 元/(kg/hour)
        
        # 固定运营成本 (按单位产能分摊)
        total_fixed_opex_annual = fac_cfg.get('fixed_opex_annual', 1000000)  # 元/年 (整个工厂)
        # 按标准产能1000 kg/h分摊，得到单位产能的固定成本
        standard_capacity_kg_h = 1000  
        total_fixed_opex = total_fixed_opex_annual / standard_capacity_kg_h  # 元/年 per (kg/hour)
        
        # 变动运营成本 (从生产变动成本配置获取)
        fac_cfg_opex = fac_cfg.get('variable_opex_per_kg', 0.3)  # 元/kg - 使用配置文件的0.3而非300
        total_variable_opex = fac_cfg_opex  # 元/kg产品
        
        # 日志输出参数读取情况
        logger.info(f"MTJ变动运营成本参数读取: {fac_cfg_opex}元/kg (配置文件中值: {fac_cfg.get('variable_opex_per_kg', '未找到')})")
        
        logger.info(f"MTJ生产基础成本估算: CAPEX={total_capex:,.0f}元/(kg/hour), 固定OPEX={total_fixed_opex:,.0f}元/年, 变动OPEX={total_variable_opex:,.0f}元/kg")
        
        return {
            'capex_per_kg_hour': total_capex,
            'fixed_opex_annual': total_fixed_opex,
            'variable_opex_per_kg': total_variable_opex
        }
        
        # 天然气价格将在每条管道数据中单独存储，不需要全局更新
        
        logger.info("成本参数定义完成")
    
    def build_model(self):
        """构建优化模型"""
        logger.info("构建Gurobi优化模型...")

        self.model = gp.Model("NaturalGasSupplyChain")
        # 从配置文件加载求解器参数（TimeLimit忽略不再设置）
        solver_params = self.config.get('solver_parameters', {})

        mip_gap = solver_params.get('MIPGap', 0.01)
        if isinstance(mip_gap, str):
            mip_gap = float(mip_gap)

        threads = solver_params.get('Threads', 4)
        if isinstance(threads, str):
            threads = int(threads)

        if 'TimeLimit' in solver_params:
            logger.info("TimeLimit found in config but will be ignored (no solver time limit applied)")

        self.model.setParam('MIPGap', mip_gap)
        self.model.setParam('Threads', threads)

        # 内存限制参数（防止OOM）
        self.model.setParam('SoftMemLimit', 80)  # 软限制80GB，接近时尝试节省内存继续求解
        self.model.setParam('MemLimit', 100)     # 硬限制100GB，超过则停止并返回当前最佳解

        # MTJ工厂位置映射已在数据加载时构建，这里无需重复调用
        # 创建决策变量
        self._create_variables()

        # 创建成本表达式（在约束和目标函数之前）
        self._create_cost_expressions()

        # 创建约束条件
        self._create_constraints()

        # 创建目标函数
        self._create_objective()
        
        logger.info("模型构建完成")
    
    def _create_variables(self):
        """创建决策变量"""
        logger.info("创建决策变量...")
        
        # 1. 小时级生产变量 X_{i,j,t}
        self.production_vars = {}
        for location in self.locations:
            for tech in self.technologies:
                for hour in range(self.total_hours):
                    var_name = f"prod_{location}_{tech}_{hour}"
                    self.production_vars[(location, tech, hour)] = self.model.addVar(
                        lb=0, ub=GRB.INFINITY, vtype=GRB.CONTINUOUS, name=var_name
                    )
        
        # 2. 设施建设变量 W_{i,j} (二进制变量：是否建设)
        self.facility_vars = {}
        for location in self.locations:
            for tech in self.technologies:
                var_name = f"facility_{location}_{tech}"
                self.facility_vars[(location, tech)] = self.model.addVar(
                    vtype=GRB.BINARY, name=var_name
                )
        
        # 2.1 设施产能决策变量 CAP_{i,j} (连续变量：设施产能 kg/hour)
        self.facility_capacity_vars = {}
        # 读取MTJ容量配置
        mtj_capacity_limit = self.config.get('capacity_limits', {}).get('mtj_max_capacity_kg_per_hour', 10000)
        logger.info(f"MTJ容量配置: 读取到的容量上限 = {mtj_capacity_limit} kg/h")

        # 强制使用正确的MTJ容量限制（临时调试）
        if mtj_capacity_limit != 100000:
            logger.warning(f"MTJ容量配置异常: 期望100000，实际{mtj_capacity_limit}，强制使用100000")
            mtj_capacity_limit = 100000

        logger.info(f"最终使用的MTJ容量限制: {mtj_capacity_limit} kg/h")

        for location in self.locations:
            for tech in self.technologies:
                var_name = f"capacity_{location}_{tech}"
                # MTJ容量限制已确认生效，恢复正常范围
                # 强制验证测试证明：设置50000下界导致不可行，说明有其他约束限制实际容量

                self.facility_capacity_vars[(location, tech)] = self.model.addVar(
                    lb=0, ub=mtj_capacity_limit,
                    vtype=GRB.CONTINUOUS, name=var_name
                )
        
        # 3. 周运输变量 Y_{i,k,w} (从生产地到机场的周运输量)
        self.transport_vars = {}
        for location in self.locations:
            for airport in self.airports:
                for week in range(self.time_horizon_weeks):
                    var_name = f"transport_{location}_{airport}_{week}"
                    self.transport_vars[(location, airport, week)] = self.model.addVar(
                        lb=0, ub=GRB.INFINITY, vtype=GRB.CONTINUOUS, name=var_name
                    )
        
        # 4. 库存变量 S_{i,t} (每小时的库存量)
        self.storage_vars = {}
        for location in self.locations:
            for hour in range(self.total_hours + 1):  # +1 for final inventory
                var_name = f"storage_{location}_{hour}"
                self.storage_vars[(location, hour)] = self.model.addVar(
                    lb=0, ub=GRB.INFINITY, vtype=GRB.CONTINUOUS, name=var_name
                )
        
        # 5. 制氢决策变量 (仅在可再生能源地点)
        self.hydrogen_production_vars = {}  # 小时级制氢量 (kg H2/hour)
        self.electrolyzer_capacity_vars = {}  # 电解槽设施容量 (kg H2/hour)
        self.electrolyzer_facility_vars = {}  # 电解槽建设决策 (二进制)
        self.hydrogen_storage_vars = {}  # 氢气库存 (kg H2)

        # 6. 氢气运输决策变量 (从制氢地到MTJ工厂)
        # self.hydrogen_transport_vars = {}  # 【禁用罐车运输】氢气罐车运输量 (kg H2/week)

        for location in self.locations:
            location_type = self.locations[location]['type']
            # 只在可再生能源地点创建制氢变量
            if location_type in ['solar_plant', 'wind_farm', 'byproduct_hydrogen_steel', 'byproduct_hydrogen_refinery']:
                # 电解槽设施建设决策 (二进制)
                var_name = f"electrolyzer_facility_{location}"
                self.electrolyzer_facility_vars[location] = self.model.addVar(
                    vtype=GRB.BINARY, name=var_name
                )
                
                # 电解槽容量 (连续变量，kg H2/hour)
                var_name = f"electrolyzer_capacity_{location}"
                self.electrolyzer_capacity_vars[location] = self.model.addVar(
                    lb=0, ub=self.config.get('capacity_limits', {}).get('electrolyzer_max_capacity_kg_per_hour', 2000), 
                    vtype=GRB.CONTINUOUS, name=var_name
                )
                
                # 小时级制氢量
                for hour in range(self.total_hours):
                    var_name = f"h2_prod_{location}_{hour}"
                    self.hydrogen_production_vars[(location, hour)] = self.model.addVar(
                        lb=0, ub=GRB.INFINITY, vtype=GRB.CONTINUOUS, name=var_name
                    )
                
                # 氢气库存
                for hour in range(self.total_hours + 1):
                    var_name = f"h2_storage_{location}_{hour}"
                    self.hydrogen_storage_vars[(location, hour)] = self.model.addVar(
                        lb=0, ub=GRB.INFINITY, vtype=GRB.CONTINUOUS, name=var_name
                    )

            # 【修复零产量BUG】为MTJ工厂位置创建氢气库存变量
            elif location_type in ['lng_terminal', 'airport']:
                # MTJ位置需要氢气库存变量来跟踪从管道接收的氢气
                for hour in range(self.total_hours + 1):
                    var_name = f"h2_storage_mtj_{location}_{hour}"
                    self.hydrogen_storage_vars[(location, hour)] = self.model.addVar(
                        lb=0, ub=GRB.INFINITY, vtype=GRB.CONTINUOUS, name=var_name
                    )
        mtj_locations_set = set()
        for tech, tech_locations in self.mtj_locations.items():
            if not hasattr(tech_locations, '__iter__') or isinstance(tech_locations, str):
                continue
            for mtj_loc in tech_locations:
                mtj_locations_set.add(mtj_loc)

        additional_mtj_storage_vars = 0
        for mtj_loc in mtj_locations_set:
            for hour in range(self.total_hours + 1):
                if (mtj_loc, hour) in self.hydrogen_storage_vars:
                    continue
                var_name = f"h2_storage_{mtj_loc}_{hour}"
                self.hydrogen_storage_vars[(mtj_loc, hour)] = self.model.addVar(
                    lb=0, ub=GRB.INFINITY, vtype=GRB.CONTINUOUS, name=var_name
                )
                additional_mtj_storage_vars += 1

        if additional_mtj_storage_vars > 0:
            logger.info(f"补充创建 {additional_mtj_storage_vars} 个MTJ氢气库存变量")

        # 【禁用罐车运输】为提升计算效率，暂时禁用氢气罐车运输计算
        # 8. 创建氢气运输变量 (仅为需要氢气运输的模式，无距离限制)
        """
        logger.info("创建氢气运输变量，无距离限制")

        valid_h2_routes = 0  # 计数有效路线
        for h2_loc in self.hydrogen_locations:
            for tech in self.technologies.keys():
                # 只为需要氢气运输的技术路线创建运输变量
                if not self.technologies[tech]['hydrogen_transport_required']:
                    continue

                if tech not in self.mtj_locations:
                    logger.warning(f"技术 {tech} 不在 mtj_locations 中，跳过氢气运输变量创建")
                    continue

                locations = self.mtj_locations[tech]
                if not hasattr(locations, '__iter__') or isinstance(locations, str):
                    logger.error(f"技术 {tech} 的位置不可迭代: {locations} (类型: {type(locations)})")
                    continue

                for mtj_loc in locations:
                    # 不再检查距离限制，允许所有路径
                    valid_h2_routes += 1
                    # 修改为周级运输变量，与生产时间尺度一致
                    var_name = f"h2_transport_{h2_loc}_{mtj_loc}_week"
                    self.hydrogen_transport_vars[(h2_loc, mtj_loc)] = self.model.addVar(
                        lb=0, ub=GRB.INFINITY, vtype=GRB.CONTINUOUS, name=var_name
                    )

        logger.info(f"创建了 {valid_h2_routes} 条氢气运输路线（无距离限制）")
        """
        logger.info("【禁用罐车运输】跳过氢气罐车运输变量创建，仅使用管道运输")

        # 9. 创建氢能管道运输变量 (与罐车运输并行的选择方案)
        logger.info("创建氢能管道运输变量，作为罐车运输的替代选择")
        
        self.hydrogen_pipeline_transport_vars = {}  # 氢能管道运输变量 (kg H2/week)
        # self.hydrogen_pipeline_facility_vars = {}   # 【禁用管道建设决策】氢能管道建设决策变量 (二进制)
        
        valid_pipeline_routes = 0  # 计数有效管道路线
        total_days = self.total_hours // 24
        
        for h2_loc in self.hydrogen_locations:
            for tech in self.technologies.keys():
                # 只为需要氢气运输的技术路线创建管道变量
                if not self.technologies[tech]['hydrogen_transport_required']:
                    continue
                    
                if tech not in self.mtj_locations:
                    continue
                    
                locations = self.mtj_locations[tech]
                if not hasattr(locations, '__iter__') or isinstance(locations, str):
                    continue
                
                for mtj_loc in locations:
                    # 【禁用管道建设决策】管道建设决策变量 (每条路线一个二进制变量)
                    """
                    pipeline_facility_name = f"h2_pipeline_facility_{h2_loc}_{mtj_loc}"
                    self.hydrogen_pipeline_facility_vars[(h2_loc, mtj_loc)] = self.model.addVar(
                        vtype=GRB.BINARY, name=pipeline_facility_name
                    )
                    """
                    
                    # 管道运输量变量 (天级)
                    valid_pipeline_routes += 1
                    # 氢能管道运输变量改为周级
                    var_name = f"h2_pipeline_transport_{h2_loc}_{mtj_loc}_week"
                    self.hydrogen_pipeline_transport_vars[(h2_loc, mtj_loc)] = self.model.addVar(
                        lb=0, ub=GRB.INFINITY, vtype=GRB.CONTINUOUS, name=var_name
                    )
        
        logger.info(f"创建了 {valid_pipeline_routes} 条氢能管道运输路线")
        # logger.info(f"创建了 {len(self.hydrogen_pipeline_facility_vars)} 个氢能管道建设决策变量")  # 【禁用管道建设决策】
        
        logger.info(f"创建了 {len(self.production_vars)} 个生产变量")
        logger.info(f"创建了 {len(self.facility_vars)} 个设施变量")
        logger.info(f"创建了 {len(self.facility_capacity_vars)} 个设施产能变量")
        logger.info(f"创建了 {len(self.transport_vars)} 个运输变量")
        logger.info(f"创建了 {len(self.storage_vars)} 个库存变量")
        logger.info(f"创建了 {len(self.hydrogen_production_vars)} 个制氢变量")
        logger.info(f"创建了 {len(self.electrolyzer_capacity_vars)} 个电解槽容量变量")
        logger.info(f"创建了 {len(self.hydrogen_storage_vars)} 个氢气库存变量")
        # 10. 创建缺货惩罚变量 (周级需求缺口)
        self.shortage_vars = {}
        for airport in self.airports:
            for week in range(self.time_horizon_weeks):
                var_name = f"shortage_{airport}_{week}"
                self.shortage_vars[(airport, week)] = self.model.addVar(
                    lb=0, ub=GRB.INFINITY, vtype=GRB.CONTINUOUS, name=var_name
                )
        
        logger.info(f"创建了 {len(self.shortage_vars)} 个缺货惩罚变量")
        # logger.info(f"创建了 {len(self.hydrogen_transport_vars)} 个氢气罐车运输变量")  # 【禁用罐车运输】
        logger.info(f"创建了 {len(self.hydrogen_pipeline_transport_vars)} 个氢能管道运输变量")

        # v3.0: 煤炭气化路线不需要CO₂运输变量（CO₂在甲醇厂本地产生）

        # v3.1：一步法不需要甲醇变量（直接 H₂+CO₂→SAF）
        logger.info("v3.1一步法：跳过甲醇变量创建（直接 H₂+CO₂→SAF）")

        self.methanol_production_vars = {}  # 保留空字典以避免代码报错
        self.methanol_inventory_vars = {}   # 保留空字典以避免代码报错

        # 原两步法代码已禁用：
        # # 在所有可以生产甲醇的位置创建变量（即MTJ工厂位置）
        # for tech, tech_locations in self.mtj_locations.items():
        #     if 'green_h2_co2' not in tech:
        #         continue
        #
        #     if not hasattr(tech_locations, '__iter__') or isinstance(tech_locations, str):
        #         continue
        #
        #     for methanol_loc in tech_locations:
        #         # 小时级甲醇生产量
        #         for hour in range(self.total_hours):
        #             var_name = f"methanol_prod_{methanol_loc}_{hour}"
        #             self.methanol_production_vars[(methanol_loc, hour)] = self.model.addVar(
        #                 lb=0, ub=GRB.INFINITY, vtype=GRB.CONTINUOUS, name=var_name
        #             )
        #
        #         # 甲醇库存（小时级）
        #         for hour in range(self.total_hours + 1):  # +1 for final inventory
        #             var_name = f"methanol_storage_{methanol_loc}_{hour}"
        #             self.methanol_inventory_vars[(methanol_loc, hour)] = self.model.addVar(
        #                 lb=0, ub=GRB.INFINITY, vtype=GRB.CONTINUOUS, name=var_name
        #             )

        logger.info(f"v3.1一步法：甲醇变量数 = 0（已禁用两步法）")

        # v3.0新增：煤炭采购决策变量（周级）
        logger.info("创建煤炭采购变量（v3.0煤炭气化路线）")

        self.coal_purchase_vars = {}  # 煤炭采购变量 (周级, kg coal/week)

        # 在所有甲醇生产位置创建煤炭采购变量（煤炭在本地气化产生CO₂）
        for tech, tech_locations in self.mtj_locations.items():
            if 'green_h2_co2' not in tech:
                continue

            if not hasattr(tech_locations, '__iter__') or isinstance(tech_locations, str):
                continue

            for methanol_loc in tech_locations:
                # 周级煤炭采购量
                for week in range(self.time_horizon_weeks):
                    var_name = f"coal_purchase_{methanol_loc}_week_{week}"
                    self.coal_purchase_vars[(methanol_loc, week)] = self.model.addVar(
                        lb=0, ub=GRB.INFINITY, vtype=GRB.CONTINUOUS, name=var_name
                    )

        logger.info(f"创建了 {len(self.coal_purchase_vars)} 个煤炭采购变量（周级）")

        # 13. CO₂库存决策变量（用于时间尺度匹配：周级煤炭气化→小时级消耗）
        logger.info("创建CO₂库存变量（时间尺度匹配：周级供应→小时级消耗）")

        self.co2_inventory_vars = {}  # CO₂库存变量 (小时级, kg CO₂)

        # 在所有接收CO₂的甲醇生产位置创建库存变量
        for tech, tech_locations in self.mtj_locations.items():
            if 'green_h2_co2' not in tech:
                continue

            if not hasattr(tech_locations, '__iter__') or isinstance(tech_locations, str):
                continue

            for methanol_loc in tech_locations:
                # CO₂库存（小时级，用于周级到小时级的时间匹配）
                for hour in range(self.total_hours + 1):  # +1 for final inventory
                    var_name = f"co2_storage_{methanol_loc}_{hour}"
                    self.co2_inventory_vars[(methanol_loc, hour)] = self.model.addVar(
                        lb=0, ub=GRB.INFINITY, vtype=GRB.CONTINUOUS, name=var_name
                    )

        logger.info(f"创建了 {len(self.co2_inventory_vars)} 个CO₂库存变量")

    def _create_constraints(self):
        """创建约束条件"""
        logger.info("创建约束条件...")
        
        # 1. 时间尺度匹配约束
        self._add_time_scale_matching_constraints()
        
        # 2. 生产能力约束
        self._add_production_capacity_constraints()
        
        # 3. 原料供应约束
        self._add_material_supply_constraints()
        
        # 4. 库存平衡约束
        self._add_inventory_balance_constraints()
        
        # 5. 机场需求约束
        self._add_airport_demand_constraints()
        
        # 6. 设施选择约束
        self._add_facility_selection_constraints()
        
        # 7. 制氢约束
        self._add_hydrogen_production_constraints()
        
        # 8. 氢气平衡约束
        self._add_hydrogen_balance_constraints()
        
        # 8.1. 氢气每日产量限制MTJ每日产量约束
        self._add_daily_hydrogen_mtj_constraints()
        
        # 9. 氢气运输约束
        self._add_hydrogen_transport_constraints()

        # 9.1. 氢能管道运输约束
        self._add_hydrogen_pipeline_transport_constraints()

        # v3.0: 煤炭气化路线不需要CO₂供应平衡约束（CO₂来自煤炭气化）
        # self._add_co2_supply_balance_constraints()

        # v3.1: 一步法不需要甲醇中间变量和相关约束（直接 H₂+CO₂→SAF）
        # 11. 甲醇生产约束（已禁用，v3.1改为一步法）
        # self._add_methanol_production_constraints()

        # 12. SAF生产约束（已禁用，v3.1改为一步法）
        # self._add_saf_production_from_methanol_constraints()

        # 13. 甲醇库存平衡约束（已禁用，v3.1改为一步法）
        # self._add_methanol_inventory_balance_constraints()

        # 14. CO₂库存平衡约束（时间尺度匹配：周级供应→小时级消耗）
        self._add_co2_inventory_balance_constraints()

        # 15. 平准化成本约束
        self._add_levelized_cost_constraint()  # 已修复门槛值配置，重新启用

        # 16. 有效不等式（收紧LP Relaxation，加速MIP求解）
        self._add_valid_inequalities()

    def _add_levelized_cost_constraint(self):
        """添加平准化成本约束：(总成本 - 短缺成本) / 总产量现值 <= 门槛值"""
        logger.info("添加平准化成本约束...")

        # 获取约束参数
        threshold = self.economic_params.get('levelized_cost_threshold_yuan_per_kg', 5.62)
        logger.info(f"平准化成本门槛值: {threshold} 元/kg")

        # 获取经济参数
        discount_rate = self.economic_params['discount_rate']
        project_lifespan = self.economic_params['project_lifespan']

        # 计算现值系数（与成本表达式创建中的计算保持一致）
        if discount_rate == 0:
            present_value_factor = project_lifespan
        else:
            present_value_factor = (1 - (1 + discount_rate)**(-project_lifespan)) / discount_rate

        # 运营成本扩展系数：将时间窗口运营成本扩展到20年生命周期现值
        operation_expansion_factor = 52.0 / self.time_horizon_weeks  # 年化系数（1周→52周）
        lifecycle_operation_factor = operation_expansion_factor * present_value_factor

        # 计算总产量的现值（修正：与平准化成本计算中的产量计算保持一致）
        # 先计算时间窗口内的总产量，然后年化，最后现值化
        weekly_production_expr = gp.quicksum(
            self.production_vars[(location, tech, hour)]
            for location in self.locations
            for tech in self.technologies
            for hour in range(self.total_hours)
            if (location, tech, hour) in self.production_vars
        )

        # 年化产量现值：周产量 × 年化系数 × 现值系数
        lifecycle_present_value_production_expr = weekly_production_expr * operation_expansion_factor * present_value_factor

        # 平准化成本约束：(总成本 - 短缺成本) <= 门槛值 * 总产量现值
        # 转换为标准形式：(总成本 - 短缺成本) - 门槛值 * 总产量现值 <= 0
        levelized_cost_lhs = (
            self.cost_aggregates['total_cost_excluding_shortage'] -
            threshold * lifecycle_present_value_production_expr
        )

        # 添加约束
        constraint = self.model.addConstr(
            levelized_cost_lhs <= 0,
            name="levelized_cost_constraint"
        )

        logger.info(f"平准化成本约束添加完成")
        logger.info(f"约束形式: (总成本 - 短缺成本) - {threshold} * 总产量现值 <= 0")
        logger.info(f"现值系数: {present_value_factor:.4f}")
        logger.info(f"年化系数: {operation_expansion_factor:.4f}")
        logger.info(f"产量现值化系数: {operation_expansion_factor * present_value_factor:.4f}")
        logger.info(f"修正前的错误系数(lifecycle_operation_factor): {lifecycle_operation_factor:.4f}")

        return constraint

    def remove_levelized_cost_constraint(self):
        """
        移除平准化成本约束 (用于敏感性分析)
        允许在不重建整个模型的情况下更新约束参数
        """
        try:
            constr = self.model.getConstrByName("levelized_cost_constraint")
            if constr is not None:
                self.model.remove(constr)
                self.model.update()
                logger.info("已移除平准化成本约束")
                return True
            else:
                logger.warning("未找到名为'levelized_cost_constraint'的约束")
                return False
        except Exception as e:
            logger.error(f"移除约束失败: {e}")
            return False

    def add_levelized_cost_constraint_with_threshold(self, threshold: float):
        """
        使用指定threshold添加平准化成本约束
        (用于敏感性分析,避免重建整个模型)

        Args:
            threshold: 平准化成本门槛值 (元/kg)

        Returns:
            添加的约束对象
        """
        logger.info(f"添加平准化成本约束 (threshold={threshold} 元/kg)...")

        # 获取经济参数
        discount_rate = self.economic_params['discount_rate']
        project_lifespan = self.economic_params['project_lifespan']

        # 计算现值系数
        if discount_rate == 0:
            present_value_factor = project_lifespan
        else:
            present_value_factor = (1 - (1 + discount_rate)**(-project_lifespan)) / discount_rate

        # 运营成本扩展系数
        operation_expansion_factor = 52.0 / self.time_horizon_weeks

        # 计算总产量的现值
        weekly_production_expr = gp.quicksum(
            self.production_vars[(location, tech, hour)]
            for location in self.locations
            for tech in self.technologies
            for hour in range(self.total_hours)
            if (location, tech, hour) in self.production_vars
        )

        # 年化产量现值
        lifecycle_present_value_production_expr = weekly_production_expr * operation_expansion_factor * present_value_factor

        # 平准化成本约束
        levelized_cost_lhs = (
            self.cost_aggregates['total_cost_excluding_shortage'] -
            threshold * lifecycle_present_value_production_expr
        )

        # 添加约束
        constraint = self.model.addConstr(
            levelized_cost_lhs <= 0,
            name="levelized_cost_constraint"
        )
        self.model.update()

        logger.info(f"平准化成本约束添加完成 (threshold={threshold})")

        return constraint

    def update_threshold_and_resolve(self, threshold: float) -> Dict:
        """
        更新threshold并重新求解 (敏感性分析专用接口)
        不重新加载数据和重建模型,只更新约束参数

        Args:
            threshold: 新的平准化成本门槛值 (元/kg)

        Returns:
            求解结果字典
        """
        logger.info("="*80)
        logger.info(f"[敏感性分析] 更新threshold={threshold}并重新求解")
        logger.info("="*80)

        # 移除旧约束
        self.remove_levelized_cost_constraint()

        # 添加新约束
        self.add_levelized_cost_constraint_with_threshold(threshold)

        # 重新求解
        logger.info("开始重新求解模型...")
        solution = self.solve()

        return solution


    def _create_cost_expressions(self):
        """创建所有成本表达式对象（用于目标函数和约束）"""
        logger.info("创建统一的成本表达式对象...")

        # 初始化成本表达式存储结构
        self.cost_expressions = {}  # 存储所有成本项的表达式对象
        self.cost_aggregates = {}   # 存储聚合成本表达式

        # 定义时间相关常量
        total_days = self.total_hours // 24

        # 读取目标函数系数配置（带默认值，保证向后兼容）
        obj_cfg = self.config.get('objective_coefficients', {}) or {}
        transport_cfg = obj_cfg.get('transport', {}) or {}
        storage_cfg = obj_cfg.get('storage', {}) or {}

        # 获取经济参数
        discount_rate = self.economic_params['discount_rate']
        project_lifespan = self.economic_params['project_lifespan']

        # 计算现值系数（用于运营成本折现）
        if discount_rate == 0:
            present_value_factor = project_lifespan  # 无折现时的累计系数
        else:
            # 计算20年运营成本的现值系数
            present_value_factor = (1 - (1 + discount_rate)**(-project_lifespan)) / discount_rate

        # 运营成本扩展系数：将时间窗口运营成本扩展到20年生命周期现值
        operation_expansion_factor = 52.0 / self.time_horizon_weeks  # 年化系数（1周→52周）
        lifecycle_operation_factor = operation_expansion_factor * present_value_factor  # 20年生命周期现值系数

        # 1. MTJ生产设施投资成本（项目开始时的一次性投资）
        fac_cfg = self.config.get('facility_lcoe_parameters', {}) or {}
        fixed_capex = fac_cfg.get('fixed_capex', 20000000)
        variable_capex_per_capacity = fac_cfg.get('variable_capex_per_capacity', 20000)
        self.cost_expressions['facility_investment_cost'] = gp.quicksum(
            self.facility_vars[(location, tech)] * fixed_capex +
            self.facility_capacity_vars[(location, tech)] * variable_capex_per_capacity *
            self.economic_params['mtj_plant_capacity_factor']
            for location in self.locations
            for tech in self.technologies
        )

        # 2. MTJ生产设施运营成本（20年现值）
        fixed_opex_annual = fac_cfg.get('fixed_opex_annual', 1000000)
        self.cost_expressions['facility_operation_cost'] = gp.quicksum(
            self.facility_vars[(location, tech)] * fixed_opex_annual * present_value_factor
            for location in self.locations
            for tech in self.technologies
        )

        # 3. 生产变动运营成本（20年生命周期现值）
        variable_opex_per_kg = fac_cfg.get('variable_opex_per_kg', 0.3)  # 元/kg - 修正默认值从300到0.3
        logger.info(f"成本表达式中使用的MTJ变动运营成本: {variable_opex_per_kg}元/kg")
        self.cost_expressions['production_cost'] = gp.quicksum(
            self.production_vars[(location, tech, hour)] * variable_opex_per_kg * lifecycle_operation_factor
            for location in self.locations
            for tech in self.technologies
            for hour in range(self.total_hours)
            if (location, tech, hour) in self.production_vars
        )

        # 4. 运输运营成本现值
        self.cost_expressions['transport_operation_cost'] = gp.quicksum(
            self.transport_vars[(location, airport, week)] *
            self._calculate_mtj_transport_cost_by_distance(
                self._calculate_distance(location, airport)
            ) * lifecycle_operation_factor  # 20年运营成本现值，基于运输理论公式
            for location in self.locations
            for airport in self.airports
            for week in range(self.time_horizon_weeks)
            if (location, airport, week) in self.transport_vars
        )

        # 5. 储存设施投资成本 + 20年运营成本现值
        # 修正：储存设备成本应基于各地点的最大库存量之和，而非所有时间点库存量之和
        # 创建辅助变量来捕获各地点的最大库存量
        max_storage_by_location = {}
        for location in self.locations:
            max_var = self.model.addVar(
                lb=0, ub=GRB.INFINITY,
                vtype=GRB.CONTINUOUS,
                name=f'max_mtj_storage_{location}'
            )
            # 约束：max_var必须大于等于该地点在任何时刻的库存量
            for hour in range(self.total_hours + 1):
                self.model.addConstr(
                    max_var >= self.storage_vars[(location, hour)],
                    name=f'max_mtj_storage_constr_{location}_h{hour}'
                )
            max_storage_by_location[location] = max_var

        # 总的储存设备需求 = 各地点最大库存量之和
        max_storage_needed = gp.quicksum(max_storage_by_location.values())

        # 优先使用统一成本配置中的MTJ储存设备成本
        storage_unit_cost = float(
            self.config.get('unified_costs', {}).get('storage', {}).get('mtj_equipment_cost_yuan_per_kg') or
            storage_cfg.get('equipment_unit_cost_yuan_per_kg', 10)
        )
        self.cost_expressions['storage_equipment_cost'] = max_storage_needed * storage_unit_cost

        # MTJ库存运营成本：使用平均库存（峰值/2）而非所有时刻库存总和
        # 运营成本 = Σ(各地点最大库存/2) × 小时成本 × 总小时数 × 生命周期系数
        average_storage_total = gp.quicksum(max_storage_by_location.values()) / 2.0
        self.cost_expressions['storage_operation_cost'] = (
            average_storage_total *
            self._calculate_total_storage_cost_per_kg_hour() *
            self.total_hours *
            lifecycle_operation_factor
        )

        # 6. 电解槽投资成本（一次性投资）
        electrolyzer_capex_raw = self.config['equipment_raw_costs']['electrolyzer']['capex_raw']
        logger.info(f"电解槽投资成本参数: {electrolyzer_capex_raw} 元/(kg H₂/hour) [单位产能投资]")
        self.cost_expressions['electrolyzer_investment_cost'] = gp.quicksum(
            self.electrolyzer_capacity_vars[location] *
            electrolyzer_capex_raw * self.economic_params['electrolyzer_capacity_factor']  # 电解槽投资成本 - 使用配置参数
            for location in self.locations
            if location in self.electrolyzer_capacity_vars
        )

        # 7. 制氢运营成本（20年生命周期现值）- 使用统一成本配置
        hydrogen_production_unit_cost = float(
            self.config.get('unified_costs', {}).get('production', {}).get('hydrogen_internal_cost_yuan_per_kg', 0)
        )
        self.cost_expressions['hydrogen_production_cost'] = gp.quicksum(
            self.hydrogen_production_vars[(location, hour)] * hydrogen_production_unit_cost * lifecycle_operation_factor
            for location in self.locations
            for hour in range(self.total_hours)
            if (location, hour) in self.hydrogen_production_vars
        )

        # 8. 电解制氢电力成本（20年生命周期现值）
        # 电力成本（基于实际氢气生产的电力消耗）
        h2_electrolysis_power_cost = gp.quicksum(
            self.hydrogen_production_vars[(location, hour)] *
            self.costs['electrolysis_power_consumption'] / 1000 *  # kWh -> MWh
            self.costs['renewable_electricity_cost_yuan_per_mwh']  # 时间窗口内实际电力成本，不乘以生命周期系数
            for location in self.locations
            for hour in range(self.total_hours)
            if (location, hour) in self.hydrogen_production_vars
        ) * operation_expansion_factor * present_value_factor  # 扩展到20年生命周期现值

        # 8.2 SAF合成工艺电力成本（RWGS + FT）
        # 新增：从配置文件中获取SAF合成能耗参数（之前未计算）
        # 修正日期：2025-11-09
        saf_synthesis_energy_kwh_per_kg = float(
            self.config.get('technologies', {}).get('green_h2_co2_to_saf', {}).get('energy_consumption_kwh_per_kg_saf', 0)
        )

        # 获取可再生能源电价和市电电价
        renewable_electricity_price = self.config.get('cost_parameters', {}).get('renewable_energy', {}).get('wind_power_price_yuan_per_kwh', 0.35)
        grid_electricity_price = self.config.get('cost_parameters', {}).get('renewable_energy', {}).get('grid_electricity_price_yuan_per_kwh', 0.6)

        # 根据SAF工厂位置类型选择电价
        # - 可再生能源发电厂（solar_plant, wind_farm）：使用可再生电价 (0.35-0.5 元/kWh)
        # - 其他位置（airport等）：使用市电电价 (0.6 元/kWh)
        saf_synthesis_power_cost = gp.quicksum(
            self.production_vars[(location, tech, hour)] *
            saf_synthesis_energy_kwh_per_kg *  # kWh/kg
            (renewable_electricity_price if self.locations[location]['type'] in ['solar_plant', 'wind_farm']
             else grid_electricity_price)
            for location in self.locations
            for tech in self.technologies
            for hour in range(self.total_hours)
            if (location, tech, hour) in self.production_vars
        ) * operation_expansion_factor * present_value_factor

        # 8.3 SAF合成催化剂成本
        # 新增：催化剂成本计算（之前配置文件中有定义但代码中未使用）
        # 修正日期：2025-11-09
        catalyst_cost_yuan_per_kg_saf = float(
            self.config.get('technologies', {}).get('green_h2_co2_to_saf', {}).get('catalyst_cost_yuan_per_kg_saf', 0)
        )

        saf_catalyst_cost = gp.quicksum(
            self.production_vars[(location, tech, hour)] * catalyst_cost_yuan_per_kg_saf
            for location in self.locations
            for tech in self.technologies
            for hour in range(self.total_hours)
            if (location, tech, hour) in self.production_vars
        ) * operation_expansion_factor * present_value_factor

        # 8.4 总电力成本（电解制氢 + SAF合成）
        self.cost_expressions['electricity_cost'] = h2_electrolysis_power_cost + saf_synthesis_power_cost

        # 8.5 总催化剂成本
        self.cost_expressions['catalyst_cost'] = saf_catalyst_cost

        # 9. 氢气储存投资 + 20年运营成本现值
        # 修正：氢气储存设备成本应基于各地点的最大库存量之和，而非所有时间点库存量之和
        # 创建辅助变量来捕获各地点的最大氢气库存量
        max_h2_storage_by_location = {}
        for location in self.locations:
            if any((location, hour) in self.hydrogen_storage_vars for hour in range(self.total_hours + 1)):
                max_var = self.model.addVar(
                    lb=0, ub=GRB.INFINITY,
                    vtype=GRB.CONTINUOUS,
                    name=f'max_h2_storage_{location}'
                )
                # 约束：max_var必须大于等于该地点在任何时刻的氢气库存量
                for hour in range(self.total_hours + 1):
                    if (location, hour) in self.hydrogen_storage_vars:
                        self.model.addConstr(
                            max_var >= self.hydrogen_storage_vars[(location, hour)],
                            name=f'max_h2_storage_constr_{location}_h{hour}'
                        )
                max_h2_storage_by_location[location] = max_var

        # 总的氢气储存设备需求 = 各地点最大氢气库存量之和
        max_h2_storage = gp.quicksum(max_h2_storage_by_location.values())

        # 优先使用统一成本配置中的氢气储存设备成本
        h2_storage_unit_cost = float(
            self.config.get('unified_costs', {}).get('storage', {}).get('hydrogen_equipment_cost_yuan_per_kg') or
            storage_cfg.get('hydrogen_equipment_unit_cost_yuan_per_kg', 20)
        )
        self.cost_expressions['h2_storage_investment'] = max_h2_storage * h2_storage_unit_cost

        # 氢气库存运营成本：使用平均库存（峰值/2）而非所有时刻库存总和
        # 运营成本 = Σ(各地点最大氢气库存/2) × 小时成本 × 总小时数 × 生命周期系数
        average_h2_storage_total = gp.quicksum(max_h2_storage_by_location.values()) / 2.0
        self.cost_expressions['h2_storage_operation'] = (
            average_h2_storage_total *
            self._calculate_total_storage_cost_per_kg_hour() *
            self.total_hours *
            lifecycle_operation_factor
        )

        # 9. 氢气运输投资 + 20年运营成本现值（改为周级）
        self.cost_expressions['hydrogen_transport_investment'] = gp.LinExpr(0)  # 已包含在平准化氢气运输成本中
        # 【禁用罐车运输】注释掉氢气罐车运输成本计算
        """
        self.cost_expressions['hydrogen_transport_operation'] = gp.quicksum(
            self.hydrogen_transport_vars[(h_loc, mtj_loc)] *
            self._calculate_hydrogen_transport_cost_by_distance(
                self._calculate_location_distance(h_loc, mtj_loc)
            ) * operation_expansion_factor * present_value_factor  # 周运输量 × 单位成本 × 年化系数 × 现值系数
            for h_loc in self.hydrogen_locations
            for mtj_loc in sum(self.mtj_locations.values(), [])
            if (h_loc, mtj_loc) in self.hydrogen_transport_vars
        )
        """
        self.cost_expressions['hydrogen_transport_operation'] = gp.LinExpr(0)  # 【禁用罐车运输】设为0

        # 9.1. 氢能管道运输成本现值（成本函数已包含所有费用）
        if hasattr(self, 'hydrogen_pipeline_transport_vars') and self.hydrogen_pipeline_transport_vars:
            # 🚀 性能优化：预先缓存所有氢气管道运输距离（延迟计算模式 + 大批量并行）
            # 避免在quicksum循环中重复计算，显著提升性能
            if not hasattr(self, 'hydrogen_distance_cache'):
                self.hydrogen_distance_cache = {}

                # 收集所有需要计算的路径对
                h2_route_pairs = [
                    (h2_loc, mtj_loc)
                    for h2_loc in self.hydrogen_locations
                    for mtj_loc in sum(self.mtj_locations.values(), [])
                    if (h2_loc, mtj_loc) in self.hydrogen_pipeline_transport_vars
                    and h2_loc != mtj_loc
                ]

                total_h2_routes = len(h2_route_pairs)
                logger.info(f"开始缓存氢气管道运输距离: {total_h2_routes}条路径...")
                logger.info(f"使用{self.parallel_workers}个并行workers进行批量计算")
                h2_start_time = time.time()

                # 使用并行处理，批量大小10000
                batch_size = 10000
                h2_calculated = 0

                with ThreadPoolExecutor(max_workers=self.parallel_workers) as executor:
                    # 分批处理
                    for batch_start in range(0, total_h2_routes, batch_size):
                        batch_end = min(batch_start + batch_size, total_h2_routes)
                        batch_pairs = h2_route_pairs[batch_start:batch_end]

                        # 并行计算这一批
                        futures = {
                            executor.submit(self._get_hydrogen_transport_distance_with_clustering, h2_loc, mtj_loc): (h2_loc, mtj_loc)
                            for h2_loc, mtj_loc in batch_pairs
                        }

                        # 收集结果
                        for future in as_completed(futures):
                            h2_loc, mtj_loc = futures[future]
                            try:
                                distance_km = future.result()
                                self.hydrogen_distance_cache[(h2_loc, mtj_loc)] = distance_km
                                h2_calculated += 1

                                # 每1000条输出进度
                                if h2_calculated % 1000 == 0:
                                    elapsed = time.time() - h2_start_time
                                    avg_time = elapsed / h2_calculated
                                    remaining = (total_h2_routes - h2_calculated) * avg_time
                                    logger.info(f"氢气距离缓存进度: {h2_calculated}/{total_h2_routes} "
                                              f"({h2_calculated/total_h2_routes*100:.1f}%), "
                                              f"预计剩余: {remaining:.1f}秒")
                            except Exception as e:
                                logger.warning(f"氢气距离计算失败 {h2_loc} -> {mtj_loc}: {e}")
                                # 使用默认距离
                                self.hydrogen_distance_cache[(h2_loc, mtj_loc)] = 50.0
                                h2_calculated += 1

                h2_elapsed_time = time.time() - h2_start_time
                logger.info(f"氢气距离缓存完成: {len(self.hydrogen_distance_cache)}条路径, "
                           f"耗时: {h2_elapsed_time:.2f}秒, "
                           f"平均速度: {total_h2_routes/h2_elapsed_time:.1f}条/秒")

            # 管道运输成本（基于图像拟合的成本函数，已包含所有投资和运营成本）
            # 使用预先缓存的距离，避免重复计算
            self.cost_expressions['hydrogen_pipeline_operation'] = gp.quicksum(
                self.hydrogen_pipeline_transport_vars[(h2_loc, mtj_loc)] *
                self._calculate_hydrogen_pipeline_cost_by_distance(
                    self.hydrogen_distance_cache[(h2_loc, mtj_loc)]  # 从缓存获取距离
                ) * operation_expansion_factor * present_value_factor  # 周运输量 × 单位成本 × 年化系数 × 现值系数
                for h2_loc in self.hydrogen_locations
                for mtj_loc in sum(self.mtj_locations.values(), [])
                if (h2_loc, mtj_loc) in self.hydrogen_pipeline_transport_vars
                and h2_loc != mtj_loc  # 排除同位置运输（距离为0，无需运输）
            )
        else:
            self.cost_expressions['hydrogen_pipeline_operation'] = gp.LinExpr(0)

        # v3.0: 煤炭气化路线不需要CO₂捕获和运输成本

        # 注意：一步法（process_mode: one_step）不需要甲醇成本
        # H₂+CO₂ 直接转化为 SAF，甲醇不作为成本项
        # 甲醇变量仍存在（用于约束建模），但不计入成本
        self.cost_expressions['methanol_production_cost'] = gp.LinExpr(0)
        self.cost_expressions['methanol_storage_investment'] = gp.LinExpr(0)
        self.cost_expressions['methanol_storage_operation'] = gp.LinExpr(0)

        logger.info("一步法模式：甲醇成本已设置为0（甲醇不作为独立成本项）")

        # v3.0新增：煤炭采购和气化成本（20年生命周期现值）
        logger.info("创建煤炭采购和气化成本表达式（v3.0）")

        # 煤炭采购成本（周级采购量 × 单位采购成本）
        coal_purchase_unit_cost = self.coal_supply.calculate_coal_purchase_cost(1.0)  # 元/kg煤炭
        # 直接遍历已创建的煤炭采购变量，避免复杂的过滤条件导致漏掉变量
        self.cost_expressions['coal_purchase_cost'] = gp.quicksum(
            var * coal_purchase_unit_cost * lifecycle_operation_factor
            for var in self.coal_purchase_vars.values()
        )

        # 煤炭气化能耗成本（周级采购量 × 单位气化能耗成本）
        coal_gasification_unit_cost = self.coal_supply.calculate_gasification_energy_cost(1.0)  # 元/kg煤炭
        # 直接遍历已创建的煤炭采购变量，避免复杂的过滤条件导致漏掉变量
        self.cost_expressions['coal_gasification_cost'] = gp.quicksum(
            var * coal_gasification_unit_cost * lifecycle_operation_factor
            for var in self.coal_purchase_vars.values()
        )

        logger.info(f"煤炭采购单位成本: {coal_purchase_unit_cost:.4f} 元/kg")
        logger.info(f"煤炭气化单位成本: {coal_gasification_unit_cost:.4f} 元/kg")


        # 13. 短缺惩罚成本（20年生命周期现值）
        if hasattr(self, 'shortage_vars'):
            self.cost_expressions['shortage_cost'] = gp.quicksum(
                var * self.costs['shortage_penalty_yuan_per_kg'] * lifecycle_operation_factor  # 20年现值
                for var in self.shortage_vars.values()
            )
        else:
            self.cost_expressions['shortage_cost'] = gp.LinExpr(0)

        # 14. 期末资产处置成本（20年后的现值）
        disposal_cost_per_kg = float(obj_cfg.get('final_inventory_disposal_cost_per_kg', 100))
        self.cost_expressions['final_inventory_cost'] = gp.quicksum(
            self.storage_vars[(location, self.total_hours)] * disposal_cost_per_kg * operation_expansion_factor *
            (1 + discount_rate)**(-project_lifespan)  # 20年后处置成本的现值
            for location in self.locations
        )

        # 创建聚合成本表达式
        # 投资成本聚合
        self.cost_aggregates['total_investment_cost'] = (
            self.cost_expressions['facility_investment_cost'] +
            self.cost_expressions['storage_equipment_cost'] +
            self.cost_expressions['electrolyzer_investment_cost'] +
            self.cost_expressions['h2_storage_investment'] +
            self.cost_expressions['hydrogen_transport_investment']
            # 注意：一步法不包含甲醇储存投资成本
        )

        # 运营成本聚合
        self.cost_aggregates['total_operation_cost'] = (
            self.cost_expressions['facility_operation_cost'] +
            self.cost_expressions['production_cost'] +
            self.cost_expressions['transport_operation_cost'] +
            self.cost_expressions['storage_operation_cost'] +
            self.cost_expressions['hydrogen_production_cost'] +
            self.cost_expressions['electricity_cost'] +
            self.cost_expressions['catalyst_cost'] +  # 新增：SAF合成催化剂成本 (2025-11-09)
            self.cost_expressions['h2_storage_operation'] +
            self.cost_expressions['hydrogen_transport_operation'] +
            self.cost_expressions['hydrogen_pipeline_operation'] +
            self.cost_expressions['coal_purchase_cost'] +  # v3.0新增：煤炭采购成本
            self.cost_expressions['coal_gasification_cost'] +  # v3.0新增：煤炭气化成本
            # 注意：一步法不包含甲醇生产成本和甲醇储存运营成本
            self.cost_expressions['final_inventory_cost']
        )

        # 不含短缺成本的总成本
        self.cost_aggregates['total_cost_excluding_shortage'] = (
            self.cost_aggregates['total_investment_cost'] +
            self.cost_aggregates['total_operation_cost']
        )

        logger.info("统一成本表达式创建完成")
        logger.info(f"项目期限: {project_lifespan}年，时间窗口: {self.time_horizon_weeks}周")
        logger.info(f"运营成本年化系数: {operation_expansion_factor:.1f}")
        logger.info(f"20年运营成本现值系数: {present_value_factor:.2f}")
        logger.info(f"生命周期运营成本系数: {lifecycle_operation_factor:.2f}")
        logger.info("所有运营成本已扩展至20年生命周期现值")

        # 关键参数验证
        logger.info("\n【关键参数验证】")
        logger.info(f"MTJ变动运营成本参数: {variable_opex_per_kg} 元/kg")
        logger.info(f"电力成本参数: {self.costs['renewable_electricity_cost_yuan_per_mwh']} 元/MWh")
        logger.info(f"电解制氢耗电: {self.costs['electrolysis_power_consumption']} kWh/kg H2")

        # 创建性能指标表达式（产量、缺货、需求等）
        self._create_performance_expressions()

        # 创建碳排放表达式（如果启用）
        if self.carbon_params.get('calculation_control', {}).get('enable_carbon_tracking', True):
            self._create_carbon_emission_expressions()

    def _create_carbon_emission_expressions(self):
        """创建碳排放计算表达式（基于SAF生命周期碳排放计算方法）"""
        logger.info("="*80)
        logger.info("创建碳排放计算表达式...")
        logger.info("="*80)

        # 初始化碳排放表达式存储结构
        self.carbon_expressions = {}  # 存储各阶段碳排放表达式
        self.carbon_aggregates = {}   # 存储聚合碳排放表达式

        # 从配置获取碳排放参数
        raw_materials = self.carbon_params.get('raw_materials', {})
        facility_constr = self.carbon_params.get('facility_construction', {})
        production = self.carbon_params.get('production_process', {})
        storage_handling = self.carbon_params.get('storage_handling', {})
        transportation = self.carbon_params.get('transportation', {})

        # 验证碳排放参数完整性
        logger.info("验证碳排放参数完整性...")
        required_params = {
            'raw_materials': [],  # 绿氢供应链无需天然气开采参数
            'facility_construction': ['saf_facility_embodied', 'saf_facility_lifetime',
                                    'electrolyzer_embodied', 'electrolyzer_lifetime'],
            'production_process': ['mtj_process_energy', 'renewable_electricity',
                                 'electrolysis_energy', 'green_h2_intensity'],
            'storage_handling': ['mtj_storage_energy', 'h2_storage_energy'],
            'transportation': ['h2_truck_intensity', 'mtj_truck_intensity']
        }

        missing_params = []
        for category, params in required_params.items():
            category_data = self.carbon_params.get(category, {})
            for param in params:
                if param not in category_data:
                    missing_params.append(f"{category}.{param}")
                    logger.warning(f"缺失碳排放参数: {category}.{param}")

        if missing_params:
            logger.warning(f"发现 {len(missing_params)} 个缺失的碳排放参数，将使用默认值")
        else:
            logger.info("碳排放参数完整性检查通过")

        # 时间相关常量
        total_days = self.total_hours // 24
        project_lifespan = self.economic_params['project_lifespan']
        operation_expansion_factor = 52.0 / self.time_horizon_weeks  # 年化系数

        # =========================================================================
        # 1. 原料获取阶段碳排放 (Raw Material Extraction)
        # =========================================================================
        # 煤炭供应链特有碳排放：煤炭开采、运输、气化过程

        # 从配置获取煤炭碳排放参数
        coal_mining = production.get('coal_mining_emission', 0.04)  # kg CO2e/kg coal
        coal_transport = production.get('coal_transport_emission', 0.05)  # kg CO2e/kg coal
        coal_gasif_direct = production.get('coal_gasification_direct_emission', 0.15)  # kg CO2e/kg coal
        coal_gasif_energy = production.get('coal_gasification_energy_kwh_per_kg', 2.22)  # kWh/kg coal
        gasif_elec_intensity = production.get('gasification_electricity_intensity', 0.6)  # kg CO2e/kWh
        co2_capture_energy = production.get('co2_capture_energy_kwh_per_ton', 120)  # kWh/ton CO2
        co2_capture_eff = production.get('co2_capture_efficiency', 0.85)  # 85%
        coal_co2_yield = production.get('coal_co2_yield_kg_per_kg', 2.44)  # kg CO2/kg coal
        coal_consumption = production.get('coal_consumption_kg_per_kg_saf', 1.8)  # kg coal/kg SAF

        # 1.1 煤炭开采排放
        # 排放 = SAF产量 × 单位SAF煤炭消耗 × 开采排放因子
        self.carbon_expressions['coal_mining'] = gp.quicksum(
            self.production_vars.get((location, tech, hour), gp.LinExpr(0)) *
            coal_consumption * coal_mining  # kg SAF × kg coal/kg SAF × kg CO2e/kg coal
            for location in self.locations
            for tech in self.technologies
            for hour in range(self.total_hours)
            if (location, tech, hour) in self.production_vars
        )

        # 1.2 煤炭运输排放
        self.carbon_expressions['coal_transport'] = gp.quicksum(
            self.production_vars.get((location, tech, hour), gp.LinExpr(0)) *
            coal_consumption * coal_transport
            for location in self.locations
            for tech in self.technologies
            for hour in range(self.total_hours)
            if (location, tech, hour) in self.production_vars
        )

        # 1.3 煤炭气化过程直接排放（不包括CO₂产品）
        self.carbon_expressions['coal_gasification_direct'] = gp.quicksum(
            self.production_vars.get((location, tech, hour), gp.LinExpr(0)) *
            coal_consumption * coal_gasif_direct
            for location in self.locations
            for tech in self.technologies
            for hour in range(self.total_hours)
            if (location, tech, hour) in self.production_vars
        )

        # 1.4 煤炭气化能耗排放
        # 气化能耗排放 = SAF产量 × 煤炭消耗 × 气化能耗 × 电网碳强度
        self.carbon_expressions['coal_gasification_energy'] = gp.quicksum(
            self.production_vars.get((location, tech, hour), gp.LinExpr(0)) *
            coal_consumption * coal_gasif_energy * gasif_elec_intensity
            for location in self.locations
            for tech in self.technologies
            for hour in range(self.total_hours)
            if (location, tech, hour) in self.production_vars
        )

        # 1.5 气化产生的CO₂逸散排放（未被捕获部分）
        # CO₂逸散 = SAF产量 × 煤炭消耗 × CO₂产量 × (1 - 捕获率)
        co2_fugitive_rate = 1.0 - co2_capture_eff  # 15%逸散率
        self.carbon_expressions['coal_co2_fugitive'] = gp.quicksum(
            self.production_vars.get((location, tech, hour), gp.LinExpr(0)) *
            coal_consumption * coal_co2_yield * co2_fugitive_rate
            for location in self.locations
            for tech in self.technologies
            for hour in range(self.total_hours)
            if (location, tech, hour) in self.production_vars
        )

        # 1.6 CO₂捕获能耗排放
        # 捕获能耗排放 = SAF产量 × 煤炭消耗 × CO₂产量 × 捕获率 × 捕获能耗 × 电网碳强度
        self.carbon_expressions['co2_capture_energy'] = gp.quicksum(
            self.production_vars.get((location, tech, hour), gp.LinExpr(0)) *
            coal_consumption * coal_co2_yield * co2_capture_eff *
            (co2_capture_energy / 1000) * gasif_elec_intensity  # kWh/ton → kWh/kg
            for location in self.locations
            for tech in self.technologies
            for hour in range(self.total_hours)
            if (location, tech, hour) in self.production_vars
        )

        logger.info("煤炭碳排放参数:")
        logger.info(f"  煤炭开采排放: {coal_mining} kg CO2e/kg coal")
        logger.info(f"  煤炭运输排放: {coal_transport} kg CO2e/kg coal")
        logger.info(f"  气化直接排放: {coal_gasif_direct} kg CO2e/kg coal")
        logger.info(f"  气化能耗: {coal_gasif_energy} kWh/kg coal")
        logger.info(f"  气化电网碳强度: {gasif_elec_intensity} kg CO2e/kWh")
        logger.info(f"  CO₂捕获率: {co2_capture_eff*100:.1f}%")
        logger.info(f"  CO₂逸散率: {co2_fugitive_rate*100:.1f}%")
        logger.info(f"  单位SAF煤炭消耗: {coal_consumption} kg coal/kg SAF")
        logger.info(f"  单位煤炭CO₂产量: {coal_co2_yield} kg CO2/kg coal")

        # =========================================================================
        # 2. 设施建设阶段碳排放（年摊销）(Facility Construction)
        # =========================================================================
        saf_embodied = facility_constr.get('saf_facility_embodied', 150)  # kg CO2eq/t年产能
        saf_lifetime = facility_constr.get('saf_facility_lifetime', 25)  # 年
        electrolyzer_embodied = facility_constr.get('electrolyzer_embodied', 1200)  # kg CO2eq/MW
        electrolyzer_lifetime = facility_constr.get('electrolyzer_lifetime', 20)  # 年

        # SAF工厂建设碳排放（年摊销到优化时段）
        # 单位转换: kg/h → t/年 → kg CO2eq
        self.carbon_expressions['saf_facility'] = gp.quicksum(
            (self.facility_capacity_vars.get((location, tech), gp.LinExpr(0)) * 8760 / 1000) *  # kg/h → t/年
            saf_embodied / saf_lifetime * (self.time_horizon_weeks / 52.0)  # 年摊销到优化时段
            for location in self.locations
            for tech in self.technologies
            if (location, tech) in self.facility_capacity_vars
        )

        # 电解槽建设碳排放（年摊销）
        # 方案：基于氢气产能计算，避免功率转换的复杂性
        # 重新定义电解槽碳强度为基于氢气产能：kg CO2eq/MW → kg CO2eq/(kg H2/h)
        electrolysis_energy = production.get('electrolysis_energy', 55)  # kWh/kg H2
        # 安全检查：避免除零错误
        if electrolysis_energy <= 0:
            raise ValueError(f"电解制氢能耗必须大于0，当前值: {electrolysis_energy}")
        # 转换电解槽碳强度: MW → kg H2/h
        # 1 MW = 1000 kW, 1 kW = 1 kWh/h, 所以 1 MW = 1000 kWh/h
        # 1 MW / (55 kWh/kg H2) = 1000/55 ≈ 18.18 kg H2/h
        electrolyzer_embodied_per_capacity = electrolyzer_embodied / (1000 / electrolysis_energy)  # kg CO2eq/(kg H2/h)

        self.carbon_expressions['electrolyzer_facility'] = gp.quicksum(
            self.electrolyzer_capacity_vars.get(location, gp.LinExpr(0)) *  # kg H2/h
            electrolyzer_embodied_per_capacity / electrolyzer_lifetime * (self.time_horizon_weeks / 52.0)
            for location in self.hydrogen_locations
            if location in self.electrolyzer_capacity_vars
        )

        logger.info(f"SAF设施碳强度: {saf_embodied} kg CO2eq/t年产能, 寿命: {saf_lifetime}年")
        logger.info(f"电解槽碳强度: {electrolyzer_embodied} kg CO2eq/MW → {electrolyzer_embodied_per_capacity:.2f} kg CO2eq/(kg H2/h), 寿命: {electrolyzer_lifetime}年")
        logger.info(f"[调试] 设施容量变量数量: {len([k for k in self.facility_capacity_vars.keys()])}") if hasattr(self, 'facility_capacity_vars') else logger.warning("[调试] 未找到设施容量变量")
        logger.info(f"[调试] 电解槽容量变量数量: {len([k for k in self.electrolyzer_capacity_vars.keys()])}") if hasattr(self, 'electrolyzer_capacity_vars') else logger.warning("[调试] 未找到电解槽容量变量")

        # =========================================================================
        # 3. 生产过程阶段碳排放 (Production Process)
        # =========================================================================
        mtj_energy = production.get('mtj_process_energy', 800)  # kWh/t SAF
        renewable_elec_fixed = production.get('renewable_electricity', 0.02)  # kg CO2eq/kWh (仅用作fallback)
        electrolysis_energy = production.get('electrolysis_energy', 55)  # kWh/kg H2
        h2_process_emission = production.get('electrolysis_process_emission', 0.05)  # kg CO2eq/kg H2

        # ✨ 预计算动态碳强度（Gurobi表达式要求系数为静态值）
        logger.info("✨ 预计算动态可再生能源碳强度...")

        # 收集所有需要计算的位置
        unique_locations = set(self.locations.keys()) | set(self.hydrogen_locations)

        # 预计算所有location-hour组合的动态碳强度
        self.dynamic_carbon_intensity = {}
        for location in unique_locations:
            for hour in range(self.total_hours):
                ci = self._calculate_dynamic_renewable_intensity(location, hour)
                self.dynamic_carbon_intensity[(location, hour)] = ci

        logger.info(f"✨ 已预计算 {len(self.dynamic_carbon_intensity)} 个location-hour动态碳强度值")

        # 预计算动态绿氢碳强度
        self.dynamic_h2_intensity = {}
        for location in self.hydrogen_locations:
            for hour in range(self.total_hours):
                elec_ci = self.dynamic_carbon_intensity.get((location, hour), renewable_elec_fixed)
                h2_ci = electrolysis_energy * elec_ci + h2_process_emission
                self.dynamic_h2_intensity[(location, hour)] = h2_ci

        logger.info(f"✨ 已预计算 {len(self.dynamic_h2_intensity)} 个location-hour动态绿氢碳强度值")

        # 甲醇制SAF过程碳排放（使用动态碳强度）
        self.carbon_expressions['methanol_to_saf'] = gp.quicksum(
            self.production_vars.get((location, tech, hour), gp.LinExpr(0)) *
            mtj_energy / 1000 * self.dynamic_carbon_intensity.get((location, hour), renewable_elec_fixed)  # ✨ 使用动态CI
            for location in self.locations
            for tech in self.technologies
            for hour in range(self.total_hours)
            if (location, tech, hour) in self.production_vars
        )

        # SAF合成工艺能耗碳排放 (新增：修复遗漏的主要能耗碳排放)
        # 根据SAF工厂位置类型选择碳强度：
        # - 可再生能源站点 (solar_plant, wind_farm) → 使用动态可再生碳强度 (0.015-0.045 kgCO₂e/kWh)
        # - 其他站点 (airport等) → 使用市电碳强度 (0.6 kgCO₂e/kWh)
        # 修正日期：2025-11-09
        # 注：煤制路线仅计算SAF合成能耗7.6 kWh/kg（MTJ能耗忽略）
        saf_synthesis_energy_kwh_per_kg = 7.6  # kWh/kg SAF (RWGS+FT合成能耗)
        grid_electricity_intensity = self.config.get('carbon_intensity', {}).get('grid_electricity_intensity', 0.6)

        self.carbon_expressions['saf_synthesis_energy'] = gp.quicksum(
            self.production_vars.get((location, tech, hour), gp.LinExpr(0)) *
            saf_synthesis_energy_kwh_per_kg *  # SAF合成能耗
            (self.dynamic_carbon_intensity.get((location, hour), renewable_elec_fixed)  # 可再生站点：动态碳强度
             if self.locations[location]['type'] in ['solar_plant', 'wind_farm']
             else grid_electricity_intensity)  # 其他站点：市电碳强度
            for location in self.locations
            for tech in self.technologies
            for hour in range(self.total_hours)
            if (location, tech, hour) in self.production_vars
        )

        logger.info(f"SAF合成工艺能耗: {saf_synthesis_energy_kwh_per_kg} kWh/kg, 市电碳强度: {grid_electricity_intensity} kgCO₂e/kWh")
        logger.info(f"✨ SAF合成碳排放根据工厂位置类型选择碳强度（可再生站点 vs 市电）")

        # 氢气生产碳排放（使用动态绿氢碳强度）
        self.carbon_expressions['h2_production'] = gp.quicksum(
            self.hydrogen_production_vars.get((location, hour), gp.LinExpr(0)) *
            self.dynamic_h2_intensity.get((location, hour), renewable_elec_fixed * electrolysis_energy + h2_process_emission)  # ✨ 使用动态H2 CI
            for location in self.hydrogen_locations
            for hour in range(self.total_hours)
            if (location, hour) in self.hydrogen_production_vars
        )

        logger.info(f"MTJ工艺能耗: {mtj_energy} kWh/t")
        logger.info(f"✨ 使用动态碳强度代替固定值 (原固定值: {renewable_elec_fixed} kg CO2eq/kWh)")
        logger.info(f"✨ 使用动态绿氢碳强度 (电解能耗: {electrolysis_energy} kWh/kg H2, 过程排放: {h2_process_emission} kg CO2eq/kg H2)")
        logger.info(f"[调试] 生产变量数量: {len([k for k in self.production_vars.keys()])}") if hasattr(self, 'production_vars') else logger.warning("[调试] 未找到生产变量")
        logger.info(f"[调试] 氢气生产变量数量: {len([k for k in self.hydrogen_production_vars.keys()])}") if hasattr(self, 'hydrogen_production_vars') else logger.warning("[调试] 未找到氢气生产变量")

        # =========================================================================
        # 4. 储存处理阶段碳排放 (Storage & Handling)
        # =========================================================================
        mtj_storage_energy = storage_handling.get('mtj_storage_energy', 5)  # kWh/t·天
        h2_storage_energy = storage_handling.get('h2_storage_energy', 0.5)  # kWh/kg·天

        # 基本参数验证
        if mtj_storage_energy <= 0:
            logger.warning(f"MTJ储存能耗参数异常: {mtj_storage_energy}")
        if h2_storage_energy <= 0:
            logger.warning(f"氢气储存能耗参数异常: {h2_storage_energy}")

        # MTJ储存碳排放（使用动态碳强度）
        # 注：存储变量索引范围应为0到total_hours（包含边界状态）
        self.carbon_expressions['mtj_storage'] = gp.quicksum(
            self.storage_vars.get((location, hour), gp.LinExpr(0)) *
            mtj_storage_energy / 24 * self.dynamic_carbon_intensity.get((location, min(hour, self.total_hours - 1)), renewable_elec_fixed)  # ✨ 使用动态CI，处理边界状态
            for location in self.locations
            for hour in range(self.total_hours + 1)  # 存储变量包含边界状态
            if (location, hour) in self.storage_vars
        )

        # 氢气储存碳排放（使用动态碳强度）
        # 注：氢气存储变量索引范围应为0到total_hours（包含边界状态）
        self.carbon_expressions['h2_storage'] = gp.quicksum(
            self.hydrogen_storage_vars.get((location, hour), gp.LinExpr(0)) *
            h2_storage_energy / 24 * self.dynamic_carbon_intensity.get((location, min(hour, self.total_hours - 1)), renewable_elec_fixed)  # ✨ 使用动态CI，处理边界状态
            for location in self.hydrogen_locations
            for hour in range(self.total_hours + 1)  # 氢气存储变量包含边界状态
            if (location, hour) in self.hydrogen_storage_vars
        )

        logger.info(f"MTJ储存能耗: {mtj_storage_energy} kWh/t·天")
        logger.info(f"氢气储存能耗: {h2_storage_energy} kWh/kg·天")
        logger.info(f"[调试] MTJ存储变量数量: {len([k for k in self.storage_vars.keys()])}") if hasattr(self, 'storage_vars') else logger.warning("[调试] 未找到MTJ存储变量")
        logger.info(f"[调试] 氢气存储变量数量: {len([k for k in self.hydrogen_storage_vars.keys()])}") if hasattr(self, 'hydrogen_storage_vars') else logger.warning("[调试] 未找到氢气存储变量")

        # =========================================================================
        # 5. 运输配送阶段碳排放 (Transportation & Distribution)
        # =========================================================================
        # h2_truck = transportation.get('h2_truck_intensity', 0.15)  # 【禁用罐车运输】
        h2_pipeline = transportation.get('h2_pipeline_intensity', 0.005)  # kg CO2eq/kg·km
        mtj_truck = transportation.get('mtj_truck_intensity', 0.12)  # kg CO2eq/t·km

        # 【禁用罐车运输】注释掉氢气罐车运输碳排放计算
        """
        # 氢气罐车运输碳排放
        # 注：hydrogen_transport_vars单位为kg H2/week，h2_truck为kg CO2eq/kg·km
        self.carbon_expressions['h2_truck_transport'] = gp.quicksum(
            self.hydrogen_transport_vars.get((h2_loc, mtj_loc), gp.LinExpr(0)) *
            self._calculate_distance(h2_loc, mtj_loc) * h2_truck
            for h2_loc in self.hydrogen_locations
            for mtj_loc in self.locations
            if (h2_loc, mtj_loc) in self.hydrogen_transport_vars
        )
        """
        self.carbon_expressions['h2_truck_transport'] = gp.LinExpr(0)  # 【禁用罐车运输】设为0

        # 氢气管道运输碳排放（修复：之前遗漏了这部分）
        # 注：hydrogen_pipeline_transport_vars单位为kg H2/week，h2_pipeline为kg CO2eq/kg·km
        # 使用预先缓存的距离，避免重复计算
        self.carbon_expressions['h2_pipeline_transport'] = gp.quicksum(
            self.hydrogen_pipeline_transport_vars.get((h2_loc, mtj_loc), gp.LinExpr(0)) *
            self.hydrogen_distance_cache.get((h2_loc, mtj_loc), 50.0) * h2_pipeline  # 从缓存获取距离
            for h2_loc in self.hydrogen_locations
            for mtj_loc in self.locations
            if (h2_loc, mtj_loc) in self.hydrogen_pipeline_transport_vars
        ) if hasattr(self, 'hydrogen_pipeline_transport_vars') and self.hydrogen_pipeline_transport_vars and hasattr(self, 'hydrogen_distance_cache') else gp.LinExpr(0)

        # 氢气总运输碳排放（【禁用罐车运输】仅包含管道运输）
        self.carbon_expressions['h2_transport'] = (
            # self.carbon_expressions['h2_truck_transport'] +  # 【禁用罐车运输】
            self.carbon_expressions['h2_pipeline_transport']
        )

        # MTJ运输碳排放
        # 单位转换: kg → t，因为mtj_truck单位是kg CO2eq/t·km
        self.carbon_expressions['mtj_transport'] = gp.quicksum(
            (self.transport_vars.get((location, airport, week), gp.LinExpr(0)) / 1000) *  # kg → t
            self._calculate_distance(location, airport) * mtj_truck  # t × km × kg CO2eq/t·km
            for location in self.locations
            for airport in self.airports
            for week in range(self.time_horizon_weeks)
            if (location, airport, week) in self.transport_vars
        )

        # 验证运输碳强度参数合理性
        transport_params = [
            # (h2_truck, 0.05, 0.50, "氢气罐车运输碳强度"),  # 【禁用罐车运输】
            (h2_pipeline, 0.001, 0.020, "氢气管道运输碳强度"),
            (mtj_truck, 0.05, 0.30, "MTJ罐车运输碳强度")
        ]
        for value, min_val, max_val, name in transport_params:
            if not (min_val <= value <= max_val):
                logger.warning(f"{name}可能不合理: {value}, 期望范围: [{min_val}, {max_val}]")

        # logger.info(f"氢气罐车运输: {h2_truck} kg CO2eq/kg·km")  # 【禁用罐车运输】
        logger.info(f"氢气管道运输: {h2_pipeline} kg CO2eq/kg·km")
        logger.info(f"MTJ罐车运输: {mtj_truck} kg CO2eq/t·km")
        # logger.info(f"[调试] 氢气罐车变量数量: {len([k for k in self.hydrogen_transport_vars.keys()])}") if hasattr(self, 'hydrogen_transport_vars') else logger.warning("[调试] 未找到氢气罐车变量")  # 【禁用罐车运输】
        logger.info(f"[调试] 氢气管道变量数量: {len([k for k in self.hydrogen_pipeline_transport_vars.keys()])}") if hasattr(self, 'hydrogen_pipeline_transport_vars') else logger.warning("[调试] 未找到氢气管道变量")
        logger.info(f"[调试] MTJ运输变量数量: {len([k for k in self.transport_vars.keys()])}") if hasattr(self, 'transport_vars') else logger.warning("[调试] 未找到MTJ运输变量")

        # 测试距离计算方法
        if hasattr(self, 'locations') and hasattr(self, 'airports') and self.locations and self.airports:
            sample_location = list(self.locations.keys())[0] if self.locations else None
            sample_airport = list(self.airports.keys())[0] if self.airports else None
            if sample_location and sample_airport:
                try:
                    test_distance = self._calculate_distance(sample_location, sample_airport)
                    logger.info(f"[调试] 距离计算测试 {sample_location} -> {sample_airport}: {test_distance:.2f} km")
                except Exception as e:
                    logger.warning(f"[调试] 距离计算方法测试失败: {e}")
            else:
                logger.warning("[调试] 无法测试距离计算：缺少位置或机场数据")
        else:
            logger.warning("[调试] 无法测试距离计算：位置或机场数据未初始化")

        # =========================================================================
        # 5.6 CO₂利用负排放 (CO₂ Utilization Credit - Negative Emissions)
        # =========================================================================
        # 从配置文件读取CO₂源类型和碳汇控制参数
        co2_source_config = self.carbon_params.get('co2_source_configuration', {})
        enable_co2_credit = co2_source_config.get('enable_co2_utilization_credit', False)
        scenario_type = co2_source_config.get('scenario_type', 'unknown')
        credit_factor = co2_source_config.get('utilization_credit_factor', 0.0)

        logger.info(f"CO₂源配置: scenario_type={scenario_type}, enable_credit={enable_co2_credit}")

        if enable_co2_credit:
            # 仅当配置允许时计算CO₂利用负排放（仅限工业捕获/DAC场景）
            # 根据CORSIA标准，固定在SAF中的碳应计为负排放
            saf_carbon_content = 0.85  # SAF中碳的质量分数
            co2_to_c_ratio = 44.0 / 12.0  # CO₂与碳的摩尔质量比
            utilization_credit_factor = credit_factor if credit_factor != 0 else -1.0  # 负排放系数

            self.carbon_expressions['co2_utilization_credit'] = gp.quicksum(
                self.production_vars.get((location, tech, hour), gp.LinExpr(0)) *
                saf_carbon_content * co2_to_c_ratio * utilization_credit_factor
                for location in self.locations
                for tech in self.technologies
                for hour in range(self.total_hours)
                if (location, tech, hour) in self.production_vars
            )

            logger.info(f"✨ CO₂利用负排放表达式已创建 (场景: {scenario_type})")
            logger.info(f"   SAF碳含量: {saf_carbon_content}, CO₂/C比: {co2_to_c_ratio:.2f}, 单位SAF负排放: {saf_carbon_content * co2_to_c_ratio * utilization_credit_factor:.2f} kg CO2eq/kg SAF")
        else:
            # 化石燃料原料场景（煤气化）：副产CO₂循环利用不属于碳移除，不计入负排放
            self.carbon_expressions['co2_utilization_credit'] = gp.LinExpr(0)
            logger.info(f"⚠️ CO₂利用负排放已禁用 (场景: {scenario_type})")
            logger.info(f"   原因: {co2_source_config.get('description', '副产CO₂循环利用不属于碳移除')}")

        # =========================================================================
        # 6. 汇总碳排放 (Carbon Emission Aggregation)
        # =========================================================================

        # 各类别汇总
        # 煤炭基SAF供应链：包含煤炭全生命周期排放
        self.carbon_aggregates['raw_material_emissions'] = (
            self.carbon_expressions['coal_mining'] +
            self.carbon_expressions['coal_transport'] +
            self.carbon_expressions['coal_gasification_direct'] +
            self.carbon_expressions['coal_gasification_energy'] +
            self.carbon_expressions['coal_co2_fugitive'] +
            self.carbon_expressions['co2_capture_energy']
        )

        self.carbon_aggregates['facility_emissions'] = (
            self.carbon_expressions['saf_facility'] +
            self.carbon_expressions['electrolyzer_facility']
        )

        self.carbon_aggregates['production_emissions'] = (
            self.carbon_expressions['methanol_to_saf'] +
            self.carbon_expressions['saf_synthesis_energy'] +  # ✨ 新增：SAF合成工艺能耗碳排放
            self.carbon_expressions['h2_production']
        )

        self.carbon_aggregates['storage_emissions'] = (
            self.carbon_expressions['mtj_storage'] +
            self.carbon_expressions['h2_storage']
        )

        self.carbon_aggregates['transport_emissions'] = (
            self.carbon_expressions['h2_transport'] +
            self.carbon_expressions['mtj_transport']
        )

        # CO₂利用负排放
        self.carbon_aggregates['co2_utilization_credit'] = self.carbon_expressions['co2_utilization_credit']

        # 总碳排放
        self.carbon_aggregates['total_emissions'] = (
            self.carbon_aggregates['raw_material_emissions'] +
            self.carbon_aggregates['facility_emissions'] +
            self.carbon_aggregates['production_emissions'] +
            self.carbon_aggregates['storage_emissions'] +
            self.carbon_aggregates['transport_emissions'] +
            self.carbon_aggregates['co2_utilization_credit']  # ✨ v3.0.1新增：CO₂固定在SAF中的负排放
        )

        # 将碳排放扩展到年化值（用于报告）
        self.carbon_aggregates['annual_emissions'] = (
            self.carbon_aggregates['total_emissions'] * operation_expansion_factor
        )

        # =========================================================================
        # 7. 碳强度相关组件表达式
        # =========================================================================
        # 注意：由于Gurobi不支持除法表达式，这里仅存储组件表达式
        # 实际的碳强度值需要在求解后通过getValue()获取分子分母再计算

        # 存储碳强度计算所需的常量参数
        self.carbon_params['saf_energy_content'] = self.carbon_params.get('benchmarks', {}).get('saf_energy_content', 43.15)  # MJ/kg
        self.carbon_params['traditional_jet_ci'] = self.carbon_params.get('benchmarks', {}).get('traditional_jet_fuel', 89)  # g CO2eq/MJ
        self.carbon_params['corsia_limit_ci'] = self.carbon_params.get('benchmarks', {}).get('corsia_limit', 30)  # g CO2eq/MJ

        # 碳强度分子：总碳排放（已在上面定义）
        # 碳强度分母：总产量（在performance_expressions中定义）
        # 实际碳强度计算公式：
        #   carbon_intensity_kg = total_emissions / production_total  [kg CO2eq/kg SAF]
        #   carbon_intensity_mj = carbon_intensity_kg * 1000 / saf_energy_content  [g CO2eq/MJ]
        #   vs_traditional_jet = (carbon_intensity_mj / traditional_jet_ci - 1) * 100  [%]
        #   vs_corsia = (carbon_intensity_mj / corsia_limit_ci - 1) * 100  [%]

        logger.info("碳排放表达式创建完成")
        logger.info(f"包含 {len(self.carbon_expressions)} 个细分项，{len(self.carbon_aggregates)} 个汇总项")
        logger.info("碳强度计算组件已准备，将在求解后计算具体数值")

        # 详细输出各表达式项
        logger.info("[调试] 碳排放表达式详情:")
        for name, expr in self.carbon_expressions.items():
            logger.info(f"  - {name}: {type(expr).__name__}")

        logger.info("[调试] 碳排放汇总项详情:")
        for name, expr in self.carbon_aggregates.items():
            logger.info(f"  - {name}: {type(expr).__name__}")

        logger.info(f"[调试] 优化时段: {self.time_horizon_weeks}周, 总小时数: {self.total_hours}小时")
        logger.info(f"[调试] 年化系数: {52.0 / self.time_horizon_weeks:.3f}")

        # 时间尺度一致性验证
        logger.info("="*60)
        logger.info("时间尺度一致性验证:")
        logger.info("  原料获取: CO₂捕获（按周计算）")
        logger.info("  设施建设: 年产能摊销到优化时段")
        logger.info("  生产过程: 按小时计算(production_vars, hydrogen_production_vars)")
        logger.info("  储存处理: 按小时计算(storage_vars, hydrogen_storage_vars)")
        logger.info("  运输配送: MTJ按周, H₂按总量, CO₂按周")
        logger.info("  最终结果: 所有项目累计为优化时段内总碳排放(kg CO2eq)")
        logger.info("="*60)

    def _create_performance_expressions(self):
        """创建性能指标表达式：产量、缺货、需求满足比例等

        注意：需求满足比例涉及除法运算，Gurobi不支持非线性表达式，
        因此存储分子和分母表达式，在求解后计算比例值。
        """
        logger.info("创建性能指标表达式...")

        # 初始化performance_expressions字典
        if not hasattr(self, 'performance_expressions'):
            self.performance_expressions = {}

        # 1. 总生产量表达式
        self.performance_expressions['production_total'] = gp.quicksum(
            var for var in self.production_vars.values()
        )
        logger.info(f"[调试] 创建总生产量表达式，包含 {len(self.production_vars)} 个生产变量")

        # 2. 缺货产量总和
        if hasattr(self, 'shortage_vars') and self.shortage_vars:
            self.performance_expressions['shortage_total'] = gp.quicksum(self.shortage_vars.values())
            logger.info(f"[调试] 创建缺货产量表达式，包含 {len(self.shortage_vars)} 个缺货变量")
        else:
            self.performance_expressions['shortage_total'] = gp.LinExpr(0)
            logger.info("[调试] 未找到缺货变量，缺货产量设为0")

        # 3. 总需求量（总产量 + 缺货产量）
        self.performance_expressions['total_demand'] = (
            self.performance_expressions['production_total'] +
            self.performance_expressions['shortage_total']
        )

        # 4. 氢气总产量
        if hasattr(self, 'hydrogen_production_vars') and self.hydrogen_production_vars:
            self.performance_expressions['hydrogen_total_production'] = gp.quicksum(
                self.hydrogen_production_vars.values()
            )
            logger.info(f"[调试] 创建氢气总产量表达式，包含 {len(self.hydrogen_production_vars)} 个变量")
        else:
            self.performance_expressions['hydrogen_total_production'] = gp.LinExpr(0)

        # 5. 甲醇总产量（如果有）
        if hasattr(self, 'methanol_production_vars') and self.methanol_production_vars:
            self.performance_expressions['methanol_total_production'] = gp.quicksum(
                self.methanol_production_vars.values()
            )
            logger.info(f"[调试] 创建甲醇总产量表达式，包含 {len(self.methanol_production_vars)} 个变量")
        else:
            self.performance_expressions['methanol_total_production'] = gp.LinExpr(0)

        # 6. 设施数量
        if hasattr(self, 'facility_vars') and self.facility_vars:
            self.performance_expressions['facilities_count'] = gp.quicksum(
                self.facility_vars.values()
            )
        else:
            self.performance_expressions['facilities_count'] = gp.LinExpr(0)

        # 7. 氢气设施数量
        if hasattr(self, 'electrolyzer_facility_vars') and self.electrolyzer_facility_vars:
            self.performance_expressions['hydrogen_facilities_count'] = gp.quicksum(
                self.electrolyzer_facility_vars.values()
            )
        else:
            self.performance_expressions['hydrogen_facilities_count'] = gp.LinExpr(0)

        logger.info("性能指标表达式创建完成")
        logger.info(f"包含 {len(self.performance_expressions)} 个性能表达式")
        logger.info("  - production_total: SAF总产量")
        logger.info("  - shortage_total: 缺货总量")
        logger.info("  - total_demand: 总需求量")
        logger.info("  - hydrogen_total_production: 氢气总产量")
        logger.info("  - methanol_total_production: 甲醇总产量")
        logger.info("  - facilities_count: MTJ设施数量")
        logger.info("  - hydrogen_facilities_count: 氢气设施数量")

    def _add_time_scale_matching_constraints(self):
        """添加改进的时间尺度匹配约束：允许累积生产和库存支持运输"""
        logger.info("添加改进的时间尺度匹配约束...")
        
        for location in self.locations:
            for airport in self.airports:
                for week in range(self.time_horizon_weeks):
                    week_end_hour = (week + 1) * self.hours_per_week
                    
                    # 累积生产量：从项目开始到该周结束的所有生产
                    cumulative_production = gp.quicksum(
                        self.production_vars[(location, tech, hour)]
                        for tech in self.technologies
                        for hour in range(week_end_hour)
                        if (location, tech, hour) in self.production_vars
                    )
                    
                    # 累积运输量：从项目开始到该周的所有运输
                    cumulative_transport = gp.quicksum(
                        self.transport_vars[(location, airport, w)]
                        for w in range(week + 1)
                        if (location, airport, w) in self.transport_vars
                    )
                    
                    # 当前库存水平（项目开始时库存为0）
                    current_inventory = self.storage_vars[(location, week_end_hour)]
                    
                    # 改进约束：累积运输 ≤ 累积生产 - 当前库存
                    # 这允许使用历史生产和释放库存来支持运输
                    self.model.addConstr(
                        cumulative_transport <= cumulative_production - current_inventory,
                        name=f"cumulative_balance_{location}_{airport}_{week}"
                    )
    
    def _add_production_capacity_constraints(self):
        """添加生产能力约束：基于产能决策变量"""
        for location in self.locations:
            for tech in self.technologies:
                for hour in range(self.total_hours):
                    if (location, tech, hour) in self.production_vars:
                        # 生产量不能超过设施产能
                        self.model.addConstr(
                            self.production_vars[(location, tech, hour)] <= 
                            self.facility_capacity_vars[(location, tech)],
                            name=f"capacity_{location}_{tech}_{hour}"
                        )
                
                # 产能只能在建设了设施的地方存在（大M约束）
                # 使用MTJ设施的最大容量上限作为大M值
                mtj_max_capacity = self.config.get('capacity_limits', {}).get('mtj_max_capacity_kg_per_hour', 100000)
                M = mtj_max_capacity  # 大M常数跟随MTJ工厂上限
                self.model.addConstr(
                    self.facility_capacity_vars[(location, tech)] <=
                    M * self.facility_vars[(location, tech)],
                    name=f"capacity_facility_link_{location}_{tech}"
                )

                # 【修复】添加最小经济规模约束（防止建了设施但容量为0）
                # 如果建设设施(facility_vars=1)，则容量必须≥最小经济规模
                # 如果不建设(facility_vars=0)，则容量必须为0
                min_economic_scale = self.config.get('capacity_limits', {}).get(
                    'saf_reactor_min_capacity_kg_per_hour', 100
                )
                self.model.addConstr(
                    self.facility_capacity_vars[(location, tech)] >=
                    min_economic_scale * self.facility_vars[(location, tech)],
                    name=f"min_capacity_{location}_{tech}"
                )
                logger.debug(f"添加最小容量约束: {location} {tech}, 最小规模={min_economic_scale} kg/h")

                # 移除基于平均发电量的硬性产能上限约束
                # 改为依赖动态的时段级约束：
                # 1. 氢气生产受每时段发电量限制 (在_add_renewable_power_constraints中)
                # 2. MTJ生产受氢气库存限制 (在_add_material_supply_constraints中)
                # 这样允许设施产能更灵活，只要满足实际运行时的供需平衡即可
    
    def _add_material_supply_constraints(self):
        """添加严格的小时级原料供应约束（氢气和天然气供应约束）"""
        logger.info(f"开始添加严格的小时级原料供应约束，共有{len(self.locations)}个位置")
        
        for location in self.locations:
            location_type = self.locations[location]['type']
            location_info = self.locations[location]
            
            # 检查位置数据完整性
            for key, value in location_info.items():
                # 跳过某些可能为空的非关键字段
                skip_fields = ['hourly_generation', 'operator', 'description', 'notes', 'comments']
                if key in skip_fields:
                    continue
                elif isinstance(value, (list, np.ndarray)):
                    # 对于数组类型，检查是否有任何NaN值
                    if np.any(pd.isna(value)):
                        raise ValueError(f"位置数据包含NaN值: {location}.{key} 数组中有NaN")
                elif pd.isna(value):
                    # 对于标量值，直接检查
                    raise ValueError(f"位置数据包含NaN值: {location}.{key} = {value}")
            
            for hour in range(self.total_hours):
                # 1. 为所有位置添加氢气供应约束：MTJ生产所需氢气不能超过可用氢气
                h2_demand = gp.quicksum(
                    self.production_vars[(location, tech, hour)] *
                    self.technologies[tech]['h2_consumption_ratio']
                    for tech in self.technologies
                    if (location, tech, hour) in self.production_vars and
                       self.technologies[tech]['h2_consumption_ratio'] > 0
                )

                if h2_demand.size() > 0:
                    if location_type not in ['solar_plant', 'wind_farm']:
                        # 其他位置（机场、LNG终端）：氢气需求必须通过运输满足
                        # 这里先输出调试信息，实际供给由运输/库存约束处理
                        logger.debug(f"位置 {location} 在第{hour}小时有氢气需求，需要运输供应")

                # 【已优化】仅对副产氢设施添加电力供应约束
                # solar_plant 和 wind_farm 的电力约束由 electricity_balance 统一处理
                # （在 _add_hydrogen_production_constraints 中，约束更严格：包含制氢+SAF合成电力）
                if location_type in ['byproduct_hydrogen_steel', 'byproduct_hydrogen_refinery']:
                    # 副产氢设施：添加电力供应约束
                    self._add_renewable_power_constraints(location, hour)
        
        # 移除设备维护停机时间约束 - 这是导致20%利用率的主因
        # self._add_maintenance_downtime_constraints()  # 注释掉
        
        # 6. 氢气运输能力限制约束
        self._add_hydrogen_transport_capacity_constraints()
        
        logger.info("严格的小时级原料供应约束添加完成（已移除维护停机约束）")
    
    def _add_renewable_power_constraints(self, location: str, hour: int):
        """添加可再生能源电力供应约束（支持3小时时间粒度）"""
        location_info = self.locations[location]

        # 该时段可用电力 (MWh) = 功率(MW) × 时间(小时)
        # 对于3小时粒度：MWh = MW × hours_per_period
        # 对于1小时粒度：MWh = MW × 1
        if 'hourly_generation' in location_info and hour < len(location_info['hourly_generation']):
            power_mw = location_info['hourly_generation'][hour]  # 平均功率 MW
            available_power_mwh = power_mw * self.hours_per_period  # 该期间可用电力 MWh
        else:
            available_power_mwh = 0.0
        
        # 添加电力供应约束
        if available_power_mwh > 0:
            self.model.addConstr(
                self.hydrogen_production_vars[(location, hour)] * 
                self.costs['electrolysis_power_consumption'] / 1000 <= available_power_mwh,
                name=f"power_supply_{location}_{hour}"
            )

    def _add_maintenance_downtime_constraints(self):
        """添加设备维护停机时间约束"""
        logger.info("添加设备维护停机时间约束...")
        
        for location in self.locations:
            for tech in self.technologies:
                # 每周安排4小时维护时间（设备不能生产）
                maintenance_hours = []
                for week in range(self.time_horizon_weeks):
                    # 每周的维护时间：每周开始后的第1-4小时
                    # （如果week从周一0点开始，则为周一凌晨1-4点）
                    week_start_hour = week * self.hours_per_week
                    maintenance_hours.extend([
                        week_start_hour + 1,  # 第1小时
                        week_start_hour + 2,  # 第2小时
                        week_start_hour + 3,  # 第3小时
                        week_start_hour + 4   # 第4小时
                    ])
                
                # 在维护时间内，生产为0
                for maintenance_hour in maintenance_hours:
                    if maintenance_hour < self.total_hours and (location, tech, maintenance_hour) in self.production_vars:
                        self.model.addConstr(
                            self.production_vars[(location, tech, maintenance_hour)] == 0,
                            name=f"maintenance_{location}_{tech}_{maintenance_hour}"
                        )
        
        logger.info(f"为每个设施每周添加了4小时维护停机约束")
    
    def _add_hydrogen_transport_capacity_constraints(self):
        """添加氢气运输能力限制约束"""
        logger.info("添加氢气运输能力限制约束...")

        # 【禁用罐车运输】注释掉氢气罐车运输能力限制约束
        """
        if not hasattr(self, 'hydrogen_transport_vars'):
            return

        # 氢气运输车辆调度约束（改为天级）
        for h_loc in self.hydrogen_locations:
            total_days = self.total_hours // 24
            for day in range(total_days):
                # 从配置文件读取氢气运输车辆参数
                h2_transport_config = self.config.get('objective_coefficients', {}).get('hydrogen_transport_vehicle', {})
                max_vehicles_per_day = h2_transport_config.get('max_vehicles_per_day', 48)  # 每天最多车次
                vehicle_capacity_kg = h2_transport_config.get('vehicle_capacity_kg', 500)  # 每辆车氢气容量
                max_h2_transport_per_day = max_vehicles_per_day * vehicle_capacity_kg

                # 从该地点运出的总氢气不能超过运输能力（周级）
                total_h2_transport = gp.quicksum(
                    self.hydrogen_transport_vars[(h_loc, dest)]
                    for dest in sum(self.mtj_locations.values(), [])
                    if (h_loc, dest) in self.hydrogen_transport_vars
                )

                if total_h2_transport.size() > 0:
                    # 周级约束：7天的运输能力
                    max_h2_transport_per_week = max_h2_transport_per_day * 7
                    self.model.addConstr(
                        total_h2_transport <= max_h2_transport_per_week,
                        name=f"h2_transport_capacity_{h_loc}_weekly"
                    )
        """
        logger.info("【禁用罐车运输】跳过氢气罐车运输能力限制约束")
        
        logger.info("氢气运输能力限制约束添加完成")
    
    def _add_inventory_balance_constraints(self):
        """添加库存平衡约束

        【修改说明 v5.0】
        SAF库存改为周积累模式：
        - 生产地累积库存，不再每小时平摊出库
        - 在每周的最后一个期间统一出库运输到机场
        - 库存平衡：仅在最后一个期间时出库，其他时间只生产累积

        【修改说明 v5.1 - 3小时粒度适配】
        - 使用 periods_per_week 替代硬编码的168
        - 每周最后一个期间索引 = periods_per_week - 1
        """
        # 每周最后一个期间的索引（用于统一出库）
        last_period_in_week = self.periods_per_week - 1  # 3小时粒度时为55，1小时粒度时为167

        for location in self.locations:
            # 计算该location所有周的运输总量
            weekly_transports = {}
            for week in range(self.time_horizon_weeks):
                weekly_transports[week] = gp.quicksum(
                    self.transport_vars[(location, airport, week)]
                    for airport in self.airports
                    if (location, airport, week) in self.transport_vars
                )

            for hour in range(self.total_hours):
                # 库存平衡：当前库存 = 上期库存 + 生产 - 出库
                current_inventory = self.storage_vars[(location, hour + 1)]
                previous_inventory = self.storage_vars[(location, hour)]

                # 当前期间总生产
                production = gp.quicksum(
                    self.production_vars[(location, tech, hour)]
                    for tech in self.technologies
                    if (location, tech, hour) in self.production_vars
                )

                # 出库量：仅在每周的最后一个期间统一出库
                current_week = hour // self.periods_per_week
                hour_in_week = hour % self.periods_per_week

                if hour_in_week == last_period_in_week:  # 每周最后一个期间统一出库
                    outflow = weekly_transports.get(current_week, gp.LinExpr(0))
                else:
                    outflow = gp.LinExpr(0)

                self.model.addConstr(
                    current_inventory == previous_inventory + production - outflow,
                    name=f"inventory_balance_{location}_{hour}"
                )

            # 初始库存为0
            self.model.addConstr(
                self.storage_vars[(location, 0)] == 0,
                name=f"initial_inventory_{location}"
            )
    
    def _add_airport_demand_constraints(self):
        """添加机场周时间序列需求约束（软约束：允许缺货但有惩罚）"""
        for airport in self.airports:
            weekly_demand_series = self.airports[airport]['weekly_demand_series']  # 52周序列
            
            for week in range(self.time_horizon_weeks):
                # 获取该周的实际需求
                if week < len(weekly_demand_series):
                    weekly_demand = weekly_demand_series[week]
                else:
                    weekly_demand = 0.0  # 超出范围的周需求为0
                
                # 该机场该周的总运输量
                total_supply = gp.quicksum(
                    self.transport_vars[(location, airport, week)]
                    for location in self.locations
                    if (location, airport, week) in self.transport_vars
                )
                
                # 软约束：供应量 + 缺货量 = 需求量
                if weekly_demand > 0:
                    self.model.addConstr(
                        total_supply + self.shortage_vars[(airport, week)] >= weekly_demand,
                        name=f"demand_{airport}_{week}"
                    )
    
    def _add_facility_selection_constraints(self):
        """添加设施选择约束"""
        for location in self.locations:
            for tech in self.technologies:
                # 检查技术-位置兼容性
                tech_info = self.technologies[tech]
                location_type = self.locations[location]['type']
                
                if location_type not in tech_info['suitable_locations']:
                    # 不兼容的技术-位置组合：禁止建设
                    self.model.addConstr(
                        self.facility_vars[(location, tech)] == 0,
                        name=f"tech_location_compat_{location}_{tech}"
                    )
                    # 同时禁止产能分配
                    self.model.addConstr(
                        self.facility_capacity_vars[(location, tech)] == 0,
                        name=f"capacity_location_compat_{location}_{tech}"
                    )
    
    def _add_hydrogen_production_constraints(self):
        """添加制氢约束"""
        logger.info("添加制氢约束...")
        
        for location in self.locations:
            location_type = self.locations[location]['type']
            
            if location_type in ['solar_plant', 'wind_farm', 'byproduct_hydrogen_steel', 'byproduct_hydrogen_refinery']:
                # 1. 电解槽/副产氢产能上限约束（差异化处理）
                if location_type in ['byproduct_hydrogen_steel', 'byproduct_hydrogen_refinery']:
                    # 副产氢设施：使用从CSV读取的实际产能上限
                    byproduct_h2_max_capacity = self.locations[location].get('capacity_mw', 0)  # 实际是kg/h
                    self.model.addConstr(
                        self.electrolyzer_capacity_vars[location] <= byproduct_h2_max_capacity,
                        name=f"byproduct_h2_capacity_limit_{location}"
                    )
                    logger.debug(f"副产氢 {location}: 产能上限 {byproduct_h2_max_capacity:.2f} kg/h")
                else:
                    # 可再生能源站点：使用配置中的电解槽最大容量
                    max_electrolyzer_capacity = self.config.get('capacity_limits', {}).get('electrolyzer_max_capacity_kg_per_hour', 2000)
                    self.model.addConstr(
                        self.electrolyzer_capacity_vars[location] <=
                        max_electrolyzer_capacity * self.electrolyzer_facility_vars[location],
                        name=f"electrolyzer_capacity_{location}"
                    )

                # 获取发电数据（所有设施都需要，副产氢会得到空列表）
                hourly_generation = self.locations[location].get('hourly_generation', [])
                total_generation_mwh = float(np.sum(hourly_generation)) if isinstance(hourly_generation, (list, np.ndarray)) else 0.0
                positive_hours = sum(1 for g in hourly_generation if g > 1e-6)

                # 调试日志输出（根据类型输出不同信息）
                if location_type in ['byproduct_hydrogen_steel', 'byproduct_hydrogen_refinery']:
                    logger.debug(f"[调试][氢源] {location} (副产氢): 产能上限 {self.locations[location].get('capacity_mw', 0):.2f} kg/h")
                else:
                    if len(hourly_generation) != self.total_hours:
                        logger.warning(
                            f"[调试][氢源] {location}: hourly_generation 长度 {len(hourly_generation)} "
                            f"与 total_hours {self.total_hours} 不一致"
                        )
                    max_electrolyzer_capacity = self.config.get('capacity_limits', {}).get('electrolyzer_max_capacity_kg_per_hour', 2000)
                    logger.debug(
                        f"[调试][氢源] {location}: 可用电量总计 {total_generation_mwh:.2f} MWh, "
                        f"正值小时 {positive_hours}/{self.total_hours}, "
                        f"电解槽容量上限 {max_electrolyzer_capacity} kg H2/h"
                    )


                
                # 2. 制氢生产能力约束
                for hour in range(self.total_hours):
                    self.model.addConstr(
                        self.hydrogen_production_vars[(location, hour)] <=
                        self.electrolyzer_capacity_vars[location],
                        name=f"h2_production_capacity_{location}_{hour}"
                    )

                    # 3. 根据设施类型添加不同的供应约束（支持3小时时间粒度）
                    if location_type in ['byproduct_hydrogen_steel', 'byproduct_hydrogen_refinery']:
                        # 副产氢设施：小时级氢气供应约束
                        # hourly_generation中存储的是氢气产量率（kg/h），需乘以期间小时数得总量
                        available_h2_kg = 0.0
                        if hour < len(hourly_generation):
                            h2_rate_kg_per_h = hourly_generation[hour]  # kg/h
                            available_h2_kg = h2_rate_kg_per_h * self.hours_per_period  # 期间总可用氢气 kg

                        # 约束：该期间的氢气生产不能超过可用供应量
                        if available_h2_kg > 0:
                            self.model.addConstr(
                                self.hydrogen_production_vars[(location, hour)] <= available_h2_kg,
                                name=f"byproduct_h2_supply_{location}_{hour}"
                            )
                    else:
                        # 可再生能源站点：电力平衡约束（支持3小时时间粒度）
                        # hourly_generation中存储的是功率(MW)，需乘以期间小时数得MWh
                        available_energy_mwh = 0.0
                        if hour < len(hourly_generation):
                            power_mw = hourly_generation[hour]  # 平均功率 MW
                            available_energy_mwh = power_mw * self.hours_per_period  # 期间可用电力 MWh

                        # 制氢耗电：55 kWh/kg H2
                        h2_electricity_consumption_mwh = (
                            self.hydrogen_production_vars[(location, hour)] *
                            self.costs['electrolysis_power_consumption'] / 1000  # kWh -> MWh
                        )

                        # SAF合成耗电（仅当SAF工厂建在可再生能源站点时计入）
                        # 修正日期：2025-11-09
                        # 注：煤制路线仅计算SAF合成能耗7.6 kWh/kg（MTJ能耗忽略）
                        saf_synthesis_energy_kwh_per_kg = 7.6  # kWh/kg SAF (RWGS+FT合成能耗)
                        saf_electricity_consumption_mwh = gp.quicksum(
                            self.production_vars.get((location, tech, hour), gp.LinExpr(0)) *
                            saf_synthesis_energy_kwh_per_kg / 1000  # kWh -> MWh
                            for tech in self.technologies
                            if (location, tech, hour) in self.production_vars
                        )

                        # 总电力消耗 = 制氢耗电 + SAF合成耗电（仅可再生站点）
                        total_electricity_consumption_mwh = h2_electricity_consumption_mwh + saf_electricity_consumption_mwh

                        # 电力平衡：总耗电不能超过可再生能源发电量
                        if available_energy_mwh > 0:
                            self.model.addConstr(
                                total_electricity_consumption_mwh <= available_energy_mwh,
                                name=f"electricity_balance_{location}_{hour}"
                            )
                        
    def _add_hydrogen_balance_constraints(self):
        """添加氢气平衡约束

        【修改说明 v4.0】
        1. 氢气生产位置（solar_plant/wind_farm）：
           - 改为累计库存模式，不强制平均出库
           - 在每周最后一个期间时统一出库全部周级运输量
           - 库存平衡：当前库存 = 上期库存 + 生产 - 本地消耗 - 出库

        2. 氢气消纳位置（lng_terminal/airport）：
           - 在每周第一个期间时统一接收全部周级运输量
           - v3.1一步法：库存平衡 = 上期库存 + 入库 - SAF生产消耗

        3. 此修改允许氢气在生产地累积，避免强制每小时平均出库的约束

        【修改说明 v5.1 - 3小时粒度适配】
        - 使用 periods_per_week 替代硬编码的168
        - 每周最后一个期间索引 = periods_per_week - 1
        """
        # 每周最后一个期间的索引（用于统一出库）
        last_period_in_week = self.periods_per_week - 1  # 3小时粒度时为55，1小时粒度时为167

        logger.info(f"添加氢气平衡约束（v4.0: 累计库存，{last_period_in_week}期出库/0期入库）...")

        for location in self.locations:
            location_type = self.locations[location]['type']

            if location_type in ['solar_plant', 'wind_farm', 'byproduct_hydrogen_steel', 'byproduct_hydrogen_refinery']:
                # 氢气库存平衡（改为累计库存模式，最后一个期间时统一出库）
                # 计算周级运输总量
                weekly_pipeline_outflow = gp.LinExpr(0)
                if hasattr(self, 'hydrogen_pipeline_transport_vars') and self.hydrogen_pipeline_transport_vars:
                    weekly_pipeline_outflow = gp.quicksum(
                        self.hydrogen_pipeline_transport_vars[(location, dest_loc)]
                        for dest_loc in self.locations
                        if (location, dest_loc) in self.hydrogen_pipeline_transport_vars
                    )
                    connected_destinations = [
                        dest_loc for dest_loc in self.locations
                        if (location, dest_loc) in self.hydrogen_pipeline_transport_vars
                    ]
                    if connected_destinations:
                        logger.debug(
                            f"[调试][氢源库存v4.0] {location}: 周级管道运输总量（{last_period_in_week}期统一出库）, "
                            f"连接目的地数量 {len(connected_destinations)}, "
                            f"示例 {connected_destinations[:5]}"
                        )
                    else:
                        logger.debug(f"[调试][氢源库存v4.0] {location}: 未发现管道连接")
                else:
                    logger.debug(f"[调试][氢源库存v4.0] {location}: 未创建管道运输变量")

                logger.info(f"[氢源库存v4.0] {location}: 添加累计库存约束（{last_period_in_week}期统一出库）")
                for hour in range(self.total_hours):
                    # 当前氢气库存 = 上期库存 + 制氢生产 - 本地MTJ消耗 - 运输出库
                    current_h2_inventory = self.hydrogen_storage_vars[(location, hour + 1)]
                    previous_h2_inventory = self.hydrogen_storage_vars[(location, hour)]
                    h2_production = self.hydrogen_production_vars[(location, hour)]

                    # 氢气消耗（用于本地MTJ生产）
                    h2_local_consumption = gp.quicksum(
                        self.production_vars[(location, tech, hour)] *
                        self.technologies[tech]['h2_consumption_ratio']
                        for tech in self.technologies
                        if (location, tech, hour) in self.production_vars
                    )

                    # 氢气运输出库：每周最后一个期间时统一出库
                    h2_transport_outflow = gp.LinExpr(0)
                    if hour % self.periods_per_week == last_period_in_week:  # 每周最后一个期间出库
                        h2_transport_outflow = weekly_pipeline_outflow

                    # 氢气库存平衡方程（累计库存模式）
                    self.model.addConstr(
                        current_h2_inventory == previous_h2_inventory + h2_production - h2_local_consumption - h2_transport_outflow,
                        name=f"h2_balance_{location}_{hour}"
                    )

                # 初始氢气库存为0
                self.model.addConstr(
                    self.hydrogen_storage_vars[(location, 0)] == 0,
                    name=f"initial_h2_inventory_{location}"
                )

                # 【已优化】氢气库存非负约束已通过变量下界 lb=0 实现，无需单独约束

            # 【v3.1一步法】为MTJ工厂位置添加氢气库存平衡（直接使用SAF产量计算H₂消耗）
            elif location_type in ['lng_terminal', 'airport']:
                logger.info(f"[MTJ库存v4.0] {location}: 添加氢气库存平衡（0h统一入库）")

                # 计算周级运输总入库量
                weekly_h2_inflow = gp.quicksum(
                    self.hydrogen_pipeline_transport_vars[(h_loc, location)]
                    for h_loc in self.hydrogen_locations
                    if (h_loc, location) in self.hydrogen_pipeline_transport_vars
                )

                # 统计入库来源
                h2_source_count = sum(
                    1 for h_loc in self.hydrogen_locations
                    if (h_loc, location) in self.hydrogen_pipeline_transport_vars
                )
                if h2_source_count > 0:
                    logger.debug(f"[MTJ库存v4.0] {location}: 氢气来源数量 {h2_source_count}")
                else:
                    logger.warning(f"[MTJ库存v4.0] {location}: 没有氢气管道入库来源！")

                for hour in range(self.total_hours):
                    current_h2_inventory = self.hydrogen_storage_vars[(location, hour + 1)]
                    previous_h2_inventory = self.hydrogen_storage_vars[(location, hour)]

                    # MTJ位置：氢气入库每周第一个小时统一入库
                    h2_inflow = gp.LinExpr(0)
                    if hour % self.hours_per_week == 0:  # 每周第一个小时入库（索引0）
                        h2_inflow = weekly_h2_inflow

                    # v3.1一步法：MTJ消耗的氢气（直接从SAF产量计算）
                    # SAF_prod (kg SAF/hour) * (kg H₂ / kg SAF)
                    h2_consumption = gp.quicksum(
                        self.production_vars[(location, tech, hour)] *
                        self.technologies[tech]['h2_consumption_ratio']
                        for tech in self.technologies
                        if (location, tech, hour) in self.production_vars
                    )

                    # v3.1一步法：库存平衡方程（当前库存 = 上期库存 + 管道入库 - SAF生产消耗）
                    self.model.addConstr(
                        current_h2_inventory == previous_h2_inventory + h2_inflow - h2_consumption,
                        name=f"h2_balance_mtj_{location}_{hour}"
                    )

                # 初始氢气库存为0
                self.model.addConstr(
                    self.hydrogen_storage_vars[(location, 0)] == 0,
                    name=f"initial_h2_inventory_mtj_{location}"
                )

                # 【已优化】氢气库存非负约束已通过变量下界 lb=0 实现，无需单独约束

        logger.info("氢气平衡约束添加完成（包含发电站和MTJ工厂）")

    def _add_daily_hydrogen_mtj_constraints(self):
        """添加氢气每日产量限制下一日MTJ每日产量约束"""
        logger.info("跳过每日氢气产量与次日需求耦合约束（由库存与运输约束统一管理）")
        return
        
    def _add_hydrogen_transport_constraints(self):
        """添加氢气运输约束：氢气从可再生能源站运输到MTJ工厂"""
        logger.info("添加氢气运输约束...")

        # 1. 添加氢气全局守恒约束：确保周运输总量不超过周生产总量
        logger.info("添加氢气全局守恒约束（周级）...")

        # 计算整周全系统氢气总生产量（按周平均）
        weeks = max(1, self.time_horizon_weeks)
        total_weekly_h2_production = gp.quicksum(
            self.hydrogen_production_vars[(h_loc, hour)]
            for h_loc in self.hydrogen_locations
            for hour in range(self.total_hours)
            if (h_loc, hour) in self.hydrogen_production_vars
        ) / float(weeks)

        # 计算整周全系统氢气总运输量（【禁用罐车运输】仅管道运输）
        # 【禁用罐车运输】注释掉罐车运输变量
        """
        total_weekly_transport = gp.quicksum(
            self.hydrogen_transport_vars[(h_loc, mtj_loc)]
            for h_loc in self.hydrogen_locations
            for mtj_loc in self.locations
            if (h_loc, mtj_loc) in self.hydrogen_transport_vars
        )
        """
        total_weekly_transport = gp.LinExpr(0)  # 【禁用罐车运输】

        # 添加管道运输（也是周级）
        if hasattr(self, 'hydrogen_pipeline_transport_vars') and self.hydrogen_pipeline_transport_vars:
            pipeline_weekly_transport = gp.quicksum(
                self.hydrogen_pipeline_transport_vars[(h_loc, mtj_loc)]
                for h_loc in self.hydrogen_locations
                for mtj_loc in self.locations
                if (h_loc, mtj_loc) in self.hydrogen_pipeline_transport_vars
            )
            total_weekly_transport += pipeline_weekly_transport

        # 全局守恒约束：周运输总量不能超过周生产总量
        if total_weekly_h2_production.size() > 0:
            self.model.addConstr(
                total_weekly_transport <= total_weekly_h2_production,
                name="hydrogen_global_conservation_weekly"
            )
            logger.info("添加氢气全局守恒约束（周级）完成")

        # 2. 氢气运输平衡约束：仅对需要氢气运输的模式
        for tech in self.technologies.keys():
            if not self.technologies[tech]['hydrogen_transport_required']:
                logger.info(f"技术 {tech} 不需要氢气运输，跳过")
                continue
                
            if tech not in self.mtj_locations:
                logger.warning(f"技术 {tech} 不在 mtj_locations 中，跳过")
                continue
                
            locations = self.mtj_locations[tech]
            if not hasattr(locations, '__iter__') or isinstance(locations, str):
                logger.error(f"技术 {tech} 的位置不可迭代: {locations} (类型: {type(locations)})")
                continue
                
            for h_loc in self.hydrogen_locations:
                for mtj_loc in locations:
                        # 【禁用罐车运输】注释掉罐车运输生产限制约束
                        """
                        if (h_loc, mtj_loc) in self.hydrogen_transport_vars:
                            # 氢气运输量 <= 整周氢气生产量总和（单链路约束）
                            weekly_h2_production = gp.quicksum(
                                self.hydrogen_production_vars[(h_loc, hour)]
                                for hour in range(self.total_hours)
                                if (h_loc, hour) in self.hydrogen_production_vars
                            )
                            self.model.addConstr(
                                self.hydrogen_transport_vars[(h_loc, mtj_loc)] <= weekly_h2_production,
                                name=f"hydrogen_transport_limit_{h_loc}_{mtj_loc}"
                                )
                        """
                        pass  # 【禁用罐车运输】

        # 3. 添加源地总出库约束：从每个氢气源地出库的总量不能超过该地周生产量
        logger.info("添加氢气源地总出库约束（周级）...")
        for h_loc in self.hydrogen_locations:
            # 该源地整周的氢气生产总量
            weeks = max(1, self.time_horizon_weeks)
            weekly_h2_production = gp.quicksum(
                self.hydrogen_production_vars[(h_loc, hour)]
                for hour in range(self.total_hours)
                if (h_loc, hour) in self.hydrogen_production_vars
            ) / float(weeks)

            # 【禁用罐车运输】注释掉罐车运输出库量
            """
            # 从该源地出发的所有运输量（罐车，周级）
            total_outbound_transport = gp.quicksum(
                self.hydrogen_transport_vars[(h_loc, dest_loc)]
                for dest_loc in self.locations
                if (h_loc, dest_loc) in self.hydrogen_transport_vars
            )
            """
            total_outbound_transport = gp.LinExpr(0)  # 【禁用罐车运输】

            # 从该源地出发的所有管道运输量（周级）
            if hasattr(self, 'hydrogen_pipeline_transport_vars') and self.hydrogen_pipeline_transport_vars:
                total_outbound_pipeline = gp.quicksum(
                    self.hydrogen_pipeline_transport_vars[(h_loc, dest_loc)]
                    for dest_loc in self.locations
                    if (h_loc, dest_loc) in self.hydrogen_pipeline_transport_vars
                )
                total_outbound_transport += total_outbound_pipeline

            # 源地总出库约束：周总出库不能超过该地周生产量
            if weekly_h2_production.size() > 0:
                self.model.addConstr(
                    total_outbound_transport <= weekly_h2_production,
                    name=f"hydrogen_source_outbound_limit_{h_loc}_weekly"
                )
                logger.debug(f"添加氢气源地总出库约束（周级）: {h_loc}")
        
        # 氢气供需平衡约束：对所有消耗氢气的技术添加约束，确保氢气供应满足需求
        logger.info("添加氢气供需平衡约束...")

        # 初始化日运输供应项字典
        # 遍历所有消耗氢气的技术（不论是否需要运输）
        for tech in self.technologies:
            # 只处理消耗氢气的技术
            if self.technologies[tech]['h2_consumption_ratio'] <= 0:
                continue

            if tech not in self.mtj_locations:
                logger.warning(f"技术 {tech} 不在 mtj_locations 中，跳过氢气需求约束")
                continue

            locations = self.mtj_locations[tech]
            if not hasattr(locations, '__iter__') or isinstance(locations, str):
                logger.error(f"技术 {tech} 的位置不可迭代: {locations} (类型: {type(locations)})")
                continue
                
            for mtj_loc in locations:
                total_days = self.total_hours // 24
                for day in range(total_days):
                    # 计算该MTJ工厂该天的氢气需求（基于生产量）
                    day_start_hour = day * 24
                    day_end_hour = min((day + 1) * 24, self.total_hours)

                    hydrogen_demand_terms = []
                    for hour in range(day_start_hour, day_end_hour):
                        if (mtj_loc, tech, hour) in self.production_vars:
                            h2_consumption = self.technologies[tech]['h2_consumption_ratio']
                            hydrogen_demand_terms.append(
                                self.production_vars[(mtj_loc, tech, hour)] * h2_consumption
                            )

                    if not hydrogen_demand_terms:
                        continue  # 该天无氢气需求，跳过

                    hydrogen_demand = gp.quicksum(hydrogen_demand_terms)

                    # 需求由库存/运输平衡统一约束，这里仅记录调试信息后跳过旧的日度供给限制
                    if self.technologies[tech]['hydrogen_transport_required']:
                        logger.debug(f"记录氢气日需求（运输模式）: {mtj_loc} {tech} day {day}")
                    else:
                        logger.debug(f"记录氢气日需求（本地模式）: {mtj_loc} {tech} day {day}")
                    continue


        logger.info("氢气供需平衡约束添加完成")
    
    def _add_hydrogen_pipeline_transport_constraints(self):
        """添加氢能管道运输约束（修复版：变量是周级，索引为二元组）"""
        logger.info("添加氢能管道运输约束...")

        if not hasattr(self, 'hydrogen_pipeline_transport_vars') or not self.hydrogen_pipeline_transport_vars:
            logger.info("无氢能管道运输变量，跳过管道运输约束")
            return

        logger.info(f"[修复] 检测到 {len(self.hydrogen_pipeline_transport_vars)} 个管道运输变量（周级，索引为二元组）")

        # 1. 管道容量约束：【禁用管道建设决策】管道默认可用，直接使用容量上限约束
        # 修复：管道运输变量是周级的，索引为 (h2_loc, mtj_loc)，不是 (h2_loc, mtj_loc, day)
        pipeline_capacity_constrs = 0
        for (h2_loc, mtj_loc) in self.hydrogen_pipeline_transport_vars:
            # 【禁用管道建设决策】管道默认可用，直接使用容量上限
            max_daily_pipeline_capacity = self.config.get('capacity_limits', {}).get('hydrogen_pipeline_max_daily_capacity_kg', 50000)
            days_per_week = max(1.0, self.real_hours_per_week / 24.0)  # 使用real_hours_per_week计算天数
            max_weekly_pipeline_capacity = max_daily_pipeline_capacity * days_per_week

            self.model.addConstr(
                self.hydrogen_pipeline_transport_vars[(h2_loc, mtj_loc)] <= max_weekly_pipeline_capacity,
                name=f"h2_pipeline_capacity_{h2_loc}_{mtj_loc}_week"
            )
            pipeline_capacity_constrs += 1

        logger.info(f"[修复] 添加了 {pipeline_capacity_constrs} 个管道容量约束（周级）")

        # 【已优化】删除冗余的管道单链路约束
        # 原约束 h2_pipeline_production_limit_{h2_loc}_{mtj_loc}_week 已被
        # hydrogen_source_outbound_limit_{h_loc}_weekly 约束覆盖（源地总出库约束）
        # 单链路约束是冗余的，删除可减少约 1.2 万个约束

        # 【禁用罐车运输】注释掉氢气运输方式排他性约束
        """
        # 3. 氢气运输方式排他性约束：同一路线只能选择罐车或管道运输之一
        for tech in self.technologies.keys():
            if not self.technologies[tech]['hydrogen_transport_required']:
                continue

            if tech not in self.mtj_locations:
                continue

            locations = self.mtj_locations[tech]
            if not hasattr(locations, '__iter__') or isinstance(locations, str):
                continue

            for h2_loc in self.hydrogen_locations:
                for mtj_loc in locations:
                    # 检查周级运输变量是否存在，添加排他约束
                    has_truck = (h2_loc, mtj_loc) in self.hydrogen_transport_vars
                    has_pipeline = (h2_loc, mtj_loc) in self.hydrogen_pipeline_transport_vars

                    if has_truck and has_pipeline:
                        # 互斥约束1：如果选择了管道运输，则罐车运输为0
                        max_truck_capacity = self.config.get('capacity_limits', {}).get('hydrogen_truck_max_daily_capacity_kg', 10000)
                        max_truck_weekly_capacity = max_truck_capacity * 7  # 转换为周容量
                        self.model.addConstr(
                            self.hydrogen_transport_vars[(h2_loc, mtj_loc)] <=
                            max_truck_weekly_capacity * (1 - self.hydrogen_pipeline_facility_vars[(h2_loc, mtj_loc)]),
                            name=f"h2_truck_exclusive_{h2_loc}_{mtj_loc}_weekly"
                        )

                        # 互斥约束2：如果不选择管道运输，则管道运输为0
                        max_pipeline_capacity = self.config.get('capacity_limits', {}).get('hydrogen_pipeline_max_daily_capacity_kg', 50000)
                        max_pipeline_weekly_capacity = max_pipeline_capacity * 7  # 转换为周容量
                        self.model.addConstr(
                            self.hydrogen_pipeline_transport_vars[(h2_loc, mtj_loc)] <=
                            max_pipeline_weekly_capacity * self.hydrogen_pipeline_facility_vars[(h2_loc, mtj_loc)],
                            name=f"h2_pipeline_exclusive_{h2_loc}_{mtj_loc}_weekly"
                        )
        """
        
        # 注意：氢气需求满足约束已在 _add_hydrogen_transport_constraints() 中统一处理
        logger.info("氢能管道运输约束添加完成（需求满足约束已在主要氢气运输约束中处理）")
    
    def _create_objective(self):
        """创建目标函数：最小化项目20年生命周期总成本（使用已创建的成本表达式）"""
        logger.info("设置目标函数（使用统一的成本表达式）...")

        # 验证成本表达式已经创建
        if not hasattr(self, 'cost_aggregates') or 'total_cost_excluding_shortage' not in self.cost_aggregates:
            raise RuntimeError("成本表达式尚未创建，请先调用 _create_cost_expressions()")

        # 验证短缺成本表达式存在
        if not hasattr(self, 'cost_expressions') or 'shortage_cost' not in self.cost_expressions:
            raise RuntimeError("短缺成本表达式尚未创建，请先调用 _create_cost_expressions()")

        # 项目20年生命周期总成本（包含短缺成本）
        total_cost = (
            self.cost_aggregates['total_cost_excluding_shortage'] +
            self.cost_expressions['shortage_cost']
        )

        # 设置目标函数：最小化项目20年生命周期总成本
        self.model.setObjective(total_cost, GRB.MINIMIZE)

        logger.info("目标函数设置完成（使用统一成本表达式）")
    
    
    def _calculate_mtj_transport_cost_by_distance(self, distance_km: float) -> float:
        """基于运输理论公式计算MTJ运输成本
        
        公式: c_kg(S) = F_trip/Q_kg + v_km/Q_kg * S
        
        Args:
            distance_km: 运输距离(公里)
            
        Returns:
            float: 单位运输成本(元/kg)
        """
        # 从配置文件读取基于公式的运输参数
        formula_config = self.config.get('cost_parameters', {}).get('transport', {}).get('formula_based_transport', {})
        
        # F_trip: 单次往返固定成本(元/趟)
        F_trip = formula_config.get('trip_fixed_cost', 2000)
        
        # v_km: 单位里程变动成本(元/公里) 
        v_km = formula_config.get('variable_cost_per_km', 15.0)
        
        # Q_kg: 实际装载质量(kg)
        vehicle_payload_kg = formula_config.get('vehicle_payload_kg', 25000)
        utilization_rate = formula_config.get('utilization_rate', 0.8)
        Q_kg = vehicle_payload_kg * utilization_rate
        
        # 应用运输成本公式: c_kg(S) = F_trip/Q_kg + v_km/Q_kg * S
        fixed_cost_per_kg = F_trip / Q_kg  # 固定成本分摊到每kg
        variable_cost_per_kg_km = v_km / Q_kg  # 变动成本分摊到每kg每km
        
        total_cost_per_kg = fixed_cost_per_kg + variable_cost_per_kg_km * distance_km
        
        return total_cost_per_kg
    
    
    def _calculate_total_storage_cost_per_kg_hour(self) -> float:
        """计算总储存成本（基于实际储存的直接成本）"""
        # 储存的直接成本（不包含设备折旧），来自配置
        obj_cfg = self.config.get('objective_coefficients', {}) or {}
        direct_cfg = (obj_cfg.get('storage', {}) or {}).get('direct_costs', {})
        warehouse_rent_per_m3_hour = float(direct_cfg.get('warehouse_rent_per_m3_hour', 0.01))
        storage_density_kg_per_m3 = float(direct_cfg.get('storage_density_kg_per_m3', 500))
        handling_cost_per_kg_hour = float(direct_cfg.get('handling_cost_per_kg_hour', 0.001))

        storage_space_cost = warehouse_rent_per_m3_hour / max(storage_density_kg_per_m3, 1e-6)
        total_storage_cost = storage_space_cost + handling_cost_per_kg_hour
        return total_storage_cost
    

    def _calculate_hydrogen_transport_cost_by_distance(self, distance_km: float) -> float:
        """基于实际数据点的氢气运输成本线性插值
        
        数据点: (50,5.43), (100,8.66), (150,9.85), (200,11.03), (250,12.21), 
               (300,15.45), (350,16.63), (400,17.82), (450,19.00), (500,20.18)
        
        Args:
            distance_km: 运输距离 (km)
            
        Returns:
            float: 运输成本 (元/kg)
        """
        # 实际数据点 - 距离为0时成本为0
        data_points = [
            (0, 0),        # 距离为0时成本为0
            (50, 5.43),
            (100, 8.66),
            (150, 9.85),
            (200, 11.03),
            (250, 12.21),
            (300, 15.45),
            (350, 16.63),
            (400, 17.82),
            (450, 19.00),
            (500, 20.18)
        ]
        
        # 如果距离为0或负数，直接返回0
        if distance_km <= 0:
            return 0.0
            
        # 如果超出最大距离，使用最后两点的斜率外推
        if distance_km > 500:
            # 使用450-500km的斜率外推
            slope = (20.18 - 19.00) / (500 - 450)
            return 20.18 + slope * (distance_km - 500)
        
        # 线性插值
        for i in range(len(data_points) - 1):
            x1, y1 = data_points[i]
            x2, y2 = data_points[i + 1]
            
            if x1 <= distance_km <= x2:
                # 线性插值公式: y = y1 + (y2-y1) * (x-x1) / (x2-x1)
                if x2 == x1:  # 避免除零
                    return y1
                transport_cost = y1 + (y2 - y1) * (distance_km - x1) / (x2 - x1)
                return max(0, transport_cost)
        
        # 兜底返回最后一个点的成本
        return data_points[-1][1]
    
    def _calculate_hydrogen_pipeline_cost_by_distance(self, distance_km: float) -> float:
        """基于图像数据的氢能管道运输成本函数
        
        使用分段线性插值计算单位成本，然后转换为总运输成本
        原始数据单位：元/(kg·百公里)，需要乘以实际距离转换为元/kg
        
        数据来源：管道输送氢气成本曲线（图表33）
        原始数据点：(25km,1.91元/(kg·百公里)), (50km,1.04), (100km,0.56), 
                   (200km,0.30), (300km,0.21), (400km,0.16), (500km,0.13)
        
        Args:
            distance_km: 管道运输距离 (km)
            
        Returns:
            float: 氢能管道运输总成本 (元/kg氢气) = 单位成本 × (距离÷100)
        """
        if distance_km <= 0:
            return 0.0
            
        # 从配置文件读取数据点，如果不存在则使用默认数据点
        cost_config = self.config.get('costs', {}).get('hydrogen_pipeline_costs', {}).get('transport_cost_function', {})
        data_points = cost_config.get('data_points', [
            [25, 1.91],   # 25km距离下的单位成本: 1.91元/(kg·百公里)
            [50, 1.04],   # 50km距离下的单位成本: 1.04元/(kg·百公里)
            [100, 0.56],  # 100km距离下的单位成本: 0.56元/(kg·百公里)
            [200, 0.30],  # 200km距离下的单位成本: 0.30元/(kg·百公里)
            [300, 0.21],  # 300km距离下的单位成本: 0.21元/(kg·百公里)
            [400, 0.16],  # 400km距离下的单位成本: 0.16元/(kg·百公里)
            [500, 0.13]   # 500km距离下的单位成本: 0.13元/(kg·百公里)
        ])
        
        # 分段线性插值获取单位成本 [元/(kg·百公里)]
        unit_cost_per_100km = 0.0
        
        for i in range(len(data_points) - 1):
            x1, y1 = data_points[i]
            x2, y2 = data_points[i + 1]
            
            if x1 <= distance_km <= x2:
                # 线性插值公式: y = y1 + (y2-y1) * (x-x1) / (x2-x1)
                if x2 == x1:  # 避免除零
                    unit_cost_per_100km = y1
                else:
                    unit_cost_per_100km = y1 + (y2 - y1) * (distance_km - x1) / (x2 - x1)
                break
        else:
            # 超出范围的处理
            if distance_km < data_points[0][0]:
                # 距离小于最小值，使用最小值的单位成本
                unit_cost_per_100km = data_points[0][1]
            else:
                # 距离大于最大值，使用最大值的单位成本
                unit_cost_per_100km = data_points[-1][1]
        
        # 单位转换：元/(kg·百公里) × (距离km ÷ 100) = 元/kg
        total_transport_cost = unit_cost_per_100km * (distance_km / 100.0)
        
        return max(0, total_transport_cost)
    
    def _estimate_location_mtj_capacity(self, location: str) -> float:
        """估算MTJ生产位置的日产能规模
        
        Args:
            location: MTJ生产位置
            
        Returns:
            float: 估算日产能 (kg/d)
        """
        # 从配置读取MTJ产能估算参数
        capacity_estimates = self.config.get('capacity_limits', {}).get('mtj_capacity_estimates', {})
        
        if location in self.locations:
            location_data = self.locations[location]
            location_type = location_data.get('type', 'industrial')
            
            # 根据位置类型估算生产规模，从配置读取
            if location_type == 'petrochemical':
                return capacity_estimates.get('petrochemical_base', 5000)  # 大型石化基地
            elif location_type == 'industrial':
                return capacity_estimates.get('industrial', 2000)  # 工业园区
            elif location_type == 'renewable_energy':
                return capacity_estimates.get('renewable_energy', 1000)  # 可再生能源基地
            else:
                return capacity_estimates.get('default', 1500)  # 其他类型
        
        return capacity_estimates.get('default', 1500)  # 默认值

    def _calculate_dynamic_renewable_intensity(self, location, hour):
        """
        基于实际发电数据动态计算可再生能源碳强度

        根据指定位置和时刻的风电/光伏发电量，按比例计算碳强度。
        当数据不可用时，使用50%-50%平均值作为fallback。

        Args:
            location: 位置标识
            hour: 小时索引

        Returns:
            float: 动态碳强度 (kg CO2eq/kWh)
        """
        renewable_energy = self.carbon_params.get('renewable_energy', {})
        wind_ci = renewable_energy.get('wind_power_intensity', 0.015)  # kg CO2eq/kWh
        solar_ci = renewable_energy.get('solar_power_intensity', 0.045)  # kg CO2eq/kWh

        # 尝试使用实际发电数据
        if hasattr(self, 'renewable_generation_data') and self.renewable_generation_data:
            gen_data = self.renewable_generation_data.get((location, hour), {})
            wind_gen = gen_data.get('wind_mwh', 0)
            solar_gen = gen_data.get('solar_mwh', 0)
            total_gen = wind_gen + solar_gen

            if total_gen > 0:
                wind_ratio = wind_gen / total_gen
                solar_ratio = solar_gen / total_gen
                dynamic_ci = wind_ratio * wind_ci + solar_ratio * solar_ci
                return dynamic_ci

        # Fallback: 使用50%-50%平均值
        fallback_ci = (wind_ci + solar_ci) / 2  # 0.03 kg CO2eq/kWh
        return fallback_ci

    def _calculate_distance(self, location: str, airport: str) -> float:
        """使用OSM路径规划计算两点间真实道路距离"""
        # 创建缓存键
        cache_key = f"{location}_{airport}"
        if cache_key in self.distance_cache:
            return self.distance_cache[cache_key]
        
        loc_lat = self.locations[location]['latitude']
        loc_lon = self.locations[location]['longitude']
        air_lat = self.airports[airport]['latitude']
        air_lon = self.airports[airport]['longitude']
        
        # 使用GraphHopper路径规划计算真实距离
        result = self.routing_engine.calculate_route_distance(
            loc_lat, loc_lon, air_lat, air_lon, vehicle="truck", include_route_geometry=False
        )
        distance_km = result.get('distance_km', 0)
        
        # 如果百度地图API失败，使用备选方案
        if not result.get('route_found', False):
            # 使用直线距离乘以系数作为备选方案
            distance_km = self.distance_calculator.calculate_haversine_distance(
                loc_lat, loc_lon, air_lat, air_lon
            ) * 1.3
        
        # 缓存结果
        self.distance_cache[cache_key] = distance_km
        
        return max(distance_km, 5)  # 最小距离5km（避免除零）
    
    def _calculate_distance_with_route(self, location: str, airport: str) -> tuple:
        """使用OSM路径规划计算两点间真实道路距离并返回路径坐标"""
        # 创建缓存键
        route_cache_key = f"route_{location}_{airport}"
        if hasattr(self, 'route_cache') and route_cache_key in self.route_cache:
            cached_result = self.route_cache[route_cache_key]
            return cached_result['distance_km'], cached_result['route_coordinates']
        
        loc_lat = self.locations[location]['latitude']
        loc_lon = self.locations[location]['longitude']
        air_lat = self.airports[airport]['latitude']
        air_lon = self.airports[airport]['longitude']
        
        # 使用GraphHopper路径规划计算真实距离并获取路径
        result = self.routing_engine.calculate_route_distance(
            loc_lat, loc_lon, air_lat, air_lon, vehicle="truck", include_route_geometry=True
        )
        distance_km = result.get('distance_km', 0)
        route_coordinates = result.get('route_coordinates', [])
        
        # 验证路径规划结果
        if not result.get('route_found', False):
            error_msg = f"路径规划失败: {location} -> {airport}, GraphHopper未找到路径"
            logger.error(error_msg)
            logger.error(f"错误详情: {result.get('error', '未知错误')}")
            logger.error(f"完整GraphHopper响应: {result}")
            logger.error(f"起点坐标: ({loc_lat}, {loc_lon})")
            logger.error(f"终点坐标: ({air_lat}, {air_lon})")
            raise Exception(error_msg)

        if not route_coordinates:
            error_msg = f"路径坐标解析失败: {location} -> {airport}, GraphHopper返回结果: route_found={result.get('route_found')}, route_coordinates数量=0, 错误信息: {result.get('error', '未知错误')}"
            logger.error(error_msg)
            logger.error(f"GraphHopper详细响应: route_found={result.get('route_found')}, distance_km={distance_km}, time_hours={result.get('time_hours', 'N/A')}")
            logger.error(f"起点坐标: ({loc_lat}, {loc_lon})")
            logger.error(f"终点坐标: ({air_lat}, {air_lon})")
            logger.error(f"完整GraphHopper结果: {result}")
            raise Exception(error_msg)
        
        # 缓存路径结果
        if not hasattr(self, 'route_cache'):
            self.route_cache = {}
        
        self.route_cache[route_cache_key] = {
            'distance_km': distance_km,
            'route_coordinates': route_coordinates
        }
        
        return max(distance_km, 5), route_coordinates
    
    def _calculate_location_distance(self, location1: str, location2: str) -> float:
        """使用GraphHopper路径规划计算两个位置间的真实道路距离

        支持从以下数据源查找位置：
        1. self.locations（机场、可再生能源工厂等）
        2. self.co2_capture_sources（CO₂捕获源）
        """
        # 创建缓存键
        cache_key = f"{location1}_{location2}"
        if cache_key in self.distance_cache:
            return self.distance_cache[cache_key]

        # 反向缓存键（距离是对称的）
        reverse_cache_key = f"{location2}_{location1}"
        if reverse_cache_key in self.distance_cache:
            return self.distance_cache[reverse_cache_key]

        # 辅助函数：从多个数据源查找位置坐标
        def get_location_coords(loc_name):
            """从locations或co2_capture_sources中获取位置坐标"""
            if loc_name in self.locations:
                return self.locations[loc_name]['latitude'], self.locations[loc_name]['longitude']
            elif loc_name in self.co2_capture_sources:
                return self.co2_capture_sources[loc_name]['latitude'], self.co2_capture_sources[loc_name]['longitude']
            else:
                raise KeyError(f"位置 '{loc_name}' 既不在 locations 也不在 co2_capture_sources 中")

        # 获取两个位置的坐标
        loc1_lat, loc1_lon = get_location_coords(location1)
        loc2_lat, loc2_lon = get_location_coords(location2)
        
        # 使用GraphHopper路径规划计算真实距离
        result = self.routing_engine.calculate_route_distance(
            loc1_lat, loc1_lon, loc2_lat, loc2_lon, vehicle="truck", include_route_geometry=False
        )
        distance_km = result.get('distance_km', 0)
        
        # 如果路径规划失败，直接抛出异常
        if not result.get('route_found', False):
            raise Exception(f"距离计算失败: {location1} -> {location2}, "
                          f"GraphHopper返回结果: route_found={result.get('route_found')}, "
                          f"错误信息: {result.get('error', '未知错误')}")
        
        # 缓存结果（双向）
        self.distance_cache[cache_key] = distance_km
        self.distance_cache[reverse_cache_key] = distance_km
        
        return max(distance_km, 5)  # 最小距离5km（避免除零）

    def _get_hydrogen_transport_distance_with_clustering(self, h2_loc: str, mtj_loc: str) -> float:
        """
        使用聚类和管道路权算法计算氢气管道运输距离

        Args:
            h2_loc: 氢气生产位置
            mtj_loc: 甲醇生产位置

        Returns:
            氢气管道运输距离(公里)

        Raises:
            RuntimeError: 如果聚类结果未初始化
        """
        if not hasattr(self, 'clustering_results') or self.clustering_results is None:
            raise RuntimeError(
                f"聚类结果未初始化，无法计算氢气管道距离。\n"
                f"起点: {h2_loc}, 终点: {mtj_loc}\n"
                f"请检查配置文件中的 'use_hydrogen_pipeline_distance' 参数是否启用。\n"
                f"该参数路径: basic_parameters.use_hydrogen_pipeline_distance"
            )

        # 🚀🚀 优先使用超图优化器（如果可用）
        if hasattr(self, 'super_graph_optimizer') and self.super_graph_optimizer is not None:
            try:
                distance_result = self.super_graph_optimizer.get_distance(h2_loc, mtj_loc)
                if distance_result:
                    # 超图查询成功，直接返回
                    return distance_result['total_distance_km']
                else:
                    # 超图查询失败（路径不可达），降级到直线距离
                    logger.warning(f"超图查询路径不可达，使用直线距离: {h2_loc} -> {mtj_loc}")
                    return self._calculate_location_distance(h2_loc, mtj_loc)
            except Exception as e:
                # 超图查询出错，检查是否允许回退
                fallback_on_failure = self.config.get('super_graph_config', {}).get('fallback_on_failure', True)
                if fallback_on_failure:
                    logger.warning(f"超图查询失败，回退到传统方法: {h2_loc} -> {mtj_loc}, 错误: {e}")
                    # 继续执行传统方法（下面的代码）
                else:
                    # 不允许回退，直接抛出异常
                    raise RuntimeError(
                        f"超图查询失败且不允许回退。\n"
                        f"起点: {h2_loc}, 终点: {mtj_loc}\n"
                        f"错误: {str(e)}\n"
                        f"解决方法：设置 super_graph_config.fallback_on_failure: true"
                    )

        # 传统方法：聚类路径计算
        for cluster in self.clustering_results.clusters:
            if h2_loc in cluster.member_locations:
                route_key = (cluster.cluster_id, mtj_loc)
                if route_key in self.clustered_routes:
                    route = self.clustered_routes[route_key]
                    member_total_distance = route.total_distance_per_member.get(h2_loc, 0)
                    return max(member_total_distance, 5)
                else:
                    cluster_members = list(zip(cluster.member_locations, cluster.member_coords))
                    mtj_coords = (self.locations[mtj_loc]['latitude'], self.locations[mtj_loc]['longitude'])
                    try:
                        route = self.hydrogen_pipeline_calculator.calculate_clustered_pipeline_route(
                            cluster.cluster_id,
                            cluster_members,
                            cluster.center_coord,
                            mtj_coords
                        )
                        self.clustered_routes[route_key] = route
                        member_total_distance = route.total_distance_per_member.get(h2_loc, 0)
                        return max(member_total_distance, 5)
                    except PipelineRouteNotFoundError as e:
                        # 聚类到目的地找不到管道路径，使用直线距离作为降级方案
                        logger.warning(f"管道路径未找到（聚类），使用直线距离: 聚类{cluster.cluster_id}成员{h2_loc} -> {mtj_loc}, 原因: {str(e)}")
                        self.skipped_routes['hydrogen_pipeline'].append({
                            'from': h2_loc,
                            'from_cluster_id': cluster.cluster_id,
                            'to': mtj_loc,
                            'to_coords': mtj_coords,
                            'reason': str(e),
                            'type': 'cluster_route'
                        })
                        return self._calculate_location_distance(h2_loc, mtj_loc)  # 使用直线距离
                    except Exception as e:
                        # 其他未预期的错误仍然抛出
                        raise RuntimeError(
                            f"氢气管道距离计算失败（聚类路径，非路径查找错误）。\n"
                            f"聚类ID: {cluster.cluster_id}, 成员: {h2_loc}\n"
                            f"终点: {mtj_loc} ({mtj_coords[0]:.6f}, {mtj_coords[1]:.6f})\n"
                            f"错误: {str(e)}"
                        )

        for noise_loc, noise_coord in self.clustering_results.noise_points:
            if h2_loc == noise_loc:
                mtj_coords = (self.locations[mtj_loc]['latitude'], self.locations[mtj_loc]['longitude'])
                try:
                    route = self.hydrogen_pipeline_calculator.calculate_pipeline_distance(
                        noise_coord[0], noise_coord[1],
                        mtj_coords[0], mtj_coords[1]
                    )
                    return max(route.total_distance_km, 5)
                except PipelineRouteNotFoundError as e:
                    # 找不到管道路径，使用直线距离作为降级方案
                    logger.warning(f"管道路径未找到（噪声点），使用直线距离: {h2_loc} -> {mtj_loc}, 原因: {str(e)}")
                    self.skipped_routes['hydrogen_pipeline'].append({
                        'from': h2_loc,
                        'from_coords': (noise_coord[0], noise_coord[1]),
                        'to': mtj_loc,
                        'to_coords': mtj_coords,
                        'reason': str(e),
                        'type': 'noise_point'
                    })
                    return self._calculate_location_distance(h2_loc, mtj_loc)  # 使用直线距离
                except Exception as e:
                    # 其他未预期的错误仍然抛出
                    raise RuntimeError(
                        f"氢气管道距离计算失败（噪声点，非路径查找错误）。\n"
                        f"起点: {h2_loc} (噪声点坐标: {noise_coord[0]:.6f}, {noise_coord[1]:.6f})\n"
                        f"终点: {mtj_loc} ({mtj_coords[0]:.6f}, {mtj_coords[1]:.6f})\n"
                        f"错误: {str(e)}"
                    )

        # 如果在聚类和噪声点中都找不到该位置，抛出错误
        raise RuntimeError(
            f"无法找到氢气生产位置在聚类结果中。\n"
            f"位置: {h2_loc}\n"
            f"终点: {mtj_loc}\n"
            f"聚类数量: {len(self.clustering_results.clusters)}\n"
            f"噪声点数量: {len(self.clustering_results.noise_points)}\n"
            f"请检查聚类配置或位置数据的一致性。"
        )

    def _get_co2_transport_distance_with_clustering(self, co2_source_id: str, mtj_loc: str) -> dict:
        """
        使用CO2聚类和管道路权算法计算CO₂管道运输距离（v3.0: 已禁用）

        v3.0煤炭气化路线不需要CO₂运输，此方法保留供参考。
        """
        raise NotImplementedError("v3.0煤炭气化路线不需要CO₂运输距离计算")

        # 以下代码在v3.0中不再使用（保留供参考）
        """
        三层运输结构：
        - Layer 1: CO2捕获源 -> 聚类中心（直线距离）
        - Layer 2: 聚类中心 -> 管道接入点（管道距离）
        - Layer 3: 管道网络 -> 甲醇生产位置（管道距离）

        Args:
            co2_source_id: CO₂捕获源ID
            mtj_loc: 甲醇生产位置

        Returns:
            dict: {
                'total_distance_km': float,
                'layer1_distance_km': float,  # CO2源 -> 聚类中心
                'layer2_distance_km': float,  # 聚类中心 -> 管道接入点
                'layer3_distance_km': float,  # 管道网络 -> 目的地
                'cluster_id': int or None,    # 聚类ID（-1表示独立点）
                'cluster_center_coords': tuple or None,
                'pipeline_access_coords': tuple or None,
                'is_noise': bool,
                'route_coordinates': list  # 完整路径坐标
            }

        Raises:
            RuntimeError: 如果CO2聚类结果未初始化
        """
        # 检查CO2聚类结果是否初始化
        if not hasattr(self, 'co2_clustering_results') or self.co2_clustering_results is None:
            raise RuntimeError(
                f"CO2聚类结果未初始化，无法计算CO₂管道距离。\n"
                f"起点: {co2_source_id}, 终点: {mtj_loc}\n"
                f"请检查配置文件中的 'use_co2_pipeline_distance' 参数是否启用。\n"
                f"该参数路径: basic_parameters.use_co2_pipeline_distance"
            )

        # 验证CO₂捕获源和目的地
        if co2_source_id not in self.co2_capture_sources:
            raise ValueError(f"无效的CO₂捕获源ID: {co2_source_id}")
        if mtj_loc not in self.locations:
            raise ValueError(f"无效的甲醇生产位置: {mtj_loc}")

        # 获取坐标
        co2_source = self.co2_capture_sources[co2_source_id]
        co2_coords = (co2_source['latitude'], co2_source['longitude'])
        mtj_coords = (self.locations[mtj_loc]['latitude'], self.locations[mtj_loc]['longitude'])

        # 查找CO2源所属的聚类
        cluster_id = None
        cluster_center_coords = None
        is_noise = False

        # 检查是否在聚类中
        for cluster in self.co2_clustering_results.clusters:
            if co2_source_id in cluster.member_locations:
                cluster_id = cluster.cluster_id
                cluster_center_coords = cluster.center_coord
                break

        # 如果不在聚类中，说明是独立点（noise）
        if cluster_id is None:
            is_noise = True
            for noise_loc, noise_coords in self.co2_clustering_results.noise_points:
                if noise_loc == co2_source_id:
                    break

        # 计算三层距离
        if is_noise:
            # 独立点：直接计算管道距离（不经过聚类中心）
            try:
                route = self.hydrogen_pipeline_calculator.calculate_pipeline_distance(
                    co2_coords[0], co2_coords[1],
                    mtj_coords[0], mtj_coords[1]
                )
                return {
                    'total_distance_km': max(route.total_distance_km, 5),
                    'layer1_distance_km': 0,
                    'layer2_distance_km': 0,
                    'layer3_distance_km': max(route.total_distance_km, 5),
                    'cluster_id': -1,
                    'cluster_center_coords': None,
                    'pipeline_access_coords': route.access_point_coords if hasattr(route, 'access_point_coords') else None,
                    'is_noise': True,
                    'route_coordinates': route.route_geometry if (hasattr(route, 'route_geometry') and route.route_geometry) else [co2_coords, mtj_coords]
                }
            except PipelineRouteNotFoundError as e:
                # 管道路径未找到，使用直线距离
                logger.warning(f"CO2独立点管道路径未找到，使用直线距离: {co2_source_id} -> {mtj_loc}")
                distance = self._calculate_haversine_distance(
                    co2_coords[0], co2_coords[1],
                    mtj_coords[0], mtj_coords[1]
                )
                return {
                    'total_distance_km': max(distance, 5),
                    'layer1_distance_km': 0,
                    'layer2_distance_km': 0,
                    'layer3_distance_km': max(distance, 5),
                    'cluster_id': -1,
                    'cluster_center_coords': None,
                    'pipeline_access_coords': None,
                    'is_noise': True,
                    'route_coordinates': [co2_coords, mtj_coords]  # 修复：使用直线路径坐标
                }
        else:
            # 聚类成员：使用三层运输结构
            # Layer 1: CO2源 -> 聚类中心（直线距离）
            layer1_distance = self._calculate_haversine_distance(
                co2_coords[0], co2_coords[1],
                cluster_center_coords[0], cluster_center_coords[1]
            )

            # Layer 2+3: 聚类中心 -> 管道网络 -> 目的地（管道距离）
            try:
                route = self.hydrogen_pipeline_calculator.calculate_pipeline_distance(
                    cluster_center_coords[0], cluster_center_coords[1],
                    mtj_coords[0], mtj_coords[1]
                )

                # Layer 2: 聚类中心 -> 管道接入点
                # Layer 3: 管道网络 -> 目的地
                # 这里简化处理：将管道距离拆分为Layer2和Layer3
                pipeline_access_coords = route.pipeline_access_point if hasattr(route, 'pipeline_access_point') else cluster_center_coords

                # 计算Layer2和Layer3距离
                if hasattr(route, 'access_distance_km') and hasattr(route, 'pipeline_distance_km'):
                    layer2_distance = route.access_distance_km
                    layer3_distance = route.pipeline_distance_km
                else:
                    # 如果路径对象没有细分距离，按50-50拆分
                    layer2_distance = route.total_distance_km * 0.3
                    layer3_distance = route.total_distance_km * 0.7

                return {
                    'total_distance_km': max(layer1_distance + route.total_distance_km, 5),
                    'layer1_distance_km': layer1_distance,
                    'layer2_distance_km': layer2_distance,
                    'layer3_distance_km': layer3_distance,
                    'cluster_id': cluster_id,
                    'cluster_center_coords': cluster_center_coords,
                    'pipeline_access_coords': pipeline_access_coords,
                    'is_noise': False,
                    'route_coordinates': route.route_geometry if (hasattr(route, 'route_geometry') and route.route_geometry) else [co2_coords, cluster_center_coords, mtj_coords]
                }
            except PipelineRouteNotFoundError as e:
                # 管道路径未找到，使用直线距离
                logger.warning(f"CO2聚类路径管道未找到，使用直线距离: cluster_{cluster_id} -> {mtj_loc}")
                layer2_layer3_distance = self._calculate_haversine_distance(
                    cluster_center_coords[0], cluster_center_coords[1],
                    mtj_coords[0], mtj_coords[1]
                )
                return {
                    'total_distance_km': max(layer1_distance + layer2_layer3_distance, 5),
                    'layer1_distance_km': layer1_distance,
                    'layer2_distance_km': layer2_layer3_distance * 0.3,
                    'layer3_distance_km': layer2_layer3_distance * 0.7,
                    'cluster_id': cluster_id,
                    'cluster_center_coords': cluster_center_coords,
                    'pipeline_access_coords': None,
                    'is_noise': False,
                    'route_coordinates': [co2_coords, cluster_center_coords, mtj_coords]  # 修复：三层路径坐标
                }

    def _calculate_location_distance_with_route(self, location1: str, location2: str) -> tuple:
        """使用GraphHopper路径规划计算两个位置间的真实道路距离并返回路径坐标"""
        # 创建缓存键
        route_cache_key = f"route_{location1}_{location2}"
        reverse_route_cache_key = f"route_{location2}_{location1}"
        
        if not hasattr(self, 'route_cache'):
            self.route_cache = {}
        
        if route_cache_key in self.route_cache:
            cached_result = self.route_cache[route_cache_key]
            return cached_result['distance_km'], cached_result['route_coordinates']
        elif reverse_route_cache_key in self.route_cache:
            cached_result = self.route_cache[reverse_route_cache_key]
            # 反向路径坐标
            reversed_coords = cached_result['route_coordinates'][::-1] if cached_result['route_coordinates'] else []
            return cached_result['distance_km'], reversed_coords
        
        loc1_lat = self.locations[location1]['latitude']
        loc1_lon = self.locations[location1]['longitude']
        loc2_lat = self.locations[location2]['latitude']
        loc2_lon = self.locations[location2]['longitude']
        
        # 使用GraphHopper路径规划计算真实距离并获取路径
        result = self.routing_engine.calculate_route_distance(
            loc1_lat, loc1_lon, loc2_lat, loc2_lon, vehicle="truck", include_route_geometry=True
        )
        distance_km = result.get('distance_km', 0)
        route_coordinates = result.get('route_coordinates', [])
        
        # 如果路径规划失败，直接抛出异常
        if not result.get('route_found', False) or not route_coordinates:
            raise Exception(f"路径规划失败: {location1} -> {location2}, "
                          f"GraphHopper返回结果: route_found={result.get('route_found')}, "
                          f"route_coordinates数量={len(route_coordinates) if route_coordinates else 0}, "
                          f"错误信息: {result.get('error', '未知错误')}")
        
        # 缓存路径结果（双向）
        self.route_cache[route_cache_key] = {
            'distance_km': distance_km,
            'route_coordinates': route_coordinates
        }
        self.route_cache[reverse_route_cache_key] = {
            'distance_km': distance_km,
            'route_coordinates': route_coordinates[::-1] if route_coordinates else []
        }
        
        return max(distance_km, 5), route_coordinates
    
    def solve(self) -> Dict:
        """求解优化模型"""
        logger.info("开始求解优化模型...")

        if self.model is None:
            raise ValueError("模型尚未构建，请先调用build_model()")

        # 求解
        self.model.optimize()

        # 定义状态码含义映射
        status_names = {
            1: "LOADED", 2: "OPTIMAL", 3: "INFEASIBLE", 4: "INF_OR_UNBD",
            5: "UNBOUNDED", 6: "CUTOFF", 7: "ITERATION_LIMIT", 8: "NODE_LIMIT",
            9: "TIME_LIMIT", 10: "SOLUTION_LIMIT", 11: "INTERRUPTED", 12: "NUMERIC",
            13: "SUBOPTIMAL", 14: "INPROGRESS", 15: "USER_OBJ_LIMIT",
            16: "WORK_LIMIT", 17: "MEM_LIMIT"
        }
        status_name = status_names.get(self.model.status, f"UNKNOWN({self.model.status})")

        # 检查是否有可行解（无论状态如何，只要SolCount > 0就有解）
        has_solution = self.model.SolCount > 0

        logger.info(f"求解状态: {status_name} (代码: {self.model.status})")
        logger.info(f"找到的解数量: {self.model.SolCount}")

        # 检查求解状态
        if self.model.status == GRB.OPTIMAL:
            logger.info("找到最优解")
            self._check_production_after_solve()
            self._log_variable_summary_post_solve()
            return self._extract_solution()

        elif self.model.status == GRB.INFEASIBLE:
            logger.error("模型不可行")
            # 计算IIS（不可行不可约子系统）来找出冲突约束
            logger.info("正在计算不可行不可约子系统(IIS)...")
            self.model.computeIIS()

            # 输出IIS信息
            iis_file = "infeasible_model.ilp"
            self.model.write(iis_file)
            logger.info(f"不可行模型已保存为: {iis_file}")

            # 统计冲突约束
            iis_constrs = []
            for constr in self.model.getConstrs():
                if constr.IISConstr:
                    iis_constrs.append(constr.ConstrName)

            logger.error(f"发现 {len(iis_constrs)} 个冲突约束:")
            for i, constr_name in enumerate(iis_constrs[:10]):  # 只打印前10个
                logger.error(f"  {i+1}. {constr_name}")
            if len(iis_constrs) > 10:
                logger.error(f"  ... 还有 {len(iis_constrs)-10} 个约束")

            return {"status": "infeasible", "status_code": self.model.status, "iis_constraints": iis_constrs}

        elif self.model.status == GRB.TIME_LIMIT and has_solution:
            # 只处理TIME_LIMIT，MEM_LIMIT的解质量较差暂不处理
            logger.warning(f"求解因 {status_name} 提前终止，但找到了可行解")

            # 输出MIP Gap信息（如果可用）
            try:
                mip_gap = self.model.MIPGap
                logger.info(f"当前MIP Gap: {mip_gap*100:.4f}%")
                if mip_gap < 0.05:  # Gap < 5%
                    logger.info("MIP Gap较小，解的质量很好")
                elif mip_gap < 0.10:  # Gap < 10%
                    logger.warning("MIP Gap中等，解的质量可接受")
                else:
                    logger.warning("MIP Gap较大，解可能还有优化空间")
            except:
                pass

            self._check_production_after_solve()
            self._log_variable_summary_post_solve()
            return self._extract_solution()

        else:
            # 没有可行解
            logger.error(f"求解失败，状态: {status_name}，未找到可行解")
            return {"status": "failed", "status_code": self.model.status, "status_name": status_name}

    def _check_production_after_solve(self):
        """求解后检查产量是否正常"""
        try:
            if hasattr(self, 'performance_expressions') and 'production_total' in self.performance_expressions:
                production_total_value = self.performance_expressions['production_total'].getValue()
                logger.info(f"[产量检查] 总产量: {production_total_value:,.2f} kg")

                if production_total_value < 0.01:
                    logger.warning("="*80)
                    logger.warning("⚠️  检测到零产量问题！")
                    logger.warning("可能原因:")
                    logger.warning("  1. MTJ位置的氢气库存平衡缺失（已修复）")
                    logger.warning("  2. 运输成本过高（检查距离计算是否返回1e9）")
                    logger.warning("  3. shortage成本设置过低")
                    logger.warning("="*80)
            else:
                logger.warning("[产量检查] 未找到production_total表达式")
        except Exception as e:
            logger.error(f"[产量检查] 检测失败: {e}")
    
    def _log_variable_summary_post_solve(self) -> None:
        """求解后输出关键变量的汇总信息，辅助诊断产量为0问题"""
        try:
            def sum_var_dict(var_dict):
                return sum(var.x for var in var_dict.values()) if var_dict else 0.0

            def aggregate_by_index(var_dict, index):
                agg = defaultdict(float)
                for key, var in var_dict.items():
                    value = getattr(var, "x", 0.0)
                    if value > 1e-6 and isinstance(key, tuple) and len(key) > index:
                        agg[key[index]] += value
                return agg

            def log_top_entries(title, agg_dict, unit, top_n=5):
                if not agg_dict:
                    logger.debug(f"[调试] {title}: 无数据")
                    return
                sorted_items = sorted(agg_dict.items(), key=lambda kv: kv[1], reverse=True)
                logger.info(f"[调试] {title} Top{min(top_n, len(sorted_items))}:")
                for name, value in sorted_items[:top_n]:
                    logger.info(f"    {name}: {value:,.2f} {unit}")

            total_h2_production = sum_var_dict(getattr(self, 'hydrogen_production_vars', {}))
            total_h2_pipeline = sum_var_dict(getattr(self, 'hydrogen_pipeline_transport_vars', {}))
            total_methanol = sum_var_dict(getattr(self, 'methanol_production_vars', {}))  # v3.1一步法: 应为0
            total_saf = sum_var_dict(getattr(self, 'production_vars', {}))
            total_coal_purchase = sum_var_dict(getattr(self, 'coal_purchase_vars', {}))  # v3.0: 煤炭采购
            total_shortage = sum_var_dict(getattr(self, 'shortage_vars', {}))

            logger.info("[调试] 求解后关键变量汇总：")
            logger.info(f"    氢气总产量: {total_h2_production:,.2f} kg")
            logger.info(f"    氢气管道运输总量: {total_h2_pipeline:,.2f} kg")
            logger.info(f"    甲醇总产量: {total_methanol:,.2f} kg (v3.1一步法: 应为0)")
            logger.info(f"    SAF 总产量: {total_saf:,.2f} kg")
            logger.info(f"    煤炭采购总量: {total_coal_purchase:,.2f} kg (v3.0)")  # v3.0: 替换CO₂运输
            logger.info(f"    缺货总量: {total_shortage:,.2f} kg")

            h2_prod_by_location = aggregate_by_index(getattr(self, 'hydrogen_production_vars', {}), 0)
            log_top_entries("氢气产量（按氢源位置）", h2_prod_by_location, "kg")

            # v3.1一步法: 甲醇产量应为0（无中间步骤）
            methanol_by_location = aggregate_by_index(getattr(self, 'methanol_production_vars', {}), 0)
            log_top_entries("甲醇产量（按位置）", methanol_by_location, "kg")

            saf_by_location = aggregate_by_index(getattr(self, 'production_vars', {}), 0)
            log_top_entries("SAF 产量（按位置）", saf_by_location, "kg")

            h2_pipeline_by_source = aggregate_by_index(getattr(self, 'hydrogen_pipeline_transport_vars', {}), 0)
            log_top_entries("氢气管道运输（按氢源）", h2_pipeline_by_source, "kg")

        except Exception as exc:
            logger.warning(f"[调试] 求解后变量汇总失败: {exc}")

    def _extract_solution(self) -> Dict:
        """从优化结果中提取解决方案"""
        solution = {}
        
        # 获取基本优化信息
        solution['optimization_status'] = self.model.status
        solution['optimization_time'] = self.model.Runtime
        solution['objective_value_lifecycle_total'] = self.model.ObjVal  # 20年生命周期总成本
        solution['project_lifespan_years'] = self.economic_params['project_lifespan']
        solution['time_window_weeks'] = self.time_horizon_weeks
        
        # 从表达式对象获取所有成本指标和数据
        cost_metrics = self._get_cost_metrics_from_expressions()
        solution.update(cost_metrics)

        # 保持与原有接口的兼容性
        solution['cost_breakdown'] = cost_metrics  # cost_breakdown就是完整的成本指标
        
        # 所有成本和产量指标已在cost_metrics中计算完成
        
        # 提取设施决策
        solution['facilities'] = {}
        for (location, tech), var in self.facility_vars.items():
            if var.x > 0.5:  # 二进制变量大于0.5视为选中
                facility_info = {
                    'location': location,
                    'technology': tech,
                    'built': True,
                    'max_annual_capacity_kg': self.facility_capacity_vars[(location, tech)].x * 8760,  # 转换为年产能
                    'capacity_kg_per_hour': self.facility_capacity_vars[(location, tech)].x,
                    'location_type': self.locations[location]['type'],
                    'transport_mode': self.technologies[tech]['transport_mode']
                }
        
                # 计算实际产量和利用率
                actual_production = sum(
                    self.production_vars[(location, tech, hour)].x
                    for hour in range(self.total_hours)
                    if (location, tech, hour) in self.production_vars
                )
                annual_production_facility = actual_production * (52.0 / self.time_horizon_weeks)
                
                facility_info['actual_annual_production_kg'] = annual_production_facility
                if facility_info['max_annual_capacity_kg'] > 0:
                    facility_info['utilization_rate'] = annual_production_facility / facility_info['max_annual_capacity_kg']
                else:
                    facility_info['utilization_rate'] = 0
                
                facility_key = f"{location}_{tech}"
                solution['facilities'][facility_key] = facility_info
        
        # 提取电解槽设施决策
        solution['hydrogen_facilities'] = {}
        for location, var in self.electrolyzer_facility_vars.items():
            if var.x > 0.5:  # 二进制变量大于0.5视为选中建设电解槽
                electrolyzer_capacity = self.electrolyzer_capacity_vars[location].x
                
                # 计算实际氢气产量和利用率
                actual_h2_production = sum(
                    self.hydrogen_production_vars[(location, hour)].x
                    for hour in range(self.total_hours)
                    if (location, hour) in self.hydrogen_production_vars
                )
                annual_h2_production = actual_h2_production * (52.0 / self.time_horizon_weeks)
                max_annual_h2_capacity = electrolyzer_capacity * 8760 * 0.75  # 考虑75%容量因子
                
                electrolyzer_info = {
                    'location': location,
                    'built': True,
                    'capacity_kg_h2_per_hour': electrolyzer_capacity,
                    'max_annual_h2_capacity_kg': max_annual_h2_capacity,
                    'actual_annual_h2_production_kg': annual_h2_production,
                    'utilization_rate': annual_h2_production / max_annual_h2_capacity if max_annual_h2_capacity > 0 else 0,
                    'location_type': self.locations[location]['type'],
                    'technology': 'electrolyzer'
                }
                
                electrolyzer_key = f"electrolyzer_{location}"
                solution['hydrogen_facilities'][location] = electrolyzer_info
                # 同时也添加到主设施列表中以便在设施决策文件中显示
                solution['facilities'][electrolyzer_key] = {
                    'location': location,
                    'technology': 'electrolyzer',
                    'built': True,
                    'capacity_kg_per_hour': electrolyzer_capacity,  # 氢气产能 kg H2/h
                    'max_annual_capacity_kg': max_annual_h2_capacity,  # 年氢气产能
                    'actual_annual_production_kg': annual_h2_production,  # 实际年氢气产量
                    'utilization_rate': electrolyzer_info['utilization_rate'],
                    'location_type': self.locations[location]['type'],
                    'transport_mode': 'hydrogen_pipeline'
                }
        
        # 提取运输计划
        solution['transport_plan'] = {}
        for (location, airport, week), var in self.transport_vars.items():
            if var.x > 0:
                transport_key = f"{location}_{airport}_{week}"
                from_coords = self._get_location_coordinates(location)
                to_coords = self._get_location_coordinates(airport)
                
                # 获取真实路径坐标
                distance_km, route_coordinates = self._calculate_distance_with_route(location, airport)
                
                solution['transport_plan'][transport_key] = {
                    'from_location': location,
                    'to_airport': airport,
                    'week': week,
                    'transport_kg': var.x,
                    'distance_km': distance_km,
                    'from_latitude': from_coords[0],
                    'from_longitude': from_coords[1],
                    'to_latitude': to_coords[0],
                    'to_longitude': to_coords[1],
                    'route_coordinates': route_coordinates,  # 新增：真实路径坐标
                    'transport_type': 'MTJ',
                    'transport_mode': 'truck'  # 默认卡车运输
                }

        # 提取氢气运输计划（【禁用罐车运输】仅处理管道运输）
        solution['hydrogen_transport'] = {}

        # 调试信息：统计氢气运输变量
        # truck_count = 0  # 【禁用罐车运输】
        # truck_positive = 0  # 【禁用罐车运输】
        pipeline_count = 0
        pipeline_positive = 0

        # 【禁用罐车运输】注释掉氢气罐车运输提取代码
        """
        # 1. 提取氢气罐车运输（周级变量）
        for (h_loc, mtj_loc), var in self.hydrogen_transport_vars.items():
            truck_count += 1
            if var.x > 0:
                truck_positive += 1
                transport_key = f"{h_loc}_{mtj_loc}_weekly_truck"
                from_coords = self._get_location_coordinates(h_loc)
                to_coords = self._get_location_coordinates(mtj_loc)

                # 获取真实路径坐标
                distance_km, route_coordinates = self._calculate_location_distance_with_route(h_loc, mtj_loc)

                solution['hydrogen_transport'][transport_key] = {
                    'from_location': h_loc,
                    'to_location': mtj_loc,
                    'transport_kg_h2': var.x,  # 周级运输量
                    'distance_km': distance_km,
                    'from_latitude': from_coords[0],
                    'from_longitude': from_coords[1],
                    'to_latitude': to_coords[0],
                    'to_longitude': to_coords[1],
                    'route_coordinates': route_coordinates,  # 新增：真实路径坐标
                    'transport_type': 'H2',
                    'transport_mode': 'truck'
                }
        """

        # 2. 提取氢能管道运输
        if hasattr(self, 'hydrogen_pipeline_transport_vars') and self.hydrogen_pipeline_transport_vars:
            for (h_loc, mtj_loc), var in self.hydrogen_pipeline_transport_vars.items():
                pipeline_count += 1
                if var.x > 0:
                    pipeline_positive += 1
                    transport_key = f"{h_loc}_{mtj_loc}_weekly_pipeline"
                    from_coords = self._get_location_coordinates(h_loc)
                    to_coords = self._get_location_coordinates(mtj_loc)

                    distance_km = self.hydrogen_distance_cache.get((h_loc, mtj_loc),
                                    self._get_hydrogen_transport_distance_with_clustering(h_loc, mtj_loc))

                    cluster_id = None
                    cluster_center = None
                    layer1_distance = 0
                    layer2_distance = 0
                    layer3_distance = 0
                    route_coordinates = []

                    if hasattr(self, 'clustering_results') and self.clustering_results:
                        for cluster in self.clustering_results.clusters:
                            if h_loc in cluster.member_locations:
                                cluster_id = cluster.cluster_id
                                cluster_center = cluster.center_coord
                                route_key = (cluster_id, mtj_loc)
                                if route_key in self.clustered_routes:
                                    route = self.clustered_routes[route_key]
                                    layer1_distance = route.layer1_distances.get(h_loc, 0)
                                    layer2_distance = route.layer2_distance
                                    layer3_distance = route.layer3_distance
                                    if route.route_geometry:
                                        route_coordinates = [[coord[1], coord[0]] for coord in route.route_geometry]
                                else:
                                    # 路径不在缓存中,重新计算聚类路径
                                    cluster_members = list(zip(cluster.member_locations, cluster.member_coords))
                                    mtj_coords = (self.locations[mtj_loc]['latitude'], self.locations[mtj_loc]['longitude'])
                                    try:
                                        route = self.hydrogen_pipeline_calculator.calculate_clustered_pipeline_route(
                                            cluster.cluster_id,
                                            cluster_members,
                                            cluster.center_coord,
                                            mtj_coords
                                        )
                                        self.clustered_routes[route_key] = route
                                        layer1_distance = route.layer1_distances.get(h_loc, 0)
                                        layer2_distance = route.layer2_distance
                                        layer3_distance = route.layer3_distance
                                        if route.route_geometry:
                                            route_coordinates = [[coord[1], coord[0]] for coord in route.route_geometry]
                                        logger.info(f"重新计算聚类路径: {h_loc} (cluster_{cluster_id}) -> {mtj_loc}, Layer1={layer1_distance:.2f}km, Layer2={layer2_distance:.2f}km, Layer3={layer3_distance:.2f}km")
                                    except Exception as e:
                                        logger.warning(f"聚类路径计算失败: {h_loc} (cluster_{cluster_id}) -> {mtj_loc}, 使用直线距离, 错误: {str(e)}")
                                        # 降级处理:使用直线距离计算Layer距离
                                        h_coords = self._get_location_coordinates(h_loc)
                                        layer1_distance = self._calculate_haversine_distance(
                                            h_coords[0], h_coords[1],
                                            cluster_center[0], cluster_center[1]
                                        )
                                        layer2_layer3_distance = self._calculate_haversine_distance(
                                            cluster_center[0], cluster_center[1],
                                            mtj_coords[0], mtj_coords[1]
                                        )
                                        layer2_distance = layer2_layer3_distance * 0.3
                                        layer3_distance = layer2_layer3_distance * 0.7
                                        _, route_coordinates = self._calculate_location_distance_with_route(h_loc, mtj_loc)
                                break

                        if cluster_id is None:
                            for noise_loc, noise_coord in self.clustering_results.noise_points:
                                if h_loc == noise_loc:
                                    _, fallback_route = self._calculate_location_distance_with_route(h_loc, mtj_loc)
                                    route_coordinates = fallback_route if fallback_route else []
                                    break

                    if not route_coordinates:
                        _, route_coordinates = self._calculate_location_distance_with_route(h_loc, mtj_loc)

                    solution['hydrogen_transport'][transport_key] = {
                        'from_location': h_loc,
                        'to_location': mtj_loc,
                        'transport_kg_h2': var.x,
                        'distance_km': distance_km,
                        'from_latitude': from_coords[0],
                        'from_longitude': from_coords[1],
                        'to_latitude': to_coords[0],
                        'to_longitude': to_coords[1],
                        'route_coordinates': route_coordinates,
                        'transport_type': 'H2',
                        'transport_mode': 'pipeline',
                        'cluster_id': cluster_id,
                        'cluster_center': cluster_center,
                        'layer1_distance_km': layer1_distance,
                        'layer2_distance_km': layer2_distance,
                        'layer3_distance_km': layer3_distance
                    }
        
        # 输出氢气运输统计信息（【禁用罐车运输】仅显示管道运输）
        print(f"\n=== 氢气运输决策统计 ===")
        # print(f"氢气罐车运输变量: {truck_count} 个, 其中非零: {truck_positive} 个")  # 【禁用罐车运输】
        print(f"氢能管道运输变量: {pipeline_count} 个, 其中非零: {pipeline_positive} 个")
        print(f"总氢气运输记录: {len(solution['hydrogen_transport'])} 条")
        if solution['hydrogen_transport']:
            total_h2_transport = sum(info['transport_kg_h2'] for info in solution['hydrogen_transport'].values())
            print(f"总氢气运输量: {total_h2_transport:.2f} kg/week")
        print("=======================\n")

        # v3.0: 提取煤炭采购数据（替代CO₂运输）
        solution['coal_purchase'] = {}
        coal_purchase_count = 0
        coal_purchase_positive = 0

        if hasattr(self, 'coal_purchase_vars') and self.coal_purchase_vars:
            for (methanol_loc, week), var in self.coal_purchase_vars.items():
                coal_purchase_count += 1
                if var.x > 0:
                    coal_purchase_positive += 1
                    purchase_key = f"{methanol_loc}_week_{week}"

                    solution['coal_purchase'][purchase_key] = {
                        'location': methanol_loc,
                        'week': week,
                        'coal_kg': var.x,  # 煤炭采购量 (kg/week)
                        'co2_generated_kg': var.x * self.coal_supply.co2_per_kg_coal  # 气化产生CO₂量
                    }

        # 输出煤炭采购统计信息
        print(f"\n=== 煤炭采购决策统计 (v3.0) ===")
        print(f"煤炭采购变量: {coal_purchase_count} 个, 其中非零: {coal_purchase_positive} 个")
        print(f"总煤炭采购记录: {len(solution['coal_purchase'])} 条")
        if solution['coal_purchase']:
            total_coal = sum(info['coal_kg'] for info in solution['coal_purchase'].values())
            total_co2_from_coal = sum(info['co2_generated_kg'] for info in solution['coal_purchase'].values())
            print(f"总煤炭采购量: {total_coal:.2f} kg")
            print(f"气化产生CO₂总量: {total_co2_from_coal:.2f} kg")
            print(f"煤炭价格: {self.coal_supply.coal_price_yuan_per_ton} 元/吨")
            print(f"CO₂产率: {self.coal_supply.co2_per_kg_coal} kg CO₂/kg 煤")
        print("=======================\n")

        # 提取库存信息
        solution['inventory'] = {}
        for (location, hour), var in self.storage_vars.items():
            if var.x > 0:
                storage_key = f"{location}_{hour}"
                coords = self._get_location_coordinates(location)
                solution['inventory'][storage_key] = {
                    'location': location,
                    'hour': hour,
                    'inventory_kg': var.x,
                    'latitude': coords[0],
                    'longitude': coords[1]
                }
        # 由于使用表达式对象，不再需要手动验证成本组件
        logger.info("使用表达式对象获取成本数据，确保数据一致性")

        # 使用表达式对象计算年产量和生命周期总产量
        # 创建总生产量表达式对象（如果还不存在）
        if not hasattr(self, 'production_total_expr'):
            self.production_total_expr = gp.quicksum(
                var for var in self.production_vars.values()
            )

        # 从表达式对象获取总生产量
        total_actual_production = self.production_total_expr.getValue()

        # 获取经济参数
        project_lifespan = self.economic_params['project_lifespan']
        discount_rate = self.economic_params['discount_rate']

        # 计算现值系数（与目标函数保持一致）
        if discount_rate == 0:
            present_value_factor = project_lifespan
        else:
            present_value_factor = (1 - (1 + discount_rate)**(-project_lifespan)) / discount_rate

        # 计算年化产量（从时间窗口扩展到全年）
        annual_production_kg = total_actual_production * (52.0 / self.time_horizon_weeks)

        # 计算生命周期总产量（简单累计，不含折现）
        lifecycle_total_production_kg = annual_production_kg * project_lifespan

        # 计算生命周期现值化总产量（用于正确的平准化成本计算）
        lifecycle_present_value_production_kg = annual_production_kg * present_value_factor

        # 存储产量数据
        solution['annual_production_kg'] = annual_production_kg
        solution['lifecycle_total_production_kg'] = lifecycle_total_production_kg

        # 使用表达式对象计算平准化成本（含短缺和不含短缺）
        # 目标函数中的成本已经是现值化的，产量也需要现值化来匹配
        total_cost_with_shortage = self.model.ObjVal  # 已经是现值化的总成本
        total_cost_without_shortage = cost_metrics.get('total_cost_excluding_shortage', 0)  # 已经是现值化的成本

        if lifecycle_present_value_production_kg > 0:
            # 正确的生命周期平准化成本（含短缺）= 现值化总成本 / 现值化总产量
            lifecycle_levelized_cost_per_kg = total_cost_with_shortage / lifecycle_present_value_production_kg

            # 正确的生命周期平准化成本（不含短缺）= 现值化总成本 / 现值化总产量
            lifecycle_levelized_cost_excluding_shortage_per_kg = total_cost_without_shortage / lifecycle_present_value_production_kg

            # 年化平准化成本（含短缺）
            annual_levelized_cost_per_kg = total_cost_with_shortage / project_lifespan / annual_production_kg if annual_production_kg > 0 else 0
        else:
            lifecycle_levelized_cost_per_kg = 0
            lifecycle_levelized_cost_excluding_shortage_per_kg = 0
            annual_levelized_cost_per_kg = 0

        # 存储平准化成本
        solution['lifecycle_levelized_cost_per_kg'] = lifecycle_levelized_cost_per_kg
        solution['lifecycle_levelized_cost_excluding_shortage_per_kg'] = lifecycle_levelized_cost_excluding_shortage_per_kg
        solution['annual_levelized_cost_per_kg'] = annual_levelized_cost_per_kg

        logger.info("已使用表达式对象和折现考虑计算平准化成本")
        logger.info(f"贴现率: {discount_rate*100:.1f}%，项目期限: {project_lifespan}年")
        logger.info(f"现值系数: {present_value_factor:.2f}")
        logger.info(f"总生产量(表达式对象值): {total_actual_production:,.2f} kg")
        logger.info(f"年产量: {annual_production_kg:,.2f} kg")
        logger.info(f"生命周期总产量(简单累计): {lifecycle_total_production_kg:,.2f} kg")
        logger.info(f"生命周期现值化总产量: {lifecycle_present_value_production_kg:,.2f} kg")
        logger.info(f"生命周期平准化成本(含短缺,考虑折现): {lifecycle_levelized_cost_per_kg:,.2f} 元/kg")
        logger.info(f"生命周期平准化成本(不含短缺,考虑折现): {lifecycle_levelized_cost_excluding_shortage_per_kg:,.2f} 元/kg")
        logger.info(f"年化平准化成本: {annual_levelized_cost_per_kg:,.2f} 元/kg")

        # 输出需求满足比例
        demand_fulfillment_ratio = cost_metrics.get('demand_fulfillment_ratio', 1.0)
        logger.info(f"需求满足比例: {demand_fulfillment_ratio*100:.2f}%")

        # ==================================================================================
        # 验证平准化成本约束满足情况
        # ==================================================================================
        threshold = self.config.get('economic_parameters', {}).get('levelized_cost_threshold_yuan_per_kg', 5.62)

        logger.info("")
        logger.info("="*80)
        logger.info("【平准化成本约束验证】")
        logger.info(f"门槛值设定: {threshold} 元/kg（不含短缺成本）")
        logger.info(f"实际平准化成本(不含短缺): {lifecycle_levelized_cost_excluding_shortage_per_kg:,.2f} 元/kg")

        if lifecycle_levelized_cost_excluding_shortage_per_kg <= threshold:
            constraint_status = "✓ 满足"
            constraint_margin = threshold - lifecycle_levelized_cost_excluding_shortage_per_kg
            logger.info(f"约束状态: {constraint_status}")
            logger.info(f"成本余量: {constraint_margin:,.4f} 元/kg（距离门槛值的余量）")
        else:
            constraint_status = "✗ 违反"
            constraint_violation = lifecycle_levelized_cost_excluding_shortage_per_kg - threshold
            logger.info(f"约束状态: {constraint_status}")
            logger.info(f"约束违反程度: {constraint_violation:,.4f} 元/kg（超出门槛值）")
            logger.warning("警告：当前方案的平准化成本超出设定门槛值！")

        logger.info(f"成本比例: {(lifecycle_levelized_cost_excluding_shortage_per_kg / threshold * 100):,.1f}% 相对于门槛值")
        logger.info("="*80)

        # 将约束验证结果存储到solution中
        solution['levelized_cost_constraint_satisfied'] = lifecycle_levelized_cost_excluding_shortage_per_kg <= threshold
        solution['levelized_cost_threshold'] = threshold
        solution['levelized_cost_margin_or_violation'] = threshold - lifecycle_levelized_cost_excluding_shortage_per_kg

        # ==================================================================================
        # 输出跳过路径统计信息
        # ==================================================================================
        logger.info("")
        logger.info("="*80)
        logger.info("【路径跳过统计】")

        total_skipped = len(self.skipped_routes['hydrogen_pipeline']) + len(self.skipped_routes['co2_pipeline'])

        if total_skipped > 0:
            logger.warning(f"共有 {total_skipped} 条路径因无管道连接而被跳过")

            if self.skipped_routes['hydrogen_pipeline']:
                logger.info(f"\n氢气管道路径跳过数量: {len(self.skipped_routes['hydrogen_pipeline'])}")
                logger.info("跳过的氢气管道路径:")
                for i, route in enumerate(self.skipped_routes['hydrogen_pipeline'][:10], 1):  # 只显示前10条
                    logger.info(f"  {i}. {route['from']} -> {route['to']} ({route['type']})")
                    logger.debug(f"     原因: {route['reason']}")
                if len(self.skipped_routes['hydrogen_pipeline']) > 10:
                    logger.info(f"  ... 还有 {len(self.skipped_routes['hydrogen_pipeline']) - 10} 条路径")

            if self.skipped_routes['co2_pipeline']:
                logger.info(f"\nCO₂管道路径跳过数量: {len(self.skipped_routes['co2_pipeline'])}")
                logger.info("跳过的CO₂管道路径:")
                for i, route in enumerate(self.skipped_routes['co2_pipeline'][:10], 1):  # 只显示前10条
                    logger.info(f"  {i}. {route['from']} -> {route['to']} ({route['type']})")
                    logger.debug(f"     原因: {route['reason']}")
                if len(self.skipped_routes['co2_pipeline']) > 10:
                    logger.info(f"  ... 还有 {len(self.skipped_routes['co2_pipeline']) - 10} 条路径")

            logger.info("\n说明：这些路径在优化中被分配了极高成本(1e9)，优化器会自动避免选择")
        else:
            logger.info("所有路径均找到管道连接，无跳过路径")

        logger.info("="*80)

        # 将跳过路径信息存储到solution中
        solution['skipped_routes'] = {
            'hydrogen_pipeline': self.skipped_routes['hydrogen_pipeline'],
            'co2_pipeline': self.skipped_routes['co2_pipeline'],
            'total_count': total_skipped
        }

        # 注意：已移除 decision_variables 的保存（2025-12-14）
        # 原因：保存所有决策变量会导致内存爆炸（45GB+），且这些数据从未被可视化或分析代码使用
        # 如需调试特定变量，请直接在优化完成后通过 self.xxx_vars 访问

        return solution

    def _get_cost_metrics_from_expressions(self) -> Dict:
        """从 Gurobi 表达式对象直接获取所有成本指标"""
        logger.info("从表达式对象获取成本指标...")

        # 检查是否有表达式对象
        if not hasattr(self, 'cost_expressions') or not self.cost_expressions:
            raise ValueError("表达式对象未初始化，请先调用_create_objective方法")

        # 获取经济参数
        discount_rate = self.economic_params['discount_rate']
        project_lifespan = self.economic_params['project_lifespan']

        # 计算现值系数（与目标函数保持完全一致）
        if discount_rate == 0:
            present_value_factor = project_lifespan
        else:
            present_value_factor = (1 - (1 + discount_rate)**(-project_lifespan)) / discount_rate

        # 运营成本扩展系数
        operation_expansion_factor = 52.0 / self.time_horizon_weeks


        # 从表达式对象获取成本分解数值
        cost_breakdown = {}

        # 获取所有成本项的数值
        for cost_name, expr in self.cost_expressions.items():
            try:
                cost_breakdown[cost_name] = expr.getValue()
            except Exception as e:
                logger.warning(f"获取成本项 {cost_name} 的数值失败: {e}")
                cost_breakdown[cost_name] = 0

        # 获取聚合成本数值
        for agg_name, expr in self.cost_aggregates.items():
            try:
                cost_breakdown[agg_name] = expr.getValue()
            except Exception as e:
                logger.warning(f"获取聚合成本 {agg_name} 的数值失败: {e}")
                cost_breakdown[agg_name] = 0

        # 计算需求满足比例
        demand_fulfillment_ratio = self._calculate_demand_fulfillment_ratio()
        cost_breakdown['demand_fulfillment_ratio'] = demand_fulfillment_ratio

        logger.info("成本指标获取完成")
        logger.info(f"生命周期总成本: {self.model.ObjVal:,.2f} 元")
        logger.info(f"不含短缺总成本: {cost_breakdown.get('total_cost_excluding_shortage', 0):,.2f} 元")
        logger.info(f"短缺成本: {cost_breakdown.get('shortage_cost', 0):,.2f} 元")
        logger.info(f"需求满足比例: {demand_fulfillment_ratio*100:.2f}%")

        return cost_breakdown

    # _calculate_cost_breakdown 方法已被 _get_cost_metrics_from_expressions 替代

    def _calculate_demand_fulfillment_ratio(self) -> float:
        """计算需求满足比例: 1 - (缺货产量 / (缺货产量 + 总产量))"""
        try:
            # 检查是否有performance_expressions
            if not hasattr(self, 'performance_expressions') or not self.performance_expressions:
                logger.warning("[调试] performance_expressions未初始化，需求满足比例设为1.0")
                return 1.0

            # 获取表达式的数值
            shortage_total_value = 0.0
            production_total_value = 0.0
            total_demand_value = 0.0

            # 获取缺货产量总和
            if 'shortage_total' in self.performance_expressions:
                shortage_total_value = self.performance_expressions['shortage_total'].getValue()
                logger.info(f"[调试] 缺货产量总和: {shortage_total_value:,.2f} kg")
            else:
                logger.warning("[调试] 未找到shortage_total表达式")

            # 获取总产量
            if 'production_total' in self.performance_expressions:
                production_total_value = self.performance_expressions['production_total'].getValue()
                logger.info(f"[调试] 总产量: {production_total_value:,.2f} kg")
            else:
                logger.warning("[调试] 未找到production_total表达式")

            # 获取总需求量
            if 'total_demand' in self.performance_expressions:
                total_demand_value = self.performance_expressions['total_demand'].getValue()
                logger.info(f"[调试] 总需求量(总产量+缺货): {total_demand_value:,.2f} kg")
            else:
                logger.warning("[调试] 未找到total_demand表达式")

            # 计算需求满足比例
            if total_demand_value > 0:
                # 需求满足比例 = 1 - (缺货产量 / 总需求量)
                # 其中总需求量 = 总产量 + 缺货产量
                demand_fulfillment_ratio = 1.0 - (shortage_total_value / total_demand_value)

                # 确保比例在0-1之间
                demand_fulfillment_ratio = max(0.0, min(1.0, demand_fulfillment_ratio))

                logger.info(f"[调试] 需求满足比例计算: 1 - ({shortage_total_value:,.2f} / {total_demand_value:,.2f}) = {demand_fulfillment_ratio:.4f}")

                return demand_fulfillment_ratio
            else:
                # 如果总需求为0，定义为100%满足
                logger.info("[调试] 总需求量为0，需求满足比例设为1.0 (100%)")
                return 1.0

        except Exception as e:
            logger.error(f"计算需求满足比例时出错: {e}")
            logger.info("[调试] 发生错误，需求满足比例设为1.0 (100%)")
            return 1.0

    def _calculate_unit_costs_from_optimization(self, solution: Dict) -> Dict:
        """
        直接使用优化模型的现有结果，基于目标函数值计算单位成本

        Args:
            solution: 优化求解结果

        Returns:
            Dict: 单位成本分析结果
        """
        try:
            # 基于配置参数计算理论单位成本（不依赖cost_breakdown）

            # 氢气理论成本（基于配置参数）
            electricity_cost_yuan_per_mwh = self.costs.get('renewable_electricity_cost_yuan_per_mwh', 500)
            electrolysis_power_kwh_per_kg = self.costs.get('electrolysis_power_consumption', 45)
            electrolysis_efficiency = self.costs.get('electrolysis_efficiency', 0.8)

            # 氢气电力成本（元/kg H2）
            h2_electricity_cost_per_kg = (electrolysis_power_kwh_per_kg / 1000) * electricity_cost_yuan_per_mwh / electrolysis_efficiency

            # 电解槽设备摊销成本（简化计算）
            electrolyzer_capex_raw = self.config['equipment_raw_costs']['electrolyzer']['capex_raw']
            discount_rate = self.economic_params['discount_rate']
            project_lifespan = self.economic_params['project_lifespan']
            if discount_rate == 0:
                annuity_factor = 1.0 / project_lifespan
            else:
                annuity_factor = discount_rate / (1 - (1 + discount_rate)**(-project_lifespan))

            # 假设电解槽年利用小时数
            annual_utilization_hours = 8760 * 0.8  # 80%利用率
            h2_equipment_cost_per_kg = (electrolyzer_capex_raw * annuity_factor) / (annual_utilization_hours * electrolysis_power_kwh_per_kg / 1000)

            # 氢气总成本
            h2_total_cost_per_kg = h2_electricity_cost_per_kg + h2_equipment_cost_per_kg

            # MTJ理论成本（基于配置参数）
            mtj_variable_opex_per_kg = 0.3  # 元/kg，配置文件中的MTJ变动运营成本
            hydrogen_ratio = 0.12  # kg H2 per kg MTJ（化学计量比）

            # MTJ单位成本组成
            mtj_hydrogen_raw_material_cost_per_kg = h2_total_cost_per_kg * hydrogen_ratio
            mtj_co2_raw_material_cost_per_kg = 0  # 假设CO2成本为0
            mtj_equipment_cost_per_kg = 0.3  # 简化设备摊销成本
            mtj_operation_cost_per_kg = mtj_variable_opex_per_kg
            mtj_total_cost_per_kg = (mtj_hydrogen_raw_material_cost_per_kg + mtj_co2_raw_material_cost_per_kg +
                                   mtj_equipment_cost_per_kg + mtj_operation_cost_per_kg)

            # 运输和储存成本（简化）
            h2_transport_cost_per_kg_km = 0.05
            mtj_transport_cost_per_kg_km = 0.03
            h2_storage_cost_per_kg = 0.016
            mtj_storage_cost_per_kg = 0

            # 效率参数
            electrolysis_theoretical_efficiency = 0.8
            electrolysis_actual_efficiency = electrolysis_efficiency
            mtj_conversion_efficiency = 0.85
            overall_efficiency = electrolysis_actual_efficiency * mtj_conversion_efficiency
            power_consumption_mwh_per_kg_mtj = (electrolysis_power_kwh_per_kg / 1000) * hydrogen_ratio / overall_efficiency

            # 成本占比计算
            h_total = h2_total_cost_per_kg
            hydrogen_electricity_ratio = h2_electricity_cost_per_kg / h_total if h_total > 0 else 0
            hydrogen_equipment_ratio = h2_equipment_cost_per_kg / h_total if h_total > 0 else 0
            hydrogen_operation_ratio = 0

            m_total = mtj_total_cost_per_kg
            mtj_hydrogen_ratio = mtj_hydrogen_raw_material_cost_per_kg / m_total if m_total > 0 else 0
            mtj_co2_ratio = mtj_co2_raw_material_cost_per_kg / m_total if m_total > 0 else 0
            
            m_total = mtj_total_cost_per_kg
            mtj_hydrogen_ratio = mtj_hydrogen_raw_material_cost_per_kg / m_total if m_total > 0 else 0
            mtj_equipment_ratio = mtj_equipment_cost_per_kg / m_total if m_total > 0 else 0
            mtj_operation_ratio = mtj_operation_cost_per_kg / m_total if m_total > 0 else 0
            
            result = {
                # 氢气成本 - 基于配置参数的理论计算
                'hydrogen_electricity_cost_yuan_per_kg': h2_electricity_cost_per_kg,
                'hydrogen_equipment_amortization_yuan_per_kg': h2_equipment_cost_per_kg,
                'hydrogen_operation_maintenance_yuan_per_kg': 0,
                'hydrogen_total_production_cost_yuan_per_kg': h2_total_cost_per_kg,
                
                # MTJ成本 - 基于优化模型的实际计算
                'mtj_hydrogen_raw_material_cost_yuan_per_kg': mtj_hydrogen_raw_material_cost_per_kg,
                'mtj_co2_raw_material_cost_yuan_per_kg': 0.0,
                'mtj_equipment_amortization_yuan_per_kg': mtj_equipment_cost_per_kg,
                'mtj_operation_maintenance_yuan_per_kg': mtj_operation_cost_per_kg,
                'mtj_total_production_cost_yuan_per_kg': mtj_total_cost_per_kg,
                
                # 运输储存成本 - 使用优化结果
                'h2_transport_unit_cost_yuan_per_kg_km': 0.05,  # 配置值
                'mtj_transport_unit_cost_yuan_per_kg_km': 0.03,  # 配置值  
                'h2_storage_cost_yuan_per_kg': h2_storage_cost_per_kg,
                'mtj_storage_cost_yuan_per_kg': mtj_storage_cost_per_kg,
                
                # 效率指标 - 使用配置参数
                'electrolysis_theoretical_efficiency': 80.0,
                'electrolysis_actual_efficiency': electrolysis_efficiency * 100,
                'electrolysis_actual_efficiency_percent': electrolysis_efficiency * 100,
                'h2_to_mtj_conversion_efficiency': mtj_conversion_efficiency * 100,
                'overall_electricity_to_mtj_efficiency': overall_efficiency * 100,
                'power_consumption_mwh_per_kg_mtj': power_consumption_mwh_per_kg_mtj,
                
                # 成本占比 - 简单计算
                'hydrogen_electricity_cost_ratio': hydrogen_electricity_ratio,
                'hydrogen_equipment_cost_ratio': hydrogen_equipment_ratio,
                'hydrogen_operation_cost_ratio': hydrogen_operation_ratio,
                'mtj_hydrogen_cost_ratio': mtj_hydrogen_ratio,
                'mtj_co2_cost_ratio': 0.0,
                'mtj_equipment_cost_ratio': mtj_equipment_ratio,
                'mtj_operation_cost_ratio': mtj_operation_ratio
            }
            
            logger.info(f"基于配置参数计算单位成本: 氢气 {h2_total_cost_per_kg:.4f} 元/kg, MTJ {mtj_total_cost_per_kg:.4f} 元/kg")
            return result
            
        except Exception as e:
            logger.error(f"提取优化结果成本数据失败: {e}")
            return {}
    
    def calculate_carbon_emissions(self, solution: Dict) -> Dict:
        """计算碳排放结果（基于优化求解后的变量值）

        注意：所有碳排放表达式已在模型内部创建，此函数仅负责从表达式获取数值并计算衍生指标
        """
        logger.info("="*80)
        logger.info("从模型表达式获取碳排放结果...")
        logger.info("="*80)

        carbon_results = {}

        # 检查是否创建了碳排放表达式
        if not hasattr(self, 'carbon_expressions'):
            logger.warning("未创建碳排放表达式，跳过碳排放计算")
            return carbon_results

        logger.info(f"[调试] 碳排放表达式数量: {len(self.carbon_expressions)}")
        logger.info(f"[调试] 碳排放汇总项数量: {len(self.carbon_aggregates)}")

        try:
            # 1. 从表达式获取各细分项碳排放（kg CO2eq）
            carbon_results['detailed'] = {}
            for name, expr in self.carbon_expressions.items():
                value = expr.getValue() if hasattr(expr, 'getValue') else 0
                carbon_results['detailed'][name] = value
                logger.info(f"  {name}: {value:.2f} kg CO2eq")

            # 2. 从表达式获取各阶段汇总碳排放
            carbon_results['by_stage'] = {}
            for name, expr in self.carbon_aggregates.items():
                value = expr.getValue() if hasattr(expr, 'getValue') else 0
                carbon_results['by_stage'][name] = value
                logger.info(f"  {name}: {value:.2f} kg CO2eq")

            # 3. 从性能表达式获取总生产量（kg SAF）
            total_production = self.performance_expressions['production_total'].getValue()
            carbon_results['total_production_kg'] = total_production

            # 4. 计算碳强度（基于模型内部已准备的参数）
            if total_production > 0:
                # 获取总碳排放
                total_emissions = carbon_results['by_stage'].get('total_emissions', 0)

                # 质量碳强度 (kg CO2eq/kg SAF)
                carbon_intensity_mass = total_emissions / total_production
                carbon_results['carbon_intensity_kg'] = carbon_intensity_mass

                # 能量碳强度 (g CO2eq/MJ) - 使用模型内部准备的参数
                saf_energy_content = self.carbon_params.get('saf_energy_content', 43.15)
                carbon_intensity_energy = carbon_intensity_mass * 1000 / saf_energy_content
                carbon_results['carbon_intensity_mj'] = carbon_intensity_energy

                # 与基准比较 - 使用模型内部准备的参数
                traditional_jet = self.carbon_params.get('traditional_jet_ci', 89)
                corsia_limit = self.carbon_params.get('corsia_limit_ci', 30)

                carbon_results['vs_traditional_jet'] = (carbon_intensity_energy / traditional_jet - 1) * 100
                carbon_results['vs_corsia'] = (carbon_intensity_energy / corsia_limit - 1) * 100

                logger.info(f"碳强度: {carbon_intensity_mass:.3f} kg CO2eq/kg SAF")
                logger.info(f"碳强度: {carbon_intensity_energy:.2f} g CO2eq/MJ")
                logger.info(f"相比传统航煤: {carbon_results['vs_traditional_jet']:.1f}%")
                logger.info(f"相比CORSIA标准: {carbon_results['vs_corsia']:.1f}%")
            else:
                logger.warning("总生产量为0，无法计算碳强度")

            # 5. 计算各阶段贡献比例
            total_emissions = carbon_results['by_stage'].get('total_emissions', 0)
            if total_emissions > 0:
                carbon_results['stage_contributions'] = {}
                for stage in ['raw_material_emissions', 'facility_emissions',
                             'production_emissions', 'storage_emissions', 'transport_emissions']:
                    if stage in carbon_results['by_stage']:
                        value = carbon_results['by_stage'][stage]
                        percentage = (value / total_emissions) * 100
                        carbon_results['stage_contributions'][stage] = {
                            'value': value,
                            'percentage': percentage
                        }
                        logger.info(f"  {stage}: {percentage:.1f}%")

            return carbon_results

        except Exception as e:
            logger.error(f"碳排放计算失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return carbon_results

    def save_carbon_emissions_report(self, carbon_results: Dict, output_dir: str, timestamp: str):
        """保存碳排放报告到CSV文件"""
        if not carbon_results:
            logger.warning("没有碳排放数据可保存")
            return

        try:
            # 创建碳排放详细报告DataFrame
            # 确保输出目录存在
            os.makedirs(output_dir, exist_ok=True)

            report_data = []

            # 1. 总体指标
            report_data.append({
                '类别': '总体指标',
                '项目': '总碳排放',
                '数值': carbon_results.get('by_stage', {}).get('total_emissions', 0),
                '单位': 'kg CO2eq',
                '备注': f"优化时段: {self.time_horizon_weeks}周"
            })

            report_data.append({
                '类别': '总体指标',
                '项目': '年化碳排放',
                '数值': carbon_results.get('by_stage', {}).get('annual_emissions', 0),
                '单位': 'kg CO2eq/年',
                '备注': '扩展到全年'
            })

            report_data.append({
                '类别': '总体指标',
                '项目': '总生产量',
                '数值': carbon_results.get('total_production_kg', 0),
                '单位': 'kg SAF',
                '备注': f"{self.time_horizon_weeks}周内"
            })

            report_data.append({
                '类别': '总体指标',
                '项目': '碳强度(质量)',
                '数值': carbon_results.get('carbon_intensity_kg', 0),
                '单位': 'kg CO2eq/kg SAF',
                '备注': ''
            })

            report_data.append({
                '类别': '总体指标',
                '项目': '碳强度(能量)',
                '数值': carbon_results.get('carbon_intensity_mj', 0),
                '单位': 'g CO2eq/MJ',
                '备注': ''
            })

            # 2. 各阶段排放
            stage_mapping = {
                'raw_material_emissions': '原料获取',
                'facility_emissions': '设施建设',
                'production_emissions': '生产过程',
                'storage_emissions': '储存处理',
                'transport_emissions': '运输配送'
            }

            contributions = carbon_results.get('stage_contributions', {})
            for stage_key, stage_name in stage_mapping.items():
                if stage_key in contributions:
                    data = contributions[stage_key]
                    report_data.append({
                        '类别': '各阶段排放',
                        '项目': stage_name,
                        '数值': data['value'],
                        '单位': 'kg CO2eq',
                        '备注': f"占比: {data['percentage']:.1f}%"
                    })

            # 3. 细分项排放
            detailed = carbon_results.get('detailed', {})
            detail_mapping = {
                'saf_facility': 'SAF工厂建设',
                'electrolyzer_facility': '电解槽建设',
                'methanol_to_saf': '甲醇制SAF',
                'h2_production': '氢气生产',
                'mtj_storage': 'MTJ储存',
                'h2_storage': '氢气储存',
                'h2_transport': '氢气运输',
                'mtj_transport': 'MTJ运输'
            }

            for key, name in detail_mapping.items():
                if key in detailed:
                    report_data.append({
                        '类别': '细分项排放',
                        '项目': name,
                        '数值': detailed[key],
                        '单位': 'kg CO2eq',
                        '备注': ''
                    })

            # 4. 基准对比
            report_data.append({
                '类别': '基准对比',
                '项目': '传统航煤碳强度',
                '数值': self.carbon_params.get('benchmarks', {}).get('traditional_jet_fuel', 89),
                '单位': 'g CO2eq/MJ',
                '备注': 'ICAO基准'
            })

            report_data.append({
                '类别': '基准对比',
                '项目': 'CORSIA限值',
                '数值': self.carbon_params.get('benchmarks', {}).get('corsia_limit', 30),
                '单位': 'g CO2eq/MJ',
                '备注': '2027年标准'
            })

            report_data.append({
                '类别': '基准对比',
                '项目': '相比传统航煤',
                '数值': carbon_results.get('vs_traditional_jet', 0),
                '单位': '%',
                '备注': '负值表示减排'
            })

            report_data.append({
                '类别': '基准对比',
                '项目': '相比CORSIA标准',
                '数值': carbon_results.get('vs_corsia', 0),
                '单位': '%',
                '备注': '负值表示优于标准'
            })

            # 保存到CSV
            df = pd.DataFrame(report_data)
            csv_path = os.path.join(output_dir, f"carbon_emissions_{timestamp}.csv")
            df.to_csv(csv_path, index=False, encoding='utf-8-sig')
            logger.info(f"碳排放报告已保存到: {csv_path}")

            # 同时保存详细的JSON格式数据
            json_path = os.path.join(output_dir, f"carbon_emissions_detailed_{timestamp}.json")
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(carbon_results, f, ensure_ascii=False, indent=2)
            logger.info(f"碳排放详细数据已保存到: {json_path}")

        except Exception as e:
            logger.error(f"保存碳排放报告失败: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def save_results(self, solution: Dict, output_dir: str):
        """保存求解结果"""
        import json  # 确保json模块可用
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 如果output_dir为None，使用配置文件中的默认目录
        if output_dir is None:
            output_dir = self._get_results_dir()
            logger.info(f"未指定输出目录，使用配置文件默认目录: {output_dir}")

        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)

        # 首先保存基础设施选点信息
        self._save_infrastructure_locations(output_dir, timestamp)
        
        # 从solution中获取不含短缺成本的平准化成本
        lifecycle_levelized_cost_excluding_shortage = solution.get("lifecycle_levelized_cost_excluding_shortage_per_kg", 0)

        # 直接从优化模型计算单位成本，不依赖cost_breakdown
        unit_costs = self._calculate_unit_costs_from_optimization(solution)
        logger.info("直接从优化模型计算单位成本数据用于optimization_summary")

        # 获取表达式对象的成本分解结果
        cost_breakdown = solution.get('cost_breakdown', {})
        logger.info(f"从表达式对象获取的成本分解数据: {len(cost_breakdown)} 项")

        # 建立表达式对象字段到CSV输出字段的映射
        cost_field_mapping = {
            'facility_investment_cost': 'MTJ工厂建设投资(元)',
            'electrolyzer_investment_cost': '电解槽建设投资(元)',
            'storage_equipment_cost': 'MTJ储存设备投资(元)',
            'h2_storage_investment': '氢气储存设备投资(元)',
            'facility_operation_cost': 'MTJ工厂运营成本(元)',
            'production_cost': 'MTJ生产运营成本(元)',
            # 'hydrogen_transport_operation': '氢气罐车运输成本(元)',  # 【禁用罐车运输】
            'hydrogen_pipeline_operation': '氢能管道运输成本(元)',
            'co2_pipeline_transport_cost': 'CO₂管道运输成本(元)',
            'transport_operation_cost': 'MTJ运输运营成本(元)',
            'storage_operation_cost': 'MTJ储存运营成本(元)',
            'h2_storage_operation': '氢气储存运营成本(元)',
            'electricity_cost': '电力成本(元)',
            'final_inventory_cost': '期末库存处置成本(元)',
            'shortage_cost': '短缺惩罚成本(元)'
        }

        # 获取不含短缺的总成本
        total_cost_excluding_shortage = cost_breakdown.get('total_cost_excluding_shortage', 0)
        project_lifespan = solution.get("project_lifespan_years", 20)

        # 获取需求满足比例
        demand_fulfillment_ratio = cost_breakdown.get('demand_fulfillment_ratio', 1.0)

        results_summary = {
            "优化状态": [solution.get("optimization_status", "未知")],
            "生命周期总成本(元)": [total_cost_excluding_shortage],
            "年化成本(元/年)": [total_cost_excluding_shortage / project_lifespan if project_lifespan > 0 else 0],
            "生命周期平准化成本(元/kg)": [solution.get("lifecycle_levelized_cost_per_kg", 0)],
            "年化平准化成本(元/kg)": [solution.get("annual_levelized_cost_per_kg", 0)],
            "生命周期平准化成本_不含短缺(元/kg)": [lifecycle_levelized_cost_excluding_shortage],
            "平准化成本门槛值(元/kg)": [solution.get("levelized_cost_threshold", 0)],
            "平准化成本约束满足": [solution.get("levelized_cost_constraint_satisfied", False)],
            "平准化成本余量_或违反程度(元/kg)": [solution.get("levelized_cost_margin_or_violation", 0)],
            "需求满足比例(%)": [demand_fulfillment_ratio * 100],
        }

        # 使用表达式对象的实际成本数据
        logger.info("="*80)
        logger.info("详细成本分解结果（基于表达式对象）")
        logger.info("="*80)

        total_investment = 0
        total_operation = 0

        # 投资成本类别
        investment_fields = ['facility_investment_cost', 'electrolyzer_investment_cost',
                           'storage_equipment_cost',
                           'h2_storage_investment', 'hydrogen_transport_investment',
                           'hydrogen_pipeline_investment']

        # 运营成本类别（【禁用罐车运输】移除hydrogen_transport_operation）
        operation_fields = ['facility_operation_cost', 'production_cost', 'hydrogen_production_cost',
                          # 'hydrogen_transport_operation',  # 【禁用罐车运输】
                          'hydrogen_pipeline_operation',
                          'transport_operation_cost', 'storage_operation_cost', 'h2_storage_operation',
                          'electricity_cost', 'final_inventory_cost']

        logger.info("【投资成本明细】")
        for expr_field, csv_field in cost_field_mapping.items():
            cost_value = cost_breakdown.get(expr_field, 0)
            results_summary[csv_field] = [cost_value]

            if expr_field in investment_fields:
                total_investment += cost_value
                if cost_value > 0:
                    logger.info(f"  {csv_field}: {cost_value:,.2f} 元")
                else:
                    logger.info(f"  {csv_field}: 0.00 元")

        logger.info(f"投资成本小计: {total_investment:,.2f} 元")
        logger.info("")

        logger.info("【运营成本明细】")
        for expr_field, csv_field in cost_field_mapping.items():
            cost_value = cost_breakdown.get(expr_field, 0)

            if expr_field in operation_fields:
                total_operation += cost_value
                if cost_value > 0:
                    logger.info(f"  {csv_field}: {cost_value:,.2f} 元")
                else:
                    logger.info(f"  {csv_field}: 0.00 元")

        # 处理短缺成本（特殊类别）
        shortage_cost = cost_breakdown.get('shortage_cost', 0)
        if shortage_cost > 0:
            logger.info(f"  短缺惩罚成本(元): {shortage_cost:,.2f} 元")
        else:
            logger.info(f"  短缺惩罚成本(元): 0.00 元")

        logger.info(f"运营成本小计: {total_operation:,.2f} 元")
        logger.info("")

        # 汇总信息
        total_all_costs = total_investment + total_operation
        logger.info("【成本汇总】")
        logger.info(f"总投资成本: {total_investment:,.2f} 元")
        logger.info(f"总运营成本: {total_operation:,.2f} 元")
        logger.info(f"不含短缺总成本: {total_cost_excluding_shortage:,.2f} 元")
        logger.info(f"短缺惩罚成本: {shortage_cost:,.2f} 元")
        logger.info(f"生命周期总成本: {total_cost_excluding_shortage + shortage_cost:,.2f} 元")
        logger.info(f"年化成本: {(total_cost_excluding_shortage + shortage_cost) / project_lifespan:,.2f} 元/年")
        logger.info("="*80)

        # 打印生产和设施统计信息
        logger.info("【生产与设施统计信息】")
        facilities_count = len(solution.get("facilities", {}))
        transport_routes = len(solution.get("transport_plan", {}))
        annual_production = solution.get("annual_production_kg", 0)
        lifecycle_production = solution.get("lifecycle_total_production_kg", 0)

        logger.info(f"建设设施数: {facilities_count}")
        logger.info(f"运输路线数: {transport_routes}")
        logger.info(f"年产量: {annual_production:,.0f} kg")
        logger.info(f"20年总产量: {lifecycle_production:,.0f} kg")
        logger.info(f"优化时长: {self.time_horizon_weeks} 周")
        logger.info(f"总时段数: {self.total_hours} 小时")
        logger.info(f"项目期限: {project_lifespan} 年")


        logger.info("")
        logger.info("【优化求解信息】")
        logger.info(f"求解状态: {solution.get('optimization_status', '未知')}")
        logger.info(f"求解时间: {solution.get('optimization_time', 0):.2f} 秒")
        logger.info("="*80)

        # 额外添加原本没有对应表达式对象的字段（保持原逻辑）
        results_summary.update({
            # 统计信息
            "建设设施数": [facilities_count],
            "运输路线数": [transport_routes],
            "年产量(kg)": [annual_production],
            "20年总产量(kg)": [lifecycle_production],
            "优化时长(周)": [self.time_horizon_weeks],
            "总时段数(小时)": [self.total_hours],
            "项目期限(年)": [project_lifespan]
        })
        
        # 添加直接从优化模型计算的单位成本分析指标
        # 电解制氢成本指标
        results_summary.update({
            "氢气单位电力成本(元/kg)": [unit_costs.get('hydrogen_electricity_cost_yuan_per_kg', 0)],
            "氢气设备摊销成本(元/kg)": [unit_costs.get('hydrogen_equipment_amortization_yuan_per_kg', 0)],
            "氢气运营维护成本(元/kg)": [unit_costs.get('hydrogen_operation_maintenance_yuan_per_kg', 0)],
            "氢气总单位成本(元/kg)": [unit_costs.get('hydrogen_total_production_cost_yuan_per_kg', 0)],
            "电解制氢效率(%)": [unit_costs.get('electrolysis_actual_efficiency_percent', 68.0)]
        })
        
        # MTJ生产成本指标  
        results_summary.update({
            "MTJ氢气原料成本(元/kg)": [unit_costs.get('mtj_hydrogen_raw_material_cost_yuan_per_kg', 0)],
            "MTJ CO2原料成本(元/kg)": [unit_costs.get('mtj_co2_raw_material_cost_yuan_per_kg', 0)],
            "MTJ设备摊销成本(元/kg)": [unit_costs.get('mtj_equipment_amortization_yuan_per_kg', 0)],
            "MTJ运营维护成本(元/kg)": [unit_costs.get('mtj_operation_maintenance_yuan_per_kg', 0)],
            "MTJ总单位成本(元/kg)": [unit_costs.get('mtj_total_production_cost_yuan_per_kg', 0)]
        })
        
        # 运输成本指标
        results_summary.update({
            "氢气运输单位成本(元/kg·km)": [unit_costs.get('h2_transport_unit_cost_yuan_per_kg_km', 0)],
            "MTJ运输单位成本(元/kg·km)": [unit_costs.get('mtj_transport_unit_cost_yuan_per_kg_km', 0)],
            "氢气储存单位成本(元/kg)": [unit_costs.get('h2_storage_cost_yuan_per_kg', 0)],
            "MTJ储存单位成本(元/kg)": [unit_costs.get('mtj_storage_cost_yuan_per_kg', 0)]
        })
        
        # 转化效率指标
        results_summary.update({
            "电解制氢理论效率(%)": [unit_costs.get('electrolysis_theoretical_efficiency', 80.0)],
            "电解制氢实际效率(%)": [unit_costs.get('electrolysis_actual_efficiency', 68.0)],
            "MTJ转化效率(%)": [unit_costs.get('h2_to_mtj_conversion_efficiency', 85.0)],
            "综合电力转MTJ效率(%)": [unit_costs.get('overall_electricity_to_mtj_efficiency', 68.0)],
            "单位电力消耗(MWh/kg_MTJ)": [unit_costs.get('power_consumption_mwh_per_kg_mtj', 0)]
        })
        
        # 经济性指标（从现有成本比例数据计算）
        results_summary.update({
            "氢气电力成本占比(%)": [unit_costs.get('hydrogen_electricity_cost_ratio', 0) * 100],
            "氢气设备成本占比(%)": [unit_costs.get('hydrogen_equipment_cost_ratio', 0) * 100],
            "氢气运营成本占比(%)": [unit_costs.get('hydrogen_operation_cost_ratio', 0) * 100],
            "MTJ氢气原料成本占比(%)": [unit_costs.get('mtj_hydrogen_cost_ratio', 0) * 100],
            "MTJ CO2原料成本占比(%)": [unit_costs.get('mtj_co2_cost_ratio', 0) * 100]
        })
        
        # 计算和保存碳排放结果（如果启用）
        if self.carbon_params.get('calculation_control', {}).get('enable_carbon_tracking', True):
            logger.info("="*80)
            logger.info("开始碳排放计算和报告...")
            logger.info("="*80)

            # 计算碳排放
            carbon_results = self.calculate_carbon_emissions(solution)

            # 保存碳排放报告
            if carbon_results and self.carbon_params.get('calculation_control', {}).get('save_carbon_csv', True):
                self.save_carbon_emissions_report(carbon_results, output_dir, timestamp)

            # 将碳排放结果添加到solution字典中
            solution['carbon_emissions'] = carbon_results

            # 在优化总结中添加碳排放指标
            if carbon_results:
                results_summary.update({
                    "总碳排放(kg CO2eq)": [carbon_results.get('by_stage', {}).get('total_emissions', 0)],
                    "碳强度(kg CO2eq/kg SAF)": [carbon_results.get('carbon_intensity_kg', 0)],
                    "碳强度(g CO2eq/MJ)": [carbon_results.get('carbon_intensity_mj', 0)],
                    "相比传统航煤(%)": [carbon_results.get('vs_traditional_jet', 0)],
                    "相比CORSIA标准(%)": [carbon_results.get('vs_corsia', 0)]
                })

        # 保存优化总结
        summary_df = pd.DataFrame(results_summary)
        summary_path = self._get_output_path('optimization_summary', timestamp)
        summary_df.to_csv(summary_path, index=False, encoding='utf-8-sig')
        print(f"优化总结保存到: {summary_path}")
        
        # 保存设施建设决策
        facilities_data = []
        for facility_id, info in solution.get("facilities", {}).items():
            facilities_data.append({
                "设施ID": facility_id,
                "位置": info.get("location", ""),
                "技术类型": info.get("technology", ""),
                "是否建设": info.get("built", False),
                "小时产能(kg/h)": info.get("capacity_kg_per_hour", 0),
                "年产能(kg)": info.get("max_annual_capacity_kg", 0),
                "实际年产量(kg)": info.get("actual_annual_production_kg", 0),
                "产能利用率": info.get("utilization_rate", 0),
                "位置类型": info.get("location_type", ""),
                "运输模式": info.get("transport_mode", "")
            })
        
        if facilities_data:
            facilities_df = pd.DataFrame(facilities_data)
            facilities_path = self._get_output_path('facility_decisions', timestamp)
            facilities_df.to_csv(facilities_path, index=False, encoding='utf-8-sig')
            print(f"设施决策保存到: {facilities_path}")

        # 保存运输计划
        transport_data = []
        for transport_id, info in solution.get("transport_plan", {}).items():
            transport_data.append({
                "运输ID": transport_id,
                "起点": info.get("from_location", ""),
                "终点": info.get("to_airport", ""),
                "周次": info.get("week", 0),
                "运输量(kg)": info.get("transport_kg", 0),
                "距离(km)": info.get("distance_km", 0),
                "起点纬度": info.get("from_latitude", 0),
                "起点经度": info.get("from_longitude", 0),
                "终点纬度": info.get("to_latitude", 0),
                "终点经度": info.get("to_longitude", 0),
                "运输类型": info.get("transport_type", "MTJ"),
                "运输方式": info.get("transport_mode", "truck")
            })
        
        if transport_data:
            transport_df = pd.DataFrame(transport_data)
            transport_path = os.path.join(output_dir, f"mtj_transport_plan_{timestamp}.csv")
            transport_df.to_csv(transport_path, index=False, encoding='utf-8-sig')
            print(f"MTJ运输计划保存到: {transport_path}")

        # 保存氢气运输计划
        h2_transport_data = []
        for transport_id, info in solution.get("hydrogen_transport", {}).items():
            h2_transport_data.append({
                "运输ID": transport_id,
                "起点": info.get("from_location", ""),
                "终点": info.get("to_location", ""),
                "天": info.get("day", 0),
                "氢气运输量(kg)": info.get("transport_kg_h2", 0),
                "距离(km)": info.get("distance_km", 0),
                "起点纬度": info.get("from_latitude", 0),
                "起点经度": info.get("from_longitude", 0),
                "终点纬度": info.get("to_latitude", 0),
                "终点经度": info.get("to_longitude", 0),
                "运输类型": info.get("transport_type", "H2"),
                "运输方式": info.get("transport_mode", "truck")
            })
        
        if h2_transport_data:
            h2_transport_df = pd.DataFrame(h2_transport_data)
            h2_transport_path = os.path.join(output_dir, f"hydrogen_transport_plan_{timestamp}.csv")
            h2_transport_df.to_csv(h2_transport_path, index=False, encoding='utf-8-sig')
            print(f"氢气运输计划保存到: {h2_transport_path}")

        # 保存库存信息（更新后的版本，包含坐标）
        inventory_data = []
        for inventory_id, info in solution.get("inventory", {}).items():
            inventory_data.append({
                "库存ID": inventory_id,
                "位置": info.get("location", ""),
                "小时": info.get("hour", 0),
                "库存量(kg)": info.get("inventory_kg", 0),
                "纬度": info.get("latitude", 0),
                "经度": info.get("longitude", 0)
            })
        
        if inventory_data:
            inventory_df = pd.DataFrame(inventory_data)
            inventory_path = os.path.join(output_dir, f"inventory_levels_{timestamp}.csv")
            inventory_df.to_csv(inventory_path, index=False, encoding='utf-8-sig')
            print(f"库存水平保存到: {inventory_path}")

        # 保存运输路径汇总表
        all_transport_summary = []
        
        # 添加MTJ运输路径
        for transport_id, info in solution.get("transport_plan", {}).items():
            # 序列化路径坐标为JSON字符串
            route_coords_str = json.dumps(info.get("route_coordinates", [])) if info.get("route_coordinates") else "[]"
            
            all_transport_summary.append({
                "路径ID": transport_id,
                "起点": info.get("from_location", ""),
                "终点": info.get("to_airport", ""),
                "起点类型": "生产设施",
                "终点类型": "机场",
                "距离(km)": info.get("distance_km", 0),
                "起点坐标": f"({info.get('from_latitude', 0):.4f}, {info.get('from_longitude', 0):.4f})",
                "终点坐标": f"({info.get('to_latitude', 0):.4f}, {info.get('to_longitude', 0):.4f})",
                "路径坐标": route_coords_str,  # 新增：真实路径坐标
                "货物类型": "MTJ",
                "运输方式": info.get("transport_mode", "truck"),
                "周运输量(kg)": info.get("transport_kg", 0),
                "时间单位": "周"
            })
        
        # 添加氢气运输路径
        for transport_id, info in solution.get("hydrogen_transport", {}).items():
            # 序列化路径坐标为JSON字符串
            route_coords_str = json.dumps(info.get("route_coordinates", [])) if info.get("route_coordinates") else "[]"

            cluster_info = ""
            if info.get("cluster_id") is not None:
                cluster_center = info.get("cluster_center", (0, 0))
                cluster_info = f"聚类{info.get('cluster_id')}_(中心:{cluster_center[0]:.4f},{cluster_center[1]:.4f})"

            all_transport_summary.append({
                "路径ID": transport_id,
                "起点": info.get("from_location", ""),
                "终点": info.get("to_location", ""),
                "起点类型": "氢气生产站",
                "终点类型": "MTJ工厂",
                "距离(km)": info.get("distance_km", 0),
                "聚类信息": cluster_info,
                "Layer1距离(km)": info.get("layer1_distance_km", 0),
                "Layer2距离(km)": info.get("layer2_distance_km", 0),
                "Layer3距离(km)": info.get("layer3_distance_km", 0),
                "起点坐标": f"({info.get('from_latitude', 0):.4f}, {info.get('from_longitude', 0):.4f})",
                "终点坐标": f"({info.get('to_latitude', 0):.4f}, {info.get('to_longitude', 0):.4f})",
                "路径坐标": route_coords_str,
                "货物类型": "氢气",
                "运输方式": info.get("transport_mode", "truck"),
                "周运输量(kg)": info.get("transport_kg_h2", 0),
                "时间单位": "周"
            })

        # 添加CO2运输路径（类似氢气运输）
        for transport_id, info in solution.get("co2_transport", {}).items():
            # 序列化路径坐标为JSON字符串
            route_coords_str = json.dumps(info.get("route_coordinates", [])) if info.get("route_coordinates") else "[]"

            cluster_info = ""
            if info.get("cluster_id") is not None and info.get("cluster_id") >= 0:
                cluster_center = info.get("cluster_center", (0, 0))
                cluster_info = f"CO2聚类{info.get('cluster_id')}_(中心:{cluster_center[0]:.4f},{cluster_center[1]:.4f})"
            elif info.get("is_noise"):
                cluster_info = "独立点"

            all_transport_summary.append({
                "路径ID": transport_id,
                "起点": info.get("from_location", ""),
                "终点": info.get("to_location", ""),
                "起点类型": "CO2捕获源",
                "终点类型": "MTJ工厂",
                "距离(km)": info.get("distance_km", 0),
                "聚类信息": cluster_info,
                "Layer1距离(km)": info.get("layer1_distance_km", 0),
                "Layer2距离(km)": info.get("layer2_distance_km", 0),
                "Layer3距离(km)": info.get("layer3_distance_km", 0),
                "起点坐标": f"({info.get('from_latitude', 0):.4f}, {info.get('from_longitude', 0):.4f})",
                "终点坐标": f"({info.get('to_latitude', 0):.4f}, {info.get('to_longitude', 0):.4f})",
                "路径坐标": route_coords_str,
                "货物类型": "CO2",
                "运输方式": info.get("transport_mode", "pipeline"),
                "周运输量(kg)": info.get("transport_kg_co2", 0),
                "时间单位": "周"
            })

        if all_transport_summary:
            transport_summary_df = pd.DataFrame(all_transport_summary)
            transport_summary_path = os.path.join(output_dir, f"transport_summary_{timestamp}.csv")
            transport_summary_df.to_csv(transport_summary_path, index=False, encoding='utf-8-sig')
            print(f"运输路径汇总保存到: {transport_summary_path}")
            
            # 移除对外部成本分析器的依赖
            # 详细成本分析功能已集成到 optimization_summary 方法中
            logger.info("成本分析数据已包含在优化总结中，无需独立的成本分析报告")
        
        # 保存完整的解决方案到JSON文件
        solution_path = os.path.join(output_dir, f"complete_solution_{timestamp}.json")
        with open(solution_path, 'w', encoding='utf-8') as f:
            # 使用自定义编码器处理numpy类型
            import json
            json.dump(solution, f, ensure_ascii=False, indent=2, default=str)
        print(f"完整解决方案保存到: {solution_path}")
        
        print(f"所有结果已成功保存到目录: {output_dir}")
    
    def _save_infrastructure_locations(self, output_dir: str, timestamp: str):
        """保存基础设施选点信息"""
        
        # 1. 保存可再生能源发电站信息
        renewable_data = []
        for location, info in self.locations.items():
            if info['type'] in ['solar_plant', 'wind_farm']:
                avg_generation = np.mean(info['hourly_generation']) if info['hourly_generation'] else 0
                max_generation = np.max(info['hourly_generation']) if info['hourly_generation'] else 0
                min_generation = np.min(info['hourly_generation']) if info['hourly_generation'] else 0
                renewable_data.append({
                    "位置ID": location,
                    "发电站类型": "太阳能发电站" if info['type'] == 'solar_plant' else "风电场",
                    "纬度": info['latitude'],
                    "经度": info['longitude'],
                    "装机容量(MW)": info.get('capacity_mw', 0),
                    "平均发电量(MW)": avg_generation,
                    "最大发电量(MW)": max_generation,
                    "最小发电量(MW)": min_generation,
                    "容量因子": avg_generation / info.get('capacity_mw', 1) if info.get('capacity_mw', 0) > 0 else 0,
                    "坐标": f"({info['latitude']:.4f}, {info['longitude']:.4f})"
                })

        if renewable_data:
            renewable_df = pd.DataFrame(renewable_data)
            renewable_path = os.path.join(output_dir, f"renewable_energy_plants_{timestamp}.csv")
            renewable_df.to_csv(renewable_path, index=False, encoding='utf-8-sig')
            print(f"可再生能源发电站信息保存到: {renewable_path}")

        # 2. 保存机场信息
        airport_data = []
        for location, info in self.locations.items():
            if info['type'] == 'airport':
                # 从原始airports字典获取更详细的信息
                airport_name = info.get('original_airport_name', location)
                airport_info = self.airports.get(airport_name, {})
                
                airport_data.append({
                    "位置ID": location,
                    "机场名称": airport_name,
                    "纬度": info['latitude'],
                    "经度": info['longitude'],
                    "年总需求(kg)": airport_info.get('total_fuel_kg', 0),
                    "平均周需求(kg)": airport_info.get('avg_weekly_demand_kg', 0),
                    "最大周需求(kg)": airport_info.get('max_weekly_demand_kg', 0),
                    "坐标": f"({info['latitude']:.4f}, {info['longitude']:.4f})"
                })
        
        if airport_data:
            airport_df = pd.DataFrame(airport_data)
            airport_path = os.path.join(output_dir, f"airports_{timestamp}.csv")
            airport_df.to_csv(airport_path, index=False, encoding='utf-8-sig')
            print(f"机场信息保存到: {airport_path}")
        
        # 5. 保存基础设施选点汇总
        infrastructure_summary = []
        
        # 统计各类型基础设施数量
        type_counts = {}
        for location, info in self.locations.items():
            location_type = info['type']
            type_counts[location_type] = type_counts.get(location_type, 0) + 1
            
            # 添加到汇总列表
            type_name_map = {
                'solar_plant': '太阳能发电站',
                'wind_farm': '风电场',
                'airport': '机场'
            }
            
            infrastructure_summary.append({
                "位置ID": location,
                "设施类型": type_name_map.get(location_type, location_type),
                "纬度": info['latitude'],
                "经度": info['longitude'],
                "主要参数": self._get_location_main_parameter(info),
                "坐标": f"({info['latitude']:.4f}, {info['longitude']:.4f})"
            })
        
        if infrastructure_summary:
            infrastructure_df = pd.DataFrame(infrastructure_summary)
            infrastructure_path = os.path.join(output_dir, f"infrastructure_summary_{timestamp}.csv")
            infrastructure_df.to_csv(infrastructure_path, index=False, encoding='utf-8-sig')
            print(f"基础设施汇总保存到: {infrastructure_path}")
        
        # 6. 保存选点统计信息
        selection_stats = []
        for location_type, count in type_counts.items():
            type_name_map = {
                'solar_plant': '太阳能发电站',
                'wind_farm': '风电场',
                'airport': '机场'
            }
            selection_stats.append({
                "设施类型": type_name_map.get(location_type, location_type),
                "选取数量": count,
                "类型代码": location_type
            })
        
        if selection_stats:
            stats_df = pd.DataFrame(selection_stats)
            stats_path = os.path.join(output_dir, f"infrastructure_selection_stats_{timestamp}.csv")
            stats_df.to_csv(stats_path, index=False, encoding='utf-8-sig')
            print(f"选点统计信息保存到: {stats_path}")
    
    def _get_location_main_parameter(self, location_info: dict) -> str:
        """根据位置类型获取主要参数描述"""
        location_type = location_info['type']

        if location_type in ['solar_plant', 'wind_farm']:
            capacity = location_info.get('capacity_mw', 0)
            avg_gen = np.mean(location_info['hourly_generation']) if location_info['hourly_generation'] else 0
            return f"装机{capacity}MW, 平均发电{avg_gen:.1f}MW"
        elif location_type == 'airport':
            # 这里可以添加机场的主要参数
            return "航空燃料需求"
        else:
            return "其他"

    def _analyze_supply_chain_paths(self, solution: Dict) -> Dict:
        """分析详细的供应链路径（氢气和天然气来源）"""
        logger.info("分析详细供应链路径...")
        
        supply_chain_analysis = {}
        
        # 分析每个MTJ厂址的供应链
        for facility_key, facility_info in solution['facility_decisions'].items():
            location = facility_info['location']
            technology = facility_info['technology']
            
            # 初始化该厂址的供应链分析
            facility_analysis = {
                'location': location,
                'technology': technology,
                'capacity_kg_per_hour': facility_info['capacity_kg_per_hour'],
                'hydrogen_supply_chain': {},
                'electricity_supply': {},
                'total_production_kg': 0,
                'supply_costs': {}
            }

            # 1. 分析氢气供应链
            facility_analysis['hydrogen_supply_chain'] = self._analyze_hydrogen_supply_for_location(location, solution)

            # 2. 分析电力供应（如果有可再生能源）
            facility_analysis['electricity_supply'] = self._analyze_electricity_supply_for_location(location)
            
            # 4. 计算总生产量
            total_production = 0
            for prod_key, prod_info in solution['production_schedule'].items():
                if prod_info['location'] == location and prod_info['technology'] == technology:
                    total_production += prod_info['production_kg']
            facility_analysis['total_production_kg'] = total_production
            
            # 5. 分析供应成本
            facility_analysis['supply_costs'] = self._calculate_supply_costs_for_location(location, technology, total_production)
            
            supply_chain_analysis[facility_key] = facility_analysis
        
        # 添加供应链汇总信息
        supply_chain_analysis['summary'] = self._create_supply_chain_summary(supply_chain_analysis)
        
        return supply_chain_analysis
    
    def _analyze_hydrogen_supply_for_location(self, location: str, solution: Dict) -> Dict:
        """分析指定位置的氢气供应链"""
        hydrogen_supply = {
            'supply_sources': [],
            'self_production': {},
            'external_sources': [],
            'total_hydrogen_demand_kg': 0,
            'supply_adequacy': 'sufficient'
        }
        
        # 检查是否有自产氢气能力
        if location in self.hydrogen_locations:
            # 自产氢气
            hydrogen_supply['self_production'] = {
                'has_electrolyzer': location in solution.get('hydrogen_facilities', {}),
                'electrolyzer_capacity_kg_per_hour': solution.get('hydrogen_facilities', {}).get(location, {}).get('capacity_kg_h2_per_hour', 0),
                'total_h2_production_kg': sum(
                    prod_info['h2_production_kg'] 
                    for prod_key, prod_info in solution.get('hydrogen_production', {}).items()
                    if prod_info['location'] == location
                ),
                'renewable_energy_source': self.locations[location]['type']
            }
        
        # 检查外部氢气运输（【禁用罐车运输】改为仅检查管道运输）
        external_h2_sources = []
        for h_loc in self.hydrogen_locations:
            if h_loc != location:
                # 计算从该氢气源运输的总量
                transport_amount = 0
                # 【禁用罐车运输】注释掉罐车运输提取，改为检查管道运输
                """
                for (source, dest), var in self.hydrogen_transport_vars.items():
                    if source == h_loc and dest == location and var.x > 0.01:
                        transport_amount += var.x
                """

                # 【新增】检查管道运输
                if hasattr(self, 'hydrogen_pipeline_transport_vars') and self.hydrogen_pipeline_transport_vars:
                    for (source, dest), var in self.hydrogen_pipeline_transport_vars.items():
                        if source == h_loc and dest == location and var.x > 0.01:
                            transport_amount += var.x

                if transport_amount > 0:
                    distance = self._calculate_location_distance(h_loc, location)
                    transport_cost = self._calculate_hydrogen_transport_cost_by_distance(distance)
                    external_h2_sources.append({
                        'source_location': h_loc,
                        'source_type': self.locations[h_loc]['type'],
                        'transport_amount_kg': transport_amount,
                        'transport_distance_km': distance,
                        'transport_cost_yuan_per_kg': transport_cost
                    })

        hydrogen_supply['external_sources'] = external_h2_sources

        return hydrogen_supply
    
    def _analyze_electricity_supply_for_location(self, location: str) -> Dict:
        """分析指定位置的电力供应"""
        electricity_supply = {
            'source_type': 'none',
            'renewable_capacity_mw': 0,
            'hourly_generation_profile': [],
            'annual_generation_mwh': 0,
            'capacity_factor': 0
        }
        
        location_info = self.locations[location]
        if location_info['type'] in ['solar_plant', 'wind_farm']:
            electricity_supply['source_type'] = location_info['type']
            electricity_supply['renewable_capacity_mw'] = location_info.get('capacity_mw', 0)
            
            hourly_gen = location_info.get('hourly_generation', [])
            if hourly_gen:
                electricity_supply['hourly_generation_profile'] = hourly_gen[:24]  # 展示第一天
                electricity_supply['annual_generation_mwh'] = sum(hourly_gen) * (8760 / len(hourly_gen))
                
                if electricity_supply['renewable_capacity_mw'] > 0:
                    electricity_supply['capacity_factor'] = (
                        electricity_supply['annual_generation_mwh'] / 
                        (electricity_supply['renewable_capacity_mw'] * 8760)
                    )
        
        return electricity_supply
    
    def _calculate_supply_costs_for_location(self, location: str, technology: str, total_production_kg: float) -> Dict:
        """计算指定位置的供应成本"""
        supply_costs = {
            'hydrogen_cost_yuan': 0,
            'electricity_cost_yuan': 0,
            'transport_cost_yuan': 0,
            'total_levelized_supply_cost_yuan': 0,
            'unit_levelized_supply_cost_yuan_per_kg': 0
        }

        tech_info = self.technologies[technology]
        
        # 氢气成本
        if tech_info.get('hydrogen_transport_required', False):
            h2_consumption = total_production_kg * tech_info.get('h2_consumption_ratio', 0)
            # 找最近的氢气源并计算成本
            min_h2_cost = float('inf')
            for h_loc in self.hydrogen_locations:
                distance = self._calculate_location_distance(h_loc, location)
                transport_cost = self._calculate_hydrogen_transport_cost_by_distance(distance)
                # 使用统一成本配置的氢气生产成本
                h2_production_cost = float(
                    self.config.get('unified_costs', {}).get('production', {}).get('hydrogen_internal_cost_yuan_per_kg', 0)
                )
                total_h2_cost = (h2_production_cost + transport_cost) * h2_consumption
                min_h2_cost = min(min_h2_cost, total_h2_cost)
            
            if min_h2_cost != float('inf'):
                supply_costs['hydrogen_cost_yuan'] = min_h2_cost

        # 电力成本（基于可再生能源边际成本）
        electricity_cost_yuan = 0
        
        # 如果工艺需要制氢，计算电解制氢的电力成本
        if tech_info.get('hydrogen_transport_required', False):
            h2_consumption = total_production_kg * tech_info.get('h2_consumption_ratio', 0)
            # 电解制氢耗电量 (MWh)
            electricity_consumption_mwh = h2_consumption * self.costs['electrolysis_power_consumption'] / 1000
            electricity_cost_yuan = electricity_consumption_mwh * self.costs['renewable_electricity_cost_yuan_per_mwh']
        
        supply_costs['electricity_cost_yuan'] = electricity_cost_yuan
        
        # 运输成本（到机场的平均运输成本）
        total_transport_cost = 0
        for airport in self.airports:
            distance = self._calculate_distance(location, airport)
            airport_demand = sum(self.airports[airport]['weekly_demand_series']) * 52
            transport_cost = self._calculate_mtj_transport_cost_by_distance(distance) * airport_demand
            total_transport_cost += transport_cost
        supply_costs['transport_cost_yuan'] = total_transport_cost
        
        # 总平准化供应成本
        supply_costs['total_levelized_supply_cost_yuan'] = (
            supply_costs['hydrogen_cost_yuan'] +
            supply_costs['electricity_cost_yuan'] +
            supply_costs['transport_cost_yuan']
        )
        
        if total_production_kg > 0:
            supply_costs['unit_levelized_supply_cost_yuan_per_kg'] = (
                supply_costs['total_levelized_supply_cost_yuan'] / total_production_kg
            )
        
        return supply_costs
    
    def _create_supply_chain_summary(self, supply_chain_analysis: Dict) -> Dict:
        """创建供应链汇总信息"""
        summary = {
            'total_facilities': len([k for k in supply_chain_analysis.keys() if k != 'summary']),
            'total_production_kg': 0,
            'total_levelized_supply_cost_yuan': 0,
            'avg_unit_levelized_cost_yuan_per_kg': 0,
            'hydrogen_supply_breakdown': {
                'self_production_facilities': 0,
                'external_supply_facilities': 0,
                'total_h2_production_kg': 0
            },
            'renewable_energy_breakdown': {
                'solar_facilities': 0,
                'wind_facilities': 0,
                'total_renewable_capacity_mw': 0
            }
        }
        
        for facility_key, facility_analysis in supply_chain_analysis.items():
            if facility_key == 'summary':
                continue
                
            summary['total_production_kg'] += facility_analysis['total_production_kg']
            summary['total_levelized_supply_cost_yuan'] += facility_analysis['supply_costs']['total_levelized_supply_cost_yuan']
            
            # 氢气供应统计
            if facility_analysis['hydrogen_supply_chain']['self_production'].get('has_electrolyzer', False):
                summary['hydrogen_supply_breakdown']['self_production_facilities'] += 1
                summary['hydrogen_supply_breakdown']['total_h2_production_kg'] += facility_analysis['hydrogen_supply_chain']['self_production']['total_h2_production_kg']
            
            if facility_analysis['hydrogen_supply_chain']['external_sources']:
                summary['hydrogen_supply_breakdown']['external_supply_facilities'] += 1

            # 可再生能源统计
            elec_supply = facility_analysis['electricity_supply']
            if elec_supply['source_type'] == 'solar_plant':
                summary['renewable_energy_breakdown']['solar_facilities'] += 1
                summary['renewable_energy_breakdown']['total_renewable_capacity_mw'] += elec_supply['renewable_capacity_mw']
            elif elec_supply['source_type'] == 'wind_farm':
                summary['renewable_energy_breakdown']['wind_facilities'] += 1
                summary['renewable_energy_breakdown']['total_renewable_capacity_mw'] += elec_supply['renewable_capacity_mw']
        
        if summary['total_production_kg'] > 0:
            summary['avg_unit_levelized_cost_yuan_per_kg'] = summary['total_levelized_supply_cost_yuan'] / summary['total_production_kg']
        
        return summary


    def _calculate_haversine_distance(self, lat1: float, lon1: float,
                                     lat2: float, lon2: float) -> float:
        """计算两点间的Haversine距离（公里）"""
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        return 6371 * c

    def _calculate_average_distances(self):
        """计算并更新平均运输距离统计 - 使用并行计算"""
        logger.info("开始计算平均运输距离统计 (并行模式)...")

        # 计算氢气运输平均距离（可再生能源站到MTJ工厂）
        renewable_locations = [loc for loc, info in self.locations.items()
                             if info['type'] in ['solar_plant', 'wind_farm']]
        mtj_locations = [loc for loc, info in self.locations.items()
                        if info['type'] in ['industrial_park', 'port']]

        # 限制样本数以节省时间
        renewable_sample = renewable_locations[:min(10, len(renewable_locations))]
        mtj_sample = mtj_locations[:min(10, len(mtj_locations))]

        # 生成所有位置对组合
        location_pairs = [(h_loc, mtj_loc) for h_loc in renewable_sample for mtj_loc in mtj_sample]

        if location_pairs:
            logger.info(f"使用{self.parallel_workers}个并行workers计算{len(location_pairs)}对氢气运输距离")

            # 准备并行计算的参数
            distance_args = [
                (self.routing_engine, self.locations, loc1, loc2)
                for loc1, loc2 in location_pairs
            ]

            # 使用线程池并行计算距离
            hydrogen_distances = []
            with ThreadPoolExecutor(max_workers=self.parallel_workers) as executor:
                results = list(executor.map(_calculate_distance_worker, distance_args))

                for (loc1, loc2), distance in results:
                    hydrogen_distances.append(distance)
                    # 缓存结果
                    cache_key = f"{loc1}_{loc2}"
                    self.distance_cache[cache_key] = distance
                    reverse_cache_key = f"{loc2}_{loc1}"
                    self.distance_cache[reverse_cache_key] = distance

            if hydrogen_distances:
                self.avg_hydrogen_transport_distance = np.mean(hydrogen_distances)
                logger.info(f"氢气运输平均距离: {self.avg_hydrogen_transport_distance:.1f}km "
                           f"(基于{len(hydrogen_distances)}个样本, 并行计算)")
        else:
            # 从配置文件读取默认氢气运输距离
            distance_config = self.config.get('operational_parameters', {}).get('default_transport_distances', {})
            self.avg_hydrogen_transport_distance = distance_config.get('hydrogen_transport_distance_km', 50)
            logger.warning("无法计算氢气运输平均距离，使用默认值50km")

        # 计算机场运输平均距离
        production_sample = list(self.locations.keys())[:min(15, len(self.locations))]
        airport_sample = list(self.airports.keys())[:min(10, len(self.airports))]

        # 生成所有位置对组合
        airport_pairs = [(loc, airport) for loc in production_sample for airport in airport_sample]

        if airport_pairs:
            logger.info(f"使用{self.parallel_workers}个并行workers计算{len(airport_pairs)}对机场运输距离")

            # 准备并行计算的参数
            airport_args = [
                (self.routing_engine, self.locations, loc, airport)
                for loc, airport in airport_pairs
            ]

            # 使用线程池并行计算距离
            airport_distances = []
            with ThreadPoolExecutor(max_workers=self.parallel_workers) as executor:
                results = list(executor.map(_calculate_distance_worker, airport_args))

                for (loc, airport), distance in results:
                    airport_distances.append(distance)
                    # 缓存结果
                    cache_key = f"{loc}_{airport}"
                    self.distance_cache[cache_key] = distance
                    reverse_cache_key = f"{airport}_{loc}"
                    self.distance_cache[reverse_cache_key] = distance

            if airport_distances:
                avg_airport_distance = np.mean(airport_distances)
                logger.info(f"机场运输平均距离: {avg_airport_distance:.1f}km "
                           f"(基于{len(airport_distances)}个样本, 并行计算)")

        logger.info("距离统计计算完成 (并行计算加速)")


    def _add_co2_supply_balance_constraints(self):
        """添加CO₂供应平衡约束（v3.0: 已禁用，煤炭气化路线通过CO₂库存平衡约束处理）

        v3.0变更：CO₂供应来自煤炭气化，通过_add_co2_inventory_balance_constraints()中
        的库存平衡约束直接处理，不再需要单独的周级供应平衡约束。
        """
        logger.info("v3.0煤炭气化路线不需要CO₂供应平衡约束，跳过")
        return

        # 以下代码在v3.0中不再使用（保留供参考）
        """
        约束逻辑：
        - CO₂来源：碳捕获源通过管道和罐车运输供应（周级决策）
        - CO₂去向：进入甲醇生产工厂的CO₂库存
        - 平衡约束：每周运输的总CO₂量 ≥ 该周甲醇生产所需的总CO₂量（通过库存匹配）
        """
        logger.info("添加CO₂供应平衡约束（周级）...")

        tech_key = 'green_h2_co2_to_saf'
        if tech_key not in self.technologies:
            logger.warning(f"未找到技术 {tech_key}，跳过CO₂供应平衡约束")
            return

        tech_info = self.technologies[tech_key]
        co2_consumption_ratio = tech_info.get('co2_consumption_ratio', 0)
        methanol_intermediate_ratio = tech_info.get('methanol_intermediate_ratio', 0)

        if co2_consumption_ratio <= 0 or methanol_intermediate_ratio <= 0:
            logger.warning(
                f"[调试] 技术 {tech_key} 的 CO₂ 或甲醇转化参数异常 "
                f"(co2_consumption_ratio={co2_consumption_ratio}, "
                f"methanol_intermediate_ratio={methanol_intermediate_ratio})，跳过约束"
            )
            return

        # 获取所有甲醇生产位置
        methanol_locations = []
        for tech, tech_locations in self.mtj_locations.items():
            if 'green_h2_co2' in tech:
                methanol_locations.extend(tech_locations)
        methanol_locations = list(set(methanol_locations))

        # 对每个甲醇生产位置和每周，添加CO₂供应平衡约束
        for methanol_loc in methanol_locations:
            for week in range(self.time_horizon_weeks):
                # 该周通过管道运输供应的CO₂总量（kg CO₂/week）
                co2_pipeline_supply = gp.quicksum(
                    self.co2_pipeline_transport_vars[(co2_source_id, methanol_loc)]
                    for co2_source_id in self.co2_capture_sources
                    if (co2_source_id, methanol_loc) in self.co2_pipeline_transport_vars
                )

                # 【禁用罐车运输】注释掉CO₂罐车运输供应部分
                """
                # 该周通过罐车运输供应的CO₂总量（kg CO₂/week）
                co2_truck_supply = gp.quicksum(
                    self.co2_truck_transport_vars[(co2_source_id, methanol_loc)]
                    for co2_source_id in self.co2_capture_sources
                    if (co2_source_id, methanol_loc) in self.co2_truck_transport_vars
                )
                """
                co2_truck_supply = gp.LinExpr(0)  # 【禁用罐车运输】

                # 总CO₂供应（kg CO₂/week）（【禁用罐车运输】仅管道供应）
                total_co2_supply = co2_pipeline_supply + co2_truck_supply

                # 该周进入CO₂库存的量 = 周末库存 - 周初库存
                week_start_hour = week * self.hours_per_week
                week_end_hour = (week + 1) * self.hours_per_week

                co2_inventory_inflow = (
                    self.co2_inventory_vars[(methanol_loc, week_end_hour)] -
                    self.co2_inventory_vars[(methanol_loc, week_start_hour)]
                )

                # 周内CO₂消耗量（小时级消耗累加）
                weekly_consumption = gp.quicksum(
                    self.methanol_production_vars[(methanol_loc, h)] *
                    (1.0 / methanol_intermediate_ratio) * co2_consumption_ratio
                    for h in range(week_start_hour, min(week_end_hour, self.total_hours))
                    if (methanol_loc, h) in self.methanol_production_vars
                )

                # CO₂供应平衡约束：周运输量 = 周库存增量 + 周内消耗量
                self.model.addConstr(
                    total_co2_supply == co2_inventory_inflow + weekly_consumption,
                    name=f"co2_supply_balance_{methanol_loc}_week{week}"
                )

        logger.info(f"添加了 {len(methanol_locations) * self.time_horizon_weeks} 个CO₂供应平衡约束")

    def _add_methanol_production_constraints(self):
        """添加甲醇生产约束（H₂+CO₂→甲醇，两步法第一步，小时级）

        约束逻辑：
        - 输入：氢气 + CO₂
        - 输出：甲醇（中间产物）
        - 化学计量比：从技术配置中读取
          * h2_consumption_ratio: kg H₂ / kg SAF（最终产物）
          * co2_consumption_ratio: kg CO₂ / kg SAF
          * methanol_intermediate_ratio: kg 甲醇 / kg SAF

        注意：H₂和CO₂供需平衡由库存平衡约束保证，无需额外约束
        """
        logger.info("添加甲醇生产约束（H₂+CO₂→甲醇）...")

        # 🆕 添加诊断日志
        tech_key = 'green_h2_co2_to_saf'
        logger.info(f"[诊断] 检查技术 {tech_key}...")

        if tech_key not in self.technologies:
            logger.error(f"❌ 未找到技术 {tech_key}")
            logger.error(f"   可用技术: {list(self.technologies.keys())}")
            return

        tech_info = self.technologies[tech_key]

        # 🆕 验证关键参数
        # 注意: co2_consumption_ratio 由 carbon_consumption_ratio 自动计算得出
        # carbon_consumption_ratio (kg C/kg SAF) × (44/12) = co2_consumption_ratio (kg CO₂/kg SAF)
        required_params = ['h2_consumption_ratio', 'co2_consumption_ratio', 'methanol_intermediate_ratio']
        missing_params = [p for p in required_params if p not in tech_info]
        if missing_params:
            logger.warning(f"⚠️  技术 {tech_key} 缺失参数: {missing_params}")
            logger.warning(f"   将使用默认值")

        h2_consumption_ratio = tech_info['h2_consumption_ratio']  # kg H₂ / kg SAF
        co2_consumption_ratio = tech_info['co2_consumption_ratio']  # kg CO₂ / kg SAF (由carbon_consumption_ratio计算)
        carbon_consumption_ratio = tech_info.get('carbon_consumption_ratio', co2_consumption_ratio * 12.0 / 44.0)  # kg C / kg SAF
        methanol_intermediate_ratio = tech_info['methanol_intermediate_ratio']  # kg 甲醇 / kg SAF

        logger.info(f"[参数] 技术 {tech_key} 的消耗比:")
        logger.info(f"  - 碳消耗: {carbon_consumption_ratio:.3f} kg C/kg SAF")
        logger.info(f"  - CO₂消耗: {co2_consumption_ratio:.3f} kg CO₂/kg SAF")
        logger.info(f"  - H₂消耗: {h2_consumption_ratio:.3f} kg H₂/kg SAF")

        # 获取所有甲醇生产位置
        methanol_locations = []
        for tech, tech_locations in self.mtj_locations.items():
            if 'green_h2_co2' in tech:
                methanol_locations.extend(tech_locations)
        methanol_locations = list(set(methanol_locations))

        # 🆕 诊断位置信息
        logger.info(f"[诊断] 甲醇生产位置数量: {len(methanol_locations)}")
        if len(methanol_locations) == 0:
            logger.error("❌ 没有找到甲醇生产位置！")
            logger.error(f"   mtj_locations内容: {dict((k, len(v)) for k, v in self.mtj_locations.items())}")
            logger.error("   → 检查位置类型是否匹配技术要求")
            return
        else:
            logger.info(f"   示例位置: {methanol_locations[:3]}")

        # ✅ 修复：删除过严的H₂和CO₂实时供应约束
        # 原约束要求：hydrogen_storage[(loc, hour)] >= h2_required
        #           co2_inventory[(loc, hour)] >= co2_required
        # 问题：检查的是hour时刻开始时的库存，初始库存=0会卡死hour=0的生产
        # 正确做法：由氢气库存平衡约束和CO₂库存平衡约束保证供需平衡

        logger.info("甲醇生产约束：依赖氢气和CO₂库存平衡约束保证原料供需平衡")

    def _add_saf_production_from_methanol_constraints(self):
        """添加SAF生产约束（甲醇→SAF，两步法第二步，小时级）

        约束逻辑：
        - 输入：甲醇（中间产物）
        - 输出：SAF（最终产物）
        - 化学计量比：methanol_to_saf_ratio = kg SAF / kg 甲醇

        注意：甲醇供需平衡由甲醇库存平衡约束保证，无需额外约束
        """
        logger.info("添加SAF生产约束（甲醇→SAF）...")

        # 获取green_h2_co2_to_saf技术的转化率
        tech_key = 'green_h2_co2_to_saf'
        if tech_key not in self.technologies:
            logger.warning(f"未找到技术 {tech_key}，跳过SAF生产约束")
            return

        tech_info = self.technologies[tech_key]
        methanol_to_saf_ratio = tech_info['methanol_to_saf_ratio']  # kg SAF / kg 甲醇

        # ✅ 修复：删除过严的实时甲醇供应约束
        # 原约束要求：methanol_production[(loc, hour)] >= saf_production[(loc, hour)] * (1/ratio)
        # 问题：要求甲醇实时满足SAF消耗，消除了库存缓冲作用
        # 正确做法：由甲醇库存平衡约束(_add_methanol_inventory_balance_constraints)保证供需平衡

        logger.info("SAF生产约束：依赖甲醇库存平衡约束保证甲醇供需平衡")

    def _add_methanol_inventory_balance_constraints(self):
        """添加甲醇库存平衡约束（小时级）

        约束逻辑：
        - 当前库存 = 上期库存 + 本期生产 - 本期消耗
        - 生产：methanol_production_vars (kg methanol/hour)
        - 消耗：用于SAF生产
        - 初始库存：0
        """
        logger.info("添加甲醇库存平衡约束...")

        # 获取green_h2_co2_to_saf技术的转化率
        tech_key = 'green_h2_co2_to_saf'
        if tech_key not in self.technologies:
            logger.warning(f"未找到技术 {tech_key}，跳过甲醇库存平衡约束")
            return

        tech_info = self.technologies[tech_key]
        methanol_to_saf_ratio = tech_info['methanol_to_saf_ratio']

        # 获取所有甲醇生产位置
        methanol_locations = []
        for tech, tech_locations in self.mtj_locations.items():
            if 'green_h2_co2' in tech:
                methanol_locations.extend(tech_locations)
        methanol_locations = list(set(methanol_locations))

        constraint_count = 0
        for methanol_loc in methanol_locations:
            # 初始库存约束（hour 0）
            if (methanol_loc, 0) in self.methanol_inventory_vars:
                self.model.addConstr(
                    self.methanol_inventory_vars[(methanol_loc, 0)] == 0,
                    name=f"methanol_init_inventory_{methanol_loc}"
                )
                constraint_count += 1

            # 库存平衡约束（hour 1 到 total_hours）
            for hour in range(1, self.total_hours + 1):
                if (methanol_loc, hour) not in self.methanol_inventory_vars:
                    continue

                # 上期库存
                prev_inventory = self.methanol_inventory_vars[(methanol_loc, hour - 1)]

                # 本期生产（kg methanol/hour）
                production = 0
                if (methanol_loc, hour - 1) in self.methanol_production_vars:
                    production = self.methanol_production_vars[(methanol_loc, hour - 1)]

                # 本期消耗（用于SAF生产，kg methanol/hour）
                consumption = 0
                if (methanol_loc, tech_key, hour - 1) in self.production_vars:
                    saf_prod = self.production_vars[(methanol_loc, tech_key, hour - 1)]
                    consumption = saf_prod * (1.0 / methanol_to_saf_ratio)

                # 库存平衡：当前库存 = 上期库存 + 生产 - 消耗
                self.model.addConstr(
                    self.methanol_inventory_vars[(methanol_loc, hour)] ==
                    prev_inventory + production - consumption,
                    name=f"methanol_inventory_balance_{methanol_loc}_{hour}"
                )
                constraint_count += 1

        logger.info(f"添加了 {constraint_count} 个甲醇库存平衡约束")

        # 甲醇库存非负约束，防止通过负库存透支供给
        nonneg_constraints = 0
        for methanol_loc in methanol_locations:
            for hour in range(self.total_hours + 1):
                if (methanol_loc, hour) in self.methanol_inventory_vars:
                    self.model.addConstr(
                        self.methanol_inventory_vars[(methanol_loc, hour)] >= 0,
                        name=f"methanol_inventory_nonnegative_{methanol_loc}_{hour}"
                    )
                    nonneg_constraints += 1

        logger.info(f"添加了 {nonneg_constraints} 个甲醇库存非负约束")

    def _add_co2_inventory_balance_constraints(self):
        """添加CO₂库存平衡约束（v3.1一步法：周级气化→小时级消耗）

        约束逻辑：
        - 当前库存 = 上期库存 + 本期供应 - 本期消耗
        - 供应：周级煤炭气化（coal_purchase × co2_per_kg_coal）[v3.0修改]
        - 消耗：小时级消耗（直接用于SAF生产，一步法）[v3.1修改]
        - 初始库存：0
        - 时间尺度匹配：周级煤炭气化产生CO₂，按小时均匀摊销，然后逐小时消耗
        """
        logger.info("添加CO₂库存平衡约束（v3.1煤炭气化路线，一步法）...")

        # 获取green_h2_co2_to_saf技术的化学计量比
        tech_key = 'green_h2_co2_to_saf'
        if tech_key not in self.technologies:
            logger.warning(f"未找到技术 {tech_key}，跳过CO₂库存平衡约束")
            return

        tech_info = self.technologies[tech_key]
        co2_consumption_ratio = tech_info['co2_consumption_ratio']  # kg CO₂ / kg SAF
        carbon_consumption_ratio = tech_info.get('carbon_consumption_ratio', co2_consumption_ratio * 12.0 / 44.0)  # kg C / kg SAF

        logger.info(f"[CO₂库存平衡] 碳消耗参数 (一步法):")
        logger.info(f"  - 碳消耗比: {carbon_consumption_ratio:.3f} kg C/kg SAF")
        logger.info(f"  - CO₂消耗比: {co2_consumption_ratio:.3f} kg CO₂/kg SAF")

        # 获取所有SAF生产位置（一步法：直接生产SAF，无甲醇中间步骤）
        saf_locations = []
        for tech, tech_locations in self.mtj_locations.items():
            if 'green_h2_co2' in tech:
                saf_locations.extend(tech_locations)
        saf_locations = list(set(saf_locations))

        constraint_count = 0
        for saf_loc in saf_locations:
            # 初始库存约束（hour 0）
            if (saf_loc, 0) in self.co2_inventory_vars:
                self.model.addConstr(
                    self.co2_inventory_vars[(saf_loc, 0)] == 0,
                    name=f"co2_init_inventory_{saf_loc}"
                )
                constraint_count += 1

            # 库存平衡约束（hour 1 到 total_hours）
            for hour in range(1, self.total_hours + 1):
                if (saf_loc, hour) not in self.co2_inventory_vars:
                    continue

                # 上期库存
                prev_inventory = self.co2_inventory_vars[(saf_loc, hour - 1)]

                # v3.1：本期CO₂供应（kg CO₂/hour）：煤炭气化产生
                # 周级煤炭采购 × CO₂产率 / 每周小时数 = 小时级CO₂供应
                week = (hour - 1) // self.hours_per_week
                supply = gp.LinExpr(0)
                if week < self.time_horizon_weeks:
                    if (saf_loc, week) in self.coal_purchase_vars:
                        coal_purchase_weekly = self.coal_purchase_vars[(saf_loc, week)]
                        co2_per_kg_coal = self.coal_supply.co2_per_kg_coal  # kg CO₂/kg coal
                        supply = coal_purchase_weekly * co2_per_kg_coal / float(self.hours_per_week)

                # v3.1一步法：本期CO₂消耗（直接用于SAF生产，kg CO₂/hour）
                # ✅ 修正公式：SAF产量 × CO₂消耗比
                consumption = 0
                if (saf_loc, tech_key, hour - 1) in self.production_vars:
                    saf_prod = self.production_vars[(saf_loc, tech_key, hour - 1)]  # kg SAF/hour
                    # 一步法：直接计算 CO₂消耗 = SAF产量 × CO₂消耗比
                    consumption = saf_prod * co2_consumption_ratio

                # 库存平衡：当前库存 = 上期库存 + 供应 - 消耗
                self.model.addConstr(
                    self.co2_inventory_vars[(saf_loc, hour)] ==
                    prev_inventory + supply - consumption,
                    name=f"co2_inventory_balance_{saf_loc}_{hour}"
                )
                constraint_count += 1

        logger.info(f"添加了 {constraint_count} 个CO₂库存平衡约束")

        # 【已优化】CO₂库存非负约束已通过变量下界 lb=0 实现，无需单独约束

    def _add_valid_inequalities(self):
        """添加有效不等式（Valid Inequalities）以收紧LP Relaxation

        有效不等式不改变整数可行域，但能切掉LP松弛的非整数解区域，
        从而缩小LP最优解与MIP最优解之间的Gap，加速分支定界收敛。

        精简版有效不等式（2个核心约束）：
        1. 总SAF产能下界 - 基于50%利用率估算最小产能需求
        2. 总生产量下界 - 至少满足80%的需求
        """
        logger.info("=" * 60)
        logger.info("添加有效不等式以收紧LP Relaxation（精简版）...")
        logger.info("=" * 60)

        valid_ineq_count = 0

        # ==================== 计算基础参数 ====================
        # 计算总需求
        total_demand = sum(
            sum(self.airports[airport]['weekly_demand_series'][:self.time_horizon_weeks])
            for airport in self.airports
        )
        avg_weekly_demand = total_demand / self.time_horizon_weeks if self.time_horizon_weeks > 0 else 0

        logger.info(f"需求统计: 总需求={total_demand:.0f} kg, 周均需求={avg_weekly_demand:.0f} kg/周")

        # ==================== 1. 总SAF产能下界约束 ====================
        # 所有设施的总产能必须足以满足总需求（考虑50%利用率）
        utilization_factor = 0.5  # 50%利用率
        min_total_capacity_per_hour = avg_weekly_demand / (self.hours_per_week * utilization_factor)

        total_capacity = gp.quicksum(
            self.facility_capacity_vars[(loc, tech)]
            for loc in self.locations
            for tech in self.technologies
            if (loc, tech) in self.facility_capacity_vars
        )

        self.model.addConstr(
            total_capacity >= min_total_capacity_per_hour,
            name="valid_ineq_min_total_capacity"
        )
        valid_ineq_count += 1
        logger.info(f"[有效不等式1] 总SAF产能下界: >= {min_total_capacity_per_hour:.0f} kg/h (基于50%利用率)")

        # ==================== 2. 总生产量下界约束 ====================
        # 总生产量至少满足90%的需求
        min_demand_satisfaction = 0.90  # 80%需求满足率

        total_production = gp.quicksum(
            self.production_vars[(loc, tech, hour)]
            for loc in self.locations
            for tech in self.technologies
            for hour in range(self.total_hours)
            if (loc, tech, hour) in self.production_vars
        )

        min_production = total_demand * min_demand_satisfaction

        self.model.addConstr(
            total_production >= min_production,
            name="valid_ineq_min_production"
        )
        valid_ineq_count += 1
        logger.info(f"[有效不等式3] 总生产量下界: >= {min_production:.0f} kg (总需求的80%)")

        logger.info("=" * 60)
        logger.info(f"有效不等式添加完成，共 {valid_ineq_count} 个约束")
        logger.info("=" * 60)

        return valid_ineq_count


if __name__ == '__main__':
    """主执行块"""
    try:
        logger.info("开始执行天然气供应链优化模型...")
        
        # 1. 初始化优化器 (使用1周时间范围以减少内存使用)
        # 设置正确的OSM文件路径
        base_dir = get_project_base_dir()
        osm_file_path = os.path.join(base_dir, "products", "supply_chain_optimization",
                                   "coal_hydrogen_saf_optimization", "data", "china-latest.osm.pbf")

        optimizer = CoalHydrogenSAFOptimizer(
            time_horizon_weeks=1,
            osm_pbf_path=osm_file_path
        )
        
        # 2. 加载数据
        # 使用内置的真实数据加载逻辑，无需传入额外参数
        # 使用配置文件中的路径加载数据（如果传入airport_excel_path=None，会自动从配置文件获取）
        optimizer.load_data_from_excel(
            airport_excel_path=None  # 从配置文件自动获取路径
        )

        # 2.5 运行约束诊断（在构建模型前诊断数据完整性）
        logger.info("\n" + "="*80)
        logger.info("【运行约束诊断工具】")
        logger.info("="*80)
        if ConstraintDiagnostic is not None:
            try:
                diagnostic = ConstraintDiagnostic()

                # 将优化器的内部数据转换为DataFrame格式
                # 1. 机场数据
                airports_data = pd.DataFrame([
                    {
                        'airport_name': name,
                        'total_weekly_demand_kg': data.get('avg_weekly_demand_kg', 0),  # 使用平均周需求进行诊断
                        'latitude': data.get('latitude'),
                        'longitude': data.get('longitude')
                    }
                    for name, data in optimizer.airports.items()
                ])

                logger.info(f"[诊断] 提取机场需求数据: {[(name, data.get('avg_weekly_demand_kg', 0)) for name, data in optimizer.airports.items()]}")

                # 2. CO₂捕获源数据
                co2_sources_data = pd.DataFrame([
                    {
                        'source_name': name,
                        'weekly_co2_supply_kg': data.get('co2_capture_capacity_ton_per_week', 0) * 1000,  # 吨→公斤
                        'latitude': data.get('latitude'),
                        'longitude': data.get('longitude')
                    }
                    for name, data in optimizer.co2_capture_sources.items()
                ])

                logger.info(f"[诊断] 提取CO₂供应数据: 总供应量 = {co2_sources_data['weekly_co2_supply_kg'].sum():,.0f} kg/周")

                # 3. 可再生能源发电厂数据
                renewable_plants_data = pd.DataFrame([
                    {
                        'plant_name': name,
                        'type': data.get('type', 'unknown'),
                        'hourly_generation': data.get('hourly_generation', []),
                        'latitude': data.get('latitude'),
                        'longitude': data.get('longitude')
                    }
                    for name, data in optimizer.locations.items()
                ])

                # 计算可再生能源总发电量以进行验证
                total_hourly_gen = 0
                for _, row in renewable_plants_data.iterrows():
                    if isinstance(row['hourly_generation'], (list, np.ndarray)) and len(row['hourly_generation']) > 0:
                        total_hourly_gen += sum(row['hourly_generation'][:optimizer.hours_per_week])  # 前一周小时数

                logger.info(f"准备诊断数据: {len(airports_data)}个机场, {len(co2_sources_data)}个CO₂源, {len(renewable_plants_data)}个可再生能源厂")
                logger.info(f"[诊断] 可再生能源周发电量验证: {total_hourly_gen:,.2f} MWh")

                # 运行完整诊断
                diagnostic_results = diagnostic.generate_diagnosis_report(
                    airports_data=airports_data,
                    co2_sources_data=co2_sources_data,
                    renewable_plants_data=renewable_plants_data
                )

                logger.info("约束诊断完成")
                logger.info("="*80 + "\n")

            except Exception as e:
                logger.warning(f"约束诊断工具执行失败: {e}")
                logger.warning("继续执行优化模型...")
        else:
            logger.warning("约束诊断工具不可用，跳过诊断步骤")

        # 3. 构建模型
        optimizer.build_model()
        
        # 4. 求解模型
        solution = optimizer.solve()
        
        # 5. 打印关键结果
        if solution:
            status = solution.get('optimization_status', 'unknown')
            if status != 2:  # GRB.OPTIMAL = 2
                logger.error("模型求解失败！")
                logger.error(f"  - 求解状态码: {status}")
            else:
                logger.info("模型求解成功！")
                logger.info(f"  - 求解状态: 最优解")
                objective_value_lifecycle_total = solution.get('objective_value_lifecycle_total', 'N/A')
                lifecycle_levelized_cost_per_kg = solution.get('lifecycle_levelized_cost_per_kg', 'N/A')
                annual_levelized_cost_per_kg = solution.get('annual_levelized_cost_per_kg', 'N/A')
                project_lifespan = solution.get('project_lifespan_years', 20)
                time_window_weeks = solution.get('time_window_weeks', 1)
                annual_production = solution.get('annual_production_kg', 0)
                lifecycle_total_production = solution.get('lifecycle_total_production_kg', 0)
                

                if isinstance(objective_value_lifecycle_total, (int, float)):
                    logger.info(f"  - 项目生命周期总成本（{project_lifespan}年）: {objective_value_lifecycle_total:,.2f} 元")
                    
                    annual_cost = objective_value_lifecycle_total / project_lifespan
                    logger.info(f"  - 年化成本: {annual_cost:,.2f} 元/年")
                    
                    if isinstance(lifecycle_levelized_cost_per_kg, (int, float)):
                        logger.info(f"  - 生命周期平准化成本: {lifecycle_levelized_cost_per_kg:,.2f} 元/kg")
                    
                    if isinstance(annual_levelized_cost_per_kg, (int, float)):
                        logger.info(f"  - 年化平准化成本: {annual_levelized_cost_per_kg:,.2f} 元/kg")
                    
                    if annual_production > 0:
                        logger.info(f"  - 年产量: {annual_production:,.0f} kg")
                    
                    if lifecycle_total_production > 0:
                        logger.info(f"  - 20年总产量: {lifecycle_total_production:,.0f} kg")
                        
                else:
                    logger.info(f"  - 目标函数值: {objective_value_lifecycle_total}")
                
                # 输出设施建设数量
                facilities_count = len(solution.get('facilities', {}))
                logger.info(f"  - 建设设施数量: {facilities_count}")
                logger.info(f"  - 优化时间窗口: {time_window_weeks} 周")

            # 保存结果到results目录
            base_dir = get_project_base_dir()
            results_dir = os.path.join(base_dir, "products", "supply_chain_optimization", "coal_hydrogen_saf_optimization", "results")
            os.makedirs(results_dir, exist_ok=True)
            optimizer.save_results(solution, results_dir)
            print(f"\n结果已保存到目录: {results_dir}")
            print("="*50)
        else:
            logger.error("模型求解失败或未返回结果。")

    except Exception as e:
        logger.error("="*80)
        logger.error("模型执行过程中发生严重错误")
        logger.error("="*80)
        logger.error(f"错误类型: {type(e).__name__}")
        logger.error(f"错误信息: {e}")
        logger.error(f"错误发生时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # 如果是路径规划相关的错误，记录额外信息
        if "路径规划" in str(e) or "GraphHopper" in str(e) or "route" in str(e).lower():
            logger.error("这是一个路径规划相关的错误")
            logger.error("建议检查:")
            logger.error("  1. GraphHopper服务是否正常运行 (http://localhost:8989)")
            logger.error("  2. OSM数据文件是否存在且完整")
            logger.error("  3. 坐标数据是否有效")
            logger.error("  4. 网络连接是否正常")

        logger.error("完整错误堆栈信息:")
        logger.error("-"*60, exc_info=True)
        logger.error("="*80)
