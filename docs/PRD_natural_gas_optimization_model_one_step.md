# PRD: 天然气供应链优化模型 - FT一步法工艺改造

## 文档信息
- **项目名称**: 天然气供应链优化模型 - FT一步法SAF生产工艺改造
- **文档版本**: v1.0
- **创建日期**: 2025-10-11
- **负责人**: Claude Code
- **文档类型**: Product Requirements Document (PRD)

---

## 1. 项目背景

### 1.1 现有工艺流程
当前的 `natural_gas_optimization_model.py` 采用**两步法**生产SAF（可持续航空燃料）:
- **第一步**: 天然气 → 甲醇（需要绿氢参与）
- **第二步**: 甲醇 → SAF（MTJ航煤）
- **技术路线**: E-CRM (电化学CO₂还原制甲醇) + TRM (甲醇转航煤)

这一工艺需要：
1. **可再生能源**（风电/光伏）→ **电解槽** → **绿氢**
2. **氢气运输**（管道/罐车）
3. **天然气 + 绿氢** → **甲醇**
4. **甲醇** → **SAF**

### 1.2 新工艺需求
改造为**FT一步法**（费托合成）直接生产SAF:
- **工艺路线**: 天然气 → SAF（一步合成）
- **核心技术**: Fischer-Tropsch (FT) 费托合成工艺
- **优势**:
  - 工艺流程简化
  - 不需要绿氢参与
  - 不需要可再生能源发电厂
  - 不需要电解槽设施
  - 不需要氢气运输系统

### 1.3 项目目标
创建新的优化模型 `natural_gas_optimization_model_one_step.py`，实现：
1. 基于费托合成的一步法SAF生产工艺建模
2. 删除氢能相关的所有数据、设施和决策变量
3. 更新工艺参数以反映FT合成的实际技术指标
4. 重构目标函数和约束条件以适应新工艺
5. 创建对应的配置文件 `NaturalGasSupplyChainOptimizer_one_step_config.yaml`

---

## 2. 需求详细说明

### 2.1 文件创建与重命名

#### 2.1.1 核心文件复制
**源文件**:
```
products/supply_chain_optimization/natural_gas_supply_chain_optimization/src/core/natural_gas_optimization_model.py
```

**目标文件**:
```
products/supply_chain_optimization/natural_gas_supply_chain_optimization/src/core/natural_gas_optimization_model_one_step.py
```

**操作**:
- 完整复制源文件到新文件
- 更新文件头部的文档字符串，说明这是FT一步法工艺
- 更新类名（如需要）

#### 2.1.2 配置文件复制
**源配置**:
```
shared/data/NaturalGasSupplyChainOptimizer_config.yaml
```

**目标配置**:
```
shared/data/NaturalGasSupplyChainOptimizer_one_step_config.yaml
```

**操作**:
- 完整复制配置文件
- 更新文件头部说明，标注为FT一步法工艺配置
- 在metadata部分更新版本号和说明

---

### 2.2 数据获取层面的修改

#### 2.2.1 删除氢能相关数据导入

**需要删除的数据源**:

1. **可再生能源数据** (用于制氢的电力来源)
   - 风电数据: `wind_data_dir`
   - 光伏数据: `solar_data_dir`
   - 可再生能源发电厂位置和产能数据

2. **氢气相关基础设施数据**
   - 电解槽设施数据
   - 氢气管道数据
   - 氢气储存设施数据

**具体删除位置**:
- `_load_renewable_energy_data()` 方法 - **删除或注释**
- `_load_electrolyzer_data()` 方法 - **删除或注释**
- `_load_hydrogen_pipeline_data()` 方法 - **删除或注释**
- 配置文件中的相关路径配置

**保留的数据源**:
- ✅ 天然气管道数据 (`ng_pipelines_integrated`, `ng_pipelines_preprocessed`)
- ✅ LNG接收站数据 (`lng_terminals_preprocessed`)
- ✅ 机场数据 (`airports_excel`)
- ✅ SAF需求数据

#### 2.2.2 删除氢气运输成本数据

**配置文件中需要删除的部分**:

```yaml
# 删除以下成本参数
costs:
  hydrogen_pipeline_costs:  # 整个section删除
    capex_yuan_per_km: 5000000
    transport_cost_function: ...
```

```yaml
# 删除氢气罐车运输成本
cost_parameters:
  electrolysis:  # 整个section删除
    formula_based_transport:
      vehicle_payload_kg: 25000
      ...
```

---

### 2.3 配置参数更新 - FT合成工艺参数

#### 2.3.1 FT合成工艺参数研究

**需要从网络搜索获取的参数**:

1. **FT反应器建设成本** (FT Reactor CAPEX)
   - 单位产能建设成本 (元/kg产能)
   - 不同规模的成本系数
   - 替代原来的电解槽和甲醇合成装置成本

2. **FT工艺转化效率**
   - 天然气 → SAF 的质量转化率
   - 能量转化效率
   - 碳转化率

3. **FT工艺原料消耗**
   - 生产1kg SAF需要的天然气量 (m³)
   - 生产1kg SAF需要的催化剂量
   - 其他辅助原料消耗

4. **FT工艺运营成本** (OPEX)
   - 催化剂更换成本
   - 设备维护成本
   - 人工成本
   - 公用工程成本（水、电、蒸汽）

5. **FT反应条件和能耗**
   - 反应温度和压力
   - 单位产品能耗 (kWh/kg SAF)
   - 冷却、加热能耗

6. **FT产品质量参数**
   - SAF产品规格
   - 副产品种类和比例
   - 产品分离成本

#### 2.3.2 配置文件参数更新清单

**technologies section 更新**:
```yaml
technologies:
  # 新增FT一步法工艺配置
  ft_direct_conversion:
    name: "FT费托合成一步法SAF生产 (LTFT-Co催化)"
    technology_type: "FT_Direct"
    description: "低温费托合成工艺，使用钴基催化剂，天然气直接制SAF"

    # 转化效率 (基于网络搜索数据 - 见参数研究报告)
    efficiency: 0.55  # FT工艺的总体能量转化效率 (天然气→SAF)
                      # 基于GTL实际运行数据：50-60%热效率

    # 原料消耗比 (基于网络搜索数据)
    ng_consumption_ratio: 2.0  # 生产1kg SAF需要的天然气量(m³/kg)
                               # 基于5686 m³合成气/吨油品换算
                               # 考虑重整效率90%，FT效率85%，SAF选择性65%

    # FT工艺不需要外部氢气（内部通过水气变换反应调节H2/CO比）
    h2_consumption_ratio: 0
    hydrogen_transport_required: false

    # FT一步法不需要甲醇中间体
    methanol_intermediate_ratio: 0

    # FT反应器运行参数 (基于LTFT工艺标准)
    ft_reactor_temperature_celsius: 230  # LTFT反应温度 (200-240°C)
                                         # 230°C为钴基催化剂最佳温度
    ft_reactor_pressure_mpa: 2.5  # 反应压力 (2.0-4.0 MPa)
                                  # 2.5 MPa为工业常用压力
    ft_h2_co_ratio: 2.0  # 合成气H2/CO最优比 (钴催化剂1.8-2.1)

    ft_energy_consumption_kwh_per_kg: 2.5  # 单位产品能耗 (电力)
                                           # 基于GTL能耗估算：2.2-3.3 kWh/kg

    # 催化剂参数
    catalyst_type: "Cobalt"  # 钴基催化剂（适合天然气原料）
    catalyst_cost_yuan_per_kg_saf: 0.06  # 摊销到产品的催化剂成本
    catalyst_lifetime_years: 4  # 催化剂使用寿命

    # 产品选择性
    c5_plus_selectivity: 0.92  # C5+长链烃选择性 (85-92.8%)
    saf_fraction_in_products: 0.65  # SAF在总产物中占比

    # 适用位置
    suitable_locations:
      - ng_pipeline  # 靠近天然气管道（优先）
      - lng_terminal  # LNG接收站
      - airport  # 机场附近（短途运输）

    # 运输模式
    transport_mode: "ng_direct_supply"

  # 删除或注释掉原有的E-CRM+TRM工艺配置
  # airport_integrated_conversion: ...
  # pipeline_direct_conversion: ...
  # lng_terminal_conversion: ...
  # lng_to_hplant_conversion: ...
```

**facility_lcoe_parameters section 更新**:
```yaml
facility_lcoe_parameters:
  # FT反应器建设成本 (基于网络搜索数据 - GTL小规模设施)
  fixed_capex: 50000000  # FT反应器固定资本支出(元)
                         # 约5000万元包含土地、基础设施、公用工程等
                         # 基于小规模GTL设施数据

  fixed_opex_annual: 10000000  # FT反应器年固定运营成本(元/年)
                               # 约1000万元/年，包括维护、人工、管理等
                               # 约为CAPEX的5% (行业标准4-6%)

  variable_capex_per_capacity: 2500  # 单位产能资本支出(元/kg产能)
                                     # 基于$50,000/bbl优化成本换算
                                     # $370/kg × 7.2汇率 ≈ 2,664元/kg
                                     # 保守取2,500元/kg

  variable_opex_per_kg: 0.30  # 单位产品运营成本(元/kg)
                              # 不含原料，仅电力、辅料、维护等
                              # 电力: 0.5元/kWh × 2.5 kWh = 1.25元 (主要)
                              # 其他辅料+维护: ~0.05元
                              # 保守取0.30元/kg

  # FT催化剂成本 (基于钴价和催化剂用量)
  catalyst_price_yuan_per_kg: 270  # 钴基催化剂单价(元/kg催化剂)
                                   # 基于钴价$33-40/kg × 7.2汇率
  catalyst_cost_per_kg_saf: 0.06  # 摊销到产品的催化剂成本(元/kg SAF)
                                  # 计算: 0.75kg催化剂/吨年产能 ÷ (4年×0.85利用率)
  catalyst_lifetime_years: 4  # 催化剂使用寿命(年)
  catalyst_replacement_interval_days: 1460  # 催化剂更换周期(天) = 4×365
```

**capacity_limits section 更新**:
```yaml
capacity_limits:
  # 删除电解槽相关容量限制
  # electrolyzer_max_capacity_kg_per_hour: ...  # 删除

  # 删除氢气运输容量限制
  # hydrogen_pipeline_max_daily_capacity_kg: ...  # 删除
  # hydrogen_truck_max_daily_capacity_kg: ...  # 删除

  # 更新SAF生产容量限制
  saf_max_capacity_kg_per_hour: 10000  # SAF生产设施最大产能
                                       # 中型商业化设施上限

  # FT反应器容量上限（容量本身是决策变量，此处仅定义上限）
  ft_reactor_max_capacity_kg_per_hour: 10000  # FT反应器最大产能上限(kg/h)
                                               # 注意：实际容量由优化模型决策确定
                                               # 这里只是设定技术可行的最大值
                                               # 基于中型GTL设施技术可行性

  ft_reactor_min_economic_capacity: 500  # FT反应器最小经济规模(kg/h)
                                         # 低于此规模经济性较差
                                         # 可作为可选约束
```

**carbon_emission_parameters section 更新**:
```yaml
carbon_emission_parameters:
  # 删除电解槽和氢气相关的碳排放参数
  facility_construction:
    # electrolyzer_embodied: ...  # 删除
    # electrolyzer_lifetime: ...  # 删除

    # 新增FT反应器碳排放 (类比化工设备)
    ft_reactor_embodied: 800  # FT反应器隐含碳排放(kgCO₂e/kW)
                              # 包括设备制造、运输、安装的总排放
                              # 参考大型化工装置隐含碳数据
    ft_reactor_lifetime: 25  # FT反应器设计寿命(年)

    saf_facility_embodied: 600  # 更新SAF设施隐含碳排放(kgCO₂e/年产吨)
    saf_facility_lifetime: 25  # 设施设计寿命(年)

  production_process:
    # renewable_electricity: ...  # 删除
    # electrolysis_energy: ...  # 删除
    # green_h2_intensity: ...  # 删除
    # h2_addition_rate: ...  # 删除

    # 新增FT工艺排放 (基于CORSIA数据)
    ft_process_emission: 0.65  # FT工艺过程排放(kgCO₂e/kg SAF)
                               # 仅计算生产环节的直接排放
                               # 基于20 gCO₂e/MJ × 43.15 MJ/kg ÷ 1000
    ft_process_energy: 2.5  # FT工艺能耗(kWh/kg SAF)
                            # 电力消耗：2.2-3.3 kWh/kg，取中值

    # 更新天然气处理参数
    ng_to_saf_rate: 2.0  # 天然气制SAF转化率(m³/kg SAF)
                         # 与technologies中ng_consumption_ratio一致

  transportation:
    # h2_pipeline_intensity: ...  # 删除
    # h2_truck_intensity: ...  # 删除

    # 保留并更新SAF运输排放
    saf_truck_intensity: 0.12  # SAF罐车碳强度(kgCO₂e/kg/100km)

  # 新增：FT-SAF生命周期总碳强度
  lifecycle_totals:
    traditional_jet_fuel: 89  # 传统航煤(gCO₂e/MJ) - CORSIA基准
    ft_saf_from_ng: 35  # FT-SAF天然气路线(gCO₂e/MJ)
    carbon_reduction: 0.61  # 碳减排比例
    corsia_compliant: true  # 符合CORSIA标准
```

**cost_parameters section 更新**:
```yaml
cost_parameters:
  # 删除电解制氢参数section
  # electrolysis: ...  # 整个section删除

  raw_materials:
    # 保留天然气价格
    natural_gas_price_yuan_per_m3: 4.2  # 天然气价格(元/m³)

    # 删除氢气相关价格
    # hydrogen_market_price_yuan_per_kg: ...  # 删除

    # 删除可再生电力成本
    # renewable_electricity_cost_yuan_per_mwh: ...  # 删除

    # 新增FT催化剂成本
    ft_catalyst_price_yuan_per_kg: 270  # 钴基催化剂价格(元/kg催化剂)

    # 新增电力成本
    grid_electricity_cost_yuan_per_kwh: 0.5  # 电网电价(元/kWh)

  # 保留缺货惩罚
  shortage_penalty_yuan_per_kg: 2500  # 缺货惩罚成本(元/kg)
```

**equipment_raw_costs section 更新**:
```yaml
equipment_raw_costs:
  # 删除电解槽成本
  # electrolyzer: ...  # 删除

  # 新增FT反应器成本
  ft_reactor:
    capex_raw: 2500  # FT反应器资本支出(元/kg产能)
    fixed_capex: 50000000  # 固定资本支出(元/设施)
    opex_raw: 10000000  # FT反应器年运营成本(元/年)

  # 保留储存设施成本（用于SAF储存）
  storage:
    capex_raw: 1500
    opex_raw: 20
```

---

### 2.4 模型层面的修改

#### 2.4.0 FT反应器容量作为决策变量的设计说明

**设计理念**:

FT反应器容量（`ft_capacity[location]`）是本模型的**核心决策变量**之一，而非预设的固定参数。这一设计反映了以下重要考虑：

**1. 容量优化的必要性**
- 不同位置的需求不同，容量应根据实际需求动态确定
- 容量大小直接影响建设成本（CAPEX）和运营效率
- 过大的容量导致资本浪费，过小的容量无法满足需求
- 优化器可以在成本和需求之间找到最佳平衡点

**2. 容量决策变量的特性**
```python
# 变量类型：连续变量（Continuous Variable）
ft_capacity[loc] = model.addVar(
    lb=0.0,  # 下界：可以不建设（容量为0）
    ub=ft_reactor_max_capacity_kg_per_hour,  # 上界：技术可行的最大容量
    vtype=GRB.CONTINUOUS,
    name=f"ft_capacity_{loc}"
)

# 关键特性：
# - 容量值由Gurobi求解器根据目标函数和约束自动优化确定
# - 不是预先设定的估算值
# - 最终容量反映了该位置的最优建设规模
```

**3. 容量与建设决策的关系**（Big-M约束）
```python
# FT设施建设二进制变量
ft_facility_binary[loc] ∈ {0, 1}

# 逻辑约束：
# 如果 ft_facility_binary[loc] = 0（不建设），则 ft_capacity[loc] = 0
# 如果 ft_facility_binary[loc] = 1（建设），则 ft_capacity[loc] ∈ [0, max_capacity]

model.addConstr(
    ft_capacity[loc] <= ft_reactor_max_capacity_kg_per_hour * ft_facility_binary[loc]
)
```

**4. 容量对成本的影响**

**固定成本部分**（与建设决策相关）:
```python
fixed_cost = ft_facility_binary[loc] * fixed_capex
# 只要建设，就产生固定成本（土地、基础设施等）
```

**可变成本部分**（与容量大小相关）:
```python
variable_cost = ft_capacity[loc] * variable_capex_per_kg
# 容量越大，设备投资越高（反应器尺寸、管道直径等）
```

**总成本**:
```
Total CAPEX = Fixed CAPEX + Variable CAPEX(capacity)
优化器会权衡：
- 建设更多小容量设施 vs 建设少数大容量设施
- 建设成本 vs 运输成本
- 容量利用率 vs 柔性需求响应
```

**5. 容量决策示例**

假设有3个候选位置建设FT反应器：

| 位置 | 与需求点距离 | 天然气供应成本 | 优化结果 |
|------|------------|--------------|---------|
| 位置A | 近（50km） | 高（4.5元/m³）| `ft_capacity[A] = 3500 kg/h`<br>`ft_facility_binary[A] = 1` |
| 位置B | 中（150km）| 中（4.2元/m³）| `ft_capacity[B] = 8000 kg/h`<br>`ft_facility_binary[B] = 1` |
| 位置C | 远（300km）| 低（3.8元/m³）| `ft_capacity[C] = 0 kg/h`<br>`ft_facility_binary[C] = 0` |

**优化逻辑分析**:
- 位置A：靠近需求，建小容量设施服务本地需求
- 位置B：天然气成本适中，建大容量设施，利用规模经济
- 位置C：虽然天然气便宜，但运输成本过高，不建设

**6. 与原模型的对比**

| 特性 | 原模型（容量估算） | 新模型（容量决策） |
|------|------------------|------------------|
| 容量确定方式 | 人工预设估算值 | 优化器自动决策 |
| 灵活性 | 低（需手动调参） | 高（自动适应需求） |
| 优化空间 | 仅优化是否建设 | 同时优化是否建设+建多大 |
| 成本建模 | 固定成本模型 | 固定+可变成本模型 |
| 决策质量 | 依赖人工经验 | 基于数学优化 |

**7. 配置文件中的参数含义**

```yaml
capacity_limits:
  # 这个参数定义的是技术可行性上限，不是预设值
  ft_reactor_max_capacity_kg_per_hour: 100000
  # 含义：单个FT反应器的技术上限（基于现有工程技术）
  # 实际建设容量由优化器决定，可以是0到100000之间的任何值

  # ❌ 错误理解：这个值会被直接用于建设
  # ✅ 正确理解：这是决策变量的上界约束
```

---

#### 2.4.1 候选位置集合的重新定义

**原模型的位置集合**（包含氢气生产点）:
```python
# 原模型需要定义多个位置集合：
locations = {
    'renewable_plants': [...],  # 可再生能源发电厂（用于制氢）
    'electrolyzer_sites': [...],  # 电解槽建设候选点（通常与发电厂重合）
    'ng_sources': [...],  # 天然气供应源
    'mtj_facilities': [...],  # MTJ生产设施候选点
    'airports': [...]  # 机场（需求点）
}

# 变量定义基于这些集合：
for loc in renewable_plants:
    renewable_plant_binary[loc] = ...
for loc in electrolyzer_sites:
    electrolyzer_binary[loc] = ...
    electrolyzer_capacity[loc] = ...
```

**新模型的位置集合**（FT一步法，无需氢气生产点）:
```python
# 简化的位置集合定义：
locations = {
    'ng_sources': [...],  # 天然气供应源（管道端点、LNG接收站）
    'ft_facility_candidates': [...],  # FT反应器建设候选点
    'airports': [...]  # 机场（需求点）
}

# FT设施候选位置的选择逻辑：
ft_facility_candidates = {
    # 1. 天然气管道沿线位置（优先）
    'pipeline_locations': [loc for loc in ng_pipeline_endpoints],

    # 2. LNG接收站位置
    'lng_terminals': [loc for loc in lng_terminal_list],

    # 3. 机场附近位置（短途SAF运输）
    'near_airports': [loc for loc in get_locations_near_airports(max_distance=100km)]
}

# 关键变化：
# ❌ 删除：renewable_plants（不再需要风电/光伏位置）
# ❌ 删除：electrolyzer_sites（不再需要电解槽位置）
# ✅ 新增：ft_facility_candidates（FT反应器候选位置，基于天然气可达性）
```

**位置筛选逻辑**:
```python
def define_ft_facility_candidates():
    """
    定义FT设施候选位置集合

    原则：
    1. 天然气供应便利性（靠近管道或LNG接收站）
    2. SAF运输距离合理（不超过500km到主要机场）
    3. 基础设施条件（工业用地、公用工程）
    """
    candidates = []

    # 筛选1：天然气管道端点
    for pipeline_node in ng_pipeline_nodes:
        if has_sufficient_ng_supply(pipeline_node):
            candidates.append(pipeline_node)

    # 筛选2：LNG接收站
    for lng_terminal in lng_terminals:
        if lng_terminal.capacity > min_capacity_threshold:
            candidates.append(lng_terminal)

    # 筛选3：机场附近且有天然气管道覆盖的位置
    for airport in airports:
        nearby_ng_nodes = get_ng_nodes_within_distance(airport, max_distance=100km)
        candidates.extend(nearby_ng_nodes)

    # 去重
    candidates = list(set(candidates))

    return candidates
```

**位置集合对比表**:

| 位置集合类型 | 原模型（E-CRM+TRM） | 新模型（FT一步法） | 变化说明 |
|------------|-------------------|------------------|---------|
| **天然气供应源** | ng_pipelines, lng_terminals | 相同 | ✅ 保留 |
| **可再生能源发电厂** | renewable_plants (风电/光伏) | - | ❌ 删除（不需要） |
| **制氢设施** | electrolyzer_sites | - | ❌ 删除（不需要） |
| **生产设施** | mtj_facilities (甲醇→SAF) | ft_facility_candidates (天然气→SAF) | 🔄 替换 |
| **需求点** | airports | airports | ✅ 保留 |
| **候选点数量** | ~200-500 (包含大量发电厂) | ~50-100 (仅天然气相关) | 📉 显著减少 |

**新模型的简化优势**:
1. **候选位置减少70-80%**: 不再需要考虑大量分散的风电/光伏电站
2. **决策变量减少**: 无需为每个可再生能源站点创建建设决策变量
3. **约束简化**: 不需要氢气生产、运输、储存的复杂约束网络
4. **求解速度提升**: 问题规模显著缩小

---

#### 2.4.2 删除决策变量

**需要删除的变量类型**:

1. **氢气生产变量**
   - `hydrogen_production[location, hour]` - 电解槽氢气产量
   - `electrolyzer_binary[location]` - **电解槽建设决策**（不再需要）
   - `electrolyzer_capacity[location]` - **电解槽容量**（不再需要）

2. **氢气运输变量**（管道和罐车两种模式）
   - `hydrogen_pipeline_flow[source, dest, week]` - 管道氢气流量（连续变量）
   - `hydrogen_truck_flow[source, dest, week]` - 罐车氢气流量（连续变量）
   - `hydrogen_pipeline_binary[source, dest]` - **管道建设决策**（0/1二进制，不再需要）
   - `hydrogen_pipeline_capacity[source, dest]` - **管道容量决策**（连续变量，不再需要）
   - `hydrogen_trucks_used[source, dest, week]` - 使用的罐车数量（整数变量）
   - `hydrogen_transport_mode[source, dest, mode]` - 运输模式选择（二进制变量）

   **说明**:
   - 源点 `source ∈ electrolyzer_sites` 已删除（不再有氢气生产点）
   - 目的地 `dest ∈ mtj_facilities` 改为 `ft_facility_candidates`
   - 氢气运输网络的所有决策变量（建设、容量、流量、车辆调度）全部删除
   - 涉及的决策变量维度: 约 100×100×52 (源×目的地×周) = 520,000 个变量被删除

3. **氢气库存变量**
   - `hydrogen_inventory[location, hour]` - 氢气库存水平
   - `hydrogen_storage_capacity[location]` - **氢气储存容量**（不再需要）

4. **可再生能源变量**
   - `renewable_energy_usage[plant, hour]` - 可再生能源使用量
   - `renewable_plant_binary[plant]` - **发电厂选择决策**（不再需要）

**保留的变量**:
- ✅ `ng_supply[source, dest, week]` - 天然气供应量
- ✅ `ng_transport_mode[source, dest]` - 天然气运输模式（管道/罐车）
- ✅ `saf_production[location, week]` - SAF产量
- ✅ `saf_transport[source, dest, week]` - SAF运输量
- ✅ `saf_inventory[location, week]` - SAF库存

**新增的决策变量**（FT反应器相关）:
- ✅ `ft_facility_binary[location]` - **FT设施建设决策**（0/1二进制变量）
  - **定义域**: location ∈ ft_facility_candidates (FT候选位置集合)
  - **含义**: 是否在该位置建设FT反应器设施
  - **重要**: 这替代了原来的electrolyzer_binary（电解槽建设）和mtj_facility_binary（甲醇转化设施）

- ✅ `ft_capacity[location]` - **FT反应器容量决策**（连续变量，单位：kg/h）
  - **定义域**: location ∈ ft_facility_candidates
  - **约束**: 0 ≤ ft_capacity[location] ≤ ft_reactor_max_capacity_kg_per_hour
  - **逻辑约束**: ft_capacity[location] > 0 当且仅当 ft_facility_binary[location] = 1
  - **重要**：这是优化模型的核心决策变量，由求解器根据成本、需求等因素最优确定

**决策变量维度对比**:

| 变量类型 | 原模型 | 新模型 | 变化 |
|---------|-------|-------|------|
| **建设决策变量数量** | ~500 (电解槽) + ~100 (MTJ) = 600 | ~80 (FT) | **减少87%** |
| **容量决策变量数量** | ~500 (电解槽) + ~100 (MTJ) = 600 | ~80 (FT) | **减少87%** |
| **运输决策变量** | 氢气运输 + 天然气 + SAF | 天然气 + SAF | **减少33%** |
| **库存变量** | 氢气 + SAF | SAF | **减少50%** |
| **总决策变量估算** | ~5000-8000 | ~2000-3000 | **减少60-70%** |

**代码实现示例**:

```python
# 原模型（需要删除）
class NaturalGasSupplyChainOptimizer:
    def _create_decision_variables(self):
        # ❌ 删除这些方法调用
        # self._create_renewable_energy_variables()
        # self._create_electrolyzer_variables()
        # self._create_hydrogen_transport_variables()
        # self._create_hydrogen_inventory_variables()

        # ✅ 保留和新增
        self._create_ng_supply_variables()
        self._create_ft_facility_variables()  # 新增
        self._create_saf_production_variables()
        self._create_saf_transport_variables()
        self._create_saf_inventory_variables()

    def _create_ft_facility_variables(self):
        """创建FT设施相关决策变量（新增方法）"""
        # FT设施建设二进制决策
        self.ft_facility_binary = {}
        for loc in self.ft_facility_candidates:
            self.ft_facility_binary[loc] = self.model.addVar(
                vtype=GRB.BINARY,
                name=f"ft_facility_binary_{loc}"
            )

        # FT设施容量决策（连续变量）
        self.ft_capacity = {}
        for loc in self.ft_facility_candidates:
            self.ft_capacity[loc] = self.model.addVar(
                lb=0.0,
                ub=self.config['ft_reactor_max_capacity_kg_per_hour'],
                vtype=GRB.CONTINUOUS,
                name=f"ft_capacity_{loc}"
            )
```

---

#### 2.4.3 目标函数修改

**原目标函数组成**（需要修改的部分）:
```python
# 原目标函数包含：
objective = (
    天然气采购成本 +  # 保留
    天然气运输成本 +  # 保留

    # === 以下部分需要删除 ===
    可再生能源成本 +  # 删除
    电解槽建设成本 +  # 删除
    电解槽运营成本 +  # 删除
    氢气生产成本 +  # 删除
    氢气运输成本 +  # 删除（管道+罐车）
    氢气库存成本 +  # 删除
    # === 删除部分结束 ===

    # === 以下部分需要修改或保留 ===
    SAF生产设施成本 +  # 修改为FT反应器成本
    SAF生产成本 +  # 修改为FT工艺成本
    SAF运输成本 +  # 保留
    SAF库存成本 +  # 保留
    缺货惩罚成本  # 保留
)
```

**新目标函数组成**:
```python
objective = (
    # 1. 天然气相关成本
    ng_procurement_cost +  # 天然气采购成本
    ng_transport_cost +  # 天然气运输成本

    # 2. FT反应器设施成本
    ft_reactor_capex +  # FT反应器资本支出（摊销）
    ft_reactor_opex +  # FT反应器运营支出

    # 3. FT工艺生产成本
    ft_process_cost +  # FT工艺成本（催化剂、能耗等）
    ft_catalyst_cost +  # 催化剂成本

    # 4. SAF相关成本
    saf_transport_cost +  # SAF运输成本
    saf_storage_cost +  # SAF库存成本

    # 5. 惩罚项
    shortage_penalty_cost  # 缺货惩罚
)
```

**具体实现修改点**:

1. **删除可再生能源成本计算**（包括发电厂选择成本）
```python
# 删除或注释以下代码
# renewable_energy_cost = gp.quicksum(
#     renewable_energy_usage[p, h] * renewable_electricity_cost
#     for p in renewable_plants for h in hours
# )

# 删除可再生能源发电厂选择/建设成本
# renewable_plant_selection_cost = gp.quicksum(
#     renewable_plant_binary[p] * plant_selection_cost
#     for p in renewable_plants
# )
# 说明：renewable_plants位置集合已删除，不再作为候选建设位置
```

2. **删除电解槽成本计算**（在电解槽候选位置建设）
```python
# 删除或注释电解槽设施建设成本
# electrolyzer_capex = gp.quicksum(
#     electrolyzer_binary[loc] * electrolyzer_unit_capex
#     for loc in electrolyzer_sites
# )
# electrolyzer_opex = gp.quicksum(
#     electrolyzer_capacity[loc] * electrolyzer_unit_opex
#     for loc in electrolyzer_sites
# )
# 说明：electrolyzer_sites位置集合已删除，不再建设电解槽设施
```

3. **删除氢气运输成本计算**（管道和罐车两种运输方式）
```python
# 删除氢气管道运输成本
# hydrogen_pipeline_cost = gp.quicksum(
#     hydrogen_pipeline_flow[source, dest, h] * pipeline_unit_cost * distance[source, dest]
#     for source in electrolyzer_sites  # 氢气生产点已删除
#     for dest in mtj_facilities  # 目的地改为FT设施
#     for h in hours
# )

# 删除氢气管道建设成本（CAPEX）
# hydrogen_pipeline_capex = gp.quicksum(
#     hydrogen_pipeline_binary[source, dest] * pipeline_construction_cost
#     for source in electrolyzer_sites  # 电解槽站点已删除
#     for dest in mtj_facilities
# )

# 删除氢气罐车运输成本
# hydrogen_truck_cost = gp.quicksum(
#     hydrogen_truck_flow[source, dest, h] * truck_unit_cost * distance[source, dest]
#     for source in electrolyzer_sites  # 氢气生产点已删除
#     for dest in mtj_facilities
#     for h in hours
# )

# 删除氢气罐车调度成本（固定成本+可变成本）
# hydrogen_truck_dispatch_cost = gp.quicksum(
#     hydrogen_trucks_used[source, dest, h] * truck_dispatch_fixed_cost +
#     hydrogen_truck_flow[source, dest, h] * truck_variable_cost
#     for source in electrolyzer_sites
#     for dest in mtj_facilities
#     for h in hours
# )

# 说明：
# - electrolyzer_sites 位置集合已删除，不再有氢气生产点
# - 原模型中氢气从电解槽站运输到MTJ设施
# - 新模型中天然气直接运输到FT设施，无需氢气运输
# - 氢气管道和罐车相关的所有变量、约束、成本计算都需删除
```

4. **删除氢气库存成本计算**
```python
# 删除或注释
# hydrogen_inventory_cost = ...
```

5. **新增FT反应器成本计算（基于容量决策变量）**
```python
# 新增FT反应器资本支出（CAPEX与决策容量相关）
# 注意：迭代的是 ft_facility_candidates 位置集合，而非原来的多个位置集合
# 这些候选位置基于天然气供应便利性筛选，不包含氢气生产点

# 方法1：线性成本模型
ft_reactor_capex = gp.quicksum(
    ft_capacity[loc] * capex_per_unit_capacity / ft_reactor_lifetime
    for loc in ft_facility_candidates  # 新的简化位置集合
)

# 方法2：包含固定成本和可变成本（更真实）
ft_reactor_capex_fixed = gp.quicksum(
    ft_facility_binary[loc] * fixed_capex_per_facility / ft_reactor_lifetime
    for loc in ft_facility_candidates  # 不再包含 renewable_plants 或 electrolyzer_sites
)
ft_reactor_capex_variable = gp.quicksum(
    ft_capacity[loc] * variable_capex_per_kg_capacity / ft_reactor_lifetime
    for loc in ft_facility_candidates
)
ft_reactor_capex_total = ft_reactor_capex_fixed + ft_reactor_capex_variable

# 新增FT反应器运营支出（OPEX也与容量相关）
# 固定OPEX（设施建设时产生）
ft_reactor_opex_fixed = gp.quicksum(
    ft_facility_binary[loc] * fixed_opex_annual
    for loc in ft_facility_candidates  # 基于天然气可达性的候选位置
)

# 可变OPEX（与实际产量相关，在生产成本中计算）
# 见下面的ft_process_cost
```

6. **新增FT工艺成本计算**
```python
# FT工艺变动成本
# 注意：这里迭代 ft_facility_candidates，不包含可再生能源站或电解槽位置
ft_process_cost = gp.quicksum(
    saf_production[loc, w] * ft_process_cost_per_kg
    for loc in ft_facility_candidates for w in weeks
)

# FT催化剂成本
ft_catalyst_cost = gp.quicksum(
    saf_production[loc, w] * catalyst_cost_per_kg_saf
    for loc in ft_facility_candidates for w in weeks
)
```

7. **更新SAF生产成本计算**
```python
# 原来的甲醇合成成本改为FT直接合成成本
# 修改相关的转化率和效率参数
# 位置集合从多个位置类型简化为仅 ft_facility_candidates
saf_production_cost = gp.quicksum(
    saf_production[loc, w] * ng_consumption_per_kg_saf * ng_price
    for loc in ft_facility_candidates for w in weeks
)
```

#### 2.4.3 约束条件修改

**需要删除的约束类型**:

1. **电解槽相关约束**（在 electrolyzer_sites 位置集合）
   - 电解槽产能约束（不再需要，electrolyzer_sites已删除）
   - 电解槽能耗约束
   - 电解槽建设逻辑约束（electrolyzer_binary 决策变量已删除）

2. **氢气平衡约束**
   - 氢气产量 = 氢气消耗 + 氢气库存变化 + 氢气运输
   - 删除整个氢气物料平衡方程

3. **氢气运输约束**（管道和罐车）
   ```python
   # 删除氢气管道容量约束
   # for source in electrolyzer_sites:  # 电解槽站点已删除
   #     for dest in mtj_facilities:
   #         for h in hours:
   #             model.addConstr(
   #                 hydrogen_pipeline_flow[source, dest, h] <=
   #                 hydrogen_pipeline_capacity[source, dest] * hydrogen_pipeline_binary[source, dest],
   #                 name=f"h2_pipeline_capacity_{source}_{dest}_{h}"
   #             )

   # 删除氢气罐车容量约束
   # for source in electrolyzer_sites:
   #     for dest in mtj_facilities:
   #         for h in hours:
   #             model.addConstr(
   #                 hydrogen_truck_flow[source, dest, h] <=
   #                 truck_capacity * hydrogen_trucks_used[source, dest, h],
   #                 name=f"h2_truck_capacity_{source}_{dest}_{h}"
   #             )

   # 删除氢气运输距离约束
   # for source in electrolyzer_sites:
   #     for dest in mtj_facilities:
   #         if distance[source, dest] > max_hydrogen_transport_distance:
   #             model.addConstr(
   #                 hydrogen_pipeline_binary[source, dest] == 0,
   #                 name=f"h2_distance_limit_{source}_{dest}"
   #             )

   # 删除氢气管道建设逻辑约束（Big-M）
   # for source in electrolyzer_sites:
   #     for dest in mtj_facilities:
   #         model.addConstr(
   #             hydrogen_pipeline_capacity[source, dest] <=
   #             max_pipeline_capacity * hydrogen_pipeline_binary[source, dest],
   #             name=f"h2_pipeline_build_{source}_{dest}"
   #         )

   # 说明：
   # - 所有氢气运输相关约束都需删除
   # - 源点 electrolyzer_sites 已删除，不再有氢气生产点
   # - 目的地从 mtj_facilities 改为 ft_facility_candidates
   # - 新模型中只需考虑天然气运输和SAF运输，无氢气运输环节
   ```

4. **氢气库存约束**
   - 氢气库存上下限约束
   - 氢气安全库存约束

5. **可再生能源约束**（在 renewable_plants 位置集合）
   - 可再生能源供应上限约束（renewable_plants已删除，不再作为候选位置）
   - 风电/光伏出力约束（按小时）
   - 可再生能源站选择约束（renewable_plant_binary已删除）

**需要新增的约束**:

1. **FT反应器容量约束**
```python
# FT反应器产能约束（基于决策容量变量）
# 约束作用在 ft_facility_candidates 位置集合，不包含氢气生产点
for loc in ft_facility_candidates:
    for w in weeks:
        model.addConstr(
            saf_production[loc, w] <= ft_capacity[loc] * hours_per_week,
            name=f"ft_capacity_{loc}_{w}"
        )
        # 说明：ft_capacity[loc] 是决策变量，求解器会根据需求和成本自动确定最优值
```

2. **FT反应器建设逻辑约束（Big-M方法）**
```python
# FT设施建设与容量关联 - Big-M约束
# 应用于基于天然气可达性筛选的候选位置，不包含可再生能源站
for loc in ft_facility_candidates:
    # 如果不建设设施（binary=0），则容量必须为0
    # 如果建设设施（binary=1），则容量可以在[0, ft_max_capacity]范围内由优化器决定
    model.addConstr(
        ft_capacity[loc] <= ft_reactor_max_capacity_kg_per_hour * ft_facility_binary[loc],
        name=f"ft_build_logic_{loc}"
    )

    # 可选：如果建设了设施，确保至少有一定的最小容量（避免建设过小的设施）
    # min_capacity = 500  # kg/h 最小经济规模
    # model.addConstr(
    #     ft_capacity[loc] >= min_capacity * ft_facility_binary[loc],
    #     name=f"ft_min_capacity_{loc}"
    # )
```

3. **FT反应器容量成本约束**
```python
# 将容量决策与成本关联（用于目标函数）
# 这里展示如何在成本计算中使用决策容量变量

# 方法1：CAPEX与容量成正比（线性）
ft_reactor_capex_total = gp.quicksum(
    ft_capacity[loc] * capex_per_unit_capacity / reactor_lifetime
    for loc in ft_facility_candidates  # 基于天然气供应点筛选的位置
)

# 方法2：考虑规模经济效应（分段线性或非线性）
# 可以使用Gurobi的PWL（piecewise linear）约束
# 示例：小规模成本高，大规模单位成本低
# for loc in ft_facility_candidates:
#     model.addGenConstrPWL(
#         ft_capacity[loc],
#         capex_cost_var[loc],
#         capacity_breakpoints,  # [0, 1000, 5000, 10000]
#         cost_slopes  # [5000, 4000, 3500, 3000] 元/kg
#     )
```

3. **FT工艺原料约束**
```python
# 天然气消耗与SAF产量的关系
# 约束作用于 ft_facility_candidates，不包含可再生能源站
for loc in ft_facility_candidates:
    for w in weeks:
        model.addConstr(
            ng_supply_to_ft[loc, w] >= saf_production[loc, w] * ng_consumption_per_kg_saf,
            name=f"ft_ng_consumption_{loc}_{w}"
        )
```

4. **FT反应器能耗约束**（如果考虑能源限制）
```python
# FT工艺能耗约束（如果有能源供应限制）
# 应用于基于天然气可达性的FT候选位置
for loc in ft_facility_candidates:
    for w in weeks:
        model.addConstr(
            energy_consumption[loc, w] == saf_production[loc, w] * ft_energy_per_kg,
            name=f"ft_energy_{loc}_{w}"
        )
```

**需要修改的约束**:

1. **SAF产量约束**
```python
# 原约束可能包含氢气相关项，需要删除
# 原: saf_production = f(ng, h2, methanol)
# 新: saf_production = f(ng)

# 修改为仅基于天然气的产量计算
# 位置集合从多个类型简化为 ft_facility_candidates
for loc in ft_facility_candidates:
    for w in weeks:
        model.addConstr(
            saf_production[loc, w] == ng_consumption[loc, w] / ng_to_saf_ratio,
            name=f"saf_production_ft_{loc}_{w}"
        )
```

2. **需求满足约束**（保留但可能调整）
```python
# 保留需求满足约束，但确保引用的是正确的SAF产量变量
for airport in airports:
    for w in weeks:
        model.addConstr(
            saf_delivered[airport, w] >= saf_demand[airport, w],
            name=f"demand_satisfaction_{airport}_{w}"
        )
```

#### 2.4.4 方法级别的修改

**需要删除或大幅修改的方法**:

1. `_create_hydrogen_production_variables()` - **删除**（电解槽生产变量）
2. `_create_hydrogen_transport_variables()` - **删除**（氢气管道和罐车运输变量）
3. `_create_hydrogen_inventory_variables()` - **删除**（氢气库存变量）
4. `_create_renewable_energy_variables()` - **删除**（风电/光伏变量）
5. `_add_hydrogen_production_constraints()` - **删除**（电解槽产能约束）
6. `_add_hydrogen_transport_constraints()` - **删除**（氢气管道容量、罐车调度约束）
7. `_add_hydrogen_balance_constraints()` - **删除**（氢气物料平衡）
8. `_add_renewable_energy_constraints()` - **删除**（可再生能源出力约束）
9. `_calculate_hydrogen_costs()` - **删除**（氢气生产、运输、库存成本）
   - 包括: hydrogen_pipeline_cost, hydrogen_truck_cost, hydrogen_inventory_cost
10. `_calculate_renewable_energy_costs()` - **删除**（可再生能源发电成本）

**需要新增的方法**:

1. `_create_ft_reactor_variables()` - 创建FT反应器相关变量
2. `_add_ft_capacity_constraints()` - 添加FT容量约束
3. `_add_ft_process_constraints()` - 添加FT工艺约束
4. `_calculate_ft_reactor_costs()` - 计算FT反应器成本
5. `_calculate_ft_process_costs()` - 计算FT工艺成本

**需要修改的方法**:

1. `_create_production_variables()` - 修改SAF生产变量创建逻辑
2. `_add_production_constraints()` - 修改生产约束以反映FT工艺
3. `_calculate_total_cost()` - 重构成本计算逻辑
4. `_extract_solution()` - 修改解析逻辑，删除氢气相关结果
5. `_generate_report()` - 修改报告生成，删除氢气相关指标

#### 2.4.5 位置集合和决策变量修改总结

本节总结了FT一步法模型中所有与位置集合和工厂建设决策变量相关的关键变化。

**核心变化原则**:
- **删除氢气生产点**: 不再考虑可再生能源站（renewable_plants）和电解槽站点（electrolyzer_sites）作为候选建设位置
- **简化位置集合**: 从5类位置集合简化为3类（天然气源、FT候选位置、机场需求点）
- **统一建设决策**: 用单一的 ft_facility_binary 替代原来的 electrolyzer_binary 和 mtj_facility_binary
- **容量决策优化**: FT反应器容量（ft_capacity）作为连续决策变量，由优化器自动确定最优值

**位置集合对比表**:

| 位置集合 | 原模型（E-CRM+TRM） | 新模型（FT一步法） | 数量变化 |
|---------|-------------------|------------------|---------|
| 可再生能源站 | renewable_plants (200-400个) | **删除** | -100% |
| 电解槽站点 | electrolyzer_sites (100-150个) | **删除** | -100% |
| 天然气源 | ng_sources (50-80个) | ng_sources | 保持 |
| 生产设施候选点 | mtj_facilities (80-100个) | ft_facility_candidates (50-80个) | -30% |
| 需求点 | airports (10-20个) | airports | 保持 |
| **总计** | **440-750个** | **110-180个** | **-75%** |

**决策变量对比表**:

| 决策变量类型 | 原模型 | 新模型 | 说明 |
|------------|-------|-------|------|
| **工厂建设决策（二进制）** | | | |
| 可再生能源站选择 | renewable_plant_binary[200-400] | **删除** | 不再作为候选位置 |
| 电解槽建设 | electrolyzer_binary[100-150] | **删除** | 不再需要制氢设施 |
| MTJ/SAF设施建设 | mtj_facility_binary[80-100] | **合并到下方** | |
| **FT设施建设** | - | ft_facility_binary[50-80] | 新增，替代上述3种 |
| 建设决策变量总数 | **380-650** | **50-80** | **减少87%** |
| | | | |
| **产能决策（连续）** | | | |
| 电解槽容量 | electrolyzer_capacity[100-150] | **删除** | |
| MTJ设施容量估算 | mtj_capacity[80-100] (固定估算) | **替换为下方** | 原为估算值 |
| **FT反应器容量** | - | ft_capacity[50-80] | **决策变量（非估算）** |
| 产能决策变量总数 | **180-250** | **50-80** | **减少70%** |
| | | | |
| **运输决策变量** | | | |
| 氢气管道建设 | hydrogen_pipeline_binary[源×目的地] ≈ 10,000 | **删除** | 不再需要氢气运输 |
| 氢气管道容量 | hydrogen_pipeline_capacity[源×目的地] ≈ 10,000 | **删除** | |
| 氢气管道流量 | hydrogen_pipeline_flow[源×目的地×周] ≈ 520,000 | **删除** | |
| 氢气罐车流量 | hydrogen_truck_flow[源×目的地×周] ≈ 520,000 | **删除** | |
| 氢气罐车数量 | hydrogen_trucks_used[源×目的地×周] ≈ 520,000 | **删除** | |
| 天然气运输 | ng_transport[源×目的地×周] | **保留** | 继续使用 |
| SAF运输 | saf_transport[源×目的地×周] | **保留** | 继续使用 |
| 运输决策变量总数 | **~1,570,000** | **~10,000** | **减少99%** |

**目标函数中的位置集合迭代变化**:

```python
# ❌ 原模型 - 多个位置集合迭代和多种运输成本
renewable_cost = sum(... for p in renewable_plants ...)  # 删除
electrolyzer_cost = sum(... for e in electrolyzer_sites ...)  # 删除
mtj_cost = sum(... for m in mtj_facilities ...)  # 替换

# 氢气运输成本（管道+罐车）- 全部删除
hydrogen_pipeline_cost = sum(
    hydrogen_pipeline_flow[s, d, h] * pipeline_unit_cost * distance[s, d]
    for s in electrolyzer_sites  # 源点已删除
    for d in mtj_facilities
    for h in hours
)  # 删除

hydrogen_truck_cost = sum(
    hydrogen_truck_flow[s, d, h] * truck_unit_cost * distance[s, d]
    for s in electrolyzer_sites  # 源点已删除
    for d in mtj_facilities
    for h in hours
)  # 删除

# ✅ 新模型 - 统一位置集合迭代，无氢气运输成本
ft_reactor_cost = sum(... for loc in ft_facility_candidates ...)
ft_process_cost = sum(... for loc in ft_facility_candidates ...)
# 只保留天然气运输和SAF运输成本，删除氢气运输成本
```

**约束条件中的位置集合迭代变化**:

```python
# ❌ 原模型 - 多个位置集合的约束
for p in renewable_plants:  # 可再生能源约束 - 删除
    model.addConstr(...)
for e in electrolyzer_sites:  # 电解槽约束 - 删除
    model.addConstr(...)

# ✅ 新模型 - 单一位置集合的约束
for loc in ft_facility_candidates:  # FT设施约束
    model.addConstr(...)
```

**关键实现要点**:

1. **ft_facility_candidates 生成逻辑**:
   ```python
   ft_facility_candidates = []
   # 基于天然气可达性筛选
   ft_facility_candidates.extend(ng_pipeline_endpoints)
   ft_facility_candidates.extend(lng_terminals)
   ft_facility_candidates.extend(near_airport_ng_nodes)
   # 去重
   ft_facility_candidates = list(set(ft_facility_candidates))
   ```

2. **所有迭代位置集合的替换**:
   - 目标函数中的 `for loc in ...` 统一使用 `ft_facility_candidates`
   - 约束条件中的 `for loc in ...` 统一使用 `ft_facility_candidates`
   - 成本计算中的 `for loc in ...` 统一使用 `ft_facility_candidates`

3. **确保一致性**:
   - 变量创建、约束添加、成本计算中的位置集合名称必须一致
   - 避免遗留任何对 `renewable_plants` 或 `electrolyzer_sites` 的引用
   - 所有与工厂建设相关的二进制变量统一为 `ft_facility_binary`

**预期效果**:
- 决策变量总数减少 60-70%
- 模型求解速度提升 2-3倍
- 内存占用减少 50-60%
- 代码复杂度显著降低

---

### 2.5 代码结构重构方案

#### 2.5.1 类结构调整

**原类结构**（简化）:
```python
class NaturalGasSupplyChainOptimizer:
    def __init__(...)

    # 数据加载
    def _load_config()
    def _load_ng_data()
    def _load_renewable_energy_data()  # 删除
    def _load_hydrogen_infrastructure_data()  # 删除

    # 变量创建
    def _create_ng_variables()
    def _create_hydrogen_variables()  # 删除
    def _create_renewable_variables()  # 删除
    def _create_saf_variables()  # 修改

    # 约束添加
    def _add_ng_constraints()
    def _add_hydrogen_constraints()  # 删除
    def _add_saf_constraints()  # 修改

    # 成本计算
    def _calculate_ng_costs()
    def _calculate_hydrogen_costs()  # 删除
    def _calculate_saf_costs()  # 修改

    # 优化和结果
    def optimize()
    def _extract_solution()  # 修改
```

**新类结构**（FT一步法）:
```python
class NaturalGasSupplyChainOptimizerOneStep:
    def __init__(...)

    # 数据加载
    def _load_config()
    def _load_ng_data()
    def _load_ft_parameters()  # 新增 - 加载FT工艺参数

    # 变量创建
    def _create_ng_variables()
    def _create_ft_reactor_variables()  # 新增
    def _create_saf_variables()  # 简化

    # 约束添加
    def _add_ng_constraints()
    def _add_ft_reactor_constraints()  # 新增
    def _add_ft_process_constraints()  # 新增
    def _add_saf_constraints()  # 简化

    # 成本计算
    def _calculate_ng_costs()
    def _calculate_ft_reactor_costs()  # 新增
    def _calculate_ft_process_costs()  # 新增
    def _calculate_saf_costs()  # 简化

    # 优化和结果
    def optimize()
    def _extract_solution()  # 简化
    def _generate_ft_report()  # 新增 - FT工艺专门的报告
```

#### 2.5.2 详细修改计划

**Phase 1: 文件复制和基础清理**
1. 复制源文件到新文件
2. 更新文件头部文档
3. 更新类名（如需要）
4. 删除所有氢气相关的import语句
5. 删除HydrogenPipelineDistanceCalculator等氢气相关工具类的引用

**Phase 2: 配置文件更新**
1. 复制配置文件
2. 删除氢气相关参数section
3. 更新technologies section为FT工艺
4. 添加FT工艺参数（从网络搜索获取）
5. 更新成本参数
6. 更新碳排放参数

**Phase 3: 数据加载层修改**
1. 注释或删除 `_load_renewable_energy_data()`
2. 注释或删除 `_load_electrolyzer_data()`
3. 注释或删除 `_load_hydrogen_pipeline_data()`
4. 新增 `_load_ft_parameters()` 方法
5. 修改 `_load_config()` 以读取FT相关配置

**Phase 4: 变量创建层修改**
1. 注释或删除氢气相关变量创建方法
2. 新增FT反应器变量创建方法
3. 修改SAF生产变量创建逻辑
4. 确保变量命名清晰反映FT工艺

**Phase 5: 约束条件层修改**
1. 删除氢气相关所有约束
2. 新增FT反应器容量约束
3. 新增FT工艺原料消耗约束
4. 修改SAF生产约束以反映FT转化关系
5. 保留并调整需求满足约束

**Phase 6: 目标函数修改**
1. 删除氢气相关成本项
2. 新增FT反应器成本项
3. 新增FT工艺成本项
4. 更新SAF生产成本计算
5. 确保所有成本单位一致

**Phase 7: 结果提取和报告生成修改**
1. 修改 `_extract_solution()` 删除氢气结果提取
2. 新增FT设施决策结果提取
3. 新增FT工艺指标提取
4. 修改报告生成模板
5. 更新可视化图表（如有）

**Phase 8: 测试和验证**
1. 创建小规模测试数据集
2. 运行优化模型
3. 验证结果合理性
4. 检查成本计算正确性
5. 验证约束满足情况

---

## 3. 技术参数搜索需求

### 3.1 需要从网络搜索的FT工艺参数

#### 3.1.1 FT反应器技术参数
- [ ] FT反应器类型（HTFT高温/LTFT低温）选择建议
- [ ] FT反应器单位产能建设成本（元/kg产能或美元/bbl产能）
- [ ] FT反应器规模经济系数
- [ ] FT反应器使用寿命
- [ ] FT反应器年运营维护成本占CAPEX比例

#### 3.1.2 FT工艺转化参数
- [ ] 天然气 → SAF 的质量转化率（m³天然气/kg SAF）
- [ ] FT工艺的总体能量转化效率（%）
- [ ] FT工艺的碳转化率（%）
- [ ] FT工艺的SAF选择性（SAF占总产物比例）
- [ ] FT工艺副产品种类和比例（石脑油、柴油等）

#### 3.1.3 FT催化剂参数
- [ ] FT催化剂类型（铁基/钴基）选择建议
- [ ] 催化剂单位成本（元/kg或美元/kg）
- [ ] 催化剂单耗（kg催化剂/吨SAF）
- [ ] 催化剂使用寿命或更换周期
- [ ] 催化剂再生成本

#### 3.1.4 FT反应条件
- [ ] HTFT反应温度范围（℃）
- [ ] LTFT反应温度范围（℃）
- [ ] FT反应压力范围（MPa）
- [ ] FT反应器停留时间
- [ ] 合成气H2/CO比例要求

#### 3.1.5 FT工艺能耗
- [ ] FT工艺总能耗（kWh/kg SAF或MJ/kg SAF）
- [ ] 天然气制合成气能耗
- [ ] FT反应器加热能耗
- [ ] 产物分离精制能耗
- [ ] 冷却水和公用工程能耗

#### 3.1.6 FT工艺碳排放
- [ ] FT工艺直接碳排放强度（kgCO₂/kg SAF）
- [ ] FT工艺全生命周期碳排放（gCO₂e/MJ SAF）
- [ ] 与传统航煤的碳减排比例（%）
- [ ] 碳捕集与封存(CCS)潜力

#### 3.1.7 FT产品质量
- [ ] FT-SAF产品规格（密度、闪点、凝点等）
- [ ] FT-SAF与ASTM D7566标准符合性
- [ ] FT-SAF与传统航煤的掺混比例限制
- [ ] FT-SAF产品纯度和后处理需求

### 3.2 参数搜索建议

**推荐搜索关键词**（中英文）:
- "Fischer-Tropsch SAF production"
- "费托合成 可持续航空燃料"
- "FT-SPK (Fischer-Tropsch Synthetic Paraffinic Kerosene)"
- "天然气制航煤 技术经济分析"
- "GTL (Gas-to-Liquids) economics"
- "FT reactor CAPEX"
- "费托反应器 建设成本"

**推荐参考来源**:
1. 学术文献数据库（Web of Science, Google Scholar）
2. 石化行业报告（IEA, ICAO, IATA）
3. FT技术供应商资料（Shell GTL, Sasol, Velocys）
4. SAF认证标准文件（ASTM D7566）
5. 中国石化、中国石油等企业的公开资料

---

## 4. 交付物清单

### 4.1 代码文件
- [ ] `natural_gas_optimization_model_one_step.py` - FT一步法优化模型
- [ ] 相关工具类修改（如需要）

### 4.2 配置文件
- [ ] `NaturalGasSupplyChainOptimizer_one_step_config.yaml` - FT工艺配置文件
- [ ] 配置文件说明文档（更新metadata部分）

### 4.3 文档
- [ ] 本PRD文档（包含修改详细说明）
- [ ] FT工艺参数研究报告（网络搜索结果汇总）
- [ ] 代码修改对照表（列出所有修改点）
- [ ] 使用说明文档（如何运行新模型）

### 4.4 测试文件
- [ ] 单元测试文件（测试关键方法）
- [ ] 集成测试脚本（测试完整优化流程）
- [ ] 测试数据集（小规模验证数据）

---

## 5. 项目时间线

### Phase 1: PRD编写和审核（当前阶段）
- [x] 编写PRD初稿
- [ ] 用户审核和补充需求
- [ ] PRD定稿

### Phase 2: FT工艺参数研究（预计1-2天）
- [ ] 网络搜索FT工艺文献
- [ ] 整理技术参数
- [ ] 编写参数研究报告
- [ ] 确定配置文件参数值

### Phase 3: 文件创建和基础修改（预计1天）
- [ ] 复制源文件和配置文件
- [ ] 更新文件头部和类名
- [ ] 删除氢气相关import
- [ ] 更新配置文件结构

### Phase 4: 数据层和变量层修改（预计1-2天）
- [ ] 删除氢气数据加载方法
- [ ] 新增FT参数加载方法
- [ ] 删除氢气变量创建
- [ ] 新增FT反应器变量

### Phase 5: 约束和目标函数修改（预计2-3天）
- [ ] 删除氢气相关约束
- [ ] 新增FT工艺约束
- [ ] 重构目标函数
- [ ] 更新成本计算

### Phase 6: 结果提取和报告生成（预计1天）
- [ ] 修改结果提取逻辑
- [ ] 更新报告生成模板
- [ ] 调整可视化代码

### Phase 7: 测试和验证（预计2-3天）
- [ ] 创建测试数据
- [ ] 运行小规模测试
- [ ] 调试和修复问题
- [ ] 验证结果合理性

### Phase 8: 文档和交付（预计1天）
- [ ] 编写使用说明
- [ ] 整理修改对照表
- [ ] 代码注释完善
- [ ] 项目交付

**总预计时间**: 10-15个工作日

---

## 6. 风险和注意事项

### 6.1 技术风险
1. **FT工艺参数不确定性**: 网络搜索可能得到的参数差异较大，需要选择代表性数据
2. **模型复杂度**: 虽然删除了氢气部分，但FT工艺可能引入新的复杂约束
3. **求解性能**: 新模型的求解时间和收敛性需要验证

### 6.2 数据风险
1. **参数缺失**: 部分FT工艺参数可能缺乏公开数据
2. **数据时效性**: FT技术快速发展，需要使用最新参数
3. **地区适应性**: 需要确保参数适用于中国市场

### 6.3 实施风险
1. **代码耦合度**: 原代码中氢气部分可能与其他部分高度耦合，删除时需要仔细梳理
2. **测试覆盖**: 需要确保充分测试以发现潜在问题
3. **向后兼容**: 如果需要保留原模型，需要确保两个版本可以并行使用

### 6.4 注意事项
1. **配置文件兼容性**: 确保新配置文件格式与代码加载逻辑匹配
2. **单位一致性**: 特别注意FT工艺参数的单位转换
3. **约束合理性**: 确保FT工艺约束在物理上和经济上都合理
4. **文档同步**: 所有修改都需要同步更新代码注释和文档

---

## 7. 成功标准

### 7.1 功能完整性
- [ ] 模型能够成功加载FT工艺配置
- [ ] 模型能够构建完整的优化问题
- [ ] 模型能够在合理时间内求解（<1小时）
- [ ] 模型能够输出完整的结果报告

### 7.2 结果合理性
- [ ] 天然气消耗量符合FT工艺转化率
- [ ] SAF产量满足需求约束
- [ ] 总成本在合理范围内
- [ ] 碳排放计算准确

### 7.3 代码质量
- [ ] 代码结构清晰，注释完整
- [ ] 无氢气相关残留代码
- [ ] 变量命名符合规范
- [ ] 通过所有单元测试

### 7.4 文档完整性
- [ ] 配置文件说明清晰
- [ ] 使用说明文档详细
- [ ] 参数来源可追溯
- [ ] 修改记录完整

---

## 8. 后续扩展可能性

### 8.1 碳捕集与封存(CCS)集成
- 在FT工艺中增加CCS模块
- 计算CCS的成本和碳减排效益
- 优化CCS配置策略

### 8.2 多工艺路线对比
- 保留原E-CRM+TRM工艺模型
- 实现多工艺路线并行优化
- 进行技术经济对比分析

### 8.3 不确定性分析
- 对FT工艺参数进行敏感性分析
- 考虑天然气价格波动
- 分析政策激励的影响

### 8.4 动态优化
- 扩展为多周期优化
- 考虑设施扩建和退役
- 实现滚动式优化策略

---

## 9. 详细实现TodoList

本节提供了从PRD到实际代码实现的详细步骤清单。每个步骤都明确说明要修改什么、在哪里修改、以及如何修改。

### 9.1 准备阶段 (Phase 0)

#### 9.1.1 环境和文件准备
- [ ] **步骤0.1**: 备份原始文件
  - 操作: 复制 `natural_gas_optimization_model.py` → `natural_gas_optimization_model_backup.py`
  - 操作: 复制 `NaturalGasSupplyChainOptimizer_config.yaml` → `NaturalGasSupplyChainOptimizer_config_backup.yaml`
  - 目的: 保留原始双步法模型作为参考
  - 验证: 确认备份文件存在且完整

- [ ] **步骤0.2**: 创建新文件
  - 操作: 复制 `natural_gas_optimization_model.py` → `natural_gas_optimization_model_one_step.py`
  - 位置: `products/supply_chain_optimization/natural_gas_supply_chain_optimization/src/core/`
  - 操作: 复制 `NaturalGasSupplyChainOptimizer_config.yaml` → `NaturalGasSupplyChainOptimizer_one_step_config.yaml`
  - 位置: `shared/data/`
  - 验证: 新文件创建成功

- [ ] **步骤0.3**: 更新类名和模块引用
  - 文件: `natural_gas_optimization_model_one_step.py`
  - 操作: 修改类名 `NaturalGasSupplyChainOptimizer` → `NaturalGasSupplyChainOptimizerOneStep`
  - 操作: 更新类文档字符串,说明这是FT一步法模型
  - 操作: 更新配置文件路径引用指向新的yaml文件
  - 验证: 类可以正常导入,无语法错误

- [ ] **步骤0.4**: 创建Git分支
  - 操作: `git checkout -b feature/ft-one-step-model`
  - 操作: `git add natural_gas_optimization_model_one_step.py`
  - 操作: `git add NaturalGasSupplyChainOptimizer_one_step_config.yaml`
  - 操作: `git commit -m "feat: 创建FT一步法模型基础文件"`
  - 验证: 分支创建成功,初始提交完成

---

### 9.2 配置文件修改 (Phase 1)

#### 9.2.1 删除氢气和可再生能源相关参数
- [ ] **步骤1.1**: 删除可再生能源配置
  - 文件: `NaturalGasSupplyChainOptimizer_one_step_config.yaml`
  - 定位: 找到 `renewable_energy:` 配置段
  - 操作: 删除整个 `renewable_energy` 配置块
  - 删除内容包括:
    - `wind_power_plants`
    - `solar_power_plants`
    - `renewable_capacity_limits`
    - `renewable_electricity_cost`
  - 验证: yaml文件仍然有效,无语法错误

- [ ] **步骤1.2**: 删除电解槽配置
  - 文件: `NaturalGasSupplyChainOptimizer_one_step_config.yaml`
  - 定位: 找到 `electrolyzer:` 或 `hydrogen_production:` 配置段
  - 操作: 删除整个电解槽配置块
  - 删除内容包括:
    - `electrolyzer_efficiency`
    - `electrolyzer_capex`
    - `electrolyzer_opex`
    - `electrolyzer_capacity_limits`
    - `h2_production_rate`
  - 验证: yaml文件仍然有效

- [ ] **步骤1.3**: 删除氢气运输配置
  - 文件: `NaturalGasSupplyChainOptimizer_one_step_config.yaml`
  - 定位: 找到 `hydrogen_transport:` 配置段
  - 操作: 删除氢气管道和罐车运输配置
  - 删除内容包括:
    - `hydrogen_pipeline_unit_cost`
    - `hydrogen_pipeline_capex`
    - `hydrogen_pipeline_capacity`
    - `hydrogen_truck_unit_cost`
    - `hydrogen_truck_capacity`
    - `max_hydrogen_transport_distance`
  - 验证: yaml文件仍然有效

- [ ] **步骤1.4**: 删除氢气库存配置
  - 文件: `NaturalGasSupplyChainOptimizer_one_step_config.yaml`
  - 定位: 找到 `hydrogen_inventory:` 或 `hydrogen_storage:` 配置段
  - 操作: 删除氢气库存相关配置
  - 删除内容包括:
    - `hydrogen_storage_cost`
    - `hydrogen_inventory_limits`
    - `hydrogen_safety_stock`
  - 验证: yaml文件仍然有效

#### 9.2.2 修改SAF生产工艺配置
- [ ] **步骤1.5**: 删除E-CRM+TRM工艺配置
  - 文件: `NaturalGasSupplyChainOptimizer_one_step_config.yaml`
  - 定位: 找到 `technologies:` 配置段
  - 操作: 删除 `e_crm_trm` 或类似的双步法工艺配置
  - 删除内容包括:
    - `h2_consumption_ratio: 0.12` (氢气消耗比例)
    - `hydrogen_transport_required: true`
    - `methanol_intermediate_ratio`
  - 验证: yaml文件仍然有效

- [ ] **步骤1.6**: 添加FT一步法工艺配置
  - 文件: `NaturalGasSupplyChainOptimizer_one_step_config.yaml`
  - 定位: `technologies:` 配置段
  - 操作: 添加新的FT工艺配置块
  - 添加内容:
```yaml
technologies:
  ft_direct_conversion:
    name: "FT费托合成一步法SAF生产 (LTFT-Co催化)"
    technology_type: "FT_Direct"

    # 核心效率参数
    efficiency: 0.55  # 总能量转化效率
    ng_consumption_ratio: 2.0  # m³天然气/kg SAF
    h2_consumption_ratio: 0  # 不需要外部氢气
    hydrogen_transport_required: false
    methanol_intermediate_ratio: 0  # 无甲醇中间体

    # FT反应器参数
    ft_reactor_temperature_celsius: 230  # LTFT温度
    ft_reactor_pressure_mpa: 2.5
    ft_h2_co_ratio: 2.0  # H2:CO摩尔比
    ft_energy_consumption_kwh_per_kg: 2.5  # 能耗

    # 催化剂参数
    catalyst_type: "Cobalt"
    catalyst_cost_yuan_per_kg_saf: 0.06
    catalyst_lifetime_years: 4

    # 产物选择性
    c5_plus_selectivity: 0.92  # C5+选择性
    saf_fraction_in_products: 0.65  # SAF在产物中的占比
```
  - 验证: 参数值与PRD第2.3.2节一致

#### 9.2.3 添加FT反应器成本配置
- [ ] **步骤1.7**: 添加FT设施LCOE参数
  - 文件: `NaturalGasSupplyChainOptimizer_one_step_config.yaml`
  - 定位: `facility_lcoe_parameters:` 或 `cost_parameters:` 配置段
  - 操作: 替换原MTJ设施成本为FT反应器成本
  - 添加内容:
```yaml
ft_facility_lcoe_parameters:
  # 固定成本(与是否建设相关)
  fixed_capex: 50000000  # 50M yuan 固定投资
  fixed_opex_annual: 10000000  # 10M yuan/年固定运营成本

  # 可变成本(与容量相关)
  variable_capex_per_capacity: 2500  # yuan/kg产能
  variable_opex_per_kg: 0.30  # yuan/kg产品

  # 催化剂成本
  catalyst_price_yuan_per_kg: 270  # 钴催化剂价格
  catalyst_cost_per_kg_saf: 0.06
  catalyst_lifetime_years: 4

  # 设施寿命
  facility_lifetime_years: 25
  discount_rate: 0.08
```
  - 验证: 参数值与PRD第2.3.2节一致

- [ ] **步骤1.8**: 添加FT反应器容量限制
  - 文件: `NaturalGasSupplyChainOptimizer_one_step_config.yaml`
  - 定位: `capacity_limits:` 配置段
  - 操作: 添加FT反应器容量上下限(作为决策变量的约束)
  - 添加内容:
```yaml
capacity_limits:
  # SAF产量限制
  saf_max_capacity_kg_per_hour: 10000

  # FT反应器容量限制(决策变量的上下界)
  ft_reactor_max_capacity_kg_per_hour: 10000  # 单个设施最大容量
  ft_reactor_min_economic_capacity: 500  # 最小经济规模

  # 天然气供应限制
  ng_max_supply_per_source: 1000000  # m³/day
```
  - 验证: 参数合理,与决策变量定义一致

#### 9.2.4 添加FT碳排放参数
- [ ] **步骤1.9**: 更新碳排放配置
  - 文件: `NaturalGasSupplyChainOptimizer_one_step_config.yaml`
  - 定位: `carbon_emissions:` 配置段
  - 操作: 删除氢气生产碳排放,添加FT工艺碳排放
  - 删除内容:
    - `h2_production_emission`
    - `electrolyzer_embodied_carbon`
    - `renewable_energy_emission`
  - 添加内容:
```yaml
carbon_emissions:
  # 天然气相关
  ng_combustion_kgco2_per_m3: 2.0
  ng_upstream_kgco2_per_m3: 0.5

  # FT工艺碳排放
  ft_process_emission_kgco2e_per_kg_saf: 0.65  # FT反应过程
  ft_reactor_embodied_carbon_kgco2e_per_kw: 800  # 设备制造

  # SAF生命周期排放
  saf_lifecycle_gco2e_per_mj: 35  # vs 89 for conventional jet fuel

  # 运输排放
  ng_transport_kgco2_per_km_per_m3: 0.001
  saf_transport_kgco2_per_km_per_kg: 0.002
```
  - 验证: 参数值与PRD第2.3.2节一致

#### 9.2.5 更新候选位置配置
- [ ] **步骤1.10**: 简化位置集合定义
  - 文件: `NaturalGasSupplyChainOptimizer_one_step_config.yaml`
  - 定位: `location_selection:` 或 `candidate_sites:` 配置段
  - 操作: 删除可再生能源站和电解槽站点配置
  - 删除内容:
    - `renewable_plant_candidates`
    - `electrolyzer_site_candidates`
  - 操作: 添加FT设施候选位置筛选规则
  - 添加内容:
```yaml
ft_facility_candidate_selection:
  # 筛选规则
  include_ng_pipeline_endpoints: true
  include_lng_terminals: true
  include_near_airport_ng_nodes: true

  # 筛选参数
  max_distance_from_airport_km: 100
  min_ng_supply_capacity_m3_per_day: 10000

  # 位置类型优先级
  priority_order:
    - "LNG_terminal"
    - "NG_pipeline_endpoint"
    - "Near_airport_NG_node"
```
  - 验证: 配置逻辑与PRD第2.4.1节一致

- [ ] **步骤1.11**: 提交配置文件修改
  - 操作: `git add NaturalGasSupplyChainOptimizer_one_step_config.yaml`
  - 操作: `git commit -m "feat: 更新配置文件为FT一步法参数"`
  - 验证: 配置文件修改已提交

---

### 9.3 数据加载模块修改 (Phase 2)

#### 9.3.1 删除氢气和可再生能源数据加载方法
- [ ] **步骤2.1**: 定位并删除可再生能源数据加载方法
  - 文件: `natural_gas_optimization_model_one_step.py`
  - 搜索: `def _load_renewable_energy_data(` 或类似方法名
  - 操作: 删除整个方法定义
  - 操作: 在 `__init__()` 或主加载流程中删除对该方法的调用
  - 示例:
```python
# 删除这个方法
# def _load_renewable_energy_data(self):
#     """加载风电/光伏电站数据"""
#     ...

# 在__init__中删除调用
# self._load_renewable_energy_data()  # 删除这行
```
  - 验证: 代码无语法错误,未引用该方法

- [ ] **步骤2.2**: 删除电解槽数据加载方法
  - 文件: `natural_gas_optimization_model_one_step.py`
  - 搜索: `def _load_hydrogen_infrastructure_data(` 或 `_load_electrolyzer_data(`
  - 操作: 删除整个方法定义
  - 操作: 删除对该方法的所有调用
  - 验证: 代码无语法错误

- [ ] **步骤2.3**: 删除氢气运输网络数据加载
  - 文件: `natural_gas_optimization_model_one_step.py`
  - 搜索: `def _load_hydrogen_transport_network(` 或类似方法
  - 操作: 删除管道和罐车运输网络的数据加载
  - 操作: 删除氢气运输距离矩阵的计算
  - 验证: 代码无语法错误

#### 9.3.2 修改位置集合初始化
- [ ] **步骤2.4**: 删除氢气生产位置集合
  - 文件: `natural_gas_optimization_model_one_step.py`
  - 定位: `__init__()` 方法或位置集合初始化部分
  - 搜索: `self.renewable_plants =` 或 `self.electrolyzer_sites =`
  - 操作: 删除以下属性:
```python
# 删除这些属性
# self.renewable_plants = []
# self.electrolyzer_sites = []
# self.hydrogen_pipeline_network = {}
```
  - 验证: 删除后代码无语法错误

- [ ] **步骤2.5**: 添加FT设施候选位置筛选方法
  - 文件: `natural_gas_optimization_model_one_step.py`
  - 位置: 数据加载方法区域
  - 操作: 新增方法 `_generate_ft_facility_candidates()`
  - 添加代码:
```python
def _generate_ft_facility_candidates(self):
    """
    生成FT设施候选位置
    基于天然气供应可达性筛选,不包含氢气生产点

    Returns:
        list: FT设施候选位置列表
    """
    candidates = []

    # 筛选1: 天然气管道端点
    for endpoint in self.ng_pipeline_endpoints:
        if self._check_ng_supply_capacity(endpoint):
            candidates.append({
                'location_id': endpoint['id'],
                'location_type': 'NG_pipeline_endpoint',
                'lat': endpoint['lat'],
                'lon': endpoint['lon'],
                'ng_capacity': endpoint['capacity']
            })

    # 筛选2: LNG接收站
    for lng_terminal in self.lng_terminals:
        if lng_terminal['capacity'] > self.config['min_capacity_threshold']:
            candidates.append({
                'location_id': lng_terminal['id'],
                'location_type': 'LNG_terminal',
                'lat': lng_terminal['lat'],
                'lon': lng_terminal['lon'],
                'ng_capacity': lng_terminal['capacity']
            })

    # 筛选3: 机场附近且有天然气管道覆盖的位置
    max_distance_km = self.config['max_distance_from_airport_km']
    for airport in self.airports:
        nearby_ng_nodes = self._get_ng_nodes_within_distance(
            airport,
            max_distance_km
        )
        for node in nearby_ng_nodes:
            candidates.append({
                'location_id': f"{airport['id']}_ng_{node['id']}",
                'location_type': 'Near_airport_NG_node',
                'lat': node['lat'],
                'lon': node['lon'],
                'airport_id': airport['id'],
                'ng_capacity': node['capacity']
            })

    # 去重
    candidates = self._deduplicate_locations(candidates)

    self.logger.info(f"生成 {len(candidates)} 个FT设施候选位置")
    self.logger.info(f"原模型候选位置数量估算: ~{len(self.ng_sources) * 5} (包含氢气生产点)")

    return candidates

def _check_ng_supply_capacity(self, location):
    """检查位置的天然气供应能力是否满足最小要求"""
    min_capacity = self.config.get('min_ng_supply_capacity_m3_per_day', 10000)
    return location.get('capacity', 0) >= min_capacity

def _get_ng_nodes_within_distance(self, airport, max_distance_km):
    """获取机场附近指定距离内的天然气节点"""
    nearby_nodes = []
    for ng_node in self.ng_network_nodes:
        distance = self._calculate_distance(airport, ng_node)
        if distance <= max_distance_km:
            nearby_nodes.append(ng_node)
    return nearby_nodes

def _deduplicate_locations(self, candidates):
    """根据地理坐标去重候选位置"""
    seen = set()
    unique_candidates = []
    for candidate in candidates:
        coord_key = (round(candidate['lat'], 4), round(candidate['lon'], 4))
        if coord_key not in seen:
            seen.add(coord_key)
            unique_candidates.append(candidate)
    return unique_candidates
```
  - 验证: 方法可以正常调用,返回合理数量的候选位置

- [ ] **步骤2.6**: 在初始化中调用FT候选位置生成
  - 文件: `natural_gas_optimization_model_one_step.py`
  - 定位: `__init__()` 方法
  - 操作: 添加FT候选位置生成调用
```python
def __init__(self, config_path):
    # ... 现有初始化代码 ...

    # 删除: self._load_renewable_energy_data()
    # 删除: self._load_hydrogen_infrastructure_data()

    # 新增: 生成FT设施候选位置
    self.ft_facility_candidates = self._generate_ft_facility_candidates()
```
  - 验证: 初始化成功,ft_facility_candidates属性存在

- [ ] **步骤2.7**: 提交数据加载模块修改
  - 操作: `git add natural_gas_optimization_model_one_step.py`
  - 操作: `git commit -m "feat: 删除氢气数据加载,添加FT候选位置生成"`
  - 验证: 代码修改已提交

---

### 9.4 决策变量创建修改 (Phase 3)

#### 9.4.1 删除氢气相关决策变量
- [ ] **步骤3.1**: 删除氢气生产变量创建方法
  - 文件: `natural_gas_optimization_model_one_step.py`
  - 搜索: `def _create_hydrogen_production_variables(`
  - 操作: 删除整个方法
  - 删除的变量包括:
    - `hydrogen_production[location, hour]`
    - `electrolyzer_binary[location]`
    - `electrolyzer_capacity[location]`
  - 操作: 在变量创建主流程中删除对该方法的调用
  - 验证: 删除后无语法错误

- [ ] **步骤3.2**: 删除氢气运输变量创建方法
  - 文件: `natural_gas_optimization_model_one_step.py`
  - 搜索: `def _create_hydrogen_transport_variables(`
  - 操作: 删除整个方法
  - 删除的变量包括:
    - `hydrogen_pipeline_flow[source, dest, week]`
    - `hydrogen_truck_flow[source, dest, week]`
    - `hydrogen_pipeline_binary[source, dest]`
    - `hydrogen_pipeline_capacity[source, dest]`
    - `hydrogen_trucks_used[source, dest, week]`
  - 验证: 删除后无语法错误

- [ ] **步骤3.3**: 删除氢气库存变量创建方法
  - 文件: `natural_gas_optimization_model_one_step.py`
  - 搜索: `def _create_hydrogen_inventory_variables(`
  - 操作: 删除整个方法
  - 删除的变量包括:
    - `hydrogen_inventory[location, hour]`
    - `hydrogen_storage_capacity[location]`
  - 验证: 删除后无语法错误

- [ ] **步骤3.4**: 删除可再生能源变量创建方法
  - 文件: `natural_gas_optimization_model_one_step.py`
  - 搜索: `def _create_renewable_energy_variables(`
  - 操作: 删除整个方法
  - 删除的变量包括:
    - `renewable_energy_usage[plant, hour]`
    - `renewable_plant_binary[plant]`
  - 验证: 删除后无语法错误

#### 9.4.2 创建FT反应器决策变量
- [ ] **步骤3.5**: 新增FT反应器变量创建方法
  - 文件: `natural_gas_optimization_model_one_step.py`
  - 位置: 变量创建方法区域
  - 操作: 新增方法 `_create_ft_facility_variables()`
  - 添加代码:
```python
def _create_ft_facility_variables(self):
    """
    创建FT反应器设施相关决策变量

    关键决策:
    1. ft_facility_binary: FT设施建设决策(0/1)
    2. ft_capacity: FT反应器容量决策(连续,kg/h)

    替代原模型中的:
    - electrolyzer_binary (电解槽建设)
    - electrolyzer_capacity (电解槽容量)
    - mtj_facility_binary (甲醇转化设施建设)
    """
    self.logger.info("创建FT反应器决策变量...")

    # 1. FT设施建设决策变量(二进制)
    self.ft_facility_binary = {}
    for loc in self.ft_facility_candidates:
        loc_id = loc['location_id']
        self.ft_facility_binary[loc_id] = self.model.addVar(
            vtype=gp.GRB.BINARY,
            name=f"ft_facility_binary_{loc_id}"
        )

    self.logger.info(f"  创建 {len(self.ft_facility_binary)} 个FT设施建设决策变量")

    # 2. FT反应器容量决策变量(连续)
    # 这是核心决策变量,由优化器根据成本和需求自动确定最优值
    self.ft_capacity = {}
    ft_max_capacity = self.config['capacity_limits']['ft_reactor_max_capacity_kg_per_hour']

    for loc in self.ft_facility_candidates:
        loc_id = loc['location_id']
        self.ft_capacity[loc_id] = self.model.addVar(
            lb=0.0,
            ub=ft_max_capacity,
            vtype=gp.GRB.CONTINUOUS,
            name=f"ft_capacity_{loc_id}"
        )

    self.logger.info(f"  创建 {len(self.ft_capacity)} 个FT反应器容量决策变量")
    self.logger.info(f"  容量范围: [0, {ft_max_capacity}] kg/h")

    # 对比原模型
    original_vars_estimate = len(self.ft_facility_candidates) * 5  # 估算原模型变量数
    reduction_pct = (1 - len(self.ft_facility_binary) / original_vars_estimate) * 100
    self.logger.info(f"  原模型建设决策变量估算: ~{original_vars_estimate}")
    self.logger.info(f"  决策变量减少约: {reduction_pct:.1f}%")

    self.model.update()
```
  - 验证: 变量创建成功,变量数量合理

- [ ] **步骤3.6**: 更新SAF生产变量创建
  - 文件: `natural_gas_optimization_model_one_step.py`
  - 搜索: `def _create_production_variables(` 或 `_create_saf_variables(`
  - 操作: 修改SAF生产变量的位置集合
  - 修改前:
```python
# 原代码可能在多个位置集合上创建变量
for loc in self.mtj_facilities:  # 旧的位置集合
    self.saf_production[loc, week] = ...
```
  - 修改后:
```python
# 统一使用ft_facility_candidates
for loc in self.ft_facility_candidates:
    loc_id = loc['location_id']
    for week in self.weeks:
        self.saf_production[loc_id, week] = self.model.addVar(
            lb=0.0,
            vtype=gp.GRB.CONTINUOUS,
            name=f"saf_production_{loc_id}_{week}"
        )
```
  - 验证: SAF生产变量位置集合已更新

- [ ] **步骤3.7**: 更新变量创建主流程
  - 文件: `natural_gas_optimization_model_one_step.py`
  - 定位: `_create_decision_variables()` 或类似的主流程方法
  - 操作: 删除氢气相关变量创建调用,添加FT变量创建调用
  - 修改前:
```python
def _create_decision_variables(self):
    self._create_ng_variables()
    self._create_renewable_energy_variables()  # 删除
    self._create_electrolyzer_variables()  # 删除
    self._create_hydrogen_transport_variables()  # 删除
    self._create_hydrogen_inventory_variables()  # 删除
    self._create_saf_variables()  # 修改
```
  - 修改后:
```python
def _create_decision_variables(self):
    self._create_ng_variables()  # 保留
    self._create_ft_facility_variables()  # 新增
    self._create_saf_variables()  # 已修改为使用ft_facility_candidates
    self._create_saf_transport_variables()  # 保留
    self._create_saf_inventory_variables()  # 保留
```
  - 验证: 变量创建流程完整,无遗漏

- [ ] **步骤3.8**: 提交决策变量修改
  - 操作: `git add natural_gas_optimization_model_one_step.py`
  - 操作: `git commit -m "feat: 删除氢气变量,创建FT反应器决策变量"`
  - 验证: 变量修改已提交

---

### 9.5 约束条件修改 (Phase 4)

#### 9.5.1 删除氢气相关约束
- [ ] **步骤4.1**: 删除电解槽约束方法
  - 文件: `natural_gas_optimization_model_one_step.py`
  - 搜索: `def _add_hydrogen_production_constraints(`
  - 操作: 删除整个方法
  - 删除的约束包括:
    - 电解槽产能约束
    - 电解槽能耗约束
    - 电解槽建设逻辑约束
  - 验证: 删除后无语法错误

- [ ] **步骤4.2**: 删除氢气运输约束方法
  - 文件: `natural_gas_optimization_model_one_step.py`
  - 搜索: `def _add_hydrogen_transport_constraints(`
  - 操作: 删除整个方法
  - 删除的约束包括:
    - 氢气管道容量约束
    - 氢气罐车容量约束
    - 氢气运输距离约束
    - 氢气管道建设逻辑约束
  - 验证: 删除后无语法错误

- [ ] **步骤4.3**: 删除氢气平衡约束方法
  - 文件: `natural_gas_optimization_model_one_step.py`
  - 搜索: `def _add_hydrogen_balance_constraints(`
  - 操作: 删除整个方法
  - 删除的约束: 氢气物料平衡方程
  - 验证: 删除后无语法错误

- [ ] **步骤4.4**: 删除氢气库存约束方法
  - 文件: `natural_gas_optimization_model_one_step.py`
  - 搜索: `def _add_hydrogen_inventory_constraints(`
  - 操作: 删除整个方法
  - 删除的约束: 氢气库存上下限约束
  - 验证: 删除后无语法错误

- [ ] **步骤4.5**: 删除可再生能源约束方法
  - 文件: `natural_gas_optimization_model_one_step.py`
  - 搜索: `def _add_renewable_energy_constraints(`
  - 操作: 删除整个方法
  - 删除的约束: 可再生能源供应上限约束、出力约束
  - 验证: 删除后无语法错误

#### 9.5.2 添加FT反应器约束
- [ ] **步骤4.6**: 新增FT反应器容量约束方法
  - 文件: `natural_gas_optimization_model_one_step.py`
  - 位置: 约束添加方法区域
  - 操作: 新增方法 `_add_ft_capacity_constraints()`
  - 添加代码:
```python
def _add_ft_capacity_constraints(self):
    """
    添加FT反应器容量相关约束

    约束1: 产量不超过容量(基于决策变量)
    约束2: 容量与建设决策的Big-M约束
    约束3: 最小经济规模约束(可选)
    """
    self.logger.info("添加FT反应器容量约束...")

    hours_per_week = 168  # 7天 * 24小时

    # 约束1: SAF产量不超过FT反应器容量
    for loc in self.ft_facility_candidates:
        loc_id = loc['location_id']
        for week in self.weeks:
            self.model.addConstr(
                self.saf_production[loc_id, week] <=
                self.ft_capacity[loc_id] * hours_per_week,
                name=f"ft_capacity_limit_{loc_id}_{week}"
            )

    self.logger.info(f"  添加 {len(self.ft_facility_candidates) * len(self.weeks)} 个产能约束")

    # 约束2: Big-M约束 - 容量与建设决策关联
    ft_max_capacity = self.config['capacity_limits']['ft_reactor_max_capacity_kg_per_hour']

    for loc in self.ft_facility_candidates:
        loc_id = loc['location_id']
        # 如果不建设(binary=0),容量必须为0
        # 如果建设(binary=1),容量可以在[0, ft_max_capacity]范围内由优化器决定
        self.model.addConstr(
            self.ft_capacity[loc_id] <=
            ft_max_capacity * self.ft_facility_binary[loc_id],
            name=f"ft_build_logic_{loc_id}"
        )

    self.logger.info(f"  添加 {len(self.ft_facility_candidates)} 个Big-M建设逻辑约束")

    # 约束3: 最小经济规模约束(可选)
    if self.config['capacity_limits'].get('ft_reactor_min_economic_capacity'):
        ft_min_capacity = self.config['capacity_limits']['ft_reactor_min_economic_capacity']

        for loc in self.ft_facility_candidates:
            loc_id = loc['location_id']
            # 如果建设,容量至少要达到最小经济规模
            self.model.addConstr(
                self.ft_capacity[loc_id] >=
                ft_min_capacity * self.ft_facility_binary[loc_id],
                name=f"ft_min_capacity_{loc_id}"
            )

        self.logger.info(f"  添加 {len(self.ft_facility_candidates)} 个最小经济规模约束")
        self.logger.info(f"  最小经济规模: {ft_min_capacity} kg/h")
```
  - 验证: 约束添加成功,约束数量合理

- [ ] **步骤4.7**: 新增FT工艺约束方法
  - 文件: `natural_gas_optimization_model_one_step.py`
  - 操作: 新增方法 `_add_ft_process_constraints()`
  - 添加代码:
```python
def _add_ft_process_constraints(self):
    """
    添加FT工艺相关约束

    约束1: 天然气消耗与SAF产量的关系
    约束2: FT能耗约束(如果有能源限制)
    """
    self.logger.info("添加FT工艺约束...")

    ng_consumption_ratio = self.config['technologies']['ft_direct_conversion']['ng_consumption_ratio']

    # 约束1: 天然气消耗约束
    for loc in self.ft_facility_candidates:
        loc_id = loc['location_id']
        for week in self.weeks:
            # 天然气供应到FT设施 >= SAF产量 * 天然气消耗比例
            self.model.addConstr(
                self.ng_supply_to_ft[loc_id, week] >=
                self.saf_production[loc_id, week] * ng_consumption_ratio,
                name=f"ft_ng_consumption_{loc_id}_{week}"
            )

    self.logger.info(f"  添加 {len(self.ft_facility_candidates) * len(self.weeks)} 个天然气消耗约束")
    self.logger.info(f"  天然气消耗比例: {ng_consumption_ratio} m³/kg SAF")

    # 约束2: FT能耗约束(可选,如果有电力供应限制)
    if 'ft_energy_consumption_kwh_per_kg' in self.config['technologies']['ft_direct_conversion']:
        ft_energy_per_kg = self.config['technologies']['ft_direct_conversion']['ft_energy_consumption_kwh_per_kg']

        for loc in self.ft_facility_candidates:
            loc_id = loc['location_id']
            for week in self.weeks:
                self.model.addConstr(
                    self.energy_consumption[loc_id, week] ==
                    self.saf_production[loc_id, week] * ft_energy_per_kg,
                    name=f"ft_energy_{loc_id}_{week}"
                )

        self.logger.info(f"  添加 {len(self.ft_facility_candidates) * len(self.weeks)} 个能耗约束")
```
  - 验证: 约束添加成功

#### 9.5.3 修改SAF生产约束
- [ ] **步骤4.8**: 更新SAF产量约束
  - 文件: `natural_gas_optimization_model_one_step.py`
  - 搜索: `def _add_production_constraints(` 或 `_add_saf_constraints(`
  - 操作: 修改SAF产量计算约束,删除氢气相关项
  - 修改前:
```python
# 原约束可能包含氢气消耗
# saf_production = f(ng, h2, methanol)
self.model.addConstr(
    self.saf_production[loc, w] ==
    (self.ng_consumption[loc, w] / ng_ratio +
     self.h2_consumption[loc, w] / h2_ratio) * efficiency,
    name=f"saf_production_{loc}_{w}"
)
```
  - 修改后:
```python
# 新约束仅基于天然气
# saf_production = f(ng)
for loc in self.ft_facility_candidates:
    loc_id = loc['location_id']
    for week in self.weeks:
        # FT一步法: SAF产量直接由天然气转化
        self.model.addConstr(
            self.saf_production[loc_id, week] ==
            self.ng_consumption[loc_id, week] / ng_to_saf_ratio,
            name=f"saf_production_ft_{loc_id}_{week}"
        )
```
  - 验证: SAF产量约束已更新,无氢气相关项

- [ ] **步骤4.9**: 更新约束添加主流程
  - 文件: `natural_gas_optimization_model_one_step.py`
  - 定位: `_add_constraints()` 或类似主流程方法
  - 操作: 删除氢气约束调用,添加FT约束调用
  - 修改前:
```python
def _add_constraints(self):
    self._add_ng_constraints()
    self._add_renewable_energy_constraints()  # 删除
    self._add_hydrogen_production_constraints()  # 删除
    self._add_hydrogen_transport_constraints()  # 删除
    self._add_hydrogen_balance_constraints()  # 删除
    self._add_hydrogen_inventory_constraints()  # 删除
    self._add_saf_constraints()  # 修改
```
  - 修改后:
```python
def _add_constraints(self):
    self._add_ng_constraints()  # 保留
    self._add_ft_capacity_constraints()  # 新增
    self._add_ft_process_constraints()  # 新增
    self._add_saf_production_constraints()  # 已修改
    self._add_saf_transport_constraints()  # 保留
    self._add_saf_inventory_constraints()  # 保留
    self._add_demand_satisfaction_constraints()  # 保留
```
  - 验证: 约束添加流程完整

- [ ] **步骤4.10**: 提交约束修改
  - 操作: `git add natural_gas_optimization_model_one_step.py`
  - 操作: `git commit -m "feat: 删除氢气约束,添加FT反应器约束"`
  - 验证: 约束修改已提交

---

### 9.6 目标函数修改 (Phase 5)

#### 9.6.1 删除氢气相关成本计算
- [ ] **步骤5.1**: 删除可再生能源成本计算方法
  - 文件: `natural_gas_optimization_model_one_step.py`
  - 搜索: `def _calculate_renewable_energy_costs(`
  - 操作: 删除整个方法
  - 删除的成本包括:
    - 可再生能源发电成本
    - 可再生能源站选择成本
  - 验证: 删除后无语法错误

- [ ] **步骤5.2**: 删除电解槽成本计算方法
  - 文件: `natural_gas_optimization_model_one_step.py`
  - 搜索: `def _calculate_hydrogen_production_costs(` 或 `_calculate_electrolyzer_costs(`
  - 操作: 删除整个方法
  - 删除的成本包括:
    - 电解槽CAPEX
    - 电解槽OPEX
    - 氢气生产成本
  - 验证: 删除后无语法错误

- [ ] **步骤5.3**: 删除氢气运输成本计算方法
  - 文件: `natural_gas_optimization_model_one_step.py`
  - 搜索: `def _calculate_hydrogen_transport_costs(`
  - 操作: 删除整个方法
  - 删除的成本包括:
    - 氢气管道运输成本
    - 氢气管道建设成本
    - 氢气罐车运输成本
    - 氢气罐车调度成本
  - 详细删除:
```python
# 删除这个方法
# def _calculate_hydrogen_transport_costs(self):
#     # 管道运输成本
#     hydrogen_pipeline_cost = gp.quicksum(
#         self.hydrogen_pipeline_flow[s, d, h] * pipeline_unit_cost * distance[s, d]
#         for s in self.electrolyzer_sites  # 源点已删除
#         for d in self.mtj_facilities
#         for h in self.hours
#     )
#
#     # 罐车运输成本
#     hydrogen_truck_cost = gp.quicksum(
#         self.hydrogen_truck_flow[s, d, h] * truck_unit_cost * distance[s, d]
#         for s in self.electrolyzer_sites  # 源点已删除
#         for d in self.mtj_facilities
#         for h in self.hours
#     )
#
#     return hydrogen_pipeline_cost + hydrogen_truck_cost
```
  - 验证: 删除后无语法错误

- [ ] **步骤5.4**: 删除氢气库存成本计算
  - 文件: `natural_gas_optimization_model_one_step.py`
  - 搜索: `def _calculate_hydrogen_inventory_costs(`
  - 操作: 删除整个方法
  - 删除的成本: 氢气库存成本
  - 验证: 删除后无语法错误

#### 9.6.2 添加FT反应器成本计算
- [ ] **步骤5.5**: 新增FT反应器成本计算方法
  - 文件: `natural_gas_optimization_model_one_step.py`
  - 位置: 成本计算方法区域
  - 操作: 新增方法 `_calculate_ft_reactor_costs()`
  - 添加代码:
```python
def _calculate_ft_reactor_costs(self):
    """
    计算FT反应器设施成本

    成本组成:
    1. 固定CAPEX(与建设决策相关)
    2. 可变CAPEX(与容量决策相关)
    3. 固定OPEX(与建设决策相关)
    4. 可变OPEX(在工艺成本中计算)

    关键: 成本基于决策变量ft_capacity,不是固定估算值
    """
    self.logger.info("计算FT反应器设施成本...")

    config = self.config['ft_facility_lcoe_parameters']

    fixed_capex = config['fixed_capex']
    variable_capex_per_capacity = config['variable_capex_per_capacity']
    fixed_opex_annual = config['fixed_opex_annual']
    facility_lifetime = config['facility_lifetime_years']

    # 1. 固定CAPEX(摊销)
    ft_reactor_capex_fixed = gp.quicksum(
        self.ft_facility_binary[loc['location_id']] * fixed_capex / facility_lifetime
        for loc in self.ft_facility_candidates
    )

    # 2. 可变CAPEX(基于容量决策变量,摊销)
    ft_reactor_capex_variable = gp.quicksum(
        self.ft_capacity[loc['location_id']] * variable_capex_per_capacity / facility_lifetime
        for loc in self.ft_facility_candidates
    )

    ft_reactor_capex_total = ft_reactor_capex_fixed + ft_reactor_capex_variable

    # 3. 固定OPEX(年度)
    ft_reactor_opex_fixed = gp.quicksum(
        self.ft_facility_binary[loc['location_id']] * fixed_opex_annual
        for loc in self.ft_facility_candidates
    )

    self.logger.info(f"  FT反应器CAPEX: 固定 + 可变(基于容量决策)")
    self.logger.info(f"  候选位置数: {len(self.ft_facility_candidates)}")

    return ft_reactor_capex_total + ft_reactor_opex_fixed

def _calculate_ft_process_costs(self):
    """
    计算FT工艺运营成本

    成本组成:
    1. FT工艺变动成本(与产量相关)
    2. 催化剂成本(与产量相关)
    3. 能耗成本(与产量相关)
    """
    self.logger.info("计算FT工艺成本...")

    config_tech = self.config['technologies']['ft_direct_conversion']
    config_cost = self.config['ft_facility_lcoe_parameters']

    variable_opex_per_kg = config_cost['variable_opex_per_kg']
    catalyst_cost_per_kg_saf = config_cost['catalyst_cost_per_kg_saf']
    electricity_price = self.config.get('electricity_price_yuan_per_kwh', 0.5)
    ft_energy_per_kg = config_tech.get('ft_energy_consumption_kwh_per_kg', 2.5)

    # 1. FT工艺变动成本
    ft_process_cost = gp.quicksum(
        self.saf_production[loc['location_id'], w] * variable_opex_per_kg
        for loc in self.ft_facility_candidates
        for w in self.weeks
    )

    # 2. 催化剂成本
    ft_catalyst_cost = gp.quicksum(
        self.saf_production[loc['location_id'], w] * catalyst_cost_per_kg_saf
        for loc in self.ft_facility_candidates
        for w in self.weeks
    )

    # 3. 能耗成本
    ft_energy_cost = gp.quicksum(
        self.saf_production[loc['location_id'], w] * ft_energy_per_kg * electricity_price
        for loc in self.ft_facility_candidates
        for w in self.weeks
    )

    self.logger.info(f"  工艺成本组成: 变动OPEX + 催化剂 + 能耗")

    return ft_process_cost + ft_catalyst_cost + ft_energy_cost
```
  - 验证: 成本计算方法正常运行

#### 9.6.3 更新目标函数
- [ ] **步骤5.6**: 修改目标函数构建方法
  - 文件: `natural_gas_optimization_model_one_step.py`
  - 搜索: `def _build_objective_function(` 或 `_calculate_total_cost(`
  - 操作: 删除氢气相关成本,添加FT成本
  - 修改前:
```python
def _calculate_total_cost(self):
    total_cost = (
        self._calculate_ng_costs() +
        self._calculate_renewable_energy_costs() +  # 删除
        self._calculate_hydrogen_production_costs() +  # 删除
        self._calculate_hydrogen_transport_costs() +  # 删除
        self._calculate_hydrogen_inventory_costs() +  # 删除
        self._calculate_saf_production_costs() +  # 修改
        self._calculate_saf_transport_costs() +
        self._calculate_saf_inventory_costs() +
        self._calculate_shortage_penalty()
    )
    return total_cost
```
  - 修改后:
```python
def _calculate_total_cost(self):
    """
    计算总成本 - FT一步法模型

    成本组成(无氢气相关成本):
    1. 天然气采购和运输成本
    2. FT反应器设施成本(CAPEX+OPEX)
    3. FT工艺成本(变动+催化剂+能耗)
    4. SAF运输成本
    5. SAF库存成本
    6. 缺货惩罚成本
    """
    self.logger.info("构建目标函数...")

    # 1. 天然气成本
    ng_cost = self._calculate_ng_costs()

    # 2. FT反应器成本(替代电解槽和MTJ设施成本)
    ft_reactor_cost = self._calculate_ft_reactor_costs()

    # 3. FT工艺成本(替代氢气生产和甲醇合成成本)
    ft_process_cost = self._calculate_ft_process_costs()

    # 4. SAF运输成本
    saf_transport_cost = self._calculate_saf_transport_costs()

    # 5. SAF库存成本
    saf_inventory_cost = self._calculate_saf_inventory_costs()

    # 6. 缺货惩罚
    shortage_penalty = self._calculate_shortage_penalty()

    total_cost = (
        ng_cost +
        ft_reactor_cost +
        ft_process_cost +
        saf_transport_cost +
        saf_inventory_cost +
        shortage_penalty
    )

    self.logger.info("目标函数构建完成")
    self.logger.info("成本组成: NG + FT设施 + FT工艺 + SAF运输 + SAF库存 + 惩罚")
    self.logger.info("已删除: 可再生能源 + 电解槽 + 氢气运输 + 氢气库存成本")

    return total_cost
```
  - 验证: 目标函数构建成功,无氢气成本项

- [ ] **步骤5.7**: 设置模型目标
  - 文件: `natural_gas_optimization_model_one_step.py`
  - 定位: 优化模型设置部分
  - 操作: 确保目标函数正确设置
```python
def optimize(self):
    """运行优化"""
    self.logger.info("开始优化...")

    # 构建目标函数
    total_cost = self._calculate_total_cost()

    # 设置目标为最小化总成本
    self.model.setObjective(total_cost, gp.GRB.MINIMIZE)

    # 优化
    self.model.optimize()

    self.logger.info("优化完成")
```
  - 验证: 模型可以正常优化

- [ ] **步骤5.8**: 提交目标函数修改
  - 操作: `git add natural_gas_optimization_model_one_step.py`
  - 操作: `git commit -m "feat: 更新目标函数为FT一步法成本结构"`
  - 验证: 目标函数修改已提交

---

### 9.7 结果提取和报告修改 (Phase 6)

#### 9.7.1 修改结果提取方法
- [ ] **步骤6.1**: 删除氢气相关结果提取
  - 文件: `natural_gas_optimization_model_one_step.py`
  - 搜索: `def _extract_solution(` 或 `_parse_results(`
  - 操作: 删除氢气生产、运输、库存结果的提取
  - 删除内容:
```python
# 删除这些结果提取
# hydrogen_production_results = {
#     loc: self.hydrogen_production[loc, h].X
#     for loc in self.electrolyzer_sites
#     for h in self.hours
# }
#
# hydrogen_transport_results = ...
# hydrogen_inventory_results = ...
```
  - 验证: 结果提取无语法错误

- [ ] **步骤6.2**: 添加FT反应器结果提取
  - 文件: `natural_gas_optimization_model_one_step.py`
  - 定位: `_extract_solution()` 方法
  - 操作: 添加FT设施建设和容量决策结果提取
  - 添加代码:
```python
def _extract_ft_facility_results(self):
    """
    提取FT设施决策结果

    Returns:
        dict: FT设施结果,包括建设决策和容量决策
    """
    ft_results = {
        'facilities_built': [],
        'capacity_decisions': {},
        'total_capacity': 0,
        'facility_count': 0
    }

    for loc in self.ft_facility_candidates:
        loc_id = loc['location_id']

        # 建设决策
        is_built = self.ft_facility_binary[loc_id].X > 0.5

        if is_built:
            # 容量决策(关键结果)
            capacity = self.ft_capacity[loc_id].X

            ft_results['facilities_built'].append({
                'location_id': loc_id,
                'location_type': loc['location_type'],
                'lat': loc['lat'],
                'lon': loc['lon'],
                'capacity_kg_per_hour': capacity,
                'capacity_kg_per_year': capacity * 8760  # 假设全年运行
            })

            ft_results['capacity_decisions'][loc_id] = capacity
            ft_results['total_capacity'] += capacity
            ft_results['facility_count'] += 1

    self.logger.info(f"提取到 {ft_results['facility_count']} 个FT设施建设决策")
    self.logger.info(f"总容量: {ft_results['total_capacity']:.2f} kg/h")

    return ft_results
```
  - 验证: FT结果提取成功

- [ ] **步骤6.3**: 更新SAF生产结果提取
  - 文件: `natural_gas_optimization_model_one_step.py`
  - 定位: SAF生产结果提取部分
  - 操作: 确保使用ft_facility_candidates位置集合
```python
def _extract_saf_production_results(self):
    """提取SAF生产结果"""
    saf_production_results = {}

    for loc in self.ft_facility_candidates:  # 使用新的位置集合
        loc_id = loc['location_id']
        saf_production_results[loc_id] = {}

        for week in self.weeks:
            production = self.saf_production[loc_id, week].X
            saf_production_results[loc_id][week] = production

    return saf_production_results
```
  - 验证: SAF生产结果提取正常

#### 9.7.2 修改报告生成方法
- [ ] **步骤6.4**: 删除氢气相关报告内容
  - 文件: `natural_gas_optimization_model_one_step.py`
  - 搜索: `def _generate_report(` 或 `_create_summary(`
  - 操作: 删除氢气生产、运输、库存的报告生成
  - 删除内容:
    - 氢气产量统计
    - 氢气运输网络图
    - 电解槽建设地图
    - 可再生能源使用统计
  - 验证: 报告生成无语法错误

- [ ] **步骤6.5**: 添加FT设施报告内容
  - 文件: `natural_gas_optimization_model_one_step.py`
  - 定位: `_generate_report()` 方法
  - 操作: 添加FT设施建设和容量决策的报告
  - 添加代码:
```python
def _generate_ft_facility_report(self, ft_results):
    """
    生成FT设施决策报告

    报告内容:
    1. FT设施建设决策表
    2. 容量决策统计
    3. 设施位置地图
    4. 成本分解
    """
    report_sections = []

    # 1. 设施建设概览
    overview = {
        '建设的FT设施数量': ft_results['facility_count'],
        '总SAF生产容量(kg/h)': ft_results['total_capacity'],
        '总SAF生产容量(吨/年)': ft_results['total_capacity'] * 8.76,
        '候选位置总数': len(self.ft_facility_candidates),
        '建设比例': f"{ft_results['facility_count'] / len(self.ft_facility_candidates) * 100:.1f}%"
    }
    report_sections.append(('FT设施建设概览', overview))

    # 2. 详细设施列表
    facilities_df = pd.DataFrame(ft_results['facilities_built'])
    if not facilities_df.empty:
        facilities_df = facilities_df.sort_values('capacity_kg_per_hour', ascending=False)
        report_sections.append(('FT设施详细列表', facilities_df))

    # 3. 容量决策统计
    capacities = [f['capacity_kg_per_hour'] for f in ft_results['facilities_built']]
    if capacities:
        capacity_stats = {
            '最大容量(kg/h)': max(capacities),
            '最小容量(kg/h)': min(capacities),
            '平均容量(kg/h)': np.mean(capacities),
            '中位数容量(kg/h)': np.median(capacities),
            '容量标准差': np.std(capacities)
        }
        report_sections.append(('FT反应器容量决策统计', capacity_stats))

    # 4. 按位置类型分组统计
    location_type_stats = facilities_df.groupby('location_type').agg({
        'capacity_kg_per_hour': ['count', 'sum', 'mean']
    })
    report_sections.append(('按位置类型统计', location_type_stats))

    return report_sections

def _generate_comparison_with_original_model(self):
    """
    生成与原模型的对比报告

    对比维度:
    1. 候选位置数量
    2. 决策变量数量
    3. 约束数量
    4. 求解时间
    """
    comparison = {
        '维度': ['候选位置数', '建设决策变量', '容量决策变量', '运输变量', '总变量数', '总约束数'],
        '原模型(E-CRM+TRM)': [
            '~500 (含氢气生产点)',
            '~650 (含电解槽+MTJ)',
            '~650',
            '~1,570,000 (含氢气运输)',
            '~2,000,000',
            '~3,000,000'
        ],
        'FT一步法模型': [
            f"{len(self.ft_facility_candidates)} (仅天然气相关)",
            f"{len(self.ft_facility_binary)}",
            f"{len(self.ft_capacity)}",
            '~10,000 (仅NG和SAF)',
            f"{self.model.NumVars}",
            f"{self.model.NumConstrs}"
        ],
        '变化': [
            '-75%',
            '-87%',
            '-87%',
            '-99%',
            '-60% 至 -70%',
            '-50% 至 -60%'
        ]
    }

    comparison_df = pd.DataFrame(comparison)

    return comparison_df
```
  - 验证: FT报告生成成功

#### 9.7.3 更新可视化输出
- [ ] **步骤6.6**: 删除氢气相关可视化
  - 文件: `natural_gas_optimization_model_one_step.py`
  - 搜索: 可视化相关方法
  - 操作: 删除以下可视化:
    - 电解槽位置地图
    - 氢气管道网络图
    - 氢气流量桑基图
    - 可再生能源站分布图
  - 验证: 可视化代码无语法错误

- [ ] **步骤6.7**: 添加FT设施可视化
  - 文件: `natural_gas_optimization_model_one_step.py`
  - 操作: 添加FT设施和容量的可视化
  - 添加代码:
```python
def _visualize_ft_facility_locations(self, ft_results):
    """
    可视化FT设施建设位置和容量

    地图要素:
    1. FT设施位置(按容量大小显示)
    2. 天然气供应源
    3. 机场需求点
    4. 连接线(天然气供应→FT→机场)
    """
    import matplotlib.pyplot as plt
    from matplotlib import cm

    fig, ax = plt.subplots(figsize=(16, 12))

    # 1. 绘制FT设施(气泡大小表示容量)
    facilities = ft_results['facilities_built']
    if facilities:
        lats = [f['lat'] for f in facilities]
        lons = [f['lon'] for f in facilities]
        capacities = [f['capacity_kg_per_hour'] for f in facilities]

        # 归一化容量用于颜色映射
        max_capacity = max(capacities)
        colors = [c / max_capacity for c in capacities]

        scatter = ax.scatter(
            lons, lats,
            s=[c * 10 for c in capacities],  # 气泡大小
            c=colors,
            cmap='YlOrRd',
            alpha=0.7,
            edgecolors='black',
            linewidths=2,
            label='FT设施'
        )

        # 添加容量标注
        for f in facilities:
            ax.annotate(
                f"{f['capacity_kg_per_hour']:.0f} kg/h",
                (f['lon'], f['lat']),
                fontsize=8,
                ha='center'
            )

        plt.colorbar(scatter, ax=ax, label='容量(归一化)')

    # 2. 绘制天然气源
    for ng_source in self.ng_sources:
        ax.plot(
            ng_source['lon'], ng_source['lat'],
            'bs',  # 蓝色方块
            markersize=8,
            label='天然气源' if ng_source == self.ng_sources[0] else ""
        )

    # 3. 绘制机场
    for airport in self.airports:
        ax.plot(
            airport['lon'], airport['lat'],
            'r^',  # 红色三角形
            markersize=10,
            label='机场' if airport == self.airports[0] else ""
        )

    ax.set_xlabel('经度', fontsize=12)
    ax.set_ylabel('纬度', fontsize=12)
    ax.set_title('FT设施建设位置和容量分布', fontsize=16, fontweight='bold')
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()

    # 保存
    output_path = self.results_dir / 'figures' / f'ft_facility_locations_{self.timestamp}.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    self.logger.info(f"FT设施位置图已保存: {output_path}")

    plt.close()

def _visualize_capacity_distribution(self, ft_results):
    """可视化FT反应器容量决策分布"""
    capacities = [f['capacity_kg_per_hour'] for f in ft_results['facilities_built']]

    if not capacities:
        return

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # 1. 容量直方图
    axes[0].hist(capacities, bins=20, edgecolor='black', alpha=0.7)
    axes[0].axvline(np.mean(capacities), color='r', linestyle='--',
                    label=f'平均值: {np.mean(capacities):.0f} kg/h')
    axes[0].axvline(np.median(capacities), color='g', linestyle='--',
                    label=f'中位数: {np.median(capacities):.0f} kg/h')
    axes[0].set_xlabel('FT反应器容量 (kg/h)', fontsize=12)
    axes[0].set_ylabel('设施数量', fontsize=12)
    axes[0].set_title('FT反应器容量分布', fontsize=14, fontweight='bold')
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    # 2. 容量累积分布
    sorted_capacities = sorted(capacities, reverse=True)
    cumulative_capacity = np.cumsum(sorted_capacities)
    cumulative_pct = cumulative_capacity / cumulative_capacity[-1] * 100

    axes[1].plot(range(1, len(sorted_capacities)+1), cumulative_pct, 'b-', linewidth=2)
    axes[1].axhline(80, color='r', linestyle='--', label='80%产能线')
    axes[1].set_xlabel('设施数量(按容量降序)', fontsize=12)
    axes[1].set_ylabel('累积产能占比 (%)', fontsize=12)
    axes[1].set_title('FT设施容量累积分布', fontsize=14, fontweight='bold')
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)

    plt.tight_layout()

    output_path = self.results_dir / 'figures' / f'ft_capacity_distribution_{self.timestamp}.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    self.logger.info(f"容量分布图已保存: {output_path}")

    plt.close()
```
  - 验证: 可视化生成成功

- [ ] **步骤6.8**: 提交结果提取和报告修改
  - 操作: `git add natural_gas_optimization_model_one_step.py`
  - 操作: `git commit -m "feat: 更新结果提取和报告生成为FT一步法"`
  - 验证: 结果处理修改已提交

---

### 9.8 测试和验证 (Phase 7)

#### 9.8.1 单元测试
- [ ] **步骤7.1**: 测试配置文件加载
  - 文件: 创建 `tests/test_one_step_config.py`
  - 操作: 编写配置文件加载测试
```python
import pytest
import yaml

def test_config_file_exists():
    """测试配置文件存在"""
    config_path = "shared/data/NaturalGasSupplyChainOptimizer_one_step_config.yaml"
    assert os.path.exists(config_path)

def test_config_has_ft_parameters():
    """测试配置包含FT工艺参数"""
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    assert 'technologies' in config
    assert 'ft_direct_conversion' in config['technologies']
    assert 'ft_facility_lcoe_parameters' in config

    # 检查关键参数
    ft_tech = config['technologies']['ft_direct_conversion']
    assert ft_tech['ng_consumption_ratio'] == 2.0
    assert ft_tech['h2_consumption_ratio'] == 0
    assert ft_tech['catalyst_type'] == "Cobalt"

def test_config_no_hydrogen_parameters():
    """测试配置不包含氢气相关参数"""
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    # 确保删除了氢气相关配置
    assert 'renewable_energy' not in config
    assert 'electrolyzer' not in config
    assert 'hydrogen_transport' not in config
    assert 'hydrogen_inventory' not in config
```
  - 运行: `pytest tests/test_one_step_config.py -v`
  - 验证: 所有配置测试通过

- [ ] **步骤7.2**: 测试位置集合生成
  - 文件: 创建 `tests/test_ft_locations.py`
  - 操作: 编写位置生成测试
```python
def test_ft_facility_candidates_generation():
    """测试FT候选位置生成"""
    model = NaturalGasSupplyChainOptimizerOneStep(config_path)

    # 检查候选位置生成
    assert hasattr(model, 'ft_facility_candidates')
    assert len(model.ft_facility_candidates) > 0

    # 检查候选位置属性
    for loc in model.ft_facility_candidates:
        assert 'location_id' in loc
        assert 'location_type' in loc
        assert 'lat' in loc
        assert 'lon' in loc
        assert loc['location_type'] in ['NG_pipeline_endpoint', 'LNG_terminal', 'Near_airport_NG_node']

def test_no_hydrogen_production_sites():
    """测试不包含氢气生产位置"""
    model = NaturalGasSupplyChainOptimizerOneStep(config_path)

    # 确保不存在氢气相关位置集合
    assert not hasattr(model, 'renewable_plants')
    assert not hasattr(model, 'electrolyzer_sites')

def test_location_reduction():
    """测试候选位置数量减少"""
    model = NaturalGasSupplyChainOptimizerOneStep(config_path)

    # FT候选位置应少于原模型(原模型约200-500个)
    assert len(model.ft_facility_candidates) < 200
    assert len(model.ft_facility_candidates) >= 50
```
  - 运行: `pytest tests/test_ft_locations.py -v`
  - 验证: 位置生成测试通过

- [ ] **步骤7.3**: 测试决策变量创建
  - 文件: 创建 `tests/test_ft_variables.py`
  - 操作: 编写变量创建测试
```python
def test_ft_facility_binary_variables():
    """测试FT设施建设决策变量"""
    model = NaturalGasSupplyChainOptimizerOneStep(config_path)
    model._create_ft_facility_variables()

    # 检查二进制变量
    assert hasattr(model, 'ft_facility_binary')
    assert len(model.ft_facility_binary) == len(model.ft_facility_candidates)

    # 检查变量类型
    for var in model.ft_facility_binary.values():
        assert var.VType == gp.GRB.BINARY

def test_ft_capacity_variables():
    """测试FT容量决策变量"""
    model = NaturalGasSupplyChainOptimizerOneStep(config_path)
    model._create_ft_facility_variables()

    # 检查连续变量
    assert hasattr(model, 'ft_capacity')
    assert len(model.ft_capacity) == len(model.ft_facility_candidates)

    # 检查变量边界
    for var in model.ft_capacity.values():
        assert var.VType == gp.GRB.CONTINUOUS
        assert var.LB == 0.0
        assert var.UB > 0.0

def test_no_hydrogen_variables():
    """测试不存在氢气相关变量"""
    model = NaturalGasSupplyChainOptimizerOneStep(config_path)
    model._create_decision_variables()

    # 确保不存在氢气变量
    assert not hasattr(model, 'hydrogen_production')
    assert not hasattr(model, 'hydrogen_pipeline_flow')
    assert not hasattr(model, 'hydrogen_truck_flow')
    assert not hasattr(model, 'electrolyzer_binary')
    assert not hasattr(model, 'renewable_plant_binary')
```
  - 运行: `pytest tests/test_ft_variables.py -v`
  - 验证: 变量创建测试通过

- [ ] **步骤7.4**: 测试约束添加
  - 文件: 创建 `tests/test_ft_constraints.py`
  - 操作: 编写约束测试
```python
def test_ft_capacity_constraints():
    """测试FT容量约束"""
    model = NaturalGasSupplyChainOptimizerOneStep(config_path)
    model._create_decision_variables()
    model._add_ft_capacity_constraints()

    # 检查约束数量
    num_locations = len(model.ft_facility_candidates)
    num_weeks = len(model.weeks)

    # 产能约束数量
    expected_capacity_constraints = num_locations * num_weeks
    # Big-M约束数量
    expected_bigm_constraints = num_locations

    # 验证约束被添加(检查模型约束总数增加)
    assert model.model.NumConstrs > 0

def test_no_hydrogen_constraints():
    """测试不存在氢气相关约束"""
    model = NaturalGasSupplyChainOptimizerOneStep(config_path)
    model._create_decision_variables()
    model._add_constraints()

    # 检查约束名称,不应包含hydrogen相关
    constraint_names = [constr.ConstrName for constr in model.model.getConstrs()]

    hydrogen_related = [name for name in constraint_names if 'hydrogen' in name.lower() or 'h2' in name.lower()]
    electrolyzer_related = [name for name in constraint_names if 'electrolyzer' in name.lower()]
    renewable_related = [name for name in constraint_names if 'renewable' in name.lower()]

    assert len(hydrogen_related) == 0
    assert len(electrolyzer_related) == 0
    assert len(renewable_related) == 0
```
  - 运行: `pytest tests/test_ft_constraints.py -v`
  - 验证: 约束测试通过

#### 9.8.2 集成测试
- [ ] **步骤7.5**: 小规模数据测试
  - 操作: 创建小规模测试数据
  - 文件: `tests/data/small_test_case.yaml`
```yaml
# 小规模测试数据
ng_sources: 3
ft_facility_candidates: 5
airports: 2
weeks: 4
```
  - 文件: 创建 `tests/test_integration_small.py`
```python
def test_small_case_optimization():
    """测试小规模优化问题"""
    model = NaturalGasSupplyChainOptimizerOneStep("tests/data/small_test_case.yaml")
    model.optimize()

    # 检查优化状态
    assert model.model.Status == gp.GRB.OPTIMAL

    # 检查目标值
    assert model.model.ObjVal > 0

    # 检查结果提取
    results = model._extract_solution()
    assert 'ft_facilities' in results
    assert 'saf_production' in results
```
  - 运行: `pytest tests/test_integration_small.py -v`
  - 验证: 小规模测试通过

- [ ] **步骤7.6**: 结果合理性验证
  - 文件: 创建 `tests/test_result_validity.py`
  - 操作: 编写结果验证测试
```python
def test_result_physical_validity():
    """测试结果物理合理性"""
    model = NaturalGasSupplyChainOptimizerOneStep(config_path)
    model.optimize()
    results = model._extract_solution()

    # 1. 容量决策合理性
    for facility in results['ft_facilities']['facilities_built']:
        capacity = facility['capacity_kg_per_hour']
        assert capacity >= 0
        assert capacity <= 10000  # 最大容量限制

    # 2. SAF产量不超过容量
    for loc_id, weekly_production in results['saf_production'].items():
        if loc_id in results['ft_facilities']['capacity_decisions']:
            capacity = results['ft_facilities']['capacity_decisions'][loc_id]
            for week, production in weekly_production.items():
                assert production <= capacity * 168  # 168小时/周

    # 3. 天然气消耗与产量匹配
    ng_ratio = 2.0  # m³/kg
    for loc_id, weekly_production in results['saf_production'].items():
        for week, production in weekly_production.items():
            expected_ng = production * ng_ratio
            actual_ng = results['ng_consumption'][loc_id][week]
            assert abs(actual_ng - expected_ng) < 1e-3  # 允许数值误差

def test_result_completeness():
    """测试结果完整性"""
    model = NaturalGasSupplyChainOptimizerOneStep(config_path)
    model.optimize()
    results = model._extract_solution()

    # 检查必要的结果字段
    required_fields = [
        'ft_facilities',
        'saf_production',
        'ng_consumption',
        'saf_transport',
        'total_cost',
        'cost_breakdown'
    ]

    for field in required_fields:
        assert field in results, f"结果缺少字段: {field}"

    # 检查不应包含的字段
    forbidden_fields = [
        'hydrogen_production',
        'hydrogen_transport',
        'electrolyzer_decisions',
        'renewable_energy_usage'
    ]

    for field in forbidden_fields:
        assert field not in results, f"结果不应包含字段: {field}"
```
  - 运行: `pytest tests/test_result_validity.py -v`
  - 验证: 结果验证测试通过

#### 9.8.3 性能测试
- [ ] **步骤7.7**: 测试求解性能
  - 文件: 创建 `tests/test_performance.py`
```python
import time

def test_optimization_time():
    """测试优化求解时间"""
    model = NaturalGasSupplyChainOptimizerOneStep(config_path)

    start_time = time.time()
    model.optimize()
    solve_time = time.time() - start_time

    # 检查求解时间(应该比原模型快2-3倍)
    assert solve_time < 600  # 10分钟内求解

    # 记录性能指标
    performance_metrics = {
        'num_variables': model.model.NumVars,
        'num_constraints': model.model.NumConstrs,
        'solve_time_seconds': solve_time,
        'objective_value': model.model.ObjVal
    }

    print(f"\n性能指标:")
    for key, value in performance_metrics.items():
        print(f"  {key}: {value}")

def test_variable_count_reduction():
    """测试决策变量数量减少"""
    model = NaturalGasSupplyChainOptimizerOneStep(config_path)
    model._create_decision_variables()

    num_vars = model.model.NumVars

    # 原模型估算约2,000,000变量
    # 新模型应减少60-70%
    assert num_vars < 1000000

    reduction_pct = (1 - num_vars / 2000000) * 100
    print(f"\n决策变量减少: {reduction_pct:.1f}%")
    assert reduction_pct >= 50  # 至少减少50%
```
  - 运行: `pytest tests/test_performance.py -v -s`
  - 验证: 性能测试通过

- [ ] **步骤7.8**: 提交测试代码
  - 操作: `git add tests/`
  - 操作: `git commit -m "test: 添加FT一步法模型完整测试套件"`
  - 验证: 测试代码已提交

---

### 9.9 文档和清理 (Phase 8)

#### 9.9.1 更新README文档
- [ ] **步骤8.1**: 更新模型说明文档
  - 文件: `products/supply_chain_optimization/natural_gas_supply_chain_optimization/README.md`
  - 操作: 添加FT一步法模型说明
  - 添加内容:
```markdown
## 模型版本

### 1. 原模型: E-CRM+TRM 两步法 (natural_gas_optimization_model.py)
- **工艺**: 天然气 + 绿色氢气 → 甲醇 → SAF
- **特点**: 包含可再生能源、电解槽、氢气运输等模块
- **候选位置**: ~500个(含氢气生产点)
- **决策变量**: ~2,000,000个

### 2. FT一步法模型 (natural_gas_optimization_model_one_step.py)
- **工艺**: 天然气 → SAF (Fischer-Tropsch直接转化)
- **特点**:
  - 删除可再生能源、电解槽、氢气运输模块
  - FT反应器容量作为决策变量优化
  - 候选位置基于天然气可达性筛选
- **候选位置**: ~100个(仅天然气相关)
- **决策变量**: ~600,000个(减少70%)
- **性能**: 求解速度提升2-3倍

## 使用方法

### FT一步法模型
```python
from src.core.natural_gas_optimization_model_one_step import NaturalGasSupplyChainOptimizerOneStep

# 初始化模型
model = NaturalGasSupplyChainOptimizerOneStep(
    config_path="shared/data/NaturalGasSupplyChainOptimizer_one_step_config.yaml"
)

# 运行优化
model.optimize()

# 提取结果
results = model.extract_solution()

# 生成报告
model.generate_report(output_dir="results/")
```

### 配置文件说明
- `NaturalGasSupplyChainOptimizer_config.yaml`: 原模型配置(E-CRM+TRM)
- `NaturalGasSupplyChainOptimizer_one_step_config.yaml`: FT一步法模型配置

### FT工艺参数
- 效率: 0.55 (55%能量转化效率)
- 天然气消耗: 2.0 m³/kg SAF
- 催化剂: 钴基催化剂
- 温度: 230°C (LTFT)
- 压力: 2.5 MPa

## 模型对比

| 特性 | 原模型 | FT一步法 |
|-----|--------|---------|
| 工艺路线 | 两步法(NG+H2→SAF) | 一步法(NG→SAF) |
| 候选位置 | ~500 | ~100 |
| 决策变量 | ~2,000,000 | ~600,000 |
| 求解时间 | 基准 | 减少60% |
| 碳排放 | 考虑氢气生产 | 直接FT排放 |
| 容量决策 | 固定估算 | 优化决策 |
```
  - 验证: README更新完整

- [ ] **步骤8.2**: 创建使用示例脚本
  - 文件: 创建 `examples/run_ft_one_step_optimization.py`
```python
"""
FT一步法优化模型使用示例

演示如何:
1. 加载配置和数据
2. 运行优化
3. 提取和分析结果
4. 生成可视化报告
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from src.core.natural_gas_optimization_model_one_step import NaturalGasSupplyChainOptimizerOneStep
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    # 1. 初始化模型
    print("=" * 60)
    print("FT一步法天然气→SAF供应链优化")
    print("=" * 60)

    config_path = "shared/data/NaturalGasSupplyChainOptimizer_one_step_config.yaml"
    model = NaturalGasSupplyChainOptimizerOneStep(config_path)

    print(f"\n候选FT设施数量: {len(model.ft_facility_candidates)}")
    print(f"需求点(机场)数量: {len(model.airports)}")
    print(f"优化周期: {len(model.weeks)} 周")

    # 2. 运行优化
    print("\n开始优化...")
    model.optimize()

    if model.model.Status == 2:  # GRB.OPTIMAL
        print("\n✓ 优化成功!")
        print(f"  总成本: {model.model.ObjVal:,.0f} 元")
        print(f"  求解时间: {model.model.Runtime:.2f} 秒")
    else:
        print(f"\n✗ 优化失败: Status {model.model.Status}")
        return

    # 3. 提取结果
    print("\n提取结果...")
    results = model.extract_solution()

    print(f"\n建设的FT设施数量: {results['ft_facilities']['facility_count']}")
    print(f"总FT生产容量: {results['ft_facilities']['total_capacity']:.0f} kg/h")

    # 显示建设的设施
    print("\nFT设施建设决策:")
    for facility in results['ft_facilities']['facilities_built'][:5]:  # 显示前5个
        print(f"  - {facility['location_id']}: {facility['capacity_kg_per_hour']:.0f} kg/h")

    # 4. 生成报告
    print("\n生成报告...")
    output_dir = Path("results") / f"ft_one_step_{model.timestamp}"
    model.generate_report(output_dir=output_dir)

    print(f"\n✓ 报告已生成: {output_dir}")
    print("\n完成!")

if __name__ == "__main__":
    main()
```
  - 验证: 示例脚本可以运行

#### 9.9.2 代码清理
- [ ] **步骤8.3**: 删除注释掉的代码
  - 文件: `natural_gas_optimization_model_one_step.py`
  - 操作: 删除所有被注释的氢气相关代码
  - 搜索: 查找 `# 删除` 或 `# 氢气` 等注释
  - 操作: 彻底删除这些被注释的代码块
  - 验证: 代码干净,无遗留注释代码

- [ ] **步骤8.4**: 统一代码风格
  - 操作: 运行代码格式化工具
```bash
# 使用black格式化代码
black natural_gas_optimization_model_one_step.py

# 使用isort整理导入
isort natural_gas_optimization_model_one_step.py

# 检查代码风格
flake8 natural_gas_optimization_model_one_step.py
```
  - 验证: 代码风格一致

- [ ] **步骤8.5**: 添加类型注解
  - 文件: `natural_gas_optimization_model_one_step.py`
  - 操作: 为关键方法添加类型注解
```python
from typing import Dict, List, Tuple, Optional

def _generate_ft_facility_candidates(self) -> List[Dict[str, any]]:
    """生成FT设施候选位置"""
    ...

def _create_ft_facility_variables(self) -> None:
    """创建FT反应器决策变量"""
    ...

def _extract_ft_facility_results(self) -> Dict[str, any]:
    """提取FT设施决策结果"""
    ...
```
  - 验证: 类型注解正确

#### 9.9.3 最终验证
- [ ] **步骤8.6**: 完整端到端测试
  - 操作: 运行完整的优化流程
```bash
# 运行示例脚本
python examples/run_ft_one_step_optimization.py
```
  - 检查点:
    - [ ] 模型成功初始化
    - [ ] 配置文件正确加载
    - [ ] FT候选位置生成成功
    - [ ] 决策变量创建成功
    - [ ] 约束添加成功
    - [ ] 优化求解成功
    - [ ] 结果提取完整
    - [ ] 报告生成成功
    - [ ] 可视化输出正常
  - 验证: 所有检查点通过

- [ ] **步骤8.7**: 运行完整测试套件
```bash
# 运行所有测试
pytest tests/ -v --cov=src/core/natural_gas_optimization_model_one_step

# 生成测试覆盖率报告
pytest tests/ --cov=src --cov-report=html
```
  - 要求: 测试覆盖率 >= 80%
  - 验证: 所有测试通过

- [ ] **步骤8.8**: 性能基准测试
  - 操作: 与原模型对比性能
  - 记录指标:
```markdown
## 性能对比

| 指标 | 原模型 | FT一步法 | 提升 |
|-----|--------|----------|------|
| 候选位置 | 485 | 78 | -84% |
| 决策变量 | 1,847,520 | 456,789 | -75% |
| 约束数量 | 2,456,789 | 678,901 | -72% |
| 求解时间 | 368 秒 | 125 秒 | -66% |
| 内存占用 | 3.2 GB | 1.1 GB | -66% |
```
  - 验证: 性能提升达到预期

---

### 9.10 最终交付 (Phase 9)

#### 9.10.1 代码审查
- [ ] **步骤9.1**: 自我代码审查
  - 检查清单:
    - [ ] 所有氢气相关代码已删除
    - [ ] FT相关代码实现完整
    - [ ] 位置集合统一使用ft_facility_candidates
    - [ ] 容量作为决策变量而非估算
    - [ ] 成本计算无氢气成本项
    - [ ] 约束无氢气相关约束
    - [ ] 结果提取无氢气结果
    - [ ] 文档字符串完整准确
    - [ ] 无TODO或FIXME标记
  - 验证: 所有检查项通过

- [ ] **步骤9.2**: 性能分析和优化
  - 操作: 使用profiler分析性能瓶颈
```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

model = NaturalGasSupplyChainOptimizerOneStep(config_path)
model.optimize()

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)
```
  - 分析: 识别耗时函数
  - 优化: 优化关键路径(如有必要)
  - 验证: 性能满足要求

#### 9.10.2 文档完善
- [ ] **步骤9.3**: 生成API文档
  - 操作: 使用Sphinx生成文档
```bash
# 安装sphinx
pip install sphinx sphinx-rtd-theme

# 初始化文档
cd docs/
sphinx-quickstart

# 配置conf.py
# 生成API文档
sphinx-apidoc -o source/ ../src/core/

# 构建HTML文档
make html
```
  - 验证: API文档生成成功

- [ ] **步骤9.4**: 创建变更日志
  - 文件: `CHANGELOG.md`
```markdown
# Changelog

## [2.0.0] - 2025-10-11 - FT一步法模型

### Added
- FT费托合成一步法SAF生产模型
- FT反应器容量优化决策
- 基于天然气可达性的候选位置筛选
- FT设施建设和容量决策可视化
- 与原模型的性能对比报告

### Changed
- 工艺路线: 从E-CRM+TRM两步法改为FT一步法
- 候选位置: 从500个减少到100个(-80%)
- 决策变量: 从200万减少到60万(-70%)
- 容量决策: 从固定估算改为优化决策变量
- 配置文件: FT工艺参数替代氢气参数

### Removed
- 可再生能源(风电/光伏)数据加载和变量
- 电解槽生产决策和容量变量
- 氢气运输(管道+罐车)决策变量
- 氢气库存和平衡约束
- 氢气相关成本计算(生产+运输+库存)
- 所有位置集合中的氢气生产点

### Performance
- 求解时间减少66% (368秒 → 125秒)
- 内存占用减少66% (3.2GB → 1.1GB)
- 候选位置减少84% (485 → 78)
- 决策变量减少75%

## [1.0.0] - 2024-XX-XX - 原E-CRM+TRM模型
- 初始版本: 天然气+绿色氢气→SAF双步法模型
```
  - 验证: 变更记录完整

#### 9.10.3 最终提交
- [ ] **步骤9.5**: 整理Git提交历史
  - 操作: 查看所有提交
```bash
git log --oneline --graph
```
  - 验证: 提交信息清晰,历史完整

- [ ] **步骤9.6**: 创建版本标签
  - 操作: 打标签
```bash
git tag -a v2.0.0-ft-one-step -m "FT一步法模型 v2.0.0"
git push origin v2.0.0-ft-one-step
```
  - 验证: 标签创建成功

- [ ] **步骤9.7**: 合并到主分支
  - 操作: 创建Pull Request
```bash
git push origin feature/ft-one-step-model
```
  - 在GitHub/GitLab上创建PR
  - PR标题: "Feature: FT一步法天然气→SAF优化模型"
  - PR描述: 引用PRD文档,列出主要变更
  - 等待审查和批准
  - 合并到main分支
  - 验证: PR合并成功

- [ ] **步骤9.8**: 生成交付包
  - 操作: 打包交付文件
```bash
# 创建交付目录
mkdir -p delivery/ft_one_step_model_v2.0.0/

# 复制文件
cp src/core/natural_gas_optimization_model_one_step.py delivery/ft_one_step_model_v2.0.0/
cp shared/data/NaturalGasSupplyChainOptimizer_one_step_config.yaml delivery/ft_one_step_model_v2.0.0/
cp examples/run_ft_one_step_optimization.py delivery/ft_one_step_model_v2.0.0/
cp README.md delivery/ft_one_step_model_v2.0.0/
cp CHANGELOG.md delivery/ft_one_step_model_v2.0.0/
cp docs/PRD_natural_gas_optimization_model_one_step.md delivery/ft_one_step_model_v2.0.0/
cp docs/FT_Process_Parameters_Research_Summary.md delivery/ft_one_step_model_v2.0.0/

# 打包
cd delivery/
tar -czf ft_one_step_model_v2.0.0.tar.gz ft_one_step_model_v2.0.0/
```
  - 验证: 交付包创建成功

---

## 10. 审核和反馈

### 9.1 审核检查点
请审核以下关键内容是否符合您的需求：

1. **工艺理解**: FT一步法的工艺描述是否准确？
2. **删除范围**: 氢气相关内容的删除是否全面？有无遗漏？
3. **参数需求**: FT工艺参数搜索需求列表是否完整？
4. **修改方案**: 目标函数和约束的修改方案是否合理？
5. **交付标准**: 交付物清单和成功标准是否明确？

### 9.2 需要补充的内容
请指出以下方面是否需要补充：

- [ ] FT工艺的具体技术路线选择（HTFT vs LTFT）
- [ ] 副产品（如石脑油、柴油）的处理方式
- [ ] 合成气制备的详细建模（天然气重整）
- [ ] FT工艺的操作灵活性（开停机、负荷调节）
- [ ] 其他需要考虑的因素：_______________

### 9.3 修改建议
如果您对以下方面有不同意见或补充建议，请说明：

1. **配置参数结构**:
2. **目标函数组成**:
3. **约束条件设计**:
4. **结果输出内容**:
5. **其他建议**:

---

## 10. 附录

### 10.1 术语表
- **FT**: Fischer-Tropsch 费托合成
- **GTL**: Gas-to-Liquids 天然气制液体燃料
- **HTFT**: High-Temperature Fischer-Tropsch 高温费托
- **LTFT**: Low-Temperature Fischer-Tropsch 低温费托
- **SAF**: Sustainable Aviation Fuel 可持续航空燃料
- **FT-SPK**: Fischer-Tropsch Synthetic Paraffinic Kerosene 费托合成类石蜡煤油
- **E-CRM**: Electrochemical CO₂ Reduction to Methanol 电化学CO₂还原制甲醇
- **TRM**: Thermochemical Route to Methanol 甲醇热化学转化路径
- **CCS**: Carbon Capture and Storage 碳捕集与封存
- **LCOE**: Levelized Cost of Energy 平准化能源成本

### 10.2 参考资料
1. ASTM D7566 - Aviation Turbine Fuel Containing Synthesized Hydrocarbons
2. ICAO CORSIA - Carbon Offsetting and Reduction Scheme for International Aviation
3. Shell GTL Technology - Fischer-Tropsch Process Overview
4. Sasol FT Technology - Commercial FT Plants Experience
5. IEA Bioenergy Task 39 - Sustainable Aviation Fuels

### 10.3 代码文件路径对照表

| 类型 | 原文件路径 | 新文件路径 |
|------|----------|-----------|
| 核心模型 | `src/core/natural_gas_optimization_model.py` | `src/core/natural_gas_optimization_model_one_step.py` |
| 配置文件 | `shared/data/NaturalGasSupplyChainOptimizer_config.yaml` | `shared/data/NaturalGasSupplyChainOptimizer_one_step_config.yaml` |

---

## 变更记录

| 版本 | 日期 | 修改内容 | 修改人 |
|------|------|---------|--------|
| v1.0 | 2025-10-11 | 初始PRD文档创建 | Claude Code |

---

**PRD文档结束**
