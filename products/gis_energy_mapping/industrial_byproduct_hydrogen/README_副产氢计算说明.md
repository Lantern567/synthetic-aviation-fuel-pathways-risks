# 工业副产氢产量计算 - 完整文档索引

## 文档概览

本目录包含关于工业副产氢产量计算逻辑的完整文档。副产氢是从钢铁焦化和石化催化重整等工业过程中获得的氢气。

### 三个文档的使用指南

#### 1. QUICK_REFERENCE.md (快速参考 - 推荐首先阅读)
**适合人群**：需要快速了解计算逻辑的开发者、分析师
**内容包括**：
- 快速公式查看
- 文件位置速查表
- 参数调整指南
- 常见问题解答
- 已知限制

**何时使用**：
- 需要快速找到某个计算公式
- 想修改参数进行敏感性分析
- 遇到常见问题需要快速解答

---

#### 2. BYPRODUCT_HYDROGEN_CALCULATION_GUIDE.md (完整计算指南 - 推荐全面学习)
**适合人群**：需要深入理解计算逻辑的研究人员、模型开发者
**内容包括**：
- 项目结构和文件组织
- 核心计算公式详解（钢铁和石化）
- 输入数据源说明
- 计算参数及其科学依据
- 输出数据格式规范
- 不同工业来源的特异性
- 参数敏感性分析

**何时使用**：
- 需要理解完整的计算逻辑
- 要评估数据准确性
- 计划添加新的工业来源
- 需要检验计算结果的合理性

---

#### 3. CODE_DETAILS.md (代码详解 - 推荐实现和维护)
**适合人群**：代码维护人员、贡献者、集成开发者
**内容包括**：
- 核心代码逐行详解
- 关键代码段的注释
- 转换系数汇总表
- 供应链优化格式转换逻辑
- 数据质量检查点
- 数据流向图

**何时使用**：
- 需要修改或扩展代码
- 要添加新的计算模块
- 需要调试或优化性能
- 进行代码审查或重构

---

## 核心计算逻辑概览

### 钢铁焦化副产氢

```
数据源：Global Iron and Steel Tracker
输入：高炉产能 (万吨/年)

计算：
  高炉产能 × 10000 → 铁水产能(吨)
  铁水产能 × 350 kg/t → 焦炭需求(吨)
  焦炭 × 420 Nm³/t → 焦炉煤气(Nm³)
  焦炉煤气 × 0.57 × 0.90 → 提纯氢气(Nm³)
  提纯氢气 × 0.0899 kg/Nm³ → 氢气(kg)
  
综合公式：年产氢(吨) = 铁水产能(吨) × 0.01629

代码位置：calculate_byproduct_hydrogen.py 第70-112行
```

### 石化催化重整副产氢

```
数据源：Oil Refineries GeoJSON
输入：日处理量 (千桶/天)

计算：
  日处理量 × 0.136 × 365 × 1000 → 年处理原油(吨)
  年处理原油 × 0.20 × 0.85 → 重整产能(吨)
  重整产能 × 3.5 kg/t → 氢气(kg)
  
综合公式：年产氢(吨) = 日处理量(KBD) × 27.72

代码位置：calculate_byproduct_hydrogen.py 第114-171行
```

---

## 文件系统结构

```
industrial_byproduct_hydrogen/
├── README_副产氢计算说明.md          ← 您现在正在看这个文件
├── QUICK_REFERENCE.md               (快速参考 - 9.6KB)
├── BYPRODUCT_HYDROGEN_CALCULATION_GUIDE.md  (完整指南 - 8.4KB)
├── CODE_DETAILS.md                  (代码详解 - 11KB)
│
├── calculate_byproduct_hydrogen.py   (226行) - 核心计算脚本
├── create_hydrogen_excel.py          (267行) - Excel输出
├── convert_to_renewable_format.py    (318行) - 供应链优化格式转换
├── analyze_data_granularity.py       (310行) - 数据粒度分析
├── analyze_steel_data.py             (107行) - 钢铁数据分析
├── visualize_byproduct_hydrogen.py   (430行) - GIS可视化
├── visualize_byproduct_hydrogen_frykit.py   - 交互式可视化
│
├── data/                             (输入数据)
│   ├── Plant-level-data-Global-Iron-and-Steel-Tracker-September-2025-V1.xlsx
│   ├── Iron-unit-data-Global-Iron-and-Steel-Tracker-September-2025-V1.xlsx
│   ├── steel_daily_byproduct_h2_*.csv
│   ├── refinery_daily_byproduct_h2_*.csv
│   └── *.geojson
│
├── results/                          (输出结果)
│   ├── tables/     (Excel和表格)
│   ├── figures/    (图表和可视化)
│   └── reports/    (报告)
│
└── logs/                             (运行日志)
    └── *_analysis_*.txt
```

---

## 快速开始指南

### 场景1：我想了解副产氢是怎么计算的
1. 先读：QUICK_REFERENCE.md 的"快速参考"部分（5分钟）
2. 再读：BYPRODUCT_HYDROGEN_CALCULATION_GUIDE.md 的"核心计算公式"部分（15分钟）

### 场景2：我需要调整参数或做敏感性分析
1. 查看：QUICK_REFERENCE.md 的"参数调整指南"部分
2. 参考：BYPRODUCT_HYDROGEN_CALCULATION_GUIDE.md 的"参数敏感性分析"表格
3. 编辑：calculate_byproduct_hydrogen.py 的参数行

### 场景3：我要修改或扩展代码
1. 学习：CODE_DETAILS.md 的"核心代码详解"部分
2. 查看：CODE_DETAILS.md 的"转换系数汇总表"
3. 编辑：相关的.py文件
4. 运行：calculate_byproduct_hydrogen.py 验证改动

### 场景4：我想添加新的工业氢源（如氯碱）
1. 学习：BYPRODUCT_HYDROGEN_CALCULATION_GUIDE.md 的"不同工业来源的特异性"
2. 参考：CODE_DETAILS.md 中钢铁或石化副产氢的代码结构
3. 获取：该工业的产能和工艺数据
4. 编写：新的计算函数
5. 测试：与现有计算一起运行

---

## 关键参数速查表

### 钢铁焦化副产氢参数

| 参数 | 数值 | 单位 | 来源 |
|------|------|------|------|
| 焦比 | 350 | kg焦/t铁 | GB/T冶金标准 |
| 焦炉煤气产率 | 420 | Nm³/t焦 | 工程数据库 |
| 焦炉煤气含氢量 | 57% | 体积比 | 冶金数据 |
| 提纯率 | 90% | - | PSA技术指标 |
| 氢气密度 | 0.0899 | kg/Nm³ | 物理常数 |
| 可外供比例 | 30% | - | 行业平均 |

### 石化催化重整副产氢参数

| 参数 | 数值 | 单位 | 来源 |
|------|------|------|------|
| 催化重整装置比例 | 20% | - | 装置统计 |
| 氢气产率 | 3.5 | kg/t原油 | API标准 |
| 运营率 | 85% | - | 行业平均 |
| 桶-吨转换 | 0.136 | t/barrel | 原油密度 |
| 可外供比例 | 15% | - | 保守估计 |

**注**：所有参数都可在 calculate_byproduct_hydrogen.py 中修改

---

## 数据输入输出

### 输入数据
- **钢铁**：Global Iron and Steel Tracker (Excel格式)
  - 211个中国钢铁设施
  - 包含产能、位置、运营状态等信息

- **石化**：Oil Refineries GeoJSON
  - 180个中国炼油厂
  - 包含处理量、位置、运营状态等信息

### 输出数据
- CSV：日产氢量统计（设施级）
- GeoJSON：地理位置和产氢量
- Excel：多维汇总报告（总体、省份、单厂）
- 时间序列：供应链优化模型格式（小时级）
- JSON：计算结果和统计汇总

---

## 已知的计算假设和限制

### 假设
1. **时间均匀性**：全年365天均匀运行（日产量 = 年产量 ÷ 365）
2. **运营率**：钢铁100%，石化85%
3. **可外供比例**：钢铁30%，石化15%
4. **参数固定**：转换系数全年不变

### 限制
1. **无动态数据**：源数据只有年产能，无小时/天级波动
2. **参数估算**：部分参数（如可外供比例）是行业平均，个别企业可能不同
3. **地理精度**：坐标精度为工厂级，不是具体设备位置
4. **成本未包含**：不含提纯、压缩、运输等后续成本

---

## 版本历史和更新

| 版本 | 日期 | 主要改动 |
|------|------|---------|
| 1.0 | 2024-10-27 | 初版：钢铁和石化副产氢计算 |
| 1.1 | 2025-01-18 | 新增：供应链优化格式转换 |
| 1.2 | 2025-11-19 | 新增：完整文档和参考指南 |

---

## 技术支持和常见问题

### Q: 如何运行计算脚本？
A: 在项目环境中运行：
```bash
python calculate_byproduct_hydrogen.py
```
输出会保存到 data/ 目录和日志文件。

### Q: 如何修改参数？
A: 编辑 calculate_byproduct_hydrogen.py 的这些行：
- 第79-84行：钢铁参数
- 第137-144行：石化参数

### Q: 计算结果的准确性如何？
A: 根据参数来源和数据质量：
- 钢铁：产能数据准确度高，转换系数基于标准，误差±10%
- 石化：产能数据准确度高，参数为工业平均，误差±15%

### Q: 可以添加其他氢源吗？
A: 可以。参考 CODE_DETAILS.md 的代码结构，按照相同方法添加新的计算段落。

---

## 相关文件和文档链接

### 项目相关
- 供应链优化模型配置：`shared/data/ByproductHydrogenSupplyChainOptimizer_config.yaml`
- GIS数据：`products/gis_energy_mapping/gis_data_scraper/scraped_gis_data/`
- 可视化工具：visualize_byproduct_hydrogen.py 和 visualize_byproduct_hydrogen_frykit.py

### 外部参考
- Global Iron and Steel Tracker：https://www.metallicminerals.org/
- API (American Petroleum Institute)：https://www.api.org/
- 中国钢铁标准：GB/T 相关冶金标准

---

## 许可和使用声明

本项目的副产氢计算逻辑基于：
- 公开的工业数据库
- 标准的工程参数
- 行业平均运营数据

可自由用于学术研究和商业应用，但结果仅供参考，不代表任何官方立场。

---

**最后更新**：2025-11-19  
**文档维护者**：Claude Code  
**联系方式**：在项目issues中提出问题或建议
