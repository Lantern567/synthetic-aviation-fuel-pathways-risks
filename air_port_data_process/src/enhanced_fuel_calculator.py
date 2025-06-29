"""
增强版航班燃油消耗计算模块
修复里程为0的问题，使用坐标计算距离
"""

import os
import numpy as np
import pandas as pd
import math
from aircraft_mapping import get_icao_code, get_aircraft_capacity, get_cruise_mach, calculate_load_factor
from fuel_consumption_calculator import estimate_fuel_consumption_simple

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    使用Haversine公式计算两点间的球面距离
    
    Args:
        lat1, lon1: 点1的纬度和经度
        lat2, lon2: 点2的纬度和经度
        
    Returns:
        float: 距离（公里）
    """
    # 转换为弧度
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    
    # Haversine公式
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    # 地球半径（公里）
    r = 6371
    
    return c * r

def fix_distance_data(row):
    """
    修复距离数据，当里程为0时使用坐标计算
    
    Args:
        row: 数据行
        
    Returns:
        float: 修复后的距离（公里）
    """
    distance = float(row['里程（公里）'])
    
    # 如果里程大于0，直接使用
    if distance > 0:
        return distance
    
    # 如果里程为0，尝试使用坐标计算
    try:
        # 尝试使用出发/到达城市坐标
        lat1 = float(row['出发城市y']) if pd.notna(row['出发城市y']) else None
        lon1 = float(row['出发城市x']) if pd.notna(row['出发城市x']) else None
        lat2 = float(row['到达城市y']) if pd.notna(row['到达城市y']) else None
        lon2 = float(row['到达城市x']) if pd.notna(row['到达城市x']) else None
        
        if all(coord is not None for coord in [lat1, lon1, lat2, lon2]):
            calculated_distance = haversine_distance(lat1, lon1, lat2, lon2)
            if calculated_distance > 0:
                return calculated_distance
        
        # 如果城市坐标不可用，尝试使用机场坐标
        lat1 = float(row['起飞机场y']) if pd.notna(row['起飞机场y']) else None
        lon1 = float(row['起飞机场x']) if pd.notna(row['起飞机场x']) else None
        lat2 = float(row['降落机场y']) if pd.notna(row['降落机场y']) else None
        lon2 = float(row['降落机场x']) if pd.notna(row['降落机场x']) else None
        
        if all(coord is not None for coord in [lat1, lon1, lat2, lon2]):
            calculated_distance = haversine_distance(lat1, lon1, lat2, lon2)
            if calculated_distance > 0:
                return calculated_distance
        
        # 如果都无法计算，根据城市名称估算距离
        departure = str(row['出发城市']).strip()
        arrival = str(row['到达城市']).strip()
        
        if departure != arrival:
            # 使用一个简单的城市间距离估算
            # 这里可以扩展为更完整的城市距离数据库
            estimated_distance = estimate_city_distance(departure, arrival)
            if estimated_distance > 0:
                return estimated_distance
        
        # 最后，如果所有方法都失败，返回一个默认的最小距离
        print(f"警告: 无法计算 {departure} -> {arrival} 的距离，使用默认值100km")
        return 100.0  # 默认100公里
        
    except Exception as e:
        print(f"计算距离时出错: {e}")
        return 100.0  # 默认值

def estimate_city_distance(city1, city2):
    """
    基于城市名称估算距离的简单方法
    
    Args:
        city1, city2: 城市名称
        
    Returns:
        float: 估算距离（公里）
    """
    
    # 一些常见城市间距离的估算表（可以扩展）
    city_distances = {
        ('阿克苏', '上海'): 3200,
        ('上海', '阿克苏'): 3200,
        ('北京', '上海'): 1200,
        ('上海', '北京'): 1200,
        ('广州', '北京'): 2100,
        ('北京', '广州'): 2100,
        ('深圳', '北京'): 2200,
        ('北京', '深圳'): 2200,
        ('成都', '北京'): 1500,
        ('北京', '成都'): 1500,
    }
    
    # 检查直接匹配
    key1 = (city1, city2)
    key2 = (city2, city1)
    
    if key1 in city_distances:
        return city_distances[key1]
    elif key2 in city_distances:
        return city_distances[key2]
    
    # 如果没有找到，根据城市类型估算
    major_cities = ['北京', '上海', '广州', '深圳', '成都', '重庆', '杭州', '南京', '武汉', '西安']
    
    city1_major = any(major in city1 for major in major_cities)
    city2_major = any(major in city2 for major in major_cities)
    
    if city1_major and city2_major:
        return 1500  # 主要城市间平均距离
    elif city1_major or city2_major:
        return 1000  # 主要城市与其他城市
    else:
        return 500   # 其他城市间
    
def process_enhanced_flight_data(df, batch_size=1000):
    """
    增强版航班数据处理，修复距离问题
    
    Args:
        df (pd.DataFrame): 航班数据
        batch_size (int): 批处理大小
        
    Returns:
        pd.DataFrame: 处理后的数据
    """
    
    print(f"开始处理 {len(df)} 条航班数据...")
    
    # 添加新字段
    df['原始里程'] = df['里程（公里）'].copy()
    df['修复后里程'] = 0.0
    df['距离修复状态'] = ''
    df['ICAO代码'] = ''
    df['载客率'] = 0.0
    df['燃油消耗_kg'] = 0.0
    df['计算状态'] = ''
    
    # 统计信息
    distance_fixed_count = 0
    total_success = 0
    
    # 批量处理
    for i in range(0, len(df), batch_size):
        batch_end = min(i + batch_size, len(df))
        print(f"处理批次: 第{i+1}-{batch_end}条记录")
        
        for idx in range(i, batch_end):
            try:
                row = df.iloc[idx]
                
                # 获取基础数据
                chinese_aircraft = str(row['机型']).strip()
                original_distance = float(row['里程（公里）'])
                passengers = int(row['人数'])
                
                # 修复距离
                fixed_distance = fix_distance_data(row)
                df.loc[idx, '修复后里程'] = fixed_distance
                
                # 记录距离修复状态
                if original_distance == 0 and fixed_distance > 0:
                    df.loc[idx, '距离修复状态'] = '已修复'
                    distance_fixed_count += 1
                elif original_distance > 0:
                    df.loc[idx, '距离修复状态'] = '原始正常'
                else:
                    df.loc[idx, '距离修复状态'] = '使用默认值'
                
                # 转换机型
                icao_code = get_icao_code(chinese_aircraft)
                load_factor = calculate_load_factor(passengers, icao_code)
                
                # 使用修复后的距离计算燃油消耗
                fuel_consumption = estimate_fuel_consumption_simple(
                    fixed_distance, icao_code, passengers
                )
                
                # 更新数据
                df.loc[idx, 'ICAO代码'] = icao_code
                df.loc[idx, '载客率'] = round(load_factor, 3)
                df.loc[idx, '燃油消耗_kg'] = fuel_consumption
                df.loc[idx, '计算状态'] = '成功'
                
                total_success += 1
                
            except Exception as e:
                print(f"第{idx+1}行计算失败: {e}")
                df.loc[idx, '计算状态'] = f'失败: {str(e)}'
    
    print(f"\n处理完成:")
    print(f"总记录数: {len(df)}")
    print(f"成功计算: {total_success}")
    print(f"距离修复: {distance_fixed_count}")
    
    return df

def main_enhanced():
    """增强版主函数"""
    
    try:
        # 设置路径
        base_dir = os.path.dirname(os.path.abspath(__file__))
        data_path = os.path.join(base_dir, '../data/22年1月1日至24年12月31日航班数据.xlsx')
        output_dir = os.path.join(base_dir, '../results/tables')
        os.makedirs(output_dir, exist_ok=True)
        
        print("=== 增强版燃油消耗计算 ===")
        print("开始读取航班数据...")
        
        # 读取数据
        max_rows = 1000
        df = pd.read_excel(data_path, nrows=max_rows)
        
        print(f"读取数据: {len(df)} 条记录")
        print(f"原始数据中里程为0的记录: {(df['里程（公里）'] == 0).sum()} 条")
        
        # 处理数据
        processed_df = process_enhanced_flight_data(df)
        
        # 统计结果
        success_df = processed_df[processed_df['计算状态'] == '成功']
        zero_fuel_count = (success_df['燃油消耗_kg'] == 0).sum()
        
        print(f"\n=== 处理结果 ===")
        print(f"成功计算: {len(success_df)} 条")
        print(f"燃油消耗为0的记录: {zero_fuel_count} 条")
        print(f"距离修复统计:")
        print(processed_df['距离修复状态'].value_counts())
        
        # 保存结果
        output_path = os.path.join(output_dir, f'增强版燃油消耗计算结果_{max_rows}条.xlsx')
        
        with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
            processed_df.to_excel(writer, sheet_name='航班燃油消耗', index=False)
            
            # 统计汇总
            if len(success_df) > 0:
                summary_data = {
                    '指标': [
                        '总航班数', '成功计算数', '成功率%', 
                        '距离修复数', '燃油消耗为0数',
                        '总燃油消耗_kg', '平均燃油消耗_kg', '平均载客率%'
                    ],
                    '数值': [
                        len(df),
                        len(success_df),
                        f"{len(success_df)/len(df)*100:.1f}",
                        (processed_df['距离修复状态'] == '已修复').sum(),
                        zero_fuel_count,
                        f"{success_df['燃油消耗_kg'].sum():,.2f}",
                        f"{success_df['燃油消耗_kg'].mean():,.2f}",
                        f"{success_df['载客率'].mean()*100:.1f}"
                    ]
                }
                summary_df = pd.DataFrame(summary_data)
                summary_df.to_excel(writer, sheet_name='统计汇总', index=False)
                
                # 距离修复详情
                distance_repair = processed_df[processed_df['距离修复状态'] == '已修复'][
                    ['出发城市', '到达城市', '原始里程', '修复后里程', '燃油消耗_kg']
                ]
                distance_repair.to_excel(writer, sheet_name='距离修复详情', index=False)
        
        print(f"\n结果已保存到: {output_path}")
        return processed_df
        
    except Exception as e:
        print(f"处理过程中发生错误: {e}")
        raise

if __name__ == "__main__":
    result_df = main_enhanced() 