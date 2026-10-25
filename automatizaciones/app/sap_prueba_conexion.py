"""Prueba de conexión a SAP GUI. SOLO LECTURA. Usa la lista de sistemas permitidos de conexion_local.json.

No toca las sesiones de ninguna conexión que no esté permitida (p. ej. producción): solo lee su nombre.
Uso:  python sap_prueba_conexion.py     (no usar python -I)
"""
import sys

import sap_backend

if __name__ == "__main__":
    r = sap_backend.estado()
    print(("OK: " if r["ok"] else "PROBLEMA: ") + r["mensaje"])
    sys.exit(0 if r["ok"] else 1)
