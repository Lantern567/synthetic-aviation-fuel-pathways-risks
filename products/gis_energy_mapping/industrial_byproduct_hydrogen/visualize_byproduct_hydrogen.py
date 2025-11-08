#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工业副产氢源数据可视化

生成交互式地图和统计图表，展示副产氢源的地理分布和供应能力。

输出：
1. 交互式地图：results/figures/byproduct_hydrogen_sources_map.html
2. 统计图表：results/figures/byproduct_hydrogen_analysis.png

作者：Claude Code
创建日期：2025-10-27
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

# 氢源类型颜色映射
HYDROGEN_SOURCE_COLORS = {
    'steel': [255, 69, 0],        # 红橙色 - 钢铁焦化
    'refinery': [50, 205, 50]      # 青柠绿 - 石化催化重整
}

HYDROGEN_SOURCE_NAMES = {
    'steel': '钢铁焦化副产氢',
    'refinery': '石化催化重整副产氢'
}


def load_data(base_dir: Path):
    """加载副产氢数据"""
    logger.info("Loading byproduct hydrogen data...")

    data_dir = base_dir / 'data'

    # 找到最新的数据文件
    steel_files = list(data_dir.glob('steel_daily_byproduct_h2_*.csv'))
    refinery_files = list(data_dir.glob('refinery_daily_byproduct_h2_*.csv'))

    if not steel_files or not refinery_files:
        raise FileNotFoundError("Data files not found!")

    # 使用最新的文件
    steel_file = sorted(steel_files)[-1]
    refinery_file = sorted(refinery_files)[-1]

    logger.info(f"Loading steel data from: {steel_file.name}")
    df_steel = pd.read_csv(steel_file, encoding='utf-8-sig')
    df_steel['source_type'] = 'steel'
    df_steel['source_name'] = HYDROGEN_SOURCE_NAMES['steel']
    df_steel['h2_capacity'] = df_steel['h2_daily_tonnes']
    df_steel['facility_name'] = df_steel['plant_name']
    df_steel['num_units'] = df_steel['num_blast_furnaces']

    logger.info(f"Loading refinery data from: {refinery_file.name}")
    df_refinery = pd.read_csv(refinery_file, encoding='utf-8-sig')
    df_refinery['source_type'] = 'refinery'
    df_refinery['source_name'] = HYDROGEN_SOURCE_NAMES['refinery']
    df_refinery['h2_capacity'] = df_refinery['h2_daily_tonnes']
    df_refinery['facility_name'] = df_refinery['refinery_name']
    df_refinery['num_units'] = 1  # 每个炼油厂计为1个单元

    # 合并数据
    df_combined = pd.concat([
        df_steel[['source_type', 'source_name', 'facility_name', 'province',
                  'latitude', 'longitude', 'h2_capacity', 'num_units']],
        df_refinery[['source_type', 'source_name', 'facility_name', 'province',
                     'latitude', 'longitude', 'h2_capacity', 'num_units']]
    ], ignore_index=True)

    logger.info(f"Total hydrogen sources: {len(df_combined)}")
    logger.info(f"  - Steel plants: {len(df_steel)}")
    logger.info(f"  - Refineries: {len(df_refinery)}")

    return df_combined


def create_interactive_map(df: pd.DataFrame, output_path: str):
    """创建交互式地图"""
    logger.info("Creating interactive map...")

    # 为每个数据源类型添加颜色和半径
    df['color'] = df['source_type'].map(HYDROGEN_SOURCE_COLORS)

    # 根据氢气产能计算半径（对数缩放）
    df['radius'] = np.log10(df['h2_capacity'] + 1) * 5000

    # 为不同类型创建不同的图层
    layers = []

    for source_type, color in HYDROGEN_SOURCE_COLORS.items():
        source_df = df[df['source_type'] == source_type].copy()

        if len(source_df) == 0:
            continue

        # 创建ScatterplotLayer
        layer = pdk.Layer(
            'ScatterplotLayer',
            data=source_df,
            get_position='[longitude, latitude]',
            get_color='color',
            get_radius='radius',
            radius_scale=1,
            radius_min_pixels=3,
            radius_max_pixels=20,
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
        <b>氢源类型:</b> {source_name}<br/>
        <b>设施名称:</b> {facility_name}<br/>
        <b>省份:</b> {province}<br/>
        <b>日产氢量:</b> {h2_capacity:.1f} 吨/日<br/>
        <b>年产氢量:</b> {h2_annual:.0f} 吨/年<br/>
        <b>设备数量:</b> {num_units} 个<br/>
        <b>坐标:</b> ({latitude:.4f}, {longitude:.4f})
        """,
        "style": {
            "backgroundColor": "steelblue",
            "color": "white",
            "fontSize": "12px",
            "padding": "10px"
        }
    }

    # 添加年产氢量字段用于tooltip
    df['h2_annual'] = df['h2_capacity'] * 365

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

    # 1. 按氢源类型统计日产氢量
    ax1 = plt.subplot(2, 2, 1)
    source_stats = df.groupby('source_type').agg({
        'h2_capacity': 'sum',
        'facility_name': 'count'
    }).reset_index()
    source_stats['source_name'] = source_stats['source_type'].map(HYDROGEN_SOURCE_NAMES)

    colors_list = [HYDROGEN_SOURCE_COLORS[st] for st in source_stats['source_type']]
    colors_normalized = [[c[0]/255, c[1]/255, c[2]/255] for c in colors_list]

    bars = ax1.bar(source_stats['source_name'],
                   source_stats['h2_capacity'] / 1000,  # 转换为千吨
                   color=colors_normalized, alpha=0.8, edgecolor='black')
    ax1.set_title('按氢源类型统计的日产氢量', fontsize=14, fontweight='bold', pad=15)
    ax1.set_xlabel('氢源类型', fontsize=12)
    ax1.set_ylabel('日产氢量 (千吨/日)', fontsize=12)
    ax1.grid(axis='y', alpha=0.3, linestyle='--')

    # 在柱子上标注数值
    for bar, value, count in zip(bars, source_stats['h2_capacity'],
                                  source_stats['facility_name']):
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height,
                f'{value/1000:.1f}千吨\n({count}个设施)',
                ha='center', va='bottom', fontsize=10)

    # 2. 按氢源类型统计设施数量（饼图）
    ax2 = plt.subplot(2, 2, 2)
    wedges, texts, autotexts = ax2.pie(source_stats['facility_name'],
                                        labels=source_stats['source_name'],
                                        colors=colors_normalized,
                                        autopct='%1.1f%%',
                                        startangle=90,
                                        explode=[0.05, 0.05])
    ax2.set_title('氢源设施数量占比', fontsize=14, fontweight='bold', pad=15)

    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_fontsize(11)
        autotext.set_weight('bold')

    # 3. Top 10省份日产氢量
    ax3 = plt.subplot(2, 2, 3)
    province_stats = df.groupby('province')['h2_capacity'].sum().sort_values(ascending=False).head(10)

    bars = ax3.barh(range(len(province_stats)), province_stats.values / 1000,
                    color='steelblue', alpha=0.8, edgecolor='black')
    ax3.set_yticks(range(len(province_stats)))
    ax3.set_yticklabels(province_stats.index)
    ax3.set_title('Top 10 省份日产氢量', fontsize=14, fontweight='bold', pad=15)
    ax3.set_xlabel('日产氢量 (千吨/日)', fontsize=12)
    ax3.grid(axis='x', alpha=0.3, linestyle='--')
    ax3.invert_yaxis()

    # 在柱子上标注数值
    for i, (bar, value) in enumerate(zip(bars, province_stats.values)):
        width = bar.get_width()
        ax3.text(width, bar.get_y() + bar.get_height()/2.,
                f'{value/1000:.1f}',
                ha='left', va='center', fontsize=9,
                bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.7))

    # 4. 单个设施产氢量分布（箱线图）
    ax4 = plt.subplot(2, 2, 4)

    # 准备箱线图数据
    steel_data = df[df['source_type'] == 'steel']['h2_capacity'].values
    refinery_data = df[df['source_type'] == 'refinery']['h2_capacity'].values

    bp = ax4.boxplot([steel_data, refinery_data],
                     labels=[HYDROGEN_SOURCE_NAMES['steel'],
                            HYDROGEN_SOURCE_NAMES['refinery']],
                     patch_artist=True,
                     showmeans=True,
                     meanline=True)

    # 设置箱子颜色
    for patch, color in zip(bp['boxes'], colors_normalized):
        patch.set_facecolor(color)
        patch.set_alpha(0.6)

    ax4.set_title('单设施日产氢量分布', fontsize=14, fontweight='bold', pad=15)
    ax4.set_ylabel('日产氢量 (吨/日)', fontsize=12)
    ax4.grid(axis='y', alpha=0.3, linestyle='--')
    ax4.set_yscale('log')  # 对数尺度，因为钢铁厂和炼油厂差异很大

    # 添加统计信息
    stats_text = f"钢铁厂:\n平均: {steel_data.mean():.1f} t/d\n中位数: {np.median(steel_data):.1f} t/d\n\n"
    stats_text += f"炼油厂:\n平均: {refinery_data.mean():.1f} t/d\n中位数: {np.median(refinery_data):.1f} t/d"
    ax4.text(0.98, 0.98, stats_text,
            transform=ax4.transAxes,
            fontsize=9,
            verticalalignment='top',
            horizontalalignment='right',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    logger.info(f"Statistical charts saved to: {output_path}")
    plt.close()


def create_summary_report(df: pd.DataFrame, output_path: str):
    """生成文本摘要报告"""
    logger.info("Creating summary report...")

    report = []
    report.append("="*80)
    report.append("工业副产氢源分布摘要报告")
    report.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("="*80)

    # 总体统计
    report.append("\n一、总体统计")
    report.append(f"  设施总数: {len(df)}")
    report.append(f"  总日产氢量: {df['h2_capacity'].sum():,.1f} 吨/日")
    report.append(f"  总年产氢量: {df['h2_capacity'].sum() * 365:,.0f} 吨/年")

    # 按类型统计
    report.append("\n二、按氢源类型统计")
    for source_type, source_name in HYDROGEN_SOURCE_NAMES.items():
        source_df = df[df['source_type'] == source_type]
        if len(source_df) > 0:
            report.append(f"\n  {source_name}:")
            report.append(f"    设施数量: {len(source_df)}")
            report.append(f"    日产氢量: {source_df['h2_capacity'].sum():,.1f} 吨/日")
            report.append(f"    占比: {source_df['h2_capacity'].sum() / df['h2_capacity'].sum() * 100:.1f}%")
            report.append(f"    平均单设施产氢: {source_df['h2_capacity'].mean():,.1f} 吨/日")
            report.append(f"    最大单设施产氢: {source_df['h2_capacity'].max():,.1f} 吨/日")

    # Top 10 省份
    report.append("\n三、Top 10 省份日产氢量")
    province_stats = df.groupby('province')['h2_capacity'].sum().sort_values(ascending=False).head(10)
    for i, (province, capacity) in enumerate(province_stats.items(), 1):
        report.append(f"  {i:2d}. {province:15s}: {capacity:8,.1f} 吨/日")

    # Top 10 设施
    report.append("\n四、Top 10 单设施日产氢量")
    top_facilities = df.nlargest(10, 'h2_capacity')
    for i, row in enumerate(top_facilities.itertuples(), 1):
        report.append(f"  {i:2d}. {row.facility_name[:40]:40s} | {row.province:10s} | {row.h2_capacity:6,.1f} t/d")

    report.append("\n" + "="*80)
    report.append("报告结束")
    report.append("="*80)

    # 保存报告
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report))

    logger.info(f"Summary report saved to: {output_path}")

    # 同时打印到控制台
    print('\n'.join(report))


def main():
    """主函数"""
    # 设置路径
    base_dir = Path(__file__).parent
    results_dir = base_dir / 'results'
    figures_dir = results_dir / 'figures'
    reports_dir = results_dir / 'reports'

    # 创建输出目录
    figures_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 1. 加载数据
        df = load_data(base_dir)

        # 2. 创建交互式地图
        map_output = figures_dir / 'byproduct_hydrogen_sources_map.html'
        create_interactive_map(df, str(map_output))

        # 3. 创建统计图表
        chart_output = figures_dir / 'byproduct_hydrogen_analysis.png'
        create_statistical_charts(df, str(chart_output))

        # 4. 生成摘要报告
        report_output = reports_dir / 'byproduct_hydrogen_summary.txt'
        create_summary_report(df, str(report_output))

        logger.info("\nVisualization complete!")
        logger.info(f"  - Interactive map: {map_output}")
        logger.info(f"  - Statistical charts: {chart_output}")
        logger.info(f"  - Summary report: {report_output}")

    except Exception as e:
        logger.error(f"Error during visualization: {e}", exc_info=True)
        raise


if __name__ == '__main__':
    main()
