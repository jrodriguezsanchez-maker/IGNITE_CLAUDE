"""Diagnóstico de la pantalla de MIGO tras fijar el movimiento por defecto (344). NO contabiliza, NO teclea material ni cantidades.
Lista los campos de la tabla de posiciones y del detalle tal como quedan, y sale de MIGO. Salvar la salida a un fichero."""
import faulthandler
import sys

import sap_backend
import sap_mb52
import sap_migo
from sap_migo_campos import recorrer

faulthandler.dump_traceback_later(150, exit=True)


def main():
    p = (sap_backend.leer_config().get("sistemas_permitidos") or [None])[0]
    pc = sap_mb52.pythoncom
    pc.CoInitialize()
    ses, creada = sap_mb52.sesion(p["sid"], crear=True, mandante=p["mandante"], conexion=p.get("conexion"))
    try:
        assert str(ses.Info.SystemName).upper() == p["sid"].upper() and str(ses.Info.Client) == str(p["mandante"])
        print("sesión nueva:", creada, flush=True)

        def ir(c):
            ses.findById("wnd[0]/tbar[0]/okcd").text = c
            ses.findById("wnd[0]").sendVKey(0)
            sap_migo._esperar(ses)

        ir("/nMIGO")
        usr = lambda: ses.findById("wnd[0]/usr")
        for sufijo, texto in (("GODYNPRO-ACTION", "Transfer Posting"), ("GODYNPRO-REFDOC", "Other")):
            c = sap_migo._buscar(usr(), "GuiComboBox", sufijo)
            for k in range(c.Entries.Count):
                if texto.lower() in str(c.Entries.Item(k).Value).lower():
                    c.key = c.Entries.Item(k).Key
                    sap_migo._esperar(ses, 30)
                    break
        bw = sap_migo._buscar(usr(), "GuiCTextField", "GODEFAULT_TV-BWART")
        bw.text = "344"
        ses.findById("wnd[0]").sendVKey(0)
        sap_migo._esperar(ses)
        print("ventanas emergentes:", ses.Children.Count, "| título:", str(ses.findById("wnd[0]").Text).strip(), flush=True)
        print("movimiento por defecto ahora:", sap_migo._buscar(usr(), "GuiCTextField", "GODEFAULT_TV-BWART").text, flush=True)
        salida = []
        recorrer(usr(), salida)
        print("\n=== pantalla tras fijar 344 (%d elementos) ===" % len(salida))
        print("\n".join(salida), flush=True)
        sb = ses.findById("wnd[0]/sbar")
        print("\nbarra de estado:", str(sb.Text).strip(), "(%s)" % sb.MessageType, flush=True)
    finally:
        try:
            ses.findById("wnd[0]/tbar[0]/okcd").text = "/n"
            ses.findById("wnd[0]").sendVKey(0)
            sap_migo._esperar(ses)
            if ses.Children.Count > 1:
                print("ventana al salir:", str(ses.findById("wnd[1]").Text).strip(), flush=True)
        except Exception:
            pass
        print("transacción final:", ses.Info.Transaction, flush=True)
        if creada:
            sap_mb52.cerrar_sesion(ses)
            print("sesión nueva cerrada.", flush=True)
        pc.CoUninitialize()


if __name__ == "__main__":
    sys.exit(main())
