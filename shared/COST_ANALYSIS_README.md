# 成本分析引擎使用说明

## 概述
绿色甲醇供应链成本分析引擎是一个专门用于详细成本分解和效率分析的模块，已集成到主优化模型中。

## 功能特性

### 1. 电解制氢成本分析
- 电力成本（可再生能源电力）
- 电解槽设备摊销成本  
- 电解槽运营维护成本
- 成本占比分析

### 2. MTJ生产成本分析
- 氢气原料成本
- CO2原料成本（来自天然气）
- MTJ工厂设备摊销
- MTJ工厂运营维护成本
- 各项成本占比分析

### 3. 运输成本分析
- 氢气运输单位成本 (元/kg·km)
- MTJ运输单位成本 (元/kg·km)
- 储存配送成本
- 距离调整因子

### 4. 转化效率分析
- 电解制氢效率 (理论vs实际)
- 氢气制MTJ转化效率
- 综合电力→MTJ效率
- 单位电力消耗 (MWh/kg MTJ)

## 输出文件

### 增强的 transport_summary_*.csv
现在包含以下新增列：
- **MTJ相关成本**
  - MTJ生产单位成本(元/kg)
  - MTJ氢气原料成本(元/kg)
  - MTJ CO2原料成本(元/kg)  
  - MTJ设备摊销成本(元/kg)
  - MTJ运输单位成本(元/kg·km)
  - MTJ储存成本(元/kg)
  - MTJ总运输成本(元)

- **氢气相关成本**
  - 氢气生产单位成本(元/kg)
  - 氢气电力成本(元/kg)
  - 氢气设备摊销成本(元/kg)
  - 氢气运输单位成本(元/kg·km)
  - 氢气储存成本(元/kg)
  - 氢气总运输成本(元)

- **效率指标**
  - 电解制氢效率(%)
  - MTJ转化效率(%)
  - 综合电力转MTJ效率(%)
  - 单位电力消耗(MWh/kg_MTJ)

### 新增 cost_analysis_report_*.csv
详细的成本分析报告，包含：
- 各成本类别详细分解
- 成本项目说明
- 单位成本和占比
- 备注信息

## 使用方法

### 自动集成（推荐）
成本分析模块已自动集成到主优化模型中，无需额外配置：

```python
# 正常运行优化模型
optimizer = NaturalGasSupplyChainOptimizer()
optimizer.load_data(renewable_data, airport_data)
optimizer.build_model()
solution = optimizer.solve()

# 保存结果时自动包含成本分析
optimizer.save_results(solution, output_dir)
```

### 独立使用
也可以独立使用成本分析模块：

```python
from shared.cost_analysis_engine import create_cost_analyzer

# 创建成本分析器
analyzer = create_cost_analyzer(config, costs, economic_params)

# 电解制氢成本分析
h2_costs = analyzer.calculate_electrolysis_unit_costs()

# MTJ生产成本分析  
mtj_costs = analyzer.calculate_mtj_production_unit_costs(h2_unit_cost)

# 运输成本分析
transport_costs = analyzer.calculate_transport_unit_costs(distance_km, "MTJ")

# 效率分析
efficiencies = analyzer.calculate_conversion_efficiencies()

# 综合分析
comprehensive = analyzer.analyze_supply_chain_costs(solution)
```

## 参数配置
成本分析器使用现有配置文件中的参数，主要包括：

### 电解制氢参数
- `electrolysis_efficiency`: 电解制氢效率
- `electrolysis_power_consumption`: 电力消耗 (MWh/t H2)  
- `renewable_electricity_cost_yuan_per_mwh`: 可再生能源电价

### 设备成本参数
- `electrolyzer_capex_yuan_per_kg_h2_year`: 电解槽年化投资成本
- `electrolyzer_opex_yuan_per_kg_h2`: 电解槽运营成本
- `mtj_base_lcop_yuan_per_kg`: MTJ基础平准化成本

### 运输参数
- 基于距离的运输成本模型
- 不同货物类型的基础运输费率
- 储存成本参数

## 技术特性
- **模块化设计**: 独立的成本分析模块，易于维护和扩展
- **数据驱动**: 基于配置文件参数，支持灵活调整
- **自动集成**: 无缝集成到主优化模型，自动增强输出结果
- **错误处理**: 完善的异常处理，确保主流程不受影响
- **可扩展性**: 易于添加新的成本类别和分析指标

## 文件位置
- 主模块: `shared/cost_analysis_engine.py`
- 测试脚本: `src/simple_test.py`, `src/test_integration.py`
- 集成位置: `src/natural_gas_optimization_model.py`

成本分析引擎为绿色甲醇项目的经济可行性分析提供了全面的成本透明度和决策支持。