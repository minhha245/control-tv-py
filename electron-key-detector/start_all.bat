@echo off
echo ========================================
echo Starting YouTube Key Detector
echo ========================================
echo.

echo [1/2] Starting YouTube Server on port 5001...
start "YouTube Server" cmd /k "python youtube_server.py"
timeout /t 3 /nobreak >nul

echo [2/2] Starting Electron App...
start "Electron App" cmd /k "npm start"

echo.
echo ========================================
echo Both services started!
echo ========================================
echo.
echo YouTube Server: http://127.0.0.1:5001
echo.
echo Press any key to stop all services...
pause >nul

echo.
echo Stopping services...
taskkill /FI "WINDOWTITLE eq YouTube Server*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Electron App*" /T /F >nul 2>&1

echo Done!
