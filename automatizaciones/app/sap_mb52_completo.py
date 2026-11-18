"""Prueba de que la lectura de MB52 no se deja líneas: tras leer el listado de un centro/almacén, pide a SAP los materiales MAYORES que el último leído.
Si SAP dice que no hay stock, el listado estaba completo. SOLO LECTURA. Salvar la salida a un fichero."""
import faulthandler
import sys

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
        mats = sorted({str(f["MATNR"]).strip().lstrip("0") for f in r["filas"] if str(f.get("MATNR", "")).strip()}, key=lambda m: (len(m), m))
        print("líneas con material: %d · materiales distintos: %d · primero %s · último %s" % (sum(1 for f in r["filas"] if str(f.get("MATNR", "")).strip()), len(mats), mats[0], mats[-1]), flush=True)
        ultimo = mats[-1]
        # materiales estrictamente mayores que el último (si es numérico) hasta el máximo posible
        desde = str(int(ultimo) + 1) if ultimo.isdigit() else ultimo
        r2 = sap_mb52.consultar(ses, desde, CENTRO, ALMACEN, lotes=True, especiales=False, max_filas=5000, material_hasta="999999999999999999")
        n2 = sum(1 for f in r2["filas"] if str(f.get("MATNR", "")).strip())
        print("materiales MAYORES que %s en %s/%s: %d líneas · mensaje de SAP: %r" % (ultimo, CENTRO, ALMACEN, n2, r2["mensaje"]), flush=True)
        print("CONCLUSIÓN:", "listado completo (no hay nada más allá del último material)" if n2 == 0 else "¡FALTAN LÍNEAS en la lectura!", flush=True)
        print("transacción final:", ses.Info.Transaction, flush=True)
    finally:
        if ses is not None and creada:
            sap_mb52.cerrar_sesion(ses)
            print("sesión nueva cerrada.", flush=True)
        pc.CoUninitialize()


if __name__ == "__main__":
    sys.exit(main())
