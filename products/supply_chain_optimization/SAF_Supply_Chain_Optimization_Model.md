# Sustainable Aviation Fuel Supply Chain Network Optimization: A Mixed-Integer Linear Programming Formulation

---

## Abstract

This document presents a mixed-integer linear programming (MILP) model for optimizing the supply chain network of Sustainable Aviation Fuel (SAF). The model incorporates multiple hydrogen production pathways, carbon dioxide capture technologies, and synthesis routes to minimize total supply chain costs while satisfying airport demand constraints. The formulation addresses the temporal mismatch between hourly renewable energy availability and weekly demand patterns through inventory management mechanisms.

---

## 1. Problem Description

### 1.1 Network Structure

The SAF supply chain network comprises four tiers:

1. **Hydrogen Supply Tier**: Renewable energy sites (wind/solar for electrolysis), industrial byproduct sources (steel plants, refineries), and natural gas reforming facilities
2. **Carbon Dioxide Supply Tier**: Industrial point sources (power plants, refineries), Direct Air Capture (DAC) facilities, and coal gasification units
3. **Production Tier**: SAF synthesis facilities employing either the Methanol-to-Jet (MTJ) pathway or the Fischer-Tropsch (FT) direct synthesis pathway
4. **Demand Tier**: Airports with specified SAF requirements

### 1.2 Synthesis Pathways

Two primary synthesis pathways are considered:

- **Methanol-to-Jet (MTJ) Pathway**: Hydrogen and carbon dioxide are first converted to methanol via catalytic synthesis, followed by methanol-to-jet fuel conversion
- **Fischer-Tropsch Direct Synthesis (FT-DS) Pathway**: Hydrogen and carbon dioxide undergo reverse water-gas shift reaction followed by Fischer-Tropsch synthesis to directly produce jet fuel

---

## 2. Notation

### 2.1 Sets

| Symbol | Description |
|:------:|-------------|
| $\mathcal{I}$ | Set of hydrogen supply facilities |
| $\mathcal{I}^{elec} \subseteq \mathcal{I}$ | Subset of electrolysis-based hydrogen facilities |
| $\mathcal{I}^{byp} \subseteq \mathcal{I}$ | Subset of industrial byproduct hydrogen facilities |
| $\mathcal{I}^{ref} \subseteq \mathcal{I}$ | Subset of reforming-based hydrogen facilities |
| $\mathcal{J}$ | Set of CO₂ supply sources |
| $\mathcal{J}^{ind} \subseteq \mathcal{J}$ | Subset of industrial point sources |
| $\mathcal{J}^{dac} \subseteq \mathcal{J}$ | Subset of DAC facilities |
| $\mathcal{J}^{gas} \subseteq \mathcal{J}$ | Subset of gasification-based CO₂ sources |
| $\mathcal{K}$ | Set of candidate SAF production facility locations |
| $\mathcal{A}$ | Set of airports (demand nodes) |
| $\mathcal{T}$ | Set of time periods (hourly/sub-hourly granularity) |
| $\mathcal{W}$ | Set of planning weeks |
| $\mathcal{M}$ | Set of transportation modes $\{pipeline, truck\}$ |
| $\mathcal{P}$ | Set of synthesis pathways $\{MTJ, FT\text{-}DS\}$ |

### 2.2 Index Mapping

| Symbol | Description |
|:------:|-------------|
| $w(t)$ | Week index corresponding to time period $t$ |
| $\mathcal{T}_w$ | Set of time periods within week $w$ |
| $H_w$ | Number of time periods per week |

### 2.3 Parameters

#### 2.3.1 Supply Parameters

| Symbol | Description | Unit |
|:------:|-------------|:----:|
| $\bar{Q}^{H_2}_{i,t}$ | Maximum hydrogen production capacity at facility $i$ in period $t$ | kg |
| $\bar{S}^{CO_2}_{j,w}$ | Maximum CO₂ supply from source $j$ in week $w$ | kg |
| $\gamma^{cap}_j$ | Capture efficiency at CO₂ source $j$ | - |
| $\eta^{elec}$ | Electrolysis energy consumption | kWh/kg H₂ |
| $E^{dac}$ | DAC energy consumption | kWh/kg CO₂ |
| $P_{i,t}$ | Available renewable power at site $i$ in period $t$ | kW |

#### 2.3.2 Conversion Parameters

| Symbol | Description | Unit |
|:------:|-------------|:----:|
| $\alpha^{H_2}_p$ | Hydrogen consumption ratio for pathway $p$ | kg H₂/kg SAF |
| $\alpha^{CO_2}_p$ | CO₂ consumption ratio for pathway $p$ | kg CO₂/kg SAF |
| $\alpha^{MeOH}$ | Methanol requirement for MTJ pathway | kg MeOH/kg SAF |
| $\beta^{MeOH}$ | Methanol-to-SAF conversion efficiency | kg SAF/kg MeOH |
| $\gamma^{coal}$ | CO₂ generation ratio from coal gasification | kg CO₂/kg coal |
| $\gamma^{ref}_{H_2}$ | H₂ yield from natural gas reforming | kg H₂/m³ NG |
| $\gamma^{ref}_{CO_2}$ | CO₂ yield from natural gas reforming | kg CO₂/m³ NG |

#### 2.3.3 Cost Parameters

| Symbol | Description | Unit |
|:------:|-------------|:----:|
| $c^{H_2}_i$ | Unit hydrogen production cost at facility $i$ | ¥/kg |
| $c^{CO_2}_j$ | Unit CO₂ capture cost at source $j$ | ¥/kg |
| $c^{trans}_{m}(d)$ | Transportation cost function for mode $m$ over distance $d$ | ¥/kg |
| $c^{prod}_p$ | Unit production cost for pathway $p$ | ¥/kg SAF |
| $c^{inv}$ | Unit inventory holding cost | ¥/kg·period |
| $c^{short}$ | Unit shortage penalty cost | ¥/kg |
| $C^{fix}$ | Fixed facility investment cost | ¥ |
| $C^{var}$ | Variable capacity investment cost | ¥/(kg/h) |

#### 2.3.4 Capacity Parameters

| Symbol | Description | Unit |
|:------:|-------------|:----:|
| $\bar{Q}^{SAF}$ | Maximum SAF facility capacity | kg/h |
| $\underline{Q}^{SAF}$ | Minimum SAF facility capacity | kg/h |
| $\bar{Y}^m$ | Maximum transportation capacity for mode $m$ | kg/period |
| $\bar{I}$ | Maximum inventory capacity | kg |

#### 2.3.5 Demand Parameters

| Symbol | Description | Unit |
|:------:|-------------|:----:|
| $D_{a,w}$ | SAF demand at airport $a$ in week $w$ | kg |

#### 2.3.6 Distance Parameters

| Symbol | Description | Unit |
|:------:|-------------|:----:|
| $d_{i,k}$ | Distance from H₂ source $i$ to facility $k$ | km |
| $d_{j,k}$ | Distance from CO₂ source $j$ to facility $k$ | km |
| $d_{k,a}$ | Distance from facility $k$ to airport $a$ | km |

#### 2.3.7 Economic Parameters

| Symbol | Description | Unit |
|:------:|-------------|:----:|
| $r$ | Discount rate | - |
| $L$ | Project lifetime | years |
| $\tau$ | Duration of each time period | hours |

### 2.4 Decision Variables

#### 2.4.1 Continuous Variables

| Symbol | Description | Domain |
|:------:|-------------|:------:|
| $x^{H_2}_{i,t}$ | Hydrogen production at facility $i$ in period $t$ | $\mathbb{R}_+$ |
| $x^{CO_2}_{j,w}$ | CO₂ supply from source $j$ in week $w$ | $\mathbb{R}_+$ |
| $x^{MeOH}_{k,t}$ | Methanol production at facility $k$ in period $t$ | $\mathbb{R}_+$ |
| $x^{SAF}_{k,t}$ | SAF production at facility $k$ in period $t$ | $\mathbb{R}_+$ |
| $y^{H_2,m}_{i,k,t}$ | H₂ flow from $i$ to $k$ via mode $m$ in period $t$ | $\mathbb{R}_+$ |
| $y^{CO_2,m}_{j,k,w}$ | CO₂ flow from $j$ to $k$ via mode $m$ in week $w$ | $\mathbb{R}_+$ |
| $y^{SAF}_{k,a,w}$ | SAF flow from $k$ to airport $a$ in week $w$ | $\mathbb{R}_+$ |
| $I^{MeOH}_{k,t}$ | Methanol inventory at facility $k$ in period $t$ | $\mathbb{R}_+$ |
| $I^{CO_2}_{k,t}$ | CO₂ inventory at facility $k$ in period $t$ | $\mathbb{R}_+$ |
| $Q_k$ | Installed capacity at facility $k$ | $\mathbb{R}_+$ |
| $s_{a,w}$ | Shortage quantity at airport $a$ in week $w$ | $\mathbb{R}_+$ |

#### 2.4.2 Binary Variables

| Symbol | Description | Domain |
|:------:|-------------|:------:|
| $z_k$ | Facility location decision at site $k$ | $\{0,1\}$ |
| $z^{pipe}_{i,k}$ | Pipeline construction from H₂ source $i$ to $k$ | $\{0,1\}$ |
| $z^{pipe}_{j,k}$ | Pipeline construction from CO₂ source $j$ to $k$ | $\{0,1\}$ |

---

## 3. Mathematical Formulation

### 3.1 Objective Function

Minimize total supply chain cost:

$$\min Z = C_{H_2} + C_{CO_2} + C_{trans} + C_{prod} + C_{inv} + C_{fac} + C_{short}$$

where:

**Hydrogen Production Cost:**
$$C_{H_2} = \sum_{t \in \mathcal{T}} \sum_{i \in \mathcal{I}} c^{H_2}_i \cdot x^{H_2}_{i,t}$$

**CO₂ Capture Cost:**
$$C_{CO_2} = \sum_{w \in \mathcal{W}} \sum_{j \in \mathcal{J}} c^{CO_2}_j \cdot x^{CO_2}_{j,w}$$

**Transportation Cost:**
$$C_{trans} = \sum_{t,i,k,m} c^{trans}_m(d_{i,k}) \cdot y^{H_2,m}_{i,k,t} + \sum_{w,j,k,m} c^{trans}_m(d_{j,k}) \cdot y^{CO_2,m}_{j,k,w} + \sum_{w,k,a} c^{trans}(d_{k,a}) \cdot y^{SAF}_{k,a,w}$$

**Production Cost:**
$$C_{prod} = \sum_{t \in \mathcal{T}} \sum_{k \in \mathcal{K}} \left( c^{MeOH} \cdot x^{MeOH}_{k,t} + c^{SAF} \cdot x^{SAF}_{k,t} \right)$$

**Inventory Holding Cost:**
$$C_{inv} = \sum_{t \in \mathcal{T}} \sum_{k \in \mathcal{K}} \left( c^{inv}_{MeOH} \cdot I^{MeOH}_{k,t} + c^{inv}_{CO_2} \cdot I^{CO_2}_{k,t} \right)$$

**Facility Investment Cost (Annualized):**
$$C_{fac} = CRF \cdot \sum_{k \in \mathcal{K}} \left( C^{fix} \cdot z_k + C^{var} \cdot Q_k \right) \cdot \frac{|\mathcal{W}|}{52}$$

where the Capital Recovery Factor is:
$$CRF = \frac{r(1+r)^L}{(1+r)^L - 1}$$

**Shortage Penalty Cost:**
$$C_{short} = \sum_{w \in \mathcal{W}} \sum_{a \in \mathcal{A}} c^{short} \cdot s_{a,w}$$

### 3.2 Constraints

#### 3.2.1 Hydrogen Supply Constraints

**Electrolysis Capacity (Renewable Energy Limited):**
$$x^{H_2}_{i,t} \leq \frac{P_{i,t} \cdot \tau}{\eta^{elec}}, \quad \forall i \in \mathcal{I}^{elec}, t \in \mathcal{T}$$

**Industrial Byproduct Hydrogen Supply:**
$$x^{H_2}_{i,t} \leq \gamma^{avail}_i \cdot \bar{Q}^{byp}_{i,t}, \quad \forall i \in \mathcal{I}^{byp}, t \in \mathcal{T}$$

**Natural Gas Reforming Hydrogen Production:**
$$x^{H_2}_{i,t} = \gamma^{ref}_{H_2} \cdot x^{NG}_{i,t}, \quad \forall i \in \mathcal{I}^{ref}, t \in \mathcal{T}$$

**Hydrogen Flow Balance:**
$$x^{H_2}_{i,t} = \sum_{k \in \mathcal{K}} \sum_{m \in \mathcal{M}} y^{H_2,m}_{i,k,t}, \quad \forall i \in \mathcal{I}, t \in \mathcal{T}$$

#### 3.2.2 Carbon Dioxide Supply Constraints

**Industrial Point Source Capture:**
$$x^{CO_2}_{j,w} \leq \gamma^{cap}_j \cdot \bar{S}^{CO_2}_{j,w}, \quad \forall j \in \mathcal{J}^{ind}, w \in \mathcal{W}$$

**Direct Air Capture (Energy Limited):**
$$x^{DAC}_{k,t} \leq \frac{P^{avail}_{k,t} \cdot \tau}{E^{dac}}, \quad \forall k \in \mathcal{K}, t \in \mathcal{T}$$

**Coal Gasification CO₂ Generation:**
$$x^{CO_2}_{k,t} = \gamma^{coal} \cdot x^{coal}_{k,t}, \quad \forall k \in \mathcal{K}^{gas}, t \in \mathcal{T}$$

**Natural Gas Reforming CO₂ Generation:**
$$x^{CO_2}_{i,t} = \gamma^{ref}_{CO_2} \cdot x^{NG}_{i,t}, \quad \forall i \in \mathcal{I}^{ref}, t \in \mathcal{T}$$

**CO₂ Flow Balance:**
$$x^{CO_2}_{j,w} = \sum_{k \in \mathcal{K}} \sum_{m \in \mathcal{M}} y^{CO_2,m}_{j,k,w}, \quad \forall j \in \mathcal{J}, w \in \mathcal{W}$$

#### 3.2.3 Production Constraints — MTJ Pathway

**Methanol Synthesis (H₂ Balance):**
$$\alpha^{H_2 \to MeOH} \cdot x^{MeOH}_{k,t} \leq \sum_{i \in \mathcal{I}} \sum_{m \in \mathcal{M}} y^{H_2,m}_{i,k,t}, \quad \forall k \in \mathcal{K}^{MTJ}, t \in \mathcal{T}$$

**Methanol Synthesis (CO₂ Balance):**
$$\alpha^{CO_2 \to MeOH} \cdot x^{MeOH}_{k,t} \leq I^{CO_2}_{k,t-1} + \frac{1}{H_w} \sum_{j \in \mathcal{J}} \sum_{m \in \mathcal{M}} y^{CO_2,m}_{j,k,w(t)}, \quad \forall k \in \mathcal{K}^{MTJ}, t \in \mathcal{T}$$

**Methanol-to-Jet Conversion:**
$$x^{SAF}_{k,t} = \beta^{MeOH} \cdot x^{MeOH,cons}_{k,t}, \quad \forall k \in \mathcal{K}^{MTJ}, t \in \mathcal{T}$$

**Methanol Inventory Balance:**
$$I^{MeOH}_{k,t} = I^{MeOH}_{k,t-1} + x^{MeOH}_{k,t} - x^{MeOH,cons}_{k,t}, \quad \forall k \in \mathcal{K}^{MTJ}, t \in \mathcal{T}$$

#### 3.2.4 Production Constraints — FT Direct Synthesis Pathway

**Hydrogen Consumption:**
$$\alpha^{H_2}_{FT} \cdot x^{SAF}_{k,t} \leq \sum_{i \in \mathcal{I}} \sum_{m \in \mathcal{M}} y^{H_2,m}_{i,k,t}, \quad \forall k \in \mathcal{K}^{FT}, t \in \mathcal{T}$$

**CO₂ Consumption:**
$$\alpha^{CO_2}_{FT} \cdot x^{SAF}_{k,t} \leq I^{CO_2}_{k,t-1} + \frac{1}{H_w} \sum_{j \in \mathcal{J}} \sum_{m \in \mathcal{M}} y^{CO_2,m}_{j,k,w(t)}, \quad \forall k \in \mathcal{K}^{FT}, t \in \mathcal{T}$$

#### 3.2.5 CO₂ Inventory Balance (Temporal Aggregation)

$$I^{CO_2}_{k,t} = I^{CO_2}_{k,t-1} + \frac{1}{H_w} \sum_{j \in \mathcal{J}} \sum_{m \in \mathcal{M}} y^{CO_2,m}_{j,k,w(t)} - \phi^{CO_2}_{k,t}, \quad \forall k \in \mathcal{K}, t \in \mathcal{T}$$

where $\phi^{CO_2}_{k,t}$ denotes the CO₂ consumption in period $t$:
$$\phi^{CO_2}_{k,t} = \begin{cases} \alpha^{CO_2 \to MeOH} \cdot x^{MeOH}_{k,t} & \text{if } k \in \mathcal{K}^{MTJ} \\ \alpha^{CO_2}_{FT} \cdot x^{SAF}_{k,t} & \text{if } k \in \mathcal{K}^{FT} \end{cases}$$

#### 3.2.6 Inventory Capacity Constraints

$$I^{MeOH}_{k,t} \leq \bar{I}^{MeOH}_k, \quad \forall k \in \mathcal{K}, t \in \mathcal{T}$$

$$I^{CO_2}_{k,t} \leq \bar{I}^{CO_2}_k, \quad \forall k \in \mathcal{K}, t \in \mathcal{T}$$

#### 3.2.7 Transportation Capacity Constraints

**Pipeline Transportation:**
$$y^{H_2,pipe}_{i,k,t} \leq \bar{Y}^{pipe} \cdot z^{pipe}_{i,k}, \quad \forall i \in \mathcal{I}, k \in \mathcal{K}, t \in \mathcal{T}$$

$$y^{CO_2,pipe}_{j,k,w} \leq \bar{Y}^{pipe} \cdot z^{pipe}_{j,k}, \quad \forall j \in \mathcal{J}, k \in \mathcal{K}, w \in \mathcal{W}$$

**Truck Transportation:**
$$y^{H_2,truck}_{i,k,t} \leq \bar{Y}^{truck}, \quad \forall i \in \mathcal{I}, k \in \mathcal{K}, t \in \mathcal{T}$$

$$y^{CO_2,truck}_{j,k,w} \leq \bar{Y}^{truck}, \quad \forall j \in \mathcal{J}, k \in \mathcal{K}, w \in \mathcal{W}$$

#### 3.2.8 Facility Capacity Constraints

**Production-Capacity Linkage:**
$$x^{SAF}_{k,t} \leq Q_k \cdot \tau, \quad \forall k \in \mathcal{K}, t \in \mathcal{T}$$

**Capacity-Location Linkage:**
$$\underline{Q}^{SAF} \cdot z_k \leq Q_k \leq \bar{Q}^{SAF} \cdot z_k, \quad \forall k \in \mathcal{K}$$

**Minimum Annual Production (Economies of Scale):**
$$\sum_{t \in \mathcal{T}} x^{SAF}_{k,t} \geq \underline{P}^{annual} \cdot z_k, \quad \forall k \in \mathcal{K}$$

#### 3.2.9 Demand Satisfaction Constraints

**Demand Fulfillment (Soft Constraint):**
$$\sum_{k \in \mathcal{K}} y^{SAF}_{k,a,w} + s_{a,w} \geq D_{a,w}, \quad \forall a \in \mathcal{A}, w \in \mathcal{W}$$

**SAF Production-Distribution Balance:**
$$\sum_{t \in \mathcal{T}_w} x^{SAF}_{k,t} \geq \sum_{a \in \mathcal{A}} y^{SAF}_{k,a,w}, \quad \forall k \in \mathcal{K}, w \in \mathcal{W}$$

#### 3.2.10 Initial Conditions

$$I^{MeOH}_{k,0} = 0, \quad \forall k \in \mathcal{K}$$

$$I^{CO_2}_{k,0} = 0, \quad \forall k \in \mathcal{K}$$

#### 3.2.11 Non-negativity and Integrality

$$x^{H_2}_{i,t}, x^{CO_2}_{j,w}, x^{MeOH}_{k,t}, x^{SAF}_{k,t}, y^{(\cdot)}_{(\cdot)}, I^{(\cdot)}_{(\cdot)}, Q_k, s_{a,w} \geq 0$$

$$z_k, z^{pipe}_{i,k}, z^{pipe}_{j,k} \in \{0, 1\}$$

---

## 4. Model Variants

The general formulation above can be specialized into multiple configurations based on hydrogen source, CO₂ source, and synthesis pathway selection.

### 4.1 Classification Framework

| Variant | Hydrogen Source | CO₂ Source | Synthesis Pathway |
|:-------:|-----------------|------------|-------------------|
| **H-1** | Electrolysis (Renewable) | Coal Gasification | MTJ |
| **H-2** | Electrolysis (Renewable) | Direct Air Capture | MTJ |
| **H-3** | Electrolysis (Renewable) | Direct Air Capture | FT-DS |
| **H-4** | Natural Gas Reforming | Reforming Byproduct | MTJ |
| **H-5** | Natural Gas Reforming | Reforming Byproduct | FT-DS |
| **H-6** | Electrolysis (Renewable) | Industrial CCS | MTJ |
| **H-7** | Electrolysis (Renewable) | Industrial CCS | FT-DS |
| **B-1** | Industrial Byproduct | Coal Gasification | MTJ |
| **B-2** | Industrial Byproduct | Direct Air Capture | MTJ |
| **B-3** | Industrial Byproduct | Direct Air Capture | FT-DS |
| **B-4** | Industrial Byproduct + NG Reforming | Reforming Byproduct | MTJ |
| **B-5** | Industrial Byproduct + Electrolysis | Industrial CCS | MTJ |
| **B-6** | Industrial Byproduct + Electrolysis | Industrial CCS | FT-DS |

### 4.2 Variant-Specific Constraint Modifications

#### 4.2.1 Electrolysis-Based Variants (H-1 through H-7)

Active constraint sets: $\mathcal{I} = \mathcal{I}^{elec}$

Hydrogen production governed by renewable energy availability:
$$x^{H_2}_{i,t} \leq \frac{P_{i,t} \cdot \tau}{\eta^{elec}}, \quad \forall i \in \mathcal{I}^{elec}, t \in \mathcal{T}$$

#### 4.2.2 Industrial Byproduct Variants (B-1 through B-6)

Active constraint sets: $\mathcal{I}^{byp} \neq \emptyset$

**Steel Plant Byproduct Hydrogen:**
$$x^{H_2}_{i,t} \leq \gamma^{steel}_{avail} \cdot \bar{Q}^{steel}_{i,t}, \quad \forall i \in \mathcal{I}^{steel}$$

**Refinery Byproduct Hydrogen:**
$$x^{H_2}_{i,t} \leq \gamma^{ref}_{avail} \cdot \bar{Q}^{ref}_{i,t}, \quad \forall i \in \mathcal{I}^{refinery}$$

#### 4.2.3 Natural Gas Reforming Variants (H-4, H-5, B-4)

Active constraint sets: $\mathcal{I}^{ref} \neq \emptyset$

**Coupled H₂-CO₂ Production:**
$$x^{H_2}_{i,t} = \gamma^{ref}_{H_2} \cdot x^{NG}_{i,t}, \quad x^{CO_2}_{i,t} = \gamma^{ref}_{CO_2} \cdot x^{NG}_{i,t}$$

**Natural Gas Supply Constraint:**
$$x^{NG}_{l,w} \leq \bar{S}^{NG}_{l,w}, \quad \forall l \in \mathcal{L}^{LNG}, w \in \mathcal{W}$$

#### 4.2.4 Coal Gasification Variants (H-1, B-1)

CO₂ generated locally, eliminating CO₂ transportation:
$$x^{CO_2}_{k,t} = \gamma^{coal} \cdot x^{coal}_{k,t}, \quad y^{CO_2,m}_{j,k,w} = 0$$

#### 4.2.5 Direct Air Capture Variants (H-2, H-3, B-2, B-3)

CO₂ captured locally at production site:
$$x^{DAC}_{k,t} \leq \frac{P^{avail}_{k,t} \cdot \tau}{E^{dac}}, \quad y^{CO_2,m}_{j,k,w} = 0$$

#### 4.2.6 Industrial CCS Variants (H-6, H-7, B-5, B-6)

Full CO₂ transportation network activated:
$$x^{CO_2}_{j,w} \leq \gamma^{cap}_j \cdot \bar{S}^{CO_2}_{j,w}, \quad \forall j \in \mathcal{J}^{ind}$$

#### 4.2.7 Mixed Hydrogen Source Variants (B-4, B-5, B-6)

**Total Hydrogen Supply:**
$$x^{H_2,total}_{k,t} = \sum_{i \in \mathcal{I}^{byp}} y^{H_2}_{i,k,t} + \sum_{i \in \mathcal{I}^{elec} \cup \mathcal{I}^{ref}} y^{H_2}_{i,k,t}$$

### 4.3 Carbon Accounting Configuration

The carbon credit configuration parameter $\xi \in \{0, 1\}$ determines whether captured CO₂ qualifies as a carbon sink under lifecycle assessment:

| CO₂ Source Type | Carbon Credit ($\xi$) | Rationale |
|-----------------|:---------------------:|-----------|
| Coal Gasification | 0 | Fossil carbon origin |
| Natural Gas Reforming | 0 | Fossil carbon origin |
| Industrial CCS | 1 | Avoided emissions |
| Direct Air Capture | 1 | Atmospheric carbon removal |

**Carbon Sink Calculation:**
$$E^{sink} = \xi \cdot \sum_{w \in \mathcal{W}} \sum_{j \in \mathcal{J}} x^{CO_2}_{j,w}$$

---

## 5. Solution Methodology

### 5.1 Model Characteristics

- **Problem Type**: Mixed-Integer Linear Program (MILP)
- **Complexity**: NP-hard due to binary facility location decisions
- **Scale**: $O(|\mathcal{I}||\mathcal{K}||\mathcal{T}| + |\mathcal{J}||\mathcal{K}||\mathcal{W}|)$ continuous variables, $O(|\mathcal{K}| + |\mathcal{I}||\mathcal{K}| + |\mathcal{J}||\mathcal{K}|)$ binary variables

### 5.2 Preprocessing Techniques

1. **Spatial Clustering**: Apply density-based clustering (DBSCAN) to aggregate proximate supply sources
2. **Distance-Based Filtering**: Eliminate infeasible source-facility pairs exceeding maximum transportation distance
3. **Variable Fixing**: Pre-solve obvious location decisions based on demand proximity

### 5.3 Solver Configuration

The model is implemented using Gurobi Optimizer with the following recommended parameters:

- **MIPGap**: 0.01 (1% optimality tolerance)
- **TimeLimit**: 3600 seconds
- **Threads**: System-dependent (parallel branch-and-bound)
- **Presolve**: Aggressive

---

## 6. Model Extensions

### 6.1 Stochastic Programming Extension

Incorporate uncertainty in renewable energy availability:
$$\min_{\mathbf{z}} \mathbb{E}_{\omega} \left[ \min_{\mathbf{x}(\omega)} Z(\mathbf{z}, \mathbf{x}(\omega), \omega) \right]$$

### 6.2 Multi-Objective Extension

Consider simultaneous cost and carbon minimization:
$$\min \left( Z_{cost}, Z_{carbon} \right)$$

where:
$$Z_{carbon} = \sum_{i,t} e^{H_2}_i \cdot x^{H_2}_{i,t} + \sum_{j,w} e^{CO_2}_j \cdot x^{CO_2}_{j,w} - E^{sink}$$

### 6.3 Dynamic Capacity Expansion

Introduce time-indexed capacity decisions:
$$Q_{k,w} = Q_{k,w-1} + \Delta Q_{k,w}, \quad \forall k \in \mathcal{K}, w \in \mathcal{W}$$

---

## References

1. ICAO (2023). CORSIA Methodology for Calculating Actual Life Cycle Emissions Values
2. IEA (2024). Global Hydrogen Review
3. IRENA (2024). Green Hydrogen Cost Reduction: Scaling up Electrolysers
4. Global CCS Institute (2024). Global Status of CCS Report
5. Schmidt, P. et al. (2018). Power-to-Liquids: Potentials and Perspectives. *Energy & Environmental Science*

---

**Document End**
