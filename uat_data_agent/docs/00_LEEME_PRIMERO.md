# uat_data_agent — léeme primero

Documento de entrada para quien retome el proyecto (persona o un Claude nuevo, p. ej. tras migrar de cuenta). Las notas de memoria de Claude **no viajan** con el usuario: todo lo que importa está aquí y en `docs/`.

## Qué es y para qué sirve
Herramienta local (Python + HTML) para el programa iGnite S/4HANA · SCM HUMAN. El fichero UAT tiene **2472 casos y ~7079 pasos**. Cada paso tiene un campo **Data** (texto con organización, tipo de documento y datos transaccionales). El usuario tiene que **validar unos 2500 casos** y proponer para cada uno **datos de prueba válidos y exclusivos del caso** (planta, material, proveedor, componentes, línea de producción…), comprobados contra QS4 (SAP calidad), y dejarlos escritos en el Excel (columnas AG–AL de una **copia**).

La herramienta lee tablas de QS4 por SE16N (solo lectura), propone datos por caso y paso, deja que el usuario los ajuste en un front web y guarda sus decisiones. **El Excel solo se genera cuando el usuario lo pide** («no generes excel, tengo que trabajar muchos casos antes de tener el excel»).

## Cómo se usa (resumen)
1. El usuario arranca `iniciar_uat.bat` (abre `http://localhost:8766`; la ventana negra debe seguir abierta).
2. Elige un caso en la lista (filtros arriba: texto, tipo, estados, L2, L3, flujo, planta).
3. El caso se abre en 3 pasos: **plantas** (se muestran ya confirmadas si el caso trae planta; «cambiar» reabre) · **elige los datos** (listas con checkbox de materiales/proveedores/componentes) · **revisa y guarda** (una fila por paso: formulario del paso | Data original del Excel | propuesta editable).
4. Arriba del caso: tarjeta con «Buscamos…» y **Rationale** (por qué se propone cada cosa; colapsado por defecto).
5. Guardar escribe en `data/ledger/asignaciones.json`. Estados: Propuesto · Original OK · No requiere · Revisar a mano · Sin candidato · Validado · En curso.

## Reglas que no se pueden saltar
- **SAP solo lectura** (CLAUDE.md regla 1). Whitelist de transacciones: SE16N. La ejecución real de pasos en SAP se discutió y el usuario dijo «Ahora no».
- **Nunca modificar el Excel UAT original** ni guardarlo con openpyxl (rompe fórmulas de matriz de la hoja oculta `AUX_parse`). Se escribe por XML solo `sheet2.xml` y `table2.xml` (`engine/patch_xlsx.py`).
- No dar nada por «hecho/verde» sin datos reales; decir siempre qué se probó de verdad y qué no.
- El usuario **trabaja en SAP a la vez**: no lanzar lecturas largas de SAP sin avisar (la «autocuración» mata y relanza saplogon). Antes de reiniciar el servidor comprobar que `/api/qs4/status` no dice `consultando`.
- El usuario no quiere descubrir las mejoras de usabilidad uno a uno: proponerlas/aplicarlas (ver `04_PREFERENCIAS_Y_REGLAS_DEL_USUARIO.md`).

## Mapa de la documentación
| Fichero | Contenido |
|---|---|
| `01_ARQUITECTURA.md` | módulos, flujo de datos, API, ficheros de datos |
| `02_REGLAS_DE_NEGOCIO.md` | formato de Data, defaults, reglas por flujo y familia, Prev.Data, modelo de transacciones |
| `03_OPERACION.md` | arrancar/reiniciar, lecturas de SAP, colas, problemas conocidos y cómo se resolvieron |
| `04_PREFERENCIAS_Y_REGLAS_DEL_USUARIO.md` | cómo quiere trabajar el usuario (copia de las notas de memoria) |
| `05_ESTADO_Y_PENDIENTES.md` | qué está hecho, qué se probó, qué falta |
| `../CLAUDE.md` | reglas no negociables y reglas de negocio base (se carga solo en cada sesión) |
| `../TRANSACCIONES_DATA.md`, `../LOG_FAMILIAS.md`, `../QM_FAMILIAS.md`, `../PP_FAMILIAS.md` | análisis por transacción y por familia de caso |
| `../PLAN.md`, `../README.md`, `../PROMPT_INICIAL.md` | **históricos** (plan por fases de noviembre; parcialmente desfasados) |

## Cuidado con un detalle de despliegue
`front/static/*` (JS/HTML) se sirve **sin caché**: los cambios aparecen al recargar (Ctrl+F5). Los cambios en Python **requieren reiniciar** el servidor. Esa diferencia ya rompió la pantalla del usuario dos veces: tras tocar Python, reinicia siempre y avisa.
