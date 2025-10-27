"""
CO₂排放计算器单元测试
Test CO2 Emission Calculator

测试所有碳排放计算方法的正确性和合理性。

Author: Claude Code
Date: 2025-10-13
"""

import os
import sys
import yaml
import logging

# 添加src目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, '..', 'src')
sys.path.insert(0, src_dir)

# 添加项目根目录到路径（用于加载配置）
project_root = os.path.abspath(os.path.join(current_dir, '..', '..', '..', '..', '..'))
sys.path.insert(0, project_root)

from co2.co2_emission_calculator import CO2EmissionCalculator

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_config():
    """加载配置文件"""
    # 从当前测试文件目录计算项目根目录
    # tests/ -> green_hydrogen_supply_chain_optimization/ -> supply_chain_optimization/ -> products/ -> 项目根
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, '..', '..', '..', '..'))

    config_path = os.path.join(
        project_root,
        'shared',
        'data',
        'GreenHydrogenSupplyChainOptimizer_config.yaml'
    )

    logger.info(f"尝试加载配置文件: {config_path}")

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    logger.info(f"成功加载配置文件")
    return config


def test_calculator_initialization():
    """测试计算器初始化"""
    logger.info("\n=== 测试1: 计算器初始化 ===")

    config = load_config()
    calculator = CO2EmissionCalculator(config)

    assert calculator is not None, "计算器初始化失败"
    assert calculator.traditional_jet_fuel_ci == 89, "传统航煤碳强度参数错误"
    assert calculator.saf_energy_content == 43.15, "SAF能量含量参数错误"
    assert calculator.corsia_limit == 30, "CORSIA限值参数错误"

    logger.info("✓ 计算器初始化测试通过")
    return calculator


def test_h2_production_emission(calculator):
    """测试绿氢生产排放计算"""
    logger.info("\n=== 测试2: 绿氢生产排放计算 ===")

    # 测试案例：100 kg氢气
    h2_kg = 100.0
    emission = calculator._calc_h2_production_emission(h2_kg)

    # 预期：50 kWh/kg × 100 kg × 0.03 kgCO₂e/kWh + 100 kg × 0.05 kgCO₂e/kg = 155 kgCO₂e
    expected_min = 150.0
    expected_max = 160.0

    assert expected_min <= emission <= expected_max, \
        f"绿氢生产排放异常: {emission:.2f} kgCO₂e (预期 {expected_min}-{expected_max})"

    logger.info(f"✓ 绿氢生产排放: {emission:.2f} kgCO₂e (合理范围)")
    return emission


def test_co2_capture_emission(calculator):
    """测试CO₂捕获过程排放计算"""
    logger.info("\n=== 测试3: CO₂捕获过程排放计算 ===")

    # 测试案例：1000 kg CO₂
    co2_kg = 1000.0
    emission = calculator._calc_co2_capture_emission(co2_kg)

    # 预期：1000 kg × 0.1 = 100 kgCO₂e
    expected = 100.0

    assert abs(emission - expected) < 1.0, \
        f"CO₂捕获排放异常: {emission:.2f} kgCO₂e (预期 {expected:.2f})"

    logger.info(f"✓ CO₂捕获排放: {emission:.2f} kgCO₂e")
    return emission


def test_transport_emissions(calculator):
    """测试运输排放计算"""
    logger.info("\n=== 测试4: 运输排放计算 ===")

    # 测试案例
    h2_kg = 100.0
    co2_kg = 1000.0
    saf_kg = 500.0
    distance_km = 100.0

    # 氢气管道运输
    h2_pipeline = calculator._calc_h2_transport_emission(h2_kg, distance_km, 'pipeline')
    logger.info(f"  氢气管道运输 (100kg, 100km): {h2_pipeline:.2f} kgCO₂e")

    # 氢气罐车运输
    h2_truck = calculator._calc_h2_transport_emission(h2_kg, distance_km, 'truck')
    logger.info(f"  氢气罐车运输 (100kg, 100km): {h2_truck:.2f} kgCO₂e")

    # CO₂管道运输
    co2_pipeline = calculator._calc_co2_transport_emission(co2_kg, distance_km, 'pipeline')
    logger.info(f"  CO₂管道运输 (1000kg, 100km): {co2_pipeline:.2f} kgCO₂e")

    # CO₂罐车运输
    co2_truck = calculator._calc_co2_transport_emission(co2_kg, distance_km, 'truck')
    logger.info(f"  CO₂罐车运输 (1000kg, 100km): {co2_truck:.2f} kgCO₂e")

    # SAF运输
    saf_transport = calculator._calc_saf_transport_emission(saf_kg, distance_km)
    logger.info(f"  SAF运输 (500kg, 100km): {saf_transport:.2f} kgCO₂e")

    # 验证：罐车运输排放应显著高于管道
    assert h2_truck > h2_pipeline * 5, "氢气罐车排放应远高于管道"
    assert co2_truck > co2_pipeline * 5, "CO₂罐车排放应远高于管道"

    logger.info("✓ 运输排放计算测试通过")


def test_production_emissions(calculator):
    """测试生产过程排放计算"""
    logger.info("\n=== 测试5: 生产过程排放计算 ===")

    saf_kg = 1000.0

    # 甲醇合成排放
    methanol_emission = calculator._calc_methanol_synthesis_emission(saf_kg)
    logger.info(f"  甲醇合成排放 (1000kg SAF): {methanol_emission:.2f} kgCO₂e")

    # MTJ转化排放
    mtj_emission = calculator._calc_mtj_conversion_emission(saf_kg)
    logger.info(f"  MTJ转化排放 (1000kg SAF): {mtj_emission:.2f} kgCO₂e")

    # 验证：排放应在合理范围
    assert 200 <= methanol_emission <= 500, f"甲醇合成排放异常: {methanol_emission:.2f}"
    assert 100 <= mtj_emission <= 300, f"MTJ转化排放异常: {mtj_emission:.2f}"

    logger.info("✓ 生产过程排放计算测试通过")


def test_storage_emission(calculator):
    """测试储存排放计算"""
    logger.info("\n=== 测试6: 储存排放计算 ===")

    h2_kg = 100.0
    co2_kg = 1000.0
    saf_kg = 500.0

    emission = calculator._calc_storage_emission(h2_kg, co2_kg, saf_kg)

    logger.info(f"  储存排放: {emission:.2f} kgCO₂e")

    # 验证：储存排放应相对较低
    assert emission < 100, f"储存排放过高: {emission:.2f} kgCO₂e"

    logger.info("✓ 储存排放计算测试通过")


def test_co2_utilization_credit(calculator):
    """测试CO₂利用负排放计算"""
    logger.info("\n=== 测试7: CO₂利用负排放计算 ===")

    co2_kg = 1000.0
    credit = calculator._calc_co2_utilization_credit(co2_kg)

    # 验证：应该是负值
    assert credit < 0, "CO₂利用负排放应该是负值"
    assert abs(credit) == co2_kg, f"负排放量应等于CO₂利用量: {credit:.2f} vs {-co2_kg:.2f}"

    logger.info(f"✓ CO₂利用负排放: {credit:.2f} kgCO₂e")


def test_lifecycle_calculation():
    """测试完整生命周期碳排放计算"""
    logger.info("\n=== 测试8: 完整生命周期碳排放计算 ===")

    config = load_config()
    calculator = CO2EmissionCalculator(config)

    # 测试案例：生产1000 kg SAF
    # 根据两步法工艺参数
    saf_production_kg = 1000.0
    h2_consumption_kg = 150.0  # 0.15 kg H₂/kg SAF × 1000
    co2_consumption_kg = 3000.0  # 3.0 kg CO₂/kg SAF × 1000

    result = calculator.calculate_lifecycle_emissions(
        saf_production_kg=saf_production_kg,
        h2_consumption_kg=h2_consumption_kg,
        co2_consumption_kg=co2_consumption_kg,
        h2_transport_distance_km=100.0,
        co2_transport_distance_km=80.0,
        saf_transport_distance_km=150.0,
        h2_transport_mode='pipeline',
        co2_transport_mode='pipeline'
    )

    logger.info(f"\n完整生命周期碳排放结果：")
    logger.info(f"  总碳排放: {result['total_emission_kgCO2e']:.2f} kgCO₂e")
    logger.info(f"  碳强度: {result['carbon_intensity_gCO2e_per_MJ']:.2f} gCO₂e/MJ")
    logger.info(f"  减排百分比: {result['emission_reduction_percent']:.1f}%")
    logger.info(f"  CORSIA符合性: {'✓ 符合' if result['corsia_compliant'] else '✗ 不符合'}")

    # 验证关键指标
    assert result['carbon_intensity_gCO2e_per_MJ'] < result['benchmarks']['traditional_jet_fuel_ci_gCO2e_per_MJ'], \
        "碳强度应低于传统航煤"

    assert result['emission_reduction_percent'] > 0, "应该有减排效果"

    # 理想情况下应符合CORSIA标准
    if result['corsia_compliant']:
        logger.info("  ✓ 符合CORSIA标准 (<30 gCO₂e/MJ)")
    else:
        logger.warning(f"  ⚠️ 未达到CORSIA标准，碳强度为 {result['carbon_intensity_gCO2e_per_MJ']:.2f} gCO₂e/MJ")

    logger.info("\n✓ 完整生命周期碳排放计算测试通过")

    return result


def test_emission_report(calculator, emission_data):
    """测试碳排放报告生成"""
    logger.info("\n=== 测试9: 碳排放报告生成 ===")

    report = calculator.generate_emission_report(emission_data)

    assert len(report) > 0, "报告内容为空"
    assert "总碳排放量" in report, "报告缺少总排放量"
    assert "碳强度" in report, "报告缺少碳强度"
    assert "CORSIA" in report, "报告缺少CORSIA符合性"

    logger.info("生成的碳排放报告：")
    logger.info("\n" + report)

    logger.info("\n✓ 碳排放报告生成测试通过")


def run_all_tests():
    """运行所有测试"""
    logger.info("=" * 80)
    logger.info("开始CO₂排放计算器单元测试")
    logger.info("=" * 80)

    try:
        # 测试1: 初始化
        calculator = test_calculator_initialization()

        # 测试2: 绿氢生产排放
        test_h2_production_emission(calculator)

        # 测试3: CO₂捕获排放
        test_co2_capture_emission(calculator)

        # 测试4: 运输排放
        test_transport_emissions(calculator)

        # 测试5: 生产过程排放
        test_production_emissions(calculator)

        # 测试6: 储存排放
        test_storage_emission(calculator)

        # 测试7: CO₂利用负排放
        test_co2_utilization_credit(calculator)

        # 测试8: 完整生命周期计算
        emission_data = test_lifecycle_calculation()

        # 测试9: 报告生成
        test_emission_report(calculator, emission_data)

        logger.info("\n" + "=" * 80)
        logger.info("所有测试通过！✓")
        logger.info("=" * 80)

        return True

    except AssertionError as e:
        logger.error(f"\n测试失败: {e}")
        return False
    except Exception as e:
        logger.error(f"\n测试异常: {e}", exc_info=True)
        return False


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
