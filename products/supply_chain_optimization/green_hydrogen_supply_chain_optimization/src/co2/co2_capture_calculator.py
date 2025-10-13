"""
CO₂捕获量计算器 (CO2 Capture Calculator)

本模块从GIS数据计算各类工业设施的CO₂捕获量，支持：
1. 燃煤电厂 (Coal Power Plants)
2. 天然气发电厂 (Gas Power Plants)
3. 石油炼厂 (Oil Refineries)

计算方法基于设施容量、排放因子和捕获率，输出标准化的CO₂捕获源数据表。

作者：Claude Code
创建日期：2025-10-13
版本：v1.0

参考文档：
- 绿氢供应链优化产品需求文档_PRD_v2.0.md 第5节
- IPCC碳排放指南
- Global CCS Institute技术报告
"""

import pandas as pd
import numpy as np
import os
import logging
from typing import Dict, List, Tuple, Optional
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CO2CaptureCalculator:
    """
    CO₂捕获量计算器

    从GIS数据加载工业设施信息，计算各设施的CO₂捕获量和捕获成本。

    Attributes:
        config (Dict): 配置参数字典
        co2_params (Dict): CO₂捕获相关参数
    """

    def __init__(self, config: Dict):
        """
        初始化CO₂捕获计算器

        Args:
            config: 配置参数字典，包含co2_parameters等配置
        """
        self.config = config
        self.co2_params = config.get('co2_parameters', {})

        # 提取关键参数
        self.capture_sources = self.co2_params.get('capture_sources', {})
        self.capture_costs = self.co2_params.get('capture_costs', {})

        logger.info("CO2CaptureCalculator initialized successfully")

    def _load_coal_power_plants(self, gis_data_dir: str) -> pd.DataFrame:
        """
        加载燃煤电厂GIS数据

        Args:
            gis_data_dir: GIS数据目录路径

        Returns:
            DataFrame包含燃煤电厂数据
        """
        coal_file = os.path.join(gis_data_dir, 'coal_power_plants.csv')

        if not os.path.exists(coal_file):
            logger.warning(f"Coal power plants file not found: {coal_file}")
            return pd.DataFrame()

        # 读取CSV文件
        df = pd.read_csv(coal_file, encoding='utf-8-sig')
        logger.info(f"Loaded {len(df)} coal power plant records")

        # 筛选运行中的电厂
        if 'Status' in df.columns:
            df = df[df['Status'] == 'Operating'].copy()
            logger.info(f"Filtered to {len(df)} operating coal power plants")

        # 处理缺失的Capacity_factor（使用默认值0.70）
        if 'Capacity_factor' not in df.columns:
            df['Capacity_factor'] = self.capture_sources.get('coal_power_capacity_factor', 0.70)
        else:
            df['Capacity_factor'] = df['Capacity_factor'].fillna(
                self.capture_sources.get('coal_power_capacity_factor', 0.70)
            )

        # 数据验证：容量范围检查
        if 'Capacity__MW_' in df.columns:
            # 过滤掉异常容量值
            df = df[
                (df['Capacity__MW_'] >= 10) &
                (df['Capacity__MW_'] <= 5000)
            ].copy()
            logger.info(f"After capacity validation: {len(df)} records")

        return df

    def _load_gas_power_plants(self, gis_data_dir: str) -> pd.DataFrame:
        """
        加载天然气发电厂GIS数据

        Args:
            gis_data_dir: GIS数据目录路径

        Returns:
            DataFrame包含天然气电厂数据
        """
        gas_file = os.path.join(gis_data_dir, 'gas_power_plants.csv')

        if not os.path.exists(gas_file):
            logger.warning(f"Gas power plants file not found: {gas_file}")
            return pd.DataFrame()

        # 读取CSV文件
        df = pd.read_csv(gas_file, encoding='utf-8-sig')
        logger.info(f"Loaded {len(df)} gas power plant records")

        # 筛选运行中的电厂
        if 'Status' in df.columns:
            df = df[df['Status'] == 'Operating'].copy()
            logger.info(f"Filtered to {len(df)} operating gas power plants")

        # 统一使用固定Capacity_factor=0.75
        df['Capacity_factor'] = self.capture_sources.get('lng_power_capacity_factor', 0.75)

        # 数据验证：容量范围检查
        if 'Capacity__MW_' in df.columns:
            df = df[
                (df['Capacity__MW_'] >= 20) &
                (df['Capacity__MW_'] <= 3000)
            ].copy()
            logger.info(f"After capacity validation: {len(df)} records")

        return df

    def _load_oil_refineries(self, gis_data_dir: str) -> pd.DataFrame:
        """
        加载石油炼厂GIS数据

        Args:
            gis_data_dir: GIS数据目录路径

        Returns:
            DataFrame包含石油炼厂数据
        """
        oil_file = os.path.join(gis_data_dir, 'oil_refineries.csv')

        if not os.path.exists(oil_file):
            logger.warning(f"Oil refineries file not found: {oil_file}")
            return pd.DataFrame()

        # 读取CSV文件
        df = pd.read_csv(oil_file, encoding='utf-8-sig')
        logger.info(f"Loaded {len(df)} oil refinery records")

        # 筛选运行中的炼厂
        if 'Status' in df.columns:
            df = df[df['Status'] == 'Operating'].copy()
            logger.info(f"Filtered to {len(df)} operating oil refineries")

        # 容量单位转换：KBD → 吨原油/周
        # 1 KBD = 1000桶/天 × 7天 × 159升/桶 × 0.85吨/m³ ÷ 1000 = 945吨/周
        if 'Capacity' in df.columns and 'CapUnit' in df.columns:
            kbd_mask = df['CapUnit'] == 'KBD'
            df.loc[kbd_mask, 'Capacity_ton_per_week'] = df.loc[kbd_mask, 'Capacity'] * 945
            logger.info(f"Converted {kbd_mask.sum()} KBD capacity values to ton/week")

        # 统一使用固定Capacity_factor=0.85
        df['Capacity_factor'] = self.capture_sources.get('oil_refinery_capacity_factor', 0.85)

        return df

    def _calculate_coal_capture(self, plant: pd.Series, week: int) -> Dict:
        """
        计算燃煤电厂CO₂捕获量

        计算公式：
        1. 周发电量(MWh) = 装机容量(MW) × 168小时 × 容量因子
        2. CO₂排放(吨) = 周发电量 × 排放因子(0.95 tCO₂/MWh)
        3. CO₂捕获(吨) = CO₂排放 × 捕获率(0.85)

        Args:
            plant: 电厂数据（Series）
            week: 周数

        Returns:
            字典包含捕获量和成本信息
        """
        capacity_mw = plant.get('Capacity__MW_', 600)  # 默认600MW
        capacity_factor = plant.get('Capacity_factor', 0.70)

        # Step 1: 计算周发电量
        hours_per_week = 168
        weekly_electricity_mwh = capacity_mw * hours_per_week * capacity_factor

        # Step 2: 计算CO₂排放
        emission_factor = self.capture_sources.get('coal_power_emission_factor', 0.95)  # tCO₂/MWh
        co2_emission_ton = weekly_electricity_mwh * emission_factor

        # Step 3: 计算CO₂捕获
        capture_rate = self.capture_sources.get('coal_power_capture_rate', 0.85)
        co2_capture_ton = co2_emission_ton * capture_rate

        # Step 4: 捕获成本
        capture_cost_yuan_per_ton = self.capture_costs.get('coal_power_yuan_per_ton', 150)

        return {
            'co2_capture_capacity_ton_per_week': co2_capture_ton,
            'capture_cost_yuan_per_ton': capture_cost_yuan_per_ton,
            'total_capture_cost_yuan_per_week': co2_capture_ton * capture_cost_yuan_per_ton,
            'facility_type': 'coal_power',
            'week': week
        }

    def _calculate_gas_capture(self, plant: pd.Series, week: int) -> Dict:
        """
        计算天然气发电厂CO₂捕获量

        计算公式：
        1. 周发电量(MWh) = 装机容量(MW) × 168小时 × 容量因子(0.75)
        2. CO₂排放(吨) = 周发电量 × 排放因子(0.42 tCO₂/MWh)
        3. CO₂捕获(吨) = CO₂排放 × 捕获率(0.90)

        Args:
            plant: 电厂数据（Series）
            week: 周数

        Returns:
            字典包含捕获量和成本信息
        """
        capacity_mw = plant.get('Capacity__MW_', 400)
        capacity_factor = plant.get('Capacity_factor', 0.75)

        # Step 1: 计算周发电量
        hours_per_week = 168
        weekly_electricity_mwh = capacity_mw * hours_per_week * capacity_factor

        # Step 2: 计算CO₂排放
        emission_factor = self.capture_sources.get('lng_power_emission_factor', 0.42)  # tCO₂/MWh
        co2_emission_ton = weekly_electricity_mwh * emission_factor

        # Step 3: 计算CO₂捕获
        capture_rate = self.capture_sources.get('lng_power_capture_rate', 0.90)
        co2_capture_ton = co2_emission_ton * capture_rate

        # Step 4: 捕获成本
        capture_cost_yuan_per_ton = self.capture_costs.get('lng_power_yuan_per_ton', 180)

        return {
            'co2_capture_capacity_ton_per_week': co2_capture_ton,
            'capture_cost_yuan_per_ton': capture_cost_yuan_per_ton,
            'total_capture_cost_yuan_per_week': co2_capture_ton * capture_cost_yuan_per_ton,
            'facility_type': 'gas_power',
            'week': week
        }

    def _calculate_refinery_capture(self, refinery: pd.Series, week: int) -> Dict:
        """
        计算石油炼厂CO₂捕获量

        计算公式：
        1. 容量转换：KBD × 945 = 吨原油/周
        2. 实际处理量 = 设计产能 × 容量因子(0.85)
        3. CO₂排放(吨) = 实际处理量 × 排放因子(0.6 tCO₂/吨原油)
        4. CO₂捕获(吨) = CO₂排放 × 捕获率(0.80)

        Args:
            refinery: 炼厂数据（Series）
            week: 周数

        Returns:
            字典包含捕获量和成本信息
        """
        # Step 1 & 2: 容量转换和实际处理量
        crude_ton_per_week = refinery.get('Capacity_ton_per_week', 94500)  # 默认100 KBD
        capacity_factor = refinery.get('Capacity_factor', 0.85)
        actual_crude_ton = crude_ton_per_week * capacity_factor

        # Step 3: 计算CO₂排放
        emission_factor = self.capture_sources.get('oil_refinery_emission_factor', 0.6)  # tCO₂/吨原油
        co2_emission_ton = actual_crude_ton * emission_factor

        # Step 4: 计算CO₂捕获
        capture_rate = self.capture_sources.get('oil_refinery_capture_rate', 0.80)
        co2_capture_ton = co2_emission_ton * capture_rate

        # Step 5: 捕获成本
        capture_cost_yuan_per_ton = self.capture_costs.get('oil_refinery_yuan_per_ton', 120)

        return {
            'co2_capture_capacity_ton_per_week': co2_capture_ton,
            'capture_cost_yuan_per_ton': capture_cost_yuan_per_ton,
            'total_capture_cost_yuan_per_week': co2_capture_ton * capture_cost_yuan_per_ton,
            'facility_type': 'oil_refinery',
            'week': week
        }

    def calculate_from_gis_data(
        self,
        gis_data_dir: str,
        time_horizon_weeks: int
    ) -> pd.DataFrame:
        """
        从GIS数据计算CO₂捕获量（主计算方法）

        Args:
            gis_data_dir: GIS数据目录路径
            time_horizon_weeks: 优化时间范围（周数）

        Returns:
            DataFrame包含标准化的CO₂捕获源数据

        列定义（共15列）：
            - location_id: 设施唯一标识
            - location_name: 设施名称
            - facility_type: 设施类型（coal_power/gas_power/oil_refinery）
            - latitude, longitude: 坐标
            - province: 省份
            - capacity_original: 原始容量
            - capacity_unit: 容量单位
            - capacity_factor: 容量因子
            - status: 运行状态
            - week: 周数
            - co2_capture_capacity_ton_per_week: 每周CO₂捕获量（吨）
            - capture_cost_yuan_per_ton: 单位捕获成本（元/吨）
            - total_capture_cost_yuan_per_week: 周总捕获成本（元）
            - data_source: 数据来源文件名
            - year_online: 投产年份
        """
        logger.info(f"Starting CO₂ capture calculation for {time_horizon_weeks} weeks")
        logger.info(f"GIS data directory: {gis_data_dir}")

        all_sources = []

        # 1. 加载并计算燃煤电厂CO₂捕获
        coal_df = self._load_coal_power_plants(gis_data_dir)
        if not coal_df.empty:
            for idx, plant in coal_df.iterrows():
                for week in range(time_horizon_weeks):
                    capture_data = self._calculate_coal_capture(plant, week)

                    record = {
                        'location_id': f"coal_power_{idx}",
                        'location_name': plant.get('Plant_name', f'Coal Plant {idx}'),
                        'facility_type': 'coal_power',
                        'latitude': plant.get('Latitude', 0.0),
                        'longitude': plant.get('Longitude', 0.0),
                        'province': plant.get('Province', 'Unknown'),
                        'capacity_original': plant.get('Capacity__MW_', 0.0),
                        'capacity_unit': 'MW',
                        'capacity_factor': plant.get('Capacity_factor', 0.70),
                        'status': plant.get('Status', 'Operating'),
                        'week': week,
                        'co2_capture_capacity_ton_per_week': capture_data['co2_capture_capacity_ton_per_week'],
                        'capture_cost_yuan_per_ton': capture_data['capture_cost_yuan_per_ton'],
                        'total_capture_cost_yuan_per_week': capture_data['total_capture_cost_yuan_per_week'],
                        'data_source': 'coal_power_plants.csv',
                        'year_online': plant.get('Start_year', None)
                    }
                    all_sources.append(record)

                # 每100个电厂打印一次进度
                if (idx + 1) % 100 == 0:
                    logger.info(f"Processed {idx + 1} coal power plants")

        # 2. 加载并计算天然气电厂CO₂捕获
        gas_df = self._load_gas_power_plants(gis_data_dir)
        if not gas_df.empty:
            for idx, plant in gas_df.iterrows():
                for week in range(time_horizon_weeks):
                    capture_data = self._calculate_gas_capture(plant, week)

                    record = {
                        'location_id': f"gas_power_{idx}",
                        'location_name': plant.get('Name', plant.get('ChineseName', f'Gas Plant {idx}')),
                        'facility_type': 'gas_power',
                        'latitude': plant.get('Lat', 0.0),
                        'longitude': plant.get('Long', 0.0),
                        'province': plant.get('Province', 'Unknown'),
                        'capacity_original': plant.get('Capacity__MW_', 0.0),
                        'capacity_unit': 'MW',
                        'capacity_factor': plant.get('Capacity_factor', 0.75),
                        'status': plant.get('Status', 'Operating'),
                        'week': week,
                        'co2_capture_capacity_ton_per_week': capture_data['co2_capture_capacity_ton_per_week'],
                        'capture_cost_yuan_per_ton': capture_data['capture_cost_yuan_per_ton'],
                        'total_capture_cost_yuan_per_week': capture_data['total_capture_cost_yuan_per_week'],
                        'data_source': 'gas_power_plants.csv',
                        'year_online': plant.get('YearOnline', None)
                    }
                    all_sources.append(record)

        # 3. 加载并计算石油炼厂CO₂捕获
        oil_df = self._load_oil_refineries(gis_data_dir)
        if not oil_df.empty:
            for idx, refinery in oil_df.iterrows():
                for week in range(time_horizon_weeks):
                    capture_data = self._calculate_refinery_capture(refinery, week)

                    record = {
                        'location_id': f"oil_refinery_{idx}",
                        'location_name': refinery.get('Name', refinery.get('ChineseName', f'Refinery {idx}')),
                        'facility_type': 'oil_refinery',
                        'latitude': refinery.get('Lat', 0.0),
                        'longitude': refinery.get('Long', 0.0),
                        'province': refinery.get('Province', 'Unknown'),
                        'capacity_original': refinery.get('Capacity', 0.0),
                        'capacity_unit': refinery.get('CapUnit', 'KBD'),
                        'capacity_factor': refinery.get('Capacity_factor', 0.85),
                        'status': refinery.get('Status', 'Operating'),
                        'week': week,
                        'co2_capture_capacity_ton_per_week': capture_data['co2_capture_capacity_ton_per_week'],
                        'capture_cost_yuan_per_ton': capture_data['capture_cost_yuan_per_ton'],
                        'total_capture_cost_yuan_per_week': capture_data['total_capture_cost_yuan_per_week'],
                        'data_source': 'oil_refineries.csv',
                        'year_online': refinery.get('YearOnline', None)
                    }
                    all_sources.append(record)

        # 4. 合并所有数据源
        result_df = pd.DataFrame(all_sources)

        # 5. 数据验证
        if not result_df.empty:
            result_df = self._validate_output(result_df)

        logger.info(f"CO₂ capture calculation completed: {len(result_df)} records generated")
        logger.info(f"Total facilities: Coal={len(coal_df)}, Gas={len(gas_df)}, Oil={len(oil_df)}")

        return result_df

    def _validate_output(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        验证输出数据的完整性和合理性

        Args:
            df: 待验证的DataFrame

        Returns:
            验证后的DataFrame
        """
        logger.info("Validating output data...")

        initial_count = len(df)

        # 1. 检查必需列是否存在
        required_cols = [
            'location_id', 'location_name', 'facility_type',
            'latitude', 'longitude', 'week',
            'co2_capture_capacity_ton_per_week',
            'capture_cost_yuan_per_ton'
        ]

        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            logger.error(f"Missing required columns: {missing_cols}")
            raise ValueError(f"Missing required columns: {missing_cols}")

        # 2. 检查数值列范围
        # CO₂捕获量必须 > 0
        invalid_capture = df[df['co2_capture_capacity_ton_per_week'] <= 0]
        if not invalid_capture.empty:
            logger.warning(f"Found {len(invalid_capture)} records with invalid capture capacity (<= 0)")
            df = df[df['co2_capture_capacity_ton_per_week'] > 0].copy()

        # 坐标范围检查
        invalid_coords = df[
            (df['latitude'] < -90) | (df['latitude'] > 90) |
            (df['longitude'] < -180) | (df['longitude'] > 180)
        ]
        if not invalid_coords.empty:
            logger.warning(f"Found {len(invalid_coords)} records with invalid coordinates")
            df = df[
                (df['latitude'] >= -90) & (df['latitude'] <= 90) &
                (df['longitude'] >= -180) & (df['longitude'] <= 180)
            ].copy()

        # 捕获成本必须 > 0
        invalid_cost = df[df['capture_cost_yuan_per_ton'] <= 0]
        if not invalid_cost.empty:
            logger.warning(f"Found {len(invalid_cost)} records with invalid cost (<= 0)")
            df = df[df['capture_cost_yuan_per_ton'] > 0].copy()

        # 3. 检查空值
        null_counts = df.isnull().sum()
        if null_counts.any():
            logger.warning(f"Null values found:\n{null_counts[null_counts > 0]}")

        final_count = len(df)
        if final_count < initial_count:
            logger.warning(f"Removed {initial_count - final_count} invalid records")

        logger.info(f"Validation complete: {final_count} valid records")

        return df

    def save_to_csv(self, df: pd.DataFrame, output_path: str) -> None:
        """
        保存CO₂捕获源数据到CSV文件

        Args:
            df: CO₂捕获源DataFrame
            output_path: 输出文件路径
        """
        # 确保输出目录存在
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            logger.info(f"Created output directory: {output_dir}")

        # 保存到CSV
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        logger.info(f"CO₂ capture sources data saved to: {output_path}")
        logger.info(f"Total records: {len(df)}")

        # 打印统计信息
        self._print_statistics(df)

    def _print_statistics(self, df: pd.DataFrame) -> None:
        """
        打印CO₂捕获数据的统计信息

        Args:
            df: CO₂捕获源DataFrame
        """
        logger.info("\n" + "="*60)
        logger.info("CO₂ Capture Statistics Summary")
        logger.info("="*60)

        # 按设施类型统计
        facility_stats = df.groupby('facility_type').agg({
            'location_id': 'nunique',
            'co2_capture_capacity_ton_per_week': 'sum',
            'total_capture_cost_yuan_per_week': 'sum'
        }).rename(columns={
            'location_id': 'Facility Count',
            'co2_capture_capacity_ton_per_week': 'Total CO₂ Capture (ton/week)',
            'total_capture_cost_yuan_per_week': 'Total Cost (yuan/week)'
        })

        logger.info(f"\nBy Facility Type:\n{facility_stats}")

        # 总体统计
        total_facilities = df['location_id'].nunique()
        total_capture = df['co2_capture_capacity_ton_per_week'].sum()
        total_cost = df['total_capture_cost_yuan_per_week'].sum()
        avg_cost = df['capture_cost_yuan_per_ton'].mean()

        logger.info(f"\nOverall Statistics:")
        logger.info(f"  Total Facilities: {total_facilities}")
        logger.info(f"  Total CO₂ Capture: {total_capture:,.2f} ton/week")
        logger.info(f"  Total Capture Cost: {total_cost:,.2f} yuan/week")
        logger.info(f"  Average Unit Cost: {avg_cost:.2f} yuan/ton")

        logger.info("="*60 + "\n")
