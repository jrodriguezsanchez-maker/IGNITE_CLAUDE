import sys, pickle; sys.path.insert(0,'/home/claude/work')
from engine import *
cases,scr,_=load()
PF=pd.read_pickle('profile.pkl').set_index('ID by unit')
B=pickle.load(open('built.pkl','rb')); FND=B['FND']
S=pickle.load(open('share.pkl','rb')); U=S['U']
KO={'D01','D02','F01','O01','O06','O02','O03','O04','U01','M01'}
fx=FND[FND.Check!='D04'].groupby('Fila UAT_testscript')['Check'].apply(lambda s: sorted(set(s)))
case_ko=FND[FND.Check.isin(KO)].groupby('ID by unit').size()
case_share=U.groupby('id')['n'].max()
# per step shared materials
U2=U[U.n>1].copy()
stepsh=U2.groupby('i').apply(lambda g: [(r.m,r.p,r.n) for r in g.sort_values('n',ascending=False).itertuples()])
LBL={'D01':'Completar Data vacía','D02':'Completar dato pendiente','F01':'Normalizar formato (Plant:)','O01':'Planta inexistente','O06':'Sociedad inexistente',
     'O02':'Sociedad','O03':'Org. compras','O04':'Org. ventas','U01':'Planta de la unidad','U02':'Planta de otro país (verificar)','M01':'Material ficticio','D03':'Planta (verificar si aplica)'}
out=[]
for i,r in scr.iterrows():
    cid=r['ID by unit']; row=i+2
    need=PF.at[cid,'Tipo de necesidad'] if cid in PF.index else ''
    codes=fx.get(row,[])
    items=[LBL[c] for c in codes if c in LBL]
    sh=stepsh.get(i,[])
    if sh:
        m,p,n=sh[0]
        lab='Equipo/UT' if m.startswith('EQ:') else 'Material'
        mm=m[3:] if m.startswith('EQ:') else m
        txt=f'{lab} {mm} compartido con {n-1} caso{"s" if n-1!=1 else ""} más ({p})' if p!='*' else f'{lab} {mm} compartido con {n-1} caso{"s" if n-1!=1 else ""} más'
        if len(sh)>1: txt+=f' (+{len(sh)-1} más compartidos)'
        items.insert(0,txt)
    ko=case_ko.get(cid,0)>0; excl=case_share.get(cid,0)<=1
    if need.startswith('Crea su propio') or need.startswith('Solo consulta'):
        org,dp,conf='No requiere','', 'Suposición'
        items=[x for x in items if not x.startswith(('Material','Equipo'))]
    elif need.startswith('Necesita transportista'):
        org,dp,conf='Pendiente extracción','', 'Probable'
        items.insert(0,'Transportista (BP) dedicado + entregas del caso origen')
    elif need.startswith('Sin material'):
        org,dp,conf='Pendiente perfil','', 'Suposición'
        items.insert(0,'Perfil por validar (02_Perfil_por_caso)')
    elif excl and not ko:
        org,dp,conf='Sin cambio',r['Data'] if isinstance(r['Data'],str) else '', 'Probable'
        items=['Ninguno (dato ya exclusivo del caso; falta validar MARC/stock)']
    else:
        org,dp,conf='Pendiente extracción','', 'Probable'
    out.append((row, dp, org, '; '.join(dict.fromkeys(items)), ', '.join(codes), conf, r['Accenture Owner'] if isinstance(r['Accenture Owner'],str) else ''))
V=pd.DataFrame(out,columns=['row','AG','AH','AI','AJ','AK','AL'])
V.to_pickle('v0.pkl')
print(V.AH.value_counts().to_dict())
cs=V.merge(scr[['ID by unit']].assign(row=scr.index+2),on='row').groupby('ID by unit')['AH'].agg(lambda s: s.value_counts().index[0])
print(cs.value_counts().to_dict())
print(V.sample(5,random_state=3)[['AH','AI','AJ']].to_string())
