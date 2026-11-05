/* Views for single-cell ATAC-seq: what the cluster stage made (Run page) and reading the fragments. Filtering,
   clustering, markers, naming and export are the shared single-cell views (../shared/cells_ui.js), told to talk
   about fragments and TSS enrichment instead of UMIs and genes. */
"use strict";
(() => {
  const E = window.Everyome, H = E.helpers, { $, esc, fmt, fmtSize, toast, guarded, followTask, guide, lede, legend } = H;
  const { S, refresh, reached, views } = E.cells({ order: ["loaded", "filtered", "clustered", "exported"], words: {
    count: "Fragments", feature: "TSS enrichment", featureLow: "TSS enrichment", hvg: "Variable regions (×25 tiles)", pcs: "Spectral components",
    qc: "Remove barcodes that are not real cells: too few fragments, or low TSS enrichment (little signal at gene starts). " +
        "Move the thresholds and watch how many cells each sample keeps.",
    qcNote: "Barcodes with very many fragments may be two cells captured together." } });

  // ---------------------------------------------------------------- after the cluster stage (Run page)
  async function report(el, q) {
    el.innerHTML = `<h2>What the cluster stage made</h2><div class="card"><div class="label">Fragments per sample</div>
      <table><thead><tr><th>Sample</th><th>File</th><th class="num">Size</th></tr></thead><tbody>${q.fragments.map(f =>
        `<tr><td>${esc(f.sample)}</td><td><code class="small" style="word-break:break-all">${esc(f.path)}</code></td><td class="num">${f.size != null ? fmtSize(f.size) : "missing"}</td></tr>`).join("")}</tbody></table>
      ${E.state().demo ? `<p class="small muted" style="margin-top:8px">On the demo cluster, a quick stand-in replaces chromap.</p>` : ""}${guide("run_report")}</div>`;
  }

  // Fragment size histogram, one line per sample, on a log scale (the nucleosome ladder shows as bumps).
  function sizes(d) {
    const C = H.COL(), P = H.PALETTE(), names = Object.keys(d);
    if (!names.length) return "";
    const w = 560, h = 240, L = 46, B = 30, max = 800, X = x => L + x / max * (w - L - 10);
    const norm = names.map(n => { const v = d[n].slice(0, max + 1), s = v.reduce((a, b) => a + b, 0) || 1; return v.map(x => x / s); });
    const top = Math.max(...norm.flat(), 1e-6), Y = v => h - B - Math.log10(1 + 1e4 * v) / Math.log10(1 + 1e4 * top) * (h - B - 10);
    let s = `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="Fragment size distribution">`;
    norm.forEach((v, i) => s += `<polyline fill="none" stroke="${P[i % P.length]}" stroke-width="1.6" points="${v.map((y, x) => `${X(x).toFixed(1)},${Y(y).toFixed(1)}`).join(" ")}"/>`);
    [147, 294].forEach(x => s += `<line x1="${X(x)}" x2="${X(x)}" y1="10" y2="${h - B}" stroke="${C.muted}" stroke-dasharray="3 3"/>`);
    for (let x = 0; x <= max; x += 200) s += `<text x="${X(x)}" y="${h - B + 15}" text-anchor="middle" class="ax">${x}</text>`;
    s += `<text x="${(w + L) / 2}" y="${h - 4}" text-anchor="middle" class="ax">fragment length (bp); dashed: one and two nucleosomes</text>`;
    return s + "</svg>" + legend(names.map((n, i) => [n, P[i % P.length]]));
  }

  // ---------------------------------------------------------------- read the fragments
  async function load(el) {
    await refresh();
    const done = S.an.loaded_from || {};
    el.innerHTML = lede("Read each sample's fragments. Every barcode with enough fragments becomes a cell, with its TSS enrichment and fragment sizes.") +
      `<div class="grid g-side"><div class="card"><div class="label">Settings</div>
          <label class="field"><span>Fewest fragments for a barcode to count as a cell</span><input type="number" id="minf" min="50" step="50" value="${done.min_fragments ?? 500}">
            <small>A first, loose cut; the next step sets the real thresholds.</small></label>
          <label class="field"><span>Tile size (bp)</span><input type="number" id="bin" min="200" max="5000" step="100" value="${done.bin_size ?? 500}">
            <small>Clustering uses open chromatin in tiles of this size.</small></label>
          ${guide("fragments")}<div class="row" style="margin-top:12px"><button class="btn primary" id="go">${reached("loaded") ? "Read again" : "Read the fragments"}</button></div><div id="lprog"></div></div>
        <div class="card"><div class="label">Cells per sample</div><div id="cps"><p class="small muted">Read the fragments to see each sample's cells.</p></div></div></div>
      <div class="card" style="margin-top:18px"><div class="label">Fragment sizes</div><div id="fs"><p class="small muted">After reading.</p></div>${guide("fragment_sizes")}</div>`;
    async function show() {
      if (!reached("loaded")) return;
      const l = S.an.loaded_from, s = await E.call("load_summary");
      $("#cps", el).innerHTML = `<p class="small">${fmt(l.cells)} cells, ${fmt(l.tiles)} tiles and ${fmt(l.genes)} genes.</p>
        <table><thead><tr><th>Sample</th><th class="num">Cells</th><th class="num">Median fragments</th><th class="num">Median TSS enrichment</th></tr></thead><tbody>
        ${s.samples.map(r => `<tr><td>${esc(r.sample)}</td><td class="num">${fmt(r.cells)}</td><td class="num">${fmt(r.median_fragments)}</td><td class="num">${r.median_tsse}</td></tr>`).join("")}</tbody></table>
        <div class="row" style="margin-top:12px"><button class="btn primary" data-go="step:qc">Continue to filtering →</button></div>`;
      $("#fs", el).innerHTML = sizes(s.frag_sizes);
    }
    $("#go", el).onclick = e => guarded(e.currentTarget, async () => {
      await E.call("load", { min_fragments: Number($("#minf", el).value), bin_size: Number($("#bin", el).value) });
      await followTask($("#lprog", el)); await refresh(); toast(`Read ${fmt(S.an.cells)} cells.`, true); show();
    });
    show();
  }

  E.registerViews("singlecell.scatac", { report, load, ...views });
})();
