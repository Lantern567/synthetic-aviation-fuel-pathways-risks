"""
生成可再生能源数据的交互式HTML可视化
使用plotly生成交互式图表

Author: Claude Code
Date: 2025-11-27
"""

import os
import sys
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
from pathlib import Path
from datetime import datetime

# 设置项目根目录
project_root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(project_root))


def load_data(data_dir: str):
    """加载预处理后的数据"""
    print("="*80)
    print("加载可再生能源数据...")
    print("="*80)

    solar_path = os.path.join(data_dir, 'solar_hourly_complete.csv')
    wind_path = os.path.join(data_dir, 'wind_hourly_complete.csv')

    print(f"\n正在加载太阳能数据...")
    solar_data = pd.read_csv(solar_path)
    print(f"  ✓ {len(solar_data):,} 条记录")

    print(f"\n正在加载风电数据...")
    wind_data = pd.read_csv(wind_path)
    print(f"  ✓ {len(wind_data):,} 条记录")

    return solar_data, wind_data


def create_24h_pattern_chart(solar_data: pd.DataFrame, wind_data: pd.DataFrame):
    """创建24小时发电模式交互式图表"""
    print("\n生成24小时发电模式图表...")

    # 计算24小时平均值
    solar_data['hour_of_day'] = solar_data['hour'] % 24
    wind_data['hour_of_day'] = wind_data['hour'] % 24

    solar_hourly = solar_data.groupby('hour_of_day')['power_output_mw'].mean()
    wind_hourly = wind_data.groupby('hour_of_day')['power_output_mw'].mean()

    # 计算容量因子
    solar_capacity = solar_data.groupby('plant_name')['capacity_mw'].first().sum()
    wind_capacity = wind_data.groupby('plant_name')['capacity_mw'].first().sum()
    solar_cf = (solar_hourly / solar_capacity * 100)
    wind_cf = (wind_hourly / wind_capacity * 100)

    # 创建子图
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            '太阳能24小时发电模式',
            '风电24小时发电模式',
            '24小时发电量对比',
            '24小时容量因子对比'
        ),
        specs=[[{'type': 'scatter'}, {'type': 'scatter'}],
               [{'type': 'bar'}, {'type': 'scatter'}]]
    )

    # 1. 太阳能24小时模式
    fig.add_trace(
        go.Scatter(
            x=solar_hourly.index,
            y=solar_hourly.values,
            mode='lines+markers',
            name='太阳能',
            line=dict(color='#FF9500', width=3),
            marker=dict(size=8),
            fill='tozeroy',
            fillcolor='rgba(255, 149, 0, 0.2)',
            hovertemplate='小时: %{x}<br>发电量: %{y:.2f} MW<extra></extra>'
        ),
        row=1, col=1
    )

    # 2. 风电24小时模式
    fig.add_trace(
        go.Scatter(
            x=wind_hourly.index,
            y=wind_hourly.values,
            mode='lines+markers',
            name='风电',
            line=dict(color='#34C759', width=3),
            marker=dict(size=8),
            fill='tozeroy',
            fillcolor='rgba(52, 199, 89, 0.2)',
            hovertemplate='小时: %{x}<br>发电量: %{y:.2f} MW<extra></extra>'
        ),
        row=1, col=2
    )

    # 3. 对比柱状图
    fig.add_trace(
        go.Bar(
            x=solar_hourly.index,
            y=solar_hourly.values,
            name='太阳能',
            marker_color='#FF9500',
            hovertemplate='小时: %{x}<br>太阳能: %{y:.2f} MW<extra></extra>'
        ),
        row=2, col=1
    )
    fig.add_trace(
        go.Bar(
            x=wind_hourly.index,
            y=wind_hourly.values,
            name='风电',
            marker_color='#34C759',
            hovertemplate='小时: %{x}<br>风电: %{y:.2f} MW<extra></extra>'
        ),
        row=2, col=1
    )

    # 4. 容量因子对比
    fig.add_trace(
        go.Scatter(
            x=solar_cf.index,
            y=solar_cf.values,
            mode='lines+markers',
            name='太阳能容量因子',
            line=dict(color='#FF9500', width=3),
            marker=dict(size=8),
            hovertemplate='小时: %{x}<br>容量因子: %{y:.2f}%<extra></extra>'
        ),
        row=2, col=2
    )
    fig.add_trace(
        go.Scatter(
            x=wind_cf.index,
            y=wind_cf.values,
            mode='lines+markers',
            name='风电容量因子',
            line=dict(color='#34C759', width=3),
            marker=dict(size=8),
            hovertemplate='小时: %{x}<br>容量因子: %{y:.2f}%<extra></extra>'
        ),
        row=2, col=2
    )

    # 更新布局
    fig.update_xaxes(title_text="小时 (0-23)", row=1, col=1, dtick=2)
    fig.update_xaxes(title_text="小时 (0-23)", row=1, col=2, dtick=2)
    fig.update_xaxes(title_text="小时 (0-23)", row=2, col=1, dtick=2)
    fig.update_xaxes(title_text="小时 (0-23)", row=2, col=2, dtick=2)

    fig.update_yaxes(title_text="平均发电量 (MW)", row=1, col=1)
    fig.update_yaxes(title_text="平均发电量 (MW)", row=1, col=2)
    fig.update_yaxes(title_text="平均发电量 (MW)", row=2, col=1)
    fig.update_yaxes(title_text="容量因子 (%)", row=2, col=2)

    fig.update_layout(
        title_text="可再生能源24小时发电模式分析",
        height=900,
        showlegend=True,
        hovermode='x unified',
        template='plotly_white'
    )

    print("  ✓ 24小时发电模式图表已生成")
    return fig


def create_statistics_chart(solar_data: pd.DataFrame, wind_data: pd.DataFrame):
    """创建统计分析交互式图表"""
    print("\n生成统计分析图表...")

    # 创建子图
    fig = make_subplots(
        rows=2, cols=3,
        subplot_titles=(
            '太阳能发电量分布',
            '风电发电量分布',
            '电站/风电场容量分布',
            '一周发电量时间序列',
            '容量因子分布',
            '地理分布对比'
        ),
        specs=[[{'type': 'histogram'}, {'type': 'histogram'}, {'type': 'histogram'}],
               [{'type': 'scatter'}, {'type': 'histogram'}, {'type': 'scatter'}]]
    )

    # 1. 太阳能发电量分布
    solar_power = solar_data[solar_data['power_output_mw'] > 0]['power_output_mw']
    fig.add_trace(
        go.Histogram(
            x=solar_power,
            nbinsx=50,
            name='太阳能',
            marker_color='#FF9500',
            opacity=0.7,
            hovertemplate='发电量: %{x:.2f} MW<br>频次: %{y}<extra></extra>'
        ),
        row=1, col=1
    )

    # 2. 风电发电量分布
    wind_power = wind_data[wind_data['power_output_mw'] > 0]['power_output_mw']
    fig.add_trace(
        go.Histogram(
            x=wind_power,
            nbinsx=50,
            name='风电',
            marker_color='#34C759',
            opacity=0.7,
            hovertemplate='发电量: %{x:.2f} MW<br>频次: %{y}<extra></extra>'
        ),
        row=1, col=2
    )

    # 3. 容量分布对比
    solar_capacity = solar_data.groupby('plant_name')['capacity_mw'].first()
    wind_capacity = wind_data.groupby('plant_name')['capacity_mw'].first()

    fig.add_trace(
        go.Histogram(
            x=solar_capacity,
            nbinsx=30,
            name='太阳能电站',
            marker_color='#FF9500',
            opacity=0.6,
            hovertemplate='容量: %{x:.2f} MW<br>数量: %{y}<extra></extra>'
        ),
        row=1, col=3
    )
    fig.add_trace(
        go.Histogram(
            x=wind_capacity,
            nbinsx=30,
            name='风电场',
            marker_color='#34C759',
            opacity=0.6,
            hovertemplate='容量: %{x:.2f} MW<br>数量: %{y}<extra></extra>'
        ),
        row=1, col=3
    )

    # 4. 一周发电量时间序列
    sample_hours = 168  # 一周
    solar_timeseries = solar_data[solar_data['hour'] < sample_hours].groupby('hour')['power_output_mw'].sum()
    wind_timeseries = wind_data[wind_data['hour'] < sample_hours].groupby('hour')['power_output_mw'].sum()

    fig.add_trace(
        go.Scatter(
            x=solar_timeseries.index,
            y=solar_timeseries.values,
            mode='lines',
            name='太阳能总发电',
            line=dict(color='#FF9500', width=2),
            hovertemplate='小时: %{x}<br>总发电量: %{y:.2f} MW<extra></extra>'
        ),
        row=2, col=1
    )
    fig.add_trace(
        go.Scatter(
            x=wind_timeseries.index,
            y=wind_timeseries.values,
            mode='lines',
            name='风电总发电',
            line=dict(color='#34C759', width=2),
            hovertemplate='小时: %{x}<br>总发电量: %{y:.2f} MW<extra></extra>'
        ),
        row=2, col=1
    )

    # 5. 容量因子分布
    solar_cf = solar_data['power_output_mw'] / solar_data['capacity_mw'] * 100
    wind_cf = wind_data['power_output_mw'] / wind_data['capacity_mw'] * 100

    fig.add_trace(
        go.Histogram(
            x=solar_cf[solar_cf > 0],
            nbinsx=50,
            name='太阳能容量因子',
            marker_color='#FF9500',
            opacity=0.6,
            hovertemplate='容量因子: %{x:.2f}%<br>频次: %{y}<extra></extra>'
        ),
        row=2, col=2
    )
    fig.add_trace(
        go.Histogram(
            x=wind_cf[wind_cf > 0],
            nbinsx=50,
            name='风电容量因子',
            marker_color='#34C759',
            opacity=0.6,
            hovertemplate='容量因子: %{x:.2f}%<br>频次: %{y}<extra></extra>'
        ),
        row=2, col=2
    )

    # 6. 地理分布（抽样）
    solar_sample = solar_data.groupby('plant_name')[['latitude', 'longitude', 'capacity_mw']].first().sample(min(500, len(solar_data['plant_name'].unique())))
    wind_sample = wind_data.groupby('plant_name')[['latitude', 'longitude', 'capacity_mw']].first().sample(min(500, len(wind_data['plant_name'].unique())))

    fig.add_trace(
        go.Scatter(
            x=solar_sample['longitude'],
            y=solar_sample['latitude'],
            mode='markers',
            name='太阳能电站',
            marker=dict(
                color='#FF9500',
                size=5,
                opacity=0.6
            ),
            hovertemplate='经度: %{x:.2f}<br>纬度: %{y:.2f}<br>容量: %{marker.size:.2f} MW<extra></extra>'
        ),
        row=2, col=3
    )
    fig.add_trace(
        go.Scatter(
            x=wind_sample['longitude'],
            y=wind_sample['latitude'],
            mode='markers',
            name='风电场',
            marker=dict(
                color='#34C759',
                size=5,
                opacity=0.6
            ),
            hovertemplate='经度: %{x:.2f}<br>纬度: %{y:.2f}<br>容量: %{marker.size:.2f} MW<extra></extra>'
        ),
        row=2, col=3
    )

    # 更新布局
    fig.update_xaxes(title_text="发电量 (MW)", row=1, col=1)
    fig.update_xaxes(title_text="发电量 (MW)", row=1, col=2)
    fig.update_xaxes(title_text="容量 (MW)", row=1, col=3)
    fig.update_xaxes(title_text="小时", row=2, col=1)
    fig.update_xaxes(title_text="容量因子 (%)", row=2, col=2)
    fig.update_xaxes(title_text="经度", row=2, col=3)

    fig.update_yaxes(title_text="频次", row=1, col=1)
    fig.update_yaxes(title_text="频次", row=1, col=2)
    fig.update_yaxes(title_text="电站数量", row=1, col=3)
    fig.update_yaxes(title_text="总发电量 (MW)", row=2, col=1)
    fig.update_yaxes(title_text="频次", row=2, col=2)
    fig.update_yaxes(title_text="纬度", row=2, col=3)

    fig.update_layout(
        title_text="可再生能源统计分析",
        height=900,
        showlegend=True,
        template='plotly_white'
    )

    print("  ✓ 统计分析图表已生成")
    return fig


def create_summary_dashboard(solar_data: pd.DataFrame, wind_data: pd.DataFrame):
    """创建综合仪表板"""
    print("\n生成综合仪表板...")

    # 计算关键指标
    solar_capacity = solar_data.groupby('plant_name')['capacity_mw'].first().sum()
    wind_capacity = wind_data.groupby('plant_name')['capacity_mw'].first().sum()
    total_capacity = solar_capacity + wind_capacity

    solar_plants = solar_data['plant_name'].nunique()
    wind_plants = wind_data['plant_name'].nunique()

    solar_avg_power = solar_data[solar_data['power_output_mw'] > 0]['power_output_mw'].mean()
    wind_avg_power = wind_data[wind_data['power_output_mw'] > 0]['power_output_mw'].mean()

    # 创建仪表板
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            '装机容量占比',
            '电站/风电场数量对比',
            '平均发电量对比',
            '总装机容量'
        ),
        specs=[[{'type': 'pie'}, {'type': 'bar'}],
               [{'type': 'bar'}, {'type': 'indicator'}]]
    )

    # 1. 装机容量饼图
    fig.add_trace(
        go.Pie(
            labels=['太阳能', '风电'],
            values=[solar_capacity, wind_capacity],
            marker=dict(colors=['#FF9500', '#34C759']),
            hovertemplate='%{label}<br>容量: %{value:.2f} MW<br>占比: %{percent}<extra></extra>',
            textposition='inside',
            textinfo='label+percent'
        ),
        row=1, col=1
    )

    # 2. 电站数量对比
    fig.add_trace(
        go.Bar(
            x=['太阳能电站', '风电场'],
            y=[solar_plants, wind_plants],
            marker=dict(color=['#FF9500', '#34C759']),
            text=[solar_plants, wind_plants],
            textposition='auto',
            hovertemplate='%{x}<br>数量: %{y}<extra></extra>'
        ),
        row=1, col=2
    )

    # 3. 平均发电量对比
    fig.add_trace(
        go.Bar(
            x=['太阳能', '风电'],
            y=[solar_avg_power, wind_avg_power],
            marker=dict(color=['#FF9500', '#34C759']),
            text=[f'{solar_avg_power:.2f} MW', f'{wind_avg_power:.2f} MW'],
            textposition='auto',
            hovertemplate='%{x}<br>平均发电量: %{y:.2f} MW<extra></extra>'
        ),
        row=2, col=1
    )

    # 4. 总装机容量指示器
    fig.add_trace(
        go.Indicator(
            mode="number+delta",
            value=total_capacity,
            title={'text': "总装机容量 (MW)"},
            number={'suffix': " MW", 'font': {'size': 40}},
            delta={'reference': 1000000, 'relative': True},
            domain={'x': [0, 1], 'y': [0, 1]}
        ),
        row=2, col=2
    )

    fig.update_layout(
        title_text="可再生能源综合仪表板",
        height=800,
        showlegend=False,
        template='plotly_white'
    )

    print("  ✓ 综合仪表板已生成")
    return fig


def main():
    """主流程"""
    print("\n" + "="*80)
    print("生成可再生能源交互式HTML可视化")
    print("="*80)
    print()

    # 数据目录
    data_dir = project_root / 'products' / 'aviation_fuel_analysis' / 'resource_flight_data_process' / 'results' / 'preprocessed'
    output_dir = data_dir / 'visualizations'
    os.makedirs(output_dir, exist_ok=True)

    print(f"数据目录: {data_dir}")
    print(f"输出目录: {output_dir}")

    # 加载数据
    solar_data, wind_data = load_data(str(data_dir))

    # 生成24小时模式图表
    fig_24h = create_24h_pattern_chart(solar_data, wind_data)
    html_24h = os.path.join(output_dir, 'renewable_24h_pattern_interactive.html')
    fig_24h.write_html(html_24h)
    print(f"  ✓ 保存到: {html_24h}")

    # 生成统计分析图表
    fig_stats = create_statistics_chart(solar_data, wind_data)
    html_stats = os.path.join(output_dir, 'renewable_statistics_interactive.html')
    fig_stats.write_html(html_stats)
    print(f"  ✓ 保存到: {html_stats}")

    # 生成综合仪表板
    fig_dashboard = create_summary_dashboard(solar_data, wind_data)
    html_dashboard = os.path.join(output_dir, 'renewable_dashboard.html')
    fig_dashboard.write_html(html_dashboard)
    print(f"  ✓ 保存到: {html_dashboard}")

    print("\n" + "="*80)
    print("✓ 所有HTML可视化生成完成！")
    print("="*80)
    print(f"\n请在浏览器中打开以下文件查看交互式可视化：")
    print(f"  1. {html_24h}")
    print(f"  2. {html_stats}")
    print(f"  3. {html_dashboard}")
    print()


if __name__ == "__main__":
    main()
