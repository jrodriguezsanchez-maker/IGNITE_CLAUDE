"""Servidor local del front de automatizaciones.

Solo escucha en 127.0.0.1, sin dependencias externas. Los datos de prueba y los
resultados se guardan en data/ y results/ de cada flujo (ignoradas por git).
Uso:  python server.py   ->  http://127.0.0.1:8765
"""
import json
import re
import sys
import threading
import time
import unicodedata
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote

import engine
import sit_engine
import chequeo
import sit_import
import sto_engine
import sto_import
from xlsx_reader import read_xlsx

ROOT = Path(__file__).resolve().parent.parent  # .../automatizaciones
STATIC = Path(__file__).resolve().parent / "static"
HOST = "127.0.0.1"
PORT = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 8765
MAX_UPLOAD = 20 * 1024 * 1024
SAFE = re.compile(r"^[A-Za-z0-9_\-]+$")
SAFE_FILE = re.compile(r"^[A-Za-z0-9_\-. ()]+\.xlsx$")
RUN_ID = re.compile(r"^\d{8}-\d{6}-[a-f0-9]{4}$")
LOCK = threading.Lock()


def flow_dir(stream, flow):
    if not (SAFE.match(stream) and SAFE.match(flow)):
        raise ValueError("Nombre no válido")
    d = (ROOT / stream / "flujos" / flow).resolve()
    if ROOT not in d.parents or not (d / "flow.json").exists():
        raise FileNotFoundError("Flujo no encontrado")
    return d


def tree():
    out = []
    for s in sorted(p for p in ROOT.iterdir() if p.is_dir() and (p / "flujos").is_dir()):
        flujos = []
        for f in sorted((s / "flujos").iterdir()):
            if f.name.startswith("_") or not (f / "flow.json").exists():
                continue
            meta = json.loads((f / "flow.json").read_text(encoding="utf-8"))
            runs = list((f / "results").glob("*.json"))
            flujos.append({"id": f.name, "nombre": meta.get("nombre", f.name), "descripcion": meta.get("descripcion", ""),
                           "reglas": meta.get("reglas", {}), "tipo": meta.get("tipo", "excel_filas"),
                           "config": {k: meta[k] for k in ("filtro", "columnas_por_defecto", "filtros_columnas", "etiquetas", "modo") if k in meta}, "ficheros": len(list((f / "data").glob("*.xlsx"))), "ejecuciones": len(runs)})
        out.append({"id": s.name, "flujos": flujos})
    return out


def list_files(d):
    return sorted(({"nombre": p.name, "bytes": p.stat().st_size, "fecha": time.strftime("%Y-%m-%d %H:%M", time.localtime(p.stat().st_mtime))}
                   for p in (d / "data").glob("*.xlsx")), key=lambda x: x["fecha"], reverse=True)


def list_runs(d=None):
    items = []
    for s in tree():
        for f in s["flujos"]:
            for p in (ROOT / s["id"] / "flujos" / f["id"] / "results").glob("*.json"):
                try:
                    r = json.loads(p.read_text(encoding="utf-8"))
                except Exception:
                    continue
                items.append({"id": r["id"], "stream": s["id"], "flujo": f["id"], "fichero": r["fichero"], "inicio": r["inicio"],
                              "estado": r["estado"], "simulado": r["simulado"], "resumen": r.get("resumen", {})})
    return sorted(items, key=lambda x: x["id"], reverse=True)


def execute(stream, flow, filename, run_id):
    d = flow_dir(stream, flow)
    path = d / "results" / (run_id + ".json")
    log_lines = []
    run = {"id": run_id, "stream": stream, "flujo": flow, "fichero": filename, "inicio": time.strftime("%Y-%m-%d %H:%M:%S"),
           "simulado": True, "estado": "EN_CURSO", "resumen": {}, "filas": [], "log": log_lines}

    def log(nivel, msg):
        log_lines.append({"t": time.strftime("%H:%M:%S"), "nivel": nivel, "msg": msg})

    def save():
        path.write_text(json.dumps(run, ensure_ascii=False, indent=1), encoding="utf-8")

    save()
    try:
        log("INFO", "Modo SIMULADO: no se conecta a SAP.")
        headers, rows = read_xlsx(d / "data" / filename)
        log("INFO", "Leídas %d filas de %s" % (len(rows), filename))
        run["filas"], run["resumen"] = engine.run(headers, rows, engine.crear_backend(), log)
        run["estado"] = "ERROR" if run["resumen"].get("error") else "FINALIZADA"
    except Exception as e:
        log("ERROR", "Fallo en la ejecución: %s" % e)
        run["estado"] = "ERROR"
    run["fin"] = time.strftime("%Y-%m-%d %H:%M:%S")
    save()


def catalog_path(d):
    return d / "data" / "catalogo_escenarios.json"


def load_catalog(d):
    p = catalog_path(d)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def load_req(d):
    nombre = json.loads((d / "flow.json").read_text(encoding="utf-8")).get("requisitos", "requisitos_movimiento.json")
    return json.loads((d / nombre).read_text(encoding="utf-8"))


def defaults_path(d):
    return d / "data" / "valores_centro.json"


def load_motivos(d):
    """Motivos de movimiento válidos por clase de movimiento (datos de configuración del cliente: solo en data/, fuera de git)."""
    p = d / "data" / "motivos_movimiento.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def load_defaults(d):
    p = defaults_path(d)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


VALOR = re.compile(r"^[A-Za-z0-9_\-\. /,;]{0,60}$")


MAX_DOCS_REAL = 25      # una sola confirmación por lanzamiento (no una por documento)


def en_sap(fn, *args):
    """Con el modo «SAP real», las operaciones con SAP van al hilo único (un solo enganche, sin avisos repetidos); en simulado se ejecutan sin más."""
    return fn(*args)     # (se probó un hilo único para SAP y tumbaba el proceso con un fallo de COM: se ejecuta directamente, como antes)


_PREPARADOS = {}          # clave -> {"lote": ..., "ts": ...}: lo que «preparar» enseñó al usuario (para no volver a leer SAP al contabilizar)
PREPARADO_TTL = 600       # 10 minutos


def preparar_real(d, claves, cantidad_global, lotes_ya_elegidos=None):
    """Datos exactos de cada documento que se contabilizaría y su huella. Lee SAP (MB52, solo lectura) únicamente para elegir el lote si no está fijado."""
    import sap_backend
    import sap_migo
    cfg = sap_backend.leer_config()
    if cfg.get("modo") != "sap":
        raise ValueError("La contabilización real exige el modo «Chequeo con SAP real» (selector de la cabecera).")
    req, defaults = load_req(d), load_defaults(d)
    cat = {e["clave"]: e for e in load_catalog(d)}
    out, be = [], None
    try:
        for c in claves:
            e = cat.get(c)
            if e is None:
                raise ValueError("Escenario desconocido.")
            fila = {"clave": c, "jira_id": e["jira_id"], "id_jira_unidad": e["id_jira_unidad"], "escenario": e["escenario"], "mov": e["mov"],
                    "ok": False, "problema": "", "material": "", "centro": "", "almacen": "", "almacen_destino": "", "lote": "", "cantidad": "", "motivo": "", "huella": ""}
            vals, fuentes, faltan, rq = sit_import.resolver(e, e["mov"], req, defaults, cantidad_global)
            if e["mov"] not in sap_migo.MOVIMIENTOS_PERMITIDOS:
                fila["problema"] = "El movimiento %s aún no se puede contabilizar de verdad (solo %s)." % (e["mov"] or "—", ", ".join(sorted(sap_migo.MOVIMIENTOS_PERMITIDOS)))
            elif faltan:
                fila["problema"] = "Faltan datos: " + ", ".join(req["campos"][f] for f in faltan)
            elif len(vals["material"]) != 1:
                fila["problema"] = "Varios materiales en un mismo escenario: aún no soportado para contabilizar."
            else:
                mat, centro, alm = vals["material"][0], vals["centro"], vals["alm_origen"]
                try:
                    cant = float(str(vals["cantidad"]).replace(",", "."))
                except ValueError:
                    cant = 0
                if not 0 < cant <= sap_migo.MAX_CANTIDAD:
                    fila["problema"] = "Cantidad no válida."
                else:
                    lote = (vals.get("lote") or "").strip()
                    if lotes_ya_elegidos is not None and c in lotes_ya_elegidos:
                        lote, cubierto = lotes_ya_elegidos[c], True      # lo vio el usuario al preparar; el Check de MIGO vuelve a validar el stock
                    elif lote:
                        cubierto = True                                  # lote fijado por el usuario: sin leer SAP; MIGO valida el stock al contabilizar
                    else:
                        if be is None:
                            be = engine.crear_backend("chequeo")         # SAP real, solo lectura
                        st = be.stock_origen(mat, centro, alm, False)
                        lineas = sorted([l for l in st["lineas"] if l["qty"] > 0], key=engine._orden)
                        cubre = [l for l in lineas if l["qty"] >= cant] if st["lotes_activo"] else lineas
                        lote = cubre[0]["lote"] if cubre and st["lotes_activo"] else ""
                        cubierto = bool(cubre) and sum(l["qty"] for l in cubre) >= cant
                    if not cubierto:
                        fila["problema"] = "Ningún lote libre cubre %s por sí solo (repartir entre varios lotes aún no está soportado)." % vals["cantidad"]
                    else:
                        dest = vals.get("alm_destino", "") if e["mov"] in sap_migo.CON_DESTINO else ""
                        fila.update({"ok": True, "material": mat, "centro": centro, "almacen": alm, "almacen_destino": dest, "lote": lote,
                                     "cantidad": sap_migo.normalizar_cantidad(vals["cantidad"]), "motivo": vals.get("motivo", ""), "um": ""})
                        fila["huella"] = sap_migo.huella(e["mov"], mat, centro, alm, lote, fila["cantidad"], fila["motivo"], dest)
            out.append(fila)
    finally:
        if be is not None and hasattr(be, "cerrar"):
            be.cerrar()
    return out


def ejecuciones(d):
    p = d / "data" / "ejecuciones.json"          # data/ está fuera de git
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def registrar_ejecucion(d, clave, estado, documento, run_id):
    """Último resultado real de cada escenario: OK (contabilizado y stock verificado), REVISAR (stock distinto del esperado) o KO (error)."""
    if not clave:
        return
    e = ejecuciones(d)
    e[clave] = {"estado": estado, "documento": documento or "", "run": run_id, "fecha": time.strftime("%Y-%m-%d %H:%M:%S")}
    p = d / "data" / "ejecuciones.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(e, ensure_ascii=False, indent=1), encoding="utf-8")


def execute_real(stream, flow, items, run_id):
    """Contabiliza de verdad (MIGO) los documentos ya confirmados por el usuario. Uno a uno, con verificación de stock antes y después."""
    import sap_backend
    import sap_migo
    import sap_mb52
    d = flow_dir(stream, flow)
    path = d / "results" / (run_id + ".json")
    log_lines = []
    run = {"id": run_id, "stream": stream, "flujo": flow, "tipo": "sit", "modo": "migo", "real": True, "simulado": False,
           "fichero": "%d documento(s) REALES en SAP" % len(items), "inicio": time.strftime("%Y-%m-%d %H:%M:%S"), "estado": "EN_CURSO",
           "resumen": {}, "log": log_lines, "escenarios": [], "mm": [], "fi": [], "co": [], "ml": [], "pasos": []}

    def log(nivel, msg):
        log_lines.append({"t": time.strftime("%H:%M:%S"), "nivel": nivel, "msg": msg})

    def save():
        path.write_text(json.dumps(run, ensure_ascii=False, indent=1), encoding="utf-8")

    save()
    pc = sap_mb52.pythoncom
    ses = creada = None
    resumen = {"CONTABILIZADO": 0, "ERROR": 0}
    try:
        pc.CoInitialize()
        cfg = sap_backend.leer_config()
        p = (cfg.get("sistemas_permitidos") or [None])[0]
        ses, creada = sap_mb52.sesion(p["sid"], crear=True, mandante=p["mandante"], conexion=p.get("conexion"))
        if str(ses.Info.SystemName).upper() != p["sid"].upper() or str(ses.Info.Client) != str(p["mandante"]):
            raise ValueError("La sesión no es del sistema/mandante permitidos.")
        log("INFO", "CONTABILIZACIÓN REAL en %s/%s (sesión nueva: %s)" % (p["sid"], p["mandante"], creada))
        for it in items:
            base = {"jira_id": it["jira_id"], "id_jira_unidad": it["id_jira_unidad"], "escenario": it["escenario"], "mov": it["mov"]}
            esc = {**base, "unidad": "", "estado": "", "detalle": ""}
            fila = {**base, "material": it["material"], "centro": it["centro"], "almacen": it["almacen"], "almacen_destino": it.get("almacen_destino", ""),
                    "lote": it["lote"], "motivo": it["motivo"],
                    "pedida": it["cantidad"], "movida": 0, "estado": "", "documentos": "", "detalle": "", "stock_antes": "", "stock_despues": ""}
            try:
                dest = it.get("almacen_destino", "")
                antes = sap_migo.stock_lote(ses, it["material"], it["centro"], it["almacen"], it["lote"])
                antes_d = sap_migo.stock_lote(ses, it["material"], it["centro"], dest, it["lote"]) if dest else None
                log("INFO", "%s stock antes: %s%s" % (it["jira_id"], antes, (" · destino " + str(antes_d)) if dest else ""))
                res = sap_migo.traspaso(ses, mov=it["mov"], material=it["material"], centro=it["centro"], almacen=it["almacen"], lote=it["lote"],
                                        cantidad=it["cantidad"], um="", modo="contabilizar", clave=it["huella"], motivo=it["motivo"],
                                        almacen_destino=dest)
                despues = sap_migo.stock_lote(ses, it["material"], it["centro"], it["almacen"], it["lote"])
                despues_d = sap_migo.stock_lote(ses, it["material"], it["centro"], dest, it["lote"]) if dest else None
                log("INFO", "%s documento %s · stock después: %s%s" % (it["jira_id"], res["documento"] or "(no leído)", despues, (" · destino " + str(despues_d)) if dest else ""))
                cant = float(str(it["cantidad"]).replace(",", "."))
                esperado = (it["mov"] == "344" and abs((antes["libre"] - despues["libre"]) - cant) < 1e-6 and abs((despues["bloqueado"] - antes["bloqueado"]) - cant) < 1e-6) \
                    or (it["mov"] == "343" and abs((despues["libre"] - antes["libre"]) - cant) < 1e-6 and abs((antes["bloqueado"] - despues["bloqueado"]) - cant) < 1e-6) \
                    or (it["mov"] == "311" and dest and abs((antes["libre"] - despues["libre"]) - cant) < 1e-6 and abs((despues_d["libre"] - antes_d["libre"]) - cant) < 1e-6)
                fila.update({"movida": cant, "estado": "CONTABILIZADO" if esperado else "REVISAR", "documentos": res["documento"], "detalle": res["mensaje"],
                             "stock_antes": "origen: libre %s · bloqueado %s" % (antes["libre"], antes["bloqueado"]) + ((" | destino: libre %s" % antes_d["libre"]) if dest else ""),
                             "stock_despues": "origen: libre %s · bloqueado %s" % (despues["libre"], despues["bloqueado"]) + ((" | destino: libre %s" % despues_d["libre"]) if dest else "")})
                esc.update({"estado": fila["estado"], "detalle": ("Documento %s. " % res["documento"]) + res["mensaje"] +
                            ("" if esperado else " · OJO: el stock no cambió como se esperaba")})
                resumen["CONTABILIZADO"] += 1
                if res["documento"]:                   # documentos contables (FI, CO, ML) con MIGO Display + «FI Documents»; si falla, no invalida la contabilización
                    try:
                        import sap_docs
                        cont = sap_docs.leer_documento(ses, res["documento"], time.strftime("%Y"))
                        for c in cont["contables"]:
                            clave_doc = {"FI": "doc_fi", "CO": "doc_co", "ML": "doc_ml"}.get(c["categoria"])
                            if clave_doc:
                                run[c["categoria"].lower()].append({**base, "doc_material": res["documento"], clave_doc: c["documento"], "sociedad": c["sociedad"], "tipo": c["tipo"]})
                        if cont.get("sin_contabilidad"):
                            txt = "Este movimiento no genera documentos contables (FI, CO ni ML)."
                        else:
                            txt = "Contabilidad: " + (", ".join("%s %s" % (c["categoria"], c["documento"]) for c in cont["contables"]) or "; ".join(cont["avisos"]))
                        log("INFO", "%s %s" % (it["jira_id"], txt))
                        fila["detalle"] = (fila["detalle"] + " · " + txt)[:600]
                    except Exception as ex2:
                        log("AVISO", "%s: no se pudieron leer los documentos contables: %s" % (it["jira_id"], str(ex2)[:300]))
            except Exception as ex:                     # un documento fallido no continúa con los demás sin que el usuario lo vea
                log("ERROR", "%s: %s" % (it["jira_id"], ex))
                fila.update({"estado": "ERROR", "detalle": str(ex)[:400]})
                esc.update({"estado": "ERROR", "detalle": str(ex)[:400]})
                resumen["ERROR"] += 1
            registrar_ejecucion(d, it.get("clave"), {"CONTABILIZADO": "OK", "ERROR": "KO"}.get(fila["estado"], "REVISAR"), fila["documentos"], run_id)
            run["mm"].append(fila)
            run["escenarios"].append(esc)
            run["resumen"] = resumen
            save()
        run["estado"] = "FINALIZADA"
    except Exception as ex:
        log("ERROR", "Fallo en la contabilización: %s" % ex)
        run["estado"] = "ERROR"
    finally:
        try:
            if ses is not None and creada:
                sap_mb52.cerrar_sesion(ses)
            pc.CoUninitialize()
        except Exception:
            pass
    run["resumen"] = resumen
    run["fin"] = time.strftime("%Y-%m-%d %H:%M:%S")
    save()


def execute_sit(stream, flow, claves, run_id, cantidad, propuestas=None):
    d = flow_dir(stream, flow)
    meta = json.loads((d / "flow.json").read_text(encoding="utf-8"))
    path = d / "results" / (run_id + ".json")
    log_lines = []
    run = {"id": run_id, "stream": stream, "flujo": flow, "tipo": "sit", "modo": meta.get("modo", "migo"), "fichero": "%d escenario(s) SIT" % len(claves),
           "inicio": time.strftime("%Y-%m-%d %H:%M:%S"), "simulado": True, "estado": "EN_CURSO", "resumen": {}, "log": log_lines}

    def log(nivel, msg):
        log_lines.append({"t": time.strftime("%H:%M:%S"), "nivel": nivel, "msg": msg})

    def save():
        path.write_text(json.dumps(run, ensure_ascii=False, indent=1), encoding="utf-8")

    save()
    try:
        log("INFO", "Modo SIMULADO: no se conecta a SAP. IDoc/EDI fuera de alcance.")
        sel = [e for e in load_catalog(d) if e["clave"] in set(claves)]
        log("INFO", "Cantidad por defecto: %s" % cantidad)
        motor = sto_engine if meta.get("modo") == "sto" else sit_engine
        out, run["resumen"] = motor.ejecutar(sel, engine.crear_backend(), log, cantidad, load_req(d), load_defaults(d), propuestas)
        run.update(out)
        run["estado"] = "FINALIZADA"
    except Exception as e:
        log("ERROR", "Fallo en la ejecución: %s" % e)
        run["estado"] = "ERROR"
    run["fin"] = time.strftime("%Y-%m-%d %H:%M:%S")
    save()


def _plain(s):
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


STOP = {"el", "la", "los", "las", "de", "del", "un", "una", "con", "para", "por", "que", "en", "y", "o", "a", "al", "lanza", "lanzar",
        "ejecuta", "ejecutar", "quiero", "las", "pruebas", "prueba", "escenario", "escenarios", "fichero", "excel", "todos", "todas", "ultimo", "ultima"}
SINONIMOS = {"bloquear": "block", "bloqueo": "block", "bloqueado": "block", "desbloquear": "unblock", "desbloqueo": "unblock",
             "traslado": "transfer", "traslados": "transfer", "transferencia": "transfer", "entrada": "receipt", "recepcion": "receipt",
             "salida": "issue", "desguace": "scrap", "chatarra": "scrap", "calidad": "quality", "inventario": "inventory",
             "lote": "batch", "lotes": "batch", "produccion": "production", "pedido": "purchase", "bloqueos": "block"}


def interpret(text, stream, flow):
    """Propone fichero y escenarios del flujo seleccionado con reglas locales. No lanza nada ni envía nada fuera."""
    d = flow_dir(stream, flow)
    t = _plain(text)
    words = [w for w in re.findall(r"[a-z0-9_\-\.]+", t) if w not in STOP and len(w) >= 2]
    terms = [{w, SINONIMOS.get(w, w)} for w in words]
    files = list_files(d)
    fichero = next((f["nombre"] for f in files if any(_plain(f["nombre"]).find(w) >= 0 for w in words if len(w) > 3)), None)
    if not fichero and re.search(r"ultim", t) and files:
        fichero = files[0]["nombre"]
    out = {"ok": True, "fichero": fichero, "claves": [], "ejemplos": [], "mensaje": ""}
    meta = json.loads((d / "flow.json").read_text(encoding="utf-8"))
    if meta.get("tipo") == "sit_jira":
        cat = load_catalog(d)
        scored = []
        for e in cat:
            blob = _plain(" ".join([e["jira_id"], e["id_jira_unidad"], e["escenario"], e["descripcion_paso1"], e["unidad"], e["l3"],
                                    " ".join(e["datos"]["materiales"]), " ".join(e["datos"]["plantas"]), " ".join(e["movs_candidatos"]),
                                    e["fila1"].get("Data", "")]))
            sc = sum(1 for alts in terms if any(a in blob for a in alts))
            if sc:
                scored.append((sc, e))
        if scored:
            top = max(sc for sc, _ in scored)
            sel = [e for sc, e in scored if sc == top][:200]
            out["claves"] = [e["clave"] for e in sel]
            out["ejemplos"] = ["%s · %s · %s" % (e["jira_id"], e["unidad"], e["escenario"][:70].replace("\n", " ")) for e in sel[:5]]
            out["mensaje"] = "%d escenario(s) coinciden con %d de %d palabras." % (len(sel), top, len(terms))
        elif words:
            out["mensaje"] = "Ningún escenario coincide. Prueba con un ID de Jira, una unidad (Belgium…) o un tipo de operación (traslado, bloqueo…)."
    if not fichero and not out["claves"] and not out["mensaje"]:
        out["ok"], out["mensaje"] = False, "No he entendido qué buscas."
    return out


class Handler(BaseHTTPRequestHandler):
    server_version = "AutoFront/1.0"

    def log_message(self, fmt, *a):  # no registrar rutas/consultas en consola
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'")
        self.end_headers()
        self.wfile.write(body)

    def _guard(self):
        # Defensa frente a DNS rebinding y peticiones de otros orígenes
        if self.headers.get("Host", "") not in (f"{HOST}:{PORT}", f"localhost:{PORT}"):
            self._send(403, {"error": "Host no permitido"})
            return False
        origin = self.headers.get("Origin")
        if origin and origin not in (f"http://{HOST}:{PORT}", f"http://localhost:{PORT}"):
            self._send(403, {"error": "Origen no permitido"})
            return False
        return True

    def _handle(self, fn):
        try:
            fn()
        except (ValueError, FileNotFoundError) as e:
            self._send(400, {"error": str(e)})
        except Exception:
            self._send(500, {"error": "Error interno"})

    def do_GET(self):
        if self._guard():
            self._handle(self._get)

    def do_POST(self):
        if self._guard():
            self._handle(self._post)

    def _get(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        if u.path == "/":
            return self._send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
        if u.path == "/app.js":
            return self._send(200, (STATIC / "app.js").read_bytes(), "text/javascript; charset=utf-8")
        if u.path == "/api/tree":
            return self._send(200, tree())
        if u.path == "/api/files":
            return self._send(200, list_files(flow_dir(q.get("stream", ""), q.get("flow", ""))))
        if u.path == "/api/preview":
            d = flow_dir(q.get("stream", ""), q.get("flow", ""))
            name = q.get("file", "")
            if not SAFE_FILE.match(name) or not (d / "data" / name).exists():
                raise FileNotFoundError("Fichero no encontrado")
            headers, rows = read_xlsx(d / "data" / name)
            mapping, missing = engine.map_columns(headers)
            return self._send(200, {"cabeceras": headers, "filas": rows[:50], "total": len(rows), "faltan": missing})
        if u.path == "/api/sap/estado":
            import sap_backend
            return self._send(200, sap_backend.estado())
        if u.path == "/api/modo":
            import sap_backend
            cfg = sap_backend.leer_config()
            return self._send(200, {"modo": cfg.get("modo", "simulado"), "sistemas": ["%s/%s" % (p["sid"], p["mandante"]) for p in cfg.get("sistemas_permitidos", [])]})
        if u.path == "/api/sit/catalog":
            d = flow_dir(q.get("stream", ""), q.get("flow", ""))
            mp = d / "data" / "catalogo_meta.json"
            return self._send(200, {"meta": json.loads(mp.read_text(encoding="utf-8")) if mp.exists() else {}, "escenarios": load_catalog(d),
                                    "requisitos": load_req(d), "defaults": load_defaults(d), "motivos": load_motivos(d),
                                    "cantidad_por_defecto": json.loads((d / "flow.json").read_text(encoding="utf-8")).get("cantidad_por_defecto", 1),
                                    "ejecuciones": ejecuciones(d)})
        if u.path == "/api/sit/ejecuciones":
            return self._send(200, ejecuciones(flow_dir(q.get("stream", ""), q.get("flow", ""))))
        if u.path == "/api/runs":
            return self._send(200, list_runs())
        m = re.match(r"^/api/runs/([^/]+)$", u.path)
        if m:
            rid = unquote(m.group(1))
            if not RUN_ID.match(rid):
                raise ValueError("Id no válido")
            for r in list_runs():
                if r["id"] == rid:
                    p = ROOT / r["stream"] / "flujos" / r["flujo"] / "results" / (rid + ".json")
                    return self._send(200, p.read_bytes())
            raise FileNotFoundError("Ejecución no encontrada")
        self._send(404, {"error": "No encontrado"})

    def _post(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        n = int(self.headers.get("Content-Length", 0))
        if n > MAX_UPLOAD:
            raise ValueError("Fichero demasiado grande (máx. 20 MB)")
        body = self.rfile.read(n)
        if u.path == "/api/upload":
            d = flow_dir(q.get("stream", ""), q.get("flow", ""))
            name = unquote(q.get("name", ""))
            if not SAFE_FILE.match(name):
                raise ValueError("Nombre no válido: solo .xlsx con letras, números, espacios, - _ .")
            if body[:2] != b"PK":
                raise ValueError("No parece un .xlsx válido")
            (d / "data" / name).write_bytes(body)
            return self._send(200, {"ok": True, "nombre": name})
        data = json.loads(body or b"{}")
        if u.path == "/api/run":
            d = flow_dir(data.get("stream", ""), data.get("flow", ""))
            name = data.get("file", "")
            if not SAFE_FILE.match(name) or not (d / "data" / name).exists():
                raise FileNotFoundError("Fichero no encontrado")
            with LOCK:
                rid = time.strftime("%Y%m%d-%H%M%S-") + "%04x" % (time.time_ns() & 0xFFFF)
            threading.Thread(target=execute, args=(data["stream"], data["flow"], name, rid), daemon=True).start()
            return self._send(200, {"ok": True, "id": rid})
        if u.path == "/api/sit/import":
            d = flow_dir(data.get("stream", ""), data.get("flow", ""))
            name = data.get("file", "")
            if not SAFE_FILE.match(name) or not (d / "data" / name).exists():
                raise FileNotFoundError("Fichero no encontrado")
            fmeta = json.loads((d / "flow.json").read_text(encoding="utf-8"))
            filtro = fmeta.get("filtro")
            if fmeta.get("modo") == "sto":
                nuevo, stats = sto_import.importar_sto(d / "data" / name, filtro)
            else:
                nuevo, stats = sit_import.importar(d / "data" / name, d / "reglas_movimiento.json", filtro)
            stats.update({"fichero": name, "fecha": time.strftime("%Y-%m-%d %H:%M")})
            (d / "data" / "catalogo_meta.json").write_text(json.dumps(stats, ensure_ascii=False), encoding="utf-8")
            previo = {e["clave"]: e for e in load_catalog(d)}
            for e in nuevo:  # conserva confirmaciones anteriores
                o = previo.get(e["clave"])
                if o and o.get("confirmado"):
                    e["mov"], e["confirmado"] = o["mov"], True
                if o and o.get("aportados"):
                    e["aportados"] = o["aportados"]
            catalog_path(d).write_text(json.dumps(nuevo, ensure_ascii=False), encoding="utf-8")
            return self._send(200, {"ok": True, "escenarios": len(nuevo), "meta": stats})
        if u.path == "/api/sit/confirm":
            d = flow_dir(data.get("stream", ""), data.get("flow", ""))
            cat = load_catalog(d)
            idx = {e["clave"]: e for e in cat}
            for it in data.get("items", []):
                mov = str(it.get("mov", "")).strip().upper()
                if it.get("clave") in idx and re.match(r"^[0-9A-Z]{3,4}$", mov):
                    idx[it["clave"]]["mov"], idx[it["clave"]]["confirmado"] = mov, True
            catalog_path(d).write_text(json.dumps(cat, ensure_ascii=False), encoding="utf-8")
            return self._send(200, {"ok": True, "confirmados": sum(1 for e in cat if e["confirmado"])})
        if u.path == "/api/sit/completar":
            d = flow_dir(data.get("stream", ""), data.get("flow", ""))
            campos = load_req(d)["campos"]
            cat = load_catalog(d)
            idx = {e["clave"]: e for e in cat}

            def limpio(v):
                out = {}
                for k, x in (v or {}).items():
                    x = str(x).strip()
                    if k in campos and VALOR.match(x):
                        out[k] = x
                return out
            for it in data.get("items", []):
                e = idx.get(it.get("clave"))
                if e is not None:
                    e["aportados"] = {**e.get("aportados", {}), **limpio(it.get("valores"))}
                    e["aportados"] = {k: v for k, v in e["aportados"].items() if v}
            cd = data.get("centro_default")
            if cd:
                centro = str(cd.get("centro", "")).strip()
                if not re.match(r"^[A-Za-z0-9]{1,6}$", centro):
                    raise ValueError("Centro no válido")
                df = load_defaults(d)
                df[centro] = {k: v for k, v in {**df.get(centro, {}), **limpio(cd.get("valores"))}.items() if v}
                defaults_path(d).write_text(json.dumps(df, ensure_ascii=False), encoding="utf-8")
            catalog_path(d).write_text(json.dumps(cat, ensure_ascii=False), encoding="utf-8")
            return self._send(200, {"ok": True, "escenarios": cat, "defaults": load_defaults(d)})
        if u.path == "/api/modo":
            import sap_backend
            if data.get("modo") not in ("simulado", "sap"):
                raise ValueError("Modo no válido")
            cfg = sap_backend.guardar_modo(data["modo"])
            return self._send(200, {"modo": cfg["modo"], "sistemas": ["%s/%s" % (p["sid"], p["mandante"]) for p in cfg.get("sistemas_permitidos", [])]})
        if u.path == "/api/sit/chequear":
            d = flow_dir(data.get("stream", ""), data.get("flow", ""))
            claves = {str(c) for c in data.get("claves", [])}
            if not claves:
                raise ValueError("No hay escenarios seleccionados")
            try:
                cantidad = float(str(data.get("cantidad", 1)).replace(",", "."))
            except ValueError:
                raise ValueError("Cantidad no válida")
            if not 0 < cantidad <= 1000000:
                raise ValueError("Cantidad fuera de rango")
            modo = json.loads((d / "flow.json").read_text(encoding="utf-8")).get("modo", "migo")
            movs = {str(k): str(v).strip().upper() for k, v in (data.get("movs") or {}).items()}
            sel = []
            for e in load_catalog(d):
                if e["clave"] in claves:
                    if re.match(r"^[0-9A-Z]{3,4}$", movs.get(e["clave"], "")):
                        e = {**e, "mov": movs[e["clave"]]}   # el tipo que se ve en pantalla, sin confirmarlo
                    sel.append(e)
            def trabajo():
                backend = engine.crear_backend("chequeo")      # SAP real (solo lectura) si el modo local lo indica
                try:
                    return chequeo.chequear(sel, backend, cantidad, load_req(d), load_defaults(d), modo)
                finally:
                    if hasattr(backend, "cerrar"):
                        backend.cerrar()
            return self._send(200, en_sap(trabajo))
        if u.path == "/api/sit/preparar":
            d = flow_dir(data.get("stream", ""), data.get("flow", ""))
            claves = [str(c) for c in data.get("claves", [])]
            if not claves:
                raise ValueError("No hay escenarios seleccionados")
            try:
                cantidad = float(str(data.get("cantidad", 1)).replace(",", "."))
            except ValueError:
                raise ValueError("Cantidad no válida")
            docs = en_sap(preparar_real, d, claves, cantidad)
            for f in docs:
                if f["ok"]:
                    _PREPARADOS[f["clave"]] = {"lote": f["lote"], "ts": time.time()}
            return self._send(200, {"documentos": docs, "maximo": MAX_DOCS_REAL})
        if u.path == "/api/sit/contabilizar":
            d = flow_dir(data.get("stream", ""), data.get("flow", ""))
            if json.loads((d / "flow.json").read_text(encoding="utf-8")).get("modo") == "sto":
                raise ValueError("La contabilización real de pedidos de traslado (STO) aún no existe.")
            if str(data.get("confirmacion", "")).strip() != "CONTABILIZAR":
                raise ValueError("Falta la confirmación escrita: hay que teclear CONTABILIZAR.")
            claves = [str(c) for c in data.get("claves", [])]
            huellas = data.get("huellas") or {}
            if not claves or len(claves) > MAX_DOCS_REAL:
                raise ValueError("Se pueden contabilizar entre 1 y %d documentos por ejecución." % MAX_DOCS_REAL)
            try:
                cantidad = float(str(data.get("cantidad", 1)).replace(",", "."))
            except ValueError:
                raise ValueError("Cantidad no válida")
            vigentes = {c: _PREPARADOS[c]["lote"] for c in claves if c in _PREPARADOS and time.time() - _PREPARADOS[c]["ts"] < PREPARADO_TTL}
            if len(vigentes) != len(claves):
                raise ValueError("Los datos se prepararon hace más de %d minutos o no se prepararon: pulsa de nuevo «Contabilizar en SAP…»." % (PREPARADO_TTL // 60))
            # se recalcula todo con los datos actuales (sin volver a leer SAP): si algo cambió desde que el usuario lo vio, la huella ya no coincide
            prep = preparar_real(d, claves, cantidad, vigentes)
            for f in prep:
                if not f["ok"]:
                    raise ValueError("%s no se puede contabilizar: %s" % (f["jira_id"], f["problema"]))
                if str(huellas.get(f["clave"], "")).upper() != f["huella"]:
                    raise ValueError("%s: los datos han cambiado desde que los confirmaste (la huella no coincide). No se contabiliza nada." % f["jira_id"])
            with LOCK:
                rid = time.strftime("%Y%m%d-%H%M%S-") + "%04x" % (time.time_ns() & 0xFFFF)
            threading.Thread(target=execute_real, args=(data["stream"], data["flow"], prep, rid), daemon=True).start()
            return self._send(200, {"ok": True, "id": rid})
        if u.path == "/api/sit/run":
            d = flow_dir(data.get("stream", ""), data.get("flow", ""))
            claves = [str(c) for c in data.get("claves", [])]
            idx = {e["clave"]: e for e in load_catalog(d)}
            sin = [c for c in claves if c not in idx or not idx[c]["confirmado"]]
            if not claves or sin:
                raise ValueError("Hay escenarios sin confirmar el tipo de movimiento: %d" % len(sin) if claves else "No hay escenarios seleccionados")
            with LOCK:
                rid = time.strftime("%Y%m%d-%H%M%S-") + "%04x" % (time.time_ns() & 0xFFFF)
            try:
                cantidad = float(str(data.get("cantidad", 1)).replace(",", "."))
            except ValueError:
                raise ValueError("Cantidad no válida")
            if not 0 < cantidad <= 1000000:
                raise ValueError("Cantidad fuera de rango")
            cantidad = int(cantidad) if cantidad == int(cantidad) else cantidad
            props = {}
            for c, mats in (data.get("cantidades") or {}).items():
                if c in idx and isinstance(mats, dict):
                    for m, q in mats.items():
                        try:
                            q = float(q)
                        except (TypeError, ValueError):
                            continue
                        if 0 < q <= 1000000 and re.match(r"^[A-Za-z0-9_\-]{1,40}$", str(m)):
                            props.setdefault(c, {})[str(m)] = int(q) if q == int(q) else q
            threading.Thread(target=execute_sit, args=(data["stream"], data["flow"], claves, rid, cantidad, props), daemon=True).start()
            return self._send(200, {"ok": True, "id": rid})
        if u.path == "/api/nl":
            return self._send(200, interpret(str(data.get("text", ""))[:500], data.get("stream", ""), data.get("flow", "")))
        self._send(404, {"error": "No encontrado"})


class Servidor(ThreadingHTTPServer):
    allow_reuse_address = False   # en Windows, si no, un segundo servidor arranca "bien" en el mismo puerto sin recibir nada


if __name__ == "__main__":
    try:
        srv = Servidor((HOST, PORT), Handler)
    except OSError:
        print(f"ERROR: ya hay otro servidor usando el puerto {PORT}. Ciérralo (ventana negra anterior) y vuelve a abrir este programa.")
        print("Mientras siga abierto el antiguo, el navegador seguirá usando el código viejo.")
        sys.exit(1)
    print(f"Front de automatizaciones en http://{HOST}:{PORT}  (Ctrl+C para parar)")
    srv.serve_forever()
