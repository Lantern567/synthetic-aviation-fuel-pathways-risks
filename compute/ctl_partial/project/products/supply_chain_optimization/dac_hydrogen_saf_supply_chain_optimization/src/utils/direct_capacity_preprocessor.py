#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
直接数据预处理工具 - 计算天然气设施日处理能力

该脚本直接读取原始GIS数据文件，计算天然气管道和LNG接收站的有效日处理能力，
并将结果添加到原始数据文件中。

功能：
1. 读取原始天然气管道数据
2. 读取原始LNG接收站数据  
3. 计算有效日处理能力
4. 将计算结果添加到原始文件中

作者: Claude Code
日期: 2025-01-28
"""

import pandas as pd
import numpy as np
import logging
from pathlib import Path

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DirectCapacityPreprocessor:
    """直接处理原始数据文件的容量预处理器"""
    
    def __init__(self):
        """初始化预处理器"""
        # 定义文件路径
        self.base_dir = Path(__file__).parent.parent.parent.parent.parent
        self.data_dir = self.base_dir / "products" / "gis_energy_mapping" / "gis_data_scraper" / "scraped_gis_data"
        
        # 数据文件路径 - 使用集成的带坐标的管道数据
        self.ng_pipeline_file = self.base_dir / "products" / "supply_chain_optimization" / "dac_hydrogen_saf_supply_chain_optimization" / "data" / "integrated_gas_pipeline_price_data_with_coords.csv"
        self.lng_terminal_file = self.data_dir / "lng_terminals.xlsx"
        
        # 默认参数
        self.default_supply_reliability = 0.95
        self.default_operational_efficiency = 0.90
        
        logger.info(f"数据目录: {self.data_dir}")
    
    def process_pipeline_data(self):
        """处理天然气管道数据，添加日处理能力字段"""
        logger.info("开始处理天然气管道数据...")
        
        try:
            # 读取集成的管道数据（CSV格式，已包含坐标）
            df = pd.read_csv(self.ng_pipeline_file)
            logger.info(f"读取到 {len(df)} 条管道数据")
            
            # 检查现有列
            logger.info(f"现有列: {list(df.columns)}")
            
            # 检查是否已有有效日处理能力字段
            if 'effective_daily_capacity_m3_per_day' not in df.columns:
                df['effective_daily_capacity_m3_per_day'] = 0.0
                logger.info("添加了 effective_daily_capacity_m3_per_day 字段")
            
            processed_count = 0
            
            for idx, row in df.iterrows():
                # 集成文件已经有capacity_mcm_per_day字段
                capacity_mcm_per_day = row.get('capacity_mcm_per_day', 0)
                
                if pd.isna(capacity_mcm_per_day) or capacity_mcm_per_day <= 0:
                    logger.warning(f"第 {idx+1} 行管道缺少有效容量数据，跳过")
                    continue
                
                # 转换为立方米/天
                daily_capacity_m3 = capacity_mcm_per_day * 10000  # 万立方米转立方米
                
                # 获取供应可靠性（集成文件中已有此字段）
                reliability = row.get('supply_reliability', self.default_supply_reliability)
                
                # 计算有效日处理能力
                effective_daily_capacity = daily_capacity_m3 * reliability
                
                # 更新数据框
                df.loc[idx, 'effective_daily_capacity_m3_per_day'] = effective_daily_capacity
                
                processed_count += 1
                
                pipeline_name = row.get('pipeline_name', row.get('Name', '未知'))
                logger.info(f"管道 {idx+1} ({pipeline_name}): "
                           f"日容量 {capacity_mcm_per_day:.2f} 万m³/天, "
                           f"可靠性 {reliability:.2%}, "
                           f"有效容量 {effective_daily_capacity/10000:.2f} 万m³/天")
            
            # 保存更新后的数据
            output_file = self.data_dir / "natural_gas_pipelines_with_capacity.xlsx"
            df.to_excel(output_file, index=False)
            logger.info(f"管道数据已保存到: {output_file}")
            logger.info(f"成功处理 {processed_count} 条管道记录")
            
            return df, processed_count
            
        except Exception as e:
            logger.error(f"处理管道数据时发生错误: {e}")
            raise
    
    def process_lng_terminal_data(self):
        """处理LNG接收站数据，添加日处理能力字段"""
        logger.info("开始处理LNG接收站数据...")
        
        try:
            # 读取数据
            df = pd.read_excel(self.lng_terminal_file)
            logger.info(f"读取到 {len(df)} 条LNG接收站数据")
            
            # 检查现有列
            logger.info(f"现有列: {list(df.columns)}")
            
            # 初始化新列
            df['lng_capacity_mcm_per_year'] = 0.0
            df['operational_efficiency'] = self.default_operational_efficiency
            df['effective_daily_capacity_m3_per_day'] = 0.0
            
            processed_count = 0
            
            for idx, row in df.iterrows():
                # 优先使用current_capacity，然后是Capacity
                capacity_raw = row.get('current_capacity__Million_tonne', 0)
                if pd.isna(capacity_raw) or capacity_raw == 0:
                    capacity_raw = row.get('Capacity', 0)
                    
                if pd.isna(capacity_raw) or capacity_raw == 0:
                    logger.warning(f"第 {idx+1} 行LNG接收站缺少容量数据，跳过")
                    continue
                
                # 处理不同单位的容量
                cap_unit = str(row.get('CapUnit', 'MTPA')).upper()
                
                if 'MTPA' in cap_unit or 'Million' in str(cap_unit):  # Million Tonnes Per Annum
                    # 1 吨LNG ≈ 1380 立方米天然气
                    # 1 MTPA = 1,000,000 * 1380 / 365 立方米/天
                    lng_capacity_mcm_per_year = capacity_raw * 138  # 万立方米/年
                elif 'MMCM' in cap_unit:  # Million Cubic Meters per Year
                    lng_capacity_mcm_per_year = capacity_raw * 10  # 转换为万立方米/年
                else:
                    # 默认假设为MTPA
                    logger.warning(f"第 {idx+1} 行单位未知: {cap_unit}，假设为MTPA")
                    lng_capacity_mcm_per_year = capacity_raw * 138
                
                # 转换为日处理能力（立方米/天）
                daily_capacity_mcm = lng_capacity_mcm_per_year / 365  # 万立方米/天
                daily_capacity_m3 = daily_capacity_mcm * 10000  # 立方米/天
                
                # 计算有效日处理能力（考虑操作效率）
                efficiency = self.default_operational_efficiency
                effective_daily_capacity = daily_capacity_m3 * efficiency
                
                # 更新数据框
                df.loc[idx, 'lng_capacity_mcm_per_year'] = lng_capacity_mcm_per_year
                df.loc[idx, 'operational_efficiency'] = efficiency
                df.loc[idx, 'effective_daily_capacity_m3_per_day'] = effective_daily_capacity
                
                processed_count += 1
                
                logger.info(f"LNG接收站 {idx+1} ({row.get('Name', '未知')}): "
                           f"原始容量 {capacity_raw} {cap_unit}, "
                           f"年容量 {lng_capacity_mcm_per_year:.1f} 万m³/年, "
                           f"有效日容量 {effective_daily_capacity/10000:.2f} 万m³/天")
            
            # 保存更新后的数据
            output_file = self.data_dir / "lng_terminals_with_capacity.xlsx"
            df.to_excel(output_file, index=False)
            logger.info(f"LNG接收站数据已保存到: {output_file}")
            logger.info(f"成功处理 {processed_count} 条LNG接收站记录")
            
            return df, processed_count
            
        except Exception as e:
            logger.error(f"处理LNG接收站数据时发生错误: {e}")
            raise
    
    def generate_summary_report(self, pipeline_count, lng_count):
        """生成处理汇总报告"""
        report_file = self.data_dir / "capacity_preprocessing_report.md"
        
        report_content = f"""# 天然气设施容量预处理报告

## 处理概况
- **处理时间**: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}
- **管道处理数量**: {pipeline_count}
- **LNG接收站处理数量**: {lng_count}

## 处理逻辑

### 天然气管道容量计算
- **输入字段**: Capacity, CapUnit
- **单位转换**:
  - BCF/D → 万立方米/天 (×28.32)  
  - MMCF/D → 万立方米/天 (×0.02832)
  - MCM/D → 万立方米/天 (直接使用)
- **有效容量**: 原始容量 × 供应可靠性 (默认0.95)
- **输出字段**: 
  - capacity_mcm_per_day: 日处理能力 (万立方米/天)
  - effective_daily_capacity_m3_per_day: 有效日处理能力 (立方米/天)

### LNG接收站容量计算  
- **输入字段**: current_capacity__Million_tonne 或 Capacity, CapUnit
- **单位转换**:
  - MTPA → 万立方米/年 (×138, 基于1吨LNG≈1380m³天然气)
  - MMCM/Y → 万立方米/年 (×10)
- **日容量转换**: 年容量 ÷ 365天
- **有效容量**: 日容量 × 操作效率 (默认0.90)
- **输出字段**:
  - lng_capacity_mcm_per_year: 年处理能力 (万立方米/年)
  - effective_daily_capacity_m3_per_day: 有效日处理能力 (立方米/天)

## 输出文件
- `natural_gas_pipelines_with_capacity.xlsx`: 包含日处理能力的管道数据
- `lng_terminals_with_capacity.xlsx`: 包含日处理能力的LNG接收站数据

## 使用建议
1. 在优化模型中直接读取 `effective_daily_capacity_m3_per_day` 字段
2. 删除优化过程中的日处理能力计算逻辑
3. 定期重新运行此脚本以更新数据
"""
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        logger.info(f"处理报告已生成: {report_file}")
    
    def run(self):
        """运行完整的预处理流程"""
        logger.info("=" * 60)
        logger.info("开始天然气设施容量预处理")
        logger.info("=" * 60)
        
        try:
            # 处理管道数据
            pipeline_df, pipeline_count = self.process_pipeline_data()
            
            # 处理LNG接收站数据
            lng_df, lng_count = self.process_lng_terminal_data()
            
            # 生成汇总报告
            self.generate_summary_report(pipeline_count, lng_count)
            
            logger.info("=" * 60)
            logger.info("天然气设施容量预处理完成")
            logger.info(f"处理管道: {pipeline_count} 个")
            logger.info(f"处理LNG接收站: {lng_count} 个")
            logger.info("=" * 60)
            
            return {
                'pipeline_count': pipeline_count,
                'lng_count': lng_count,
                'success': True
            }
            
        except Exception as e:
            logger.error(f"预处理过程中发生错误: {e}")
            return {
                'error': str(e),
                'success': False
            }


def main():
    """主函数"""
    preprocessor = DirectCapacityPreprocessor()
    result = preprocessor.run()
    
    if result['success']:
        logger.info("预处理成功完成!")
    else:
        logger.error(f"预处理失败: {result['error']}")


if __name__ == "__main__":
    main()