"""
并行处理器测试脚本
用于验证修复后的代码是否正常运行
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime
import tempfile

# 添加当前目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from parallel_flight_processor import (
    get_optimal_worker_count,
    single_process_flight_data,
    parallel_process_flight_data
)

def create_test_data(num_records=100):
    """
    创建测试数据
    
    Args:
        num_records: 记录数量
        
    Returns:
        DataFrame: 测试数据
    """
    np.random.seed(42)  # 确保结果可重复
    
    # 生成测试数据
    aircraft_types = ['波音737(中)', '空客320(中)', '波音777(大)', '空客330(大)', 'CRJ900(小)']
    
    test_data = {
        '日期': pd.date_range('2024-01-01', periods=num_records, freq='D'),
        '机型': np.random.choice(aircraft_types, num_records),
        '里程（公里）': np.random.uniform(300, 3000, num_records),
        '人数': np.random.randint(50, 300, num_records),
        '起飞机场': 'PEK',
        '降落机场': 'SHA'
    }
    
    return pd.DataFrame(test_data)

def test_system_info():
    """测试系统信息获取"""
    print("🔍 测试系统信息获取...")
    
    try:
        worker_count = get_optimal_worker_count()
        print(f"✅ 系统信息获取成功，推荐工作进程数: {worker_count}")
        return True
    except Exception as e:
        print(f"❌ 系统信息获取失败: {e}")
        return False

def test_single_process(test_data_file, output_dir):
    """测试单进程处理"""
    print("\n🔍 测试单进程处理...")
    
    try:
        results = single_process_flight_data(
            data_file_path=test_data_file,
            output_dir=output_dir,
            chunk_size=50  # 小块用于测试
        )
        
        if results is not None and len(results) > 0:
            print(f"✅ 单进程处理成功，处理了 {len(results)} 条记录")
            return True
        else:
            print("❌ 单进程处理失败，没有返回结果")
            return False
            
    except Exception as e:
        print(f"❌ 单进程处理失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_parallel_process(test_data_file, output_dir):
    """测试并行处理"""
    print("\n🔍 测试并行处理...")
    
    try:
        results = parallel_process_flight_data(
            data_file_path=test_data_file,
            output_dir=output_dir,
            chunk_size=50,  # 小块用于测试
            max_workers=2   # 使用2个进程进行测试
        )
        
        if results is not None and len(results) > 0:
            print(f"✅ 并行处理成功，处理了 {len(results)} 条记录")
            return True
        else:
            print("❌ 并行处理失败，没有返回结果")
            return False
            
    except Exception as e:
        print(f"❌ 并行处理失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主测试函数"""
    print("🚀 开始测试并行处理器...")
    
    # 创建临时目录
    with tempfile.TemporaryDirectory() as temp_dir:
        test_data_file = os.path.join(temp_dir, "test_data.xlsx")
        output_dir = os.path.join(temp_dir, "test_output")
        
        # 创建测试数据
        print("📝 创建测试数据...")
        test_data = create_test_data(200)  # 200条记录用于测试
        test_data.to_excel(test_data_file, index=False)
        print(f"✅ 测试数据已保存到: {test_data_file}")
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        # 运行测试
        test_results = []
        
        # 测试1: 系统信息
        test_results.append(test_system_info())
        
        # 测试2: 单进程处理
        test_results.append(test_single_process(test_data_file, output_dir))
        
        # 测试3: 并行处理
        test_results.append(test_parallel_process(test_data_file, output_dir))
        
        # 显示测试结果
        print("\n📊 测试结果汇总:")
        tests = ["系统信息获取", "单进程处理", "并行处理"]
        for i, (test_name, result) in enumerate(zip(tests, test_results)):
            status = "✅ 通过" if result else "❌ 失败"
            print(f"   {i+1}. {test_name}: {status}")
        
        success_count = sum(test_results)
        total_tests = len(test_results)
        
        print(f"\n🎯 测试完成: {success_count}/{total_tests} 项测试通过")
        
        if success_count == total_tests:
            print("🎉 所有测试通过！代码修复成功！")
            return True
        else:
            print("⚠️  部分测试失败，建议进一步调试")
            return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 