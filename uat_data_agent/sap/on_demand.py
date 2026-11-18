"""Ejecuta un plan A DEMANDA contra QS4 (SE16N, solo lectura). Lo lanza el front tras confirmación del usuario.
Reutiliza sap_gui (salvaguardas de sistema/mandante y lista blanca)."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _pywin32():
    """Usa pywin32 si está instalado; si no, la copia local de ../automatizaciones/vendor/pywin32 (mismo truco que ese proyecto)."""
    try:
        import pythoncom  # noqa: F401
        return
    except ImportError:
        pass
    v = os.path.join(os.path.dirname(ROOT), "automatizaciones", "vendor", "pywin32")
    if not os.path.isdir(v):
        raise RuntimeError("Falta pywin32. Instálalo con: pip install pywin32 (desde un PowerShell normal) y reinicia el servidor.")
    for sub in ("", "win32", os.path.join("win32", "lib")):
        pth = os.path.join(v, sub) if sub else v
        if pth not in sys.path:
            sys.path.append(pth)
    dll = os.path.join(v, "pywin32_system32")
    if os.path.isdir(dll):
        os.add_dll_directory(dll)
        os.environ["PATH"] = dll + os.pathsep + os.environ.get("PATH", "")


import queue
import threading

_Q = queue.Queue()
_T = None
_S = {'ses': None}
IDLE = 600          # a los 10 min sin consultas se cierra la sesión que abrimos (solo la nuestra)


def _cerrar():
    ses, _S['ses'] = _S['ses'], None
    if ses is not None:
        try:
            from sap_gui import close_session
            close_session(ses)
        except Exception:
            pass


def _loop(q):
    _pywin32()
    import pythoncom
    pythoncom.CoInitialize()        # un único hilo COM vive todo el servidor: así la conexión se reutiliza
    while True:
        try:
            fn, box, ev = q.get(timeout=IDLE)
        except queue.Empty:
            _cerrar()
            continue
        try:
            box['r'] = fn()
        except BaseException as e:
            box['e'] = e
        ev.set()


def com(fn, vigilar=None):
    """Ejecuta fn en el hilo COM único y devuelve su resultado (o relanza su error)."""
    global _T, _Q
    if _T is None or not _T.is_alive():
        _T = threading.Thread(target=_loop, args=(_Q,), daemon=True)
        _T.start()
    box, ev = {}, threading.Event()
    _Q.put((fn, box, ev))
    while not ev.wait(3):
        if vigilar and vigilar():
            _Q = queue.Queue()         # el hilo bloqueado se abandona: las siguientes consultas usan uno nuevo
            _T = None
            _S['ses'] = None
            raise TimeoutError('SAP lleva más de 5 minutos sin avanzar en la consulta. Cierra en SAP la ventana de esa sesión y vuelve a lanzarla.')
    if 'e' in box:
        raise box['e']
    return box['r']


def _sesion(cfg, status):
    """Reutiliza la sesión de trabajo si sigue viva; si no, engancha (comprueba QS4/200) y abre una nueva."""
    from sap_gui import attach, new_session
    ses = _S['ses']
    if ses is not None:
        try:
            if (ses.Info.SystemName, str(ses.Info.Client)) == (cfg['system_id'], str(cfg['client'])):
                return ses
        except Exception:
            pass
        _S['ses'] = None
    conn, base = attach(cfg)
    status['paso_texto'] = 'abriendo sesión nueva'
    _S['ses'] = new_session(conn, base)
    return _S['ses']


def run(items, cfg_sap, raw_dir, readers, status, fields_by_table=None, max_rows=None):
    status['avance'] = time.time()
    return com(lambda: _run(items, cfg_sap, raw_dir, readers, status, fields_by_table, max_rows), vigilar=lambda: time.time() - status.get('avance', time.time()) > 300)


def _registrar_tiempo(raw_dir, tabla, seg, filas):
    """Guarda cuánto tardó cada tabla, para poder avisar la próxima vez («suele tardar ~X»)."""
    import json
    f = os.path.join(os.path.dirname(os.path.abspath(raw_dir)), 'ledger', 'tiempos_qs4.json')
    try:
        d = json.load(open(f, encoding='utf-8')) if os.path.exists(f) else {}
        d[tabla] = {'seg': int(seg), 'filas': int(filas)}
        os.makedirs(os.path.dirname(f), exist_ok=True)
        json.dump(d, open(f, 'w', encoding='utf-8'), indent=1)
    except Exception:
        pass


TROZO_TABLA = {'STPO': 300}     # tablas que devuelven muchísimas filas por clave: trozos más pequeños
FACTOR = [1.0]                 # se reduce a la mitad en cada reintento tras un cuelgue


def _trozo(tabla):
    return max(50, int(TROZO_TABLA.get(tabla, TROZO) * FACTOR[0]))


TROZO = 1000      # claves por consulta: si hay más, se trocea en varias y se unen (antes se cortaba en 3000 y se perdían materiales)


def _unir(paths, destino):
    """Une los ficheros de las partes en uno solo (misma cabecera) y borra las partes."""
    hdr, filas = None, []
    for pth in paths:
        with open(pth, encoding='utf-8', newline='') as fh:
            lineas = fh.read().split('\n')
        if hdr is None:
            hdr = lineas[0]
        filas += [x for x in lineas[1:] if x.strip()]
    with open(destino, 'w', encoding='utf-8', newline='') as fh:
        fh.write(hdr + '\n' + '\n'.join(filas) + ('\n' if filas else ''))
    for pth in paths:
        try:
            os.remove(pth)
        except OSError:
            pass
    return destino


class _Omitida(Exception):
    pass


def _anotar_vacio(it, raw_dir, fields_by_table):
    """Una tabla leída que no devuelve filas se guarda solo con su cabecera, para que el panel la dé por leída (0 filas) y no la pida otra vez."""
    cols = (fields_by_table or {}).get(it['table']) or []
    if cols:
        os.makedirs(raw_dir, exist_ok=True)
        with open(os.path.join(raw_dir, it['name'] + '.txt'), 'w', encoding='utf-8', newline='') as fh:
            fh.write('\t'.join(cols) + '\n')


def _run(items, cfg_sap, raw_dir, readers, status, fields_by_table=None, max_rows=None):
    """status: dict mutable {'estado','paso','total','items':[{name,estado,error,filas}]}"""
    s = None
    try:
        from sap_gui import se16n_extract
        cfg = dict(cfg_sap)
        cfg['export_dir'] = os.path.abspath(raw_dir)        # los ficheros caen siempre en data/raw del proyecto
        s = _sesion(cfg, status)                            # reutiliza la sesión nuestra (sin nuevo "Permitir"); nunca toca la tuya
        status['sistema'] = f'{s.Info.SystemName}/{s.Info.Client}'
        status['paso_texto'] = ''
        keys = {}
        fallidas = set()          # tablas que han dado error en esta pasada
        import glob

        def _vals(part, it):
            """Claves de TABLA.COL: las de esta pasada si la tabla se leyó ahora; si no, las de la copia guardada en data/raw (misma planta)."""
            part = part.strip()
            if it['table'] == 'STPO' and part == 'MAST.STLNR':
                part = 'MAST.STLNR@1'          # de los componentes solo hacen falta las listas de producción (uso 1)
            if part in keys or '.' not in part:
                return keys.get(part, [])
            tabla, col = part.split('.', 1)
            solo1 = col.endswith('@1')
            col = col[:-2] if solo1 else col
            base = it['name'].split('__', 1)[1] if '__' in it['name'] else ''
            out = []
            for f in sorted(glob.glob(os.path.join(os.path.abspath(raw_dir), f"{tabla}__{base.split('_')[0]}*.txt"))):
                out += [r[col] for r in readers.read_table(f) if r.get(col) and (not solo1 or (r.get('STLAN') or '').strip() == '1')]
            return out
        for n, it in enumerate(items, 1):
            st = {'name': it['name'], 'estado': 'consultando', 'error': None, 'filas': None, 'ini': time.time()}
            status['items'].append(st)
            status['paso'] = n
            try:
                filt = {}
                for f, v in it['filters'].items():
                    if isinstance(v, str) and v.startswith('@'):
                        k = v[1:]
                        vals = list(dict.fromkeys(x for part in k.split('+') for x in _vals(part, it)))     # 'A.X+B.X' = unión de claves
                        if len(vals) > _trozo(it['table']):
                            st['aviso'] = f"{len(vals)} claves: se consulta en {-(-len(vals) // _trozo(it['table']))} partes"
                        if not vals:
                            if any(x.strip().split('.')[0] in fallidas for x in k.split('+')):
                                raise RuntimeError('la etapa anterior falló: no se puede leer esta tabla todavía')     # error, NO se anota como vacía
                            raise _Omitida('la etapa anterior no devolvió datos')
                        filt[f] = vals
                    else:
                        filt[f] = v
                tz = _trozo(it['table'])
                grande = next((f for f, v in filt.items() if isinstance(v, list) and len(v) > tz), None)
                trozos = [filt[grande][i:i + tz] for i in range(0, len(filt[grande]), tz)] if grande else [None]
                if it.get('rangos_matnr'):
                    trozos = [tuple(r) for r in it['rangos_matnr']]       # exclusiones: solo se piden los rangos que aplican
                partes = []
                for k, tr in enumerate(trozos, 1):
                    f2 = dict(filt)
                    if it.get('rangos_matnr'):
                        f2['MATNR'] = {'low': str(tr[0]), 'high': str(tr[1])}
                    elif tr is not None:
                        f2[grande] = tr
                    pre = f'parte {k} de {len(trozos)}: ' if len(trozos) > 1 else ''
                    pth = se16n_extract(s, it['table'], f2, it['name'] + (f'__parte{k}' if len(trozos) > 1 else ''), cfg, max_rows=max_rows,
                                        fields=(fields_by_table or {}).get(it['table']), progress=lambda m, st=st, pre=pre: (st.__setitem__('fase', pre + m), status.__setitem__('avance', time.time())))
                    if pth:
                        partes.append(pth)
                if len(trozos) > 1:
                    path = _unir(partes, os.path.join(os.path.abspath(raw_dir), it['name'] + '.txt')) if partes else None
                else:
                    path = partes[0] if partes else None
                if path is None:
                    st['estado'], st['filas'] = 'sin resultados', 0
                    _anotar_vacio(it, raw_dir, fields_by_table)      # leído y vacío: no se vuelve a pedir
                    continue
                rows = readers.read_table(path)
                st['estado'], st['filas'], st['fase'] = 'ok', len(rows), ''
                _registrar_tiempo(raw_dir, it['table'], time.time() - st['ini'], len(rows))
                tab = it['table']
                for r in rows:
                    for col in ('MATNR', 'EQUNR', 'INFNR', 'STLNR', 'PLNNR', 'AUFNR', 'LGNUM', 'IDNRK', 'LIFNR'):
                        if col in r and r[col]:
                            keys.setdefault(col if col != 'MATNR' else 'MATERIAL', []).append(r[col])
                            keys.setdefault(f'{tab}.{col}', []).append(r[col])
                    if tab == 'MAST' and (r.get('STLAN') or '').strip() == '1' and r.get('STLNR'):
                        keys.setdefault('MAST.STLNR@1', []).append(r['STLNR'])
            except _Omitida as e:
                st['estado'], st['filas'], st['aviso'] = 'omitida', 0, str(e)
                _anotar_vacio(it, raw_dir, fields_by_table)
            except Exception as e:
                fallidas.add(it['table'])
                st['estado'], st['error'] = 'error', f'{type(e).__name__}: {e}'
                if type(e).__name__ == 'GuardError':
                    raise
    except BaseException:
        _cerrar()                                           # ante cualquier fallo se descarta la sesión: la siguiente consulta empieza limpia
        raise
