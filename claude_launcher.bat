@echo off
setlocal enabledelayedexpansion

echo ====================================================
echo             Claude Code API 启动器
echo ====================================================
echo.

echo 请选择API端点:
echo.
echo 1. GAC Code (当前配置)
echo    URL: https://gaccode.com/claudecode
echo    密钥: sk-ant-oat01-8b1b9779ff075b50b427361ba2...
echo.
echo 2. CC Vibe Coding
echo    URL: https://cc-vibecoding.vip/
echo    密钥: sk-ccvb-code-sSWj-PanrM9XJTgNpLY7KKRQoVj...
echo.
echo 0. 退出
echo.

set /p choice="请输入选择 (0-2): "

if "%choice%"=="0" (
    echo 退出程序
    goto :end
)

if "%choice%"=="1" (
    set "API_URL=https://gaccode.com/claudecode"
    set "API_KEY=sk-ant-oat01-8b1b9779ff075b50b427361ba2e227e765e59768ddeb8bc6276f651e31431005"
    echo 选择了: GAC Code
) else if "%choice%"=="2" (
    set "API_URL=https://cc-vibecoding.vip/"
    set "API_KEY=sk-ccvb-code-sSWj-PanrM9XJTgNpLY7KKRQoVjPmOGTifGjcWzrAft-CjtWhTy1IxvHtoJpgRbATM9CzYOWkVmbk7e3NjwlIw"
    echo 选择了: CC Vibe Coding
) else (
    echo 无效选择！
    goto :end
)

echo.
echo 正在更新配置...

REM 使用Python脚本更新.claude.json配置
python -c "
import json
import os
from pathlib import Path

config_path = Path.home() / '.claude.json'
if config_path.exists():
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
else:
    config = {}

config['customApiUrl'] = '%API_URL%'

with open(config_path, 'w', encoding='utf-8') as f:
    json.dump(config, f, indent=2, ensure_ascii=False)

print('配置文件已更新')
"

if errorlevel 1 (
    echo 更新配置失败！
    goto :end
)

echo 设置环境变量...
set "ANTHROPIC_API_KEY=%API_KEY%"

echo.
echo 配置完成！正在启动 Claude Code...
echo.

REM 启动Claude Code
claude

:end
echo.
echo 按任意键退出...
pause >nul