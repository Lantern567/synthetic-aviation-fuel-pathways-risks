"""
筛选北京500km范围内的可再生能源电站数据
Filter renewable energy plants within 500km of Beijing

This script pre-filters the complete hourly renewable energy data to only include
plants within 500km of Beijing, significantly reducing data loading time for optimization.

使用方法 (Usage):
    python filter_500km_renewable_data.py --solar --wind
    python filter_500km_renewable_data.py --all
"""

import os
import sys
import gc
import argparse
import pandas as pd
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from math import radians, sin, cos, sqrt, atan2
from typing import List, Tuple

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


def is_within_beijing_range(lat: float, lon: float, max_distance_km: float = 500) -> bool:
    """
    检查坐标是否在北京指定范围内

    Args:
        lat, lon: 检查点的纬度经度
        max_distance_km: 最大距离（公里），默认500公里

    Returns:
        bool: 是否在范围内
    """
    # 北京市中心坐标（天安门）
    beijing_lat = 39.9042
    beijing_lon = 116.4074

    distance = calculate_distance_km(lat, lon, beijing_lat, beijing_lon)
    return distance <= max_distance_km


# ==================== 并行筛选函数 ====================

def filter_plant_worker(args: Tuple[str, pd.DataFrame, float]) -> pd.DataFrame:
    """
    并行筛选单个电站的worker函数

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


def filter_renewable_data_500km(
    input_file: str,
    output_file: str,
    max_distance_km: float = 500,
    max_workers: int = 128
) -> Tuple[int, int]:
    """
    筛选500km范围内的可再生能源数据

    Args:
        input_file: 输入CSV文件路径
        output_file: 输出CSV文件路径
        max_distance_km: 最大距离（公里）
        max_workers: 并行worker数量

    Returns:
        (original_count, filtered_count): 原始记录数和筛选后记录数
    """
    logger.info("="*80)
    logger.info(f"开始筛选数据: {os.path.basename(input_file)}")
    logger.info(f"筛选范围: 北京{max_distance_km}km以内")
    logger.info("="*80)

    # 读取数据
    logger.info(f"读取数据: {input_file}")
    df = pd.read_csv(input_file)
    original_count = len(df)
    original_plants = df['plant_name'].nunique()
    logger.info(f"原始数据: {original_count:,} 条记录, {original_plants:,} 个电站")

    # 使用groupby分组，比列表推导式快得多
    logger.info("按电站名称分组数据...")
    grouped = df.groupby('plant_name', sort=False)
    plant_count = len(grouped)
    logger.info(f"使用{max_workers}个并行workers处理{plant_count:,}个电站")

    # 准备并行处理参数（使用groupby迭代器，避免重复筛选）
    logger.info("准备并行处理参数...")
    plant_data_list = [
        (plant_name, plant_data, max_distance_km)
        for plant_name, plant_data in grouped
    ]

    # 释放原始DataFrame以节省内存
    del df, grouped
    gc.collect()
    logger.info(f"已准备{len(plant_data_list):,}个电站的数据")

    # 并行筛选
    logger.info("开始并行筛选电站...")
    filtered_plants = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(filter_plant_worker, plant_data_list))

        for result in results:
            if result is not None:
                filtered_plants.append(result)

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
        filtered_plants_count = filtered_df['plant_name'].nunique()

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
        description='筛选北京500km范围内的可再生能源电站数据'
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
        default=500,
        help='筛选距离（公里），默认500km'
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=128,
        help='并行worker数量，默认128'
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

    # 数据路径
    preprocessed_dir = os.path.join(resource_dir, 'results', 'preprocessed')

    logger.info("="*80)
    logger.info("可再生能源数据500km筛选工具")
    logger.info("="*80)
    logger.info(f"预处理数据目录: {preprocessed_dir}")
    logger.info(f"筛选距离: {args.distance}km")
    logger.info(f"并行workers: {args.workers}")
    logger.info("="*80)

    # 统计信息
    total_original = 0
    total_filtered = 0

    # 处理太阳能数据
    if process_solar:
        solar_input = os.path.join(preprocessed_dir, 'solar_hourly_complete.csv')
        solar_output = os.path.join(preprocessed_dir, 'solar_hourly_500km.csv')

        if os.path.exists(solar_input):
            orig, filt = filter_renewable_data_500km(
                solar_input,
                solar_output,
                max_distance_km=args.distance,
                max_workers=args.workers
            )
            total_original += orig
            total_filtered += filt
        else:
            logger.error(f"未找到太阳能数据文件: {solar_input}")

    # 处理风电数据
    if process_wind:
        wind_input = os.path.join(preprocessed_dir, 'wind_hourly_complete.csv')
        wind_output = os.path.join(preprocessed_dir, 'wind_hourly_500km.csv')

        if os.path.exists(wind_input):
            orig, filt = filter_renewable_data_500km(
                wind_input,
                wind_output,
                max_distance_km=args.distance,
                max_workers=args.workers
            )
            total_original += orig
            total_filtered += filt
        else:
            logger.error(f"未找到风电数据文件: {wind_input}")

    # 总结
    logger.info("="*80)
    logger.info("筛选完成！")
    logger.info("="*80)
    logger.info(f"总原始记录数: {total_original:,}")
    logger.info(f"总筛选记录数: {total_filtered:,}")
    logger.info(f"总体保留率: {total_filtered/total_original*100:.2f}%")
    logger.info("="*80)

    logger.info("\n下一步:")
    logger.info("修改优化模型配置，使用筛选后的数据文件:")
    logger.info("  - solar_hourly_500km.csv")
    logger.info("  - wind_hourly_500km.csv")


if __name__ == '__main__':
    main()
