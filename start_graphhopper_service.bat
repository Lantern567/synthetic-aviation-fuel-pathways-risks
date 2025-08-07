@echo off
echo ========================================
echo 启动GraphHopper路径规划服务
echo ========================================
echo.

REM 检查Java是否安装
echo 检查Java安装...
java -version >nul 2>&1
if errorlevel 1 (
    echo [错误] Java未安装或不在PATH中
    echo 请安装Java 8或更高版本
    pause
    exit /b 1
)
echo [OK] Java已安装

REM 检查JAR文件
set JAR_PATH=natural_gas_supply_chain_optimization\data\graphhopper-web-10.2.jar
if not exist "%JAR_PATH%" (
    echo [错误] GraphHopper JAR文件不存在: %JAR_PATH%
    pause
    exit /b 1
)
echo [OK] GraphHopper JAR文件存在

REM 检查OSM数据文件
set OSM_PATH=natural_gas_supply_chain_optimization\data\china-latest.osm.pbf
if not exist "%OSM_PATH%" (
    echo [错误] OSM数据文件不存在: %OSM_PATH%
    pause
    exit /b 1
)
echo [OK] OSM数据文件存在

REM 检查配置文件
if not exist "config.yml" (
    echo [提示] config.yml不存在，将使用默认配置
)

REM 创建图缓存目录
if not exist "graph-cache" (
    echo 创建图缓存目录...
    mkdir graph-cache
)

echo.
echo 配置信息:
echo   OSM数据文件: %OSM_PATH%
echo   JAR文件: %JAR_PATH%
echo   服务端口: 8989
echo   图缓存目录: graph-cache
echo.
echo 启动GraphHopper服务...
echo 首次启动可能需要10-30分钟来处理OSM数据，请耐心等待
echo 看到 "Started @" 消息后表示启动成功
echo 然后可以访问: http://localhost:8989
echo.
echo 按Ctrl+C停止服务
echo ========================================

REM 启动GraphHopper服务
java -Xmx4g ^
     -Ddw.graphhopper.datareader.file=%OSM_PATH% ^
     -Ddw.graphhopper.graph.location=./graph-cache ^
     -Ddw.server.applicationConnectors[0].port=8989 ^
     -jar %JAR_PATH% server config.yml

echo.
echo GraphHopper服务已停止
pause