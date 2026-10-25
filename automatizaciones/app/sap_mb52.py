"""Lectura de stock con MB52 mediante SAP GUI Scripting. SOLO CONSULTA: no contabiliza nada.

Se engancha a una sesión abierta (el usuario se loguea a mano). Protecciones:
  - el sistema (SID) debe coincidir con el pedido; si no, se aborta,
  - solo actúa si la sesión está en la pantalla inicial y sin ventanas emergentes,
  - ante cualquier ventana emergente se aborta sin pulsar nada,
  - al terminar vuelve a la pantalla inicial.

Uso (prueba):  python sap_mb52.py <SID> <material> <centro> [almacen]
(no usar python -I: pywin32 está en el entorno de usuario)
"""
import sys
import time

try:
    import pythoncom
    import win32com.client
except ImportError:      # el servidor puede arrancar sin pywin32 (modo simulado)
    pythoncom = win32com = None


class SapError(ValueError):
    pass


def _attr(o, nombre, defecto=""):
    try:
        return getattr(o, nombre)
    except Exception:
        return defecto


def _engine():
    if win32com is None:
        raise SapError("Falta pywin32: python -m pip install --user pywin32")
    try:
        return win32com.client.GetObject("SAPGUI").GetScriptingEngine
    except pythoncom.com_error:
        raise SapError("No se puede enganchar a SAP GUI (¿SAP Logon cerrado o scripting desactivado?)")


def _sesiones(engine, sid):
    res = []
    for i in range(engine.Children.Count):
        con = engine.Children.Item(i)
        for j in range(con.Children.Count):
            s = con.Children.Item(j)
            if str(s.Info.SystemName).upper() == str(sid).upper():
                res.append((con, s))
    return res


def _libre(s):
    """Sesión libre: en la pantalla inicial y sin ventanas emergentes."""
    return str(s.Info.Transaction) == "SESSION_MANAGER" and s.Children.Count == 1


def _crear_sesion(con, base):
    """Abre una sesión nueva (otro 'modo') en la misma conexión y la devuelve."""
    antes = {con.Children.Item(k).Id for k in range(con.Children.Count)}
    base.CreateSession()
    t0 = time.time()
    while time.time() - t0 < 20:
        time.sleep(0.5)
        for k in range(con.Children.Count):
            n = con.Children.Item(k)
            if n.Id not in antes:
                t1 = time.time()
                while n.Busy and time.time() - t1 < 10:
                    time.sleep(0.2)
                return n
    raise SapError("SAP no abrió la sesión nueva a tiempo.")


def sesion(sid, crear=False):
    """Devuelve (sesion, creada). Usa una sesión LIBRE para no interrumpir el trabajo del usuario en otras.
    Si no hay ninguna libre y crear=True, abre una nueva (que luego hay que cerrar con cerrar_sesion)."""
    cands = _sesiones(_engine(), sid)
    if not cands:
        raise SapError("No hay ninguna sesión abierta en el sistema %s." % sid)
    for con, s in cands:
        if _libre(s):
            return s, False
    if not crear:
        raise SapError("Ninguna de las %d sesión(es) de %s está libre. Deja una en la pantalla inicial (SAP Easy Access), sin ventanas emergentes." % (len(cands), sid))
    for con, base in cands:
        if base.Children.Count > 1:
            continue                      # esa sesión tiene una ventana emergente
        try:
            return _crear_sesion(con, base), True
        except pythoncom.com_error:
            continue
    raise SapError("No hay sesión libre y no se pudo abrir una nueva (¿límite de sesiones o ventanas emergentes abiertas?). Cierra alguna sesión de SAP.")


def cerrar_sesion(ses):
    """Cierra una sesión que abrió el programa. Nunca se usa con sesiones del usuario."""
    try:
        ses.Parent.CloseSession(ses.Id)
    except Exception:
        pass


def estado(permitidos):
    """Diagnóstico de solo lectura: ¿hay conexión con un sistema permitido? No crea ni cierra sesiones."""
    if win32com is None:
        return {"ok": False, "mensaje": "Falta pywin32 (python -m pip install --user pywin32)."}
    try:
        engine = _engine()
    except SapError as e:
        return {"ok": False, "mensaje": str(e)}
    sistemas = {}
    for i in range(engine.Children.Count):
        con = engine.Children.Item(i)
        for j in range(con.Children.Count):
            s = con.Children.Item(j)
            clave = (str(s.Info.SystemName).upper(), str(s.Info.Client))
            d = sistemas.setdefault(clave, {"sesiones": 0, "libres": 0, "responde": None})
            d["sesiones"] += 1
            if _libre(s):
                d["libres"] += 1
                if d["responde"] is None:
                    try:
                        s.findById("wnd[0]")
                        d["responde"] = True
                    except pythoncom.com_error:
                        d["responde"] = False
    partes, ok = [], False
    for p in permitidos:
        d = sistemas.get((str(p["sid"]).upper(), str(p["mandante"])))
        if d:
            ok = True
            libre = "%d libre(s)" % d["libres"] if d["libres"] else "ninguna libre: se abrirá una nueva al lanzar"
            resp = "" if d["responde"] in (None, True) else " · el scripting NO responde (¿Basis?)"
            partes.append("%s/%s conectado · %d sesión(es), %s%s" % (p["sid"], p["mandante"], d["sesiones"], libre, resp))
            if d["responde"] is False:
                ok = False
        else:
            partes.append("%s/%s: no hay sesión abierta" % (p["sid"], p["mandante"]))
    otros = [k for k in sistemas if not any((str(p["sid"]).upper(), str(p["mandante"])) == k for p in permitidos)]
    if otros:
        partes.append("otros sistemas abiertos (se ignoran): " + ", ".join("%s/%s" % k for k in otros))
    return {"ok": ok, "mensaje": " · ".join(partes) or "SAP GUI abierto, sin conexiones."}


def _esperar(ses, segundos=60):
    t0 = time.time()
    while ses.Busy and time.time() - t0 < segundos:
        time.sleep(0.2)


def _buscar_grid(o):
    try:
        hijos = o.Children
        n = hijos.Count
    except Exception:
        return None
    for i in range(n):
        h = hijos.Item(i)
        if _attr(h, "Type") == "GuiShell" and _attr(h, "SubType") == "GridView":
            return h
        r = _buscar_grid(h)
        if r is not None:
            return r
    return None


def consultar(ses, material, centro, almacen="", lotes=True, especiales=False, max_filas=500):
    """Devuelve {"mensaje", "columnas": [(nombre, titulo)], "filas": [dict]}."""
    if str(ses.Info.Transaction) != "SESSION_MANAGER":
        raise SapError("La sesión no está en la pantalla inicial (transacción %s): no se interrumpe tu trabajo." % ses.Info.Transaction)
    if ses.Children.Count > 1:
        raise SapError("Hay una ventana emergente abierta en SAP.")

    def ir(cmd):
        ses.findById("wnd[0]/tbar[0]/okcd").text = cmd
        ses.findById("wnd[0]").sendVKey(0)
        _esperar(ses)

    ir("/nMB52")
    try:
        if ses.Children.Count > 1:
            raise SapError("Ventana emergente al abrir MB52 (no se pulsa nada).")
        usr = "wnd[0]/usr/"
        ses.findById(usr + "ctxtMATNR-LOW").text = str(material)
        ses.findById(usr + "ctxtWERKS-LOW").text = str(centro)
        ses.findById(usr + "ctxtLGORT-LOW").text = str(almacen)
        ses.findById(usr + "chkXMCHB").selected = bool(lotes)         # una línea por lote
        ses.findById(usr + "chkPA_SOND").selected = bool(especiales)  # sin stocks especiales
        ses.findById(usr + "chkNOZERO").selected = True               # sin líneas de stock cero
        ses.findById("wnd[0]/tbar[1]/btn[8]").press()                 # ejecutar
        _esperar(ses)
        if ses.Children.Count > 1:
            popup = ses.findById("wnd[1]")
            raise SapError("Ventana emergente tras ejecutar: %s" % str(_attr(popup, "Text")).strip())
        sbar = ses.findById("wnd[0]/sbar")
        mensaje = "%s (%s)" % (str(sbar.Text).strip(), sbar.MessageType)
        grid = _buscar_grid(ses.findById("wnd[0]/usr"))
        if grid is None:
            return {"mensaje": mensaje, "columnas": [], "filas": [], "pantalla": str(ses.findById("wnd[0]").Text).strip()}
        cols = []
        for k in range(grid.ColumnOrder.Count):
            nombre = grid.ColumnOrder.Item(k)
            try:
                titulo = " ".join(str(t) for t in grid.GetColumnTitles(nombre)) or nombre
            except Exception:
                titulo = nombre
            cols.append((nombre, titulo))
        filas = []
        for r in range(min(grid.RowCount, max_filas)):
            filas.append({n: grid.GetCellValue(r, n) for n, _ in cols})
        return {"mensaje": mensaje, "columnas": cols, "filas": filas, "total_filas": grid.RowCount, "grid": _attr(grid, "Id")}
    finally:
        try:
            ir("/n")
        except Exception:
            pass


def main():
    if len(sys.argv) not in (4, 5):
        print(__doc__)
        return 2
    sid, material, centro = sys.argv[1], sys.argv[2], sys.argv[3]
    almacen = sys.argv[4] if len(sys.argv) == 5 else ""
    try:
        ses, creada = sesion(sid, crear=True)
        try:
            r = consultar(ses, material, centro, almacen)
        finally:
            if creada:
                cerrar_sesion(ses)
    except SapError as e:
        print("ABORTADO:", e)
        return 1
    print("Mensaje de la barra de estado:", r["mensaje"])
    if r.get("grid"):
        print("Identificador de la tabla:", r["grid"])
    print("Columnas (%d):" % len(r["columnas"]))
    for n, t in r["columnas"]:
        print("  %-14s %s" % (n, t))
    print("Filas: %s (se muestran %d)" % (r.get("total_filas", 0), len(r["filas"])))
    for f in r["filas"]:
        print("  " + " | ".join("%s=%s" % (n, str(v).strip()) for n, v in f.items() if str(v).strip()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
