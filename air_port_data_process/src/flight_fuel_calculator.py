import os
import pandas as pd

# 1. 读取Excel数据，打印所有字段名
base_dir = os.path.dirname(os.path.abspath(__file__))
data_path = os.path.join(base_dir, '../data/22年1月1日至24年12月31日航班数据.xlsx')
data_path = os.path.abspath(data_path)

# 只读取前1行，获取字段名
try:
    df = pd.read_excel(data_path, nrows=1)
    columns = list(df.columns)
    print('字段名:', columns)
    # 保存字段名到txt
    output_dir = os.path.join(base_dir, '../results/tables')
    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, 'flight_data_columns.txt'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(columns))
except Exception as e:
    print('读取数据失败:', e)
    exit(1)

# 其余代码注释掉，避免大文件操作
# # 2. 预留pybada燃油消耗计算函数接口（示例）
# def calculate_fuel_consumption(row):
#     # TODO: 使用pybada库，根据航班参数计算燃油消耗
#     # 示例：假设有速度、距离、机型等字段
#     # 这里返回一个虚拟值，后续替换为真实计算
#     return 123.45
#
# # 3. 计算每趟航班燃油消耗，并插入新字段
# # 假设每行代表一趟航班
# if '燃油消耗_kg' not in df.columns:
#     df['燃油消耗_kg'] = df.apply(calculate_fuel_consumption, axis=1)
#
# # 4. 保存结果到results/tables/
# output_path = os.path.join(base_dir, '../results/tables/flight_fuel_consumption_sample.xlsx')
# os.makedirs(os.path.dirname(output_path), exist_ok=True)
# df.to_excel(output_path, index=False)
# print(f'已保存带燃油消耗的样例数据到: {output_path}') 