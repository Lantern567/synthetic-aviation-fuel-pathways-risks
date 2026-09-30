"""
CCU-BH 和 DAC-BH bh_capex 敏感性分析重跑脚本
修复了副产氢PSA CAPEX硬编码bug后，重新运行4个场景共28次
"""
import os
import sys
import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))
for _d in [
    PROJECT_ROOT / "products/supply_chain_optimization/green_hydrogen_supply_chain_optimization",
    PROJECT_ROOT / "products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization",
]:
    if str(_d) not in sys.path:
        sys.path.insert(0, str(_d))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s - %(message)s"
)

from products.supply_chain_optimization.sensitivity_analysis.parallel_executor import run_parameter_group
from products.supply_chain_optimization.sensitivity_analysis.result_collector import print_progress_summary

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="重跑 CCU-BH/DAC-BH BH CAPEX 敏感性分析")
    parser.add_argument("--workers", type=int, default=2, help="并行进程数")
    parser.add_argument("--threads", type=int, default=50, help="每进程Gurobi线程数")
    parser.add_argument("--time-limit", type=float, default=7200)
    parser.add_argument("--mip-gap", type=float, default=0.01)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("=" * 70)
    print("CCU-BH / DAC-BH BH CAPEX 敏感性分析重跑（修复硬编码bug后）")
    print("=" * 70)

    all_results = []

    # CCU-BH (7点 × 2场景 = 14次)
    print(f"\n[CCU-BH CAPEX扫描] 7点 × 2场景 = 14次")
    results_ccu_bh = run_parameter_group(
        param_name="bh_capex",
        scenario_names=["CCU-BH-MTJ", "CCU-BH-FT"],
        n_workers=args.workers,
        gurobi_threads=args.threads,
        time_limit_s=args.time_limit,
        mip_gap=args.mip_gap,
        skip_existing=False,  # 强制重跑
        dry_run=args.dry_run,
    )
    all_results.extend(results_ccu_bh)
    n_ok = sum(1 for r in results_ccu_bh if r.get("status") in ("optimal", "feasible"))
    print(f"CCU-BH 完成: {n_ok}/{len(results_ccu_bh)} 成功")

    # DAC-BH (7点 × 2场景 = 14次)
    print(f"\n[DAC-BH CAPEX扫描] 7点 × 2场景 = 14次")
    results_dac_bh = run_parameter_group(
        param_name="bh_capex",
        scenario_names=["DAC-BH-MTJ", "DAC-BH-FT"],
        n_workers=args.workers,
        gurobi_threads=args.threads,
        time_limit_s=args.time_limit,
        mip_gap=args.mip_gap,
        skip_existing=False,
        dry_run=args.dry_run,
    )
    all_results.extend(results_dac_bh)
    n_ok = sum(1 for r in results_dac_bh if r.get("status") in ("optimal", "feasible"))
    print(f"DAC-BH 完成: {n_ok}/{len(results_dac_bh)} 成功")

    total_ok = sum(1 for r in all_results if r.get("status") in ("optimal", "feasible"))
    print(f"\n总计: {total_ok}/{len(all_results)} 成功")
    print_progress_summary()
