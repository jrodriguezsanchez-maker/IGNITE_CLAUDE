"""Prueba de conexión a SAP GUI. SOLO LECTURA: no envía teclas, no abre transacciones, no lee datos de negocio.

Se engancha a una sesión de SAP GUI ya abierta (el usuario se loguea a mano) y muestra:
  - si el scripting del cliente está activo,
  - versión de SAP GUI y del API de scripting,
  - por cada sesión: sistema (SID), mandante, idioma y si el scripting responde.
No imprime usuario, servidor/IP ni el contenido de ninguna pantalla.

Uso:  python sap_prueba_conexion.py
(no usar python -I: pywin32 se instaló en el entorno de usuario)
"""
import sys

try:
    import pythoncom
    import win32com.client
except ImportError:
    print("FALTA pywin32: python -m pip install --user pywin32")
    sys.exit(2)


def main():
    try:
        sapgui = win32com.client.GetObject("SAPGUI")
    except pythoncom.com_error as e:
        print("NO SE PUEDE ENGANCHAR a SAP GUI.")
        print("Causas habituales: SAP Logon cerrado, o scripting desactivado en el cliente")
        print("(SAP GUI > Opciones > Accesibilidad y scripting > Scripting > Activar scripting).")
        print("Detalle técnico: 0x%08X" % (e.hresult & 0xFFFFFFFF))
        return 1

    engine = sapgui.GetScriptingEngine
    print("Scripting del cliente: ACTIVO (el objeto SAPGUI responde)")
    for atr, etq in (("Version", "Versión API de scripting"), ("BuildNumber", "Build")):
        try:
            print("%s: %s" % (etq, getattr(engine, atr)))
        except Exception:
            pass

    conexiones = engine.Children
    print("Conexiones abiertas: %d" % conexiones.Count)
    if conexiones.Count == 0:
        print("No hay ninguna conexión: abre SAP Logon, entra al sistema de pruebas y vuelve a ejecutar.")
        return 0

    for i in range(conexiones.Count):
        con = conexiones.Item(i)
        sesiones = con.Children
        print("\nConexión %d: %d sesión(es)" % (i + 1, sesiones.Count))
        for j in range(sesiones.Count):
            ses = sesiones.Item(j)
            info = ses.Info
            try:
                ses.findById("wnd[0]")          # solo comprueba que el scripting responde en esa sesión
                scripting = "responde"
            except pythoncom.com_error:
                scripting = "NO responde (scripting desactivado en el servidor, o pantalla bloqueada)"
            print("  Sesión %d · sistema %s · mandante %s · idioma %s · scripting %s"
                  % (j + 1, info.SystemName, info.Client, info.Language, scripting))
    return 0


if __name__ == "__main__":
    sys.exit(main())
