"""
小规模测试燃油消耗计算
用少量数据验证计算功能是否正常
"""

import os
import sys
from datetime import datetime

# 添加src路径
sys.path.append('src')

from process_all_flights import load_flight_data, process_all_flight_data

def test_small_calculation():
    """测试小规模计算"""
    print("🧪 开始小规模燃油消耗计算测试")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*50)
    
    # 数据文件路径
    data_file = 'data/22年1月1日至24年12月31日航班数据.xlsx'
    
    # 输出目录
    output_dir = 'results/test_calculation'
    
    # 处理参数 - 只处理前100条记录进行测试
    chunk_size = 50  # 每批50条
    
    print(f"📊 数据文件: {data_file}")
    print(f"📂 输出目录: {output_dir}")
    print(f"⚙️  测试规模: 前100条记录")
    print("="*50)
    
    try:
        # 先测试数据加载
        print("🔍 测试数据加载...")
        chunks = list(load_flight_data(data_file, chunk_size=chunk_size))
        
        if not chunks:
            print("❌ 没有加载到任何数据")
            return
        
        # 只取前2个chunk进行测试（约100条记录）
        test_chunks = chunks[:2]
        total_test_records = sum(len(chunk) for chunk in test_chunks)
        
        print(f"✅ 成功加载测试数据: {total_test_records} 条记录")
        
        # 显示数据样本
        first_chunk = test_chunks[0]
        print(f"\n📄 数据样本:")
        print(f"机型样本: {first_chunk['机型'].head(3).tolist()}")
        print(f"里程样本: {first_chunk['里程（公里）'].head(3).tolist()}")
        print(f"人数样本: {first_chunk['人数'].head(3).tolist()}")
        
        # 测试完整计算流程（仅使用测试数据）
        print(f"\n🚀 开始测试燃油消耗计算...")
        
        # 创建临时测试文件
        import pandas as pd
        test_data = pd.concat(test_chunks, ignore_index=True)
        test_file = 'temp_test_data.xlsx'
        test_data.to_excel(test_file, index=False)
        
        print(f"💾 创建临时测试文件: {test_file} ({len(test_data)}条记录)")
        
        # 运行计算
        results = process_all_flight_data(
            data_file_path=test_file,
            output_dir=output_dir,
            chunk_size=25  # 小批量测试
        )
        
        # 清理临时文件
        if os.path.exists(test_file):
            os.remove(test_file)
            print(f"🗑️  删除临时文件: {test_file}")
        
        if results is not None:
            print("="*50)
            print("🎉 测试计算完成！")
            print(f"✅ 成功处理: {len(results):,} 条航班记录")
            
            # 显示详细统计
            success_count = len(results[results['计算方法'] == 'pybada'])
            total_count = len(results)
            success_rate = success_count / total_count * 100 if total_count > 0 else 0
            
            print(f"📊 测试统计:")
            print(f"   总记录数: {total_count:,}")
            print(f"   成功计算: {success_count:,}")
            print(f"   失败记录: {total_count - success_count:,}")
            print(f"   成功率: {success_rate:.1f}%")
            
            if '燃油消耗_kg' in results.columns:
                valid_fuel = results[results['燃油消耗_kg'] > 0]
                if len(valid_fuel) > 0:
                    avg_fuel = valid_fuel['燃油消耗_kg'].mean()
                    min_fuel = valid_fuel['燃油消耗_kg'].min()
                    max_fuel = valid_fuel['燃油消耗_kg'].max()
                    print(f"   平均燃油消耗: {avg_fuel:,.1f} kg/航班")
                    print(f"   燃油消耗范围: {min_fuel:,.1f} - {max_fuel:,.1f} kg")
            
            # 显示机型分布
            if '机型' in results.columns:
                print(f"\n🛩️  机型分布:")
                aircraft_counts = results['机型'].value_counts().head(5)
                for aircraft, count in aircraft_counts.items():
                    print(f"   {aircraft}: {count} 航班")
            
            # 显示ICAO代码分布
            if 'ICAO代码' in results.columns:
                print(f"\n✈️  ICAO代码分布:")
                icao_counts = results['ICAO代码'].value_counts().head(5)
                for icao, count in icao_counts.items():
                    print(f"   {icao}: {count} 航班")
            
            print(f"\n📁 测试结果已保存到: {output_dir}")
            print(f"🕒 测试完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 如果测试成功，询问是否进行全量计算
            if success_rate > 50:  # 成功率超过50%认为测试成功
                print(f"\n✅ 测试成功！成功率达到{success_rate:.1f}%")
                print(f"💡 建议进行全量数据计算")
            else:
                print(f"\n⚠️  测试成功率较低({success_rate:.1f}%)，建议检查数据或算法")
            
        else:
            print("❌ 测试计算失败，没有返回结果")
            
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_small_calculation() 