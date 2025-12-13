# 可持续航空燃料供应链网络优化：混合整数线性规划模型

---

## 摘要

本文针对可持续航空燃料（Sustainable Aviation Fuel, SAF）供应链网络优化问题，建立混合整数线性规划（Mixed-Integer Linear Programming, MILP）模型。模型综合考虑多种氢气生产路径、二氧化碳捕集技术及合成工艺路线，以供应链总成本最小化为目标，同时满足机场需求约束。模型通过库存管理机制解决可再生能源小时级波动性与周级需求之间的时间尺度匹配问题。

---

## 1 问题描述

### 1.1 网络拓扑结构

SAF供应链网络由四层节点构成：

1. **氢气供应层**：包括可再生能源电解制氢设施（风电/光伏）、工业副产氢源（钢铁厂/炼油厂）及天然气重整制氢设施
2. **二氧化碳供应层**：包括工业点源捕集设施（电厂/炼油厂）、直接空气捕集（DAC）设施及煤气化装置
3. **生产转化层**：SAF合成设施，采用甲醇制喷气燃料（MTJ）路径或费托直接合成（FT-DS）路径
4. **需求终端层**：具有SAF需求的机场节点

### 1.2 合成工艺路径

模型考虑两类主要合成路径：

- **甲醇制喷气燃料路径（Methanol-to-Jet, MTJ）**：氢气与二氧化碳经催化合成生成甲醇中间产物，再经甲醇转化工艺生产喷气燃料
- **费托直接合成路径（Fischer-Tropsch Direct Synthesis, FT-DS）**：氢气与二氧化碳经逆水煤气变换反应后，通过费托合成直接生产喷气燃料

---

## 2 符号系统

### 2.1 集合定义

| 符号 | 定义 |
|:----:|------|
| $\mathcal{I}$ | 氢气供应设施集合 |
| $\mathcal{I}^{elec} \subseteq \mathcal{I}$ | 电解制氢设施子集（风电/光伏） |
| $\mathcal{I}^{byp} \subseteq \mathcal{I}$ | 工业副产氢设施子集 |
| $\mathcal{I}^{steel} \subseteq \mathcal{I}^{byp}$ | 钢铁厂副产氢设施子集 |
| $\mathcal{I}^{refinery} \subseteq \mathcal{I}^{byp}$ | 炼油厂副产氢设施子集 |
| $\mathcal{I}^{ref} \subseteq \mathcal{I}$ | 天然气重整制氢设施子集 |
| $\mathcal{J}$ | 二氧化碳供应源集合 |
| $\mathcal{J}^{ind} \subseteq \mathcal{J}$ | 工业点源捕集子集（煤电厂/气电厂/炼油厂） |
| $\mathcal{J}^{dac} \subseteq \mathcal{J}$ | 直接空气捕集设施子集 |
| $\mathcal{J}^{gas} \subseteq \mathcal{J}$ | 煤气化CO₂设施子集 |
| $\mathcal{L}^{LNG}$ | LNG接收站/天然气供应点集合 |
| $\mathcal{K}$ | SAF生产设施候选位置集合 |
| $\mathcal{K}^{MTJ} \subseteq \mathcal{K}$ | 采用MTJ路径的设施子集 |
| $\mathcal{K}^{FT} \subseteq \mathcal{K}$ | 采用FT-DS路径的设施子集 |
| $\mathcal{A}$ | 机场（需求节点）集合 |
| $\mathcal{T}$ | 时段集合（亚小时粒度） |
| $\mathcal{W}$ | 规划周集合 |
| $\mathcal{M}$ | 运输方式集合 $\{管道, 槽车\}$ |
| $\mathcal{P}$ | 合成路径集合 $\{MTJ, FT\text{-}DS\}$ |

### 2.2 时间索引映射

| 符号 | 定义 |
|:----:|------|
| $w(t)$ | 时段$t$所属的周索引 |
| $\mathcal{T}_w$ | 第$w$周包含的时段集合 |
| $H_w$ | 每周时段数 |

### 2.3 参数定义

#### 2.3.1 供应参数

| 符号 | 定义 | 量纲 |
|:----:|------|:----:|
| $\bar{Q}^{H_2}_{i,t}$ | 设施$i$在时段$t$的最大产氢能力 | kg |
| $\bar{Q}^{steel}_{i,t}$ | 钢铁厂$i$在时段$t$的副产氢产量 | kg |
| $\bar{Q}^{refinery}_{i,t}$ | 炼油厂$i$在时段$t$的副产氢产量 | kg |
| $\gamma^{steel}_{avail}$ | 钢铁厂副产氢可外供比例 | - |
| $\gamma^{refinery}_{avail}$ | 炼油厂副产氢可外供比例 | - |
| $\bar{S}^{CO_2}_{j,w}$ | 碳源$j$在第$w$周的最大CO₂供给量 | kg |
| $\bar{S}^{NG}_{l,w}$ | LNG接收站$l$在第$w$周的天然气供给量 | m³ |
| $\gamma^{cap}_j$ | 碳源$j$的捕集效率 | - |
| $\eta^{elec}$ | 电解制氢单位能耗 | kWh/kg H₂ |
| $E^{dac}$ | DAC单位能耗 | kWh/kg CO₂ |
| $P_{i,t}$ | 站点$i$在时段$t$的可再生能源出力 | kW |
| $P^{avail}_{k,t}$ | 设施$k$在时段$t$的可用电力 | kW |

#### 2.3.2 转化参数

| 符号 | 定义 | 量纲 |
|:----:|------|:----:|
| $\alpha^{H_2}_p$ | 路径$p$的氢气消耗系数 | kg H₂/kg SAF |
| $\alpha^{CO_2}_p$ | 路径$p$的CO₂消耗系数 | kg CO₂/kg SAF |
| $\alpha^{MeOH}$ | MTJ路径甲醇需求系数 | kg MeOH/kg SAF |
| $\beta^{MeOH}$ | 甲醇转化效率 | kg SAF/kg MeOH |
| $\gamma^{coal}$ | 煤气化CO₂产生系数 | kg CO₂/kg coal |
| $\gamma^{ref}_{H_2}$ | 天然气重整制氢系数 | kg H₂/m³ NG |
| $\gamma^{ref}_{CO_2}$ | 天然气重整CO₂产生系数 | kg CO₂/m³ NG |

#### 2.3.3 成本参数

| 符号 | 定义 | 量纲 |
|:----:|------|:----:|
| $c^{H_2}_i$ | 设施$i$的单位制氢成本 | 元/kg |
| $c^{CO_2}_j$ | 碳源$j$的单位捕集成本 | 元/kg |
| $c^{trans}_{m}(d)$ | 运输方式$m$距离$d$的单位运输成本 | 元/kg |
| $c^{prod}_p$ | 路径$p$的单位生产成本 | 元/kg SAF |
| $c^{inv}$ | 单位库存持有成本 | 元/kg·期 |
| $c^{short}$ | 单位缺货惩罚成本 | 元/kg |
| $C^{fix}$ | 设施固定投资成本 | 元 |
| $C^{var}$ | 单位产能投资成本 | 元/(kg/h) |

#### 2.3.4 容量参数

| 符号 | 定义 | 量纲 |
|:----:|------|:----:|
| $\bar{Q}^{SAF}$ | SAF设施最大产能 | kg/h |
| $\underline{Q}^{SAF}$ | SAF设施最小产能 | kg/h |
| $\bar{Y}^m$ | 运输方式$m$的最大运力 | kg/期 |
| $\bar{I}$ | 最大库存容量 | kg |

#### 2.3.5 需求参数

| 符号 | 定义 | 量纲 |
|:----:|------|:----:|
| $D_{a,w}$ | 机场$a$在第$w$周的SAF需求量 | kg |

#### 2.3.6 距离参数

| 符号 | 定义 | 量纲 |
|:----:|------|:----:|
| $d_{i,k}$ | 氢源$i$至设施$k$的距离 | km |
| $d_{j,k}$ | 碳源$j$至设施$k$的距离 | km |
| $d_{k,a}$ | 设施$k$至机场$a$的距离 | km |

#### 2.3.7 经济参数

| 符号 | 定义 | 量纲 |
|:----:|------|:----:|
| $r$ | 贴现率 | - |
| $L$ | 项目寿命期 | 年 |
| $\tau$ | 单时段时长 | 3小时 |

### 2.4 决策变量

#### 2.4.1 连续变量

| 符号 | 定义 | 定义域 |
|:----:|------|:------:|
| $x^{H_2}_{i,t}$ | 设施$i$在时段$t$的产氢量 | $\mathbb{R}_+$ |
| $x^{CO_2}_{j,w}$ | 碳源$j$在第$w$周的CO₂供给量 | $\mathbb{R}_+$ |
| $x^{DAC}_{k,t}$ | 设施$k$在时段$t$的DAC捕集量 | $\mathbb{R}_+$ |
| $x^{NG}_{i,t}$ | 设施$i$在时段$t$的天然气消耗量 | $\mathbb{R}_+$ |
| $x^{coal}_{k,t}$ | 设施$k$在时段$t$的煤炭消耗量 | $\mathbb{R}_+$ |
| $x^{MeOH}_{k,t}$ | 设施$k$在时段$t$的甲醇产量 | $\mathbb{R}_+$ |
| $x^{MeOH,cons}_{k,t}$ | 设施$k$在时段$t$的甲醇消耗量 | $\mathbb{R}_+$ |
| $x^{SAF}_{k,t}$ | 设施$k$在时段$t$的SAF产量 | $\mathbb{R}_+$ |
| $y^{H_2,m}_{i,k,t}$ | 时段$t$经方式$m$从$i$至$k$的H₂运输量 | $\mathbb{R}_+$ |
| $y^{CO_2,m}_{j,k,w}$ | 第$w$周经方式$m$从$j$至$k$的CO₂运输量 | $\mathbb{R}_+$ |
| $y^{SAF}_{k,a,w}$ | 第$w$周从$k$至机场$a$的SAF配送量 | $\mathbb{R}_+$ |
| $I^{MeOH}_{k,t}$ | 设施$k$在时段$t$的甲醇库存量 | $\mathbb{R}_+$ |
| $I^{CO_2}_{k,t}$ | 设施$k$在时段$t$的CO₂库存量 | $\mathbb{R}_+$ |
| $Q_k$ | 设施$k$的建设产能 | $\mathbb{R}_+$ |
| $s_{a,w}$ | 机场$a$在第$w$周的缺货量 | $\mathbb{R}_+$ |

#### 2.4.2 二元变量

| 符号 | 定义 | 定义域 |
|:----:|------|:------:|
| $z_k$ | 是否在位置$k$建设SAF设施 | $\{0,1\}$ |
| $z^{pipe}_{i,k}$ | 是否建设氢源$i$至$k$的管道 | $\{0,1\}$ |
| $z^{pipe}_{j,k}$ | 是否建设碳源$j$至$k$的管道 | $\{0,1\}$ |

---

## 3 数学模型

### 3.1 目标函数

最小化供应链总成本：

$$\min Z = C_{H_2} + C_{CO_2} + C_{trans} + C_{prod} + C_{inv} + C_{fac} + C_{short}$$

各成本项定义如下：

**氢气生产成本：**
$$C_{H_2} = \sum_{t \in \mathcal{T}} \sum_{i \in \mathcal{I}} c^{H_2}_i \cdot x^{H_2}_{i,t}$$

**二氧化碳捕集成本：**
$$C_{CO_2} = \sum_{w \in \mathcal{W}} \sum_{j \in \mathcal{J}} c^{CO_2}_j \cdot x^{CO_2}_{j,w}$$

**运输成本：**
$$C_{trans} = \sum_{t,i,k,m} c^{trans}_m(d_{i,k}) \cdot y^{H_2,m}_{i,k,t} + \sum_{w,j,k,m} c^{trans}_m(d_{j,k}) \cdot y^{CO_2,m}_{j,k,w} + \sum_{w,k,a} c^{trans}(d_{k,a}) \cdot y^{SAF}_{k,a,w}$$

**生产成本：**
$$C_{prod} = \sum_{t \in \mathcal{T}} \sum_{k \in \mathcal{K}} \left( c^{MeOH} \cdot x^{MeOH}_{k,t} + c^{SAF} \cdot x^{SAF}_{k,t} \right)$$

**库存持有成本：**
$$C_{inv} = \sum_{t \in \mathcal{T}} \sum_{k \in \mathcal{K}} \left( c^{inv}_{MeOH} \cdot I^{MeOH}_{k,t} + c^{inv}_{CO_2} \cdot I^{CO_2}_{k,t} \right)$$

**设施投资成本（年化）：**
$$C_{fac} = CRF \cdot \sum_{k \in \mathcal{K}} \left( C^{fix} \cdot z_k + C^{var} \cdot Q_k \right) \cdot \frac{|\mathcal{W}|}{52}$$

其中资本回收系数为：
$$CRF = \frac{r(1+r)^L}{(1+r)^L - 1}$$

**缺货惩罚成本：**
$$C_{short} = \sum_{w \in \mathcal{W}} \sum_{a \in \mathcal{A}} c^{short} \cdot s_{a,w}$$

### 3.2 约束条件

#### 3.2.1 氢气供应约束

**电解制氢产能约束（可再生能源受限）：**
$$x^{H_2}_{i,t} \leq \frac{P_{i,t} \cdot \tau}{\eta^{elec}}, \quad \forall i \in \mathcal{I}^{elec}, t \in \mathcal{T}$$

**工业副产氢供应约束：**
$$x^{H_2}_{i,t} \leq \gamma^{avail}_i \cdot \bar{Q}^{byp}_{i,t}, \quad \forall i \in \mathcal{I}^{byp}, t \in \mathcal{T}$$

**天然气重整制氢约束：**
$$x^{H_2}_{i,t} = \gamma^{ref}_{H_2} \cdot x^{NG}_{i,t}, \quad \forall i \in \mathcal{I}^{ref}, t \in \mathcal{T}$$

**氢气产销平衡：**
$$x^{H_2}_{i,t} = \sum_{k \in \mathcal{K}} \sum_{m \in \mathcal{M}} y^{H_2,m}_{i,k,t}, \quad \forall i \in \mathcal{I}, t \in \mathcal{T}$$

#### 3.2.2 二氧化碳供应约束

**工业点源捕集约束：**
$$x^{CO_2}_{j,w} \leq \gamma^{cap}_j \cdot \bar{S}^{CO_2}_{j,w}, \quad \forall j \in \mathcal{J}^{ind}, w \in \mathcal{W}$$

**直接空气捕集约束（能源受限）：**
$$x^{DAC}_{k,t} \leq \frac{P^{avail}_{k,t} \cdot \tau}{E^{dac}}, \quad \forall k \in \mathcal{K}, t \in \mathcal{T}$$

**煤气化CO₂生成约束：**
$$x^{CO_2}_{k,t} = \gamma^{coal} \cdot x^{coal}_{k,t}, \quad \forall k \in \mathcal{K}^{gas}, t \in \mathcal{T}$$

**天然气重整CO₂生成约束：**
$$x^{CO_2}_{i,t} = \gamma^{ref}_{CO_2} \cdot x^{NG}_{i,t}, \quad \forall i \in \mathcal{I}^{ref}, t \in \mathcal{T}$$

**CO₂产销平衡：**
$$x^{CO_2}_{j,w} = \sum_{k \in \mathcal{K}} \sum_{m \in \mathcal{M}} y^{CO_2,m}_{j,k,w}, \quad \forall j \in \mathcal{J}, w \in \mathcal{W}$$

#### 3.2.3 MTJ路径生产约束

**甲醇合成氢气平衡：**
$$\alpha^{H_2 \to MeOH} \cdot x^{MeOH}_{k,t} \leq \sum_{i \in \mathcal{I}} \sum_{m \in \mathcal{M}} y^{H_2,m}_{i,k,t}, \quad \forall k \in \mathcal{K}^{MTJ}, t \in \mathcal{T}$$

**甲醇合成CO₂平衡：**
$$\alpha^{CO_2 \to MeOH} \cdot x^{MeOH}_{k,t} \leq I^{CO_2}_{k,t-1} + \frac{1}{H_w} \sum_{j \in \mathcal{J}} \sum_{m \in \mathcal{M}} y^{CO_2,m}_{j,k,w(t)}, \quad \forall k \in \mathcal{K}^{MTJ}, t \in \mathcal{T}$$

**甲醇转化约束：**
$$x^{SAF}_{k,t} = \beta^{MeOH} \cdot x^{MeOH,cons}_{k,t}, \quad \forall k \in \mathcal{K}^{MTJ}, t \in \mathcal{T}$$

**甲醇库存平衡：**
$$I^{MeOH}_{k,t} = I^{MeOH}_{k,t-1} + x^{MeOH}_{k,t} - x^{MeOH,cons}_{k,t}, \quad \forall k \in \mathcal{K}^{MTJ}, t \in \mathcal{T}$$

#### 3.2.4 FT-DS路径生产约束

**氢气消耗约束：**
$$\alpha^{H_2}_{FT} \cdot x^{SAF}_{k,t} \leq \sum_{i \in \mathcal{I}} \sum_{m \in \mathcal{M}} y^{H_2,m}_{i,k,t}, \quad \forall k \in \mathcal{K}^{FT}, t \in \mathcal{T}$$

**CO₂消耗约束：**
$$\alpha^{CO_2}_{FT} \cdot x^{SAF}_{k,t} \leq I^{CO_2}_{k,t-1} + \frac{1}{H_w} \sum_{j \in \mathcal{J}} \sum_{m \in \mathcal{M}} y^{CO_2,m}_{j,k,w(t)}, \quad \forall k \in \mathcal{K}^{FT}, t \in \mathcal{T}$$

#### 3.2.5 CO₂库存平衡约束（时间聚合）

$$I^{CO_2}_{k,t} = I^{CO_2}_{k,t-1} + \frac{1}{H_w} \sum_{j \in \mathcal{J}} \sum_{m \in \mathcal{M}} y^{CO_2,m}_{j,k,w(t)} - \phi^{CO_2}_{k,t}, \quad \forall k \in \mathcal{K}, t \in \mathcal{T}$$

其中$\phi^{CO_2}_{k,t}$表示时段$t$的CO₂消耗量：
$$\phi^{CO_2}_{k,t} = \begin{cases} \alpha^{CO_2 \to MeOH} \cdot x^{MeOH}_{k,t} & k \in \mathcal{K}^{MTJ} \\ \alpha^{CO_2}_{FT} \cdot x^{SAF}_{k,t} & k \in \mathcal{K}^{FT} \end{cases}$$

#### 3.2.6 库存容量约束

$$I^{MeOH}_{k,t} \leq \bar{I}^{MeOH}_k, \quad \forall k \in \mathcal{K}, t \in \mathcal{T}$$

$$I^{CO_2}_{k,t} \leq \bar{I}^{CO_2}_k, \quad \forall k \in \mathcal{K}, t \in \mathcal{T}$$

#### 3.2.7 运输能力约束

**管道运输：**
$$y^{H_2,pipe}_{i,k,t} \leq \bar{Y}^{pipe} \cdot z^{pipe}_{i,k}, \quad \forall i \in \mathcal{I}, k \in \mathcal{K}, t \in \mathcal{T}$$

$$y^{CO_2,pipe}_{j,k,w} \leq \bar{Y}^{pipe} \cdot z^{pipe}_{j,k}, \quad \forall j \in \mathcal{J}, k \in \mathcal{K}, w \in \mathcal{W}$$

**槽车运输：**
$$y^{H_2,truck}_{i,k,t} \leq \bar{Y}^{truck}, \quad \forall i \in \mathcal{I}, k \in \mathcal{K}, t \in \mathcal{T}$$

$$y^{CO_2,truck}_{j,k,w} \leq \bar{Y}^{truck}, \quad \forall j \in \mathcal{J}, k \in \mathcal{K}, w \in \mathcal{W}$$

#### 3.2.8 设施容量约束

**生产-产能关联：**
$$x^{SAF}_{k,t} \leq Q_k \cdot \tau, \quad \forall k \in \mathcal{K}, t \in \mathcal{T}$$

**产能-选址关联：**
$$\underline{Q}^{SAF} \cdot z_k \leq Q_k \leq \bar{Q}^{SAF} \cdot z_k, \quad \forall k \in \mathcal{K}$$

**最小年产量约束（规模经济）：**
$$\sum_{t \in \mathcal{T}} x^{SAF}_{k,t} \geq \underline{P}^{annual} \cdot z_k, \quad \forall k \in \mathcal{K}$$

#### 3.2.9 需求满足约束

**需求满足（软约束）：**
$$\sum_{k \in \mathcal{K}} y^{SAF}_{k,a,w} + s_{a,w} \geq D_{a,w}, \quad \forall a \in \mathcal{A}, w \in \mathcal{W}$$

**SAF产配平衡：**
$$\sum_{t \in \mathcal{T}_w} x^{SAF}_{k,t} \geq \sum_{a \in \mathcal{A}} y^{SAF}_{k,a,w}, \quad \forall k \in \mathcal{K}, w \in \mathcal{W}$$

#### 3.2.10 初始条件

$$I^{MeOH}_{k,0} = 0, \quad \forall k \in \mathcal{K}$$

$$I^{CO_2}_{k,0} = 0, \quad \forall k \in \mathcal{K}$$

#### 3.2.11 非负性与整数性约束

$$x^{H_2}_{i,t}, x^{CO_2}_{j,w}, x^{MeOH}_{k,t}, x^{SAF}_{k,t}, y^{(\cdot)}_{(\cdot)}, I^{(\cdot)}_{(\cdot)}, Q_k, s_{a,w} \geq 0$$

$$z_k, z^{pipe}_{i,k}, z^{pipe}_{j,k} \in \{0, 1\}$$

---

## 4 模型变体

基础模型可根据氢源类型、碳源类型及合成路径进行特化配置。

### 4.1 变体分类框架

| 变体编号 | 氢气来源 | CO₂来源 | 合成路径 |
|:--------:|----------|---------|----------|
| **H-1** | 可再生能源电解 | 煤气化 | MTJ |
| **H-2** | 可再生能源电解 | 直接空气捕集 | MTJ |
| **H-3** | 可再生能源电解 | 直接空气捕集 | FT-DS |
| **H-4** | 天然气重整 | 重整副产 | MTJ |
| **H-5** | 天然气重整 | 重整副产 | FT-DS |
| **H-6** | 可再生能源电解 | 工业点源捕集 | MTJ |
| **H-7** | 可再生能源电解 | 工业点源捕集 | FT-DS |
| **B-1** | 工业副产氢 | 煤气化 | MTJ |
| **B-2** | 工业副产氢 | 直接空气捕集 | MTJ |
| **B-3** | 工业副产氢 | 直接空气捕集 | FT-DS |
| **B-4** | 工业副产氢 + 天然气重整 | 重整副产 | MTJ |
| **B-5** | 工业副产氢 + 可再生电解 | 工业点源捕集 | MTJ |
| **B-6** | 工业副产氢 + 可再生电解 | 工业点源捕集 | FT-DS |

### 4.2 变体特化约束

#### 4.2.1 电解制氢变体（H-1至H-7）

激活约束集：$\mathcal{I} = \mathcal{I}^{elec}$

氢气产量受可再生能源出力约束：
$$x^{H_2}_{i,t} \leq \frac{P_{i,t} \cdot \tau}{\eta^{elec}}, \quad \forall i \in \mathcal{I}^{elec}, t \in \mathcal{T}$$

#### 4.2.2 工业副产氢变体（B-1至B-6）

激活约束集：$\mathcal{I}^{byp} \neq \emptyset$

**钢铁厂副产氢：**
$$x^{H_2}_{i,t} \leq \gamma^{steel}_{avail} \cdot \bar{Q}^{steel}_{i,t}, \quad \forall i \in \mathcal{I}^{steel}$$

**炼油厂副产氢：**
$$x^{H_2}_{i,t} \leq \gamma^{refinery}_{avail} \cdot \bar{Q}^{refinery}_{i,t}, \quad \forall i \in \mathcal{I}^{refinery}$$

#### 4.2.3 天然气重整变体（H-4, H-5, B-4）

激活约束集：$\mathcal{I}^{ref} \neq \emptyset$

**H₂-CO₂联产约束：**
$$x^{H_2}_{i,t} = \gamma^{ref}_{H_2} \cdot x^{NG}_{i,t}, \quad x^{CO_2}_{i,t} = \gamma^{ref}_{CO_2} \cdot x^{NG}_{i,t}$$

**天然气供应约束：**
$$x^{NG}_{l,w} \leq \bar{S}^{NG}_{l,w}, \quad \forall l \in \mathcal{L}^{LNG}, w \in \mathcal{W}$$

#### 4.2.4 煤气化变体（H-1, B-1）

CO₂本地生成，取消CO₂运输：
$$x^{CO_2}_{k,t} = \gamma^{coal} \cdot x^{coal}_{k,t}, \quad y^{CO_2,m}_{j,k,w} = 0$$

#### 4.2.5 直接空气捕集变体（H-2, H-3, B-2, B-3）

CO₂在生产现场就地捕集：
$$x^{DAC}_{k,t} \leq \frac{P^{avail}_{k,t} \cdot \tau}{E^{dac}}, \quad y^{CO_2,m}_{j,k,w} = 0$$

#### 4.2.6 工业点源捕集变体（H-6, H-7, B-5, B-6）

激活完整CO₂运输网络：
$$x^{CO_2}_{j,w} \leq \gamma^{cap}_j \cdot \bar{S}^{CO_2}_{j,w}, \quad \forall j \in \mathcal{J}^{ind}$$

#### 4.2.7 混合氢源变体（B-4, B-5, B-6）

**总氢气供应：**
$$x^{H_2,total}_{k,t} = \sum_{i \in \mathcal{I}^{byp}} y^{H_2}_{i,k,t} + \sum_{i \in \mathcal{I}^{elec} \cup \mathcal{I}^{ref}} y^{H_2}_{i,k,t}$$

---

**文档结束**
