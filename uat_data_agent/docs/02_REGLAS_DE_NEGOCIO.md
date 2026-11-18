# Reglas de negocio y de formato acordadas con el usuario

Fuente de verdad de flujos: `config/rules.yaml`. Fuente de verdad de los campos por transacción: `config/transacciones_modelo.xlsx` (rellenado por el usuario) + `engine/modelo_tx.py`. Análisis de apoyo: `TRANSACCIONES_DATA.md`, `LOG_FAMILIAS.md`, `QM_FAMILIAS.md`, `PP_FAMILIAS.md`.

## Formato del campo Data
Tres bloques separados por `-----------------------` (hay que **conservar siempre los separadores**):
1. **Organizativo**: P.Org, C.Code, S.Org, P.Grp, Sup. Plant, Plant, St.Loc…
2. **Tipo de documento**: Doc Type, **Mov.Type** (va con el tipo de documento), Transportation planning point…
3. **Transaccional**: BP / Vendor / Customer, Material, Batch, Component, Production line…

Etiquetas en **inglés** (el Excel es inglés). Si un material va en dos pasos el texto se conserva con la misma estructura; las parejas «A -> B» se mantienen en una línea.

### Prev.Data
`Prev.Data (descripción)` al **final** del Data = paso de comprobación que usa datos transaccionales de pasos anteriores (p. ej. `Prev.Data (purchase order)`, opcionalmente seguido de `, ` + más datos). Un paso que solo trae `Prev.Data` hereda el Data real anterior. Todos los pasos, también estos, tienen formulario y «＋ añadir campo».

## Valores por defecto
| Campo | Valor |
|---|---|
| Storage location | `1000` |
| Batch | `<< get from the system >>` |
| BOM Type | `1` (en casos de costes: `6`) |
| Routing Type | `N` (en costes: `R`) |
| Routing Counter | `01` (dos cifras) |
| Routing Number | la **hoja de ruta** (columna «hoja de ruta»); no duplicar la información |
| Una sola planta en el caso | planta emisora = planta final |
| Production line (puesto de trabajo) | **todos los pasos de PP salvo 5.1.1 (datos maestros)**; viene de la versión de fabricación (MKAL-MDV01). En datos maestros no se toca |
| Component | todos los pasos que **fabrican** (`FABRICA` en `modelo_tx.py`: MD11, MD12, MFBF, MF42N, MF12, CO01, CO02, CO11N) y los de **staging/consumo** (descripción/escenario/Data con stag·consum·component·goods issue·261/262) en PP salvo 5.1.1 |
| S.Org | se muestra «org / canal» (p. ej. `9000 / 10`); no mezclar canal con división |

Placeholders (`<<…>>`, `XXXX`) no cuentan como valor original.

## Flujos de logística (`rules.yaml`)
- **ZTRA** traslado en la misma sociedad; **ZTRA entre sociedades es un error de datos**.
- **ZWIA** (plant abroad): como ZTRA, misma sociedad, distinto país.
- **ZINT / ZINR**: traslado/devolución entre sociedades; proveedor «P» + planta emisora (p. ej. `PL101`); registro info preferente.
- **ZPO** compra (registro info obligatorio) · **ZSPO** subcontratación (registro info tipo 3) · **ZSPA** repuestos y pallets de alquiler · **ZSER** servicios · **ZPAS** descartado.
- **Venta**: cliente del área de ventas + material vendible (MVKE) + stock en planta. En compras no hace falta cliente. Regla de clasificación de ventas y de transfer orders en `build()` (`avisos_data`).
- Tipos de material: ZFIN terminado · ZSEM semielaborado · ZFOR formulado · ZRAW materia prima · ZPAC packaging · ZRPL pallets · ZSPN/ZSPV repuestos.
- Modelo **dedicado**: cada material/stock/equipo pertenece a un solo caso; un material se reserva **por planta**; un material «modelo» (PP creación) solo se copia, no se consume.

### Proveedor y registro info (corregido el 16/11)
Un material solo sirve en una compra si tiene **registro info válido CON ESE proveedor** en la org. de compras de la planta compradora (EINA/EINE, sin marca de borrado; en ZSPO, subcontratación). Si no se ha elegido proveedor se usa el de la Data del caso. No afirmar «no existe en EINA» si los registros de ese proveedor no están leídos del todo (se muestra «?»). Ejemplo real (16/11): en una compra ZPO había dos materiales con registro info solo con otro proveedor; la lista los marcaba aptos porque no se tenía en cuenta el proveedor del caso.
Grupo de compras (P.Grp): hoy se toma de la org. de compras; el real (MARC-EKGRP) está **sin leer** (~45 min de SAP).

## Tramos (cadenas)
Casos con ≥2 ME21N o paso «Automatic creation – Stock Transfer Order»: se detectan tramos con Plant 1/2/3. Las transfer orders van de la planta A a la B y de la B a la C según el Excel; sin traslado a la misma planta. «Se parte de una compra a un proveedor» en los flujos de import/export.

## PP
- Creación (≈170 de 780 casos PP): el caso necesita lo previo y que falte lo que se crea (BOM/ruta/versión/cost collector). En «Material Creation» los números de la Data son los **modelos** (deben existir en la planta).
- Puesto de trabajo = línea de producción de la versión de fabricación; la hoja de ruta sale de esa versión.
- Casos de 5.1.1 (datos maestros): **ya trabajados por el usuario, no tocar**.
- Listas de PP: todas con checkbox; selección múltiple; solo lo marcado va a la propuesta. Componentes: panel por producto (`<details>`), filas deduplicadas.
- Pasos de planificación (PLAN/STAGE) con Data vacía también se proponen (rellenan `componentes`).

## QM
- Los tipos de inspección son **familias** por prefijo (`ZQMPP*`, `ZQMEM*`); `ZPAS` se ignora. Los requisitos se leen del escenario (`qm_requisitos`). Reemplazo de material del **mismo tipo** que el original; sin candidato del mismo tipo → «Sin candidato» (189 casos).
- El usuario validó con calidad los registros info; la herramienta no debe decir que «no existe» algo que calidad ha validado.

## Selección en la UI
Checkbox por fila; marcar/desmarcar; **solo lo marcado va a la propuesta**; chips «Seleccionados» siempre visibles. Materiales originales marcados se conservan; los nuevos ocupan huecos libres por tipo; los desmarcados se quitan; los extra se añaden a la línea del tipo (`_mapea_materiales`).

## Rationale
Razón por la que se propone cada material, **arriba en la tarjeta del caso, colapsado por defecto**. La sección de chequeos también va colapsada. No usar una caja de notas aparte en el paso 3.
