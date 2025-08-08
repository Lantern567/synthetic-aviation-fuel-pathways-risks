# 天然气基供应链优化模型算例

基于《多供应链优化建模方法论》中天然气基供应链的Gurobi优化模型实现，特别处理了时间尺度匹配问题。

## 项目概述

本算例实现了天然气基航煤供应链的完整优化模型，使用真实数据和现实场景，包含：

- **真实数据源**：太阳能发电站数据、中国主要机场、天然气管道网络、LNG接收站
- **数学模型**：基于文档中的建模方法论，添加时间尺度匹配约束
- **优化算法**：Gurobi混合整数线性规划求解器
- **多种技术路径**：管道直供、机场集成、LNG接收站等
- **时间尺度匹配**：解决生产计划(1小时)与机场需求(1周)的时间粒度差异

## 时间尺度匹配设计 ⭐

### 问题背景
- **生产侧**：基于太阳能发电的制氢生产，数据粒度为1小时
- **需求侧**：机场燃料定制计划，以周为单位进行规划
- **挑战**：如何在优化模型中协调不同时间尺度的决策变量

### 解决方案
通过引入库存变量实现时间尺度桥接：

```
小时级生产 → 累积库存 → 周级运输 → 机场周需求
```

### 数学建模
```python
# 时间尺度匹配约束
for week w in range(time_horizon_weeks):
    week_start_hour = w * 168  # 周起始小时
    week_end_hour = (w + 1) * 168  # 周结束小时
    
    # 该周总生产量
    weekly_production = Σ(生产变量[location, tech, hour] 
                         for hour in [week_start_hour, week_end_hour))
    
    # 该周库存变化
    inventory_change = 库存[week_end_hour] - 库存[week_start_hour]
    
    # 约束：周运输量 ≤ 周生产量 - 库存增量
    周运输量[location, airport, week] ≤ weekly_production - inventory_change

# 库存平衡约束(每小时)
for hour h in range(total_hours):
    库存[h+1] = 库存[h] + Σ(生产量[h]) - 出库量[h]
```

## 目录结构

```
natural_gas_supply_chain_optimization/
├── main.py                     # 主运行脚本
├── README.md                   # 项目说明文档
├── requirements.txt            # 依赖包列表
├── data/                       # 数据文件夹
│   ├── solar_generation_data.csv      # 太阳能发电数据
│   ├── airport_data.csv               # 机场需求数据
│   ├── pipeline_data.csv              # 天然气管道数据
│   ├── lng_terminal_data.csv          # LNG接收站数据
│   ├── price_scenarios.csv            # 价格情景数据
│   └── technology_parameters.json     # 技术参数
├── src/                        # 源代码文件夹
│   ├── data_loader.py                 # 数据加载模块
│   └── gurobi_optimizer.py            # Gurobi优化模型
└── results/                    # 结果输出文件夹
    ├── optimization_results_*.json    # 详细优化结果
    ├── summary_report_*.md            # 结果摘要报告
    └── mock_results_*.json            # 模拟结果（当Gurobi不可用时）
```

## 主要特征

### 1. 真实数据应用

#### 太阳能发电数据
- 来源：项目中的`results/solar_generation/`文件夹
- 包含：50个代表性太阳能发电站的真实发电数据
- 数据项：发电站名称、位置坐标、装机容量、逐小时发电量

#### 机场数据
- 8个中国主要机场的真实坐标
- 包括：北京首都、上海浦东、广州白云、成都双流等
- 年需求量基于实际航空燃料消耗估算

#### 天然气基础设施
- **管道网络**：西气东输一线、二线、三线等6条主要管道
- **LNG接收站**：大连、天津、青岛、上海等7个沿海接收站
- **价格模型**：考虑季节性波动和区域差异

### 2. 数学模型实现

#### 决策变量
```
- NG_pipeline[i,t]: 天然气管道采购量（立方米/月）
- NG_lng[i,t]: LNG采购量（立方米/月）
- H2_solar[i,t]: 太阳能制氢量（kg/月）
- H2_direct[i,t]: 氢气直接采购量（kg/月）
- X_production[i,j,t]: 航煤生产量（吨/月）
- W_facility[i,j]: 设施建设决策（0-1变量）
- Y_transport[i,k,m,t]: 运输量（吨/月）
```

#### 约束条件
1. **需求满足约束**：每个机场的航煤需求必须满足
2. **供应能力约束**：天然气管道、LNG接收站容量限制
3. **技术约束**：原料消耗比例、生产效率
4. **运输约束**：产品运输平衡
5. **逻辑约束**：技术与位置匹配

#### 目标函数
```
Min Z = 原料成本 + 生产成本 + 运输成本 + 设施建设成本
```

### 3. 技术路径

#### 五种运输模式
1. **管道直供**：天然气管道→氢气产地→制备航煤
2. **机场集成**：原料→机场→集中制备
3. **港口进口**：LNG接收站→制备航煤
4. **港口转运**：LNG→氢气产地→制备航煤
5. **综合供应**：多种原料→机场→制备航煤

#### 技术参数（基于真实工程数据）
```json
{
  "pipeline_direct_conversion": {
    "capex_yuan_per_ton_year": 9500,
    "opex_yuan_per_ton": 2800,
    "efficiency": 0.82,
    "ng_consumption_ratio": 1.2,
    "h2_consumption_ratio": 0.3
  }
}
```

## 安装和运行

### 1. 环境要求
```bash
Python 3.8+
pandas >= 1.3.0
numpy >= 1.21.0
gurobipy >= 9.5.0  # Gurobi优化器（需要许可证）
```

### 2. 安装依赖
```bash
pip install -r requirements.txt
```

### 3. Gurobi许可证
- 学术用户：从[Gurobi官网](https://www.gurobi.com/academia/)获取免费许可证
- 商业用户：购买商业许可证
- 无许可证：程序会生成模拟结果

### 4. 运行算例
```bash
cd natural_gas_supply_chain_optimization
python main.py
```

## 结果分析

### 输出文件

1. **优化结果**（`optimization_results_*.json`）
   - 目标函数值（总成本）
   - 所有决策变量的最优值
   - 求解统计信息

2. **摘要报告**（`summary_report_*.md`）
   - 成本分解
   - 设施建设决策
   - 生产和运输方案

3. **模拟结果**（`mock_results_*.json`，当Gurobi不可用）
   - 基于经验的合理结果估算
   - 完整的成本结构分析

### 典型结果示例

```
总成本: 1,000,000,000 元
├── 原料成本: 500,000,000 元 (50%)
├── 生产成本: 200,000,000 元 (20%)
├── 运输成本: 100,000,000 元 (10%)
└── 设施成本: 200,000,000 元 (20%)

设施建设：
- 北京：管道直接转化技术
- 上海：LNG接收站转化技术
- 广州：机场集成转化技术
```

## 模型扩展

### 1. 不确定性分析
- 添加价格波动情景
- 需求不确定性建模
- 鲁棒优化方法

### 2. 多目标优化
- 成本最小化
- 碳排放最小化
- 供应安全性最大化

### 3. 动态规划
- 多年期投资决策
- 技术学习曲线
- 设施扩建策略

## 技术说明

### 距离计算
使用Haversine公式计算两点间的球面距离：
```python
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371  # 地球半径（公里）
    # ... Haversine公式实现
    return distance
```

### 数据预处理
- 太阳能数据：按省份选择代表性发电站
- 价格数据：考虑季节性波动（冬高夏低）
- 需求数据：年需求均匀分布到12个月

### 求解策略
- 时间限制：30分钟
- MIP间隙：5%
- 预处理：自动
- 启发式：开启

## 参考文献

1. 《多供应链优化建模方法论》- 项目内部文档
2. Gurobi Optimization Guide
3. 中国天然气发展报告
4. 民航燃料消费统计年鉴

## 联系信息

- 项目地址：绿色甲醇港口运输项目
- 技术支持：优化团队
- 最后更新：2025年7月22日

---

**注意**：本算例基于真实数据和工程参数，结果具有实际参考价值。模型可根据具体需求进行调整和扩展。

## 更新记录

- 2025-08-08
  - 修复重构版本在 `load_data()` 阶段计算平均距离时访问未初始化属性 (`mtj_locations`/`non_lng_mtj_locations`) 的问题。
  - 统一 `_calculate_average_distances()` 的实现，改为仅基于 `self.locations` 的类型筛选，避免依赖建模阶段产物。
  - 新增单元测试：`tests/test_average_distance_no_mtj_attribute.py`，验证在不启用 GraphHopper 的情况下，平均距离计算流程可稳定运行且无属性错误。