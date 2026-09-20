@echo off
cd /d C:\Users\hp\jarvis.ai
start "" /min powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "C:\Users\hp\jarvis.ai\jarvis_watchdog.ps1"
exit
