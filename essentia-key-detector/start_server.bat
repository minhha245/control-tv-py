@echo off
echo Installing Python dependencies...
pip install -r requirements.txt

echo.
echo Starting Audio Processing Server...
python audio_server.py
