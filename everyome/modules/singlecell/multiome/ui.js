/* Views for multiome: reading Cell Ranger ARC's matrices. Filtering, clustering (with a choice of RNA, ATAC or both),
   markers, naming and export are the shared single-cell views (../shared/cells_ui.js). */
"use strict";
(() => {
  const E = window.Everyome, H = E.helpers, { $, esc, fmt, toast, guarded, followTask, guide, lede } = H;
  const { S, refresh, reached, views } = E.cells({ order: ["loaded", "filtered", "clustered", "exported"], words: {
    modes: [["joint", "RNA and ATAC together"], ["rna", "RNA only"], ["atac", "ATAC only"]], modesLabel: "Cluster on" } });

  async function load(el) {
    await refresh();
    const done = S.an.loaded_from || {};
    el.innerHTML = lede("Read each sample's matrices: genes (RNA) and peaks (open chromatin) for the same cells.") +
      `<div class="grid g-side"><div class="card"><div class="label">Settings</div>
          <label class="field"><span>Fewest ATAC counts for a cell</span><input type="number" id="mina" min="0" step="100" value="${done.min_atac ?? 500}">
            <small>Cells with less open-chromatin signal than this are left out; the RNA thresholds come in the next step.</small></label>
          ${guide("matrices")}<div class="row" style="margin-top:12px"><button class="btn primary" id="go">${reached("loaded") ? "Read again" : "Read the matrices"}</button></div><div id="lprog"></div></div>
        <div class="card"><div class="label">Cells per sample</div><div id="cps"><p class="small muted">Read the matrices to see each sample's cells.</p></div></div></div>`;
    async function show() {
      if (!reached("loaded")) return;
      const l = S.an.loaded_from, s = await E.call("load_summary");
      $("#cps", el).innerHTML = `<p class="small">${fmt(l.cells)} cells, ${fmt(l.genes)} genes and ${fmt(l.peaks)} peaks.</p>
        <table><thead><tr><th>Sample</th><th class="num">Cells</th><th class="num">Median RNA UMIs</th><th class="num">Median ATAC counts</th></tr></thead><tbody>
        ${s.samples.map(r => `<tr><td>${esc(r.sample)}</td><td class="num">${fmt(r.cells)}</td><td class="num">${fmt(r.median_umis)}</td><td class="num">${fmt(r.median_atac)}</td></tr>`).join("")}</tbody></table>
        <div class="row" style="margin-top:12px"><button class="btn primary" data-go="step:qc">Continue to filtering →</button></div>`;
    }
    $("#go", el).onclick = e => guarded(e.currentTarget, async () => {
      await E.call("load", { min_atac: Number($("#mina", el).value) }); await followTask($("#lprog", el)); await refresh();
      toast(`Read ${fmt(S.an.cells)} cells.`, true); show();
    });
    show();
  }

  E.registerViews("singlecell.multiome", { load, ...views });
})();
