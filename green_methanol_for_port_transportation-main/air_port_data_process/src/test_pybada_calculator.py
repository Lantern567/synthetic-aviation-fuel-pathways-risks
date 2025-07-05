"""
测试PyBADA燃油计算器的功能
"""

import sys
import logging
from pybada_fuel_calculator import PyBADAFuelCalculator

def test_pybada_calculator():
    """测试PyBADA计算器"""
    print("🧪 开始测试 PyBADAFuelCalculator...")
    
    # 设置日志级别
    logging.basicConfig(level=logging.WARNING)
    
    try:
        # 初始化计算器
        print("正在初始化计算器...")
        calculator = PyBADAFuelCalculator()
        print("✅ 计算器初始化成功")
        
        # 测试单个航班计算
        print("\n🔬 测试单个航班计算...")
        print("  机型: 空客320")
        print("  距离: 1000 km")
        print("  乘客: 150 人")
        
        result = calculator.calculate_single_flight('空客320', 1000, 150)
        
        print(f"\n📊 计算结果:")
        print(f"  机型: {result['aircraft_type']}")
        print(f"  距离: {result['distance_km']} km")
        print(f"  乘客数: {result['passengers']}")
        print(f"  计算方法: {result['calculation_method']}")
        print(f"  燃油消耗: {result['fuel_consumption_kg']:.2f} kg")
        print(f"  飞行时间: {result['flight_time_minutes']:.2f} 分钟")
        
        # 分阶段结果
        print(f"\n🛫 分阶段结果:")
        print(f"  爬升燃油: {result.get('climb_fuel_kg', 0):.2f} kg")
        print(f"  巡航燃油: {result.get('cruise_fuel_kg', 0):.2f} kg")
        print(f"  下降燃油: {result.get('descent_fuel_kg', 0):.2f} kg")
        
        # 排放结果
        print(f"\n🌿 碳排放结果:")
        print(f"  CO2直接排放: {result['co2_direct_kg']:.2f} kg")
        print(f"  CO2当量排放: {result.get('co2_equivalent_kg', 0):.2f} kg")
        print(f"  辐射强迫CO2当量: {result.get('co2_rf_equivalent_kg', 0):.2f} kg")
        print(f"  单位旅客CO2: {result['co2_per_passenger_kg']:.2f} kg/人")
        print(f"  单位公里CO2: {result.get('co2_per_km_kg', 0):.3f} kg/km")
        
        print("\n✅ 测试完成！")
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_pybada_calculator()
    sys.exit(0 if success else 1) 