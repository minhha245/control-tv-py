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
del /q *.spec 2>nul

REM ==============================
REM BUILD
REM ==============================
echo [1/2] BUILDING EXE (OPTIMIZED)...

C:\Python311\python.exe -m PyInstaller ^
 --onedir ^
 --windowed ^
 --clean ^
 --name "%APP_NAME%_v%NEW_VER%" ^
 --icon=%ICON% ^
 --add-data "autokey_tool;autokey_tool" ^
 --collect-all librosa ^
 --collect-all pyaudiowpatch ^
 --collect-all soundfile ^
 --collect-all audioread ^
 --collect-all soxr ^
 --hidden-import=pkg_resources.extern ^
 --hidden-import=sklearn.utils._typedefs ^
 --hidden-import=sklearn.neighbors._partition_nodes ^
 --hidden-import=scipy.signal ^
 --hidden-import=scipy.fft ^
 --hidden-import=scipy.ndimage ^
 --hidden-import=numba ^
 --exclude-module tkinter.test ^
 --exclude-module cv2 ^
 --exclude-module pyautogui ^
 --exclude-module pygetwindow ^
 --exclude-module matplotlib ^
 --exclude-module PIL ^
 %MAIN_PY%

if %errorlevel% neq 0 (
    echo BUILD FAILED!
    pause
    exit /b
)

set DIST_DIR=dist\%APP_NAME%_v%NEW_VER%

REM ==============================
REM COPY DATA FILES
REM ==============================
echo [2/2] COPYING DATA FILES...

if exist config.json copy /Y config.json %DIST_DIR%\
if exist autokey_coords.json copy /Y autokey_coords.json %DIST_DIR%\
if exist license.dat copy /Y license.dat %DIST_DIR%\

echo.
echo =========================================
echo DONE! FILE EXE:
echo dist\%APP_NAME%_v%NEW_VER%.exe
echo =========================================
pause
