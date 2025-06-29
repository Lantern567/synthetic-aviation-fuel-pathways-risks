"""
航班燃油消耗计算主程序
使用pyBADA模型对所有航班数据进行燃油消耗计算
"""

import os
import sys
from datetime import datetime

# 添加src路径
sys.path.append('src')

from process_all_flights import process_all_flight_data

def main():
    """主函数"""
    print("🚀 航班燃油消耗计算系统启动")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # 数据文件路径
    data_file = 'data/22年1月1日至24年12月31日航班数据.xlsx'
    
    # 输出目录
    output_dir = 'results/fuel_calculation_results'
    
    # 处理参数
    chunk_size = 1000  # 每批处理1000条记录
    
    print(f"📊 数据文件: {data_file}")
    print(f"📂 输出目录: {output_dir}")
    print(f"⚙️  批处理大小: {chunk_size} 条/批")
    print("="*60)
    
    try:
        # 运行燃油消耗计算
        results = process_all_flight_data(
            data_file_path=data_file,
            output_dir=output_dir,
            chunk_size=chunk_size
        )
        
        if results is not None:
            print("="*60)
            print("🎉 计算完成！")
            print(f"✅ 成功处理: {len(results):,} 条航班记录")
            
            # 显示基本统计
            success_count = len(results[results['计算方法'] == 'pybada'])
            total_count = len(results)
            success_rate = success_count / total_count * 100 if total_count > 0 else 0
            
            print(f"📊 计算统计:")
            print(f"   总记录数: {total_count:,}")
            print(f"   成功计算: {success_count:,}")
            print(f"   成功率: {success_rate:.1f}%")
            
            if '燃油消耗_kg' in results.columns:
                total_fuel = results['燃油消耗_kg'].sum()
                avg_fuel = results['燃油消耗_kg'].mean()
                print(f"   总燃油消耗: {total_fuel:,.1f} kg")
                print(f"   平均燃油消耗: {avg_fuel:,.1f} kg/航班")
            
            # 显示机型统计
            if '机型' in results.columns:
                print(f"\n🛩️  机型统计 (前10):")
                aircraft_stats = results.groupby('机型').agg({
                    '燃油消耗_kg': ['count', 'mean'],
                    '里程（公里）': 'mean'
                }).round(1)
                aircraft_stats.columns = ['航班数', '平均燃油(kg)', '平均里程(km)']
                aircraft_stats = aircraft_stats.sort_values('航班数', ascending=False)
                print(aircraft_stats.head(10).to_string())
            
            print(f"\n📁 详细结果已保存到: {output_dir}")
            print(f"🕒 计算完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
        else:
            print("❌ 计算失败，没有返回结果")
            
    except Exception as e:
        print(f"❌ 计算过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 