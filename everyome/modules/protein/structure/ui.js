/* Views for structure prediction: what the pipeline made (Run page), then the live session: every prediction, one
   structure in 3D with its pLDDT and PAE, methods side by side, export. Engine: engine.py. The 3D view is a small
   canvas drawing of the Cα trace (no viewer library), enough to see the fold and its confidence. */
"use strict";
(() => {
  const E = window.Everyome, H = E.helpers;
  const { $, $$, esc, fmt, fmtSize, toast, guarded, guide } = H;
  const COL = () => H.COL(), PALETTE = () => H.PALETTE();
  const lede = t => `<p class="lede">${t}</p>`;
  // Intent: the pLDDT colours used by the AlphaFold database and most viewers, so pictures match what people know.
  const BAND = [["very high", 90, "#0053D6"], ["confident", 70, "#65CBF3"], ["low", 50, "#FFDB13"], ["very low", 0, "#FF7D45"]];
  const bandColour = v => BAND.find(b => v >= b[1])[2];
  let current = null;                                    // the prediction last looked at, shared by the views

  async function ensure() {
    const st = await E.status();
    if (!st.loaded) await E.call("load");
    return E.call("predictions");
  }
  const label = p => `${p.id} · ${p.method}${p.variant ? ` (${p.variant.replace(/_/g, " ")})` : ""}`;
  const bandsBar = (b, w = 160) => `<svg width="${w}" height="12" role="img" aria-label="Share of residues in each confidence band">${(() => {
    let x = 0; return BAND.map(([n, , c]) => { const ww = w * (b[n] || 0) / 100, s = `<rect x="${x}" y="0" width="${ww}" height="12" fill="${c}"><title>${n}: ${b[n]}%</title></rect>`; x += ww; return s; }).join(""); })()}</svg>`;
  const bandLegend = () => `<div class="legend">${BAND.map(([n, lo, c], i) => `<span><i style="background:${c}"></i>${n} (${i ? `${lo}–${BAND[i - 1][1]}` : "> 90"})</span>`).join("")}</div>`;

  // ---------------------------------------------------------------- Run page
  async function report(el, q) {
    el.innerHTML = `<h2>What the pipeline made</h2><div class="card"><div class="label">Predicted structures</div>
      ${q.structures.length ? `<ul class="small">${q.structures.map(p => `<li><code style="word-break:break-all">${esc(p)}</code></li>`).join("")}</ul>
        <p class="small muted">Look at them in the live session.</p>` : `<div class="notice warn">No structures were found. Check the pipeline log.</div>`}
      ${q.reports.length ? `<div class="label" style="margin-top:12px">The pipeline's reports</div><div class="row" style="flex-wrap:wrap;gap:6px">${q.reports.map(r =>
        `<a class="btn small" href="/api/run/file?path=${encodeURIComponent(r)}" target="_blank" rel="noopener">${esc(r.split("/").pop().replace(/_report\.html$/, "").replace(/_/g, " "))}</a>`).join("")}</div>` : ""}
      ${E.state().demo ? `<p class="small muted" style="margin-top:10px">On the demo cluster a stand-in replaces the pipeline; its reports are placeholders.</p>` : ""}${guide("run_report")}</div>`;
  }

  // ---------------------------------------------------------------- predictions
  async function overview(el) {
    const list = await ensure();
    current = current && list.some(p => p.key === current) ? current : list[0]?.key;
    // Intent: ipTM exists only for complexes; a domain is shown as its first to last residue (its parts on hover).
    const iptm = list.some(p => p.iptm != null), span = d => `${d.ranges[0][0]}–${d.ranges[d.ranges.length - 1][1]}`;
    el.innerHTML = lede("Every structure the pipeline predicted (the top-ranked model of each); click a name to look at it. The bar shows how much of each protein falls in each confidence band; domains are parts that are both confident and placed reliably relative to themselves.") +
      `<div class="card" style="overflow:auto"><table><thead><tr><th>Protein</th><th>Method</th><th class="num">Residues</th><th class="num">Mean pLDDT</th><th>Confidence</th><th class="num">pTM</th>${iptm ? `<th class="num">ipTM</th>` : ""}<th>Domains</th></tr></thead><tbody>
        ${list.map(p => `<tr><td><a href="#" data-look="${esc(p.key)}" title="Look at this structure"><b>${esc(p.id)}</b></a>${p.chains.length > 1 ? ` <span class="small muted">${p.chains.length} chains</span>` : ""}</td><td>${esc(p.method)}</td><td class="num">${fmt(p.length)}</td>
          <td class="num">${p.mean_plddt.toFixed(1)}</td><td>${bandsBar(p.bands, 110)}</td><td class="num">${p.ptm == null ? "–" : p.ptm.toFixed(2)}</td>${iptm ? `<td class="num">${p.iptm == null ? "–" : p.iptm.toFixed(2)}</td>` : ""}
          <td class="small" style="white-space:nowrap">${p.has_pae ? (p.domains.length ? p.domains.map(d => `<span title="${d.ranges.map(r => r.join("–")).join(", ")}">${d.name} ${span(d)}</span>`).join(" · ") : "none") : "no PAE"}</td>
          </tr>`).join("")}</tbody></table>${bandLegend()}${guide("plddt")}${guide("domains", { title: "How domains are found" })}</div>
      <div class="row" style="margin-top:18px"><button class="btn primary" data-look="${esc(current)}">Look at a structure →</button></div>`;
    $$("[data-look]", el).forEach(b => b.onclick = e => { e.preventDefault(); current = b.dataset.look; H.go("step:structure"); });
  }

  // ---------------------------------------------------------------- the 3D view
  function viewer(canvas, residues, colourOf, tip) {
    const ctx = canvas.getContext("2d"), dpr = window.devicePixelRatio || 1;
    let R = [[1, 0, 0], [0, 1, 0], [0, 0, 1]], zoom = 1, drag = null, hover = -1, active = false;
    // Intent: size the view to the bulk of the protein (90% of residues), so long loose ends do not shrink the fold.
    const dists = residues.map(r => Math.hypot(...r.xyz)).sort((a, b) => a - b), radius = Math.max(dists[Math.floor(0.9 * (dists.length - 1))] * 1.1, 10);
    const mul = (A, B) => A.map((r, i) => B[0].map((_, j) => r.reduce((s, _, k) => s + A[i][k] * B[k][j], 0)));
    const rot = (ax, a) => { const c = Math.cos(a), s = Math.sin(a); return ax === "x" ? [[1, 0, 0], [0, c, -s], [0, s, c]] : [[c, 0, s], [0, 1, 0], [-s, 0, c]]; };
    R = mul(rot("x", -0.5), mul(rot("y", 0.6), R));
    const linked = residues.map((r, i) => i > 0 && residues[i - 1].chain === r.chain && Math.hypot(...r.xyz.map((v, k) => v - residues[i - 1].xyz[k])) < 7.5);
    let pts = [];
    function draw() {
      const w = canvas.clientWidth, h = canvas.clientHeight;
      if (canvas.width !== w * dpr) { canvas.width = w * dpr; canvas.height = h * dpr; }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const c = COL(), scale = 0.45 * Math.min(w, h) / radius * zoom;
      ctx.fillStyle = c.card; ctx.fillRect(0, 0, w, h);
      pts = residues.map(r => { const p = R.map(row => row[0] * r.xyz[0] + row[1] * r.xyz[1] + row[2] * r.xyz[2]); return [w / 2 + p[0] * scale, h / 2 - p[1] * scale, p[2]]; });
      // Painter's order: far segments first; nearer ones drawn wider, with a dark edge so crossings read as tubes.
      const segs = [];
      for (let i = 1; i < residues.length; i++) if (linked[i]) segs.push([i - 1, i, (pts[i - 1][2] + pts[i][2]) / 2]);
      segs.sort((a, b) => a[2] - b[2]);
      ctx.lineCap = "round";
      for (const [a, b, z] of segs) {
        const near = 0.5 + 0.5 * (z / radius + 1) / 2, wd = Math.max(1.5, 5.5 * near * Math.sqrt(zoom));
        ctx.globalAlpha = 0.45 + 0.55 * near;
        ctx.strokeStyle = c.ink; ctx.lineWidth = wd + 1.6; ctx.beginPath(); ctx.moveTo(pts[a][0], pts[a][1]); ctx.lineTo(pts[b][0], pts[b][1]); ctx.stroke();
        const mx = (pts[a][0] + pts[b][0]) / 2, my = (pts[a][1] + pts[b][1]) / 2;
        ctx.lineWidth = wd;
        ctx.strokeStyle = colourOf(residues[a], a); ctx.beginPath(); ctx.moveTo(pts[a][0], pts[a][1]); ctx.lineTo(mx, my); ctx.stroke();
        ctx.strokeStyle = colourOf(residues[b], b); ctx.beginPath(); ctx.moveTo(mx, my); ctx.lineTo(pts[b][0], pts[b][1]); ctx.stroke();
      }
      ctx.globalAlpha = 1;
      if (hover >= 0) { ctx.strokeStyle = c.ink; ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(pts[hover][0], pts[hover][1], 7, 0, 2 * Math.PI); ctx.stroke(); }
    }
    canvas.onpointerdown = e => { drag = [e.clientX, e.clientY]; active = true; canvas.setPointerCapture(e.pointerId); };
    canvas.onpointerleave = () => { active = false; };
    canvas.onpointerup = () => { drag = null; };
    canvas.onpointermove = e => {
      if (drag) { R = mul(rot("y", (e.clientX - drag[0]) * 0.01), mul(rot("x", (e.clientY - drag[1]) * 0.01), R)); drag = [e.clientX, e.clientY]; draw(); return; }
      const b = canvas.getBoundingClientRect(), x = e.clientX - b.left, y = e.clientY - b.top;
      let best = -1, bd = 10;
      pts.forEach((p, i) => { const d = Math.hypot(p[0] - x, p[1] - y); if (d < bd) { bd = d; best = i; } });
      if (best !== hover) { hover = best; draw(); tip(best >= 0 ? residues[best] : null); }
    };
    // Intent: the wheel scrolls the page unless the view was clicked (or Ctrl/⌘ is held), so it never traps the page.
    canvas.onwheel = e => { if (!active && !e.ctrlKey && !e.metaKey) return; e.preventDefault(); zoom = Math.min(6, Math.max(0.4, zoom * (e.deltaY < 0 ? 1.1 : 0.9))); draw(); };
    draw();
    return { redraw: (f) => { colourOf = f || colourOf; draw(); } };
  }

  function plddtSvg(ranks, domains) {
    const w = 760, h = 220, L = 40, B = 30, c = COL(), names = Object.keys(ranks), n = ranks[names[0]].length;
    const X = i => L + i / Math.max(1, n - 1) * (w - L - 10), Y = v => 10 + (100 - v) / 100 * (h - B - 10);
    let s = `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="pLDDT along the sequence">`;
    BAND.forEach(([, lo, col], i) => { const hi = i ? BAND[i - 1][1] : 100; s += `<rect x="${L}" y="${Y(hi)}" width="${w - L - 10}" height="${Y(lo) - Y(hi)}" fill="${col}" opacity=".12"/>`; });
    (domains || []).forEach(d => d.ranges.forEach(([a, b]) => { s += `<rect x="${X(a - 1)}" y="${h - B + 2}" width="${X(b - 1) - X(a - 1)}" height="6" fill="${c.golddk}"><title>${d.name}</title></rect>`; }));
    [0, 50, 70, 90, 100].forEach(v => s += `<text x="${L - 6}" y="${Y(v) + 4}" text-anchor="end" class="ax">${v}</text>`);
    names.slice().reverse().forEach((r, k) => { const top = r === names[0];
      s += `<polyline fill="none" stroke="${top ? c.ink : c.muted}" stroke-width="${top ? 1.8 : 0.8}" opacity="${top ? 1 : 0.6}" points="${ranks[r].map((v, i) => `${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join(" ")}"><title>${esc(r)}</title></polyline>`; });
    for (let i = 0; i < n; i += Math.max(1, Math.round(n / 8 / 10) * 10 || 10)) s += `<text x="${X(i)}" y="${h - 4}" text-anchor="middle" class="ax">${i + 1}</text>`;
    return s + `</svg><p class="small muted">Black: the top-ranked model${names.length > 1 ? `; grey: the other ${names.length - 1} ranked models` : ""}. Bars under the axis mark the domains.</p>`;
  }

  function paeCanvas(canvas, pae, domains) {
    const c = COL(), n = pae.cells.length, size = canvas.clientWidth, dpr = window.devicePixelRatio || 1, ctx = canvas.getContext("2d");
    canvas.width = canvas.height = size * dpr; canvas.style.height = size + "px";
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const lo = H.hexRgb(c.plum), hi = H.hexRgb(c.card), cell = size / n;
    for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) {
      const t = Math.min(1, pae.cells[i][j] / 30);
      ctx.fillStyle = `rgb(${lo.map((v, k) => Math.round(v + (hi[k] - v) * t))})`;
      ctx.fillRect(j * cell, i * cell, cell + 0.6, cell + 0.6);
    }
    ctx.strokeStyle = c.gold; ctx.lineWidth = 2;
    (domains || []).forEach(d => { const ii = d.ranges.flatMap(([a, b]) => [a, b]); const a = Math.min(...ii) - 1, b = Math.max(...ii);
      ctx.strokeRect(a / pae.step * cell, a / pae.step * cell, (b - a) / pae.step * cell, (b - a) / pae.step * cell); });
  }

  async function structureView(el) {
    const list = await ensure();
    current = current && list.some(p => p.key === current) ? current : list[0]?.key;
    el.innerHTML = lede("One predicted structure. Drag to turn it, click it and scroll to zoom, point at a residue to see its confidence. Below: confidence along the sequence, and how reliably each part is placed relative to the others.") +
      `<div class="card"><div class="row" style="gap:12px;flex-wrap:wrap;align-items:center">
          <label class="small">Prediction <select id="pick" style="width:auto">${list.map(p => `<option value="${esc(p.key)}" ${p.key === current ? "selected" : ""}>${esc(label(p))}</option>`).join("")}</select></label>
          <label class="small">Colour by <select id="by" style="width:auto"><option value="plddt">pLDDT</option><option value="domain">domain</option><option value="chain">chain</option></select></label>
          <button class="btn small" id="reset">Reset view</button></div>
        <div style="position:relative;margin-top:10px"><canvas id="mol" style="width:100%;height:440px;border-radius:6px;touch-action:none;cursor:grab" aria-label="3D structure"></canvas>
          <div id="tip" class="small" style="position:absolute;left:10px;top:8px;background:${COL().card};padding:2px 6px;border-radius:4px"></div></div>
        <div id="leg"></div><div id="facts" class="small" style="margin-top:6px"></div>${guide("viewer")}</div>
      <div class="card" style="margin-top:18px"><div class="label">pLDDT along the sequence</div><div id="pl"></div>${guide("plddt")}</div>
      <div class="card" style="margin-top:18px"><div class="label">Predicted aligned error</div><div id="pae"></div>${guide("pae")}</div>
      <div class="row" style="margin-top:18px"><button class="btn primary" data-go="step:compare">Compare methods →</button><button class="btn" data-go="step:export">Export</button></div>`;
    let v = null, s = null;
    const P = PALETTE();
    const colour = by => by === "plddt" ? r => bandColour(r.plddt)
      : by === "domain" ? r => r.domain ? P[(+r.domain.slice(1) - 1) % P.length] : COL().rule
      : r => P[s.chains.indexOf(r.chain) % P.length];
    const legend = by => by === "plddt" ? bandLegend()
      : by === "domain" ? (s.domains.length ? `<div class="legend">${s.domains.map((d, i) => `<span><i style="background:${P[i % P.length]}"></i>${d.name}: ${d.ranges.map(r => r.join("–")).join(", ")}</span>`).join("")}<span><i style="background:${COL().rule}"></i>not in a domain</span></div>`
        : `<p class="small muted">No domains: ${list.find(p => p.key === current).has_pae ? "no part is both confident and rigid" : "this method gives no PAE"}.</p>`)
      : `<div class="legend">${s.chains.map((ch, i) => `<span><i style="background:${P[i % P.length]}"></i>chain ${esc(ch)}</span>`).join("")}</div>`;
    async function show() {
      const p = list.find(x => x.key === current), by = $("#by", el).value;
      s = await E.call("structure", { key: current });
      v = viewer($("#mol", el), s.residues, colour(by), r => { $("#tip", el).textContent = r ? `${r.chain}${r.num} ${r.aa} · pLDDT ${r.plddt}${r.domain ? " · " + r.domain : ""}` : ""; });
      $("#leg", el).innerHTML = legend(by);
      $("#facts", el).innerHTML = `${fmt(p.length)} residues${p.chains.length > 1 ? ` in ${p.chains.length} chains` : ""} · mean pLDDT ${p.mean_plddt.toFixed(1)}${p.ptm != null ? ` · pTM ${p.ptm.toFixed(2)}` : ""}${p.iptm != null ? ` · ipTM ${p.iptm.toFixed(2)}` : ""}`;
      const conf = await E.call("confidence", { key: current });
      $("#pl", el).innerHTML = plddtSvg(conf.plddt, s.domains);
      if (conf.pae) {
        $("#pae", el).innerHTML = `<div class="row" style="gap:18px;align-items:flex-start;flex-wrap:wrap"><canvas id="paec" style="width:360px;max-width:100%" aria-label="Predicted aligned error"></canvas>
          <div class="small" style="max-width:300px"><p>Rows: residue lined up on; columns: residue whose error is shown (1 to ${fmt(conf.pae.n)}${conf.pae.step > 1 ? `, averaged in blocks of ${conf.pae.step}` : ""}).</p>
          <div class="legend"><span><i style="background:${COL().plum}"></i>0 Å (confident)</span><span><i style="background:${COL().card};border:1px solid ${COL().rule}"></i>30 Å or more</span>${s.domains.length ? `<span><i style="background:${COL().gold}"></i>domains</span>` : ""}</div></div></div>`;
        paeCanvas($("#paec", el), conf.pae, s.domains);
      } else $("#pae", el).innerHTML = `<p class="small muted">${esc(p.method)} gives no predicted aligned error here. Predict with alphafold2 or colabfold as well to see it.</p>`;
    }
    $("#pick", el).onchange = e => { current = e.target.value; show(); };
    $("#by", el).onchange = e => { v.redraw(colour(e.target.value)); $("#leg", el).innerHTML = legend(e.target.value); };
    $("#reset", el).onclick = () => show();
    show();
  }

  // ---------------------------------------------------------------- compare
  async function compare(el) {
    const list = await ensure(), ids = [...new Set(list.map(p => p.id))], multi = ids.filter(id => list.filter(p => p.id === id).length > 1);
    if (!multi.length) {
      el.innerHTML = lede("Compare the same protein predicted by different methods.") + `<div class="card"><p>Each protein in this run was predicted by one method only. To compare, run again with several methods in <b>Prediction methods</b>, separated by commas (for example <code>alphafold2,esmfold</code>).</p>${guide("compare")}</div>`;
      return;
    }
    const cur = list.find(p => p.key === current)?.id;
    el.innerHTML = lede("The same protein predicted by different methods: their confidence, and how far apart their structures are after superposition.") +
      `<div class="card"><label class="small">Protein <select id="pid" style="width:auto">${multi.map(id => `<option ${id === cur ? "selected" : ""}>${esc(id)}</option>`).join("")}</select></label><div id="cmp" style="margin-top:12px"></div>${guide("compare")}</div>`;
    const show = async () => {
      const id = $("#pid", el).value, q = await E.call("compare", { id }), ps = list.filter(p => p.id === id);
      const confs = await Promise.all(ps.map(p => E.call("confidence", { key: p.key })));
      const P = PALETTE(), c = COL(), w = 760, h = 200, L = 40, n = confs[0].plddt.rank_0?.length || 1;
      const X = i => L + i / Math.max(1, n - 1) * (w - L - 10), Y = v => 10 + (100 - v) / 100 * (h - 30);
      const lines = confs.map((cf, k) => `<polyline fill="none" stroke="${P[k % P.length]}" stroke-width="1.6" points="${(cf.plddt.rank_0 || Object.values(cf.plddt)[0]).map((v, i) => `${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join(" ")}"/>`).join("");
      $("#cmp", el).innerHTML = `<table><thead><tr><th>Method</th><th class="num">Mean pLDDT</th><th>Confidence</th><th class="num">pTM</th><th>Domains</th></tr></thead><tbody>${ps.map(p => `<tr><td>${esc(p.method)}</td><td class="num">${p.mean_plddt.toFixed(1)}</td><td>${bandsBar(p.bands)}</td><td class="num">${p.ptm == null ? "–" : p.ptm.toFixed(2)}</td><td class="small">${p.has_pae ? p.domains.length : "no PAE"}</td></tr>`).join("")}</tbody></table>
        <svg class="chart" viewBox="0 0 ${w} ${h}" style="margin-top:12px" role="img" aria-label="pLDDT by method">${[0, 50, 70, 90, 100].map(v => `<line x1="${L}" x2="${w - 10}" y1="${Y(v)}" y2="${Y(v)}" stroke="${c.rule}"/><text x="${L - 6}" y="${Y(v) + 4}" text-anchor="end" class="ax">${v}</text>`).join("")}${lines}</svg>
        <div class="legend">${ps.map((p, k) => `<span><i style="background:${P[k % P.length]}"></i>${esc(p.method)}</span>`).join("")}</div>
        <table style="margin-top:12px"><thead><tr><th>Methods</th><th class="num">RMSD, all residues</th><th class="num">RMSD, confident residues</th><th class="num">Each domain on its own</th><th class="num">Confident in both</th></tr></thead><tbody>
          ${q.pairs.map(x => `<tr><td>${esc(x.a.split("/")[0])} vs ${esc(x.b.split("/")[0])}</td><td class="num">${x.rmsd == null ? esc(x.note) : x.rmsd.toFixed(2) + " Å"}</td><td class="num">${x.rmsd_confident == null ? "–" : x.rmsd_confident.toFixed(2) + " Å"}</td><td class="num">${x.domains?.length ? x.domains.map(d => `${d.name} ${d.rmsd.toFixed(2)} Å`).join(" · ") : "–"}</td><td class="num">${x.confident_residues ?? "–"}</td></tr>`).join("")}</tbody></table>`;
    };
    $("#pid", el).onchange = show;
    show();
  }

  // ---------------------------------------------------------------- export
  async function exportView(el) {
    const list = await ensure();
    el.innerHTML = lede("Save the top-ranked models as PDB files (pLDDT in the B-factor column), whole or with only their confident parts, with a summary table, in <code>results/final/</code>. The choice is noted in the run record.") +
      `<div class="card">${list.map(p => `<label class="row small" style="margin:6px 0;flex-wrap:nowrap"><input type="checkbox" name="pick" value="${esc(p.key)}" checked>
          <span><b>${esc(label(p))}</b> · ${fmt(p.length)} residues · mean pLDDT ${p.mean_plddt.toFixed(1)}</span></label>`).join("")}
        <div class="row" style="gap:18px;margin-top:10px;flex-wrap:wrap;align-items:center">
          <label class="small">Remove residues with pLDDT below <input type="number" id="min" min="0" max="100" step="5" value="0" style="width:70px"> (0 keeps all)</label>
          <label class="small"><input type="checkbox" id="dom"> Only confident domains</label></div>
        ${guide("export")}<div class="row" style="margin-top:12px"><button class="btn primary" id="go">Export</button></div><div id="files"></div></div>`;
    const files = async () => {
      const f = await E.call("files");
      $("#files", el).innerHTML = f.length ? `<table style="margin-top:14px"><thead><tr><th>File</th><th class="num">Size</th><th></th></tr></thead><tbody>${f.map(x =>
        `<tr><td class="mono small">${esc(x.name)}</td><td class="num small">${fmtSize(x.size)}</td><td class="num"><a class="btn small" href="${E.downloadUrl(x.name)}" download>Download</a></td></tr>`).join("")}</tbody></table>` : "";
    };
    $("#go", el).onclick = e => guarded(e.currentTarget, async () => {
      const keys = $$("input[name=pick]:checked", el).map(i => i.value);
      if (!keys.length) return toast("Choose at least one prediction.");
      await E.call("export", { keys, min_plddt: +$("#min", el).value || 0, domains_only: $("#dom", el).checked });
      await files(); toast("Structures saved to results/final.", true);
    });
    files();
  }

  E.registerViews("protein.structure", { report, overview, structure: structureView, compare, export: exportView });
})();
