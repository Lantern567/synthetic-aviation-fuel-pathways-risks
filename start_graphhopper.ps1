# GraphHopper服务启动脚本
Write-Host "========================================" -ForegroundColor Green
Write-Host "启动GraphHopper路径规划服务" -ForegroundColor Green  
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

# 设置工作目录
$workDir = "D:\Green methanol\green_methanol_for_port_transportation-main\green_methanol_for_port_transportation-main"
Set-Location $workDir
Write-Host "工作目录: $workDir" -ForegroundColor Yellow

# 检查Java
Write-Host "检查Java安装..." -ForegroundColor Cyan
try {
    $javaVersion = java -version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] Java已安装" -ForegroundColor Green
        Write-Host "    $($javaVersion[0])" -ForegroundColor Gray
    } else {
        Write-Host "[ERROR] Java未正确安装" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "[ERROR] Java未安装或不在PATH中" -ForegroundColor Red
    exit 1
}

# 检查文件
Write-Host "`n检查必要文件..." -ForegroundColor Cyan
$jarPath = "natural_gas_supply_chain_optimization\data\graphhopper-web-10.2.jar"
$osmPath = "natural_gas_supply_chain_optimization\data\china-latest.osm.pbf"
$configPath = "config.yml"

if (-not (Test-Path $jarPath)) {
    Write-Host "[ERROR] JAR文件不存在: $jarPath" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] JAR文件存在: $jarPath" -ForegroundColor Green

if (-not (Test-Path $osmPath)) {
    Write-Host "[ERROR] OSM数据文件不存在: $osmPath" -ForegroundColor Red
    exit 1
}
$osmSize = [math]::Round((Get-Item $osmPath).Length / 1MB, 1)
Write-Host "[OK] OSM数据文件存在: $osmPath ($osmSize MB)" -ForegroundColor Green

if (-not (Test-Path $configPath)) {
    Write-Host "[WARNING] 配置文件不存在: $configPath" -ForegroundColor Yellow
} else {
    Write-Host "[OK] 配置文件存在: $configPath" -ForegroundColor Green
}

# 创建缓存目录
$cacheDir = "graph-cache"
if (-not (Test-Path $cacheDir)) {
    Write-Host "创建图缓存目录: $cacheDir" -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $cacheDir -Force | Out-Null
} else {
    Write-Host "[OK] 图缓存目录已存在: $cacheDir" -ForegroundColor Green
}

# 显示启动信息
Write-Host "`n启动配置:" -ForegroundColor Yellow
Write-Host "  OSM数据文件: $osmPath"
Write-Host "  服务端口: 8989"
Write-Host "  图缓存目录: $cacheDir"
Write-Host "  内存分配: 4GB"
Write-Host ""
Write-Host "首次启动可能需要10-30分钟来处理OSM数据，请耐心等待..." -ForegroundColor Yellow
Write-Host "看到 'Started @' 消息后表示启动成功" -ForegroundColor Yellow
Write-Host "然后可以访问: http://localhost:8989" -ForegroundColor Cyan
Write-Host "按Ctrl+C停止服务" -ForegroundColor Yellow
Write-Host "`n========================================" -ForegroundColor Green

# 启动GraphHopper服务
try {
    Write-Host "正在启动GraphHopper服务..." -ForegroundColor Green
    
    $process = Start-Process -FilePath "java" -ArgumentList @(
        "-Xmx4g",
        "-Ddw.graphhopper.datareader.file=$osmPath",
        "-Ddw.graphhopper.graph.location=./graph-cache",
        "-Ddw.server.applicationConnectors[0].port=8989",
        "-jar", $jarPath,
        "server", $configPath
    ) -NoNewWindow -PassThru -Wait
    
    Write-Host "`nGraphHopper服务已停止" -ForegroundColor Yellow
    
} catch {
    Write-Host "`n[ERROR] 启动失败: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host "`n按任意键退出..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")