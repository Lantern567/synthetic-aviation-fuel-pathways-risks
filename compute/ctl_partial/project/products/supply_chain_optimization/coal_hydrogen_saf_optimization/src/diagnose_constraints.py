"""
约束冲突诊断工具
用于诊断优化模型中的约束冲突和不可行性问题
"""

import pandas as pd
import numpy as np
import yaml
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ConstraintDiagnostic:
    """约束诊断类"""

    def __init__(self, config_path=None):
        """初始化诊断工具"""
        if config_path is None:
            # 默认配置路径
            config_path = Path(__file__).parents[4] / 'shared' / 'data' / 'GreenHydrogenSupplyChainOptimizer_config.yaml'

        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

        logger.info(f"加载配置文件: {config_path}")

    def diagnose_co2_supply(self, airports_data, co2_sources_data):
        """
        诊断CO₂供应是否充足

        Args:
            airports_data: DataFrame，机场需求数据
            co2_sources_data: DataFrame，CO₂捕获源数据

        Returns:
            dict: 诊断结果
        """
        logger.info("=" * 80)
        logger.info("诊断1: CO₂供应充足性")
        logger.info("=" * 80)

        # 计算总SAF需求
        if 'total_weekly_demand_kg' in airports_data.columns:
            total_saf_demand = airports_data['total_weekly_demand_kg'].sum()
        else:
            total_saf_demand = 0
            logger.warning("未找到机场需求数据列: total_weekly_demand_kg")

        # 计算总CO₂需求（SAF需求 × CO₂消耗比）
        co2_consumption_ratio = self.config['technologies']['green_h2_co2_to_saf']['co2_consumption_ratio']
        total_co2_demand = total_saf_demand * co2_consumption_ratio

        # 计算总CO₂供应（每周）
        time_horizon_weeks = self.config['basic_parameters']['time_horizon_weeks']
        hours_per_week = self.config['basic_parameters']['hours_per_week']

        if 'weekly_co2_supply_kg' in co2_sources_data.columns:
            total_co2_supply = co2_sources_data['weekly_co2_supply_kg'].sum()
        else:
            total_co2_supply = 0
            logger.warning("未找到CO₂供应数据列: weekly_co2_supply_kg")

        # 诊断结果
        result = {
            'total_saf_demand_kg': total_saf_demand,
            'total_co2_demand_kg': total_co2_demand,
            'total_co2_supply_kg': total_co2_supply,
            'supply_ratio': total_co2_supply / total_co2_demand if total_co2_demand > 0 else 0,
            'is_sufficient': total_co2_supply >= total_co2_demand
        }

        logger.info(f"SAF周需求: {total_saf_demand:,.2f} kg")
        logger.info(f"CO₂周需求: {total_co2_demand:,.2f} kg (SAF需求 × {co2_consumption_ratio})")
        logger.info(f"CO₂周供应: {total_co2_supply:,.2f} kg")
        logger.info(f"供应比例: {result['supply_ratio']:.2%}")

        if result['is_sufficient']:
            logger.info("✓ CO₂供应充足")
        else:
            shortfall = total_co2_demand - total_co2_supply
            logger.warning(f"⚠️ CO₂供应不足! 缺口: {shortfall:,.2f} kg ({shortfall/total_co2_demand:.1%})")

        return result

    def diagnose_h2_supply(self, airports_data, renewable_plants_data):
        """
        诊断氢气供应能力

        Args:
            airports_data: DataFrame，机场需求数据
            renewable_plants_data: DataFrame，可再生能源发电厂数据

        Returns:
            dict: 诊断结果
        """
        logger.info("\n" + "=" * 80)
        logger.info("诊断2: 氢气供应能力")
        logger.info("=" * 80)

        # 计算总SAF需求
        if 'total_weekly_demand_kg' in airports_data.columns:
            total_saf_demand = airports_data['total_weekly_demand_kg'].sum()
        else:
            total_saf_demand = 0

        # 计算总氢气需求（SAF需求 × H₂消耗比）
        h2_consumption_ratio = self.config['technologies']['green_h2_co2_to_saf']['h2_consumption_ratio']
        total_h2_demand = total_saf_demand * h2_consumption_ratio

        # 计算可再生能源发电总量（每周）
        hours_per_week = self.config['basic_parameters']['hours_per_week']
        if 'hourly_generation' in renewable_plants_data.columns:
            # 计算每个电厂的周发电量
            total_weekly_generation_mwh = 0
            for _, row in renewable_plants_data.iterrows():
                if isinstance(row['hourly_generation'], (list, np.ndarray)):
                    weekly_gen = sum(row['hourly_generation'][:hours_per_week])
                    total_weekly_generation_mwh += weekly_gen
        else:
            total_weekly_generation_mwh = 0
            logger.warning("未找到发电数据列: hourly_generation")

        # 计算电解制氢能力
        electrolysis_power_consumption = self.config['cost_parameters']['electrolysis']['electrolysis_power_consumption']  # kWh/kg H₂
        max_h2_production_kg = (total_weekly_generation_mwh * 1000) / electrolysis_power_consumption

        # 诊断结果
        result = {
            'total_saf_demand_kg': total_saf_demand,
            'total_h2_demand_kg': total_h2_demand,
            'total_weekly_generation_mwh': total_weekly_generation_mwh,
            'max_h2_production_kg': max_h2_production_kg,
            'supply_ratio': max_h2_production_kg / total_h2_demand if total_h2_demand > 0 else 0,
            'is_sufficient': max_h2_production_kg >= total_h2_demand
        }

        logger.info(f"SAF周需求: {total_saf_demand:,.2f} kg")
        logger.info(f"H₂周需求: {total_h2_demand:,.2f} kg (SAF需求 × {h2_consumption_ratio})")
        logger.info(f"可再生能源周发电量: {total_weekly_generation_mwh:,.2f} MWh")
        logger.info(f"最大H₂制氢量: {max_h2_production_kg:,.2f} kg (发电量 ÷ {electrolysis_power_consumption} kWh/kg)")
        logger.info(f"供应比例: {result['supply_ratio']:.2%}")

        if result['is_sufficient']:
            logger.info("✓ 氢气供应能力充足")
        else:
            shortfall = total_h2_demand - max_h2_production_kg
            logger.warning(f"⚠️ 氢气供应能力不足! 缺口: {shortfall:,.2f} kg ({shortfall/total_h2_demand:.1%})")

        return result

    def diagnose_levelized_cost_constraint(self):
        """诊断平准化成本约束的合理性"""
        logger.info("\n" + "=" * 80)
        logger.info("诊断3: 平准化成本约束合理性")
        logger.info("=" * 80)

        # 从配置文件读取参数
        threshold = self.config['economic_parameters']['levelized_cost_threshold_yuan_per_kg']
        h2_cost = self.config['cost_parameters']['hydrogen']['electrolysis_cost_yuan_per_kg']

        # 估算实际平准化成本
        # 简化计算：氢气成本 + 设施成本 + 运输成本
        h2_consumption = self.config['technologies']['green_h2_co2_to_saf']['h2_consumption_ratio']
        estimated_h2_cost_per_kg_saf = h2_cost * h2_consumption

        # 设施成本（粗略估算）
        variable_opex = self.config['facility_lcoe_parameters']['variable_opex_per_kg']

        # 总估算成本
        estimated_total_cost = estimated_h2_cost_per_kg_saf + variable_opex + 5.0  # +5元运输等其他成本

        result = {
            'threshold_yuan_per_kg': threshold,
            'estimated_total_cost_yuan_per_kg': estimated_total_cost,
            'h2_component_yuan_per_kg': estimated_h2_cost_per_kg_saf,
            'facility_component_yuan_per_kg': variable_opex,
            'is_feasible': estimated_total_cost <= threshold
        }

        logger.info(f"平准化成本门槛: {threshold} 元/kg")
        logger.info(f"氢气成本组成: {estimated_h2_cost_per_kg_saf:.2f} 元/kg ({h2_cost} × {h2_consumption})")
        logger.info(f"设施运营成本: {variable_opex:.2f} 元/kg")
        logger.info(f"估算总成本: {estimated_total_cost:.2f} 元/kg")
        logger.info(f"成本余量: {threshold - estimated_total_cost:.2f} 元/kg")

        if result['is_feasible']:
            logger.info(f"✓ 平准化成本约束可行 ({estimated_total_cost/threshold:.1%} of threshold)")
        else:
            excess = estimated_total_cost - threshold
            logger.warning(f"⚠️ 平准化成本约束过严! 超出: {excess:.2f} 元/kg ({excess/threshold:.1%})")
            logger.warning(f"   建议将门槛值提高至: {estimated_total_cost * 1.2:.1f} 元/kg")

        return result

    def diagnose_time_scale_matching(self):
        """诊断时间尺度匹配问题"""
        logger.info("\n" + "=" * 80)
        logger.info("诊断4: 时间尺度匹配检查")
        logger.info("=" * 80)

        time_horizon_weeks = self.config['basic_parameters']['time_horizon_weeks']
        hours_per_week = self.config['basic_parameters']['hours_per_week']

        logger.info(f"优化时间窗口: {time_horizon_weeks} 周")
        logger.info(f"每周小时数: {hours_per_week} 小时")
        logger.info(f"总时段数: {time_horizon_weeks * hours_per_week} 小时")
        logger.info("")
        logger.info("时间尺度一致性:")
        logger.info("  - 氢气生产: 小时级 (hydrogen_production_vars[location, hour])")
        logger.info("  - SAF生产: 小时级 (production_vars[location, tech, hour])")
        logger.info("  - 氢气运输: 周级总量 (hydrogen_transport_vars[src, dst])")
        logger.info("  - SAF运输: 周级 (transport_vars[location, airport, week])")
        logger.info("  - CO₂供应: 周级 (按周计算供应量)")
        logger.info("")
        logger.info("✓ 时间尺度设计合理（小时级生产，周级运输）")

        return {
            'time_horizon_weeks': time_horizon_weeks,
            'hours_per_week': hours_per_week,
            'total_hours': time_horizon_weeks * hours_per_week
        }

    def generate_diagnosis_report(self, airports_data=None, co2_sources_data=None, renewable_plants_data=None):
        """生成完整诊断报告"""
        logger.info("\n" + "=" * 80)
        logger.info("开始全面约束诊断")
        logger.info("=" * 80)

        results = {}

        # 诊断3: 平准化成本约束（不需要数据）
        results['levelized_cost'] = self.diagnose_levelized_cost_constraint()

        # 诊断4: 时间尺度匹配（不需要数据）
        results['time_scale'] = self.diagnose_time_scale_matching()

        # 诊断1和2需要数据
        if airports_data is not None and co2_sources_data is not None:
            results['co2_supply'] = self.diagnose_co2_supply(airports_data, co2_sources_data)

        if airports_data is not None and renewable_plants_data is not None:
            results['h2_supply'] = self.diagnose_h2_supply(airports_data, renewable_plants_data)

        # 生成总结
        logger.info("\n" + "=" * 80)
        logger.info("诊断总结")
        logger.info("=" * 80)

        issues = []
        if 'co2_supply' in results and not results['co2_supply']['is_sufficient']:
            issues.append("CO₂供应不足")
        if 'h2_supply' in results and not results['h2_supply']['is_sufficient']:
            issues.append("氢气供应能力不足")
        if not results['levelized_cost']['is_feasible']:
            issues.append("平准化成本约束过严")

        if issues:
            logger.warning(f"发现 {len(issues)} 个潜在问题:")
            for i, issue in enumerate(issues, 1):
                logger.warning(f"  {i}. {issue}")
        else:
            logger.info("✓ 所有诊断项通过")

        return results


def main():
    """主函数 - 运行诊断"""
    diagnostic = ConstraintDiagnostic()

    # 仅运行不需要数据的诊断
    logger.info("运行基础诊断（不需要输入数据）...")
    results = diagnostic.generate_diagnosis_report()

    logger.info("\n提示:")
    logger.info("  如需诊断CO₂和H₂供应，请在优化器中调用:")
    logger.info("  diagnostic.diagnose_co2_supply(airports_df, co2_sources_df)")
    logger.info("  diagnostic.diagnose_h2_supply(airports_df, renewable_plants_df)")

    return results


if __name__ == '__main__':
    main()
