"""Propone candidatos para un 301 (traslado entre centros): lee MB52 de un centro/almacén (SOLO LECTURA) y lista lotes con mucho stock libre.
Uso: python sap_candidatos_301.py <centro> <almacen>   (salvar la salida a un fichero)"""
import faulthandler
import sys

import sap_backend
import sap_mb52

faulthandler.dump_traceback_later(240, exit=True)


def main():
    centro, almacen = sys.argv[1], sys.argv[2]
    p = (sap_backend.leer_config().get("sistemas_permitidos") or [None])[0]
    pc = sap_mb52.pythoncom
    pc.CoInitialize()
    ses = creada = None
    try:
        ses, creada = sap_mb52.sesion(p["sid"], crear=True, mandante=p["mandante"], conexion=p.get("conexion"))
        assert str(ses.Info.SystemName).upper() == p["sid"].upper() and str(ses.Info.Client) == str(p["mandante"])
        r = sap_mb52.consultar(ses, "", centro, almacen, lotes=True, especiales=False, columnas=sap_mb52.COLUMNAS_STOCK)
        lineas = []
        for f in r["filas"]:
            mat = str(f.get("MATNR", "")).strip()
            if mat:
                lineas.append((mat.lstrip("0"), str(f.get("MAKTX", "")).strip()[:30], str(f.get("CHARG", "")).strip(), str(f.get("MEINS", "")).strip(),
                               sap_backend.numero(f.get("LABST", "0")), sap_backend.numero(f.get("SPEME", "0")), sap_backend.numero(f.get("INSME", "0"))))
        print("MB52 %s/%s: %d líneas" % (centro, almacen, len(lineas)), flush=True)
        buenas = sorted([l for l in lineas if l[4] >= 500], key=lambda l: -l[4])
        print("Lotes con >= 500 libres (los 12 mayores):", flush=True)
        for l in buenas[:12]:
            print("  material %s · %s · lote %s · %s %s libres (bloq %s, calidad %s)" % (l[0], l[1].encode("ascii", "replace").decode(), l[2].encode("ascii", "replace").decode(), l[4], l[3], l[5], l[6]), flush=True)
        print("transacción final:", ses.Info.Transaction, flush=True)
    finally:
        if ses is not None and creada:
            sap_mb52.cerrar_sesion(ses)
        pc.CoUninitialize()


if __name__ == "__main__":
    sys.exit(main())
