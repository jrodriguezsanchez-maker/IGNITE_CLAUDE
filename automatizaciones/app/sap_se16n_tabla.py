"""Inspecciona la tabla de criterios de SE16N (nombres de celdas y texto de las etiquetas de campo). SOLO LECTURA: no teclea criterios ni ejecuta.
Uso:  python sap_se16n_tabla.py MKPF"""
import faulthandler
import sys

import sap_backend
import sap_mb52
import sap_migo

faulthandler.dump_traceback_later(120, exit=True)


def main():
    tabla = (sys.argv[1] if len(sys.argv) > 1 else "MKPF").upper()
    p = (sap_backend.leer_config().get("sistemas_permitidos") or [None])[0]
    pc = sap_mb52.pythoncom
    pc.CoInitialize()
    ses, creada = sap_mb52.sesion(p["sid"], crear=True, mandante=p["mandante"], conexion=p.get("conexion"))
    try:
        assert str(ses.Info.SystemName).upper() == p["sid"].upper() and str(ses.Info.Client) == str(p["mandante"])

        def ir(c):
            ses.findById("wnd[0]/tbar[0]/okcd").text = c
            ses.findById("wnd[0]").sendVKey(0)
            sap_migo._esperar(ses)

        ir("/nSE16N")
        usr = lambda: ses.findById("wnd[0]/usr")
        t = sap_migo._buscar(usr(), "GuiCTextField", "GD-TAB")
        t.text = tabla
        ses.findById("wnd[0]").sendVKey(0)
        sap_migo._esperar(ses)
        tbl = sap_migo._buscar(usr(), "GuiTableControl", "tblSAPLSE16NSELFIELDS_TC")
        print("tabla de criterios:", str(tbl.Id).split("/")[-1], "| filas:", tbl.RowCount, "| visibles:", tbl.VisibleRowCount, flush=True)
        print("columnas:", [str(tbl.Columns.Item(i).Title) + "/" + str(tbl.Columns.Item(i).Name) for i in range(tbl.Columns.Count)], flush=True)
        hs = tbl.Children
        print("celdas hijas:", hs.Count, flush=True)
        for i in range(min(hs.Count, 60)):
            h = hs.Item(i)
            try:
                txt = str(h.Text).strip()
            except Exception:
                txt = "?"
            print("  %-4d %-12s %s  texto=%r" % (i, h.Type, str(h.Id).split("/")[-1], txt[:30]), flush=True)
        print("botones de la barra de herramientas:", [str(ses.findById("wnd[0]/tbar[1]").Children.Item(i).Tooltip) for i in range(ses.findById("wnd[0]/tbar[1]").Children.Count)], flush=True)
    finally:
        try:
            ses.findById("wnd[0]/tbar[0]/okcd").text = "/n"
            ses.findById("wnd[0]").sendVKey(0)
            sap_migo._esperar(ses)
        except Exception:
            pass
        print("transacción final:", ses.Info.Transaction, flush=True)
        if creada:
            sap_mb52.cerrar_sesion(ses)
            print("sesión nueva cerrada.", flush=True)
        pc.CoUninitialize()


if __name__ == "__main__":
    sys.exit(main())
