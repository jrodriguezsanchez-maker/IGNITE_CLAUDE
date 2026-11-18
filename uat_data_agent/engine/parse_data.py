"""Lector del campo Data y clasificación de casos (adaptado de engine/reference/parse.py, sin rutas fijas)."""
import re
from collections import defaultdict

NORM = {
 'plant': 'Plant', 'plant 1': 'Plant', 'plant 2': 'Plant2', 'plant  3': 'Plant3', 'destination plant': 'DestPlant',
 'source plant': 'SupPlant', 'supplier plant': 'SupPlant', 'sup. plant': 'SupPlant',
 'c.code': 'CCode', 'company code': 'CCode',
 'p.org': 'POrg', 'purchase org': 'POrg', 'purchase': 'POrg', 's.org': 'SOrg', 'sales org': 'SOrg',
 'doc type': 'DocType', 'doc type 1': 'DocType', 'doc type 2': 'DocType', 'purchase order type': 'DocType',
 'planned order type': 'DocType', 'notification type': 'DocType', 'functional location doc type': 'DocType',
 'mov.type': 'MovType', 'mov type': 'MovType', 'movement type': 'MovType', 'mov. type': 'MovType',
 'st.loc': 'SLoc', 'st-loc ini': 'SLoc', 'st.loc fin': 'SLoc', 'storage location': 'SLoc',
 'bp': 'BP', 'bp - customer': 'Customer', 'bp - vendor': 'Vendor', 'vendor': 'Vendor', 'supplier': 'Vendor',
 'bp role': 'BPRole', 'transportation planning point': 'TPP', 'shipment type': 'ShipType',
 'sp.point': 'ShipPoint', 'shipping point': 'ShipPoint', 'equipment': 'Equipment', 'functional location': 'FuncLoc',
}


def norm_label(label):
    l = label.strip().lower()
    if l.startswith('material') or l in ('materia', 'materials', 'new material'):
        return 'Material'
    if '-> bp' in l:
        return 'BP'
    return NORM.get(l, 'OTHER:' + l)


# «Prev.Data» al principio del Data = paso de chequeo: no mete datos, usa los transaccionales generados en pasos anteriores. Admite descripción entre paréntesis
# («Prev.Data (purchase order)») y, detrás de una coma, más datos normales («Prev.Data (purchase order), Material: 123»).
PREV_RE = re.compile(r'^\s*prev\.?\s*data\b(?:\s*\([^)]*\))?(?:\s*,\s*\([^)]*\))*\s*[,;]?\s*', re.I)


def prev_data(text):
    """(prefijo, descripciones, resto). Si el Data no empieza por «Prev.Data»: ('', [], text)."""
    if not isinstance(text, str):
        return '', [], text
    m = PREV_RE.match(text)
    if not m:
        return '', [], text
    return m.group(0), [x.strip() for x in re.findall(r'\(([^)]*)\)', m.group(0)) if x.strip()], text[m.end():]


def parse(v):
    d = defaultdict(list)
    if not isinstance(v, str):
        return d
    pref, descs, v = prev_data(v)
    if pref:
        d['PrevData'].append(', '.join(descs) or '(sin descripción)')
    cur = None
    for line in v.split('\n'):
        s = line.strip()
        if not s:
            continue
        if re.match(r'(?i)^prev\.?\s*data\b', s):            # línea suelta «Prev.Data (…)»: datos de pasos anteriores, no un valor de la etiqueta de arriba
            d['PrevData'].append(', '.join(re.findall(r'\(([^)]*)\)', s)) or '(sin descripción)')
            continue
        if re.fullmatch(r'-{3,}', s):
            cur = None
            continue
        m = re.match(r'([^:]{1,40}):(.*)', s)
        if m and not re.match(r'^\d', m.group(1).strip()):
            cur = norm_label(m.group(1))
            val = m.group(2).strip()
            if val:
                d[cur].append(val)
        elif cur:
            d[cur].append(s)
        else:
            d['FREE'].append(s)
    return d


def plants_in(values, known=None):
    """Plantas citadas. Con `known` (Org.Structure) admite también las numéricas (0010)."""
    out = set()
    for v in values:
        for t in re.findall(r'\b([A-Z0-9]{4})\b', v.upper()):
            if (known and t in known) or (not known and re.fullmatch(r'[CLMS]\d{3}', t)):
                out.add(t)
    return sorted(out)


# --- clasificación por transacciones (de engine/reference/profile.py) ---
FLAGS = [
    ('pm', r'\b(IW\d\d|IH01|IE0\d|IL0\d|IP\d\d|IA05|PM FIORI|ZPM\w*)\b'),
    ('qm', r'\b(QA32|QE51N|QA01|QM01|QM02|QE11|QI01|QP01|QP02|QP60|QS23|QS33|ZQM\w*)\b'),
    ('pp', r'\b(MFBF|MD61|MD11|MD12|CO11N|CO01|MF50|MF12|MF42N|COOIS|CK11N|CK24|CS01|C223|CA01|CA11|ZPP\w*)\b'),
    ('wm', r'\b(LT\d\d|LS\d\d|LI\d\dN?|LL01|LM\d\d|LX\d\d|ZWM\w*)\b'),
    ('transporte', r'\b(VT01N|VT02N|VI01|VI02|TK11|VT\d\dN?)\b'),
    ('venta', r'\b(VA01|VA02|VF01)\b'),
    ('compra', r'\b(ME21N|ME2[123]N|MIRO|ME61)\b'),
]
FLOW_DOCS = ['ZTRA', 'ZWIA', 'ZINT', 'ZINR', 'ZSPO', 'ZSPA', 'ZPO', 'ZSER']
VENTA_DOCS = {'ZAOR', 'ZBRE', 'ZBRN', 'ZAWI', 'ZGOS', 'ZADO', 'ZSSA', 'ZCCR'}


def classify(trans_text, l2, parsed_steps):
    """Devuelve (stream, flujo, clases_doc). Stream: PP | QM | PM | WM | LOG."""
    t = (trans_text or '').upper()
    fl = {k: bool(re.search(p, t)) for k, p in FLAGS}
    docs = set()
    for d in parsed_steps:
        docs |= set(re.findall(r'\b(Z[A-Z0-9]{2,4})\b', ' '.join(d.get('DocType', []))))
    l2 = str(l2 or '')
    by_l2 = {'5.1': 'PP', '5.2': 'QM', '5.3': 'PM', '5.4': 'WM', '5.5': 'LOG', '5.6': 'LOG'}.get(l2[:3])
    if by_l2:
        stream = by_l2
    elif fl['pm']:
        stream = 'PM'
    elif fl['qm']:
        stream = 'QM'
    elif fl['pp']:
        stream = 'PP'
    elif fl['wm']:
        stream = 'WM'
    else:
        stream = 'LOG'
    flow = next((f for f in FLOW_DOCS if f in docs), None)
    if not flow and (docs & VENTA_DOCS or fl['venta']):
        flow = 'VENTA'
    if not flow and fl['transporte']:
        flow = 'TRANSPORTE'
    if not flow and fl['compra']:
        flow = 'ZPO'
    return stream, flow, sorted(docs)
