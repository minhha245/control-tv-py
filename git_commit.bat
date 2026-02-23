@echo off
echo ========================================
echo Git Commit Helper
echo ========================================
echo.

echo Checking git status...
git status

echo.
echo ========================================
echo Adding files...
echo ========================================
git add .

echo.
echo ========================================
echo Files to be committed:
echo ========================================
git status

echo.
echo ========================================
echo Committing...
echo ========================================
git commit -m "feat: Add YouTube Auto Detector with cleanup and optimization

- Add YouTube browser integration with Selenium
- Auto-detect key from YouTube videos
- Download audio using yt-dlp (native format, no conversion)
- Auto-fallback: Essentia server -> librosa
- Cleanup: Remove 1244 lines of duplicate code
- Add comprehensive documentation
- Add audio format support (soundfile, audioread)
- Optimize download workflow (1 step instead of 2)
- Add .gitignore and README.md

Features:
- Click YOUTUBE button -> Chrome opens automatically
- Click video -> Auto-detect URL change
- Auto-download and analyze
- Display results on AUTO-KEY panel
- Auto-cleanup temp files

Fixes:
- Fix yt-dlp import error (use Python API)
- Fix audio format support (add soundfile/audioread)
- Fix Essentia server m4a error (auto-fallback)
- Fix code duplication (clean 2945 -> 1701 lines)

Documentation:
- HUONG_DAN_YOUTUBE_INTEGRATION.md
- FIX_AUDIO_FORMAT.md
- YOUTUBE_SIMPLE_METHOD.md
- DEBUG_YOUTUBE.md
- CLEANUP_SUMMARY.md
- README.md"

echo.
echo ========================================
echo Commit completed!
echo ========================================
echo.
echo To push to remote:
echo   git push origin main
echo.
pause
