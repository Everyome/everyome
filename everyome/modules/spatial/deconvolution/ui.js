/* Views for cell types in spots: pipeline report, checks on the mapping, cell types on the tissue, cell types found
   together, export. Draws spots with the shared spatial views (../shared/spatial_ui.js), so the tissue looks the same
   as in the Visium module and follows the active theme. */
"use strict";
(() => {
  const E = window.Everyome, H = E.helpers;
  const { $, esc, fmt, toast, guarded, guide, legend, lede, filesTable, barChart } = H;
  const COL = () => H.COL();
  const SP = E.spatial({ S: { an: {} }, refresh: async () => {}, reached: () => false });
  let ov = null;
  const overview = async () => (ov = ov || await E.call("overview"));

  // A training curve: loss against training round (log scale on loss), so you can see it flatten.
  function curve(points, title) {
    if (!points.length) return `<p class="small muted">No training curve was saved.</p>`;
    const w = 520, h = 170, L = 50, B = 28, T = 10, xs = points.map(p => p[0]), ys = points.map(p => Math.log10(p[1]));
    const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
    const X = v => L + (v - x0) / ((x1 - x0) || 1) * (w - L - 10), Y = v => T + (y1 - v) / ((y1 - y0) || 1) * (h - B - T);
    return `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(title)}"><polyline fill="none" stroke="${COL().ox}" stroke-width="2" points="${points.map((p, i) => `${X(xs[i]).toFixed(1)},${Y(ys[i]).toFixed(1)}`).join(" ")}"/>
      <line x1="${L}" x2="${w - 10}" y1="${h - B}" y2="${h - B}" stroke="${COL().muted}"/><text x="${L}" y="${h - 8}" class="ax">round ${fmt(x0)}</text><text x="${w - 10}" y="${h - 8}" text-anchor="end" class="ax">${fmt(x1)}</text>
      <text x="${L - 6}" y="${T + 8}" text-anchor="end" class="ax">${fmt(Math.round(10 ** y1))}</text><text x="${L - 6}" y="${h - B}" text-anchor="end" class="ax">${fmt(Math.round(10 ** y0))}</text>
      <text x="${(w + L) / 2}" y="${T + 10}" text-anchor="middle" class="ax">${esc(title)}</text></svg>`;
  }

  // ---------------------------------------------------------------- pipeline report (Run page)
  async function report(el, q) {
    el.innerHTML = `<h2>What the run made</h2><div class="grid g2">
      <div class="card"><div class="label">Cell types mapped</div>
        ${q.types.length ? `<p class="small">${q.types.length} cell types from the reference, mapped to ${fmt(q.spots)} spots:</p><p class="small">${q.types.map(esc).join(", ")}</p>`
          : `<div class="notice warn">No cell abundances were found. Check the stage logs; the live session needs them.</div>`}</div>
      <div class="card"><div class="label">Training</div>${curve(q.reference_curve, "Reference model")}${curve(q.mapping_curve, "Mapping model")}</div></div>${guide("pipeline_report")}`;
  }

  // ---------------------------------------------------------------- check the mapping
  async function overviewView(el) {
    const o = await overview();
    el.innerHTML = lede(`${o.types.length} cell types mapped to ${fmt(o.spots)} spots in ${o.sections.length} section${o.sections.length > 1 ? "s" : ""}. First, check the models trained fully and the numbers of cells look sensible.`) +
      `<div class="grid g2"><div class="card"><div class="label">Training</div>${curve(o.reference_curve, "Reference model")}${curve(o.mapping_curve, "Mapping model")}${guide("training", { open: true })}</div>
        <div class="card"><div class="label">Cells per spot (all types)</div>
          ${barChart(o.cells_hist.counts.map((c, i) => [`${o.cells_hist.edges[i]}–${o.cells_hist.edges[i + 1]}`, c]), { label: v => fmt(v), title: "Spots by estimated cells" })}
          <p class="small">Median ${o.median_cells} cells per spot; the run expected about ${esc(String(o.expected))}.</p></div></div>
      <div class="card" style="margin-top:18px"><div class="label">Each cell type</div><div style="overflow:auto"><table><thead><tr><th>Cell type</th><th class="num">Cells (all spots)</th><th class="num">Spots where it is the main type</th>${o.sections.map(s => `<th class="num">${esc(s)}</th>`).join("")}</tr></thead><tbody>
        ${o.per_type.map(t => `<tr><td><span class="chip" style="cursor:inherit"><i style="background:${o.colours[t.type]}"></i>${esc(t.type)}</span></td><td class="num">${fmt(t.cells)}</td><td class="num">${fmt(t.dominant_spots)}</td>${o.sections.map(s => `<td class="num">${fmt(t[s])}</td>`).join("")}</tr>`).join("")}</tbody></table></div>${guide("abundance")}</div>
      <div class="row" style="margin-top:18px"><button class="btn primary" data-go="step:tissue">See them on the tissue →</button></div>`;
  }

  // ---------------------------------------------------------------- on the tissue
  async function tissue(el) {
    const o = await overview();
    el.innerHTML = lede("Each cell type where it lies. Colour by one cell type, by the main type in each spot, or by all cells together.") +
      `<div class="grid g-side"><div class="card"><div class="row" style="justify-content:space-between;flex-wrap:wrap;gap:8px">
          <label class="small">Section <select id="sec" style="width:auto">${o.sections.map(s => `<option>${esc(s)}</option>`).join("")}</select></label>
          <label class="small">Colour by <select id="key" style="width:auto"><option value="dominant">Main cell type</option><option value="total">All cells</option>${o.types.map(t => `<option>${esc(t)}</option>`).join("")}</select></label>
          <label class="small">Show <select id="measure" style="width:auto"><option value="mean">cells (mean estimate)</option><option value="q05">cells (cautious estimate)</option><option value="share">share of the spot</option></select></label>
          <label class="small">Opacity <input type="range" id="op" min="0" max="1" step="0.05" value="0.9" style="width:80px"></label></div>
        <div id="view" style="margin-top:10px"></div><div id="leg"></div><div id="g"></div></div>
        <div class="card"><div class="label">Signature genes</div><div id="sig"><p class="small muted">Choose a cell type to see the genes that mark it in the reference.</p></div>${guide("signature")}</div></div>
      <div class="row" style="margin-top:18px"><button class="btn primary" data-go="step:together">Which types live together →</button></div>`;
    const draw = async () => {
      const key = $("#key", el).value, d = await E.call("tissue", { sample: $("#sec", el).value, key, measure: $("#measure", el).value });
      $("#view", el).innerHTML = SP.tissueSvg(d, { opacity: +$("#op", el).value, maxW: 640 });
      $("#leg", el).innerHTML = key === "dominant" ? legend(o.types.map(t => [t, o.colours[t]]))
        : legend([[`low ${d.colour.label}`, COL().parch], [`high (${fmt(d.colour.max)})`, COL().ox]]);
      $("#g", el).innerHTML = key === "dominant" ? guide("dominant") : guide("tissue");
      if (o.types.includes(key)) {
        const s = await E.call("signature", { cell_type: key });
        $("#sig", el).innerHTML = `<p class="small"><b>${esc(key)}</b>: genes most specific to it in the reference.</p><table><thead><tr><th>Gene</th><th class="num">Expression</th><th class="num">Specificity</th></tr></thead><tbody>
          ${s.genes.map(g => `<tr><td>${esc(g.gene)}</td><td class="num">${g.expression}</td><td class="num">${Math.round(g.specificity * 100)}%</td></tr>`).join("")}</tbody></table>`;
      }
    };
    ["#sec", "#key", "#measure", "#op"].forEach(s => $(s, el).addEventListener(s === "#op" ? "input" : "change", () => draw().catch(err => toast(err.message))));
    await draw();
  }

  // ---------------------------------------------------------------- together
  async function together(el) {
    el.innerHTML = lede("Cell types that rise and fall together across spots tend to share a place in the tissue: neighbours, layers, or a niche.") +
      `<div class="card"><div class="grid g3">
          <label class="field"><span>Compare</span><select id="measure"><option value="share">share of each spot</option><option value="mean">number of cells</option></select></label>
          <label class="field"><span>Leave out spots with fewer cells than</span><input type="number" id="min" min="0" step="0.5" value="0.5"></label></div>
        <div class="row"><button class="btn primary" id="go">Compare cell types</button></div></div><div id="out"></div>`;
    $("#go", el).onclick = e => guarded(e.currentTarget, async () => {
      const r = await E.call("together", { measure: $("#measure", el).value, min_cells: Number($("#min", el).value) });
      const C = COL(), n = r.types.length, cell = 34, left = 150, top = 120, w = left + n * cell + 20, h = top + n * cell + 10;
      const a = H.hexRgb(C.parch), pos = H.hexRgb(C.ox), neg = H.hexRgb(C.plum || C.ink);
      const mix = (to, t) => `rgb(${a.map((v, i) => Math.round(v + (to[i] - v) * Math.min(1, Math.abs(t))))})`;
      let svg = `<svg class="chart" style="max-width:${w}px" viewBox="0 0 ${w} ${h}" role="img" aria-label="Correlation between cell types across spots">`;
      r.types.forEach((t, j) => svg += `<text transform="translate(${left + j * cell + cell / 2 + 4},${top - 6}) rotate(-50)" class="ax">${esc(t)}</text>`);
      r.types.forEach((t, i) => {
        svg += `<text x="${left - 6}" y="${top + i * cell + cell / 2 + 4}" text-anchor="end" class="ax">${esc(t)}</text>`;
        r.corr[i].forEach((v, j) => svg += `<rect x="${left + j * cell}" y="${top + i * cell}" width="${cell - 1}" height="${cell - 1}" fill="${v >= 0 ? mix(pos, v) : mix(neg, v)}"><title>${esc(t)} · ${esc(r.types[j])}: r = ${v}</title></rect>`);
      });
      svg += "</svg>";
      $("#out", el).innerHTML = `<div class="grid g2" style="margin-top:18px"><div class="card"><div class="label">Correlation across ${fmt(r.spots)} spots</div><div style="overflow:auto">${svg}</div>
          ${legend([["found together", C.ox], ["kept apart", C.plum || C.ink]])}${guide("together", { open: true })}</div>
        <div class="card"><div class="label">Pairs, most together first</div><table><thead><tr><th>Cell types</th><th class="num">r</th></tr></thead><tbody>
          ${r.pairs.map(p => `<tr><td>${esc(p[0])} and ${esc(p[1])}</td><td class="num">${p[2].toFixed(2)}</td></tr>`).join("")}</tbody></table></div></div>
        <div class="row" style="margin-top:18px"><button class="btn primary" data-go="step:export">Export →</button></div>`;
      toast("Cell types compared.", true);
    });
  }

  // ---------------------------------------------------------------- export
  async function exportView(el) {
    el.innerHTML = lede("Save the tables. Everything goes in the run's results folder.") +
      `<div class="card"><div class="label">What you get</div><ul class="small">
        <li><b>cell_abundance_mean.csv</b> and <b>cell_abundance_q05.csv</b>: estimated cells of each type in every spot (mean, and a cautious 5% quantile).</li>
        <li><b>cell_type_shares.csv</b>: each type's share of every spot.</li>
        <li><b>main_cell_type.csv</b>: the main type in every spot, its share and the spot's estimated cells.</li>
        <li><b>cell_types_together.csv</b>: the correlation between cell types (after Which cell types live together).</li></ul>
        <p class="small muted">cell2location's full output, with every posterior summary, is <code>results/cell2location/spots.h5ad</code> (real runs only).</p>
        <div class="row" style="margin-top:12px"><button class="btn primary" id="go">Export</button></div><div id="files"></div></div>`;
    $("#go", el).onclick = e => guarded(e.currentTarget, async () => { await E.call("export"); await filesTable($("#files", el)); toast("Tables saved.", true); });
    filesTable($("#files", el));
  }

  E.registerViews("spatial.deconvolution", { report, overview: overviewView, tissue, together, export: exportView });
})();
