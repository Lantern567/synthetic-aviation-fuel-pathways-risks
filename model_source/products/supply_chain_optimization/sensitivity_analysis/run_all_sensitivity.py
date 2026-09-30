"""
全量敏感性分析主入口

运行全部13个场景、5个参数维度的敏感性分析（共223次Gurobi运行）。

用法:
    # 全量运行（4进程并行）
    python run_all_sensitivity.py

    # 只运行某个参数组
    python run_all_sensitivity.py --param ng_price

    # 只运行某个场景
    python run_all_sensitivity.py --scenario GTL-BH

    # dry-run（测试框架，不调用Gurobi）
    python run_all_sensitivity.py --dry-run

    # 查看进度
    python run_all_sensitivity.py --status-only

参数组说明:
    ng_price          - 天然气价格 (Group A)
    coal_price        - 煤炭价格 (Group B)
    bh_capex          - 副产氢PSA设备CAPEX (Groups A/B/C/D)
    electricity_capex_grid - 电价×电解槽CAPEX二维 (Groups C/D)
    dac_cost          - DAC捕获成本 (Group D)
"""
import os
import sys
import logging
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "products/supply_chain_optimization/natural_gas_supply_chain_optimization/src"))
sys.path.insert(0, str(PROJECT_ROOT / "products/supply_chain_optimization/coal_hydrogen_saf_optimization/src"))
sys.path.insert(0, str(PROJECT_ROOT / "products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/src"))
sys.path.insert(0, str(PROJECT_ROOT / "products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/src"))

# 确保results目录存在
RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            RESULTS_DIR / f"run_all_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
            encoding="utf-8"
        )
    ]
)
logger = logging.getLogger(__name__)


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="SAF敏感性分析全量运行器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("--workers", type=int, default=4, help="并行进程数 (默认: 4)")
    parser.add_argument("--threads", type=int, default=25, help="每进程Gurobi线程数 (默认: 25)")
    parser.add_argument("--time-limit", type=float, default=7200.0, help="每次Gurobi时间限制（秒）(默认: 7200)")
    parser.add_argument("--mip-gap", type=float, default=0.01, help="MIP间隙 (默认: 0.01=1%%)")
    parser.add_argument("--no-skip", action="store_true", help="不跳过已有结果，重新运行全部")
    parser.add_argument("--dry-run", action="store_true", help="测试框架，不调用Gurobi")
    parser.add_argument("--param", type=str, default=None,
                        choices=["ng_price", "coal_price", "bh_capex", "electricity_capex_grid", "dac_cost"],
                        help="只运行指定参数")
    parser.add_argument("--scenario", type=str, default=None, help="只运行指定场景")
    parser.add_argument("--status-only", action="store_true", help="只显示进度状态，不运行")
    args = parser.parse_args()

    from products.supply_chain_optimization.sensitivity_analysis.scenario_registry import (
        count_total_runs, list_scenarios
    )
    from products.supply_chain_optimization.sensitivity_analysis.parallel_executor import run_all
    from products.supply_chain_optimization.sensitivity_analysis.result_collector import print_progress_summary

    if args.status_only:
        print_progress_summary()
        return

    logger.info("=" * 80)
    logger.info("SAF供应链敏感性分析 - 全量运行")
    logger.info(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"总计划运行: {count_total_runs()} 次")
    logger.info(f"并行进程: {args.workers}, 每进程线程: {args.threads}")
    logger.info(f"时间限制: {args.time_limit}秒 ({args.time_limit/3600:.1f}小时)")
    logger.info(f"MIP Gap: {args.mip_gap:.1%}")
    if args.param:
        logger.info(f"参数过滤: {args.param}")
    if args.scenario:
        logger.info(f"场景过滤: {args.scenario}")
    logger.info("=" * 80)

    param_filter = [args.param] if args.param else None
    scenario_filter = [args.scenario] if args.scenario else None

    results = run_all(
        n_workers=args.workers,
        gurobi_threads=args.threads,
        time_limit_s=args.time_limit,
        mip_gap=args.mip_gap,
        skip_existing=not args.no_skip,
        param_filter=param_filter,
        scenario_filter=scenario_filter,
        dry_run=args.dry_run,
    )

    n_ok = sum(1 for r in results if r.get("status") in ("optimal", "feasible"))
    n_err = sum(1 for r in results if r.get("status") == "error")
    logger.info(f"\n全量运行完成: {n_ok}/{len(results)} 成功, {n_err} 失败")

    print("\n" + "=" * 80)
    print_progress_summary()

    # 导出CSV
    from products.supply_chain_optimization.sensitivity_analysis.result_collector import export_to_csv
    csv_path = export_to_csv()
    if csv_path:
        logger.info(f"结果CSV: {csv_path}")


if __name__ == "__main__":
    main()
