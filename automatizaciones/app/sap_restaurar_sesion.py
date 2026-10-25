"""Devuelve a la pantalla inicial las sesiones del sistema permitido que se hayan quedado abiertas en una transacción sin datos.

Solo actúa sobre la conexión permitida de conexion_local.json y solo sale de transacciones indicadas (por defecto MIGO) cuando no hay
ventanas emergentes. No contabiliza nada. Uso:  python sap_restaurar_sesion.py [TRANSACCION]
"""
import faulthandler
import sys
import time

import sap_backend
import sap_mb52

faulthandler.dump_traceback_later(60, exit=True)


def main():
    trx = (sys.argv[1] if len(sys.argv) > 1 else "MIGO").upper()
    p = (sap_backend.leer_config().get("sistemas_permitidos") or [None])[0]
    if not p:
        print("No hay sistemas permitidos.")
        return 2
    pc = sap_mb52.pythoncom
    pc.CoInitialize()
    try:
        for con, s in sap_mb52._sesiones(sap_mb52._engine(), p["sid"], p["mandante"], p.get("conexion")):
            print("sesión %s · transacción %s · ventanas %d" % (s.Id.split("/")[-1], s.Info.Transaction, s.Children.Count))
            if str(s.Info.Transaction).upper() == trx and s.Children.Count == 1:
                s.findById("wnd[0]/tbar[0]/okcd").text = "/n"
                s.findById("wnd[0]").sendVKey(0)
                t = time.time()
                while s.Busy and time.time() - t < 30:
                    time.sleep(0.2)
                print("   -> restaurada: transacción %s · ventanas %d" % (s.Info.Transaction, s.Children.Count))
    finally:
        pc.CoUninitialize()
    return 0


if __name__ == "__main__":
    sys.exit(main())
