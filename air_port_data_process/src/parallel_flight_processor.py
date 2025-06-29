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

# 添加当前目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from pybada_fuel_calculator import PyBADAFuelCalculator, process_flight_data_with_pybada

def get_optimal_worker_count():
    """
    获取最佳工作进程数
    
    Returns:
        int: 推荐的工作进程数
    """
    cpu_count = mp.cpu_count()
    memory_gb = psutil.virtual_memory().total / (1024**3)
    
    # 基于CPU核心数和内存大小计算最佳进程数
    # 每个进程大约需要1-2GB内存用于pyBADA计算
    memory_based_workers = max(1, int(memory_gb / 2))
    cpu_based_workers = cpu_count
    
    # 取较小值，但至少保留1个核心给系统
    optimal_workers = min(memory_based_workers, cpu_based_workers - 1)
    optimal_workers = max(1, optimal_workers)  # 至少1个工作进程
    
    print(f"🖥️  系统信息:")
    print(f"   CPU核心数: {cpu_count}")
    print(f"   可用内存: {memory_gb:.1f} GB")
    print(f"   推荐工作进程数: {optimal_workers}")
    
    return optimal_workers

def process_chunk_worker(chunk_data):
    """
    工作进程函数：处理单个数据块
    
    Args:
        chunk_data: 要处理的数据块 (chunk_id, chunk_df)
        
    Returns:
        tuple: (chunk_id, 处理结果, 统计信息)
    """
    chunk_id, df_chunk = chunk_data
    
    try:
        start_time = time.time()
        
        # 在工作进程中初始化计算器
        # 由于pyBADA可能不支持多进程，我们在每个进程中独立初始化
        processed_chunk = process_flight_data_with_pybada(df_chunk)
        
        # 统计信息
        success_count = len(processed_chunk[processed_chunk['计算方法'] == 'pybada'])
        failed_count = len(processed_chunk[processed_chunk['计算方法'] == 'failed'])
        processing_time = time.time() - start_time
        
        stats = {
            'chunk_id': chunk_id,
            'total_records': len(processed_chunk),
            'success_count': success_count,
            'failed_count': failed_count,
            'processing_time': processing_time,
            'success_rate': success_count / len(processed_chunk) * 100 if len(processed_chunk) > 0 else 0
        }
        
        return chunk_id, processed_chunk, stats
        
    except Exception as e:
        # 返回错误信息
        error_stats = {
            'chunk_id': chunk_id,
            'total_records': len(df_chunk) if df_chunk is not None else 0,
            'success_count': 0,
            'failed_count': len(df_chunk) if df_chunk is not None else 0,
            'processing_time': 0,
            'success_rate': 0,
            'error': str(e)
        }
        return chunk_id, None, error_stats

def load_and_split_data(file_path: str, chunk_size: int = 1000):
    """
    加载数据并分割为块
    
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
        print(f"数据读取完成，总计 {len(all_data)} 条记录")
        
        # 检查必要字段
        required_fields = ['机型', '里程（公里）', '人数']
        missing_fields = [field for field in required_fields if field not in all_data.columns]
        
        if missing_fields:
            raise ValueError(f"缺少必要字段: {missing_fields}")
        
        # 数据清洗
        print("正在进行数据清洗...")
        
        # 清理机型字段
        all_data['机型'] = all_data['机型'].astype(str).str.strip()
        
        # 清理里程字段
        all_data['里程（公里）'] = pd.to_numeric(all_data['里程（公里）'], errors='coerce')
        all_data['里程（公里）'] = all_data['里程（公里）'].fillna(0)
        
        # 清理人数字段
        all_data['人数'] = pd.to_numeric(all_data['人数'], errors='coerce')
        all_data['人数'] = all_data['人数'].fillna(0)
        
        # 过滤有效数据
        valid_data = all_data[
            (all_data['机型'] != 'nan') & 
            (all_data['机型'] != '') &
            (all_data['里程（公里）'] >= 0) &
            (all_data['人数'] > 0)
        ]
        
        print(f"数据清洗完成，有效记录: {len(valid_data)}/{len(all_data)} 条")
        
        if len(valid_data) == 0:
            raise ValueError("没有有效数据")
        
        # 分割数据为块
        chunks = []
        total_chunks = (len(valid_data) - 1) // chunk_size + 1
        print(f"将数据分为 {total_chunks} 块，每块约 {chunk_size} 条记录")
        
        for i in range(0, len(valid_data), chunk_size):
            chunk_df = valid_data.iloc[i:i+chunk_size].copy()
            chunk_id = i // chunk_size
            chunks.append((chunk_id, chunk_df))
        
        print(f"✅ 数据分割完成，共 {len(chunks)} 个数据块")
        return chunks
        
    except Exception as e:
        print(f"❌ 数据加载失败: {e}")
        raise

def parallel_process_flight_data(data_file_path: str, output_dir: str, 
                                chunk_size: int = 1000, max_workers: int = None):
    """
    并行处理所有航班数据
    
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
                    
                    if processed_data is not None:
                        all_results.append(processed_data)
                        print(f"✅ 块 {chunk_id_result} 完成 "
                             f"({completed_chunks}/{len(data_chunks)}) - "
                             f"成功率: {stats['success_rate']:.1f}% "
                             f"({stats['success_count']}/{stats['total_records']})")
                    else:
                        error_msg = stats.get('error', '未知错误')
                        print(f"❌ 块 {chunk_id_result} 失败 "
                             f"({completed_chunks}/{len(data_chunks)}) - {error_msg}")
                
                except Exception as e:
                    completed_chunks += 1
                    print(f"❌ 块 {chunk_id} 处理异常 "
                         f"({completed_chunks}/{len(data_chunks)}): {e}")
        
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
            from process_all_flights import save_results_to_excel
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = os.path.join(output_dir, f"并行计算结果_{timestamp}.xlsx")
            save_results_to_excel(final_results, output_file)
            
            # 保存处理统计
            stats_df = pd.DataFrame(all_stats)
            stats_file = os.path.join(output_dir, f"处理统计_{timestamp}.xlsx")
            stats_df.to_excel(stats_file, index=False)
            
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
            print(f"总燃油消耗: {final_results['燃油消耗_kg'].sum():,.2f} kg")
            print(f"平均燃油消耗: {final_results['燃油消耗_kg'].mean():,.2f} kg/航班")
            print(f"结果文件: {output_file}")
            print(f"统计文件: {stats_file}")
            
            return final_results
        
        else:
            print("❌ 没有成功处理任何数据")
            return None
            
    except Exception as e:
        print(f"❌ 并行处理过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """主程序入口"""
    # 配置文件路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    
    data_file = os.path.join(project_root, "data", "22年1月1日至24年12月31日航班数据.xlsx")
    output_dir = os.path.join(project_root, "results", "parallel_calculation")
    
    # 检查数据文件是否存在
    if not os.path.exists(data_file):
        print(f"❌ 数据文件不存在: {data_file}")
        return
    
    file_size_mb = os.path.getsize(data_file) / (1024*1024)
    print(f"数据文件大小: {file_size_mb:.1f} MB")
    
    # 获取系统信息
    cpu_count = mp.cpu_count()
    memory_gb = psutil.virtual_memory().total / (1024**3)
    
    print(f"\n💻 系统配置:")
    print(f"   CPU核心数: {cpu_count}")
    print(f"   内存: {memory_gb:.1f} GB")
    print(f"   推荐工作进程数: {get_optimal_worker_count()}")
    
    # 询问用户配置
    print(f"\n⚙️  并行处理配置:")
    
    # 工作进程数
    default_workers = get_optimal_worker_count()
    try:
        workers_input = input(f"工作进程数 [默认: {default_workers}]: ").strip()
        max_workers = int(workers_input) if workers_input else default_workers
    except ValueError:
        max_workers = default_workers
    
    # 数据块大小
    try:
        chunk_input = input("数据块大小 [默认: 1000]: ").strip()
        chunk_size = int(chunk_input) if chunk_input else 1000
    except ValueError:
        chunk_size = 1000
    
    print(f"\n确认配置:")
    print(f"  工作进程数: {max_workers}")
    print(f"  数据块大小: {chunk_size}")
    print(f"  预计加速比: {max_workers}x (理论)")
    
    # 询问是否继续
    user_input = input("\n开始并行计算？(y/n): ").lower().strip()
    
    if user_input == 'y':
        # 开始并行处理
        results = parallel_process_flight_data(
            data_file_path=data_file,
            output_dir=output_dir,
            chunk_size=chunk_size,
            max_workers=max_workers
        )
        
        if results is not None:
            print("\n🎉 所有航班数据并行处理完成！")
        else:
            print("\n❌ 并行处理未完成")
    else:
        print("用户取消处理")

if __name__ == "__main__":
    main() 