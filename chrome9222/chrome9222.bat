@echo off
echo [1/3] Closing Chrome...
taskkill /F /IM chrome.exe 2>nul
timeout /t 2 /nobreak >nul

echo [2/3] Checking Profile...
if not exist "C:\ChromeDebugProfile\Default" (
    echo First time setup...
    xcopy "C:\Users\GaryPC\AppData\Local\Google\Chrome\User Data\Default" "C:\ChromeDebugProfile\Default" /E /I /Q /Y
) else (
    echo Profile exists
)

echo [3/3] Starting Chrome 9222...
set CHROME_EXE=C:\Program Files\Google\Chrome\Application\chrome.exe
set CHROME_PROFILE=C:\ChromeDebugProfile

start "" "%CHROME_EXE%" --remote-debugging-port=9222 --user-data-dir="%CHROME_PROFILE%" --no-first-run --no-default-browser-check --disable-extensions

timeout /t 3 /nobreak >nul
echo [Done] Chrome launched, verifying port 9222...
netstat -an | findstr "9222" | findstr "LISTENING" >nul
if %errorlevel%==0 (
    echo [OK] Port 9222 is LISTENING
) else (
    echo [WARN] Port 9222 not detected yet, Chrome may still be loading...
)
