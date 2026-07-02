@echo off
:: 1. Cambiar el directorio a la ubicación donde reside este archivo .bat
cd /d "%~dp0"

:: 2. Ejecutar usando la ruta relativa a esta carpeta
".\.venv\Scripts\python.exe" app.py