"""
Unified SAF Supply Chain Optimizer Runner

统一的SAF供应链优化运行接口,支持两步法、一步法和副产氢工艺路线。

主要功能:
1. 自动选择配置文件(两步法/一步法/副产氢一步法/副产氢两步法)
2. 灵活设置Gurobi求解器参数(Threads, MIPGap, TimeLimit)
3. 自动检测可用CPU核心数
4. 标准化的运行流程
5. 性能监控和报告生成

使用示例:
    >>> from src.runner import UnifiedSAFOptimizer
    >>>
    >>> # 运行两步法优化
    >>> optimizer = UnifiedSAFOptimizer(process_type='two_step', threads=64)
    >>> results = optimizer.run()
    >>>
    >>> # 运行一步法优化
    >>> optimizer = UnifiedSAFOptimizer(process_type='one_step', threads=64, mip_gap=0.03)
    >>> results = optimizer.run()
    >>>
    >>> # 运行副产氢一步法优化
    >>> optimizer = UnifiedSAFOptimizer(process_type='byproduct_one_step', threads=64)
    >>> results = optimizer.run()
    >>>
    >>> # 运行副产氢两步法优化
    >>> optimizer = UnifiedSAFOptimizer(process_type='byproduct_two_step', threads=64)
    >>> results = optimizer.run()

作者: Claude Code
创建日期: 2025-01-25
版本: 1.2.0
"""

import os
import sys
import time
import logging
import psutil
from pathlib import Path
from typing import Optional, Dict, Any, Union
from datetime import datetime

# 添加项目路径到Python路径
# __file__ 是 src/runner/unified_optimizer_runner.py
# parents[2] 是 dac_hydrogen_saf_supply_chain_optimization/
# parents[5] 是项目根目录 green_methanol_for_port_transportation-main/
project_root = Path(__file__).resolve().parents[2]  # dac_hydrogen_saf_supply_chain_optimization/
repo_root = Path(__file__).resolve().parents[5]     # green_methanol_for_port_transportation-main/

# 默认使用12个典型周的需求数据路径
DEFAULT_TWELVE_WEEK_DEMAND = repo_root / "products/aviation_fuel_analysis/resource_flight_data_process/results/typical_weeks_data/typical_12weeks_demand_20251129_163442.xlsx"

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 导入核心优化模型
# ===== v4.0变更: 导入DAC版本优化器 =====
from src.core.dac_hydrogen_optimization_model import DACHydrogenSAFOptimizer


class UnifiedSAFOptimizer:
    """
    统一SAF供应链优化器

    提供简洁的API来运行两步法、一步法、副产氢一步法和副产氢两步法工艺路线的供应链优化。

    Attributes:
        process_type (str): 工艺类型,'two_step'、'one_step'、'byproduct_one_step'或'byproduct_two_step'
        threads (int): CPU线程数
        time_limit (int): 求解时间限制(秒)
        mip_gap (float): MIP求解精度
        config_path (Path): 配置文件路径
        optimizer (DACHydrogenSAFOptimizer): 底层优化器实例（v4.0 DAC版本）
        logger (logging.Logger): 日志记录器
    """

    # ===== v4.0变更: 使用DAC版本配置文件 =====
    # v4.0.1: 配置文件移至shared/config目录
    # v4.1: 支持一步法和两步法不同配置文件
    # v4.2: 支持副产氢一步法和两步法配置
    CONFIG_MAPPING = {
        'two_step': 'shared/config/DACHydrogenSAFOptimizer_config_two_step.yaml',
        'one_step': 'shared/config/DACHydrogenSAFOptimizer_config.yaml',
        'byproduct_one_step': 'shared/data/DACByproductHydrogenSAFOptimizer_config_one_step.yaml',
        'byproduct_two_step': 'shared/data/DACByproductHydrogenSAFOptimizer_config_two_step.yaml',
    }

    # 结果输出目录映射（副产氢类型分一步法和两步法）
    RESULTS_DIR_MAPPING = {
        'two_step': 'two_step',
        'one_step': 'one_step',
        'byproduct_one_step': 'byproduct_hydrogen/one_step',
        'byproduct_two_step': 'byproduct_hydrogen/two_step',
    }

    def __init__(
        self,
        process_type: str = 'two_step',
        threads: Optional[int] = None,
        time_limit: int = 129600,  # 36小时
        mip_gap: float = 0.03,  # 从0.01改为0.03，降低求解精度但加快速度
        time_horizon_weeks: Optional[int] = None,
        parallel_workers: Optional[int] = None,
        osm_pbf_path: Optional[str] = None,
        airport_excel_path: Optional[Union[str, Path]] = None,
        results_dir: Optional[str] = None,
        config_path: Optional[str] = None,
        solver_params: Optional[Dict[str, Any]] = None,
        log_level: str = 'INFO',
    ):
        """
        初始化统一SAF优化器

        Args:
            process_type: 工艺类型
                - 'two_step': 两步法 (H₂+CO₂→甲醇→SAF)
                - 'one_step': 一步法 (H₂+CO₂→RWGS→FT→SAF)
                - 'byproduct_one_step': 副产氢一步法 (副产氢+CO₂→RWGS→FT→SAF)
                - 'byproduct_two_step': 副产氢两步法 (副产氢+CO₂→甲醇→SAF)
                - 'custom': 使用自定义配置文件(需提供config_path)
            threads: Gurobi求解器CPU线程数,None时自动检测(推荐cpu_count-2)
            time_limit: Gurobi求解时间限制(秒),默认129600(36小时)
            mip_gap: MIP相对最优间隙,默认0.03(3%)
            time_horizon_weeks: 优化时间范围(周数),默认None使用配置值(12个典型周)
            parallel_workers: 数据处理+距离计算并行workers数,None时自动检测(cpu_count)
            osm_pbf_path: OSM地图文件路径,None时使用默认
            airport_excel_path: 机场数据Excel路径,默认指向12个典型周的需求文件
            results_dir: 结果保存目录,None时使用默认
            config_path: 自定义配置文件路径(仅当process_type='custom'时使用)
            solver_params: 完整的求解器参数字典,会覆盖默认参数
            log_level: 日志级别,'DEBUG','INFO','WARNING','ERROR'

        Raises:
            ValueError: 如果process_type无效
            FileNotFoundError: 如果配置文件不存在
        """
        # 设置日志
        self._setup_logging(log_level)

        # 验证参数
        valid_process_types = ['two_step', 'one_step', 'byproduct_one_step', 'byproduct_two_step', 'custom']
        if process_type not in valid_process_types:
            raise ValueError(
                f"Invalid process_type: {process_type}. "
                f"Must be one of {valid_process_types}."
            )

        if process_type == 'custom' and config_path is None:
            raise ValueError("config_path must be provided when process_type='custom'")

        self.process_type = process_type
        self.time_horizon_weeks = time_horizon_weeks
        self.osm_pbf_path = osm_pbf_path
        self.airport_excel_path = Path(airport_excel_path) if airport_excel_path else DEFAULT_TWELVE_WEEK_DEMAND

        if results_dir is None:
            # 使用映射表确定输出目录（副产氢类型统一输出到byproduct_hydrogen）
            results_subdir = self.RESULTS_DIR_MAPPING.get(self.process_type, self.process_type)
            resolved_results_dir = project_root / 'results' / results_subdir
        else:
            resolved_results_dir = Path(results_dir)

        resolved_results_dir.mkdir(parents=True, exist_ok=True)
        self.results_dir = resolved_results_dir

        # 确定配置文件路径
        if process_type == 'custom':
            self.config_path = Path(config_path)
        else:
            # v4.0.1: 配置文件移至repo根目录的shared/config下
            self.config_path = repo_root / self.CONFIG_MAPPING[process_type]

        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        self.logger.info(f"Using configuration file: {self.config_path}")

        # CPU线程数设置
        self.threads = self._determine_threads(threads)
        self.parallel_workers = parallel_workers  # 保存parallel_workers参数
        self.time_limit = time_limit
        self.mip_gap = mip_gap

        # 求解器参数
        if solver_params is None:
            self.solver_params = {
                'Threads': self.threads,
                'TimeLimit': self.time_limit,
                'MIPGap': self.mip_gap,
            }
        else:
            # 用户提供完整参数字典
            self.solver_params = solver_params
            # 确保关键参数存在
            self.solver_params.setdefault('Threads', self.threads)
            self.solver_params.setdefault('TimeLimit', self.time_limit)
            self.solver_params.setdefault('MIPGap', self.mip_gap)

        # 性能监控
        self.start_time = None
        self.end_time = None
        self.peak_memory_mb = 0

        # 优化器实例(延迟初始化)
        self.optimizer = None

        self.logger.info(f"Initialized {process_type} optimizer")
        self.logger.info(f"CPU threads: {self.threads}")
        self.logger.info(f"Time limit: {self.time_limit}s")
        self.logger.info(f"MIP gap: {self.mip_gap:.2%}")

    def _setup_logging(self, log_level: str):
        """设置日志系统"""
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(getattr(logging, log_level.upper()))

        # 避免重复添加handler
        if not self.logger.handlers:
            # 控制台输出
            console_handler = logging.StreamHandler()
            console_handler.setLevel(getattr(logging, log_level.upper()))
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)

    def _determine_threads(self, threads: Optional[int]) -> int:
        """
        确定最优线程数

        Args:
            threads: 用户指定的线程数,None时自动检测

        Returns:
            int: 推荐的线程数
        """
        if threads is not None:
            self.logger.info(f"Using user-specified threads: {threads}")
            return threads

        # 自动检测
        available_cpus = os.cpu_count()
        if available_cpus is None:
            self.logger.warning("Could not detect CPU count, defaulting to 4 threads")
            return 4

        # 推荐策略:保留2核给操作系统,但至少使用1核，最多128核
        recommended = min(max(1, available_cpus - 2), 128)

        self.logger.info(f"Auto-detected {available_cpus} CPU cores")
        self.logger.info(f"Recommended threads: {recommended} (leaving 2 cores for system, max 128)")

        return recommended

    def _get_system_info(self) -> Dict[str, Any]:
        """获取系统信息"""
        memory = psutil.virtual_memory()
        return {
            'cpu_count': os.cpu_count(),
            'total_memory_gb': memory.total / (1024**3),
            'available_memory_gb': memory.available / (1024**3),
            'cpu_percent': psutil.cpu_percent(interval=1),
        }

    def _monitor_memory(self):
        """监控内存使用"""
        process = psutil.Process()
        memory_mb = process.memory_info().rss / (1024**2)
        if memory_mb > self.peak_memory_mb:
            self.peak_memory_mb = memory_mb

    def run(self) -> Dict[str, Any]:
        """
        运行优化

        执行完整的优化工作流程:
        1. 加载数据
        2. 构建模型
        3. 求解优化问题
        4. 保存结果
        5. 生成性能报告

        Returns:
            Dict[str, Any]: 优化结果字典,包含:
                - status: 求解状态
                - objective_value: 目标函数值
                - solve_time: 求解时间(秒)
                - gap: 最终MIP Gap
                - results: 详细结果(设施位置、生产计划、运输计划等)
                - performance: 性能指标(CPU利用率、内存使用等)

        Raises:
            Exception: 如果优化过程出错
        """
        self.logger.info("="*80)
        self.logger.info(f"Starting {self.process_type.upper()} SAF Supply Chain Optimization")
        self.logger.info("="*80)

        # 记录系统信息
        sys_info = self._get_system_info()
        self.logger.info(f"System Info:")
        self.logger.info(f"  CPU Cores: {sys_info['cpu_count']}")
        self.logger.info(f"  Total Memory: {sys_info['total_memory_gb']:.1f} GB")
        self.logger.info(f"  Available Memory: {sys_info['available_memory_gb']:.1f} GB")
        self.logger.info(f"  CPU Usage: {sys_info['cpu_percent']:.1f}%")

        # 开始计时
        self.start_time = time.time()

        try:
            # Step 1: 初始化优化器
            self.logger.info("\n[Step 1/4] Initializing optimizer...")

            # ===== v4.0变更: 实例化DAC版本优化器 =====
            # ===== v4.1修复: 传递process_mode参数 =====
            # ===== v4.2修复: 映射副产氢类型到底层工艺类型 =====
            override_params = {}
            if self.parallel_workers is not None:
                override_params['parallel_workers'] = self.parallel_workers
            if self.time_horizon_weeks is not None:
                override_params['time_horizon_weeks'] = self.time_horizon_weeks
            if self.osm_pbf_path is not None:
                override_params['osm_pbf_path'] = self.osm_pbf_path

            # 映射 process_type 到 process_mode
            # 副产氢类型使用相同的底层工艺，只是配置文件不同（氢源不同）
            process_mode_mapping = {
                'two_step': 'two_step',
                'one_step': 'one_step',
                'byproduct_one_step': 'one_step',      # 副产氢一步法 -> 底层一步法
                'byproduct_two_step': 'two_step',      # 副产氢两步法 -> 底层两步法
                'custom': self.process_type,           # 自定义类型保持不变
            }
            process_mode = process_mode_mapping.get(self.process_type, self.process_type)

            # 获取日志/结果子目录（与results_dir保持一致）
            log_subdir = self.RESULTS_DIR_MAPPING.get(self.process_type, self.process_type)

            self.optimizer = DACHydrogenSAFOptimizer(
                config_path=str(self.config_path),
                process_mode=process_mode,
                log_subdir=log_subdir,
                **override_params,
            )
            if self.time_horizon_weeks is None:
                self.time_horizon_weeks = getattr(self.optimizer, 'time_horizon_weeks', None)
            self._monitor_memory()
            self.logger.info("Optimizer initialized successfully")

            # Step 2: 加载数据
            self.logger.info("\n[Step 2/4] Loading data...")
            self.optimizer.load_data_from_excel(
                airport_excel_path=str(self.airport_excel_path) if self.airport_excel_path else None
            )
            self._monitor_memory()
            self.logger.info("Data loaded successfully")

            # Step 3: 构建模型
            self.logger.info("\n[Step 3/4] Building optimization model...")
            self.optimizer.build_model()
            self._monitor_memory()

            # 覆盖求解器参数
            self.logger.info(f"Setting solver parameters: {self.solver_params}")
            for param, value in self.solver_params.items():
                self.optimizer.model.setParam(param, value)

            # 获取模型统计信息
            self.optimizer.model.update()
            num_vars = self.optimizer.model.NumVars
            num_constrs = self.optimizer.model.NumConstrs
            num_int_vars = self.optimizer.model.NumIntVars

            self.logger.info("Model built successfully")
            self.logger.info(f"  Variables: {num_vars:,}")
            self.logger.info(f"  Constraints: {num_constrs:,}")
            self.logger.info(f"  Integer Variables: {num_int_vars:,}")

            # Step 4: 求解
            self.logger.info("\n[Step 4/4] Solving optimization problem...")
            self.logger.info("This may take a while depending on problem size and solver settings...")

            solve_start = time.time()
            solution = self.optimizer.solve()
            solve_time = time.time() - solve_start

            self._monitor_memory()

            # 获取求解信息
            status = self.optimizer.model.Status
            status_name = self._get_status_name(status)

            if solution is not None:
                obj_value = self.optimizer.model.ObjVal
                mip_gap = self.optimizer.model.MIPGap
                node_count = self.optimizer.model.NodeCount

                self.logger.info(f"Optimization completed successfully!")
                self.logger.info(f"  Status: {status_name}")
                self.logger.info(f"  Objective Value: ¥{obj_value:,.2f}")
                self.logger.info(f"  MIP Gap: {mip_gap:.2%}")
                self.logger.info(f"  Solve Time: {solve_time:.1f}s")
                self.logger.info(f"  Nodes Explored: {node_count:,}")
            else:
                self.logger.error(f"Optimization failed with status: {status_name}")
                obj_value = None
                mip_gap = None
                node_count = None

            # 保存结果
            if solution is not None:
                self.logger.info("\nSaving results...")
                if self.results_dir:
                    results_path = Path(self.results_dir)
                else:
                    results_path = project_root / 'results'

                self.optimizer.save_results(solution, str(results_path))
                self.logger.info(f"Results saved to: {results_path}")

            # 结束计时
            self.end_time = time.time()
            total_time = self.end_time - self.start_time

            # 生成性能报告
            performance = {
                'total_runtime_s': total_time,
                'solve_time_s': solve_time,
                'data_loading_time_s': solve_start - self.start_time,
                'peak_memory_mb': self.peak_memory_mb,
                'peak_memory_gb': self.peak_memory_mb / 1024,
                'threads_used': self.threads,
                'cpu_utilization_%': psutil.cpu_percent(interval=1),
            }

            self.logger.info("\n" + "="*80)
            self.logger.info("Performance Summary")
            self.logger.info("="*80)
            self.logger.info(f"Total Runtime: {total_time:.1f}s ({total_time/60:.1f}min)")
            self.logger.info(f"Solve Time: {solve_time:.1f}s ({solve_time/60:.1f}min)")
            self.logger.info(f"Peak Memory: {self.peak_memory_mb:.1f} MB ({self.peak_memory_mb/1024:.2f} GB)")
            self.logger.info(f"Threads Used: {self.threads}")
            self.logger.info(f"CPU Utilization: {performance['cpu_utilization_%']:.1f}%")
            self.logger.info("="*80)

            # 构建返回结果
            results = {
                'status': status_name,
                'status_code': status,
                'objective_value': obj_value,
                'solve_time': solve_time,
                'total_time': total_time,
                'gap': mip_gap,
                'node_count': node_count,
                'num_variables': num_vars,
                'num_constraints': num_constrs,
                'num_integer_vars': num_int_vars,
                'solution': solution,
                'performance': performance,
                'system_info': sys_info,
                'config': {
                    'process_type': self.process_type,
                    'config_path': str(self.config_path),
                    'threads': self.threads,
                    'time_limit': self.time_limit,
                    'mip_gap': self.mip_gap,
                    'time_horizon_weeks': self.time_horizon_weeks,
                },
            }

            return results

        except Exception as e:
            self.logger.error(f"Error during optimization: {str(e)}", exc_info=True)
            raise

    def _get_status_name(self, status_code: int) -> str:
        """
        获取Gurobi状态码对应的名称

        Args:
            status_code: Gurobi状态码

        Returns:
            str: 状态名称
        """
        status_map = {
            1: 'LOADED',
            2: 'OPTIMAL',
            3: 'INFEASIBLE',
            4: 'INF_OR_UNBD',
            5: 'UNBOUNDED',
            6: 'CUTOFF',
            7: 'ITERATION_LIMIT',
            8: 'NODE_LIMIT',
            9: 'TIME_LIMIT',
            10: 'SOLUTION_LIMIT',
            11: 'INTERRUPTED',
            12: 'NUMERIC',
            13: 'SUBOPTIMAL',
            14: 'INPROGRESS',
            15: 'USER_OBJ_LIMIT',
        }
        return status_map.get(status_code, f'UNKNOWN({status_code})')

    def compare_with(self, other_optimizer: 'UnifiedSAFOptimizer') -> Dict[str, Any]:
        """
        与另一个优化器的结果进行对比

        Args:
            other_optimizer: 另一个UnifiedSAFOptimizer实例

        Returns:
            Dict[str, Any]: 对比结果

        Raises:
            ValueError: 如果两个优化器都未运行
        """
        if self.optimizer is None or other_optimizer.optimizer is None:
            raise ValueError("Both optimizers must be run before comparison")

        # 这里可以添加详细的对比逻辑
        # 目前返回基本信息
        comparison = {
            'optimizer1': {
                'type': self.process_type,
                'objective': self.optimizer.model.ObjVal if hasattr(self.optimizer.model, 'ObjVal') else None,
            },
            'optimizer2': {
                'type': other_optimizer.process_type,
                'objective': other_optimizer.optimizer.model.ObjVal if hasattr(other_optimizer.optimizer.model, 'ObjVal') else None,
            },
        }

        return comparison


def run_two_step_optimization(
    threads: Optional[int] = None,
    time_limit: int = 129600,
    mip_gap: float = 0.03,
    **kwargs
) -> Dict[str, Any]:
    """
    快捷函数: 运行两步法优化

    Args:
        threads: CPU线程数
        time_limit: 求解时间限制(秒)
        mip_gap: MIP Gap
        **kwargs: 其他传递给UnifiedSAFOptimizer的参数

    Returns:
        Dict[str, Any]: 优化结果
    """
    optimizer = UnifiedSAFOptimizer(
        process_type='two_step',
        threads=threads,
        time_limit=time_limit,
        mip_gap=mip_gap,
        **kwargs
    )
    return optimizer.run()


def run_one_step_optimization(
    threads: Optional[int] = None,
    time_limit: int = 129600,
    mip_gap: float = 0.03,
    **kwargs
) -> Dict[str, Any]:
    """
    快捷函数: 运行一步法优化

    Args:
        threads: CPU线程数
        time_limit: 求解时间限制(秒)
        mip_gap: MIP Gap
        **kwargs: 其他传递给UnifiedSAFOptimizer的参数

    Returns:
        Dict[str, Any]: 优化结果
    """
    optimizer = UnifiedSAFOptimizer(
        process_type='one_step',
        threads=threads,
        time_limit=time_limit,
        mip_gap=mip_gap,
        **kwargs
    )
    return optimizer.run()


def run_byproduct_one_step_optimization(
    threads: Optional[int] = None,
    time_limit: int = 129600,
    mip_gap: float = 0.03,
    **kwargs
) -> Dict[str, Any]:
    """
    快捷函数: 运行副产氢一步法优化

    Args:
        threads: CPU线程数
        time_limit: 求解时间限制(秒)
        mip_gap: MIP Gap
        **kwargs: 其他传递给UnifiedSAFOptimizer的参数

    Returns:
        Dict[str, Any]: 优化结果
    """
    optimizer = UnifiedSAFOptimizer(
        process_type='byproduct_one_step',
        threads=threads,
        time_limit=time_limit,
        mip_gap=mip_gap,
        **kwargs
    )
    return optimizer.run()


def run_byproduct_two_step_optimization(
    threads: Optional[int] = None,
    time_limit: int = 129600,
    mip_gap: float = 0.03,
    **kwargs
) -> Dict[str, Any]:
    """
    快捷函数: 运行副产氢两步法优化

    Args:
        threads: CPU线程数
        time_limit: 求解时间限制(秒)
        mip_gap: MIP Gap
        **kwargs: 其他传递给UnifiedSAFOptimizer的参数

    Returns:
        Dict[str, Any]: 优化结果
    """
    optimizer = UnifiedSAFOptimizer(
        process_type='byproduct_two_step',
        threads=threads,
        time_limit=time_limit,
        mip_gap=mip_gap,
        **kwargs
    )
    return optimizer.run()


if __name__ == '__main__':
    # 命令行运行示例
    import argparse

    parser = argparse.ArgumentParser(description='Run SAF Supply Chain Optimization')
    parser.add_argument(
        '--process',
        '--process-type',
        dest='process_type',
        choices=['two_step', 'one_step', 'byproduct_one_step', 'byproduct_two_step'],
        default='two_step',
        help='Process type to use (two_step: DAC两步法, one_step: DAC一步法, byproduct_one_step: 副产氢一步法, byproduct_two_step: 副产氢两步法)'
    )
    parser.add_argument('--threads', type=int, default=None, help='Number of CPU threads')
    parser.add_argument('--time-limit', type=int, default=129600, help='Time limit in seconds (default: 129600 = 36 hours)')
    parser.add_argument('--mip-gap', type=float, default=0.03, help='MIP gap tolerance (default: 0.03 = 3%)')
    parser.add_argument('--log-level', default='INFO', help='Logging level')

    args = parser.parse_args()

    # 设置环境变量（用于模块级别的日志路径）
    os.environ["DAC_SUPPLY_CHAIN_PROCESS"] = args.process_type

    optimizer = UnifiedSAFOptimizer(
        process_type=args.process_type,
        threads=args.threads,
        time_limit=args.time_limit,
        mip_gap=args.mip_gap,
        log_level=args.log_level,
    )

    results = optimizer.run()

    print("\n" + "="*80)
    print("OPTIMIZATION COMPLETE")
    print("="*80)
    print(f"Status: {results['status']}")
    if results['objective_value'] is not None:
        print(f"Objective Value: ¥{results['objective_value']:,.2f}")
        print(f"MIP Gap: {results['gap']:.2%}")
    print(f"Solve Time: {results['solve_time']:.1f}s")
    print("="*80)
