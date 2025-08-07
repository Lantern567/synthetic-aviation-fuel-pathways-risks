@echo off
chcp 65001
echo 启动GraphHopper服务...
echo.
echo 检查Java环境...
java -version
if errorlevel 1 (
    echo Java环境不可用！
    pause
    exit /b 1
)

echo.
echo 检查必要文件...
if not exist "natural_gas_supply_chain_optimization\data\china-latest.osm.pbf" (
    echo OSM数据文件不存在！
    pause
    exit /b 1
)

if not exist "natural_gas_supply_chain_optimization\data\graphhopper-web-10.2.jar" (
    echo GraphHopper JAR文件不存在！
    pause
    exit /b 1
)

if not exist "config.yml" (
    echo 配置文件不存在！
    pause
    exit /b 1
)

echo.
echo 创建缓存目录...
if not exist "graph-cache" mkdir graph-cache

echo.
echo 启动GraphHopper服务（端口8989）...
echo 首次启动可能需要几分钟来处理OSM数据，请耐心等待...
echo 当您看到 "Server started" 消息时，表示服务启动成功
echo.

java -Xmx4g -Ddw.graphhopper.datareader.file=natural_gas_supply_chain_optimization/data/china-latest.osm.pbf -Ddw.graphhopper.graph.location=./graph-cache -Ddw.server.applicationConnectors[0].port=8989 -jar natural_gas_supply_chain_optimization/data/graphhopper-web-10.2.jar server config.yml

pause