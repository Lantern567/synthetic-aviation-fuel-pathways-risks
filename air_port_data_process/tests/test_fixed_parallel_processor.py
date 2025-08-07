#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试修复后的并行航班处理器
"""

import os
import sys
from datetime import datetime
import logging

# 添加父目录到路径以导入模块
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)
sys.path.insert(0, os.path.join(parent_dir, 'src'))

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_fixed_parallel_processor():
    """测试修复后的并行处理器"""
    print("🧪 === 测试修复后的并行航班处理器 ===")
    print("开始时间:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    print()
    
    # 检查数据文件
    data_dir = os.path.join(parent_dir, "data")
    
    data_file_2024 = os.path.join(data_dir, "2024年航班数据.xlsx")
    data_file_full = os.path.join(data_dir, "22年1月1日至24年12月31日航班数据.xlsx")
    
    print("📂 检查数据文件:")
    
    if os.path.exists(data_file_2024):
        file_size = os.path.getsize(data_file_2024) / (1024*1024)
        print(f"  ✅ 2024年数据文件: {file_size:.1f} MB")
        data_file = data_file_2024
    elif os.path.exists(data_file_full):
        file_size = os.path.getsize(data_file_full) / (1024*1024)
        print(f"  ⚠️ 完整数据文件: {file_size:.1f} MB")
        print("     建议先运行提取脚本生成2024年数据文件")
        data_file = data_file_full
    else:
        print("  ❌ 未找到数据文件")
        return False
    
    print()
    
    # 测试数据加载
    print("📖 测试数据加载功能...")
    try:
        from parallel_flight_processor import load_and_split_data
        
        # 使用小的chunk_size进行测试
        test_chunks = load_and_split_data(data_file, chunk_size=1000)
        
        if test_chunks:
            print(f"✅ 数据加载成功，共 {len(test_chunks)} 个数据块")
            
            # 显示第一个块的信息
            first_chunk_id, first_chunk_df = test_chunks[0]
            print(f"   第一个数据块: {len(first_chunk_df)} 条记录")
            print(f"   数据列: {list(first_chunk_df.columns)}")
            
            # 检查是否有日期信息
            date_columns = [col for col in first_chunk_df.columns if '日期' in col]
            if date_columns:
                print(f"   日期列: {date_columns}")
                sample_dates = first_chunk_df[date_columns[0]].head(3)
                print(f"   样本日期: {list(sample_dates)}")
            
        else:
            print("❌ 数据加载失败，未返回数据块")
            return False
            
    except Exception as e:
        print(f"❌ 数据加载测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print()
    
    # 测试pybada计算器可用性
    print("🔧 测试计算器可用性...")
    try:
        from pybada_fuel_calculator import PYBADA_AVAILABLE, PyBADAFuelCalculator
        print(f"   pyBADA状态: {'✅ 可用' if PYBADA_AVAILABLE else '❌ 不可用'}")
        
        if PYBADA_AVAILABLE:
            calculator = PyBADAFuelCalculator()
            print("   ✅ 计算器初始化成功")
        else:
            print("   ⚠️ pyBADA不可用，将使用备用计算方法")
            
    except Exception as e:
        print(f"❌ 计算器测试失败: {e}")
        return False
    
    print()
    
    # 测试处理函数
    print("⚙️ 测试处理函数...")
    try:
        from parallel_flight_processor import process_chunk_worker
        
        # 获取一个小的测试块
        test_chunk_id, test_chunk_df = test_chunks[0]
        
        # 只取前5条记录进行测试
        small_test_df = test_chunk_df.head(5)
        
        print(f"   测试数据: {len(small_test_df)} 条记录")
        
        # 测试处理
        result = process_chunk_worker((0, small_test_df))
        
        if result:
            chunk_id, processed_data, stats = result
            print(f"   ✅ 处理成功")
            print(f"   统计信息: {stats}")
            
            if processed_data is not None:
                print(f"   处理结果: {len(processed_data)} 条记录")
                print(f"   结果列: {list(processed_data.columns)}")
            else:
                print("   ⚠️ 处理返回空结果")
        else:
            print("   ❌ 处理返回None")
            return False
            
    except Exception as e:
        print(f"❌ 处理函数测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print()
    
    # 系统信息检查
    print("💻 系统信息检查...")
    try:
        from parallel_flight_processor import get_optimal_worker_count
        import psutil
        
        virtual_memory = psutil.virtual_memory()
        print(f"   可用内存: {virtual_memory.available / (1024**3):.1f} GB")
        print(f"   内存使用率: {virtual_memory.percent:.1f}%")
        
        optimal_workers = get_optimal_worker_count()
        print(f"   推荐工作进程数: {optimal_workers}")
        
    except Exception as e:
        print(f"❌ 系统信息检查失败: {e}")
        return False
    
    print()
    print("🎉 所有测试通过！修复后的并行处理器工作正常")
    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return True

if __name__ == "__main__":
    success = test_fixed_parallel_processor()
    if success:
        print("\n✅ 测试通过，可以运行正式处理")
        print("   运行命令: python src/parallel_flight_processor.py")
    else:
        print("\n❌ 测试失败，请检查问题") 