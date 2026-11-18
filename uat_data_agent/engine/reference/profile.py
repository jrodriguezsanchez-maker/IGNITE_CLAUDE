import sys; sys.path.insert(0,'/home/claude/work')
from engine import *
from collections import Counter, defaultdict
cases,scr,_=load()
P=scr['Data'].apply(parse)
T=scr['Transaction'].fillna('').str.upper()
CONS_MOV={'311','313','315','321','322','325','343','344','541','551','701','702','707','708','301','309','261','201','221'}
R=[
 ('crea_maestro', r'\b(MM01|MDM FIORI|CS01|C223|CA01|CA11|QP01|IE01|IL01|IA05|IP42|CV01N|QS23|QS33|CR01|MSC1N)\b'),
 ('stock_salida', r'\b(VL01N|VL10B|VL10D|VL02N|VL10|LT01|LT03|LT12|LT06|MB21|MF60|MFBF|MB1B|LI01N|LI20|LM00|LM02|LM05|LL01|VL32N|MB56|ZWM\d+)\b'),
 ('pedido_compra', r'\b(ME21N|ME2[123]N|MIRO|ME61)\b'),
 ('venta', r'\b(VA01|VA02|VF01|VL01N|VL10B)\b'),
 ('produccion', r'\b(MFBF|MD61|MD11|MD12|CO11N|CO01|MF50|MF12|MF42N|COOIS|CK11N|CK24|ZPP\w*)\b'),
 ('calidad', r'\b(QA32|QE51N|QA01|QM01|QM02|QE11|QI01|QP02|QP60|ZQM\w*)\b'),
 ('wm', r'\b(LT\d\d|LS\d\d|LI\d\dN?|LL01|LM\d\d|ZWM\w*|LX\d\d)\b'),
 ('mantenimiento', r'\b(IW\d\d|IH01|IE0\d|IL0\d|IP\d\d|PM FIORI|ZPM\w*)\b'),
 ('transporte', r'\b(VT01N|VT02N|VI01|VI02|TK11|VT\d\dN?)\b'),
 ('mov_mercancia', r'\b(MIGO|MGO|MI0\d|MI10|MB1[ABC]|MBST)\b'),
 ('solo_consulta', r'\b(FB03|KE24|CKM3N|SQ01|CO2 REPORT|MMBE|MB52|ZMMR\w*)\b'),
]
def ctx(v): return v if isinstance(v,str) else ''
scr['_T']=T
rows=[]
for cid,g in scr.groupby('ID by unit',sort=False):
    idx=g.index
    tt=' '.join(g['_T'])
    flags={k:bool(re.search(p,tt)) for k,p in R}
    pls=Counter(); sps=Counter(); mats=set(); mlabels=Counter(); bps=set(); cust=set(); vend=set(); dts=set(); mvs=set(); ccs=set(); sos=set(); pos=set(); lo=False; ph=False
    for i in idx:
        d=P.loc[i]
        for p in plants(d.get('Plant',[])+d.get('Plant2',[])+d.get('Plant3',[])): pls[p]+=1
        for p in plants(d.get('SupPlant',[])+d.get('DestPlant',[])): sps[p]+=1
        for v in d.get('Material',[]): mats|=set(re.findall(r'\b\d{5,8}\b',v))
        for m in re.findall(r'Material (Z[A-Z]{3})',ctx(scr.at[i,'Data'])): mlabels[m]+=1
        for m in re.findall(r'\b(Z(?:FIN|SEM|RAW|FOR|PAC|PAS))\s*-\s*\d',ctx(scr.at[i,'Data'])): mlabels[m]+=1
        bps|=set(re.findall(r'\b\d{4,8}\b',' '.join(d.get('BP',[]))))
        cust|=set(re.findall(r'\b\d{4,8}\b',' '.join(d.get('Customer',[]))))
        vend|=set(re.findall(r'\b\d{4,8}\b',' '.join(d.get('Vendor',[]))))
        dts|=set(re.findall(r'\b(Z[A-Z0-9]{2,4}|PE|Q\d)\b',' '.join(d.get('DocType',[]))))
        mvs|=set(re.findall(r'\b\d{3}\b',' '.join(d.get('MovType',[]))))
        ccs|=set(codes4(d.get('CCode',[]))); sos|=set(sorgs(d.get('SOrg',[]))); pos|=set(porgs(d.get('POrg',[])))
        if PEND.search(DYN.sub('',ctx(scr.at[i,'Data']))): ph=True
    allp=list(pls)+list(sps)
    lo=any(p.startswith('L') for p in allp) or bool(re.search(r'EDI MESSAGE',tt))
    eq=set()
    for i in idx:
        d=P.loc[i]; eq|=set(re.findall(r'[A-Z0-9_]{5,}',' '.join(d.get('Equipment',[])+d.get('FuncLoc',[]))))
    gr_only = flags['mov_mercancia'] and mvs and mvs<= {'101','103','105'}
    stock = flags['stock_salida'] or bool(mvs&CONS_MOV) or (flags['mov_mercancia'] and not gr_only) or bool({'ZINT','ZTRA','ZINR'}&dts and sps) or flags['venta'] or bool(mvs&CONS_MOV) or bool({'ZINT','ZTRA','ZINR'}&dts and sps) or flags['venta']
    recv=[p for p,_ in pls.most_common()]
    main=recv[0] if recv else (list(sps)[0] if sps else '')
    o=ORG.get(main)
    r0=g.iloc[0]
    only_cons = flags['solo_consulta'] and not any(flags[k] for k in flags if k!='solo_consulta')
    if flags['crea_maestro'] and not (stock or flags['pedido_compra'] or flags['venta'] or flags['produccion'] or flags['calidad'] or flags['wm']): need='Crea su propio dato (no necesita candidato)'
    elif only_cons: need='Solo consulta (hereda dato de otro caso)'
    elif r0['L2'].startswith('5.3') and eq: need='Necesita equipo/ubicación técnica dedicada'
    elif r0['L2'].startswith('5.5'): need='Necesita transportista (BP) + entregas de otro caso'
    elif not mats and not bps and not cust and not vend: need='Sin material/BP en Data: revisar perfil'
    else: need='Necesita dato dedicado'
    heavy = flags['produccion'] or flags['calidad']
    model = '' if need!='Necesita dato dedicado' else ('Dedicado: material + estructuras (BOM/PV/plan QM)' if heavy else ('Dedicado: material con stock' if stock else 'Dedicado: material sin stock previo'))
    types=', '.join(f'{k}' for k in sorted(mlabels)) if mlabels else ('Sin etiquetar' if mats else '')
    rows.append({'ID by unit':cid,'New ID':r0['New ID'],'L2':r0['L2'],'L3':r0['L3'],'Location by Unit':r0['Location by Unit'],'Test Scenario':str(r0['Test Scenario']).replace('\n',' ')[:150],
      'Nº pasos':len(g),'Planta principal (actual)':main,'Plantas receptoras (actual)':', '.join(recv),'Planta suministradora (actual)':', '.join(sps),
      'Sociedad derivada de planta':o['Company Code'] if o is not None else '','P.Org derivada de planta':o['Purch. Org'] if o is not None else '',
      'C.Code en Data':', '.join(sorted(ccs)),'S.Org en Data':', '.join(sorted(sos)),'P.Org en Data':', '.join(sorted(pos)),
      'Nº materiales distintos (actual)':len(mats),'Tipos de material':types,'Materiales actuales':', '.join(sorted(mats))[:200],
      'Clases doc.':', '.join(sorted(dts)),'Clases mov.':', '.join(sorted(mvs)),
      'Necesita cliente':'SÍ' if (cust or flags['venta'] or {'ZAOR','ZBRE','ZBRN'}&dts) else '',
      'Necesita proveedor':'SÍ' if (vend or flags['pedido_compra'] and {'ZPO','ZSER','ZSPO'}&dts) else '',
      'BP actuales':', '.join(sorted(bps|cust|vend))[:120],
      'Necesita stock previo':'SÍ' if stock else '','Necesita BOM/versión fabricación':'SÍ' if flags['produccion'] else '','Necesita plan/inspección QM':'SÍ' if flags['calidad'] else '',
      'Equipos/UT actuales':', '.join(sorted(eq))[:150],'Necesita ubicación WM':'SÍ' if flags['wm'] else '','Implica operador logístico':'SÍ' if lo else '','Tiene placeholders':'SÍ' if ph else '',
      'Tipo de necesidad':need,'Modelo de dato propuesto':model,'Transacciones':', '.join(sorted(set(x for x in g['_T'] if x)))[:250],
      'Confianza perfil':'Probable' if need=='Necesita dato dedicado' else 'Suposición'})
PF=pd.DataFrame(rows)
PF.to_pickle('profile.pkl')
print(PF['Tipo de necesidad'].value_counts().to_dict())
print(PF['Modelo de dato propuesto'].value_counts().to_dict())
print(pd.crosstab(PF.L2,PF['Tipo de necesidad']))
