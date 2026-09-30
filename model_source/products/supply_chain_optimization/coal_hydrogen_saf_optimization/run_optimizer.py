#!/usr/bin/env python
"""
SAF供应链优化命令行工具

支持两步法、一�?�工艺以及煤炭+绿氢并行路线的快速运行入口。
"""

import sys
import argparse
from pathlib import Path

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.runner import UnifiedSAFOptimizer, CoalSAFOptimizerRunner


def main() -> None:
    parser = argparse.ArgumentParser(
        description='SAF供应链优化工具 - 支持多种工艺路线',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''示例:
  python run_optimizer.py --process two_step
  python run_optimizer.py --process one_step --threads 64 --parallel-workers 64 --time-limit 7200
  python run_optimizer.py --process coal_two_step --threads 32 --time-limit 1800 --results-dir results/coal
'''
    )

    parser.add_argument(
        '--process',
        type=str,
        required=True,
        choices=['two_step', 'one_step', 'coal_two_step'],
        help='工艺路线: two_step (H₂+CO₂→甲醇→SAF)、one_step (H₂+CO₂→RWGS→FT→SAF)、coal_two_step (煤炭气化CO₂ + 绿氢)' 
    )
    parser.add_argument('--config', type=str, default=None, help='配置文件路径 (默认使用内置配置)')
    parser.add_argument('--threads', type=int, default=None, help='Gurobi求解线程数 (默认: 自动检测)')
    parser.add_argument('--parallel-workers', type=int, default=None, help='数据处理/距离计算并行workers (默认: 自动检测)')
    parser.add_argument('--time-limit', type=int, default=3600, help='求解时间限制(秒) (默认: 3600)')
    parser.add_argument('--mip-gap', type=float, default=0.01, help='MIP Gap (默认: 0.01=1%)')
    parser.add_argument('--weeks', type=int, default=12, help='优化时间范围(周) (默认: 12)')
    parser.add_argument('--log-level', type=str, default='INFO', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], help='日志级别 (默认: INFO)')
    parser.add_argument('--results-dir', type=str, default=None, help='结果输出目录 (默认: 项目results目录)')

    args = parser.parse_args()

    print('=' * 80)
    print(f'SAF供应链优化 - {args.process.upper()}')
    print('=' * 80)
    print(f'工艺路线: {args.process}')
    print(f'MIP Gap: {args.mip_gap:.2%}')
    print(f'优化周数: {args.weeks}')
    if args.threads:
        print(f'Gurobi线程: {args.threads}')
    if args.parallel_workers:
        print(f'并行Workers: {args.parallel_workers}')
    if args.config:
        print(f'配置文件: {args.config}')
    if args.results_dir:
        print(f'结果目录: {args.results_dir}')
    print('=' * 80)
    print()

    if args.process == 'coal_two_step':
        runner = CoalSAFOptimizerRunner(
            config_path=args.config,
            time_horizon_weeks=args.weeks,
            threads=args.threads,
            time_limit=args.time_limit,
            mip_gap=args.mip_gap,
            results_dir=Path(args.results_dir) if args.results_dir else None,
            log_level=args.log_level,
        )
        print('开始优化 (煤炭+绿氢两步法)...\n')
        results = runner.run()

        print('\n' + '=' * 80)
        print('优化结果')
        print('=' * 80)
        objective = results.get('objective_value')
        if objective is not None:
            print(f'目标函数: ¥{objective:,.2f}')
            gap = results.get('gap')
            if gap is not None:
                print(f'MIP Gap: {gap:.2%}')
            print(f'求解时间: {results.get("solve_time", 0):.1f} 秒')
        else:
            print('未获得可行解')

        results_path = results.get('results_path')
        if results_path:
            print(f'结果文件: {results_path}')
    else:
        optimizer = UnifiedSAFOptimizer(
            process_type=args.process,
            config_path=args.config,
            threads=args.threads,
            parallel_workers=args.parallel_workers,
            time_limit=args.time_limit,
            mip_gap=args.mip_gap,
            time_horizon_weeks=args.weeks,
            log_level=args.log_level,
            results_dir=args.results_dir,
        )

        print('开始优化...\n')
        results = optimizer.run()

        print('\n' + '=' * 80)
        print('优化结果')
        print('=' * 80)
        print(f"状态: {results['status']}")

        if results['status'] in ['OPTIMAL', 'TIME_LIMIT'] and results['objective_value'] is not None:
            print(f"总成本: ¥{results['objective_value']:,.2f}")
            print(f"MIP Gap: {results['gap']:.2%}")
            print(f"求解时间: {results['solve_time']:.1f} 秒 ({results['solve_time']/60:.1f} 分钟)")
            print(f"总运行时间: {results['total_time']:.1f} 秒 ({results['total_time']/60:.1f} 分钟)")
            print(f"变量数: {results['num_variables']:,}")
            print(f"约束数: {results['num_constraints']:,}")
        else:
            print(f"优化失败: {results['status_code']}")

    print('=' * 80)
    print()


if __name__ == '__main__':
    main()
