"""Diagnóstico de las filas de MB52 que mi lectura descarta por no tener material. SOLO LECTURA.
Uso: python sap_mb52_filas.py   (salvar la salida a un fichero)"""
import faulthandler
import sys
from collections import Counter

import sap_backend
import sap_mb52

faulthandler.dump_traceback_later(250, exit=True)
CENTRO, ALMACEN = "M117", "1000"


def main():
    p = (sap_backend.leer_config().get("sistemas_permitidos") or [None])[0]
    pc = sap_mb52.pythoncom
    pc.CoInitialize()
    ses = creada = None
    try:
        ses, creada = sap_mb52.sesion(p["sid"], crear=True, mandante=p["mandante"], conexion=p.get("conexion"))
        assert str(ses.Info.SystemName).upper() == p["sid"].upper() and str(ses.Info.Client) == str(p["mandante"])
        r = sap_mb52.consultar(ses, "", CENTRO, ALMACEN, lotes=True, especiales=False, max_filas=5000)
        filas = r["filas"]
        sin_mat = [f for f in filas if not str(f.get("MATNR", "")).strip()]
        con_mat = [f for f in filas if str(f.get("MATNR", "")).strip()]
        print("columnas:", [c for c, _ in r["columnas"]][:12], "...", flush=True)
        print("filas ALV: %d · con MATNR: %d · sin MATNR: %d" % (len(filas), len(con_mat), len(sin_mat)), flush=True)
        # ¿qué tienen las filas sin material?
        def resumen(f):
            return {k: str(v).strip() for k, v in f.items() if str(v).strip() and k in ("MAKTX", "WERKS", "LGORT", "CHARG", "MEINS", "LABST", "WLABS", "SPEME", "INSME", "UMLME")}
        print("\nPrimeras 12 filas SIN material:", flush=True)
        for f in sin_mat[:12]:
            print("  ", resumen(f), flush=True)
        print("\nFilas sin material con descripción (MAKTX):", sum(1 for f in sin_mat if str(f.get("MAKTX", "")).strip()), flush=True)
        print("Filas sin material con CHARG (lote):", sum(1 for f in sin_mat if str(f.get("CHARG", "")).strip()), flush=True)
        print("Filas sin material con LABST distinto de 0:", sum(1 for f in sin_mat if sap_backend.numero(f.get("LABST", "0")) != 0), flush=True)
        print("Filas sin material con WERKS:", sum(1 for f in sin_mat if str(f.get("WERKS", "")).strip()), flush=True)
        print("\nPrimeras 6 filas CON material:", flush=True)
        for f in con_mat[:6]:
            print("  ", resumen(f), flush=True)
        print("Índices de las filas con material (primeros 30):", [i for i, f in enumerate(filas) if str(f.get("MATNR", "")).strip()][:30], flush=True)
        print("transacción final:", ses.Info.Transaction, flush=True)
    finally:
        if ses is not None and creada:
            sap_mb52.cerrar_sesion(ses)
            print("sesión nueva cerrada.", flush=True)
        pc.CoUninitialize()


if __name__ == "__main__":
    sys.exit(main())
