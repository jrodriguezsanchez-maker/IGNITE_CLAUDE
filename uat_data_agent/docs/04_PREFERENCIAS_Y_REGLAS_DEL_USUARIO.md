# Cómo quiere trabajar el usuario

Copia en el repositorio de lo aprendido en las sesiones (la memoria de Claude no se traslada entre cuentas). Idioma: **español**. Tono: directo; sin rodeos ni opciones que no se van a seguir.

## Forma de trabajar
- **Actuar, no preguntar.** Si hay una recomendación clara, aplicarla y contarlo. El usuario se ha quejado de perder tiempo («no me hagas perder tiempo», «poco usable»).
- **Proponer yo las mejoras de usabilidad.** Tras tocar una pantalla, revisar el flujo completo y listar/aplicar lo que sobra, se repite, está escondido u obliga a hacer scroll.
- **Uniformidad:** si algo se aplica a algunos pasos, aplicarlo a todos («ya que lo pones en algunos pasos, ponlo en todos»). No cambiar una pieza y dejar otra igual con otro comportamiento.
- **Honestidad con los datos:** no marcar nada como hecho/verde sin datos reales; decir qué se probó y qué no. No proponer algo que no existe; no afirmar «no existe» sin haber leído los datos.
- **No romper lo que ya está bien** (p. ej. casos de datos maestros PP 5.1.1, ya trabajados) y no perder los separadores del Data.
- **El usuario trabaja en SAP a la vez**: no lanzar cargas ni reiniciar SAP sin avisar; no reiniciar el servidor durante una lectura.
- No generar el Excel hasta que lo pida.
- No aprobar todo en bloque: «solo propones»; el usuario revisa antes («Antes reviso»).
- Si algo contradice lo que dice el usuario o el fichero, **avisar**.

## Estilo de pantalla
- Textos explicativos en iconos ⓘ (tooltip), no párrafos fijos.
- Estados con iconos y color: neutro = blanco, verde = sí, rojo = no; nunca palabras como «da igual».
- La descripción de un paso va en la misma línea que su transacción.
- Mostrar todo por defecto y dejar filtrar; no ocultar en silencio.
- Barra de herramientas compacta de una fila. Secciones secundarias **colapsadas** por defecto (chequeos, rationale, valores por defecto del caso).
- Filtros arriba, lista a la izquierda, acciones habituales siempre visibles.
- Si el caso ya trae planta, mostrarla como **confirmada** con su descripción (nombre, país, sociedad) y «cambiar».
- Una sección que no pertenece a ningún paso no tiene sentido: los datos van **por paso**, alineados con la fila del paso.

## Reglas de datos que ha dado (resumen; detalle en `02_REGLAS_DE_NEGOCIO.md`)
Etiquetas en inglés · defaults (almacén 1000, lote `<< get from the system >>`, BOM 1/6, ruta N/R, contador 01) · Prev.Data al final · Mov.Type con el bloque de tipo de documento · Production line en todo PP salvo datos maestros · Component en todo lo que fabrica o hace staging/consumo · una planta ⇒ origen = destino · el proveedor debe tener registro info con los materiales elegidos · selección por checkbox, solo lo marcado va a la propuesta.

## Pendientes que el usuario conoce y decidió aplazar
Grupo de compras real (P.Grp, «Más tarde») · registros info de ES01 · clientes KNVV (≈2 h de SAP) · regla de Mov.Type por paso (no la ha dado) · ejecución real de pasos en SAP («Ahora no»).

## Sobre el entorno
Windows 11 corporativo (Accenture), OneDrive sincroniza la carpeta del proyecto (cuidado con ficheros bloqueados), SAP GUI con scripting, usuario sin Node. La carpeta de trabajo de Claude es `CLAUDE - IGNITE` (contiene también `automatizaciones/` y `sit-reporter/`, otros proyectos del usuario).
