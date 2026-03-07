@echo off
REM ========================================
REM Chrome 9222 调试启动脚本
REM 使用前请修改下方的路径配置
REM ========================================

REM 你的 Chrome 路径
set CHROME_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe

REM 调试 Profile 存放目录（可自定义）
set CHROME_DEBUG_PROFILE=C:\ChromeDebugProfile

REM 原有 Chrome Profile 路径（首次运行需要手动修改为你的路径）
set CHROME_ORIGINAL_PROFILE=C:\Users\你的用户名\AppData\Local\Google\Chrome\User Data\Default

echo [1/3] Closing Chrome...
taskkill /F /IM chrome.exe 2>nul
timeout /t 2 /nobreak >nul

echo [2/3] Checking Profile...
if not exist "%CHROME_DEBUG_PROFILE%\Default" (
    echo First time setup - copying from original profile...
    xcopy "%CHROME_ORIGINAL_PROFILE%" "%CHROME_DEBUG_PROFILE%\Default" /E /I /Q /Y
) else (
    echo Profile exists, reusing...
)

echo [3/3] Starting Chrome 9222...
start "" "%CHROME_PATH%" --remote-debugging-port=9222 --user-data-dir="%CHROME_DEBUG_PROFILE%" --no-first-run --no-default-browser-check
