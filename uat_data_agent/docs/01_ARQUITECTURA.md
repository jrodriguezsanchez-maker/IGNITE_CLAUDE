# Arquitectura

## Vista general
```
Excel UAT (data/project)  ──► front/server.py ◄── data/raw/<TABLA>__<PLANTA>.txt  (lecturas SE16N de QS4)
                               │  (build(): casos, pasos, flujos, plantas)      ▲
                               │                                                │
 front/static (app.js, index.html)                              sap/on_demand.py + engine/qs4_plan.py (SAP GUI Scripting, solo lectura)
                               │
                               ▼
        data/ledger/asignaciones.json (decisiones del usuario)  ·  reservas.csv (un recurso = un caso)
                               │  (solo bajo petición)
                               ▼
        out/..._DataProposal.xlsx (copia del Excel con AG–AL, parche XML)
```
Servidor: `http.server` de la librería estándar, un solo proceso, puerto **8766** (`python front/server.py --port 8766`; el preview `uat-front` de `.claude/launch.json` usa la misma orden y salta a 8767 si 8766 está ocupado).

## Módulos
| Fichero | Papel |
|---|---|
| `front/server.py` (~1850 líneas) | Servidor y lógica de caso: `build()` (lee el Excel, clasifica streams/flujos, aplica reglas de clasificación), `data_proposal(c,a)` (texto de Data por paso), `form_caso` (formulario por paso), `rationale_caso`, `check_flujo`, `auto_proponer` (propuesta en bloque), `qm_requisitos`, `_mapea_materiales`, `resources/reserved_map` (modelo dedicado), `guarda_asig/load_asig` |
| `front/static/app.js`, `index.html` | UI. Lista + caso en 3 pasos; `renderCase`, `loadOptions`, `pintarAntesProp` (filas por paso), `renderFormPasos`, checkboxes de selección, filtros multiselección |
| `engine/modelo_tx.py` | **Modelo de transacciones**: qué campos lleva el Data de cada transacción y cómo se calculan/pintan. Lee `config/transacciones_modelo.xlsx` (hoja *Modelo*, col. A transacción, col. D campos; se recarga al cambiar el fichero). `interpreta`, `calcula`, `render`, `ajusta` (añadir/quitar campo), `specs_data` (campos de una transacción fuera del libro a partir de su Data) |
| `engine/options.py` | Opciones por stream (`for_stream`; `_pp`, `_qm`, `_log`, `componentes`): qué materiales/proveedores/clientes sirven y por qué (columnas Apto/Motivo, «En ECC», «Registro info») |
| `engine/derivados.py` | Deriva BOM, hoja de ruta, versión de fabricación, cost collector y puesto de trabajo (MAST/MKAL/MAPL/AFPO/AUFK) para un material y planta |
| `engine/parse_data.py` | Parser del texto Data (etiquetas con variantes), `prev_data()` y `Prev.Data` |
| `engine/tramos.py` | Cadenas de varios documentos (≥2 ME21N, STO automática, Plant 1/2/3) |
| `engine/ecc.py`, `flows_ecc.py` | Listado de pedidos de ECC (`GRT.txt`, ruta en settings) para comprobar que algo ya se compró/trasladó |
| `engine/qs4_plan.py` | Planes de lectura de QS4 por stream/planta (`plan_info_org`, `plan_vendors`, `plan_clientes_transporte`) |
| `engine/readers.py` | Lector de las exportaciones SE16N |
| `engine/patch_xlsx.py` | Escritura de AG–AL por XML sin tocar nada más |
| `sap/on_demand.py` | Lecturas a demanda por SE16N (hilo COM único, ALV con scroll, portapapeles para listas de valores, **autocuración**: si SAP se cuelga mata saplogon y reloguea) |
| `sap/credencial.py`, `login.py` | Credencial en el Administrador de credenciales de Windows; **un solo intento** de login (freno en `%LOCALAPPDATA%\uat_agent\login_fallido.txt`) |
| `config/settings.yaml`, `rules.yaml`, `extractions.yaml` | Sistema/mandante (QS4/200), rutas, whitelist; reglas de flujos; 56 tablas por bloque |
| `cola_*.ps1/.bat` | Colas de lectura largas lanzadas fuera del servidor (ver `03_OPERACION.md`) |

## Datos en disco
- `data/project/` Excel original (no tocar). `data/raw/TABLA__PLANTA.txt` lecturas (MARA, MARC, MARD, MAKT, MAST/STKO/STPO, MAPL/PLKO, MKAL, AFPO/AUFK, QMAT, EINA/EINE por planta/org/proveedor, LFA1/LFB1/LFM1, KNVV, T001L/T001W/T320, MLGN/MLGT/LQUA…). Excluidos de base los repuestos 80000000–89999999.
- `data/ledger/asignaciones.json`: por caso → `status`, `fields` (valores por defecto del caso), `extras`, `pasos` {idx:{clave:valor}}, `pasos_campos` {idx:{add,quitar}}, `edits` (texto editado a mano por paso; tiene prioridad), `auto`, `resumen`, `hallazgo`, `note`. **Se guarda con escritura directa y reintentos** (OneDrive bloquea el fichero; ver `03_OPERACION.md`).
- `data/ledger/reservas.csv`: recurso → caso (MATERIAL se reserva por planta: `material@planta`).
- `out/`: Excel propuesta, `peticion_creacion_maestros.csv`, logs de carga.

## API (GET salvo indicación)
`/api/meta`, `/api/cases`, `/api/case?id=` (incluye `org_info`), `/api/options`, `/api/plantas`, `/api/componentes`, `/api/alternatives`, `/api/org?plants=`, `/api/check`, `/api/ecc/destinos`, `/api/ecc/proveedores`, `/api/conflicts`, `/api/auto/status`, `/api/sap/estado`, `/api/qs4/status|plan`, `/api/excel`, `/api/reload`. POST: `/api/proposal` (devuelve propuesta + `form`), `/api/qs4/run` (con `extra: clientes_transporte|info_org`), propuesta en bloque. PUT `/api/case` (guarda).

## Cómo se genera el Data de un paso
1. `build()` clasifica el caso (stream PP/QM/LOG/PM/WM, flujo ZTRA/ZPO/…/VENTA, plantas, tramos).
2. `_ctx_modelo` arma el contexto (defaults del caso + valores derivados); `_ctx_para_paso` lo particulariza por paso y aplica lo que el usuario cambió en ese paso (`pasos`).
3. `modelo_tx.especificacion(tx)` da los campos de la transacción (o `specs_data` si no está en el libro, o parte de `Prev.Data`); `ajusta` aplica `pasos_campos`; `calcula` obtiene los valores; `render` escribe el texto con tres bloques separados por `-----------------------` y `Prev.Data (…)` al final.
4. Si hay `edits[idx]`, ese texto gana.
Un paso fuera del libro (o con `Prev.Data` explícito en el Excel) mantiene el texto del Excel **hasta que el usuario cambia o añade un campo**.
