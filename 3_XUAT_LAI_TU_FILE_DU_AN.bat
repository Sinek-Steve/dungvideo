@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "F=%~1"
if "%F%"=="" set /p F=Keo tha file _du_an.yaml vao day roi Enter: 
set F=%F:"=%
python dungvideo.py render "%F%"
echo.
pause
