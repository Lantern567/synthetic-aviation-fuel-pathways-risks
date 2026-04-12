"""
Group A: 天然气价格敏感性分析
覆盖场景: GTL-GH, GTL, GTL-BH
NG价格范围: 2.0 ~ 8.0 元/m³ (9个点)
总运行数: 9 × 3 = 27 次
"""
import os
import sys
import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "products/supply_chain_optimization/natural_gas_supply_chain_optimization/src"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s - %(message)s"
)

from products.supply_chain_optimization.sensitivity_analysis.parallel_executor import run_parameter_group
from products.supply_chain_optimization.sensitivity_analysis.result_collector import print_progress_summary

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Group A: NG价格敏感性")
    parser.add_argument("--workers", type=int, default=3, help="并行进程数（3个场景）")
    parser.add_argument("--threads", type=int, default=33, help="每进程Gurobi线程数")
    parser.add_argument("--time-limit", type=float, default=7200, help="时间限制（秒）")
    parser.add_argument("--mip-gap", type=float, default=0.01)
    parser.add_argument("--no-skip", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--scenario", type=str, default=None, help="指定单个场景")
    args = parser.parse_args()

    scenario_names = [args.scenario] if args.scenario else ["GTL-GH", "GTL", "GTL-BH"]

    print("=" * 70)
    print("Group A: 天然气价格敏感性分析")
    print(f"场景: {scenario_names}")
    print(f"NG价格: 2.0 ~ 8.0 元/m³ (9点)")
    print(f"总运行: {9 * len(scenario_names)} 次")
    print(f"并行进程: {args.workers}, 每进程线程: {args.threads}")
    print("=" * 70)

    results = run_parameter_group(
        param_name="ng_price",
        scenario_names=scenario_names,
        n_workers=args.workers,
        gurobi_threads=args.threads,
        time_limit_s=args.time_limit,
        mip_gap=args.mip_gap,
        skip_existing=not args.no_skip,
        dry_run=args.dry_run,
    )

    n_ok = sum(1 for r in results if r.get("status") in ("optimal", "feasible"))
    print(f"\nGroup A 完成: {n_ok}/{len(results)} 成功")
    print_progress_summary()
