/* Views for the SPLiT-seq (SPLiTscape) module, ported from the SPLiTscape app by Helen R Horkan PhD.
   report: read QC after the cluster stages; then the six live-session steps (merge … compare).
   Uses only Everyome's shared helpers, so every chart follows the active theme. */
"use strict";
(() => {
  const E = window.Everyome, H = E.helpers;
  const { $, $$, esc, fmt, fmtSize, toast, guarded, followTask, barChart, logHist, logLine, stacked, dotplot, legendFor, EmbeddingPlot, guide } = H;
  const COL = () => H.COL(), PALETTE = () => H.PALETTE();
  const ORDER = ["merged", "labelled", "filtered", "clustered", "exported"];
  const S = { an: null, emb: null };
  const refresh = async () => (S.an = await E.status());
  const reached = s => ORDER.indexOf(S.an?.step) >= ORDER.indexOf(s);
  const named = () => Object.values(S.an?.annotations || {}).filter(v => v.name).length;
  const lede = t => `<p class="lede">${t}</p>`;
  async function embedding() { if (!S.emb || S.emb.step !== S.an.step) S.emb = { ...(await E.call("embedding")), step: S.an.step }; return S.emb; }

  // ---------------------------------------------------------------- read QC (Run page, after stage 08)
  async function report(el, q) {
    const c = COL(), reg = q.regions ? [...new Set(q.regions.map(r => r.sublib))] : [];
    const cats = q.regions ? [...new Set(q.regions.filter(r => r.locus_function !== "TOTAL").map(r => r.locus_function))] : [];
    const regCols = [c.golddk, c.gold, c.goldlt, c.ox, c.plum, c.rule, c.muted];
    el.innerHTML = `<h2>Quality checks</h2><div class="notice">Review these before starting the live session.</div>
      <div class="grid g2">
      <div class="card"><div class="label">Read pairs per run</div>${q.reads ? barChart(q.reads.map(r => [`${r.sublib} · ${r.run}`, r.reads]), { label: v => (v / 1e6).toFixed(1) + " M" }) : "—"}
        <p class="small muted">Runs of the same sublibrary should scale with sequencing depth.</p>${guide("read_pairs")}</div>
      <div class="card"><div class="label">Where reads land</div>${q.regions ? stacked(reg.map(s => [s, cats.map(k => +(q.regions.find(r => r.sublib === s && r.locus_function === k)?.fraction || 0))]), cats, regCols) : "—"}
        <p class="small muted">Coding plus UTR is the usable mRNA signal; sublibraries should look alike.</p>${guide("read_regions")}</div>
      <div class="card"><div class="label">Cells and saturation</div>${q.dge ? `<table><thead><tr><th>Sublibrary</th><th class="num">Cells</th><th class="num">UMIs</th><th class="num">Reads per UMI</th></tr></thead><tbody>
        ${q.dge.map(r => `<tr><td>${esc(r.sublib)}</td><td class="num">${fmt(r.cells)}</td><td class="num">${fmt(r.umis)}</td><td class="num">${r.reads_per_umi}</td></tr>`).join("")}</tbody></table>` : "—"}
        <p class="small muted" style="margin-top:8px">Reads per UMI above about 10 means more sequencing would add few new molecules.</p>${guide("saturation")}</div>
      <div class="card"><div class="label">Knee plot</div>${q.knee ? logLine(q.knee, { xlab: "Barcode rank", ylab: "Reads per barcode" }) : "—"}
        <p class="small muted">Real cells form the plateau on the left; the drop marks where background begins.</p>${guide("knee")}</div></div>`;
  }

  // ---------------------------------------------------------------- 09–10 merge and label
  async function merge(el) {
    await refresh();
    const atlas = E.state().run.values.atlas_dir, withAtlas = S.an.merged ? S.an.merged.with_atlas !== false : true;
    el.innerHTML = lede("Combine your sublibraries, and if you like merge in an existing atlas or dataset, then say what each library is, so every cell carries its batch and condition.") +
      `<h2>1 · Combine your data</h2><div class="card"><div class="row"><label class="field" style="margin:0;flex:1;max-width:280px"><span>Name for your experiment</span><input type="text" id="expname" value="${esc(S.an.experiment || "expt")}"><small>Letters and digits only; it becomes part of every cell's name.</small></label>
        <button class="btn primary" id="merge">${reached("merged") ? "Combine again" : "Combine"}</button></div>
        ${atlas ? `<label class="row small" style="margin-top:12px"><input type="checkbox" id="withatlas" ${withAtlas ? "checked" : ""}> Also merge in <span class="mono">${esc(atlas)}</span></label>
          <p class="small muted">Optional. Leave it unticked to analyse your sublibraries on their own.</p>`
          : `<p class="small muted" style="margin-top:12px">No atlas or other dataset was given, so your sublibraries are analysed on their own. That is all you need to build a first atlas.</p>`}
        <div id="mprog"></div><div id="msum"></div>${guide("combine")}</div>
      <h2>2 · Describe each library</h2><div id="labels"></div>`;
    const showSum = () => { const m = S.an.merged || (S.an.cells ? { cells: S.an.cells, genes: S.an.genes } : null); if (reached("merged") && m)
      $("#msum", el).innerHTML = `<p class="small" style="margin-top:12px">Combined: <b>${fmt(m.cells)}</b> cells × <b>${fmt(m.genes)}</b> genes${m.atlas_cells ? ` (${fmt(m.experiment_cells)} yours, ${fmt(m.atlas_cells)} merged in)` : " from your sublibraries"}.</p>`; };
    showSum();
    $("#merge", el).onclick = e => guarded(e.currentTarget, async () => {
      await E.call("merge", { experiment: $("#expname", el).value.trim() || "expt", include_atlas: !!$("#withatlas", el)?.checked });
      await followTask($("#mprog", el)); await refresh(); showSum(); labels();
    });
    async function labels() {
      if (!reached("merged")) { $("#labels", el).innerHTML = `<div class="empty">Combine your data first.</div>`; return; }
      const libs = await E.call("libraries"), st = E.state(), demo = st.demo, prev = S.an.library_table || null;
      let cols = S.an.label_columns || ["batch", "condition"];
      const sheets = { ...(S.an.sheets || {}) };
      if (demo && !sheets.condition) sheets.condition = `${st.conn.data_root}/singlecell.splitseq/sheets/round1_condition.xlsx`;
      const def = (l, c) => prev?.[l.library]?.[c] ?? (c === "batch" ? (l.experiment === "atlas" ? "atlas" : l.experiment) : c === "condition" ? (l.experiment === "atlas" ? "control" : demo ? "from_barcodes" : "") : "");
      const table = Object.fromEntries(libs.map(l => [l.library, Object.fromEntries(cols.map(c => [c, def(l, c)]))]));
      function draw() {
        const usesSheet = c => Object.values(table).some(r => r[c] === "from_barcodes");
        $("#labels", el).innerHTML = `<div class="card"><p class="small">Type a value for each library. Use <code>from_barcodes</code> when samples share a sublibrary and are told apart by their round-1 well, then give that column a barcode sheet.</p>
          <table><thead><tr><th>Library</th><th>Source</th><th class="num">Cells</th>${cols.map(c => `<th>${esc(c)}</th>`).join("")}</tr></thead><tbody>
          ${libs.map(l => `<tr><td class="mono">${esc(l.library)}</td><td class="small">${esc(l.experiment)}</td><td class="num">${fmt(l.cells)}</td>
            ${cols.map(c => `<td><input type="text" list="vals-${esc(c)}" data-l="${esc(l.library)}" data-c="${esc(c)}" value="${esc(table[l.library][c])}" aria-label="${esc(c)} for ${esc(l.library)}"></td>`).join("")}</tr>`).join("")}</tbody></table>
          ${cols.map(c => `<datalist id="vals-${esc(c)}"><option value="from_barcodes">${[...new Set(Object.values(table).map(r => r[c]).filter(Boolean))].map(v => `<option value="${esc(v)}">`).join("")}</datalist>`).join("")}
          <div class="row" style="margin-top:12px"><input type="text" id="newcol" placeholder="New column, e.g. tissue" style="max-width:240px" aria-label="New column name"><button class="btn small" id="addcol">Add column</button></div>
          ${cols.filter(usesSheet).map(c => `<div class="field" style="margin-top:16px"><span>Barcode sheet for <b>${esc(c)}</b></span><div class="row">
            <input type="text" class="mono" style="flex:1" data-sheet="${esc(c)}" value="${esc(sheets[c] || "")}" placeholder="Upload an Excel sheet: well barcode, value" aria-label="Barcode sheet for ${esc(c)}">
            <label class="btn small">Upload<input type="file" accept=".xlsx,.xls" data-up="${esc(c)}" hidden></label></div></div>`).join("")}
          <div class="row" style="margin-top:16px"><button class="btn primary" id="apply">Apply labels</button></div><div id="lprog"></div><div id="ucounts"></div></div>`;
        $$("[data-l]", el).forEach(i => i.addEventListener("change", () => { table[i.dataset.l][i.dataset.c] = i.value.trim(); draw(); }));
        $$("[data-sheet]", el).forEach(i => i.addEventListener("change", () => sheets[i.dataset.sheet] = i.value.trim()));
        $$("[data-up]", el).forEach(i => i.addEventListener("change", () => guarded(null, async () => {
          const r = await E.upload(i.files[0]); sheets[i.dataset.up] = r.path; toast(`Uploaded ${r.name}.`, true); draw(); })));
        $("#addcol", el).onclick = () => { const n = $("#newcol", el).value.trim().replace(/\W+/g, "_"); if (!n || cols.includes(n)) return; cols = [...cols, n]; Object.values(table).forEach(r => r[n] = ""); draw(); };
        $("#apply", el).onclick = e => guarded(e.currentTarget, async () => {
          const empty = Object.entries(table).flatMap(([l, r]) => cols.filter(c => !r[c]).map(c => `${l}/${c}`));
          if (empty.length) throw new Error("Fill in every cell first (missing: " + empty.slice(0, 4).join(", ") + (empty.length > 4 ? "…" : "") + ").");
          const used = Object.fromEntries(cols.filter(usesSheet).map(c => [c, sheets[c]]));
          if (Object.values(used).some(v => !v)) throw new Error("Each from_barcodes column needs a barcode sheet.");
          await E.call("label", { table, columns: cols, sheets: used }); await followTask($("#lprog", el)); await refresh(); counts();
          toast("Labels applied.", true);
        });
        if (reached("labelled")) counts();
      }
      async function counts() {
        const u = await E.call("unique_counts");
        $("#ucounts", el).innerHTML = `<h2>Cells per sample</h2><p class="small muted">Check each sample has roughly the number of cells you expect. A sample far below the rest is easiest to catch here.</p>
          ${barChart(Object.entries(u), { w: 640, title: "Cells per sample" })}${guide("cells_per_sample")}<div class="row" style="margin-top:12px"><button class="btn primary" data-go="step:qc">Continue to filtering →</button></div>`;
      }
      draw();
    }
    labels();
  }

  // ---------------------------------------------------------------- 11 filter cells
  async function qc(el) {
    el.innerHTML = lede("Remove near-empty barcodes and likely doublets. Move the thresholds and watch how many cells each sample keeps.") + `<div class="empty" id="loading">Loading QC data…</div>`;
    const d = await E.call("qc_data"), t = { ...d.thresholds }, c = COL();
    $("#loading", el).remove();
    el.insertAdjacentHTML("beforeend", `<div class="grid g-side"><div><div class="card"><div class="label">UMIs per cell</div><div id="h1"></div></div>
        <div class="card" style="margin-top:18px"><div class="label">Genes per cell</div><div id="h2"></div></div>
        <div class="card" style="margin-top:18px"><div class="label">Genes against UMIs (sample of cells)</div><div id="sc"></div>${guide("filter_cells", { open: true })}</div></div>
      <div><div class="card"><div class="label">Thresholds</div>
        ${[["min_counts", "Minimum UMIs"], ["max_counts", "Maximum UMIs"], ["min_genes", "Minimum genes"], ["max_genes", "Maximum genes"]].map(([k, l]) =>
          `<label class="field"><span>${l}</span><input type="number" min="0" name="${k}" value="${t[k]}"></label>`).join("")}
        <p class="small muted">Lower bounds remove empty barcodes; upper bounds remove likely doublets. Set the upper bounds where the tail of the distribution starts.</p>
        <div id="kept"></div><div class="row" style="margin-top:12px"><button class="btn primary" id="apply">Apply filter</button></div><div id="qprog"></div></div></div></div>`);
    const draw = () => {
      $("#h1", el).innerHTML = logHist(d.umi_edges, Object.fromEntries(Object.entries(d.groups).map(([k, v]) => [k, v.umi])), { lo: t.min_counts, hi: t.max_counts, xlab: "UMIs per cell" });
      $("#h2", el).innerHTML = logHist(d.gene_edges, Object.fromEntries(Object.entries(d.groups).map(([k, v]) => [k, v.gene])), { lo: t.min_genes, hi: t.max_genes, xlab: "Genes per cell" });
      const s = d.scatter, w = 540, h = 300, L = 50, B = 30, lx = v => Math.log10(Math.max(v, 1));
      const xm = Math.max(...s.umi.map(lx)), ym = Math.max(...s.gene.map(lx)), X = v => L + lx(v) / xm * (w - L - 10), Y = v => h - B - lx(v) / ym * (h - B - 10);
      const keep = i => s.umi[i] >= t.min_counts && s.umi[i] < t.max_counts && s.gene[i] >= t.min_genes && s.gene[i] < t.max_genes;
      $("#sc", el).innerHTML = `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="Genes against UMIs">${s.umi.map((u, i) =>
        `<circle cx="${X(u).toFixed(1)}" cy="${Y(s.gene[i]).toFixed(1)}" r="1.6" fill="${keep(i) ? c.golddk : c.ox}" opacity="${keep(i) ? .45 : .9}"/>`).join("")}
        <line x1="${L}" x2="${w}" y1="${h - B}" y2="${h - B}" stroke="${c.muted}"/><line x1="${L}" x2="${L}" y1="0" y2="${h - B}" stroke="${c.muted}"/>
        <text x="${w / 2}" y="${h - 6}" text-anchor="middle" class="ax">UMIs per cell (log)</text><text x="14" y="${h / 2}" transform="rotate(-90 14 ${h / 2})" text-anchor="middle" class="ax">Genes per cell (log)</text></svg>
        <div class="legend"><span><i style="background:${c.golddk}"></i>kept</span><span><i style="background:${c.ox}"></i>removed</span></div>`;
    };
    let tm;
    const preview = () => { clearTimeout(tm); tm = setTimeout(async () => {
      const r = await E.call("qc_preview", t);
      $("#kept", el).innerHTML = `<div class="metric"><span>Cells kept</span><b>${fmt(r.kept)}</b></div><p class="small muted">of ${fmt(r.total)} (${(100 * r.kept / r.total).toFixed(1)}%)</p>
        <table class="small"><thead><tr><th>Sample</th><th class="num">Kept</th></tr></thead><tbody>${r.per_sample.map(x =>
          `<tr><td class="small">${esc(x.sample)}</td><td class="num">${(100 * x.kept / x.total).toFixed(0)}%</td></tr>`).join("")}</tbody></table>`; }, 200); };
    $$("input[type=number]", el).forEach(i => i.addEventListener("input", () => { t[i.name] = Number(i.value); draw(); preview(); }));
    $("#apply", el).onclick = e => guarded(e.currentTarget, async () => {
      await E.call("qc_apply", t); await followTask($("#qprog", el)); await refresh(); toast(`Filter applied: ${fmt(S.an.cells)} cells kept.`, true); H.go("step:cluster");
    });
    draw(); preview();
  }

  // ---------------------------------------------------------------- 12 integrate and cluster
  async function cluster(el) {
    await refresh();
    const prev = S.an.cluster_params || {}, cols = S.an.obs_columns.filter(c => !["Unique", "cluster"].includes(c));
    const P = { n_top_genes: 2000, n_pcs: 30, batch_key: cols.includes("batch") ? "batch" : cols[0], harmony: true, n_neighbors: 15, resolution: 0.6, min_dist: 0.3, ...prev };
    el.innerHTML = lede("Correct for batch, place cells on a map and group them into clusters. Change a setting and run again to compare.") +
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
        <p class="small muted">Batch mixing near 100% means batches are interleaved. Check cell types still separate when you colour by your batch column.</p>
        ${e.n_total > e.xy.length / 2 ? `<p class="small muted">Showing ${fmt(e.xy.length / 2)} of ${fmt(e.n_total)} cells.</p>` : ""}
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

  // ---------------------------------------------------------------- 13–14 markers
  async function markers(el) {
    await refresh();
    const cl = S.an.clusters, P = PALETTE();
    el.innerHTML = lede("Pick a cluster to see the genes that set it apart. Click a gene to see where it is expressed.") +
      `<div class="card"><div class="label">Clusters</div><div class="chips" id="chips">${cl.map((c, i) => `<button class="chip" data-c="${c.id}" aria-pressed="false"><i style="background:${P[i % P.length]}"></i>${c.id} <span class="muted small">${fmt(c.cells)}</span></button>`).join("")}</div></div>
      <div class="grid g2" style="margin-top:18px"><div class="card"><div class="label" id="mt">Markers</div><div id="mk"><p class="small muted">Choose a cluster above.</p></div>${guide("markers")}</div>
        <div class="card"><div class="label" id="ut">UMAP</div><div class="plotwrap"><canvas class="umap" id="cv" style="height:440px"></canvas><div class="tip" id="tip"></div></div><div id="leg"></div></div></div>
      <h2>Dotplot</h2><div class="card"><p class="small muted">Top two markers of every cluster. Dot size is the share of cells expressing the gene; colour is mean expression, scaled per gene.</p>
        <button class="btn" id="dp">Draw dotplot</button><div id="dot" style="overflow:auto;margin-top:12px"></div>${guide("dotplot")}</div>`;
    const um = new EmbeddingPlot($("#cv", el), $("#tip", el)); um.setXY((await embedding()).xy);
    const colour = async key => { const c = await E.call("colour", { key }); um.labels = null; um.setColour(c); if (key === "cluster") um.centroids(c.codes, c.categories); $("#leg", el).innerHTML = legendFor(c); };
    await colour("cluster");
    async function pick(id) {
      $$("#chips .chip", el).forEach(b => b.setAttribute("aria-pressed", b.dataset.c === id));
      $("#mt", el).textContent = `Markers of cluster ${id}`; $("#mk", el).innerHTML = `<p class="small muted">Loading…</p>`;
      const m = await E.call("markers", { cluster: id });
      $("#mk", el).innerHTML = m.length ? `<table><thead><tr><th>Gene</th><th>Best match</th><th class="num">log FC</th><th class="num">In / out</th></tr></thead><tbody>
        ${m.map(g => `<tr class="click" tabindex="0" data-g="${esc(g.gene)}"><td class="mono small">${esc(g.gene)}</td><td class="small">${esc(g.name)}</td><td class="num">${g.logfc}</td><td class="num small">${g.pct_in}% / ${g.pct_out}%</td></tr>`).join("")}</tbody></table>`
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

  // ---------------------------------------------------------------- 15 annotate
  async function annotate(el) {
    await refresh();
    const cl = S.an.clusters, P = PALETTE(); let ann = { ...(S.an.annotations || {}) }, sel = cl[0]?.id;
    el.innerHTML = lede("Give each cluster a cell-type name and a colour. Clusters with the same name are treated as one type. Click a cluster on the map or in the list.") +
      `<div class="grid g-side"><div class="card"><div class="row" style="justify-content:space-between"><div class="label">Cell types</div><span class="small muted" id="prog"></span></div>
        <div class="plotwrap"><canvas class="umap" id="cv"></canvas><div class="tip" id="tip"></div></div><div id="leg"></div></div>
      <div><div class="card"><div class="label" id="et">Cluster</div><label class="field"><span>Cell-type name</span><input type="text" id="nm" list="names"></label><datalist id="names"></datalist>
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
    const cols = S.an.obs_columns.filter(c => !["cluster", "Unique"].includes(c));
    const def = cols.includes("condition") ? "condition" : cols[0];
    el.innerHTML = lede("See how cell-type proportions differ between groups, then save everything to the run folder.") +
      (named() ? "" : `<div class="notice warn">No clusters are named yet, so every cell is "Unannotated". Name clusters first for a useful comparison.</div>`) +
      `<div class="card"><div class="row" style="justify-content:space-between"><div class="label">Composition</div><label class="small">Compare by <select id="grp" style="width:auto">${cols.map(c => `<option ${c === def ? "selected" : ""}>${esc(c)}</option>`).join("")}</select></label></div>
        <div id="comp"></div>${guide("composition")}</div>
      <h2>Export</h2><div class="card"><p class="small">Writes the annotated data, composition tables, a marker workbook and a UMAP figure to <code>${esc(E.state().run.dir)}/results</code>. You can also download them here.</p>
        <div class="row"><button class="btn primary" id="exp">Export results</button></div><div id="eprog"></div><div id="files"></div></div>`;
    async function comp() {
      const g = $("#grp", el).value, d = await E.call("composition", { group: g });
      const rows = d.groups.map((gr, j) => [`${gr} (n=${fmt(d.group_sizes[j])})`, d.types.map((_, i) => d.fractions[i][j])]);
      $("#comp", el).innerHTML = stacked(rows, d.types, d.colors, { w: 760, left: 190, title: "Composition" }) +
        `<table style="margin-top:16px"><thead><tr><th>Cell type</th>${d.groups.map(x => `<th class="num">${esc(x)}</th>`).join("")}</tr></thead><tbody>
        ${d.types.map((t, i) => `<tr><td><span class="chip" style="cursor:inherit"><i style="background:${d.colors[i]}"></i>${esc(t)}</span></td>${d.groups.map((_, j) => `<td class="num">${(100 * d.fractions[i][j]).toFixed(1)}% <span class="muted small">(${fmt(d.counts[i][j])})</span></td>`).join("")}</tr>`).join("")}</tbody></table>
        ${d.group_sizes.some(n => n < 50) ? `<div class="notice warn" style="margin-top:12px">At least one group has fewer than 50 cells; treat its proportions as anecdotal.</div>` : ""}
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

  E.registerViews("singlecell.splitseq", { report, merge, qc, cluster, markers, annotate, compare });
})();
