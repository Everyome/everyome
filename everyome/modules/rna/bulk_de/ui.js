/* Views for bulk RNA-seq differential expression: pipeline report, sample checks, DESeq2 comparison, results, export.
   Uses only Everyome's shared helpers, so every chart follows the active theme. */
"use strict";
(() => {
  const E = window.Everyome, H = E.helpers;
  const { $, $$, esc, fmt, fmtSize, toast, guarded, followTask, barChart } = H;
  const COL = () => H.COL(), PAL = () => H.PALETTE();
  const S = { an: null, padj: 0.05, lfc: 0 };
  const refresh = async () => (S.an = await E.status());
  const lede = t => `<p class="lede">${t}</p>`;
  const condColour = (conds, c) => PAL()[conds.indexOf(c) % PAL().length];

  // Scatter plot in SVG with axes; points = [{x, y, c, t}] (colour, tooltip).
  function scatter(points, { w = 560, h = 360, xlab = "", ylab = "", r = 2.2, lines = [], label = "" } = {}) {
    const c = COL(), L = 48, B = 36, T = 10, R = 12;
    const xs = points.map(p => p.x), ys = points.map(p => p.y);
    const x0 = Math.min(...xs, ...lines.filter(l => l.x != null).map(l => l.x)), x1 = Math.max(...xs, ...lines.filter(l => l.x != null).map(l => l.x));
    const y0 = Math.min(0, ...ys), y1 = Math.max(...ys, ...lines.filter(l => l.y != null).map(l => l.y));
    const pad = v => v === 0 ? 1 : Math.abs(v) * 0.05;
    const X = v => L + (v - (x0 - pad(x1 - x0))) / ((x1 - x0) + 2 * pad(x1 - x0) || 1) * (w - L - R);
    const Y = v => h - B - (v - y0) / ((y1 - y0) * 1.05 || 1) * (h - B - T);
    const ticks = (a, b) => { const st = Math.pow(10, Math.floor(Math.log10((b - a) / 4 || 1))), k = Math.ceil((b - a) / st / 5) * st || 1; const out = []; for (let v = Math.ceil(a / k) * k; v <= b; v += k) out.push(+v.toFixed(6)); return out; };
    let s = `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(label || ylab + " against " + xlab)}">`;
    ticks(x0, x1).forEach(v => s += `<text x="${X(v)}" y="${h - B + 15}" text-anchor="middle" class="ax">${v}</text>`);
    ticks(y0, y1).forEach(v => s += `<text x="${L - 6}" y="${Y(v) + 4}" text-anchor="end" class="ax">${v}</text>`);
    s += `<line x1="${L}" x2="${w - R}" y1="${h - B}" y2="${h - B}" stroke="${c.muted}"/><line x1="${L}" x2="${L}" y1="${T}" y2="${h - B}" stroke="${c.muted}"/>`;
    lines.forEach(l => s += l.x != null ? `<line x1="${X(l.x)}" x2="${X(l.x)}" y1="${T}" y2="${h - B}" stroke="${c.ox}" stroke-dasharray="4 3"/>`
      : `<line x1="${L}" x2="${w - R}" y1="${Y(l.y)}" y2="${Y(l.y)}" stroke="${c.ox}" stroke-dasharray="4 3"/>`);
    points.forEach(p => s += `<circle cx="${X(p.x).toFixed(1)}" cy="${Y(p.y).toFixed(1)}" r="${p.r || r}" fill="${p.c}" ${p.g ? `data-g="${esc(p.g)}" style="cursor:pointer"` : ""}>${p.t ? `<title>${esc(p.t)}</title>` : ""}</circle>`);
    return s + `<text x="${(w + L) / 2}" y="${h - 4}" text-anchor="middle" class="ax">${esc(xlab)}</text><text x="12" y="${h / 2}" transform="rotate(-90 12 ${h / 2})" text-anchor="middle" class="ax">${esc(ylab)}</text></svg>`;
  }
  const legend = items => `<div class="legend">${items.map(([t, col]) => `<span><i style="background:${col}"></i>${esc(t)}</span>`).join("")}</div>`;

  // ---------------------------------------------------------------- pipeline report (Run page)
  async function report(el, q) {
    const st = E.state();
    el.innerHTML = `<h2>What the pipeline made</h2>
      <div class="grid g2"><div class="card"><div class="label">Gene counts</div>
        ${q.counts ? `<p class="small">Table: <code>${esc(q.counts)}</code><br>${fmt(q.genes)} genes × ${q.samples.length} samples.</p>
          ${barChart(q.samples.map(s => [s.sample, s.reads]), { label: v => (v / 1e6).toFixed(2) + " M", title: "Reads counted per sample" })}
          <p class="small muted">Samples should have broadly similar totals; one far below the rest may have failed.</p>`
          : `<div class="notice warn">No gene count table was found. Check the pipeline log; the live session needs this table.</div>`}</div>
      <div class="card"><div class="label">Quality report</div>
        ${q.multiqc ? `<p class="small">nf-core/rnaseq's MultiQC report brings together every quality check: read quality, trimming, alignment rates, strandedness and more.</p>
          <a class="btn primary small" href="/api/run/file?path=${encodeURIComponent(q.multiqc)}" target="_blank" rel="noopener">Open the MultiQC report</a>`
          : `<p class="small muted">No MultiQC report found.</p>`}
        ${st.demo ? `<p class="small muted" style="margin-top:10px">On the demo cluster this is a placeholder.</p>` : ""}</div></div>`;
  }

  // ---------------------------------------------------------------- check samples
  async function qc(el) {
    await refresh();
    const o = await E.call("overview"), p = await E.call("sample_qc"), c = COL(), conds = S.an.conditions;
    el.innerHTML = lede("Before comparing, check the samples. Replicates of the same condition should look alike and sit close together.") +
      (o.missing.length ? `<div class="notice warn">These samples are in your table but not in the count table (the pipeline may have dropped them for too few reads): ${o.missing.map(esc).join(", ")}.</div>` : "") +
      `<div class="grid g2"><div class="card"><div class="label">Samples</div><table><thead><tr><th>Sample</th><th>Condition</th><th class="num">Reads counted</th><th class="num">Genes detected</th></tr></thead><tbody>
        ${o.samples.map(s => `<tr><td>${esc(s.sample)}</td><td><span class="chip" style="cursor:inherit"><i style="background:${condColour(conds, s.condition)}"></i>${esc(s.condition)}</span></td><td class="num">${fmt(s.reads)}</td><td class="num">${fmt(s.genes)}</td></tr>`).join("")}</tbody></table>
        <p class="small muted" style="margin-top:8px">${fmt(o.genes)} genes in <code>${esc(o.counts_file)}</code>.</p></div>
      <div class="card"><div class="label">Principal components (${p.n_genes} most variable genes)</div>
        ${scatter(p.samples.map((s, i) => ({ x: p.pc1[i], y: p.pc2[i], c: condColour(conds, p.conditions[i]), r: 6, t: `${s} (${p.conditions[i]})` })),
          { xlab: `PC1 (${p.var[0]}%)`, ylab: `PC2 (${p.var[1] ?? 0}%)`, h: 300, label: "Principal component plot of samples" })}
        ${legend(conds.map(k => [k, condColour(conds, k)]))}
        <p class="small muted">Samples of one condition should group. A sample on its own may be mislabelled or failed.</p></div></div>
      <div class="card" style="margin-top:18px"><div class="label">Sample correlation</div><div id="heat" style="overflow:auto"></div>
        <p class="small muted">Correlation of normalised, log-scaled counts. Darker means more alike; replicates should be darkest with each other.</p></div>
      <div class="row" style="margin-top:18px"><button class="btn primary" data-go="step:de">Compare conditions →</button></div>`;
    const n = p.samples.length, cw = 34, left = 110, top = 100, mix = t => { const a = H.hexRgb(c.parch), b = H.hexRgb(c.ox); return `rgb(${a.map((v, i) => Math.round(v + (b[i] - v) * t))})`; };
    const lo = Math.min(...p.corr.flat()), hi = 1;
    let svg = `<svg class="chart" style="min-width:${left + n * cw + 20}px;max-width:${left + n * cw + 20}px" viewBox="0 0 ${left + n * cw + 20} ${top + n * cw + 10}" role="img" aria-label="Sample correlation heatmap">`;
    p.samples.forEach((s, j) => svg += `<text transform="translate(${left + j * cw + cw / 2 + 4},${top - 6}) rotate(-55)" class="ax">${esc(s)}</text>`);
    p.samples.forEach((s, i) => { svg += `<text x="${left - 6}" y="${top + i * cw + cw / 2 + 4}" text-anchor="end" class="ax">${esc(s)}</text>`;
      p.corr[i].forEach((v, j) => svg += `<rect x="${left + j * cw}" y="${top + i * cw}" width="${cw - 1}" height="${cw - 1}" fill="${mix((v - lo) / ((hi - lo) || 1))}"><title>${esc(s)} · ${esc(p.samples[j])}: ${v}</title></rect>`); });
    $("#heat", el).innerHTML = svg + "</svg>";
  }

  // ---------------------------------------------------------------- compare
  async function de(el) {
    await refresh();
    const conds = S.an.conditions, prev = S.an.de || {};
    const ref = prev.reference || conds.find(c => /control|ctrl|wt|wild|untreated|mock/i.test(c)) || conds[0];
    const test = prev.test || conds.find(c => c !== ref) || conds[0];
    el.innerHTML = lede("Choose what to compare. DESeq2 estimates each gene's variation from the replicates and tests whether it differs between the two conditions.") +
      (conds.length < 2 ? `<div class="notice warn">Only one condition is in the samples table, so there is nothing to compare. Start a new run with conditions filled in.</div>` : "") +
      `<div class="grid g-side"><div class="card"><div class="label">Comparison</div><div class="grid g2">
          <label class="field"><span>Condition to test</span><select id="test">${conds.map(c => `<option ${c === test ? "selected" : ""}>${esc(c)}</option>`).join("")}</select><small>Fold changes are this condition relative to the reference.</small></label>
          <label class="field"><span>Reference</span><select id="ref">${conds.map(c => `<option ${c === ref ? "selected" : ""}>${esc(c)}</option>`).join("")}</select><small>Usually the control.</small></label>
          <label class="field"><span>Significance threshold (adjusted P)</span><input type="number" id="alpha" step="0.01" min="0.001" max="0.5" value="${prev.alpha ?? 0.05}"><small>Also used to tune DESeq2's independent filtering.</small></label>
          <label class="field"><span>Minimum total count</span><input type="number" id="minc" min="0" value="${prev.min_count ?? 10}"><small>Genes with fewer reads than this across the compared samples are left out.</small></label></div>
        <div class="row" style="margin-top:6px"><button class="btn primary" id="run">${prev.test ? "Compare again" : "Compare"}</button></div><div id="prog"></div></div>
        <div class="card"><div class="label">Result</div><div id="sum">${prev.test ? summary(prev) : '<p class="small muted">Not compared yet.</p>'}</div></div></div>`;
    $("#run", el).onclick = e => guarded(e.currentTarget, async () => {
      await E.call("run_de", { test: $("#test", el).value, reference: $("#ref", el).value, alpha: Number($("#alpha", el).value), min_count: Number($("#minc", el).value) });
      await followTask($("#prog", el)); await refresh(); $("#sum", el).innerHTML = summary(S.an.de); toast("Comparison finished.", true);
    });
  }
  const summary = d => `<div class="metric"><span>Higher in ${esc(d.test)}</span><b>${fmt(d.up)}</b></div><div class="metric"><span>Lower in ${esc(d.test)}</span><b>${fmt(d.down)}</b></div>
    <div class="metric"><span>Genes tested</span><b>${fmt(d.genes_tested)}</b></div><p class="small muted">At adjusted P below ${d.alpha}, ${esc(d.test)} against ${esc(d.reference)}.</p>
    <div class="row" style="margin-top:10px"><button class="btn primary" data-go="step:results">Explore results →</button></div>`;

  // ---------------------------------------------------------------- explore
  async function results(el) {
    await refresh();
    if (!S.an.de) { el.innerHTML = `<div class="empty">Compare conditions first.</div>`; return; }
    const d = S.an.de;
    el.innerHTML = lede(`${esc(d.test)} compared with ${esc(d.reference)}. Click a gene in the plot or table to see its counts in each sample.`) +
      `<div class="card"><div class="row"><label class="small">Adjusted P below <input type="number" id="padj" step="0.01" min="0.0001" max="1" value="${S.padj}" style="width:90px"></label>
        <label class="small">and |log2 fold change| at least <input type="number" id="lfc" step="0.1" min="0" value="${S.lfc}" style="width:80px"></label><span id="counts" class="small"></span></div></div>
      <div class="grid g2" style="margin-top:18px"><div class="card"><div class="label">Volcano plot</div><div id="vol"></div></div>
        <div class="card"><div class="label">MA plot</div><div id="ma"></div><p class="small muted">Fold change against average expression. Large changes at low expression are often noise.</p></div></div>
      <div class="grid g-side" style="margin-top:18px"><div class="card"><div class="row" style="justify-content:space-between"><div class="label">Genes</div>
          <input type="text" id="q" placeholder="Search a gene…" style="width:200px" aria-label="Search a gene"></div><div id="tbl"></div></div>
        <div class="card"><div class="label" id="gt">Gene</div><div id="gene"><p class="small muted">Click a gene.</p></div></div></div>`;
    const c = COL();
    async function draw() {
      S.padj = Number($("#padj", el).value) || 0.05; S.lfc = Number($("#lfc", el).value) || 0;
      const [v, m] = await Promise.all([E.call("volcano", { padj: S.padj, lfc: S.lfc }), E.call("ma", { padj: S.padj })]);
      const col = s => s > 0 ? c.ox : s < 0 ? c.plum : c.rule;
      $("#vol", el).innerHTML = scatter(v.x.map((x, i) => ({ x, y: v.y[i], c: col(v.sig[i]), g: v.sig[i] ? v.gene[i] : null, t: v.sig[i] ? `${v.name[i]} (${v.gene[i]})` : "" })),
        { xlab: `log2 fold change (${d.test} vs ${d.reference})`, ylab: "−log10 adjusted P", lines: [{ y: -Math.log10(S.padj) }, ...(S.lfc ? [{ x: S.lfc }, { x: -S.lfc }] : [])], label: "Volcano plot" }) +
        legend([[`higher in ${d.test}`, c.ox], [`lower in ${d.test}`, c.plum], ["not significant", c.rule]]);
      $("#ma", el).innerHTML = scatter(m.x.map((x, i) => ({ x, y: m.y[i], c: m.sig[i] ? c.ox : c.rule, r: 1.6 })), { xlab: "log10 mean normalised count", ylab: "log2 fold change", lines: [{ y: 0 }], label: "MA plot" });
      await table();
    }
    async function table() {
      const r = await E.call("results", { padj: S.padj, lfc: S.lfc, q: $("#q", el).value.trim(), n: 200 });
      $("#counts", el).innerHTML = ` → <b>${fmt(r.up)}</b> higher, <b>${fmt(r.down)}</b> lower`;
      $("#tbl", el).innerHTML = r.rows.length ? `<table><thead><tr><th>Gene</th><th>ID</th><th class="num">Mean count</th><th class="num">log2 FC</th><th class="num">Adjusted P</th></tr></thead><tbody>
        ${r.rows.map(g => `<tr class="click" tabindex="0" data-g="${esc(g.gene)}"><td>${esc(g.name)}</td><td class="mono small">${esc(g.gene)}</td><td class="num">${fmt(g.base_mean)}</td><td class="num">${g.lfc}</td><td class="num">${g.padj == null ? "–" : g.padj.toExponential(2)}</td></tr>`).join("")}</tbody></table>
        ${r.rows.length >= 200 ? `<p class="small muted">Showing the first 200; export to get them all.</p>` : ""}` : `<p class="small muted">No genes pass these thresholds${$("#q", el).value ? " or match the search" : ""}.</p>`;
    }
    async function gene(g) {
      const r = await E.call("gene", { gene: g }), conds = S.an.conditions;
      $("#gt", el).textContent = `${r.name} (${r.gene})`;
      const order = [...new Set(r.values.map(v => v.condition))];
      $("#gene", el).innerHTML = scatter(r.values.map(v => ({ x: order.indexOf(v.condition) + 1 + (Math.random() - .5) * .25, y: v.count, c: condColour(conds, v.condition), r: 5, t: `${v.sample}: ${v.count}` })),
        { w: 320, h: 260, xlab: order.join("  ·  "), ylab: "normalised count", label: `Counts of ${r.name}` }) + legend(order.map(k => [k, condColour(conds, k)]));
    }
    el.addEventListener("click", e => { const t = e.target.closest("[data-g]"); if (t) gene(t.dataset.g); });
    el.addEventListener("keydown", e => { if (e.key === "Enter" && e.target.dataset.g) gene(e.target.dataset.g); });
    ["#padj", "#lfc"].forEach(id => $(id, el).addEventListener("change", () => guarded(null, draw)));
    let tq; $("#q", el).addEventListener("input", () => { clearTimeout(tq); tq = setTimeout(() => guarded(null, table), 250); });
    await draw();
  }

  // ---------------------------------------------------------------- export
  async function exportView(el) {
    await refresh();
    if (!S.an.de) { el.innerHTML = `<div class="empty">Compare conditions first.</div>`; return; }
    el.innerHTML = lede("Save the results in the run folder, to use in other tools or a paper. Then build the record for the protocol and methods.") +
      `<div class="card"><div class="row"><label class="small">Significant means adjusted P below <input type="number" id="padj" step="0.01" value="${S.padj}" style="width:90px"></label>
        <label class="small">and |log2 fold change| at least <input type="number" id="lfc" step="0.1" min="0" value="${S.lfc}" style="width:80px"></label>
        <button class="btn primary" id="exp">Export results</button></div><div id="eprog"></div><div id="files"></div>
        <p class="small muted" style="margin-top:10px">Writes all genes, the significant genes, normalised counts and a volcano plot to <code>${esc(E.state().run.dir)}/results/differential_expression</code>.</p></div>
      <div class="row" style="margin-top:18px"><button class="btn" data-go="record">Record and write-up →</button></div>`;
    async function files() {
      const f = await E.call("files");
      $("#files", el).innerHTML = f.length ? `<table style="margin-top:14px"><thead><tr><th>File</th><th class="num">Size</th><th></th></tr></thead><tbody>${f.map(x =>
        `<tr><td class="mono small">${esc(x.name)}</td><td class="num small">${fmtSize(x.size)}</td><td class="num"><a class="btn small" href="${E.downloadUrl(x.name)}" download>Download</a></td></tr>`).join("")}</tbody></table>` : "";
    }
    $("#exp", el).onclick = e => guarded(e.currentTarget, async () => {
      S.padj = Number($("#padj", el).value); S.lfc = Number($("#lfc", el).value);
      await E.call("export", { padj: S.padj, lfc: S.lfc }); await followTask($("#eprog", el)); await files(); toast("Results exported.", true);
    });
    files();
  }

  E.registerViews("rna.bulk_de", { report, qc, de, results, export: exportView });
})();
