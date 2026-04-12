"""
GTL-BH 副产氢PSA设备CAPEX敏感性分析
测试副产氢净化成本（钢铁厂/炼油厂废气PSA设备）对GTL-BH成本优势的影响。

CAPEX范围: 140,000 ~ 400,000 元/(kg H₂/hour)
  - 低端(140k): 技术优化/规模效应的乐观情形
  - 基准(280k/224k): 文献中值（钢铁/炼油分别）
  - 高端(400k): 高成本/小规模情形

总运行: 7 次
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
    parser = argparse.ArgumentParser(description="GTL-BH: 副产氢CAPEX敏感性")
    parser.add_argument("--threads", type=int, default=100, help="Gurobi线程数（串行，不并行）")
    parser.add_argument("--time-limit", type=float, default=7200)
    parser.add_argument("--mip-gap", type=float, default=0.01)
    parser.add_argument("--no-skip", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("=" * 70)
    print("GTL-BH: 副产氢PSA设备CAPEX敏感性分析")
    print("测量钢铁/炼油副产氢净化设备CAPEX对成本的影响")
    print("CAPEX范围: 140,000 ~ 400,000 元/(kg H₂/hour)")
    print("注: 炼油CAPEX = 钢铁CAPEX × (224k/280k = 0.8)")
    print("=" * 70)

    results = run_parameter_group(
        param_name="bh_capex",
        scenario_names=["GTL-BH"],
        n_workers=1,
        gurobi_threads=args.threads,
        time_limit_s=args.time_limit,
        mip_gap=args.mip_gap,
        skip_existing=not args.no_skip,
        dry_run=args.dry_run,
    )

    n_ok = sum(1 for r in results if r.get("status") in ("optimal", "feasible"))
    print(f"\nGTL-BH CAPEX扫描完成: {n_ok}/{len(results)} 成功")

    if results:
        print("\n结果摘要:")
        print(f"{'CAPEX(钢铁)':<20} {'LCO (元/kg)':<15} {'状态'}")
        print("-" * 45)
        for r in sorted(results, key=lambda x: x.get("param_value", 0) or 0):
            capex = r.get("param_value", "N/A")
            lco = r.get("lco_excluding_shortage_per_kg")
            status = r.get("status", "unknown")
            lco_str = f"{lco:.2f}" if isinstance(lco, (int, float)) and lco else "N/A"
            print(f"{capex:<20} {lco_str:<15} {status}")
