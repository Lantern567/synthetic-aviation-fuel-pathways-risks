"""
CO₂捕获计算器测试脚本

测试CO2CaptureCalculator的完整功能：
1. GIS数据加载
2. CO₂捕获量计算
3. 数据验证
4. CSV输出

作者：Claude Code
创建日期：2025-10-13
"""

import sys
import os
from pathlib import Path

# 添加项目根目录和src目录到路径
project_root = Path(__file__).parent.parent.parent.parent.parent
src_dir = Path(__file__).parent.parent / 'src'
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(src_dir))

from co2.co2_capture_calculator import CO2CaptureCalculator
import pandas as pd
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_test_config():
    """创建测试配置"""
    return {
        'co2_parameters': {
            'capture_sources': {
                # 燃煤电厂参数
                'coal_power_capture_rate': 0.85,
                'coal_power_emission_factor': 0.95,  # tCO₂/MWh
                'coal_power_capacity_factor': 0.70,

                # 天然气电厂参数
                'lng_power_capture_rate': 0.90,
                'lng_power_emission_factor': 0.42,  # tCO₂/MWh
                'lng_power_capacity_factor': 0.75,

                # 石油炼厂参数
                'oil_refinery_capture_rate': 0.80,
                'oil_refinery_emission_factor': 0.6,  # tCO₂/吨原油
                'oil_refinery_capacity_factor': 0.85,
            },
            'capture_costs': {
                'coal_power_yuan_per_ton': 150,
                'lng_power_yuan_per_ton': 180,
                'oil_refinery_yuan_per_ton': 120,
            }
        }
    }


def test_co2_calculator():
    """测试CO₂捕获计算器"""
    logger.info("="*60)
    logger.info("开始测试CO₂捕获计算器")
    logger.info("="*60)

    # 1. 创建测试配置
    config = create_test_config()
    logger.info("\n✅ Step 1: 配置创建成功")

    # 2. 初始化计算器
    calculator = CO2CaptureCalculator(config)
    logger.info("✅ Step 2: CO2CaptureCalculator初始化成功")

    # 3. 设置GIS数据路径
    gis_data_dir = os.path.join(
        project_root,
        'products', 'gis_energy_mapping', 'gis_data_scraper', 'scraped_gis_data'
    )
    logger.info(f"\n✅ Step 3: GIS数据目录: {gis_data_dir}")

    # 验证数据文件是否存在
    coal_file = os.path.join(gis_data_dir, 'coal_power_plants.csv')
    gas_file = os.path.join(gis_data_dir, 'gas_power_plants.csv')
    oil_file = os.path.join(gis_data_dir, 'oil_refineries.csv')

    logger.info(f"  - Coal power plants file exists: {os.path.exists(coal_file)}")
    logger.info(f"  - Gas power plants file exists: {os.path.exists(gas_file)}")
    logger.info(f"  - Oil refineries file exists: {os.path.exists(oil_file)}")

    # 4. 运行计算（使用1周测试）
    time_horizon_weeks = 1
    logger.info(f"\n✅ Step 4: 开始计算CO₂捕获量 (time_horizon_weeks={time_horizon_weeks})")

    try:
        result_df = calculator.calculate_from_gis_data(gis_data_dir, time_horizon_weeks)
        logger.info(f"✅ Step 5: CO₂捕获量计算完成")
        logger.info(f"  - 总记录数: {len(result_df)}")
        logger.info(f"  - 预期记录数: (3821 + 270 + 220) × {time_horizon_weeks} = {(3821 + 270 + 220) * time_horizon_weeks}")

        # 5. 验证数据格式
        logger.info(f"\n✅ Step 6: 验证数据格式")
        logger.info(f"  - DataFrame columns: {list(result_df.columns)}")
        logger.info(f"  - DataFrame shape: {result_df.shape}")

        # 检查数据类型
        required_cols = [
            'location_id', 'location_name', 'facility_type',
            'latitude', 'longitude', 'week',
            'co2_capture_capacity_ton_per_week',
            'capture_cost_yuan_per_ton'
        ]

        missing_cols = [col for col in required_cols if col not in result_df.columns]
        if missing_cols:
            logger.error(f"❌ 缺少必需列: {missing_cols}")
        else:
            logger.info(f"  ✓ 所有必需列都存在")

        # 6. 显示示例数据
        logger.info(f"\n✅ Step 7: 数据示例（前5条）")
        print(result_df.head())

        # 7. 统计分析
        logger.info(f"\n✅ Step 8: 按设施类型统计")
        facility_stats = result_df.groupby('facility_type').agg({
            'location_id': 'nunique',
            'co2_capture_capacity_ton_per_week': 'sum',
            'capture_cost_yuan_per_ton': 'mean'
        })
        print(facility_stats)

        # 8. 总体统计
        total_capture = result_df['co2_capture_capacity_ton_per_week'].sum()
        total_cost = result_df['total_capture_cost_yuan_per_week'].sum()
        avg_cost = result_df['capture_cost_yuan_per_ton'].mean()

        logger.info(f"\n✅ Step 9: 总体统计")
        logger.info(f"  - 总CO₂捕获量: {total_capture:,.2f} 吨/周")
        logger.info(f"  - 总捕获成本: {total_cost:,.2f} 元/周")
        logger.info(f"  - 平均单位成本: {avg_cost:.2f} 元/吨")

        # 9. 保存到CSV
        output_dir = os.path.join(
            project_root,
            'products', 'supply_chain_optimization',
            'green_hydrogen_supply_chain_optimization', 'data'
        )
        output_file = os.path.join(output_dir, 'co2_capture_sources_test.csv')

        logger.info(f"\n✅ Step 10: 保存测试结果到CSV")
        calculator.save_to_csv(result_df, output_file)
        logger.info(f"  - 文件保存位置: {output_file}")

        # 10. 验收测试
        logger.info(f"\n" + "="*60)
        logger.info("验收测试结果")
        logger.info("="*60)

        checks = {
            "数据加载成功": len(result_df) > 0,
            "记录数合理": 1000 < len(result_df) < 10000,
            "CO₂捕获量>0": (result_df['co2_capture_capacity_ton_per_week'] > 0).all(),
            "捕获成本>0": (result_df['capture_cost_yuan_per_ton'] > 0).all(),
            "坐标范围有效": (
                (result_df['latitude'] >= -90).all() and
                (result_df['latitude'] <= 90).all() and
                (result_df['longitude'] >= -180).all() and
                (result_df['longitude'] <= 180).all()
            ),
            "CSV文件生成": os.path.exists(output_file),
        }

        all_passed = all(checks.values())

        for check_name, passed in checks.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            logger.info(f"{status}: {check_name}")

        if all_passed:
            logger.info("\n" + "="*60)
            logger.info("🎉 所有测试通过！CO₂捕获计算器验证成功！")
            logger.info("="*60)
        else:
            logger.error("\n" + "="*60)
            logger.error("❌ 部分测试失败，请检查错误信息")
            logger.error("="*60)

        return result_df

    except Exception as e:
        logger.error(f"❌ 测试过程中发生错误: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None


if __name__ == "__main__":
    test_co2_calculator()
