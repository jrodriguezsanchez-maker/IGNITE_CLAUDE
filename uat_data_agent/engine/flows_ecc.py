"""Lee listados ECC (Dynamic List Display, columnas separadas por '|') con STO/pedidos y agrega los flujos reales.
Uso: python engine/flows_ecc.py <fichero.txt> [--out out/flujos_ecc.csv]"""
import argparse
import collections
import csv
import sys
from pathlib import Path


def read_list(path):
    """Devuelve (cabecera, filas dict). Ignora separadores, títulos y cabeceras repetidas por página."""
    hdr, rows = None, []
    with open(path, encoding='cp1252', errors='replace') as f:
        for l in f:
            if not l.startswith('|'):
                continue
            c = [x.strip() for x in l.rstrip('\r\n').strip('|').split('|')]
            if hdr is None:
                hdr = [h if h not in c[:i] or h == '' else f'{h}_{i}' for i, h in enumerate(c)]
                hdr = [(h + '_2') if hdr.count(h) > 1 and hdr.index(h) != i else h for i, h in enumerate(hdr)]
                continue
            if c[0] == 'Type' or len(c) != len(hdr):
                continue
            rows.append(dict(zip(hdr, c)))
    return hdr, rows


def aggregate(rows):
    """Un flujo = (tipo, planta suministradora, planta receptora, tipo material, sociedad, org.compras, proveedor)."""
    agg = collections.OrderedDict()
    for r in rows:
        k = (r['Type'], r['SPlt'], r['Plnt'], r['MTyp'], r['CoCd'], r['POrg'], r['Supplier'] or r['Vendor'])
        a = agg.setdefault(k, {'docs': set(), 'materiales': set(), 'lineas': 0, 'desde': '99999999', 'hasta': '00000000', 'almacenes': set()})
        a['docs'].add(r['Pur. Doc.'])
        a['materiales'].add(r['Material'])
        a['lineas'] += 1
        a['almacenes'].add(r['SLoc'])
        d = r['Created On'][6:10] + r['Created On'][3:5] + r['Created On'][0:2]
        a['desde'], a['hasta'] = min(a['desde'], d), max(a['hasta'], d)
    return agg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('fichero')
    ap.add_argument('--out', default='out/flujos_ecc.csv')
    a = ap.parse_args()
    hdr, rows = read_list(a.fichero)
    agg = aggregate(rows)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    with open(a.out, 'w', newline='', encoding='utf-8-sig') as fh:
        w = csv.writer(fh, delimiter=';')
        w.writerow(['tipo', 'planta_suministradora', 'planta_receptora', 'tipo_material', 'sociedad', 'org_compras', 'proveedor',
                    'n_documentos', 'n_materiales', 'n_lineas', 'desde', 'hasta', 'almacenes'])
        for k, v in agg.items():
            w.writerow(list(k) + [len(v['docs']), len(v['materiales']), v['lineas'], v['desde'], v['hasta'], ' '.join(sorted(v['almacenes']))])
    print(f'{len(rows)} líneas · {len(agg)} flujos distintos -> {a.out}')
    c = collections.Counter(r['Type'] for r in rows)
    print('por tipo:', dict(c))


if __name__ == '__main__':
    sys.exit(main())
