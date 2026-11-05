/* Views for high-resolution spatial data: read the sections at a bin size, then the shared single-cell steps
   (../../singlecell/shared/cells_ui.js) and the shared spatial views (../shared/spatial_ui.js). */
"use strict";
(() => {
  const E = window.Everyome, H = E.helpers, { $, esc, fmt, toast, guarded, followTask, barChart, legendFor, guide, lede } = H;
  const { S, refresh, reached, views } = E.cells({ order: ["loaded", "filtered", "clustered", "exported"], words: {
    unit: "bin", units: "bins", Units: "Bins",
    qc: "Remove bins with too little RNA to place (often outside the tissue or at tears). Move the thresholds and watch how many bins each section keeps.",
    qcNote: "Small bins hold little RNA; keep the lower bounds low, especially at 2 µm." } });
  const { tissueSvg, tissue, neighbourhood } = E.spatial({ S, refresh, reached, words: {
    unit: "bin", units: "bins", count: "UMIs per bin", features: "Genes per bin", typeNames: "Names", typeWord: "types" } });

  async function load(el) {
    await refresh();
    const rows = await E.call("samples_info"), done = S.an.loaded_from || {};
    el.innerHTML = lede("Everyome reads each section's bins (or beads), their counts and positions, at the bin size you choose.") +
      `<div class="card"><div class="label">Sections</div><table><thead><tr><th>Section</th><th>Platform</th><th>Condition</th><th>Output folder</th></tr></thead><tbody>
        ${rows.map(r => `<tr><td>${esc(r.sample)}</td><td>${esc(r.platform || "auto")}</td><td>${esc(r.condition)}</td><td><code class="small" style="word-break:break-all">${esc(r.outs)}</code></td></tr>`).join("")}</tbody></table>
        <label class="field" style="max-width:260px;margin-top:12px"><span>Bin size</span><select id="bin">${[2, 8, 16].map(b => `<option value="${b}" ${b === (done.bin_um || 8) ? "selected" : ""}>${b} µm</option>`).join("")}</select></label>
        ${guide("load")}<div class="row" style="margin-top:12px"><button class="btn primary" id="go">${reached("loaded") ? "Read again" : "Read the sections"}</button></div><div id="lprog"></div></div>
      <div id="after"></div>`;
    async function show() {
      if (!reached("loaded")) return;
      const n = await E.call("spots_per_sample");
      $("#after", el).innerHTML = `<div class="card" style="margin-top:18px"><div class="label">Bins per section (${S.an.loaded_from.bin_um} µm)</div>${barChart(Object.entries(n), { w: 560, title: "Bins per section" })}${guide("cells_per_sample")}</div>
        <div class="grid g2" style="margin-top:18px" id="thumbs"></div>
        <div class="row" style="margin-top:12px"><button class="btn primary" data-go="step:qc">Continue to filtering →</button></div>`;
      for (const s of Object.keys(n)) {
        const d = await E.call("tissue", { sample: s, key: "total_counts" });
        $("#thumbs", el).insertAdjacentHTML("beforeend", `<div class="card"><div class="label">${esc(s)} · UMIs per bin</div>${tissueSvg(d, { maxW: 420, size: 1, opacity: 0.8 })}${legendFor(d.colour)}
          ${d.drawn < d.spots ? `<p class="small muted">Showing ${fmt(d.drawn)} of ${fmt(d.spots)} bins.</p>` : ""}</div>`);
      }
    }
    $("#go", el).onclick = e => guarded(e.currentTarget, async () => {
      await E.call("load", { bin_um: Number($("#bin", el).value) }); await followTask($("#lprog", el)); await refresh(); toast(`Read ${fmt(S.an.cells)} bins.`, true); show();
    });
    show();
  }

  E.registerViews("spatial.hires", { load, ...views, tissue, neighbourhood });
})();
