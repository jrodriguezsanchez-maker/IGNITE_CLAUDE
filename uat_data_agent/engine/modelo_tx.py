"""Modelo de Data por TRANSACCIÓN (config/transacciones_modelo.xlsx, hoja «Modelo»): qué campos lleva el Data de cada paso según su transacción.
El usuario escribe los campos con sus propias palabras («source plant», «Purch.Org», «PD (delivery ID)»…); aquí se interpretan y se pintan en el formato del Data del Excel.
 - «PD (xxx)» = Prev.Data: datos transaccionales generados en pasos anteriores -> «Prev.Data (xxx)».
 - «(optional)» = solo sale si hay valor.
 - Un campo sin valor conocido sale con el marcador XXXX (como en las plantillas del Excel)."""
import re
from pathlib import Path

from engine import parse_data

RUTA = Path(__file__).resolve().parent.parent / 'config' / 'transacciones_modelo.xlsx'
HOJA = 'Modelo'
PLACEHOLDER = 'XXXX'

# texto normalizado -> (clave interna, etiqueta que se escribe en el Data)
SIN = {
    'plant': ('planta', 'Plant'), 'planta': ('planta', 'Plant'),
    'material': ('material', 'Material'), 'materials': ('material', 'Material'),
    'company code': ('sociedad', 'C.Code'), 'sociedad': ('sociedad', 'C.Code'),
    'sales organization': ('org_ventas', 'S.Org'), 'org_ventas': ('org_ventas', 'S.Org'), 'sales org': ('org_ventas', 'S.Org'),
    'purch.org': ('org_compras', 'P.Org'), 'purchase organization': ('org_compras', 'P.Org'), 'org_compras': ('org_compras', 'P.Org'), 'purchase org': ('org_compras', 'P.Org'),
    'purchase group': ('grupo_compras', 'P.Grp'), 'purchasing group': ('grupo_compras', 'P.Grp'),
    'vendor': ('proveedor', 'BP - Vendor'), 'supplier': ('proveedor', 'BP - Vendor'),
    'supplier plant or vendor': ('emisora_o_proveedor', None),
    'supplier plant': ('planta_emisora', 'Sup. Plant'), 'source plant': ('planta_emisora', 'Source Plant'),
    'destination plant': ('planta_receptora', 'Destination Plant'), 'destination plan': ('planta_receptora', 'Destination Plant'), 'final plant': ('planta_receptora', 'Final Plant'),
    'storage location': ('almacen', 'St.Loc'), 'source st. location': ('alm_emisora', 'Source St.Loc'), 'final storage location': ('alm_receptora', 'Final St.Loc'),
    'issue storage location': ('alm_emision', 'Issue St.Loc'),
    'order type': ('tipo_pedido', 'Doc Type'), 'transfer order type': ('tipo_pedido', 'Transfer Order Type'), 'sales order type': ('tipo_pedido', 'Sales Order Type'),
    'delivery type': ('tipo_entrega', 'Delivery Type'), 'notification type': ('tipo_aviso', 'Notification Type'),
    'customer': ('cliente', 'BP - Customer'), 'rol bp': ('rol_bp', 'BP Role'), 'bp role': ('rol_bp', 'BP Role'),
    'distribution channel': ('canal', 'Distribution Channel'), 'sector': ('sector', 'Sector'),
    'shipping point': ('punto_expedicion', 'Shipping Point'),
    'tranportation point': ('punto_transporte', 'Transportation planning point'), 'transportation point': ('punto_transporte', 'Transportation planning point'),
    'punto_transporte': ('punto_transporte', 'Transportation planning point'),
    'technical location': ('ubicacion_tecnica', 'Functional location'), 'equipment': ('equipo', 'Equipment'), 'equiptment': ('equipo', 'Equipment'),
    'batch': ('lote', 'Batch'), 'storage unit': ('unidad_almacen', 'Storage Unit'), 'inspection lot': ('lote_inspeccion', 'Inspection Lot'),
    'movement type': ('mov_tipo', 'Mov.Type'), 'quantity': ('cantidad', 'Quantity'),
    'cost collector': ('cost_collector', 'Cost Collector'),
    'production line': ('puesto_trabajo', 'Production line'), 'work center': ('puesto_trabajo', 'Production line'), 'puesto de trabajo': ('puesto_trabajo', 'Production line'),
    'component': ('componentes', 'Component'), 'components': ('componentes', 'Component'), 'componente': ('componentes', 'Component'),
    'bom': ('lista_materiales', 'BOM'), 'bom number': ('lista_materiales', 'BOM'), 'bill of material': ('lista_materiales', 'BOM'), 'list of materials': ('lista_materiales', 'BOM'),
    'list of material': ('lista_materiales', 'BOM'), 'lista de materiales': ('lista_materiales', 'BOM'), 'lista mat': ('lista_materiales', 'BOM'),
    'routing': ('hoja_ruta', 'Routing Number'), 'hoja de ruta': ('hoja_ruta', 'Routing Number'), 'routing group': ('hoja_ruta', 'Routing Number'),
    'production version': ('version_fabricacion', 'Production Version'), 'version': ('version_fabricacion', 'Production Version'), 'cost center': ('centro_coste', 'Cost Center'),
    'bom type': ('bom_tipo', 'BOM Type'), 'bom alternative': ('bom_alt', 'BOM Alternative'),
    'routing type': ('ruta_tipo', 'Routing Type'), 'routing number': ('hoja_ruta', 'Routing Number'), 'routing counter': ('ruta_cont', 'Routing Counter'),
    'control key': ('clave_control', 'Control Key'), 'quality characteristic': ('caract_calidad', 'Quality Characteristic'),
    'item type': ('tipo_pos', 'Item Type'), 'purchase order': ('pedido_compra', 'Purchase Order'),
}
# etiquetas del Data original donde puede venir ya el valor de cada clave (parse_data -> clave interna del parser)
ORIGEN = {'bp': ['BP'], 'planta': ['Plant'], 'sociedad': ['CCode'], 'org_compras': ['POrg'], 'org_ventas': ['SOrg'], 'planta_emisora': ['SupPlant'], 'planta_receptora': ['DestPlant', 'Plant'],
          'tipo_pedido': ['DocType'], 'proveedor': ['Vendor'], 'cliente': ['Customer', 'BP'], 'material': ['Material'], 'mov_tipo': ['MovType'], 'almacen': ['SLoc'],
          'punto_transporte': ['TPP'], 'equipo': ['Equipment'], 'ubicacion_tecnica': ['FuncLoc'], 'punto_expedicion': ['ShipPoint'], 'rol_bp': ['BPRole'],
          'tipo_entrega': ['ShipType']}
SEPARADOR = '-----------------------'
# Los tres bloques del Data, separados por rayas: 1 = datos organizativos (organización, sociedad, plantas, almacenes, punto de expedición),
# 2 = tipo de documento (clase de pedido/entrega/aviso, punto de planificación de transporte), 3 = datos transaccionales (proveedor, cliente, material, lote…).
BLOQUE = {'sociedad': 1, 'org_compras': 1, 'org_ventas': 1, 'canal': 1, 'sector': 1, 'grupo_compras': 1, 'planta': 1, 'planta_emisora': 1, 'planta_receptora': 1,
          'almacen': 1, 'alm_emisora': 1, 'alm_receptora': 1, 'alm_emision': 1, 'punto_expedicion': 1,
          'tipo_pedido': 2, 'tipo_entrega': 2, 'tipo_aviso': 2, 'punto_transporte': 2, 'mov_tipo': 2}      # el tipo de movimiento (MIGO) es como el tipo de documento de compra: va en el bloque de tipo de documento
# Transacciones que FABRICAN algo: su Data lleva siempre el puesto de trabajo (Production line) y, si se ha elegido, el componente
FABRICA = {'MD11', 'MD12', 'MFBF', 'MF42N', 'MF12', 'CO01', 'CO02', 'CO11N'}
SALIDA = {'VL01N', 'VL02N', 'VL10B', 'VL10D', 'VL06O', 'VL10C'}      # entregas de salida: la planta es la que suministra


def _trocea(texto):
    out, dep, cur = [], 0, ''
    for ch in str(texto or ''):
        if ch == '(':
            dep += 1
        elif ch == ')':
            dep -= 1
        if ch == ',' and dep <= 0:
            out.append(cur.strip())
            cur = ''
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return [x for x in out if x]


def _limpia(tok):
    opc = bool(re.search(r'\(\s*optional\b', tok, re.I))
    t = re.sub(r'\(\s*optional\s*\)?', '', tok, flags=re.I)
    t = re.sub(r'\s+', ' ', t).strip(' .;:')
    return t, opc


def interpreta(texto):
    """Lista de especificaciones: {'tipo': 'pd'|'campo'|'desconocido', 'texto', 'clave', 'etiqueta', 'opc', 'desc'}"""
    out = []
    for tok in _trocea(texto):
        m = re.match(r'(?i)^\s*pd\s*\((.*?)\)?\s*$', tok)
        if m:
            out.append({'tipo': 'pd', 'texto': tok, 'desc': m.group(1).strip(' )'), 'opc': False})
            continue
        t, opc = _limpia(tok)
        k = t.lower()
        if k in SIN:
            clave, et = SIN[k]
            out.append({'tipo': 'campo', 'texto': tok, 'clave': clave, 'etiqueta': et, 'opc': opc})
        else:
            et = ' '.join(w.capitalize() if w.islower() else w for w in t.split())
            out.append({'tipo': 'desconocido', 'texto': tok, 'clave': 'otro:' + re.sub(r'\W+', '_', k).strip('_'), 'etiqueta': et, 'opc': opc})
    return out


def tx_key(tx):
    t = re.split(r'\s*\|\|\s*|\n', str(tx or ''))[0].strip()
    t = re.sub(r'\s*\(validar\)\s*', '', t).strip()
    return t


_CACHE = {'mtime': None, 'modelo': {}}


def cargar():
    """transacción -> lista de especificaciones (recarga sola si el fichero cambia). Las filas con la columna de campos vacía no entran: ese paso conserva su Data."""
    try:
        mt = RUTA.stat().st_mtime
    except OSError:
        return {}
    if _CACHE['mtime'] == mt:
        return _CACHE['modelo']
    modelo = {}
    try:
        from openpyxl import load_workbook
        wb = load_workbook(RUTA, read_only=True, data_only=True)
        ws = wb[HOJA]
        for fila in ws.iter_rows(min_row=2, values_only=True):
            tx, campos = (str(fila[0] or '').strip(), str(fila[3] or '').strip())
            if tx and campos:
                modelo[tx] = interpreta(campos)
        wb.close()
    except Exception:
        return _CACHE['modelo']
    _CACHE.update(mtime=mt, modelo=modelo)
    return modelo


def especificacion(tx):
    return cargar().get(tx_key(tx))


VALIDO = {'planta': r'[A-Z]\d{3}|\d{4}', 'planta_emisora': r'[A-Z]\d{3}|\d{4}', 'planta_receptora': r'[A-Z]\d{3}|\d{4}', 'sociedad': r'\d{4}', 'org_compras': r'[A-Z]{2}\d{2}'}


def _vale(clave, v):
    pat = VALIDO.get(clave)
    return bool(v) and (not pat or bool(re.fullmatch(pat, str(v).strip())))


def _marcador(v):
    return bool(re.fullmatch(r'\s*(<<.*>>|X{3,}|\?+)\s*', str(v or '')))


def _valor_original(clave, orig):
    for k in ORIGEN.get(clave, []):
        v = orig.get(k)
        if v and not (clave != 'material' and _marcador(v[0])):
            return ', '.join(v) if clave == 'material' else str(v[0]).strip()
    et_norm = {s[1].lower(): s[0] for s in SIN.values() if s[1]}
    for k, v in orig.items():
        if k.startswith('OTHER:') and v:
            lab = k[6:].strip()
            if SIN.get(lab, (None,))[0] == clave:
                return str(v[0]).strip()
    return ''


FLECHA = re.compile(r'\d\s*(?:-{1,2}>|→)\s*\d')


def _materiales(txt):
    return [x for x in re.split(r'[,;\s]+', str(txt or '')) if x and not re.fullmatch(r'-{1,2}>|→|-', x)]


def calcula(specs, ctx, orig, flow, tx=''):
    """Campos de UN paso con su valor: {'items': [{'clave','etiqueta','valor','opc','bloque','texto'}], 'pds': [...]}.
    valor == '' = no se conoce (sale XXXX, o no sale si es opcional). ctx = valores conocidos (elegidos, plantas, organización…); orig = parse_data del Data original (respaldo)."""
    traslado = flow in ('ZTRA', 'ZWIA', 'ZINT', 'ZINR')
    items, pds = [], []
    for sp in specs:
        if sp['tipo'] == 'pd':
            pds.append(sp['desc'])
            continue
        clave, et = sp['clave'], sp.get('etiqueta')
        if clave == 'emisora_o_proveedor':
            clave, et = ('planta_emisora', 'Sup. Plant') if traslado else ('proveedor', 'BP - Vendor')
        v, texto = '', None
        if clave == 'planta':
            v = ctx.get('planta') or ''
            if traslado:
                v = (ctx.get('planta_emisora') if tx_key(tx) in SALIDA else ctx.get('planta_receptora')) or v
            v = v if _vale('planta', v) else ''
            v = v or _valor_original('planta', orig)
        elif clave == 'material':
            if ctx.get('_material_lineas'):
                texto = ctx['_material_lineas']            # el caso trae materiales con tipo («Material ZRAW: …»): se conservan sus líneas
                v = ', '.join(re.findall(r'\b\d{4,}\b', texto))
            else:
                raw_o = re.sub(r'\s+', ' ', ' '.join(orig.get('Material', []))).strip()
                sel_m = str(ctx.get('material') or '').strip()
                if sel_m and FLECHA.search(sel_m):
                    v = re.sub(r'\s+', ' ', sel_m).strip()                      # lo escrito ya es una pareja «A -> B»
                elif FLECHA.search(raw_o) and not sel_m:
                    v = raw_o                                                      # sin selección: la pareja original tal cual
                elif FLECHA.search(raw_o) and len(_materiales(sel_m)) == 2:
                    v = ' -> '.join(_materiales(sel_m))                            # el Data de este caso escribe parejas: la selección de dos materiales sale como pareja
                else:
                    v = ', '.join(_materiales(sel_m)) or _valor_original('material', orig)
        elif clave in ('canal', 'sector'):
            partes = [x.strip() for x in str(ctx.get('org_ventas_original') or _valor_original('org_ventas', orig)).split('/') if x.strip()]
            v = (partes[1] if clave == 'canal' and len(partes) > 1 else (partes[2] if clave == 'sector' and len(partes) > 2 else ''))
        elif clave == 'org_ventas' and any(s2.get('clave') in ('canal', 'sector') for s2 in specs):
            partes = [x.strip() for x in str(ctx.get('org_ventas') or _valor_original('org_ventas', orig) or (ctx.get('def') or {}).get('org_ventas', '')).split('/') if x.strip()]
            v = partes[0] if partes else ''
        else:
            v = str(ctx.get(clave) or '').strip()
            if not _vale(clave, v):
                v = ''
            v = v or _valor_original(clave, orig)
            if not _vale(clave, v):
                v = ''
            v = v or str((ctx.get('def') or {}).get(clave) or '').strip()
            if not v and clave in ('planta_emisora', 'planta_receptora') and ctx.get('_una_planta'):      # una sola planta en el caso: origen y destino son la misma
                v = str(ctx.get('planta') or ctx.get('planta_receptora') or ctx.get('planta_emisora') or '').strip()
        v = str(v or '').strip()
        if clave == 'ruta_cont' and re.fullmatch(r'\d', v):
            v = '0' + v                      # contador de la hoja de ruta a dos cifras: 01
        items.append({'clave': clave, 'etiqueta': et, 'valor': v, 'opc': sp['opc'], 'bloque': BLOQUE.get(clave, 3), 'texto': texto})
    if ctx.get('_fabrica') or ctx.get('_puesto'):                  # lo que FABRICA algo lleva siempre puesto de trabajo y, si se ha elegido, el componente; en producción (salvo datos maestros) todos los pasos llevan el puesto
        ya = {it['clave'] for it in items}
        if 'componentes' not in ya and ctx.get('componentes') and (ctx.get('_fabrica') or ctx.get('_comp')):
            items.append({'clave': 'componentes', 'etiqueta': 'Component', 'valor': ', '.join(x.strip() for x in re.split(r'[,;]', str(ctx['componentes'])) if x.strip()), 'opc': True, 'bloque': 3, 'texto': None})
        if 'puesto_trabajo' not in ya:
            items.append({'clave': 'puesto_trabajo', 'etiqueta': 'Production line', 'bloque': 3, 'opc': False, 'texto': None,
                          'valor': str(ctx.get('puesto_trabajo') or '').strip() or str((ctx.get('def') or {}).get('puesto_trabajo') or '').strip()})
    if ctx.get('_comp') and 'componentes' not in {it['clave'] for it in items}:      # staging / consumo de componentes: siempre llevan Component
        items.append({'clave': 'componentes', 'etiqueta': 'Component', 'valor': ', '.join(x.strip() for x in re.split(r'[,;]', str(ctx.get('componentes') or '')) if x.strip()), 'opc': False, 'bloque': 3, 'texto': None})
    return {'items': items, 'pds': pds}


def render(specs, ctx, orig, flow, tx=''):
    """Texto del Data de un paso, en el formato del Excel: tres bloques (organizativos / tipo de documento / transaccionales) separados por rayas y «Prev.Data (…)» al final."""
    r = calcula(specs, ctx, orig, flow, tx)
    lineas = []
    for it in r['items']:
        v = it['valor']
        if it['texto']:
            lineas.append((3, it['texto']))
            continue
        if not v:
            if it['opc']:
                continue
            v = PLACEHOLDER
        if it['clave'] == 'material' and v != PLACEHOLDER and FLECHA.search(v):
            lineas.append((3, f"{it['etiqueta']}: {v}"))
        elif it['clave'] == 'material' and v != PLACEHOLDER:
            ms = _materiales(v)
            lineas.append((3, f"{it['etiqueta']}: {ms[0]}" + ''.join('\n' + m for m in ms[1:])))
        else:
            lineas.append((it['bloque'], f"{it['etiqueta']}: {v}"))
    ds_ = [d for d in r['pds'] if d]
    pie = ('Prev.Data (' + '), ('.join(ds_) + ')') if ds_ else ('Prev.Data' if r['pds'] else '')      # los datos de pasos anteriores, al final y en su línea
    bloques = []
    for n in (1, 2, 3):
        txt = [t for b_, t in lineas if b_ == n]
        if txt:
            bloques.append('\n'.join(txt))
    cuerpo = ('\n' + SEPARADOR + '\n').join(bloques)      # raya entre datos organizativos, tipo de documento y datos transaccionales (como en el Excel)
    if pie and cuerpo:
        return cuerpo + '\n' + pie
    return pie or cuerpo


# clave del parser (parse_data) -> (clave interna, etiqueta)
_PARSER2CAMPO = {'CCode': ('sociedad', 'C.Code'), 'POrg': ('org_compras', 'P.Org'), 'SOrg': ('org_ventas', 'S.Org'), 'Plant': ('planta', 'Plant'), 'SupPlant': ('planta_emisora', 'Sup. Plant'),
                 'DestPlant': ('planta_receptora', 'Destination Plant'), 'DocType': ('tipo_pedido', 'Doc Type'), 'MovType': ('mov_tipo', 'Mov.Type'), 'SLoc': ('almacen', 'St.Loc'),
                 'BP': ('bp', 'BP'), 'Customer': ('cliente', 'BP - Customer'), 'Vendor': ('proveedor', 'BP - Vendor'), 'Material': ('material', 'Material'), 'BPRole': ('rol_bp', 'BP Role'),
                 'TPP': ('punto_transporte', 'Transportation planning point'), 'ShipType': ('tipo_entrega', 'Delivery Type'), 'ShipPoint': ('punto_expedicion', 'Shipping Point'),
                 'Equipment': ('equipo', 'Equipment'), 'FuncLoc': ('ubicacion_tecnica', 'Functional location')}


def specs_data(orig):
    """Campos de un paso cuya transacción NO está en el libro: los que ya trae su Data del Excel, en su orden (así se puede editar igual y añadirle campos)."""
    out, vistos = [], set()
    for k in orig.keys():
        if k in ('PrevData', 'FREE', 'Plant2', 'Plant3'):
            continue
        if k in _PARSER2CAMPO:
            clave, et = _PARSER2CAMPO[k]
        elif k.startswith('OTHER:'):
            lab = k[6:].strip()
            clave, et = SIN.get(lab, ('otro:' + re.sub(r'\W+', '_', lab).strip('_'), ' '.join(w.capitalize() if w.islower() else w for w in lab.split())))
            et = et or lab
        else:
            continue
        if clave in vistos:
            continue
        vistos.add(clave)
        out.append({'tipo': 'campo', 'texto': et, 'clave': clave, 'etiqueta': et, 'opc': False})
    return out


def catalogo():
    """[(clave, etiqueta)] de los campos que se pueden añadir a un paso."""
    vistos, out = set(), []
    for k, (clave, et) in SIN.items():
        if clave in vistos or not et or clave in ('emisora_o_proveedor', 'canal', 'sector'):
            continue
        vistos.add(clave)
        out.append((clave, et))
    return sorted(out, key=lambda x: x[1].lower())


def ajusta(specs, add=None, quitar=None):
    """Especificación de UN paso con sus cambios propios: campos quitados y campos añadidos (el usuario puede darle a cada paso su propio juego de campos)."""
    quitar, add = set(quitar or []), list(add or [])
    cat = dict(catalogo())
    out = [sp for sp in specs if sp['tipo'] == 'pd' or sp.get('clave') not in quitar]
    ya = {sp.get('clave') for sp in out}
    for clave in add:
        if clave in cat and clave not in ya:
            out.append({'tipo': 'campo', 'texto': cat[clave], 'clave': clave, 'etiqueta': cat[clave], 'opc': False})
            ya.add(clave)
    return out


def describir(texto):
    """Cómo lo interpreta la aplicación (para la columna de comprobación del Excel)."""
    partes, dudas = [], []
    for sp in interpreta(texto):
        if sp['tipo'] == 'pd':
            partes.append(f'Prev.Data ({sp["desc"]})')
        elif sp['tipo'] == 'campo':
            partes.append(f'{sp["etiqueta"] or "(según el flujo: Sup. Plant o BP - Vendor)"}' + (' [opcional]' if sp['opc'] else ''))
        else:
            partes.append(f'{sp["etiqueta"]} [nuevo: sin valor propio, sale con {PLACEHOLDER}]' + (' [opcional]' if sp['opc'] else ''))
            dudas.append(sp['texto'])
    return ' | '.join(partes), dudas
