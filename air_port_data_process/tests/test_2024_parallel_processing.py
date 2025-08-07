"""
测试2024年数据的并行处理功能
"""

import sys
import os
import pandas as pd
import tempfile
import shutil

# 添加src路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from parallel_flight_processor import parallel_process_flight_data

def test_small_scale_parallel_processing():
    """测试小规模并行处理"""
    print("🧪 测试小规模2024年数据并行处理...")
    
    # 创建临时目录
    temp_dir = tempfile.mkdtemp()
    
    try:
        # 数据文件路径
        data_path = os.path.join(os.path.dirname(__file__), '..', 'data', '22年1月1日至24年12月31日航班数据.xlsx')
        
        if not os.path.exists(data_path):
            print(f"❌ 数据文件不存在: {data_path}")
            return False
        
        # 创建小规模测试数据（只取前2000条记录）
        print("📖 创建小规模测试数据...")
        original_data = pd.read_excel(data_path, nrows=2000)
        
        # 筛选2024年数据
        date_columns = [col for col in original_data.columns if '日期' in col]
        if date_columns:
            date_col = date_columns[0]
            original_data[date_col] = pd.to_datetime(original_data[date_col], errors='coerce')
            data_2024 = original_data[original_data[date_col].dt.year == 2024]
            
            if len(data_2024) == 0:
                print("⚠️ 前2000条记录中没有2024年数据，使用全部数据")
                data_2024 = original_data
        else:
            print("⚠️ 未找到日期列，使用全部数据")
            data_2024 = original_data
        
        # 保存测试数据
        test_data_path = os.path.join(temp_dir, 'test_data.xlsx')
        data_2024.to_excel(test_data_path, index=False)
        
        print(f"创建测试数据完成，共 {len(data_2024)} 条记录")
        
        # 运行并行处理
        print("🚀 开始小规模并行处理...")
        results = parallel_process_flight_data(
            data_file_path=test_data_path,
            output_dir=temp_dir,
            chunk_size=200,  # 小块大小
            max_workers=2    # 少量工作进程
        )
        
        if results is not None:
            print(f"✅ 并行处理成功，处理了 {len(results)} 条记录")
            
            # 验证结果
            if 'calculation_successful' in results.columns:
                success_count = results['calculation_successful'].sum()
                total_count = len(results)
                success_rate = success_count / total_count * 100
                print(f"成功率: {success_rate:.1f}% ({success_count}/{total_count})")
            
            # 检查燃油计算结果
            fuel_columns = [col for col in results.columns if 'fuel' in col.lower()]
            if fuel_columns:
                print(f"燃油相关列: {fuel_columns}")
                
                # 显示一些统计信息
                for col in fuel_columns[:3]:  # 只显示前3个燃油列
                    if results[col].dtype in ['float64', 'int64']:
                        avg_value = results[col].mean()
                        print(f"  {col} 平均值: {avg_value:.2f}")
            
            return True
        else:
            print("❌ 并行处理失败")
            return False
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False
    
    finally:
        # 清理临时目录
        try:
            shutil.rmtree(temp_dir)
        except:
            pass

if __name__ == '__main__':
    print("🚀 开始测试2024年数据并行处理功能...")
    
    result = test_small_scale_parallel_processing()
    
    if result:
        print("\n🎉 2024年数据并行处理测试通过！")
        print("现在可以运行完整的并行处理程序了。")
    else:
        print("\n❌ 测试失败，请检查代码。") 