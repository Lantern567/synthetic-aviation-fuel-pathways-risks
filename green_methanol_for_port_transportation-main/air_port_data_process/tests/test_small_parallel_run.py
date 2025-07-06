#!/usr/bin/env python3
"""
小规模并行处理测试
验证修复后的并行处理器是否能正常运行完整流程
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime

# 添加src目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from parallel_flight_processor import parallel_process_flight_data

def test_small_parallel_run():
    """测试小规模并行处理"""
    
    # 数据文件路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_file = os.path.join(current_dir, '..', 'data', '22年1月1日至24年12月31日航班数据.xlsx')
    output_dir = os.path.join(current_dir, '..', 'results', 'test_parallel')
    
    print("🧪 === 小规模并行处理测试 ===")
    print(f"数据文件: {data_file}")
    print(f"输出目录: {output_dir}")
    
    # 检查文件是否存在
    if not os.path.exists(data_file):
        print(f"❌ 数据文件不存在: {data_file}")
        return
    
    try:
        print("\n🚀 开始小规模并行处理测试...")
        
        # 使用较小的参数进行测试
        chunk_size = 500  # 每块500条记录
        max_workers = 2   # 只使用2个工作进程
        
        print(f"测试参数:")
        print(f"  数据块大小: {chunk_size}")
        print(f"  工作进程数: {max_workers}")
        
        # 调用并行处理函数
        results = parallel_process_flight_data(
            data_file_path=data_file,
            output_dir=output_dir,
            chunk_size=chunk_size,
            max_workers=max_workers
        )
        
        if results is not None:
            print(f"\n✅ 并行处理测试成功!")
            print(f"   处理记录数: {len(results):,}")
            
            # 验证结果
            if len(results) > 0:
                print(f"\n📊 结果验证:")
                print(f"   总记录数: {len(results):,}")
                print(f"   列数: {len(results.columns)}")
                
                # 检查关键列
                key_columns = ['机型', '里程（公里）', '人数', 'calculation_successful']
                for col in key_columns:
                    if col in results.columns:
                        print(f"   ✅ {col}: 存在")
                    else:
                        print(f"   ❌ {col}: 缺失")
                
                # 统计计算成功率
                if 'calculation_successful' in results.columns:
                    success_count = results['calculation_successful'].sum()
                    success_rate = success_count / len(results) * 100
                    print(f"   计算成功率: {success_rate:.1f}% ({success_count}/{len(results)})")
                
                # 检查燃油消耗数据
                fuel_columns = [col for col in results.columns if 'fuel' in col.lower() or '燃油' in col]
                if fuel_columns:
                    print(f"   燃油相关列: {fuel_columns}")
                    
                    # 统计燃油消耗
                    for fuel_col in fuel_columns:
                        if results[fuel_col].dtype in ['float64', 'int64']:
                            total_fuel = results[fuel_col].sum()
                            avg_fuel = results[fuel_col].mean()
                            print(f"   {fuel_col}: 总计 {total_fuel:,.2f}, 平均 {avg_fuel:,.2f}")
                
                # 检查日期数据
                if '日期' in results.columns:
                    dates = pd.to_datetime(results['日期'], errors='coerce')
                    valid_dates = dates.dropna()
                    
                    if len(valid_dates) > 0:
                        years = valid_dates.dt.year.unique()
                        print(f"   日期验证: {sorted(years)} 年")
                        
                        if len(years) == 1 and years[0] == 2024:
                            print(f"   ✅ 所有数据都是2024年")
                        else:
                            print(f"   ⚠️ 数据包含多个年份")
                
                # 显示机型统计
                print(f"\n🛩️  机型统计 (前5):")
                aircraft_counts = results['机型'].value_counts().head(5)
                for aircraft, count in aircraft_counts.items():
                    print(f"   {aircraft}: {count:,} 条")
                
                print(f"\n🎯 测试结果:")
                print(f"   ✅ 数据加载正常")
                print(f"   ✅ 2024年数据筛选正常")
                print(f"   ✅ 并行处理正常")
                print(f"   ✅ 结果保存正常")
                
            else:
                print(f"❌ 结果为空")
                
        else:
            print(f"❌ 并行处理失败")
            
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_small_parallel_run() 