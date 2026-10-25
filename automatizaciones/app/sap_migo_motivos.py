"""Lee los motivos de movimiento válidos que ofrece MIGO para un traspaso (ayuda de entrada F4). NO contabiliza nada.

Rellena la MIGO como en la prueba (datos confirmados), pulsa Check, cierra el registro de mensajes (Continue), abre la ayuda F4 del campo
«motivo del movimiento», lee la lista, la cierra (Cancel) y sale de MIGO descartando los datos. Salvar la salida a un fichero.
"""
import faulthandler
from pathlib import Path
import json
import sys

import sap_backend
import sap_mb52
import sap_migo
from sap_migo import _buscar, _esperar, _texto_ventana

faulthandler.dump_traceback_later(240, exit=True)
D = json.loads((Path(__file__).parent / "data" / "pruebas_migo_local.json").read_text(encoding="utf-8"))["344"]   # datos locales, fuera de git


def main():
    p = (sap_backend.leer_config().get("sistemas_permitidos") or [None])[0]
    pc = sap_mb52.pythoncom
    pc.CoInitialize()
    ses, creada = sap_mb52.sesion(p["sid"], crear=True, mandante=p["mandante"], conexion=p.get("conexion"))
    try:
        assert str(ses.Info.SystemName).upper() == p["sid"].upper() and str(ses.Info.Client) == str(p["mandante"])
        usr = lambda: ses.findById("wnd[0]/usr")

        def ir(c):
            ses.findById("wnd[0]/tbar[0]/okcd").text = c
            ses.findById("wnd[0]").sendVKey(0)
            _esperar(ses)

        def intro():
            ses.findById("wnd[0]").sendVKey(0)
            _esperar(ses)

        def campo(suf):
            return _buscar(usr(), "GuiCTextField", suf) or _buscar(usr(), "GuiTextField", suf)

        ir("/nMIGO")
        for suf, txt in (("GODYNPRO-ACTION", "Transfer Posting"), ("GODYNPRO-REFDOC", "Other")):
            c = _buscar(usr(), "GuiComboBox", suf)
            for k in range(c.Entries.Count):
                if txt.lower() in str(c.Entries.Item(k).Value).lower():
                    c.key = c.Entries.Item(k).Key
                    _esperar(ses, 30)
                    break
        campo("GODEFAULT_TV-BWART").text = D["mov"]
        intro()
        campo("GODYNPRO-MAKTX").text = D["material"]
        intro()
        campo("GODYNPRO-NAME1").text = D["centro"]
        campo("GODYNPRO-LGOBE").text = D["almacen"]
        intro()
        c = campo("GOITEM-CHARG") or campo("GODYNPRO-CHARG")
        print("campo de lote encontrado:", str(c.Id).split("/")[-1] if c is not None else None, flush=True)
        if c is not None:
            c.text = D["lote"]
        campo("GODYNPRO-ERFMG").text = D["cantidad"]
        intro()
        sap_migo._boton_barra(ses, ("check",)).press()
        _esperar(ses)
        print("tras el Check:", _texto_ventana(ses)[:300], flush=True)
        if ses.Children.Count > 1:
            ses.findById("wnd[1]/tbar[0]/btn[0]").press()          # Continue: solo cierra el registro de mensajes
            _esperar(ses)
        print("ventanas tras cerrar el registro:", ses.Children.Count, flush=True)
        g = campo("GRUND")
        if g is None:                                  # el motivo está en otra pestaña del detalle: se recorren (solo cambiar de pestaña)
            for tab in ("tabpOK_GOITEM_DESTINAT.", "tabpOK_GOITEM_MATERIAL", "tabpOK_GOITEM_QUANTITIES", "tabpOK_GOITEM_PARTNER", "tabpOK_GOITEM_ACCOUNT", "tabpOK_GOITEM_PO"):
                t = _buscar(usr(), "GuiTab", tab)
                if t is None:
                    continue
                t.select()
                _esperar(ses, 20)
                g = campo("GRUND")
                print("  pestaña %s -> motivo %s" % (tab, "ENCONTRADO" if g is not None else "no"), flush=True)
                if g is not None:
                    break
            if g is None:                              # lista de pestañas realmente disponibles
                tabs = []
                def rec(o):
                    try:
                        for i in range(o.Children.Count):
                            h = o.Children.Item(i)
                            if getattr(h, "Type", "") == "GuiTab":
                                tabs.append(str(h.Id).split("/")[-1] + "=" + str(h.Text).strip())
                            rec(h)
                    except Exception:
                        pass
                rec(usr())
                print("  pestañas disponibles:", "; ".join(tabs), flush=True)
        print("campo de motivo:", str(g.Id).split("/")[-1] if g is not None else None, flush=True)
        if g is None:
            print("No encuentro el campo de motivo. Campos editables:", sap_migo._editables(usr()), flush=True)
        else:
            g.setFocus()
            ses.findById("wnd[0]").sendVKey(4)                       # F4: ayuda de entrada (solo lectura)
            _esperar(ses)
            print("\n=== AYUDA F4 DE MOTIVOS ===")
            print(_texto_ventana(ses, 1, 60), flush=True)
            if ses.Children.Count > 1:
                try:
                    ses.findById("wnd[1]/tbar[0]/btn[12]").press()   # Cancel
                except Exception:
                    ses.findById("wnd[1]").sendVKey(12)
                _esperar(ses)
    finally:
        try:
            while ses.Children.Count > 1:
                try:
                    ses.findById("wnd[%d]/tbar[0]/btn[12]" % (ses.Children.Count - 1)).press()
                except Exception:
                    break
                _esperar(ses)
            ses.findById("wnd[0]/tbar[0]/okcd").text = "/n"
            ses.findById("wnd[0]").sendVKey(0)
            _esperar(ses)
            if ses.Children.Count > 1:
                titulo = str(ses.findById("wnd[1]").Text).lower()
                print("ventana al salir:", titulo, flush=True)
                if any(x in titulo for x in ("exit", "salir", "data will be lost", "datos")):
                    ses.findById("wnd[1]/usr/btnSPOP-OPTION1").press()
                    _esperar(ses)
        except Exception as e:
            print("aviso al salir:", e, flush=True)
        print("transacción final:", ses.Info.Transaction, flush=True)
        if creada:
            sap_mb52.cerrar_sesion(ses)
            print("sesión nueva cerrada.", flush=True)
        pc.CoUninitialize()


if __name__ == "__main__":
    sys.exit(main())
