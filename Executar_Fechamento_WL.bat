@echo off
setlocal
set "WL_APP_DIR=%~dp0app"
set "WL_PYTHON=C:\Users\lilia\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\pythonw.exe"
if not exist "%WL_PYTHON%" (
  echo Nao foi possivel localizar o Python do aplicativo.
  pause
  exit /b 1
)
cd /d "%WL_APP_DIR%"
start "" "%WL_PYTHON%" main.py
endlocal
