@echo off
setlocal
cd /d "%~dp0"
set MPLCONFIGDIR=%CD%\.matplotlib
set QT_API=pyqt6
"%~dp0..\..\.venv\Scripts\python.exe" -X utf8 "main_pyqt6.py"
