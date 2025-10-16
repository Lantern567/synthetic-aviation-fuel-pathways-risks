"""
生成完整的CO₂捕获源数据

本脚本从GIS数据计算所有CO₂捕获源的捕获量，生成供应链优化所需的完整数据集。

输出：data/co2_capture_sources.csv

作者：Claude Code
创建日期：2025-10-13
"""

import sys
import os
from pathlib import Path

# 添加src目录到路径
src_dir = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_dir))

from co2.co2_capture_calculator import CO2CaptureCalculator
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_config():
    """创建配置参数"""
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


def main():
    """主函数：生成完整CO₂捕获源数据"""
    logger.info("=" * 80)
    logger.info("开始生成完整CO₂捕获源数据")
    logger.info("=" * 80)

    # 1. 创建配置
    config = create_config()
    logger.info("✅ 配置创建成功")

    # 2. 初始化计算器
    calculator = CO2CaptureCalculator(config)
    logger.info("✅ CO2CaptureCalculator初始化成功")

    # 3. 设置GIS数据路径
    project_root = Path(__file__).parent.parent.parent.parent
    gis_data_dir = os.path.join(
        project_root,
        'products', 'gis_energy_mapping', 'gis_data_scraper', 'scraped_gis_data'
    )
    logger.info(f"✅ GIS数据目录: {gis_data_dir}")

    # 验证数据文件
    coal_file = os.path.join(gis_data_dir, 'coal_power_plants.csv')
    gas_file = os.path.join(gis_data_dir, 'gas_power_plants.csv')
    oil_file = os.path.join(gis_data_dir, 'oil_refineries.csv')

    logger.info(f"  - Coal power plants: {os.path.exists(coal_file)}")
    logger.info(f"  - Gas power plants: {os.path.exists(gas_file)}")
    logger.info(f"  - Oil refineries: {os.path.exists(oil_file)}")

    # 4. 计算CO₂捕获量（只生成1周数据，因为每周数据相同）
    time_horizon_weeks = 1
    logger.info(f"\n✅ 开始计算CO₂捕获量 (time_horizon_weeks={time_horizon_weeks})")

    result_df = calculator.calculate_from_gis_data(gis_data_dir, time_horizon_weeks)

    logger.info(f"✅ CO₂捕获量计算完成")
    logger.info(f"  - 总记录数: {len(result_df):,}")
    logger.info(f"  - 唯一设施数: {result_df['location_id'].nunique():,}")
    logger.info(f"  - 时间范围: {time_horizon_weeks} 周")

    # 5. 数据统计
    logger.info("\n" + "=" * 80)
    logger.info("数据统计")
    logger.info("=" * 80)

    facility_stats = result_df.groupby('facility_type').agg({
        'location_id': 'nunique',
        'co2_capture_capacity_ton_per_week': 'sum',
    })

    for facility_type, row in facility_stats.iterrows():
        logger.info(f"{facility_type}:")
        logger.info(f"  - 设施数量: {int(row['location_id']):,}")
        logger.info(f"  - 总捕获量: {row['co2_capture_capacity_ton_per_week']:,.2f} 吨/周")

    total_capture = result_df['co2_capture_capacity_ton_per_week'].sum()
    total_cost = result_df['total_capture_cost_yuan_per_week'].sum()

    logger.info(f"\n总体统计:")
    logger.info(f"  - 总设施数: {result_df['location_id'].nunique():,}")
    logger.info(f"  - 总CO₂捕获量: {total_capture:,.2f} 吨/周")
    logger.info(f"  - 总捕获成本: {total_cost:,.2f} 元/周")
    logger.info(f"  - 平均单位成本: {result_df['capture_cost_yuan_per_ton'].mean():.2f} 元/吨")

    # 6. 保存完整数据
    output_dir = Path(__file__).parent / 'data'
    output_file = output_dir / 'co2_capture_sources.csv'

    logger.info(f"\n✅ 保存完整数据到: {output_file}")
    calculator.save_to_csv(result_df, str(output_file))

    logger.info("\n" + "=" * 80)
    logger.info("🎉 完整CO₂捕获源数据生成成功！")
    logger.info("=" * 80)

    return result_df


if __name__ == "__main__":
    result = main()
