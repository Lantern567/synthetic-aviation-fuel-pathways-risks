"""
并行航班数据燃油消耗计算程序
使用多进程提高计算速度
"""

import os
import sys
import pandas as pd
import numpy as np
import time
from datetime import datetime
from pathlib import Path
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, as_completed
import psutil
from functools import partial
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 添加当前目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from pybada_fuel_calculator import PyBADAFuelCalculator, process_flight_data_with_pybada, PYBADA_AVAILABLE

def get_optimal_worker_count():
    """
    获取最佳工作进程数 - 考虑虚拟内存限制
    
    Returns:
        int: 推荐的工作进程数
    """
    cpu_count = mp.cpu_count()
    memory_gb = psutil.virtual_memory().total / (1024**3)
    
    # 获取虚拟内存信息
    virtual_memory = psutil.virtual_memory()
    swap_memory = psutil.swap_memory()
    
    # 计算可用内存（物理内存 + 交换文件）
    total_available_gb = (virtual_memory.available + swap_memory.free) / (1024**3)
    
    # 保守估算：每个进程需要约3-4GB内存（包括pandas、numpy等）
    memory_per_process_gb = 4.0
    memory_based_workers = max(1, int(total_available_gb / memory_per_process_gb))
    
    # 限制最大进程数，避免系统过载
    max_safe_workers = min(8, cpu_count // 2)  # 最多8个进程，且不超过CPU核心数的一半
    
    # 选择最保守的配置
    optimal_workers = min(memory_based_workers, max_safe_workers)
    optimal_workers = max(1, optimal_workers)  # 至少1个工作进程
    
    print(f"🖥️  系统信息:")
    print(f"   CPU核心数: {cpu_count}")
    print(f"   总内存: {memory_gb:.1f} GB")
    print(f"   可用内存: {virtual_memory.available / (1024**3):.1f} GB")
    print(f"   交换文件: {swap_memory.total / (1024**3):.1f} GB")
    print(f"   可用交换: {swap_memory.free / (1024**3):.1f} GB")
    print(f"   总可用: {total_available_gb:.1f} GB")
    print(f"   推荐工作进程数: {optimal_workers}")
    
    return optimal_workers

def process_chunk_worker(chunk_data):
    """
    工作进程函数：处理单个数据块 - 优化内存使用
    
    Args:
        chunk_data: 要处理的数据块 (chunk_id, chunk_df)
        
    Returns:
        tuple: (chunk_id, 处理结果, 统计信息)
    """
    chunk_id, df_chunk = chunk_data
    
    try:
        start_time = time.time()
        
        # 清理内存
        import gc
        gc.collect()
        
        # 检查进程内存使用
        process = psutil.Process()
        initial_memory = process.memory_info().rss / (1024**2)  # MB
        
        # 重新映射字段名称到计算函数需要的格式
        df_chunk_mapped = df_chunk.copy()
        df_chunk_mapped['aircraft_type'] = df_chunk_mapped['机型']
        df_chunk_mapped['distance_km'] = df_chunk_mapped['里程（公里）']
        df_chunk_mapped['passengers'] = df_chunk_mapped['人数']
        
        # 🔍 添加日期信息处理
        date_columns = [col for col in df_chunk_mapped.columns if '日期' in col]
        if date_columns:
            date_col = date_columns[0]
            # 确保日期格式正确
            df_chunk_mapped[date_col] = pd.to_datetime(df_chunk_mapped[date_col], errors='coerce')
            # 添加年月字段用于燃油价格计算
            df_chunk_mapped['flight_year_month'] = df_chunk_mapped[date_col].dt.strftime('%Y-%m')
            print(f"✅ Chunk {chunk_id}: 添加日期信息字段 'flight_year_month'")
            
            # 显示当前chunk的日期分布
            date_counts = df_chunk_mapped['flight_year_month'].value_counts().sort_index()
            print(f"📅 Chunk {chunk_id} 日期分布: {dict(date_counts.head())}")
        else:
            print(f"⚠️ Chunk {chunk_id}: 未找到日期列，使用默认日期")
            df_chunk_mapped['flight_year_month'] = '2024-12'
        
        # 删除原始数据框以释放内存
        del df_chunk
        gc.collect()
        
        # 在工作进程中初始化计算器，并传递日期信息
        processed_chunk = process_flight_data_with_pybada_enhanced(df_chunk_mapped)
        
        # 清理映射数据
        del df_chunk_mapped
        gc.collect()
        
        # 添加计算方法标识
        processed_chunk['计算方法'] = 'pybada'
        
        # 统计信息
        success_count = len(processed_chunk[processed_chunk['calculation_successful'] == True])
        failed_count = len(processed_chunk[processed_chunk['calculation_successful'] == False])
        processing_time = time.time() - start_time
        
        # 检查最终内存使用
        final_memory = process.memory_info().rss / (1024**2)  # MB
        
        stats = {
            'chunk_id': chunk_id,
            'total_records': len(processed_chunk),
            'success_count': success_count,
            'failed_count': failed_count,
            'processing_time': processing_time,
            'success_rate': success_count / len(processed_chunk) * 100 if len(processed_chunk) > 0 else 0,
            'memory_usage_mb': final_memory - initial_memory,
            'process_id': process.pid
        }
        
        # 最后一次清理
        gc.collect()
        
        return chunk_id, processed_chunk, stats
        
    except MemoryError as e:
        # 内存错误特殊处理
        error_stats = {
            'chunk_id': chunk_id,
            'total_records': len(df_chunk) if df_chunk is not None else 0,
            'success_count': 0,
            'failed_count': len(df_chunk) if df_chunk is not None else 0,
            'processing_time': 0,
            'success_rate': 0,
            'error': f"内存不足: {str(e)}",
            'error_type': 'MemoryError'
        }
        return chunk_id, None, error_stats
        
    except Exception as e:
        # 其他错误处理
        error_stats = {
            'chunk_id': chunk_id,
            'total_records': len(df_chunk) if df_chunk is not None else 0,
            'success_count': 0,
            'failed_count': len(df_chunk) if df_chunk is not None else 0,
            'processing_time': 0,
            'success_rate': 0,
            'error': str(e),
            'error_type': type(e).__name__
        }
        return chunk_id, None, error_stats

def process_flight_data_with_pybada_enhanced(df: pd.DataFrame) -> pd.DataFrame:
    """处理航班数据并计算燃油消耗和排放 - 增强版本支持日期参数"""
    if not PYBADA_AVAILABLE:
        logger.error("pyBADA库不可用，无法处理数据")
        return df
    
    calculator = PyBADAFuelCalculator()
    results = []
    
    for idx, row in df.iterrows():
        try:
            aircraft_type = row.get('aircraft_type', 'A320')
            distance_km = row.get('distance_km', 0)
            passengers = row.get('passengers', 150)
            flight_year_month = row.get('flight_year_month', '2024-12')  # 获取航班日期
            
            if distance_km <= 0:
                logger.warning(f"第{idx}行距离无效: {distance_km}")
                continue
            
            # 调用单个航班计算，传递日期信息
            result = calculator.calculate_single_flight_with_date(
                aircraft_type, distance_km, passengers, flight_year_month
            )
            result['original_index'] = idx
            result['flight_date'] = flight_year_month  # 保存航班日期
            results.append(result)
            
            if idx % 10 == 0:
                logger.info(f"已处理 {idx+1}/{len(df)} 条记录")
                
        except Exception as e:
            logger.error(f"处理第{idx}行数据时出错: {e}")
            continue
    
    if not results:
        logger.warning("没有成功处理任何数据")
        return df
    
    # 创建结果DataFrame
    results_df = pd.DataFrame(results)
    
    # 合并原始数据和计算结果
    final_df = df.copy()
    for col in results_df.columns:
        if col != 'original_index':
            final_df[col] = None
    
    for _, result_row in results_df.iterrows():
        idx = result_row['original_index']
        for col in results_df.columns:
            if col != 'original_index':
                final_df.loc[idx, col] = result_row[col]
    
    logger.info(f"✅ 成功处理 {len(results)} 条航班数据")
    return final_df

def load_and_split_data(file_path: str, chunk_size: int = 1000):
    """
    加载数据并分割为块 - 优化版：适用于已筛选的数据文件
    
    Args:
        file_path: 数据文件路径
        chunk_size: 每块的记录数
        
    Returns:
        list: 数据块列表 [(chunk_id, chunk_df), ...]
    """
    print(f"📖 加载和分割数据: {file_path}")
    
    try:
        # 读取全部数据
        print("正在读取Excel文件...")
        all_data = pd.read_excel(file_path)
        print(f"数据读取完成，总计 {len(all_data):,} 条记录")
        
        # 🔍 检查数据文件类型
        file_name = os.path.basename(file_path)
        print(f"数据文件名: {file_name}")
        
        # 检查日期列（用于验证数据完整性，不用于筛选）
        date_columns = [col for col in all_data.columns if '日期' in col]
        
        if date_columns:
            date_col = date_columns[0]
            print(f"找到日期列: '{date_col}'")
            
            # 显示日期列的样本数据
            print(f"日期列样本数据:")
            sample_dates = all_data[date_col].head(5)
            for i, date_val in enumerate(sample_dates):
                print(f"  {i+1}. {date_val} (类型: {type(date_val)})")
            
            # 转换日期格式
            print("正在转换日期格式...")
            all_data[date_col] = pd.to_datetime(all_data[date_col], errors='coerce')
            
            # 检查转换结果
            converted_dates = all_data[date_col].dropna()
            print(f"日期转换完成，有效日期: {len(converted_dates):,}/{len(all_data):,}")
            
            if len(converted_dates) > 0:
                # 显示日期范围
                date_range = f"{converted_dates.min()} 到 {converted_dates.max()}"
                print(f"日期范围: {date_range}")
                
                # 按年份统计
                year_counts = converted_dates.dt.year.value_counts().sort_index()
                print(f"按年份统计:")
                for year, count in year_counts.items():
                    print(f"  {year}: {count:,} 条记录")
                
                # 如果是2024年数据文件，显示月份分布
                if "2024" in file_name:
                    month_counts = converted_dates.dt.month.value_counts().sort_index()
                    print(f"2024年按月份分布:")
                    for month, count in month_counts.items():
                        print(f"  {month:2d}月: {count:,} 条记录")
            else:
                print("❌ 日期转换失败，未找到有效日期")
        else:
            print("⚠️ 未找到包含'日期'的列")
            print(f"可用列: {list(all_data.columns)}")
        
        # 检查必要字段
        required_fields = ['机型', '里程（公里）', '人数']
        missing_fields = [field for field in required_fields if field not in all_data.columns]
        
        if missing_fields:
            raise ValueError(f"缺少必要字段: {missing_fields}")
        
        print(f"✅ 必要字段检查通过: {required_fields}")
        
        # 数据清洗
        print("正在进行数据清洗...")
        
        # 清理机型字段
        print("  - 清理机型字段...")
        all_data['机型'] = all_data['机型'].astype(str).str.strip()
        
        # 清理里程字段
        print("  - 清理里程字段...")
        all_data['里程（公里）'] = pd.to_numeric(all_data['里程（公里）'], errors='coerce')
        all_data['里程（公里）'] = all_data['里程（公里）'].fillna(0)
        
        # 清理人数字段
        print("  - 清理人数字段...")
        all_data['人数'] = pd.to_numeric(all_data['人数'], errors='coerce')
        all_data['人数'] = all_data['人数'].fillna(0)
        
        # 过滤有效数据
        print("  - 过滤有效数据...")
        valid_data = all_data[
            (all_data['机型'] != 'nan') & 
            (all_data['机型'] != '') &
            (all_data['里程（公里）'] >= 0) &
            (all_data['人数'] > 0)
        ]
        
        print(f"✅ 数据清洗完成，有效记录: {len(valid_data):,}/{len(all_data):,} 条")
        print(f"   数据有效率: {len(valid_data)/len(all_data)*100:.1f}%")
        
        if len(valid_data) == 0:
            raise ValueError("没有有效数据")
        
        # 显示最终数据统计
        print(f"\n📊 最终数据统计:")
        print(f"   总记录数: {len(valid_data):,}")
        print(f"   机型种类: {valid_data['机型'].nunique()}")
        print(f"   里程范围: {valid_data['里程（公里）'].min():.0f} - {valid_data['里程（公里）'].max():.0f} 公里")
        print(f"   人数范围: {valid_data['人数'].min():.0f} - {valid_data['人数'].max():.0f} 人")
        
        # 显示主要机型
        top_aircraft = valid_data['机型'].value_counts().head(5)
        print(f"   主要机型:")
        for aircraft, count in top_aircraft.items():
            print(f"     {aircraft}: {count:,} 条")
        
        # 分割数据为块
        total_chunks = (len(valid_data) - 1) // chunk_size + 1
        print(f"\n🔄 将数据分为 {total_chunks} 块，每块约 {chunk_size} 条记录")
        
        chunks = []
        for i in range(0, len(valid_data), chunk_size):
            chunk_df = valid_data.iloc[i:i+chunk_size].copy()
            chunk_id = i // chunk_size
            chunks.append((chunk_id, chunk_df))
        
        print(f"✅ 数据分割完成，共 {len(chunks)} 个数据块")
        
        # 验证分割结果
        total_records_in_chunks = sum(len(chunk_df) for _, chunk_df in chunks)
        print(f"   分割验证: {total_records_in_chunks:,} 条记录")
        
        if total_records_in_chunks != len(valid_data):
            print(f"⚠️ 警告: 分割后记录数不匹配!")
        
        return chunks
        
    except Exception as e:
        print(f"❌ 数据加载失败: {e}")
        import traceback
        traceback.print_exc()
        raise

def parallel_process_flight_data(data_file_path: str, output_dir: str, 
                                chunk_size: int = 1000, max_workers: int = None):
    """
    并行处理所有航班数据 - 优化内存使用和错误处理
    
    Args:
        data_file_path: 输入数据文件路径
        output_dir: 输出目录
        chunk_size: 每块的记录数
        max_workers: 最大工作进程数，None表示自动检测
    """
    start_time = time.time()
    
    print("🚀 === 开始并行处理所有航班数据 ===")
    print(f"数据文件: {data_file_path}")
    print(f"输出目录: {output_dir}")
    print(f"数据块大小: {chunk_size}")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    
    # 检查系统虚拟内存
    virtual_memory = psutil.virtual_memory()
    swap_memory = psutil.swap_memory()
    
    print(f"\n💾 内存状态检查:")
    print(f"   物理内存: {virtual_memory.total / (1024**3):.1f} GB")
    print(f"   可用内存: {virtual_memory.available / (1024**3):.1f} GB")
    print(f"   内存使用率: {virtual_memory.percent:.1f}%")
    print(f"   交换文件: {swap_memory.total / (1024**3):.1f} GB")
    print(f"   可用交换: {swap_memory.free / (1024**3):.1f} GB")
    
    # 如果可用内存太少，发出警告
    if virtual_memory.available / (1024**3) < 5:
        print("⚠️  警告: 可用内存不足5GB，可能会出现内存问题")
    
    # 确定工作进程数
    if max_workers is None:
        max_workers = get_optimal_worker_count()
    else:
        max_workers = max(1, min(max_workers, mp.cpu_count()))
    
    print(f"🔧 使用 {max_workers} 个工作进程")
    
    try:
        # 加载和分割数据
        data_chunks = load_and_split_data(data_file_path, chunk_size)
        
        if not data_chunks:
            print("❌ 没有数据需要处理")
            return None
        
        print(f"\n🔄 开始并行处理 {len(data_chunks)} 个数据块...")
        
        # 存储结果
        all_results = []
        all_stats = []
        completed_chunks = 0
        memory_errors = 0
        other_errors = 0
        
        # 使用ProcessPoolExecutor进行并行处理
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_chunk = {
                executor.submit(process_chunk_worker, chunk_data): chunk_data[0]
                for chunk_data in data_chunks
            }
            
            print(f"已提交 {len(future_to_chunk)} 个处理任务")
            
            # 收集结果
            for future in as_completed(future_to_chunk):
                chunk_id = future_to_chunk[future]
                
                try:
                    chunk_id_result, processed_data, stats = future.result()
                    completed_chunks += 1
                    
                    # 记录统计信息
                    all_stats.append(stats)
                    
                    # 检查错误类型
                    if 'error_type' in stats:
                        if stats['error_type'] == 'MemoryError':
                            memory_errors += 1
                        else:
                            other_errors += 1
                    
                    if processed_data is not None:
                        all_results.append(processed_data)
                        memory_info = f"(内存: {stats.get('memory_usage_mb', 0):.1f}MB)" if 'memory_usage_mb' in stats else ""
                        print(f"✅ 块 {chunk_id_result} 完成 "
                             f"({completed_chunks}/{len(data_chunks)}) - "
                             f"成功率: {stats['success_rate']:.1f}% "
                             f"({stats['success_count']}/{stats['total_records']}) {memory_info}")
                    else:
                        error_msg = stats.get('error', '未知错误')
                        error_type = stats.get('error_type', '未知')
                        print(f"❌ 块 {chunk_id_result} 失败 "
                             f"({completed_chunks}/{len(data_chunks)}) - "
                             f"[{error_type}] {error_msg}")
                        
                        # 如果是内存错误，建议降低并行度
                        if error_type == 'MemoryError':
                            print(f"💡 建议：内存不足，考虑减少并行进程数或增加数据块大小")
                
                except Exception as e:
                    completed_chunks += 1
                    other_errors += 1
                    print(f"❌ 块 {chunk_id} 处理异常 "
                         f"({completed_chunks}/{len(data_chunks)}): {e}")
                
                # 定期检查内存状态
                if completed_chunks % 10 == 0:
                    current_memory = psutil.virtual_memory()
                    if current_memory.percent > 90:
                        print(f"⚠️  内存使用率过高: {current_memory.percent:.1f}%")
        
        # 显示错误统计
        if memory_errors > 0 or other_errors > 0:
            print(f"\n📊 错误统计:")
            print(f"   内存错误: {memory_errors}")
            print(f"   其他错误: {other_errors}")
            print(f"   成功块数: {len(all_results)}")
            print(f"   总体成功率: {len(all_results) / len(data_chunks) * 100:.1f}%")
        
        # 合并结果
        if all_results:
            print(f"\n📊 合并 {len(all_results)} 个处理结果...")
            final_results = pd.concat(all_results, ignore_index=True)
            
            # 计算总体统计
            total_records = sum(stat['total_records'] for stat in all_stats)
            total_success = sum(stat['success_count'] for stat in all_stats)
            total_failed = sum(stat['failed_count'] for stat in all_stats)
            total_processing_time = sum(stat['processing_time'] for stat in all_stats)
            
            # 保存结果
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = os.path.join(output_dir, f"并行计算结果_{timestamp}.xlsx")
            
            # 保存到Excel
            try:
                final_results.to_excel(output_file, index=False)
                print(f"✅ 结果已保存到: {output_file}")
            except Exception as e:
                print(f"❌ 保存结果失败: {e}")
                # 尝试保存为CSV
                csv_file = output_file.replace('.xlsx', '.csv')
                final_results.to_csv(csv_file, index=False, encoding='utf-8-sig')
                print(f"✅ 结果已保存为CSV: {csv_file}")
            
            # 保存处理统计
            stats_df = pd.DataFrame(all_stats)
            stats_file = os.path.join(output_dir, f"处理统计_{timestamp}.xlsx")
            try:
                stats_df.to_excel(stats_file, index=False)
            except:
                stats_df.to_csv(stats_file.replace('.xlsx', '.csv'), index=False, encoding='utf-8-sig')
            
            # 显示最终统计
            end_time = time.time()
            wall_clock_time = end_time - start_time
            speedup = total_processing_time / wall_clock_time if wall_clock_time > 0 else 1
            
            print(f"\n🎉 === 并行处理完成 ===")
            print(f"总记录数: {total_records:,}")
            print(f"成功计算: {total_success:,} ({total_success/total_records*100:.1f}%)")
            print(f"计算失败: {total_failed:,} ({total_failed/total_records*100:.1f}%)")
            print(f"实际处理时间: {wall_clock_time:.2f} 秒")
            print(f"CPU总计算时间: {total_processing_time:.2f} 秒")
            print(f"加速比: {speedup:.1f}x")
            
            # 计算燃油相关统计
            if 'total_fuel_kg' in final_results.columns:
                total_fuel = final_results['total_fuel_kg'].sum()
                avg_fuel = final_results['total_fuel_kg'].mean()
                print(f"总燃油消耗: {total_fuel:,.2f} kg")
                print(f"平均燃油消耗: {avg_fuel:,.2f} kg/航班")
            
            print(f"结果文件: {output_file}")
            print(f"统计文件: {stats_file}")
            
            return final_results
        
        else:
            print("❌ 没有成功处理任何数据")
            if memory_errors > 0:
                print("💡 建议解决方案:")
                print("   1. 增加系统虚拟内存（页面文件）大小")
                print("   2. 减少并行进程数量")
                print("   3. 增加数据块大小以减少进程创建开销")
                print("   4. 关闭其他占用内存的程序")
            return None
            
    except Exception as e:
        print(f"❌ 并行处理过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return None

def single_process_flight_data(data_file_path: str, output_dir: str, chunk_size: int = 5000):
    """
    单进程处理所有航班数据 - 内存友好的备选方案
    
    Args:
        data_file_path: 输入数据文件路径
        output_dir: 输出目录
        chunk_size: 每块的记录数（用于分批处理）
    """
    start_time = time.time()
    
    print("🔄 === 开始单进程处理所有航班数据 ===")
    print(f"数据文件: {data_file_path}")
    print(f"输出目录: {output_dir}")
    print(f"数据块大小: {chunk_size}")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        # 加载和分割数据
        data_chunks = load_and_split_data(data_file_path, chunk_size)
        
        if not data_chunks:
            print("❌ 没有数据需要处理")
            return None
        
        print(f"\n🔄 开始处理 {len(data_chunks)} 个数据块...")
        
        # 存储结果
        all_results = []
        all_stats = []
        
        # 逐块处理数据
        for i, (chunk_id, chunk_df) in enumerate(data_chunks):
            print(f"处理块 {chunk_id + 1}/{len(data_chunks)} ({len(chunk_df)} 条记录)...")
            
            # 检查内存状态
            memory_info = psutil.virtual_memory()
            print(f"  当前内存使用: {memory_info.percent:.1f}%")
            
            try:
                # 处理当前块
                chunk_id_result, processed_data, stats = process_chunk_worker((chunk_id, chunk_df))
                
                all_stats.append(stats)
                
                if processed_data is not None:
                    all_results.append(processed_data)
                    print(f"  ✅ 成功处理: {stats['success_count']}/{stats['total_records']} "
                         f"(成功率: {stats['success_rate']:.1f}%)")
                else:
                    error_msg = stats.get('error', '未知错误')
                    print(f"  ❌ 处理失败: {error_msg}")
                
                # 手动垃圾回收
                import gc
                gc.collect()
                
            except Exception as e:
                print(f"  ❌ 处理块 {chunk_id} 时发生错误: {e}")
                continue
        
        # 合并结果
        if all_results:
            print(f"\n📊 合并 {len(all_results)} 个处理结果...")
            final_results = pd.concat(all_results, ignore_index=True)
            
            # 计算总体统计
            total_records = sum(stat['total_records'] for stat in all_stats)
            total_success = sum(stat['success_count'] for stat in all_stats)
            total_failed = sum(stat['failed_count'] for stat in all_stats)
            
            # 保存结果
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = os.path.join(output_dir, f"单进程计算结果_{timestamp}.xlsx")
            
            # 保存到Excel
            try:
                final_results.to_excel(output_file, index=False)
                print(f"✅ 结果已保存到: {output_file}")
                
            except Exception as e:
                print(f"❌ 保存结果失败: {e}")
                # 尝试保存为CSV
                csv_file = output_file.replace('.xlsx', '.csv')
                final_results.to_csv(csv_file, index=False, encoding='utf-8-sig')
                print(f"✅ 结果已保存为CSV: {csv_file}")
            
            # 显示最终统计
            end_time = time.time()
            processing_time = end_time - start_time
            
            print(f"\n🎉 === 单进程处理完成 ===")
            print(f"总记录数: {total_records:,}")
            print(f"成功计算: {total_success:,} ({total_success/total_records*100:.1f}%)")
            print(f"计算失败: {total_failed:,} ({total_failed/total_records*100:.1f}%)")
            print(f"处理时间: {processing_time:.2f} 秒")
            
            # 计算燃油相关统计
            if 'total_fuel_kg' in final_results.columns:
                total_fuel = final_results['total_fuel_kg'].sum()
                avg_fuel = final_results['total_fuel_kg'].mean()
                print(f"总燃油消耗: {total_fuel:,.2f} kg")
                print(f"平均燃油消耗: {avg_fuel:,.2f} kg/航班")
            
            print(f"结果文件: {output_file}")
            
            return final_results
        
        else:
            print("❌ 没有成功处理任何数据")
            return None
            
    except Exception as e:
        print(f"❌ 单进程处理过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """主程序入口 - 优先使用2024年数据文件，使用保守的内存配置"""
    # 配置文件路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    
    # 优先使用2024年数据文件
    data_file_2024 = os.path.join(project_root, "data", "2024年航班数据.xlsx")
    data_file_full = os.path.join(project_root, "data", "22年1月1日至24年12月31日航班数据.xlsx")
    output_dir = os.path.join(project_root, "results", "parallel_calculation")
    
    # 选择数据文件
    if os.path.exists(data_file_2024):
        data_file = data_file_2024
        print(f"✅ 使用2024年数据文件: {os.path.basename(data_file)}")
    elif os.path.exists(data_file_full):
        data_file = data_file_full
        print(f"⚠️ 使用完整数据文件: {os.path.basename(data_file)}")
        print("   建议先运行提取脚本生成2024年数据文件以提高处理速度")
    else:
        print(f"❌ 未找到数据文件:")
        print(f"   2024年数据: {data_file_2024}")
        print(f"   完整数据: {data_file_full}")
        print("请确保数据文件存在")
        return
    
    file_size_mb = os.path.getsize(data_file) / (1024*1024)
    print(f"数据文件大小: {file_size_mb:.1f} MB")
    
    # 获取系统信息
    cpu_count = mp.cpu_count()
    memory_gb = psutil.virtual_memory().total / (1024**3)
    virtual_memory = psutil.virtual_memory()
    swap_memory = psutil.swap_memory()
    
    print(f"\n💻 系统配置:")
    print(f"   CPU核心数: {cpu_count}")
    print(f"   总内存: {memory_gb:.1f} GB")
    print(f"   可用内存: {virtual_memory.available / (1024**3):.1f} GB")
    print(f"   交换文件: {swap_memory.total / (1024**3):.1f} GB")
    
    # 检查系统是否适合并行处理
    available_memory_gb = virtual_memory.available / (1024**3)
    
    # 根据数据文件大小调整策略
    if data_file == data_file_2024:
        # 2024年数据文件相对较小，可以更积极的并行配置
        print("📊 使用2024年数据文件，可以使用更高效的配置")
        if available_memory_gb < 4:
            print("⚠️  内存有限，使用单进程模式")
            max_workers = 1
            chunk_size = 3000
        elif available_memory_gb < 8:
            print("⚠️  内存有限，使用保守配置")
            max_workers = 2
            chunk_size = 2000
        else:
            # 对于2024年数据，可以使用更多进程
            max_workers = min(4, get_optimal_worker_count())
            chunk_size = 1500
    else:
        # 完整数据文件很大，需要更保守的配置
        print("📊 使用完整数据文件，需要更保守的配置")
        if available_memory_gb < 8:
            print("⚠️  警告: 可用内存不足8GB，建议使用单进程模式")
            max_workers = 1
            chunk_size = 5000
        elif available_memory_gb < 16:
            print("⚠️  内存有限，使用保守配置")
            max_workers = 2
            chunk_size = 3000
        else:
            # 自动配置参数，但更保守
            max_workers = get_optimal_worker_count()
            chunk_size = 3000
    
    print(f"\n⚙️  配置参数:")
    print(f"  工作进程数: {max_workers}")
    print(f"  数据块大小: {chunk_size}")
    if max_workers > 1:
        print(f"  预计加速比: {max_workers}x (理论)")
    else:
        print(f"  运行模式: 单进程 (内存保护)")
    
    # 显示内存使用预估
    estimated_memory_per_process = 3 if data_file == data_file_2024 else 4  # GB
    estimated_total_memory = max_workers * estimated_memory_per_process
    print(f"  预计内存需求: {estimated_total_memory:.1f} GB")
    
    if estimated_total_memory > available_memory_gb:
        print("⚠️  警告: 预计内存需求可能超过可用内存")
        print("   建议减少并行进程数或增加系统虚拟内存")
    
    print(f"\n🚀 开始处理数据集...")
    
    # 根据系统状况选择处理模式
    if max_workers == 1:
        print("💡 使用单进程模式处理（内存友好）")
        results = single_process_flight_data(
            data_file_path=data_file,
            output_dir=output_dir,
            chunk_size=chunk_size
        )
    else:
        print("💡 使用多进程模式处理（高性能）")
        results = parallel_process_flight_data(
            data_file_path=data_file,
            output_dir=output_dir,
            chunk_size=chunk_size,
            max_workers=max_workers
        )
    
    if results is not None:
        print("\n🎉 航班数据处理完成！")
        print(f"处理了 {len(results)} 条记录")
        
        # 显示最终系统状态
        final_memory = psutil.virtual_memory()
        print(f"\n📊 最终系统状态:")
        print(f"   内存使用率: {final_memory.percent:.1f}%")
        print(f"   可用内存: {final_memory.available / (1024**3):.1f} GB")
        
    else:
        print("\n❌ 处理未完成")
        
        # 提供故障排除建议
        print("\n🔧 故障排除建议:")
        if data_file == data_file_full:
            print("1. 建议使用2024年数据文件:")
            print("   python src/extract_2024_data.py")
            print("   这将大大减少内存需求")
        print("2. 检查系统虚拟内存设置:")
        print("   - 右键'此电脑' → 属性 → 高级系统设置")
        print("   - 性能设置 → 高级 → 虚拟内存 → 更改")
        print("   - 建议设置为16GB以上")
        print("3. 尝试单进程模式:")
        print("   - 重新运行程序，系统会自动检测并调整")
        print("4. 关闭其他占用内存的程序")

if __name__ == "__main__":
    main()