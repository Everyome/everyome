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
      ...(hasSession(m) ? [{ id: "session", title: "Live session", ok: runDone(), done: ST.sess === "READY" }] : [])] },
  ];
  if (m && hasSession(m)) groups.push({ group: m.name, medal: "II", items: m.steps.map(st => (
    { id: "step:" + st.id, title: st.title, ok: ST.sess === "READY", done: false })) });
  if (m) groups.push({ group: "Learn", medal: "?", items: [{ id: "manual", title: "Manual", ok: m.has_manual, done: false }] });
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
  if (ST.state.run?.session_job) {
    try { const s = await api("/api/session/status"); ST.sess = s.state; ST.eng = s.engine || null; } catch { ST.sess = null; }
  } else ST.sess = null;
  renderSide(); renderPills();
}

async function go(id) {
  clearTimers(); ST.page = id; renderSide();
  const page = $("#page");
  page.innerHTML = "";
  try { await (id.startsWith("step:") ? moduleStep(page, id.slice(5)) : id.startsWith("manual:") ? VIEWS.manual(page, id.slice(7)) : id.startsWith("suite:") ? suitePage(page, id.slice(6)) : VIEWS[id](page)); }
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
  const max = Math.max(...items.map(d => d[1]), 1), left = 120, bh = Math.min(26, (h - 10) / items.length - 6);
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
// Minimal Markdown for module manuals: headings, paragraphs, lists, tables, **bold**, *italic*, `code`.
function md(src) {
  const inline = s => esc(s).replace(/`([^`]+)`/g, "<code>$1</code>").replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>").replace(/\*([^*]+)\*/g, "<i>$1</i>");
  const out = [], lines = src.split("\n"); let i = 0;
  while (i < lines.length) {
    const l = lines[i];
    if (!l.trim()) { i++; continue; }
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
    const para = []; while (i < lines.length && lines[i].trim() && !lines[i].match(/^(#|\||\s*(\d+\.|-)\s)/)) para.push(lines[i++].trim());
    out.push(`<p>${inline(para.join(" "))}</p>`);
  }
  return out.join("\n");
}

// Follow a background step in the session, updating a progress bar; resolves with the final status.
async function followTask(box) {
  for (;;) {
    const s = await api("/api/s/status"); ST.eng = s;
    if (box) box.innerHTML = `<div class="progress"><i style="width:${s.task.progress}%"></i></div><span class="small muted">${esc(s.task.message || "")}</span>`;
    if (!s.task.running) { renderSide(); if (s.task.error) throw new Error(s.task.error); return s; }
    await sleep(600);
  }
}

// What a module's ui.js receives.
const MODULE_VIEWS = {};
window.Everyome = {
  registerViews(moduleId, views) { MODULE_VIEWS[moduleId] = views; },
  call: (method, body = {}) => api("/api/s/call/" + method, { method: "POST", body }),
  status: () => api("/api/s/status"),
  helpers: { $, $$, esc, fmt, toast, guarded, followTask, barChart, histChart, COL: () => COL, PALETTE: () => PALETTE, every },
};
async function loadModuleUi(m) {
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
    "Everyome does the heavy work on a computing cluster and shows it here. Use the demo cluster to try it out, or connect to your own with your SSH key.") +
    `${s.connected ? `<div class="notice">Connected to <b>${esc(s.label)}</b>. <button class="btn small" id="disc">Disconnect</button></div>` : ""}
    <div class="grid g2">
      <button class="choice" id="pick-demo" aria-pressed="${s.demo}"><div class="label">Try it out</div><h3>Demo cluster</h3>
        <p>A practice cluster on this computer with example data and a pretend job scheduler. Nothing leaves your machine.</p></button>
      <button class="choice" id="pick-ssh" aria-pressed="${s.connected && !s.demo}"><div class="label">Real data</div><h3>My cluster</h3>
        <p>Connect with the SSH key you already use. No passwords are stored; jobs run under your own account.</p></button>
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
      go(hasBatch(curModule()) ? "run" : "session"); });
  });
  $("#create", el).onclick = e => guarded(e.currentTarget, async () => {
    await api("/api/project/create", { method: "POST", body: { name: $("#pname", el).value } }); await refreshState();
    toast("Project created.", true); go(ST.pick ? "settings" : "modules");
  });
};

const suiteName = id => ST.suites?.suites.find(s => s.id === id)?.name || id;
const moduleCard = m => `<div class="choice" aria-pressed="${curModule()?.id === m.id}"><div class="label">${esc(suiteName(m.suite))} · v${esc(m.version)}</div><h3>${esc(m.name)}</h3><p>${esc(m.summary)}</p>
  <div class="tags">${m.kind.map(k => `<span class="tag">${{ batch: "Cluster jobs", interactive: "Live session", local: "Runs here" }[k]}</span>`).join("")}</div>
  <div class="acts"><button class="btn primary small" data-pick="${esc(m.id)}">Start a new run</button>${m.has_manual ? `<button class="btn small" data-man="${esc(m.id)}">Read the manual</button>` : ""}</div></div>`;
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

const fieldHtml = (f, val) => {
  const help = f.help ? `<small>${esc(f.help)}${f.min != null || f.max != null ? ` (${f.min != null ? "from " + f.min : ""}${f.min != null && f.max != null ? " " : ""}${f.max != null ? "up to " + f.max : ""})` : ""}</small>` : "";
  const req = f.required ? ' <span class="muted small">(required)</span>' : "";
  if (f.type === "bool") return `<label class="field" data-f="${f.id}"><span><input type="checkbox" name="${f.id}" ${val ? "checked" : ""}>${esc(f.label)}</span>${help}</label>`;
  if (f.type === "choice") return `<label class="field" data-f="${f.id}"><span>${esc(f.label)}${req}</span><select name="${f.id}">${f.choices.map(c => `<option ${String(c) === String(val) ? "selected" : ""}>${esc(c)}</option>`).join("")}</select>${help}</label>`;
  if (f.type === "file" || f.type === "folder") return `<label class="field" data-f="${f.id}"><span>${esc(f.label)}${req}</span><span class="pathrow"><input type="text" class="mono" name="${f.id}" data-path="${f.type === "file" ? "file" : "dir"}" value="${esc(val ?? "")}">
    <button type="button" class="btn small" data-browse="${f.id}">Browse</button></span>${help}</label>`;
  const num = f.type === "int" || f.type === "float";
  return `<label class="field" data-f="${f.id}"><span>${esc(f.label)}${req}</span><input type="${num ? "number" : "text"}" name="${f.id}" value="${esc(val ?? "")}"
    ${num && f.min != null ? `min="${f.min}"` : ""} ${num && f.max != null ? `max="${f.max}"` : ""} ${f.type === "float" ? 'step="any"' : ""}>${help}</label>`;
};
const readField = (el, f) => { const i = $(`[name=${f.id}]`, el); return f.type === "bool" ? i.checked : i.value.trim(); };

VIEWS.settings = async el => {
  const m = curModule(), s = ST.state, run = s.run;
  const demoVal = f => s.demo && f.demo ? `${s.conn.data_root}/${m.id}/${f.demo}` : f.default;
  const val = f => run ? run.values[f.id] : demoVal(f);
  const res = run?.resources || { ...m.resources, partition: s.conn.partition };
  el.innerHTML = head("I", m.name, "Inputs and settings", esc(m.summary)) +
    (run ? `<div class="notice">These are the settings of run <b class="mono">${esc(run.id)}</b>. To change them, start a new run below; the old one is kept.</div>` : "") +
    (s.demo && !run ? `<div class="notice">Demo inputs are filled in for you. Browse to see the demo data.</div>` : "") +
    `<div class="grid g-side"><div>
      ${m.inputs.length ? `<div class="card" style="margin-bottom:18px"><div class="label">Inputs</div>${m.inputs.map(f => fieldHtml(f, val(f))).join("")}</div>` : ""}
      ${m.params.length ? `<div class="card"><div class="label">Settings</div><div class="grid g2">${m.params.map(f => fieldHtml(f, val(f))).join("")}</div></div>` : ""}
    </div>${hasBatch(m) ? `<div class="card"><div class="label">Cluster resources</div>
      ${[["partition", "Partition", "Leave empty for the default queue."], ["cpus", "CPUs per job", ""], ["mem", "Memory per job", "e.g. 4G"], ["time", "Time limit per job", "hours:minutes:seconds"]]
        .map(([k, l, h]) => `<label class="field"><span>${l}</span><input type="text" class="mono" name="res_${k}" value="${esc(res[k] ?? "")}">${h ? `<small>${h}</small>` : ""}</label>`).join("")}</div>` : ""}</div>
    <div class="row" style="margin-top:18px"><button class="btn primary" id="save">${run ? "Start a new run with these settings →" : "Create the run →"}</button><button class="btn" id="reset">Restore defaults</button></div>`;
  el.addEventListener("click", async e => {
    const b = e.target.closest("[data-browse]"); if (!b) return;
    const inp = $(`[name=${b.dataset.browse}]`, el), mode = inp.dataset.path, cur = inp.value || s.conn.data_root || s.conn.projects_root;
    const v = await browse(mode === "file" ? cur.replace(/\/[^/]*$/, "") : cur, mode, mode === "dir" ? "Choose a folder" : "Choose a file");
    if (v) inp.value = v;
  });
  $("#reset", el).onclick = () => m.fields_all.forEach(f => { const i = $(`[name=${f.id}]`, el); if (f.type === "bool") i.checked = !!f.default; else i.value = demoVal(f) ?? ""; });
  $("#save", el).onclick = e => guarded(e.currentTarget, async () => {
    $$(".field.bad", el).forEach(x => x.classList.remove("bad"));
    const values = {}, resources = {};
    m.fields_all.forEach(f => values[f.id] = readField(el, f));
    ["partition", "cpus", "mem", "time"].forEach(k => { const i = $(`[name=res_${k}]`, el); if (i) resources[k] = i.value.trim(); });
    const missing = m.fields_all.filter(f => f.required && values[f.id] === "");
    if (missing.length) { missing.forEach(f => $(`[data-f=${f.id}]`, el).classList.add("bad")); throw new Error("Please fill in: " + missing.map(f => f.label).join(", ")); }
    await api("/api/run/create", { method: "POST", body: { module: m.id, values, resources } }); await refreshState();
    toast("Run created. Nothing has been submitted yet.", true); go(hasBatch(m) ? "run" : "session");
  });
};

VIEWS.run = async el => {
  const m = curModule(), run = ST.state.run;
  el.innerHTML = head("I", m.name, "Run on the cluster",
    "You will see the exact job scripts before anything is sent. Each stage waits for the one before, so you can close the app and come back later.") +
    `<p class="small muted">Run <span class="mono">${esc(run.id)}</span>, created ${esc(run.created)}${run.defaults_changed.length ? `; settings changed from the defaults: ${run.defaults_changed.map(esc).join(", ")}` : ""}.</p>
    <div class="row" style="margin-bottom:16px"><button class="btn primary" id="runall">Check and submit…</button><button class="btn" id="rerun" disabled>Re-run from selected stage…</button><button class="btn danger" id="cancel">Cancel jobs</button></div><div id="fail"></div>
    <div class="grid g-side"><div class="card"><div class="label">Stages</div><ol class="stages" id="stages">
      ${m.stages.map(s => `<li data-sid="${s.id}"><span class="n">${s.id}</span><span>${esc(s.title)}</span><span class="state" data-st="${s.id}">Not run</span><span class="small muted mono" data-el="${s.id}"></span></li>`).join("")}</ol></div>
    <div class="card"><div class="label">Job log</div><p class="small muted" id="logtitle">Select a stage to see its log.</p><pre class="log" id="log">–</pre></div></div>
    <div id="next"></div>`;
  let sel = null;
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
    if (r.done && !ST.state.run.done) { ST.state.run.done = true; renderSide(); }
    $("#next", el).innerHTML = r.done ? `<div class="notice" style="margin-top:18px">All stages finished. Results are in <span class="mono">${esc(run.dir)}/results</span>.</div>
      ${hasSession(m) ? `<div class="row"><button class="btn primary" data-go="session">Continue to the live session →</button></div>` : ""}` : "";
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
    await api("/api/run/submit", { method: "POST", body: { start_at: from } }); await refreshState(); toast("Jobs submitted.", true); poll();
  };
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

VIEWS.manual = async (el, mid) => {
  const m = ST.modules.find(x => x.id === mid) || curModule(), r = await api(`/api/modules/${encodeURIComponent(m.id)}/manual`);
  el.innerHTML = head("?", "Learn", m.name + " manual", "") + `<div class="card manual">${md(r.markdown)}</div>` +
    (mid ? `<div class="row" style="margin-top:18px"><button class="btn" data-go="modules">← Back to analyses</button></div>` : "");
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
