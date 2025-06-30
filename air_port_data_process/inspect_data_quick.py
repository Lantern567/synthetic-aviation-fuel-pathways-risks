import pandas as pd

# 读取数据
df = pd.read_excel('results/parallel_fuel_calculation/并行计算结果_20250630_011947.xlsx')

print('数据形状:', df.shape)
print('列名:', df.columns.tolist())
print('\n前5行数据:')
print(df.head())

print('\n数据类型:')
print(df.dtypes)

print('\n基本统计信息:')
print(df.describe())

# 检查是否有日期相关的列
date_columns = [col for col in df.columns if 'date' in col.lower() or '日期' in col or '时间' in col]
print('\n日期相关的列:', date_columns)

# 检查航线相关信息
route_columns = [col for col in df.columns if any(keyword in col.lower() for keyword in ['route', 'origin', 'dest', '起', '终', '航线', 'airport'])]
print('\n航线相关的列:', route_columns)

# 检查是否已有燃油相关数据
fuel_columns = [col for col in df.columns if any(keyword in col.lower() for keyword in ['fuel', '燃', '油', 'consumption'])]
print('\n燃油相关的列:', fuel_columns) 