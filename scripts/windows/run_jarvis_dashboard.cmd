@echo off
setlocal
cd /d "%~dp0\..\.."
if not exist "generated\logs" mkdir "generated\logs"
set "JARVIS_PYTHON=venv\Scripts\python.exe"
if not exist "%JARVIS_PYTHON%" set "JARVIS_PYTHON=.venv\Scripts\python.exe"
if not exist "%JARVIS_PYTHON%" exit /b 2
:restart
set JARVIS_PUBLIC_PUBLISH_ENABLED=false
"%JARVIS_PYTHON%" "scripts\run_dashboard.py" >> "generated\logs\dashboard.log" 2>&1
echo Dashboard exited at %date% %time%; retrying in 15 seconds.>> "generated\logs\dashboard.log"
timeout /t 15 /nobreak >nul
goto restart
