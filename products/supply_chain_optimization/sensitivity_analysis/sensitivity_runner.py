"""
敏感性分析单次运行器 - 负责运行单个（场景, 参数值）组合并保存结果。
"""
import os
import sys
import json
import logging
import importlib
import traceback
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

# 确保项目根目录在路径中
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 各模型 src 父目录（用于解析内部 `from src.xxx` 相对导入）
_SRC_PARENT_DIRS = [
    PROJECT_ROOT / "products/supply_chain_optimization/green_hydrogen_supply_chain_optimization",
    PROJECT_ROOT / "products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization",
    PROJECT_ROOT / "products/supply_chain_optimization/coal_hydrogen_saf_optimization",
    PROJECT_ROOT / "products/supply_chain_optimization/natural_gas_supply_chain_optimization",
]
for _d in _SRC_PARENT_DIRS:
    if str(_d) not in sys.path:
        sys.path.insert(0, str(_d))

logger = logging.getLogger(__name__)

# 结果保存目录
RESULTS_DIR = Path(__file__).parent / "results"


def _load_optimizer_class(model_module: str, model_class: str):
    """动态加载优化器类"""
    mod = importlib.import_module(model_module)
    cls = getattr(mod, model_class)
    return cls


def _build_config_overrides(param_name: str, param_value: Any, param_config: Dict) -> Dict:
    """
    构建配置覆盖字典，支持：
    - 单键覆盖
    - 多键覆盖（GTL-BH的两个BH CAPEX键）
    - 二维扫描（electricity × capex）
    """
    overrides = {}

    if param_name == "electricity_capex_grid":
        # 二维扫描: param_value是(electricity_price, capex)元组
        elec_price, capex = param_value
        keys = param_config["config_keys"]
        overrides[keys["electricity"]] = elec_price
        overrides[keys["capex"]] = capex

    elif isinstance(param_config.get("config_key"), list):
        # 多键覆盖（如GTL-BH的钢铁+炼油CAPEX）
        keys = param_config["config_key"]
        scale_factors = param_config.get("scale_factors", [1.0] * len(keys))
        for key, scale in zip(keys, scale_factors):
            overrides[key] = param_value * scale

    else:
        # 单键覆盖
        overrides[param_config["config_key"]] = param_value

    return overrides


def run_single(
    scenario_name: str,
    param_name: str,
    param_value: Any,
    scenario_config: Dict,
    gurobi_threads: int = 25,
    time_limit_s: float = 7200.0,
    mip_gap: float = 0.01,
    dry_run: bool = False,
) -> Dict:
    """
    运行单个敏感性分析点。

    Args:
        scenario_name: 场景名，如 "GTL-BH"
        param_name: 参数名，如 "bh_capex"
        param_value: 参数值，或 (electricity, capex) 元组
        scenario_config: 场景配置字典（来自 scenario_registry.SCENARIOS）
        gurobi_threads: Gurobi求解线程数
        time_limit_s: Gurobi时间限制（秒）
        mip_gap: MIP最优差距
        dry_run: 如为True则跳过实际求解，用于测试框架

    Returns:
        result dict with keys:
          scenario_name, param_name, param_value,
          status, lco_per_kg, annual_production_kg,
          total_cost_excluding_shortage, error (if any)
    """
    param_config = scenario_config["sensitivity_params"][param_name]
    overrides = _build_config_overrides(param_name, param_value, param_config)

    # 构建运行标识符
    if isinstance(param_value, tuple):
        val_str = f"e{param_value[0]}_c{param_value[1]}"
    else:
        val_str = str(param_value)
    run_id = f"{scenario_name}__{param_name}__{val_str}"

    result = {
        "scenario_name": scenario_name,
        "param_name": param_name,
        "param_value": param_value,
        "run_id": run_id,
        "status": "not_started",
        "lco_per_kg": None,
        "lco_excluding_shortage_per_kg": None,
        "annual_production_kg": None,
        "total_cost_excluding_shortage": None,
        "optimization_time_s": None,
        "error": None,
        "timestamp": datetime.now().isoformat(),
    }

    if dry_run:
        logger.info(f"[dry_run] {run_id}: overrides={overrides}")
        result["status"] = "dry_run"
        return result

    try:
        logger.info(f"[{run_id}] 开始运行, overrides={overrides}")

        # 动态加载优化器类
        OptimizerClass = _load_optimizer_class(
            scenario_config["model_module"],
            scenario_config["model_class"]
        )

        # 构建额外模型参数
        extra_kwargs = dict(scenario_config.get("model_kwargs", {}))
        extra_kwargs.update(overrides)  # dot-notation overrides

        # 加入求解器参数（用dot-notation覆盖config['solver_parameters']）
        extra_kwargs["solver_parameters.TimeLimit"] = time_limit_s
        extra_kwargs["solver_parameters.MIPGap"] = mip_gap
        extra_kwargs["solver_parameters.Threads"] = gurobi_threads

        # 动态log_subdir，避免并行运行互相覆盖
        log_subdir = scenario_config.get("log_subdir", "sensitivity/unknown")
        log_subdir = f"{log_subdir}/{param_name}/{val_str}"
        if "log_subdir" in OptimizerClass.__init__.__code__.co_varnames:
            extra_kwargs["log_subdir"] = log_subdir

        # 初始化优化器
        optimizer = OptimizerClass(
            config_path=scenario_config["config_path"],
            **extra_kwargs
        )

        # 加载数据（必须在 set_ng_price_override 之前，否则 ng_pipeline_sources 为空）
        if hasattr(optimizer, "load_data_from_excel"):
            optimizer.load_data_from_excel(airport_excel_path=None)
        elif hasattr(optimizer, "load_data"):
            optimizer.load_data()

        # 对NG价格场景，额外强制覆盖管道价格（在数据加载之后，此时 ng_pipeline_sources 已填充）
        if param_config.get("use_ng_override"):
            if isinstance(param_value, tuple):
                ng_price = param_value[0]
            else:
                ng_price = param_value
            if hasattr(optimizer, "set_ng_price_override"):
                optimizer.set_ng_price_override(ng_price)

        # 构建模型
        optimizer.build_model()

        # 求解
        solution = optimizer.solve()

        opt_status = solution.get("optimization_status") if solution else None
        # Gurobi状态码: 2=OPTIMAL, 9=TIME_LIMIT(有可行解), 13=SUBOPTIMAL
        FEASIBLE_STATUSES = (2, 9, 13)
        if solution is None or opt_status not in FEASIBLE_STATUSES:
            result["status"] = f"no_solution_gurobi_{opt_status}" if solution else "no_solution"
            logger.warning(f"[{run_id}] 无可行解: status={result['status']}, opt_status={opt_status}")
        else:
            result["status"] = "optimal" if opt_status == 2 else "feasible"
            result["lco_per_kg"] = solution.get("lifecycle_levelized_cost_per_kg")
            result["lco_excluding_shortage_per_kg"] = solution.get(
                "lifecycle_levelized_cost_excluding_shortage_per_kg"
            )
            result["annual_production_kg"] = solution.get("annual_production_kg")
            result["total_cost_excluding_shortage"] = solution.get(
                "total_cost_excluding_shortage"
            )
            result["optimization_time_s"] = solution.get("optimization_time")
            logger.info(
                f"[{run_id}] 完成: LCO={result['lco_excluding_shortage_per_kg']:.2f} 元/kg"
                if result["lco_excluding_shortage_per_kg"] else f"[{run_id}] 完成，无LCO数据"
            )

    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        result["traceback"] = traceback.format_exc()
        logger.error(f"[{run_id}] 运行失败: {e}\n{traceback.format_exc()}")

    # 保存单次结果到文件
    _save_result(result)
    return result


def _save_result(result: Dict):
    """将单次运行结果保存为JSON文件"""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    run_id = result["run_id"]
    out_path = RESULTS_DIR / f"{run_id}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    logger.debug(f"结果已保存: {out_path}")


def load_existing_result(run_id: str) -> Optional[Dict]:
    """加载已存在的结果（用于跳过重复运行）"""
    out_path = RESULTS_DIR / f"{run_id}.json"
    if out_path.exists():
        with open(out_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def result_exists(run_id: str) -> bool:
    """检查运行结果是否已存在"""
    out_path = RESULTS_DIR / f"{run_id}.json"
    return out_path.exists() and out_path.stat().st_size > 0


def make_run_id(scenario_name: str, param_name: str, param_value: Any) -> str:
    """生成运行ID（与run_single保持一致）"""
    if isinstance(param_value, tuple):
        val_str = f"e{param_value[0]}_c{param_value[1]}"
    else:
        val_str = str(param_value)
    return f"{scenario_name}__{param_name}__{val_str}"
