@echo off
rem Registros info por organizacion de compras (QS4, solo lectura). Deja esta ventana abierta hasta que ponga COLA INFO ORG terminada (mira out\carga_info_org.log).
cd /d "%~dp0"
title Cola registros info por org. de compras (no cerrar)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0cola_info_org.ps1"
echo.
echo La cola ha terminado. Mira out\carga_info_org.log. Pulsa una tecla para cerrar.
pause
