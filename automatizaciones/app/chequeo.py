"""Chequeo previo (solo lectura): no contabiliza nada en SAP.

Para cada escenario seleccionado comprueba:
  - datos completos para su movimiento / tipo de documento (Excel + aportados + valores por centro),
  - registro info por material (solo pedidos de traslado),
  - stock libre y lote (FEFO/FIFO) en centro/almacén origen (MB52, o cuantos WM si el almacén es WM),
  - cantidad: si no se indicó, propuesta desde el stock libre del lote (solo con SAP conectado; el motor simulado no la propone).
"""
import engine
import sit_import

TRAZA = ("jira_id", "id_jira_unidad", "new_id", "unidad")


def _si(v):
    return str(v or "").strip().upper() in ("S", "SI", "SÍ", "Y", "YES", "1")


def chequear(sel, backend, cantidad_global, req_cfg, defaults, modo):
    campos = req_cfg["campos"]
    filas = []
    for e in sel:
        vals, fuentes, faltan, req = sit_import.resolver(e, e["mov"], req_cfg, defaults, cantidad_global)
        fila = {**{k: e.get(k, "") for k in TRAZA}, "clave": e["clave"], "escenario": e["escenario"], "mov": e["mov"],
                "estado": "LISTO", "faltan": [campos[f] for f in faltan], "avisos": [], "items": []}
        if e.get("requiere_doc_previo"):
            fila["avisos"].append("necesita documento previo (PO/orden)")
        if req.get("desconocido"):
            fila["avisos"].append("requisitos del movimiento sin definir")
        if req.get("transaccion"):
            fila["estado"] = "NO_SOPORTADO"
            fila["avisos"].append("no se hace con MIGO (%s)" % req["transaccion"])
        elif faltan:
            fila["estado"] = "FALTAN_DATOS"
        else:
            wm = _si(vals.get("wm"))
            centro, almacen = vals["centro"], vals.get("alm_origen", "")
            try:
                qty = float(str(vals["cantidad"]).replace(",", "."))
            except ValueError:
                qty = float(cantidad_global)
            malos = sin_stock = parcial = errores = 0
            for m in vals["material"]:
                try:
                    st = backend.stock_origen(m, centro, almacen, wm)
                except Exception as ex:          # p. ej. almacén WM aún no soportado, SAP ocupado o sin sesión
                    errores += 1
                    fila["items"].append({"material": m, "stock": None, "fuente_stock": "", "lotes_activo": None, "lote": "", "lote_stock": 0,
                                          "cantidad": qty, "cantidad_origen": fuentes.get("cantidad", ""), "registro_info": None,
                                          "cantidad_propuesta": None, "lote_propuesto": "", "error": str(ex)})
                    continue
                lineas = sorted([l for l in st["lineas"] if l["qty"] > 0], key=engine._orden)
                total = sum(l["qty"] for l in lineas)
                item = {"material": m, "stock": total, "fuente_stock": st["fuente"], "lotes_activo": st["lotes_activo"],
                        "lote": (lineas[0]["lote"] or "sin lote") if lineas else "", "lote_stock": lineas[0]["qty"] if lineas else 0,
                        "cantidad": qty, "cantidad_origen": fuentes.get("cantidad", ""), "registro_info": None,
                        "cantidad_propuesta": None, "lote_propuesto": ""}
                pend = qty
                asign = []
                for l in lineas:                                   # lotes en orden FEFO/FIFO hasta cubrir la cantidad
                    if pend <= 0:
                        break
                    q = min(pend, l["qty"])
                    asign.append({"lote": l["lote"] or "sin lote", "cantidad": q})
                    pend -= q
                item["lotes"] = [{"lote": l["lote"] or "sin lote", "qty": l["qty"]} for l in lineas]
                item["asignacion"] = asign
                item["sin_cubrir"] = max(pend, 0)
                if modo == "sto":
                    try:
                        item["registro_info"] = bool(backend.registro_info(m, centro, vals["org_compras"]))
                        malos += 0 if item["registro_info"] else 1
                    except NotImplementedError:
                        if "registro info no comprobado" not in " ".join(fila["avisos"]):
                            fila["avisos"].append("registro info no comprobado (la comprobación real aún no está implementada)")
                if not lineas:
                    sin_stock += 1
                elif total < qty:
                    parcial += 1
                if item["cantidad_origen"] == "global" and backend.puede_proponer_cantidad:
                    p = backend.proponer_cantidad(m, centro, almacen, wm)
                    if p:
                        item["cantidad_propuesta"], item["lote_propuesto"] = p["cantidad"], p["lote"] or "sin lote"
                fila["items"].append(item)
            if errores:
                fila["estado"] = "ERROR_SAP"
                fila["avisos"].append("error al leer SAP: " + "; ".join(sorted({i["error"] for i in fila["items"] if i.get("error")}))[:300])
            elif malos:
                fila["estado"] = "SIN_REGISTRO_INFO"
            elif sin_stock == len(fila["items"]):
                fila["estado"] = "SIN_STOCK"
            elif sin_stock or parcial:
                fila["estado"] = "AVISO"
                fila["avisos"].append("stock insuficiente en algún material: se movería lo disponible (parcial)")
        filas.append(fila)
    info = backend.info() if hasattr(backend, "info") else {}
    return {"simulado": backend.simulado, "puede_proponer": backend.puede_proponer_cantidad, "sistema": info, "filas": filas}
