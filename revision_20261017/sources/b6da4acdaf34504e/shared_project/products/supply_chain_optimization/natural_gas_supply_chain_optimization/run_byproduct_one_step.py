#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
天然气供应链优化模型 - 副产氢一步法运行脚本
运行副产氢场景下的一步法优化（NG→FT合成→SAF）
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
current_dir = Path(__file__).parent
project_root = current_dir.parent.parent.parent  # 向上3级到项目根目录
sys.path.insert(0, str(project_root))

# 添加src目录到Python路径
src_dir = current_dir / "src"
sys.path.insert(0, str(src_dir))

# 导入核心优化模型
from core.natural_gas_optimization_model import NaturalGasSupplyChainOptimizer

def main():
    """主函数 - 运行副产氢一步法优化"""
    try:
        print("="*80)
        print("天然气供应链优化模型 - 副产氢一步法（NG→FT合成→SAF）")
        print("="*80)
        print("开始执行优化...")

        # 配置文件路径：使用副产氢一步法配置
        config_path = os.path.join(
            project_root,
            "shared",
            "data",
            "NaturalGasByproductHydrogenOptimizer_config_one_step.yaml"
        )

        print(f"\n配置文件: {config_path}")

        # 检查配置文件是否存在
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"配置文件不存在: {config_path}")

        # OSM文件路径
        osm_file_path = os.path.join(
            project_root,
            "products",
            "supply_chain_optimization",
            "natural_gas_supply_chain_optimization",
            "data",
            "china-latest.osm.pbf"
        )

        print(f"OSM文件路径: {osm_file_path}")

        # 1. 初始化优化器（指定配置文件和日志子目录）
        print(f"\n正在初始化优化器（副产氢一步法）...")
        optimizer = NaturalGasSupplyChainOptimizer(
            config_path=config_path,
            log_subdir='byproduct_hydrogen/one_step',  # 指定日志和结果子目录
            osm_pbf_path=osm_file_path
        )

        # 2. 加载数据
        print("\n正在加载数据...")
        optimizer.load_data_from_excel(
            airport_excel_path=None  # 从配置文件自动获取路径
        )

        # 3. 构建优化模型
        print("\n正在构建优化模型...")
        optimizer.build_model()

        # 4. 求解模型
        print("\n正在求解优化模型...")
        solution = optimizer.solve()

        if solution:
            print("\n" + "="*80)
            print("优化求解成功！")
            print("="*80)

            # 显示关键结果
            optimization_status = solution.get('optimization_status', 'Unknown')
            optimization_time = solution.get('optimization_time', 0)
            time_window_weeks = solution.get('time_window_weeks', 1)

            print(f"\n求解状态: {optimization_status}")
            print(f"求解时间: {optimization_time:.2f} 秒")
            print(f"时间窗口: {time_window_weeks} 周")

            # 显示成本指标
            lifecycle_levelized_cost_per_kg = solution.get('lifecycle_levelized_cost_excluding_shortage_per_kg', 0)
            annual_levelized_cost_per_kg = solution.get('annual_levelized_cost_excluding_shortage_per_kg', 0)
            demand_fulfillment = solution.get('demand_fulfillment_ratio', 0)

            if isinstance(lifecycle_levelized_cost_per_kg, (int, float)):
                print(f"\n关键指标:")
                print(f"  - 生命周期平准化成本: {lifecycle_levelized_cost_per_kg:,.2f} 元/kg")

            if isinstance(annual_levelized_cost_per_kg, (int, float)):
                print(f"  - 年化平准化成本: {annual_levelized_cost_per_kg:,.2f} 元/kg")

            if isinstance(demand_fulfillment, (int, float)):
                print(f"  - 需求满足程度: {demand_fulfillment*100:.2f}%")

            # 输出设施建设数量
            facilities_count = len(solution.get('facilities', {}))
            print(f"  - 建设设施数量: {facilities_count}")

            # 保存结果（会自动使用配置的byproduct_hydrogen/one_step子目录）
            optimizer.save_results(solution, None)

            print(f"\n结果已保存到目录（根据log_subdir自动设置）")
            print("="*80)

            return 0  # 成功
        else:
            print("\n" + "="*80)
            print("模型求解失败或未返回结果")
            print("="*80)
            return 1  # 失败

    except Exception as e:
        print("\n" + "="*80)
        print("模型执行过程中发生错误")
        print("="*80)
        print(f"错误类型: {type(e).__name__}")
        print(f"错误信息: {e}")

        import traceback
        print("\n完整错误堆栈信息:")
        print("-"*60)
        traceback.print_exc()
        print("="*80)

        return 1  # 失败


if __name__ == '__main__':
    sys.exit(main())
