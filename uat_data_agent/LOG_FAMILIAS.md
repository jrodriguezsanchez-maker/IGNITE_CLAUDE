# Logística por familias — qué necesita cada tipo de caso (propuesta en bloque de LOG)

Son **598 casos de LOG** (no ~1.900: ese número que dije antes estaba mal), con 170 escenarios distintos. Los he agrupado en 12 familias con lo que dicen los propios casos: el escenario, las transacciones y las etiquetas de la Data (porcentajes sobre los casos de cada familia). **Lo marcado como «propuesta» lo he deducido yo y necesita tu visto bueno antes de implementarlo.**

Cómo revisarlo: contesta solo con el número de pregunta, o «apruebo todas».

## Criterios de validez (los fijó el usuario; mandan sobre el resto del documento)

Un dato de logística sirve si cumple, por este orden:
1. **Los materiales existen en las plantas que trata el caso** (MARC, sin marca de borrado).
2. **Los materiales no tienen estado ZZ** (ni en la planta ni el general).
3. **Hay registro info** del material con datos de compras en la organización de compras de la planta compradora, en los pedidos de compra (ZPO, ZSPA, ZSER), de subcontratación (ZSPO, solo registros de tipo subcontratación) e interco (ZINT, con el proveedor `P` + planta emisora).
4. **Los proveedores existen para la sociedad Y para la organización de compras** de la planta (LFB1 y LFM1), sin bloqueos.
5. **Se muestra para cada planta su sociedad, su organización de compras y que el almacén existe en esa planta** (Org.Structure y T001L).
6. **El stock en origen es deseable, no obligatorio:** solo ordena la lista y sale como aviso, nunca bloquea.

## Qué ya está hecho y qué falta

- **Hecho:** el panel de un caso (fases 3 y 5): materiales con stock libre y ampliados en la planta receptora, clientes del área de ventas, proveedor `P` + planta en ZINT/ZINR, proveedores con datos de compras y registro info, puntos de planificación de transporte, y el contraste con ECC. Los datos de QS4 de LOG están leídos en **36 de las 38 plantas** (572 de 582 casos con planta); faltan 1 tabla en M024 y 1 en M025.
- **Falta:** la propuesta en bloque, que necesita unas reglas por familia que decidan qué se propone y qué se deja a mano. Eso es lo que te pido aprobar aquí.

## Resumen por familia

| # | Familia | Casos | Qué hace el caso (evidencia) | Qué necesita para ejecutarse (propuesta) | Tablas |
|---|---|---|---|---|---|
| L1 | Alta de rol de BP (transportistas, operadores) | 55 | Transacción BP; Data: solo planta y rol | «No requiere dato de SAP» | — |
| L2 | Condiciones de coste de transporte | 66 | TK11; Data: planta y punto de planificación de transporte | «No requiere»; solo se comprueba que el punto existe en la planta | TTDS |
| L3 | Envíos de transporte (ZLC, ZCL, ZMLI…) | 43 | VT01N, VI01, VI02; Data: planta, tipo de envío y punto de planificación | Comprobar que el punto de planificación existe; sin material ni stock | TTDS |
| L4 | Compra / entrada de proveedor | 48 | ME21N, VL31N, MIGO, MIRO; ZPO (43). Data: material (79 %), proveedor, org. de compras | Material del tipo de la Data **con registro info** del proveedor, y un proveedor con datos de compras en la org. de la planta | EINA, EINE, LFM1, MARC |
| L5 | Traslados entre plantas y sociedades | 47 | ZTRA, ZINT, ZINR, ZWIA; 77 % con planta emisora; 91 % con 2 plantas | Material con **stock libre en la emisora y ampliado en la receptora**; en ZINT proveedor `P` + emisora | MARD, MARC, LFA1 |
| L6 | Venta / salida a cliente | 25 | VA01, VL01N, VF01; Data: cliente (52 %), material | Material con stock en la planta y un cliente del área de ventas sin bloqueos | MARD, KNVV |
| L7 | Devoluciones | 51 | VL02N, VL10B, ZMMR0211; ZINR (28), ZTRA, ZINT, venta; 100 % con planta emisora | Depende de un traslado o venta previos: material de ese documento. **Se deja a mano** salvo cadena clara | los de L5 y L6 |
| L8 | Movimientos internos entre almacenes | 68 | MIGO con mensaje EDI del operador; 93 % con tipo de movimiento y almacén origen | Material con **stock en el almacén origen** (St-Loc ini) de la planta; almacén destino que exista | MARD por almacén, T001L |
| L9 | Estado de stock, calidad, chatarra, donaciones | 77 | Bloquear/desbloquear, control de calidad, destruir; MIGO, VA01 en donaciones | Material con stock libre en la planta; para bloquear, stock libre; para desbloquear, stock bloqueado | MARD (LABST, SPEME) |
| L10 | Palés | 32 | ZRPL (32 casos), compra o venta de palés | Material ZRPL con stock; proveedor (34 %) o cliente (19 %) según el caso | MARD, LFM1, KNVV |
| L11 | Subcontratación | 16 | ME21N, MIGO, VL31N; ZSPO (11); Data: proveedor (94 %), almacén | Proveedor subcontratista con registro info **de subcontratación** y componentes con stock | EINA, EINE, LFM1, MARD |
| L12 | Inventario, conciliación, interfaces e informes | 69 | Conciliación diaria, inventario físico, maestros al operador, pre-facturación; Data casi siempre solo planta | «No requiere»; si la Data trae material, se trata como L8 o L9 | — |

## Preguntas (con mi recomendación)

1. **L1, L2, L3, L12 (233 casos, el 39 %):** ¿«No requiere dato de SAP», comprobando solo que la planta o el punto de planificación existen? *Recomiendo: sí; lo que depende de ellos son documentos que se crean durante la prueba.*
2. **Papel por tipo de material:** como en QM, si la Data cita un tipo (ZFIN, ZRAW, ZPAC, ZSPN…), ¿se sustituye por otro del mismo tipo? *Recomiendo: sí.*
3. **Stock en origen:** ya decidido, es deseable y no bloquea (criterio 6). Solo queda decidir si el caso cita una cantidad concreta: *recomiendo mostrarla como aviso.*
4. **Un dato, un caso:** ¿reservo el material en esa planta para un solo caso (como en PP) o aceptas el mismo material en varios casos de logística? *Recomiendo: reservar solo el material, y avisar (no bloquear).*
5. **L7 devoluciones (51 casos):** ¿las dejo en «Revisar a mano» con una nota de qué documento previo hace falta? *Recomiendo: sí; elegir un material al azar no sirve si no hay documento que devolver.*
6. **L11 subcontratación (16 casos):** exige registro info de subcontratación. ¿Leo EINE completo para distinguirlo? *Recomiendo: sí; si no hay proveedor con ese registro, «Sin candidato».*
7. **L8 movimientos internos (68 casos):** ¿el almacén origen de la Data es obligatorio? *Recomiendo: sí; busco material con stock en ese almacén y, si no hay, otro almacén de la misma planta con aviso.*
8. **Los 238 casos sin flujo detectado** (movimientos internos, estado de stock, inventario…): se resuelven por la familia, no por el flujo ZPO/ZINT. *Recomiendo: sí.*
9. **Plantas:** faltan 1 tabla en M024 y 1 en M025 (leídas pendientes) y 16 casos no tienen planta en la Data. *Recomiendo: completar esas dos plantas y dejar los 16 en «Revisar a mano».*

## Orden que propongo

1. L5 traslados y L4 compras (son los de la fase 5 y los más directos: ya existen sus opciones).
2. L6 ventas y L10 palés.
3. L8 movimientos internos y L9 estado de stock (necesitan el stock por almacén).
4. L11 subcontratación (con EINE).
5. L1, L2, L3, L7, L12: «No requiere» o «Revisar a mano» según lo aprobado.
6. Propuesta en bloque por módulo (LOG), Excel y tu revisión de excepciones.
