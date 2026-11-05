/* Views for RNA abundance: sample checks, gene look-up and most expressed genes, expression patterns, export.
   Uses only Everyome's shared helpers, so every chart follows the active theme. */
"use strict";
(() => {
  const E = window.Everyome, H = E.helpers;
  const { $, $$, esc, fmt, toast, guarded, followTask, guide, scatter, legend, lede, filesTable } = H;
  const COL = () => H.COL(), PAL = () => H.PALETTE();
  let st = null;
  const refresh = async () => (st = await E.status());
  const groupColour = g => PAL()[st.groups.indexOf(g) % PAL().length];
  const chip = g => `<span class="chip" style="cursor:inherit"><i style="background:${groupColour(g)}"></i>${esc(g)}</span>`;

  // A heatmap in SVG: rows × columns of values, coloured from `lo` to `hi` (diverging around 0 when `diverge`).
  function heatmap(rows, cols, values, { lo, hi, diverge = false, cell = 30, rowH = null, left = 110, top = 90, rowLabels = true, rowColors = null, label = "" } = {}) {
    const c = COL(), rh = rowH || cell, a = H.hexRgb(c.parch), neg = H.hexRgb(c.plum || c.ink), pos = H.hexRgb(c.ox);
    const mix = (from, to, t) => `rgb(${from.map((v, i) => Math.round(v + (to[i] - v) * Math.max(0, Math.min(1, t))))})`;
    const colour = v => diverge ? (v >= 0 ? mix(a, pos, v / hi) : mix(a, neg, v / lo)) : mix(a, pos, (v - lo) / ((hi - lo) || 1));
    const w = left + cols.length * cell + 20, h = top + rows.length * rh + 10;
    let s = `<svg class="chart" style="min-width:${w}px;max-width:${w}px" viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(label)}">`;
    cols.forEach((t, j) => s += `<text transform="translate(${left + j * cell + cell / 2 + 4},${top - 6}) rotate(-55)" class="ax">${esc(t)}</text>`);
    rows.forEach((r, i) => {
      if (rowLabels) s += `<text x="${left - 6}" y="${top + i * rh + rh / 2 + 4}" text-anchor="end" class="ax">${esc(r)}</text>`;
      if (rowColors) s += `<rect x="${left - 12}" y="${top + i * rh}" width="8" height="${rh}" fill="${rowColors[i]}"/>`;
      values[i].forEach((v, j) => s += `<rect x="${left + j * cell}" y="${top + i * rh}" width="${cell - 1}" height="${Math.max(1, rh - (rh > 4 ? 1 : 0))}" fill="${colour(v)}"><title>${esc(r)} · ${esc(cols[j])}: ${v}</title></rect>`);
    });
    return s + "</svg>";
  }

  // ---------------------------------------------------------------- samples
  async function samples(el) {
    await refresh();
    const o = await E.call("overview"), p = await E.call("sample_qc");
    el.innerHTML = lede("First, check the samples. Samples of one group should look alike; one that doesn't may be mislabelled or failed.") +
      (o.missing.length ? `<div class="notice warn">These samples are in your table but not in the pipeline's TPM table: ${o.missing.map(esc).join(", ")}.</div>` : "") +
      `<div class="grid g2"><div class="card"><div class="label">Samples</div><table><thead><tr><th>Sample</th><th>Group</th><th class="num">Genes detected</th><th class="num">Top 10 genes' share</th></tr></thead><tbody>
        ${o.samples.map(s => `<tr><td>${esc(s.sample)}</td><td>${chip(s.group)}</td><td class="num">${fmt(s.detected)}</td><td class="num">${s.top10_share}%</td></tr>`).join("")}</tbody></table>
        <p class="small muted" style="margin-top:8px">${fmt(o.genes)} genes in <code>${esc(o.tpm_file.split("/").slice(-2).join("/"))}</code>. Samples are compared on ${esc(o.normalised)}.</p>${guide("samples")}</div>
      <div class="card"><div class="label">Principal components (${p.n_genes} most variable genes)</div>
        ${scatter(p.samples.map((s, i) => ({ x: p.pc1[i], y: p.pc2[i], c: groupColour(p.groups[i]), r: 6, t: `${s} (${p.groups[i]})` })),
          { xlab: `PC1 (${p.var[0]}%)`, ylab: `PC2 (${p.var[1] ?? 0}%)`, h: 300, label: "Principal component plot of samples" })}
        ${legend(st.groups.map(g => [g, groupColour(g)]))}${guide("pca", { open: true })}</div></div>
      <div class="card" style="margin-top:18px"><div class="label">Sample correlation</div><div style="overflow:auto">
        ${heatmap(p.samples, p.samples, p.corr, { lo: Math.min(...p.corr.flat()), hi: 1, label: "Sample correlation heatmap" })}</div>
        <p class="small muted">Darker means more alike.</p>${guide("correlation")}</div>
      <div class="row" style="margin-top:18px"><button class="btn primary" data-go="step:genes">Look up genes →</button></div>`;
  }

  // ---------------------------------------------------------------- genes
  async function genes(el) {
    await refresh();
    el.innerHTML = lede("Look up any gene's expression in every sample, or start from the most expressed genes.") +
      `<div class="grid g-side"><div class="card"><div class="label">One gene</div>
          <div class="row"><input type="text" id="q" placeholder="Gene name or ID" style="flex:1"><button class="btn primary" id="find">Show</button></div>
          <div id="gene" style="margin-top:12px"><p class="small muted">Type a name, or click a gene in the list.</p></div>${guide("tpm")}</div>
        <div class="card"><div class="label">Most expressed genes</div><div id="top" style="max-height:520px;overflow:auto"></div>${guide("top_genes")}</div></div>
      <div class="row" style="margin-top:18px"><button class="btn primary" data-go="step:patterns">Find patterns →</button></div>`;
    const show = async q => {
      const r = await E.call("gene", { q });
      if (r.choices) {
        $("#gene", el).innerHTML = `<p class="small">Several genes match; choose one:</p><div class="row" style="flex-wrap:wrap">${r.choices.map(c => `<button class="btn small" data-q="${esc(c.id)}">${esc(c.label)}</button>`).join("")}</div>`;
        return;
      }
      const max = Math.max(...r.values.map(v => v.tpm), 1);
      $("#gene", el).innerHTML = `<div class="label">${esc(r.label)}</div>` + H.barChart(r.values.map(v => [v.sample, v.tpm]),
        { label: v => fmt(v) + " TPM", title: `${r.label}: TPM in each sample`, colors: r.values.map(v => groupColour(v.group)), h: 30 * r.values.length }) +
        legend(st.groups.map(g => [g, groupColour(g)]));
    };
    $("#find", el).onclick = e => guarded(e.currentTarget, () => show($("#q", el).value));
    $("#q", el).onkeydown = e => { if (e.key === "Enter") $("#find", el).click(); };
    el.addEventListener("click", e => { const b = e.target.closest("[data-q]"); if (b) { $("#q", el).value = b.dataset.q; show(b.dataset.q).catch(err => toast(err.message)); } });
    const top = await E.call("top_genes", { n: 40 });
    $("#top", el).innerHTML = `<table><thead><tr><th>Gene</th><th class="num">Mean TPM</th>${st.groups.map(g => `<th class="num">${esc(g)}</th>`).join("")}</tr></thead><tbody>
      ${top.map(t => `<tr class="click" tabindex="0" data-q="${esc(t.id)}"><td>${esc(t.label)}</td><td class="num">${fmt(t.mean_tpm)}</td>${st.groups.map(g => `<td class="num">${fmt(t.by_group[g])}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
  }

  // ---------------------------------------------------------------- patterns
  async function patterns(el) {
    await refresh();
    const prev = st.patterns || {};
    el.innerHTML = lede("Group the most variable genes by how they rise and fall across your samples. Genes in one cluster are co-expressed here.") +
      `<div class="card"><div class="grid g3">
          <label class="field"><span>Most variable genes to use</span><input type="number" id="n" min="50" max="5000" step="50" value="${prev.n_genes || 500}"></label>
          <label class="field"><span>Clusters</span><input type="number" id="k" min="2" max="12" value="${prev.k || 4}"><small>Try a few values.</small></label>
          <label class="field"><span>Leave out genes below (TPM)</span><input type="number" id="t" min="0" step="0.5" value="${prev.min_tpm ?? 1}"><small>In every sample.</small></label></div>
        <div class="row"><button class="btn primary" id="go">${prev.k ? "Cluster again" : "Find patterns"}</button></div></div>
      <div id="out"></div>`;
    const draw = r => {
      const k = r.k, cols = r.samples, P = PAL();
      const w = 560, h = 240, L = 40, B = 30, X = j => L + j * (w - L - 10) / Math.max(1, cols.length - 1);
      const zs = r.profiles.flat(), lo = Math.min(-1.5, ...zs), hi = Math.max(1.5, ...zs), Y = v => 10 + (hi - v) / (hi - lo) * (h - B - 10);
      let prof = `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="Average pattern of each cluster"><line x1="${L}" x2="${w - 10}" y1="${Y(0)}" y2="${Y(0)}" stroke="${COL().muted}" stroke-dasharray="3 3"/>`;
      r.profiles.forEach((p, j) => prof += `<polyline fill="none" stroke="${P[j % P.length]}" stroke-width="2.5" points="${p.map((v, i) => `${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join(" ")}"><title>Cluster ${j + 1}</title></polyline>`);
      cols.forEach((c, i) => prof += `<text transform="translate(${X(i) + 4},${h - B + 12}) rotate(-35)" class="ax">${esc(c)}</text>`);
      prof += `<text x="12" y="${h / 2}" transform="rotate(-90 12 ${h / 2})" text-anchor="middle" class="ax">z-score</text></svg>`;
      const rowH = Math.max(2, Math.min(10, 600 / r.heat.genes.length));
      $("#out", el).innerHTML = `<div class="grid g2" style="margin-top:18px"><div class="card"><div class="label">${fmt(r.n_genes)} genes in ${k} clusters</div><div style="overflow:auto">
          ${heatmap(r.heat.genes, cols, r.heat.z, { lo: -2.5, hi: 2.5, diverge: true, rowH, cell: 26, left: 18, rowLabels: false, rowColors: r.heat.cluster.map(j => P[(j - 1) % P.length]), label: "Heatmap of gene patterns" })}</div>
          ${legend([["above the gene's average", COL().ox], ["below it", COL().plum || COL().ink]])}
          <p class="small muted">Rows are genes, sorted by cluster; the strip on the left shows each gene's cluster (${r.sizes.map((n, j) => `cluster ${j + 1}: ${n}`).join(", ")}).</p>${guide("patterns", { open: true })}</div>
        <div class="card"><div class="label">Each cluster's average pattern</div>${prof}${legend(r.profiles.map((_, j) => [`Cluster ${j + 1} (${r.sizes[j]} genes)`, P[j % P.length]]))}
          ${r.members.map((m, j) => `<p class="small"><b>Cluster ${j + 1}:</b> ${m.map(esc).join(", ")}${r.sizes[j] > m.length ? "…" : ""}</p>`).join("")}${guide("clusters")}</div></div>
        <div class="row" style="margin-top:18px"><button class="btn primary" data-go="step:export">Export →</button></div>`;
    };
    $("#go", el).onclick = e => guarded(e.currentTarget, async () => {
      draw(await E.call("patterns", { n_genes: Number($("#n", el).value), k: Number($("#k", el).value), min_tpm: Number($("#t", el).value) }));
      await refresh(); toast("Patterns found.", true);
    });
    if (prev.k) draw(await E.call("patterns", { n_genes: prev.n_genes, k: prev.k, min_tpm: prev.min_tpm }));
  }

  // ---------------------------------------------------------------- export
  async function exportView(el) {
    el.innerHTML = lede("Save the tables for your own analysis or a paper's supplement. Everything goes in the run's results folder.") +
      `<div class="card"><div class="label">What you get</div><ul class="small">
        <li><b>tpm.csv</b>: TPM of every gene in every sample, with gene names.</li>
        <li><b>normalised_log2.csv</b>: the normalised, log-scaled values the sample checks and patterns use.</li>
        <li><b>samples.csv</b>: each sample's group.</li>
        <li><b>gene_clusters.csv</b>: each clustered gene's cluster (after Find patterns).</li></ul>
        <div class="row" style="margin-top:12px"><button class="btn primary" id="go">Export</button></div><div id="files"></div></div>`;
    $("#go", el).onclick = e => guarded(e.currentTarget, async () => { await E.call("export"); await filesTable($("#files", el)); toast("Tables saved.", true); });
    filesTable($("#files", el));
  }

  E.registerViews("rna.abundance", { samples, genes, patterns, export: exportView });
})();
