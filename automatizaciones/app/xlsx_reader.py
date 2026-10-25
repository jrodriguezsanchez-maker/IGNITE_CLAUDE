"""Lector mínimo de .xlsx con la librería estándar (sin dependencias externas)."""
import re
import zipfile
import xml.etree.ElementTree as ET

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
MAX_UNCOMPRESSED = 50 * 1024 * 1024


def _col_index(ref):
    letters = re.match(r"[A-Z]+", ref).group(0)
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n - 1


def read_xlsx(path):
    """Devuelve (cabeceras, filas) de la primera hoja. Filas = lista de dicts."""
    with zipfile.ZipFile(path) as z:
        if sum(i.file_size for i in z.infolist()) > MAX_UNCOMPRESSED:
            raise ValueError("Fichero demasiado grande")
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall("m:si", NS):
                shared.append("".join(t.text or "" for t in si.iter("{%s}t" % NS["m"])))
        sheets = sorted(n for n in z.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", n))
        if not sheets:
            raise ValueError("El Excel no tiene hojas")
        root = ET.fromstring(z.read(sheets[0]))
    rows = []
    for r in root.iter("{%s}row" % NS["m"]):
        vals = {}
        for c in r.findall("m:c", NS):
            t = c.get("t")
            v = c.find("m:v", NS)
            if t == "inlineStr":
                val = "".join(x.text or "" for x in c.iter("{%s}t" % NS["m"]))
            elif v is None:
                continue
            elif t == "s":
                val = shared[int(v.text)]
            else:
                val = v.text
            vals[_col_index(c.get("r"))] = val
        if vals:
            rows.append([vals.get(i, "") for i in range(max(vals) + 1)])
    if not rows:
        return [], []
    headers = [str(h).strip() for h in rows[0]]
    data = []
    for row in rows[1:]:
        row = row + [""] * (len(headers) - len(row))
        data.append({headers[i]: row[i] for i in range(len(headers))})
    return headers, data
