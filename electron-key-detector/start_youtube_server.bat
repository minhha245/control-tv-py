@echo off
echo Installing dependencies...
pip install -r requirements.txt

echo.
echo Starting YouTube Key Detection Server...
python youtube_server.py
