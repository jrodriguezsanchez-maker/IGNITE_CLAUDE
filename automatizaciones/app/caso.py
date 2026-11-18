"""Caso concreto: un movimiento de material definido a mano (o con lenguaje natural) y lanzado desde la pestaña «Caso concreto».
- interpretar(): rellena los campos desde una frase, con reglas locales (no sale nada fuera del equipo).
- leer_lotes(): MB52 de solo lectura -> TODOS los lotes con stock del material en ese centro/almacén (con evidencia de lo leído).
- preparar(): valida, aplica los valores por defecto (destino vacío = origen) y calcula la huella de los datos exactos.
Contabilizar reutiliza server.execute_real (misma verificación de stock, lectura FI/CO/ML y pestañas de resultados)."""
import re
from contextlib import contextmanager

import sap_backend
import sap_mb52
import sap_migo

# Stock del que sale cada movimiento: define qué columna de MB52 se enseña y se toma como cantidad disponible.
STOCK_ORIGEN = {"301": "libre", "311": "libre", "343": "bloqueado", "344": "libre", "321": "calidad", "322": "libre"}
COLUMNA_STOCK = {"libre": "LABST", "calidad": "INSME", "bloqueado": "SPEME"}
NOMBRES = {"301": "Traslado entre centros", "311": "Traslado entre almacenes", "343": "Bloqueado → libre utilización",
           "344": "Libre utilización → bloqueado", "321": "Calidad → libre utilización", "322": "Libre utilización → calidad"}
CAMPOS = ("mov", "material", "centro", "almacen", "centro_destino", "almacen_destino", "lote", "lote_destino", "cantidad", "tipo_stock",
          "vendor", "pedido_compra", "orden_produccion", "motivo")


def _txt(v):
    return str(v or "").strip()


def interpretar(texto):
    """Frase -> campos. Solo reglas locales; devuelve lo que ha entendido y lo que no."""
    t = _txt(texto)
    low = t.lower()
    c, entendido = {}, []

    def poner(k, v, why):
        if v and k not in c:
            c[k] = v
            entendido.append("%s = %s (%s)" % (k, v, why))

    m = re.search(r"(?:movimiento|mov\.?|tipo)\s*([0-9a-z]{3})\b", low) or re.match(r"\s*(\d{3}|z\d{2})\b", low)
    if m:
        poner("mov", m.group(1).upper(), "indicado")
    else:
        for patron, mov in ((r"entre\s+(?:centros|plantas)", "301"), (r"entre\s+almacenes|de\s+almac[eé]n\s+a\s+almac[eé]n", "311"),
                            (r"desbloque|libera(?:r)?\s+(?:el\s+)?(?:stock\s+)?bloqueado|bloqueado\s+a\s+libre", "343"),
                            (r"bloque", "344"), (r"calidad\s+a\s+libre|liberar\s+de\s+calidad", "321"), (r"libre\s+a\s+calidad|pasar\s+a\s+calidad", "322")):
            if re.search(patron, low):
                poner("mov", mov, "por la frase")
                break
    m = re.search(r"material\s+0*([0-9a-z\-]{4,18})", low)
    if m:
        poner("material", m.group(1).upper(), "indicado")
    else:
        m = re.search(r"\b0*(\d{6,9})\b", low)
        if m:
            poner("material", m.group(1), "primer número largo")
    m = re.search(r"\b([a-z]\d{3})\b\s*(?:/|-|\s)\s*(\d{4})?\s*(?:a|->|→|hacia|=>)\s*\b([a-z]\d{3})\b\s*(?:/|-|\s)?\s*(\d{4})?", low)
    if m:
        poner("centro", m.group(1).upper(), "origen")
        poner("almacen", m.group(2), "origen")
        poner("centro_destino", m.group(3).upper(), "destino")
        poner("almacen_destino", m.group(4), "destino")
    else:
        for k, pat in (("centro", r"(?:centro|planta)(?:\s+origen)?\s+([a-z0-9]{4})\b"), ("centro_destino", r"(?:centro|planta)\s+destino\s+([a-z0-9]{4})\b")):
            m = re.search(pat, low)
            if m:
                poner(k, m.group(1).upper(), "indicado")
        plantas = list(dict.fromkeys(re.findall(r"\b([a-z]\d{3})\b", low)))
        if "centro" not in c and plantas:
            poner("centro", plantas[0].upper(), "primera planta citada")
        if "centro_destino" not in c and len(plantas) > 1:
            poner("centro_destino", plantas[1].upper(), "segunda planta citada")
    m = re.search(r"almac[eé]n(?:es)?\s+(?:origen\s+)?(\d{4})\s*(?:a|->|→|hacia|=>)\s*(\d{4})", low)
    if m:
        poner("almacen", m.group(1), "origen")
        poner("almacen_destino", m.group(2), "destino")
    else:
        m = re.search(r"almac[eé]n(?:\s+origen)?\s+(\d{4})", low)
        if m:
            poner("almacen", m.group(1), "indicado")
        m = re.search(r"almac[eé]n\s+destino\s+(\d{4})", low)
        if m:
            poner("almacen_destino", m.group(1), "indicado")
    m = re.search(r"lote\s+destino\s+([^\s,;]+)", t, re.I)
    if m:
        poner("lote_destino", m.group(1), "indicado")
    m = re.search(r"lote(?:\s+origen)?\s+(?!destino)([^\s,;]+)", t, re.I)
    if m:
        poner("lote", m.group(1), "indicado")
    m = re.search(r"cantidad\s+(\d+(?:[.,]\d+)?)", low) or re.search(r"\b(\d+(?:[.,]\d+)?)\s*(?:kg|un\b|uni|unidades|ud|l\b|litros|m\b|metros)", low)
    if m:
        poner("cantidad", m.group(1), "indicado")
    m = re.search(r"(?:proveedor|vendor)\s+([a-z0-9]+)", low)
    if m:
        poner("vendor", m.group(1).upper(), "indicado")
    m = re.search(r"pedido(?:\s+de\s+compra)?\s+(\d{8,10})", low)
    if m:
        poner("pedido_compra", m.group(1), "indicado")
    m = re.search(r"orden(?:\s+de\s+producci[oó]n)?\s+(\d{6,12})", low)
    if m:
        poner("orden_produccion", m.group(1), "indicado")
    m = re.search(r"motivo\s+(\d{4})", low)
    if m:
        poner("motivo", m.group(1), "indicado")
    m = re.search(r"\b(libre|calidad|bloqueado)\b\s+(?:stock|de\s+stock)", low) or re.search(r"stock\s+(libre|de\s+calidad|bloqueado)", low)
    if m:
        poner("tipo_stock", m.group(1).replace("de ", ""), "indicado")
    return {"campos": c, "entendido": entendido,
            "mensaje": "No he entendido nada: indica al menos movimiento, material, centro, almacén y cantidad." if not c else
                       "He rellenado %d campo(s). Revísalos antes de buscar stock." % len(c)}


@contextmanager
def sesion_sap():
    """Sesión SAP de solo el sistema/mandante permitidos: una libre o una nueva (que se cierra al terminar)."""
    cfg = sap_backend.leer_config()
    if cfg.get("modo") != "sap":
        raise sap_mb52.SapError("Esta pestaña lee SAP real: cambia el selector de la cabecera a «Chequeo con SAP real».")
    p = (cfg.get("sistemas_permitidos") or [None])[0]
    if not p:
        raise sap_mb52.SapError("No hay sistema SAP permitido configurado.")
    pc = sap_mb52.pythoncom
    pc.CoInitialize()
    ses = creada = None
    try:
        ses, creada = sap_mb52.sesion(p["sid"], crear=True, mandante=p["mandante"], conexion=p.get("conexion"))
        if str(ses.Info.SystemName).upper() != p["sid"].upper() or str(ses.Info.Client) != str(p["mandante"]):
            raise sap_mb52.SapError("La sesión no es del sistema/mandante permitidos.")
        yield ses
    finally:
        try:
            if ses is not None and creada:
                sap_mb52.cerrar_sesion(ses)
        finally:
            pc.CoUninitialize()


def leer_lotes(material, centro, almacen):
    """TODOS los lotes del material en ese centro/almacén (MB52, solo lectura), con stock libre, de calidad y bloqueado."""
    material, centro, almacen = _txt(material), _txt(centro).upper(), _txt(almacen)
    if not (material and centro):
        raise ValueError("Indica material y centro para buscar stock.")
    with sesion_sap() as ses:
        r = sap_mb52.consultar(ses, material, centro, almacen, lotes=True, especiales=False, columnas=sap_mb52.COLUMNAS_STOCK)
    lotes = []
    for f in r["filas"]:
        if not _txt(f.get("MATNR", "")):
            continue                                                           # fila de totales
        lotes.append({"lote": _txt(f.get("CHARG", "")), "centro": _txt(f.get("WERKS", "")) or centro, "almacen": _txt(f.get("LGORT", "")) or almacen,
                      "libre": sap_backend.numero(f.get("LABST", "0")), "calidad": sap_backend.numero(f.get("INSME", "0")),
                      "bloqueado": sap_backend.numero(f.get("SPEME", "0")), "um": _txt(f.get("MEINS", "")), "descripcion": _txt(f.get("MAKTX", ""))})
    evidencia = "MB52 %s/%s, material %s: %d línea(s) leída(s) de %s filas del listado" % (centro, almacen or "todos los almacenes", material, len(lotes), r.get("total_filas", 0))
    if r.get("mensaje"):
        evidencia += " · mensaje de SAP: " + r["mensaje"]
    return {"lotes": lotes, "evidencia": evidencia, "lotes_activo": any(l["lote"] for l in lotes)}


def preparar(campos, req, motivos, lotes_leidos=None):
    """Valida, rellena los valores por defecto y calcula la huella. No toca SAP salvo que se pase lotes_leidos (ya leídos)."""
    c = {k: _txt(campos.get(k)) for k in CAMPOS}
    mov = c["mov"].upper()
    problemas, avisos, derivado = [], [], []
    info = (req.get("movimientos") or {}).get(mov) or {}
    res = {"ok": False, "problemas": problemas, "avisos": avisos, "derivado": derivado, "mov": mov,
           "nombre": NOMBRES.get(mov) or info.get("nombre", ""), "requiere": info.get("requiere", []),
           "permitido_comprobar": mov in sap_migo.MOVIMIENTOS_COMPROBAR, "permitido_contabilizar": mov in sap_migo.MOVIMIENTOS_PERMITIDOS}
    if not re.match(r"^[0-9A-Z]{3,4}$", mov):
        problemas.append("Falta el tipo de movimiento.")
    if not c["material"]:
        problemas.append("Falta el material.")
    if not c["centro"]:
        problemas.append("Falta el centro de origen.")
    if not c["almacen"]:
        problemas.append("Falta el almacén de origen.")
    try:
        cant = float(str(c["cantidad"]).replace(",", ".").replace(" ", "")) if "," not in c["cantidad"] or "." not in c["cantidad"] else float(sap_migo.normalizar_cantidad(c["cantidad"]))
    except ValueError:
        cant = 0
    if not 0 < cant <= sap_migo.MAX_CANTIDAD:
        problemas.append("Falta la cantidad o está fuera de rango (máximo %s)." % sap_migo.MAX_CANTIDAD)
    d = {"mov": mov, "material": c["material"].upper(), "centro": c["centro"].upper(), "almacen": c["almacen"],
         "cantidad": sap_migo.normalizar_cantidad(cant) if cant else "", "motivo": c["motivo"]}
    for k_dest, k_org, etq in (("centro_destino", "centro", "centro de destino"), ("almacen_destino", "almacen", "almacén de destino")):
        d[k_dest] = (c[k_dest].upper() if k_dest == "centro_destino" else c[k_dest]) or d[k_org]
        if not c[k_dest]:
            derivado.append("%s = %s (el mismo que el origen)" % (etq, d[k_dest]))
    d["lote"] = c["lote"]
    d["lote_destino"] = c["lote_destino"] or c["lote"]
    d["tipo_stock"] = (c["tipo_stock"] or STOCK_ORIGEN.get(mov, "libre")).lower()
    if d["tipo_stock"] not in COLUMNA_STOCK:
        problemas.append("Tipo de stock no válido (libre, calidad o bloqueado).")
        d["tipo_stock"] = STOCK_ORIGEN.get(mov, "libre")
    if mov in sap_migo.CON_CENTRO_DESTINO and d["centro_destino"] == d["centro"]:
        problemas.append("Un traslado entre centros necesita un centro de destino distinto del de origen.")
    if mov == "311" and d["almacen_destino"] == d["almacen"] and d["centro_destino"] == d["centro"]:
        problemas.append("Un traslado entre almacenes necesita un almacén de destino distinto del de origen.")
    if mov not in sap_migo.CON_CENTRO_DESTINO and d["centro_destino"] != d["centro"]:
        problemas.append("El movimiento %s no cambia de centro: deja vacío el centro de destino." % mov)
    if mov in motivos and motivos[mov] and not d["motivo"]:
        problemas.append("El movimiento %s necesita motivo (%s)." % (mov, ", ".join(m["codigo"] for m in motivos[mov][:6])))
    for k, etq in (("vendor", "proveedor"), ("pedido_compra", "pedido de compra"), ("orden_produccion", "orden de producción")):
        d[k] = c[k]
        if c[k] and etq not in " ".join(res["requiere"]):
            avisos.append("El %s no se usa en el movimiento %s: se ignora." % (etq, mov))
    if re.match(r"^[0-9A-Z]{3,4}$", mov) and not res["permitido_comprobar"]:
        problemas.append("El movimiento %s todavía no se puede chequear ni contabilizar desde aquí (soportados: %s)." % (mov, ", ".join(sorted(sap_migo.MOVIMIENTOS_COMPROBAR))))
    # lote: obligatorio si el material lleva lotes; si falta, se deriva del stock leído (el primero que cubre la cantidad)
    if lotes_leidos is not None and not d["lote"]:
        col = d["tipo_stock"]
        cubren = sorted([l for l in lotes_leidos["lotes"] if l[col] >= cant > 0], key=lambda l: l["lote"])
        if lotes_leidos["lotes_activo"]:
            if cubren:
                d["lote"] = cubren[0]["lote"]
                d["lote_destino"] = c["lote_destino"] or d["lote"]
                derivado.append("lote = %s (primero con %s %s libre suficiente; sin fechas de caducidad, por orden de lote: cámbialo si quieres otro)" % (d["lote"], cubren[0][col], cubren[0]["um"]))
            else:
                problemas.append("Ningún lote tiene %s suficiente (%s) para %s: elige uno o baja la cantidad." % (d["tipo_stock"], lotes_leidos["evidencia"], d["cantidad"]))
    elif lotes_leidos is None and not d["lote"]:
        avisos.append("Sin lote: pulsa «Buscar stock» para ver los lotes y elegir uno (si el material no lleva lotes, vale así).")
    res["datos"] = d
    res["ok"] = not problemas
    if res["ok"]:
        res["huella"] = sap_migo.huella(mov, d["material"], d["centro"], d["almacen"], d["lote"], d["cantidad"], d["motivo"],
                                        d["almacen_destino"] if mov in sap_migo.CON_DESTINO else "",
                                        d["centro_destino"] if mov in sap_migo.CON_CENTRO_DESTINO else "", d["lote_destino"] if d["lote_destino"] != d["lote"] else "")
    return res
