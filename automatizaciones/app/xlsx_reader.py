"""Lector mínimo de .xlsx con la librería estándar (sin dependencias externas)."""
import re
import zipfile
import xml.etree.ElementTree as ET

M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PKG = "{http://schemas.openxmlformats.org/package/2006/relationships}"
MAX_UNCOMPRESSED = 200 * 1024 * 1024


def _col_index(ref):
    n = 0
    for ch in re.match(r"[A-Z]+", ref).group(0):
        n = n * 26 + ord(ch) - 64
    return n - 1


def sheet_names(path):
    with zipfile.ZipFile(path) as z:
        return [s.get("name") for s in ET.fromstring(z.read("xl/workbook.xml")).iter(M + "sheet")]


def _sheet_path(z, sheet):
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels")).iter(PKG + "Relationship")}
    sheets = [(s.get("name"), rels.get(s.get(R + "id"))) for s in wb.iter(M + "sheet")]
    if not sheets:
        raise ValueError("El Excel no tiene hojas")
    for name, target in sheets:
        if sheet is None or name == sheet:
            t = target.lstrip("/")
            return t if t.startswith("xl/") else "xl/" + t
    raise ValueError("No existe la hoja «%s»" % sheet)


def read_xlsx(path, sheet=None):
    """Devuelve (cabeceras, filas) de la hoja indicada (por defecto la primera). Filas = lista de dicts."""
    with zipfile.ZipFile(path) as z:
        if sum(i.file_size for i in z.infolist()) > MAX_UNCOMPRESSED:
            raise ValueError("Fichero demasiado grande")
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall(M + "si"):
                shared.append("".join(t.text or "" for t in si.iter(M + "t")))
        rows = []
        with z.open(_sheet_path(z, sheet)) as f:
            for _, el in ET.iterparse(f):
                if el.tag != M + "row":
                    continue
                vals = {}
                for c in el.findall(M + "c"):
                    t = c.get("t")
                    v = c.find(M + "v")
                    if t == "inlineStr":
                        val = "".join(x.text or "" for x in c.iter(M + "t"))
                    elif v is None:
                        continue
                    elif t == "s":
                        val = shared[int(v.text)]
                    else:
                        val = v.text
                    vals[_col_index(c.get("r"))] = val
                if vals:
                    rows.append([vals.get(i, "") for i in range(max(vals) + 1)])
                el.clear()
    if not rows:
        return [], []
    headers = [str(h).strip() for h in rows[0]]
    data = []
    for row in rows[1:]:
        row = row + [""] * (len(headers) - len(row))
        data.append({headers[i]: row[i] for i in range(len(headers))})
    return headers, data
