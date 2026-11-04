@echo off
rem Stops a running Dramatis: the Python process listening on its port (8815, or the one given: stop.bat 8820).
setlocal
set "port=%~1"
if "%port%"=="" set "port=8815"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$found = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort %port% -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue } | Where-Object { $_.ProcessName -like 'python*' } | Sort-Object Id -Unique;" ^
  "if (-not $found) { Write-Host 'Dramatis is not running on port %port%.'; exit 0 }" ^
  "$found | ForEach-Object { Stop-Process -Id $_.Id -Force; Write-Host ('Stopped Dramatis (process ' + $_.Id + ').') }"
exit /b %ERRORLEVEL%
