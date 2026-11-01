/* Views for 10x Visium: load the sections, then the shared single-cell steps (spots instead of cells, regions instead of
   cell types; ../../singlecell/shared/cells_ui.js), plus the tissue view with spatially variable genes. */
"use strict";
(() => {
  const E = window.Everyome, H = E.helpers, { $, $$, esc, fmt, toast, guarded, followTask, barChart, legendFor, guide } = H;
  const { S, refresh, reached, views } = E.cells({ order: ["loaded", "filtered", "clustered", "exported"], words: {
    unit: "spot", units: "spots", Units: "Spots", type: "region", types: "regions", Type: "Region",
    qc: "Remove spots with too little RNA to be trusted (often at torn or folded tissue) and spots from damaged tissue. Move the thresholds and watch how many spots each section keeps.",
    qcNote: "Lower bounds remove spots with little RNA; upper bounds are rarely needed for spots (each holds several cells), so set them high." } });
  const lede = t => `<p class="lede">${t}</p>`;

  // A colour for spot i: categories use their own colours; numbers run from pale to the theme's strong colour.
  function colourOf(c, i) {
    const C = H.COL();
    if (c.kind === "cat") return c.colors[c.codes[i]] || C.rule;
    const t = Math.min(1, c.values[i] / (c.max || 1)), a = H.hexRgb(C.parch), m = H.hexRgb(C.gold), b = H.hexRgb(C.ox);
    const mix = (p, q, s) => p.map((v, k) => Math.round(v + (q[k] - v) * s));
    return `rgb(${t < .5 ? mix(a, m, t * 2) : mix(m, b, (t - .5) * 2)})`;
  }
  function tissueSvg(d, { opacity = 0.85, maxW = 560, size = 1.4 } = {}) {
    const c = H.themed(d.colour);
    const order = d.x.map((_, i) => i);
    if (c.kind === "num") order.sort((i, j) => c.values[i] - c.values[j]);      // strongest spots drawn last, on top
    return `<svg class="chart" viewBox="0 0 ${d.width} ${d.height}" style="max-width:${maxW}px;background:${H.COL().card}" role="img" aria-label="Spots on the tissue">
      ${d.image ? `<image href="${d.image}" x="0" y="0" width="${d.width}" height="${d.height}"/>` : ""}
      ${order.map(i => `<circle cx="${d.x[i]}" cy="${d.y[i]}" r="${(d.r * size).toFixed(2)}" fill="${colourOf(c, i)}" fill-opacity="${opacity}"><title>${esc(c.kind === "cat" ? c.categories[c.codes[i]] : `${c.gene}: ${c.values[i]}`)}</title></circle>`).join("")}</svg>`;
  }

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

  // ---------------------------------------------------------------- on the tissue
  async function tissue(el) {
    await refresh();
    const sections = Object.keys(await E.call("spots_per_sample")), cols = S.an.obs_columns || [];
    const keys = [...(reached("clustered") ? ["cluster", "annotation"] : []), "total_counts", "n_genes", ...cols.filter(c => !["cluster"].includes(c))];
    const label = { cluster: "Cluster", annotation: "Region names", total_counts: "UMIs per spot", n_genes: "Genes per spot" };
    el.innerHTML = lede("Every spot in its place on the tissue. Colour the spots by region, by a gene, or by a quality measure, and look for genes whose expression follows the tissue's structure.") +
      `<div class="grid g-side"><div class="card"><div class="row" style="justify-content:space-between;flex-wrap:wrap;gap:8px">
          <label class="small">Section <select id="sec" style="width:auto">${sections.map(s => `<option>${esc(s)}</option>`).join("")}</select></label>
          <label class="small">Colour by <select id="key" style="width:auto">${keys.map(k => `<option value="${esc(k)}">${esc(label[k] || k)}</option>`).join("")}</select></label>
          <input type="text" id="gq" placeholder="Gene…" style="width:140px" list="gl" aria-label="Colour by gene"><datalist id="gl"></datalist>
          <label class="small">Spot opacity <input type="range" id="op" min="0" max="1" step="0.05" value="0.9" style="width:80px"></label>
          <label class="small" title="1 is the spots' true size; larger is easier to see">Spot size <input type="range" id="sz" min="1" max="2" step="0.1" value="1.4" style="width:80px"></label></div>
        <div id="view" style="margin-top:10px"></div><div id="leg"></div>${guide("tissue")}</div>
        <div><div class="card"><div class="label">Spatially variable genes</div>
          <p class="small muted">Genes whose expression is similar in neighbouring spots (Moran's I, from 0 for no pattern up to 1).</p>
          <div id="svg"></div><div class="row" style="margin-top:10px"><button class="btn" id="find">${S.an.spatial_genes ? "Find again" : "Find them"}</button></div><div id="sprog"></div>${guide("spatial_genes")}</div></div></div>`;
    let key = reached("clustered") ? "cluster" : "total_counts";
    $("#key", el).value = key;
    const draw = async () => {
      const d = await E.call("tissue", { sample: $("#sec", el).value, key });
      $("#view", el).innerHTML = tissueSvg(d, { opacity: +$("#op", el).value, size: +$("#sz", el).value, maxW: 640 });
      $("#leg", el).innerHTML = legendFor(d.colour) + `<p class="small muted">${fmt(d.spots)} spots.</p>`;
    };
    const list = () => {
      const g = S.an.spatial_genes;
      $("#svg", el).innerHTML = g ? `<table class="small"><thead><tr><th>Gene</th><th class="num">Moran's I</th><th class="num">In spots</th></tr></thead><tbody>${g.slice(0, 25).map(x =>
        `<tr class="click" tabindex="0" data-g="${esc(x.gene)}"><td class="mono">${esc(x.gene)}</td><td class="num">${x.morans_i.toFixed(2)}</td><td class="num">${x.detected}%</td></tr>`).join("")}</tbody></table>` : "";
    };
    $("#sec", el).onchange = draw;
    $("#key", el).onchange = e => { key = e.target.value; draw(); };
    $("#op", el).oninput = draw; $("#sz", el).oninput = draw;
    $("#svg", el).addEventListener("click", e => { const r = e.target.closest("[data-g]"); if (r) { key = r.dataset.g; $("#gq", el).value = key; draw(); } });
    $("#svg", el).addEventListener("keydown", e => { if (e.key === "Enter") e.target.click(); });
    let gt; $("#gq", el).addEventListener("input", e => { clearTimeout(gt); gt = setTimeout(async () => {
      const q = e.target.value.trim(); if (q.length < 2) return;
      const g = await E.call("genes", { q }).catch(() => []);
      $("#gl", el).innerHTML = g.map(x => `<option value="${esc(x.gene)}">`).join("");
      if (g.some(x => x.gene === q)) { key = q; draw(); } }, 250); });
    $("#find", el).onclick = e => guarded(e.currentTarget, async () => {
      await E.call("spatial_genes", {}); await followTask($("#sprog", el)); await refresh(); list(); toast("Spatially variable genes found.", true);
    });
    list(); draw();
  }

  E.registerViews("spatial.visium", { load, ...views, tissue });
})();
