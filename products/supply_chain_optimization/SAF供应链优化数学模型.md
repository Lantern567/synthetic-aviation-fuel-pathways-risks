# SAF供应链优化数学模型

## Sustainable Aviation Fuel Supply Chain Optimization Mathematical Model

**文档版本**: v1.0.0
**创建日期**: 2025-12-13
**适用项目**: 绿色甲醇港口运输项目 - 供应链优化模块

---

## 目录

1. [概述](#1-概述)
2. [符号定义](#2-符号定义)
3. [决策变量](#3-决策变量)
4. [约束条件](#4-约束条件)
5. [目标函数](#5-目标函数)
6. [13场景模型配置](#6-13场景模型配置)
7. [附录：参数取值表](#7-附录参数取值表)

---

## 1. 概述

### 1.1 问题背景

本模型针对可持续航空燃料（SAF, Sustainable Aviation Fuel）供应链网络优化问题，建立混合整数线性规划（MILP, Mixed Integer Linear Programming）模型。模型目标是在满足机场SAF需求的前提下，最小化供应链总成本。

### 1.2 供应链网络结构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SAF供应链网络拓扑结构                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────┐ │
│   │  氢气来源     │    │  CO₂来源     │    │   甲醇厂     │    │  机场    │ │
│   ├──────────────┤    ├──────────────┤    │  (两步法)    │    │          │ │
│   │ • 绿氢(风/光) │    │ • 工业捕获   │    ├──────────────┤    │          │ │
│   │ • 副产氢      │───▶│ • DAC大气    │───▶│   SAF厂     │───▶│  需求点  │ │
│   │ • 天然气重整  │    │ • 煤气化     │    │  (一/两步)   │    │          │ │
│   └──────────────┘    └──────────────┘    └──────────────┘    └──────────┘ │
│         │                    │                    │                        │
│         ▼                    ▼                    ▼                        │
│   ┌──────────────────────────────────────────────────────────┐             │
│   │               运输模式：管道 / 罐车                        │             │
│   └──────────────────────────────────────────────────────────┘             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.3 技术路线分类

本模型支持两种主要的SAF合成工艺：

| 工艺类型 | 技术路线 | 中间产物 | 典型场景 |
|---------|---------|---------|---------|
| **两步法** | H₂ + CO₂ → 甲醇 → SAF (E-CRM + MTJ) | 甲醇 | 场景1-2, 6, 8-9, 11-12 |
| **一步法** | H₂ + CO₂ → SAF (RWGS + Fischer-Tropsch) | 无 | 场景3, 5, 7, 10, 13 |

### 1.4 13场景汇总

| 编号 | 场景名称 | 氢气来源 | CO₂来源 | 工艺路线 |
|:---:|---------|---------|---------|---------|
| 1 | 煤制氢+绿氢两步法 | 绿氢(风/光电解) | 煤气化 | 两步法 |
| 2 | DAC制氢两步法 | 绿氢(风/光电解) | DAC大气捕获 | 两步法 |
| 3 | DAC制氢一步法 | 绿氢(风/光电解) | DAC大气捕获 | 一步法RWGS-FT |
| 4 | 天然气两步法 | 天然气重整 | 天然气重整副产 | 两步法 |
| 5 | 天然气一步法 | 天然气重整 | 天然气重整副产 | 一步法FT |
| 6 | 绿氢+工业CO₂两步法 | 绿氢(风/光电解) | 工业点源捕获 | 两步法 |
| 7 | 绿氢+工业CO₂一步法 | 绿氢(风/光电解) | 工业点源捕获 | 一步法RWGS-FT |
| 8 | 副产氢+煤气化CO₂两步法 | 工业副产氢 | 煤气化 | 两步法 |
| 9 | 副产氢+DAC两步法 | 工业副产氢 | DAC大气捕获 | 两步法 |
| 10 | 副产氢+DAC一步法 | 工业副产氢 | DAC大气捕获 | 一步法RWGS-FT |
| 11 | 副产氢+天然气两步法 | 工业副产氢 + 天然气 | 天然气重整副产 | 两步法 |
| 12 | 副产氢+绿氢两步法 | 工业副产氢 + 绿氢 | 工业点源捕获 | 两步法 |
| 13 | 副产氢+绿氢一步法 | 工业副产氢 + 绿氢 | 工业点源捕获 | 一步法RWGS-FT |

---

## 2. 符号定义

### 2.1 集合 (Sets)

| 符号 | 描述 | 说明 |
|-----|------|------|
| $\mathcal{I}$ | 氢气生产/供应设施集合 | 包括风电场、光伏电站、副产氢工厂 |
| $\mathcal{J}$ | CO₂供应源集合 | 包括煤电厂、天然气电厂、炼油厂、DAC设施 |
| $\mathcal{K}$ | SAF生产设施候选位置集合 | 可建设甲醇厂/SAF厂的地点 |
| $\mathcal{A}$ | 机场（需求点）集合 | SAF需求终端 |
| $\mathcal{T}$ | 时间周期集合 | $\mathcal{T} = \{1, 2, ..., T\}$，以小时/3小时为单位 |
| $\mathcal{W}$ | 周集合 | $\mathcal{W} = \{1, 2, ..., W\}$，需求按周计 |
| $\mathcal{M}$ | 运输模式集合 | $\mathcal{M} = \{\text{pipeline}, \text{truck}\}$ |
| $\mathcal{P}$ | 技术工艺集合 | $\mathcal{P} = \{\text{two\_step}, \text{one\_step}\}$ |

### 2.2 时间参数 (Temporal Parameters)

| 符号 | 描述 | 典型值 | 单位 |
|-----|------|--------|------|
| $T$ | 优化时间范围总期数 | 672 (12周×56) | 期 |
| $W$ | 优化时间范围周数 | 12 | 周 |
| $\tau$ | 每期小时数 | 3 | 小时/期 |
| $H_w$ | 每周期数 | 56 | 期/周 |

### 2.3 技术参数 (Technical Parameters)

#### 2.3.1 氢气相关参数

| 符号 | 描述 | 单位 | 两步法取值 | 一步法取值 |
|-----|------|------|-----------|-----------|
| $\alpha^{H_2}$ | 制1kg SAF所需氢气量 | kg H₂/kg SAF | 0.20 | 0.19 |
| $\eta^{elec}$ | 电解制氢效率 | kWh/kg H₂ | 55 | 55 |
| $\bar{Q}^{H_2}_i$ | 设施$i$的最大产氢能力 | kg/期 | - | - |
| $q^{H_2}_{i,t}$ | 设施$i$在$t$期的可再生能源发电量 | MWh | - | - |

#### 2.3.2 CO₂相关参数

| 符号 | 描述 | 单位 | 两步法取值 | 一步法取值 |
|-----|------|------|-----------|-----------|
| $\alpha^{CO_2}$ | 制1kg SAF所需CO₂量 | kg CO₂/kg SAF | 3.5 | 3.0 |
| $\gamma^{cap}_j$ | CO₂源$j$的捕获率 | - | 0.80-0.90 | 0.80-0.90 |
| $\bar{S}^{CO_2}_j$ | CO₂源$j$的最大可供给量 | kg/周 | - | - |
| $E^{DAC}$ | DAC单位能耗 | kWh/kg CO₂ | 0.35 | 0.35 |

#### 2.3.3 甲醇相关参数（仅两步法）

| 符号 | 描述 | 单位 | 取值 |
|-----|------|------|------|
| $\alpha^{MeOH}$ | 制1kg SAF所需甲醇量 | kg MeOH/kg SAF | 1.30 |
| $\beta^{MeOH}$ | 甲醇对SAF转化率 | kg SAF/kg MeOH | 0.77 |
| $\alpha^{H_2 \to MeOH}$ | 制1kg甲醇所需氢气量 | kg H₂/kg MeOH | 0.15 |
| $\alpha^{CO_2 \to MeOH}$ | 制1kg甲醇所需CO₂量 | kg CO₂/kg MeOH | 2.69 |

#### 2.3.4 天然气相关参数（仅天然气场景）

| 符号 | 描述 | 单位 | 取值 |
|-----|------|------|------|
| $\alpha^{NG}$ | 制1kg SAF所需天然气量 | m³ NG/kg SAF | 0.80 |
| $\alpha^{H_2}_{NG}$ | 天然气场景的额外氢气消耗 | kg H₂/kg SAF | 0.05 |

### 2.4 成本参数 (Cost Parameters)

#### 2.4.1 原料成本

| 符号 | 描述 | 单位 | 取值 |
|-----|------|------|------|
| $c^{wind}$ | 风电电价 | 元/kWh | 0.35 |
| $c^{solar}$ | 光伏电价 | 元/kWh | 0.40 |
| $c^{grid}$ | 电网电价 | 元/kWh | 0.60 |
| $c^{NG}$ | 天然气价格 | 元/m³ | 4.20 |
| $c^{coal}$ | 煤炭价格 | 元/kg | 0.60 |

#### 2.4.2 捕获成本

| 符号 | 描述 | 单位 | 取值 |
|-----|------|------|------|
| $c^{CCS}_{coal}$ | 煤电厂CCS成本 | 元/kg CO₂ | 0.15 |
| $c^{CCS}_{lng}$ | 天然气电厂CCS成本 | 元/kg CO₂ | 0.18 |
| $c^{CCS}_{ref}$ | 炼油厂CCS成本 | 元/kg CO₂ | 0.12 |
| $c^{DAC}$ | DAC捕获成本 | 元/kg CO₂ | 4.50 |

#### 2.4.3 运输成本

| 符号 | 描述 | 单位 | 取值 |
|-----|------|------|------|
| $c^{H_2}_{pipe}(d)$ | 氢气管道运输成本函数 | 元/kg·100km | 分段线性 |
| $c^{H_2}_{truck}$ | 氢气罐车运输成本 | 元/kg·100km | 15.0 |
| $c^{CO_2}_{pipe}(d)$ | CO₂管道运输成本函数 | 元/kg·100km | 分段线性 |
| $c^{CO_2}_{truck}$ | CO₂罐车运输成本 | 元/kg·100km | 5.0 |
| $c^{SAF}_{truck}$ | SAF罐车运输成本 | 元/kg·100km | 2.0 |

#### 2.4.4 设施成本（平准化LCOE）

| 符号 | 描述 | 单位 | 取值 |
|-----|------|------|------|
| $C^{fix}_{CAPEX}$ | 固定投资成本 | 元 | 20-80M |
| $C^{var}_{CAPEX}$ | 单位产能投资成本 | 元/(kg/h) | 20,000-400,000 |
| $C^{fix}_{OPEX}$ | 年固定运营成本 | 元/年 | 10-22M |
| $C^{var}_{OPEX}$ | 单位产品运营成本 | 元/kg | 0.3-0.8 |
| $r$ | 贴现率 | - | 0.08 |
| $L$ | 项目寿命 | 年 | 20 |

#### 2.4.5 惩罚成本

| 符号 | 描述 | 单位 | 取值 |
|-----|------|------|------|
| $c^{short}$ | 缺货惩罚成本 | 元/kg | 2,500 |

### 2.5 距离参数 (Distance Parameters)

| 符号 | 描述 | 单位 |
|-----|------|------|
| $d_{i,k}$ | 氢气源$i$到SAF厂$k$的距离 | km |
| $d_{j,k}$ | CO₂源$j$到SAF厂$k$的距离 | km |
| $d_{k,a}$ | SAF厂$k$到机场$a$的距离 | km |

### 2.6 需求参数 (Demand Parameters)

| 符号 | 描述 | 单位 |
|-----|------|------|
| $D_{a,w}$ | 机场$a$在第$w$周的SAF需求量 | kg/周 |

---

## 3. 决策变量

### 3.1 连续变量

#### 3.1.1 生产变量

| 符号 | 描述 | 单位 | 索引 |
|-----|------|------|------|
| $x^{H_2}_{i,t}$ | 设施$i$在$t$期的氢气产量 | kg | $i \in \mathcal{I}, t \in \mathcal{T}$ |
| $x^{CO_2}_{j,w}$ | CO₂源$j$在第$w$周的CO₂供给量 | kg | $j \in \mathcal{J}, w \in \mathcal{W}$ |
| $x^{DAC}_{k,t}$ | 设施$k$在$t$期的DAC捕获量 | kg | $k \in \mathcal{K}, t \in \mathcal{T}$ |
| $x^{MeOH}_{k,t}$ | 设施$k$在$t$期的甲醇产量 | kg | $k \in \mathcal{K}, t \in \mathcal{T}$ |
| $x^{SAF}_{k,t}$ | 设施$k$在$t$期的SAF产量 | kg | $k \in \mathcal{K}, t \in \mathcal{T}$ |

#### 3.1.2 运输变量

| 符号 | 描述 | 单位 | 索引 |
|-----|------|------|------|
| $y^{H_2,pipe}_{i,k,t}$ | 氢气管道运输量 | kg | $i \in \mathcal{I}, k \in \mathcal{K}, t \in \mathcal{T}$ |
| $y^{H_2,truck}_{i,k,t}$ | 氢气罐车运输量 | kg | $i \in \mathcal{I}, k \in \mathcal{K}, t \in \mathcal{T}$ |
| $y^{CO_2,pipe}_{j,k,w}$ | CO₂管道运输量 | kg | $j \in \mathcal{J}, k \in \mathcal{K}, w \in \mathcal{W}$ |
| $y^{CO_2,truck}_{j,k,w}$ | CO₂罐车运输量 | kg | $j \in \mathcal{J}, k \in \mathcal{K}, w \in \mathcal{W}$ |
| $y^{SAF}_{k,a,w}$ | SAF运输量 | kg | $k \in \mathcal{K}, a \in \mathcal{A}, w \in \mathcal{W}$ |

#### 3.1.3 库存变量

| 符号 | 描述 | 单位 | 索引 |
|-----|------|------|------|
| $I^{MeOH}_{k,t}$ | 甲醇库存量 | kg | $k \in \mathcal{K}, t \in \mathcal{T}$ |
| $I^{CO_2}_{k,t}$ | CO₂库存量 | kg | $k \in \mathcal{K}, t \in \mathcal{T}$ |
| $I^{SAF}_{k,w}$ | SAF库存量 | kg | $k \in \mathcal{K}, w \in \mathcal{W}$ |

#### 3.1.4 缺货变量

| 符号 | 描述 | 单位 | 索引 |
|-----|------|------|------|
| $s_{a,w}$ | 机场$a$在第$w$周的SAF缺货量 | kg | $a \in \mathcal{A}, w \in \mathcal{W}$ |

#### 3.1.5 产能变量

| 符号 | 描述 | 单位 | 索引 |
|-----|------|------|------|
| $Q^{SAF}_k$ | SAF设施$k$的建设产能 | kg/h | $k \in \mathcal{K}$ |

### 3.2 二元变量

| 符号 | 描述 | 索引 |
|-----|------|------|
| $z_k$ | 是否在位置$k$建设SAF设施 | $k \in \mathcal{K}$ |
| $z^{MeOH}_k$ | 是否在位置$k$建设甲醇设施（两步法） | $k \in \mathcal{K}$ |
| $z^{pipe}_{i,k}$ | 是否建设氢气管道$i \to k$ | $i \in \mathcal{I}, k \in \mathcal{K}$ |
| $z^{CO_2pipe}_{j,k}$ | 是否建设CO₂管道$j \to k$ | $j \in \mathcal{J}, k \in \mathcal{K}$ |

---

## 4. 约束条件

### 4.1 氢气供应约束

#### 4.1.1 绿氢生产约束（场景1-3, 6-7, 12-13）

绿氢产量受限于可再生能源发电量：

$$x^{H_2}_{i,t} \leq \frac{q^{H_2}_{i,t} \times 1000 \times \tau}{\eta^{elec}}, \quad \forall i \in \mathcal{I}^{green}, t \in \mathcal{T}$$

其中 $q^{H_2}_{i,t}$ 为第$t$期的可再生能源发电功率（MW），$\tau$为每期小时数。

#### 4.1.2 副产氢供应约束（场景8-13）

副产氢产量受限于工业副产可外供量：

$$x^{H_2}_{i,t} \leq \bar{Q}^{byproduct}_{i,t}, \quad \forall i \in \mathcal{I}^{byproduct}, t \in \mathcal{T}$$

其中 $\bar{Q}^{byproduct}_{i,t}$ 为副产氢在第$t$期的最大可外供量。

#### 4.1.3 氢气产销平衡

$$x^{H_2}_{i,t} = \sum_{k \in \mathcal{K}} \left( y^{H_2,pipe}_{i,k,t} + y^{H_2,truck}_{i,k,t} \right), \quad \forall i \in \mathcal{I}, t \in \mathcal{T}$$

### 4.2 CO₂供应约束

#### 4.2.1 工业点源CO₂捕获（场景6-7, 12-13）

$$x^{CO_2}_{j,w} \leq \gamma^{cap}_j \cdot \bar{S}^{CO_2}_{j,w}, \quad \forall j \in \mathcal{J}^{industrial}, w \in \mathcal{W}$$

#### 4.2.2 DAC大气捕获（场景2-3, 9-10）

DAC捕获受能源供应约束：

$$x^{DAC}_{k,t} \leq \frac{P^{avail}_{k,t} \times \tau}{E^{DAC}}, \quad \forall k \in \mathcal{K}, t \in \mathcal{T}$$

其中 $P^{avail}_{k,t}$ 为位置$k$在$t$期的可用电力（kW）。

#### 4.2.3 煤气化CO₂生成（场景1, 8）

煤气化过程伴随CO₂生成，本地直接使用：

$$x^{CO_2}_{k,t} = \gamma^{coal \to CO_2} \cdot x^{coal}_{k,t}, \quad \forall k \in \mathcal{K}^{coal}, t \in \mathcal{T}$$

其中 $\gamma^{coal \to CO_2}$ 为煤炭转化为CO₂的比例（约2.86 kg CO₂/kg coal）。

#### 4.2.4 CO₂产销平衡

$$x^{CO_2}_{j,w} = \sum_{k \in \mathcal{K}} \left( y^{CO_2,pipe}_{j,k,w} + y^{CO_2,truck}_{j,k,w} \right), \quad \forall j \in \mathcal{J}, w \in \mathcal{W}$$

### 4.3 生产工艺约束

#### 4.3.1 两步法：甲醇合成约束（场景1-2, 4, 6, 8-9, 11-12）

**氢气消耗约束**：
$$\alpha^{H_2 \to MeOH} \cdot x^{MeOH}_{k,t} \leq \sum_{i \in \mathcal{I}} \left( y^{H_2,pipe}_{i,k,t} + y^{H_2,truck}_{i,k,t} \right), \quad \forall k \in \mathcal{K}, t \in \mathcal{T}$$

**CO₂消耗约束**：
$$\alpha^{CO_2 \to MeOH} \cdot x^{MeOH}_{k,t} \leq I^{CO_2}_{k,t-1} + \frac{1}{H_w}\sum_{j \in \mathcal{J}} \left( y^{CO_2,pipe}_{j,k,w(t)} + y^{CO_2,truck}_{j,k,w(t)} \right), \quad \forall k, t$$

**甲醇转化SAF约束**：
$$x^{SAF}_{k,t} = \beta^{MeOH} \cdot x^{MeOH,used}_{k,t}, \quad \forall k \in \mathcal{K}, t \in \mathcal{T}$$

其中 $x^{MeOH,used}_{k,t}$ 为用于SAF生产的甲醇量。

#### 4.3.2 一步法：直接合成约束（场景3, 5, 7, 10, 13）

**氢气消耗约束**：
$$\alpha^{H_2} \cdot x^{SAF}_{k,t} \leq \sum_{i \in \mathcal{I}} \left( y^{H_2,pipe}_{i,k,t} + y^{H_2,truck}_{i,k,t} \right), \quad \forall k \in \mathcal{K}, t \in \mathcal{T}$$

**CO₂消耗约束**：
$$\alpha^{CO_2} \cdot x^{SAF}_{k,t} \leq I^{CO_2}_{k,t-1} + \frac{1}{H_w}\sum_{j \in \mathcal{J}} \left( y^{CO_2,pipe}_{j,k,w(t)} + y^{CO_2,truck}_{j,k,w(t)} \right), \quad \forall k, t$$

### 4.4 库存平衡约束

#### 4.4.1 甲醇库存平衡（两步法）

$$I^{MeOH}_{k,t} = I^{MeOH}_{k,t-1} + x^{MeOH}_{k,t} - x^{MeOH,used}_{k,t}, \quad \forall k \in \mathcal{K}, t \in \mathcal{T}$$

$$I^{MeOH}_{k,0} = 0, \quad \forall k \in \mathcal{K}$$

#### 4.4.2 CO₂库存平衡

CO₂库存用于实现周级供应到小时级消耗的时间尺度匹配：

$$I^{CO_2}_{k,t} = I^{CO_2}_{k,t-1} + \frac{1}{H_w}\sum_{j \in \mathcal{J}} \left( y^{CO_2,pipe}_{j,k,w(t)} + y^{CO_2,truck}_{j,k,w(t)} \right) - CO_2^{consumed}_{k,t}, \quad \forall k, t$$

其中 $CO_2^{consumed}_{k,t}$ 为：
- 两步法：$\alpha^{CO_2 \to MeOH} \cdot x^{MeOH}_{k,t}$
- 一步法：$\alpha^{CO_2} \cdot x^{SAF}_{k,t}$

#### 4.4.3 库存上限约束

$$I^{MeOH}_{k,t} \leq \bar{I}^{MeOH}_k, \quad \forall k \in \mathcal{K}, t \in \mathcal{T}$$

$$I^{CO_2}_{k,t} \leq \bar{I}^{CO_2}_k, \quad \forall k \in \mathcal{K}, t \in \mathcal{T}$$

### 4.5 运输能力约束

#### 4.5.1 氢气管道运输

$$y^{H_2,pipe}_{i,k,t} \leq \bar{Y}^{H_2,pipe} \cdot z^{pipe}_{i,k}, \quad \forall i \in \mathcal{I}, k \in \mathcal{K}, t \in \mathcal{T}$$

#### 4.5.2 氢气罐车运输

$$y^{H_2,truck}_{i,k,t} \leq \bar{Y}^{H_2,truck}, \quad \forall i \in \mathcal{I}, k \in \mathcal{K}, t \in \mathcal{T}$$

#### 4.5.3 CO₂管道运输

$$y^{CO_2,pipe}_{j,k,w} \leq \bar{Y}^{CO_2,pipe} \cdot z^{CO_2pipe}_{j,k}, \quad \forall j \in \mathcal{J}, k \in \mathcal{K}, w \in \mathcal{W}$$

#### 4.5.4 CO₂罐车运输

$$y^{CO_2,truck}_{j,k,w} \leq \bar{Y}^{CO_2,truck}, \quad \forall j \in \mathcal{J}, k \in \mathcal{K}, w \in \mathcal{W}$$

### 4.6 设施约束

#### 4.6.1 设施建设与产能关联

$$x^{SAF}_{k,t} \leq Q^{SAF}_k \cdot \tau, \quad \forall k \in \mathcal{K}, t \in \mathcal{T}$$

$$Q^{SAF}_k \leq \bar{Q}^{SAF}_{max} \cdot z_k, \quad \forall k \in \mathcal{K}$$

$$Q^{SAF}_k \geq \underline{Q}^{SAF}_{min} \cdot z_k, \quad \forall k \in \mathcal{K}$$

#### 4.6.2 最小年产量约束

如果建设设施，年产量必须达到最小值：

$$\sum_{t \in \mathcal{T}} x^{SAF}_{k,t} \geq \underline{P}^{annual}_{min} \cdot z_k, \quad \forall k \in \mathcal{K}$$

### 4.7 需求满足约束

#### 4.7.1 机场需求约束（软约束）

$$\sum_{k \in \mathcal{K}} y^{SAF}_{k,a,w} + s_{a,w} \geq D_{a,w}, \quad \forall a \in \mathcal{A}, w \in \mathcal{W}$$

#### 4.7.2 缺货非负约束

$$s_{a,w} \geq 0, \quad \forall a \in \mathcal{A}, w \in \mathcal{W}$$

### 4.8 非负约束

所有连续决策变量非负：

$$x^{H_2}_{i,t}, x^{CO_2}_{j,w}, x^{MeOH}_{k,t}, x^{SAF}_{k,t}, y^{(\cdot)}_{(\cdot)}, I^{(\cdot)}_{(\cdot)}, Q^{SAF}_k \geq 0$$

---

## 5. 目标函数

### 5.1 总成本最小化

$$\min Z = C^{H_2} + C^{CO_2} + C^{trans} + C^{prod} + C^{inv} + C^{facility} + C^{short}$$

### 5.2 各成本项定义

#### 5.2.1 氢气生产成本

**绿氢生产成本**：
$$C^{H_2}_{green} = \sum_{t \in \mathcal{T}} \sum_{i \in \mathcal{I}^{green}} c^{elec}_i \cdot \eta^{elec} \cdot x^{H_2}_{i,t}$$

**副产氢采购成本**：
$$C^{H_2}_{byproduct} = \sum_{t \in \mathcal{T}} \sum_{i \in \mathcal{I}^{byproduct}} c^{byproduct}_i \cdot x^{H_2}_{i,t}$$

**总氢气成本**：
$$C^{H_2} = C^{H_2}_{green} + C^{H_2}_{byproduct}$$

#### 5.2.2 CO₂捕获成本

**工业点源CCS成本**：
$$C^{CCS} = \sum_{w \in \mathcal{W}} \sum_{j \in \mathcal{J}^{industrial}} c^{CCS}_j \cdot x^{CO_2}_{j,w}$$

**DAC捕获成本**：
$$C^{DAC} = \sum_{t \in \mathcal{T}} \sum_{k \in \mathcal{K}} c^{DAC} \cdot x^{DAC}_{k,t}$$

**煤气化成本**：
$$C^{coal} = \sum_{t \in \mathcal{T}} \sum_{k \in \mathcal{K}^{coal}} c^{coal}_{gasify} \cdot x^{coal}_{k,t}$$

**总CO₂成本**：
$$C^{CO_2} = C^{CCS} + C^{DAC} + C^{coal}$$

#### 5.2.3 运输成本

**氢气运输成本**：
$$C^{trans}_{H_2} = \sum_{t \in \mathcal{T}} \sum_{i \in \mathcal{I}} \sum_{k \in \mathcal{K}} \left[ c^{H_2}_{pipe}(d_{i,k}) \cdot y^{H_2,pipe}_{i,k,t} + c^{H_2}_{truck} \cdot \frac{d_{i,k}}{100} \cdot y^{H_2,truck}_{i,k,t} \right]$$

**CO₂运输成本**：
$$C^{trans}_{CO_2} = \sum_{w \in \mathcal{W}} \sum_{j \in \mathcal{J}} \sum_{k \in \mathcal{K}} \left[ c^{CO_2}_{pipe}(d_{j,k}) \cdot y^{CO_2,pipe}_{j,k,w} + c^{CO_2}_{truck} \cdot \frac{d_{j,k}}{100} \cdot y^{CO_2,truck}_{j,k,w} \right]$$

**SAF运输成本**：
$$C^{trans}_{SAF} = \sum_{w \in \mathcal{W}} \sum_{k \in \mathcal{K}} \sum_{a \in \mathcal{A}} c^{SAF}_{truck} \cdot \frac{d_{k,a}}{100} \cdot y^{SAF}_{k,a,w}$$

**总运输成本**：
$$C^{trans} = C^{trans}_{H_2} + C^{trans}_{CO_2} + C^{trans}_{SAF}$$

#### 5.2.4 生产成本

**甲醇生产成本（两步法）**：
$$C^{prod}_{MeOH} = \sum_{t \in \mathcal{T}} \sum_{k \in \mathcal{K}} c^{MeOH}_{prod} \cdot x^{MeOH}_{k,t}$$

**SAF生产成本**：
$$C^{prod}_{SAF} = \sum_{t \in \mathcal{T}} \sum_{k \in \mathcal{K}} c^{SAF}_{prod} \cdot x^{SAF}_{k,t}$$

**总生产成本**：
$$C^{prod} = C^{prod}_{MeOH} + C^{prod}_{SAF}$$

#### 5.2.5 库存成本

$$C^{inv} = \sum_{t \in \mathcal{T}} \sum_{k \in \mathcal{K}} \left[ c^{inv}_{MeOH} \cdot I^{MeOH}_{k,t} + c^{inv}_{CO_2} \cdot I^{CO_2}_{k,t} \right]$$

#### 5.2.6 设施投资成本（平准化LCOE）

采用资本回收因子(CRF)将投资成本年化：

$$CRF = \frac{r(1+r)^L}{(1+r)^L - 1}$$

**年化设施成本**：
$$C^{facility} = \sum_{k \in \mathcal{K}} \left[ CRF \cdot \left( C^{fix}_{CAPEX} \cdot z_k + C^{var}_{CAPEX} \cdot Q^{SAF}_k \right) + C^{fix}_{OPEX} \cdot z_k + C^{var}_{OPEX} \cdot \sum_{t \in \mathcal{T}} x^{SAF}_{k,t} \right] \cdot \frac{W}{52}$$

注：乘以 $\frac{W}{52}$ 将年成本按比例分配到优化时间范围。

#### 5.2.7 缺货惩罚成本

$$C^{short} = \sum_{w \in \mathcal{W}} \sum_{a \in \mathcal{A}} c^{short} \cdot s_{a,w}$$

---

## 6. 13场景模型配置

### 6.1 场景1：煤制氢+绿氢两步法

**技术路线**：煤气化CO₂ + 绿氢(风/光电解) → 甲醇 → SAF

**特化约束**：
- CO₂来源：煤气化本地产生，无需运输
- 氢气来源：可再生能源电解水
- 工艺：两步法（E-CRM + MTJ）

**配置文件**：`CoalHydrogenSAFOptimizer_config.yaml`

**关键参数**：
| 参数 | 取值 | 说明 |
|-----|------|------|
| h2_consumption_ratio | 0.20 | kg H₂/kg SAF |
| co2_consumption_ratio | 3.5 | kg CO₂/kg SAF |
| coal_to_co2_ratio | 2.86 | kg CO₂/kg coal |
| enable_co2_utilization_credit | false | 化石碳不计负排放 |

### 6.2 场景2：DAC制氢两步法

**技术路线**：DAC大气CO₂ + 绿氢 → 甲醇 → SAF

**特化约束**：
- CO₂来源：DAC大气直接捕获（本地产消）
- 删除CO₂运输约束
- 新增DAC能耗约束

**配置文件**：`DACHydrogenSAFOptimizer_config.yaml`

**关键参数**：
| 参数 | 取值 | 说明 |
|-----|------|------|
| h2_consumption_ratio | 0.20 | kg H₂/kg SAF |
| co2_consumption_ratio | 3.5 | kg CO₂/kg SAF |
| dac_energy_kwh_per_ton | 350 | kWh/ton CO₂ |
| dac_cost_yuan_per_ton | 4500 | 元/ton CO₂ |

### 6.3 场景3：DAC制氢一步法

**技术路线**：DAC大气CO₂ + 绿氢 → SAF (RWGS-FT直接合成)

**特化约束**：
- 删除甲醇中间环节
- CO₂、H₂直接参与RWGS反应生成CO
- CO + H₂经Fischer-Tropsch合成SAF

**配置文件**：`DACHydrogenSAFOptimizer_config.yaml` (process=one_step)

**关键参数**：
| 参数 | 取值 | 说明 |
|-----|------|------|
| h2_consumption_ratio | 0.19 | kg H₂/kg SAF (一步法更低) |
| co2_consumption_ratio | 3.0 | kg CO₂/kg SAF |
| rwgs_temperature_celsius | 700 | RWGS反应温度 |
| ft_temperature_celsius | 230 | FT反应温度 |

### 6.4 场景4：天然气两步法

**技术路线**：天然气重整(E-CRM+TRM) → 甲醇 → SAF

**特化约束**：

1. **天然气供应约束**（来自LNG接收站/管道）：
$$x^{NG}_{l,w} \leq \bar{S}^{NG}_{l,w}, \quad \forall l \in \mathcal{L}^{LNG}, w \in \mathcal{W}$$

2. **天然气重整物料平衡**（同时产生H₂和CO₂）：
$$x^{H_2}_{k,t} = \gamma^{NG \to H_2} \cdot x^{NG}_{k,t}, \quad x^{CO_2}_{k,t} = \gamma^{NG \to CO_2} \cdot x^{NG}_{k,t}$$

3. **天然气消耗约束**：
$$\alpha^{NG} \cdot x^{SAF}_{k,t} \leq x^{NG}_{k,t}, \quad \forall k \in \mathcal{K}, t \in \mathcal{T}$$

4. **碳汇约束**：化石燃料CO₂不计入负排放
$$\text{enable\_co2\_utilization\_credit} = \text{false}$$

**配置文件**：`NaturalGasSupplyChainOptimizer_config.yaml`

**关键参数**（从配置文件提取）：
| 参数 | 取值 | 说明 |
|-----|------|------|
| ng_consumption_ratio | 0.80 | m³ NG/kg SAF |
| h2_consumption_ratio | 0.05 | kg H₂/kg SAF (补充氢) |
| ng_to_methanol_rate | 1.2 | m³ NG/kg 甲醇 |
| h2_addition_rate | 40% | 甲醇合成氢气添加比例 |
| natural_gas_price_yuan_per_m3 | 4.2 | 天然气价格 |
| avg_lng_capacity_mcm_per_year | 1000 | LNG接收站平均容量(万m³/年) |
| enable_co2_utilization_credit | false | 化石碳不计负排放 |

### 6.5 场景5：天然气一步法

**技术路线**：天然气重整 → SAF (FT直接合成)

**特化约束**：

1. **删除甲醇中间环节**：无$x^{MeOH}_{k,t}$变量和约束

2. **天然气直接转化SAF约束**：
$$\alpha^{NG}_{FT} \cdot x^{SAF}_{k,t} \leq x^{NG}_{k,t}, \quad \forall k \in \mathcal{K}, t \in \mathcal{T}$$

3. **FT反应器容量约束**：
$$x^{SAF}_{k,t} \leq \bar{Q}^{FT}_{max} \cdot z^{FT}_k, \quad \forall k \in \mathcal{K}, t \in \mathcal{T}$$

**配置文件**：`NaturalGasSupplyChainOptimizer_config_one_step.yaml`

**关键参数**：
| 参数 | 取值 | 说明 |
|-----|------|------|
| ft_reactor_max_capacity_kg_per_hour | 1,000,000 | FT反应器最大产能 |
| ft_reactor_min_capacity_kg_per_hour | 0.01 | FT反应器最小产能 |

### 6.6 场景6：绿氢+工业CO₂两步法

**技术路线**：绿氢 + 工业点源CCS捕获CO₂ → 甲醇 → SAF

**特化约束**：
- CO₂来源：煤电厂、天然气电厂、炼油厂
- 包含完整的CO₂管道/罐车运输

**配置文件**：`GreenHydrogenSupplyChainOptimizer_config.yaml`

**关键参数**：
| 参数 | 取值 | 说明 |
|-----|------|------|
| h2_consumption_ratio | 0.20 | kg H₂/kg SAF |
| co2_consumption_ratio | 3.5 | kg CO₂/kg SAF |
| enable_co2_utilization_credit | true | 工业碳计入负排放 |
| utilization_credit_factor | -1.0 | CORSIA 100%计入 |

### 6.7 场景7：绿氢+工业CO₂一步法

**技术路线**：绿氢 + 工业点源CCS捕获CO₂ → SAF (RWGS-FT)

**配置文件**：`GreenHydrogenSupplyChainOptimizer_config_one_step_direct_ft.yaml`

**关键参数**：
| 参数 | 取值 | 说明 |
|-----|------|------|
| h2_consumption_ratio | 0.19 | kg H₂/kg SAF |
| co2_consumption_ratio | 3.0 | kg CO₂/kg SAF |

### 6.8 场景8：副产氢+煤气化CO₂两步法

**技术路线**：工业副产氢 + 煤气化CO₂ → 甲醇 → SAF

**特化约束**：

1. **钢铁厂副产氢供应约束**：
$$x^{H_2}_{i,t} \leq \gamma^{steel}_{avail} \cdot \bar{Q}^{steel}_{i,t}, \quad \forall i \in \mathcal{I}^{steel}, t \in \mathcal{T}$$

其中 $\gamma^{steel}_{avail} = 0.30$（30%可外供率）

2. **炼油厂副产氢供应约束**：
$$x^{H_2}_{i,t} \leq \gamma^{refinery}_{avail} \cdot \bar{Q}^{refinery}_{i,t}, \quad \forall i \in \mathcal{I}^{refinery}, t \in \mathcal{T}$$

其中 $\gamma^{refinery}_{avail} = 0.15$（15%可外供率）

3. **煤气化CO₂生成约束**（本地产消）：
$$x^{CO_2}_{k,t} = \gamma^{coal \to CO_2} \cdot x^{coal}_{k,t}, \quad \forall k \in \mathcal{K}$$

其中 $\gamma^{coal \to CO_2} = 2.44$ kg CO₂/kg coal

4. **碳汇约束**：化石燃料CO₂不计入负排放
$$\text{enable\_co2\_utilization\_credit} = \text{false}$$

**配置文件**：`CoalByproductHydrogenSAFOptimizer_config.yaml`

**关键参数**（从配置文件提取）：
| 参数 | 取值 | 说明 |
|-----|------|------|
| steel_available_rate | 0.30 | 钢铁厂副产氢可外供比例 |
| refinery_available_rate | 0.15 | 炼油厂副产氢可外供比例 |
| co2_per_kg_coal | 2.44 | kg CO₂/kg coal |
| coal_price_yuan_per_ton | 525 | 煤炭价格 |
| gasification_efficiency | 0.75 | 气化效率 |
| coal_consumption_kg_per_kg_saf | 1.0 | kg coal/kg SAF |
| enable_co2_utilization_credit | false | 化石碳不计负排放 |

### 6.9 场景9：副产氢+DAC两步法

**技术路线**：工业副产氢 + DAC大气CO₂ → 甲醇 → SAF

**特化约束**：

1. **副产氢供应约束**：同场景8的副产氢约束

2. **DAC能耗约束**：
$$x^{DAC}_{k,t} \leq \frac{P^{avail}_{k,t} \times \tau}{E^{DAC}}, \quad \forall k \in \mathcal{K}, t \in \mathcal{T}$$

3. **碳汇约束**：DAC捕获的大气CO₂计入负排放
$$\text{enable\_co2\_utilization\_credit} = \text{true}, \quad \text{utilization\_credit\_factor} = -1.0$$

**配置文件**：`DACByproductHydrogenSAFOptimizer_config_two_step.yaml`

**关键参数**：
| 参数 | 取值 | 说明 |
|-----|------|------|
| dac_energy_kwh_per_ton | 350 | DAC能耗 |
| dac_cost_yuan_per_ton | 4500 | DAC成本 |
| enable_co2_utilization_credit | true | 大气碳计入负排放 |

### 6.10 场景10：副产氢+DAC一步法

**技术路线**：工业副产氢 + DAC大气CO₂ → SAF (RWGS-FT)

**特化约束**：

1. **副产氢供应约束**：同场景8

2. **DAC能耗约束**：同场景9

3. **一步法工艺约束**：删除甲醇中间环节，H₂+CO₂直接合成SAF
$$\alpha^{H_2}_{one-step} \cdot x^{SAF}_{k,t} \leq x^{H_2,avail}_{k,t}, \quad \forall k, t$$

**配置文件**：`DACByproductHydrogenSAFOptimizer_config_one_step.yaml`

**关键参数**：
| 参数 | 取值 | 说明 |
|-----|------|------|
| h2_consumption_ratio | 0.19 | kg H₂/kg SAF (一步法) |
| co2_consumption_ratio | 3.0 | kg CO₂/kg SAF (一步法) |

### 6.11 场景11：副产氢+天然气两步法

**技术路线**：工业副产氢 + 天然气重整 → 甲醇 → SAF

**特化约束**：

1. **副产氢供应约束**：同场景8

2. **天然气供应约束**：同场景4

3. **混合氢源约束**：总氢气供应 = 副产氢 + 天然气重整制氢
$$x^{H_2,total}_{k,t} = x^{H_2,byproduct}_{k,t} + x^{H_2,NG}_{k,t}, \quad \forall k, t$$

4. **碳汇约束**：化石燃料CO₂不计入负排放

**配置文件**：`NaturalGasByproductHydrogenOptimizer_config.yaml`

**关键参数**：
| 参数 | 取值 | 说明 |
|-----|------|------|
| steel_available_rate | 0.30 | 钢铁厂副产氢可外供比例 |
| refinery_available_rate | 0.15 | 炼油厂副产氢可外供比例 |
| natural_gas_price_yuan_per_m3 | 4.2 | 天然气价格 |
| enable_co2_utilization_credit | false | 化石碳不计负排放 |

### 6.12 场景12：副产氢+绿氢两步法

**技术路线**：(工业副产氢 + 绿氢) + 工业CCS CO₂ → 甲醇 → SAF

**特化约束**：

1. **副产氢供应约束**：同场景8

2. **绿氢供应约束**：同场景6（可再生能源电解）

3. **混合氢源约束**（副产氢优先使用）：
$$x^{H_2,total}_{k,t} = x^{H_2,byproduct}_{k,t} + x^{H_2,green}_{k,t}, \quad \forall k, t$$

4. **工业CO₂捕获约束**：
$$x^{CO_2}_{j,w} \leq \gamma^{cap}_j \cdot \bar{S}^{CO_2}_{j,w}, \quad \forall j \in \mathcal{J}^{industrial}, w \in \mathcal{W}$$

5. **碳汇约束**：工业捕获CO₂计入负排放
$$\text{enable\_co2\_utilization\_credit} = \text{true}, \quad \text{utilization\_credit\_factor} = -1.0$$

**配置文件**：`ByproductHydrogenSupplyChainOptimizer_config_two_step.yaml`

**关键参数**：
| 参数 | 取值 | 说明 |
|-----|------|------|
| steel_available_rate | 0.30 | 钢铁厂副产氢可外供比例 |
| refinery_available_rate | 0.15 | 炼油厂副产氢可外供比例 |
| steel_upstream_carbon_intensity | 22 | kgCO₂/kg H₂ (钢铁副产氢) |
| refinery_upstream_carbon_intensity | 0.484 | kgCO₂/kg H₂ (炼油副产氢) |
| enable_co2_utilization_credit | true | 工业碳计入负排放 |

### 6.13 场景13：副产氢+绿氢一步法

**技术路线**：(工业副产氢 + 绿氢) + 工业CCS CO₂ → SAF (RWGS-FT)

**特化约束**：

1. **副产氢供应约束**：同场景8

2. **绿氢供应约束**：同场景6

3. **混合氢源约束**：同场景12

4. **一步法工艺约束**：删除甲醇中间环节
$$\alpha^{H_2}_{one-step} \cdot x^{SAF}_{k,t} \leq x^{H_2,total}_{k,t}, \quad \forall k, t$$
$$\alpha^{CO_2}_{one-step} \cdot x^{SAF}_{k,t} \leq I^{CO_2}_{k,t-1} + \text{CO}_2\text{\_supply}_{k,t}, \quad \forall k, t$$

5. **碳汇约束**：工业捕获CO₂计入负排放

**配置文件**：`ByproductHydrogenSupplyChainOptimizer_config.yaml`

**关键参数**：
| 参数 | 取值 | 说明 |
|-----|------|------|
| h2_consumption_ratio | 0.19 | kg H₂/kg SAF (一步法) |
| co2_consumption_ratio | 3.0 | kg CO₂/kg SAF (一步法) |
| enable_co2_utilization_credit | true | 工业碳计入负排放 |

---

## 7. 附录：参数取值表

### 7.1 技术参数汇总

| 参数 | 两步法(E-CRM+MTJ) | 一步法(RWGS-FT) | 单位 |
|------|-----------------|----------------|------|
| H₂消耗比 | 0.20 | 0.19 | kg H₂/kg SAF |
| CO₂消耗比 | 3.50 | 3.00 | kg CO₂/kg SAF |
| 甲醇中间比 | 1.30 | - | kg MeOH/kg SAF |
| 甲醇转化率 | 0.77 | - | kg SAF/kg MeOH |
| 电解制氢能耗 | 55 | 55 | kWh/kg H₂ |
| DAC能耗 | 350 | 350 | kWh/ton CO₂ |

### 7.2 成本参数汇总

| 参数 | 取值 | 单位 |
|------|------|------|
| 风电电价 | 0.35 | 元/kWh |
| 光伏电价 | 0.40 | 元/kWh |
| 电网电价 | 0.60 | 元/kWh |
| 天然气价格 | 4.20 | 元/m³ |
| 副产氢成本 | 12.00 | 元/kg |
| 煤电厂CCS成本 | 0.15 | 元/kg CO₂ |
| DAC捕获成本 | 4.50 | 元/kg CO₂ |
| 缺货惩罚 | 2,500 | 元/kg |

### 7.3 容量参数汇总

| 参数 | 取值 | 单位 |
|------|------|------|
| 电解槽最大产能 | 100,000 | kg H₂/h |
| 电解槽最小产能 | 100 | kg H₂/h |
| SAF反应器最大产能 | 1,000,000 | kg SAF/h |
| SAF最小年产量 | 100 | kg/年 |
| 最大运输距离 | 1,000 | km |

### 7.4 经济参数汇总

| 参数 | 取值 | 单位 |
|------|------|------|
| 贴现率 | 8% | - |
| 项目寿命 | 20 | 年 |
| 电解槽寿命 | 15 | 年 |
| SAF反应器寿命 | 25 | 年 |
| 管道寿命 | 30 | 年 |

### 7.5 碳排放参数汇总

| 参数 | 取值 | 单位 |
|------|------|------|
| 传统航空煤油碳强度 | 89 | gCO₂e/MJ |
| SAF能量含量 | 43.15 | MJ/kg |
| CORSIA限值 | 30 | gCO₂e/MJ |
| 风电碳强度 | 0.015 | kgCO₂e/kWh |
| 光伏碳强度 | 0.045 | kgCO₂e/kWh |
| 绿氢碳强度 | 1.1 | kgCO₂e/kg H₂ |

---

## 参考文献

1. IEA (2024). Hydrogen Projects Database
2. IRENA (2024). Green Hydrogen Cost Reduction Report
3. Global CCS Institute (2024). Global Status of CCS Report
4. ICAO (2023). CORSIA Methodology for Calculating Actual Life Cycle Emissions Values
5. Climeworks (2023). Direct Air Capture Technology Whitepaper

---

**文档结束**

