@echo off
setlocal
set "PYTHONUTF8=1"
if not defined STUDIO_HOME_ROOT set "STUDIO_HOME_ROOT=E:\AI-Creative-Studio"
if not exist "%STUDIO_HOME_ROOT%\venvs\studio\Scripts\python.exe" (
  echo Falta el entorno HOME. Consulte docs\HOME.md.
  exit /b 1
)
if "%~1"=="" (
  "%STUDIO_HOME_ROOT%\venvs\studio\Scripts\python.exe" "%~dp0scripts\home.py" start
  if errorlevel 1 exit /b 1
  start "" "http://127.0.0.1:8765/studio"
) else (
  "%STUDIO_HOME_ROOT%\venvs\studio\Scripts\python.exe" "%~dp0scripts\home.py" %*
)
