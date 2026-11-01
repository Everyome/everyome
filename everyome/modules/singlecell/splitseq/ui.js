/* Views for the SPLiT-seq (SPLiTscape) module, ported from the SPLiTscape app by Helen R Horkan PhD.
   report: read QC after the cluster stages; then the six live-session steps (merge … compare).
   Uses only Everyome's shared helpers, so every chart follows the active theme. */
"use strict";
(() => {
  const E = window.Everyome, H = E.helpers;
  const { $, $$, esc, fmt, fmtSize, toast, guarded, followTask, barChart, logHist, logLine, stacked, dotplot, legendFor, EmbeddingPlot, guide } = H;
  const COL = () => H.COL(), PALETTE = () => H.PALETTE();
  // Intent: filtering, clustering, markers, naming and export are shared with other single-cell modules (shared/cells_ui.js).
  const { S, refresh, reached, views } = E.cells({ order: ["merged", "labelled", "filtered", "clustered", "exported"] });
  const lede = t => `<p class="lede">${t}</p>`;

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

  E.registerViews("singlecell.splitseq", { report, merge, ...views });
})();
