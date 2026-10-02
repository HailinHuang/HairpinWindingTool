@echo off
setlocal
cd /d "%~dp0"

set "PYINSTALLER=%~dp0..\..\.venv\Scripts\pyinstaller.exe"
set "MPLCONFIGDIR=%CD%\.matplotlib"
set "QT_API=pyqt6"
set "PYTHONDONTWRITEBYTECODE=1"

if not exist "%PYINSTALLER%" (
    echo ERROR: PyInstaller not found:
    echo   %PYINSTALLER%
    echo.
    echo Please check that the project virtual environment exists.
    pause
    exit /b 1
)

if not exist "%CD%\dist" mkdir "%CD%\dist"
if not exist "%CD%\build" mkdir "%CD%\build"

"%PYINSTALLER%" ^
    --noconfirm ^
    --clean ^
    --onefile ^
    --windowed ^
    --name WindingDesignTool_v7_6 ^
    --distpath "%CD%\dist" ^
    --workpath "%CD%\build\WindingDesignTool_v7_6" ^
    --specpath "%CD%\build\WindingDesignTool_v7_6" ^
    --add-data "%CD%\Pin_Info.csv;." ^
    --add-data "%CD%\connection_rules.html;." ^
    --add-data "%CD%\pattern_guide.html;." ^
    --add-data "%CD%\pattern_naa_division_layout.html;." ^
    --add-data "%CD%\pattern_route_inventory.json;." ^
    --add-data "%CD%\inductance_guide.html;." ^
    --add-data "%CD%\PATTERN_DEFINITIONS_AND_CONSTRAINTS.md;." ^
    --add-data "%CD%\PATTERN_DIVIDER_FORMULA_SUPPORT.md;." ^
    --add-data "%CD%\INTEGER_Q_DIVIDER_SUPPORT_STATUS.md;." ^
    --add-data "%CD%\assets\checkmark.svg;assets" ^
    --exclude-module PyQt5 ^
    --exclude-module PyQtWebEngine ^
    --exclude-module tkinter ^
    "main_pyqt6.py"

if errorlevel 1 (
    echo.
    echo Build failed.
    pause
    exit /b 1
)

echo.
echo Build completed:
echo   %CD%\dist\WindingDesignTool_v7_6.exe
pause
