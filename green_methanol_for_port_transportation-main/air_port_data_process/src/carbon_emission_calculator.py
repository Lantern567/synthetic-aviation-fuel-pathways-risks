"""
基于pyBADA和燃油消耗的航空碳排放计算模块
根据IPCC和EPA标准计算CO2排放量
"""

import os
import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
import time
from datetime import datetime
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, as_completed
import warnings
warnings.filterwarnings('ignore')

# 航空燃油碳排放系数 (根据EPA和IPCC标准)
# 参考资料:
# - EPA Emission Factors: 9.75 kg CO2/gallon 转换为 kg CO2/kg fuel
# - IATA报告: 3.16 kg CO2/kg jet fuel
# - IPCC标准: 航空煤油密度约0.8 kg/L, 1 gallon = 3.785 L
AVIATION_FUEL_CO2_FACTOR = 3.16  # kg CO2 per kg fuel (标准航空煤油)

class CarbonEmissionCalculator:
    """
    航空碳排放计算器
    基于燃油消耗量和IPCC标准排放系数
    """
    
    def __init__(self):
        """初始化碳排放计算器"""
        self.co2_factor = AVIATION_FUEL_CO2_FACTOR
        self.calculation_stats = {
            'total_calculated': 0,
            'total_emissions': 0.0,
            'calculation_errors': 0
        }
    
    def calculate_co2_emissions(self, fuel_consumption_kg: float, 
                              aircraft_type: str = None) -> Dict:
        """
        计算单次航班的CO2排放量
        
        Args:
            fuel_consumption_kg: 燃油消耗量 (kg)
            aircraft_type: 机型 (可选，用于特定机型的调整系数)
            
        Returns:
            Dict: 包含CO2排放量和相关信息的字典
        """
        try:
            if pd.isna(fuel_consumption_kg) or fuel_consumption_kg <= 0:
                return {
                    'co2_emissions_kg': 0.0,
                    'co2_emissions_tons': 0.0,
                    'emission_factor_used': self.co2_factor,
                    'calculation_status': 'invalid_fuel_data',
                    'error_message': f'无效的燃油消耗数据: {fuel_consumption_kg}'
                }
            
            # 基础CO2排放计算
            co2_emissions_kg = fuel_consumption_kg * self.co2_factor
            co2_emissions_tons = co2_emissions_kg / 1000.0
            
            # 可选: 根据机型进行微调 (预留接口)
            adjusted_factor = self.get_aircraft_specific_factor(aircraft_type)
            if adjusted_factor != self.co2_factor:
                co2_emissions_kg = fuel_consumption_kg * adjusted_factor
                co2_emissions_tons = co2_emissions_kg / 1000.0
            
            self.calculation_stats['total_calculated'] += 1
            self.calculation_stats['total_emissions'] += co2_emissions_kg
            
            return {
                'co2_emissions_kg': round(co2_emissions_kg, 2),
                'co2_emissions_tons': round(co2_emissions_tons, 4),
                'emission_factor_used': adjusted_factor,
                'calculation_status': 'success',
                'error_message': None
            }
            
        except Exception as e:
            self.calculation_stats['calculation_errors'] += 1
            return {
                'co2_emissions_kg': 0.0,
                'co2_emissions_tons': 0.0,
                'emission_factor_used': self.co2_factor,
                'calculation_status': 'calculation_error',
                'error_message': str(e)
            }
    
    def get_aircraft_specific_factor(self, aircraft_type: str) -> float:
        """
        获取特定机型的CO2排放系数调整
        
        Args:
            aircraft_type: 机型代码
            
        Returns:
            float: 调整后的排放系数
        """
        # 预留机型特定调整系数的接口
        # 目前使用统一的标准系数
        aircraft_adjustments = {
            # 可以根据具体机型的发动机效率进行微调
            # 'A320': 3.15,  # 稍微更高效
            # 'B737': 3.17,  # 标准
            # 'B777': 3.16,  # 大型宽体机
        }
        
        if aircraft_type and aircraft_type in aircraft_adjustments:
            return aircraft_adjustments[aircraft_type]
        
        return self.co2_factor
    
    def calculate_per_passenger_emissions(self, total_co2_kg: float, 
                                        passenger_count: int,
                                        load_factor: float = 1.0) -> Dict:
        """
        计算单个乘客的CO2排放量
        
        Args:
            total_co2_kg: 总CO2排放量 (kg)
            passenger_count: 乘客数量
            load_factor: 载客率
            
        Returns:
            Dict: 包含单个乘客排放量的字典
        """
        try:
            if passenger_count <= 0:
                return {
                    'co2_per_passenger_kg': 0.0,
                    'co2_per_passenger_tons': 0.0,
                    'calculation_status': 'invalid_passenger_count'
                }
            
            # 考虑载客率的实际乘客CO2排放
            effective_passengers = passenger_count * load_factor
            if effective_passengers <= 0:
                effective_passengers = passenger_count
            
            co2_per_passenger_kg = total_co2_kg / effective_passengers
            co2_per_passenger_tons = co2_per_passenger_kg / 1000.0
            
            return {
                'co2_per_passenger_kg': round(co2_per_passenger_kg, 2),
                'co2_per_passenger_tons': round(co2_per_passenger_tons, 4),
                'effective_passengers': effective_passengers,
                'calculation_status': 'success'
            }
            
        except Exception as e:
            return {
                'co2_per_passenger_kg': 0.0,
                'co2_per_passenger_tons': 0.0,
                'effective_passengers': 0,
                'calculation_status': 'error',
                'error_message': str(e)
            }
    
    def get_calculation_statistics(self) -> Dict:
        """获取计算统计信息"""
        stats = self.calculation_stats.copy()
        if stats['total_calculated'] > 0:
            stats['average_emissions_per_flight'] = stats['total_emissions'] / stats['total_calculated']
            stats['success_rate'] = (stats['total_calculated'] - stats['calculation_errors']) / stats['total_calculated'] * 100
        else:
            stats['average_emissions_per_flight'] = 0.0
            stats['success_rate'] = 0.0
        
        return stats

def process_flight_carbon_emissions(df_chunk: pd.DataFrame, 
                                  chunk_id: int = 0) -> pd.DataFrame:
    """
    处理单个数据块的碳排放计算
    
    Args:
        df_chunk: 数据块
        chunk_id: 块ID
        
    Returns:
        pd.DataFrame: 包含碳排放计算结果的数据框
    """
    calculator = CarbonEmissionCalculator()
    
    print(f"🔬 处理数据块 {chunk_id}: {len(df_chunk)} 条记录")
    
    # 创建结果列
    df_result = df_chunk.copy()
    
    # 初始化新列
    df_result['co2_emissions_kg'] = 0.0
    df_result['co2_emissions_tons'] = 0.0
    df_result['co2_per_passenger_kg'] = 0.0
    df_result['co2_per_passenger_tons'] = 0.0
    df_result['emission_factor_used'] = AVIATION_FUEL_CO2_FACTOR
    df_result['carbon_calculation_status'] = 'pending'
    
    successful_calculations = 0
    failed_calculations = 0
    
    for idx, row in df_chunk.iterrows():
        try:
            # 获取燃油消耗数据
            fuel_consumption = row.get('燃油消耗_kg', 0)
            aircraft_type = row.get('ICAO代码', row.get('机型', ''))
            passenger_count = row.get('人数', 0)
            load_factor = row.get('载客率', 1.0)
            
            # 计算总CO2排放
            co2_result = calculator.calculate_co2_emissions(
                fuel_consumption, aircraft_type
            )
            
            # 更新结果
            df_result.loc[idx, 'co2_emissions_kg'] = co2_result['co2_emissions_kg']
            df_result.loc[idx, 'co2_emissions_tons'] = co2_result['co2_emissions_tons']
            df_result.loc[idx, 'emission_factor_used'] = co2_result['emission_factor_used']
            df_result.loc[idx, 'carbon_calculation_status'] = co2_result['calculation_status']
            
            # 计算单个乘客排放量
            if co2_result['calculation_status'] == 'success' and passenger_count > 0:
                passenger_result = calculator.calculate_per_passenger_emissions(
                    co2_result['co2_emissions_kg'], passenger_count, load_factor
                )
                df_result.loc[idx, 'co2_per_passenger_kg'] = passenger_result['co2_per_passenger_kg']
                df_result.loc[idx, 'co2_per_passenger_tons'] = passenger_result['co2_per_passenger_tons']
                
                successful_calculations += 1
            else:
                failed_calculations += 1
                
        except Exception as e:
            df_result.loc[idx, 'carbon_calculation_status'] = 'error'
            failed_calculations += 1
            print(f"❌ 处理记录 {idx} 时出错: {e}")
    
    # 打印统计信息
    success_rate = successful_calculations / len(df_chunk) * 100 if len(df_chunk) > 0 else 0
    print(f"✅ 块 {chunk_id} 完成: 成功 {successful_calculations}, 失败 {failed_calculations}, 成功率 {success_rate:.1f}%")
    
    return df_result

def parallel_carbon_emission_calculation(data_file_path: str, 
                                       output_dir: str,
                                       chunk_size: int = 1000,
                                       max_workers: int = None) -> Optional[pd.DataFrame]:
    """
    并行计算航班碳排放
    
    Args:
        data_file_path: 输入数据文件路径
        output_dir: 输出目录
        chunk_size: 数据块大小
        max_workers: 最大工作进程数
        
    Returns:
        pd.DataFrame or None: 计算结果
    """
    start_time = time.time()
    
    print("🌱 === 开始并行碳排放计算 ===")
    print(f"📊 数据文件: {data_file_path}")
    print(f"📂 输出目录: {output_dir}")
    print(f"🔧 数据块大小: {chunk_size}")
    print(f"🕒 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 确定工作进程数
    if max_workers is None:
        max_workers = max(1, mp.cpu_count() - 1)
    
    print(f"🚀 使用 {max_workers} 个工作进程")
    
    try:
        # 读取数据
        print("📖 正在读取数据...")
        if data_file_path.endswith('.xlsx'):
            df = pd.read_excel(data_file_path)
        else:
            df = pd.read_csv(data_file_path)
        
        print(f"✅ 数据读取完成: {len(df):,} 条记录")
        
        # 检查必要字段
        required_fields = ['燃油消耗_kg']
        missing_fields = [field for field in required_fields if field not in df.columns]
        if missing_fields:
            raise ValueError(f"缺少必要字段: {missing_fields}")
        
        # 数据分块
        chunks = []
        for i in range(0, len(df), chunk_size):
            chunk_df = df.iloc[i:i+chunk_size].copy()
            chunks.append((chunk_df, i // chunk_size))
        
        print(f"📦 数据分为 {len(chunks)} 块进行并行处理")
        
        # 并行处理
        all_results = []
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_chunk = {
                executor.submit(process_flight_carbon_emissions, chunk_data, chunk_id): chunk_id
                for chunk_data, chunk_id in chunks
            }
            
            # 收集结果
            for future in as_completed(future_to_chunk):
                chunk_id = future_to_chunk[future]
                try:
                    result = future.result()
                    all_results.append(result)
                    print(f"✅ 块 {chunk_id} 处理完成")
                except Exception as e:
                    print(f"❌ 块 {chunk_id} 处理失败: {e}")
        
        # 合并结果
        if all_results:
            final_result = pd.concat(all_results, ignore_index=True)
            
            # 创建输出目录
            os.makedirs(output_dir, exist_ok=True)
            
            # 保存结果
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = os.path.join(output_dir, f'碳排放计算结果_{timestamp}.xlsx')
            
            final_result.to_excel(output_file, index=False)
            print(f"💾 结果已保存到: {output_file}")
            
            # 统计信息
            total_co2_kg = final_result['co2_emissions_kg'].sum()
            total_co2_tons = total_co2_kg / 1000
            avg_co2_per_flight = final_result['co2_emissions_kg'].mean()
            successful_calculations = len(final_result[final_result['carbon_calculation_status'] == 'success'])
            
            print(f"📊 碳排放计算统计:")
            print(f"   总航班数: {len(final_result):,}")
            print(f"   成功计算: {successful_calculations:,}")
            print(f"   成功率: {successful_calculations/len(final_result)*100:.1f}%")
            print(f"   总CO2排放: {total_co2_tons:,.1f} 吨")
            print(f"   平均每航班CO2: {avg_co2_per_flight:,.1f} kg")
            
            # 保存统计信息
            stats_file = os.path.join(output_dir, f'碳排放统计_{timestamp}.txt')
            with open(stats_file, 'w', encoding='utf-8') as f:
                f.write(f"碳排放计算统计报告\n")
                f.write(f"计算时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"数据文件: {data_file_path}\n")
                f.write(f"处理时间: {time.time() - start_time:.1f} 秒\n\n")
                f.write(f"总航班数: {len(final_result):,}\n")
                f.write(f"成功计算: {successful_calculations:,}\n")
                f.write(f"成功率: {successful_calculations/len(final_result)*100:.1f}%\n")
                f.write(f"总CO2排放: {total_co2_tons:,.1f} 吨\n")
                f.write(f"平均每航班CO2: {avg_co2_per_flight:,.1f} kg\n")
            
            print(f"📈 统计信息已保存到: {stats_file}")
            
            return final_result
        else:
            print("❌ 没有成功处理的数据")
            return None
            
    except Exception as e:
        print(f"❌ 碳排放计算失败: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    # 示例使用
    data_file = 'results/parallel_fuel_calculation/并行计算结果_20250630_011947.xlsx'
    output_dir = 'results/carbon_emissions'
    
    result = parallel_carbon_emission_calculation(
        data_file_path=data_file,
        output_dir=output_dir,
        chunk_size=500,
        max_workers=4
    ) 