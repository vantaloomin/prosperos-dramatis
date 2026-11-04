@echo off
rem Starts Dramatis at http://127.0.0.1:8815 and opens it in the browser. Close this window to stop it.
setlocal
pushd "%~dp0..\Program" || exit /b 1
if not exist .venv\Scripts\python.exe (
  echo Dramatis is not installed yet. Run Windows\install.bat first.
  popd
  exit /b 1
)
.venv\Scripts\python -m dramatis %*
set "result=%ERRORLEVEL%"
popd
exit /b %result%
