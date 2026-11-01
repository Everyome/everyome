/* Views for the single-cell RNA-seq module: what nf-core/scrnaseq made (Run page), then loading the cells.
   Filtering, clustering, markers, naming and export are the shared single-cell views (../shared/cells_ui.js). */
"use strict";
(() => {
  const E = window.Everyome, H = E.helpers, { $, esc, fmt, toast, guarded, followTask, barChart, guide } = H;
  const { S, refresh, reached, views } = E.cells({ order: ["loaded", "filtered", "clustered", "exported"] });
  const lede = t => `<p class="lede">${t}</p>`;

  // ---------------------------------------------------------------- after the pipeline (Run page)
  async function report(el, q) {
    const st = E.state();
    el.innerHTML = `<h2>What the pipeline made</h2>
      <div class="grid g2"><div class="card"><div class="label">Cell-by-gene matrices</div>
        ${q.matrices.length ? `<table><tbody>${q.matrices.map(m => `<tr><td class="small"><b>${esc(m.description)}</b><br><code class="small" style="word-break:break-all">${esc(m.path)}</code></td></tr>`).join("")}</tbody></table>
          <p class="small muted" style="margin-top:8px">The live session starts from the first one; you can choose another there.</p>`
          : `<div class="notice warn">No combined matrix was found. Check the pipeline log; the live session needs one.</div>`}</div>
      <div class="card"><div class="label">Quality report</div>
        ${q.multiqc ? `<p class="small">nf-core/scrnaseq's MultiQC report brings together the read quality checks and, for each sample, how many reads carried a valid cell barcode and mapped to genes.</p>
          <a class="btn primary small" href="/api/run/file?path=${encodeURIComponent(q.multiqc)}" target="_blank" rel="noopener">Open the MultiQC report</a>`
          : `<p class="small muted">No MultiQC report found.</p>`}
        ${st.demo ? `<p class="small muted" style="margin-top:10px">On the demo cluster this is a placeholder.</p>` : ""}</div></div>${guide("pipeline_report")}`;
  }

  // ---------------------------------------------------------------- load the cells
  async function load(el) {
    await refresh();
    const ms = (await E.call("matrices")).filter(m => m.exists), done = S.an.loaded_from;
    el.innerHTML = lede("Choose which matrix to start from. The one with empty droplets and background removed is best for most experiments.") +
      `<div class="grid g-side"><div class="card"><div class="label">Matrix</div>
        ${ms.map((m, i) => `<label class="row small" style="margin:6px 0;flex-wrap:nowrap;align-items:flex-start"><input type="radio" name="mx" value="${esc(m.kind)}" ${(done ? done.kind === m.kind : i === 0) ? "checked" : ""}>
          <span><b>${esc(m.description)}</b><br><code class="small" style="word-break:break-all">${esc(m.path)}</code></span></label>`).join("")}
        ${guide("matrix")}
        <div class="row" style="margin-top:12px"><button class="btn primary" id="go">${done ? "Load again" : "Load"}</button></div><div id="lprog"></div></div>
      <div class="card"><div class="label">Cells per sample</div><div id="cps"><p class="small muted">Load a matrix to see how many cells each sample has.</p></div>${guide("cells_per_sample")}</div></div>`;
    async function show() {
      if (!reached("loaded")) return;
      const l = S.an.loaded_from, c = await E.call("cells_per_sample");
      $("#cps", el).innerHTML = `<p class="small">${fmt(l.cells)} barcodes and ${fmt(l.genes)} genes from <code style="word-break:break-all">${esc(l.path)}</code>.</p>
        ${l.missing.length ? `<div class="notice warn">No cells were found for: ${l.missing.map(esc).join(", ")}. Check these samples in the MultiQC report.</div>` : ""}
        ${l.unknown.length ? `<div class="notice warn">Cells from samples not in your table were left out: ${l.unknown.map(esc).join(", ")}.</div>` : ""}
        ${barChart(Object.entries(c), { w: 560, title: "Cells per sample" })}
        <div class="row" style="margin-top:12px"><button class="btn primary" data-go="step:qc">Continue to filtering →</button></div>`;
    }
    $("#go", el).onclick = e => guarded(e.currentTarget, async () => {
      await E.call("load", { kind: $("input[name=mx]:checked", el)?.value || "" }); await followTask($("#lprog", el)); await refresh();
      toast(`Loaded ${fmt(S.an.cells)} cells.`, true); show();
    });
    show();
  }

  E.registerViews("singlecell.scrna", { report, load, ...views });
})();
