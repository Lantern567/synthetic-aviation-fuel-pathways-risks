# 绿氢+CO₂制SAF供应链优化器 - 用户手册

**版本**: v2.0.0
**更新日期**: 2025-10-14
**作者**: 绿色甲醇港口运输研究组

---

## 目录

1. [快速开始](#快速开始)
2. [安装指南](#安装指南)
3. [数据准备](#数据准备)
4. [配置说明](#配置说明)
5. [使用示例](#使用示例)
6. [结果解读](#结果解读)
7. [高级功能](#高级功能)
8. [常见问题](#常见问题)
9. [性能优化](#性能优化)
10. [故障排除](#故障排除)

---

## 快速开始

### 最简示例 (3步运行)

```python
from core import GreenHydrogenSupplyChainOptimizer

# 1. 创建优化器
optimizer = GreenHydrogenSupplyChainOptimizer(
    time_horizon_weeks=1,              # 优化1周
    use_graphhopper_routing=False      # 关闭GraphHopper以加快测试
)

# 2. 加载数据
optimizer.load_data_from_excel(
    airport_excel_path="path/to/airport_data.xlsx",
    renewable_data=renewable_df  # pandas DataFrame
)

# 3. 运行优化并获取结果
optimizer.optimize()
results = optimizer.get_optimization_results()

print(f"总成本: {results['total_cost']:,.2f} 元")
print(f"SAF产量: {results['total_saf_production']:,.2f} kg")
```

---

## 安装指南

### 系统要求

- **操作系统**: Windows 10+, Linux, macOS
- **Python**: 3.12+ (推荐使用3.12)
- **内存**: 最少8GB (推荐16GB+用于大规模优化)
- **磁盘空间**: 5GB (包含OSM地图数据)

### 步骤1: 创建Conda环境

```bash
# 创建Python 3.12环境
conda create -n green_h2_saf python=3.12
conda activate green_h2_saf
```

### 步骤2: 安装Python依赖

```bash
# 进入项目目录
cd products/supply_chain_optimization/green_hydrogen_supply_chain_optimization

# 安装依赖包
pip install -r requirements.txt
```

### 步骤3: 安装Gurobi优化器

```bash
# 安装Gurobi
conda install -c gurobi gurobi

# 激活许可证 (需要先在Gurobi官网注册并获取许可证密钥)
grbgetkey YOUR_LICENSE_KEY
```

**Gurobi许可证说明**:
- 学术用户: 免费许可证 (需要.edu邮箱注册)
- 商业用户: 需要购买商业许可证
- 试用许可证: 30天免费试用

### 步骤4: (可选) 下载OSM地图数据

如果需要使用GraphHopper进行真实路网路径规划:

```bash
# 下载中国OSM地图数据 (约2GB)
wget https://download.geofabrik.de/asia/china-latest.osm.pbf \
     -P data/

# 或使用浏览器下载后移动到 data/ 目录
```

### 步骤5: 验证安装

```python
# 测试导入
from core import GreenHydrogenSupplyChainOptimizer
print("安装成功!")
```

---

## 数据准备

### 必需数据文件

#### 1. 机场需求数据 (Excel格式)

**文件路径**: 在配置文件中指定
**必需字段**:
- `机场名称` 或 `Airport Name`: 机场名称
- `IATA代码` 或 `IATA Code`: 三字母代码 (如PEK, SHA)
- `纬度` 或 `Latitude`: 纬度坐标
- `经度` 或 `Longitude`: 经度坐标
- `SAF需求量_kg` 或 `SAF Demand`: 周需求量(kg)

**示例数据**:
```
机场名称,IATA代码,纬度,经度,SAF需求量_kg
北京首都国际机场,PEK,40.0801,116.5846,50000
上海浦东国际机场,PVG,31.1434,121.8052,45000
广州白云国际机场,CAN,23.3924,113.2988,40000
```

#### 2. 可再生能源数据 (DataFrame格式)

**必需列**:
- `location_id`: 位置标识符
- `hour`: 小时编号 (0 到 总小时数-1)
- `wind_capacity_kw`: 风电装机容量 (kW)
- `solar_capacity_kw`: 光伏装机容量 (kW)
- `wind_generation_kwh`: 风电发电量 (kWh)
- `solar_generation_kwh`: 光伏发电量 (kWh)

**示例数据**:
```python
import pandas as pd

renewable_data = pd.DataFrame({
    'location_id': ['Beijing'] * 168,
    'hour': range(168),  # 1周 = 168小时
    'wind_capacity_kw': [5000] * 168,
    'solar_capacity_kw': [3000] * 168,
    'wind_generation_kwh': [...],  # 小时级风电发电量
    'solar_generation_kwh': [...]  # 小时级光伏发电量
})
```

#### 3. CO₂捕获源数据 (自动生成)

**文件路径**: `products/gis_energy_mapping/gis_data_scraper/scraped_gis_data/`

**必需文件**:
- `coal_power_plants.csv`: 煤电厂数据
- `gas_power_plants.csv`: 气电厂数据
- `oil_refineries.csv`: 炼油厂数据

**如果文件不存在**: 优化器会自动运行`CO2CaptureCalculator`生成数据

---

## 配置说明

### 配置文件路径

`shared/data/GreenHydrogenSupplyChainOptimizer_config.yaml`

### 主要配置段落

#### 1. 基础参数 (`basic_parameters`)

```yaml
basic_parameters:
  time_horizon_weeks: 1              # 优化时间范围(周)
  hours_per_week: 168                # 每周小时数 (固定)
  use_graphhopper_routing: true      # 是否使用GraphHopper路径规划
  max_transport_distance_km: 1000.0  # 最大运输距离(km)

  # GraphHopper设置
  graphhopper_host: "localhost"      # GraphHopper服务器地址
  graphhopper_port: 8989             # GraphHopper端口

  # 缓存设置
  cache_base_dir: "shared/data/cache"  # 缓存根目录
```

**参数说明**:
- `time_horizon_weeks`: 建议从1开始测试，大问题可设为4-12周
- `use_graphhopper_routing`:
  - `true`: 使用真实路网距离，更精确但需要OSM数据和GraphHopper服务器
  - `false`: 使用直线距离 * 1.3折算，速度快但不够精确

#### 2. CO₂参数 (`co2_parameters`)

```yaml
co2_parameters:
  # 捕获源参数
  capture_sources:
    coal_power_capture_rate: 0.85     # 煤电厂捕获率 (85%)
    lng_power_capture_rate: 0.90      # 气电厂捕获率 (90%)
    oil_refinery_capture_rate: 0.80   # 炼油厂捕获率 (80%)
    max_capture_distance_km: 1000.0   # 最大捕获距离(km)

  # 运输参数
  transport:
    # 管道运输成本函数 (分段线性)
    pipeline_transport_cost_function:
      function_type: piecewise_linear
      data_points:  # [距离(km), 成本(元/吨/100km)]
        - [25, 12.0]
        - [50, 8.5]
        - [100, 5.0]
        - [200, 3.5]
        - [500, 2.5]
        - [1000, 2.0]

    # 罐车运输成本
    truck_transport_cost_per_ton_km: 0.50  # 元/吨/km
```

#### 3. 氢气参数 (`hydrogen_parameters`)

```yaml
hydrogen_parameters:
  # 电解水制氢
  electrolysis_efficiency: 0.65       # 电解效率
  electrolysis_energy_consumption: 55.0  # kWh/kg H₂

  # 管道运输
  pipeline_capacity_kg_per_hour: 1000.0  # kg/h
  pipeline_transport_cost: 0.30       # 元/kg/km

  # 罐车运输
  truck_capacity_kg: 500.0            # kg/车
  truck_transport_cost: 0.50          # 元/kg/km
```

#### 4. 技术参数 (`technologies`)

```yaml
technologies:
  methanol_mtj_two_step:
    name: "甲醇MTJ两步法"
    description: "H₂+CO₂→甲醇→SAF"

    # 物料消耗比 (相对于SAF)
    h2_consumption_ratio: 0.20        # kg H₂ / kg SAF
    co2_consumption_ratio: 3.5        # kg CO₂ / kg SAF
    methanol_intermediate_ratio: 1.3  # kg 甲醇 / kg SAF
    methanol_to_saf_ratio: 0.77       # kg SAF / kg 甲醇

    # 效率参数
    efficiency: 0.70                   # 总体能量效率

    # 成本参数
    methanol_production_cost_per_kg: 5.0   # 元/kg 甲醇
    saf_conversion_cost_per_kg: 8.0        # 元/kg SAF

    # 设施参数
    suitable_locations: ["city", "industrial_zone"]
    min_capacity_kg_per_hour: 100.0
    max_capacity_kg_per_hour: 5000.0
```

**关键参数理解**:
- `h2_consumption_ratio = 0.20`: 生产1 kg SAF需要0.20 kg H₂
- `co2_consumption_ratio = 3.5`: 生产1 kg SAF需要3.5 kg CO₂
- `methanol_intermediate_ratio = 1.3`: 中间产物，生产1 kg SAF需要1.3 kg甲醇
- `methanol_to_saf_ratio = 0.77`: 1 kg甲醇可转化为0.77 kg SAF (倒数1.3)

#### 5. 求解器参数 (`solver_parameters`)

```yaml
solver_parameters:
  time_limit: 3600           # 求解时间限制(秒), 默认1小时
  mip_gap: 0.01              # MIP间隙, 0.01 = 1%最优性
  threads: 0                 # 线程数, 0=自动
  method: -1                 # 求解方法, -1=自动选择
  presolve: -1               # 预处理, -1=自动
  heuristics: 0.05           # 启发式时间比例
```

**参数调优建议**:
- 快速测试: `time_limit=300, mip_gap=0.05` (5分钟, 5%精度)
- 标准求解: `time_limit=3600, mip_gap=0.01` (1小时, 1%精度)
- 精确求解: `time_limit=14400, mip_gap=0.001` (4小时, 0.1%精度)

---

## 使用示例

### 示例1: 基础优化 (单周, 无GraphHopper)

```python
from core import GreenHydrogenSupplyChainOptimizer
import pandas as pd

# 创建优化器
optimizer = GreenHydrogenSupplyChainOptimizer(
    time_horizon_weeks=1,
    use_graphhopper_routing=False
)

# 加载数据
optimizer.load_data_from_excel(
    airport_excel_path="data/airports.xlsx",
    renewable_data=renewable_df
)

# 运行优化
optimizer.optimize()

# 获取结果
results = optimizer.get_optimization_results()
print(f"优化完成!")
print(f"  总成本: {results['total_cost']:,.2f} 元")
print(f"  SAF产量: {results['total_saf_production']:,.2f} kg")
print(f"  H₂消耗: {results['total_h2_consumption']:,.2f} kg")
print(f"  CO₂消耗: {results['total_co2_consumption']:,.2f} kg")
```

### 示例2: 多周优化 (带GraphHopper)

```python
optimizer = GreenHydrogenSupplyChainOptimizer(
    time_horizon_weeks=4,           # 优化4周
    use_graphhopper_routing=True,   # 启用真实路网
    solver_time_limit=7200,         # 2小时时间限制
    solver_mip_gap=0.02             # 2%精度
)

optimizer.load_data_from_excel(
    airport_excel_path="data/airports.xlsx",
    renewable_data=renewable_df
)

optimizer.optimize()
results = optimizer.get_optimization_results()
```

### 示例3: 自定义配置文件

```python
optimizer = GreenHydrogenSupplyChainOptimizer(
    config_path="/path/to/custom_config.yaml",
    time_horizon_weeks=2
)

optimizer.load_data_from_excel(
    airport_excel_path="data/airports.xlsx",
    renewable_data=renewable_df
)

optimizer.optimize()
```

### 示例4: 获取详细结果

```python
# 运行优化
optimizer.optimize()

# 获取总体结果
results = optimizer.get_optimization_results()

# 获取详细结果
co2_supply = optimizer.get_co2_supply_plan()          # CO₂供应计划
h2_transport = optimizer.get_hydrogen_transport_plan()  # H₂运输计划
methanol_prod = optimizer.get_methanol_production_schedule()  # 甲醇生产
saf_prod = optimizer.get_saf_production_schedule()    # SAF生产
carbon_report = optimizer.get_carbon_emission_report()  # 碳排放报告
```

### 示例5: 敏感性分析

```python
# 测试不同H₂价格对总成本的影响
h2_prices = [10, 15, 20, 25, 30]  # 元/kg
results_list = []

for price in h2_prices:
    # 创建优化器并覆盖H₂价格参数
    optimizer = GreenHydrogenSupplyChainOptimizer(
        time_horizon_weeks=1,
        h2_production_cost=price  # 覆盖默认H₂价格
    )

    optimizer.load_data_from_excel(
        airport_excel_path="data/airports.xlsx",
        renewable_data=renewable_df
    )

    optimizer.optimize()
    results = optimizer.get_optimization_results()

    results_list.append({
        'h2_price': price,
        'total_cost': results['total_cost'],
        'saf_production': results['total_saf_production']
    })

# 绘制敏感性曲线
import matplotlib.pyplot as plt
plt.figure(figsize=(10, 6))
plt.plot([r['h2_price'] for r in results_list],
         [r['total_cost'] for r in results_list],
         marker='o')
plt.xlabel('H₂价格 (元/kg)')
plt.ylabel('总成本 (元)')
plt.title('H₂价格敏感性分析')
plt.grid(True)
plt.savefig('h2_price_sensitivity.png', dpi=300)
```

---

## 结果解读

### 输出文件结构

```
results/
├── tables/                          # CSV表格文件
│   ├── optimization_summary_20251014_153045.csv      # 优化汇总
│   ├── facility_decisions_20251014_153045.csv        # 设施决策
│   ├── co2_supply_plan_20251014_153045.csv          # CO₂供应
│   ├── hydrogen_supply_plan_20251014_153045.csv     # H₂供应
│   ├── methanol_production_20251014_153045.csv      # 甲醇生产
│   ├── saf_production_plan_20251014_153045.csv      # SAF生产
│   └── carbon_emission_report_20251014_153045.csv   # 碳排放
│
├── figures/                         # 可视化图表
│   ├── cost_breakdown_20251014_153045.png           # 成本分解
│   ├── carbon_comparison_20251014_153045.png        # 碳排放对比
│   ├── transport_routes_co2_20251014_153045.html    # CO₂运输路径
│   └── transport_routes_h2_20251014_153045.html     # H₂运输路径
│
├── reports/                         # 分析报告
│   └── optimization_report_20251014_153045.md
│
└── logs/                            # 运行日志
    └── ng_supply_chain_20251014.log
```

### 关键结果指标

#### 1. 优化汇总 (`optimization_summary.csv`)

| 指标 | 说明 | 单位 |
|------|------|------|
| total_cost | 总成本 | 元 |
| h2_production_cost | H₂生产成本 | 元 |
| co2_capture_cost | CO₂捕获成本 | 元 |
| co2_transport_cost | CO₂运输成本 | 元 |
| h2_transport_cost | H₂运输成本 | 元 |
| methanol_production_cost | 甲醇生产成本 | 元 |
| saf_production_cost | SAF生产成本 | 元 |
| facility_investment_cost | 设施投资成本 | 元 |
| total_saf_production | SAF总产量 | kg |
| total_h2_consumption | H₂总消耗 | kg |
| total_co2_consumption | CO₂总消耗 | kg |
| total_carbon_emission | 总碳排放 | kg CO₂e |

#### 2. 设施决策 (`facility_decisions.csv`)

显示哪些位置建设了甲醇厂和SAF厂:

| 字段 | 说明 |
|------|------|
| location_id | 位置ID |
| technology | 技术类型 (methanol_mtj_two_step) |
| build_decision | 是否建设 (0/1) |
| capacity_kg_per_hour | 设施容量 (kg/h) |
| investment_cost | 投资成本 (元) |

#### 3. CO₂供应计划 (`co2_supply_plan.csv`)

每周CO₂运输详情:

| 字段 | 说明 |
|------|------|
| week | 周编号 |
| co2_source_id | CO₂捕获源ID |
| destination_location | 目的地位置 |
| pipeline_transport_kg | 管道运输量 (kg) |
| truck_transport_kg | 罐车运输量 (kg) |
| total_transport_kg | 总运输量 (kg) |
| transport_distance_km | 运输距离 (km) |

#### 4. 碳排放报告 (`carbon_emission_report.csv`)

全生命周期碳排放分析:

| 字段 | 说明 |
|------|------|
| stage | 阶段 |
| emission_kg_co2e | 碳排放量 (kg CO₂e) |
| emission_intensity | 碳强度 (kg CO₂e/kg SAF) |
| percentage | 占比 (%) |

**碳排放分解**:
- H₂生产碳排放 (电力碳排放)
- CO₂捕获能耗碳排放
- CO₂运输碳排放
- H₂运输碳排放
- 甲醇生产碳排放
- SAF转化碳排放

---

## 高级功能

### 1. 氢气厂聚类优化

当氢气生产点数量过多时，使用聚类减少决策变量:

```python
optimizer = GreenHydrogenSupplyChainOptimizer(
    time_horizon_weeks=1,
    enable_hydrogen_clustering=True,   # 启用聚类
    max_hydrogen_clusters=50          # 最大聚类数
)
```

**聚类算法**:
- 使用K-means聚类
- 考虑地理位置和生产能力
- 自动选择最优聚类数

### 2. 管道路径优化

使用真实管道网络进行距离计算:

```python
optimizer = GreenHydrogenSupplyChainOptimizer(
    time_horizon_weeks=1,
    use_pipeline_network=True,        # 使用管道网络
    pipeline_data_path="data/pipelines.csv"
)
```

### 3. 多情景分析

批量运行不同情景:

```python
scenarios = [
    {'name': '基准情景', 'h2_price': 20, 'co2_price': 100},
    {'name': '低H₂价格', 'h2_price': 15, 'co2_price': 100},
    {'name': '高CO₂价格', 'h2_price': 20, 'co2_price': 150},
]

for scenario in scenarios:
    print(f"\n运行情景: {scenario['name']}")

    optimizer = GreenHydrogenSupplyChainOptimizer(
        time_horizon_weeks=1,
        h2_production_cost=scenario['h2_price'],
        co2_capture_cost=scenario['co2_price']
    )

    optimizer.load_data_from_excel(
        airport_excel_path="data/airports.xlsx",
        renewable_data=renewable_df
    )

    optimizer.optimize()
    results = optimizer.get_optimization_results()

    print(f"  总成本: {results['total_cost']:,.2f} 元")
    print(f"  SAF产量: {results['total_saf_production']:,.2f} kg")
```

### 4. 自定义约束

添加额外的业务约束:

```python
# 创建优化器并加载数据
optimizer = GreenHydrogenSupplyChainOptimizer(time_horizon_weeks=1)
optimizer.load_data_from_excel(...)

# 访问Gurobi模型对象
model = optimizer.model

# 添加自定义约束: 特定位置最小SAF产量
location_id = "Beijing"
tech = "methanol_mtj_two_step"
min_production = 10000  # kg

total_production = gp.quicksum(
    optimizer.production_vars[(location_id, tech, hour)]
    for hour in range(optimizer.total_hours)
    if (location_id, tech, hour) in optimizer.production_vars
)

model.addConstr(
    total_production >= min_production,
    name=f"min_production_{location_id}"
)

# 运行优化
optimizer.optimize()
```

---

## 常见问题

### Q1: Gurobi许可证错误

**错误信息**:
```
GurobiError: Model too large for limited license
```

**解决方法**:
- 检查许可证类型 (学术版有1000变量限制)
- 减少时间范围 (`time_horizon_weeks=1`)
- 启用聚类 (`enable_hydrogen_clustering=True`)
- 升级到完整许可证

### Q2: GraphHopper连接失败

**错误信息**:
```
ConnectionError: GraphHopper service not available
```

**解决方法**:
1. 方法1 (推荐): 关闭GraphHopper
   ```python
   optimizer = GreenHydrogenSupplyChainOptimizer(
       use_graphhopper_routing=False
   )
   ```

2. 方法2: 启动GraphHopper服务器
   ```bash
   # 下载GraphHopper
   wget https://graphhopper.com/public/releases/graphhopper-web-5.3.jar

   # 启动服务 (需要OSM数据)
   java -jar graphhopper-web-5.3.jar \
        -i data/china-latest.osm.pbf \
        -o graphhopper-data
   ```

### Q3: 内存不足

**错误信息**:
```
MemoryError: Unable to allocate array
```

**解决方法**:
- 减少时间范围
- 启用聚类
- 增加系统内存
- 使用64位Python

### Q4: 模型不可行 (Infeasible)

**错误信息**:
```
Optimization terminated with status: INFEASIBLE
```

**诊断方法**:
```python
# 计算不可行子系统 (IIS)
if optimizer.model.Status == 3:  # INFEASIBLE
    optimizer.model.computeIIS()
    optimizer.model.write("infeasible_model.ilp")
    print("不可行子系统已保存到 infeasible_model.ilp")
```

**常见原因**:
- SAF需求量超过可供应能力
- 运输距离超过限制
- 可再生能源不足

### Q5: 求解时间过长

**现象**: 优化运行超过1小时仍未完成

**解决方法**:
```python
# 1. 增大MIP gap (降低精度要求)
optimizer = GreenHydrogenSupplyChainOptimizer(
    solver_mip_gap=0.05  # 5%精度 (默认1%)
)

# 2. 设置时间限制
optimizer = GreenHydrogenSupplyChainOptimizer(
    solver_time_limit=600  # 10分钟
)

# 3. 启用启发式
optimizer = GreenHydrogenSupplyChainOptimizer(
    solver_heuristics=0.1  # 10%时间用于启发式
)
```

---

## 性能优化

### 模型规模估算

| 时间范围 | 决策变量数 | 约束数 | 估计求解时间 |
|---------|----------|-------|------------|
| 1周     | ~5,000   | ~10,000 | 5-30分钟 |
| 4周     | ~20,000  | ~40,000 | 30分钟-2小时 |
| 12周    | ~60,000  | ~120,000 | 2-8小时 |

### 性能优化策略

#### 1. 分阶段求解

```python
# 第一阶段: 粗求解 (快速得到可行解)
optimizer1 = GreenHydrogenSupplyChainOptimizer(
    time_horizon_weeks=1,
    solver_mip_gap=0.10,      # 10%精度
    solver_time_limit=300     # 5分钟
)
optimizer1.load_data_from_excel(...)
optimizer1.optimize()

# 获取设施位置决策
facility_decisions = optimizer1.get_facility_decisions()

# 第二阶段: 固定设施位置，精细求解
optimizer2 = GreenHydrogenSupplyChainOptimizer(
    time_horizon_weeks=4,     # 扩展到4周
    solver_mip_gap=0.01,      # 1%精度
    solver_time_limit=3600    # 1小时
)
optimizer2.load_data_from_excel(...)

# 固定设施决策
for loc, tech in facility_decisions:
    optimizer2.facility_vars[(loc, tech)].LB = facility_decisions[(loc, tech)]
    optimizer2.facility_vars[(loc, tech)].UB = facility_decisions[(loc, tech)]

optimizer2.optimize()
```

#### 2. 并行计算

```python
# 启用多线程
optimizer = GreenHydrogenSupplyChainOptimizer(
    solver_threads=8  # 使用8线程 (0=自动)
)
```

#### 3. 预处理优化

```python
# 启用激进预处理
optimizer = GreenHydrogenSupplyChainOptimizer(
    solver_presolve=2  # 2=激进预处理
)
```

---

## 故障排除

### 日志分析

查看运行日志:

```bash
# 查看最新日志
tail -f results/logs/ng_supply_chain_20251014.log

# 搜索错误信息
grep "ERROR" results/logs/*.log

# 搜索警告信息
grep "WARNING" results/logs/*.log
```

### 调试模式

启用详细日志:

```python
import logging

# 设置日志级别为DEBUG
logging.getLogger().setLevel(logging.DEBUG)

# 创建优化器
optimizer = GreenHydrogenSupplyChainOptimizer(time_horizon_weeks=1)
```

### 数据验证

```python
# 检查数据完整性
optimizer = GreenHydrogenSupplyChainOptimizer()
optimizer.load_data_from_excel(...)

# 验证数据
print(f"机场数量: {len(optimizer.airports)}")
print(f"氢气厂数量: {len(optimizer.locations)}")
print(f"CO₂捕获源数量: {len(optimizer.co2_capture_sources)}")
print(f"可再生能源数据行数: {len(renewable_df)}")
```

### 获取技术支持

1. 查阅文档: `README.md`, `USER_MANUAL.md`
2. 查看示例: `tests/` 目录下的测试脚本
3. 提交Issue: GitHub项目页面
4. 联系作者: [联系信息]

---

## 附录

### A. 配置参数完整列表

见 `shared/data/GreenHydrogenSupplyChainOptimizer_config.yaml`

### B. 输出字段说明

见 `README.md` 第277-292行

### C. 技术参考文献

- PRD v2.0: 产品需求文档
- IEA Hydrogen Report 2024: 国际能源署氢能报告
- IRENA Green Hydrogen Cost 2024: 国际可再生能源署绿氢成本报告
- Global CCS Institute Report: 全球碳捕获与封存研究所报告
- Haldor Topsoe MTJ Technology: 甲醇制航空燃料技术

### D. 版本历史

- **v2.0.0** (2025-10-14): 绿氢+CO₂两步法工艺
  - 添加CO₂捕获模块
  - 添加甲醇中间产物
  - 添加时间尺度匹配
  - 完全替代天然气路线

- **v1.0.0** (2025-09): 天然气单步法工艺 (已废弃)

---

**文档更新**: 2025-10-14
**适用版本**: v2.0.0+
**维护者**: 绿色甲醇港口运输研究组
