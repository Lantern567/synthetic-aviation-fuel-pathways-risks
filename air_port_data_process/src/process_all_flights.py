"""
完整航班数据燃油消耗计算程序
使用pyBADA模型对所有航班数据进行燃油消耗计算
"""

import os
import sys
import pandas as pd
import numpy as np
import time
from datetime import datetime
from pathlib import Path

# 添加当前目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from pybada_fuel_calculator import PyBADAFuelCalculator, process_flight_data_with_pybada

def load_flight_data(file_path: str, chunk_size: int = 1000):
    """
    分批读取航班数据文件
    
    Args:
        file_path: 数据文件路径
        chunk_size: 每批处理的记录数
        
    Yields:
        DataFrame: 每批的航班数据
    """
    print(f"开始读取航班数据: {file_path}")
    
    try:
        # 先读取全部数据，因为pd.read_excel不支持chunksize
        print("正在读取Excel文件...")
        all_data = pd.read_excel(file_path)
        print(f"数据读取完成，总计 {len(all_data)} 条记录")
        
        # 检查必要字段
        required_fields = ['机型', '里程（公里）', '人数']
        missing_fields = [field for field in required_fields if field not in all_data.columns]
        
        if missing_fields:
            print(f"⚠️ 缺少必要字段: {missing_fields}")
            print(f"可用字段: {list(all_data.columns)}")
            return
        
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
            print("⚠️ 没有有效数据")
            return
        
        # 分批处理
        total_chunks = (len(valid_data) - 1) // chunk_size + 1
        print(f"将数据分为 {total_chunks} 批处理，每批 {chunk_size} 条")
        
        for i in range(0, len(valid_data), chunk_size):
            chunk = valid_data.iloc[i:i+chunk_size].copy()
            chunk_num = i // chunk_size + 1
            print(f"正在处理第 {chunk_num}/{total_chunks} 批数据，共 {len(chunk)} 条记录")
            yield chunk
                
    except Exception as e:
        print(f"❌ 读取数据文件失败: {e}")
        raise

def save_results_to_excel(results_df: pd.DataFrame, output_path: str):
    """
    保存计算结果到Excel文件
    
    Args:
        results_df: 计算结果DataFrame
        output_path: 输出文件路径
    """
    print(f"正在保存结果到: {output_path}")
    
    try:
        with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
            # 工作表1: 完整计算结果
            results_df.to_excel(writer, sheet_name='航班燃油消耗详细', index=False)
            
            # 工作表2: 统计汇总
            summary_stats = {
                '总航班数': len(results_df),
                '成功计算数': len(results_df[results_df['计算方法'] == 'pybada']),
                '失败计算数': len(results_df[results_df['计算方法'] == 'failed']),
                '总燃油消耗_kg': results_df['燃油消耗_kg'].sum(),
                '平均燃油消耗_kg': results_df['燃油消耗_kg'].mean(),
                '平均载客率': results_df['载客率'].mean(),
                '平均里程_km': results_df['里程（公里）'].mean(),
                'pyBADA使用率_%': (len(results_df[results_df['计算方法'] == 'pybada']) / len(results_df) * 100) if len(results_df) > 0 else 0
            }
            
            summary_df = pd.DataFrame(list(summary_stats.items()), columns=['指标', '数值'])
            summary_df.to_excel(writer, sheet_name='统计汇总', index=False)
            
            # 工作表3: 按机型统计
            if len(results_df) > 0:
                aircraft_stats = results_df.groupby(['ICAO代码', '计算方法']).agg({
                    '燃油消耗_kg': ['count', 'mean', 'sum'],
                    '载客率': 'mean',
                    '里程（公里）': 'mean'
                }).round(2)
                
                aircraft_stats.columns = ['航班数', '平均燃油消耗_kg', '总燃油消耗_kg', '平均载客率', '平均里程_km']
                aircraft_stats.to_excel(writer, sheet_name='机型统计')
            
            # 工作表4: 按计算方法统计
            if len(results_df) > 0:
                method_stats = results_df.groupby('计算方法').agg({
                    '燃油消耗_kg': ['count', 'mean', 'sum'],
                    '载客率': 'mean',
                    '里程（公里）': 'mean'
                }).round(2)
                
                method_stats.columns = ['航班数', '平均燃油消耗_kg', '总燃油消耗_kg', '平均载客率', '平均里程_km']
                method_stats.to_excel(writer, sheet_name='计算方法对比')
        
        print(f"✅ 结果已保存到: {output_path}")
        
    except Exception as e:
        print(f"❌ 保存结果失败: {e}")
        raise

def process_all_flight_data(data_file_path: str, output_dir: str, chunk_size: int = 1000):
    """
    处理所有航班数据的主函数
    
    Args:
        data_file_path: 输入数据文件路径
        output_dir: 输出目录
        chunk_size: 每批处理的记录数
    """
    start_time = time.time()
    
    print("=== 开始处理所有航班数据 ===")
    print(f"数据文件: {data_file_path}")
    print(f"输出目录: {output_dir}")
    print(f"批处理大小: {chunk_size}")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    
    # 初始化计算器
    calculator = PyBADAFuelCalculator()
    
    # 存储所有结果
    all_results = []
    total_processed = 0
    total_success = 0
    total_failed = 0
    
    try:
        # 分批处理数据
        for chunk_num, chunk_data in enumerate(load_flight_data(data_file_path, chunk_size), 1):
            print(f"\n--- 处理第 {chunk_num} 批数据 ---")
            
            # 使用pyBADA计算器处理当前批次
            try:
                processed_chunk = process_flight_data_with_pybada(chunk_data)
                
                # 统计当前批次结果
                chunk_success = len(processed_chunk[processed_chunk['计算方法'] == 'pybada'])
                chunk_failed = len(processed_chunk[processed_chunk['计算方法'] == 'failed'])
                
                print(f"第 {chunk_num} 批结果:")
                print(f"  成功: {chunk_success} 条")
                print(f"  失败: {chunk_failed} 条")
                print(f"  成功率: {chunk_success/(chunk_success + chunk_failed)*100:.1f}%")
                
                # 添加到总结果
                all_results.append(processed_chunk)
                total_processed += len(processed_chunk)
                total_success += chunk_success
                total_failed += chunk_failed
                
                # 定期保存中间结果
                if chunk_num % 10 == 0:
                    print(f"已处理 {chunk_num} 批，总计 {total_processed} 条记录")
                    intermediate_df = pd.concat(all_results, ignore_index=True)
                    intermediate_path = os.path.join(output_dir, f"中间结果_第{chunk_num}批.xlsx")
                    save_results_to_excel(intermediate_df, intermediate_path)
                
            except Exception as e:
                print(f"❌ 第 {chunk_num} 批处理失败: {e}")
                total_failed += len(chunk_data)
                continue
    
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断处理，保存已处理的结果...")
    
    except Exception as e:
        print(f"❌ 数据处理过程中发生错误: {e}")
    
    # 合并所有结果
    if all_results:
        print("\n=== 合并所有结果 ===")
        final_results = pd.concat(all_results, ignore_index=True)
        
        # 保存最终结果
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        final_output_path = os.path.join(output_dir, f"所有航班燃油消耗计算结果_{timestamp}.xlsx")
        save_results_to_excel(final_results, final_output_path)
        
        # 显示最终统计
        end_time = time.time()
        processing_time = end_time - start_time
        
        print(f"\n=== 处理完成 ===")
        print(f"处理时间: {processing_time:.2f} 秒")
        print(f"总记录数: {total_processed:,}")
        print(f"成功计算: {total_success:,} ({total_success/total_processed*100:.1f}%)")
        print(f"计算失败: {total_failed:,} ({total_failed/total_processed*100:.1f}%)")
        print(f"总燃油消耗: {final_results['燃油消耗_kg'].sum():,.2f} kg")
        print(f"平均燃油消耗: {final_results['燃油消耗_kg'].mean():,.2f} kg/航班")
        print(f"结果文件: {final_output_path}")
        
        return final_results
    
    else:
        print("❌ 没有成功处理任何数据")
        return None

def main():
    """主程序入口"""
    # 配置文件路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    
    data_file = os.path.join(project_root, "data", "22年1月1日至24年12月31日航班数据.xlsx")
    output_dir = os.path.join(project_root, "results", "tables")
    
    # 检查数据文件是否存在
    if not os.path.exists(data_file):
        print(f"❌ 数据文件不存在: {data_file}")
        return
    
    print(f"数据文件大小: {os.path.getsize(data_file) / (1024*1024):.1f} MB")
    
    # 询问用户是否继续
    print("\n⚠️ 这将处理所有航班数据，可能需要较长时间。")
    user_input = input("是否继续？(y/n): ").lower().strip()
    
    if user_input == 'y':
        # 开始处理
        results = process_all_flight_data(
            data_file_path=data_file,
            output_dir=output_dir,
            chunk_size=1000  # 每批处理1000条记录
        )
        
        if results is not None:
            print("\n🎉 所有航班数据处理完成！")
        else:
            print("\n❌ 数据处理未完成")
    else:
        print("用户取消处理")

if __name__ == "__main__":
    main() 