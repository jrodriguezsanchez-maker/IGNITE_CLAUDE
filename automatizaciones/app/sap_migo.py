"""MIGO real por SAP GUI Scripting: traspasos (acción «Transfer Posting», referencia «Other»), p. ej. 344/343.

MODOS
  "comprobar"    : rellena la MIGO y pulsa «Check». NO contabiliza. Después descarta los datos y sale de MIGO.
  "contabilizar" : igual y, si el Check es correcto, pulsa «Post» y lee el número de documento de material.

CANDADOS (todos obligatorios para contabilizar)
  1. Solo movimientos de la lista MOVIMIENTOS_PERMITIDOS.
  2. La cantidad no puede superar MAX_CANTIDAD y la sesión debe ser del sistema y mandante permitidos de conexion_local.json.
  3. Hace falta pasar «huella»: un código calculado a partir de los datos exactos (movimiento, material, centro, almacén, lote, cantidad).
     La pantalla se la enseña al usuario con los datos y solo si él confirma se reenvía; si cambia cualquier dato, la huella ya no vale.

Siempre: una sesión libre (o nueva, que se cierra), nunca la del usuario con trabajo en curso. Cualquier ventana emergente inesperada aborta
sin pulsar nada. No se usa python -I.
"""
import hashlib
import time

import sap_mb52

MOVIMIENTOS_PERMITIDOS = {"311", "343", "344"}   # contabilización real: se amplía tras validar cada tipo con el Check (311 validado: 0 errores)
MOVIMIENTOS_COMPROBAR = {"311", "321", "322", "343", "344"}   # el Check (sin contabilizar) sí puede probarlos para validar la pantalla
CON_DESTINO = {"311"}                         # movimientos que necesitan almacén de destino
MAX_CANTIDAD = 100000
CONTENEDORES = ("GuiUserArea", "GuiSimpleContainer", "GuiContainerShell", "GuiTab", "GuiTabStrip", "GuiScrollContainer", "GuiCustomControl",
                "GuiSplitterContainer", "GuiMainWindow", "GuiGOS", "GuiTableControl")


class MigoError(sap_mb52.SapError):
    pass


def huella(mov, material, centro, almacen, lote, cantidad, motivo="", almacen_destino=""):
    """Código que identifica los datos exactos. Cambia si cambia cualquiera de ellos."""
    txt = "|".join(str(x).strip().upper() for x in (mov, material, centro, almacen, lote, cantidad, motivo))
    if almacen_destino:
        txt += "|" + str(almacen_destino).strip().upper()
    return hashlib.sha256(txt.encode("utf-8")).hexdigest()[:8].upper()


def _attr(o, n, d=""):
    try:
        return getattr(o, n)
    except Exception:
        return d


def _buscar(raiz, tipo, sufijo):
    """Primer control de ese tipo cuyo Id termina en el sufijo (se busca por nombre: los Id de MIGO cambian de número de pantalla)."""
    try:
        hs = raiz.Children
        for i in range(hs.Count):
            h = hs.Item(i)
            if _attr(h, "Type") == tipo and str(_attr(h, "Id")).endswith(sufijo):
                return h
            if _attr(h, "Type") in CONTENEDORES or _attr(h, "ContainerType", False):
                r = _buscar(h, tipo, sufijo)
                if r is not None:
                    return r
    except Exception:
        pass
    return None


def _editables(raiz, maximo=40):
    """Ids cortos de los campos editables visibles (para explicar un fallo sin adivinar)."""
    res = []

    def rec(o):
        try:
            hs = o.Children
            for i in range(hs.Count):
                if len(res) >= maximo:
                    return
                h = hs.Item(i)
                t = _attr(h, "Type")
                if t in ("GuiTextField", "GuiCTextField") and _attr(h, "Changeable", True):
                    res.append(str(_attr(h, "Id")).split("/")[-1])
                if t in CONTENEDORES or _attr(h, "ContainerType", False):
                    rec(h)
        except Exception:
            pass
    rec(raiz)
    return ", ".join(res)


def _boton_barra(ses, textos):
    for barra in ("wnd[0]/tbar[1]", "wnd[0]/tbar[0]"):
        try:
            tb = ses.findById(barra)
            for i in range(tb.Children.Count):
                b = tb.Children.Item(i)
                t = (str(_attr(b, "Tooltip")) + " " + str(_attr(b, "Text"))).lower()
                if any(x in t for x in textos):
                    return b
        except Exception:
            continue
    return None


def _texto_ventana(ses, nivel=1, max_filas=25):
    """Lee (sin pulsar nada) el contenido de la ventana emergente: etiquetas, tablas ALV y botones disponibles."""
    try:
        w = ses.findById("wnd[%d]" % nivel)
    except Exception:
        return "(no se pudo leer la ventana)"
    partes = ["título «%s»" % str(_attr(w, "Text")).strip()]

    def rec(o):
        try:
            hs = o.Children
            for i in range(hs.Count):
                h = hs.Item(i)
                t = _attr(h, "Type")
                if t == "GuiLabel" and str(_attr(h, "Text")).strip():
                    partes.append("texto: " + str(_attr(h, "Text")).strip())
                elif t == "GuiShell" and _attr(h, "SubType") == "GridView":
                    cols = [h.ColumnOrder.Item(k) for k in range(h.ColumnOrder.Count)]
                    for r in range(min(h.RowCount, max_filas)):
                        partes.append("fila %d: " % r + " | ".join(str(h.GetCellValue(r, c)).strip() for c in cols if str(h.GetCellValue(r, c)).strip()))
                elif t == "GuiButton" and (str(_attr(h, "Text")).strip() or str(_attr(h, "Tooltip")).strip()):
                    partes.append("botón %s: %s" % (str(_attr(h, "Id")).split("/")[-1], str(_attr(h, "Text") or _attr(h, "Tooltip")).strip()))
                if t in CONTENEDORES or _attr(h, "ContainerType", False):
                    rec(h)
        except Exception:
            pass
    rec(w)
    return " · ".join(partes)


def _esperar(ses, seg=60):
    t0 = time.time()
    while ses.Busy and time.time() - t0 < seg:
        time.sleep(0.2)


def _mensaje(ses):
    sb = ses.findById("wnd[0]/sbar")
    return str(sb.Text).strip(), str(sb.MessageType)


def traspaso(ses, mov, material, centro, almacen, lote, cantidad, um="", modo="comprobar", clave=None, motivo="", almacen_destino=""):
    """Prepara (y opcionalmente contabiliza) un traspaso en MIGO. Devuelve un dict con el resultado."""
    mov, cantidad = str(mov).strip().upper(), cantidad
    permitidos = MOVIMIENTOS_PERMITIDOS if modo == "contabilizar" else MOVIMIENTOS_COMPROBAR
    if mov not in permitidos:
        raise MigoError("Movimiento %s no permitido para %s (permitidos: %s)." % (mov, "contabilizar de verdad" if modo == "contabilizar" else "comprobar", ", ".join(sorted(permitidos))))
    if mov in CON_DESTINO and not str(almacen_destino).strip():
        raise MigoError("El movimiento %s necesita almacén de destino." % mov)
    try:
        cant = float(str(cantidad).replace(",", "."))
    except ValueError:
        raise MigoError("Cantidad no válida.")
    if not 0 < cant <= MAX_CANTIDAD:
        raise MigoError("Cantidad fuera de rango (máximo %s)." % MAX_CANTIDAD)
    if modo not in ("comprobar", "contabilizar"):
        raise MigoError("Modo no válido.")
    esperada = huella(mov, material, centro, almacen, lote, cantidad, motivo, almacen_destino)
    if modo == "contabilizar" and (clave or "").upper() != esperada:
        raise MigoError("La huella no coincide con los datos: el usuario no ha confirmado estos datos exactos. No se contabiliza.")
    if str(ses.Info.Transaction) != "SESSION_MANAGER" or ses.Children.Count > 1:
        raise MigoError("La sesión no está libre (pantalla inicial, sin ventanas emergentes).")

    res = {"modo": modo, "huella": esperada, "check": "", "documento": "", "mensaje": "", "tipo_mensaje": "", "registro": ""}

    def ir(cmd):
        ses.findById("wnd[0]/tbar[0]/okcd").text = cmd
        ses.findById("wnd[0]").sendVKey(0)
        _esperar(ses)

    def sin_popup(donde):
        if ses.Children.Count > 1:
            raise MigoError("Ventana emergente inesperada %s. No se pulsa nada. Contenido: %s" % (donde, _texto_ventana(ses)))

    ir("/nMIGO")
    try:
        sin_popup("al abrir MIGO")
        usr = lambda: ses.findById("wnd[0]/usr")
        for sufijo, texto in (("GODYNPRO-ACTION", "Transfer Posting"), ("GODYNPRO-REFDOC", "Other")):
            c = _buscar(usr(), "GuiComboBox", sufijo)
            if c is None:
                raise MigoError("No encuentro el desplegable %s." % sufijo)
            for k in range(c.Entries.Count):
                if texto.lower() in str(c.Entries.Item(k).Value).lower():
                    c.key = c.Entries.Item(k).Key
                    _esperar(ses, 30)
                    break
            sin_popup("al elegir " + texto)
        _buscar(usr(), "GuiCTextField", "GODEFAULT_TV-BWART").text = mov                     # movimiento por defecto
        ses.findById("wnd[0]").sendVKey(0)
        _esperar(ses)
        sin_popup("al fijar el movimiento")

        # Al fijar el movimiento MIGO abre el panel de detalle de la primera posición: ahí se teclean los datos.
        def campo(sufijo):
            c = _buscar(usr(), "GuiCTextField", sufijo) or _buscar(usr(), "GuiTextField", sufijo)
            if c is None:
                raise MigoError("No encuentro el campo %s en el detalle de la posición. Campos editables visibles: %s" % (sufijo, _editables(usr())))
            return c

        def intro(donde):
            ses.findById("wnd[0]").sendVKey(0)
            _esperar(ses)
            sin_popup(donde)

        campo("GODYNPRO-MAKTX").text = str(material)                                        # material
        intro("al introducir el material")
        campo("GODYNPRO-NAME1").text = str(centro)                                          # centro
        campo("GODYNPRO-LGOBE").text = str(almacen)                                         # almacén (origen)
        if mov in CON_DESTINO:
            campo("GOITEM-UMLGOBE").text = str(almacen_destino)                             # almacén de destino
        intro("al introducir centro y almacén")
        if lote:
            c = None
            for suf in ("GOITEM-CHARG", "GODYNPRO-CHARG"):
                c = _buscar(usr(), "GuiCTextField", suf) or _buscar(usr(), "GuiTextField", suf)
                if c is not None:
                    break
            if c is None:                                   # puede estar en otra pestaña del detalle («Where»)
                for tab in ("tabpOK_GOITEM_DESTINAT.", "tabpOK_GOITEM_MATERIAL", "tabpOK_GOITEM_QUANTITIES"):
                    t = _buscar(usr(), "GuiTab", tab)
                    if t is not None:
                        t.select()
                        _esperar(ses, 20)
                        c = _buscar(usr(), "GuiCTextField", "CHARG") or _buscar(usr(), "GuiTextField", "CHARG")
                        if c is not None:
                            break
            if c is None:
                raise MigoError("No encuentro el campo de lote (¿el material no gestiona lotes?). Campos editables visibles: %s" % _editables(usr()))
            c.text = str(lote)
            if mov in CON_DESTINO:                            # traslado entre almacenes: MIGO exige también el lote de recepción (el mismo)
                u = _buscar(usr(), "GuiCTextField", "GODYNPRO-UMCHA") or _buscar(usr(), "GuiTextField", "GODYNPRO-UMCHA")
                if u is not None:
                    u.text = str(lote)
        campo("GODYNPRO-ERFMG").text = str(cantidad)                                        # cantidad
        intro("al introducir cantidad y lote")
        if motivo:                                                                          # motivo del movimiento: pestaña «Where»
            t = _buscar(usr(), "GuiTab", "tabpOK_GOITEM_DESTINAT.")
            if t is None:
                raise MigoError("No encuentro la pestaña «Where» del detalle de la posición (aquí va el motivo).")
            t.select()
            _esperar(ses, 20)
            campo("GOITEM-GRUND").text = str(motivo)
            intro("al introducir el motivo")
        ok = _buscar(usr(), "GuiCheckBox", "DETAIL_TAKE")                                    # «Item OK»
        if ok is not None and not ok.selected:
            ok.selected = True
            _esperar(ses)

        chk = _boton_barra(ses, ("check",))
        if chk is None:
            raise MigoError("No encuentro el botón Check de MIGO.")
        chk.press()
        _esperar(ses)
        if ses.Children.Count > 1 and "log" in str(_attr(ses.findById("wnd[1]"), "Text")).lower():
            # «Display logs»: registro de mensajes del Check. Se lee, y solo si no hay errores se cierra con Continue.
            res["registro"] = _texto_ventana(ses)
            b = _buscar(ses.findById("wnd[1]"), "GuiButton", "btn[17]")                    # contador de errores
            try:
                errores = int(str(_attr(b, "Text", "0")).strip() or 0) if b is not None else 0
            except ValueError:
                errores = 0
            if errores > 0:
                raise MigoError("El Check de MIGO da %d error(es). Registro: %s" % (errores, res["registro"]))
            ses.findById("wnd[1]/tbar[0]/btn[0]").press()                                  # Continue
            _esperar(ses)
        sin_popup("tras el Check")
        res["check"], res["tipo_mensaje"] = _mensaje(ses)
        if not res["check"] and res["registro"]:
            avisos = [x.replace("texto: ", "") for x in res["registro"].split(" · ") if x.startswith("texto: ") and not x.replace("texto: ", "").strip().isdigit()
                      and x.replace("texto: ", "") not in ("Type", "Item", "Message text", "Long")]
            res["check"] = "Check sin errores" + (" · aviso: " + "; ".join(avisos) if avisos else "")
            res["tipo_mensaje"] = "W"
        res["mensaje"] = res["check"]
        if res["tipo_mensaje"] in ("E", "A"):
            raise MigoError("MIGO rechaza los datos en el Check: " + res["check"])

        if modo == "contabilizar":
            post = _boton_barra(ses, ("post",))
            if post is None:
                raise MigoError("No encuentro el botón Post de MIGO.")
            post.press()
            _esperar(ses)
            sin_popup("tras Post")
            res["mensaje"], res["tipo_mensaje"] = _mensaje(ses)
            if res["tipo_mensaje"] in ("E", "A"):
                raise MigoError("MIGO no contabilizó: " + res["mensaje"])
            digitos = [t for t in res["mensaje"].replace(".", " ").split() if t.isdigit() and len(t) >= 8]
            res["documento"] = digitos[0] if digitos else ""
    finally:
        # salir de MIGO sin guardar: si SAP pregunta si se descartan los datos, se acepta SOLO si el aviso es el de salir
        try:
            ir("/n")
            if ses.Children.Count > 1:
                titulo = str(_attr(ses.findById("wnd[1]"), "Text")).lower()
                if any(x in titulo for x in ("exit", "salir", "data will be lost", "datos")):
                    ses.findById("wnd[1]/usr/btnSPOP-OPTION1").press()
                    _esperar(ses)
        except Exception:
            pass
    return res


def stock_lote(ses, material, centro, almacen, lote):
    """Stock del lote según MB52 (solo lectura): libre, bloqueado, calidad. Si no hay lotes, la suma del material."""
    r = sap_mb52.consultar(ses, material, centro, almacen, lotes=True, especiales=False)

    def num(v):
        t = str(v).strip().replace(".", "").replace(",", ".")
        try:
            return float(t) if t else 0.0
        except ValueError:
            return 0.0
    tot = {"libre": 0.0, "bloqueado": 0.0, "calidad": 0.0}
    for f in r["filas"]:
        if not str(f.get("MATNR", "")).strip():
            continue                                        # fila de totales
        if lote and str(f.get("CHARG", "")).strip() != str(lote):
            continue
        tot["libre"] += num(f.get("LABST"))
        tot["bloqueado"] += num(f.get("SPEME"))
        tot["calidad"] += num(f.get("INSME"))
    return tot
