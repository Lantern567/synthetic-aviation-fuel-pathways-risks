#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
提取12个典型周的需求和可再生能源数据
Extract demand and renewable energy data for 12 typical weeks
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TypicalWeeksDataExtractor:
    """提取12个典型周数据的处理器"""

    def __init__(self):
        """初始化"""
        # 12个典型周（源周）
        self.typical_weeks = [1, 5, 9, 14, 18, 22, 27, 31, 35, 40, 44, 48]

        # 每周168小时
        self.hours_per_week = 168

        # 数据路径
        self.base_dir = Path('products/aviation_fuel_analysis/resource_flight_data_process')
        self.demand_file = self.base_dir / 'results/flights_beijing_tianjing/all_airports_weekly_parameters_20250726_142747.xlsx'
        self.solar_file = self.base_dir / 'results/preprocessed/solar_hourly_500km.csv'
        self.wind_file = self.base_dir / 'results/preprocessed/wind_hourly_500km.csv'

        # 输出目录
        self.output_dir = self.base_dir / 'results/typical_weeks_data'
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def calculate_hour_ranges(self):
        """计算12个典型周对应的小时范围"""
        hour_ranges = []

        for week_num in self.typical_weeks:
            # 周编号从1开始，所以hour从(week_num-1)*168开始
            start_hour = (week_num - 1) * self.hours_per_week
            end_hour = start_hour + self.hours_per_week - 1
            hour_ranges.append((week_num, start_hour, end_hour))

        logger.info("12个典型周的小时范围:")
        for week_num, start_h, end_h in hour_ranges:
            logger.info(f"  第{week_num:2d}周: 小时 {start_h:4d} - {end_h:4d}")

        return hour_ranges

    def extract_demand_data(self):
        """提取需求数据"""
        logger.info("=" * 80)
        logger.info("提取航班需求数据...")
        logger.info("=" * 80)

        # 读取需求数据
        df = pd.read_excel(self.demand_file)
        logger.info(f"原始数据维度: {df.shape}")
        logger.info(f"机场列表: {df['airport'].unique().tolist()}")

        # 筛选12个典型周
        typical_weeks_demand = df[df['week_number'].isin(self.typical_weeks)].copy()

        # 重新编号周，从1-12
        week_mapping = {orig: new for new, orig in enumerate(self.typical_weeks, 1)}
        typical_weeks_demand['original_week'] = typical_weeks_demand['week_number']
        typical_weeks_demand['week_number'] = typical_weeks_demand['original_week'].map(week_mapping)

        # 排序
        typical_weeks_demand = typical_weeks_demand.sort_values(['airport', 'week_number'])

        logger.info(f"提取后数据维度: {typical_weeks_demand.shape}")
        logger.info(f"周数分布:\n{typical_weeks_demand.groupby('original_week').size()}")

        # 保存
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = self.output_dir / f'typical_12weeks_demand_{timestamp}.xlsx'
        typical_weeks_demand.to_excel(output_file, index=False)
        logger.info(f"保存需求数据: {output_file}")

        # 保存周映射关系
        mapping_file = self.output_dir / f'week_mapping_{timestamp}.csv'
        mapping_df = pd.DataFrame({
            'new_week_number': list(week_mapping.values()),
            'original_week_number': list(week_mapping.keys())
        })
        mapping_df.to_csv(mapping_file, index=False)
        logger.info(f"保存周映射: {mapping_file}")

        return typical_weeks_demand, timestamp

    def extract_renewable_data(self, data_file, data_type, hour_ranges, timestamp, chunk_size=1000000):
        """提取可再生能源数据（分块处理大文件）

        Args:
            data_file: 数据文件路径
            data_type: 数据类型（'solar' or 'wind'）
            hour_ranges: 小时范围列表
            timestamp: 时间戳
            chunk_size: 每次读取的行数
        """
        logger.info("=" * 80)
        logger.info(f"提取{data_type}数据...")
        logger.info("=" * 80)

        # 创建小时集合（用于快速查找）
        hours_to_extract = set()
        for _, start_h, end_h in hour_ranges:
            hours_to_extract.update(range(start_h, end_h + 1))

        logger.info(f"需要提取的小时数: {len(hours_to_extract)}")
        logger.info(f"小时范围: {min(hours_to_extract)} - {max(hours_to_extract)}")

        # 分块读取和筛选
        logger.info(f"开始分块读取文件: {data_file.name}")

        chunks_to_concat = []
        total_rows_read = 0
        total_rows_extracted = 0

        for chunk_idx, chunk in enumerate(pd.read_csv(data_file, chunksize=chunk_size)):
            total_rows_read += len(chunk)

            # 筛选目标小时
            filtered_chunk = chunk[chunk['hour'].isin(hours_to_extract)].copy()

            if len(filtered_chunk) > 0:
                chunks_to_concat.append(filtered_chunk)
                total_rows_extracted += len(filtered_chunk)

            if (chunk_idx + 1) % 10 == 0:
                logger.info(f"  已处理 {total_rows_read:,} 行, 提取 {total_rows_extracted:,} 行...")

        logger.info(f"读取完成: 总共读取 {total_rows_read:,} 行, 提取 {total_rows_extracted:,} 行")

        # 合并所有筛选的数据
        if chunks_to_concat:
            logger.info("合并数据块...")
            typical_weeks_data = pd.concat(chunks_to_concat, ignore_index=True)

            # 创建小时映射（将原始小时映射到新的连续小时编号）
            hour_mapping = {}
            new_hour = 0
            for week_num, start_h, end_h in hour_ranges:
                for orig_hour in range(start_h, end_h + 1):
                    hour_mapping[orig_hour] = new_hour
                    new_hour += 1

            # 重新编号小时
            typical_weeks_data['original_hour'] = typical_weeks_data['hour']
            typical_weeks_data['hour'] = typical_weeks_data['original_hour'].map(hour_mapping)

            # 排序
            typical_weeks_data = typical_weeks_data.sort_values(['plant_id', 'hour'])

            logger.info(f"最终数据维度: {typical_weeks_data.shape}")
            logger.info(f"小时范围: {typical_weeks_data['hour'].min()} - {typical_weeks_data['hour'].max()}")
            logger.info(f"电站数量: {typical_weeks_data['plant_id'].nunique()}")

            # 统计信息
            logger.info("\n数据统计:")
            logger.info(f"  总发电量: {typical_weeks_data['power_output_mw'].sum():,.2f} MWh")
            logger.info(f"  总装机容量: {typical_weeks_data.groupby('plant_id')['capacity_mw'].first().sum():,.2f} MW")
            logger.info(f"  平均容量因子: {typical_weeks_data['power_output_mw'].sum() / (typical_weeks_data.groupby('plant_id')['capacity_mw'].first().sum() * 2016) * 100:.2f}%")

            # 保存
            output_file = self.output_dir / f'typical_12weeks_{data_type}_{timestamp}.csv'
            typical_weeks_data.to_csv(output_file, index=False)
            logger.info(f"保存{data_type}数据: {output_file}")

            # 保存小时映射
            hour_mapping_file = self.output_dir / f'hour_mapping_{data_type}_{timestamp}.csv'
            hour_mapping_df = pd.DataFrame({
                'new_hour': list(hour_mapping.values()),
                'original_hour': list(hour_mapping.keys())
            })
            hour_mapping_df = hour_mapping_df.drop_duplicates().sort_values('new_hour')
            hour_mapping_df.to_csv(hour_mapping_file, index=False)
            logger.info(f"保存小时映射: {hour_mapping_file}")

            return typical_weeks_data
        else:
            logger.warning("未找到匹配的数据!")
            return None

    def verify_data_alignment(self, demand_data, solar_data, wind_data):
        """验证数据对齐"""
        logger.info("=" * 80)
        logger.info("验证数据对齐...")
        logger.info("=" * 80)

        # 检查周数
        demand_weeks = demand_data['week_number'].unique()
        logger.info(f"需求数据周数: {sorted(demand_weeks)}")

        # 检查小时数
        if solar_data is not None:
            solar_hours = solar_data['hour'].unique()
            logger.info(f"光伏数据小时数: {len(solar_hours)} (范围: {min(solar_hours)} - {max(solar_hours)})")

        if wind_data is not None:
            wind_hours = wind_data['hour'].unique()
            logger.info(f"风电数据小时数: {len(wind_hours)} (范围: {min(wind_hours)} - {max(wind_hours)})")

        # 验证总小时数
        expected_hours = 12 * 168  # 12周 × 168小时
        logger.info(f"预期总小时数: {expected_hours}")

        if solar_data is not None:
            actual_solar_hours = len(solar_data['hour'].unique())
            logger.info(f"光伏实际小时数: {actual_solar_hours} {'✓' if actual_solar_hours == expected_hours else '✗'}")

        if wind_data is not None:
            actual_wind_hours = len(wind_data['hour'].unique())
            logger.info(f"风电实际小时数: {actual_wind_hours} {'✓' if actual_wind_hours == expected_hours else '✗'}")

        logger.info("=" * 80)
        logger.info("数据对齐验证完成!")
        logger.info("=" * 80)

    def generate_summary_report(self, demand_data, solar_data, wind_data, timestamp):
        """生成汇总报告"""
        logger.info("生成汇总报告...")

        report_file = self.output_dir / f'extraction_summary_{timestamp}.txt'

        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("12个典型周数据提取汇总报告\n")
            f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")

            # 典型周信息
            f.write("典型周编号:\n")
            f.write(f"  原始周: {self.typical_weeks}\n")
            f.write(f"  新编号: {list(range(1, 13))}\n")
            f.write(f"  总小时数: {12 * 168} (12周 × 168小时/周)\n\n")

            # 需求数据
            f.write("-" * 80 + "\n")
            f.write("需求数据统计:\n")
            f.write("-" * 80 + "\n")
            f.write(f"  数据维度: {demand_data.shape}\n")
            f.write(f"  机场数量: {demand_data['airport'].nunique()}\n")
            f.write(f"  机场列表: {demand_data['airport'].unique().tolist()}\n")
            f.write(f"  周数: {len(demand_data['week_number'].unique())}\n")

            for airport in demand_data['airport'].unique():
                airport_data = demand_data[demand_data['airport'] == airport]
                total_demand = airport_data['weekly_total_fuel_kg_total'].sum()
                f.write(f"  {airport}总需求: {total_demand:,.0f} kg\n")

            f.write("\n")

            # 光伏数据
            if solar_data is not None:
                f.write("-" * 80 + "\n")
                f.write("光伏数据统计:\n")
                f.write("-" * 80 + "\n")
                f.write(f"  数据维度: {solar_data.shape}\n")
                f.write(f"  电站数量: {solar_data['plant_id'].nunique()}\n")
                f.write(f"  小时数: {len(solar_data['hour'].unique())}\n")
                f.write(f"  小时范围: {solar_data['hour'].min()} - {solar_data['hour'].max()}\n")
                f.write(f"  总发电量: {solar_data['power_output_mw'].sum():,.2f} MWh\n")
                f.write(f"  总装机容量: {solar_data.groupby('plant_id')['capacity_mw'].first().sum():,.2f} MW\n")
                f.write(f"  平均容量因子: {solar_data['power_output_mw'].sum() / (solar_data.groupby('plant_id')['capacity_mw'].first().sum() * 2016) * 100:.2f}%\n\n")

            # 风电数据
            if wind_data is not None:
                f.write("-" * 80 + "\n")
                f.write("风电数据统计:\n")
                f.write("-" * 80 + "\n")
                f.write(f"  数据维度: {wind_data.shape}\n")
                f.write(f"  电站数量: {wind_data['plant_id'].nunique()}\n")
                f.write(f"  小时数: {len(wind_data['hour'].unique())}\n")
                f.write(f"  小时范围: {wind_data['hour'].min()} - {wind_data['hour'].max()}\n")
                f.write(f"  总发电量: {wind_data['power_output_mw'].sum():,.2f} MWh\n")
                f.write(f"  总装机容量: {wind_data.groupby('plant_id')['capacity_mw'].first().sum():,.2f} MW\n")
                f.write(f"  平均容量因子: {wind_data['power_output_mw'].sum() / (wind_data.groupby('plant_id')['capacity_mw'].first().sum() * 2016) * 100:.2f}%\n\n")

            f.write("=" * 80 + "\n")
            f.write("数据提取完成!\n")
            f.write("=" * 80 + "\n")

        logger.info(f"保存汇总报告: {report_file}")

    def run(self):
        """运行完整的数据提取流程"""
        logger.info("\n" + "=" * 80)
        logger.info("开始提取12个典型周数据")
        logger.info("=" * 80 + "\n")

        # 1. 计算小时范围
        hour_ranges = self.calculate_hour_ranges()

        # 2. 提取需求数据
        demand_data, timestamp = self.extract_demand_data()

        # 3. 提取光伏数据
        solar_data = self.extract_renewable_data(
            self.solar_file,
            'solar',
            hour_ranges,
            timestamp
        )

        # 4. 提取风电数据
        wind_data = self.extract_renewable_data(
            self.wind_file,
            'wind',
            hour_ranges,
            timestamp
        )

        # 5. 验证数据对齐
        self.verify_data_alignment(demand_data, solar_data, wind_data)

        # 6. 生成汇总报告
        self.generate_summary_report(demand_data, solar_data, wind_data, timestamp)

        logger.info("\n" + "=" * 80)
        logger.info("所有数据提取完成!")
        logger.info(f"输出目录: {self.output_dir}")
        logger.info("=" * 80)


def main():
    """主函数"""
    extractor = TypicalWeeksDataExtractor()
    extractor.run()


if __name__ == '__main__':
    main()
