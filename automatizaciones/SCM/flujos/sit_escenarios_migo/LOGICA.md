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
