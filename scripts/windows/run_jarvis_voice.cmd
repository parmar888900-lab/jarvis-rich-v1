@echo off
setlocal
cd /d "%~dp0\..\.."
if not exist "generated\logs" mkdir "generated\logs"
set "JARVIS_PYTHON=venv\Scripts\python.exe"
if not exist "%JARVIS_PYTHON%" set "JARVIS_PYTHON=.venv\Scripts\python.exe"
if not exist "%JARVIS_PYTHON%" exit /b 2
:restart
set JARVIS_PUBLIC_PUBLISH_ENABLED=false
"%JARVIS_PYTHON%" -m backend.services.voice.voice_runtime >> "generated\logs\voice-runtime.log" 2>&1
echo Voice service exited at %date% %time%; restarting in 15 seconds.>> "generated\logs\voice-runtime.log"
timeout /t 15 /nobreak >nul
goto restart
