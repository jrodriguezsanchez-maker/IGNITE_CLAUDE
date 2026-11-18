"""Plan de consulta A DEMANDA a QS4 (SE16N, solo lectura): solo las tablas que necesita un stream y solo para una planta.
Nada se ejecuta aquí: devuelve la lista de lo que se consultaría para que el usuario la confirme en el front."""

# etapa 1: filtradas por planta
STAGE1 = {
    'PP':  [('MKAL', 'WERKS'), ('MAST', 'WERKS'), ('MARC', 'WERKS'), ('MARD', 'WERKS')],   # + MAPL y AUFK con filtros propios (ver plan)
    'QM':  [('QMAT', 'WERKS'), ('MARC', 'WERKS'), ('MARD', 'WERKS'), ('QALS', 'WERK')],
    'PM':  [('EQUZ', 'IWERK'), ('IFLOT', 'IWERK'), ('AFIH', 'IWERK')],
    'WM':  [('LQUA', 'WERKS'), ('T320', 'WERKS'), ('MARD', 'WERKS')],
    'LOG': [('T001L', 'WERKS'), ('MARC', 'WERKS'), ('MARD', 'WERKS')],
}
# etapa 2: filtradas por claves obtenidas en la etapa 1 -> (tabla, campo, de_tabla_etapa1, campo_origen)
STAGE2 = {
    'MATERIAL': [('MARA', 'MATNR'), ('MAKT', 'MATNR')],
    'PM': [('EQUI', 'EQUNR', 'EQUZ', 'EQUNR')],
}
MAX_CLAVES = 3000
SALES = {'VENTA'}
BUY = {'ZPO', 'ZSPO', 'ZSPA', 'ZSER'}


def plan_vendor(vendor):
    """Tablas pequeñas del proveedor de una compra: existe, datos de compras y registros info."""
    items = [{'name': f'{t}__V{vendor}', 'table': t, 'stage': 1, 'filters': {'LIFNR': [vendor]}} for t in ('LFA1', 'LFM1', 'LFB1', 'EINA')]
    items.append({'name': f'EINE__V{vendor}', 'table': 'EINE', 'stage': 2, 'filters': {'INFNR': '@EINA.INFNR'}})
    return items


def plan_vendors(vendors, tag='ZINT'):
    """Varios proveedores de golpe (p. ej. los «P + planta» de los traslados entre sociedades): 5 lecturas en vez de 5 por proveedor."""
    vs = [v for v in dict.fromkeys(vendors) if v]
    items = [{'name': f'{t}__V{tag}', 'table': t, 'stage': 1, 'filters': {'LIFNR': vs}} for t in ('LFA1', 'LFM1', 'LFB1', 'EINA')]
    items.append({'name': f'EINE__V{tag}', 'table': 'EINE', 'stage': 2, 'filters': {'INFNR': '@EINA.INFNR'}})
    return items


def plan_info_org(ekorg):
    """Registros info de UNA organización de compras: EINE por EKORG (trae los de nivel de organización, que EINE por planta no ve) y sus cabeceras EINA."""
    return [{'name': f'EINE__O{ekorg}', 'table': 'EINE', 'stage': 1, 'filters': {'EKORG': [ekorg]}},
            {'name': f'EINA__O{ekorg}', 'table': 'EINA', 'stage': 2, 'filters': {'INFNR': '@EINE.INFNR'}}]


def plan_clientes_transporte(vkorgs):
    """Datos generales de logística que no dependen de la planta: puntos de planificación de transporte (TTDS) y clientes por organización de ventas (KNVV, una lectura por org.)."""
    items = [{'name': 'TTDS__ALL', 'table': 'TTDS', 'stage': 1, 'filters': {}}]
    for vk in dict.fromkeys(v for v in vkorgs if v):
        items.append({'name': f'KNVV__VK{vk}', 'table': 'KNVV', 'stage': 1, 'filters': {'VKORG': [vk]}})
    return items


def _plan_pp(plant):
    """PP: solo lo que define un producto fabricable. Materiales = los que aparecen en lista, ruta, versión o cost collector."""
    uni = '@MAST.MATNR+MKAL.MATNR+MAPL.MATNR+AFPO.MATNR+MARC.MATNR+STPO.IDNRK'
    return [
        {'name': f'MARC__{plant}', 'table': 'MARC', 'stage': 1, 'filters': {'WERKS': [plant]}},
        {'name': f'MKAL__{plant}', 'table': 'MKAL', 'stage': 1, 'filters': {'WERKS': [plant]}},
        {'name': f'MAST__{plant}', 'table': 'MAST', 'stage': 1, 'filters': {'WERKS': [plant]}},
        {'name': f'MAPL__{plant}_N', 'table': 'MAPL', 'stage': 1, 'filters': {'WERKS': [plant], 'PLNTY': ['N']}},
        {'name': f'MAPL__{plant}_R', 'table': 'MAPL', 'stage': 1, 'filters': {'WERKS': [plant], 'PLNTY': ['R']}},
        {'name': f'MARD__{plant}', 'table': 'MARD', 'stage': 1, 'filters': {'WERKS': [plant]}},
        {'name': f'AUFK__{plant}_05', 'table': 'AUFK', 'stage': 1, 'filters': {'WERKS': [plant], 'AUTYP': ['05']}},
        {'name': f'STKO__{plant}', 'table': 'STKO', 'stage': 2, 'filters': {'STLNR': '@MAST.STLNR'}},
        {'name': f'STPO__{plant}', 'table': 'STPO', 'stage': 2, 'filters': {'STLTY': ['M'], 'STLNR': '@MAST.STLNR'}},
        {'name': f'PLKO__{plant}_N', 'table': 'PLKO', 'stage': 2, 'filters': {'PLNNR': '@MAPL.PLNNR', 'PLNTY': ['N']}},
        {'name': f'AFPO__{plant}', 'table': 'AFPO', 'stage': 2, 'filters': {'AUFNR': '@AUFK.AUFNR'}},
        {'name': f'MARA__{plant}', 'table': 'MARA', 'stage': 3, 'filters': {'MATNR': uni}},
        {'name': f'MAKT__{plant}', 'table': 'MAKT', 'stage': 3, 'filters': {'MATNR': uni, 'SPRAS': ['EN']}},      # solo el texto en inglés: menos filas y más rápido
    ]


def _plan_qm(plant):
    """Calidad: tipos de inspección activos por material (QMAT) y planes de inspección tipo Q (cabecera con su uso y proveedor en MAPL)."""
    return [
        {'name': f'QMAT__{plant}', 'table': 'QMAT', 'stage': 1, 'filters': {'WERKS': [plant]}},
        {'name': f'MAPL__{plant}_Q', 'table': 'MAPL', 'stage': 1, 'filters': {'WERKS': [plant], 'PLNTY': ['Q']}},
        {'name': f'PLKO__{plant}_Q', 'table': 'PLKO', 'stage': 2, 'filters': {'PLNNR': '@MAPL.PLNNR', 'PLNTY': ['Q']}},
    ]


def _plan_wm(plant):
    """WM: almacén de gestión de almacenes de la planta (T320), vista WM del material (MLGN), tipos de almacén (MLGT) y stock por ubicación (LQUA)."""
    return [
        {'name': f'T320__{plant}', 'table': 'T320', 'stage': 1, 'filters': {'WERKS': [plant]}},
        # solo cuantos con stock (VERME de 1 en adelante, en entero para no depender del separador decimal): en SAP quedan muchos cuantos a cero
        {'name': f'LQUA__{plant}', 'table': 'LQUA', 'stage': 1, 'filters': {'WERKS': [plant], 'VERME': {'low': '1', 'high': '9999999999'}}},
        {'name': f'MLGN__{plant}', 'table': 'MLGN', 'stage': 2, 'filters': {'LGNUM': '@T320.LGNUM', 'MATNR': '@MARC.MATNR'}},
        {'name': f'MLGT__{plant}', 'table': 'MLGT', 'stage': 2, 'filters': {'LGNUM': '@T320.LGNUM', 'MATNR': '@MARC.MATNR'}},
    ]


def plan(stream, plant, flow=None, org=None):
    if stream == 'PP':
        return _plan_pp(plant)
    if stream == 'WM':
        return _plan_pp(plant) + _plan_wm(plant)
    if stream == 'QM':           # lo de PP (ya leído en las plantas de fabricación) + las tablas de calidad
        return _plan_pp(plant) + _plan_qm(plant)
    org = org or {}
    items = []
    for t, col in STAGE1.get(stream, STAGE1['LOG']):
        items.append({'name': f'{t}__{plant}', 'table': t, 'stage': 1, 'filters': {col: [plant]}})
    if stream == 'PP':
        # hoja de ruta (MAPL tipo N) y cost collector (AUFK tipo 05) con filtros propios; después sus cabeceras por clave
        items.append({'name': f'MAPL__{plant}_N', 'table': 'MAPL', 'stage': 1, 'filters': {'WERKS': [plant], 'PLNTY': ['N']}})
        items.append({'name': f'AUFK__{plant}_05', 'table': 'AUFK', 'stage': 1, 'filters': {'WERKS': [plant], 'AUTYP': ['05']}})
        items.append({'name': f'STKO__{plant}', 'table': 'STKO', 'stage': 2, 'filters': {'STLNR': '@MAST.STLNR'}})
        items.append({'name': f'PLKO__{plant}_N', 'table': 'PLKO', 'stage': 2, 'filters': {'PLNNR': '@MAPL.PLNNR', 'PLNTY': ['N']}})
        items.append({'name': f'AFPO__{plant}', 'table': 'AFPO', 'stage': 2, 'filters': {'AUFNR': '@AUFK.AUFNR'}})
    if stream == 'LOG' and flow in SALES and org.get('org_ventas'):
        vk = [x.strip() for x in org['org_ventas'].split(',') if x.strip()]
        items.append({'name': f'KNVV__{plant}', 'table': 'KNVV', 'stage': 1, 'filters': {'VKORG': vk}})
    if stream == 'LOG' and flow in BUY:
        items.append({'name': f'EINE__{plant}', 'table': 'EINE', 'stage': 1, 'filters': {'WERKS': [plant]}})
    if stream == 'PM':
        for t, col, src, scol in STAGE2['PM']:
            items.append({'name': f'{t}__{plant}', 'table': t, 'stage': 2, 'filters': {col: f'@{src}.{scol}'}})
    else:
        for t, col in STAGE2['MATERIAL']:
            items.append({'name': f'{t}__{plant}', 'table': t, 'stage': 2, 'filters': {col: '@MATERIAL', **({'SPRAS': ['EN']} if t == 'MAKT' else {})}})
    if stream == 'LOG' and flow in BUY:
        items.append({'name': f'EINA__{plant}', 'table': 'EINA', 'stage': 2, 'filters': {'INFNR': '@EINE.INFNR'}})
        # proveedores de esos registros info: existencia (LFA1), sociedad (LFB1) y organización de compras (LFM1)
        for t_ in ('LFA1', 'LFB1', 'LFM1'):
            items.append({'name': f'{t_}__{plant}', 'table': t_, 'stage': 3, 'filters': {'LIFNR': '@EINA.LIFNR'}})
    return items


def describe(items):
    out = []
    for it in items:
        f = ', '.join(f'{k} = {v if isinstance(v, str) else (str(v["low"]) + " a " + str(v["high"]) if isinstance(v, dict) else ",".join(v))}' for k, v in it['filters'].items())
        out.append(f"{it['table']}  ({f})")
    return out
