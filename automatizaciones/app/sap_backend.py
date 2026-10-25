"""Backend real contra SAP GUI (hoy SOLO CHEQUEO, lectura de stock con MB52).

Seguridad:
  - Solo se conecta a sistemas/mandantes listados en conexion_local.json (fuera de git). Si la sesión abierta no está en la lista, se aborta.
  - El usuario se loguea a mano: no hay usuarios ni contraseñas en ficheros.
  - La contabilización (MIGO, ME21N, VL10B) NO está implementada: cualquier intento falla. El lanzamiento sigue siendo simulado.
  - Límite de consultas por chequeo para no saturar el sistema.
"""
import json
import time
from pathlib import Path

import engine

CONFIG = Path(__file__).resolve().parent.parent / "conexion_local.json"
_STOCK_TTL = {}
MAX_CONSULTAS = 25


def leer_config():
    if CONFIG.exists():
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    return {"modo": "simulado", "sistemas_permitidos": []}


def guardar_modo(modo):
    cfg = leer_config()
    cfg["modo"] = modo
    CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    return cfg


def estado():
    """Diagnóstico de solo lectura de la conexión (botón «Probar conexión SAP»)."""
    cfg = leer_config()
    import sap_mb52
    pythoncom = sap_mb52.pythoncom
    if pythoncom is None:
        return {"ok": False, "mensaje": sap_mb52.msg_falta_pywin32()}
    pythoncom.CoInitialize()
    try:
        r = sap_mb52.estado(cfg.get("sistemas_permitidos") or [])
        r["enganches"] = sap_mb52.ATTACHES
        return r
    finally:
        pythoncom.CoUninitialize()


def numero(txt):
    """Formato numérico de SAP del usuario: punto de miles, coma decimal y signo detrás ('1.234,5-')."""
    t = str(txt).strip().replace(" ", "")
    if not t:
        return 0.0
    neg = t.endswith("-")
    t = t.rstrip("-").replace(".", "").replace(",", ".")
    try:
        v = float(t)
    except ValueError:
        return 0.0
    return -v if neg else v


class SapGuiBackend(engine.SapBackend):
    simulado = False
    puede_proponer_cantidad = True

    def __init__(self, cfg):
        import sap_mb52
        pythoncom = sap_mb52.pythoncom
        if pythoncom is None:
            raise ValueError(sap_mb52.msg_falta_pywin32())
        self._com = pythoncom
        self._mb52 = sap_mb52
        pythoncom.CoInitialize()
        self.ses = self.sid = self.mandante = None
        self._creada = False
        permitidos = cfg.get("sistemas_permitidos") or []
        if not permitidos:
            self.cerrar()
            raise ValueError("No hay sistemas permitidos en conexion_local.json.")
        errores = []
        for p in permitidos:
            try:
                ses, creada = sap_mb52.sesion(p["sid"], crear=True, mandante=p["mandante"], conexion=p.get("conexion"))   # sesión libre o, si no hay, una nueva
            except sap_mb52.SapError as e:
                errores.append(str(e))
                continue
            if str(ses.Info.Client) != str(p["mandante"]):
                if creada:
                    sap_mb52.cerrar_sesion(ses)
                errores.append("La sesión de %s es de otro mandante: no está permitido." % p["sid"])
                continue
            self.ses, self.sid, self.mandante, self._creada = ses, p["sid"], p["mandante"], creada
            break
        if self.ses is None:
            self.cerrar()
            raise ValueError("Modo SAP real: no hay sesión abierta en un sistema permitido. Abre SAP, entra y vuelve a intentarlo "
                             "(o cambia el chequeo a simulado). " + " ".join(errores))
        self._cache = {}
        self._consultas = 0

    def info(self):
        return {"sistema": self.sid, "mandante": self.mandante}

    def cerrar(self):
        if getattr(self, "_creada", False) and self.ses is not None:
            self._mb52.cerrar_sesion(self.ses)      # solo la sesión que abrió el programa
            self._creada = False
        try:
            self._com.CoUninitialize()
        except Exception:
            pass

    def _stock(self, material, centro, almacen):
        clave = (str(material), str(centro), str(almacen))
        if clave in self._cache:
            return self._cache[clave]
        hit = _STOCK_TTL.get(clave)
        if hit and time.time() - hit[0] < 45:        # se acaba de leer (p. ej. al preparar): no se vuelve a consultar SAP
            self._cache[clave] = hit[1]
            return hit[1]
        if self._consultas >= MAX_CONSULTAS:
            raise self._mb52.SapError("Límite de %d consultas a SAP por chequeo: reduce la selección." % MAX_CONSULTAS)
        self._consultas += 1
        # defensa en profundidad: justo antes de actuar se vuelve a comprobar que la sesión es del sistema y mandante permitidos
        if str(self.ses.Info.SystemName).upper() != str(self.sid).upper() or str(self.ses.Info.Client) != str(self.mandante):
            raise self._mb52.SapError("La sesión ya no es del sistema permitido (%s/%s): se aborta." % (self.sid, self.mandante))
        r = self._mb52.consultar(self.ses, material, centro, almacen, lotes=True, especiales=False, columnas=self._mb52.COLUMNAS_STOCK)
        lineas = []
        for f in r["filas"]:
            if not str(f.get("MATNR", "")).strip():
                continue           # fila de totales
            q = numero(f.get("LABST", "0"))
            if q > 0:
                lineas.append({"lote": str(f.get("CHARG", "")).strip(), "qty": q, "caducidad": "", "entrada": "",
                               "almacen": str(f.get("LGORT", "")).strip()})
        if not r["filas"] and "(E)" in r["mensaje"]:
            raise self._mb52.SapError("MB52: " + r["mensaje"])
        st = {"lotes_activo": any(l["lote"] for l in lineas), "lineas": lineas, "fuente": "MB52"}
        self._cache[clave] = st
        _STOCK_TTL[clave] = (time.time(), st)
        return st

    # --- lectura (implementada) ---
    def stock_origen(self, material, centro, almacen, wm):
        if wm:
            raise NotImplementedError("Almacén WM: la lectura de cuantos (LS24) aún no está implementada.")
        return self._stock(material, centro, almacen)

    def proponer_cantidad(self, material, centro, almacen, wm):
        lineas = sorted(self.stock_origen(material, centro, almacen, wm)["lineas"], key=engine._orden)
        return {"lote": lineas[0]["lote"], "cantidad": lineas[0]["qty"]} if lineas else None

    def registro_info(self, material, centro_suministrador, org_compras):
        raise NotImplementedError("Registro info (ME13): comprobación real aún no implementada.")

    # --- contabilización: NO implementada (a propósito) ---
    def _no(self, *a, **k):
        raise self._mb52.SapError("La contabilización real no está implementada: el lanzamiento es solo simulado.")

    migo = crear_sto = crear_entrega = mb52 = _no
