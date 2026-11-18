import pandas as pd, re, sys
sys.path.insert(0,'/home/claude/work')
from parse import *
from collections import Counter, defaultdict
F2='/mnt/user-data/uploads/iGnite_SIT_Central__JIRA_FILE_.xlsx'
cases,scr,org=load()
org=org[org['Plant'].notna()]
ORG={r['Plant']:r for _,r in org.iterrows()}
PL=re.compile(r'\b([CLMS]\d{3})\b')
def plants(vals): return sorted(set(PL.findall(' '.join(vals))))
def sorgs(vals):
    out=[]
    for v in vals:
        m=re.match(r'\s*(\d{4})',v)
        if m: out.append(m.group(1))
    return sorted(set(out))
def codes4(vals): return sorted(set(re.findall(r'\b(\d{4})\b',' '.join(vals))))
def porgs(vals): return sorted(set(re.findall(r'\b([A-Z]{2}\d{2})\b',' '.join(vals))))
def sorg_set(p):
    s=ORG[p]['Sales Org(s)'] if p in ORG else None
    if not isinstance(s,str): return set()
    return set(re.findall(r'(\d+)\s*–',s))
HOME={'Agrate':['M116'],'Alcañiz':['M109'],'Alcañiz Flavour':['M105'],'Algeria':['M117'],'ballobar':['M103'],
'Ghana':['M021'],'Le Pontet':['M027'],'Lubeck':['M025'],'Miajadas':['M015'],'NG - Kebbi':['M024'],'NG - Lagos':['M022'],
'NG - Sango':['M023'],'Puurs':['M026'],'Rubi':['M006'],'Senegal':['M120']}
CTRY={'Spain':['ES'],'Italy':['IT'],'Belgium':['BE'],'France':['FR'],'Germany':['DE'],'Nordics':['SE','FI'],'Cote Ivore':['CI']}
# unit-related plants (home + local LOs/ports) for plant units
RELATED={'Ghana':['M021','L048','L063'],'NG - Lagos':['M022','L046','L038'],'NG - Sango':['M023','L047','L038'],'NG - Kebbi':['M024','L038'],
'Algeria':['M117','S017'],'Senegal':['M120'],'ballobar':['M103','L035','L105','L031']}
PH=re.compile(r'(?i)pending|mock|tbd|to be defined|xxx|\?\?|<<\s*[^<>]*\s*>>|n/a|por definir|pendiente')
def run():
    P=scr['Data'].apply(parse)
    rows=[]
    for i,(idx,r) in enumerate(scr.iterrows()):
        d=P.iloc[i]; loc=r['Location by Unit']; data=r['Data'] if isinstance(r['Data'],str) else ''
        f=[]
        pl=plants(d.get('Plant',[])+d.get('Plant2',[])+d.get('Plant3',[]))
        sp=plants(d.get('SupPlant',[])+d.get('DestPlant',[]))
        cc=codes4(d.get('CCode',[])); so=sorgs(d.get('SOrg',[])); po=porgs(d.get('POrg',[]))
        mats=re.findall(r'\b(\d{5,8})\b',' '.join(d.get('Material',[])))
        if not data.strip(): f.append(('D01','Data vacía'))
        if PH.search(data): f.append(('D02','Placeholder/pendiente en Data'))
        if data.strip() and not pl and not sp: f.append(('D03','Sin planta en Data'))
        for p in pl+sp:
            if p not in ORG: f.append(('O01',f'Planta {p} no existe en Org.Structure'))
        chain=any('->' in v for v in d.get('Plant',[]))
        recv=[pl[-1]] if (chain and pl) else pl
        if chain:
            ch=PL.findall(' '.join(d.get('Plant',[])))
            recv=[ch[-1]]; sp=sp or [ch[0]]
        supply=sp
        for p in recv:
            if p not in ORG: continue
            pc=ORG[p]['Company Code']; pp=ORG[p]['Purch. Org']
            if cc and len(recv)==1 and pc not in cc: f.append(('O02',f'C.Code {"/".join(cc)} ≠ sociedad de planta receptora {p} ({pc})'))
            if po and len(recv)==1 and isinstance(pp,str) and pp not in po: f.append(('O03',f'P.Org {"/".join(po)} ≠ P.Org de planta receptora {p} ({pp})'))
        base=supply if supply else recv
        for s in so:
            okp=[p for p in base if p in ORG and s in sorg_set(p)]
            known=[p for p in base if p in ORG]
            if known and not okp: f.append(('O04',f'S.Org {s} no asignada a {"/".join(known)}'+(' (planta suministradora)' if supply else '')))
        # unit coherence
        if loc in HOME and pl:
            ok=set(HOME[loc])|set(RELATED.get(loc,[]))
            bad=[p for p in pl if p not in ok]
            if bad: f.append(('U01',f'Planta {"/".join(bad)} ajena a la unidad {loc} (esperada {HOME[loc][0]})'))
        if loc in CTRY and pl:
            bad=[p for p in pl if p in ORG and ORG[p]['Country'] not in CTRY[loc]]
            if bad and not sp: f.append(('U02',f'Planta {"/".join(bad)} de otro país para unidad {loc}'))
        for code,msg in f:
            rows.append(dict(row=idx+2,ID=r['ID by unit'],NewID=r['New ID'],Step=r['Step'],L2=r['L2'],L3=r['L3'],Loc=loc,Scenario=r['Test Scenario'],Transaction=r['Transaction'],Check=code,Detail=msg,Data=data))
    return pd.DataFrame(rows),P
