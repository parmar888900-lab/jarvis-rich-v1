@echo off
setlocal
cd /d "%~dp0\..\.."
if not exist "generated\logs" mkdir "generated\logs"
set "JARVIS_PYTHON=venv\Scripts\python.exe"
if not exist "%JARVIS_PYTHON%" set "JARVIS_PYTHON=.venv\Scripts\python.exe"
if not exist "%JARVIS_PYTHON%" (
  echo Jarvis Python environment missing. Install pinned requirements first.
  exit /b 2
)
:restart
set JARVIS_PUBLIC_PUBLISH_ENABLED=false
"%JARVIS_PYTHON%" "scripts\run_network_supervisor.py" --interval 60 >> "generated\logs\network-supervisor.log" 2>&1
echo Supervisor exited at %date% %time%; restarting in 15 seconds.>> "generated\logs\network-supervisor.log"
timeout /t 15 /nobreak >nul
goto restart
