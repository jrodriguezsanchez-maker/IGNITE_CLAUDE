"""Casos encadenados: se parten en TRAMOS. Cada ME21N abre un tramo (compra o traspaso).
Un caso con un solo ME21N (o ninguno) no es una cadena y se trata como siempre."""
import re

from engine import parse_data

START = re.compile(r'\b(ME21N|ME21|ME27)\b', re.I)
AUTO_STO = re.compile(r'automatic creation.*(stock transfer|\bsto\b)|(stock transfer|\bsto\b).*automatic creation', re.I)      # compra que genera sola el traslado (ME22N «Check the Automatic creation - Stock Transfer Order»)
TRANSFER_DOCS = {'ZTRA', 'ZWIA', 'ZINT', 'ZINR'}
BUY_DOCS = {'ZPO', 'ZSPO', 'ZSPA', 'ZSER'}
PLANT_SLOC = re.compile(r'\b([CLMS]\d{3}|\d{4})\s*\((\w{1,4})\)')


def plant_sloc(values, known=None):
    """'L031 (1000)' -> [('L031', '1000')]; sin paréntesis -> [('L031', '')]."""
    out = []
    for v in values:
        for p, a in PLANT_SLOC.findall(v):
            if not known or p in known:
                out.append((p, a))
        for p in parse_data.plants_in([PLANT_SLOC.sub('', v)], known):
            if p not in [x[0] for x in out]:
                out.append((p, ''))
    return out


def _kind(desc, docs):
    d = (desc or '').lower()
    if re.search(r'transfer|sto\b', d):
        return 'TRASPASO'
    if re.search(r'purchase', d):
        return 'COMPRA'
    if docs & TRANSFER_DOCS:
        return 'TRASPASO'
    return 'COMPRA'


def detect(steps, known=None):
    """steps: filas del UAT de un caso. Devuelve [] si no es una cadena (menos de 2 ME21N)."""
    starts = [i for i, s in enumerate(steps) if START.search(str(s.get('Transaction', '')))]
    if starts:
        starts = sorted(set(starts) | {i for i, s in enumerate(steps) if i > starts[0] and AUTO_STO.search(str(s.get('Test Step Description', '')))})
    if len(starts) < 2:
        return []
    starts[0] = 0                       # lo anterior al primer ME21N cuelga del primer tramo
    out = []
    ntr = 0                             # traspasos ya vistos: «Plant 1, Plant 2, Plant 3» de la Data son los destinos de cada traspaso encadenado
    for n, a in enumerate(starts):
        b = starts[n + 1] if n + 1 < len(starts) else len(steps)
        first = steps[a if n else starts[0]]
        txt_ = first.get('Data', '')
        k_ = a if n else starts[0]
        while parse_data.prev_data(txt_)[0] and not parse_data.prev_data(txt_)[2].strip() and k_ > 0:      # «Prev.Data» sin datos propios: se usan los del último paso anterior que los tenga
            k_ -= 1
            txt_ = steps[k_].get('Data', '')
        parsed = parse_data.parse(txt_)
        docs = set(re.findall(r'\b(Z[A-Z0-9]{2,4})\b', ' '.join(parsed.get('DocType', []))))
        desc = ''
        for s in steps[a:b]:
            if START.search(str(s.get('Transaction', ''))) or s is steps[a]:
                desc = str(s.get('Test Step Description', ''))
                break
        kind = _kind(desc, docs)
        t = {'n': n + 1, 'kind': kind, 'steps': list(range(a, b)), 'title': desc, 'proveedor': '', 'o_planta': '', 'o_alm': '',
             'd_planta': '', 'd_alm': ''}
        # la Data solo es fiable si su clase de documento corresponde al tipo de tramo
        fiable = (kind == 'COMPRA' and (docs & BUY_DOCS or not docs)) or (kind == 'TRASPASO' and docs & TRANSFER_DOCS)
        if fiable:
            ps = plant_sloc(parsed.get('Plant', []) + parsed.get('DestPlant', []), known)
            ss = plant_sloc(parsed.get('SupPlant', []), known)
            if ps:
                t['d_planta'], t['d_alm'] = ps[0]
            if ss:
                t['o_planta'], t['o_alm'] = ss[0]
            masp = plant_sloc(parsed.get('Plant2', []) + parsed.get('Plant3', []), known)
            if kind == 'TRASPASO' and masp:      # con Supplier Plant: SP → Plant 1 → Plant 2 → …; sin él (tras una compra): Plant 1 → Plant 2 → Plant 3
                dests = ps[:1] + masp
                origenes, destinos = ([ss[0]] + dests[:-1], dests) if ss else (dests[:-1], dests[1:])
                k = min(ntr, len(destinos) - 1)
                t['o_planta'], t['o_alm'] = origenes[k]
                t['d_planta'], t['d_alm'] = destinos[k]
            v = re.findall(r'\b[A-Z]?\d{4,10}\b', ' '.join(parsed.get('Vendor', []) + parsed.get('BP', [])))
            if kind == 'COMPRA' and v:
                t['proveedor'] = v[0]
        if kind == 'TRASPASO':
            ntr += 1
        out.append(t)
    for i in range(1, len(out)):        # el origen de un traspaso es el destino del tramo anterior
        if out[i]['kind'] == 'TRASPASO' and not out[i]['o_planta']:
            out[i]['o_planta'], out[i]['o_alm'] = out[i - 1]['d_planta'], out[i - 1]['d_alm']
        if out[i]['kind'] == 'TRASPASO' and out[i]['o_planta'] and out[i]['o_planta'] == out[i]['d_planta']:      # un traspaso a la misma planta no existe: el destino lo pone el usuario
            out[i]['d_planta'], out[i]['d_alm'] = '', ''
    return out
