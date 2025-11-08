"""
工业副产氢源数据整合为Excel
整合钢铁焦化和石化炼厂的副产氢源数据到单个Excel文件
"""

import pandas as pd
import logging
from pathlib import Path
from datetime import datetime

def setup_logging():
    """设置日志"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)

def find_latest_data_files(data_dir):
    """查找最新的数据文件"""
    logger = logging.getLogger(__name__)
    logger.info("正在查找最新的数据文件...")

    steel_files = list(data_dir.glob('steel_daily_byproduct_h2_*.csv'))
    refinery_files = list(data_dir.glob('refinery_daily_byproduct_h2_*.csv'))

    if not steel_files or not refinery_files:
        raise FileNotFoundError("未找到数据文件")

    latest_steel = max(steel_files, key=lambda x: x.stat().st_mtime)
    latest_refinery = max(refinery_files, key=lambda x: x.stat().st_mtime)

    logger.info(f"钢铁数据: {latest_steel.name}")
    logger.info(f"石化数据: {latest_refinery.name}")

    return latest_steel, latest_refinery

def load_and_prepare_steel_data(steel_file):
    """加载并准备钢铁数据"""
    logger = logging.getLogger(__name__)
    logger.info("正在加载钢铁焦化数据...")

    df = pd.read_csv(steel_file, encoding='utf-8')

    # 选择需要的列并重命名
    steel_df = pd.DataFrame({
        '设施名称': df['plant_name'],
        '氢源类型': '钢铁焦化副产氢',
        '省份': df['province'],
        '纬度': df['latitude'],
        '经度': df['longitude'],
        '日产氢量(吨/天)': df['h2_daily_tonnes'],
        '年产氢量(吨/年)': df['h2_daily_tonnes'] * 365,
        '高炉数量': df.get('num_blast_furnaces', None)
    })

    # 按日产氢量降序排序
    steel_df = steel_df.sort_values('日产氢量(吨/天)', ascending=False).reset_index(drop=True)

    logger.info(f"加载钢铁设施: {len(steel_df)} 个")

    return steel_df

def load_and_prepare_refinery_data(refinery_file):
    """加载并准备石化数据"""
    logger = logging.getLogger(__name__)
    logger.info("正在加载石化炼厂数据...")

    df = pd.read_csv(refinery_file, encoding='utf-8')

    # 选择需要的列并重命名
    refinery_df = pd.DataFrame({
        '设施名称': df['refinery_name'],
        '氢源类型': '石化催化重整副产氢',
        '省份': df['province'],
        '纬度': df['latitude'],
        '经度': df['longitude'],
        '日产氢量(吨/天)': df['h2_daily_tonnes'],
        '年产氢量(吨/年)': df['h2_daily_tonnes'] * 365,
        '炼厂产能(千桶/日)': df.get('capacity_kbd', None)
    })

    # 按日产氢量降序排序
    refinery_df = refinery_df.sort_values('日产氢量(吨/天)', ascending=False).reset_index(drop=True)

    logger.info(f"加载石化设施: {len(refinery_df)} 个")

    return refinery_df

def create_summary_df(steel_df, refinery_df):
    """创建汇总数据"""
    logger = logging.getLogger(__name__)
    logger.info("正在创建汇总数据...")

    # 钢铁统计
    steel_stats = {
        '氢源类型': '钢铁焦化副产氢',
        '设施数量': len(steel_df),
        '日产氢量(吨/天)': steel_df['日产氢量(吨/天)'].sum(),
        '年产氢量(吨/年)': steel_df['年产氢量(吨/年)'].sum(),
        '平均单厂日产氢(吨/天)': steel_df['日产氢量(吨/天)'].mean(),
        '最大单厂日产氢(吨/天)': steel_df['日产氢量(吨/天)'].max(),
        '最小单厂日产氢(吨/天)': steel_df['日产氢量(吨/天)'].min()
    }

    # 石化统计
    refinery_stats = {
        '氢源类型': '石化催化重整副产氢',
        '设施数量': len(refinery_df),
        '日产氢量(吨/天)': refinery_df['日产氢量(吨/天)'].sum(),
        '年产氢量(吨/年)': refinery_df['年产氢量(吨/年)'].sum(),
        '平均单厂日产氢(吨/天)': refinery_df['日产氢量(吨/天)'].mean(),
        '最大单厂日产氢(吨/天)': refinery_df['日产氢量(吨/天)'].max(),
        '最小单厂日产氢(吨/天)': refinery_df['日产氢量(吨/天)'].min()
    }

    # 总计统计
    total_stats = {
        '氢源类型': '总计',
        '设施数量': len(steel_df) + len(refinery_df),
        '日产氢量(吨/天)': steel_stats['日产氢量(吨/天)'] + refinery_stats['日产氢量(吨/天)'],
        '年产氢量(吨/年)': steel_stats['年产氢量(吨/年)'] + refinery_stats['年产氢量(吨/年)'],
        '平均单厂日产氢(吨/天)': (steel_stats['日产氢量(吨/天)'] + refinery_stats['日产氢量(吨/天)']) / (len(steel_df) + len(refinery_df)),
        '最大单厂日产氢(吨/天)': max(steel_stats['最大单厂日产氢(吨/天)'], refinery_stats['最大单厂日产氢(吨/天)']),
        '最小单厂日产氢(吨/天)': min(steel_stats['最小单厂日产氢(吨/天)'], refinery_stats['最小单厂日产氢(吨/天)'])
    }

    summary_df = pd.DataFrame([steel_stats, refinery_stats, total_stats])

    return summary_df

def create_province_summary(steel_df, refinery_df):
    """创建省份汇总"""
    logger = logging.getLogger(__name__)
    logger.info("正在创建省份汇总...")

    # 钢铁按省份统计
    steel_by_province = steel_df.groupby('省份').agg({
        '设施名称': 'count',
        '日产氢量(吨/天)': 'sum',
        '年产氢量(吨/年)': 'sum'
    }).rename(columns={'设施名称': '钢铁设施数量', '日产氢量(吨/天)': '钢铁日产氢(吨/天)', '年产氢量(吨/年)': '钢铁年产氢(吨/年)'})

    # 石化按省份统计
    refinery_by_province = refinery_df.groupby('省份').agg({
        '设施名称': 'count',
        '日产氢量(吨/天)': 'sum',
        '年产氢量(吨/年)': 'sum'
    }).rename(columns={'设施名称': '石化设施数量', '日产氢量(吨/天)': '石化日产氢(吨/天)', '年产氢量(吨/年)': '石化年产氢(吨/年)'})

    # 合并
    province_summary = pd.concat([steel_by_province, refinery_by_province], axis=1).fillna(0)

    # 计算总计
    province_summary['设施总数'] = province_summary['钢铁设施数量'] + province_summary['石化设施数量']
    province_summary['日产氢总量(吨/天)'] = province_summary['钢铁日产氢(吨/天)'] + province_summary['石化日产氢(吨/天)']
    province_summary['年产氢总量(吨/年)'] = province_summary['钢铁年产氢(吨/年)'] + province_summary['石化年产氢(吨/年)']

    # 重新排列列顺序
    province_summary = province_summary[[
        '设施总数', '钢铁设施数量', '石化设施数量',
        '日产氢总量(吨/天)', '钢铁日产氢(吨/天)', '石化日产氢(吨/天)',
        '年产氢总量(吨/年)', '钢铁年产氢(吨/年)', '石化年产氢(吨/年)'
    ]]

    # 按日产氢总量降序排序
    province_summary = province_summary.sort_values('日产氢总量(吨/天)', ascending=False)

    # 将索引(省份)变为列
    province_summary = province_summary.reset_index()

    return province_summary

def save_to_excel(steel_df, refinery_df, summary_df, province_summary, output_path):
    """保存到Excel文件"""
    logger = logging.getLogger(__name__)
    logger.info(f"正在保存Excel文件: {output_path}")

    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        # 汇总sheet
        summary_df.to_excel(writer, sheet_name='汇总统计', index=False)

        # 省份汇总sheet
        province_summary.to_excel(writer, sheet_name='省份统计', index=False)

        # 钢铁数据sheet
        steel_df.to_excel(writer, sheet_name='钢铁焦化', index=False)

        # 石化数据sheet
        refinery_df.to_excel(writer, sheet_name='石化炼厂', index=False)

        # 全部数据合并sheet
        all_facilities = pd.concat([
            steel_df.drop(columns=['高炉数量'], errors='ignore'),
            refinery_df.drop(columns=['炼厂产能(千桶/日)'], errors='ignore')
        ], ignore_index=True)

        all_facilities = all_facilities.sort_values('日产氢量(吨/天)', ascending=False).reset_index(drop=True)
        all_facilities.to_excel(writer, sheet_name='全部设施', index=False)

    logger.info(f"Excel文件保存成功: {output_path}")

def main():
    """主函数"""
    logger = setup_logging()

    logger.info("="*60)
    logger.info("开始创建工业副产氢源Excel文件")
    logger.info("="*60)

    # 设置路径
    script_dir = Path(__file__).parent
    data_dir = script_dir / 'data'
    results_dir = script_dir / 'results' / 'tables'
    results_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 1. 查找数据文件
        steel_file, refinery_file = find_latest_data_files(data_dir)

        # 2. 加载并准备数据
        steel_df = load_and_prepare_steel_data(steel_file)
        refinery_df = load_and_prepare_refinery_data(refinery_file)

        # 3. 创建汇总统计
        summary_df = create_summary_df(steel_df, refinery_df)

        # 4. 创建省份统计
        province_summary = create_province_summary(steel_df, refinery_df)

        # 5. 保存Excel
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f'industrial_byproduct_hydrogen_sources_{timestamp}.xlsx'
        output_path = results_dir / output_filename

        save_to_excel(steel_df, refinery_df, summary_df, province_summary, output_path)

        # 打印统计信息
        logger.info("="*60)
        logger.info("✓ Excel文件创建成功!")
        logger.info(f"✓ 输出文件: {output_filename}")
        logger.info(f"✓ 完整路径: {output_path}")
        logger.info("="*60)
        logger.info("数据统计:")
        logger.info(f"  钢铁设施: {len(steel_df)} 个")
        logger.info(f"  石化设施: {len(refinery_df)} 个")
        logger.info(f"  设施总数: {len(steel_df) + len(refinery_df)} 个")
        logger.info(f"  日产氢总量: {steel_df['日产氢量(吨/天)'].sum() + refinery_df['日产氢量(吨/天)'].sum():,.0f} 吨/天")
        logger.info(f"  年产氢总量: {steel_df['年产氢量(吨/年)'].sum() + refinery_df['年产氢量(吨/年)'].sum():,.0f} 吨/年")
        logger.info("="*60)
        logger.info("Excel包含以下工作表:")
        logger.info("  1. 汇总统计 - 钢铁、石化、总计的统计数据")
        logger.info("  2. 省份统计 - 各省份产氢量汇总")
        logger.info("  3. 钢铁焦化 - 211个钢铁设施详细数据")
        logger.info("  4. 石化炼厂 - 180个炼厂详细数据")
        logger.info("  5. 全部设施 - 391个设施完整数据")
        logger.info("="*60)

        print(f"\n[SUCCESS] Excel文件已保存至: {output_path}")

    except Exception as e:
        logger.error(f"创建Excel文件失败: {e}")
        raise

if __name__ == "__main__":
    main()
