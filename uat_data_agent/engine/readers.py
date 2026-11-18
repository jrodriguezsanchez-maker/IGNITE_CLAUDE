"""Lectura de exportaciones SE16N (texto con tabuladores) y CSV/XLSX manuales; valida output_fields."""
import csv
import io
from pathlib import Path


class MissingColumns(Exception):
    pass


def _split(line):
    if line.lstrip().startswith('|'):
        return [c.strip() for c in line.strip().strip('|').split('|')]
    return [c.strip() for c in line.rstrip('\r\n').split('\t')]


def read_table(path):
    p = Path(path)
    ext = p.suffix.lower()
    if ext == '.xlsx':
        import openpyxl
        wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
        rows = list(wb.worksheets[0].iter_rows(values_only=True))
        if not rows:
            return []
        hdr = [str(h).strip() if h is not None else '' for h in rows[0]]
        return [dict(zip(hdr, ['' if c is None else str(c).strip() for c in r])) for r in rows[1:]]
    raw = p.read_bytes()
    text = None
    for enc in ('utf-8-sig', 'cp1252'):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    lines = [l for l in text.splitlines() if l.strip() and not set(l.strip()) <= set('-|+ ')]
    if not lines:
        return []
    if ext == '.csv':
        dialect = csv.Sniffer().sniff(lines[0], delimiters=',;\t')
        recs = list(csv.reader(io.StringIO('\n'.join(lines)), dialect))
    else:
        recs = [_split(l) for l in lines]
    hdr = recs[0]
    return [dict(zip(hdr, r)) for r in recs[1:]]


def validate(name, rows, output_fields):
    if not rows:
        return
    missing = [f for f in output_fields if f not in rows[0]]
    if missing:
        raise MissingColumns(
            f"{name}: faltan columnas {missing}. Presentes: {list(rows[0])}. "
            f"Re-exporta de SE16N marcando esos campos como salida.")


EXCL = []      # [(desde, hasta)] de número de material que no aplican (se rellena desde config/settings.yaml)


def set_exclusiones(rangos):
    global EXCL
    EXCL = [(int(a), int(b)) for a, b in (rangos or [])]


def excluido(matnr):
    m = str(matnr).strip()
    return m.isdigit() and any(a <= int(m) <= b for a, b in EXCL)


def load_all(raw_dir, extractions=None):
    """Devuelve (tablas, avisos). Un fichero por tabla: <TABLA>.txt|tsv|csv|xlsx."""
    tables, warns = {}, []
    spec = {e['name']: e.get('output_fields', []) for e in (extractions or [])}
    d = Path(raw_dir)
    if not d.exists():
        return tables, [f'No existe {raw_dir}']
    for f in sorted(d.glob('*')):
        if f.suffix.lower() not in ('.txt', '.tsv', '.csv', '.xlsx'):
            continue
        name = f.stem.upper().split('__')[0]       # TABLA o TABLA__PLANTA (consultas a demanda)
        try:
            rows = read_table(f)
            if name in spec:
                validate(name, rows, spec[name])
            if EXCL and rows and 'MATNR' in rows[0]:
                rows = [r for r in rows if not excluido(r['MATNR'])]
            tables.setdefault(name, []).extend(rows)
        except MissingColumns as e:
            warns.append(str(e))
        except Exception as e:
            warns.append(f'{f.name}: {type(e).__name__}: {e}')
    return tables, warns
