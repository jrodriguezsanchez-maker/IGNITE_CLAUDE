@echo off
rem Cola final de cargas desde QS4 (solo lectura). Deja esta ventana abierta hasta que ponga COLA FINAL terminada (mira out\carga_final.log).
cd /d "%~dp0"
title Cola final de cargas (no cerrar)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0cola_final.ps1"
echo.
echo La cola ha terminado. Mira out\carga_final.log. Pulsa una tecla para cerrar.
pause
