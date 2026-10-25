"use strict";
// Todo el contenido dinámico se inserta con textContent (nunca innerHTML) para evitar XSS con datos del Excel.
const $ = (id) => document.getElementById(id);
const JSONH = { "Content-Type": "application/json" };

let sel = null;               // {stream, flow, meta}
let files = [];
let ejec = {};  // último resultado real por escenario
let catalog = [], cmeta = {}; // escenarios SIT y datos de la importación
let reqCfg = null, defaults = {}, qty0 = 1, motivos = {};
let modoSap = false, sistemasModo = "";
const chk = {};
const chkDet = {};        // clave -> detalle del último chequeo (lotes, stock…)           // clave -> estado del último chequeo
let cantidadesOk = {};    // clave -> {material: cantidad} propuestas aceptadas
const picked = new Set();
const movIn = {};             // clave -> movimiento tecleado
const open = new Set();       // filas desplegadas
const fil = {};               // filtros por columna del Excel
let visCols = [];
let curRun = null, curTab = null, curRows = [], poll = null;

function h(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (k === "class") e.className = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v);
  }
  for (const c of kids.flat()) e.append(c instanceof Node ? c : document.createTextNode(c ?? ""));
  return e;
}
const chip = (t, label) => h("span", { class: "chip " + t }, label ?? String(t).replace(/_/g, " "));
const clear = (e) => { while (e.firstChild) e.removeChild(e.firstChild); return e; };
const note = (box, text, err) => {
  clear(box).append(h("div", { class: "msg" + (err ? " err" : "") }, text));
  if (box.id === "sitOut" || box.id === "upOut") {            // son mensajes flotantes: se quitan solos
    clearTimeout(box._t);
    box._t = setTimeout(() => clear(box), err ? 20000 : 7000);
  }
};

async function api(path, opts) {
  const r = await fetch(path, opts);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || "Error " + r.status);
  return j;
}
const post = (path, body) => api(path, { method: "POST", headers: JSONH, body: JSON.stringify(body) });
const q = () => `stream=${sel.stream}&flow=${sel.flow}`;
const etq = () => ((sel && sel.meta.config) || {}).etiquetas || { clase: "Movimiento SAP", paso: "paso 1: MIGO", clase_ejemplo: "311" };
const esSto = () => ((sel && sel.meta.config) || {}).modo === "sto";
const isSit = () => sel && sel.meta.tipo === "sit_jira";

// ---------- pestañas ----------
function setTab(t) {
  $("vPrep").classList.toggle("hide", t !== "prep");
  $("vRes").classList.toggle("hide", t !== "res");
  $("tabPrep").classList.toggle("on", t === "prep");
  $("tabRes").classList.toggle("on", t === "res");
  if (t === "res") loadRuns();
}
$("tabPrep").addEventListener("click", () => setTab("prep"));
$("tabRes").addEventListener("click", () => setTab("res"));

// ---------- flujos ----------
async function loadTree() {
  const t = await api("/api/tree");
  const box = clear($("tree"));
  for (const s of t) {
    box.append(h("div", { class: "stream" }, s.id));
    for (const f of s.flujos)
      box.append(h("div", { class: "flow" + (sel && sel.flow === f.id ? " sel" : ""), onclick: () => selectFlow(s.id, f) },
        f.nombre, h("small", {}, `${f.ejecuciones} ejecución(es)`)));
  }
  return t;
}

async function selectFlow(stream, f) {
  sel = { stream, flow: f.id, meta: f };
  $("flowTitle").textContent = `${stream} › ${f.nombre}`;
  $("flowDesc").textContent = f.descripcion;
  $("flowTitle").title = f.descripcion;
  $("btnImport").classList.toggle("hide", !isSit());
  $("btnPreview").classList.toggle("hide", isSit());
  $("btnRunFile").classList.toggle("hide", isSit());
  $("secSit").classList.toggle("hide", !isSit());
  actualizarBotones();
  for (const id of ["upOut", "nlOut", "sitOut", "preview"]) clear($(id));
  picked.clear(); open.clear(); catalog = []; cmeta = {};
  visCols = (f.config || {}).columnas_por_defecto || [];
  await loadTree();
  await loadFiles();
  if (isSit()) await loadCatalog();
  setTab("prep");
}

// ---------- fichero (una sola tarjeta) ----------
async function loadFiles(select) {
  files = await api(`/api/files?${q()}`);
  const box = clear($("fileSel"));
  if (!files.length) box.append(h("option", { value: "" }, "— sube un Excel —"));
  for (const f of files) box.append(h("option", { value: f.nombre }, `${f.nombre} · ${f.fecha} · ${Math.round(f.bytes / 1024)} KB`));
  if (select) box.value = select;
  updateFileInfo();
}
const curFile = () => $("fileSel").value;

function updateFileInfo() {
  const box = $("fileInfo");
  if (!isSit()) return void (box.textContent = files.length ? "" : "Sube el Excel con los movimientos a probar.");
  box.textContent = cmeta.fichero
    ? `Última importación: «${cmeta.fichero}» (${cmeta.fecha}). Si cambias de fichero, pulsa «Importar escenarios».`
    : "Aún no has importado escenarios: elige el fichero y pulsa «Importar escenarios».";
}

async function upload(file) {
  if (!file) return;
  try {
    await api(`/api/upload?${q()}&name=${encodeURIComponent(file.name)}`, { method: "POST", body: file });
    await loadFiles(file.name);
    note($("upOut"), `«${file.name}» subido. Se guarda solo en tu equipo (data/, fuera de GitHub).`);
  } catch (e) { note($("upOut"), e.message, true); }
}
$("btnUpload").addEventListener("click", () => $("file").click());
$("file").addEventListener("change", (e) => upload(e.target.files[0]));
const card = $("cardFile");
card.addEventListener("dragover", (e) => { e.preventDefault(); card.classList.add("over"); });
card.addEventListener("dragleave", () => card.classList.remove("over"));
card.addEventListener("drop", (e) => { e.preventDefault(); card.classList.remove("over"); upload(e.dataTransfer.files[0]); });

$("btnImport").addEventListener("click", async () => {
  if (!curFile()) return note($("upOut"), "Primero sube un Excel.", true);
  try {
    note($("upOut"), "Importando…");
    await post("/api/sit/import", { stream: sel.stream, flow: sel.flow, file: curFile() });
    picked.clear(); open.clear();
    await loadCatalog();
    note($("upOut"), `Importados ${catalog.length} escenarios dentro del alcance.`);
  } catch (e) { note($("upOut"), e.message, true); }
});

async function showPreview(name) {
  const box = clear($("preview"));
  try {
    const p = await api(`/api/preview?${q()}&file=${encodeURIComponent(name)}`);
    const tb = h("table", {}, h("tr", {}, p.cabeceras.map((x) => h("th", {}, x))));
    for (const r of p.filas) tb.append(h("tr", {}, p.cabeceras.map((x) => h("td", {}, r[x]))));
    const c = h("div", { class: "card" }, h("h2", {}, `${name}: ${p.total} filas (se muestran ${p.filas.length})`));
    if (p.faltan.length) c.append(h("div", { class: "msg err" }, "Faltan columnas obligatorias: " + p.faltan.join(", ")));
    c.append(h("div", { class: "scroll" }, tb));
    box.append(c);
  } catch (e) { note(box, e.message, true); }
}
$("btnPreview").addEventListener("click", () => curFile() && showPreview(curFile()));
$("btnRunFile").addEventListener("click", async () => {
  if (!curFile()) return;
  try {
    const r = await post("/api/run", { stream: sel.stream, flow: sel.flow, file: curFile() });
    setTab("res"); openRun(r.id);
  } catch (e) { note($("upOut"), e.message, true); }
});

// ---------- lenguaje natural: solo propone ----------
$("btnNl").addEventListener("click", async () => {
  const text = $("nl").value.trim();
  if (!text || !sel) return;
  const box = clear($("nlOut"));
  try {
    const r = await post("/api/nl", { text, stream: sel.stream, flow: sel.flow });
    const p = h("div", { class: "prop" });
    if (!r.ok) p.append(r.mensaje);
    if (r.fichero) p.append(h("div", { class: "row" }, h("span", {}, "Fichero propuesto: "), h("b", {}, r.fichero),
      h("button", { class: "sec", onclick: () => { $("fileSel").value = r.fichero; updateFileInfo(); } }, "Usar este fichero")));
    if (r.claves.length || r.mensaje) {
      p.append(h("div", { style: "margin-top:6px" }, r.mensaje));
      for (const x of r.ejemplos) p.append(h("div", { class: "muted" }, "· " + x));
      if (r.claves.length) p.append(h("div", { style: "margin-top:6px" },
        h("button", { onclick: () => selectProposed(r.claves) }, `Seleccionar estos ${r.claves.length} en la tabla`),
        h("span", { class: "muted" }, "  (no se ejecuta nada hasta que pulses «Simular lanzamiento»)")));
    }
    box.append(p);
  } catch (e) { note(box, e.message, true); }
});
$("nl").addEventListener("keydown", (e) => { if (e.key === "Enter") $("btnNl").click(); });

function selectProposed(claves) {
  picked.clear(); claves.forEach((c) => picked.add(c));
  $("sitEst").value = "sel"; $("sitQ").value = "";
  for (const k of Object.keys(fil)) delete fil[k];
  buildFilters((sel.meta.config || {}).filtros_columnas || []);
  renderSit();
  $("secSit").scrollIntoView({ behavior: "smooth" });
}

// ---------- escenarios SIT ----------
async function loadCatalog() {
  const r = await api(`/api/sit/catalog?${q()}`);
  catalog = r.escenarios; cmeta = r.meta || {}; ejec = r.ejecuciones || {};
  reqCfg = r.requisitos; defaults = r.defaults || {}; motivos = r.motivos || {}; qty0 = r.cantidad_por_defecto || 1;
  if (!$("qty").value) $("qty").value = qty0;
  if (catalog.some((e) => !e.fila1 || !e.interpretado || !cmeta.columnas)) {   // catálogo de una versión anterior
    catalog = []; cmeta = {};
    note($("upOut"), "El catálogo guardado es de una versión anterior: pulsa «Importar escenarios» para regenerarlo.", true);
  }
  const cfg = sel.meta.config || {};
  const orden = cmeta.columnas || [];
  if (orden.length && !visCols.some((c) => orden.includes(c))) visCols = cfg.columnas_por_defecto || [];
  const pick = clear($("colPick"));
  for (const c of orden) {
    const cb = h("input", { type: "checkbox" });
    cb.checked = visCols.includes(c);
    cb.addEventListener("change", () => { visCols = orden.filter((x) => (x === c ? cb.checked : visCols.includes(x))); renderSit(); });
    pick.append(h("label", {}, cb, " " + c));
  }
  visCols = orden.filter((c) => visCols.includes(c));   // orden original del Excel
  for (const k of Object.keys(fil)) delete fil[k];
  buildFilters(cfg.filtros_columnas || []);
  renderScope();
  updateFileInfo();
  renderSit();
}

function renderScope() {
  const box = $("scope");
  if (!catalog.length) return void (box.textContent = "Sin escenarios: elige el fichero y pulsa «Importar escenarios».");
  const f = cmeta.filtro || {};
  const alc = Object.entries(f).map(([k, v]) => `${k} = ${[].concat(v).join(" / ")}`).join(" · ") || "sin filtro";
  const fuera = Object.entries(cmeta.excluidos || {});
  box.textContent = `Alcance: ${alc} → ${catalog.length} escenarios. `;
  if (fuera.length) box.append(h("span", { title: fuera.map(([k, v]) => `${k}: ${v}`).join("\n") },
    `Hay ${fuera.reduce((a, [, v]) => a + v, 0)} más fuera de alcance (pasa el ratón para ver cuáles).`));
}

function buildFilters(cols) {
  const box = clear($("filtros"));
  for (const col of cols) {
    const counts = {};
    for (const e of catalog) { const v = e.fila1[col] || "(vacío)"; counts[v] = (counts[v] || 0) + 1; }
    const s = h("select", {}, h("option", { value: "" }, `${col}: todos`),
      ...Object.keys(counts).sort().map((v) => h("option", { value: v }, `${v} (${counts[v]})`)));
    s.addEventListener("input", () => { fil[col] = s.value; renderSit(); });
    box.append(s);
  }
}

function avisos(e) {
  const a = [];
  if (e.requiere_doc_previo) a.push("necesita documento previo (PO/orden)");
  if (!e.datos.materiales.length) a.push("sin material en el Excel");
  if (!e.datos.plantas.length) a.push("sin centro en el Excel");
  return a;
}
const qtyGlobal = () => parseFloat(String($("qty").value).replace(",", ".")) > 0 ? $("qty").value : qty0;
function resolve(e, mov) {
  const req = reqCfg.movimientos[mov] || reqCfg.generico;
  const i = e.interpretado, a = e.aportados || {}, d = defaults[a.centro || i.centro] || {};
  const vals = {}, src = {};
  const put = (f, v, s) => { if (v && (!Array.isArray(v) || v.length)) { vals[f] = v; src[f] = s; return true; } return false; };
  for (const f of Object.keys(reqCfg.campos)) {
    if (f === "material") { const m = (a.material || "").split(/[,\s;]+/).filter(Boolean); put(f, m.length ? m : i.materiales, m.length ? "aportado" : "excel"); continue; }
    if (put(f, a[f], "aportado") || put(f, i[f], "excel")) continue;
    if (f === "centro_destino" && vals.centro && reqCfg.derivar_centro_destino !== false) put(f, vals.centro, "= origen");
    else if (f === "alm_destino" && req.alm_destino_igual_origen && vals.alm_origen) put(f, vals.alm_origen, "= origen");
    else if (!(put(f, d[f], "centro") || put(f, (reqCfg.valores_por_defecto || {})[f], "por defecto")) && f === "cantidad") put(f, String(qtyGlobal()), "global");
  }
  return { req, vals, src, faltan: req.requiere.filter((f) => !vals[f]) };
}
const lab = (f) => reqCfg.campos[f] || f;
function lotesChequeo(e) {
  const d = chkDet[e.clave];
  if (!d || !d.items) return "";
  return d.items.filter((it) => it.asignacion && it.asignacion.length)
    .map((it) => (d.items.length > 1 ? it.material + ": " : "") + it.asignacion.map((a) => `${a.lote} × ${a.cantidad}`).join(" + ")).join(" · ");
}
const lotesSugeridos = (e) => { const d = chkDet[e.clave]; return d && d.items ? [...new Set(d.items.flatMap((it) => (it.asignacion || []).map((a) => a.lote)))].join(", ") : ""; };
const movOf = (e) => movIn[e.clave] ?? (e.confirmado ? e.mov : (e.mov_ambiguo ? "" : (e.movs_candidatos[0] || "")));
const movOk = (m) => /^[0-9A-Z]{3,4}$/.test(m);

function visible() {
  const t = $("sitQ").value.toLowerCase(), est = $("sitEst").value;
  return catalog.filter((e) => {
    for (const [c, v] of Object.entries(fil)) if (v && (e.fila1[c] || "(vacío)") !== v) return false;
    if (t && !Object.values(e.fila1).join(" ").toLowerCase().includes(t)) return false;
    if (est === "pend") return !e.confirmado;
    if (est === "ok") return e.confirmado;
    if (est === "aviso") return avisos(e).length > 0;
    if (est === "falta") return resolve(e, movOf(e)).faltan.length > 0;
    if (est === "sel") return picked.has(e.clave);
    return true;
  });
}

function datosChip(e) {
  const r = resolve(e, movOf(e));
  const ok = !r.faltan.length && !r.req.transaccion;
  const texto = r.req.transaccion ? "NO SOPORTADO" : ok ? "OK" : `NOK · ${r.faltan.length}`;
  const ayuda = r.req.transaccion ? r.req.nota : ok ? "Datos completos. Pulsa para ver o modificar." : "Faltan: " + r.faltan.map(lab).join(", ") + ". Pulsa para completarlos.";
  return h("button", { class: "chipbtn " + (ok ? "OK" : "ERROR"), title: ayuda,
    onclick: () => { open.has(e.clave) ? open.delete(e.clave) : open.add(e.clave); renderSit(); } }, texto);
}

async function guardar(e, inputs, comoCentro) {
  const valores = {};
  for (const [f, inp] of Object.entries(inputs)) if (inp.value.trim() && (f !== "lote" || inp.dataset.dirty)) valores[f] = inp.value.trim();
  try {
    const body = { stream: sel.stream, flow: sel.flow };
    if (comoCentro) { const c = e.interpretado.centro; if (!c) throw new Error("El escenario no tiene centro"); delete valores.cantidad; delete valores.material;
      body.items = []; body.centro_default = { centro: c, valores }; }
    else body.items = [{ clave: e.clave, valores }];
    const r = await post("/api/sit/completar", body);
    const keep = new Map(catalog.map((x) => [x.clave, x]));
    catalog = r.escenarios.map((x) => ({ ...x, confirmado: keep.get(x.clave)?.confirmado ?? x.confirmado, mov: keep.get(x.clave)?.mov ?? x.mov }));
    defaults = r.defaults;
    for (const k of Object.keys(chk)) { delete chk[k]; delete chkDet[k]; }
    note($("sitOut"), comoCentro ? `Guardado como valor por defecto del centro ${e.interpretado.centro}.` : `Datos guardados para ${e.fila1["JIRA ID"]}.`);
    renderSit();
  } catch (err) { note($("sitOut"), err.message, true); }
}

function planSap(e, r, mov) {
  const val = (f) => { const x = r.vals[f]; return x ? (Array.isArray(x) ? x.join(", ") : x) : null; };
  const par = (a, b) => (val(a) && val(b) ? `${val(a)} / ${val(b)}` : null);
  const kv = (rows) => h("div", { style: "margin-left:14px" }, ...rows.map(([k, x, nota]) => h("div", {}, h("span", { class: "muted" }, k + ": "),
    x ? h("b", {}, x) : chip("ERROR", "FALTA"), nota ? h("span", { class: "muted" }, " " + nota) : "")));
  const paso = (n, trans, titulo, filas, nota) => h("div", { style: "margin-bottom:8px" }, h("div", {}, h("b", {}, `${n}. ${trans}`), " · " + titulo), kv(filas),
    nota ? h("div", { class: "muted", style: "margin-left:14px" }, nota) : "");
  const box = h("div", { style: "margin-top:10px;padding:8px 10px;border:1px dashed var(--pri);border-radius:6px;background:#f8faff" },
    h("h3", { style: "margin-top:0" }, "Qué haría en SAP si se lanzara ahora"));
  if (r.req.transaccion) return box.appendChild(h("div", {}, chip("ERROR", "No soportado"), " " + r.req.nota)) && box;
  if (!movOk(mov)) return box.appendChild(h("div", { class: "muted" }, `Indica antes ${etq().clase.toLowerCase()} para ver el plan.`)) && box;
  const wm = ["S", "SI", "SÍ", "Y", "YES", "1"].includes(String(r.vals.wm || "").toUpperCase());
  const cant = r.src.cantidad === "global" ? "(por defecto; con SAP se propondrá desde el stock y la confirmas tú)" : `(${r.src.cantidad})`;
  if (esSto()) {
    box.append(
      paso(1, "ME13", "Comprobar el registro info de cada material", [["Materiales", val("material")], ["Proveedor", `vendor del centro ${val("centro") || "—"}`, "(se lee en SAP)"],
        ["Org. compras", val("org_compras")], ["Centro", val("centro")]], "Si falta alguno, se para el escenario y se avisa (darlo de alta con ME11 sería manual)."),
      paso(2, wm ? "LS24 / LX02" : "MB52", wm ? "Buscar stock libre en cuantos WM" : "Buscar stock libre", [["Centro / almacén suministrador", par("centro", "alm_origen")],
        ["Lote", val("lote") || lotesChequeo(e) || "FEFO / FIFO: el primero con stock", val("lote") ? "(indicado por ti)" : lotesChequeo(e) ? "(según el chequeo)" : ""], ["Cantidad", val("cantidad"), cant]], "Si el stock no llega, se traslada lo disponible (parcial)."),
      paso(3, "ME21N", `Crear el pedido de traslado ${mov}`, [["Org. compras / grupo / sociedad", val("org_compras") && val("grupo_compras") && val("sociedad") ? `${val("org_compras")} / ${val("grupo_compras")} / ${val("sociedad")}` : null],
        ["Centro suministrador", val("centro")], ["Centro / almacén receptor", par("centro_destino", "alm_destino")], ["Posiciones", val("material") ? `${val("material")} · cantidad ${val("cantidad") || "—"} · lote del paso 2` : null]]),
      paso(4, "VL10B", "Crear la entrega de salida desde los pedidos pendientes de entrega", [["Selección", `el STO creado en el paso 3 · centro suministrador ${val("centro") || "—"}`],
        ["Punto de expedición", val("punto_expedicion") || "sin indicar: lo toma SAP del centro suministrador"], ["Posiciones", "las del STO, con su lote"]],
        "Se marca el STO y se crea la entrega. La fase 1 termina aquí: no se hace picking (VL02N) ni salida de mercancía. Los pasos siguientes del Excel se entregan para validar."));
  } else {
    const extra = r.req.requiere.filter((f) => !["centro", "alm_origen", "material", "cantidad", "centro_destino", "alm_destino"].includes(f)).map((f) => [lab(f), val(f)]);
    box.append(
      paso(1, "MB52", "Buscar stock libre y lote", [["Centro / almacén origen", par("centro", "alm_origen")], ["Material(es)", val("material")], ["Lote", val("lote") || lotesChequeo(e) || "FEFO / FIFO: el primero con stock", val("lote") ? "(indicado por ti)" : lotesChequeo(e) ? "(según el chequeo)" : ""],
        ["Cantidad", val("cantidad"), cant]], "Si el stock no llega, se mueve lo disponible (parcial)."),
      paso(2, "MIGO", `Contabilizar el movimiento ${mov}${r.req.nombre ? " · " + r.req.nombre : ""}`, [["Centro / almacén origen", par("centro", "alm_origen")],
        ...(r.req.requiere.includes("centro_destino") || r.req.requiere.includes("alm_destino") ? [["Centro / almacén destino", par("centro_destino", "alm_destino") || (val("alm_destino") ? `${val("centro_destino") || val("centro")} / ${val("alm_destino")}` : null)]] : []),
        ...extra]),
      paso(3, "FB03 / KE24 / CKM3N", "Leer el resultado", [["Se leen", "documento de material y sus apuntes FI, CO y ML"]], "Se entregan a los equipos que validan."));
  }
  return box;
}

function campoEntrada(f, v, mov, placeholder) {
  const valor = Array.isArray(v) ? v.join(", ") : (v || "");
  if (f === "motivo" && motivos[mov]) {                      // motivo: desplegable con los valores válidos del movimiento
    const s = h("select", { style: "width:100%" }, h("option", { value: "" }, "— elige el motivo —"),
      ...motivos[mov].map((m) => h("option", { value: m.codigo }, `${m.codigo} · ${m.texto}`)));
    s.value = valor;
    return s;
  }
  const inp = h("input", { type: "text", style: "width:100%", placeholder });
  inp.value = valor;
  return inp;
}

function detailRow(e, span) {
  const d = e.datos;
  const mov = movOf(e);
  const r = resolve(e, mov);
  const inputs = {};
  const form = h("div", {}, h("h3", { style: "margin-top:0" }, `Datos para ${etq().clase.toLowerCase()} ${mov || "—"}${r.req.nombre ? " · " + r.req.nombre : ""}`));
  if (r.req.desconocido) form.append(h("div", {}, chip("WARN", "Aviso"), " " + r.req.nota));
  if (r.req.transaccion) form.append(h("div", {}, chip("ERROR", "No soportado"), " " + r.req.nota));
  else if (r.req.nota && !r.req.desconocido) form.append(h("div", { class: "muted" }, r.req.nota));
  const grid = h("div", { style: "display:grid;grid-template-columns:150px 1fr auto;gap:5px 8px;align-items:center;margin-top:6px" });
  for (const f of r.req.requiere) {
    const v = r.vals[f];
    const inp = campoEntrada(f, v, mov, v ? "" : "obligatorio");
    inputs[f] = inp;
    inp.addEventListener("change", () => guardar(e, { [f]: inp }, false));   // se guarda al salir del campo o con Intro
    grid.append(h("span", {}, lab(f)), inp, v ? h("span", { class: "muted" }, r.src[f]) : chip("ERROR", "falta"));
  }
  for (const f of r.req.opcionales || []) {
    const inp = h("input", { type: "text", style: "width:100%", placeholder: "opcional" });
    inp.value = Array.isArray(r.vals[f]) ? r.vals[f].join(", ") : (r.vals[f] || "");
    inputs[f] = inp;
    inp.addEventListener("change", () => guardar(e, { [f]: inp }, false));
    grid.append(h("span", { class: "muted" }, lab(f) + " (opcional)"), inp, h("span", { class: "muted" }, r.vals[f] ? r.src[f] : ""));
  }
  if (motivos[mov] && !r.req.requiere.includes("motivo") && !(r.req.opcionales || []).includes("motivo")) {   // movimiento con motivos definidos pero no obligatorio
    const sel = campoEntrada("motivo", r.vals.motivo, mov, "opcional");
    sel.addEventListener("change", () => guardar(e, { motivo: sel }, false));
    inputs.motivo = sel;
    grid.append(h("span", { class: "muted" }, "Motivo del movimiento (opcional)"), sel, h("span", { class: "muted" }, r.vals.motivo ? r.src.motivo : ""));
  }
  if (reqCfg.campos.lote) {
    const sug = lotesSugeridos(e);
    const aport = (e.aportados || {}).lote || "";
    const inp = h("input", { type: "text", style: "width:100%", placeholder: sug ? "" : "opcional · si lo dejas vacío se elige FEFO/FIFO" });
    inp.value = aport || sug;
    inp.addEventListener("input", () => { inp.dataset.dirty = "1"; });
    inp.addEventListener("change", () => guardar(e, { lote: inp }, false));
    inputs.lote = inp;
    grid.append(h("span", { class: "muted" }, "Lote (opcional)"), inp,
      h("span", { class: "muted" }, aport ? "indicado por ti" : sug ? "propuesto por el chequeo (FEFO/FIFO)" : "sin chequeo"));
  }
  form.append(grid, h("div", { class: "muted", style: "margin-top:6px" }, "Los cambios se guardan al salir del campo o al pulsar Intro."), h("div", { class: "row", style: "margin-top:8px" },
    h("button", { onclick: () => guardar(e, inputs, false) }, "Guardar en este escenario"),
    h("button", { class: "sec", onclick: () => guardar(e, inputs, true), title: "Se aplicará a todos los escenarios de este centro que no traigan el dato" },
      `Guardar como valor del centro ${e.interpretado.centro || "—"}`)));
  form.append(planSap(e, r, mov));
  form.append(h("div", { class: "muted", style: "margin-top:6px" }, e.mov_origen + (e.mov_nota ? " · " + e.mov_nota : "")),
    ...avisos(e).map((a) => h("div", {}, chip("WARN", "Aviso"), " " + a)),
    h("h3", {}, `Datos del Excel (${etq().paso})`), h("pre", {}, e.fila1["Data"] || ""),
    h("h3", {}, "Resultado esperado"), h("pre", {}, e.fila1["Expected result"] || ""));
  const FASE = { previo: ["WARN", "previo, no se automatiza"], sto: ["OK", "se ejecuta: STO"], entrega: ["OK", "se ejecuta: entrega"], posterior: ["INFO", "se entrega para validar"] };
  const right = h("div", {}, h("h3", { style: "margin-top:0" }, esSto() ? `Pasos del escenario (${e.pasos.length})` : `Pasos siguientes: se entregan para validar (${e.pasos.length})`),
    ...e.pasos.map((p) => h("div", { style: "margin-bottom:6px" }, h("b", {}, `Paso ${p.paso} · ${p.transacciones.join(" / ")} `),
      p.fase ? chip(FASE[p.fase][0], FASE[p.fase][1]) : chip("INFO", p.categorias.join(", ")), h("div", { class: "muted" }, p.descripcion.slice(0, 220)))));
  return h("tr", { class: "det" }, h("td", { colspan: String(span) }, h("div", { class: "grid2" }, form, right)));
}

// Reconstruir la tabla no debe mover lo que el usuario está viendo: se conserva el scroll de la página y el de la propia tabla.
function conservarVista(fn) {
  const caja = document.querySelector("#secSit .scroll");
  const y = window.scrollY, x = window.scrollX, top = caja ? caja.scrollTop : 0, left = caja ? caja.scrollLeft : 0;
  const prev = document.body.style.minHeight;
  document.body.style.minHeight = document.documentElement.scrollHeight + "px";   // evita que el navegador recorte el scroll mientras la tabla está vacía
  try { fn(); } finally {
    if (caja) { caja.scrollTop = top; caja.scrollLeft = left; }
    window.scrollTo(x, y);
    document.body.style.minHeight = prev;
  }
}

function confirmarContabilizar(sistema, lineas, excluidos, yaHechos) {
  return new Promise((resolve) => {
    const cerrar = (v) => { fondo.remove(); document.removeEventListener("keydown", tecla); resolve(v); };
    const tecla = (ev) => { if (ev.key === "Escape") cerrar(false); };
    const filas = lineas.map((l) => h("li", { style: "margin:2px 0" }, l));
    const caja = h("div", { style: "background:#fff;border-radius:10px;max-width:1100px;width:92vw;max-height:86vh;display:flex;flex-direction:column;box-shadow:0 10px 40px rgba(0,0,0,.4)" },
      h("div", { style: "padding:14px 18px;border-bottom:1px solid #ddd;font-weight:700;color:#b42318" }, `Contabilizar DE VERDAD en SAP (${sistema}): se crearán ${lineas.length} documento(s) de material`),
      h("div", { style: "padding:10px 18px;overflow:auto;font-size:13px" },
        h("ul", { style: "margin:0;padding-left:18px" }, ...filas),
        yaHechos.length ? h("p", { style: "color:#b54708;font-weight:600" }, `Ojo: ya constan como ejecutados (se volverían a contabilizar): ${yaHechos.join(", ")}`) : "",
        excluidos.length ? h("p", { class: "muted" }, `No se contabilizan ${excluidos.length}: ` + excluidos.slice(0, 6).join(" | ")) : "",
        h("p", { class: "muted" }, "Esto MODIFICA datos en el sistema (stock y documentos). Solo se contabilizan exactamente estos datos: si algo cambia, el servidor lo rechaza.")),
      h("div", { style: "padding:12px 18px;border-top:1px solid #ddd;display:flex;gap:10px;justify-content:flex-end" },
        h("button", { class: "sec", onclick: () => cerrar(false) }, "Cancelar"),
        h("button", { style: "background:#b42318", id: "btnConfirmaCont", onclick: () => cerrar(true) }, `Contabilizar ${lineas.length} documento${lineas.length === 1 ? "" : "s"}`)));
    const fondo = h("div", { style: "position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:1000;display:flex;align-items:center;justify-content:center" }, caja);
    document.addEventListener("keydown", tecla);
    document.body.append(fondo);
    caja.querySelector("button.sec").focus();      // el foco empieza en «Cancelar»: Intro no contabiliza
  });
}

function renderSit() { conservarVista(renderSitInterno); }

function renderSitInterno() {
  const vis = visible();
  const tb = clear($("sitTable"));
  const span = visCols.length + 5;
  tb.append(h("tr", {}, h("th", {}, ""), h("th", {}, ""), ...visCols.map((c) => h("th", {}, c)),
    h("th", { class: "app" }, "Datos"), h("th", { class: "app" }, etq().clase), h("th", { class: "app" }, "Avisos")));
  for (const e of vis) {
    const cb = h("input", { type: "checkbox" });
    cb.checked = picked.has(e.clave);
    cb.addEventListener("change", () => { cb.checked ? picked.add(e.clave) : picked.delete(e.clave); barInfo(); });
    const isOpen = open.has(e.clave);
    const tog = h("button", { class: "sec", style: "padding:1px 7px", title: "Ver detalle y completar datos",
      onclick: () => { isOpen ? open.delete(e.clave) : open.add(e.clave); renderSit(); } }, isOpen ? "▾" : "▸");
    const inp = h("input", { type: "text", maxlength: "4", style: "width:62px;text-align:center" });
    inp.value = movOf(e);
    inp.title = e.movs_candidatos.length ? "Propuesta: " + e.movs_candidatos.join(", ") : "Sin propuesta: indícalo tú";
    inp.addEventListener("change", () => { movIn[e.clave] = inp.value.toUpperCase(); delete chk[e.clave]; delete chkDet[e.clave]; renderSit(); });
    const est = e.confirmado ? chip("CONFIRMADO", "confirmado") : (movOf(e) ? chip("PROPUESTO", "propuesto") : chip("SIN_PROPUESTA", "sin propuesta"));
    const r = resolve(e, movOf(e));
    const av = [...avisos(e).filter((a) => !a.startsWith("sin material") && !a.startsWith("sin centro")),
      r.req.desconocido ? "requisitos del movimiento sin definir" : "",
      r.req.destino_distinto && r.src.centro_destino === "= origen" ? "traslado entre centros con el mismo centro: ¿falta el centro destino?" : "", r.req.transaccion ? "no se hace con MIGO (" + r.req.transaccion + ")" : ""].filter(Boolean);
    tb.append(h("tr", {}, h("td", {}, cb), h("td", {}, tog), ...visCols.map((c) => h("td", {}, h("div", { class: "cell" }, e.fila1[c] || ""))),
      h("td", {}, datosChip(e)), h("td", {}, inp, " ", est, ejec[e.clave] ? [" ", chip({ OK: "OK", KO: "ERROR", REVISAR: "PARCIAL" }[ejec[e.clave].estado] || "PARCIAL", `EJECUTADO ${ejec[e.clave].estado}${ejec[e.clave].documento ? " · " + ejec[e.clave].documento : ""}`)] : ""), h("td", {}, chk[e.clave] ? [chip(chk[e.clave], "chequeo: " + chk[e.clave].toLowerCase().replace(/_/g, " ")), " ", ((e.aportados || {}).lote || lotesChequeo(e)) ? h("span", { class: "muted" }, "lote " + ((e.aportados || {}).lote || lotesChequeo(e)) + " ") : ""] : "", av.join(" · "))));
    if (isOpen) tb.append(detailRow(e, span));
  }
  $("sitCount").textContent = `${vis.length} de ${catalog.length} escenarios visibles`;
  barInfo();
}

function barInfo() {
  const s = catalog.filter((e) => picked.has(e.clave));
  const ok = s.filter((e) => movOk(movOf(e))).length;
  const falta = s.filter((e) => resolve(e, movOf(e)).faltan.length).length;
  $("barInfo").textContent = `${s.length} seleccionados · ${ok} con movimiento válido · ${falta} con datos pendientes`;
  $("btnRunSit").disabled = !s.length;
}

for (const id of ["sitQ", "sitEst"]) $(id).addEventListener("input", renderSit);
$("sitEst").append(h("option", { value: "sel" }, "Solo seleccionados"));
$("btnSelVis").addEventListener("click", () => { visible().forEach((e) => picked.add(e.clave)); renderSit(); });
$("btnSelNone").addEventListener("click", () => { picked.clear(); renderSit(); });


// ---------- chequeo previo (solo lectura) ----------
async function chequear() {
  const items = catalog.filter((e) => picked.has(e.clave));
  if (!items.length) return note($("sitOut"), "Selecciona escenarios para chequear.", true);
  const sinTipo = items.filter((e) => !movOk(movOf(e)));
  if (sinTipo.length) return note($("sitOut"), `Indica antes ${etq().clase.toLowerCase()} (p. ej. ${etq().clase_ejemplo}) en ${sinTipo.length} escenario(s): ` +
    sinTipo.slice(0, 8).map((e) => e.fila1["JIRA ID"]).join(", ") + (sinTipo.length > 8 ? "…" : ""), true);
  const box = clear($("chkOut"));
  note($("sitOut"), "Chequeando… (no se contabiliza nada)");
  try {
    const movs = Object.fromEntries(items.map((e) => [e.clave, movOf(e)]));
    const r = await post("/api/sit/chequear", { stream: sel.stream, flow: sel.flow, claves: items.map((e) => e.clave), cantidad: qtyGlobal(), movs });
    clear($("sitOut"));
    for (const f of r.filas) { chk[f.clave] = f.estado; chkDet[f.clave] = f; }
    const cuenta = {};
    r.filas.forEach((f) => { cuenta[f.estado] = (cuenta[f.estado] || 0) + 1; });
    const card = h("div", { class: "prop" }, h("h3", { style: "margin-top:0" }, `Chequeo de ${r.filas.length} escenario(s) · solo lectura`),
      h("div", { class: "row" }, ...Object.entries(cuenta).map(([k, n]) => h("span", {}, chip(k, k === "LISTO" ? "LISTO" : k.replace(/_/g, " ")), ` ${n}`))));
    if (r.simulado) card.append(h("div", { class: "muted" }, "Chequeo SIMULADO: stock y registros info son inventados; sirve para ver el formato y detectar datos pendientes."));
    else card.append(h("div", { class: "muted" }, `Chequeo con SAP real (${(r.sistema || {}).sistema || "—"}/${(r.sistema || {}).mandante || "—"}) · solo lectura. Lotes ordenados por número de lote: MB52 no da caducidad ni fecha de entrada. El registro info aún no se comprueba contra SAP.`));
    if (!r.puede_proponer) card.append(h("div", { class: "muted" }, `La propuesta de cantidad desde el stock estará disponible al conectar con SAP. De momento se usa la cantidad por defecto (${qtyGlobal()}) cuando no la indiques.`));
    const th = ["JIRA ID", "External ID - JIRA", etq().clase, "Estado", "Material", ...(esSto() ? ["Registro info"] : []), "Stock libre", "Lote (FEFO/FIFO)", "Cantidad", "Propuesta", "Detalle"];
    const tb = h("table", {}, h("tr", {}, th.map((x) => h("th", {}, x))));
    const propuestas = {};
    for (const f of r.filas) {
      const det = [f.faltan.length ? "Faltan: " + f.faltan.join(", ") : "", ...f.avisos].filter(Boolean).join(" · ");
      const rows = f.items.length ? f.items : [null];
      rows.forEach((it, i) => {
        if (it && it.cantidad_propuesta != null) (propuestas[f.clave] = propuestas[f.clave] || {})[it.material] = it.cantidad_propuesta;
        tb.append(h("tr", {}, h("td", {}, f.jira_id), h("td", {}, f.id_jira_unidad), h("td", {}, f.mov), h("td", {}, i === 0 ? chip(f.estado) : ""),
          h("td", {}, it ? it.material : ""),
          ...(esSto() ? [h("td", {}, it ? (it.registro_info === null ? h("span", { class: "muted" }, "no comprobado") : it.registro_info ? chip("OK", "OK") : chip("ERROR", "FALTA (ME11)")) : "")] : []),
          h("td", {}, it ? (it.stock === null ? "—" : `${it.stock} (${it.fuente_stock})`) : ""), h("td", {}, it ? (it.asignacion && it.asignacion.length ? it.asignacion.map((a) => `${a.lote} × ${a.cantidad}`).join(" + ") + (it.sin_cubrir ? ` (faltan ${it.sin_cubrir})` : "") : "—") : ""),
          h("td", {}, it ? `${it.cantidad} (${it.cantidad_origen})` : ""), h("td", {}, it && it.cantidad_propuesta != null ? `${it.cantidad_propuesta} · lote ${it.lote_propuesto}` : ""),
          h("td", {}, i === 0 ? det : "")));
      });
    }
    card.append(h("div", { class: "scroll", style: "max-height:300px;margin-top:8px" }, tb));
    if (Object.keys(propuestas).length) card.append(h("div", { class: "row", style: "margin-top:8px" },
      h("button", { onclick: () => { cantidadesOk = propuestas; note($("sitOut"), "Cantidades propuestas aceptadas: se usarán al simular el lanzamiento."); } }, "Usar las cantidades propuestas"),
      h("span", { class: "muted" }, "Si no las aceptas, se usa la cantidad por defecto.")));
    card.append(h("div", { style: "margin-top:8px" }, h("button", { class: "sec", onclick: () => clear($("chkOut")) }, "Cerrar informe")));
    box.append(card);
    renderSit();
  } catch (e) { note($("sitOut"), e.message, true); }
}
$("btnChk").addEventListener("click", chequear);

$("btnPost").addEventListener("click", async () => {
  const todos = catalog.filter((e) => picked.has(e.clave)).map((e) => ({ e, mov: movOf(e) }));
  if (!todos.length) return;
  const malos = todos.filter((i) => !movOk(i.mov));
  if (malos.length) return note($("sitOut"), `Falta indicar ${etq().clase.toLowerCase()} en ${malos.length} escenario(s): ` + malos.slice(0, 8).map((i) => i.e.fila1["JIRA ID"]).join(", "), true);
  try {
    await post("/api/sit/confirm", { stream: sel.stream, flow: sel.flow, items: todos.map((i) => ({ clave: i.e.clave, mov: i.mov })) });
    todos.forEach((i) => { i.e.confirmado = true; i.e.mov = i.mov; });
    note($("sitOut"), "Preparando los datos exactos (lee el stock en SAP)…");
    const r = await post("/api/sit/preparar", { stream: sel.stream, flow: sel.flow, claves: todos.map((i) => i.e.clave), cantidad: qtyGlobal() });
    const ok = r.documentos.filter((d) => d.ok), no = r.documentos.filter((d) => !d.ok);
    if (!ok.length) return note($("sitOut"), "Ninguno se puede contabilizar: " + no.slice(0, 4).map((d) => `${d.jira_id}: ${d.problema}`).join(" | "), true);
    if (ok.length > r.maximo) return note($("sitOut"), `Máximo ${r.maximo} documentos por ejecución: has seleccionado ${ok.length}.`, true);
    const lineas = ok.map((d) => `• ${d.jira_id} · mov ${d.mov} · material ${d.material} · centro ${d.centro} · almacén ${d.almacen}${d.almacen_destino ? " → " + d.almacen_destino : ""} · lote ${d.lote || "sin lote"} · cantidad ${d.cantidad} · motivo ${d.motivo ? d.motivo + " (" + (((motivos[d.mov] || []).find((m) => m.codigo === d.motivo) || {}).texto || "?") + ")" : "—"}   [huella ${d.huella}]`);
    const yaHechos = ok.filter((d) => ejec[d.clave] && ejec[d.clave].estado === "OK").map((d) => d.jira_id);
    const okUser = await confirmarContabilizar(sistemasModo, lineas, no.map((d) => `${d.jira_id}: ${d.problema}`), yaHechos);
    if (!okUser) return note($("sitOut"), "Cancelado: no se ha contabilizado nada.");
    const huellas = Object.fromEntries(ok.map((d) => [d.clave, d.huella]));
    const res = await post("/api/sit/contabilizar", { stream: sel.stream, flow: sel.flow, claves: ok.map((d) => d.clave), huellas, cantidad: qtyGlobal(), confirmacion: "CONTABILIZAR" });
    for (const k of Object.keys(chk)) { delete chk[k]; delete chkDet[k]; }
    renderSit();
    setTab("res"); openRun(res.id);
  } catch (e) { note($("sitOut"), e.message, true); }
});

$("qty").addEventListener("change", () => { for (const k of Object.keys(chk)) { delete chk[k]; delete chkDet[k]; } cantidadesOk = {}; renderSit(); });
$("btnRunSit").addEventListener("click", async () => {
  const todos = catalog.filter((e) => picked.has(e.clave)).map((e) => ({ e, mov: movOf(e) }));
  const malos = todos.filter((i) => !movOk(i.mov));
  if (malos.length) return note($("sitOut"), `Falta indicar ${etq().clase.toLowerCase()} (p. ej. ${etq().clase_ejemplo}) en ${malos.length} escenario(s): ` +
    malos.slice(0, 8).map((i) => i.e.fila1["JIRA ID"]).join(", ") + (malos.length > 8 ? "…" : ""), true);
  const BLOQ = ["SIN_REGISTRO_INFO", "SIN_STOCK", "ERROR_SAP"];   // el chequeo ya dijo que no se puede ejecutar
  const excl = todos.filter((i) => BLOQ.includes(chk[i.e.clave]));
  const items = todos.filter((i) => !BLOQ.includes(chk[i.e.clave]));
  if (!items.length) return note($("sitOut"), "Todos los escenarios seleccionados quedaron bloqueados por el chequeo (sin registro info, sin stock o error de SAP). Revisa el informe.", true);
  const rs = items.map((i) => resolve(i.e, i.mov));
  const noSop = rs.filter((r) => r.req.transaccion).length;
  const falta = rs.filter((r) => !r.req.transaccion && r.faltan.length).length;
  const resumen = {};
  items.forEach((i) => { resumen[i.mov] = (resumen[i.mov] || 0) + 1; });
  const sinChk = items.filter((i) => !chk[i.e.clave]).length;
  const txt = `Vas a SIMULAR el lanzamiento de ${items.length} escenario(s).\n\nNO se contabiliza nada en SAP: los stocks, lotes y documentos del resultado serán INVENTADOS.\n\n` +
    (modoSap ? "AVISO: el chequeo usa SAP real, pero el lanzamiento todavía es simulado: no contabiliza nada en SAP.\n\n" : "") +
    (sinChk ? `AVISO: ${sinChk} escenario(s) sin chequear (botón «Chequear datos»: comprueba datos, registro info y stock sin contabilizar).\n` : "") +
    (excl.length ? `${excl.length} se EXCLUYEN del lanzamiento porque el chequeo dio sin registro info, sin stock o error de SAP.
` : "") +
    `${etq().clase}: ${Object.entries(resumen).map(([m, n]) => `${m} × ${n}`).join(", ")}\nCantidad por defecto: ${qtyGlobal()}\n` +
    (falta ? `${falta} tienen datos pendientes y no se ejecutarán (FALTAN DATOS).\n` : "") +
    (noSop ? `${noSop} no se hacen con MIGO (NO SOPORTADO).\n` : "") + (esSto() ? "\nFase 1: se valida registro info, se busca lote con stock y se crean el STO y la entrega de salida." : "") + `\n¿Confirmas y lanzas?`;
  if (!window.confirm(txt)) return;
  try {
    await post("/api/sit/confirm", { stream: sel.stream, flow: sel.flow, items: items.map((i) => ({ clave: i.e.clave, mov: i.mov })) });
    const r = await post("/api/sit/run", { stream: sel.stream, flow: sel.flow, claves: items.map((i) => i.e.clave), cantidad: qtyGlobal(), cantidades: cantidadesOk });
    items.forEach((i) => { i.e.confirmado = true; i.e.mov = i.mov; });
    clear($("sitOut")); renderSit();
    setTab("res"); openRun(r.id);
  } catch (e) { note($("sitOut"), e.message, true); }
});

// ---------- resultados ----------
async function loadRuns() {
  let runs = await api("/api/runs");
  const all = $("runsAll").checked;
  if (!all && sel) runs = runs.filter((r) => r.flujo === sel.flow && r.stream === sel.stream);
  $("resCount").textContent = runs.length ? `(${runs.length})` : "";
  $("runsTitle").textContent = all || !sel ? "Ejecuciones de todos los flujos" : "Ejecuciones de este flujo";
  const box = clear($("runs"));
  if (!runs.length) return void (box.textContent = "Sin ejecuciones todavía.");
  const tb = h("table", {}, h("tr", {}, ["Inicio", "Flujo", "Origen", "Estado", "OK", "Parcial", "Sin stock", "Error", "Faltan datos", "Sin reg. info", "No soportado"].map((x) => h("th", {}, x))));
  for (const r of runs) {
    const s = r.resumen || {};
    tb.append(h("tr", { style: "cursor:pointer", onclick: () => openRun(r.id) }, h("td", {}, r.inicio), h("td", {}, r.flujo), h("td", {}, r.fichero),
      h("td", {}, chip(r.estado), r.simulado ? " simulado" : ""), h("td", {}, s.OK ?? s.CONTABILIZADO ?? ""), h("td", {}, s.PARCIAL ?? ""),
      h("td", {}, s.SIN_STOCK ?? ""), h("td", {}, s.ERROR ?? ""), h("td", {}, s.FALTAN_DATOS ?? ""), h("td", {}, s.SIN_REGISTRO_INFO ?? ""), h("td", {}, s.NO_SOPORTADO ?? "")));
  }
  box.append(tb);
}
$("runsAll").addEventListener("change", loadRuns);

const TABS_SIT = {
  escenarios: ["Escenarios", [["jira_id", "JIRA ID"], ["id_jira_unidad", "External ID - JIRA"], ["unidad", "Location by Unit"], ["escenario", "Test Scenario"], ["mov", "Mov."], ["estado", "Estado"], ["detalle", "Detalle"]]],
  mm: ["MM · Movimientos", [["jira_id", "JIRA ID"], ["id_jira_unidad", "External ID - JIRA"], ["escenario", "Test Scenario"], ["mov", "Mov."], ["material", "Material"], ["centro", "Centro"], ["almacen", "Almacén"], ["centro_destino", "Centro destino"], ["alm_destino", "Almacén destino"], ["vendor", "Vendor"], ["ceco", "CECO"], ["orden", "Orden"], ["pedida", "Pedida"], ["movida", "Movida"], ["estado", "Estado"], ["documentos", "Doc. material (lote×cant.)"], ["detalle", "Detalle"], ["nota", "Nota"]]],
  fi: ["FI · Apuntes", [["jira_id", "JIRA ID"], ["id_jira_unidad", "External ID - JIRA"], ["doc_material", "Doc. material"], ["doc_fi", "Doc. FI"], ["pos", "Pos."], ["cuenta", "Cuenta"], ["dc", "D/H"], ["importe", "Importe"], ["moneda", "Moneda"], ["centro_coste", "Centro coste"]]],
  co: ["CO · Imputaciones", [["jira_id", "JIRA ID"], ["id_jira_unidad", "External ID - JIRA"], ["doc_material", "Doc. material"], ["objeto_co", "Objeto CO"], ["clase_coste", "Clase coste"], ["valor", "Valor"], ["moneda", "Moneda"]]],
  ml: ["ML · Valoración", [["jira_id", "JIRA ID"], ["id_jira_unidad", "External ID - JIRA"], ["doc_material", "Doc. material"], ["material", "Material"], ["centro", "Centro"], ["control_precio", "Ctrl. precio"], ["precio", "Precio"], ["cantidad", "Cantidad"], ["valor", "Valor"], ["diferencia_precio", "Dif. precio"], ["moneda", "Moneda"]]],
  pasos: ["Pasos a validar", [["jira_id", "JIRA ID"], ["id_jira_unidad", "External ID - JIRA"], ["paso", "Paso"], ["equipo", "Equipo"], ["transacciones", "Transacciones"], ["descripcion", "Descripción"], ["esperado", "Resultado esperado"]]],
};
const TABS_STO = {
  escenarios: ["Escenarios", [["jira_id", "JIRA ID"], ["id_jira_unidad", "External ID - JIRA"], ["unidad", "Location by Unit"], ["escenario", "Test Scenario"], ["mov", "Tipo doc."], ["estado", "Estado"], ["sto", "STO"], ["entrega", "Entrega"], ["detalle", "Detalle"]]],
  sto: ["STO creados", [["jira_id", "JIRA ID"], ["id_jira_unidad", "External ID - JIRA"], ["sto", "STO"], ["tipo", "Tipo"], ["centro_suministrador", "Centro sumin."], ["alm_suministrador", "Alm. sumin."], ["wm", "WM"], ["centro_receptor", "Centro receptor"], ["alm_receptor", "Alm. receptor"], ["material", "Material"], ["lote", "Lote"], ["cantidad", "Cantidad"], ["registro_info", "Registro info"], ["org_compras", "Org. compras"], ["grupo_compras", "Grupo compras"], ["sociedad", "Sociedad"], ["fuente_stock", "Stock desde"]]],
  entregas: ["Entregas de salida", [["jira_id", "JIRA ID"], ["id_jira_unidad", "External ID - JIRA"], ["entrega", "Entrega"], ["sto", "STO"], ["centro_suministrador", "Centro sumin."], ["alm_suministrador", "Alm. sumin."], ["material", "Material"], ["lote", "Lote"], ["cantidad", "Cantidad"], ["wm", "WM"]]],
  pasos: ["Pasos del escenario", [["jira_id", "JIRA ID"], ["id_jira_unidad", "External ID - JIRA"], ["paso", "Paso"], ["fase", "Fase"], ["equipo", "Equipo"], ["transacciones", "Transacciones"], ["descripcion", "Descripción"], ["esperado", "Resultado esperado"]]],
};
const TABS_REAL = {
  escenarios: ["Documentos", [["jira_id", "JIRA ID"], ["id_jira_unidad", "External ID - JIRA"], ["escenario", "Test Scenario"], ["mov", "Mov."], ["estado", "Estado"], ["detalle", "Detalle"]]],
  mm: ["MM · Movimientos", [["jira_id", "JIRA ID"], ["id_jira_unidad", "External ID - JIRA"], ["mov", "Mov."], ["material", "Material"], ["centro", "Centro"], ["almacen", "Almacén"], ["almacen_destino", "Alm. destino"], ["lote", "Lote"], ["motivo", "Motivo"], ["pedida", "Cantidad"], ["estado", "Estado"], ["documentos", "Doc. material"], ["stock_antes", "Stock antes (MB52)"], ["stock_despues", "Stock después (MB52)"], ["detalle", "Mensaje de SAP"]]],
  fi: ["FI · Documentos", [["jira_id", "JIRA ID"], ["id_jira_unidad", "External ID - JIRA"], ["doc_material", "Doc. material"], ["doc_fi", "Doc. FI"], ["sociedad", "Sociedad"]]],
  co: ["CO · Documentos", [["jira_id", "JIRA ID"], ["id_jira_unidad", "External ID - JIRA"], ["doc_material", "Doc. material"], ["doc_co", "Doc. CO"], ["sociedad", "Sociedad"]]],
  ml: ["ML · Documentos", [["jira_id", "JIRA ID"], ["id_jira_unidad", "External ID - JIRA"], ["doc_material", "Doc. material"], ["doc_ml", "Doc. ML"]]],
};
const tabsDe = (r) => (r.real ? TABS_REAL : r.tipo === "sit" ? (r.modo === "sto" ? TABS_STO : TABS_SIT) : TABS_ROWS);
const TABS_ROWS = { filas: ["Filas", [["fila", "Fila"], ["tipo_mov", "Mov."], ["material", "Material"], ["centro", "Centro"], ["almacen", "Almacén"], ["pedida", "Pedida"], ["movida", "Movida"], ["estado", "Estado"], ["detalle", "Detalle"], ["docs", "Documentos"]]] };

function showTab(key) {
  const defs = tabsDe(curRun);
  curTab = key;
  const cols = defs[key][1];
  let data = curRun[key] || [];
  if (key === "filas") data = data.map((f) => ({ ...f, docs: f.documentos.map((d) => `${d.doc} (${d.lote || "sin lote"}×${d.cantidad})`).join("; ") }));
  curRows = data;
  const tb = clear($("detTable"));
  tb.append(h("tr", {}, cols.map(([, t]) => h("th", {}, t))));
  for (const r of data) tb.append(h("tr", {}, cols.map(([k]) => h("td", {}, k === "estado" ? chip(String(r[k])) : r[k]))));
  clear($("detTabs")).append(...Object.entries(defs).map(([k, v]) =>
    h("button", { class: k === key ? "" : "sec", onclick: () => showTab(k) }, `${v[0]} (${(curRun[k] || []).length})`)));
  $("detNote").textContent = curRun.simulado && curRun.tipo === "sit" && ["fi", "co", "ml"].includes(key) ? " Datos SIMULADOS: formato definitivo, valores inventados." : "";
}

async function openRun(id) {
  clearTimeout(poll);
  const r = await api("/api/runs/" + id);
  curRun = r;
  $("secDetail").classList.remove("hide");
  $("detTitle").textContent = `Ejecución ${r.id} · ${r.fichero}${r.simulado ? " · SIMULADA" : ""}`;
  clear($("detAviso"));
  if (r.simulado) $("detAviso").append(h("div", { class: "simul" }, "SIMULACIÓN: no se ha contabilizado nada en SAP. El stock, los lotes, los documentos y los apuntes FI/CO/ML de esta ejecución son INVENTADOS "
    + "(sirven para ver el formato). Para datos reales usa «Chequear datos» con SAP real; la contabilización real aún no está implementada."));
  if (r.real) $("detAviso").append(h("div", { class: "real" }, "CONTABILIZACIÓN REAL en SAP: estos documentos SÍ se han creado. Documento y stock antes/después en «MM · Movimientos»; documentos contables en «FI», «CO» y «ML»."));
  const cards = clear($("detSum"));
  cards.append(h("div", { class: "kpi" }, "Estado", h("b", {}, r.estado.replace(/_/g, " "))));
  for (const k of (r.real ? ["CONTABILIZADO", "ERROR"] : ["OK", "PARCIAL", "SIN_STOCK", "ERROR", "FALTAN_DATOS", "SIN_REGISTRO_INFO", "NO_SOPORTADO"]))
    if (r.real || k in (r.resumen || {}) || ["OK", "PARCIAL", "SIN_STOCK", "ERROR"].includes(k)) cards.append(h("div", { class: "kpi" }, k.replace(/_/g, " "), h("b", {}, (r.resumen || {})[k] ?? 0)));
  showTab(r.tipo === "sit" ? (curTab in tabsDe(r) ? curTab : "escenarios") : "filas");
  $("detLog").textContent = r.log.map((l) => `${l.t} [${l.nivel}] ${l.msg}`).join("\n");
  if (r.estado === "EN_CURSO") poll = setTimeout(() => openRun(id), 800);
  else { loadRuns(); loadTree(); if (r.real && sel) api(`/api/sit/ejecuciones?${q()}`).then((x) => { ejec = x; renderSit(); }).catch(() => {}); }
}

function csvCell(v) {
  let s = String(v ?? "");
  if (/^[=+\-@\t\r]/.test(s)) s = "'" + s;   // evita inyección de fórmulas al abrir en Excel
  return /[";\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
}
$("btnCsv").addEventListener("click", () => {
  if (!curRun) return;
  const cols = tabsDe(curRun)[curTab][1];
  const lines = [cols.map(([, t]) => csvCell(t)).join(";")].concat(curRows.map((r) => cols.map(([k]) => csvCell(r[k])).join(";")));
  h("a", { href: URL.createObjectURL(new Blob(["﻿" + lines.join("\n")], { type: "text/csv" })), download: `${curRun.id}_${curTab}.csv` }).click();
});

// ---------- arranque: abre el primer flujo SIT (o el primero) ----------
function actualizarBotones() {
  // «Contabilizar en SAP…» solo con el chequeo en modo SAP real y en flujos de MIGO (los STO aún no se contabilizan de verdad)
  $("btnPost").classList.toggle("hide", !(modoSap && sel && isSit() && !esSto()));
}

async function loadModo() {
  try {
    const m = await api("/api/modo");
    modoSap = m.modo === "sap";
    sistemasModo = (m.sistemas || []).join(", ");
    actualizarBotones();
    $("modoSel").value = m.modo;
    const b = $("badge");
    b.classList.toggle("sap", modoSap);
    $("btnChk").textContent = modoSap ? "Chequear datos (SAP real)" : "Chequear datos (simulado)";
    b.textContent = modoSap ? `CHEQUEO CON SAP REAL (${m.sistemas.join(", ")}) · solo lectura · el lanzamiento sigue simulado` : "MODO SIMULADO · sin conexión a SAP";
  } catch (e) { /* servidor antiguo sin /api/modo: se queda en simulado */ }
}
$("modoSel").addEventListener("change", async () => {
  try {
    await post("/api/modo", { modo: $("modoSel").value });
    for (const k of Object.keys(chk)) { delete chk[k]; delete chkDet[k]; }
    cantidadesOk = {};
    clear($("chkOut"));
    await loadModo();
    renderSit();
    if (modoSap) probarSap();
  } catch (e) { note($("sitOut"), e.message, true); await loadModo(); }
});
async function probarSap() {
  const s = $("sapEstado");
  s.style.color = "#ccd";
  s.textContent = "comprobando…";
  try {
    const r = await api("/api/sap/estado");
    s.textContent = (r.ok ? "✔ " : "✖ ") + r.mensaje;
    s.style.color = r.ok ? "#9be7b0" : "#ffb4a8";
  } catch (e) { s.textContent = "✖ " + e.message; s.style.color = "#ffb4a8"; }
}
$("btnSap").addEventListener("click", probarSap);
loadModo();

loadTree().then((t) => {
  const flows = t.flatMap((s) => s.flujos.map((f) => [s.id, f]));
  const first = flows.find(([, f]) => f.tipo === "sit_jira") || flows[0];
  if (first) return selectFlow(first[0], first[1]);
  note($("tree"), "No hay flujos.", true);
}).catch((e) => note($("tree"), e.message, true));
