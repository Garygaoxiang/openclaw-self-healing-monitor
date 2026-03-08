@echo off
REM OpenClaw 双浏览器启动脚本
REM 同时启动 9222 和 9223 两个 Chrome 实例

echo [1/3] 启动 Chrome 9222...
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\ChromeDebugProfile" --no-first-run --no-default-browser-check --load-extension="F:\Scripts\openclaw-browser-relay-extension"

echo [2/3] 启动 Chrome 9223...
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9223 --user-data-dir="C:\ChromeDebugProfile_9223" --no-first-run --no-default-browser-check --load-extension="F:\Scripts\openclaw-browser-relay-extension"

echo [3/3] 等待启动...
timeout /t 3 /nobreak >nul

echo.
echo ========================================
echo Chrome 9222 和 9223 已启动！
echo 9222: 主浏览器（发文章用）
echo 9223: 监控脚本专用
echo ========================================
