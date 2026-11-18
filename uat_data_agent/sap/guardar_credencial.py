"""Guarda (o cambia) usuario y contraseña de QS4 en el Administrador de credenciales de Windows.
Se ejecuta a mano: la contraseña se teclea aquí, oculta, y no pasa por el front ni por Claude.
Uso:  python sap/guardar_credencial.py            (guardar / cambiar)
      python sap/guardar_credencial.py --borrar   (eliminar)"""
import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import credencial  # noqa: E402

if "--borrar" in sys.argv:
    credencial.borrar()
    print("Credencial eliminada.")
    sys.exit(0)

actual = credencial.hay()
print("Credencial de QS4 (queda cifrada en el Administrador de credenciales de Windows).")
if actual:
    print(f"Ahora hay guardado el usuario: {actual}  (Enter en usuario = mantenerlo)")
u = input("Usuario SAP: ").strip() or (actual or "")
if not u:
    sys.exit("Falta el usuario.")
p = getpass.getpass("Contraseña (no se ve al escribir): ")
if not p:
    sys.exit("Contraseña vacía; no se guarda nada.")
credencial.guardar(u, p)
print(f"Guardado para {u}. Para cambiarla cuando caduque, vuelve a ejecutar este fichero.")
