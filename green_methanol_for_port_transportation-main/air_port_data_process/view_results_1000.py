import pandas as pd

# 读取1000条记录的计算结果
df_dict = pd.read_excel('results/tables/航班燃油消耗计算结果_1000条.xlsx', sheet_name=None)

print("=== 工作表列表 ===")
print(list(df_dict.keys()))

print("\n=== 统计汇总 ===")
summary_df = df_dict['统计汇总']
print(summary_df)

print("\n=== 前10行航班燃油消耗数据 ===")
fuel_df = df_dict['航班燃油消耗']
columns_to_show = ['机型', 'ICAO代码', '里程（公里）', '人数', '载客率', '燃油消耗_kg']
print(fuel_df.head(10)[columns_to_show])

print("\n=== 按机型统计燃油消耗 ===")
if '机型统计' in df_dict:
    aircraft_stats = df_dict['机型统计']
    print(aircraft_stats)

print("\n=== 燃油消耗分布统计 ===")
fuel_consumption = fuel_df['燃油消耗_kg']
print(f"最小燃油消耗: {fuel_consumption.min():.2f} kg")
print(f"最大燃油消耗: {fuel_consumption.max():.2f} kg")
print(f"中位数燃油消耗: {fuel_consumption.median():.2f} kg")
print(f"标准差: {fuel_consumption.std():.2f} kg")

print("\n=== 载客率分析 ===")
load_factor = fuel_df['载客率']
print(f"平均载客率: {load_factor.mean():.2%}")
print(f"载客率中位数: {load_factor.median():.2%}")
print(f"满载航班比例: {(load_factor >= 1.0).mean():.2%}")

print("\n=== 距离分析 ===")
distance = fuel_df['里程（公里）']
print(f"平均飞行距离: {distance.mean():.0f} km")
print(f"最短距离: {distance.min():.0f} km")
print(f"最长距离: {distance.max():.0f} km")

# 按距离分段分析燃油效率
print("\n=== 按距离分段的燃油效率分析 ===")
fuel_df['距离分段'] = pd.cut(fuel_df['里程（公里）'], 
                        bins=[0, 500, 1500, 3000, float('inf')], 
                        labels=['短程(<500km)', '中程(500-1500km)', '长程(1500-3000km)', '超长程(>3000km)'])

distance_analysis = fuel_df.groupby('距离分段').agg({
    '燃油消耗_kg': ['count', 'mean'],
    '里程（公里）': 'mean',
    '载客率': 'mean'
}).round(2)
distance_analysis.columns = ['航班数', '平均燃油消耗_kg', '平均距离_km', '平均载客率']
print(distance_analysis) 