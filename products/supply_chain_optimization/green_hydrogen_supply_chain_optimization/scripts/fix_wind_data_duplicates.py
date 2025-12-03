"""
风能数据去重修复脚本
修复同名但位置不同导致的重复数据问题

Author: Claude Code
Date: 2025-11-28
"""

import os
import sys
import pandas as pd
import logging
from pathlib import Path
from datetime import datetime
from multiprocessing import Pool, cpu_count

# 设置项目根目录
project_root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(project_root))


def setup_logger(log_dir: str) -> logging.Logger:
    """配置日志系统"""
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, 'wind_data_fix.log')

    logger = logging.getLogger('wind_data_fix')
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    file_handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
    file_handler.setLevel(logging.INFO)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logger.info("="*80)
    logger.info("风能数据去重修复脚本启动")
    logger.info(f"日志文件: {log_file}")
    logger.info("="*80)

    return logger


def process_single_plant(args):
    """处理单个电站的零填充（必须在模块级别定义以支持multiprocessing）"""
    plant_id, group_df = args
    full_hour_range = pd.DataFrame({'hour': range(8784)})

    merged = full_hour_range.merge(
        group_df[['hour', 'power_output_mw', 'capacity_mw', 'latitude', 'longitude', 'type', 'plant_name', 'plant_id']],
        on='hour',
        how='left'
    )

    merged['power_output_mw'] = merged['power_output_mw'].fillna(0)
    merged['capacity_mw'] = merged['capacity_mw'].bfill().ffill()
    merged['latitude'] = merged['latitude'].bfill().ffill()
    merged['longitude'] = merged['longitude'].bfill().ffill()
    merged['type'] = merged['type'].bfill().ffill()
    merged['plant_name'] = merged['plant_name'].bfill().ffill()
    merged['plant_id'] = plant_id

    return merged


def main():
    """主流程"""
    overall_start_time = datetime.now()

    print("="*80)
    print("风能数据去重修复")
    print("修复同名但位置不同导致的重复数据问题")
    print("="*80)

    # 设置路径
    input_path = project_root / 'products' / 'aviation_fuel_analysis' / 'resource_flight_data_process' / 'results' / 'preprocessed' / 'wind_hourly_complete.csv'
    output_dir = project_root / 'products' / 'aviation_fuel_analysis' / 'resource_flight_data_process' / 'results' / 'preprocessed'
    log_dir = output_dir / 'logs'

    logger = setup_logger(str(log_dir))

    try:
        # 步骤1: 加载数据
        logger.info("="*80)
        logger.info("步骤1: 加载风能数据")
        logger.info("="*80)
        logger.info(f"输入文件: {input_path}")

        start_time = datetime.now()
        df = pd.read_csv(str(input_path), encoding='utf-8-sig')
        logger.info(f"加载完成，耗时: {(datetime.now() - start_time).total_seconds():.1f} 秒")
        logger.info(f"原始记录数: {len(df):,}")
        logger.info(f"电站名称数量: {df['plant_name'].nunique():,}")

        # 步骤2: 创建唯一标识符
        logger.info("="*80)
        logger.info("步骤2: 创建plant_id（站点名称+位置）")
        logger.info("="*80)

        start_time = datetime.now()
        df['plant_id'] = (
            df['plant_name'] + '_' +
            df['latitude'].round(4).astype(str) + '_' +
            df['longitude'].round(4).astype(str)
        )
        logger.info(f"plant_id创建完成，耗时: {(datetime.now() - start_time).total_seconds():.1f} 秒")
        logger.info(f"唯一电站数量（含位置）: {df['plant_id'].nunique():,}")

        # 检查多位置站点
        location_counts = df.groupby('plant_name')[['latitude', 'longitude']].nunique()
        plants_multi_locations = location_counts[(location_counts['latitude'] > 1) | (location_counts['longitude'] > 1)]
        logger.info(f"有多个位置的站点名称数量: {len(plants_multi_locations)}")

        # 步骤3: 检查并去除重复数据
        logger.info("="*80)
        logger.info("步骤3: 检查并去除重复数据")
        logger.info("="*80)

        start_time = datetime.now()
        n_before = len(df)
        duplicates = df.duplicated(subset=['plant_id', 'hour'], keep=False)
        n_duplicates = duplicates.sum()
        logger.info(f"发现重复记录: {n_duplicates:,} 条 ({n_duplicates/n_before*100:.2f}%)")

        if n_duplicates > 0:
            # 对于重复记录，使用平均值进行合并
            logger.info("对重复记录按(plant_id, hour)进行聚合（使用均值）...")
            agg_dict = {
                'power_output_mw': 'mean',
                'capacity_mw': 'first',
                'latitude': 'first',
                'longitude': 'first',
                'type': 'first',
                'plant_name': 'first'
            }
            df = df.groupby(['plant_id', 'hour'], as_index=False).agg(agg_dict)
            logger.info(f"去重后记录数: {len(df):,} 条")
            logger.info(f"减少了: {n_before - len(df):,} 条记录")
            logger.info(f"去重耗时: {(datetime.now() - start_time).total_seconds():.1f} 秒")

        # 步骤4: 验证数据完整性
        logger.info("="*80)
        logger.info("步骤4: 验证数据完整性")
        logger.info("="*80)

        plant_hour_counts = df.groupby('plant_id')['hour'].count()
        logger.info(f"每个电站的小时数统计:")
        logger.info(f"  最小值: {plant_hour_counts.min()}")
        logger.info(f"  最大值: {plant_hour_counts.max()}")
        logger.info(f"  平均值: {plant_hour_counts.mean():.1f}")

        all_complete = (plant_hour_counts == 8784).all()
        logger.info(f"  所有电站都有8784小时: {all_complete}")

        if not all_complete:
            # 如果还有不完整的数据，进行零填充
            logger.info("发现数据不完整，开始零填充...")

            logger.info("使用并行处理进行零填充...")
            n_workers = min(96, cpu_count())
            logger.info(f"使用 {n_workers} 个CPU核心")

            plant_groups = [(plant_id, group) for plant_id, group in df.groupby('plant_id')]

            with Pool(processes=n_workers) as pool:
                results = []
                for idx, result in enumerate(pool.imap_unordered(process_single_plant, plant_groups), 1):
                    results.append(result)
                    if idx % 500 == 0:
                        logger.info(f"零填充进度: {idx}/{len(plant_groups)} ({idx/len(plant_groups)*100:.1f}%)")

            df = pd.concat(results, ignore_index=True)
            logger.info(f"零填充完成，最终记录数: {len(df):,}")

        # 步骤5: 保存修复后的数据
        logger.info("="*80)
        logger.info("步骤5: 保存修复后的数据")
        logger.info("="*80)

        output_path = output_dir / 'wind_hourly_complete.csv'
        logger.info(f"保存到: {output_path}")

        start_time = datetime.now()
        df.to_csv(str(output_path), index=False, encoding='utf-8-sig')
        logger.info(f"保存完成，耗时: {(datetime.now() - start_time).total_seconds():.1f} 秒")
        logger.info(f"文件大小: {os.path.getsize(output_path)/(1024**3):.2f} GB")

        # 最终验证
        logger.info("="*80)
        logger.info("最终验证")
        logger.info("="*80)

        final_duplicates = df.duplicated(subset=['plant_id', 'hour'], keep=False).sum()
        final_plant_counts = df.groupby('plant_id')['hour'].count()

        logger.info(f"重复记录数: {final_duplicates}")
        logger.info(f"每个电站的小时数: 最小={final_plant_counts.min()}, 最大={final_plant_counts.max()}")
        logger.info(f"所有电站都有8784小时: {(final_plant_counts == 8784).all()}")

        total_time = (datetime.now() - overall_start_time).total_seconds() / 60

        logger.info("="*80)
        logger.info("风能数据去重修复完成！")
        logger.info(f"总耗时: {total_time:.1f} 分钟")
        logger.info("="*80)

    except Exception as e:
        logger.error(f"处理错误: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
