// Un caso cada vez: qué probamos · qué buscamos · 3 pasos (plantas → datos de QS4 → guardar)
let META = {}, CASES = [], QUEUE = [], POS = 0, CUR = null, OPT = null, TYPES = new Set();
const $ = s => document.querySelector(s);
const tip = t => `<span class="info" tabindex="0" data-tip="${String(t).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;')}">ⓘ</span>`;
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const api = (u, o) => fetch(u, o).then(r => r.json());
const PLANT_KEYS = ['planta', 'planta_emisora', 'planta_receptora'];
const PLANT_LABEL = {planta: 'Planta', planta_emisora: 'Planta emisora (origen)', planta_receptora: 'Planta receptora (destino)'};
// Solo un traslado tiene origen Y destino. Una compra, una venta o un envío tienen UNA planta (las cadenas muestran sus tramos, cada uno con sus plantas).
const unaPlantaLog = c => c.stream === 'LOG' && !(c.tramos && c.tramos.length > 1) && !['ZTRA', 'ZWIA', 'ZINT', 'ZINR'].includes(c.flow);
function plantLabel(c, k) {
  if (k === 'planta' && c.stream === 'LOG') return c.flow === 'VENTA' ? 'Planta (de la que sale la venta)' : (['ZPO', 'ZSPO', 'ZSPA', 'ZSER'].includes(c.flow) ? 'Planta compradora (la que recibe)' : 'Planta');
  return PLANT_LABEL[k];
}

async function init() {
  sapPintar();
  META = await api('/api/meta');
  if (META.warnings.length) { const b = $('#banner'); b.hidden = false; b.innerHTML = META.warnings.map(esc).join('<br>'); }
  CASES = await api('/api/cases');
  fill('#f2', [...new Set(CASES.map(c => c.l2))].sort(), 'Todos los bloques (L2)');
  fillL3();
  fill('#ff', [...new Set(CASES.map(c => c.flow).filter(Boolean))].sort(), 'Todos los flujos');
  fill('#fp', [...new Set(CASES.flatMap(c => c.plants))].sort(), 'Todas las plantas');
  renderList();
  $('#main').innerHTML = '<div class="empty">Elige un caso de la lista de la izquierda.</div>';
  const id = new URLSearchParams(location.hash.slice(1)).get('caso');
  if (id) goTo(id);
}
function fill(sel, vals, first) {
  const e = $(sel), v = e.value;
  e.innerHTML = `<option value="">${first}</option>` + vals.map(x => `<option>${esc(x)}</option>`).join(''); e.value = v;
}
function fillL3() { const l2 = $('#f2').value; fill('#f3', [...new Set(CASES.filter(c => !l2 || c.l2 === l2).map(c => c.l3))].sort(), 'Todos los subbloques (L3)'); }
function onL2() { $('#f3').value = ''; fillL3(); renderList(); }
function filtered(sinEstado) {      // sinEstado: ignora el filtro de estados (para contar cuántos casos hay de cada estado con los DEMÁS filtros puestos)
  const q = $('#q').value.toLowerCase(), fs = $('#fs').value, fe = (!sinEstado && $('#fe').value ? $('#fe').value.split('|') : []), f2 = $('#f2').value, f3 = $('#f3').value, ff = $('#ff').value, fp = $('#fp').value;
  return CASES.filter(c => (!fs || c.stream === fs) && (!fe.length || fe.includes(c.status)) && (!f2 || c.l2 === f2) && (!f3 || c.l3 === f3) && (!ff || c.flow === ff) &&
    (!fp || c.plants.includes(fp)) && (!q || (c.id + ' ' + c.scenario + ' ' + c.l3 + ' ' + c.plants.join(' ')).toLowerCase().includes(q)));
}
// Filtro de estados con SELECCIÓN MÚLTIPLE: casillas dentro de un desplegable; el valor se guarda en #fe como «Estado1|Estado2».
const ESTADOS = ['Pendiente', 'En curso', 'Validado', 'Propuesto', 'Original OK', 'No requiere', 'Revisar a mano', 'Sin candidato'];
function feSel() { const v = $('#fe').value; return v ? v.split('|') : []; }
function syncFe() {
  const sel = feSel(), cnt = {};
  (typeof CASES !== 'undefined' ? filtered(true) : []).forEach(c => { cnt[c.status] = (cnt[c.status] || 0) + 1; });      // los números se recalculan con el resto de filtros (tipo, bloque, planta, búsqueda…)
  $('#febtn').textContent = sel.length ? (sel.length <= 2 ? sel.join(', ') : sel.length + ' estados') : 'Todos los estados';
  $('#febtn').title = sel.length ? sel.join(', ') : '';
  $('#fepanel').innerHTML = ESTADOS.map(e => `<label><input type="checkbox" value="${e}" ${sel.includes(e) ? 'checked' : ''} onchange="feCambio()">${e} <span class="mu">(${cnt[e] || 0})</span></label>`).join('') +
    `<div class="fe-pie"><a href="#" onclick="feTodos(false);return false">Quitar selección</a><a href="#" onclick="$('#fepanel').hidden=true;return false">Cerrar</a></div>`;
}
function feCambio() { $('#fe').value = [...document.querySelectorAll('#fepanel input:checked')].map(e => e.value).join('|'); renderList(); }
function feTodos() { $('#fe').value = ''; renderList(); }
function toggleFe(ev) { ev.stopPropagation(); const p = $('#fepanel'); p.hidden = !p.hidden; if (!p.hidden) syncFe(); }
document.addEventListener('click', e => { const p = document.getElementById('fepanel'); if (p && !p.hidden && !document.getElementById('fewrap').contains(e.target)) p.hidden = true; });

function clearFilters() { ['q', 'fs', 'fe', 'f2', 'f3', 'ff', 'fp'].forEach(k => $('#' + k).value = ''); fillL3(); renderList(); }
function renderList() {
  QUEUE = filtered();
  if (document.getElementById('fe')) { const p_ = $('#fepanel'), abierto = p_ && !p_.hidden; syncFe(); if (p_) p_.hidden = !abierto; }
  $('#count').textContent = `${QUEUE.length} de ${CASES.length} casos`;
  $('#list').innerHTML = QUEUE.map(c => `<div class="it ${CUR && CUR.id === c.id ? 'sel' : ''}" data-id="${esc(c.id)}" onclick="openCase(this.dataset.id)">
    <div class="t"><span class="tg ${c.stream}">${c.stream}</span><b>${esc(c.id)}</b>${c.flow ? `<span class="mu">${esc(c.flow)}</span>` : ''}<span class="st ${c.status.split(' ')[0]}">${esc(c.status)}</span></div>
    <div class="s">${esc(c.scenario)}</div><div class="s">${esc(c.l3)} · ${esc(c.plants.join(', ') || c.location)}</div></div>`).join('') || '<div class="empty">Sin resultados</div>';
}
function markSelected() {
  document.querySelectorAll('#list .it').forEach(e => e.classList.toggle('sel', CUR && e.dataset.id === CUR.id));
  const e = document.querySelector('#list .it.sel'); if (e) e.scrollIntoView({block: 'nearest'});
}
function goTo(id) {
  const c = CASES.find(x => x.id === id);
  if (!c) return;
  ['q', 'fs', 'fe', 'f2', 'f3', 'ff', 'fp'].forEach(k => { if (!filtered().some(x => x.id === id)) $('#' + k).value = ''; });
  fillL3(); renderList(); openCase(id);
}

// ---------- campos ----------
function stream() { return CUR.stream; }
function fieldVal(k) { const e = document.getElementById('f_' + k); return e ? e.value.trim() : ''; }
const isChain = () => !!(CUR && CUR.tramos && CUR.tramos.length > 1);
const val = id => { const e = document.getElementById(id); return e ? e.value.trim() : ''; };
function tramosVals() {
  return CUR.tramos.map((t, i) => ({kind: t.kind, proveedor: val(`t${i}_prov`), o_planta: val(`t${i}_op`).toUpperCase(), o_alm: val(`t${i}_oa`), d_planta: val(`t${i}_dp`).toUpperCase(), d_alm: val(`t${i}_da`)}));
}
function chainPlants() { return [...new Set(tramosVals().flatMap(t => [t.o_planta, t.d_planta]).filter(Boolean))]; }
function plantA() { return isChain() ? (chainPlants()[0] || '') : (fieldVal('planta_emisora') || fieldVal('planta')).toUpperCase(); }
function plant2() { return isChain() ? chainPlants().slice(1).join(',') : fieldVal('planta_receptora').toUpperCase(); }
function roleDefault(c, key) {
  const r = c.roles || {emisora: [], receptora: []};
  if (key === 'planta_emisora') return r.emisora[0] || '';
  if (key === 'planta_receptora') return r.receptora.find(p => p !== r.emisora[0]) || r.receptora[0] || '';
  if (key === 'planta') return c.plants[0] || '';
  if (key === 'alm_emisora') return (c.almacenes || {}).emisora ? c.almacenes.emisora[1] : '';
  if (key === 'alm_receptora') return (c.almacenes || {}).receptora ? c.almacenes.receptora[1] : '';
  if (key === 'proveedor') return c.proveedor || '';
  if (key === 'tipo_pedido') return (['VENTA', 'TRANSPORTE'].includes(c.flow) ? (c.docs || [])[0] : c.flow) || '';
  return '';
}
function setField(k, v, multi) {
  const e = document.getElementById('f_' + k); if (!e) return;
  if (multi && e.value) { const l = e.value.split(',').map(x => x.trim()); if (!l.includes(v)) l.push(v); e.value = l.join(', '); } else e.value = v;
}

// ---------- qué probamos / qué buscamos ----------
function probamos(c) {
  const tx = [...new Set(c.steps.map(s => s.transaction).filter(Boolean))];
  return `<b>${esc(c.scenario)}</b>${tx.length ? `<div class="mu" style="margin-top:4px">Transacciones: ${tx.map(esc).join(' → ')}</div>` : ''}`;
}
function buscamos(c) {
  if (isChain()) {
    const tv = tramosVals(), pls = chainPlants(), L = [];
    L.push(`Un mismo material para toda la cadena, dado de alta en: <b>${esc(pls.join(', ') || 'las plantas de cada tramo')}</b>`);
    L.push(tv[0].kind === 'TRASPASO' ? `Con stock libre en <b>${esc(tv[0].o_planta || 'el origen')}</b>` : 'Sin stock previo: el stock nace con la compra');
    tv.forEach((t, k) => L.push(t.kind === 'COMPRA'
      ? `Tramo ${c.tramos[k].n}: proveedor <b>${esc(t.proveedor || '?')}</b> con datos de compras y registro info del material en <b>${esc(t.d_planta || 'la planta')}</b>`
      : `Tramo ${c.tramos[k].n}: ${esc(t.o_planta || '?')} (${esc(t.o_alm || '—')}) → ${esc(t.d_planta || '?')} (${esc(t.d_alm || '—')}), un flujo que exista en ECC`));
    return L;
  }
  if (c.stream === 'PP' && c.objetivo) {
    const P = plantA() || 'la planta', T = (c.mtypes || []).join('/') || 'el tipo de material del caso';
    const base = {
      MATERIAL: [`Los materiales de la Data son los <b>modelos</b> de los que se copia: tienen que existir en <b>${esc(P)}</b>, de tipo ${esc(T)}`, 'Si alguno no existe, se sustituye por otro modelo válido', 'No hace falta lista, ruta, versión ni cost collector'],
      BOM: [`Un material de <b>${esc(P)}</b> que <b>no tenga</b> lista de materiales activa`],
      RUTA: [`Un material de <b>${esc(P)}</b> con lista de materiales y <b>sin</b> hoja de ruta tipo N`],
      VERSION: [`Un material de <b>${esc(P)}</b> con lista y hoja de ruta y <b>sin</b> versión de fabricación vigente`],
      CC: [`Un material de <b>${esc(P)}</b> con versión de fabricación y <b>sin</b> cost collector`],
      VERSIONSEL: [`Un material de <b>${esc(P)}</b> con <b>2 o más</b> versiones de fabricación vigentes, para poder cambiar la selección`],
      COSTBOM: [`Un material de <b>${esc(P)}</b> con lista de producción (uso 1) y <b>sin</b> lista de costes (uso 6)`],
      COSTRUTA: [`Un material de <b>${esc(P)}</b> con lista de costes (uso 6) y <b>sin</b> ruta de tasa (tipo R)`],
      COSTPV: [`Un material de <b>${esc(P)}</b> con lista de costes y ruta de tasa, <b>sin</b> versión de costes`],
      COSTLIB: [`Un material de <b>${esc(P)}</b> con versión de costes, lista de costes y ruta de tasa`]}[c.objetivo]
      || (c.objetivo.startsWith('PLAN:') ? [`Un producto de <b>${esc(P)}</b> con lista, ruta y versión, que lleve en su lista un componente del tipo de origen`, 'Se planifica con MD11 (tipo PE)'] : null)
      || (c.objetivo.startsWith('STAGE:') ? [`Un producto de <b>${esc(P)}</b> con lista, ruta y versión, con un componente del tipo pedido con <b>stock libre</b>`, 'Hace falta además una orden o reserva abierta (esta lectura no la mira)'] : null)
      || (c.objetivo === 'MFBF' ? [`Un producto de <b>${esc(P)}</b> completo (lista, ruta, versión, cost collector y puesto)`, 'Con <b>stock libre en todos los componentes</b> que consume'] : null)
      || (c.objetivo === 'SUBPROD' ? [`Un producto de <b>${esc(P)}</b> completo con <b>subproductos</b> en su lista de materiales`] : null)
      || (c.objetivo.startsWith('ESTADO:') ? [`Un material de <b>${esc(P)}</b> cuyo estado sea <b>${esc(c.objetivo.slice(7))}</b> (parte de ese estado)`].concat(['OK', 'PL', 'ZW'].includes(c.objetivo.slice(7)) ? ['Con datos de producción completos: el caso ejecuta MD61, MD11 y MFBF'] : []) : []);
    return (base || []).concat(['Material exclusivo de este caso']);
  }
  const A = plantA() || 'la planta origen', B = plant2() || 'la planta destino', f = c.flow;
  const trasl = [`Un material con stock libre en <b>${esc(A)}</b>`, `Ese mismo material dado de alta también en <b>${esc(B)}</b>`];
  if (c.stream === 'LOG') {
    if (f === 'ZTRA') return trasl.concat([`${esc(A)} y ${esc(B)} de la misma sociedad`]);
    if (f === 'ZWIA') return trasl.concat([`${esc(A)} y ${esc(B)} de la misma sociedad pero en distinto país`]);
    if (f === 'ZINT' || f === 'ZINR') return trasl.concat([`${esc(A)} y ${esc(B)} de sociedades distintas`, `Proveedor <b>P${esc(A)}</b> dado de alta con datos de compras`]);
    if (['ZPO', 'ZSPO', 'ZSPA'].includes(f)) return [`Un proveedor con datos de compras en la organización de compras`, `Registro info de ese proveedor con el material`, `Material dado de alta en <b>${esc(A)}</b>`];
    if (f === 'ZSER') return ['Un proveedor con datos de compras (pedido de servicios, sin stock)'];
    if (f === 'VENTA') return ['Un cliente dado de alta en la organización de ventas, sin bloqueos', `Un material vendible con stock en <b>${esc(A)}</b>`];
    if (f === 'TRANSPORTE') return ['Un punto de planificación de transporte', 'Entregas o transportista del caso'];
    return [`Un material con stock libre en <b>${esc(A)}</b>`];
  }
  return (META.checks[c.stream] || []).map(esc);
}
function renderGoal() {
  const e = $('#buscamos'); if (e) e.innerHTML = buscamos(CUR).map(x => `<li>${x}</li>`).join('');
  const r = $('#resumen'); if (r) r.innerHTML = '<b>Buscamos:</b> ' + buscamos(CUR).join(' · ');
}
function toggleFicha() { const f = $('#ficha'); f.classList.toggle('compacta'); $('#fichab').textContent = f.classList.contains('compacta') ? '▾' : '▴'; }

// ---------- pantalla del caso ----------
async function openCase(id) {
  CUR = await api('/api/case?id=' + encodeURIComponent(id)); OPT = null; TYPES = new Set(CUR.mtypes || []);
  history.replaceState(null, '', '#caso=' + encodeURIComponent(id));
  markSelected();
  const a = CUR.assignment.fields || {};
  const chosen = Object.entries(a).some(([k, v]) => v && !PLANT_KEYS.includes(k) && !['sociedad', 'org_compras', 'org_ventas', 'tipo_pedido'].includes(k));
  const conPlanta = (CUR.plants || []).length > 0 || PLANT_KEYS.some(k => a[k]);      // si ya hay planta, sale confirmada (y se puede cambiar)
  const seguir = CUR.assignment.org_ok || chosen || conPlanta || (CUR.assignment.tramos || []).length > 0;
  renderCase(seguir);
  if (seguir) loadOptions();
}

function renderCase(seguir) {
  const c = CUR, a = c.assignment.fields || {};
  const pk = c.stream === 'LOG' && !unaPlantaLog(c) ? ['planta_emisora', 'planta_receptora'] : ['planta'];
  const rest = (META.fields[c.stream] || []).filter(f => !PLANT_KEYS.includes(f.key));
  // un caso que CREA algo no necesita rellenar lo que va a crear
  const KEEP0 = ['almacen', 'material', 'componentes'];
  const KEEP = {MATERIAL: ['almacen', 'material'], BOM: ['almacen', 'material'], RUTA: ['almacen', 'material', 'lista_materiales', 'componentes'],
                VERSION: ['almacen', 'material', 'lista_materiales', 'hoja_ruta', 'componentes'], CC: ['almacen', 'material', 'version_fabricacion', 'componentes']};
  const COMPLETOS = ['PLAN', 'STAGE', 'MFBF', 'SUBPROD', 'VERSIONSEL'];
  const visibles = c.stream === 'PP' && c.objetivo && !COMPLETOS.some(p => c.objetivo.startsWith(p)) ? rest.filter(f => (KEEP[c.objetivo] || KEEP0).includes(f.key)) : rest;
  const info = c.org_info || {}, pls = Object.keys(info);
  const orgDef = k => a[k] || (c.data_org[k] || []).join(', ') || (((info[roleDefault(c, 'planta_receptora')] || info[pls[0]] || {}).fill || {})[k] || '');
  const pend = (META.pendientes || []).filter(p => c.flow && p.includes(c.flow));
  const warns = (c.avisos || []).concat(pend.map(p => 'Pendiente de definir: ' + p));
  $('#main').innerHTML = `
  <div class="card ficha compacta" id="ficha">
    <div class="fichal"><span class="tag">${esc(c.id)}</span><b>${esc(c.scenario)}</b><span class="mu">· ${esc(c.location)} · ${esc(c.status)}</span><button class="fichab" id="fichab" onclick="toggleFicha()" title="Ver / ocultar el detalle">▾</button></div>
    <div id="resumen" class="mu"></div>
    <div id="rational"></div>
    <div class="fichad">
    <div class="mu">${esc(c.l2)} › ${esc(c.l3)} · ${esc(c.location)}</div>
    <div style="margin-top:4px"><span class="tag">${esc(c.id)}</span> ${c.flow ? `<b>${esc(c.flow)}</b> · ${esc(META.flows[c.flow] || '')}` : ''} <span class="mu">· Estado: ${esc(c.status)}</span>${c.assignment.auto ? tip('Rellenado automáticamente.\n' + (c.assignment.resumen || c.assignment.note || '') + (c.assignment.hallazgo ? '\nMotivo: ' + c.assignment.hallazgo : '') + '\nRevísalo y pulsa «Validar y siguiente».') : ''}</div>
    ${warns.map(w => `<div class="msg er">${esc(w)}</div>`).join('')}
    <div class="goal">
      <div><h4>Qué probamos</h4>${probamos(c)}</div>
      <div><h4>Qué buscamos</h4><ul id="buscamos"></ul></div>
    </div>
    </div>
  </div>

  <div class="card ${seguir ? 'done' : ''}" id="s1">
    <h2><span class="num">1</span>¿Qué plantas usa? ${tip(isChain() ? 'Este caso encadena varios movimientos: cada tramo es un documento nuevo (ME21N). El destino de un tramo es el origen del siguiente.' : 'Vienen de la Data del caso. Corrígelas si no son las que quieres.')}</h2>
    <div id="s1sum" class="s1sum" hidden><span id="s1txt"></span> <a href="#" onclick="abrirS1();return false">cambiar</a></div>
    <div id="s1body">

    ${isChain() ? tramosHtml(c) : `<div class="row big-in">${pk.map((k, i) => `${i ? '<span class="arrow">→</span>' : ''}<label>${plantLabel(c, k)}<input id="f_${k}" list="plants" value="${esc(a[k] || roleDefault(c, k))}" onchange="plantsChanged()"></label>${c.stream === 'LOG' ? `<label style="max-width:110px">Almacén<input id="f_alm_${k === 'planta_emisora' ? 'emisora' : 'receptora'}" value="${esc(a['alm_' + (k === 'planta_emisora' ? 'emisora' : 'receptora')] || roleDefault(c, 'alm_' + (k === 'planta_emisora' ? 'emisora' : 'receptora')))}" onchange="loadChecks()"></label>` : ''}`).join('')}</div>`}
    <datalist id="plants">${META.plants.map(p => `<option>${p}</option>`).join('')}</datalist>
    <div id="orglines" style="margin-top:10px"></div>
    <details><summary>Cambiar sociedad y organizaciones</summary>
      <div class="grid" style="margin-top:8px">${META.org_fields.map(f => `<label>${esc(f.label)}<input id="f_${f.key}" value="${esc(orgDef(f.key))}" placeholder="Data: ${esc((c.data_org[f.key] || []).join(', ') || '—')}"></label>`).join('')}</div></details>
    <div class="bar"><button class="pri big" onclick="confirmPlants()">${seguir ? 'Plantas confirmadas ✓' : 'Confirmar plantas'}</button></div>
    </div>
  </div>

  <div class="card ${seguir ? '' : 'off'}" id="s2">
    <h2><span class="num">2</span>Elige los datos ${tip('Los datos se leen de QS4 solo cuando lo pides, en solo lectura (SE16N).')}</h2>
    <div id="qs4" style="margin-top:8px"></div>
    <div id="qs4status" style="margin:8px 0"></div>
    <div id="eccvia"></div>
    <div id="checks"></div>
    ${!isChain() && stream() === 'LOG' && ['ZPO', 'ZSPO', 'ZSPA'].includes(c.flow) ? `<details ontoggle="if(this.open)loadProvEcc()"><summary>Proveedores que compraban a esta planta en ECC</summary><div id="provecc"></div></details>` : ''}
    <div id="selbar" style="margin:8px 0"></div>
    <div id="optctl" class="bar" style="margin:6px 0;gap:8px" hidden>
      <input id="optq" placeholder="Buscar…" oninput="OPTF.q = this.value; renderOptions()" style="width:190px">
      <span id="optreq" style="display:flex;gap:6px;flex-wrap:wrap;align-items:center"></span>
      <span id="types" style="display:inline-flex;gap:6px;flex-wrap:wrap;align-items:center"></span>
      <button id="optsolo" class="chip" onclick="OPTF.solo = !OPTF.solo; renderOptions()"></button>
    </div>
    <div id="opts"></div>
    <div id="comps"></div>
    <div class="bar">
      <details style="margin:0"><summary>¿No hay datos? Probar otras plantas</summary>
        <div class="row" style="margin-top:6px"><button onclick="loadAlts('sociedad')">Misma sociedad</button><button onclick="loadAlts('todas')">Cualquier planta</button></div><div id="alts"></div></details></div>
  </div>

  <div class="card ${seguir ? '' : 'off'}" id="s3">
    <h2><span class="num">3</span>Revisa y guarda</h2>
    <details><summary><b>Valores por defecto del caso</b> <span class="mu">· los usan todos los pasos salvo los que cambies en su fila; al marcar en las listas de arriba se rellenan aquí</span></summary><div style="margin-top:8px;max-width:760px">
        ${c.stream === 'LOG' && !isChain() ? s3Log(c, a) : ''}
        <div class="grid1" ${c.stream === 'LOG' && !isChain() ? 'hidden' : ''}>${visibles.filter(f => !['alm_emisora', 'alm_receptora'].includes(f.key) && !(c.stream === 'LOG' && !isChain() && f.key !== 'almacen')).map(f => `<label>${esc(f.label)}<input id="f_${f.key}" value="${esc(a[f.key] || (f.key === 'material' && c.stream === 'PP' && c.objetivo === 'MATERIAL' ? (c.data_materials || []).join(', ') : roleDefault(c, f.key)))}" onchange="loadChecks()"></label>`).join('')}</div>
        <details><summary>Notas</summary><input id="note" value="${esc(c.assignment.note || '')}" style="margin-top:6px"></details></div></details>
    <h4 class="sub" style="margin:14px 0 6px">Pasos: datos de cada uno y cómo quedan en el Excel ${tip('En cada fila: a la izquierda los datos de ESE paso (formulario), en el centro la Data original del Excel y a la derecha la propuesta, que se calcula sola desde el formulario.')}</h4>
    <div id="antesprop"></div>
    <div id="saveres"></div>
  </div>
  <div class="stickybar ${seguir ? '' : 'off'}" id="actbar">
    <button class="pri big" onclick="save('Validado', true)">Validar y siguiente ›</button>
    <button onclick="save('En curso')">Guardar</button>
    <button onclick="save('Sin candidato', true)">No hay candidato</button>
    <span class="mu">${esc(c.id)}</span>
  </div>`;
  OPTF = {q: '', todos: false, sort: null, req: {}};
  if (seguir) colapsarS1();
  EDITS = Object.assign({}, (c.assignment || {}).edits || {}); AUTO = (c.proposal || []).slice();
  renderGoal();
  renderOrgLines();
  renderEccVia();
  PC = JSON.parse(JSON.stringify((CUR.assignment || {}).pasos_campos || {})); window.FORM_REDIBUJAR = false;
  renderFormPasos();
  renderRational();
  pintarAntesProp();
  if (isChain()) refreshTramos(); else loadChecks();
}

// «Datos elegidos» de logística: los mismos campos que la Data (organización de compras, sociedad, grupo de compras, plantas, almacén destino, tipo de pedido, material).
// Los marcados «espejo» viven en el paso 1 (f_<clave>): aquí se editan y se copian allí, y al revés.
function s3Log(c, a) {
  let L;
  if (c.flow === 'VENTA' && !isChain()) {
    L = [['org_ventas', 'Sales organization', 1], ['sociedad', 'Company code', 1], ['planta', 'Plant', 1], ['tipo_pedido', 'Order type', 0], ['cliente', 'Customer', 0]];
  } else if (['ZPO', 'ZSPO', 'ZSPA', 'ZSER'].includes(c.flow) && !isChain()) {
    L = [['org_compras', 'Purchase organization', 1], ['sociedad', 'Company code', 1], ['grupo_compras', 'Purchasing group', 0], ['planta', 'Plant', 1]];
    if (['ZPO', 'ZSPO'].includes(c.flow)) L.push(['proveedor', 'Vendor', 0]);
    L.push(['alm_receptora', 'Storage location', 1], ['tipo_pedido', 'Order type', 0]);
  } else if (unaPlantaLog(c)) {
    L = [['sociedad', 'Company code', 1], ['planta', 'Plant', 1]];
    if (c.flow === 'TRANSPORTE') L.push(['punto_expedicion', 'Punto de expedición', 0], ['punto_transporte', 'Pto. planif. transporte', 0], ['transportista', 'Transportista', 0]);
  } else {
    L = [['org_compras', 'Purchase organization', 1], ['sociedad', 'Company code', 1], ['grupo_compras', 'Purchasing group', 0], ['planta_emisora', 'Supplier plant', 1],
         ['planta_receptora', 'Destination plant', 1], ['alm_receptora', 'Destination storage location', 1], ['tipo_pedido', 'Order type', 0]];
  }
  const ocultos = ['proveedor', 'cliente', 'punto_expedicion', 'punto_transporte', 'transportista'].filter(k => !L.some(x => x[0] === k));
  const campo = ([k, lab, esp]) => esp
    ? `<label>${lab}<input data-mirror="${k}" onchange="mirrorSet('${k}', this.value)"></label>`
    : `<label>${lab}<input id="f_${k}" value="${esc(a[k] || roleDefault(c, k))}" onchange="loadChecks()"></label>`;
  return `<div class="grid1">${L.map(campo).join('')}
    <label style="grid-column:1/-1">Material <span class="mu">(uno o varios, separados por coma: al pulsar filas de la lista se van añadiendo o quitando)</span><input id="f_material" value="${esc(a.material || '')}" placeholder="Data: ${esc((c.data_materials || []).join(', ') || '—')}" onchange="loadChecks()"></label></div>
    ${ocultos.map(k => `<input type="hidden" id="f_${k}" value="${esc(a[k] || roleDefault(c, k))}">`).join('')}`;
}
function syncMirror() {
  document.querySelectorAll('[data-mirror]').forEach(e => {
    const r = document.getElementById('f_' + e.dataset.mirror);
    if (r && document.activeElement !== e) e.value = r.value;
  });
}
function mirrorSet(k, v) {
  const r = document.getElementById('f_' + k); if (!r) return;
  r.value = k.startsWith('planta') ? v.toUpperCase() : v;
  if (k.startsWith('planta')) plantsChanged(); else loadChecks();
}

function renderEccVia() {      // antecedentes en ECC (sistema actual) del caso, con sugerencias que se aplican con un clic
  const box = $('#eccvia');
  if (!box) return;
  const v = CUR && CUR.ecc_via;
  if (!v || isChain()) { box.innerHTML = ''; return; }
  const ico = v.estado === 'ok' ? '<span style="color:var(--ok)">✓</span>' : '<span style="color:#b7791f">△</span>';
  box.innerHTML = `<div style="margin:8px 0;padding:8px 10px;background:#f6f8fb;border:1px solid var(--line);border-radius:8px"><b>Antecedentes en ECC</b> ${tip('Contraste con el listado de pedidos reales de ECC (el sistema actual). No es obligatorio: un flujo nuevo de S/4 puede no existir en ECC.')}<div>${ico} ${esc(v.texto)}</div>` +
    ((v.sugerencias || []).length ? `<div style="margin-top:6px" class="mu">Sugerencias (se aplican al pulsar):</div><div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:4px">${v.sugerencias.map(x => `<button class="chip" onclick="usaEcc('${x.campo}','${esc(x.valor)}')">Usar ${esc(x.texto)}</button>`).join('')}</div>` : '') + '</div>';
}
function usaEcc(campo, valor) {
  setField(campo, valor);
  if (campo.startsWith('planta')) plantsChanged(); else loadChecks();
  syncMirror(); toast(`${valor} puesto en «${campo === 'planta_emisora' ? 'Planta emisora' : 'Proveedor'}»: pulsa «Confirmar plantas» / mira la propuesta`);
}

// Formulario de los pasos: los campos que cada transacción necesita según el modelo (config/transacciones_modelo.xlsx) y no están ya arriba, para rellenarlos aquí.
// ---------- FORMULARIO POR PASO ----------
// Cada paso tiene su bloque: los campos que pide su transacción (modelo) + los que le añadas o quites, con valores propios. Lo que no tocas sigue lo de «Datos elegidos».
let PC = {};      // campos añadidos / quitados por paso: {idx: {add: [], quitar: []}}
function extrasVals() { return (CUR && CUR.assignment && CUR.assignment.extras) || {}; }      // los extras antiguos (por caso) se conservan tal cual
function pasosVals() {
  const o = {};
  document.querySelectorAll('input.pxtra').forEach(e => {
    const v = e.value.trim();
    if (v && v !== (e.dataset.auto || '')) { (o[e.dataset.i] = o[e.dataset.i] || {})[e.dataset.clave] = v; }      // solo lo que es distinto de lo automático
  });
  return o;
}
function pasoCambio(e) {
  e.dataset.ed = (e.value.trim() && e.value.trim() !== (e.dataset.auto || '')) ? '1' : '0';
  e.style.background = e.dataset.ed === '1' ? '#fff7e0' : '';
  delete EDITS[e.dataset.i];      // el formulario manda: se descarta la edición a mano del texto de ese paso
  refreshProposal();
}
function aplicaTodos(clave, i) {
  const src = document.querySelector(`input.pxtra[data-i="${i}"][data-clave="${clave}"]`);
  if (!src) return;
  let n = 0;
  document.querySelectorAll(`input.pxtra[data-clave="${clave}"]`).forEach(e => { e.value = src.value; e.dataset.ed = (e.value.trim() && e.value.trim() !== (e.dataset.auto || '')) ? '1' : '0'; e.style.background = e.dataset.ed === '1' ? '#fff7e0' : ''; delete EDITS[e.dataset.i]; n++; });
  refreshProposal(); toast(`«${src.value || 'vacío'}» aplicado a ${n} pasos`);
}
function quitaCampo(i, clave) {
  const p = PC[i] = PC[i] || {add: [], quitar: []};
  if ((p.add || []).includes(clave)) p.add = p.add.filter(x => x !== clave); else p.quitar = [...new Set([...(p.quitar || []), clave])];
  window.FORM_REDIBUJAR = true; refreshProposal();
}
function addCampo(i, sel) {
  const clave = sel.value; if (!clave) return;
  const p = PC[i] = PC[i] || {add: [], quitar: []};
  p.quitar = (p.quitar || []).filter(x => x !== clave);
  if (!(p.add || []).includes(clave)) p.add = [...(p.add || []), clave];
  window.FORM_REDIBUJAR = true; refreshProposal();
}
function resetEditsTodos() { EDITS = {}; refreshProposal(); toast('Los textos de los pasos vuelven a seguir el formulario'); }
function renderFormPasos() {
  if (!CUR) return;
  const F = CUR.form || {pasos: [], catalogo: []};
  (F.pasos || []).forEach(p => {
    const box = document.getElementById('sf' + p.idx);
    if (!box) return;
    if (!p.en_modelo) { box.innerHTML = '<div class="mu">Este paso trae «Prev.Data» en el Excel: no mete datos propios.</div>'; return; }
    const usados = new Set(p.items.map(it => it.clave));
    const inp = it => `<label class="pf"><span class="pf-l">${esc(it.etiqueta)}${it.opc ? ' <i>(opc.)</i>' : ''}<a class="pf-a" title="Aplicar este valor a todos los pasos que tienen este campo" onclick="aplicaTodos('${it.clave}', ${p.idx})">⇉</a><a class="pf-a" title="Quitar este campo de este paso" onclick="quitaCampo(${p.idx}, '${it.clave}')">✕</a></span>` +
      `<input class="pxtra" data-i="${p.idx}" data-clave="${esc(it.clave)}" data-auto="${esc(it.auto || '')}" data-ed="${it.editado ? 1 : 0}" value="${esc(it.valor || '')}" placeholder="XXXX" style="${it.editado ? 'background:#fff7e0' : ''}" oninput="pasoCambio(this)"></label>`;
    box.innerHTML = (!p.modelo && !p.activo ? '<div class="mu" style="margin-bottom:6px;font-size:12px">Este paso no está en el libro (o trae «Prev.Data» en el Excel): el texto sigue siendo el del Excel hasta que cambies o añadas un campo.</div>' : '') +
      (p.items.length ? `<div class="pasof-g" style="margin-top:0">${p.items.map(inp).join('')}</div>` : '<div class="mu">Este paso no lleva datos.</div>') +
      `<div class="pasof-f"><select onchange="addCampo(${p.idx}, this)"><option value="">＋ añadir campo a este paso…</option>${(F.catalogo || []).filter(c => !usados.has(c.clave)).map(c => `<option value="${esc(c.clave)}">${esc(c.etiqueta)}</option>`).join('')}</select></div>`;
  });
}
function actualizaFormPasos() {      // tras recalcular: los campos que no has tocado se ponen al día; los tuyos se respetan
  const F = CUR.form || {pasos: []};
  (F.pasos || []).forEach(p => (p.items || []).forEach(it => {
    const e = document.querySelector(`input.pxtra[data-i="${p.idx}"][data-clave="${it.clave}"]`);
    if (!e) return;
    e.dataset.auto = it.auto || '';
    if (e.dataset.ed !== '1' && document.activeElement !== e) e.value = it.valor || '';
  }));
}

// EL RATIONAL: el motivo por el que se propone cada material (y por qué se descarta el original). Arriba, en la ficha del caso; desplegable, comprimido por defecto.
function renderRational() {
  const box = $('#rational');
  if (!box || !CUR) return;
  const R = CUR.rational;
  if (!R) { box.innerHTML = ''; return; }
  const M = R.materiales || [];
  const val = M.filter(m => m.valido === true && m.papel !== 'Original descartado'), malos = M.filter(m => m.valido === false && m.papel !== 'Original descartado'), desc = M.filter(m => m.papel === 'Original descartado');
  const ico = m => m.valido === true ? '<span style="color:var(--ok)">✓</span>' : (m.valido === false ? '<span style="color:var(--er)">✗</span>' : '<span class="mu">?</span>');
  const fila = m => `<tr style="${m.papel === 'Original descartado' ? 'opacity:.75' : ''}"><td>${ico(m)} <b>${esc(m.material)}</b>${m.tipo ? ` <span class="mu">${esc(m.tipo)}</span>` : ''}</td><td>${esc(m.papel)}</td><td>${esc(m.motivo)}</td><td>${m.stock !== '' && m.stock !== undefined ? esc(Number(m.stock).toLocaleString('es-ES')) : ''}</td><td>${esc(m.ecc || '')}</td><td>${m.reservado ? `<span style="color:var(--er)">${esc(m.reservado)}</span>` : ''}</td></tr>`;
  const P = R.proveedor;
  const resumen = M.length ? `${R.estado} · <span style="color:var(--ok)">✓ ${val.length}</span>` + (malos.length ? ` · <span style="color:var(--er)">✗ ${malos.length}</span>` : '') + (desc.length ? ` · ${desc.length} original(es) descartado(s)` : '') : R.estado;
  const cuerpo = (M.length ? `<div class="tw"><table><thead><tr><th>Material</th><th>Papel</th><th>Por qué</th><th>Stock libre</th><th>En ECC</th><th>Reservado por</th></tr></thead><tbody>${M.map(fila).join('')}</tbody></table></div>` : '<div class="mu">El caso no trae materiales en su Data ni se ha elegido ninguno.</div>') +
    (P ? `<div style="margin:6px 0">${P.valido ? '<span style="color:var(--ok)">✓</span>' : '<span style="color:var(--er)">✗</span>'} <b>Proveedor ${esc(P.proveedor)}:</b> ${esc(P.motivo)}${P.registros_info !== '' ? ` · registro info ${esc(P.registros_info)}` : ''}${P.ecc ? ` · en ECC ${esc(P.ecc)}` : ''}</div>` : '') +
    (R.resumen ? `<div style="margin:6px 0"><b>Qué cambia:</b> ${esc(R.resumen)}</div>` : '') +
    (R.notas || []).map(n => `<div style="margin:3px 0" class="mu">${esc(n)}</div>`).join('') +
    ((CUR.ecc_via && CUR.ecc_via.texto) ? `<div style="margin:3px 0" class="mu"><b>ECC:</b> ${esc(CUR.ecc_via.texto)}</div>` : '') +
    ((CUR.avisos || []).map(w => `<div style="margin:3px 0" class="mu"><b>Aviso:</b> ${esc(w)}</div>`).join(''));
  box.innerHTML = `<details style="margin:6px 0 2px"><summary><b>Rationale</b> <span class="mu">· por qué se propone esto</span> <span style="margin-left:8px">${resumen}</span></summary><div style="margin-top:6px;padding:8px 10px;background:#f6f8fb;border:1px solid var(--line);border-radius:8px;font-size:13px">${cuerpo}</div></details>`;
}

function tramosHtml(c) {
  return '<div id="tramos">' + c.tramos.map((t, i) => `<div class="tramo">
    <div><b>Tramo ${t.n} · ${t.kind === 'COMPRA' ? 'Compra' : 'Traspaso'}</b> <span class="mu">${esc(t.title)} · pasos ${t.steps[0] + 1}–${t.steps[t.steps.length - 1] + 1}</span> <span id="tdoc${i}" class="tag"></span></div>
    <div class="row big-in" style="margin-top:6px">
      ${t.kind === 'COMPRA'
        ? `<label>Proveedor<input id="t${i}_prov" value="${esc(t.proveedor)}" onchange="tramoChanged(${i})"></label>`
        : `<label>Origen: planta<input id="t${i}_op" list="plants" value="${esc(t.o_planta)}" onchange="tramoChanged(${i})"></label><label style="max-width:110px">Almacén<input id="t${i}_oa" value="${esc(t.o_alm)}" onchange="tramoChanged(${i})"></label>`}
      <span class="arrow">→</span>
      <label>Destino: planta<input id="t${i}_dp" list="plants" value="${esc(t.d_planta)}" onchange="tramoChanged(${i})"></label>
      <label style="max-width:110px">Almacén<input id="t${i}_da" value="${esc(t.d_alm)}" onchange="tramoChanged(${i})"></label>
    </div>
    <div id="tecc${i}" class="mu" style="margin-top:4px"></div>
    ${t.kind === 'TRASPASO' ? `<details ontoggle="if(this.open)loadDestinos(${i})"><summary>Destinos usados en ECC desde este origen</summary><div id="tdest${i}"></div></details>`
      : `<details ontoggle="if(this.open)loadProveedores(${i})"><summary>Proveedores que compraban a esta planta y almacén en ECC</summary><div id="tprov${i}"></div></details>`}
  </div>`).join('') + '</div>';
}
const fmtFecha = f => f ? `${f.slice(6, 8)}/${f.slice(4, 6)}/${f.slice(0, 4)}` : '—';
function eccBadge(t, e) {
  if (!e) return '';
  if (t.kind === 'COMPRA') return e.existe ? `✓ En ECC este proveedor compraba a esa planta: ${e.docs} documentos, el último el ${fmtFecha(e.ultimo)}`
    : `✗ En ECC no hay compras de ese proveedor a esa planta/almacén${e.proveedor_en_planta ? ' (sí con otro almacén)' : ''}`;
  return e.existe ? `✓ Este traspaso existía en ECC: ${e.docs} documentos (${e.tipo}), el último el ${fmtFecha(e.ultimo)}${e.almacenes_exactos ? '' : ' · almacén sin confirmar en ECC'}`
    : `✗ Este traspaso no existía en ECC${e.mismo_par_plantas ? ' (el par de plantas sí, con otros almacenes)' : ''}. Mira "Destinos usados en ECC".`;
}
async function refreshTramos() {
  refreshProposal();
  const tv = tramosVals();
  await Promise.all(tv.map(async (t, i) => {
    if (!(t.d_planta && (t.kind === 'COMPRA' ? t.proveedor : t.o_planta))) { $('#tecc' + i).textContent = 'Completa el tramo para comprobarlo en ECC.'; $('#tdoc' + i).textContent = ''; return; }
    const q = new URLSearchParams({kind: t.kind, proveedor: t.proveedor, o_planta: t.o_planta, o_alm: t.o_alm, d_planta: t.d_planta, d_alm: t.d_alm});
    const r = await api('/api/ecc/tramo?' + q);
    const el = $('#tecc' + i);
    if (!el) return;
    el.innerHTML = r.error ? esc(r.error) : esc(eccBadge(t, r.ecc));
    el.style.color = r.ecc && r.ecc.existe ? 'var(--ok)' : (r.ecc ? 'var(--er)' : '');
    const d = $('#tdoc' + i); if (d) { d.textContent = r.doc ? 'Doc ' + r.doc : ''; d.style.background = r.doc ? '#1f5fbf' : ''; }
  }));
}
async function tramoChanged(i) {
  const n = CUR.tramos[i + 1];
  if (n && n.kind === 'TRASPASO') { const a = $(`#t${i + 1}_op`), b = $(`#t${i + 1}_oa`); if (a) a.value = val(`t${i}_dp`); if (b) b.value = val(`t${i}_da`); }
  renderGoal(); renderOrgLines(); await refreshTramos();
  if (!$('#s2').classList.contains('off')) loadOptions();
}
async function loadDestinos(i) {
  const o = val(`t${i}_op`).toUpperCase(), a = val(`t${i}_oa`);
  const r = await api(`/api/ecc/destinos?plant=${o}&alm=${a}`);
  $('#tdest' + i).innerHTML = (r.items || []).length ? `<div class="tw"><table><thead><tr><th>Destino</th><th>Almacén</th><th>Clase</th><th>Documentos</th><th>Último</th><th></th></tr></thead><tbody>${r.items.map(x =>
    `<tr><td><b>${x.planta}</b></td><td>${esc(x.alm || '—')}</td><td>${x.tipo}</td><td>${x.docs}</td><td>${fmtFecha(x.ultimo)}</td><td><button onclick="useDestino(${i},'${x.planta}','${x.alm}')">Usar</button></td></tr>`).join('')}</tbody></table></div>`
    : `<div class="mu">En ECC no salía ningún traspaso desde ${esc(o)}${a ? ' / ' + esc(a) : ''}.</div>`;
}
function useDestino(i, pl, alm) { $(`#t${i}_dp`).value = pl; $(`#t${i}_da`).value = alm; tramoChanged(i); }
async function loadProveedores(i) {
  const r = await api(`/api/ecc/proveedores?plant=${val(`t${i}_dp`).toUpperCase()}&alm=${val(`t${i}_da`)}`);
  $('#tprov' + i).innerHTML = (r.items || []).length ? `<div class="tw"><table><thead><tr><th>Proveedor</th><th>Documentos</th><th>Último</th><th></th></tr></thead><tbody>${r.items.map(x =>
    `<tr><td><b>${x.proveedor}</b></td><td>${x.docs}</td><td>${fmtFecha(x.ultimo)}</td><td><button onclick="$('#t${i}_prov').value='${x.proveedor}';tramoChanged(${i})">Usar</button></td></tr>`).join('')}</tbody></table></div>`
    : '<div class="mu">En ECC no hay compras a esa planta/almacén.</div>';
}

async function loadProvEcc() {
  const r = await api(`/api/ecc/proveedores?plant=${fieldVal('planta_receptora').toUpperCase() || plantA()}&alm=${fieldVal('alm_receptora')}`);
  $('#provecc').innerHTML = (r.items || []).length ? `<div class="tw"><table><thead><tr><th>Proveedor</th><th>Documentos</th><th>Último</th><th></th></tr></thead><tbody>${r.items.map(x =>
    `<tr><td><b>${x.proveedor}</b></td><td>${x.docs}</td><td>${fmtFecha(x.ultimo)}</td><td><button onclick="document.getElementById('f_proveedor').value='${x.proveedor}';dirty();loadChecks()">Usar</button></td></tr>`).join('')}</tbody></table></div>`
    : '<div class="mu">En ECC no hay compras a esa planta/almacén.</div>';
}
let EDITS = {}, AUTO = [];
function pintarAntesProp(forzar) {
  const box = $('#antesprop');
  if (!box || !CUR) return;
  const estado = (i) => { const s = CUR.steps[i], ed = EDITS[String(i)] !== undefined, val = ed ? EDITS[String(i)] : (AUTO[i] || ''); return {s, ed, val, cambia: val !== s.data}; };
  if (!forzar && box.dataset.cid === CUR.id && box.dataset.n === String(CUR.steps.length)) {      // ya pintado: solo se actualizan los textos y las marcas
    CUR.steps.forEach((_, i) => {
      const {ed, val, cambia} = estado(i), ta = $('#prop' + i), bd = $('#bd' + i);
      if (ta && document.activeElement !== ta) ta.value = val;
      if (ta) { ta.style.background = ed ? '#fff7e0' : (cambia ? '#eaf7ef' : '#fff'); ta.rows = Math.min(12, Math.max(3, val.split('\n').length + 1)); }
      if (bd) bd.innerHTML = badge(i, ed, cambia);
    });
    return;
  }
  box.dataset.cid = CUR.id; box.dataset.n = String(CUR.steps.length);
  box.innerHTML = `<div class="steprow hdr"><div class="mu" style="font-size:11px;letter-spacing:.04em">DATOS DEL PASO <a href="#" style="font-weight:400;margin-left:6px" onclick="resetEditsTodos();return false" title="Descarta los textos editados a mano para que sigan el formulario">restablecer textos editados a mano</a></div>
      <div class="cols2 mu" style="font-size:11px;letter-spacing:.04em"><span>ANTES (Excel)</span><span>PROPUESTA · editable</span></div></div>` + CUR.steps.map((_, i) => {
    const {s, ed, val, cambia} = estado(i);
    return `<div class="steprow"><div class="stepform" id="sf${i}"></div><div>
      <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:4px"><b>Paso ${s.n}</b><span class="pill">${esc(s.transaction)}</span>${prevDataTag(s.data)}${(s.extra || {})['Test Step Description'] ? `<span style="font-size:13px">${esc(s.extra['Test Step Description'])}</span>` : ''}${(s.extra || {})['Expected result'] ? tip('Resultado esperado:\n' + s.extra['Expected result']) : ''}<span id="bd${i}" style="margin-left:auto">${badge(i, ed, cambia)}</span></div>
      <div class="cols2"><pre>${esc(s.data) || '—'}</pre>
      <textarea id="prop${i}" rows="${Math.min(12, Math.max(3, val.split('\n').length + 1))}" oninput="editProp(${i}, this.value)" style="width:100%;font:12.5px/1.4 Consolas,monospace;border:1px solid var(--line);border-radius:6px;padding:6px 8px;background:${ed ? '#fff7e0' : (cambia ? '#eaf7ef' : '#fff')}">${esc(val)}</textarea></div></div></div>`;
  }).join('');
  renderFormPasos();
}
function prevDataTag(data) {      // paso de chequeo: no mete datos, usa los generados en pasos anteriores
  const m = /^\s*prev\.?\s*data\b((?:\s*\([^)]*\))*)/i.exec(String(data || ''));
  if (!m) return '';
  const d = [...m[1].matchAll(/\(([^)]*)\)/g)].map(x => x[1].trim()).filter(Boolean).join(', ');
  return `<span class="pill" style="background:#e8f0fe;color:#1a4fa0" title="Check step: it enters no data, it uses the transactional data generated in previous steps${d ? ' (' + d + ')' : ''}">Prev.Data${d ? ' · ' + esc(d) : ''}</span>`;
}
function badge(i, ed, cambia) {
  return ed ? `<span class="ic am" title="Editado a mano: este texto es el que irá al Excel">✎</span> <a href="#" class="ic mu" title="Volver a la propuesta automática" onclick="resetEdit(${i});return false">↺</a>`
    : (cambia ? '<span class="ic ok" title="La propuesta cambia la Data del Excel">✎</span>' : '<span class="ic mu" title="Igual que el Excel: sin cambios">＝</span>');
}
function editProp(i, v) {
  if (v === (AUTO[i] || '')) delete EDITS[String(i)]; else EDITS[String(i)] = v;
  const ed = EDITS[String(i)] !== undefined, ta = $('#prop' + i);
  if (ta) ta.style.background = ed ? '#fff7e0' : '';
  const bd = $('#bd' + i); if (bd) bd.innerHTML = badge(i, ed, v !== CUR.steps[i].data);
}
function resetEdit(i) { delete EDITS[String(i)]; pintarAntesProp(); }
let PROPTIMER = null;
function refreshProposal() {
  clearTimeout(PROPTIMER);
  PROPTIMER = setTimeout(async () => {
    if (!CUR) return;
    const fields = {};
    (META.fields[stream()] || []).concat(META.org_fields).forEach(f => fields[f.key] = fieldVal(f.key));
    if (isChain()) { const cp = chainPlants(); fields.planta_emisora = cp[0] || ''; fields.planta_receptora = cp[cp.length - 1] || ''; }
    const r = await api('/api/proposal', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({id: CUR.id, fields, tramos: isChain() ? tramosVals() : [], extras: extrasVals(), pasos: pasosVals(), pasos_campos: PC})});
    if (r.form) { CUR.form = r.form; if (window.FORM_REDIBUJAR) { window.FORM_REDIBUJAR = false; renderFormPasos(); } else actualizaFormPasos(); }
    if (r.proposal) {
      const viejo = AUTO; AUTO = r.proposal;
      Object.keys(EDITS).forEach(k => { if (EDITS[k] === (AUTO[+k] || '')) delete EDITS[k]; });
      const aviso = Object.keys(EDITS).filter(k => (viejo[+k] || '') !== (AUTO[+k] || ''));
      pintarAntesProp();
      if (aviso.length && $('#antesprop')) $('#antesprop').insertAdjacentHTML('afterbegin', `<div class="msg er">Los datos han cambiado y has editado a mano el paso ${aviso.map(k => +k + 1).join(', ')}: revisa tu edición (o pulsa «restablecer»).</div>`);
    }
  }, 350);
}
let COMPTIMER = null;
function loadComps() {
  clearTimeout(COMPTIMER);
  COMPTIMER = setTimeout(async () => {
    const box = $('#comps');
    if (!box || !CUR || stream() !== 'PP' || ['MATERIAL', 'BOM'].includes(CUR.objetivo)) return;
    const mats = fieldVal('material').split(/[,;\s]+/).filter(Boolean).slice(0, 3);
    if (!mats.length || !plantA()) { box.innerHTML = ''; return; }
    const r = await api(`/api/componentes?plant=${encodeURIComponent(plantA())}&material=${mats.join(',')}`);
    const comp = new Set(fieldVal('componentes').split(',').map(x => x.trim()).filter(Boolean));
    box.innerHTML = (r.grupos || []).map((g, gi) => {
      if (!g.tiene_lista) return `<div class="mu" style="margin:8px 0">${esc(g.material)} no tiene lista de materiales en ${esc(plantA())}.</div>`;
      if (!g.rows.length) return `<div class="mu" style="margin:8px 0">${esc(g.material)}: ${r.hay_stpo ? 'la lista no tiene componentes' : 'faltan los componentes (STPO): abre «QS4» y consúltalos'}.</div>`;
      const sin = g.rows.filter(x => !(x['Stock libre'] > 0)).length;
      return `<details ${gi === 0 ? 'open' : ''} style="margin:10px 0"><summary><b>Componentes de ${esc(g.material)}</b> <span class="mu">${esc(g.descripcion || '')} · ${g.rows.length}${sin ? ` · <span style="color:var(--er)">${sin} sin stock</span>` : ''}</span>${tip('Componentes de la lista de materiales de uso 1 de este material, con la cantidad y el stock libre en la planta. Pulsa una fila para añadirla a «Componentes» (otra vez, para quitarla).')}</summary><div class="tw"><table><thead><tr><th>Componente</th><th>Descripción</th><th>Tipo</th><th>Cantidad</th><th>Stock libre</th><th>Coprod.</th></tr></thead><tbody>${g.rows.map(x => `<tr class="pick ${comp.has(x.Componente) ? 'sel' : ''}" onclick="addComp('${esc(x.Componente)}')"><td>${esc(x.Componente)}</td><td>${esc(x['Descripción'])}</td><td>${esc(x.Tipo)}</td><td>${esc(x.Cantidad)}</td><td class="${x['Stock libre'] > 0 ? '' : 'bad'}">${(+x['Stock libre'] || 0).toLocaleString('es-ES')}</td><td>${esc(x.Coproducto)}</td></tr>`).join('')}</tbody></table></div></details>`;
    }).join('');
  }, 250);
}
function addComp(c) {
  const lista = fieldVal('componentes').split(',').map(x => x.trim()).filter(Boolean), i = lista.indexOf(c);
  if (i >= 0) lista.splice(i, 1); else lista.push(c);
  const e = document.getElementById('f_componentes'); if (e) e.value = lista.join(', ');
  loadChecks(); toast(i >= 0 ? `Componente ${c} quitado` : `Componente ${c} añadido`);
}
async function loadChecks() {
  syncMirror();
  refreshProposal();
  loadComps();
  const box = $('#checks');
  if (!box) return;
  if (isChain() || stream() !== 'LOG') { box.innerHTML = ''; return; }
  const q = new URLSearchParams({id: CUR.id});
  ['planta', 'planta_emisora', 'planta_receptora', 'alm_emisora', 'alm_receptora', 'proveedor', 'material'].forEach(k => q.set(k, fieldVal(k)));
  const r = await api('/api/check?' + q);
  const ic = (ok, des) => ok === true ? '<span style="color:var(--ok)">✓</span>' : (ok === false ? (des ? '<span style="color:#b7791f" title="Deseable, no obligatorio">△</span>' : '<span style="color:var(--er)">✗</span>') : '<span class="mu">?</span>');
  // «Comprobación del flujo»: desplegable, comprimido por defecto; el resumen enseña de un vistazo cuántas comprobaciones están bien, mal, sin datos o son avisos
  const nOk = r.checks.filter(c => c.ok === true).length, nKo = r.checks.filter(c => c.ok === false && !c.deseable).length,
        nAv = r.checks.filter(c => c.ok === false && c.deseable).length, nDu = r.checks.filter(c => c.ok === null || c.ok === undefined).length;
  const resumen = `<span style="color:var(--ok)">✓ ${nOk}</span>` + (nKo ? ` · <span style="color:var(--er);font-weight:600">✗ ${nKo}</span>` : '') + (nDu ? ` · <span class="mu">? ${nDu}</span>` : '') + (nAv ? ` · <span style="color:#b7791f">△ ${nAv}</span>` : '');
  box.innerHTML = r.checks.length ? `<details style="margin:8px 0" ${window.CHK_ABIERTO ? 'open' : ''} ontoggle="window.CHK_ABIERTO = this.open"><summary><b>Comprobación del flujo</b> <span style="margin-left:8px">${resumen}</span></summary><div style="margin-top:6px">${r.checks.map(c => `<div>${ic(c.ok, c.deseable)} ${esc(c.req)}${c.detalle ? ` <span class="mu">· ${esc(c.detalle)}</span>` : ''}</div>`).join('')}</div></details>` : '';
}

async function renderOrgLines() {
  const pls = [plantA(), plant2()].filter((x, i, l) => x && l.indexOf(x) === i);
  const box = $('#orglines');
  if (!box) return;
  if (!pls.length) { box.innerHTML = '<div class="msg er">El caso no cita ninguna planta conocida: escribe una arriba.</div>'; return; }
  const r = await api('/api/org?plants=' + pls.join(','));
  let h = pls.map(p => {
    const o = r[p] || {};
    if (!o.sociedad && !o.nombre) return `<div class="msg er"><b>${p}</b>: planta desconocida (no está en Org.Structure ni en QS4).</div>`;
    return `<div><b>${p}</b> ${esc(o.nombre)} · Sociedad <b>${esc(o.sociedad)}</b> · Org. compras <b>${esc(o.org_compras || '—')}</b>
      ${o.en_qs4 === false ? '<span class="tag" style="background:#c0392b">no existe en QS4</span>' : ''}</div>`;
  }).join('');
  const soc = new Set(pls.map(p => (r[p] || {}).sociedad).filter(Boolean)), d = CUR.data_org;
  if (d.sociedad.length && soc.size && !d.sociedad.some(x => soc.has(x))) h += `<div class="msg er">El C.Code de la Data (${esc(d.sociedad.join(', '))}) no coincide con la sociedad de las plantas (${esc([...soc].join(', '))}).</div>`;
  box.innerHTML = h;
}
async function plantsChanged() {
  renderGoal(); renderOrgLines(); loadChecks();
  const pl = plantA();
  if (pl) { const r = await api('/api/org?plants=' + (plant2() ? pl + ',' + plant2() : pl)); const o = r[plant2() || pl] || {}; Object.entries(o.fill || {}).forEach(([k, v]) => v && setField(k, v)); syncMirror(); refreshProposal(); }
  if (!$('#s2').classList.contains('off')) loadOptions();
}
let OPTF = {q: '', todos: false, sort: null, req: {}};
function toast(msg, er) {
  const t = $('#toast'); if (!t) return;
  t.textContent = msg; t.className = 'on' + (er ? ' er' : '');
  clearTimeout(window.TOASTT); window.TOASTT = setTimeout(() => { t.className = ''; }, er ? 4500 : 2600);
}
function colapsarS1() {
  if (!plantA() && !(isChain() && chainPlants().length)) return;
  const pls = isChain() ? chainPlants() : [plantA(), plant2()].filter((x, i, l) => x && l.indexOf(x) === i);
  CUR.org_info = CUR.org_info || {};
  const pinta = () => {
    const info = CUR.org_info;
    $('#s1txt').innerHTML = pls.map(p => { const o = info[p] || {}; return `<b>${esc(p)}</b>${o.nombre ? ' ' + esc(o.nombre) : ''}${o.pais ? ' (' + esc(o.pais) + ')' : ''}${o.sociedad ? ' · Sociedad ' + esc(o.sociedad) : ''}`; }).join(' &nbsp;→&nbsp; ') + ' <span class="mu">✓ confirmadas</span>';
  };
  pinta();
  const faltan = pls.filter(p => !(CUR.org_info[p] && CUR.org_info[p].nombre));      // plantas elegidas a mano: se pide su descripción
  if (faltan.length) fetch('/api/org?plants=' + encodeURIComponent(faltan.join(','))).then(r => r.json()).then(d => { Object.assign(CUR.org_info, d); pinta(); }).catch(() => {});
  $('#s1sum').hidden = false; $('#s1body').hidden = true;
}
function abrirS1() { $('#s1sum').hidden = true; $('#s1body').hidden = false; }
function sortOpt(si, col) {
  const s = OPTF.sort;
  OPTF.sort = s && s.si === si && s.col === col ? (s.dir === 1 ? {si, col, dir: -1} : null) : {si, col, dir: 1};
  renderOptions();
}
function confirmPlants() {
  if (!plantA()) return alert('Indica al menos una planta.');
  $('#s2').classList.remove('off'); $('#s3').classList.remove('off'); $('#actbar').classList.remove('off');
  $('#s1').classList.add('done');
  loadOptions();
  colapsarS1();
  $('#s2').scrollIntoView({behavior: 'smooth', block: 'start'});
}

async function loadOptions() {
  const plant = plantA();
  if (!plant) return;
  const ex = !isChain() && stream() === 'LOG' && fieldVal('proveedor') ? `&vendor=${encodeURIComponent(fieldVal('proveedor'))}` : isChain() ? `&sin_stock=${CUR.tramos[0].kind === 'COMPRA' ? 1 : 0}&vendor=${encodeURIComponent((tramosVals().find(t => t.kind === 'COMPRA') || {}).proveedor || '')}` : '';
  OPT = await api(`/api/options?id=${encodeURIComponent(CUR.id)}&plant=${plant}&plant2=${plant2()}&stream=${stream()}${ex}`);
  const n = OPT.sections.reduce((t, s) => t + s.rows.length, 0);
  $('#qs4status').innerHTML = OPT.missing.length
    ? `<div class="msg er">Aún no tengo datos de QS4 para este caso: abre la línea «QS4» de arriba y consulta las tablas que faltan.</div>`
    : (n ? '' : `<div class="msg er">No hay opciones para ${esc(plant)}${plant2() ? ' y ' + esc(plant2()) : ''}. Prueba otras plantas.</div>`);
  $('#qs4status').innerHTML += excelHtml();
  if (!window.QS4RUN) qs4Consultar(true);
  // si el tipo que sugiere el caso no existe en las opciones, no se filtra
  const present = new Set(OPT.sections.flatMap(x => x.rows.map(r => r['Tipo'])).filter(Boolean));
  if (TYPES.size && ![...TYPES].some(t => present.has(t))) TYPES = new Set();
  preseleccion();
  renderOptions();
  autoPuesto();
  loadComps();
}
// QM y LOG: si aún no hay nada elegido, se marcan de inicio los materiales de la Data que sirven en la planta (la propuesta de partida).
function preseleccion() {
  if (!(['QM', 'LOG'].includes(stream()) || esListaPP()) || isChain() || selMats().length || !(OPT.excel || []).length) return;
  const obj = OPT.objetivo;
  const sirve = x => obj ? (obj === 'MATERIAL' ? x.existe : x.Apto === 'SÍ') : (stream() === 'PP' ? (x.existe && x.Completo === 'SÍ') : (x.existe && (!x.Apto || x.Apto === 'SÍ')));
  const buenos = OPT.excel.filter(sirve).map(x => String(x.material));
  if (!buenos.length) return;
  setField('material', buenos.join(', '));
  loadChecks();
  refrescaProv();
}
function autoPuesto() {
  if (!CUR || !CUR.con_puesto || !$('#f_puesto_trabajo') || fieldVal('puesto_trabajo')) return;
  const ms = fieldVal('material').split(/[,;\s]+/).filter(Boolean).reverse();      // en pares A → B manda el producto (el último)
  const filas = OPT.sections.flatMap(x => x.rows);
  let r = null;
  for (const m of ms) { r = filas.find(x => x.Material === m && x.fill && x.fill.puesto_trabajo); if (r) break; }
  if (r) { setField('puesto_trabajo', r.fill.puesto_trabajo); loadChecks(); }
}
function excelHtml() {
  const ex = OPT.excel || [], obj = OPT.objetivo;
  if (!ex.length) return '';
  const pp = stream() === 'PP';
  const OBJ = new Proxy({MATERIAL: 'crear un material nuevo', BOM: 'crear la lista de materiales', RUTA: 'crear la hoja de ruta', VERSION: 'crear la versión de fabricación', CC: 'crear el cost collector', VERSIONSEL: 'cambiar la selección de versión', COSTBOM: 'crear la lista de costes', COSTRUTA: 'crear la ruta de tasa', COSTPV: 'crear la versión de costes', COSTLIB: 'liberar el costing'}, {get: (o, k) => o[k] || (String(k).startsWith('ESTADO:') ? 'probar el estado ' + String(k).slice(7) : 'este caso')});
  const lg = !pp && ex.some(x => x.Apto);          // logística: sirve si existe, sin estado ZZ y con registro info donde haga falta
  const bien = ex.filter(x => obj ? (obj === 'MATERIAL' ? x.existe : x.Apto === 'SÍ') : (x.existe && (lg ? x.Apto === 'SÍ' : (!pp || x.Completo === 'SÍ'))));
  const cls = v => String(v).startsWith('✗') ? 'bad' : '';
  const conCas = !pp || esListaPP(), fila = x => `<tr>${conCas ? `<td><input type="checkbox" class="mchk" data-m="${esc(String(x.material))}" ${selMats().includes(String(x.material)) ? 'checked' : ''} ${x.existe ? '' : 'disabled title="No existe en la planta"'} onclick="toggleMat('${esc(String(x.material))}')"></td>` : ''}<td><b>${esc(x.material)}</b></td><td>${x.existe ? esc(x.Tipo) : (x.excluido ? '<span class="mu">repuesto: no se lee de QS4</span>' : `<span class="bad">no existe en ${esc(plantA())}</span>`)}</td>` + (lg ? (x.existe ? `<td class="${x.Apto === 'SÍ' ? 'ok' : 'bad'}">${esc(x.Apto)}</td><td>${esc(x.Motivo)}</td>` : '<td class="bad">NO</td><td class="bad">No existe en la planta</td>') : '') +
    (pp ? `<td class="${cls(x['Lista mat.'])}">${esc(x['Lista mat.'])}</td><td class="${cls(x['Hoja ruta'])}">${esc(x['Hoja ruta'])}</td>${CUR.con_puesto ? `<td class="${cls(x['Puesto trabajo'])}">${esc(x['Puesto trabajo'])}</td>` : ''}<td class="${cls(x['Versión fab.'])}">${esc(x['Versión fab.'])}</td><td class="${cls(x['Cost collector'])}">${esc(x['Cost collector'])}</td>` +
      (obj ? (obj === 'MATERIAL' && !x.existe ? '<td class="bad">NO</td><td class="bad">No existe en la planta: no sirve de modelo</td>' : `<td class="${x.Apto === 'SÍ' ? 'ok' : 'bad'}">${esc(x.Apto || 'NO')}</td><td>${esc(x.Motivo || (x.existe ? '' : 'No existe en la planta'))}</td>`) : `<td class="${x.Completo === 'SÍ' ? 'ok' : 'bad'}">${esc(x.Completo)}</td>`) : '') + '</tr>';
  const falta = ex.filter(x => !bien.includes(x)).map(x => x.material).join(', ');
  let prop;
  if (bien.length === ex.length) prop = `<div style="margin:6px 0"><span class="pill ok">✓ Data original OK</span>${tip(obj === 'MATERIAL' ? 'Todos los modelos de la Data existen en ' + plantA() + ': se puede dejar la Data como está.' : 'Todos los materiales de la Data sirven en ' + plantA() + ': se puede dejar la Data como está.')}</div>`;
  else {
    const cand = OPT.sections.flatMap(s => s.rows).filter(r => ((obj || lg) ? r.Apto === 'SÍ' : (!pp || r.Completo === 'SÍ')) && !r['Reservado por'] && (!TYPES.size || TYPES.has(r.Tipo)));
    prop = `<div class="msg er" style="margin:6px 0">⚠ <b>Cambiar ${esc(falta)}</b> · ${cand.length ? cand.length + ' alternativas abajo (clic en una fila)' : 'sin alternativas con este tipo: prueba «Todos» u otra planta'}</div>`;
  }
  return `<div style="margin:8px 0"><b>Lo que trae el Excel para este caso</b><div class="tw"><table><thead><tr>${conCas ? '<th title="Marca lo que va a la propuesta">✓</th>' : ''}<th>Material</th><th>Tipo</th>${lg ? '<th>Apto</th><th>Motivo</th>' : ''}${pp ? '<th>Lista mat.</th><th>Hoja ruta</th>' + (CUR.con_puesto ? '<th>Puesto</th>' : '') + '<th>Versión</th><th>Cost collector</th>' + (obj ? '<th>Apto</th><th>Motivo</th>' : '<th>Completo</th>') : ''}</tr></thead><tbody>${ex.map(fila).join('')}</tbody></table></div>${prop}</div>`;
}
function toggleType(t) { if (t === '') TYPES = new Set(); else if (TYPES.has(t)) TYPES.delete(t); else TYPES.add(t); renderOptions(); }
function renderOptions() {
  if (!OPT) return;
  const count = {};
  OPT.sections.forEach(x => x.rows.forEach(r => { if (r['Tipo']) count[r['Tipo']] = (count[r['Tipo']] || 0) + 1; }));
  const tipos = Object.keys(count).sort();
  const desc = {ZFIN: 'terminado', ZSEM: 'semielaborado', ZFOR: 'formulado', ZRAW: 'materia prima', ZPAC: 'packaging', ZRPL: 'pallets', ZSPN: 'repuesto', ZSPV: 'repuesto'};
  $('#types').innerHTML = tipos.length ? `<span class="mu">Tipo</span> ` +
    `<button class="chip ${TYPES.size ? '' : 'on'}" onclick="toggleType('')">Todos</button>` +
    tipos.map(t => `<button class="chip ${TYPES.has(t) ? 'on' : ''}" onclick="toggleType('${t}')">${t}${desc[t] ? ' · ' + desc[t] : ''} (${count[t]})</button>`).join('') : '';
  const ok = r => !TYPES.size || !r['Tipo'] || TYPES.has(r['Tipo']);
  const q = OPTF.q.trim().toLowerCase(), elegidos = new Set(fieldVal('material').split(/[,;\s]+/).filter(Boolean));
  let ocultos = 0, nAptos = 0;
  // requisitos que elige el usuario: lista, ruta, versión, cost collector, puesto (da igual / con / sin)
  const reqOn = Object.values(OPTF.req || {}).some(v => v);
  const tiene = (r, col) => { const v = String(r[col] ?? '').trim(); return v === '?' ? null : !!v && !v.startsWith('✗') && v !== '—'; };
  const cumple = (r, sec) => ATTRS.every(([k, , col]) => {
    const e = (OPTF.req || {})[k] || 0;
    if (!e || !sec.columns.includes(col)) return true;
    const t = tiene(r, col);
    return t === null || (e === 1 ? t : !t);
  });
  $('#optctl').hidden = !OPT.sections.some(s => s.rows.length);
  const scrolls = [...document.querySelectorAll('#opts .tw')].map(e => e.scrollTop);
  $('#opts').innerHTML = OPT.sections.map((s, si) => {
    let rows = s.rows.map((r, ri) => [r, ri]).filter(([r]) => ok(r));
    const ac = s.columns.includes('Apto') ? 'Apto' : (s.columns.includes('Completo') ? 'Completo' : null);
    if (ac) nAptos += rows.filter(([r]) => r[ac] === 'SÍ').length;
    if (reqOn) rows = rows.filter(([r]) => cumple(r, s));
    else if (ac && OPTF.solo) { const n0 = rows.length; rows = rows.filter(([r]) => r[ac] === 'SÍ'); ocultos += n0 - rows.length; }
    if (q) rows = rows.filter(([r]) => s.columns.some(c => String(r[c] ?? '').toLowerCase().includes(q)));
    if (!(OPTF.sort && OPTF.sort.si === si)) rows.sort((a, b) => (marcada(b[0]) ? 1 : 0) - (marcada(a[0]) ? 1 : 0));      // lo marcado, arriba
    if (OPTF.sort && OPTF.sort.si === si) { const {col, dir} = OPTF.sort; rows.sort((a, b) => dir * String(a[0][col] ?? '').localeCompare(String(b[0][col] ?? ''), 'es', {numeric: true})); }
    if (!rows.length && s.rows.length) return `<div style="margin-bottom:10px"><b>${esc(s.title)}</b> <span class="mu">0 de ${s.rows.length}</span><div class="mu">Ninguna fila con estos filtros.</div></div>`;
    return rows.length ? `<div style="margin-bottom:10px"><b>${esc(s.title.split(':')[0])}</b> <span class="mu">${rows.length} de ${s.rows.length}</span>${tip(s.title + (s.hint ? '\n\n' + s.hint : ''))}
    <div class="tw"><table><thead><tr><th title="Marca lo que va a la propuesta">✓</th>${s.columns.map(c => `<th class="sortable" onclick="sortOpt(${si},'${c.replace(/'/g, '')}')">${esc(c)}${OPTF.sort && OPTF.sort.si === si && OPTF.sort.col === c ? (OPTF.sort.dir === 1 ? ' ▲' : ' ▼') : ''}</th>`).join('')}</tr></thead><tbody>${rows.map(([r, ri]) =>
      `<tr class="pick ${r['Reservado por'] ? 'res' : ''} ${marcada(r) ? 'sel' : ''}" onclick="pick(${si},${ri},this)"><td>${r.fill && Object.keys(r.fill).some(k => !PLANT_KEYS.includes(k)) ? `<input type="checkbox" class="mchk" data-m="${esc(String((r.fill || {}).material || ''))}" ${marcada(r) ? 'checked' : ''} onclick="event.stopPropagation();pick(${si},${ri},this)">` : ''}</td>${s.columns.map(c => { const v = String(r[c] ?? ''); return `<td class="${v.startsWith('✗') || ((c === 'Completo' || c === 'Apto') && v === 'NO') ? 'bad' : ((c === 'Completo' || c === 'Apto') && v === 'SÍ' ? 'ok' : '')}">${esc(v)}</td>`; }).join('')}</tr>`).join('')}</tbody></table></div></div>` : '';
  }).join('') || (OPT.missing.length ? '' : '<div class="mu">Ninguna opción con ese tipo de material.</div>');
  document.querySelectorAll('#opts .tw').forEach((e, i) => { e.scrollTop = scrolls[i] || 0; });
  pintaSel();
  const bs = $('#optsolo');
  if (bs) { bs.className = 'chip req ' + (OPTF.solo ? 'yes' : ''); bs.textContent = (OPTF.solo ? '✓ ' : '') + `Solo los que sirven (${nAptos})`; bs.hidden = !OPT.sections.some(x => x.columns.includes('Apto') || x.columns.includes('Completo')); }
  const presentes = ATTRS.filter(([, , col]) => OPT.sections.some(x => x.columns.includes(col)));
  $('#optreq').innerHTML = presentes.length ? '<span class="mu">Debe llevar</span> ' + presentes.map(([k, lab]) => {
    const e = (OPTF.req || {})[k] || 0;
    return `<button class="chip req ${e === 1 ? 'yes' : (e === -1 ? 'no' : '')}" onclick="reqToggle('${k}')" title="Pulsa: con ✓ → sin ✕ → sin filtro">${e === 1 ? '✓ ' : (e === -1 ? '✕ ' : '')}${lab}</button>`;
  }).join('') + (reqOn ? ' <a href="#" onclick="OPTF.req = {}; renderOptions(); return false">quitar</a>' : '') : '';
}
const ATTRS = [['lista', 'Lista de materiales', 'Lista mat.'], ['ruta', 'Hoja de ruta', 'Hoja ruta'], ['version', 'Versión de fabricación', 'Versión fab.'], ['cc', 'Cost collector', 'Cost collector'], ['puesto', 'Puesto de trabajo', 'Puesto trabajo']];
function reqToggle(k) { const e = (OPTF.req || {})[k] || 0; OPTF.req = Object.assign({}, OPTF.req, {[k]: e === 0 ? 1 : (e === 1 ? -1 : 0)}); renderOptions(); }
// Selección en las listas de opciones. Cada fila tiene una CASILLA: marcada = va a «Datos elegidos» y a la propuesta; desmarcada = no va.
//  · QM y LOG (y el modelo a copiar de PP): la selección es una LISTA de materiales; marcar añade, desmarcar quita. De inicio se marcan los de la Data que sirven.
//  · PP (producto a fabricar): el material elegido sustituye al de la Data que no sirve (como siempre).
//  · Otras filas (equipo, proveedor, cliente, ubicación…): marcar la elige, desmarcar la quita.
const selMats = () => fieldVal('material').split(/[,;\s]+/).filter(Boolean);
// PP: los casos que CREAN algo (material, lista, ruta, versión, costes…) eligen materiales con casillas, como QM y LOG. El resto (producto completo, pares A → B, planificación…) sigue como antes.
const OBJ_LISTA_PP = ['MATERIAL', 'BOM', 'RUTA', 'VERSION', 'CC', 'COSTBOM', 'COSTRUTA', 'COSTPV', 'COSTLIB', 'VERSIONSEL'];
const esListaPP = () => stream() === 'PP' && !!OPT;      // todo PP: casillas, varios materiales a la vez (marcar / desmarcar)
function marcada(r) {
  const f = r.fill || {};
  if (/^\d+$/.test(String(f.material || '').trim())) return selMats().includes(String(f.material).trim());
  const k = Object.keys(f).find(x => !PLANT_KEYS.includes(x));
  const v = k ? String(f[k]).trim() : '';
  return !!v && fieldVal(k).split(/[,;]\s*/).includes(v);
}
function syncChecks() {      // los cuadros de las dos tablas reflejan siempre lo que hay en «Datos elegidos»
  const sel = new Set(selMats());
  document.querySelectorAll('input.mchk').forEach(e => { if (e.dataset.m) e.checked = sel.has(e.dataset.m); });
  pintaSel();
}
function pintaSel() {      // resumen SIEMPRE visible de lo seleccionado: cada material es una etiqueta que se quita con un clic
  const box = $('#selbar');
  if (!box || !CUR || !OPT) return;
  const st = stream();
  if (!(st === 'QM' || st === 'LOG' || st === 'PP') || isChain()) { box.innerHTML = ''; return; }
  const sel = selMats(), n0 = (OPT.excel || []).length;
  const tipo = m => { for (const sc of OPT.sections) { const r = sc.rows.find(x => String((x.fill || {}).material) === m); if (r && r.Tipo) return r.Tipo; } return ((OPT.excel || []).find(x => String(x.material) === m) || {}).Tipo || ''; };
  box.innerHTML = sel.length
    ? `<div style="display:flex;flex-wrap:wrap;gap:6px;align-items:center"><b>Seleccionados (${sel.length})</b>${sel.map(m => `<button class="chip on" onclick="toggleMat('${m}')" title="Pulsa para quitarlo de la propuesta">${esc(m)}${tipo(m) ? ' · ' + esc(tipo(m)) : ''} ✕</button>`).join('')}<a href="#" onclick="quitaTodos();return false">quitar todos</a>${n0 && sel.length !== n0 ? `<span class="mu">· la Data original trae ${n0}</span>` : ''}</div>`
    : `<div class="mu">Nada seleccionado${n0 ? ` (la Data original trae ${n0})` : ''}: marca las filas que quieras en la lista.</div>`;
}
function quitaTodos() { setField('material', ''); renderOptions(); syncChecks(); loadChecks(); refrescaProv(); toast('Selección vacía'); }
let PROVT = null;
function refrescaProv() {      // compras: «Registros info» y «Apto» de cada proveedor dependen de los materiales marcados
  clearTimeout(PROVT);
  PROVT = setTimeout(async () => {
    if (!CUR || !OPT || stream() !== 'LOG' || !['ZPO', 'ZSPO', 'ZSPA', 'ZSER'].includes(CUR.flow) || isChain() || !plantA()) return;
    const r = await api(`/api/options?id=${encodeURIComponent(CUR.id)}&plant=${plantA()}&plant2=${plant2()}&stream=LOG&mats=${encodeURIComponent(selMats().join(','))}`);
    const i = OPT.sections.findIndex(x => x.tipo === 'PROVEEDOR'), j = (r.sections || []).findIndex(x => x.tipo === 'PROVEEDOR');
    if (i >= 0 && j >= 0) { OPT.sections[i] = r.sections[j]; renderOptions(); }
  }, 400);
}
function toggleMat(m) {      // desde la tabla «Lo que trae el Excel»
  const cur = selMats(), i = cur.indexOf(m);
  if (i >= 0) cur.splice(i, 1); else cur.push(m);
  setField('material', cur.join(', '));
  renderOptions(); syncChecks(); loadChecks(); refrescaProv();
  toast(i >= 0 ? `${m} desmarcado: sale de la propuesta` : `${m} marcado: entra en la propuesta`);
}
function pick(si, ri, tr) {
  const r = OPT.sections[si].rows[ri];
  const st = stream();
  const actuales = selMats();
  const nuevoM = ((r.fill || {}).material || '').trim();
  const otros = () => Object.entries(r.fill || {}).filter(([k]) => k !== 'material' && !PLANT_KEYS.includes(k));
  const poneOtros = () => otros().forEach(([k, v]) => setField(k, v, (META.fields[st].find(f => f.key === k) || {}).multi));
  const fin = msg => { renderOptions(); syncChecks(); loadChecks(); refrescaProv(); toast(msg); };
  const num = /^\d+$/.test(nuevoM);
  const lista = num && (st === 'QM' || st === 'LOG' || esListaPP());
  if (lista) {
    if (actuales.includes(nuevoM)) { setField('material', actuales.filter(m => m !== nuevoM).join(', ')); return fin(`${nuevoM} desmarcado: sale de la propuesta`); }
    if (r['Reservado por'] && !confirm(`Este dato ya está reservado por ${r['Reservado por']} (cada dato va a un solo caso). ¿Usarlo igualmente?`)) { renderOptions(); return; }
    setField('material', actuales.concat(nuevoM).join(', ')); poneOtros();
    return fin(`${nuevoM} marcado: entra en la propuesta (${actuales.length + 1} materiales)`);
  }
  if (marcada(r)) {                                                  // estaba elegida: se quita
    Object.keys(r.fill || {}).forEach(k => { if (!PLANT_KEYS.includes(k)) { const e = document.getElementById('f_' + k); if (e) e.value = ''; } });
    return fin(`Quitado: ${r.Material || r.Equipo || r.Proveedor || nuevoM || 'fila'}`);
  }
  if (r['Reservado por'] && !confirm(`Este dato ya está reservado por ${r['Reservado por']} (cada dato va a un solo caso). ¿Usarlo igualmente?`)) { renderOptions(); return; }
  if (st === 'PP' && num && (OPT.excel || []).length) {              // PP: el material elegido sustituye al de la Data que no sirve (si no, el original se queda en la propuesta)
    const obj = OPT.objetivo;
    const sirve = x => obj ? (obj === 'MATERIAL' ? x.existe : x.Apto === 'SÍ') : (x.existe && x.Completo === 'SÍ');
    const malos = new Set(OPT.excel.filter(x => !sirve(x)).map(x => String(x.material)));
    const cur = actuales.length ? actuales.slice() : OPT.excel.map(x => String(x.material));
    const tipoDe = m => (OPT.excel.find(x => String(x.material) === m) || {}).Tipo;
    let i = cur.findIndex(m => malos.has(m) && r.Tipo && tipoDe(m) === r.Tipo);
    if (i < 0) i = cur.findIndex(m => malos.has(m));
    if (i >= 0 && !cur.includes(nuevoM)) {
      const viejo = cur[i]; cur[i] = nuevoM;
      setField('material', cur.join(', ')); poneOtros();
      return fin(`${nuevoM} sustituye a ${viejo} en la propuesta`);
    }
  }
  Object.entries(r.fill || {}).forEach(([k, v]) => { if (!PLANT_KEYS.includes(k)) setField(k, v, (META.fields[st].find(f => f.key === k) || {}).multi); });
  fin(`Elegido: ${r.Material || r.Equipo || r.Proveedor || Object.values(r.fill || {}).find(Boolean) || 'fila'} — míralo en «Datos elegidos»`);
}

let QS4CTX = null;
async function qs4Consultar(silencio) {
  const pls = isChain() ? chainPlants() : [plantA(), plant2()].filter((x, i, l) => x && l.indexOf(x) === i);
  if (!pls.length) return silencio === true ? null : alert('Indica primero una planta.');
  const s0 = await api('/api/qs4/status');
  if (s0.estado === 'consultando') { qs4Seguir(); return; }          // hay una consulta en marcha (p. ej. tras recargar): se retoma su progreso
  const vendor = isChain() ? ((tramosVals().find(t => t.kind === 'COMPRA') || {}).proveedor || '') : (stream() === 'LOG' ? (fieldVal('proveedor') || (['ZTRA', 'ZWIA', 'ZINT', 'ZINR'].includes(CUR.flow) && plantA() ? 'P' + plantA() : '')) : '');
  const pl = await api(`/api/qs4/plan?id=${encodeURIComponent(CUR.id)}&plants=${pls.join(',')}&stream=${stream()}&vendor=${encodeURIComponent(vendor)}`);
  QS4CTX = {pls, vendor};
  const hay = pl.items.filter(i => i.existe), faltan = pl.items.filter(i => !i.existe);
  const ult = hay.reduce((m, i) => (!m || i.ts > m.ts ? i : m), null);
  const abierto = faltan.length > 0 || window.QS4ABIERTO;      // comprimido salvo que falte algo o lo abras tú
  $('#qs4').innerHTML = `<details id="qs4det" ${abierto ? 'open' : ''} ontoggle="window.QS4ABIERTO = this.open" style="margin:0 0 8px;background:#eef3fb;border:1px solid var(--line);border-radius:8px;padding:6px 10px">
    <summary style="color:var(--tx)"><b>QS4</b> · ${esc(pls.join(', '))} · ${hay.length} tabla${hay.length === 1 ? '' : 's'} guardada${hay.length === 1 ? '' : 's'}${ult ? ` <span class="mu">(última lectura ${esc(ult.fecha)})</span>` : ''}${faltan.length ? ` · <span style="color:var(--er);font-weight:600">faltan ${faltan.length}</span>` : ' · <span style="color:var(--ok)">completo</span>'}</summary>
    ${hay.length ? `<div style="margin-top:6px"><span class="mu">Marca las que quieras releer</span>${tip('Las tablas guardadas se reutilizan; solo se vuelven a leer de QS4 las que marques.')}${hay.map(i => `<label style="display:flex;gap:6px;align-items:center;margin:2px 0;font-weight:400"><input type="checkbox" class="qs4r" value="${esc(i.name)}" style="width:auto" onchange="qs4Boton()"> <span>${esc(i.humano || i.name)}</span> <span class="mu">· ${esc(i.name)} · ${i.filas} filas · leída ${esc(i.fecha)}</span></label>`).join('')}
      <div style="margin-top:2px"><a href="#" onclick="document.querySelectorAll('.qs4r').forEach(c => c.checked = true); qs4Boton(); return false">marcar todas</a> · <a href="#" onclick="document.querySelectorAll('.qs4r').forEach(c => c.checked = false); qs4Boton(); return false">ninguna</a></div></div>` : ''}
    ${faltan.length ? `<div style="margin-top:6px"><b>Se consultará ahora</b>${faltan.map(i => `<div>• ${esc(i.humano || i.texto)} <span class="mu">(${esc(i.name)})</span>${i.est ? ` <span class="mu">· la última vez tardó ~${i.est >= 60 ? Math.round(i.est / 60) + ' min' : i.est + ' s'}</span>` : ''}</div>`).join('')}</div>` : ''}
    <div class="bar" style="margin:8px 0 2px"><button class="pri" id="qs4go" onclick="qs4Lanzar()">Consultar QS4</button><button onclick="qs4TodoPlanta(${hay.length + faltan.length}, ${hay.concat(faltan).reduce((a, i) => a + (i.est || 0), 0)})" title="Vuelve a leer de QS4 todas las tablas de la planta, también las que ya tienes">↻ Refrescar todo</button>
      ${tip(pl.sistema + ' · solo lectura (SE16N).\nSi SAP no está abierto, se conecta con la credencial guardada (un solo intento).')}</div></details>`;
  window.QS4FALTAN = faltan.length; window.QS4HAY = hay.length; window.QS4N = hay.length + faltan.length;
  qs4Boton();
}
function qs4Boton() {
  const ref = document.querySelectorAll('.qs4r:checked').length, b = $('#qs4go');
  if (!b) return;
  b.disabled = !window.QS4FALTAN && !ref;
  b.textContent = ref ? `Consultar QS4 (${window.QS4FALTAN ? window.QS4FALTAN + ' que faltan + ' : ''}${ref} a refrescar)` : (window.QS4FALTAN ? (window.QS4HAY ? `Consultar lo que falta (${window.QS4FALTAN})` : `Consultar las ${window.QS4N} tablas`) : 'Nada que consultar');
}
function qs4TodoPlanta(n, seg) {
  const dur = seg >= 60 ? `unos ${Math.round(seg / 60)} min según la última vez` : (seg ? `~${seg} s según la última vez` : 'puede llevar varios minutos');
  if (!confirm(`Se volverán a leer en QS4 las ${n} tablas de ${QS4CTX.pls.join(', ')} (${dur}). Es solo lectura. ¿Continuar?`)) return;
  document.querySelectorAll('.qs4r').forEach(c => { c.checked = true; });
  qs4Lanzar();
}
async function qs4Lanzar() {
  const refrescar = [...document.querySelectorAll('.qs4r:checked')].map(c => c.value), {pls, vendor} = QS4CTX;
  window.QS4RUN = true;
  const r = await api('/api/qs4/run', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({id: CUR.id, plants: pls, vendor, stream: stream(), confirmado: true, refrescar})});
  if (r.error) { $('#qs4').innerHTML = `<div class="msg er">${esc(r.error)}</div>`; return; }
  qs4Seguir();
}
function qs4Seguir() {
  if (window.QS4POLL) return;
  window.QS4RUN = true;
  const fmt = sg => `${Math.floor(sg / 60)}:${String(Math.floor(sg % 60)).padStart(2, '0')}`;
  const pinta = s => {
    const ahora = Date.now() / 1000;
    $('#qs4').innerHTML = `<div class="msg" style="background:#eef3fb;border:1px solid var(--line)"><div><b>${esc(s.sistema || 'Conectando con SAP…')}</b> · ${esc(s.estado)} (${s.paso}/${s.total}) <span class="mu">${esc(s.paso_texto || '')}</span>${s.items.length > 8 ? ` · <span class="mu">${s.items.filter(i => i.estado === 'error').length} con error</span>` : ''}</div>` +
      s.items.slice(-8).map(i => `<div style="${i.estado === 'error' ? 'color:var(--er)' : (i.estado === 'consultando' ? '' : 'color:var(--mu)')}">${i.estado === 'consultando' ? '⏳' : (i.estado === 'error' ? '✗' : '✓')} ${esc(i.name)}: ${esc(i.estado)}${i.filas != null ? ' · ' + i.filas + ' filas' : ''}${i.estado === 'consultando' && i.ini ? ' · ' + fmt(ahora - i.ini) : ''}${i.error ? ' · ' + esc(i.error) : ''}${i.aviso ? ' · ' + esc(i.aviso) : ''}${i.estado === 'consultando' && i.fase ? `<div class="mu" style="margin-left:22px">↳ ${esc(i.fase)}</div>` : ''}</div>`).join('') +
      (s.estado === 'consultando' ? '<div class="mu" style="margin-top:4px">Las tablas grandes pueden tardar minutos ' + tip('Las listas de materiales y el stock son tablas grandes y pueden tardar varios minutos.\nPuedes seguir trabajando: esto se actualiza solo.\nNo cierres SAP.') + '</div>' : '') +
      (s.error ? `<div class="msg er">${esc(s.error)}</div>` : '') + '</div>';
  };
  window.QS4POLL = setInterval(async () => {
    let s;
    try { s = await api('/api/qs4/status'); }
    catch (err) { clearInterval(window.QS4POLL); window.QS4POLL = null; window.QS4RUN = false; $('#qs4').innerHTML = '<div class="msg er">Se perdió la conexión con el servidor: la lectura se ha interrumpido. Ábrelo con iniciar_uat.bat y vuelve a lanzarla (lo ya guardado se conserva).</div>'; return; }
    pinta(s);
    if (s.estado !== 'consultando') { clearInterval(window.QS4POLL); window.QS4POLL = null; window.QS4RUN = false; META = await api('/api/meta'); if (s.estado === 'terminado') { loadOptions(); loadChecks(); } }
  }, 1000);
}
// ---- Conexión a SAP: sección general en la cabecera (estado siempre visible) ----
async function sapPintar() {
  let e, q;
  try { e = await api('/api/sap/estado'); q = await api('/api/qs4/status'); }
  catch (err) {          // el servidor no contesta: se dice, en vez de dejar el último estado congelado
    $('#sap').innerHTML = '<span class="dot er"></span><span class="tx" style="color:#ffb3ad;max-width:none">El servidor no responde. Ábrelo de nuevo con iniciar_uat.bat (una lectura en marcha se ha perdido)</span>';
    window.QS4POLL && (clearInterval(window.QS4POLL), window.QS4POLL = null, window.QS4RUN = false);
    return;
  }
  if (e.version) {          // qué versión es la que veo, y aviso si el servidor ya tiene otra
    if (!window.VER0) window.VER0 = e.version;
    $('#ver').textContent = 'versión ' + window.VER0;
    $('#newver').hidden = true;
    $('#newbar').hidden = e.version === window.VER0;
  }
  let dot = '', txt = '', btn = '';
  if (!e.usuario) { dot = 'er'; txt = 'SAP: sin credencial guardada'; }
  else if (e.bloqueado) { dot = 'er'; txt = `SAP: el último intento de login con ${e.usuario} falló o se cortó; no reintento solo`; btn = 'Reintentar login…'; }
  else if (e.estado === 'conectando') { dot = 'wait'; txt = `SAP: conectando… ${e.texto || ''}`; }
  else if (e.estado === 'error') { dot = 'er'; txt = 'SAP: ' + e.error; btn = 'Reintentar'; }
  else if (q.estado === 'consultando') { dot = 'wait'; txt = `SAP ${q.sistema || ''}: consultando (${q.paso}/${q.total}) ${q.paso_texto || ''}`; }
  else if (e.estado === 'conectado') { dot = 'ok'; txt = `SAP: ${e.texto} · usuario ${e.usuario}`; btn = 'Comprobar'; }
  else { dot = ''; txt = `SAP: sin conectar · usuario ${e.usuario}`; btn = 'Conectar a SAP'; }
  $('#sap').innerHTML = `<span class="dot ${dot}"></span><span class="tx" title="${esc(txt)}">${esc(txt)}</span>` + (btn ? `<button onclick="sapConectar()">${btn}</button>` : '') +
    `<button onclick="abrirPwd()" title="Guardar o cambiar la contraseña de SAP">${e.usuario ? 'Contraseña…' : 'Guardar contraseña…'}</button>`;
  window.SAPUSER = e.usuario || '';
}
async function abrirPwd() {
  $('#pw_user').value = window.SAPUSER || ''; $('#pw_pwd').value = ''; $('#pw_msg').innerHTML = '';
  $('#dlgpwd').showModal();
  ($('#pw_user').value ? $('#pw_pwd') : $('#pw_user')).focus();
}
async function guardarPwd() {
  const u = $('#pw_user').value.trim(), p = $('#pw_pwd').value;
  if (!u || !p) { $('#pw_msg').innerHTML = '<div class="msg er">Indica usuario y contraseña.</div>'; return; }
  const r = await api('/api/sap/credencial', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-UAT': '1'}, body: JSON.stringify({usuario: u, password: p})});
  $('#pw_pwd').value = '';
  if (r.error) { $('#pw_msg').innerHTML = `<div class="msg er">${esc(r.error)}</div>`; return; }
  $('#dlgpwd').close();
  sapPintar();
  alert('Contraseña guardada para ' + r.usuario + '. Ya puedes pulsar Conectar (se hará un solo intento).');
}
// ---------- Propuesta en bloque por módulos, con reloj de avance ----------
let PROP = {stream: 'PP', poll: null};
const mmss = sg => { sg = Math.max(0, Math.round(sg)); return `${Math.floor(sg / 60)}:${String(sg % 60).padStart(2, '0')}`; };
async function abrirProp(stream) {
  const s = await api('/api/auto/status');
  const st = typeof stream === 'string' ? stream : (s.estado === 'calculando' ? s.stream : PROP.stream);
  PROP.stream = st;
  $('#prstream').innerHTML = Object.keys(s.modulos).map(m => `<option value="${m}" ${m === st ? 'selected' : ''} ${s.modulos[m] ? 'disabled' : ''}>${m}${s.modulos[m] ? ' (pendiente)' : ''}</option>`).join('');
  const r = await api('/api/plantas?stream=' + st);
  const listas = r.plantas.filter(p => !p.faltan);
  $('#prmsg').innerHTML = `Rellena la propuesta de los casos del módulo <b>${esc(st)}</b> en las plantas que marques (solo las que tienen todos sus datos leídos de QS4). Si la Data del Excel ya sirve, se deja; si no, se propone el primer dato válido y libre. No se toca lo validado ni lo trabajado a mano, y solo se rehace lo automático anterior <b>de este módulo y estas plantas</b>. ${tip('Los otros módulos (QM, PM, WM, LOG) aparecen como pendientes hasta que tengan sus reglas aprobadas e implementadas: proponer sin reglas daría datos sin garantías.')}`;
  $('#prlista').innerHTML = `<table><thead><tr><th></th><th>Planta</th><th>Casos</th><th>Datos</th></tr></thead><tbody>${r.plantas.map(p => `<tr><td><input type="checkbox" class="prsel" value="${esc(p.planta)}" data-casos="${p.casos}" ${p.faltan ? 'disabled' : 'checked'} style="width:auto" onchange="propResumen()"></td><td><b>${esc(p.planta)}</b></td><td>${p.casos}</td><td>${p.faltan ? `<span style="color:var(--er)">faltan ${p.faltan} de ${p.tablas} tablas</span>` : '<span style="color:var(--ok)">✓ completos</span>'}</td></tr>`).join('')}</tbody></table><div class="mu" style="margin-top:6px">Marcar: <a href="#" onclick="propMarca(0);return false">ninguna</a> · <a href="#" onclick="propMarca(1);return false">todas las completas</a></div>`;
  propResumen();
  if (s.estado === 'calculando') seguirProp(); else pintaProp(s);
  $('#dlgprop').showModal();
}
function propMarca(m) { document.querySelectorAll('.prsel:not(:disabled)').forEach(c => { c.checked = !!m; }); propResumen(); }
function propResumen() {
  const sel = [...document.querySelectorAll('.prsel:checked')], casos = sel.reduce((a, c) => a + (+c.dataset.casos || 0), 0);
  const b = $('#prgo'); if (!b) return;
  b.disabled = !sel.length || !!PROP.poll;
  b.textContent = sel.length ? `Proponer ${casos} casos (${sel.length} planta${sel.length === 1 ? '' : 's'})` : 'Marca alguna planta';
}
async function lanzarProp() {
  const plantas = [...document.querySelectorAll('.prsel:checked')].map(c => c.value);
  if (!plantas.length) return;
  const x = await api('/api/auto', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({confirmado: true, stream: PROP.stream, plantas})});
  if (x.error) return alert(x.error);
  seguirProp();
}
function pintaProp(s) {
  const box = $('#prreloj'); if (!box) return;
  if (s.estado === 'libre' || !s.inicio) { box.innerHTML = ''; return; }
  const fin = s.estado === 'calculando' ? s.ahora : s.fin, t = fin - s.inicio, pc = s.total ? Math.round(100 * s.hechos / s.total) : 0;
  const quedan = s.estado === 'calculando' && s.hechos > 3 ? ` · quedan ~${mmss(t / s.hechos * (s.total - s.hechos))}` : '';
  const c = s.cuenta || {};
  const cuenta = `Propuestos ${c.propuestos || 0} · Original OK ${c.original_ok || 0} · Sin candidato ${c.sin_candidato || 0} · No requiere ${c.no_requiere || 0} · Revisar a mano ${c.revisar || 0} · Respetados ${c.respetados || 0}${c.sin_datos ? ' · Sin datos ' + c.sin_datos : ''}`;
  box.innerHTML = `<div class="msg ${s.estado === 'error' ? 'er' : (s.estado === 'terminado' ? 'ok' : '')}" style="${s.estado === 'calculando' ? 'background:#eef3fb;border:1px solid var(--line)' : ''}">
    <div style="display:flex;gap:10px;align-items:baseline"><b style="font-size:18px;font-variant-numeric:tabular-nums">⏱ ${mmss(t)}</b><span>${s.estado === 'calculando' ? `${s.hechos} de ${s.total} casos · ${pc}%${quedan}${s.planta ? ' · ' + esc(s.planta) : ''}` : (s.estado === 'terminado' ? `✓ Terminado: ${s.total} casos de ${esc(s.stream)} en ${mmss(t)}` : '✗ ' + esc(s.error || 'error'))}</span></div>
    <div style="height:6px;background:#d6dde8;border-radius:3px;margin:6px 0"><div style="height:6px;width:${s.estado === 'terminado' ? 100 : pc}%;background:${s.estado === 'error' ? 'var(--er)' : 'var(--ok)'};border-radius:3px"></div></div>
    <div class="mu">${cuenta}</div></div>`;
  const b = $('#prbtn'); if (b) b.textContent = s.estado === 'calculando' ? `⏱ Propuesta ${pc}%…` : 'Propuesta en bloque…';
}
function seguirProp() {
  if (PROP.poll) return;
  propResumen();
  PROP.poll = setInterval(async () => {
    let s;
    try { s = await api('/api/auto/status'); } catch (e) { return; }
    pintaProp(s);
    if (s.estado !== 'calculando') {
      clearInterval(PROP.poll); PROP.poll = null; propResumen();
      CASES = await api('/api/cases'); renderList();
      toast(s.estado === 'terminado' ? 'Propuesta terminada' : 'La propuesta ha fallado', s.estado !== 'terminado');
    }
  }, 700);
}
let PLANTAS = null;
async function abrirPlantas(stream) {
  const st = typeof stream === 'string' ? stream : (($('#plstream') || {}).value || 'PP');
  const r = await api('/api/plantas?stream=' + st); $('#plstream').value = st;
  PLANTAS = r;
  const pend = r.plantas.filter(p => p.faltan);
  if (!pend.length) { $('#plmsg').innerHTML = `✓ Las ${r.plantas.length} plantas de ${st} ya tienen todos sus datos cargados. Si quieres releer alguna, hazlo desde el panel «QS4» de un caso de esa planta («↻ Refrescar todo»).`; }
  else $('#plmsg').innerHTML = `Lee de QS4, una planta detrás de otra y solo lo que falta (solo lectura). Puedes dejarlo corriendo: el equipo no se duerme mientras lee. Si algo falla, se sigue con lo siguiente y lo ya guardado se conserva. ${tip('Cada planta son unas 13 tablas. Una planta suele llevar entre 10 y 25 minutos. No cierres la ventana negra del servidor (iniciar_uat.bat) ni SAP mientras dure.')}`;
  $('#pllista').innerHTML = `<table><thead><tr><th></th><th>Planta</th><th>Casos</th><th>Estado</th><th>Tiempo aprox.</th></tr></thead><tbody>${r.plantas.map(p => `<tr><td><input type="checkbox" class="plsel" value="${esc(p.planta)}" data-seg="${p.seg}" ${p.faltan ? ((st !== 'LOG' || p.planta.startsWith('L')) ? 'checked' : '') : 'disabled'} style="width:auto" onchange="plResumen()"></td><td><b>${esc(p.planta)}</b></td><td>${p.casos}</td><td>${p.faltan ? `<span style="color:var(--er)">faltan ${p.faltan} de ${p.tablas}</span>` : '<span style="color:var(--ok)">✓ completa</span>'}</td><td class="mu">${p.faltan ? '~' + Math.max(1, Math.round(p.seg / 60)) + ' min' : ''}</td></tr>`).join('')}</tbody></table><div class="mu" style="margin-top:6px">Marcar: <a href="#" onclick="plMarca(0);return false">ninguna</a> · <a href="#" onclick="plMarca(1);return false">todas las pendientes</a>${st === 'LOG' ? ' · <a href="#" onclick="plMarca(2);return false">solo las L</a>' : ''}</div>`;
  plResumen();
  $('#dlgplantas').showModal();
}
function plMarca(m) {
  document.querySelectorAll('.plsel:not(:disabled)').forEach(c => { c.checked = m === 1 || (m === 2 && c.value.startsWith('L')); });
  plResumen();
}
function plResumen() {
  const sel = [...document.querySelectorAll('.plsel:checked')], seg = sel.reduce((a, c) => a + (+c.dataset.seg || 0), 0);
  const b = $('#plgo'); b.hidden = !sel.length; $('#plautol').hidden = !sel.length;
  b.textContent = sel.length ? `Lanzar ${sel.length} planta${sel.length > 1 ? 's' : ''} (~${seg >= 3600 ? (seg / 3600).toFixed(1) + ' h' : Math.round(seg / 60) + ' min'})` : 'Nada pendiente';
}
async function lanzarPlantas() {
  const plants = [...document.querySelectorAll('.plsel:checked')].map(c => c.value);
  if (!plants.length) return;
  const r = await api('/api/qs4/run', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({id: PLANTAS.ejemplo, plants, stream: PLANTAS.stream, masivo: true, confirmado: true, refrescar: [], vendor: '', autocurar: $('#plauto').checked})});
  $('#dlgplantas').close();
  if (r.error) return alert(r.error);
  toast(`Lectura lanzada: ${plants.length} planta${plants.length > 1 ? 's' : ''}. Mira el estado en la cabecera.`);
  sapPintar();
}
async function sapConectar() {
  const e = await api('/api/sap/estado');
  const freno = !!e.bloqueado;
  if (!e.usuario) return alert('No hay credencial guardada. Haz doble clic en guardar_credencial_sap.bat (una sola vez; también para cambiarla cuando caduque).');
  if (freno ? !confirm(`El último intento de login con ${e.usuario} falló o se cortó. Si la contraseña guardada es incorrecta, intentarlo otra vez puede BLOQUEAR tu usuario de SAP.\n\nSi no estás seguro, entra antes a mano en SAP o cambia la contraseña con guardar_credencial_sap.bat.\n\n¿Quieres que haga UN intento ahora?`)
         : !confirm(`Se abrirá SAP Logon y se entrará en QS4 como ${e.usuario} (un solo intento, sin reintentos). Si ya estás dentro, solo se comprueba. ¿Continuar?`)) return;
  const r = await api('/api/sap/conectar', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({confirmado: true, levantar_freno: freno})});
  if (r.error) alert(r.error);
  sapPintar();
}
setInterval(sapPintar, 3000);

async function loadAlts(scope) {
  const r = await api(`/api/alternatives?id=${encodeURIComponent(CUR.id)}&plant=${plantA()}&stream=${stream()}&scope=${scope}`);
  const box = $('#alts');
  if (r.missing.length) { box.innerHTML = `<div class="mu">Primero consulta QS4 para poder proponer plantas.</div>`; return; }
  box.innerHTML = r.alternatives.length ? `<div class="tw"><table><thead><tr><th>Planta</th><th>Nombre</th><th>Sociedad</th><th>Opciones</th><th></th></tr></thead><tbody>${r.alternatives.map(x =>
      `<tr><td><b>${x.planta}</b></td><td>${esc(x.nombre)}</td><td>${esc(x.sociedad)} ${x.misma_sociedad ? '✓' : ''}</td><td>${x.candidatos}</td><td><button onclick="useAlt('${x.planta}')">Usar</button></td></tr>`).join('')}</tbody></table></div>`
    : `<div class="mu">Ninguna planta tiene opciones con los datos cargados.</div>`;
}
async function useAlt(plant) {
  setField(stream() === 'LOG' && !unaPlantaLog(CUR) ? 'planta_emisora' : 'planta', plant);
  await plantsChanged();
}

async function save(status, next) {
  const fields = {};
  (META.fields[stream()] || []).concat(META.org_fields).forEach(f => fields[f.key] = fieldVal(f.key));
  const tramos = isChain() ? tramosVals() : [];
  if (isChain()) { const cp = chainPlants(); fields.planta_emisora = cp[0] || ''; fields.planta_receptora = cp[cp.length - 1] || ''; }
  const r = await api('/api/case?id=' + encodeURIComponent(CUR.id), {method: 'PUT', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({fields, tramos, extras: extrasVals(), pasos: pasosVals(), pasos_campos: PC, edits: EDITS, status, note: ($('#note') || {}).value || '', org_ok: true, stream_override: CUR.stream !== CUR.detected_stream ? CUR.stream : ''})});
  const msg = (r.avisos || []).map(w => `<div class="msg er">${esc(w)}</div>`).join('') + '<div class="msg ok">Guardado.</div>' + (r.conflicts.length
    ? `<div class="msg warn">⚠ Dato compartido con otro caso (guardado igualmente): ${r.conflicts.map(c => `${esc(c.tipo)} ${esc(c.recurso)} (${esc(c.casos.join(', '))})`).join('; ')}</div>`
    : '');
  const id = CUR.id;
  CASES = await api('/api/cases');
  if (next && !(r.avisos || []).length) {          // un dato compartido es solo un aviso: no frena el paso al siguiente caso
    const antes = QUEUE.findIndex(c => c.id === id);
    renderList();
    const sig = QUEUE[Math.min(QUEUE.findIndex(c => c.id === id) >= 0 ? antes + 1 : antes, QUEUE.length - 1)];
    if (sig) openCase(sig.id); else $('#main').innerHTML = '<div class="empty">No quedan casos con ese filtro.</div>';
    return;
  }
  renderList();
  const st = $('#main').scrollTop;
  await openCase(id); $('#main').scrollTop = st; $('#saveres').innerHTML = msg;
  toast((r.avisos || []).length ? 'Guardado, pero hay avisos: revisa «Datos elegidos»' : (r.conflicts.length ? 'Guardado (dato compartido con otro caso)' : 'Guardado'), !!(r.avisos || []).length);
}
async function genExcel() {
  const r = await api('/api/excel?abrir=1'), v = r.verificacion;
  alert(r.error ? r.error : `Excel generado (copia; el original no se toca):\n${r.ruta}\n\nFilas con propuesta: ${r.filas}\nSolo cambian sheet2.xml y table2.xml: ${v.solo_sheet2_y_table2 ? 'SÍ' : 'NO'}\nColumnas A:AF idénticas: ${v.filas_A_AF_identicas ? 'SÍ' : 'NO'}${r.peticiones ? '\nPeticiones de maestros: ' + r.peticiones : ''}`);
}
init();
setTimeout(() => api('/api/auto/status').then(s => { if (s.estado === 'calculando') { PROP.stream = s.stream; seguirProp(); } }).catch(() => {}), 800);
