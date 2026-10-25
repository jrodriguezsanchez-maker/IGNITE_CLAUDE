"""Muestra en qué transacción está cada sesión de la conexión permitida. SOLO LECTURA (no toca nada). Uso: python sap_ver_sesiones.py"""
import faulthandler

import sap_backend
import sap_mb52

faulthandler.dump_traceback_later(40, exit=True)

p = (sap_backend.leer_config().get("sistemas_permitidos") or [None])[0]
pc = sap_mb52.pythoncom
pc.CoInitialize()
try:
    for con, s in sap_mb52._sesiones(sap_mb52._engine(), p["sid"], p["mandante"], p.get("conexion")):
        print("sesión %s · transacción %s · ventanas %d · ocupada %s" % (s.Id.split("/")[-1], s.Info.Transaction, s.Children.Count, s.Busy))
finally:
    pc.CoUninitialize()
