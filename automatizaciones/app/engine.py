"""Motor del flujo "Movimientos de material".

SapBackend es la interfaz que implementará el enganche a SAP GUI (fase posterior).
MockSap simula stock de forma determinista: NO toca SAP. Todo resultado es simulado.
"""
import hashlib
import re

ALIAS = {
    "tipo_mov": ["tipo movimiento", "tipo de movimiento", "clase de movimiento", "tipomov", "mvt", "bwart", "movimiento"],
    "material": ["material", "matnr", "n material", "numero de material"],
    "centro": ["centro", "werks", "planta"],
    "alm_origen": ["almacen origen", "almacén origen", "almacen", "almacén", "lgort", "alm origen"],
    "centro_destino": ["centro destino", "centro receptor"],
    "alm_destino": ["almacen destino", "almacén destino", "alm destino"],
    "cantidad": ["cantidad", "menge", "qty"],
    "um": ["um", "unidad", "unidad de medida", "meins"],
    "lote": ["lote", "charg", "batch"],
    "vendor": ["vendor", "proveedor"],
    "ceco": ["ceco", "centro de coste"],
    "orden": ["orden"],
    "po": ["po", "pedido"],
    "motivo": ["motivo"],
}
REQUIRED = ["tipo_mov", "material", "centro", "alm_origen", "cantidad"]


def _norm(s):
    return re.sub(r"\s+", " ", str(s).strip().lower())


def map_columns(headers):
    mapping = {}
    for key, aliases in ALIAS.items():
        for h in headers:
            if _norm(h) in [_norm(a) for a in aliases]:
                mapping[key] = h
                break
    missing = [k for k in REQUIRED if k not in mapping]
    return mapping, missing


class SapBackend:
    simulado = False
    puede_proponer_cantidad = False   # True solo con SAP conectado (lee stock real)

    def proponer_cantidad(self, material, centro, almacen, wm):
        """Con SAP: stock libre del lote elegido (FEFO/FIFO) -> {"lote": ..., "cantidad": ...}; None si no hay."""
        return None

    def stock_origen(self, material, centro, almacen, wm):
        raise NotImplementedError

    def registro_info(self, material, centro_suministrador, org_compras):
        raise NotImplementedError

    def mb52(self, material, centro, almacen):
        raise NotImplementedError

    def migo(self, tipo_mov, material, centro, almacen, lote, cantidad, um, destino, extra=None):
        raise NotImplementedError


class MockSap(SapBackend):
    simulado = True

    def _h(self, *parts):
        return int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest(), 16)

    def mb52(self, material, centro, almacen):
        h = self._h(material, centro, almacen)
        if h % 5 == 0:
            return {"lotes_activo": False, "lineas": []}
        if h % 2 == 0:
            return {"lotes_activo": False, "lineas": [{"lote": "", "qty": 10 + h % 90, "caducidad": "", "entrada": ""}]}
        n = 1 + h % 3
        lineas = [{"lote": "L%07d" % ((h >> (i * 4)) % 10**7), "qty": 5 + (h >> (i * 3)) % 40,
                   "caducidad": "2027-%02d-15" % (1 + (h >> i) % 12) if h % 3 == 0 else "",
                   "entrada": "2026-%02d-01" % (1 + (h >> (i + 2)) % 12)} for i in range(n)]
        return {"lotes_activo": True, "lineas": lineas}

    def migo(self, tipo_mov, material, centro, almacen, lote, cantidad, um, destino, extra=None):
        return "SIM-%010d" % (self._h(tipo_mov, material, lote, cantidad) % 10**10)

    # --- Pedido de traslado (STO) y entrega de salida (en SAP real: ME13, MB52/LS24, ME21N, VL01N) ---
    def registro_info(self, material, centro_suministrador, org_compras):
        return self._h(material, centro_suministrador, org_compras, "info") % 6 != 0

    def stock_origen(self, material, centro, almacen, wm):
        s = self.mb52(material, centro, almacen)
        s["fuente"] = "WM (LS24/LX02)" if wm else "MB52"
        return s

    def crear_sto(self, tipo, centro, centro_destino, org_compras, sociedad, items):
        return "SIM-PO-%010d" % (self._h(tipo, centro, centro_destino, str(items)) % 10**10)

    def crear_entrega(self, sto, items):
        return "SIM-DL-%010d" % (self._h(sto, "entrega") % 10**10)

    # --- Apuntes derivados del documento de material (en SAP real: FB03, KE24, CKM3N) ---
    def apuntes_fi(self, doc, material, centro, cantidad):
        h = self._h(doc, "fi")
        precio = 1 + h % 50
        importe = round(float(cantidad) * precio, 2)
        return [{"doc_fi": "SIMFI-%08d" % (h % 10**8), "pos": 1, "cuenta": "300000", "dc": "D", "importe": importe, "moneda": "EUR", "centro_coste": ""},
                {"doc_fi": "SIMFI-%08d" % (h % 10**8), "pos": 2, "cuenta": "400000", "dc": "H", "importe": -importe, "moneda": "EUR", "centro_coste": ""}]

    def apuntes_co(self, doc, material, centro, cantidad):
        h = self._h(doc, "co")
        return [{"objeto_co": "CC%06d" % (h % 10**6), "clase_coste": "400000", "valor": round(float(cantidad) * (1 + h % 50), 2), "moneda": "EUR"}]

    def datos_ml(self, doc, material, centro, cantidad):
        h = self._h(doc, "ml")
        std = 1 + h % 50
        return [{"material": material, "centro": centro, "control_precio": "S" if h % 2 else "V", "precio": std,
                 "cantidad": cantidad, "valor": round(float(cantidad) * std, 2), "diferencia_precio": 0.0, "moneda": "EUR"}]


def _num(v):
    return float(str(v).replace(",", "."))


def _orden(l):
    # FEFO: caducidad asc (los que no caducan al final); desempate FIFO por fecha de entrada
    return (l["caducidad"] or "9999-99-99", l["entrada"] or "9999-99-99")


def run(headers, rows, backend, log):
    mapping, missing = map_columns(headers)
    if missing:
        log("ERROR", "Faltan columnas obligatorias: %s" % ", ".join(missing))
        return [], {"error": "columnas"}

    def g(r, k):
        return str(r.get(mapping.get(k, ""), "")).strip()

    results, resumen = [], {"OK": 0, "PARCIAL": 0, "SIN_STOCK": 0, "ERROR": 0}
    for i, r in enumerate(rows, start=2):
        ref = "fila %d" % i
        res = {"fila": i, "tipo_mov": g(r, "tipo_mov"), "material": g(r, "material"), "centro": g(r, "centro"),
               "almacen": g(r, "alm_origen"), "pedida": g(r, "cantidad"), "movida": 0, "estado": "", "detalle": "", "documentos": []}
        try:
            pedida = _num(res["pedida"])
            if pedida <= 0 or not res["material"]:
                raise ValueError("Material o cantidad no válido")
            stock = backend.mb52(res["material"], res["centro"], res["almacen"])
            lineas = [l for l in stock["lineas"] if l["qty"] > 0]
            if g(r, "lote"):
                lineas = [l for l in lineas if l["lote"] == g(r, "lote")]
            disponible = sum(l["qty"] for l in lineas)
            log("INFO", "%s MB52 %s/%s/%s: stock %s, lotes=%s" % (ref, res["material"], res["centro"], res["almacen"], disponible, stock["lotes_activo"]))
            if disponible <= 0:
                res["estado"], res["detalle"] = "SIN_STOCK", "Sin stock libre en origen"
            else:
                a_mover = min(pedida, disponible)
                pendiente = a_mover
                for l in sorted(lineas, key=_orden):
                    if pendiente <= 0:
                        break
                    q = min(pendiente, l["qty"])
                    doc = backend.migo(res["tipo_mov"], res["material"], res["centro"], res["almacen"], l["lote"], q, g(r, "um"),
                                       (g(r, "centro_destino"), g(r, "alm_destino")),
                                       {k: g(r, k) for k in ("vendor", "ceco", "orden", "po", "motivo")})
                    res["documentos"].append({"doc": doc, "lote": l["lote"], "cantidad": q})
                    pendiente -= q
                res["movida"] = a_mover
                if a_mover < pedida:
                    res["estado"] = "PARCIAL"
                    res["detalle"] = "Movido %s de %s (faltan %s)" % (a_mover, pedida, pedida - a_mover)
                else:
                    res["estado"] = "OK"
        except Exception as e:  # una fila fallida no detiene el resto
            res["estado"], res["detalle"] = "ERROR", str(e)
        resumen[res["estado"]] += 1
        log("INFO" if res["estado"] == "OK" else "WARN", "%s -> %s %s" % (ref, res["estado"], res["detalle"]))
        results.append(res)
    return results, resumen


def crear_backend():
    """Backend activo. Hoy simulado; con la conexión a SAP GUI devolverá el backend real."""
    return MockSap()
