# 示例功能需求 - 绿色甲醇碳排放对比分析工具

## FEATURE:
构建一个绿色甲醇与传统航空燃料的碳排放对比分析工具。该工具应该能够：

1. **数据输入功能**：
   - 读取航班数据（Excel/CSV格式），包含机型、距离、乘客数等信息
   - 支持批量处理多个数据文件
   - 自动识别和验证数据格式

2. **碳排放计算功能**：
   - 使用现有的pyBADA燃料计算器计算传统航空燃料的碳排放
   - 实现绿色甲醇燃料的碳排放计算模型
   - 考虑不同机型的燃料效率差异
   - 包含生产阶段的碳足迹（Well-to-Wake分析）

3. **对比分析功能**：
   - 计算减排量和减排百分比
   - 分析不同航线的减排潜力
   - 生成机型级别的对比统计
   - 计算成本效益分析

4. **可视化输出**：
   - 生成柱状图、饼图、散点图等多种图表
   - 支持中文标签和说明
   - 输出高分辨率PNG图片到results/figures/目录
   - 创建交互式HTML报告

5. **数据输出**：
   - 详细对比结果表格（Excel和CSV格式）
   - 汇总统计报告
   - 保存到results/tables/目录，文件名包含时间戳

## EXAMPLES:
应该遵循的代码模式：

1. **数据处理模式**：
   - 遵循 `examples/data_processing_pattern.py` 的标准数据处理流程
   - 使用 `ProcessingResult` 数据类进行结果封装
   - 实现完整的错误处理和日志记录

2. **计算模式**：
   - 参考 `air_port_data_process/src/pybada_fuel_calculator.py` 的计算结构
   - 使用现有的航空燃料计算方法
   - 遵循相同的单位和数据验证模式

3. **测试模式**：
   - 使用 `examples/test_pattern.py` 的测试结构
   - 实现参数化测试用于不同机型和燃料类型
   - 包含集成测试验证完整工作流

4. **可视化模式**：
   - 参考 `gis_data_scraper/visualize_energy_infrastructure.py` 的可视化结构
   - 确保中文字体正确设置
   - 使用项目统一的颜色方案

## DOCUMENTATION:
相关技术文档：

1. **项目文档**：
   - `README.md` - 了解项目整体架构
   - `air_port_data_process/README.md` - pyBADA燃料计算系统文档
   - `natural_gas_supply_chain_optimization/天然气供应链优化数学模型与数据流分析.md` - 能源建模方法

2. **外部API文档**：
   - pyBADA文档: https://github.com/eurocontrol/pyBADA
   - pandas处理Excel: https://pandas.pydata.org/docs/user_guide/io.html#excel-files
   - matplotlib中文字体: https://matplotlib.org/stable/tutorials/text/usetex.html

3. **领域知识资源**：
   - ICAO碳排放计算标准: https://www.icao.int/environmental-protection/CarbonOffset/
   - 绿色甲醇技术: https://www.irena.org/publications/2021/Jan/Innovation-Outlook-Renewable-Methanol
   - 航空燃料生命周期评估方法

## OTHER CONSIDERATIONS:

### 技术要求：
- **环境兼容**：必须在 `green_methanol_for_port_transportation` conda环境中运行
- **性能目标**：能够处理包含10,000个航班记录的数据集，完整分析时间<2分钟
- **内存管理**：对于大数据集实现分块处理，避免内存溢出
- **并行计算**：利用multiprocessing并行处理不同机型的计算

### 数据处理特殊要求：
- **中文支持**：正确处理中文机场名称（如"北京首都国际机场"）
- **坐标验证**：验证机场坐标的合理性（中国境内：lat 18-54, lon 73-135）
- **数据完整性**：检查必需字段的完整性（机型、距离、乘客数等）
- **单位统一**：确保所有计算使用统一单位（距离：km，燃料：kg，排放：kg CO2）

### 绿色甲醇特定参数：
- **碳强度**：绿色甲醇碳强度约 0.1 kg CO2/kg fuel（包含生产阶段）
- **燃烧效率**：相比传统燃料效率调整系数 0.95-1.05
- **能量密度**：绿色甲醇 19.9 MJ/kg vs Jet A-1 43.2 MJ/kg
- **成本因子**：当前绿色甲醇成本约为传统燃料的2.5-3倍

### 输出格式要求：
- **表格文件**：使用时间戳命名 `methanol_comparison_20250107_143022.xlsx`
- **图表文件**：PNG格式，300 DPI，尺寸 12x8 英寸
- **报告结构**：包含执行摘要、详细分析、附录数据表
- **元数据文件**：记录计算参数、数据来源、处理时间等

### 常见陷阱和注意事项：
- **机型映射**：确保正确映射ICAO机型代码到容量和效率参数
- **距离计算**：使用大圆距离（Haversine公式）而非直线距离
- **负载因子**：考虑实际载客率对燃料消耗的影响
- **季节调整**：不同季节的飞行条件对燃料消耗的影响
- **高度修正**：高原机场的燃料消耗调整
- **数据时效性**：确保使用最新的排放因子和燃料特性数据

### 质量保证要求：
- **基准验证**：使用已知航线的实际数据验证计算精度
- **敏感性分析**：测试关键参数变化对结果的影响
- **对比验证**：与现有工具（如OpenAP）的结果进行对比
- **专家审核**：计算逻辑需要经过航空燃料专家审核

### 部署和维护：
- **版本控制**：所有代码变更通过git管理
- **文档更新**：更新模块README和主项目README
- **依赖管理**：新增依赖添加到requirements.txt
- **测试覆盖**：确保测试覆盖率>90%
- **性能监控**：记录处理时间和内存使用情况