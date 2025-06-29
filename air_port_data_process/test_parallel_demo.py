"""
并行处理演示程序
测试多核心加速计算功能
"""

import os
import sys
import pandas as pd
import time
from datetime import datetime

# 添加src路径
sys.path.append('src')

from parallel_flight_processor import get_optimal_worker_count, parallel_process_flight_data

def create_test_data():
    """创建测试数据"""
    print("📊 创建测试数据...")
    
    # 创建一个较小的测试数据集
    test_data = pd.DataFrame({
        '机型': ['波音737(中)', '空客320', '波音777', '空客330'] * 25,  # 100条记录
        '里程（公里）': [1500, 2000, 8000, 3500] * 25,
        '人数': [150, 120, 250, 180] * 25,
        '出发机场': ['北京', '上海', '广州', '深圳'] * 25,
        '到达机场': ['上海', '广州', '北京', '成都'] * 25
    })
    
    # 保存测试数据
    test_file = 'test_flight_data_100.xlsx'
    test_data.to_excel(test_file, index=False)
    
    print(f"✅ 测试数据已创建: {test_file} ({len(test_data)} 条记录)")
    return test_file

def test_parallel_performance():
    """测试并行处理性能"""
    print("🚀 开始并行处理性能测试")
    print("="*60)
    
    # 创建测试数据
    test_file = create_test_data()
    
    try:
        # 显示系统信息
        optimal_workers = get_optimal_worker_count()
        file_size_mb = os.path.getsize(test_file) / (1024*1024)
        
        print(f"📁 测试文件大小: {file_size_mb:.2f} MB")
        print(f"💻 推荐工作进程数: {optimal_workers}")
        print("="*60)
        
        # 测试不同的并行配置
        test_configs = [
            {'workers': 1, 'chunk_size': 25, 'name': '单进程'},
            {'workers': optimal_workers, 'chunk_size': 25, 'name': f'{optimal_workers}进程并行'}
        ]
        
        results_comparison = []
        
        for config in test_configs:
            print(f"\n🧪 测试配置: {config['name']}")
            print(f"   工作进程数: {config['workers']}")
            print(f"   数据块大小: {config['chunk_size']}")
            
            start_time = time.time()
            
            output_dir = f"results/test_parallel_{config['workers']}workers"
            
            try:
                results = parallel_process_flight_data(
                    data_file_path=test_file,
                    output_dir=output_dir,
                    chunk_size=config['chunk_size'],
                    max_workers=config['workers']
                )
                
                end_time = time.time()
                processing_time = end_time - start_time
                
                if results is not None:
                    success_count = len(results[results['计算方法'] == 'pybada'])
                    total_count = len(results)
                    success_rate = success_count / total_count * 100
                    
                    config_result = {
                        'name': config['name'],
                        'workers': config['workers'],
                        'processing_time': processing_time,
                        'total_records': total_count,
                        'success_count': success_count,
                        'success_rate': success_rate,
                        'records_per_second': total_count / processing_time if processing_time > 0 else 0
                    }
                    
                    results_comparison.append(config_result)
                    
                    print(f"✅ {config['name']} 完成:")
                    print(f"   处理时间: {processing_time:.2f} 秒")
                    print(f"   处理记录: {total_count}")
                    print(f"   成功率: {success_rate:.1f}%")
                    print(f"   处理速度: {total_count/processing_time:.1f} 记录/秒")
                
                else:
                    print(f"❌ {config['name']} 失败")
                    
            except Exception as e:
                end_time = time.time()
                processing_time = end_time - start_time
                print(f"❌ {config['name']} 出错: {e}")
                print(f"   耗时: {processing_time:.2f} 秒")
        
        # 比较结果
        if len(results_comparison) >= 2:
            print("\n📊 性能比较:")
            print("="*60)
            
            single_proc = next((r for r in results_comparison if r['workers'] == 1), None)
            multi_proc = next((r for r in results_comparison if r['workers'] > 1), None)
            
            if single_proc and multi_proc:
                speedup = single_proc['processing_time'] / multi_proc['processing_time']
                efficiency = speedup / multi_proc['workers'] * 100
                
                print(f"单进程处理时间: {single_proc['processing_time']:.2f} 秒")
                print(f"{multi_proc['workers']}进程处理时间: {multi_proc['processing_time']:.2f} 秒")
                print(f"加速比: {speedup:.2f}x")
                print(f"并行效率: {efficiency:.1f}%")
                
                if speedup > 1.5:
                    print("🎉 并行加速效果显著！")
                elif speedup > 1.1:
                    print("✅ 并行有一定加速效果")
                else:
                    print("⚠️  并行加速效果不明显，可能是数据量太小")
            
            # 显示详细对比表
            print(f"\n📋 详细对比:")
            for result in results_comparison:
                print(f"{result['name']:12s} | "
                     f"{result['processing_time']:6.2f}s | "
                     f"{result['records_per_second']:6.1f} rec/s | "
                     f"{result['success_rate']:5.1f}%")
        
    finally:
        # 清理测试文件
        if os.path.exists(test_file):
            os.remove(test_file)
            print(f"\n🗑️  已删除测试文件: {test_file}")

if __name__ == "__main__":
    test_parallel_performance() 