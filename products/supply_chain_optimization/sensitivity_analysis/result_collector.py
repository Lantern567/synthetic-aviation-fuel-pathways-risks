"""
结果收集器 - 汇总所有JSON结果为CSV，并提供统计摘要。
"""
import os
import sys
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

import pandas as pd
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from products.supply_chain_optimization.sensitivity_analysis.scenario_registry import (
    SCENARIOS, get_all_run_tasks
)
from products.supply_chain_optimization.sensitivity_analysis.sensitivity_runner import (
    RESULTS_DIR, result_exists, load_existing_result, make_run_id
)

logger = logging.getLogger(__name__)


def collect_all_results(
    include_errors: bool = False,
    results_dir: Optional[Path] = None,
) -> pd.DataFrame:
    """
    扫描results/目录，将所有JSON结果合并为DataFrame。

    Returns:
        DataFrame，每行一次运行，关键列：
        scenario_name, param_name, param_value, status,
        lco_per_kg, lco_excluding_shortage_per_kg, annual_production_kg,
        optimization_time_s
    """
    rdir = results_dir or RESULTS_DIR
    json_files = sorted(rdir.glob("*.json"))

    rows = []
    for jf in json_files:
        if jf.name.startswith("parallel_run_"):
            continue  # 跳过日志文件
        try:
            with open(jf, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not include_errors and data.get("status") == "error":
                continue
            rows.append(data)
        except Exception as e:
            logger.warning(f"读取 {jf} 失败: {e}")

    if not rows:
        logger.warning("未找到任何结果文件")
        return pd.DataFrame()

    df = pd.DataFrame(rows)

    # 展开二维扫描的 param_value（将(e, c)元组转为两列）
    mask_2d = df["param_name"] == "electricity_capex_grid"
    if mask_2d.any():
        df.loc[mask_2d, "electricity_price"] = df.loc[mask_2d, "param_value"].apply(
            lambda x: x[0] if isinstance(x, (list, tuple)) else None
        )
        df.loc[mask_2d, "electrolyzer_capex"] = df.loc[mask_2d, "param_value"].apply(
            lambda x: x[1] if isinstance(x, (list, tuple)) else None
        )

    return df


def get_completion_status() -> pd.DataFrame:
    """
    检查每个运行任务的完成情况。

    Returns:
        DataFrame，显示每个任务的状态（completed/missing/error）
    """
    tasks = get_all_run_tasks()
    rows = []
    for task in tasks:
        run_id = make_run_id(task["scenario_name"], task["param_name"], task["param_value"])
        if result_exists(run_id):
            data = load_existing_result(run_id)
            status = data.get("status", "unknown")
        else:
            status = "missing"
        rows.append({
            "scenario_name": task["scenario_name"],
            "param_name": task["param_name"],
            "param_value": str(task["param_value"]),
            "run_id": run_id,
            "status": status,
        })
    return pd.DataFrame(rows)


def print_progress_summary():
    """打印完成进度摘要"""
    df = get_completion_status()
    total = len(df)
    completed = (df["status"].isin(["optimal", "feasible"])).sum()
    missing = (df["status"] == "missing").sum()
    errors = (df["status"] == "error").sum()

    print("=" * 60)
    print(f"敏感性分析进度报告 ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
    print("=" * 60)
    print(f"总计: {total} 次运行")
    print(f"已完成: {completed} ({100*completed/total:.1f}%)")
    print(f"缺失:   {missing} ({100*missing/total:.1f}%)")
    print(f"错误:   {errors} ({100*errors/total:.1f}%)")
    print()

    # 按参数分组
    for param_name in df["param_name"].unique():
        sub = df[df["param_name"] == param_name]
        sub_done = sub["status"].isin(["optimal", "feasible"]).sum()
        print(f"  {param_name:30s}: {sub_done:3d}/{len(sub):3d}")

    print("=" * 60)


def export_to_csv(output_path: Optional[str] = None) -> str:
    """将所有结果导出为CSV文件"""
    df = collect_all_results(include_errors=False)
    if df.empty:
        logger.warning("无结果可导出")
        return ""

    if output_path is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = str(RESULTS_DIR / f"sensitivity_results_all_{ts}.csv")

    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    logger.info(f"结果已导出: {output_path} ({len(df)} 行)")
    return output_path


def get_ng_price_sensitivity() -> pd.DataFrame:
    """提取NG价格敏感性结果"""
    df = collect_all_results()
    if df.empty:
        return df
    return df[df["param_name"] == "ng_price"].sort_values(
        ["scenario_name", "param_value"]
    )


def get_coal_price_sensitivity() -> pd.DataFrame:
    """提取煤价敏感性结果"""
    df = collect_all_results()
    if df.empty:
        return df
    return df[df["param_name"] == "coal_price"].sort_values(
        ["scenario_name", "param_value"]
    )


def get_bh_capex_sensitivity() -> pd.DataFrame:
    """提取副产氢CAPEX敏感性结果"""
    df = collect_all_results()
    if df.empty:
        return df
    return df[df["param_name"] == "bh_capex"].sort_values(
        ["scenario_name", "param_value"]
    )


def get_electricity_capex_grid() -> pd.DataFrame:
    """提取电价×CAPEX二维扫描结果"""
    df = collect_all_results()
    if df.empty:
        return df
    return df[df["param_name"] == "electricity_capex_grid"].sort_values(
        ["scenario_name", "electricity_price", "electrolyzer_capex"]
    )


def get_dac_cost_sensitivity() -> pd.DataFrame:
    """提取DAC成本敏感性结果"""
    df = collect_all_results()
    if df.empty:
        return df
    return df[df["param_name"] == "dac_cost"].sort_values(
        ["scenario_name", "param_value"]
    )


if __name__ == "__main__":
    print_progress_summary()
    path = export_to_csv()
    if path:
        print(f"\n结果已保存到: {path}")
