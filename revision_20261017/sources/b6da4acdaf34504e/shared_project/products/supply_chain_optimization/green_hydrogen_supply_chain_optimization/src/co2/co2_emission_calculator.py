"""
⚠️ DEPRECATED - 本模块已废弃 (DEPRECATED)
==================================================

本独立CO₂排放计算器已被废弃，所有碳排放计算已迁移到优化器内部实现。

废弃日期：2025-11-09
迁移到：green_hydrogen_optimization_model.py 的 _create_carbon_emission_expressions() 方法

废弃原因：
1. 动态碳强度计算需要基于实际发电数据，独立计算器无法访问优化器内部状态
2. Gurobi优化要求碳排放表达式与决策变量集成，无法分离计算
3. 统一在优化器内部计算可确保数据一致性和计算效率

替代方案：
- 碳排放计算现已完全集成到优化器的约束和目标函数中
- 使用 optimizer.carbon_expressions 和 optimizer.carbon_aggregates 获取结果

如需继续使用本模块，请参考优化器源码中的实现
==================================================

CO₂排放量计算器 (CO2 Emission Calculator)

本模块计算绿氢+CO₂制SAF全生命周期碳排放，包括：
1. 原材料排放（绿氢生产、CO₂捕获过程）
2. 运输排放（H₂、CO₂、SAF运输）
3. 生产过程排放（甲醇合成E-CRM、MTJ转化）
4. 储存处理排放
5. CO₂利用负排放（固定在产品中的碳）

计算方法基于IPCC标准和配置文件参数，输出符合CORSIA标准的碳排放报告。

作者：Claude Code
创建日期：2025-10-13
版本：v1.0（已废弃 - DEPRECATED）

参考文档：
- 绿氢供应链优化产品需求文档_PRD_v2.0.md 第5.2节、3.2节
- IPCC碳排放计算指南
- CORSIA可持续航空燃料标准
"""

import logging
import warnings
from typing import Dict, List, Tuple, Optional

# 废弃警告
warnings.warn(
    "CO2EmissionCalculator独立模块已废弃，请使用优化器内部的碳排放计算功能。"
    "所有碳排放计算已迁移到 green_hydrogen_optimization_model.py 的 _create_carbon_emission_expressions() 方法中。"
    "详见模块顶部的废弃说明。",
    DeprecationWarning,
    stacklevel=2
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CO2EmissionCalculator:
    """
    CO₂排放量计算器

    计算绿氢+CO₂制SAF的全生命周期碳排放。

    Attributes:
        config (Dict): 配置参数字典
        carbon_params (Dict): 碳排放相关参数
    """

    def __init__(self, config: Dict):
        """
        初始化CO₂排放计算器

        Args:
            config: 配置参数字典，包含carbon_emission_parameters等配置
        """
        self.config = config
        self.carbon_params = config.get('carbon_emission_parameters', {})

        # 提取关键参数
        self.benchmarks = self.carbon_params.get('benchmarks', {})
        self.renewable_energy = self.carbon_params.get('renewable_energy', {})
        self.production_process = self.carbon_params.get('production_process', {})
        self.storage_handling = self.carbon_params.get('storage_handling', {})
        self.transportation = self.carbon_params.get('transportation', {})

        # 基准值
        self.traditional_jet_fuel_ci = self.benchmarks.get('traditional_jet_fuel', 89)  # gCO₂e/MJ
        self.saf_energy_content = self.benchmarks.get('saf_energy_content', 43.15)  # MJ/kg
        self.corsia_limit = self.benchmarks.get('corsia_limit', 30)  # gCO₂e/MJ

        # CO₂来源类型配置
        # 可选值: 'dac' (直接空气捕获), 'industrial_capture' (工业捕获), 'self_emission' (自身排放)
        tech_params = config.get('technologies', {}).get('green_h2_co2_to_saf', {})
        self.co2_source_type = tech_params.get('co2_source_type', 'self_emission')

        logger.info(f"CO2EmissionCalculator initialized successfully (CO₂来源类型: {self.co2_source_type})")

    def calculate_lifecycle_emissions(
        self,
        saf_production_kg: float,
        h2_consumption_kg: float,
        co2_consumption_kg: float,
        h2_transport_distance_km: float = 100.0,
        co2_transport_distance_km: float = 80.0,
        saf_transport_distance_km: float = 150.0,
        h2_transport_mode: str = 'pipeline',
        co2_transport_mode: str = 'pipeline'
    ) -> Dict:
        """
        计算全生命周期碳排放（主方法）

        Args:
            saf_production_kg: SAF生产量 (kg)
            h2_consumption_kg: 氢气消耗量 (kg)
            co2_consumption_kg: CO₂消耗量 (kg)
            h2_transport_distance_km: 氢气运输距离 (km)
            co2_transport_distance_km: CO₂运输距离 (km)
            saf_transport_distance_km: SAF运输距离 (km)
            h2_transport_mode: 氢气运输方式 ('pipeline' or 'truck')
            co2_transport_mode: CO₂运输方式 ('pipeline' or 'truck')

        Returns:
            Dict包含碳排放详细信息：
            - total_emission_kgCO2e: 总碳排放量 (kgCO₂e)
            - carbon_intensity_gCO2e_per_MJ: 碳强度 (gCO₂e/MJ SAF)
            - emission_reduction_percent: 相对传统航煤的减排百分比
            - corsia_compliant: 是否符合CORSIA标准
            - breakdown: 各环节分项排放
        """
        logger.info(f"开始计算全生命周期碳排放：SAF产量 {saf_production_kg:.2f} kg")

        # 1. 原材料排放
        h2_production_emission = self._calc_h2_production_emission(h2_consumption_kg)
        co2_capture_emission = self._calc_co2_capture_emission(co2_consumption_kg)

        # 2. 运输排放
        h2_transport_emission = self._calc_h2_transport_emission(
            h2_consumption_kg, h2_transport_distance_km, h2_transport_mode
        )
        co2_transport_emission = self._calc_co2_transport_emission(
            co2_consumption_kg, co2_transport_distance_km, co2_transport_mode
        )
        saf_transport_emission = self._calc_saf_transport_emission(
            saf_production_kg, saf_transport_distance_km
        )

        # 3. 生产过程排放
        methanol_synthesis_emission = self._calc_methanol_synthesis_emission(saf_production_kg)
        mtj_conversion_emission = self._calc_mtj_conversion_emission(saf_production_kg)

        # 4. 储存处理排放
        storage_emission = self._calc_storage_emission(
            h2_consumption_kg, co2_consumption_kg, saf_production_kg
        )

        # 5. CO₂利用负排放
        co2_utilization_credit = self._calc_co2_utilization_credit(co2_consumption_kg)

        # 6. 汇总计算
        total_emission_kgCO2e = (
            h2_production_emission +
            co2_capture_emission +
            h2_transport_emission +
            co2_transport_emission +
            saf_transport_emission +
            methanol_synthesis_emission +
            mtj_conversion_emission +
            storage_emission +
            co2_utilization_credit  # 负值
        )

        # 7. 计算碳强度 (gCO₂e/MJ)
        saf_energy_mj = saf_production_kg * self.saf_energy_content
        carbon_intensity = (total_emission_kgCO2e * 1000) / saf_energy_mj  # kg → g

        # 8. 计算减排百分比
        emission_reduction_percent = (
            (self.traditional_jet_fuel_ci - carbon_intensity) /
            self.traditional_jet_fuel_ci * 100
        )

        # 9. 判断CORSIA符合性
        corsia_compliant = carbon_intensity <= self.corsia_limit

        # 10. 构建结果
        result = {
            'total_emission_kgCO2e': total_emission_kgCO2e,
            'carbon_intensity_gCO2e_per_MJ': carbon_intensity,
            'emission_reduction_percent': emission_reduction_percent,
            'corsia_compliant': corsia_compliant,
            'breakdown': {
                'h2_production_emission': h2_production_emission,
                'co2_capture_emission': co2_capture_emission,
                'h2_transport_emission': h2_transport_emission,
                'co2_transport_emission': co2_transport_emission,
                'saf_transport_emission': saf_transport_emission,
                'methanol_synthesis_emission': methanol_synthesis_emission,
                'mtj_conversion_emission': mtj_conversion_emission,
                'storage_emission': storage_emission,
                'co2_utilization_credit': co2_utilization_credit
            },
            'benchmarks': {
                'traditional_jet_fuel_ci_gCO2e_per_MJ': self.traditional_jet_fuel_ci,
                'corsia_limit_gCO2e_per_MJ': self.corsia_limit,
                'saf_energy_content_MJ_per_kg': self.saf_energy_content
            }
        }

        logger.info(f"碳排放计算完成：总排放 {total_emission_kgCO2e:.2f} kgCO₂e, "
                    f"碳强度 {carbon_intensity:.2f} gCO₂e/MJ, "
                    f"减排 {emission_reduction_percent:.1f}%, "
                    f"CORSIA符合性: {corsia_compliant}")

        return result

    def _calc_h2_production_emission(self, h2_kg: float) -> float:
        """
        计算绿氢生产排放

        Args:
            h2_kg: 氢气消耗量 (kg)

        Returns:
            排放量 (kgCO₂e)
        """
        # 绿氢生产排放 = 电解过程排放 + 可再生能源电力碳强度
        electrolysis_emission = self.production_process.get('h2_electrolysis_emission', 0.05)  # kgCO₂e/kg H₂

        # 电力消耗
        green_h2_params = self.config.get('green_hydrogen_supply', {})
        energy_kwh_per_kg = green_h2_params.get('production_energy_kwh_per_kg', 50)  # kWh/kg H₂

        # 可再生能源碳强度（使用风电和光伏加权平均）
        wind_intensity = self.renewable_energy.get('wind_power_intensity', 0.015)  # kgCO₂e/kWh
        solar_intensity = self.renewable_energy.get('solar_power_intensity', 0.045)  # kgCO₂e/kWh
        renewable_intensity = (wind_intensity + solar_intensity) / 2  # 简化：50%-50%加权

        electricity_emission = h2_kg * energy_kwh_per_kg * renewable_intensity
        process_emission = h2_kg * electrolysis_emission

        total = electricity_emission + process_emission

        logger.debug(f"绿氢生产排放: {total:.2f} kgCO₂e (电力 {electricity_emission:.2f} + 工艺 {process_emission:.2f})")

        return total

    def _calc_co2_capture_emission(self, co2_kg: float) -> float:
        """
        计算CO₂捕获过程排放

        Args:
            co2_kg: CO₂捕获量 (kg)

        Returns:
            排放量 (kgCO₂e)
        """
        # CO₂捕获过程的能源消耗和设备运行产生的排放
        # 注意：这里是捕获过程本身的排放，不是捕获的CO₂量
        capture_process_intensity = 0.1  # kgCO₂e/kg CO₂捕获
        # 说明：捕获1kg CO₂需要消耗能源，产生约0.1kg CO₂排放

        emission = co2_kg * capture_process_intensity

        logger.debug(f"CO₂捕获过程排放: {emission:.2f} kgCO₂e")

        return emission

    def _calc_h2_transport_emission(
        self,
        h2_kg: float,
        distance_km: float,
        transport_mode: str
    ) -> float:
        """
        计算氢气运输排放

        Args:
            h2_kg: 氢气运输量 (kg)
            distance_km: 运输距离 (km)
            transport_mode: 运输方式 ('pipeline' or 'truck')

        Returns:
            排放量 (kgCO₂e)
        """
        if transport_mode == 'pipeline':
            intensity = self.transportation.get('h2_pipeline_intensity', 0.02)  # kgCO₂e/kg/100km
        elif transport_mode == 'truck':
            intensity = self.transportation.get('h2_truck_intensity', 0.15)  # kgCO₂e/kg/100km
        else:
            logger.warning(f"未知的氢气运输方式: {transport_mode}，使用管道默认值")
            intensity = 0.02

        emission = h2_kg * (distance_km / 100) * intensity

        logger.debug(f"氢气运输排放 ({transport_mode}): {emission:.2f} kgCO₂e")

        return emission

    def _calc_co2_transport_emission(
        self,
        co2_kg: float,
        distance_km: float,
        transport_mode: str
    ) -> float:
        """
        计算CO₂运输排放

        Args:
            co2_kg: CO₂运输量 (kg)
            distance_km: 运输距离 (km)
            transport_mode: 运输方式 ('pipeline' or 'truck')

        Returns:
            排放量 (kgCO₂e)
        """
        if transport_mode == 'pipeline':
            intensity = self.transportation.get('co2_pipeline_intensity', 0.01)  # kgCO₂e/kg/100km
        elif transport_mode == 'truck':
            intensity = self.transportation.get('co2_truck_intensity', 0.08)  # kgCO₂e/kg/100km
        else:
            logger.warning(f"未知的CO₂运输方式: {transport_mode}，使用管道默认值")
            intensity = 0.01

        emission = co2_kg * (distance_km / 100) * intensity

        logger.debug(f"CO₂运输排放 ({transport_mode}): {emission:.2f} kgCO₂e")

        return emission

    def _calc_saf_transport_emission(
        self,
        saf_kg: float,
        distance_km: float
    ) -> float:
        """
        计算SAF运输排放

        Args:
            saf_kg: SAF运输量 (kg)
            distance_km: 运输距离 (km)

        Returns:
            排放量 (kgCO₂e)
        """
        intensity = self.transportation.get('saf_truck_intensity', 0.12)  # kgCO₂e/kg/100km

        emission = saf_kg * (distance_km / 100) * intensity

        logger.debug(f"SAF运输排放: {emission:.2f} kgCO₂e")

        return emission

    def _calc_methanol_synthesis_emission(self, saf_kg: float) -> float:
        """
        计算甲醇合成过程排放（E-CRM工艺）

        Args:
            saf_kg: SAF生产量 (kg)

        Returns:
            排放量 (kgCO₂e)
        """
        # 获取两步法技术参数
        tech_params = self.config.get('technologies', {}).get('green_h2_co2_to_saf', {})
        methanol_intermediate_ratio = tech_params.get('methanol_intermediate_ratio', 1.3)  # kg甲醇/kg SAF

        # 甲醇生产量
        methanol_kg = saf_kg * methanol_intermediate_ratio

        # 甲醇合成排放强度（E-CRM工艺）
        synthesis_emission = self.production_process.get('saf_synthesis_emission', 0.3)  # kgCO₂e/kg SAF

        # 工艺能耗
        saf_process_energy = self.production_process.get('saf_process_energy', 3.0)  # kWh/kg SAF

        # 能源碳强度（使用可再生能源）
        wind_intensity = self.renewable_energy.get('wind_power_intensity', 0.015)
        solar_intensity = self.renewable_energy.get('solar_power_intensity', 0.045)
        renewable_intensity = (wind_intensity + solar_intensity) / 2

        energy_emission = saf_kg * saf_process_energy * renewable_intensity
        process_emission = saf_kg * synthesis_emission

        total = energy_emission + process_emission

        logger.debug(f"甲醇合成排放: {total:.2f} kgCO₂e (能耗 {energy_emission:.2f} + 工艺 {process_emission:.2f})")

        return total

    def _calc_mtj_conversion_emission(self, saf_kg: float) -> float:
        """
        计算MTJ转化过程排放

        Args:
            saf_kg: SAF生产量 (kg)

        Returns:
            排放量 (kgCO₂e)
        """
        # MTJ转化的工艺排放（较低，因为主要是催化重排）
        mtj_emission_intensity = 0.2  # kgCO₂e/kg SAF

        emission = saf_kg * mtj_emission_intensity

        logger.debug(f"MTJ转化排放: {emission:.2f} kgCO₂e")

        return emission

    def _calc_storage_emission(
        self,
        h2_kg: float,
        co2_kg: float,
        saf_kg: float
    ) -> float:
        """
        计算储存处理排放

        Args:
            h2_kg: 氢气储存量 (kg)
            co2_kg: CO₂储存量 (kg)
            saf_kg: SAF储存量 (kg)

        Returns:
            排放量 (kgCO₂e)
        """
        # 储存能耗
        h2_storage_energy = self.storage_handling.get('h2_storage_energy', 2)  # kWh/kg/天
        saf_storage_energy = self.storage_handling.get('saf_storage_energy', 5)  # kWh/吨/天

        # 假设平均储存时间
        avg_storage_days = 3  # 平均储存3天

        # 能源碳强度
        wind_intensity = self.renewable_energy.get('wind_power_intensity', 0.015)
        solar_intensity = self.renewable_energy.get('solar_power_intensity', 0.045)
        renewable_intensity = (wind_intensity + solar_intensity) / 2

        h2_storage = h2_kg * h2_storage_energy * avg_storage_days * renewable_intensity
        saf_storage = (saf_kg / 1000) * saf_storage_energy * avg_storage_days * renewable_intensity

        # CO₂储存排放较低（已液化）
        co2_storage = co2_kg * 0.001 * avg_storage_days  # 简化计算

        total = h2_storage + co2_storage + saf_storage

        logger.debug(f"储存处理排放: {total:.2f} kgCO₂e (H₂ {h2_storage:.2f} + CO₂ {co2_storage:.2f} + SAF {saf_storage:.2f})")

        return total

    def _calc_co2_utilization_credit(self, co2_kg: float) -> float:
        """
        计算CO₂利用负排放（碳固定）

        根据CO₂来源类型确定是否计入负排放：
        - 'dac': 直接空气捕获（DAC） → 100%计入负排放（真正的碳汇）
        - 'industrial_capture': 外部工业捕获 → 50%计入负排放（避免了排放）
        - 'self_emission': 自身排放循环利用 → 0%计入负排放（不算碳汇）

        Args:
            co2_kg: CO₂利用量 (kg)

        Returns:
            负排放量 (kgCO₂e，负值或0)
        """
        # 根据CO₂来源类型设置负排放系数
        if self.co2_source_type == 'dac':
            utilization_credit_factor = -1.0  # 100%计入负排放
            source_desc = "DAC直接空气捕获（真正碳汇）"
        elif self.co2_source_type == 'industrial_capture':
            utilization_credit_factor = -0.5  # 50%计入负排放
            source_desc = "工业捕获（避免排放）"
        elif self.co2_source_type == 'self_emission':
            utilization_credit_factor = 0.0   # 不计入负排放
            source_desc = "自身排放循环利用（不算碳汇）"
        else:
            utilization_credit_factor = 0.0
            source_desc = f"未知来源类型({self.co2_source_type})"
            logger.warning(f"未知的CO₂来源类型: {self.co2_source_type}，不计入负排放")

        credit = co2_kg * utilization_credit_factor

        logger.debug(f"CO₂利用负排放: {credit:.2f} kgCO₂e (来源: {source_desc}, 系数: {utilization_credit_factor})")

        return credit

    def generate_emission_report(self, emission_data: Dict) -> str:
        """
        生成碳排放报告（文本格式）

        Args:
            emission_data: calculate_lifecycle_emissions()的返回结果

        Returns:
            格式化的报告文本
        """
        report = []
        report.append("=" * 80)
        report.append("绿氢+CO₂制SAF全生命周期碳排放报告")
        report.append("Green Hydrogen + CO₂ to SAF Lifecycle Carbon Emission Report")
        report.append("=" * 80)
        report.append("")

        # 总览
        report.append("【总览 Summary】")
        report.append(f"  总碳排放量: {emission_data['total_emission_kgCO2e']:.2f} kgCO₂e")
        report.append(f"  碳强度: {emission_data['carbon_intensity_gCO2e_per_MJ']:.2f} gCO₂e/MJ SAF")
        report.append(f"  相对传统航煤减排: {emission_data['emission_reduction_percent']:.1f}%")
        report.append(f"  CORSIA符合性: {'✓ 符合' if emission_data['corsia_compliant'] else '✗ 不符合'}")
        report.append("")

        # 基准对比
        benchmarks = emission_data['benchmarks']
        report.append("【基准对比 Benchmarks】")
        report.append(f"  传统航空煤油碳强度: {benchmarks['traditional_jet_fuel_ci_gCO2e_per_MJ']:.2f} gCO₂e/MJ")
        report.append(f"  CORSIA排放限值: {benchmarks['corsia_limit_gCO2e_per_MJ']:.2f} gCO₂e/MJ")
        report.append(f"  SAF能量含量: {benchmarks['saf_energy_content_MJ_per_kg']:.2f} MJ/kg")
        report.append("")

        # 分项排放
        breakdown = emission_data['breakdown']
        report.append("【分项排放 Emission Breakdown】")
        report.append(f"  1. 绿氢生产: {breakdown['h2_production_emission']:.2f} kgCO₂e")
        report.append(f"  2. CO₂捕获: {breakdown['co2_capture_emission']:.2f} kgCO₂e")
        report.append(f"  3. 氢气运输: {breakdown['h2_transport_emission']:.2f} kgCO₂e")
        report.append(f"  4. CO₂运输: {breakdown['co2_transport_emission']:.2f} kgCO₂e")
        report.append(f"  5. SAF运输: {breakdown['saf_transport_emission']:.2f} kgCO₂e")
        report.append(f"  6. 甲醇合成: {breakdown['methanol_synthesis_emission']:.2f} kgCO₂e")
        report.append(f"  7. MTJ转化: {breakdown['mtj_conversion_emission']:.2f} kgCO₂e")
        report.append(f"  8. 储存处理: {breakdown['storage_emission']:.2f} kgCO₂e")
        report.append(f"  9. CO₂利用负排放: {breakdown['co2_utilization_credit']:.2f} kgCO₂e")
        report.append("")

        report.append("=" * 80)

        return "\n".join(report)
