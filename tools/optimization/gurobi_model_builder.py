"""
Gurobi优化模型构建器
处理决策变量创建、约束条件添加和目标函数设置
"""

import gurobipy as gp
from gurobipy import GRB
import logging
from typing import Dict, Any, List, Tuple, Optional

logger = logging.getLogger(__name__)


class GurobiModelBuilder:
    """Gurobi优化模型构建器"""
    
    def __init__(self, time_horizon_weeks: int = 1):
        """
        初始化模型构建器
        
        Args:
            time_horizon_weeks: 优化时间范围(周数)
        """
        self.time_horizon_weeks = time_horizon_weeks
        self.hours_per_week = 168  # 7天 * 24小时
        self.total_hours = time_horizon_weeks * self.hours_per_week
        
        self.model = None
        self.production_vars = {}
        self.facility_vars = {}
        self.facility_capacity_vars = {}
        self.transport_vars = {}
        self.storage_vars = {}
        self.hydrogen_production_vars = {}
        self.electrolyzer_capacity_vars = {}
        self.electrolyzer_facility_vars = {}
        self.hydrogen_storage_vars = {}
        self.hydrogen_transport_vars = {}
        self.ng_transport_vars = {}
        self.shortage_vars = {}
    
    def build_model(self, locations: Dict, technologies: Dict, airports: Dict, 
                   mtj_locations: Dict = None, non_lng_mtj_locations: Dict = None,
                   hydrogen_locations: List = None, ng_locations: List = None) -> gp.Model:
        """
        构建优化模型
        
        Args:
            locations: 位置数据字典
            technologies: 技术数据字典  
            airports: 机场数据字典
            mtj_locations: MTJ工厂位置映射
            non_lng_mtj_locations: 非LNG接收站的MTJ工厂位置映射
            hydrogen_locations: 氢气生产位置列表
            ng_locations: 天然气来源位置列表
            
        Returns:
            gp.Model: 构建好的Gurobi模型
        """
        logger.info("构建Gurobi优化模型...")
        
        self.model = gp.Model("NaturalGasSupplyChain")
        self.model.setParam('TimeLimit', 3600)  # 1小时求解时间限制
        self.model.setParam('MIPGap', 0.01)     # 1% MIP gap
        self.model.setParam('Threads', 128)      # 使用128个核心进行并行计算
        
        # 存储数据引用
        self.locations = locations
        self.technologies = technologies
        self.airports = airports
        self.mtj_locations = mtj_locations or {}
        self.non_lng_mtj_locations = non_lng_mtj_locations or {}
        self.hydrogen_locations = hydrogen_locations or []
        self.ng_locations = ng_locations or []
        
        # 创建决策变量
        self._create_variables()
        
        logger.info("模型构建完成")
        return self.model
    
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
                    lb=0, ub=10000, vtype=GRB.CONTINUOUS, name=var_name  # 最大10吨/小时产能
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
        self.hydrogen_transport_vars = {}  # 氢气运输量 (kg H2/day)
        
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
                    lb=0, ub=2000, vtype=GRB.CONTINUOUS, name=var_name  # 最大2吨H2/小时（更合理规模）
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
        self._create_hydrogen_transport_vars()
        
        # 9. 创建天然气运输变量 (从管道到所有非LNG接收站的MTJ工厂，改为天级罐车运输，无距离限制)
        self._create_ng_transport_vars()
        
        # 10. 创建缺货惩罚变量 (周级需求缺口)
        self.shortage_vars = {}
        for airport in self.airports:
            for week in range(self.time_horizon_weeks):
                var_name = f"shortage_{airport}_{week}"
                self.shortage_vars[(airport, week)] = self.model.addVar(
                    lb=0, ub=GRB.INFINITY, vtype=GRB.CONTINUOUS, name=var_name
                )
        
        self._log_variable_counts()
    
    def _create_hydrogen_transport_vars(self):
        """创建氢气运输变量"""
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
                    # 修改为天级运输变量，每天24小时聚合
                    total_days = self.total_hours // 24
                    for day in range(total_days):
                        var_name = f"h2_transport_{h2_loc}_{mtj_loc}_day_{day}"
                        self.hydrogen_transport_vars[(h2_loc, mtj_loc, day)] = self.model.addVar(
                            lb=0, ub=GRB.INFINITY, vtype=GRB.CONTINUOUS, name=var_name
                            )
        
        logger.info(f"创建了 {valid_h2_routes} 条氢气运输路线（无距离限制）")
    
    def _create_ng_transport_vars(self):
        """创建天然气运输变量"""
        logger.info("创建天然气罐车运输变量，无距离限制")
        
        valid_ng_routes = 0  # 计数有效路线
        total_days = self.total_hours // 24
        for ng_loc in self.ng_locations:
            for tech in ['pipeline_direct_conversion', 'airport_integrated_conversion', 'lng_to_hplant_conversion', 'integrated_supply_conversion']:
                if tech not in self.non_lng_mtj_locations:
                    continue
                for mtj_loc in self.non_lng_mtj_locations[tech]:
                    # 不再检查距离限制，允许所有路径
                    valid_ng_routes += 1
                    for day in range(total_days): # 改为天级
                        var_name = f"ng_transport_{ng_loc}_{mtj_loc}_day_{day}"
                        self.ng_transport_vars[(ng_loc, mtj_loc, day)] = self.model.addVar(
                                lb=0, ub=GRB.INFINITY, vtype=GRB.CONTINUOUS, name=var_name
                            )
        
        logger.info(f"创建了 {valid_ng_routes} 条天然气运输路线（无距离限制）")
    
    def _log_variable_counts(self):
        """记录变量数量统计"""
        logger.info(f"创建了 {len(self.production_vars)} 个生产变量")
        logger.info(f"创建了 {len(self.facility_vars)} 个设施变量")
        logger.info(f"创建了 {len(self.facility_capacity_vars)} 个设施产能变量")
        logger.info(f"创建了 {len(self.transport_vars)} 个运输变量")
        logger.info(f"创建了 {len(self.storage_vars)} 个库存变量")
        logger.info(f"创建了 {len(self.hydrogen_production_vars)} 个制氢变量")
        logger.info(f"创建了 {len(self.electrolyzer_capacity_vars)} 个电解槽容量变量")
        logger.info(f"创建了 {len(self.hydrogen_storage_vars)} 个氢气库存变量")
        logger.info(f"创建了 {len(self.shortage_vars)} 个缺货惩罚变量")
        logger.info(f"创建了 {len(self.hydrogen_transport_vars)} 个氢气运输变量")
        logger.info(f"创建了 {len(self.ng_transport_vars)} 个天然气运输变量")
    
    def get_variables(self) -> Dict[str, Dict]:
        """
        获取所有决策变量
        
        Returns:
            Dict: 包含所有变量类型的字典
        """
        return {
            'production_vars': self.production_vars,
            'facility_vars': self.facility_vars,
            'facility_capacity_vars': self.facility_capacity_vars,
            'transport_vars': self.transport_vars,
            'storage_vars': self.storage_vars,
            'hydrogen_production_vars': self.hydrogen_production_vars,
            'electrolyzer_capacity_vars': self.electrolyzer_capacity_vars,
            'electrolyzer_facility_vars': self.electrolyzer_facility_vars,
            'hydrogen_storage_vars': self.hydrogen_storage_vars,
            'hydrogen_transport_vars': self.hydrogen_transport_vars,
            'ng_transport_vars': self.ng_transport_vars,
            'shortage_vars': self.shortage_vars
        }


class GurobiConstraintBuilder:
    """Gurobi约束条件构建器"""
    
    def __init__(self, model: gp.Model, variables: Dict, 
                 locations: Dict, technologies: Dict, airports: Dict,
                 time_horizon_weeks: int = 1):
        """
        初始化约束构建器
        
        Args:
            model: Gurobi模型实例
            variables: 决策变量字典
            locations: 位置数据字典
            technologies: 技术数据字典
            airports: 机场数据字典
            time_horizon_weeks: 优化时间范围(周数)
        """
        self.model = model
        self.variables = variables
        self.locations = locations
        self.technologies = technologies
        self.airports = airports
        self.time_horizon_weeks = time_horizon_weeks
        self.hours_per_week = 168
        self.total_hours = time_horizon_weeks * self.hours_per_week
    
    def create_constraints(self, mtj_locations: Dict = None, 
                          non_lng_mtj_locations: Dict = None,
                          hydrogen_locations: List = None, 
                          ng_locations: List = None,
                          distance_calculator=None):
        """
        创建约束条件
        
        Args:
            mtj_locations: MTJ工厂位置映射
            non_lng_mtj_locations: 非LNG接收站的MTJ工厂位置映射  
            hydrogen_locations: 氢气生产位置列表
            ng_locations: 天然气来源位置列表
            distance_calculator: 距离计算器
        """
        logger.info("创建约束条件...")
        
        # 存储额外数据
        self.mtj_locations = mtj_locations or {}
        self.non_lng_mtj_locations = non_lng_mtj_locations or {}
        self.hydrogen_locations = hydrogen_locations or []
        self.ng_locations = ng_locations or []
        self.distance_calculator = distance_calculator
        
        # 1. 时间尺度匹配约束
        self._add_time_scale_matching_constraints()
        
        # 2. 生产能力约束
        self._add_production_capacity_constraints()
        
        # 3. 原料供应约束
        self._add_material_supply_constraints()
        
        # 4. 库存平衡约束
        self._add_inventory_balance_constraints()
        
        # 5. 机场需求约束（软约束：允许缺货但有惩罚）
        self._add_airport_demand_constraints()

        # 6. 设施建设约束
        self._add_facility_construction_constraints()
        
        logger.info("约束条件创建完成")
    
    def _add_time_scale_matching_constraints(self):
        """添加时间尺度匹配约束（小时级生产 -> 周级运输）"""
        logger.info("添加时间尺度匹配约束...")
        
        production_vars = self.variables['production_vars']
        transport_vars = self.variables['transport_vars']
        storage_vars = self.variables['storage_vars']
        
        constraint_count = 0
        for location in self.locations:
            for week in range(self.time_horizon_weeks):
                # 计算该周的小时范围
                start_hour = week * self.hours_per_week
                end_hour = (week + 1) * self.hours_per_week
                
                # 该周总生产量
                weekly_production = gp.quicksum(
                    production_vars[(location, tech, hour)]
                    for tech in self.technologies
                    for hour in range(start_hour, end_hour)
                    if (location, tech, hour) in production_vars
                )
                
                # 该周总运输量
                weekly_transport = gp.quicksum(
                    transport_vars[(location, airport, week)]
                    for airport in self.airports
                    if (location, airport, week) in transport_vars
                )
                
                # 库存变化 = 周末库存 - 周初库存
                initial_inventory = storage_vars[(location, start_hour)] if (location, start_hour) in storage_vars else 0
                final_inventory = storage_vars[(location, end_hour)] if (location, end_hour) in storage_vars else 0
                inventory_change = final_inventory - initial_inventory
                
                # 平衡约束：生产 = 运输 + 库存变化
                constraint_name = f"time_scale_match_{location}_{week}"
                self.model.addConstr(
                    weekly_production == weekly_transport + inventory_change,
                    name=constraint_name
                )
                constraint_count += 1
        
        logger.info(f"添加了 {constraint_count} 个时间尺度匹配约束")
    
    def _add_production_capacity_constraints(self):
        """添加生产能力约束"""
        logger.info("添加生产能力约束...")
        
        production_vars = self.variables['production_vars']
        facility_capacity_vars = self.variables['facility_capacity_vars']
        
        constraint_count = 0
        for location in self.locations:
            for tech in self.technologies:
                for hour in range(self.total_hours):
                    if (location, tech, hour) in production_vars and (location, tech) in facility_capacity_vars:
                        constraint_name = f"capacity_{location}_{tech}_{hour}"
                        self.model.addConstr(
                            production_vars[(location, tech, hour)] <= facility_capacity_vars[(location, tech)],
                            name=constraint_name
                        )
                        constraint_count += 1
        
        logger.info(f"添加了 {constraint_count} 个生产能力约束")
    
    def _add_material_supply_constraints(self):
        """添加原料供应约束"""
        logger.info("添加原料供应约束...")
        
        constraint_count = 0
        for location in self.locations:
            for hour in range(self.total_hours):
                # 可再生能源约束
                if location in self.locations:
                    location_type = self.locations[location]['type']
                    if location_type in ['solar_plant', 'wind_farm']:
                        self._add_renewable_power_constraints(location, hour)
                        constraint_count += 1
                
                # 天然气管段约束
                if location in self.ng_locations:
                    self._add_ng_pipeline_flow_constraints(location, hour)
                    constraint_count += 1
        
        logger.info(f"添加了约 {constraint_count} 个原料供应约束")
    
    def _add_renewable_power_constraints(self, location: str, hour: int):
        """添加可再生能源功率约束"""
        if location not in self.locations:
            return
            
        location_info = self.locations[location]
        if 'hourly_generation' not in location_info or hour >= len(location_info['hourly_generation']):
            return
            
        available_power = location_info['hourly_generation'][hour]  # MW
        
        # 所有消耗电力的生产过程
        power_consuming_production = gp.quicksum(
            self.variables['production_vars'][(location, tech, hour)] * 
            self.technologies[tech].get('electricity_consumption_mwh_per_kg', 0)
            for tech in self.technologies
            if (location, tech, hour) in self.variables['production_vars']
        )
        
        # 制氢消耗的电力
        electrolyzer_power = 0
        if (location, hour) in self.variables['hydrogen_production_vars']:
            # 假设电解槽电耗为50 MWh/吨H2 = 0.05 MWh/kg H2
            electrolyzer_power = self.variables['hydrogen_production_vars'][(location, hour)] * 0.05
        
        # 电力平衡约束
        constraint_name = f"renewable_power_{location}_{hour}"
        self.model.addConstr(
            power_consuming_production + electrolyzer_power <= available_power,
            name=constraint_name
        )
    
    def _add_ng_pipeline_flow_constraints(self, location: str, hour: int):
        """添加天然气管段流量约束"""
        # 简化实现：假设每个天然气来源有无限供应
        # 在实际应用中，这里应该根据管道容量和流量数据设置约束
        pass
    
    def _add_inventory_balance_constraints(self):
        """添加库存平衡约束"""
        logger.info("添加库存平衡约束...")
        
        storage_vars = self.variables['storage_vars']
        production_vars = self.variables['production_vars']
        transport_vars = self.variables['transport_vars']
        
        constraint_count = 0
        for location in self.locations:
            for hour in range(1, self.total_hours + 1):
                if (location, hour) in storage_vars and (location, hour-1) in storage_vars:
                    # 计算该小时的生产量
                    hourly_production = gp.quicksum(
                        production_vars[(location, tech, hour-1)]
                        for tech in self.technologies
                        if (location, tech, hour-1) in production_vars
                    )
                    
                    # 计算该小时的运输量（需要从周级分摊到小时级）
                    week = (hour-1) // self.hours_per_week
                    hourly_transport = gp.quicksum(
                        transport_vars[(location, airport, week)] / self.hours_per_week
                        for airport in self.airports
                        if (location, airport, week) in transport_vars and week < self.time_horizon_weeks
                    )
                    
                    # 库存平衡：当前库存 = 上一小时库存 + 生产 - 运输
                    constraint_name = f"inventory_balance_{location}_{hour}"
                    self.model.addConstr(
                        storage_vars[(location, hour)] == 
                        storage_vars[(location, hour-1)] + hourly_production - hourly_transport,
                        name=constraint_name
                    )
                    constraint_count += 1
        
        logger.info(f"添加了 {constraint_count} 个库存平衡约束")
    
    def _add_airport_demand_constraints(self):
        """添加机场周需求约束：Σ(各地点→该机场的周运输量) + 缺货 ≥ 该机场该周需求"""
        logger.info("添加机场需求约束...")
        transport_vars = self.variables['transport_vars']
        shortage_vars = self.variables.get('shortage_vars', {})

        constraint_count = 0
        for airport, info in self.airports.items():
            # 兼容不同字段命名
            weekly_series = (
                info.get('weekly_demand_series')
                or info.get('weekly_fuel_series')
                or info.get('weekly_fuel_demand')
            )
            if not isinstance(weekly_series, list):
                # 无有效需求序列则跳过
                continue

            for week in range(self.time_horizon_weeks):
                weekly_demand = weekly_series[week] if week < len(weekly_series) else 0.0

                total_supply = gp.quicksum(
                    transport_vars[(location, airport, week)]
                    for location in self.locations
                    if (location, airport, week) in transport_vars
                )

                if (airport, week) in shortage_vars:
                    constr_name = f"demand_{airport}_{week}"
                    self.model.addConstr(
                        total_supply + shortage_vars[(airport, week)] >= weekly_demand,
                        name=constr_name
                    )
                    constraint_count += 1

        logger.info(f"添加了 {constraint_count} 个机场需求约束")

    def _add_facility_construction_constraints(self):
        """添加设施建设约束"""
        logger.info("添加设施建设约束...")
        
        facility_vars = self.variables['facility_vars']
        facility_capacity_vars = self.variables['facility_capacity_vars']
        
        constraint_count = 0
        for location in self.locations:
            for tech in self.technologies:
                if (location, tech) in facility_vars and (location, tech) in facility_capacity_vars:
                    # 大M约束：容量只有在建设设施时才能大于0
                    M = 10000  # 足够大的数
                    constraint_name = f"facility_construct_{location}_{tech}"
                    self.model.addConstr(
                        facility_capacity_vars[(location, tech)] <= M * facility_vars[(location, tech)],
                        name=constraint_name
                    )
                    constraint_count += 1
        
        logger.info(f"添加了 {constraint_count} 个设施建设约束")


class GurobiObjectiveBuilder:
    """Gurobi目标函数构建器"""
    
    def __init__(self, model: gp.Model, variables: Dict, costs: Dict,
                 locations: Dict, technologies: Dict, airports: Dict):
        """
        初始化目标函数构建器
        
        Args:
            model: Gurobi模型实例
            variables: 决策变量字典
            costs: 成本数据字典
            locations: 位置数据字典
            technologies: 技术数据字典
            airports: 机场数据字典
        """
        self.model = model
        self.variables = variables
        self.costs = costs
        self.locations = locations
        self.technologies = technologies
        self.airports = airports
    
    def create_objective(self, distance_calculator=None):
        """
        创建目标函数：最小化总成本
        
        Args:
            distance_calculator: 距离计算器
        """
        logger.info("创建目标函数...")
        
        self.distance_calculator = distance_calculator
        
        # 1. 设施建设成本
        facility_cost = self._calculate_facility_cost()
        
        # 2. 生产成本  
        production_cost = self._calculate_production_cost()
        
        # 3. 运输成本
        transport_cost = self._calculate_transport_cost()
        
        # 4. 缺货惩罚成本
        shortage_penalty = self._calculate_shortage_penalty()
        
        # 设置目标函数
        total_cost = facility_cost + production_cost + transport_cost + shortage_penalty
        self.model.setObjective(total_cost, GRB.MINIMIZE)
        
        logger.info("目标函数创建完成")
    
    def _calculate_facility_cost(self) -> gp.LinExpr:
        """计算设施建设成本"""
        facility_vars = self.variables['facility_vars']
        facility_capacity_vars = self.variables['facility_capacity_vars']
        
        facility_cost = gp.LinExpr()
        
        for location in self.locations:
            for tech in self.technologies:
                if (location, tech) in facility_capacity_vars:
                    # 使用平准化固定成本
                    tech_costs = self.costs.get('technologies', {}).get(tech, {})
                    if 'facility_cost_yuan_per_kg_h' in tech_costs:
                        cost_per_unit = tech_costs['facility_cost_yuan_per_kg_h']
                        facility_cost += facility_capacity_vars[(location, tech)] * cost_per_unit
        
        return facility_cost
    
    def _calculate_production_cost(self) -> gp.LinExpr:
        """计算生产成本"""
        production_vars = self.variables['production_vars']
        
        production_cost = gp.LinExpr()
        
        for (location, tech, hour), var in production_vars.items():
            tech_costs = self.costs.get('technologies', {}).get(tech, {})
            if 'production_cost_yuan_per_kg' in tech_costs:
                cost_per_kg = tech_costs['production_cost_yuan_per_kg']
                production_cost += var * cost_per_kg
        
        return production_cost
    
    def _calculate_transport_cost(self) -> gp.LinExpr:
        """计算运输成本"""
        transport_vars = self.variables['transport_vars']
        
        transport_cost = gp.LinExpr()
        transport_cost_per_km_per_kg = self.costs.get('transport_cost_yuan_per_km_per_kg', 0.05)
        
        for (location, airport, week), var in transport_vars.items():
            # 计算距离
            if self.distance_calculator and location in self.locations and airport in self.airports:
                try:
                    distance_km = self.distance_calculator.get_distance(
                        self.locations[location]['latitude'],
                        self.locations[location]['longitude'],
                        self.airports[airport]['latitude'],
                        self.airports[airport]['longitude']
                    )
                except:
                    distance_km = 100  # 默认距离
            else:
                distance_km = 100  # 默认距离
            
            cost = distance_km * transport_cost_per_km_per_kg
            transport_cost += var * cost
        
        return transport_cost
    
    def _calculate_shortage_penalty(self) -> gp.LinExpr:
        """计算缺货惩罚成本"""
        shortage_vars = self.variables['shortage_vars']
        
        shortage_penalty = gp.LinExpr()
        penalty_cost = self.costs.get('shortage_penalty_yuan_per_kg', 10000)  # 高惩罚成本
        
        for var in shortage_vars.values():
            shortage_penalty += var * penalty_cost
        
        return shortage_penalty