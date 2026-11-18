"""Lista los centros/almacenes donde existe un material (MB52 sin filtrar centro, SOLO LECTURA).
Uso: python sap_centros_material.py <material>   (salvar la salida a un fichero)"""
import faulthandler
import sys

import sap_backend
import sap_mb52

faulthandler.dump_traceback_later(240, exit=True)


def main():
    material = sys.argv[1]
    p = (sap_backend.leer_config().get("sistemas_permitidos") or [None])[0]
    pc = sap_mb52.pythoncom
    pc.CoInitialize()
    ses = creada = None
    try:
        ses, creada = sap_mb52.sesion(p["sid"], crear=True, mandante=p["mandante"], conexion=p.get("conexion"))
        assert str(ses.Info.SystemName).upper() == p["sid"].upper() and str(ses.Info.Client) == str(p["mandante"])
        r = sap_mb52.consultar(ses, material, "", "", lotes=True, especiales=False, columnas=sap_mb52.COLUMNAS_STOCK)
        print("mensaje SAP:", r["mensaje"], flush=True)
        for f in r["filas"]:
            if str(f.get("MATNR", "")).strip():
                print("  centro %s · almacén %s · lote %r · libre %s %s · bloq %s · calidad %s" % (
                    f.get("WERKS"), f.get("LGORT"), str(f.get("CHARG", "")).strip(), f.get("LABST"), f.get("MEINS"), f.get("SPEME"), f.get("INSME")), flush=True)
        print("transacción final:", ses.Info.Transaction, flush=True)
    finally:
        if ses is not None and creada:
            sap_mb52.cerrar_sesion(ses)
        pc.CoUninitialize()


if __name__ == "__main__":
    sys.exit(main())
