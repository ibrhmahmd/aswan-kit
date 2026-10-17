@echo off
chcp 65001 >nul
title Aswan Projects - keep this window open
cd /d "%~dp0kit"

rem Already running? Then just open the browser again.
curl.exe -s -o nul http://localhost:8500/_stcore/health
if not errorlevel 1 (
    start "" http://localhost:8500
    exit /b 0
)

echo.
echo  Aswan Projects is starting. Your browser will open in a moment.
echo  Keep this window open. You can minimize it.
echo.
set "PYTHONPATH=%~dp0kit\libs\@@LAUNCHER_ENV@@"
set "PYTHONNOUSERSITE=1"
set "PYTHONUTF8=1"

rem Open the browser as soon as the launcher answers.
start "" /b powershell -NoProfile -WindowStyle Hidden -Command "for ($i = 0; $i -lt 180; $i++) { try { Invoke-WebRequest -UseBasicParsing http://localhost:8500/_stcore/health -TimeoutSec 1 | Out-Null; break } catch { Start-Sleep -Seconds 1 } }; Start-Process 'http://localhost:8500'"

"python\python.exe" -m streamlit run "launcher\app.py" --server.port 8500 --server.address localhost

echo.
echo  Aswan Projects stopped. You can close this window.
pause
