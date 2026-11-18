"""Front local de seguimiento de casos UAT. Solo lee ficheros (UAT + exportaciones SE16N); no toca SAP.
Uso: python front/server.py [--port 8766]   ->  http://localhost:8766"""
import argparse
import csv
import io
import json
import os
import re
import sys
import threading
import time
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import yaml  # noqa: E402
from engine import parse_data, readers, tramos as tramos_mod, ecc as ecc_mod, modelo_tx, derivados  # noqa: E402
from engine.options import Options  # noqa: E402

CFG = yaml.safe_load((ROOT / 'config/settings.yaml').read_text(encoding='utf-8'))
EXTR = yaml.safe_load((ROOT / 'config/extractions.yaml').read_text(encoding='utf-8'))['extractions']
RULES = yaml.safe_load((ROOT / 'config/rules.yaml').read_text(encoding='utf-8'))
SHEET = 'UAT_testscript - breaks by unit'
ASIG = ROOT / 'data/ledger/asignaciones.json'
LEDGER = ROOT / CFG['paths']['ledger']
LOCK = threading.Lock()

ORG_FIELDS = [('sociedad', 'Sociedad (C.Code)'), ('org_compras', 'Org. compras (P.Org)'), ('org_ventas', 'Org. ventas (S.Org)')]
COMMON = [('planta_emisora', 'Planta emisora'), ('planta_receptora', 'Planta receptora'), ('almacen', 'Almacén')]
FIELDS = {
    'PP': [('planta', 'Planta'), ('almacen', 'Almacén'), ('material', 'Material a fabricar'),
           ('version_fabricacion', 'Versión de fabricación'), ('lista_materiales', 'Lista de materiales'),
           ('hoja_ruta', 'Hoja de ruta'), ('puesto_trabajo', 'Puesto de trabajo (línea)'), ('cost_collector', 'Cost collector (orden)'), ('componentes', 'Componentes (varios)')],
    'QM': [('planta', 'Planta'), ('material', 'Material'), ('clase_inspeccion', 'Clase de inspección'),
           ('lote', 'Lote / lote de inspección')],
    'PM': [('planta', 'Planta de mantenimiento'), ('equipo', 'Equipo'),
           ('ubicacion_tecnica', 'Ubicación técnica'), ('material', 'Material repuesto')],
    'WM': [('planta', 'Planta'), ('almacen', 'Almacén'), ('lgnum', 'Nº almacén (LGNUM)'),
           ('tipo_almacen', 'Tipo de almacén'), ('ubicacion', 'Ubicación'), ('material', 'Material'), ('lote', 'Lote')],
    'LOG': [('planta', 'Planta')] + COMMON + [('alm_emisora', 'Almacén emisor'), ('alm_receptora', 'Almacén receptor'), ('material', 'Material'), ('proveedor', 'Proveedor'), ('cliente', 'Cliente'),
                     ('punto_expedicion', 'Punto de expedición'), ('punto_transporte', 'Pto. planif. transporte'),
                     ('transportista', 'Transportista'), ('grupo_compras', 'Grupo de compras'), ('tipo_pedido', 'Tipo de pedido')],
}
MULTI = {'componentes'}
CHECKS = {
    'PP': ['Material (ZFIN/ZSEM/ZFOR) en la planta', 'Lista de materiales activa', 'Hoja de ruta (tipo N)', 'Puesto de trabajo en la versión de fabricación (casos de planificación en adelante)', 'Versión de fabricación vigente y sin bloquear',
           'Cost collector (fabricación repetitiva)', 'Componentes con stock libre', 'Material exclusivo de este caso'],
    'QM': ['Plan de inspección / clase de inspección activa (QMAT)', 'Material con stock o lote inspeccionable',
           'Material exclusivo de este caso'],
    'PM': ['Equipo activo en la planta de mantenimiento', 'Ubicación técnica asociada', 'Equipo exclusivo de este caso',
           'Repuesto (ZSPN/ZSPV) con stock si hay reserva'],
    'WM': ['LGNUM asignado a la planta/almacén (T320)', 'Stock en ubicación (LQUA) con cantidad suficiente',
           'Material con datos WM (MLGN/MLGT)', 'Ubicación exclusiva de este caso'],
    'LOG': ['Sociedad y orgs derivadas de la planta', 'Material ampliado en emisora y receptora',
            'Stock libre en la emisora', 'Proveedor/cliente/registro info según flujo', 'Material exclusivo de este caso'],
}

state = {}
SERVER_START = datetime.now().timestamp()


TABLA_ES = {
    'MARC': 'Materiales de la planta', 'MARA': 'Datos generales y tipo de cada material', 'MAKT': 'Descripciones de los materiales',
    'MARD': 'Stock por almacén', 'MKAL': 'Versiones de fabricación (con línea de producción)', 'MAST': 'Qué lista de materiales tiene cada material',
    'STKO': 'Cabeceras de las listas de materiales', 'STPO': 'Componentes de las listas de materiales', 'PLKO': 'Cabeceras de las hojas de ruta',
    'AFPO': 'Órdenes: material de cada una', 'T001L': 'Almacenes', 'EINA': 'Registros info (material y proveedor)', 'EINE': 'Registros info (condiciones)',
    'QMAT': 'Tipos de inspección activos por material', 'T320': 'Almacén de gestión de almacenes (WM) de la planta', 'LQUA': 'Stock por ubicación (WM)',
    'MLGN': 'Datos WM del material', 'MLGT': 'Tipos de almacén del material',
    'LFA1': 'Proveedores', 'LFM1': 'Proveedores por organización de compras', 'T001W': 'Plantas',
}


def humano(name, table):
    if table == 'MAPL':
        return 'Rutas de tasa (tipo R, para costes)' if name.endswith('_R') else 'Hojas de ruta de fabricación (tipo N)'
    if table == 'AUFK':
        return 'Cost collectors (órdenes de tipo 05)'
    return TABLA_ES.get(table, table)


def front_version():
    """Marca de versión: la más reciente entre el arranque del servidor y los ficheros de la pantalla. Cambia con cada actualización."""
    ts = [SERVER_START] + [f.stat().st_mtime for f in (ROOT / 'front/static').glob('*') if f.is_file()]
    return datetime.fromtimestamp(max(ts)).strftime('%d/%m %H:%M:%S')


def load_orgs():
    """Org.Structure del UAT: planta -> sociedad, org. compras, orgs. ventas."""
    p = ROOT / CFG['paths']['uat_file']
    if not p.exists():
        return {}
    import openpyxl
    wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
    out = {}
    for r in wb['Org.Structure'].iter_rows(min_row=4, values_only=True):
        if not r[0]:
            continue
        sor = [x.strip().split()[0] for x in str(r[8] or '').split('|') if x.strip()]
        out[str(r[0]).strip()] = {'nombre': str(r[1] or ''), 'pais': str(r[2] or ''), 'sociedad': str(r[4] or '').strip(),
                                  'org_compras': str(r[6] or '').strip(), 'org_ventas_lista': sor, 'ubicacion': str(r[10] or '').strip()}
    return out


def load_uat():
    p = ROOT / CFG['paths']['uat_file']
    if p.exists():
        import openpyxl
        wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
        it = wb[SHEET].iter_rows(values_only=True)
        hdr = [str(h).strip() if h is not None else '' for h in next(it)]
        rows = [{h: ('' if c is None else str(c)) for h, c in zip(hdr, r) if h} | {'_row': i} for i, r in enumerate(it, 2)]
        return [r for r in rows if r.get('ID by unit')], str(p), False
    return json.loads((ROOT / 'tests/mock/uat_mock.json').read_text(encoding='utf-8')), 'tests/mock/uat_mock.json', True


MT_WORDS = [(r'raw material|materia prima|materias primas', 'ZRAW'), (r'packaging|envase|embalaje', 'ZPAC'),
            (r'final product|finished|producto terminado|\bFG\b', 'ZFIN'), (r'semi[- ]?(finished|elaborad)', 'ZSEM'),
            (r'formulat|formulad', 'ZFOR'), (r'spare|repuesto', 'ZSPN'), (r'pallet', 'ZRPL')]


def suggest_mtypes(texts):
    """Tipos de material citados en el caso: códigos explícitos (ZFIN…) o palabras (Raw materials, Packaging…)."""
    t = ' '.join(texts)
    found = []
    for code in re.findall(r'\bZ(?:FIN|SEM|RAW|FOR|PAC|RPL|SPN|SPV|IBE|PRO|PAL)\b', t.upper()):
        if code not in found:
            found.append(code)
    for pat, code in MT_WORDS:
        if re.search(pat, t, re.I) and code not in found:
            found.append(code)
    if 'ZSPN' in found and 'ZSPV' not in found and re.search('spare|repuesto', t, re.I):
        found.append('ZSPV')
    return found


def build():
    global ASIG, LEDGER
    rows, src, mock = load_uat()
    if mock:  # en modo prueba no se contamina el ledger real
        ASIG = ROOT / 'data/ledger/asignaciones_MOCK.json'
        LEDGER = ROOT / 'data/ledger/reservas_MOCK.csv'
    orgs = load_orgs()
    known = set(orgs) or None
    groups = {}
    for r in rows:
        groups.setdefault(r['ID by unit'], []).append(r)
    cases = {}
    for cid, g in groups.items():
        parsed = [parse_data.parse(r.get('Data', '')) for r in g]
        stream, flow, docs = parse_data.classify(' '.join(r.get('Transaction', '') for r in g), g[0].get('L2'), parsed)
        avisos_data = []
        escen = str(g[0].get('Test Scenario', '')).replace('\n', ' ')
        # Regla del usuario: «outbound flow (customers)» / «sales flow» es una VENTA a cliente, salvo que en los pasos haya una transfer order.
        # La clase de documento de la Data a veces no lo dice (p. ej. «Doc Type: ZPO» en una venta): manda el escenario.
        if (stream == 'LOG' and flow in ('ZPO', 'ZSPO', 'ZSPA', 'ZSER', 'ZINT', 'ZINR', 'ZTRA', 'ZWIA')
                and re.search(r'outbound (flow|process)|sales? flows?|sell\b|to (the )?(final )?customer', escen, re.I)
                and not any(re.search(r'transfer order|stock transfer|\bsto\b', str(r.get('Test Step Description', '')), re.I) for r in g)
                and any(re.search(r'\b(VA01|VL01N|VL10[A-D]|VF01)\b', str(r.get('Transaction', ''))) for r in g)):
            avisos_data.append(f'La Data dice «Doc Type: {flow}», pero el escenario es una venta a cliente (VA01, entrega de salida) y no tiene transfer order: se trata como venta. Revisa la clase de documento del Excel.')
            flow = 'VENTA'
        plants = parse_data.plants_in([v for p in parsed for k in ('Plant', 'Plant2', 'Plant3', 'DestPlant', 'SupPlant') for v in p.get(k, [])], known)
        roles = {'emisora': parse_data.plants_in([v for p in parsed for v in p.get('SupPlant', [])], known),
                 'receptora': parse_data.plants_in([v for p in parsed for k in ('Plant', 'Plant2', 'Plant3', 'DestPlant') for v in p.get(k, [])], known)}
        # Regla del usuario: una «transfer order» va de una planta a otra; NO es una compra. Si la Data trae planta emisora y receptora (y no es una cadena de tramos),
        # o el escenario/los pasos hablan de transfer order, el flujo es un traslado (ZTRA / ZWIA / ZINT según sociedad y país), aunque la Data diga ZPO o no diga nada.
        if (stream == 'LOG' and flow in ('ZPO', 'ZSPO', 'ZSPA', 'ZSER') and roles['emisora'] and roles['receptora'] and not tramos_mod.detect(g, known)):
            hay_to = bool(re.search(r'transfer order|stock transfer|\bsto\b', escen, re.I)) or any(re.search(r'transfer order|stock transfer|\bsto\b', str(r.get('Test Step Description', '')), re.I) for r in g)
            explicito = bool(set(docs) & {'ZPO', 'ZSPO', 'ZSPA', 'ZSER'})
            o_ = roles['emisora'][0]
            d_ = next((p for p in roles['receptora'] if p != o_), '')
            if d_ and (hay_to or not explicito):
                a_, b_ = orgs.get(o_), orgs.get(d_)
                nuevo = 'ZTRA' if not (a_ and b_) else ('ZINT' if a_['sociedad'] != b_['sociedad'] else ('ZWIA' if a_['pais'] != b_['pais'] else 'ZTRA'))
                avisos_data.append((f'La Data dice «Doc Type: {flow}», pero el escenario es un traslado' if explicito else 'La Data no dice que sea una compra y el escenario es un traslado')
                                   + f' entre plantas ({o_} → {d_}, transfer order): se trata como {nuevo}. Revisa la clase de documento del Excel.')
                flow = nuevo
        data_org = {k: sorted({x for p in parsed for v in p.get(src_k, []) for x in re.findall(r'[A-Z0-9]{1,6}', v.upper()) if not re.fullmatch(r'X{3,}', x)})
                    for k, src_k in (('sociedad', 'CCode'), ('org_compras', 'POrg'))}
        # org. de ventas: el texto TAL CUAL de la Data («9000 / 10 / 10» = org. de ventas / canal / sector); trocearlo mezclaba canal y sector con la organización
        data_org['org_ventas'] = sorted({' / '.join([x.strip() for x in v.split('/') if x.strip()][:2]) for p in parsed for v in p.get('SOrg', []) if v.strip() and not re.match(r'\s*X{3,}', v)})
        cases[cid] = {'id': cid, 'new_id': g[0].get('New ID', ''), 'l2': g[0].get('L2', ''), 'l3': g[0].get('L3', ''),
                      'location': g[0].get('Location by Unit', ''), 'scenario': str(g[0].get('Test Scenario', '')).replace('\n', ' '),
                      'avisos_data': avisos_data, 'stream': stream, 'flow': flow, 'docs': docs, 'plants': plants, 'roles': roles, 'data_org': data_org,
                      'mtypes': suggest_mtypes([str(g[0].get('Test Scenario', ''))] + [str(r.get('Test Step Description', '')) + ' ' + str(r.get('Data', '')) for r in g]),
                      'tramos': tramos_mod.detect(g, known), 'steps': g, 'n_steps': len(g),
                      'almacenes': {'emisora': next(iter(tramos_mod.plant_sloc([v for p in parsed for v in p.get('SupPlant', [])], known)), ('', '')),
                                    'receptora': next(iter(tramos_mod.plant_sloc([v for p in parsed for k in ('Plant', 'Plant2', 'Plant3', 'DestPlant') for v in p.get(k, [])], known)), ('', ''))},
                      'proveedor': next(iter(re.findall(r'\b[A-Z]?\d{4,10}\b', ' '.join(v for p in parsed for k in ('Vendor', 'BP') for v in p.get(k, [])))), '')}
    raw_dir = ROOT / CFG['paths']['raw_dir']
    raw_empty = not (raw_dir.exists() and any(raw_dir.glob('*.*')))
    raw_mock = raw_empty and mock          # los datos sintéticos solo se mezclan con casos sintéticos
    if raw_mock:
        raw_dir = ROOT / 'tests/mock/raw'
    readers.set_exclusiones((CFG.get('exclusiones') or {}).get('matnr', []))
    tables, warns = ({}, []) if (raw_empty and not mock) else readers.load_all(raw_dir, EXTR)
    if mock:
        warns.insert(0, 'MODO PRUEBA: no hay fichero UAT en data/project; casos y opciones SINTÉTICOS.')
    elif raw_empty:
        warns.insert(0, f'Faltan exportaciones SE16N en data/raw/: las listas de opciones saldrán vacías. Organización tomada de Org.Structure ({len(orgs)} plantas).')
    state.update(orgs=orgs, cases=cases, tables=tables, warns=warns, source=src, mock=mock,
                 tables_info={k: len(v) for k, v in tables.items()})


def guarda_asig(asig):
    """Guarda con copia de seguridad y reintentos: OneDrive bloquea el fichero un instante al sincronizar."""
    txt = json.dumps(asig, ensure_ascii=False, indent=1)
    ultimo = None
    for _ in range(15):
        try:
            ASIG.write_text(txt, encoding='utf-8')
            return
        except OSError as e:
            ultimo = e
            time.sleep(0.4)
    raise ultimo


def load_asig():
    for _ in range(5):
        try:
            return json.loads(ASIG.read_text(encoding='utf-8')) if ASIG.exists() else {}
        except ValueError:
            time.sleep(0.3)
    return json.loads(ASIG.read_text(encoding='utf-8'))


def reserved_map(asig, exclude=None):
    res = {}
    for cid, a in asig.items():
        if cid == exclude:
            continue
        for tipo, rec in resources(a):
            res[(tipo, rec)] = cid
    return res


def resources(a):
    f = a.get('fields', {})
    out = []
    suf = '@' + (f.get('planta') or f.get('planta_emisora') or '') if (f.get('planta') or f.get('planta_emisora')) else ''     # un material se reserva POR PLANTA: el stock, la lista y la ruta son de cada planta
    for k, tipo in (('material', 'MATERIAL'), ('equipo', 'EQUIPO'), ('ubicacion_tecnica', 'UT')):
        if k == 'material' and a.get('objetivo') == 'MATERIAL':
            continue            # material MODELO: solo se copia, no se consume
        if f.get(k):
            for part in ((a['nuevos'] if (a.get('auto') and 'nuevos' in a) else re.split(r'[,;\s]+', f[k])) if k == 'material' else [f[k]]):
                if part.strip():
                    out.append((tipo, part.strip() + (suf if tipo == 'MATERIAL' else '')))
    for c in str(f.get('componentes', '')).split(','):
        if c.strip():
            out.append(('MATERIAL', c.strip() + suf))
    if f.get('lgnum') and f.get('ubicacion') and f.get('material'):
        out.append(('UBICACION', f"{f['material']}|{f['lgnum']}|{f['ubicacion']}"))
    return out


def conflicts(asig):
    seen, out = {}, []
    for cid, a in asig.items():
        for res in resources(a):
            if res in seen and seen[res] != cid:
                out.append({'tipo': res[0], 'recurso': res[1], 'casos': [seen[res], cid]})
            seen.setdefault(res, cid)
    return out


def write_ledger(asig):
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    old = {}
    if LEDGER.exists():
        for r in csv.DictReader(LEDGER.open(encoding='utf-8')):
            old[(r['caso'], r['tipo_recurso'], r['recurso'])] = r
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    out = []
    for cid, a in asig.items():
        f = a.get('fields', {})
        for tipo, rec in resources(a):
            k = (cid, tipo, rec)
            row = old.get(k) or {'caso': cid, 'tipo_recurso': tipo, 'recurso': rec, 'estado': 'RESERVADO', 'fecha': now, 'ejecucion': ''}
            row['planta'] = f.get('planta') or f.get('planta_emisora', '')
            row['almacen'] = f.get('almacen', '')
            out.append(row)
    keep = {(r['caso'], r['tipo_recurso'], r['recurso']) for r in out}
    for k, r in old.items():       # lo que ya no está asignado pasa a LIBERADO (no se borra el rastro)
        if k not in keep and r.get('estado') == 'RESERVADO':
            r['estado'] = 'LIBERADO'
            out.append(r)
    cols = ['caso', 'tipo_recurso', 'recurso', 'planta', 'almacen', 'estado', 'fecha', 'ejecucion']
    with LEDGER.open('w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction='ignore')
        w.writeheader()
        w.writerows(out)


def flow_warnings(flow, f):
    """Avisos de coherencia del flujo con Org.Structure (reglas confirmadas por el usuario)."""
    o = state['orgs']
    a, b = f.get('planta_emisora') or f.get('planta'), f.get('planta_receptora')
    oa, ob = o.get(a or '', {}), o.get(b or '', {})
    w = []
    if flow in ('ZTRA', 'ZWIA') and oa and ob and oa['sociedad'] != ob['sociedad']:
        w.append(f"{flow} entre sociedades distintas ({oa['sociedad']} -> {ob['sociedad']}) es un error de datos: usa plantas de la misma sociedad.")
    if flow == 'ZWIA' and oa and ob and oa['pais'] == ob['pais']:
        w.append(f"ZWIA (plant abroad) necesita plantas en distinto país; {a} y {b} están en {oa['pais']}.")
    if flow in ('ZINT', 'ZINR') and oa and ob and oa['sociedad'] == ob['sociedad']:
        w.append(f"{flow} es entre sociedades y {a} y {b} son de la misma ({oa['sociedad']}).")
    return w


def ecc():
    p = CFG['paths'].get('ecc_file')
    return ecc_mod.get(p) if p and Path(p).exists() else None


def doc_for(o_pl, d_pl):
    """Clase de documento de un traslado, según las plantas (reglas confirmadas): misma sociedad y país -> ZTRA;
    misma sociedad y distinto país -> ZWIA; sociedades distintas -> ZINT."""
    o = state['orgs']
    a, b = o.get(o_pl or ''), o.get(d_pl or '')
    if not a or not b:
        return ''
    if a['sociedad'] != b['sociedad']:
        return 'ZINT'
    return 'ZWIA' if a['pais'] != b['pais'] else 'ZTRA'


def _n(x):
    return str(x or '').strip().lstrip('0')


def ecc_viabilidad(c):
    """¿Había antecedente en ECC (listado de pedidos reales) de lo que pide el caso? Devuelve estado, texto y sugerencias que el usuario puede aplicar (nunca se aplican solas)."""
    e = ecc()
    fl = (c or {}).get('flow')
    if e is None or not c or c.get('stream') != 'LOG' or fl not in ('ZTRA', 'ZWIA', 'ZINT', 'ZINR', 'ZPO', 'ZSPO', 'ZSPA', 'ZSER') or c.get('tramos'):      # los casos encadenados se contrastan por tramo
        return None
    r = c.get('roles') or {}
    if fl in ('ZTRA', 'ZWIA', 'ZINT', 'ZINR'):
        em = (r.get('emisora') or [''])[0]
        rc = next((p for p in (r.get('receptora') or []) if p != em), (r.get('receptora') or [''])[0] if r.get('receptora') else '')
        orig, mismo = e.origenes(fl, rc) if rc else ([], False)
        sug = [{'campo': 'planta_emisora', 'valor': p, 'texto': f'{p} ({n} doc.)'} for p, n in orig if p != rc]
        if not rc:
            return {'estado': 'faltan_plantas', 'texto': 'La Data no trae planta receptora: no se puede contrastar con ECC.', 'sugerencias': []}
        if not em:
            t = (f'En ECC {rc} recibía traslados {"de tipo " + fl if mismo else "(de otro tipo que " + fl + ")"} desde: ' + ', '.join(x['texto'] for x in sug)) if sug else f'En ECC {rc} no recibe ningún traslado: no hay antecedente para completar la planta emisora (flujo nuevo de S/4).'
            return {'estado': 'faltan_plantas', 'texto': 'La Data no trae planta emisora. ' + t, 'sugerencias': sug}
        t = e.traslado(em, '', rc, '')
        if t['existe']:
            return {'estado': 'ok', 'texto': f"Había antecedente en ECC: {t['docs']} documentos {t['tipo']} de {em} a {rc}, el último el {t['ultimo']}.", 'sugerencias': []}
        sug = [x for x in sug if x['valor'] != em]
        txt = f'Sin antecedente en ECC de {em} a {rc}.' + (' ' + (f'Orígenes que sí enviaban a {rc}: ' if mismo else f'{rc} recibía de otros orígenes (otro tipo de traslado): ') + ', '.join(x['texto'] for x in sug) if sug else f' {rc} no recibe traslados en ECC: es un flujo nuevo de S/4.')
        return {'estado': 'sin_antecedente', 'texto': txt, 'sugerencias': sug}
    pl = (c.get('plants') or [''])[0]
    ven = c.get('proveedor') or ''
    if not pl:
        return {'estado': 'faltan_plantas', 'texto': 'La Data no trae planta: no se puede contrastar con ECC.', 'sugerencias': []}
    top = e.proveedores(pl, '', 3)
    sug = [{'campo': 'proveedor', 'valor': x['proveedor'], 'texto': f"{x['proveedor']} ({x['docs']} doc.)"} for x in top]
    if not ven:
        return {'estado': 'sin_proveedor', 'texto': 'La Data no trae proveedor.' + (f' En ECC {pl} compraba sobre todo a: ' + ', '.join(x['texto'] for x in sug) if sug else f' {pl} no tiene compras en ECC.'), 'sugerencias': sug}
    t = e.compra(ven, pl, '')
    if t['existe']:
        return {'estado': 'ok', 'texto': f"Había antecedente en ECC: {t['docs']} documentos de {ven} a {pl}, el último el {t['ultimo']}.", 'sugerencias': []}
    return {'estado': 'sin_antecedente', 'texto': f'El proveedor {ven} no compraba a {pl} en ECC.' + (' Sí compraban: ' + ', '.join(x['texto'] for x in sug) if sug else f' {pl} no tiene compras en ECC.'), 'sugerencias': sug}


_EINA_V = {'sig': None, 'set': set()}


def eina_proveedores_leidos():
    """Proveedores de los que SÍ se han leído TODOS sus registros info (lectura por proveedor: EINA__V<proveedor> o el lote «VZINT»). Lo leído por planta solo trae
    los registros con datos de esa planta (EINE por WERKS): los de nivel de organización de compras no se ven, y no se puede decir que «no existen»."""
    d = ROOT / CFG['paths']['raw_dir']
    fs = sorted(d.glob('EINA__V*.txt'))
    sig = tuple((f.name, f.stat().st_mtime) for f in fs)
    if _EINA_V['sig'] != sig:
        leidos = set()
        for f in fs:
            nom = f.stem[len('EINA__V'):]
            if re.fullmatch(r'[A-Za-z]{2,}\d*|[A-Z]+', nom) and not nom.isdigit():       # lote de varios proveedores (p. ej. «ZINT»): se leen sus LIFNR
                try:
                    with f.open(encoding='utf-8', errors='ignore') as fh:
                        cab = fh.readline().rstrip('\r\n').split('\t')
                        i = cab.index('LIFNR')
                        for ln in fh:
                            c_ = ln.rstrip('\r\n').split('\t')
                            if len(c_) > i:
                                leidos.add(c_[i].strip().lstrip('0'))
                except (OSError, ValueError):
                    pass
            leidos.add(nom.strip().lstrip('0'))
        _EINA_V.update(sig=sig, set=leidos)
    return _EINA_V['set']


def check_flujo(flow, f):
    """Comprobaciones de un flujo de logística de un solo tramo. ok: True / False / None (faltan datos de QS4)."""
    T, e = state['tables'], ecc()
    out = []

    def add(req, ok, det='', deseable=False):
        out.append({'req': req, 'ok': ok, 'detalle': det, 'deseable': deseable})
    o, d = (f.get('planta_emisora') or '').upper(), (f.get('planta_receptora') or f.get('planta') or '').upper()
    ao, ad = f.get('alm_emisora', ''), f.get('alm_receptora', '')
    mat, ven = f.get('material', '').strip(), f.get('proveedor', '').strip()
    traslado = flow in ('ZTRA', 'ZWIA', 'ZINT', 'ZINR')
    compra = flow in ('ZPO', 'ZSPO', 'ZSPA', 'ZSER')
    if not (traslado or compra):
        return out
    if traslado and not ven and o:
        ven = 'P' + o
    sin = 'Sin datos de QS4: pulsa Consultar QS4'

    def cargada(tabla, col, pl):
        return any(r.get(col) == pl for r in T.get(tabla, []))
    # 1) el flujo existía en ECC
    if e is not None:
        if traslado and o and d:
            r = e.traslado(o, ao, d, ad)
            add('Existía en ECC (planta y almacén de origen → destino)', r['existe'],
                f"{r['docs']} documentos {r['tipo']}, el último el {r['ultimo']}" if r['existe'] else 'No hay traslados así en ECC' + (' (el par de plantas sí, con otros almacenes)' if r.get('mismo_par_plantas') else ''))
        if compra and ven and d:
            r = e.compra(ven, d, ad)
            add('Existía en ECC (proveedor → planta y almacén)', r['existe'], f"{r['docs']} documentos, el último el {r['ultimo']}" if r['existe'] else 'Ese proveedor no compraba a esa planta/almacén en ECC')
    mats_sel = [x.strip().lstrip('0') for x in re.split(r'[,;\s]+', mat) if x.strip()]
    if e is not None and mats_sel:
        if traslado and o and d:
            r = e.mats_traslado(o, d, mats_sel)
            add(f'Los materiales elegidos se trasladaban de {o} a {d} en ECC', (not r['no']),
                (f"{len(r['si'])} de {len(mats_sel)}" + (f"; sin antecedente: {', '.join(r['no'][:6])}" if r['no'] else '')), deseable=True)
        if compra and ven and d:
            r = e.mats_compra(ven, d, mats_sel)
            add(f'Los materiales elegidos se compraban a {ven} en {d} en ECC', (not r['no']), (f"{len(r['si'])} de {len(mats_sel)}" + (f"; sin antecedente: {', '.join(r['no'][:6])}" if r['no'] else '')), deseable=True)
    # 2) clase de documento coherente con las plantas
    if traslado and o and d:
        dc = doc_for(o, d)
        add(f'Clase {flow} coherente con las plantas', (dc == flow) if dc else None, f'Por sociedad y país, las plantas piden {dc}' if dc and dc != flow else '')
    # 3) plantas y almacenes en QS4
    t001w = {r['WERKS'] for r in T.get('T001W', [])}
    t001l = {(r['WERKS'], r['LGORT']) for r in T.get('T001L', [])}
    for pl in [x for x in dict.fromkeys([o, d]) if x]:
        add(f'Planta {pl} existe en QS4', (pl in t001w) if t001w else None, '' if t001w else sin)
        og = state['orgs'].get(pl, {})
        add(f'Planta {pl}: sociedad y organización de compras', bool(og.get('sociedad') and og.get('org_compras')),
            f"Sociedad {og.get('sociedad')}, org. de compras {og.get('org_compras')}" if og.get('sociedad') and og.get('org_compras') else 'Falta en Org.Structure')
        if cargada('T001L', 'WERKS', pl):
            alm = sorted(r['LGORT'] for r in T.get('T001L', []) if r['WERKS'] == pl)
            add(f'Planta {pl} tiene almacenes', bool(alm), ', '.join(alm[:10]) + (' …' if len(alm) > 10 else '') if alm else 'Sin almacenes en T001L')
        else:
            add(f'Planta {pl} tiene almacenes', None, f'Sin datos de {pl}: pulsa Consultar QS4')
    for pl, al in ((o, ao), (d, ad)):
        if pl and al:
            ok = ((pl, al) in t001l) if cargada('T001L', 'WERKS', pl) else None
            add(f'Almacén {al} existe en {pl}', ok, f'Sin datos de {pl}: pulsa Consultar QS4' if ok is None else '')
    # 4) proveedor
    if compra and not ven:
        add('Proveedor indicado', False, 'El caso no trae proveedor: elige uno (abajo, "Proveedores que compraban…" en ECC)')
    if ven:
        lfa1 = {_n(r['LIFNR']): r for r in T.get('LFA1', [])}
        if lfa1 or 'LFA1' in T:
            r = lfa1.get(_n(ven))
            add(f'Proveedor {ven} existe', bool(r), '' if r else 'No está en LFA1')
            if r:
                add(f'Proveedor {ven} sin bloqueos', not (r.get('SPERR') or r.get('SPERM')), 'Bloqueado' if (r.get('SPERR') or r.get('SPERM')) else '')
        else:
            add(f'Proveedor {ven} existe', None, sin)
        bk = state['orgs'].get(d, {}).get('sociedad', '')
        if 'LFB1' in T and bk:
            okb = any(_n(r['LIFNR']) == _n(ven) and r['BUKRS'] == bk and not r.get('SPERR') for r in T['LFB1'])
            add(f'Proveedor {ven} existe en la sociedad {bk}', okb, '' if okb else 'No tiene LFB1 en esa sociedad (o está bloqueado)')
        elif bk:
            add(f'Proveedor {ven} existe en la sociedad {bk}', None, 'Faltan los datos de proveedor por sociedad (LFB1): cárgalos desde «Cargar plantas…» (LOG)')
        ek = state['orgs'].get(d, {}).get('org_compras', '')
        if 'LFM1' in T:
            ok = any(_n(r['LIFNR']) == _n(ven) and (not ek or r['EKORG'] == ek) and not r.get('SPERM') for r in T['LFM1'])
            add(f'Proveedor {ven} con datos de compras en {ek or "su org. de compras"}', ok, '' if ok else 'No tiene LFM1 en esa organización (o está bloqueado)')
        else:
            add(f'Proveedor {ven} con datos de compras', None, sin)
    # 5) registro info (compras): de CADA material elegido con el proveedor
    mats_l = [x for x in re.split(r'[,;\s]+', mat) if x.strip()]
    if (compra or flow == 'ZINT') and mats_l and ven:
        if 'EINA' in T:
            sin_reg = [m for m in mats_l if not any(_n(r['MATNR']) == _n(m) and _n(r['LIFNR']) == _n(ven) and not r.get('LOEKZ') for r in T['EINA'])]
            req = f'Registro info de los materiales elegidos ({len(mats_l)}) con el proveedor {ven}'
            if not sin_reg:
                add(req, True, f'{len(mats_l)} de {len(mats_l)}')
            elif _n(ven) not in eina_proveedores_leidos():
                # solo hay registros info LEÍDOS POR PLANTA: los de nivel de organización de compras no se ven. No se puede afirmar que no existan.
                add(req, None, f'Sin leer: de este proveedor no se han leído sus registros info completos (solo los de planta). Pulsa «Consultar QS4» para leerlos. Sin registro en lo leído: {", ".join(sin_reg[:6])}')
            else:
                add(req, False, f'No existe en EINA para {len(sin_reg)} de {len(mats_l)}: {", ".join(sin_reg[:6])}')
            ids = {r['INFNR'] for r in T['EINA'] if _n(r['LIFNR']) == _n(ven) and _n(r['MATNR']) in {_n(m) for m in mats_l} and not r.get('LOEKZ')}
            if ids and 'EINE' in T:
                ek = state['orgs'].get(d, {}).get('org_compras', '')
                okk = any(r['INFNR'] in ids and (not ek or r['EKORG'] == ek) and not r.get('LOEKZ') and (flow != 'ZSPO' or (r.get('ESOKZ') or '').strip() == '3') for r in T['EINE'])
                add(f'Registro info con datos de compras{" de subcontratación" if flow == "ZSPO" else ""} en {ek or "la org. de compras"}', okk, '' if okk else 'Falta EINE para esa organización' + (' (tipo subcontratación)' if flow == 'ZSPO' else ''))
        else:
            add('Registro info del material con el proveedor', None, sin)
    # 6) materiales en las plantas y stock (todos los elegidos)
    if mats_l:
        marc = {(_n(r['MATNR']), r['WERKS']): r for r in T.get('MARC', [])}
        lista = ', '.join(mats_l[:4]) + (' …' if len(mats_l) > 4 else '')
        for pl in [x for x in dict.fromkeys([o, d]) if x]:
            if cargada('MARC', 'WERKS', pl):
                falta = [m for m in mats_l if not (marc.get((_n(m), pl)) and not marc[(_n(m), pl)].get('LVORM'))]
                add(f'Materiales elegidos ampliados en {pl}', not falta, f'{len(mats_l) - len(falta)} de {len(mats_l)}' + (f'; no están en MARC: {", ".join(falta[:6])}' if falta else ''))
                zz = [m for m in mats_l if (marc.get((_n(m), pl)) or {}).get('MMSTA', '').strip() == 'ZZ']
                if marc and any(marc.get((_n(m), pl)) for m in mats_l):
                    add(f'Materiales elegidos sin estado ZZ en {pl}', not zz, ('con ZZ: ' + ', '.join(zz[:6])) if zz else '')
            else:
                add(f'Materiales elegidos ({lista}) ampliados en {pl}', None, f'Sin datos de {pl}: pulsa Consultar QS4')
        if traslado and o:      # el stock en origen es deseable, no obligatorio: se avisa pero no bloquea
            if cargada('MARD', 'WERKS', o):
                sin_st = [m for m in mats_l if sum(_f_num(r.get('LABST')) for r in T['MARD'] if _n(r['MATNR']) == _n(m) and r['WERKS'] == o and (not ao or r['LGORT'] == ao)) <= 0]
                add(f'Stock libre de los materiales elegidos en {o}{" / " + ao if ao else ""} (deseable)', not sin_st, (f'sin stock: {", ".join(sin_st[:6])} (no bloquea)' if sin_st else 'todos con stock'), deseable=True)
            else:
                add(f'Stock libre de los materiales elegidos en {o}', None, f'Sin datos de {o}: pulsa Consultar QS4')
    return out


def _f_num(x):
    from engine.options import _f
    return _f(x)


def tramos_vista(c, a):
    """Tramos del caso con lo guardado encima de lo que dice la Data, el origen encadenado y la comprobación en ECC."""
    out = []
    guardados = a.get('tramos') or []
    e = ecc()
    t001l = {(r['WERKS'], r['LGORT']) for r in state['tables'].get('T001L', [])}
    for i, base in enumerate(c['tramos']):
        t = dict(base)
        if i < len(guardados):
            t.update({k: str(v).strip() for k, v in guardados[i].items() if k in ('proveedor', 'o_planta', 'o_alm', 'd_planta', 'd_alm')})
        if t['kind'] == 'TRASPASO' and i and not t['o_planta']:
            t['o_planta'], t['o_alm'] = out[i - 1]['d_planta'], out[i - 1]['d_alm']
        t['doc'] = 'ZPO' if t['kind'] == 'COMPRA' else doc_for(t['o_planta'], t['d_planta'])
        t['ecc'] = None
        if e is not None:
            if t['kind'] == 'TRASPASO' and t['o_planta'] and t['d_planta']:
                t['ecc'] = e.traslado(t['o_planta'], t['o_alm'], t['d_planta'], t['d_alm'])
            elif t['kind'] == 'COMPRA' and t['proveedor'] and t['d_planta']:
                t['ecc'] = e.compra(t['proveedor'], t['d_planta'], t['d_alm'])
        t['alm_qs4'] = ({'origen': (t['o_planta'], t['o_alm']) in t001l if t['o_alm'] else None,
                         'destino': (t['d_planta'], t['d_alm']) in t001l if t['d_alm'] else None} if t001l else None)
        out.append(t)
    return out


def bloque_tramo(t, material, org_override=None):
    """Data de un tramo con el formato del campo Data del UAT."""
    o = state['orgs'].get(t['d_planta'], {})
    ov = org_override or {}
    L = [f"C.Code: {ov.get('sociedad') or o.get('sociedad', '')}", f"P.Org: {ov.get('org_compras') or o.get('org_compras', '')}"]
    if t['kind'] == 'TRASPASO':
        L.append(f"Supplier Plant: {t['o_planta']}" + (f" ({t['o_alm']})" if t['o_alm'] else ''))
    L.append(f"Plant: {t['d_planta']}" + (f" ({t['d_alm']})" if t['d_alm'] else ''))
    L += ['-----------------------', f"Doc Type: {t['doc']}", '-----------------------']
    L.append(f"BP - Vendor: {t['proveedor']}" if t['kind'] == 'COMPRA' else f"BP - Vendor: P{t['o_planta']}")
    if material:
        L.append(f"Material: {material}")
    return '\n'.join(L)


def case_summary(c, asig):
    a = asig.get(c['id'], {})
    return {k: c[k] for k in ('id', 'new_id', 'l2', 'l3', 'location', 'scenario', 'flow', 'plants', 'n_steps')} | {
        'org_ok': bool(a.get('org_ok')),
        'stream': a.get('stream_override') or c['stream'], 'status': a.get('status', 'Pendiente'),
        'n_fields': sum(1 for v in a.get('fields', {}).values() if v)}


# Campos de «Datos elegidos» de logística que deben figurar en el Data según el flujo: (clave, etiqueta que se escribe, variantes que ya cuentan como «está», bloque)
_ORDEN_CAB = ['P.Org', 'S.Org', 'C.Code', 'P.Grp', 'Sup. Plant', 'Plant', 'St.Loc']
_CAMPOS_DATA = {
    'org_compras': ('P.Org', r'P\.\s?Org|Purchase Org', 'cab'), 'org_ventas': ('S.Org', r'S\.\s?Org|Sales Org', 'cab'), 'sociedad': ('C.Code', r'C\.\s?Code|Company Code', 'cab'),
    'grupo_compras': ('P.Grp', r'P\.\s?Gr(?:ou)?p|Purch(?:asing|ase)?\.?\s?Group', 'cab'), 'planta_emisora': ('Sup. Plant', r'Supplier Plant|Source Plant|Sup\.\s?Plant', 'cab'),
    'alm_receptora': ('St.Loc', r'St\.?\s?Loc|Storage Location', 'cab'), 'tipo_pedido': ('Doc Type', r'Doc\.?\s?Type|Order Type|Purchase order type', 'doc'),
    'proveedor': ('BP - Vendor', r'(?:BP\s*-\s*)?Vendor|Supplier(?! Plant)', 'bp'), 'cliente': ('BP - Customer', r'BP\s*-\s*Customer|Customer|BP', 'bp'),
}
_CLAVES_FLUJO = {
    'traslado': ('org_compras', 'sociedad', 'grupo_compras', 'planta_emisora', 'alm_receptora', 'tipo_pedido'),
    'compra': ('org_compras', 'sociedad', 'grupo_compras', 'alm_receptora', 'tipo_pedido', 'proveedor'),
    'venta': ('org_ventas', 'sociedad', 'tipo_pedido', 'cliente'),
}


def _inserta_faltantes(t, f, flow):
    """Lo que rellenas en «Datos elegidos» y el Data no tiene (p. ej. el grupo de compras) se AÑADE en su sitio: cabecera (organización, sociedad, plantas, almacén),
    clase de documento (entre rayas) y proveedor/cliente (antes del material). Solo si el campo tiene valor y no hay ninguna línea con ese nombre."""
    tipo = 'traslado' if flow in ('ZTRA', 'ZWIA', 'ZINT', 'ZINR') else ('compra' if flow in ('ZPO', 'ZSPO', 'ZSPA', 'ZSER') else ('venta' if flow == 'VENTA' else None))
    if not tipo or not t.strip():
        return t
    for clave in _CLAVES_FLUJO[tipo]:
        v = (f.get(clave) or '').strip()
        if not v or (clave == 'proveedor' and flow not in ('ZPO', 'ZSPO')):
            continue
        et, variantes, bloque = _CAMPOS_DATA[clave]
        if re.search(rf'(?im)^[ \t]*(?:{variantes})[ \t]*:', t):
            continue
        L = t.split('\n')
        sep = [i for i, x in enumerate(L) if re.fullmatch(r'[ \t]*-{3,}[ \t]*', x)]
        if bloque == 'cab':
            fin = sep[0] if sep else next((i for i, x in enumerate(L) if re.match(r'(?i)[ \t]*(?:BP\b|Material|Vendor|Customer)', x)), len(L))
            rango = _ORDEN_CAB.index(et)
            pos = 0
            for i in range(fin):
                m = re.match(r'[ \t]*([^:\n]{1,30}):', L[i])
                if not m:
                    continue
                for k, (et2, var2, _) in _CAMPOS_DATA.items():
                    if et2 in _ORDEN_CAB and re.fullmatch(var2, m.group(1).strip(), re.I) and _ORDEN_CAB.index(et2) < rango:
                        pos = i + 1
                if re.fullmatch(r'Plant\s*\d?', m.group(1).strip(), re.I) and _ORDEN_CAB.index('Plant') < rango:
                    pos = i + 1
            L.insert(pos, f'{et}: {v}')
        elif bloque == 'doc':
            if len(sep) >= 2:
                L.insert(sep[0] + 1, f'{et}: {v}')
            else:
                dentro = next((i for i, x in enumerate(L) if re.match(r'(?i)[ \t]*(?:BP\b|Material|Vendor|Customer)', x)), len(L))
                L[dentro:dentro] = ['-----------------------', f'{et}: {v}', '-----------------------']
        else:
            dentro = next((i for i, x in enumerate(L) if re.match(r'(?i)[ \t]*Materials?\b', x)), len(L))
            L.insert(dentro, f'{et}: {v}')
        t = '\n'.join(L)
    return t


def _reemplaza_sorg(t, nuevo):
    """S.Org del Excel = «org. de ventas / canal / sector» (p. ej. 9000 / 10 /10). Solo se toca si la organización (el primer número) es otra; si es la misma,
    la línea queda igual, y si cambia, se conserva el sufijo «/ canal / sector» original cuando el nuevo valor no trae el suyo."""
    def rep(m):
        actual = m.group(2)
        a1, n1 = re.match(r'\s*(\w*)', actual).group(1), re.match(r'\s*(\w*)', nuevo).group(1)
        if a1 == n1:
            return m.group(0)
        if '/' in nuevo:
            return m.group(1) + nuevo
        return m.group(1) + nuevo + actual[len(re.match(r'\s*\w*', actual).group(0)):]
    return re.sub(r'(?im)^(\s*(?:S\.Org|Sales Org)\s*:\s*)([^\n]*)', rep, t)


def _mapea_materiales(t, olds, news):
    """Texto de la Data con la selección marcada: (1) un original que sigue marcado se queda donde está; (2) cada material nuevo ocupa el hueco de un original
    no marcado (mejor del mismo tipo: «Material ZFIN:» o su tipo en QS4); (3) los originales sin sustituto se quitan; (4) los nuevos que sobran se añaden en la línea de su tipo o tras el último."""
    mt = _mtart()
    lab = {}
    for mm in re.finditer(r'(?im)^[ \t]*Material[ \t]+(Z[A-Z]{3})[ \t]*:[ \t]*([^\n]*)', t):
        for num in re.findall(r'\b\d{4,}\b', mm.group(2)):
            lab.setdefault(num, mm.group(1))
    tipo = lambda x: lab.get(x) or mt.get(x, '')
    libres = [o for o in olds if o not in news]
    nuevos = [n for n in news if n not in olds]
    par, sobran = {}, []
    for n in nuevos:
        k = next((o for o in libres if tipo(o) and tipo(o) == tipo(n)), None)
        if k is None and libres and not any(tipo(o) for o in libres):
            k = libres[0]
        if k is None:
            sobran.append(n)
        else:
            par[k] = n
            libres.remove(k)
    quitar = set(libres)
    SENT = '\x00'
    t = re.sub(r'\b(' + '|'.join(olds) + r')\b', lambda m: par.get(m.group(1), SENT if m.group(1) in quitar else m.group(1)), t)
    if SENT in t:                                              # limpiar los quitados: su línea, o su sitio dentro de una lista
        t = re.sub(r'(?m)^[ \t]*\x00[ \t]*\n', '', t)
        t = re.sub(r'[ \t]*,[ \t]*\x00', '', t)
        t = re.sub(r'\x00[ \t]*,[ \t]*', '', t)
        t = t.replace(SENT, '')
    t = re.sub(r'(?im)^([ \t]*Materials?[^:\n]*:)[ \t]*\n[ \t]*(\d{4,})', r'\1 \2', t)      # «Material:» vacío + lista debajo -> «Material: 543217»
    for e in sobran:
        tp = mt.get(e)
        ms = list(re.finditer(r'(?im)^[ \t]*Material[ \t]+' + re.escape(tp) + r'[ \t]*:[^\n]*(?:\n[ \t]*\d{4,}[^\n]*)*', t)) if tp else []
        if not ms:
            ms = list(re.finditer(r'(?im)^[ \t]*Material[^:\n]*:[^\n]*(?:\n[ \t]*\d{4,}[^\n]*)*', t))
        if ms:
            m = ms[-1]
            t = t[:m.end()] + ('\n' if '\n' in m.group(0) else ', ') + e + t[m.end():]
    return t


_MT = {'n': -1, 'm': {}}


def _mtart():
    """Tipo de material por número (MARA leída de QS4); se recalcula si cambian las tablas."""
    ra = state['tables'].get('MARA', [])
    if _MT['n'] != len(ra):
        _MT.update(n=len(ra), m={r['MATNR']: r.get('MTART', '') for r in ra})
    return _MT['m']


def rationale_caso(c, a):
    """EL RATIONAL: el motivo por el que se propone cada material (y por qué se descarta el original). Sale de las mismas comprobaciones que las listas de opciones
    (existe en la planta, sin estado ZZ, registro info, tipo de inspección y plan, datos de producción…), más stock, antecedente en ECC y reservas de otros casos."""
    f = (a or {}).get('fields') or {}
    stream = (a or {}).get('stream_override') or c['stream']
    plantas = c.get('plants') or [x_ for x_ in (f.get('planta_emisora'), f.get('planta')) if x_]      # sin planta en la Data, la que has escrito en el paso 1
    if not plantas:
        return None
    orden = plantas
    if stream == 'LOG' and c.get('flow') in ('ZTRA', 'ZWIA', 'ZINT', 'ZINR') and (c.get('roles') or {}).get('emisora'):
        e0 = c['roles']['emisora'][0]
        orden = [e0] + [p_ for p_ in plantas if p_ != e0]
    plant = (f.get('planta_emisora') or f.get('planta') or orden[0]).upper()
    plant2 = (f.get('planta_receptora') or ','.join(orden[1:])).upper() if stream == 'LOG' else ''
    sel = [x for x in re.split(r'[,;\\s]+', f.get('material', '') or '') if x]
    opt = Options(state['tables'], reserved_map(load_asig(), exclude=c['id']), state['orgs'])
    opt.ecc = ecc()
    obj = objetivo_pp(c['scenario']) if stream == 'PP' else None
    try:
        secs = opt.for_stream(stream, plant, c.get('flow'), plant2, False, f.get('proveedor', '') if stream == 'LOG' else '', obj, con_puesto(c), flecha_data(c), qm_requisitos(c) if stream == 'QM' else None, sel)
    except Exception:
        return None
    filas = {str(r.get('Material')): r for r in (secs[0]['rows'] if secs else []) if r.get('Material')}
    ex = {str(x['material']): x for x in excel_vs_opciones(c, secs)}

    def motivo_fila(r):
        if r.get('Motivo'):
            return r['Motivo']
        trozos = [f"{k} {r[k]}" for k in ('Lista mat.', 'Hoja ruta', 'Versión fab.', 'Cost collector') if r.get(k) not in (None, '', '✗', '—')]
        faltan = [k for k in ('Lista mat.', 'Hoja ruta', 'Versión fab.', 'Cost collector') if r.get(k) in ('✗',)]
        return ('Producto completo: ' + ', '.join(trozos)) if r.get('Completo') == 'SÍ' else ('Faltan: ' + ', '.join(faltan) if faltan else ', '.join(trozos))

    def item(m, papel):
        r = filas.get(m)
        if r:
            ok = r.get('Apto') or r.get('Completo')
            return {'material': m, 'papel': papel, 'valido': ok == 'SÍ' if ok else None, 'tipo': r.get('Tipo', ''), 'motivo': motivo_fila(r),
                    'stock': r.get('Stock libre', ''), 'ecc': r.get('En ECC', ''), 'reservado': r.get('Reservado por', '')}
        x = ex.get(m)
        mot = (x or {}).get('Motivo') or ('Repuesto: no se lee de QS4, hay que validarlo a mano' if (x or {}).get('excluido') else 'No existe en la planta ' + plant)
        return {'material': m, 'papel': papel, 'valido': False, 'tipo': (x or {}).get('Tipo', ''), 'motivo': mot, 'stock': '', 'ecc': '', 'reservado': ''}
    items = []
    if sel:
        for m in sel:
            items.append(item(m, 'Original que se mantiene' if m in ex else 'Propuesto'))
        for m in ex:
            if m not in sel:
                items.append(item(m, 'Original descartado'))
    else:
        for m in ex:
            items.append(item(m, 'Original de la Data'))
    prov = None
    if f.get('proveedor') and stream == 'LOG':
        sec = next((x for x in secs if x.get('tipo') == 'PROVEEDOR'), None)
        r = next((r_ for r_ in (sec or {}).get('rows', []) if str(r_.get('Proveedor')).lstrip('0') == str(f['proveedor']).lstrip('0')), None)
        if r:
            prov = {'proveedor': f['proveedor'], 'valido': r.get('Apto') == 'SÍ', 'motivo': r.get('Motivo', ''), 'registros_info': r.get('Registros info', ''), 'ecc': r.get('En ECC', '')}
    notas = [x for x in ((a or {}).get('hallazgo'), (a or {}).get('note')) if x]
    return {'estado': (a or {}).get('status') or 'Pendiente', 'auto': bool((a or {}).get('auto')), 'resumen': (a or {}).get('resumen') or '', 'planta': plant,
            'materiales': items, 'proveedor': prov, 'notas': notas}


def _derivados_caso(c, f, planta=''):
    """Lista de materiales, hoja de ruta, versión y cost collector del primer material del caso en su planta (de lo leído de QS4). Lo que el usuario haya puesto en «Datos elegidos» manda."""
    mats = [x for x in re.split(r'[,;\s]+', str((f or {}).get('material') or '')) if x] or mats_de_data(c)
    pl = planta or (f or {}).get('planta') or (c.get('plants') or [''])[0]
    d = derivados.derivar(state['tables'], mats[0], pl) if mats and pl else {}
    for k2 in ('hoja_ruta', 'lista_materiales', 'version_fabricacion', 'cost_collector', 'puesto_trabajo'):
        if (f or {}).get(k2):
            d[k2] = f[k2]
    return d


def _limpia_pasos(x):
    """{paso: {campo: valor}} sin vacíos."""
    return {str(k): {str(kk): str(vv).strip() for kk, vv in (v or {}).items() if str(vv).strip()} for k, v in (x or {}).items() if v}


def _limpia_pc(x):
    """{paso: {'add': [...], 'quitar': [...]}} sin vacíos."""
    out = {}
    for k, v in (x or {}).items():
        add, quitar = [str(i) for i in (v or {}).get('add', [])], [str(i) for i in (v or {}).get('quitar', [])]
        if add or quitar:
            out[str(k)] = {'add': add, 'quitar': quitar}
    return out


def _ctx_para_paso(c, a, idx, t, paso_tramo, con_overrides=True):
    """Valores con los que se pinta el Data del paso idx: caso (Datos elegidos, plantas, organización…) + extras + lo escrito para ESE paso (si con_overrides)."""
    f = a.get('fields', {})
    ctx_ = _ctx_modelo(c, f, paso_tramo.get(idx))
    ctx_.update({k_: str(v_).strip() for k_, v_ in (a.get('extras') or {}).items() if str(v_).strip()})
    ctx_['_fabrica'] = modelo_tx.tx_key(c['steps'][idx].get('Transaction')) in modelo_tx.FABRICA
    ctx_['_comp'] = con_puesto(c) and bool(re.search(r'stag|consum|component|goods issue|\b261\b|\b262\b', ' '.join([str(c['steps'][idx].get('Test Step Description') or ''), str(c.get('scenario') or ''), t or '']), re.I))      # staging / consumo: llevan componentes
    ctx_['_puesto'] = con_puesto(c)      # PP salvo datos maestros: Production line por defecto en todos los pasos
    orig_ = parse_data.parse(t)
    ctx_['org_ventas_original'] = (orig_.get('SOrg') or [''])[0]
    ov = ((a.get('pasos') or {}).get(str(idx)) or {}) if con_overrides else {}
    if 'material' not in ov and re.search(r'(?im)^[ \t]*Material[ \t]+Z[A-Z]{3}[ \t]*:', t):      # «Material ZRAW: …», «Material ZPAC: …» (calidad): se mantienen los tipos
        bloque_m = '\n'.join(m_.group(0) for m_ in re.finditer(r'(?im)^[ \t]*Materials?[^:\n]*:[^\n]*(?:\n[ \t]*\d{4,}[^\n]*)*', t))
        olds_m = list(dict.fromkeys(re.findall(r'\b\d{5,8}\b', bloque_m)))
        news_m = [x.strip() for x in re.split(r'[,;\s]+', f.get('material', '')) if x.strip()]
        ctx_['_material_lineas'] = _mapea_materiales(bloque_m, olds_m, news_m) if (olds_m and news_m) else bloque_m
    ctx_.update({k_: str(v_).strip() for k_, v_ in ov.items() if str(v_).strip()})
    return ctx_, orig_


def form_caso(c, a):
    """Formulario de la sección 3, POR PASO: cada paso con los campos que pide su transacción (modelo) más los que el usuario le haya añadido o quitado, con su valor.
    valor = lo que sale en el Data; auto = lo que saldría sin lo escrito para ese paso; editado = hay un valor propio de ese paso."""
    a = a or {}
    tv = tramos_vista(c, a) if c.get('tramos') and a.get('tramos') else []
    paso_tramo = {i: t for t in tv for i in t['steps']}
    pasos = []
    for idx, st in enumerate(c['steps']):
        tx = modelo_tx.tx_key(st.get('Transaction'))
        t = st.get('Data', '') or ''
        esp = modelo_tx.especificacion(st.get('Transaction'))
        pref_prev = parse_data.prev_data(t)[0]
        pc = (a.get('pasos_campos') or {}).get(str(idx)) or {}
        activo = esp is not None or bool(pc.get('add') or pc.get('quitar') or (a.get('pasos') or {}).get(str(idx)))      # fuera del libro, el texto solo se genera si el usuario toca algo
        base = {'idx': idx, 'n': st.get('n') or idx + 1, 'tx': tx, 'desc': re.sub(r'\s+', ' ', st.get('Test Step Description') or '')[:70], 'en_modelo': True, 'modelo': esp is not None, 'activo': activo, 'items': [], 'pd': []}
        if base['en_modelo']:
            if pref_prev:                                    # «Prev.Data» en el Excel: parte de sus datos previos (los que enlaza) y de lo que traiga detrás
                _, descs_f, resto_f = parse_data.prev_data(t)
                esp = [{'tipo': 'pd', 'desc': d_, 'opc': False} for d_ in (descs_f or [''])] + modelo_tx.specs_data(parse_data.parse(resto_f))
                t = resto_f
            elif esp is None:
                esp = modelo_tx.specs_data(parse_data.parse(t))
            esp2 = modelo_tx.ajusta(esp, pc.get('add'), pc.get('quitar'))
            ctx_con, orig_ = _ctx_para_paso(c, a, idx, t, paso_tramo, True)
            ctx_sin, _ = _ctx_para_paso(c, a, idx, t, paso_tramo, False)
            r_con = modelo_tx.calcula(esp2, ctx_con, orig_, c.get('flow'), st.get('Transaction'))
            auto = {it['clave']: it['valor'] for it in modelo_tx.calcula(esp2, ctx_sin, orig_, c.get('flow'), st.get('Transaction'))['items']}
            ov = (a.get('pasos') or {}).get(str(idx)) or {}
            base['items'] = [{'clave': it['clave'], 'etiqueta': it['etiqueta'], 'opc': it['opc'], 'valor': it['valor'], 'auto': auto.get(it['clave'], ''),
                              'editado': bool(str(ov.get(it['clave'], '')).strip())} for it in r_con['items']]
            base['pd'] = r_con['pds']
        pasos.append(base)
    return {'pasos': pasos, 'catalogo': [{'clave': k, 'etiqueta': v} for k, v in modelo_tx.catalogo()]}


def _ctx_modelo(c, f, tr):
    """Valores conocidos del caso para pintar el Data de un paso: lo elegido en «Datos elegidos» y, si falta, lo que dicen la Data, las plantas, el tramo y la estructura organizativa."""
    ctx = dict(f)
    roles = c.get('roles') or {}
    emi = (roles.get('emisora') or [''])[0]
    rec = next((p_ for p_ in (roles.get('receptora') or []) if p_ != emi), '')
    plantas = c.get('plants') or []
    ctx['planta_emisora'] = f.get('planta_emisora') or emi
    ctx['planta_receptora'] = f.get('planta_receptora') or rec or ('' if emi else (plantas[0] if plantas else ''))
    ctx['planta'] = f.get('planta') or ('' if emi and rec else (plantas[0] if plantas else ''))
    if tr:                                                   # caso encadenado: cada paso usa las plantas y el proveedor de SU tramo
        ctx['planta_emisora'] = tr.get('o_planta') or ctx['planta_emisora']
        ctx['planta_receptora'] = tr.get('d_planta') or ctx['planta_receptora']
        ctx['planta'] = tr.get('d_planta') or ctx['planta']
        if tr.get('kind') == 'COMPRA' and tr.get('proveedor'):
            ctx['proveedor'] = tr['proveedor']
    pl_org = ctx['planta_receptora'] or ctx['planta'] or ctx['planta_emisora']
    if c.get('flow') == 'VENTA':
        pl_org = ctx['planta'] or pl_org
    org = state['orgs'].get(pl_org, {}) if pl_org else {}
    fl = c.get('flow')
    ctx['def'] = {'sociedad': org.get('sociedad', ''), 'org_compras': org.get('org_compras', ''),
                  'org_ventas': (org.get('org_ventas_lista') or [''])[0] if org else '',
                  'tipo_pedido': ((c.get('docs') or [''])[0] if fl in ('VENTA', 'TRANSPORTE') else fl) or ''}
    ctx['almacen'] = f.get('almacen') or f.get('alm_receptora') or ''
    costes = (objetivo_pp(c.get('scenario')) or '').startswith('COST')      # casos de costes: lista de costes (uso 6) y hoja de ruta de tasa (tipo R)
    dflt = ctx.setdefault('def', {})
    dflt.update({'bom_tipo': '6' if costes else '1', 'ruta_tipo': 'R' if costes else 'N', 'ruta_cont': '01',
                 'almacen': '1000', 'alm_emisora': '1000', 'alm_receptora': '1000', 'lote': '<< get from the system >>'})      # almacén 1000 por defecto; el lote lo da el sistema
    ctx['_una_planta'] = len(set(c.get('plants') or [])) <= 1
    for k_, v_ in _derivados_caso(c, f, ctx.get('planta') or ctx.get('planta_emisora') or ctx.get('planta_receptora') or '').items():
        if v_ and k_ not in ('bom_tipo', 'ruta_tipo', 'ruta_cont'):
            dflt[k_] = v_
    return ctx


def data_proposal(c, a):
    """Sustituye valores dentro del texto existente (material/planta viejos -> nuevos) para conservar el formato."""
    f = a.get('fields', {})
    out = []
    tv = tramos_vista(c, a) if c.get('tramos') and a.get('tramos') else []
    paso_tramo = {i: t for t in tv for i in t['steps']}
    for idx, s in enumerate(c['steps']):
        t = s.get('Data', '') or ''
        pref_prev, descs_prev, resto_prev = parse_data.prev_data(t)
        pc_p = (a.get('pasos_campos') or {}).get(str(idx)) or {}
        if pref_prev and (pc_p.get('add') or pc_p.get('quitar') or (a.get('pasos') or {}).get(str(idx))):      # «Prev.Data» en el Excel + el usuario le ha tocado algo: se genera desde el formulario
            esp_p = modelo_tx.ajusta([{'tipo': 'pd', 'desc': d_, 'opc': False} for d_ in (descs_prev or [''])] + modelo_tx.specs_data(parse_data.parse(resto_prev)), pc_p.get('add'), pc_p.get('quitar'))
            ctx_p, orig_p = _ctx_para_paso(c, a, idx, resto_prev, paso_tramo, True)
            out.append(modelo_tx.render(esp_p, ctx_p, orig_p, c.get('flow'), s.get('Transaction')))
            continue
        if pref_prev and not resto_prev.strip():      # paso de chequeo («Prev.Data»): no mete datos, se deja tal cual
            out.append(t)
            continue
        if not pref_prev:                              # Data CENTRALIZADO POR TRANSACCIÓN (config/transacciones_modelo.xlsx) y ajustable POR PASO (campos propios y valores propios)
            esp = modelo_tx.especificacion(s.get('Transaction'))
            pc = (a.get('pasos_campos') or {}).get(str(idx)) or {}
            if esp is None and (pc.get('add') or pc.get('quitar') or (a.get('pasos') or {}).get(str(idx))):      # fuera del libro: se parte de los campos de su Data del Excel
                esp = modelo_tx.specs_data(parse_data.parse(t))
            if esp is not None:
                esp = modelo_tx.ajusta(esp, pc.get('add'), pc.get('quitar'))
                ctx_, orig_ = _ctx_para_paso(c, a, idx, t, paso_tramo, True)
                out.append(modelo_tx.render(esp, ctx_, orig_, c.get('flow'), s.get('Transaction')))
                continue
        lineas_prev = [ln for ln in resto_prev.split('\n') if re.match(r'(?i)^\s*prev\.?\s*data\b', ln)]      # «Prev.Data (…)» suelto en su línea: se conserva al final
        if lineas_prev:
            resto_prev = '\n'.join(ln for ln in resto_prev.split('\n') if ln not in lineas_prev)
            if not resto_prev.strip():
                out.append(t)
                continue
        t = resto_prev                                 # si lleva más datos detrás de la coma, esos se tratan como siempre y el prefijo se conserva
        tr = paso_tramo.get(idx)
        base_tr = c['tramos'][tr['n'] - 1] if tr and tr['n'] - 1 < len(c['tramos']) else None
        igual_data = bool(base_tr) and all(str(tr.get(k, '')) == str(base_tr.get(k, '')) for k in ('o_planta', 'o_alm', 'd_planta', 'd_alm', 'proveedor'))
        if tr and not igual_data and tr['d_planta'] and (tr['kind'] == 'COMPRA' or tr['o_planta']):      # solo si el tramo ya no es el de la Data; si no, se conserva el texto original
            mat = f.get('material') or ', '.join(dict.fromkeys(re.findall(r'\b\d{5,8}\b', ' '.join(parse_data.parse(t).get('Material', [])))))
            out.append(pref_prev + bloque_tramo(tr, mat, {k: f.get(k, '') for k in ('sociedad', 'org_compras')} if tr['n'] == 1 else None))
            continue
        d = parse_data.parse(t)
        old_m = re.findall(r'\b\d{5,8}\b', ' '.join(d.get('Material', [])))
        olds = list(dict.fromkeys(old_m))
        news = [x.strip() for x in re.split(r'[,;\s]+', f.get('material', '')) if x.strip()]
        if olds and news and c['stream'] in ('QM', 'LOG', 'PP'):      # lo MARCADO manda: los originales marcados se quedan, los nuevos ocupan el hueco de uno no marcado, los desmarcados se quitan
            t = _mapea_materiales(t, olds, news)
        elif (c['stream'] == 'PP' and olds and news and sorted(news) != sorted(olds)
              and (objetivo_pp(c['scenario']) or '').split(':')[0] in ('MATERIAL', 'BOM', 'RUTA', 'VERSION', 'CC', 'COSTBOM', 'COSTRUTA', 'COSTPV', 'COSTLIB', 'VERSIONSEL')):
            # el producto que has elegido sustituye a TODA la lista de materiales de la Data (que traía producto + componente…)
            num_ = r'\d{4,}(?:[ \t]*[,;][ \t]*\d{4,})*[ \t]*'
            t = re.sub(r'(?im)^([ \t]*Materials?[^:\n]*:[ \t]*)(' + num_ + r'(?:\n[ \t]*' + num_ + r')*)', lambda m: m.group(1) + ', '.join(news), t, count=1)
        elif olds and len(news) == len(olds):      # PP: sustitución 1 a 1 en orden; si no cuadran, no se toca
            t = re.sub(r'\b(' + '|'.join(olds) + r')\b', lambda m: news[olds.index(m.group(1))], t)
        elif not olds and news:      # marcador «Material: XXXXX» en la Data: se rellena con los materiales elegidos
            t = re.sub(r'(?im)^([ \t]*Material[^:\n]*:[ \t]*)X{3,}\b', lambda m: m.group(1) + ', '.join(news), t)
        def _pl(t, lab, pl, alm):
            return re.sub(rf'(?im)^(\s*(?:{lab})\s*:\s*)(?:[CLMS]\d{{3}}|\d{{4}})(\s*\(\w{{1,4}}\))?',
                          lambda m: m.group(1) + pl + (f' ({alm})' if alm else (m.group(2) or '')), t)
        sin_alm = c.get('flow') == 'VENTA'      # una venta no lleva almacén en la Data: no se añade «(1000)» tras la planta
        con_stloc = bool(re.search(r'(?im)^\s*(?:St\.? ?Loc\.?|Storage Location)\s*:', t))      # si la Data ya tiene su línea de almacén, no se añade «(almacén)» tras la planta
        if f.get('planta_emisora'):
            t = _pl(t, r'Supplier Plant|Source Plant|Sup\. Plant', f['planta_emisora'], '' if (con_stloc or sin_alm) else f.get('alm_emisora', ''))
        if f.get('planta_receptora'):
            t = _pl(t, 'Plant', f['planta_receptora'], '' if (con_stloc or sin_alm) else f.get('alm_receptora', ''))
        elif f.get('planta'):
            t = _pl(t, 'Plant', f['planta'], '' if (con_stloc or sin_alm) else f.get('alm_receptora', ''))
        for key, lab in (('alm_receptora', r'St\.? ?Loc\.?|Storage Location'), ('tipo_pedido', r'Doc\.? ?Type|Order Type'),
                         ('grupo_compras', r'P\.? ?Gr(?:ou)?p\.?|Purch(?:asing|ase)? Group'), ('proveedor', r'(?:BP\s*-\s*)?(?:Vendor|Supplier(?! Plant))'), ('cliente', r'BP\s*-\s*Customer|Customer|BP')):
            if f.get(key) and (key not in ('proveedor', 'cliente') or (key == 'proveedor' and c.get('flow') in ('ZPO', 'ZSPO')) or (key == 'cliente' and c.get('flow') == 'VENTA')):
                t = re.sub(rf'(?im)^(\s*(?:{lab})\s*:\s*)[^\n]*', lambda m, v=f[key]: m.group(1) + v, t)
        for key, lab in (('sociedad', r'C\.Code|Company Code'), ('org_compras', r'P\.Org|Purchase Org')):
            if f.get(key):
                t = re.sub(rf'(?im)^(\s*(?:{lab})\s*:\s*)[^\n]*', lambda m, v=f[key]: m.group(1) + v, t)
        if f.get('org_ventas'):
            t = _reemplaza_sorg(t, f['org_ventas'])
        if f.get('puesto_trabajo') and d.get('Material'):          # el puesto de trabajo va junto al material propuesto
            linea = f"Work Center: {f['puesto_trabajo']}"
            pat = r'(?im)^\s*(?:work ?cent(?:er|re)|puesto[^:\n]*)\s*:[^\n]*'
            t = re.sub(pat, linea, t) if re.search(pat, t) else t.rstrip() + '\n' + linea
        if f.get('componentes') and d.get('Material'):             # componentes elegidos: entre paréntesis al lado del producto (el último material de la línea de materiales)
            comps_ = ', '.join(x.strip() for x in re.split(r'[,;]', f['componentes']) if x.strip())
            def _con_comp(m):
                vals = m.group(2)
                vals = re.sub(r'\s*\([^)]*\)\s*$', '', vals.rstrip())            # sin duplicar si ya llevaba paréntesis
                return m.group(1) + vals + f' ({comps_})'
            t = re.sub(r'(?im)^([ \t]*Materials?[^:\n]*:[ \t]*)([^\n]*)$', _con_comp, t, count=1)
        if c['stream'] == 'LOG':
            t = _inserta_faltantes(t, f, c.get('flow'))
        out.append(pref_prev + t + (('\n' + '\n'.join(lineas_prev)) if lineas_prev else ''))
    return out


QS4 = {'estado': 'libre', 'items': [], 'paso': 0, 'total': 0, 'sistema': '', 'error': None}


def qs4_items(cid, plants, stream, forzar=False, vendor='', refrescar=(), flow=None):
    from engine import qs4_plan
    c = state['cases'].get(cid) or {}
    items = []
    for plant in dict.fromkeys(p for p in plants if p):
        org = Options(state['tables'], None, state['orgs']).org(plant)
        items += qs4_plan.plan(stream, plant, flow or c.get('flow'), org)
    if vendor:
        items += qs4_plan.plan_vendors(vendor.split(','), 'ZINT') if ',' in vendor else qs4_plan.plan_vendor(vendor)
    excl = sorted((int(a), int(b)) for a, b in ((CFG.get('exclusiones') or {}).get('matnr', [])))
    if excl:                 # las tablas por material se leen en los rangos que NO están excluidos (la exclusión se hace en SAP)
        desde, rangos = 1, []
        for a, b in excl:
            if a > desde:
                rangos.append([desde, a - 1])
            desde = b + 1
        rangos.append([desde, 99999999])
        def trocear(rs, paso=100000, tope=1000000):      # trozos de 100.000 materiales: ninguna parte supera lo que SAP aguanta de una vez
            out = []
            for a, b in rs:
                while a <= b:
                    fin = min(b, (a // paso + 1) * paso - 1 if a < tope else b)
                    out.append([a, fin])
                    a = fin + 1
            return out
        for i in items:
            if i['stage'] == 1 and i['table'] in ('MARC', 'MARD', 'MKAL', 'MAST', 'MAPL', 'QMAT', 'LQUA'):
                i['rangos_matnr'] = trocear(rangos) if i['table'] == 'LQUA' else rangos
    if not forzar:      # no se repite lo que ya está descargado en data/raw
        items = [i for i in items if not fichero_ok(i['name'], i['table']) or i['name'] in set(refrescar)]      # lo que falta + lo que el usuario marcó
    return items


SAPCON = {'estado': 'libre', 'texto': '', 'error': None}


def sap_conectar(status):
    """Abre/entra en QS4 con la credencial guardada (sap/login.py). Un solo intento; devuelve el resultado o lanza LoginError."""
    sys.path.insert(0, str(ROOT / 'sap'))
    import login
    import on_demand
    return on_demand.com(lambda: login.conectar(CFG['sap'], status))     # mismo hilo COM que las consultas


def sap_worker():
    try:
        SAPCON.update(estado='conectando', texto='', error=None)
        SAPCON['texto'] = sap_conectar(SAPCON)
        SAPCON['estado'] = 'conectado'
    except Exception as e:
        SAPCON.update(estado='error', error=str(e))


def credencial_guardada():
    try:
        sys.path.insert(0, str(ROOT / 'sap'))
        import credencial
        return credencial.hay()
    except Exception:
        return None


def con_puesto(c):
    """Desde planificación en adelante (todo PP salvo 5.1.1 datos maestros) el caso también necesita el puesto de trabajo."""
    return bool(c) and c.get('stream') == 'PP' and not str(c.get('l3', '')).startswith('5.1.1')


def fichero_ok(name, table):
    """Un fichero descargado vale si trae todas las columnas que hoy pide la receta (si se añadió una, hay que volver a leerlo)."""
    f = ROOT / CFG['paths']['raw_dir'] / (name + '.txt')
    if not f.exists():
        return False
    e0 = next((e for e in EXTR if e['table'] == table), {})
    need = (e0.get('output_fields') or []) + (e0.get('extra_fields') or [])      # extra_fields: se piden, pero un fichero antiguo sin ellas sigue siendo legible
    try:
        with f.open(encoding='utf-8', errors='ignore') as fh:
            head = fh.readline().rstrip('\r\n').split('\t')
    except OSError:
        return False
    return all(x in head for x in need)


def flecha_data(c):
    """La Data de esa unidad escribe los materiales como «A -> B» (componente -> producto)."""
    return bool(c) and any(re.search(r'\d+\s*-{1,2}>\s*\d+', st.get('Data') or '') for st in c['steps'])


def _tipo_mat(w):
    w = (w or '').lower()
    for k, v in (('raw', 'ZRAW'), ('semi', 'ZSEM'), ('formul', 'ZFOR'), ('finish', 'ZFIN'), ('pack', 'ZPAC')):
        if k in w:
            return v
    return None


def objetivo_pp(scenario):
    """Qué CREA el caso (si crea algo): de ahí sale lo que necesita para poder ejecutarse."""
    t = (scenario or '').lower()
    if 'agribusiness' in t or 'rf devices' in t:
        return None
    if 'production version selection' in t:
        return 'VERSIONSEL'
    if 'costing bom creation' in t:
        return 'COSTBOM'
    if 'costing rate routing creation' in t:
        return 'COSTRUTA'
    if 'costing product version creation' in t:
        return 'COSTPV'
    if 'release product costing' in t:
        return 'COSTLIB'
    m = re.search(r'material status (\w\w)\b', t) or re.search(r'change status of material\s+\w+\s+(\w\w)\s*->', t)
    if m:
        return 'ESTADO:' + m.group(1).upper()
    mp = re.search(r'planned orders:\s*(.+?)\s*->\s*(\w+)', t)
    if mp and _tipo_mat(mp.group(1)) and _tipo_mat(mp.group(2)):
        return f'PLAN:{_tipo_mat(mp.group(1))}:{_tipo_mat(mp.group(2))}'
    ms = re.search(r'stagging\s+(.+?)\s+-\s+(?:reservation-based|direct transfer)', t)
    if ms:
        return 'STAGE:' + (_tipo_mat(ms.group(1)) or '*')
    if 'subproducts' in t:
        return 'SUBPROD'
    if any(k in t for k in ('mfbf', 'consumption', 'good reception', 'null receptions')):
        return 'MFBF'
    if 'material creation' in t:
        return 'MATERIAL'
    if 'bom creation' in t:
        return 'BOM'
    if 'routing creation' in t:
        return 'RUTA'
    if 'product version creation' in t:
        return 'VERSION'
    if 'cost colector creation' in t or 'cost collector creation' in t:
        return 'CC'
    return None


def mats_de_data(c):
    from engine import parse_data
    mats = []
    for st in c['steps']:
        for v in parse_data.parse(st.get('Data', '')).get('Material', []):
            for t in re.split(r'[,\s;/]+', v):
                if re.fullmatch(r'\d{4,}', t) and t not in mats:
                    mats.append(t)
    return mats


def en_rango_excluido(m):
    """Material dentro de los rangos que NO se leen de QS4 (p. ej. repuestos 80000000–89999999)."""
    try:
        n = int(str(m).strip())
    except ValueError:
        return False
    return any(int(a) <= n <= int(b) for a, b in ((CFG.get('exclusiones') or {}).get('matnr', [])))


def excel_vs_opciones(c, secs):
    """Materiales que ya trae la Data del Excel, contrastados con lo leído de QS4 (el Excel manda: primero se comprueba lo suyo)."""
    if not c or not secs:
        return []
    mats = mats_de_data(c)
    idx = {}
    for sec in secs:
        for r in sec['rows']:
            idx.setdefault(r.get('Material'), r)
    cols = ('Tipo', 'Lista mat.', 'Hoja ruta', 'Puesto trabajo', 'Versión fab.', 'Cost collector', 'Completo', 'Apto', 'Motivo', 'Almacén', 'Stock libre')
    lab = {}      # tipo que dice la propia Data («Material ZFIN: 123»), por si el material no existe en la planta y no se puede leer su tipo de QS4
    for st in c['steps']:
        for mm in re.finditer(r'(?im)^[ \t]*Material[ \t]+(Z[A-Z]{3})[ \t]*:[ \t]*([^\n]*)', st.get('Data') or ''):
            for num in re.findall(r'\b\d{4,}\b', mm.group(2)):
                lab.setdefault(num, mm.group(1))
    out = [{'material': m, 'existe': m in idx, **{k: (idx[m].get(k, '') if m in idx else '') for k in cols}} for m in mats]
    for x in out:
        if not x['Tipo']:
            x['Tipo'] = lab.get(x['material'], '')
    for x in out:
        x['excluido'] = (not x['existe']) and en_rango_excluido(x['material'])
        if x['excluido']:
            x['Motivo'] = 'Repuesto: no se lee de QS4 (rango excluido); hay que validarlo a mano'
    return out


def freno_activo():
    """True si el último login con la credencial guardada falló (login.py no reintenta hasta guardar otra)."""
    try:
        sys.path.insert(0, str(ROOT / 'sap'))
        import credencial
        import login
        return bool(credencial.hay()) and login._frenado(credencial.marca())
    except Exception:
        return False


def matar_sap():
    """Cierra SAP Logon y todas sus sesiones (también la del usuario): solo con autorización expresa («autocurar»)."""
    import subprocess
    subprocess.run(['taskkill', '/F', '/IM', 'saplogon.exe'], capture_output=True)
    time.sleep(5)


def qs4_worker(items, autocurar=False):
    import importlib
    sys.path.insert(0, str(ROOT / 'sap'))
    try:
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)      # mientras se lee de SAP el equipo no se duerme
    except Exception:
        pass
    try:
        QS4['paso_texto'] = 'conectando con SAP'
        sap_conectar(QS4)                 # si ya estás dentro no hace nada; si no, abre QS4 y entra (un solo intento)
        od = importlib.import_module('on_demand')
        campos = {e['table']: (e.get('output_fields') or []) + (e.get('extra_fields') or []) for e in EXTR}
        pendientes, intento = items, 0
        od.FACTOR[0] = 1.0
        while True:
            try:
                od.run(pendientes, CFG['sap'], str(ROOT / CFG['paths']['raw_dir']), readers, QS4, campos)
                break
            except TimeoutError as e:                      # SAP colgado: el vigilante abandonó la lectura
                intento += 1
                for i in QS4['items']:
                    if i['estado'] == 'consultando':
                        i['estado'], i['error'] = 'error', 'SAP colgado'
                if not autocurar or intento > 3:
                    raise
                QS4['paso_texto'] = f'SAP colgado: se cierra y se reintenta ({intento}/3) con trozos más pequeños'
                matar_sap()
                od.FACTOR[0] *= 0.5
                hechas = {i['name'] for i in QS4['items'] if i['estado'] in ('ok', 'sin resultados', 'omitida')}
                pendientes = [it for it in items if it['name'] not in hechas]
                QS4['total'] = QS4.get('total', 0) + len(pendientes)
                QS4['avance'] = time.time()
                sap_conectar(QS4)                          # vuelve a abrir QS4 y entrar (un solo intento)
        QS4['paso_texto'] = 'cargando los datos nuevos'
        build()                       # primero se recargan las tablas...
        QS4['estado'] = 'terminado'   # ...y solo entonces el front pide las opciones
    except Exception as e:
        QS4['estado'], QS4['error'] = 'error', f'{type(e).__name__}: {e}'
        try:
            build()
        except Exception:
            pass
    finally:
        try:
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)      # se libera: el equipo vuelve a poder dormirse
        except Exception:
            pass


def usados_(ex):
    return {x['material'] for x in ex}


def qm_requisitos(c):
    """Lo que exige un caso de calidad (reglas del usuario): tipo de inspección habilitado, plan de inspección del uso que toca y, si es de orden planificada,
    lista + ruta + versión + cost collector. Solo se exige donde el escenario lo dice; el resto se muestra sin juzgar."""
    s = ((c or {}).get('scenario') or '').lower()
    if 'planned order' in s:
        return {'arts': ['ZQMPP*'], 'uso': '1', 'orden': True, 'plan': True,
                'texto': 'Inspección de orden planificada. Sirve si: tiene habilitado el tipo de inspección de producción (cualquiera de la familia ZQMPP*) en la planta · tiene plan de inspección tipo Q de uso 1 · y tiene lista de materiales, hoja de ruta, versión de fabricación y cost collector.'}
    if 'incoming goods' in s:
        return {'arts': ['ZQMEM*'], 'uso': '5', 'orden': False, 'plan': True,
                'texto': 'Inspección de entrada de mercancías. Sirve si: tiene habilitado el tipo de inspección de recepción (cualquiera de la familia ZQMEM*) en la planta · y tiene plan de inspección tipo Q de uso 5 (recepciones).'}
    if 'stock transfer' in s:
        return {'arts': ['Z08', '08'], 'uso': '8', 'orden': False, 'plan': True,
                'texto': 'Inspección de traslado (STO). Sirve si: tiene habilitado el tipo de inspección Z08 (o 08) en la planta · y tiene plan de inspección tipo Q de uso 8 (traslados).'}
    if 'manual inspection lot' in s:
        return {'arts': ['Z89', '89'], 'uso': '', 'orden': False, 'plan': True,
                'texto': 'Lote de inspección manual. Sirve si: tiene habilitado el tipo de inspección Z89 (o 89) en la planta · y tiene un plan de inspección tipo Q.'}
    if 'inspection plan' in s:
        return {'arts': [], 'uso': '', 'orden': False, 'plan': True,
                'texto': 'Plan de inspección. Sirve si el material ya tiene un plan de inspección tipo Q en la planta.'}
    return None


def modo_auto(c):
    """auto = se propone; comprobar = solo se comprueba la Data; manual = sin dato que proponer; wm = depende de la fase WM."""
    t = (c['scenario'] or '').lower()
    if 'rf devices' in t:
        return 'wm'
    if any(k in t for k in ('product recipe', 'fixed sending', 'forms / instruction', 'repackaging', 'send the stock to azo', 'label re-printing', 'migo - for every material', 'agribusiness')):
        return 'manual'
    if str(c['l3']).startswith('5.1.6') or any(k in t for k in ('redistribution', 'pp/ds')):
        return 'comprobar'
    return 'auto'


def enlaza_pares(c):
    """La Data enlaza dos materiales («A -> B», «A - B»): no se sabe cuál es cada uno, no se sustituye solo."""
    return any(re.search(r'\d+\s*(?:-{1,2}>|→|-)\s*\d+', st.get('Data') or '') for st in c['steps'])


def plantas_completas(stream='PP'):
    """Plantas del stream con TODAS sus tablas leídas de QS4 (solo en esas se puede proponer con garantías)."""
    from engine import qs4_plan
    pl = {p_ for c in state['cases'].values() if c['stream'] == stream and c['plants'] for p_ in (c['plants'] if stream == 'LOG' else c['plants'][:1])}
    return {p for p in pl if all(fichero_ok(i['name'], i['table']) for i in qs4_plan.plan(stream, p, None, {}))}


MODULOS_AUTO = {'PP': None, 'QM': None, 'PM': 'reglas de mantenimiento pendientes (fase 8)',
                'WM': 'reglas de almacén pendientes (fase 9)', 'LOG': None}      # None = disponible
AUTO = {'estado': 'libre', 'stream': '', 'plantas': [], 'hechos': 0, 'total': 0, 'inicio': 0, 'fin': 0, 'planta': '', 'cuenta': {}, 'error': None}


def auto_lanzar(stream, plantas):
    """Lanza la propuesta de UN módulo (y, si se indica, de unas plantas) en segundo plano; el avance se lee en /api/auto/status."""
    if AUTO['estado'] == 'calculando':
        return {'error': 'Ya hay una propuesta en marcha.'}
    if MODULOS_AUTO.get(stream, 'módulo desconocido') is not None:
        return {'error': f'Módulo {stream}: {MODULOS_AUTO.get(stream, "módulo desconocido")}. Todavía no se puede proponer con garantías.'}
    AUTO.update(estado='calculando', stream=stream, plantas=list(plantas or []), hechos=0, total=0, inicio=time.time(), fin=0, planta='', cuenta={}, error=None)

    def run():
        try:
            AUTO['cuenta'] = dict(auto_proponer(stream, plantas))
            AUTO['estado'] = 'terminado'
        except Exception as e:
            AUTO['estado'], AUTO['error'] = 'error', f'{type(e).__name__}: {e}'
        AUTO['fin'] = time.time()
    threading.Thread(target=run, daemon=True).start()
    return {'ok': True}


def auto_proponer(stream='PP', plantas=None):
    """Propuesta en bloque de un módulo: por cada caso, ¿sirve la Data del Excel? Si no, el primer candidato válido y libre (un dato, un caso).
    No toca lo validado, en curso, sin candidato o con datos puestos a mano; rehace solo lo automático anterior DE ESTE MÓDULO (y de esas plantas)."""
    from collections import Counter
    cuenta = Counter()
    with LOCK:
        asig = load_asig()
        sel = set(plantas or [])
        en_ambito = lambda c: c['stream'] == stream and c['plants'] and (not sel or c['plants'][0] in sel)
        for cid in [k for k, v in asig.items() if v.get('auto') and state['cases'].get(k) and en_ambito(state['cases'][k])]:
            del asig[cid]
        reservados = reserved_map(asig)
        cargadas = plantas_completas(stream)
        opt = Options(state['tables'], reservados, state['orgs'])
        ahora = datetime.now().isoformat(timespec='seconds')
        valido = lambda x: (x.get('Apto') or x.get('Completo')) == 'SÍ'
        AUTO['total'] = sum(1 for c in state['cases'].values() if en_ambito(c))
        AUTO['cuenta'] = cuenta          # se ve crecer en vivo
        if stream in ('LOG', 'QM') and not sel:      # sin planta en la Data no hay dato que proponer: queda para revisar a mano
            for cid, c in state['cases'].items():
                a0 = asig.get(cid) or {}
                if c['stream'] == stream and not c['plants'] and a0.get('status') not in ('Validado', 'En curso'):
                    asig[cid] = {'stream_override': '', 'tramos': [], 'objetivo': None, 'edits': {}, 'org_ok': False, 'auto': True, 'updated': ahora, 'status': 'Revisar a mano',
                                 'fields': {}, 'note': 'La Data no trae planta: no se puede proponer dato de SAP.'}
                    cuenta['revisar'] += 1
        for cid, c in state['cases'].items():
            if not en_ambito(c):
                continue
            AUTO['hechos'] += 1
            orden_pl = c['plants']
            if stream == 'LOG' and c.get('flow') in ('ZTRA', 'ZWIA', 'ZINT', 'ZINR') and c['roles'].get('emisora'):      # traslado: la primera planta es la que suministra
                e0 = c['roles']['emisora'][0]
                orden_pl = [e0] + [p_ for p_ in c['plants'] if p_ != e0]
            plant = orden_pl[0]
            AUTO['planta'] = plant
            if plant not in cargadas:
                cuenta['sin_datos'] += 1
                continue
            a0 = asig.get(cid) or {}
            if a0.get('status') in ('Validado', 'En curso', 'Sin candidato') or any(v for k, v in a0.get('fields', {}).items() if k not in ('sociedad', 'org_compras', 'org_ventas', 'tipo_pedido')):
                cuenta['respetados'] += 1
                continue
            ob = objetivo_pp(c['scenario']) if stream == 'PP' else None
            opt.reserved = reservados
            secs = opt.for_stream(stream, plant, c.get('flow'), ','.join(orden_pl[1:]) if stream == 'LOG' else '', False, '', ob, con_puesto(c), flecha_data(c), qm_requisitos(c) if stream == 'QM' else None)
            ex = excel_vs_opciones(c, secs)
            base = {'stream_override': '', 'tramos': [], 'objetivo': ob, 'edits': {}, 'org_ok': False, 'auto': True, 'updated': ahora}
            modo = modo_auto(c)
            if modo == 'manual':
                asig[cid] = dict(base, status='No requiere', note='Caso manual, de interfaz o con transacción propia: no hay dato de SAP que proponer.', fields={})
                cuenta['no_requiere'] += 1
                continue
            if modo == 'wm':
                asig[cid] = dict(base, status='Revisar a mano', note='Dispositivos RF: dependen de datos WM (fase pendiente).', fields={})
                cuenta['revisar'] += 1
                continue
            if stream == 'LOG' and (c.get('flow') == 'ZINR' or any(k in (c['scenario'] or '').lower() for k in ('return', 'devoluci'))):
                asig[cid] = dict(base, status='Revisar a mano', fields={}, note='Devolución: depende de un traslado o venta previos; hace falta el documento que se devuelve. Elige el material de ese documento.',
                                 hallazgo='; '.join(f"{x['material']}: {'no existe en ' + plant if not x['existe'] else (x.get('Motivo') or 'no sirve')}" for x in ex if not valido(x)))
                cuenta['revisar'] += 1
                continue
            if not ex and stream == 'PP' and (ob or '').split(':')[0] in ('PLAN', 'STAGE'):
                # el caso FABRICA algo (planifica o aprovisiona) pero la Data solo trae la planta: hace falta un producto que cumpla lo que pide (lista, ruta, versión, puesto y componente)
                pool0 = [r for r in secs[0]['rows'] if valido(r) and not r.get('Reservado por')] if secs else []
                if not pool0:
                    asig[cid] = dict(base, status='Sin candidato', fields={}, note=f'No hay en {plant} un producto que cumpla lo que pide este caso ({ob}).', hallazgo='La Data solo trae la planta.')
                    cuenta['sin_candidato'] += 1
                    continue
                r = pool0[0]
                fields = {'planta': plant, 'material': r['Material']}
                for k in ('version_fabricacion', 'lista_materiales', 'hoja_ruta', 'cost_collector', 'puesto_trabajo', 'componentes'):
                    if (r.get('fill') or {}).get(k):
                        fields[k] = r['fill'][k]
                reservados[('MATERIAL', f"{r['Material']}@{plant}")] = cid
                asig[cid] = dict(base, status='Propuesto', fields=fields, nuevos=[r['Material']], note='Propuesta automática: pendiente de revisar.',
                                 resumen=f"{r['Material']} ({r.get('Tipo', '')}) · Por qué sirve: {r.get('Motivo') or 'cumple lo que pide el caso'}", hallazgo='La Data solo trae la planta: se propone un producto que cumple lo que pide el caso.')
                cuenta['propuestos'] += 1
                continue
            if not ex:
                asig[cid] = dict(base, status='No requiere', note='La Data solo trae la planta: depende de lo que dejan otros casos.', fields={})
                cuenta['no_requiere'] += 1
                continue
            malos = [x for x in ex if not valido(x)]
            if any(x.get('excluido') for x in malos):
                asig[cid] = dict(base, status='Revisar a mano', fields={}, note='Trae repuestos (80000000–89999999) que no se leen de QS4: no se pueden verificar ni sustituir; valídalos a mano.',
                                 hallazgo='; '.join(f"{x['material']}: {'repuesto no leído de QS4' if x.get('excluido') else ('no existe en ' + plant if not x['existe'] else (x.get('Motivo') or 'no sirve'))}" for x in malos))
                cuenta['revisar'] += 1
                continue
            # Pares «A -> B» en PLAN / STAGE / MFBF: A es un componente de la lista de B (el nombre del escenario dice el tipo de cada uno)
            if modo == 'auto' and flecha_data(c) and len(ex) == 2 and (ob or '').split(':')[0] in ('PLAN', 'STAGE', 'MFBF'):
                a_, b_ = ex[0]['material'], ex[1]['material']
                fila_b = next((r for r in secs[0]['rows'] if r['Material'] == b_), None)
                grupos, _ = opt.componentes(plant, [b_])
                a_ok = any(x['Componente'] == a_ and ((x['Stock libre'] or 0) > 0 or (ob or '').startswith('PLAN')) for g in grupos for x in g['rows'])      # planificar no consume: solo STAGE y MFBF exigen stock
                if fila_b and valido(fila_b) and a_ok:
                    asig[cid] = dict(base, status='Original OK', note=f'El par {a_} → {b_} sirve en {plant}.', fields={}, resumen=f'Data original válida en QS4 ({plant})', hallazgo='')
                    cuenta['original_ok'] += 1
                    continue
                motivo = (f"{b_} no existe en {plant}" if not fila_b else (f"{b_}: {fila_b.get('Motivo') or 'no sirve'}" if not valido(fila_b) else f"{a_} no es componente de {b_} o no tiene stock"))
                pool_p = [r for r in secs[0]['rows'] if valido(r) and not r.get('Reservado por') and r['Material'] not in usados_(ex)
                          and len([m for m in re.split(r'[,;\s]+', (r.get('fill') or {}).get('material', '')) if m]) == 2]
                if not pool_p:
                    asig[cid] = dict(base, status='Sin candidato', fields={}, note=f"No hay pareja componente → producto válida en {plant} para este caso ({ob}).", hallazgo=motivo)
                    cuenta['sin_candidato'] += 1
                    continue
                r = pool_p[0]
                final = [m for m in re.split(r'[,;\s]+', r['fill']['material']) if m]
                fields = {'planta': plant, 'material': ', '.join(final)}
                for k in ('version_fabricacion', 'lista_materiales', 'hoja_ruta', 'cost_collector', 'puesto_trabajo'):      # el puesto es el del producto B (la fila elegida)
                    if r['fill'].get(k):
                        fields[k] = r['fill'][k]
                reservados[('MATERIAL', f"{r['Material']}@{plant}")] = cid
                asig[cid] = dict(base, status='Propuesto', fields=fields, nuevos=[r['Material']], note='Propuesta automática: pendiente de revisar.',
                                 resumen=f"{a_} → {b_}  ⇒  {final[0]} → {final[1]} ({r.get('Tipo', '')})", hallazgo=motivo)
                cuenta['propuestos'] += 1
                continue
            if malos and (modo == 'comprobar' or enlaza_pares(c)):
                asig[cid] = dict(base, status='Revisar a mano', fields={},
                                 note=('Cierre/capacidad: solo se comprueba la Data, no se propone dato.' if modo == 'comprobar' else 'La Data enlaza dos materiales (A → B): elígelos a mano.'),
                                 hallazgo='; '.join(f"{x['material']}: {'no existe en ' + plant if not x['existe'] else (x.get('Motivo') or 'no sirve')}" for x in malos))
                cuenta['revisar'] += 1
                continue
            if not malos:
                asig[cid] = dict(base, status='Original OK', note=f'Todos los materiales de la Data sirven en {plant}.', fields={}, resumen=f'Data original válida en QS4 ({plant})', hallazgo='')
                cuenta['original_ok'] += 1
                continue
            rows = secs[0]['rows']
            tipos = set(c.get('mtypes') or [])
            usados = {x['material'] for x in ex}

            def cands(solo_tipo):
                return [r for r in rows if valido(r) and not r.get('Reservado por') and r['Material'] not in usados and (not solo_tipo or not tipos or r.get('Tipo') in tipos)]
            pool = cands(True) or cands(False)
            final, elegidos = [x['material'] for x in ex], []
            if stream == 'QM':      # calidad: cada hueco se rellena con un material DEL MISMO TIPO que el que no sirve (la Data dice «Material ZFIN: …»)
                ocupados, falta_t = set(), []
                for k, x in enumerate(ex):
                    if valido(x) or x.get('Tipo') == 'ZPAS':      # ZPAS está descartado en las reglas: no se sustituye
                        continue
                    t_ = x.get('Tipo') or ''
                    r = next((r for r in rows if valido(r) and not r.get('Reservado por') and r['Material'] not in usados and r['Material'] not in ocupados and (not t_ or r.get('Tipo') == t_)), None)
                    if r is None:
                        falta_t.append(t_ or '?')
                        continue
                    ocupados.add(r['Material'])
                    final[k] = r['Material']
                    elegidos.append(r)
                if falta_t:
                    asig[cid] = dict(base, status='Sin candidato', fields={}, note=f"No hay material válido de tipo {', '.join(falta_t)} en {plant} para este caso.",
                                     hallazgo='; '.join(f"{x['material']}: {'no existe en ' + plant if not x['existe'] else (x.get('Motivo') or 'no sirve')}" for x in malos))
                    cuenta['sin_candidato'] += 1
                    continue
                if not elegidos:      # lo único que no servía era ZPAS (descartado): la Data se queda como está
                    asig[cid] = dict(base, status='Original OK', note=f'Todos los materiales de la Data sirven en {plant} (ZPAS se ignora).', fields={}, resumen=f'Data original válida en QS4 ({plant})', hallazgo='')
                    cuenta['original_ok'] += 1
                    continue
            elif flecha_data(c) and pool and len(re.split(r'[,;\s]+', pool[0].get('fill', {}).get('material', ''))) == len(ex):
                final, elegidos = [m for m in re.split(r'[,;\s]+', pool[0]['fill']['material']) if m], [pool[0]]
            elif len(pool) >= len(malos):
                it = iter(pool)
                final, elegidos = [m if valido(x) else None for x, m in zip(ex, final)], []
                for k, m in enumerate(final):
                    if m is None:
                        r = next(it)
                        final[k] = r['Material']
                        elegidos.append(r)
            else:
                asig[cid] = dict(base, status='Sin candidato', fields={}, note=f"Faltan {len(malos) - len(pool)} material(es) válidos en {plant} para este caso ({ob or 'completo'}).",
                                 hallazgo='; '.join(f"{x['material']}: {'no existe en ' + plant if not x['existe'] else (x.get('Motivo') or 'no sirve')}" for x in malos))
                cuenta['sin_candidato'] += 1
                continue
            r0 = elegidos[0].get('fill', {})
            fields = {'planta': plant, 'material': ', '.join(final)}
            if stream == 'LOG' and c.get('flow') in ('ZTRA', 'ZWIA', 'ZINT', 'ZINR') and len(orden_pl) > 1:
                fields.pop('planta', None)
                fields['planta_emisora'], fields['planta_receptora'] = orden_pl[0], orden_pl[1]
            for k in ('version_fabricacion', 'lista_materiales', 'hoja_ruta', 'cost_collector'):
                if r0.get(k):
                    fields[k] = r0[k]
            if r0.get('puesto_trabajo') and (len(final) == 1 or (flecha_data(c) and len(elegidos) == 1)):      # en pares A → B el puesto es el del producto (la fila elegida)
                fields['puesto_trabajo'] = r0['puesto_trabajo']
            if ob != 'MATERIAL':                               # un modelo solo se copia; lo demás es de un solo caso
                for r in elegidos:
                    reservados[('MATERIAL', f"{r['Material']}@{plant}")] = cid
            cambios = [f"{x['material']} → {m}" for x, m in zip(ex, final) if x['material'] != m]
            asig[cid] = dict(base, status='Propuesto', fields=fields, nuevos=[r['Material'] for r in elegidos], note='Propuesta automática: pendiente de revisar.',
                 resumen='; '.join(cambios) + f" ({', '.join(r.get('Tipo', '') for r in elegidos)})" + ' · Por qué sirve: ' + ' | '.join(f"{r['Material']}: {r.get('Motivo') or 'cumple las reglas del caso'}" for r in elegidos)[:420],
                             hallazgo='; '.join(f"{x['material']}: {'no existe en ' + plant if not x['existe'] else (x.get('Motivo') or 'no sirve')}" for x in malos))
            cuenta['propuestos'] += 1
        if stream == 'LOG':        # traslados entre sociedades: el proveedor «P + planta» tiene que servir en la sociedad receptora; si no, se anota (hay que pedir su ampliación)
            for cid, a in asig.items():
                c = state['cases'].get(cid)
                if not (c and c['stream'] == 'LOG' and c.get('flow') == 'ZINT' and a.get('auto') and a.get('status') in ('Propuesto', 'Original OK') and c['plants']):
                    continue
                try:
                    sec = next((x for x in opt.for_stream('LOG', c['plants'][0], 'ZINT', ','.join(c['plants'][1:])) if x['title'].startswith('Proveedor esperado')), None)
                except Exception:
                    sec = None
                f = (sec or {}).get('rows', [{}])[0] if sec and sec.get('rows') else None
                if f and f.get('Apto') != 'SÍ':
                    a['hallazgo'] = ((a.get('hallazgo') or '') + '; ' if a.get('hallazgo') else '') + f"Proveedor {f.get('Proveedor')}: {f.get('Motivo')}"
                    a['note'] = (a.get('note') or '') + ' Falta ampliar el proveedor ' + str(f.get('Proveedor')) + ' en la sociedad receptora.'
                    cuenta['prov_interco_a_ampliar'] += 1
        if stream == 'LOG':        # antecedentes en ECC: el motivo queda anotado; las sugerencias las aplica el usuario desde el panel
            for cid, a in asig.items():
                c = state['cases'].get(cid)
                if not (c and c['stream'] == 'LOG' and a.get('auto') and a.get('status') in ('Propuesto', 'Original OK', 'Revisar a mano', 'Sin candidato')):
                    continue
                if c.get('flow') == 'VENTA' and a.get('status') in ('Propuesto', 'Original OK'):      # venta: los clientes (KNVV) no se han leído de QS4, solo se validan los materiales
                    a['hallazgo'] = ((a.get('hallazgo') or '') + '; ' if a.get('hallazgo') else '') + 'Cliente sin verificar: los clientes (KNVV) no se han leído de QS4'
                    cuenta['venta_cliente_sin_verificar'] += 1
                v = ecc_viabilidad(c)
                if v and v['estado'] != 'ok':
                    a['hallazgo'] = ((a.get('hallazgo') or '') + '; ' if a.get('hallazgo') else '') + 'ECC: ' + v['texto']
                    a['note'] = ((a.get('note') or '') + ' ' if a.get('note') else '') + 'ECC: ' + v['texto']
                    cuenta['sin_ecc'] += 1
        ASIG.parent.mkdir(parents=True, exist_ok=True)
        guarda_asig(asig)
        write_ledger(asig)
    return dict(cuenta, plantas=sorted(plantas_completas(stream)))


def generar_excel():
    """Escribe AG–AL en una COPIA (out/) con patch_xlsx; no toca el original."""
    from engine import patch_xlsx
    if state['mock']:
        return {'error': 'Modo prueba: no hay fichero UAT real que copiar.'}
    asig = load_asig()
    vals, peticion = {}, []
    for cid, a in asig.items():
        c = state['cases'].get(cid)
        if not c:
            continue
        prop = data_proposal(c, a)
        f = {k: v for k, v in a.get('fields', {}).items() if v}
        if a.get('status') == 'Sin candidato':
            peticion.append([cid, ', '.join(c['plants']), a.get('fields', {}).get('material', ''), c['flow'] or '', a.get('note', '')])
        edits = a.get('edits') or {}
        for i, (step, text) in enumerate(zip(c['steps'], prop)):
            manual = str(i) in edits
            if manual:
                text = edits[str(i)]
            changed = text != (step.get('Data') or '')
            st_ = a.get('status')
            origen = 'Sin candidato' if st_ == 'Sin candidato' else ('No requiere' if st_ == 'No requiere' else ('Pool SAP' if changed else 'Sin cambio'))      # «Revisar a mano» queda como «Sin cambio» + nota
            vals[step['_row']] = {'AG': text if changed else '', 'AH': origen,
                                  'AI': ((a.get('resumen') or '; '.join(f'{k}={v}' for k, v in f.items())) + ('; propuesta editada a mano' if manual else ''))[:250] if changed else (a.get('resumen') or a.get('note') or '' if st_ in ('Original OK', 'No requiere', 'Sin candidato', 'Revisar a mano') else ''),
                                  'AJ': (a.get('hallazgo') or '')[:250],
                                  'AK': {'Validado': 'Seguro', 'En curso': 'Probable', 'Original OK': 'Probable'}.get(st_, 'Suposición'),
                                  'AL': step.get('Accenture Owner', '')}
    out_dir = ROOT / CFG['paths']['out_dir']
    out_dir.mkdir(exist_ok=True)
    src = ROOT / CFG['paths']['uat_file']
    dst = out_dir / (src.stem + '_DataProposal.xlsx')
    try:
        n = patch_xlsx.patch(src, dst, vals)
    except PermissionError:      # abierto en Excel: se guarda con otra marca de hora
        dst = out_dir / f"{src.stem}_DataProposal_{datetime.now():%H%M%S}.xlsx"
        n = patch_xlsx.patch(src, dst, vals)
    ver = patch_xlsx.verify(src, dst)
    if peticion:
        with (out_dir / 'peticion_creacion_maestros.csv').open('w', newline='', encoding='utf-8-sig') as fh:
            w = csv.writer(fh, delimiter=';')
            w.writerow(['caso', 'plantas', 'material/tipo', 'flujo', 'notas'])
            w.writerows(peticion)
    return {'ok': True, 'ruta': str(dst), 'filas': n, 'verificacion': ver, 'peticiones': len(peticion)}


class H(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(ROOT / 'front/static'), **k)

    def log_message(self, *a):
        pass

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')      # Edge no debe reutilizar un app.js antiguo
        super().end_headers()

    def send_json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        p = u.path
        asig = load_asig()
        if p == '/api/meta':
            return self.send_json({'source': state['source'], 'mock': state['mock'], 'warnings': state['warns'],
                                   'tables': state['tables_info'], 'fields': {k: [{'key': a, 'label': b, 'multi': a in MULTI or (k in ('LOG', 'QM') and a == 'material')} for a, b in v] for k, v in FIELDS.items()},
                                   'org_fields': [{'key': a, 'label': b} for a, b in ORG_FIELDS], 'n_orgs': len(state['orgs']),
                                   'checks': CHECKS, 'pendientes': RULES.get('pendientes', []),
                                   'flows': {k: v.get('descripcion') for k, v in RULES['flows'].items()},
                                   'plants': sorted(set(state['orgs']) | {r['WERKS'] for r in state['tables'].get('T001W', [])})})
        if p == '/api/cases':
            return self.send_json([case_summary(c, asig) for c in state['cases'].values()])
        if p == '/api/case':
            c = state['cases'].get(q.get('id'))
            if not c:
                return self.send_json({'error': 'caso no encontrado'}, 404)
            a = asig.get(c['id'], {})
            d = case_summary(c, asig) | {'docs': c['docs'], 'steps': [
                {'n': i + 1, 'transaction': s.get('Transaction', ''), 'data': s.get('Data', ''),
                 'extra': {k: v for k, v in s.items() if k not in ('Transaction', 'Data', 'ID by unit') and v}} for i, s in enumerate(c['steps'])],
                'assignment': a, 'objetivo': objetivo_pp(c['scenario']) if c['stream'] == 'PP' else None, 'data_materials': mats_de_data(c), 'con_puesto': con_puesto(c), 'avisos': flow_warnings(c['flow'], a.get('fields', {})) + c.get('avisos_data', []), 'proposal': data_proposal(c, a), 'detected_stream': c['stream'], 'data_org': c['data_org'], 'roles': c['roles'], 'mtypes': c['mtypes'], 'tramos': tramos_vista(c, a), 'almacenes': c['almacenes'], 'proveedor': c['proveedor'], 'ecc_via': ecc_viabilidad(c), 'form': form_caso(c, a), 'rational': rationale_caso(c, a),
                'org_info': {p: Options(state['tables'], None, state['orgs']).org(p) for p in c['plants']}}
            return self.send_json(d)
        if p == '/api/options':
            c = state['cases'].get(q.get('id'))
            stream = q.get('stream') or (c or {}).get('stream', 'LOG')
            plant = q.get('plant', '').strip().upper()
            opt = Options(state['tables'], reserved_map(asig, exclude=q.get('id')), state['orgs'])
            opt.ecc = ecc()
            plant2 = q.get('plant2', '').strip().upper()
            vendor_q = (q.get('vendor') or '').strip()
            if not vendor_q and stream == 'LOG' and (c or {}).get('flow') in ('ZPO', 'ZSPO', 'ZSPA'):      # sin proveedor elegido, el que trae la Data: el material solo sirve si tiene registro info CON ESE proveedor
                vendor_q = str(((asig.get(q.get('id')) or {}).get('fields') or {}).get('proveedor') or (c or {}).get('proveedor') or '').strip()
            objetivo = objetivo_pp((c or {}).get('scenario')) if stream == 'PP' else None
            secs = opt.for_stream(stream, plant, (c or {}).get('flow'), plant2, q.get('sin_stock') == '1', vendor_q, objetivo, con_puesto(c), flecha_data(c), qm_requisitos(c) if stream == 'QM' else None, [x for x in re.split(r'[,;\s]+', q.get('mats', '')) if x]) if plant else []
            return self.send_json({'org': opt.org(plant) if plant else {}, 'sections': secs, 'missing': opt.missing(stream), 'objetivo': objetivo, 'excel': excel_vs_opciones(c, secs),
                                   'known_plant': bool(plant and opt.org(plant))})
        if p == '/api/plantas':
            from collections import Counter
            from engine import qs4_plan
            stream = q.get('stream', 'PP')
            cs = [c for c in state['cases'].values() if c['stream'] == stream]
            try:
                tiempos = json.loads((ROOT / 'data/ledger/tiempos_qs4.json').read_text(encoding='utf-8'))
            except Exception:
                tiempos = {}
            out = []
            for pl, n in Counter(c['plants'][0] for c in cs if c['plants']).most_common():
                items = qs4_plan.plan(stream, pl, 'ZPO' if stream == 'LOG' else None, {})      # carga masiva de logística: también registros info
                falta = [i for i in items if not fichero_ok(i['name'], i['table'])]
                out.append({'planta': pl, 'casos': n, 'tablas': len(items), 'faltan': len(falta),
                            'seg': sum((tiempos.get(i['table']) or {}).get('seg', 60) for i in falta)})
            return self.send_json({'stream': stream, 'plantas': out, 'ejemplo': cs[0]['id'] if cs else ''})
        if p == '/api/componentes':
            opt = Options(state['tables'], None, state['orgs'])
            grupos, hay = opt.componentes(q.get('plant', '').strip().upper(), [x for x in re.split(r'[,;\s]+', q.get('material', '')) if x])
            return self.send_json({'grupos': grupos, 'hay_stpo': hay})
        if p == '/api/alternatives':
            c = state['cases'].get(q.get('id'))
            stream = q.get('stream') or (c or {}).get('stream', 'LOG')
            opt = Options(state['tables'], reserved_map(asig, exclude=q.get('id')), state['orgs'])
            alts = opt.alternatives(stream, q.get('plant', '').strip().upper(), (c or {}).get('flow'))
            if q.get('scope') == 'sociedad':
                alts = [x for x in alts if x['misma_sociedad']]
            return self.send_json({'missing': opt.missing(stream), 'alternatives': alts})
        if p == '/api/org':
            opt = Options(state['tables'], None, state['orgs'])
            return self.send_json({x: opt.org(x) for x in q.get('plants', '').split(',') if x})
        if p == '/api/check':
            c = state['cases'].get(q.get('id')) or {}
            f = {k: q.get(k, '') for k in ('planta', 'planta_emisora', 'planta_receptora', 'alm_emisora', 'alm_receptora', 'proveedor', 'material')}
            return self.send_json({'checks': check_flujo(c.get('flow'), f)})
        if p in ('/api/ecc/destinos', '/api/ecc/proveedores', '/api/ecc/tramo'):
            e = ecc()
            if e is None:
                return self.send_json({'error': 'No hay fichero de ECC configurado (paths.ecc_file).'})
            if p == '/api/ecc/destinos':
                return self.send_json({'items': e.destinos(q.get('plant', '').upper(), q.get('alm', ''))})
            if p == '/api/ecc/proveedores':
                return self.send_json({'items': e.proveedores(q.get('plant', '').upper(), q.get('alm', ''))})
            t = {k: q.get(k, '') for k in ('kind', 'proveedor', 'o_planta', 'o_alm', 'd_planta', 'd_alm')}
            t['o_planta'], t['d_planta'] = t['o_planta'].upper(), t['d_planta'].upper()
            doc = 'ZPO' if t['kind'] == 'COMPRA' else doc_for(t['o_planta'], t['d_planta'])
            r = (e.compra(t['proveedor'], t['d_planta'], t['d_alm']) if t['kind'] == 'COMPRA' else e.traslado(t['o_planta'], t['o_alm'], t['d_planta'], t['d_alm']))
            return self.send_json({'doc': doc, 'ecc': r})
        if p == '/api/conflicts':
            return self.send_json(conflicts(asig))
        if p == '/api/export.csv':
            buf = io.StringIO()
            w = csv.writer(buf, delimiter=';')
            w.writerow(['ID by unit', 'Stream', 'Flujo', 'Estado', 'Campos', 'Data propuesta (resumen)', 'Notas'])
            for c in state['cases'].values():
                a = asig.get(c['id'], {})
                s = case_summary(c, asig)
                w.writerow([c['id'], s['stream'], c['flow'] or '', s['status'],
                            '; '.join(f'{k}={v}' for k, v in a.get('fields', {}).items() if v), ' || '.join(data_proposal(c, a)).replace('\n', ' / '), a.get('note', '')])
            b = ('﻿' + buf.getvalue()).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/csv; charset=utf-8')
            self.send_header('Content-Disposition', 'attachment; filename=seguimiento_casos.csv')
            self.end_headers()
            self.wfile.write(b)
            return
        if p == '/api/qs4/plan':
            from engine import qs4_plan
            allitems = qs4_items(q.get('id'), [x.upper() for x in q.get('plants', q.get('plant', '')).split(',')], q.get('stream', 'LOG'), True, q.get('vendor', ''))
            try:
                tiempos = json.loads((ROOT / 'data/ledger/tiempos_qs4.json').read_text(encoding='utf-8'))
            except Exception:
                tiempos = {}
            raw = ROOT / CFG['paths']['raw_dir']
            out = []
            for it, txt in zip(allitems, qs4_plan.describe(allitems)):
                f = raw / (it['name'] + '.txt')
                e = {'name': it['name'], 'texto': txt, 'existe': fichero_ok(it['name'], it['table']), 'est': (tiempos.get(it['table']) or {}).get('seg'), 'humano': humano(it['name'], it['table'])}
                if f.exists() and not e['existe']:
                    e['texto'] += '  (la guardada no trae todas las columnas actuales: se vuelve a leer)'
                if e['existe']:
                    e['fecha'] = datetime.fromtimestamp(f.stat().st_mtime).strftime('%d/%m %H:%M')
                    e['ts'] = int(f.stat().st_mtime)
                    with f.open(encoding='utf-8', errors='ignore') as fh:
                        e['filas'] = max(sum(1 for _ in fh) - 1, 0)
                out.append(e)
            return self.send_json({'sistema': f"{CFG['sap']['system_id']}/{CFG['sap']['client']}", 'items': out,
                                   'n': sum(1 for x in out if not x['existe']), 'n_total': len(out)})
        if p == '/api/qs4/status':
            return self.send_json(QS4)
        if p == '/api/auto/status':
            return self.send_json(dict(AUTO, ahora=time.time(), modulos={k: v for k, v in MODULOS_AUTO.items()}))
        if p == '/api/sap/estado':
            return self.send_json(dict(SAPCON, usuario=credencial_guardada(), bloqueado=freno_activo(), version=front_version()))
        if p == '/api/excel':
            r = generar_excel()
            if r.get('ok') and q.get('abrir'):
                import os
                os.startfile(r['ruta'])
            return self.send_json(r)
        if p == '/api/reload':
            build()
            return self.send_json({'ok': True})
        return super().do_GET()

    def do_POST(self):
        u = urlparse(self.path)
        if u.path == '/api/auto':
            body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))) or b'{}')
            if not body.get('confirmado'):
                return self.send_json({'error': 'Falta la confirmación del usuario.'}, 400)
            return self.send_json(auto_lanzar(body.get('stream', 'PP'), body.get('plantas') or []))
        if u.path == '/api/sap/credencial':
            # La contraseña SOLO se guarda (Administrador de credenciales de Windows); nunca se devuelve ni se escribe en logs.
            # Defensas: solo desde esta misma página en localhost (Host, Origin y cabecera propia).
            port = self.server.server_address[1]
            okhost = {f'localhost:{port}', f'127.0.0.1:{port}'}
            origin = self.headers.get('Origin')
            if self.headers.get('Host') not in okhost or (origin and origin not in {f'http://{h}' for h in okhost}) or self.headers.get('X-UAT') != '1':
                return self.send_json({'error': 'Petición no permitida.'}, 403)
            try:
                body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))) or b'{}')
                usuario = str(body.get('usuario', '')).strip() or (credencial_guardada() or '')
                pwd = str(body.get('password', ''))
                if not usuario or not pwd:
                    return self.send_json({'error': 'Faltan usuario o contraseña; no se guarda nada.'}, 400)
                sys.path.insert(0, str(ROOT / 'sap'))
                import credencial
                credencial.guardar(usuario, pwd)
                return self.send_json({'ok': True, 'usuario': usuario})
            except Exception:
                return self.send_json({'error': 'No se pudo guardar la credencial.'}, 500)
            finally:
                body = pwd = None
        if u.path == '/api/sap/conectar':
            body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))) or b'{}')
            if not body.get('confirmado'):
                return self.send_json({'error': 'Falta la confirmación del usuario.'}, 400)
            if SAPCON['estado'] == 'conectando':
                return self.send_json({'error': 'Ya se está conectando.'}, 409)
            if body.get('levantar_freno'):          # decisión expresa del usuario: se quita la marca del último intento y se hace UN intento
                sys.path.insert(0, str(ROOT / 'sap'))
                import login
                try:
                    os.remove(login.FRENO)
                except OSError:
                    pass
            threading.Thread(target=sap_worker, daemon=True).start()
            return self.send_json({'ok': True})
        if u.path == '/api/proposal':
            body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))) or b'{}')
            c = state['cases'].get(body.get('id'))
            if not c:
                return self.send_json({'error': 'caso no encontrado'}, 404)
            a2 = {'fields': {k: str(v).strip() for k, v in body.get('fields', {}).items()}, 'tramos': body.get('tramos', []),
                  'extras': {k: str(v).strip() for k, v in (body.get('extras') or {}).items()}, 'pasos': _limpia_pasos(body.get('pasos')), 'pasos_campos': _limpia_pc(body.get('pasos_campos'))}
            return self.send_json({'proposal': data_proposal(c, a2), 'form': form_caso(c, a2)})
        if u.path != '/api/qs4/run':
            return self.send_json({'error': 'no'}, 404)
        body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))) or b'{}')
        if not body.get('confirmado'):
            return self.send_json({'error': 'Falta la confirmación del usuario: no se consulta QS4 sin ella.'}, 400)
        if QS4['estado'] == 'consultando':
            return self.send_json({'error': 'Ya hay una consulta en curso.'}, 409)
        plants = body.get('plants') or [body.get('plant', '')]
        if body.get('extra') == 'info_org':      # registros info por organización de compras (una por llamada: la clave @EINE.INFNR es la de esa organización)
            from engine import qs4_plan
            ek = str(body.get('ekorg', '')).strip().upper()
            if not ek:
                return self.send_json({'error': 'Falta ekorg.'}, 400)
            items = [i for i in qs4_plan.plan_info_org(ek) if not fichero_ok(i['name'], i['table']) or body.get('forzar')]
            if not items:
                return self.send_json({'error': 'Ya está leído.'}, 400)
            QS4.update(estado='consultando', items=[], paso=0, total=len(items), sistema='', error=None)
            threading.Thread(target=qs4_worker, args=(items, bool(body.get('autocurar'))), daemon=True).start()
            return self.send_json({'ok': True, 'n': len(items), 'ekorg': ek})
        if body.get('extra') == 'clientes_transporte':      # TTDS + KNVV por org. de ventas de las plantas de LOG
            from engine import qs4_plan
            vks = sorted({x.strip() for c in state['cases'].values() if c['stream'] == 'LOG' for p_ in c['plants']
                          for x in Options(state['tables'], None, state['orgs']).org(p_).get('org_ventas', '').split(',') if x.strip()})
            items = [i for i in qs4_plan.plan_clientes_transporte(vks) if not fichero_ok(i['name'], i['table']) or body.get('forzar')]
            if not items:
                return self.send_json({'error': 'Ya está todo leído.'}, 400)
            QS4.update(estado='consultando', items=[], paso=0, total=len(items), sistema='', error=None)
            threading.Thread(target=qs4_worker, args=(items, bool(body.get('autocurar'))), daemon=True).start()
            return self.send_json({'ok': True, 'n': len(items), 'vkorg': vks})
        items = qs4_items(body.get('id'), [str(x).upper() for x in plants], body.get('stream', 'LOG'), bool(body.get('forzar')), str(body.get('vendor', '')), body.get('refrescar') or [], 'ZPO' if (body.get('masivo') and body.get('stream') == 'LOG') else None)
        if not items:
            return self.send_json({'error': 'Plan vacío: no se indicó ninguna planta. Recarga la página con Ctrl+F5.'}, 400)
        QS4.update(estado='consultando', items=[], paso=0, total=len(items), sistema='', error=None)
        threading.Thread(target=qs4_worker, args=(items, bool(body.get('autocurar'))), daemon=True).start()
        self.send_json({'ok': True, 'n': len(items)})

    def do_PUT(self):
        u = urlparse(self.path)
        if u.path != '/api/case':
            return self.send_json({'error': 'no'}, 404)
        cid = parse_qs(u.query).get('id', [''])[0]
        if cid not in state['cases']:
            return self.send_json({'error': 'caso no encontrado'}, 404)
        body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))) or b'{}')
        with LOCK:
            asig = load_asig()
            asig[cid] = {'stream_override': body.get('stream_override', ''), 'status': body.get('status', 'Pendiente'),
                         'objetivo': objetivo_pp(state['cases'][cid]['scenario']) if state['cases'][cid]['stream'] == 'PP' else None, 'tramos': body.get('tramos', []), 'edits': {str(k): v for k, v in (body.get('edits') or {}).items()}, 'note': body.get('note', ''), 'org_ok': bool(body.get('org_ok')), 'fields': {k: str(v).strip() for k, v in body.get('fields', {}).items()},
                         'extras': {k: str(v).strip() for k, v in (body.get('extras') or {}).items() if str(v).strip()},
                         'pasos': _limpia_pasos(body.get('pasos')), 'pasos_campos': _limpia_pc(body.get('pasos_campos')),
                         'updated': datetime.now().isoformat(timespec='seconds')}
            ASIG.parent.mkdir(parents=True, exist_ok=True)
            guarda_asig(asig)
            write_ledger(asig)
        mine = {r for r in resources(asig[cid])}
        self.send_json({'ok': True, 'avisos': flow_warnings(state['cases'][cid]['flow'], asig[cid]['fields']), 'conflicts': [c for c in conflicts(asig) if (c['tipo'], c['recurso']) in mine]})


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=8766)
    port = ap.parse_args().port
    build()
    print(f'Casos: {len(state["cases"])} · fuente: {state["source"]}')
    for w in state['warns']:
        print('AVISO:', w)
    print(f'http://localhost:{port}')
    ThreadingHTTPServer(('127.0.0.1', port), H).serve_forever()
