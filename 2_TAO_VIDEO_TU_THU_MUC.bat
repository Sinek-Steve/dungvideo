@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "DIR=%~1"
if "%DIR%"=="" set /p DIR=Keo tha thu muc anh/clip vao day roi Enter: 
set DIR=%DIR:"=%
python dungvideo.py auto "%DIR%"
echo.
pause
