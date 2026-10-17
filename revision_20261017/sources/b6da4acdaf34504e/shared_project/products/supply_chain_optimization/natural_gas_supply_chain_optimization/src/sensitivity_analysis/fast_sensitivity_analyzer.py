"""
高性能敏感性分析器
核心优化: 共享数据加载和距离计算，只更新约束参数
避免重复计算运输距离矩阵，大幅提升性能

性能对比:
- 旧方案: 17分钟/次 × 17次 = 289分钟 (4.8小时)
- 新方案: 17分钟(一次性) + 10分钟/次 × 17次 = 187分钟 (3.1小时)
- 性能提升: ~35%
"""

import os
import sys
import json
import shutil
import logging
import numpy as np
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

# 修复Windows控制台编码问题
if sys.platform.startswith('win'):
    import codecs
    # 检查是否已经被包装过
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, errors='replace')
    if hasattr(sys.stderr, 'buffer'):
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, errors='replace')

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class FastSensitivityAnalyzer:
    """
    高性能敏感性分析器

    核心优化策略:
    1. 一次性完成数据加载和距离计算 (最大性能瓶颈)
    2. 一次性构建优化模型 (变量、成本表达式、约束)
    3. 通过动态修改Gurobi约束实现参数扫描
    4. 利用Gurobi热启动加速求解
    """

    def __init__(self,
                 param_min: float = 6.72,
                 param_max: float = 6.77,
                 param_step: float = 0.001):
        """
        初始化敏感性分析器

        Args:
            param_min: 参数最小值
            param_max: 参数最大值
            param_step: 参数步长
        """
        self.param_min = param_min
        self.param_max = param_max
        self.param_step = param_step

        # 生成参数序列 - 使用linspace确保精确包含终点
        num_points = int(round((param_max - param_min) / param_step)) + 1
        self.param_values = np.linspace(param_min, param_max, num_points)
        logger.info(f"参数序列: {self.param_values}")
        logger.info(f"总计 {len(self.param_values)} 个参数点")

        # 设置路径
        self.project_root = self._get_project_root()
        self.results_base_dir = os.path.join(
            self.project_root, "products", "supply_chain_optimization",
            "natural_gas_supply_chain_optimization", "results"
        )

        # 创建时间戳
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 创建敏感性分析结果目录
        self.sensitivity_dir = os.path.join(
            self.results_base_dir,
            f"sensitivity_{self.timestamp}"
        )
        os.makedirs(self.sensitivity_dir, exist_ok=True)
        os.makedirs(os.path.join(self.sensitivity_dir, "raw_results"), exist_ok=True)
        os.makedirs(os.path.join(self.sensitivity_dir, "processed_data"), exist_ok=True)
        os.makedirs(os.path.join(self.sensitivity_dir, "figures"), exist_ok=True)

        # 设置日志文件
        log_dir = os.path.join(
            self.project_root, "products", "supply_chain_optimization",
            "natural_gas_supply_chain_optimization", "logs"
        )
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f"fast_sensitivity_{self.timestamp}.log")

        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        ))
        logger.addHandler(file_handler)

        logger.info(f"敏感性分析结果目录: {self.sensitivity_dir}")
        logger.info(f"日志文件: {log_file}")

        # 存储结果
        self.results = []

        # OSM文件路径
        self.osm_file_path = os.path.join(
            self.project_root, "products", "supply_chain_optimization",
            "natural_gas_supply_chain_optimization", "data", "china-latest.osm.pbf"
        )

    def _get_project_root(self) -> str:
        """获取项目根目录"""
        current_file = os.path.abspath(__file__)
        # fast_sensitivity_analyzer.py -> sensitivity_analysis/ -> src/ -> natural_gas/ -> supply_chain/ -> products/ -> 根目录
        return os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.dirname(current_file))))))

    def run_analysis(self):
        """执行完整的敏感性分析"""
        logger.info("="*80)
        logger.info("开始高性能敏感性分析")
        logger.info("="*80)
        logger.info(f"参数范围: {self.param_min} - {self.param_max}")
        logger.info(f"步长: {self.param_step}")
        logger.info(f"总运行次数: {len(self.param_values)}")

        try:
            # ===================================================================
            # 步骤1: 一次性初始化优化器 (性能关键)
            # ===================================================================
            logger.info("")
            logger.info("="*80)
            logger.info("步骤1: 初始化优化器")
            logger.info("="*80)

            # 导入优化器类
            sys.path.insert(0, os.path.join(self.project_root, "products",
                                           "supply_chain_optimization",
                                           "natural_gas_supply_chain_optimization", "src"))
            from core.natural_gas_optimization_model import NaturalGasSupplyChainOptimizer

            # 初始化优化器 (使用1周时间范围)
            # 注意: 第一个参数是config_path，使用None表示使用默认配置
            optimizer = NaturalGasSupplyChainOptimizer(
                config_path=None,  # 使用默认配置文件
                time_horizon_weeks=1,
                osm_pbf_path=self.osm_file_path
            )
            logger.info("优化器初始化完成")

            # ===================================================================
            # 步骤2: 一次性加载数据 (包括耗时的距离计算)
            # ===================================================================
            logger.info("")
            logger.info("="*80)
            logger.info("步骤2: 加载数据 (包括运输距离计算)")
            logger.info("="*80)

            optimizer.load_data_from_excel(airport_excel_path=None)
            logger.info("数据加载完成 (距离矩阵已计算并缓存)")

            # ===================================================================
            # 步骤3: 一次性构建优化模型
            # ===================================================================
            logger.info("")
            logger.info("="*80)
            logger.info("步骤3: 构建优化模型")
            logger.info("="*80)

            optimizer.build_model()
            logger.info("优化模型构建完成")

            # ===================================================================
            # 步骤4: 循环遍历不同的threshold参数
            # ===================================================================
            logger.info("")
            logger.info("="*80)
            logger.info("步骤4: 开始参数扫描")
            logger.info("="*80)

            for i, threshold in enumerate(self.param_values):
                logger.info("")
                logger.info("="*80)
                logger.info(f"运行 {i + 1}/{len(self.param_values)}: threshold = {threshold:.3f} 元/kg")
                logger.info("="*80)

                try:
                    # 更新threshold并重新求解 (不重新加载数据!)
                    solution = optimizer.update_threshold_and_resolve(threshold)

                    if solution:
                        # 保存结果文件
                        self._save_solution_files(optimizer, solution, threshold, i)

                        # 提取指标
                        metrics = self._extract_metrics(solution, threshold, i)
                        self.results.append(metrics)

                        # 安全格式化日志输出 (处理None值)
                        cost = metrics.get('lifecycle_levelized_cost')
                        demand = metrics.get('demand_fulfillment_ratio')
                        carbon = metrics.get('total_carbon_emission', 0)

                        cost_str = f"{cost:.3f}" if cost is not None else "N/A"
                        demand_str = f"{demand*100:.1f}%" if demand is not None else "N/A"
                        carbon_str = f"{carbon:.0f}" if carbon else "0"

                        logger.info(f"✓ 运行成功: 平准化成本={cost_str}, "
                                  f"需求满足={demand_str}, "
                                  f"总碳排放={carbon_str}")
                    else:
                        logger.warning(f"✗ threshold={threshold} 求解失败")

                except Exception as e:
                    logger.error(f"✗ threshold={threshold} 运行失败: {e}")
                    import traceback
                    logger.error(traceback.format_exc())

            # ===================================================================
            # 步骤5: 保存整合结果
            # ===================================================================
            logger.info("")
            logger.info("="*80)
            logger.info("步骤5: 保存整合结果")
            logger.info("="*80)

            self.save_consolidated_results()

            # ===================================================================
            # 步骤6: 生成可视化图表
            # ===================================================================
            if len(self.results) > 0:
                logger.info("")
                logger.info("="*80)
                logger.info("步骤6: 生成可视化图表")
                logger.info("="*80)

                try:
                    self.generate_visualizations()
                except Exception as e:
                    logger.error(f"生成可视化图表失败: {e}")
                    logger.warning("敏感性分析数据已保存，但可视化失败")

            # ===================================================================
            # 完成
            # ===================================================================
            logger.info("")
            logger.info("="*80)
            logger.info("敏感性分析完成")
            logger.info("="*80)
            logger.info(f"成功运行: {len(self.results)}/{len(self.param_values)}")
            logger.info(f"结果目录: {self.sensitivity_dir}")
            logger.info("="*80)

        except Exception as e:
            logger.error(f"敏感性分析失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise

    def _save_solution_files(self, optimizer, solution: Dict, threshold: float, run_index: int):
        """
        保存解决方案文件到敏感性分析目录

        Args:
            optimizer: 优化器实例
            solution: 解决方案字典
            threshold: 当前threshold参数值
            run_index: 运行序号
        """
        raw_results_dir = os.path.join(self.sensitivity_dir, "raw_results")

        # 1. 先计算并添加碳排放数据到solution（确保JSON包含完整数据）
        try:
            carbon_results = optimizer.calculate_carbon_emissions(solution)

            if carbon_results:
                # 将碳排放数据添加到solution中
                solution['carbon_emissions'] = carbon_results
            else:
                logger.warning("碳排放数据为空")

        except Exception as e:
            logger.warning(f"碳排放计算失败: {e}")

        # 2. 保存完整的解决方案JSON（包含carbon_emissions）
        solution_filename = f"solution_p{threshold:.3f}.json"
        solution_path = os.path.join(raw_results_dir, solution_filename)
        with open(solution_path, 'w', encoding='utf-8') as f:
            json.dump(solution, f, ensure_ascii=False, indent=2)
        logger.info(f"已保存solution: {solution_filename}")

        # 3. 保存碳排放CSV
        if 'carbon_emissions' in solution:
            try:
                carbon_filename = f"carbon_p{threshold:.3f}.csv"
                temp_timestamp = f"p{threshold:.3f}"

                optimizer.save_carbon_emissions_report(
                    solution['carbon_emissions'],
                    raw_results_dir,
                    temp_timestamp
                )
                logger.info(f"已保存carbon: {carbon_filename}")

            except Exception as e:
                logger.warning(f"保存碳排放CSV失败: {e}")

    def _extract_metrics(self, solution: Dict, threshold: float, run_index: int) -> Dict:
        """
        从解决方案中提取关键指标

        Args:
            solution: 解决方案字典
            threshold: 当前threshold参数值
            run_index: 运行序号

        Returns:
            提取的指标字典
        """
        metrics = {
            'param_value': threshold,
            'run_index': run_index
        }

        # 提取经济指标
        metrics['lifecycle_levelized_cost'] = solution.get(
            'lifecycle_levelized_cost_excluding_shortage_per_kg', None
        )
        metrics['demand_fulfillment_ratio'] = solution.get(
            'demand_fulfillment_ratio',
            solution.get('cost_breakdown', {}).get('demand_fulfillment_ratio', None)
        )
        metrics['total_cost'] = solution.get('objective_value_lifecycle_total', None)
        metrics['optimization_time'] = solution.get('optimization_time', None)

        # 提取碳排放指标 (如果有)
        # 注意: solution中的碳排放数据存储在 'carbon_emissions' 字段
        carbon_data = solution.get('carbon_emissions', {})
        if carbon_data:
            # 总碳排放在by_stage中
            by_stage = carbon_data.get('by_stage', {})
            metrics['total_carbon_emission'] = by_stage.get('total_emissions', None)

            # 碳强度在顶层
            metrics['carbon_intensity_mass'] = carbon_data.get('carbon_intensity_kg', None)
            metrics['carbon_intensity_energy'] = carbon_data.get('carbon_intensity_mj', None)

        # 格式化日志输出（正确处理None值）
        cost = metrics.get('lifecycle_levelized_cost')
        demand = metrics.get('demand_fulfillment_ratio')
        carbon = metrics.get('total_carbon_emission')

        cost_str = f"{cost:.3f}" if cost is not None else "未计算"
        demand_str = f"{demand*100:.1f}%" if demand is not None else "未计算"
        carbon_str = f"{carbon:.0f}" if carbon is not None else "未计算"

        logger.info(f"提取指标: 平准化成本={cost_str}, "
                   f"需求满足={demand_str}, "
                   f"总碳排放={carbon_str}")

        return metrics

    def save_consolidated_results(self):
        """保存整合后的结果数据"""
        if not self.results:
            logger.warning("没有结果数据可保存")
            return

        # 转换为DataFrame
        df = pd.DataFrame(self.results)

        # 使用Path对象规范化路径
        processed_data_dir = Path(self.sensitivity_dir) / "processed_data"
        processed_data_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"保存目录: {processed_data_dir}")
        logger.info(f"目录是否存在: {processed_data_dir.exists()}")

        # 保存完整结果 - 使用规范化的字符串路径
        full_results_path = str(processed_data_dir / "complete_sensitivity_results.csv")
        logger.info(f"准备保存到: {full_results_path}")
        df.to_csv(full_results_path, index=False, encoding='utf-8-sig')
        logger.info(f"完整结果已保存: {full_results_path}")

        # 保存经济指标
        economic_cols = ['param_value', 'run_index', 'lifecycle_levelized_cost',
                        'total_cost', 'optimization_time']
        if all(col in df.columns for col in economic_cols):
            economic_df = df[economic_cols]
            economic_path = str(processed_data_dir / "economic_metrics.csv")
            economic_df.to_csv(economic_path, index=False, encoding='utf-8-sig')
            logger.info(f"经济指标已保存: {economic_path}")

        # 保存需求指标
        demand_cols = ['param_value', 'run_index', 'demand_fulfillment_ratio']
        if all(col in df.columns for col in demand_cols):
            demand_df = df[demand_cols]
            demand_path = str(processed_data_dir / "demand_metrics.csv")
            demand_df.to_csv(demand_path, index=False, encoding='utf-8-sig')
            logger.info(f"需求指标已保存: {demand_path}")

        # 保存碳排放指标
        carbon_cols = ['param_value', 'run_index', 'total_carbon_emission',
                      'carbon_intensity_mass', 'carbon_intensity_energy']
        if all(col in df.columns for col in carbon_cols):
            carbon_df = df[carbon_cols]
            carbon_path = str(processed_data_dir / "carbon_metrics.csv")
            carbon_df.to_csv(carbon_path, index=False, encoding='utf-8-sig')
            logger.info(f"碳排放指标已保存: {carbon_path}")

    def generate_visualizations(self):
        """生成可视化图表"""
        try:
            # 导入可视化模块
            from .sensitivity_visualization import SensitivityVisualizer

            # 设置数据和输出目录
            data_dir = os.path.join(self.sensitivity_dir, "processed_data")
            output_dir = os.path.join(self.sensitivity_dir, "figures")

            # 创建可视化器
            visualizer = SensitivityVisualizer(data_dir, output_dir)

            # 生成所有图表
            visualizer.generate_all_plots()

            logger.info("可视化图表生成成功")

        except ImportError as e:
            logger.error(f"无法导入可视化模块: {e}")
            logger.warning("请确保sensitivity_visualization.py在同一目录下")
            raise
        except Exception as e:
            logger.error(f"生成可视化图表时发生错误: {e}")
            raise


if __name__ == '__main__':
    # 创建分析器
    analyzer = FastSensitivityAnalyzer(
        param_min=6.71,
        param_max=6.77,
        param_step=0.001
    )

    # 运行分析
    analyzer.run_analysis()