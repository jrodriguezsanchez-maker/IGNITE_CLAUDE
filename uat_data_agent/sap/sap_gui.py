"""
Acceso de SOLO LECTURA a SAP por SAP GUI Scripting (Windows + SAP GUI + pywin32).

Salvaguardas:
- Comprueba sistema y mandante antes de cualquier acción; si no coinciden con settings.yaml, se detiene.
- Solo usa la conexión cuyo nombre contiene `connection_name` y abre una SESIÓN NUEVA (no toca la que estés usando); la cierra al terminar.
- Solo abre transacciones de la lista blanca (por defecto SE16N). Nunca escribe nada que no sea "/n<TCODE>" de la lista blanca o "/i" para cerrar su sesión.
- No graba nada en SAP: solo rellena criterios, ejecuta y LEE el ALV de resultados (sin diálogos de fichero).

Controles de SE16N validados en QS4 (inspección de solo lectura): ctxtGD-TAB, txtGD-MAX_LINES y la tabla de criterios
tblSAPLSE16NSELFIELDS_TC dentro de un subscreen. Se buscan POR NOMBRE, no por ruta fija.
"""
import os
import time

CONTENEDORES = ("GuiUserArea", "GuiSimpleContainer", "GuiCustomControl", "GuiContainerShell", "GuiTab", "GuiTabStrip",
                "GuiScrollContainer", "GuiSplitterContainer", "GuiDockShell", "GuiMainWindow", "GuiModalWindow")
COL_LABEL, COL_OPTION, COL_LOW, COL_HIGH, COL_MORE, COL_OUT, COL_TECH = 0, 1, 2, 3, 4, 5, 6


class GuardError(RuntimeError):
    pass


def _attr(o, n, d=""):
    try:
        return getattr(o, n)
    except Exception:
        return d


def find(root, suffix, tipo=None):
    """Primer control cuyo Id termina en `suffix` (y de ese tipo, si se indica)."""
    try:
        hs = root.Children
        for i in range(hs.Count):
            h = hs.Item(i)
            if str(_attr(h, "Id")).endswith(suffix) and (tipo is None or _attr(h, "Type") == tipo):
                return h
            if _attr(h, "Type") in CONTENEDORES or _attr(h, "ContainerType", False):
                r = find(h, suffix, tipo)
                if r is not None:
                    return r
    except Exception:
        pass
    return None


def find_grid(root):
    """Primer ALV (GuiShell con subtipo GridView)."""
    try:
        hs = root.Children
        for i in range(hs.Count):
            h = hs.Item(i)
            if _attr(h, "Type") == "GuiShell" and _attr(h, "SubType") == "GridView":
                return h
            if _attr(h, "Type") in CONTENEDORES or _attr(h, "ContainerType", False):
                r = find_grid(h)
                if r is not None:
                    return r
    except Exception:
        pass
    return None


def need(root, suffix, what, tipo=None):
    c = find(root, suffix, tipo)
    if c is None:
        raise GuardError(f"No encuentro {what} ({suffix}) en la pantalla actual.")
    return c


def attach(cfg):
    """Engancha con SAP GUI, localiza la conexión por nombre, comprueba sistema/mandante y devuelve (conexión, sesión base)."""
    import win32com.client
    sap = win32com.client.GetObject("SAPGUI")
    engine = sap.GetScriptingEngine
    conn = None
    if cfg.get("connection_name"):
        for i in range(engine.Children.Count):
            c = engine.Children(i)
            if cfg["connection_name"].lower() in str(c.Description).lower():
                conn = c
                break
        if conn is None:
            raise GuardError(f"No hay una conexión abierta cuyo nombre contenga '{cfg['connection_name']}'. Entra a mano en SAP Logon.")
    else:
        conn = engine.Children(int(cfg["connection_index"]))
    base = conn.Children(conn.Children.Count - 1)
    sid, cli = base.Info.SystemName, base.Info.Client
    if sid != cfg["system_id"] or cli != cfg["client"]:
        raise GuardError(f"Sesión en {sid}/{cli}; se esperaba {cfg['system_id']}/{cfg['client']}. Detenido.")
    return conn, base


def new_session(conn, base, timeout=30):
    n0 = conn.Children.Count
    base.CreateSession()
    t0 = time.time()
    while conn.Children.Count <= n0:
        if time.time() - t0 > timeout:
            raise TimeoutError("SAP no abrió la sesión nueva (¿límite de sesiones alcanzado?)")
        time.sleep(0.5)
    time.sleep(1.0)
    return conn.Children(conn.Children.Count - 1)


def close_session(ses):
    try:
        ses.findById("wnd[0]/tbar[0]/okcd").text = "/i"
        ses.findById("wnd[0]").sendVKey(0)
    except Exception:
        pass


def wait(s, timeout=900, progress=None, texto=''):
    t0 = time.time()
    while s.Busy:
        if time.time() - t0 > timeout:
            raise TimeoutError("SAP sigue ocupado")
        if progress and texto:
            progress(texto)
        time.sleep(0.3)


def start_tx(s, tcode, cfg):
    if tcode.upper() not in [t.upper() for t in cfg["transaction_whitelist"]]:
        raise GuardError(f"Transacción {tcode} fuera de la lista blanca")
    s.findById("wnd[0]/tbar[0]/okcd").text = "/n" + tcode
    s.findById("wnd[0]").sendVKey(0)
    wait(s, cfg["max_wait_seconds"])
    if s.Info.Transaction.upper() != tcode.upper():
        raise GuardError(f"Se esperaba {tcode} y la sesión está en {s.Info.Transaction}")


def _clipboard(values):
    import time
    import win32clipboard
    ultimo = None
    for _ in range(40):          # otro programa puede tener el portapapeles abierto unos instantes: reintenta hasta ~20 s
        try:
            win32clipboard.OpenClipboard()
            try:
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardText("\r\n".join(values), win32clipboard.CF_UNICODETEXT)
            finally:
                win32clipboard.CloseClipboard()
            return
        except Exception as e:
            ultimo = e
            time.sleep(0.5)
    raise ultimo


def _cell(tbl, r, c):
    try:
        return tbl.GetCell(r, c)
    except Exception:
        return None


def _find_row(s, field):
    """Devuelve (fila_visible, tabla) de la fila de criterios cuyo nombre técnico (o, si no se ve, su etiqueta) es `field`."""
    usr = s.findById("wnd[0]/usr")
    tbl = need(usr, "tblSAPLSE16NSELFIELDS_TC", "la tabla de criterios", "GuiTableControl")
    total = tbl.RowCount
    page = max(1, tbl.VisibleRowCount)
    seen = []
    pos = 0
    while pos < total:
        tbl.VerticalScrollbar.Position = pos
        tbl = need(s.findById("wnd[0]/usr"), "tblSAPLSE16NSELFIELDS_TC", "la tabla de criterios", "GuiTableControl")
        for r in range(tbl.VisibleRowCount):
            tech = _cell(tbl, r, COL_TECH)
            label = _cell(tbl, r, COL_LABEL)
            t = str(_attr(tech, "Text")).strip() if tech is not None else ""
            l = str(_attr(label, "Text")).strip() if label is not None else ""
            seen.append(t or l)
            if t and t.upper() == field.upper():
                return r, tbl
        pos += page
    raise GuardError(f"Campo {field} no encontrado en los criterios de SE16N. Vistos: {seen[:15]}"
                     + ("" if any(seen) else " (la columna de nombre técnico no es legible: hay que mostrarla en SE16N)"))


KEYCOLS = ("MATNR", "EQUNR", "INFNR", "STLNR", "PLNNR", "AUFNR", "LGNUM", "LIFNR")     # claves que se propagan entre etapas: siempre en la salida


def _set_output(s, want):
    """Marca en la pantalla de selección de SE16N SOLO las columnas de salida que necesitamos (casilla de la columna COL_OUT).
    Devuelve (marcadas, no_encontradas). Si la casilla no es legible, no toca nada y lo dice: se sigue con la salida por defecto."""
    want = {w.upper() for w in want} | set(KEYCOLS)
    usr = s.findById("wnd[0]/usr")
    tbl = need(usr, "tblSAPLSE16NSELFIELDS_TC", "la tabla de criterios", "GuiTableControl")
    total, page = tbl.RowCount, max(1, tbl.VisibleRowCount)
    marcadas, vistas, pos = set(), set(), 0
    while pos < total:
        tbl.VerticalScrollbar.Position = pos
        tbl = need(s.findById("wnd[0]/usr"), "tblSAPLSE16NSELFIELDS_TC", "la tabla de criterios", "GuiTableControl")
        for r in range(tbl.VisibleRowCount):
            tech, chk = _cell(tbl, r, COL_TECH), _cell(tbl, r, COL_OUT)
            t = str(_attr(tech, "Text")).strip().upper() if tech is not None else ""
            if not t:
                continue
            vistas.add(t)
            if chk is None or _attr(chk, "Type") != "GuiCheckBox":
                return None, "la casilla de salida no es una casilla legible (tipo %s)" % (_attr(chk, "Type") if chk is not None else "None")
            quiero = t in want
            if bool(chk.Selected) != quiero:
                chk.Selected = quiero
            if quiero:
                marcadas.add(t)
        pos += page
    tbl.VerticalScrollbar.Position = 0
    return marcadas, sorted(w for w in want if w not in vistas and w not in KEYCOLS)


def _set_filter(s, field, values, cfg):
    """values: lista de valores (uno o varios) o dict {"low": X, "high": Y} para un rango."""
    r, tbl = _find_row(s, field)
    low, high, push = _cell(tbl, r, COL_LOW), _cell(tbl, r, COL_HIGH), _cell(tbl, r, COL_MORE)
    if isinstance(values, dict):
        low.Text = str(values["low"])
        if values.get("high"):
            high.Text = str(values["high"])
        return
    if len(values) == 1:
        low.Text = values[0]
        return
    if push is None:
        raise GuardError(f"Sin botón de selección múltiple para {field}")
    push.setFocus()
    push.Press()
    t0 = time.time()
    while s.Children.Count < 2:                      # el popup de selección múltiple tarda en abrirse
        if time.time() - t0 > 15:
            raise GuardError(f"No se abrió la selección múltiple de {field}")
        time.sleep(0.3)
    wait(s, cfg["max_wait_seconds"])
    _clipboard(values)
    s.findById("wnd[1]/tbar[0]/btn[24]").Press()   # Upload from Clipboard
    wait(s, cfg["max_wait_seconds"])
    s.findById("wnd[1]/tbar[0]/btn[8]").Press()    # Transfer Data (F8)
    wait(s, cfg["max_wait_seconds"])
    t0 = time.time()
    while s.Children.Count > 1:
        if time.time() - t0 > 15:
            raise GuardError(f"El popup de selección múltiple de {field} no se cerró")
        time.sleep(0.3)


def _read_grid(grid, fields=None, max_rows=None, progress=None):
    """Lee el ALV completo. El ALV solo tiene cargadas las filas visibles: hay que ir haciendo scroll por páginas."""
    cols = [str(grid.ColumnOrder.ElementAt(i)) for i in range(grid.ColumnOrder.Count)]
    use = [c for c in cols if not fields or c in fields]
    if fields and not use:
        raise GuardError(f"El resultado no trae ninguna de las columnas pedidas {fields}. Trae: {cols[:20]}")
    total = grid.RowCount
    n = min(total, max_rows) if max_rows else total
    page = max(1, int(grid.VisibleRowCount))
    rows = []
    start = 0
    while start < n:
        if progress:
            progress(f'leyendo filas del resultado: {min(start + page, n)} de {n}')
        grid.firstVisibleRow = start
        time.sleep(0.05)
        for i in range(start, min(start + page, n)):
            rows.append([str(grid.GetCellValue(i, c)).strip() for c in use])
        start += page
    if len(rows) != n:
        raise GuardError(f"Leídas {len(rows)} filas de {n}")
    return use, rows


def se16n_extract(s, table, filters, out_name, cfg, dry_run=False, max_rows=None, fields=None, progress=None):
    """Consulta `table` con `filters` {CAMPO: [valores]} y deja <export_dir>/<out_name>.txt (texto con tabuladores).
    Devuelve la ruta o None si no hay datos."""
    if dry_run:
        print(f"[dry-run] SE16N {table} filtros={ {k: (v if isinstance(v, dict) else len(v)) for k, v in filters.items()} } -> {out_name}.txt")
        return None
    P = progress or (lambda m: None)
    P('abriendo SE16N')
    start_tx(s, "SE16N", cfg)
    usr = lambda: s.findById("wnd[0]/usr")
    P(f'cargando la tabla {table}')
    need(usr(), "ctxtGD-TAB", "el campo de tabla").Text = table
    s.findById("wnd[0]").sendVKey(0)
    wait(s, cfg["max_wait_seconds"])
    ml = find(usr(), "txtGD-MAX_LINES")
    if ml is not None:
        ml.Text = str(max_rows) if max_rows else ""        # vacío = sin límite
    if fields:
        P('marcando las columnas de salida')
        try:
            marc, falta = _set_output(s, fields)
            if marc is None:
                print(f"{table}: salida por defecto ({falta})")
            else:
                print(f"{table}: salida = {len(marc)} columnas marcadas" + (f"; no existen en la tabla: {falta}" if falta else ""))
        except GuardError:
            raise
        except Exception as e:
            print(f"{table}: no pude elegir las columnas ({type(e).__name__}: {e}); salida por defecto")
    for f, vals in filters.items():
        P(f'poniendo el filtro {f}' + (f' ({len(vals)} valores: se pegan en SAP)' if not isinstance(vals, dict) and len(vals) > 1 else ''))
        _set_filter(s, f, vals if isinstance(vals, dict) else [str(v) for v in vals], cfg)
    P('ejecutando en SAP')
    s.findById("wnd[0]/tbar[1]/btn[8]").Press()             # Ejecutar (F8)
    wait(s, cfg["max_wait_seconds"], P, 'SAP está buscando los datos (puede tardar varios minutos)')
    grid = find_grid(s.findById("wnd[0]"))
    if grid is None:
        msg = str(s.findById("wnd[0]/sbar").Text)
        print(f"{table}: sin resultados ({msg})")
        return None
    hdr, rows = _read_grid(grid, fields, max_rows, P)
    P('guardando el fichero')
    os.makedirs(cfg["export_dir"], exist_ok=True)
    path = os.path.join(cfg["export_dir"], f"{out_name}.txt")
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write("\t".join(hdr) + "\n")
        for r in rows:
            fh.write("\t".join(x.replace("\t", " ").replace("\n", " ") for x in r) + "\n")
    return path
