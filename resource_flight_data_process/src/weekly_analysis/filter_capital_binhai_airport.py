import pandas as pd
import os
from datetime import datetime

def filter_capital_binhai_airports():
    """
    筛选出发机场为首都机场和滨海机场的数据
    """
    # 读取数据
    input_file = 'D:/Green methanol/green_methanol_for_port_transportation-main/green_methanol_for_port_transportation-main/resource_flight_data_process/data/beijing_tianjin_hebei_filtered_data_20250722_204348.csv'
    
    try:
        df = pd.read_csv(input_file, encoding='utf-8')
        print(f"成功读取数据文件，共 {len(df)} 行数据")
        
        # 查看起飞机场列中的唯一值，用于确认机场名称
        print("起飞机场列中的唯一值：")
        print(df['起飞机场'].unique())
        
        # 筛选首都机场和滨海机场的数据
        # 根据机场名称进行筛选
        filtered_df = df[df['起飞机场'].isin(['首都机场', '滨海机场'])]
        
        print(f"筛选后数据：{len(filtered_df)} 行")
        print("各机场数据分布：")
        print(filtered_df['起飞机场'].value_counts())
        
        # 生成输出文件名和路径
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"capital_binhai_airports_data_{timestamp}.xlsx"
        output_path = f"D:/Green methanol/green_methanol_for_port_transportation-main/green_methanol_for_port_transportation-main/results/{output_filename}"
        
        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # 保存为Excel文件
        filtered_df.to_excel(output_path, index=False)
        
        print(f"数据已保存到: {output_path}")
        return output_path, len(filtered_df)
        
    except Exception as e:
        print(f"处理过程中出现错误: {e}")
        return None, 0

if __name__ == "__main__":
    output_file, record_count = filter_capital_binhai_airports()
    if output_file:
        print(f"筛选完成！")
        print(f"输出文件: {output_file}")
        print(f"数据行数: {record_count}")
    else:
        print("筛选失败！")