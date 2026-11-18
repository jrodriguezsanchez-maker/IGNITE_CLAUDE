# PP por familias — qué necesita cada tipo de caso (fase 6c)

Los **780 casos de PP** son 92 escenarios que se repiten por unidad. Los he agrupado en 14 grupos por lo que dicen los propios casos (transacciones, etiquetas de la Data, nombre del escenario). **Lo marcado como «propuesta» lo he deducido yo y necesita tu visto bueno antes de implementarlo.**

Cómo revisarlo: contesta solo con el número de pregunta (p. ej. «1 sí, 2 no: …, 5 como propones»). No hace falta tocar este fichero.

## Resumen por grupo

| # | Grupo | Casos | Qué hace el caso (evidencia) | Qué necesita para ejecutarse (propuesta) | Hoy |
|---|---|---|---|---|---|
| G1 | Maestros: creación | 132 | Material (MDM), lista (CS01), ruta (CA01), versión (C223), cost collector (KKF6N) | Lo previo existe y falta lo que se crea; para material, modelo existente en la planta | **Hecho** (salvo subcontratación) |
| G2 | Costing | 56 | Lista de costes con componente scrap (CS01), ruta de tasa (CA11), versión de costes (C223), liberar costing (CK11N, CK24) | Lista uso 6, ruta tipo R y versión ZCOS: crear la que falta, o tenerlas todas para liberar | Falta ruta R en la lectura (MAPL tipo R) |
| G3 | Estado de material | 120 | MM02 y pasos MD61 → MD11 → MFBF según estado: Z0, CC, OK, PL, ZW, ZY, ZZ, CC→OK | Material cuyo estado de partida sea el del escenario; datos de producción completos en OK/PL/ZW | Falta leer el estado (MMSTA) |
| G4 | Órdenes planificadas | 79 | MD11 tipo PE: materia prima → semielaborado → formulado → terminado; creación desde IBP (COOIS) | Material producido completo, con el consumido como componente en su lista | Falta leer listas (STPO) |
| G5 | Selección de versión | 17 | MD12: cambiar la versión de fabricación de una orden | Material con 2 o más versiones de fabricación vigentes (sin contar ZCOS) | **Sale ya de MKAL** (falta aplicarlo) |
| G6 | Aprovisionamiento MF60 | 60 | Aprovisionar por reserva: aditivos, envase, materia prima, semielaborado, formulado, premezclas | Componente con stock y que sea componente de un producto completo; posible área de suministro | Falta STPO, MARD y área de suministro |
| G7 | Aprovisionamiento MB21 | 38 | Traspaso directo a la zona de aprovisionamiento (la Data trae «A → B») | Material con stock libre en la planta; destino por definir | Falta MARD de PP |
| G8 | MFBF entradas | 34 | Entrada manual de producto terminado, subproductos (scrap), integración MES | Producto completo con puesto de trabajo; para subproductos, lista con subproducto | Producto: sí. Subproducto: falta STPO |
| G9 | MFBF consumos | 40 | Consumo manual (MFBF, MF42N, MF47, MES) | Producto completo y componentes con stock libre | Falta STPO y MARD |
| G10 | Anulaciones | 45 | Anular entradas, consumos y salidas (probable: el caso contabiliza y luego anula; las salidas no lo sé) | Lo mismo que el movimiento que anulan; las salidas, por confirmar | Igual que G8 y G9 |
| G11 | Dispositivos RF | 31 | Transacciones propias ZPP135, ZWM125, ZWM130 en M105 (palé completo, declaración parcial, consumo) | Datos de almacén WM de la planta: número de almacén, tipo de almacén, palé | Depende de la fase WM |
| G12 | Cierre e informes | 75 | MF12 (movimientos de orden y cost collector), SQ01, notificaciones de actividad, diferencias de inventario | En 66 de los 75 la Data trae **solo la planta**: consultan lo creado por otros casos | Sin datos que proponer |
| G13 | Capacidad e integración APS | 30 | MF50 redistribuir a recursos alternativos; integración PP/DS | Material con versión y puestos de trabajo alternativos | Falta capacidad de puestos |
| G14 | Manual, Z o interfaz | 23 | ZPLM, envío a AZO/JEDI/MES, formularios, reetiquetado, reenvasado, cuarentena | Nada derivable de las tablas | No requiere dato nuevo |

## Lo que dicen los datos y conviene saber

- **Los casos están repartidos en 14 plantas** con unos 50 casos cada una (M024 63, M022 56, M027 55, M026 55, M105 54, M103 54, M117 53, M025 52, M015 50, M006 49, M023 48, M120 47, M109 44, M116 40), y 60 casos no citan ninguna planta. **Solo tengo descargada M116.** Para el resto hay que consultar planta a planta.
- En los 8 estados de material (G3) la Data trae **el mismo material 542608**, y en las tres familias de creación (lista, ruta, versión) la **misma lista de 5 materiales**. Con el modelo dedicado, un mismo material no puede servir a todos los casos.
- En M116 hay **tres tipos de lista de materiales** (uso 1, 2 y 6) y versiones de costes (ZCOS) con ruta tipo R. Es lo que me hace pensar que «Costing» significa uso 6, ruta R y versión ZCOS.
- Anulaciones (G10): «Null consumptions» y «Null receptions» tienen 3 pasos (MFBF → FB03 → KE24), así que **probablemente** contabilizan y anulan en el mismo caso. «Null good issues» tiene un solo paso (MB21) y solo la planta: **no sé** si necesita un movimiento previo (pregunta 5).

## Preguntas (con mi recomendación)

1. **Estado de material (G3, 120 casos):** ¿el caso **parte** de un material que ya está en ese estado, o lo **cambia** durante el caso? *Recomiendo: parte del estado previo (en «CC → OK» parte de CC). Propondría materiales por estado.*
2. **Costing (G2, 56 casos):** ¿«Costing BOM» es la lista de uso 6, «Costing Rate routing» la ruta tipo R y «Costing product version» la versión ZCOS? *Recomiendo: sí.*
3. **Órdenes planificadas «A → B» (G4, 79 casos):** ¿A es **componente** de B (B lleva A en su lista de materiales)? *Recomiendo: sí; propondría B con A en su lista.*
4. **Aprovisionamiento MF60 y MB21 (G6 y G7, 98 casos):** ¿qué necesita el caso además de material con stock? ¿Área de suministro de producción? ¿Una reserva previa? *Recomiendo: proponer material con stock libre que sea componente de un producto completo, y que me digas si hace falta área de suministro.*
5. **Casos que solo traen la planta (G12: 66 casos; en total 89 en PP, contando 15 anulaciones de salida y 6 subproductos):** ¿dependen de lo creado en otro caso? *Recomiendo: no proponer datos y marcar «No requiere» en la columna de origen, con la nota «consulta lo creado por otros casos». Si sabes de qué caso depende cada uno, lo anoto.*
6. **Dispositivos RF (G11, 31 casos):** ¿pasan a la fase WM, con el almacén WM de M105? *Recomiendo: sí.*
7. **Capacidad y PP/DS (G13, 30 casos):** ¿basta con comprobar que el material y la planta existen y tienen versión, sin proponer datos nuevos? *Recomiendo: sí.*
8. **Subcontratación (14 casos de versión):** ¿el material debe tener lista de subcontratación (clase de aprovisionamiento F, aprovisionamiento especial 30)? *Hoy no lo modelo. Recomiendo añadirlo.*
9. **Plantas:** ¿cuál descargo primero después de M116? *Recomiendo M024 (63 casos) y M022 (56). Y una opción «cargar todas las plantas de PP» con una sola confirmación.*

## Orden de implementación que propongo (más casos por menos esfuerzo)

1. **G5 Selección de versión** (17): ya se calcula con lo descargado.
2. **G2 Costing** (56): leer MAPL de tipo R.
3. **G3 Estado de material** (120): leer el estado del material (campo extra, sin tabla nueva).
4. **G4, G8, G9, G10 y G6** (≈260): leer las listas de materiales (STPO) y el stock de componentes. Es una sola ampliación para todos.
5. **G7** (38) y **G11** (31, con la fase WM).
6. **G12, G13, G14** (128): sin propuesta de datos, solo marcar «No requiere» y la nota.

Cada paso con su comprobación contigo, como el resto del plan.
