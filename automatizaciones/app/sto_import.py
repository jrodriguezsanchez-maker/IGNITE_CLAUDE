"""Importador de escenarios SIT con un paso ME21N y tipo de documento ZTRA / ZINT / ZWIA (pedidos de traslado).

Un escenario = External ID - JIRA (ID por unidad). Entra si algún paso es ME21N y el tipo aparece en la descripción
o en el Data de ese paso (o, si no, en otro paso del escenario). El catálogo contiene datos de cliente: va a data/ (fuera de git).
"""
import re
from collections import OrderedDict

from sit_import import _etq, _s, categoria, clean_transaction
from xlsx_reader import read_xlsx

TIPOS = ("ZTRA", "ZINT", "ZWIA")
ENTREGA = {"VL01N", "VL10B", "VL10G", "VL10D", "VL01NO"}
TIPO_RX = re.compile(r"Z(?:TRA|INT|WIA)")


def interpretar_sto(txt):
    """Data del paso ME21N -> campos del pedido de traslado (centro suministrador y receptor distintos)."""
    r = {"centro": "", "centro_destino": "", "alm_origen": "", "alm_destino": "", "materiales": [], "cantidad": "", "org_compras": "",
         "grupo_compras": "", "sociedad": "", "org_ventas": "", "vendor": "", "incoterms": "", "tipo_doc": "", "wm": ""}
    last = None
    for raw in _s(txt).split("\n"):
        line = raw.strip()
        if not line or set(line) <= {"-"}:
            continue
        m = re.match(r"^([A-Za-z][A-Za-z0-9\.\-\(\) /]*?)\s*:\s*(.*)$", line)
        if not m:
            if last == "materiales" and not re.search(r"[A-Za-z]{3}", line):
                r["materiales"] += re.findall(r"\b\d{5,}\b", line)
            continue
        et, val = _etq(m.group(1)), m.group(2).strip()
        last = None
        centros = re.findall(r"\b[A-Z]\d{3}\b", val)
        if et in ("supplier plant", "sup plant", "source plant", "supplying plant", "plant 1"):
            r["centro"] = r["centro"] or (centros[0] if centros else "")
        elif et in ("plant", "plants"):
            if len(centros) >= 2:      # cadena L035 -> L048 -> M021: primer salto
                r["centro"], r["centro_destino"] = r["centro"] or centros[0], r["centro_destino"] or centros[1]
            elif centros:
                r["centro_destino"] = r["centro_destino"] or centros[0]
        elif et in ("plant 2", "destination plant", "dest plant", "receiving plant"):
            r["centro_destino"] = r["centro_destino"] or (centros[0] if centros else "")
        elif et in ("p org", "purchasing org", "purchasing organization"):
            r["org_compras"] = val[:8]
        elif et in ("p grp", "purchasing group", "p group"):
            r["grupo_compras"] = val[:8]
        elif et in ("c code", "company code"):
            r["sociedad"] = val[:8]
        elif et in ("s org", "sales org", "sales organization"):
            r["org_ventas"] = val[:8]
        elif et in ("st loc", "storage location", "receiving storage location"):
            r["alm_destino"] = (re.findall(r"\b[A-Z0-9]{4}\b", val) or [""])[0]
        elif et in ("source storage location", "supplying storage location"):
            r["alm_origen"] = (re.findall(r"\b[A-Z0-9]{4}\b", val) or [""])[0]
        elif et in ("bp", "bp vendor", "vendor", "supplier", "business partner"):
            r["vendor"] = val[:20]
        elif et == "incoterms":
            r["incoterms"] = val[:10]
        elif et in ("qty", "quantity", "cantidad"):
            r["cantidad"] = val[:20]
        elif et.startswith("doc type") or et == "purchase":
            r["tipo_doc"] = (r["tipo_doc"] + " " + val).strip()[:60]
        elif et.startswith("material") or et in ("zraw", "zfin", "zsem", "zpac", "zfor"):
            r["materiales"] += re.findall(r"\b\d{5,}\b", val)
            last = "materiales"
    r["materiales"] = list(OrderedDict.fromkeys(r["materiales"]))
    return r


def importar_sto(xlsx_path, filtro=None):
    cabeceras, rows = read_xlsx(xlsx_path, "SCRIPTS")
    stats = {"incluidos": 0, "excluidos": {}, "filtro": filtro or {}, "columnas": cabeceras}
    grupos = OrderedDict()
    for r in rows:
        nid = _s(r.get("New ID"))
        if nid:
            clave = _s(r.get("External ID - JIRA")) or "%s|%s" % (nid, _s(r.get("Location by Unit")))
            grupos.setdefault(clave, []).append(r)

    def paso(r):
        try:
            return int(float(r.get("Step") or 0))
        except ValueError:
            return 0

    def fuera(motivo):
        stats["excluidos"][motivo] = stats["excluidos"].get(motivo, 0) + 1

    cat = []
    for clave, filas in grupos.items():
        filas.sort(key=paso)
        me = [f for f in filas if "ME21N" in clean_transaction(f.get("Transaction"))]
        if not me:
            continue
        prim = me[0]
        texto_me = " ".join(_s(f.get("Data")) + " " + _s(f.get("Test Step Description")) for f in me)
        tipos = list(OrderedDict.fromkeys(TIPO_RX.findall(texto_me)))
        origen = "paso ME21N"
        if not tipos:
            texto_esc = " ".join(_s(f.get("Data")) + " " + _s(f.get("Test Step Description")) + " " + _s(f.get("Test Scenario")) for f in filas)
            tipos = list(OrderedDict.fromkeys(TIPO_RX.findall(texto_esc)))
            origen = "otro paso del escenario"
        if not tipos:
            fuera("ME21N sin ZTRA/ZINT/ZWIA")
            continue
        if filtro and any(_s(prim.get(c)) not in ([v] if isinstance(v, str) else v) for c, v in filtro.items()):
            fuera("%s / %s" % (_s(prim.get("L1")), _s(prim.get("L2"))))
            continue
        stats["incluidos"] += 1
        i_me = paso(prim)
        entrega_vista = False
        pasos = []
        for f in filas:
            cs = clean_transaction(f.get("Transaction"))
            if f is prim or ("ME21N" in cs and paso(f) >= i_me):
                fase = "sto"
            elif paso(f) < i_me:
                fase = "previo"
            elif not entrega_vista and ENTREGA & set(cs):
                fase, entrega_vista = "entrega", True
            else:
                fase = "posterior"
            pasos.append({"paso": paso(f), "transacciones": cs, "categorias": sorted({categoria(c) for c in cs}), "fase": fase,
                          "descripcion": _s(f.get("Test Step Description"))[:400], "esperado": _s(f.get("Expected result"))[:400]})
        d = interpretar_sto(prim.get("Data"))
        ambiguo = len(tipos) > 1
        cat.append({
            "clave": clave, "jira_id": _s(prim.get("JIRA ID")), "id_jira_unidad": _s(prim.get("External ID - JIRA")),
            "new_id": _s(prim.get("New ID")), "l1": _s(prim.get("L1")), "l2": _s(prim.get("L2")), "l3": _s(prim.get("L3")),
            "unidad": _s(prim.get("Location by Unit")), "escenario": _s(prim.get("Test Scenario"))[:200],
            "descripcion_paso1": _s(prim.get("Test Step Description"))[:300],
            "datos": {"materiales": d["materiales"], "plantas": [x for x in (d["centro"],) if x], "plantas_destino": [x for x in (d["centro_destino"],) if x],
                      "alm": d["alm_origen"], "cantidad": d["cantidad"], "movs": tipos, "po": ""},
            "interpretado": d, "aportados": {}, "previo": "", "requiere_doc_previo": False,
            "movs_candidatos": tipos, "mov_ambiguo": ambiguo,
            "mov_origen": ("varios tipos en el Excel (%s): elige uno" % ", ".join(tipos)) if ambiguo else "detectado en el %s" % origen,
            "mov_nota": "", "mov": "", "confirmado": False,
            "pasos": pasos, "fila1": {k: _s(v)[:1500] for k, v in prim.items()},
        })
    return cat, stats
