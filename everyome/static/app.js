/* Everyome app frontend (shell carried over from SPLiTscape). One page per step;
   the sidebar unlocks steps as their prerequisites finish. Forms are built from
   each module's manifest; a module's own interactive views come from its ui.js,
   which registers them with Everyome.registerViews(). All cluster work goes
   through /api (this computer), which forwards session calls through the tunnel. */
"use strict";

// ------------------------------------------------------------------ helpers
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const fmt = n => Number(n).toLocaleString();
const sleep = ms => new Promise(r => setTimeout(r, ms));
// "#RRGGBB" -> [r, g, b], for blending theme colours in heatmaps and expression scales.
const hexRgb = h => [1, 3, 5].map(i => parseInt(String(h).slice(i, i + 2), 16));
// Colours used in plots. Filled from the active theme by applyTheme(); these are the house-style defaults.
const COL = { gold: "#C2A24A", golddk: "#8F7529", goldlt: "#DFC684", ox: "#6E1B2B", wine: "#8E2438", plum: "#32203A", ink: "#1C1620",
  muted: "#5A5260", rule: "#D6CBB6", card: "#FBF7EF", parch: "#E7DECC", ok: "#5E6B2E" };
let PALETTE = ["#C2A24A", "#6E1B2B", "#32203A", "#8F7529", "#A83B50", "#5A5260", "#DFC684", "#0E8F8A", "#B9AEC0"];

async function api(path, { method = "GET", body } = {}) {
  const opt = { method, headers: {} };
  if (body !== undefined) { opt.body = JSON.stringify(body); opt.headers["content-type"] = "application/json"; }
  const r = await fetch(path, opt);
  const txt = await r.text();
  let data; try { data = txt ? JSON.parse(txt) : null; } catch { data = txt; }
  if (!r.ok) throw new Error((data && data.detail) || `Request failed (${r.status})`);
  return data;
}
function toast(msg, ok = false) {
  const t = $("#toast"); t.textContent = msg; t.className = ok ? "ok" : ""; t.style.display = "block";
  clearTimeout(toast.t); toast.t = setTimeout(() => t.style.display = "none", ok ? 2500 : 6000);
}
async function guarded(btn, fn) {
  if (btn) btn.disabled = true;
  try { return await fn(); } catch (e) { toast(e.message); } finally { if (btn) btn.disabled = false; }
}

// ------------------------------------------------------------------ app state
const ST = { state: null, page: "home", modules: [], suites: null, pick: null, sess: null, eng: null, timers: [], answers: { data: [], aims: [] } };
function every(ms, fn) { const id = setInterval(fn, ms); ST.timers.push(id); fn(); return id; }
function clearTimers() { ST.timers.forEach(clearInterval); ST.timers = []; }

// The module in use: the open run's module, otherwise the one picked in the catalogue.
const curModule = () => ST.modules.find(m => m.id === (ST.state?.run?.module || ST.pick));
const hasBatch = m => m?.kind.includes("batch");
const hasSession = m => m?.kind.includes("interactive");
const isLocal = m => m?.kind.includes("local");
const isLocalMode = () => ST.state?.conn?.mode === "local";
// Open a run where it belongs: cluster stages, the live session, or (local modules) straight into its first step.
async function openRun() {
  const m = curModule();
  if (isLocal(m)) { await api("/api/session/start", { method: "POST" }); ST.sess = "READY"; renderSide(); renderPills(); return go("step:" + m.steps[0].id); }
  go(hasBatch(m) ? "run" : "session");
}
const runDone = () => !!ST.state?.run?.done || (ST.state?.run && !hasBatch(curModule()));

function pages() {
  const s = ST.state || {}, m = curModule();
  const groups = [
    { group: "Get started", medal: "✦", items: [
      { id: "home", title: "Home", ok: true, done: false },
      { id: "connect", title: "Connect", ok: true, done: s.connected },
      { id: "project", title: "Project", ok: s.connected, done: !!s.project }] },
    { group: "Analyses", medal: "I", items: [
      { id: "modules", title: "Choose an analysis", ok: !!s.project, done: !!m },
      { id: "settings", title: "Inputs and settings", ok: !!s.project && !!m, done: !!s.run },
      ...(hasBatch(m) ? [{ id: "run", title: "Run on the cluster", ok: !!s.run, done: !!s.run?.done }] : []),
      ...(hasSession(m) ? [{ id: "session", title: "Live session", ok: runDone(), done: ST.sess === "READY" }] : []),
      { id: "record", title: "Record and write-up", ok: !!s.run, done: false }] },
  ];
  if (m && (hasSession(m) || isLocal(m))) groups.push({ group: m.name, medal: "II", items: m.steps.map(st => (
    { id: "step:" + st.id, title: st.title, ok: ST.sess === "READY", done: false })) });
  if (m) groups.push({ group: "Learn", medal: "?", items: [{ id: "manual", title: "Manual", ok: m.has_manual, done: false },
    ...(m.playground ? [{ id: "playground", title: "Playground", ok: true, done: false }] : [])] });
  return groups;
}

function renderSide() {
  $("#side").innerHTML = pages().map(g => `<div class="grp"><span class="medal" aria-hidden="true">${g.medal}</span><span class="label">${esc(g.group)}</span></div>
    <ol>${g.items.map(p => `<li><button data-page="${p.id}" ${p.ok ? "" : "disabled"} ${ST.page === p.id ? 'aria-current="page"' : ""}>
      ${esc(p.title)}${p.done ? '<span class="tick" aria-label="done">✓</span>' : ""}</button></li>`).join("")}</ol>`).join("") +
    `<p class="credit">Everyome was created by Helen R Horkan PhD. Please cite it when you use it.</p>`;
}
function renderPills() {
  const s = ST.state || {};
  const set = (id, on, txt, busy) => { const el = $(id); el.className = "pill" + (on ? " on" : "") + (busy ? " busy" : ""); el.lastElementChild.textContent = txt; };
  set("#pill-conn", s.connected, s.connected ? s.label : "Not connected");
  set("#pill-proj", !!s.project, s.project ? s.project.name : "No project");
  set("#pill-sess", ST.sess === "READY", ST.sess === "READY" ? "Session ready" : ST.sess && ST.sess !== "NONE" ? "Session " + ST.sess.toLowerCase() : "No session",
    ["PENDING", "STARTING", "RUNNING"].includes(ST.sess));
}
async function refreshState() {
  ST.state = await api("/api/state");
  if (ST.state.run?.session_job || (ST.state.run && isLocal(curModule()))) {
    try {
      let st = await api("/api/session/status");
      // Intent: a local module's engine lives in the app; reopen it quietly after a reload.
      if (st.state === "NONE" && isLocal(curModule())) { await api("/api/session/start", { method: "POST" }); st = await api("/api/session/status"); }
      ST.sess = st.state; ST.eng = st.engine || null;
    } catch { ST.sess = null; }
  } else ST.sess = null;
  renderSide(); renderPills();
}

async function go(id) {
  clearTimers(); ST.page = id; renderSide();
  const page = $("#page");
  page.innerHTML = "";
  try { await (id.startsWith("step:") ? moduleStep(page, id.slice(5)) : id.startsWith("manual:") ? VIEWS.manual(page, id.slice(7)) : id.startsWith("playground:") ? VIEWS.playground(page, id.slice(11)) : id.startsWith("suite:") ? suitePage(page, id.slice(6)) : VIEWS[id](page)); }
  catch (e) { page.innerHTML += `<div class="notice warn">${esc(e.message)}</div>`; }
  $("#main").scrollTop = 0;
}
document.addEventListener("click", e => {
  const b = e.target.closest("[data-page]"); if (b && !b.disabled) go(b.dataset.page);
  const g = e.target.closest("[data-go]"); if (g) { e.preventDefault(); go(g.dataset.go); }
});

const head = (medal, kicker, title, lede) => `<div class="kicker"><span class="medal" aria-hidden="true">${medal}</span><span class="label">${esc(kicker)}</span></div>
  <h1>${esc(title)}</h1>${lede ? `<p class="lede">${lede}</p>` : ""}`;

// ------------------------------------------------------------------ modals
function modal(title, bodyHtml, buttons) {
  return new Promise(resolve => {
    const m = document.createElement("div"); m.className = "modal";
    m.innerHTML = `<div class="box" role="dialog" aria-modal="true" aria-label="${esc(title)}"><header><div class="label">${esc(title)}</div></header>
      <div class="body">${bodyHtml}</div><footer>${buttons.map((b, i) => `<button class="btn${b.primary ? " primary" : ""}" data-v="${i}">${esc(b.text)}</button>`).join("")}</footer></div>`;
    document.body.appendChild(m);
    const close = v => { m.remove(); resolve(v); };
    m.addEventListener("click", e => { const b = e.target.closest("[data-v]"); if (b) close(buttons[+b.dataset.v].value); });
    m.addEventListener("keydown", e => { if (e.key === "Escape") close(null); });
    setTimeout(() => ($("[data-v].primary", m) || $("[data-v]", m)).focus(), 30);
  });
}
function browse(start, mode = "dir", title = "Choose a folder") {
  return new Promise(resolve => {
    const m = document.createElement("div"); m.className = "modal";
    m.innerHTML = `<div class="box" role="dialog" aria-modal="true" aria-label="${esc(title)}"><header><div class="label">${esc(title)}</div>
      <div class="pathrow" style="margin-top:8px"><input type="text" class="mono" id="bpath" aria-label="Path"><button class="btn small" id="bgo">Go</button><button class="btn small" id="bup">Up</button></div></header>
      <div class="body"><ul class="fl" id="blist"></ul></div>
      <footer><span class="muted small" id="bsel" style="margin-right:auto"></span><button class="btn" id="bcancel">Cancel</button><button class="btn primary" id="bok">${mode === "dir" ? "Use this folder" : "Use this file"}</button></footer></div>`;
    document.body.appendChild(m);
    let cur = start || "/", chosen = null;
    const close = v => { m.remove(); resolve(v); };
    async function load(p) {
      try {
        const r = await api("/api/ls?path=" + encodeURIComponent(p)); cur = r.path; chosen = null;
        $("#bpath", m).value = cur; $("#bsel", m).textContent = mode === "dir" ? cur : "";
        $("#blist", m).innerHTML = r.entries.map(e => `<li tabindex="0" data-name="${esc(e.name)}" data-dir="${e.dir}"><span class="ic">${e.dir ? "▸" : "·"}</span>${esc(e.name)}<span class="sz">${e.dir ? "" : fmtSize(e.size)}</span></li>`).join("") || `<li class="muted">Empty folder</li>`;
      } catch (e) { toast(e.message); }
    }
    $("#blist", m).addEventListener("click", e => {
      const li = e.target.closest("li[data-name]"); if (!li) return;
      const p = cur.replace(/\/$/, "") + "/" + li.dataset.name;
      if (li.dataset.dir === "true") load(p);
      else { $$("li", m).forEach(x => x.classList.remove("sel")); li.classList.add("sel"); chosen = p; $("#bsel", m).textContent = li.dataset.name; }
    });
    $("#blist", m).addEventListener("keydown", e => { if (e.key === "Enter") e.target.click(); });
    $("#bgo", m).onclick = () => load($("#bpath", m).value);
    $("#bup", m).onclick = () => load(cur.replace(/\/[^/]+\/?$/, "") || "/");
    $("#bcancel", m).onclick = () => close(null);
    $("#bok", m).onclick = () => { if (mode === "dir") close(cur); else if (chosen) close(chosen); else toast("Select a file first."); };
    m.addEventListener("keydown", e => { if (e.key === "Escape") close(null); });
    load(cur); setTimeout(() => $("#bpath", m).focus(), 50);
  });
}
const fmtSize = b => b > 1e9 ? (b / 1e9).toFixed(1) + " GB" : b > 1e6 ? (b / 1e6).toFixed(1) + " MB" : b > 1e3 ? (b / 1e3).toFixed(0) + " KB" : b + " B";

// ------------------------------------------------------------------ shared viewers (any module may use these)
function barChart(items, { w = 520, h = 180, color = COL.golddk, label = v => fmt(v), title = "" } = {}) {
  // Intent: make room for the longest label (about 7 px per character), up to half the chart.
  const max = Math.max(...items.map(d => d[1]), 1), left = Math.min(w / 2, Math.max(120, 14 + 7 * Math.max(...items.map(d => String(d[0]).length)))), bh = Math.min(26, (h - 10) / items.length - 6);
  return `<svg class="chart" viewBox="0 0 ${w} ${items.length * (bh + 6) + 12}" role="img" aria-label="${esc(title)}">${items.map(([k, v], i) => {
    const y = i * (bh + 6) + 4, ww = (w - left - 90) * v / max;
    return `<text x="${left - 8}" y="${y + bh / 2 + 4}" text-anchor="end" class="ax">${esc(k)}</text><rect x="${left}" y="${y}" width="${ww}" height="${bh}" fill="${color}"/>
      <text x="${left + ww + 6}" y="${y + bh / 2 + 4}" class="ax">${label(v)}</text>`; }).join("")}</svg>`;
}
// Histogram on a linear scale, with optional shaded keep-range [lo, hi].
function histChart(edges, counts, { lo, hi, w = 560, h = 200, xlab = "", digits = 2 } = {}) {
  const L = 34, B = 34, n = counts.length, max = Math.max(...counts, 1), x0 = edges[0], x1 = edges[n];
  const X = v => L + (v - x0) / (x1 - x0 || 1) * (w - L - 8), Y = c => (h - B) - c / max * (h - B - 12);
  const inside = i => lo == null || (edges[i + 1] > lo && edges[i] < hi);
  let out = "";
  for (let i = 0; i < n; i++) if (counts[i]) out += `<rect x="${X(edges[i]) + .5}" y="${Y(counts[i])}" width="${Math.max(.5, X(edges[i + 1]) - X(edges[i]) - 1)}" height="${(h - B) - Y(counts[i])}" fill="${inside(i) ? COL.golddk : COL.rule}"><title>${edges[i].toFixed(digits)}–${edges[i + 1].toFixed(digits)}: ${counts[i]}</title></rect>`;
  // Intent: label "min" to the right of its line and "max" to the left, so neither runs off the chart.
  const line = (v, t, end) => `<line x1="${X(v)}" x2="${X(v)}" y1="4" y2="${h - B}" stroke="${COL.ox}" stroke-dasharray="4 3" stroke-width="1.5"/><text x="${X(v) + (end ? -4 : 4)}" y="14" text-anchor="${end ? "end" : "start"}" class="ax">${t}</text>`;
  let ticks = ""; for (let k = 0; k <= 4; k++) { const v = x0 + (x1 - x0) * k / 4; ticks += `<text x="${X(v)}" y="${h - B + 16}" text-anchor="${k === 4 ? "end" : k === 0 ? "start" : "middle"}" class="ax">${v.toFixed(digits)}</text>`; }
  return `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(xlab)} histogram">${out}
    <line x1="${L}" x2="${w - 8}" y1="${h - B}" y2="${h - B}" stroke="${COL.muted}"/><text x="${L - 6}" y="${Y(max) + 4}" text-anchor="end" class="ax">${max}</text>${ticks}
    ${lo != null ? line(lo, "min") + line(hi, "max", true) : ""}<text x="${(w + L) / 2}" y="${h - 2}" text-anchor="middle" class="ax">${esc(xlab)}</text></svg>`;
}
// Recolour categorical data with the active theme's palette (annotation colours are the user's own).
function themed(c) {
  if (!c || c.kind !== "cat" || c.userColours) return c;
  return { ...c, colors: c.categories.map((_, i) => PALETTE[i % PALETTE.length]) };
}
function legendFor(c) {
  if (!c) return "";
  c = themed(c);
  if (c.kind === "num") return `<div class="row small"><span>${esc(c.gene)}${c.label ? " · " + esc(c.label) : ""}</span><span class="muted">0</span><span class="colorbar"></span><span class="muted">${c.max.toFixed(1)}</span></div>`;
  return `<div class="legend">${c.categories.slice(0, 40).map((k, i) => `<span><i style="background:${c.colors[i]}"></i>${esc(k)}</span>`).join("")}</div>`;
}
// Stacked horizontal bars: rows of [label, fractions], one colour per category.
function stacked(rows, cats, colors, { w = 560, left = 130, bh = 22, title = "" } = {}) {
  return `<svg class="chart" viewBox="0 0 ${w} ${rows.length * (bh + 10) + 6}" role="img" aria-label="${esc(title)}">${rows.map(([k, fr], i) => {
    let x = left; const y = i * (bh + 10) + 3;
    return `<text x="${left - 8}" y="${y + bh / 2 + 4}" text-anchor="end" class="ax">${esc(k)}</text>` + fr.map((f, j) => {
      const ww = f * (w - left - 4), r = ww > 0.5 ? `<rect x="${x}" y="${y}" width="${ww}" height="${bh}" fill="${colors[j]}" stroke="${COL.card}" stroke-width=".5"><title>${esc(cats[j])}: ${(f * 100).toFixed(1)}%</title></rect>` : "";
      x += ww; return r; }).join(""); }).join("")}</svg>` +
    `<div class="legend">${cats.map((c, j) => `<span><i style="background:${colors[j]}"></i>${esc(c)}</span>`).join("")}</div>`;
}
const sup = e => String(e).split("").map(c => "⁰¹²³⁴⁵⁶⁷⁸⁹"["0123456789".indexOf(c)] || (c === "-" ? "⁻" : c)).join("");
// Log-log lines, e.g. knee plots: series = {name: [[x, y], ...]}.
function logLine(series, { w = 560, h = 260, xlab = "", ylab = "" } = {}) {
  const pts = Object.values(series).flat(); if (!pts.length) return "";
  const lx = v => Math.log10(Math.max(v, 1)), xs = pts.map(p => lx(p[0])), ys = pts.map(p => lx(p[1]));
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys), L = 52, B = 34;
  const X = v => L + (lx(v) - x0) / (x1 - x0 || 1) * (w - L - 10), Y = v => (h - B) - (lx(v) - y0) / (y1 - y0 || 1) * (h - B - 10);
  const cols = [COL.golddk, COL.ox, COL.plum, COL.gold];
  let ticks = ""; for (let e = Math.ceil(x0); e <= x1; e++) ticks += `<text x="${X(10 ** e)}" y="${h - B + 16}" text-anchor="middle" class="ax">10${sup(e)}</text>`;
  for (let e = Math.ceil(y0); e <= y1; e++) ticks += `<text x="${L - 6}" y="${Y(10 ** e) + 4}" text-anchor="end" class="ax">10${sup(e)}</text>`;
  return `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(ylab)} against ${esc(xlab)}">${ticks}
    <line x1="${L}" x2="${w - 10}" y1="${h - B}" y2="${h - B}" stroke="${COL.muted}"/><line x1="${L}" x2="${L}" y1="10" y2="${h - B}" stroke="${COL.muted}"/>
    ${Object.entries(series).map(([k, p], i) => `<polyline fill="none" stroke="${cols[i % 4]}" stroke-width="2" points="${p.map(q => `${X(q[0]).toFixed(1)},${Y(q[1]).toFixed(1)}`).join(" ")}"/>`).join("")}
    <text x="${(w + L) / 2}" y="${h - 4}" text-anchor="middle" class="ax">${esc(xlab)}</text><text x="12" y="${h / 2}" transform="rotate(-90 12 ${h / 2})" text-anchor="middle" class="ax">${esc(ylab)}</text></svg>
    <div class="legend">${Object.keys(series).map((k, i) => `<span><i style="background:${cols[i % 4]}"></i>${esc(k)}</span>`).join("")}</div>`;
}
// Histogram on a log scale, stacked by group, with optional min/max lines.
function logHist(edges, groups, { lo, hi, w = 540, h = 170, xlab = "" } = {}) {
  const L = 10, B = 30, n = edges.length - 1, tot = Array.from({ length: n }, (_, i) => Object.values(groups).reduce((a, g) => a + g[i], 0));
  const max = Math.max(...tot, 1), le = edges.map(v => Math.log10(v)), X = v => L + (Math.log10(Math.max(v, edges[0])) - le[0]) / (le[n] - le[0]) * (w - L - 4);
  const cols = [COL.golddk, COL.ox, COL.plum]; let out = "";
  for (let i = 0; i < n; i++) { let y = h - B; Object.values(groups).forEach((g, k) => { const hh = g[i] / max * (h - B - 14); y -= hh;
    if (hh > 0) out += `<rect x="${X(edges[i])}" y="${y}" width="${Math.max(0.5, X(edges[i + 1]) - X(edges[i]) - 1)}" height="${hh}" fill="${cols[k % 3]}"/>`; }); }
  const line = (v, t, end) => `<line x1="${X(v)}" x2="${X(v)}" y1="4" y2="${h - B}" stroke="${COL.ox}" stroke-dasharray="4 3" stroke-width="1.5"/><text x="${X(v) + (end ? -4 : 4)}" y="14" text-anchor="${end ? "end" : "start"}" class="ax">${t}</text>`;
  let ticks = ""; for (let e = Math.ceil(le[0]); e <= le[n]; e++) ticks += `<text x="${X(10 ** e)}" y="${h - B + 15}" text-anchor="middle" class="ax">${fmt(10 ** e)}</text>`;
  return `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(xlab)} histogram">${out}<line x1="${L}" x2="${w}" y1="${h - B}" y2="${h - B}" stroke="${COL.muted}"/>${ticks}
    ${lo != null ? line(lo, "min") : ""}${hi != null ? line(hi, "max", true) : ""}<text x="${w / 2}" y="${h - 2}" text-anchor="middle" class="ax">${esc(xlab)} (log scale)</text></svg>
    <div class="legend">${Object.keys(groups).map((k, i) => `<span><i style="background:${cols[i % 3]}"></i>${esc(k)}</span>`).join("")}</div>`;
}
// Dot plot: dot size = share of cells expressing, colour = mean expression scaled per gene.
function dotplot(d) {
  const cw = 26, rh = 22, left = 44, top = 110, W = left + d.genes.length * cw + 20, H = top + d.groups.length * rh + 8;
  const lo = d.genes.map((_, j) => Math.min(...d.mean.map(r => r[j]))), hi = d.genes.map((_, j) => Math.max(...d.mean.map(r => r[j])));
  const mix = t => { const a = hexRgb(COL.parch), b = hexRgb(COL.ox); return `rgb(${a.map((v, i) => Math.round(v + (b[i] - v) * t))})`; };
  let s = `<svg class="chart" style="min-width:${W}px" viewBox="0 0 ${W} ${H}" role="img" aria-label="Dotplot">`;
  d.genes.forEach((g, j) => s += `<text transform="translate(${left + j * cw + cw / 2 + 4},${top - 8}) rotate(-60)" class="ax" style="font-size:11px">${esc(g)}<title>${esc(d.names[j])}</title></text>`);
  d.groups.forEach((g, r) => { s += `<text x="${left - 8}" y="${top + r * rh + rh / 2 + 4}" text-anchor="end" class="axb">${esc(g)}</text>`;
    d.genes.forEach((_, j) => { const f = d.frac[r][j]; if (f > .02) s += `<circle cx="${left + j * cw + cw / 2}" cy="${top + r * rh + rh / 2}" r="${1.5 + 8 * f}" fill="${mix((d.mean[r][j] - lo[j]) / ((hi[j] - lo[j]) || 1))}" stroke="${COL.rule}" stroke-width=".5"/>`; }); });
  return s + "</svg>";
}
// Embedding map (UMAP and similar) on a canvas: colour by category or value, hover, click to pick, labels at centroids.
class EmbeddingPlot {
  constructor(canvas, tip) { this.cv = canvas; this.tip = tip; this.xy = null; this.col = null; this.onPick = null;
    canvas.addEventListener("click", e => this.pick(e)); canvas.addEventListener("mousemove", e => this.hover(e));
    canvas.addEventListener("mouseleave", () => { if (this.tip) this.tip.style.display = "none"; });
    this._rs = () => this.draw(); window.addEventListener("resize", this._rs); }
  setXY(flat) { this.xy = flat; this.n = flat.length / 2; this.draw(); }
  setColour(c) { this.col = themed(c); this.draw(); }
  colourOf(i) {
    const c = this.col; if (!c) return COL.golddk;
    if (c.kind === "cat") return c.colors[c.codes[i]] || COL.rule;
    const t = Math.min(1, c.values[i] / (c.max || 1)), a = hexRgb(COL.parch), m = hexRgb(COL.gold), b = hexRgb(COL.ox);
    const mix = (p, q, s) => p.map((v, k) => Math.round(v + (q[k] - v) * s));
    return `rgb(${t < .5 ? mix(a, m, t * 2) : mix(m, b, (t - .5) * 2)})`;
  }
  layout() {
    const W = this.cv.clientWidth, H = this.cv.clientHeight, xy = this.xy;
    let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
    for (let i = 0; i < this.n; i++) { const x = xy[2 * i], y = xy[2 * i + 1]; if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y; }
    const pad = 18, s = Math.min((W - 2 * pad) / (x1 - x0 || 1), (H - 2 * pad) / (y1 - y0 || 1));
    return { W, H, s, ox: (W - s * (x1 - x0)) / 2 - x0 * s, oy: (H - s * (y1 - y0)) / 2 + y1 * s };
  }
  draw() {
    if (!this.xy || !this.cv.isConnected) return;
    const dpr = devicePixelRatio || 1, L = this.L = this.layout();
    this.cv.width = L.W * dpr; this.cv.height = L.H * dpr;
    const g = this.cv.getContext("2d"); g.scale(dpr, dpr); g.fillStyle = COL.card; g.fillRect(0, 0, L.W, L.H);
    const r = this.n > 40000 ? 1.2 : this.n > 10000 ? 1.8 : 2.6, xy = this.xy;
    // Intent: draw numeric colours low-to-high so expressing cells sit on top.
    let order = [...Array(this.n).keys()];
    if (this.col?.kind === "num") order.sort((a, b) => this.col.values[a] - this.col.values[b]);
    g.globalAlpha = .85;
    for (const i of order) { g.fillStyle = this.colourOf(i); g.beginPath(); g.arc(L.ox + xy[2 * i] * L.s, L.oy - xy[2 * i + 1] * L.s, r, 0, 6.283); g.fill(); }
    g.globalAlpha = 1;
    if (this.labels) {
      g.textAlign = "center"; g.textBaseline = "middle"; g.lineWidth = 3.5; g.strokeStyle = COL.card; g.fillStyle = COL.ink;
      g.font = `600 14px ${getComputedStyle(document.documentElement).getPropertyValue("--body")}`;
      for (const [t, x, y] of this.labels) { const px = L.ox + x * L.s, py = L.oy - y * L.s; g.strokeText(t, px, py); g.fillText(t, px, py); }
    }
  }
  nearest(e) {
    if (!this.L) return -1;
    const b = this.cv.getBoundingClientRect(), mx = e.clientX - b.left, my = e.clientY - b.top, L = this.L, xy = this.xy;
    let best = -1, bd = 64;
    for (let i = 0; i < this.n; i++) { const dx = L.ox + xy[2 * i] * L.s - mx, dy = L.oy - xy[2 * i + 1] * L.s - my, d = dx * dx + dy * dy; if (d < bd) { bd = d; best = i; } }
    return best;
  }
  pick(e) { const i = this.nearest(e); if (i >= 0 && this.onPick) this.onPick(i); }
  hover(e) {
    if (!this.tip || !this.col) return; const i = this.nearest(e);
    if (i < 0) { this.tip.style.display = "none"; return; }
    const c = this.col, txt = c.kind === "cat" ? c.categories[c.codes[i]] : `${c.gene}: ${c.values[i].toFixed(2)}`;
    const b = this.cv.getBoundingClientRect(); this.tip.textContent = txt; this.tip.style.display = "block";
    this.tip.style.left = (e.clientX - b.left + 12) + "px"; this.tip.style.top = (e.clientY - b.top + 12) + "px";
  }
  centroids(codes, names) {
    const acc = new Map();
    for (let i = 0; i < this.n; i++) { const k = codes[i], a = acc.get(k) || [0, 0, 0]; a[0] += this.xy[2 * i]; a[1] += this.xy[2 * i + 1]; a[2]++; acc.set(k, a); }
    this.labels = [...acc].map(([k, a]) => [names[k], a[0] / a[2], a[1] / a[2]]); this.draw();
  }
}

// Plasmid or sequence map. features: [{start, end, strand, label, type}] (1-based, end inclusive);
// sites: [{name, pos}]; primers: [{label, start, end, strand}]; highlight: {start, end, label}.
// Circular for plasmids, linear otherwise. Positions in the sequence's own coordinates.
function seqMap(len, { features = [], sites = [], primers = [], highlight = null, circular = true, title = "", w = 560 } = {}) {
  const c = COL, pal = PALETTE, typeCol = {};
  let k = 0;
  const colOf = t => typeCol[t] ??= pal[(k++) % pal.length];
  if (!circular) {
    const L = 30, R = w - 30, Y = 90, X = p => L + (p - 1) / Math.max(1, len - 1) * (R - L);
    let s = `<svg class="chart" viewBox="0 0 ${w} 200" role="img" aria-label="${esc(title || "Sequence map")}"><line x1="${L}" x2="${R}" y1="${Y}" y2="${Y}" stroke="${c.muted}" stroke-width="2"/>`;
    if (highlight) s += `<rect x="${X(highlight.start)}" y="${Y - 26}" width="${Math.max(2, X(highlight.end) - X(highlight.start))}" height="52" fill="${c.gold}" opacity=".25"><title>${esc(highlight.label || "")}</title></rect>`;
    features.forEach((f, i) => { const y = Y + (f.strand < 0 ? 8 : -20);
      s += `<rect x="${X(f.start)}" y="${y}" width="${Math.max(2, X(f.end) - X(f.start))}" height="12" fill="${colOf(f.type)}"><title>${esc(f.label)} (${f.start}–${f.end})</title></rect>`;
      s += `<text x="${(X(f.start) + X(f.end)) / 2}" y="${f.strand < 0 ? Y + 34 + (i % 2) * 12 : Y - 26 - (i % 2) * 12}" text-anchor="middle" class="ax">${esc(f.label)}</text>`; });
    sites.forEach(t => s += `<line x1="${X(t.pos)}" x2="${X(t.pos)}" y1="${Y - 6}" y2="${Y + 6}" stroke="${c.ink}"/><text x="${X(t.pos)}" y="${Y + 62}" text-anchor="middle" class="ax" transform="rotate(-50 ${X(t.pos)} ${Y + 62})">${esc(t.name)}</text>`);
    primers.forEach(p => { const x0 = X(p.start), x1 = X(p.end), y = Y + (p.strand < 0 ? 16 : -32);
      s += `<path d="M${p.strand < 0 ? x1 : x0} ${y}L${p.strand < 0 ? x0 + 4 : x1 - 4} ${y}" stroke="${c.ox}" stroke-width="3" marker-end="url(#ah)"/>`; });
    return s + `<defs><marker id="ah" markerWidth="6" markerHeight="6" refX="3" refY="3" orient="auto"><path d="M0,0L6,3L0,6z" fill="${c.ox}"/></marker></defs>
      <text x="${L}" y="${Y + 100}" class="ax">1</text><text x="${R}" y="${Y + 100}" text-anchor="end" class="ax">${fmt(len)} bp</text></svg>${legendTypes()}`;
  }
  const W = w, H = w * 0.9, cx = W / 2, cy = H / 2, r = H * 0.3;
  const ang = p => (p - 1) / len * 2 * Math.PI - Math.PI / 2, pt = (a, rr) => [cx + rr * Math.cos(a), cy + rr * Math.sin(a)];
  const arc = (a0, a1, r0, r1) => { if (a1 < a0) a1 += 2 * Math.PI; const big = a1 - a0 > Math.PI ? 1 : 0, [x0, y0] = pt(a0, r1), [x1, y1] = pt(a1, r1), [x2, y2] = pt(a1, r0), [x3, y3] = pt(a0, r0);
    return `M${x0.toFixed(1)} ${y0.toFixed(1)}A${r1} ${r1} 0 ${big} 1 ${x1.toFixed(1)} ${y1.toFixed(1)}L${x2.toFixed(1)} ${y2.toFixed(1)}A${r0} ${r0} 0 ${big} 0 ${x3.toFixed(1)} ${y3.toFixed(1)}Z`; };
  let s = `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(title || "Plasmid map")}">
    <circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="${c.muted}" stroke-width="2"/>`;
  if (highlight) s += `<path d="${arc(ang(highlight.start), ang(highlight.end + 1), r - 22, r + 22)}" fill="${c.gold}" opacity=".25"><title>${esc(highlight.label || "")}</title></path>`;
  const labels = [];
  features.forEach(f => { const a0 = ang(f.start), a1 = ang(f.end + 1), out = f.strand >= 0;
    s += `<path d="${arc(a0, a1, out ? r + 3 : r - 13, out ? r + 13 : r - 3)}" fill="${colOf(f.type)}"><title>${esc(f.label)} (${f.start}–${f.end}, ${f.strand < 0 ? "reverse" : "forward"})</title></path>`;
    labels.push({ a: ang((f.start + f.end) / 2), t: f.label, r: r + 30 }); });
  sites.forEach(t => { const a = ang(t.pos), [x0, y0] = pt(a, r - 6), [x1, y1] = pt(a, r + 6);
    s += `<line x1="${x0}" y1="${y0}" x2="${x1}" y2="${y1}" stroke="${c.ink}"/>`; labels.push({ a, t: `${t.name} (${t.pos})`, r: r + 30, small: true }); });
  primers.forEach(p => { const a0 = ang(p.start), a1 = ang(p.end + 1), rr = p.strand < 0 ? r - 26 : r + 22;
    s += `<path d="${arc(a0, a1, rr - 3, rr + 3)}" fill="${c.ox}"><title>${esc(p.label)}</title></path>`; labels.push({ a: (a0 + a1) / 2, t: p.label, r: r + 30, primer: true }); });
  // Intent: place labels just outside the circle, then push apart any on the same side that would overlap.
  const placed = labels.map(l => { const [x, y] = pt(l.a, r + 30); return { ...l, x, y, right: Math.cos(l.a) >= 0 }; });
  for (const side of [true, false]) {
    const g = placed.filter(l => l.right === side).sort((p, q) => p.y - q.y);
    for (let i = 1; i < g.length; i++) if (g[i].y - g[i - 1].y < 13) g[i].y = g[i - 1].y + 13;
  }
  placed.forEach(l => { s += `<text x="${l.x.toFixed(1)}" y="${(l.y + 4).toFixed(1)}" text-anchor="${l.right ? "start" : "end"}" class="ax" ${l.primer ? `style="fill:${c.ox}"` : ""}>${esc(l.t)}</text>`; });
  return s + `<text x="${cx}" y="${cy - 4}" text-anchor="middle" class="axb">${esc(title)}</text><text x="${cx}" y="${cy + 16}" text-anchor="middle" class="ax">${fmt(len)} bp</text></svg>${legendTypes()}`;
  function legendTypes() { return `<div class="legend">${Object.entries(typeCol).map(([t, col]) => `<span><i style="background:${col}"></i>${esc(t)}</span>`).join("")}</div>`; }
}

// Minimal Markdown for module manuals: headings, paragraphs, lists, tables, **bold**, *italic*, `code`.
function md(src) {
  const inline = s => esc(s).replace(/`([^`]+)`/g, "<code>$1</code>").replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>").replace(/\*([^*]+)\*/g, "<i>$1</i>");
  const out = [], lines = src.split("\n"); let i = 0;
  while (i < lines.length) {
    const l = lines[i];
    if (!l.trim()) { i++; continue; }
    if (l.startsWith("```")) {                                 // fenced code block
      const code = []; i++; while (i < lines.length && !lines[i].startsWith("```")) code.push(lines[i++]); i++;
      out.push(`<pre class="script">${esc(code.join("\n"))}</pre>`); continue;
    }
    const h = l.match(/^(#{1,3})\s+(.*)/);
    if (h) { out.push(`<h${h[1].length}>${inline(h[2])}</h${h[1].length}>`); i++; continue; }
    if (l.startsWith("|")) {
      const rows = []; while (i < lines.length && lines[i].startsWith("|")) rows.push(lines[i++]);
      const cells = r => r.replace(/^\||\|$/g, "").split("|").map(c => c.trim());
      out.push(`<table><thead><tr>${cells(rows[0]).map(c => `<th>${inline(c)}</th>`).join("")}</tr></thead><tbody>${rows.slice(2).map(r => `<tr>${cells(r).map(c => `<td>${inline(c)}</td>`).join("")}</tr>`).join("")}</tbody></table>`);
      continue;
    }
    const li = l.match(/^\s*(\d+\.|-)\s+(.*)/);
    if (li) {
      const tag = li[1] === "-" ? "ul" : "ol", items = [];
      while (i < lines.length && lines[i].match(/^\s*(\d+\.|-)\s+/)) {
        let t = lines[i++].replace(/^\s*(\d+\.|-)\s+/, "");
        while (i < lines.length && lines[i].match(/^\s{2,}\S/)) t += " " + lines[i++].trim();
        items.push(`<li>${inline(t)}</li>`);
      }
      out.push(`<${tag}>${items.join("")}</${tag}>`); continue;
    }
    const para = []; while (i < lines.length && lines[i].trim() && !lines[i].match(/^(#|\||```|\s*(\d+\.|-)\s)/)) para.push(lines[i++].trim());
    out.push(`<p>${inline(para.join(" "))}</p>`);
  }
  return out.join("\n");
}

// Follow a background step in the session, updating a progress bar; resolves with the final status.
async function followTask(box) {
  for (;;) {
    const s = await api("/api/s/status"); ST.eng = s;
    if (box) box.innerHTML = `<div class="progress"><i style="width:${s.task.progress}%"></i></div><span class="small muted">${esc(s.task.message || "")}</span>`;
    if (!s.task.running) { renderSide(); if (s.task.error) throw new Error(s.task.error); if (box) box.innerHTML = ""; return s; }
    await sleep(600);
  }
}

// What a module's ui.js receives.
const MODULE_VIEWS = {};
window.Everyome = {
  makePlayground: (...a) => makePlayground(...a),
  registerViews(moduleId, views) { MODULE_VIEWS[moduleId] = views; },
  call: (method, body = {}) => api("/api/s/call/" + method, { method: "POST", body }),
  status: () => api("/api/s/status"),
  state: () => ST.state,
  // Save a small file (for example, a barcode sheet) into the run folder; returns {path, name}.
  upload: async file => { const f = new FormData(); f.append("file", file);
    const r = await fetch("/api/run/upload", { method: "POST", body: f }), d = await r.json(); if (!r.ok) throw new Error(d.detail || "Upload failed."); return d; },
  downloadUrl: name => "/api/s/download?name=" + encodeURIComponent(name),
  helpers: { $, $$, esc, fmt, fmtSize, sleep, toast, guarded, followTask, barChart, histChart, logHist, logLine, stacked, dotplot, legendFor, themed, seqMap, guide, md,
    EmbeddingPlot, hexRgb: h => hexRgb(h), COL: () => COL, PALETTE: () => PALETTE, every, go },
};
// "How to read this" guides: short Markdown notes a module places next to its charts and tables.
const GUIDES = {};
async function loadGuides(m) { if (!GUIDES[m.id]) GUIDES[m.id] = m.guides?.length ? await api(`/api/modules/${encodeURIComponent(m.id)}/guides`) : {}; }
function guide(key, { open = false, title = "How to read this" } = {}) {
  const g = GUIDES[curModule()?.id]?.[key];
  return g ? `<details class="guide" ${open ? "open" : ""}><summary>${esc(title)}</summary><div class="manual">${md(g)}</div></details>` : "";
}

// A playground from controls, presets and a render function: the shared builder module playgrounds use.
// controls: [{group, items: [{key, label, type: range|select, min, max, step, options: [[value, label]], help}]}]
// presets: [[title, {changes}, what to notice]]; render(state, panelElement) draws the results.
function makePlayground({ controls, defaults, presets = [], render, panelHtml = "" }) {
  let S = { ...defaults }, root = null, timer = null;
  const ctl = c => c.type === "select"
    ? `<label class="ctl"><span class="lab">${esc(c.label)}</span><select data-key="${c.key}">${c.options.map(([v, l]) => `<option value="${esc(v)}" ${String(S[c.key]) === String(v) ? "selected" : ""}>${esc(l)}</option>`).join("")}</select>${c.help ? `<span class="help">${esc(c.help)}</span>` : ""}</label>`
    : `<label class="ctl"><span class="lab">${esc(c.label)}<output data-out="${c.key}">${S[c.key]}</output></span><input type="range" data-key="${c.key}" min="${c.min}" max="${c.max}" step="${c.step}" value="${S[c.key]}">${c.help ? `<span class="help">${esc(c.help)}</span>` : ""}</label>`;
  const run = () => { clearTimeout(timer); timer = setTimeout(() => { if (root?.isConnected) render(S, $(".pgp-panels", root)); }, 60); };
  const set = p => { Object.assign(S, p); $$("[data-key]", root).forEach(i => { i.value = S[i.dataset.key]; }); $$("[data-out]", root).forEach(o => o.textContent = S[o.dataset.out]); run(); };
  return {
    mount(el) {
      root = el;
      el.innerHTML = `<div class="pgp"><div class="pg-controls">${controls.map(g => `<section class="pg-card"><div class="label">${esc(g.group)}</div>${g.items.map(ctl).join("")}</section>`).join("")}
        <button type="button" class="pg-reset" data-reset>Reset all settings</button></div><div class="pgp-panels">${panelHtml}</div></div>`;
      el.addEventListener("input", e => { const k = e.target.dataset.key; if (!k) return; S[k] = e.target.type === "range" ? Number(e.target.value) : e.target.value;
        const o = $(`[data-out="${k}"]`, el); if (o) o.textContent = S[k]; run(); });
      el.addEventListener("click", e => { if (e.target.closest("[data-reset]")) set({ ...defaults }); });
      run();
    },
    presetsHtml: () => `<ol class="tries">${presets.map(([t, , d], i) => `<li><button type="button" data-preset="${i}">${esc(t)}</button><span>${esc(d)}</span></li>`).join("")}</ol>`,
    applyPreset(i) { set({ ...defaults, ...presets[i][1] }); root?.scrollIntoView({ behavior: "smooth", block: "start" }); },
  };
}

async function loadModuleUi(m) {
  await loadGuides(m);
  if (!m.has_ui || MODULE_VIEWS[m.id]) return;
  await new Promise((ok, bad) => { const s = document.createElement("script"); s.src = `/api/modules/${encodeURIComponent(m.id)}/ui.js`;
    s.onload = ok; s.onerror = () => bad(new Error("This module's views could not be loaded.")); document.head.appendChild(s); });
}
async function moduleStep(el, stepId) {
  const m = curModule(), st = m.steps.find(s => s.id === stepId);
  await loadModuleUi(m);
  const view = MODULE_VIEWS[m.id]?.[stepId];
  el.innerHTML = head("II", m.name, st.title, "");
  if (!view) throw new Error("This step has no view yet.");
  const box = document.createElement("div"); el.appendChild(box);
  await view(box);
}

// ------------------------------------------------------------------ views
const VIEWS = {};

VIEWS.connect = async el => {
  const s = ST.state, sv = s.saved || {};
  el.innerHTML = head("✦", "Get started", "Connect",
    "Big analyses run on a computing cluster and show here; smaller ones run on this computer. Use the demo cluster to try everything out, connect to your own cluster with your SSH key, or work on this computer alone.") +
    `${s.connected ? `<div class="notice">Connected to <b>${esc(s.label)}</b>. <button class="btn small" id="disc">Disconnect</button></div>` : ""}
    <div class="grid g3">
      <button class="choice" id="pick-demo" aria-pressed="${s.demo}"><div class="label">Try it out</div><h3>Demo cluster</h3>
        <p>A practice cluster on this computer with example data and a pretend job scheduler. Nothing leaves your machine.</p></button>
      <button class="choice" id="pick-ssh" aria-pressed="${s.connected && !s.demo}"><div class="label">Real data</div><h3>My cluster</h3>
        <p>Connect with the SSH key you already use. No passwords are stored; jobs run under your own account.</p></button>
      <button class="choice" id="pick-local" aria-pressed="${s.conn?.mode === "local"}"><div class="label">No cluster</div><h3>This computer</h3>
        <p>For analyses that run here, such as primer design. Projects are saved in the Everyome folder in your home folder.</p></button>
    </div>
    <div id="sshform" hidden><h2>Cluster details</h2><div class="card"><div class="grid g2">
      ${[["host", "Cluster address", "e.g. login.cluster.example.org"], ["user", "Your username", ""], ["port", "SSH port", "Usually 22"],
         ["partition", "Partition (optional)", "Leave empty for the default"],
         ["python", "Python with Everyome installed, on the cluster", "e.g. /path/to/shared/everyome-env/bin/python"],
         ["projects_root", "Where projects are saved", "A folder you can write to, e.g. /path/to/lab/everyome_projects"],
         ["data_root", "Where your data usually lives", "The file browser opens here"]]
        .map(([k, l, h]) => `<label class="field"><span>${l}</span><input type="text" class="mono" name="${k}" value="${esc(sv[k] ?? (k === "port" ? "22" : ""))}"><small>${h}</small></label>`).join("")}
      </div><div class="row"><button class="btn primary" id="go-ssh">Connect</button><span class="small muted">Your IT team can tell you the shared paths.</span></div></div></div>
    <div id="checks"></div>`;
  const showChecks = checks => {
    $("#checks", el).innerHTML = `<h2>Readiness checks</h2><div class="card"><ul class="checks">${checks.map(c => `<li><span class="${c.ok ? "ok" : "bad"}">${c.ok ? "✓" : "✗"}</span><div>${esc(c.name)}<small>${esc(c.detail)}</small></div></li>`).join("")}</ul>
      ${checks.every(c => c.ok) ? `<div class="row" style="margin-top:14px"><button class="btn primary" data-go="project">Continue to projects →</button></div>` : `<p class="small muted" style="margin-top:10px">Fix the items marked ✗, then connect again.</p>`}</div>`;
  };
  $("#pick-demo", el).onclick = e => guarded(e.currentTarget, async () => {
    $("#checks", el).innerHTML = `<div class="notice">Setting up the demo cluster…</div>`;
    const r = await api("/api/connect", { method: "POST", body: { mode: "demo" } });
    await refreshState(); showChecks(r.checks); toast("Connected to the demo cluster.", true);
    $("#pick-demo", el).setAttribute("aria-pressed", "true");
  });
  $("#pick-local", el).onclick = e => guarded(e.currentTarget, async () => {
    const r = await api("/api/connect", { method: "POST", body: { mode: "local" } });
    await refreshState(); showChecks(r.checks); toast("Working on this computer.", true);
  });
  $("#pick-ssh", el).onclick = () => { $("#sshform", el).hidden = false; $("[name=host]", el).focus(); };
  $("#go-ssh", el).onclick = e => guarded(e.currentTarget, async () => {
    const body = { mode: "ssh" }; $$("#sshform input", el).forEach(i => body[i.name] = i.value.trim());
    $("#checks", el).innerHTML = `<div class="notice">Connecting to ${esc(body.host)}…</div>`;
    try { const r = await api("/api/connect", { method: "POST", body }); await refreshState(); showChecks(r.checks); }
    catch (err) { $("#checks", el).innerHTML = `<div class="notice warn">${esc(err.message)}</div>`; }
  });
  if ($("#disc", el)) $("#disc", el).onclick = async () => { await api("/api/disconnect", { method: "POST" }); ST.sess = null; ST.pick = null; await refreshState(); go("connect"); };
  if (s.connected) showChecks(await api("/api/checks"));
};

VIEWS.project = async el => {
  const s = ST.state, list = await api("/api/projects");
  el.innerHTML = head("✦", "Get started", "Choose a project",
    "A project holds one experiment: every analysis you run on it, with its settings, jobs and results, in one folder.") +
    `<h2>Your projects</h2>${list.length ? `<div class="card"><table><thead><tr><th>Name</th><th>Created</th><th class="num">Runs</th><th></th></tr></thead><tbody>
      ${list.map(p => `<tr><td>${esc(p.name)}</td><td class="small">${esc(p.created || "")}</td><td class="num">${p.runs}</td>
      <td class="num"><button class="btn small" data-open="${esc(p.dir)}">${s.project?.dir === p.dir ? "Open (current)" : "Open"}</button></td></tr>`).join("")}</tbody></table></div>`
      : `<div class="empty">No projects yet. Create one below.</div>`}
    ${s.project ? `<h2>Runs in ${esc(s.project.name)}</h2>${s.project.runs.length ? `<div class="card"><table><thead><tr><th>Run</th><th>Analysis</th><th>Created</th><th></th></tr></thead><tbody>
      ${s.project.runs.slice().reverse().map(r => `<tr><td class="mono">${esc(r.id)}</td><td>${esc(ST.modules.find(m => m.id === r.module)?.name || r.module)}</td><td class="small">${esc(r.created)}</td>
      <td class="num"><button class="btn small" data-run="${esc(r.id)}">${s.run?.id === r.id ? "Open (current)" : "Open"}</button></td></tr>`).join("")}</tbody></table></div>`
      : `<div class="empty">No runs yet. <button class="btn small" data-go="modules">Choose an analysis →</button></div>`}` : ""}
    <h2>New project</h2><div class="card">
      <label class="field"><span>Project name</span><input type="text" id="pname" value="${s.demo ? "demo_" + (list.length + 1) : ""}" placeholder="e.g. regeneration_2026"></label>
      <div class="row"><button class="btn primary" id="create">Create project</button></div></div>`;
  el.addEventListener("click", e => {
    const b = e.target.closest("[data-open]"); if (b) guarded(b, async () => {
      // Intent: keep an analysis chosen before opening the project, and carry on to its settings.
      await api("/api/project/open", { method: "POST", body: { dir: b.dataset.open } }); await refreshState(); go(ST.pick ? "settings" : "project"); });
    const r = e.target.closest("[data-run]"); if (r) guarded(r, async () => {
      await api("/api/run/open", { method: "POST", body: { id: r.dataset.run } }); await refreshState();
      await openRun(); });
  });
  $("#create", el).onclick = e => guarded(e.currentTarget, async () => {
    await api("/api/project/create", { method: "POST", body: { name: $("#pname", el).value } }); await refreshState();
    toast("Project created.", true); go(ST.pick ? "settings" : "modules");
  });
};

const suiteName = id => ST.suites?.suites.find(s => s.id === id)?.name || id;
const moduleCard = m => `<div class="choice" aria-pressed="${curModule()?.id === m.id}"><div class="label">${esc(suiteName(m.suite))} · v${esc(m.version)}</div><h3>${esc(m.name)}</h3><p>${esc(m.summary)}</p>
  <div class="tags">${m.kind.map(k => `<span class="tag">${{ batch: "Cluster jobs", interactive: "Live session", local: "Runs here" }[k]}</span>`).join("")}</div>
  ${isLocalMode() && !isLocal(m) ? `<p class="small muted" style="margin-top:8px">Needs a cluster: connect to yours, or try it on the demo cluster.</p>` : ""}
  <div class="acts"><button class="btn primary small" data-pick="${esc(m.id)}" ${isLocalMode() && !isLocal(m) ? "disabled" : ""}>Start a new run</button>${m.has_manual ? `<button class="btn small" data-man="${esc(m.id)}">Read the manual</button>` : ""}${m.playground ? `<button class="btn small" data-go="playground:${esc(m.id)}">Try the playground</button>` : ""}</div></div>`;
function wireModuleCards(el) {
  el.addEventListener("click", e => {
    const mn = e.target.closest("[data-man]"); if (mn) return go("manual:" + mn.dataset.man);
    const p = e.target.closest("[data-pick]"); if (!p) return;
    ST.pick = p.dataset.pick;
    // Intent: remember the choice and send people to connect or pick a project first; they come back to its settings.
    if (!ST.state.connected) { toast("Connect first. Your choice of analysis is remembered.", true); return go("connect"); }
    if (!ST.state.project) { toast("Choose or create a project first. Your choice of analysis is remembered.", true); return go("project"); }
    guarded(p, async () => {
      // Intent: starting a new run closes the open one here; it stays in the project and can be reopened.
      await api("/api/run/close", { method: "POST" }); await refreshState(); go("settings");
    });
  });
}

VIEWS.modules = async el => {
  const r = await api("/api/modules"), suites = ST.suites.suites.filter(su => r.modules.some(m => m.suite === su.id));
  el.innerHTML = head("I", "Analyses", "Choose an analysis",
    "Each analysis is a module with its own settings, manual and demo data. Every setting can be changed; the defaults are a sensible place to start.") +
    suites.map(su => `<h2>${esc(su.name)}</h2><div class="grid g2">${r.modules.filter(m => m.suite === su.id).map(moduleCard).join("")}</div>`).join("") +
    `<p class="small" style="margin-top:18px">More suites are on the way. <button class="btn small" data-go="home">See all suites</button></p>` +
    (r.problems.length ? `<h2>Modules that could not load</h2>${r.problems.map(p => `<div class="notice warn mono small">${esc(p)}</div>`).join("")}` : "") +
    `<p class="small muted" style="margin-top:22px">Community modules are ${r.community ? "on" : "switched off in this version"}. Only modules shipped with Everyome are listed.</p>`;
  wireModuleCards(el);
};

// ------------------------------------------------------------------ home and suites
VIEWS.home = async el => {
  const cat = ST.suites, A = ST.answers;
  const chips = (list, key) => `<div class="chips" role="group">${list.map(x => `<button type="button" class="chip" data-${key}="${esc(x.id)}" aria-pressed="${A[key === "d" ? "data" : "aims"].includes(x.id)}">${esc(x.label)}</button>`).join("")}</div>`;
  el.innerHTML = `<div class="hero"><div class="label">Welcome to Everyome</div><h1>Every -ome, for everyone.</h1>
      <p class="lede">Everyome helps biologists analyse omics data without writing code. Choose an analysis, point it at your data,
      and Everyome runs it for you, explains what each result means, and keeps a record of exactly what was done.</p>
      <div class="grid g4 points">
        <div><div class="label">Simple to start</div><p>Step-by-step pages with sensible defaults.</p></div>
        <div><div class="label">Nothing hidden</div><p>Every setting can be seen and changed, with a plain explanation.</p></div>
        <div><div class="label">Learn as you go</div><p>Manuals, demo data and guides to reading your results.</p></div>
        <div><div class="label">Your data stays yours</div><p>Runs on your own computer or cluster account. Free and open source.</p></div>
      </div>
      <div class="row" style="margin-top:20px"><button class="btn primary" data-go="${ST.state.connected ? (ST.state.project ? "modules" : "project") : "connect"}">${ST.state.connected ? "Continue →" : "Get started →"}</button>
        <button class="btn" id="tofind">Not sure where to start?</button></div></div>
    <h2>Suites</h2>
    <div class="grid g4">${cat.suites.map(su => `<button class="suitebox" data-suite="${esc(su.id)}"><h3>${esc(su.name)}</h3><p>${esc(su.blurb)}</p>
      <span class="tag${su.ready ? " ready" : ""}">${su.ready ? "Ready to use" : "In progress"}</span></button>`).join("")}</div>
    <h2 id="find">Find the right analysis</h2>
    <div class="card"><p>Tell Everyome about your data and what you want to find out, and it will suggest where to start. Choose as many as fit.
      <span class="muted">Your answers stay on this computer.</span></p>
      <div class="label" style="margin:16px 0 8px">What kind of data do you have?</div>${chips(cat.data_types, "d")}
      <div class="label" style="margin:18px 0 8px">What do you want to find out?</div>${chips(cat.aims, "a")}
      <div class="row" style="margin-top:18px"><button class="btn primary" id="suggest">Suggest analyses</button><button class="btn" id="clear">Clear</button></div>
      <div id="sugg"></div></div>`;
  const show = async () => {
    if (!A.data.length && !A.aims.length) { $("#sugg", el).innerHTML = ""; return; }
    const r = (await api("/api/suggest", { method: "POST", body: A })).suggestions;
    $("#sugg", el).innerHTML = r.length ? `<h2>Suggestions</h2><ol class="sugg">${r.map(t => `<li><div><b>${esc(t.name)}</b> <span class="tag">${esc(t.suite_name)}</span>
        <span class="tag${t.ready ? " ready" : ""}">${t.ready ? "Ready to use" : "In progress"}</span><p class="small muted">${esc(t.reason)}</p></div>
        <button class="btn small" data-suite="${esc(t.suite)}">Open ${esc(t.suite_name)}</button></li>`).join("")}</ol>`
      : `<p class="muted" style="margin-top:14px">Nothing fits that combination yet. Try fewer choices, or look through the suites above.</p>`;
  };
  el.addEventListener("click", e => {
    const d = e.target.closest("[data-d]"), a = e.target.closest("[data-a]"), su = e.target.closest("[data-suite]");
    if (d || a) {
      const list = d ? A.data : A.aims, id = (d || a).dataset[d ? "d" : "a"], i = list.indexOf(id);
      i < 0 ? list.push(id) : list.splice(i, 1); (d || a).setAttribute("aria-pressed", i < 0);
    }
    if (su) go("suite:" + su.dataset.suite);
  });
  $("#tofind", el).onclick = () => $("#find", el).scrollIntoView({ behavior: "smooth" });
  $("#suggest", el).onclick = e => guarded(e.currentTarget, async () => { await show(); if (!A.data.length && !A.aims.length) toast("Choose your data type or an aim first."); });
  $("#clear", el).onclick = () => { A.data = []; A.aims = []; go("home"); };
  if (A.data.length || A.aims.length) await show();
};

async function suitePage(el, id) {
  const su = ST.suites.suites.find(s => s.id === id), ready = su.tools.filter(t => t.ready), planned = su.tools.filter(t => !t.ready);
  el.innerHTML = head("✦", "Suite", su.name, esc(su.blurb)) +
    (ready.length ? `<h2>Ready to use</h2><div class="grid g2">${ready.map(t => moduleCard(ST.modules.find(m => m.id === t.module))).join("")}</div>`
      : `<div class="notice"><b>Tools for the ${esc(su.name)} suite are being built.</b> Everyome adds analyses one at a time, each with its own manual,
        demo data and guides to reading the results, so nothing arrives half-finished. The tools planned for this suite are listed below.</div>
        <p>In the meantime, the <b>Getting started</b> suite has a small worked example that shows how every Everyome analysis runs.</p>
        <div class="row" style="margin:14px 0 6px"><button class="btn primary" data-go="suite:tutorial">Try the worked example →</button><button class="btn" data-go="home">Back to all suites</button></div>`) +
    (planned.length ? `<h2>${ready.length ? "Also planned" : "Planned tools"}</h2><div class="card"><ul class="checks">${planned.map(t =>
      `<li><span class="muted">○</span><div>${esc(t.name)} <span class="tag">In progress</span></div></li>`).join("")}</ul></div>` : "");
  wireModuleCards(el);
}

const tableRow = (f, r = {}) => `<tr>${f.columns.map(c => `<td><input type="text" class="mono${c.wide ? " wide" : ""}" data-col="${esc(c.id)}" aria-label="${esc(c.label)}" value="${esc(r[c.id] ?? "")}"></td>`).join("")}
  <td class="num"><button type="button" class="btn small" data-delrow>Remove</button></td></tr>`;
const fieldHtml = (f, val) => {
  if (f.type === "table") return `<div class="field" data-f="${f.id}"><span>${esc(f.label)}${f.required ? ' <span class="muted small">(required)</span>' : ""}</span>
    <div class="tablewrap"><table data-table="${f.id}"><thead><tr>${f.columns.map(c => `<th>${esc(c.label)}</th>`).join("")}<th></th></tr></thead><tbody>${(val?.length ? val : [{}]).map(r => tableRow(f, r)).join("")}</tbody></table></div>
    <div class="row" style="margin-top:8px"><button type="button" class="btn small" data-addrow="${f.id}">Add row</button>${f.fill?.helper ? `<button type="button" class="btn small" data-fill="${f.id}">${esc(f.fill.label || "Fill in")}</button>` : ""}</div>
    ${f.help ? `<small>${esc(f.help)}</small>` : ""}<div data-fillmsg="${f.id}"></div></div>`;
  const help = f.help ? `<small>${esc(f.help)}${f.min != null || f.max != null ? ` (${f.min != null ? "from " + f.min : ""}${f.min != null && f.max != null ? " " : ""}${f.max != null ? "up to " + f.max : ""})` : ""}</small>` : "";
  const req = f.required ? ' <span class="muted small">(required)</span>' : "";
  if (f.type === "bool") return `<label class="field" data-f="${f.id}"><span><input type="checkbox" name="${f.id}" ${val ? "checked" : ""}>${esc(f.label)}</span>${help}</label>`;
  if (f.type === "choice") return `<label class="field" data-f="${f.id}"><span>${esc(f.label)}${req}</span><select name="${f.id}">${f.choices.map(c => `<option ${String(c) === String(val) ? "selected" : ""}>${esc(c)}</option>`).join("")}</select>${help}</label>`;
  if (f.type === "file" || f.type === "folder") return `<label class="field" data-f="${f.id}"><span>${esc(f.label)}${req}</span><span class="pathrow"><input type="text" class="mono" name="${f.id}" data-path="${f.type === "file" ? "file" : "dir"}" value="${esc(val ?? "")}">
    <button type="button" class="btn small" data-browse="${f.id}">Browse</button></span>${help}</label>`;
  if (f.type === "longtext") return `<label class="field" data-f="${f.id}"><span>${esc(f.label)}${req}</span><textarea name="${f.id}" rows="6" class="mono" style="width:100%">${esc(val ?? "")}</textarea>${help}</label>`;
  const num = f.type === "int" || f.type === "float";
  return `<label class="field" data-f="${f.id}"><span>${esc(f.label)}${req}</span><input type="${num ? "number" : "text"}" name="${f.id}" value="${esc(val ?? "")}"
    ${num && f.min != null ? `min="${f.min}"` : ""} ${num && f.max != null ? `max="${f.max}"` : ""} ${f.type === "float" ? 'step="any"' : ""}>${help}</label>`;
};
const readField = (el, f) => {
  if (f.type === "table") return $$(`[data-table=${f.id}] tbody tr`, el).map(tr => Object.fromEntries($$("[data-col]", tr).map(i => [i.dataset.col, i.value.trim()])))
    .filter(r => Object.values(r).some(Boolean));
  const i = $(`[name=${f.id}]`, el); return f.type === "bool" ? i.checked : i.value.trim();
};
// Module settings show open; a pipeline's own settings come in collapsible groups (its first group open), with the
// settings the pipeline marks as specialist gathered under "Advanced". Groups with changed values are opened.
const paramCards = ps => {
  const own = ps.filter(f => !f.pipeline), pipe = ps.filter(f => f.pipeline && !f.advanced), adv = ps.filter(f => f.pipeline && f.advanced);
  const changed = f => f._val !== f.default && !(f._val == null && f.default == null) && f._val !== "";
  const grid = fs => `<div class="grid g2">${fs.map(f => fieldHtml(f, f._val)).join("")}</div>`;
  const groups = fs => [...new Set(fs.map(f => f.group || "Settings"))];
  const card = (g, fs, open) => `<details class="card fold" style="margin-bottom:14px" ${open ? "open" : ""}><summary class="label">${esc(g)} <span class="muted">(${fs.length})</span></summary>${grid(fs)}</details>`;
  return groups(own).map(g => `<div class="card" style="margin-bottom:18px"><div class="label">${esc(g)}</div>${grid(own.filter(f => (f.group || "Settings") === g))}</div>`).join("") +
    (pipe.length ? `<h2>Pipeline settings</h2><p class="small muted">Every setting the pipeline accepts, with its own defaults. Only the ones you change are passed to it.</p>` : "") +
    groups(pipe).map((g, i) => { const fs = pipe.filter(f => f.group === g); return card(g, fs, i === 0 || fs.some(changed)); }).join("") +
    (adv.length ? card("Advanced", adv, adv.some(changed)) : "");
};

VIEWS.settings = async el => {
  const m = curModule(), s = ST.state, run = s.run;
  const exampleVal = f => `${s.conn.data_root}/${m.id}/${f.demo}`;
  const demoVal = f => s.demo && f.demo ? exampleVal(f) : f.default;
  const val = f => run ? run.values[f.id] : demoVal(f);
  const res = run?.resources || { ...m.resources, partition: s.conn.partition };
  el.innerHTML = head("I", m.name, "Inputs and settings", esc(m.summary)) +
    (run ? `<div class="notice">These are the settings of run <b class="mono">${esc(run.id)}</b>. To change them, start a new run below; the old one is kept.</div>` : "") +
    (s.demo && !run ? `<div class="notice">Demo inputs are filled in for you. Browse to see the demo data.</div>` : "") +
    (isLocalMode() && !run && m.fields_all.some(f => f.demo) ? `<div class="notice">Want to try it first? <button class="btn small" id="example">Fill in the example</button></div>` : "") + `<div id="needs"></div>` +
    `<div class="grid g-side"><div>
      ${m.inputs.length ? `<div class="card" style="margin-bottom:18px"><div class="label">Inputs</div>${m.inputs.map(f => fieldHtml(f, val(f))).join("")}</div>` : ""}
      ${paramCards(m.params.map(f => ({ ...f, _val: val(f) })))}
    </div>${hasBatch(m) ? `<div class="card"><div class="label">Cluster resources</div>
      ${[["partition", "Partition", "Leave empty for the default queue."], ["cpus", "CPUs per job", ""], ["mem", "Memory per job", "e.g. 4G"], ["time", "Time limit per job", "hours:minutes:seconds"]]
        .map(([k, l, h]) => `<label class="field"><span>${l}</span><input type="text" class="mono" name="res_${k}" value="${esc(res[k] ?? "")}">${h ? `<small>${h}</small>` : ""}</label>`).join("")}</div>` : ""}</div>
    <div class="row" style="margin-top:18px"><button class="btn primary" id="save">${run ? "Start a new run with these settings →" : "Create the run →"}</button><button class="btn" id="reset">Restore defaults</button></div>`;
  // Intent: say early if the cluster's Python lacks what this analysis needs, rather than at the session.
  if (m.requires?.length) api(`/api/modules/${encodeURIComponent(m.id)}/check`).then(c => { if (c.missing.length) $("#needs", el).innerHTML =
    `<div class="notice warn">The Python on <b>${esc(s.label)}</b> is missing ${c.missing.map(x => `<code>${esc(x)}</code>`).join(", ")}, which this analysis needs. Ask IT, or install them in that environment, before the live session.</div>`; }).catch(() => {});
  const fill = async (id, quiet) => {
    const f = m.fields_all.find(x => x.id === id), from = $(`[name=${f.fill.from}]`, el).value.trim(), msg = $(`[data-fillmsg=${id}]`, el);
    try {
      const r = await api(`/api/modules/${encodeURIComponent(m.id)}/helpers/${f.fill.helper}`, { method: "POST", body: { path: from } });
      $(`[data-table=${id}] tbody`, el).innerHTML = r.rows.map(row => tableRow(f, row)).join("");
      msg.innerHTML = r.message ? `<div class="notice" style="margin-top:8px">${esc(r.message)}</div>` : "";
    } catch (err) { if (!quiet) msg.innerHTML = `<div class="notice warn" style="margin-top:8px">${esc(err.message)}</div>`; }
  };
  el.addEventListener("click", e => {
    const add = e.target.closest("[data-addrow]"); if (add) { const f = m.fields_all.find(x => x.id === add.dataset.addrow); $(`[data-table=${f.id}] tbody`, el).insertAdjacentHTML("beforeend", tableRow(f)); }
    const del = e.target.closest("[data-delrow]"); if (del) del.closest("tr").remove();
    const fl = e.target.closest("[data-fill]"); if (fl) guarded(fl, () => fill(fl.dataset.fill));
  });
  // On the demo, fill tables straight away from the demo inputs.
  if (s.demo && !run) m.fields_all.filter(f => f.fill?.helper).forEach(f => fill(f.id, true));
  el.addEventListener("click", async e => {
    const b = e.target.closest("[data-browse]"); if (!b) return;
    const inp = $(`[name=${b.dataset.browse}]`, el), mode = inp.dataset.path, cur = inp.value || s.conn.data_root || s.conn.projects_root;
    const v = await browse(mode === "file" ? cur.replace(/\/[^/]*$/, "") : cur, mode, mode === "dir" ? "Choose a folder" : "Choose a file");
    if (v) inp.value = v;
  });
  if ($("#example", el)) $("#example", el).onclick = () => m.fields_all.filter(f => f.demo).forEach(f => { const i = $(`[name=${f.id}]`, el); if (i) i.value = exampleVal(f); });
  $("#reset", el).onclick = () => m.fields_all.forEach(f => { if (f.type === "table") return; const i = $(`[name=${f.id}]`, el); if (f.type === "bool") i.checked = !!f.default; else i.value = demoVal(f) ?? ""; });
  $("#save", el).onclick = e => guarded(e.currentTarget, async () => {
    $$(".field.bad", el).forEach(x => x.classList.remove("bad"));
    const values = {}, resources = {};
    m.fields_all.forEach(f => values[f.id] = readField(el, f));
    ["partition", "cpus", "mem", "time"].forEach(k => { const i = $(`[name=res_${k}]`, el); if (i) resources[k] = i.value.trim(); });
    const missing = m.fields_all.filter(f => f.required && (values[f.id] === "" || (f.type === "table" && !values[f.id].length)));
    if (missing.length) { missing.forEach(f => $(`[data-f=${f.id}]`, el).classList.add("bad")); throw new Error("Please fill in: " + missing.map(f => f.label).join(", ")); }
    await api("/api/run/create", { method: "POST", body: { module: m.id, values, resources } }); await refreshState();
    toast(isLocal(m) ? "Run created." : "Run created. Nothing has been submitted yet.", true); await openRun();
  });
};

VIEWS.run = async el => {
  const m = curModule(), run = ST.state.run;
  el.innerHTML = head("I", m.name, "Run on the cluster", m.batch_engine === "nextflow"
    ? `You will see the exact job script before anything is sent. One job runs ${esc(m.pipeline.pipeline)} ${esc(m.pipeline.revision)}, which then sends its own tasks to the cluster, so you can close the app and come back later.`
    : "You will see the exact job scripts before anything is sent. Each stage waits for the one before, so you can close the app and come back later.") +
    `<p class="small muted">Run <span class="mono">${esc(run.id)}</span>, created ${esc(run.created)}${run.defaults_changed.length ? `; settings changed from the defaults: ${run.defaults_changed.map(esc).join(", ")}` : ""}.</p>
    <div class="row" style="margin-bottom:16px"><button class="btn primary" id="runall">Check and submit…</button><button class="btn" id="rerun" disabled>Re-run from selected stage…</button><button class="btn danger" id="cancel">Cancel jobs</button></div><div id="fail"></div>
    <div class="grid g-side"><div class="card"><div class="label">Stages</div><ol class="stages" id="stages">
      ${m.stages.map(s => `<li data-sid="${s.id}"><span class="n">${s.id}</span><span>${esc(s.title)}</span><span class="state" data-st="${s.id}">Not run</span><span class="small muted mono" data-el="${s.id}"></span></li>`).join("")}</ol></div>
    <div class="card"><div class="label">Job log</div><p class="small muted" id="logtitle">Select a stage to see its log.</p><pre class="log" id="log">–</pre></div></div>
    ${m.batch_engine === "nextflow" ? `<div class="card" style="margin-top:18px"><div class="label">Pipeline progress</div><div id="nfprog"><p class="small muted">Starts when the pipeline job runs. The pipeline sends its own tasks to the cluster; they are counted here as they finish.</p></div></div>` : ""}
    <div id="next"></div>`;
  let sel = null, shownNext = false;
  async function poll() {
    if (!Object.keys(ST.state.run.jobs || {}).length) return;
    const r = await api("/api/run/status");
    let failed = null;
    for (const s of m.stages) {
      const v = r.stages[s.id], b = $(`[data-st="${s.id}"]`, el);
      // Real Slurm leaves jobs behind a failed stage pending forever; show them as blocked.
      const st = v ? (failed && v.state === "PENDING" ? "BLOCKED" : v.state) : "";
      if (v && ["FAILED", "TIMEOUT", "OUT_OF_MEMORY"].includes(v.state) && !failed) failed = s;
      b.textContent = st ? st.toLowerCase() : "not run"; b.className = "state " + st;
      $(`[data-el="${s.id}"]`, el).textContent = v?.elapsed || "";
    }
    $("#fail", el).innerHTML = failed ? `<div class="notice warn">Stage ${failed.id} (${esc(failed.title)}) failed, so the stages after it did not run. Its log is shown on the right. Fix the cause, then use <b>Re-run from selected stage</b>.</div>` : "";
    if (failed && !sel) select(failed.id);
    if (sel) $("#log", el).textContent = (await api("/api/run/log?stage=" + sel)).log || "(no output yet)";
    if (m.batch_engine === "nextflow") { const p = await api("/api/run/progress"); if (p.started) $("#nfprog", el).innerHTML =
      `<div class="metric"><span>Tasks finished</span><b>${fmt(p.completed)}</b></div>${p.failed ? `<div class="metric"><span>Tasks failed</span><b>${fmt(p.failed)}</b></div>` : ""}
       <p class="small muted">Latest: ${p.recent.map(esc).join(" · ")}</p>`; }
    if (r.done && !ST.state.run.done) { ST.state.run.done = true; renderSide(); }
    if (r.done && !shownNext) {
      shownNext = true;
      $("#next", el).innerHTML = `<div class="notice" style="margin-top:18px">All stages finished. Outputs are in <span class="mono">${esc(run.dir)}</span>.</div><div id="report"></div>
        ${hasSession(m) ? `<div class="row" style="margin-top:18px"><button class="btn primary" data-go="session">Continue to the live session →</button></div>` : ""}`;
      // Intent: modules can summarise their batch output (for example, read QC) before the live session.
      if (m.has_report) { await loadModuleUi(m); const view = MODULE_VIEWS[m.id]?.report;
        if (view) await view($("#report", el), await api("/api/run/report")); }
    }
  }
  function select(id) {
    sel = id; $$("#stages li", el).forEach(x => x.classList.toggle("sel", x.dataset.sid === sel)); $("#rerun", el).disabled = false;
    $("#logtitle", el).textContent = `Stage ${sel}: last lines of the log`;
  }
  $("#stages", el).addEventListener("click", e => { const li = e.target.closest("li[data-sid]"); if (li) { select(li.dataset.sid); poll(); } });
  const submit = async from => {
    const p = await api("/api/run/preview", { method: "POST", body: { start_at: from } });
    const ok = await modal("Check before submitting",
      `<p>Everyome will submit <b>${p.scripts.length} job${p.scripts.length > 1 ? "s" : ""}</b> to <b>${esc(ST.state.label)}</b> under your account (<b>${esc(run.user)}</b>). These are the exact scripts:</p>` +
      p.scripts.map(s => `<div class="label" style="margin-top:12px">Stage ${esc(s.stage)} · ${esc(s.title)}</div><pre class="script">${esc(s.script)}</pre>`).join(""),
      [{ text: "Cancel", value: false }, { text: `Submit ${p.scripts.length} job${p.scripts.length > 1 ? "s" : ""}`, value: true, primary: true }]);
    if (!ok) return;
    await api("/api/run/submit", { method: "POST", body: { start_at: from } }); await refreshState(); shownNext = false; $("#next", el).innerHTML = ""; toast("Jobs submitted.", true); poll();
  };
  if (m.batch_engine === "nextflow" && !Object.keys(run.jobs || {}).length) select("01");
  $("#runall", el).onclick = e => guarded(e.currentTarget, () => submit(null));
  $("#rerun", el).onclick = e => guarded(e.currentTarget, () => submit(sel));
  $("#cancel", el).onclick = e => guarded(e.currentTarget, async () => { await api("/api/run/cancel", { method: "POST" }); toast("Cancel requested.", true); poll(); });
  every(3000, () => poll().catch(() => {}));
};

VIEWS.session = async el => {
  const m = curModule();
  el.innerHTML = head("II", m.name, "Live session",
    "The interactive steps run on a cluster compute node, not on this computer. Starting a session reserves a node; Everyome connects to it securely and everything from here happens live.") +
    `<div class="grid g-side"><div class="card"><div class="label">Session</div><div class="steps" id="ssteps"></div><p id="smsg" class="small"></p>
      <div class="row"><button class="btn primary" id="start">Start session</button><button class="btn danger" id="stop">Stop session</button></div></div>
      <div class="card"><div class="label">Good to know</div><p class="small">The session stops itself after an hour with no activity, and at its time limit. Your choices are saved after every step, so a new session picks up where you left off.</p></div></div>
    <div id="next"></div>`;
  const order = ["Submitted", "Waiting for a node", "Starting", "Ready"];
  async function poll() {
    const r = await api("/api/session/status"); ST.sess = r.state; if (r.engine) ST.eng = r.engine; renderPills(); renderSide();
    const idx = { NONE: -1, PENDING: 1, STARTING: 2, RUNNING: 2, READY: 3 }[r.state] ?? -1;
    $("#ssteps", el).innerHTML = order.map((s, i) => `<span class="${i < idx || (i === 3 && idx === 3) ? "done" : i === idx ? "now" : ""}">${s}</span>`).join("");
    $("#smsg", el).textContent = r.state === "READY" ? `Connected to ${r.node}.` : r.state === "NONE" ? "No session running." : ["FAILED", "CANCELLED", "TIMEOUT", "COMPLETED"].includes(r.state) ? `The last session ended (${r.state.toLowerCase()}). Start a new one to continue.` : "Waiting for the cluster…";
    $("#next", el).innerHTML = r.state === "READY" && m.steps.length ? `<div class="row" style="margin-top:18px"><button class="btn primary" data-go="step:${esc(m.steps[0].id)}">Continue →</button></div>` : "";
  }
  $("#start", el).onclick = e => guarded(e.currentTarget, async () => {
    const ok = await modal("Start a session", `<p>Everyome will submit <b>one job</b> to <b>${esc(ST.state.label)}</b> under your account to run the live session for this run.</p>`,
      [{ text: "Cancel", value: false }, { text: "Start session", value: true, primary: true }]);
    if (!ok) return;
    await api("/api/session/start", { method: "POST" }); await refreshState(); poll(); });
  $("#stop", el).onclick = e => guarded(e.currentTarget, async () => { await api("/api/session/stop", { method: "POST" }); ST.sess = null; renderPills(); renderSide(); poll(); });
  every(2000, () => poll().catch(() => {}));
};

VIEWS.record = async el => {
  const run = ST.state.run, m = curModule();
  let r = await api("/api/run/record");
  const file = n => `/api/run/record/file?name=${encodeURIComponent(n)}`;
  el.innerHTML = head("✎", m.name, "Record and write-up",
    "Everything about this run in one place: a lab-book protocol, a draft methods section to edit, the references, and what you need to repeat it.") +
    `<div class="row" style="margin-bottom:6px"><button class="btn primary" id="build">${r.exists ? "Update the record" : "Build the record"}</button>
      <span class="small muted" id="when">${r.exists ? "Last built " + esc(r.created) + "." : "Not built yet."}</span></div>
    <p class="small muted">Building reads the run folder, checks the size and checksum of each input, and asks the cluster which software versions it has. It takes longer for large inputs. Build again after more live-session steps.</p>
    <div id="body"></div>`;
  function draw() {
    if (!r.exists) { $("#body", el).innerHTML = `<div class="empty">Build the record to see the protocol, methods and references.</div>`; return; }
    $("#body", el).innerHTML = `
      <h2>Lab-book protocol</h2><div class="row" style="margin-bottom:10px"><a class="btn small" href="${file("protocol.md")}" download>Download (Markdown)</a><button class="btn small" id="print">Print or save as PDF</button>
        <a class="btn small" href="${file("record.json")}" download>Full record (JSON)</a></div>
      <div class="card manual" id="proto">${md(r.protocol || "")}</div>
      <h2>Methods</h2><p class="small">A draft written from the record. Edit it for your paper; your version is saved next to the draft, which is kept.${r.methods_edited ? ' <b>Showing your edited version.</b>' : ""}</p>
      <textarea id="meth" rows="14" style="width:100%;font:15px/1.6 var(--body);padding:12px;background:var(--bone);border:1px solid var(--rule);color:var(--ink)" aria-label="Methods text">${esc(r.methods || "")}</textarea>
      <div class="row" style="margin-top:10px"><button class="btn primary" id="msave">Save my version</button><button class="btn" id="mreset" ${r.methods_edited ? "" : "disabled"}>Go back to the draft</button>
        <button class="btn" id="mcopy">Copy</button><a class="btn small" href="${file(r.methods_edited ? "methods_edited.md" : "methods.md")}" download>Download</a></div>
      <h2>References</h2><div class="card"><ul>${(r.references || "").trim().split("\n").map(x => `<li class="small">${esc(x)}</li>`).join("")}</ul>
        <div class="row"><a class="btn small" href="${file("references.txt")}" download>Text</a><a class="btn small" href="${file("references.bib")}" download>BibTeX</a></div></div>
      <h2>Repeat this run</h2><div class="card"><p class="small">The folder <code>${esc(r.dir)}/rerun</code> holds the exact settings, the job scripts and the live-session steps. To repeat the run, on the cluster, with the Python that has Everyome:</p>
        <pre class="script">python -m everyome.core.rerun ${esc(r.dir)}/rerun /path/to/new/run/folder --submit
python -m everyome.core.rerun ${esc(r.dir)}/rerun /path/to/new/run/folder --session   # after its jobs finish</pre>
        <p class="small muted">Leave out <code>--submit</code> first to read the job scripts without sending them. The repeat gets its own folder; this run is never changed.</p></div>`;
    $("#print", el).onclick = () => { const w = window.open("", "_blank"); w.document.write(`<!doctype html><title>${esc(run.id)} protocol</title><style>body{font:15px/1.55 Georgia,serif;max-width:900px;margin:30px auto;color:#111}table{border-collapse:collapse;width:100%;margin:8px 0}td,th{border:1px solid #bbb;padding:4px 6px;text-align:left;font-size:13px}code{font-size:12px}</style>${$("#proto", el).innerHTML}`); w.document.close(); w.focus(); w.print(); };
    $("#msave", el).onclick = e => guarded(e.currentTarget, async () => { await api("/api/run/methods", { method: "POST", body: { text: $("#meth", el).value } }); r = await api("/api/run/record"); draw(); toast("Your methods text is saved.", true); });
    $("#mreset", el).onclick = e => guarded(e.currentTarget, async () => { r = await api("/api/run/methods/reset", { method: "POST" }); draw(); toast("Back to the generated draft.", true); });
    $("#mcopy", el).onclick = () => navigator.clipboard.writeText($("#meth", el).value).then(() => toast("Copied.", true));
  }
  $("#build", el).onclick = e => { const btn = e.currentTarget; guarded(btn, async () => {
    $("#when", el).textContent = "Building…"; r = await api("/api/run/record", { method: "POST" });
    $("#when", el).textContent = "Last built " + r.created + "."; btn.textContent = "Update the record"; draw(); toast("Record built.", true);
  }); };
  draw();
};

VIEWS.manual = async (el, mid) => {
  const m = ST.modules.find(x => x.id === mid) || curModule(), r = await api(`/api/modules/${encodeURIComponent(m.id)}/manual`);
  el.innerHTML = head("?", "Learn", m.name + " manual", "") +
    (m.playground ? `<div class="notice">See what each setting does on a toy dataset in the <button class="btn small" data-go="playground:${esc(m.id)}">Playground →</button></div>` : "") +
    `<div class="card manual">${md(r.markdown)}</div>` +
    (mid ? `<div class="row" style="margin-top:18px"><button class="btn" data-go="modules">← Back to analyses</button></div>` : "");
};

// A module's playground: its own scripts (listed in the manifest, loaded once, in order) run a toy analysis in the browser.
const PLAYGROUND_LOADED = {};
async function loadScript(src) {
  await new Promise((ok, bad) => { const s = document.createElement("script"); s.src = src; s.onload = ok;
    s.onerror = () => bad(new Error("The playground could not be loaded.")); document.head.appendChild(s); });
}
VIEWS.playground = async (el, mid) => {
  const m = ST.modules.find(x => x.id === mid) || curModule(), pg = m.playground;
  if (!PLAYGROUND_LOADED[m.id]) {
    for (let i = 0; i < pg.n_scripts; i++) await loadScript(`/api/modules/${encodeURIComponent(m.id)}/playground/${i}`);
    PLAYGROUND_LOADED[m.id] = true;
  }
  const P = window[pg.object];
  el.innerHTML = head("?", "Learn · " + m.name, "Playground", esc(pg.lede || "")) +
    (pg.intro || []).map(p => `<p>${esc(p)}</p>`).join("") +
    `<h2>Things to try</h2>${P.presetsHtml()}<div id="pg-root"></div>` +
    (pg.caveats?.length ? `<h2>What is simplified</h2><ul>${pg.caveats.map(c => `<li>${esc(c)}</li>`).join("")}</ul>` : "") +
    (pg.credit ? `<p class="small muted" style="margin-top:18px">${esc(pg.credit)}</p>` : "") +
    `<div class="row" style="margin-top:18px">${m.has_manual ? `<button class="btn" data-go="manual:${esc(m.id)}">Read the manual</button>` : ""}<button class="btn" data-go="modules">← Back to analyses</button></div>`;
  el.addEventListener("click", e => { const b = e.target.closest("[data-preset]"); if (b) P.applyPreset(+b.dataset.preset); });
  P.mount($("#pg-root", el));
};

// ------------------------------------------------------------------ themes
// Intent: new users start in Nematostella, light mode; a style they pick is remembered.
const DEFAULT_THEME = "nematostella", DEFAULT_MODE = "light";
const THEME = { list: [], groups: [], id: localStorage.getItem("everyome-theme") || DEFAULT_THEME, mode: localStorage.getItem("everyome-mode") || DEFAULT_MODE };
const darkQuery = matchMedia("(prefers-color-scheme: dark)");
const effectiveMode = () => THEME.mode === "system" ? (darkQuery.matches ? "dark" : "light") : THEME.mode;

function applyTheme(rerender = true) {
  const t = THEME.list.find(x => x.id === THEME.id) || THEME.list[0]; if (!t) return;
  const mode = effectiveMode(), v = t[mode], root = document.documentElement, vars = {};
  for (const [k, x] of Object.entries(v)) if (k !== "palette") vars["--" + k] = x;
  for (const [k, x] of Object.entries(t.fonts)) vars["--" + k] = x;
  for (const [k, x] of Object.entries(vars)) root.style.setProperty(k, x);
  root.style.colorScheme = mode; root.dataset.theme = t.id; root.dataset.mode = mode;
  Object.assign(COL, { gold: v.gold, golddk: v.golddk, goldlt: v.goldlt, ox: v.ox, wine: v.wine, plum: v.plum, ink: v.ink, muted: v.muted,
    rule: v.rule, card: v.card, parch: v.parch, ok: v.ok });
  PALETTE = v.palette.slice();
  $("#tdots").innerHTML = t.swatches.map(c => `<i style="background:${c}"></i>`).join("");
  $("#theme-select").title = `${t.name}: ${t.species} (${t.common})`;
  localStorage.setItem("everyome-vars", JSON.stringify({ vars, mode }));
  if (rerender && ST.page) go(ST.page);
}
async function initThemes() {
  try { const d = await (await fetch("themes.json")).json(); THEME.list = d.themes; THEME.groups = d.groups; }
  catch { return; }
  $("#theme-select").innerHTML = THEME.groups.map(g => `<optgroup label="${esc(g)}">${THEME.list.filter(t => t.group === g)
    .map(t => `<option value="${t.id}">${esc(t.name)}${t.style === "vivid" ? " ✦" : ""} · ${esc(t.common)}</option>`).join("")}</optgroup>`).join("");
  if (!THEME.list.some(t => t.id === THEME.id)) THEME.id = DEFAULT_THEME;
  $("#theme-select").value = THEME.id; $("#mode-select").value = THEME.mode;
  $("#theme-select").onchange = e => { THEME.id = e.target.value; localStorage.setItem("everyome-theme", THEME.id); applyTheme(); };
  $("#mode-select").onchange = e => { THEME.mode = e.target.value; localStorage.setItem("everyome-mode", THEME.mode); applyTheme(); };
  darkQuery.addEventListener("change", () => { if (THEME.mode === "system") applyTheme(); });
  applyTheme(false);
}

// ------------------------------------------------------------------ start
(async () => {
  await initThemes();
  ST.modules = (await api("/api/modules")).modules.map(m => ({ ...m, fields_all: [...m.inputs, ...m.params] }));
  ST.suites = await api("/api/suites");
  await refreshState();
  go("home");
})();
