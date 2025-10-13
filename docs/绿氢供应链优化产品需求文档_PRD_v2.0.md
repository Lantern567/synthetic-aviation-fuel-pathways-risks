# 绿氢供应链优化产品需求文档（PRD）v2.0
## 聚焦两步法：绿氢+CO₂→甲醇→SAF

---

## 一、项目概述

**项目名称**：绿氢+CO₂制SAF供应链优化模型（两步法）

**工艺路线**：绿氢 + CO₂ → 甲醇 → SAF（E-CRM+MTJ航煤生产）

**核心变更**：
- **原工艺**：天然气 + 绿氢 → 甲醇 → SAF
- **新工艺**：绿氢 + CO₂ → 甲醇 → SAF

**版本**：v2.0
**创建日期**：2025-10-13
**重点**：两步法迁移，完成后再考虑一步法

---

## ⚠️ 核心实施原则：先迁移，后修改

**重要提醒**：本项目采用**分阶段渐进式**的开发方式，严格遵循以下原则：

### 实施策略
1. **第一阶段（Phase 1-2）：完整迁移**
   - 将所有文件原样复制到新目录
   - 仅修改import路径，保证代码能够运行
   - **不修改任何业务逻辑代码**
   - **不删除任何天然气相关代码**
   - 目标：建立一个可运行的副本

2. **第二阶段（Phase 3-4）：新增模块**
   - 开发CO₂捕获计算模块
   - 开发碳排放计算模块
   - 这些是新增功能，不影响原有代码

3. **第三阶段（Phase 5）：逐步重构**
   - 在确保迁移成功的基础上
   - 逐步删除天然气相关代码
   - 逐步添加CO₂相关代码
   - 每次修改后测试验证

4. **第四阶段（Phase 6-7）：测试与文档**
   - 集成测试
   - 完善文档

### 为什么要"先迁移后修改"？
- ✅ **降低风险**：迁移和修改分离，问题更容易定位
- ✅ **便于回滚**：如果修改出错，可以回退到迁移成功的版本
- ✅ **逐步验证**：每个阶段都有明确的验收标准
- ✅ **团队协作**：不同阶段可以由不同人员负责

---

## 二、目录结构与文件迁移计划

### 2.1 新产品目录结构

```
products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/
├── src/                              # 源代码目录
│   ├── core/                         # 核心优化模型
│   │   ├── __init__.py              # [迁移] 修改导入路径
│   │   └── green_hydrogen_optimization_model.py  # [迁移] 从natural_gas_optimization_model.py重命名
│   │
│   ├── co2/                          # [新建] CO₂捕获与处理模块
│   │   ├── __init__.py              # [新建]
│   │   ├── co2_capture_calculator.py  # [新建] CO₂捕获量计算
│   │   └── co2_emission_calculator.py # [新建] 碳排放自定义计算
│   │
│   ├── hydrogen/                     # [迁移] 氢气处理模块（完全复用）
│   │   ├── __init__.py
│   │   ├── hydrogen_clustering_optimizer.py
│   │   ├── hydrogen_pipeline_distance_calculator.py
│   │   └── hydrogen_transport_visualizer.py
│   │
│   ├── routing/                      # [迁移] 路径规划模块（完全复用）
│   │   ├── __init__.py
│   │   ├── graphhopper_routing_engine.py
│   │   ├── osm_routing_engine.py
│   │   └── pipeline_coordinate_integrator.py
│   │
│   ├── cache/                        # [迁移] 缓存模块（完全复用）
│   │   ├── __init__.py
│   │   ├── cache_management_utility.py
│   │   ├── data_cache_manager.py
│   │   ├── pipeline_route_cache_manager.py
│   │   ├── pipeline_route_types.py
│   │   └── unified_cache_configuration.py
│   │
│   ├── visualization/                # [迁移] 可视化模块（完全复用）
│   │   ├── __init__.py
│   │   ├── transport_route_visualizer.py
│   │   ├── method_comparison_visualizer.py
│   │   └── method_comparison_visualizer_en.py
│   │
│   ├── utils/                        # [迁移] 工具模块（完全复用）
│   │   ├── __init__.py
│   │   └── direct_capacity_preprocessor.py
│   │
│   └── sensitivity_analysis/         # [迁移] 敏感性分析（完全复用）
│       ├── __init__.py
│       ├── fast_sensitivity_analyzer.py
│       ├── extract_sensitivity_data_corrected.py
│       └── sensitivity_visualization_tradeoff.py
│
├── data/                             # [新建] 数据文件
│   └── co2_capture_sources.csv      # [新建] CO₂捕获源数据（程序生成）
│
├── results/                          # [新建] 结果输出
│   ├── tables/
│   ├── figures/
│   ├── reports/
│   └── logs/
│
├── tests/                            # [迁移] 单元测试（需修改）
│   └── test_phase7_methods.py       # 需要适配新模型
│
├── README.md                         # [新建] 项目说明
└── requirements.txt                  # [新建] 依赖列表
```

### 2.2 不迁移的文件

- ❌ `run_optimization.py` - 不迁移（无实际用途）
- ❌ `run_cluster_viz.bat` - 不迁移
- ❌ `test_ft_one_step.py` - 一步法相关，暂不迁移
- ❌ `extract_sensitivity_data_fixed.py` - 旧版本，不迁移
- ❌ `natural_gas_optimization_model_one_step.py` - 一步法，暂不迁移
- ❌ `visualization/*_one_step.py` - 一步法可视化，暂不迁移
- ❌ `data/` 下具体数据文件
- ❌ `results/` 下历史结果
- ❌ `logs/` 下历史日志
- ❌ `cache/` 下缓存文件
- ❌ `clustering_results.json`

---

## 三、配置文件修改计划

### 3.1 创建新配置文件

**原文件**：`shared/data/NaturalGasSupplyChainOptimizer_config.yaml`
**新文件**：`shared/data/GreenHydrogenSupplyChainOptimizer_config.yaml`

### 3.2 配置文件修改清单

#### 3.2.1 文件头部元数据

```yaml
# 修改：
# 原：NaturalGasSupplyChainOptimizer 配置文件
# 新：GreenHydrogenSupplyChainOptimizer 配置文件

# 更新描述：
description: |
  绿氢供应链优化器综合参数配置文件
  支持绿氢+CO₂制SAF（两步法：甲醇路径）
  Green Hydrogen Supply Chain Optimizer Configuration

# 更新版本信息
metadata:
  version: 2.0.0
  last_updated: '2025-10-13'
  process_type: 'two_step_methanol_mtj'
```

#### 3.2.2 需要完全删除的参数段

```yaml
# ❌ 删除整个段落：
supply_capacity:
  natural_gas_supply:        # 删除整个天然气供应参数
    default_daily_volume_m3
    default_max_flow_m3_per_hour
    default_reduced_flow_m3_per_hour
    airport_max_flow_m3_per_hour

  lng_terminal_capacity:     # 删除LNG接收站容量（如果不用于CO₂捕获）
    default_capacity_mcm_per_year

# ❌ 删除原料价格中的天然气：
cost_parameters:
  raw_materials:
    natural_gas_price_yuan_per_m3: 4.2  # 删除

# ❌ 删除技术参数中的天然气消耗比：
technologies:
  pipeline_direct_conversion:
    ng_consumption_ratio: 0.8  # 删除
  airport_integrated_conversion:
    ng_consumption_ratio: 0.8  # 删除
  lng_terminal_conversion:
    ng_consumption_ratio: 0.8  # 删除
  lng_to_hplant_conversion:
    ng_consumption_ratio: 0.8  # 删除

# ❌ 删除碳排放参数中的天然气相关：
carbon_emission_parameters:
  raw_materials:
    ng_extraction_intensity: 0.25       # 删除
    ng_pipeline_transport: 0.01         # 删除
  production_process:
    ng_process_emission: 0.8            # 删除
    ng_to_methanol_rate: 1.2            # 删除
  transportation:
    ng_truck_intensity: 0.1             # 删除

# ❌ 删除统一成本中的天然气：
unified_costs:
  production:
    natural_gas_processing_cost_yuan_per_m3: 0.1  # 删除
  raw_materials:
    natural_gas_base_price_yuan_per_m3: 4.2  # 删除

# ❌ 删除运输约束中的天然气罐车：
transport_constraints:
  ng_truck_transport:  # 删除整个段落
    max_trucks_per_day: 20
    truck_capacity_m3: 1200

# ❌ 删除数据路径中的天然气管道相关：
data_paths:
  gis_data:
    ng_pipelines_original: ...          # 删除
    ng_pipelines_preprocessed: ...      # 删除
    ng_pipelines_integrated: ...        # 删除
```

#### 3.2.3 需要新增的参数段

```yaml
# =============== 新增：CO₂捕获与供应参数 ===============
co2_parameters:
  # CO₂捕获源参数
  capture_sources:
    coal_power_capture_rate: 0.85          # 燃煤电厂捕获率
    lng_power_capture_rate: 0.90           # LNG发电捕获率
    oil_refinery_capture_rate: 0.80        # 石油精炼捕获率

    # 排放因子 (kgCO₂/单位)
    coal_power_emission_factor: 0.95       # tCO₂/MWh
    lng_power_emission_factor: 0.42        # tCO₂/MWh
    oil_refinery_emission_factor: 0.6      # tCO₂/ton原油

    # 容量因子
    coal_power_capacity_factor: 0.70       # 燃煤电厂年运行率
    lng_power_capacity_factor: 0.75        # LNG电厂年运行率
    oil_refinery_capacity_factor: 0.85     # 炼油厂年运行率

  # CO₂捕获成本
  capture_costs:
    coal_power_yuan_per_ton: 150           # 燃煤电厂捕获成本
    lng_power_yuan_per_ton: 180            # LNG电厂捕获成本
    oil_refinery_yuan_per_ton: 120         # 炼油厂捕获成本

  # CO₂运输参数
  transport:
    # 管道运输成本函数（分段线性，模仿氢气管道成本结构）
    pipeline_transport_cost_function:
      function_type: piecewise_linear      # 函数类型：分段线性
      unit: yuan_per_ton_co2_per_100km     # 成本单位：元/(吨CO₂·百公里)
      description: CO₂管道运输成本曲线（包含建设成本摊销）

      # 成本数据点 [距离(km), 成本(元/吨/100km)]
      data_points:
      - [25, 12.0]     # 25km: 12元/吨/100km
      - [50, 8.5]      # 50km: 8.5元/吨/100km
      - [100, 5.0]     # 100km: 5元/吨/100km
      - [200, 3.0]     # 200km: 3元/吨/100km
      - [300, 2.2]     # 300km: 2.2元/吨/100km
      - [400, 1.8]     # 400km: 1.8元/吨/100km
      - [500, 1.5]     # 500km: 1.5元/吨/100km

      notes: |
        成本函数已包含以下所有费用（与氢气管道成本处理方式一致）：
        - 管道建设投资摊销（Pipeline construction amortization）
        - 压缩机站投资和运营（Compressor station CAPEX & OPEX）
        - 管道维护和检测（Pipeline maintenance & inspection）
        - 能耗成本（Energy cost for compression）
        - 人工和管理成本（Labor & management）

        ⚠️ 重要说明：
        - 管道建设成本（pipeline_capex_yuan_per_km）已摊销到分段线性成本函数中
        - 目标函数中不需要单独添加管道建设成本项
        - 当SAF工厂位置 = CO₂捕获源位置时，运输距离 = 0，运输成本 = 0（本地供应）

        单位转换说明：
        - 配置单位：元/(吨CO₂·百公里)
        - 计算公式：总成本 = 单位成本 × (运输距离km ÷ 100)
        - 最终单位：元/吨CO₂

    # 罐车运输成本
    truck_cost_yuan_per_ton_per_100km: 50     # 罐车运输成本（元/吨/100km）
    liquefaction_cost_yuan_per_ton: 80        # CO₂液化成本（罐车运输需要）

    # 运输容量限制
    max_pipeline_capacity_ton_per_day: 5000   # 管道日最大容量
    max_truck_capacity_ton_per_day: 500       # 罐车日最大容量

  # CO₂储存参数
  storage:
    storage_cost_yuan_per_ton_per_day: 0.5    # 储存成本
    max_storage_capacity_ton: 50000           # 最大储存容量
    storage_density_ton_per_m3: 0.8           # 储存密度(液态CO₂)

# =============== 新增：绿氢供应参数 ===============
green_hydrogen_supply:
  # 生产成本
  production_cost_yuan_per_kg: 25          # 绿氢生产成本(元/kg)
  production_energy_kwh_per_kg: 50         # 制氢能耗(kWh/kg H₂)
  electrolyzer_efficiency: 0.70            # 电解槽效率

  # 运输成本
  transport:
    pipeline_cost_yuan_per_kg_per_100km: 0.5   # 管道运输
    truck_cost_yuan_per_kg_per_100km: 2.0      # 罐车运输
    pipeline_capex_yuan_per_km: 5000000        # 氢气管道建设(已有)

  # 储存参数
  storage:
    storage_cost_yuan_per_kg_per_day: 1.0      # 氢气储存成本
    compression_cost_yuan_per_kg: 2.0          # 压缩成本
    liquefaction_cost_yuan_per_kg: 5.0         # 液化成本(如需要)

# =============== 修改：技术路线参数（两步法）===============
technologies:
  # 删除原有的4种技术路线，新增1种两步法技术
  methanol_mtj_two_step:
    name: "两步法：绿氢+CO₂→甲醇→SAF (E-CRM+MTJ)"
    technology_type: "Methanol-MTJ-TwoStep"
    process_description: "电化学CO₂还原制甲醇+甲醇转航煤"

    # 原料消耗比例
    h2_consumption_ratio: 0.20             # kg H₂/kg SAF
    co2_consumption_ratio: 3.5             # kg CO₂/kg SAF
    methanol_intermediate_ratio: 1.3       # kg甲醇/kg SAF

    # 工艺参数
    efficiency: 0.70                       # 总体转换效率
    e_crm_efficiency: 0.75                 # 甲醇合成效率
    mtj_efficiency: 0.85                   # MTJ转化效率

    # 能耗参数
    energy_consumption_kwh_per_kg_saf: 15  # 工艺总能耗(kWh/kg SAF)
    e_crm_energy_kwh_per_kg_methanol: 8    # 甲醇合成能耗
    mtj_energy_kwh_per_kg_saf: 5           # MTJ转化能耗

    # 适用位置
    suitable_locations:
    - solar_plant
    - wind_farm
    - airport

    # 运输需求
    hydrogen_transport_required: true      # 需要氢气运输
    co2_transport_required: true           # 需要CO₂运输
    methanol_intermediate_storage: true    # 需要甲醇中间存储

# =============== 修改：碳排放参数 ===============
carbon_emission_parameters:
  benchmarks:
    traditional_jet_fuel: 89               # 保留
    saf_energy_content: 43.15              # 保留
    corsia_limit: 30                       # 保留

  # 原材料排放
  raw_materials:
    green_h2_intensity: 0.5                # 绿氢碳强度(kgCO₂e/kgH₂) - 仅生命周期
    co2_capture_process_intensity: 0.1     # CO₂捕获过程排放(kgCO₂e/kgCO₂)
    renewable_electricity: 0.02            # 可再生电力碳强度(保留)

  # 生产过程排放
  production_process:
    e_crm_synthesis_emission: 0.3          # 甲醇合成工艺排放(kgCO₂e/kg甲醇)
    mtj_conversion_emission: 0.4           # MTJ转化排放(kgCO₂e/kgSAF)
    total_process_emission: 1.2            # 总工艺排放(kgCO₂e/kgSAF)

    # CO₂利用负排放
    co2_utilization_credit: -1.0           # CO₂固定在产品中的负排放系数

  # 运输排放
  transportation:
    h2_pipeline_intensity: 0.005           # 氢气管道(kgCO₂e/kg/100km)
    h2_truck_intensity: 0.15               # 氢气罐车(kgCO₂e/kg/100km)
    co2_pipeline_intensity: 0.003          # CO₂管道(kgCO₂e/kg/100km)
    co2_truck_intensity: 0.08              # CO₂罐车(kgCO₂e/kg/100km)
    saf_truck_intensity: 0.12              # SAF运输(kgCO₂e/kg/100km)

  # 储存和处理排放
  storage_handling:
    h2_storage_energy: 0.5                 # 氢气储存能耗
    co2_storage_energy: 0.3                # CO₂储存能耗
    methanol_storage_energy: 0.1           # 甲醇储存能耗
    saf_storage_energy: 0.05               # SAF储存能耗

# =============== 修改：成本参数 ===============
cost_parameters:
  # 原料价格（删除天然气，保留氢气，新增CO₂）
  raw_materials:
    hydrogen_market_price_yuan_per_kg: 30  # 保留
    co2_capture_price_yuan_per_ton: 150    # 新增：CO₂捕获价格(平均值)
    renewable_electricity_cost_yuan_per_mwh: 500  # 保留

  # 电解制氢参数（保留）
  electrolysis:
    electrolysis_efficiency: 0.8
    electrolysis_power_consumption: 45

  # 缺货惩罚（保留）
  shortage_penalty_yuan_per_kg: 2500

# =============== 修改：数据路径 ===============
data_paths:
  gis_data:
    # 删除天然气管道相关路径
    # 保留可再生能源数据
    renewable_plants_cache_prefix: temp_renewable

    # 新增CO₂捕获源数据路径
    coal_power_plants: products/gis_energy_mapping/gis_data_scraper/scraped_gis_data/coal_power_plants.csv
    lng_terminals: products/gis_energy_mapping/gis_data_scraper/scraped_gis_data/lng_terminals.csv
    oil_refineries: products/gis_energy_mapping/gis_data_scraper/scraped_gis_data/oil_refineries.csv  # 如存在

  output_paths:
    results_base_dir: products/supply_chain_optimization/green_hydrogen_supply_chain_optimization/results
    file_templates:
      optimization_summary: optimization_summary_{timestamp}.csv
      facility_decisions: facility_decisions_{timestamp}.csv
      co2_supply_plan: co2_supply_plan_{timestamp}.csv        # 新增
      hydrogen_supply_plan: hydrogen_supply_plan_{timestamp}.csv  # 新增
      saf_production_plan: saf_production_plan_{timestamp}.csv    # 新增
      carbon_emission_report: carbon_emission_report_{timestamp}.csv  # 新增
```

---

## 四、核心代码修改计划

### 4.1 主优化模型文件修改

**文件**：`src/core/green_hydrogen_optimization_model.py`
**原文件**：`src/core/natural_gas_optimization_model.py`

#### 4.1.1 类名和文件路径修改

```python
# ===== 修改1：类名 =====
# 原：class NaturalGasSupplyChainOptimizer:
# 新：class GreenHydrogenSupplyChainOptimizer:

# ===== 修改2：日志目录路径 =====
# 原：
_log_dir = os.path.join(_base_dir, "products", "supply_chain_optimization",
                       "natural_gas_supply_chain_optimization", "results", "logs")
mount_file_logging(_log_dir, filename_prefix="ng_supply_chain")

# 新：
_log_dir = os.path.join(_base_dir, "products", "supply_chain_optimization",
                       "green_hydrogen_supply_chain_optimization", "results", "logs")
mount_file_logging(_log_dir, filename_prefix="green_h2_supply_chain")

# ===== 修改3：配置文件路径 =====
# 原：
config_path = os.path.join(project_root, "shared", "data",
                          "NaturalGasSupplyChainOptimizer_config.yaml")
# 新：
config_path = os.path.join(project_root, "shared", "data",
                          "GreenHydrogenSupplyChainOptimizer_config.yaml")
```

#### 4.1.2 数据加载方法修改

```python
# ===== 删除：天然气管道加载方法 =====
# ❌ 删除整个方法：def _load_ng_pipelines(self, ...)

# ===== 删除：LNG接收站加载方法（如果不用于CO₂捕获）=====
# ❌ 删除整个方法：def _load_lng_terminals(self, ...)

# ===== 新增：CO₂捕获源加载方法 =====
def _load_co2_capture_sources(self) -> pd.DataFrame:
    """
    从GIS数据加载CO₂捕获源并计算捕获量

    Returns:
        DataFrame包含列：
        - location_name: 设施名称
        - latitude, longitude: 坐标
        - facility_type: 设施类型(coal_power/lng_power/oil_refinery)
        - co2_capture_capacity_ton_per_week: 每周CO₂捕获量(吨)
        - week: 周数
        - capture_cost_yuan_per_ton: 捕获成本(元/吨)
    """
    from ..co2.co2_capture_calculator import CO2CaptureCalculator

    logger.info("开始加载CO₂捕获源数据...")

    # 初始化CO₂捕获计算器
    co2_calculator = CO2CaptureCalculator(self.config)

    # 获取GIS数据目录
    gis_data_dir = self._get_data_path('gis_data.coal_power_plants')
    gis_data_dir = os.path.dirname(gis_data_dir)

    # 计算CO₂捕获量
    time_horizon_weeks = self.config['basic_parameters']['time_horizon_weeks']
    co2_sources = co2_calculator.calculate_from_gis_data(
        gis_data_dir,
        time_horizon_weeks
    )

    logger.info(f"成功加载 {len(co2_sources)} 条CO₂捕获源记录")

    return co2_sources

# ===== 修改：load_data方法 =====
def load_data(...):
    """主数据加载方法"""

    # ❌ 删除：天然气管道加载
    # self.ng_pipelines = self._load_ng_pipelines(...)

    # ❌ 删除：LNG接收站加载（如不需要）
    # self.lng_terminals = self._load_lng_terminals(...)

    # ✅ 保留：可再生能源发电站加载
    self.renewable_plants = renewable_plants_df

    # ✅ 保留：机场需求加载
    self.airports = self._load_airports(...)

    # ✅ 新增：CO₂捕获源加载
    self.co2_sources = self._load_co2_capture_sources()

    # ✅ 保留：距离计算等其他逻辑
    ...
```

#### 4.1.3 决策变量修改

**核心变更说明**：
1. **CO₂运输决策变量**：模仿氢气运输模式，支持管道和罐车两种运输方式
2. **建厂决策变量调整**：原来以天然气生产地为SAF建厂位置，现改为以CO₂捕获源为SAF建厂位置

```python
# ===== 在 _define_decision_variables() 方法中修改 =====

# ❌ 删除：天然气供应变量
# self.ng_supply = model.addVars(
#     [(i, j, t) for i in ng_sources for j in saf_locations for t in hours],
#     vtype=GRB.CONTINUOUS, lb=0, name="ng_supply"
# )

# ❌ 删除：LNG供应变量（如果有）
# self.lng_supply = model.addVars(...)

# ===== 氢气运输决策变量（保留，作为CO₂运输的参考模板）=====
# ✅ 保留：氢气管道运输变量
self.h2_pipeline_transport = model.addVars(
    [(i, j, t) for i in h2_sources for j in saf_locations for t in hours],
    vtype=GRB.CONTINUOUS, lb=0, name="h2_pipeline_transport"
)

# ✅ 保留：氢气罐车运输变量
self.h2_truck_transport = model.addVars(
    [(i, j, t) for i in h2_sources for j in saf_locations for t in hours],
    vtype=GRB.CONTINUOUS, lb=0, name="h2_truck_transport"
)

# ✅ 保留：氢气总供应量（管道+罐车）
self.h2_supply = model.addVars(
    [(i, j, t) for i in h2_sources for j in saf_locations for t in hours],
    vtype=GRB.CONTINUOUS, lb=0, name="h2_supply"
)

# ===== CO₂运输决策变量（新增，模仿氢气运输模式）=====
# ✅ 新增：CO₂管道运输变量
self.co2_pipeline_transport = model.addVars(
    [(c, j, t) for c in co2_sources for j in saf_locations for t in hours],
    vtype=GRB.CONTINUOUS, lb=0, name="co2_pipeline_transport"
)

# ✅ 新增：CO₂罐车运输变量
self.co2_truck_transport = model.addVars(
    [(c, j, t) for c in co2_sources for j in saf_locations for t in hours],
    vtype=GRB.CONTINUOUS, lb=0, name="co2_truck_transport"
)

# ===== 建厂决策变量（关键调整）=====
# ⚠️ 重要变更：原来以天然气管道位置为建厂候选点，现改为以CO₂捕获源为建厂候选点
#
# 原逻辑：
#   - 天然气管道沿线 → 可作为SAF工厂选址
#   - 决策：是否在该管道位置建设SAF工厂
#
# 新逻辑：
#   - CO₂捕获源（电厂、炼厂）附近 → 可作为SAF工厂选址
#   - 决策：是否在该CO₂捕获源位置建设SAF工厂
#   - 理由：CO₂运输成本高，优先靠近CO₂源建厂

# ✅ 修改：SAF工厂建设决策变量（位置由NG管道改为CO₂捕获源）
self.facility_build = model.addVars(
    [(c, tech) for c in co2_sources for tech in ['methanol_mtj_two_step']],
    vtype=GRB.BINARY, name="facility_build"
)
# 说明：facility_build[c, tech] = 1 表示在CO₂捕获源c的位置建设tech技术的SAF工厂

# ===== 生产相关变量 =====
# ✅ 新增：甲醇中间体生产变量
self.methanol_production = model.addVars(
    [(j, t) for j in saf_locations for t in hours],
    vtype=GRB.CONTINUOUS, lb=0, name="methanol_production"
)

# ✅ 新增：甲醇库存变量
self.methanol_inventory = model.addVars(
    [(j, t) for j in saf_locations for t in hours],
    vtype=GRB.CONTINUOUS, lb=0, name="methanol_inventory"
)

# ✅ 新增：CO₂库存变量（用于时间尺度匹配）
self.co2_inventory = model.addVars(
    [(j, t) for j in saf_locations for t in hours],
    vtype=GRB.CONTINUOUS, lb=0, name="co2_inventory"
)
# 说明：CO₂库存用于桥接周级供应和小时级生产需求

# ✅ 修改：SAF生产变量（仅两步法技术，位置与CO₂源关联）
self.saf_production = model.addVars(
    [(j, tech, t) for j in saf_locations for tech in ['methanol_mtj_two_step'] for t in hours],
    vtype=GRB.CONTINUOUS, lb=0, name="saf_production"
)

# ===== 运输和库存变量 =====
# ✅ 保留：SAF运输变量
self.saf_transport = model.addVars(
    [(j, k, t) for j in saf_locations for k in airports for t in hours],
    vtype=GRB.CONTINUOUS, lb=0, name="saf_transport"
)

# ✅ 保留：SAF库存变量
self.saf_inventory = model.addVars(
    [(k, t) for k in airports for t in hours],
    vtype=GRB.CONTINUOUS, lb=0, name="saf_inventory"
)

# ===== 运输约束辅助变量 =====
# ✅ 新增：CO₂管道建设决策变量（0-1变量）
self.co2_pipeline_built = model.addVars(
    [(c, j) for c in co2_sources for j in saf_locations],
    vtype=GRB.BINARY, name="co2_pipeline_built"
)
# 说明：如果co2_pipeline_built[c,j] = 1，则可以使用管道运输CO₂

# ✅ 保留：氢气管道建设决策变量
self.h2_pipeline_built = model.addVars(
    [(i, j) for i in h2_sources for j in saf_locations],
    vtype=GRB.BINARY, name="h2_pipeline_built"
)
```

**关键设计说明**：

1. **CO₂运输模式**：
   - 完全模仿氢气运输的双模式设计（管道+罐车）
   - 管道运输：大规模、长期、低单位成本，但需要前期资本投入
   - 罐车运输：灵活、短距离、适合小规模，无需管道建设
   - 模型自动优化选择最经济的运输组合

2. **建厂位置决策逻辑变更**：
   ```
   原逻辑：天然气管道 → SAF工厂
            ↓ (天然气供应)
            SAF生产 ← 氢气运输 (来自可再生能源站)

   新逻辑：CO₂捕获源 → SAF工厂
            ↓ (CO₂本地供应，运输距离=0)
            SAF生产 ← 氢气运输 (来自可再生能源站)
                    ← CO₂运输 (如需额外CO₂)
   ```
   - 优先在CO₂捕获源附近建厂，减少CO₂运输成本
   - 氢气通过管道或罐车从可再生能源站运输过来
   - 生产的SAF再运输到机场

3. **决策变量索引说明**：
   - `c` : CO₂捕获源索引 (coal_power_plant_001, gas_power_plant_002, oil_refinery_003, ...)
   - `i` : 氢气生产源索引 (renewable_plant_001, ...)
   - `j` : SAF生产地/CO₂捕获源位置 (与c可以是同一位置)
   - `k` : 机场索引
   - `t` : 时间索引（小时）
```

#### 4.1.4 约束条件修改

```python
# ===== 在 _add_constraints() 方法中修改 =====

# ❌ 删除：天然气平衡约束
# for i in ng_sources:
#     for t in hours:
#         model.addConstr(
#             gp.quicksum(ng_supply[i,j,t] for j in saf_locations) <= ng_capacity[i,t]
#         )

# ✅ 新增：CO₂供应平衡约束
for c in co2_sources:
    for week in weeks:
        week_start_hour = week * 168
        week_end_hour = (week + 1) * 168
        weekly_co2_supply = gp.quicksum(
            co2_pipeline_transport[c, j, t] + co2_truck_transport[c, j, t]
            for j in saf_locations
            for t in range(week_start_hour, week_end_hour)
        )
        model.addConstr(
            weekly_co2_supply <= co2_capture_capacity[c, week],
            name=f"co2_supply_limit_{c}_{week}"
        )

# ✅ 新增：CO₂管道建设Big-M约束（与氢气管道逻辑完全一致）
for c in co2_sources:
    for j in saf_locations:
        for t in hours:
            # Big-M约束：只有建设了管道，才能使用管道运输
            model.addConstr(
                co2_pipeline_transport[c, j, t] <= Big_M * co2_pipeline_built[c, j],
                name=f"co2_pipeline_bigm_{c}_{j}_{t}"
            )
# 说明：co2_pipeline_built[c,j] = 1时允许管道运输，= 0时强制管道运输量为0

# ✅ 新增：CO₂管道和罐车运输互斥约束
for c in co2_sources:
    for j in saf_locations:
        for t in hours:
            # 引入辅助二元变量：use_pipeline[c,j,t] = 1表示该时刻使用管道
            # 约束1：如果使用管道，则罐车运输量必须为0
            model.addConstr(
                co2_truck_transport[c, j, t] <= Big_M * (1 - co2_pipeline_built[c, j]),
                name=f"co2_exclusive_truck_{c}_{j}_{t}"
            )
            # 说明：co2_pipeline_built[c,j] = 1时，罐车运输被强制为0
            #      co2_pipeline_built[c,j] = 0时，罐车运输允许（管道运输已被上面的Big-M约束强制为0）
# 注：这里使用co2_pipeline_built作为互斥控制变量，简化了模型（不需要引入额外的二元变量）

# ✅ 新增：氢气-甲醇-SAF工艺约束（两步法）
for j in saf_locations:
    for t in hours:
        tech = 'methanol_mtj_two_step'

        # 第一步：氢气+CO₂ → 甲醇
        h2_required_for_methanol = (
            methanol_production[j, t] *
            tech_params['h2_to_methanol_ratio']  # 例如：0.15 kg H₂/kg甲醇
        )
        co2_required_for_methanol = (
            methanol_production[j, t] *
            tech_params['co2_to_methanol_ratio']  # 例如：2.8 kg CO₂/kg甲醇
        )

        model.addConstr(
            gp.quicksum(h2_supply[i, j, t] for i in h2_sources) >= h2_required_for_methanol,
            name=f"h2_methanol_{j}_{t}"
        )

        model.addConstr(
            gp.quicksum(co2_pipeline_transport[c, j, t] + co2_truck_transport[c, j, t]
                        for c in co2_sources) >= co2_required_for_methanol,
            name=f"co2_methanol_{j}_{t}"
        )

        # 第二步：甲醇 → SAF
        methanol_required_for_saf = (
            saf_production[j, tech, t] *
            tech_params['methanol_intermediate_ratio']  # 例如：1.3 kg甲醇/kg SAF
        )

        model.addConstr(
            methanol_inventory[j, t] >= methanol_required_for_saf,
            name=f"methanol_saf_{j}_{t}"
        )

# ✅ 新增：甲醇库存平衡约束
for j in saf_locations:
    for t in hours:
        if t == 0:
            model.addConstr(
                methanol_inventory[j, t] == methanol_production[j, t],
                name=f"methanol_inv_init_{j}"
            )
        else:
            tech = 'methanol_mtj_two_step'
            methanol_consumed = (
                saf_production[j, tech, t] *
                tech_params['methanol_intermediate_ratio']
            )
            model.addConstr(
                methanol_inventory[j, t] == (
                    methanol_inventory[j, t-1] +
                    methanol_production[j, t] -
                    methanol_consumed
                ),
                name=f"methanol_inv_{j}_{t}"
            )

# ✅ 新增：CO₂库存平衡约束（时间尺度匹配：周级供应 → 小时级生产）
for j in saf_locations:
    for t in hours:
        if t == 0:
            # 初始库存 = 第一小时的CO₂进货量
            model.addConstr(
                co2_inventory[j, t] == gp.quicksum(
                    co2_pipeline_transport[c, j, t] + co2_truck_transport[c, j, t]
                    for c in co2_sources
                ),
                name=f"co2_inv_init_{j}"
            )
        else:
            # 库存平衡：本小时库存 = 上小时库存 + 本小时进货 - 本小时消耗
            co2_consumed = (
                methanol_production[j, t] *
                tech_params['co2_to_methanol_ratio']  # CO₂消耗比例（kg CO₂/kg 甲醇）
            )
            model.addConstr(
                co2_inventory[j, t] == (
                    co2_inventory[j, t-1] +
                    gp.quicksum(
                        co2_pipeline_transport[c, j, t] + co2_truck_transport[c, j, t]
                        for c in co2_sources
                    ) -
                    co2_consumed
                ),
                name=f"co2_inv_{j}_{t}"
            )

# 说明：CO₂库存约束的作用
# 1. 时间尺度匹配：CO₂捕获源提供周级供应数据，但生产决策是小时级的
# 2. 库存桥接：通过库存变量，允许CO₂在一周内灵活调配
# 3. 约束逻辑：
#    - 周初：CO₂捕获量进入库存
#    - 周中：每小时从库存中提取CO₂用于甲醇生产
#    - 周末：理论上库存应接近0（优化器会自动调整以避免过度库存成本）

# ❌ 删除：原有的NG消耗约束
# model.addConstr(ng_consumption == ...)

# ✅ 保留：其他约束（需求满足、运输、库存等）
...
```

#### 4.1.5 目标函数修改

```python
# ===== 在 _define_objective() 方法中修改 =====

# ❌ 删除：天然气成本
# ng_cost = gp.quicksum(
#     ng_supply[i,j,t] * ng_price[i]
#     for i in ng_sources for j in saf_locations for t in hours
# )

# ❌ 删除：LNG成本
# lng_cost = ...

# ✅ 保留：氢气成本（已存在）
h2_cost = gp.quicksum(
    h2_supply[i,j,t] * h2_price
    for i in h2_sources for j in saf_locations for t in hours
)

# ✅ 新增：CO₂捕获成本
co2_capture_cost = gp.quicksum(
    (co2_pipeline_transport[c,j,t] + co2_truck_transport[c,j,t]) * co2_capture_price[c]
    for c in co2_sources for j in saf_locations for t in hours
)

# ✅ 新增：CO₂运输成本
# 管道运输成本（使用分段线性函数计算）
co2_pipeline_cost = gp.quicksum(
    co2_pipeline_transport[c,j,t] * co2_pipeline_unit_cost[c,j]
    for c in co2_sources for j in saf_locations for t in hours
)
# 罐车运输成本
co2_truck_cost = gp.quicksum(
    co2_truck_transport[c,j,t] * co2_truck_unit_cost[c,j]
    for c in co2_sources for j in saf_locations for t in hours
)
co2_transport_cost = co2_pipeline_cost + co2_truck_cost

# ⚠️ 重要说明：CO₂运输成本计算逻辑
# 1. co2_pipeline_unit_cost[c,j] 是基于分段线性函数计算的单位成本（元/吨）
#    - 函数输入：CO₂捕获源c到SAF工厂j的距离（km）
#    - 函数输出：单位运输成本（元/吨）
#    - 距离越长，单位成本越低（规模经济）
#
# 2. 特殊情况：本地供应（c和j是同一位置）
#    - 当SAF工厂位置 = CO₂捕获源位置时
#    - 运输距离 = 0 km
#    - co2_pipeline_unit_cost[c,j] = 0
#    - 本地供应无运输成本
#
# 3. 管道建设成本处理（与氢气管道逻辑完全一致）
#    - ❌ 不需要单独添加管道建设成本项到目标函数
#    - ✅ 建设成本已摊销到分段线性函数中
#    - ✅ co2_pipeline_unit_cost[c,j]已包含所有成本：
#      * 管道建设投资摊销
#      * 压缩机站投资和运营
#      * 管道维护和检测
#      * 能耗成本（压缩机电力）
#      * 人工和管理成本
#
# 4. 与氢气管道成本处理方式的对比：
#    氢气：h2_pipeline_cost = Σ(h2量 × h2单位成本[i,j])
#    CO₂： co2_pipeline_cost = Σ(co2量 × co2单位成本[c,j])
#    两者完全一致，均不单独计算管道建设成本

# ✅ 新增：甲醇生产成本
methanol_production_cost = gp.quicksum(
    methanol_production[j,t] * methanol_unit_cost
    for j in saf_locations for t in hours
)

# ✅ 新增：甲醇储存成本
methanol_storage_cost = gp.quicksum(
    methanol_inventory[j,t] * methanol_storage_unit_cost
    for j in saf_locations for t in hours
)

# ✅ 保留：其他成本（SAF生产、运输、设施等）
saf_production_cost = ...
saf_transport_cost = ...
facility_cost = ...

# ✅ 修改后的总目标函数
total_cost = (
    h2_cost +
    co2_capture_cost +
    co2_transport_cost +
    h2_transport_cost +  # 已有
    methanol_production_cost +
    methanol_storage_cost +
    saf_production_cost +
    saf_transport_cost +
    facility_cost +
    shortage_penalty
)

model.setObjective(total_cost, GRB.MINIMIZE)
```

---

## 五、CO₂捕获计算模块开发

### 5.0 CO₂捕获数据源确认

#### 5.0.1 可用数据源总览

基于项目现有GIS数据，以下是确认可用的CO₂捕获源数据：

| 数据源类型 | 文件名 | 记录数 | 是否使用 | 备注 |
|----------|--------|--------|---------|------|
| **燃煤电厂** | coal_power_plants.csv | 3,821 | ✅ 使用 | 主要CO₂捕获源 |
| **天然气发电厂** | gas_power_plants.csv | 270 | ✅ 使用 | 次要CO₂捕获源 |
| **石油炼厂** | oil_refineries.csv | 220 | ✅ 使用 | 重要工业CO₂源 |
| **LNG接收站** | lng_terminals.csv | 129 | ❌ 不使用 | 按用户要求排除 |

**数据位置**：`products/gis_energy_mapping/gis_data_scraper/scraped_gis_data/`

---

#### 5.0.2 燃煤电厂数据详细说明

**文件**：`coal_power_plants.csv`
**数据量**：3,821 条记录

**关键字段**：

| 字段名 | 字段说明 | 数据类型 | 用途 |
|--------|---------|----------|------|
| `Plant_name` | 电厂名称 | String | 设施标识 |
| `Capacity__MW_` | 装机容量（兆瓦） | Float | CO₂捕获量计算基础 |
| `Status` | 运行状态 | String | 筛选条件（仅使用Operating） |
| `Latitude` / `Longitude` | 坐标 | Float | 距离计算和可视化 |
| `Capacity_factor` | 容量因子 | Float | 实际运行率（如有） |
| `Annual_CO2__million_tonnes___an` | 年CO₂排放量 | Float | 参考值（可用于验证） |
| `Start_year` | 投产年份 | Integer | 设施年龄评估 |
| `Province` | 省份 | String | 地理筛选 |

**数据质量**：
- ✅ 容量数据完整性高
- ✅ 坐标数据准确
- ⚠️ 部分记录缺少Capacity_factor，需使用默认值1

**预处理需求**：
1. 筛选Status为"Operating"的电厂
2. 对缺失的Capacity_factor使用行业平均值1
3. 验证Capacity__MW_在合理范围内（10-5000 MW）

---

#### 5.0.3 天然气发电厂数据详细说明

**文件**：`gas_power_plants.csv`
**数据量**：270 条记录

**关键字段**：

| 字段名 | 字段说明 | 数据类型 | 用途 |
|--------|---------|----------|------|
| `Name` / `ChineseName` | 电厂名称 | String | 设施标识 |
| `Capacity__MW_` | 装机容量（兆瓦） | Float | CO₂捕获量计算基础 |
| `Status` | 运行状态 | String | 筛选条件（仅使用Operating） |
| `Lat` / `Long` | 坐标 | Float | 距离计算和可视化 |
| `Technology` | 技术类型 | String | 排放因子选择依据 |
| `Gas_type_source` | 气源类型 | String | 补充信息 |
| `YearOnline` | 投产年份 | Integer | 设施年龄评估 |
| `Province` | 省份 | String | 地理筛选 |

**数据质量**：
- ✅ 容量数据完整
- ✅ 坐标数据准确
- ⚠️ 无Capacity_factor字段，统一使用默认值1

**预处理需求**：
1. 筛选Status为"Operating"的电厂
2. 统一使用Capacity_factor=1（天然气电厂典型值）
3. 验证Capacity__MW_在合理范围内（20-3000 MW）

---

#### 5.0.4 石油炼厂数据详细说明

**文件**：`oil_refineries.csv`
**数据量**：220 条记录

**关键字段**：

| 字段名 | 字段说明 | 数据类型 | 用途 |
|--------|---------|----------|------|
| `Name` / `ChineseName` | 炼厂名称 | String | 设施标识 |
| `Capacity` | 产能容量 | Float | CO₂捕获量计算基础 |
| `CapUnit` | 容量单位 | String | 通常为"KBD"（千桶/天） |
| `Status` | 运行状态 | String | 筛选条件（仅使用Operating） |
| `Lat` / `Long` | 坐标 | Float | 距离计算和可视化 |
| `YearOnline` | 投产年份 | Integer | 设施年龄评估 |
| `Province` | 省份 | String | 地理筛选 |
| `Coastal_` | 是否沿海 | String | 补充信息 |
| `Operator` | 运营商 | String | 补充信息 |

**数据质量**：
- ✅ 产能数据完整
- ✅ 坐标数据准确
- ⚠️ 容量单位为KBD（千桶/天），需转换为标准单位

**预处理需求**：
1. 筛选Status为"Operating"的炼厂
2. 容量单位转换：KBD → 吨原油/周
   - 1 KBD = 1000桶/天 × 7天 × 159升/桶 × 0.85吨/m³ ÷ 1000 = 945吨/周
3. 统一使用Capacity_factor=1（石油炼厂典型值）
4. 验证转换后容量在合理范围内

---

#### 5.0.5 CO₂捕获量计算方法

##### 5.0.5.1 燃煤电厂CO₂捕获计算

**计算步骤**：

```python
# Step 1: 计算周发电量
weekly_electricity_MWh = (
    Capacity__MW_ *                    # 装机容量
    168 hours *                        # 一周小时数
    capacity_factor                    # 容量因子（默认0.70）
)

# Step 2: 计算CO₂排放量
co2_emission_ton = (
    weekly_electricity_MWh *           # 周发电量
    0.95                               # 排放因子：tCO₂/MWh（燃煤电厂）
)

# Step 3: 计算CO₂捕获量
co2_capture_ton_per_week = (
    co2_emission_ton *                 # CO₂排放量
    0.85                               # 捕获率：85%
)

# Step 4: 估算捕获成本
capture_cost_yuan_per_ton = 150        # 燃煤电厂CCS成本：150元/吨
```

**参数依据**：
- **容量因子 0.70**：基于中国燃煤电厂平均运行率（来源：中国电力年鉴2023）
- **排放因子 0.95 tCO₂/MWh**：IPCC燃煤发电碳排放标准值
- **捕获率 85%**：后燃烧捕获技术（Post-combustion Capture）典型值（来源：Global CCS Institute）
- **成本 150元/吨**：基于现有CCS项目平均成本（来源：IEA CCS Cost Report 2024）

**计算示例**：
```
燃煤电厂：600 MW
容量因子：0.70
周发电量：600 × 168 × 0.70 = 70,560 MWh
CO₂排放：70,560 × 0.95 = 67,032 吨
CO₂捕获：67,032 × 0.85 = 56,977 吨/周
总成本：56,977 × 150 = 8,546,550 元/周
```

---

##### 5.0.5.2 天然气发电厂CO₂捕获计算

**计算步骤**：

```python
# Step 1: 计算周发电量
weekly_electricity_MWh = (
    Capacity__MW_ *                    # 装机容量
    168 hours *                        # 一周小时数
    0.75                               # 容量因子（天然气电厂典型值）
)

# Step 2: 计算CO₂排放量
co2_emission_ton = (
    weekly_electricity_MWh *           # 周发电量
    0.42                               # 排放因子：tCO₂/MWh（天然气电厂）
)

# Step 3: 计算CO₂捕获量
co2_capture_ton_per_week = (
    co2_emission_ton *                 # CO₂排放量
    0.90                               # 捕获率：90%（天然气电厂捕获效率更高）
)

# Step 4: 估算捕获成本
capture_cost_yuan_per_ton = 180        # 天然气电厂CCS成本：180元/吨
```

**参数依据**：
- **容量因子 0.75**：天然气电厂调峰运行典型值
- **排放因子 0.42 tCO₂/MWh**：IPCC天然气联合循环发电碳排放标准值
- **捕获率 90%**：天然气燃烧烟气CO₂浓度较高，捕获效率优于燃煤
- **成本 180元/吨**：天然气CCS成本略高于燃煤（技术要求更高）

**计算示例**：
```
天然气电厂：400 MW
容量因子：0.75
周发电量：400 × 168 × 0.75 = 50,400 MWh
CO₂排放：50,400 × 0.42 = 21,168 吨
CO₂捕获：21,168 × 0.90 = 19,051 吨/周
总成本：19,051 × 180 = 3,429,180 元/周
```

---

##### 5.0.5.3 石油炼厂CO₂捕获计算

**计算步骤**：

```python
# Step 1: 容量单位转换（KBD → 吨原油/周）
if CapUnit == "KBD":
    crude_oil_ton_per_week = (
        Capacity *                     # 产能（千桶/天）
        7 days *                       # 一周天数
        159 liters_per_barrel *        # 桶到升的转换
        0.85 ton_per_m3 /              # 原油密度（吨/立方米）
        1000                           # 升到立方米
    )
    # 简化公式：Capacity(KBD) × 945 = 吨原油/周

# Step 2: 计算实际处理量（考虑容量因子）
actual_crude_ton_per_week = (
    crude_oil_ton_per_week *           # 设计产能
    0.85                               # 容量因子（炼厂典型值）
)

# Step 3: 计算CO₂排放量
co2_emission_ton = (
    actual_crude_ton_per_week *        # 实际原油处理量
    0.6                                # 排放因子：tCO₂/吨原油
)

# Step 4: 计算CO₂捕获量
co2_capture_ton_per_week = (
    co2_emission_ton *                 # CO₂排放量
    0.80                               # 捕获率：80%
)

# Step 5: 估算捕获成本
capture_cost_yuan_per_ton = 120        # 石油炼厂CCS成本：120元/吨
```

**参数依据**：
- **容量因子 0.85**：石油炼厂连续运行率（来源：石化行业统计数据）
- **排放因子 0.6 tCO₂/吨原油**：炼油过程综合排放因子（来源：IPCC工业过程排放指南）
- **捕获率 80%**：工业过程CO₂捕获技术典型值
- **成本 120元/吨**：炼厂CCS成本相对较低（浓度较高，捕获容易）

**计算示例**：
```
石油炼厂：100 KBD
周原油处理能力：100 × 945 = 94,500 吨/周（设计）
实际处理量：94,500 × 0.85 = 80,325 吨/周
CO₂排放：80,325 × 0.6 = 48,195 吨
CO₂捕获：48,195 × 0.80 = 38,556 吨/周
总成本：38,556 × 120 = 4,626,720 元/周
```

---

#### 5.0.6 输出数据标准格式

**输出DataFrame结构**：

```python
columns = [
    'location_id',                    # 设施唯一标识（自动生成）
    'location_name',                  # 设施名称
    'facility_type',                  # 设施类型：'coal_power' / 'gas_power' / 'oil_refinery'
    'latitude',                       # 纬度
    'longitude',                      # 经度
    'province',                       # 省份
    'capacity_original',              # 原始容量（MW或KBD）
    'capacity_unit',                  # 容量单位
    'capacity_factor',                # 容量因子
    'status',                         # 运行状态
    'week',                           # 周数（0 to time_horizon_weeks-1）
    'co2_capture_capacity_ton_per_week',  # 每周CO₂捕获量（吨）
    'capture_cost_yuan_per_ton',      # 单位捕获成本（元/吨）
    'total_capture_cost_yuan_per_week',   # 周总捕获成本（元）
    'data_source',                    # 数据来源文件名
    'year_online'                     # 投产年份（如有）
]
```

**数据验证规则**：
1. `co2_capture_capacity_ton_per_week` > 0
2. `latitude` in [-90, 90], `longitude` in [-180, 180]
3. `week` in [0, time_horizon_weeks-1]
4. `facility_type` in ['coal_power', 'gas_power', 'oil_refinery']
5. `capture_cost_yuan_per_ton` > 0

---

#### 5.0.7 数据处理流程图

```
┌─────────────────────────────────────────────────────────────┐
│                   CO₂捕获数据处理流程                          │
└─────────────────────────────────────────────────────────────┘

   ┌──────────────┐      ┌──────────────┐      ┌──────────────┐
   │ 燃煤电厂     │      │ 天然气电厂   │      │ 石油炼厂     │
   │ .csv (3821)  │      │ .csv (270)   │      │ .csv (220)   │
   └──────┬───────┘      └──────┬───────┘      └──────┬───────┘
          │                     │                     │
          │                     │                     │
   ┌──────▼─────────────────────▼─────────────────────▼───────┐
   │              GIS数据加载与预处理模块                       │
   │  • 读取CSV文件                                            │
   │  • 筛选Status='Operating'                                │
   │  • 缺失值填充（Capacity_factor）                         │
   │  • 容量单位转换（KBD→吨/周）                              │
   └──────┬─────────────────────────────────────────────────┘
          │
          │  ┌─────────────────────────────────────────┐
          ├──► 燃煤电厂CO₂捕获计算                      │
          │  │ MW × 168h × 0.70 × 0.95 × 0.85         │
          │  └─────────────────────────────────────────┘
          │
          │  ┌─────────────────────────────────────────┐
          ├──► 天然气电厂CO₂捕获计算                    │
          │  │ MW × 168h × 0.75 × 0.42 × 0.90         │
          │  └─────────────────────────────────────────┘
          │
          │  ┌─────────────────────────────────────────┐
          └──► 石油炼厂CO₂捕获计算                      │
             │ KBD × 945 × 0.85 × 0.6 × 0.80          │
             └─────────────────────────────────────────┘
                              │
                              │
   ┌──────────────────────────▼───────────────────────────────┐
   │                   数据合并与验证                           │
   │  • 合并3类数据源                                          │
   │  • 数据验证（范围检查、空值检查）                          │
   │  • 生成location_id                                       │
   │  • 添加week维度                                          │
   └──────────────────────────┬───────────────────────────────┘
                              │
                              │
   ┌──────────────────────────▼───────────────────────────────┐
   │              标准化DataFrame输出                           │
   │  包含15列：location_id, name, type, lat, lon, ...        │
   │  总记录数：(3821 + 270 + 220) × time_horizon_weeks       │
   └──────────────────────────┬───────────────────────────────┘
                              │
                              │
   ┌──────────────────────────▼───────────────────────────────┐
   │         输出到优化模型 / 保存到CSV文件                      │
   │  • products/.../data/co2_capture_sources.csv             │
   │  • 供优化模型加载使用                                      │
   └──────────────────────────────────────────────────────────┘
```

---

### 5.1 模块文件：co2_capture_calculator.py

**文件路径**：`src/co2/co2_capture_calculator.py`

**主要功能**：
1. 从GIS数据加载燃煤电厂、LNG设施、炼油厂数据
2. 根据设施容量和排放因子计算CO₂排放量
3. 应用捕获率计算可捕获CO₂量
4. 估算捕获成本
5. 输出标准化的CO₂捕获源数据表

**核心方法**：
- `calculate_from_gis_data()` - 主计算方法
- `_calculate_coal_capture()` - 燃煤电厂CO₂计算
- `_calculate_lng_capture()` - LNG设施CO₂计算
- `_calculate_refinery_capture()` - 炼油厂CO₂计算
- `_load_coal_power_plants()` - 加载燃煤电厂GIS数据
- `_load_lng_terminals()` - 加载LNG设施GIS数据
- `_load_oil_refineries()` - 加载炼油厂GIS数据

**计算公式**：
```
CO₂捕获量(吨/周) = 设施容量 × 运行时间 × 容量因子 × 排放因子 × 捕获率

例如燃煤电厂：
- 设施容量：600 MW
- 运行时间：168 小时/周
- 容量因子：0.70
- 发电量：600 × 168 × 0.70 = 70,560 MWh
- CO₂排放：70,560 × 0.95 = 67,032 吨CO₂
- CO₂捕获：67,032 × 0.85 = 56,977 吨CO₂/周
```

### 5.2 碳排放计算模块：co2_emission_calculator.py

**文件路径**：`src/co2/co2_emission_calculator.py`

**主要功能**：
1. 计算全生命周期碳排放
2. 不依赖外部库，使用自定义计算方法
3. 分项计算各环节排放
4. 计算CO₂利用负排放
5. 生成碳排放报告

**核心方法**：
- `calculate_lifecycle_emissions()` - 主计算方法
- `_calc_h2_production_emission()` - 氢气生产排放
- `_calc_co2_capture_emission()` - CO₂捕获过程排放
- `_calc_h2_transport_emission()` - 氢气运输排放
- `_calc_co2_transport_emission()` - CO₂运输排放
- `_calc_saf_transport_emission()` - SAF运输排放
- `_calc_methanol_synthesis_emission()` - 甲醇合成排放
- `_calc_mtj_conversion_emission()` - MTJ转化排放
- `_calc_storage_emission()` - 储存处理排放
- `_calc_co2_utilization_credit()` - CO₂利用负排放

**输出指标**：
- 总碳排放量 (kgCO₂e)
- 碳强度 (gCO₂e/MJ SAF)
- 与传统航煤对比的减排百分比
- 是否符合CORSIA标准
- 各环节分项排放

---

## 六、详细任务分解（TodoList）

### ⚡ 实施优先级调整说明

**核心策略变更**：将CO₂捕获模块开发作为**第一优先级任务**，确保数据源和计算方法的正确性。

**调整理由**：
1. CO₂捕获模块是绿氢供应链的**核心差异点**，必须优先验证
2. 独立模块开发，不依赖其他代码迁移，可以并行工作
3. 完成后可以立即进行数据验证，及早发现问题
4. 为后续的模型集成提供清晰的接口定义

---

### 📋 任务总览

**总任务数**：50个子任务
**预计工期**：12个工作日
**关键路径**：Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5

---

### Phase 0: CO₂捕获模块开发（优先级最高）⭐

**时间**：2天
**前置条件**：无（独立开发）
**目标**：完成CO₂捕获计算器，验证GIS数据可用性

#### Task 0.1: 创建CO₂模块目录结构
- [ ] 在当前项目临时位置创建测试目录
- [ ] 创建 `co2/` 文件夹
- [ ] 创建 `co2/__init__.py`
- [ ] 创建 `co2/co2_capture_calculator.py` 空文件
- **验收**：目录结构创建成功，可以import

#### Task 0.2: 实现GIS数据加载功能
- [ ] 实现 `_load_coal_power_plants()` 方法
  - 读取 `coal_power_plants.csv`
  - 筛选 Status='Operating'
  - 处理缺失的 Capacity_factor（默认0.70）
  - 数据验证：容量范围检查
- [ ] 实现 `_load_gas_power_plants()` 方法
  - 读取 `gas_power_plants.csv`
  - 筛选 Status='Operating'
  - 使用固定 Capacity_factor=0.75
  - 数据验证：容量范围检查
- [ ] 实现 `_load_oil_refineries()` 方法
  - 读取 `oil_refineries.csv`
  - 筛选 Status='Operating'
  - 容量单位转换：KBD → 吨/周（×945）
  - 使用固定 Capacity_factor=0.85
  - 数据验证：转换后容量检查
- **验收**：成功加载3类GIS数据，打印记录数

#### Task 0.3: 实现燃煤电厂CO₂计算
- [ ] 实现 `_calculate_coal_capture()` 方法
  - 输入：plant (pd.Series), week (int)
  - 计算：MW × 168 × 0.70 × 0.95 × 0.85
  - 输出：co2_capture_ton_per_week (float)
- [ ] 添加日志记录：每100个电厂打印一次进度
- [ ] 单元测试：使用示例数据验证计算结果
- **验收**：600MW电厂计算结果=56,977吨/周

#### Task 0.4: 实现天然气电厂CO₂计算
- [ ] 实现 `_calculate_gas_capture()` 方法
  - 输入：plant (pd.Series), week (int)
  - 计算：MW × 168 × 0.75 × 0.42 × 0.90
  - 输出：co2_capture_ton_per_week (float)
- [ ] 添加日志记录
- [ ] 单元测试：使用示例数据验证
- **验收**：400MW电厂计算结果=19,051吨/周

#### Task 0.5: 实现石油炼厂CO₂计算
- [ ] 实现 `_calculate_refinery_capture()` 方法
  - 输入：refinery (pd.Series), week (int)
  - 步骤1：KBD × 945 → 吨/周
  - 步骤2：× 0.85（容量因子）
  - 步骤3：× 0.6（排放因子）
  - 步骤4：× 0.80（捕获率）
  - 输出：co2_capture_ton_per_week (float)
- [ ] 添加日志记录
- [ ] 单元测试：使用示例数据验证
- **验收**：100KBD炼厂计算结果=38,556吨/周

#### Task 0.6: 实现主计算方法
- [ ] 实现 `calculate_from_gis_data(gis_data_dir, time_horizon_weeks)` 方法
  - 加载3类GIS数据
  - 对每类数据源循环计算CO₂捕获量
  - 添加week维度（0 to time_horizon_weeks-1）
  - 合并3类数据源到统一DataFrame
  - 生成location_id（唯一标识）
  - 添加capture_cost_yuan_per_ton列
  - 数据验证：检查空值、范围、类型
- [ ] 返回标准化DataFrame（15列）
- **验收**：输出DataFrame符合5.0.6节定义的格式

#### Task 0.7: 添加成本计算
- [ ] 为每条记录添加 `capture_cost_yuan_per_ton`
  - coal_power: 150元/吨
  - gas_power: 180元/吨
  - oil_refinery: 120元/吨
- [ ] 计算 `total_capture_cost_yuan_per_week`
  - = co2_capture_capacity × capture_cost
- **验收**：成本列非空且>0

#### Task 0.8: 数据验证和日志
- [ ] 实现数据验证方法 `_validate_output()`
  - 检查必需列是否存在
  - 检查数值列范围（>0, 坐标范围等）
  - 检查空值
  - 生成验证报告
- [ ] 添加详细日志
  - INFO: 开始加载、完成加载、记录数统计
  - WARNING: 数据质量问题
  - ERROR: 严重错误
- **验收**：日志输出清晰，验证通过

#### Task 0.9: 保存输出到CSV
- [ ] 实现保存方法 `save_to_csv(output_path)`
- [ ] 保存位置：`data/co2_capture_sources.csv`
- [ ] 添加时间戳到文件名（可选）
- **验收**：CSV文件生成成功，可用Excel打开

#### Task 0.10: 完整测试CO₂模块
- [ ] 编写测试脚本 `test_co2_capture.py`
  - 测试3类数据加载
  - 测试3类捕获计算
  - 测试主方法
  - 测试数据验证
  - 测试CSV保存
- [ ] 使用time_horizon_weeks=1运行完整流程
- [ ] 检查输出：(3821+270+220)×1 = 4311条记录
- [ ] 计算总捕获量、平均成本等统计指标
- **验收**：所有测试通过，统计结果合理

---

### Phase 1: 目录搭建与文件迁移

**时间**：1天
**前置条件**：Phase 0完成
**目标**：建立新产品目录，原样迁移所有文件

#### Task 1.1: 创建新产品目录结构
- [ ] 创建主目录：`green_hydrogen_supply_chain_optimization/`
- [ ] 创建子目录：
  - `src/` `src/core/` `src/co2/` `src/hydrogen/`
  - `src/routing/` `src/cache/` `src/visualization/`
  - `src/utils/` `src/sensitivity_analysis/`
  - `data/` `results/` `results/tables/` `results/figures/`
  - `results/reports/` `results/logs/` `tests/`
- **验收**：目录树完整（对照2.1节）

#### Task 1.2: 复制hydrogen模块
- [ ] 复制4个文件到 `src/hydrogen/`
  - `__init__.py`
  - `hydrogen_clustering_optimizer.py`
  - `hydrogen_pipeline_distance_calculator.py`
  - `hydrogen_transport_visualizer.py`
- **验收**：文件内容与原文件完全一致

#### Task 1.3: 复制routing模块
- [ ] 复制4个文件到 `src/routing/`
- **验收**：文件内容完全一致

#### Task 1.4: 复制cache模块
- [ ] 复制6个文件到 `src/cache/`
- **验收**：文件内容完全一致

#### Task 1.5: 复制visualization模块
- [ ] 复制3个文件到 `src/visualization/`
- **验收**：文件内容完全一致

#### Task 1.6: 复制utils模块
- [ ] 复制1个文件到 `src/utils/`
- **验收**：文件内容完全一致

#### Task 1.7: 复制sensitivity_analysis模块
- [ ] 复制3个文件到 `src/sensitivity_analysis/`
- **验收**：文件内容完全一致

#### Task 1.8: 复制核心模型文件
- [ ] 复制 `natural_gas_optimization_model.py` 到 `src/core/`
- [ ] 重命名为 `green_hydrogen_optimization_model.py`
- [ ] **暂不修改文件内容**（除了文件名）
- **验收**：文件存在，内容未改变

#### Task 1.9: 移动CO₂模块到新目录
- [ ] 将Phase 0开发的CO₂模块移动到 `src/co2/`
- [ ] 确保 `__init__.py` 和 `co2_capture_calculator.py` 都在
- **验收**：CO₂模块在正确位置

#### Task 1.10: 创建__init__.py文件
- [ ] 为所有模块目录创建 `__init__.py`
- [ ] 保持与原项目一致的导入结构
- **验收**：所有目录都有__init__.py

---

### Phase 2: Import路径批量修改

**时间**：0.5天
**前置条件**：Phase 1完成
**目标**：修改所有import路径，确保代码可导入

#### Task 2.1: 批量替换import路径 - hydrogen模块
- [ ] 在4个文件中查找：`natural_gas_supply_chain_optimization`
- [ ] 替换为：`green_hydrogen_supply_chain_optimization`
- [ ] 测试导入：`from src.hydrogen import *`
- **验收**：无ImportError

#### Task 2.2: 批量替换import路径 - routing模块
- [ ] 同上操作
- **验收**：无ImportError

#### Task 2.3: 批量替换import路径 - cache模块
- [ ] 同上操作
- **验收**：无ImportError

#### Task 2.4: 批量替换import路径 - visualization模块
- [ ] 同上操作
- **验收**：无ImportError

#### Task 2.5: 批量替换import路径 - utils模块
- [ ] 同上操作
- **验收**：无ImportError

#### Task 2.6: 批量替换import路径 - sensitivity模块
- [ ] 同上操作
- **验收**：无ImportError

#### Task 2.7: 修改核心模型import路径
- [ ] 在 `green_hydrogen_optimization_model.py` 中修改import
- [ ] **仅修改路径，不修改业务逻辑**
- **验收**：无ImportError

#### Task 2.8: 测试完整导入链
- [ ] 测试主类导入：
  ```python
  from src.core.green_hydrogen_optimization_model import NaturalGasSupplyChainOptimizer
  ```
- [ ] 测试CO₂模块导入：
  ```python
  from src.co2.co2_capture_calculator import CO2CaptureCalculator
  ```
- **验收**：所有导入成功，无错误

---

### Phase 3: 配置文件处理

**时间**：1天
**前置条件**：Phase 2完成
**目标**：创建新配置文件，添加CO₂参数

#### Task 3.1: 复制配置文件
- [ ] 复制 `NaturalGasSupplyChainOptimizer_config.yaml`
- [ ] 重命名为 `GreenHydrogenSupplyChainOptimizer_config.yaml`
- [ ] 保持内容完全一致
- **验收**：新文件存在，YAML格式正确

#### Task 3.2: 修改文件头部元数据
- [ ] 修改description
- [ ] 修改metadata.version → 2.0.0
- [ ] 修改metadata.last_updated
- [ ] 添加metadata.process_type: 'two_step_methanol_mtj'
- **验收**：元数据已更新

#### Task 3.3: 删除天然气相关参数
- [ ] 删除 `supply_capacity.natural_gas_supply`
- [ ] 删除 `supply_capacity.lng_terminal_capacity`
- [ ] 删除 `cost_parameters.raw_materials.natural_gas_price`
- [ ] 删除technologies中的 `ng_consumption_ratio`
- [ ] 删除碳排放中的ng相关参数
- [ ] 删除unified_costs中的ng参数
- [ ] 删除transport_constraints.ng_truck_transport
- [ ] 删除data_paths中的ng_pipelines路径
- **验收**：grep查找"natural_gas"或"ng_"无结果

#### Task 3.4: 添加CO₂捕获参数
- [ ] 添加 `co2_parameters` section
- [ ] 添加 `capture_sources` 子section（按3.2.3节）
- [ ] 添加 `capture_costs` 子section
- [ ] 添加 `transport` 子section
- [ ] 添加 `storage` 子section
- **验收**：CO₂参数完整（对照3.2.3节）

#### Task 3.5: 添加绿氢供应参数
- [ ] 添加 `green_hydrogen_supply` section
- [ ] 添加生产成本参数
- [ ] 添加运输参数
- [ ] 添加储存参数
- **验收**：绿氢参数完整

#### Task 3.6: 修改技术路线参数
- [ ] 删除原有4种技术路线
- [ ] 添加 `methanol_mtj_two_step` 技术
- [ ] 配置原料消耗比例
- [ ] 配置工艺参数
- [ ] 配置能耗参数
- [ ] 配置适用位置
- **验收**：只有一种两步法技术

#### Task 3.7: 修改碳排放参数
- [ ] 保留benchmarks
- [ ] 修改raw_materials（绿氢、CO₂捕获）
- [ ] 修改production_process（E-CRM、MTJ）
- [ ] 添加co2_utilization_credit
- [ ] 修改transportation（H₂、CO₂、SAF）
- [ ] 修改storage_handling
- **验收**：碳排放参数符合绿氢工艺

#### Task 3.8: 修改数据路径
- [ ] 删除天然气管道路径
- [ ] 添加coal_power_plants路径
- [ ] 添加gas_power_plants路径（用于天然气发电CO₂捕获）
- [ ] 添加oil_refineries路径
- [ ] 添加新的output模板（co2_supply_plan等）
- **验收**：数据路径指向正确

#### Task 3.9: 验证YAML格式
- [ ] 使用Python加载YAML：
  ```python
  import yaml
  with open(config_path) as f:
      config = yaml.safe_load(f)
  ```
- [ ] 检查所有key可访问
- **验收**：YAML加载成功，无语法错误

#### Task 3.10: 测试配置加载
- [ ] 在优化器中测试加载新配置
- [ ] 打印关键参数验证
- **验收**：配置成功加载，参数正确

---

### Phase 4: 核心模型集成CO₂模块

**时间**：2天
**前置条件**：Phase 3完成，CO₂模块可用
**目标**：在优化模型中集成CO₂捕获数据加载

#### Task 4.1: 修改类名和日志路径
- [ ] 类名：`NaturalGasSupplyChainOptimizer` → `GreenHydrogenSupplyChainOptimizer`
- [ ] 日志目录：`.../natural_gas_...` → `.../green_hydrogen_...`
- [ ] 日志前缀：`ng_supply_chain` → `green_h2_supply_chain`
- [ ] 配置文件路径修改
- **验收**：类可实例化，日志路径正确

#### Task 4.2: 添加CO₂捕获源加载方法
- [ ] 实现 `_load_co2_capture_sources()` 方法
- [ ] 导入CO2CaptureCalculator
- [ ] 调用calculate_from_gis_data()
- [ ] 返回DataFrame
- [ ] 添加日志记录
- **验收**：方法可运行，返回数据

#### Task 4.3: 修改load_data()方法
- [ ] 在load_data()中调用_load_co2_capture_sources()
- [ ] 存储到self.co2_sources
- [ ] 打印CO₂源统计信息
- [ ] **保留天然气加载代码**（此阶段不删除）
- **验收**：数据加载成功，CO₂源可用

#### Task 4.4: 测试数据加载流程
- [ ] 创建最小测试脚本
- [ ] 实例化优化器
- [ ] 调用load_data()
- [ ] 检查self.co2_sources
- [ ] 打印前10条记录
- **验收**：CO₂数据正确加载

---

### Phase 5: 碳排放计算模块开发

**时间**：1天
**前置条件**：Phase 4完成
**目标**：实现自定义碳排放计算

#### Task 5.1: 创建CO2EmissionCalculator类框架
- [ ] 创建文件 `src/co2/co2_emission_calculator.py`
- [ ] 定义类 `CO2EmissionCalculator`
- [ ] 添加__init__方法（接收config）
- [ ] 添加主方法 `calculate_lifecycle_emissions()`
- **验收**：类可导入

#### Task 5.2: 实现原材料排放计算
- [ ] `_calc_h2_production_emission()` - 绿氢生产
- [ ] `_calc_co2_capture_emission()` - CO₂捕获过程
- [ ] 使用config中的排放强度参数
- **验收**：方法返回合理数值

#### Task 5.3: 实现运输排放计算
- [ ] `_calc_h2_transport_emission()` - 氢气运输
- [ ] `_calc_co2_transport_emission()` - CO₂运输
- [ ] `_calc_saf_transport_emission()` - SAF运输
- [ ] 考虑距离和运输方式
- **验收**：排放量随距离线性增加

#### Task 5.4: 实现生产过程排放计算
- [ ] `_calc_methanol_synthesis_emission()` - E-CRM甲醇合成
- [ ] `_calc_mtj_conversion_emission()` - MTJ转化
- [ ] `_calc_storage_emission()` - 储存处理
- **验收**：排放量与产量成正比

#### Task 5.5: 实现CO₂利用负排放
- [ ] `_calc_co2_utilization_credit()` - CO₂固定负排放
- [ ] 使用co2_utilization_credit系数
- **验收**：返回负值

#### Task 5.6: 实现总排放计算和报告
- [ ] 在`calculate_lifecycle_emissions()`中整合各环节
- [ ] 计算总碳排放量（kgCO₂e）
- [ ] 计算碳强度（gCO₂e/MJ SAF）
- [ ] 与传统航煤对比
- [ ] 判断是否符合CORSIA标准
- **验收**：返回完整的排放报告字典

#### Task 5.7: 单元测试碳排放模块
- [ ] 测试各分项排放计算
- [ ] 测试总排放计算
- [ ] 使用典型参数验证结果合理性
- **验收**：SAF碳强度 < 30 gCO₂e/MJ

---

### Phase 6: 核心模型重构

**时间**：4天
**前置条件**：Phase 5完成，所有模块可用
**目标**：重构决策变量、约束和目标函数

#### Task 6.1-6.10: 决策变量重构
- [ ] 删除天然气供应变量（ng_supply, lng_supply）
- [ ] 新增CO₂供应变量（co2_supply）
- [ ] 新增甲醇生产变量（methanol_production）
- [ ] 新增甲醇库存变量（methanol_inventory）
- [ ] 修改SAF生产变量（仅methanol_mtj_two_step）
- [ ] 保留氢气供应变量
- [ ] 保留其他变量（运输、库存等）
- [ ] 测试：模型可构建
- [ ] 打印变量统计
- **验收**：决策变量定义完整

#### Task 6.11-6.20: 约束条件重构
- [ ] 删除天然气平衡约束
- [ ] 新增CO₂供应平衡约束（按周）
- [ ] 新增H₂+CO₂→甲醇约束（两步法第一步）
- [ ] 新增甲醇→SAF约束（两步法第二步）
- [ ] 新增甲醇库存平衡约束
- [ ] 保留需求满足约束
- [ ] 保留运输约束
- [ ] 保留其他约束
- [ ] 测试：约束添加成功
- **验收**：约束数量合理，无语法错误

#### Task 6.21-6.30: 目标函数重构
- [ ] 删除天然气成本项
- [ ] 删除LNG成本项
- [ ] 新增CO₂捕获成本
- [ ] 新增CO₂运输成本
- [ ] 新增甲醇生产成本
- [ ] 新增甲醇储存成本
- [ ] 保留氢气成本
- [ ] 保留SAF生产成本
- [ ] 保留运输成本
- [ ] 保留设施成本
- [ ] 保留缺货惩罚
- [ ] 设置目标函数：最小化总成本
- [ ] 测试：目标函数可计算
- **验收**：成本结构合理

#### Task 6.31: 完全删除天然气代码
- [ ] 删除_load_ng_pipelines()方法
- [ ] 删除_load_lng_terminals()方法（如果有）
- [ ] 删除所有ng相关变量定义
- [ ] 删除所有ng相关约束
- [ ] 删除所有ng相关成本项
- [ ] grep搜索确认无ng残留
- **验收**：grep "ng_" "natural_gas" 无结果

---

### Phase 7: 集成测试

**时间**：2天
**前置条件**：Phase 6完成
**目标**：端到端测试，验证模型可求解

#### Task 7.1-7.5: 小规模测试
- [ ] 创建小规模测试数据（1个机场，10个电厂，1周）
- [ ] 运行优化器
- [ ] 检查求解状态
- [ ] 检查解的合理性
- [ ] 修复bug（如有）
- **验收**：小规模问题求解成功

#### Task 7.6-7.10: 完整测试
- [ ] 使用完整数据运行（所有机场，所有电厂，多周）
- [ ] 监控求解时间和内存使用
- [ ] 分析优化结果
- [ ] 验证成本分解
- [ ] 验证碳排放计算
- **验收**：完整问题求解成功

---

### Phase 8: 文档编写

**时间**：1天
**前置条件**：Phase 7完成
**目标**：完善项目文档

#### Task 8.1-8.5: 编写文档
- [ ] 编写README.md
- [ ] 编写requirements.txt
- [ ] 更新代码注释
- [ ] 创建使用手册
- [ ] PEP8代码规范检查
- **验收**：文档完整，项目可交付

---

## 七、实施步骤与时间计划（原版保留）

### Phase 1: 目录搭建与文件完整迁移（1天）

**核心原则**：⚠️ **原样复制，不修改业务逻辑！**

**任务**：
1. 创建新产品目录结构
2. **原样复制**src/下所有子目录（hydrogen, routing, cache, visualization, utils, sensitivity_analysis）
3. 复制src/core/natural_gas_optimization_model.py → green_hydrogen_optimization_model.py（仅重命名文件）
4. **仅修改import路径**：批量替换 `natural_gas_supply_chain_optimization` → `green_hydrogen_supply_chain_optimization`
5. 创建空的co2/目录和__init__.py
6. **保留所有天然气相关代码**，不做任何删除
7. 确保迁移后的代码能够正常import（语法检查）

**禁止操作**：
- ❌ 不删除天然气相关变量、方法、约束
- ❌ 不添加CO₂相关业务逻辑
- ❌ 不修改配置文件中的参数值
- ❌ 不修改类名（暂时保留NaturalGasSupplyChainOptimizer）

**验收标准**：
- [ ] 新目录结构完整
- [ ] 所有文件迁移完成（文件内容与原文件一致）
- [ ] import路径修改完成，无导入错误
- [ ] 可以成功import主模块类：`from src.core.green_hydrogen_optimization_model import NaturalGasSupplyChainOptimizer`
- [ ] 所有天然气相关代码保持完整

---

### Phase 2: 配置文件复制（0.5天）

**核心原则**：⚠️ **先复制原配置，暂不修改参数！**

**任务**：
1. 复制配置文件：`NaturalGasSupplyChainOptimizer_config.yaml` → `GreenHydrogenSupplyChainOptimizer_config.yaml`
2. **仅修改文件头部元数据**（文件说明、版本号）
3. **暂不删除天然气参数**，保持配置文件完整
4. 验证YAML文件格式正确性
5. 测试新配置文件能否被成功加载

**禁止操作**：
- ❌ 不删除天然气相关参数
- ❌ 不新增CO₂参数（这一步在Phase 5进行）
- ❌ 不修改参数数值

**验收标准**：
- [ ] 配置文件创建完成
- [ ] YAML格式验证通过
- [ ] 优化器能成功加载新配置文件
- [ ] 配置内容与原文件保持一致（除元数据外）

---

### Phase 2.5: 配置文件参数修改（0.5天）

**说明**：此阶段在Phase 5代码重构之前进行

**任务**：
1. 按照3.2节删除天然气相关参数
2. 按照3.2节新增CO₂和绿氢参数
3. 网络搜索收集最新工艺参数
4. 填写所有新增参数的数值

**验收标准**：
- [ ] 天然气参数已完全删除
- [ ] CO₂和绿氢参数已添加
- [ ] 所有参数值合理且有数据来源

---

### Phase 3: CO₂捕获计算模块开发（2天）

**任务**：
1. 实现CO2CaptureCalculator类
2. 实现从GIS数据加载功能
3. 实现燃煤电厂CO₂计算
4. 实现LNG设施CO₂计算
5. 单元测试

**验收标准**：
- [ ] CO₂捕获计算器工作正常
- [ ] 能从GIS数据生成co2_capture_sources.csv
- [ ] 数据合理性验证通过

---

### Phase 4: 碳排放计算模块开发（1天）

**任务**：
1. 实现CO2EmissionCalculator类
2. 实现各分项排放计算方法
3. 实现CO₂利用负排放计算
4. 单元测试

**验收标准**：
- [ ] 碳排放计算器工作正常
- [ ] 计算结果符合预期
- [ ] 单元测试通过

---

### Phase 5: 核心模型代码重构（4天）

**核心原则**：⚠️ **基于迁移成功的代码进行重构，分步验证！**

**前置条件**：
- Phase 1-4全部完成
- 迁移的代码能够正常运行
- CO₂捕获和碳排放模块已开发完成

**任务**（按顺序逐步进行）：

#### Day 1: 类名和基础重构
1. 修改类名：`NaturalGasSupplyChainOptimizer` → `GreenHydrogenSupplyChainOptimizer`
2. 修改日志前缀：`ng_supply_chain` → `green_h2_supply_chain`
3. 更新所有类方法的文档字符串
4. **测试**：确保类能够正常实例化

#### Day 2: 数据加载方法重构
1. 新增：`_load_co2_capture_sources()` 方法
2. 修改：`load_data()` 方法，调用CO₂加载
3. **保留但标记待删除**：天然气管道加载方法（添加TODO注释）
4. **测试**：确保数据加载正常，CO₂数据正确

#### Day 3: 决策变量和约束重构
1. 新增：CO₂供应变量、甲醇生产变量、甲醇库存变量
2. 新增：两步法工艺约束（H₂+CO₂→甲醇→SAF）
3. 新增：甲醇库存平衡约束
4. **暂时保留**：天然气相关变量和约束
5. **测试**：模型能够构建，无语法错误

#### Day 4: 目标函数重构和清理
1. 新增：CO₂捕获成本、CO₂运输成本、甲醇成本项
2. 删除：天然气成本项
3. 删除：所有天然气相关的数据加载方法、变量、约束
4. **全面测试**：模型能够求解，结果合理

**禁止操作**：
- ❌ 不要一次性删除所有天然气代码（容易出错）
- ❌ 不要跳过中间测试步骤

**验收标准**：
- [ ] 类名修改完成
- [ ] 数据加载方法重构完成
- [ ] 决策变量定义完成
- [ ] 约束条件重写完成
- [ ] 目标函数修改完成
- [ ] 天然气相关代码完全删除
- [ ] 每个步骤都经过测试验证
- [ ] 语法检查通过
- [ ] 逻辑审查通过

---

### Phase 6: 集成测试与调试（2天）

**任务**：
1. 创建小规模测试案例
2. 运行优化器并调试
3. 修复bugs
4. 验证结果合理性

**验收标准**：
- [ ] 模型能成功求解
- [ ] 结果数据完整
- [ ] 成本和碳排放合理

---

### Phase 7: 文档与收尾（1天）

**任务**：
1. 编写README.md
2. 更新代码注释
3. 创建用户手册
4. 代码规范检查

**验收标准**：
- [ ] 文档完整清晰
- [ ] 代码符合PEP8
- [ ] 项目可交付

---

**总计**：12个工作日

---

## 阶段性里程碑

### 里程碑1：迁移完成（Phase 1-2结束）
- ✅ 新产品目录建立
- ✅ 所有文件迁移完成
- ✅ 代码能够正常import
- ✅ 配置文件复制完成
- **此时代码应该是天然气版本的完整副本**

### 里程碑2：新模块开发完成（Phase 3-4结束）
- ✅ CO₂捕获计算器开发完成
- ✅ 碳排放计算器开发完成
- ✅ 配置参数已更新（Phase 2.5）
- **此时具备了重构所需的所有新功能模块**

### 里程碑3：代码重构完成（Phase 5结束）
- ✅ 类名和方法名已更新
- ✅ 天然气代码已删除
- ✅ CO₂和绿氢代码已添加
- ✅ 模型能够成功求解
- **此时已完成从天然气版本到绿氢版本的转换**

### 里程碑4：项目交付（Phase 6-7结束）
- ✅ 所有测试通过
- ✅ 文档完整
- ✅ 代码规范
- **项目可以正式使用**

---

## 七、关键技术参数数据源

### 7.1 在线数据源推荐

**绿氢生产参数**：
- IEA Hydrogen Report 2024
- IRENA Green Hydrogen Cost 2024
- 搜索关键词："green hydrogen LCOE 2024 china"

**CO₂捕获参数**：
- Global CCS Institute - CO2RE Database
- IPCC Carbon Capture and Storage Report
- 搜索关键词："carbon capture cost coal power plant 2024"

**甲醇合成参数**：
- Carbon Recycling International技术报告
- 搜索关键词："CO2 to methanol electrolysis efficiency"

**MTJ航煤转化参数**：
- Haldor Topsoe MTJ技术文档
- 搜索关键词："methanol to jet fuel conversion ratio"

### 7.2 建议参数范围（基于文献）

```yaml
# 两步法工艺参数（参考范围）
methanol_mtj_two_step:
  h2_consumption_ratio: 0.18-0.22        # kg H₂/kg SAF
  co2_consumption_ratio: 3.2-3.8         # kg CO₂/kg SAF
  methanol_intermediate_ratio: 1.2-1.4   # kg甲醇/kg SAF
  efficiency: 0.65-0.75                  # 总体效率
  e_crm_efficiency: 0.70-0.80            # 甲醇合成效率
  mtj_efficiency: 0.80-0.90              # MTJ转化效率

# 成本参数（参考范围）
green_hydrogen_supply:
  production_cost_yuan_per_kg: 20-35     # 绿氢成本(2024年)

co2_parameters:
  capture_costs:
    coal_power_yuan_per_ton: 120-200     # 燃煤CCS成本
    lng_power_yuan_per_ton: 150-250      # LNG CCS成本
```

---

## 八、风险与缓解措施

### 8.1 数据风险

**风险**：GIS数据可能缺少电厂容量信息
**缓解**：使用行业平均值，提供参数配置接口

### 8.2 模型复杂度

**风险**：新增CO₂变量增加求解时间
**缓解**：使用聚类减少决策变量数量

### 8.3 参数不确定性

**风险**：新工艺参数可能不准确
**缓解**：使用多源数据交叉验证，实施敏感性分析

---

## 九、验收标准总结

### 9.1 功能完整性

- [ ] 新产品目录结构完整
- [ ] 所有必需文件已迁移
- [ ] CO₂捕获模块工作正常
- [ ] 碳排放计算模块工作正常
- [ ] 优化模型能成功求解

### 9.2 结果合理性

- [ ] 碳排放低于传统航煤80gCO₂e/MJ
- [ ] 成本结构合理（氢气成本>50%，CO₂成本<20%）
- [ ] 供应链方案可行

### 9.3 代码质量

- [ ] 所有单元测试通过
- [ ] 代码符合PEP8规范
- [ ] 文档完整清晰
- [ ] 无明显性能问题
- [ ] 每完成一个阶段的工作，就要commit一下修改后的代码

---

## 十、待确认事项

1. **CO₂捕获源范围确认**：
   - 仅考虑燃煤、LNG、石油三类？
   - 是否包含钢铁、水泥等工业源？

2. **时间尺度确认**：
   - 是否保持周级需求+小时级生产？

3. **地理范围确认**：
   - 京津冀地区 or 全国？

4. **GraphHopper使用确认**：
   - CO₂运输是否使用路径规划？

5. **参数精度要求**：
   - 工艺参数精度要求到小数点后几位？

6. **甲醇中间体处理**：
   - 甲醇是否需要单独的运输决策变量？
   - 还是只在生产地点进行转化？

---

**PRD文档结束**

---

## 附录：重要代码片段示例

### A.1 CO₂捕获量计算示例

```python
def _calculate_coal_capture(self, plant: pd.Series, week: int) -> float:
    """计算燃煤电厂CO₂捕获量"""
    capacity_mw = plant.get('capacity_mw', 600)  # 默认600MW
    hours_per_week = 168
    capacity_factor = 0.70  # 70%运行率

    # 发电量
    electricity_mwh = capacity_mw * hours_per_week * capacity_factor

    # CO₂排放
    emission_factor = 0.95  # tCO₂/MWh
    co2_emission_ton = electricity_mwh * emission_factor

    # CO₂捕获
    capture_rate = 0.85  # 85%捕获率
    co2_capture_ton = co2_emission_ton * capture_rate

    return co2_capture_ton
```

### A.2 两步法工艺约束示例

```python
# 第一步：H₂ + CO₂ → 甲醇
for j in saf_locations:
    for t in hours:
        # 甲醇生产需要的氢气
        h2_for_methanol = methanol_production[j,t] * 0.154  # kg H₂/kg 甲醇
        model.addConstr(
            gp.quicksum(h2_supply[i,j,t] for i in h2_sources) >= h2_for_methanol
        )

        # 甲醇生产需要的CO₂
        co2_for_methanol = methanol_production[j,t] * 2.75  # kg CO₂/kg 甲醇
        model.addConstr(
            gp.quicksum(co2_supply[c,j,t] for c in co2_sources) >= co2_for_methanol
        )

# 第二步：甲醇 → SAF
for j in saf_locations:
    for t in hours:
        methanol_for_saf = saf_production[j,'methanol_mtj_two_step',t] * 1.3
        model.addConstr(
            methanol_inventory[j,t] >= methanol_for_saf
        )
```

---

**文档版本**：v2.0
**最后更新**：2025-10-13
**作者**：Claude Code
**状态**：待审阅
