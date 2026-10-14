"""
分析成本构成和电力使用情况（简化版，不依赖numpy等库）
"""
import json
from pathlib import Path
import logging
from datetime import datetime
from collections import defaultdict

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_solution_data(json_path):
    """加载优化解决方案数据"""
    logger.info(f"正在加载解决方案数据: {json_path}")
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data

def analyze_cost_composition(data):
    """分析成本构成（不包括缺货成本）"""
    logger.info("分析成本构成...")

    # 从顶层数据结构中提取成本项
    cost_items = {
        'SAF设施投资成本': data.get('facility_investment_cost', 0),
        'SAF设施运营成本': data.get('facility_operation_cost', 0),
        '生产成本': data.get('production_cost', 0),
        '运输设备成本': data.get('transport_equipment_cost', 0),
        '运输运营成本': data.get('transport_operation_cost', 0),
        '储存设备成本': data.get('storage_equipment_cost', 0),
        '储存运营成本': data.get('storage_operation_cost', 0),
        '电解槽投资成本': data.get('electrolyzer_investment_cost', 0),
        '氢气生产成本': data.get('hydrogen_production_cost', 0),
        '电力成本': data.get('electricity_cost', 0),
        '氢气储存投资': data.get('h2_storage_investment', 0),
        '氢气储存运营': data.get('h2_storage_operation', 0),
        '氢气运输投资': data.get('hydrogen_transport_investment', 0),
        '氢气运输运营': data.get('hydrogen_transport_operation', 0),
        '氢气管道运营': data.get('hydrogen_pipeline_operation', 0),
    }

    # 计算总成本（不包括缺货成本）
    total_cost = sum(cost_items.values())

    # 计算百分比
    cost_percentages = {k: (v/total_cost*100) if total_cost > 0 else 0 for k, v in cost_items.items()}

    # 排序
    sorted_items = sorted(cost_items.items(), key=lambda x: x[1], reverse=True)

    logger.info(f"\n{'='*80}")
    logger.info(f"总成本（不含缺货成本）: {total_cost:,.2f} 元")
    logger.info(f"\n成本构成:")
    for name, cost in sorted_items:
        percentage = cost_percentages[name]
        logger.info(f"  {name:20s}: {cost:15,.2f} 元 ({percentage:6.2f}%)")

    return cost_items, cost_percentages, total_cost

def analyze_power_usage(data):
    """分析电力使用情况"""
    logger.info(f"\n{'='*80}")
    logger.info("分析电力使用情况...")

    # 从 hydrogen_facilities 中提取电力数据
    h2_facilities = data.get('hydrogen_facilities', {})

    power_data = []
    power_by_site = {}

    # 标准电解槽电耗：50 kWh/kg H2
    power_consumption_kwh_per_kg = 50

    for site_name, facility_info in h2_facilities.items():
        if not facility_info.get('built', False):
            continue

        # 实际产氢量 (kg/year)
        h2_production_kg = facility_info.get('actual_annual_h2_production_kg', 0)

        # 最大产氢容量 (kg/year)
        max_h2_capacity_kg = facility_info.get('max_annual_h2_capacity_kg', 0)

        # 电解槽容量 (kg H2/hour)
        capacity_kg_per_hour = facility_info.get('capacity_kg_h2_per_hour', 0)

        # 利用率
        utilization_rate = facility_info.get('utilization_rate', 0) * 100  # 转换为百分比

        # 计算电力使用
        # 实际使用电力 = 实际产氢量 * 电耗
        actual_power_used_mwh = h2_production_kg * power_consumption_kwh_per_kg / 1000

        # 理论最大电力 = 最大产氢容量 * 电耗
        theoretical_power_mwh = max_h2_capacity_kg * power_consumption_kwh_per_kg / 1000

        # 电解槽功率容量 (MW) = 容量(kg/h) * 电耗(kWh/kg) / 1000
        electrolyzer_capacity_mw = capacity_kg_per_hour * power_consumption_kwh_per_kg / 1000

        location_type = facility_info.get('location_type', 'unknown')

        power_data.append({
            'site_name': site_name,
            'location_type': location_type,
            'theoretical_power_mwh': theoretical_power_mwh,
            'actual_power_used_mwh': actual_power_used_mwh,
            'electrolyzer_capacity_mw': electrolyzer_capacity_mw,
            'h2_production_kg': h2_production_kg,
            'utilization_rate': utilization_rate
        })

        power_by_site[site_name] = {
            'location_type': location_type,
            'theoretical_power': theoretical_power_mwh,
            'actual_power': actual_power_used_mwh,
            'electrolyzer_capacity': electrolyzer_capacity_mw,
            'h2_production': h2_production_kg,
            'utilization_rate': utilization_rate
        }

    if power_data:
        # 计算总体统计
        total_theoretical = sum(d['theoretical_power_mwh'] for d in power_data)
        total_actual = sum(d['actual_power_used_mwh'] for d in power_data)
        avg_utilization = sum(d['utilization_rate'] for d in power_data) / len(power_data)
        avg_capacity = sum(d['electrolyzer_capacity_mw'] for d in power_data) / len(power_data)

        logger.info(f"\n电力使用总体统计:")
        logger.info(f"  总理论电力: {total_theoretical:,.2f} MWh")
        logger.info(f"  总实际使用电力: {total_actual:,.2f} MWh")
        logger.info(f"  平均利用率: {avg_utilization:.2f}%")
        logger.info(f"  平均电解槽容量: {avg_capacity:.2f} MW")

        # 按风场统计
        logger.info(f"\n各站点详细统计 (前20个):")
        sorted_sites = sorted(
            power_by_site.items(),
            key=lambda x: x[1]['actual_power'],
            reverse=True
        )

        for i, (site_name, stats) in enumerate(sorted_sites[:20], 1):
            logger.info(f"\n  {i}. {site_name} ({stats['location_type']}):")
            logger.info(f"    理论电力: {stats['theoretical_power']:,.2f} MWh")
            logger.info(f"    实际使用: {stats['actual_power']:,.2f} MWh")
            logger.info(f"    电解槽容量: {stats['electrolyzer_capacity']:.2f} MW")
            logger.info(f"    产氢量: {stats['h2_production']:,.2f} kg")
            logger.info(f"    利用率: {stats['utilization_rate']:.2f}%")

    else:
        logger.warning("没有电力数据")

    return power_data, power_by_site

def save_analysis_report(cost_items, cost_percentages, total_cost, power_data, power_by_site, output_dir):
    """保存分析报告"""
    logger.info(f"\n{'='*80}")
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

        if power_data:
            total_theoretical = sum(d['theoretical_power_mwh'] for d in power_data)
            total_actual = sum(d['actual_power_used_mwh'] for d in power_data)
            avg_utilization = sum(d['utilization_rate'] for d in power_data) / len(power_data)
            avg_capacity = sum(d['electrolyzer_capacity_mw'] for d in power_data) / len(power_data)

            f.write(f"总理论电力: {total_theoretical:,.2f} MWh\n")
            f.write(f"总实际使用电力: {total_actual:,.2f} MWh\n")
            f.write(f"平均利用率: {avg_utilization:.2f}%\n")
            f.write(f"平均电解槽容量: {avg_capacity:.2f} MW\n")

            # 按站点统计
            f.write("\n各站点详细数据 (按实际电力使用排序):\n")
            sorted_sites = sorted(
                power_by_site.items(),
                key=lambda x: x[1]['actual_power'],
                reverse=True
            )

            for i, (site_name, stats) in enumerate(sorted_sites, 1):
                f.write(f"\n  {i}. {site_name} ({stats['location_type']}):\n")
                f.write(f"    理论电力: {stats['theoretical_power']:,.2f} MWh\n")
                f.write(f"    实际使用: {stats['actual_power']:,.2f} MWh\n")
                f.write(f"    电解槽容量: {stats['electrolyzer_capacity']:.2f} MW\n")
                f.write(f"    产氢量: {stats['h2_production']:,.2f} kg\n")
                f.write(f"    利用率: {stats['utilization_rate']:.2f}%\n")
        else:
            f.write("无电力数据\n")

    logger.info(f"分析报告已保存: {report_path}")
    return report_path

def save_csv_reports(cost_items, cost_percentages, power_data, power_by_site, output_dir):
    """保存CSV格式的报告"""
    logger.info("保存CSV格式报告...")

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # 保存成本分析CSV
    cost_csv_path = output_dir / f'cost_analysis_{timestamp}.csv'
    with open(cost_csv_path, 'w', encoding='utf-8-sig') as f:
        f.write("成本项,金额(元),占比(%)\n")
        sorted_items = sorted(cost_items.items(), key=lambda x: x[1], reverse=True)
        for name, cost in sorted_items:
            percentage = cost_percentages[name]
            f.write(f"{name},{cost:.2f},{percentage:.2f}\n")

    logger.info(f"成本分析CSV已保存: {cost_csv_path}")

    # 保存电力分析CSV
    if power_by_site:
        power_csv_path = output_dir / f'power_analysis_{timestamp}.csv'
        with open(power_csv_path, 'w', encoding='utf-8-sig') as f:
            f.write("站点名称,位置类型,理论电力(MWh),实际使用电力(MWh),电解槽容量(MW),产氢量(kg),利用率(%)\n")
            sorted_sites = sorted(
                power_by_site.items(),
                key=lambda x: x[1]['actual_power'],
                reverse=True
            )
            for site_name, stats in sorted_sites:
                f.write(f"{site_name},{stats['location_type']},{stats['theoretical_power']:.2f},{stats['actual_power']:.2f},{stats['electrolyzer_capacity']:.2f},{stats['h2_production']:.2f},{stats['utilization_rate']:.2f}\n")

        logger.info(f"电力分析CSV已保存: {power_csv_path}")

def main():
    """主函数"""
    logger.info("开始分析成本构成和电力使用情况")

    # 设置路径
    base_dir = Path(__file__).parent

    # 从当前项目（coal_hydrogen_saf_optimization）读取数据
    source_results_dir = base_dir / 'results'

    # 保存到同一个目录
    output_dir = base_dir / 'results'
    output_dir.mkdir(exist_ok=True)

    # 找到最新的 JSON 文件
    json_files = sorted(source_results_dir.glob('complete_solution_*.json'))
    if not json_files:
        logger.error("未找到优化解决方案文件")
        logger.error(f"查找路径: {source_results_dir}")
        return

    latest_json = json_files[-1]
    logger.info(f"使用文件: {latest_json.name}")
    logger.info(f"输出目录: {output_dir}")

    # 加载数据
    data = load_solution_data(latest_json)

    # 分析成本构成
    cost_items, cost_percentages, total_cost = analyze_cost_composition(data)

    # 分析电力使用
    power_data, power_by_site = analyze_power_usage(data)

    # 保存报告
    save_analysis_report(cost_items, cost_percentages, total_cost, power_data, power_by_site, output_dir)
    save_csv_reports(cost_items, cost_percentages, power_data, power_by_site, output_dir)

    logger.info(f"\n{'='*80}")
    logger.info("分析完成!")

if __name__ == '__main__':
    main()
