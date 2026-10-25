"""Importador del Excel SIT (Jira): extrae los escenarios cuyo paso 1 es una MIGO.

Lee la hoja SCRIPTS (una fila por paso). Un escenario = External ID - JIRA (ID por unidad);
si falta, New ID + unidad. Ignora EDI/IDoc: de "MIGO || EDI ..." solo se conserva la parte SAP.
El catálogo resultante contiene datos de cliente: se guarda en data/ (fuera de git).
"""
import json
import re
from collections import OrderedDict
from pathlib import Path

from xlsx_reader import read_xlsx

CATEGORIAS = {
    "FI": {"FB03", "FAGLL03", "FBL3N", "FBL1N", "FBL5N", "FS10N", "FAGLB03", "F0956", "FB01", "FTXP", "FAGL_FCV"},
    "CO": {"KE24", "KE5Z", "KSB1", "CJI3", "KOB1", "KE21N", "KE30", "KKBC_ORD", "KKS1", "CO03"},
    "ML": {"CKM3N", "CKM3", "CKMLCP", "CKMLQS", "CKMLCT", "CKMLHD", "CKMLPP", "CKM1"},
    "MM": {"MIGO", "MMBE", "MB51", "MB52", "MB5B", "MSC3N", "MIRO", "MFBF", "QA32", "LT01", "LT06", "LT12", "LT22", "LT0A"},
}
COD = re.compile(r"\b[A-Z][A-Z0-9_]{2,9}\b")


def _s(v):
    return str(v or "").strip()


STOP = {"VALIDAR", "VALIDATE", "SOURCE", "TRANSACTION", "EDI", "IDOC"}


def clean_transaction(txt):
    """Devuelve la lista de transacciones SAP del paso (p. ej. 'KE24 / CKM3N (validar)').
    Descarta cualquier mención a EDI/IDoc; si el paso es solo EDI devuelve ['EDI']."""
    lines = [l.strip() for l in re.split(r"\n|\|\|", _s(txt)) if l.strip()]
    sap = [l for l in lines if not re.search(r"edi|idoc", l, re.I)]
    if not sap:
        return ["EDI"]
    codes = []
    for l in sap:
        for tok in re.split(r"[/,;]+", l):
            m = re.match(r"^\s*([A-Z][A-Z0-9_]{2,9})(?![A-Za-z0-9_])", tok)
            if m and m.group(1) not in STOP and m.group(1) not in codes:
                codes.append(m.group(1))
    return codes or ["OTRO"]


def categoria(codigo):
    if codigo == "EDI":
        return "EDI"
    for cat, s in CATEGORIAS.items():
        if codigo in s:
            return cat
    return "OTRO"


def parse_data(txt):
    out = {"plantas": [], "plantas_destino": [], "materiales": [], "movs": [], "alm": "", "cantidad": "", "po": ""}
    last = None
    for raw in _s(txt).split("\n"):
        line = raw.strip()
        if not line or set(line) <= {"-"}:
            continue
        m = re.match(r"^([A-Za-z][A-Za-z\.\(\) /]*?)\s*:\s*(.*)$", line)
        if m:
            label, val = m.group(1).strip().lower(), m.group(2)
            last = None
            if "plant" in label and "supplier" not in label:
                key = "plantas_destino" if "dest" in label else "plantas"
                out[key] += re.findall(r"\b[A-Z]\d{3}\b", val)
            elif label.startswith("material") or label in ("zraw", "zfin", "zsem", "zpac", "zfor"):
                out["materiales"] += re.findall(r"\b\d{5,}\b", val)
                last = "materiales"
            elif "mov" in label and ("type" in label or "id" in label):
                out["movs"] += re.findall(r"\b(?:\d{3}|Z\d{2})\b", val)
            elif "st.loc" in label or "storage" in label:
                out["alm"] = (out["alm"] + " " + val).strip()[:60]
            elif label == "qty":
                out["cantidad"] = val.strip()[:30]
            elif label.startswith("po"):
                out["po"] = val.strip()[:40]
        elif last == "materiales":
            out["materiales"] += re.findall(r"\b\d{5,}\b", line)
    for k in ("plantas", "plantas_destino", "materiales", "movs"):
        out[k] = list(OrderedDict.fromkeys(out[k]))
    return out


def _etq(label):
    return re.sub(r"[^a-z0-9]+", " ", label.lower()).strip()


def interpretar(txt):
    """Interpreta el campo Data del paso 1 en campos SAP separados (origen y destino distintos).
    Etiquetas reconocidas: Plant/Source Plant, Destination Plant, Sup. Plant, St-Loc Ini/St.Loc fin/Storage location,
    Material*, Qty, Vendor/Supplier, Cost center, Order, PO No., Batch, Reason."""
    r = {"centro": "", "centro_destino": "", "centro_suministrador": "", "alm_origen": "", "alm_destino": "", "materiales": [],
         "cantidad": "", "vendor": "", "ceco": "", "orden": "", "po": "", "lote": "", "motivo": ""}
    last = None
    for raw in _s(txt).split("\n"):
        line = raw.strip()
        if not line or set(line) <= {"-"}:
            continue
        m = re.match(r"^([A-Za-z][A-Za-z0-9\.\-\(\) /]*?)\s*:\s*(.*)$", line)
        if not m:
            if last == "materiales":
                r["materiales"] += re.findall(r"\b\d{5,}\b", line)
            continue
        et, val = _etq(m.group(1)), m.group(2).strip()
        last = None
        centro = (re.findall(r"\b[A-Z]\d{3}\b", val) or [""])[0]
        sloc = (re.findall(r"\b[A-Z0-9]{4}\b", val) or [""])[0]
        if et in ("plant", "source plant", "plants"):
            r["centro"] = r["centro"] or centro
        elif et in ("destination plant", "dest plant", "receiving plant", "target plant"):
            r["centro_destino"] = r["centro_destino"] or centro
        elif et in ("sup plant", "supplier plant", "supplying plant"):
            r["centro_suministrador"] = r["centro_suministrador"] or centro
        elif et in ("st loc ini", "storage location", "st loc", "source storage location", "sloc"):
            r["alm_origen"] = r["alm_origen"] or sloc
        elif et in ("st loc fin", "destination storage location", "dest storage location"):
            r["alm_destino"] = r["alm_destino"] or sloc
        elif et.startswith("material") or et in ("zraw", "zfin", "zsem", "zpac", "zfor"):
            r["materiales"] += re.findall(r"\b\d{5,}\b", val)
            last = "materiales"
        elif et in ("qty", "quantity", "cantidad"):
            r["cantidad"] = val[:20]
        elif et in ("vendor", "supplier", "lifnr", "proveedor", "vendor number"):
            r["vendor"] = val[:20]
        elif et in ("cost center", "cost centre", "ceco", "cc", "kostl"):
            r["ceco"] = val[:20]
        elif et in ("order", "production order", "work order", "order no", "aufnr"):
            r["orden"] = val[:20]
        elif et in ("po no", "po", "purchase order", "po number"):
            r["po"] = val[:20]
        elif et in ("batch", "lote", "charg"):
            r["lote"] = val[:20]
        elif et in ("reason", "motivo", "movement reason"):
            r["motivo"] = val[:20]
    r["materiales"] = list(OrderedDict.fromkeys(r["materiales"]))
    return r


def resolver(e, mov, req_cfg, defaults, cantidad_global):
    """Valores finales de un escenario y qué campos faltan para su movimiento.
    Prioridad: aportado por el usuario > Excel > derivado/valor por centro > cantidad global."""
    req = req_cfg["movimientos"].get(mov) or req_cfg["generico"]
    i, a = e["interpretado"], e.get("aportados") or {}
    d = (defaults or {}).get(a.get("centro") or i["centro"], {})
    vals, fuentes = {}, {}

    def poner(f, v, src):
        if v:
            vals[f], fuentes[f] = v, src
            return True
        return False

    for f in req_cfg["campos"]:
        if f == "material":
            mats = [x for x in re.split(r"[,\s;]+", a.get("material", "")) if x] or i["materiales"]
            poner(f, mats, "aportado" if a.get("material") else "excel")
            continue
        if poner(f, a.get(f), "aportado") or poner(f, i.get(f), "excel"):
            continue
        if f == "centro_destino" and vals.get("centro") and req_cfg.get("derivar_centro_destino", True):
            poner(f, vals["centro"], "= origen")
        elif f == "alm_destino" and req.get("alm_destino_igual_origen") and vals.get("alm_origen"):
            poner(f, vals["alm_origen"], "= origen")
        elif not poner(f, d.get(f), "centro") and f == "cantidad":
            poner(f, str(cantidad_global), "global")
    faltan = [f for f in req["requiere"] if not vals.get(f)]
    return vals, fuentes, faltan, req


def load_rules(rules_path):
    cfg = json.loads(Path(rules_path).read_text(encoding="utf-8"))
    return [(re.compile(r["patron"], re.I), r) for r in cfg["reglas"]], [re.compile(p, re.I) for p in cfg["marcadores_documento_previo"]]


def proponer_mov(texto, reglas):
    for rx, r in reglas:
        if rx.search(texto):
            return r["mov"], r.get("nota", ""), bool(r.get("requiere_doc"))
    return "", "Sin regla: indícalo tú", False


def _pasa_filtro(fila, filtro):
    """filtro = {"L1": "5.SCM", "L2": ["5.6 Logistics Flows"]}; sin filtro entra todo."""
    for col, vals in (filtro or {}).items():
        vals = [vals] if isinstance(vals, str) else vals
        if _s(fila.get(col)) not in vals:
            return False
    return True


def importar(xlsx_path, rules_path, filtro=None):
    """Devuelve (catalogo, stats). stats: escenarios con MIGO totales, incluidos y excluidos por L1/L2."""
    reglas, marcadores = load_rules(rules_path)
    cabeceras, rows = read_xlsx(xlsx_path, "SCRIPTS")
    stats = {"total_migo": 0, "incluidos": 0, "excluidos": {}, "filtro": filtro or {}, "columnas": cabeceras}
    grupos = OrderedDict()
    for r in rows:
        nid = _s(r.get("New ID"))
        if not nid:
            continue
        unit = _s(r.get("Location by Unit"))
        clave = _s(r.get("External ID - JIRA")) or "%s|%s" % (nid, unit)
        grupos.setdefault(clave, []).append(r)

    def paso(r):
        try:
            return int(float(r.get("Step") or 0))
        except ValueError:
            return 0

    catalogo = []
    for clave, filas in grupos.items():
        filas.sort(key=paso)
        p1 = filas[0]
        if "MIGO" not in clean_transaction(p1.get("Transaction")):
            continue
        stats["total_migo"] += 1
        if not _pasa_filtro(p1, filtro):
            k = "%s / %s" % (_s(p1.get("L1")), _s(p1.get("L2")))
            stats["excluidos"][k] = stats["excluidos"].get(k, 0) + 1
            continue
        stats["incluidos"] += 1
        datos = parse_data(p1.get("Data"))
        texto = " ".join([_s(p1.get("Test Step Description")), _s(p1.get("Data"))]).lower()
        mov, nota, req = proponer_mov(texto, reglas)
        previo = req or any(m.search(texto + " " + _s(p1.get("Pre-requeriment")).lower()) for m in marcadores)
        explicitos = datos["movs"]
        pasos = []
        for f in filas[1:]:
            cs = clean_transaction(f.get("Transaction"))
            pasos.append({"paso": paso(f), "transacciones": cs, "categorias": sorted({categoria(c) for c in cs}),
                          "descripcion": _s(f.get("Test Step Description"))[:400], "esperado": _s(f.get("Expected result"))[:400]})
        catalogo.append({
            "clave": clave,
            "jira_id": _s(p1.get("JIRA ID")),            # IG-xxxx
            "id_jira_unidad": _s(p1.get("External ID - JIRA")),   # ID by unit
            "new_id": _s(p1.get("New ID")),
            "l1": _s(p1.get("L1")), "l2": _s(p1.get("L2")), "l3": _s(p1.get("L3")),
            "unidad": _s(p1.get("Location by Unit")),
            "escenario": _s(p1.get("Test Scenario"))[:200],
            "descripcion_paso1": _s(p1.get("Test Step Description"))[:300],
            "datos": datos,
            "interpretado": interpretar(p1.get("Data")),
            "aportados": {},       # valores que da el usuario (CECO, vendor, cantidad…); se guardan solo en data/
            "previo": _s(p1.get("Pre-requeriment"))[:200],
            "requiere_doc_previo": previo,
            "movs_candidatos": explicitos or ([mov] if mov else []),
            "mov_origen": "explícito en el Excel" if explicitos else ("regla local" if mov else "sin propuesta"),
            "mov_nota": "" if explicitos else nota,
            "mov": "",             # lo fija el usuario al confirmar
            "confirmado": False,
            "pasos": pasos,
            "fila1": {k: _s(v)[:1500] for k, v in p1.items()},   # paso 1 con las columnas originales del Excel
        })
    return catalogo, stats
