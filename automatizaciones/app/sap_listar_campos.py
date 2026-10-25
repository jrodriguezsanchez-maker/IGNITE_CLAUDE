"""Lista los identificadores de los campos de la pantalla de selección de una transacción de CONSULTA de SAP GUI.

SOLO LECTURA de la estructura de la pantalla: abre la transacción (navegación), NO ejecuta la consulta, NO escribe en
ningún campo y NO imprime el contenido de los campos de entrada. Al terminar vuelve a la pantalla inicial.

Protecciones:
  - el sistema (SID) se pasa como argumento y debe coincidir con el de la sesión (si no, se aborta);
  - solo se abren transacciones de consulta de una lista cerrada;
  - solo se actúa si la sesión está en la pantalla inicial (no interrumpe trabajo en curso);
  - si aparece una ventana emergente, se aborta sin pulsar nada.

Uso:  python sap_listar_campos.py <SID> <TRANSACCION>      p. ej.  python sap_listar_campos.py QS4 MB52
(no usar python -I: pywin32 está en el entorno de usuario)
"""
import sys

try:
    import pythoncom
    import win32com.client
except ImportError:
    print("FALTA pywin32: python -m pip install --user pywin32")
    sys.exit(2)

SOLO_CONSULTA = {"MB52", "MMBE", "MB51", "LS24", "ME13", "ME23N", "ME2N", "CKM3N", "FB03", "KE24"}
CONTENEDORES = ("GuiUserArea", "GuiSimpleContainer", "GuiContainerShell", "GuiTab", "GuiTabStrip", "GuiScrollContainer", "GuiCustomControl",
                "GuiSplitterContainer", "GuiMainWindow", "GuiTitlebar", "GuiStatusbar")


def attr(o, nombre, defecto=""):
    try:
        return getattr(o, nombre)
    except Exception:
        return defecto


def recorrer(o, nivel, salida, maximo=400):
    try:
        hijos = o.Children
        n = hijos.Count
    except Exception:
        return
    for i in range(n):
        if len(salida) >= maximo:
            return
        h = hijos.Item(i)
        tipo = attr(h, "Type")
        ident = attr(h, "Id").split("/usr/")[-1] if "/usr/" in attr(h, "Id") else attr(h, "Id")
        if tipo == "GuiLabel":
            txt = str(attr(h, "Text")).strip()
            if txt:
                salida.append("%sEtiqueta %s: %s" % ("  " * nivel, ident, txt))
        elif tipo in ("GuiTextField", "GuiCTextField", "GuiPasswordField"):
            # solo estructura: nunca el contenido del campo
            salida.append("%sCampo   %s  [%s, longitud %s, %s%s]" % ("  " * nivel, ident, tipo, attr(h, "MaxLength"),
                          "editable" if attr(h, "Changeable", True) else "solo lectura", ", obligatorio" if attr(h, "Required", False) else ""))
        elif tipo in ("GuiCheckBox", "GuiRadioButton"):
            salida.append("%s%s %s: %s  (marcado: %s)" % ("  " * nivel, "Casilla" if tipo == "GuiCheckBox" else "Opción ", ident, str(attr(h, "Text")).strip(), attr(h, "Selected")))
        elif tipo in ("GuiButton", "GuiTab"):
            salida.append("%s%s %s: %s" % ("  " * nivel, "Botón  " if tipo == "GuiButton" else "Pestaña", ident, str(attr(h, "Text") or attr(h, "Tooltip")).strip()))
        elif tipo not in CONTENEDORES:
            salida.append("%s%s %s" % ("  " * nivel, tipo, ident))
        if tipo in CONTENEDORES or attr(h, "ContainerType", False):
            recorrer(h, nivel + 1, salida, maximo)


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    sid, trx = sys.argv[1].upper(), sys.argv[2].upper()
    if trx not in SOLO_CONSULTA:
        print("Transacción %s no permitida en este script (solo consulta: %s)" % (trx, ", ".join(sorted(SOLO_CONSULTA))))
        return 2
    try:
        engine = win32com.client.GetObject("SAPGUI").GetScriptingEngine
    except pythoncom.com_error:
        print("No se puede enganchar a SAP GUI (¿SAP Logon cerrado o scripting desactivado?)")
        return 1
    ses = None
    for i in range(engine.Children.Count):
        con = engine.Children.Item(i)
        if sid.lower() not in str(attr(con, "Description")).lower():
            continue                       # otras conexiones (p. ej. producción): no se tocan
        for j in range(con.Children.Count):
            s = con.Children.Item(j)
            if str(s.Info.SystemName).upper() == sid:
                ses = s
    if ses is None:
        print("No hay ninguna sesión abierta en el sistema %s. No se hace nada." % sid)
        return 1
    actual = str(ses.Info.Transaction)
    if actual != "SESSION_MANAGER":
        print("La sesión no está en la pantalla inicial (transacción actual: %s). Para no interrumpir tu trabajo, no hago nada." % actual)
        return 1
    if ses.Children.Count > 1:
        print("Hay una ventana emergente abierta en SAP. No hago nada.")
        return 1

    def ir(cmd):
        ses.findById("wnd[0]/tbar[0]/okcd").text = cmd
        ses.findById("wnd[0]").sendVKey(0)

    ir("/n" + trx)
    try:
        if ses.Children.Count > 1:
            print("Aparece una ventana emergente al abrir %s. La dejo como está y no pulso nada." % trx)
            return 1
        print("Pantalla: %s  (transacción %s)" % (str(ses.findById("wnd[0]").Text).strip(), ses.Info.Transaction))
        salida = []
        recorrer(ses.findById("wnd[0]/usr"), 0, salida)
        print("Elementos de la pantalla de selección (%d):" % len(salida))
        print("\n".join(salida))
        print("\nBarra de herramientas de aplicación:")
        try:
            tb = ses.findById("wnd[0]/tbar[1]")
            for i in range(tb.Children.Count):
                b = tb.Children.Item(i)
                t = str(attr(b, "Tooltip") or attr(b, "Text")).strip()
                if t:
                    print("  %s: %s" % (attr(b, "Id").split("wnd[0]/")[-1], t))
        except Exception:
            pass
    finally:
        ir("/n")   # vuelve a la pantalla inicial
    return 0


if __name__ == "__main__":
    sys.exit(main())
