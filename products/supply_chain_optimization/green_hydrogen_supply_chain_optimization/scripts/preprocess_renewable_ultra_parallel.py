"""
可再生能源数据预处理脚本（超级并行版本）
太阳能和风电数据同时处理，充分利用192核心和大内存

Author: Claude Code
Date: 2025-11-27
"""

import os
import sys
import yaml
import pandas as pd
import logging
import gc
from pathlib import Path
from datetime import datetime
from multiprocessing import Pool, cpu_count, Process, Queue
import numpy as np

# 设置项目根目录
project_root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(project_root))

# 导入可视化模块
try:
    from products.supply_chain_optimization.green_hydrogen_supply_chain_optimization.src.visualization.renewable_24h_pattern_visualization import visualize_24h_renewable_pattern
    VISUALIZATION_AVAILABLE = True
except ImportError:
    VISUALIZATION_AVAILABLE = False


def setup_logger(log_dir: str, log_name: str) -> logging.Logger:
    """配置日志系统"""
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f'{log_name}.log')

    logger = logging.getLogger(log_name)
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
    logger.info(f"{log_name} 启动")
    logger.info(f"日志文件: {log_file}")
    logger.info("="*80)

    return logger


def load_config(config_path: str) -> dict:
    """加载配置文件"""
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    return config


def get_data_path(config: dict, key_path: str, project_root: Path) -> str:
    """获取数据路径"""
    keys = key_path.split('.')
    value = config
    for key in keys:
        value = value[key]

    if not os.path.isabs(value):
        value = os.path.join(project_root, value)

    return value


# ==================== 太阳能数据处理 ====================

def load_single_solar_batch(file_path: str) -> pd.DataFrame:
    """加载单个太阳能批次文件"""
    try:
        df = pd.read_csv(file_path, encoding='utf-8-sig')
        # 原始数据是UTC时间，转换为北京时间（UTC+8）
        df['timestamp'] = pd.to_datetime(df['timestamp']) + pd.Timedelta(hours=8)
        df = df[df['timestamp'].dt.year == 2020]

        if len(df) == 0:
            return pd.DataFrame()

        # 使用全局固定起始时间：2020-01-01 00:00:00（北京时间）
        start_time = pd.Timestamp('2020-01-01 00:00:00')
        df['hour'] = ((df['timestamp'] - start_time).dt.total_seconds() // 3600).astype(int)
        df = df[df['hour'] < 8784]

        result = df[['plant_name', 'latitude', 'longitude', 'capacity_mw', 'power_output_mw', 'hour']].copy()
        result['type'] = 'solar_farm'

        return result
    except Exception as e:
        print(f"读取太阳能文件 {file_path} 失败: {e}")
        return pd.DataFrame()


def process_single_plant(args):
    """处理单个电站的零填充"""
    plant_name, plant_data_dict, total_hours = args

    plant_data = pd.DataFrame(plant_data_dict)
    full_hour_range = pd.DataFrame({'hour': range(total_hours)})

    merged = full_hour_range.merge(
        plant_data[['hour', 'power_output_mw', 'capacity_mw', 'latitude', 'longitude', 'type']],
        on='hour',
        how='left'
    )

    merged['power_output_mw'] = merged['power_output_mw'].fillna(0)
    merged['capacity_mw'] = merged['capacity_mw'].bfill().ffill()
    merged['latitude'] = merged['latitude'].bfill().ffill()
    merged['longitude'] = merged['longitude'].bfill().ffill()
    merged['type'] = merged['type'].bfill().ffill()
    merged['plant_name'] = plant_name

    return merged


def process_solar_data(config, project_root, n_workers):
    """处理太阳能数据的独立进程"""
    log_dir = get_data_path(config, 'data_paths.aviation_data.preprocessed_data_dir', project_root)
    log_dir = os.path.join(log_dir, 'logs')
    logger = setup_logger(log_dir, 'solar_ultra_parallel')

    try:
        solar_data_dir = get_data_path(config, 'data_paths.aviation_data.solar_data_dir', project_root)
        output_dir = get_data_path(config, 'data_paths.aviation_data.preprocessed_data_dir', project_root)

        logger.info(f"太阳能数据目录: {solar_data_dir}")
        logger.info(f"使用 {n_workers} 个核心")

        # 步骤1: 并行加载
        logger.info("步骤1: 并行加载太阳能数据")
        # 只加载按月组织的新格式文件，排除旧的batch文件
        batch_files = [
            os.path.join(solar_data_dir, f)
            for f in os.listdir(solar_data_dir)
            if f.startswith('solar_generation_month') and f.endswith('.csv')
        ]
        batch_files.sort()
        logger.info(f"找到 {len(batch_files)} 个批次文件（12个月，全年数据）")

        start_time = datetime.now()
        optimal_chunksize = max(1, len(batch_files) // (n_workers * 2))

        with Pool(processes=n_workers) as pool:
            results = []
            for idx, result in enumerate(pool.imap(load_single_solar_batch, batch_files, chunksize=optimal_chunksize), 1):
                if not result.empty:
                    results.append(result)
                if idx % 10 == 0:
                    logger.info(f"太阳能加载进度: {idx}/{len(batch_files)}")

        logger.info(f"太阳能加载完成，耗时: {(datetime.now() - start_time).total_seconds():.1f} 秒")

        solar_data = pd.concat(results, ignore_index=True)
        logger.info(f"成功加载 {len(solar_data)} 条，{solar_data['plant_name'].nunique()} 个电站")

        # 步骤2: 并行零填充（使用groupby优化）
        logger.info("步骤2: 并行零填充太阳能数据")
        start_time = datetime.now()

        logger.info("使用groupby进行高速数据分组...")
        prep_start = datetime.now()
        plant_data_list = []
        for plant_name, group_df in solar_data.groupby('plant_name', sort=False):
            plant_data_dict = group_df.to_dict('list')
            plant_data_list.append((plant_name, plant_data_dict, 8784))

        logger.info(f"数据分组完成，耗时: {(datetime.now() - prep_start).total_seconds():.1f} 秒")

        optimal_chunksize = max(1, len(plant_data_list) // (n_workers * 4))
        logger.info(f"使用chunksize: {optimal_chunksize}")

        with Pool(processes=n_workers) as pool:
            results = []
            for idx, result in enumerate(pool.imap_unordered(process_single_plant, plant_data_list, chunksize=optimal_chunksize), 1):
                results.append(result)
                if idx % 1000 == 0:
                    logger.info(f"太阳能零填充进度: {idx}/{len(plant_data_list)}")

        logger.info(f"太阳能零填充完成，耗时: {(datetime.now() - start_time).total_seconds()/60:.1f} 分钟")

        complete_solar_data = pd.concat(results, ignore_index=True)
        del solar_data, results
        gc.collect()

        # 步骤3: 保存数据
        logger.info("步骤3: 保存太阳能数据")
        os.makedirs(output_dir, exist_ok=True)

        csv_path = os.path.join(output_dir, 'solar_hourly_complete.csv')
        logger.info(f"保存CSV到: {csv_path}")
        complete_solar_data.to_csv(csv_path, index=False, encoding='utf-8-sig')
        logger.info(f"CSV保存完成: {os.path.getsize(csv_path)/(1024**3):.2f} GB")

        parquet_path = os.path.join(output_dir, 'solar_hourly_complete.parquet')
        logger.info(f"保存Parquet到: {parquet_path}")
        complete_solar_data.to_parquet(parquet_path, index=False, engine='pyarrow', compression='snappy')
        logger.info(f"Parquet保存完成: {os.path.getsize(parquet_path)/(1024**3):.2f} GB")

        logger.info("太阳能数据处理完成！")

    except Exception as e:
        logger.error(f"太阳能处理错误: {e}", exc_info=True)
        raise


# ==================== 风电数据处理 ====================

def interpolate_wind_to_hourly(wind_df: pd.DataFrame) -> pd.DataFrame:
    """将风电3小时数据插值到每小时"""
    hourly_data = []

    # 使用全局固定起始时间：2024-01-01 00:00:00（北京时间）
    start_time = pd.Timestamp('2024-01-01 00:00:00')

    for row in wind_df.itertuples():
        timestamp = row.timestamp
        generation_3h = row.generation_3h_mwh
        hourly_generation = generation_3h

        for i in range(3):
            hour_timestamp = timestamp + pd.Timedelta(hours=i)
            hour_from_start = (hour_timestamp - start_time).total_seconds() // 3600

            hourly_data.append({
                'plant_name': row.farm_name,
                'type': 'wind_farm',
                'latitude': row.latitude,
                'longitude': row.longitude,
                'capacity_mw': row.capacity_mw,
                'power_output_mw': hourly_generation,
                'hour': int(hour_from_start)
            })

    return pd.DataFrame(hourly_data)


def load_single_wind_file(file_path: str) -> pd.DataFrame:
    """加载单个风电文件"""
    try:
        df = pd.read_csv(file_path)
        # 原始数据是UTC时间，转换为北京时间（UTC+8）
        df['timestamp'] = pd.to_datetime(df['timestamp']) + pd.Timedelta(hours=8)
        df = df[df['timestamp'].dt.year == 2024]

        if len(df) == 0:
            return pd.DataFrame()

        df_hourly = interpolate_wind_to_hourly(df)
        df_hourly = df_hourly[df_hourly['hour'] < 8784]

        return df_hourly
    except Exception as e:
        print(f"读取风电文件 {file_path} 失败: {e}")
        return pd.DataFrame()


def process_wind_data(config, project_root, n_workers):
    """处理风电数据的独立进程"""
    log_dir = get_data_path(config, 'data_paths.aviation_data.preprocessed_data_dir', project_root)
    log_dir = os.path.join(log_dir, 'logs')
    logger = setup_logger(log_dir, 'wind_ultra_parallel')

    try:
        wind_data_dir = get_data_path(config, 'data_paths.aviation_data.wind_data_dir', project_root)
        output_dir = get_data_path(config, 'data_paths.aviation_data.preprocessed_data_dir', project_root)

        logger.info(f"风电数据目录: {wind_data_dir}")
        logger.info(f"使用 {n_workers} 个核心")

        # 步骤1: 并行加载
        logger.info("步骤1: 并行加载风电数据")
        wind_files = [
            os.path.join(wind_data_dir, f)
            for f in os.listdir(wind_data_dir)
            if f.endswith('.csv') and 'wind_farms_3hourly_generation' in f
        ]
        wind_files.sort()
        logger.info(f"找到 {len(wind_files)} 个风电文件")

        start_time = datetime.now()
        optimal_chunksize = max(1, len(wind_files) // (n_workers * 2))

        with Pool(processes=n_workers) as pool:
            results = []
            for idx, result in enumerate(pool.imap(load_single_wind_file, wind_files, chunksize=optimal_chunksize), 1):
                if not result.empty:
                    results.append(result)
                if idx % 10 == 0:
                    logger.info(f"风电加载进度: {idx}/{len(wind_files)}")

        logger.info(f"风电加载完成，耗时: {(datetime.now() - start_time).total_seconds():.1f} 秒")

        wind_data = pd.concat(results, ignore_index=True)
        logger.info(f"成功加载 {len(wind_data)} 条，{wind_data['plant_name'].nunique()} 个风电场")

        # 步骤2: 并行零填充（使用groupby优化）
        logger.info("步骤2: 并行零填充风电数据")
        start_time = datetime.now()

        logger.info("使用groupby进行高速数据分组...")
        prep_start = datetime.now()
        plant_data_list = []
        for plant_name, group_df in wind_data.groupby('plant_name', sort=False):
            plant_data_dict = group_df.to_dict('list')
            plant_data_list.append((plant_name, plant_data_dict, 8784))

        logger.info(f"数据分组完成，耗时: {(datetime.now() - prep_start).total_seconds():.1f} 秒")

        optimal_chunksize = max(1, len(plant_data_list) // (n_workers * 4))
        logger.info(f"使用chunksize: {optimal_chunksize}")

        with Pool(processes=n_workers) as pool:
            results = []
            for idx, result in enumerate(pool.imap_unordered(process_single_plant, plant_data_list, chunksize=optimal_chunksize), 1):
                results.append(result)
                if idx % 500 == 0:
                    logger.info(f"风电零填充进度: {idx}/{len(plant_data_list)}")

        logger.info(f"风电零填充完成，耗时: {(datetime.now() - start_time).total_seconds()/60:.1f} 分钟")

        complete_wind_data = pd.concat(results, ignore_index=True)
        del wind_data, results
        gc.collect()

        # 步骤3: 保存数据
        logger.info("步骤3: 保存风电数据")
        os.makedirs(output_dir, exist_ok=True)

        csv_path = os.path.join(output_dir, 'wind_hourly_complete.csv')
        logger.info(f"保存CSV到: {csv_path}")
        complete_wind_data.to_csv(csv_path, index=False, encoding='utf-8-sig')
        logger.info(f"CSV保存完成: {os.path.getsize(csv_path)/(1024**3):.2f} GB")

        parquet_path = os.path.join(output_dir, 'wind_hourly_complete.parquet')
        logger.info(f"保存Parquet到: {parquet_path}")
        complete_wind_data.to_parquet(parquet_path, index=False, engine='pyarrow', compression='snappy')
        logger.info(f"Parquet保存完成: {os.path.getsize(parquet_path)/(1024**3):.2f} GB")

        logger.info("风电数据处理完成！")

    except Exception as e:
        logger.error(f"风电处理错误: {e}", exc_info=True)
        raise


def main():
    """主流程 - 太阳能和风电同时并行处理"""
    overall_start_time = datetime.now()

    print("="*80)
    print("可再生能源数据预处理（超级并行版本）")
    print("太阳能和风电数据将同时处理，充分利用192核心")
    print("="*80)

    # 加载配置
    config_path = project_root / 'shared' / 'data' / 'GreenHydrogenSupplyChainOptimizer_config.yaml'
    config = load_config(str(config_path))

    # CPU核心分配：每个任务使用96核心
    available_cores = cpu_count()
    n_workers_per_task = min(96, available_cores // 2)

    print(f"系统可用CPU核心: {available_cores}")
    print(f"每个任务分配: {n_workers_per_task} 个核心")
    print(f"总计使用: {n_workers_per_task * 2} 个核心")
    print()

    # 创建两个独立进程，同时处理太阳能和风电
    solar_process = Process(target=process_solar_data, args=(config, project_root, n_workers_per_task))
    wind_process = Process(target=process_wind_data, args=(config, project_root, n_workers_per_task))

    print("启动太阳能处理进程...")
    solar_process.start()

    print("启动风电处理进程...")
    wind_process.start()

    print()
    print("两个处理进程已启动，正在并行处理...")
    print("请查看日志文件获取详细进度：")
    print("  - solar_ultra_parallel.log")
    print("  - wind_ultra_parallel.log")
    print()

    # 等待两个进程完成
    solar_process.join()
    wind_process.join()

    total_time = (datetime.now() - overall_start_time).total_seconds() / 60

    print()
    print("="*80)
    print("所有可再生能源数据预处理完成！")
    print(f"总耗时: {total_time:.1f} 分钟")
    print("="*80)


if __name__ == "__main__":
    main()
