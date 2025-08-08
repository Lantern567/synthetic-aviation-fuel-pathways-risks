# 功能需求示例

## FEATURE:
构建一个基于GraphHopper的绿色甲醇运输路径优化器，能够计算从天然气源头到港口的最优运输路径，并进行成本效益分析。

具体功能要求：
- 集成GraphHopper路径规划引擎，支持多种运输方式（管道、卡车、船舶）
- 实现多目标优化算法（成本最小化 + 碳排放最小化）
- 生成交互式地图可视化，显示优化后的运输网络
- 输出详细的成本分析报告和环境影响评估
- 支持实时路径调整和备选方案生成

性能要求：
- 处理500+基础设施节点的网络优化
- 计算时间 < 5分钟（包括路径规划和优化）
- 支持并行计算以提高处理速度

## EXAMPLES:
遵循项目中的现有模式：

1. **数据处理模式** (`examples/data_processing_pattern.py`)
   - 使用标准的数据读取、清理、验证、保存流程
   - 实现时间戳文件命名和结果分类存储
   - 添加数据质量检查和异常处理

2. **测试模式** (`examples/test_pattern.py`)
   - 为每个主要功能编写单元测试
   - 使用pytest框架和Mock对象
   - 包含集成测试验证端到端功能

3. **现有模块参考**:
   - `products/supply_chain_optimization/natural_gas_supply_chain_optimization/` - 供应链优化算法结构
   - `tools/graphhopper/` - GraphHopper集成模式
   - `products/gis_energy_mapping/` - GIS数据处理和可视化

## DOCUMENTATION:
相关文档和资源：

### 项目内部文档：
- `natural_gas_supply_chain_optimization/天然气供应链优化数学模型与数据流分析.md` - 优化算法理论基础
- `natural_gas_supply_chain_optimization/GRAPHHOPPER_INTEGRATION.md` - GraphHopper集成指南
- `PBR_ARCHITECTURE.md` - 项目架构规范

### 外部API和库文档：
- GraphHopper API: https://docs.graphhopper.com/
- Gurobi优化器: https://www.gurobi.com/documentation/
- PyDeck可视化: https://pydeck.gl/
- Pandas地理数据: https://geopandas.org/

### 数据源：
- 天然气管道数据：`products/supply_chain_optimization/natural_gas_supply_chain_optimization/data/integrated_gas_pipeline_price_data.csv`
- 港口位置数据：从现有数据集提取
- OSM地图数据：`china-latest.osm.pbf`

## OTHER CONSIDERATIONS:

### 技术约束：
- **环境要求**：必须在 `green_methanol_for_port_transportation` conda环境中运行
- **GraphHopper服务**：需要先启动GraphHopper服务（端口8989）
- **内存管理**：大规模路径规划可能消耗大量内存，需要实现分批处理
- **并发处理**：充分利用多核CPU进行并行路径计算

### 常见陷阱：
- GraphHopper服务启动检查：确保服务可用再开始计算
- 坐标系统一致性：确保所有地理数据使用相同的坐标系统（WGS84）
- 网络连通性验证：处理不连通的路径节点
- 优化算法收敛性：设置合理的迭代次数和收敛条件

### 输出规范：
- 所有结果文件包含时间戳：`optimization_results_YYYYMMDD_HHMMSS.csv`
- 可视化输出：PNG高分辨率图片 + HTML交互地图
- 日志记录：详细记录优化过程和性能指标
- 错误处理：友好的错误消息和恢复建议

### 领域特定要求：
- 考虑季节性因素对运输成本的影响
- 包含不同运输方式的碳排放系数
- 支持多货币成本计算和汇率转换
- 遵循港口操作的实际约束条件
