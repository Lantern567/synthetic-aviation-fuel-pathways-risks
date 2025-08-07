# GraphHopper路径规划集成

本文档说明了如何将天然气供应链优化模型从百度地图路径规划切换到使用本地OSM数据和GraphHopper服务进行路径规划。

## 主要变更

### 1. 新增文件

- `src/graphhopper_routing_engine.py` - GraphHopper路径规划引擎
- `src/test_graphhopper_routing.py` - GraphHopper引擎单元测试
- `src/test_modified_optimization_model.py` - 修改后优化模型的测试
- `src/graphhopper_usage_example.py` - 使用示例
- `GRAPHHOPPER_INTEGRATION.md` - 本文档

### 2. 修改文件

- `src/natural_gas_optimization_model.py` - 主要优化模型文件

## 核心功能

### GraphHopper路径规划引擎特性

1. **本地OSM数据支持**
   - 使用本地OSM PBF文件（如`china-latest.osm.pbf`）
   - 通过HTTP API调用GraphHopper服务
   - 支持多种车辆类型（car, truck, bike, foot）

2. **路径规划功能**
   - 计算两点间的真实道路距离
   - 估算行驶时间
   - 获取完整的路径坐标信息
   - 支持距离矩阵计算

3. **缓存机制**
   - SQLite数据库缓存路径计算结果
   - 避免重复计算，提高性能
   - 支持路径坐标的存储和检索

4. **容错机制**
   - API调用失败时自动重试
   - 回退到直线距离估算
   - 详细的错误日志记录

## 使用方法

### 基本使用

```python
from graphhopper_routing_engine import GraphHopperRoutingEngine

# 创建路径规划引擎
engine = GraphHopperRoutingEngine(
    osm_pbf_path="data/china-latest.osm.pbf",
    graphhopper_host="localhost",
    graphhopper_port=8989
)

# 计算路径距离
result = engine.calculate_route_distance(
    39.9042, 116.4074,  # 北京
    31.2304, 121.4737,  # 上海
    vehicle="car",
    include_route_geometry=True
)

print(f"距离: {result['distance_km']} 公里")
print(f"时间: {result['time_hours']} 小时")
```

### 优化模型使用

```python
from natural_gas_optimization_model import NaturalGasSupplyChainOptimizer

# 创建优化器（新参数）
optimizer = NaturalGasSupplyChainOptimizer(
    time_horizon_weeks=1,
    use_graphhopper_routing=True,  # 启用GraphHopper
    osm_pbf_path="data/china-latest.osm.pbf",  # OSM数据文件路径
    graphhopper_host="localhost",  # GraphHopper服务主机
    graphhopper_port=8989,  # GraphHopper服务端口
    max_transport_distance_km=1000.0,
    use_routing_for_short_distance=True
)
```

## 参数对比

### 旧参数（百度地图）
```python
NaturalGasSupplyChainOptimizer(
    use_baidu_routing=True,
    baidu_api_key="your_api_key",
    use_api_for_short_distance=True
)
```

### 新参数（GraphHopper）
```python
NaturalGasSupplyChainOptimizer(
    use_graphhopper_routing=True,
    osm_pbf_path="data/china-latest.osm.pbf",
    graphhopper_host="localhost",
    graphhopper_port=8989,
    use_routing_for_short_distance=True
)
```

## 环境要求

### 1. GraphHopper服务

需要运行GraphHopper服务，可以通过以下方式启动：

```bash
# 下载GraphHopper
wget https://github.com/graphhopper/graphhopper/releases/download/9.1/graphhopper-web-9.1.jar

# 启动服务（使用本地OSM数据）
java -Ddw.graphhopper.datareader.file=data/china-latest.osm.pbf \
     -Ddw.graphhopper.graph.location=./graph-cache \
     -jar graphhopper-web-9.1.jar server config.yml
```

### 2. OSM数据文件

下载中国的OSM数据文件：
```bash
# 从Geofabrik下载
wget https://download.geofabrik.de/asia/china-latest.osm.pbf
```

### 3. Python依赖

```bash
pip install requests sqlite3 pandas numpy
```

## API变更说明

### 初始化参数变更

| 旧参数 | 新参数 | 说明 |
|--------|--------|------|
| `use_baidu_routing` | `use_graphhopper_routing` | 启用路径规划 |
| `baidu_api_key` | `osm_pbf_path` | API密钥 → 本地数据文件路径 |
| - | `graphhopper_host` | GraphHopper服务主机地址 |
| - | `graphhopper_port` | GraphHopper服务端口 |
| `use_api_for_short_distance` | `use_routing_for_short_distance` | 短距离精确计算开关 |

### 内部属性变更

| 旧属性 | 新属性 | 说明 |
|--------|--------|------|
| `baidu_engine` | `routing_engine` | 路径规划引擎实例 |
| `distance_stats['api_calls']` | `distance_stats['routing_calls']` | API调用次数统计 |

## 性能特点

### 优势
1. **本地数据** - 不依赖外部API，更快的响应速度
2. **无调用限制** - 没有API调用次数限制
3. **路径保存** - 可以保存完整的路径坐标信息
4. **离线工作** - 不需要网络连接

### 注意事项
1. **启动时间** - GraphHopper服务首次启动需要处理OSM数据，可能需要较长时间
2. **内存使用** - 大型OSM文件需要更多内存
3. **存储空间** - 需要存储OSM数据文件和图缓存

## 测试

运行测试以验证集成是否正确：

```bash
# 运行GraphHopper引擎测试
python src/test_graphhopper_routing.py

# 运行修改后的优化模型测试
python src/test_modified_optimization_model.py

# 运行使用示例
python src/graphhopper_usage_example.py
```

## 故障排除

### 常见问题

1. **GraphHopper服务连接失败**
   - 检查服务是否运行在正确的端口
   - 验证防火墙设置
   - 查看GraphHopper服务日志

2. **OSM数据文件问题**
   - 确认文件路径正确
   - 检查文件是否完整下载
   - 验证文件格式（应为.osm.pbf）

3. **性能问题**
   - 启用缓存机制
   - 对大批量计算使用距离矩阵方法
   - 调整GraphHopper服务的内存设置

### 调试信息

启用详细日志以获取更多调试信息：

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 兼容性

这个集成保持了与原有API的最大兼容性：
- 主要的公共方法签名未改变
- 返回的数据结构保持一致
- 错误处理机制类似

只需要修改初始化参数即可从百度地图切换到GraphHopper。

## 扩展功能

GraphHopper集成还提供了一些额外功能：

1. **路径可视化支持** - 获取完整路径坐标用于地图可视化
2. **多种车辆类型** - 支持汽车、卡车、自行车、步行等
3. **路径保存** - 将路径结果保存为JSON文件
4. **统计信息** - 详细的调用统计和性能指标

这些功能为未来的扩展和优化提供了更多可能性。