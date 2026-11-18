"""Genera datos SINTÉTICOS (no son datos reales) para probar el front sin SAP y sin el fichero UAT.
Uso: python tests/make_mock.py"""
import json
from pathlib import Path

M = Path(__file__).parent / 'mock'
RAW = M / 'raw'
RAW.mkdir(parents=True, exist_ok=True)


def tsv(name, cols, rows):
    lines = ['\t'.join(cols)] + ['\t'.join(str(r.get(c, '')) for c in cols) for r in rows]
    (RAW / f'{name}.txt').write_text('\n'.join(lines), encoding='utf-8')


plants = {'L101': ('Planta Log 101', '1010'), 'L102': ('Planta Log 102', '1020'), 'M020': ('Fábrica 020', '2000'),
          'M021': ('Fábrica 021', '2000')}
tsv('T001W', ['WERKS', 'NAME1', 'BWKEY', 'LAND1', 'KUNNR', 'LIFNR', 'VKORG', 'VTWIV', 'SPAIV'],
    [{'WERKS': p, 'NAME1': n, 'BWKEY': p, 'LAND1': 'ES'} for p, (n, _) in plants.items()])
tsv('T001K', ['BWKEY', 'BUKRS'], [{'BWKEY': p, 'BUKRS': b} for p, (_, b) in plants.items()])
tsv('T024W', ['WERKS', 'EKORG'], [{'WERKS': p, 'EKORG': 'ES01'} for p in plants])
tsv('TVKWZ', ['VKORG', 'VTWEG', 'WERKS'], [{'VKORG': '1200', 'VTWEG': '10', 'WERKS': p} for p in ('L101', 'L102')])
tsv('T001L', ['WERKS', 'LGORT', 'LGOBE'], [{'WERKS': p, 'LGORT': l} for p in plants for l in ('0001', '0002')])
tsv('T320', ['WERKS', 'LGORT', 'LGNUM'], [{'WERKS': 'L101', 'LGORT': '0001', 'LGNUM': '101'}])
tsv('TVSWZ', ['VSTEL', 'WERKS'], [{'VSTEL': 'S101', 'WERKS': 'L101'}])
mats = [('1000001', 'ZFIN', 'Producto A'), ('1000002', 'ZFIN', 'Producto B'), ('1000003', 'ZSEM', 'Semielab C'),
        ('1000004', 'ZRAW', 'Materia prima D'), ('1000005', 'ZPAC', 'Envase E'), ('1000006', 'ZFIN', 'Producto F')]
tsv('MARA', ['MATNR', 'MTART', 'MATKL', 'MEINS', 'XCHPF', 'MSTAE', 'LVORM'], [{'MATNR': m, 'MTART': t, 'MEINS': 'KG'} for m, t, _ in mats])
tsv('MAKT', ['MATNR', 'SPRAS', 'MAKTX'], [{'MATNR': m, 'SPRAS': 'S', 'MAKTX': d} for m, _, d in mats])
tsv('MARD', ['MATNR', 'WERKS', 'LGORT', 'LABST', 'INSME', 'SPEME'],
    [{'MATNR': m, 'WERKS': p, 'LGORT': '0001', 'LABST': 100 * (i + 1)} for i, (m, _, _) in enumerate(mats) for p in ('L101', 'M020')])
tsv('MKAL', ['MATNR', 'WERKS', 'VERID', 'ADATU', 'BDATU', 'STLAL', 'PLNTY', 'PLNNR', 'MKSP'],
    [{'MATNR': m, 'WERKS': 'M020', 'VERID': '0001', 'STLAL': '01', 'PLNTY': 'R', 'PLNNR': '5000%03d' % i} for i, m in enumerate(('1000001', '1000002', '1000003'))])
tsv('MAST', ['MATNR', 'WERKS', 'STLAN', 'STLNR', 'STLAL'],
    [{'MATNR': m, 'WERKS': 'M020', 'STLAN': '1', 'STLNR': '2000%03d' % i, 'STLAL': '01'} for i, m in enumerate(('1000001', '1000002', '1000003'))])
tsv('QMAT', ['MATNR', 'WERKS', 'ART', 'AKTIV'], [{'MATNR': '1000001', 'WERKS': 'M020', 'ART': '04', 'AKTIV': 'X'},
                                                  {'MATNR': '1000006', 'WERKS': 'M020', 'ART': '01', 'AKTIV': 'X'}])
tsv('QALS', ['PRUEFLOS', 'ART', 'MATNR', 'WERK', 'CHARG', 'ENSTEHDAT'], [{'PRUEFLOS': '90000001', 'ART': '04', 'MATNR': '1000001', 'WERK': 'M020'}])
tsv('EQUI', ['EQUNR', 'EQTYP', 'EQART'], [{'EQUNR': '10000%03d' % i, 'EQTYP': 'M', 'EQART': 'MACH'} for i in range(1, 4)])
tsv('EQUZ', ['EQUNR', 'IWERK', 'TPLNR', 'DATBI'], [{'EQUNR': '10000%03d' % i, 'IWERK': 'M020', 'TPLNR': 'M020-LIN-0%d' % i, 'DATBI': '99991231'} for i in range(1, 4)])
tsv('IFLOT', ['TPLNR', 'IWERK', 'FLTYP'], [{'TPLNR': 'M020-LIN-0%d' % i, 'IWERK': 'M020', 'FLTYP': 'L'} for i in range(1, 4)])
tsv('AFIH', ['AUFNR', 'IWERK', 'EQUNR', 'ILART'], [{'AUFNR': '4000001', 'IWERK': 'M020', 'EQUNR': '10000001', 'ILART': '010'}])
tsv('LQUA', ['LGNUM', 'MATNR', 'WERKS', 'CHARG', 'LGTYP', 'LGPLA', 'VERME'],
    [{'LGNUM': '101', 'MATNR': m, 'WERKS': 'L101', 'CHARG': 'B%s' % m[-2:], 'LGTYP': '001', 'LGPLA': 'A-01-0%d' % i, 'VERME': 50} for i, m in enumerate(('1000001', '1000002', '1000006'), 1)])
tsv('KNVV', ['KUNNR', 'VKORG', 'VTWEG', 'SPART', 'AUFSD', 'LIFSD', 'FAKSD', 'LOEVM'],
    [{'KUNNR': '30000%02d' % i, 'VKORG': '1200', 'VTWEG': '10', 'SPART': '00'} for i in range(1, 4)])
tsv('LFA1', ['LIFNR', 'LAND1', 'NAME1', 'SPERR', 'SPERM', 'WERKS'], [{'LIFNR': 'PL101', 'LAND1': 'ES', 'NAME1': 'Proveedor interno 101'}])
tsv('LFM1', ['LIFNR', 'EKORG', 'SPERM'], [{'LIFNR': 'PL101', 'EKORG': 'ES01'}, {'LIFNR': '2000001', 'EKORG': 'ES01'}])
tsv('TTDS', ['TPLST', 'BUKRS'], [{'TPLST': 'T101', 'BUKRS': '1010'}])

data_ztra = 'C.Code: 1010\nP.Org: ES01\n-----------------------\nDoc Type: ZTRA\nSupplier Plant: L101\nPlant: L102\n-----------------------\nMaterial: 1000001 (ZFIN)'
rows = []


def case(cid, l2, l3, loc, scen, steps):
    for i, (tr, data) in enumerate(steps, 1):
        rows.append({'ID by unit': cid, 'New ID': 'N-' + cid, 'L2': l2, 'L3': l3, 'Location by Unit': loc,
                     'Test Scenario': scen, 'Step': i, 'Transaction': tr, 'Data': data})


case('MOCK-PP-01', '4.1', 'Fabricación repetitiva', 'M020', 'Backflush de producto terminado en línea repetitiva',
     [('MD61', 'Plant: M020\n-----------------------\nMaterial: 1000001 (ZFIN)'), ('MFBF', 'Plant: M020\nMaterial: 1000001'), ('MIGO', 'Mov.Type: 101')])
case('MOCK-PP-02', '4.1', 'Fabricación repetitiva', 'M020', 'Reversión de backflush', [('MF12', 'Plant: M020\nMaterial: 1000002')])
case('MOCK-QM-01', '4.4', 'Inspección en recepción', 'M020', 'Lote de inspección con decisión de empleo',
     [('QA32', 'Plant: M020\nMaterial: 1000001'), ('QE51N', 'Plant: M020')])
case('MOCK-PM-01', '5.3', 'Mantenimiento correctivo', 'M020', 'Aviso y orden de mantenimiento sobre equipo',
     [('IW21', 'Plant: M020\nNotification Type: M1\nEquipment: 10000001'), ('IW31', 'Plant: M020\nEquipment: 10000001')])
case('MOCK-WM-01', '3.2', 'Almacén WM', 'L101', 'Traslado de ubicación en almacén WM',
     [('LT01', 'Plant: L101\nMaterial: 1000001'), ('LT12', 'Plant: L101')])
case('MOCK-LOG-01', '3.1', 'Traslado intra-sociedad', 'L101', 'Traslado entre plantas misma sociedad', [('ME21N', data_ztra), ('VL10B', data_ztra), ('MIGO', 'Mov.Type: 101')])
case('MOCK-LOG-02', '3.1', 'Traslado inter-sociedad', 'L101', 'Traslado entre sociedades (ZINT)',
     [('ME21N', 'C.Code: 1020\nDoc Type: ZINT\nSupplier Plant: L101\nPlant: L102\nVendor: PL101\n-----------------------\nMaterial: 1000002')])
case('MOCK-LOG-03', '3.3', 'Venta', 'L101', 'Pedido de venta y entrega', [('VA01', 'S.Org: 1200\nDoc Type: ZAOR\nPlant: L101\nBP - Customer: 3000001\nMaterial: 1000006'), ('VL01N', 'Plant: L101')])
case('MOCK-LOG-04', '5.5', 'Transporte', 'L101', 'Crear transporte', [('VT01N', 'Transportation Planning Point: T101\nShipment Type: Z001')])
(M / 'uat_mock.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding='utf-8')
print('mock generado en', M)
