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
- Al abrir un escenario (pulsando su OK/NOK) se ve **«Qué haría en SAP si se lanzara ahora»**: los pasos con su transacción y los valores concretos
  (lo que falta aparece como FALTA). Los datos que escribes en el detalle se guardan al salir del campo o al pulsar Intro.

## Chequeo con SAP real (solo lectura)
- Selector en la cabecera: **Chequeo simulado** (por defecto) o **Chequeo con SAP real**. El modo se guarda en `automatizaciones/conexion_local.json`
  (fuera de git, con la lista de sistemas/mandantes permitidos: solo el de pruebas). Plantilla: `conexion_local.ejemplo.json`.
- Con SAP real, «Chequear datos» lee el stock libre y los lotes con **MB52** (sesión abierta por el usuario, sin credenciales en ficheros) y propone la cantidad
  desde el stock libre del primer lote. Se aborta si la sesión no es de un sistema/mandante permitido, si SAP no está en la pantalla inicial o si aparece una ventana emergente.
- Aún no implementado con SAP real: registro info (ME13), almacenes WM (LS24), caducidad/fecha de entrada del lote (los lotes se ordenan por número de lote)
  y la **contabilización**: el lanzamiento sigue siendo simulado. Los escenarios que el chequeo dio sin stock, sin registro info o con error de SAP se excluyen del lanzamiento.
- Botón **Probar conexión SAP** (cabecera, solo lectura): indica si hay sesión en un sistema permitido, cuántas hay, cuántas libres y si el scripting responde.
- Sesiones: el programa usa una sesión **libre** (pantalla inicial, sin ventanas). Si todas están ocupadas **abre una sesión nueva**, la usa y la cierra al terminar;
  nunca cierra ni toca sesiones del usuario. Cada vez que el programa se engancha, SAP muestra el aviso de «un script se engancha» y lo acepta el usuario.
- **Solo se toca la conexión permitida:** `conexion_local.json` indica sistema, mandante y el nombre de la entrada de SAP Logon (`conexion`). El programa solo lee el
  nombre de las demás conexiones abiertas (p. ej. producción) y **no accede a sus sesiones**, ni siquiera para leerlas.
- `pywin32`: si no está en el Python del usuario se usa la copia de `automatizaciones/vendor/pywin32` (fuera de git). Hace falta porque la app de Claude es una aplicación
  empaquetada de Windows y un `pip install --user` hecho desde ella queda en una copia privada de AppData que no ven los procesos lanzados desde el Explorador.
- **Lote:** el chequeo devuelve los lotes en orden FEFO/FIFO y cómo se cubriría la cantidad (p. ej. «A × 600 + B × 400»). En el detalle del escenario hay un campo
  **Lote (opcional)** rellenado con esa propuesta y **editable**: lo que escribas manda (si el material es único; se guarda al salir del campo). Con SAP real se usa ese
  lote; con el motor simulado se ignora para no mezclar lotes reales con stock inventado. El lote también aparece en la tabla y en el plan «Qué haría en SAP».

## MIGO real (en preparación)
- Módulo `sap_migo.py`: traspasos 344/343 con modos «comprobar» (Check de MIGO, no contabiliza) y «contabilizar». Candados: solo movimientos 343/344, cantidad máxima,
  sistema/mandante permitidos y una **huella** calculada con los datos exactos (movimiento, material, centro, almacén, lote, cantidad **y motivo**) que el usuario confirma.
- QS4 exige el **motivo del movimiento** en el 344 (error del Check «Enter Reason for Movement» si falta). Va en la pestaña «Where» de MIGO (`GOITEM-GRUND`).
  En la pantalla es un desplegable con los motivos válidos de cada movimiento (lista facilitada por el usuario, guardada en `data/motivos_movimiento.json`, fuera de git).
- Lote: campo `GODYNPRO-CHARG` de la pestaña «Transfer Posting». El registro de mensajes del Check («Display logs») se lee: si tiene errores se aborta; si no, se cierra con Continue.
- Probado (Check, sin contabilizar): 344 · 1 KG · motivo 0046 (datos concretos en local, no versionados) → «Document is O.K.».
- Verificación posterior prevista: anotar el nº de documento de material, leerlo (MB51/MB03), comprobar movimiento, cantidad, lote y stock con MB52, y de ahí obtener los apuntes FI, CO y ML.

## Contabilización real desde el HTML (botón «Contabilizar en SAP…»)
- Solo con el chequeo en modo «SAP real» y en flujos de MIGO. Movimientos habilitados: **311, 343, 344** (cada tipo se habilita tras validarlo con el Check de MIGO; el 311 dio 0 errores y exige además el lote de recepción `UMCHA`, el mismo lote).
- Flujo: confirmar tipos → el servidor prepara los datos exactos de cada documento (lee MB52 para elegir un lote que cubra la cantidad) y calcula la huella → el diálogo enseña
  los datos (con el texto del motivo) → hay que **teclear CONTABILIZAR** → el servidor recalcula y solo continúa si la huella coincide.
- Máximo 5 documentos por ejecución. Un solo material por escenario y un solo lote que cubra la cantidad (repartir entre lotes aún no).
- Cada documento: stock antes (MB52) → MIGO (Check + Post) → stock después, y se marca CONTABILIZADO solo si el stock cambió como se esperaba. Se guarda el nº de documento de material.
- Pendiente: leer el documento y sus apuntes FI/CO/ML; STO (ME21N/VL10B); 301, 321/322, 541.
