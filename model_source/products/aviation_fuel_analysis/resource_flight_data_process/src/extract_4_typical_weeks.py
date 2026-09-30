#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
提取4个真正典型周的需求和可再生能源数据
Extract demand and renewable energy data for 4 truly typical weeks
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


class FourTypicalWeeksExtractor:
    """提取4个真正典型周数据的处理器"""

    def __init__(self):
        """初始化"""
        # 4个典型周的映射（12周数据中的周编号）
        self.typical_4_weeks = [1, 2, 4, 11]

        # 对应的原52周编号
        self.original_weeks = [1, 5, 14, 44]

        # 每周168小时
        self.hours_per_week = 168

        # 数据路径（从12周数据中提取）
        self.base_dir = Path('products/aviation_fuel_analysis/resource_flight_data_process/results/typical_weeks_data')
        self.demand_12weeks_file = self.base_dir / 'typical_12weeks_demand_20251129_163442.xlsx'
        self.solar_12weeks_file = self.base_dir / 'solar_hourly_500km.csv'
        self.wind_12weeks_file = self.base_dir / 'wind_hourly_500km.csv'

        # 输出目录
        self.output_dir = Path('products/aviation_fuel_analysis/resource_flight_data_process/results/4_typical_weeks_data')
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def calculate_hour_ranges_from_12weeks(self):
        """计算4个典型周在12周数据中对应的小时范围"""
        hour_ranges = []

        for week_num_in_12 in self.typical_4_weeks:
            # 在12周数据中，week_num_in_12编号从1开始
            start_hour = (week_num_in_12 - 1) * self.hours_per_week
            end_hour = week_num_in_12 * self.hours_per_week - 1

            # 找到对应的原周编号
            idx = self.typical_4_weeks.index(week_num_in_12)
            orig_week = self.original_weeks[idx]

            hour_ranges.append((week_num_in_12, orig_week, start_hour, end_hour))

        logger.info("4个典型周在12周数据中的小时范围:")
        for week_12, orig_week, start_h, end_h in hour_ranges:
            logger.info(f"  12周中的第{week_12:2d}周 (原第{orig_week:2d}周): 小时 {start_h:4d} - {end_h:4d}")

        return hour_ranges

    def extract_demand_data(self):
        """提取需求数据"""
        logger.info("=" * 80)
        logger.info("提取航班需求数据...")
        logger.info("=" * 80)

        # 读取12周需求数据
        df = pd.read_excel(self.demand_12weeks_file)
        logger.info(f"12周数据维度: {df.shape}")

        # 筛选4个典型周
        typical_4_demand = df[df['week_number'].isin(self.typical_4_weeks)].copy()

        # 创建新的周编号映射（1, 2, 4, 11 -> 1, 2, 3, 4）
        week_mapping = {old: new for new, old in enumerate(self.typical_4_weeks, 1)}

        # 保存原12周编号和原52周编号
        typical_4_demand['week_in_12'] = typical_4_demand['week_number']
        typical_4_demand['week_number'] = typical_4_demand['week_in_12'].map(week_mapping)

        # 排序
        typical_4_demand = typical_4_demand.sort_values(['airport', 'week_number'])

        logger.info(f"提取后数据维度: {typical_4_demand.shape}")
        logger.info(f"周数分布:\n{typical_4_demand.groupby(['week_number', 'week_in_12', 'original_week']).size()}")

        # 保存
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = self.output_dir / f'typical_4weeks_demand_{timestamp}.xlsx'
        typical_4_demand.to_excel(output_file, index=False)
        logger.info(f"保存需求数据: {output_file}")

        # 保存周映射关系
        mapping_file = self.output_dir / f'week_mapping_{timestamp}.csv'
        mapping_df = pd.DataFrame({
            'new_week_number': list(week_mapping.values()),
            'week_in_12weeks': list(week_mapping.keys()),
            'original_week_in_52': self.original_weeks
        })
        mapping_df.to_csv(mapping_file, index=False)
        logger.info(f"保存周映射: {mapping_file}")

        return typical_4_demand, timestamp

    def extract_renewable_data(self, data_file, data_type, hour_ranges, timestamp, chunk_size=1000000):
        """提取可再生能源数据（分块处理）"""
        logger.info("=" * 80)
        logger.info(f"提取{data_type}数据...")
        logger.info("=" * 80)

        # 创建小时集合
        hours_to_extract = set()
        for _, _, start_h, end_h in hour_ranges:
            hours_to_extract.update(range(start_h, end_h + 1))

        logger.info(f"需要提取的小时数: {len(hours_to_extract)}")

        # 分块读取
        chunks_to_concat = []
        total_rows_read = 0
        total_rows_extracted = 0

        for chunk_idx, chunk in enumerate(pd.read_csv(data_file, chunksize=chunk_size)):
            total_rows_read += len(chunk)
            filtered_chunk = chunk[chunk['hour'].isin(hours_to_extract)].copy()

            if len(filtered_chunk) > 0:
                chunks_to_concat.append(filtered_chunk)
                total_rows_extracted += len(filtered_chunk)

            if (chunk_idx + 1) % 5 == 0:
                logger.info(f"  已处理 {total_rows_read:,} 行, 提取 {total_rows_extracted:,} 行...")

        logger.info(f"读取完成: 提取 {total_rows_extracted:,} 行")

        # 合并数据
        if chunks_to_concat:
            logger.info("合并数据块...")
            typical_weeks_data = pd.concat(chunks_to_concat, ignore_index=True)

            # 创建小时映射
            hour_mapping = {}
            new_hour = 0
            for week_12, orig_week, start_h, end_h in hour_ranges:
                for orig_hour in range(start_h, end_h + 1):
                    hour_mapping[orig_hour] = new_hour
                    new_hour += 1

            # 重新编号小时
            typical_weeks_data['hour_in_12weeks'] = typical_weeks_data['hour']
            typical_weeks_data['hour'] = typical_weeks_data['hour_in_12weeks'].map(hour_mapping)

            # 排序
            typical_weeks_data = typical_weeks_data.sort_values(['plant_id', 'hour'])

            logger.info(f"最终数据维度: {typical_weeks_data.shape}")
            logger.info(f"小时范围: {typical_weeks_data['hour'].min()} - {typical_weeks_data['hour'].max()}")
            logger.info(f"电站数量: {typical_weeks_data['plant_id'].nunique()}")

            # 保存
            output_file = self.output_dir / f'typical_4weeks_{data_type}_{timestamp}.csv'
            typical_weeks_data.to_csv(output_file, index=False)
            logger.info(f"保存{data_type}数据: {output_file}")

            return typical_weeks_data
        else:
            logger.warning("未找到匹配的数据!")
            return None

    def generate_summary_report(self, demand_data, solar_data, wind_data, timestamp):
        """生成汇总报告"""
        logger.info("生成汇总报告...")

        report_file = self.output_dir / f'extraction_summary_{timestamp}.txt'

        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("4个典型周数据提取汇总报告\n")
            f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")

            f.write("典型周选择:\n")
            f.write(f"  12周中选择: {self.typical_4_weeks}\n")
            f.write(f"  对应原52周: {self.original_weeks}\n")
            f.write(f"  总小时数: 672 (4周 × 168小时/周)\n\n")

            f.write("需求数据:\n")
            f.write(f"  维度: {demand_data.shape}\n")
            for airport in demand_data['airport'].unique():
                total = demand_data[demand_data['airport'] == airport]['weekly_total_fuel_kg_total'].sum()
                f.write(f"  {airport}: {total:,.0f} kg\n")

            if solar_data is not None:
                f.write(f"\n光伏数据:\n")
                f.write(f"  维度: {solar_data.shape}\n")
                f.write(f"  电站数: {solar_data['plant_id'].nunique()}\n")
                f.write(f"  总发电量: {solar_data['power_output_mw'].sum():,.0f} MWh\n")

            if wind_data is not None:
                f.write(f"\n风电数据:\n")
                f.write(f"  维度: {wind_data.shape}\n")
                f.write(f"  电站数: {wind_data['plant_id'].nunique()}\n")
                f.write(f"  总发电量: {wind_data['power_output_mw'].sum():,.0f} MWh\n")

            f.write("\n问题规模: 52周 → 4周, 减少 92.3%\n")
            f.write("预期内存: 200-300GB → 15-20GB\n")

        logger.info(f"保存汇总报告: {report_file}")

    def run(self):
        """运行完整的数据提取流程"""
        logger.info("\n" + "=" * 80)
        logger.info("开始提取4个典型周数据")
        logger.info("=" * 80 + "\n")

        # 1. 计算小时范围
        hour_ranges = self.calculate_hour_ranges_from_12weeks()

        # 2. 提取需求数据
        demand_data, timestamp = self.extract_demand_data()

        # 3. 提取光伏数据
        solar_data = self.extract_renewable_data(
            self.solar_12weeks_file,
            'solar',
            hour_ranges,
            timestamp
        )

        # 4. 提取风电数据
        wind_data = self.extract_renewable_data(
            self.wind_12weeks_file,
            'wind',
            hour_ranges,
            timestamp
        )

        # 5. 生成汇总报告
        self.generate_summary_report(demand_data, solar_data, wind_data, timestamp)

        logger.info("\n" + "=" * 80)
        logger.info("所有数据提取完成!")
        logger.info(f"输出目录: {self.output_dir}")
        logger.info("=" * 80)

        return timestamp


def main():
    """主函数"""
    extractor = FourTypicalWeeksExtractor()
    extractor.run()


if __name__ == '__main__':
    main()
