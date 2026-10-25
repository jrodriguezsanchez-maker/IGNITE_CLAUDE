# Flujo: Escenarios SIT con MIGO en el paso 1

Origen: Excel SIT (Jira), hoja `SCRIPTS` (una fila por paso). El fichero es de cliente: se sube desde el front
y queda en `data/` (fuera de git). El catálogo importado y los resultados tampoco se suben.

## Decisiones acordadas
- Alcance: escenarios con L1 = `5.SCM` y L2 = `5.6 Logistics Flows` (configurable en `flow.json`, clave `filtro`) cuyo paso 1
  contiene MIGO (incluye `MIGO || ...`). El resto de escenarios con MIGO (Warehouse Management, Finance, Controlling, PP, PM)
  queda fuera y la pantalla muestra cuántos son. La columna `Automatable` se ignora.
- Pantalla: la tabla usa los nombres y el orden de columnas del Excel; las columnas visibles y los filtros se configuran en `flow.json`.
- IDoc/EDI fuera de alcance: de `MIGO || EDI ...` solo se usa la parte SAP; los pasos que son solo EDI se descartan.
- Un escenario = `External ID - JIRA` (ID por unidad). Trazabilidad: `JIRA ID` (IG-xxxx) + ID por unidad en todas las salidas.
- Tipo de movimiento: explícito en `Data` si existe; si no, propuesta por reglas locales (`reglas_movimiento.json`).
  El usuario siempre lo confirma en el front antes de lanzar (el servidor rechaza escenarios sin confirmar).
- Lotes FEFO/FIFO, stock insuficiente = movimiento parcial, entorno sandbox/QAS.

## Interpretación del Data y datos que faltan
- El `Data` del paso 1 se interpreta en: centro origen/destino, almacén origen/destino, material(es), cantidad, vendor, CECO, orden, PO, lote, motivo.
- Si solo hay un centro, es origen y destino. En 343/344/321/322 el almacén destino es el de origen.
- `requisitos_movimiento.json` define qué exige SAP por movimiento (p. ej. 541/542 vendor, 201/551 CECO, 261 orden, 101 PO, 315/305 doc. de referencia).
  Si falta algún campo, el escenario no se ejecuta (FALTAN_DATOS) y la pantalla pide el dato.
- Prioridad de valores: aportado por el usuario > Excel > derivado / valor por centro > cantidad por defecto.
- Lo aportado se guarda en `data/` (por escenario o como valor por centro en `valores_centro.json`), nunca en git.
- Cantidad: valor global editable en la pantalla (por defecto 1), con posibilidad de fijarla por escenario.
- 701/702 no se hacen con MIGO (inventario físico MI01/MI04/MI07): estado NO_SOPORTADO. Movimientos sin requisitos definidos
  (325, 707/708, Z..) usan requisitos mínimos y se avisan; validar con consultor MM.
- Con SAP conectado (fase posterior): si falta material o almacén se buscarán candidatos con stock en MB52 y el usuario elige;
  nunca se elige uno automáticamente. También se comprobarán lote (marca en maestro), periodo abierto, bloqueos y almacén WM.

## Salida (pestañas, descargables en CSV)
- MM: movimientos y documentos de material (MB52 + MIGO).
- FI: apuntes contables por documento de material (FB03).
- CO: imputaciones (KE24).
- ML: valoración/precio (CKM3N).
- Pasos a validar: pasos 2..n del escenario con su transacción, equipo (FI/CO/ML/MM) y resultado esperado.

## Limitaciones actuales
- Modo simulado: stock, documentos y apuntes FI/CO/ML son inventados (formato definitivo).
- Cantidad: si el Excel no la indica se usa `cantidad_por_defecto` (1).
- Escenarios sin material o centro en el Excel -> SIN_DATOS. Los que requieren PO/orden previa se avisan.
- Los pasos MIGO posteriores al primero no se ejecutan todavía.

## Chequeo previo y cantidad
- Botón **Chequear datos** (solo lectura, no contabiliza nada): para los escenarios seleccionados comprueba datos completos, stock y lote
  (FEFO/FIFO) en centro/almacén origen y muestra un informe por escenario y material. Estados: LISTO, AVISO, FALTAN_DATOS, SIN_STOCK.
- En la tabla, cada escenario muestra **OK** (datos completos) o **NOK · n** (faltan n datos); al pulsarlo se abre el detalle para ver y modificar.
- Cantidad: si no se indica (Excel, escenario o centro) se usa el valor por defecto de la pantalla. Con SAP conectado, el chequeo propone la cantidad
  desde el stock libre del lote elegido y se usa solo si la aceptas antes de lanzar. El motor simulado no propone cantidades.
