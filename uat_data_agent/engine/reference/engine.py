import pandas as pd, re, sys
sys.path.insert(0,'/home/claude/work')
from parse import parse, load, F
from checks import ORG, org, PL, plants, sorgs, codes4, porgs, sorg_set, HOME, CTRY, RELATED
F2='/mnt/user-data/uploads/iGnite_SIT_Central__JIRA_FILE_.xlsx'
DYN=re.compile(r'(?i)<<+\s*(deliveries|shiptment document|shipment document|shipment cost)\s*>+')
PEND=re.compile(r'(?i)pending|mock|tbd|to be defined|x{3,}|\?\?|n/a|por definir|pendiente|Z_{3,}')
SUSMAT={'699250','599167','699238','699176'}
OCC=set(org['Company Code'].dropna())
CHECKS={
 'D01':('Data vacía','Seguro','Completar Data'),
 'D02':('Dato pendiente/placeholder en Data','Seguro','Completar Data'),
 'D04':('Referencia dinámica (dato generado en paso previo)','Seguro','Informativo: no es error'),
 'D03':('Sin planta en Data','Probable','Verificar si el paso requiere planta'),
 'F01':('Planta sin etiqueta "Plant:" (formato no estándar)','Seguro','Normalizar formato'),
 'O01':('Planta no existe en Org.Structure','Seguro','Validar contra T001W'),
 'O06':('Sociedad no existe en Org.Structure','Seguro','Validar contra T001'),
 'O02':('C.Code ≠ sociedad de la planta receptora','Probable','Validar con matriz de flujos / T001K'),
 'O03':('P.Org ≠ P.Org de la planta receptora','Probable','Validar con T024W'),
 'O04':('S.Org no asignada a la planta (suministradora si existe)','Probable','Validar con TVKWZ'),
 'U01':('Planta ajena a la unidad','Probable','Validar maestro Unidad→Planta'),
 'U02':('Planta de otro país para unidad-país','Suposición','Puede ser legítimo en flujos IC'),
 'M01':('Material sospechoso (serie 599/699, posible ficticio)','Probable','Validar contra MARC / Golden Data Set'),
}
def check_text(data, loc):
    data=data if isinstance(data,str) else ''
    d=parse(data); f=[]
    if not data.strip(): return [('D01','')]
    if PEND.search(DYN.sub('',data)): 
        m=PEND.search(DYN.sub('',data)); f.append(('D02',f'Marcador: "{m.group(0)}"'))
    if DYN.search(data): f.append(('D04',DYN.search(data).group(0)))
    pl=plants(d.get('Plant',[])+d.get('Plant2',[])+d.get('Plant3',[]))
    sp=plants(d.get('SupPlant',[])+d.get('DestPlant',[]))
    if not pl and not sp:
        if PL.search(data): f.append(('F01',f'Código {PL.search(data).group(1)} sin etiqueta'))
        else: f.append(('D03',''))
    cc=codes4(d.get('CCode',[])); so=sorgs(d.get('SOrg',[])); po=porgs(d.get('POrg',[]))
    for c in cc:
        if c not in OCC: f.append(('O06',f'C.Code {c}'))
    for p in pl+sp:
        if p not in ORG: f.append(('O01',f'Planta {p}'))
    chain=any('->' in v for v in d.get('Plant',[]))
    recv=pl
    if chain:
        ch=PL.findall(' '.join(d.get('Plant',[]))); recv=[ch[-1]]; sp=sp or [ch[0]]
    for p in recv:
        if p not in ORG: continue
        pc=ORG[p]['Company Code']; pp=ORG[p]['Purch. Org']
        if cc and len(recv)==1 and pc not in cc and all(c in OCC for c in cc): f.append(('O02',f'C.Code {"/".join(cc)} vs {p} (sociedad {pc})'))
        if po and len(recv)==1 and isinstance(pp,str) and pp not in po: f.append(('O03',f'P.Org {"/".join(po)} vs {p} ({pp})'))
    base=sp if sp else recv
    for s in so:
        known=[p for p in base if p in ORG]
        if known and not [p for p in known if s in sorg_set(p)]:
            f.append(('O04',f'S.Org {s} no asignada a {"/".join(known)}'+(' (suministradora)' if sp else '')))
    if loc in HOME and pl:
        ok=set(HOME[loc])|set(RELATED.get(loc,[]))
        bad=[p for p in pl if p not in ok]
        if bad:
            extra=''
            if loc in ('Alcañiz','Alcañiz Flavour'): extra=' — en PP/PM se usa '+HOME[loc][0]+'; QM/WM usan la contraria'
            f.append(('U01',f'{"/".join(bad)} en unidad {loc} (esperada {HOME[loc][0]}){extra}'))
    if loc in CTRY and pl and not sp:
        bad=[p for p in pl if p in ORG and ORG[p]['Country'] not in CTRY[loc]]
        if bad: f.append(('U02',f'{"/".join(bad)} ({",".join(ORG[p]["Country"] for p in bad)}) en unidad {loc}'))
    mats=set(re.findall(r'\b(\d{5,8})\b',' '.join(d.get('Material',[]))))
    s=sorted(mats&SUSMAT)
    if s: f.append(('M01','Material '+'/'.join(s)))
    return f
