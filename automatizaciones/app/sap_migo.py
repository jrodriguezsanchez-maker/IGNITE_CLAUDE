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

MOVIMIENTOS_PERMITIDOS = {"344", "343"}      # se amplía de uno en uno, tras probar cada uno
MAX_CANTIDAD = 100000
CONTENEDORES = ("GuiUserArea", "GuiSimpleContainer", "GuiContainerShell", "GuiTab", "GuiTabStrip", "GuiScrollContainer", "GuiCustomControl",
                "GuiSplitterContainer", "GuiMainWindow", "GuiGOS", "GuiTableControl")


class MigoError(sap_mb52.SapError):
    pass


def huella(mov, material, centro, almacen, lote, cantidad):
    """Código que identifica los datos exactos. Cambia si cambia cualquiera de ellos."""
    txt = "|".join(str(x).strip().upper() for x in (mov, material, centro, almacen, lote, cantidad))
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


def _esperar(ses, seg=60):
    t0 = time.time()
    while ses.Busy and time.time() - t0 < seg:
        time.sleep(0.2)


def _mensaje(ses):
    sb = ses.findById("wnd[0]/sbar")
    return str(sb.Text).strip(), str(sb.MessageType)


def traspaso(ses, mov, material, centro, almacen, lote, cantidad, um="", modo="comprobar", clave=None):
    """Prepara (y opcionalmente contabiliza) un traspaso en MIGO. Devuelve un dict con el resultado."""
    mov, cantidad = str(mov).strip().upper(), cantidad
    if mov not in MOVIMIENTOS_PERMITIDOS:
        raise MigoError("Movimiento %s no permitido para la contabilización real (permitidos: %s)." % (mov, ", ".join(sorted(MOVIMIENTOS_PERMITIDOS))))
    try:
        cant = float(str(cantidad).replace(",", "."))
    except ValueError:
        raise MigoError("Cantidad no válida.")
    if not 0 < cant <= MAX_CANTIDAD:
        raise MigoError("Cantidad fuera de rango (máximo %s)." % MAX_CANTIDAD)
    if modo not in ("comprobar", "contabilizar"):
        raise MigoError("Modo no válido.")
    esperada = huella(mov, material, centro, almacen, lote, cantidad)
    if modo == "contabilizar" and (clave or "").upper() != esperada:
        raise MigoError("La huella no coincide con los datos: el usuario no ha confirmado estos datos exactos. No se contabiliza.")
    if str(ses.Info.Transaction) != "SESSION_MANAGER" or ses.Children.Count > 1:
        raise MigoError("La sesión no está libre (pantalla inicial, sin ventanas emergentes).")

    res = {"modo": modo, "huella": esperada, "check": "", "documento": "", "mensaje": "", "tipo_mensaje": ""}

    def ir(cmd):
        ses.findById("wnd[0]/tbar[0]/okcd").text = cmd
        ses.findById("wnd[0]").sendVKey(0)
        _esperar(ses)

    def sin_popup(donde):
        if ses.Children.Count > 1:
            raise MigoError("Ventana emergente inesperada %s: %s. No se pulsa nada." % (donde, str(_attr(ses.findById("wnd[1]"), "Text")).strip()))

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

        tabla = "tblSAPLMIGOTV_GOITEM"
        def celda(prefijo, col):
            c = _buscar(usr(), "GuiCTextField", "%s[%d,0]" % (prefijo, col)) or _buscar(usr(), "GuiTextField", "%s[%d,0]" % (prefijo, col))
            if c is None:
                raise MigoError("No encuentro la columna %s de la tabla de posiciones." % prefijo)
            return c
        celda("GOITEM-MAKTX", 1).text = str(material)                                       # material
        ses.findById("wnd[0]").sendVKey(0)
        _esperar(ses)
        sin_popup("al introducir el material")
        celda("GOITEM-NAME1", 8).text = str(centro)                                        # centro
        celda("GOITEM-LGOBE", 5).text = str(almacen)                                       # almacén
        ses.findById("wnd[0]").sendVKey(0)
        _esperar(ses)
        sin_popup("al introducir centro y almacén")
        celda("GOITEM-ERFMG", 3).text = str(cantidad).replace(".", ",") if "," not in str(cantidad) and "." in str(cantidad) else str(cantidad)
        if um:
            celda("GOITEM-ERFME", 4).text = str(um)
        if lote:
            c = _buscar(usr(), "GuiCTextField", "GOITEM-CHARG") or _buscar(usr(), "GuiCTextField", "GODYNPRO-CHARG") or _buscar(usr(), "GuiTextField", "GOITEM-CHARG")
            if c is None:
                raise MigoError("No encuentro el campo de lote (¿el material no gestiona lotes?).")
            c.text = str(lote)
        ses.findById("wnd[0]").sendVKey(0)
        _esperar(ses)
        sin_popup("al introducir cantidad y lote")
        ok = _buscar(usr(), "GuiCheckBox", "DETAIL_TAKE")                                    # «Item OK»
        if ok is not None and not ok.selected:
            ok.selected = True
            _esperar(ses)

        chk = _boton_barra(ses, ("check",))
        if chk is None:
            raise MigoError("No encuentro el botón Check de MIGO.")
        chk.press()
        _esperar(ses)
        sin_popup("tras el Check")
        res["check"], res["tipo_mensaje"] = _mensaje(ses)
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
