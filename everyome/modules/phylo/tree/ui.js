/* Views for alignment and tree building: what the stages made (Run page), then the live session: check the alignment,
   read the model and support, explore the tree (root, collapse, colour by a table), export. Engine: engine.py. */
"use strict";
(() => {
  const E = window.Everyome, H = E.helpers;
  const { $, $$, esc, fmt, fmtSize, toast, guarded, histChart, guide } = H;
  const COL = () => H.COL(), PALETTE = () => H.PALETTE();
  const lede = t => `<p class="lede">${t}</p>`;
  const tipName = s => s.replace(/_/g, " ");
  // Intent: read the results once per run (the engine notes them for the record); later views reuse them.
  async function ensure() {
    const st = await E.status();
    return st.loaded || await E.call("load");
  }

  // ---------------------------------------------------------------- Run page
  async function report(el, q) {
    el.innerHTML = `<h2>What the stages made</h2><div class="card"><div class="metrics">
        <div class="m"><span class="k">Sequences</span><span class="v">${fmt(q.sequences)}</span></div>
        <div class="m"><span class="k">Alignment columns kept</span><span class="v">${q.kept != null ? `${fmt(q.kept)} of ${fmt(q.columns)}` : "–"}</span></div>
        <div class="m"><span class="k">Model</span><span class="v">${esc(q.model || "–")}</span><span class="n">${q.selected_by ? `chosen by ModelFinder (${esc(q.selected_by)})` : ""}</span></div>
        <div class="m"><span class="k">Tree</span><span class="v">${q.tree ? "built" : "missing"}</span></div></div>
      ${q.report ? `<p class="small" style="margin-top:10px"><a class="btn small" href="/api/run/file?path=${encodeURIComponent(q.report)}" target="_blank" rel="noopener">Open IQ-TREE's report</a></p>` : ""}
      ${q.tree ? `<p class="small muted">Check the alignment and explore the tree in the live session.</p>` : `<div class="notice warn">No tree was found. Check the log of stage 03.</div>`}
      ${E.state().demo ? `<p class="small muted">On the demo cluster, quick stand-ins replace MAFFT, trimAl and IQ-TREE.</p>` : ""}${guide("run_report")}</div>`;
  }

  // ---------------------------------------------------------------- alignment
  const BASE = () => { const c = COL(); return { A: c.gold, C: c.ox, G: c.plum, T: c.golddk, U: c.golddk }; };
  // Amino acids by kind: water-avoiding, polar, positive, negative, and the special glycine and proline.
  const AA = () => { const c = COL(), p = PALETTE(); return Object.fromEntries([..."AVLIMFWC"].map(a => [a, c.gold]).concat([..."STNQYH"].map(a => [a, p[7] || c.golddk]),
    [..."KR"].map(a => [a, c.ox]), [..."DE"].map(a => [a, c.plum]), [..."GP"].map(a => [a, c.muted]))); };

  function alignmentSvg(a, type) {
    const cw = 7, rh = 13, L = 190, c = COL(), col = type === "protein" ? AA() : BASE();
    const w = L + a.width * cw + 4, h = 18 + a.rows.length * rh + 4;
    let s = `<svg class="chart" viewBox="0 0 ${w} ${h}" style="min-width:${Math.min(w, 900)}px" role="img" aria-label="Part of the alignment">`;
    a.kept.forEach((k, j) => { if (!k) s += `<rect x="${L + j * cw}" y="14" width="${cw}" height="${h - 14}" fill="${c.rule}" opacity=".55"/>`; });
    for (let j = 0; j < a.width; j += 10) s += `<text x="${L + j * cw}" y="10" class="ax" style="font-size:9px">${a.start + j + 1}</text>`;
    a.rows.forEach((r, i) => {
      const y = 18 + i * rh;
      s += `<text x="${L - 6}" y="${y + 10}" text-anchor="end" class="ax" style="font-size:10px">${esc(tipName(r.name).slice(0, 28))}</text>`;
      [...r.seq].forEach((ch, j) => {
        const f = col[ch.toUpperCase()];
        if (ch !== "-" && ch !== ".") s += `<rect x="${L + j * cw}" y="${y}" width="${cw - 1}" height="${rh - 2}" fill="${f || c.muted}" opacity="${a.kept[j] ? 0.9 : 0.35}"><title>${esc(r.name)} · column ${a.start + j + 1}: ${esc(ch)}</title></rect>`;
      });
    });
    return s + "</svg>";
  }
  function overview(a) {
    const w = 760, n = a.kept_all.length, c = COL(), step = Math.max(1, Math.ceil(n / w));
    let s = `<svg class="chart" id="ov" viewBox="0 0 ${w} 26" style="cursor:pointer" role="img" aria-label="Columns kept and removed along the alignment">`;
    for (let x = 0; x * step < n; x++) {
      const part = a.kept_all.slice(x * step, (x + 1) * step), kept = part.split("").filter(v => v === "1").length / part.length;
      s += `<rect x="${x * w / Math.ceil(n / step)}" y="4" width="${w / Math.ceil(n / step) + .5}" height="14" fill="${kept > .5 ? c.golddk : c.rule}"/>`;
    }
    const X = v => v / n * w;
    return s + `<rect x="${X(a.start)}" y="1" width="${Math.max(2, X(a.width))}" height="20" fill="none" stroke="${c.ox}" stroke-width="2"/></svg>`;
  }

  async function alignment(el) {
    const info = await ensure(), q = await E.call("summary"), flagged = q.rows.filter(r => r.flag);
    el.innerHTML = lede("The aligned sequences, and the columns trimming removed. A good alignment lines up related positions; sequences that are mostly gaps or very different from the rest can pull a tree out of shape.") +
      `<div class="card"><div class="metrics">
          <div class="m"><span class="k">Sequences</span><span class="v">${fmt(q.sequences)}</span><span class="n">${q.type === "protein" ? "protein" : "DNA"}</span></div>
          <div class="m"><span class="k">Alignment columns</span><span class="v">${fmt(q.columns)}</span></div>
          <div class="m"><span class="k">Kept after trimming</span><span class="v">${fmt(q.kept)}</span><span class="n">${q.columns ? Math.round(100 * q.kept / q.columns) : 0}% (${fmt(q.removed)} removed)</span></div>
          <div class="m ${flagged.length ? "warn" : ""}"><span class="k">Sequences to look at</span><span class="v">${flagged.length}</span><span class="n">${flagged.length ? "see the table" : "none flagged"}</span></div></div></div>
      <div class="card" style="margin-top:18px"><div class="label">Alignment</div>
        <p class="small muted">Each row is a sequence; pale columns were removed by trimming. Click the strip to move along the alignment.</p>
        <div id="ovw"></div><div class="row small" style="gap:10px;margin:6px 0"><button class="btn small" id="prev">← Back</button><button class="btn small" id="next">Forward →</button><span id="where" class="muted"></span></div>
        <div id="aln" style="overflow-x:auto"></div>${guide("alignment")}${guide("trimming", { title: "About trimming" })}</div>
      <div class="card" style="margin-top:18px;overflow:auto"><div class="label">Sequences</div><table class="small"><thead><tr><th>Name</th><th class="num">Length</th><th class="num">Gaps (aligned)</th>
        <th class="num">Gaps (trimmed)</th><th class="num">Same as consensus</th><th>Look at</th></tr></thead><tbody>
        ${q.rows.map(r => `<tr><td title="${esc(r.original)}">${esc(tipName(r.name))}</td><td class="num">${fmt(r.length)}</td><td class="num">${r.gaps}%</td><td class="num">${r.gaps_trimmed}%</td>
          <td class="num">${r.identity == null ? "–" : r.identity + "%"}</td><td class="${r.flag ? "warn" : "muted"}">${esc(r.flag || "–")}</td></tr>`).join("")}</tbody></table></div>
      <div class="row" style="margin-top:18px"><button class="btn primary" data-go="step:model">Continue to model and support →</button></div>`;
    let start = 0;
    const W = 110;
    const draw = async () => {
      const a = await E.call("alignment", { start, width: W, rows: 200 });
      $("#ovw", el).innerHTML = overview(a);
      $("#aln", el).innerHTML = alignmentSvg(a, q.type);
      $("#where", el).textContent = `columns ${fmt(a.start + 1)}–${fmt(Math.min(a.total, a.start + a.width))} of ${fmt(a.total)}`;
      $("#ov", el).onclick = e => { const r = e.currentTarget.getBoundingClientRect(); start = Math.max(0, Math.round((e.clientX - r.left) / r.width * a.total - W / 2)); draw(); };
      $("#prev", el).disabled = start === 0; $("#next", el).disabled = start + W >= a.total;
    };
    $("#prev", el).onclick = () => { start = Math.max(0, start - W); draw(); };
    $("#next", el).onclick = () => { start += W; draw(); };
    draw();
    return info;
  }

  // ---------------------------------------------------------------- model and support
  async function model(el) {
    await ensure();
    const q = await E.call("models"), best = q.best_model || q.model;
    const hist = key => { const v = q.support.map(s => s[key]).filter(x => x != null); if (!v.length) return "";
      const edges = Array.from({ length: 21 }, (_, i) => i * 5), counts = edges.slice(0, -1).map((e, i) => v.filter(x => x >= e && (x < edges[i + 1] || (i === 19 && x <= 100))).length);
      return histChart(edges, counts, { w: 360, h: 170, xlab: "%", digits: 0 }); };
    const both = q.support.some(s => "ufboot" in s), strong = q.support.filter(s => both ? s.alrt >= 80 && s.ufboot >= 95 : (s.support ?? 0) >= 70).length;
    el.innerHTML = lede("Which model of evolution the tree was built with, and how strongly the data support each branch.") +
      (q.stand_in || q.demo ? `<div class="notice">On the demo cluster a quick neighbour-joining tree stands in for IQ-TREE, and its model table is illustrative.</div>` : "") +
      `<div class="card"><div class="label">Model</div>
        <div class="metrics"><div class="m"><span class="k">Model used</span><span class="v">${esc(best || "–")}</span><span class="n">${q.best_model ? `best by ${esc(q.criterion)} of ${q.models.length} shown` : "set in the settings"}</span></div>
          <div class="m"><span class="k">Sites</span><span class="v">${q.sites ? fmt(q.sites) : "–"}</span><span class="n">${q.informative != null ? `${fmt(q.informative)} informative` : ""}</span></div>
          <div class="m"><span class="k">Log-likelihood</span><span class="v">${q.log_likelihood != null ? q.log_likelihood.toFixed(1) : "–"}</span></div></div>
        ${q.models.length ? `<table class="small" style="margin-top:10px"><thead><tr><th>Model</th><th class="num">Log-likelihood</th><th class="num">BIC</th><th class="num">BIC weight</th></tr></thead><tbody>
          ${q.models.slice(0, 10).map(m => `<tr ${m.model === best ? 'style="font-weight:600"' : ""}><td class="mono">${esc(m.model)}</td><td class="num">${m.logl.toFixed(1)}</td><td class="num">${m.bic.toFixed(1)}</td><td class="num">${m.w_bic.toFixed(3)}</td></tr>`).join("")}</tbody></table>` : ""}
        ${guide("model")}</div>
      <div class="card" style="margin-top:18px"><div class="label">Branch support</div>
        <p class="small">${fmt(strong)} of ${fmt(q.support.length)} inner branches are well supported${both ? " (SH-aLRT ≥ 80% and UFBoot ≥ 95%)" : ""}.</p>
        ${both ? `<div class="grid g2"><div><div class="small muted">UFBoot</div>${hist("ufboot")}</div><div><div class="small muted">SH-aLRT</div>${hist("alrt")}</div></div>` : hist("support")}
        ${q.support.length ? "" : `<p class="small muted">No support values: bootstrap and SH-aLRT were both turned off.</p>`}${guide("support")}</div>
      <div class="row" style="margin-top:18px"><button class="btn primary" data-go="step:tree">Explore the tree →</button></div>`;
  }

  // ---------------------------------------------------------------- the tree
  function treeSvg(d, { mark = "", width = 820 } = {}) {
    const c = COL(), P = PALETTE(), rowh = 17, top = 14, nodes = d.nodes, byi = Object.fromEntries(nodes.map(n => [n.i, n]));
    const labels = nodes.filter(n => n.tip || n.collapsed).map(n => n.tip ? tipName(n.tip) : n.label);
    // Intent: drawn at its real size (names stay readable); wide trees scroll sideways instead of shrinking.
    const lw = 26 + 6.8 * Math.max(10, ...labels.map(s => s.length)), W = Math.max(width, lw + 360), span = d.width || 1;
    const X = v => 16 + v / span * (W - 30 - lw), Y = v => top + v * rowh, h = top + d.rows * rowh + 34;
    const values = d.groups.map(g => g.value), colour = v => v && values.includes(v) ? P[values.indexOf(v) % P.length] : c.ink;
    let s = `<svg viewBox="0 0 ${W} ${h}" width="${W}" height="${h}" role="img" aria-label="Phylogenetic tree" style="max-width:none;display:block">`;
    for (const n of nodes) {
      if (n.parent >= 0) {
        const p = byi[n.parent];
        s += `<path d="M${X(p.x)},${Y(n.y)}H${X(n.x)}" stroke="${c.ink}" fill="none" stroke-width="1.3"/>`;
        // Intent: a wide invisible line over each branch makes it easy to click.
        s += `<path class="hit" data-i="${n.i}" d="M${X(p.x)},${Y(n.y)}H${Math.max(X(n.x), X(p.x) + 6)}" stroke="transparent" stroke-width="10" fill="none" style="cursor:pointer"><title>${n.tip ? esc(n.tip) : `${n.collapsed || ""} group`}</title></path>`;
      }
      if (n.kids) { const ys = n.kids.map(k => byi[k].y); s += `<path d="M${X(n.x)},${Y(Math.min(...ys))}V${Y(Math.max(...ys))}" stroke="${c.ink}" fill="none" stroke-width="1.3"/>`; }
      if (n.tip) {
        const hit = mark && n.tip.toLowerCase().includes(mark.toLowerCase());
        // A coloured square before the name shows its group; the name stays in ink so every colour reads.
        if (n.value) s += `<rect x="${X(n.x) + 5}" y="${Y(n.y) - 4.5}" width="9" height="9" fill="${colour(n.value)}"><title>${esc(n.value)}</title></rect>`;
        s += `<text x="${X(n.x) + (n.value ? 19 : 5)}" y="${Y(n.y) + 4}" style="font-size:12px;${hit ? "font-weight:700;text-decoration:underline" : ""}" fill="${hit ? c.ox : c.ink}">${esc(tipName(n.tip))}</text>`;
      } else if (n.collapsed) {
        const x0 = X(n.x), x1 = Math.max(X(n.far), x0 + 14), y0 = Y(n.y), f = colour(n.value);
        s += `<path class="hit" data-i="${n.i}" d="M${x0},${y0}L${x1},${y0 - 8}L${x1},${y0 + 8}Z" fill="${f}" fill-opacity=".3" stroke="${f}" style="cursor:pointer"><title>${esc(n.first)} … ${esc(n.last)}</title></path>`;
        s += `<text x="${x1 + 5}" y="${y0 + 4}" style="font-size:12px;font-style:italic" fill="${c.ink}">${esc(n.label)}</text>`;
      }
      if (n.support && d.view.support === "values") {
        const t = "ufboot" in n.support ? `${Math.round(n.support.alrt)}/${Math.round(n.support.ufboot)}` : `${Math.round(n.support.support)}`;
        s += `<text x="${X(n.x) - 3}" y="${Y(n.y) - 3}" text-anchor="end" style="font-size:9px" fill="${n.strong ? c.ink : c.muted}">${t}</text>`;
      } else if (n.strong && d.view.support === "strong") s += `<circle cx="${X(n.x)}" cy="${Y(n.y)}" r="3.2" fill="${c.ox}"><title>Well supported</title></circle>`;
    }
    if (d.lengths) {
      const bar = 10 ** Math.round(Math.log10(span / 5)), yb = Y(d.rows) + 16;
      s += `<path d="M${X(0)},${yb}H${X(bar)}" stroke="${c.ink}" stroke-width="1.5"/><text x="${X(bar) + 6}" y="${yb + 4}" style="font-size:11px" fill="${c.muted}">${bar} substitutions per site</text>`;
    }
    return s + "</svg>";
  }

  async function tree(el) {
    await ensure();
    let d = await E.call("tree"), mode = "collapse", mark = "";
    const v = () => d.view;
    el.innerHTML = lede("The tree, drawn from its root. Click a branch to collapse the group above it (or open it again), or switch to rooting and click the branch to root on. Colour the names by a column of your table to see whether a group sits together.") +
      `<div class="card"><div class="row" style="flex-wrap:wrap;gap:10px;align-items:center">
          <span class="small">Clicking a branch <select id="mode" style="width:auto"><option value="collapse">collapses or opens it</option><option value="root">roots the tree on it</option></select></span>
          <span class="small">Root <button class="btn small" id="mid">Midpoint</button> <button class="btn small" id="built">As built</button></span>
          <span class="small"><input type="text" id="out" placeholder="Outgroup names, comma-separated" style="width:220px" aria-label="Outgroup"> <button class="btn small" id="og">Root on outgroup</button></span></div>
        <div class="row" style="flex-wrap:wrap;gap:14px;margin-top:8px;align-items:center">
          <label class="small"><input type="checkbox" id="lad"> Ladderize</label><label class="small"><input type="checkbox" id="len"> Branch lengths</label>
          <label class="small">Support <select id="sup" style="width:auto"><option value="strong">dots on well-supported branches</option><option value="values">numbers</option><option value="none">hidden</option></select></label>
          <label class="small">Colour by <select id="col" style="width:auto"></select></label>
          <input type="text" id="find" placeholder="Find a name…" style="width:150px" aria-label="Find a sequence"><button class="btn small" id="all">Open all groups</button></div>
        <div id="rootnote" class="small muted" style="margin-top:8px"></div>
        <div id="tv" style="margin-top:10px;overflow-x:auto"></div>${guide("rooting")}</div>
      <div class="card" style="margin-top:18px"><div class="label">Groups</div><div id="groups"></div>${guide("groups")}</div>
      <div class="row" style="margin-top:18px"><button class="btn primary" data-go="step:export">Export the tree →</button></div>`;
    const sync = () => {
      $("#lad", el).checked = v().ladderize; $("#len", el).checked = v().lengths; $("#sup", el).value = v().support;
      $("#col", el).innerHTML = `<option value="">nothing</option>` + d.columns.map(c => `<option ${c === d.colour_by ? "selected" : ""}>${esc(c)}</option>`).join("");
      const r = v().root;
      $("#rootnote", el).textContent = r.how === "outgroup" ? `Rooted on ${r.tips.map(tipName).join(", ")}.` : r.how === "midpoint" ? "Rooted at the midpoint (halfway along the longest path between two tips)." : "Shown as IQ-TREE wrote it: the tree is unrooted, so the root drawn here means nothing.";
      $("#tv", el).innerHTML = treeSvg(d, { mark, width: $("#tv", el).clientWidth - 4 });
      const P = PALETTE();
      $("#groups", el).innerHTML = d.colour_by ? `<table class="small"><thead><tr><th>${esc(d.colour_by)}</th><th class="num">Sequences</th><th>One group on this tree?</th><th class="num">Support for the group</th></tr></thead><tbody>
        ${d.groups.map((g, i) => { const s = g.support; return `<tr><td><i style="display:inline-block;width:10px;height:10px;background:${P[i % P.length]};margin-right:6px"></i>${esc(g.value)}</td><td class="num">${g.n}</td>
          <td>${g.n === 1 ? "–" : g.clade ? "yes" : "<b>no</b>"}</td><td class="num">${s ? ("ufboot" in s ? `${Math.round(s.alrt)}/${Math.round(s.ufboot)}` : Math.round(s.support)) : "–"}</td></tr>`; }).join("")}</tbody></table>`
        : `<p class="small muted">Choose a column to colour by${d.columns.length ? "" : " (add a table about the sequences in the run's inputs to have some)"}.</p>`;
      $$(".hit", el).forEach(p => p.onclick = () => click(+p.dataset.i));
    };
    const act = async (method, args) => { try { d = await E.call(method, args); sync(); } catch (e) { toast(e.message || String(e)); } };
    const click = i => {
      const n = d.nodes.find(x => x.i === i);
      if (mode === "root") return act("reroot", { node: i });
      if (n.tip) return toast("A single sequence cannot be collapsed. Switch to rooting to root on it.");
      return act(n.collapsed ? "expand" : "collapse", { node: i });
    };
    $("#mode", el).onchange = e => { mode = e.target.value; };
    $("#mid", el).onclick = () => act("reroot", { how: "midpoint" });
    $("#built", el).onclick = () => act("reroot", { how: "as_built" });
    $("#og", el).onclick = () => act("reroot", { how: "outgroup", tips: $("#out", el).value.split(",").map(x => x.trim().replace(/\s+/g, "_")).filter(Boolean) });
    $("#lad", el).onchange = e => act("view", { ladderize: e.target.checked });
    $("#len", el).onchange = e => act("view", { lengths: e.target.checked });
    $("#sup", el).onchange = e => act("view", { support: e.target.value });
    $("#col", el).onchange = e => act("view", { colour_by: e.target.value });
    $("#all", el).onclick = () => act("expand", { all: true });
    let ft; $("#find", el).oninput = e => { clearTimeout(ft); ft = setTimeout(() => { mark = e.target.value.trim().replace(/\s+/g, "_"); sync(); }, 200); };
    if (v().root.how === "outgroup") $("#out", el).value = v().root.tips.map(tipName).join(", ");
    sync();
  }

  // ---------------------------------------------------------------- export
  async function exportView(el) {
    await ensure();
    el.innerHTML = lede("Save the tree as you have drawn it: rooted, with groups collapsed and names coloured. Everyome writes the files to <code>results/final/</code> and notes the root and groups in the run record.") +
      `<div class="card"><ul class="small"><li><b>tree_rooted.nwk</b>: the rooted tree with support values, for FigTree, iTOL, R (ape, ggtree) or Python (ete, Bio.Phylo).</li>
        <li><b>tree_figure.svg</b>: the drawing, for Illustrator, Inkscape or a slide.</li><li><b>tips.tsv</b>: each sequence's name, original header and your table's columns.</li>
        <li><b>groups.tsv</b>: whether each group forms one branch, with its support (when you colour by a column).</li></ul>
        ${guide("export")}<div class="row" style="margin-top:12px"><button class="btn primary" id="go">Export</button></div><div id="files"></div></div>`;
    const files = async () => {
      const f = await E.call("files");
      $("#files", el).innerHTML = f.length ? `<table style="margin-top:14px"><thead><tr><th>File</th><th class="num">Size</th><th></th></tr></thead><tbody>${f.map(x =>
        `<tr><td class="mono small">${esc(x.name)}</td><td class="num small">${fmtSize(x.size)}</td><td class="num"><a class="btn small" href="${E.downloadUrl(x.name)}" download>Download</a></td></tr>`).join("")}</tbody></table>` : "";
    };
    $("#go", el).onclick = e => guarded(e.currentTarget, async () => { await E.call("export"); await files(); toast("Tree saved to results/final.", true); });
    files();
  }

  E.registerViews("phylo.tree", { report, alignment, model, tree, export: exportView });
})();
