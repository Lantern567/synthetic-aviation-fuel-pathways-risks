# 天然气设施容量预处理报告

## 处理概况
- **处理时间**: 2025-09-03 00:58:41
- **管道处理数量**: 487
- **LNG接收站处理数量**: 78

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
