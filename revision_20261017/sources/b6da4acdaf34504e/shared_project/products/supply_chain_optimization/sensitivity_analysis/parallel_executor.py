"""
并行执行器 - 使用 multiprocessing 以 4 进程并行运行敏感性分析任务。
每个进程运行一个 (场景, 参数值) 组合，共占用 4×25=100 个 Gurobi 线程。
"""
import os
import sys
import logging
import multiprocessing as mp
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from products.supply_chain_optimization.sensitivity_analysis.scenario_registry import (
    SCENARIOS, get_all_run_tasks, count_total_runs
)
from products.supply_chain_optimization.sensitivity_analysis.sensitivity_runner import (
    run_single, result_exists, make_run_id
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(processName)s] %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            Path(__file__).parent / "results" / f"parallel_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
            encoding="utf-8"
        )
    ]
)
logger = logging.getLogger(__name__)

# 并行进程数（每进程25线程 × 4进程 = 100线程）
N_WORKERS = 4
GUROBI_THREADS_PER_WORKER = 25


def _worker_fn(task_args: Tuple) -> Dict:
    """
    子进程工作函数。
    task_args: (scenario_name, param_name, param_value, gurobi_threads, time_limit_s, mip_gap)
    """
    scenario_name, param_name, param_value, gurobi_threads, time_limit_s, mip_gap = task_args
    scenario_config = SCENARIOS[scenario_name]
    return run_single(
        scenario_name=scenario_name,
        param_name=param_name,
        param_value=param_value,
        scenario_config=scenario_config,
        gurobi_threads=gurobi_threads,
        time_limit_s=time_limit_s,
        mip_gap=mip_gap,
    )


def run_parameter_group(
    param_name: str,
    scenario_names: Optional[List[str]] = None,
    n_workers: int = N_WORKERS,
    gurobi_threads: int = GUROBI_THREADS_PER_WORKER,
    time_limit_s: float = 7200.0,
    mip_gap: float = 0.01,
    skip_existing: bool = True,
    dry_run: bool = False,
) -> List[Dict]:
    """
    并行运行指定参数的所有场景扫描。

    Args:
        param_name: 参数名（如 "ng_price", "bh_capex", "electricity_capex_grid"...）
        scenario_names: 限定场景列表（None = 全部有该参数的场景）
        n_workers: 并行进程数
        gurobi_threads: 每进程Gurobi线程数
        time_limit_s: Gurobi时间限制
        mip_gap: MIP间隙
        skip_existing: 如结果文件已存在则跳过
        dry_run: 仅测试框架，不实际求解

    Returns:
        所有运行结果列表
    """
    # 收集任务
    tasks_args = []
    for sc_name, sc_config in SCENARIOS.items():
        if scenario_names and sc_name not in scenario_names:
            continue
        if param_name not in sc_config["sensitivity_params"]:
            continue
        for val in sc_config["sensitivity_params"][param_name]["values"]:
            run_id = make_run_id(sc_name, param_name, val)
            if skip_existing and result_exists(run_id):
                logger.info(f"[skip] {run_id} 已存在，跳过")
                continue
            tasks_args.append((sc_name, param_name, val, gurobi_threads, time_limit_s, mip_gap))

    if not tasks_args:
        logger.info(f"[{param_name}] 无新任务（全部已完成或无匹配场景）")
        return []

    logger.info(f"[{param_name}] 共 {len(tasks_args)} 个任务，使用 {n_workers} 个并行进程")
    for t in tasks_args:
        logger.info(f"  - {t[0]} / {t[1]} / {t[2]}")

    if dry_run:
        logger.info("[dry_run] 不实际运行，返回空结果")
        return [{"run_id": make_run_id(t[0], t[1], t[2]), "status": "dry_run"} for t in tasks_args]

    results = []
    # 确保results目录存在（在子进程创建FileHandler前）
    (Path(__file__).parent / "results").mkdir(parents=True, exist_ok=True)

    # 串行运行时使用n_workers=1，并行时使用Pool
    if n_workers == 1:
        for task_args in tasks_args:
            result = _worker_fn(task_args)
            results.append(result)
    else:
        with mp.Pool(processes=n_workers) as pool:
            results = pool.map(_worker_fn, tasks_args)

    # 统计
    n_ok = sum(1 for r in results if r.get("status") in ("optimal", "feasible"))
    n_err = sum(1 for r in results if r.get("status") == "error")
    logger.info(f"[{param_name}] 完成: {n_ok}/{len(results)} 成功, {n_err} 失败")
    return results


def run_all(
    n_workers: int = N_WORKERS,
    gurobi_threads: int = GUROBI_THREADS_PER_WORKER,
    time_limit_s: float = 7200.0,
    mip_gap: float = 0.01,
    skip_existing: bool = True,
    param_filter: Optional[List[str]] = None,
    scenario_filter: Optional[List[str]] = None,
    dry_run: bool = False,
) -> List[Dict]:
    """
    运行全部223次敏感性分析。

    Args:
        param_filter: 只运行指定参数类型（None = 全部）
        scenario_filter: 只运行指定场景（None = 全部）
        其他参数同 run_parameter_group
    """
    logger.info("=" * 80)
    logger.info("开始全量敏感性分析")
    logger.info(f"总任务数: {count_total_runs()}")
    logger.info(f"并行进程: {n_workers}, 每进程线程: {gurobi_threads}")
    logger.info("=" * 80)

    all_param_names = set()
    for sc_config in SCENARIOS.values():
        all_param_names.update(sc_config["sensitivity_params"].keys())

    if param_filter:
        all_param_names = {p for p in all_param_names if p in param_filter}

    all_results = []
    for param_name in sorted(all_param_names):
        logger.info(f"\n{'='*40}")
        logger.info(f"参数组: {param_name}")
        results = run_parameter_group(
            param_name=param_name,
            scenario_names=scenario_filter,
            n_workers=n_workers,
            gurobi_threads=gurobi_threads,
            time_limit_s=time_limit_s,
            mip_gap=mip_gap,
            skip_existing=skip_existing,
            dry_run=dry_run,
        )
        all_results.extend(results)

    logger.info("\n" + "=" * 80)
    logger.info(f"全量分析完成: 共 {len(all_results)} 个任务")
    return all_results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SAF敏感性分析并行执行器")
    parser.add_argument("--param", type=str, default=None, help="只运行指定参数 (如 ng_price)")
    parser.add_argument("--scenario", type=str, default=None, help="只运行指定场景 (如 GTL-BH)")
    parser.add_argument("--workers", type=int, default=N_WORKERS, help=f"并行进程数 (默认: {N_WORKERS})")
    parser.add_argument("--threads", type=int, default=GUROBI_THREADS_PER_WORKER, help="每进程Gurobi线程数")
    parser.add_argument("--time-limit", type=float, default=7200.0, help="Gurobi时间限制（秒）")
    parser.add_argument("--mip-gap", type=float, default=0.01, help="MIP间隙")
    parser.add_argument("--no-skip", action="store_true", help="不跳过已有结果，重新运行")
    parser.add_argument("--dry-run", action="store_true", help="测试运行，不调用Gurobi")
    args = parser.parse_args()

    param_filter = [args.param] if args.param else None
    scenario_filter = [args.scenario] if args.scenario else None

    run_all(
        n_workers=args.workers,
        gurobi_threads=args.threads,
        time_limit_s=args.time_limit,
        mip_gap=args.mip_gap,
        skip_existing=not args.no_skip,
        param_filter=param_filter,
        scenario_filter=scenario_filter,
        dry_run=args.dry_run,
    )
