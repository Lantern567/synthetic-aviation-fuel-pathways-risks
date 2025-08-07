# GraphHopper服务手动启动指南

由于bash环境存在一些问题，这里提供手动启动GraphHopper服务的详细指令。

## 🚀 启动方法

### 方法1：使用命令提示符(推荐)

1. **打开命令提示符**
   - 按 `Win + R`，输入 `cmd`，按回车
   - 或者右键点击开始菜单，选择"命令提示符"

2. **切换到项目目录**
   ```cmd
   cd /d "D:\Green methanol\green_methanol_for_port_transportation-main\green_methanol_for_port_transportation-main"
   ```

3. **启动GraphHopper服务**
   ```cmd
   java -Xmx4g -Ddw.graphhopper.datareader.file=natural_gas_supply_chain_optimization/data/china-latest.osm.pbf -Ddw.graphhopper.graph.location=./graph-cache -Ddw.server.applicationConnectors[0].port=8989 -jar natural_gas_supply_chain_optimization/data/graphhopper-web-10.2.jar server config.yml
   ```

### 方法2：使用PowerShell

1. **打开PowerShell**
   - 按 `Win + X`，选择"Windows PowerShell"
   - 或者在开始菜单搜索"PowerShell"

2. **切换到项目目录**
   ```powershell
   Set-Location "D:\Green methanol\green_methanol_for_port_transportation-main\green_methanol_for_port_transportation-main"
   ```

3. **启动GraphHopper服务**
   ```powershell
   java -Xmx4g `
        "-Ddw.graphhopper.datareader.file=natural_gas_supply_chain_optimization/data/china-latest.osm.pbf" `
        "-Ddw.graphhopper.graph.location=./graph-cache" `
        "-Ddw.server.applicationConnectors[0].port=8989" `
        -jar "natural_gas_supply_chain_optimization/data/graphhopper-web-10.2.jar" server config.yml
   ```

### 方法3：双击批处理文件

直接双击以下任一文件：
- `start_graphhopper_service.bat`
- `start_graphhopper_simple.bat`

## ⏱️ 启动过程

### 首次启动（10-30分钟）
GraphHopper需要处理1.3GB的中国OSM数据，这个过程需要时间：

1. **数据读取阶段**
   ```
   INFO  [main] com.graphhopper.GraphHopper: start creating graph from natural_gas_supply_chain_optimization/data/china-latest.osm.pbf
   INFO  [main] com.graphhopper.reader.osm.OSMReader: using CH speedup. RAM usage optimized.
   ```

2. **图形处理阶段**
   ```
   INFO  [main] com.graphhopper.GraphHopper: time pass:XXs, 
   INFO  [main] com.graphhopper.GraphHopper: graph.nodes:X,XXX,XXX, graph.edges:X,XXX,XXX
   ```

3. **启动完成标志**
   ```
   INFO  [main] org.eclipse.jetty.server.Server: Started @XXXXXms
   ```

### 后续启动（30秒-2分钟）
一旦图形缓存建立，后续启动会很快。

## ✅ 验证服务运行

### 1. 查看日志输出
启动成功后，你会看到：
```
INFO  [main] org.eclipse.jetty.server.Server: Started @12345ms  
```

### 2. 访问Web界面
打开浏览器访问：http://localhost:8989

### 3. 检查API健康状态
访问：http://localhost:8989/health

### 4. 使用Python测试
```python
python test_graphhopper_service.py
```

## 🔧 常见问题解决

### Java未找到
**错误**: `'java' is not recognized as an internal or external command`

**解决方案**:
1. 确保已安装Java 8或更高版本
2. 将Java添加到PATH环境变量
3. 或使用Java的完整路径，例如：
   ```cmd
   "C:\Program Files\Java\jdk-11.0.1\bin\java.exe" -Xmx4g ...
   ```

### 端口被占用
**错误**: `Port 8989 already in use`

**解决方案**:
1. 修改config.yml中的端口号
2. 或杀死占用端口的进程：
   ```cmd
   netstat -ano | findstr :8989
   taskkill /PID <PID> /F
   ```

### 内存不足
**错误**: `OutOfMemoryError`

**解决方案**:
- 增加内存分配：将 `-Xmx4g` 改为 `-Xmx6g` 或 `-Xmx8g`

### 文件路径问题
**错误**: 找不到文件

**解决方案**:
1. 确保所有文件都在正确位置
2. 使用绝对路径
3. 检查文件权限

## 📊 服务状态监控

### 检查进程
```cmd
tasklist | findstr java
```

### 检查端口
```cmd
netstat -an | findstr :8989
```

### 检查日志
服务启动后会在命令行窗口显示实时日志。

## 🎯 下一步

一旦服务启动成功：

1. **测试路径计算**
   ```python
   python test_graphhopper_service.py
   ```

2. **使用路径规划功能**
   ```python
   from natural_gas_supply_chain_optimization.src.graphhopper_routing_engine import GraphHopperRoutingEngine
   
   engine = GraphHopperRoutingEngine()
   result = engine.calculate_route_distance(39.9042, 116.4074, 31.2304, 121.4737)
   print(f"北京到上海: {result['distance_km']:.1f}公里")
   ```

3. **运行优化模型**
   ```python
   from natural_gas_supply_chain_optimization.src.natural_gas_optimization_model import NaturalGasSupplyChainOptimizer
   
   optimizer = NaturalGasSupplyChainOptimizer(use_graphhopper_routing=True)
   # 使用优化器...
   ```

## 💡 提示

- 保持命令行窗口打开，服务运行期间不要关闭
- 首次启动请耐心等待数据处理完成
- 服务启动后，之前的警告消息将消失
- 可以开启多个命令行窗口同时使用服务

现在您可以享受无限制的本地路径规划功能了！