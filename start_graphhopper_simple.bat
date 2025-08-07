@echo off
echo Starting GraphHopper Service...
echo ===============================

REM Change to the correct directory first
cd /d "D:\Green methanol\green_methanol_for_port_transportation-main\green_methanol_for_port_transportation-main"

REM Check if Java is available
java -version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Java not found or not in PATH
    pause
    exit /b 1
)
echo [OK] Java is available

REM Check if JAR file exists
if not exist "natural_gas_supply_chain_optimization\data\graphhopper-web-10.2.jar" (
    echo [ERROR] GraphHopper JAR file not found
    pause
    exit /b 1
)
echo [OK] GraphHopper JAR file found

REM Check if OSM data exists
if not exist "natural_gas_supply_chain_optimization\data\china-latest.osm.pbf" (
    echo [ERROR] OSM data file not found
    pause
    exit /b 1
)
echo [OK] OSM data file found

REM Create graph cache directory if it doesn't exist
if not exist "graph-cache" (
    echo Creating graph cache directory...
    mkdir graph-cache
)

echo.
echo Starting GraphHopper service...
echo This may take 10-30 minutes for first run
echo Service will be available at: http://localhost:8989
echo Press Ctrl+C to stop the service
echo.

REM Start GraphHopper with proper parameters
java -Xmx4g ^
     "-Ddw.graphhopper.datareader.file=natural_gas_supply_chain_optimization/data/china-latest.osm.pbf" ^
     "-Ddw.graphhopper.graph.location=./graph-cache" ^
     "-Ddw.server.applicationConnectors[0].port=8989" ^
     -jar "natural_gas_supply_chain_optimization/data/graphhopper-web-10.2.jar" server config.yml

echo.
echo GraphHopper service stopped
pause