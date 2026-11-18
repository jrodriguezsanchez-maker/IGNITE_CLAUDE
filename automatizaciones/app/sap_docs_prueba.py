"""Lee un documento de material y sus documentos contables (SOLO LECTURA). Uso: python sap_docs_prueba.py 4900022395 2026
Salvar la salida a un fichero; no cortarla con tuberías."""
import faulthandler
import json
import sys

import sap_backend
import sap_docs
import sap_mb52

faulthandler.dump_traceback_later(200, exit=True)


def main():
    matdoc, anio = sys.argv[1], sys.argv[2]
    p = (sap_backend.leer_config().get("sistemas_permitidos") or [None])[0]
    pc = sap_mb52.pythoncom
    pc.CoInitialize()
    ses = creada = None
    try:
        ses, creada = sap_mb52.sesion(p["sid"], crear=True, mandante=p["mandante"], conexion=p.get("conexion"))
        assert str(ses.Info.SystemName).upper() == p["sid"].upper() and str(ses.Info.Client) == str(p["mandante"])
        print("sesión nueva creada por el programa:", creada, flush=True)
        r = sap_docs.leer_documento(ses, matdoc, anio, depurar=True)
        print(json.dumps(r, ensure_ascii=False, indent=1), flush=True)
        print("transacción final:", ses.Info.Transaction, flush=True)
    except Exception as e:
        print("NO SE PUDO LEER (solo lectura, nada modificado):", e, flush=True)
        return 1
    finally:
        if ses is not None and creada:
            sap_mb52.cerrar_sesion(ses)
            print("sesión nueva cerrada.", flush=True)
        pc.CoUninitialize()
    return 0


if __name__ == "__main__":
    sys.exit(main())
