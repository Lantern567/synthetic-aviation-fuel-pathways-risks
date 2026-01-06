"""
Unified SAF Supply Chain Optimizer Runner

统一的SAF供应链优化运行接口,支持两步法和一步法工艺路线。

主要功能:
1. 自动选择配置文件(两步法/一步法)
2. 灵活设置Gurobi求解器参数(Threads, MIPGap)
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
    >>> optimizer = UnifiedSAFOptimizer(process_type='one_step', threads=64, mip_gap=0.02)
    >>> results = optimizer.run()

作者: Claude Code
创建日期: 2025-01-25
版本: 1.0.0
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
# parents[2] 是 green_hydrogen_supply_chain_optimization/
# parents[5] 是项目根目录 green_methanol_for_port_transportation-main/
project_root = Path(__file__).resolve().parents[2]  # green_hydrogen_supply_chain_optimization/
repo_root = Path(__file__).resolve().parents[5]     # green_methanol_for_port_transportation-main/

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 导入核心优化模型
from src.core.coal_hydrogen_optimization_model import CoalHydrogenSAFOptimizer


class UnifiedSAFOptimizer:
    """
    统一SAF供应链优化器（煤炭制氢版本）

    提供简洁的API来运行两步法和一步法工艺路线的供应链优化。

    Attributes:
        process_type (str): 工艺类型,'two_step'或'one_step'
        threads (int): CPU线程数
        time_limit (Optional[int]): 求解时间限制(秒)，默认不设置
        mip_gap (float): MIP求解精度
        config_path (Path): 配置文件路径
        optimizer (CoalHydrogenSAFOptimizer): 底层优化器实例（煤炭制氢版本）
        logger (logging.Logger): 日志记录器
    """

    # 配置文件映射
    # 煤制氢模块支持两种氢气源：绿氢（可再生能源电解）和副产氢（工业副产）
    CONFIG_MAPPING = {
        'two_step': 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/data/CoalHydrogenSAFOptimizer_config.yaml',  # 煤气化CO₂+绿氢两步法
        'one_step': 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/data/CoalHydrogenSAFOptimizer_config.yaml',   # 煤气化CO₂+绿氢一步法
        'byproduct_two_step': 'shared/data/CoalByproductHydrogenSAFOptimizer_config.yaml',  # 煤气化CO₂+副产氢两步法
    }

    def __init__(
        self,
        process_type: str = 'two_step',
        threads: Optional[int] = None,
        time_limit: Optional[int] = None,
        mip_gap: float = 0.01,
        time_horizon_weeks: Optional[int] = None,  # None时从配置文件读取
        parallel_workers: Optional[int] = None,
        osm_pbf_path: Optional[str] = None,
        airport_excel_path: Optional[str] = None,
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
                - 'custom': 使用自定义配置文件(需提供config_path)
            threads: Gurobi求解器CPU线程数,None时自动检测(推荐cpu_count-2)
            time_limit: Gurobi求解时间限制(秒),默认不设置
            mip_gap: MIP相对最优间隙,默认0.01(1%)
            time_horizon_weeks: 优化时间范围(周数),默认12周
            parallel_workers: 数据处理+距离计算并行workers数,None时自动检测(cpu_count)
            osm_pbf_path: OSM地图文件路径,None时使用默认
            airport_excel_path: 机场数据Excel路径,None时使用默认
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
        valid_process_types = ['two_step', 'one_step', 'byproduct_two_step', 'custom']
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
        self.airport_excel_path = airport_excel_path
        self.results_dir = results_dir

        # 确定配置文件路径
        if process_type == 'custom':
            self.config_path = Path(config_path)
            self.logger.info(f"[CONFIG] Using custom configuration file: {config_path}")
        else:
            # 配置文件在项目根目录的shared/data/下
            relative_config_path = self.CONFIG_MAPPING[process_type]
            self.config_path = repo_root / relative_config_path
            self.logger.info(f"[CONFIG] Process type: {process_type}")
            self.logger.info(f"[CONFIG] Relative config path: {relative_config_path}")
            self.logger.info(f"[CONFIG] Repo root: {repo_root}")
            self.logger.info(f"[CONFIG] Full config path: {self.config_path}")

        if not self.config_path.exists():
            self.logger.error(f"[CONFIG] Configuration file NOT FOUND: {self.config_path}")
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        self.logger.info(f"[CONFIG] Configuration file exists and will be loaded: {self.config_path}")

        # CPU线程数设置
        self.threads = self._determine_threads(threads)
        self.parallel_workers = parallel_workers  # 保存parallel_workers参数
        self.time_limit = time_limit
        self.mip_gap = mip_gap

        # 求解器参数
        if solver_params is None:
            self.solver_params = {
                'Threads': self.threads,
                'MIPGap': self.mip_gap,
                'NodefileStart': 100,  # 内存使用超过100GB时，将节点数据写入磁盘
                'NodefileDir': '/tmp/gurobi_nodes',  # 节点文件存储目录
            }
        else:
            # 用户提供完整参数字典
            self.solver_params = solver_params
            # 确保关键参数存在
            self.solver_params.setdefault('Threads', self.threads)
            self.solver_params.setdefault('MIPGap', self.mip_gap)
            self.solver_params.setdefault('NodefileStart', 100)
            self.solver_params.setdefault('NodefileDir', '/tmp/gurobi_nodes')

        # 去除TimeLimit配置，确保不对求解时间进行限制
        if 'TimeLimit' in self.solver_params:
            self.logger.info("TimeLimit provided but will not be applied; removing from solver parameters")
            self.solver_params.pop('TimeLimit')

        # 性能监控
        self.start_time = None
        self.end_time = None
        self.peak_memory_mb = 0

        # 优化器实例(延迟初始化)
        self.optimizer = None

        self.logger.info(f"Initialized {process_type} optimizer")
        self.logger.info(f"CPU threads: {self.threads}")
        self.logger.info("Time limit: not set")
        self.logger.info(f"MIP gap: {self.mip_gap:.1%}")

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

        # 默认使用100线程以避免内存溢出
        default_threads = 100
        available_cpus = os.cpu_count()

        self.logger.info(f"Auto-detected {available_cpus} CPU cores")
        self.logger.info(f"Using default threads: {default_threads} (to avoid memory overflow)")

        return default_threads

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

            # 准备override_params传递parallel_workers
            override_params = {}
            if self.parallel_workers is not None:
                override_params['parallel_workers'] = self.parallel_workers
            # 只有当显式指定time_horizon_weeks时才覆盖配置文件值
            if self.time_horizon_weeks is not None:
                override_params['time_horizon_weeks'] = self.time_horizon_weeks

            # 确定实际的process_mode (去掉byproduct_前缀)
            actual_process_mode = self.process_type.replace('byproduct_', '')

            self.optimizer = CoalHydrogenSAFOptimizer(
                config_path=str(self.config_path),
                process_mode=actual_process_mode,
                osm_pbf_path=self.osm_pbf_path,
                **override_params,
            )
            self._monitor_memory()
            self.logger.info("Optimizer initialized successfully")

            # Step 2: 加载数据
            self.logger.info("\n[Step 2/4] Loading data...")
            self.optimizer.load_data_from_excel(
                airport_excel_path=self.airport_excel_path
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
                    # 从optimizer的配置中读取results_base_dir
                    try:
                        results_base_dir = self.optimizer.config.get('data_paths', {}).get('output_paths', {}).get('results_base_dir', None)
                        if results_base_dir:
                            results_path = Path(results_base_dir)
                            self.logger.info(f"使用配置文件中的results_base_dir: {results_path}")
                        else:
                            results_path = project_root / 'results'
                            self.logger.warning("配置文件中未找到results_base_dir，使用默认路径")
                    except Exception as e:
                        self.logger.warning(f"读取results_base_dir失败: {e}，使用默认路径")
                        results_path = project_root / 'results'

                # 确保目录存在
                results_path.mkdir(parents=True, exist_ok=True)

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
    time_limit: Optional[int] = None,
    mip_gap: float = 0.01,
    **kwargs
) -> Dict[str, Any]:
    """
    快捷函数: 运行两步法优化

    Args:
        threads: CPU线程数
        time_limit: 求解时间限制(秒)，已忽略
        mip_gap: MIP Gap
        **kwargs: 其他传递给UnifiedSAFOptimizer的参数

    Returns:
        Dict[str, Any]: 优化结果
    """
    optimizer = UnifiedSAFOptimizer(
        process_type='two_step',
        threads=threads,
        mip_gap=mip_gap,
        **kwargs
    )
    return optimizer.run()


def run_one_step_optimization(
    threads: Optional[int] = None,
    time_limit: Optional[int] = None,
    mip_gap: float = 0.01,
    **kwargs
) -> Dict[str, Any]:
    """
    快捷函数: 运行一步法优化

    Args:
        threads: CPU线程数
        time_limit: 求解时间限制(秒)，已忽略
        mip_gap: MIP Gap
        **kwargs: 其他传递给UnifiedSAFOptimizer的参数

    Returns:
        Dict[str, Any]: 优化结果
    """
    optimizer = UnifiedSAFOptimizer(
        process_type='one_step',
        threads=threads,
        mip_gap=mip_gap,
        **kwargs
    )
    return optimizer.run()


if __name__ == '__main__':
    # 命令行运行示例
    import argparse

    parser = argparse.ArgumentParser(description='Run SAF Supply Chain Optimization')
    parser.add_argument(
        '--process-type',
        choices=['two_step', 'one_step', 'byproduct_two_step'],
        default='two_step',
        help='Process type to use (two_step: 绿氢两步法, one_step: 绿氢一步法, byproduct_two_step: 副产氢两步法)'
    )
    parser.add_argument('--threads', type=int, default=None, help='Number of CPU threads')
    parser.add_argument('--time-limit', type=int, default=None, help='Time limit in seconds (ignored)')
    parser.add_argument('--mip-gap', type=float, default=0.01, help='MIP gap tolerance')
    parser.add_argument('--log-level', default='INFO', help='Logging level')

    args = parser.parse_args()

    optimizer = UnifiedSAFOptimizer(
        process_type=args.process_type,
        threads=args.threads,
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
