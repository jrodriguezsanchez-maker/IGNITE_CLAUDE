"""Prueba controlada de la MIGO real (un solo documento, con datos confirmados por el usuario).

Uso:  python sap_migo_prueba.py comprobar
      python sap_migo_prueba.py contabilizar <huella>
Datos fijos de esta prueba (confirmados por el usuario): 344 · material 108210 · centro L056 · almacén 1000 · lote 73994721 · 1 KG.
Muestra el stock del lote (MB52) antes y, al contabilizar, también después. Salvar la salida a un fichero; no cortarla con tuberías.
"""
import faulthandler
import sys

import sap_backend
import sap_migo
import sap_mb52

faulthandler.dump_traceback_later(240, exit=True)

DATOS = dict(mov="344", material="108210", centro="L056", almacen="1000", lote="73994721", cantidad="1", um="KG", motivo="0046")   # 0046 = Blocked Temporarily


def stock_lote(ses):
    r = sap_mb52.consultar(ses, DATOS["material"], DATOS["centro"], DATOS["almacen"], lotes=True, especiales=False)
    for f in r["filas"]:
        if str(f.get("CHARG", "")).strip() == DATOS["lote"]:
            return {"libre": f.get("LABST"), "bloqueado": f.get("SPEME"), "calidad": f.get("INSME"), "unidad": f.get("MEINS")}
    return {"mensaje": r["mensaje"]}


def main():
    modo = sys.argv[1] if len(sys.argv) > 1 else "comprobar"
    clave = sys.argv[2] if len(sys.argv) > 2 else None
    p = (sap_backend.leer_config().get("sistemas_permitidos") or [None])[0]
    pc = sap_mb52.pythoncom
    pc.CoInitialize()
    ses = creada = None
    try:
        ses, creada = sap_mb52.sesion(p["sid"], crear=True, mandante=p["mandante"], conexion=p.get("conexion"))
        if str(ses.Info.SystemName).upper() != p["sid"].upper() or str(ses.Info.Client) != str(p["mandante"]):
            print("ABORTADO: la sesión no es del sistema/mandante permitidos.")
            return 1
        print("Sesión %s/%s · sesión nueva creada por el programa: %s" % (p["sid"], p["mandante"], creada), flush=True)
        print("huella calculada:", sap_migo.huella(DATOS["mov"], DATOS["material"], DATOS["centro"], DATOS["almacen"], DATOS["lote"], DATOS["cantidad"], DATOS["motivo"]), flush=True)
        print("STOCK ANTES  (MB52, lote %s):" % DATOS["lote"], stock_lote(ses), flush=True)
        try:
            res = sap_migo.traspaso(ses, modo=modo, clave=clave, **DATOS)
            print("RESULTADO MIGO:", res, flush=True)
        except sap_migo.MigoError as e:
            print("MIGO NO CONTINÚA (no se ha contabilizado nada):", e, flush=True)
            return 1
        if modo == "contabilizar":
            print("STOCK DESPUÉS (MB52, lote %s):" % DATOS["lote"], stock_lote(ses), flush=True)
        print("transacción final de la sesión:", ses.Info.Transaction, flush=True)
    finally:
        if ses is not None and creada:
            sap_mb52.cerrar_sesion(ses)
            print("sesión nueva cerrada.", flush=True)
        pc.CoUninitialize()
    return 0


if __name__ == "__main__":
    sys.exit(main())
