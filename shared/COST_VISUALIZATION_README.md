# 成本可视化系统 (Cost Visualization System)

绿色甲醇供应链成本分析和可视化引擎，提供全面的成本分析图表和交互式仪表板。

## 功能特性

### 📊 可视化类型
- **成本结构分解图表**: 饼图、柱状图、堆叠图
- **成本瀑布图**: 显示从原料到最终产品的成本流
- **单位成本分析**: 氢气vs MTJ成本对比
- **效率分析**: 转化效率和效率损失分析  
- **运输成本分析**: 单位运输成本和总运输成本
- **交互式仪表板**: HTML格式的动态仪表板
- **综合成本报告**: 文本格式的详细分析报告

### 🎯 核心指标
- 生命周期总成本分析
- 平准化成本计算 (含/不含短缺成本)
- 单位成本分解 (氢气/MTJ)
- 转化效率分析 (理论vs实际)
- 成本构成占比分析
- 运输和储存成本分析

## 使用方法

### 1. 基本用法

```python
from shared.cost_visualization_engine import create_cost_visualization_engine

# 创建可视化引擎
engine = create_cost_visualization_engine('results')

# 加载数据
engine.load_optimization_data()

# 生成综合报告
results = engine.generate_comprehensive_report()
```

### 2. 独立脚本使用

```bash
# 生成完整报告
python create_cost_visualizations.py

# 指定特定文件
python create_cost_visualizations.py --file optimization_summary_20250911_222029.csv

# 仅生成特定类型的可视化
python create_cost_visualizations.py --breakdown-only
python create_cost_visualizations.py --interactive-only
python create_cost_visualizations.py --waterfall-only

# 显示帮助
python create_cost_visualizations.py --help
```

### 3. 单独调用不同功能

```python
# 成本结构分解图表
charts = engine.create_cost_breakdown_charts()

# 成本瀑布图
waterfall = engine.create_cost_waterfall_chart()

# 单位成本分析
unit_costs = engine.create_unit_cost_analysis_charts()

# 交互式仪表板
dashboard = engine.create_interactive_dashboard()
```

## 输出文件结构

```
results/
├── charts/                                    # 静态图表
│   ├── cost_breakdown_pie_YYYYMMDD_HHMMSS.png
│   ├── investment_vs_operational_YYYYMMDD_HHMMSS.png
│   ├── detailed_cost_breakdown_YYYYMMDD_HHMMSS.png
│   ├── cost_waterfall_YYYYMMDD_HHMMSS.png
│   ├── unit_cost_comparison_YYYYMMDD_HHMMSS.png
│   ├── efficiency_analysis_YYYYMMDD_HHMMSS.png
│   ├── cost_composition_YYYYMMDD_HHMMSS.png
│   └── transport_cost_analysis_YYYYMMDD_HHMMSS.png
├── figures/                                   # 交互式图表
│   └── interactive_cost_dashboard_YYYYMMDD_HHMMSS.html
└── reports/                                   # 分析报告
    └── cost_analysis_report_YYYYMMDD_HHMMSS.txt
```

## 技术架构

### 依赖库
- **pandas**: 数据处理和分析
- **matplotlib**: 静态图表生成
- **seaborn**: 统计图表美化
- **plotly**: 交互式图表和仪表板
- **numpy**: 数值计算

### 核心组件
- `CostVisualizationEngine`: 主要可视化引擎类
- `create_cost_visualization_engine()`: 工厂函数
- `create_cost_visualizations.py`: 独立执行脚本

## 数据源

系统从以下CSV文件读取数据：
- `optimization_summary_YYYYMMDD_HHMMSS.csv`

### 关键数据字段
- 生命周期总成本(元)
- 生命周期平准化成本(元/kg) 
- 生命周期平准化成本_不含短缺(元/kg)
- 氢气总单位成本(元/kg)
- MTJ总单位成本(元/kg)
- 各类投资和运营成本项
- 转化效率指标
- 运输和储存成本

## 关键洞察

系统能够识别和展示：

1. **成本驱动因素**
   - MTJ生产运营成本占主导地位
   - 短缺惩罚成本对总成本影响巨大
   - 投资vs运营成本比例分析

2. **效率优化机会**
   - 电解制氢效率损失分析
   - MTJ转化效率提升潜力
   - 综合电力转MTJ效率评估

3. **成本结构优化**
   - 氢气vs MTJ单位成本对比
   - 运输成本优化机会识别
   - 储存成本效率分析

## 使用示例

### 快速测试
```bash
cd products/supply_chain_optimization/natural_gas_supply_chain_optimization
python test_visualization.py
```

### 生成完整报告
```bash
cd products/supply_chain_optimization/natural_gas_supply_chain_optimization
python create_cost_visualizations.py --all --verbose
```

## 故障排除

### 常见问题

1. **数据文件未找到**
   - 检查results目录下是否存在optimization_summary_*.csv文件
   - 确保文件路径正确

2. **中文显示问题**
   - Windows系统可能存在编码问题
   - 图表中文字体已配置为SimHei/Microsoft YaHei

3. **依赖库缺失**
   ```bash
   pip install pandas matplotlib seaborn plotly numpy
   ```

4. **内存不足**
   - 大数据集可能导致内存问题
   - 建议在生成图表后及时释放资源

## 版本信息

- **创建时间**: 2025-09-12
- **作者**: Claude Code
- **版本**: 1.0.0
- **最后更新**: 2025-09-12

## 未来改进

- [ ] 添加PDF报告生成功能
- [ ] 支持多文件对比分析
- [ ] 增加更多交互式图表类型
- [ ] 优化大数据集的处理性能
- [ ] 添加自定义颜色主题支持