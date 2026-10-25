# Flujo: Transfer orders (pedidos de traslado, STO): ZTRA / ZINT / ZWIA

"Transfer order" aquí = pedido de traslado (STO): se crea con ME21N y se consulta con ME23N. No es la transfer order de WM (LT0x).

## Alcance
- Origen: Excel SIT (Jira), hoja `SCRIPTS`. Entra todo escenario con un paso **ME21N** cuyo Data o descripción mencione ZTRA, ZINT o ZWIA
  (si no, se mira el resto del escenario). Sin filtro por L1/L2. Los ME21N sin esos tipos quedan fuera y la pantalla muestra cuántos.
- Tipo de documento: se detecta del texto. Si el Excel lista varios tipos, no se propone ninguno y lo eliges tú. Siempre se confirma antes de lanzar.
- Fase 1: validar registro info, buscar lote con stock, crear STO y crear entrega de salida. Picking, salida de mercancía, entrada (MIGO),
  facturación intercompany y validaciones FI/CO/ML quedan para fases posteriores (los pasos aparecen como «se entrega para validar»).
- Los pasos del Excel se clasifican en: previo (antes del ME21N, no se automatiza), STO, entrega y posterior.

## Datos (requisitos_sto.json)
Obligatorios: centro y almacén suministrador, centro receptor, material, cantidad, org. compras, grupo de compras, sociedad y
si el almacén suministrador es WM (S/N, se pregunta por escenario). ZINT y ZWIA añaden incoterms. Opcionales: almacén receptor, org. ventas.
No hay derivación de centro destino = origen (en un STO son distintos). Lo que falta se completa en pantalla, por escenario o como valor del centro.

## Orden de ejecución por escenario
1. Resolver datos y comprobar obligatorios (si faltan: FALTAN_DATOS).
2. Registro info por material con el centro suministrador (ME13, EINA/EINE). Si falta alguno se **para el escenario** y se avisa (SIN_REGISTRO_INFO).
3. Stock en centro/almacén suministrador: MB52, o cuantos WM (LS24/LX02) si el almacén es WM. Lote FEFO/FIFO. Stock insuficiente = parcial.
4. Crear STO (ME21N) y entrega de salida (VL01N por referencia al STO).

## Pendiente de validar con consultor MM/SD
- Requisitos reales por tipo (campos obligatorios, partida aduanera/Intrastat en ZWIA, cliente del centro receptor en ZINT).
- Con SAP conectado: detectar WM leyendo la asignación de número de almacén (T320), tipo de entrega por tipo de STO, punto de expedición.
- Modo simulado: registro info, stock, STO y entrega son inventados (formato definitivo).
