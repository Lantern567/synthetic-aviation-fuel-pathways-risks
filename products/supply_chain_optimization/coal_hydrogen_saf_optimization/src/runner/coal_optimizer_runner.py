"""
Lightweight runner for the coal + green hydrogen SAF optimization pathway.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Sequence

import psutil
import yaml

from ..core.coal_hydrogen_optimization_model import CoalHydrogenSAFOptimizer

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = (
    PROJECT_ROOT / "data" / "CoalHydrogenSAFOptimizer_config.yaml"
)


class CoalSAFOptimizerRunner:
    """Wrapper around :class:`CoalHydrogenSAFOptimizer` for CLI and scripting use."""

    def __init__(
        self,
        config_path: Optional[Path] = None,
        time_horizon_weeks: Optional[int] = None,  # None时从配置文件读取
        threads: Optional[int] = None,
        time_limit: int = 10800,  # 3小时
        mip_gap: float = 0.01,
        results_dir: Optional[Path] = None,
        log_level: str = "INFO",
    ) -> None:
        self.config_path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
        self._time_horizon_weeks_override = time_horizon_weeks  # 保存用户覆盖值(可能为None)
        self.threads = threads if threads is not None else 192  # 默认192线程避免内存溢出
        self.time_limit = time_limit
        self.mip_gap = mip_gap
        self.results_dir = Path(results_dir) if results_dir else PROJECT_ROOT / "results"

        self.logger = logging.getLogger(self.__class__.__name__)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                )
            )
            self.logger.addHandler(handler)
        self.logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        with self.config_path.open("r", encoding="utf-8") as stream:
            self.config: Dict[str, Any] = yaml.safe_load(stream)

        self.logger.info("Coal SAF optimizer configured with %s", self.config_path)

    @property
    def time_horizon_weeks(self) -> int:
        """获取时间范围(周)：优先使用覆盖值，否则从配置读取"""
        if self._time_horizon_weeks_override is not None:
            return max(1, int(self._time_horizon_weeks_override))
        basic = self.config.get("basic_parameters", {})
        return max(1, int(basic.get("time_horizon_weeks", 4)))

    def _build_default_demand_profile(self) -> List[float]:
        basic = self.config.get("basic_parameters", {})
        operational = self.config.get("operational_parameters", {})

        hours_per_week = int(basic.get("hours_per_week", 168))
        total_hours = hours_per_week * self.time_horizon_weeks
        default_demand = float(
            operational.get("default_coal_saf_demand_kg_per_hour", 0.0)
        )
        if total_hours <= 0:
            total_hours = 1
        profile = [default_demand for _ in range(total_hours)]
        self.logger.debug(
            "Generated default demand profile: %d hours @ %.2f kg/h",
            total_hours,
            default_demand,
        )
        return profile

    def _solver_parameters(self) -> Dict[str, Any]:
        params = {
            "TimeLimit": self.time_limit,
            "MIPGap": self.mip_gap,
            "NodefileStart": 100,  # 内存使用超过100GB时，将节点数据写入磁盘
            "NodefileDir": "/tmp/gurobi_nodes",  # 节点文件存储目录
        }
        if self.threads is not None:
            params["Threads"] = self.threads
        return params

    def run(
        self, demand_profile: Optional[Sequence[float]] = None
    ) -> Dict[str, Any]:
        """
        Execute the coal-based optimization workflow.

        Parameters
        ----------
        demand_profile:
            Optional iterable of hourly SAF demand in kilograms.
            When omitted, the default demand defined in the configuration file is used.
        """
        profile = (
            list(demand_profile)
            if demand_profile is not None
            else self._build_default_demand_profile()
        )

        # 只有显式指定time_horizon_weeks时才覆盖配置文件
        override_params = {}
        if self._time_horizon_weeks_override is not None:
            override_params['time_horizon_weeks'] = self.time_horizon_weeks
            self.logger.info(f"使用命令行指定的时间范围: {self.time_horizon_weeks}周")
        else:
            self.logger.info(f"使用配置文件的时间范围: {self.time_horizon_weeks}周")

        optimizer = CoalHydrogenSAFOptimizer(
            config_path=str(self.config_path),
            **override_params
        )
        optimizer.build_model(profile)

        for param, value in self._solver_parameters().items():
            optimizer.model.setParam(param, value)
        optimizer.model.update()

        start_time = time.time()
        result = optimizer.solve(time_limit=self.time_limit)
        solve_time = time.time() - start_time

        status = optimizer.model.Status
        objective = optimizer.model.ObjVal if status == 2 else None
        mip_gap = optimizer.model.MIPGap if status == 2 else None
        node_count = getattr(optimizer.model, "NodeCount", None)

        peak_memory_mb = psutil.Process().memory_info().rss / (1024**2)

        summary = {
            "status_code": status,
            "objective_value": objective,
            "coal_purchase_profile_kg": result.coal_purchase,
            "saf_production_profile_kg": result.saf_production,
            "co2_inventory_profile_kg": result.co2_inventory,
            "mip_gap": mip_gap,
            "node_count": node_count,
            "solve_time_s": solve_time,
            "peak_memory_mb": peak_memory_mb,
        }

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output_dir = self.results_dir / "coal_route"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"coal_optimizer_results_{timestamp}.json"
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(summary, handle, ensure_ascii=False, indent=2)

        self.logger.info("Coal SAF optimization completed: %s", output_path)

        return {
            "objective_value": objective,
            "solve_time": solve_time,
            "gap": mip_gap,
            "node_count": node_count,
            "results": summary,
            "results_path": str(output_path),
        }
