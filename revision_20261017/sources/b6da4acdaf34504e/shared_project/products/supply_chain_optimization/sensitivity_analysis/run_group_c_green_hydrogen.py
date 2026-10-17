"""
Group C: 绿氢路径敏感性分析 (GreenHydrogenSupplyChainOptimizer)
覆盖场景: CCU-GH-MTJ, CCU-GH-FT, CCU-BH-MTJ, CCU-BH-FT

电价×电解槽CAPEX二维扫描 (CCU-GH-MTJ, CCU-GH-FT):
  5 × 5 = 25 组合 × 2 场景 = 50 次

副产氢CAPEX扫描 (CCU-BH-MTJ, CCU-BH-FT):
  7 点 × 2 场景 = 14 次

合计: 64 次
"""
import os
import sys
import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/src"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s - %(message)s"
)

from products.supply_chain_optimization.sensitivity_analysis.parallel_executor import run_parameter_group
from products.supply_chain_optimization.sensitivity_analysis.result_collector import print_progress_summary

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Group C: 绿氢敏感性分析")
    parser.add_argument("--workers", type=int, default=4, help="并行进程数")
    parser.add_argument("--threads", type=int, default=25, help="每进程Gurobi线程数")
    parser.add_argument("--time-limit", type=float, default=7200)
    parser.add_argument("--mip-gap", type=float, default=0.01)
    parser.add_argument("--no-skip", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--only-gh", action="store_true", help="只运行GH(电价×CAPEX)扫描")
    parser.add_argument("--only-bh", action="store_true", help="只运行BH CAPEX扫描")
    args = parser.parse_args()

    print("=" * 70)
    print("Group C: 绿氢路径敏感性分析")
    print("=" * 70)

    all_results = []

    # CCU-GH 电价×电解槽CAPEX 二维扫描
    if not args.only_bh:
        print(f"\n[CCU-GH 电价×CAPEX扫描] 5×5=25组合 × 2场景 = 50次")
        results_gh = run_parameter_group(
            param_name="electricity_capex_grid",
            scenario_names=["CCU-GH-MTJ", "CCU-GH-FT"],
            n_workers=args.workers,
            gurobi_threads=args.threads,
            time_limit_s=args.time_limit,
            mip_gap=args.mip_gap,
            skip_existing=not args.no_skip,
            dry_run=args.dry_run,
        )
        all_results.extend(results_gh)
        n_ok = sum(1 for r in results_gh if r.get("status") in ("optimal", "feasible"))
        print(f"CCU-GH 扫描完成: {n_ok}/{len(results_gh)} 成功")

    # CCU-BH 副产氢CAPEX扫描
    if not args.only_gh:
        print(f"\n[CCU-BH CAPEX扫描] 7点 × 2场景 = 14次")
        results_bh = run_parameter_group(
            param_name="bh_capex",
            scenario_names=["CCU-BH-MTJ", "CCU-BH-FT"],
            n_workers=min(args.workers, 2),
            gurobi_threads=min(args.threads * 2, 50),
            time_limit_s=args.time_limit,
            mip_gap=args.mip_gap,
            skip_existing=not args.no_skip,
            dry_run=args.dry_run,
        )
        all_results.extend(results_bh)
        n_ok = sum(1 for r in results_bh if r.get("status") in ("optimal", "feasible"))
        print(f"CCU-BH CAPEX扫描完成: {n_ok}/{len(results_bh)} 成功")

    print(f"\nGroup C 总计: {sum(1 for r in all_results if r.get('status') in ('optimal','feasible'))}/{len(all_results)} 成功")
    print_progress_summary()
