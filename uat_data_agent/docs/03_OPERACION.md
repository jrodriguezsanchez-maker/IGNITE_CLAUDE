# Operación: arrancar, leer SAP y problemas conocidos

## Servidor
- Arranque normal (usuario): `iniciar_uat.bat` → `python front\server.py --port 8766` y abre el navegador. Si ya hay servidor, solo abre el navegador. **No cerrar la ventana negra** (al cerrarla se para).
- Reinicio desde Claude (probado): comprobar `GET /api/qs4/status` → `estado` distinto de `consultando`; matar el proceso python cuyo `CommandLine` contiene `server.py`; relanzar con `Start-Process explorer.exe "<ruta>\iniciar_uat.bat"` (arrancarlo desde otros procesos lo dejaba colgado o muerto). Esperar ~10 s hasta que responda.
- El servidor tarda unos segundos en cargar (tablas en memoria). Una consulta durante el arranque da «conexión rechazada».
- `reiniciar_servidor_cuando_libre.ps1` y `reiniciar_y_proponer.ps1` existen para reiniciar al terminar una lectura.
- Python 3.14, Windows 11. **No hay Node** (no se puede validar el JS por sintaxis; verificar en el navegador/preview: cargar y mirar la consola).

## Lecturas de QS4 (solo lectura, SE16N)
- Desde el front («QS4») o por colas PowerShell: `cola_final.ps1/.bat` (carga final de tablas), `cola_info_org.ps1/.bat` (registros info por org. de compras; usa rutas `data/raw/...` con barras normales; hubo un bug con un carácter CR en la ruta), `cola_carga.*`, `carga_noche.ps1`. Se lanzan **desde el explorador** para que vivan fuera del proceso de Claude. Logs en `out/*.log`.
- Salida: `data/raw/TABLA__PLANTA.txt`. Una tabla vale si trae todas las columnas que pide la receta (`fichero_ok`).
- Listas largas de valores en SE16N: se pegan por **portapapeles** (el lector reintenta 20 s si Windows lo bloquea).
- **Autocuración** (`autocurar`): si SAP se cuelga, mata `saplogon` y relogin. **Mata la sesión del usuario**: no lanzar lecturas mientras trabaja en SAP.
- Login: un único intento; si falla, freno en `%LOCALAPPDATA%\uat_agent\login_fallido.txt` (el usuario puede levantarlo desde el HTML con confirmación). La contraseña se guarda desde el HTML (solo localhost, cabecera `X-UAT`); Claude nunca la ve.
- Aviso «Permitir» de scripting: un único hilo COM reutiliza la sesión; no tocar la opción de SAP GUI.
- Tiempos medidos en `data/ledger/tiempos_qs4.json`. Estimaciones: grupo de compras por planta ≈ 45 min; clientes (KNVV) 26 orgs ≈ 2 h (no se ha hecho).

## Problemas conocidos y su solución
| Síntoma | Causa | Solución |
|---|---|---|
| `JSONDecodeError` / `PermissionError` al **grabar** en el front | OneDrive sincroniza `asignaciones.json` y lo bloquea o lo deja a medias; una lectura concurrente veía el fichero incompleto. El intento de escritura atómica (`os.replace`) falló con *Access denied* | `guarda_asig` escribe directamente con **hasta 15 reintentos**; `load_asig` reintenta 5 veces. No volver a `os.replace` sobre esa carpeta |
| Pantalla del front rota tras un cambio | JS/HTML se sirven sin caché (aparecen ya) pero Python necesita reinicio | Reiniciar el servidor y pedir Ctrl+F5 |
| Mensaje «Mantiene el Data del Excel…» sin formulario | Servidor con código viejo | Reiniciar |
| Logs bloqueados (`Add-Content` falla) | `tail -F` mantiene el fichero abierto | No usar `tail -F`; consultar con `grep` puntual |
| OpenClipboard «Access denied» | Bloqueo global del portapapeles de Windows | Reintentos de 20 s; esperar |
| Dos servidores (8766 y 8767) | El preview arranca otro si 8766 está ocupado | Parar el preview al terminar |
| Parches en Python desde PowerShell | Escapes (`\b` → retroceso, `\d`…) | Escribir parches en un `.py` y ejecutarlos con `python -I`; comprobar que no hay `\x08` |

## Excel de salida
Solo a petición expresa. `engine/patch_xlsx.py` modifica únicamente `xl/worksheets/sheet2.xml` y `xl/tables/table2.xml` (tabla `A1:AF7080` → `A1:AL7080`), conserva el filtro, y escribe `out/<nombre>_DataProposal.xlsx`. Comprobar siempre que A:AF queda idéntico. `AJ` (hallazgos) no se genera; estado/notas aún no salen al Excel. `out/peticion_creacion_maestros.csv` lista los casos «Sin candidato».

## Antes de decir «hecho» en un cambio de front
Recargar en el preview, ver que la pantalla carga y que no hay errores de consola. Cuidado con nombres globales nuevos en `app.js` (grep antes; hubo choques `info` vs variable de `renderCase` y `let prop` duplicado). Con cambios de Python: reiniciar y verificar por API (`/api/proposal` devuelve `form`).

## Proyecto hermano
`../automatizaciones/` (front en el puerto 8765, ejecución real de MIGO/MB52 en SAP con confirmaciones) es **otro proyecto**, con sus propias reglas; el agente UAT no ejecuta pasos en SAP.
