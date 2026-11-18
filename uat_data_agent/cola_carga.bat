@echo off
rem Cola de cargas masivas: QM, WM y logistica (plantas L), una detras de otra. Deja esta ventana abierta; al cerrarla se para la cola.
rem Espera a que acabe la lectura en curso y anota el avance en out\carga_noche.log
cd /d "%~dp0"
title Cola de cargas QS4 (no cerrar)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0cola_carga.ps1"
echo.
echo La cola ha terminado. Pulsa una tecla para cerrar.
pause
