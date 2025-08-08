@echo off
echo 启动GraphHopper服务...
echo.
echo 注意：请确保以下文件存在：
echo 1. graphhopper-web-9.1.jar （或其他版本）
echo 2. data/china-latest.osm.pbf
echo 3. config.yml
echo.

REM 检查Java是否安装
java -version >nul 2>&1
if errorlevel 1 (
    echo 错误：Java未安装或不在PATH中
    echo 请安装Java 8或更高版本
    pause
    exit /b 1
)

REM 检查OSM数据文件
if not exist "data\china-latest.osm.pbf" (
    echo 错误：OSM数据文件不存在: data\china-latest.osm.pbf
    echo.
    echo 请下载中国OSM数据文件：
    echo wget https://download.geofabrik.de/asia/china-latest.osm.pbf
    echo 并放置在 data\ 目录下
    pause
    exit /b 1
)

REM 检查GraphHopper JAR文件
if not exist "graphhopper-web-*.jar" (
    echo 错误：GraphHopper JAR文件不存在
    echo.
    echo 请下载GraphHopper：
    echo wget https://github.com/graphhopper/graphhopper/releases/download/9.1/graphhopper-web-9.1.jar
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
     -Ddw.graphhopper.datareader.file=data/china-latest.osm.pbf ^
     -Ddw.graphhopper.graph.location=./graph-cache ^
     -Ddw.server.applicationConnectors[0].port=8989 ^
     -jar graphhopper-web-*.jar server config.yml

pause