@echo off
setlocal

cd /d "%~dp0"

set "FLASK_ENV=development"
set "FLASK_DEBUG=1"

".\.venv\Scripts\python.exe" app.py

endlocal