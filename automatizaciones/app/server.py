"""Servidor local del front de automatizaciones.

Solo escucha en 127.0.0.1, sin dependencias externas. Los datos de prueba y los
resultados se guardan en data/ y results/ de cada flujo (ignoradas por git).
Uso:  python server.py   ->  http://127.0.0.1:8765
"""
import json
import re
import threading
import time
import unicodedata
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote

import engine
from xlsx_reader import read_xlsx

ROOT = Path(__file__).resolve().parent.parent  # .../automatizaciones
STATIC = Path(__file__).resolve().parent / "static"
HOST, PORT = "127.0.0.1", 8765
MAX_UPLOAD = 20 * 1024 * 1024
SAFE = re.compile(r"^[A-Za-z0-9_\-]+$")
SAFE_FILE = re.compile(r"^[A-Za-z0-9_\-. ]+\.xlsx$")
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
                           "reglas": meta.get("reglas", {}), "ficheros": len(list((f / "data").glob("*.xlsx"))), "ejecuciones": len(runs)})
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
        run["filas"], run["resumen"] = engine.run(headers, rows, engine.MockSap(), log)
        run["estado"] = "ERROR" if run["resumen"].get("error") else "FINALIZADA"
    except Exception as e:
        log("ERROR", "Fallo en la ejecución: %s" % e)
        run["estado"] = "ERROR"
    run["fin"] = time.strftime("%Y-%m-%d %H:%M:%S")
    save()


def _plain(s):
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


def interpret(text):
    """Interpretación local por palabras clave. No envía nada fuera del equipo."""
    t = _plain(text)
    words = set(re.findall(r"[a-z0-9]+", t))
    best = None
    for s in tree():
        for f in s["flujos"]:
            meta = json.loads((ROOT / s["id"] / "flujos" / f["id"] / "flow.json").read_text(encoding="utf-8"))
            kws = {_plain(k) for k in meta.get("palabras_clave", [])} | set(re.findall(r"[a-z0-9]+", _plain(f["nombre"])))
            score = len(words & kws)
            if score and (not best or score > best[0]):
                best = (score, s["id"], f["id"])
    if not best:
        return {"ok": False, "mensaje": "No he encontrado un flujo que encaje. Prueba con el nombre del flujo."}
    _, stream, flow = best
    files = list_files(flow_dir(stream, flow))
    chosen = next((f for f in files if _plain(f["nombre"]).rsplit(".", 1)[0] in t), files[0] if files else None)
    accion = "lanzar" if words & {"lanza", "lanzar", "ejecuta", "ejecutar", "corre", "simula", "simular", "pruebas", "prueba"} else "ver"
    return {"ok": True, "stream": stream, "flujo": flow, "fichero": chosen["nombre"] if chosen else None, "accion": accion,
            "mensaje": "Entendido: flujo «%s»%s." % (flow, (", fichero «%s»" % chosen["nombre"]) if chosen else ", pero no hay ficheros subidos")}


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
        if u.path == "/api/nl":
            return self._send(200, interpret(str(data.get("text", ""))[:500]))
        self._send(404, {"error": "No encontrado"})


if __name__ == "__main__":
    print(f"Front de automatizaciones en http://{HOST}:{PORT}  (Ctrl+C para parar)")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
