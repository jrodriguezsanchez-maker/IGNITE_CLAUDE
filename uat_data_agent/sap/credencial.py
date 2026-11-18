"""Credenciales de SAP en el Administrador de credenciales de Windows (cifradas con tu cuenta de Windows).
Nunca se guardan en ficheros del proyecto ni de OneDrive. Esta lectura solo la usa login.py, en memoria."""
from on_demand import _pywin32

TARGET = "uat_agent_QS4"


def _cred():
    _pywin32()
    import win32cred
    return win32cred


def guardar(usuario, password):
    w = _cred()
    w.CredWrite({"Type": w.CRED_TYPE_GENERIC, "TargetName": TARGET, "UserName": usuario,
                 "CredentialBlob": password, "Persist": w.CRED_PERSIST_LOCAL_MACHINE,
                 "Comment": "uat_agent: acceso a SAP QS4 (solo lo lee sap/login.py)"}, 0)


def leer():
    """(usuario, contraseña) o None si no hay nada guardado."""
    w = _cred()
    try:
        c = w.CredRead(TARGET, w.CRED_TYPE_GENERIC, 0)
    except Exception:
        return None
    blob = c["CredentialBlob"]
    if isinstance(blob, (bytes, bytearray)):
        blob = bytes(blob).decode("utf-16-le")
    return c["UserName"], blob


def marca():
    """Identifica la versión guardada de la credencial (fecha de escritura); cambia al guardar una nueva."""
    w = _cred()
    try:
        return str(w.CredRead(TARGET, w.CRED_TYPE_GENERIC, 0)["LastWritten"])
    except Exception:
        return None


def hay():
    c = leer()
    return c[0] if c else None


def borrar():
    w = _cred()
    try:
        w.CredDelete(TARGET, w.CRED_TYPE_GENERIC, 0)
    except Exception:
        pass
