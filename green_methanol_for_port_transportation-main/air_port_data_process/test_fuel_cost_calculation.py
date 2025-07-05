"""
测试燃油价格计算功能的集成
验证pyBADA燃油计算器和燃油价格计算器的集成
"""

import os
import sys
import pandas as pd
import logging
from datetime import datetime

# 添加src目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_fuel_cost_integration():
    """测试燃油成本计算的集成功能"""
    try:
        from pybada_fuel_calculator import PyBADAFuelCalculator
        
        logger.info("🧪 开始测试燃油成本计算集成")
        
        # 创建计算器实例
        calculator = PyBADAFuelCalculator()
        
        # 测试数据
        test_flights = [
            {'aircraft': 'A320', 'distance': 1200, 'passengers': 150, 'route': '北京-上海'},
            {'aircraft': 'B737', 'distance': 800, 'passengers': 140, 'route': '广州-深圳'},
            {'aircraft': 'B777', 'distance': 8000, 'passengers': 300, 'route': '北京-纽约'},
            {'aircraft': 'E190', 'distance': 600, 'passengers': 95, 'route': '成都-重庆'},
            {'aircraft': 'C919', 'distance': 1500, 'passengers': 160, 'route': '上海-西安'}
        ]
        
        results = []
        
        for i, flight in enumerate(test_flights, 1):
            logger.info(f"测试航班 {i}/5: {flight['route']} - {flight['aircraft']}")
            
            # 计算单个航班
            result = calculator.calculate_single_flight(
                aircraft_type=flight['aircraft'],
                distance_km=flight['distance'],
                passengers=flight['passengers']
            )
            
            # 添加航线信息
            result['route'] = flight['route']
            results.append(result)
            
            # 显示关键信息
            if result.get('calculation_successful', False):
                fuel_kg = result.get('total_fuel_kg', 0)
                fuel_cost_avg = result.get('fuel_cost_yuan_avg', 0)
                fuel_cost_range = result.get('fuel_cost_range_yuan', 'N/A')
                fuel_price_avg = result.get('fuel_price_per_kg_avg', 0)
                cost_per_passenger = result.get('fuel_cost_per_passenger', 0)
                market_trend = result.get('fuel_market_trend', 'N/A')
                
                logger.info(f"  ✅ 燃油消耗: {fuel_kg:.1f} kg")
                logger.info(f"  💰 燃油成本: ¥{fuel_cost_avg:.2f} ({fuel_cost_range})")
                logger.info(f"  📊 燃油价格: ¥{fuel_price_avg:.2f}/kg")
                logger.info(f"  👤 单人成本: ¥{cost_per_passenger:.2f}/人")
                logger.info(f"  📈 市场趋势: {market_trend}")
            else:
                logger.warning(f"  ❌ 计算失败")
        
        # 创建结果DataFrame
        df_results = pd.DataFrame(results)
        
        # 选择要显示的关键列
        display_columns = [
            'route', 'aircraft_type', 'distance_km', 'passengers',
            'total_fuel_kg', 'fuel_cost_yuan_avg', 'fuel_cost_range_yuan',
            'fuel_price_per_kg_avg', 'fuel_cost_per_passenger', 'fuel_cost_per_km',
            'co2_direct_kg', 'fuel_market_trend', 'pricing_month'
        ]
        
        # 过滤存在的列
        available_columns = [col for col in display_columns if col in df_results.columns]
        df_display = df_results[available_columns]
        
        # 保存详细结果到Excel
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        excel_filename = f"results/fuel_cost_test_results_{timestamp}.xlsx"
        
        # 确保results目录存在
        os.makedirs("results", exist_ok=True)
        
        with pd.ExcelWriter(excel_filename, engine='openpyxl') as writer:
            # 主要结果
            df_display.to_excel(writer, sheet_name='燃油成本计算结果', index=False)
            
            # 完整结果
            df_results.to_excel(writer, sheet_name='完整计算结果', index=False)
            
            # 统计汇总
            summary_data = {
                '指标': [
                    '总航班数', '成功计算数', '总燃油消耗(kg)', '总燃油成本(元)',
                    '平均燃油价格(元/kg)', '平均单人燃油成本(元)', '总CO2排放(kg)'
                ],
                '数值': [
                    len(results),
                    len([r for r in results if r.get('calculation_successful', False)]),
                    df_results['total_fuel_kg'].sum(),
                    df_results['fuel_cost_yuan_avg'].sum(),
                    df_results['fuel_price_per_kg_avg'].mean(),
                    df_results['fuel_cost_per_passenger'].mean(),
                    df_results['co2_direct_kg'].sum()
                ]
            }
            pd.DataFrame(summary_data).to_excel(writer, sheet_name='统计汇总', index=False)
        
        logger.info(f"📊 结果已保存到: {excel_filename}")
        
        # 打印汇总统计
        logger.info("\n📈 测试汇总统计:")
        logger.info(f"  总航班数: {len(results)}")
        logger.info(f"  成功率: {len([r for r in results if r.get('calculation_successful', False)])}/{len(results)}")
        logger.info(f"  总燃油消耗: {df_results['total_fuel_kg'].sum():.1f} kg")
        logger.info(f"  总燃油成本: ¥{df_results['fuel_cost_yuan_avg'].sum():.2f}")
        logger.info(f"  平均燃油价格: ¥{df_results['fuel_price_per_kg_avg'].mean():.2f}/kg")
        logger.info(f"  平均单人燃油成本: ¥{df_results['fuel_cost_per_passenger'].mean():.2f}")
        logger.info(f"  总CO2排放: {df_results['co2_direct_kg'].sum():.1f} kg")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_price_range_analysis():
    """测试燃油价格区间分析"""
    try:
        from fuel_price_calculator import FuelPriceCalculator
        
        logger.info("\n🔍 测试燃油价格区间分析")
        
        price_calc = FuelPriceCalculator()
        
        # 测试不同月份的价格
        test_months = ['2024-01', '2024-06', '2024-12']
        
        for month in test_months:
            price_info = price_calc.get_monthly_price_info(month)
            logger.info(f"  {month}: {price_info['cost_range']} 元/吨, 趋势: {price_info['trend']}")
        
        # 测试价格波动分析
        volatility = price_calc.analyze_price_volatility()
        logger.info(f"  价格波动率: {volatility['volatility_rate']:.1%}")
        logger.info(f"  最高月份: {volatility['highest_month']} (¥{volatility['highest_price']}/吨)")
        logger.info(f"  最低月份: {volatility['lowest_month']} (¥{volatility['lowest_price']}/吨)")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 价格分析测试失败: {e}")
        return False

if __name__ == "__main__":
    logger.info("🚀 开始燃油成本计算集成测试")
    
    success1 = test_fuel_cost_integration()
    success2 = test_price_range_analysis()
    
    if success1 and success2:
        logger.info("✅ 所有测试通过！燃油成本计算功能已成功集成")
    else:
        logger.error("❌ 部分测试失败，请检查错误信息")
        sys.exit(1) 