@echo off
setlocal

cd /d "%~dp0"

set "FLASK_ENV=production"
set "FLASK_DEBUG=0"

if not exist "log" mkdir "log"

".\.venv\Scripts\waitress-serve.exe" --host=0.0.0.0 --port=5000 wsgi:app >> "log\waitress.log" 2>&1

endlocal