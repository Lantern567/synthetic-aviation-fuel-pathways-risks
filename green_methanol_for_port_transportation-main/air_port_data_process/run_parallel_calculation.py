"""
并行航班燃油消耗计算主程序
利用多CPU核心加速计算
"""

import os
import sys
from datetime import datetime
import multiprocessing as mp

# 添加src路径
sys.path.append('src')

from parallel_flight_processor import parallel_process_flight_data, get_optimal_worker_count

def main():
    """主函数"""
    print("🚀 并行航班燃油消耗计算系统启动")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # 数据文件路径
    data_file = 'data/22年1月1日至24年12月31日航班数据.xlsx'
    
    # 输出目录
    output_dir = 'results/parallel_fuel_calculation'
    
    print(f"📊 数据文件: {data_file}")
    print(f"📂 输出目录: {output_dir}")
    
    # 检查文件是否存在
    if not os.path.exists(data_file):
        print(f"❌ 数据文件不存在: {data_file}")
        return
    
    # 显示系统信息
    cpu_count = mp.cpu_count()
    optimal_workers = get_optimal_worker_count()
    file_size_mb = os.path.getsize(data_file) / (1024*1024)
    
    print(f"💻 系统信息:")
    print(f"   CPU核心数: {cpu_count}")
    print(f"   推荐工作进程数: {optimal_workers}")
    print(f"   数据文件大小: {file_size_mb:.1f} MB")
    print("="*60)
    
    # 并行处理参数
    chunk_size = 500  # 适中的块大小，平衡内存和并行度
    max_workers = optimal_workers
    
    print(f"⚙️  并行处理配置:")
    print(f"   工作进程数: {max_workers}")
    print(f"   数据块大小: {chunk_size} 条/块")
    print(f"   预计加速比: {max_workers}x (理论)")
    print("="*60)
    
    try:
        # 运行并行燃油消耗计算
        print("🚀 开始并行计算...")
        results = parallel_process_flight_data(
            data_file_path=data_file,
            output_dir=output_dir,
            chunk_size=chunk_size,
            max_workers=max_workers
        )
        
        if results is not None:
            print("="*60)
            print("🎉 并行计算完成！")
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
            
            # 显示Top机型统计
            if '机型' in results.columns:
                print(f"\n🛩️  Top 5机型统计:")
                aircraft_stats = results.groupby('机型').agg({
                    '燃油消耗_kg': ['count', 'mean'],
                    '里程（公里）': 'mean'
                }).round(1)
                aircraft_stats.columns = ['航班数', '平均燃油(kg)', '平均里程(km)']
                aircraft_stats = aircraft_stats.sort_values('航班数', ascending=False)
                print(aircraft_stats.head(5).to_string())
            
            print(f"\n📁 详细结果已保存到: {output_dir}")
            print(f"🕒 计算完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
        else:
            print("❌ 并行计算失败，没有返回结果")
            
    except Exception as e:
        print(f"❌ 并行计算过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # 设置多进程启动方法（Windows兼容性）
    if __name__ == "__main__":
        mp.set_start_method('spawn', force=True)
    
    main() 