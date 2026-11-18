"""Lista los controles de la pantalla de selección de SE16N para una tabla (SOLO LECTURA: no ejecuta la consulta, no teclea criterios).
Uso:  python sap_se16n_campos.py MKPF      (salvar la salida a un fichero; no cortarla con tuberías)
"""
import faulthandler
import sys

import sap_backend
import sap_mb52
import sap_migo
from sap_migo_campos import recorrer

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
        print("pantalla:", str(ses.findById("wnd[0]").Text).strip(), "| ventanas:", ses.Children.Count, flush=True)
        salida = []
        recorrer(ses.findById("wnd[0]/usr"), salida)
        print("\n=== SE16N inicial (%d) ===" % len(salida))
        print("\n".join(salida), flush=True)
        t = sap_migo._buscar(ses.findById("wnd[0]/usr"), "GuiCTextField", "GD-TAB") or sap_migo._buscar(ses.findById("wnd[0]/usr"), "GuiTextField", "GD-TAB")
        print("\ncampo de tabla:", str(t.Id).split("/")[-1] if t is not None else None, flush=True)
        if t is not None:
            t.text = tabla
            ses.findById("wnd[0]").sendVKey(0)
            sap_migo._esperar(ses)
            salida = []
            recorrer(ses.findById("wnd[0]/usr"), salida, 400)
            print("\n=== SE16N con %s (%d elementos; se muestran los primeros 80) ===" % (tabla, len(salida)))
            print("\n".join(salida[:80]), flush=True)
            sb = ses.findById("wnd[0]/sbar")
            print("barra de estado:", str(sb.Text).strip(), "(%s)" % sb.MessageType, flush=True)
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
