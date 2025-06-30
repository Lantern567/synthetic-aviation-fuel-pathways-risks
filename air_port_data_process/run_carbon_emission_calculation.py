#!/usr/bin/env python3
"""
航空碳排放计算主程序
整合pyBADA库和分组优化算法
执行2024年航班数据的碳排放计算
"""

import os
import sys
import time
from datetime import datetime
import pandas as pd

# 添加src目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from grouped_carbon_calculator import process_grouped_carbon_emissions
from carbon_emission_calculator import parallel_carbon_emission_calculation

def main():
    """主函数"""
    print("🌱 === 航空碳排放计算系统启动 ===")
    print(f"🕒 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 配置参数
    data_file = 'results/parallel_fuel_calculation/并行计算结果_20250630_011947.xlsx'
    output_dir = 'results/carbon_emissions'
    
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    
    # 检查数据文件是否存在
    if not os.path.exists(data_file):
        print(f"❌ 数据文件不存在: {data_file}")
        return
    
    print(f"📊 输入数据文件: {data_file}")
    print(f"📂 输出目录: {output_dir}")
    
    # 方案1: 使用分组优化计算（推荐）
    print("\n🚀 === 方案1: 分组优化碳排放计算 ===")
    print("针对相同航线但不同日期的数据进行优化")
    
    # 指定分组列（不包含日期，这样相同航线会被分到一组）
    group_columns = ['起飞机场', '降落机场', 'ICAO代码', '航班班次']
    
    start_time = time.time()
    
    try:
        result_grouped = process_grouped_carbon_emissions(
            data_file_path=data_file,
            output_dir=output_dir,
            group_columns=group_columns
        )
        
        if result_grouped is not None:
            grouped_time = time.time() - start_time
            print(f"✅ 分组计算完成，耗时: {grouped_time:.1f} 秒")
            
            # 显示结果概览
            print(f"\n📊 分组计算结果概览:")
            print(f"   处理记录数: {len(result_grouped):,}")
            print(f"   新增列数: {len([col for col in result_grouped.columns if 'co2' in col.lower() or 'emission' in col.lower()])}")
            
            # 显示前几行结果
            carbon_columns = [col for col in result_grouped.columns if any(keyword in col.lower() for keyword in ['co2', 'emission', 'carbon'])]
            if carbon_columns:
                print(f"   碳排放相关新列: {carbon_columns}")
                print("\n前5行碳排放数据:")
                print(result_grouped[['起飞机场', '降落机场', 'ICAO代码'] + carbon_columns].head())
            
        else:
            print("❌ 分组计算失败")
            
    except Exception as e:
        print(f"❌ 分组计算出错: {e}")
        import traceback
        traceback.print_exc()
    
    # 方案2: 并行计算（备选方案）
    print("\n🔄 === 方案2: 传统并行计算 ===")
    print("逐行计算所有记录（可选执行）")
    
    # 询问是否执行方案2
    choice = input("是否同时执行传统并行计算？(y/n): ").lower().strip()
    
    if choice == 'y':
        start_time = time.time()
        
        try:
            result_parallel = parallel_carbon_emission_calculation(
                data_file_path=data_file,
                output_dir=output_dir,
                chunk_size=1000,
                max_workers=4
            )
            
            if result_parallel is not None:
                parallel_time = time.time() - start_time
                print(f"✅ 并行计算完成，耗时: {parallel_time:.1f} 秒")
                
                # 比较两种方法的结果
                if 'result_grouped' in locals() and result_grouped is not None:
                    print(f"\n⚖️ 两种方法对比:")
                    print(f"   分组计算耗时: {grouped_time:.1f} 秒")
                    print(f"   并行计算耗时: {parallel_time:.1f} 秒")
                    print(f"   性能提升: {(parallel_time/grouped_time):.1f}x")
            else:
                print("❌ 并行计算失败")
                
        except Exception as e:
            print(f"❌ 并行计算出错: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("跳过传统并行计算")
    
    print(f"\n🎉 === 碳排放计算完成 ===")
    print(f"🕒 结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📂 查看结果文件: {output_dir}")

def test_carbon_calculation():
    """测试碳排放计算功能"""
    print("🧪 === 开始测试碳排放计算 ===")
    
    # 创建测试数据
    test_data = {
        '起飞机场': ['PEK', 'PEK', 'SHA', 'SHA'],
        '降落机场': ['SHA', 'SHA', 'CAN', 'CAN'],
        'ICAO代码': ['A320', 'A320', 'B737', 'B737'],
        '航班班次': ['CA1234', 'CA1234', 'MU5678', 'MU5678'],
        '燃油消耗_kg': [4500, 4500, 3200, 3200],
        '人数': [150, 150, 180, 180],
        '载客率': [0.8, 0.8, 0.9, 0.9],
        '日期': ['2024-01-01', '2024-01-02', '2024-01-01', '2024-01-02']
    }
    
    test_df = pd.DataFrame(test_data)
    test_file = 'test_data.xlsx'
    test_df.to_excel(test_file, index=False)
    
    print(f"📊 测试数据已创建: {test_file}")
    print(f"测试数据预览:\n{test_df}")
    
    # 执行测试计算
    try:
        from grouped_carbon_calculator import PyBADAGroupedCarbonCalculator
        
        calculator = PyBADAGroupedCarbonCalculator(use_pybada=True)
        
        # 测试单条记录计算
        test_record = test_df.iloc[0]
        result = calculator.calculate_route_carbon_emissions(test_record)
        
        print(f"\n🔬 单条记录测试结果:")
        for key, value in result.items():
            print(f"   {key}: {value}")
        
        # 清理测试文件
        if os.path.exists(test_file):
            os.remove(test_file)
            
        print("✅ 测试完成")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # 首先运行测试
    test_carbon_calculation()
    
    print("\n" + "="*60 + "\n")
    
    # 然后运行主程序
    main() 