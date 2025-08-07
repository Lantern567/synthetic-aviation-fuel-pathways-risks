# 业务上下文库

这个目录包含了项目中不同业务领域的专业知识和上下文信息，用于辅助AI助手更好地理解特定业务需求。

## 业务领域分类

### 🛩️ 航空燃料业务 (`aviation_fuel_context.md`)
- pyBADA燃料计算模型
- 航空碳排放标准和计算方法
- 机型特性和燃料效率数据
- 航线规划和燃料优化

### ⛽ 供应链优化业务 (`supply_chain_context.md`)
- 天然气供应链建模
- Gurobi优化模型设计
- 成本分析和路径优化
- 时间尺度匹配问题

### 🗺️ GIS数据处理业务 (`gis_processing_context.md`)
- 中国能源基础设施数据
- GeoJSON数据处理标准
- 空间数据分析和可视化
- 坐标系统和投影变换

### 🚢 港口物流业务 (`port_operations_context.md`)
- 港口运输优化
- 绿色甲醇储运特性
- 物流成本分析
- 环境影响评估

## 使用方法

### 在PRP中引用业务上下文
```markdown
## DOCUMENTATION:
- 业务上下文：business_contexts/aviation_fuel_context.md
- 相关模块：air_port_data_process/
- 技术标准：BADA3模型文档
```

### 选择合适的上下文
根据你的功能需求，选择1-2个最相关的业务上下文：

1. **航空燃料计算** → `aviation_fuel_context.md`
2. **供应链优化** → `supply_chain_context.md` 
3. **GIS数据分析** → `gis_processing_context.md`
4. **港口物流** → `port_operations_context.md`

### 组合使用
复杂功能可能涉及多个业务领域：
```markdown
## DOCUMENTATION:
- 主要业务：business_contexts/aviation_fuel_context.md
- 辅助业务：business_contexts/supply_chain_context.md
- 数据处理：business_contexts/gis_processing_context.md
```

## 维护和更新

### 业务上下文更新原则
1. **领域专家审核**：业务变更需要相关专家确认
2. **版本控制**：重要变更记录在git历史中
3. **定期评审**：每季度检查上下文的时效性
4. **实践反馈**：根据实际开发经验调整内容

### 新增业务上下文
当发现新的业务领域时：
1. 创建对应的`{business}_context.md`文件
2. 更新本README文件的分类列表
3. 在相关模块的README中添加引用
4. 通知团队成员新上下文的可用性