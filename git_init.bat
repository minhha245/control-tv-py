@echo off
echo ========================================
echo Git Initialize
echo ========================================
echo.

echo Initializing git repository...
git init

echo.
echo Setting up remote (if needed)...
echo Enter your GitHub repository URL (or press Enter to skip):
set /p REPO_URL=

if not "%REPO_URL%"=="" (
    echo Adding remote origin...
    git remote add origin %REPO_URL%
    echo Remote added: %REPO_URL%
) else (
    echo Skipped remote setup
)

echo.
echo ========================================
echo Git initialized!
echo ========================================
echo.
echo Next steps:
echo   1. Run git_commit.bat to commit
echo   2. Run: git push -u origin main
echo.
pause
