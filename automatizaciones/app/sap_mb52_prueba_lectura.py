"""Prueba de la lectura completa de MB52 (con desplazamiento del ALV). SOLO LECTURA. Salvar la salida a un fichero.
1) lee todo el centro/almacén; 2) lo parte por rangos de material y comprueba que la suma coincide; 3) compara con las 33 líneas de la captura del usuario."""
import faulthandler
import sys
import time

import sap_backend
import sap_mb52
from sap_mb52_validar import ESPERADO

faulthandler.dump_traceback_later(290, exit=True)
CENTRO, ALMACEN = "M117", "1000"
RANGOS = [("", "199999"), ("200000", "299999"), ("300000", "329999"), ("330000", "339999"), ("340000", "999999999")]


def leer(ses, desde, hasta):
    t = time.time()
    r = sap_mb52.consultar(ses, desde, CENTRO, ALMACEN, lotes=True, especiales=False, material_hasta=hasta, columnas=sap_mb52.COLUMNAS_STOCK)
    datos = [f for f in r["filas"] if str(f.get("MATNR", "")).strip()]
    return r, datos, time.time() - t


def main():
    p = (sap_backend.leer_config().get("sistemas_permitidos") or [None])[0]
    pc = sap_mb52.pythoncom
    pc.CoInitialize()
    ses = creada = None
    try:
        ses, creada = sap_mb52.sesion(p["sid"], crear=True, mandante=p["mandante"], conexion=p.get("conexion"))
        assert str(ses.Info.SystemName).upper() == p["sid"].upper() and str(ses.Info.Client) == str(p["mandante"])
        r, datos, seg = leer(ses, "", "")
        mats = {str(f["MATNR"]).strip() for f in datos}
        print("1) TODO el centro %s/%s: %d líneas · %d materiales · filas ALV %s · leídas %s · vacías %s · %.0fs" % (CENTRO, ALMACEN, len(datos), len(mats), r["total_filas"], r["leidas"], r["vacias"], seg), flush=True)
        suma = 0
        for d, h in RANGOS:
            rr, dd, s2 = leer(ses, d, h)
            suma += len(dd)
            print("   rango %-9s..%-10s %4d líneas · vacías %s · %.0fs" % (d or "(inicio)", h, len(dd), rr.get("vacias"), s2), flush=True)
        print("2) suma de los rangos = %d · lectura completa = %d -> %s" % (suma, len(datos), "COINCIDEN" if suma == len(datos) else "¡NO COINCIDEN!"), flush=True)
        idx = {}
        for f in datos:
            k = (str(f["MATNR"]).strip().lstrip("0"), str(f["CHARG"]).strip())
            idx[k] = idx.get(k, 0.0) + sap_backend.numero(f.get("LABST", "0"))
        ok = sum(1 for m, l, c in ESPERADO if abs(idx.get((m, l), -1) - c) <= 1e-6 * max(1, c))
        print("3) comparación con la captura del usuario: %d de %d líneas coinciden" % (ok, len(ESPERADO)), flush=True)
        print("transacción final:", ses.Info.Transaction, flush=True)
    finally:
        if ses is not None and creada:
            sap_mb52.cerrar_sesion(ses)
            print("sesión nueva cerrada.", flush=True)
        pc.CoUninitialize()


if __name__ == "__main__":
    sys.exit(main())
