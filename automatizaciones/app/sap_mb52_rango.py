"""Diagnóstico: ¿se aplica el rango de materiales en MB52? SOLO LECTURA. Salvar la salida a un fichero."""
import faulthandler
import sys

import sap_backend
import sap_mb52
import sap_migo

faulthandler.dump_traceback_later(250, exit=True)
CENTRO, ALMACEN = "M117", "1000"


def leer(ses, desde, hasta):
    ses.findById("wnd[0]/tbar[0]/okcd").text = "/nMB52"
    ses.findById("wnd[0]").sendVKey(0)
    sap_migo._esperar(ses)
    u = "wnd[0]/usr/"
    ses.findById(u + "ctxtMATNR-LOW").text = desde
    ses.findById(u + "ctxtMATNR-HIGH").text = hasta
    ses.findById(u + "ctxtWERKS-LOW").text = CENTRO
    ses.findById(u + "ctxtLGORT-LOW").text = ALMACEN
    ses.findById(u + "chkXMCHB").selected = True
    ses.findById(u + "chkPA_SOND").selected = False
    ses.findById(u + "chkNOZERO").selected = True
    quedaron = (ses.findById(u + "ctxtMATNR-LOW").text, ses.findById(u + "ctxtMATNR-HIGH").text)
    ses.findById("wnd[0]/tbar[1]/btn[8]").press()
    sap_migo._esperar(ses)
    sb = ses.findById("wnd[0]/sbar")
    grid = sap_mb52._buscar_grid(ses.findById("wnd[0]/usr"))
    mats = []
    if grid is not None:
        for r in range(grid.RowCount):
            m = str(grid.GetCellValue(r, "MATNR")).strip()
            if m:
                mats.append(m)
    ses.findById("wnd[0]/tbar[0]/okcd").text = "/n"
    ses.findById("wnd[0]").sendVKey(0)
    sap_migo._esperar(ses)
    return quedaron, str(sb.Text).strip(), mats


def main():
    p = (sap_backend.leer_config().get("sistemas_permitidos") or [None])[0]
    pc = sap_mb52.pythoncom
    pc.CoInitialize()
    ses = creada = None
    try:
        ses, creada = sap_mb52.sesion(p["sid"], crear=True, mandante=p["mandante"], conexion=p.get("conexion"))
        assert str(ses.Info.SystemName).upper() == p["sid"].upper() and str(ses.Info.Client) == str(p["mandante"])
        for nombre, d, h in (("todo el centro", "", ""), ("rango 336148..999999999", "336148", "999999999"), ("rango 100000..199999", "100000", "199999"),
                             ("material exacto 336147", "336147", "")):
            q, msg, mats = leer(ses, d, h)
            print("%-26s pantalla quedó LOW=%r HIGH=%r · líneas %d · materiales distintos %d · primero %s último %s · SAP: %r" % (
                nombre, q[0], q[1], len(mats), len(set(mats)), mats[0] if mats else None, mats[-1] if mats else None, msg), flush=True)
        print("transacción final:", ses.Info.Transaction, flush=True)
    finally:
        if ses is not None and creada:
            sap_mb52.cerrar_sesion(ses)
            print("sesión nueva cerrada.", flush=True)
        pc.CoUninitialize()


if __name__ == "__main__":
    sys.exit(main())
