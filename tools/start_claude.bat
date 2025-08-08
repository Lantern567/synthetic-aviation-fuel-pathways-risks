@echo off
echo 启动 Claude Code API 选择器...
echo.

REM 检查Python是否可用
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误：未找到Python，请确保Python已安装并添加到PATH
    pause
    exit /b 1
)

REM 运行API选择器
python "%~dp0claude_api_selector.py"

echo.
echo 按任意键退出...
pause >nul