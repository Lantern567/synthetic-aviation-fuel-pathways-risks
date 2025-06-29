import pandas as pd

# 读取500条记录的计算结果
df_dict = pd.read_excel('results/tables/综合燃油消耗计算结果_500条.xlsx', sheet_name=None)

print("=== 工作表列表 ===")
print(list(df_dict.keys()))

print("\n=== 统计汇总 ===")
summary_df = df_dict['统计汇总']
print(summary_df)

print("\n=== 航班数据字段名 ===")
fuel_df = df_dict['航班燃油消耗']
print("所有字段:", list(fuel_df.columns))

# 查找人数字段的正确名称
people_col = None
for col in fuel_df.columns:
    if '人数' in str(col):
        people_col = col
        break

print(f"人数字段名: '{people_col}'")

print("\n=== 前5行航班燃油消耗数据 ===")
columns_to_show = ['机型', 'ICAO代码', '里程（公里）', people_col, '载客率', '燃油消耗_kg', '计算方法']
print(fuel_df.head()[columns_to_show])

print("\n=== 按机型统计燃油消耗 ===")
aircraft_stats = fuel_df.groupby('ICAO代码').agg({
    '燃油消耗_kg': ['count', 'mean', 'sum'],
    '载客率': 'mean',
    '里程（公里）': 'mean'
}).round(2)
aircraft_stats.columns = ['航班数', '平均燃油消耗_kg', '总燃油消耗_kg', '平均载客率', '平均里程_km']
print(aircraft_stats)

print("\n=== 总体统计信息 ===")
total_flights = len(fuel_df)
total_fuel = fuel_df['燃油消耗_kg'].sum()
avg_fuel = fuel_df['燃油消耗_kg'].mean()
avg_load_factor = fuel_df['载客率'].mean()

print(f"总航班数: {total_flights}")
print(f"总燃油消耗: {total_fuel:,.2f} kg")
print(f"平均燃油消耗: {avg_fuel:,.2f} kg/航班")
print(f"平均载客率: {avg_load_factor:.2%}") 