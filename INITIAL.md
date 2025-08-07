# 功能需求说明

## FEATURE:
[在这里详细描述你想要构建的功能 - 要具体说明功能需求、预期输入输出、性能要求等]

示例：
- 构建一个绿色甲醇运输成本分析模块
- 实现航空燃料碳足迹对比功能
- 开发港口能源效率优化算法
- 创建能源基础设施可视化工具

## EXAMPLES:
[列出examples/文件夹中相关的示例文件，说明应该如何使用这些模式]

可用的示例模式：
- `examples/data_processing_pattern.py` - 标准数据处理流程，包括读取、清理、验证、保存
- `examples/test_pattern.py` - 测试结构和模式，包括单元测试、集成测试、Mock使用
- 查看 `examples/README.md` 了解所有可用模式

你应该遵循的模式：
- [指定应该遵循的具体模式，如数据处理、可视化、测试等]
- [说明需要特别注意的代码风格或架构要求]

## DOCUMENTATION:
[包含相关文档、API、MCP服务器资源的链接]

项目相关文档：
- 主README: `README.md` - 项目概述和模块说明
- 模块README: `{module_name}/README.md` - 具体模块文档
- 技术文档: `natural_gas_supply_chain_optimization/天然气供应链优化数学模型与数据流分析.md`

外部资源：
- [相关API文档URL]
- [参考论文或技术标准URL]
- [第三方库文档URL]

数据源说明：
- [描述数据来源和格式]
- [数据质量和预处理要求]
- [数据更新频率和获取方式]

## OTHER CONSIDERATIONS:
[提及任何需要注意的问题、特定要求或AI助手通常会忽略的细节]

技术要求：
- 环境：必须在 `green_methanol_for_port_transportation` conda环境中运行
- 性能：能够处理10K+记录的数据集，处理时间<60秒
- 内存：注意大数据集的内存使用，实现分块处理
- 并发：充分利用CPU/GPU资源进行并行计算

数据处理要求：
- 输入格式：支持CSV、Excel、GeoJSON等标准格式
- 输出格式：结果必须保存在 `results/` 目录下的对应子目录
- 时间戳：所有输出文件包含时间戳 (YYYYMMDD_HHMMSS)
- 元数据：重要数据集需要包含元数据文件

代码质量要求：
- 模块化：遵循项目的模块化结构 (src/, data/, results/, tests/, logs/)
- 测试：必须包含单元测试和集成测试
- 文档：所有函数需要docstring，模块需要README
- 日志：使用Python logging模块，生成带日期的日志文件

集成要求：
- 兼容性：与现有模块 (air_port_data_process/, gis_data_scraper/, natural_gas_supply_chain_optimization/) 保持兼容
- 数据流：遵循项目的数据流模式，确保可以与其他模块数据交换
- 依赖管理：新依赖需要添加到requirements.txt

领域知识：
- 绿色甲醇：了解绿色甲醇的生产、运输、使用特性
- 航空燃料：熟悉航空燃料计算标准（BADA3模型等）
- 能源供应链：理解能源供应链优化的基本原理
- 港口物流：掌握港口运输和物流优化方法

常见陷阱：
- 坐标系统：确保地理坐标使用正确的坐标系（WGS84）
- 单位换算：注意能源单位的正确换算（kg, MJ, kWh等）
- 中文支持：确保可视化中中文字体正确显示
- 数据验证：对输入数据进行完整性和合理性检查

## 使用说明

1. **填写完整信息**：详细填写上述各个部分
2. **生成PRP**：在Claude Code中运行 `/generate-prp INITIAL.md`
3. **执行实现**：运行 `/execute-prp PRPs/your-feature-name.md`

## 示例模板

以下是一个完整示例：

```
## FEATURE:
构建一个绿色甲醇与传统航空燃料的碳排放对比分析工具。该工具应该能够：
- 读取航班数据（Excel格式）
- 计算传统燃料和绿色甲醇的碳排放
- 生成对比分析报告和可视化图表
- 输出Excel报告和PNG图表到results/目录

## EXAMPLES:
- 遵循 `examples/data_processing_pattern.py` 的数据处理模式
- 使用 `examples/test_pattern.py` 的测试结构
- 参考 `air_port_data_process/src/pybada_fuel_calculator.py` 的计算模式

## DOCUMENTATION:
- BADA3模型文档: https://www.eurocontrol.int/model/bada
- pandas文档: https://pandas.pydata.org/docs/
- matplotlib文档: https://matplotlib.org/stable/

## OTHER CONSIDERATIONS:
- 必须处理中文机场名称和城市名称
- 考虑不同机型的燃料效率差异
- 实现缓存机制以提高大数据集处理速度
- 确保结果可以导出为政府报告格式
```