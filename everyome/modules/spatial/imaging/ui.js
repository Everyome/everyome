/* Views for imaging spatial data: read the sections, then the shared single-cell steps (../../singlecell/shared/cells_ui.js)
   and the shared spatial views (../shared/spatial_ui.js): cells on the tissue, spatially variable genes, neighbourhoods. */
"use strict";
(() => {
  const E = window.Everyome, H = E.helpers, { $, esc, fmt, toast, guarded, followTask, barChart, legendFor, guide, lede } = H;
  const { S, refresh, reached, views } = E.cells({ order: ["loaded", "filtered", "clustered", "exported"], words: {
    count: "Transcripts", featureLow: "genes",
    qc: "Remove cells with too few transcripts to place them (often cells cut at the section's surface or poorly segmented). " +
        "Move the thresholds and watch how many cells each section keeps.",
    qcNote: "Panels measure hundreds of genes, so cells have far fewer transcripts than in single-cell RNA-seq; keep the lower bounds low." } });
  const { tissueSvg, tissue, neighbourhood } = E.spatial({ S, refresh, reached, words: {
    unit: "cell", units: "cells", count: "Transcripts per cell", features: "Genes per cell", typeNames: "Cell type names", typeWord: "cell types" } });

  async function load(el) {
    await refresh();
    const rows = await E.call("samples_info");
    el.innerHTML = lede("Everyome reads each section's cells, their transcript counts and their positions, leaving out control probes.") +
      `<div class="card"><div class="label">Sections</div><table><thead><tr><th>Section</th><th>Platform</th><th>Condition</th><th>Batch</th><th>Output folder</th></tr></thead><tbody>
        ${rows.map(r => `<tr><td>${esc(r.sample)}</td><td>${esc(r.platform || "auto")}</td><td>${esc(r.condition)}</td><td>${esc(r.batch || "–")}</td><td><code class="small" style="word-break:break-all">${esc(r.outs)}</code></td></tr>`).join("")}</tbody></table>
        ${guide("load")}<div class="row" style="margin-top:12px"><button class="btn primary" id="go">${reached("loaded") ? "Read again" : "Read the sections"}</button></div><div id="lprog"></div></div>
      <div id="after"></div>`;
    async function show() {
      if (!reached("loaded")) return;
      const n = await E.call("spots_per_sample");
      $("#after", el).innerHTML = `<div class="card" style="margin-top:18px"><div class="label">Cells per section</div>${barChart(Object.entries(n), { w: 560, title: "Cells per section" })}${guide("cells_per_sample")}</div>
        <div class="grid g2" style="margin-top:18px" id="thumbs"></div>
        <div class="row" style="margin-top:12px"><button class="btn primary" data-go="step:qc">Continue to filtering →</button></div>`;
      for (const s of Object.keys(n)) {
        const d = await E.call("tissue", { sample: s, key: "total_counts" });
        $("#thumbs", el).insertAdjacentHTML("beforeend", `<div class="card"><div class="label">${esc(s)} · transcripts per cell</div>${tissueSvg(d, { maxW: 420, size: 1 })}${legendFor(d.colour)}
          ${d.drawn < d.spots ? `<p class="small muted">Showing ${fmt(d.drawn)} of ${fmt(d.spots)} cells.</p>` : ""}</div>`);
      }
    }
    $("#go", el).onclick = e => guarded(e.currentTarget, async () => {
      await E.call("load"); await followTask($("#lprog", el)); await refresh(); toast(`Read ${fmt(S.an.cells)} cells.`, true); show();
    });
    show();
  }

  E.registerViews("spatial.imaging", { load, ...views, tissue, neighbourhood });
})();
