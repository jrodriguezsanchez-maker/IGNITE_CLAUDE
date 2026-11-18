"""Datos que se DERIVAN de lo ya leído de QS4 para un material y una planta (producción): número de lista de materiales, hoja de ruta, versión de fabricación y cost collector.
Es la misma lógica que las columnas «Lista mat.», «Hoja ruta», «Versión fab.» y «Cost collector» de las listas de PP, para que el formulario y el Data digan lo mismo."""
import collections
from datetime import date

_IDX = {'sig': None, 'idx': None}


def _d8(x):
    x = str(x).strip()
    return x[6:10] + x[3:5] + x[0:2] if len(x) >= 10 and x[2] in './' else x


def _indices(t):
    sig = tuple(len(t.get(k, [])) for k in ('MAST', 'STKO', 'MKAL', 'MAPL', 'AFPO', 'AUFK'))
    if _IDX['sig'] == sig:
        return _IDX['idx']
    ix = {'mast': collections.defaultdict(list), 'mkal': collections.defaultdict(list), 'mapl': collections.defaultdict(list), 'cc': collections.defaultdict(list)}
    for r in t.get('MAST', []):
        ix['mast'][(r['MATNR'].strip().lstrip('0'), r['WERKS'])].append(r)
    for r in t.get('MKAL', []):
        ix['mkal'][(r['MATNR'].strip().lstrip('0'), r['WERKS'])].append(r)
    for r in t.get('MAPL', []):
        ix['mapl'][(r['MATNR'].strip().lstrip('0'), r['WERKS'])].append(r)
    colectores = {r['AUFNR'] for r in t.get('AUFK', []) if str(r.get('AUTYP', '')).lstrip('0') == '5' and not (r.get('LOEKZ') or '').strip()}
    for r in t.get('AFPO', []):
        if r['AUFNR'] in colectores:
            ix['cc'][(r['MATNR'].strip().lstrip('0'), r.get('DWERK', ''))].append(r['AUFNR'])
    ix['stko_ok'] = {(r['STLNR'], r['STLAL']) for r in t.get('STKO', []) if r.get('STLTY', 'M') in ('M', '') and not (r.get('LOEKZ') or '').strip() and r.get('STLST', '1') in ('1', '')}
    ix['hay_stko'] = 'STKO' in t
    _IDX.update(sig=sig, idx=ix)
    return ix


def derivar(tablas, material, planta):
    """{'lista_materiales','bom_tipo','bom_alt','hoja_ruta','ruta_tipo','ruta_cont','version_fabricacion','cost_collector'}; '' si no hay dato leído."""
    out = dict.fromkeys(('lista_materiales', 'bom_tipo', 'bom_alt', 'hoja_ruta', 'ruta_tipo', 'ruta_cont', 'version_fabricacion', 'cost_collector', 'puesto_trabajo'), '')
    m = str(material or '').strip().lstrip('0')
    if not m or not planta:
        return out
    ix = _indices(tablas)
    k = (m, planta)
    hoy = date.today().strftime('%Y%m%d')
    # lista de materiales: la primera activa; mejor la de uso 1 (producción)
    ms = [r for r in ix['mast'].get(k, []) if (not ix['hay_stko']) or (r['STLNR'], r['STLAL']) in ix['stko_ok']]
    ms.sort(key=lambda r: (str(r.get('STLAN', '')).strip() != '1', r['STLNR']))
    if ms:
        out['lista_materiales'], out['bom_tipo'], out['bom_alt'] = ms[0]['STLNR'], str(ms[0].get('STLAN', '')).strip(), ms[0]['STLAL']
    # versión de fabricación vigente y sin bloquear; su hoja de ruta manda
    vs = [r for r in ix['mkal'].get(k, []) if not (r.get('MKSP') or '').strip() and (not r.get('ADATU') or _d8(r['ADATU']) <= hoy) and (not r.get('BDATU') or _d8(r['BDATU']) >= hoy)]
    vs.sort(key=lambda r: (str(r.get('PLNTY', '')) != 'N', not (r.get('MDV01') or '').strip(), r['VERID']))
    vbest = vs[0] if vs else None
    if vbest:
        out['version_fabricacion'] = vbest['VERID']
        out['puesto_trabajo'] = (vbest.get('MDV01') or '').strip()
    rutas = [r for r in ix['mapl'].get(k, []) if r.get('PLNTY', 'N') == 'N' and not (r.get('LOEKZ') or '').strip()]
    if vbest and vbest.get('PLNTY') == 'N' and vbest.get('PLNNR'):
        out['hoja_ruta'], out['ruta_tipo'] = vbest['PLNNR'], 'N'
        r0 = next((r for r in rutas if r['PLNNR'] == vbest['PLNNR']), None)
    elif rutas:
        out['hoja_ruta'], out['ruta_tipo'] = rutas[0]['PLNNR'], 'N'
        r0 = rutas[0]
    else:
        r0 = None
    if r0:
        out['ruta_cont'] = r0.get('PLNAL', '')
    cc = ix['cc'].get(k, [])
    if cc:
        out['cost_collector'] = cc[0]
    return out
