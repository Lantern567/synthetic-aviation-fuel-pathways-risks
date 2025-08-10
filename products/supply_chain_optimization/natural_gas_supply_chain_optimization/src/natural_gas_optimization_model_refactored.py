"""
天然气基供应链优化模型 - 重构版本
基于Gurobi求解器的混合整数线性规划模型
包含时间尺度匹配：生产(1小时) vs 需求(1周)
集成OSM真实路网数据进行距离计算和路径规划

重构说明：使用模块化组件替换原有单体代码
- 地理计算：使用 shared.utils.GeographicCalculator
- 数据处理：使用 tools.data_processing.RenewableDataProcessor  
- 成本计算：使用 shared.core.CostCalculator
- 优化建模：使用 tools.optimization.GurobiModelBuilder
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
from datetime import datetime

# 导入新的模块化组件
import sys
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
sys.path.append(project_root)

from shared.utils.geographic_calculator import GeographicCalculator
try:
    from shared.utils.log_preserver import mount_file_logging
except ModuleNotFoundError:
    import sys
    # 动态加入项目根目录到sys.path后重试
    current_file = os.path.abspath(__file__)
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file)))))
    if project_root not in sys.path:
        sys.path.append(project_root)
    from shared.utils.log_preserver import mount_file_logging
from tools.data_processing.renewable_data_processor import RenewableDataProcessor
from shared.core.cost_calculator import CostCalculator, EconomicParametersManager
# 延迟导入Gurobi模型构建器，避免在仅进行数据加载/距离计算时引入不必要依赖

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


# 在模块加载时尽早挂载日志文件输出（仅作用于logging，不捕获print）
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
    """天然气基供应链优化器 - 重构版本使用模块化组件"""
    
    def __init__(self, time_horizon_weeks: int = 1, use_graphhopper_routing: bool = True, 
                 osm_pbf_path: str = None,
                 graphhopper_host: str = "localhost",
                 graphhopper_port: int = 8989,
                 max_transport_distance_km: float = 1000.0,
                 use_routing_for_short_distance: bool = True):
        """
        初始化优化器
        
        Args:
            time_horizon_weeks: 优化时间范围(周数)，默认1周以减少内存使用
            use_graphhopper_routing: 是否使用GraphHopper本地路径规划
            osm_pbf_path: 本地OSM数据文件路径
            graphhopper_host: GraphHopper服务主机地址
            graphhopper_port: GraphHopper服务端口
            max_transport_distance_km: 最大运输距离限制(公里)，超过此距离使用直线距离估算
            use_routing_for_short_distance: 对短距离路径是否使用路径规划精确计算
        """
        self.time_horizon_weeks = time_horizon_weeks
        self.hours_per_week = 168  # 7天 * 24小时
        self.total_hours = time_horizon_weeks * self.hours_per_week
        
        # 模型组件
        self.model = None
        self.locations = {}
        self.technologies = {}
        self.airports = {}
        self.costs = {}
        
        # 天然气基供应链专用数据
        self.ng_pipeline_sources = {}     # 天然气管段数据
        self.lng_terminals = {}           # LNG接收站数据
        self.transport_modes = {}         # 运输模式数据
        
        # LNG容量平均值（从实际数据计算得出）
        self.avg_lng_capacity_mcm_per_year = 1000  # 默认值，在数据加载后会更新
        
        # 通过GraphHopper路径规划计算得出的距离统计值（用于模型中的参考）
        self.avg_hydrogen_transport_distance = None  # 将通过GraphHopper路径规划计算得出
        self.avg_ng_transport_distance = None  # 将通过GraphHopper路径规划计算得出
        
        # 决策变量
        self.production_vars = {}  # 小时级生产变量
        self.facility_vars = {}    # 设施建设变量
        self.transport_vars = {}   # 运输变量
        self.storage_vars = {}     # 库存变量
        
        # 初始化模块化组件
        self.geographic_calculator = GeographicCalculator()
        self.renewable_data_processor = RenewableDataProcessor(
            total_hours=self.total_hours, 
            max_distance_km=500
        )
        # 设置与原版一致的经济参数（8%贴现率，20年生命周期）
        self.economic_params = EconomicParametersManager.define_default_economic_parameters()
        # 覆盖默认参数以匹配原版
        self.economic_params.update({
            'discount_rate': 0.08,  # 从5%改为8%，与原版一致
            'project_lifespan': 20,
            'mtj_plant_lifetime': 20,
            'electrolyzer_lifetime': 15,
            'pipeline_lifetime': 30,
            'storage_lifetime': 25,
            'transport_vehicle_lifetime': 10,
            'mtj_plant_capacity_factor': 0.85,
            'electrolyzer_capacity_factor': 0.80,
            'pipeline_capacity_factor': 0.95,
            'storage_capacity_factor': 0.90,
            'transport_capacity_factor': 0.75,
            'transport_cost_yuan_per_km_kg': 0.15,
            'hydrogen_transport_cost_yuan_per_kg_km': 0.85,
        })
        
        # 使用正确的经济参数初始化成本计算器
        self.cost_calculator = CostCalculator(
            discount_rate=self.economic_params['discount_rate'],
            project_lifespan=self.economic_params['project_lifespan']
        )
        
        # 优化模型构建器（稍后初始化）
        self.model_builder = None
        self.constraint_builder = None
        self.objective_builder = None
        
        # 初始化GraphHopper路径规划引擎
        self.use_graphhopper_routing = use_graphhopper_routing
        
        # 设置OSM数据文件路径
        if osm_pbf_path is None:
            # 使用项目中的默认OSM数据文件
            project_root = get_project_base_dir()
            self.osm_pbf_path = os.path.join(project_root, "products", "supply_chain_optimization", 
                                           "natural_gas_supply_chain_optimization", "data", "china-latest.osm.pbf")
        else:
            self.osm_pbf_path = osm_pbf_path
            
        if use_graphhopper_routing:
            # 创建缓存目录 - 使用shared/data/cache路径
            cache_dir = os.path.join(get_project_base_dir(), "shared", "data", "cache", "graphhopper_routes")
            
            self.routing_engine = GraphHopperRoutingEngine(
                osm_pbf_path=self.osm_pbf_path,
                graphhopper_host=graphhopper_host,
                graphhopper_port=graphhopper_port,
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
        self.graphhopper_host = graphhopper_host
        self.graphhopper_port = graphhopper_port
        self.max_transport_distance_km = max_transport_distance_km
        self.use_routing_for_short_distance = use_routing_for_short_distance
        
        # 距离计算统计
        self.distance_stats = {
            'total_requests': 0,
            'routing_calls': 0,
            'cache_hits': 0,
            'haversine_fallback': 0,
            'exceeded_max_distance': 0
        }
        
        logger.info(f"初始化优化器: {time_horizon_weeks}周 ({self.total_hours}小时), GraphHopper路径规划: {use_graphhopper_routing}")
        logger.info(f"OSM数据文件: {osm_pbf_path}")
        logger.info(f"GraphHopper服务: {graphhopper_host}:{graphhopper_port}")
        logger.info(f"最大运输距离限制: {max_transport_distance_km} 公里")
        logger.info(f"短距离路径规划精确计算: {use_routing_for_short_distance}")
    
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
    
    def load_data(self, renewable_data: pd.DataFrame, airport_data: pd.DataFrame):
        """
        加载数据 - 使用模块化数据处理器
        
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
        
        # 使用与原版一致的处理逻辑（包含缓存与500km过滤）
        try:
            self._process_renewable_data(renewable_data)
        except Exception as e:
            logger.error(f"可再生能源数据处理失败，回退到降级方法: {e}")
            self._process_renewable_data_fallback(renewable_data)

        # 将天然气管道源纳入通用locations，避免后续距离计算找不到pipeline_*键
        self._merge_ng_pipelines_into_locations()
        
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
    
    def load_data_from_excel(self, airport_excel_path: str, renewable_data: pd.DataFrame = None):
        """
        从Excel文件加载机场数据
        
        Args:
            airport_excel_path: 机场数据Excel文件路径
            renewable_data: 可再生能源数据(如果为None，将创建示例数据)
        """
        logger.info(f"从Excel文件加载数据: {airport_excel_path}")
        
        # 使用真实结构解析Excel；固定使用 Sheet1（与用户确认一致）
        try:
            excel_df = pd.read_excel(airport_excel_path, sheet_name='All_Airports')
            logger.info(f"Excel文件读取成功(All_Airports)，包含 {len(excel_df)} 行数据")
        except Exception as e:
            logger.error(f"读取Excel文件失败（All_Airports）: {e}")
            raise
        
        # 基于真实字段解析机场周需求与坐标
        airport_data = self._process_airport_excel_real(excel_df)
        
        # 如果没有提供可再生能源数据，必须加载真实数据
        if renewable_data is None:
            renewable_data = self._load_real_renewable_data()
        
        # 使用统一的load_data方法
        self.load_data(renewable_data, airport_data)

    def _merge_ng_pipelines_into_locations(self):
        """将天然气管道源合并进通用的locations字典，供距离计算与约束构建统一使用。"""
        if not hasattr(self, 'ng_pipeline_sources') or not self.ng_pipeline_sources:
            return
        merged = 0
        for pipeline_id, info in self.ng_pipeline_sources.items():
            if pipeline_id in self.locations:
                continue
            lat = float(info.get('lat', info.get('center_latitude', 40.0)))
            lon = float(info.get('lon', info.get('center_longitude', 116.0)))
            self.locations[pipeline_id] = {
                'type': 'gas_field',
                'latitude': lat,
                'longitude': lon,
                'capacity_mcm_per_day': info.get('capacity_mcm_per_day'),
                'is_ng_source': True,
            }
            merged += 1
        if merged > 0:
            logger.info(f"已将 {merged} 个天然气管段源并入locations，统一参与距离计算与建模")

    def _process_airport_excel_real(self, excel_df: pd.DataFrame) -> pd.DataFrame:
        """
        基于真实Excel结构解析机场数据，直接生成每个机场的完整周序列列表（weekly_demand_series），与原版一致。
        输出字段：
          - airport: 机场名称
          - weekly_demand_series: list[float]，按周序号升序
          - latitude/longitude: 若Excel提供则附带
        """
        # 规范化列名
        original_cols = list(excel_df.columns)
        lower_to_original = {str(c).strip().lower(): c for c in original_cols}
        synonyms = {
            'departure_airport_name': ['departure_airport_name', 'airport', 'airport_name', 'departure_airport', '出发机场', '机场', '起飞机场'],
            'week_number': ['week_number', 'week', 'week_no', 'weekindex', '周数', '周'],
            'weekly_total_fuel_kg_total': ['weekly_total_fuel_kg_total', 'weekly_total_fuel_kg', 'weekly_fuel_kg', 'weekly_methanol_kg', '总甲醇消耗_kg', '周总甲醇消耗_kg'],
            'departure_airport_latitude': ['departure_airport_latitude', 'latitude', 'lat', '机场纬度', '纬度'],
            'departure_airport_longitude': ['departure_airport_longitude', 'longitude', 'lon', '机场经度', '经度']
        }

        rename_map: Dict[str, str] = {}
        for canonical, alias_list in synonyms.items():
            for alias in alias_list:
                key = alias.lower()
                if key in lower_to_original:
                    rename_map[lower_to_original[key]] = canonical
                    break

        excel_df = excel_df.rename(columns=rename_map)

        required_cols = {'departure_airport_name', 'week_number', 'weekly_total_fuel_kg_total'}
        if not required_cols.issubset(set(excel_df.columns)):
            raise ValueError("机场Excel缺少必要字段：departure_airport_name, week_number, weekly_total_fuel_kg_total")

        lat_col = 'departure_airport_latitude' if 'departure_airport_latitude' in excel_df.columns else None
        lon_col = 'departure_airport_longitude' if 'departure_airport_longitude' in excel_df.columns else None

        processed_rows = []
        for airport_name, group in excel_df.groupby('departure_airport_name'):
            group_sorted = group.sort_values('week_number')
            weekly_series = []
            for _, row in group_sorted.iterrows():
                try:
                    weekly_series.append(float(row['weekly_total_fuel_kg_total']))
                except Exception:
                    weekly_series.append(0.0)

            row_out = {
                'airport': str(airport_name),
                'weekly_demand_series': weekly_series
            }

            if lat_col and lon_col:
                try:
                    row_out['latitude'] = float(group_sorted.iloc[0][lat_col])
                    row_out['longitude'] = float(group_sorted.iloc[0][lon_col])
                except Exception:
                    pass

            processed_rows.append(row_out)

        result_df = pd.DataFrame(processed_rows)
        logger.info(f"按真实Excel结构处理完成，包含 {len(result_df)} 个机场，生成 weekly_demand_series 列")
        return result_df
    
    def _process_renewable_data_fallback(self, renewable_data: pd.DataFrame):
        """降级处理可再生能源数据的方法（使用模块化组件）"""
        logger.warning("使用降级方法处理可再生能源数据")
        
        # 使用模块化处理器的降级方法
        processed_locations = self.renewable_data_processor._process_renewable_data_fallback(
            renewable_data, self.geographic_calculator
        )
        
        # 更新locations
        self.locations.update(processed_locations)
        
        # 添加机场和LNG终端位置
        self.locations = self.renewable_data_processor.add_airports_to_locations(
            self.locations, self.airports
        )
        self.locations = self.renewable_data_processor.add_lng_terminals_to_locations(
            self.locations, self.lng_terminals
        )

    def _process_renewable_data(self, renewable_data: pd.DataFrame):
        """处理可再生能源数据（与原版一致，支持缓存并按500km过滤）"""
        try:
            # 引入缓存管理器
            try:
                from .data_cache_manager import cache_manager
            except ImportError:
                from products.supply_chain_optimization.natural_gas_supply_chain_optimization.src.data_cache_manager import cache_manager

            # 使用稳定的源标识文件，避免临时键导致缓存失效
            project_root = get_project_base_dir()
            temp_renewable_file = os.path.join(
                project_root,
                'products', 'aviation_fuel_analysis', 'resource_flight_data_process', 'results',
                'renewable_source_marker.csv'
            )

            # 写一个轻量标识文件作为源文件（记录摘要便于哈希）
            try:
                os.makedirs(os.path.dirname(temp_renewable_file), exist_ok=True)
                summary = pd.DataFrame({
                    'records': [len(renewable_data)],
                    'plants': [renewable_data['plant_name'].nunique() if 'plant_name' in renewable_data.columns else 0]
                })
                summary.to_csv(temp_renewable_file, index=False, encoding='utf-8')
            except Exception:
                pass

            # 检查缓存
            if cache_manager.is_cache_valid('renewable_plants', temp_renewable_file):
                logger.info("使用缓存的可再生能源数据（500km过滤）")
                cached_df = cache_manager.load_filtered_data('renewable_plants')
                if cached_df is not None:
                    filtered_renewable_data = cached_df
                else:
                    logger.warning("缓存加载失败，执行完整处理")
                    filtered_renewable_data = self._filter_renewable_data(
                        renewable_data, cache_manager, temp_renewable_file
                    )
            else:
                logger.info("缓存无效或不存在，执行完整处理和过滤")
                filtered_renewable_data = self._filter_renewable_data(
                    renewable_data, cache_manager, temp_renewable_file
                )

            # 聚合到locations（取前total_hours小时）
            locations: Dict[str, Dict] = {}
            if len(filtered_renewable_data) > 0:
                for plant_name in filtered_renewable_data['plant_name'].unique():
                    plant_data = filtered_renewable_data[filtered_renewable_data['plant_name'] == plant_name]
                    if len(plant_data) >= self.total_hours:
                        hourly_data = plant_data.head(self.total_hours)
                        plant_type = hourly_data.iloc[0]['type'] if 'type' in hourly_data.columns else 'solar_plant'
                        latitude = float(hourly_data.iloc[0].get('latitude', 30.0))
                        longitude = float(hourly_data.iloc[0].get('longitude', 104.0))
                        capacity_val = hourly_data.iloc[0]['capacity_mw'] if 'capacity_mw' in hourly_data.columns else hourly_data.iloc[0].get('power_output_mw', 0.0)
                        locations[str(plant_name)] = {
                            'type': plant_type,
                            'latitude': latitude,
                            'longitude': longitude,
                            'capacity_mw': capacity_val,
                            'hourly_generation': hourly_data['power_output_mw'].tolist(),
                        }

            logger.info(f"处理了 {len(locations)} 个可再生能源发电站")
            solar_count = sum(1 for loc in locations.values() if loc['type'] == 'solar_plant')
            wind_count = sum(1 for loc in locations.values() if loc['type'] == 'wind_farm')
            logger.info(f"  太阳能发电站: {solar_count} 个")
            logger.info(f"  风电场: {wind_count} 个")

            # 写入类的locations
            self.locations.update(locations)

            # 将机场与LNG位置合入locations（复用处理器的方法，避免重复实现）
            self.locations = self.renewable_data_processor.add_airports_to_locations(self.locations, self.airports)
            self.locations = self.renewable_data_processor.add_lng_terminals_to_locations(self.locations, self.lng_terminals)

        except Exception as e:
            logger.error(f"处理可再生能源数据失败: {e}")
            raise

    def _filter_renewable_data(self, renewable_data: pd.DataFrame, cache_manager, temp_file: str) -> pd.DataFrame:
        """过滤可再生能源数据（500km范围内），并保存缓存"""
        logger.info(f"过滤可再生能源数据: {len(renewable_data)} 条原始记录")

        filtered_plants = []
        for plant_name in renewable_data['plant_name'].unique():
            plant_data = renewable_data[renewable_data['plant_name'] == plant_name]
            if len(plant_data) == 0:
                continue
            plant_lat = plant_data.iloc[0].get('latitude', 30.0)
            plant_lon = plant_data.iloc[0].get('longitude', 104.0)

            try:
                in_range = self.geographic_calculator.is_within_beijing_range(plant_lat, plant_lon, 500)
            except Exception:
                in_range = True

            if in_range:
                filtered_plants.append(plant_data)

        filtered_df = pd.concat(filtered_plants, ignore_index=True) if filtered_plants else pd.DataFrame()
        logger.info(f"500km范围内的可再生能源数据: {len(filtered_df)} 条记录，{filtered_df['plant_name'].nunique() if len(filtered_df)>0 else 0} 个电站")

        if len(filtered_df) > 0:
            cache_manager.save_filtered_data('renewable_plants', filtered_df, temp_file)

        return filtered_df
    
    def _define_economic_parameters(self):
        """定义经济参数 - 使用模块化参数管理器"""
        logger.info("定义经济参数（使用模块化参数管理器）...")
        
        # 使用模块化经济参数管理器
        self.economic_params = EconomicParametersManager.define_default_economic_parameters()
        
        # 验证参数有效性
        if not EconomicParametersManager.validate_economic_parameters(self.economic_params):
            raise ValueError("经济参数验证失败")
        
        logger.info("经济参数定义完成")
    
    def _define_costs(self):
        """定义成本参数 - 使用模块化成本计算器"""
        logger.info("定义成本参数（使用模块化成本计算器）...")
        
        # 确保经济参数已定义
        if not hasattr(self, 'economic_params') or not self.economic_params:
            self._define_economic_parameters()
        
        # 使用经济参数中的价格数据
        self.costs = {
            # 原料成本
            'natural_gas_cost_yuan_per_mcm': self.economic_params['natural_gas_price_yuan_per_mcm'],
            'hydrogen_cost_yuan_per_kg': self.economic_params['hydrogen_price_yuan_per_kg'], 
            'electricity_cost_yuan_per_mwh': self.economic_params['electricity_price_yuan_per_mwh'],
            
            # 产品价格
            'mtj_price_yuan_per_kg': self.economic_params['mtj_price_yuan_per_kg'],
            
            # 运输成本
            'transport_cost_yuan_per_km_per_kg': self.economic_params['transport_cost_yuan_per_km_per_kg'],
            
            # 技术成本（在_define_technologies中计算）
            'technologies': {}
        }
        
        logger.info("成本参数定义完成")
    
    def build_model(self):
        """构建优化模型 - 使用模块化模型构建器"""
        logger.info("构建Gurobi优化模型（使用模块化构建器）...")
        # 在方法内部导入，降低上游依赖耦合
        from tools.optimization.gurobi_model_builder import (
            GurobiModelBuilder,
            GurobiConstraintBuilder,
            GurobiObjectiveBuilder,
        )
        
        # 构建MTJ工厂位置映射（依赖locations和technologies）
        self._build_mtj_locations()
        
        # 定义运输位置映射
        self.hydrogen_locations = [loc for loc in self.locations if self.locations[loc]['type'] in ['solar_plant', 'wind_farm']]
        self.ng_locations = list(self.ng_pipeline_sources.keys())
        
        # 初始化模块化模型构建器
        self.model_builder = GurobiModelBuilder(time_horizon_weeks=self.time_horizon_weeks)
        
        # 构建模型并获取决策变量
        self.model = self.model_builder.build_model(
            locations=self.locations,
            technologies=self.technologies,
            airports=self.airports,
            mtj_locations=self.mtj_locations,
            non_lng_mtj_locations=self.non_lng_mtj_locations,
            hydrogen_locations=self.hydrogen_locations,
            ng_locations=self.ng_locations
        )
        
        # 获取决策变量引用
        variables = self.model_builder.get_variables()
        self.production_vars = variables['production_vars']
        self.facility_vars = variables['facility_vars']
        self.facility_capacity_vars = variables['facility_capacity_vars']
        self.transport_vars = variables['transport_vars']
        self.storage_vars = variables['storage_vars']
        self.hydrogen_production_vars = variables['hydrogen_production_vars']
        self.electrolyzer_capacity_vars = variables['electrolyzer_capacity_vars']
        self.electrolyzer_facility_vars = variables['electrolyzer_facility_vars']
        self.hydrogen_storage_vars = variables['hydrogen_storage_vars']
        self.hydrogen_transport_vars = variables['hydrogen_transport_vars']
        self.ng_transport_vars = variables['ng_transport_vars']
        self.shortage_vars = variables['shortage_vars']
        
        # 初始化约束构建器并创建约束
        self.constraint_builder = GurobiConstraintBuilder(
            model=self.model,
            variables=variables,
            locations=self.locations,
            technologies=self.technologies,
            airports=self.airports,
            time_horizon_weeks=self.time_horizon_weeks
        )
        
        self.constraint_builder.create_constraints(
            mtj_locations=self.mtj_locations,
            non_lng_mtj_locations=self.non_lng_mtj_locations,
            hydrogen_locations=self.hydrogen_locations,
            ng_locations=self.ng_locations,
            distance_calculator=self.distance_calculator
        )
        
        # 初始化目标函数构建器并创建目标函数
        self.objective_builder = GurobiObjectiveBuilder(
            model=self.model,
            variables=variables,
            costs=self.costs,
            locations=self.locations,
            technologies=self.technologies,
            airports=self.airports,
            time_horizon_weeks=self.time_horizon_weeks,
            economic_params=self.economic_params
        )
        
        self.objective_builder.create_objective(
            mtj_locations=self.mtj_locations,
            non_lng_mtj_locations=self.non_lng_mtj_locations,
            hydrogen_locations=self.hydrogen_locations,
            ng_locations=self.ng_locations,
            distance_calculator=self.distance_calculator
        )
        
        logger.info("模型构建完成")
    
    def solve(self) -> Dict:
        """求解优化模型并返回与原始实现保持一致的结果结构"""
        logger.info("开始求解优化模型...")
        
        if self.model is None:
            raise ValueError("模型尚未构建，请先调用build_model()")
        
        try:
            self.model.optimize()

            # 统一返回结构
            solution: Dict = {}
            solution['optimization_status'] = self.model.Status
            solution['optimization_time'] = getattr(self.model, 'Runtime', None)
            
            if self.model.Status == GRB.OPTIMAL:
                # 目标值（生命周期总成本）
                objective_value = getattr(self.model, 'ObjVal', 0.0)
                solution['objective_value_lifecycle_total'] = objective_value

                # 项目参数
                project_lifespan_years = (
                    self.economic_params.get('project_lifespan_years', 20)
                    if isinstance(self.economic_params, dict) else 20
                )
                solution['project_lifespan_years'] = project_lifespan_years
                solution['time_window_weeks'] = self.time_horizon_weeks

                # 计算产量与平准化成本（与原版逻辑对齐）
                total_production_in_window = 0.0
                for (location, tech, hour), var in self.production_vars.items():
                    if getattr(var, 'x', 0.0) > 0:
                        total_production_in_window += var.x

                annual_production = total_production_in_window * (52.0 / max(self.time_horizon_weeks, 1))
                lifecycle_total_production = annual_production * project_lifespan_years

                solution['annual_production_kg'] = annual_production
                solution['lifecycle_total_production_kg'] = lifecycle_total_production

                if lifecycle_total_production > 0:
                    solution['lifecycle_levelized_cost_per_kg'] = objective_value / lifecycle_total_production
                else:
                    solution['lifecycle_levelized_cost_per_kg'] = 0.0

                if annual_production > 0:
                    solution['annual_levelized_cost_per_kg'] = (objective_value / project_lifespan_years) / annual_production
                else:
                    solution['annual_levelized_cost_per_kg'] = 0.0

                # 复用简化结果提取，补充facilities/transport等
                brief = self.get_results() or {}
                solution['facilities'] = brief.get('facilities', {})
                solution['transport'] = brief.get('transport', {})

                logger.info(f"模型求解成功! 最优解: {objective_value:.2f} 元")
                return solution

            elif self.model.Status == GRB.INFEASIBLE:
                logger.error("模型不可行")
                solution['status'] = 'infeasible'
                return solution
            elif self.model.Status == GRB.UNBOUNDED:
                logger.error("模型无界")
                solution['status'] = 'unbounded'
                return solution
            else:
                logger.error(f"求解失败，状态码: {self.model.Status}")
                solution['status'] = 'failed'
                return solution
                
        except Exception as e:
            logger.error(f"求解过程出现异常: {e}")
            raise
    
    def get_results(self) -> Dict:
        """
        获取求解结果
        
        Returns:
            Dict: 包含求解结果的字典
        """
        if self.model is None or self.model.Status != GRB.OPTIMAL:
            logger.error("模型未成功求解，无法获取结果")
            return {}
        
        results = {
            'objective_value': self.model.ObjVal,
            'production': {},
            'facilities': {},
            'transport': {},
            'storage': {}
        }
        
        # 提取生产结果
        for (location, tech, hour), var in self.production_vars.items():
            if var.x > 0.01:  # 只记录有意义的生产量
                key = f"{location}_{tech}"
                if key not in results['production']:
                    results['production'][key] = []
                results['production'][key].append({
                    'hour': hour,
                    'production': var.x
                })
        
        # 提取设施建设结果
        for (location, tech), var in self.facility_vars.items():
            if var.x > 0.5:  # 二进制变量
                results['facilities'][f"{location}_{tech}"] = {
                    'built': True,
                    'capacity': self.facility_capacity_vars[(location, tech)].x
                }
        
        # 提取运输结果
        for (location, airport, week), var in self.transport_vars.items():
            if var.x > 0.01:
                results['transport'][f"{location}_to_{airport}_{week}"] = var.x
        
        return results
    
    def save_results(self, solution: Dict, output_dir: str):
        """保存求解结果"""
        import json  # 确保json模块可用
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 保存详细的求解结果
        result_file = os.path.join(output_dir, f"optimization_solution_{timestamp}.json")
        try:
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(solution, f, ensure_ascii=False, indent=2, default=str)
            logger.info(f"求解结果已保存到: {result_file}")
        except Exception as e:
            logger.error(f"保存求解结果失败: {e}")
            
        # 保存设施建设决策
        if 'facilities' in solution:
            facilities_file = os.path.join(output_dir, f"facility_decisions_{timestamp}.json")
            try:
                with open(facilities_file, 'w', encoding='utf-8') as f:
                    json.dump(solution['facilities'], f, ensure_ascii=False, indent=2)
                logger.info(f"设施决策已保存到: {facilities_file}")
            except Exception as e:
                logger.error(f"保存设施决策失败: {e}")
        
        # 保存运输决策
        if 'transport' in solution:
            transport_file = os.path.join(output_dir, f"transport_decisions_{timestamp}.json")
            try:
                with open(transport_file, 'w', encoding='utf-8') as f:
                    json.dump(solution['transport'], f, ensure_ascii=False, indent=2)
                logger.info(f"运输决策已保存到: {transport_file}")
            except Exception as e:
                logger.error(f"保存运输决策失败: {e}")
    
    # 以下是需要保留的原有方法，因为它们处理具体的业务逻辑
    # 这些方法调用模块化组件来完成具体功能
    
    def _process_airport_data(self, airport_data: pd.DataFrame):
        """处理机场数据：优先使用 Excel 中完整 weekly_demand_series，与原版保持一致"""
        logger.info("处理机场需求数据...")
        
        self.airports = {}
        for _, row in airport_data.iterrows():
            airport_name = row['airport']

            # 优先支持 weekly_demand_series 列（与原版一致，包含完整周序列）
            weekly_series: List[float] = []
            if 'weekly_demand_series' in airport_data.columns:
                series_value = row.get('weekly_demand_series')
                if isinstance(series_value, (list, tuple)):
                    weekly_series = [float(x) for x in series_value]
                else:
                    # 兼容字符串形式（如已被序列化）
                    try:
                        import ast
                        parsed = ast.literal_eval(str(series_value))
                        if isinstance(parsed, (list, tuple)):
                            weekly_series = [float(x) for x in parsed]
                    except Exception:
                        weekly_series = []
            
            if not weekly_series:
                # 兼容旧的 week_1..week_N 列，仅取到 time_horizon_weeks 长度
                temp_series: List[float] = []
                for week in range(self.time_horizon_weeks):
                    week_col = f'week_{week + 1}'
                    value = row.get(week_col, 0.0)
                    try:
                        temp_series.append(float(value))
                    except Exception:
                        temp_series.append(0.0)
                weekly_series = temp_series

            # 坐标优先取机场行自带的真实坐标
            lat_val = row.get('latitude', None)
            lon_val = row.get('longitude', None)
            if pd.notna(lat_val) and pd.notna(lon_val):
                latitude = float(lat_val)
                longitude = float(lon_val)
            else:
                coords = self._get_airport_coordinates(airport_name)
                latitude = coords.get('latitude', coords.get('lat', 40.0))
                longitude = coords.get('longitude', coords.get('lon', 116.0))

            avg_weekly = float(np.mean(weekly_series)) if weekly_series else 0.0
            max_weekly = float(np.max(weekly_series)) if weekly_series else 0.0
            total_annual = float(np.sum(weekly_series)) if weekly_series else 0.0

            self.airports[airport_name] = {
                'latitude': latitude,
                'longitude': longitude,
                'weekly_demand_series': weekly_series,
                'weekly_fuel_series': weekly_series,
                'avg_weekly_demand_kg': avg_weekly,
                'max_weekly_demand_kg': max_weekly,
                'total_annual_demand_kg': total_annual,
            }
        
        logger.info(f"处理了 {len(self.airports)} 个机场的需求数据")
    
    def _get_airport_coordinates(self, airport_name: str) -> dict:
        """获取京津冀机场坐标信息（与原版一致）"""
        airport_coords_map = {
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
            '邯郸': {'latitude': 36.5258, 'longitude': 114.4253},
        }

        if airport_name in airport_coords_map:
            return airport_coords_map[airport_name]

        logger.error(f"未知的机场名称: {airport_name}，请检查数据")
        return {'latitude': 40.0, 'longitude': 116.0}
    
    def _load_ng_pipeline_data(self):
        """加载天然气管段数据（使用集成真实数据与缓存，参考原版实现）"""
        try:
            try:
                from .data_cache_manager import cache_manager
            except ImportError:
                from products.supply_chain_optimization.natural_gas_supply_chain_optimization.src.data_cache_manager import cache_manager

            project_root = get_project_base_dir()
            integrated_file = os.path.join(project_root, "products", "supply_chain_optimization", 
                                         "natural_gas_supply_chain_optimization", "data", 
                                         "integrated_gas_pipeline_price_data_with_coords.csv")

            if not os.path.exists(integrated_file):
                logger.error(f"集成天然气数据文件不存在: {integrated_file}")
                return self._load_original_pipeline_data()

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

            # 写入 self.ng_pipeline_sources（与原版对齐字段）
            self.ng_pipeline_sources = {}
            for _, row in integrated_df.iterrows():
                pipeline_id = row['pipeline_id']
                lat = float(row.get('center_latitude') or row.get('lat'))
                lon = float(row.get('center_longitude') or row.get('lon'))
                self.ng_pipeline_sources[pipeline_id] = {
                    'name': row['pipeline_name'],
                    'operator': row['operator'],
                    'status': row['status'],
                    'year_online': row.get('year_online', 2020),
                    'capacity_mcm_per_day': row['capacity_mcm_per_day'],
                    'length_km': row['length_km'],
                    'natural_gas_price_yuan_per_10k_m3': row['natural_gas_price_yuan_per_10k_m3'],
                    'pipeline_cost_yuan_per_mcm': row['pipeline_cost_yuan_per_mcm'],
                    'transport_cost_yuan_per_mcm_km': row['transport_cost_yuan_per_mcm_km'],
                    'supply_reliability': row['supply_reliability'],
                    'center_latitude': lat,
                    'center_longitude': lon,
                    'lat': lat,
                    'lon': lon,
                    'start_latitude': row.get('start_latitude', None),
                    'start_longitude': row.get('start_longitude', None),
                    'end_latitude': row.get('end_latitude', None),
                    'end_longitude': row.get('end_longitude', None),
                }

            logger.info(f"成功加载 {len(self.ng_pipeline_sources)} 条天然气管段数据（含价格和坐标信息）")
        except Exception as e:
            logger.error(f"加载集成天然气数据失败: {e}")
            self._load_original_pipeline_data()
    
    def _load_lng_terminal_data(self):
        """加载LNG接收站数据（使用真实CSV与缓存，参考原版实现）"""
        try:
            try:
                from .data_cache_manager import cache_manager
            except ImportError:
                from products.supply_chain_optimization.natural_gas_supply_chain_optimization.src.data_cache_manager import cache_manager

            project_root = get_project_base_dir()
            lng_file = os.path.join(project_root, "products", "gis_energy_mapping", "gis_data_scraper", "scraped_gis_data", "lng_terminals.csv")
            if not os.path.exists(lng_file):
                logger.error(f"LNG接收站数据文件不存在: {lng_file}")
                raise FileNotFoundError(f"无法找到LNG接收站数据文件: {lng_file}")

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

            self.lng_terminals = {}
            for idx, row in lng_df.iterrows():
                terminal_id = f"lng_terminal_{idx+1}"
                # 容量与坐标转换对齐原版
                capacity_raw = row.get('current_capacity__Million_tonne', 0)
                try:
                    capacity_mt = float(capacity_raw) if capacity_raw else 0.0
                    capacity_mcm_per_year = capacity_mt * 13.8 * 10
                except (ValueError, TypeError):
                    try:
                        capacity_mcm_per_year = float(row.get('Full_capacity__100_MMCM_y_', 300))
                    except Exception:
                        capacity_mcm_per_year = row.get('capacity_mcm_per_year', None)
                        if capacity_mcm_per_year is None:
                            logger.warning(f"LNG接收站 {row.get('Name','未知')} 缺少容量数据，跳过")
                            continue

                lat = float(row.get('Lat'))
                lon = float(row.get('Long'))

                self.lng_terminals[terminal_id] = {
                    'name': row.get('Name', f'LNG接收站{idx+1}'),
                    'chinese_name': row.get('ChineseName', ''),
                    'location': row.get('Location', ''),
                    'capacity_mcm_per_year': capacity_mcm_per_year,
                    'operator': row.get('Operator', '未知'),
                    'status': row.get('Status', 'Operating'),
                    'year_online': row.get('YearOnline', 2020),
                    'cost_yuan_per_mcm': 200 + idx * 15,
                    'lat': lat,
                    'lon': lon,
                    'berths': row.get('Berths', ''),
                    'gas_type_source': row.get('Gas_type_source', ''),
                    'operational_status': row.get('Status', '运营中'),
                    'object_id': row.get('ObjectId', idx+1)
                }

            # 平均容量
            if self.lng_terminals:
                    capacity_values = [info['capacity_mcm_per_year'] for info in self.lng_terminals.values() if info.get('capacity_mcm_per_year')]
                    if capacity_values:
                        self.avg_lng_capacity_mcm_per_year = sum(capacity_values) / len(capacity_values)
                        logger.info(f"计算得出LNG接收站容量平均值: {self.avg_lng_capacity_mcm_per_year:.1f} 万立方米/年")
                    else:
                        logger.warning("未找到有效的LNG容量数据，使用默认值1000万立方米/年")
            else:
                logger.warning("未加载到任何LNG接收站数据，使用默认容量值1000万立方米/年")
        except Exception as e:
            logger.error(f"加载LNG接收站数据失败: {e}")
            raise
    
    def _define_technologies(self):
        """定义生产技术（使用模块化成本计算器）"""
        logger.info("定义生产技术（使用模块化成本计算）...")
        
        # 技术参数定义（完整版本，包含所有原版技术）
        tech_params = {
            'pipeline_direct_conversion': {
                'name': '管段直供转换',
                'capex_per_kg_h': 50000,  # 元/(kg/h)
                'fixed_opex_annual': 100000,  # 元/年
                'variable_opex_per_kg': 2.5,  # 元/kg
                'lifetime_years': 15,
                'suitable_locations': ['gas_field'],
                'hydrogen_transport_required': False
            },
            'airport_integrated_conversion': {
                'name': '机场综合转换',
                'capex_per_kg_h': 80000,
                'fixed_opex_annual': 150000,
                'variable_opex_per_kg': 3.0,
                'lifetime_years': 20,
                'suitable_locations': ['airport', 'solar_plant', 'wind_farm'],
                'hydrogen_transport_required': True
            },
            'lng_terminal_conversion': {
                'name': 'LNG接收站转换',
                'capex_per_kg_h': 70000,  # 元/(kg/h)
                'fixed_opex_annual': 120000,  # 元/年
                'variable_opex_per_kg': 2.8,  # 元/kg
                'lifetime_years': 18,
                'suitable_locations': ['lng_terminal'],
                'hydrogen_transport_required': True
            },
            'integrated_supply_conversion': {
                'name': '综合供应转换',
                'capex_per_kg_h': 90000,  # 元/(kg/h)
                'fixed_opex_annual': 180000,  # 元/年
                'variable_opex_per_kg': 3.5,  # 元/kg
                'lifetime_years': 20,
                'suitable_locations': ['industrial_park', 'port'],
                'hydrogen_transport_required': True
            }
        }
        
        self.technologies = {}
        
        # 使用成本计算器计算每个技术的平准化成本
        for tech_name, params in tech_params.items():
            # 计算设施成本（LCOE方法）
            facility_cost = self.cost_calculator.calculate_levelized_cost(
                capex=params['capex_per_kg_h'],  # 这里简化为单位容量成本
                opex_annual=params['fixed_opex_annual'],
                lifetime_years=params['lifetime_years'],
                capacity_factor=0.8
            )
            
            self.technologies[tech_name] = {
                **params,
                'facility_cost_yuan_per_kg_h': facility_cost,
                'production_cost_yuan_per_kg': params['variable_opex_per_kg']
            }
            
            # 添加到成本字典
            self.costs['technologies'][tech_name] = {
                'facility_cost_yuan_per_kg_h': facility_cost,
                'production_cost_yuan_per_kg': params['variable_opex_per_kg']
            }
        
        logger.info(f"定义了 {len(self.technologies)} 种生产技术")
    
    def _define_transport_locations(self):
        """定义运输相关的位置映射（保留原有逻辑）"""
        logger.info("定义运输位置映射...")
        
        # 氢气生产位置（可再生能源站点）
        self.hydrogen_locations = [
            loc for loc in self.locations 
            if self.locations[loc]['type'] in ['solar_plant', 'wind_farm']
        ]
        
        # 天然气来源位置
        self.ng_locations = list(self.ng_pipeline_sources.keys())
        
        logger.info(f"氢气生产地点: {len(self.hydrogen_locations)} 个")
        logger.info(f"天然气来源地点: {len(self.ng_locations)} 个")
    
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
            self.avg_hydrogen_transport_distance = 50  # 默认值
            logger.warning("无法计算氢气运输平均距离，使用默认值50km")
        
        # 计算天然气运输平均距离（管道到非LNG接收站）
        ng_distances = []
        ng_locations = list(self.ng_pipeline_sources.keys())[:5]  # 天然气源位置
        non_lng_mtj_locations = [loc for loc, info in self.locations.items() 
                               if info['type'] in ['industrial_park', 'port']]  # 不包括LNG接收站
        
        for ng_loc in ng_locations:
            for mtj_loc in non_lng_mtj_locations[:5]:
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
            self.avg_ng_transport_distance = 100  # 默认值
            logger.warning("无法计算天然气运输平均距离，使用默认值100km")
        
        # 计算机场运输平均距离（MTJ工厂到机场）
        airport_distances = []
        airport_locations = [loc for loc, info in self.locations.items() 
                           if info['type'] == 'airport']
        
        for mtj_loc in mtj_locations[:5]:
            for airport_loc in airport_locations[:5]:
                try:
                    distance = self._calculate_location_distance(mtj_loc, airport_loc)
                    airport_distances.append(distance)
                except Exception as e:
                    logger.warning(f"机场运输距离计算失败 {mtj_loc} -> {airport_loc}: {e}")
        
        if airport_distances:
            avg_airport_distance = np.mean(airport_distances)
            logger.info(f"机场运输平均距离: {avg_airport_distance:.1f}km "
                       f"(基于{len(airport_distances)}个样本)")
        
        logger.info("距离统计计算完成")
    
    def _calculate_location_distance(self, loc1: str, loc2: str) -> float:
        """计算两个位置间的距离（使用模块化地理计算器）"""
        try:
            lat1, lon1 = self._get_location_coordinates(loc1)
            lat2, lon2 = self._get_location_coordinates(loc2)
            
            # 使用GraphHopper距离计算器（如果可用）
            if self.distance_calculator:
                try:
                    return self.distance_calculator.get_distance(lat1, lon1, lat2, lon2)
                except:
                    pass
            
            # 否则使用模块化地理计算器
            return self.geographic_calculator.calculate_distance_km(lat1, lon1, lat2, lon2)
            
        except Exception as e:
            logger.error(f"距离计算失败 {loc1} -> {loc2}: {e}")
            return 0.0
    
    def _get_location_coordinates(self, location: str) -> tuple:
        """获取位置坐标"""
        # 首先检查locations
        if location in self.locations:
            return (self.locations[location]['latitude'], self.locations[location]['longitude'])
        
        # 检查机场
        if location in self.airports:
            return (self.airports[location]['latitude'], self.airports[location]['longitude'])
        
        # 检查天然气来源
        if location in self.ng_pipeline_sources:
            return (self.ng_pipeline_sources[location]['lat'], self.ng_pipeline_sources[location]['lon'])
        
        # 检查LNG接收站
        if location in self.lng_terminals:
            return (self.lng_terminals[location]['lat'], self.lng_terminals[location]['lon'])
        
        # 默认坐标
        logger.warning(f"未找到位置 {location} 的坐标，使用默认值")
        return (40.0, 116.0)
    
    def _process_excel_airport_data(self, excel_data: pd.DataFrame) -> pd.DataFrame:
        """处理Excel机场数据（保留原有逻辑）"""
        logger.info("处理Excel机场数据...")
        
        processed_data = []
        
        for _, row in excel_data.iterrows():
            # 提取机场名称
            airport_name = str(row.iloc[0]).strip() if not pd.isna(row.iloc[0]) else "未知机场"
            
            # 提取周需求数据
            weekly_demands = []
            for i in range(1, min(len(row), self.time_horizon_weeks + 1)):
                if not pd.isna(row.iloc[i]):
                    try:
                        demand = float(row.iloc[i])
                        weekly_demands.append(demand)
                    except:
                        weekly_demands.append(1000)  # 默认需求
                else:
                    weekly_demands.append(1000)
            
            # 确保有足够的周数据
            while len(weekly_demands) < self.time_horizon_weeks:
                weekly_demands.append(weekly_demands[-1] if weekly_demands else 1000)
            
            # 创建行数据
            row_data = {'airport': airport_name}
            for week in range(self.time_horizon_weeks):
                row_data[f'week_{week + 1}'] = weekly_demands[week]
            
            processed_data.append(row_data)
        
        result_df = pd.DataFrame(processed_data)
        logger.info(f"处理完成，包含 {len(result_df)} 个机场")
        
        return result_df
    
    def _load_real_renewable_data(self) -> pd.DataFrame:
        """加载真实的可再生能源数据（与原版一致）"""
        logger.info("加载真实的可再生能源数据...")

        base_dir = get_project_base_dir()
        wind_data_dir = os.path.join(base_dir, "products", "aviation_fuel_analysis", "resource_flight_data_process", "results", "3hourly_generation")
        solar_data_dir = os.path.join(base_dir, "products", "aviation_fuel_analysis", "resource_flight_data_process", "results", "solar_generation")

        if not os.path.exists(wind_data_dir):
            logger.error(f"风电数据目录不存在: {wind_data_dir}")
            raise FileNotFoundError(f"无法找到风电数据目录: {wind_data_dir}")
        if not os.path.exists(solar_data_dir):
            logger.error(f"光伏数据目录不存在: {solar_data_dir}")
            raise FileNotFoundError(f"无法找到光伏数据目录: {solar_data_dir}")

        wind_data = self._load_wind_data(wind_data_dir)
        solar_data = self._load_solar_data(solar_data_dir)
        renewable_data = pd.concat([wind_data, solar_data], ignore_index=True)
        logger.info(f"成功加载了 {len(renewable_data)} 条可再生能源数据记录")
        return renewable_data

    def _load_wind_data(self, wind_data_dir: str) -> pd.DataFrame:
        """加载风电数据（读取前若干文件并将3小时数据插值到小时）"""
        logger.info("正在加载风电数据...")
        wind_data_list = []
        wind_files = [f for f in os.listdir(wind_data_dir) if f.endswith('.csv')][:10]
        for file_name in wind_files:
            file_path = os.path.join(wind_data_dir, file_name)
            try:
                df = pd.read_csv(file_path)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df = df[df['timestamp'].dt.year == 2024]
                df = df[df['timestamp'] < '2024-01-15']
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

    def _interpolate_wind_to_hourly(self, wind_df: pd.DataFrame) -> pd.DataFrame:
        """将风电3小时数据插值到每小时（最近邻法：3小时值复制到每小时）"""
        hourly_data = []
        for _, row in wind_df.iterrows():
            timestamp = row['timestamp']
            generation_3h = row['generation_3h_mwh']
            hourly_generation = generation_3h
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
                        'power_output_mw': hourly_generation,
                        'hour': int(hour_from_start)
                    })
        return pd.DataFrame(hourly_data)

    def _load_solar_data(self, solar_data_dir: str) -> pd.DataFrame:
        """加载光伏数据（读取第一个月批次并取前total_hours小时）"""
        logger.info("正在加载光伏数据...")
        solar_data_list = []
        all_files = os.listdir(solar_data_dir)
        month01_files = [f for f in all_files if f.startswith('solar_generation_month01_batch_') and f.endswith('.csv')]
        month01_files.sort()
        logger.info(f"找到 {len(month01_files)} 个第一个月的批次文件")
        for file_name in month01_files:
            file_path = os.path.join(solar_data_dir, file_name)
            try:
                df = pd.read_csv(file_path)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                available_years = df['timestamp'].dt.year.unique()
                logger.info(f"文件 {file_name} 包含年份: {sorted(available_years)}")
                base_year = int(min(available_years))
                start_date = f"{base_year}-01-01"
                end_date = f"{base_year}-02-01"
                df_filtered = df[(df['timestamp'] >= start_date) & (df['timestamp'] < end_date)].copy()
                if len(df_filtered) == 0:
                    logger.warning(f"文件 {file_name} 在时间范围 {start_date} 到 {end_date} 内没有数据")
                    continue
                df_processed = df_filtered.copy()
                df_processed['plant_name'] = df_filtered['plant_name']
                df_processed['type'] = 'solar_plant'
                df_processed['generation_mwh'] = df_filtered['generation_1h_mwh']
                df_processed['power_output_mw'] = df_filtered['generation_1h_mwh']
                start_time = pd.to_datetime(f"{base_year}-01-01")
                df_processed['hour'] = (df_processed['timestamp'] - start_time).dt.total_seconds() // 3600
                df_processed['hour'] = df_processed['hour'].astype(int)
                df_processed = df_processed[df_processed['hour'] < self.total_hours]
                logger.info(f"文件 {file_name} 处理后得到 {len(df_processed)} 条记录")
                solar_data_list.append(df_processed)
            except Exception as e:
                logger.warning(f"读取光伏文件 {file_name} 失败: {e}")
        if solar_data_list:
            solar_data = pd.concat(solar_data_list, ignore_index=True)
            logger.info(f"成功加载 {len(solar_data)} 条光伏数据，来自 {len(month01_files)} 个批次文件")
        else:
            logger.warning("没有成功读取任何光伏数据")
            solar_data = pd.DataFrame()
        return solar_data


# 保持与原文件相同的接口
def main():
    """主执行函数 - 与原始版本完全一致的执行逻辑"""
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
        # 构建相对路径到机场数据文件
        airport_excel_path = os.path.join(str(base_dir), "products", "aviation_fuel_analysis", 
                                        "resource_flight_data_process", "results", "flights_beijing_tianjing",
                                        "all_airports_weekly_parameters_20250726_142747.xlsx")
        
        optimizer.load_data_from_excel(
            airport_excel_path=airport_excel_path
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
            results_dir = os.path.join(base_dir, "products", "supply_chain_optimization", 
                                     "natural_gas_supply_chain_optimization", "results")
            os.makedirs(results_dir, exist_ok=True)
            optimizer.save_results(solution, results_dir)
            print(f"\n结果已保存到目录: {results_dir}")
            print("="*50)
        else:
            logger.error("模型求解失败或未返回结果。")

    except Exception as e:
        logger.error(f"模型执行过程中发生严重错误: {e}", exc_info=True)


if __name__ == "__main__":
    main()