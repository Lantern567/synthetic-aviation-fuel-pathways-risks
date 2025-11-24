# 天然气供应链优化 - 副产氢场景运行指南

## 目录结构

运行副产氢场景后，日志和结果会按照以下结构分类存储：

```
products/supply_chain_optimization/natural_gas_supply_chain_optimization/
├── results/
│   ├── logs/                          # 日志文件目录
│   │   ├── default/                   # 默认场景日志
│   │   │   └── ng_supply_chain_default_YYYYMMDD.log
│   │   └── byproduct_hydrogen/        # 副产氢场景日志
│   │       ├── one_step/              # 一步法日志
│   │       │   └── ng_supply_chain_byproduct_hydrogen_one_step_YYYYMMDD.log
│   │       └── two_step/              # 两步法日志
│   │           └── ng_supply_chain_byproduct_hydrogen_two_step_YYYYMMDD.log
│   │
│   ├── default/                       # 默认场景结果
│   │   ├── optimization_summary_TIMESTAMP.csv
│   │   ├── facility_decisions_TIMESTAMP.csv
│   │   └── ...
│   │
│   └── byproduct_hydrogen/            # 副产氢场景结果
│       ├── one_step/                  # 一步法结果（NG→FT合成→SAF）
│       │   ├── optimization_summary_TIMESTAMP.csv
│       │   ├── facility_decisions_TIMESTAMP.csv
│       │   ├── hydrogen_transport_plan_TIMESTAMP.csv
│       │   ├── mtj_transport_plan_TIMESTAMP.csv
│       │   └── ...
│       └── two_step/                  # 两步法结果（NG→甲醇→SAF）
│           ├── optimization_summary_TIMESTAMP.csv
│           ├── facility_decisions_TIMESTAMP.csv
│           ├── hydrogen_transport_plan_TIMESTAMP.csv
│           ├── mtj_transport_plan_TIMESTAMP.csv
│           └── ...
```

## 运行方式

### 1. 副产氢两步法（NG→甲醇→SAF）

```bash
cd /home/ljt/code_project/green_methanol_for_port_transportation-main

# 前台运行
python products/supply_chain_optimization/natural_gas_supply_chain_optimization/run_byproduct_two_step.py

# 后台运行（推荐）
nohup python products/supply_chain_optimization/natural_gas_supply_chain_optimization/run_byproduct_two_step.py > ng_two_step.log 2>&1 &
```

**配置文件**：`shared/data/NaturalGasByproductHydrogenOptimizer_config.yaml`

**日志位置**：`results/logs/byproduct_hydrogen/two_step/`

**结果位置**：`results/byproduct_hydrogen/two_step/`

---

### 2. 副产氢一步法（NG→FT合成→SAF）

```bash
cd /home/ljt/code_project/green_methanol_for_port_transportation-main

# 前台运行
python products/supply_chain_optimization/natural_gas_supply_chain_optimization/run_byproduct_one_step.py

# 后台运行（推荐）
nohup python products/supply_chain_optimization/natural_gas_supply_chain_optimization/run_byproduct_one_step.py > ng_one_step.log 2>&1 &
```

**配置文件**：`shared/data/NaturalGasByproductHydrogenOptimizer_config_one_step.yaml`

**日志位置**：`results/logs/byproduct_hydrogen/one_step/`

**结果位置**：`results/byproduct_hydrogen/one_step/`

---

### 3. 默认场景（非副产氢）

```bash
cd /home/ljt/code_project/green_methanol_for_port_transportation-main

# 前台运行
python products/supply_chain_optimization/natural_gas_supply_chain_optimization/run_optimization.py

# 后台运行
nohup python products/supply_chain_optimization/natural_gas_supply_chain_optimization/run_optimization.py > ng_default.log 2>&1 &
```

**配置文件**：使用默认配置

**日志位置**：`results/logs/default/`

**结果位置**：`results/default/`

---

## 监控运行进度

### 查看后台进程
```bash
ps aux | grep run_byproduct
```

### 实时查看日志
```bash
# 查看控制台输出日志
tail -f ng_two_step.log

# 查看文件系统日志
tail -f products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/logs/byproduct_hydrogen/two_step/ng_supply_chain_byproduct_hydrogen_two_step_*.log
```

### 检查结果文件
```bash
# 一步法结果
ls -lh products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/byproduct_hydrogen/one_step/

# 两步法结果
ls -lh products/supply_chain_optimization/natural_gas_supply_chain_optimization/results/byproduct_hydrogen/two_step/
```

---

## 配置文件说明

### 两步法 vs 一步法关键差异

| 参数 | 两步法 | 一步法 |
|------|--------|--------|
| 技术路线 | NG→甲醇→SAF | NG→FT合成→SAF |
| 工艺类型 | E-CRM+TRM | FT Direct Conversion |
| 甲醇中间体比例 | 1.2 | 无 |
| H₂消耗比例 | 0.05 | 0 |
| 催化剂成本 | 0.1 元/kg SAF | 0.06 元/kg SAF |
| 能耗 | 较高 | 较低 |

---

## 输出文件说明

每次运行都会生成以下文件（包含时间戳）：

1. **optimization_summary_TIMESTAMP.csv** - 优化汇总结果
2. **facility_decisions_TIMESTAMP.csv** - 设施建设决策
3. **hydrogen_transport_plan_TIMESTAMP.csv** - 氢气运输计划
4. **mtj_transport_plan_TIMESTAMP.csv** - MTJ运输计划
5. **infrastructure_summary_TIMESTAMP.csv** - 基础设施汇总
6. **inventory_levels_TIMESTAMP.csv** - 库存水平
7. **complete_solution_TIMESTAMP.json** - 完整求解方案（JSON格式）
8. **airports_TIMESTAMP.csv** - 机场数据
9. **renewable_energy_plants_TIMESTAMP.csv** - 可再生能源电厂数据
10. **lng_terminals_TIMESTAMP.csv** - LNG接收站数据
11. **ng_pipelines_TIMESTAMP.csv** - 天然气管道数据

---

## 常见问题

### Q: 为什么日志/结果没有出现在预期位置？

A: 确保在初始化 `NaturalGasSupplyChainOptimizer` 时传入了正确的 `log_subdir` 参数：
- 副产氢一步法: `log_subdir='byproduct_hydrogen/one_step'`
- 副产氢两步法: `log_subdir='byproduct_hydrogen/two_step'`
- 默认场景: `log_subdir='default'`

### Q: 如何区分不同运行的结果？

A: 所有文件名都包含时间戳（YYYYMMDD_HHMMSS），同时按场景分目录存储。

### Q: 两步法和一步法应该选择哪个？

A:
- **两步法**：技术成熟度高，通过甲醇中间体，适合现有甲醇制SAF技术路线
- **一步法**：直接FT合成，工艺更简洁，能耗更低，但技术难度较高

建议两种都运行，对比经济性和碳排放结果。

### Q: 如何停止后台运行？

```bash
# 查找进程ID
ps aux | grep run_byproduct

# 停止进程
kill <PID>

# 强制停止
kill -9 <PID>
```

---

## 技术支持

如有问题，请检查：
1. 日志文件中的错误信息
2. Gurobi许可证是否有效
3. GraphHopper服务是否启动（如果启用路径规划）
4. 输入数据文件是否存在

---

**最后更新**: 2025-11-23
**版本**: 1.0.0
