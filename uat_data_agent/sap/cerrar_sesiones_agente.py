"""Cierra las sesiones de SAP GUI que abrió el agente y se quedaron colgadas o huérfanas (p. ej. tras reiniciar el servidor).

Seguridad:
- Solo la conexión cuyo nombre contiene `connection_name` de settings.yaml y solo si es QS4/200.
- NUNCA toca la primera sesión de la conexión (la tuya).
- Solo cierra sesiones que están en SE16N (las del agente); una sesión en cualquier otra transacción no se toca.
- Lo que se llama desde otro proceso desbloquea al servidor si estaba esperando una llamada a SAP que no vuelve.
Uso:  python sap/cerrar_sesiones_agente.py [--simular]"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from on_demand import _pywin32  # noqa: E402

simular = '--simular' in sys.argv
_pywin32()
import pythoncom  # noqa: E402
import win32com.client  # noqa: E402
import yaml  # noqa: E402

pythoncom.CoInitialize()
cfg = yaml.safe_load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config', 'settings.yaml'), encoding='utf-8'))['sap']
eng = win32com.client.GetObject('SAPGUI').GetScriptingEngine
cerradas = 0
for i in range(eng.Children.Count):
    conn = eng.Children(i)
    if cfg['connection_name'].lower() not in str(conn.Description).lower():
        continue
    n = conn.Children.Count
    print(f'Conexión «{conn.Description}»: {n} sesiones')
    for k in range(n - 1, 0, -1):          # de la última a la segunda; la primera (k = 0) es tuya y no se toca
        ses = conn.Children(k)
        inf = ses.Info
        if (inf.SystemName, str(inf.Client)) != (cfg['system_id'], str(cfg['client'])):
            print(f'  sesión {k}: {inf.SystemName}/{inf.Client}, no se toca')
            continue
        if inf.Transaction.upper() != 'SE16N':
            print(f'  sesión {k}: en {inf.Transaction}, no es del agente, no se toca')
            continue
        print(f"  sesión {k}: SE16N · {'(simulación)' if simular else 'se cierra'}")
        if not simular:
            try:
                ses.findById('wnd[0]/tbar[0]/okcd').text = '/i'
                ses.findById('wnd[0]').sendVKey(0)
                cerradas += 1
            except Exception as e:
                print('    no pude cerrarla:', type(e).__name__, e)
print('Cerradas:', cerradas)
