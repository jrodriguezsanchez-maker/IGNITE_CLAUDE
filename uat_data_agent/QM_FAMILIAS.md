# QM por familias — qué necesita cada tipo de caso (fase 7)

Los **412 casos de QM** son 37 escenarios que se repiten por unidad, en 15 plantas (unos 26 casos cada una; M021 tiene 31). Los he agrupado en 8 grupos usando lo que dicen los propios casos (transacciones, descripción de los pasos, resultado esperado y etiquetas de la Data). **Lo marcado como «propuesta» lo he deducido yo y necesita tu visto bueno antes de implementarlo.**

Cómo revisarlo: contesta solo con el número de pregunta, o «apruebo todas».

## Lo que dicen los datos (distinto de PP)

- **La Data de QM ya dice el papel de cada material, por la etiqueta:** `Material ZFIN: …`, `Material ZSEM: …`, `Material ZFOR: …`, `Material ZRAW: …`, `Material ZPAC: …`. Casi todos los casos piden **uno de cada tipo en la misma planta**. Si uno no sirve, se sustituye por otro **del mismo tipo**, sin la ambigüedad de los pares A → B de PP.
- Los resultados esperados citan los **tipos de inspección**: **89** (lote manual, en QA01) y **08** (traslado, en MM02 del caso de STO). Entrada de mercancías y fabricación usan los suyos.
- Los materiales de la Data se repiten entre familias (en M116: 503925, 517299, 526753, 100675), como en PP.
- La etiqueta `Material ZPAS` aparece en entrada de mercancías: ZPAS está **descartado** en las reglas, así que se ignora.

## Resumen por grupo

| # | Grupo | Casos | Qué hace el caso (evidencia) | Qué necesita para ejecutarse (propuesta) | Tablas |
|---|---|---|---|---|---|
| Q1 | Maestros de calidad | 103 | QS33 método, QS23 característica, QP01 plan, MM02 material, ZPLM desarrollo, QI01 QIR proveedor, ME61 evaluación de proveedor | QS33, QS23 y QP01 (45): solo planta → «No requiere». MM02, ZPLM (30): un material de cada tipo existente en la planta. QIR y evaluación (28): proveedor | MARC, MARA; LFA1, LFM1 |
| Q2 | Entrada de mercancías | 34 | QE51N con pedido ZPO, material ZRAW y ZPAC | Material con **tipo de inspección de recepción activo** y **plan de inspección de uso 5 (recepciones) con el proveedor** | QMAT, MAPL y PLKO tipo Q, EINA |
| Q3 | Lotes manuales | 30 | QA01 con tipo de inspección **89**, QA32, MSC2N | Un material de cada tipo con el **tipo 89 activo** | QMAT |
| Q4 | Fabricación (orden planificada) | 80 | QE51N, QA32, QE11 sobre orden planificada | Material de producción completo (lista, ruta, versión) **más** tipo de inspección de producción activo y plan de **uso 1** | QMAT, MAPL y PLKO tipo Q + lo de PP |
| Q5 | Traslados (STO) | 12 | MM02 activa el tipo **08**, ME21N, VL01N, MIGO; solo M021 | Materiales ZRAW, ZSEM y ZFIN en M021, con stock; el caso activa el 08 | MARC, MARD (y la lógica de logística) |
| Q6 | Planes de inspección | 30 | CC01, QP02, QP60, ZZPP01: modificar o especificar un plan | Un material de cada tipo que **ya tenga plan de inspección** en la planta | MAPL y PLKO tipo Q |
| Q7 | Resultados, trazabilidad y documentos | 48 | ZQM057/039 resultados, MB56 trazabilidad de lotes, CV01N documentos, ZQM033 contaminantes | Materiales por tipo en la planta; trazabilidad: **con gestión de lotes y lotes** | MARC (XCHPF), MCHA |
| Q8 | Avisos de calidad | 75 | QM01 y QM02 con tipo de aviso Q1 a Q4 y la interfaz NICE | Materiales por tipo existentes en la planta (la referencia de pedido o proveedor, por decidir) | MARC, MARA |

## Preguntas (con mi recomendación)

1. **Papel por etiqueta:** ¿cada «Material ZFIN/ZSEM/ZFOR/ZRAW/ZPAC» es un papel fijo, y si no sirve se sustituye por otro del mismo tipo? *Recomiendo: sí.*
2. **Tipos de inspección:** ¿el caso exige el tipo que cita su resultado esperado (89 en los lotes manuales, 08 en traslados) y, para recepción y fabricación, el que tenga el material activo? *Recomiendo: sí; leeré `QMAT` de QS4 para ver qué tipos existen por material y planta, y te lo enseño antes de fijar las reglas.*
3. **Planes de inspección por uso:** uso 1 en fabricación, uso 5 en entrada de mercancías (con proveedor), uso 8 en traslados. *Recomiendo: sí, como me dijiste.*
4. **Casos de solo planta o de transacción de maestro** (QS33, QS23, QP01: 45 casos): ¿«No requiere dato»? *Recomiendo: sí.*
5. **MM02 y ZPLM (30 casos):** ¿el material debe existir en la planta **sin** la vista de calidad aún activada (porque el caso la activa), o ya con ella? *Recomiendo: que exista en la planta y sea de ese tipo, sin exigir la calidad activa.*
6. **Entrada de mercancías (34):** ¿qué proveedor? *Recomiendo: uno con registro info del material y con plan de uso 5 de ese proveedor; si no hay, «Sin candidato».*
7. **Avisos de calidad (75):** ¿necesitan además una referencia (pedido de venta o entrega para Q1, pedido de compra o proveedor para Q2…)? *Recomiendo: proponer solo los materiales por tipo y dejar la referencia a mano.*
8. **Trazabilidad de lotes (11 casos, MB56):** ¿materiales con gestión de lotes y lotes existentes? *Recomiendo: sí; sin candidato si no los hay.*
9. **Plantas:** son 15, M021 incluida (31 casos). *Recomiendo: cargar de una vez las tablas de calidad de las 15 con la carga masiva (QMAT, MAPL y PLKO de tipo Q; unos 5 a 8 minutos por planta), con la recuperación automática activada.*

## Orden que propongo

1. **Leer las tablas de calidad** de las 15 plantas (carga masiva) y enseñarte qué tipos de inspección y planes hay: es lo que decide las reglas reales.
2. **Q3** (lotes manuales, tipo 89) y **Q2** (entrada de mercancías, plan de uso 5 con proveedor), que son los más directos con QMAT y los planes.
3. **Q6, Q7 y Q8** (materiales por tipo con plan, lotes, o solo existencia).
4. **Q4** (reutiliza todo lo de PP) y **Q5** (con la lógica de logística).
5. Propuesta en bloque y Excel como en PP, con tu revisión de las excepciones.
