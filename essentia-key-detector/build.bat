@echo off
echo ========================================
echo Building Essentia Key Detector
echo ========================================

echo.
echo Step 1: Installing Python dependencies...
pip install -r requirements.txt

echo.
echo Step 2: Building Python server executable...
python build_server.py

echo.
echo Step 3: Installing Node dependencies...
call npm install

echo.
echo Step 4: Building Electron app...
call npm run build:win

echo.
echo ========================================
echo Build complete!
echo ========================================
echo.
echo Installer: release\Essentia Key Detector Setup 1.0.0.exe
echo.
pause
