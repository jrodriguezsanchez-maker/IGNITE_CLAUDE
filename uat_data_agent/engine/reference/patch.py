import zipfile, re, shutil, pandas as pd
from xml.sax.saxutils import escape
SRC='/mnt/user-data/uploads/iGnite_SCM_HUMAN_UAT_Planning_v20261008_SITsync.xlsx'
OUT='/mnt/user-data/outputs/iGnite_SCM_HUMAN_UAT_Planning_v20261106_DataProposal_v0.xlsx'
V=pd.read_pickle('/home/claude/work/v0.pkl').set_index('row')
HDR=['Data propuesta','Origen propuesta','Qué cambia','Hallazgos que corrige','Confianza propuesta','Validar con']
COLS=['AG','AH','AI','AJ','AK','AL']
ILL=re.compile('[\x00-\x08\x0b\x0c\x0e-\x1f]')
def cell(ref,val,style=None):
    st=f' s="{style}"' if style else ''
    if val is None or val=='': return ''
    v=escape(ILL.sub('',str(val)))
    return f'<c r="{ref}"{st} t="inlineStr"><is><t xml:space="preserve">{v}</t></is></c>'
zin=zipfile.ZipFile(SRC)
s=zin.read('xl/worksheets/sheet2.xml').decode('utf-8')
t=zin.read('xl/tables/table2.xml').decode('utf-8')
def rowrep(m):
    head,body=m.group(1),m.group(2)
    r=int(re.search(r' r="(\d+)"',head).group(1))
    if r>7080: return m.group(0)
    if r==1: add=''.join(cell(f'{c}1',h,'29') for c,h in zip(COLS,HDR))
    else:
        v=V.loc[r]; add=''.join(cell(f'{c}{r}',v[c]) for c in COLS)
    head=head.replace('spans="1:32"','spans="1:38"')
    return f'{head}{body}{add}</row>'
s2,nrows=re.subn(r'(<row [^>]*?(?<!/)>)(.*?)</row>',rowrep,s,flags=re.S)
assert nrows>=7080, nrows
s2=s2.replace('<dimension ref="A1:AF7396"/>','<dimension ref="A1:AL7396"/>',1)
newcols='<col min="33" max="33" width="55" customWidth="1"/><col min="34" max="34" width="22" customWidth="1"/><col min="35" max="35" width="50" customWidth="1"/><col min="36" max="37" width="20" customWidth="1"/><col min="38" max="38" width="22" customWidth="1"/>'
assert s2.count('</cols>')==1
s2=s2.replace('</cols>',newcols+'</cols>',1)
t2=t.replace('ref="A1:AF7080"','ref="A1:AL7080"')
assert t2.count('A1:AL7080')==2
tc=''.join(f'<tableColumn id="{36+k}" name="{escape(h)}"/>' for k,h in enumerate(HDR))
t2=t2.replace('tableColumns count="32"','tableColumns count="38"').replace('</tableColumns>',tc+'</tableColumns>')
zout=zipfile.ZipFile(OUT,'w',zipfile.ZIP_DEFLATED)
for it in zin.infolist():
    data=zin.read(it.filename)
    if it.filename=='xl/worksheets/sheet2.xml': data=s2.encode('utf-8')
    elif it.filename=='xl/tables/table2.xml': data=t2.encode('utf-8')
    zout.writestr(it,data)
zout.close(); print('ok',nrows,OUT)
