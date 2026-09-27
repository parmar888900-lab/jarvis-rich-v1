@echo off
setlocal
cd /d "%~dp0\..\.."
if not exist "generated\logs" mkdir "generated\logs"
if not exist ".venv\Scripts\python.exe" (
  echo Jarvis Python environment missing. Install pinned requirements first.
  exit /b 2
)
:restart
set JARVIS_PUBLIC_PUBLISH_ENABLED=false
".venv\Scripts\python.exe" "scripts\run_network_supervisor.py" --interval 60 >> "generated\logs\network-supervisor.log" 2>&1
echo Supervisor exited at %date% %time%; restarting in 15 seconds.>> "generated\logs\network-supervisor.log"
timeout /t 15 /nobreak >nul
goto restart
