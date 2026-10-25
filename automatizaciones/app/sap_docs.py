"""Lectura (SOLO LECTURA) de un documento de material y de sus documentos contables, igual que lo haría una persona en MIGO:
acción «Display» + referencia «Material Document» + nº de documento y ejercicio → pestaña «Doc. info» → botón «FI Documents».

La ventana «List of Documents in Accounting» enseña, en una sola lista, los documentos de contabilidad (FI), de Controlling (CO) y del
Material Ledger (ML) generados por el movimiento. Si el movimiento no genera apuntes, la lista sale vacía (p. ej. un traspaso 344).

No teclea nada salvo el nº de documento y el ejercicio; no contabiliza ni modifica nada; al terminar sale de MIGO con /n.
"""
import time

import sap_mb52
import sap_migo
from sap_migo import _attr, _buscar, _esperar, _texto_ventana

CONTENEDORES = sap_migo.CONTENEDORES


def _por_texto(raiz, tipo, texto):
    """Primer control del tipo indicado cuyo Text o Tooltip contiene el texto."""
    try:
        hs = raiz.Children
        for i in range(hs.Count):
            h = hs.Item(i)
            if _attr(h, "Type") == tipo and texto.lower() in (str(_attr(h, "Text")) + " " + str(_attr(h, "Tooltip"))).lower():
                return h
            if _attr(h, "Type") in CONTENEDORES or _attr(h, "ContainerType", False):
                r = _por_texto(h, tipo, texto)
                if r is not None:
                    return r
    except Exception:
        pass
    return None


def _clasificar(tipo):
    t = tipo.lower()
    if "controlling" in t:
        return "CO"
    if "material ledger" in t:
        return "ML"
    if "accounting" in t:
        return "FI"
    return "OTRO"


def _estructura(ventana, maximo=60):
    """Descripción de los controles de una ventana (para entender listas que aún no conocemos)."""
    res = []

    def rec(o, n=0):
        try:
            for i in range(o.Children.Count):
                if len(res) >= maximo:
                    return
                h = o.Children.Item(i)
                t = _attr(h, "Type")
                txt = ""
                try:
                    txt = str(h.Text).strip()[:40]
                except Exception:
                    pass
                res.append("%s%s %s %r" % ("  " * n, t, str(_attr(h, "Id")).split("/")[-1], txt))
                rec(h, n + 1)
        except Exception:
            pass
    rec(ventana)
    return res


def leer_documento(ses, matdoc, anio, depurar=False):
    """Devuelve {"documento", "ejercicio", "contables": [{documento, tipo, categoria, sociedad}], "items": [...], "avisos": [...]}."""
    if str(ses.Info.Transaction) != "SESSION_MANAGER" or ses.Children.Count > 1:
        raise sap_migo.MigoError("La sesión no está libre (pantalla inicial, sin ventanas emergentes).")
    out = {"documento": str(matdoc), "ejercicio": str(anio), "contables": [], "items": [], "avisos": [], "estructura_lista": []}

    def ir(cmd):
        ses.findById("wnd[0]/tbar[0]/okcd").text = cmd
        ses.findById("wnd[0]").sendVKey(0)
        _esperar(ses)

    def sin_popup(donde):
        if ses.Children.Count > 1:
            raise sap_migo.MigoError("Ventana emergente inesperada %s: %s" % (donde, _texto_ventana(ses)))

    usr = lambda: ses.findById("wnd[0]/usr")
    ir("/nMIGO")
    try:
        sin_popup("al abrir MIGO")
        for sufijo, texto in (("GODYNPRO-ACTION", "Display"), ("GODYNPRO-REFDOC", "Material Document")):
            c = _buscar(usr(), "GuiComboBox", sufijo)
            if c is None:
                raise sap_migo.MigoError("No encuentro el desplegable %s." % sufijo)
            for k in range(c.Entries.Count):
                if str(c.Entries.Item(k).Value).strip().lower() == texto.lower():
                    c.key = c.Entries.Item(k).Key
                    _esperar(ses, 30)
                    break
            sin_popup("al elegir " + texto)
        d = _buscar(usr(), "GuiTextField", "GODYNPRO-MAT_DOC") or _buscar(usr(), "GuiCTextField", "GODYNPRO-MAT_DOC")
        y = _buscar(usr(), "GuiTextField", "GODYNPRO-DOC_YEAR") or _buscar(usr(), "GuiCTextField", "GODYNPRO-DOC_YEAR")
        if d is None or y is None:
            raise sap_migo.MigoError("No encuentro los campos de documento y ejercicio de MIGO.")
        d.text, y.text = str(matdoc), str(anio)
        ses.findById("wnd[0]").sendVKey(0)
        _esperar(ses)
        sin_popup("al mostrar el documento")
        sb = ses.findById("wnd[0]/sbar")
        if str(sb.MessageType) in ("E", "A"):
            raise sap_migo.MigoError("MIGO no muestra el documento: " + str(sb.Text).strip())

        # posiciones del documento (tabla de la parte inferior)
        for fila in range(0, 30):
            vals = {}
            for col_nombre in ("GOITEM-MAKTX", "GOITEM-ERFMG", "GOITEM-ERFME", "GOITEM-LGOBE", "GOITEM-BWART", "GOITEM-CHARG", "GOITEM-NAME1"):
                for tipo in ("GuiCTextField", "GuiTextField"):
                    c = None
                    try:
                        c = _buscar(usr(), tipo, "%s[%d,%d]" % (col_nombre, 0, fila))
                    except Exception:
                        c = None
                    if c is not None:
                        break
                if c is not None:
                    vals[col_nombre] = str(c.Text).strip()
            if not vals:
                break
        # (las celdas de la tabla dependen del diseño del usuario: la lista de posiciones se completa en una iteración posterior)

        # pestaña «Doc. info» y botón «FI Documents»
        tab = _buscar(usr(), "GuiTab", "tabpOK_GOHEAD_CREATEDBY")
        if tab is not None:
            tab.select()
            _esperar(ses, 20)
        if depurar:
            def listar(o, acc, n=0):
                if n > 12:
                    return
                try:
                    t = str(o.Type)
                    if t in ("GuiButton", "GuiTab", "GuiToolbarControl"):
                        acc.append("%s %s '%s' tip='%s'" % (t, o.Id.split("/", 3)[-1], str(_attr(o, "Text")).strip(), str(_attr(o, "Tooltip")).strip()))
                    for i in range(o.Children.Count):
                        listar(o.Children.Item(i), acc, n + 1)
                except Exception:
                    pass
            acc = []
            listar(ses.findById("wnd[0]"), acc)
            out["botones"] = acc
            out["barra_estado"] = str(ses.findById("wnd[0]/sbar").Text).strip()
        boton = _por_texto(usr(), "GuiButton", "FI Documents")
        if boton is None:
            out["avisos"].append("No hay botón «FI Documents»: el documento no tiene documentos contables asociados.")
            return out
        boton.press()
        _esperar(ses, 30)
        if ses.Children.Count < 2:
            msg = str(ses.findById("wnd[0]/sbar").Text).strip()
            out["tras_boton"] = {"barra_estado": msg, "transaccion": str(ses.Info.Transaction), "titulo": str(ses.findById("wnd[0]").Text).strip()}
            if "no subsequent document" in msg.lower():
                out["sin_contabilidad"] = True
                out["avisos"].append("Este documento no genera documentos contables (FI, CO ni ML). SAP: %r" % msg)
            else:
                out["avisos"].append("«FI Documents» no abrió ventana. Mensaje de SAP: %r" % (msg or "(ninguno)"))
            return out
        w = ses.findById("wnd[1]")
        titulo = str(_attr(w, "Text")).strip()
        out["ventana"] = titulo
        out["estructura_lista"] = _estructura(w) if depurar else []
        filas = []
        # lista como tabla ALV (GridView) o como tabla de etiquetas
        grid = None

        def buscar_grid(o):
            nonlocal grid
            try:
                for i in range(o.Children.Count):
                    h = o.Children.Item(i)
                    if _attr(h, "Type") == "GuiShell" and _attr(h, "SubType") == "GridView" and grid is None:
                        grid = h
                    buscar_grid(h)
            except Exception:
                pass
        buscar_grid(w)
        if grid is not None:
            cols = [grid.ColumnOrder.Item(k) for k in range(grid.ColumnOrder.Count)]
            for r in range(grid.RowCount):
                filas.append([str(grid.GetCellValue(r, c)).strip() for c in cols])
        else:
            etiquetas = []

            def recoger(o):
                try:
                    for i in range(o.Children.Count):
                        h = o.Children.Item(i)
                        if _attr(h, "Type") == "GuiLabel" and str(_attr(h, "Text")).strip():
                            etiquetas.append((str(_attr(h, "Id")), str(h.Text).strip()))
                        recoger(h)
                except Exception:
                    pass
            recoger(w)
            # las celdas de una tabla de etiquetas se llaman lbl[columna,fila]
            import re
            tabla = {}
            for ident, txt in etiquetas:
                m = re.search(r"\[(\d+),(\d+)\]$", ident)
                if m:
                    tabla.setdefault(int(m.group(2)), {})[int(m.group(1))] = txt
            for f in sorted(tabla):
                filas.append([tabla[f][c] for c in sorted(tabla[f])])
        out["filas_crudas"] = filas
        for f in filas:
            vals = [x for x in f if x]
            if len(vals) >= 2 and vals[0].lower() not in ("document",):
                tipo = vals[1]
                out["contables"].append({"documento": vals[0], "tipo": tipo, "categoria": _clasificar(tipo), "sociedad": vals[2] if len(vals) > 2 else ""})
        return out
    finally:
        try:
            while ses.Children.Count > 1:                       # cerrar la lista de documentos contables (solo lectura)
                try:
                    ses.findById("wnd[%d]/tbar[0]/btn[12]" % (ses.Children.Count - 1)).press()
                except Exception:
                    try:
                        ses.findById("wnd[%d]" % (ses.Children.Count - 1)).close()
                    except Exception:
                        break
                _esperar(ses)
            ir("/n")
            if ses.Children.Count > 1:
                titulo = str(_attr(ses.findById("wnd[1]"), "Text")).lower()
                if any(x in titulo for x in ("exit", "salir", "data will be lost", "datos")):
                    ses.findById("wnd[1]/usr/btnSPOP-OPTION1").press()
                    _esperar(ses)
        except Exception:
            pass
