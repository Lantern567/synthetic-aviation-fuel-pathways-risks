"""
基于pyBADA的航班燃油消耗计算演示程序
处理小批量数据以验证pyBADA功能
"""

import os
import pandas as pd
from pybada_fuel_calculator import PyBADAFuelCalculator

def process_demo_data_with_pybada(sample_size=100):
    """
    使用pyBADA处理演示数据
    
    Args:
        sample_size (int): 处理的样本数量
    """
    
    try:
        # 初始化pyBADA计算器
        print("初始化pyBADA燃油计算器...")
        calculator = PyBADAFuelCalculator()
        
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
        df['计算方法'] = ''
        df['计算状态'] = ''
        
        print("\n开始使用pyBADA计算燃油消耗...")
        success_count = 0
        fail_count = 0
        pybada_count = 0
        fallback_count = 0
        
        for idx, row in df.iterrows():
            try:
                # 获取基础数据
                chinese_aircraft = str(row['机型']).strip()
                distance_km = float(row['里程（公里）'])
                passengers = int(row['人数'])
                
                # 使用pyBADA计算燃油消耗
                result = calculator.calculate_flight_fuel_consumption(
                    chinese_aircraft, distance_km, passengers
                )
                
                # 更新数据
                df.loc[idx, 'ICAO代码'] = result['icao_code']
                df.loc[idx, '载客率'] = result['load_factor']
                df.loc[idx, '燃油消耗_kg'] = result['fuel_consumption_kg']
                df.loc[idx, '计算方法'] = result['calculation_method']
                df.loc[idx, '计算状态'] = '成功'
                
                success_count += 1
                
                # 统计计算方法
                if result['calculation_method'] == 'pybada':
                    pybada_count += 1
                else:
                    fallback_count += 1
                
                # 显示前几条处理结果
                if idx < 5:
                    print(f"第{idx+1}条: {chinese_aircraft} -> {result['icao_code']}, "
                          f"{distance_km}km, {passengers}人, "
                          f"燃油:{result['fuel_consumption_kg']:.2f}kg, "
                          f"方法:{result['calculation_method']}")
                
            except Exception as e:
                fail_count += 1
                df.loc[idx, '计算状态'] = f'失败: {str(e)}'
                print(f"第{idx+1}行计算失败: {e}")
        
        print(f"\n处理完成:")
        print(f"  总计: {len(df)} 条")
        print(f"  成功: {success_count} 条")
        print(f"  失败: {fail_count} 条")
        print(f"  pyBADA计算: {pybada_count} 条")
        print(f"  经验公式: {fallback_count} 条")
        
        # 避免除零错误
        if success_count > 0:
            print(f"  pyBADA使用率: {pybada_count/success_count*100:.1f}%")
        else:
            print(f"  pyBADA使用率: 0.0%")
        
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
            aircraft_stats = successful_df.groupby(['ICAO代码', '计算方法']).agg({
                '燃油消耗_kg': ['count', 'mean', 'sum'],
                '载客率': 'mean',
                '里程（公里）': 'mean'
            }).round(2)
            aircraft_stats.columns = ['航班数', '平均燃油消耗_kg', '总燃油消耗_kg', '平均载客率', '平均里程_km']
            print(aircraft_stats)
            
            # 按计算方法统计
            print(f"\n=== 计算方法对比 ===")
            method_stats = successful_df.groupby('计算方法').agg({
                '燃油消耗_kg': ['count', 'mean', 'sum'],
                '载客率': 'mean',
                '里程（公里）': 'mean'
            }).round(2)
            method_stats.columns = ['航班数', '平均燃油消耗_kg', '总燃油消耗_kg', '平均载客率', '平均里程_km']
            print(method_stats)
        
        # 保存演示结果
        output_path = os.path.join(output_dir, f'pyBADA_燃油消耗计算结果_{sample_size}条.xlsx')
        print(f"\n保存结果到: {output_path}")
        
        with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='航班燃油消耗', index=False)
            
            # 统计汇总
            summary_data = {
                '总航班数': [len(df)],
                '成功计算数': [success_count],
                '失败计算数': [fail_count],
                '成功率': [f"{success_count/len(df)*100:.1f}%"],
                'pyBADA计算数': [pybada_count],
                'pyBADA使用率': [f"{pybada_count/success_count*100:.1f}%" if success_count > 0 else "0%"],
                '总燃油消耗_kg': [successful_df['燃油消耗_kg'].sum() if len(successful_df) > 0 else 0],
                '平均燃油消耗_kg': [successful_df['燃油消耗_kg'].mean() if len(successful_df) > 0 else 0],
                '平均载客率': [successful_df['载客率'].mean() if len(successful_df) > 0 else 0],
            }
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='统计汇总', index=False)
            
            # 机型统计
            if len(successful_df) > 0:
                aircraft_stats.to_excel(writer, sheet_name='机型统计')
                method_stats.to_excel(writer, sheet_name='计算方法对比')
        
        print(f"pyBADA演示处理完成！结果已保存。")
        
        return df
        
    except Exception as e:
        print(f"处理过程中发生错误: {e}")
        import traceback
        print(f"错误详情: {traceback.format_exc()}")
        raise

if __name__ == "__main__":
    # 运行pyBADA演示处理
    result_df = process_demo_data_with_pybada(sample_size=50)  # 处理前50条记录进行快速验证 