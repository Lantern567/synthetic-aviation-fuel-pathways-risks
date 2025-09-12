"""
绿色甲醇供应链成本分析引擎

该模块专门负责详细的成本分解和效率分析，包括：
- 电解制氢成本分析
- MTJ生产成本分析  
- 运输成本分析
- 综合转化效率计算
- 成本结构优化分析
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CostComponents:
    """成本组件数据结构"""
    electricity_cost: float = 0.0  # 电力成本
    equipment_amortization: float = 0.0  # 设备摊销
    operation_maintenance: float = 0.0  # 运营维护
    raw_materials: float = 0.0  # 原料成本
    transport_cost: float = 0.0  # 运输成本
    storage_cost: float = 0.0  # 储存成本
    total_cost: float = 0.0  # 总成本


@dataclass
class EfficiencyMetrics:
    """效率指标数据结构"""
    theoretical_efficiency: float = 0.0  # 理论效率
    actual_efficiency: float = 0.0  # 实际效率
    system_efficiency: float = 0.0  # 系统效率
    economic_efficiency: float = 0.0  # 经济效率


class SupplyChainCostAnalyzer:
    """供应链成本分析器"""
    
    def __init__(self, config: Dict, costs: Dict, economic_params: Dict):
        """
        初始化成本分析器
        
        Args:
            config: 配置参数
            costs: 成本参数
            economic_params: 经济参数
        """
        self.config = config
        self.costs = costs
        self.economic_params = economic_params
        
        # 成本计算参数
        self.cost_config = config.get('cost_parameters', {})
        self.equipment_costs = config.get('equipment_raw_costs', {})
        
        # 日志记录
        logger.info("供应链成本分析器初始化完成")
    
    def calculate_electrolysis_unit_costs(self) -> Dict[str, float]:
        """
        计算电解制氢详细单位成本
        
        Returns:
            Dict: 电解制氢成本分解
        """
        try:
            # 获取电解制氢相关参数
            electrolysis_efficiency = self.costs.get('electrolysis_efficiency', 0.7)  # 默认70%效率
            power_consumption = self.costs.get('electrolysis_power_consumption', 50)  # MWh/t H2
            electricity_price = self.costs.get('renewable_electricity_cost_yuan_per_mwh', 300)  # 元/MWh
            
            # 设备成本参数
            electrolyzer_capex = self.costs.get('electrolyzer_capex_yuan_per_kg_h2_year', 0)
            electrolyzer_opex = self.costs.get('electrolyzer_opex_yuan_per_kg_h2', 0)
            
            # 计算各项成本组件 (元/kg H2)
            costs = CostComponents()
            
            # 1. 电力成本 - 计算单位成本（元/kg H2）
            # 这应该是单次生产成本，不需要乘以项目年限
            single_production_electricity_cost = (power_consumption * electricity_price / 1000) / electrolysis_efficiency
            costs.electricity_cost = single_production_electricity_cost
            
            # 2. 设备摊销成本 - 计算单位成本（元/kg H2）
            # electrolyzer_capex是年化平准化成本，需要转换为单位成本
            annual_hours = 8760  # 一年的小时数
            capacity_factor = self.economic_params.get('electrolyzer_capacity_factor', 0.75)
            actual_annual_hours = annual_hours * capacity_factor
            
            # 年化成本 ÷ 年产能 = 单位成本
            annual_equipment_cost_per_kg = electrolyzer_capex / actual_annual_hours
            costs.equipment_amortization = annual_equipment_cost_per_kg
            
            # 3. 运营维护成本 - 计算单位成本（元/kg H2）
            # electrolyzer_opex应该是单位运营维护成本
            costs.operation_maintenance = electrolyzer_opex
            
            # 4. 总成本
            costs.total_cost = (costs.electricity_cost + 
                               costs.equipment_amortization + 
                               costs.operation_maintenance)
            
            result = {
                'hydrogen_electricity_cost_yuan_per_kg': costs.electricity_cost,
                'hydrogen_equipment_amortization_yuan_per_kg': costs.equipment_amortization,
                'hydrogen_operation_maintenance_yuan_per_kg': costs.operation_maintenance,
                'hydrogen_total_production_cost_yuan_per_kg': costs.total_cost,
                'hydrogen_electricity_cost_ratio': costs.electricity_cost / costs.total_cost if costs.total_cost > 0 else 0,
                'hydrogen_equipment_cost_ratio': costs.equipment_amortization / costs.total_cost if costs.total_cost > 0 else 0,
                'hydrogen_operation_cost_ratio': costs.operation_maintenance / costs.total_cost if costs.total_cost > 0 else 0
            }
            
            logger.info(f"电解制氢成本计算完成: 总成本 {costs.total_cost:.2f} 元/kg H2")
            return result
            
        except Exception as e:
            logger.error(f"电解制氢成本计算失败: {e}")
            return {}
    
    def calculate_mtj_production_unit_costs(self, hydrogen_cost_per_kg: float) -> Dict[str, float]:
        """
        计算MTJ生产详细单位成本
        
        Args:
            hydrogen_cost_per_kg: 氢气单位成本 (元/kg H2)
            
        Returns:
            Dict: MTJ生产成本分解
        """
        try:
            # MTJ生产参数
            mtj_base_lcop = self.costs.get('mtj_base_lcop_yuan_per_kg', 0)  # MTJ基础平准化成本
            hydrogen_ratio = 0.188  # kg H2 per kg MTJ (化学计量比)
            
            # 成本计算
            costs = CostComponents()
            
            # 1. 氢气原料成本
            costs.raw_materials = hydrogen_cost_per_kg * hydrogen_ratio
            
            # 2. MTJ设备和运营成本 - 计算单位成本（元/kg MTJ）
            # 基础LCOP是单位生产成本，直接使用
            equipment_operation_cost = max(0, mtj_base_lcop - costs.raw_materials)
            
            # 分配设备和运营成本
            costs.equipment_amortization = equipment_operation_cost * 0.6  # 假设60%为设备摊销
            costs.operation_maintenance = equipment_operation_cost * 0.4  # 假设40%为运营维护
            
            # 3. 总成本 (不包含CO2成本)
            costs.total_cost = costs.raw_materials + costs.equipment_amortization + costs.operation_maintenance
            
            result = {
                'mtj_hydrogen_raw_material_cost_yuan_per_kg': costs.raw_materials,
                'mtj_co2_raw_material_cost_yuan_per_kg': 0,  # 移除CO2成本，设为0
                'mtj_equipment_amortization_yuan_per_kg': costs.equipment_amortization,
                'mtj_operation_maintenance_yuan_per_kg': costs.operation_maintenance,
                'mtj_total_production_cost_yuan_per_kg': costs.total_cost,
                'mtj_hydrogen_cost_ratio': costs.raw_materials / costs.total_cost if costs.total_cost > 0 else 0,
                'mtj_co2_cost_ratio': 0,  # 移除CO2成本占比，设为0
                'mtj_equipment_cost_ratio': costs.equipment_amortization / costs.total_cost if costs.total_cost > 0 else 0,
                'mtj_operation_cost_ratio': costs.operation_maintenance / costs.total_cost if costs.total_cost > 0 else 0
            }
            
            logger.info(f"MTJ生产成本计算完成: 总成本 {costs.total_cost:.2f} 元/kg MTJ")
            return result
            
        except Exception as e:
            logger.error(f"MTJ生产成本计算失败: {e}")
            return {}
    
    def calculate_transport_unit_costs(self, distance_km: float, cargo_type: str = "MTJ") -> Dict[str, float]:
        """
        计算运输单位成本
        
        Args:
            distance_km: 运输距离 (km)
            cargo_type: 货物类型 ("H2", "MTJ", "NG")
            
        Returns:
            Dict: 运输成本分解
        """
        try:
            # 基础运输成本参数 (元/kg·km)
            base_transport_costs = {
                "H2": 0.5,   # 氢气运输成本较高
                "MTJ": 0.2,  # MTJ运输成本中等
                "NG": 0.1    # 天然气运输成本较低
            }
            
            base_cost_per_kg_km = base_transport_costs.get(cargo_type, 0.2)
            
            # 距离调整系数 (长距离运输有规模效应)
            if distance_km > 500:
                distance_factor = 0.8
            elif distance_km > 200:
                distance_factor = 0.9
            else:
                distance_factor = 1.0
            
            # 计算运输成本
            unit_cost_per_kg_km = base_cost_per_kg_km * distance_factor
            
            # 储存配送成本 (元/kg)
            storage_cost_per_kg = {
                "H2": 2.0,   # 氢气储存成本高
                "MTJ": 0.5,  # MTJ储存成本中等
                "NG": 0.1    # 天然气储存成本低
            }
            
            storage_cost = storage_cost_per_kg.get(cargo_type, 0.5)
            
            result = {
                f'{cargo_type.lower()}_transport_unit_cost_yuan_per_kg_km': unit_cost_per_kg_km,
                f'{cargo_type.lower()}_storage_cost_yuan_per_kg': storage_cost,
                f'{cargo_type.lower()}_transport_distance_factor': distance_factor
            }
            
            logger.debug(f"{cargo_type}运输成本计算: {unit_cost_per_kg_km:.3f} 元/kg·km")
            return result
            
        except Exception as e:
            logger.error(f"运输成本计算失败: {e}")
            return {}
    
    def calculate_conversion_efficiencies(self) -> Dict[str, float]:
        """
        计算综合转化效率
        
        Returns:
            Dict: 各种效率指标
        """
        try:
            # 电解制氢效率
            electrolysis_efficiency = self.costs.get('electrolysis_efficiency', 0.7)
            
            # MTJ转化效率 (假设值，实际应从配置获取)
            h2_to_mtj_efficiency = 0.85  # 氢气制MTJ转化效率
            
            # 综合效率
            overall_efficiency = electrolysis_efficiency * h2_to_mtj_efficiency
            
            # 能耗计算
            power_consumption_mwh_per_kg_h2 = self.costs.get('electrolysis_power_consumption', 50) / 1000
            h2_ratio_per_kg_mtj = 0.188  # kg H2 per kg MTJ
            power_consumption_mwh_per_kg_mtj = power_consumption_mwh_per_kg_h2 * h2_ratio_per_kg_mtj / electrolysis_efficiency
            
            result = {
                'electrolysis_theoretical_efficiency': 1.0,  # 理论最大效率
                'electrolysis_actual_efficiency': electrolysis_efficiency,
                'h2_to_mtj_conversion_efficiency': h2_to_mtj_efficiency,
                'overall_electricity_to_mtj_efficiency': overall_efficiency,
                'power_consumption_mwh_per_kg_h2': power_consumption_mwh_per_kg_h2,
                'power_consumption_mwh_per_kg_mtj': power_consumption_mwh_per_kg_mtj,
                'system_efficiency_vs_theoretical': overall_efficiency
            }
            
            logger.info(f"转化效率计算完成: 综合效率 {overall_efficiency:.1%}")
            return result
            
        except Exception as e:
            logger.error(f"转化效率计算失败: {e}")
            return {}
    
    def analyze_supply_chain_costs(self, solution: Dict) -> Dict[str, any]:
        """
        综合分析供应链成本
        
        Args:
            solution: 优化解决方案
            
        Returns:
            Dict: 综合成本分析结果
        """
        try:
            # 1. 电解制氢成本分析
            h2_costs = self.calculate_electrolysis_unit_costs()
            h2_unit_cost = h2_costs.get('hydrogen_total_production_cost_yuan_per_kg', 0)
            
            # 2. MTJ生产成本分析
            mtj_costs = self.calculate_mtj_production_unit_costs(h2_unit_cost)
            
            # 3. 转化效率分析
            efficiencies = self.calculate_conversion_efficiencies()
            
            # 4. 运输成本分析 (示例距离)
            h2_transport_costs = self.calculate_transport_unit_costs(200, "H2")
            mtj_transport_costs = self.calculate_transport_unit_costs(300, "MTJ")
            
            # 5. 综合成本结构分析
            total_production_cost = (h2_unit_cost + 
                                   mtj_costs.get('mtj_total_production_cost_yuan_per_kg', 0))
            
            # 合并所有结果
            comprehensive_analysis = {
                **h2_costs,
                **mtj_costs,
                **efficiencies,
                **h2_transport_costs,
                **mtj_transport_costs,
                'total_production_cost_yuan_per_kg_mtj': total_production_cost,
            }
            
            logger.info("供应链成本综合分析完成")
            return comprehensive_analysis
            
        except Exception as e:
            logger.error(f"供应链成本分析失败: {e}")
            return {}
    
    def generate_cost_analysis_report(self, solution: Dict, output_path: str) -> str:
        """
        生成详细成本分析报告
        
        Args:
            solution: 优化解决方案
            output_path: 输出文件路径
            
        Returns:
            str: 报告文件路径
        """
        try:
            # 执行成本分析
            analysis_results = self.analyze_supply_chain_costs(solution)
            
            # 创建分析报告DataFrame
            report_data = []
            
            # 电解制氢成本部分
            report_data.append({
                '成本类别': '电解制氢',
                '成本项目': '电力成本',
                '单位成本(元/kg)': analysis_results.get('hydrogen_electricity_cost_yuan_per_kg', 0),
                '成本占比(%)': analysis_results.get('hydrogen_electricity_cost_ratio', 0) * 100,
                '备注': '可再生能源电力成本'
            })
            
            report_data.append({
                '成本类别': '电解制氢',
                '成本项目': '设备摊销',
                '单位成本(元/kg)': analysis_results.get('hydrogen_equipment_amortization_yuan_per_kg', 0),
                '成本占比(%)': analysis_results.get('hydrogen_equipment_cost_ratio', 0) * 100,
                '备注': '电解槽设备投资摊销'
            })
            
            # MTJ生产成本部分
            report_data.append({
                '成本类别': 'MTJ生产',
                '成本项目': '氢气原料',
                '单位成本(元/kg)': analysis_results.get('mtj_hydrogen_raw_material_cost_yuan_per_kg', 0),
                '成本占比(%)': analysis_results.get('mtj_hydrogen_cost_ratio', 0) * 100,
                '备注': '氢气原料成本'
            })
            
            # CO2原料成本已移除，不再显示
            
            # 效率指标部分
            report_data.append({
                '成本类别': '效率指标',
                '成本项目': '电解制氢效率',
                '单位成本(元/kg)': 0,
                '成本占比(%)': analysis_results.get('electrolysis_actual_efficiency', 0) * 100,
                '备注': '实际电解制氢效率'
            })
            
            # 创建DataFrame并保存
            df = pd.DataFrame(report_data)
            df.to_csv(output_path, index=False, encoding='utf-8-sig')
            
            logger.info(f"成本分析报告已保存: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"生成成本分析报告失败: {e}")
            return ""


def create_cost_analyzer(config: Dict, costs: Dict, economic_params: Dict) -> SupplyChainCostAnalyzer:
    """
    创建成本分析器实例
    
    Args:
        config: 配置参数
        costs: 成本参数  
        economic_params: 经济参数
        
    Returns:
        SupplyChainCostAnalyzer: 成本分析器实例
    """
    return SupplyChainCostAnalyzer(config, costs, economic_params)