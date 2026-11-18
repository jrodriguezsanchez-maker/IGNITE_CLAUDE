# Estado y pendientes (a 18/11/2026)

> `PLAN.md` es el plan por fases de principios de noviembre y está desfasado; este documento manda.
> Criterio de honestidad: «probado» = visto con datos reales de QS4/ECC en la herramienta. **Nada se ha contrastado en SAP con ejecución de pasos.**

## Hecho
| Área | Estado |
|---|---|
| Lectura de QS4 por SE16N (solo lectura) | Tablas de PP, QM, LOG y WM cargadas para las plantas del proyecto (ver `data/raw`). EINA/EINE por planta y por org. de compras: hechas salvo ES01 |
| Front de casos | Lista + filtros (estados con multiselección y contadores en cascada), caso en 3 pasos, rationale arriba (colapsado), chequeos colapsados, ficha del caso |
| Formulario **por paso** | Cada paso (todos, incluidos los fuera del libro y los `Prev.Data`) tiene su formulario con «＋ añadir campo», «⇉ aplicar a todos» y «✕ quitar»; fila = formulario \| Data original \| propuesta editable |
| Modelo de transacciones | `config/transacciones_modelo.xlsx` (86 filas rellenadas por el usuario) interpretado por `engine/modelo_tx.py` |
| Propuesta en bloque | PP, QM y LOG (LOG/QM rehechas tras las reglas del usuario; revisadas por el usuario antes de aprobar) |
| LOG | Flujos ZTRA/ZWIA/ZINT/ZINR/ZPO/ZSPO/ZSPA/ZSER/venta, tramos, ECC como antecedente, registro info por proveedor |
| QM | Tipos de inspección por familia (`ZQMPP*`, `ZQMEM*`), reemplazo del mismo tipo, 3 reglas confirmadas |
| PP | Material/BOM/ruta/versión/cost collector/puesto de trabajo derivados; Production line y Component por defecto según `02_REGLAS_DE_NEGOCIO.md` |
| Excel AG–AL | Generado y verificado una vez con las 9 primeras plantas PP (en `out/`); **regenerar solo a petición** |
| Robustez | Grabación del ledger con reintentos (OneDrive); recuperación automática de SAP; login de un solo intento |

## Última sesión (15–18/11)
- Formulario por paso uniforme (también `Prev.Data`) · plantas confirmadas automáticamente con descripción · Production line y Component por defecto · lista de materiales filtrada por el proveedor del caso · arreglo de errores al grabar.
- **No verificado en pantalla**: el formulario de los pasos `Prev.Data` (el script de comprobación por API se colgó y se cortó), el resumen de plantas con la descripción y la confirmación automática (solo comprobados por datos de API/estáticos). Comprobar con Ctrl+F5 y un caso con `Prev.Data`.

## Pendiente
1. **Verificación visual** de lo no verificado arriba.
2. **Mov.Type por paso**: el usuario aún no ha dado la regla (se trata como el tipo de documento: va en el bloque 2).
3. **P.Grp real**: leer MARC-EKGRP (~45 min de SAP; el usuario dijo «más tarde»).
4. **Registros info ES01** (org. de compras): pendiente de cargar.
5. **Clientes KNVV** para ventas (26 orgs ≈ 2 h): hoy las notas dicen «Cliente sin verificar».
6. **QM**: 189 casos «Sin candidato» por exigir mismo tipo de material.
7. **Cómo valida el usuario los registros info con calidad**: pregunta sin respuesta.
8. Revisar la fila de **MIGO** del libro (afecta a todos los pasos MIGO).
9. Pendientes históricos de `PLAN.md`: PM (8) y WM (9) por familias, subcontratación, RF, modelo dedicado dentro de cadenas, pruebas con datos simulados.
10. Generar el Excel final cuando el usuario lo pida: propuesta en bloque con todas las plantas → `engine/patch_xlsx.py` → comprobar que A:AF no cambia.

## Hallazgos conocidos que NO se corrigen salvo petición (de `CLAUDE.md`)
169 casos de transporte con prefijo distinto entre hojas · 590 IDs duplicados en UAT_cases · 2 casos sin pasos y 2 grupos de pasos sin caso.

## Cómo seguir en una sesión nueva (sugerencia)
1. Leer `docs/00_LEEME_PRIMERO.md` y `CLAUDE.md`.
2. Arrancar con `iniciar_uat.bat`, abrir un caso de cada stream y comprobar que la pantalla carga.
3. Preguntar al usuario qué casos está validando y qué ha visto mal; tratar cada queja con la regla de uniformidad.
