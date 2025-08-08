@echo off
echo 启动GraphHopper服务...
echo.

REM 检查Java是否安装
java -version >nul 2>&1
if errorlevel 1 (
    echo 错误：Java未安装或不在PATH中
    pause
    exit /b 1
)

REM 检查OSM数据文件
if not exist "natural_gas_supply_chain_optimization\data\china-latest.osm.pbf" (
    echo 错误：OSM数据文件不存在
    pause
    exit /b 1
)

REM 检查GraphHopper JAR文件
if not exist "natural_gas_supply_chain_optimization\data\graphhopper-web-10.2.jar" (
    echo 错误：GraphHopper JAR文件不存在
    pause
    exit /b 1
)

REM 创建图缓存目录
if not exist "graph-cache" mkdir graph-cache

echo 启动GraphHopper服务（端口8989）...
echo 首次启动可能需要几分钟来处理OSM数据...
echo.

REM 启动GraphHopper服务
java -Xmx4g ^
     -Ddw.graphhopper.datareader.file=natural_gas_supply_chain_optimization/data/china-latest.osm.pbf ^
     -Ddw.graphhopper.graph.location=./graph-cache ^
     -Ddw.server.applicationConnectors[0].port=8989 ^
     -jar natural_gas_supply_chain_optimization/data/graphhopper-web-10.2.jar server config.yml

pause