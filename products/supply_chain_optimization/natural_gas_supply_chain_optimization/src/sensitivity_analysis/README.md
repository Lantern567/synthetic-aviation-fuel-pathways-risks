# 敏感性分析模块

## 概述

本模块用于对天然气供应链优化模型的关键参数进行敏感性分析，自动化批量运行模型并生成三维可视化图表。

## 功能特性

- **参数化分析**: 对`levelized_cost_threshold_yuan_per_kg`参数进行区间扫描（默认6.7-6.78，步长0.005）
- **自动化运行**: 批量调用优化模型，自动管理配置文件和结果文件
- **多维度指标**: 提取经济、需求、碳排放三个维度的关键指标
- **三维可视化**: 生成高质量的三维图表展示参数敏感性

## 文件结构

```
sensitivity_analysis/
├── __init__.py                      # 模块初始化文件
├── sensitivity_analysis.py          # 敏感性分析主程序
├── sensitivity_visualization.py     # 三维可视化模块
└── README.md                        # 本文件
```

## 使用方法

### 1. 基本用法

运行完整的敏感性分析：

```bash
cd products/supply_chain_optimization/natural_gas_supply_chain_optimization/src/sensitivity_analysis
python sensitivity_analysis.py
```

### 2. 自定义参数范围

修改代码中的参数：

```python
analyzer = SensitivityAnalyzer(
    param_min=6.7,      # 最小值
    param_max=6.78,     # 最大值
    param_step=0.005    # 步长
)
```

### 3. 单独生成可视化

如果已有敏感性分析结果，可以单独运行可视化：

```bash
python sensitivity_visualization.py <敏感性分析结果目录>

# 示例
python sensitivity_visualization.py ../../results/sensitivity_analysis_20250930_120000
```

## 输出结果

### 目录结构

```
results/sensitivity_analysis_YYYYMMDD_HHMMSS/
├── raw_results/                     # 原始结果文件
│   ├── complete_solution_paramX.XXX.json
│   ├── carbon_emissions_paramX.XXX.csv
│   └── ...
├── processed_data/                  # 整理后的数据
│   ├── complete_sensitivity_results.csv    # 完整结果
│   ├── economic_metrics.csv                # 经济指标
│   ├── demand_metrics.csv                  # 需求指标
│   └── carbon_metrics.csv                  # 碳排放指标
└── figures/                         # 可视化图表
    ├── economic_3d_analysis.png            # 经济性能三维图
    ├── demand_3d_analysis.png              # 需求满足度三维图
    └── carbon_3d_analysis.png              # 碳排放三维图
```

### 关键指标

#### 经济指标
- `lifecycle_levelized_cost`: 生命周期平准化成本（元/kg）
- `total_cost`: 生命周期总成本（元）
- `optimization_time`: 优化求解时间（秒）

#### 需求指标
- `demand_fulfillment_ratio`: 需求满足程度（0-1）

#### 碳排放指标
- `total_carbon_emission`: 总碳排放量（kg CO2eq）
- `carbon_intensity_mass`: 碳强度-质量基准（kg CO2eq/kg SAF）
- `carbon_intensity_energy`: 碳强度-能量基准（g CO2eq/MJ）

## 工作流程

1. **备份配置**: 自动备份原始配置文件
2. **参数扫描**: 遍历参数区间，每次修改配置文件
3. **模型运行**: 调用优化模型进行求解
4. **结果收集**: 复制并重命名结果文件
5. **指标提取**: 从JSON和CSV文件中提取关键指标
6. **数据整合**: 汇总所有运行结果
7. **生成图表**: 创建三维可视化图表
8. **恢复配置**: 恢复原始配置文件

## 注意事项

1. **运行时间**: 17个参数点，每次约10分钟，总计约3小时
2. **磁盘空间**: 确保有足够空间存储所有结果文件
3. **配置备份**: 程序自动备份和恢复配置，但建议手动备份重要配置
4. **错误处理**: 单次运行失败不会中断整个流程，会在日志中记录
5. **中断恢复**: 目前不支持断点续传，中断后需重新运行

## 依赖要求

- Python 3.12+
- numpy
- pandas
- matplotlib
- scipy (用于曲面拟合)
- pyyaml

## 故障排除

### 问题1: 配置文件修改失败
**解决**: 检查配置文件路径和权限

### 问题2: 模型运行超时
**解决**: 增加`timeout`参数（默认600秒）

### 问题3: 可视化中文乱码
**解决**: 确保系统安装了SimHei或Microsoft YaHei字体

### 问题4: 找不到结果文件
**解决**: 检查模型是否正常运行并生成结果文件

## 扩展功能

### 添加新的敏感性参数

修改`modify_config_parameter`方法：

```python
def modify_config_parameter(self, param_value: float):
    with open(self.config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    # 添加其他参数
    config['your_parameter_name'] = param_value

    with open(self.config_path, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, allow_unicode=True)
```

### 添加新的可视化指标

在`SensitivityVisualizer`类中添加新方法：

```python
def create_3d_your_metric_plot(self):
    # 实现新的三维图表
    pass
```

## 日志文件

日志文件保存在：
```
products/supply_chain_optimization/natural_gas_supply_chain_optimization/logs/
sensitivity_analysis_YYYYMMDD_HHMMSS.log
```

包含详细的运行信息、错误记录和性能统计。

## 联系方式

如有问题或建议，请通过项目Issues反馈。