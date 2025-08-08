import os
import pandas as pd

# 获取当前脚本所在目录
base_dir = os.path.dirname(os.path.abspath(__file__))
file_path = os.path.join(base_dir, '../data/22年1月1日至24年12月31日航班数据.xlsx')

# 读取Excel文件
# 支持中文路径
file_path = os.path.abspath(file_path)
df = pd.read_excel(file_path)

# 提取出发机场名称、坐标和起飞时间、降落时间、日期
cols = ['起飞机场', '起飞机场y', '起飞机场x', '起飞时间', '降落时间', '日期']
departure_info = df[cols].drop_duplicates()

# 保存为csv
output_path = os.path.join(base_dir, '../results/tables/departure_airport_info.csv')
output_path = os.path.abspath(output_path)
departure_info.to_csv(output_path, index=False, encoding='utf-8-sig')

print(f'已提取并保存到 {output_path}') 