@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === Cai thu vien Python cho DungVideo ===
python --version || (echo Chua co Python. Tai tai https://www.python.org/downloads/ va tick "Add to PATH". & pause & exit /b)
python -m pip install -r requirements.txt
where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo.
  echo Chua thay ffmpeg. Dang cai bang winget...
  winget install -e --id Gyan.FFmpeg
  echo Cai xong hay DONG cua so nay va mo lai.
) else (
  echo ffmpeg: OK
)
echo.
echo Xong! Chay thu: 4_CHAY_THU_DEMO.bat
pause
