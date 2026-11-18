@echo off
rem Arranca la herramienta de datos UAT. Deja esta ventana abierta mientras la uses; al cerrarla se para el servidor.
rem Si hay una lectura de SAP en marcha, no cierres esta ventana.
cd /d "%~dp0"
title Servidor UAT (puerto 8766) - no cerrar

rem Si ya hay un servidor en marcha, no se arranca otro: solo se abre el navegador.
powershell -NoProfile -Command "try { Invoke-WebRequest http://localhost:8766/api/qs4/status -UseBasicParsing -TimeoutSec 3 | Out-Null; exit 0 } catch { exit 1 }"
if %errorlevel%==0 (
    echo El servidor ya estaba arrancado en otra ventana negra. Abriendo el navegador en http://localhost:8766 ...
    start "" http://localhost:8766
    timeout /t 5 >nul
    exit /b
)

echo Arrancando el servidor. El navegador se abrira solo en unos segundos (http://localhost:8766).
start "" /min cmd /c "timeout /t 4 >nul & start http://localhost:8766"
python front\server.py --port 8766
echo.
echo El servidor se ha parado (o no ha podido arrancar: mira el mensaje de arriba). Pulsa una tecla para cerrar.
pause
