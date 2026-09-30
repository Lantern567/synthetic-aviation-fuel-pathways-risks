"""
Group D: DAC路径敏感性分析 (DACHydrogenSAFOptimizer)
覆盖场景: DAC-GH-MTJ, DAC-GH-FT, DAC-BH-MTJ, DAC-BH-FT

DAC成本扫描 (全部4场景):
  8 点 × 4 场景 = 32 次

电价×电解槽CAPEX扫描 (DAC-GH-MTJ, DAC-GH-FT):
  25 组合 × 2 场景 = 50 次

副产氢CAPEX扫描 (DAC-BH-MTJ, DAC-BH-FT):
  7 点 × 2 场景 = 14 次（但BH CAPEX+DAC成本不交叉，分开运行）

注：总104次（含交叉参数分组）
"""
import os
import sys
import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/src"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s - %(message)s"
)

from products.supply_chain_optimization.sensitivity_analysis.parallel_executor import run_parameter_group
from products.supply_chain_optimization.sensitivity_analysis.result_collector import print_progress_summary

DAC_SCENARIOS = ["DAC-GH-MTJ", "DAC-GH-FT", "DAC-BH-MTJ", "DAC-BH-FT"]
DAC_GH_SCENARIOS = ["DAC-GH-MTJ", "DAC-GH-FT"]
DAC_BH_SCENARIOS = ["DAC-BH-MTJ", "DAC-BH-FT"]

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Group D: DAC路径敏感性分析")
    parser.add_argument("--workers", type=int, default=4, help="并行进程数")
    parser.add_argument("--threads", type=int, default=25, help="每进程Gurobi线程数")
    parser.add_argument("--time-limit", type=float, default=7200)
    parser.add_argument("--mip-gap", type=float, default=0.01)
    parser.add_argument("--no-skip", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--only-dac-cost", action="store_true", help="只运行DAC成本扫描")
    parser.add_argument("--only-elec-capex", action="store_true", help="只运行电价×CAPEX扫描")
    parser.add_argument("--only-bh-capex", action="store_true", help="只运行BH CAPEX扫描")
    args = parser.parse_args()

    print("=" * 70)
    print("Group D: DAC路径敏感性分析")
    print("=" * 70)

    all_results = []

    # DAC成本扫描（全部4个场景）
    if not args.only_elec_capex and not args.only_bh_capex:
        print(f"\n[DAC成本扫描] 4500~300 元/ton (8点) × 4场景 = 32次")
        results_dac = run_parameter_group(
            param_name="dac_cost",
            scenario_names=DAC_SCENARIOS,
            n_workers=args.workers,
            gurobi_threads=args.threads,
            time_limit_s=args.time_limit,
            mip_gap=args.mip_gap,
            skip_existing=not args.no_skip,
            dry_run=args.dry_run,
        )
        all_results.extend(results_dac)
        n_ok = sum(1 for r in results_dac if r.get("status") in ("optimal", "feasible"))
        print(f"DAC成本扫描完成: {n_ok}/{len(results_dac)} 成功")

    # DAC-GH 电价×电解槽CAPEX二维扫描
    if not args.only_dac_cost and not args.only_bh_capex:
        print(f"\n[DAC-GH 电价×CAPEX扫描] 5×5=25组合 × 2场景 = 50次")
        results_gh = run_parameter_group(
            param_name="electricity_capex_grid",
            scenario_names=DAC_GH_SCENARIOS,
            n_workers=args.workers,
            gurobi_threads=args.threads,
            time_limit_s=args.time_limit,
            mip_gap=args.mip_gap,
            skip_existing=not args.no_skip,
            dry_run=args.dry_run,
        )
        all_results.extend(results_gh)
        n_ok = sum(1 for r in results_gh if r.get("status") in ("optimal", "feasible"))
        print(f"DAC-GH 电价×CAPEX扫描完成: {n_ok}/{len(results_gh)} 成功")

    # DAC-BH 副产氢CAPEX扫描
    if not args.only_dac_cost and not args.only_elec_capex:
        print(f"\n[DAC-BH CAPEX扫描] 7点 × 2场景 = 14次")
        results_bh = run_parameter_group(
            param_name="bh_capex",
            scenario_names=DAC_BH_SCENARIOS,
            n_workers=min(args.workers, 2),
            gurobi_threads=min(args.threads * 2, 50),
            time_limit_s=args.time_limit,
            mip_gap=args.mip_gap,
            skip_existing=not args.no_skip,
            dry_run=args.dry_run,
        )
        all_results.extend(results_bh)
        n_ok = sum(1 for r in results_bh if r.get("status") in ("optimal", "feasible"))
        print(f"DAC-BH CAPEX扫描完成: {n_ok}/{len(results_bh)} 成功")

    print(f"\nGroup D 总计: {sum(1 for r in all_results if r.get('status') in ('optimal','feasible'))}/{len(all_results)} 成功")
    print_progress_summary()
