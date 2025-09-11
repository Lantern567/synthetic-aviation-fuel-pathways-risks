#!/usr/bin/env python3
"""
20年生命周期成本分解分析
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from shared.cost_analysis_engine import create_cost_analyzer
import yaml

def analyze_lifecycle_costs():
    """分析20年生命周期成本"""
    
    print("=== 20年生命周期成本分解分析 ===\n")
    
    # 加载配置
    config_path = "../../../shared/data/NaturalGasSupplyChainOptimizer_config.yaml"
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # 实际运行的成本参数
    costs = {
        'electrolysis_efficiency': 0.7,
        'electrolysis_power_consumption': 50,  # MWh/t H2
        'renewable_electricity_cost_yuan_per_mwh': 300,
        'electrolyzer_capex_yuan_per_kg_h2_year': 15355.76,  # 年化平准化成本
        'electrolyzer_opex_yuan_per_kg_h2': 0,  # 已包含在平准化成本中
        'mtj_base_lcop_yuan_per_kg': 808.0
    }
    
    economic_params = {
        'discount_rate': 0.08,
        'project_lifespan_years': 20,
        'electrolyzer_capacity_factor': 0.75
    }
    
    cost_analyzer = create_cost_analyzer(config, costs, economic_params)
    
    print("成本参数:")
    print(f"   项目生命周期: {economic_params['project_lifespan_years']} 年")
    print(f"   电解槽容量因子: {economic_params['electrolyzer_capacity_factor']*100:.1f}%")
    print(f"   电解制氢效率: {costs['electrolysis_efficiency']*100:.1f}%")
    print()
    
    # 氢气成本分析
    print("氢气生产成本 (20年生命周期):")
    h2_costs = cost_analyzer.calculate_electrolysis_unit_costs()
    
    electricity_cost = h2_costs.get('hydrogen_electricity_cost_yuan_per_kg', 0)
    equipment_cost = h2_costs.get('hydrogen_equipment_amortization_yuan_per_kg', 0)
    opex_cost = h2_costs.get('hydrogen_operation_maintenance_yuan_per_kg', 0)
    total_h2_cost = h2_costs.get('hydrogen_total_production_cost_yuan_per_kg', 0)
    
    print(f"   电力成本: {electricity_cost:.2f} 元/kg H2 ({electricity_cost/total_h2_cost*100:.1f}%)")
    print(f"   设备摊销: {equipment_cost:.2f} 元/kg H2 ({equipment_cost/total_h2_cost*100:.1f}%)")
    print(f"   运营维护: {opex_cost:.2f} 元/kg H2 ({opex_cost/total_h2_cost*100:.1f}%)")
    print(f"   总成本: {total_h2_cost:.2f} 元/kg H2")
    
    # 单年成本计算
    annual_electricity_cost = electricity_cost / economic_params['project_lifespan_years']
    annual_equipment_cost = equipment_cost / economic_params['project_lifespan_years']
    annual_total_cost = total_h2_cost / economic_params['project_lifespan_years']
    
    print(f"\n   (单年成本对比:")
    print(f"    电力: {annual_electricity_cost:.2f} 元/kg·年)")
    print(f"    设备: {annual_equipment_cost:.2f} 元/kg·年)")
    print(f"    总计: {annual_total_cost:.2f} 元/kg·年)")
    print()
    
    # MTJ生产成本分析
    print("MTJ生产成本 (20年生命周期):")
    mtj_costs = cost_analyzer.calculate_mtj_production_unit_costs(total_h2_cost)
    
    h2_raw_cost = mtj_costs.get('mtj_hydrogen_raw_material_cost_yuan_per_kg', 0)
    co2_raw_cost = mtj_costs.get('mtj_co2_raw_material_cost_yuan_per_kg', 0)
    mtj_equipment_cost = mtj_costs.get('mtj_equipment_amortization_yuan_per_kg', 0)
    mtj_opex_cost = mtj_costs.get('mtj_operation_maintenance_yuan_per_kg', 0)
    total_mtj_cost = mtj_costs.get('mtj_total_production_cost_yuan_per_kg', 0)
    
    print(f"   氢气原料: {h2_raw_cost:.2f} 元/kg MTJ ({h2_raw_cost/total_mtj_cost*100:.1f}%)")
    print(f"   CO2原料: {co2_raw_cost:.2f} 元/kg MTJ ({co2_raw_cost/total_mtj_cost*100:.1f}%)")
    print(f"   设备摊销: {mtj_equipment_cost:.2f} 元/kg MTJ ({mtj_equipment_cost/total_mtj_cost*100:.1f}%)")
    print(f"   运营维护: {mtj_opex_cost:.2f} 元/kg MTJ ({mtj_opex_cost/total_mtj_cost*100:.1f}%)")
    print(f"   总成本: {total_mtj_cost:.2f} 元/kg MTJ")
    
    # 氢气消耗计算
    h2_ratio = 0.188  # kg H2 per kg MTJ
    print(f"\n   氢气消耗比例: {h2_ratio} kg H2/kg MTJ")
    print(f"   氢气成本验证: {total_h2_cost:.2f} × {h2_ratio} = {total_h2_cost * h2_ratio:.2f} 元/kg MTJ")
    print()
    
    # 单年成本对比
    annual_mtj_cost = total_mtj_cost / economic_params['project_lifespan_years']
    print(f"   (单年MTJ成本: {annual_mtj_cost:.2f} 元/kg·年)")
    print()
    
    # 效率分析
    efficiencies = cost_analyzer.calculate_conversion_efficiencies()
    print("转化效率:")
    print(f"   电解制氢实际效率: {efficiencies.get('electrolysis_actual_efficiency', 0)*100:.1f}%")
    print(f"   H2→MTJ转化效率: {efficiencies.get('h2_to_mtj_conversion_efficiency', 0)*100:.1f}%")
    print(f"   综合电力→MTJ效率: {efficiencies.get('overall_electricity_to_mtj_efficiency', 0)*100:.1f}%")
    print(f"   单位电力消耗: {efficiencies.get('power_consumption_mwh_per_kg_mtj', 0):.3f} MWh/kg MTJ")
    print()
    
    print("成本解释:")
    print("   1. 这些是20年项目生命周期的总成本")
    print("   2. 不含缺货成本和运输成本")
    print("   3. 氢气成本主要来自设备投资摊销")
    print("   4. MTJ成本主要来自氢气原料")
    print("   5. 成本已考虑容量因子和效率损失")

if __name__ == "__main__":
    analyze_lifecycle_costs()