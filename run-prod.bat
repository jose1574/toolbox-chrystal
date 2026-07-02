@echo off
setlocal

cd /d "%~dp0"

set "FLASK_ENV=production"
set "FLASK_DEBUG=0"

".\.venv\Scripts\waitress-serve.exe" --host=0.0.0.0 --port=5000 wsgi:app

endlocal