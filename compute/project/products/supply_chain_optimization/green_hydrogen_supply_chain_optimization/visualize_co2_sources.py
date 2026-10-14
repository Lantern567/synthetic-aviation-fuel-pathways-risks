"""
CO₂捕获源数据可视化

生成交互式地图和统计图表，展示CO₂捕获源的地理分布和统计特征。

输出：
1. 交互式地图：results/figures/co2_sources_map.html
2. 统计图表：results/figures/co2_sources_analysis.png

作者：Claude Code
创建日期：2025-10-13
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import pydeck as pdk
from pathlib import Path
import logging
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 配置matplotlib中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

# 设施类型颜色映射
FACILITY_COLORS = {
    'coal_power': [255, 69, 0],      # 红橙色
    'gas_power': [30, 144, 255],      # 道奇蓝
    'oil_refinery': [50, 205, 50]     # 青柠绿
}

FACILITY_NAMES = {
    'coal_power': '燃煤电厂',
    'gas_power': '天然气电厂',
    'oil_refinery': '石油炼厂'
}


def load_data(data_path: str) -> pd.DataFrame:
    """加载CO₂捕获源数据"""
    logger.info(f"Loading data from: {data_path}")
    df = pd.read_csv(data_path, encoding='utf-8-sig')
    logger.info(f"Loaded {len(df)} records")

    # 修复province字段：从原始GIS数据重新读取正确的省份信息
    df = fix_province_data(df)

    return df


def fix_province_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    修复province字段：从原始GIS数据重新读取正确的省份信息

    问题：燃煤电厂数据的Province字段全部为Unknown，因为原始数据使用的字段名是
          'Subnational_unit__province__sta' 而不是 'Province'

    解决方案：使用设施名称和坐标匹配原始GIS数据，重新获取省份信息
    """
    logger.info("Fixing province data...")

    # 获取GIS数据目录
    project_root = Path(__file__).parent.parent.parent.parent.parent
    gis_data_dir = project_root / 'products' / 'gis_energy_mapping' / 'gis_data_scraper' / 'scraped_gis_data'

    # 1. 修复燃煤电厂的province
    coal_mask = df['facility_type'] == 'coal_power'
    if coal_mask.any():
        logger.info(f"Fixing province for {coal_mask.sum()} coal power plants...")

        coal_file = gis_data_dir / 'coal_power_plants.csv'
        if coal_file.exists():
            coal_gis = pd.read_csv(coal_file, encoding='utf-8-sig')

            # 使用名称+坐标来匹配（因为location_id的index不连续）
            # 创建唯一标识符：name_lat_lon
            coal_gis['match_key'] = (
                coal_gis['Plant_name'].astype(str) + '_' +
                coal_gis['Latitude'].round(6).astype(str) + '_' +
                coal_gis['Longitude'].round(6).astype(str)
            )

            df_coal = df[coal_mask].copy()
            df_coal['match_key'] = (
                df_coal['location_name'].astype(str) + '_' +
                df_coal['latitude'].round(6).astype(str) + '_' +
                df_coal['longitude'].round(6).astype(str)
            )

            # 创建匹配映射
            province_map = coal_gis.set_index('match_key')['Subnational_unit__province__sta'].to_dict()

            # 更新province
            df.loc[coal_mask, 'province'] = df_coal['match_key'].map(province_map).fillna('Unknown').values

            updated_count = (df.loc[coal_mask, 'province'] != 'Unknown').sum()
            logger.info(f"Updated {updated_count} coal power plant provinces")

    # 2. 修复天然气电厂的province（如果需要）
    gas_mask = df['facility_type'] == 'gas_power'
    if gas_mask.any():
        unknown_gas = (df.loc[gas_mask, 'province'] == 'Unknown').sum()
        if unknown_gas > 0:
            logger.info(f"Fixing province for {unknown_gas} gas power plants...")

            gas_file = gis_data_dir / 'gas_power_plants.csv'
            if gas_file.exists():
                gas_gis = pd.read_csv(gas_file, encoding='utf-8-sig')

                gas_gis['match_key'] = (
                    gas_gis['Name'].astype(str) + '_' +
                    gas_gis['Lat'].round(6).astype(str) + '_' +
                    gas_gis['Long'].round(6).astype(str)
                )

                df_gas = df[gas_mask].copy()
                df_gas['match_key'] = (
                    df_gas['location_name'].astype(str) + '_' +
                    df_gas['latitude'].round(6).astype(str) + '_' +
                    df_gas['longitude'].round(6).astype(str)
                )

                province_map = gas_gis.set_index('match_key')['Province'].to_dict()
                df.loc[gas_mask, 'province'] = df_gas['match_key'].map(province_map).fillna(df.loc[gas_mask, 'province']).values

                updated_count = (df.loc[gas_mask, 'province'] != 'Unknown').sum()
                logger.info(f"Updated {updated_count} gas power plant provinces")

    # 3. 修复石油炼厂的province（如果需要）
    oil_mask = df['facility_type'] == 'oil_refinery'
    if oil_mask.any():
        unknown_oil = (df.loc[oil_mask, 'province'] == 'Unknown').sum()
        if unknown_oil > 0:
            logger.info(f"Fixing province for {unknown_oil} oil refineries...")

            oil_file = gis_data_dir / 'oil_refineries.csv'
            if oil_file.exists():
                oil_gis = pd.read_csv(oil_file, encoding='utf-8-sig')

                oil_gis['match_key'] = (
                    oil_gis['Name'].astype(str) + '_' +
                    oil_gis['Lat'].round(6).astype(str) + '_' +
                    oil_gis['Long'].round(6).astype(str)
                )

                df_oil = df[oil_mask].copy()
                df_oil['match_key'] = (
                    df_oil['location_name'].astype(str) + '_' +
                    df_oil['latitude'].round(6).astype(str) + '_' +
                    df_oil['longitude'].round(6).astype(str)
                )

                province_map = oil_gis.set_index('match_key')['Province'].to_dict()
                df.loc[oil_mask, 'province'] = df_oil['match_key'].map(province_map).fillna(df.loc[oil_mask, 'province']).values

                updated_count = (df.loc[oil_mask, 'province'] != 'Unknown').sum()
                logger.info(f"Updated {updated_count} oil refinery provinces")

    # 统计修复结果
    unknown_count = (df['province'] == 'Unknown').sum()
    total_count = len(df)
    fixed_count = total_count - unknown_count

    logger.info(f"Province fix complete: {fixed_count}/{total_count} records have valid province data")
    logger.info(f"Remaining Unknown: {unknown_count}")

    return df


def create_interactive_map(df: pd.DataFrame, output_path: str):
    """创建交互式pydeck地图"""
    logger.info("Creating interactive map...")

    # 为每种设施类型准备数据
    layers = []

    for facility_type, color in FACILITY_COLORS.items():
        facility_df = df[df['facility_type'] == facility_type].copy()

        if facility_df.empty:
            continue

        # 归一化捕获量用于点的大小
        max_capture = facility_df['co2_capture_capacity_ton_per_week'].max()
        min_capture = facility_df['co2_capture_capacity_ton_per_week'].min()
        facility_df['radius'] = 1000 + (facility_df['co2_capture_capacity_ton_per_week'] - min_capture) / (max_capture - min_capture) * 9000

        # 添加RGB颜色列
        facility_df['color'] = [color] * len(facility_df)

        # 创建ScatterplotLayer
        layer = pdk.Layer(
            'ScatterplotLayer',
            data=facility_df,
            get_position='[longitude, latitude]',
            get_color='color',
            get_radius='radius',
            radius_scale=1,
            radius_min_pixels=3,
            radius_max_pixels=15,
            pickable=True,
            opacity=0.7,
            stroked=True,
            filled=True,
            line_width_min_pixels=1,
        )
        layers.append(layer)

    # 设置视图（中国中心）
    view_state = pdk.ViewState(
        latitude=35.0,
        longitude=105.0,
        zoom=4,
        pitch=0,
        bearing=0
    )

    # 创建tooltip
    tooltip = {
        "html": """
        <b>设施名称:</b> {location_name}<br/>
        <b>设施类型:</b> {facility_type}<br/>
        <b>省份:</b> {province}<br/>
        <b>CO₂捕获量:</b> {co2_capture_capacity_ton_per_week:.2f} 吨/周<br/>
        <b>捕获成本:</b> {capture_cost_yuan_per_ton:.2f} 元/吨<br/>
        <b>装机容量:</b> {capacity_original:.2f} {capacity_unit}
        """,
        "style": {
            "backgroundColor": "steelblue",
            "color": "white",
            "fontSize": "12px",
            "padding": "10px"
        }
    }

    # 创建地图
    r = pdk.Deck(
        layers=layers,
        initial_view_state=view_state,
        tooltip=tooltip,
        map_style='mapbox://styles/mapbox/light-v10'
    )

    # 保存HTML
    r.to_html(output_path)
    logger.info(f"Interactive map saved to: {output_path}")


def create_statistical_charts(df: pd.DataFrame, output_path: str):
    """创建统计图表"""
    logger.info("Creating statistical charts...")

    # 创建2x2子图布局
    fig = plt.figure(figsize=(16, 12))

    # 1. 按设施类型统计CO₂捕获量
    ax1 = plt.subplot(2, 2, 1)
    facility_stats = df.groupby('facility_type').agg({
        'co2_capture_capacity_ton_per_week': 'sum',
        'location_id': 'count'
    }).reset_index()
    facility_stats['facility_name'] = facility_stats['facility_type'].map(FACILITY_NAMES)

    colors_list = [FACILITY_COLORS[ft] for ft in facility_stats['facility_type']]
    colors_normalized = [[c[0]/255, c[1]/255, c[2]/255] for c in colors_list]

    bars = ax1.bar(facility_stats['facility_name'],
                   facility_stats['co2_capture_capacity_ton_per_week'] / 1e6,
                   color=colors_normalized, alpha=0.8, edgecolor='black')
    ax1.set_title('按设施类型统计的CO₂总捕获量', fontsize=14, fontweight='bold', pad=15)
    ax1.set_xlabel('设施类型', fontsize=12)
    ax1.set_ylabel('总捕获量 (百万吨/周)', fontsize=12)
    ax1.grid(axis='y', alpha=0.3, linestyle='--')

    # 在柱子上标注数值
    for bar, value, count in zip(bars, facility_stats['co2_capture_capacity_ton_per_week'],
                                   facility_stats['location_id']):
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height,
                f'{value/1e6:.1f}M吨\n({count}个)',
                ha='center', va='bottom', fontsize=10)

    # 2. 按设施类型统计设施数量
    ax2 = plt.subplot(2, 2, 2)
    wedges, texts, autotexts = ax2.pie(facility_stats['location_id'],
                                        labels=facility_stats['facility_name'],
                                        colors=colors_normalized,
                                        autopct='%1.1f%%',
                                        startangle=90,
                                        explode=[0.05, 0.05, 0.05])
    ax2.set_title('按设施类型统计的设施数量分布', fontsize=14, fontweight='bold', pad=15)

    # 美化百分比文字
    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_fontsize(11)
        autotext.set_fontweight('bold')

    # 3. 前15个省份CO₂捕获量排名
    ax3 = plt.subplot(2, 2, 3)
    province_stats = df.groupby('province').agg({
        'co2_capture_capacity_ton_per_week': 'sum',
        'location_id': 'count'
    }).reset_index()
    province_stats = province_stats.sort_values('co2_capture_capacity_ton_per_week', ascending=False).head(15)

    bars = ax3.barh(province_stats['province'],
                    province_stats['co2_capture_capacity_ton_per_week'] / 1e6,
                    color='steelblue', alpha=0.8, edgecolor='black')
    ax3.set_title('前15省份CO₂捕获量排名', fontsize=14, fontweight='bold', pad=15)
    ax3.set_xlabel('总捕获量 (百万吨/周)', fontsize=12)
    ax3.set_ylabel('省份', fontsize=12)
    ax3.invert_yaxis()
    ax3.grid(axis='x', alpha=0.3, linestyle='--')

    # 标注数值
    for i, (bar, value, count) in enumerate(zip(bars, province_stats['co2_capture_capacity_ton_per_week'],
                                                  province_stats['location_id'])):
        width = bar.get_width()
        ax3.text(width, bar.get_y() + bar.get_height()/2.,
                f' {value/1e6:.1f}M ({count}个)',
                ha='left', va='center', fontsize=9)

    # 4. 关键统计指标（文本展示）
    ax4 = plt.subplot(2, 2, 4)
    ax4.axis('off')  # 关闭坐标轴

    # 计算统计指标
    total_facilities = len(df)
    total_capture_weekly = df['co2_capture_capacity_ton_per_week'].sum()
    total_capture_annual = total_capture_weekly * 52 / 1e9  # 转换为十亿吨/年
    total_cost_weekly = df['total_capture_cost_yuan_per_week'].sum()
    total_cost_annual = total_cost_weekly * 52 / 1e9  # 转换为十亿元/年
    avg_unit_cost = df['capture_cost_yuan_per_ton'].mean()
    province_count = df['province'].nunique()

    # 按设施类型统计
    facility_stats = []
    for facility_type in ['coal_power', 'gas_power', 'oil_refinery']:
        fac_df = df[df['facility_type'] == facility_type]
        if not fac_df.empty:
            facility_stats.append({
                'name': FACILITY_NAMES[facility_type],
                'count': len(fac_df),
                'capture': fac_df['co2_capture_capacity_ton_per_week'].sum() / 1e6,
                'cost': fac_df['capture_cost_yuan_per_ton'].iloc[0]
            })

    # 创建文本内容
    text_content = f"""
    关键统计指标
    {'='*50}

    总体规模
      • 设施总数：{total_facilities:,} 个
      • 覆盖省份：{province_count} 个

    CO₂捕获能力
      • 每周捕获量：{total_capture_weekly/1e6:.2f} 百万吨
      • 年捕获能力：{total_capture_annual:.2f} 十亿吨

    经济指标
      • 周捕获成本：{total_cost_weekly/1e9:.2f} 十亿元
      • 年捕获成本：{total_cost_annual:.2f} 十亿元
      • 平均单位成本：{avg_unit_cost:.2f} 元/吨

    分设施类型单位成本
    """

    for stat in facility_stats:
        text_content += f"      • {stat['name']}：{stat['cost']:.0f} 元/吨 ({stat['count']:,}个)\n"

    # 显示文本
    ax4.text(0.05, 0.95, text_content,
             transform=ax4.transAxes,
             fontsize=11,
             verticalalignment='top',
             fontfamily='sans-serif',  # 使用sans-serif支持中文
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))

    # 添加整体标题
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    fig.suptitle(f'CO₂捕获源数据分析 | 总设施数: {len(df):,} | 生成时间: {timestamp}',
                 fontsize=16, fontweight='bold', y=0.995)

    plt.tight_layout(rect=[0, 0, 1, 0.99])
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    logger.info(f"Statistical charts saved to: {output_path}")
    plt.close()


def print_summary_statistics(df: pd.DataFrame):
    """打印汇总统计信息"""
    logger.info("\n" + "="*80)
    logger.info("CO₂捕获源数据汇总统计")
    logger.info("="*80)

    # 总体统计
    total_facilities = len(df)
    total_capture = df['co2_capture_capacity_ton_per_week'].sum()
    total_cost = df['total_capture_cost_yuan_per_week'].sum()
    avg_cost = df['capture_cost_yuan_per_ton'].mean()

    logger.info(f"\n总体统计:")
    logger.info(f"  总设施数: {total_facilities:,}")
    logger.info(f"  总CO₂捕获量: {total_capture:,.2f} 吨/周 ({total_capture/1e6:.2f} 百万吨/周)")
    logger.info(f"  总捕获成本: {total_cost:,.2f} 元/周 ({total_cost/1e9:.2f} 亿元/周)")
    logger.info(f"  平均单位成本: {avg_cost:.2f} 元/吨")

    # 按设施类型统计
    logger.info(f"\n按设施类型统计:")
    facility_stats = df.groupby('facility_type').agg({
        'location_id': 'count',
        'co2_capture_capacity_ton_per_week': ['sum', 'mean', 'min', 'max'],
        'capture_cost_yuan_per_ton': 'mean'
    })

    for facility_type in ['coal_power', 'gas_power', 'oil_refinery']:
        if facility_type in facility_stats.index:
            stats = facility_stats.loc[facility_type]
            logger.info(f"\n  {FACILITY_NAMES[facility_type]}:")
            logger.info(f"    设施数量: {int(stats[('location_id', 'count')]):,}")
            logger.info(f"    总捕获量: {stats[('co2_capture_capacity_ton_per_week', 'sum')]:,.2f} 吨/周")
            logger.info(f"    平均捕获量: {stats[('co2_capture_capacity_ton_per_week', 'mean')]:,.2f} 吨/周")
            logger.info(f"    捕获量范围: {stats[('co2_capture_capacity_ton_per_week', 'min')]:,.2f} - {stats[('co2_capture_capacity_ton_per_week', 'max')]:,.2f} 吨/周")
            logger.info(f"    平均单位成本: {stats[('capture_cost_yuan_per_ton', 'mean')]:.2f} 元/吨")

    # 地理分布统计
    logger.info(f"\n地理分布统计:")
    province_count = df['province'].nunique()
    logger.info(f"  覆盖省份数: {province_count}")

    top5_provinces = df.groupby('province')['co2_capture_capacity_ton_per_week'].sum().sort_values(ascending=False).head(5)
    logger.info(f"\n  前5省份CO₂捕获量:")
    for province, capture in top5_provinces.items():
        count = len(df[df['province'] == province])
        logger.info(f"    {province}: {capture:,.2f} 吨/周 ({count}个设施)")

    logger.info("\n" + "="*80 + "\n")


def main():
    """主函数"""
    logger.info("="*80)
    logger.info("开始CO₂捕获源数据可视化")
    logger.info("="*80)

    # 1. 加载数据
    project_root = Path(__file__).parent
    data_path = project_root / 'data' / 'co2_capture_sources.csv'
    df = load_data(str(data_path))

    # 2. 打印统计信息
    print_summary_statistics(df)

    # 3. 创建输出目录
    figures_dir = project_root / 'results' / 'figures'
    figures_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Output directory: {figures_dir}")

    # 4. 创建交互式地图
    map_output = figures_dir / 'co2_sources_map.html'
    create_interactive_map(df, str(map_output))

    # 5. 创建统计图表
    chart_output = figures_dir / 'co2_sources_analysis.png'
    create_statistical_charts(df, str(chart_output))

    logger.info("\n" + "="*80)
    logger.info("🎉 CO₂捕获源数据可视化完成！")
    logger.info("="*80)
    logger.info(f"\n输出文件:")
    logger.info(f"  1. 交互式地图: {map_output}")
    logger.info(f"  2. 统计图表: {chart_output}")
    logger.info("\n" + "="*80)


if __name__ == "__main__":
    main()
