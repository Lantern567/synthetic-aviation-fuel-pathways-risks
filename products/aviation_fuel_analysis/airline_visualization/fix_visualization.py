"""
修复航线可视化 - 创建不依赖网络的版本
"""

import pandas as pd
import pydeck as pdk
import os
import logging
from datetime import datetime

def fix_visualization():
    """重新生成不依赖网络的可视化"""
    
    print("🔧 正在修复可视化问题...")
    
    # 1. 检查数据文件
    data_file = "../air_port_data_process/data/22年1月1日至24年12月31日航班数据.xlsx"
    if not os.path.exists(data_file):
        print(f"❌ 数据文件不存在: {data_file}")
        return
    
    # 2. 读取样本数据
    print("📊 正在读取数据...")
    try:
        df = pd.read_excel(data_file, nrows=1000)  # 只读取1000行用于测试
        print(f"✅ 成功读取 {len(df)} 行数据")
    except Exception as e:
        print(f"❌ 读取数据失败: {e}")
        return
    
    # 3. 数据预处理
    print("🧹 正在清洗数据...")
    
    # 检查必要的列
    required_cols = ['出发城市', '到达城市', '出发城市x', '出发城市y', '到达城市x', '到达城市y']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"❌ 缺少必要列: {missing_cols}")
        print(f"可用列: {list(df.columns)}")
        return
    
    # 清洗坐标数据
    df = df.dropna(subset=['出发城市x', '出发城市y', '到达城市x', '到达城市y'])
    df = df[(df['出发城市x'] >= 73) & (df['出发城市x'] <= 135)]
    df = df[(df['出发城市y'] >= 18) & (df['出发城市y'] <= 54)]
    df = df[(df['到达城市x'] >= 73) & (df['到达城市x'] <= 135)]
    df = df[(df['到达城市y'] >= 18) & (df['到达城市y'] <= 54)]
    
    print(f"✅ 清洗后剩余 {len(df)} 行有效数据")
    
    if len(df) == 0:
        print("❌ 没有有效数据")
        return
    
    # 4. 创建航线数据
    route_data = []
    for _, row in df.head(100).iterrows():  # 只用前100条航线
        route_data.append({
            'start_lat': row['出发城市y'],
            'start_lon': row['出发城市x'],
            'end_lat': row['到达城市y'],
            'end_lon': row['到达城市x'],
            'from_city': row['出发城市'],
            'to_city': row['到达城市']
        })
    
    route_df = pd.DataFrame(route_data)
    
    # 5. 创建城市数据
    cities = []
    for _, row in df.iterrows():
        cities.extend([
            {'city': row['出发城市'], 'lat': row['出发城市y'], 'lon': row['出发城市x']},
            {'city': row['到达城市'], 'lat': row['到达城市y'], 'lon': row['到达城市x']}
        ])
    
    city_df = pd.DataFrame(cities).drop_duplicates(subset=['city'])
    city_counts = pd.DataFrame(cities).groupby('city').size().reset_index(name='flight_count')
    city_df = city_df.merge(city_counts, on='city')
    
    print(f"✅ 创建了 {len(route_df)} 条航线和 {len(city_df)} 个城市")
    
    # 6. 创建可视化图层 - 使用离线地图样式
    print("🎨 正在创建可视化...")
    
    # 航线图层
    route_layer = pdk.Layer(
        'ArcLayer',
        route_df,
        get_source_position=['start_lon', 'start_lat'],
        get_target_position=['end_lon', 'end_lat'],
        get_source_color=[0, 128, 200],
        get_target_color=[200, 0, 80],
        auto_highlight=True,
        width_scale=0.0001,
        get_width=5,
        width_min_pixels=3,
        width_max_pixels=30,
    )
    
    # 城市图层
    city_layer = pdk.Layer(
        'ScatterplotLayer',
        city_df,
        get_position=['lon', 'lat'],
        get_color=[200, 30, 0, 160],
        get_radius='flight_count',
        radius_scale=1000,
        radius_min_pixels=4,
        radius_max_pixels=60,
        pickable=True,
    )
    
    # 设置视图状态
    view_state = pdk.ViewState(
        latitude=32,
        longitude=110,
        zoom=4,
        pitch=30,
        bearing=0
    )
    
    # 创建deck对象 - 不使用在线地图
    deck = pdk.Deck(
        layers=[route_layer, city_layer],
        initial_view_state=view_state,
        map_style='',  # 空字符串表示不使用背景地图
        tooltip={
            'html': '<b>城市:</b> {city}<br/><b>航班数:</b> {flight_count}',
            'style': {
                'backgroundColor': 'steelblue',
                'color': 'white'
            }
        }
    )
    
    # 7. 保存HTML文件
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = 'results/html_reports'
    os.makedirs(output_dir, exist_ok=True)
    
    html_file = os.path.join(output_dir, f'fixed_visualization_{timestamp}.html')
    deck.to_html(html_file)
    
    print(f"✅ 修复的可视化已生成: {html_file}")
    
    # 8. 尝试创建matplotlib备用图
    try:
        import matplotlib.pyplot as plt
        import matplotlib
        matplotlib.use('Agg')  # 使用非交互式后端
        
        plt.figure(figsize=(12, 8))
        plt.scatter(city_df['lon'], city_df['lat'], s=city_df['flight_count']*2, 
                   alpha=0.6, c='red')
        
        # 绘制航线
        for _, route in route_df.head(50).iterrows():
            plt.plot([route['start_lon'], route['end_lon']], 
                    [route['start_lat'], route['end_lat']], 
                    'b-', alpha=0.3, linewidth=0.5)
        
        plt.xlabel('经度')
        plt.ylabel('纬度')
        plt.title('中国航线网络图')
        plt.grid(True, alpha=0.3)
        
        img_file = os.path.join('results/charts', f'route_network_{timestamp}.png')
        os.makedirs('results/charts', exist_ok=True)
        plt.savefig(img_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"✅ 备用静态图已生成: {img_file}")
        
    except Exception as e:
        print(f"⚠️ 生成静态图失败: {e}")
    
    return html_file

if __name__ == "__main__":
    fix_visualization() 