> **Aviso:** este README es histórico (octubre/noviembre). Hoy el front también lanza lecturas de QS4 a demanda y guarda decisiones por paso. Documentación vigente: `docs/00_LEEME_PRIMERO.md`.

# Cómo arrancar
1. PC Windows con SAP GUI y scripting activo (servidor: parámetro sapgui/user_scripting = TRUE; cliente: Opciones > Accesibilidad y scripting > Activar scripting, desmarcar los avisos). Python 3.11+ con `pywin32 pandas pyyaml openpyxl`.
2. Copiar el fichero UAT original a `data/project/`.
3. Abrir una terminal en esta carpeta y ejecutar `claude`. Pegar el contenido de PROMPT_INICIAL.md.
4. Antes de la primera extracción real: grabar una vez SE16N (tabla T001W, exportar a fichero local) con el grabador de SAP GUI y pasar el .vbs a Claude Code para que ajuste los IDs de `sap/sap_gui.py`.

# Front de seguimiento de casos
```
python front/server.py        # http://localhost:8766
```
- Lee el UAT de `config/settings.yaml > paths.uat_file` y las exportaciones SE16N de `data/raw/` (`<TABLA>.txt|csv|xlsx`). Si faltan, entra en **modo prueba** con datos sintéticos (`python tests/make_mock.py`) y guarda aparte (`*_MOCK`).
- Streams: PP (repetitiva) · QM · PM · WM · LOG (traslados, venta, compra, transporte). Se detectan por transacción y se pueden cambiar a mano.
- Por caso: elige planta → ve opciones reales (material con versión/BOM, equipos, ubicaciones WM, clientes, proveedores) → clic para rellenar → Guardar. Guarda en `data/ledger/asignaciones.json` y registra reservas en `data/ledger/reservas.csv`; avisa si un recurso ya es de otro caso.
- Solo lee ficheros: no se conecta a SAP.

## Consultas a QS4 (solo a demanda)
- No se extrae nada por lotes. En la ficha de un caso, el botón **"Consultar QS4 para <planta>…"** muestra las tablas y filtros que se consultarían (SE16N, solo lectura, solo ese stream y esa planta) y pide confirmación.
- Requiere SAP abierto y con tu sesión iniciada en QS4/200 (entrada de SAP Logon "QS4 - S4 Calidad"); si el sistema o mandante no coinciden, se detiene.
- Los resultados caen en `data/raw/<TABLA>__<PLANTA>.txt` y el front los recarga. `sap/run_extractions.py` (lotes) queda como herramienta manual opcional; no lo usa el front.
- Los IDs de pantalla de SE16N en `sap/sap_gui.py` están sin validar: la primera consulta real es la prueba; si falla una tabla, el error sale en el front por tabla.
