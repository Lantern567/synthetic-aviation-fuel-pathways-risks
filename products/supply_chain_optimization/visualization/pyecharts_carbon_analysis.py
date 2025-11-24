#!/usr/bin/env python3
"""
PyEcharts交互式碳排放分析可视化脚本
PyEcharts Interactive Carbon Emission Analysis Visualization Script

功能 | Features:
1. 详细的碳排放分解（运输、生产、储存等）
2. 交互式多维度对比（一步法vs两步法）
3. 旭日图展示碳排放层级结构
4. 堆叠条形图展示成本构成细节
5. 多场景对比分析

作者 | Author: Claude Code
创建时间 | Created: 2025-11-19
"""

import json
import glob
from pathlib import Path
from typing import Dict, List, Tuple
import logging
from datetime import datetime

from pyecharts import options as opts
from pyecharts.charts import Bar, Pie, Sunburst, Line, Grid, Tab
from pyecharts.commons.utils import JsCode

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PyEchartsInteractiveCarbonAnalyzer:
    """PyEcharts交互式碳排放分析器"""

    def __init__(self, output_dir: str = None):
        """
        初始化分析器

        Args:
            output_dir: 输出目录
        """
        if output_dir is None:
            base_dir = Path(__file__).parent.parent.parent.parent
            output_dir = base_dir / "products" / "supply_chain_optimization" / "visualization" / "results"

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 创建带时间戳的子目录
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = self.output_dir / f"pyecharts_analysis_{timestamp}"
        self.session_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"输出目录: {self.session_dir}")

        # 获取项目根目录
        project_root = Path(__file__).parent.parent.parent.parent

        # 场景配置
        self.modules = {
            # ========== 绿氢场景 (7个) ==========
            'Coal Hydrogen': {
                'name_cn': '煤制氢',
                'group': '绿氢场景',
                'color': '#E74C3C',
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/complete_solution_*.json'),
                'carbon_pattern': str(project_root / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/carbon_emissions_detailed_*.json')
            },
            'DAC Two-Step': {
                'name_cn': 'DAC两步法',
                'group': '绿氢场景',
                'color': '#3498DB',
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/two_step/complete_solution_*.json'),
                'carbon_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/two_step/carbon_emissions_detailed_*.json')
            },
            'DAC One-Step': {
                'name_cn': 'DAC一步法',
                'group': '绿氢场景',
                'color': '#5DADE2',
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/one_step/complete_solution_*.json'),
                'carbon_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/one_step/carbon_emissions_detailed_*.json')
            },
            'Natural Gas Two-Step': {
                'name_cn': '天然气两步法',
                'group': '绿氢场景',
                'color': '#2ECC71',
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/complete_solution_*.json'),
                'carbon_pattern': str(project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/carbon_emissions_detailed_*.json')
            },
            'Natural Gas One-Step': {
                'name_cn': '天然气一步法',
                'group': '绿氢场景',
                'color': '#F39C12',
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/ft_one_step/complete_solution_*.json'),
                'carbon_pattern': str(project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/ft_one_step/carbon_emissions_detailed_*.json')
            },
            'Green H2 Two-Step': {
                'name_cn': '绿氢两步法',
                'group': '绿氢场景',
                'color': '#9B59B6',
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/two_step/complete_solution_*.json'),
                'carbon_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/two_step/carbon_emissions_detailed_*.json')
            },
            'Green H2 One-Step': {
                'name_cn': '绿氢一步法',
                'group': '绿氢场景',
                'color': '#C39BD3',
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/one_step/complete_solution_*.json'),
                'carbon_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/one_step/carbon_emissions_detailed_*.json')
            },

            # ========== 副产氢场景 (7个) ==========
            'Byproduct H2 + Coal': {
                'name_cn': '副产氢+煤',
                'group': '副产氢场景',
                'color': '#FF6B6B',
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/byproduct_hydrogen/complete_solution_*.json'),
                'carbon_pattern': str(project_root / 'products/supply_chain_optimization/coal_hydrogen_saf_optimization/results/byproduct_hydrogen/carbon_emissions_detailed_*.json')
            },
            'Byproduct H2 + DAC Two-Step': {
                'name_cn': '副产氢+DAC两步',
                'group': '副产氢场景',
                'color': '#4ECDC4',
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/two_step/complete_solution_*.json'),
                'carbon_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/two_step/carbon_emissions_detailed_*.json')
            },
            'Byproduct H2 + DAC One-Step': {
                'name_cn': '副产氢+DAC一步',
                'group': '副产氢场景',
                'color': '#95E1D3',
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/one_step/complete_solution_*.json'),
                'carbon_pattern': str(project_root / 'products/supply_chain_optimization/dac_hydrogen_saf_supply_chain_optimization/results/byproduct_hydrogen/one_step/carbon_emissions_detailed_*.json')
            },
            'Byproduct H2 + NG Two-Step': {
                'name_cn': '副产氢+天然气两步',
                'group': '副产氢场景',
                'color': '#26DE81',
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/byproduct_hydrogen/byproduct_hydrogen/two_step/complete_solution_*.json'),
                'carbon_pattern': str(project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/byproduct_hydrogen/byproduct_hydrogen/two_step/carbon_emissions_detailed_*.json')
            },
            'Byproduct H2 + NG One-Step': {
                'name_cn': '副产氢+天然气一步',
                'group': '副产氢场景',
                'color': '#FED330',
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/byproduct_hydrogen/byproduct_hydrogen/ft_one_step/complete_solution_*.json'),
                'carbon_pattern': str(project_root / 'products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/byproduct_hydrogen/byproduct_hydrogen/ft_one_step/carbon_emissions_detailed_*.json')
            },
            'Byproduct H2 Two-Step': {
                'name_cn': '副产氢两步法',
                'group': '副产氢场景',
                'color': '#A29BFE',
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/two_step/complete_solution_*.json'),
                'carbon_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/two_step/carbon_emissions_detailed_*.json')
            },
            'Byproduct H2 One-Step': {
                'name_cn': '副产氢一步法',
                'group': '副产氢场景',
                'color': '#DFE4EA',
                'solution_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/one_step/complete_solution_*.json'),
                'carbon_pattern': str(project_root / 'products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results/byproduct_hydrogen/one_step/carbon_emissions_detailed_*.json')
            }
        }

        # 数据存储
        self.data = {}

    def load_data(self):
        """加载所有场景的数据"""
        logger.info("=" * 80)
        logger.info("加载模块数据")
        logger.info("=" * 80)

        for module_name, config in self.modules.items():
            logger.info(f"\n正在加载: {module_name} ({config['name_cn']})")

            try:
                # 加载解决方案文件
                solution_files = sorted(glob.glob(config['solution_pattern']), reverse=True)
                if not solution_files:
                    logger.warning(f"  ⚠ 未找到解决方案文件: {config['solution_pattern']}")
                    continue

                solution_path = Path(solution_files[0])
                logger.info(f"  使用最新的解决方案文件: {solution_path.name}")
                with open(solution_path, 'r', encoding='utf-8') as f:
                    solution_data = json.load(f)

                # 加载碳排放文件
                carbon_files = sorted(glob.glob(config['carbon_pattern']), reverse=True)
                if not carbon_files:
                    logger.warning(f"  ⚠ 未找到碳排放文件: {config['carbon_pattern']}")
                    continue

                carbon_path = Path(carbon_files[0])
                logger.info(f"  使用最新的碳排放文件: {carbon_path.name}")
                with open(carbon_path, 'r', encoding='utf-8') as f:
                    carbon_data = json.load(f)

                self.data[module_name] = {
                    'solution': solution_data,
                    'carbon': carbon_data,
                    'config': config
                }

                logger.info(f"  ✓ 碳强度: {carbon_data.get('carbon_intensity_kg', 0):.2f} kg CO₂/kg SAF")

            except Exception as e:
                logger.error(f"  ✗ 加载失败: {e}")
                continue

        logger.info("\n" + "=" * 80)
        logger.info(f"数据加载完成 - 成功加载 {len(self.data)} 个场景")
        logger.info("=" * 80)

    def create_carbon_intensity_comparison(self) -> Bar:
        """创建碳强度对比图"""
        logger.info("\n生成碳强度对比图...")

        modules_list = list(self.data.keys())
        scenarios = [self.modules[m]['name_cn'] for m in modules_list]

        # 提取碳强度数据
        carbon_intensity_kg = [self.data[m]['carbon']['carbon_intensity_kg'] for m in modules_list]
        carbon_intensity_mj = [self.data[m]['carbon']['carbon_intensity_mj'] for m in modules_list]

        bar = (
            Bar(init_opts=opts.InitOpts(width="1600px", height="600px", theme="light"))
            .add_xaxis(scenarios)
            .add_yaxis(
                "碳强度 (kg CO₂/kg SAF)",
                [round(v, 2) for v in carbon_intensity_kg],
                label_opts=opts.LabelOpts(position="top", formatter="{c}"),
                itemstyle_opts=opts.ItemStyleOpts(
                    color=JsCode(
                        """
                        function(params) {
                            var colors = ['#E74C3C', '#3498DB', '#5DADE2', '#2ECC71', '#F39C12',
                                         '#9B59B6', '#C39BD3', '#FF6B6B', '#4ECDC4', '#95E1D3',
                                         '#26DE81', '#FED330', '#A29BFE', '#DFE4EA'];
                            return colors[params.dataIndex];
                        }
                        """
                    )
                )
            )
            .set_global_opts(
                title_opts=opts.TitleOpts(
                    title="十四场景碳强度对比",
                    subtitle="Carbon Intensity Comparison (14 Scenarios)",
                    pos_left="center"
                ),
                xaxis_opts=opts.AxisOpts(
                    axislabel_opts=opts.LabelOpts(rotate=45, font_size=10)
                ),
                yaxis_opts=opts.AxisOpts(
                    name="碳强度 (kg CO₂/kg SAF)",
                    name_location="middle",
                    name_gap=50
                ),
                tooltip_opts=opts.TooltipOpts(
                    trigger="axis",
                    axis_pointer_type="shadow"
                ),
                datazoom_opts=[
                    opts.DataZoomOpts(type_="slider", xaxis_index=0, range_start=0, range_end=100),
                    opts.DataZoomOpts(type_="inside", xaxis_index=0)
                ],
                toolbox_opts=opts.ToolboxOpts(
                    feature={
                        "saveAsImage": {},
                        "dataView": {},
                        "magicType": {"type": ["line", "bar"]},
                        "restore": {}
                    }
                )
            )
        )

        return bar

    def create_detailed_emission_breakdown(self) -> Bar:
        """创建详细排放分解堆叠条形图"""
        logger.info("\n生成详细排放分解图...")

        modules_list = list(self.data.keys())
        scenarios = [self.modules[m]['name_cn'] for m in modules_list]

        # 定义详细排放项分类
        emission_categories = {
            '生产排放': {
                'SAF合成能耗': 'saf_synthesis_energy',
                '氢气生产': 'h2_production',
                '甲醇转SAF': 'methanol_to_saf'
            },
            '运输排放': {
                '氢气管道运输': 'h2_pipeline_transport',
                '氢气罐车运输': 'h2_truck_transport',
                'CO₂管道运输': 'co2_pipeline_transport',
                'CO₂罐车运输': 'co2_truck_transport',
                '甲醇运输': 'mtj_transport'
            },
            '储存排放': {
                '甲醇储存': 'mtj_storage',
                '氢气储存': 'h2_storage'
            },
            '设施排放': {
                'SAF设施': 'saf_facility',
                '电解槽设施': 'electrolyzer_facility',
                'DAC设备': 'dac_equipment'
            },
            '原料排放': {
                'DAC设备原料': 'dac_equipment'
            },
            'CO₂碳汇': {
                'CO₂利用': 'co2_utilization_credit'
            }
        }

        # 提取数据
        series_data = {}
        for main_cat, sub_items in emission_categories.items():
            for sub_label, key in sub_items.items():
                values = []
                for module in modules_list:
                    carbon_detailed = self.data[module]['carbon'].get('detailed', {})
                    value = carbon_detailed.get(key, 0) / 1e6  # 转换为百万kg CO₂
                    values.append(round(value, 2))

                series_data[f"{main_cat} - {sub_label}"] = values

        # 创建堆叠条形图
        bar = (
            Bar(init_opts=opts.InitOpts(width="1800px", height="800px", theme="light"))
            .add_xaxis(scenarios)
        )

        # 定义颜色映射
        color_map = {
            '生产排放': ['#E74C3C', '#C0392B', '#A93226'],
            '运输排放': ['#3498DB', '#2980B9', '#21618C', '#1B4F72', '#154360'],
            '储存排放': ['#2ECC71', '#27AE60'],
            '设施排放': ['#F39C12', '#E67E22', '#D35400'],
            '原料排放': ['#9B59B6'],
            'CO₂碳汇': ['#1ABC9C']
        }

        color_idx = {}
        for main_cat in emission_categories.keys():
            color_idx[main_cat] = 0

        for series_name, values in series_data.items():
            main_cat = series_name.split(' - ')[0]
            colors = color_map.get(main_cat, ['#95A5A6'])
            color = colors[color_idx[main_cat] % len(colors)]
            color_idx[main_cat] += 1

            bar.add_yaxis(
                series_name,
                values,
                stack="total",
                label_opts=opts.LabelOpts(is_show=False),
                itemstyle_opts=opts.ItemStyleOpts(color=color)
            )

        bar.set_global_opts(
            title_opts=opts.TitleOpts(
                title="详细碳排放分解 (百万kg CO₂)",
                subtitle="Detailed Carbon Emission Breakdown (Million kg CO₂)",
                pos_left="center"
            ),
            xaxis_opts=opts.AxisOpts(
                axislabel_opts=opts.LabelOpts(rotate=45, font_size=10)
            ),
            yaxis_opts=opts.AxisOpts(
                name="碳排放 (百万kg CO₂)",
                name_location="middle",
                name_gap=60
            ),
            tooltip_opts=opts.TooltipOpts(
                trigger="axis",
                axis_pointer_type="shadow"
            ),
            legend_opts=opts.LegendOpts(
                orient="vertical",
                pos_right="2%",
                pos_top="5%",
                type_="scroll"
            ),
            datazoom_opts=[
                opts.DataZoomOpts(type_="slider", xaxis_index=0, range_start=0, range_end=100),
                opts.DataZoomOpts(type_="inside", xaxis_index=0)
            ]
        )

        return bar

    def create_emission_sunburst(self, module_name: str) -> Sunburst:
        """创建单个场景的旭日图"""
        logger.info(f"\n生成 {module_name} 的旭日图...")

        carbon_data = self.data[module_name]['carbon']
        detailed = carbon_data.get('detailed', {})
        by_stage = carbon_data.get('by_stage', {})

        # 构建旭日图数据结构
        sunburst_data = []

        # 生产排放
        production_children = []
        if detailed.get('saf_synthesis_energy', 0) != 0:
            production_children.append({
                'name': f"SAF合成能耗\n{detailed.get('saf_synthesis_energy', 0)/1e6:.1f}M kg",
                'value': abs(detailed.get('saf_synthesis_energy', 0))
            })
        if detailed.get('h2_production', 0) != 0:
            production_children.append({
                'name': f"氢气生产\n{detailed.get('h2_production', 0)/1e6:.1f}M kg",
                'value': abs(detailed.get('h2_production', 0))
            })
        if detailed.get('methanol_to_saf', 0) != 0:
            production_children.append({
                'name': f"甲醇转SAF\n{detailed.get('methanol_to_saf', 0)/1e6:.1f}M kg",
                'value': abs(detailed.get('methanol_to_saf', 0))
            })

        if production_children:
            sunburst_data.append({
                'name': f"生产排放\n{by_stage.get('production_emissions', 0)/1e6:.1f}M kg",
                'children': production_children
            })

        # 运输排放
        transport_children = []
        if detailed.get('h2_pipeline_transport', 0) != 0:
            transport_children.append({
                'name': f"氢气管道\n{detailed.get('h2_pipeline_transport', 0)/1e6:.1f}M kg",
                'value': abs(detailed.get('h2_pipeline_transport', 0))
            })
        if detailed.get('h2_truck_transport', 0) != 0:
            transport_children.append({
                'name': f"氢气罐车\n{detailed.get('h2_truck_transport', 0)/1e6:.1f}M kg",
                'value': abs(detailed.get('h2_truck_transport', 0))
            })
        if detailed.get('co2_pipeline_transport', 0) != 0:
            transport_children.append({
                'name': f"CO₂管道\n{detailed.get('co2_pipeline_transport', 0)/1e6:.1f}M kg",
                'value': abs(detailed.get('co2_pipeline_transport', 0))
            })
        if detailed.get('mtj_transport', 0) != 0:
            transport_children.append({
                'name': f"甲醇运输\n{detailed.get('mtj_transport', 0)/1e6:.1f}M kg",
                'value': abs(detailed.get('mtj_transport', 0))
            })

        if transport_children:
            sunburst_data.append({
                'name': f"运输排放\n{by_stage.get('transport_emissions', 0)/1e6:.1f}M kg",
                'children': transport_children
            })

        # 储存排放
        storage_children = []
        if detailed.get('mtj_storage', 0) != 0:
            storage_children.append({
                'name': f"甲醇储存\n{detailed.get('mtj_storage', 0)/1e6:.1f}M kg",
                'value': abs(detailed.get('mtj_storage', 0))
            })
        if detailed.get('h2_storage', 0) != 0:
            storage_children.append({
                'name': f"氢气储存\n{detailed.get('h2_storage', 0)/1e6:.1f}M kg",
                'value': abs(detailed.get('h2_storage', 0))
            })

        if storage_children:
            sunburst_data.append({
                'name': f"储存排放\n{by_stage.get('storage_emissions', 0)/1e6:.1f}M kg",
                'children': storage_children
            })

        # CO₂碳汇
        if detailed.get('co2_utilization_credit', 0) != 0:
            sunburst_data.append({
                'name': f"CO₂碳汇\n{detailed.get('co2_utilization_credit', 0)/1e6:.1f}M kg",
                'value': abs(detailed.get('co2_utilization_credit', 0))
            })

        scenario_name = self.modules[module_name]['name_cn']

        sunburst = (
            Sunburst(init_opts=opts.InitOpts(width="1000px", height="800px", theme="light"))
            .add(
                series_name="",
                data_pair=sunburst_data,
                radius=[0, "90%"],
                label_opts=opts.LabelOpts(formatter="{b}"),
            )
            .set_global_opts(
                title_opts=opts.TitleOpts(
                    title=f"{scenario_name} 碳排放层级结构",
                    subtitle="Carbon Emission Hierarchy",
                    pos_left="center"
                ),
                tooltip_opts=opts.TooltipOpts(
                    formatter="{b}: {c} kg CO₂"
                )
            )
        )

        return sunburst

    def create_transport_detail_comparison(self) -> Bar:
        """创建运输排放详细对比图"""
        logger.info("\n生成运输排放详细对比图...")

        modules_list = list(self.data.keys())
        scenarios = [self.modules[m]['name_cn'] for m in modules_list]

        # 提取运输排放数据
        h2_pipeline = []
        h2_truck = []
        co2_pipeline = []
        co2_truck = []
        mtj_transport = []

        for module in modules_list:
            detailed = self.data[module]['carbon'].get('detailed', {})
            h2_pipeline.append(round(detailed.get('h2_pipeline_transport', 0) / 1e6, 2))
            h2_truck.append(round(detailed.get('h2_truck_transport', 0) / 1e6, 2))
            co2_pipeline.append(round(detailed.get('co2_pipeline_transport', 0) / 1e6, 2))
            co2_truck.append(round(detailed.get('co2_truck_transport', 0) / 1e6, 2))
            mtj_transport.append(round(detailed.get('mtj_transport', 0) / 1e6, 2))

        bar = (
            Bar(init_opts=opts.InitOpts(width="1800px", height="700px", theme="light"))
            .add_xaxis(scenarios)
            .add_yaxis(
                "氢气管道运输",
                h2_pipeline,
                stack="transport",
                itemstyle_opts=opts.ItemStyleOpts(color="#3498DB")
            )
            .add_yaxis(
                "氢气罐车运输",
                h2_truck,
                stack="transport",
                itemstyle_opts=opts.ItemStyleOpts(color="#2980B9")
            )
            .add_yaxis(
                "CO₂管道运输",
                co2_pipeline,
                stack="transport",
                itemstyle_opts=opts.ItemStyleOpts(color="#2ECC71")
            )
            .add_yaxis(
                "CO₂罐车运输",
                co2_truck,
                stack="transport",
                itemstyle_opts=opts.ItemStyleOpts(color="#27AE60")
            )
            .add_yaxis(
                "甲醇运输",
                mtj_transport,
                stack="transport",
                itemstyle_opts=opts.ItemStyleOpts(color="#F39C12")
            )
            .set_global_opts(
                title_opts=opts.TitleOpts(
                    title="运输排放详细对比 (百万kg CO₂)",
                    subtitle="Transport Emission Detailed Comparison",
                    pos_left="center"
                ),
                xaxis_opts=opts.AxisOpts(
                    axislabel_opts=opts.LabelOpts(rotate=45, font_size=10)
                ),
                yaxis_opts=opts.AxisOpts(
                    name="碳排放 (百万kg CO₂)",
                    name_location="middle",
                    name_gap=50
                ),
                tooltip_opts=opts.TooltipOpts(
                    trigger="axis",
                    axis_pointer_type="shadow"
                ),
                legend_opts=opts.LegendOpts(pos_top="5%"),
                datazoom_opts=[
                    opts.DataZoomOpts(type_="slider", xaxis_index=0, range_start=0, range_end=100),
                    opts.DataZoomOpts(type_="inside", xaxis_index=0)
                ]
            )
        )

        return bar

    def create_production_detail_comparison(self) -> Bar:
        """创建生产排放详细对比图"""
        logger.info("\n生成生产排放详细对比图...")

        modules_list = list(self.data.keys())
        scenarios = [self.modules[m]['name_cn'] for m in modules_list]

        # 提取生产排放数据
        saf_synthesis = []
        h2_production = []
        methanol_to_saf = []

        for module in modules_list:
            detailed = self.data[module]['carbon'].get('detailed', {})
            saf_synthesis.append(round(detailed.get('saf_synthesis_energy', 0) / 1e6, 2))
            h2_production.append(round(detailed.get('h2_production', 0) / 1e6, 2))
            methanol_to_saf.append(round(detailed.get('methanol_to_saf', 0) / 1e6, 2))

        bar = (
            Bar(init_opts=opts.InitOpts(width="1800px", height="700px", theme="light"))
            .add_xaxis(scenarios)
            .add_yaxis(
                "SAF合成能耗",
                saf_synthesis,
                stack="production",
                itemstyle_opts=opts.ItemStyleOpts(color="#E74C3C")
            )
            .add_yaxis(
                "氢气生产",
                h2_production,
                stack="production",
                itemstyle_opts=opts.ItemStyleOpts(color="#C0392B")
            )
            .add_yaxis(
                "甲醇转SAF",
                methanol_to_saf,
                stack="production",
                itemstyle_opts=opts.ItemStyleOpts(color="#A93226")
            )
            .set_global_opts(
                title_opts=opts.TitleOpts(
                    title="生产排放详细对比 (百万kg CO₂)",
                    subtitle="Production Emission Detailed Comparison",
                    pos_left="center"
                ),
                xaxis_opts=opts.AxisOpts(
                    axislabel_opts=opts.LabelOpts(rotate=45, font_size=10)
                ),
                yaxis_opts=opts.AxisOpts(
                    name="碳排放 (百万kg CO₂)",
                    name_location="middle",
                    name_gap=50
                ),
                tooltip_opts=opts.TooltipOpts(
                    trigger="axis",
                    axis_pointer_type="shadow"
                ),
                legend_opts=opts.LegendOpts(pos_top="5%"),
                datazoom_opts=[
                    opts.DataZoomOpts(type_="slider", xaxis_index=0, range_start=0, range_end=100),
                    opts.DataZoomOpts(type_="inside", xaxis_index=0)
                ]
            )
        )

        return bar

    def create_one_vs_two_step_comparison(self) -> Bar:
        """创建一步法vs两步法对比"""
        logger.info("\n生成一步法vs两步法对比图...")

        # 筛选一步法和两步法场景
        comparison_pairs = [
            ('DAC One-Step', 'DAC Two-Step'),
            ('Natural Gas One-Step', 'Natural Gas Two-Step'),
            ('Green H2 One-Step', 'Green H2 Two-Step')
        ]

        scenarios = []
        carbon_intensity = []
        colors = []

        for one_step, two_step in comparison_pairs:
            if one_step in self.data and two_step in self.data:
                # 一步法
                scenarios.append(self.modules[one_step]['name_cn'])
                carbon_intensity.append(
                    round(self.data[one_step]['carbon']['carbon_intensity_kg'], 2)
                )
                colors.append(self.modules[one_step]['color'])

                # 两步法
                scenarios.append(self.modules[two_step]['name_cn'])
                carbon_intensity.append(
                    round(self.data[two_step]['carbon']['carbon_intensity_kg'], 2)
                )
                colors.append(self.modules[two_step]['color'])

        bar = (
            Bar(init_opts=opts.InitOpts(width="1400px", height="600px", theme="light"))
            .add_xaxis(scenarios)
            .add_yaxis(
                "碳强度 (kg CO₂/kg SAF)",
                carbon_intensity,
                label_opts=opts.LabelOpts(position="top", formatter="{c}"),
                itemstyle_opts=opts.ItemStyleOpts(
                    color=JsCode(
                        f"""
                        function(params) {{
                            var colors = {colors};
                            return colors[params.dataIndex];
                        }}
                        """
                    )
                )
            )
            .set_global_opts(
                title_opts=opts.TitleOpts(
                    title="一步法 vs 两步法碳强度对比",
                    subtitle="One-Step vs Two-Step Process Comparison",
                    pos_left="center"
                ),
                xaxis_opts=opts.AxisOpts(
                    axislabel_opts=opts.LabelOpts(rotate=30, font_size=12)
                ),
                yaxis_opts=opts.AxisOpts(
                    name="碳强度 (kg CO₂/kg SAF)",
                    name_location="middle",
                    name_gap=50
                ),
                tooltip_opts=opts.TooltipOpts(
                    trigger="axis",
                    axis_pointer_type="shadow"
                )
            )
        )

        return bar

    # ========================================================================
    # 新增可视化方法 - 运输距离和增量分析
    # ========================================================================

    def _calculate_weighted_average_distance(self, transport_data: dict, weight_key: str) -> float:
        """
        计算加权平均运输距离

        Args:
            transport_data: 运输数据字典
            weight_key: 权重键名（如 'transport_kg_h2'）

        Returns:
            加权平均距离（km）
        """
        total_weight = 0
        weighted_distance = 0

        for route in transport_data.values():
            weight = route.get(weight_key, 0)
            distance = route.get('distance_km', 0)
            weighted_distance += distance * weight
            total_weight += weight

        return weighted_distance / total_weight if total_weight > 0 else 0

    def create_average_distance_comparison(self) -> Bar:
        """创建平均运输距离对比图"""
        logger.info("\n生成平均运输距离对比图...")

        modules_list = list(self.data.keys())
        scenarios = [self.modules[m]['name_cn'] for m in modules_list]

        # 提取平均运输距离数据
        h2_avg_distance = []
        co2_avg_distance = []
        mtj_avg_distance = []

        for module in modules_list:
            solution = self.data[module]['solution']

            # 氢气平均运输距离
            h2_transport = solution.get('hydrogen_transport', {})
            h2_avg = self._calculate_weighted_average_distance(h2_transport, 'transport_kg_h2')
            h2_avg_distance.append(round(h2_avg, 1))

            # CO₂平均运输距离
            co2_transport = solution.get('co2_transport', {})
            co2_avg = self._calculate_weighted_average_distance(co2_transport, 'transport_kg_co2')
            co2_avg_distance.append(round(co2_avg, 1))

            # 甲醇平均运输距离
            mtj_transport = solution.get('transport_plan', {})
            mtj_avg = self._calculate_weighted_average_distance(mtj_transport, 'transport_kg')
            mtj_avg_distance.append(round(mtj_avg, 1))

        bar = (
            Bar(init_opts=opts.InitOpts(width="1800px", height="700px", theme="light"))
            .add_xaxis(scenarios)
            .add_yaxis(
                "氢气平均运输距离",
                h2_avg_distance,
                itemstyle_opts=opts.ItemStyleOpts(color="#3498DB"),
                label_opts=opts.LabelOpts(position="top", formatter="{c} km")
            )
            .add_yaxis(
                "CO₂平均运输距离",
                co2_avg_distance,
                itemstyle_opts=opts.ItemStyleOpts(color="#2ECC71"),
                label_opts=opts.LabelOpts(position="top", formatter="{c} km")
            )
            .add_yaxis(
                "甲醇平均运输距离",
                mtj_avg_distance,
                itemstyle_opts=opts.ItemStyleOpts(color="#F39C12"),
                label_opts=opts.LabelOpts(position="top", formatter="{c} km")
            )
            .set_global_opts(
                title_opts=opts.TitleOpts(
                    title="平均运输距离对比（加权平均）",
                    subtitle="Average Transport Distance Comparison (Weighted)",
                    pos_left="center"
                ),
                xaxis_opts=opts.AxisOpts(
                    axislabel_opts=opts.LabelOpts(rotate=30, font_size=11)
                ),
                yaxis_opts=opts.AxisOpts(
                    name="平均距离 (km)",
                    name_location="middle",
                    name_gap=50
                ),
                tooltip_opts=opts.TooltipOpts(
                    trigger="axis",
                    axis_pointer_type="shadow"
                ),
                legend_opts=opts.LegendOpts(pos_top="5%"),
                toolbox_opts=opts.ToolboxOpts(
                    feature={
                        "saveAsImage": {},
                        "dataView": {"readOnly": False},
                        "magicType": {"type": ["line", "bar"]},
                        "restore": {}
                    }
                )
            )
        )

        logger.info("✓ 平均运输距离对比图生成完成")
        return bar

    def create_waterfall_chart(self, scenario_pair: Tuple[str, str] = ('DAC One-Step', 'DAC Two-Step')) -> Bar:
        """
        创建瀑布图，展示从一步法到两步法的排放增量分解

        Args:
            scenario_pair: 场景对 (一步法, 两步法)
        """
        logger.info(f"\n生成瀑布图: {scenario_pair[0]} → {scenario_pair[1]}...")

        one_step_name, two_step_name = scenario_pair

        if one_step_name not in self.data or two_step_name not in self.data:
            logger.warning(f"场景数据缺失，跳过瀑布图生成")
            return None

        one_step = self.data[one_step_name]['carbon']['detailed']
        two_step = self.data[two_step_name]['carbon']['detailed']

        # 计算增量（单位：百万kg）
        categories = [
            ('SAF合成能耗', 'saf_synthesis_energy'),
            ('氢气生产', 'h2_production'),
            ('甲醇转SAF', 'methanol_to_saf'),
            ('氢气管道运输', 'h2_pipeline_transport'),
            ('CO₂管道运输', 'co2_pipeline_transport'),
            ('甲醇运输', 'mtj_transport'),
            ('甲醇储存', 'mtj_storage'),
            ('氢气储存', 'h2_storage')
        ]

        category_names = []
        deltas = []
        colors = []

        for name, key in categories:
            delta = (two_step.get(key, 0) - one_step.get(key, 0)) / 1e6
            if abs(delta) > 0.01:  # 只显示有意义的增量
                category_names.append(name)
                deltas.append(round(delta, 2))
                # 颜色：正增量=红色，负增量=绿色
                colors.append("#E74C3C" if delta > 0 else "#2ECC71")

        # 使用PyEcharts实现瀑布效果（堆叠柱状图模拟）
        bar = (
            Bar(init_opts=opts.InitOpts(width="1400px", height="600px", theme="light"))
            .add_xaxis(category_names)
            .add_yaxis(
                "排放增量",
                deltas,
                itemstyle_opts=opts.ItemStyleOpts(
                    color=JsCode(
                        f"""
                        function(params) {{
                            var colors = {colors};
                            return colors[params.dataIndex];
                        }}
                        """
                    )
                ),
                label_opts=opts.LabelOpts(
                    position="top",
                    formatter="{c} M kg"
                )
            )
            .set_global_opts(
                title_opts=opts.TitleOpts(
                    title=f"排放增量分解: {self.modules[one_step_name]['name_cn']} → {self.modules[two_step_name]['name_cn']}",
                    subtitle="Emission Increment Breakdown (Waterfall Chart)",
                    pos_left="center"
                ),
                xaxis_opts=opts.AxisOpts(
                    axislabel_opts=opts.LabelOpts(rotate=30, font_size=11)
                ),
                yaxis_opts=opts.AxisOpts(
                    name="排放增量 (M kg CO₂)",
                    name_location="middle",
                    name_gap=50
                ),
                tooltip_opts=opts.TooltipOpts(
                    trigger="axis",
                    formatter="{b}: {c} M kg CO₂"
                ),
                toolbox_opts=opts.ToolboxOpts(
                    feature={
                        "saveAsImage": {},
                        "dataView": {"readOnly": False},
                        "restore": {}
                    }
                )
            )
        )

        logger.info("✓ 瀑布图生成完成")
        return bar

    def create_increase_rate_heatmap(self, scenario_pair: Tuple[str, str] = ('DAC One-Step', 'DAC Two-Step')) -> Bar:
        """
        创建增幅百分比热力图

        Args:
            scenario_pair: 场景对 (一步法, 两步法)
        """
        logger.info(f"\n生成增幅百分比热力图: {scenario_pair[0]} → {scenario_pair[1]}...")

        one_step_name, two_step_name = scenario_pair

        if one_step_name not in self.data or two_step_name not in self.data:
            logger.warning(f"场景数据缺失，跳过增幅热力图生成")
            return None

        one_step = self.data[one_step_name]['carbon']['detailed']
        two_step = self.data[two_step_name]['carbon']['detailed']

        # 计算增幅百分比
        categories = [
            ('SAF合成能耗', 'saf_synthesis_energy'),
            ('氢气生产', 'h2_production'),
            ('甲醇转SAF', 'methanol_to_saf'),
            ('氢气管道运输', 'h2_pipeline_transport'),
            ('CO₂管道运输', 'co2_pipeline_transport'),
            ('甲醇运输', 'mtj_transport'),
            ('甲醇储存', 'mtj_storage'),
            ('氢气储存', 'h2_storage')
        ]

        category_names = []
        increase_rates = []
        colors = []

        for name, key in categories:
            one_val = one_step.get(key, 0)
            two_val = two_step.get(key, 0)

            if one_val > 1000:  # 只对有意义的基准值计算增幅
                rate = ((two_val - one_val) / one_val) * 100 if one_val != 0 else 0
                category_names.append(name)
                increase_rates.append(round(rate, 1))

                # 热力颜色映射
                if rate < 0:
                    colors.append("#2ECC71")  # 绿色（减少）
                elif rate < 50:
                    colors.append("#F39C12")  # 橙色（小幅增加）
                elif rate < 200:
                    colors.append("#E74C3C")  # 红色（中等增加）
                else:
                    colors.append("#8B0000")  # 深红色（异常增加）

        bar = (
            Bar(init_opts=opts.InitOpts(width="1400px", height="600px", theme="light"))
            .add_xaxis(category_names)
            .add_yaxis(
                "增幅百分比",
                increase_rates,
                itemstyle_opts=opts.ItemStyleOpts(
                    color=JsCode(
                        f"""
                        function(params) {{
                            var colors = {colors};
                            return colors[params.dataIndex];
                        }}
                        """
                    )
                ),
                label_opts=opts.LabelOpts(
                    position="top",
                    formatter="{c}%",
                    font_size=12,
                    font_weight="bold"
                )
            )
            .set_global_opts(
                title_opts=opts.TitleOpts(
                    title=f"排放增幅百分比: {self.modules[one_step_name]['name_cn']} → {self.modules[two_step_name]['name_cn']}",
                    subtitle="Emission Increase Rate (%) with Heat Color Mapping",
                    pos_left="center"
                ),
                xaxis_opts=opts.AxisOpts(
                    axislabel_opts=opts.LabelOpts(rotate=30, font_size=11)
                ),
                yaxis_opts=opts.AxisOpts(
                    name="增幅 (%)",
                    name_location="middle",
                    name_gap=50
                ),
                tooltip_opts=opts.TooltipOpts(
                    trigger="axis",
                    formatter="{b}: {c}%"
                ),
                toolbox_opts=opts.ToolboxOpts(
                    feature={
                        "saveAsImage": {},
                        "dataView": {"readOnly": False},
                        "restore": {}
                    }
                )
            )
        )

        logger.info("✓ 增幅百分比热力图生成完成")
        return bar

    def create_factory_utilization_comparison(self) -> Bar:
        """创建工厂数量与平均产能利用率对比图"""
        logger.info("\n生成工厂数量与产能利用率对比图...")

        modules_list = list(self.data.keys())
        scenarios = [self.modules[m]['name_cn'] for m in modules_list]

        factory_counts = []
        avg_utilizations = []

        for module in modules_list:
            solution = self.data[module]['solution']
            facilities = solution.get('facilities', {})

            # 统计建设的工厂数量
            built_facilities = [f for f in facilities.values() if f.get('built', False)]
            factory_counts.append(len(built_facilities))

            # 计算平均产能利用率
            if built_facilities:
                avg_util = sum([f.get('utilization_rate', 0) for f in built_facilities]) / len(built_facilities)
                avg_utilizations.append(round(avg_util * 100, 1))
            else:
                avg_utilizations.append(0)

        bar = (
            Bar(init_opts=opts.InitOpts(width="1800px", height="700px", theme="light"))
            .add_xaxis(scenarios)
            .add_yaxis(
                "工厂数量",
                factory_counts,
                yaxis_index=0,
                itemstyle_opts=opts.ItemStyleOpts(color="#3498DB"),
                label_opts=opts.LabelOpts(position="top", formatter="{c} 个")
            )
            .add_yaxis(
                "平均产能利用率",
                avg_utilizations,
                yaxis_index=1,
                itemstyle_opts=opts.ItemStyleOpts(color="#E74C3C"),
                label_opts=opts.LabelOpts(position="top", formatter="{c}%")
            )
            .extend_axis(
                yaxis=opts.AxisOpts(
                    name="平均产能利用率 (%)",
                    name_location="middle",
                    name_gap=50,
                    position="right"
                )
            )
            .set_global_opts(
                title_opts=opts.TitleOpts(
                    title="工厂数量与平均产能利用率对比",
                    subtitle="Factory Count and Average Utilization Rate Comparison",
                    pos_left="center"
                ),
                xaxis_opts=opts.AxisOpts(
                    axislabel_opts=opts.LabelOpts(rotate=30, font_size=11)
                ),
                yaxis_opts=opts.AxisOpts(
                    name="工厂数量",
                    name_location="middle",
                    name_gap=50
                ),
                tooltip_opts=opts.TooltipOpts(
                    trigger="axis",
                    axis_pointer_type="shadow"
                ),
                legend_opts=opts.LegendOpts(pos_top="5%"),
                toolbox_opts=opts.ToolboxOpts(
                    feature={
                        "saveAsImage": {},
                        "dataView": {"readOnly": False},
                        "restore": {}
                    }
                )
            )
        )

        logger.info("✓ 工厂数量与产能利用率对比图生成完成")
        return bar

    def create_energy_type_comparison(self) -> Bar:
        """创建能源类型使用对比图（风电vs光伏）"""
        logger.info("\n生成能源类型使用对比图...")

        modules_list = list(self.data.keys())
        scenarios = [self.modules[m]['name_cn'] for m in modules_list]

        wind_production = []
        solar_production = []
        wind_ratios = []

        for module in modules_list:
            solution = self.data[module]['solution']
            facilities = solution.get('facilities', {})

            # 统计风电和光伏的实际产量
            wind_prod = 0
            solar_prod = 0

            for facility in facilities.values():
                if not facility.get('built', False):
                    continue

                loc_type = facility.get('location_type', '')
                prod = facility.get('actual_annual_production_kg', 0)

                if 'wind' in loc_type.lower():
                    wind_prod += prod
                elif 'solar' in loc_type.lower():
                    solar_prod += prod

            total_prod = wind_prod + solar_prod

            wind_production.append(round(wind_prod / 1e6, 2))  # 转换为百万kg
            solar_production.append(round(solar_prod / 1e6, 2))

            # 计算风电占比
            if total_prod > 0:
                wind_ratios.append(round((wind_prod / total_prod) * 100, 1))
            else:
                wind_ratios.append(0)

        bar = (
            Bar(init_opts=opts.InitOpts(width="1800px", height="700px", theme="light"))
            .add_xaxis(scenarios)
            .add_yaxis(
                "风电产量",
                wind_production,
                stack="energy",
                itemstyle_opts=opts.ItemStyleOpts(color="#2ECC71"),
                label_opts=opts.LabelOpts(position="inside", formatter="{c} M kg")
            )
            .add_yaxis(
                "光伏产量",
                solar_production,
                stack="energy",
                itemstyle_opts=opts.ItemStyleOpts(color="#F39C12"),
                label_opts=opts.LabelOpts(position="inside", formatter="{c} M kg")
            )
            .set_global_opts(
                title_opts=opts.TitleOpts(
                    title="能源类型使用对比（风电 vs 光伏）",
                    subtitle="Energy Type Comparison (Wind vs Solar) - SAF Production",
                    pos_left="center"
                ),
                xaxis_opts=opts.AxisOpts(
                    axislabel_opts=opts.LabelOpts(rotate=30, font_size=11)
                ),
                yaxis_opts=opts.AxisOpts(
                    name="SAF产量 (M kg)",
                    name_location="middle",
                    name_gap=50
                ),
                tooltip_opts=opts.TooltipOpts(
                    trigger="axis",
                    axis_pointer_type="shadow",
                    formatter="{b}<br/>"
                              "风电: {c0} M kg<br/>"
                              "光伏: {c1} M kg<br/>"
                              "总计: {c2} M kg"
                ),
                legend_opts=opts.LegendOpts(pos_top="5%"),
                toolbox_opts=opts.ToolboxOpts(
                    feature={
                        "saveAsImage": {},
                        "dataView": {"readOnly": False},
                        "magicType": {"type": ["line", "bar"]},
                        "restore": {}
                    }
                )
            )
        )

        logger.info("✓ 能源类型使用对比图生成完成")
        return bar

    def generate_all_visualizations(self):
        """生成所有可视化"""
        logger.info("\n" + "=" * 80)
        logger.info("开始生成PyEcharts交互式可视化")
        logger.info("=" * 80)

        try:
            # 创建Tab容器
            tab = Tab()

            # 1. 碳强度对比
            tab.add(self.create_carbon_intensity_comparison(), "碳强度对比")

            # 2. 一步法vs两步法
            tab.add(self.create_one_vs_two_step_comparison(), "一步法vs两步法")

            # 3. 详细排放分解
            tab.add(self.create_detailed_emission_breakdown(), "详细排放分解")

            # 4. 运输排放详细对比
            tab.add(self.create_transport_detail_comparison(), "运输排放详细")

            # 5. 生产排放详细对比
            tab.add(self.create_production_detail_comparison(), "生产排放详细")

            # ========== 新增可视化 ==========

            # 6. 平均运输距离对比 ⭐ 核心
            tab.add(self.create_average_distance_comparison(), "平均运输距离对比")

            # 7. DAC场景瀑布图 ⭐ 核心
            dac_waterfall = self.create_waterfall_chart(('DAC One-Step', 'DAC Two-Step'))
            if dac_waterfall:
                tab.add(dac_waterfall, "DAC排放增量瀑布图")

            # 8. 绿氢场景瀑布图 ⭐ 核心
            green_waterfall = self.create_waterfall_chart(('Green H2 One-Step', 'Green H2 Two-Step'))
            if green_waterfall:
                tab.add(green_waterfall, "绿氢排放增量瀑布图")

            # 9. DAC场景增幅热力图
            dac_heatmap = self.create_increase_rate_heatmap(('DAC One-Step', 'DAC Two-Step'))
            if dac_heatmap:
                tab.add(dac_heatmap, "DAC排放增幅热力图")

            # 10. 绿氢场景增幅热力图
            green_heatmap = self.create_increase_rate_heatmap(('Green H2 One-Step', 'Green H2 Two-Step'))
            if green_heatmap:
                tab.add(green_heatmap, "绿氢排放增幅热力图")

            # 11. 工厂数量与产能利用率对比
            tab.add(self.create_factory_utilization_comparison(), "工厂数量与产能利用率")

            # 12. 能源类型使用对比
            tab.add(self.create_energy_type_comparison(), "能源类型使用对比")

            # ========== 原有旭日图 ==========

            # 13-16. 为重点场景生成旭日图
            key_scenarios = ['DAC Two-Step', 'DAC One-Step', 'Green H2 Two-Step', 'Green H2 One-Step']
            for scenario in key_scenarios:
                if scenario in self.data:
                    sunburst = self.create_emission_sunburst(scenario)
                    tab.add(sunburst, f"{self.modules[scenario]['name_cn']}旭日图")

            # 保存HTML文件
            output_path = self.session_dir / "interactive_carbon_analysis.html"
            tab.render(str(output_path))

            logger.info("\n" + "=" * 80)
            logger.info("✓ 所有可视化生成完成")
            logger.info(f"✓ 输出文件: {output_path}")
            logger.info("=" * 80)

        except Exception as e:
            logger.error(f"\n✗ 可视化生成失败: {e}")
            import traceback
            traceback.print_exc()
            raise


def main():
    """主函数"""
    logger.info("=" * 80)
    logger.info("PyEcharts交互式碳排放分析脚本")
    logger.info("PyEcharts Interactive Carbon Emission Analysis Script")
    logger.info("=" * 80)

    try:
        # 创建分析器
        analyzer = PyEchartsInteractiveCarbonAnalyzer()

        # 加载数据
        analyzer.load_data()

        # 检查数据
        if len(analyzer.data) < 2:
            logger.error(f"✗ 数据不足：只找到 {len(analyzer.data)} 个场景的数据，至少需要2个")
            logger.error("  请先运行各场景的优化器生成结果文件")
            return

        # 生成可视化
        analyzer.generate_all_visualizations()

        logger.info("\n✓ 程序执行成功")

    except Exception as e:
        logger.error(f"\n✗ 程序执行失败: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()