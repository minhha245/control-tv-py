@echo off
echo ========================================
echo Installing Audio Format Support
echo ========================================
echo.

echo Installing soundfile and audioread...
pip install soundfile audioread

echo.
echo ========================================
echo Installation Complete!
echo ========================================
echo.
echo Now librosa can read webm, opus, m4a files
echo.
pause
