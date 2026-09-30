"""
调试省份匹配逻辑
"""

import pandas as pd
from pathlib import Path

# 读取CO₂数据
co2_df = pd.read_csv('data/co2_capture_sources.csv', encoding='utf-8-sig')
coal_co2 = co2_df[co2_df['facility_type']=='coal_power'].head(5)

# 读取GIS数据
project_root = Path('D:/Green methanol/green_methanol_for_port_transportation-main/green_methanol_for_port_transportation-main')
gis_file = project_root / 'products' / 'gis_energy_mapping' / 'gis_data_scraper' / 'scraped_gis_data' / 'coal_power_plants.csv'
gis_df = pd.read_csv(gis_file, encoding='utf-8-sig')

print('=== CO2 DATA SAMPLE ===')
print(coal_co2[['location_name', 'latitude', 'longitude', 'province']])

print('\n=== GIS DATA FIRST 5 ROWS ===')
print(gis_df[['Plant_name', 'Latitude', 'Longitude', 'Subnational_unit__province__sta']].head())

# 测试匹配
print('\n=== TESTING MATCH ===')
coal_co2['match_key'] = (
    coal_co2['location_name'].astype(str) + '_' +
    coal_co2['latitude'].round(6).astype(str) + '_' +
    coal_co2['longitude'].round(6).astype(str)
)

gis_df['match_key'] = (
    gis_df['Plant_name'].astype(str) + '_' +
    gis_df['Latitude'].round(6).astype(str) + '_' +
    gis_df['Longitude'].round(6).astype(str)
)

print('\nCO2 match_keys:')
print(coal_co2['match_key'].tolist())

print('\nGIS match_keys (first 5):')
print(gis_df['match_key'].head().tolist())

# 测试是否有匹配
common_keys = set(coal_co2['match_key']) & set(gis_df['match_key'])
print(f'\nCommon match keys: {len(common_keys)}')
if common_keys:
    print('Example:', list(common_keys)[0])
