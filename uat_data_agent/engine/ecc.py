"""Índice de flujos REALES de ECC (listado de pedidos) con planta y almacén, para validar que un tramo existía.
Traslado: planta/almacén que suministra (SPlt/IStLoc) -> planta/almacén que recibe (Plnt/SLoc).
Compra:   proveedor -> planta/almacén que recibe (Plnt/SLoc)."""
import collections
import threading
from pathlib import Path

from engine import flows_ecc

TRANSFER = ('ZTRA', 'ZWIA', 'ZINT', 'ZINR')
BUY = ('ZPO', 'ZSPO', 'ZSPA', 'ZSER')
_LOCK = threading.Lock()


def _d(fecha):
    """dd.mm.yyyy -> yyyymmdd"""
    return fecha[6:10] + fecha[3:5] + fecha[0:2] if len(fecha) >= 10 else ''


class Ecc:
    def __init__(self, path):
        self.path = Path(path)
        self.ok = self.path.exists()
        self.sto = {}          # (tipo, splt, ist, plnt, sloc) -> info
        self.po = {}           # (tipo, vendor, plnt, sloc) -> info
        self.po_m = collections.defaultdict(lambda: collections.defaultdict(set))      # (proveedor, planta) -> material -> documentos
        self.po_pm = collections.defaultdict(set)                                       # (planta, material) -> documentos (cualquier proveedor)
        self.sto_m = collections.defaultdict(set)                                       # (planta que suministra, planta que recibe, material) -> documentos
        if self.ok:
            self._load()

    def _acc(self, d, key, r):
        a = d.setdefault(key, {'docs': set(), 'ultimo': '', 'mtyp': collections.Counter()})
        a['docs'].add(r['Pur. Doc.'])
        a['ultimo'] = max(a['ultimo'], _d(r['Created On']))
        a['mtyp'][r['MTyp']] += 1

    def _load(self):
        _, rows = flows_ecc.read_list(self.path)
        for r in rows:
            t = r['Type']
            if t in TRANSFER:
                self._acc(self.sto, (t, r['SPlt'], r['IStLoc'], r['Plnt'], r['SLoc']), r)
            elif t in BUY and r['Supplier']:
                self._acc(self.po, (t, r['Supplier'], r['Plnt'], r['SLoc']), r)
            mt = (r.get('Material') or '').strip().lstrip('0')
            if mt:
                if t in TRANSFER:
                    self.sto_m[(r['SPlt'], r['Plnt'], mt)].add(r['Pur. Doc.'])
                elif t in BUY and r['Supplier']:
                    self.po_m[((r['Supplier'] or '').strip().lstrip('0'), r['Plnt'])][mt].add(r['Pur. Doc.'])
                    self.po_pm[(r['Plnt'], mt)].add(r['Pur. Doc.'])

    @staticmethod
    def _fmt(key, a, campos):
        d = dict(zip(campos, key))
        d.update({'docs': len(a['docs']), 'ultimo': a['ultimo'], 'tipos_material': dict(a['mtyp'].most_common(4))})
        return d

    # ---------- traslados ----------
    def destinos(self, o_pl, o_alm='', limite=40):
        """Destinos usados en ECC desde una planta (y almacén, si se indica), agrupados por planta/almacén destino."""
        agg = {}
        for k, a in self.sto.items():
            t, sp, ist, pl, sl = k
            if sp != o_pl or (o_alm and ist and ist != o_alm):
                continue
            g = agg.setdefault((pl, sl), {'docs': set(), 'ultimo': '', 'tipos': collections.Counter(), 'alm_origen': collections.Counter()})
            g['docs'] |= a['docs']
            g['ultimo'] = max(g['ultimo'], a['ultimo'])
            g['tipos'][t] += len(a['docs'])
            g['alm_origen'][ist or '—'] += len(a['docs'])
        out = [{'planta': pl, 'alm': sl, 'docs': len(g['docs']), 'ultimo': g['ultimo'], 'tipo': g['tipos'].most_common(1)[0][0],
                'alm_origen': g['alm_origen'].most_common(1)[0][0]} for (pl, sl), g in agg.items()]
        out.sort(key=lambda x: -x['docs'])
        return out[:limite]

    def traslado(self, o_pl, o_alm, d_pl, d_alm):
        """¿Existía este traslado? Un almacén vacío (ECC no siempre lo trae) casa con cualquiera."""
        docs, ultimo, tipos = set(), '', collections.Counter()
        exacto = False
        for (t, sp, ist, pl, sl), a in self.sto.items():
            if sp != o_pl or pl != d_pl:
                continue
            if o_alm and ist and ist != o_alm:
                continue
            if d_alm and sl and sl != d_alm:
                continue
            docs |= a['docs']
            ultimo = max(ultimo, a['ultimo'])
            tipos[t] += len(a['docs'])
            exacto = exacto or (ist == o_alm and sl == d_alm)
        if not docs:
            par = any(sp == o_pl and pl == d_pl for (_, sp, _, pl, _) in self.sto)
            return {'existe': False, 'mismo_par_plantas': par}
        return {'existe': True, 'docs': len(docs), 'ultimo': ultimo, 'tipo': tipos.most_common(1)[0][0], 'almacenes_exactos': exacto}

    def origenes(self, tipo, d_pl, limite=3):
        """Plantas que suministraban a d_pl en ECC (del mismo tipo de documento; si no hay, de cualquier tipo de traslado), con nº de documentos."""
        por_tipo, cualquiera = collections.Counter(), collections.Counter()
        for (t, sp, ist, pl, sl), a in self.sto.items():
            if pl != d_pl:
                continue
            cualquiera[sp] += len(a['docs'])
            if t == tipo:
                por_tipo[sp] += len(a['docs'])
        return (por_tipo or cualquiera).most_common(limite), bool(por_tipo)

    # ---------- por material: ¿esos materiales se compraban / trasladaban así en ECC? ----------
    def mats_compra(self, vendor, plnt, mats):
        """Materiales (de la lista) que se compraron en ECC a ese proveedor en esa planta."""
        d = self.po_m.get((str(vendor).strip().lstrip('0'), plnt), {})
        si = [m for m in mats if d.get(m)]
        return {'si': si, 'no': [m for m in mats if m not in si]}

    def mats_traslado(self, o_pl, d_pl, mats):
        si = [m for m in mats if self.sto_m.get((o_pl, d_pl, m))]
        return {'si': si, 'no': [m for m in mats if m not in si]}

    # ---------- compras ----------
    def proveedores(self, plnt, sloc='', limite=40):
        agg = {}
        for (t, v, pl, sl), a in self.po.items():
            if pl != plnt or (sloc and sl and sl != sloc):
                continue
            g = agg.setdefault(v, {'docs': set(), 'ultimo': ''})
            g['docs'] |= a['docs']
            g['ultimo'] = max(g['ultimo'], a['ultimo'])
        out = [{'proveedor': v, 'docs': len(g['docs']), 'ultimo': g['ultimo']} for v, g in agg.items()]
        out.sort(key=lambda x: -x['docs'])
        return out[:limite]

    def compra(self, vendor, plnt, sloc):
        docs, ultimo = set(), ''
        for (t, v, pl, sl), a in self.po.items():
            if v == vendor and pl == plnt and (not sloc or not sl or sl == sloc):
                docs |= a['docs']
                ultimo = max(ultimo, a['ultimo'])
        if docs:
            return {'existe': True, 'docs': len(docs), 'ultimo': ultimo}
        return {'existe': False, 'proveedor_en_planta': any(v == vendor and pl == plnt for (_, v, pl, _) in self.po)}


_INSTANCE = {}


def get(path):
    """Se carga una sola vez (tarda unos segundos)."""
    with _LOCK:
        if path not in _INSTANCE:
            _INSTANCE[path] = Ecc(path)
        return _INSTANCE[path]
