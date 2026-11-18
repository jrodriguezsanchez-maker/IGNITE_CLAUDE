"""Opciones de datos por stream a partir de las tablas SAP leídas (solo lectura de ficheros exportados)."""
from collections import defaultdict
from datetime import date


def _f(x):
    t = str(x).strip().replace(' ', '')
    if ',' in t:
        t = t.replace('.', '').replace(',', '.')
    neg = t.endswith('-')
    try:
        v = float(t.rstrip('-') or 0)
        return -v if neg else v
    except ValueError:
        return 0.0


class Options:
    def __init__(self, tables, reserved=None, orgs=None):
        self.t = tables
        self.orgs = orgs or {}
        self.reserved = reserved or {}          # (tipo, recurso) -> caso
        self.desc = {}
        for r in tables.get('MAKT', []):
            if r.get('SPRAS', 'S') in ('S', 'E', 'ES', 'EN'):
                self.desc.setdefault(r['MATNR'], r.get('MAKTX', ''))
        self.mtart = {r['MATNR']: r.get('MTART', '') for r in tables.get('MARA', [])}
        stock = defaultdict(float)
        for r in tables.get('MARD', []):
            stock[(r['MATNR'], r['WERKS'])] += _f(r.get('LABST'))
        self.stock = stock

    # ---------- organización derivada de la planta ----------
    def org(self, plant):
        """Organización de la planta: Org.Structure del UAT + (si hay exportaciones) tablas SAP."""
        t = self.t
        o = self.orgs.get(plant)
        w = next((r for r in t.get('T001W', []) if r['WERKS'] == plant), None)
        if not o and not w:
            return {}
        bukrs = o['sociedad'] if o else next((r['BUKRS'] for r in t.get('T001K', []) if r['BWKEY'] == w.get('BWKEY')), '')
        ekorg = [o['org_compras']] if o and o['org_compras'] else [r['EKORG'] for r in t.get('T024W', []) if r['WERKS'] == plant]
        vkorg = o['org_ventas_lista'] if o else sorted({r['VKORG'] for r in t.get('TVKWZ', []) if r['WERKS'] == plant})
        lgort = [r['LGORT'] for r in t.get('T001L', []) if r['WERKS'] == plant]
        lgnum = sorted({r['LGNUM'] for r in t.get('T320', []) if r['WERKS'] == plant})
        vstel = [r['VSTEL'] for r in t.get('TVSWZ', []) if r['WERKS'] == plant]
        return {'nombre': (o or {}).get('nombre') or (w or {}).get('NAME1', ''), 'sociedad': bukrs,
                'org_compras': ', '.join(ekorg), 'org_ventas': ', '.join(vkorg), 'almacenes': lgort, 'lgnum': lgnum,
                'puntos_expedicion': vstel, 'pais': (o or {}).get('pais', ''), 'ubicacion': (o or {}).get('ubicacion', ''),
                'fuente': 'Org.Structure' if o else 'SAP',
                'en_qs4': (w is not None) if 't001w' in {k.lower() for k in t} else None,
                'fill': {'sociedad': bukrs, 'org_compras': ekorg[0] if ekorg else '', 'org_ventas': vkorg[0] if vkorg else ''}}

    REQ = {'PP': ['MKAL', 'MAST', 'MAPL', 'STKO', 'AUFK', 'AFPO'], 'QM': ['QMAT', 'MARD'], 'PM': ['EQUZ'], 'WM': ['LQUA'], 'LOG': ['MARD', 'MARA']}
    KEY = {'PP': ('MKAL', 'WERKS'), 'QM': ('QMAT', 'WERKS'), 'PM': ('EQUZ', 'IWERK'), 'WM': ('LQUA', 'WERKS'), 'LOG': ('MARD', 'WERKS')}

    def missing(self, stream):
        return [x for x in self.REQ.get(stream, []) if x not in self.t]

    def plants_with_data(self, stream):
        tb, col = self.KEY.get(stream, ('MARD', 'WERKS'))
        return sorted({r[col] for r in self.t.get(tb, []) if r.get(col)})

    def alternatives(self, stream, plant, flow=None):
        """Plantas con candidatos para el stream, ordenadas: misma sociedad / misma ubicación primero."""
        me = self.orgs.get(plant, {})
        out = []
        for p in self.plants_with_data(stream):
            secs = self.for_stream(stream, p, flow)
            n = len(secs[0]['rows']) if secs else 0
            if not n:
                continue
            o = self.orgs.get(p, {})
            out.append({'planta': p, 'nombre': o.get('nombre', ''), 'sociedad': o.get('sociedad', ''), 'org_compras': o.get('org_compras', ''),
                        'ubicacion': o.get('ubicacion', ''), 'candidatos': n,
                        'misma_sociedad': bool(me and o.get('sociedad') == me.get('sociedad')),
                        'misma_ubicacion': bool(me and o.get('ubicacion') and o.get('ubicacion') == me.get('ubicacion'))})
        out.sort(key=lambda x: (not x['misma_ubicacion'], not x['misma_sociedad'], -x['candidatos']))
        return out

    def _res(self, tipo, rec):
        if tipo == 'MATERIAL' and getattr(self, '_plant', ''):
            rec = f'{rec}@{self._plant}'          # la reserva de un material es por planta
        return self.reserved.get((tipo, rec), '')

    def _mat_row(self, m, plant):
        return {'Material': m, 'Descripción': self.desc.get(m, ''), 'Tipo': self.mtart.get(m, ''),
                'Stock libre': self.stock.get((m, plant), 0)}

    # ---------- secciones por stream ----------
    def for_stream(self, stream, plant, flow=None, plant2=None, sin_stock=False, vendor='', objetivo=None, con_puesto=False, flecha=False, qm=None, sel=None):
        self._plant = plant
        if stream not in ('PP', 'QM', 'PM', 'WM'):
            return self._log(plant, flow, plant2, sin_stock, vendor, sel)
        if stream == 'QM':
            return self._qm(plant, flow, qm)
        fn = {'PP': self._pp, 'QM': self._qm, 'PM': self._pm, 'WM': self._wm}[stream]
        return fn(plant, flow, objetivo, con_puesto, flecha) if stream == 'PP' else fn(plant, flow)

    def _section(self, title, hint, cols, rows, tipo):
        for r in rows:
            r['Reservado por'] = self._res(tipo, r.get('_key', ''))
        return {'title': title, 'hint': hint, 'columns': cols + ['Reservado por'], 'rows': rows, 'tipo': tipo}

    OBJ_TXT = {
        'VERSIONSEL': ('Materiales con 2 o más versiones de fabricación vigentes', 'Para cambiar la selección de versión el material necesita al menos dos versiones de fabricación vigentes y sin bloquear (no cuenta la de costes).'),
        'COSTBOM': ('Materiales con lista de producción y SIN lista de costes', 'Lista de costes = lista de materiales de uso 6. Hace falta una lista de producción (uso 1) y ninguna de uso 6.'),
        'COSTRUTA': ('Materiales con lista de costes y SIN ruta de tasa', 'Ruta de tasa = hoja de ruta de tipo R. Hace falta lista de costes (uso 6) y ninguna ruta tipo R.'),
        'COSTPV': ('Materiales con lista de costes y ruta de tasa, SIN versión de costes', 'Versión de costes = versión de fabricación que apunta a una ruta tipo R (p. ej. ZCOS).'),
        'COSTLIB': ('Materiales con versión de costes, lista de costes y ruta de tasa', 'Para liberar el costing hace falta tener las tres cosas.'),
        'MATERIAL': ('Material modelo (para copiar al crear el nuevo)', 'Crear un material no necesita lista, ruta ni cost collector: necesita un material modelo del mismo tipo, ya ampliado en la planta. Los materiales de la Data son los modelos: tienen que existir en la planta. Los más completos van primero.'),
        'BOM': ('Materiales de la planta SIN lista de materiales', 'Para crear la lista, el material debe existir en la planta y no tener ya una lista activa.'),
        'RUTA': ('Materiales con lista de materiales y SIN hoja de ruta', 'Para crear la hoja de ruta, el material necesita lista de materiales y no tener hoja de ruta tipo N.'),
        'VERSION': ('Materiales con lista y hoja de ruta y SIN versión de fabricación', 'Para crear la versión, el material necesita lista y ruta y ninguna versión vigente.'),
        'CC': ('Materiales con versión de fabricación y SIN cost collector', 'Para crear el cost collector, el material necesita versión de fabricación y ninguna orden tipo 05.'),
    }

    def componentes(self, plant, materiales):
        """Componentes de la lista de materiales (uso 1) de cada material elegido, con cantidad y stock libre en la planta."""
        t = self.t
        items = defaultdict(list)
        for r in t.get('STPO', []):
            if r.get('STLTY', 'M') in ('M', '') and not (r.get('LKENZ') or '').strip() and (r.get('IDNRK') or '').strip():      # sin IDNRK = posición de texto, no es un componente
                items[r['STLNR']].append(r)
        out = []
        for m in materiales[:3]:
            bom = [x for x in t.get('MAST', []) if x['MATNR'] == m and x['WERKS'] == plant]
            nums = {x['STLNR'] for x in bom if str(x.get('STLAN', '')).strip() == '1'} or {x['STLNR'] for x in bom}
            rows = []
            for n in sorted(nums):
                for i in items.get(n, []):
                    c = i['IDNRK']
                    rows.append({'Componente': c, 'Descripción': self.desc.get(c, ''), 'Tipo': self.mtart.get(c, ''), 'Cantidad': i.get('MENGE', ''),
                                 'Stock libre': self.stock.get((c, plant), 0), 'Coproducto': '✓' if (i.get('KZKUP') or '').strip() == 'X' else ''})
            vistos_ = set()
            rows = [r_ for r_ in rows if not ((r_['Componente'], r_['Cantidad']) in vistos_ or vistos_.add((r_['Componente'], r_['Cantidad'])))]      # la misma posición no sale dos veces (alternativas de lista)
            rows.sort(key=lambda r: (r['Stock libre'] > 0, r['Componente']))      # primero los que no tienen stock: son los que hay que mirar
            out.append({'material': m, 'descripcion': self.desc.get(m, ''), 'tipo': self.mtart.get(m, ''), 'tiene_lista': bool(nums), 'rows': rows})
        return out, bool(t.get('STPO'))

    def _obj_txt(self, o):
        t = {'ZRAW': 'materia prima', 'ZSEM': 'semielaborado', 'ZFOR': 'formulado', 'ZFIN': 'terminado', 'ZPAC': 'envase'}
        if o.startswith('PLAN:'):
            _, de, a = o.split(':')
            return (f'Productos {a} ({t.get(a, a)}) con componentes {de} ({t.get(de, de)})',
                    'Para planificar el material necesita lista, ruta y versión; y en su lista de materiales, al menos un componente del tipo de origen. Entre paréntesis, el stock libre del componente.')
        if o.startswith('STAGE:'):
            tp = o.split(':', 1)[1]
            return (f'Productos con componentes ' + (f'{tp} ({t.get(tp, tp)})' if tp != '*' else '(cualquier tipo)') + ' con stock libre',
                    'Para aprovisionar el material necesita lista, ruta y versión, y un componente del tipo pedido con stock libre en la planta. Esta lectura no mira si hay una orden o reserva abierta.')
        if o == 'MFBF':
            return ('Productos completos con todos sus componentes con stock',
                    'MFBF contabiliza la entrada y consume los componentes: hace falta producto completo (lista, ruta, versión, cost collector y puesto) y stock libre en todos los componentes que consume (los coproductos no cuentan).')
        if o == 'SUBPROD':
            return ('Productos completos con subproductos en la lista de materiales', 'La entrada de subproductos necesita una lista con al menos un coproducto (indicador de coproducto en la posición).')
        return None

    def _pp(self, plant, flow, objetivo=None, con_puesto=False, flecha=False):
        """Producción repetitiva. Sin objetivo: material completo (lista + ruta + versión + cost collector).
        Con objetivo (el caso CREA algo): lo que el caso necesita para poder ejecutarse (tiene lo previo y le falta lo que se crea)."""
        t = self.t
        hoy = date.today().strftime('%Y%m%d')

        def d8(x):
            x = str(x).strip()
            return x[6:10] + x[3:5] + x[0:2] if len(x) >= 10 and x[2] in './' else x
        stko_ok = {(r['STLNR'], r['STLAL']) for r in t.get('STKO', []) if r.get('STLTY', 'M') in ('M', '') and not r.get('LOEKZ') and r.get('STLST', '1') in ('1', '')}
        bom, ruta, ver, cc = defaultdict(list), defaultdict(list), defaultdict(list), defaultdict(list)
        for r in t.get('MAST', []):
            if r['WERKS'] == plant:
                bom[r['MATNR']].append(r)
        for r in t.get('MAPL', []):
            if r['WERKS'] == plant and r.get('PLNTY', 'N') == 'N' and not r.get('LOEKZ'):
                ruta[r['MATNR']].append(r)
        for r in t.get('MKAL', []):
            if r['WERKS'] == plant and not r.get('MKSP') and (not r.get('ADATU') or d8(r['ADATU']) <= hoy) and (not r.get('BDATU') or d8(r['BDATU']) >= hoy):
                ver[r['MATNR']].append(r)
        colectores = {r['AUFNR'] for r in t.get('AUFK', []) if r.get('WERKS') == plant and str(r.get('AUTYP', '')).lstrip('0') == '5' and not r.get('LOEKZ')}
        for r in t.get('AFPO', []):
            if r['AUFNR'] in colectores:
                cc[r['MATNR']].append(r['AUFNR'])
        hay_mdv = any('MDV01' in r for r in t.get('MKAL', []) if r.get('WERKS') == plant)      # puesto de trabajo = línea de producción de la versión de fabricación
        bom_uso = defaultdict(set)
        for r in t.get('MAST', []):
            if r['WERKS'] == plant:
                bom_uso[r['MATNR']].add(str(r.get('STLAN', '')).strip())
        ruta_r = {r['MATNR'] for r in t.get('MAPL', []) if r['WERKS'] == plant and r.get('PLNTY') == 'R' and not r.get('LOEKZ')}
        estado = {r['MATNR']: (r.get('MMSTA') or '').strip() for r in t.get('MARC', []) if r.get('WERKS') == plant}
        vman, vcos = defaultdict(list), defaultdict(list)
        for m_, L_ in ver.items():
            for r in L_:
                (vcos if r.get('PLNTY') == 'R' else vman)[m_].append(r['VERID'])
        items_bom = defaultdict(list)
        for r in t.get('STPO', []):
            if r.get('STLTY', 'M') in ('M', '') and not (r.get('LKENZ') or '').strip() and (r.get('IDNRK') or '').strip():      # sin IDNRK = posición de texto, no es un componente
                items_bom[r['STLNR']].append(r)
        hay_stpo = bool(t.get('STPO'))
        hay_mard = any(k[1] == plant for k in self.stock)

        def comps(m_):
            nums = {x['STLNR'] for x in bom[m_] if str(x.get('STLAN', '')).strip() == '1'} or {x['STLNR'] for x in bom[m_]}
            return [i for n in sorted(nums) for i in items_bom.get(n, [])]

        def libre(c_):
            return self.stock.get((c_, plant), 0)
        universo = set(bom) | set(ruta) | set(ver) | set(cc)
        hay_marc = any(r.get('WERKS') == plant for r in t.get('MARC', []))
        if objetivo:
            universo |= {r['MATNR'] for r in t.get('MARC', []) if r.get('WERKS') == plant}
        NA = '—' if objetivo else '✗'
        rows = []
        for m in universo:
            if self.mtart and self.mtart.get(m) not in (None, '', 'ZFIN', 'ZSEM', 'ZFOR'):
                continue
            b = next((x for x in bom[m] if (x['STLNR'], x['STLAL']) in stko_ok), None) if 'STKO' in t else (bom[m][0] if bom[m] else None)
            lista = b['STLNR'] if b else NA
            vbest = sorted(ver[m], key=lambda r: (str(r.get('PLNTY', '')) != 'N', not (r.get('MDV01') or '').strip(), r['VERID']))[0] if ver[m] else None
            hoja = vbest['PLNNR'] if (vbest and vbest.get('PLNTY') == 'N' and vbest.get('PLNNR')) else (ruta[m][0]['PLNNR'] if ruta[m] else NA)
            vf = vbest['VERID'] if vbest else NA
            col = cc[m][0] if cc[m] else NA
            pt = (vbest.get('MDV01') or '').strip() if (vbest and hay_mdv) else ''
            puesto = (pt or NA) if (con_puesto and hay_mdv) else ('?' if con_puesto else '')
            tiene = [x != NA for x in (lista, hoja, vf, col)]
            completo = all(tiene) and puesto != NA
            row = self._mat_row(m, plant)
            row['Puesto trabajo'] = puesto
            row['Estado mat.'] = estado.get(m, '')
            row['Versiones'] = ', '.join(sorted(vman[m]))
            row['Lista uso 6'] = '✓' if '6' in bom_uso[m] else '—'
            row['Ruta R'] = '✓' if m in ruta_r else '—'
            row['Versión costes'] = ', '.join(sorted(vcos[m])) or '—'
            row.update({'Lista mat.': lista, 'Hoja ruta': hoja, 'Versión fab.': vf, 'Cost collector': col, '_key': m,
                        'fill': {'material': m, 'version_fabricacion': vf if vf != NA else '', 'lista_materiales': lista if lista != NA else '',
                                 'hoja_ruta': hoja if hoja != NA else '', 'cost_collector': col if col != NA else '', 'planta': plant,
                                 **({'puesto_trabajo': pt} if con_puesto else {})}})
            if not objetivo:
                row['Completo'] = 'SÍ' if completo else 'NO'
            else:
                L, R, V, C = tiene
                if objetivo == 'MATERIAL':
                    ok, why = True, f'Existe en la planta · {sum(tiene)} de 4 datos de producción' + (' (completo)' if completo else '')
                    row['fill'] = {'material': m, 'planta': plant}
                elif objetivo == 'BOM':
                    ok, why = (not L), ('Ya tiene lista de materiales' if L else 'Existe en la planta y no tiene lista')
                elif objetivo == 'RUTA':
                    ok, why = (L and not R), ('Falta la lista de materiales' if not L else ('Ya tiene hoja de ruta' if R else 'Tiene lista y no tiene ruta'))
                elif objetivo == 'VERSION':
                    ok, why = (L and R and not V), ('Falta lista o ruta' if not (L and R) else ('Ya tiene versión vigente' if V else 'Tiene lista y ruta, sin versión'))
                elif objetivo == 'CC':
                    ok, why = (V and not C), ('Falta la versión de fabricación' if not V else ('Ya tiene cost collector' if C else 'Tiene versión, sin cost collector'))
                elif objetivo == 'VERSIONSEL':
                    nv = len(set(vman[m]))
                    ok, why = nv >= 2, (f'{nv} versiones: ' + ', '.join(sorted(set(vman[m]))) if nv else 'Sin versión de fabricación')
                elif objetivo == 'COSTBOM':
                    b1, b6 = '1' in bom_uso[m], '6' in bom_uso[m]
                    ok, why = (b1 and not b6), ('Ya tiene lista de costes' if b6 else ('Sin lista de producción' if not b1 else 'Tiene lista de producción y no la de costes'))
                elif objetivo == 'COSTRUTA':
                    b6, rr = '6' in bom_uso[m], m in ruta_r
                    ok, why = (b6 and not rr), ('Ya tiene ruta de tasa' if rr else ('Falta la lista de costes' if not b6 else 'Tiene lista de costes y no ruta R'))
                elif objetivo == 'COSTPV':
                    b6, rr, vc = '6' in bom_uso[m], m in ruta_r, bool(vcos[m])
                    ok, why = (b6 and rr and not vc), ('Ya tiene versión de costes' if vc else ('Falta lista de costes o ruta R' if not (b6 and rr) else 'Tiene lista y ruta de costes, sin versión'))
                elif objetivo == 'COSTLIB':
                    b6, rr, vc = '6' in bom_uso[m], m in ruta_r, bool(vcos[m])
                    ok, why = (b6 and rr and vc), ('Tiene versión, lista y ruta de costes' if (b6 and rr and vc) else 'Falta: ' + ', '.join(n for n, v in (('lista de costes', b6), ('ruta R', rr), ('versión de costes', vc)) if not v))
                elif objetivo.startswith('ESTADO:'):
                    cod = objetivo[7:]
                    pide_todo = cod in ('OK', 'PL', 'ZW')          # esos escenarios ejecutan MD61, MD11 y MFBF: necesitan datos de producción completos
                    ok = estado.get(m, '') == cod and (not pide_todo or (L and R and V and C))
                    why = (f'Estado {cod}' if estado.get(m, '') == cod else f'Estado {estado.get(m, "") or "(vacío)"}, no {cod}') + (' · producción completa' if (pide_todo and estado.get(m, '') == cod and L and R and V and C) else (' · faltan datos de producción' if (pide_todo and estado.get(m, '') == cod) else ''))
                elif objetivo.startswith(('PLAN:', 'STAGE:', 'MFBF', 'SUBPROD')):
                    cl = comps(m)
                    ids = [i['IDNRK'] for i in cl]
                    base_ok = bool(L and R and V and puesto != NA)      # de planificación en adelante también hace falta el puesto de trabajo
                    best = None
                    if objetivo.startswith('PLAN:'):
                        _, de, dst = objetivo.split(':')
                        cde = sorted((c for c in ids if self.mtart.get(c) == de), key=lambda c: -libre(c))
                        ok = base_ok and self.mtart.get(m) == dst and bool(cde)
                        why = (f'Producto {dst}' if self.mtart.get(m) == dst else f'Es {self.mtart.get(m) or "?"}, no {dst}') + (f' · {len(cde)} componente(s) {de}' if cde else f' · sin componentes {de}') + ('' if base_ok else ' · falta lista, ruta, versión o puesto')
                        row['Componentes'] = ', '.join(f'{c} ({libre(c):g})' for c in cde[:3]) + (' …' if len(cde) > 3 else '')
                        best = cde[0] if cde else None
                    elif objetivo.startswith('STAGE:'):
                        tp = objetivo.split(':', 1)[1]
                        cok = sorted((c for c in dict.fromkeys(ids) if (tp == '*' or self.mtart.get(c) == tp) and libre(c) > 0), key=lambda c: -libre(c))
                        ok = base_ok and bool(cok)
                        why = (f'{len(cok)} componente(s) con stock' if cok else 'Ningún componente del tipo con stock') + ('' if base_ok else ' · falta lista, ruta o versión')
                        row['Componentes'] = ', '.join(f'{c} ({libre(c):g})' for c in cok[:3]) + (' …' if len(cok) > 3 else '')
                        best = cok[0] if cok else None
                    elif objetivo == 'MFBF':
                        real = [i['IDNRK'] for i in cl if (i.get('KZKUP') or '').strip() != 'X']
                        sin = [c for c in dict.fromkeys(real) if libre(c) <= 0]
                        ok = completo and bool(real) and not sin
                        row['Comp. con stock'] = f'{len(set(real)) - len(sin)} de {len(set(real))}' if real else '—'
                        row['_f'] = len(sin) if real else 9999        # para ordenar: primero los que casi tienen todo
                        best = max(set(real), key=libre) if real else None
                        why = ('Producto completo' if completo else 'Faltan datos de producción') + (' · sin componentes en la lista' if not real else (f' · {len(sin)} componente(s) sin stock' if sin else ' · todos con stock'))
                    else:
                        co = [i['IDNRK'] for i in cl if (i.get('KZKUP') or '').strip() == 'X']
                        ok = completo and bool(co)
                        row['Subproductos'] = ', '.join(co[:3])
                        why = ('Producto completo' if completo else 'Faltan datos de producción') + (f' · {len(co)} subproducto(s)' if co else ' · sin subproductos')
                    if best and not flecha and objetivo.startswith(('PLAN:', 'STAGE:')):
                        row['fill']['componentes'] = best      # el producto necesita un componente del tipo de origen (p. ej. un formulado para llegar al semielaborado): se propone con él
                    if best and flecha:                       # la Data de esa unidad escribe «A → B»: componente y producto
                        row['fill'] = dict(row['fill'], material=f'{best}, {m}')
                else:
                    ok, why = False, 'Objetivo sin regla'
                row['Apto'], row['Motivo'], row['_n'] = ('SÍ' if ok else 'NO'), why, sum(tiene)
            rows.append(row)
        if objetivo:
            rows.sort(key=lambda r: (r['Apto'] != 'SÍ', r.get('_f', 0), -r['_n'] if objetivo == 'MATERIAL' else 0, r['Material']))
            titulo, hint = self.OBJ_TXT.get(objetivo) or self._obj_txt(objetivo) or (f'Materiales con estado {objetivo[7:]} en la planta', 'El caso parte de un material que ya está en ese estado (campo MMSTA de la planta). En OK, PL y ZW se exige además lista, ruta, versión y cost collector, porque el caso ejecuta MD61, MD11 y MFBF.')
            if objetivo == 'BOM' and not hay_marc:
                hint += ' ATENCIÓN: faltan los materiales de la planta (MARC); vuelve a pulsar Consultar QS4 para traerlos.'
            base3 = ['Material', 'Descripción', 'Tipo']
            if objetivo == 'VERSIONSEL':
                cols = base3 + ['Versiones', 'Hoja ruta'] + (['Puesto trabajo'] if con_puesto else []) + ['Apto', 'Motivo']
            elif objetivo.startswith('COST'):
                cols = base3 + ['Lista mat.', 'Lista uso 6', 'Ruta R', 'Versión costes', 'Apto', 'Motivo']
                if not ruta_r:
                    hint += ' ATENCIÓN: no hay ninguna ruta de tipo R en la lectura; pulsa Consultar QS4 si falta MAPL tipo R.'
            elif objetivo.startswith('ESTADO:'):
                cols = base3 + ['Estado mat.', 'Lista mat.', 'Hoja ruta', 'Versión fab.', 'Cost collector', 'Apto', 'Motivo']
            elif objetivo.startswith('PLAN:'):
                cols = base3 + ['Lista mat.', 'Hoja ruta'] + (['Puesto trabajo'] if con_puesto else []) + ['Versión fab.', 'Componentes', 'Apto', 'Motivo']
            elif objetivo.startswith('STAGE:'):
                cols = base3 + ['Hoja ruta'] + (['Puesto trabajo'] if con_puesto else []) + ['Componentes', 'Apto', 'Motivo']
            elif objetivo == 'MFBF':
                cols = base3 + ['Lista mat.', 'Hoja ruta'] + (['Puesto trabajo'] if con_puesto else []) + ['Versión fab.', 'Cost collector', 'Comp. con stock', 'Apto', 'Motivo']
            elif objetivo == 'SUBPROD':
                cols = base3 + ['Lista mat.', 'Subproductos', 'Apto', 'Motivo']
            else:
                cols = base3 + ['Lista mat.', 'Hoja ruta', 'Versión fab.', 'Cost collector', 'Apto', 'Motivo']
            if objetivo.startswith(('PLAN:', 'STAGE:', 'MFBF', 'SUBPROD')):
                if not hay_stpo:
                    hint += ' ATENCIÓN: faltan los componentes de las listas (STPO); pulsa Consultar QS4.'
                if not hay_mard:
                    hint += ' ATENCIÓN: falta el stock de la planta (MARD); pulsa Consultar QS4.'
        else:
            rows.sort(key=lambda r: (r['Completo'] != 'SÍ', r['Material']))
            titulo, hint = ('Producto a fabricar: material, lista de materiales, hoja de ruta, versión de fabricación y cost collector',
                            'Los completos van primero. ✗ = falta en QS4 para esta planta. Lista de materiales activa (STKO), hoja de ruta de tipo N, versión vigente y sin bloquear, y cost collector (orden tipo 05).')
            cols = ['Material', 'Descripción', 'Tipo', 'Lista mat.', 'Hoja ruta'] + (['Puesto trabajo'] if con_puesto else []) + ['Versión fab.', 'Cost collector', 'Completo']
            if con_puesto:
                hint += ' Puesto de trabajo = línea de producción de la versión de fabricación.'
                if not hay_mdv:
                    hint += ' ATENCIÓN: la lectura de MKAL guardada no trae el puesto de trabajo (MDV01); pulsa Consultar QS4 para actualizarla.'
        comp = []
        if not objetivo:
            for r in t.get('MARD', []):
                m = r['MATNR']
                if r['WERKS'] == plant and _f(r.get('LABST')) > 0 and self.mtart.get(m) in ('ZRAW', 'ZPAC'):
                    row = self._mat_row(m, plant)
                    row.update({'Almacén': r['LGORT'], '_key': m, 'fill': {'componentes': m, 'almacen': r['LGORT']}})
                    comp.append(row)
        secs = [self._section(titulo, hint, cols, rows[:1500], 'MATERIAL')]
        return secs

    @staticmethod
    def _art_ok(art, arts):
        """Un tipo de inspección vale si coincide con alguno de los pedidos; «ZQMPP*» = cualquiera de la familia (prefijo)."""
        return any(art.startswith(x[:-1]) if x.endswith('*') else art == x for x in arts)

    def _qm(self, plant, flow, req=None):
        """Calidad. Un material sirve si (reglas del usuario): 1) tiene habilitado en la planta el tipo de inspección que pide el caso (QMAT),
        2) tiene asociado un plan de inspección tipo Q del uso que corresponde (MAPL+PLKO), 3) si la inspección es de orden planificada,
        tiene además lista de materiales, hoja de ruta, versión de fabricación y cost collector.
        req = {'arts': [...], 'uso': '1|5|8|', 'orden': bool, 'texto': str}; None = el caso no exige nada de esto (se muestra la información sin juzgar)."""
        t = self.t
        req = req or {}
        arts, uso, orden = list(req.get('arts') or []), (req.get('uso') or ''), bool(req.get('orden'))
        lots = defaultdict(int)
        for r in t.get('QALS', []):
            lots[(r['MATNR'], r['WERK'])] += 1
        act, todos = defaultdict(set), set()
        for r in t.get('QMAT', []):
            if r['WERKS'] != plant:
                continue
            todos.add(r['MATNR'])
            if r.get('AKTIV') == 'X':
                act[r['MATNR']].add(str(r['ART']).strip())
        plko = {}
        for r in t.get('PLKO', []):
            if r.get('PLNTY', 'Q') == 'Q' and not (r.get('LOEKZ') or '').strip():
                plko[(r['PLNNR'], r.get('PLNAL', ''))] = str(r.get('VERWE', '')).strip()
        planes = defaultdict(list)          # material -> [(plan, uso, proveedor)]
        for r in t.get('MAPL', []):
            if r['WERKS'] == plant and r.get('PLNTY') == 'Q' and not (r.get('LOEKZ') or '').strip():
                u = plko.get((r['PLNNR'], r.get('PLNAL', '')))
                if u is not None:
                    planes[r['MATNR']].append((r['PLNNR'], u, (r.get('LIFNR') or '').strip()))
        prod = {}
        if orden:
            for s in self._pp(plant, flow):
                for r in s['rows']:
                    prod[r['Material']] = r
        NA = '✗'
        rows = []
        for m in sorted(todos):
            a_ = sorted(act.get(m, ()))
            pl = planes.get(m, [])
            row = self._mat_row(m, plant)
            ok1 = (any(self._art_ok(x, arts) for x in a_) if arts else bool(a_))
            ok2 = (any(u == uso for _, u, _ in pl) if uso else bool(pl)) if req.get('plan') else True
            pr = prod.get(m, {})
            ok3 = (pr.get('Completo') == 'SÍ') if orden else True
            motivos = []
            if not ok1:
                motivos.append(('Sin el tipo de inspección ' + '/'.join(arts) + ' activo en la planta') if arts else 'Sin tipo de inspección activo en la planta')
            if not ok2:
                motivos.append(f'Sin plan de inspección tipo Q de uso {uso}' if uso else 'Sin plan de inspección tipo Q')
            if orden and not ok3:
                falta = [n for n, k in (('lista de materiales', 'Lista mat.'), ('hoja de ruta', 'Hoja ruta'), ('versión de fabricación', 'Versión fab.'), ('cost collector', 'Cost collector')) if pr.get(k, NA) == NA]
                motivos.append('Falta ' + (', '.join(falta) if falta else 'algún dato de producción'))
            req_hay = bool(arts or uso or orden or req.get('plan'))
            row.update({'Clases activas': ', '.join(a_) or '—',
                        'Planes Q (uso)': ', '.join(f'{p} (uso {u}{", prov. " + v if v else ""})' for p, u, v in pl[:3]) + (' …' if len(pl) > 3 else '') if pl else '—',
                        'Lotes previos (evidencia)': lots.get((m, plant), 0), '_key': m,
                        'fill': {'material': m, 'planta': plant, 'clase_inspeccion': next((x for x in a_ if self._art_ok(x, arts)), a_[0] if a_ else '')}})
            if orden:
                row.update({k: pr.get(k, NA) for k in ('Lista mat.', 'Hoja ruta', 'Versión fab.', 'Cost collector')})
            row['Apto'] = 'SÍ' if not motivos else 'NO'
            row['Motivo'] = '; '.join(motivos) or ('Cumple las reglas de calidad del caso' if req_hay else 'Tiene inspección activa en la planta')
            row['_n'] = (lots.get((m, plant), 0), len(pl))
            rows.append(row)
        rows.sort(key=lambda r: (r['Apto'] != 'SÍ', -r['_n'][0], -r['_n'][1], r['Material']))
        cols = ['Material', 'Descripción', 'Tipo', 'Clases activas', 'Planes Q (uso)'] + (['Lista mat.', 'Hoja ruta', 'Versión fab.', 'Cost collector'] if orden else []) + ['Lotes previos (evidencia)', 'Stock libre', 'Apto', 'Motivo']
        hint = req.get('texto') or 'Sin exigencia concreta de inspección en este escenario: se enseñan los materiales de la planta con su inspección y sus planes.'
        hint += ' «Uso» del plan de inspección (campo VERWE del plan): 1 = producción (órdenes), 5 = entrada de mercancías, 8 = traslados (STO); lo demás son usos propios de la compañía.'
        falt = [x for x in ('QMAT', 'MAPL', 'PLKO') if x not in t]
        if falt:
            hint += ' ATENCIÓN: faltan tablas de calidad de QS4 (' + ', '.join(falt) + '); pulsa Consultar QS4.'
        return [self._section('Materiales con inspección de calidad en la planta', hint, cols, rows, 'MATERIAL')]

    def _pm(self, plant, flow):
        t = self.t
        equi = {r['EQUNR']: r for r in t.get('EQUI', [])}
        orders = defaultdict(int)
        for r in t.get('AFIH', []):
            orders[r['EQUNR']] += 1
        eq = []
        for r in t.get('EQUZ', []):
            if r['IWERK'] != plant or r.get('DATBI', '99991231') < '99991231':
                continue
            e = equi.get(r['EQUNR'], {})
            eq.append({'Equipo': r['EQUNR'], 'Tipo': e.get('EQTYP', ''), 'Clase': e.get('EQART', ''),
                       'Ubic. técnica': r.get('TPLNR', ''), 'Órdenes previas': orders.get(r['EQUNR'], 0),
                       '_key': r['EQUNR'],
                       'fill': {'equipo': r['EQUNR'], 'ubicacion_tecnica': r.get('TPLNR', ''), 'planta': plant}})
        ut = [{'Ubic. técnica': r['TPLNR'], 'Tipo': r.get('FLTYP', ''), '_key': r['TPLNR'],
               'fill': {'ubicacion_tecnica': r['TPLNR'], 'planta': plant}}
              for r in t.get('IFLOT', []) if r['IWERK'] == plant]
        return [self._section('Equipos activos de la planta de mantenimiento', 'Cada equipo se asigna a un solo caso.',
                              ['Equipo', 'Tipo', 'Clase', 'Ubic. técnica', 'Órdenes previas'], eq, 'EQUIPO'),
                self._section('Ubicaciones técnicas', '', ['Ubic. técnica', 'Tipo'], ut, 'UT')]

    def _wm(self, plant, flow):
        rows = []
        for r in self.t.get('LQUA', []):
            if r['WERKS'] != plant:
                continue
            m = r['MATNR']
            rows.append({'Material': m, 'Descripción': self.desc.get(m, ''), 'Tipo': self.mtart.get(m, ''),
                         'LGNUM': r['LGNUM'], 'Tipo alm.': r['LGTYP'], 'Ubicación': r['LGPLA'], 'Lote': r.get('CHARG', ''),
                         'Cantidad': r['VERME'], '_key': f"{m}|{r['LGNUM']}|{r['LGPLA']}",
                         'fill': {'material': m, 'lgnum': r['LGNUM'], 'tipo_almacen': r['LGTYP'],
                                  'ubicacion': r['LGPLA'], 'lote': r.get('CHARG', ''), 'planta': plant}})
        return [self._section('Stock en ubicaciones WM (LQUA)', 'Cuantos más cuantos con stock libre, mejor para movimientos WM.',
                              ['Material', 'Descripción', 'Tipo', 'LGNUM', 'Tipo alm.', 'Ubicación', 'Lote', 'Cantidad'],
                              rows, 'UBICACION')]

    COMPRAS = ('ZPO', 'ZSPA', 'ZSER', 'ZSPO')          # pedidos de compra, servicios, repuestos y subcontratación: piden registro info
    TIPOS_LOG = ('ZFIN', 'ZSEM', 'ZRAW', 'ZPAC', 'ZFOR', 'ZRPL', 'ZSPN', 'ZSPV')
    MAX_FILAS_LOG = 2000

    def _log(self, plant, flow, plant2=None, sin_stock=False, vendor='', sel=None):
        """Logística. Lo que decide si un material sirve (por orden de importancia):
        1) existe en las plantas del caso (MARC, sin marca de borrado); 2) no tiene el estado ZZ;
        3) tiene registro info con datos de compras de la org. de compras de la planta compradora (ZPO, ZSPA, ZSER, ZSPO, ZINT; en ZSPO, de subcontratación).
        El stock en origen es deseable, no obligatorio: solo ordena."""
        t = self.t
        n = lambda x: str(x or '').strip().lstrip('0')
        otras = [x for x in dict.fromkeys((plant2 or '').split(',')) if x and x != plant]      # plantas restantes del caso
        plant2 = ', '.join(otras)
        pide_info = flow in self.COMPRAS or flow == 'ZINT'
        pl_compra = plant if flow in self.COMPRAS else (otras[0] if otras else plant)         # la que compra: la propia, o la receptora en un traslado entre sociedades
        org_c = self.org(pl_compra)
        ekorgs = {x.strip() for x in org_c.get('org_compras', '').split(',') if x.strip()}
        bukrs = org_c.get('sociedad', '')
        ven_n = n(vendor)

        # ---- registros info válidos en la org. de compras de la planta compradora ----
        info = defaultdict(set)            # material -> proveedores con registro info válido
        info_cargado = 'EINA' in t and 'EINE' in t and any(r.get('WERKS') == pl_compra for r in t['EINE'])
        if info_cargado:
            validos = {r['INFNR'] for r in t['EINE'] if not r.get('LOEKZ') and (not ekorgs or r.get('EKORG') in ekorgs)
                       and (flow != 'ZSPO' or (r.get('ESOKZ') or '').strip() == '3') and (not (r.get('WERKS') or '').strip() or r.get('WERKS') == pl_compra)}
            for r in t['EINA']:
                if not r.get('LOEKZ') and r['INFNR'] in validos:
                    info[n(r['MATNR'])].add(n(r['LIFNR']))

        # ---- materiales ----
        marc = {r['MATNR']: r for r in t.get('MARC', []) if r['WERKS'] == plant and not (r.get('LVORM') or '').strip()}
        marc_ot = {pl: {r['MATNR']: r for r in t.get('MARC', []) if r['WERKS'] == pl and not (r.get('LVORM') or '').strip()} for pl in otras}
        cargada_ot = {pl: any(r['WERKS'] == pl for r in t.get('MARC', [])) for pl in otras}
        mstae = {r['MATNR']: (r.get('MSTAE') or '').strip() for r in t.get('MARA', [])}
        mats = []
        for m, r in marc.items():
            if self.mtart.get(m) not in self.TIPOS_LOG:
                continue
            motivos = []
            est = (r.get('MMSTA') or '').strip()
            ests = {plant: est}
            sin_receptora = [pl for pl in otras if cargada_ot[pl] and m not in marc_ot[pl]]
            for pl in otras:
                if m in marc_ot[pl]:
                    ests[pl] = (marc_ot[pl][m].get('MMSTA') or '').strip()
            if sin_receptora:
                motivos.append('No existe en ' + ', '.join(sin_receptora))
            zz = [pl for pl, e in ests.items() if e == 'ZZ']
            if zz or mstae.get(m) == 'ZZ':
                motivos.append('Estado ZZ' + (' en ' + ', '.join(zz) if zz else ' (general)'))
            reg = None
            if pide_info:
                if info_cargado:
                    reg = (ven_n in info[n(m)]) if ven_n else bool(info[n(m)])
                    if not reg:
                        motivos.append(f'Sin registro info{" con " + vendor if ven_n else ""} en {", ".join(sorted(ekorgs)) or "la org. de compras"}{" (subcontratación)" if flow == "ZSPO" else ""}')
            stock = self.stock.get((m, plant), 0)
            row = self._mat_row(m, plant)
            row.update({'Estado mat.': est, '_key': m, '_n': stock,
                        'fill': {'material': m, 'planta_emisora': plant}})
            for pl in otras:
                row['Ampliado en ' + pl] = ('SÍ' if m in marc_ot[pl] else 'NO') if cargada_ot[pl] else '?'
            if pide_info:
                row['Registro info'] = ('SÍ' if reg else 'NO') if info_cargado else '?'
            e_ = getattr(self, 'ecc', None)
            if e_ is not None and (flow in self.COMPRAS or (flow in ('ZTRA', 'ZWIA', 'ZINT', 'ZINR') and otras)):
                nm = n(m)
                if flow in self.COMPRAS:
                    docs_e = e_.po_m.get((ven_n, plant), {}).get(nm) if ven_n else e_.po_pm.get((plant, nm))
                else:
                    docs_e = e_.sto_m.get((plant, otras[0], nm))
                row['En ECC'] = f'SÍ ({len(docs_e)})' if docs_e else 'NO'
            row['Apto'] = 'NO' if motivos else 'SÍ'
            row['Motivo'] = '; '.join(motivos) or ('Existe, sin estado ZZ' + (', con registro info' if reg else '') + (f' · stock {stock:,.0f}' if stock > 0 else ' · sin stock (deseable)'))
            mats.append(row)
        mats.sort(key=lambda r: (r['Apto'] != 'SÍ', -r['_n'], r['Material']))
        total = len(mats)
        mats = mats[:self.MAX_FILAS_LOG]
        cols = ['Material', 'Descripción', 'Tipo', 'Estado mat.', 'Stock libre'] + [f'Ampliado en {pl}' for pl in otras] + (['Registro info'] if pide_info else []) + (['En ECC'] if getattr(self, 'ecc', None) is not None and (flow in self.COMPRAS or (flow in ('ZTRA', 'ZWIA', 'ZINT', 'ZINR') and otras)) else []) + ['Apto', 'Motivo']
        hint = ('Sirve si: existe en ' + ', '.join([plant] + otras) + ' · no tiene estado ZZ' + (' · tiene registro info' + (' de subcontratación' if flow == 'ZSPO' else '') + f' en {", ".join(sorted(ekorgs)) or "la org. de compras"}' if pide_info else '') +
                '. El stock en origen es deseable: solo ordena (primero los que tienen más).' + (f' Se muestran {len(mats)} de {total}.' if total > len(mats) else ''))
        if pide_info and not info_cargado:
            hint += f' ATENCIÓN: faltan los registros info de {pl_compra} (EINA/EINE); cárgalos desde «Cargar plantas…» (LOG).'
        if not marc:
            hint += f' ATENCIÓN: faltan los materiales de {plant} (MARC); pulsa Consultar QS4.'
        out = [self._section(f'Materiales de {plant}' + (f' y ampliados en {plant2}' if otras else ''), hint, cols, mats, 'MATERIAL')]

        # ---- clientes / proveedores / puntos de transporte ----
        org = self.org(plant)
        vk = set(x.strip() for x in org.get('org_ventas', '').split(',') if x.strip())
        if flow == 'VENTA':
            cu = [{'Cliente': r['KUNNR'], 'Org. ventas': r['VKORG'], 'Canal': r['VTWEG'],
                   'Bloqueo pedido': r.get('AUFSD', ''), 'Bloqueo entrega': r.get('LIFSD', ''), '_key': r['KUNNR'],
                   'fill': {'cliente': r['KUNNR']}}
                  for r in t.get('KNVV', []) if r['VKORG'] in vk and not r.get('LOEVM')]
            out.append(self._section('Clientes del área de ventas', 'Sin bloqueos de pedido/entrega.',
                                     ['Cliente', 'Org. ventas', 'Canal', 'Bloqueo pedido', 'Bloqueo entrega'], cu, 'CLIENTE'))
        lfa1 = {n(r['LIFNR']): r for r in t.get('LFA1', [])}
        lfb1 = defaultdict(dict)
        for r in t.get('LFB1', []):
            lfb1[n(r['LIFNR'])][r['BUKRS']] = r
        lfm1 = defaultdict(dict)
        for r in t.get('LFM1', []):
            lfm1[n(r['LIFNR'])][r['EKORG']] = r
        cuenta_info = defaultdict(int)
        for m_, vs in info.items():
            for v_ in vs:
                cuenta_info[v_] += 1

        seleccion = [n(m) for m in (sel or []) if n(m)]

        def prov_fila(v):
            """Un proveedor sirve si existe y tiene datos para la sociedad Y la org. de compras de la planta compradora (sin bloqueos)."""
            vn = n(v)
            a, b = lfa1.get(vn), lfb1.get(vn, {})
            em = [lfm1.get(vn, {}).get(e) for e in ekorgs]
            em = [x for x in em if x]
            leido = bool(a) or vn in lfm1 or vn in lfb1          # solo se puede decir que algo NO existe de un proveedor ya leído de QS4
            ok_soc = (bukrs in b and not (b[bukrs].get('SPERR') or '').strip()) if (leido and t.get('LFB1') and bukrs) else None
            ok_org = (bool(em) and not any((x.get('SPERM') or '').strip() for x in em)) if (leido and t.get('LFM1')) else None
            motivos = []
            if not leido:
                motivos.append('Proveedor sin leer de QS4: pulsa «Consultar QS4» (o «Cargar plantas…»)')
            if ok_soc is False:
                motivos.append(f'Sin datos o bloqueado en la sociedad {bukrs}')
            if ok_org is False:
                motivos.append(f'Sin datos o bloqueado en {", ".join(sorted(ekorgs)) or "la org. de compras"}')
            cubre, sin_reg = None, []
            if seleccion and info_cargado:      # registro info de los materiales marcados con ESTE proveedor (en ZSPO, de subcontratación)
                sin_reg = [m for m in seleccion if vn not in info.get(m, set())]
                cubre = len(seleccion) - len(sin_reg)
                if sin_reg:
                    motivos.append(f'Sin registro info{" de subcontratación" if flow == "ZSPO" else ""} para {len(sin_reg)} de {len(seleccion)} materiales seleccionados: ' + ', '.join(sin_reg[:6]) + (' …' if len(sin_reg) > 6 else ''))
            en_ecc = None
            e_ = getattr(self, 'ecc', None)
            if e_ is not None and seleccion:      # deseable: ¿esos materiales se compraban a este proveedor en esta planta en ECC? (no bloquea)
                en_ecc = f"{len(e_.mats_compra(vn, pl_compra, seleccion)['si'])} de {len(seleccion)}"
            return {'Proveedor': v, 'Nombre': (a or {}).get('NAME1', ''), f'Sociedad {bukrs}': '?' if ok_soc is None else ('SÍ' if ok_soc else 'NO'),
                    'Org. compras ' + '/'.join(sorted(ekorgs)): '?' if ok_org is None else ('SÍ' if ok_org else 'NO'),
                    'Registros info': (f'{cubre} de {len(seleccion)}' if cubre is not None else (cuenta_info.get(vn, 0) if info_cargado else '?')),
                    'Apto': 'NO' if motivos else 'SÍ',
                    'Motivo': '; '.join(motivos) or ('Existe, tiene datos de la sociedad y de la org. de compras y registro info de los ' + str(len(seleccion)) + ' materiales seleccionados' if cubre is not None else 'Existe y tiene datos de la sociedad y de la org. de compras'),
                    **({'En ECC': en_ecc} if en_ecc is not None else {}),
                    '_key': v, '_n': (cubre if cubre is not None else 0) * 100000 + cuenta_info.get(vn, 0), 'fill': {'proveedor': v}}
        if flow in ('ZINT', 'ZINR'):
            sup = f'P{plant}'
            f = prov_fila(sup)
            out.append(self._section(f'Proveedor esperado para {flow}: {sup}', 'Regla: "P" + planta emisora. Tiene que existir y tener datos de la sociedad y de la org. de compras de la planta receptora.',
                                     [k for k in f if not k.startswith('_') and k != 'fill'], [f], 'PROVEEDOR'))
        elif flow in self.COMPRAS:
            vs = {}
            for r in t.get('LFM1', []):
                if r['EKORG'] in ekorgs:
                    vs.setdefault(n(r['LIFNR']), r['LIFNR'])
            for v_ in cuenta_info:
                vs.setdefault(v_, v_)
            filas = [prov_fila(raw) for raw in vs.values()]
            filas.sort(key=lambda r: (r['Apto'] != 'SÍ', -r['_n'], str(r['Proveedor'])))
            cols_p = [k for k in (filas[0] if filas else prov_fila('0')) if not k.startswith('_') and k != 'fill']
            out.append(self._section('Proveedores', 'Sirve si existe, tiene datos de la sociedad y de la org. de compras de la planta y **registro info de los materiales que has seleccionado**. «Registros info» = cuántos de los materiales seleccionados tienen registro info con ese proveedor (sin selección: cuántos materiales de la planta).' + ('' if t.get('LFB1') else ' ATENCIÓN: faltan los datos de proveedor por sociedad (LFB1); cárgalos desde «Cargar plantas…» (LOG).'),
                                     cols_p, filas[:self.MAX_FILAS_LOG], 'PROVEEDOR'))
        if flow == 'TRANSPORTE':
            tp = [{'Pto. planif. transporte': r['TPLST'], 'Sociedad': r['BUKRS'], '_key': r['TPLST'],
                   'fill': {'punto_transporte': r['TPLST']}} for r in t.get('TTDS', [])]
            out.append(self._section('Puntos de planificación de transporte', '', ['Pto. planif. transporte', 'Sociedad'], tp, 'TPP'))

        # ---- organización de las plantas del caso: sociedad, org. de compras y almacenes ----
        filas_o = []
        for pl in [plant] + otras:
            o = self.org(pl)
            if not o:
                filas_o.append({'Planta': pl, 'Sociedad': '?', 'Org. compras': '?', 'Almacenes': 'sin datos', 'Existe en QS4': '?', '_key': pl})
                continue
            filas_o.append({'Planta': pl, 'Nombre': o.get('nombre', ''), 'Sociedad': o.get('sociedad') or '✗', 'Org. compras': o.get('org_compras') or '✗',
                            'Almacenes': (f"{len(o['almacenes'])}: " + ', '.join(sorted(o['almacenes'])[:12])) if o.get('almacenes') else ('✗ ninguno' if any(r['WERKS'] == pl for r in t.get('T001L', [])) or 'T001L' in t else 'sin datos'),
                            'Existe en QS4': {True: 'SÍ', False: 'NO', None: '?'}[o.get('en_qs4')], '_key': pl})
        out.append(self._section('Organización de las plantas del caso', 'Sociedad y organización de compras de cada planta (Org.Structure) y almacenes que existen en ella (T001L).',
                                 ['Planta', 'Nombre', 'Sociedad', 'Org. compras', 'Almacenes', 'Existe en QS4'], filas_o, 'ORG'))
        return out
