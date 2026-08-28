@echo off
setlocal
set "WL_APP_DIR=C:\Users\lilia\OneDrive\Documentos\Automatização - Fechamento\app"
set "WL_PYTHON=C:\Users\lilia\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\pythonw.exe"
set "TCL_LIBRARY=C:\WLAppRuntime\runtime_tcl\tcl8.6"
set "TK_LIBRARY=C:\WLAppRuntime\runtime_tcl\tk8.6"
if not exist "%WL_PYTHON%" (
  echo Nao foi possivel localizar o Python do aplicativo.
  pause
  exit /b 1
)
cd /d "%WL_APP_DIR%"
start "" "%WL_PYTHON%" main.py
endlocal
