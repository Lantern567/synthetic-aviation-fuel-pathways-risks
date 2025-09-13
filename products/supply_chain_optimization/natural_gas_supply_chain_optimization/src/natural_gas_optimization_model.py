"""
天然气基供应链优化模型
基于Gurobi求解器的混合整数线性规划模型
包含时间尺度匹配：生产(1小时) vs 需求(1周)
集成OSM真实路网数据进行距离计算和路径规划
"""

import gurobipy as gp
from gurobipy import GRB
import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Tuple, Optional
import os
import json
import re
import traceback
import yaml
from datetime import datetime
try:
    from shared.utils.log_preserver import mount_file_logging
    # 移除对外部成本分析引擎的依赖，直接在优化模型内部计算成本
    create_cost_analyzer = None
except ModuleNotFoundError:
    import sys
    # 动态加入项目根目录到sys.path后重试
    current_file = os.path.abspath(__file__)
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file)))))
    if project_root not in sys.path:
        sys.path.append(project_root)
    from shared.utils.log_preserver import mount_file_logging
    # 移除对外部成本分析引擎的依赖，直接在优化模型内部计算成本
    create_cost_analyzer = None

# 导入GraphHopper路径规划模块 - 必须可用
try:
    # 尝试相对导入（当作为包使用时）
    try:
        from .graphhopper_routing_engine import GraphHopperRoutingEngine, GraphHopperDistanceCalculator, DistanceCalculator
    except ImportError:
        from graphhopper_routing_engine import GraphHopperRoutingEngine, GraphHopperDistanceCalculator, DistanceCalculator
except ImportError:
    try:
        # 尝试绝对导入（当直接运行时）
        from graphhopper_routing_engine import GraphHopperRoutingEngine, GraphHopperDistanceCalculator, DistanceCalculator
    except ImportError as e:
        raise ImportError(f"GraphHopper路径规划模块不可用，必须安装相关依赖: {e}. 请运行: pip install requests")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

def get_project_base_dir():
    """
    获取项目根目录的绝对路径
    从当前文件位置向上找到项目根目录
    
    路径结构: 
    project_root/products/supply_chain_optimization/natural_gas_supply_chain_optimization/src/natural_gas_optimization_model.py
    需要向上5级目录到达项目根目录
    
    Returns:
        str: 项目根目录路径
    """
    # 当前文件的绝对路径
    current_file = os.path.abspath(__file__)
    # 向上5级目录: src -> natural_gas_supply_chain_optimization -> supply_chain_optimization -> products -> project_root
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file)))))
    return project_root


# 在模块加载时挂载日志文件输出（仅作用于logging，不捕获print）
try:
    _base_dir = get_project_base_dir()
    _log_dir = os.path.join(
        _base_dir,
        "products",
        "supply_chain_optimization",
        "natural_gas_supply_chain_optimization",
        "results",
        "logs",
    )
    mount_file_logging(_log_dir, filename_prefix="ng_supply_chain")
except Exception:
    # 静默失败，不影响主流程
    pass

class NaturalGasSupplyChainOptimizer:
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
                                            'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results')
            
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
                                     "natural_gas_supply_chain_optimization", "results")
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
            # 使用默认配置文件路径
            project_root = get_project_base_dir()
            config_path = os.path.join(project_root, "shared", "data", "NaturalGasSupplyChainOptimizer_config.yaml")
        
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
                      'graphhopper_port', 'max_transport_distance_km', 'use_routing_for_short_distance',
                      'avg_lng_capacity_mcm_per_year']:
                new_config['basic_parameters'][key] = value
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
        for tech, tech_info in self.technologies.items():
            suitable_types = tech_info.get('suitable_locations', [])
            self.mtj_locations[tech] = [loc for loc, info in self.locations.items() if info['type'] in suitable_types]
        # 非LNG接收站的MTJ工厂位置（用于天然气运输变量）
        self.non_lng_mtj_locations = {}
        for tech, locs in self.mtj_locations.items():
            self.non_lng_mtj_locations[tech] = [loc for loc in locs if self.locations[loc]['type'] != 'lng_terminal']

    """天然气基供应链优化器"""
    
    def __init__(self, config_path: str = None, **override_params):
        """
        初始化优化器
        
        Args:
            config_path: 配置文件路径，默认使用项目内置配置文件
            **override_params: 可以通过关键字参数覆盖配置文件中的任何参数
        """
        # 加载配置文件
        self.config = self._load_config(config_path, override_params)
        
        # 从配置中获取基础参数
        basic_params = self.config['basic_parameters']
        self.time_horizon_weeks = basic_params['time_horizon_weeks']
        self.hours_per_week = basic_params['hours_per_week']
        self.total_hours = self.time_horizon_weeks * self.hours_per_week
        
        # 模型组件
        self.model = None
        self.locations = {}
        self.technologies = {}
        self.airports = {}
        self.costs = {}
        
        # 天然气基供应链专用数据
        self.ng_pipeline_sources = {}     # 天然气管段数据
        self.lng_terminals = {}           # LNG接收站数据
        
        # LNG容量平均值（从配置文件加载，在数据加载后会更新）
        self.avg_lng_capacity_mcm_per_year = basic_params['avg_lng_capacity_mcm_per_year']
        
        # 通过GraphHopper路径规划计算得出的距离统计值（用于模型中的参考）
        self.avg_hydrogen_transport_distance = None  # 将通过GraphHopper路径规划计算得出
        self.avg_ng_transport_distance = None  # 将通过GraphHopper路径规划计算得出
        
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
                                           "natural_gas_supply_chain_optimization", "data", "china-latest.osm.pbf")
        else:
            self.osm_pbf_path = osm_pbf_path
            
        if self.use_graphhopper_routing:
            # 创建缓存目录 - 使用shared/data/cache路径
            cache_dir = os.path.join(get_project_base_dir(), "shared", "data", "cache", "graphhopper_routes")
            
            self.routing_engine = GraphHopperRoutingEngine(
                osm_pbf_path=self.osm_pbf_path,
                graphhopper_host=basic_params['graphhopper_host'],
                graphhopper_port=basic_params['graphhopper_port'],
                cache_dir=cache_dir,
                enable_cache=True
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
        
        # 加载天然气供应链数据
        self._load_ng_pipeline_data()
        self._load_lng_terminal_data()
        
        # 处理可再生能源数据（在机场和LNG数据加载后，这样可以在_process_renewable_data中添加所有位置类型）
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

        logger.info(f"数据加载完成: {len(self.locations)}个生产地点, {len(self.airports)}个机场, {len(self.ng_pipeline_sources)}条天然气管段, {len(self.lng_terminals)}个LNG接收站")
    
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
        
        # 如果没有提供可再生能源数据，必须加载真实数据
        if renewable_data is None:
            renewable_data = self._load_real_renewable_data()
        
        # 处理机场数据  
        self._process_airport_data(airport_data)
        
        # 加载天然气供应链数据  
        self._load_ng_pipeline_data()
        self._load_lng_terminal_data()
        
        # 处理可再生能源数据（在机场和LNG数据加载后，这样可以在_process_renewable_data中添加所有位置类型）
        self._process_renewable_data(renewable_data)
        
        # 首先定义经济参数（平准化成本计算需要）
        self._define_economic_parameters()
        
        # 定义成本参数（使用平准化成本方法）
        self._define_costs()
        
        # 定义生产技术（使用平准化成本）
        self._define_technologies()

        # 定义运输相关的位置映射
        self._define_transport_locations()

        logger.info(f"数据加载完成: {len(self.locations)}个生产地点, {len(self.airports)}个机场, {len(self.ng_pipeline_sources)}条天然气管段, {len(self.lng_terminals)}个LNG接收站")
    
    def _process_renewable_data(self, renewable_data: pd.DataFrame):
        """处理可再生能源数据（包含太阳能和风能，支持缓存）"""
        try:
            # 导入缓存管理器
            try:
                from .data_cache_manager import cache_manager
            except ImportError:
                from data_cache_manager import cache_manager
            
            # 为可再生能源数据创建临时文件路径用于缓存检查
            # （因为renewable_data是内存中的DataFrame，我们使用数据摘要作为标识）
            renewable_cache_key = f"renewable_{len(renewable_data)}_{renewable_data['plant_name'].nunique()}"
            temp_renewable_file = f"temp_renewable_{renewable_cache_key}.csv"
            
            # 检查是否有缓存
            if cache_manager.is_cache_valid('renewable_plants', temp_renewable_file):
                logger.info("使用缓存的可再生能源数据（500km过滤）")
                cached_df = cache_manager.load_filtered_data('renewable_plants')
                if cached_df is not None:
                    filtered_renewable_data = cached_df
                    logger.info(f"从缓存加载可再生能源数据: {len(filtered_renewable_data)} 条记录")
                else:
                    logger.warning("缓存加载失败，执行完整处理")
                    filtered_renewable_data = self._filter_renewable_data(renewable_data, cache_manager, temp_renewable_file)
            else:
                logger.info("缓存无效或不存在，执行完整处理和过滤")
                filtered_renewable_data = self._filter_renewable_data(renewable_data, cache_manager, temp_renewable_file)
            
            # 按地点聚合小时级发电数据
            plant_names = filtered_renewable_data['plant_name'].unique()
            for plant_name in plant_names:
                plant_data = filtered_renewable_data[filtered_renewable_data['plant_name'] == plant_name]
                
                # 取前total_hours小时数据
                if len(plant_data) >= self.total_hours:
                    hourly_data = plant_data.head(self.total_hours)
                    
                    # 确定电站类型
                    plant_type = hourly_data.iloc[0]['type'] if 'type' in hourly_data.columns else 'solar_plant'
                    
                    self.locations[plant_name] = {
                        'type': plant_type,  # 'solar_plant' 或 'wind_farm'
                        'latitude': hourly_data.iloc[0].get('latitude', 30.0),
                        'longitude': hourly_data.iloc[0].get('longitude', 104.0),
                        'capacity_mw': hourly_data.iloc[0]['capacity_mw'] if 'capacity_mw' in hourly_data.columns else hourly_data.iloc[0]['power_output_mw'],
                        'hourly_generation': hourly_data['power_output_mw'].tolist(),  # 每小时发电量 MWh (等价于平均功率 MW)
                    }
            
            logger.info(f"处理了 {len(self.locations)} 个可再生能源发电站")
            
            # 统计电站类型
            solar_count = sum(1 for loc in self.locations.values() if loc['type'] == 'solar_plant')
            wind_count = sum(1 for loc in self.locations.values() if loc['type'] == 'wind_farm')
            logger.info(f"  太阳能发电站: {solar_count} 个")
            logger.info(f"  风电场: {wind_count} 个")
            
            # 将机场位置添加到基础locations中
            self._add_airports_to_locations()
            
            # 将LNG接收站位置添加到基础locations中  
            self._add_lng_terminals_to_locations()
            
            # 将天然气管道位置添加到基础locations中
            self._add_ng_pipelines_to_locations()
        
        except Exception as e:
            logger.error(f"处理可再生能源数据失败: {e}")
            # 降级到原有处理方法
            self._process_renewable_data_fallback(renewable_data)
    
    def _filter_renewable_data(self, renewable_data: pd.DataFrame, cache_manager, temp_file: str) -> pd.DataFrame:
        """过滤可再生能源数据（500km范围内）"""
        logger.info(f"过滤可再生能源数据: {len(renewable_data)} 条原始记录")
        
        # 按电站分组过滤
        filtered_plants = []
        for plant_name in renewable_data['plant_name'].unique():
            plant_data = renewable_data[renewable_data['plant_name'] == plant_name]
            
            if len(plant_data) > 0:
                # 获取电站坐标（使用第一行数据）
                plant_lat = plant_data.iloc[0].get('latitude', 30.0)
                plant_lon = plant_data.iloc[0].get('longitude', 104.0)
                
                # 检查坐标是否在北京500公里范围内
                if is_within_beijing_range(plant_lat, plant_lon, 500):
                    filtered_plants.append(plant_data)
                else:
                    distance = calculate_distance_km(plant_lat, plant_lon, 39.9042, 116.4074)
                    logger.debug(f"可再生能源电站 {plant_name} 距离北京 {distance:.1f}km，超出500km范围，跳过")
        
        # 合并过滤后的数据
        if filtered_plants:
            filtered_df = pd.concat(filtered_plants, ignore_index=True)
        else:
            filtered_df = pd.DataFrame()
        
        logger.info(f"500km范围内的可再生能源数据: {len(filtered_df)} 条记录，{filtered_df['plant_name'].nunique() if len(filtered_df) > 0 else 0} 个电站")
        
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
                
                # 检查坐标是否在北京500公里范围内
                plant_lat = hourly_data.iloc[0].get('latitude', 30.0)
                plant_lon = hourly_data.iloc[0].get('longitude', 104.0)
                
                if not is_within_beijing_range(plant_lat, plant_lon, 500):
                    distance = calculate_distance_km(plant_lat, plant_lon, 39.9042, 116.4074)
                    logger.info(f"可再生能源电站 {plant_name} 距离北京 {distance:.1f}km，超出500km范围，跳过")
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
        
        # 将LNG接收站位置添加到基础locations中  
        self._add_lng_terminals_to_locations()
        
        # 将天然气管道位置添加到基础locations中
        self._add_ng_pipelines_to_locations()
    
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
                    'hourly_generation': [0] * self.total_hours,  # 无发电
                    'original_airport_name': airport_name,  # 保留原始机场名称
                    'fuel_demand_weekly': airport_info.get('weekly_fuel_series', [])
                }
            
            airport_count = sum(1 for loc in self.locations.values() if loc['type'] == 'airport')
            logger.info(f"  添加了 {airport_count} 个机场位置到基础locations中")
        else:
            logger.warning("机场数据尚未加载，无法添加机场位置")
    
    def _add_lng_terminals_to_locations(self):
        """将LNG接收站位置添加到基础locations字典中，使其可以用于决策变量"""
        if hasattr(self, 'lng_terminals') and self.lng_terminals:
            for terminal_id, terminal_info in self.lng_terminals.items():
                # 使用LNG接收站标识符作为位置标识符
                location_id = f"lng_{terminal_id}"
                
                # 检查坐标有效性
                lat = terminal_info.get('lat', None)
                lon = terminal_info.get('lon', None)
                
                if lat is None or lon is None or pd.isna(lat) or pd.isna(lon):
                    logger.error(f"LNG终端 {terminal_id} 缺少有效坐标信息，跳过")
                    continue
                
                try:
                    lat = float(lat)
                    lon = float(lon)
                except (ValueError, TypeError):
                    logger.error(f"LNG终端 {terminal_id} 坐标转换失败，跳过")
                    continue
                
                # 添加到基础locations字典
                self.locations[location_id] = {
                    'type': 'lng_terminal',  # 新的位置类型
                    'latitude': lat,
                    'longitude': lon,
                    'capacity_mw': 0,  # LNG接收站本身不发电
                    'hourly_generation': [0] * self.total_hours,  # 无发电
                    'original_terminal_id': terminal_id,  # 保留原始接收站ID
                    'lng_capacity': terminal_info.get('capacity_mcm_per_year', self.avg_lng_capacity_mcm_per_year) if not pd.isna(terminal_info.get('capacity_mcm_per_year', self.avg_lng_capacity_mcm_per_year)) else self.avg_lng_capacity_mcm_per_year  # LNG处理能力
                }
                
            lng_count = sum(1 for loc in self.locations.values() if loc['type'] == 'lng_terminal')
            logger.info(f"  添加了 {lng_count} 个LNG接收站位置到基础locations中")
        else:
            logger.warning("LNG接收站数据尚未加载，无法添加LNG位置")
    
    def _add_ng_pipelines_to_locations(self):
        """将天然气管道位置添加到基础locations字典中，使其可以用于决策变量"""
        if hasattr(self, 'ng_pipeline_sources') and self.ng_pipeline_sources:
            for pipeline_id, pipeline_info in self.ng_pipeline_sources.items():
                # 使用天然气管道标识符作为位置标识符
                location_id = f"ng_pipeline_{pipeline_id}"
                
                # 检查坐标有效性
                lat = pipeline_info.get('lat', None)
                lon = pipeline_info.get('lon', None)
                
                if lat is None or lon is None or pd.isna(lat) or pd.isna(lon):
                    logger.error(f"天然气管道 {pipeline_id} 缺少有效坐标信息，跳过")
                    continue
                
                try:
                    lat = float(lat)
                    lon = float(lon)
                except (ValueError, TypeError):
                    logger.error(f"天然气管道 {pipeline_id} 坐标转换失败，跳过")
                    continue
                
                # 添加到基础locations字典
                self.locations[location_id] = {
                    'type': 'ng_pipeline',  # 新的位置类型
                    'latitude': lat,
                    'longitude': lon,
                    'capacity_mw': 0,  # 天然气管道本身不发电
                    'hourly_generation': [0] * self.total_hours,  # 无发电
                    'pipeline_id': pipeline_id,  # 保留原始管道ID
                    'pipeline_name': pipeline_info.get('name', ''),  # 管道名称
                    'operator': pipeline_info.get('operator', ''),  # 运营商
                    'capacity_mcm_per_day': pipeline_info.get('capacity', 0)  # 输送能力
                }
                
            pipeline_count = sum(1 for loc in self.locations.values() if loc['type'] == 'ng_pipeline')
            logger.info(f"  添加了 {pipeline_count} 个天然气管道位置到基础locations中")
        else:
            logger.warning("天然气管道数据尚未加载，无法添加管道位置")
    
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
    
    
    def _load_real_renewable_data(self) -> pd.DataFrame:
        """
        加载真实的可再生能源数据
        
        Returns:
            可再生能源数据DataFrame
        """
        logger.info("加载真实的可再生能源数据...")
        
        # 从配置文件获取数据目录路径
        try:
            wind_data_dir = self._get_data_path('aviation_data.wind_data_dir')
            solar_data_dir = self._get_data_path('aviation_data.solar_data_dir')
            logger.info(f"从配置文件获取数据目录 - 风电: {wind_data_dir}, 光伏: {solar_data_dir}")
        except Exception as e:
            logger.error(f"从配置文件获取数据目录失败: {e}")
            # 使用默认相对路径
            base_dir = get_project_base_dir()
            wind_data_dir = os.path.join(base_dir, "products", "aviation_fuel_analysis", "resource_flight_data_process", "results", "3hourly_generation")
            solar_data_dir = os.path.join(base_dir, "products", "aviation_fuel_analysis", "resource_flight_data_process", "results", "solar_generation")
            logger.info(f"使用默认数据目录 - 风电: {wind_data_dir}, 光伏: {solar_data_dir}")
        
        # 检查数据目录是否存在
        if not os.path.exists(wind_data_dir):
            logger.error(f"风电数据目录不存在: {wind_data_dir}")
            raise FileNotFoundError(f"无法找到风电数据目录: {wind_data_dir}")
        
        if not os.path.exists(solar_data_dir):
            logger.error(f"光伏数据目录不存在: {solar_data_dir}")
            raise FileNotFoundError(f"无法找到光伏数据目录: {solar_data_dir}")
        
        # 读取风电数据
        wind_data = self._load_wind_data(wind_data_dir)
        
        # 读取光伏数据
        solar_data = self._load_solar_data(solar_data_dir)
        
        # 合并数据
        renewable_data = pd.concat([wind_data, solar_data], ignore_index=True)
        
        logger.info(f"成功加载了 {len(renewable_data)} 条可再生能源数据记录")
        
        return renewable_data
    
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
                
                # 筛选2024年数据
                df = df[df['timestamp'].dt.year == 2024]
                
                # 筛选前2周数据
                df = df[df['timestamp'] < '2024-01-15']
                
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
        
        # 读取第一个月的所有批次文件
        all_files = os.listdir(solar_data_dir)
        month01_files = [f for f in all_files if f.startswith('solar_generation_month01_batch_') and f.endswith('.csv')]
        month01_files.sort()  # 按批次顺序排序
        
        logger.info(f"找到 {len(month01_files)} 个第一个月的批次文件")
        
        for file_name in month01_files:
            file_path = os.path.join(solar_data_dir, file_name)
            try:
                df = pd.read_csv(file_path)
                
                # 数据预处理
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                
                # 检查数据的年份（应该是2020年1月）
                available_years = df['timestamp'].dt.year.unique()
                logger.info(f"文件 {file_name} 包含年份: {sorted(available_years)}")
                
                # 使用2020年1月的数据（第一个月的完整数据）
                base_year = min(available_years)
                start_date = f"{base_year}-01-01"
                end_date = f"{base_year}-02-01"  # 整个1月
                
                df_filtered = df[(df['timestamp'] >= start_date) & (df['timestamp'] < end_date)].copy()
                
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
                
                # 只保留前336小时（2周），如果数据超过这个范围
                df_processed = df_processed[df_processed['hour'] < self.total_hours]
                
                logger.info(f"文件 {file_name} 处理后得到 {len(df_processed)} 条记录")
                solar_data_list.append(df_processed)
                
            except Exception as e:
                logger.warning(f"读取光伏文件 {file_name} 失败: {e}")
        
        if solar_data_list:
            solar_data = pd.concat(solar_data_list, ignore_index=True)
            logger.info(f"成功加载 {len(solar_data)} 条光伏数据，来自 {len(month01_files)} 个批次文件")
            
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
        """处理机场周时间序列数据"""
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
            
            # 按机场分组处理数据
            for airport_name in excel_df['departure_airport_name'].unique():
                airport_df = excel_df[excel_df['departure_airport_name'] == airport_name].sort_values('week_number')
                
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
                
                self.airports[airport_name] = {
                    'latitude': latitude,
                    'longitude': longitude, 
                    'weekly_demand_series': weekly_series,  # 52周的真实需求序列
                    'avg_weekly_demand_kg': avg_weekly_demand,
                    'max_weekly_demand_kg': max_weekly_demand,
                    'total_annual_demand_kg': total_annual_demand,
                    'flight_count': total_flights
                }
                
                logger.info(f"处理机场 {airport_name}: {len(weekly_series)} 周真实数据，年需求 {total_annual_demand:,.0f} kg")
                
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
            if info['type'] in ['solar_plant', 'wind_farm']
        ]
        
        # 机场位置（统一从locations获取）
        self.airport_locations = [
            loc for loc, info in self.locations.items() 
            if info['type'] == 'airport'
        ]
        
        # LNG接收站位置（统一从locations获取）
        self.lng_terminal_locations = [
            loc for loc, info in self.locations.items() 
            if info['type'] == 'lng_terminal'
        ]
        
        # 天然气来源位置（管道接入点）
        self.ng_locations = []
        for i, (pipeline_id, pipeline_data) in enumerate(self.ng_pipeline_sources.items()):
            ng_location_name = f"ng_pipeline_{i}"
            
            # 优先使用已计算的中心坐标
            lat = pipeline_data.get('center_latitude', pipeline_data.get('lat', None))
            lon = pipeline_data.get('center_longitude', pipeline_data.get('lon', None))
            
            # 如果中心坐标缺失或为NaN，尝试从起点终点坐标计算
            if pd.isna(lat) or lat is None or pd.isna(lon) or lon is None:
                start_lat = pipeline_data.get('start_latitude', None)
                start_lon = pipeline_data.get('start_longitude', None)
                end_lat = pipeline_data.get('end_latitude', None)
                end_lon = pipeline_data.get('end_longitude', None)
                
                # 如果起点终点坐标都有效，计算中心坐标
                if (not pd.isna(start_lat) and not pd.isna(start_lon) and 
                    not pd.isna(end_lat) and not pd.isna(end_lon) and
                    start_lat is not None and start_lon is not None and
                    end_lat is not None and end_lon is not None):
                    try:
                        lat = (float(start_lat) + float(end_lat)) / 2
                        lon = (float(start_lon) + float(end_lon)) / 2
                        logger.info(f"管道 {pipeline_id} 使用起点终点坐标计算中心坐标: ({lat:.6f}, {lon:.6f})")
                    except (ValueError, TypeError):
                        logger.error(f"管道 {pipeline_id} 起点终点坐标转换失败: start_lat={start_lat}, start_lon={start_lon}, end_lat={end_lat}, end_lon={end_lon}")
                        continue  # 跳过这个管道
                else:
                    logger.error(f"管道 {pipeline_id} 缺少有效的坐标信息: center_lat={lat}, center_lon={lon}, start_lat={start_lat}, start_lon={start_lon}, end_lat={end_lat}, end_lon={end_lon}")
                    continue  # 跳过这个管道
            
            # 检查坐标是否仍然无效
            if pd.isna(lat) or lat is None or pd.isna(lon) or lon is None:
                logger.error(f"管道 {pipeline_id} 无法获取有效坐标，跳过此管道")
                continue
            
            # 确保坐标是有效的数值
            try:
                lat = float(lat)
                lon = float(lon)
                
                # 验证坐标是否在合理范围内（中国境内）
                if not (18 <= lat <= 54 and 73 <= lon <= 135):
                    logger.error(f"管道 {pipeline_id} 坐标超出中国范围 ({lat}, {lon})，跳过此管道")
                    continue
                
            except (ValueError, TypeError):
                logger.error(f"管道 {pipeline_id} 坐标转换失败，跳过此管道")
                continue
            
            self.ng_locations.append(ng_location_name)
            
            # 将天然气管道位置添加到locations字典中
            self.locations[ng_location_name] = {
                'type': 'ng_pipeline',
                'latitude': lat,
                'longitude': lon,
                'capacity_mw': 0,  # 管道本身不发电
                'hourly_generation': [0] * self.total_hours,  # 无发电
                'pipeline_id': pipeline_id,
                'pipeline_name': pipeline_data.get('name', f'管道{i+1}'),
                'operator': pipeline_data.get('operator', '未知'),
                'capacity_mcm_per_day': pipeline_data.get('capacity_mcm_per_day', 0)
            }
        
        # 所有可用于建设MTJ工厂的位置（现在统一从self.locations中获取）
        # 每种技术的适用位置由技术定义中的suitable_locations决定，不需要单独的mtj_locations映射
        
        logger.info(f"定义了运输位置映射:")
        logger.info(f"  氢气生产位置: {len(self.hydrogen_locations)} 个")
        logger.info(f"  机场位置: {len(self.airport_locations)} 个") 
        logger.info(f"  LNG接收站位置: {len(self.lng_terminal_locations)} 个")
        logger.info(f"  天然气管道位置: {len(self.ng_locations)} 个")
        logger.info(f"  总位置数: {len(self.locations)} 个")
 
    
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
        
        # 检查是否是天然气管道（需要从管道数据中获取）
        if location.startswith('ng_pipeline_'):
            pipeline_idx = int(location.split('_')[-1])
            if pipeline_idx < len(self.ng_pipeline_sources):
                pipeline_id = list(self.ng_pipeline_sources.keys())[pipeline_idx]
                pipeline_data = self.ng_pipeline_sources[pipeline_id]
                # 尝试获取有效坐标
                lat = pipeline_data.get('lat', None)
                lon = pipeline_data.get('lon', None)
                if lat is not None and lon is not None and not pd.isna(lat) and not pd.isna(lon):
                    try:
                        return (float(lat), float(lon))
                    except (ValueError, TypeError):
                        pass
                # 如果没有有效坐标，抛出错误
                raise ValueError(f"管道 {pipeline_id} 缺少有效坐标信息")
        
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
        
        for tech_key in ['pipeline_direct_conversion', 'airport_integrated_conversion', 
                        'lng_terminal_conversion', 'lng_to_hplant_conversion', 
                        'integrated_supply_conversion']:
            if tech_key in tech_config:
                tech_info = tech_config[tech_key]
                self.technologies[tech_key] = {
                    'name': tech_info['name'],
                    'lcop_yuan_per_kg': base_lcop * complexity_factors[tech_key],
                    'efficiency': tech_info['efficiency'],
                    'ng_consumption_ratio': tech_info['ng_consumption_ratio'],
                    'h2_consumption_ratio': tech_info['h2_consumption_ratio'],
                    'methanol_intermediate_ratio': tech_info['methanol_intermediate_ratio'],
                    'suitable_locations': tech_info['suitable_locations'],
                    'transport_mode': tech_info['transport_mode'],
                    'hydrogen_transport_required': tech_info['hydrogen_transport_required'],
                    'technology_type': tech_info['technology_type'],
                    'complexity_factor': complexity_factors[tech_key]
                }
        
        logger.info(f"定义了 {len(self.technologies)} 种MTJ航煤生产技术")
        logger.info(f"基础平准化成本: {base_lcop:.0f} 元/kg")
        
        # 检查技术参数中的NaN值
        for tech, config in self.technologies.items():
            logger.info(f"  {config['name']}: {config['lcop_yuan_per_kg']:,.0f} 元/kg (复杂度因子: {config['complexity_factor']:.2f})")
            
            # 检查每个技术配置中的数值参数
            for param, value in config.items():
                if isinstance(value, (int, float)) and pd.isna(value):
                    print(f"ERROR: 技术 {tech} 的参数 {param} 包含NaN值: {value}")
                    raise ValueError(f"技术参数包含NaN值: {tech}.{param} = {value}")
    
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
        
        self.economic_params = {
            'discount_rate': economic_config['discount_rate'],
            'project_lifespan': economic_config['project_lifespan'],
            'mtj_plant_lifetime': economic_config['mtj_plant_lifetime'],
            'electrolyzer_lifetime': economic_config['electrolyzer_lifetime'],
            'pipeline_lifetime': economic_config['pipeline_lifetime'],
            'storage_lifetime': economic_config['storage_lifetime'],
            'transport_vehicle_lifetime': economic_config['transport_vehicle_lifetime'],
            
            # 容量因子 (设备年利用率)
            'mtj_plant_capacity_factor': capacity_factors['mtj_plant_capacity_factor'],
            'electrolyzer_capacity_factor': capacity_factors['electrolyzer_capacity_factor'],
            'pipeline_capacity_factor': capacity_factors['pipeline_capacity_factor'],
            'storage_capacity_factor': capacity_factors['storage_capacity_factor'],
            'transport_capacity_factor': capacity_factors['transport_capacity_factor']
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
            # 优先使用统一成本配置，向后兼容原有配置
            'natural_gas_price_yuan_per_m3': (
                cost_config.get('unified_costs', {}).get('raw_materials', {}).get('natural_gas_base_price_yuan_per_m3') or
                cost_config['raw_materials']['natural_gas_price_yuan_per_m3']
            ),
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
            'natural_gas_price_yuan_per_m3': raw_costs['natural_gas_price_yuan_per_m3'],
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
        # 从配置文件加载求解器参数
        solver_params = self.config['solver_parameters']
        self.model.setParam('TimeLimit', solver_params['TimeLimit'])
        self.model.setParam('MIPGap', solver_params['MIPGap'])
        self.model.setParam('Threads', solver_params['Threads'])

        # 构建MTJ工厂位置映射（依赖locations和technologies）
        self._build_mtj_locations()
        # 创建决策变量
        self._create_variables()
        
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
        for location in self.locations:
            for tech in self.technologies:
                var_name = f"capacity_{location}_{tech}"
                self.facility_capacity_vars[(location, tech)] = self.model.addVar(
                    lb=0, ub=self.config.get('capacity_limits', {}).get('mtj_max_capacity_kg_per_hour', 10000), 
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
        self.hydrogen_transport_vars = {}  # 氢气运输量 (kg H2/week)
        
        # 7. 天然气运输决策变量 (从管道到MTJ工厂，罐车运输)  
        self.ng_transport_vars = {}  # 天然气运输量 (m³/day)
        
        for location in self.locations:
            location_type = self.locations[location]['type']
            # 只在可再生能源地点创建制氢变量
            if location_type in ['solar_plant', 'wind_farm']:
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
        
        # 8. 创建氢气运输变量 (仅为需要氢气运输的模式，无距离限制)
        logger.info("创建氢气运输变量，无距离限制")
        
        valid_h2_routes = 0  # 计数有效路线
        for h2_loc in self.hydrogen_locations:
            for tech in ['airport_integrated_conversion', 'lng_terminal_conversion', 'integrated_supply_conversion']:
                # 排除管段直供和LNG转运模式，因为它们在可再生能源站就地制备MTJ，氢气无需运输
                if tech not in self.technologies:
                    logger.warning(f"技术 {tech} 不在 technologies 中，跳过氢气运输变量创建")
                    continue
                    
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
        
        # 9. 创建天然气运输变量 (从管道到所有非LNG接收站的MTJ工厂，改为天级罐车运输，无距离限制)
        logger.info("创建天然气罐车运输变量，无距离限制")
        
        valid_ng_routes = 0  # 计数有效路线
        total_days = self.total_hours // 24
        for ng_loc in self.ng_locations:
            for tech in ['pipeline_direct_conversion', 'airport_integrated_conversion', 'lng_to_hplant_conversion', 'integrated_supply_conversion']:
                for mtj_loc in self.non_lng_mtj_locations[tech]:
                    # 不再检查距离限制，允许所有路径
                    valid_ng_routes += 1
                    for day in range(total_days): # 改为天级
                        var_name = f"ng_transport_{ng_loc}_{mtj_loc}_day_{day}"
                        self.ng_transport_vars[(ng_loc, mtj_loc, day)] = self.model.addVar(
                                lb=0, ub=GRB.INFINITY, vtype=GRB.CONTINUOUS, name=var_name
                            )
        
        logger.info(f"创建了 {valid_ng_routes} 条天然气运输路线（无距离限制）")
        
        # 10. 创建氢能管道运输变量 (与罐车运输并行的选择方案)
        logger.info("创建氢能管道运输变量，作为罐车运输的替代选择")
        
        self.hydrogen_pipeline_transport_vars = {}  # 氢能管道运输变量 (kg H2/week)
        self.hydrogen_pipeline_facility_vars = {}   # 氢能管道建设决策变量 (二进制)
        
        valid_pipeline_routes = 0  # 计数有效管道路线
        total_days = self.total_hours // 24
        
        for h2_loc in self.hydrogen_locations:
            for tech in ['airport_integrated_conversion', 'lng_terminal_conversion', 'integrated_supply_conversion']:
                # 只为需要氢气运输的技术路线创建管道变量
                if tech not in self.technologies:
                    continue
                    
                if not self.technologies[tech]['hydrogen_transport_required']:
                    continue
                    
                if tech not in self.mtj_locations:
                    continue
                    
                locations = self.mtj_locations[tech]
                if not hasattr(locations, '__iter__') or isinstance(locations, str):
                    continue
                
                for mtj_loc in locations:
                    # 管道建设决策变量 (每条路线一个二进制变量)
                    pipeline_facility_name = f"h2_pipeline_facility_{h2_loc}_{mtj_loc}"
                    self.hydrogen_pipeline_facility_vars[(h2_loc, mtj_loc)] = self.model.addVar(
                        vtype=GRB.BINARY, name=pipeline_facility_name
                    )
                    
                    # 管道运输量变量 (天级)
                    valid_pipeline_routes += 1
                    # 氢能管道运输变量改为周级
                    var_name = f"h2_pipeline_transport_{h2_loc}_{mtj_loc}_week"
                    self.hydrogen_pipeline_transport_vars[(h2_loc, mtj_loc)] = self.model.addVar(
                        lb=0, ub=GRB.INFINITY, vtype=GRB.CONTINUOUS, name=var_name
                    )
        
        logger.info(f"创建了 {valid_pipeline_routes} 条氢能管道运输路线")
        logger.info(f"创建了 {len(self.hydrogen_pipeline_facility_vars)} 个氢能管道建设决策变量")
        
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
        logger.info(f"创建了 {len(self.hydrogen_transport_vars)} 个氢气罐车运输变量")
        logger.info(f"创建了 {len(self.hydrogen_pipeline_transport_vars)} 个氢能管道运输变量")
        logger.info(f"创建了 {len(self.ng_transport_vars)} 个天然气运输变量")
    
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
        
        # 10. 天然气运输约束
        self._add_natural_gas_transport_constraints()
    
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
                M = self.config.get('capacity_limits', {}).get('big_m_constant', 10000)  # 大M常数
                self.model.addConstr(
                    self.facility_capacity_vars[(location, tech)] <= 
                    M * self.facility_vars[(location, tech)],
                    name=f"capacity_facility_link_{location}_{tech}"
                )
                
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

                if h2_demand.size() > 0:  # 只有当确实有氢气需求时才添加约束
                    if location_type in ['solar_plant', 'wind_farm']:
                        # 可再生能源站：氢气需求不能超过氢气库存
                        if (location, hour) in self.hydrogen_storage_vars:
                            self.model.addConstr(
                                h2_demand <= self.hydrogen_storage_vars[(location, hour)],
                                name=f"h2_supply_{location}_{hour}"
                            )
                    else:
                        # 其他位置（机场、LNG终端）：氢气需求必须通过运输满足
                        # 这里先添加一个强制约束，确保模型必须考虑氢气供应
                        # 实际的氢气运输约束在 _add_hydrogen_transport_constraints 中处理
                        logger.debug(f"位置 {location} 在第{hour}小时有氢气需求，需要运输供应")

                if location_type in ['solar_plant', 'wind_farm']:
                    # 2. 可再生能源电力供应约束（基于时段和天气）
                    self._add_renewable_power_constraints(location, hour)

                elif location_type in ['lng_terminal', 'airport']:
                    # 3. 天然气管道流量限制约束（简化版，移除维护停机）
                    self._add_simplified_ng_pipeline_constraints(location, hour)

                    # 4. 天然气储罐压力和流量约束
                    self._add_ng_storage_flow_constraints(location, hour)
        
        # 移除设备维护停机时间约束 - 这是导致20%利用率的主因
        # self._add_maintenance_downtime_constraints()  # 注释掉
        
        # 6. 氢气运输能力限制约束
        self._add_hydrogen_transport_capacity_constraints()
        
        logger.info("严格的小时级原料供应约束添加完成（已移除维护停机约束）")
    
    def _add_renewable_power_constraints(self, location: str, hour: int):
        """添加可再生能源电力供应约束"""
        location_info = self.locations[location]
        
        # 该时段可用电力 (MWh)
        if 'hourly_generation' in location_info and hour < len(location_info['hourly_generation']):
            available_power_mwh = location_info['hourly_generation'][hour]
        else:
            available_power_mwh = 0.0
        
        # 添加电力供应约束
        if available_power_mwh > 0:
            self.model.addConstr(
                self.hydrogen_production_vars[(location, hour)] * 
                self.costs['electrolysis_power_consumption'] / 1000 <= available_power_mwh,
                name=f"power_supply_{location}_{hour}"
            )
    
    def _add_ng_pipeline_flow_constraints(self, location: str, hour: int):
        """添加天然气管道流量限制约束"""
        location_info = self.locations[location]
        
        # 计算该地点的天然气需求
        ng_demand = gp.quicksum(
            self.production_vars[(location, tech, hour)] * 
            self.technologies[tech]['ng_consumption_ratio']
            for tech in self.technologies
            if (location, tech, hour) in self.production_vars
        )
        
        if ng_demand.size() == 0:
            return  # 没有需求，跳过
        
        # 根据位置类型设置不同的管道流量限制
        if location_info['type'] == 'lng_terminal':
            # LNG接收站：基于实际处理能力
            lng_capacity = location_info.get('lng_capacity', self.avg_lng_capacity_mcm_per_year)
            if lng_capacity is None or pd.isna(lng_capacity) or lng_capacity <= 0:
                lng_capacity = self.avg_lng_capacity_mcm_per_year
            
            # 基础流量：年产能平均到小时，但考虑小时波动
            base_flow_m3_per_hour = lng_capacity * 1000000 / 8760
            
            # 管道压力波动：高峰时段压力下降
            hour_of_day = hour % 24
            if 8 <= hour_of_day <= 20:  # 白天高峰
                pressure_factor = 0.7 + 0.2 * (1 - abs(hour_of_day - 14) / 6)
            else:  # 夜间低峰
                pressure_factor = 0.9 + 0.1 * ((hour % 12) / 12)
            
            # 管道维护因子：模拟管道定期维护
            maintenance_factor = 1.0
            if hour % (7 * 24) < 4:  # 每周前4小时进行维护，流量减少
                maintenance_factor = 0.6
            
            max_flow_m3_per_hour = base_flow_m3_per_hour * pressure_factor * maintenance_factor
            
        elif location_info['type'] == 'airport':
            # 机场：通过运输获得天然气，从配置读取流量限制
            max_flow_m3_per_hour = self.config.get('supply_capacity', {}).get('natural_gas_supply', {}).get('airport_max_flow_m3_per_hour', 5000)
            
        else:
            # 其他类型的默认约束，从配置读取
            max_flow_m3_per_hour = self.config.get('supply_capacity', {}).get('natural_gas_supply', {}).get('default_reduced_flow_m3_per_hour', 4000)
        
        # 添加流量约束
        self.model.addConstr(
            ng_demand <= max_flow_m3_per_hour,
            name=f"ng_flow_{location}_{hour}"
        )
    
    def _add_ng_storage_flow_constraints(self, location: str, hour: int):
        """
        原本用于添加天然气储罐压力和流量约束
        但对于LNG接收站，日处理能力约束已经足够，此函数已简化为仅记录日志
        """
        location_info = self.locations[location]
        
        # 对于LNG接收站，日处理能力约束已经足够，不需要额外的存储流量约束
        if location_info['type'] == 'lng_terminal':
            # 仅记录日志，不添加约束
            lng_capacity = location_info.get('lng_capacity', self.avg_lng_capacity_mcm_per_year)
            logger.debug(f"LNG接收站 {location} 小时 {hour}: 依赖日处理能力约束 ({lng_capacity} 万m³/年)")
            return
        
        # 对于其他类型的天然气源，保持原有逻辑
        # （如果需要的话，这里可以添加其他类型的存储约束）
    
    def _add_maintenance_downtime_constraints(self):
        """添加设备维护停机时间约束"""
        logger.info("添加设备维护停机时间约束...")
        
        for location in self.locations:
            for tech in self.technologies:
                # 每周安排4小时维护时间（设备不能生产）
                maintenance_hours = []
                for week in range(self.time_horizon_weeks):
                    # 每周的维护时间：周日凌晨1-4点
                    week_start_hour = week * 168
                    maintenance_hours.extend([
                        week_start_hour + 1,  # 周日凌晨1点
                        week_start_hour + 2,  # 周日凌晨2点
                        week_start_hour + 3,  # 周日凌晨3点
                        week_start_hour + 4   # 周日凌晨4点
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
        
        logger.info("氢气运输能力限制约束添加完成")
    
    def _add_inventory_balance_constraints(self):
        """添加库存平衡约束"""
        for location in self.locations:
            for hour in range(self.total_hours):
                # 库存平衡：当前库存 = 上期库存 + 生产 - 出库
                current_inventory = self.storage_vars[(location, hour + 1)]
                previous_inventory = self.storage_vars[(location, hour)]
                
                # 当前小时总生产
                production = gp.quicksum(
                    self.production_vars[(location, tech, hour)]
                    for tech in self.technologies
                    if (location, tech, hour) in self.production_vars
                )
                
                # 出库量（用于运输的部分，按小时平摊）
                outflow = gp.quicksum(
                    self.transport_vars[(location, airport, hour // self.hours_per_week)] / self.hours_per_week
                    for airport in self.airports
                    if (location, airport, hour // self.hours_per_week) in self.transport_vars
                )
                
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
            
            if location_type in ['solar_plant', 'wind_farm']:
                # 1. 电解槽容量约束
                # 从配置读取电解槽最大容量
                max_electrolyzer_capacity = self.config.get('capacity_limits', {}).get('electrolyzer_max_capacity_kg_per_hour', 2000)
                self.model.addConstr(
                    self.electrolyzer_capacity_vars[location] <= 
                    max_electrolyzer_capacity * self.electrolyzer_facility_vars[location],  # 使用配置参数
                    name=f"electrolyzer_capacity_{location}"
                )
                
                # 2. 制氢生产能力约束
                for hour in range(self.total_hours):
                    self.model.addConstr(
                        self.hydrogen_production_vars[(location, hour)] <= 
                        self.electrolyzer_capacity_vars[location],
                        name=f"h2_production_capacity_{location}_{hour}"
                    )
                    
                    # 3. 可再生能源电力平衡约束
                    available_energy_mwh = self.locations[location]['hourly_generation'][hour]  # MWh 每小时发电量
                    
                    # 制氢耗电：50 kWh/kg H2
                    electricity_consumption_mwh = (
                        self.hydrogen_production_vars[(location, hour)] * 
                        self.costs['electrolysis_power_consumption'] / 1000  # kWh -> MWh
                    )
                    
                    # 电力平衡：制氢耗电不能超过可再生能源发电量
                    if available_energy_mwh > 0:
                        self.model.addConstr(
                            electricity_consumption_mwh <= available_energy_mwh,
                            name=f"electricity_balance_{location}_{hour}"
                        )
                        
    def _add_hydrogen_balance_constraints(self):
        """添加氢气平衡约束"""
        logger.info("添加氢气平衡约束...")
        
        for location in self.locations:
            location_type = self.locations[location]['type']
            
            if location_type in ['solar_plant', 'wind_farm']:
                # 氢气库存平衡（加入运输影响）
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

                    # 氢气运输出库（周级运输量在最后一小时统一扣减）
                    h2_transport_outflow = 0
                    if hour == self.total_hours - 1:  # 在最后一小时统一扣减周运输量
                        # 整周的氢气运输出库量（周级变量）
                        weekly_outbound_transport = gp.quicksum(
                            self.hydrogen_transport_vars[(location, dest_loc)]
                            for dest_loc in self.locations
                            if (location, dest_loc) in self.hydrogen_transport_vars
                        )

                        # 管道运输（周级变量）
                        if hasattr(self, 'hydrogen_pipeline_transport_vars') and self.hydrogen_pipeline_transport_vars:
                            weekly_outbound_pipeline = gp.quicksum(
                                self.hydrogen_pipeline_transport_vars[(location, dest_loc)]
                                for dest_loc in self.locations
                                if (location, dest_loc) in self.hydrogen_pipeline_transport_vars
                            )
                            weekly_outbound_transport += weekly_outbound_pipeline

                        h2_transport_outflow = weekly_outbound_transport

                    # 氢气库存平衡方程
                    self.model.addConstr(
                        current_h2_inventory == previous_h2_inventory + h2_production - h2_local_consumption - h2_transport_outflow,
                        name=f"h2_balance_{location}_{hour}"
                    )

                # 初始氢气库存为0
                self.model.addConstr(
                    self.hydrogen_storage_vars[(location, 0)] == 0,
                    name=f"initial_h2_inventory_{location}"
                )

                # 添加氢气库存非负约束
                for hour in range(self.total_hours + 1):
                    self.model.addConstr(
                        self.hydrogen_storage_vars[(location, hour)] >= 0,
                        name=f"h2_inventory_nonnegative_{location}_{hour}"
                    )
    
    def _add_daily_hydrogen_mtj_constraints(self):
        """添加氢气每日产量限制下一日MTJ每日产量约束"""
        logger.info("添加氢气每日产量限制MTJ每日产量约束...")
        
        hours_per_day = 24  # 每日24小时
        total_days = self.total_hours // hours_per_day
        
        for location in self.locations:
            location_type = self.locations[location]['type']
            
            # 对于有氢气生产能力的位置（太阳能电站和风电场）
            if location_type in ['solar_plant', 'wind_farm']:
                for day in range(total_days - 1):  # 不包括最后一日，因为没有下一日
                    # 计算当日氢气总产量（24小时累计）
                    current_day_start = day * hours_per_day
                    current_day_end = (day + 1) * hours_per_day
                    
                    daily_h2_production = gp.quicksum(
                        self.hydrogen_production_vars[(location, hour)]
                        for hour in range(current_day_start, current_day_end)
                        if (location, hour) in self.hydrogen_production_vars
                    )
                    
                    # 计算下一日MTJ总产量（24小时累计）
                    next_day_start = (day + 1) * hours_per_day
                    next_day_end = (day + 2) * hours_per_day
                    
                    next_day_mtj_production = gp.quicksum(
                        self.production_vars[(location, tech, hour)]
                        for tech in self.technologies
                        for hour in range(next_day_start, next_day_end)
                        if (location, tech, hour) in self.production_vars and
                           self.technologies[tech].get('h2_consumption_ratio', 0) > 0
                    )
                    
                    # 计算下一日MTJ生产所需的氢气需求
                    next_day_h2_demand = gp.quicksum(
                        self.production_vars[(location, tech, hour)] * 
                        self.technologies[tech]['h2_consumption_ratio']
                        for tech in self.technologies
                        for hour in range(next_day_start, next_day_end)
                        if (location, tech, hour) in self.production_vars and
                           self.technologies[tech].get('h2_consumption_ratio', 0) > 0
                    )
                    
                    # 约束：当日氢气产量必须能够满足下一日MTJ生产的氢气需求
                    if daily_h2_production.size() > 0 and next_day_h2_demand.size() > 0:
                        self.model.addConstr(
                            daily_h2_production >= next_day_h2_demand,
                            name=f"daily_h2_limits_next_day_mtj_{location}_day{day}"
                        )
                        
        
        logger.info("氢气每日产量限制MTJ每日产量约束添加完成")
    
    def _add_hydrogen_transport_constraints(self):
        """添加氢气运输约束：氢气从可再生能源站运输到MTJ工厂"""
        logger.info("添加氢气运输约束...")

        # 1. 添加氢气全局守恒约束：确保周运输总量不超过周生产总量
        logger.info("添加氢气全局守恒约束（周级）...")

        # 计算整周全系统氢气总生产量
        total_weekly_h2_production = gp.quicksum(
            self.hydrogen_production_vars[(h_loc, hour)]
            for h_loc in self.hydrogen_locations
            for hour in range(self.total_hours)
            if (h_loc, hour) in self.hydrogen_production_vars
        )

        # 计算整周全系统氢气总运输量（运输变量现在是周级）
        total_weekly_transport = gp.quicksum(
            self.hydrogen_transport_vars[(h_loc, mtj_loc)]
            for h_loc in self.hydrogen_locations
            for mtj_loc in self.locations
            if (h_loc, mtj_loc) in self.hydrogen_transport_vars
        )

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
        for tech in ['airport_integrated_conversion', 'lng_terminal_conversion', 'integrated_supply_conversion']:
            if tech not in self.technologies:
                logger.warning(f"技术 {tech} 不在 technologies 中，跳过")
                continue
                
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

        # 3. 添加源地总出库约束：从每个氢气源地出库的总量不能超过该地周生产量
        logger.info("添加氢气源地总出库约束（周级）...")
        for h_loc in self.hydrogen_locations:
            # 该源地整周的氢气生产总量
            weekly_h2_production = gp.quicksum(
                self.hydrogen_production_vars[(h_loc, hour)]
                for hour in range(self.total_hours)
                if (h_loc, hour) in self.hydrogen_production_vars
            )

            # 从该源地出发的所有运输量（罐车，周级）
            total_outbound_transport = gp.quicksum(
                self.hydrogen_transport_vars[(h_loc, dest_loc)]
                for dest_loc in self.locations
                if (h_loc, dest_loc) in self.hydrogen_transport_vars
            )

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
        daily_transport_supply_terms = {}

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
                # 初始化该位置的字典结构
                if mtj_loc not in daily_transport_supply_terms:
                    daily_transport_supply_terms[mtj_loc] = {}
                if tech not in daily_transport_supply_terms[mtj_loc]:
                    daily_transport_supply_terms[mtj_loc][tech] = {}

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

                    # 根据技术类型确定氢气供应方式
                    if self.technologies[tech]['hydrogen_transport_required']:
                        # 需要运输的技术：氢气供应来自运输（累加所有天的需求）
                        if day not in daily_transport_supply_terms[mtj_loc][tech]:
                            daily_transport_supply_terms[mtj_loc][tech][day] = []

                        # 罐车运输（周级变量需要分摊到每天）
                        for h_loc in self.hydrogen_locations:
                            if (h_loc, mtj_loc) in self.hydrogen_transport_vars:
                                # 将周级运输量分摊到每天，除以总天数
                                total_days = self.total_hours // 24
                                daily_transport_share = self.hydrogen_transport_vars[(h_loc, mtj_loc)] / total_days
                                daily_transport_supply_terms[mtj_loc][tech][day].append(daily_transport_share)

                        # 管道运输（周级变量需要分摊到每天）
                        if hasattr(self, 'hydrogen_pipeline_transport_vars') and self.hydrogen_pipeline_transport_vars:
                            for h_loc in self.hydrogen_locations:
                                if (h_loc, mtj_loc) in self.hydrogen_pipeline_transport_vars:
                                    # 将周级管道运输量分摊到每天
                                    total_days = self.total_hours // 24
                                    daily_pipeline_share = self.hydrogen_pipeline_transport_vars[(h_loc, mtj_loc)] / total_days
                                    daily_transport_supply_terms[mtj_loc][tech][day].append(daily_pipeline_share)

                        # 氢气运输供应约束（每天的需求 <= 分摊的运输量）
                        if daily_transport_supply_terms[mtj_loc][tech][day]:
                            self.model.addConstr(
                                gp.quicksum(daily_transport_supply_terms[mtj_loc][tech][day]) >= hydrogen_demand,
                                name=f"hydrogen_transport_supply_{mtj_loc}_{tech}_day_{day}"
                            )
                            logger.debug(f"添加氢气运输供应约束: {len(daily_transport_supply_terms[mtj_loc][tech][day])} 个运输变量 -> {mtj_loc} {tech} day {day}")
                        else:
                            # 需要运输但无运输变量 - 强制约束导致不可行
                            self.model.addConstr(
                                0 >= hydrogen_demand,
                                name=f"missing_hydrogen_transport_{mtj_loc}_{tech}_day_{day}"
                            )
                            logger.warning(f"强制添加氢气运输缺失约束: 位置 {mtj_loc} 技术 {tech} 第{day}天")

                    else:
                        # 不需要运输的技术：氢气供应来自就地生产
                        # 该位置当天的氢气生产总量
                        daily_h2_production_terms = []
                        for hour in range(day_start_hour, day_end_hour):
                            if (mtj_loc, hour) in self.hydrogen_production_vars:
                                daily_h2_production_terms.append(self.hydrogen_production_vars[(mtj_loc, hour)])

                        if daily_h2_production_terms:
                            daily_h2_production = gp.quicksum(daily_h2_production_terms)
                            # 就地制氢供应约束：当天氢气需求不能超过当天生产
                            self.model.addConstr(
                                hydrogen_demand <= daily_h2_production,
                                name=f"hydrogen_local_supply_{mtj_loc}_{tech}_day_{day}"
                            )
                            logger.debug(f"添加就地制氢供应约束: {mtj_loc} {tech} day {day}")
                        else:
                            # 没有氢气生产能力但需要氢气 - 强制约束导致不可行
                            self.model.addConstr(
                                0 >= hydrogen_demand,
                                name=f"missing_hydrogen_production_{mtj_loc}_{tech}_day_{day}"
                            )
                            logger.warning(f"强制添加氢气生产缺失约束: 位置 {mtj_loc} 技术 {tech} 第{day}天 需要氢气但无生产能力")

        logger.info("氢气供需平衡约束添加完成")
    
    def _add_hydrogen_pipeline_transport_constraints(self):
        """添加氢能管道运输约束"""
        logger.info("添加氢能管道运输约束...")
        
        if not hasattr(self, 'hydrogen_pipeline_transport_vars') or not self.hydrogen_pipeline_transport_vars:
            logger.info("无氢能管道运输变量，跳过管道运输约束")
            return
        
        # 1. 管道建设决策约束：只有建设了管道才能进行运输
        for (h2_loc, mtj_loc) in self.hydrogen_pipeline_facility_vars:
            total_days = self.total_hours // 24
            for day in range(total_days):
                if (h2_loc, mtj_loc, day) in self.hydrogen_pipeline_transport_vars:
                    # 管道运输量 <= 管道建设决策 * 大M（管道日最大容量）
                    max_daily_pipeline_capacity = self.config.get('capacity_limits', {}).get('hydrogen_pipeline_max_daily_capacity_kg', 50000)
                    self.model.addConstr(
                        self.hydrogen_pipeline_transport_vars[(h2_loc, mtj_loc, day)] <= 
                        self.hydrogen_pipeline_facility_vars[(h2_loc, mtj_loc)] * max_daily_pipeline_capacity,
                        name=f"h2_pipeline_capacity_{h2_loc}_{mtj_loc}_day_{day}"
                    )
        
        # 2. 管道运输量约束：不超过氢气源地的生产能力
        for tech in ['airport_integrated_conversion', 'lng_terminal_conversion', 'integrated_supply_conversion']:
            if tech not in self.technologies or not self.technologies[tech]['hydrogen_transport_required']:
                continue
                
            if tech not in self.mtj_locations:
                continue
                
            locations = self.mtj_locations[tech]
            if not hasattr(locations, '__iter__') or isinstance(locations, str):
                continue
                
            for h2_loc in self.hydrogen_locations:
                for mtj_loc in locations:
                    if (h2_loc, mtj_loc) not in self.hydrogen_pipeline_facility_vars:
                        continue
                        
                    total_days = self.total_hours // 24
                    for day in range(total_days):
                        if (h2_loc, mtj_loc, day) in self.hydrogen_pipeline_transport_vars:
                            # 管道运输量 <= 该天氢气生产量
                            day_start_hour = day * 24
                            day_end_hour = min((day + 1) * 24, self.total_hours)
                            daily_h2_production = gp.quicksum(
                                self.hydrogen_production_vars[(h2_loc, hour)]
                                for hour in range(day_start_hour, day_end_hour)
                                if (h2_loc, hour) in self.hydrogen_production_vars
                            )
                            self.model.addConstr(
                                self.hydrogen_pipeline_transport_vars[(h2_loc, mtj_loc, day)] <= daily_h2_production,
                                name=f"h2_pipeline_production_limit_{h2_loc}_{mtj_loc}_day_{day}"
                            )
        
        # 3. 氢气运输方式排他性约束：同一路线只能选择罐车或管道运输之一
        for tech in ['airport_integrated_conversion', 'lng_terminal_conversion', 'integrated_supply_conversion']:
            if tech not in self.technologies or not self.technologies[tech]['hydrogen_transport_required']:
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
        
        # 注意：氢气需求满足约束已在 _add_hydrogen_transport_constraints() 中统一处理
        logger.info("氢能管道运输约束添加完成（需求满足约束已在主要氢气运输约束中处理）")
    
    def _add_natural_gas_transport_constraints(self):
        """添加天然气运输约束：天然气从管道通过罐车运输到非LNG接收站的MTJ工厂"""
        logger.info("添加天然气罐车运输约束...")
        
        # 天然气运输约束：对于非LNG接收站位置的MTJ工厂（改为天级罐车运输）
        total_days = self.total_hours // 24
        for tech in ['airport_integrated_conversion', 'lng_to_hplant_conversion', 'integrated_supply_conversion']:
            for ng_loc in self.ng_locations:
                for mtj_loc in self.non_lng_mtj_locations[tech]:
                    # 检查距离限制（罐车运输距离更短）
                    distance = self._calculate_location_distance(ng_loc, mtj_loc)
                    if distance > 300:  # 300公里距离限制（罐车）
                        continue
                        
                    for day in range(total_days):
                        # 只为存在的变量创建约束
                        if (ng_loc, mtj_loc, day) in self.ng_transport_vars:
                            # 从配置文件读取天然气罐车运输参数
                            truck_config = self.config.get('transport_constraints', {}).get('ng_truck_transport', {})
                            max_trucks_per_day = truck_config.get('max_trucks_per_day', 20)  # 每天最多车次
                            truck_capacity_m3 = truck_config.get('truck_capacity_m3', 1200)  # 每车容量(m³)
                            max_transport_per_day = max_trucks_per_day * truck_capacity_m3
                            self.model.addConstr(
                                self.ng_transport_vars[(ng_loc, mtj_loc, day)] <= max_transport_per_day,
                                name=f"ng_transport_capacity_{ng_loc}_{mtj_loc}_day_{day}"
                            )
        
        # 天然气运输需求满足约束：所有非LNG接收站的MTJ工厂天然气需求（改为天级罐车运输）
        total_days = self.total_hours // 24
        for tech in ['pipeline_direct_conversion', 'airport_integrated_conversion', 'lng_to_hplant_conversion', 'integrated_supply_conversion']:
            for mtj_loc in self.non_lng_mtj_locations[tech]:
                for day in range(total_days):
                    # 计算该天的天然气需求（基于该天所有小时的生产量）
                    day_start_hour = day * 24
                    day_end_hour = min((day + 1) * 24, self.total_hours)
                    
                    ng_demand_terms = []
                    for hour in range(day_start_hour, day_end_hour):
                        if (mtj_loc, tech, hour) in self.production_vars:
                            ng_consumption = self.technologies[tech]['ng_consumption_ratio']
                            ng_demand_terms.append(
                                self.production_vars[(mtj_loc, tech, hour)] * ng_consumption
                            )
                    
                    if ng_demand_terms:
                        ng_demand = gp.quicksum(ng_demand_terms)
                    else:
                        ng_demand = 0
                    
                    # 只对存在的运输变量求和
                    valid_transport_vars = [
                        self.ng_transport_vars[(ng_loc, mtj_loc, day)]
                        for ng_loc in self.ng_locations
                        if (ng_loc, mtj_loc, day) in self.ng_transport_vars
                    ]
                    
                    # 天然气运输量必须满足需求（只有当存在有效运输路线时）
                    if valid_transport_vars:
                        self.model.addConstr(
                            gp.quicksum(valid_transport_vars) >= ng_demand,
                            name=f"ng_demand_satisfaction_{mtj_loc}_{tech}_day_{day}"
                        )
    
        # 添加天然气管段日最大购入量约束
        self._add_ng_pipeline_daily_capacity_constraints()
        
        # 添加LNG接收站日最大供应量约束
        self._add_lng_terminal_daily_capacity_constraints()
    
    def _create_objective(self):
        """创建目标函数：最小化项目20年生命周期总成本"""
        logger.info("创建目标函数（基于20年生命周期总成本）...")

        # 定义时间相关常量
        total_days = self.total_hours // 24

        total_cost = 0
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
        facility_investment_cost = gp.quicksum(
            self.facility_vars[(location, tech)] * fixed_capex +
            self.facility_capacity_vars[(location, tech)] * variable_capex_per_capacity * 
            self.economic_params['mtj_plant_capacity_factor']
            for location in self.locations
            for tech in self.technologies
        )
        
        # 2. MTJ生产设施运营成本（20年现值）
        fixed_opex_annual = fac_cfg.get('fixed_opex_annual', 1000000)
        facility_operation_cost = gp.quicksum(
            self.facility_vars[(location, tech)] * fixed_opex_annual * present_value_factor
            for location in self.locations
            for tech in self.technologies
        )
        
        # 3. 生产变动运营成本（20年生命周期现值）
        variable_opex_per_kg = fac_cfg.get('variable_opex_per_kg', 0.3)  # 元/kg - 修正默认值从300到0.3
        logger.info(f"目标函数中使用的MTJ变动运营成本: {variable_opex_per_kg}元/kg")
        production_cost = gp.quicksum(
            self.production_vars[(location, tech, hour)] * variable_opex_per_kg * lifecycle_operation_factor
            for location in self.locations
            for tech in self.technologies  
            for hour in range(self.total_hours)
            if (location, tech, hour) in self.production_vars
        )
        
        # 4. 运输设备投资成本 + 20年运营成本现值
        total_transport_demand = gp.quicksum(
            self.transport_vars[(location, airport, week)]
            for location in self.locations
            for airport in self.airports
            for week in range(self.time_horizon_weeks)
            if (location, airport, week) in self.transport_vars
        )
        
        transport_equipment_cost = 0  # 已包含在平准化运输成本中
        transport_operation_cost = gp.quicksum(
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
        max_storage_needed = gp.quicksum(
            self.storage_vars[(location, hour)]
            for location in self.locations
            for hour in range(self.total_hours + 1)
        )
        # 优先使用统一成本配置中的MTJ储存设备成本
        storage_unit_cost = float(
            self.config.get('unified_costs', {}).get('storage', {}).get('mtj_equipment_cost_yuan_per_kg') or
            storage_cfg.get('equipment_unit_cost_yuan_per_kg', 10)
        )
        storage_equipment_cost = max_storage_needed * storage_unit_cost
        storage_operation_cost = gp.quicksum(
            self.storage_vars[(location, hour)] * 
            self._calculate_total_storage_cost_per_kg_hour() * lifecycle_operation_factor  # 20年运营成本现值
            for location in self.locations
            for hour in range(self.total_hours + 1)
        )
        
        # 6. 电解槽投资成本（一次性投资）
        electrolyzer_capex_raw = self.config['equipment_raw_costs']['electrolyzer']['capex_raw']
        logger.info(f"电解槽投资成本参数: {electrolyzer_capex_raw} 元/(kg H2/hour)")
        electrolyzer_investment_cost = gp.quicksum(
            self.electrolyzer_capacity_vars[location] * 
            electrolyzer_capex_raw * self.economic_params['electrolyzer_capacity_factor']  # 电解槽投资成本 - 使用配置参数
            for location in self.locations
            if location in self.electrolyzer_capacity_vars
        )
        
        # 7. 制氢运营成本（20年生命周期现值）- 使用统一成本配置
        hydrogen_production_unit_cost = float(
            self.config.get('unified_costs', {}).get('production', {}).get('hydrogen_internal_cost_yuan_per_kg', 0)
        )
        hydrogen_production_cost = gp.quicksum(
        self.hydrogen_production_vars[(location, hour)] * hydrogen_production_unit_cost * lifecycle_operation_factor
        for location in self.locations
        for hour in range(self.total_hours)
        if (location, hour) in self.hydrogen_production_vars
        )
        
        # 8. 电解制氢电力成本（20年生命周期现值）
        # 8. 电力成本（基于实际氢气生产的电力消耗）
        electricity_cost = gp.quicksum(
            self.hydrogen_production_vars[(location, hour)] *
            self.costs['electrolysis_power_consumption'] / 1000 *  # kWh -> MWh
            self.costs['renewable_electricity_cost_yuan_per_mwh']  # 时间窗口内实际电力成本，不乘以生命周期系数
            for location in self.locations
            for hour in range(self.total_hours)
            if (location, hour) in self.hydrogen_production_vars
        ) * operation_expansion_factor * present_value_factor  # 扩展到20年生命周期现值
        
        # 9. 氢气储存投资 + 20年运营成本现值
        max_h2_storage = gp.quicksum(
            self.hydrogen_storage_vars[(location, hour)]
            for location in self.locations
            for hour in range(self.total_hours + 1)
            if (location, hour) in self.hydrogen_storage_vars
        )
        # 优先使用统一成本配置中的氢气储存设备成本
        h2_storage_unit_cost = float(
            self.config.get('unified_costs', {}).get('storage', {}).get('hydrogen_equipment_cost_yuan_per_kg') or
            storage_cfg.get('hydrogen_equipment_unit_cost_yuan_per_kg', 20)
        )
        h2_storage_investment = max_h2_storage * h2_storage_unit_cost
        h2_storage_operation = gp.quicksum(
            self.hydrogen_storage_vars[(location, hour)] * 
            self._calculate_total_storage_cost_per_kg_hour() * lifecycle_operation_factor  # 20年运营成本现值
            for location in self.locations
            for hour in range(self.total_hours + 1)
            if (location, hour) in self.hydrogen_storage_vars
        )
        
        # 9. 氢气运输投资 + 20年运营成本现值（改为周级）
        hydrogen_transport_investment = 0  # 已包含在平准化氢气运输成本中
        hydrogen_transport_operation = gp.quicksum(
            self.hydrogen_transport_vars[(h_loc, mtj_loc)] *
            self._calculate_hydrogen_transport_cost_by_distance(
                self._calculate_location_distance(h_loc, mtj_loc)
            ) * operation_expansion_factor * present_value_factor  # 周运输量 × 单位成本 × 年化系数 × 现值系数
            for h_loc in self.hydrogen_locations
            for mtj_loc in sum(self.mtj_locations.values(), [])
            if (h_loc, mtj_loc) in self.hydrogen_transport_vars
        )
        
        # 9.1. 氢能管道运输成本现值（成本函数已包含所有费用）
        hydrogen_pipeline_operation = 0
        
        if hasattr(self, 'hydrogen_pipeline_transport_vars') and self.hydrogen_pipeline_transport_vars:
            # 管道运输成本（基于图像拟合的成本函数，已包含所有投资和运营成本）
            hydrogen_pipeline_operation = gp.quicksum(
                self.hydrogen_pipeline_transport_vars[(h2_loc, mtj_loc)] *
                self._calculate_hydrogen_pipeline_cost_by_distance(
                    self._calculate_location_distance(h2_loc, mtj_loc)
                ) * operation_expansion_factor * present_value_factor  # 周运输量 × 单位成本 × 年化系数 × 现值系数
                for h2_loc in self.hydrogen_locations
                for mtj_loc in sum(self.mtj_locations.values(), [])
                if (h2_loc, mtj_loc) in self.hydrogen_pipeline_transport_vars
            )
        
        # 10. 天然气罐车运输投资 + 20年运营成本现值（改为天级）
        ng_transport_investment = 0  # 已包含在平准化天然气运输成本中
        # 天然气运输成本 - 基于LNG公式 W_LNG = (4.52e-4 * L) + (0.888/q) + 0.927
        # 其中q是日输送量(10^4 m³/d)，需要基于实际优化变量计算
        ng_transport_operation = gp.LinExpr()
        total_days = self.total_hours // 24

        # 为每条路线计算基于实际日输送量的运输成本
        for ng_loc in self.ng_locations:
            for mtj_loc in sum(self.non_lng_mtj_locations.values(), []):
                # 检查该MTJ位置是否属于机场集成转换
                is_airport_integrated = False
                if 'airport_integrated_conversion' in self.non_lng_mtj_locations:
                    if mtj_loc in self.non_lng_mtj_locations['airport_integrated_conversion']:
                        is_airport_integrated = True

                # 机场集成转换模式下天然气运输成本为0，跳过计算
                if is_airport_integrated:
                    continue

                distance_km = self._calculate_location_distance(ng_loc, mtj_loc)

                # 计算每天该路线的运输量，用于确定日输送量q
                # 确保total_days在此作用域内可用
                total_days_local = self.total_hours // 24
                for day in range(total_days_local):
                    if (ng_loc, mtj_loc, day) in self.ng_transport_vars:
                        transport_var = self.ng_transport_vars[(ng_loc, mtj_loc, day)]
                        
                        # LNG公式的线性部分: (4.52e-4 * L + 0.927) * 运输量
                        linear_cost = (4.52e-4 * distance_km + 0.927) * transport_var
                        ng_transport_operation += linear_cost * lifecycle_operation_factor
                        
        # 处理规模经济部分 0.888/q - 直接使用约束中计算好的日处理能力上限
        for ng_loc in self.ng_locations:
            # 从存储中获取该天然气源的日处理能力上限
            daily_capacity_limit = self.ng_daily_capacities.get(ng_loc, 10000)  # m³/d
            q_max = daily_capacity_limit / 10000  # 转换为10^4 m³/d单位
            
            if q_max > 0:
                total_days_local = self.total_hours // 24
                for day in range(total_days_local):
                    # 计算该天然气源在这一天的总输送量
                    daily_volume = gp.LinExpr()
                    has_transport = False
                    
                    for mtj_loc in sum(self.non_lng_mtj_locations.values(), []):
                        if (ng_loc, mtj_loc, day) in self.ng_transport_vars:
                            # 检查该MTJ位置是否属于机场集成转换
                            is_airport_integrated = False
                            if 'airport_integrated_conversion' in self.non_lng_mtj_locations:
                                if mtj_loc in self.non_lng_mtj_locations['airport_integrated_conversion']:
                                    is_airport_integrated = True

                            # 机场集成转换模式下天然气运输成本为0，跳过计算
                            if is_airport_integrated:
                                continue

                            daily_volume += self.ng_transport_vars[(ng_loc, mtj_loc, day)]
                            has_transport = True
                    
                    if has_transport:
                        # 创建二进制变量表示是否有运输
                        transport_indicator = self.model.addVar(
                            vtype=gp.GRB.BINARY,
                            name=f"ng_transport_active_{ng_loc}_day_{day}"
                        )
                        
                        # 如果有运输，daily_volume > 0，则 transport_indicator = 1
                        # 使用Big-M约束
                        M = q_max * 10000  # 大M值
                        self.model.addConstr(
                            daily_volume <= M * transport_indicator,
                            name=f"ng_transport_activate_{ng_loc}_day_{day}"
                        )
                        
                        # 当有运输时，规模经济成本 = 0.888 * transport_indicator
                        # 这是对0.888/q的简化处理：当q>0时，成本为固定值0.888
                        scale_economy_cost = 0.888 * transport_indicator
                        
                        # 将成本分摊到各运输路线
                        for mtj_loc in sum(self.non_lng_mtj_locations.values(), []):
                            if (ng_loc, mtj_loc, day) in self.ng_transport_vars:
                                # 检查该MTJ位置是否属于机场集成转换
                                is_airport_integrated = False
                                if 'airport_integrated_conversion' in self.non_lng_mtj_locations:
                                    if mtj_loc in self.non_lng_mtj_locations['airport_integrated_conversion']:
                                        is_airport_integrated = True
                                
                                # 机场集成转换模式下天然气运输成本为0，跳过规模经济成本计算
                                if is_airport_integrated:
                                    continue
                                    
                                transport_var = self.ng_transport_vars[(ng_loc, mtj_loc, day)]
                                # 每单位运输量承担的规模经济成本
                                ng_transport_operation += transport_var * scale_economy_cost * lifecycle_operation_factor
        
        # 11. 原料成本（20年生命周期现值）
        natural_gas_cost = self._calculate_natural_gas_cost() * lifecycle_operation_factor
        
        
        # 13. 短缺惩罚成本（20年生命周期现值）
        shortage_cost = 0
        if hasattr(self, 'shortage_vars'):
            shortage_cost = gp.quicksum(
                var * self.costs['shortage_penalty_yuan_per_kg'] * lifecycle_operation_factor  # 20年现值
                for var in self.shortage_vars.values()
            )
        
        # 14. 期末资产处置成本（20年后的现值）
        disposal_cost_per_kg = float(obj_cfg.get('final_inventory_disposal_cost_per_kg', 100))
        final_inventory_cost = gp.quicksum(
            self.storage_vars[(location, self.total_hours)] * disposal_cost_per_kg * operation_expansion_factor * 
            (1 + discount_rate)**(-project_lifespan)  # 20年后处置成本的现值
            for location in self.locations
        )
        
        # 项目20年生命周期总成本
        total_cost = (
            # 投资成本（项目开始时）
            facility_investment_cost + transport_equipment_cost + storage_equipment_cost +
            electrolyzer_investment_cost + h2_storage_investment + hydrogen_transport_investment +
            ng_transport_investment +

            # 运营成本（20年现值）
            facility_operation_cost + production_cost + transport_operation_cost +
            storage_operation_cost + hydrogen_production_cost + electricity_cost + h2_storage_operation +
            hydrogen_transport_operation + hydrogen_pipeline_operation + ng_transport_operation +
            natural_gas_cost + shortage_cost + final_inventory_cost
        )
        
        # 设置目标函数：最小化项目20年生命周期总成本
        self.model.setObjective(total_cost, GRB.MINIMIZE)

        logger.info("项目20年生命周期总成本目标函数创建完成")
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
    

    def _calculate_total_ng_transport_cost_per_kg_km(self) -> float:
        """计算天然气运输总成本（已弃用，统一使用基于距离的LNG成本公式）
        
        注意：此函数已被_calculate_ng_transport_cost_by_distance()替代
        保留此函数仅为向后兼容，建议使用基于距离的计算方法
        """
        # 为保持向后兼容，返回默认距离下的成本
        return self._calculate_ng_transport_cost_by_distance(100)  # 默认100km距离
    
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
    
    def _calculate_ng_transport_cost_by_distance(self, distance_km: float, daily_volume_m3: float = None) -> float:
        """基于LNG运输成本公式计算天然气运输成本
        
        公式: W_LNG ≈ (4.52 × 10^-4 × L) + (0.888/q) + 0.927
        
        Args:
            distance_km: 运输距离 L (km)  
            daily_volume_m3: 日输送量 q (m³/d)，如果为None则从配置读取默认值
            
        Returns:
            float: 运输成本 (元/m³)
        """
        if distance_km <= 0:
            return 0.0
            
        # 从配置读取默认日处理量
        if daily_volume_m3 is None:
            daily_volume_m3 = self.config.get('supply_capacity', {}).get('natural_gas_supply', {}).get('default_daily_volume_m3', 10000)
            
        # LNG运输成本公式
        L = distance_km
        q = daily_volume_m3 / 10000  # 转换为10^4 m³/d单位
        
        # 避免除零
        if q <= 0:
            q = 1.0  # 默认值
            
        # W_LNG = (4.52 × 10^-4 × L) + (0.888/q) + 0.927
        transport_cost_yuan_per_m3 = (4.52e-4 * L) + (0.888 / q) + 0.927
        
        return max(0, transport_cost_yuan_per_m3)

    def _calculate_unified_ng_transport_cost(self, operation_expansion_factor: float, present_value_factor: float) -> float:
        """
        计算天然气运输成本 - 与目标函数使用相同的复杂计算逻辑
        包含线性成本和规模经济成本两部分
        """
        ng_transport_cost_total = 0.0
        total_days = self.total_hours // 24

        if not hasattr(self, 'ng_transport_vars'):
            return 0.0

        # 第一部分：线性成本计算 (4.52e-4 * L + 0.927) * 运输量
        for ng_loc in self.ng_locations:
            for mtj_loc in sum(self.non_lng_mtj_locations.values(), []):
                # 检查该MTJ位置是否属于机场集成转换
                is_airport_integrated = False
                if 'airport_integrated_conversion' in self.non_lng_mtj_locations:
                    if mtj_loc in self.non_lng_mtj_locations['airport_integrated_conversion']:
                        is_airport_integrated = True

                # 机场集成转换模式下天然气运输成本为0，跳过计算
                if is_airport_integrated:
                    continue

                distance_km = self._calculate_location_distance(ng_loc, mtj_loc)

                for day in range(total_days):
                    if (ng_loc, mtj_loc, day) in self.ng_transport_vars:
                        transport_var = self.ng_transport_vars[(ng_loc, mtj_loc, day)]
                        if hasattr(transport_var, 'x') and transport_var.x > 0:
                            # LNG公式的线性部分: (4.52e-4 * L + 0.927) * 运输量
                            linear_cost = (4.52e-4 * distance_km + 0.927) * transport_var.x
                            ng_transport_cost_total += linear_cost

        # 第二部分：规模经济成本计算 0.888/q
        # 为每个天然气源的每天计算规模经济成本
        for ng_loc in self.ng_locations:
            daily_capacity_limit = self.ng_daily_capacities.get(ng_loc, 10000)  # m³/d

            for day in range(total_days):
                # 计算该天然气源在这一天的总输送量
                daily_volume = 0.0

                for mtj_loc in sum(self.non_lng_mtj_locations.values(), []):
                    if (ng_loc, mtj_loc, day) in self.ng_transport_vars:
                        transport_var = self.ng_transport_vars[(ng_loc, mtj_loc, day)]
                        if hasattr(transport_var, 'x') and transport_var.x > 0:
                            daily_volume += transport_var.x

                # 如果当天有运输，则应用规模经济成本
                if daily_volume > 0:
                    # 将成本分摊到各运输路线
                    for mtj_loc in sum(self.non_lng_mtj_locations.values(), []):
                        if (ng_loc, mtj_loc, day) in self.ng_transport_vars:
                            # 检查该MTJ位置是否属于机场集成转换
                            is_airport_integrated = False
                            if 'airport_integrated_conversion' in self.non_lng_mtj_locations:
                                if mtj_loc in self.non_lng_mtj_locations['airport_integrated_conversion']:
                                    is_airport_integrated = True

                            # 机场集成转换模式下天然气运输成本为0，跳过规模经济成本计算
                            if is_airport_integrated:
                                continue

                            transport_var = self.ng_transport_vars[(ng_loc, mtj_loc, day)]
                            if hasattr(transport_var, 'x') and transport_var.x > 0:
                                # 每单位运输量承担的规模经济成本
                                scale_economy_cost = 0.888  # 简化处理，固定值
                                ng_transport_cost_total += transport_var.x * scale_economy_cost

        # 应用生命周期扩展系数
        ng_transport_cost_total *= operation_expansion_factor * present_value_factor

        return ng_transport_cost_total

    def _get_ng_transport_unit_cost(self, ng_loc: str, mtj_loc: str, total_days: int) -> float:
        """计算天然气运输单位成本，基于预期的路线运输量
        
        Args:
            ng_loc: 天然气源位置
            mtj_loc: MTJ生产位置  
            total_days: 总天数
            
        Returns:
            float: 单位运输成本 (元/m³)
        """
        distance_km = self._calculate_location_distance(ng_loc, mtj_loc)
        
        # 估算该路线的日均运输量
        # 基于MTJ位置的需求规模估算天然气运输量
        estimated_daily_volume_m3 = self._estimate_ng_daily_volume_for_route(ng_loc, mtj_loc)
        
        # 使用LNG公式计算运输成本
        return self._calculate_ng_transport_cost_by_distance(distance_km, estimated_daily_volume_m3)
    
    def _estimate_ng_daily_volume_for_route(self, ng_loc: str, mtj_loc: str) -> float:
        """估算天然气运输路线的日均运输量
        
        Args:
            ng_loc: 天然气源位置
            mtj_loc: MTJ生产位置
            
        Returns:
            float: 估算的日运输量 (m³/d)
        """
        # 基于MTJ位置的技术类型和规模估算天然气需求
        if mtj_loc in self.locations:
            location_data = self.locations[mtj_loc]
            tech_type = location_data.get('mtj_technology', 'FT')  # 默认费托技术
            
            # 根据技术类型估算天然气消耗比例
            tech_info = self.technologies.get(tech_type, {})
            ng_consumption_ratio = tech_info.get('ng_consumption_ratio', 3.0)  # m³天然气/kg MTJ
            
            # 估算该位置的MTJ生产规模（基于位置类型和规模）
            estimated_daily_mtj_kg = self._estimate_location_mtj_capacity(mtj_loc)
            estimated_daily_ng_m3 = estimated_daily_mtj_kg * ng_consumption_ratio
            
            return max(1000, min(50000, estimated_daily_ng_m3))  # 限制在合理范围内
        
        # 从配置读取默认天然气需求
        return self.config.get('capacity_limits', {}).get('ng_demand_estimates', {}).get('default_daily_volume_m3', 10000)
    
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
    
    def _calculate_levelized_ng_transport_cost(self) -> float:
        """保留兼容性的函数，内部调用新的基于距离的计算方法
        
        Returns:
            float: 默认距离下的运输成本 (元/m³)
        """
        # 使用默认距离100km和从配置读取的默认日输送量计算
        default_distance_km = 100
        default_daily_volume_m3 = self.config.get('supply_capacity', {}).get('natural_gas_supply', {}).get('default_daily_volume_m3', 10000)
        return self._calculate_ng_transport_cost_by_distance(default_distance_km, default_daily_volume_m3)
    
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
            loc_lat, loc_lon, air_lat, air_lon, vehicle="car", include_route_geometry=False
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
            loc_lat, loc_lon, air_lat, air_lon, vehicle="car", include_route_geometry=True
        )
        distance_km = result.get('distance_km', 0)
        route_coordinates = result.get('route_coordinates', [])
        
        # 如果路径规划失败，使用直线作为后备方案
        if not result.get('route_found', False) or not route_coordinates:
            distance_km = self.distance_calculator.calculate_haversine_distance(
                loc_lat, loc_lon, air_lat, air_lon
            ) * 1.3
            route_coordinates = [[loc_lon, loc_lat], [air_lon, air_lat]]  # 直线路径
        
        # 缓存路径结果
        if not hasattr(self, 'route_cache'):
            self.route_cache = {}
        
        self.route_cache[route_cache_key] = {
            'distance_km': distance_km,
            'route_coordinates': route_coordinates
        }
        
        return max(distance_km, 5), route_coordinates
    
    def _calculate_location_distance(self, location1: str, location2: str) -> float:
        """使用GraphHopper路径规划计算两个位置间的真实道路距离"""
        # 创建缓存键
        cache_key = f"{location1}_{location2}"
        if cache_key in self.distance_cache:
            return self.distance_cache[cache_key]
        
        # 反向缓存键（距离是对称的）
        reverse_cache_key = f"{location2}_{location1}"
        if reverse_cache_key in self.distance_cache:
            return self.distance_cache[reverse_cache_key]
        
        loc1_lat = self.locations[location1]['latitude']
        loc1_lon = self.locations[location1]['longitude']
        loc2_lat = self.locations[location2]['latitude']
        loc2_lon = self.locations[location2]['longitude']
        
        # 使用GraphHopper路径规划计算真实距离
        result = self.routing_engine.calculate_route_distance(
            loc1_lat, loc1_lon, loc2_lat, loc2_lon, vehicle="car", include_route_geometry=False
        )
        distance_km = result.get('distance_km', 0)
        
        # 如果百度地图API失败，使用备选方案
        if not result.get('route_found', False):
            # 使用直线距离乘以系数作为备选方案
            distance_km = self.distance_calculator.calculate_haversine_distance(
                loc1_lat, loc1_lon, loc2_lat, loc2_lon
            ) * 1.3
        
        # 缓存结果（双向）
        self.distance_cache[cache_key] = distance_km
        self.distance_cache[reverse_cache_key] = distance_km
        
        return max(distance_km, 5)  # 最小距离5km（避免除零）
    
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
            loc1_lat, loc1_lon, loc2_lat, loc2_lon, vehicle="car", include_route_geometry=True
        )
        distance_km = result.get('distance_km', 0)
        route_coordinates = result.get('route_coordinates', [])
        
        # 如果路径规划失败，使用直线作为后备方案
        if not result.get('route_found', False) or not route_coordinates:
            distance_km = self.distance_calculator.calculate_haversine_distance(
                loc1_lat, loc1_lon, loc2_lat, loc2_lon
            ) * 1.3
            route_coordinates = [[loc1_lon, loc1_lat], [loc2_lon, loc2_lat]]  # 直线路径
        
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
    
    def _calculate_natural_gas_cost(self):
        """计算天然气原料成本（修复：使用MTJ生产变量）"""
        natural_gas_cost = 0

        # 获取天然气价格
        ng_price_per_10k_m3 = None
        for pipeline_id, pipeline_data in self.ng_pipeline_sources.items():
            price = pipeline_data.get('natural_gas_price_yuan_per_10k_m3', None)
            if price is not None:
                ng_price_per_10k_m3 = price
                break

        if ng_price_per_10k_m3 is None:
            return 0

        # 基于MTJ生产变量计算天然气成本
        if hasattr(self, 'mtj_production_vars'):
            for (location, tech, hour), var in self.mtj_production_vars.items():
                tech_info = self.technologies.get(tech, {})
                ng_consumption_ratio = tech_info.get('natural_gas_consumption_m3_per_kg_mtj', 0)

                if ng_consumption_ratio > 0:
                    natural_gas_cost += (
                        var * ng_consumption_ratio * ng_price_per_10k_m3 / 10000
                    )

        return natural_gas_cost
    
    def _calculate_actual_natural_gas_cost(self):
        """计算实际天然气成本（用于结果分析）"""
        natural_gas_cost = 0
        
        for location in self.locations:
            location_data = self.locations[location]
            # 优先使用管道文件价格，没有时使用配置默认价格
            ng_price_per_m3 = self._get_natural_gas_price_yuan_per_m3(location)
            ng_price_per_10k_m3 = ng_price_per_m3 * 10000
            
            # 计算实际消耗的天然气成本
            for tech in self.technologies:
                ng_consumption_ratio = self.technologies[tech]['ng_consumption_ratio']
                
                for hour in range(self.total_hours):
                    if (location, tech, hour) in self.production_vars:
                        var = self.production_vars[(location, tech, hour)]
                        if var.x > 0:
                            natural_gas_cost += (
                                var.x * ng_consumption_ratio * ng_price_per_10k_m3 / 10000
                            )
        
        return natural_gas_cost

    def _calculate_natural_gas_cost_for_breakdown(self):
        """计算天然气原料成本（修复：使用MTJ生产变量）"""
        natural_gas_cost = 0

        # 检查是否有MTJ生产变量
        if not hasattr(self, 'mtj_production_vars') or not self.mtj_production_vars:
            logger.warning("没有找到MTJ生产变量，天然气成本为0")
            return 0

        # 获取天然气价格
        ng_price_per_10k_m3 = None
        for pipeline_id, pipeline_data in self.ng_pipeline_sources.items():
            price = pipeline_data.get('natural_gas_price_yuan_per_10k_m3', None)
            if price is not None:
                ng_price_per_10k_m3 = price
                break

        if ng_price_per_10k_m3 is None:
            logger.warning("没有找到天然气价格，天然气成本为0")
            return 0

        # 统计活跃的MTJ locations
        active_mtj_locations = {}
        for (location, tech, hour), var in self.mtj_production_vars.items():
            if hasattr(var, 'x') and var.x > 0:
                if location not in active_mtj_locations:
                    active_mtj_locations[location] = {}
                if tech not in active_mtj_locations[location]:
                    active_mtj_locations[location][tech] = 0
                active_mtj_locations[location][tech] += var.x

        # 计算每个活跃location的天然气成本
        total_mtj_production = 0
        for location, tech_production in active_mtj_locations.items():
            location_cost = 0
            for tech, production in tech_production.items():
                tech_info = self.technologies.get(tech, {})
                ng_consumption_ratio = tech_info.get('natural_gas_consumption_m3_per_kg_mtj', 0)

                if ng_consumption_ratio > 0 and production > 0:
                    tech_ng_cost = production * ng_consumption_ratio * ng_price_per_10k_m3 / 10000
                    location_cost += tech_ng_cost
                    total_mtj_production += production
                    logger.info(f"Location {location}, Tech {tech}: 生产量={production:.0f}kg, 天然气消耗={production * ng_consumption_ratio:.0f}m³, 成本={tech_ng_cost:.2f}元")

            natural_gas_cost += location_cost
            if location_cost > 0:
                logger.info(f"MTJ Location {location} 天然气总成本: {location_cost:.2f}元")

        logger.info(f"活跃MTJ位置数: {len(active_mtj_locations)}, 总MTJ生产量: {total_mtj_production:.0f}kg, 天然气总成本: {natural_gas_cost:.2f}元")
        return natural_gas_cost

    def solve(self) -> Dict:
        """求解优化模型"""
        logger.info("开始求解优化模型...")
        
        if self.model is None:
            raise ValueError("模型尚未构建，请先调用build_model()")
        
        # 求解
        self.model.optimize()
        
        # 检查求解状态
        if self.model.status == GRB.OPTIMAL:
            logger.info("找到最优解")
            return self._extract_solution()
        elif self.model.status == GRB.TIME_LIMIT:
            logger.warning("达到时间限制，返回当前最优解")
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
        else:
            logger.error(f"求解失败，状态: {self.model.status}")
            return {"status": "failed", "status_code": self.model.status}
    
    def _extract_solution(self) -> Dict:
        """从优化结果中提取解决方案"""
        solution = {}
        
        # 获取基本优化信息
        solution['optimization_status'] = self.model.status
        solution['optimization_time'] = self.model.Runtime
        solution['objective_value_lifecycle_total'] = self.model.ObjVal  # 20年生命周期总成本
        solution['project_lifespan_years'] = self.economic_params['project_lifespan']
        solution['time_window_weeks'] = self.time_horizon_weeks
        
        # 计算生命周期平准化成本（基于20年总产量）
        # 计算时间窗口内的实际产量
        total_production_in_window = sum(
                    self.production_vars[(location, tech, hour)].x
            for location in self.locations
            for tech in self.technologies  
                    for hour in range(self.total_hours)
            if (location, tech, hour) in self.production_vars and self.production_vars[(location, tech, hour)].x > 0
        )
        
        # 计算生命周期总产量（使用现值系数而不是简单20倍）
        annual_production = total_production_in_window * (52.0 / self.time_horizon_weeks)

        # 计算现值系数（与目标函数保持一致）
        discount_rate = self.economic_params['discount_rate']
        project_lifespan = solution['project_lifespan_years']
        if discount_rate == 0:
            present_value_factor = project_lifespan
        else:
            present_value_factor = (1 - (1 + discount_rate)**(-project_lifespan)) / discount_rate

        # 生命周期总产量现值等效
        lifecycle_total_production = annual_production * present_value_factor
        
        # 获取成本分解数据用于统一计算基础
        cost_breakdown = self._calculate_cost_breakdown()
        solution['cost_breakdown'] = cost_breakdown
        
        # 使用cost_breakdown统一计算平准化成本
        total_cost_excluding_shortage = cost_breakdown.get('total_lifecycle_cost', 0)
        shortage_cost = cost_breakdown.get('shortage_penalty_cost', 0)
        total_cost_including_shortage = total_cost_excluding_shortage + shortage_cost
        
        # 生命周期平准化成本（含短缺，基于cost_breakdown）
        if lifecycle_total_production > 0:
            solution['lifecycle_levelized_cost_per_kg'] = total_cost_including_shortage / lifecycle_total_production
        else:
            solution['lifecycle_levelized_cost_per_kg'] = 0
        
        # 年化平准化成本（含短缺，基于cost_breakdown）
        if annual_production > 0:
            solution['annual_levelized_cost_per_kg'] = (total_cost_including_shortage / solution['project_lifespan_years']) / annual_production
        else:
            solution['annual_levelized_cost_per_kg'] = 0
        
        # 存储产量信息
        solution['annual_production_kg'] = annual_production
        solution['lifecycle_total_production_kg'] = lifecycle_total_production
        
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

        # 提取氢气运输计划（同时处理罐车和管道运输）
        solution['hydrogen_transport'] = {}
        
        # 调试信息：统计氢气运输变量
        truck_count = 0
        truck_positive = 0
        pipeline_count = 0
        pipeline_positive = 0
        
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
        
        # 2. 提取氢能管道运输
        if hasattr(self, 'hydrogen_pipeline_transport_vars') and self.hydrogen_pipeline_transport_vars:
            for (h_loc, mtj_loc), var in self.hydrogen_pipeline_transport_vars.items():
                pipeline_count += 1
                if var.x > 0:
                    pipeline_positive += 1
                    transport_key = f"{h_loc}_{mtj_loc}_weekly_pipeline"
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
                        'transport_mode': 'pipeline'
                    }
        
        # 输出氢气运输统计信息
        print(f"\n=== 氢气运输决策统计 ===")
        print(f"氢气罐车运输变量: {truck_count} 个, 其中非零: {truck_positive} 个")
        print(f"氢能管道运输变量: {pipeline_count} 个, 其中非零: {pipeline_positive} 个")
        print(f"总氢气运输记录: {len(solution['hydrogen_transport'])} 条")
        if solution['hydrogen_transport']:
            total_h2_transport = sum(info['transport_kg_h2'] for info in solution['hydrogen_transport'].values())
            print(f"总氢气运输量: {total_h2_transport:.2f} kg/week")
        print("=======================\n")

        # 提取天然气运输计划（改为天级）
        solution['ng_transport'] = {}
        for (ng_loc, mtj_loc, day), var in self.ng_transport_vars.items():
            if var.x > 0:
                transport_key = f"{ng_loc}_{mtj_loc}_day_{day}"
                from_coords = self._get_location_coordinates(ng_loc)
                to_coords = self._get_location_coordinates(mtj_loc)
                solution['ng_transport'][transport_key] = {
                    'from_location': ng_loc,
                    'to_location': mtj_loc,
                    'day': day,
                    'transport_m3_ng': var.x,
                    'distance_km': self._calculate_location_distance(ng_loc, mtj_loc),
                    'from_latitude': from_coords[0],
                    'from_longitude': from_coords[1],
                    'to_latitude': to_coords[0],
                    'to_longitude': to_coords[1],
                    'transport_type': 'NG',
                    'transport_mode': 'truck'
                }
        
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
        
        # 直接计算短缺惩罚成本
        shortage_cost_total = 0
        operation_expansion_factor = 52.0 / self.time_horizon_weeks
        discount_rate = self.economic_params['discount_rate']
        project_lifespan = self.economic_params['project_lifespan']
        if discount_rate == 0:
            present_value_factor = project_lifespan
        else:
            present_value_factor = (1 - (1 + discount_rate)**(-project_lifespan)) / discount_rate

        if hasattr(self, 'shortage_vars'):
            shortage_cost_total = sum(
                var.x * self.costs['shortage_penalty_yuan_per_kg']
                for var in self.shortage_vars.values()
                if var.x > 0
            ) * operation_expansion_factor * present_value_factor

        # 保存短缺成本到solution中
        solution['shortage_penalty_cost'] = shortage_cost_total

        # 使用目标函数值减去短缺成本计算不含短缺的总成本
        total_cost_excluding_shortage = self.model.ObjVal - shortage_cost_total

        # 检查实际生产情况
        total_h2_production = 0
        if hasattr(self, 'hydrogen_production_vars'):
            total_h2_production = sum(
                var.x for var in self.hydrogen_production_vars.values() if var.x > 0
            )

        total_mtj_production = sum(
            self.production_vars[(location, tech, hour)].x
            for location in self.locations
            for tech in self.technologies
            for hour in range(self.total_hours)
            if (location, tech, hour) in self.production_vars and self.production_vars[(location, tech, hour)].x > 0
        )

        # 计算实际电力消耗和成本
        theoretical_electricity_consumption = total_h2_production * self.costs['electrolysis_power_consumption'] / 1000  # MWh
        # 计算理论电力成本（1周实际消耗）
        weekly_electricity_cost = theoretical_electricity_consumption * self.costs['renewable_electricity_cost_yuan_per_mwh']
        # 计算20年生命周期总电力成本用于比较
        theoretical_electricity_cost = weekly_electricity_cost * operation_expansion_factor * present_value_factor

        # 详细打印成本信息
        logger.info(f"=== 成本计算详情 ===")
        logger.info(f"目标函数值(ObjVal): {self.model.ObjVal:,.2f} 元")
        logger.info(f"短缺惩罚成本: {shortage_cost_total:,.2f} 元")
        logger.info(f"不含短缺的总成本: {total_cost_excluding_shortage:,.2f} 元")
        logger.info(f"短缺成本占目标函数值比例: {shortage_cost_total / self.model.ObjVal * 100:.2f}%")
        logger.info(f"=== 生产量分析 ===")
        logger.info(f"1周内实际氢气生产量: {total_h2_production:,.0f} kg")
        logger.info(f"1周内实际MTJ生产量: {total_mtj_production:,.0f} kg")
        logger.info(f"理论电力消耗: {theoretical_electricity_consumption:,.0f} MWh")
        logger.info(f"1周电力成本: {weekly_electricity_cost:,.2f} 元")
        logger.info(f"年化系数: {operation_expansion_factor}")
        logger.info(f"现值系数: {present_value_factor}")
        logger.info(f"理论电力成本(20年): {theoretical_electricity_cost:,.2f} 元")

        # 计算平准化成本（不含短缺）
        lifecycle_total_production = solution.get('lifecycle_total_production_kg', 1)
        if lifecycle_total_production > 0:
            solution['lifecycle_levelized_cost_excluding_shortage_per_kg'] = total_cost_excluding_shortage / lifecycle_total_production

            # 计算成本分解（基于实际优化结果）
            logger.info(f"生命周期总产量: {lifecycle_total_production:,.0f} kg")
            logger.info(f"生命周期平准化成本_不含短缺: {solution['lifecycle_levelized_cost_excluding_shortage_per_kg']:.3f} 元/kg")

            # === 成本分解分析 ===
            logger.info(f"\n=== 生命周期平准化成本分解分析 ===")

            # 调用现有的成本分解方法（基于实际计算）
            cost_breakdown = self._calculate_cost_breakdown()

            # 计算各组成部分的单位成本（使用正确的键名）
            electricity_cost_total = cost_breakdown.get('electricity_cost', 0)
            electrolyzer_investment_total = cost_breakdown.get('electrolyzer_investment_cost', 0)
            hydrogen_transport_total = cost_breakdown.get('hydrogen_transport_cost', 0)
            hydrogen_pipeline_transport_total = cost_breakdown.get('hydrogen_pipeline_transport_cost', 0)
            hydrogen_storage_investment_total = cost_breakdown.get('h2_storage_investment_cost', 0)
            hydrogen_storage_operation_total = cost_breakdown.get('h2_storage_operation_cost', 0)

            natural_gas_procurement_total = cost_breakdown.get('natural_gas_raw_material_cost', 0)
            natural_gas_transport_total = cost_breakdown.get('ng_transport_cost', 0)

            facility_investment_total = cost_breakdown.get('facility_investment_cost', 0)
            facility_operation_total = cost_breakdown.get('facility_operation_cost', 0)
            mtj_production_total = cost_breakdown.get('production_operational_cost', 0)
            mtj_storage_equipment_total = cost_breakdown.get('storage_equipment_cost', 0)
            mtj_storage_operation_total = cost_breakdown.get('storage_operation_cost', 0)
            transport_operation_total = cost_breakdown.get('transport_operation_cost', 0)

            # 计算单位成本
            electricity_unit = electricity_cost_total / lifecycle_total_production
            electrolyzer_unit = electrolyzer_investment_total / lifecycle_total_production
            h2_transport_unit = hydrogen_transport_total / lifecycle_total_production
            h2_pipeline_transport_unit = hydrogen_pipeline_transport_total / lifecycle_total_production
            h2_storage_investment_unit = hydrogen_storage_investment_total / lifecycle_total_production
            h2_storage_operation_unit = hydrogen_storage_operation_total / lifecycle_total_production

            ng_procurement_unit = natural_gas_procurement_total / lifecycle_total_production
            ng_transport_unit = natural_gas_transport_total / lifecycle_total_production

            facility_investment_unit = facility_investment_total / lifecycle_total_production
            facility_operation_unit = facility_operation_total / lifecycle_total_production
            mtj_production_unit = mtj_production_total / lifecycle_total_production
            mtj_storage_equipment_unit = mtj_storage_equipment_total / lifecycle_total_production
            mtj_storage_operation_unit = mtj_storage_operation_total / lifecycle_total_production
            transport_operation_unit = transport_operation_total / lifecycle_total_production

            # 计算三大成本类别
            hydrogen_related_unit = (electricity_unit + electrolyzer_unit +
                                   h2_transport_unit + h2_pipeline_transport_unit +
                                   h2_storage_investment_unit + h2_storage_operation_unit)
            natural_gas_related_unit = ng_procurement_unit + ng_transport_unit
            mtj_direct_unit = (facility_investment_unit + facility_operation_unit +
                             mtj_production_unit + mtj_storage_equipment_unit + mtj_storage_operation_unit +
                             transport_operation_unit)

            # 输出详细分解
            logger.info(f"1. 氢能相关成本: {hydrogen_related_unit:.3f} 元/kg")
            logger.info(f"   - 电力成本: {electricity_unit:.3f} 元/kg")
            logger.info(f"   - 电解槽投资: {electrolyzer_unit:.3f} 元/kg")
            logger.info(f"   - 氢气卡车运输: {h2_transport_unit:.3f} 元/kg")
            logger.info(f"   - 氢气管道运输: {h2_pipeline_transport_unit:.3f} 元/kg")
            logger.info(f"   - 氢气储存投资: {h2_storage_investment_unit:.3f} 元/kg")
            logger.info(f"   - 氢气储存运营: {h2_storage_operation_unit:.3f} 元/kg")

            logger.info(f"2. 天然气相关成本: {natural_gas_related_unit:.3f} 元/kg")
            logger.info(f"   - 天然气采购: {ng_procurement_unit:.3f} 元/kg")
            logger.info(f"   - 天然气运输: {ng_transport_unit:.3f} 元/kg")

            logger.info(f"3. MTJ直接成本: {mtj_direct_unit:.3f} 元/kg")
            logger.info(f"   - MTJ工厂投资: {facility_investment_unit:.3f} 元/kg")
            logger.info(f"   - MTJ工厂运营: {facility_operation_unit:.3f} 元/kg")
            logger.info(f"   - MTJ生产运营: {mtj_production_unit:.3f} 元/kg")
            logger.info(f"   - MTJ储存设备: {mtj_storage_equipment_unit:.3f} 元/kg")
            logger.info(f"   - MTJ储存运营: {mtj_storage_operation_unit:.3f} 元/kg")
            logger.info(f"   - MTJ运输运营: {transport_operation_unit:.3f} 元/kg")

            # 验证总和
            calculated_total_unit = hydrogen_related_unit + natural_gas_related_unit + mtj_direct_unit
            actual_unit = total_cost_excluding_shortage / lifecycle_total_production

            logger.info(f"")
            logger.info(f"分解成本合计: {calculated_total_unit:.3f} 元/kg")
            logger.info(f"实际平准化成本: {actual_unit:.3f} 元/kg")
            logger.info(f"差额: {calculated_total_unit - actual_unit:.3f} 元/kg")
            logger.info(f"=======================")
        else:
            solution['lifecycle_levelized_cost_excluding_shortage_per_kg'] = 0

        # 保存不含短缺成本的总成本
        solution['objective_value_lifecycle_total_excluding_shortage'] = total_cost_excluding_shortage

        return solution
    
    def _calculate_cost_breakdown(self) -> Dict:
        """计算生命周期平准化成本分解（基于20年总产量）"""
        breakdown = {}
        
        # 使用与目标函数完全相同的生命周期系数计算逻辑
        discount_rate = self.economic_params['discount_rate']
        project_lifespan = self.economic_params['project_lifespan']

        # 计算现值系数（与目标函数保持完全一致）
        if discount_rate == 0:
            present_value_factor = project_lifespan
        else:
            present_value_factor = (1 - (1 + discount_rate)**(-project_lifespan)) / discount_rate

        # 运营成本扩展系数（与目标函数保持一致）
        operation_expansion_factor = 52.0 / self.time_horizon_weeks  # 年化系数

        # 计算与目标函数完全相同的生命周期运营成本系数
        lifecycle_operation_factor = operation_expansion_factor * present_value_factor
        
        # 计算20年总产量
        total_production_in_window = sum(
            self.production_vars[(location, tech, hour)].x
            for location in self.locations
            for tech in self.technologies  
                for hour in range(self.total_hours)
            if (location, tech, hour) in self.production_vars and self.production_vars[(location, tech, hour)].x > 0
        )
        annual_production = total_production_in_window * operation_expansion_factor
        # 使用现值系数而不是简单project_lifespan倍数
        lifecycle_total_production = annual_production * present_value_factor
        
        # MTJ生产设施成本分解
        facility_investment_total = 0
        facility_operation_total = 0
        
        for location in self.locations:
            for tech in self.technologies:
                if (location, tech) in self.facility_vars and self.facility_vars[(location, tech)].x > 0.5:
                    # 使用与目标函数相同的配置参数（避免重复定义）
                    fac_cfg = self.config.get('facility_lcoe_parameters', {}) or {}
                    fixed_capex = fac_cfg.get('fixed_capex', 20000000)  # 固定投资
                    variable_capex_per_capacity = fac_cfg.get('variable_capex_per_capacity', 20000)  # 单位产能投资
                    fixed_opex_annual = fac_cfg.get('fixed_opex_annual', 1000000)  # 固定运营成本
                    
                    # 投资成本
                    variable_investment = (self.facility_capacity_vars[(location, tech)].x * variable_capex_per_capacity * 
                                         self.economic_params['mtj_plant_capacity_factor'])
                    facility_investment_total += fixed_capex + variable_investment
                    
                    # 运营成本（20年现值）
                    facility_operation_total += fixed_opex_annual * present_value_factor
        
        breakdown["facility_investment_cost"] = facility_investment_total
        breakdown["facility_operation_cost"] = facility_operation_total
        
        # 生产运营成本（20年现值）- 使用配置文件参数
        variable_opex_per_kg = fac_cfg.get('variable_opex_per_kg', 0.3)  # 元/kg - 从配置读取，默认0.3
        logger.info(f"成本分解计算中的MTJ变动运营成本: {variable_opex_per_kg}元/kg")
        # 应用生命周期系数，与目标函数保持一致
        production_cost_total = total_production_in_window * variable_opex_per_kg * lifecycle_operation_factor
        breakdown["production_operational_cost"] = production_cost_total
        
        # 运输成本分解
        transport_equipment_total = 0
        transport_operation_total = 0
        for (location, airport, week), var in self.transport_vars.items():
            if var.x > 0:
                transport_equipment_total += var.x * 0  # 设备投资已包含在平准化运输成本中
                distance_km = self._calculate_distance(location, airport)
                transport_operation_total += (var.x *
                    self._calculate_mtj_transport_cost_by_distance(distance_km) *
                    lifecycle_operation_factor)  # 基于运输理论公式的20年运营成本现值
        
        breakdown["transport_equipment_cost"] = transport_equipment_total
        breakdown["transport_operation_cost"] = transport_operation_total
        
        # 储存成本分解
        storage_equipment_total = sum(
            var.x * 10 for var in self.storage_vars.values() if var.x > 0
        )
        storage_operation_total = sum(
            var.x * self._calculate_total_storage_cost_per_kg_hour() * 
            operation_expansion_factor * present_value_factor
            for var in self.storage_vars.values() if var.x > 0
        )
        
        breakdown["storage_equipment_cost"] = storage_equipment_total
        breakdown["storage_operation_cost"] = storage_operation_total
        
        # 氢气储存运营成本（目标函数中的h2_storage_operation）
        h2_storage_operation_total = 0
        if hasattr(self, 'hydrogen_storage_vars'):
            h2_storage_operation_total = sum(
                self.hydrogen_storage_vars[(location, hour)].x * 
                self._calculate_total_storage_cost_per_kg_hour() * operation_expansion_factor * present_value_factor
                for location in self.locations
                for hour in range(self.total_hours + 1)
                if (location, hour) in self.hydrogen_storage_vars and self.hydrogen_storage_vars[(location, hour)].x > 0
            )
        breakdown["h2_storage_operation_cost"] = h2_storage_operation_total
        
        # 电解槽成本
        electrolyzer_capex_raw = self.config['equipment_raw_costs']['electrolyzer']['capex_raw']
        electrolyzer_investment_total = sum(
            self.electrolyzer_capacity_vars[location].x * electrolyzer_capex_raw * 
            self.economic_params['electrolyzer_capacity_factor']
            for location in self.locations
            if location in self.electrolyzer_capacity_vars and self.electrolyzer_capacity_vars[location].x > 0
        )
        breakdown["electrolyzer_investment_cost"] = electrolyzer_investment_total
        
        # 氢气储存投资成本（目标函数中的h2_storage_investment）
        h2_storage_investment_total = 0
        if hasattr(self, 'hydrogen_storage_vars'):
            max_h2_storage = max(
                (self.hydrogen_storage_vars[(location, hour)].x 
                 for location in self.locations
                 for hour in range(self.total_hours + 1)
                 if (location, hour) in self.hydrogen_storage_vars and self.hydrogen_storage_vars[(location, hour)].x > 0),
                default=0
            )
            # 使用与目标函数相同的成本参数
            storage_cfg = self.config.get('storage_parameters', {}) or {}
            h2_storage_unit_cost = float(
                self.config.get('unified_costs', {}).get('storage', {}).get('hydrogen_equipment_cost_yuan_per_kg') or
                storage_cfg.get('hydrogen_equipment_unit_cost_yuan_per_kg', 20)
            )
            h2_storage_investment_total = max_h2_storage * h2_storage_unit_cost
        breakdown["h2_storage_investment_cost"] = h2_storage_investment_total
        
        # 氢气运输投资成本（目标函数中的hydrogen_transport_investment）
        hydrogen_transport_investment_total = 0  # 目标函数中设为0，已包含在平准化运输成本中
        breakdown["hydrogen_transport_investment_cost"] = hydrogen_transport_investment_total
        
        # 天然气运输投资成本（目标函数中的ng_transport_investment）  
        ng_transport_investment_total = 0  # 目标函数中设为0，已包含在平准化运输成本中
        breakdown["ng_transport_investment_cost"] = ng_transport_investment_total
        
        # 制氢运营成本（20年现值）
        hydrogen_production_cost_total = 0
        if hasattr(self, 'hydrogen_production_vars'):
            total_h2_production = sum(
                var.x for var in self.hydrogen_production_vars.values() if var.x > 0
        )
            # 使用统一成本配置的氢气生产成本，与目标函数保持一致
            hydrogen_production_unit_cost = float(
                self.config.get('unified_costs', {}).get('production', {}).get('hydrogen_internal_cost_yuan_per_kg', 0)
            )
            hydrogen_production_cost_total = total_h2_production * hydrogen_production_unit_cost * lifecycle_operation_factor
        breakdown["hydrogen_production_cost"] = hydrogen_production_cost_total
        
        # 电解制氢电力成本（20年现值）
        electricity_cost_total = 0
        if hasattr(self, 'hydrogen_production_vars'):
            total_h2_production = sum(
                var.x for var in self.hydrogen_production_vars.values() if var.x > 0
            )
            # 计算总电力消耗成本（MWh）
            total_electricity_consumption_mwh = total_h2_production * self.costs['electrolysis_power_consumption'] / 1000
            # 应用扩展系数和现值系数，保持与其他成本计算的一致性
            electricity_cost_total = total_electricity_consumption_mwh * self.costs['renewable_electricity_cost_yuan_per_mwh'] * lifecycle_operation_factor
        breakdown["electricity_cost"] = electricity_cost_total
        
        # 氢气运输成本（20年现值）
        hydrogen_transport_cost_total = 0
        if hasattr(self, 'hydrogen_transport_vars'):
            for (h_loc, mtj_loc), var in self.hydrogen_transport_vars.items():
                if var.x > 0:
                    distance_km = self._calculate_location_distance(h_loc, mtj_loc)
                    unit_cost = self._calculate_hydrogen_transport_cost_by_distance(distance_km)
                    hydrogen_transport_cost_total += var.x * unit_cost
            hydrogen_transport_cost_total *= lifecycle_operation_factor
        breakdown["hydrogen_transport_cost"] = hydrogen_transport_cost_total
        
        # 氢能管道运输成本（20年现值）
        hydrogen_pipeline_transport_cost_total = 0
        hydrogen_pipeline_investment_cost_total = 0
        if hasattr(self, 'hydrogen_pipeline_transport_vars') and self.hydrogen_pipeline_transport_vars:
            # 管道运输运营成本（已更新为周级变量）
            for (h2_loc, mtj_loc), var in self.hydrogen_pipeline_transport_vars.items():
                if var.x > 0:
                    distance_km = self._calculate_location_distance(h2_loc, mtj_loc)
                    unit_cost = self._calculate_hydrogen_pipeline_cost_by_distance(distance_km)
                    hydrogen_pipeline_transport_cost_total += var.x * unit_cost
            hydrogen_pipeline_transport_cost_total *= lifecycle_operation_factor
            
            # 氢气管道建设投资成本已在成本分析引擎中考虑，此处不重复计算
            # if hasattr(self, 'hydrogen_pipeline_facility_vars'):
            #     pipeline_capex = self.config.get('costs', {}).get('hydrogen_pipeline_costs', {}).get('capex_yuan_per_km', 5000000)
            #     for (h2_loc, mtj_loc), var in self.hydrogen_pipeline_facility_vars.items():
            #         if var.x > 0.5:  # 建设了管道
            #             distance_km = self._calculate_location_distance(h2_loc, mtj_loc)
            #             hydrogen_pipeline_investment_cost_total += distance_km * pipeline_capex
            hydrogen_pipeline_investment_cost_total = 0  # 设为0，避免重复计算
        
        breakdown["hydrogen_pipeline_transport_cost"] = hydrogen_pipeline_transport_cost_total
        breakdown["hydrogen_pipeline_investment_cost"] = hydrogen_pipeline_investment_cost_total
        
        # 天然气运输成本（20年现值）- 使用与目标函数相同的复杂计算逻辑
        ng_transport_cost_total = self._calculate_unified_ng_transport_cost(
            operation_expansion_factor, present_value_factor
        )

        # 额外调试：检查天然气运输变量实际值
        if hasattr(self, 'ng_transport_vars'):
            ng_transport_total_volume = 0.0
            ng_transport_active_vars = 0
            for var_key, var in self.ng_transport_vars.items():
                if hasattr(var, 'x') and var.x > 0:
                    ng_transport_total_volume += var.x
                    ng_transport_active_vars += 1
            logger.info(f"天然气运输调试: 总运输量={ng_transport_total_volume:.2f} m³/week, 活跃变量={ng_transport_active_vars}个")
            logger.info(f"天然气运输成本计算结果: {ng_transport_cost_total:.2f} 元")
        else:
            logger.info("天然气运输调试: 没有天然气运输变量")
        breakdown["ng_transport_cost"] = ng_transport_cost_total
        
        # 天然气原料成本（20年现值）- 直接复制目标函数中的计算逻辑
        # 目标函数中是: natural_gas_cost = self._calculate_natural_gas_cost() * lifecycle_operation_factor
        # 但_calculate_natural_gas_cost()在求解后无法正确访问变量值，所以直接计算

        natural_gas_cost_total = 0

        # 获取天然气价格和技术参数
        ng_price_per_10k_m3 = None
        for pipeline_id, pipeline_data in self.ng_pipeline_sources.items():
            price = pipeline_data.get('natural_gas_price_yuan_per_10k_m3', None)
            if price is not None:
                ng_price_per_10k_m3 = price
                break

        if ng_price_per_10k_m3 is not None:
            # 基于实际求解结果计算天然气消耗量和成本
            total_ng_consumption = 0  # m³

            # 遍历所有MTJ生产活动，计算天然气消耗量
            for location in self.locations:
                for tech in self.technologies:
                    tech_info = self.technologies.get(tech, {})
                    ng_consumption_ratio = tech_info.get('natural_gas_consumption_m3_per_kg_mtj', 0)

                    if ng_consumption_ratio > 0:
                        location_production = 0
                        for hour in range(self.total_hours):
                            # 检查生产变量（优先检查MTJ生产变量）
                            production_value = 0
                            if hasattr(self, 'mtj_production_vars') and (location, tech, hour) in self.mtj_production_vars:
                                var = self.mtj_production_vars[(location, tech, hour)]
                                if hasattr(var, 'x'):
                                    production_value = var.x
                            elif (location, tech, hour) in self.production_vars:
                                var = self.production_vars[(location, tech, hour)]
                                if hasattr(var, 'x'):
                                    production_value = var.x

                            location_production += production_value

                        if location_production > 0:
                            location_ng_consumption = location_production * ng_consumption_ratio
                            location_ng_cost = location_ng_consumption * ng_price_per_10k_m3 / 10000
                            total_ng_consumption += location_ng_consumption
                            natural_gas_cost_total += location_ng_cost
                            logger.info(f"Location {location}, Tech {tech}: 生产量={location_production:.0f}kg, 天然气消耗={location_ng_consumption:.0f}m³, 成本={location_ng_cost:.2f}元")

            logger.info(f"总天然气消耗量: {total_ng_consumption:.0f} m³, 总成本: {natural_gas_cost_total:.2f} 元")

        # 应用生命周期系数
        natural_gas_cost_total *= lifecycle_operation_factor

        # 对比调试
        old_natural_gas_cost = self._calculate_actual_natural_gas_cost() * lifecycle_operation_factor
        logger.info(f"天然气成本调试: 新方法(直接计算)={natural_gas_cost_total:.2f}元, 旧方法={old_natural_gas_cost:.2f}元, 差异={(natural_gas_cost_total-old_natural_gas_cost):.2f}元")

        breakdown["natural_gas_raw_material_cost"] = natural_gas_cost_total
        
        # 短缺惩罚成本（20年现值）
        shortage_cost_total = 0
        if hasattr(self, 'shortage_vars'):
            shortage_cost_total = sum(
                var.x * self.costs['shortage_penalty_yuan_per_kg']
                for var in self.shortage_vars.values()
            if var.x > 0
            ) * lifecycle_operation_factor
        breakdown["shortage_penalty_cost"] = shortage_cost_total
        
        # 期末库存处置成本（目标函数中的final_inventory_cost）
        final_inventory_cost_total = 0
        discount_rate = self.economic_params['discount_rate']
        project_lifespan = self.economic_params['project_lifespan']
        obj_cfg = self.config.get('objective_parameters', {}) or {}
        disposal_cost_per_kg = float(obj_cfg.get('final_inventory_disposal_cost_per_kg', 100))
        
        if hasattr(self, 'storage_vars'):
            final_inventory_cost_total = sum(
                self.storage_vars[(location, self.total_hours)].x * disposal_cost_per_kg * operation_expansion_factor * 
                (1 + discount_rate)**(-project_lifespan)  # 20年后处置成本的现值
                for location in self.locations
                if (location, self.total_hours) in self.storage_vars and self.storage_vars[(location, self.total_hours)].x > 0
            )
        breakdown["final_inventory_disposal_cost"] = final_inventory_cost_total
        
        # 计算总的生命周期成本（排除缺货惩罚成本）- 明确列出所有成本项
        total_lifecycle_cost = (
            # 投资成本
            breakdown.get("facility_investment_cost", 0) +
            breakdown.get("transport_equipment_cost", 0) +
            breakdown.get("storage_equipment_cost", 0) +
            breakdown.get("electrolyzer_investment_cost", 0) +
            breakdown.get("h2_storage_investment_cost", 0) +
            breakdown.get("hydrogen_transport_investment_cost", 0) +
            breakdown.get("ng_transport_investment_cost", 0) +
            breakdown.get("hydrogen_pipeline_investment_cost", 0) +

            # 运营成本
            breakdown.get("facility_operation_cost", 0) +
            breakdown.get("production_operational_cost", 0) +
            breakdown.get("transport_operation_cost", 0) +
            breakdown.get("storage_operation_cost", 0) +
            breakdown.get("hydrogen_production_cost", 0) +
            breakdown.get("electricity_cost", 0) +
            breakdown.get("h2_storage_operation_cost", 0) +
            breakdown.get("hydrogen_transport_cost", 0) +
            breakdown.get("hydrogen_pipeline_transport_cost", 0) +
            breakdown.get("ng_transport_cost", 0) +
            breakdown.get("natural_gas_raw_material_cost", 0) +
            breakdown.get("final_inventory_disposal_cost", 0)
        )
        breakdown["total_lifecycle_cost"] = total_lifecycle_cost

        # 验证修复：手动计算所有成本项总和
        manual_total = (
            breakdown.get("facility_investment_cost", 0) +
            breakdown.get("transport_equipment_cost", 0) +
            breakdown.get("storage_equipment_cost", 0) +
            breakdown.get("electrolyzer_investment_cost", 0) +
            breakdown.get("h2_storage_investment_cost", 0) +
            breakdown.get("hydrogen_transport_investment_cost", 0) +
            breakdown.get("ng_transport_investment_cost", 0) +
            breakdown.get("hydrogen_pipeline_investment_cost", 0) +
            breakdown.get("facility_operation_cost", 0) +
            breakdown.get("production_operational_cost", 0) +
            breakdown.get("transport_operation_cost", 0) +
            breakdown.get("storage_operation_cost", 0) +
            breakdown.get("hydrogen_production_cost", 0) +
            breakdown.get("electricity_cost", 0) +
            breakdown.get("h2_storage_operation_cost", 0) +
            breakdown.get("hydrogen_transport_cost", 0) +
            breakdown.get("hydrogen_pipeline_transport_cost", 0) +
            breakdown.get("ng_transport_cost", 0) +
            breakdown.get("natural_gas_raw_material_cost", 0) +
            breakdown.get("final_inventory_disposal_cost", 0)
        )
        logger.info(f"修复后的total_lifecycle_cost: {total_lifecycle_cost:.2f} 元")
        logger.info(f"手动计算的总成本: {manual_total:.2f} 元")
        logger.info(f"两者差异: {abs(total_lifecycle_cost - manual_total):.2f} 元")

        # 添加关键统计信息
        breakdown["annual_production_kg"] = annual_production
        breakdown["lifecycle_total_production_kg"] = lifecycle_total_production
        breakdown["project_lifespan_years"] = project_lifespan
        breakdown["operation_expansion_factor"] = operation_expansion_factor
        breakdown["present_value_factor"] = present_value_factor
        
        # 计算生命周期平准化成本（每kg平均成本，不包含缺货惩罚成本）
        if lifecycle_total_production > 0:
            breakdown["lifecycle_levelized_cost_per_kg"] = total_lifecycle_cost / lifecycle_total_production
        else:
            breakdown["lifecycle_levelized_cost_per_kg"] = 0
        
        # 计算年化平准化成本（用于比较，不包含缺货惩罚成本）
        if annual_production > 0:
            breakdown["annual_levelized_cost_per_kg"] = (total_lifecycle_cost / project_lifespan) / annual_production
        else:
            breakdown["annual_levelized_cost_per_kg"] = 0

        # 添加详细的成本对比调试输出
        logger.info("\n=== 成本分解详细调试输出 ===")
        logger.info(f"生命周期运营成本系数: {lifecycle_operation_factor:.6f}")
        logger.info(f"  年化系数: {operation_expansion_factor:.6f}")
        logger.info(f"  现值系数: {present_value_factor:.6f}")
        logger.info(f"生命周期总产量: {lifecycle_total_production:,.0f} kg")

        # 显示各成本项的具体数值
        major_cost_items = [
            ("facility_investment_cost", "MTJ设施投资成本"),
            ("facility_operation_cost", "MTJ设施运营成本"),
            ("production_operational_cost", "生产变动运营成本"),
            ("transport_operation_cost", "运输运营成本"),
            ("storage_equipment_cost", "储存设备投资"),
            ("storage_operation_cost", "储存运营成本"),
            ("electrolyzer_investment_cost", "电解槽投资成本"),
            ("hydrogen_production_cost", "制氢运营成本"),
            ("electricity_cost", "电力成本"),
            ("hydrogen_transport_cost", "氢气运输成本"),
            ("hydrogen_pipeline_transport_cost", "氢气管道运输成本"),
            ("hydrogen_pipeline_investment_cost", "氢气管道投资成本"),
            ("ng_transport_cost", "天然气运输成本"),
            ("natural_gas_raw_material_cost", "天然气原料成本"),
            ("h2_storage_investment_cost", "氢气储存投资"),
            ("h2_storage_operation_cost", "氢气储存运营"),
            ("shortage_penalty_cost", "短缺惩罚成本"),
            ("final_inventory_disposal_cost", "期末库存处置成本")
        ]

        logger.info("--- 各项成本明细 (20年生命周期总成本) ---")
        cost_breakdown_total = 0.0
        for cost_key, cost_name in major_cost_items:
            if cost_key in breakdown:
                cost_value = breakdown[cost_key]
                cost_breakdown_total += cost_value if cost_key != 'shortage_penalty_cost' else 0
                unit_cost = cost_value / lifecycle_total_production if lifecycle_total_production > 0 else 0
                logger.info(f"{cost_name}: {cost_value:,.2f} 元 ({unit_cost:.4f} 元/kg)")

        logger.info(f"--- 成本汇总对比 ---")
        logger.info(f"成本分解总计(不含短缺): {cost_breakdown_total:,.2f} 元")
        logger.info(f"成本分解中的total_lifecycle_cost: {total_lifecycle_cost:,.2f} 元")
        logger.info(f"单位成本(不含短缺): {total_lifecycle_cost / lifecycle_total_production:.4f} 元/kg")
        logger.info("=== 成本分解调试输出结束 ===\n")

        return breakdown
    
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
    
    def save_results(self, solution: Dict, output_dir: str):
        """保存求解结果"""
        import json  # 确保json模块可用
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 首先保存基础设施选点信息
        self._save_infrastructure_locations(output_dir, timestamp)
        
        # 从solution中获取不含短缺成本的平准化成本
        lifecycle_levelized_cost_excluding_shortage = solution.get("lifecycle_levelized_cost_excluding_shortage_per_kg", 0)

        # 直接从优化模型计算单位成本，不依赖cost_breakdown
        unit_costs = self._calculate_unit_costs_from_optimization(solution)
        logger.info("直接从优化模型计算单位成本数据用于optimization_summary")
        
        results_summary = {
            "优化状态": [solution.get("optimization_status", "未知")],
            "生命周期总成本(元)": [solution.get("objective_value_lifecycle_total_excluding_shortage", 0)],
            "年化成本(元/年)": [solution.get("objective_value_lifecycle_total_excluding_shortage", 0) / solution.get("project_lifespan_years", 20)],
            "生命周期平准化成本(元/kg)": [solution.get("lifecycle_levelized_cost_per_kg", 0)],
            "年化平准化成本(元/kg)": [solution.get("annual_levelized_cost_per_kg", 0)],
            "生命周期平准化成本_不含短缺(元/kg)": [lifecycle_levelized_cost_excluding_shortage],
            
            # 简化成本信息（基于目标函数值，不依赖详细分解）
            "MTJ工厂建设投资(元)": [0],
            "电解槽建设投资(元)": [0],
            "运输设备投资(元)": [0],
            "MTJ储存设备投资(元)": [0],
            "氢气储存设备投资(元)": [0],
            "氢气运输设备投资(元)": [0],
            "天然气运输设备投资(元)": [0],
            "MTJ工厂运营成本(元)": [0],
            "MTJ生产运营成本(元)": [0],
            "氢气制取成本(元)": [0],
            "氢气罐车运输成本(元)": [0],
            "氢能管道运输成本(元)": [0],
            "氢能管道建设投资(元)": [0],
            "天然气运输成本(元)": [0],
            "天然气原料成本(元)": [0],
            "MTJ运输运营成本(元)": [0],
            "MTJ储存运营成本(元)": [0],
            "氢气储存运营成本(元)": [0],
            "电力成本(元)": [0],
            "期末库存处置成本(元)": [0],
            "短缺惩罚成本(元)": [solution.get("shortage_penalty_cost", 0)],
            
            # 统计信息
            "建设设施数": [len(solution.get("facilities", {}))],
            "运输路线数": [len(solution.get("transport_plan", {}))],
            "年产量(kg)": [solution.get("annual_production_kg", 0)],
            "20年总产量(kg)": [solution.get("lifecycle_total_production_kg", 0)],
            "优化时长(周)": [self.time_horizon_weeks],
            "总时段数(小时)": [self.total_hours],
            "项目期限(年)": [solution.get("project_lifespan_years", 20)]
        }
        
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

        # 保存天然气运输计划
        ng_transport_data = []
        for transport_id, info in solution.get("ng_transport", {}).items():
            ng_transport_data.append({
                "运输ID": transport_id,
                "起点": info.get("from_location", ""),
                "终点": info.get("to_location", ""),
                "天": info.get("day", 0),
                "天然气运输量(m3)": info.get("transport_m3_ng", 0),
                "距离(km)": info.get("distance_km", 0),
                "起点纬度": info.get("from_latitude", 0),
                "起点经度": info.get("from_longitude", 0),
                "终点纬度": info.get("to_latitude", 0),
                "终点经度": info.get("to_longitude", 0),
                "运输类型": info.get("transport_type", "NG"),
                "运输方式": info.get("transport_mode", "truck")
            })
        
        if ng_transport_data:
            ng_transport_df = pd.DataFrame(ng_transport_data)
            ng_transport_path = os.path.join(output_dir, f"ng_transport_plan_{timestamp}.csv")
            ng_transport_df.to_csv(ng_transport_path, index=False, encoding='utf-8-sig')
            print(f"天然气运输计划保存到: {ng_transport_path}")

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
            
            all_transport_summary.append({
                "路径ID": transport_id,
                "起点": info.get("from_location", ""),
                "终点": info.get("to_location", ""),
                "起点类型": "氢气生产站",
                "终点类型": "MTJ工厂",
                "距离(km)": info.get("distance_km", 0),
                "起点坐标": f"({info.get('from_latitude', 0):.4f}, {info.get('from_longitude', 0):.4f})",
                "终点坐标": f"({info.get('to_latitude', 0):.4f}, {info.get('to_longitude', 0):.4f})",
                "路径坐标": route_coords_str,  # 新增：真实路径坐标
                "货物类型": "氢气",
                "运输方式": info.get("transport_mode", "truck"),
                "日运输量(kg)": info.get("transport_kg_h2", 0),
                "时间单位": "天"
            })
        
        # 添加天然气运输路径
        for transport_id, info in solution.get("ng_transport", {}).items():
            all_transport_summary.append({
                "路径ID": transport_id,
                "起点": info.get("from_location", ""),
                "终点": info.get("to_location", ""),
                "起点类型": "天然气管道",
                "终点类型": "MTJ工厂",
                "距离(km)": info.get("distance_km", 0),
                "起点坐标": f"({info.get('from_latitude', 0):.4f}, {info.get('from_longitude', 0):.4f})",
                "终点坐标": f"({info.get('to_latitude', 0):.4f}, {info.get('to_longitude', 0):.4f})",
                "货物类型": "天然气",
                "运输方式": info.get("transport_mode", "truck"),
                "日运输量(m3)": info.get("transport_m3_ng", 0),
                "时间单位": "天"
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
        
        # 2. 保存LNG接收站信息
        lng_data = []
        for location, info in self.locations.items():
            if info['type'] == 'lng_terminal':
                lng_data.append({
                    "位置ID": location,
                    "原始接收站ID": info.get('original_terminal_id', ''),
                    "纬度": info['latitude'],
                    "经度": info['longitude'],
                    "LNG处理能力(万立方米/年)": info.get('lng_capacity', 0),
                    "坐标": f"({info['latitude']:.4f}, {info['longitude']:.4f})"
                })
        
        if lng_data:
            lng_df = pd.DataFrame(lng_data)
            lng_path = os.path.join(output_dir, f"lng_terminals_{timestamp}.csv")
            lng_df.to_csv(lng_path, index=False, encoding='utf-8-sig')
            print(f"LNG接收站信息保存到: {lng_path}")
        
        # 3. 保存天然气管道信息
        ng_pipeline_data = []
        for location, info in self.locations.items():
            if info['type'] == 'ng_pipeline':
                ng_pipeline_data.append({
                    "位置ID": location,
                    "管道ID": info.get('pipeline_id', ''),
                    "管道名称": info.get('pipeline_name', ''),
                    "运营商": info.get('operator', ''),
                    "纬度": info['latitude'],
                    "经度": info['longitude'],
                    "输送能力(万立方米/天)": info.get('capacity_mcm_per_day', 0),
                    "坐标": f"({info['latitude']:.4f}, {info['longitude']:.4f})"
                })
        
        if ng_pipeline_data:
            ng_pipeline_df = pd.DataFrame(ng_pipeline_data)
            ng_pipeline_path = os.path.join(output_dir, f"ng_pipelines_{timestamp}.csv")
            ng_pipeline_df.to_csv(ng_pipeline_path, index=False, encoding='utf-8-sig')
            print(f"天然气管道信息保存到: {ng_pipeline_path}")
        
        # 4. 保存机场信息
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
                'lng_terminal': 'LNG接收站',
                'ng_pipeline': '天然气管道',
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
                'lng_terminal': 'LNG接收站',
                'ng_pipeline': '天然气管道',
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
        elif location_type == 'lng_terminal':
            capacity = location_info.get('lng_capacity', 0)
            return f"处理能力{capacity}万立方米/年"
        elif location_type == 'ng_pipeline':
            capacity = location_info.get('capacity_mcm_per_day', 0)
            name = location_info.get('pipeline_name', '')
            return f"{name}, {capacity}万立方米/天"
        elif location_type == 'airport':
            # 这里可以添加机场的主要参数
            return "航空燃料需求"
        else:
            return "其他"

    def _load_ng_pipeline_data(self):
        """加载天然气管段数据（使用预处理的容量数据，支持缓存）"""
        try:
            # 导入缓存管理器
            try:
                from .data_cache_manager import cache_manager
            except ImportError:
                from data_cache_manager import cache_manager
            
            project_root = get_project_base_dir()
            
            # 优先使用预处理的容量数据文件
            try:
                preprocessed_file = self._get_data_path('gis_data.ng_pipelines_preprocessed')
                logger.info(f"从配置文件获取预处理管道数据路径: {preprocessed_file}")
            except Exception as e:
                logger.error(f"从配置文件获取预处理管道数据路径失败: {e}")
                preprocessed_file = os.path.join(project_root, "products", "gis_energy_mapping", 
                                               "gis_data_scraper", "scraped_gis_data", 
                                               "natural_gas_pipelines_with_capacity.xlsx")
            
            if os.path.exists(preprocessed_file):
                logger.info("使用预处理的天然气管道容量数据")
                integrated_df = pd.read_excel(preprocessed_file)
                # 过滤北京500km范围内的管道
                integrated_df = integrated_df[integrated_df.apply(
                    lambda row: is_within_beijing_range(
                        float(row.get('center_latitude') or row.get('Lat', 0)), 
                        float(row.get('center_longitude') or row.get('Long', 0)), 
                        500
                    ), axis=1
                )]
                logger.info(f"预处理数据过滤后: {len(integrated_df)} 条管道记录")
            else:
                # 备用方案：使用原有的集成数据文件
                logger.warning("预处理容量数据文件不存在，使用原有集成数据")
                try:
                    integrated_file = self._get_data_path('gis_data.ng_pipelines_integrated')
                    logger.info(f"从配置文件获取集成管道数据路径: {integrated_file}")
                except Exception as e:
                    logger.error(f"从配置文件获取集成管道数据路径失败: {e}")
                    integrated_file = os.path.join(project_root, "products", "supply_chain_optimization", 
                                                 "natural_gas_supply_chain_optimization", "data", 
                                                 "integrated_gas_pipeline_price_data_with_coords.csv")
                if not os.path.exists(integrated_file):
                    logger.error(f"集成天然气数据文件不存在: {integrated_file}")
                    self._load_original_pipeline_data()
                    return

                # 检查缓存是否有效
                if cache_manager.is_cache_valid('ng_pipelines', integrated_file):
                    logger.info("使用缓存的天然气管道数据（500km过滤）")
                    cached_df = cache_manager.load_filtered_data('ng_pipelines')
                    if cached_df is not None:
                        integrated_df = cached_df
                        logger.info(f"从缓存加载天然气管道数据: {len(integrated_df)} 条记录")
                    else:
                        logger.warning("缓存加载失败，执行完整加载")
                        integrated_df = self._load_and_filter_ng_pipeline_data(integrated_file, cache_manager)
                else:
                    logger.info("缓存无效或不存在，执行完整加载和过滤")
                    integrated_df = self._load_and_filter_ng_pipeline_data(integrated_file, cache_manager)

            # 处理过滤后的数据
            for idx, row in integrated_df.iterrows():
                # 处理不同数据源的字段名
                if 'pipeline_id' in row:
                    pipeline_id = row['pipeline_id']
                    pipeline_name = row.get('pipeline_name', row.get('Name', f'pipeline_{idx}'))
                else:
                    pipeline_id = f'pipeline_{idx}'
                    pipeline_name = row.get('Name', f'管道_{idx}')
                
                # 获取坐标（支持不同字段名）
                lat = float(row.get('center_latitude') or row.get('lat') or row.get('Lat', 0))
                lon = float(row.get('center_longitude') or row.get('lon') or row.get('Long', 0))
                
                # 获取预处理的容量数据，如果不存在则使用原始数据
                if 'effective_daily_capacity_m3_per_day' in row and pd.notna(row['effective_daily_capacity_m3_per_day']):
                    # 使用预处理的有效日处理能力
                    capacity_mcm_per_day = row['capacity_mcm_per_day']
                    effective_daily_capacity_m3_per_day = row['effective_daily_capacity_m3_per_day']
                    supply_reliability = row['supply_reliability']
                    logger.debug(f"管道 {pipeline_id} 使用预处理容量: {effective_daily_capacity_m3_per_day/10000:.2f} 万m³/天")
                else:
                    # 备用：使用原有数据计算
                    capacity_mcm_per_day = row.get('capacity_mcm_per_day', 0)
                    supply_reliability = row.get('supply_reliability', 0.95)
                    effective_daily_capacity_m3_per_day = capacity_mcm_per_day * 10000 * supply_reliability
                    logger.debug(f"管道 {pipeline_id} 使用原始数据计算容量: {effective_daily_capacity_m3_per_day/10000:.2f} 万m³/天")
                
                self.ng_pipeline_sources[pipeline_id] = {
                    'name': pipeline_name,
                    'operator': row.get('operator', row.get('Operator', '未知')),
                    'status': row.get('status', row.get('Status', 'Operating')),
                    'year_online': row.get('year_online', row.get('YearOnline', 2020)),
                    'capacity_mcm_per_day': capacity_mcm_per_day,
                    'effective_daily_capacity_m3_per_day': effective_daily_capacity_m3_per_day,  # 新增预处理字段
                    'length_km': row.get('length_km', row.get('Shape__Length', 0)),
                    'natural_gas_price_yuan_per_10k_m3': row.get('natural_gas_price_yuan_per_10k_m3', 3.0),
                    'pipeline_cost_yuan_per_mcm': row.get('pipeline_cost_yuan_per_mcm', 200),
                    'transport_cost_yuan_per_mcm_km': row.get('transport_cost_yuan_per_mcm_km', 1.5),
                    'supply_reliability': supply_reliability,
                    # 添加坐标信息
                    'center_latitude': lat,
                    'center_longitude': lon,
                    'lat': lat,
                    'lon': lon,
                    'start_latitude': row.get('start_latitude', None),
                    'start_longitude': row.get('start_longitude', None),
                    'end_latitude': row.get('end_latitude', None),
                    'end_longitude': row.get('end_longitude', None)
                }

            logger.info(f"成功加载 {len(self.ng_pipeline_sources)} 条天然气管段数据（含价格和坐标信息）")
            if len(integrated_df) > 0:
                logger.info(f"平均天然气价格: {integrated_df['natural_gas_price_yuan_per_10k_m3'].mean():.2f} 元/万立方米")
                # 输出坐标范围用于验证
                lat_min, lat_max = integrated_df['lat'].min(), integrated_df['lat'].max()
                lon_min, lon_max = integrated_df['lon'].min(), integrated_df['lon'].max()
                logger.info(f"管道坐标范围: 纬度 {lat_min:.2f}-{lat_max:.2f}, 经度 {lon_min:.2f}-{lon_max:.2f}")

        except Exception as e:
            logger.error(f"加载集成天然气数据失败: {e}")
            self._load_original_pipeline_data()
    
    def _load_and_filter_ng_pipeline_data(self, integrated_file: str, cache_manager) -> pd.DataFrame:
        """加载并过滤天然气管道数据"""
        integrated_df = pd.read_csv(integrated_file)
        logger.info(f"加载天然气管道原始数据: {len(integrated_df)} 条记录")
        logger.info("注意：模型使用坐标计算运输距离，不依赖管道长度数据")

        # 过滤数据
        filtered_rows = []
        for idx, row in integrated_df.iterrows():
            pipeline_id = row['pipeline_id']
            # 添加坐标信息 - 不使用默认值，确保数据质量
            lat = row.get('center_latitude') or row.get('lat')
            lon = row.get('center_longitude') or row.get('lon')
            
            if lat is None or lon is None or pd.isna(lat) or pd.isna(lon):
                logger.debug(f"管道 {pipeline_id} 缺少有效坐标信息，跳过")
                continue
            
            try:
                lat = float(lat)
                lon = float(lon)
            except (ValueError, TypeError):
                logger.debug(f"管道 {pipeline_id} 坐标数据无效，跳过")
                continue
            
            # 检查是否在北京500公里范围内
            if not is_within_beijing_range(lat, lon, 500):
                pipeline_name = row['pipeline_name']
                distance = calculate_distance_km(lat, lon, 39.9042, 116.4074)
                logger.debug(f"天然气管道 {pipeline_name} 距离北京 {distance:.1f}km，超出500km范围，跳过")
                continue
            
            # 更新行数据中的坐标（确保是浮点数）
            row_copy = row.copy()
            if 'center_latitude' in row_copy:
                row_copy['center_latitude'] = lat
            if 'center_longitude' in row_copy:
                row_copy['center_longitude'] = lon
            row_copy['lat'] = lat
            row_copy['lon'] = lon
            filtered_rows.append(row_copy)
        
        # 创建过滤后的DataFrame
        filtered_df = pd.DataFrame(filtered_rows) if filtered_rows else pd.DataFrame()
        
        logger.info(f"500km范围内的天然气管道: {len(filtered_df)} 条记录")
        
        # 保存到缓存
        if len(filtered_df) > 0:
            cache_manager.save_filtered_data('ng_pipelines', filtered_df, integrated_file)
        
        return filtered_df
            
    def _load_original_pipeline_data(self):
        """加载原始天然气管段数据（备用方法）"""
        try:
            # 使用相对路径的真实GIS数据
            base_dir = get_project_base_dir()
            pipeline_file = os.path.join(base_dir, "products", "gis_energy_mapping", "scraped_gis_data", "natural_gas_pipelines.csv")
            if not os.path.exists(pipeline_file):
                logger.error(f"天然气管段数据文件不存在: {pipeline_file}")
                raise FileNotFoundError(f"无法找到天然气管段数据文件: {pipeline_file}")
                
            pipeline_df = pd.read_csv(pipeline_file)
            logger.info(f"加载原始天然气管段数据: {len(pipeline_df)} 条记录")
            logger.info("注意: 管道长度数据不用于模型计算，实际距离通过坐标计算")
            
            for idx, row in pipeline_df.iterrows():
                pipeline_id = f"pipeline_{idx+1}"
                
                # 处理容量数据 - 将BCF/D转换为万立方米/天
                capacity_raw = row.get('Capacity', 0.0)
                try:
                    capacity_bcf_d = float(capacity_raw) if capacity_raw else 0.0
                    # 1 BCF = 28.3168万立方米
                    capacity_mcm_per_day = capacity_bcf_d * 28.3168
                except (ValueError, TypeError):
                    capacity_mcm_per_day = row.get('capacity_mcm_per_day', None)
                    if capacity_mcm_per_day is None:
                        pipeline_name = row.get('Name', f'管段{idx+1}')
                        logger.error(f"管道 {pipeline_name} 缺少容量数据")
                        continue
                
                # 管道长度数据不用于实际计算，只需要坐标数据
                note = str(row.get('Note', ''))
                length_km = row.get('length_km', 0)  # 默认值，不影响实际计算
                if 'Length:' in note:
                    try:
                        length_str = note.split('Length:')[1].split('km')[0].strip()
                        length_km = float(length_str)
                    except:
                        length_km = 0
                
                self.ng_pipeline_sources[pipeline_id] = {
                    'name': row.get('Name', f'管段{idx+1}'),
                    'operator': row.get('Operator', '未知'),
                    'status': row.get('Status', 'Operating'),
                    'year_online': row.get('YearOnline', 2020),
                    'capacity_mcm_per_day': capacity_mcm_per_day,  # 万立方米/天
                    'length_km': length_km,
                    'natural_gas_price_yuan_per_10k_m3': None,  # 需要从实际数据获取价格
                    'pipeline_cost_yuan_per_mcm': 150 + idx * 10,  # 根据索引调整成本
                    'transport_cost_yuan_per_mcm_km': 0.8,
                    'supply_reliability': 0.92 + (idx % 5) * 0.01,  # 0.92-0.96之间
                    'shape_length': row.get('Shape__Length', 0),
                    'object_id': row.get('ObjectId', idx+1)
                }
                
            logger.info(f"成功加载 {len(self.ng_pipeline_sources)} 条天然气管段数据")
            
        except Exception as e:
            logger.error(f"加载天然气管段数据失败: {e}")
            raise

    def _load_lng_terminal_data(self):
        """加载LNG接收站数据（使用预处理的容量数据，支持缓存）"""
        try:
            # 导入缓存管理器
            try:
                from .data_cache_manager import cache_manager
            except ImportError:
                from data_cache_manager import cache_manager
            
            project_root = get_project_base_dir()
            
            # 优先使用预处理的容量数据文件
            preprocessed_file = os.path.join(project_root, "products", "gis_energy_mapping", 
                                           "gis_data_scraper", "scraped_gis_data", 
                                           "lng_terminals_with_capacity.xlsx")
            
            if os.path.exists(preprocessed_file):
                logger.info("使用预处理的LNG接收站容量数据")
                lng_df = pd.read_excel(preprocessed_file)
                # 过滤北京500km范围内的LNG接收站
                lng_df = lng_df[lng_df.apply(
                    lambda row: is_within_beijing_range(
                        float(row.get('Lat', 0)), 
                        float(row.get('Long', 0)), 
                        500
                    ), axis=1
                )]
                logger.info(f"预处理数据过滤后: {len(lng_df)} 条LNG接收站记录")
            else:
                # 备用方案：使用原有数据文件
                logger.warning("预处理容量数据文件不存在，使用原有数据")
                lng_file = os.path.join(project_root, "products", "gis_energy_mapping", "gis_data_scraper", "scraped_gis_data", "lng_terminals.csv")
                if not os.path.exists(lng_file):
                    logger.error(f"LNG接收站数据文件不存在: {lng_file}")
                    raise FileNotFoundError(f"无法找到LNG接收站数据文件: {lng_file}")
                
                # 检查缓存是否有效
                if cache_manager.is_cache_valid('lng_terminals', lng_file):
                    logger.info("使用缓存的LNG接收站数据（500km过滤）")
                    cached_df = cache_manager.load_filtered_data('lng_terminals')
                    if cached_df is not None:
                        lng_df = cached_df
                        logger.info(f"从缓存加载LNG接收站数据: {len(lng_df)} 条记录")
                    else:
                        logger.warning("缓存加载失败，执行完整加载")
                        lng_df = self._load_and_filter_lng_data(lng_file, cache_manager)
                else:
                    logger.info("缓存无效或不存在，执行完整加载和过滤")
                    lng_df = self._load_and_filter_lng_data(lng_file, cache_manager)
            
            # 处理过滤后的数据
            for idx, row in lng_df.iterrows():
                terminal_id = f"lng_terminal_{idx+1}"
                terminal_name = row.get('Name', f'LNG接收站{idx+1}')
                
                # 获取预处理的容量数据，如果不存在则使用原始数据计算
                if 'effective_daily_capacity_m3_per_day' in row and pd.notna(row['effective_daily_capacity_m3_per_day']):
                    # 使用预处理的容量数据
                    capacity_mcm_per_year = row['lng_capacity_mcm_per_year']
                    effective_daily_capacity_m3_per_day = row['effective_daily_capacity_m3_per_day']
                    operational_efficiency = row['operational_efficiency']
                    logger.debug(f"LNG接收站 {terminal_name} 使用预处理容量: {effective_daily_capacity_m3_per_day/10000:.2f} 万m³/天")
                else:
                    # 备用：使用原始数据计算
                    capacity_raw = row.get('current_capacity__Million_tonne', 0)
                    try:
                        capacity_mt = float(capacity_raw) if capacity_raw else 0.0
                        # 1 Million tonne LNG ≈ 138 万立方米天然气/年
                        capacity_mcm_per_year = capacity_mt * 138
                    except (ValueError, TypeError):
                        # 使用备用容量字段，从配置读取默认值
                        default_lng_capacity = self.config.get('supply_capacity', {}).get('lng_terminal_capacity', {}).get('default_capacity_mcm_per_year', 300)
                        try:
                            capacity_mcm_per_year = float(row.get('Full_capacity__100_MMCM_y_', default_lng_capacity))
                        except:
                            capacity_mcm_per_year = default_lng_capacity  # 使用配置的默认值
                            logger.warning(f"LNG接收站 {terminal_name} 缺少容量数据，使用配置默认值 {default_lng_capacity} 万m³/年")
                    
                    # 计算有效日处理能力
                    operational_efficiency = 0.90  # 默认操作效率
                    daily_capacity_m3 = (capacity_mcm_per_year / 365) * 10000  # 立方米/天
                    effective_daily_capacity_m3_per_day = daily_capacity_m3 * operational_efficiency
                    logger.debug(f"LNG接收站 {terminal_name} 使用原始数据计算容量: {effective_daily_capacity_m3_per_day/10000:.2f} 万m³/天")
                
                # 获取坐标
                lat = float(row.get('Lat', 0))
                lon = float(row.get('Long', 0))
                
                self.lng_terminals[terminal_id] = {
                    'name': terminal_name,
                    'chinese_name': row.get('ChineseName', ''),
                    'location': row.get('Location', ''),
                    'capacity_mcm_per_year': capacity_mcm_per_year,  # 万立方米/年
                    'effective_daily_capacity_m3_per_day': effective_daily_capacity_m3_per_day,  # 新增预处理字段
                    'operational_efficiency': operational_efficiency,  # 操作效率
                    'operator': row.get('Operator', '未知'),
                    'status': row.get('Status', 'Operating'),
                    'year_online': row.get('YearOnline', 2020),
                    'cost_yuan_per_mcm': 200 + idx * 15,  # 根据索引调整成本
                    'lat': lat,
                    'lon': lon,
                    'berths': row.get('Berths', ''),
                    'gas_type_source': row.get('Gas_type_source', ''),
                    'operational_status': row.get('Status', '运营中'),
                    'object_id': row.get('ObjectId', idx+1)
                }
                
            logger.info(f"成功加载 {len(self.lng_terminals)} 条LNG接收站数据")
            
            # 计算LNG接收站容量的平均值
            if self.lng_terminals:
                capacity_values = []
                for terminal_id, terminal_info in self.lng_terminals.items():
                    capacity = terminal_info.get('capacity_mcm_per_year', 0)
                    if capacity > 0:  # 只包含有效的容量值
                        capacity_values.append(capacity)
                
                if capacity_values:
                    self.avg_lng_capacity_mcm_per_year = sum(capacity_values) / len(capacity_values)
                    logger.info(f"计算得出LNG接收站容量平均值: {self.avg_lng_capacity_mcm_per_year:.1f} 万立方米/年")
                    logger.info(f"基于 {len(capacity_values)} 个有效数据计算")
                else:
                    logger.warning("未找到有效的LNG容量数据，使用默认值1000万立方米/年")
            else:
                logger.warning("未加载到任何LNG接收站数据，使用默认容量值1000万立方米/年")
            
        except Exception as e:
            logger.error(f"加载LNG接收站数据失败: {e}")
            raise
    
    def _load_and_filter_lng_data(self, lng_file: str, cache_manager) -> pd.DataFrame:
        """加载并过滤LNG接收站数据"""
        lng_df = pd.read_csv(lng_file)
        logger.info(f"加载LNG接收站原始数据: {len(lng_df)} 条记录")
        
        # 过滤数据
        filtered_rows = []
        for idx, row in lng_df.iterrows():
            # 检查坐标数据质量
            lat = row.get('Lat', None)
            lon = row.get('Long', None)
            
            if lat is None or lon is None or pd.isna(lat) or pd.isna(lon):
                terminal_name = row.get('Name', f'LNG接收站{idx+1}')
                logger.debug(f"LNG接收站 {terminal_name} 缺少有效坐标信息，跳过")
                continue
            
            try:
                lat = float(lat)
                lon = float(lon)
            except (ValueError, TypeError):
                terminal_name = row.get('Name', f'LNG接收站{idx+1}')
                logger.debug(f"LNG接收站 {terminal_name} 坐标数据无效，跳过")
                continue
            
            # 检查是否在北京500公里范围内
            if not is_within_beijing_range(lat, lon, 500):
                terminal_name = row.get('Name', f'LNG接收站{idx+1}')
                distance = calculate_distance_km(lat, lon, 39.9042, 116.4074)
                logger.debug(f"LNG接收站 {terminal_name} 距离北京 {distance:.1f}km，超出500km范围，跳过")
                continue
            
            # 更新行数据中的坐标（确保是浮点数）
            row_copy = row.copy()
            row_copy['Lat'] = lat
            row_copy['Long'] = lon
            filtered_rows.append(row_copy)
        
        # 创建过滤后的DataFrame
        filtered_df = pd.DataFrame(filtered_rows) if filtered_rows else pd.DataFrame()
        
        logger.info(f"500km范围内的LNG接收站: {len(filtered_df)} 条记录")
        
        # 保存到缓存
        if len(filtered_df) > 0:
            cache_manager.save_filtered_data('lng_terminals', filtered_df, lng_file)
        
        return filtered_df
    
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
                'natural_gas_supply_chain': {},
                'electricity_supply': {},
                'total_production_kg': 0,
                'supply_costs': {}
            }
            
            # 1. 分析氢气供应链
            facility_analysis['hydrogen_supply_chain'] = self._analyze_hydrogen_supply_for_location(location, solution)
            
            # 2. 分析天然气供应链  
            facility_analysis['natural_gas_supply_chain'] = self._analyze_natural_gas_supply_for_location(location)
            
            # 3. 分析电力供应（如果有可再生能源）
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
        
        # 检查外部氢气运输
        external_h2_sources = []
        for h_loc in self.hydrogen_locations:
            if h_loc != location:
                # 计算从该氢气源运输的总量
                transport_amount = 0
                for (source, dest), var in self.hydrogen_transport_vars.items():
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
    
    def _analyze_natural_gas_supply_for_location(self, location: str) -> Dict:
        """分析指定位置的天然气供应链"""
        ng_supply = {
            'primary_source': '',
            'source_details': {},
            'transport_mode': '',
            'supply_capacity_m3_per_hour': 0,
            'price_yuan_per_m3': 0,
            'infrastructure': []
        }
        
        location_info = self.locations[location]
        location_type = location_info['type']
        
        if location_type == 'lng_terminal':
            # LNG接收站：直接供应
            ng_supply['primary_source'] = 'LNG接收站直供'
            ng_supply['source_details'] = {
                'source_type': 'lng_terminal',
                'capacity': location_info.get('lng_capacity', 0)
            }
            ng_supply['transport_mode'] = 'pipeline_direct'
            ng_supply['price_yuan_per_m3'] = self._get_natural_gas_price_yuan_per_m3(location)
            
        else:
            # 其他位置：通过管道或运输供应
            # 找最近的天然气源
            min_distance = float('inf')
            best_ng_source = None
            
            for ng_loc in self.ng_locations:
                distance = self._calculate_location_distance(ng_loc, location)
                if distance < min_distance:
                    min_distance = distance
                    best_ng_source = ng_loc
            
            if best_ng_source:
                ng_supply['primary_source'] = f'管道运输来自{best_ng_source}'
                ng_supply['source_details'] = {
                    'source_location': best_ng_source,
                    'source_type': self.locations[best_ng_source]['type'],
                    'transport_distance_km': min_distance
                }
                ng_supply['transport_mode'] = 'pipeline_transport'
                transport_cost = self._calculate_ng_transport_cost_by_distance(min_distance)
                ng_supply['price_yuan_per_m3'] = self._get_natural_gas_price_yuan_per_m3(location, best_ng_source) + transport_cost
        
        return ng_supply
    
    def _get_natural_gas_price_yuan_per_m3(self, location: str = None, source_location: str = None) -> float:
        """
        获取天然气价格，优先使用管道文件中的具体价格数据
        
        Args:
            location: 需求地点（可选）
            source_location: 供应源地点（可选）
            
        Returns:
            float: 天然气价格（元/m³）
            
        优先级：
        1. 如果有管道数据，使用管道文件中的具体价格
        2. 如果没有管道数据，使用配置文件中的默认价格
        """
        # 1. 首先尝试从管道文件中获取价格
        pipeline_price = None
        
        # 遍历所有管道数据，寻找相关的价格信息
        for pipeline_id, pipeline_data in self.ng_pipeline_sources.items():
            price_per_10k_m3 = pipeline_data.get('natural_gas_price_yuan_per_10k_m3', None)
            if price_per_10k_m3 is not None:
                pipeline_price = price_per_10k_m3 / 10000  # 转换为元/m³
                logger.debug(f"从管道 {pipeline_id} 获取天然气价格: {pipeline_price:.3f} 元/m³")
                break
        
        # 2. 如果找到管道价格，使用管道价格
        if pipeline_price is not None:
            return pipeline_price
            
        # 3. 如果没有找到管道价格，使用配置文件默认价格
        config_price = self.costs['natural_gas_price_yuan_per_m3']
        logger.debug(f"使用配置文件默认天然气价格: {config_price:.3f} 元/m³")
        return config_price
    
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
            'natural_gas_cost_yuan': 0,
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
        
        # 天然气成本
        ng_consumption = total_production_kg * tech_info.get('ng_consumption_ratio', 0)
        ng_price = self._get_natural_gas_price_yuan_per_m3(location)
        supply_costs['natural_gas_cost_yuan'] = ng_consumption * ng_price
        
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
            supply_costs['natural_gas_cost_yuan'] + 
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
            'natural_gas_supply_breakdown': {
                'lng_terminal_direct': 0,
                'pipeline_transport': 0
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
            
            # 天然气供应统计
            ng_source = facility_analysis['natural_gas_supply_chain']['primary_source']
            if 'LNG接收站直供' in ng_source:
                summary['natural_gas_supply_breakdown']['lng_terminal_direct'] += 1
            elif '管道运输' in ng_source:
                summary['natural_gas_supply_breakdown']['pipeline_transport'] += 1
            
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

    def _add_simplified_ng_pipeline_constraints(self, location: str, hour: int):
        """添加简化的天然气管道流量限制约束（移除维护停机）"""
        location_info = self.locations[location]
        
        # 计算该地点的天然气需求
        ng_demand = gp.quicksum(
            self.production_vars[(location, tech, hour)] * 
            self.technologies[tech]['ng_consumption_ratio']
            for tech in self.technologies
            if (location, tech, hour) in self.production_vars
        )
        
        if ng_demand.size() == 0:
            return  # 没有需求，跳过
        
        # 根据位置类型设置不同的管道流量限制
        if location_info['type'] == 'lng_terminal':
            # LNG接收站：基于实际处理能力
            lng_capacity = location_info.get('lng_capacity', self.avg_lng_capacity_mcm_per_year)
            if lng_capacity is None or pd.isna(lng_capacity) or lng_capacity <= 0:
                lng_capacity = self.avg_lng_capacity_mcm_per_year
            
            # 简化流量计算：基础流量（移除维护因子）
            base_flow_m3_per_hour = lng_capacity * 1000000 / 8760
            
            # 只考虑压力波动，移除维护停机
            hour_of_day = hour % 24
            if 8 <= hour_of_day <= 20:  # 白天
                pressure_factor = 0.8 + 0.2 * (1 - abs(hour_of_day - 14) / 6)
            else:  # 夜间
                pressure_factor = 0.9 + 0.1 * ((hour % 12) / 12)
            
            max_flow_m3_per_hour = base_flow_m3_per_hour * pressure_factor
            
        elif location_info['type'] == 'airport':
            # 机场：不是天然气供应点，通过运输获得天然气，不添加供应约束
            return  # 直接返回，跳过供应约束
        else:
            # 默认供应能力：从配置文件读取
            supply_config = self.config.get('supply_capacity', {}).get('natural_gas_supply', {})
            max_flow_m3_per_hour = supply_config.get('default_max_flow_m3_per_hour', 10000)
        
        # 添加天然气供应约束
        if max_flow_m3_per_hour > 0:
            self.model.addConstr(
                ng_demand <= max_flow_m3_per_hour,
                name=f"ng_supply_{location}_{hour}"
            )

    def _add_ng_pipeline_daily_capacity_constraints(self):
        """添加天然气管段日最大购入量约束（使用预处理的容量数据）"""
        logger.info("添加天然气管段日最大购入量约束...")
        
        total_days = self.total_hours // 24
        
        # 初始化日处理能力存储字典
        if not hasattr(self, 'ng_daily_capacities'):
            self.ng_daily_capacities = {}
        
        for ng_loc in self.ng_locations:
            # 获取管道信息
            location_info = self.locations.get(ng_loc, {})
            pipeline_id = location_info.get('pipeline_id', '')
            pipeline_data = self.ng_pipeline_sources.get(pipeline_id, {})
            
            # 优先使用预处理的有效日处理能力
            if 'effective_daily_capacity_m3_per_day' in pipeline_data and pipeline_data['effective_daily_capacity_m3_per_day'] > 0:
                effective_daily_capacity = pipeline_data['effective_daily_capacity_m3_per_day']
                daily_capacity_mcm = effective_daily_capacity / 10000  # 转换为万立方米/天用于显示
                reliability = pipeline_data.get('supply_reliability', 0.95)
                logger.debug(f"管道 {ng_loc} 使用预处理容量: {effective_daily_capacity/10000:.2f} 万m³/天")
            else:
                # 备用：使用原有计算方法
                daily_capacity_mcm = pipeline_data.get('capacity_mcm_per_day', 1)  # 默认1万立方米/天
                if daily_capacity_mcm <= 0:
                    daily_capacity_mcm = 1  # 确保有合理的默认值
                
                # 转换为立方米
                daily_capacity_m3 = daily_capacity_mcm * 10000  # 万立方米转立方米
                
                # 考虑管道供应可靠性
                reliability = pipeline_data.get('supply_reliability', 0.95)
                effective_daily_capacity = daily_capacity_m3 * reliability
                logger.debug(f"管道 {ng_loc} 使用原始数据计算容量: {effective_daily_capacity/10000:.2f} 万m³/天")
            
            # 存储日处理能力供后续使用
            self.ng_daily_capacities[ng_loc] = effective_daily_capacity
            
            logger.info(f"管道 {ng_loc} ({pipeline_data.get('name', '未知')}): "
                       f"有效日容量 {effective_daily_capacity/10000:.2f} 万m³/天, "
                       f"可靠性 {reliability:.2%}")
            
            # 为每天添加容量约束
            for day in range(total_days):
                # 计算该天从该管道购入的总天然气量
                daily_total_purchase = gp.quicksum(
                    self.ng_transport_vars[(ng_loc, mtj_loc, day)]
                    for tech in ['pipeline_direct_conversion', 'airport_integrated_conversion', 
                                'lng_to_hplant_conversion', 'integrated_supply_conversion']
                    for mtj_loc in self.non_lng_mtj_locations.get(tech, [])
                    if (ng_loc, mtj_loc, day) in self.ng_transport_vars
                )
                
                # 添加该天从该管道直接消费的天然气量（如果有就地生产）
                day_start_hour = day * 24
                day_end_hour = min((day + 1) * 24, self.total_hours)
                
                daily_direct_consumption = gp.quicksum(
                    self.production_vars[(ng_loc, tech, hour)] * 
                    self.technologies[tech]['ng_consumption_ratio']
                    for tech in self.technologies
                    for hour in range(day_start_hour, day_end_hour)
                    if (ng_loc, tech, hour) in self.production_vars
                )
                
                # 总购入量 = 运输量 + 直接消费量
                total_daily_demand = daily_total_purchase + daily_direct_consumption
                
                if total_daily_demand.size() > 0:
                    self.model.addConstr(
                        total_daily_demand <= effective_daily_capacity,
                        name=f"ng_pipeline_daily_capacity_{ng_loc}_day_{day}"
                    )

    def _add_lng_terminal_daily_capacity_constraints(self):
        """添加LNG接收站日最大供应量约束（使用预处理的容量数据）"""
        logger.info("添加LNG接收站日最大供应量约束...")
        
        total_days = self.total_hours // 24
        
        for lng_loc in self.lng_terminal_locations:
            # 获取LNG接收站信息
            location_info = self.locations.get(lng_loc, {})
            
            # 优先使用预处理的有效日处理能力
            if 'effective_daily_capacity_m3_per_day' in location_info and location_info['effective_daily_capacity_m3_per_day'] > 0:
                effective_daily_capacity = location_info['effective_daily_capacity_m3_per_day']
                lng_capacity_mcm_per_year = location_info.get('capacity_mcm_per_year', 0)
                operational_efficiency = location_info.get('operational_efficiency', 0.90)
                daily_capacity_mcm = effective_daily_capacity / 10000  # 转换为万立方米/天用于显示
                logger.debug(f"LNG接收站 {lng_loc} 使用预处理容量: {effective_daily_capacity/10000:.2f} 万m³/天")
            else:
                # 备用：使用原有计算方法
                lng_capacity_mcm_per_year = location_info.get('lng_capacity', self.avg_lng_capacity_mcm_per_year)  # 万立方米/年
                daily_capacity_mcm = lng_capacity_mcm_per_year / 365  # 转换为日处理能力
                daily_capacity_m3 = daily_capacity_mcm * 10000  # 转换为立方米/天
                
                # 从配置文件读取操作效率参数
                operational_efficiency = self.config.get('operational_parameters', {}).get('operational_efficiency', 0.90)
                effective_daily_capacity = daily_capacity_m3 * operational_efficiency
                logger.debug(f"LNG接收站 {lng_loc} 使用原始数据计算容量: {effective_daily_capacity/10000:.2f} 万m³/天")
            
            # 存储日处理能力供后续使用
            if not hasattr(self, 'ng_daily_capacities'):
                self.ng_daily_capacities = {}
            self.ng_daily_capacities[lng_loc] = effective_daily_capacity
            
            logger.info(f"LNG接收站 {lng_loc}: "
                       f"年处理能力 {lng_capacity_mcm_per_year} 万m³/年, "
                       f"有效日容量 {effective_daily_capacity/10000:.2f} 万m³/天, "
                       f"操作效率 {operational_efficiency:.2%}")
            
            # 为每天添加容量约束
            for day in range(total_days):
                # 计算该天该LNG接收站的总天然气供应量
                day_start_hour = day * 24
                day_end_hour = min((day + 1) * 24, self.total_hours)
                
                # LNG接收站的直接消费（就地生产MTJ）
                daily_direct_consumption = gp.quicksum(
                    self.production_vars[(lng_loc, tech, hour)] * 
                    self.technologies[tech]['ng_consumption_ratio']
                    for tech in self.technologies
                    for hour in range(day_start_hour, day_end_hour)
                    if (lng_loc, tech, hour) in self.production_vars
                )
                
                # LNG接收站向外运输的天然气（通常LNG接收站不向外运输，但为完整性考虑）
                daily_outbound_transport = gp.quicksum(
                    self.ng_transport_vars[(lng_loc, mtj_loc, day)]
                    for tech in ['pipeline_direct_conversion', 'airport_integrated_conversion', 
                                'lng_to_hplant_conversion', 'integrated_supply_conversion']
                    for mtj_loc in self.non_lng_mtj_locations.get(tech, [])
                    if (lng_loc, mtj_loc, day) in self.ng_transport_vars
                )
                
                # 总供应量 = 直接消费 + 向外运输
                total_daily_supply = daily_direct_consumption + daily_outbound_transport
                
                if total_daily_supply.size() > 0:
                    self.model.addConstr(
                        total_daily_supply <= effective_daily_capacity,
                        name=f"lng_terminal_daily_capacity_{lng_loc}_day_{day}"
                    )
    
    
    def _calculate_average_distances(self):
        """计算并更新平均运输距离统计"""
        logger.info("开始计算平均运输距离统计...")
        
        # 计算氢气运输平均距离（可再生能源站到MTJ工厂）
        hydrogen_distances = []
        renewable_locations = [loc for loc, info in self.locations.items() 
                             if info['type'] in ['solar_plant', 'wind_farm']]
        mtj_locations = [loc for loc, info in self.locations.items() 
                        if info['type'] in ['lng_terminal', 'industrial_park', 'port']]
        
        for h_loc in renewable_locations[:5]:  # 限制样本数以节省时间
            for mtj_loc in mtj_locations[:5]:
                try:
                    distance = self._calculate_location_distance(h_loc, mtj_loc)
                    hydrogen_distances.append(distance)
                except Exception as e:
                    logger.warning(f"氢气运输距离计算失败 {h_loc} -> {mtj_loc}: {e}")
        
        if hydrogen_distances:
            self.avg_hydrogen_transport_distance = np.mean(hydrogen_distances)
            logger.info(f"氢气运输平均距离: {self.avg_hydrogen_transport_distance:.1f}km "
                       f"(基于{len(hydrogen_distances)}个样本)")
        else:
            # 从配置文件读取默认氢气运输距离
            distance_config = self.config.get('operational_parameters', {}).get('default_transport_distances', {})
            self.avg_hydrogen_transport_distance = distance_config.get('hydrogen_transport_distance_km', 50)
            logger.warning("无法计算氢气运输平均距离，使用默认值50km")
        
        # 计算天然气运输平均距离（管道到非LNG接收站）
        ng_distances = []
        ng_locations = list(self.ng_pipeline_sources.keys())[:5]  # 天然气源位置
        non_lng_mtj_locations = [loc for loc, info in self.locations.items() 
                               if info['type'] in ['industrial_park', 'port']][:5]
        
        for ng_loc in ng_locations:
            for mtj_loc in non_lng_mtj_locations:
                try:
                    distance = self._calculate_location_distance(ng_loc, mtj_loc)
                    ng_distances.append(distance)
                except Exception as e:
                    logger.warning(f"天然气运输距离计算失败 {ng_loc} -> {mtj_loc}: {e}")
        
        if ng_distances:
            self.avg_ng_transport_distance = np.mean(ng_distances)
            logger.info(f"天然气运输平均距离: {self.avg_ng_transport_distance:.1f}km "
                       f"(基于{len(ng_distances)}个样本)")
        else:
            # 从配置文件读取默认天然气运输距离
            distance_config = self.config.get('operational_parameters', {}).get('default_transport_distances', {})
            self.avg_ng_transport_distance = distance_config.get('ng_transport_distance_km', 80)
            logger.warning("无法计算天然气运输平均距离，使用默认值80km")
        
        # 计算机场运输平均距离
        airport_distances = []
        production_locations = list(self.locations.keys())[:10]  # 限制样本数
        airports = list(self.airports.keys())[:5]
        
        for loc in production_locations:
            for airport in airports:
                try:
                    distance = self._calculate_distance(loc, airport)
                    airport_distances.append(distance)
                except Exception as e:
                    logger.warning(f"机场运输距离计算失败 {loc} -> {airport}: {e}")
        
        if airport_distances:
            avg_airport_distance = np.mean(airport_distances)
            logger.info(f"机场运输平均距离: {avg_airport_distance:.1f}km "
                       f"(基于{len(airport_distances)}个样本)")
        
        logger.info("距离统计计算完成")


if __name__ == '__main__':
    """主执行块"""
    try:
        logger.info("开始执行天然气供应链优化模型...")
        
        # 1. 初始化优化器 (使用1周时间范围以减少内存使用)
        # 设置正确的OSM文件路径
        base_dir = get_project_base_dir()
        osm_file_path = os.path.join(base_dir, "products", "supply_chain_optimization", 
                                   "natural_gas_supply_chain_optimization", "data", "china-latest.osm.pbf")
        
        optimizer = NaturalGasSupplyChainOptimizer(
            time_horizon_weeks=1,
            osm_pbf_path=osm_file_path
        )
        
        # 2. 加载数据
        # 使用内置的真实数据加载逻辑，无需传入额外参数
        # 使用配置文件中的路径加载数据（如果传入airport_excel_path=None，会自动从配置文件获取）
        optimizer.load_data_from_excel(
            airport_excel_path=None  # 从配置文件自动获取路径
        )
        
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
            results_dir = os.path.join(base_dir, "products", "supply_chain_optimization", "natural_gas_supply_chain_optimization", "results")
            os.makedirs(results_dir, exist_ok=True)
            optimizer.save_results(solution, results_dir)
            print(f"\n结果已保存到目录: {results_dir}")
            print("="*50)
        else:
            logger.error("模型求解失败或未返回结果。")

    except Exception as e:
        logger.error(f"模型执行过程中发生严重错误: {e}", exc_info=True)
