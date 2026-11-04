@echo off
rem For working on Dramatis: the server on 8815 in its own window, and Vite with live reload on 5207.
setlocal
pushd "%~dp0..\Program" || exit /b 1
start "Dramatis server" .venv\Scripts\python -m dramatis --no-browser
call npm run dev
popd
