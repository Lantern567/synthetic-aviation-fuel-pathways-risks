# 绿色甲醇港口运输项目

## 项目概述

本项目专注于绿色甲醇在港口运输中的应用研究，涵盖数据处理、分析建模和可视化等多个方面。项目采用模块化设计，将数据读入、处理、算法实现和结果保存完全分离，确保代码的可读性和可维护性。

## 项目结构

```
green_methanol_for_port_transportation/
├── airline_visualization/     # 🆕 航线数据可视化系统
├── air_port_data_process/     # 机场数据处理模块  
├── port_data_process/         # 港口数据处理模块
├── wind_speed/               # 风速数据处理模块
├── logs/                     # 项目日志文档
└── README.md                # 项目说明文档
```

## 核心模块

### 🚀 航线数据可视化系统 (airline_visualization)

**最新完成** - 基于pydeck库的交互式航班数据可视化系统

#### 功能特性
- 📊 **多样化可视化**：航线网络、机场分布、城市热力图、3D弧线效果
- 🔧 **智能数据处理**：自动清洗、坐标验证、异常值过滤
- 📈 **统计分析**：机型、机场、城市多维度统计报告
- 🎯 **高性能**：支持大数据文件的样本处理模式
- ✅ **完整测试**：100%测试覆盖，10个测试用例全部通过

#### 技术栈
- **可视化**：pydeck, HTML
- **数据处理**：pandas, numpy
- **测试框架**：pytest
- **输出格式**：HTML交互报告、Excel统计表格

#### 使用方法
```bash
cd airline_visualization
python main_flight_visualization.py
```

### 🛩️ 机场数据处理模块 (air_port_data_process)

该模块用于机场数据的读入、处理、分析与结果输出，结构参考port_data_process，包含data、src、results（含tables和figures）、logs、tests等子文件夹，详见air_port_data_process/README.md。

### 🚢 港口数据处理模块 (port_data_process)

港口相关数据的处理和分析功能。

### 🌪️ 风速数据处理模块 (wind_speed)

风速数据的采集、处理和分析功能。

## 环境配置

项目使用conda环境管理：

```bash
# 激活项目环境
conda activate green_methanol_for_port_transportation

# 或创建新环境（如果不存在）
conda create -n green_methanol_for_port_transportation python=3.12
conda activate green_methanol_for_port_transportation
```

### 主要依赖
- Python 3.12+
- pandas, numpy - 数据处理
- pydeck - 地理可视化
- matplotlib, seaborn - 图表绘制
- openpyxl - Excel文件处理
- pytest - 测试框架

## 项目特色

### 🎯 模块化设计
- **数据层**：统一的数据读入和预处理
- **算法层**：核心计算逻辑与业务分离
- **可视化层**：多样化的结果展示
- **测试层**：完整的单元测试覆盖

### 📁 标准化文件结构
每个模块都遵循统一的文件组织规范：
```
module_name/
├── src/           # 源代码
├── data/          # 数据文件
├── results/       # 结果输出
│   ├── tables/    # 表格数据
│   ├── charts/    # 图表文件
│   └── html_reports/ # HTML报告
├── tests/         # 测试文件
├── logs/          # 日志记录
└── algorithms/    # 算法实现
```

### 🔄 自动化工作流
- 自动化测试验证
- 日志文档更新
- Git版本控制
- 结果文件分类存储

## 最新更新

**2025-06-30**：
- ✅ 完成航线数据可视化系统开发
- ✅ 实现4种交互式可视化类型
- ✅ 生成完整的统计分析报告
- ✅ 100%测试覆盖率达成
- ✅ 项目文档和日志更新

## 贡献指南

1. 每次开发新功能时，优先检查现有模块是否可复用
2. 严格遵循项目的文件结构规范
3. 编写对应的单元测试
4. 更新相关文档和日志
5. 提交前运行完整测试套件

## 许可证

本项目用于学术研究目的。 