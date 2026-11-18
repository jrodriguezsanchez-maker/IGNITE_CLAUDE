@echo off
rem Guarda o cambia la contrasena de QS4 (cifrada en Windows, fuera del proyecto). Doble clic.
cd /d "%~dp0"
python sap\guardar_credencial.py
echo.
pause
