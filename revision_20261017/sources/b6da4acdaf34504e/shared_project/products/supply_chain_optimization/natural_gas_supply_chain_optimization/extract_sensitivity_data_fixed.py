#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
修正版敏感性分析数据提取脚本
修复：使用不含短缺成本的平准化成本字段
"""

import os
import json
import pandas as pd
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def extract_data_from_solution(solution_file: Path, run_index: int, param_value: float) -> dict:
    """
    从solution文件中提取数据

    Args:
        solution_file: solution文件路径
        run_index: 运行序号
        param_value: 参数值

    Returns:
        提取的数据字典
    """
    try:
        with open(solution_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 提取顶层字段 - 使用不含短缺成本的字段
        lifecycle_cost = data.get('lifecycle_levelized_cost_excluding_shortage_per_kg', 0)
        total_cost = data.get('total_cost_excluding_shortage', 0)
        demand_ratio = data.get('demand_fulfillment_ratio', 0)
        opt_time = data.get('optimization_time', 0)

        # 提取碳排放数据（正确的字段路径）
        carbon_emissions = data.get('carbon_emissions', {})

        # 总碳排放
        by_stage = carbon_emissions.get('by_stage', {})
        total_carbon = by_stage.get('total_emissions', 0)

        # 碳强度指标（直接从carbon_emissions提取）
        carbon_intensity_kg = carbon_emissions.get('carbon_intensity_kg', 0)  # kg CO₂/kg SAF
        carbon_intensity_mj = carbon_emissions.get('carbon_intensity_mj', 0)  # kg CO₂/MJ

        return {
            'run_index': run_index,
            'param_value': param_value,
            'lifecycle_levelized_cost': lifecycle_cost,
            'total_cost': total_cost,
            'demand_fulfillment_ratio': demand_ratio,
            'optimization_time': opt_time,
            'total_carbon_emission': total_carbon,
            'carbon_intensity_mass': carbon_intensity_kg,
            'carbon_intensity_energy': carbon_intensity_mj
        }

    except Exception as e:
        logger.error(f"提取文件 {solution_file.name} 时出错: {e}")
        return {
            'run_index': run_index,
            'param_value': param_value,
            'lifecycle_levelized_cost': 0,
            'total_cost': 0,
            'demand_fulfillment_ratio': 0,
            'optimization_time': 0,
            'total_carbon_emission': 0,
            'carbon_intensity_mass': 0,
            'carbon_intensity_energy': 0
        }


def main():
    """主函数"""
    # 设置路径
    base_dir = Path(__file__).parent
    sensitivity_dir = base_dir / "results" / "sensitivity_20251001_002400"
    raw_results_dir = sensitivity_dir / "raw_results"
    processed_data_dir = sensitivity_dir / "processed_data"

    if not raw_results_dir.exists():
        logger.error(f"原始数据目录不存在: {raw_results_dir}")
        return

    # 创建输出目录
    processed_data_dir.mkdir(parents=True, exist_ok=True)

    # 加载所有solution文件
    solution_files = sorted(raw_results_dir.glob("solution_*.json"))
    logger.info(f"找到 {len(solution_files)} 个solution文件")

    if len(solution_files) == 0:
        logger.error("没有找到solution文件")
        return

    # 提取数据
    results = []
    for idx, solution_file in enumerate(solution_files, 1):
        # 从文件名提取参数值
        filename = solution_file.name
        param_str = filename.replace('solution_p', '').replace('.json', '')
        param_value = float(param_str)

        # 提取数据
        result = extract_data_from_solution(solution_file, idx, param_value)
        results.append(result)

        # 显示进度
        if idx % 10 == 0 or idx == len(solution_files):
            logger.info(f"已处理 {idx}/{len(solution_files)} 个文件")

    # 转换为DataFrame
    df = pd.DataFrame(results)

    # 数据验证
    valid_count = (df['demand_fulfillment_ratio'] > 0).sum()
    zero_count = len(df) - valid_count
    logger.info(f"\n数据统计:")
    logger.info(f"  总文件数: {len(df)}")
    logger.info(f"  有效数据: {valid_count} 个 (需求满足度>0)")
    logger.info(f"  零数据: {zero_count} 个 (优化失败)")

    # 显示有效数据范围
    if valid_count > 0:
        valid_df = df[df['demand_fulfillment_ratio'] > 0]
        logger.info(f"\n有效数据范围:")
        logger.info(f"  参数值: {valid_df['param_value'].min():.3f} - {valid_df['param_value'].max():.3f}")
        logger.info(f"  需求满足度: {valid_df['demand_fulfillment_ratio'].min():.2%} - {valid_df['demand_fulfillment_ratio'].max():.2%}")
        logger.info(f"  平准化成本(不含短缺): {valid_df['lifecycle_levelized_cost'].min():.2f} - {valid_df['lifecycle_levelized_cost'].max():.2f}")
        logger.info(f"  总碳排放: {valid_df['total_carbon_emission'].min():.0f} - {valid_df['total_carbon_emission'].max():.0f}")

    # 保存数据（使用短路径避免Windows长路径问题）
    original_dir = os.getcwd()
    try:
        # 备份旧文件
        old_results_file = processed_data_dir / "results.csv"
        if old_results_file.exists():
            backup_file = processed_data_dir / "results_v2.csv"
            old_results_file.rename(backup_file)
            logger.info(f"已备份旧文件: results_v2.csv")

        # 切换到目标目录
        os.chdir(processed_data_dir)

        # 保存完整结果
        df.to_csv("results.csv", index=False, encoding='utf-8-sig')
        logger.info(f"✓ 已保存: results.csv (使用不含短缺成本字段)")

        # 保存分类数据
        df[['run_index', 'param_value', 'lifecycle_levelized_cost',
            'total_cost', 'optimization_time']].to_csv(
            "econ_metrics.csv", index=False, encoding='utf-8-sig')
        logger.info(f"✓ 已保存: econ_metrics.csv")

        df[['run_index', 'param_value', 'demand_fulfillment_ratio']].to_csv(
            "dem_metrics.csv", index=False, encoding='utf-8-sig')
        logger.info(f"✓ 已保存: dem_metrics.csv")

        df[['run_index', 'param_value', 'total_carbon_emission',
            'carbon_intensity_mass', 'carbon_intensity_energy']].to_csv(
            "carb_metrics.csv", index=False, encoding='utf-8-sig')
        logger.info(f"✓ 已保存: carb_metrics.csv")

    finally:
        os.chdir(original_dir)

    logger.info(f"\n✓ 数据提取完成！")
    logger.info(f"输出目录: {processed_data_dir}")
    logger.info(f"\n重要提示: 使用的是 'lifecycle_levelized_cost_excluding_shortage_per_kg' 字段")
    logger.info(f"这是不含短缺惩罚成本的真实生产成本，适合权衡分析")


if __name__ == "__main__":
    main()
