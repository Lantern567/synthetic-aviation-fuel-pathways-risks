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
        self.cost_calculator = CostCalculator()
        self.economic_params = EconomicParametersManager.define_default_economic_parameters()
        
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
        
        # 使用模块化可再生能源数据处理器
        try:
            # 导入缓存管理器（如果可用）
            try:
                from .data_cache_manager import cache_manager
            except ImportError:
                cache_manager = None
                
            # 处理可再生能源数据
            processed_locations = self.renewable_data_processor.process_renewable_data(
                renewable_data=renewable_data,
                geographic_calculator=self.geographic_calculator,
                cache_manager=cache_manager
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
            
        except Exception as e:
            logger.error(f"模块化数据处理失败，回退到原有方法: {e}")
            self._process_renewable_data_fallback(renewable_data)
        
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
        
        # 读取Excel数据
        try:
            excel_data = pd.read_excel(airport_excel_path)
            logger.info(f"Excel文件读取成功，包含 {len(excel_data)} 行数据")
        except Exception as e:
            logger.error(f"读取Excel文件失败: {e}")
            raise
        
        # 处理机场数据
        airport_data = self._process_excel_airport_data(excel_data)
        
        # 如果没有提供可再生能源数据，必须加载真实数据
        if renewable_data is None:
            renewable_data = self._load_real_renewable_data()
        
        # 使用统一的load_data方法
        self.load_data(renewable_data, airport_data)
    
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
            airports=self.airports
        )
        
        self.objective_builder.create_objective(distance_calculator=self.distance_calculator)
        
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
        """处理机场数据（保留原有业务逻辑）"""
        logger.info("处理机场需求数据...")
        
        self.airports = {}
        for _, row in airport_data.iterrows():
            airport_name = row['airport']
            
            # 获取机场坐标
            airport_coords = self._get_airport_coordinates(airport_name)
            
            # 处理周级需求数据
            weekly_demand = []
            for week in range(self.time_horizon_weeks):
                week_col = f'week_{week + 1}'
                if week_col in row:
                    weekly_demand.append(float(row[week_col]))
                else:
                    # 如果没有足够的周数据，使用最后一个可用值
                    if weekly_demand:
                        weekly_demand.append(weekly_demand[-1])
                    else:
                        weekly_demand.append(1000)  # 默认需求
            
            self.airports[airport_name] = {
                'latitude': airport_coords['lat'],
                'longitude': airport_coords['lon'],
                'weekly_fuel_demand': weekly_demand,
                'weekly_fuel_series': weekly_demand
            }
        
        logger.info(f"处理了 {len(self.airports)} 个机场的需求数据")
    
    def _get_airport_coordinates(self, airport_name: str) -> dict:
        """获取机场坐标（保留原有逻辑但可能使用地理计算器验证）"""
        # 机场坐标数据库（简化版本）
        airport_coords = {
            '北京首都国际机场': {'lat': 40.0799, 'lon': 116.6031},
            '上海浦东国际机场': {'lat': 31.1443, 'lon': 121.8083},
            '广州白云国际机场': {'lat': 23.1924, 'lon': 113.3010},
            '深圳宝安国际机场': {'lat': 22.6393, 'lon': 113.8107},
            # 可以添加更多机场
        }
        
        if airport_name in airport_coords:
            coords = airport_coords[airport_name]
            # 使用地理计算器验证坐标有效性
            if self.geographic_calculator.validate_coordinates(coords['lat'], coords['lon']):
                return coords
        
        # 默认坐标（北京）
        logger.warning(f"未找到机场 {airport_name} 的坐标，使用默认坐标")
        return {'lat': 40.0, 'lon': 116.0}
    
    def _load_ng_pipeline_data(self):
        """加载天然气管段数据（保留原有逻辑）"""
        logger.info("加载天然气管段数据...")
        
        # 简化的天然气管段数据
        self.ng_pipeline_sources = {
            'shaanxi_gas_field': {
                'name': '陕西气田',
                'lat': 37.5, 'lon': 109.0,
                'capacity_mcm_per_year': 5000,
                'type': 'gas_field'
            },
            'xinjiang_gas_field': {
                'name': '新疆气田', 
                'lat': 43.8, 'lon': 87.6,
                'capacity_mcm_per_year': 8000,
                'type': 'gas_field'
            }
        }
        
        logger.info(f"加载了 {len(self.ng_pipeline_sources)} 个天然气来源")
    
    def _load_lng_terminal_data(self):
        """加载LNG接收站数据（保留原有逻辑）"""
        logger.info("加载LNG接收站数据...")
        
        # 简化的LNG接收站数据
        self.lng_terminals = {
            'dalian_lng': {
                'name': '大连LNG接收站',
                'lat': 38.9, 'lon': 121.6,
                'capacity_mcm_per_year': 1000,
                'type': 'lng_terminal'
            },
            'shanghai_lng': {
                'name': '上海LNG接收站',
                'lat': 31.2, 'lon': 121.5, 
                'capacity_mcm_per_year': 1500,
                'type': 'lng_terminal'
            }
        }
        
        # 计算平均LNG容量
        if self.lng_terminals:
            total_capacity = sum(terminal['capacity_mcm_per_year'] for terminal in self.lng_terminals.values())
            self.avg_lng_capacity_mcm_per_year = total_capacity / len(self.lng_terminals)
        
        logger.info(f"加载了 {len(self.lng_terminals)} 个LNG接收站")
    
    def _define_technologies(self):
        """定义生产技术（使用模块化成本计算器）"""
        logger.info("定义生产技术（使用模块化成本计算）...")
        
        # 技术参数定义（简化版本）
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
        """加载真实可再生能源数据（简化版本）"""
        logger.info("创建示例可再生能源数据...")
        
        # 创建示例数据
        data = []
        
        # 添加一些太阳能电站
        solar_plants = [
            {'name': '北京太阳能电站1', 'lat': 40.2, 'lon': 116.5, 'capacity': 100},
            {'name': '天津太阳能电站1', 'lat': 39.1, 'lon': 117.2, 'capacity': 150},
        ]
        
        # 添加一些风电场
        wind_farms = [
            {'name': '河北风电场1', 'lat': 39.8, 'lon': 115.5, 'capacity': 200},
            {'name': '内蒙古风电场1', 'lat': 40.8, 'lon': 115.0, 'capacity': 250},
        ]
        
        # 生成小时级数据
        for hour in range(self.total_hours):
            # 太阳能数据（白天高，晚上低）
            for plant in solar_plants:
                solar_factor = max(0, np.sin(np.pi * (hour % 24) / 24)) if 6 <= hour % 24 <= 18 else 0
                power_output = plant['capacity'] * solar_factor * (0.8 + 0.4 * np.random.random())
                
                data.append({
                    'plant_name': plant['name'],
                    'type': 'solar_plant',
                    'latitude': plant['lat'],
                    'longitude': plant['lon'],
                    'capacity_mw': plant['capacity'],
                    'power_output_mw': power_output,
                    'hour': hour
                })
            
            # 风电数据（相对稳定）
            for farm in wind_farms:
                wind_factor = 0.6 + 0.4 * np.random.random()  # 60-100%的随机输出
                power_output = farm['capacity'] * wind_factor
                
                data.append({
                    'plant_name': farm['name'],
                    'type': 'wind_farm', 
                    'latitude': farm['lat'],
                    'longitude': farm['lon'],
                    'capacity_mw': farm['capacity'],
                    'power_output_mw': power_output,
                    'hour': hour
                })
        
        df = pd.DataFrame(data)
        logger.info(f"创建了 {len(df)} 条示例可再生能源数据记录")
        
        return df


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
                                        "resource_flight_data_process", "data", 
                                        "capital_binhai_airports_data_20250726_123415.xlsx")
        
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