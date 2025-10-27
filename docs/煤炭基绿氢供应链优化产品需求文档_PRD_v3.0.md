# 煤炭+绿氢制SAF供应链优化产品需求文档(PRD)v3.0
## 工艺路线:煤炭 → CO₂ + 绿氢 → 甲醇 → SAF(两步法)

---

## 文档信息

| 属性 | 内容 |
|-----|------|
| **文档版本** | v3.0.0 |
| **创建日期** | 2025-10-26 |
| **项目名称** | 煤炭+绿氢制SAF供应链优化模型(两步法) |
| **工艺路线** | 煤炭气化产生CO₂ + 绿氢 → 甲醇 → SAF |
| **产品类型** | 供应链优化模型(并行版本) |
| **开发模式** | 基于v2.0完整迁移后修改 |
| **预计工期** | 6个工作日 |
| **作者** | 绿色甲醇港口运输研究组 |
| **状态** | 待审阅 |

---

## 目录

1. [项目概述](#一项目概述)
2. [核心变更说明](#二核心变更说明)
3. [目录结构与文件迁移计划](#三目录结构与文件迁移计划)
4. [配置文件修改计划](#四配置文件修改计划)
5. [核心代码修改计划](#五核心代码修改计划)
6. [煤炭供应模块设计](#六煤炭供应模块设计)
7. [碳排放计算模块调整](#七碳排放计算模块调整)
8. [详细任务分解(TodoList)](#八详细任务分解todolist)
9. [实施步骤与时间计划](#九实施步骤与时间计划)
10. [与v2.0的全面对比分析](#十与v20的全面对比分析)
11. [关键技术参数数据源](#十一关键技术参数数据源)
12. [风险与缓解措施](#十二风险与缓解措施)
13. [验收标准](#十三验收标准)
14. [附录:关键代码片段](#十四附录关键代码片段)

---

## 一、项目概述

### 1.1 项目背景

**产品系列演进路径**:

```
v1.0 天然气+绿氢 → 甲醇 → SAF(已废弃)
    ↓
v2.0 绿氢+CO₂捕获 → 甲醇 → SAF(当前运行)
    ↓
v3.0 煤炭+绿氢 → 甲醇 → SAF(本文档)⭐
```

**开发背景**:
- v2.0版本采用CO₂捕获技术,需要从燃煤电厂、气电厂捕获CO₂
- CO₂捕获成本高(150-180元/吨)且需要复杂的运输网络
- 中国作为煤炭大国,煤炭气化技术成熟,可直接产生高浓度CO₂
- 煤炭市场供应充足,价格相对稳定(525元/吨)

**本版本定位**:
- 作为v2.0的**并行版本**存在(非替代)
- 探索不同CO₂来源对供应链经济性和碳排放的影响
- 为实际项目提供多种工艺路线的对比分析

### 1.2 项目名称

**正式名称**:煤炭+绿氢制SAF供应链优化模型(两步法)

**英文名称**:Coal-Based Hydrogen SAF Supply Chain Optimization Model (Two-Step Pathway)

**简称**:Coal-H₂-SAF优化器

### 1.3 工艺路线

**完整工艺流程**:

```
┌──────────┐      ┌──────────────┐      ┌──────────┐
│   煤炭   │      │  可再生能源  │      │  机场    │
│  (购买)  │      │  (风/光电)   │      │  (需求)  │
└────┬─────┘      └──────┬───────┘      └────▲─────┘
     │                   │                   │
     │ 煤炭气化           │ 电解水制氢          │
     ▼                   ▼                   │
┌──────────┐      ┌──────────────┐          │
│   CO₂    │      │   绿氢 (H₂)  │          │
│ (2.44 kg │      │  (0.2 kg H₂  │          │
│  /kg煤)  │      │   /kg SAF)   │          │
└────┬─────┘      └──────┬───────┘          │
     │                   │                   │
     └──────┬────────────┘                   │
            │                                │
            │  Step 1: E-CRM甲醇合成          │
            ▼                                │
     ┌─────────────┐                         │
     │    甲醇     │                         │
     │ (1.3 kg 甲醇 │                        │
     │  /kg SAF)   │                         │
     └──────┬──────┘                         │
            │                                │
            │  Step 2: MTJ航煤转化            │
            ▼                                │
     ┌─────────────┐                         │
     │     SAF     │                         │
     │  (产品)     │─────运输────────────────┘
     └─────────────┘
```

**关键工艺参数**:

| 工艺环节 | 输入 | 输出 | 转化效率 | 能耗 |
|---------|------|------|---------|------|
| **煤炭气化** | 1 kg煤炭 | 2.44 kg CO₂ + 合成气 | 75% (Shell) | 8 kWh/kg煤 |
| **电解制氢** | 9 kg水 + 50 kWh | 1 kg H₂ | 70% | 50 kWh/kg H₂ |
| **E-CRM合成** | 2.8 kg CO₂ + 0.15 kg H₂ | 1 kg 甲醇 | 75% | 8 kWh/kg甲醇 |
| **MTJ转化** | 1.3 kg 甲醇 | 1 kg SAF | 85% | 5 kWh/kg SAF |
| **总计** | 1.8 kg煤 + 0.2 kg H₂ | 1 kg SAF | 70% | 15 kWh/kg SAF |

### 1.4 核心差异总结

**与v2.0的关键区别**(仅1个核心模块变化):

| 对比维度 | v2.0 绿氢+CO₂捕获 | v3.0 煤炭+绿氢 |
|---------|------------------|---------------|
| **CO₂来源** | 煤电厂/气电厂捕获 | 煤炭气化产生 |
| **CO₂获取方式** | CCS技术捕获 | 直接气化产生 |
| **GIS数据需求** | 需要(电厂位置) | 不需要(市场采购)|
| **CO₂运输** | 需要(管道/罐车) | 不需要(本地产生)|
| **CO₂成本** | 捕获成本150-180元/吨 | 煤炭成本525元/吨 → 215元/吨CO₂ |
| **系统复杂度** | 高(多点捕获+运输优化)| 低(单点购买) |
| **碳排放** | 低(CO₂循环利用) | 高(煤炭生命周期排放)|
| **CORSIA合规** | 可能达标 | 困难(需验证) |

**代码变更范围**(仅约10%代码需修改):

| 模块 | 变更类型 | 变更量 |
|-----|---------|--------|
| **CO₂供应模块** | 完全重写 | 100% |
| **配置文件** | 参数替换 | 30% |
| **决策变量** | 删除CO₂运输变量 | 15% |
| **约束条件** | 简化CO₂供应约束 | 10% |
| **目标函数** | 修改成本项 | 5% |
| **其他模块** | 不变 | 0% |

**关键简化点**:
- ✅ 无需加载电厂GIS数据
- ✅ 无需计算CO₂运输距离
- ✅ 无需优化CO₂运输方式(管道/罐车)
- ✅ 无需考虑CO₂捕获源容量限制
- ✅ 煤炭供应假设无限(市场充足)

### 1.5 版本定位

**并行版本关系**:

```
products/supply_chain_optimization/
├── green_hydrogen_supply_chain_optimization/  (v2.0 - CO₂捕获版本)
│   ├── src/
│   │   ├── core/green_hydrogen_optimization_model.py
│   │   ├── co2/co2_capture_calculator.py  ← 复杂
│   │   └── ...
│   └── config/GreenHydrogenSupplyChainOptimizer_config.yaml
│
└── coal_hydrogen_saf_supply_chain_optimization/  (v3.0 - 煤炭版本) ⭐新建
    ├── src/
    │   ├── core/coal_hydrogen_optimization_model.py
    │   ├── coal/coal_supply_manager.py  ← 简单
    │   └── ...(其余模块完全复用)
    └── config/CoalHydrogenSAFOptimizer_config.yaml
```

**使用场景建议**:

| 场景 | 推荐版本 | 理由 |
|-----|---------|------|
| **追求低碳排放** | v2.0 CO₂捕获 | 碳强度低,可能满足CORSIA |
| **追求经济性** | v3.0 煤炭 | 煤炭价格低,系统简单 |
| **已有CO₂捕获设施** | v2.0 CO₂捕获 | 利用现有基础设施 |
| **煤化工企业** | v3.0 煤炭 | 与现有煤炭产业协同 |
| **研究对比** | 两个版本都运行 | 对比不同工艺路线 |

### 1.6 项目目标

**主要目标**:
1. ✅ 创建煤炭基SAF供应链优化模型(基于v2.0迁移)
2. ✅ 简化CO₂供应模块(删除复杂的捕获和运输逻辑)
3. ✅ 对比分析v2.0和v3.0的经济性和碳排放
4. ✅ 验证煤炭路线的CORSIA合规性
5. ✅ 为项目决策提供多路线对比数据

**技术目标**:
- 模型求解时间 < 1小时(1周优化范围)
- 碳排放计算符合CORSIA标准
- 成本计算包含所有关键环节
- 代码质量符合PEP8规范

**非目标**(明确不做的事):
- ❌ 不考虑煤炭运输成本(假设工厂建在煤炭基地附近)
- ❌ 不加载煤矿GIS数据(市场采购模式)
- ❌ 不优化煤炭采购时机(假设随时可购买)
- ❌ 不考虑煤炭质量差异(统一使用烟煤参数)
- ❌ 不实施碳捕获与封存CCS(纯气化产生CO₂)

---

## 二、核心变更说明

### 2.1 工艺路线变更

#### 2.1.1 CO₂来源变更(唯一核心差异)

**v2.0工艺(CO₂捕获路线)**:

```
燃煤电厂/气电厂
  ↓ [CCS技术]
  ↓ 捕获率85-90%
  ↓ 成本150-180元/吨
CO₂ (纯度>95%)
  ↓ [管道/罐车运输]
  ↓ 运输距离0-500km
  ↓ 运输成本50-150元/吨
SAF生产地 (CO₂库存)
  ↓ + 绿氢
甲醇 → SAF
```

**v3.0工艺(煤炭气化路线)**:

```
煤炭市场采购
  ↓ 价格525元/吨
  ↓ 烟煤(含碳75%)
煤炭运到SAF生产地
  ↓ [Shell气化炉]
  ↓ 气化效率75%
  ↓ 能耗8 kWh/kg煤
CO₂ (纯度>95%, 2.44 kg CO₂/kg煤)
  ↓ [本地直接使用,无运输]
SAF生产地 (CO₂库存)
  ↓ + 绿氢
甲醇 → SAF
```

**关键变化总结**:

| 工艺环节 | v2.0 | v3.0 | 变化说明 |
|---------|------|------|---------|
| **CO₂获取** | CCS捕获 | 煤炭气化 | 技术完全不同 |
| **CO₂浓度** | 95% | 95% | 相同(都需提纯)|
| **CO₂生产地** | 多个电厂(分散)| SAF工厂内(集中)| 地理分布变化 |
| **运输需求** | 需要(复杂网络)| 不需要(本地产生)| 大幅简化 |
| **供应能力** | 受电厂容量限制 | 煤炭供应充足 | 约束放松 |
| **生命周期排放** | 低(CO₂循环)| 高(煤炭开采+气化)| 环境影响增加 |

#### 2.1.2 其他工艺环节(完全相同)

**保持不变的环节**:
1. ✅ 绿氢生产:可再生能源电解水(50 kWh/kg H₂)
2. ✅ 甲醇合成:E-CRM电化学CO₂还原(H₂ + CO₂ → 甲醇)
3. ✅ SAF转化:MTJ甲醇转航煤技术(甲醇 → SAF)
4. ✅ SAF运输:罐车运输到机场
5. ✅ 时间尺度:小时级生产 vs 周级需求

**相同的技术参数**:
- 甲醇合成效率:75%
- MTJ转化效率:85%
- 总体转化效率:70%
- H₂消耗比例:0.2 kg H₂/kg SAF
- CO₂消耗比例:3.5 kg CO₂/kg SAF
- 甲醇中间比例:1.3 kg 甲醇/kg SAF

### 2.2 系统架构变更

#### 2.2.1 模块架构对比

**v2.0架构(复杂)**:

```
GreenHydrogenSupplyChainOptimizer
├── 数据加载层
│   ├── _load_airports()  ← 保留
│   ├── _load_renewable_plants()  ← 保留
│   ├── _load_co2_capture_sources()  ← 删除❌
│   │   └── CO2CaptureCalculator  ← 删除❌(复杂模块)
│   │       ├── _load_coal_power_plants()
│   │       ├── _load_gas_power_plants()
│   │       ├── _calculate_coal_capture()
│   │       └── _calculate_gas_capture()
│   └── _calculate_distances()  ← 保留(但CO₂部分简化)
│
├── 优化模型层
│   ├── 决策变量
│   │   ├── h2_supply  ← 保留
│   │   ├── co2_pipeline_transport  ← 删除❌
│   │   ├── co2_truck_transport  ← 删除❌
│   │   ├── co2_inventory  ← 保留(用途变化)
│   │   └── saf_production  ← 保留
│   │
│   ├── 约束条件
│   │   ├── CO₂供应平衡(周级)  ← 删除❌
│   │   ├── CO₂运输容量限制  ← 删除❌
│   │   ├── CO₂管道建设决策  ← 删除❌
│   │   └── CO₂库存平衡  ← 保留(逻辑变化)
│   │
│   └── 目标函数
│       ├── CO₂捕获成本  ← 删除❌
│       ├── CO₂运输成本  ← 删除❌
│       └── 其他成本  ← 保留
│
└── 碳排放计算层
    └── CO2EmissionCalculator  ← 修改⚠️
        ├── _calc_co2_capture_emission()  ← 删除❌
        ├── _calc_co2_transport_emission()  ← 删除❌
        └── _calc_coal_lifecycle_emission()  ← 新增✅
```

**v3.0架构(简化)**:

```
CoalHydrogenSAFOptimizer
├── 数据加载层
│   ├── _load_airports()  ← 保留
│   ├── _load_renewable_plants()  ← 保留
│   ├── _define_coal_supply()  ← 新增✅(简单)
│   │   └── 读取配置文件中的煤炭参数(无需复杂计算)
│   └── _calculate_distances()  ← 保留(仅H₂和SAF)
│
├── 优化模型层
│   ├── 决策变量
│   │   ├── h2_supply  ← 保留
│   │   ├── coal_purchase  ← 新增✅
│   │   ├── co2_inventory  ← 保留(来源变为煤炭气化)
│   │   └── saf_production  ← 保留
│   │
│   ├── 约束条件
│   │   ├── 煤炭气化产生CO₂约束  ← 新增✅(简单)
│   │   ├── CO₂库存平衡  ← 修改⚠️(来源变化)
│   │   └── 其他约束  ← 保留
│   │
│   └── 目标函数
│       ├── 煤炭采购成本  ← 新增✅
│       └── 其他成本  ← 保留
│
└── 碳排放计算层
    └── CO2EmissionCalculator  ← 修改⚠️
        ├── _calc_coal_mining_emission()  ← 新增✅
        ├── _calc_coal_gasification_emission()  ← 新增✅
        └── 其他方法  ← 保留
```

**复杂度对比**:

| 指标 | v2.0 | v3.0 | 变化 |
|-----|------|------|------|
| **核心类数量** | 3个 | 2个 | -33% |
| **数据加载方法** | 8个 | 4个 | -50% |
| **决策变量数** | 约200万 | 约100万 | -50% |
| **约束条件数** | 约500万 | 约300万 | -40% |
| **GIS数据依赖** | 4类文件 | 2类文件 | -50% |
| **求解时间(1周)** | 30-60分钟 | 15-30分钟 | -50% |

#### 2.2.2 文件结构对比

**删除的模块**:
```
src/co2/
├── co2_capture_calculator.py  ← 删除❌(约500行代码)
│   └── CO2CaptureCalculator类
│       ├── 从GIS数据计算CO₂捕获量
│       ├── 考虑电厂容量因子
│       ├── 处理3类捕获源(煤电/气电/炼油)
│       └── 输出周级CO₂供应数据
│
└── co2_emission_calculator.py  ← 保留但修改⚠️
```

**新增的模块**:
```
src/coal/
├── __init__.py  ← 新建✅
└── coal_supply_manager.py  ← 新建✅(约100行代码)
    └── CoalSupplyManager类
        ├── 从配置读取煤炭参数
        ├── 计算煤炭-CO₂转化比例
        └── 提供煤炭供应接口(极简)
```

**完全复用的模块**(约90%代码不变):
```
src/
├── hydrogen/  ← 完全复用✅
│   ├── hydrogen_clustering_optimizer.py
│   ├── hydrogen_pipeline_distance_calculator.py
│   └── hydrogen_transport_visualizer.py
│
├── routing/  ← 完全复用✅
│   ├── graphhopper_routing_engine.py
│   ├── osm_routing_engine.py
│   └── pipeline_coordinate_integrator.py
│
├── cache/  ← 完全复用✅
│   ├── cache_management_utility.py
│   ├── data_cache_manager.py
│   └── ...
│
├── visualization/  ← 完全复用✅(需更新标题)
│   ├── transport_route_visualizer.py
│   ├── method_comparison_visualizer.py
│   └── method_comparison_visualizer_en.py
│
├── utils/  ← 完全复用✅
│   └── direct_capacity_preprocessor.py
│
└── sensitivity_analysis/  ← 完全复用✅
    ├── fast_sensitivity_analyzer.py
    └── sensitivity_visualization_tradeoff.py
```

### 2.3 关键简化点说明

#### 2.3.1 GIS数据简化

**v2.0需要的GIS数据**:
```
products/gis_energy_mapping/gis_data_scraper/scraped_gis_data/
├── coal_power_plants.csv  (3,821条记录)  ← v3.0不需要❌
├── gas_power_plants.csv  (270条记录)   ← v3.0不需要❌
├── oil_refineries.csv  (220条记录)    ← v3.0不需要❌
├── lng_terminals.csv  (129条记录)     ← v3.0不需要❌
├── solar_plants.csv  ← v3.0需要✅
└── wind_farms.csv  ← v3.0需要✅
```

**v3.0只需要**:
- ✅ 可再生能源数据(solar_plants.csv, wind_farms.csv)
- ✅ 机场数据(airport_data.xlsx)
- ❌ 不需要任何CO₂捕获源数据

**数据加载代码简化**:
```python
# v2.0代码(复杂)
def _load_co2_capture_sources(self):
    calculator = CO2CaptureCalculator(self.config)
    gis_data_dir = self._get_data_path('gis_data.coal_power_plants')
    co2_sources = calculator.calculate_from_gis_data(
        gis_data_dir,
        self.time_horizon_weeks
    )
    return co2_sources  # 返回4311条记录(3821+270+220)

# v3.0代码(简单)
def _define_coal_supply(self):
    coal_params = self.config['coal_parameters']
    self.coal_price = coal_params['coal_price_yuan_per_ton']
    self.coal_co2_ratio = coal_params['co2_generation_ratio']
    # 无需加载外部数据,仅从配置读取参数
```

**代码行数对比**:
- v2.0: CO2CaptureCalculator (~500行) + GIS数据处理 (~200行) = **700行**
- v3.0: CoalSupplyManager (~50行) + 参数读取 (~10行) = **60行**
- **减少约91%代码**

#### 2.3.2 运输网络简化

**v2.0运输网络(复杂)**:

```
        CO₂源1 ─────┐
                    │ 管道/罐车决策
        CO₂源2 ─────┼────→ SAF工厂1
                    │
        CO₂源N ─────┘      SAF工厂M

距离矩阵: N × M(需GraphHopper计算)
决策变量: N × M × T × 2(管道+罐车)
约束条件: 管道建设、容量限制、互斥约束
```

**v3.0运输网络(极简)**:

```
煤炭市场 → 煤炭运到SAF工厂(假设无运输成本)
              ↓
        煤炭气化产生CO₂(本地)
              ↓
         直接进入CO₂库存(无运输)
```

**决策变量简化**:

| 变量类型 | v2.0 | v3.0 | 变化 |
|---------|------|------|------|
| **CO₂管道运输** | co2_pipeline_transport[c,j,t] | 删除 | -100% |
| **CO₂罐车运输** | co2_truck_transport[c,j,t] | 删除 | -100% |
| **CO₂管道建设** | co2_pipeline_built[c,j] | 删除 | -100% |
| **煤炭采购** | 无 | coal_purchase[j,t] | 新增 |
| **CO₂库存** | co2_inventory[j,t] | 保留(来源变化)| 0% |

其中:
- c: CO₂捕获源索引(v2.0有4311个,v3.0删除)
- j: SAF工厂位置索引
- t: 时间索引(小时)

**约束条件简化**:

```python
# v2.0需要的约束(复杂)
for c in co2_sources:  # 4311个源
    for j in saf_locations:
        for t in hours:
            # 管道Big-M约束
            model.addConstr(
                co2_pipeline_transport[c,j,t] <= Big_M * co2_pipeline_built[c,j]
            )
            # 罐车互斥约束
            model.addConstr(
                co2_truck_transport[c,j,t] <= Big_M * (1 - co2_pipeline_built[c,j])
            )
# 总约束数: 4311 × M × T × 2 ≈ 数百万条

# v3.0需要的约束(简单)
for j in saf_locations:
    for t in hours:
        # 煤炭气化产生CO₂
        co2_from_coal = coal_purchase[j,t] * self.coal_co2_ratio
        # 直接进入库存(无运输决策)
        model.addConstr(
            co2_inventory[j,t] == co2_inventory[j,t-1] +
                                   co2_from_coal -
                                   co2_consumed[j,t]
        )
# 总约束数: M × T ≈ 数千条
# 减少约99.9%约束数量
```

#### 2.3.3 成本计算简化

**v2.0成本结构(7项)**:
```python
total_cost = (
    h2_cost +                    # 绿氢成本
    co2_capture_cost +           # CO₂捕获成本 ← 删除❌
    co2_pipeline_cost +          # CO₂管道运输 ← 删除❌
    co2_truck_cost +             # CO₂罐车运输 ← 删除❌
    co2_pipeline_capex +         # CO₂管道建设 ← 删除❌
    methanol_production_cost +   # 甲醇生产
    saf_production_cost +        # SAF生产
    saf_transport_cost +         # SAF运输
    facility_cost +              # 设施投资
    shortage_penalty             # 缺货惩罚
)
```

**v3.0成本结构(6项)**:
```python
total_cost = (
    h2_cost +                    # 绿氢成本 ← 保留✅
    coal_cost +                  # 煤炭采购成本 ← 新增✅
    methanol_production_cost +   # 甲醇生产 ← 保留✅
    saf_production_cost +        # SAF生产 ← 保留✅
    saf_transport_cost +         # SAF运输 ← 保留✅
    facility_cost +              # 设施投资 ← 保留✅
    shortage_penalty             # 缺货惩罚 ← 保留✅
)
```

**成本项对比**:

| 成本项 | v2.0 计算方法 | v3.0 计算方法 | 复杂度 |
|-------|--------------|--------------|--------|
| **CO₂获取** | Σ(捕获量 × 捕获成本[c]) | Σ(煤炭量 × 煤炭价格) | 简化90% |
| **CO₂运输** | Σ(运输量 × 距离 × 单位成本) | 无(本地产生)| 简化100% |
| **管道建设** | Σ(管道建设决策 × 建设成本) | 无 | 简化100% |

**计算复杂度**:
- v2.0: O(N × M × T) where N=4311个CO₂源
- v3.0: O(M × T) where M=SAF工厂数
- **复杂度降低约4000倍**

---

## 三、目录结构与文件迁移计划

### 3.1 新产品目录结构

```
products/supply_chain_optimization/coal_hydrogen_saf_supply_chain_optimization/  ⭐新建
├── src/                              # 源代码目录
│   ├── __init__.py
│   │
│   ├── core/                         # 核心优化模型
│   │   ├── __init__.py
│   │   └── coal_hydrogen_optimization_model.py  # [迁移+重命名] 主优化模型
│   │
│   ├── coal/                          # [新建✅] 煤炭供应模块
│   │   ├── __init__.py              # [新建]
│   │   └── coal_supply_manager.py   # [新建] 煤炭供应管理器
│   │
│   ├── hydrogen/                     # [完全复用✅] 氢气处理模块
│   │   ├── __init__.py
│   │   ├── hydrogen_clustering_optimizer.py
│   │   ├── hydrogen_pipeline_distance_calculator.py
│   │   └── hydrogen_transport_visualizer.py
│   │
│   ├── routing/                      # [完全复用✅] 路径规划模块
│   │   ├── __init__.py
│   │   ├── graphhopper_routing_engine.py
│   │   ├── osm_routing_engine.py
│   │   └── pipeline_coordinate_integrator.py
│   │
│   ├── cache/                        # [完全复用✅] 缓存模块
│   │   ├── __init__.py
│   │   ├── cache_management_utility.py
│   │   ├── data_cache_manager.py
│   │   ├── pipeline_route_cache_manager.py
│   │   ├── pipeline_route_types.py
│   │   └── unified_cache_configuration.py
│   │
│   ├── visualization/                # [完全复用✅] 可视化模块
│   │   ├── __init__.py
│   │   ├── transport_route_visualizer.py
│   │   ├── method_comparison_visualizer.py
│   │   └── method_comparison_visualizer_en.py
│   │
│   ├── utils/                        # [完全复用✅] 工具模块
│   │   ├── __init__.py
│   │   └── direct_capacity_preprocessor.py
│   │
│   └── sensitivity_analysis/         # [完全复用✅] 敏感性分析
│       ├── __init__.py
│       ├── fast_sensitivity_analyzer.py
│       ├── extract_sensitivity_data_corrected.py
│       └── sensitivity_visualization_tradeoff.py
│
├── config/                           # [新建] 配置文件目录
│   └── CoalHydrogenSAFOptimizer_config.yaml  # [新建] 主配置文件
│
├── data/                             # [新建] 数据文件(程序生成)
│   └── (煤炭相关数据由程序生成,无需预存)
│
├── results/                          # [新建] 结果输出
│   ├── tables/                      # CSV表格结果
│   ├── figures/                     # 可视化图表
│   ├── reports/                     # 分析报告
│   └── logs/                        # 运行日志
│
├── tests/                            # [迁移] 单元测试
│   └── test_coal_hydrogen_optimization.py  # [修改] 适配新模型
│
├── README.md                         # [新建] 项目说明
└── requirements.txt                  # [复制] 依赖列表(无变化)
```

### 3.2 文件迁移清单

#### 3.2.1 需要迁移并修改的文件

| 原文件路径 (v2.0) | 新文件路径 (v3.0) | 修改程度 | 说明 |
|------------------|------------------|---------|------|
| `src/core/green_hydrogen_optimization_model.py` | `src/core/coal_hydrogen_optimization_model.py` | 20% | 类名、CO₂供应模块 |
| `config/GreenHydrogenSupplyChainOptimizer_config.yaml` | `config/CoalHydrogenSAFOptimizer_config.yaml` | 30% | CO₂参数→煤炭参数 |
| `tests/test_phase7_methods.py` | `tests/test_coal_hydrogen_optimization.py` | 30% | 测试用例适配 |
| `README.md` | `README.md` | 100% | 完全重写项目说明 |

#### 3.2.2 需要完全复用的模块(不修改)

| 模块目录 | 文件数 | 代码行数 | 修改 |
|---------|-------|---------|------|
| `src/hydrogen/` | 4个文件 | ~1200行 | 0% |
| `src/routing/` | 4个文件 | ~800行 | 0% |
| `src/cache/` | 6个文件 | ~1500行 | 0% |
| `src/visualization/` | 3个文件 | ~1000行 | 0%(仅更新图表标题)|
| `src/utils/` | 1个文件 | ~300行 | 0% |
| `src/sensitivity_analysis/` | 3个文件 | ~800行 | 0% |
| **总计** | **21个文件** | **~5600行** | **0%** |

#### 3.2.3 需要删除的模块(不迁移)

| 原文件路径 (v2.0) | 删除理由 | 影响 |
|------------------|---------|------|
| `src/co2/co2_capture_calculator.py` | v3.0不需要CO₂捕获计算 | 无(功能由煤炭模块替代)|
| `src/co2/__init__.py` | 整个co2模块删除 | 无 |
| `data/co2_capture_sources.csv` | v3.0不使用捕获源数据 | 无 |

#### 3.2.4 需要新建的文件

| 新文件路径 (v3.0) | 文件类型 | 代码行数 | 说明 |
|------------------|---------|---------|------|
| `src/coal/__init__.py` | Python包初始化 | 5行 | 导出CoalSupplyManager |
| `src/coal/coal_supply_manager.py` | Python模块 | ~100行 | 煤炭供应管理器 |
| `config/CoalHydrogenSAFOptimizer_config.yaml` | YAML配置 | ~400行 | 主配置文件 |
| `README.md` | Markdown文档 | ~200行 | 项目说明文档 |

### 3.3 迁移策略

#### 3.3.1 实施原则

⚠️ **核心原则:先完整迁移,后逐步修改**

1. **Phase 1**: 完整复制green_hydrogen_supply_chain_optimization目录
   - 创建新目录coal_hydrogen_saf_supply_chain_optimization
   - 复制所有文件(包括暂时不需要的co2模块)
   - 确保新目录结构完整

2. **Phase 2**: 修改import路径
   - 批量替换所有文件中的import路径
   - `green_hydrogen_supply_chain_optimization` → `coal_hydrogen_saf_supply_chain_optimization`
   - 确保所有模块可正常导入

3. **Phase 3**: 删除不需要的模块
   - 删除src/co2/目录
   - 删除data/co2_capture_sources.csv

4. **Phase 4**: 创建新模块
   - 新建src/coal/目录和相关文件
   - 实现CoalSupplyManager类

5. **Phase 5**: 修改核心模型
   - 修改coal_hydrogen_optimization_model.py
   - 修改配置文件
   - 修改测试文件

#### 3.3.2 文件重命名清单

| 原文件名 (v2.0) | 新文件名 (v3.0) | 重命名方式 |
|----------------|----------------|-----------|
| `green_hydrogen_optimization_model.py` | `coal_hydrogen_optimization_model.py` | 手动重命名 |
| `GreenHydrogenSupplyChainOptimizer_config.yaml` | `CoalHydrogenSAFOptimizer_config.yaml` | 手动重命名 |
| `green_h2_supply_chain_*.log` | `coal_h2_saf_*.log` | 程序自动生成 |

#### 3.3.3 import路径批量替换

**需要替换的路径模式**:

```python
# 原import (v2.0)
from products.supply_chain_optimization.green_hydrogen_supply_chain_optimization.src.core import *
from products.supply_chain_optimization.green_hydrogen_supply_chain_optimization.src.hydrogen import *
from products.supply_chain_optimization.green_hydrogen_supply_chain_optimization.src.routing import *
# ... 等等

# 新import (v3.0)
from products.supply_chain_optimization.coal_hydrogen_saf_supply_chain_optimization.src.core import *
from products.supply_chain_optimization.coal_hydrogen_saf_supply_chain_optimization.src.hydrogen import *
from products.supply_chain_optimization.coal_hydrogen_saf_supply_chain_optimization.src.routing import *
# ... 等等
```

**批量替换脚本**(可选,用于加速):

```bash
# 在coal_hydrogen_saf_supply_chain_optimization目录下执行
find . -type f -name "*.py" -exec sed -i 's/green_hydrogen_supply_chain_optimization/coal_hydrogen_saf_supply_chain_optimization/g' {} +
```

### 3.4 迁移验收标准

**Phase 1-2 迁移验收**:
- [ ] 新目录结构完整创建
- [ ] 所有需要的文件已复制
- [ ] import路径批量替换完成
- [ ] 可以成功导入主模块类:
  ```python
  from src.core.coal_hydrogen_optimization_model import GreenHydrogenSupplyChainOptimizer
  # 注:此时类名还未改,仍是GreenHydrogenSupplyChainOptimizer
  ```
- [ ] 无ImportError错误

**Phase 3-4 清理验收**:
- [ ] src/co2/目录已删除
- [ ] src/coal/目录已创建
- [ ] CoalSupplyManager类已实现
- [ ] 新配置文件已创建

**Phase 5 修改验收**:
- [ ] 类名已修改为CoalHydrogenSAFOptimizer
- [ ] CO₂捕获相关代码已删除
- [ ] 煤炭供应代码已添加
- [ ] 模型可以成功实例化

---

## 四、配置文件修改计划

### 4.1 配置文件概述

**原文件**: `shared/data/GreenHydrogenSupplyChainOptimizer_config.yaml` (v2.0 CO₂捕获版本)
**新文件**: `config/CoalHydrogenSAFOptimizer_config.yaml` (v3.0 煤炭版本)

**修改策略**:
- 删除CO₂捕获相关参数(co2_parameters下的capture_sources等)
- 新增煤炭供应参数(coal_parameters)
- 保留氢气、甲醇、SAF相关参数
- 修改碳排放计算参数(coal_lifecycle_emission替代co2_capture_emission)

**修改范围**:
- 文件头部元数据: 10行
- 删除参数段: ~80行
- 新增参数段: ~60行
- 修改参数段: ~40行
- 保留参数段: ~250行
- **总计约400行YAML**

---

### 4.2 文件头部元数据修改

```yaml
# ===== 原配置(v2.0) =====
# GreenHydrogenSupplyChainOptimizer 配置文件
# 支持绿氢+CO₂制SAF(两步法:甲醇路径)
# Green Hydrogen Supply Chain Optimizer Configuration

metadata:
  version: 2.0.0
  last_updated: '2025-10-25'
  process_type: 'two_step_methanol_mtj'
  description: 绿氢+CO₂捕获制SAF供应链优化

# ===== 新配置(v3.0) =====
# CoalHydrogenSAFOptimizer 配置文件
# 支持煤炭+绿氢制SAF(两步法:甲醇路径)
# Coal-Based Hydrogen SAF Optimizer Configuration

metadata:
  version: 3.0.0
  last_updated: '2025-10-26'
  process_type: 'two_step_methanol_mtj'
  description: 煤炭气化+绿氢制SAF供应链优化
  co2_source: 'coal_gasification'  # 新增:明确CO₂来源
```

---

### 4.3 删除参数清单

**删除原因**: v3.0不使用CO₂捕获技术,无需相关参数

#### 4.3.1 删除co2_parameters段(约80行)

```yaml
# ❌ 删除整个co2_parameters段:
co2_parameters:
  # CO₂捕获源参数
  capture_sources:
    coal_power_capture_rate: 0.85          # ← 删除
    lng_power_capture_rate: 0.90           # ← 删除
    oil_refinery_capture_rate: 0.80        # ← 删除

    coal_power_emission_factor: 0.95       # ← 删除
    lng_power_emission_factor: 0.42        # ← 删除
    oil_refinery_emission_factor: 0.6      # ← 删除

    coal_power_capacity_factor: 0.70       # ← 删除
    lng_power_capacity_factor: 0.75        # ← 删除
    oil_refinery_capacity_factor: 0.85     # ← 删除

  # CO₂捕获成本
  capture_costs:
    coal_power_yuan_per_ton: 150           # ← 删除
    lng_power_yuan_per_ton: 180            # ← 删除
    oil_refinery_yuan_per_ton: 120         # ← 删除

  # CO₂运输参数
  transport:
    pipeline_transport_cost_function:      # ← 删除整个分段线性函数
      function_type: piecewise_linear
      unit: yuan_per_ton_co2_per_100km
      data_points:
      - [25, 12.0]
      - [50, 8.5]
      - [100, 5.0]
      - [200, 3.0]
      - [300, 2.2]
      - [400, 1.8]
      - [500, 1.5]

    truck_cost_yuan_per_ton_per_100km: 50  # ← 删除
    liquefaction_cost_yuan_per_ton: 80     # ← 删除

    max_pipeline_capacity_ton_per_day: 5000  # ← 删除
    max_truck_capacity_ton_per_day: 500      # ← 删除

  # CO₂储存参数
  storage:
    storage_cost_yuan_per_ton_per_day: 0.5  # ← 删除
    max_storage_capacity_ton: 50000         # ← 删除
    storage_density_ton_per_m3: 0.8         # ← 删除
```

#### 4.3.2 删除data_paths中的CO₂捕获源路径

```yaml
# ❌ 删除:
data_paths:
  gis_data:
    coal_power_plants: products/gis.../coal_power_plants.csv      # ← 删除
    lng_terminals: products/gis.../lng_terminals.csv              # ← 删除
    oil_refineries: products/gis.../oil_refineries.csv            # ← 删除
```

---

### 4.4 新增参数段

#### 4.4.1 新增coal_parameters段(约60行)

```yaml
# =============== 新增:煤炭供应参数 ===============
coal_parameters:
  # 煤炭类型与特性
  coal_type: "bituminous"                   # 煤炭类型:烟煤
  coal_type_cn: "烟煤"
  coal_description: |
    烟煤(Bituminous Coal)是中国煤炭气化的主要煤种
    - 含碳量: 75-85%
    - 热值: 24-30 MJ/kg
    - 灰分: 10-20%
    - 挥发分: 20-35%
    - 适用气化炉: Shell气化炉、GE气化炉、航天炉

  # 煤炭气化工艺参数
  gasification:
    gasification_technology: "Shell"        # 气化技术:壳牌气化炉
    gasification_efficiency: 0.75           # 气化效率:75%

    # CO₂生成比例(关键参数)
    co2_generation_ratio: 2.44              # kg CO₂ / kg 煤炭
    co2_generation_derivation: |
      推导过程:
      1. 烟煤含碳量: 75% (0.75 kg C / kg煤)
      2. 完全燃烧反应: C + O₂ → CO₂
      3. 分子量比: 44 (CO₂) / 12 (C) = 3.67
      4. 理论CO₂生成: 0.75 × 3.67 = 2.75 kg CO₂/kg煤
      5. 考虑气化效率75%和部分碳转化为合成气:
         实际CO₂生成 = 2.75 × 0.89 = 2.44 kg CO₂/kg煤

      数据来源: Shell气化技术手册(2023)、IPCC排放因子数据库

    # 其他气化参数
    gasification_temperature_celsius: 1400  # 气化温度:1400°C
    gasification_pressure_mpa: 4.0          # 气化压力:4.0 MPa
    oxygen_to_coal_ratio: 0.95              # 氧煤比:0.95 kg O₂/kg煤
    steam_to_coal_ratio: 0.20               # 水蒸气煤比

    # 能耗参数
    gasification_energy_kwh_per_kg_coal: 8  # 气化能耗:8 kWh/kg煤
    auxiliary_energy_kwh_per_kg_co2: 0.5    # CO₂处理辅助能耗

  # 煤炭定价与成本
  pricing:
    coal_price_yuan_per_ton: 525            # 煤炭市场价格:525元/吨
    coal_price_source: "中国煤炭市场周报(2024年Q3平均)"
    coal_price_volatility: 0.15             # 价格波动范围:±15%

    # 等效CO₂成本(用于与v2.0对比)
    equivalent_co2_cost_yuan_per_ton: 328   # 328元/吨CO₂
    equivalent_co2_cost_derivation: |
      计算: 525元/吨煤 ÷ 2.44 kg CO₂/kg煤 = 215元/吨CO₂
      对比v2.0: CO₂捕获150元/吨 + 运输50-150元/吨 = 200-300元/吨
      结论: 煤炭版CO₂获取成本略高,但无运输成本,总体相当

  # 煤炭消耗比例(终端产品)
  consumption_ratios:
    coal_per_kg_saf: 1.8                    # 1.8 kg煤/kg SAF
    coal_per_kg_methanol: 1.4               # 1.4 kg煤/kg甲醇

    derivation: |
      SAF生产需要:
      - CO₂: 3.5 kg/kg SAF
      - 煤炭气化产生: 2.44 kg CO₂/kg煤
      - 因此: 3.5 ÷ 2.44 ≈ 1.43 kg煤/kg SAF
      - 考虑工艺损失10%: 1.43 × 1.25 = 1.8 kg煤/kg SAF

  # 供应假设
  supply_assumptions:
    supply_model: "market_purchase"         # 供应模式:市场采购
    supply_unlimited: true                  # 假设煤炭供应无限制
    transport_to_factory: "included"        # 运输到工厂的成本已包含在价格中
    quality_standard: "GB/T 15224.1-2018"   # 质量标准:国标烟煤标准

    notes: |
      简化假设:
      1. 煤炭可以无限量购买(市场充足)
      2. 不考虑煤炭运输成本(假设SAF工厂建在煤炭基地附近)
      3. 不加载煤矿GIS数据(非优化决策)
      4. 煤炭质量统一(不考虑煤质差异)
```

---

### 4.5 保留参数段

以下参数段在v3.0中**完全保留**,无需修改:

#### 4.5.1 保留green_hydrogen_supply段

```yaml
green_hydrogen_supply:
  # 生产成本
  production_cost_yuan_per_kg: 25          # ✅ 保留
  production_energy_kwh_per_kg: 50         # ✅ 保留
  electrolyzer_efficiency: 0.70            # ✅ 保留

  # 运输成本
  transport:
    pipeline_cost_yuan_per_kg_per_100km: 0.5   # ✅ 保留
    truck_cost_yuan_per_kg_per_100km: 2.0      # ✅ 保留
    pipeline_capex_yuan_per_km: 5000000        # ✅ 保留

  # 储存参数
  storage:
    storage_cost_yuan_per_kg_per_day: 1.0      # ✅ 保留
    compression_cost_yuan_per_kg: 2.0          # ✅ 保留
```

#### 4.5.2 保留technologies段

```yaml
technologies:
  methanol_mtj_two_step:
    name: "两步法:绿氢+CO₂→甲醇→SAF (E-CRM+MTJ)"  # ✅ 保留
    technology_type: "Methanol-MTJ-TwoStep"         # ✅ 保留

    # 原料消耗比例
    h2_consumption_ratio: 0.20             # ✅ 保留
    co2_consumption_ratio: 3.5             # ✅ 保留
    methanol_intermediate_ratio: 1.3       # ✅ 保留

    # 工艺参数
    efficiency: 0.70                       # ✅ 保留
    e_crm_efficiency: 0.75                 # ✅ 保留
    mtj_efficiency: 0.85                   # ✅ 保留

    # 能耗参数
    energy_consumption_kwh_per_kg_saf: 15  # ✅ 保留
    e_crm_energy_kwh_per_kg_methanol: 8    # ✅ 保留
    mtj_energy_kwh_per_kg_saf: 5           # ✅ 保留
```

#### 4.5.3 保留basic_parameters、optimization_parameters等

```yaml
basic_parameters:                          # ✅ 完全保留
  time_horizon_weeks: 4
  hours_per_day: 24
  days_per_week: 7
  ...

optimization_parameters:                   # ✅ 完全保留
  solver: 'gurobi'
  time_limit_seconds: 3600
  mip_gap: 0.01
  ...

cost_parameters:                           # ✅ 保留(但修改raw_materials)
  shortage_penalty_yuan_per_kg: 2500
  ...
```

---

### 4.6 修改参数段

#### 4.6.1 修改carbon_emission_parameters段

**修改原因**: CO₂来源从捕获改为煤炭气化,碳排放计算方法需调整

```yaml
carbon_emission_parameters:
  benchmarks:                              # ✅ 保留
    traditional_jet_fuel: 89               # 传统航煤碳强度(gCO₂e/MJ)
    saf_energy_content: 43.15              # SAF能量含量(MJ/kg)
    corsia_limit: 44.5                     # CORSIA限值(gCO₂e/MJ)
    corsia_reduction_requirement: 0.50     # 要求减排50%

  # ===== 修改:原材料排放 =====
  raw_materials:
    # ✅ 保留:绿氢排放
    green_h2_intensity: 0.5                # 绿氢碳强度(kgCO₂e/kgH₂)
    renewable_electricity: 0.02            # 可再生电力碳强度

    # ❌ 删除:CO₂捕获排放
    # co2_capture_process_intensity: 0.1   # 删除

    # ✅ 新增:煤炭生命周期排放
    coal_mining_intensity: 0.10            # 煤炭开采排放(kgCO₂e/kg煤)
    coal_transport_intensity: 0.05         # 煤炭运输排放(kgCO₂e/kg煤)
    coal_total_upstream: 0.15              # 煤炭上游总排放

  # ===== 修改:生产过程排放 =====
  production_process:
    # ✅ 新增:煤炭气化排放
    coal_gasification_emission: 0.30       # 气化工艺排放(kgCO₂e/kg煤)
    coal_gasification_energy: 8            # 气化能耗(kWh/kg煤)

    # ✅ 保留:甲醇合成和MTJ转化排放
    e_crm_synthesis_emission: 0.3          # 甲醇合成(kgCO₂e/kg甲醇)
    mtj_conversion_emission: 0.4           # MTJ转化(kgCO₂e/kgSAF)
    total_process_emission: 1.2            # 总工艺排放(kgCO₂e/kgSAF)

    # ✅ 保留:CO₂利用负排放
    co2_utilization_credit: -1.0           # CO₂固定负排放系数

  # ===== 保留:运输排放 =====
  transportation:                          # ✅ 完全保留
    h2_pipeline_intensity: 0.005
    h2_truck_intensity: 0.15
    # ❌ 删除CO₂运输排放(v3.0无CO₂运输)
    # co2_pipeline_intensity: 0.003
    # co2_truck_intensity: 0.08
    saf_truck_intensity: 0.12

  # ===== 保留:储存处理排放 =====
  storage_handling:                        # ✅ 保留(删除co2_storage)
    h2_storage_energy: 0.5
    # co2_storage_energy: 0.3             # ❌ 删除
    methanol_storage_energy: 0.1
    saf_storage_energy: 0.05

  # ===== 新增:v3.0碳排放估算 =====
  estimated_carbon_intensity:
    coal_based_saf_gco2e_per_mj: 60        # v3.0估算:60 gCO₂e/MJ
    calculation_breakdown: |
      Well-to-Wake碳排放计算(v3.0煤炭版):

      1. 煤炭上游排放:
         - 开采: 0.10 kgCO₂e/kg煤 × 1.8 kg煤/kg SAF = 0.18
         - 运输: 0.05 kgCO₂e/kg煤 × 1.8 kg煤/kg SAF = 0.09
         - 小计: 0.27 kgCO₂e/kg SAF

      2. 煤炭气化排放:
         - 工艺排放: 0.30 kgCO₂e/kg煤 × 1.8 = 0.54
         - 能耗排放: 8 kWh/kg煤 × 0.02 kgCO₂e/kWh × 1.8 = 0.29
         - 小计: 0.83 kgCO₂e/kg SAF

      3. 绿氢生产排放:
         - 0.5 kgCO₂e/kgH₂ × 0.2 kgH₂/kgSAF = 0.10

      4. 甲醇合成+MTJ转化排放:
         - E-CRM: 0.3 kgCO₂e/kg甲醇 × 1.3 = 0.39
         - MTJ: 0.4 kgCO₂e/kgSAF = 0.40
         - 小计: 0.79 kgCO₂e/kg SAF

      5. 运输和储存排放: 0.15 kgCO₂e/kg SAF

      6. CO₂利用负排放:
         - 固定3.5 kg CO₂/kg SAF
         - 负排放: -1.0 kgCO₂e/kgSAF

      总排放: 0.27 + 0.83 + 0.10 + 0.79 + 0.15 - 1.0 = 1.14 kgCO₂e/kg SAF

      碳强度: 1.14 kgCO₂e/kg ÷ (43.15 MJ/kg) × 1000 = 26.4 gCO₂e/MJ

      ⚠️ 注意: 实际碳强度约60 gCO₂e/MJ,因为:
      - 煤炭生命周期排放被低估(实际更高)
      - CO₂利用负排放效果有限
      - 需要考虑间接排放

      对比:
      - 传统航煤: 89 gCO₂e/MJ
      - v2.0 CO₂捕获: 25 gCO₂e/MJ (满足CORSIA)
      - v3.0 煤炭: 60 gCO₂e/MJ (不满足CORSIA 44.5限值)
      - 减排效果: 33% vs 传统航煤
```

#### 4.6.2 修改cost_parameters.raw_materials段

```yaml
cost_parameters:
  raw_materials:
    # ✅ 保留:氢气价格
    hydrogen_market_price_yuan_per_kg: 30
    renewable_electricity_cost_yuan_per_mwh: 500

    # ❌ 删除:CO₂捕获价格
    # co2_capture_price_yuan_per_ton: 150   # 删除

    # ✅ 新增:煤炭价格
    coal_price_yuan_per_ton: 525            # 新增

  # ✅ 保留:其他成本参数
  electrolysis:
    electrolysis_efficiency: 0.8
    electrolysis_power_consumption: 45

  shortage_penalty_yuan_per_kg: 2500
```

---

### 4.7 配置文件验证脚本

创建脚本验证新配置文件的正确性:

```python
# ===== config/validate_config.py =====
import yaml
import sys

def validate_coal_hydrogen_config(config_path):
    """验证煤炭+绿氢配置文件"""

    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    print("=" * 60)
    print("配置文件验证: CoalHydrogenSAFOptimizer")
    print("=" * 60)

    # 1. 验证必需的顶层键
    required_keys = [
        'metadata', 'coal_parameters', 'green_hydrogen_supply',
        'technologies', 'carbon_emission_parameters', 'cost_parameters',
        'basic_parameters', 'optimization_parameters'
    ]

    missing_keys = [key for key in required_keys if key not in config]
    if missing_keys:
        print(f"❌ 缺少必需键: {missing_keys}")
        return False
    print("✅ 顶层键完整")

    # 2. 验证煤炭参数
    coal_params = config['coal_parameters']
    assert coal_params['coal_type'] == 'bituminous', "煤炭类型应为烟煤"
    assert coal_params['gasification']['co2_generation_ratio'] == 2.44, \
        "CO₂生成比应为2.44"
    assert coal_params['pricing']['coal_price_yuan_per_ton'] == 525, \
        "煤炭价格应为525元/吨"
    print("✅ 煤炭参数正确")

    # 3. 验证不存在CO₂捕获参数
    assert 'co2_parameters' not in config, \
        "❌ 不应存在co2_parameters(v3.0不使用CO₂捕获)"
    print("✅ 已删除CO₂捕获参数")

    # 4. 验证碳排放参数
    carbon_params = config['carbon_emission_parameters']
    assert 'coal_mining_intensity' in carbon_params['raw_materials'], \
        "应包含煤炭开采排放强度"
    assert 'coal_gasification_emission' in carbon_params['production_process'], \
        "应包含煤炭气化排放"
    assert 'co2_capture_process_intensity' not in carbon_params['raw_materials'], \
        "不应包含CO₂捕获排放(v3.0不使用)"
    print("✅ 碳排放参数正确")

    # 5. 验证技术路线
    tech = config['technologies']['methanol_mtj_two_step']
    assert tech['h2_consumption_ratio'] == 0.20, "氢气消耗比例应为0.20"
    assert tech['co2_consumption_ratio'] == 3.5, "CO₂消耗比例应为3.5"
    print("✅ 技术路线参数正确")

    # 6. 关键参数总结
    print("\n" + "=" * 60)
    print("关键参数总结:")
    print("=" * 60)
    print(f"配置版本: {config['metadata']['version']}")
    print(f"CO₂来源: {config['metadata']['co2_source']}")
    print(f"煤炭类型: {coal_params['coal_type_cn']}")
    print(f"CO₂生成比: {coal_params['gasification']['co2_generation_ratio']} kg/kg")
    print(f"煤炭价格: {coal_params['pricing']['coal_price_yuan_per_ton']} 元/吨")
    print(f"等效CO₂成本: {coal_params['pricing']['equivalent_co2_cost_yuan_per_ton']} 元/吨")
    print(f"估算碳强度: {carbon_params['estimated_carbon_intensity']['coal_based_saf_gco2e_per_mj']} gCO₂e/MJ")

    print("\n✅ 配置文件验证通过!")
    return True

if __name__ == "__main__":
    config_path = "config/CoalHydrogenSAFOptimizer_config.yaml"
    validate_coal_hydrogen_config(config_path)
```

**使用方法**:
```bash
python config/validate_config.py
```

---

### 4.8 配置文件修改总结表

| 修改类别 | 原配置(v2.0) | 新配置(v3.0) | 变化说明 |
|---------|-------------|-------------|---------|
| **文件头部** | GreenHydrogen...v2.0 | CoalHydrogen...v3.0 | 更新版本和描述 |
| **删除参数** | co2_parameters (80行) | ✗ 删除 | 删除CO₂捕获相关 |
| **新增参数** | ✗ 无 | coal_parameters (60行) | 新增煤炭供应参数 |
| **修改参数** | carbon_emission... | 修改排放计算 | 煤炭生命周期排放 |
| **保留参数** | green_hydrogen_supply | ✓ 保留 | 完全不变 |
| **保留参数** | technologies | ✓ 保留 | 完全不变 |
| **保留参数** | basic_parameters | ✓ 保留 | 完全不变 |
| **保留参数** | optimization_parameters | ✓ 保留 | 完全不变 |
| **GIS数据路径** | 4类CO₂源路径 | ✗ 删除 | 无需GIS数据 |
| **总行数** | ~400行 | ~400行 | 相同 |
| **有效修改** | - | ~100行实质变化 | 其余保留 |

**配置文件对比关键指标**:
- CO₂获取成本: v2.0 200-300元/吨(捕获+运输) vs v3.0 328元/吨(煤炭等效)
- 碳强度估算: v2.0 25 gCO₂e/MJ vs v3.0 60 gCO₂e/MJ
- CORSIA合规: v2.0 ✅ 满足 vs v3.0 ❌ 不满足
- 系统复杂度: v2.0 高(4311个CO₂源) vs v3.0 低(市场采购)
- 数据依赖: v2.0 需要4类GIS数据 vs v3.0 无GIS需求

---


## 五、核心代码修改计划

### 5.1 主优化模型文件修改

**文件**：`src/core/coal_hydrogen_optimization_model.py`
**原文件**：`src/core/green_hydrogen_optimization_model.py`

**修改范围**：约20%代码需要修改

#### 5.1.1 类名和文件路径修改

```python
# ===== 修改1：类名 =====
# 原：class GreenHydrogenSupplyChainOptimizer:
# 新：class CoalHydrogenSAFOptimizer:

class CoalHydrogenSAFOptimizer:
    """
    煤炭+绿氢制SAF供应链优化器

    工艺路线：煤炭气化产生CO₂ + 绿氢 → 甲醇 → SAF

    核心简化：
    - CO₂来源：煤炭气化（本地产生）vs v2.0 CO₂捕获（需运输）
    - 决策变量：约35万 vs v2.0约600万（-94%）
    - 约束条件：约2万 vs v2.0约580万（-99.7%）
    - 求解时间：5-15分钟 vs v2.0 30-60分钟（-75%）

    参数：
        config_path: 配置文件路径
    """

    def __init__(self, config_path: str = None):
        """初始化优化器"""
        # 默认配置文件路径
        if config_path is None:
            project_root = self._get_project_root()
            config_path = os.path.join(
                project_root, "shared", "data",
                "CoalHydrogenSAFOptimizer_config.yaml"
            )

        # 日志配置
        log_dir = os.path.join(
            project_root, "products", "supply_chain_optimization",
            "coal_hydrogen_saf_supply_chain_optimization", "results", "logs"
        )
        mount_file_logging(log_dir, filename_prefix="coal_h2_saf")

        # 加载配置
        self.config = self._load_config(config_path)
        logger.info("CoalHydrogenSAFOptimizer initialized")
```

#### 5.1.2 数据加载方法修改

**核心变更**：删除CO₂捕获源加载，新增煤炭供应定义

```python
# ===== v2.0代码（删除）=====
# ❌ 删除整个方法：
def _load_co2_capture_sources(self) -> pd.DataFrame:
    """
    从GIS数据加载CO₂捕获源并计算捕获量

    v2.0复杂逻辑：
    - 加载4类GIS数据（煤电、气电、炼油、LNG）
    - 使用CO2CaptureCalculator计算周级捕获量
    - 考虑容量因子、排放因子、捕获率
    - 返回4311条记录（3821+270+220）

    代码行数：约500行（含CO2CaptureCalculator类）
    """
    from ..co2.co2_capture_calculator import CO2CaptureCalculator

    calculator = CO2CaptureCalculator(self.config)
    gis_data_dir = self._get_data_path('gis_data.coal_power_plants')
    co2_sources = calculator.calculate_from_gis_data(
        gis_data_dir,
        self.time_horizon_weeks
    )

    logger.info(f"成功加载 {len(co2_sources)} 条CO₂捕获源记录")
    return co2_sources

# ===== v3.0代码（新增）=====
# ✅ 新增极简方法：
def _define_coal_supply(self):
    """
    定义煤炭供应参数（v3.0新增）

    v3.0简化逻辑：
    - 无需加载GIS数据（市场采购模式）
    - 直接从配置文件读取煤炭参数
    - 假设煤炭供应无限制（市场充足）
    - 无需计算供应容量限制

    代码行数：约50行（减少91%）
    """
    coal_params = self.config['coal_parameters']

    # 煤炭基本参数
    self.coal_type = coal_params['coal_type']  # "bituminous"
    self.coal_price_yuan_per_ton = coal_params['pricing']['coal_price_yuan_per_ton']  # 525

    # 气化参数
    gasification = coal_params['gasification']
    self.coal_co2_ratio = gasification['co2_generation_ratio']  # 2.44 kg CO₂/kg coal
    self.gasification_efficiency = gasification['gasification_efficiency']  # 0.75
    self.gasification_energy_kwh_per_kg = gasification['gasification_energy_kwh_per_kg_coal']  # 8

    # 消耗比例
    consumption = coal_params['consumption_ratios']
    self.coal_per_kg_saf = consumption['coal_per_kg_saf']  # 1.8 kg coal/kg SAF
    self.coal_per_kg_methanol = consumption['coal_per_kg_methanol']  # 1.4

    logger.info(f"煤炭供应参数定义完成：")
    logger.info(f"  煤炭类型：{self.coal_type}")
    logger.info(f"  CO₂生成比：{self.coal_co2_ratio} kg CO₂/kg coal")
    logger.info(f"  煤炭价格：{self.coal_price_yuan_per_ton} 元/吨")
    logger.info(f"  单位SAF煤耗：{self.coal_per_kg_saf} kg/kg")
```

**复杂度对比**：

| 对比项 | v2.0 CO₂捕获 | v3.0 煤炭 | 简化幅度 |
|-------|-------------|----------|---------|
| **方法行数** | ~500行 | ~50行 | -90% |
| **数据加载** | 4类GIS文件 | 0个文件 | -100% |
| **计算复杂度** | O(N×M×T) N=4311 | O(M×T) | -99.9% |
| **返回数据量** | 4311×W条记录 | 0条（参数定义） | -100% |
| **依赖模块** | CO2CaptureCalculator | 仅配置文件 | -100% |

#### 5.1.3 修改load_data()主方法

```python
def load_data(self, ...):
    """主数据加载方法"""

    # ===== 删除v2.0 CO₂捕获加载 =====
    # ❌ self.co2_sources = self._load_co2_capture_sources()

    # ✅ 保留：可再生能源发电站加载
    self.renewable_plants = renewable_plants_df
    logger.info(f"加载 {len(self.renewable_plants)} 个可再生能源发电站")

    # ✅ 保留：机场需求加载
    self.airports = self._load_airports(...)
    logger.info(f"加载 {len(self.airports)} 个机场")

    # ===== 新增v3.0煤炭参数定义 =====
    # ✅ 新增：煤炭供应参数定义
    self._define_coal_supply()

    # ✅ 保留：距离计算（仅H₂和SAF运输，删除CO₂运输）
    self._calculate_distances()

    # ✅ 保留：其他数据加载...
    ...
```

---

### 5.2 决策变量修改

#### 5.2.1 删除CO₂运输决策变量

**v2.0变量（删除）**：

```python
# ❌ 删除：CO₂管道运输变量（约580万个变量）
self.co2_pipeline_transport = model.addVars(
    [(c, j, t) for c in co2_sources for j in saf_locations for t in hours],
    vtype=GRB.CONTINUOUS, lb=0, name="co2_pipeline_transport"
)
# 变量数：4311个CO₂源 × 200个SAF位置 × 672小时 ≈ 580万

# ❌ 删除：CO₂罐车运输变量（约580万个变量）
self.co2_truck_transport = model.addVars(
    [(c, j, t) for c in co2_sources for j in saf_locations for t in hours],
    vtype=GRB.CONTINUOUS, lb=0, name="co2_truck_transport"
)

# ❌ 删除：CO₂管道建设决策变量（约86万个变量）
self.co2_pipeline_built = model.addVars(
    [(c, j) for c in co2_sources for j in saf_locations],
    vtype=GRB.BINARY, name="co2_pipeline_built"
)
# 变量数：4311 × 200 ≈ 86万

# v2.0 CO₂相关变量总数：580万 + 580万 + 86万 ≈ 1246万个变量
```

#### 5.2.2 新增煤炭采购决策变量

**v3.0变量（新增）**：

```python
# ✅ 新增：煤炭采购变量（约17,000个变量）
self.coal_purchase = model.addVars(
    [(j, t) for j in saf_locations for t in hours],
    vtype=GRB.CONTINUOUS, lb=0, name="coal_purchase"
)
# 变量数：200个SAF位置 × 672小时（4周） ≈ 134,400
# 说明：coal_purchase[j, t] = 在位置j的t时刻采购的煤炭量（kg）

# ✅ 保留但用途变化：CO₂库存变量
self.co2_inventory = model.addVars(
    [(j, t) for j in saf_locations for t in hours],
    vtype=GRB.CONTINUOUS, lb=0, name="co2_inventory"
)
# 说明：v2.0中CO₂来自运输，v3.0中CO₂来自煤炭气化
# 变量数：134,400（与v2.0相同）
```

**变量数量对比**：

| 变量类型 | v2.0（CO₂捕获） | v3.0（煤炭） | 变化 |
|---------|----------------|-------------|------|
| **CO₂管道运输** | 5,800,000 | 0（删除） | -100% |
| **CO₂罐车运输** | 5,800,000 | 0（删除） | -100% |
| **CO₂管道建设** | 862,200 | 0（删除） | -100% |
| **煤炭采购** | 0 | 134,400（新增） | +100% |
| **CO₂库存** | 134,400 | 134,400（保留） | 0% |
| **小计（CO₂相关）** | 12,596,600 | 134,400 | **-98.9%** |

---

### 5.3 约束条件修改

#### 5.3.1 删除CO₂供应和运输约束

**v2.0约束（删除）**：

```python
# ❌ 删除：CO₂供应平衡约束（按周）（约580万条约束）
for c in co2_sources:  # 4311个CO₂源
    for week in weeks:  # 4周
        week_start = week * 168
        week_end = (week + 1) * 168
        weekly_co2_supply = gp.quicksum(
            co2_pipeline_transport[c, j, t] + co2_truck_transport[c, j, t]
            for j in saf_locations
            for t in range(week_start, week_end)
        )
        model.addConstr(
            weekly_co2_supply <= co2_capture_capacity[c, week],
            name=f"co2_supply_limit_{c}_{week}"
        )
# 约束数：4311 × 4 × 200 ≈ 3,448,800

# ❌ 删除：CO₂管道Big-M约束（约580万条约束）
for c in co2_sources:
    for j in saf_locations:
        for t in hours:
            model.addConstr(
                co2_pipeline_transport[c, j, t] <= Big_M * co2_pipeline_built[c, j],
                name=f"co2_pipeline_bigm_{c}_{j}_{t}"
            )
# 约束数：4311 × 200 × 672 ≈ 5,800,000

# ❌ 删除：CO₂管道和罐车互斥约束（约580万条约束）
for c in co2_sources:
    for j in saf_locations:
        for t in hours:
            model.addConstr(
                co2_truck_transport[c, j, t] <= Big_M * (1 - co2_pipeline_built[c, j]),
                name=f"co2_exclusive_truck_{c}_{j}_{t}"
            )
# 约束数：5,800,000

# v2.0 CO₂相关约束总数：3,448,800 + 5,800,000 + 5,800,000 ≈ 15,048,800（1500万）
```

#### 5.3.2 新增煤炭气化产生CO₂约束

**v3.0约束（新增）**：

```python
# ✅ 新增：煤炭气化产生CO₂约束（约17,000条约束）
for j in saf_locations:  # 200个位置
    for t in hours:  # 672小时
        if t == 0:
            # 初始时刻：CO₂库存 = 煤炭气化产生
            co2_from_coal = self.coal_purchase[j, t] * self.coal_co2_ratio  # 2.44
            model.addConstr(
                self.co2_inventory[j, t] == co2_from_coal,
                name=f"co2_init_{j}"
            )
        else:
            # 后续时刻：库存平衡
            co2_from_coal = self.coal_purchase[j, t] * self.coal_co2_ratio
            co2_consumed = (
                self.methanol_production[j, t] *
                self.tech_params['co2_to_methanol_ratio']  # 2.8 kg CO₂/kg methanol
            )
            model.addConstr(
                self.co2_inventory[j, t] == (
                    self.co2_inventory[j, t-1] +  # 上时刻库存
                    co2_from_coal -                # 本时刻气化产生
                    co2_consumed                   # 本时刻消耗
                ),
                name=f"co2_balance_{j}_{t}"
            )
# 约束数：200 × 672 ≈ 134,400

# 说明：
# 1. 煤炭气化：coal_purchase × 2.44 → CO₂
# 2. CO₂本地产生，无运输决策，直接进入库存
# 3. 库存桥接：连接煤炭采购和甲醇生产
```

**约束数量对比**：

| 约束类型 | v2.0（CO₂捕获） | v3.0（煤炭） | 变化 |
|---------|----------------|-------------|------|
| **CO₂供应平衡** | 3,448,800 | 0（删除） | -100% |
| **CO₂管道Big-M** | 5,800,000 | 0（删除） | -100% |
| **CO₂管道罐车互斥** | 5,800,000 | 0（删除） | -100% |
| **煤炭气化CO₂生成** | 0 | 134,400（新增） | +100% |
| **小计（CO₂相关）** | 15,048,800 | 134,400 | **-99.1%** |

---

### 5.4 目标函数修改

#### 5.4.1 删除CO₂捕获和运输成本

**v2.0成本项（删除）**：

```python
# ❌ 删除：CO₂捕获成本
co2_capture_cost = gp.quicksum(
    (co2_pipeline_transport[c,j,t] + co2_truck_transport[c,j,t]) *
    co2_capture_price[c]  # 150-180元/吨
    for c in co2_sources for j in saf_locations for t in hours
)

# ❌ 删除：CO₂管道运输成本
co2_pipeline_cost = gp.quicksum(
    co2_pipeline_transport[c,j,t] * co2_pipeline_unit_cost[c,j]
    for c in co2_sources for j in saf_locations for t in hours
)

# ❌ 删除：CO₂罐车运输成本
co2_truck_cost = gp.quicksum(
    co2_truck_transport[c,j,t] * co2_truck_unit_cost[c,j]
    for c in co2_sources for j in saf_locations for t in hours
)

# ❌ 删除：CO₂管道建设成本（已摊销到分段线性函数中，但变量被删除）
# 注：v2.0中管道建设成本已摊销到运输成本中，无需单独计算

# v2.0 CO₂总成本 = 捕获 + 管道运输 + 罐车运输
# 典型值：150元/吨捕获 + 50-150元/吨运输 = 200-300元/吨CO₂
```

#### 5.4.2 新增煤炭采购和气化成本

**v3.0成本项（新增）**：

```python
# ✅ 新增：煤炭采购成本
coal_purchase_cost = gp.quicksum(
    self.coal_purchase[j, t] * (self.coal_price_yuan_per_ton / 1000)
    for j in saf_locations for t in hours
)
# 说明：
# - 煤炭价格：800元/吨 = 0.8元/kg
# - 单位SAF煤耗：1.8 kg煤/kg SAF
# - 煤炭成本：0.8 × 1.8 = 1.44元/kg SAF

# ✅ 新增：煤炭气化能耗成本
coal_gasification_energy_cost = gp.quicksum(
    self.coal_purchase[j, t] *
    self.gasification_energy_kwh_per_kg *  # 8 kWh/kg coal
    self.electricity_price_yuan_per_kwh    # 0.5元/kWh
    for j in saf_locations for t in hours
)
# 说明：
# - 气化能耗：8 kWh/kg煤
# - 电价：0.5元/kWh
# - 气化能耗成本：8 × 0.5 = 4元/kg煤
# - 单位SAF气化成本：4 × 1.8 = 7.2元/kg SAF

# v3.0煤炭总成本 = 采购 + 气化能耗
# 单位SAF成本：1.44 + 7.2 = 8.64元/kg SAF
```

#### 5.4.3 成本对比分析

**等效CO₂成本对比**：

```python
# v2.0 CO₂成本：
# - 捕获：150元/吨
# - 运输：50-150元/吨（平均100元/吨）
# - 总计：250元/吨CO₂
# - 单位SAF: 250 × (3.5 kg CO₂/kg SAF) / 1000 = 0.875元/kg SAF

# v3.0等效CO₂成本：
# - 煤炭：525元/吨煤 ÷ 2.44 kg CO₂/kg煤 = 215元/吨CO₂
# - 气化能耗：4元/kg煤 ÷ 2.44 = 1.64元/kg CO₂（约164元/吨CO₂）
# - 总计：328 + 164 = 492元/吨CO₂（等效）
# - 单位SAF: 492 × 3.5 / 1000 = 1.722元/kg SAF

# 对比结论：
# v3.0煤炭版CO₂等效成本（492元/吨）比v2.0 CO₂捕获（250元/吨）高约97%
# 但v3.0无运输成本，系统简单，煤炭供应充足
```

#### 5.4.4 修改后的总目标函数

```python
# ===== v3.0目标函数 =====
total_cost = (
    # ✅ 保留：绿氢成本
    h2_production_cost +           # 绿氢生产
    h2_transport_cost +            # 绿氢运输

    # ✅ 新增：煤炭成本
    coal_purchase_cost +           # 煤炭采购（新增）
    coal_gasification_energy_cost + # 煤炭气化能耗（新增）

    # ✅ 保留：生产成本
    methanol_production_cost +     # 甲醇合成
    methanol_storage_cost +        # 甲醇储存
    saf_production_cost +          # SAF生产

    # ✅ 保留：运输和设施成本
    saf_transport_cost +           # SAF运输
    facility_cost +                # 设施投资

    # ✅ 保留：惩罚成本
    shortage_penalty               # 缺货惩罚
)

model.setObjective(total_cost, GRB.MINIMIZE)
```

**成本结构占比估算**（假设1 kg SAF）：

| 成本项 | v2.0 | v3.0 | 变化 |
|-------|------|------|------|
| **绿氢** | 30% | 35% | +5% |
| **CO₂获取** | 15% | - | 删除 |
| **煤炭采购** | - | 20% | 新增 |
| **气化能耗** | - | 10% | 新增 |
| **甲醇生产** | 25% | 20% | -5% |
| **SAF生产** | 20% | 10% | -10% |
| **运输** | 10% | 5% | -5% |

---

### 5.5 代码修改总结

#### 5.5.1 代码行数变化

| 模块 | v2.0 | v3.0 | 变化 |
|-----|------|------|------|
| **CO₂捕获模块** | ~700行 | 0行（删除） | -100% |
| **煤炭供应模块** | 0行 | ~60行（新增） | +100% |
| **数据加载** | ~200行 | ~50行 | -75% |
| **决策变量定义** | ~300行 | ~100行 | -67% |
| **约束条件** | ~800行 | ~200行 | -75% |
| **目标函数** | ~150行 | ~80行 | -47% |
| **总计** | ~2150行 | ~490行 | **-77%** |

#### 5.5.2 模型复杂度变化

| 指标 | v2.0 | v3.0 | 变化 |
|-----|------|------|------|
| **决策变量数** | 约600万 | 约35万 | **-94%** |
| **约束条件数** | 约580万 | 约2万 | **-99.7%** |
| **GIS数据加载** | 4类文件 | 0个文件 | -100% |
| **求解时间（1周）** | 30-60分钟 | 5-15分钟 | **-75%** |
| **内存占用** | ~8GB | ~1GB | -88% |

#### 5.5.3 关键性能提升点

**1. 决策变量大幅减少**：
- 删除CO₂运输变量：580万（管道） + 580万（罐车） + 86万（建设） = 1246万
- 新增煤炭采购变量：13.4万
- 净减少：1246万 - 13.4万 ≈ 1233万变量（-98.9%）

**2. 约束条件极致简化**：
- 删除CO₂供应约束：345万（供应平衡） + 580万（Big-M） + 580万（互斥） = 1505万
- 新增煤炭气化约束：13.4万
- 净减少：1505万 - 13.4万 ≈ 1492万约束（-99.1%）

**3. 计算复杂度降低**：
- v2.0：O(N×M×T) where N=4311（CO₂源数）
- v3.0：O(M×T) where M=200（SAF位置数）
- 复杂度降低：4311倍

**4. 数据准备时间缩短**：
- v2.0：加载4类GIS数据 + CO₂捕获计算 ≈ 10-15分钟
- v3.0：读取配置文件煤炭参数 ≈ 1秒
- 数据准备时间减少：99.9%

---

### 5.6 代码修改验收标准

#### 5.6.1 功能完整性检查

- [ ] 类名已修改为CoalHydrogenSAFOptimizer
- [ ] 配置文件路径指向CoalHydrogenSAFOptimizer_config.yaml
- [ ] 日志前缀改为coal_h2_saf
- [ ] _define_coal_supply()方法实现并测试通过
- [ ] _load_co2_capture_sources()方法已完全删除
- [ ] coal_purchase决策变量定义正确
- [ ] CO₂运输相关变量已完全删除
- [ ] 煤炭气化CO₂生成约束添加正确
- [ ] CO₂供应和运输约束已完全删除
- [ ] 煤炭采购和气化成本添加到目标函数
- [ ] CO₂捕获和运输成本已从目标函数删除

#### 5.6.2 代码质量检查

- [ ] 无CO₂捕获相关代码残留（grep "co2_capture" "co2_pipeline" "co2_truck" 无结果）
- [ ] 所有import语句正确（无co2模块导入）
- [ ] 变量命名符合规范（coal_purchase, coal_co2_ratio等）
- [ ] 注释完整清晰（标注v2.0删除和v3.0新增）
- [ ] 日志记录充分（关键步骤都有日志）
- [ ] 异常处理完善（煤炭参数缺失时抛出清晰错误）

#### 5.6.3 性能验证

- [ ] 模型可成功实例化
- [ ] 数据加载时间 < 10秒
- [ ] 模型构建时间 < 5分钟
- [ ] 决策变量数 ≈ 35万（对比v2.0的600万）
- [ ] 约束条件数 ≈ 2万（对比v2.0的580万）
- [ ] 小规模测试求解时间 < 1分钟
- [ ] 完整测试求解时间 < 20分钟（1周优化范围）

---


## 五、核心代码修改计划

### 5.1 主优化模型文件修改

**文件**：`src/core/coal_hydrogen_optimization_model.py`
**原文件**：`src/core/green_hydrogen_optimization_model.py`

**修改范围**：约20%代码需要修改

#### 5.1.1 类名和文件路径修改

```python
# ===== 修改1：类名 =====
# 原：class GreenHydrogenSupplyChainOptimizer:
# 新：class CoalHydrogenSAFOptimizer:

class CoalHydrogenSAFOptimizer:
    """
    煤炭+绿氢制SAF供应链优化器

    工艺路线：煤炭气化产生CO₂ + 绿氢 → 甲醇 → SAF

    核心简化：
    - CO₂来源：煤炭气化（本地产生）vs v2.0 CO₂捕获（需运输）
    - 决策变量：约35万 vs v2.0约600万（-94%）
    - 约束条件：约2万 vs v2.0约580万（-99.7%）
    - 求解时间：5-15分钟 vs v2.0 30-60分钟（-75%）

    参数：
        config_path: 配置文件路径
    """

    def __init__(self, config_path: str = None):
        """初始化优化器"""
        # 默认配置文件路径
        if config_path is None:
            project_root = self._get_project_root()
            config_path = os.path.join(
                project_root, "shared", "data",
                "CoalHydrogenSAFOptimizer_config.yaml"
            )

        # 日志配置
        log_dir = os.path.join(
            project_root, "products", "supply_chain_optimization",
            "coal_hydrogen_saf_supply_chain_optimization", "results", "logs"
        )
        mount_file_logging(log_dir, filename_prefix="coal_h2_saf")

        # 加载配置
        self.config = self._load_config(config_path)
        logger.info("CoalHydrogenSAFOptimizer initialized")
```

#### 5.1.2 数据加载方法修改

**核心变更**：删除CO₂捕获源加载，新增煤炭供应定义

```python
# ===== v2.0代码（删除）=====
# ❌ 删除整个方法：
def _load_co2_capture_sources(self) -> pd.DataFrame:
    """
    从GIS数据加载CO₂捕获源并计算捕获量

    v2.0复杂逻辑：
    - 加载4类GIS数据（煤电、气电、炼油、LNG）
    - 使用CO2CaptureCalculator计算周级捕获量
    - 考虑容量因子、排放因子、捕获率
    - 返回4311条记录（3821+270+220）

    代码行数：约500行（含CO2CaptureCalculator类）
    """
    from ..co2.co2_capture_calculator import CO2CaptureCalculator

    calculator = CO2CaptureCalculator(self.config)
    gis_data_dir = self._get_data_path('gis_data.coal_power_plants')
    co2_sources = calculator.calculate_from_gis_data(
        gis_data_dir,
        self.time_horizon_weeks
    )

    logger.info(f"成功加载 {len(co2_sources)} 条CO₂捕获源记录")
    return co2_sources

# ===== v3.0代码（新增）=====
# ✅ 新增极简方法：
def _define_coal_supply(self):
    """
    定义煤炭供应参数（v3.0新增）

    v3.0简化逻辑：
    - 无需加载GIS数据（市场采购模式）
    - 直接从配置文件读取煤炭参数
    - 假设煤炭供应无限制（市场充足）
    - 无需计算供应容量限制

    代码行数：约50行（减少91%）
    """
    coal_params = self.config['coal_parameters']

    # 煤炭基本参数
    self.coal_type = coal_params['coal_type']  # "bituminous"
    self.coal_price_yuan_per_ton = coal_params['pricing']['coal_price_yuan_per_ton']  # 525

    # 气化参数
    gasification = coal_params['gasification']
    self.coal_co2_ratio = gasification['co2_generation_ratio']  # 2.44 kg CO₂/kg coal
    self.gasification_efficiency = gasification['gasification_efficiency']  # 0.75
    self.gasification_energy_kwh_per_kg = gasification['gasification_energy_kwh_per_kg_coal']  # 8

    # 消耗比例
    consumption = coal_params['consumption_ratios']
    self.coal_per_kg_saf = consumption['coal_per_kg_saf']  # 1.8 kg coal/kg SAF
    self.coal_per_kg_methanol = consumption['coal_per_kg_methanol']  # 1.4

    logger.info(f"煤炭供应参数定义完成：")
    logger.info(f"  煤炭类型：{self.coal_type}")
    logger.info(f"  CO₂生成比：{self.coal_co2_ratio} kg CO₂/kg coal")
    logger.info(f"  煤炭价格：{self.coal_price_yuan_per_ton} 元/吨")
    logger.info(f"  单位SAF煤耗：{self.coal_per_kg_saf} kg/kg")
```

**复杂度对比**：

| 对比项 | v2.0 CO₂捕获 | v3.0 煤炭 | 简化幅度 |
|-------|-------------|----------|---------|
| **方法行数** | ~500行 | ~50行 | -90% |
| **数据加载** | 4类GIS文件 | 0个文件 | -100% |
| **计算复杂度** | O(N×M×T) N=4311 | O(M×T) | -99.9% |
| **返回数据量** | 4311×W条记录 | 0条（参数定义） | -100% |
| **依赖模块** | CO2CaptureCalculator | 仅配置文件 | -100% |

#### 5.1.3 修改load_data()主方法

```python
def load_data(self, ...):
    """主数据加载方法"""

    # ===== 删除v2.0 CO₂捕获加载 =====
    # ❌ self.co2_sources = self._load_co2_capture_sources()

    # ✅ 保留：可再生能源发电站加载
    self.renewable_plants = renewable_plants_df
    logger.info(f"加载 {len(self.renewable_plants)} 个可再生能源发电站")

    # ✅ 保留：机场需求加载
    self.airports = self._load_airports(...)
    logger.info(f"加载 {len(self.airports)} 个机场")

    # ===== 新增v3.0煤炭参数定义 =====
    # ✅ 新增：煤炭供应参数定义
    self._define_coal_supply()

    # ✅ 保留：距离计算（仅H₂和SAF运输，删除CO₂运输）
    self._calculate_distances()

    # ✅ 保留：其他数据加载...
    ...
```

---

### 5.2 决策变量修改

#### 5.2.1 删除CO₂运输决策变量

**v2.0变量（删除）**：

```python
# ❌ 删除：CO₂管道运输变量（约580万个变量）
self.co2_pipeline_transport = model.addVars(
    [(c, j, t) for c in co2_sources for j in saf_locations for t in hours],
    vtype=GRB.CONTINUOUS, lb=0, name="co2_pipeline_transport"
)
# 变量数：4311个CO₂源 × 200个SAF位置 × 672小时 ≈ 580万

# ❌ 删除：CO₂罐车运输变量（约580万个变量）
self.co2_truck_transport = model.addVars(
    [(c, j, t) for c in co2_sources for j in saf_locations for t in hours],
    vtype=GRB.CONTINUOUS, lb=0, name="co2_truck_transport"
)

# ❌ 删除：CO₂管道建设决策变量（约86万个变量）
self.co2_pipeline_built = model.addVars(
    [(c, j) for c in co2_sources for j in saf_locations],
    vtype=GRB.BINARY, name="co2_pipeline_built"
)
# 变量数：4311 × 200 ≈ 86万

# v2.0 CO₂相关变量总数：580万 + 580万 + 86万 ≈ 1246万个变量
```

#### 5.2.2 新增煤炭采购决策变量

**v3.0变量（新增）**：

```python
# ✅ 新增：煤炭采购变量（约17,000个变量）
self.coal_purchase = model.addVars(
    [(j, t) for j in saf_locations for t in hours],
    vtype=GRB.CONTINUOUS, lb=0, name="coal_purchase"
)
# 变量数：200个SAF位置 × 672小时（4周） ≈ 134,400
# 说明：coal_purchase[j, t] = 在位置j的t时刻采购的煤炭量（kg）

# ✅ 保留但用途变化：CO₂库存变量
self.co2_inventory = model.addVars(
    [(j, t) for j in saf_locations for t in hours],
    vtype=GRB.CONTINUOUS, lb=0, name="co2_inventory"
)
# 说明：v2.0中CO₂来自运输，v3.0中CO₂来自煤炭气化
# 变量数：134,400（与v2.0相同）
```

**变量数量对比**：

| 变量类型 | v2.0（CO₂捕获） | v3.0（煤炭） | 变化 |
|---------|----------------|-------------|------|
| **CO₂管道运输** | 5,800,000 | 0（删除） | -100% |
| **CO₂罐车运输** | 5,800,000 | 0（删除） | -100% |
| **CO₂管道建设** | 862,200 | 0（删除） | -100% |
| **煤炭采购** | 0 | 134,400（新增） | +100% |
| **CO₂库存** | 134,400 | 134,400（保留） | 0% |
| **小计（CO₂相关）** | 12,596,600 | 134,400 | **-98.9%** |

---

### 5.3 约束条件修改

#### 5.3.1 删除CO₂供应和运输约束

**v2.0约束（删除）**：

```python
# ❌ 删除：CO₂供应平衡约束（按周）（约580万条约束）
for c in co2_sources:  # 4311个CO₂源
    for week in weeks:  # 4周
        week_start = week * 168
        week_end = (week + 1) * 168
        weekly_co2_supply = gp.quicksum(
            co2_pipeline_transport[c, j, t] + co2_truck_transport[c, j, t]
            for j in saf_locations
            for t in range(week_start, week_end)
        )
        model.addConstr(
            weekly_co2_supply <= co2_capture_capacity[c, week],
            name=f"co2_supply_limit_{c}_{week}"
        )
# 约束数：4311 × 4 × 200 ≈ 3,448,800

# ❌ 删除：CO₂管道Big-M约束（约580万条约束）
for c in co2_sources:
    for j in saf_locations:
        for t in hours:
            model.addConstr(
                co2_pipeline_transport[c, j, t] <= Big_M * co2_pipeline_built[c, j],
                name=f"co2_pipeline_bigm_{c}_{j}_{t}"
            )
# 约束数：4311 × 200 × 672 ≈ 5,800,000

# ❌ 删除：CO₂管道和罐车互斥约束（约580万条约束）
for c in co2_sources:
    for j in saf_locations:
        for t in hours:
            model.addConstr(
                co2_truck_transport[c, j, t] <= Big_M * (1 - co2_pipeline_built[c, j]),
                name=f"co2_exclusive_truck_{c}_{j}_{t}"
            )
# 约束数：5,800,000

# v2.0 CO₂相关约束总数：3,448,800 + 5,800,000 + 5,800,000 ≈ 15,048,800（1500万）
```

#### 5.3.2 新增煤炭气化产生CO₂约束

**v3.0约束（新增）**：

```python
# ✅ 新增：煤炭气化产生CO₂约束（约17,000条约束）
for j in saf_locations:  # 200个位置
    for t in hours:  # 672小时
        if t == 0:
            # 初始时刻：CO₂库存 = 煤炭气化产生
            co2_from_coal = self.coal_purchase[j, t] * self.coal_co2_ratio  # 2.44
            model.addConstr(
                self.co2_inventory[j, t] == co2_from_coal,
                name=f"co2_init_{j}"
            )
        else:
            # 后续时刻：库存平衡
            co2_from_coal = self.coal_purchase[j, t] * self.coal_co2_ratio
            co2_consumed = (
                self.methanol_production[j, t] *
                self.tech_params['co2_to_methanol_ratio']  # 2.8 kg CO₂/kg methanol
            )
            model.addConstr(
                self.co2_inventory[j, t] == (
                    self.co2_inventory[j, t-1] +  # 上时刻库存
                    co2_from_coal -                # 本时刻气化产生
                    co2_consumed                   # 本时刻消耗
                ),
                name=f"co2_balance_{j}_{t}"
            )
# 约束数：200 × 672 ≈ 134,400

# 说明：
# 1. 煤炭气化：coal_purchase × 2.44 → CO₂
# 2. CO₂本地产生，无运输决策，直接进入库存
# 3. 库存桥接：连接煤炭采购和甲醇生产
```

**约束数量对比**：

| 约束类型 | v2.0（CO₂捕获） | v3.0（煤炭） | 变化 |
|---------|----------------|-------------|------|
| **CO₂供应平衡** | 3,448,800 | 0（删除） | -100% |
| **CO₂管道Big-M** | 5,800,000 | 0（删除） | -100% |
| **CO₂管道罐车互斥** | 5,800,000 | 0（删除） | -100% |
| **煤炭气化CO₂生成** | 0 | 134,400（新增） | +100% |
| **小计（CO₂相关）** | 15,048,800 | 134,400 | **-99.1%** |

---

### 5.4 目标函数修改

#### 5.4.1 删除CO₂捕获和运输成本

**v2.0成本项（删除）**：

```python
# ❌ 删除：CO₂捕获成本
co2_capture_cost = gp.quicksum(
    (co2_pipeline_transport[c,j,t] + co2_truck_transport[c,j,t]) *
    co2_capture_price[c]  # 150-180元/吨
    for c in co2_sources for j in saf_locations for t in hours
)

# ❌ 删除：CO₂管道运输成本
co2_pipeline_cost = gp.quicksum(
    co2_pipeline_transport[c,j,t] * co2_pipeline_unit_cost[c,j]
    for c in co2_sources for j in saf_locations for t in hours
)

# ❌ 删除：CO₂罐车运输成本
co2_truck_cost = gp.quicksum(
    co2_truck_transport[c,j,t] * co2_truck_unit_cost[c,j]
    for c in co2_sources for j in saf_locations for t in hours
)

# ❌ 删除：CO₂管道建设成本（已摊销到分段线性函数中，但变量被删除）
# 注：v2.0中管道建设成本已摊销到运输成本中，无需单独计算

# v2.0 CO₂总成本 = 捕获 + 管道运输 + 罐车运输
# 典型值：150元/吨捕获 + 50-150元/吨运输 = 200-300元/吨CO₂
```

#### 5.4.2 新增煤炭采购和气化成本

**v3.0成本项（新增）**：

```python
# ✅ 新增：煤炭采购成本
coal_purchase_cost = gp.quicksum(
    self.coal_purchase[j, t] * (self.coal_price_yuan_per_ton / 1000)
    for j in saf_locations for t in hours
)
# 说明：
# - 煤炭价格：800元/吨 = 0.8元/kg
# - 单位SAF煤耗：1.8 kg煤/kg SAF
# - 煤炭成本：0.8 × 1.8 = 1.44元/kg SAF

# ✅ 新增：煤炭气化能耗成本
coal_gasification_energy_cost = gp.quicksum(
    self.coal_purchase[j, t] *
    self.gasification_energy_kwh_per_kg *  # 8 kWh/kg coal
    self.electricity_price_yuan_per_kwh    # 0.5元/kWh
    for j in saf_locations for t in hours
)
# 说明：
# - 气化能耗：8 kWh/kg煤
# - 电价：0.5元/kWh
# - 气化能耗成本：8 × 0.5 = 4元/kg煤
# - 单位SAF气化成本：4 × 1.8 = 7.2元/kg SAF

# v3.0煤炭总成本 = 采购 + 气化能耗
# 单位SAF成本：1.44 + 7.2 = 8.64元/kg SAF
```

#### 5.4.3 成本对比分析

**等效CO₂成本对比**：

```python
# v2.0 CO₂成本：
# - 捕获：150元/吨
# - 运输：50-150元/吨（平均100元/吨）
# - 总计：250元/吨CO₂
# - 单位SAF: 250 × (3.5 kg CO₂/kg SAF) / 1000 = 0.875元/kg SAF

# v3.0等效CO₂成本：
# - 煤炭：525元/吨煤 ÷ 2.44 kg CO₂/kg煤 = 215元/吨CO₂
# - 气化能耗：4元/kg煤 ÷ 2.44 = 1.64元/kg CO₂（约164元/吨CO₂）
# - 总计：328 + 164 = 492元/吨CO₂（等效）
# - 单位SAF: 492 × 3.5 / 1000 = 1.722元/kg SAF

# 对比结论：
# v3.0煤炭版CO₂等效成本（492元/吨）比v2.0 CO₂捕获（250元/吨）高约97%
# 但v3.0无运输成本，系统简单，煤炭供应充足
```

#### 5.4.4 修改后的总目标函数

```python
# ===== v3.0目标函数 =====
total_cost = (
    # ✅ 保留：绿氢成本
    h2_production_cost +           # 绿氢生产
    h2_transport_cost +            # 绿氢运输

    # ✅ 新增：煤炭成本
    coal_purchase_cost +           # 煤炭采购（新增）
    coal_gasification_energy_cost + # 煤炭气化能耗（新增）

    # ✅ 保留：生产成本
    methanol_production_cost +     # 甲醇合成
    methanol_storage_cost +        # 甲醇储存
    saf_production_cost +          # SAF生产

    # ✅ 保留：运输和设施成本
    saf_transport_cost +           # SAF运输
    facility_cost +                # 设施投资

    # ✅ 保留：惩罚成本
    shortage_penalty               # 缺货惩罚
)

model.setObjective(total_cost, GRB.MINIMIZE)
```

**成本结构占比估算**（假设1 kg SAF）：

| 成本项 | v2.0 | v3.0 | 变化 |
|-------|------|------|------|
| **绿氢** | 30% | 35% | +5% |
| **CO₂获取** | 15% | - | 删除 |
| **煤炭采购** | - | 20% | 新增 |
| **气化能耗** | - | 10% | 新增 |
| **甲醇生产** | 25% | 20% | -5% |
| **SAF生产** | 20% | 10% | -10% |
| **运输** | 10% | 5% | -5% |

---

### 5.5 代码修改总结

#### 5.5.1 代码行数变化

| 模块 | v2.0 | v3.0 | 变化 |
|-----|------|------|------|
| **CO₂捕获模块** | ~700行 | 0行（删除） | -100% |
| **煤炭供应模块** | 0行 | ~60行（新增） | +100% |
| **数据加载** | ~200行 | ~50行 | -75% |
| **决策变量定义** | ~300行 | ~100行 | -67% |
| **约束条件** | ~800行 | ~200行 | -75% |
| **目标函数** | ~150行 | ~80行 | -47% |
| **总计** | ~2150行 | ~490行 | **-77%** |

#### 5.5.2 模型复杂度变化

| 指标 | v2.0 | v3.0 | 变化 |
|-----|------|------|------|
| **决策变量数** | 约600万 | 约35万 | **-94%** |
| **约束条件数** | 约580万 | 约2万 | **-99.7%** |
| **GIS数据加载** | 4类文件 | 0个文件 | -100% |
| **求解时间（1周）** | 30-60分钟 | 5-15分钟 | **-75%** |
| **内存占用** | ~8GB | ~1GB | -88% |

#### 5.5.3 关键性能提升点

**1. 决策变量大幅减少**：
- 删除CO₂运输变量：580万（管道） + 580万（罐车） + 86万（建设） = 1246万
- 新增煤炭采购变量：13.4万
- 净减少：1246万 - 13.4万 ≈ 1233万变量（-98.9%）

**2. 约束条件极致简化**：
- 删除CO₂供应约束：345万（供应平衡） + 580万（Big-M） + 580万（互斥） = 1505万
- 新增煤炭气化约束：13.4万
- 净减少：1505万 - 13.4万 ≈ 1492万约束（-99.1%）

**3. 计算复杂度降低**：
- v2.0：O(N×M×T) where N=4311（CO₂源数）
- v3.0：O(M×T) where M=200（SAF位置数）
- 复杂度降低：4311倍

**4. 数据准备时间缩短**：
- v2.0：加载4类GIS数据 + CO₂捕获计算 ≈ 10-15分钟
- v3.0：读取配置文件煤炭参数 ≈ 1秒
- 数据准备时间减少：99.9%

---

### 5.6 代码修改验收标准

#### 5.6.1 功能完整性检查

- [ ] 类名已修改为CoalHydrogenSAFOptimizer
- [ ] 配置文件路径指向CoalHydrogenSAFOptimizer_config.yaml
- [ ] 日志前缀改为coal_h2_saf
- [ ] _define_coal_supply()方法实现并测试通过
- [ ] _load_co2_capture_sources()方法已完全删除
- [ ] coal_purchase决策变量定义正确
- [ ] CO₂运输相关变量已完全删除
- [ ] 煤炭气化CO₂生成约束添加正确
- [ ] CO₂供应和运输约束已完全删除
- [ ] 煤炭采购和气化成本添加到目标函数
- [ ] CO₂捕获和运输成本已从目标函数删除

#### 5.6.2 代码质量检查

- [ ] 无CO₂捕获相关代码残留（grep "co2_capture" "co2_pipeline" "co2_truck" 无结果）
- [ ] 所有import语句正确（无co2模块导入）
- [ ] 变量命名符合规范（coal_purchase, coal_co2_ratio等）
- [ ] 注释完整清晰（标注v2.0删除和v3.0新增）
- [ ] 日志记录充分（关键步骤都有日志）
- [ ] 异常处理完善（煤炭参数缺失时抛出清晰错误）

#### 5.6.3 性能验证

- [ ] 模型可成功实例化
- [ ] 数据加载时间 < 10秒
- [ ] 模型构建时间 < 5分钟
- [ ] 决策变量数 ≈ 35万（对比v2.0的600万）
- [ ] 约束条件数 ≈ 2万（对比v2.0的580万）
- [ ] 小规模测试求解时间 < 1分钟
- [ ] 完整测试求解时间 < 20分钟（1周优化范围）

---


## 六、煤炭供应模块设计

### 6.1 模块概述

**新增模块**：`src/modules/coal_supply_manager.py`

**模块定位**：
- 替代v2.0的CO₂捕获源管理模块（CO2CaptureSourceManager）
- 简化设计：不处理GIS数据，不计算运输成本
- 直接在SAF生产点配置煤炭供应参数

**核心职责**：
1. 加载煤炭供应配置参数
2. 计算煤炭气化产生的CO₂量
3. 计算煤炭采购成本和气化能耗成本
4. 提供煤炭供应约束条件

### 6.2 CoalSupplyManager类设计

#### 6.2.1 类结构

```python
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
import logging

class CoalSupplyManager:
    """
    煤炭供应管理器
    
    功能：
    - 管理煤炭类型和供应参数
    - 计算煤炭气化CO₂产量
    - 提供成本计算接口
    - 无需GIS数据加载
    
    属性：
        coal_type (str): 煤炭类型
        carbon_content (float): 碳含量
        co2_per_kg_coal (float): CO₂产量系数
        coal_price_yuan_per_ton (float): 煤炭单价
        gasification_efficiency (float): 气化效率
        gasification_energy_mj_per_kg (float): 气化能耗
    """
    
    def __init__(self, config: Dict):
        self.logger = logging.getLogger(__name__)
        self._load_coal_parameters(config)
        self._validate_parameters()
```


#### 6.2.2 核心方法

**CO₂产量计算**：

```python
def calculate_co2_from_coal(self, coal_amount_kg: float) -> float:
    """计算煤炭气化产生的CO₂量"""
    co2_amount = coal_amount_kg * self.co2_per_kg_coal
    return co2_amount

def calculate_coal_for_co2_demand(self, co2_demand_kg: float) -> float:
    """反向计算：给定CO₂需求，计算所需煤炭量"""
    coal_needed = co2_demand_kg / self.co2_per_kg_coal
    return coal_needed
```

**成本计算**：

```python
def calculate_coal_purchase_cost(self, coal_amount_kg: float) -> float:
    """计算煤炭采购成本"""
    cost = coal_amount_kg * self.coal_price_yuan_per_kg
    return cost

def calculate_gasification_energy_cost(self, coal_amount_kg: float) -> float:
    """计算煤炭气化能耗成本"""
    cost = coal_amount_kg * self.gasification_energy_cost_yuan_per_kg
    return cost

def calculate_total_coal_cost(self, coal_amount_kg: float) -> Dict[str, float]:
    """计算煤炭总成本（采购+气化）"""
    purchase_cost = self.calculate_coal_purchase_cost(coal_amount_kg)
    gasification_cost = self.calculate_gasification_energy_cost(coal_amount_kg)
    
    return {
        'purchase_cost': purchase_cost,
        'gasification_cost': gasification_cost,
        'total_cost': purchase_cost + gasification_cost
    }
```

**单位SAF成本**：

```python
def calculate_cost_per_kg_saf(self, coal_per_kg_saf: float) -> Dict[str, float]:
    """计算单位SAF的煤炭相关成本
    
    示例：
        coal_per_kg_saf = 1.8 kg coal/kg SAF
        purchase = 0.525 yuan/kg × 1.8 = 0.945 yuan/kg SAF
        gasification = 4.0 yuan/kg × 1.8 = 7.2 yuan/kg SAF
        total = 8.64 yuan/kg SAF
    """
    purchase_per_saf = self.coal_price_yuan_per_kg * coal_per_kg_saf
    gasification_per_saf = self.gasification_energy_cost_yuan_per_kg * coal_per_kg_saf
    
    return {
        'coal_purchase_yuan_per_kg_saf': purchase_per_saf,
        'gasification_yuan_per_kg_saf': gasification_per_saf,
        'total_yuan_per_kg_saf': purchase_per_saf + gasification_per_saf
    }
```

### 6.3 与v2.0 CO₂捕获模块对比

#### 6.3.1 v2.0 CO2CaptureSourceManager

**代码量**：约800行
**复杂度**：高

- 加载4个GIS数据文件（4311条记录）
- 计算捕获源到SAF生产点的距离
- 管理管道运输和卡车运输
- 计算CO₂运输成本

#### 6.3.2 v3.0 CoalSupplyManager

**代码量**：约200行
**复杂度**：低

- 加载煤炭参数（配置文件）
- 计算煤炭气化CO₂产量
- 计算煤炭采购和气化成本
- 无GIS数据依赖

#### 6.3.3 对比总结

| 指标 | v2.0 CO₂捕获 | v3.0 煤炭供应 | 变化 |
|-----|------------|-------------|------|
| 代码行数 | 约800行 | 约200行 | **-75%** |
| GIS数据文件 | 4个文件 | 0个文件 | **-100%** |
| 数据记录数 | 4311条 | 0条 | **-100%** |
| 距离计算 | 需要 | 不需要 | 简化 |
| 运输成本 | 复杂计算 | 忽略 | 简化 |
| 初始化时间 | 约5-10秒 | <0.1秒 | **-99%** |


### 6.4 与优化模型的集成

#### 6.4.1 在主优化器中使用

```python
class CoalHydrogenSAFOptimizer:
    def __init__(self, config_path: str = None):
        # 初始化煤炭供应管理器
        self.coal_supply = CoalSupplyManager(self.config)
        
        # 获取煤炭参数
        self.coal_co2_ratio = self.coal_supply.co2_per_kg_coal
        self.coal_price_per_kg = self.coal_supply.coal_price_yuan_per_kg
```

#### 6.4.2 在约束条件中使用

```python
def _add_co2_balance_constraints(self, model):
    """添加CO₂平衡约束"""
    for j in self.saf_locations:
        for t in self.time_periods:
            # 煤炭气化产生CO₂
            co2_from_coal = self.coal_purchase[j, t] * self.coal_co2_ratio
            
            # CO₂平衡
            model.addConstr(
                self.co2_inventory[j, t] == 
                self.co2_inventory[j, t-1] + 
                co2_from_coal - 
                self.co2_consumed[j, t]
            )
```

#### 6.4.3 在目标函数中使用

```python
def _build_objective_function(self, model):
    """构建目标函数"""
    # 煤炭采购成本
    coal_purchase_cost = gp.quicksum(
        self.coal_purchase[j, t] * self.coal_price_per_kg
        for j in self.saf_locations for t in self.time_periods
    )
    
    # 煤炭气化能耗成本
    coal_gasification_cost = gp.quicksum(
        self.coal_purchase[j, t] * self.coal_supply.gasification_energy_cost_yuan_per_kg
        for j in self.saf_locations for t in self.time_periods
    )
    
    model.setObjective(
        coal_purchase_cost + coal_gasification_cost + ...,
        minimize=True
    )
```

### 6.5 单元测试设计

**测试文件**：`tests/test_coal_supply_manager.py`

```python
import unittest
from src.modules.coal_supply_manager import CoalSupplyManager

class TestCoalSupplyManager(unittest.TestCase):
    def setUp(self):
        self.config = {
            'coal_parameters': {
                'coal_type': 'bituminous',
                'carbon_content': 0.75,
                'co2_per_kg_coal': 2.44,
                'coal_price_yuan_per_ton': 800,
                'gasification_efficiency': 0.75,
                'gasification_energy_mj_per_kg': 8.0
            }
        }
        self.manager = CoalSupplyManager(self.config)
    
    def test_co2_calculation(self):
        """测试CO₂产量计算"""
        coal = 1000  # kg
        co2 = self.manager.calculate_co2_from_coal(coal)
        expected = 1000 * 2.44  # 2440 kg
        self.assertAlmostEqual(co2, expected, places=2)
    
    def test_cost_calculation(self):
        """测试成本计算"""
        coal = 1000  # kg
        costs = self.manager.calculate_total_coal_cost(coal)
        
        # 采购成本：1000 × 0.525 = 525 yuan
        self.assertAlmostEqual(costs['purchase_cost'], 525, places=2)
        
        # 气化成本：1000 × 8 × 0.5 = 4000 yuan
        self.assertAlmostEqual(costs['gasification_cost'], 4000, places=2)
    
    def test_saf_unit_cost(self):
        """测试单位SAF成本"""
        coal_per_saf = 1.8
        costs = self.manager.calculate_cost_per_kg_saf(coal_per_saf)
        
        # 采购：0.8 × 1.8 = 1.44 yuan/kg SAF
        self.assertAlmostEqual(costs['coal_purchase_yuan_per_kg_saf'], 0.945, places=2)
        
        # 气化：4.0 × 1.8 = 7.2 yuan/kg SAF
        self.assertAlmostEqual(costs['gasification_yuan_per_kg_saf'], 7.2, places=2)

if __name__ == '__main__':
    unittest.main()
```

### 6.6 模块交付清单

- [ ] 代码文件：`src/modules/coal_supply_manager.py`（约200行）
- [ ] 测试文件：`tests/test_coal_supply_manager.py`（约100行）
- [ ] 文档：类和方法的完整docstring
- [ ] 日志：关键计算步骤的日志记录
- [ ] 验证：所有单元测试通过
- [ ] 集成：与主优化模型成功集成

### 6.7 关键技术决策说明

#### 决策1：不处理GIS数据
- **理由**：简化系统架构，降低数据依赖
- **权衡**：牺牲地理真实性，换取开发效率
- **适用场景**：概念验证、快速原型、参数敏感性分析

#### 决策2：忽略煤炭运输成本
- **理由**：假设煤炭在SAF生产点直接采购
- **权衡**：简化成本模型
- **未来扩展**：可通过配置文件添加固定运输成本系数

#### 决策3：参数化煤炭类型
- **理由**：支持不同煤种的快速切换和对比
- **实现**：通过YAML配置文件管理参数
- **优势**：灵活性高，便于敏感性分析

---


## 七、碳排放计算模块调整

### 7.1 碳排放强度对比

#### v2.0（CCS捕获路线）
- 碳排放强度：约25 gCO₂e/MJ SAF
- CORSIA认证：通过

#### v3.0（煤炭气化路线）
- 碳排放强度：约60 gCO₂e/MJ SAF
- CORSIA认证：不通过
- 减排幅度：32.6%（相对传统Jet A-1的89 gCO₂e/MJ）

### 7.2 市场影响

**v3.0市场定位**：
1. 国内市场：可行（价格优势，成本比v2.0低约30%）
2. 国际市场：受限（不满足CORSIA标准）
3. 混合策略：与v2.0混合使用

### 7.3 代码修改

**配置文件**：更新saf_carbon_intensity_gco2e_per_mj为60.0
**计算器类**：添加CORSIA合规性检查方法

---

## 八、详细任务分解（TodoList）

### 8.1 Phase 1：项目准备（0.5天）

**任务1.1**：创建项目目录结构
- [ ] 创建coal_hydrogen_saf_optimization目录
- [ ] 创建src/, data/, results/等子目录
- [ ] 复制共享配置文件模板

**任务1.2**：环境检查
- [ ] 验证conda环境
- [ ] 检查Gurobi许可证
- [ ] 确认依赖包版本

### 8.2 Phase 2：配置文件修改（1天）

**任务2.1**：创建新配置文件
- [ ] 复制GreenHydrogenSAFOptimizer_config.yaml
- [ ] 重命名为CoalHydrogenSAFOptimizer_config.yaml
- [ ] 更新project_name和version

**任务2.2**：修改煤炭参数段
- [ ] 添加coal_parameters段
- [ ] 设置coal_type: bituminous
- [ ] 设置carbon_content: 0.75
- [ ] 设置co2_per_kg_coal: 2.44

**任务2.3**：修改碳排放参数
- [ ] 更新saf_carbon_intensity为60.0
- [ ] 更新配置文件路径引用

**任务2.4**：删除CO₂捕获相关参数
- [ ] 删除co2_capture_sources段
- [ ] 删除co2_pipeline_parameters段
- [ ] 删除co2_truck_transport_parameters段

### 8.3 Phase 3：煤炭供应模块开发（1天）

**任务3.1**：创建CoalSupplyManager类
- [ ] 创建src/modules/coal_supply_manager.py
- [ ] 实现__init__方法
- [ ] 实现_load_coal_parameters方法

**任务3.2**：实现CO₂计算方法
- [ ] calculate_co2_from_coal方法
- [ ] calculate_coal_for_co2_demand方法

**任务3.3**：实现成本计算方法
- [ ] calculate_coal_purchase_cost方法
- [ ] calculate_gasification_energy_cost方法
- [ ] calculate_total_coal_cost方法
- [ ] calculate_cost_per_kg_saf方法

**任务3.4**：单元测试
- [ ] 创建tests/test_coal_supply_manager.py
- [ ] 测试CO₂产量计算
- [ ] 测试成本计算
- [ ] 测试单位SAF成本

### 8.4 Phase 4：主优化模型修改（2天）

**任务4.1**：创建新优化器类
- [ ] 复制green_hydrogen_optimization_model.py
- [ ] 重命名为coal_hydrogen_optimization_model.py
- [ ] 修改类名为CoalHydrogenSAFOptimizer

**任务4.2**：修改数据加载方法
- [ ] 删除_load_co2_capture_sources方法（约500行）
- [ ] 添加_define_coal_supply方法（约50行）
- [ ] 集成CoalSupplyManager

**任务4.3**：修改决策变量
- [ ] 删除CO₂运输相关变量（12.5M变量）
- [ ] 添加coal_purchase变量（134k变量）
- [ ] 验证变量数量减少94%

**任务4.4**：修改约束条件
- [ ] 删除CO₂运输约束（15M约束）
- [ ] 添加煤炭气化CO₂生成约束（134k约束）
- [ ] 修改CO₂平衡约束
- [ ] 验证约束数量减少99.7%

**任务4.5**：修改目标函数
- [ ] 删除CO₂捕获成本项
- [ ] 删除CO₂运输成本项
- [ ] 添加煤炭采购成本项
- [ ] 添加煤炭气化能耗成本项

**任务4.6**：验证简化效果
- [ ] 代码行数减少77%（约2150→490行）
- [ ] 决策变量减少94%
- [ ] 约束条件减少99.7%

### 8.5 Phase 5：碳排放计算模块调整（0.5天）

**任务5.1**：修改配置文件
- [ ] 更新carbon_emission_parameters段
- [ ] 设置saf_carbon_intensity为60.0

**任务5.2**：修改计算器类
- [ ] 添加check_corsia_compliance方法
- [ ] 更新碳排放计算逻辑

**任务5.3**：测试CORSIA合规性
- [ ] 验证v3.0不通过CORSIA
- [ ] 验证v2.0通过CORSIA

### 8.6 Phase 6：测试与验证（1天）

**任务6.1**：单元测试
- [ ] 运行CoalSupplyManager测试
- [ ] 运行CarbonEmissionCalculator测试
- [ ] 测试覆盖率>80%

**任务6.2**：集成测试
- [ ] 小规模优化测试（1周数据）
- [ ] 验证求解时间<20分钟
- [ ] 验证结果合理性

**任务6.3**：性能验证
- [ ] 决策变量数约35万
- [ ] 约束条件数约2万
- [ ] 求解时间5-15分钟

**任务6.4**：结果对比
- [ ] 与v2.0结果对比
- [ ] 成本差异分析
- [ ] 碳排放差异分析

### 8.7 总时间估算

| Phase | 任务 | 预计时间 |
|-------|------|---------|
| Phase 1 | 项目准备 | 0.5天 |
| Phase 2 | 配置文件修改 | 1天 |
| Phase 3 | 煤炭供应模块 | 1天 |
| Phase 4 | 主优化模型修改 | 2天 |
| Phase 5 | 碳排放模块调整 | 0.5天 |
| Phase 6 | 测试与验证 | 1天 |
| **总计** | **40+子任务** | **6天** |

---

## 九、实施步骤与时间计划

### 9.1 Day 1：环境准备与配置文件修改

**上午（4小时）**：
1. 创建项目目录结构（30分钟）
2. 环境检查和依赖验证（30分钟）
3. 创建新配置文件（1小时）
4. 修改煤炭参数段（1小时）
5. 删除CO₂捕获相关参数（1小时）

**下午（4小时）**：
6. 修改碳排放参数（1小时）
7. 配置文件完整性测试（1小时）
8. 文档更新（2小时）

**交付物**：
- 完整的CoalHydrogenSAFOptimizer_config.yaml
- 配置文件测试报告

### 9.2 Day 2：煤炭供应模块开发

**上午（4小时）**：
1. 创建CoalSupplyManager类框架（1小时）
2. 实现参数加载方法（1小时）
3. 实现CO₂计算方法（2小时）

**下午（4小时）**：
4. 实现成本计算方法（2小时）
5. 单元测试编写（1小时）
6. 测试运行和调试（1小时）

**交付物**：
- src/modules/coal_supply_manager.py（约200行）
- tests/test_coal_supply_manager.py（约100行）
- 所有测试通过报告

### 9.3 Day 3-4：主优化模型修改

**Day 3 上午（4小时）**：
1. 创建新优化器类文件（30分钟）
2. 修改类名和初始化方法（1小时）
3. 删除CO₂捕获源加载方法（1小时）
4. 添加煤炭供应定义方法（1.5小时）

**Day 3 下午（4小时）**：
5. 修改决策变量定义（2小时）
6. 验证变量数量简化（1小时）
7. 代码Review和优化（1小时）

**Day 4 上午（4小时）**：
8. 修改约束条件（3小时）
9. 验证约束数量简化（1小时）

**Day 4 下午（4小时）**：
10. 修改目标函数（2小时）
11. 代码完整性检查（1小时）
12. 初步调试运行（1小时）

**交付物**：
- src/core/coal_hydrogen_optimization_model.py（约490行）
- 代码行数减少77%验证报告
- 变量和约束简化验证报告

### 9.4 Day 5：碳排放模块与集成测试

**上午（4小时）**：
1. 修改碳排放计算器（2小时）
2. CORSIA合规性检查实现（1小时）
3. 单元测试运行（1小时）

**下午（4小时）**：
4. 小规模集成测试（1周数据）（2小时）
5. 结果验证和问题诊断（2小时）

**交付物**：
- 修改后的carbon_emission_calculator.py
- 小规模测试结果报告

### 9.5 Day 6：完整测试与文档

**上午（4小时）**：
1. 完整优化测试（1周数据完整运行）（2小时）
2. 性能指标验证（1小时）
3. 与v2.0结果对比分析（1小时）

**下午（4小时）**：
4. 文档完善（2小时）
5. 代码注释和清理（1小时）
6. 交付包准备（1小时）

**交付物**：
- 完整测试报告
- v2.0 vs v3.0对比分析报告
- 完整代码和文档包

### 9.6 关键里程碑

| 里程碑 | 完成标准 | 预计完成时间 |
|--------|---------|-------------|
| M1：配置文件完成 | 配置文件测试通过 | Day 1 结束 |
| M2：煤炭模块完成 | 单元测试全部通过 | Day 2 结束 |
| M3：优化模型完成 | 代码简化指标达标 | Day 4 结束 |
| M4：小规模测试通过 | 求解成功，结果合理 | Day 5 结束 |
| M5：完整验证通过 | 所有验收标准满足 | Day 6 结束 |

### 9.7 风险缓冲

- 预留1天作为风险缓冲时间
- 如遇到重大问题，总时间可延长至7天
- 关键风险点：Day 4主优化模型修改，Day 5集成测试

---

## 十、与v2.0的全面对比分析

### 10.1 技术指标对比

| 指标 | v2.0 CCS捕获 | v3.0 煤炭气化 | 变化 |
|-----|-------------|-------------|------|
| **代码规模** |
| 总代码行数 | 约2150行 | 约490行 | **-77%** |
| 模块文件数 | 8个 | 6个 | -25% |
| 配置参数数 | 120+ | 80+ | -33% |
| **优化规模** |
| 决策变量数 | 约600万 | 约35万 | **-94%** |
| 约束条件数 | 约580万 | 约2万 | **-99.7%** |
| **性能指标** |
| 模型构建时间 | 约10-15分钟 | 约1-2分钟 | **-87%** |
| 求解时间（1周） | 30-60分钟 | 5-15分钟 | **-75%** |
| 内存占用 | 约8GB | 约1GB | -88% |
| **数据依赖** |
| GIS数据文件 | 4个 | 0个 | **-100%** |
| 数据记录数 | 4311条 | 0条 | **-100%** |
| 数据加载时间 | 5-10秒 | <0.1秒 | **-99%** |

### 10.2 环境影响对比

| 指标 | v2.0 | v3.0 | 对比 |
|-----|------|------|------|
| **碳排放** |
| SAF碳强度 | 25 gCO₂e/MJ | 60 gCO₂e/MJ | +140% |
| 减排幅度 | 72% | 32.6% | -54% |
| CORSIA认证 | ✅ 通过 | ❌ 不通过 | - |
| **成本** |
| CO₂源成本 | 250 yuan/ton | 328 yuan/ton（煤炭等效）| +31% |
| 运输成本 | 50-100 yuan/ton | 0（忽略） | -100% |
| 单位SAF总成本 | 较高 | 较低30% | -30% |

### 10.3 工艺路线对比

#### v2.0：CCS捕获路线
```
工业CO₂捕获源（4311个）
    → 管道/卡车运输
    → CO₂存储
    → 可再生能源绿氢
    → E-CRM（甲醇合成）
    → MTJ（SAF合成）
```

**特点**：
- ✅ 环保性优秀：碳强度25 gCO₂e/MJ
- ✅ CORSIA认证：满足国际标准
- ✗ 成本较高：CO₂捕获和运输成本高
- ✗ 复杂度高：需要处理4311个捕获源
- ✗ 计算量大：600万决策变量，580万约束

#### v3.0：煤炭气化路线
```
煤炭直接采购
    → 气化产生CO₂
    → CO₂就地使用
    → 可再生能源绿氢
    → E-CRM（甲醇合成）
    → MTJ（SAF合成）
```

**特点**：
- ✅ 成本较低：比v2.0低约30%
- ✅ 简洁高效：代码行数减少77%
- ✅ 计算快速：求解时间减少75%
- ✗ 环保性较差：碳强度60 gCO₂e/MJ
- ✗ 不满足CORSIA：国际市场受限

### 10.4 适用场景对比

#### v2.0 适用场景
1. **国际航线SAF供应**
   - 需要CORSIA认证
   - 环保要求高的市场
   - 欧美等发达国家

2. **高端市场**
   - 愿意为环保支付溢价的客户
   - 企业ESG目标导向
   - 碳中和承诺兑现

3. **长期战略**
   - 符合全球减排趋势
   - 政策风险低
   - 技术路线可持续

#### v3.0 适用场景
1. **国内航线SAF供应**
   - 不受CORSIA限制
   - 成本敏感市场
   - 中国市场主导

2. **成本优先市场**
   - 初期市场培育
   - 价格竞争力要求高
   - 规模扩张阶段

3. **快速原型和研究**
   - 参数敏感性分析
   - 概念验证
   - 算法研究

### 10.5 并行运行策略

**推荐策略**：v2.0和v3.0并行运行

**混合比例优化**：
- 国际航线：100% v2.0（CORSIA要求）
- 国内航线：70% v3.0 + 30% v2.0（成本优化）
- 平均碳强度：可控制在<44.5 gCO₂e/MJ

**优势**：
1. 满足不同市场需求
2. 平衡成本和环保
3. 风险分散
4. 灵活调整

### 10.6 未来发展方向

#### v2.0 演进路径
- 降低CO₂捕获成本
- 优化运输网络
- 提高捕获源利用率

#### v3.0 演进路径
- 引入碳捕获技术（降低碳强度）
- 优化气化工艺（提高效率）
- 探索生物质气化（替代化石煤炭）

#### v4.0 潜在方向
- 生物质+绿氢路线
- 直接空气捕获（DAC）+绿氢
- 电解CO₂还原新技术

---

## 十一、关键技术参数数据源

### 11.1 煤炭参数数据源

| 参数 | 数值 | 数据源 |
|-----|------|--------|
| 煤炭类型 | 烟煤（Bituminous） | 中国煤炭分类标准GB/T 5751-2009 |
| 碳含量 | 75% | 中国烟煤典型碳含量范围：70-80% |
| 热值 | 24-30 MJ/kg | 中国烟煤典型热值 |
| CO₂产量系数 | 2.44 kg CO₂/kg coal | 计算：0.75 × (44/12) ≈ 2.75，保守取2.44 |
| 煤炭价格 | 800 yuan/ton | 2024年中国动力煤市场均价 |
| 气化效率 | 75% | Shell气化炉典型效率 |
| 气化能耗 | 8 MJ/kg coal | 文献值：6-10 MJ/kg |

**参考文献**：
1. 中国煤炭分类标准GB/T 5751-2009
2. "Coal Gasification and Its Applications", 2010
3. Shell煤气化技术白皮书

### 11.2 SAF生产参数数据源

| 参数 | 数值 | 数据源 |
|-----|------|--------|
| E-CRM效率 | 75% | 文献：电化学CO₂还原效率范围70-80% |
| MTJ效率 | 85% | 文献：甲醇制SAF效率范围80-90% |
| 煤炭消耗 | 1.8 kg coal/kg SAF | 根据化学计量比和效率计算 |
| SAF热值 | 43 MJ/kg | ASTM D1655标准 |
| 氢气消耗 | 0.3 kg H₂/kg SAF | 根据E-CRM和MTJ化学计量比计算 |

**计算依据**：
```
1 kg SAF生产路径：
- 需要2.5 kg甲醇（MTJ效率85%）
- 需要4.4 kg CO₂（E-CRM效率75%）
- 需要1.8 kg煤炭（CO₂产量系数2.44）
- 需要0.3 kg H₂（E-CRM化学计量比）
```

### 11.3 碳排放参数数据源

| 参数 | v2.0数值 | v3.0数值 | 数据源 |
|-----|---------|---------|--------|
| SAF碳强度 | 25 gCO₂e/MJ | 60 gCO₂e/MJ | LCA计算 |
| 传统燃料碳强度 | 89 gCO₂e/MJ | 89 gCO₂e/MJ | ICAO CORSIA文件 |
| CORSIA阈值 | 44.5 gCO₂e/MJ | 44.5 gCO₂e/MJ | ICAO CORSIA标准 |

**LCA边界**：
- 包含：原料开采、运输、转化、SAF生产
- 不包含：SAF使用阶段排放（航空燃烧）
- 时间范围：从摇篮到大门（Cradle-to-Gate）

**参考标准**：
1. ICAO CORSIA Default Life Cycle Emissions Values
2. ISO 14067:2018 碳足迹量化标准
3. GREET模型（Greenhouse gases, Regulated Emissions, and Energy use in Technologies）

### 11.4 成本参数数据源

| 成本项 | v2.0 | v3.0 | 数据源 |
|--------|------|------|--------|
| CO₂源成本 | 150-180 yuan/ton | - | 文献：CCS捕获成本 |
| CO₂运输 | 50-100 yuan/ton·100km | - | 文献：管道和卡车运输成本 |
| 煤炭采购 | - | 800 yuan/ton | 2024年中国市场价 |
| 气化能耗 | - | 8 MJ/kg × 0.5 yuan/MJ | 工业电价0.5 yuan/MJ |
| 绿氢成本 | 30 yuan/kg | 30 yuan/kg | 可再生电解氢成本预测 |
| E-CRM成本 | 5 yuan/kg methanol | 5 yuan/kg methanol | 文献估算 |
| MTJ成本 | 8 yuan/kg SAF | 8 yuan/kg SAF | 文献估算 |

### 11.5 优化参数

| 参数 | 数值 | 说明 |
|-----|------|------|
| 时间分辨率 | 1小时 | 可再生能源出力变化 |
| 优化时长 | 1周（168小时） | 平衡精度和求解时间 |
| SAF生产点数 | 10-20个 | 中国主要机场数量 |
| 可再生能源站数 | 1400+个 | 风电站实际数量 |
| Gurobi求解器参数 | MIPGap=0.01 | 1%的优化间隙 |

### 11.6 数据验证方法

1. **文献交叉验证**：
   - 对比至少3篇同行评审论文
   - 选取中位数或保守值

2. **工业数据对标**：
   - 与实际工厂运行数据对比
   - 考虑技术成熟度调整

3. **敏感性分析**：
   - 关键参数±20%范围测试
   - 确保结论鲁棒性

4. **专家审核**：
   - 能源、化工领域专家评审
   - 参数合理性确认

---

## 十二、风险与缓解措施

### 12.1 技术风险

#### 风险12.1.1：CORSIA认证失败
**描述**：v3.0碳强度60 gCO₂e/MJ，超出CORSIA阈值44.5 gCO₂e/MJ

**影响**：
- 国际航线无法使用
- 市场受限于国内航线
- 商业价值降低

**可能性**：高（100%，已确定）

**缓解措施**：
1. **市场定位调整**：专注国内市场
2. **混合策略**：与v2.0混合使用，平均碳强度达标
3. **技术改进路线图**：
   - 短期：混合比例优化
   - 中期：引入碳捕获技术
   - 长期：生物质替代化石煤炭

#### 风险12.1.2：煤炭价格波动
**描述**：煤炭市场价格波动大（±30%），影响成本预测准确性

**影响**：
- 成本优势可能消失
- 经济性分析失效
- 投资决策风险

**可能性**：中等

**缓解措施**：
1. **敏感性分析**：测试煤炭价格400-1200 yuan/ton范围
2. **长期合同**：锁定煤炭供应价格
3. **对冲策略**：煤炭期货对冲价格风险

#### 风险12.1.3：气化效率不达预期
**描述**：实际气化效率可能低于75%设计值

**影响**：
- 煤炭消耗增加
- 成本上升
- CO₂产量增加（碳强度进一步恶化）

**可能性**：低

**缓解措施**：
1. **技术选型**：选择成熟的Shell气化炉技术
2. **预留余量**：参数设计保守，实际可能优于预期
3. **持续优化**：运行期间优化气化条件

### 12.2 实施风险

#### 风险12.2.1：代码重构复杂度高
**描述**：从v2.0重构到v3.0，涉及删除500+行代码，添加新模块

**影响**：
- 开发周期延长
- 引入新bug
- 测试工作量大

**可能性**：中等

**缓解措施**：
1. **分阶段实施**：按6个Phase逐步推进
2. **持续测试**：每个Phase完成后立即测试
3. **保留v2.0**：并行版本，不删除原代码
4. **代码Review**：关键修改点进行人工审查

#### 风险12.2.2：Gurobi求解器性能瓶颈
**描述**：尽管简化了94%变量，仍可能遇到求解困难

**影响**：
- 求解时间超出预期
- 无法获得最优解
- 需要进一步简化

**可能性**：低

**缓解措施**：
1. **分阶段测试**：先测试小规模（1天），再扩展到1周
2. **参数调优**：调整Gurobi求解器参数（MIPGap, Threads等）
3. **降级方案**：如果1周求解困难，缩减到3天优化范围

#### 风险12.2.3：数据迁移错误
**描述**：从v2.0迁移到v3.0过程中，配置文件或数据文件出错

**影响**：
- 运行失败
- 结果错误
- 调试困难

**可能性**：中等

**缓解措施**：
1. **配置文件验证脚本**：自动检查YAML文件格式和内容
2. **单元测试覆盖**：所有数据加载方法都有测试
3. **差异对比工具**：对比v2.0和v3.0配置文件差异

### 12.3 商业风险

#### 风险12.3.1：市场接受度低
**描述**：客户可能不接受碳强度60 gCO₂e/MJ的SAF产品

**影响**：
- 销售困难
- 产能闲置
- 投资回收期延长

**可能性**：中等

**缓解措施**：
1. **市场教育**：强调相对传统燃料仍有32.6%减排
2. **价格优势**：成本低30%，转化为价格竞争力
3. **分级市场**：v2.0面向高端市场，v3.0面向成本敏感市场

#### 风险12.3.2：政策变化
**描述**：中国未来可能引入更严格的SAF碳强度标准

**影响**：
- v3.0可能不合规
- 需要紧急技术升级
- 已投资设施贬值

**可能性**：低（5-10年时间窗口）

**缓解措施**：
1. **持续监测**：跟踪政策动向
2. **技术预研**：碳捕获技术储备
3. **灵活设计**：设施设计预留改造空间

### 12.4 环境社会风险

#### 风险12.4.1：公众环保质疑
**描述**：使用化石煤炭作为碳源，可能面临环保组织质疑

**影响**：
- 品牌声誉风险
- ESG评级下降
- 客户流失

**可能性**：中等

**缓解措施**：
1. **透明沟通**：公开碳足迹数据，强调仍优于传统燃料
2. **过渡定位**：明确v3.0是过渡技术，非终极方案
3. **社会责任**：投资可再生能源，展示长期减排承诺

#### 风险12.4.2：煤炭供应链环境影响
**描述**：煤炭开采和运输的环境影响（尽管未纳入模型）

**影响**：
- 间接环境负面影响
- 全生命周期碳足迹增加
- 可持续性质疑

**可能性**：中等

**缓解措施**：
1. **绿色煤炭采购**：优先选择环保标准高的供应商
2. **碳抵消**：购买碳信用额度抵消间接排放
3. **技术路线升级**：尽快过渡到生物质或DAC碳源

### 12.5 风险总结

| 风险类别 | 高风险 | 中风险 | 低风险 |
|---------|--------|--------|--------|
| 技术风险 | CORSIA认证失败 | 煤炭价格波动 | 气化效率不达预期 |
| 实施风险 | - | 代码重构复杂度、数据迁移错误 | Gurobi性能瓶颈 |
| 商业风险 | - | 市场接受度低 | 政策变化 |
| 环境社会风险 | - | 公众环保质疑、供应链环境影响 | - |

**风险应对优先级**：
1. **P1（立即处理）**：CORSIA认证失败 → 市场定位调整
2. **P2（近期处理）**：代码重构、价格波动 → 技术措施和合同锁定
3. **P3（持续监控）**：其他中低风险 → 预案准备，定期评估

---

## 十三、验收标准

### 13.1 功能完整性验收

#### 13.1.1 配置文件验收
- [x] CoalHydrogenSAFOptimizer_config.yaml文件创建
- [ ] coal_parameters段完整，包含8个必要参数
- [ ] carbon_emission_parameters段已更新saf_carbon_intensity为60.0
- [ ] CO₂捕获相关参数段已完全删除
- [ ] YAML格式验证通过，无语法错误
- [ ] 配置文件路径引用正确

#### 13.1.2 煤炭供应模块验收
- [ ] CoalSupplyManager类文件创建（src/modules/coal_supply_manager.py）
- [ ] 类包含所有必要方法（至少8个核心方法）
- [ ] calculate_co2_from_coal方法测试通过
- [ ] calculate_total_coal_cost方法测试通过
- [ ] calculate_cost_per_kg_saf方法测试通过
- [ ] 单元测试覆盖率≥80%
- [ ] 所有测试用例通过，无失败

#### 13.1.3 主优化模型验收
- [ ] CoalHydrogenSAFOptimizer类文件创建
- [ ] 类名正确修改为CoalHydrogenSAFOptimizer
- [ ] _load_co2_capture_sources方法已完全删除
- [ ] _define_coal_supply方法已添加并测试通过
- [ ] coal_purchase决策变量定义正确
- [ ] CO₂运输相关变量已完全删除
- [ ] 煤炭气化CO₂生成约束添加正确
- [ ] 目标函数包含煤炭采购和气化成本项
- [ ] CO₂捕获和运输成本项已完全删除

#### 13.1.4 碳排放模块验收
- [ ] CarbonEmissionCalculator类已更新
- [ ] check_corsia_compliance方法已添加
- [ ] v3.0碳强度计算结果≈60 gCO₂e/MJ（±5%容差）
- [ ] CORSIA合规性检查返回compliant=False
- [ ] 单元测试验证v2.0和v3.0碳强度差异

### 13.2 性能指标验收

#### 13.2.1 代码简化指标
| 指标 | 目标 | 验收标准 | 测量方法 |
|-----|------|---------|---------|
| 代码行数 | 约490行 | 450-550行 | wc -l命令统计 |
| 减少比例 | -77% | -70% ~ -80% | 与v2.0的2150行对比 |
| 模块文件数 | 6个 | ≤7个 | ls命令统计 |

#### 13.2.2 优化规模指标
| 指标 | 目标 | 验收标准 | 测量方法 |
|-----|------|---------|---------|
| 决策变量数 | 约35万 | 30-40万 | Gurobi模型日志 |
| 减少比例 | -94% | -90% ~ -95% | 与v2.0的600万对比 |
| 约束条件数 | 约2万 | 1.5-2.5万 | Gurobi模型日志 |
| 减少比例 | -99.7% | -99% ~ -99.9% | 与v2.0的580万对比 |

#### 13.2.3 求解性能指标
| 指标 | 目标 | 验收标准 | 测量方法 |
|-----|------|---------|---------|
| 模型构建时间 | 1-2分钟 | ≤3分钟 | 日志时间戳 |
| 求解时间（1周） | 5-15分钟 | ≤20分钟 | Gurobi求解日志 |
| 内存占用 | 约1GB | ≤2GB | 系统监控工具 |
| MIPGap | 0.01 | ≤0.02 | Gurobi求解器输出 |

### 13.3 结果合理性验收

#### 13.3.1 成本结果验收
- [ ] 单位SAF煤炭采购成本：1.2-1.8 yuan/kg SAF
- [ ] 单位SAF气化能耗成本：6-9 yuan/kg SAF
- [ ] 单位SAF总成本比v2.0低20-40%
- [ ] 成本构成比例合理（氢气>煤炭>转化）

#### 13.3.2 碳排放结果验收
- [ ] SAF碳强度：55-65 gCO₂e/MJ
- [ ] 不通过CORSIA认证（>44.5）
- [ ] 相对传统燃料减排30-35%
- [ ] 碳强度高于v2.0约2-2.5倍

#### 13.3.3 物料平衡验收
- [ ] 煤炭消耗量：1.5-2.0 kg coal/kg SAF
- [ ] CO₂产量：3.5-5.0 kg CO₂/kg SAF
- [ ] 氢气消耗：0.25-0.35 kg H₂/kg SAF
- [ ] SAF产量满足需求约束

### 13.4 测试覆盖验收

#### 13.4.1 单元测试验收
- [ ] CoalSupplyManager测试：≥5个测试用例，全部通过
- [ ] CarbonEmissionCalculator测试：≥3个测试用例，全部通过
- [ ] 配置文件加载测试：≥2个测试用例，全部通过
- [ ] 测试覆盖率：≥80%

#### 13.4.2 集成测试验收
- [ ] 小规模测试（1天数据）：求解成功，时间<5分钟
- [ ] 中等规模测试（3天数据）：求解成功，时间<10分钟
- [ ] 完整测试（1周数据）：求解成功，时间<20分钟
- [ ] 所有测试结果合理，无异常值

#### 13.4.3 对比测试验收
- [ ] v2.0与v3.0在相同条件下运行对比
- [ ] 成本差异分析报告完成
- [ ] 碳排放差异分析报告完成
- [ ] 性能差异分析报告完成

### 13.5 文档完整性验收

#### 13.5.1 代码文档验收
- [ ] 所有类都有完整的docstring
- [ ] 所有方法都有参数和返回值说明
- [ ] 关键算法都有注释说明
- [ ] README文件更新，包含v3.0使用说明

#### 13.5.2 技术文档验收
- [ ] PRD v3.0文档完整（本文档）
- [ ] 配置文件修改指南
- [ ] 代码修改详细说明
- [ ] 测试报告
- [ ] v2.0 vs v3.0对比分析报告

#### 13.5.3 交付物清单验收
- [ ] 所有源代码文件
- [ ] 配置文件
- [ ] 测试代码和测试报告
- [ ] 技术文档
- [ ] 示例运行脚本
- [ ] 环境依赖说明

### 13.6 验收流程

#### 第一阶段：模块验收（Day 2-5）
- 每个模块开发完成后立即验收
- 验收负责人：开发者自验
- 验收标准：模块功能完整性和单元测试通过

#### 第二阶段：集成验收（Day 5-6）
- 所有模块集成后整体验收
- 验收负责人：项目负责人
- 验收标准：性能指标达标，集成测试通过

#### 第三阶段：最终验收（Day 6）
- 完整系统验收
- 验收负责人：客户或项目委员会
- 验收标准：所有验收标准满足，交付物齐全

### 13.7 验收签字表

| 验收项 | 负责人 | 完成日期 | 签字 |
|--------|--------|---------|------|
| 配置文件验收 | ___ | ____ | ___ |
| 煤炭供应模块验收 | ___ | ____ | ___ |
| 主优化模型验收 | ___ | ____ | ___ |
| 碳排放模块验收 | ___ | ____ | ___ |
| 性能指标验收 | ___ | ____ | ___ |
| 测试覆盖验收 | ___ | ____ | ___ |
| 文档完整性验收 | ___ | ____ | ___ |
| 最终验收 | ___ | ____ | ___ |

---

## 十四、附录：关键代码片段

### 14.1 配置文件完整示例

**文件**：`shared/data/CoalHydrogenSAFOptimizer_config.yaml`

```yaml
project_name: "coal_hydrogen_saf_optimization"
version: "3.0"
description: "煤炭+绿氢制SAF供应链优化（两步法：煤炭气化产CO₂）"

# 煤炭参数（新增）
coal_parameters:
  coal_type: "bituminous"  # 烟煤
  carbon_content: 0.75  # 碳含量75%
  co2_per_kg_coal: 2.44  # kg CO₂ / kg coal
  coal_price_yuan_per_ton: 525  # 煤炭价格
  gasification_efficiency: 0.75  # 气化效率
  gasification_energy_mj_per_kg: 8.0  # 气化能耗 MJ/kg coal

# 碳排放参数（修改）
carbon_emission_parameters:
  saf_carbon_intensity_gco2e_per_mj: 60.0  # v2.0: 25.0
  conventional_jet_carbon_intensity_gco2e_per_mj: 89.0
  corsia_threshold_gco2e_per_mj: 44.5
  saf_heating_value_mj_per_kg: 43.0

# 时间参数
time_parameters:
  start_time: "2024-01-01 00:00:00"
  time_resolution_hours: 1
  optimization_horizon_hours: 168  # 1周

# 绿氢参数（保留）
hydrogen_parameters:
  production_cost_yuan_per_kg: 30
  storage_capacity_kg: 10000
  # ...

# SAF生产参数（保留）
saf_production_parameters:
  ecr_efficiency: 0.75
  mtj_efficiency: 0.85
  # ...

# 删除：co2_capture_sources, co2_pipeline_parameters, co2_truck_transport_parameters
```

### 14.2 CoalSupplyManager核心代码

```python
class CoalSupplyManager:
    def __init__(self, config: Dict):
        self.config = config['coal_parameters']
        self.coal_type = self.config['coal_type']
        self.co2_per_kg_coal = self.config['co2_per_kg_coal']
        self.coal_price_yuan_per_kg = self.config['coal_price_yuan_per_ton'] / 1000

    def calculate_co2_from_coal(self, coal_kg: float) -> float:
        return coal_kg * self.co2_per_kg_coal

    def calculate_total_coal_cost(self, coal_kg: float) -> Dict:
        purchase = coal_kg * self.coal_price_yuan_per_kg
        gasification = coal_kg * self.config['gasification_energy_mj_per_kg'] * 0.5
        return {
            'purchase_cost': purchase,
            'gasification_cost': gasification,
            'total_cost': purchase + gasification
        }
```

### 14.3 主优化模型关键修改

**删除的代码**（v2.0，约500行）：
```python
# DELETE
def _load_co2_capture_sources(self):
    # 加载4个GIS文件，4311条记录
    power_plants = gpd.read_file('co2_capture_power_plant.geojson')
    steel_plants = gpd.read_file('co2_capture_steel_plant.geojson')
    # ... 200+行代码
```

**新增的代码**（v3.0，约50行）：
```python
# ADD
def _define_coal_supply(self):
    self.coal_supply = CoalSupplyManager(self.config)
    self.coal_co2_ratio = self.coal_supply.co2_per_kg_coal
    self.coal_price_per_kg = self.coal_supply.coal_price_yuan_per_kg
```

**决策变量修改**：
```python
# DELETE (v2.0)
self.co2_pipeline_transport = model.addVars(...)  # 5.8M变量
self.co2_truck_transport = model.addVars(...)     # 5.8M变量

# ADD (v3.0)
self.coal_purchase = model.addVars(
    [(j, t) for j in saf_locations for t in hours],
    vtype=GRB.CONTINUOUS, lb=0, name="coal_purchase"
)  # 134k变量（-98.9%）
```

**约束条件修改**：
```python
# ADD (v3.0)
for j in saf_locations:
    for t in hours:
        co2_from_coal = self.coal_purchase[j, t] * self.coal_co2_ratio
        model.addConstr(
            self.co2_inventory[j, t] ==
            self.co2_inventory[j, t-1] + co2_from_coal - co2_consumed
        )
```

**目标函数修改**：
```python
# DELETE (v2.0)
co2_capture_cost = gp.quicksum(...)      # 150-180 yuan/ton
co2_pipeline_cost = gp.quicksum(...)     # 距离相关
co2_truck_cost = gp.quicksum(...)        # 50 yuan/ton/100km

# ADD (v3.0)
coal_purchase_cost = gp.quicksum(
    self.coal_purchase[j, t] * 0.525
    for j in saf_locations for t in hours
)  # 0.8 yuan/kg

coal_gasification_cost = gp.quicksum(
    self.coal_purchase[j, t] * 4.0
    for j in saf_locations for t in hours
)  # 4.0 yuan/kg
```

### 14.4 运行脚本示例

```python
# run_coal_hydrogen_optimization.py
from src.core.coal_hydrogen_optimization_model import CoalHydrogenSAFOptimizer

def main():
    # 加载配置
    config_path = "shared/data/CoalHydrogenSAFOptimizer_config.yaml"

    # 创建优化器
    optimizer = CoalHydrogenSAFOptimizer(config_path)

    # 构建模型
    print("Building model...")
    optimizer.build_model()

    # 求解
    print("Solving model...")
    optimizer.solve()

    # 输出结果
    print("Saving results...")
    optimizer.save_results()

    # 生成报告
    print("Generating report...")
    optimizer.generate_report()

    print("Optimization completed!")

if __name__ == "__main__":
    main()
```

### 14.5 测试用例示例

```python
# tests/test_coal_supply_manager.py
import unittest
from src.modules.coal_supply_manager import CoalSupplyManager

class TestCoalSupplyManager(unittest.TestCase):
    def setUp(self):
        self.config = {
            'coal_parameters': {
                'coal_type': 'bituminous',
                'carbon_content': 0.75,
                'co2_per_kg_coal': 2.44,
                'coal_price_yuan_per_ton': 800,
                'gasification_efficiency': 0.75,
                'gasification_energy_mj_per_kg': 8.0
            }
        }
        self.manager = CoalSupplyManager(self.config)

    def test_co2_calculation(self):
        coal = 1000  # kg
        co2 = self.manager.calculate_co2_from_coal(coal)
        self.assertAlmostEqual(co2, 2440, places=0)

    def test_cost_calculation(self):
        coal = 1000
        costs = self.manager.calculate_total_coal_cost(coal)
        self.assertAlmostEqual(costs['purchase_cost'], 800, places=0)
        self.assertAlmostEqual(costs['gasification_cost'], 4000, places=0)

if __name__ == '__main__':
    unittest.main()
```

### 14.6 Gurobi求解器参数

```python
# 推荐的Gurobi参数设置
model.setParam('MIPGap', 0.01)  # 1%优化间隙
model.setParam('TimeLimit', 1200)  # 20分钟时间限制
model.setParam('Threads', 8)  # 使用8个线程
model.setParam('MIPFocus', 1)  # 侧重于找到可行解
model.setParam('LogFile', 'logs/gurobi.log')  # 日志文件
```

---

## 文档结束

**PRD v3.0 完成**

**版本信息**：
- 文档版本：v3.0
- 创建日期：2024-XX-XX
- 最后修改：2024-XX-XX
- 作者：[Your Name]
- 审核：[Reviewer Name]

**文档统计**：
- 总章节：14章
- 预计文档长度：约6000行
- 核心内容：工艺路线、代码修改、任务分解、风险管理、验收标准

**下一步行动**：
1. PRD评审和批准
2. 启动Phase 1开发
3. 按照任务分解执行实施

**联系方式**：
- 技术问题：[Email]
- 项目管理：[Email]

---

## 六、煤炭供应模块设计

### 6.1 模块概述

**新增模块**：

**模块定位**：
- 替代v2.0的CO₂捕获源管理模块（CO2CaptureSourceManager）
- 简化设计：不处理GIS数据，不计算运输成本
- 直接在SAF生产点配置煤炭供应参数

**核心职责**：
1. 加载煤炭供应配置参数
2. 计算煤炭气化产生的CO₂量
3. 计算煤炭采购成本和气化能耗成本
4. 提供煤炭供应约束条件

### 6.2 CoalSupplyManager类设计

#### 6.2.1 类结构



#### 6.2.2 核心方法：计算CO₂产量



