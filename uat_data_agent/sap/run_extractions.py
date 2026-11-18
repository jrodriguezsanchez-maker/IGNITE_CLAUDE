"""Ejecuta las recetas de config/extractions.yaml contra SAP (solo lectura) y deja un manifiesto.
Uso:  python sap/run_extractions.py [--dry-run] [--only MARC,MARD]
"""
import sys, os, json, datetime, argparse, yaml
sys.path.insert(0, os.path.dirname(__file__))
from sap_gui import attach, new_session, close_session, se16n_extract

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def resolve(v, ex):
    """Sustituye "@nombre" por ex["lists"] o ex["params"]; admite rangos {low, high}."""
    def one(x):
        if isinstance(x, str) and x.startswith("@"):
            k = x[1:]
            return ex["lists"].get(k, ex.get("params", {}).get(k))
        return x
    if isinstance(v, dict):
        return {k: one(x) for k, x in v.items()}
    v = one(v)
    return v if isinstance(v, list) else [v]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--only", default=""); ap.add_argument("--max-rows", type=int, default=0, help="prueba humo: limita filas por tabla")
    ap.add_argument("--skip-existing", action="store_true", help="no vuelve a extraer tablas que ya están en raw_dir")
    a = ap.parse_args()
    st = yaml.safe_load(open(os.path.join(ROOT, "config/settings.yaml"), encoding="utf-8"))
    ex = yaml.safe_load(open(os.path.join(ROOT, "config/extractions.yaml"), encoding="utf-8"))
    only = {x.strip().upper() for x in a.only.split(",") if x.strip()}
    s = base = conn = None
    if not a.dry_run:
        conn, base = attach(st["sap"])
        s = new_session(conn, base)
    man = {"timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
           "system": None if s is None else s.Info.SystemName, "client": None if s is None else s.Info.Client, "items": []}
    for r in ex["extractions"]:
        if only and r["name"].upper() not in only:
            continue
        filt = {f: resolve(v, ex) for f, v in (r.get("filters") or {}).items()}
        target = os.path.join(ROOT, st["paths"]["raw_dir"], r["name"] + ".txt")
        item = {"name": r["name"], "table": r["table"], "filters": {k: (v if isinstance(v, dict) else len(v)) for k, v in filt.items()}, "file": None, "error": None}
        if a.skip_existing and os.path.exists(target):
            item["file"] = target; item["skipped"] = True
            print(f"{r['name']}: ya existe, se omite")
        else:
            try:
                item["file"] = se16n_extract(s, r["table"], filt, r["name"], st["sap"], dry_run=a.dry_run, max_rows=a.max_rows or None, fields=r.get("output_fields"))
            except Exception as e:      # una tabla que falla no tumba el resto; queda en el manifiesto
                item["error"] = f"{type(e).__name__}: {e}"
                print(f"{r['name']}: ERROR {item['error']}")
                if type(e).__name__ == "GuardError" and "Sesión en" in str(e):
                    raise               # sistema/mandante equivocado: parar todo
        man["items"].append(item)
    if s is not None:
        close_session(s)
    out = os.path.join(ROOT, st["paths"]["raw_dir"], "manifest.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(man, open(out, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print("Manifiesto:", out)

if __name__ == "__main__":
    main()
