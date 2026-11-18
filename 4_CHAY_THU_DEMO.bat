@echo off
chcp 65001 >nul
cd /d "%~dp0"
python dungvideo.py demo
echo.
echo Video demo nam trong thu muc "xuat".
pause
