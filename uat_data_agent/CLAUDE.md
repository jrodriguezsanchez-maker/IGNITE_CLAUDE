# Agente de datos UAT — iGnite S/4HANA · SCM HUMAN

> **Empieza por `docs/00_LEEME_PRIMERO.md`** (visión general, cómo se usa, mapa de documentación). El estado real y los pendientes están en `docs/05_ESTADO_Y_PENDIENTES.md`; las preferencias del usuario en `docs/04_…`; la operación (arranque, SAP, problemas conocidos como el bloqueo de OneDrive) en `docs/03_…`. `PLAN.md`, `README.md` y `PROMPT_INICIAL.md` son históricos.

## Objetivo
Para cada caso del fichero UAT, proponer datos de prueba válidos y **dedicados al caso** (plantas, sociedad/org., material, stock, proveedor/cliente), sacados del sistema SAP de UAT, y escribirlos en 6 columnas nuevas **AG–AL** al final de la hoja `UAT_testscript - breaks by unit`, en una **copia** del fichero.

## Reglas no negociables
1. SAP **solo lectura**, por SAP GUI Scripting. Solo transacciones de `config/settings.yaml > transaction_whitelist` (por defecto SE16N). Nunca `&SAP_EDIT`, nunca transacciones de grabación.
2. Antes de cada extracción, comprobar sistema y mandante (`attach()` ya lo hace). Si no coinciden: parar.
3. Nunca modificar el fichero UAT original. **No** guardar con openpyxl: la hoja oculta `AUX_parse (no tocar)` tiene 76 fórmulas de matriz dinámica (`_xlfn.ANCHORARRAY`, `xl/metadata.xml`) que se romperían. Escribir por XML tocando **solo** `xl/worksheets/sheet2.xml` y `xl/tables/table2.xml` (Table1 `A1:AF7080` → `A1:AL7080`). Mantener el filtro activo de la tabla.
4. No cambiar nada que no se haya pedido (formatos, hojas, paneles, filtros, otras columnas).
5. Toda cifra debe poder verificarse contra los ficheros. Si algo contradice lo que dice el usuario o el fichero, **avisar**; no resolverlo en silencio.
6. Modelo **dedicado**: cada material/stock/equipo se asigna a un solo caso. Registrar cada asignación en `data/ledger/reservas.csv` (caso, tipo de recurso, recurso, planta, almacén, estado RESERVADO/LIBERADO/CONSUMIDO, fecha, ejecución). Re-ejecutar no debe reasignar lo ya reservado al mismo caso.
7. Etiquetas Seguro/Probable/Suposición: solo uso interno (columna AK); no en textos para el equipo.

## Reglas de negocio (fuente única: `config/rules.yaml`)
- **ZTRA**: traslado misma sociedad. Necesita planta emisora y receptora, material ampliado en ambas, stock en la emisora.
- **ZWIA** (plant abroad): como ZTRA, misma sociedad pero plantas en distinto país (aclarado por el usuario; en ECC no es venta).
- **ZINT / ZINR**: traslado/devolución entre sociedades. Igual que ZTRA + proveedor **"P" + planta emisora** (ej. `PL101`); registro info preferente.
- **ZPO**: compra (registro info obligatorio). **ZSPO**: subcontratación. **ZSPA**: repuestos y pallets de alquiler.
- **Venta**: cliente del área de ventas + material vendible (MVKE) + stock en la planta.
- Tipos de material: ZFIN terminado · ZSEM semielaborado · ZFOR formulado (WM y PP) · ZRAW materia prima · ZPAC packaging de producción · ZRPL pallets · ZSPN/ZSPV repuestos.
- **ZSER**: pedido de compra de servicios (confirmado). **ZPAS**: descartado (no se usa). **ZTRA entre sociedades distintas es un error**, no un flujo válido.
- Pendientes (preguntar, no suponer): BP dedicado o compartido.

## Campo Data (formato actual)
Bloques separados por `-----------------------`: organización (C.Code, P.Org, S.Org, Supplier Plant, Plant) · clase de documento / movimiento · datos (Material, BP). Las etiquetas tienen variantes; `engine/reference/parse.py` las normaliza. Al proponer, **sustituir valores dentro del texto existente** (material viejo → nuevo, etc.) para conservar el formato de cada paso.

## Columnas de salida (AG–AL)
| Col | Nombre | Valores |
|---|---|---|
| AG | Data propuesta | mismo formato que Data |
| AH | Origen propuesta | Sin cambio · Regla · Pool SAP · SIT validado · Sin candidato · No requiere |
| AI | Qué cambia | texto corto |
| AJ | Hallazgos que corrige | códigos D01…M01 del análisis |
| AK | Confianza propuesta | Seguro · Probable · Suposición (interno) |
| AL | Validar con | Accenture Owner del caso |
Si no hay candidato: AH = "Sin candidato" y una fila en `out/peticion_creacion_maestros.csv` (caso, planta(s), tipo de material, flujo, qué estructuras necesita).

## Tablas SAP (fuente: `config/extractions.yaml`, 56 tablas en 8 bloques)
A Organización · B Material y stock · C Compras/traslados/subcontratación · D Ventas y entregas · E Producción · F Calidad · G Mantenimiento · H Transporte.
- Los documentos existentes (EKKO/EKPO/EKBE, VBAK/VBAP, LIKP/LIPS, AFKO/AFPO, QALS, VTTK) son **evidencia** de que una combinación funcionó; no prueban que hoy haya stock ni que el dato esté libre.
- En S/4HANA MARD, MCHB y MSLB son vistas de compatibilidad sobre MATDOC: más lentas en SE16N; si tardan, proponer MB52 (pedir permiso para añadirla a la lista blanca).
- `output_fields`: columnas mínimas que se usan; el lector debe fallar con un mensaje claro si falta alguna.
- Pendiente: `params.desde` (ventana de documentos) y las clases de venta de `lists.auart`.

## Estructura
- `config/` settings, reglas, recetas de extracción.
- `sap/` `sap_gui.py` (scripting con salvaguardas; IDs de pantalla **sin validar**), `run_extractions.py`.
- `engine/reference/` código del análisis previo (reutilizar).
- `data/project/` fichero UAT original y Excels de análisis · `data/raw/` exportaciones SE16N · `data/ledger/` reservas · `out/` resultados.

## Hallazgos conocidos que NO se corrigen salvo petición
169 casos de transporte con prefijo distinto entre hojas (SIT-OTC vs SIT-SCM) · 590 IDs duplicados en UAT_cases (Process Owner) · 2 casos sin pasos y 2 grupos de pasos sin caso.
