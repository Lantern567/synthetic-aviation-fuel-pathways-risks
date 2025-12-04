#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
筛选北京100km范围内的12周可再生能源电站数据
Filter renewable energy plants within 100km of Beijing for 12 weeks data

使用multiprocessing实现真正的并行计算
Using multiprocessing for true parallel computation
"""

import os
import sys
import gc
import argparse
import pandas as pd
import logging
from datetime import datetime
from multiprocessing import Pool, cpu_count
from math import radians, sin, cos, sqrt, atan2
from typing import List, Tuple, Optional

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==================== 距离计算函数 ====================

def calculate_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    计算两点间的Haversine距离（公里）

    Args:
        lat1, lon1: 第一个点的纬度经度
        lat2, lon2: 第二个点的纬度经度

    Returns:
        float: 距离（公里）
    """
    # 转换为弧度
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

    # Haversine公式
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))

    # 地球半径(公里)
    R = 6371
    distance = R * c

    return distance


def is_within_beijing_range(lat: float, lon: float, max_distance_km: float = 100) -> bool:
    """
    检查坐标是否在北京指定范围内

    Args:
        lat, lon: 检查点的纬度经度
        max_distance_km: 最大距离（公里），默认100公里

    Returns:
        bool: 是否在范围内
    """
    # 北京市中心坐标（天安门）
    beijing_lat = 39.9042
    beijing_lon = 116.4074

    distance = calculate_distance_km(lat, lon, beijing_lat, beijing_lon)
    return distance <= max_distance_km


# ==================== 并行筛选函数 ====================

def filter_plant_worker(args: Tuple[str, pd.DataFrame, float]) -> Optional[pd.DataFrame]:
    """
    并行筛选单个电站的worker函数（用于multiprocessing）

    Args:
        args: (plant_name, plant_data, max_distance_km) 元组

    Returns:
        pd.DataFrame or None: 筛选后的电站数据（如果在范围内）
    """
    plant_name, plant_data, max_distance_km = args

    if len(plant_data) > 0:
        # 获取电站坐标（使用第一行数据）
        plant_lat = plant_data.iloc[0].get('latitude', 30.0)
        plant_lon = plant_data.iloc[0].get('longitude', 104.0)

        # 检查是否在北京指定范围内
        if is_within_beijing_range(plant_lat, plant_lon, max_distance_km):
            return plant_data

    return None


def filter_renewable_data_100km(
    input_file: str,
    output_file: str,
    max_distance_km: float = 100,
    max_workers: Optional[int] = None
) -> Tuple[int, int]:
    """
    筛选100km范围内的可再生能源数据（使用multiprocessing并行）

    Args:
        input_file: 输入CSV文件路径
        output_file: 输出CSV文件路径
        max_distance_km: 最大距离（公里）
        max_workers: 并行进程数量，默认为CPU核心数

    Returns:
        (original_count, filtered_count): 原始记录数和筛选后记录数
    """
    if max_workers is None:
        max_workers = cpu_count()

    logger.info("="*80)
    logger.info(f"开始筛选数据: {os.path.basename(input_file)}")
    logger.info(f"筛选范围: 北京{max_distance_km}km以内")
    logger.info(f"使用multiprocessing并行计算，进程数: {max_workers}")
    logger.info("="*80)

    # 读取数据
    logger.info(f"读取数据: {input_file}")
    df = pd.read_csv(input_file)
    original_count = len(df)
    original_plants = df['plant_id'].nunique()
    logger.info(f"原始数据: {original_count:,} 条记录, {original_plants:,} 个电站")

    # 按电站ID分组
    logger.info("按电站ID分组数据...")
    grouped = df.groupby('plant_id', sort=False)
    plant_count = len(grouped)
    logger.info(f"准备使用{max_workers}个并行进程处理{plant_count:,}个电站")

    # 准备并行处理参数
    logger.info("准备并行处理参数...")
    plant_data_list = [
        (plant_id, plant_data.copy(), max_distance_km)
        for plant_id, plant_data in grouped
    ]

    # 释放原始DataFrame以节省内存
    del df, grouped
    gc.collect()
    logger.info(f"已准备{len(plant_data_list):,}个电站的数据")

    # 使用multiprocessing并行筛选
    logger.info("开始multiprocessing并行筛选电站...")
    filtered_plants = []

    with Pool(processes=max_workers) as pool:
        results = pool.map(filter_plant_worker, plant_data_list)

        for result in results:
            if result is not None:
                filtered_plants.append(result)

    logger.info(f"并行筛选完成，找到{len(filtered_plants):,}个符合条件的电站")

    # 释放中间数据
    del plant_data_list
    gc.collect()

    # 合并筛选后的数据
    if filtered_plants:
        logger.info(f"合并{len(filtered_plants):,}个电站的数据...")
        filtered_df = pd.concat(filtered_plants, ignore_index=True)

        # 释放列表
        del filtered_plants
        gc.collect()

        filtered_count = len(filtered_df)
        filtered_plants_count = filtered_df['plant_id'].nunique()

        logger.info(f"筛选后数据: {filtered_count:,} 条记录, {filtered_plants_count:,} 个电站")
        logger.info(f"数据保留率: {filtered_count/original_count*100:.2f}%")
        logger.info(f"电站保留率: {filtered_plants_count/original_plants*100:.2f}%")

        # 保存筛选后的数据
        logger.info(f"保存筛选后的数据: {output_file}")
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        filtered_df.to_csv(output_file, index=False)

        # 计算文件大小
        file_size_mb = os.path.getsize(output_file) / (1024 * 1024)
        logger.info(f"输出文件大小: {file_size_mb:.2f} MB")

        return original_count, filtered_count
    else:
        logger.warning("没有找到符合条件的电站！")
        return original_count, 0


# ==================== 主函数 ====================

def main():
    parser = argparse.ArgumentParser(
        description='筛选北京100km范围内的12周可再生能源电站数据'
    )
    parser.add_argument(
        '--solar',
        action='store_true',
        help='筛选太阳能数据'
    )
    parser.add_argument(
        '--wind',
        action='store_true',
        help='筛选风电数据'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='筛选所有数据（太阳能+风电）'
    )
    parser.add_argument(
        '--distance',
        type=float,
        default=100,
        help='筛选距离（公里），默认100km'
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=None,
        help='并行进程数量，默认为CPU核心数'
    )

    args = parser.parse_args()

    # 确定要处理的数据类型
    if args.all:
        process_solar = True
        process_wind = True
    else:
        process_solar = args.solar
        process_wind = args.wind

    if not process_solar and not process_wind:
        logger.error("请指定要处理的数据类型: --solar, --wind, 或 --all")
        parser.print_help()
        sys.exit(1)

    # 获取项目路径
    current_file = os.path.abspath(__file__)
    src_dir = os.path.dirname(current_file)
    resource_dir = os.path.dirname(src_dir)

    # 输入数据路径（12周数据）
    typical_weeks_dir = os.path.join(resource_dir, 'results', 'typical_weeks_data')

    # 输出数据路径
    output_dir = typical_weeks_dir

    logger.info("="*80)
    logger.info("可再生能源数据100km筛选工具（12周数据）")
    logger.info("="*80)
    logger.info(f"输入数据目录: {typical_weeks_dir}")
    logger.info(f"输出数据目录: {output_dir}")
    logger.info(f"筛选距离: {args.distance}km")
    logger.info(f"并行进程数: {args.workers if args.workers else cpu_count()}")
    logger.info("="*80)

    # 统计信息
    total_original = 0
    total_filtered = 0

    # 处理太阳能数据
    if process_solar:
        # 查找最新的12周太阳能数据文件
        solar_files = [f for f in os.listdir(typical_weeks_dir) if f.startswith('typical_12weeks_solar') and f.endswith('.csv')]
        if solar_files:
            solar_files.sort(reverse=True)
            solar_input = os.path.join(typical_weeks_dir, solar_files[0])
            solar_output = os.path.join(output_dir, 'solar_hourly_100km.csv')

            logger.info(f"找到太阳能数据文件: {solar_files[0]}")
            orig, filt = filter_renewable_data_100km(
                solar_input,
                solar_output,
                max_distance_km=args.distance,
                max_workers=args.workers
            )
            total_original += orig
            total_filtered += filt
        else:
            logger.error(f"未找到12周太阳能数据文件: typical_12weeks_solar_*.csv")

    # 处理风电数据
    if process_wind:
        # 查找最新的12周风电数据文件
        wind_files = [f for f in os.listdir(typical_weeks_dir) if f.startswith('typical_12weeks_wind') and f.endswith('.csv')]
        if wind_files:
            wind_files.sort(reverse=True)
            wind_input = os.path.join(typical_weeks_dir, wind_files[0])
            wind_output = os.path.join(output_dir, 'wind_hourly_100km.csv')

            logger.info(f"找到风电数据文件: {wind_files[0]}")
            orig, filt = filter_renewable_data_100km(
                wind_input,
                wind_output,
                max_distance_km=args.distance,
                max_workers=args.workers
            )
            total_original += orig
            total_filtered += filt
        else:
            logger.error(f"未找到12周风电数据文件: typical_12weeks_wind_*.csv")

    # 总结
    logger.info("="*80)
    logger.info("筛选完成！")
    logger.info("="*80)
    logger.info(f"总原始记录数: {total_original:,}")
    logger.info(f"总筛选记录数: {total_filtered:,}")
    if total_original > 0:
        logger.info(f"总体保留率: {total_filtered/total_original*100:.2f}%")
    logger.info("="*80)

    logger.info("\n生成的100km筛选数据文件:")
    logger.info(f"  输出目录: {output_dir}")
    logger.info("  - solar_hourly_100km.csv")
    logger.info("  - wind_hourly_100km.csv")


if __name__ == '__main__':
    main()
