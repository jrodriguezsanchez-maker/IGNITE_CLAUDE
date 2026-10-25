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
  clear($("preview")); clear($("upOut"));
  await Promise.all([loadTree(), loadFiles(), loadRuns()]);
}

async function loadFiles() {
  const files = await api(`/api/files?stream=${sel.stream}&flow=${sel.flow}`);
  const box = clear($("files"));
  if (!files.length) return void (box.textContent = "Aún no has subido ningún Excel.");
  const tb = h("table", {}, h("tr", {}, ["Fichero", "Fecha", "Tamaño", ""].map((x) => h("th", {}, x))));
  for (const f of files) {
    tb.append(h("tr", {}, h("td", {}, f.nombre), h("td", {}, f.fecha), h("td", {}, Math.round(f.bytes / 1024) + " KB"),
      h("td", {}, h("div", { class: "row" },
        h("button", { class: "sec", onclick: () => showPreview(f.nombre) }, "Ver contenido"),
        h("button", { onclick: () => launch(f.nombre) }, "Lanzar simulación")))));
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
  const tb = h("table", {}, h("tr", {}, ["Inicio", "Flujo", "Fichero", "Estado", "OK", "Parcial", "Sin stock", "Error"].map((x) => h("th", {}, x))));
  for (const r of runs) {
    const s = r.resumen || {};
    tb.append(h("tr", { class: "click", onclick: () => openRun(r.id) }, h("td", {}, r.inicio), h("td", {}, r.flujo), h("td", {}, r.fichero),
      h("td", {}, chip(r.estado), r.simulado ? " simulado" : ""), h("td", {}, s.OK ?? ""), h("td", {}, s.PARCIAL ?? ""),
      h("td", {}, s.SIN_STOCK ?? ""), h("td", {}, s.ERROR ?? "")));
  }
  box.append(tb);
}

async function openRun(id) {
  clearTimeout(poll);
  const r = await api("/api/runs/" + id);
  curRun = r;
  $("secDetail").classList.remove("hide");
  $("detTitle").textContent = `Ejecución ${r.id} · ${r.fichero}${r.simulado ? " · SIMULADA" : ""}`;
  const cards = clear($("detSum"));
  cards.append(h("div", { class: "card" }, "Estado", h("b", {}, r.estado.replace("_", " "))));
  for (const k of ["OK", "PARCIAL", "SIN_STOCK", "ERROR"]) cards.append(h("div", { class: "card" }, k.replace("_", " "), h("b", {}, (r.resumen || {})[k] ?? 0)));
  const tb = clear($("detTable"));
  tb.append(h("tr", {}, ["Fila", "Mov.", "Material", "Centro", "Almacén", "Pedida", "Movida", "Estado", "Detalle", "Documentos (lote×cant.)"].map((x) => h("th", {}, x))));
  for (const f of r.filas) {
    tb.append(h("tr", {}, h("td", {}, f.fila), h("td", {}, f.tipo_mov), h("td", {}, f.material), h("td", {}, f.centro), h("td", {}, f.almacen),
      h("td", {}, f.pedida), h("td", {}, f.movida), h("td", {}, chip(f.estado)), h("td", {}, f.detalle),
      h("td", {}, f.documentos.map((d) => `${d.doc} (${d.lote || "sin lote"}×${d.cantidad})`).join("; "))));
  }
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
  const cols = ["fila", "tipo_mov", "material", "centro", "almacen", "pedida", "movida", "estado", "detalle"];
  const lines = [cols.join(";")].concat(curRun.filas.map((f) => cols.map((c) => csvCell(f[c])).join(";") + ";" +
    csvCell(f.documentos.map((d) => `${d.doc}/${d.lote}/${d.cantidad}`).join(" | "))));
  lines[0] += ";documentos";
  const a = h("a", { href: URL.createObjectURL(new Blob(["﻿" + lines.join("\n")], { type: "text/csv" })), download: curRun.id + ".csv" });
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

loadTree().then(() => loadRuns(true)).catch((e) => note($("tree"), e.message, true));
