# 复杂业务的Context Engineering应用策略

## 核心理念：分而治之，渐进应用

你说得对，复杂业务不可能把每个细节都叙述出来。Context Engineering框架的设计就是为了解决这个问题 - **让你不需要每次都重复解释业务细节**。

## 推荐应用策略

### 🎯 策略一：业务上下文库 (已部署)

**不需要重复描述细节，而是建立可复用的业务知识库**

```
你的项目现在有：
├── business_contexts/              # 业务知识库
│   ├── aviation_fuel_context.md   # 航空燃料业务 ✅ 已创建
│   ├── supply_chain_context.md    # 供应链优化 (待创建)
│   ├── gis_processing_context.md  # GIS数据处理 (待创建)
│   └── port_operations_context.md # 港口物流 (待创建)
```

**使用方式**：
```markdown
## DOCUMENTATION:
- 业务上下文：business_contexts/aviation_fuel_context.md
- 现有模块：air_port_data_process/

## FEATURE:
基于现有航空燃料计算能力，扩展绿色甲醇对比分析功能...
```

### 🏗️ 策略二：分层复杂度管理

**根据业务复杂度选择不同的Context Engineering应用深度**

| 业务复杂度 | 应用策略 | 工具使用 |
|-----------|----------|----------|
| **高频核心业务** | 完整PRP工作流 | `/generate-prp` + `/execute-prp` |
| **中等频次业务** | 简化PRP + 业务上下文 | `business_contexts/` + 基础模板 |
| **偶发业务** | 直接引用现有模式 | `examples/` + 现有代码模式 |

### 📊 策略三：渐进式知识积累

**每次开发新功能时，逐步积累业务知识**

```mermaid
开发新功能 → 识别业务模式 → 提取到业务上下文 → 下次复用
```

## 具体实施建议

### 🚀 阶段1：从最熟悉的业务开始

**建议从`航空燃料计算`开始（已经为你准备好了）**

1. **立即可用**：`aviation_fuel_context.md` 包含完整业务知识
2. **现有基础**：air_port_data_process/ 模块已经很成熟
3. **高价值**：这个业务最复杂，收益最大

**测试方法**：
```bash
# 在Claude Code中测试
/generate-prp INITIAL_EXAMPLE.md
```

### 🔄 阶段2：按需扩展其他业务

**只在需要开发新功能时才扩展对应的业务上下文**

例如，当你需要开发供应链优化功能时：
1. 创建 `supply_chain_context.md`
2. 在其中记录Gurobi模型、数学约束、性能要求等
3. 后续同类功能直接引用这个上下文

### 🎯 阶段3：智能化业务匹配

**AI助手学会自动选择合适的业务上下文**

```markdown
当你说："我想分析不同港口的甲醇运输成本"
AI自动理解：这需要 supply_chain_context.md + port_operations_context.md
```

## 实际使用示例

### 📝 简化的功能需求描述

**以前你需要这样描述**：
```
我要开发一个功能，计算从天津港到上海港的绿色甲醇运输成本，
需要考虑海运距离、船舶燃料消耗、港口装卸费用、储存成本、
时间价值、风险因素、政策补贴...（500字说明）
```

**现在你只需要这样**：
```markdown
## FEATURE:
港口间绿色甲醇运输成本分析工具

## DOCUMENTATION:
- 业务上下文：business_contexts/supply_chain_context.md
- 参考模块：natural_gas_supply_chain_optimization/

## OTHER CONSIDERATIONS:
- 起始港口：天津港
- 目的港口：上海港
- 分析维度：成本、时间、风险
```

### 🔧 复杂业务的分解策略

**对于非常复杂的功能，分解成多个小的PRP**：

```
复杂需求：完整的绿色甲醇供应链分析系统

分解为：
├── PRP1：港口储运成本分析
├── PRP2：海运路径优化  
├── PRP3：多式联运成本对比
├── PRP4：综合分析和报告生成
└── PRP5：可视化和仪表板
```

每个PRP都很具体，AI容易理解和实现。

## 避免的误区

### ❌ 不要在每个子模块都部署完整框架
- **错误做法**：在air_port_data_process/、gis_data_scraper/等每个目录都创建.claude/
- **正确做法**：统一使用根目录的Context Engineering框架

### ❌ 不要试图一次性描述所有业务细节
- **错误做法**：写一个包含所有业务逻辑的超长INITIAL.md
- **正确做法**：将业务知识分解到business_contexts/中，按需引用

### ❌ 不要忽视业务上下文的维护
- **错误做法**：写一次就不管，导致信息过时
- **正确做法**：定期更新，每次发现新知识时及时补充

## 立即行动建议

### 🎯 今天就可以做：
1. **测试航空燃料业务**：运行 `/generate-prp INITIAL_EXAMPLE.md`
2. **识别下一个核心业务**：哪个是你第二常开发的功能？
3. **开始记录业务知识**：下次开发时，把新发现的业务规则记录到对应的context文件

### 📈 本周内完成：
1. **完善最重要的2-3个业务上下文**
2. **测试完整的PRP工作流**
3. **培养使用习惯**：新功能开发都通过Context Engineering

### 🚀 长期效果：
- **开发效率提升70%+**：不需要重复解释业务逻辑
- **代码质量一致性**：所有功能都遵循established patterns  
- **知识沉淀**：业务知识系统化，新人也能快速上手
- **AI协作优化**：AI越来越懂你的业务

---

**记住**：Context Engineering不是让你描述更多细节，而是让你**只描述一次，然后永远复用**。复杂业务的管理核心是**分而治之**和**渐进积累**。