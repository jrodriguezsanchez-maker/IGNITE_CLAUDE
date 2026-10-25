"""Ejecución de escenarios SIT con MIGO en el paso 1 y paquete de validación para MM/FI/CO/ML.

Antes de mover nada se resuelve el Data del Excel (+ datos aportados por el usuario + valores por centro)
y se comprueba que estén todos los campos que SAP exige para ese movimiento (requisitos_movimiento.json).
Todas las salidas llevan JIRA ID e ID por unidad para trazabilidad.
En modo simulado los apuntes FI/CO/ML son inventados con el formato definitivo.
"""
import engine
import sit_import

HEAD = ["Tipo movimiento", "Material", "Centro", "Almacén origen", "Cantidad", "UM", "Lote", "Centro destino", "Almacén destino",
        "Vendor", "CECO", "Orden", "PO", "Motivo"]
TRAZA = ("jira_id", "id_jira_unidad", "new_id", "unidad")
ESTADOS = ("OK", "PARCIAL", "SIN_STOCK", "ERROR", "FALTAN_DATOS", "NO_SOPORTADO")


def _traza(e):
    return {k: e.get(k, "") for k in TRAZA}


def ejecutar(catalogo_sel, backend, log, cantidad_global, req_cfg, defaults, propuestas=None):
    out = {"escenarios": [], "mm": [], "fi": [], "co": [], "ml": [], "pasos": []}
    resumen = {k: 0 for k in ESTADOS}
    campos = req_cfg["campos"]
    for e in catalogo_sel:
        t = _traza(e)
        ref = "%s / %s" % (e["jira_id"], e["id_jira_unidad"])
        vals, fuentes, faltan, req = sit_import.resolver(e, e["mov"], req_cfg, defaults, cantidad_global)
        esc = {**t, "escenario": e["escenario"], "mov": e["mov"], "estado": "", "detalle": "", "filas": []}
        if req.get("transaccion"):
            esc["estado"], esc["detalle"] = "NO_SOPORTADO", "El movimiento %s no se hace con MIGO: %s" % (e["mov"], req.get("nota", ""))
            resumen["NO_SOPORTADO"] += 1
            log("WARN", "%s -> NO_SOPORTADO (%s)" % (ref, req["transaccion"]))
        elif faltan:
            nombres = ", ".join(campos[f] for f in faltan)
            esc["estado"], esc["detalle"] = "FALTAN_DATOS", "Faltan: " + nombres
            resumen["FALTAN_DATOS"] += 1
            log("WARN", "%s -> FALTAN_DATOS (%s)" % (ref, nombres))
        else:
            qty = vals["cantidad"]
            try:
                float(str(qty).replace(",", "."))
            except ValueError:
                qty = cantidad_global
            fila = {"Tipo movimiento": e["mov"], "Centro": vals["centro"], "Almacén origen": vals.get("alm_origen", ""), "Cantidad": str(qty),
                    "UM": "", "Lote": "", "Centro destino": vals.get("centro_destino", ""), "Almacén destino": vals.get("alm_destino", ""),
                    "Vendor": vals.get("vendor", ""), "CECO": vals.get("ceco", ""), "Orden": vals.get("orden", ""),
                    "PO": vals.get("po", ""), "Motivo": vals.get("motivo", "")}
            prop = (propuestas or {}).get(e["clave"], {}) if fuentes.get("cantidad") == "global" else {}
            lote_sel = vals.get("lote", "") if (len(vals["material"]) == 1 and not backend.simulado and "," not in vals.get("lote", "")) else ""
            rows = [{**fila, "Material": m, "Cantidad": str(prop.get(m, qty)), "Lote": lote_sel} for m in vals["material"]]
            res, _ = engine.run(HEAD, rows, backend, log)
            estados = [r["estado"] for r in res]
            nota = "cantidad %s (%s)" % (qty, fuentes.get("cantidad", "")) + (" · cantidad propuesta desde stock y confirmada" if prop else "")
            for r in res:
                resumen[r["estado"]] += 1
                esc["filas"].append(r)
                out["mm"].append({**t, "escenario": e["escenario"], "mov": e["mov"], "material": r["material"], "centro": r["centro"],
                                  "almacen": r["almacen"], "centro_destino": vals.get("centro_destino", ""), "alm_destino": vals.get("alm_destino", ""),
                                  "vendor": vals.get("vendor", ""), "ceco": vals.get("ceco", ""), "orden": vals.get("orden", ""),
                                  "pedida": r["pedida"], "movida": r["movida"], "estado": r["estado"], "detalle": r["detalle"], "nota": nota,
                                  "documentos": "; ".join("%s (%s×%s)" % (x["doc"], x["lote"] or "sin lote", x["cantidad"]) for x in r["documentos"])})
                for doc in r["documentos"]:
                    for fn, key in ((backend.apuntes_fi, "fi"), (backend.apuntes_co, "co"), (backend.datos_ml, "ml")):
                        for line in fn(doc["doc"], r["material"], r["centro"], doc["cantidad"]):
                            out[key].append({**t, "escenario": e["escenario"], "mov": e["mov"], "doc_material": doc["doc"], **line})
            esc["estado"] = "OK" if all(s == "OK" for s in estados) else ("ERROR" if "ERROR" in estados else
                            ("SIN_STOCK" if all(s == "SIN_STOCK" for s in estados) else "PARCIAL"))
            esc["detalle"] = nota
        if e.get("requiere_doc_previo"):
            esc["detalle"] = (esc["detalle"] + " · requiere documento previo (PO/orden)").strip(" ·")
        for p in e["pasos"]:
            out["pasos"].append({**t, "escenario": e["escenario"], "paso": p["paso"], "transacciones": " / ".join(p["transacciones"]),
                                 "equipo": ", ".join(c for c in p["categorias"] if c in ("FI", "CO", "ML", "MM")) or "otro",
                                 "descripcion": p["descripcion"], "esperado": p["esperado"]})
        out["escenarios"].append(esc)
    return out, resumen
