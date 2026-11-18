"""Escritura no destructiva de AG–AL en una COPIA del UAT.
Solo cambian xl/worksheets/sheet2.xml y xl/tables/table2.xml (no se usa openpyxl para guardar)."""
import re
import zipfile
from xml.sax.saxutils import escape

SHEET_PART, TABLE_PART = 'xl/worksheets/sheet2.xml', 'xl/tables/table2.xml'
HDR = ['Data propuesta', 'Origen propuesta', 'Qué cambia', 'Hallazgos que corrige', 'Confianza propuesta', 'Validar con']
COLS = ['AG', 'AH', 'AI', 'AJ', 'AK', 'AL']
WIDTHS = [55, 22, 50, 20, 20, 22]
ILL = re.compile('[\x00-\x08\x0b\x0c\x0e-\x1f]')


def _cell(ref, val, style=None):
    if val is None or val == '':
        return ''
    st = f' s="{style}"' if style else ''
    return f'<c r="{ref}"{st} t="inlineStr"><is><t xml:space="preserve">{escape(ILL.sub("", str(val)))}</t></is></c>'


def patch(src, out, values, last_row=None):
    """values: {nº fila Excel: {'AG': texto, ...}}. Devuelve nº de filas con contenido escrito."""
    zin = zipfile.ZipFile(src)
    s = zin.read(SHEET_PART).decode('utf-8')
    t = zin.read(TABLE_PART).decode('utf-8')
    m = re.search(r'ref="A1:AF(\d+)"', t)
    assert m, 'table2.xml no tiene ref A1:AF<n>; el fichero no es el esperado'
    last = last_row or int(m.group(1))
    h1 = re.search(r'<c r="AE1"[^>]*?s="(\d+)"', s)
    hstyle = h1.group(1) if h1 else None
    written = 0

    def rowrep(mo):
        nonlocal written
        head, body = mo.group(1), mo.group(2)
        r = int(re.search(r' r="(\d+)"', head).group(1))
        if r > last or 'r="AG' in body:
            return mo.group(0)
        if r == 1:
            add = ''.join(_cell(f'{c}1', h, hstyle) for c, h in zip(COLS, HDR))
        else:
            v = values.get(r)
            add = ''.join(_cell(f'{c}{r}', v.get(c)) for c in COLS) if v else ''
            written += 1 if add else 0
        if not add:
            return mo.group(0)
        head = head.replace('spans="1:32"', 'spans="1:38"')
        return f'{head}{body}{add}</row>'

    s2, n = re.subn(r'(<row [^>]*?(?<!/)>)(.*?)</row>', rowrep, s, flags=re.S)
    assert n >= last, f'filas leídas {n} < {last}'
    s2 = s2.replace('<dimension ref="A1:AF7396"/>', '<dimension ref="A1:AL7396"/>', 1)
    cols = ''.join(f'<col min="{33 + i}" max="{33 + i}" width="{w}" customWidth="1"/>' for i, w in enumerate(WIDTHS))
    assert s2.count('</cols>') == 1
    s2 = s2.replace('</cols>', cols + '</cols>', 1)

    t2 = t.replace(f'ref="A1:AF{last}"', f'ref="A1:AL{last}"')           # table y autoFilter
    ids = [int(x) for x in re.findall(r'<tableColumn id="(\d+)"', t2)]
    cnt = int(re.search(r'<tableColumns count="(\d+)"', t2).group(1))
    new = ''.join(f'<tableColumn id="{max(ids) + 1 + k}" name="{escape(h)}"/>' for k, h in enumerate(HDR))
    t2 = t2.replace(f'tableColumns count="{cnt}"', f'tableColumns count="{cnt + 6}"').replace('</tableColumns>', new + '</tableColumns>')

    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as zo:
        for it in zin.infolist():
            data = zin.read(it.filename)
            if it.filename == SHEET_PART:
                data = s2.encode('utf-8')
            elif it.filename == TABLE_PART:
                data = t2.encode('utf-8')
            zo.writestr(it, data)
    return written


def verify(src, out):
    """Comprueba que solo difieren sheet2 y table2, y que A:AF de cada fila quedan idénticas."""
    a, b = zipfile.ZipFile(src), zipfile.ZipFile(out)
    diff = [n for n in a.namelist() if a.read(n) != b.read(n)]
    ok_parts = sorted(diff) == sorted([SHEET_PART, TABLE_PART])
    strip = re.compile(r'<c r="A[G-L]\d+"[^>]*?(?:/>|>.*?</c>)', re.S)

    def rows(z):
        s = z.read(SHEET_PART).decode('utf-8')
        out = {}
        for mo in re.finditer(r'<row [^>]*?(?<!/)>.*?</row>', s, flags=re.S):
            x = strip.sub('', mo.group(0)).replace('spans="1:38"', 'spans="1:32"')
            out[re.search(r' r="(\d+)"', x).group(1)] = x
        return out
    ra, rb = rows(a), rows(b)
    same = ra == rb
    return {'solo_sheet2_y_table2': ok_parts, 'partes_distintas': diff, 'filas_A_AF_identicas': same, 'filas': len(ra)}
