"""
Group B: 煤炭价格敏感性分析
覆盖场景: CTL, CTL-BH
煤价范围: 280 ~ 840 元/吨 (7个点)
总运行数: 7 × 2 = 14 次

副产氢CAPEX敏感性 (CTL-BH):
CAPEX范围: 140,000 ~ 400,000 元/(kg/h) (7个点) × 1场景 = 7 次
(GTL-BH的BH CAPEX已在Group A中处理)
"""
import os
import sys
import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "products/supply_chain_optimization/coal_hydrogen_saf_optimization/src"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s - %(message)s"
)

from products.supply_chain_optimization.sensitivity_analysis.parallel_executor import run_parameter_group
from products.supply_chain_optimization.sensitivity_analysis.result_collector import print_progress_summary

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Group B: 煤价 + CTL-BH CAPEX敏感性")
    parser.add_argument("--workers", type=int, default=2, help="并行进程数")
    parser.add_argument("--threads", type=int, default=50, help="每进程Gurobi线程数")
    parser.add_argument("--time-limit", type=float, default=7200)
    parser.add_argument("--mip-gap", type=float, default=0.01)
    parser.add_argument("--no-skip", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--only-coal", action="store_true", help="只运行煤价扫描")
    parser.add_argument("--only-bh-capex", action="store_true", help="只运行CTL-BH CAPEX扫描")
    args = parser.parse_args()

    print("=" * 70)
    print("Group B: 煤价 + CTL-BH副产氢CAPEX敏感性分析")
    print("=" * 70)

    all_results = []

    if not args.only_bh_capex:
        print(f"\n[煤价扫描] 280~840 元/吨 (7点) × 2场景 = 14次")
        results_coal = run_parameter_group(
            param_name="coal_price",
            scenario_names=["CTL", "CTL-BH"],
            n_workers=args.workers,
            gurobi_threads=args.threads,
            time_limit_s=args.time_limit,
            mip_gap=args.mip_gap,
            skip_existing=not args.no_skip,
            dry_run=args.dry_run,
        )
        all_results.extend(results_coal)
        n_ok = sum(1 for r in results_coal if r.get("status") in ("optimal", "feasible"))
        print(f"煤价扫描完成: {n_ok}/{len(results_coal)} 成功")

    if not args.only_coal:
        print(f"\n[CTL-BH副产氢CAPEX扫描] 140k~400k 元/(kg/h) (7点) × 1场景 = 7次")
        results_bh = run_parameter_group(
            param_name="bh_capex",
            scenario_names=["CTL-BH"],
            n_workers=1,  # 只有1个场景，串行即可
            gurobi_threads=min(args.threads * args.workers, 100),
            time_limit_s=args.time_limit,
            mip_gap=args.mip_gap,
            skip_existing=not args.no_skip,
            dry_run=args.dry_run,
        )
        all_results.extend(results_bh)
        n_ok = sum(1 for r in results_bh if r.get("status") in ("optimal", "feasible"))
        print(f"CTL-BH CAPEX扫描完成: {n_ok}/{len(results_bh)} 成功")

    print(f"\nGroup B 总计: {sum(1 for r in all_results if r.get('status') in ('optimal','feasible'))}/{len(all_results)} 成功")
    print_progress_summary()
