@echo off
chcp 65001 >nul
title Clawdbot Monitor GUI Build

echo ========================================
echo   Clawdbot Monitor GUI 打包工具
echo ========================================
echo.

cd /d "%~dp0"

echo 正在检查依赖...
python -c "import customtkinter; import pyinstaller" 2>nul
if errorlevel 1 (
    echo 安装依赖...
    pip install customtkinter pyinstaller
)

echo.
echo 开始打包...
echo.

pyinstaller clawdbot-monitor.spec --clean

if errorlevel 1 (
    echo.
    echo 打包失败!
    pause
    exit /b 1
)

echo.
echo ========================================
echo   打包完成!
echo ========================================
echo.
echo 输出目录: dist\ClawdbotMonitor
echo.
echo 双击 ClawdbotMonitor.exe 运行
echo.

pause
