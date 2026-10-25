"""Ejecución (fase 1) de escenarios con pedido de traslado: registro info, lote con stock, STO y entrega de salida.

Orden por escenario:
  1. Resolver datos (Excel + aportados + valores por centro) y comprobar los obligatorios del tipo ZTRA/ZINT/ZWIA.
  2. Validar registro info de cada material con el centro suministrador. Si falta alguno, se para el escenario y se avisa.
  3. Buscar stock en centro/almacén suministrador (MB52, o cuantos WM si el almacén es WM) y elegir lote FEFO/FIFO.
  4. Crear el STO (ME21N) y la entrega de salida (VL10B, pedidos pendientes de entrega). No se hace picking ni salida de mercancía todavía.
En modo simulado nada de esto toca SAP.
"""
import engine
import sit_import

TRAZA = ("jira_id", "id_jira_unidad", "new_id", "unidad")
ESTADOS = ("OK", "PARCIAL", "SIN_STOCK", "ERROR", "FALTAN_DATOS", "SIN_REGISTRO_INFO")


def _si(v):
    return str(v or "").strip().upper() in ("S", "SI", "SÍ", "Y", "YES", "1")


def ejecutar(catalogo_sel, backend, log, cantidad_global, req_cfg, defaults, propuestas=None):
    out = {"escenarios": [], "sto": [], "entregas": [], "pasos": []}
    resumen = {k: 0 for k in ESTADOS}
    campos = req_cfg["campos"]
    for e in catalogo_sel:
        t = {k: e.get(k, "") for k in TRAZA}
        ref = "%s / %s" % (e["jira_id"], e["id_jira_unidad"])
        vals, fuentes, faltan, req = sit_import.resolver(e, e["mov"], req_cfg, defaults, cantidad_global)
        esc = {**t, "escenario": e["escenario"], "mov": e["mov"], "estado": "", "detalle": "", "sto": "", "entrega": ""}
        if faltan:
            nombres = ", ".join(campos[f] for f in faltan)
            esc["estado"], esc["detalle"] = "FALTAN_DATOS", "Faltan: " + nombres
            log("WARN", "%s -> FALTAN_DATOS (%s)" % (ref, nombres))
        else:
            mats, centro, almacen, wm = vals["material"], vals["centro"], vals["alm_origen"], _si(vals["wm"])
            try:
                qty = float(str(vals["cantidad"]).replace(",", "."))
            except ValueError:
                qty = float(cantidad_global)
            sin_info = [m for m in mats if not backend.registro_info(m, centro, vals["org_compras"])]
            if sin_info:
                esc["estado"] = "SIN_REGISTRO_INFO"
                esc["detalle"] = "Falta registro info (ME11) en %s / org. compras %s para: %s" % (centro, vals["org_compras"], ", ".join(sin_info))
                log("WARN", "%s -> %s" % (ref, esc["detalle"]))
            else:
                items, sin_stock, parcial = [], [], False
                prop = (propuestas or {}).get(e["clave"], {}) if fuentes.get("cantidad") == "global" else {}
                for m in mats:
                    st = backend.stock_origen(m, centro, almacen, wm)
                    lineas = sorted([l for l in st["lineas"] if l["qty"] > 0], key=engine._orden)
                    lote_sel = vals.get("lote", "") if (len(mats) == 1 and not backend.simulado and "," not in vals.get("lote", "")) else ""
                    if lote_sel:                                       # lote fijado por el usuario
                        lineas = [l for l in lineas if l["lote"] == lote_sel]
                    log("INFO", "%s stock %s %s/%s [%s]: %s" % (ref, m, centro, almacen, st["fuente"], sum(l["qty"] for l in lineas)))
                    pend = float(prop.get(m, qty))
                    for l in lineas:
                        if pend <= 0:
                            break
                        q = min(pend, l["qty"])
                        items.append({"material": m, "lote": l["lote"], "cantidad": q, "fuente": st["fuente"]})
                        pend -= q
                    if not lineas:
                        sin_stock.append(m)
                    elif pend > 0:
                        parcial = True
                if not items:
                    esc["estado"], esc["detalle"] = "SIN_STOCK", "Sin stock libre en %s/%s para: %s" % (centro, almacen, ", ".join(sin_stock))
                else:
                    sto = backend.crear_sto(e["mov"], centro, vals["centro_destino"], vals["org_compras"], vals["sociedad"], items)
                    ent = backend.crear_entrega(sto, items)
                    esc["sto"], esc["entrega"] = sto, ent
                    esc["estado"] = "PARCIAL" if (sin_stock or parcial) else "OK"
                    esc["detalle"] = "cantidad %s (%s)%s%s" % (qty, fuentes.get("cantidad", ""), " · cantidad propuesta desde stock y confirmada" if prop else "",
                                                                (" · sin stock: " + ", ".join(sin_stock)) if sin_stock else "")
                    for it in items:
                        base = {**t, "escenario": e["escenario"], "tipo": e["mov"], "centro_suministrador": centro, "alm_suministrador": almacen,
                                "wm": "S" if wm else "N", "centro_receptor": vals["centro_destino"], "alm_receptor": vals.get("alm_destino", ""),
                                "material": it["material"], "lote": it["lote"] or "sin lote", "cantidad": it["cantidad"]}
                        out["sto"].append({**base, "sto": sto, "org_compras": vals["org_compras"], "grupo_compras": vals["grupo_compras"],
                                           "sociedad": vals["sociedad"], "registro_info": "OK",
                                           "fuente_stock": it["fuente"]})
                        out["entregas"].append({**base, "entrega": ent, "sto": sto})
        resumen[esc["estado"]] += 1
        out["escenarios"].append(esc)
        for p in e["pasos"]:
            out["pasos"].append({**t, "escenario": e["escenario"], "paso": p["paso"], "fase": p["fase"], "transacciones": " / ".join(p["transacciones"]),
                                 "equipo": ", ".join(c for c in p["categorias"] if c in ("FI", "CO", "ML", "MM")) or "otro",
                                 "descripcion": p["descripcion"], "esperado": p["esperado"]})
    return out, resumen
