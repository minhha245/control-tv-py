@echo off
setlocal ENABLEDELAYEDEXPANSION

REM ==============================
REM CONFIG
REM ==============================
set APP_NAME=BangDieuKhienAudio
set MAIN_PY=controller_gui.py
set ICON=NONE
set VERSION_FILE=version.txt

REM ==============================
REM AUTO VERSION
REM ==============================
if not exist %VERSION_FILE% (
    echo 1 > %VERSION_FILE%
)

set /p VER=<%VERSION_FILE%
set /a NEW_VER=%VER%+1
echo %NEW_VER% > %VERSION_FILE%

echo =========================================
echo BUILD %APP_NAME% - VERSION v%NEW_VER%
echo =========================================

REM ==============================
REM CLEAN OLD BUILD
REM ==============================
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul
del /q *.spec 2>nul

REM ==============================
REM BUILD
REM ==============================
echo [1/2] BUILDING EXE (OPTIMIZED)...

python -m PyInstaller ^
 --onefile ^
 --windowed ^
 --clean ^
 --noupx ^
 --name "%APP_NAME%_v%NEW_VER%" ^
 --icon=%ICON% ^
 --exclude-module tkinter.test ^
 --exclude-module unittest ^
 --exclude-module email ^
 --exclude-module http ^
 --exclude-module xml ^
 --exclude-module pydoc ^
 --exclude-module setuptools ^
 --exclude-module distutils ^
 --exclude-module numpy ^
 --exclude-module cv2 ^
 --exclude-module pyautogui ^
 --exclude-module pygetwindow ^
 %MAIN_PY%

if %errorlevel% neq 0 (
    echo BUILD FAILED!
    pause
    exit /b
)

REM ==============================
REM COPY DATA FILES
REM ==============================
echo [2/2] COPYING DATA FILES...

if exist config.json copy /Y config.json dist\
if exist autokey_coords.json copy /Y autokey_coords.json dist\
if exist license.dat copy /Y license.dat dist\

echo.
echo =========================================
echo DONE! FILE EXE:
echo dist\%APP_NAME%_v%NEW_VER%.exe
echo =========================================
pause
