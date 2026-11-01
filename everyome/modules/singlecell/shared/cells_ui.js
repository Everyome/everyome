/* Shared live-session views for single-cell modules: filter cells, cluster, markers, name clusters, compare and export.
   Generalised from SPLiTscape (Helen R Horkan PhD). A module's own ui.js calls Everyome.cells({ order }) and registers
   these views next to its first step; the engine side is everyome/modules/singlecell/cells.py. */
"use strict";
(() => {
  const E = window.Everyome, H = E.helpers;
  const { $, $$, esc, fmt, fmtSize, toast, guarded, followTask, logHist, stacked, dotplot, legendFor, EmbeddingPlot, guide } = H;
  const COL = () => H.COL(), PALETTE = () => H.PALETTE();
  const lede = t => `<p class="lede">${t}</p>`;

  // order: the session's steps, first to last, as the engine names them (state.step).
  // words: what one observation and one group are called (spatial modules say spot and region).
  const CELL = { unit: "cell", units: "cells", Units: "Cells", type: "cell type", types: "cell types", Type: "Cell type",
    qc: "Remove near-empty barcodes and likely doublets. Move the thresholds and watch how many cells each sample keeps.",
    qcNote: "${W.qcNote}" };
  E.cells = ({ order, words = {} }) => {
  const W = { ...CELL, ...words };
  const S = { an: null, emb: null };
  const refresh = async () => (S.an = await E.status());
  const reached = s => order.indexOf(S.an?.step) >= order.indexOf(s);
  const named = () => Object.values(S.an?.annotations || {}).filter(v => v.name).length;
  async function embedding() { if (!S.emb || S.emb.step !== S.an.step) S.emb = { ...(await E.call("embedding")), step: S.an.step }; return S.emb; }

  // ---------------------------------------------------------------- filter cells
  async function qc(el) {
    el.innerHTML = lede(W.qc) + `<div class="empty" id="loading">Loading QC data…</div>`;
    const d = await E.call("qc_data"), t = { ...d.thresholds }, c = COL();
    $("#loading", el).remove();
    el.insertAdjacentHTML("beforeend", `<div class="grid g-side"><div><div class="card"><div class="label">UMIs per ${W.unit}</div><div id="h1"></div></div>
        <div class="card" style="margin-top:18px"><div class="label">Genes per ${W.unit}</div><div id="h2"></div></div>
        ${d.mito_edges ? `<div class="card" style="margin-top:18px"><div class="label">Mitochondrial share of counts (%)</div><div id="h3"></div>${guide("mito")}</div>` : ""}
        <div class="card" style="margin-top:18px"><div class="label">Genes against UMIs (sample of ${W.units})</div><div id="sc"></div>${guide("filter_cells", { open: true })}</div></div>
      <div><div class="card"><div class="label">Thresholds</div>
        ${[["min_counts", "Minimum UMIs"], ["max_counts", "Maximum UMIs"], ["min_genes", "Minimum genes"], ["max_genes", "Maximum genes"], ...(d.mito_edges ? [["max_mito", "Maximum mitochondrial %"]] : [])].map(([k, l]) =>
          `<label class="field"><span>${l}</span><input type="number" min="0" name="${k}" value="${t[k]}"></label>`).join("")}
        <p class="small muted">${W.qcNote}${d.mito_edges ? " A high mitochondrial share marks damaged or dying cells." : ""}</p>
        <div id="kept"></div><div class="row" style="margin-top:12px"><button class="btn primary" id="apply">Apply filter</button></div><div id="qprog"></div></div></div></div>`);
    const draw = () => {
      $("#h1", el).innerHTML = logHist(d.umi_edges, Object.fromEntries(Object.entries(d.groups).map(([k, v]) => [k, v.umi])), { lo: t.min_counts, hi: t.max_counts, xlab: `UMIs per ${W.unit}` });
      $("#h2", el).innerHTML = logHist(d.gene_edges, Object.fromEntries(Object.entries(d.groups).map(([k, v]) => [k, v.gene])), { lo: t.min_genes, hi: t.max_genes, xlab: `Genes per ${W.unit}` });
      // Intent: a linear histogram per group, summed; cells right of the line are removed.
      if (d.mito_edges) $("#h3", el).innerHTML = H.histChart(d.mito_edges, d.mito_edges.slice(1).map((_, i) => Object.values(d.groups).reduce((n, g) => n + g.mito[i], 0)), { lo: 0, hi: t.max_mito, xlab: "Mitochondrial share (%)", digits: 0 });
      const s = d.scatter, w = 540, h = 300, L = 50, B = 30, lx = v => Math.log10(Math.max(v, 1));
      const xm = Math.max(...s.umi.map(lx)), ym = Math.max(...s.gene.map(lx)), X = v => L + lx(v) / xm * (w - L - 10), Y = v => h - B - lx(v) / ym * (h - B - 10);
      const keep = i => s.umi[i] >= t.min_counts && s.umi[i] < t.max_counts && s.gene[i] >= t.min_genes && s.gene[i] < t.max_genes && (!s.mito || s.mito[i] <= t.max_mito);
      $("#sc", el).innerHTML = `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="Genes against UMIs">${s.umi.map((u, i) =>
        `<circle cx="${X(u).toFixed(1)}" cy="${Y(s.gene[i]).toFixed(1)}" r="1.6" fill="${keep(i) ? c.golddk : c.ox}" opacity="${keep(i) ? .45 : .9}"/>`).join("")}
        <line x1="${L}" x2="${w}" y1="${h - B}" y2="${h - B}" stroke="${c.muted}"/><line x1="${L}" x2="${L}" y1="0" y2="${h - B}" stroke="${c.muted}"/>
        <text x="${w / 2}" y="${h - 6}" text-anchor="middle" class="ax">UMIs per ${W.unit} (log)</text><text x="14" y="${h / 2}" transform="rotate(-90 14 ${h / 2})" text-anchor="middle" class="ax">Genes per ${W.unit} (log)</text></svg>
        <div class="legend"><span><i style="background:${c.golddk}"></i>kept</span><span><i style="background:${c.ox}"></i>removed</span></div>`;
    };
    let tm;
    const preview = () => { clearTimeout(tm); tm = setTimeout(async () => {
      const r = await E.call("qc_preview", t);
      $("#kept", el).innerHTML = `<div class="metric"><span>${W.Units} kept</span><b>${fmt(r.kept)}</b></div><p class="small muted">of ${fmt(r.total)} (${(100 * r.kept / r.total).toFixed(1)}%)</p>
        <table class="small"><thead><tr><th>Sample</th><th class="num">Kept</th></tr></thead><tbody>${r.per_sample.map(x =>
          `<tr><td class="small">${esc(x.sample)}</td><td class="num">${(100 * x.kept / x.total).toFixed(0)}%</td></tr>`).join("")}</tbody></table>`; }, 200); };
    $$("input[type=number]", el).forEach(i => i.addEventListener("input", () => { t[i.name] = Number(i.value); draw(); preview(); }));
    $("#apply", el).onclick = e => guarded(e.currentTarget, async () => {
      await E.call("qc_apply", t); await followTask($("#qprog", el)); await refresh(); toast(`Filter applied: ${fmt(S.an.cells)} ${W.units} kept.`, true); H.go("step:cluster");
    });
    draw(); preview();
  }

  // ---------------------------------------------------------------- integrate and cluster
  async function cluster(el) {
    await refresh();
    const prev = S.an.cluster_params || {}, cols = S.an.obs_columns.filter(c => !S.an.hidden_columns.includes(c));
    const P = { n_top_genes: 2000, n_pcs: 30, batch_key: cols.includes("batch") ? "batch" : cols[0], harmony: true, n_neighbors: 15, resolution: 0.6, min_dist: 0.3, ...prev };
    el.innerHTML = lede(`Correct for batch, place ${W.units} on a map and group them into clusters. Change a setting and run again to compare.`) +
      `<div class="grid g-side"><div><div class="card"><div class="row" style="justify-content:space-between"><div class="label">UMAP</div>
          <div class="row"><label class="small">Colour by <select id="colby" style="width:auto"></select></label><input type="text" id="gq" placeholder="Gene or name…" style="width:180px" list="gl" aria-label="Colour by gene"><datalist id="gl"></datalist></div></div>
          <div class="plotwrap"><canvas class="umap" id="cv"></canvas><div class="tip" id="tip"></div></div><div id="leg"></div>${guide("clusters")}</div></div>
        <div><div class="card"><div class="label">Settings</div>
          ${[["n_top_genes", "Highly variable genes", 200, 5000, 100], ["n_pcs", "Principal components", 5, 50, 1], ["n_neighbors", "Neighbours", 5, 60, 1], ["resolution", "Resolution", 0.1, 4, 0.1], ["min_dist", "UMAP spacing", 0.05, 0.9, 0.05]]
            .map(([k, l, a, b, s]) => `<label class="field"><span>${l} <output class="mono" style="float:right" data-o="${k}">${P[k]}</output></span><input type="range" name="${k}" min="${a}" max="${b}" step="${s}" value="${P[k]}"></label>`).join("")}
          <label class="field"><span>Correct batches by</span><select name="batch_key">${cols.map(c => `<option ${c === P.batch_key ? "selected" : ""}>${esc(c)}</option>`).join("")}</select></label>
          <label class="row small"><input type="checkbox" name="harmony" ${P.harmony ? "checked" : ""}> Use Harmony batch correction</label>
          <div class="row" style="margin-top:14px"><button class="btn primary" id="run">${reached("clustered") ? "Run again" : "Run"}</button></div><div id="cprog"></div></div>
          <div class="card" style="margin-top:18px"><div class="label">Result</div><div id="metrics"><p class="small muted">Run clustering to see results.</p></div></div></div></div>`;
    $$("input[type=range]", el).forEach(i => i.addEventListener("input", () => $(`[data-o=${i.name}]`, el).textContent = i.value));
    const um = new EmbeddingPlot($("#cv", el), $("#tip", el));
    async function show() {
      if (!reached("clustered")) return;
      const s = await E.call("cluster_summary"), e = await embedding(); um.setXY(e.xy);
      $("#metrics", el).innerHTML = `<div class="metric"><span>Clusters</span><b>${s.clusters.length}</b></div>
        <div class="metric"><span>Batch mixing</span><b>${s.batch_mixing != null ? Math.round(100 * s.batch_mixing) + "%" : "–"}</b></div>
        <p class="small muted">Batch mixing near 100% means batches are interleaved. Check ${W.types} still separate when you colour by your batch column.</p>
        ${e.n_total > e.xy.length / 2 ? `<p class="small muted">Showing ${fmt(e.xy.length / 2)} of ${fmt(e.n_total)} ${W.units}.</p>` : ""}
        <div class="row" style="margin-top:10px"><button class="btn primary" data-go="step:markers">Explore markers →</button></div>`;
      const opts = ["cluster", ...S.an.obs_columns.filter(c => c !== "cluster")];
      $("#colby", el).innerHTML = opts.map(o => `<option>${esc(o)}</option>`).join(""); await colour("cluster");
    }
    async function colour(key) {
      const c = await E.call("colour", { key }); um.labels = null; um.setColour(c);
      if (key === "cluster") um.centroids(c.codes, c.categories);
      $("#leg", el).innerHTML = legendFor(c);
    }
    $("#colby", el).onchange = e => colour(e.target.value);
    let gt; $("#gq", el).addEventListener("input", e => { clearTimeout(gt); gt = setTimeout(async () => {
      const q = e.target.value.trim(); if (q.length < 2) return;
      const g = await E.call("genes", { q });
      $("#gl", el).innerHTML = g.map(x => `<option value="${esc(x.gene)}">${esc(x.name)}</option>`).join("");
      if (g.some(x => x.gene === q)) colour(q); }, 250); });
    $("#run", el).onclick = e => guarded(e.currentTarget, async () => {
      const b = {}; $$("input[type=range]", el).forEach(i => b[i.name] = Number(i.value)); b.batch_key = $("[name=batch_key]", el).value; b.harmony = $("[name=harmony]", el).checked;
      await E.call("cluster", b); await followTask($("#cprog", el)); await refresh(); S.emb = null; show();
    });
    show();
  }

  // ---------------------------------------------------------------- markers
  async function markers(el) {
    await refresh();
    const cl = S.an.clusters, P = PALETTE();
    el.innerHTML = lede("Pick a cluster to see the genes that set it apart. Click a gene to see where it is expressed.") +
      `<div class="card"><div class="label">Clusters</div><div class="chips" id="chips">${cl.map((c, i) => `<button class="chip" data-c="${c.id}" aria-pressed="false"><i style="background:${P[i % P.length]}"></i>${c.id} <span class="muted small">${fmt(c.cells)}</span></button>`).join("")}</div></div>
      <div class="grid g2" style="margin-top:18px"><div class="card"><div class="label" id="mt">Markers</div><div id="mk"><p class="small muted">Choose a cluster above.</p></div>${guide("markers")}</div>
        <div class="card"><div class="label" id="ut">UMAP</div><div class="plotwrap"><canvas class="umap" id="cv" style="height:440px"></canvas><div class="tip" id="tip"></div></div><div id="leg"></div></div></div>
      <h2>Dotplot</h2><div class="card"><p class="small muted">Top two markers of every cluster. Dot size is the share of ${W.units} expressing the gene; colour is mean expression, scaled per gene.</p>
        <button class="btn" id="dp">Draw dotplot</button><div id="dot" style="overflow:auto;margin-top:12px"></div>${guide("dotplot")}</div>`;
    const um = new EmbeddingPlot($("#cv", el), $("#tip", el)); um.setXY((await embedding()).xy);
    const colour = async key => { const c = await E.call("colour", { key }); um.labels = null; um.setColour(c); if (key === "cluster") um.centroids(c.codes, c.categories); $("#leg", el).innerHTML = legendFor(c); };
    await colour("cluster");
    async function pick(id) {
      $$("#chips .chip", el).forEach(b => b.setAttribute("aria-pressed", b.dataset.c === id));
      $("#mt", el).textContent = `Markers of cluster ${id}`; $("#mk", el).innerHTML = `<p class="small muted">Loading…</p>`;
      const m = await E.call("markers", { cluster: id });
      // Intent: the "Best match" column only when the module has gene names (SPLiT-seq's annotation table).
      const nm = m.some(g => g.name);
      $("#mk", el).innerHTML = m.length ? `<table><thead><tr><th>Gene</th>${nm ? "<th>Best match</th>" : ""}<th class="num">log FC</th><th class="num">In / out</th></tr></thead><tbody>
        ${m.map(g => `<tr class="click" tabindex="0" data-g="${esc(g.gene)}"><td class="mono small">${esc(g.gene)}</td>${nm ? `<td class="small">${esc(g.name)}</td>` : ""}<td class="num">${g.logfc}</td><td class="num small">${g.pct_in}% / ${g.pct_out}%</td></tr>`).join("")}</tbody></table>`
        : `<p class="small muted">No significant upregulated markers.</p>`;
    }
    $("#chips", el).onclick = e => { const b = e.target.closest("[data-c]"); if (b) pick(b.dataset.c); };
    $("#mk", el).addEventListener("click", e => { const r = e.target.closest("[data-g]"); if (r) { $$("tr.sel", el).forEach(x => x.classList.remove("sel")); r.classList.add("sel"); $("#ut", el).textContent = r.dataset.g; colour(r.dataset.g); } });
    $("#mk", el).addEventListener("keydown", e => { if (e.key === "Enter") e.target.click(); });
    um.onPick = i => { if (um.col?.kind === "cat" && um.labels) pick(um.col.categories[um.col.codes[i]]); };
    $("#dp", el).onclick = e => guarded(e.currentTarget, async () => {
      const genes = []; for (const c of cl.slice(0, 20)) { const m = await E.call("markers", { cluster: c.id }); m.slice(0, 2).forEach(g => genes.includes(g.gene) || genes.push(g.gene)); }
      $("#dot", el).innerHTML = dotplot(await E.call("dotplot", { genes }));
    });
    if (cl.length) pick(cl[0].id);
  }

  // ---------------------------------------------------------------- name clusters
  async function annotate(el) {
    await refresh();
    const cl = S.an.clusters, P = PALETTE(); let ann = { ...(S.an.annotations || {}) }, sel = cl[0]?.id;
    el.innerHTML = lede(`Give each cluster a ${W.type} name and a colour. Clusters with the same name are treated as one ${W.type}. Click a cluster on the map or in the list.`) +
      `<div class="grid g-side"><div class="card"><div class="row" style="justify-content:space-between"><div class="label">${W.Type}s</div><span class="small muted" id="prog"></span></div>
        <div class="plotwrap"><canvas class="umap" id="cv"></canvas><div class="tip" id="tip"></div></div><div id="leg"></div></div>
      <div><div class="card"><div class="label" id="et">Cluster</div><label class="field"><span>${W.Type} name</span><input type="text" id="nm" list="names"></label><datalist id="names"></datalist>
        <div class="field"><span>Colour</span><div class="swatches" id="sw">${P.map(c => `<button style="background:${c}" data-col="${c}" aria-label="Colour ${c}" aria-pressed="false"></button>`).join("")}</div></div>
        <div class="row"><button class="btn primary" id="save">Save</button><button class="btn" id="nextc">Next cluster →</button></div>
        <div class="label" style="margin-top:18px">Top markers</div><div id="hint" class="small"></div></div></div></div>
      <h2>All clusters</h2><div class="card"><table><thead><tr><th>Cluster</th><th class="num">Cells</th><th>Name</th><th></th></tr></thead><tbody id="tb"></tbody></table>
        <div class="row" style="margin-top:14px"><button class="btn primary" data-go="step:compare">Compare and export →</button></div></div>`;
    const um = new EmbeddingPlot($("#cv", el), $("#tip", el)); um.setXY((await embedding()).xy);
    const clusterCol = await E.call("colour", { key: "cluster" });
    let colour = P[0];
    async function redraw() {
      const c = await E.call("colour", { key: "annotation" }); um.setColour(c);
      // Label each named type once (at the centre of all its clusters); unnamed clusters by number.
      const lab = clusterCol.categories.map(k => ann[k]?.name || k), uniq = [...new Set(lab)];
      um.centroids(clusterCol.codes.map(k => uniq.indexOf(lab[k])), uniq);
      $("#leg", el).innerHTML = legendFor(c);
      $("#prog", el).textContent = `${cl.filter(k => ann[k.id]?.name).length} of ${cl.length} named`;
      $("#tb", el).innerHTML = cl.map(k => `<tr class="click ${k.id === sel ? "sel" : ""}" tabindex="0" data-c="${k.id}"><td>${k.id}</td><td class="num">${fmt(k.cells)}</td>
        <td>${ann[k.id]?.name ? `<span class="chip" style="cursor:inherit"><i style="background:${ann[k.id].color}"></i>${esc(ann[k.id].name)}</span>` : '<span class="muted small">unnamed</span>'}</td><td></td></tr>`).join("");
      $("#names", el).innerHTML = [...new Set(Object.values(ann).map(v => v.name).filter(Boolean))].map(n => `<option value="${esc(n)}">`).join("");
    }
    async function select(id) {
      sel = id; $("#et", el).textContent = `Cluster ${id}`; $("#nm", el).value = ann[id]?.name || "";
      colour = ann[id]?.color || P[cl.findIndex(k => k.id === id) % P.length]; markSw();
      $$("#tb tr", el).forEach(r => r.classList.toggle("sel", r.dataset.c === id));
      const m = await E.call("markers", { cluster: id });
      $("#hint", el).innerHTML = m.slice(0, 6).map(g => `<div>${esc(g.name && !g.name.startsWith("not in") ? g.name : g.gene)} <span class="muted">(${g.logfc})</span></div>`).join("") || `<span class="muted">No clear markers.</span>`;
      $("#nm", el).focus();
    }
    const markSw = () => $$("#sw button", el).forEach(b => b.setAttribute("aria-pressed", b.dataset.col === colour));
    $("#sw", el).onclick = e => { const b = e.target.closest("[data-col]"); if (b) { colour = b.dataset.col; markSw(); } };
    $("#nm", el).addEventListener("change", () => { const same = Object.values(ann).find(v => v.name === $("#nm", el).value.trim()); if (same) { colour = same.color; markSw(); } });
    const save = async () => { ann = await E.call("annotate", { cluster: sel, name: $("#nm", el).value, color: colour }); await redraw(); };
    $("#save", el).onclick = e => guarded(e.currentTarget, save);
    $("#nm", el).addEventListener("keydown", e => { if (e.key === "Enter") guarded(null, async () => { await save(); nextc(); }); });
    const nextc = () => { const i = cl.findIndex(k => k.id === sel); select(cl[(i + 1) % cl.length].id); };
    $("#nextc", el).onclick = nextc;
    $("#tb", el).addEventListener("click", e => { const r = e.target.closest("[data-c]"); if (r) select(r.dataset.c); });
    $("#tb", el).addEventListener("keydown", e => { if (e.key === "Enter") e.target.click(); });
    um.onPick = i => select(clusterCol.categories[clusterCol.codes[i]]);
    await redraw(); if (sel) select(sel);
  }

  // ---------------------------------------------------------------- compare and export
  async function compare(el) {
    await refresh();
    const cols = S.an.obs_columns.filter(c => !S.an.hidden_columns.includes(c));
    const def = cols.includes("condition") ? "condition" : cols[0];
    el.innerHTML = lede(`See how ${W.type} proportions differ between groups, then save everything to the run folder.`) +
      (named() ? "" : `<div class="notice warn">No clusters are named yet, so every ${W.unit} is "Unannotated". Name clusters first for a useful comparison.</div>`) +
      `<div class="card"><div class="row" style="justify-content:space-between"><div class="label">Composition</div><label class="small">Compare by <select id="grp" style="width:auto">${cols.map(c => `<option ${c === def ? "selected" : ""}>${esc(c)}</option>`).join("")}</select></label></div>
        <div id="comp"></div>${guide("composition")}</div>
      <h2>Export</h2><div class="card"><p class="small">Writes the annotated data, composition tables, a marker workbook and a UMAP figure to <code>${esc(E.state().run.dir)}/results</code>. You can also download them here.</p>
        <div class="row"><button class="btn primary" id="exp">Export results</button></div><div id="eprog"></div><div id="files"></div></div>`;
    async function comp() {
      const g = $("#grp", el).value, d = await E.call("composition", { group: g });
      const rows = d.groups.map((gr, j) => [`${gr} (n=${fmt(d.group_sizes[j])})`, d.types.map((_, i) => d.fractions[i][j])]);
      $("#comp", el).innerHTML = stacked(rows, d.types, d.colors, { w: 760, left: 190, title: "Composition" }) +
        `<table style="margin-top:16px"><thead><tr><th>${W.Type}</th>${d.groups.map(x => `<th class="num">${esc(x)}</th>`).join("")}</tr></thead><tbody>
        ${d.types.map((t, i) => `<tr><td><span class="chip" style="cursor:inherit"><i style="background:${d.colors[i]}"></i>${esc(t)}</span></td>${d.groups.map((_, j) => `<td class="num">${(100 * d.fractions[i][j]).toFixed(1)}% <span class="muted small">(${fmt(d.counts[i][j])})</span></td>`).join("")}</tr>`).join("")}</tbody></table>
        ${d.group_sizes.some(n => n < 50) ? `<div class="notice warn" style="margin-top:12px">At least one group has fewer than 50 ${W.units}; treat its proportions as anecdotal.</div>` : ""}
        <p class="small muted" style="margin-top:10px">These are descriptive proportions. Testing a difference needs biological replicates and a compositional method.</p>`;
    }
    async function files() {
      const f = await E.call("files");
      $("#files", el).innerHTML = f.length ? `<table style="margin-top:14px"><thead><tr><th>File</th><th class="num">Size</th><th></th></tr></thead><tbody>${f.map(x =>
        `<tr><td class="mono small">${esc(x.name)}</td><td class="num small">${fmtSize(x.size)}</td><td class="num"><a class="btn small" href="${E.downloadUrl(x.name)}" download>Download</a></td></tr>`).join("")}</tbody></table>` : "";
    }
    $("#grp", el).onchange = comp;
    $("#exp", el).onclick = e => guarded(e.currentTarget, async () => {
      await E.call("export", { group: $("#grp", el).value }); await followTask($("#eprog", el)); await files(); toast("Results exported.", true);
    });
    comp(); files();
  }

  return { S, refresh, reached, views: { qc, cluster, markers, annotate, compare } };
  };
})();
