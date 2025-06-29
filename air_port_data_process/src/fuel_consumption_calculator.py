"""
航班燃油消耗计算模块
使用pybada库计算每趟航班的燃油消耗，考虑机型和载客数的影响
"""

import os
import numpy as np
import pandas as pd
from aircraft_mapping import get_icao_code, get_aircraft_capacity, get_cruise_mach, calculate_load_factor

def estimate_fuel_consumption_simple(distance_km, icao_code, passengers):
    """
    简化版燃油消耗估算 (当pybada无法直接使用时的备用方案)
    基于经验公式和机型参数
    
    Args:
        distance_km (float): 飞行距离 (公里)
        icao_code (str): ICAO机型代码
        passengers (int): 载客数
        
    Returns:
        float: 燃油消耗量 (公斤)
    """
    
    # 基础燃油消耗率 (升/公里，基于机型)
    base_fuel_rates = {
        'B737': 3.2,   # 波音737
        'B757': 4.1,   # 波音757 
        'B777': 8.5,   # 波音777
        'B787': 6.8,   # 波音787
        'A319': 2.9,   # 空客319
        'A320': 3.1,   # 空客320
        'A321': 3.8,   # 空客321
        'A330': 7.2,   # 空客330
        'A380': 12.5,  # 空客380
        'E190': 2.4,   # ERJ-190
        'CRJ9': 2.1,   # CRJ900
        'CRJ2': 1.8,   # CRJ200
    }
    
    # 获取基础燃油消耗率
    base_rate = base_fuel_rates.get(icao_code, 3.2)  # 默认B737
    
    # 计算载客率影响系数
    load_factor = calculate_load_factor(passengers, icao_code)
    
    # 载客率影响系数 (载客率越高，单位乘客燃油消耗越低)
    load_factor_coefficient = 0.7 + 0.3 * load_factor
    
    # 距离影响系数 (短距离效率较低)
    if distance_km < 500:
        distance_coefficient = 1.3  # 短距离起降燃油消耗较高
    elif distance_km < 1500:
        distance_coefficient = 1.0  # 中等距离
    else:
        distance_coefficient = 0.95  # 长距离效率较高
    
    # 计算燃油消耗 (升)
    fuel_liters = distance_km * base_rate * load_factor_coefficient * distance_coefficient
    
    # 转换为公斤 (航空燃油密度约0.8 kg/L)
    fuel_kg = fuel_liters * 0.8
    
    return round(fuel_kg, 2)

def process_flight_data_batch(df, batch_size=1000):
    """
    批量处理航班数据，计算燃油消耗
    
    Args:
        df (pd.DataFrame): 航班数据
        batch_size (int): 批处理大小
        
    Returns:
        pd.DataFrame: 添加了燃油消耗字段的数据
    """
    
    print(f"开始处理 {len(df)} 条航班数据...")
    
    # 添加新字段
    df['ICAO代码'] = ''
    df['载客率'] = 0.0
    df['燃油消耗_kg'] = 0.0
    df['计算状态'] = ''
    
    # 批量处理
    for i in range(0, len(df), batch_size):
        batch_end = min(i + batch_size, len(df))
        batch_df = df.iloc[i:batch_end].copy()
        
        print(f"处理批次 {i//batch_size + 1}: 第{i+1}-{batch_end}条记录")
        
        for idx, row in batch_df.iterrows():
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
                
            except Exception as e:
                print(f"第{idx+1}行计算失败: {e}")
                df.loc[idx, '计算状态'] = f'失败: {str(e)}'
    
    return df

def main():
    """主函数：读取数据，计算燃油消耗，保存结果"""
    
    try:
        # 设置路径
        base_dir = os.path.dirname(os.path.abspath(__file__))
        data_path = os.path.join(base_dir, '../data/22年1月1日至24年12月31日航班数据.xlsx')
        output_dir = os.path.join(base_dir, '../results/tables')
        os.makedirs(output_dir, exist_ok=True)
        
        print("开始读取航班数据...")
        
        # 先读取前1000条记录进行测试
        max_rows = 1000  # 限制读取行数
        df = pd.read_excel(data_path, nrows=max_rows)
        
        print(f"数据文件字段: {list(df.columns)}")
        print(f"读取数据: {len(df)} 条记录")
        
        # 处理数据
        print("开始计算燃油消耗...")
        processed_df = process_flight_data_batch(df, batch_size=200)
        
        # 计算统计信息
        success_count = (processed_df['计算状态'] == '成功').sum()
        print(f"处理完成: 成功 {success_count}/{len(processed_df)} 条")
        
        # 保存结果
        output_path = os.path.join(output_dir, f'航班燃油消耗计算结果_{max_rows}条.xlsx')
        print(f"保存结果到: {output_path}")
        
        with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
            processed_df.to_excel(writer, sheet_name='航班燃油消耗', index=False)
            
            # 创建统计汇总表
            success_df = processed_df[processed_df['计算状态'] == '成功']
            if len(success_df) > 0:
                summary_stats = {
                    '总航班数': len(processed_df),
                    '成功计算数': success_count,
                    '失败计算数': len(processed_df) - success_count,
                    '总燃油消耗_kg': success_df['燃油消耗_kg'].sum(),
                    '平均燃油消耗_kg': success_df['燃油消耗_kg'].mean(),
                    '平均载客率': success_df['载客率'].mean(),
                }
                
                summary_df = pd.DataFrame([summary_stats])
                summary_df.to_excel(writer, sheet_name='统计汇总', index=False)
                
                # 机型统计
                aircraft_stats = success_df.groupby('ICAO代码').agg({
                    '燃油消耗_kg': ['count', 'mean', 'sum'],
                    '载客率': 'mean',
                    '里程（公里）': 'mean'
                }).round(2)
                aircraft_stats.columns = ['航班数', '平均燃油消耗_kg', '总燃油消耗_kg', '平均载客率', '平均里程_km']
                aircraft_stats.to_excel(writer, sheet_name='机型统计')
        
        print(f"处理完成！")
        print(f"总计: {len(processed_df)} 条航班")
        print(f"成功: {success_count} 条")
        print(f"失败: {len(processed_df) - success_count} 条")
        print(f"结果已保存到: {output_path}")
        
        return processed_df
        
    except Exception as e:
        print(f"处理过程中发生错误: {e}")
        raise

if __name__ == "__main__":
    main() 