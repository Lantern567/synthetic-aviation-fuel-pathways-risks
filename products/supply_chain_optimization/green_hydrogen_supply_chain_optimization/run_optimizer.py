#!/usr/bin/env python
"""
SAF供应链优化命令行工具

简单的命令行接口，支持一步法和两步法优化。

使用示例:
    # 两步法，使用默认配置
    python run_optimizer.py --process two_step

    # 一步法，指定CPU和时间限制
    python run_optimizer.py --process one_step --threads 64 --parallel-workers 64 --time-limit 7200

    # 自定义配置文件
    python run_optimizer.py --process two_step --config path/to/config.yaml --threads 128

作者: Claude Code
创建日期: 2025-10-23
"""

import sys
import os
import argparse
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

def main():
    parser = argparse.ArgumentParser(
        description='SAF供应链优化工具 - 支持一步法和两步法',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 两步法，默认配置
  python run_optimizer.py --process two_step

  # 一步法，64线程，2小时
  python run_optimizer.py --process one_step --threads 64 --parallel-workers 64 --time-limit 7200

  # 最大并行度
  python run_optimizer.py --process two_step --threads 128 --parallel-workers 128 --time-limit 14400

  # 内存受限环境
  python run_optimizer.py --process one_step --threads 16 --parallel-workers 16 --time-limit 10800
        """
    )

    # 必选参数
    parser.add_argument(
        '--process',
        type=str,
        required=True,
        choices=['two_step', 'one_step'],
        help='工艺路线: two_step (两步法: H₂+CO₂→甲醇→SAF) 或 one_step (一步法: H₂+CO₂→RWGS→FT→SAF)'
    )

    # 可选参数
    parser.add_argument(
        '--config',
        type=str,
        default=None,
        help='配置文件路径 (默认使用内置配置)'
    )

    parser.add_argument(
        '--threads',
        type=int,
        default=None,
        help='Gurobi求解器线程数 (默认: CPU核心数-2)'
    )

    parser.add_argument(
        '--parallel-workers',
        type=int,
        default=None,
        help='数据处理和距离计算的并行workers数 (默认: CPU核心数)'
    )

    parser.add_argument(
        '--time-limit',
        type=float,
        default=1.0e100,
        help='Gurobi求解时间限制(秒) (默认: 1.0e100=接近无限制，与配置文件一致)'
    )

    parser.add_argument(
        '--mip-gap',
        type=float,
        default=0.01,
        help='MIP优化间隙 (默认: 0.01=1%%)'
    )

    parser.add_argument(
        '--weeks',
        type=int,
        default=1,
        help='优化时间范围(周) (默认: 1周)'
    )

    parser.add_argument(
        '--log-level',
        type=str,
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='日志级别 (默认: INFO)'
    )

    args = parser.parse_args()

    os.environ["GH_SUPPLY_CHAIN_PROCESS"] = args.process

    from src.runner import UnifiedSAFOptimizer

    # 打印配置信息
    print("=" * 80)
    print(f"SAF供应链优化 - {args.process.upper()}")
    print("=" * 80)
    print(f"工艺路线: {args.process}")
    print(f"Gurobi线程数: {args.threads if args.threads else '自动检测'}")
    print(f"并行Workers: {args.parallel_workers if args.parallel_workers else '自动检测'}")
    print(f"时间限制: {args.time_limit}秒 ({args.time_limit/60:.1f}分钟)")
    print(f"MIP Gap: {args.mip_gap:.2%}")
    print(f"优化周数: {args.weeks}")
    if args.config:
        print(f"配置文件: {args.config}")
    print("=" * 80)
    print()

    # 创建优化器
    optimizer = UnifiedSAFOptimizer(
        process_type=args.process,
        config_path=args.config,
        threads=args.threads,
        parallel_workers=args.parallel_workers,
        time_limit=args.time_limit,
        mip_gap=args.mip_gap,
        time_horizon_weeks=args.weeks,
        log_level=args.log_level
    )

    # 运行优化
    print("开始优化...")
    print()
    results = optimizer.run()

    # 输出结果
    print()
    print("=" * 80)
    print("优化结果")
    print("=" * 80)
    print(f"状态: {results['status']}")

    if results['status'] in ['OPTIMAL', 'TIME_LIMIT'] and results['objective_value'] is not None:
        print(f"总成本: ¥{results['objective_value']:,.2f}")
        print(f"MIP Gap: {results['gap']:.2%}")
        print(f"求解时间: {results['solve_time']:.1f}秒 ({results['solve_time']/60:.1f}分钟)")
        print(f"总运行时间: {results['total_time']:.1f}秒 ({results['total_time']/60:.1f}分钟)")
        print(f"变量数: {results['num_variables']:,}")
        print(f"约束数: {results['num_constraints']:,}")
    else:
        print(f"优化失败: {results['status_code']}")

    print("=" * 80)
    print()
    print("结果已保存到 results/ 目录")
    print()

    return 0 if results['status'] in ['OPTIMAL', 'TIME_LIMIT'] else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print()
        print("✗ 用户中断")
        sys.exit(1)
    except Exception as e:
        print()
        print(f"✗ 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
