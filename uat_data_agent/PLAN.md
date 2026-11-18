> **Aviso:** plan histórico a 08/11; el estado vigente está en `docs/05_ESTADO_Y_PENDIENTES.md`.

# Plan de implementación — datos UAT por caso (iGnite SCM HUMAN)

Regla de trabajo: **una fase cada vez**. Al terminar cada fase paro, enseño la evidencia y no empiezo la siguiente hasta tu OK.
Las peticiones nuevas que vayan saliendo se apuntan en "Pendientes" y se colocan en el orden; no se mezclan a mitad de fase.

Principios (no se negocian)
- El Excel manda: los datos de cada caso salen de su Data. ECC solo sirve para comprobar lo que propongamos. QS4 solo se consulta a demanda, en solo lectura, con tu confirmación.
- Cada caso se resuelve con un semáforo: cada requisito en ✓ o ✗. Lo incompleto se muestra marcado, no se oculta; los completos salen primero.
- No romper lo que ya funciona: cada fase termina con una comprobación de regresión sobre casos de otros streams.

## Dónde estamos (resumen, actualizado el 08/11)

**Lo que ves en pantalla** (cabecera: «versión …»; si hay otra más nueva sale un botón amarillo «Recargar»): filtros arriba, lista a la izquierda, caso en 3 pasos (plantas · datos · revisa y guarda), estado de SAP y contraseña en la cabecera, panel de QS4 comprimido arriba del paso 2 (tablas guardadas, refrescar solo las que marques), barra de acciones fija abajo, propuesta editable.

**Hecho y probado en el preview con datos reales de M116 (sin contrastar con SAP, salvo lo que tú validaste):** creación en PP, selección de versión, Costing, estado de material, órdenes planificadas, aprovisionamiento MF60/MB21, MFBF, anulaciones, subproductos, puesto de trabajo, material modelo.

**Hecho el 09/11:** las **14 plantas de PP están cargadas** (720 casos; 57 de 57 tablas sin error en la última pasada). Repuestos 8xxxxxxx excluidos de base (config), textos solo en inglés, STPO en trozos y solo listas de producción, recuperación automática si SAP se cuelga, servidor independiente (`iniciar_uat.bat`). **Propuesta en bloque** hecha para 9 plantas (132 propuestos, 101 Data original OK, 79 sin candidato, 102 a revisar a mano, 49 no requiere), con auditoría independiente sin fallos; **Excel AG–AL generado y verificado** (solo cambian sheet2/table2; A:AF idéntico) + `peticion_creacion_maestros.csv`. Falta repetir la propuesta con las 14 plantas (botón «Propuesta en bloque…»), a petición del usuario, no automática.

**Sin hacer:** QM (7), PM (8), WM (9), plantas de LOG/QM/PM/WM sin cargar, subcontratación, dispositivos RF (dependen de WM), lógica de familias de logística fuera de PP, validación en SAP del puesto de trabajo/estado/componentes.

**Pendiente de tu validación en SAP:** el puesto de trabajo (MKAL-MDV01) de un material de M116, el estado de material (MMSTA) y que las listas de componentes (STPO) coinciden con CS03.

## Estado

| Fase | Contenido | Estado |
|---|---|---|
| 0 | Excel real, streams por L2, organización (Org.Structure + T001W de QS4), plantas alternativas | HECHA |
| 1 | Front: filtros arriba, lista a la izquierda, caso guiado (qué probamos / qué buscamos / 3 pasos) | HECHA |
| 2 | Consulta a QS4 a demanda (SE16N por scripting, sesión nueva, ALV con scroll, selección múltiple) | HECHA (L033 y M116 descargadas de verdad; ahora se avisa de lo ya descargado y refrescar es opcional) |
| 3 | Casos encadenados: tramos desde el Excel + comprobación en ECC (planta/almacén, proveedor) | HECHA (guardado y Data por tramo verificados) |
| 4 | Generar el Excel (AG–AL) por XML sin romper A:AF | PARCIAL (probado solo con datos de prueba; AJ no se genera; estado/notas no salen al Excel) |
| 5 | Logística de un solo tramo: flujo en ECC, almacenes, proveedor y registro info | HECHA (verificada con un traslado y una compra reales) |
| 6 | PP: material, lista de materiales, hoja de ruta, versión de fabricación, cost collector | HECHA solo para PP de creación (170 de 780 casos PP): M116 cargada, 162 de 296 completos; validación en SAP dada por buena por el usuario sin contraste detallado |
| 6c | PP por familias: los otros 610 casos PP (estados de material, órdenes planificadas, aprovisionamiento MF60, MFBF, anulaciones, notificaciones, cierre) | EN CURSO. Tabla en `PP_FAMILIAS.md`, aprobadas las 9 recomendaciones. Paso 1 hecho con datos de M116 (sin validar con SAP): selección de versión (17), Costing (56), estado de material (120). Paso 2 implementado con STPO y MARD de M116 (sin validar con SAP): órdenes planificadas A→B (79), aprovisionamiento MF60 y MB21 (98), MFBF entradas/consumos/anulaciones (≈100) y subproductos (6). Siguientes: cierre/informes/Z como «No requiere» (≈128), RF con la fase WM (31), anulaciones de salida MB21 (15, por confirmar), subcontratación (14) y plantas distintas de M116 |
| 6b | Conexión a SAP: botón y estado en cabecera, login con credencial cifrada de Windows, un solo intento, sesión reutilizada | HECHA, sin probar el login real (la consulta de M116 sí corrió con SAP abierto) |
| 7 | QM: material, tipo de inspección, plan de inspección (tipo Q, uso 1/5/8, proveedor en 5) | EN CURSO: tabla de 8 grupos y 9 preguntas en `QM_FAMILIAS.md`, a la espera de tu aprobación; después, lectura de QMAT y planes tipo Q de las 15 plantas |
| 8 | PM: equipo, ubicación técnica, órdenes | PENDIENTE |
| 9 | WM: vista WM del material para el almacén de la planta (T320), tipos de almacén, stock | PENDIENTE |
| 10 | Excel de punta a punta: AG–AL completos y petición de creación de maestros | PENDIENTE |
| 11 | Modelo dedicado: un dato, un caso (también dentro de las cadenas) | PENDIENTE |
| 12 | Pruebas con datos simulados + README | PENDIENTE |

## Fases pendientes, en orden

### Fase 3 (cierre) — tramos
- Entrego: guardar la cadena y escribir la Data de cada paso según su tramo (pasos 5–10 con el traspaso 1, 11–14 con el 2).
- Compruebo yo: caso `SIT-SCM-H-5.6.2-21_IMPORT_EXPORT` guardado y su Data propuesta; regresión en un caso PP y uno de logística normal.
- Compruebas tú: abres ese caso y confirmas que la Data de los 16 pasos tiene sentido.

### Fase 5 — logística de un solo tramo
- Entrego: la misma validación de ECC que ya hay en cadenas, para casos ZTRA/ZWIA/ZINT/ZPO normales; almacén existente en QS4 (T001L); proveedor (LFA1, LFM1) y registro info (EINA) en compras.
- Compruebo yo: caso L033→M116 con M116 ya cargada, y un caso de compra.
- Compruebas tú: que lo que marca ✓/✗ coincide con lo que ves en SAP para un material.

### Fase 6 — PP
- Entrego: semáforo por material y planta: material en planta, lista de materiales activa (MAST+STKO), hoja de ruta (MAPL tipo N), versión de fabricación vigente y sin bloquear (MKAL), cost collector (AUFK tipo 05 + AFPO).
- Tablas nuevas en la consulta: MAPL, STKO, AUFK, AFPO. Campos ya comprobados en QS4.
- Check: un caso de M024 y uno de M116 con consulta real; tú validas un material completo y uno incompleto contra SAP.

### Fase 7 — QM
- Entrego: tipo de inspección activo (QMAT) + plan de inspección de tipo Q (PLKO) por uso: 1 producción (planta y material), 5 recepciones (con proveedor, campo LIFNR de MAPL), 8 traslado. El uso se preselecciona según el texto del caso.
- Check: un caso por cada uso.

### Fase 8 — PM
- Entrego: equipo activo, ubicación técnica y órdenes previas, con semáforo. (Ya existe la base; se completa.)
- Check: un caso de PM.

### Fase 9 — WM
- Entrego: almacén de WM de la planta (T320), vista WM del material (MLGN), tipos de almacén (MLGT) y stock en ubicación (LQUA).
- Check: un caso de WM con consulta real.

### Fase 10 — Excel de punta a punta
- Entrego: columnas AG–AL rellenas con criterio (origen, qué cambia, confianza, responsable), `out/peticion_creacion_maestros.csv` para casos sin candidato, y la verificación automática de que solo cambian `sheet2.xml` y `table2.xml`.
- Check: tú abres el Excel generado y revisas 10 casos al azar.

### Fase 11 — modelo dedicado
- Entrega: avisos de dato repetido entre casos, incluido dentro de una cadena; liberar al cambiar de elección.

### Fase 12 — pruebas y documentación
- `tests/` con datos simulados para todo el flujo sin SAP; README actualizado.

## Pendientes (sin fase asignada)
- BP dedicado o compartido: sigue la suposición de compartido.
- `params.desde` de las extracciones de documentos (ventana de fechas).
- Casos ZINT donde las dos plantas son de la misma sociedad (ej. `SIT-SCM-H-5.6.2-56_ITALY`): revisar caso u Org.Structure.
- Plantas que están en Org.Structure o en ECC y no existen en QS4 (L032, L058, M003, M017, M020, L024, L050, M028).
- Lanzada la consulta de M116 (PP); la de M024 sigue sin lanzar.
- El panel debe proponer datos y alternativas en TODOS los streams (hoy solo PP contrasta el Excel con QS4).
- Ledger `reservas.csv` aún sin generar con datos reales; estado y notas no salen al Excel.
