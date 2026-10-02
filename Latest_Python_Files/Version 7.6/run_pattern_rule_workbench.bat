@echo off
setlocal
cd /d "%~dp0"
set "MPLCONFIGDIR=%CD%\.matplotlib"
set "QT_API=pyqt6"
if not exist "%~dp0..\..\.venv\Scripts\python.exe" (
    echo Project Python environment not found: "%~dp0..\..\.venv\Scripts\python.exe"
    pause
    exit /b 1
)
"%~dp0..\..\.venv\Scripts\python.exe" -X utf8 "pattern_rule_workbench.py" %*
