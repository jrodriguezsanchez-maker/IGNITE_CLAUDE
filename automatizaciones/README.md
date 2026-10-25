# Automatizaciones

Iniciativa: automatización de pruebas sobre SAP S/4HANA 2025 vía SAP GUI.

Estructura: `automatizaciones/<stream>/flujos/<flujo>/`

- `SCM/` - stream de Supply Chain Management.
- Cada flujo contiene su definición (versionable) y carpetas `data/` y `results/`.

## COMPLIANCE (obligatorio)
Nunca se suben a GitHub: datos de prueba, resultados/logs (datos de cliente) ni datos
de conexión SAP GUI (sistema, mandante, usuario, contraseña). El `.gitignore` raíz lo
bloquea, pero antes de cada commit revisar `git status`.
