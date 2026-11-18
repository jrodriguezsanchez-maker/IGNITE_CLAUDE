"""Abre la conexión de QS4 en SAP Logon y entra con la credencial guardada (credencial.py).

Salvaguardas:
- Solo la entrada de SAP Logon cuyo nombre contiene `connection_name`; nunca otra.
- UN solo intento de login. Si falla (contraseña caducada/incorrecta, aviso de sesión múltiple...), se para sin reintentar
  para no bloquear el usuario, y se dice qué hacer.
- Tras entrar se comprueba sistema y mandante (QS4/200); si no coincide, se cierra esa conexión y se para.
- La contraseña solo vive en memoria durante el login; no se imprime ni se escribe en logs."""
import os
import subprocess
import time

from on_demand import _pywin32

SAPLOGON = [r"C:\Program Files (x86)\SAP\FrontEnd\SAPgui\saplogon.exe", r"C:\Program Files\SAP\FrontEnd\SAPgui\saplogon.exe"]


class LoginError(RuntimeError):
    pass


# Freno anti-bloqueo: tras un login fallido no se vuelve a intentar con la MISMA credencial guardada.
# La marca vive en %LOCALAPPDATA% (fuera de OneDrive y del repo) y se libera sola al guardar una credencial nueva.
FRENO = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "uat_agent", "login_fallido.txt")


def _frenado(marca):
    try:
        return open(FRENO, encoding="utf-8").read().strip() == str(marca)
    except OSError:
        return False


def _poner_freno(marca):
    os.makedirs(os.path.dirname(FRENO), exist_ok=True)
    open(FRENO, "w", encoding="utf-8").write(str(marca))


def _engine(arrancar=True, espera=40):
    import win32com.client
    t0 = time.time()
    lanzado = False
    while True:
        try:
            return win32com.client.GetObject("SAPGUI").GetScriptingEngine
        except Exception:
            if not arrancar:
                return None
            if not lanzado:
                exe = next((p for p in SAPLOGON if os.path.exists(p)), None)
                if not exe:
                    raise LoginError("No encuentro saplogon.exe. Abre SAP Logon a mano y vuelve a pulsar Conectar.")
                subprocess.Popen([exe])
                lanzado = True
            if time.time() - t0 > espera:
                raise LoginError("SAP Logon no arrancó a tiempo (o el scripting está desactivado en SAP GUI).")
            time.sleep(1.5)


def _conexion(engine, nombre):
    for i in range(engine.Children.Count):
        c = engine.Children(i)
        if nombre.lower() in str(c.Description).lower():
            return c
    return None


def _txt(ses, idc):
    try:
        return ses.findById(idc)
    except Exception:
        return None


def conectar(cfg, status=None):
    """Devuelve 'ya conectado' o 'conectado'. Lanza LoginError con un mensaje accionable."""
    _pywin32()
    import pythoncom
    pythoncom.CoInitialize()
    import credencial
    st = status if status is not None else {}
    nombre = cfg["connection_name"]

    st["texto"] = "buscando SAP Logon"
    engine = _engine()
    conn = _conexion(engine, nombre)
    if conn is not None and conn.Children.Count:
        ses = conn.Children(0)
        if _txt(ses, "wnd[0]/usr/pwdRSYST-BCODE") is None:                 # ya hay sesión dentro
            info = ses.Info
            if (info.SystemName, str(info.Client)) != (cfg["system_id"], str(cfg["client"])):
                raise LoginError(f"La conexión abierta es {info.SystemName}/{info.Client}, no {cfg['system_id']}/{cfg['client']}. No toco nada.")
            return "ya conectado"

    cred = credencial.leer()
    if not cred:
        raise LoginError("No hay credencial guardada. Haz doble clic en guardar_credencial_sap.bat (una sola vez) y vuelve a pulsar Conectar.")
    usuario, password = cred
    marca = credencial.marca()
    if _frenado(marca):
        raise LoginError("El último intento con esta credencial falló y NO reintento para no bloquear tu usuario. "
                         "Comprueba la contraseña en SAP y vuelve a guardarla con guardar_credencial_sap.bat.")

    if conn is None:
        st["texto"] = f"abriendo «{nombre}» en SAP Logon"
        try:
            conn = engine.OpenConnection(nombre, True)
        except Exception as e:
            raise LoginError(f"SAP Logon no tiene (o no pudo abrir) la entrada «{nombre}»: {e}")
    ses = conn.Children(0)

    t0 = time.time()
    while _txt(ses, "wnd[0]/usr/pwdRSYST-BCODE") is None:
        if time.time() - t0 > 30:
            raise LoginError("No aparece la pantalla de login de SAP (¿pide VPN o SSO?). Entra a mano.")
        time.sleep(0.5)

    st["texto"] = "entrando (un solo intento)"
    cl = _txt(ses, "wnd[0]/usr/txtRSYST-MANDT")
    if cl is not None:
        cl.text = str(cfg["client"])
    ses.findById("wnd[0]/usr/txtRSYST-BNAME").text = usuario
    ses.findById("wnd[0]/usr/pwdRSYST-BCODE").text = password
    password = None
    lg = _txt(ses, "wnd[0]/usr/txtRSYST-LANGU")
    if lg is not None:
        lg.text = "EN"
    ses.findById("wnd[0]").sendVKey(0)
    _poner_freno(marca)                  # se levanta solo si el login entra bien (más abajo)

    t0 = time.time()
    while True:
        time.sleep(0.7)
        try:
            if ses.Info.User:
                break
        except Exception:
            pass
        if _txt(ses, "wnd[1]") is not None:
            # aviso de sesión múltiple, contraseña caducada, etc.: no se decide por el usuario
            try:
                msg = ses.findById("wnd[1]").text
            except Exception:
                msg = "ventana emergente"
            raise LoginError(f"SAP muestra un aviso al entrar ({msg}). Resuélvelo en la ventana de SAP; no reintento.")
        if _txt(ses, "wnd[0]/usr/pwdRSYST-BCODE") is not None and time.time() - t0 > 3:
            try:
                msg = ses.findById("wnd[0]/sbar").text
            except Exception:
                msg = ""
            raise LoginError(f"SAP rechazó el login ({msg or 'sin mensaje'}). Si cambió la contraseña, ejecuta guardar_credencial_sap.bat. No reintento.")
        if time.time() - t0 > 40:
            raise LoginError("SAP no terminó de entrar en 40 s. Mira la ventana de SAP.")

    try:
        os.remove(FRENO)                 # entró bien: se quita el freno
    except OSError:
        pass
    info = ses.Info
    if (info.SystemName, str(info.Client)) != (cfg["system_id"], str(cfg["client"])):
        try:
            conn.CloseConnection()
        except Exception:
            pass
        raise LoginError(f"Entró en {info.SystemName}/{info.Client}, no en {cfg['system_id']}/{cfg['client']}. Conexión cerrada.")
    return "conectado"
