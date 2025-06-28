"""
演示版航班燃油消耗计算程序
处理小批量数据以快速验证功能
"""

import os
import pandas as pd
from aircraft_mapping import get_icao_code, get_aircraft_capacity, calculate_load_factor
from fuel_consumption_calculator import estimate_fuel_consumption_simple

def process_demo_data(sample_size=100):
    """
    处理演示数据，快速验证燃油消耗计算功能
    
    Args:
        sample_size (int): 处理的样本数量
    """
    
    try:
        # 设置路径
        base_dir = os.path.dirname(os.path.abspath(__file__))
        data_path = os.path.join(base_dir, '../data/22年1月1日至24年12月31日航班数据.xlsx')
        output_dir = os.path.join(base_dir, '../results/tables')
        os.makedirs(output_dir, exist_ok=True)
        
        print(f"开始处理演示数据 (前{sample_size}条记录)...")
        
        # 读取小批量数据
        df = pd.read_excel(data_path, nrows=sample_size)
        print(f"成功读取 {len(df)} 条航班数据")
        print(f"数据字段: {list(df.columns)}")
        
        # 初始化新字段
        df['ICAO代码'] = ''
        df['载客率'] = 0.0
        df['燃油消耗_kg'] = 0.0
        df['计算状态'] = ''
        
        print("\n开始计算燃油消耗...")
        success_count = 0
        fail_count = 0
        
        for idx, row in df.iterrows():
            try:
                # 获取基础数据
                chinese_aircraft = str(row['机型']).strip()
                distance_km = float(row['里程（公里）'])
                passengers = int(row['人数'])
                
                # 转换机型
                icao_code = get_icao_code(chinese_aircraft)
                load_factor = calculate_load_factor(passengers, icao_code)
                
                # 计算燃油消耗
                fuel_consumption = estimate_fuel_consumption_simple(
                    distance_km, icao_code, passengers
                )
                
                # 更新数据
                df.loc[idx, 'ICAO代码'] = icao_code
                df.loc[idx, '载客率'] = round(load_factor, 3)
                df.loc[idx, '燃油消耗_kg'] = fuel_consumption
                df.loc[idx, '计算状态'] = '成功'
                
                success_count += 1
                
                # 显示前几条处理结果
                if idx < 5:
                    print(f"第{idx+1}条: {chinese_aircraft} -> {icao_code}, {distance_km}km, {passengers}人, 燃油:{fuel_consumption}kg")
                
            except Exception as e:
                fail_count += 1
                df.loc[idx, '计算状态'] = f'失败: {str(e)}'
                print(f"第{idx+1}行计算失败: {e}")
        
        print(f"\n处理完成: 成功 {success_count} 条, 失败 {fail_count} 条")
        
        # 计算统计信息
        successful_df = df[df['计算状态'] == '成功']
        if len(successful_df) > 0:
            total_fuel = successful_df['燃油消耗_kg'].sum()
            avg_fuel = successful_df['燃油消耗_kg'].mean()
            avg_load_factor = successful_df['载客率'].mean()
            
            print(f"\n=== 统计结果 ===")
            print(f"总燃油消耗: {total_fuel:,.2f} kg")
            print(f"平均燃油消耗: {avg_fuel:,.2f} kg/航班")
            print(f"平均载客率: {avg_load_factor:.2%}")
            
            # 按机型统计
            print(f"\n=== 机型燃油消耗统计 ===")
            aircraft_stats = successful_df.groupby('ICAO代码').agg({
                '燃油消耗_kg': ['count', 'mean', 'sum'],
                '载客率': 'mean',
                '里程（公里）': 'mean'
            }).round(2)
            aircraft_stats.columns = ['航班数', '平均燃油消耗_kg', '总燃油消耗_kg', '平均载客率', '平均里程_km']
            print(aircraft_stats)
        
        # 保存演示结果
        output_path = os.path.join(output_dir, f'演示_燃油消耗计算结果_{sample_size}条.xlsx')
        print(f"\n保存结果到: {output_path}")
        
        with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='航班燃油消耗', index=False)
            
            # 统计汇总
            summary_data = {
                '总航班数': [len(df)],
                '成功计算数': [success_count],
                '失败计算数': [fail_count],
                '成功率': [f"{success_count/len(df)*100:.1f}%"],
                '总燃油消耗_kg': [successful_df['燃油消耗_kg'].sum() if len(successful_df) > 0 else 0],
                '平均燃油消耗_kg': [successful_df['燃油消耗_kg'].mean() if len(successful_df) > 0 else 0],
                '平均载客率': [successful_df['载客率'].mean() if len(successful_df) > 0 else 0],
            }
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='统计汇总', index=False)
            
            # 机型统计
            if len(successful_df) > 0:
                aircraft_stats.to_excel(writer, sheet_name='机型统计')
        
        print(f"演示处理完成！结果已保存。")
        
        return df
        
    except Exception as e:
        print(f"处理过程中发生错误: {e}")
        raise

if __name__ == "__main__":
    # 运行演示处理
    result_df = process_demo_data(sample_size=200)  # 处理前200条记录 