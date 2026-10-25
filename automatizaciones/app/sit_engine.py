"""Ejecución de escenarios SIT con MIGO en el paso 1 y paquete de validación para MM/FI/CO/ML.

Todos los datos de salida llevan JIRA ID e ID por unidad para trazabilidad.
En modo simulado los apuntes FI/CO/ML son inventados con el formato definitivo.
"""
import engine

HEAD = ["Tipo movimiento", "Material", "Centro", "Almacén origen", "Cantidad", "UM", "Lote"]
TRAZA = ("jira_id", "id_jira_unidad", "new_id", "unidad")


def _traza(e):
    return {k: e.get(k, "") for k in TRAZA}


def ejecutar(catalogo_sel, backend, log, cantidad_defecto=1):
    out = {"escenarios": [], "mm": [], "fi": [], "co": [], "ml": [], "pasos": []}
    resumen = {"OK": 0, "PARCIAL": 0, "SIN_STOCK": 0, "ERROR": 0, "SIN_DATOS": 0}
    for e in catalogo_sel:
        t = _traza(e)
        d = e["datos"]
        ref = "%s / %s" % (e["jira_id"], e["id_jira_unidad"])
        esc = {**t, "escenario": e["escenario"], "mov": e["mov"], "estado": "", "detalle": "", "filas": []}
        if not d["materiales"] or not d["plantas"]:
            falta = " y ".join(x for x, v in (("material", d["materiales"]), ("centro", d["plantas"])) if not v)
            esc["estado"], esc["detalle"] = "SIN_DATOS", "El Excel no indica %s en el paso 1" % falta
            resumen["SIN_DATOS"] += 1
            log("WARN", "%s -> SIN_DATOS (%s)" % (ref, falta))
        else:
            try:
                qty = float(str(d["cantidad"]).replace(",", ".").split()[0]) if d["cantidad"] else cantidad_defecto
            except ValueError:
                qty = cantidad_defecto
            nota_qty = "" if d["cantidad"] else "cantidad por defecto %s" % cantidad_defecto
            rows = [{"Tipo movimiento": e["mov"], "Material": m, "Centro": d["plantas"][0], "Almacén origen": d["alm"],
                     "Cantidad": str(qty), "UM": "", "Lote": ""} for m in d["materiales"]]
            res, rs = engine.run(HEAD, rows, backend, log)
            estados = [r["estado"] for r in res]
            for r in res:
                resumen[r["estado"]] += 1
                esc["filas"].append(r)
                out["mm"].append({**t, "escenario": e["escenario"], "mov": e["mov"], "material": r["material"], "centro": r["centro"],
                                  "almacen": r["almacen"], "pedida": r["pedida"], "movida": r["movida"], "estado": r["estado"],
                                  "detalle": r["detalle"], "nota": nota_qty,
                                  "documentos": "; ".join("%s (%s×%s)" % (x["doc"], x["lote"] or "sin lote", x["cantidad"]) for x in r["documentos"])})
                for doc in r["documentos"]:
                    for fn, key in ((backend.apuntes_fi, "fi"), (backend.apuntes_co, "co"), (backend.datos_ml, "ml")):
                        for line in fn(doc["doc"], r["material"], r["centro"], doc["cantidad"]):
                            out[key].append({**t, "escenario": e["escenario"], "mov": e["mov"], "doc_material": doc["doc"], **line})
            esc["estado"] = "OK" if all(s == "OK" for s in estados) else ("ERROR" if "ERROR" in estados else
                            ("SIN_STOCK" if all(s == "SIN_STOCK" for s in estados) else "PARCIAL"))
            if nota_qty:
                esc["detalle"] = nota_qty
        if e.get("requiere_doc_previo"):
            esc["detalle"] = (esc["detalle"] + " · requiere documento previo (PO/orden)").strip(" ·")
        for p in e["pasos"]:
            out["pasos"].append({**t, "escenario": e["escenario"], "paso": p["paso"], "transacciones": " / ".join(p["transacciones"]),
                                 "equipo": ", ".join(c for c in p["categorias"] if c in ("FI", "CO", "ML", "MM")) or "otro",
                                 "descripcion": p["descripcion"], "esperado": p["esperado"]})
        out["escenarios"].append(esc)
    return out, resumen
