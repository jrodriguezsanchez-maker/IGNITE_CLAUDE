"""Lista los identificadores de los campos de MIGO (acción «Transfer Posting», referencia «Other») en el sistema permitido.

NO CONTABILIZA NADA: no teclea datos, no pulsa «Post» y no guarda. Solo abre MIGO, cambia los desplegables de acción y referencia
para llegar a la pantalla de traspasos (p. ej. 344/343/311), abre el panel de detalle de posición y lee la estructura de la pantalla.
Al terminar sale de MIGO (/n). Usa una sesión libre o abre una nueva (que cierra al terminar) en la conexión permitida de conexion_local.json.

Uso:  python sap_migo_campos.py       (no usar python -I; no cortar la salida con tuberías: salvarla a un fichero)
"""
import faulthandler
import re
import sys
import time

import sap_backend
import sap_mb52

faulthandler.dump_traceback_later(150, exit=True)      # si SAP se queda colgado, vuelca dónde y termina

CONTENEDORES = ("GuiUserArea", "GuiSimpleContainer", "GuiContainerShell", "GuiTab", "GuiTabStrip", "GuiScrollContainer", "GuiCustomControl",
                "GuiSplitterContainer", "GuiMainWindow", "GuiTitlebar", "GuiStatusbar", "GuiGOS", "GuiTableControl")


def attr(o, nombre, defecto=""):
    try:
        return getattr(o, nombre)
    except Exception:
        return defecto


def recorrer(o, salida, maximo=700):
    try:
        hijos = o.Children
        n = hijos.Count
    except Exception:
        return
    for i in range(n):
        if len(salida) >= maximo:
            return
        h = hijos.Item(i)
        tipo = attr(h, "Type")
        ident = str(attr(h, "Id"))
        corto = ident.split("/usr/")[-1] if "/usr/" in ident else ident
        celda = re.search(r"\[(\d+),(\d+)\]$", ident)
        if celda and celda.group(2) != "0":
            continue                                   # tabla: solo la primera fila (las demás repiten los mismos campos)
        if tipo == "GuiComboBox":
            try:
                entradas = [(str(e.Key), str(e.Value)) for e in [h.Entries.Item(k) for k in range(h.Entries.Count)]]
            except Exception:
                entradas = []
            salida.append("Desplegable %s  opciones: %s" % (corto, "; ".join("%s=%s" % e for e in entradas) or "(no legibles)"))
        elif tipo in ("GuiTextField", "GuiCTextField"):
            if attr(h, "Changeable", True):
                salida.append("Campo   %s  [%s, long. %s%s]" % (corto, tipo, attr(h, "MaxLength"), ", obligatorio" if attr(h, "Required", False) else ""))
        elif tipo in ("GuiCheckBox", "GuiRadioButton"):
            salida.append("%s %s: %s" % ("Casilla" if tipo == "GuiCheckBox" else "Opción ", corto, str(attr(h, "Text")).strip()))
        elif tipo == "GuiButton":
            t = str(attr(h, "Text") or attr(h, "Tooltip")).strip()
            if t:
                salida.append("Botón   %s: %s" % (corto, t))
        elif tipo == "GuiTab":
            salida.append("Pestaña %s: %s" % (corto, str(attr(h, "Text")).strip()))
        elif tipo == "GuiShell":
            salida.append("Shell   %s  [%s]" % (corto, attr(h, "SubType")))
        elif tipo == "GuiTableControl":
            salida.append("Tabla   %s" % corto)
        if tipo in CONTENEDORES or attr(h, "ContainerType", False):
            recorrer(h, salida, maximo)


def encontrar(raiz, tipo, sufijo):
    try:
        hs = raiz.Children
        for i in range(hs.Count):
            h = hs.Item(i)
            if attr(h, "Type") == tipo and str(attr(h, "Id")).endswith(sufijo):
                return h
            if attr(h, "Type") in CONTENEDORES or attr(h, "ContainerType", False):
                r = encontrar(h, tipo, sufijo)
                if r is not None:
                    return r
    except Exception:
        pass
    return None


def main():
    cfg = sap_backend.leer_config()
    p = (cfg.get("sistemas_permitidos") or [None])[0]
    if not p:
        print("No hay sistemas permitidos en conexion_local.json.")
        return 2
    pythoncom = sap_mb52.pythoncom
    pythoncom.CoInitialize()
    try:
        ses, creada = sap_mb52.sesion(p["sid"], crear=True, mandante=p["mandante"], conexion=p.get("conexion"))
    except sap_mb52.SapError as e:
        print("ABORTADO:", e)
        return 1
    if str(ses.Info.SystemName).upper() != p["sid"].upper() or str(ses.Info.Client) != str(p["mandante"]):
        print("ABORTADO: la sesión no es del sistema/mandante permitidos.")
        return 1
    print("Sesión: %s/%s · sesión nueva creada por el programa: %s" % (p["sid"], p["mandante"], creada), flush=True)

    def esperar(seg=60):
        t0 = time.time()
        while ses.Busy and time.time() - t0 < seg:
            time.sleep(0.2)

    def ir(cmd):
        ses.findById("wnd[0]/tbar[0]/okcd").text = cmd
        ses.findById("wnd[0]").sendVKey(0)
        esperar()

    def listar(titulo):
        salida = []
        recorrer(ses.findById("wnd[0]/usr"), salida)
        print("\n=== %s  (%d elementos) ===" % (titulo, len(salida)))
        print("\n".join(salida), flush=True)

    def elegir(combo, texto):
        for k in range(combo.Entries.Count):
            e = combo.Entries.Item(k)
            if texto.lower() in str(e.Value).lower():
                combo.key = e.Key
                esperar(30)
                return "%s = %s" % (e.Key, e.Value)
        return None

    try:
        ir("/nMIGO")
        if ses.Children.Count > 1:
            print("Aparece una ventana emergente al abrir MIGO: %s. No pulso nada." % str(attr(ses.findById("wnd[1]"), "Text")).strip())
            return 1
        print("Pantalla:", str(ses.findById("wnd[0]").Text).strip(), "| transacción", ses.Info.Transaction, flush=True)

        usr = ses.findById("wnd[0]/usr")
        accion = encontrar(usr, "GuiComboBox", "GODYNPRO-ACTION")
        print("Desplegable de acción:", "encontrado" if accion else "NO encontrado")
        if accion:
            print("  acción elegida:", elegir(accion, "Transfer Posting"))
            ref = encontrar(ses.findById("wnd[0]/usr"), "GuiComboBox", "GODYNPRO-REFDOC")
            if ref:
                print("  referencia elegida:", elegir(ref, "Other"))
            if ses.Children.Count > 1:
                print("Ventana emergente tras cambiar la acción: no pulso nada.")
            else:
                listar("MIGO · Transfer Posting / Other (cabecera y lista de posiciones)")
                det = encontrar(ses.findById("wnd[0]/usr"), "GuiButton", "btnBUTTON_DETAIL")
                if det is not None:
                    det.press()                       # solo abre/cierra el panel de detalle (no se teclea ningún dato)
                    esperar(30)
                    if ses.Children.Count > 1:
                        print("Ventana emergente al abrir el detalle: no pulso nada.")
                    else:
                        listar("MIGO · panel de detalle de posición abierto")
    finally:
        try:
            ir("/n")                                  # sale de MIGO sin datos
        except Exception:
            pass
        print("\nSesión devuelta a la pantalla inicial: transacción", ses.Info.Transaction, flush=True)
        if creada:
            sap_mb52.cerrar_sesion(ses)
        pythoncom.CoUninitialize()
    return 0


if __name__ == "__main__":
    sys.exit(main())
