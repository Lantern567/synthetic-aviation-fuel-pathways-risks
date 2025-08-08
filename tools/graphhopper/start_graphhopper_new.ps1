Write-Host "启动GraphHopper服务..." -ForegroundColor Green

# 检查Java是否安装
try {
    java -version 2>$null
    Write-Host "Java环境检查通过" -ForegroundColor Green
} catch {
    Write-Host "错误：Java未安装或不在PATH中" -ForegroundColor Red
    exit 1
}

# 检查必要文件
$osmFile = "natural_gas_supply_chain_optimization\data\china-latest.osm.pbf"
$jarFile = "natural_gas_supply_chain_optimization\data\graphhopper-web-10.2.jar"
$configFile = "config.yml"

if (-not (Test-Path $osmFile)) {
    Write-Host "错误：OSM数据文件不存在: $osmFile" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $jarFile)) {
    Write-Host "错误：GraphHopper JAR文件不存在: $jarFile" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $configFile)) {
    Write-Host "警告：配置文件不存在: $configFile" -ForegroundColor Yellow
}

# 创建图缓存目录
if (-not (Test-Path "graph-cache")) {
    New-Item -ItemType Directory -Path "graph-cache"
    Write-Host "创建图缓存目录: graph-cache" -ForegroundColor Green
}

Write-Host "启动GraphHopper服务（端口8989）..." -ForegroundColor Green
Write-Host "首次启动可能需要几分钟来处理OSM数据，请耐心等待..." -ForegroundColor Yellow
Write-Host "服务启动后将在 http://localhost:8989 上可用" -ForegroundColor Cyan

# 启动GraphHopper服务
$arguments = @(
    "-Xmx4g",
    "-Ddw.graphhopper.datareader.file=natural_gas_supply_chain_optimization/data/china-latest.osm.pbf",
    "-Ddw.graphhopper.graph.location=./graph-cache",
    "-Ddw.server.applicationConnectors[0].port=8989",
    "-jar",
    "natural_gas_supply_chain_optimization/data/graphhopper-web-10.2.jar",
    "server",
    "config.yml"
)

Start-Process -FilePath "java" -ArgumentList $arguments -Wait