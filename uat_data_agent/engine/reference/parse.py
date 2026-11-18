import pandas as pd, re
from collections import defaultdict
F='/mnt/user-data/uploads/iGnite_SCM_HUMAN_UAT_Planning_v20261008_SITsync.xlsx'
NORM={
 'plant':'Plant','plant 1':'Plant','plant 2':'Plant2','plant  3':'Plant3','destination plant':'DestPlant','source plant':'SupPlant',
 'supplier plant':'SupPlant','sup. plant':'SupPlant',
 'c.code':'CCode','company code':'CCode',
 'p.org':'POrg','purchase org':'POrg','purchase':'POrg',
 's.org':'SOrg','sales org':'SOrg',
 'doc type':'DocType','doc type 1':'DocType','doc type 2':'DocType','purchase order type':'DocType','planned order type':'DocType','notification type':'DocType','functional location doc type':'DocType',
 'mov.type':'MovType','mov type':'MovType','movement type':'MovType','mov. type':'MovType',
 'st.loc':'SLoc','st-loc ini':'SLoc','st.loc fin':'SLoc','storage location':'SLoc',
 'bp':'BP','bp - customer':'Customer','bp - vendor':'Vendor','vendor':'Vendor','supplier':'Vendor','bp role':'BPRole',
 'transportation planning point':'TPP','shipment type':'ShipType','sp.point':'ShipPoint','shipping point':'ShipPoint',
 'equipment':'Equipment','functional location':'FuncLoc',
}
def norm_label(l):
    l=l.strip().lower()
    if l.startswith('material') or l=='materia' or l=='materials' or l=='new material': return 'Material'
    if '-> bp' in l: return 'BP'
    return NORM.get(l, 'OTHER:'+l)
def parse(v):
    d=defaultdict(list)
    if not isinstance(v,str): return d
    cur=None
    for line in v.split('\n'):
        s=line.strip()
        if not s or re.fullmatch(r'-{3,}',s): cur=None if re.fullmatch(r'-{3,}',s) else cur; continue
        m=re.match(r'([^:]{1,40}):(.*)',s)
        if m and not re.match(r'^\d',m.group(1).strip()):
            cur=norm_label(m.group(1)); val=m.group(2).strip()
            if val: d[cur].append(val)
        else:
            if cur: d[cur].append(s)
            else: d['FREE'].append(s)
    return d
def load():
    cases=pd.read_excel(F,sheet_name='UAT_cases',dtype=str)
    scr=pd.read_excel(F,sheet_name='UAT_testscript - breaks by unit',dtype=str)
    org=pd.read_excel(F,sheet_name='Org.Structure',dtype=str,header=2)
    return cases,scr,org
PLANT_RE=re.compile(r'\b([CLMS]\d{3}|\d{4})\b')
