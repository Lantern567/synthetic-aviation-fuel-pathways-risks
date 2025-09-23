# MTJTechnologyManager 使用指南

## 概述

MTJTechnologyManager是一个独立的技术管理类，专门负责管理MTJ（甲醇制航空燃料）技术的参数、配置和分析功能。该类从主要的优化模型中提取出来，提供了清晰的API来处理所有MTJ技术相关操作。

## 核心功能

1. **技术参数加载与管理** - 从配置文件加载技术参数
2. **技术筛选与查询** - 根据条件筛选和查询技术
3. **成本计算与分析** - 计算生产成本和进行技术比较
4. **位置映射管理** - 管理技术与适用位置的映射关系
5. **统计分析** - 提供技术性能统计和分析

## 初始化

### 基本初始化
```python
from shared.data_pipeline import DataPipeline
from products.supply_chain_optimization.natural_gas_supply_chain_optimization.src.natural_gas_optimization_model import MTJTechnologyManager

# 创建数据管道
pipeline = DataPipeline()

# 初始化MTJ技术管理器
mtj_manager = MTJTechnologyManager(
    data_pipeline=pipeline,
    economic_params={},  # 可选
    costs={},           # 可选
    logger_obj=None     # 可选，会创建默认日志记录器
)
```

### 与主优化器集成
```python
from products.supply_chain_optimization.natural_gas_supply_chain_optimization.src.natural_gas_optimization_model import NaturalGasSupplyChainOptimizer

# 创建优化器（会自动初始化MTJ技术管理器）
optimizer = NaturalGasSupplyChainOptimizer(data_pipeline=pipeline)
optimizer.load_data()  # 触发MTJ技术管理器的初始化

# 访问MTJ技术管理器
mtj_manager = optimizer.mtj_tech_manager
```

## 核心方法使用

### 1. 技术查询与获取

```python
# 获取所有技术
all_technologies = mtj_manager.get_all_technologies()
print(f"总共有 {len(all_technologies)} 个MTJ技术")

# 获取特定技术
pipeline_tech = mtj_manager.get_technology('pipeline_direct_conversion')
if pipeline_tech:
    print(f"技术名称: {pipeline_tech['name']}")
    print(f"LCOP: {pipeline_tech['lcop_yuan_per_kg']} 元/kg")
    print(f"效率: {pipeline_tech['efficiency']}")
```

### 2. 技术筛选

```python
# 筛选不需要氢气运输的技术
no_h2_transport = mtj_manager.filter_technologies(hydrogen_transport_required=False)
print(f"找到 {len(no_h2_transport)} 个不需要氢气运输的技术")

# 筛选适用于机场的技术
airport_suitable = mtj_manager.filter_technologies(suitable_locations=['airport'])
print(f"适用于机场的技术: {len(airport_suitable)} 个")

# 筛选高效率技术（效率>80%）
high_efficiency = mtj_manager.filter_technologies(min_efficiency=0.8)
print(f"高效率技术: {len(high_efficiency)} 个")
```

### 3. 成本计算

```python
# 计算特定技术的生产成本
tech_id = 'pipeline_direct_conversion'
production_kg = 1000  # 生产1000kg航空燃料

cost_result = mtj_manager.calculate_production_cost(tech_id, production_kg)

print(f"技术: {cost_result['technology_name']}")
print(f"总成本: {cost_result['total_cost_yuan']} 元")
print(f"单位成本: {cost_result['unit_cost_yuan_per_kg']} 元/kg")
print(f"实际产出: {cost_result['actual_output_kg']} kg")
print(f"资源消耗:")
print(f"  - 天然气: {cost_result['resource_consumption']['natural_gas_m3']} m³")
print(f"  - 氢气: {cost_result['resource_consumption']['hydrogen_kg']} kg")
print(f"  - 甲醇: {cost_result['resource_consumption']['methanol_kg']} kg")
```

### 4. 技术比较

```python
# 比较多种技术
tech_ids = ['pipeline_direct_conversion', 'airport_integrated_conversion', 'lng_terminal_conversion']
comparison = mtj_manager.compare_technologies(tech_ids, production_kg=1000)

print("技术比较结果:")
for result in comparison['comparison_results']:
    print(f"- {result['technology_name']}: {result['total_cost_yuan']} 元")

print(f"最低成本技术: {comparison['lowest_cost_technology']['name']}")
print(f"最高效率技术: {comparison['most_efficient_technology']['name']}")
```

### 5. 位置映射

```python
# 假设有一些位置数据
locations = {
    'solar_plant_1': {'type': 'solar_plant', 'name': '太阳能电站1'},
    'airport_1': {'type': 'airport', 'name': '首都机场'},
    'wind_farm_1': {'type': 'wind_farm', 'name': '风电场1'},
}

# 建立位置映射
location_mappings = mtj_manager.build_location_mappings(locations)

print("位置映射结果:")
for tech_id, loc_list in location_mappings.items():
    tech_name = mtj_manager.get_technology(tech_id)['name']
    print(f"- {tech_name}: {len(loc_list)} 个适用位置")
```

### 6. 统计分析

```python
# 获取统计信息
stats = mtj_manager.get_summary_statistics()
print("MTJ技术统计信息:")
for key, value in stats.items():
    print(f"- {key}: {value}")

# 分析特定技术性能
tech_id = 'pipeline_direct_conversion'
analysis = mtj_manager.analyze_technology_performance(tech_id)
print(f"\n{analysis['technology_name']} 性能分析:")
print(f"- 相对成本水平: {analysis['cost_relative_to_average']}")
print(f"- 相对效率水平: {analysis['efficiency_relative_to_average']}")
print(f"- 成本效率比: {analysis['cost_efficiency_ratio']}")
```

## 技术配置文件

MTJ技术参数存储在 `shared/mtj_aviation_fuel_technologies.json` 文件中：

```json
{
  "meta": {
    "description": "MTJ航煤生产技术参数配置",
    "base_lcop_yuan_per_kg": 808.0,
    "last_updated": "2025-08-30",
    "technology_type": "E-CRM+TRM"
  },
  "technologies": {
    "pipeline_direct_conversion": {
      "name": "E-CRM+TRM MTJ航煤生产（在可再生能源站）",
      "lcop_yuan_per_kg": 808.0,
      "efficiency": 0.85,
      "ng_consumption_ratio": 0.8,
      "h2_consumption_ratio": 0.12,
      "methanol_intermediate_ratio": 1.2,
      "suitable_locations": ["solar_plant", "wind_farm"],
      "transport_mode": "pipeline_direct",
      "hydrogen_transport_required": false
    }
    // ... 其他技术配置
  }
}
```

## 可用的MTJ技术

1. **pipeline_direct_conversion** - E-CRM+TRM MTJ航煤生产（在可再生能源站）
2. **airport_integrated_conversion** - E-CRM+TRM MTJ航煤生产（机场集成）
3. **lng_terminal_conversion** - E-CRM+TRM MTJ航煤生产（LNG接收站）
4. **lng_to_hplant_conversion** - E-CRM+TRM MTJ航煤生产（LNG转运+可再生能源站）
5. **integrated_supply_conversion** - E-CRM+TRM MTJ航煤生产（综合供应）

## 向后兼容性

原有的技术管理方法仍然可用，但会产生deprecation警告：

```python
# 这种用法仍然有效，但不推荐
optimizer._define_technologies()  # 会产生警告
```

## 错误处理

```python
try:
    # 查询不存在的技术
    tech = mtj_manager.get_technology('non_existent_tech')
    if tech is None:
        print("技术不存在")
        
    # 计算成本
    cost = mtj_manager.calculate_production_cost('invalid_tech', 1000)
except ValueError as e:
    print(f"参数错误: {e}")
except Exception as e:
    print(f"其他错误: {e}")
```

## 测试

运行单元测试：
```bash
python -m pytest test_mtj_technology_manager.py -v
```

运行集成测试：
```bash
python test_mtj_only_integration.py
```

## 总结

MTJTechnologyManager提供了一个强大而灵活的接口来管理MTJ技术相关的所有操作。通过模块化设计，它可以轻松集成到更大的供应链优化系统中，同时也可以作为独立工具使用。