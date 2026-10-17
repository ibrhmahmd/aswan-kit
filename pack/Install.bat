@echo off
setlocal
chcp 65001 >nul
title Aswan Projects - Installing
cd /d "%~dp0"
echo.
echo  =====================================================
echo    Installing Aswan Projects. Please wait...
echo    This takes a few minutes. Do not unplug the USB.
echo  =====================================================
echo.

rem Find the real Desktop folder (it can be moved, for example by OneDrive).
for /f "usebackq delims=" %%D in (`powershell -NoProfile -Command "[Environment]::GetFolderPath('Desktop')"`) do set "DESKTOP=%%D"
if not defined DESKTOP set "DESKTOP=%USERPROFILE%\Desktop"
set "TARGET=%DESKTOP%\Aswan Projects"

rem Stop an older copy that is still running, so its files can be replaced.
powershell -NoProfile -Command "Get-Process | Where-Object { $_.Path -like '%TARGET%\*' } | Stop-Process -Force" >nul 2>&1

echo  Copying files to "%TARGET%" ...
robocopy "%~dp0payload" "%TARGET%" /E /MT:8 /R:1 /W:1 /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 goto failed

rem Write the AI keys into the projects that need them.
@@SECRETS@@

rem Put an icon on the Desktop that opens the launcher.
powershell -NoProfile -Command "$s = (New-Object -ComObject WScript.Shell).CreateShortcut('%DESKTOP%\Open Aswan Projects.lnk'); $s.TargetPath = '%TARGET%\Start Aswan Projects.bat'; $s.WorkingDirectory = '%TARGET%'; $s.IconLocation = '%TARGET%\kit\launcher\icon.ico'; $s.Save()"

echo.
echo  Done! "Open Aswan Projects" is now on your Desktop.
echo  Opening it for you...
start "" "%TARGET%\Start Aswan Projects.bat"
timeout /t 5 >nul
exit /b 0

:failed
echo.
echo  Something went wrong while copying.
echo  Make sure the Desktop drive has 3 GB free, then double-click Install again.
pause
exit /b 1
