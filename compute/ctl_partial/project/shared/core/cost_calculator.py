"""
成本计算工具类
提供平准化成本计算(LCOE/LCOP)和经济参数定义功能
"""

import numpy as np
import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class CostCalculator:
    """成本计算工具类"""
    
    def __init__(self, discount_rate: float = 0.05, project_lifespan: int = 20):
        """
        初始化成本计算器
        
        Args:
            discount_rate: 贴现率，默认5%
            project_lifespan: 项目生命周期，默认20年
        """
        self.discount_rate = discount_rate
        self.project_lifespan = project_lifespan
    
    def calculate_levelized_cost(self, capex: float, opex_annual: float, lifetime_years: int, 
                               discount_rate: Optional[float] = None, capacity_factor: float = 1.0) -> float:
        """
        计算平准化成本 (LCOE - Levelized Cost of Energy)
        
        Args:
            capex: 初始资本支出 (元)
            opex_annual: 年运营成本 (元/年)
            lifetime_years: 设备使用寿命 (年)
            discount_rate: 贴现率 (年化)，如果为None则使用实例默认值
            capacity_factor: 容量因子 (设备利用率)
            
        Returns:
            年化平准化成本 (元/年)
        """
        dr = discount_rate if discount_rate is not None else self.discount_rate
        
        # 计算资本回收因子 (Capital Recovery Factor)
        if dr == 0:
            crf = 1.0 / lifetime_years
        else:
            crf = (dr * (1 + dr)**lifetime_years) / ((1 + dr)**lifetime_years - 1)
        
        # 年化资本成本
        annual_capex = capex * crf
        
        # 考虑容量因子的年化平准化成本
        annual_total_cost = annual_capex + opex_annual
        
        return annual_total_cost / capacity_factor
    
    def calculate_levelized_product_cost(self, capex_per_unit: float, fixed_opex_annual: float, 
                                       variable_opex_per_product: float, lifetime_years: int, 
                                       discount_rate: Optional[float] = None, capacity_factor: float = 1.0) -> float:
        """
        修正的平准化产品成本计算 (LCOP - Levelized Cost of Product)
        
        Args:
            capex_per_unit: 初始资本支出，每单位产能 (元/单位产能)
            fixed_opex_annual: 年固定运营成本 (元/年)
            variable_opex_per_product: 单位产品变动运营成本 (元/产品)
            lifetime_years: 设备使用寿命 (年)
            discount_rate: 贴现率 (年化)，如果为None则使用实例默认值
            capacity_factor: 容量因子 (设备利用率)
            
        Returns:
            平准化产品成本 (元/产品)
        """
        dr = discount_rate if discount_rate is not None else self.discount_rate
        
        # 计算资本回收因子 (Capital Recovery Factor)
        if dr == 0:
            crf = 1.0 / lifetime_years
        else:
            crf = (dr * (1 + dr)**lifetime_years) / ((1 + dr)**lifetime_years - 1)
        
        # 年化资本成本
        annual_capex = capex_per_unit * crf
        
        # 年实际产量 (假设设计产能为1单位/小时)
        annual_production = 1.0 * 8760 * capacity_factor  # 产品/年
        
        # 单位产品固定成本 = (年化CAPEX + 年固定OPEX) / 年实际产量
        fixed_cost_per_product = (annual_capex + fixed_opex_annual) / annual_production
        
        # 平准化产品成本 = 单位固定成本 + 单位变动成本
        lcop = fixed_cost_per_product + variable_opex_per_product
        
        return lcop
    
    def calculate_project_levelized_cost_with_replacement(self, capex: float, opex_annual: float, 
                                                        equipment_lifetime: int, 
                                                        project_lifespan: Optional[int] = None,
                                                        discount_rate: Optional[float] = None, 
                                                        capacity_factor: float = 1.0) -> float:
        """
        计算考虑设备更换的项目期间平准化成本
        
        Args:
            capex: 初始资本支出 (元)
            opex_annual: 年运营成本 (元/年)
            equipment_lifetime: 设备使用寿命 (年)
            project_lifespan: 项目总寿命 (年)，如果为None则使用实例默认值
            discount_rate: 贴现率 (年化)，如果为None则使用实例默认值
            capacity_factor: 容量因子 (设备利用率)
            
        Returns:
            项目期间年化平准化成本 (元/年)
        """
        pl = project_lifespan if project_lifespan is not None else self.project_lifespan
        dr = discount_rate if discount_rate is not None else self.discount_rate
        
        # 计算项目期间内需要的设备更换次数
        replacement_times = []
        current_year = equipment_lifetime
        while current_year < pl:
            replacement_times.append(current_year)
            current_year += equipment_lifetime
        
        # 计算所有CAPEX的净现值(包括初始投资和更换投资)
        total_capex_npv = capex  # 初始投资
        
        # 添加每次更换的折现成本
        for replacement_year in replacement_times:
            replacement_capex_npv = capex / ((1 + dr) ** replacement_year)
            total_capex_npv += replacement_capex_npv
        
        # 计算运营成本的净现值
        if dr == 0:
            opex_npv = opex_annual * pl
        else:
            opex_npv = opex_annual * (1 - (1 + dr)**(-pl)) / dr
        
        # 计算项目期间总净现值
        total_project_npv = total_capex_npv + opex_npv
        
        # 计算项目期间资本回收因子
        if dr == 0:
            project_crf = 1.0 / pl
        else:
            project_crf = (dr * (1 + dr)**pl) / ((1 + dr)**pl - 1)
        
        # 年化成本
        annual_cost = total_project_npv * project_crf
        
        return annual_cost / capacity_factor
    
    def calculate_lifecycle_production_from_optimization(self, production_vars: Dict, 
                                                       time_horizon_weeks: int,
                                                       project_lifespan: Optional[int] = None) -> Dict[str, float]:
        """
        基于优化结果计算全生命周期实际产量
        这个方法在求解后调用，使用实际的production_vars值
        
        Args:
            production_vars: 生产决策变量字典
            time_horizon_weeks: 优化时间范围（周）
            project_lifespan: 项目生命周期（年），如果为None则使用实例默认值
            
        Returns:
            dict: 包含各设施全生命周期产量的字典
        """
        pl = project_lifespan if project_lifespan is not None else self.project_lifespan
        lifecycle_production = {}
        
        # 累计优化期间的实际产量
        for key in production_vars:
            location, tech, hour = key
            facility_key = (location, tech)
            
            if facility_key not in lifecycle_production:
                lifecycle_production[facility_key] = 0
            
            # 获取实际优化结果的产量值
            actual_production = production_vars[key].x if hasattr(production_vars[key], 'x') else 0
            lifecycle_production[facility_key] += actual_production
        
        # 基于优化时间范围推算全生命周期
        if time_horizon_weeks == 1:
            # 基于1周数据推算20年（假设每周产量模式重复）
            weeks_in_lifecycle = 52 * pl  # 例如：1040周
            for facility_key in lifecycle_production:
                lifecycle_production[facility_key] *= weeks_in_lifecycle
                
        elif time_horizon_weeks >= 52:
            # 基于年度数据推算20年
            years_in_optimization = time_horizon_weeks / 52
            years_in_lifecycle = pl
            scaling_factor = years_in_lifecycle / years_in_optimization
            for facility_key in lifecycle_production:
                lifecycle_production[facility_key] *= scaling_factor
        
        else:
            # 基于多周数据推算20年
            weeks_per_year = 52
            years_in_lifecycle = pl
            # 先年化，再乘以生命周期年数
            annual_scaling = weeks_per_year / time_horizon_weeks
            for facility_key in lifecycle_production:
                lifecycle_production[facility_key] *= annual_scaling * years_in_lifecycle
        
        return lifecycle_production
    
    def estimate_lifecycle_production_for_lcoe(self, facility_capacity: float, time_horizon_weeks: int,
                                             project_lifespan: Optional[int] = None) -> float:
        """
        为LCOE计算估算生命周期产量
        这个方法在优化前使用，基于设施容量和预期利用率估算
        
        Args:
            facility_capacity: 设施容量 (kg/h)
            time_horizon_weeks: 优化时间范围（周）
            project_lifespan: 项目生命周期（年），如果为None则使用实例默认值
            
        Returns:
            float: 估算的生命周期产量 (kg)
        """
        pl = project_lifespan if project_lifespan is not None else self.project_lifespan
        
        # 估算年度产量（不再假设满负荷运行）
        # 基于历史数据或经验估算实际利用率
        if time_horizon_weeks == 1:
            # 基于1周优化估算：假设设施平均利用率为60%（考虑原材料约束等）
            estimated_utilization_rate = 0.60
        else:
            # 基于更长期优化：利用率可能更高
            estimated_utilization_rate = 0.75
        
        # 年产量 = 设施容量 × 年度小时数 × 实际利用率
        annual_hours = 8760
        annual_production = facility_capacity * annual_hours * estimated_utilization_rate
        
        # 生命周期产量
        lifecycle_production = annual_production * pl
        
        return lifecycle_production
    
    def calculate_correct_facility_lcoe_with_utilization(self, tech_params: Dict[str, Any], 
                                                       facility_capacity: float, 
                                                       time_horizon_weeks: int,
                                                       project_lifespan: Optional[int] = None) -> float:
        """
        使用正确的项目生命周期和实际利用率计算设施LCOE
        
        Args:
            tech_params: 技术参数字典
            facility_capacity: 设施容量
            time_horizon_weeks: 优化时间范围（周）
            project_lifespan: 项目生命周期（年），如果为None则使用实例默认值
            
        Returns:
            float: 修正后的LCOE (元/kg)
        """
        pl = project_lifespan if project_lifespan is not None else self.project_lifespan
        
        # 获取设备参数
        equipment_lifetime = tech_params['lifetime_years']
        capex_per_kg_h = tech_params['capex_per_kg_h']
        fixed_opex_annual = tech_params['fixed_opex_annual']
        variable_opex_per_kg = tech_params['variable_opex_per_kg']
        
        # 计算CAPEX（基于设施容量）
        total_capex = capex_per_kg_h * facility_capacity
        
        # 使用项目级别的平准化成本计算（考虑设备更换）
        annual_cost = self.calculate_project_levelized_cost_with_replacement(
            capex=total_capex,
            opex_annual=fixed_opex_annual,
            equipment_lifetime=equipment_lifetime,
            project_lifespan=pl,
            capacity_factor=1.0  # 这里是设施可用性，不是利用率
        )
        
        # 估算年产量（考虑实际利用率）
        if time_horizon_weeks == 1:
            estimated_utilization_rate = 0.60
        else:
            estimated_utilization_rate = 0.75
            
        annual_hours = 8760
        annual_production = facility_capacity * annual_hours * estimated_utilization_rate
        
        # 计算每公斤成本
        if annual_production > 0:
            lcoe_per_kg = annual_cost / annual_production + variable_opex_per_kg
        else:
            lcoe_per_kg = float('inf')
            
        return lcoe_per_kg


class EconomicParametersManager:
    """经济参数管理器"""
    
    @staticmethod
    def define_default_economic_parameters() -> Dict[str, Any]:
        """
        定义默认经济参数
        
        Returns:
            Dict: 包含所有经济参数的字典
        """
        return {
            # 贴现率 (年化)
            'discount_rate': 0.05,  # 5%
            
            # 项目生命周期 (年)
            'project_lifespan': 20,  # 20年项目期
            
            # 资本回收因子计算参数
            'equipment_replacement_needed': True,
            
            # 通用技术经济参数（用于缺失数据的默认值）
            'default_lifetime_years': 15,
            'default_capacity_factor': 0.9,
            
            # 价格参数
            'natural_gas_price_yuan_per_mcm': 2500000,  # 2.5万元/千立方米
            'hydrogen_price_yuan_per_kg': 30,           # 30元/公斤
            'electricity_price_yuan_per_mwh': 400,      # 400元/MWh
            'mtj_price_yuan_per_kg': 4500,              # 4500元/公斤绿色甲醇
            
            # 运输成本 (元/公里·公斤)
            'transport_cost_yuan_per_km_per_kg': 0.05,
            
            # 技术风险调整系数
            'technology_risk_factor': 1.1,  # 10%的技术风险溢价
        }
    
    @staticmethod
    def validate_economic_parameters(params: Dict[str, Any]) -> bool:
        """
        验证经济参数的有效性
        
        Args:
            params: 经济参数字典
            
        Returns:
            bool: 参数是否有效
        """
        required_params = [
            'discount_rate', 'project_lifespan', 'natural_gas_price_yuan_per_mcm',
            'hydrogen_price_yuan_per_kg', 'electricity_price_yuan_per_mwh',
            'mtj_price_yuan_per_kg', 'transport_cost_yuan_per_km_per_kg'
        ]
        
        for param in required_params:
            if param not in params:
                logger.error(f"缺少必要的经济参数: {param}")
                return False
            
            if params[param] is None or (isinstance(params[param], (int, float)) and 
                                       (np.isnan(params[param]) or params[param] < 0)):
                logger.error(f"经济参数无效: {param} = {params[param]}")
                return False
        
        return True