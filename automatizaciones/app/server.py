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


def load_defaults(d):
    p = defaults_path(d)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


VALOR = re.compile(r"^[A-Za-z0-9_\-\. /,;]{0,60}$")


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
                                    "requisitos": load_req(d), "defaults": load_defaults(d),
                                    "cantidad_por_defecto": json.loads((d / "flow.json").read_text(encoding="utf-8")).get("cantidad_por_defecto", 1)})
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
            backend = engine.crear_backend("chequeo")      # SAP real (solo lectura) si el modo local lo indica
            try:
                return self._send(200, chequeo.chequear(sel, backend, cantidad, load_req(d), load_defaults(d), modo))
            finally:
                if hasattr(backend, "cerrar"):
                    backend.cerrar()
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
