@echo off
REM ========================================
REM Chrome 9222 调试启动脚本（支持 Browser Relay）
REM ========================================

REM 你的 Chrome 路径
set CHROME_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe

REM 调试 Profile 存放目录
set CHROME_DEBUG_PROFILE=C:\ChromeDebugProfile

REM Browser Relay 扩展路径（自动加载）
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
    echo [WARN] Extension not found at: %EXTENSION_PATH%
    echo [WARN] Browser Relay will not be loaded!
)

echo [4/4] Starting Chrome 9222 with Relay...
REM 关键：添加 --load-extension 自动加载扩展
if exist "%EXTENSION_PATH%" (
    start "" "%CHROME_PATH%" --remote-debugging-port=9222 --user-data-dir="%CHROME_DEBUG_PROFILE%" --no-first-run --no-default-browser-check --load-extension="%EXTENSION_PATH%"
) else (
    start "" "%CHROME_PATH%" --remote-debugging-port=9222 --user-data-dir="%CHROME_DEBUG_PROFILE%" --no-first-run --no-default-browser-check
)

timeout /t 3 /nobreak >nul
echo [Done] Chrome 9222 launched!

REM 检查端口
netstat -an | findstr "9222" | findstr "LISTENING" >nul
if %errorlevel%==0 (
    echo [OK] Port 9222 is LISTENING
) else (
    echo [WARN] Port 9222 not detected yet...
)

echo.
echo ========================================
echo Tips:
echo - 确保已在扩展中配置 Gateway Token
echo - 访问 chrome://extensions 可查看扩展状态
echo ========================================
