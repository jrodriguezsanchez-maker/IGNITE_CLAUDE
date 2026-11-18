# Transacciones más frecuentes y qué lleva hoy su Data

Sale de los **2472 casos y 7079 pasos** del fichero UAT (243 transacciones distintas; las 25 primeras suponen el 68 % de los pasos). Para cada una: cuántos pasos y casos tiene, en qué módulos aparece, **qué etiquetas lleva hoy su Data** (porcentaje de pasos que la llevan), las combinaciones más repetidas, un ejemplo real y **qué hace hoy la aplicación con cada etiqueta**. La columna «Debe salir» la dejo en blanco para que me digas qué datos necesita de verdad cada paso.

## Lo que hoy pasa con todos los pasos

- En **1326 de 1332 casos con varios pasos (99,5 %) todos los pasos llevan exactamente el mismo texto de Data**: el del primer paso, copiado. No hay un Data propio de cada transacción. Una ME21N y una MFBF de un mismo caso muestran lo mismo.
- La aplicación no construye el Data por transacción: toma el texto del Excel y le sustituye valores. Lo que sabe tocar hoy:

| Etiqueta del Data | Qué hace hoy la aplicación |
|---|---|
| Material | se sustituye por lo marcado |
| Plant | planta del caso |
| Plant 2/3 | planta del caso (cadenas) |
| Supplier Plant | planta emisora (traslados) |
| Destination Plant | planta receptora |
| C.Code | sociedad de la planta |
| P.Org | org. de compras de la planta |
| S.Org | org. de ventas (se conserva «org / canal») |
| Doc Type | tipo de pedido (solo logística) |
| BP - Vendor | proveedor (ZPO y ZSPO) |
| BP - Customer | cliente (ventas) |
| BP | cliente (ventas) |
| St.Loc | almacén receptor |
| cualquier otra etiqueta (Mov. Type, Work Center…, tipos de inspección, etc.) | se copia tal cual, no se propone ni se valida |

## Las 40 transacciones más frecuentes

| # | Transacción | Pasos | Casos | Módulos | Etiquetas que lleva hoy (% de pasos) | Sin tratar por la app | Debe salir |
|---|---|---|---|---|---|---|---|
| 1 | **FB03** | 1110 | 1107 | LOG 437, WM 363, PP 179 | Plant 98%, Material 90%, C.Code 23%, P.Org 22%, Doc Type 21%, S.Org 15%, St.Loc 11%, Mov. Type 11%, Supplier Plant 9%, BP 8% | Mov. Type | |
| 2 | **KE24 / CKM3N** | 1093 | 1093 | LOG 420, WM 363, PP 179 | Plant 98%, Material 90%, C.Code 22%, P.Org 21%, Doc Type 21%, S.Org 15%, St.Loc 11%, Mov. Type 10%, Supplier Plant 8%, BP 8% | Mov. Type | |
| 3 | **MIGO** | 376 | 327 | LOG 202, WM 114, PM 26 | Plant 98%, Material 90%, Mov. Type 33%, St.Loc 27%, C.Code 22%, P.Org 21%, Doc Type 16%, BP 11% | Mov. Type | |
| 4 | **VL02N** | 290 | 181 | LOG 273, WM 17 | Plant 100%, Material 98%, Doc Type 88%, S.Org 60%, P.Org 59%, C.Code 59%, Supplier Plant 51%, BP 27%, St.Loc 15%, BP - Customer 10%, Shipping Point 8% | Shipping Point | |
| 5 | **ME21N** | 211 | 194 | LOG 182, PM 17, QM 12 | Plant 99%, Doc Type 91%, P.Org 90%, Material 90%, C.Code 85%, Supplier Plant 42%, BP 24%, S.Org 23%, St.Loc 20%, BP - Vendor 14% | — | |
| 6 | **MFBF** | 206 | 191 | PP 206 | Material 98%, Plant 93% | — | |
| 7 | **MD11** | 154 | 154 | PP 154 | Material 96%, Plant 92%, Doc Type 27% | — | |
| 8 | **VL32N** | 154 | 127 | LOG 137, WM 17 | Plant 100%, Material 89%, P.Org 87%, Doc Type 86%, C.Code 79%, Supplier Plant 40%, S.Org 23%, BP - Vendor 23%, BP 21%, St.Loc 16% | — | |
| 9 | **CO2 Report** | 154 | 120 | LOG 154 | Plant 100%, Doc Type 96%, Material 94%, S.Org 61%, P.Org 59%, C.Code 59%, BP 38%, Supplier Plant 33%, BP - Customer 17%, St.Loc 16%, BP - Vendor 9% | — | |
| 10 | **QE51N** | 109 | 109 | QM 109 | Plant 100%, Material 100% | — | |
| 11 | **VL01N** | 96 | 95 | LOG 84, QM 12 | Plant 100%, Material 98%, Doc Type 78%, S.Org 65%, P.Org 42%, BP 35%, C.Code 31%, Supplier Plant 22%, Shipping Point 21%, BP - Customer 21%, St.Loc 20%, Plant 2/3 8% | Shipping Point | |
| 12 | **QA32** | 92 | 92 | QM 87, LOG 4, PP 1 | Plant 100%, Material 100%, P.Org 17% | — | |
| 13 | **MD61** | 90 | 90 | PP 90 | Material 100%, Plant 93% | — | |
| 14 | **CS01** | 72 | 72 | PP 70, LOG 2 | Material 98%, Plant 93% | — | |
| 15 | **VA01** | 72 | 72 | LOG 72 | Plant 100%, Material 100%, S.Org 97%, Doc Type 87%, BP 61%, Shipping Point 30%, BP - Customer 30%, St.Loc 26%, C.Code 11%, P.Org 9% | Shipping Point | |
| 16 | **TK11** | 66 | 66 | LOG 66 | C.Code 100%, S.Org 100%, P.Org 100%, Plant 100%, Transp. Planning Point 100% | Transp. Planning Point | |
| 17 | **CA01** | 61 | 61 | PP 61 | Material 100%, Plant 93% | — | |
| 18 | **MF60** | 61 | 61 | PP 61 | Material 98%, Plant 93% | — | |
| 19 | **VL31N** | 57 | 56 | LOG 57 | P.Org 98%, Plant 98%, Doc Type 96%, C.Code 85%, Material 71%, BP - Vendor 43%, BP 40%, S.Org 22%, St.Loc 22% | — | |
| 20 | **VL10B** | 56 | 54 | LOG 56 | Plant 100%, Doc Type 98%, Material 96%, P.Org 89%, C.Code 87%, Supplier Plant 76%, S.Org 42%, BP 17%, St.Loc 14% | — | |
| 21 | **BP** | 55 | 55 | LOG 55 | C.Code 100%, S.Org 100%, P.Org 100%, Plant 100%, BP Role 100% | BP Role | |
| 22 | **MDM Fiori App** | 53 | 53 | PP 53 | Material 98%, Plant 94% | — | |
| 23 | **MB21** | 53 | 53 | PP 53 | Material 94%, Plant 86% | — | |
| 24 | **LM02** | 51 | 43 | WM 51 | Plant 100%, Material 100% | — | |
| 25 | **C223** | 49 | 49 | PP 47, LOG 2 | Material 100%, Plant 93% | — | |
| 26 | **VF01** | 49 | 48 | LOG 49 | Plant 100%, Material 97%, Doc Type 93%, S.Org 63%, P.Org 55%, C.Code 53%, BP 48%, Supplier Plant 40%, St.Loc 26%, Shipping Point 24%, Plant 2/3 16% | Shipping Point | |
| 27 | **MIRO** | 48 | 41 | LOG 47, PM 1 | Plant 100%, P.Org 97%, Doc Type 97%, Material 95%, C.Code 72%, BP - Vendor 37%, Supplier Plant 29%, BP 29%, S.Org 20%, Plant 2/3 18%, St.Loc 10% | — | |
| 28 | **IW32** | 46 | 46 | PM 46 | C.Code 100%, Plant 100%, Doc Type 100%, Functional Location 100%, Equipment 78% | Functional Location, Equipment | |
| 29 | **QM01** | 45 | 45 | QM 45 | Plant 100%, Doc Type 100%, Material 100% | — | |
| 30 | **LT12** | 45 | 39 | WM 45 | Plant 100%, Material 100% | — | |
| 31 | **VI01** | 45 | 43 | LOG 45 | C.Code 100%, S.Org 100%, P.Org 100%, Plant 100%, Shipment Type 100%, Transp. Planning Point 100% | Shipment Type, Transp. Planning Point | |
| 32 | **MSC2N** | 44 | 44 | QM 30, WM 14 | Plant 100%, Material 100% | — | |
| 33 | **VI02** | 43 | 43 | LOG 43 | C.Code 100%, S.Org 100%, P.Org 100%, Plant 100%, Shipment Type 100%, Transp. Planning Point 100% | Shipment Type, Transp. Planning Point | |
| 34 | **MM02** | 42 | 42 | QM 27, PP 15 | Plant 97%, Material 97%, P.Org 28% | — | |
| 35 | **LT01** | 42 | 42 | WM 42 | Plant 100%, Material 100% | — | |
| 36 | **VT01N** | 41 | 41 | LOG 41 | C.Code 100%, S.Org 100%, P.Org 100%, Plant 100%, Shipment Type 100%, Transp. Planning Point 100% | Shipment Type, Transp. Planning Point | |
| 37 | **ZWM027** | 39 | 20 | WM 38, PP 1 | Plant 100%, Material 100% | — | |
| 38 | **ZPLM** | 36 | 22 | PP 21, QM 15 | Plant 100%, Material 100% | — | |
| 39 | **LT22** | 36 | 36 | WM 35, LOG 1 | Plant 100%, Material 100% | — | |
| 40 | **ZWM095** | 36 | 36 | WM 36 | Plant 100%, Material 100% | — | |

## Detalle de las 25 primeras

### 1. FB03 — 1110 pasos, 1107 casos
- Descripción más habitual del paso: «Check FI accounting entries» (1093); «Check FICO accounting» (14)
- Flujos: — 803, ZPO 74, VENTA 71, ZINT 45, TRANSPORTE 43
- Combinaciones de etiquetas más repetidas (de arriba abajo, en el orden del Excel):
  - 612 pasos (55 %): Plant → Material
  - 63 pasos (5 %): Plant → St.Loc → Mov. Type → Material
  - 43 pasos (3 %): C.Code → S.Org → P.Org → Plant → Shipment Type → Transp. Planning Point
- Ejemplo real (SIT-SCM-H-5.1.1-266_AGRATE):
```
Plant: M116
-----------------------
Material: 526753
546653
545358
526659
542608
528305
```
- **Debe salir:** _(pendiente)_

### 2. KE24 / CKM3N — 1093 pasos, 1093 casos
- Descripción más habitual del paso: «Check CO-PA / Material Ledger entries» (1093)
- Flujos: — 797, ZPO 74, VENTA 71, ZINT 44, TRANSPORTE 38
- Combinaciones de etiquetas más repetidas (de arriba abajo, en el orden del Excel):
  - 612 pasos (55 %): Plant → Material
  - 63 pasos (5 %): Plant → St.Loc → Mov. Type → Material
  - 38 pasos (3 %): C.Code → S.Org → P.Org → Plant → Shipment Type → Transp. Planning Point
- Ejemplo real (SIT-SCM-H-5.1.1-266_AGRATE):
```
Plant: M116
-----------------------
Material: 526753
546653
545358
526659
542608
528305
```
- **Debe salir:** _(pendiente)_

### 3. MIGO — 376 pasos, 327 casos
- Descripción más habitual del paso: «Internal LO movement» (63); «Perform Goods Receipt for the STO in the receiving plant.» (12)
- Flujos: — 299, ZPO 41, ZSPO 17, ZINT 7, ZSER 6
- Combinaciones de etiquetas más repetidas (de arriba abajo, en el orden del Excel):
  - 136 pasos (36 %): Plant → Material
  - 63 pasos (16 %): Plant → St.Loc → Mov. Type → Material
  - 30 pasos (7 %): Plant → Mov. Type → Material
- Ejemplo real (SIT-SCM-H-5.1.4-230_KEBBI):
```
Plant: M024
-----------------------
Material: 314601
314602
329390
324872
329391
```
- **Debe salir:** _(pendiente)_

### 4. VL02N — 290 pasos, 181 casos
- Descripción más habitual del paso: «Make the PGI» (37); «Picking» (30)
- Flujos: VENTA 106, ZINT 66, ZINR 55, ZTRA 23, — 17
- Combinaciones de etiquetas más repetidas (de arriba abajo, en el orden del Excel):
  - 63 pasos (21 %): C.Code → P.Org → S.Org → Supplier Plant → Plant → Doc Type → Material
  - 54 pasos (18 %): C.Code → P.Org → Supplier Plant → Plant → Doc Type → Material
  - 35 pasos (12 %): S.Org → Plant → Doc Type → BP → Material
- Ejemplo real (SIT-SCM-H-5.6.1-39_LAGOS):
```
C.Code: 5900
P.Org: NG01
S.Org: 5300
Supplier Plant: L046
Plant: M022
-----------------------
Doc Type: ZTRA
-----------------------
Material: 107483 535154, 88634711
88634747
```
- **Debe salir:** _(pendiente)_

### 5. ME21N — 211 pasos, 194 casos
- Descripción más habitual del paso: «Create the Stock Transfer Order» (45); «Create the purchase order» (33)
- Flujos: ZPO 78, ZINT 44, ZINR 31, ZSER 24, ZTRA 14
- Combinaciones de etiquetas más repetidas (de arriba abajo, en el orden del Excel):
  - 33 pasos (15 %): C.Code → P.Org → S.Org → Supplier Plant → Plant → Doc Type → Material
  - 31 pasos (14 %): C.Code → P.Org → Supplier Plant → Plant → Doc Type → Material
  - 19 pasos (9 %): P.Org → C.Code → Plant → St.Loc → Doc Type → BP → Material
- Ejemplo real (SIT-SCM-H-5.6.1-39_LAGOS):
```
C.Code: 5900
P.Org: NG01
S.Org: 5300
Supplier Plant: L046
Plant: M022
-----------------------
Doc Type: ZTRA
-----------------------
Material: 107483 535154, 88634711
88634747
```
- **Debe salir:** _(pendiente)_

### 6. MFBF — 206 pasos, 191 casos
- Descripción más habitual del paso: «Good reception or moved current stock» (105); «Post the good reception against cost collector» (25)
- Flujos: — 206
- Combinaciones de etiquetas más repetidas (de arriba abajo, en el orden del Excel):
  - 187 pasos (90 %): Plant → Material
  - 14 pasos (6 %): Material
  - 4 pasos (1 %): Plant
- Ejemplo real (SIT-SCM-H-5.1.1-256_AGRATE):
```
Plant: M116
-----------------------
Material: 542608
```
- **Debe salir:** _(pendiente)_

### 7. MD11 — 154 pasos, 154 casos
- Descripción más habitual del paso: «Planned order creation» (90); «Create a manual planned orders» (64)
- Flujos: — 154
- Combinaciones de etiquetas más repetidas (de arriba abajo, en el orden del Excel):
  - 103 pasos (66 %): Plant → Material
  - 35 pasos (22 %): Plant → Doc Type → Material
  - 6 pasos (3 %): Material
- Ejemplo real (SIT-SCM-H-5.1.1-257_AGRATE):
```
Plant: M116
-----------------------
Material: 542608
```
- **Debe salir:** _(pendiente)_

### 8. VL32N — 154 pasos, 127 casos
- Descripción más habitual del paso: «Post the good receipt» (76); «Add lines regarding rental pallet and post the good receipt» (12)
- Flujos: ZPO 47, ZINT 45, — 18, ZTRA 16, ZSER 12
- Combinaciones de etiquetas más repetidas (de arriba abajo, en el orden del Excel):
  - 21 pasos (13 %): C.Code → P.Org → Supplier Plant → Plant → Doc Type → Material
  - 20 pasos (12 %): C.Code → P.Org → S.Org → Supplier Plant → Plant → Doc Type → Material
  - 17 pasos (11 %): Plant → Material
- Ejemplo real (SIT-SCM-H-5.6.1-31_GHANA):
```
C.Code: 6100
P.Org: GH01
Supplier Plant: L063
Plant: M021
-----------------------
Doc Type: ZTRA
-----------------------
Material: 535155
541184
```
- **Debe salir:** _(pendiente)_

### 9. CO2 Report — 154 pasos, 120 casos
- Descripción más habitual del paso: «validate CO2 report» (154)
- Flujos: VENTA 68, ZINT 31, ZPO 30, ZTRA 9, ZINR 8
- Combinaciones de etiquetas más repetidas (de arriba abajo, en el orden del Excel):
  - 25 pasos (16 %): S.Org → Plant → Doc Type → BP → Material
  - 24 pasos (15 %): C.Code → P.Org → S.Org → Supplier Plant → Plant → Doc Type → Material
  - 24 pasos (15 %): S.Org → Plant → Doc Type → BP - Customer → Material
- Ejemplo real (SIT-SCM-H-5.6.3-59_GERMANY):
```
S.Org: 8200 / 10 / 10
Plant: L051
-----------------------
Doc Type: ZAWI
-----------------------
BP: 76936
Material: 537891
```
- **Debe salir:** _(pendiente)_

### 10. QE51N — 109 pasos, 109 casos
- Descripción más habitual del paso: «Enter Material, and other details and click Execute. Select the Inspec» (75); «Record the Inspection Results either in Worklist (QE51N) or Individual» (30)
- Flujos: — 109
- Combinaciones de etiquetas más repetidas (de arriba abajo, en el orden del Excel):
  - 109 pasos (100 %): Plant → Material
- Ejemplo real (SIT-SCM-H-5.2.2-573_ALCANIZ):
```
Plant: M105
-----------------------
ZPO
-----------------------
Material ZRAW: 100580
Material ZPAC: 301128
```
- **Debe salir:** _(pendiente)_

### 11. VL01N — 96 pasos, 95 casos
- Descripción más habitual del paso: «Create the outbound delivery» (53); «Create an Outbound Delivery for the Material to be transferred.» (12)
- Flujos: VENTA 56, ZINT 22, ZPO 15, ZTRA 2, ZSPA 1
- Combinaciones de etiquetas más repetidas (de arriba abajo, en el orden del Excel):
  - 18 pasos (18 %): S.Org → Plant → Doc Type → BP - Customer → Material
  - 12 pasos (12 %): Plant → P.Org → Material
  - 9 pasos (9 %): S.Org → Plant → Doc Type → BP → Material
- Ejemplo real (SIT-SCM-H-5.6.3-59_FRANCE):
```
S.Org: 8600 / 99 / 10
Plant: L057
-----------------------
Doc Type: ZAWI
-----------------------
BP - Customer: 1000002
Material: 546390
```
- **Debe salir:** _(pendiente)_

### 12. QA32 — 92 pasos, 92 casos
- Descripción más habitual del paso: «Enter the Usage Decision if Accepted. In the Usage Decision Screen, wi» (15); «Enter the Usage Decision if Rejected. In the Usage Decision Screen, wi» (15)
- Flujos: — 77, ZPO 13, ZINT 2
- Combinaciones de etiquetas más repetidas (de arriba abajo, en el orden del Excel):
  - 76 pasos (82 %): Plant → Material
  - 12 pasos (13 %): Plant → P.Org → Material
  - 1 pasos (1 %): C.Code → P.Org → Supplier Plant → Plant → Doc Type → Material
- Ejemplo real (SIT-SCM-H-5.1.5-243_KEBBI):
```
Plant: M024
-----------------------
Material: 518850
```
- **Debe salir:** _(pendiente)_

### 13. MD61 — 90 pasos, 90 casos
- Descripción más habitual del paso: «Creation of Planned Indepence Requirement» (90)
- Flujos: — 90
- Combinaciones de etiquetas más repetidas (de arriba abajo, en el orden del Excel):
  - 84 pasos (93 %): Plant → Material
  - 6 pasos (6 %): Material
- Ejemplo real (SIT-SCM-H-5.1.1-257_AGRATE):
```
Plant: M116
-----------------------
Material: 542608
```
- **Debe salir:** _(pendiente)_

### 14. CS01 — 72 pasos, 72 casos
- Descripción más habitual del paso: «Creation of bill of material» (45); «Create a costing bill of material» (11)
- Flujos: — 70, ZSPO 2
- Combinaciones de etiquetas más repetidas (de arriba abajo, en el orden del Excel):
  - 62 pasos (86 %): Plant → Material
  - 5 pasos (6 %): Material
  - 2 pasos (2 %): Plant → Material → Scrap Component
- Ejemplo real (SIT-SCM-H-5.1.1-226_KEBBI):
```
Plant: M024
-----------------------
Material: 518850, 518856, 518859
```
- **Debe salir:** _(pendiente)_

### 15. VA01 — 72 pasos, 72 casos
- Descripción más habitual del paso: «Create the sales order to customer» (36); «Create sales order to customer» (8)
- Flujos: VENTA 70, ZINT 1, ZTRA 1
- Combinaciones de etiquetas más repetidas (de arriba abajo, en el orden del Excel):
  - 19 pasos (26 %): S.Org → Plant → Doc Type → BP - Customer → Material
  - 18 pasos (25 %): S.Org → Plant → Doc Type → BP → Material
  - 10 pasos (13 %): S.Org → Plant → St.Loc → Shipping Point → Doc Type → BP → Material
- Ejemplo real (SIT-SCM-H-5.6.3-58_SPAIN):
```
S.Org: 1200 / 10 / 10
Plant: L101
-----------------------
Doc Type: ZADO
-----------------------
BP - Customer: 63610
Material: 524730, 546447
```
- **Debe salir:** _(pendiente)_

### 16. TK11 — 66 pasos, 66 casos
- Descripción más habitual del paso: «Cost condition input» (66)
- Flujos: TRANSPORTE 66
- Combinaciones de etiquetas más repetidas (de arriba abajo, en el orden del Excel):
  - 66 pasos (100 %): C.Code → S.Org → P.Org → Plant → Transp. Planning Point
- Ejemplo real (SIT-SCM-H-5.5.1-13_BELGIUM):
```
Company Code: 8600
Sales Org: 4000
Purchase Org: BE01
Plant: L056
-----------------------
Transportation planning point: 4000
-----------------------
<<< shiptment document >>
```
- **Debe salir:** _(pendiente)_

### 17. CA01 — 61 pasos, 61 casos
- Descripción más habitual del paso: «Creation of routing» (45); «Create a manufacturing Routing» (15)
- Flujos: — 61
- Combinaciones de etiquetas más repetidas (de arriba abajo, en el orden del Excel):
  - 57 pasos (93 %): Plant → Material
  - 4 pasos (6 %): Material
- Ejemplo real (SIT-SCM-H-5.1.1-228_KEBBI):
```
Plant: M024
-----------------------
Material: 518850, 518856, 518859
```
- **Debe salir:** _(pendiente)_

### 18. MF60 — 61 pasos, 61 casos
- Descripción más habitual del paso: «Run the reservation/stagging» (61)
- Flujos: — 61
- Combinaciones de etiquetas más repetidas (de arriba abajo, en el orden del Excel):
  - 56 pasos (91 %): Plant → Material
  - 4 pasos (6 %): Material
  - 1 pasos (1 %): Plant
- Ejemplo real (SIT-SCM-H-5.1.4-282_AGRATE):
```
Plant: M116
-----------------------
Material: 528305
```
- **Debe salir:** _(pendiente)_

### 19. VL31N — 57 pasos, 56 casos
- Descripción más habitual del paso: «Create the inbound delivery» (24); «Create inbound delivery» (15)
- Flujos: ZPO 39, ZSER 6, ZINT 5, ZSPA 3, ZSPO 3
- Combinaciones de etiquetas más repetidas (de arriba abajo, en el orden del Excel):
  - 10 pasos (17 %): C.Code → P.Org → Plant → Doc Type → BP - Vendor → Material
  - 7 pasos (12 %): P.Org → C.Code → Plant → St.Loc → Doc Type → BP → Material
  - 6 pasos (10 %): Doc Type → BP - Vendor → P.Org → Plant → Material
- Ejemplo real (SIT-SCM-H-5.6.2-21_IMPORT_EXPORT):
```
C.Code: 4000
P.Org: ES01
Plant: L031 (1000)
-----------------------
Doc Type: ZPO
-----------------------
BP - Vendor: 142777
Material: 101043
```
- **Debe salir:** _(pendiente)_

### 20. VL10B — 56 pasos, 54 casos
- Descripción más habitual del paso: «Create the outbound delivery» (32); «Outbound delivery creation» (10)
- Flujos: ZINR 19, ZINT 17, VENTA 6, ZPO 5, ZTRA 4
- Combinaciones de etiquetas más repetidas (de arriba abajo, en el orden del Excel):
  - 16 pasos (28 %): C.Code → P.Org → Supplier Plant → Plant → Doc Type → Material
  - 16 pasos (28 %): C.Code → P.Org → S.Org → Supplier Plant → Plant → Doc Type → Material
  - 6 pasos (10 %): S.Org → Plant → Doc Type → BP → Material
- Ejemplo real (SIT-SCM-H-5.6.1-31_GHANA):
```
C.Code: 6100
P.Org: GH01
Supplier Plant: L063
Plant: M021
-----------------------
Doc Type: ZTRA
-----------------------
Material: 535155
541184
```
- **Debe salir:** _(pendiente)_

### 21. BP — 55 pasos, 55 casos
- Descripción más habitual del paso: «Create the BP Role» (55)
- Flujos: — 55
- Combinaciones de etiquetas más repetidas (de arriba abajo, en el orden del Excel):
  - 55 pasos (100 %): C.Code → S.Org → P.Org → Plant → BP Role
- Ejemplo real (SIT-SCM-H-5.5.1-10_ballobar):
```
Company Code: 2800
Sales Org: 4000 - PASA Industrial
Purchase Org: ES01
Plant: L035
-----------------------
BP Role: ZFLVN001
```
- **Debe salir:** _(pendiente)_

### 22. MDM Fiori App — 53 pasos, 53 casos
- Descripción más habitual del paso: «Create the material» (51); «Create a material» (2)
- Flujos: — 53
- Combinaciones de etiquetas más repetidas (de arriba abajo, en el orden del Excel):
  - 49 pasos (92 %): Plant → Material
  - 3 pasos (5 %): Material
  - 1 pasos (1 %): Plant
- Ejemplo real (SIT-SCM-H-5.1.1-253_AGRATE):
```
Plant: M116
-----------------------
Material: 526659
542608, 527832
```
- **Debe salir:** _(pendiente)_

### 23. MB21 — 53 pasos, 53 casos
- Descripción más habitual del paso: «Move packaging material to stagging area» (38); «Null good issues / Reversal» (15)
- Flujos: — 53
- Combinaciones de etiquetas más repetidas (de arriba abajo, en el orden del Excel):
  - 44 pasos (83 %): Plant → Material
  - 6 pasos (11 %): Material
  - 2 pasos (3 %): Plant
- Ejemplo real (SIT-SCM-H-5.1.4-232_ALCANIZ_FLAVOUR):
```
Plant: M105
-----------------------
Material: 107178 -> 545224
```
- **Debe salir:** _(pendiente)_

### 24. LM02 — 51 pasos, 43 casos
- Descripción más habitual del paso: «TO confirmation » (16); «Stock removal » (16)
- Flujos: — 51
- Combinaciones de etiquetas más repetidas (de arriba abajo, en el orden del Excel):
  - 51 pasos (100 %): Plant → Material
- Ejemplo real (SIT-SCM-H-5.4.3-474_ALCANIZ_FLAVOUR):
```
Plant: M109
-----------------------
Material ZFIN: 543819
Material ZSEM: 543663
Material ZFOR: << pending >>
Material ZRAW: 101986
```
- **Debe salir:** _(pendiente)_

### 25. C223 — 49 pasos, 49 casos
- Descripción más habitual del paso: «Create a costing production version» (15); «Create a manufacturing production version» (15)
- Flujos: — 47, ZSPO 2
- Combinaciones de etiquetas más repetidas (de arriba abajo, en el orden del Excel):
  - 44 pasos (89 %): Plant → Material
  - 3 pasos (6 %): Material
  - 2 pasos (4 %): P.Org → C.Code → Plant → St.Loc → Doc Type → BP → Material
- Ejemplo real (SIT-SCM-H-5.1.1-227_KEBBI):
```
Plant: M024
-----------------------
Material: 518850, 518856, 518859
```
- **Debe salir:** _(pendiente)_
