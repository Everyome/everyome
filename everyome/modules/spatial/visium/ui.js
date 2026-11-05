/* Views for 10x Visium: load the sections, then the shared single-cell steps (spots instead of cells, regions instead of
   cell types; ../../singlecell/shared/cells_ui.js), plus the shared spatial views (../shared/spatial_ui.js): the tissue
   with spatially variable genes, and neighbourhoods. */
"use strict";
(() => {
  const E = window.Everyome, H = E.helpers, { $, $$, esc, fmt, toast, guarded, followTask, barChart, legendFor, guide } = H;
  const { S, refresh, reached, views } = E.cells({ order: ["loaded", "filtered", "clustered", "exported"], words: {
    unit: "spot", units: "spots", Units: "Spots", type: "region", types: "regions", Type: "Region",
    qc: "Remove spots with too little RNA to be trusted (often at torn or folded tissue) and spots from damaged tissue. Move the thresholds and watch how many spots each section keeps.",
    qcNote: "Lower bounds remove spots with little RNA; upper bounds are rarely needed for spots (each holds several cells), so set them high." } });
  const lede = t => `<p class="lede">${t}</p>`;

  const { tissueSvg, tissue, neighbourhood } = E.spatial({ S, refresh, reached, words: { typeNames: "Region names", typeWord: "regions" } });

  // ---------------------------------------------------------------- load
  async function load(el) {
    await refresh();
    const rows = await E.call("samples_info");
    el.innerHTML = lede("Everyome reads each section's Space Ranger output: the spots under the tissue, their counts and the tissue image.") +
      `<div class="card"><div class="label">Sections</div><table><thead><tr><th>Section</th><th>Condition</th><th>Batch</th><th>Space Ranger output</th></tr></thead><tbody>
        ${rows.map(r => `<tr><td>${esc(r.sample)}</td><td>${esc(r.condition)}</td><td>${esc(r.batch || "–")}</td><td><code class="small" style="word-break:break-all">${esc(r.outs)}</code></td></tr>`).join("")}</tbody></table>
        ${guide("load")}<div class="row" style="margin-top:12px"><button class="btn primary" id="go">${reached("loaded") ? "Load again" : "Load"}</button></div><div id="lprog"></div></div>
      <div id="after"></div>`;
    async function show() {
      if (!reached("loaded")) return;
      const n = await E.call("spots_per_sample");
      $("#after", el).innerHTML = `<div class="card" style="margin-top:18px"><div class="label">Spots under the tissue</div>${barChart(Object.entries(n), { w: 560, title: "Spots per section" })}${guide("cells_per_sample")}</div>
        <div class="grid g2" style="margin-top:18px" id="thumbs"></div>
        <div class="row" style="margin-top:12px"><button class="btn primary" data-go="step:qc">Continue to filtering →</button></div>`;
      for (const s of Object.keys(n)) {
        const d = await E.call("tissue", { sample: s, key: "total_counts" });
        $("#thumbs", el).insertAdjacentHTML("beforeend", `<div class="card"><div class="label">${esc(s)} · UMIs per spot</div>${tissueSvg(d, { maxW: 420 })}${legendFor(d.colour)}</div>`);
      }
    }
    $("#go", el).onclick = e => guarded(e.currentTarget, async () => {
      await E.call("load"); await followTask($("#lprog", el)); await refresh(); toast(`Loaded ${fmt(S.an.cells)} spots.`, true); show();
    });
    show();
  }

  E.registerViews("spatial.visium", { load, ...views, tissue, neighbourhood });
})();
