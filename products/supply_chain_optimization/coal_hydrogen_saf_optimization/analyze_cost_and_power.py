"""
分析成本构成和电力使用情况
"""
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import logging
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['figure.dpi'] = 150

def load_solution_data(json_path):
    """加载优化解决方案数据"""
    logger.info(f"正在加载解决方案数据: {json_path}")
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data

def analyze_cost_composition(data):
    """分析成本构成（不包括缺货成本）"""
    logger.info("分析成本构成...")

    # 使用 cost_breakdown 字段替代 cost_summary
    cost_breakdown = data.get('cost_breakdown', {})

    logger.info(f"从JSON读取的cost_breakdown字段: {list(cost_breakdown.keys())}")

    # 根据实际JSON结构提取成本项（排除缺货成本和甲醇成本）
    # 注意：一步法模式下，甲醇不作为独立成本项
    cost_items = {
        '煤炭购买成本': cost_breakdown.get('coal_purchase_cost', 0),
        '煤气化成本': cost_breakdown.get('coal_gasification_cost', 0),
        '设施投资成本': cost_breakdown.get('facility_investment_cost', 0),
        '设施运营成本': cost_breakdown.get('facility_operation_cost', 0),
        '生产成本': cost_breakdown.get('production_cost', 0),
        '电解槽投资成本': cost_breakdown.get('electrolyzer_investment_cost', 0),
        '电力成本': cost_breakdown.get('electricity_cost', 0),
        '氢气储存投资': cost_breakdown.get('h2_storage_investment', 0),
        '氢气储存运营': cost_breakdown.get('h2_storage_operation', 0),
        '氢气管道运营': cost_breakdown.get('hydrogen_pipeline_operation', 0),
        '运输运营成本': cost_breakdown.get('transport_operation_cost', 0),
        # 一步法模式：不包含甲醇成本项和运输设备成本
        # '运输设备成本': cost_breakdown.get('transport_equipment_cost', 0),
        # '甲醇生产成本': cost_breakdown.get('methanol_production_cost', 0),
        # '甲醇储存投资': cost_breakdown.get('methanol_storage_investment', 0),
        # '甲醇储存运营': cost_breakdown.get('methanol_storage_operation', 0),
    }

    logger.info(f"提取的成本项: {cost_items}")

    # 计算总成本（不包括缺货成本）
    total_cost = sum(cost_items.values())
    logger.info(f"计算的总成本: {total_cost:,.2f} 元")

    # 防止除零错误
    if total_cost == 0:
        logger.error("总成本为0，无法计算百分比！")
        logger.error(f"JSON中的所有成本项: {cost_breakdown}")
        raise ValueError("总成本为0，请检查JSON数据是否正确")

    # 计算百分比
    cost_percentages = {k: (v/total_cost*100) for k, v in cost_items.items()}

    # 排序
    sorted_items = sorted(cost_items.items(), key=lambda x: x[1], reverse=True)

    logger.info(f"总成本（不含缺货成本）: {total_cost:,.2f} 元")
    logger.info("\n成本构成:")
    for name, cost in sorted_items:
        percentage = cost_percentages[name]
        logger.info(f"  {name}: {cost:,.2f} 元 ({percentage:.2f}%)")

    return cost_items, cost_percentages, total_cost

def analyze_power_usage(data):
    """分析电力使用情况"""
    logger.info("分析电力使用情况...")

    # 从 hydrogen_production 中提取电力数据
    h2_production = data.get('hydrogen_production', {})

    power_data = []

    for entry in h2_production:
        wind_id = entry.get('wind_site_id')
        week = entry.get('week')

        # 理论风电发电量
        theoretical_power = entry.get('theoretical_wind_power_mwh', 0)

        # 实际使用电力 = 产氢量 * 电耗
        h2_produced = entry.get('hydrogen_produced_kg', 0)
        power_consumption_kwh_per_kg = entry.get('power_consumption_kwh_per_kg', 50)
        actual_power_used = h2_produced * power_consumption_kwh_per_kg / 1000  # 转换为MWh

        # 电解槽容量
        electrolyzer_capacity = entry.get('electrolyzer_capacity_mw', 0)

        power_data.append({
            'wind_site_id': wind_id,
            'week': week,
            'theoretical_power_mwh': theoretical_power,
            'actual_power_used_mwh': actual_power_used,
            'electrolyzer_capacity_mw': electrolyzer_capacity,
            'utilization_rate': (actual_power_used / theoretical_power * 100) if theoretical_power > 0 else 0
        })

    power_df = pd.DataFrame(power_data)

    if len(power_df) > 0:
        logger.info(f"\n电力使用统计:")
        logger.info(f"  总理论电力: {power_df['theoretical_power_mwh'].sum():,.2f} MWh")
        logger.info(f"  总实际使用电力: {power_df['actual_power_used_mwh'].sum():,.2f} MWh")
        logger.info(f"  平均利用率: {power_df['utilization_rate'].mean():.2f}%")
        logger.info(f"  平均电解槽容量: {power_df['electrolyzer_capacity_mw'].mean():.2f} MW")

    return power_df

def plot_cost_composition(cost_items, cost_percentages, output_dir):
    """绘制成本构成图"""
    logger.info("绘制成本构成图...")

    # 准备数据
    sorted_items = sorted(cost_items.items(), key=lambda x: x[1], reverse=True)
    names = [item[0] for item in sorted_items]
    values = [item[1] for item in sorted_items]
    percentages = [cost_percentages[item[0]] for item in sorted_items]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

    # 饼图
    colors = plt.cm.Set3(range(len(names)))
    wedges, texts, autotexts = ax1.pie(
        values,
        labels=names,
        autopct='%1.1f%%',
        startangle=90,
        colors=colors,
        textprops={'fontsize': 10}
    )
    ax1.set_title('成本构成（不含缺货成本）', fontsize=14, fontweight='bold', pad=20)

    # 柱状图
    bars = ax2.barh(names, values, color=colors)
    ax2.set_xlabel('成本（元）', fontsize=12)
    ax2.set_title('各项成本明细', fontsize=14, fontweight='bold', pad=20)
    ax2.grid(axis='x', alpha=0.3, linestyle='--')

    # 在柱状图上添加数值标签
    for i, (bar, value, pct) in enumerate(zip(bars, values, percentages)):
        ax2.text(
            value,
            i,
            f' {value:,.0f} ({pct:.1f}%)',
            va='center',
            fontsize=9
        )

    # 调整布局
    plt.tight_layout()

    # 保存图片
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = output_dir / f'cost_composition_{timestamp}.png'
    plt.savefig(output_path, bbox_inches='tight')
    logger.info(f"成本构成图已保存: {output_path}")
    plt.close()

    return output_path

def plot_power_analysis(power_df, output_dir):
    """绘制电力分析图"""
    logger.info("绘制电力分析图...")

    if len(power_df) == 0:
        logger.warning("没有电力数据可供可视化")
        return None

    # 按风场聚合数据
    power_by_site = power_df.groupby('wind_site_id').agg({
        'theoretical_power_mwh': 'sum',
        'actual_power_used_mwh': 'sum',
        'electrolyzer_capacity_mw': 'mean'
    }).reset_index()

    # 计算利用率
    power_by_site['utilization_rate'] = (
        power_by_site['actual_power_used_mwh'] /
        power_by_site['theoretical_power_mwh'] * 100
    )

    # 排序
    power_by_site = power_by_site.sort_values('theoretical_power_mwh', ascending=False)

    # 创建三个子图
    fig, axes = plt.subplots(3, 1, figsize=(14, 12))

    # 1. 理论电力 vs 实际使用电力
    x = range(len(power_by_site))
    width = 0.35

    ax1 = axes[0]
    bars1 = ax1.bar(
        [i - width/2 for i in x],
        power_by_site['theoretical_power_mwh'],
        width,
        label='理论风电发电量',
        color='skyblue',
        alpha=0.8
    )
    bars2 = ax1.bar(
        [i + width/2 for i in x],
        power_by_site['actual_power_used_mwh'],
        width,
        label='实际使用电力',
        color='orange',
        alpha=0.8
    )

    ax1.set_xlabel('风场ID', fontsize=11)
    ax1.set_ylabel('电力 (MWh)', fontsize=11)
    ax1.set_title('理论风电发电量 vs 实际使用电力', fontsize=13, fontweight='bold', pad=15)
    ax1.set_xticks(x)
    ax1.set_xticklabels(power_by_site['wind_site_id'], rotation=45, ha='right')
    ax1.legend()
    ax1.grid(axis='y', alpha=0.3, linestyle='--')

    # 添加数值标签
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                ax1.text(
                    bar.get_x() + bar.get_width()/2.,
                    height,
                    f'{height:,.0f}',
                    ha='center',
                    va='bottom',
                    fontsize=8
                )

    # 2. 电解槽容量
    ax2 = axes[1]
    bars3 = ax2.bar(
        x,
        power_by_site['electrolyzer_capacity_mw'],
        color='green',
        alpha=0.7
    )

    ax2.set_xlabel('风场ID', fontsize=11)
    ax2.set_ylabel('电解槽容量 (MW)', fontsize=11)
    ax2.set_title('各风场电解槽容量', fontsize=13, fontweight='bold', pad=15)
    ax2.set_xticks(x)
    ax2.set_xticklabels(power_by_site['wind_site_id'], rotation=45, ha='right')
    ax2.grid(axis='y', alpha=0.3, linestyle='--')

    # 添加数值标签
    for bar in bars3:
        height = bar.get_height()
        if height > 0:
            ax2.text(
                bar.get_x() + bar.get_width()/2.,
                height,
                f'{height:.1f}',
                ha='center',
                va='bottom',
                fontsize=8
            )

    # 3. 利用率
    ax3 = axes[2]
    bars4 = ax3.bar(
        x,
        power_by_site['utilization_rate'],
        color='purple',
        alpha=0.7
    )

    ax3.set_xlabel('风场ID', fontsize=11)
    ax3.set_ylabel('利用率 (%)', fontsize=11)
    ax3.set_title('风电利用率', fontsize=13, fontweight='bold', pad=15)
    ax3.set_xticks(x)
    ax3.set_xticklabels(power_by_site['wind_site_id'], rotation=45, ha='right')
    ax3.grid(axis='y', alpha=0.3, linestyle='--')
    ax3.axhline(y=100, color='r', linestyle='--', alpha=0.5, label='100%')
    ax3.legend()

    # 添加数值标签
    for bar in bars4:
        height = bar.get_height()
        if height > 0:
            ax3.text(
                bar.get_x() + bar.get_width()/2.,
                height,
                f'{height:.1f}%',
                ha='center',
                va='bottom',
                fontsize=8
            )

    # 调整布局
    plt.tight_layout()

    # 保存图片
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = output_dir / f'power_analysis_{timestamp}.png'
    plt.savefig(output_path, bbox_inches='tight')
    logger.info(f"电力分析图已保存: {output_path}")
    plt.close()

    return output_path

def save_analysis_report(cost_items, cost_percentages, total_cost, power_df, output_dir):
    """保存分析报告"""
    logger.info("保存分析报告...")

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_path = output_dir / f'cost_power_analysis_report_{timestamp}.txt'

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("成本构成与电力使用分析报告（不含缺货成本）\n")
        f.write("=" * 80 + "\n\n")

        # 成本构成
        f.write("一、成本构成分析\n")
        f.write("-" * 80 + "\n")
        f.write(f"总成本: {total_cost:,.2f} 元\n\n")

        sorted_items = sorted(cost_items.items(), key=lambda x: x[1], reverse=True)
        for name, cost in sorted_items:
            percentage = cost_percentages[name]
            f.write(f"  {name:20s}: {cost:15,.2f} 元 ({percentage:6.2f}%)\n")

        # 电力使用
        f.write("\n\n二、电力使用分析\n")
        f.write("-" * 80 + "\n")

        if len(power_df) > 0:
            f.write(f"总理论电力: {power_df['theoretical_power_mwh'].sum():,.2f} MWh\n")
            f.write(f"总实际使用电力: {power_df['actual_power_used_mwh'].sum():,.2f} MWh\n")
            f.write(f"平均利用率: {power_df['utilization_rate'].mean():.2f}%\n")
            f.write(f"平均电解槽容量: {power_df['electrolyzer_capacity_mw'].mean():.2f} MW\n")

            # 按风场统计
            power_by_site = power_df.groupby('wind_site_id').agg({
                'theoretical_power_mwh': 'sum',
                'actual_power_used_mwh': 'sum',
                'electrolyzer_capacity_mw': 'mean'
            }).reset_index()
            power_by_site['utilization_rate'] = (
                power_by_site['actual_power_used_mwh'] /
                power_by_site['theoretical_power_mwh'] * 100
            )

            f.write("\n各风场详细数据:\n")
            for _, row in power_by_site.iterrows():
                f.write(f"\n  风场 {row['wind_site_id']}:\n")
                f.write(f"    理论电力: {row['theoretical_power_mwh']:,.2f} MWh\n")
                f.write(f"    实际使用: {row['actual_power_used_mwh']:,.2f} MWh\n")
                f.write(f"    电解槽容量: {row['electrolyzer_capacity_mw']:.2f} MW\n")
                f.write(f"    利用率: {row['utilization_rate']:.2f}%\n")
        else:
            f.write("无电力数据\n")

    logger.info(f"分析报告已保存: {report_path}")
    return report_path

def main():
    """主函数"""
    logger.info("开始分析成本构成和电力使用情况")

    # 设置路径 - 修改为煤制氢项目路径
    base_dir = Path(__file__).parent
    results_dir = base_dir / 'results'  # 使用当前项目的results目录

    # 找到最新的 JSON 文件
    json_files = sorted(results_dir.glob('complete_solution_*.json'))
    if not json_files:
        logger.error("未找到优化解决方案文件")
        logger.error(f"查找路径: {results_dir}")
        return

    latest_json = json_files[-1]
    logger.info(f"使用文件: {latest_json}")

    # 创建输出目录
    output_dir = results_dir / 'figures'
    output_dir.mkdir(exist_ok=True)

    # 加载数据
    data = load_solution_data(latest_json)

    # 分析成本构成
    cost_items, cost_percentages, total_cost = analyze_cost_composition(data)

    # 分析电力使用
    power_df = analyze_power_usage(data)

    # 绘制图表
    plot_cost_composition(cost_items, cost_percentages, output_dir)
    plot_power_analysis(power_df, output_dir)

    # 保存报告
    save_analysis_report(cost_items, cost_percentages, total_cost, power_df, output_dir)

    logger.info("分析完成!")

if __name__ == '__main__':
    main()
