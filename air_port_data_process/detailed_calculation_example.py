"""
航班燃油消耗计算详细演示
以阿克苏→上海航班为例，逐步展示完整计算过程
"""

import sys
import os
import math

# 添加源代码目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from aircraft_mapping import get_icao_code, get_aircraft_capacity, calculate_load_factor
from fuel_consumption_calculator import estimate_fuel_consumption_simple
from enhanced_fuel_calculator import haversine_distance, fix_distance_data

def detailed_calculation_example():
    """
    详细的燃油消耗计算演示
    以实际的阿克苏→上海航班为例
    """
    
    print("=" * 60)
    print("航班燃油消耗计算详细演示")
    print("=" * 60)
    
    # 示例航班数据（来自实际数据中被修复的记录）
    flight_data = {
        "航班": "阿克苏→上海",
        "机型": "波音737(中)",  # 中文机型名称
        "载客数": 150,  # 实际载客数
        "原始里程": 0,  # 原始数据里程为0，需要修复
        "出发城市": "阿克苏",
        "到达城市": "上海",
        "出发坐标": (41.2, 80.2),  # (纬度, 经度)
        "到达坐标": (31.2, 121.5)
    }
    
    print(f"🛩️  航班信息:")
    print(f"   航班线路: {flight_data['航班']}")
    print(f"   机型: {flight_data['机型']}")
    print(f"   载客数: {flight_data['载客数']} 人")
    print(f"   原始里程: {flight_data['原始里程']} 公里")
    print()
    
    # 第一步：机型映射
    print("📋 第一步：机型映射")
    print("-" * 30)
    chinese_aircraft = flight_data['机型']
    icao_code = get_icao_code(chinese_aircraft)
    standard_capacity = get_aircraft_capacity(icao_code)
    
    print(f"   中文机型: {chinese_aircraft}")
    print(f"   ICAO代码: {icao_code}")
    print(f"   标准载客量: {standard_capacity} 人")
    print()
    
    # 第二步：距离修复（重点）
    print("📍 第二步：距离修复（核心功能）")
    print("-" * 30)
    print(f"   问题：原始里程为 {flight_data['原始里程']} 公里，无法计算燃油消耗")
    print(f"   解决：使用坐标计算实际飞行距离")
    print()
    
    # 使用Haversine公式计算距离
    lat1, lon1 = flight_data['出发坐标']
    lat2, lon2 = flight_data['到达坐标']
    
    print(f"   出发坐标: 阿克苏 ({lat1}°N, {lon1}°E)")
    print(f"   到达坐标: 上海 ({lat2}°N, {lon2}°E)")
    
    # 详细展示Haversine公式计算过程
    print(f"\n   🧮 Haversine公式计算过程:")
    print(f"   1. 转换为弧度:")
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    print(f"      lat1 = {lat1_rad:.6f} rad")
    print(f"      lon1 = {lon1_rad:.6f} rad")
    print(f"      lat2 = {lat2_rad:.6f} rad")
    print(f"      lon2 = {lon2_rad:.6f} rad")
    
    print(f"\n   2. 计算差值:")
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    print(f"      Δlat = {dlat:.6f} rad")
    print(f"      Δlon = {dlon:.6f} rad")
    
    print(f"\n   3. Haversine公式:")
    print(f"      a = sin²(Δlat/2) + cos(lat1) × cos(lat2) × sin²(Δlon/2)")
    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
    print(f"      a = {a:.6f}")
    
    print(f"      c = 2 × arcsin(√a)")
    c = 2 * math.asin(math.sqrt(a))
    print(f"      c = {c:.6f}")
    
    print(f"      距离 = c × 地球半径(6371 km)")
    calculated_distance = c * 6371
    print(f"      距离 = {calculated_distance:.2f} 公里")
    
    # 验证我们的函数
    distance_verify = haversine_distance(lat1, lon1, lat2, lon2)
    print(f"\n   ✅ 函数验证: {distance_verify:.2f} 公里")
    print()
    
    # 第三步：载客率计算
    print("👥 第三步：载客率计算")
    print("-" * 30)
    actual_passengers = flight_data['载客数']
    load_factor = calculate_load_factor(actual_passengers, icao_code)
    
    print(f"   实际载客数: {actual_passengers} 人")
    print(f"   标准载客量: {standard_capacity} 人")
    print(f"   载客率 = {actual_passengers} ÷ {standard_capacity} = {load_factor:.3f} ({load_factor*100:.1f}%)")
    print()
    
    # 第四步：燃油消耗计算（详细展示）
    print("⛽ 第四步：燃油消耗计算")
    print("-" * 30)
    
    # 从源码中获取参数
    base_fuel_rates = {
        'B737': 3.2,   # 波音737基础燃油消耗率：3.2升/公里
    }
    base_rate = base_fuel_rates[icao_code]
    
    print(f"   基础参数:")
    print(f"   • 飞行距离: {calculated_distance:.2f} 公里")
    print(f"   • 机型: {icao_code}")
    print(f"   • 基础燃油消耗率: {base_rate} 升/公里")
    print(f"   • 载客率: {load_factor:.3f}")
    print()
    
    # 载客率影响系数
    load_factor_coefficient = 0.7 + 0.3 * load_factor
    print(f"   载客率影响系数:")
    print(f"   • 公式: 0.7 + 0.3 × 载客率")
    print(f"   • 系数 = 0.7 + 0.3 × {load_factor:.3f} = {load_factor_coefficient:.3f}")
    print(f"   • 说明: 载客率越高，单位乘客燃油消耗越低（规模效应）")
    print()
    
    # 距离影响系数
    if calculated_distance < 500:
        distance_coefficient = 1.3
        distance_category = "短程"
        distance_explanation = "起降燃油消耗占比高"
    elif calculated_distance < 1500:
        distance_coefficient = 1.0
        distance_category = "中程"
        distance_explanation = "标准效率"
    else:
        distance_coefficient = 0.95
        distance_category = "长程"
        distance_explanation = "巡航效率高"
    
    print(f"   距离影响系数:")
    print(f"   • 距离: {calculated_distance:.2f} 公里 → {distance_category}航班")
    print(f"   • 系数: {distance_coefficient}")
    print(f"   • 说明: {distance_explanation}")
    print()
    
    # 最终计算
    print(f"   燃油消耗计算:")
    print(f"   1. 基础燃油消耗(升) = 距离 × 基础消耗率 × 载客率系数 × 距离系数")
    fuel_liters = calculated_distance * base_rate * load_factor_coefficient * distance_coefficient
    print(f"      = {calculated_distance:.2f} × {base_rate} × {load_factor_coefficient:.3f} × {distance_coefficient}")
    print(f"      = {fuel_liters:.2f} 升")
    
    print(f"\n   2. 转换为公斤:")
    print(f"      燃油密度 = 0.8 kg/L（航空燃油标准密度）")
    fuel_kg = fuel_liters * 0.8
    print(f"      燃油消耗(kg) = {fuel_liters:.2f} × 0.8 = {fuel_kg:.2f} 公斤")
    
    # 验证函数计算
    calculated_fuel = estimate_fuel_consumption_simple(calculated_distance, icao_code, actual_passengers)
    print(f"\n   ✅ 函数验证: {calculated_fuel:.2f} 公斤")
    print()
    
    # 第五步：修复效果对比
    print("📊 第五步：修复效果对比")
    print("-" * 30)
    print(f"   修复前:")
    print(f"   • 里程: 0 公里")
    print(f"   • 燃油消耗: 0 公斤")
    print(f"   • 状态: ❌ 无法计算，数据不完整")
    print()
    print(f"   修复后:")
    print(f"   • 里程: {calculated_distance:.2f} 公里")
    print(f"   • 燃油消耗: {fuel_kg:.2f} 公斤")
    print(f"   • 状态: ✅ 计算成功，数据完整")
    print()
    
    # 第六步：结果分析
    print("📈 第六步：结果分析")
    print("-" * 30)
    
    # 与其他B737航班对比
    print(f"   性能指标:")
    fuel_per_km = fuel_kg / calculated_distance
    fuel_per_passenger = fuel_kg / actual_passengers
    print(f"   • 燃油效率: {fuel_per_km:.2f} 公斤/公里")
    print(f"   • 人均燃油: {fuel_per_passenger:.2f} 公斤/人")
    print(f"   • 总燃油: {fuel_kg:.2f} 公斤")
    print()
    
    print(f"   航班分类:")
    print(f"   • 机型等级: 中型机（B737）")
    print(f"   • 航程类型: {distance_category}航班")
    print(f"   • 载客水平: {load_factor*100:.1f}%载客率")
    print()
    
    print("=" * 60)
    print("✅ 计算完成！此航班已从无效数据成功修复为有效的燃油消耗记录")
    print("=" * 60)
    
    return {
        'distance_km': calculated_distance,
        'fuel_consumption_kg': fuel_kg,
        'load_factor': load_factor,
        'icao_code': icao_code
    }

if __name__ == "__main__":
    detailed_calculation_example()