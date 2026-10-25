# Flujo: Movimientos de material (MB52 + MIGO)

Decisiones acordadas:
- Alcance: movimientos que NO requieren documento previo (sin pedido, orden de producción, pedido de venta...).
- Lote: estrategia automática FEFO (caducidad) y, si no hay caducidad, FIFO (fecha de entrada); reparte entre lotes.
- Stock insuficiente: se mueve lo disponible (parcial) y se registra la diferencia.
- Entorno: sandbox/QAS. Nunca producción.

Algoritmo por fila del Excel:
1. MB52 (material, centro, almacén origen; "mostrar lotes") -> stock libre y si hay lotes.
2. Sin stock -> estado SIN_STOCK, no se contabiliza.
3. Cantidad a mover = min(pedida, disponible); si es menor -> PARCIAL.
4. Material sin lote -> una MIGO. Con lote -> una línea MIGO por lote, ordenados FEFO/FIFO.
5. Se registra documento de material o error SAP.

Pendiente de validar con consultor MM: stocks especiales (E/Q/K/O), stock en calidad/bloqueado, UM alternativas.
