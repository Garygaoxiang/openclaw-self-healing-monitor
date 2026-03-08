@echo off
REM ========================================
REM Chrome 9223 调试启动脚本（自动加载 Browser Relay）
REM ========================================

REM 你的 Chrome 路径
set CHROME_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe

REM 调试 Profile 存放目录
set CHROME_DEBUG_PROFILE=C:\ChromeDebugProfile

REM Browser Relay 扩展路径（修改为你的实际路径）
set EXTENSION_PATH=F:\Scripts\openclaw-browser-relay-extension

echo [1/4] Closing Chrome...
taskkill /F /IM chrome.exe 2>nul
timeout /t 2 /nobreak >nul

echo [2/4] Checking Profile...
if not exist "%CHROME_DEBUG_PROFILE%\Default" (
    echo First time setup - copying from original profile...
    xcopy "C:\Users\你的用户名\AppData\Local\Google\Chrome\User Data\Default" "%CHROME_DEBUG_PROFILE%\Default" /E /I /Q /Y
) else (
    echo Profile exists, reusing...
)

echo [3/4] Checking Extension...
if not exist "%EXTENSION_PATH%" (
    echo [ERROR] Extension not found: %EXTENSION_PATH%
    echo [ERROR] Please check the extension path!
    pause
    exit /b 1
)

echo [4/4] Starting Chrome 9223 with Relay...
REM 关键：--load-extension 自动加载扩展
start "" "%CHROME_PATH%" --remote-debugging-port=9223 --user-data-dir="%CHROME_DEBUG_PROFILE%" --no-first-run --no-default-browser-check --load-extension="%EXTENSION_PATH%" --force-device-scale-factor=1

timeout /t 3 /nobreak >nul
echo [Done] Chrome 9223 launched with Relay!

REM 检查端口
netstat -an | findstr "9223" | findstr "LISTENING" >nul
if %errorlevel%==0 (
    echo [OK] Port 9223 is LISTENING
) else (
    echo [WARN] Port 9223 not detected yet...
)

echo.
echo ========================================
echo 如果扩展未自动连接，请在浏览器中点击
echo OpenClaw Browser Relay 扩展图标
echo ========================================
