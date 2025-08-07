"""
创建简单的测试可视化，使用本地地图样式
"""

import pandas as pd
import pydeck as pdk
import os

def create_simple_visualization():
    """创建一个简单的不依赖网络的可视化"""
    
    # 创建简单的测试数据
    test_data = pd.DataFrame({
        'lat': [39.9, 31.2, 23.1, 26.1],
        'lon': [116.4, 121.5, 113.3, 119.3],
        'city': ['北京', '上海', '广州', '福州'],
        'value': [1000, 800, 600, 400]
    })
    
    # 创建散点图层
    layer = pdk.Layer(
        'ScatterplotLayer',
        test_data,
        get_position=['lon', 'lat'],
        get_color=[200, 30, 0, 160],
        get_radius=50000,
        pickable=True,
    )
    
    # 设置视图状态
    view_state = pdk.ViewState(
        latitude=32,
        longitude=118,
        zoom=4,
        pitch=0,
        bearing=0
    )
    
    # 创建deck对象，使用不需要网络的地图样式
    deck = pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        map_style=None,  # 不使用地图背景
        tooltip={'text': '城市: {city}\n数值: {value}'}
    )
    
    # 保存为HTML
    output_dir = 'results/html_reports'
    os.makedirs(output_dir, exist_ok=True)
    
    html_file = os.path.join(output_dir, 'simple_test_visualization.html')
    deck.to_html(html_file)
    
    print(f"✅ 简单测试可视化已生成: {html_file}")
    return html_file

if __name__ == "__main__":
    create_simple_visualization() 