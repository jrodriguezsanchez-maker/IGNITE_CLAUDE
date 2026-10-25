"use strict";
// Todo el contenido dinámico se inserta con textContent (nunca innerHTML) para evitar XSS con datos del Excel.
const $ = (id) => document.getElementById(id);
let sel = null;        // {stream, flow}
let curRun = null;
let poll = null;

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
const chip = (t) => h("span", { class: "chip " + t }, t.replace("_", " "));
const clear = (e) => { while (e.firstChild) e.removeChild(e.firstChild); return e; };

async function api(path, opts) {
  const r = await fetch(path, opts);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || "Error " + r.status);
  return j;
}
function note(box, text, err) { clear(box).append(h("div", { class: "msg" + (err ? " err" : "") }, text)); }

async function loadTree() {
  const t = await api("/api/tree");
  const box = clear($("tree"));
  if (!t.length) box.textContent = "No hay streams.";
  for (const s of t) {
    box.append(h("div", { class: "stream" }, s.id));
    for (const f of s.flujos) {
      const el = h("div", { class: "flow" + (sel && sel.flow === f.id ? " sel" : ""), onclick: () => selectFlow(s.id, f) },
        f.nombre, h("small", {}, `${f.ficheros} fichero(s) · ${f.ejecuciones} ejecución(es)`));
      box.append(el);
    }
  }
}

async function selectFlow(stream, f) {
  sel = { stream, flow: f.id, meta: f };
  $("secFlow").classList.remove("hide");
  $("flowTitle").textContent = `${stream} › ${f.nombre}`;
  const r = f.reglas || {};
  $("flowDesc").textContent = `${f.descripcion} · Lotes: ${r.estrategia_lote} · Stock insuficiente: ${r.stock_insuficiente} · Entorno: ${r.entorno}`;
  clear($("preview")); clear($("upOut")); clear($("sitOut"));
  const isSit = f.tipo === "sit_jira";
  $("secSit").classList.toggle("hide", !isSit);
  await Promise.all([loadTree(), loadFiles(), loadRuns(), isSit ? loadCatalog() : null]);
}

async function loadFiles() {
  const files = await api(`/api/files?stream=${sel.stream}&flow=${sel.flow}`);
  const box = clear($("files"));
  if (!files.length) return void (box.textContent = "Aún no has subido ningún Excel.");
  const tb = h("table", {}, h("tr", {}, ["Fichero", "Fecha", "Tamaño", ""].map((x) => h("th", {}, x))));
  for (const f of files) {
    tb.append(h("tr", {}, h("td", {}, f.nombre), h("td", {}, f.fecha), h("td", {}, Math.round(f.bytes / 1024) + " KB"),
      h("td", {}, h("div", { class: "row" },
        sel.meta.tipo === "sit_jira"
          ? h("button", { onclick: () => importSit(f.nombre) }, "Importar escenarios")
          : [h("button", { class: "sec", onclick: () => showPreview(f.nombre) }, "Ver contenido"),
             h("button", { onclick: () => launch(f.nombre) }, "Lanzar simulación")]))));
  }
  box.append(tb);
}

async function showPreview(name) {
  const box = clear($("preview"));
  try {
    const p = await api(`/api/preview?stream=${sel.stream}&flow=${sel.flow}&file=${encodeURIComponent(name)}`);
    box.append(h("h2", { style: "margin-top:14px" }, `${name}: ${p.total} filas (se muestran ${p.filas.length})`));
    if (p.faltan.length) box.append(h("div", { class: "msg err" }, "Faltan columnas obligatorias: " + p.faltan.join(", ")));
    const tb = h("table", {}, h("tr", {}, p.cabeceras.map((c) => h("th", {}, c))));
    for (const r of p.filas) tb.append(h("tr", {}, p.cabeceras.map((c) => h("td", {}, r[c]))));
    box.append(h("div", { class: "scroll" }, tb));
  } catch (e) { note(box, e.message, true); }
}

async function launch(name) {
  try {
    const r = await api("/api/run", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ stream: sel.stream, flow: sel.flow, file: name }) });
    await loadRuns();
    openRun(r.id);
  } catch (e) { note($("upOut"), e.message, true); }
}

async function upload(file) {
  if (!file) return;
  try {
    await api(`/api/upload?stream=${sel.stream}&flow=${sel.flow}&name=${encodeURIComponent(file.name)}`, { method: "POST", body: file });
    note($("upOut"), `«${file.name}» subido. Se guarda solo en tu equipo (carpeta data/, fuera de GitHub).`);
    await Promise.all([loadFiles(), loadTree()]);
    showPreview(file.name);
  } catch (e) { note($("upOut"), e.message, true); }
}

async function loadRuns(all) {
  let runs = await api("/api/runs");
  if (!all && sel) runs = runs.filter((r) => r.flujo === sel.flow && r.stream === sel.stream);
  $("runsTitle").textContent = all || !sel ? "Todas las ejecuciones" : "Ejecuciones de este flujo";
  const box = clear($("runs"));
  if (!runs.length) return void (box.textContent = "Sin ejecuciones todavía.");
  const tb = h("table", {}, h("tr", {}, ["Inicio", "Flujo", "Fichero", "Estado", "OK", "Parcial", "Sin stock", "Error", "Sin datos"].map((x) => h("th", {}, x))));
  for (const r of runs) {
    const s = r.resumen || {};
    tb.append(h("tr", { class: "click", onclick: () => openRun(r.id) }, h("td", {}, r.inicio), h("td", {}, r.flujo), h("td", {}, r.fichero),
      h("td", {}, chip(r.estado), r.simulado ? " simulado" : ""), h("td", {}, s.OK ?? ""), h("td", {}, s.PARCIAL ?? ""),
      h("td", {}, s.SIN_STOCK ?? ""), h("td", {}, s.ERROR ?? ""), h("td", {}, s.SIN_DATOS ?? "")));
  }
  box.append(tb);
}

const TABS_SIT = {
  escenarios: ["Escenarios", [["jira_id", "JIRA ID"], ["id_jira_unidad", "ID unidad"], ["unidad", "Unidad"], ["escenario", "Escenario"], ["mov", "Mov."], ["estado", "Estado"], ["detalle", "Detalle"]]],
  mm: ["MM · Movimientos", [["jira_id", "JIRA ID"], ["id_jira_unidad", "ID unidad"], ["escenario", "Escenario"], ["mov", "Mov."], ["material", "Material"], ["centro", "Centro"], ["almacen", "Almacén"], ["pedida", "Pedida"], ["movida", "Movida"], ["estado", "Estado"], ["documentos", "Doc. material (lote×cant.)"], ["detalle", "Detalle"], ["nota", "Nota"]]],
  fi: ["FI · Apuntes", [["jira_id", "JIRA ID"], ["id_jira_unidad", "ID unidad"], ["doc_material", "Doc. material"], ["doc_fi", "Doc. FI"], ["pos", "Pos."], ["cuenta", "Cuenta"], ["dc", "D/H"], ["importe", "Importe"], ["moneda", "Moneda"], ["centro_coste", "Centro coste"]]],
  co: ["CO · Imputaciones", [["jira_id", "JIRA ID"], ["id_jira_unidad", "ID unidad"], ["doc_material", "Doc. material"], ["objeto_co", "Objeto CO"], ["clase_coste", "Clase coste"], ["valor", "Valor"], ["moneda", "Moneda"]]],
  ml: ["ML · Valoración", [["jira_id", "JIRA ID"], ["id_jira_unidad", "ID unidad"], ["doc_material", "Doc. material"], ["material", "Material"], ["centro", "Centro"], ["control_precio", "Ctrl. precio"], ["precio", "Precio"], ["cantidad", "Cantidad"], ["valor", "Valor"], ["diferencia_precio", "Dif. precio"], ["moneda", "Moneda"]]],
  pasos: ["Pasos a validar", [["jira_id", "JIRA ID"], ["id_jira_unidad", "ID unidad"], ["paso", "Paso"], ["equipo", "Equipo"], ["transacciones", "Transacciones"], ["descripcion", "Descripción"], ["esperado", "Resultado esperado"]]],
};
const TABS_ROWS = { filas: ["Filas", [["fila", "Fila"], ["tipo_mov", "Mov."], ["material", "Material"], ["centro", "Centro"], ["almacen", "Almacén"], ["pedida", "Pedida"], ["movida", "Movida"], ["estado", "Estado"], ["detalle", "Detalle"], ["docs", "Documentos"]]] };
let curTab = null;
let curRows = [];

function showTab(key) {
  const defs = curRun.tipo === "sit" ? TABS_SIT : TABS_ROWS;
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
  const cards = clear($("detSum"));
  cards.append(h("div", { class: "card" }, "Estado", h("b", {}, r.estado.replace("_", " "))));
  for (const k of ["OK", "PARCIAL", "SIN_STOCK", "ERROR", "SIN_DATOS"])
    if (k !== "SIN_DATOS" || r.tipo === "sit") cards.append(h("div", { class: "card" }, k.replace("_", " "), h("b", {}, (r.resumen || {})[k] ?? 0)));
  showTab(r.tipo === "sit" ? (curTab in TABS_SIT ? curTab : "escenarios") : "filas");
  $("detLog").textContent = r.log.map((l) => `${l.t} [${l.nivel}] ${l.msg}`).join("\n");
  $("secDetail").scrollIntoView({ behavior: "smooth" });
  if (r.estado === "EN_CURSO") poll = setTimeout(() => openRun(id), 800);
  else { loadRuns(!sel); loadTree(); }
}

function csvCell(v) {
  let s = String(v ?? "");
  if (/^[=+\-@\t\r]/.test(s)) s = "'" + s;   // evita inyección de fórmulas al abrir en Excel
  return /[";\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
}
$("btnCsv").addEventListener("click", () => {
  if (!curRun) return;
  const defs = curRun.tipo === "sit" ? TABS_SIT : TABS_ROWS;
  const cols = defs[curTab][1];
  const lines = [cols.map(([, t]) => csvCell(t)).join(";")].concat(curRows.map((r) => cols.map(([k]) => csvCell(r[k])).join(";")));
  const a = h("a", { href: URL.createObjectURL(new Blob(["\ufeff" + lines.join("\n")], { type: "text/csv" })), download: `${curRun.id}_${curTab}.csv` });
  a.click();
});

$("btnRuns").addEventListener("click", () => loadRuns(true));
$("btnNl").addEventListener("click", async () => {
  const text = $("nl").value.trim();
  if (!text) return;
  try {
    const r = await api("/api/nl", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }) });
    const box = clear($("nlOut"));
    box.append(h("div", { class: "msg" + (r.ok ? "" : " err") }, r.mensaje));
    if (r.ok) {
      const t = await api("/api/tree");
      const f = t.find((s) => s.id === r.stream).flujos.find((x) => x.id === r.flujo);
      await selectFlow(r.stream, f);
      if (r.fichero && r.accion === "lanzar")
        box.append(h("div", { class: "row", style: "margin-top:8px" },
          h("button", { onclick: () => launch(r.fichero) }, `Confirmar y lanzar simulación con ${r.fichero}`)));
    }
  } catch (e) { note($("nlOut"), e.message, true); }
});
$("nl").addEventListener("keydown", (e) => { if (e.key === "Enter") $("btnNl").click(); });

const drop = $("drop");
drop.addEventListener("click", () => $("file").click());
$("file").addEventListener("change", (e) => upload(e.target.files[0]));
drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
drop.addEventListener("dragleave", () => drop.classList.remove("over"));
drop.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("over"); upload(e.dataTransfer.files[0]); });

let catalog = [];
const picked = new Set();
const movIn = {};   // clave -> valor tecleado

async function importSit(name) {
  try {
    note($("sitOut"), "Importando…");
    await api("/api/sit/import", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ stream: sel.stream, flow: sel.flow, file: name }) });
    await loadCatalog();
    note($("sitOut"), "Escenarios importados. Se guardan solo en tu equipo (data/, fuera de GitHub).");
  } catch (e) { note($("sitOut"), e.message, true); }
}

async function loadCatalog() {
  catalog = await api(`/api/sit/catalog?stream=${sel.stream}&flow=${sel.flow}`);
  picked.clear();
  const l2 = [...new Set(catalog.map((e) => e.l2))].sort();
  clear($("sitL2")).append(h("option", { value: "" }, "Todos los L2"), ...l2.map((x) => h("option", { value: x }, x)));
  const files = await api(`/api/files?stream=${sel.stream}&flow=${sel.flow}`);
  clear($("sitFile")).append(...files.map((f) => h("option", { value: f.nombre }, f.nombre)));
  renderSit();
}

function sitVisible() {
  const q = $("sitQ").value.toLowerCase(), l2 = $("sitL2").value, est = $("sitEst").value;
  return catalog.filter((e) => {
    if (l2 && e.l2 !== l2) return false;
    if (q && !(`${e.jira_id} ${e.id_jira_unidad} ${e.escenario} ${e.descripcion_paso1} ${e.unidad}`.toLowerCase().includes(q))) return false;
    if (est === "pend") return !e.confirmado;
    if (est === "ok") return e.confirmado;
    if (est === "sinprop") return !e.movs_candidatos.length && !e.confirmado;
    if (est === "doc") return e.requiere_doc_previo;
    return true;
  });
}

function renderSit() {
  const vis = sitVisible();
  const tb = clear($("sitTable"));
  tb.append(h("tr", {}, ["", "JIRA ID", "ID unidad", "Unidad", "L2", "Paso 1", "Centro", "Materiales", "Mov.", "Origen propuesta", "Avisos"].map((x) => h("th", {}, x))));
  for (const e of vis) {
    const cb = h("input", { type: "checkbox" });
    cb.checked = picked.has(e.clave);
    cb.addEventListener("change", () => { cb.checked ? picked.add(e.clave) : picked.delete(e.clave); sitInfo(); });
    const inp = h("input", { type: "text", maxlength: "3", style: "width:56px;text-align:center" });
    inp.value = movIn[e.clave] ?? (e.confirmado ? e.mov : (e.movs_candidatos[0] || ""));
    inp.title = e.movs_candidatos.length ? "Candidatos: " + e.movs_candidatos.join(", ") : "Sin propuesta";
    inp.addEventListener("input", () => { movIn[e.clave] = inp.value.toUpperCase(); });
    const avisos = [e.requiere_doc_previo ? "requiere doc. previo" : "", !e.datos.materiales.length ? "sin material" : "", !e.datos.plantas.length ? "sin centro" : ""].filter(Boolean).join(" · ");
    tb.append(h("tr", {}, h("td", {}, cb), h("td", {}, e.jira_id), h("td", {}, e.id_jira_unidad), h("td", {}, e.unidad), h("td", {}, e.l2),
      h("td", {}, e.descripcion_paso1.slice(0, 90)), h("td", {}, e.datos.plantas.join(", ")), h("td", {}, e.datos.materiales.length || ""),
      h("td", {}, inp, e.confirmado ? chip("OK") : ""), h("td", {}, e.mov_origen + (e.mov_nota ? " · " + e.mov_nota : "")), h("td", {}, avisos)));
  }
  sitInfo();
}

function sitInfo() {
  const conf = catalog.filter((e) => e.confirmado).length;
  $("sitSelInfo").textContent = `${catalog.length} escenarios · ${conf} confirmados · ${picked.size} seleccionados`;
  $("sitInfo").textContent = catalog.length ? `${catalog.length} escenarios en el catálogo` : "Catálogo vacío: importa el Excel";
}

$("btnImport").addEventListener("click", () => $("sitFile").value && importSit($("sitFile").value));
for (const id of ["sitQ", "sitL2", "sitEst"]) $(id).addEventListener("input", renderSit);
$("btnSelVis").addEventListener("click", () => { sitVisible().forEach((e) => picked.add(e.clave)); renderSit(); });
$("btnSelNone").addEventListener("click", () => { picked.clear(); renderSit(); });
$("btnConfirm").addEventListener("click", async () => {
  const items = [...picked].map((clave) => {
    const e = catalog.find((x) => x.clave === clave);
    return { clave, mov: movIn[clave] ?? (e.confirmado ? e.mov : (e.movs_candidatos[0] || "")) };
  }).filter((i) => /^[0-9A-Z]{3}$/.test(i.mov));
  if (!items.length) return note($("sitOut"), "Selecciona escenarios con un tipo de movimiento de 3 caracteres (p. ej. 311).", true);
  try {
    const r = await api("/api/sit/confirm", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ stream: sel.stream, flow: sel.flow, items }) });
    const keep = new Set(picked);
    await loadCatalog(); keep.forEach((k) => picked.add(k)); renderSit();
    note($("sitOut"), `${items.length} escenario(s) confirmados (${r.confirmados} en total).`);
  } catch (e) { note($("sitOut"), e.message, true); }
});
$("btnRunSit").addEventListener("click", async () => {
  try {
    const r = await api("/api/sit/run", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ stream: sel.stream, flow: sel.flow, claves: [...picked] }) });
    await loadRuns(); openRun(r.id);
  } catch (e) { note($("sitOut"), e.message, true); }
});

loadTree().then(() => loadRuns(true)).catch((e) => note($("tree"), e.message, true));
