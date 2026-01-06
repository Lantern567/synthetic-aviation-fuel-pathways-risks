"""
天然气基供应链优化模型
基于Gurobi求解器的混合整数线性规划模型
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
import gc  # 用于显式垃圾回收，释放大数据对象内存
import psutil  # 用于监控内存使用情况
import logging
from typing import Dict, List, Tuple, Optional
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
    # core/natural_gas_optimization_model.py -> core/ -> src/ -> natural_gas_supply_chain_optimization/ -> supply_chain_optimization/ -> products/ -> 项目根
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))))
    if project_root not in sys.path:
        sys.path.append(project_root)
    # 同时添加src目录到路径，确保routing模块可以被找到
    src_dir = os.path.dirname(os.path.dirname(current_file))
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
    from shared.utils.log_preserver import mount_file_logging
    # 移除对外部成本分析引擎的依赖，直接在优化模型内部计算成本
    create_cost_analyzer = None

# 导入GraphHopper路径规划模块 - 在导入父类之前先导入，避免父类导入失败
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
    # core/natural_gas_optimization_model.py -> core/ -> src/
    src_dir = os.path.dirname(os.path.dirname(current_file))
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
    try:
        from routing.graphhopper_routing_engine import GraphHopperRoutingEngine, GraphHopperDistanceCalculator, DistanceCalculator
    except ImportError as e:
        raise ImportError(f"GraphHopper路径规划模块不可用，必须安装相关依赖: {e}. 请运行: pip install requests")

# 导入父类 - 两步法模型作为基类
try:
    from .natural_gas_optimization_model import NaturalGasSupplyChainOptimizer
except ImportError:
    from natural_gas_optimization_model import NaturalGasSupplyChainOptimizer

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

def get_project_base_dir():
    """
    获取项目根目录的绝对路径
    从当前文件位置向上找到项目根目录

    路径结构:
    project_root/products/supply_chain_optimization/natural_gas_supply_chain_optimization/src/core/natural_gas_optimization_model.py
    需要向上6级目录到达项目根目录

    Returns:
        str: 项目根目录路径
    """
    # 当前文件的绝对路径
    current_file = os.path.abspath(__file__)
    # 向上6级目录: core -> src -> natural_gas_supply_chain_optimization -> supply_chain_optimization -> products -> project_root
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))))
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
        "logs_one_step",  # 一步法专用日志目录
    )
    mount_file_logging(_log_dir, filename_prefix="ng_supply_chain_one_step")  # 一步法专用前缀

    # 额外添加固定名称的log_one_step.txt文件处理器
    log_txt_path = os.path.join(_log_dir, "log_one_step.txt")  # 一步法专用日志文件
    log_txt_handler = logging.FileHandler(log_txt_path, mode='a', encoding='utf-8')
    log_txt_handler.setLevel(logging.INFO)
    log_txt_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    log_txt_handler.setFormatter(log_txt_formatter)

    # 添加到根日志记录器
    root_logger = logging.getLogger()
    root_logger.addHandler(log_txt_handler)

    logger.info(f"日志文件已配置: 按日期命名的日志 + 固定名称log_one_step.txt (一步法专用)")
    logger.info(f"日志目录: {_log_dir}")

except Exception as e:
    # 如果文件日志挂载失败，输出警告但不中断程序
    print(f"警告：文件日志挂载失败: {e}")
    print("将继续使用控制台日志")

class NaturalGasSupplyChainOptimizerOneStep(NaturalGasSupplyChainOptimizer):
    """
    FT一步法天然气供应链优化模型
    继承自两步法模型，复用基础设施代码
    主要差异：
    1. 技术参数：FT直接合成工艺(ng_consumption_ratio: 2.3, efficiency: 0.55)
    2. 决策变量：无氢气生产、无电解槽、无氢气运输变量
    3. 约束条件：无氢气平衡约束、无电解槽约束
    4. 成本计算：简化的成本结构（无氢气相关成本）
    5. 碳排放：FT一步法碳排放计算
    """

    def __init__(self, config_path: str = None, **override_params):
        """
        初始化FT一步法优化器

        Args:
            config_path: 配置文件路径，默认使用项目内置配置文件
            **override_params: 可以通过关键字参数覆盖配置文件中的任何参数
        """
        # 调用父类初始化，继承所有基础设施
        super().__init__(config_path, **override_params)

        # FT一步法模型：不再使用独立的ft_facility_candidates列表
        # 所有位置统一存储在self.locations中，通过'is_ft_candidate'标记区分

        logger.info("FT一步法优化器初始化完成")

    def _log_memory_usage(self, stage_name: str):
        """
        记录当前内存使用情况

        Args:
            stage_name: 记录阶段名称（如"加载excel_data后"）
        """
        try:
            process = psutil.Process(os.getpid())
            mem_info = process.memory_info()
            mem_mb = mem_info.rss / 1024 / 1024
            logger.info(f"[内存监控] {stage_name}: {mem_mb:.2f} MB")
        except Exception as e:
            logger.warning(f"内存监控失败: {e}")

    def load_data(self, airport_data: pd.DataFrame):
        """
        加载数据（FT一步法模型，不需要可再生能源数据）

        Args:
            airport_data: 机场需求数据(周级)
        """
        logger.info("加载优化数据（FT一步法模型）...")

        # 处理机场数据
        self._process_airport_data(airport_data)

        # 加载天然气供应链数据
        self._load_ng_pipeline_data()
        self._load_lng_terminal_data()

        # 生成FT设施候选位置（基于天然气供应可达性）
        self._generate_ft_facility_candidates()

        # 首先定义经济参数（平准化成本计算需要）
        self._define_economic_parameters()

        # 定义成本参数（使用平准化成本方法）
        self._define_costs()

        # 定义生产技术（FT一步法）
        self._define_technologies()

        # 定义运输相关的位置映射
        self._define_transport_locations()

        # 使用GraphHopper路径规划计算平均距离统计
        if self.use_graphhopper_routing:
            self._calculate_average_distances()

        ft_candidate_count = sum(1 for loc in self.locations.values() if loc.get('is_ft_candidate'))
        logger.info(f"数据加载完成: {ft_candidate_count}个FT设施候选位置, {len(self.airports)}个机场, {len(self.ng_pipeline_sources)}条天然气管段, {len(self.lng_terminals)}个LNG接收站")
    
    def load_data_from_excel(self, airport_excel_path: str = None, renewable_data: pd.DataFrame = None):
        """
        从Excel文件加载机场数据（FT一步法专用）

        注意：FT一步法不需要可再生能源数据，renewable_data参数被忽略
        此参数仅为保持与父类接口兼容性

        Args:
            airport_excel_path: 机场数据Excel文件路径，如果为None则从配置文件获取
            renewable_data: 可再生能源数据（FT一步法不使用，参数被忽略）
        """

        # 显式忽略renewable_data参数（FT一步法不需要）
        if renewable_data is not None:
            logger.info("FT一步法模型不使用可再生能源数据，renewable_data参数被忽略")

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

        # FT一步法模型不需要可再生能源数据，直接处理机场和天然气数据

        # 处理机场数据
        self._process_airport_data(airport_data)

        # 加载天然气供应链数据
        self._load_ng_pipeline_data()
        self._load_lng_terminal_data()

        # 生成FT设施候选位置（基于天然气供应可达性）
        self._generate_ft_facility_candidates()
        
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

        ft_candidate_count = sum(1 for loc in self.locations.values() if loc.get('is_ft_candidate'))
        logger.info(f"数据加载完成: {ft_candidate_count}个FT设施候选位置, {len(self.airports)}个机场, {len(self.ng_pipeline_sources)}条天然气管段, {len(self.lng_terminals)}个LNG接收站")

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

            # 立即释放Excel数据，避免内存占用
            del excel_df
            gc.collect()
            self._log_memory_usage("释放excel_df后")

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
        # FT一步法不需要氢气生产位置

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
        logger.info(f"  机场位置: {len(self.airport_locations)} 个")
        logger.info(f"  LNG接收站位置: {len(self.lng_terminal_locations)} 个")
        logger.info(f"  天然气管道位置: {len(self.ng_locations)} 个")
        logger.info(f"  总位置数: {len(self.locations)} 个")

        # 构建MTJ工厂位置映射
        self._build_mtj_locations()

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

        # FT一步法只有一种技术：FT直接转换
        for tech_key in ['ft_direct_conversion']:
            if tech_key in tech_config:
                tech_info = tech_config[tech_key]
                self.technologies[tech_key] = {
                    'name': tech_info['name'],
                    'lcop_yuan_per_kg': base_lcop * complexity_factors[tech_key],
                    'efficiency': tech_info['efficiency'],
                    'ng_consumption_ratio': tech_info['ng_consumption_ratio'],  # FT一步法核心参数
                    # 注意：FT一步法不需要以下两步法字段:
                    # - h2_consumption_ratio: FT工艺内部产氢,无需外部氢气
                    # - methanol_intermediate_ratio: 直接转换,无甲醇中间体
                    'suitable_locations': tech_info['suitable_locations'],
                    'transport_mode': tech_info['transport_mode'],
                    'technology_type': tech_info['technology_type'],
                    'complexity_factor': complexity_factors[tech_key]
                }
        
        logger.info(f"定义了 {len(self.technologies)} 种FT一步法SAF生产技术")
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
            'mtj_plant_lifetime': economic_config['mtj_plant_lifetime'],
            'pipeline_lifetime': economic_config['pipeline_lifetime'],
            'storage_lifetime': economic_config['storage_lifetime'],
            'transport_vehicle_lifetime': economic_config['transport_vehicle_lifetime'],

            # 容量因子 (设备年利用率)
            'mtj_plant_capacity_factor': capacity_factors['mtj_plant_capacity_factor'],
            'pipeline_capacity_factor': capacity_factors['pipeline_capacity_factor'],
            'storage_capacity_factor': capacity_factors['storage_capacity_factor'],
            'transport_capacity_factor': capacity_factors['transport_capacity_factor'],

            # 平准化成本门槛值
            'levelized_cost_threshold_yuan_per_kg': levelized_cost_threshold
        }
    
    def _define_costs(self):
        """定义成本参数（FT一步法模型 - 无需氢气相关成本）"""
        # 首先定义经济参数
        self._define_economic_parameters()

        # 从配置文件加载成本参数
        cost_config = self.config['cost_parameters']
        equipment_costs = self.config['equipment_raw_costs']

        # 定义原始资本和运营成本数据（FT一步法）
        raw_costs = {
            # 原料成本 (元/单位) - 运营成本，无需平准化
            'natural_gas_price_yuan_per_m3': cost_config['raw_materials']['natural_gas_price_yuan_per_m3'],

            # FT反应器原始成本
            'ft_reactor_capex_raw': equipment_costs['ft_reactor']['capex_raw'],
            'ft_reactor_opex_raw': equipment_costs['ft_reactor']['opex_raw'],

            # SAF储存设施原始成本
            'storage_capex_raw': equipment_costs.get('storage', {}).get('capex_raw', 1000),
            'storage_opex_raw': equipment_costs.get('storage', {}).get('opex_raw', 50)
        }

        # 计算平准化成本参数
        discount_rate = self.economic_params['discount_rate']

        # FT反应器平准化成本
        ft_reactor_levelized_cost = self._calculate_levelized_cost(
            capex=raw_costs['ft_reactor_capex_raw'],
            opex_annual=raw_costs['ft_reactor_opex_raw'],
            lifetime_years=self.economic_params.get('ft_reactor_lifetime', 25),
            discount_rate=discount_rate,
            capacity_factor=0.9  # FT反应器利用率
        )

        # 储存设施平准化成本
        storage_levelized_cost = self._calculate_levelized_cost(
            capex=raw_costs['storage_capex_raw'],
            opex_annual=raw_costs['storage_opex_raw'],
            lifetime_years=self.economic_params['storage_lifetime'],
            discount_rate=discount_rate,
            capacity_factor=self.economic_params['storage_capacity_factor']
        )

        self.costs = {
            # 原料成本（运营成本）
            'natural_gas_price_yuan_per_m3': raw_costs['natural_gas_price_yuan_per_m3'],

            # FT反应器平准化成本
            'ft_reactor_capex_yuan_per_kg_year': ft_reactor_levelized_cost,
            'ft_reactor_opex_yuan_per_kg': 0,  # 已包含在平准化成本中

            # 储存成本
            'storage_cost_yuan_per_kg_hour': storage_levelized_cost / 8760,  # 小时成本

            # 短缺惩罚成本
            'shortage_penalty_yuan_per_kg': cost_config.get('shortage_penalty_yuan_per_kg', 20000),
        }

        logger.info(f"FT反应器平准化成本: {ft_reactor_levelized_cost:.2f} 元/(kg·年)")
        logger.info(f"天然气价格: {raw_costs['natural_gas_price_yuan_per_m3']:.2f} 元/m³")

        # 移除对外部成本分析器的依赖
        self.cost_analyzer = None
        logger.info("使用优化模型内部成本计算（FT一步法）")
    
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

        # 提高数值稳定性：模型矩阵系数范围跨度过大
        # NumericFocus=2 表示让Gurobi更注重数值精度
        self.model.setParam('NumericFocus', 2)
        logger.info("已设置NumericFocus=2以提高数值稳定性")

        # 不设置内存限制，让Gurobi自由使用内存直到求解完成

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

        # 4.5. 氢气库存变量 (添加氢气库存追踪，小时级)
        logger.info("创建氢气库存变量（小时级追踪）")

        self.hydrogen_storage_vars = {}  # 氢气库存 (kg H2)

        # 为所有FT设施候选位置创建氢气库存变量
        # 注：FT一步法虽然内部产氢，但增加库存变量可追踪氢气流动
        for location_id in self._get_ft_candidate_ids():
            for hour in range(self.total_hours + 1):  # +1 for final inventory
                var_name = f"h2_storage_{location_id}_{hour}"
                self.hydrogen_storage_vars[(location_id, hour)] = self.model.addVar(
                    lb=0, ub=GRB.INFINITY, vtype=GRB.CONTINUOUS, name=var_name
                )

        logger.info(f"创建了 {len(self.hydrogen_storage_vars)} 个氢气库存变量")

        # 5. FT反应器设施决策变量 (基于候选位置)
        self.ft_facility_vars = {}      # FT设施建设决策 (二进制)
        self.ft_capacity_vars = {}      # FT设施产能 (kg SAF/hour)

        # 从配置读取FT反应器容量限制
        ft_max_capacity = self.config.get('capacity_limits', {}).get('ft_reactor_max_capacity_kg_per_hour', 1000000)
        ft_min_capacity = self.config.get('capacity_limits', {}).get('ft_reactor_min_capacity_kg_per_hour', 0)

        logger.info(f"FT反应器容量配置: 最小={ft_min_capacity} kg/h, 最大={ft_max_capacity} kg/h")

        for location_id in self._get_ft_candidate_ids():
            # FT设施建设决策 (二进制)
            facility_var_name = f"ft_facility_{location_id}"
            self.ft_facility_vars[location_id] = self.model.addVar(
                vtype=GRB.BINARY, name=facility_var_name
            )

            # FT设施产能决策 (连续变量)
            capacity_var_name = f"ft_capacity_{location_id}"
            self.ft_capacity_vars[location_id] = self.model.addVar(
                lb=ft_min_capacity, ub=ft_max_capacity,
                vtype=GRB.CONTINUOUS, name=capacity_var_name
            )

        logger.info(f"创建了 {len(self.ft_facility_vars)} 个FT设施建设决策变量")
        logger.info(f"创建了 {len(self.ft_capacity_vars)} 个FT设施产能变量")

        # 【关键修复】关联FT专用变量与通用变量系统
        # 确保两套变量保持一致：FT专用变量用于成本计算，通用变量用于约束
        logger.info("添加FT专用变量与通用变量的关联约束...")
        ft_tech = 'ft_direct_conversion'  # FT一步法的技术类型
        linked_count = 0
        for location_id in self._get_ft_candidate_ids():
            # 关联设施建设决策变量
            if (location_id, ft_tech) in self.facility_vars:
                self.model.addConstr(
                    self.ft_facility_vars[location_id] == self.facility_vars[(location_id, ft_tech)],
                    name=f"link_ft_facility_{location_id}"
                )
                linked_count += 1

            # 关联设施产能变量
            if (location_id, ft_tech) in self.facility_capacity_vars:
                self.model.addConstr(
                    self.ft_capacity_vars[location_id] == self.facility_capacity_vars[(location_id, ft_tech)],
                    name=f"link_ft_capacity_{location_id}"
                )

        logger.info(f"已添加 {linked_count} 个FT设施变量关联约束")


        # 6. 天然气运输决策变量 (从NG供应源到FT设施，罐车运输，天级)
        self.ng_transport_vars = {}  # 天然气运输量 (m³/day)

        logger.info("创建天然气罐车运输变量（从NG供应源到FT设施）")

        valid_ng_routes = 0  # 计数有效路线
        total_days = self.total_hours // 24

        # 为每个FT设施候选位置创建从其天然气供应源的运输变量
        for ft_location_id in self._get_ft_candidate_ids():
            ft_location_data = self.locations[ft_location_id]
            source_type = ft_location_data['source_type']
            source_id = ft_location_data['source_id']

            # 根据供应源类型确定运输需求
            # - ng_pipeline: 需要罐车运输变量（管道端点到FT设施）
            # - lng_terminal: 需要罐车运输变量（LNG接收站到FT设施）
            # - airport: 管道直供，不需要运输变量

            if source_type in ['ng_pipeline', 'lng_terminal']:
                for day in range(total_days):
                    var_name = f"ng_transport_{source_id}_{ft_location_id}_day_{day}"
                    self.ng_transport_vars[(source_id, ft_location_id, day)] = self.model.addVar(
                        lb=0, ub=GRB.INFINITY, vtype=GRB.CONTINUOUS, name=var_name
                    )
                    valid_ng_routes += 1

        logger.info(f"创建了 {valid_ng_routes} 条天然气运输路线")

        # 7. SAF运输变量 (从FT设施到机场，周级)
        self.saf_transport_vars = {}

        logger.info("创建SAF运输变量（从FT设施到机场）")

        valid_saf_routes = 0
        for ft_location_id in self._get_ft_candidate_ids():
            for airport in self.airports:
                for week in range(self.time_horizon_weeks):
                    var_name = f"saf_transport_{ft_location_id}_{airport}_{week}"
                    self.saf_transport_vars[(ft_location_id, airport, week)] = self.model.addVar(
                        lb=0, ub=GRB.INFINITY, vtype=GRB.CONTINUOUS, name=var_name
                    )
                    valid_saf_routes += 1

        logger.info(f"创建了 {valid_saf_routes} 条SAF运输路线")

        # 日志汇总
        logger.info(f"创建了 {len(self.production_vars)} 个生产变量")
        logger.info(f"创建了 {len(self.facility_vars)} 个设施变量")
        logger.info(f"创建了 {len(self.facility_capacity_vars)} 个设施产能变量")
        logger.info(f"创建了 {len(self.transport_vars)} 个运输变量")
        logger.info(f"创建了 {len(self.storage_vars)} 个库存变量")
        logger.info(f"创建了 {len(self.ng_transport_vars)} 个天然气运输变量")
        # 8. 创建缺货惩罚变量 (周级需求缺口)
        self.shortage_vars = {}
        for airport in self.airports:
            for week in range(self.time_horizon_weeks):
                var_name = f"shortage_{airport}_{week}"
                self.shortage_vars[(airport, week)] = self.model.addVar(
                    lb=0, ub=GRB.INFINITY, vtype=GRB.CONTINUOUS, name=var_name
                )

        logger.info(f"创建了 {len(self.shortage_vars)} 个缺货惩罚变量")
        logger.info(f"创建了 {len(self.saf_transport_vars)} 个SAF运输变量")

        logger.info("FT一步法模型变量创建完成")
    
    def _create_constraints(self):
        """创建约束条件（FT一步法模型）"""
        logger.info("创建约束条件（FT一步法模型）...")

        # 1. FT生产能力约束（FT反应器容量限制）
        self._add_production_capacity_constraints()

        # 2. 原料供应约束（天然气供应和消耗）
        self._add_material_supply_constraints()

        # 3. 库存平衡约束（SAF库存进出平衡）
        self._add_inventory_balance_constraints()

        # 3.5. 氢气库存平衡约束（追踪FT工艺内部氢气流动）
        self._add_hydrogen_inventory_balance_constraints()

        # 4. 机场需求约束（SAF需求满足）
        self._add_airport_demand_constraints()

        # 5. 设施选择约束（FT设施建设与产能关联）
        self._add_facility_selection_constraints()

        # 6. 天然气运输约束（管道和LNG供应能力）
        self._add_natural_gas_transport_constraints()

        # 7. 平准化成本约束（成本上限限制）
        self._add_levelized_cost_constraint()

        logger.info("FT一步法模型约束创建完成")

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

        # 4. SAF运输运营成本现值（FT一步法：使用saf_transport_vars）
        self.cost_expressions['transport_operation_cost'] = gp.quicksum(
            self.saf_transport_vars[(ft_location_id, airport, week)] *
            self._calculate_mtj_transport_cost_by_distance(
                self._calculate_distance(ft_location_id, airport)
            ) * lifecycle_operation_factor  # 20年运营成本现值，基于运输理论公式
            for ft_location_id in self._get_ft_candidate_ids()
            for airport in self.airports
            for week in range(self.time_horizon_weeks)
            if (ft_location_id, airport, week) in self.saf_transport_vars
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

        # 5.1. 氢气储存设施投资成本 + 20年运营成本现值
        # 创建辅助变量来捕获各FT设施的最大氢气库存量
        max_h2_storage_by_location = {}
        for location_id in self._get_ft_candidate_ids():
            max_var = self.model.addVar(
                lb=0, ub=GRB.INFINITY,
                vtype=GRB.CONTINUOUS,
                name=f'max_h2_storage_{location_id}'
            )
            # 约束：max_var必须大于等于该FT设施在任何时刻的氢气库存量
            for hour in range(self.total_hours + 1):
                if (location_id, hour) in self.hydrogen_storage_vars:
                    self.model.addConstr(
                        max_var >= self.hydrogen_storage_vars[(location_id, hour)],
                        name=f'max_h2_storage_constr_{location_id}_h{hour}'
                    )
            max_h2_storage_by_location[location_id] = max_var

        # 总的氢气储存设备需求 = 各FT设施最大氢气库存量之和
        max_h2_storage_needed = gp.quicksum(max_h2_storage_by_location.values())

        # 优先使用统一成本配置中的氢气储存设备成本
        h2_storage_unit_cost = float(
            self.config.get('unified_costs', {}).get('storage', {}).get('hydrogen_equipment_cost_yuan_per_kg') or
            storage_cfg.get('hydrogen_equipment_unit_cost_yuan_per_kg', 20)
        )
        self.cost_expressions['h2_storage_investment'] = max_h2_storage_needed * h2_storage_unit_cost

        # 氢气库存运营成本：使用平均库存（峰值/2）而非所有时刻库存总和
        # 运营成本 = Σ(各地点最大氢气库存/2) × 小时成本 × 总小时数 × 生命周期系数
        average_h2_storage_total = gp.quicksum(max_h2_storage_by_location.values()) / 2.0
        self.cost_expressions['h2_storage_operation'] = (
            average_h2_storage_total *
            self._calculate_total_storage_cost_per_kg_hour() *
            self.total_hours *
            lifecycle_operation_factor
        )

        # 6. FT反应器投资成本（一次性投资）
        ft_reactor_capex_raw = self.config['equipment_raw_costs']['ft_reactor']['capex_raw']
        logger.info(f"FT反应器投资成本参数: {ft_reactor_capex_raw} 元/套")

        self.cost_expressions['ft_reactor_investment_cost'] = gp.quicksum(
            self.ft_facility_vars[location_id] * ft_reactor_capex_raw
            for location_id in self.ft_facility_vars.keys()
        )

        # 7. FT反应器运营成本（20年生命周期现值）
        ft_reactor_opex_annual = self.config['equipment_raw_costs']['ft_reactor']['opex_raw']
        logger.info(f"FT反应器年运营成本参数: {ft_reactor_opex_annual} 元/年")

        self.cost_expressions['ft_reactor_operation_cost'] = gp.quicksum(
            self.ft_facility_vars[location_id] * ft_reactor_opex_annual * present_value_factor
            for location_id in self.ft_facility_vars.keys()
        )

        # 8. FT生产过程成本（20年生命周期现值）
        # 修正日期：2025-11-09 - 实现催化剂成本和能源成本，并支持差异化电价
        ft_tech = self.config['technologies']['ft_direct_conversion']
        catalyst_cost_per_kg_saf = ft_tech.get('catalyst_cost_yuan_per_kg_saf', 0.06)
        energy_consumption_kwh_per_kg = ft_tech.get('energy_consumption_kwh_per_kg_saf', 0.8)

        logger.info(f"FT催化剂成本: {catalyst_cost_per_kg_saf} 元/kg SAF")
        logger.info(f"FT能耗: {energy_consumption_kwh_per_kg} kWh/kg SAF")

        # 8.1 催化剂成本
        self.cost_expressions['ft_catalyst_cost'] = gp.quicksum(
            self.production_vars[(location, tech, hour)] * catalyst_cost_per_kg_saf
            for location in self.locations
            for tech in self.technologies
            for hour in range(self.total_hours)
            if (location, tech, hour) in self.production_vars
        ) * operation_expansion_factor * present_value_factor

        # 8.2 FT合成能源成本（差异化电价）
        # 根据SAF工厂位置类型，使用不同的电价
        # renewable_plant (solar/wind): 使用可再生电价
        # 其他位置 (airport等): 使用电网电价
        renewable_electricity_price_yuan_per_kwh = self.config.get('cost_parameters', {}).get('renewable_energy', {}).get('wind_power_price_yuan_per_kwh', 0.35)
        grid_electricity_price_yuan_per_kwh = self.config.get('cost_parameters', {}).get('renewable_energy', {}).get('grid_electricity_price_yuan_per_kwh', 0.6)

        self.cost_expressions['ft_energy_cost'] = gp.quicksum(
            self.production_vars[(location, tech, hour)] *
            energy_consumption_kwh_per_kg *
            (renewable_electricity_price_yuan_per_kwh if self.locations[location]['type'] in ['solar_plant', 'wind_farm', 'byproduct_hydrogen_steel', 'byproduct_hydrogen_refinery']
             else grid_electricity_price_yuan_per_kwh)
            for location in self.locations
            for tech in self.technologies
            for hour in range(self.total_hours)
            if (location, tech, hour) in self.production_vars
        ) * operation_expansion_factor * present_value_factor

        # 总FT生产成本 = 催化剂成本 + 能源成本
        self.cost_expressions['ft_production_cost'] = (
            self.cost_expressions['ft_catalyst_cost'] +
            self.cost_expressions['ft_energy_cost']
        )

        logger.info("FT生产成本已实现（催化剂成本 + 差异化电价能源成本）")

        # 9. 天然气运输成本（20年运营成本现值）
        # 从NG供应源（管道端点/LNG接收站）到FT设施的天然气运输
        self.cost_expressions['ng_transport_investment'] = gp.LinExpr(0)  # 已包含在平准化成本中

        ng_transport_operation_expr = gp.LinExpr()

        # 遍历所有天然气运输变量
        for (source_id, ft_location_id, day), transport_var in self.ng_transport_vars.items():
            # 计算运输距离
            # 需要根据source_id找到对应的坐标
            source_coord = None

            # 从管道源或LNG终端中查找坐标
            if source_id in self.ng_pipeline_sources:
                source_data = self.ng_pipeline_sources[source_id]
                source_coord = (source_data['lat'], source_data['lon'])
            elif source_id in self.lng_terminals:
                terminal_data = self.lng_terminals[source_id]
                source_coord = (terminal_data['lat'], terminal_data['lon'])

            # 从self.locations中查找FT候选位置的目标坐标
            if ft_location_id in self.locations:
                ft_location_data = self.locations[ft_location_id]
                ft_coord = (ft_location_data['latitude'], ft_location_data['longitude'])

                if source_coord:
                    # 使用Haversine距离计算（简化版，实际应使用GraphHopper）
                    distance_km = self._calculate_haversine_distance(
                        source_coord[0], source_coord[1],
                        ft_coord[0], ft_coord[1]
                    )

                    # 使用基于距离的天然气运输成本公式
                    ng_unit_cost = self._calculate_ng_transport_cost_by_distance(distance_km)

                    # 累加运输成本
                    ng_transport_operation_expr += transport_var * ng_unit_cost * lifecycle_operation_factor

        self.cost_expressions['ng_transport_operation'] = ng_transport_operation_expr

        # 10. SAF运输成本（从FT设施到机场）
        self.cost_expressions['saf_transport_investment'] = gp.LinExpr(0)  # 已包含在平准化成本中

        saf_transport_operation_expr = gp.LinExpr()

        for (ft_location_id, airport, week), transport_var in self.saf_transport_vars.items():
            # 查找FT设施和机场坐标
            if ft_location_id in self.locations:
                ft_location_data = self.locations[ft_location_id]
                airport_data = self.airports.get(airport)

                if airport_data:
                    # 计算距离
                    distance_km = self._calculate_haversine_distance(
                        ft_location_data['latitude'], ft_location_data['longitude'],
                        airport_data['latitude'], airport_data['longitude']
                    )

                    # 使用MTJ运输成本公式（SAF运输类似）
                    saf_unit_cost = self._calculate_mtj_transport_cost_by_distance(distance_km)

                    # 累加运输成本
                    saf_transport_operation_expr += transport_var * saf_unit_cost * lifecycle_operation_factor

        self.cost_expressions['saf_transport_operation'] = saf_transport_operation_expr

        # 11. 原料成本（20年生命周期现值）
        # 获取天然气价格 (元/m³)
        ng_price_per_m3 = None
        for pipeline_id, pipeline_data in self.ng_pipeline_sources.items():
            price = pipeline_data.get('natural_gas_price_yuan_per_10k_m3', None)
            if price is not None:
                ng_price_per_m3 = price  # 数据文件中实际是元/m³，不是元/万m³
                break

        if ng_price_per_m3 is not None:
            # 创建天然气成本表达式对象
            self.cost_expressions['natural_gas_cost'] = gp.quicksum(
                self.production_vars[(location, tech, hour)] *
                self.technologies[tech]['ng_consumption_ratio'] * ng_price_per_m3 * lifecycle_operation_factor
                for location in self.locations
                for tech in self.technologies
                for hour in range(self.total_hours)
                if (location, tech, hour) in self.production_vars and
                   self.technologies[tech].get('ng_consumption_ratio', 0) > 0
            )
        else:
            self.cost_expressions['natural_gas_cost'] = gp.LinExpr(0)  # 如果没有价格信息，成本为0


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

        # 创建聚合成本表达式（FT一步法模型）
        # 投资成本聚合
        self.cost_aggregates['total_investment_cost'] = (
            self.cost_expressions['facility_investment_cost'] +
            self.cost_expressions['storage_equipment_cost'] +
            self.cost_expressions['h2_storage_investment'] +
            self.cost_expressions['ft_reactor_investment_cost'] +
            self.cost_expressions['ng_transport_investment'] +
            self.cost_expressions['saf_transport_investment']
        )

        # 运营成本聚合
        self.cost_aggregates['total_operation_cost'] = (
            self.cost_expressions['facility_operation_cost'] +
            self.cost_expressions['production_cost'] +
            self.cost_expressions['transport_operation_cost'] +
            self.cost_expressions['storage_operation_cost'] +
            self.cost_expressions['h2_storage_operation'] +
            self.cost_expressions['ft_reactor_operation_cost'] +
            self.cost_expressions['ft_production_cost'] +
            self.cost_expressions['ng_transport_operation'] +
            self.cost_expressions['saf_transport_operation'] +
            self.cost_expressions['natural_gas_cost'] +
            self.cost_expressions['final_inventory_cost']
        )

        # 不含短缺成本的总成本
        self.cost_aggregates['total_cost_excluding_shortage'] = (
            self.cost_aggregates['total_investment_cost'] +
            self.cost_aggregates['total_operation_cost']
        )

        logger.info("FT一步法模型统一成本表达式创建完成")
        logger.info(f"项目期限: {project_lifespan}年，时间窗口: {self.time_horizon_weeks}周")
        logger.info(f"运营成本年化系数: {operation_expansion_factor:.1f}")
        logger.info(f"20年运营成本现值系数: {present_value_factor:.2f}")
        logger.info(f"生命周期运营成本系数: {lifecycle_operation_factor:.2f}")
        logger.info("所有运营成本已扩展至20年生命周期现值")

        # 关键参数验证（FT一步法模型）
        logger.info("\n【FT一步法模型关键参数验证】")
        logger.info(f"FT反应器投资成本: {ft_reactor_capex_raw} 元/套")
        logger.info(f"FT反应器运营成本: {ft_reactor_opex_annual} 元/年")
        # FT生产成本详见上方催化剂成本和能源成本的logger输出（行1958-1959）

        # 创建性能指标表达式
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
            'raw_materials': ['ng_extraction_intensity', 'ng_pipeline_transport'],
            'facility_construction': ['saf_facility_embodied', 'saf_facility_lifetime'],
            'production_process': ['ng_upstream_emission', 'ft_process_emission'],
            'storage_handling': ['saf_storage_energy'],
            'transportation': ['saf_truck_intensity', 'ng_truck_intensity']
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
        ng_extraction_intensity = raw_materials.get('ng_extraction_intensity', 0.25)  # kg CO2eq/m³
        ng_pipeline_transport = raw_materials.get('ng_pipeline_transport', 0.01)  # kg CO2eq/m³·km

        # 天然气开采碳排放（基于运输量推算开采量）
        # 注：ng_transport_vars已经是天级变量(m³/天)，无需再乘以24
        self.carbon_expressions['ng_extraction'] = gp.quicksum(
            self.ng_transport_vars.get((ng_loc, mtj_loc, day), gp.LinExpr(0)) *
            ng_extraction_intensity  # 天级变量 * kg CO2eq/m³
            for ng_loc in self.ng_locations
            for mtj_loc in self.locations
            for day in range(total_days)
            if (ng_loc, mtj_loc, day) in self.ng_transport_vars
        )

        logger.info(f"天然气开采碳强度: {ng_extraction_intensity} kg CO2eq/m³")
        logger.info(f"[调试] 天然气运输变量数量: {len([k for k in self.ng_transport_vars.keys()])}") if hasattr(self, 'ng_transport_vars') else logger.warning("[调试] 未找到天然气运输变量")

        # =========================================================================
        # 2. 设施建设阶段碳排放（年摊销）(Facility Construction)
        # =========================================================================
        saf_embodied = facility_constr.get('saf_facility_embodied', 150)  # kg CO2eq/t年产能
        saf_lifetime = facility_constr.get('saf_facility_lifetime', 25)  # 年

        # SAF工厂建设碳排放（年摊销到优化时段）
        # 单位转换: kg/h → t/年 → kg CO2eq
        self.carbon_expressions['saf_facility'] = gp.quicksum(
            (self.facility_capacity_vars.get((location, tech), gp.LinExpr(0)) * 8760 / 1000) *  # kg/h → t/年
            saf_embodied / saf_lifetime * (self.time_horizon_weeks / 52.0)  # 年摊销到优化时段
            for location in self.locations
            for tech in self.technologies
            if (location, tech) in self.facility_capacity_vars
        )

        logger.info(f"SAF设施碳强度: {saf_embodied} kg CO2eq/t年产能, 寿命: {saf_lifetime}年")
        logger.info(f"[调试] 设施容量变量数量: {len([k for k in self.facility_capacity_vars.keys()])}") if hasattr(self, 'facility_capacity_vars') else logger.warning("[调试] 未找到设施容量变量")

        # =========================================================================
        # 3. 生产过程阶段碳排放 (Production Process) - FT一步法
        # =========================================================================
        # FT一步法：天然气 → SAF（直接转化，无中间产物，能源自给）
        # 碳排放 = 天然气上游排放 + FT过程直接排放

        # 读取碳排放参数
        ng_upstream_em = production.get('ng_upstream_emission', 0.5)  # kg CO2eq/m³ NG（开采+运输）
        ft_process_em = production.get('ft_process_emission', 1.5)  # kg CO2eq/kg SAF（FT反应过程）

        # 读取FT工艺参数
        ft_tech_config = self.config.get('technologies', {}).get('ft_direct_conversion', {})
        ng_consumption_ratio = ft_tech_config.get('ng_consumption_ratio', 2.0)  # m³ NG/kg SAF

        # FT一步法总碳排放 = 天然气上游 + FT过程
        # 注意：不需要电力碳排放项，因为FT反应放热可自供能（热集成效率75%）
        self.carbon_expressions['ft_production'] = gp.quicksum(
            self.production_vars.get((location, tech, hour), gp.LinExpr(0)) *
            (ng_consumption_ratio * ng_upstream_em + ft_process_em)
            for location in self.locations
            for tech in self.technologies
            for hour in range(self.total_hours)
            if (location, tech, hour) in self.production_vars
        )

        logger.info(f"FT一步法工艺参数:")
        logger.info(f"  天然气消耗比: {ng_consumption_ratio} m³/kg SAF")
        logger.info(f"  天然气上游碳排放: {ng_upstream_em} kg CO2eq/m³")
        logger.info(f"  FT过程碳排放: {ft_process_em} kg CO2eq/kg SAF")
        logger.info(f"  单位SAF总碳排放: {ng_consumption_ratio * ng_upstream_em + ft_process_em:.2f} kg CO2eq/kg")
        logger.info(f"[调试] 生产变量数量: {len([k for k in self.production_vars.keys()])}") if hasattr(self, 'production_vars') else logger.warning("[调试] 未找到生产变量")

        # =========================================================================
        # 4. 储存处理阶段碳排放 (Storage & Handling)
        # =========================================================================
        # SAF储存能耗很小，且可能使用FT装置余热，碳排放忽略
        saf_storage_energy = storage_handling.get('saf_storage_energy', 5)  # kWh/t·天

        # 基本参数验证
        if saf_storage_energy <= 0:
            logger.warning(f"SAF储存能耗参数异常: {saf_storage_energy}")

        # SAF储存碳排放 - 忽略（能耗很小，可能使用FT余热）
        self.carbon_expressions['saf_storage'] = gp.LinExpr(0)  # 忽略储存碳排放

        logger.info(f"SAF储存能耗: {saf_storage_energy} kWh/t·天（碳排放已忽略 - FT余热利用）")
        logger.info(f"[调试] SAF存储变量数量: {len([k for k in self.storage_vars.keys()])}") if hasattr(self, 'storage_vars') else logger.warning("[调试] 未找到SAF存储变量")

        # =========================================================================
        # 5. 运输配送阶段碳排放 (Transportation & Distribution)
        # =========================================================================
        saf_truck = transportation.get('saf_truck_intensity', 0.12)  # kg CO2eq/t·km
        ng_truck = transportation.get('ng_truck_intensity', 0.10)  # kg CO2eq/m³·km

        # SAF运输碳排放
        # 单位转换: kg → t，因为saf_truck单位是kg CO2eq/t·km
        self.carbon_expressions['saf_transport'] = gp.quicksum(
            (self.transport_vars.get((location, airport, week), gp.LinExpr(0)) / 1000) *  # kg → t
            self._calculate_distance(location, airport) * saf_truck  # t × km × kg CO2eq/t·km
            for location in self.locations
            for airport in self.airports
            for week in range(self.time_horizon_weeks)
            if (location, airport, week) in self.transport_vars
        )

        # 天然气运输碳排放
        # 注：ng_transport_vars是天级变量(m³/天)，ng_truck单位是kg CO2eq/m³·km，无需时间转换
        self.carbon_expressions['ng_transport'] = gp.quicksum(
            self.ng_transport_vars.get((ng_loc, mtj_loc, day), gp.LinExpr(0)) *
            self._calculate_distance(ng_loc, mtj_loc) * ng_truck  # m³/天 * km * kg CO2eq/m³·km
            for ng_loc in self.ng_locations
            for mtj_loc in self.locations
            for day in range(total_days)
            if (ng_loc, mtj_loc, day) in self.ng_transport_vars
        )

        # 验证运输碳强度参数合理性
        transport_params = [
            (saf_truck, 0.05, 0.30, "SAF罐车运输碳强度"),
            (ng_truck, 0.05, 0.30, "天然气罐车运输碳强度")
        ]
        for value, min_val, max_val, name in transport_params:
            if not (min_val <= value <= max_val):
                logger.warning(f"{name}可能不合理: {value}, 期望范围: [{min_val}, {max_val}]")

        logger.info(f"SAF罐车运输: {saf_truck} kg CO2eq/t·km")
        logger.info(f"天然气罐车运输: {ng_truck} kg CO2eq/m³·km")
        logger.info(f"[调试] SAF运输变量数量: {len([k for k in self.transport_vars.keys()])}") if hasattr(self, 'transport_vars') else logger.warning("[调试] 未找到SAF运输变量")
        logger.info(f"[调试] 天然气运输变量数量: {len([k for k in self.ng_transport_vars.keys()])}") if hasattr(self, 'ng_transport_vars') else logger.warning("[调试] 未找到天然气运输变量")

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
        # 6. 汇总碳排放 (Carbon Emission Aggregation)
        # =========================================================================

        # 各类别汇总
        self.carbon_aggregates['raw_material_emissions'] = self.carbon_expressions['ng_extraction']

        self.carbon_aggregates['facility_emissions'] = (
            self.carbon_expressions['saf_facility']
        )

        self.carbon_aggregates['production_emissions'] = (
            self.carbon_expressions['ft_production']  # FT一步法：直接从天然气生产SAF
        )

        self.carbon_aggregates['storage_emissions'] = (
            self.carbon_expressions['saf_storage']  # FT一步法：SAF储存
        )

        self.carbon_aggregates['transport_emissions'] = (
            self.carbon_expressions['saf_transport'] +
            self.carbon_expressions['ng_transport']
        )

        # 总碳排放
        self.carbon_aggregates['total_emissions'] = (
            self.carbon_aggregates['raw_material_emissions'] +
            self.carbon_aggregates['facility_emissions'] +
            self.carbon_aggregates['production_emissions'] +
            self.carbon_aggregates['storage_emissions'] +
            self.carbon_aggregates['transport_emissions']
        )

        # 将碳排放扩展到年化值（用于报告）
        self.carbon_aggregates['annual_emissions'] = (
            self.carbon_aggregates['total_emissions'] * operation_expansion_factor
        )

        # =========================================================================
        # 7. 碳强度计算组件 (Carbon Intensity Components)
        # =========================================================================
        # 碳强度涉及除法运算（总碳排放 / 总产量），Gurobi不支持非线性表达式
        # 因此这里存储碳强度计算所需的常量参数，实际碳强度在求解后计算

        # 存储碳强度计算所需的常量参数
        self.carbon_params['saf_energy_content'] = self.carbon_params.get('benchmarks', {}).get('saf_energy_content', 43.15)  # MJ/kg
        self.carbon_params['traditional_jet_ci'] = self.carbon_params.get('benchmarks', {}).get('traditional_jet_fuel', 89)  # g CO2eq/MJ
        self.carbon_params['corsia_limit_ci'] = self.carbon_params.get('benchmarks', {}).get('corsia_limit', 30)  # g CO2eq/MJ

        # 碳强度分子：总碳排放（已在上面定义）
        # 碳强度分母：总产量（在performance_expressions中定义）
        # 实际碳强度计算公式：
        #   carbon_intensity_kg = total_emissions / production_total  [kg CO2eq/kg SAF]
        #   carbon_intensity_mj = carbon_intensity_kg * 1000 / saf_energy_content  [g CO2eq/MJ]

        logger.info("碳强度计算组件准备完成")
        logger.info(f"  SAF能量含量: {self.carbon_params['saf_energy_content']} MJ/kg")
        logger.info(f"  传统航油碳强度基准: {self.carbon_params['traditional_jet_ci']} g CO2eq/MJ")
        logger.info(f"  CORSIA碳强度限值: {self.carbon_params['corsia_limit_ci']} g CO2eq/MJ")

        logger.info("碳排放表达式创建完成")
        logger.info(f"包含 {len(self.carbon_expressions)} 个细分项，{len(self.carbon_aggregates)} 个汇总项")

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
        logger.info("  原料获取: 按天计算(ng_transport_vars)")
        logger.info("  设施建设碳排放: 按使用寿命年化后，再按优化时段比例摊销")
        logger.info("  设施产能: 决策变量(kg/h)，通过产能约束限制小时生产量")
        logger.info("  生产过程: 按小时计算(production_vars) - FT一步法")
        logger.info("  储存处理: 按小时计算(storage_vars) - FT一步法")
        logger.info("  运输配送: SAF按周, NG按天")
        logger.info("  最终结果: 所有项目累计为优化时段内总碳排放(kg CO2eq)")
        logger.info("="*60)

    def _create_performance_expressions(self):
        """创建性能指标表达式：产量、缺货、需求满足比例等

        注意：需求满足比例涉及除法运算，Gurobi不支持非线性表达式，
        因此存储分子和分母表达式，在求解后计算比例值。
        """
        logger.info("创建性能指标表达式...")

        if not hasattr(self, 'performance_expressions'):
            self.performance_expressions = {}

        # 1. 总生产量表达式
        self.performance_expressions['production_total'] = gp.quicksum(
            var for var in self.production_vars.values()
        )

        # 2. 缺货总量表达式
        if hasattr(self, 'shortage_vars') and self.shortage_vars:
            self.performance_expressions['shortage_total'] = gp.quicksum(
                self.shortage_vars.values()
            )
        else:
            self.performance_expressions['shortage_total'] = gp.LinExpr(0)

        # 3. 总需求表达式（总产量 + 缺货产量）
        self.performance_expressions['total_demand'] = (
            self.performance_expressions['production_total'] +
            self.performance_expressions['shortage_total']
        )

        # 4. 氢气总生产量
        if hasattr(self, 'hydrogen_production_vars') and self.hydrogen_production_vars:
            self.performance_expressions['hydrogen_total_production'] = gp.quicksum(
                self.hydrogen_production_vars.values()
            )
        else:
            self.performance_expressions['hydrogen_total_production'] = gp.LinExpr(0)

        # 5. 甲醇总生产量（一步法不适用，设为0）
        self.performance_expressions['methanol_total_production'] = gp.LinExpr(0)

        # 6. SAF设施总数
        if hasattr(self, 'facility_vars') and self.facility_vars:
            self.performance_expressions['facilities_count'] = gp.quicksum(
                self.facility_vars.values()
            )
        else:
            self.performance_expressions['facilities_count'] = gp.LinExpr(0)

        # 7. 电解槽设施总数
        if hasattr(self, 'electrolyzer_facility_vars') and self.electrolyzer_facility_vars:
            self.performance_expressions['hydrogen_facilities_count'] = gp.quicksum(
                self.electrolyzer_facility_vars.values()
            )
        else:
            self.performance_expressions['hydrogen_facilities_count'] = gp.LinExpr(0)

        logger.info(f"性能指标表达式创建完成，共 {len(self.performance_expressions)} 个指标")
        logger.info("[调试] 性能表达式详情:")
        for name in self.performance_expressions:
            logger.info(f"  - {name}")

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

                # FT一步法：无需氢气生产和可再生能源约束
                # 产能约束仅基于天然气供应能力和FT反应器容量
    
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
                # FT一步法：直接从天然气生产SAF，无需氢气供应约束

                if location_type in ['lng_terminal', 'airport']:
                    # 3. 天然气管道流量限制约束（简化版，移除维护停机）
                    self._add_simplified_ng_pipeline_constraints(location, hour)

                    # 4. 天然气储罐压力和流量约束
                    self._add_ng_storage_flow_constraints(location, hour)

        # 移除设备维护停机时间约束 - 这是导致20%利用率的主因
        # self._add_maintenance_downtime_constraints()  # 注释掉

        # FT一步法不需要氢气运输约束

        logger.info("严格的小时级原料供应约束添加完成（已移除维护停机约束和氢气运输约束）")

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
            # 机场：移除天然气供应限制约束，允许无限制供应
            logger.info(f"机场 {location} 在小时 {hour}: 已移除天然气供应限制约束")
            return  # 直接返回，跳过供应约束

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

    def _add_inventory_balance_constraints(self):
        """添加库存平衡约束

        【FT一步法】
        - 针对FT设施的SAF库存
        - 使用saf_transport_vars而不是transport_vars
        - 库存出库按小时平摊，与两步法保持一致
        """
        # FT一步法：遍历FT设施位置
        for ft_location_id in self._get_ft_candidate_ids():
            for hour in range(self.total_hours):
                # 库存平衡：当前库存 = 上期库存 + 生产 - 出库
                current_inventory = self.storage_vars[(ft_location_id, hour + 1)]
                previous_inventory = self.storage_vars[(ft_location_id, hour)]

                # 当前小时FT设施的SAF生产
                production = gp.quicksum(
                    self.production_vars[(ft_location_id, tech, hour)]
                    for tech in self.technologies
                    if (ft_location_id, tech, hour) in self.production_vars
                )

                # 出库量（用于SAF运输的部分，按小时平摊）
                outflow = gp.quicksum(
                    self.saf_transport_vars[(ft_location_id, airport, hour // self.hours_per_week)] / self.hours_per_week
                    for airport in self.airports
                    if (ft_location_id, airport, hour // self.hours_per_week) in self.saf_transport_vars
                )

                self.model.addConstr(
                    current_inventory == previous_inventory + production - outflow,
                    name=f"inventory_balance_{ft_location_id}_{hour}"
                )

            # 初始库存为0
            self.model.addConstr(
                self.storage_vars[(ft_location_id, 0)] == 0,
                name=f"initial_inventory_{ft_location_id}"
            )

    def _add_hydrogen_inventory_balance_constraints(self):
        """添加氢气库存平衡约束

        【说明】
        虽然Natural Gas模块使用FT一步法（天然气直接转SAF），但FT工艺内部会产生氢气。
        添加氢气库存约束可以追踪FT工艺中氢气的流动和累积。

        约束逻辑：
        - 当前库存 = 上期库存 + 本期生产（FT内部制氢） - 本期消耗（FT合成SAF）
        - 假设FT工艺的氢气产率和消耗率相匹配，库存变化应该很小或为0
        - 初始库存为0
        """
        logger.info("=" * 60)
        logger.info("添加氢气库存平衡约束（FT工艺内部氢气追踪）")
        logger.info("=" * 60)

        # 获取FT工艺的氢气相关参数
        # 注：FT一步法中氢气是内部产物，这里假设一个典型的氢气产率和消耗率
        # H2产率：天然气 → 氢气转化率（kg H2 / m³ NG）
        h2_production_rate = 0.08  # 假设：1 m³ NG → 0.08 kg H2（典型值）

        # H2消耗率：氢气 → SAF转化率（kg H2 / kg SAF）
        # 根据FT合成反应：2H2 + CO → -CH2- + H2O
        # 典型值约0.1-0.15 kg H2/kg SAF
        h2_consumption_rate = 0.12  # kg H2 / kg SAF

        constraint_count = 0
        init_constraints = 0

        # 为每个FT设施候选位置添加氢气库存平衡约束
        for location_id in self._get_ft_candidate_ids():
            # 初始库存约束（hour 0 = 0）
            if (location_id, 0) in self.hydrogen_storage_vars:
                self.model.addConstr(
                    self.hydrogen_storage_vars[(location_id, 0)] == 0,
                    name=f"h2_init_inventory_{location_id}"
                )
                init_constraints += 1

            for hour in range(self.total_hours):
                # 上一时刻库存
                prev_inventory = self.hydrogen_storage_vars.get((location_id, hour), gp.LinExpr(0))

                # 当前时刻库存
                curr_inventory = self.hydrogen_storage_vars.get((location_id, hour + 1), gp.LinExpr(0))

                # H2生产量（从天然气消耗推算）
                # 获取该位置该小时的天然气消耗（通过SAF生产量反推）
                h2_production = gp.LinExpr(0)
                if (location_id, hour) in self.production_vars:
                    # 遍历所有技术（FT一步法可能有多种技术）
                    for tech in self.technologies.keys():
                        if (location_id, tech, hour) in self.production_vars:
                            saf_production = self.production_vars[(location_id, tech, hour)]
                            # 天然气消耗（m³/hour） = SAF生产 × ng_consumption_ratio
                            ng_consumption_ratio = self.technologies[tech]['ng_consumption_ratio']
                            ng_consumption = saf_production * ng_consumption_ratio
                            # H2生产 = 天然气消耗 × h2_production_rate
                            h2_production += ng_consumption * h2_production_rate

                # H2消耗量（用于SAF合成）
                h2_consumption = gp.LinExpr(0)
                if (location_id, hour) in self.production_vars:
                    for tech in self.technologies.keys():
                        if (location_id, tech, hour) in self.production_vars:
                            saf_production = self.production_vars[(location_id, tech, hour)]
                            # H2消耗 = SAF生产 × h2_consumption_rate
                            h2_consumption += saf_production * h2_consumption_rate

                # 库存平衡约束
                self.model.addConstr(
                    curr_inventory == prev_inventory + h2_production - h2_consumption,
                    name=f"h2_inv_balance_{location_id}_h{hour}"
                )
                constraint_count += 1

        logger.info(f"添加了 {init_constraints} 个H2初始库存约束")
        logger.info(f"添加了 {constraint_count} 个H2库存平衡约束")
        logger.info(f"H2产率假设: {h2_production_rate} kg H2/m³ NG")
        logger.info(f"H2消耗率假设: {h2_consumption_rate} kg H2/kg SAF")
        logger.info("=" * 60)

    def _add_airport_demand_constraints(self):
        """添加机场周时间序列需求约束（软约束：允许缺货但有惩罚）

        FT一步法：使用saf_transport_vars而不是transport_vars
        """
        for airport in self.airports:
            weekly_demand_series = self.airports[airport]['weekly_demand_series']  # 52周序列

            for week in range(self.time_horizon_weeks):
                # 获取该周的实际需求
                if week < len(weekly_demand_series):
                    weekly_demand = weekly_demand_series[week]
                else:
                    weekly_demand = 0.0  # 超出范围的周需求为0

                # FT一步法：该机场该周的SAF总运输量（从FT设施运输到机场）
                total_supply = gp.quicksum(
                    self.saf_transport_vars[(ft_location_id, airport, week)]
                    for ft_location_id in self._get_ft_candidate_ids()
                    if (ft_location_id, airport, week) in self.saf_transport_vars
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

    def _add_natural_gas_transport_constraints(self):
        """添加天然气运输约束：天然气从管道通过罐车运输到非LNG接收站的MTJ工厂"""
        logger.info("添加天然气罐车运输约束...")
        
        # 天然气运输约束：对于非LNG接收站位置的MTJ工厂（改为天级罐车运输）
        total_days = self.total_hours // 24
        # 使用动态技术列表
        for tech in self.technologies.keys():
            # FT一步法：检查技术的运输模式配置
            tech_transport_mode = self.technologies[tech].get('transport_mode', '')
            if tech_transport_mode == 'airport_integrated':
                continue  # 机场集成模式使用管道直供

            # 检查该技术的运输模式是否支持天然气管道
            transport_config = self.config['transport_modes'].get(tech_transport_mode, {})
            suitable_sources = transport_config.get('suitable_sources', [])

            # 如果该运输模式不支持天然气管道，跳过
            if 'ng_pipeline' not in suitable_sources:
                logger.info(f"技术 {tech} 的运输模式 {tech_transport_mode} 不支持天然气管道，跳过管道运输约束")
                continue

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
        # 使用动态技术列表
        for tech in self.technologies.keys():
            for mtj_loc in self.non_lng_mtj_locations.get(tech, []):
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

                    # FT一步法：检查技术的运输模式配置
                    tech_transport_mode = self.technologies[tech].get('transport_mode', '')
                    if tech_transport_mode == 'airport_integrated':
                        # 机场集成模式：直接从城市管道供气，需求被管道直接满足
                        # 不需要添加约束，因为管道直供隐含地满足了所有需求
                        # 天然气需求成本会在天然气采购成本中体现
                        pass  # 管道直供，无需额外约束
                    else:
                        # 其他技术：通过管道运输变量满足需求
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
    
        # 添加天然气管段日最大购入量约束 - 已注释掉日上限约束
        # self._add_ng_pipeline_daily_capacity_constraints()


        # 添加LNG接收站日最大供应量约束
        self._add_lng_terminal_daily_capacity_constraints()
    
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
    

    def _calculate_total_ng_transport_cost_per_kg_km(self) -> float:
        """计算天然气运输总成本（已弃用，统一使用基于距离的LNG成本公式）
        
        注意：此函数已被_calculate_ng_transport_cost_by_distance()替代
        保留此函数仅为向后兼容，建议使用基于距离的计算方法
        """
        # 为保持向后兼容，返回默认距离下的成本
        return self._calculate_ng_transport_cost_by_distance(100)  # 默认100km距离

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
            ng_consumption_ratio = tech_info.get('ng_consumption_ratio', 0.8)  # m³天然气/kg MTJ
            
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
            else:
                return capacity_estimates.get('default', 1500)  # 其他类型

        return capacity_estimates.get('default', 1500)  # 默认值
    
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
        logger.info("=== 开始提取解决方案 ===")
        logger.info(f"优化状态: {self.model.status}")
        logger.info(f"SAF运输变量字典大小: {len(self.saf_transport_vars)}")
        logger.info(f"天然气运输变量字典大小: {len(self.ng_transport_vars)}")
        logger.info(f"FT设施变量字典大小: {len(self.ft_facility_vars)}")

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

        # FT一步法：设施决策只从FT专用系统（self.ft_facility_vars）中提取
        # 不使用通用的self.facility_vars，避免重复和混淆
        # (通用的facility_vars在一步法中不应该被使用，因为一步法只有FT反应器)

        logger.info(f"\n=== 开始提取FT设施决策 ===")
        ft_candidate_count = sum(1 for loc in self.locations.values() if loc.get('is_ft_candidate'))
        logger.info(f"FT设施候选数: {ft_candidate_count}")
        logger.info(f"FT设施决策变量数: {len(self.ft_facility_vars)}")

        # 提取FT反应器设施决策（这是一步法的唯一设施类型）
        solution['ft_facilities'] = {}
        built_ft_count = 0
        for location_id, var in self.ft_facility_vars.items():
            if var.x > 0.5:  # 二进制变量大于0.5视为选中建设FT设施
                built_ft_count += 1
                ft_capacity = self.ft_capacity_vars[location_id].x

                logger.info(f"  已建设FT设施 #{built_ft_count}: location_id={location_id}, 产能={ft_capacity:.2f} kg/h")

                # 从self.locations中查找候选位置详细信息
                if location_id in self.locations:
                    ft_location_data = self.locations[location_id]

                    # TODO: 计算实际SAF产量和利用率（需要基于实际的生产变量）
                    # 暂时使用产能作为近似
                    max_annual_saf_capacity = ft_capacity * 8760  # kg SAF/年

                    ft_info = {
                        'location_id': location_id,
                        'name': ft_location_data.get('name', f'FT设施_{location_id}'),
                        'built': True,
                        'capacity_kg_saf_per_hour': ft_capacity,
                        'max_annual_saf_capacity_kg': max_annual_saf_capacity,
                        'source_type': ft_location_data.get('source_type'),
                        'source_id': ft_location_data.get('source_id'),
                        'latitude': ft_location_data['latitude'],
                        'longitude': ft_location_data['longitude'],
                        'ng_supply_capacity_m3_per_hour': ft_location_data.get('ng_supply_capacity_m3_per_hour', 0),
                        'ng_price_yuan_per_m3': ft_location_data.get('ng_price_yuan_per_m3', 0),
                        'technology': 'ft_direct_conversion'
                    }

                    # 如果有机场附近信息
                    if 'near_airport' in ft_location_data:
                        ft_info['near_airport'] = ft_location_data['near_airport']
                        ft_info['distance_to_airport_km'] = ft_location_data['distance_to_airport_km']

                    solution['ft_facilities'][location_id] = ft_info

                    # 计算实际SAF产量（从SAF运输变量累计）
                    actual_saf_production_week = sum(
                        self.saf_transport_vars[(location_id, airport, week)].x
                        for airport in self.airports
                        for week in range(self.time_horizon_weeks)
                        if (location_id, airport, week) in self.saf_transport_vars
                    )
                    # 转换为年产量
                    actual_annual_saf_production = actual_saf_production_week * (52.0 / self.time_horizon_weeks)

                    # 计算产能利用率
                    if max_annual_saf_capacity > 0:
                        utilization_rate = actual_annual_saf_production / max_annual_saf_capacity
                    else:
                        utilization_rate = 0

                    # 同时添加到主设施列表中（用于facilities_decisions.csv输出）
                    solution['facilities'][f"ft_{location_id}"] = {
                        'location': location_id,
                        'name': ft_location_data.get('name', f'FT设施_{location_id}'),
                        'technology': 'ft_direct_conversion',
                        'built': True,
                        'capacity_kg_per_hour': ft_capacity,  # SAF产能 kg/h
                        'max_annual_capacity_kg': max_annual_saf_capacity,
                        'actual_annual_production_kg': actual_annual_saf_production,
                        'utilization_rate': utilization_rate,
                        'location_type': ft_location_data.get('source_type'),
                        'transport_mode': 'ng_pipeline_direct',
                        'latitude': ft_location_data['latitude'],
                        'longitude': ft_location_data['longitude'],
                        'source_id': ft_location_data.get('source_id'),
                        'ng_supply_capacity_m3_per_hour': ft_location_data.get('ng_supply_capacity_m3_per_hour', 0),
                        'ng_price_yuan_per_m3': ft_location_data.get('ng_price_yuan_per_m3', 0)
                    }

                    # 如果有机场附近信息，也添加到facilities中
                    if 'near_airport' in ft_location_data:
                        solution['facilities'][f"ft_{location_id}"]['near_airport'] = ft_location_data['near_airport']
                        solution['facilities'][f"ft_{location_id}"]['distance_to_airport_km'] = ft_location_data['distance_to_airport_km']

        logger.info(f"=== FT设施提取完成 ===")
        logger.info(f"已建设FT设施数: {built_ft_count}")
        logger.info(f"solution['facilities']中的设施数: {len(solution['facilities'])}")
        logger.info(f"solution['ft_facilities']中的设施数: {len(solution['ft_facilities'])}")
        if built_ft_count > 0:
            logger.info(f"设施ID列表: {list(solution['facilities'].keys())}")

        # 【BUG修复】从facilities字典中提取FT设施信息，用于后续运输提取
        # 因为ft_facilities可能为空，但facilities中包含了实际建设的FT设施
        ft_facilities_actual = {}
        for facility_key, facility_info in solution.get('facilities', {}).items():
            if facility_info.get('technology') == 'ft_direct_conversion':
                # 提取location_id（去掉"ft_"或其他前缀）
                location_id = facility_info.get('location')
                if location_id:
                    ft_facilities_actual[location_id] = facility_info

        logger.info(f"\n=== FT设施修复统计 ===")
        logger.info(f"ft_facilities字典中的设施数: {len(solution.get('ft_facilities', {}))}")
        logger.info(f"从facilities提取的FT设施数: {len(ft_facilities_actual)}")

        # 【修复】提取SAF运输计划（从FT设施到机场）- 只提取已建设设施的运输
        solution['saf_transport'] = {}
        saf_transport_count = 0
        saf_transport_positive = 0
        for (ft_location_id, airport, week), var in self.saf_transport_vars.items():
            saf_transport_count += 1
            # 【关键修复】只提取实际建设的FT设施的运输路线
            if var.x > 0 and ft_location_id in ft_facilities_actual:
                saf_transport_positive += 1
                transport_key = f"{ft_location_id}_{airport}_{week}"

                # 从self.locations查找FT设施坐标
                airport_data = self.airports.get(airport)

                if ft_location_id in self.locations and airport_data:
                    ft_location_data = self.locations[ft_location_id]
                    # 计算距离
                    distance_km = self._calculate_haversine_distance(
                        ft_location_data['latitude'], ft_location_data['longitude'],
                        airport_data['latitude'], airport_data['longitude']
                    )

                    solution['saf_transport'][transport_key] = {
                        'from_location': ft_location_id,
                        'to_airport': airport,
                        'week': week,
                        'transport_kg_saf': var.x,
                        'distance_km': distance_km,
                        'from_latitude': ft_location_data['latitude'],
                        'from_longitude': ft_location_data['longitude'],
                        'to_latitude': airport_data['latitude'],
                        'to_longitude': airport_data['longitude'],
                        'transport_type': 'SAF',
                        'transport_mode': 'truck',
                        'route_coordinates': []  # 添加空的路径坐标字段
                    }

        logger.info(f"\n=== SAF运输提取统计 ===")
        logger.info(f"SAF运输变量总数: {saf_transport_count}")
        logger.info(f"SAF运输非零变量数: {saf_transport_positive}")
        logger.info(f"提取的SAF运输记录数: {len(solution['saf_transport'])}")

        # 【修复】提取天然气运输计划（从NG源到FT设施）- 只提取已建设设施的运输
        solution['ng_transport'] = {}
        ng_transport_count = 0
        ng_transport_positive = 0
        for (source_id, ft_location_id, day), var in self.ng_transport_vars.items():
            ng_transport_count += 1
            # 【关键修复】只提取到实际建设的FT设施的运输路线
            if var.x > 0 and ft_location_id in ft_facilities_actual:
                ng_transport_positive += 1
                # 每周汇总天然气运输（从天级聚合）
                week = day // 7
                transport_key = f"{source_id}_{ft_location_id}_week_{week}"

                # 如果这个周的运输key已存在，累加运输量
                if transport_key in solution['ng_transport']:
                    solution['ng_transport'][transport_key]['transport_m3_ng'] += var.x
                else:
                    # 查找源和目标坐标
                    source_coord = None
                    if source_id in self.ng_pipeline_sources:
                        source_data = self.ng_pipeline_sources[source_id]
                        source_coord = (source_data['lat'], source_data['lon'])
                    elif source_id in self.lng_terminals:
                        terminal_data = self.lng_terminals[source_id]
                        source_coord = (terminal_data['lat'], terminal_data['lon'])

                    if source_coord and ft_location_id in self.locations:
                        ft_location_data = self.locations[ft_location_id]
                        distance_km = self._calculate_haversine_distance(
                            source_coord[0], source_coord[1],
                            ft_location_data['latitude'], ft_location_data['longitude']
                        )

                        solution['ng_transport'][transport_key] = {
                            'from_source': source_id,
                            'to_location': ft_location_id,
                            'week': week,
                            'transport_m3_ng': var.x,
                            'distance_km': distance_km,
                            'from_latitude': source_coord[0],
                            'from_longitude': source_coord[1],
                            'to_latitude': ft_location_data['latitude'],
                            'to_longitude': ft_location_data['longitude'],
                            'transport_type': 'NG',
                            'transport_mode': 'truck',
                            'route_coordinates': []  # 添加空的路径坐标字段
                        }

        logger.info(f"\n=== 天然气运输提取统计 ===")
        logger.info(f"天然气运输变量总数: {ng_transport_count}")
        logger.info(f"天然气运输非零变量数: {ng_transport_positive}")
        logger.info(f"提取的天然气运输记录数: {len(solution['ng_transport'])}")

        # 提取天然气管道直供信息（增强功能：为管道直供的FT设施创建可视化连线数据）
        solution['ng_pipeline_direct'] = {}
        ng_pipeline_direct_count = 0
        ft_facilities_count = len(ft_facilities_actual)

        logger.info(f"\n=== 天然气管道直供提取统计 ===")
        logger.info(f"已建设的FT设施总数: {ft_facilities_count}")

        # 【修复】遍历所有建设的FT设施（使用ft_facilities_actual替代空的ft_facilities）
        for location_id, ft_info in ft_facilities_actual.items():
            ng_pipeline_direct_count += 1
            # 从self.locations查找对应的候选位置信息
            if location_id in self.locations:
                ft_location_data = self.locations[location_id]

                if ft_location_data.get('source_type') in ['ng_pipeline', 'lng_terminal']:
                    source_id = ft_location_data['source_id']
                    source_type = ft_location_data['source_type']

                    logger.debug(f"  FT设施 {location_id}: source_type={source_type}, source_id={source_id}")

                    # 获取源坐标
                    source_coord = None
                    source_name = ""
                    if source_type == 'ng_pipeline' and source_id in self.ng_pipeline_sources:
                        source_data = self.ng_pipeline_sources[source_id]
                        source_coord = (source_data['lat'], source_data['lon'])
                        source_name = f"NG管道_{source_id}"
                    elif source_type == 'lng_terminal' and source_id in self.lng_terminals:
                        terminal_data = self.lng_terminals[source_id]
                        source_coord = (terminal_data['lat'], terminal_data['lon'])
                        source_name = f"LNG接收站_{source_id}"

                    if source_coord:
                        # 计算距离
                        distance_km = self._calculate_haversine_distance(
                            source_coord[0], source_coord[1],
                            ft_location_data['latitude'], ft_location_data['longitude']
                        )

                        # 估算日均天然气消耗量（基于设施产能）
                        # SAF产能(kg/h) × 24h × NG消耗比(m³ NG/kg SAF)
                        ng_consumption_ratio = self.config.get('production_parameters', {}).get('ng_consumption_ratio_m3_per_kg_saf', 2.3)
                        daily_ng_consumption_m3 = ft_info.get('capacity_kg_saf_per_hour', 0) * 24 * ng_consumption_ratio

                        pipeline_key = f"pipeline_direct_{source_id}_{location_id}"
                        solution['ng_pipeline_direct'][pipeline_key] = {
                            'from_source': source_name,
                            'to_location': location_id,
                            'source_type': source_type,
                            'distance_km': distance_km,
                            'from_latitude': source_coord[0],
                            'from_longitude': source_coord[1],
                            'to_latitude': ft_location_data['latitude'],
                            'to_longitude': ft_location_data['longitude'],
                            'transport_type': 'NG_Pipeline_Direct',
                            'transport_mode': 'pipeline',
                            'daily_ng_consumption_m3': daily_ng_consumption_m3,
                            'capacity_kg_saf_per_hour': ft_info.get('capacity_kg_saf_per_hour', 0),
                            'route_coordinates': []  # 添加空的路径坐标字段
                        }
                    else:
                        logger.warning(f"  FT设施 {location_id} 无法找到源坐标: source_type={source_type}, source_id={source_id}")
                else:
                    logger.debug(f"  FT设施 {location_id} 不是管道直供类型: source_type={ft_location_data.get('source_type', 'N/A')}")
            else:
                logger.warning(f"  FT设施 {location_id} 在候选位置中未找到")

        logger.info(f"遍历的FT设施数: {ng_pipeline_direct_count}")
        logger.info(f"提取的管道直供记录数: {len(solution['ng_pipeline_direct'])}")

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
                'ng_extraction': '天然气开采',
                'saf_facility': 'SAF工厂建设',
                'ng_to_methanol': '天然气制甲醇',
                'methanol_to_saf': '甲醇制SAF',
                'mtj_storage': 'MTJ储存',
                'mtj_transport': 'MTJ运输',
                'ng_transport': '天然气运输'
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
        
        # 首先保存基础设施选点信息
        self._save_infrastructure_locations(output_dir, timestamp)
        
        # 从solution中获取不含短缺成本的平准化成本
        lifecycle_levelized_cost_excluding_shortage = solution.get("lifecycle_levelized_cost_excluding_shortage_per_kg", 0)

        # 注意：不再计算基于配置参数的理论单位成本（会与优化结果混淆）
        # 优化结果的平准化成本(6.07元/kg)是整个供应链系统优化后的实际成本
        # 它包含了所有投资、运营、原料、运输等成本，并考虑了20年项目期折现
        unit_costs = {}  # 不使用理论成本计算
        logger.info("直接从优化模型计算单位成本数据用于optimization_summary")

        # 获取表达式对象的成本分解结果
        cost_breakdown = solution.get('cost_breakdown', {})
        logger.info(f"从表达式对象获取的成本分解数据: {len(cost_breakdown)} 项")

        # 建立表达式对象字段到CSV输出字段的映射
        cost_field_mapping = {
            'facility_investment_cost': 'MTJ工厂建设投资(元)',
            'storage_equipment_cost': 'MTJ储存设备投资(元)',
            'facility_operation_cost': 'MTJ工厂运营成本(元)',
            'production_cost': 'MTJ生产运营成本(元)',
            'ng_transport_operation': '天然气运输成本(元)',
            'natural_gas_cost': '天然气原料成本(元)',
            'transport_operation_cost': 'MTJ运输运营成本(元)',
            'storage_operation_cost': 'MTJ储存运营成本(元)',
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
        investment_fields = ['facility_investment_cost',
                           'storage_equipment_cost',
                           'ng_transport_investment']

        # 运营成本类别
        operation_fields = ['facility_operation_cost', 'production_cost',
                          'ng_transport_operation', 'natural_gas_cost', 'transport_operation_cost',
                          'storage_operation_cost', 'electricity_cost',
                          'final_inventory_cost']

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

        # MTJ生产成本指标
        results_summary.update({
            "MTJ CO2原料成本(元/kg)": [unit_costs.get('mtj_co2_raw_material_cost_yuan_per_kg', 0)],
            "MTJ设备摊销成本(元/kg)": [unit_costs.get('mtj_equipment_amortization_yuan_per_kg', 0)],
            "MTJ运营维护成本(元/kg)": [unit_costs.get('mtj_operation_maintenance_yuan_per_kg', 0)],
            "MTJ总单位成本(元/kg)": [unit_costs.get('mtj_total_production_cost_yuan_per_kg', 0)]
        })

        # 运输储存成本指标
        results_summary.update({
            "MTJ运输单位成本(元/kg·km)": [unit_costs.get('mtj_transport_unit_cost_yuan_per_kg_km', 0)],
            "MTJ储存单位成本(元/kg)": [unit_costs.get('mtj_storage_cost_yuan_per_kg', 0)]
        })

        # 经济性指标
        results_summary.update({
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

        # 添加SAF运输路径（修复BUG：使用正确的键名'saf_transport'而非'transport_plan'）
        for transport_id, info in solution.get("saf_transport", {}).items():
            # 序列化路径坐标为JSON字符串
            route_coords_str = json.dumps(info.get("route_coordinates", [])) if info.get("route_coordinates") else "[]"

            all_transport_summary.append({
                "路径ID": transport_id,
                "起点": info.get("from_location", ""),
                "终点": info.get("to_airport", ""),
                "起点类型": "FT设施",
                "终点类型": "机场",
                "距离(km)": info.get("distance_km", 0),
                "起点坐标": f"({info.get('from_latitude', 0):.4f}, {info.get('from_longitude', 0):.4f})",
                "终点坐标": f"({info.get('to_latitude', 0):.4f}, {info.get('to_longitude', 0):.4f})",
                "路径坐标": route_coords_str,  # 真实路径坐标
                "货物类型": "SAF",
                "运输方式": info.get("transport_mode", "truck"),
                "周运输量(kg)": info.get("transport_kg_saf", 0),
                "时间单位": "周"
            })

        # 添加天然气罐车运输路径（从NG供应源到FT设施）
        for transport_id, info in solution.get("ng_transport", {}).items():
            all_transport_summary.append({
                "路径ID": transport_id,
                "起点": info.get("from_source", ""),
                "终点": info.get("to_location", ""),
                "起点类型": "天然气供应源",
                "终点类型": "FT设施",
                "距离(km)": info.get("distance_km", 0),
                "起点坐标": f"({info.get('from_latitude', 0):.4f}, {info.get('from_longitude', 0):.4f})",
                "终点坐标": f"({info.get('to_latitude', 0):.4f}, {info.get('to_longitude', 0):.4f})",
                "货物类型": "天然气",
                "运输方式": info.get("transport_mode", "truck"),
                "日运输量(m3)": info.get("transport_m3_ng", 0),
                "时间单位": "天"
            })

        # 添加天然气管道直供路径（增强功能：为管道直供的FT设施添加可视化连线）
        for transport_id, info in solution.get("ng_pipeline_direct", {}).items():
            all_transport_summary.append({
                "路径ID": transport_id,
                "起点": info.get("from_source", ""),
                "终点": info.get("to_location", ""),
                "起点类型": "天然气管道端点",
                "终点类型": "FT设施",
                "距离(km)": info.get("distance_km", 0),
                "起点坐标": f"({info.get('from_latitude', 0):.4f}, {info.get('from_longitude', 0):.4f})",
                "终点坐标": f"({info.get('to_latitude', 0):.4f}, {info.get('to_longitude', 0):.4f})",
                "货物类型": "天然气",
                "运输方式": "pipeline",
                "日运输量(m3)": info.get("daily_ng_consumption_m3", 0),
                "时间单位": "天"
            })

        # 调试日志：统计运输汇总数据来源
        saf_count = len(solution.get("saf_transport", {}))
        ng_count = len(solution.get("ng_transport", {}))
        pipeline_count = len(solution.get("ng_pipeline_direct", {}))
        logger.info(f"\n=== 运输汇总CSV生成统计 ===")
        logger.info(f"SAF运输记录数: {saf_count}")
        logger.info(f"天然气罐车运输记录数: {ng_count}")
        logger.info(f"天然气管道直供记录数: {pipeline_count}")
        logger.info(f"运输汇总总记录数: {len(all_transport_summary)}")

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

        # 1. 保存LNG接收站信息
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

        # 2. 保存天然气管道信息
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
        elif location_type in ['byproduct_hydrogen_steel', 'byproduct_hydrogen_refinery']:
            avg_gen = np.mean(location_info['hourly_generation']) if location_info['hourly_generation'] else 0
            type_name = "钢铁副产氢" if location_type == 'byproduct_hydrogen_steel' else "炼油副产氢"
            return f"{type_name}, 平均产能{avg_gen:.1f}kg/h"
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


    def _generate_ft_facility_candidates(self):
        """
        生成FT设施候选位置（基于天然气供应可达性筛选）

        【重构说明】
        - 不再使用self.ft_facility_candidates列表
        - 统一存储在self.locations字典中，通过'is_ft_candidate': True标记
        - 所有FT候选位置的location_id格式为 'ft_candidate_{id}'

        候选位置来源：
        1. 天然气管道端点（有足够产能）
        2. LNG接收站
        3. 机场附近50km范围内的天然气节点

        Returns:
            None (结果存储在self.locations中)
        """
        logger.info("生成FT设施候选位置...")

        candidate_id = 1

        # 1. 筛选天然气管道端点作为FT设施候选位置
        logger.info("筛选天然气管道端点...")
        for pipeline_id, pipeline_data in self.ng_pipeline_sources.items():
            # 检查管道容量
            capacity = pipeline_data.get('max_flow_m3_per_hour', 0)
            if capacity < 1000:  # 最小容量阈值：1000 m³/h
                continue

            location_id = f'ft_candidate_{candidate_id}'

            # 统一存储在self.locations中
            self.locations[location_id] = {
                'type': 'ng_pipeline',  # 使用实际源类型，匹配技术配置的suitable_locations
                'is_ft_candidate': True,  # 关键标记：用于识别FT候选位置
                'name': f'FT设施候选点{candidate_id}',
                'latitude': pipeline_data['lat'],
                'longitude': pipeline_data['lon'],
                'source_type': 'ng_pipeline',
                'source_id': pipeline_id,
                'ng_supply_capacity_m3_per_hour': capacity,
                'ng_price_yuan_per_m3': pipeline_data.get('natural_gas_price_yuan_per_10k_m3', 4.2)
            }

            candidate_id += 1

        pipeline_count = candidate_id - 1
        logger.info(f"从天然气管道筛选了{pipeline_count}个候选位置")

        # 2. 添加LNG接收站作为候选位置
        logger.info("添加LNG接收站作为候选位置...")
        lng_count = 0
        for terminal_id, terminal_data in self.lng_terminals.items():
            location_id = f'ft_candidate_{candidate_id}'

            # 统一存储在self.locations中
            self.locations[location_id] = {
                'type': 'lng_terminal',  # 使用实际源类型，匹配技术配置的suitable_locations
                'is_ft_candidate': True,  # 关键标记：用于识别FT候选位置
                'name': f'FT设施候选点{candidate_id}(LNG接收站)',
                'latitude': terminal_data['lat'],
                'longitude': terminal_data['lon'],
                'source_type': 'lng_terminal',
                'source_id': terminal_id,
                'ng_supply_capacity_m3_per_hour': terminal_data.get('effective_daily_capacity_m3_per_day', 100000) / 24,
                'ng_price_yuan_per_m3': terminal_data.get('cost_yuan_per_mcm', 200) / 10000
            }

            candidate_id += 1
            lng_count += 1

        logger.info(f"添加了{lng_count}个LNG接收站候选位置")

        # 3. 在机场附近50km范围内查找天然气节点
        logger.info("在机场附近50km范围内查找天然气节点...")
        airport_nearby_count = 0
        for airport_id, airport_data in self.airports.items():
            airport_lat = airport_data['latitude']
            airport_lon = airport_data['longitude']

            # 查找该机场附近50km内的天然气管道端点
            for pipeline_id, pipeline_data in self.ng_pipeline_sources.items():
                pipeline_lat = pipeline_data['lat']
                pipeline_lon = pipeline_data['lon']

                # 计算距离
                distance_km = self._calculate_haversine_distance(
                    airport_lat, airport_lon,
                    pipeline_lat, pipeline_lon
                )

                if distance_km <= 50:  # 50km范围内
                    # 检查是否已经添加过这个位置（避免重复）
                    is_duplicate = any(
                        loc_data.get('source_id') == pipeline_id
                        for loc_id, loc_data in self.locations.items()
                        if loc_data.get('is_ft_candidate') and loc_data.get('source_type') == 'ng_pipeline'
                    )

                    if not is_duplicate:
                        location_id = f'ft_candidate_{candidate_id}'

                        # 统一存储在self.locations中
                        self.locations[location_id] = {
                            'type': 'ng_pipeline',  # 使用实际源类型（机场附近是管道端点）
                            'is_ft_candidate': True,  # 关键标记：用于识别FT候选位置
                            'name': f'FT设施候选点{candidate_id}(机场附近)',
                            'latitude': pipeline_lat,
                            'longitude': pipeline_lon,
                            'source_type': 'ng_pipeline',
                            'source_id': pipeline_id,
                            'ng_supply_capacity_m3_per_hour': pipeline_data.get('max_flow_m3_per_hour', 5000),
                            'ng_price_yuan_per_m3': pipeline_data.get('natural_gas_price_yuan_per_10k_m3', 4.2),
                            'near_airport': airport_id,
                            'distance_to_airport_km': distance_km
                        }

                        candidate_id += 1
                        airport_nearby_count += 1

        logger.info(f"在机场附近添加了{airport_nearby_count}个候选位置")

        # 4. 【新增】将机场本身作为FT候选位置（假设可从最近管道输送天然气）
        logger.info("将机场本身作为FT候选位置...")
        airport_as_candidate_count = 0
        for airport_id, airport_data in self.airports.items():
            airport_lat = airport_data['latitude']
            airport_lon = airport_data['longitude']

            # 查找最近的天然气管道端点
            nearest_pipeline_id = None
            nearest_distance = float('inf')
            nearest_pipeline_data = None

            for pipeline_id, pipeline_data in self.ng_pipeline_sources.items():
                pipeline_lat = pipeline_data['lat']
                pipeline_lon = pipeline_data['lon']

                distance_km = self._calculate_haversine_distance(
                    airport_lat, airport_lon,
                    pipeline_lat, pipeline_lon
                )

                if distance_km < nearest_distance:
                    nearest_distance = distance_km
                    nearest_pipeline_id = pipeline_id
                    nearest_pipeline_data = pipeline_data

            # 如果找到最近管道且距离在合理范围内（100km）
            if nearest_pipeline_id and nearest_distance <= 100:
                location_id = f'ft_candidate_{candidate_id}'

                # 天然气管道运输成本（假设每km每m³成本）
                ng_pipeline_transport_cost_per_km = 0.01  # 元/m³/km

                # 统一存储在self.locations中
                self.locations[location_id] = {
                    'type': 'airport',  # 使用机场类型
                    'is_ft_candidate': True,  # 关键标记：用于识别FT候选位置
                    'name': f'FT设施候选点{candidate_id}(机场{airport_id})',
                    'latitude': airport_lat,
                    'longitude': airport_lon,
                    'source_type': 'airport_with_ng_supply',  # 新的源类型
                    'source_id': airport_id,
                    'ng_supply_capacity_m3_per_hour': nearest_pipeline_data.get('max_flow_m3_per_hour', 5000),
                    # 天然气价格与管道端点相同（假设管道延伸到机场，无额外运输成本）
                    'ng_price_yuan_per_m3': nearest_pipeline_data.get('natural_gas_price_yuan_per_10k_m3', 4.2),
                    'nearest_pipeline_id': nearest_pipeline_id,
                    'ng_transport_distance_km': nearest_distance,
                    'at_airport': airport_id,
                    'distance_to_airport_km': 0  # 就在机场，SAF运输距离为0
                }

                candidate_id += 1
                airport_as_candidate_count += 1
                logger.info(f"  机场 {airport_id}: 最近管道距离 {nearest_distance:.2f} km")

        logger.info(f"将{airport_as_candidate_count}个机场添加为FT候选位置")

        # 去重处理（基于位置坐标）
        self._deduplicate_ft_candidates_in_locations()

        # 统计FT候选位置总数
        ft_candidate_count = sum(1 for loc in self.locations.values() if loc.get('is_ft_candidate'))
        logger.info(f"去重后，共生成{ft_candidate_count}个FT设施候选位置")

    def _deduplicate_ft_candidates_in_locations(self):
        """
        去除self.locations中重复的FT候选位置（基于地理坐标）

        【重构说明】
        - 直接在self.locations字典中进行去重
        - 保留第一个出现的位置，删除后续重复的位置
        """
        seen_coords = set()
        locations_to_remove = []

        for location_id, location_data in self.locations.items():
            # 只处理FT候选位置
            if not location_data.get('is_ft_candidate'):
                continue

            # 使用坐标的元组作为唯一标识（保留2位小数）
            coord_key = (
                round(location_data['latitude'], 2),
                round(location_data['longitude'], 2)
            )

            if coord_key in seen_coords:
                locations_to_remove.append(location_id)
            else:
                seen_coords.add(coord_key)

        # 删除重复的位置
        for location_id in locations_to_remove:
            del self.locations[location_id]

        if locations_to_remove:
            logger.info(f"去重：删除了{len(locations_to_remove)}个重复的FT候选位置")

    def _get_ft_candidate_ids(self):
        """
        获取所有FT候选位置的location_id列表

        【辅助方法】用于替代之前的self.ft_facility_candidates列表

        Returns:
            List[str]: FT候选位置的location_id列表
        """
        return [
            location_id
            for location_id, location_data in self.locations.items()
            if location_data.get('is_ft_candidate')
        ]

    def _calculate_haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        使用Haversine公式计算两点间的球面距离

        Args:
            lat1, lon1: 第一个点的纬度和经度
            lat2, lon2: 第二个点的纬度和经度

        Returns:
            float: 距离（公里）
        """
        from math import radians, sin, cos, sqrt, atan2

        R = 6371  # 地球平均半径（公里）

        lat1_rad = radians(lat1)
        lat2_rad = radians(lat2)
        delta_lat = radians(lat2 - lat1)
        delta_lon = radians(lon2 - lon1)

        a = sin(delta_lat / 2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(delta_lon / 2)**2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))

        distance = R * c
        return distance

    def _analyze_supply_chain_paths(self, solution: Dict) -> Dict:
        """分析详细的供应链路径（天然气来源）"""
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
                'natural_gas_supply_chain': {},
                'total_production_kg': 0,
                'supply_costs': {}
            }

            # 1. 分析天然气供应链
            facility_analysis['natural_gas_supply_chain'] = self._analyze_natural_gas_supply_for_location(location)

            # 2. 计算总生产量
            total_production = 0
            for prod_key, prod_info in solution['production_schedule'].items():
                if prod_info['location'] == location and prod_info['technology'] == technology:
                    total_production += prod_info['production_kg']
            facility_analysis['total_production_kg'] = total_production

            # 3. 分析供应成本
            facility_analysis['supply_costs'] = self._calculate_supply_costs_for_location(location, technology, total_production)
            
            supply_chain_analysis[facility_key] = facility_analysis
        
        # 添加供应链汇总信息
        supply_chain_analysis['summary'] = self._create_supply_chain_summary(supply_chain_analysis)
        
        return supply_chain_analysis
    
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
                pipeline_price = price_per_10k_m3  # 数据文件中已经是元/m³，无需转换
                logger.debug(f"从管道 {pipeline_id} 获取天然气价格: {pipeline_price:.3f} 元/m³")
                break
        
        # 2. 如果找到管道价格，使用管道价格
        if pipeline_price is not None:
            return pipeline_price
            
        # 3. 如果没有找到管道价格，使用配置文件默认价格
        config_price = self.costs['natural_gas_price_yuan_per_m3']
        logger.debug(f"使用配置文件默认天然气价格: {config_price:.3f} 元/m³")
        return config_price
    
    def _calculate_supply_costs_for_location(self, location: str, technology: str, total_production_kg: float) -> Dict:
        """计算指定位置的供应成本 - FT一步法"""
        supply_costs = {
            'natural_gas_cost_yuan': 0,
            'transport_cost_yuan': 0,
            'total_levelized_supply_cost_yuan': 0,
            'unit_levelized_supply_cost_yuan_per_kg': 0
        }

        tech_info = self.technologies[technology]

        # 天然气成本
        ng_consumption = total_production_kg * tech_info.get('ng_consumption_ratio', 0)
        ng_price = self._get_natural_gas_price_yuan_per_m3(location)
        supply_costs['natural_gas_cost_yuan'] = ng_consumption * ng_price

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
            supply_costs['natural_gas_cost_yuan'] +
            supply_costs['transport_cost_yuan']
        )

        if total_production_kg > 0:
            supply_costs['unit_levelized_supply_cost_yuan_per_kg'] = (
                supply_costs['total_levelized_supply_cost_yuan'] / total_production_kg
            )

        return supply_costs
    
    def _create_supply_chain_summary(self, supply_chain_analysis: Dict) -> Dict:
        """创建供应链汇总信息 - FT一步法"""
        summary = {
            'total_facilities': len([k for k in supply_chain_analysis.keys() if k != 'summary']),
            'total_production_kg': 0,
            'total_levelized_supply_cost_yuan': 0,
            'avg_unit_levelized_cost_yuan_per_kg': 0,
            'natural_gas_supply_breakdown': {
                'lng_terminal_direct': 0,
                'pipeline_transport': 0
            }
        }

        for facility_key, facility_analysis in supply_chain_analysis.items():
            if facility_key == 'summary':
                continue

            summary['total_production_kg'] += facility_analysis['total_production_kg']
            summary['total_levelized_supply_cost_yuan'] += facility_analysis['supply_costs']['total_levelized_supply_cost_yuan']

            # 天然气供应统计
            ng_source = facility_analysis['natural_gas_supply_chain']['primary_source']
            if 'LNG接收站直供' in ng_source:
                summary['natural_gas_supply_breakdown']['lng_terminal_direct'] += 1
            elif '管道运输' in ng_source:
                summary['natural_gas_supply_breakdown']['pipeline_transport'] += 1
        
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
        
        # 天然气供应约束已移除 - 允许无限制供应
        # if max_flow_m3_per_hour > 0:
        #     self.model.addConstr(
        #         ng_demand <= max_flow_m3_per_hour,
        #         name=f"ng_supply_{location}_{hour}"
        #     )
        logger.debug(f"天然气供应约束已移除，{location}在{hour}小时无流量限制")

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
                    # 使用动态技术列表
                    for tech in self.technologies.keys()
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
                    # 使用动态技术列表
                    for tech in self.technologies.keys()
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
        """计算并更新平均运输距离统计 - FT一步法"""
        logger.info("开始计算平均运输距离统计...")

        # 计算天然气运输平均距离（管道到非LNG接收站）
        ng_distances = []
        ng_locations = list(self.ng_pipeline_sources.keys())[:5]  # 天然气源位置
        non_lng_mtj_locations = [loc for loc, info in self.locations.items()
                               if info['type'] in ['industrial_park', 'port']][:5]
        
        for ng_loc in ng_locations:
            for mtj_loc in non_lng_mtj_locations:
                distance = self._calculate_location_distance(ng_loc, mtj_loc)
                ng_distances.append(distance)
        
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
                distance = self._calculate_distance(loc, airport)
                airport_distances.append(distance)
        
        if airport_distances:
            avg_airport_distance = np.mean(airport_distances)
            logger.info(f"机场运输平均距离: {avg_airport_distance:.1f}km "
                       f"(基于{len(airport_distances)}个样本)")
        
        logger.info("距离统计计算完成")


if __name__ == '__main__':
    """主执行块 - FT一步法模型"""
    try:
        logger.info("开始执行天然气供应链优化模型（FT一步法）...")

        # 1. 初始化优化器
        base_dir = get_project_base_dir()

        # 设置配置文件路径
        config_path = os.path.join(base_dir, "shared", "data",
                                   "NaturalGasSupplyChainOptimizer_config_one_step.yaml")

        # 设置OSM文件路径
        osm_file_path = os.path.join(base_dir, "products", "supply_chain_optimization",
                                   "natural_gas_supply_chain_optimization", "data", "china-latest.osm.pbf")

        optimizer = NaturalGasSupplyChainOptimizerOneStep(
            config_path=config_path,
            time_horizon_weeks=12,  # 使用12周时间窗口，与绿氢配置保持一致
            osm_pbf_path=osm_file_path
        )

        # 2. 加载数据 - 使用继承的load_data_from_excel()方法
        # 该方法会自动从配置文件获取数据路径并处理Excel列名兼容性
        optimizer.load_data_from_excel(
            airport_excel_path=None,  # 从配置文件自动获取路径
            renewable_data=None  # FT一步法不需要可再生能源数据
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
                time_window_weeks = solution.get('time_window_weeks', 4)
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

                # 输出FT设施建设数量
                ft_facilities_count = len(solution.get('ft_facilities', {}))
                logger.info(f"  - 建设FT设施数量: {ft_facilities_count}")
                logger.info(f"  - 优化时间窗口: {time_window_weeks} 周")

            # 保存结果到results目录
            results_dir = os.path.join(base_dir, "products", "supply_chain_optimization",
                                      "natural_gas_supply_chain_optimization", "results", "ft_one_step")
            os.makedirs(results_dir, exist_ok=True)
            optimizer.save_results(solution, results_dir)
            print(f"\n结果已保存到目录: {results_dir}")
            print("="*50)
        else:
            logger.error("模型求解失败或未返回结果。")

    except Exception as e:
        logger.error("="*80)
        logger.error("FT一步法模型执行过程中发生严重错误")
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
