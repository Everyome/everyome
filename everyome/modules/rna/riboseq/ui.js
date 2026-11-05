/* Views for Ribo-seq: pipeline report, periodicity checks, ORFs, translational efficiency, export.
   Uses only Everyome's shared helpers, so every chart follows the active theme. */
"use strict";
(() => {
  const E = window.Everyome, H = E.helpers;
  const { $, esc, fmt, toast, guarded, guide, scatter, legend, lede, filesTable, fileButton, barChart } = H;
  const COL = () => H.COL(), PAL = () => H.PALETTE();
  let st = null;
  const refresh = async () => (st = await E.status());
  const pct = v => (100 * v).toFixed(0) + "%";
  // Intent: frame 0 in the strong colour, the other two frames muted, so the rhythm reads at a glance.
  const frameCol = f => [COL().ox, COL().golddk, COL().rule][f];
  const classCol = c => ({ translation: COL().ox, buffering: COL().plum || COL().ink, "mRNA abundance": COL().golddk, unchanged: COL().rule })[c] || COL().muted;

  // Footprints at each position around the start or stop codon, each bar coloured by its reading frame.
  function metagene(prof, { anchor, label }) {
    const w = 560, h = 190, L = 40, B = 30, n = prof.x.length, max = Math.max(...prof.y, 1), bw = (w - L - 10) / n;
    let s = `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(label)}">`;
    prof.x.forEach((x, i) => {
      const f = ((x % 3) + 3) % 3, bh = prof.y[i] / max * (h - B - 10);
      s += `<rect x="${(L + i * bw).toFixed(1)}" y="${(h - B - bh).toFixed(1)}" width="${Math.max(1, bw - 0.6).toFixed(1)}" height="${bh.toFixed(1)}" fill="${frameCol(f)}"><title>${x} nt: ${prof.y[i]} (frame ${f})</title></rect>`;
      if (x % 12 === 0) s += `<text x="${(L + i * bw + bw / 2).toFixed(1)}" y="${h - B + 14}" text-anchor="middle" class="ax">${x}</text>`;
    });
    const z = prof.x.indexOf(0);
    if (z >= 0) s += `<line x1="${L + z * bw}" x2="${L + z * bw}" y1="6" y2="${h - B}" stroke="${COL().ink}" stroke-dasharray="3 3"/>`;
    return s + `<text x="${(w + L) / 2}" y="${h - 2}" text-anchor="middle" class="ax">P-site position from the ${esc(anchor)} (nt)</text></svg>`;
  }

  // ---------------------------------------------------------------- pipeline report (Run page)
  async function report(el, q) {
    const s = E.state(), libs = q.libraries || [], lens = Object.entries(q.lengths || {});
    const typeCol = t => ({ riboseq: COL().ox, rnaseq: COL().golddk, tiseq: COL().plum || COL().ink })[t] || COL().muted;
    el.innerHTML = `<h2>What the pipeline made</h2>
      <div class="grid g2"><div class="card"><div class="label">Counted per library</div>
        ${q.counts ? `<p class="small">Table: <code>${esc(q.counts)}</code><br>${fmt(q.genes)} genes × ${libs.length} libraries.</p>
          ${barChart(libs.map(l => [l.sample, l.counted]), { label: v => (v / 1e6).toFixed(2) + " M", title: "In-frame P-sites (Ribo-seq) or reads (RNA-seq) counted", colors: libs.map(l => typeCol(l.type)) })}
          ${legend([["Ribo-seq: in-frame P-sites", typeCol("riboseq")], ["RNA-seq: reads", typeCol("rnaseq")]])}`
          : `<div class="notice warn">No gene count table was found. Check the pipeline log; the live session needs this table.</div>`}</div>
      <div class="card"><div class="label">Footprint lengths</div>
        ${lens.length ? lens.slice(0, 1).map(([smp, d]) => barChart(Object.entries(d).map(([k, v]) => [k + " nt", v]), { label: v => v.toFixed(1) + "%", title: `Footprint lengths in ${smp}` })).join("") +
          `<p class="small muted">${esc(lens[0][0])}${lens.length > 1 ? ` (and ${lens.length - 1} more libraries in the session)` : ""}. Ribosome footprints are mostly 28–32 nt.</p>`
          : `<p class="small muted">No riboWaltz tables found.</p>`}
        ${q.orfs != null ? `<p class="small">${fmt(q.orfs)} ORFs in the ORF catalogue.</p>` : ""}
        <div class="row" style="margin-top:10px">${fileButton(q.multiqc, "Open the MultiQC report")}</div>
        ${s.demo ? `<p class="small muted" style="margin-top:10px">On the demo cluster the MultiQC report is a placeholder.</p>` : ""}</div></div>${guide("pipeline_report")}`;
  }

  // ---------------------------------------------------------------- periodicity
  async function qc(el) {
    await refresh();
    const p = await E.call("periodicity");
    if (!p.samples.length) { el.innerHTML = lede(esc(p.message)); return; }
    el.innerHTML = lede("First, check that the footprints come from translating ribosomes: they move three nucleotides at a time, so their P-sites should fall mostly in one reading frame.") +
      `<div class="grid g2"><div class="card"><div class="label">P-sites in frame 0, each library</div>
          ${barChart(p.summary.map(s => [s.sample, s.frame0 * 100]), { label: v => v.toFixed(0) + "%", title: "Share of coding P-sites in frame 0", colors: p.summary.map(s => s.frame0 >= 0.5 ? COL().ox : COL().rule) })}
          <p class="small muted">A third (33%) would mean no rhythm at all. Good libraries usually reach 50–80%.</p>${guide("frames", { open: true })}</div>
        <div class="card"><div class="label">One library</div><label class="field"><span>Library</span><select id="smp">${p.samples.map(s => `<option>${esc(s)}</option>`).join("")}</select></label><div id="lib"></div></div></div>
      <div class="card" style="margin-top:18px"><div class="label">Around the start and stop codons</div><div id="meta"></div>${guide("metagene")}</div>
      <div class="row" style="margin-top:18px"><button class="btn primary" data-go="step:orfs">Look at ORFs →</button></div>`;
    const draw = d => {
      $("#lib", el).innerHTML = `<p class="small">${fmt(d.reads)} footprints${d.capped ? " (the first 2 million)" : ""}; ${pct(d.regions.cds || 0)} in coding sequences.</p>
        <table><thead><tr><th class="num">Length</th><th class="num">Footprints</th><th class="num">P-site offset</th><th>Frames 0 · 1 · 2</th></tr></thead><tbody>
        ${d.by_length.map(b => `<tr><td class="num">${b.length} nt</td><td class="num">${fmt(b.reads)}</td><td class="num">${b.offset ?? "–"}</td>
          <td><span style="display:inline-flex;width:150px;height:12px">${b.frames.map((f, i) => `<i title="frame ${i}: ${pct(f)}" style="width:${f * 100}%;background:${frameCol(i)}"></i>`).join("")}</span> <span class="small muted">${pct(b.frames[0])}</span></td></tr>`).join("")}</tbody></table>
        ${legend([["frame 0", frameCol(0)], ["frame 1", frameCol(1)], ["frame 2", frameCol(2)]])}${guide("offsets")}`;
      $("#meta", el).innerHTML = `<div class="grid g2"><div>${metagene(d.start, { anchor: "start codon", label: "P-sites around the start codon" })}</div>
        <div>${metagene(d.stop, { anchor: "stop codon", label: "P-sites around the stop codon" })}</div></div>`;
    };
    draw(p.detail);
    $("#smp", el).onchange = async e => draw((await E.call("periodicity", { sample: e.target.value })).detail);
  }

  // ---------------------------------------------------------------- ORFs
  async function orfs(el) {
    await refresh();
    const first = await E.call("orfs", { n: 0 });
    const classes = Object.entries(first.classes);
    el.innerHTML = lede("The open reading frames being translated, from " + esc(first.source) + ". Beside each gene's main coding sequence there are often short ORFs upstream (uORFs) that can tune its translation.") +
      `<div class="grid g-side"><div class="card"><div class="label">${fmt(first.orfs)} ORFs by class</div>
          ${barChart(classes, { title: "ORFs in each class", colors: classes.map((_, i) => PAL()[i % PAL().length]) })}
          <table class="small" style="margin-top:8px"><thead><tr><th>Class</th><th class="num">Median length (amino acids)</th></tr></thead><tbody>
          ${classes.map(([k]) => `<tr><td>${esc(k)}</td><td class="num">${fmt(first.median_aa[k])}</td></tr>`).join("")}</tbody></table>${guide("orf_classes", { open: true })}</div>
        <div class="card"><div class="row"><select id="cls"><option value="">All classes</option>${classes.map(([k]) => `<option>${esc(k)}</option>`).join("")}</select>
          <input type="text" id="q" placeholder="Gene name or ID" style="flex:1"><button class="btn" id="go">Show</button></div>
          <div id="list" style="max-height:520px;overflow:auto;margin-top:10px"></div>${guide("orfs")}</div></div>
      <div class="row" style="margin-top:18px"><button class="btn primary" data-go="step:te">Compare translation →</button></div>`;
    const show = async () => {
      const r = await E.call("orfs", { cls: $("#cls", el).value, q: $("#q", el).value, n: 300 });
      $("#list", el).innerHTML = `<p class="small muted">${fmt(r.matching)} matching${r.matching > r.shown ? `, first ${fmt(r.shown)} shown` : ""}.</p>
        <table><thead><tr><th>ORF</th><th>Gene</th><th>Class</th><th class="num">Amino acids</th>${r.rows[0]?.chrom ? "<th>Position</th>" : ""}</tr></thead><tbody>
        ${r.rows.map(o => `<tr><td class="mono small">${esc(o.id)}</td><td>${esc(o.gene_name)}</td><td>${esc(o.class)}</td><td class="num">${fmt(o.aa)}</td>${o.chrom ? `<td class="mono small">${esc(o.chrom)}:${o.start}-${o.end} ${esc(o.strand || "")}</td>` : ""}</tr>`).join("")}</tbody></table>`;
    };
    $("#go", el).onclick = e => guarded(e.currentTarget, show);
    $("#cls", el).onchange = () => show().catch(err => toast(err.message));
    $("#q", el).onkeydown = e => { if (e.key === "Enter") $("#go", el).click(); };
    await show();
  }

  // ---------------------------------------------------------------- translational efficiency
  async function te(el) {
    await refresh();
    const prev = st.te || {}, conds = st.conditions;
    if (conds.length < 2) { el.innerHTML = lede("Translational efficiency compares two conditions; this run has Ribo-seq/RNA-seq pairs for only one. Check the Pair and Condition columns of the samples table."); return; }
    const opt = (sel) => conds.map(c => `<option${c === sel ? " selected" : ""}>${esc(c)}</option>`).join("");
    el.innerHTML = lede("Translational efficiency (TE) is footprints per mRNA. A gene can make more protein because it has more mRNA, or because each mRNA is translated more; comparing Ribo-seq with the matched RNA-seq tells the two apart.") +
      `<div class="card"><div class="grid g3">
          <label class="field"><span>Condition</span><select id="test">${opt(prev.test || conds[1])}</select></label>
          <label class="field"><span>Compared with (reference)</span><select id="ref">${opt(prev.reference || conds[0])}</select></label>
          <label class="field"><span>Minimum mean count</span><input type="number" id="min" min="0" step="1" value="${prev.min_count ?? 10}"><small>Footprints and reads, each.</small></label></div>
        <div class="row"><label class="field" style="max-width:220px"><span>Adjusted P below</span><input type="number" id="alpha" min="0.001" max="0.5" step="0.01" value="${prev.alpha ?? 0.05}"></label>
          <button class="btn primary" id="go">${prev.test ? "Compare again" : "Compare"}</button></div></div>
      <div id="out"></div>`;
    const draw = async () => {
      const r = await E.call("results", { n: 200 }), P = r.points;
      const pts = P.gene.map((g, i) => ({ x: P.rna[i], y: P.ribo[i], c: classCol(P.class[i]), r: P.class[i] === "unchanged" ? 1.8 : 3, t: `${g}: ${P.class[i]}`, g }));
      const order = ["translation", "buffering", "mRNA abundance", "unchanged"];
      $("#out", el).innerHTML = `<div class="grid g2" style="margin-top:18px"><div class="card"><div class="label">${esc(r.test)} against ${esc(r.reference)}: ${fmt(r.genes_tested)} genes</div>
          <div class="metrics small">TE up in ${fmt(r.up)} genes, down in ${fmt(r.down)}.</div>
          ${scatter(pts, { xlab: "RNA-seq log2 fold change", ylab: "Ribo-seq log2 fold change", lines: [{ x: 0 }], label: "Ribo-seq change against RNA-seq change" })}
          ${legend(order.map(c => [`${c} (${fmt(r.classes[c] || 0)})`, classCol(c)]))}
          ${r.anota2seq ? `<p class="small">The pipeline's anota2seq called ${fmt(r.anota2seq.significant)} genes for ${esc(r.anota2seq.contrast)}; ${fmt(r.anota2seq.both)} are also called here.</p>` : ""}
          ${guide("te_scatter", { open: true })}</div>
        <div class="card"><div class="label">Genes, most significant TE change first</div><div style="max-height:420px;overflow:auto"><table><thead><tr><th>Gene</th><th>Class</th><th class="num">TE log2FC</th><th class="num">Adj. P</th></tr></thead><tbody>
          ${r.rows.map(x => `<tr class="click" tabindex="0" data-g="${esc(x.gene)}"><td>${esc(x.label)}</td><td>${esc(x.class)}</td><td class="num">${x.te.toFixed(2)}</td><td class="num">${x.padj.toExponential(1)}</td></tr>`).join("")}</tbody></table></div>
          ${guide("te_table")}</div></div>
        <div class="card" style="margin-top:18px"><div class="label">One gene</div><div id="gene"><p class="small muted">Click a gene in the plot or the table.</p></div>${guide("te_gene")}</div>
        <div class="row" style="margin-top:18px"><button class="btn primary" data-go="step:export">Export →</button></div>`;
    };
    const gene = async g => {
      const d = await E.call("gene", { q: g });
      const P = PAL(), cc = c => P[conds.indexOf(c) % P.length];
      $("#gene", el).innerHTML = `<div class="label">${esc(d.label)}</div>
        ${d.te ? `<p class="small">${esc(d.te.class)}: TE log2 fold change ${d.te.te_log2fc} (adjusted P ${d.te.padj.toExponential(1)}); RNA-seq ${d.te.rna_log2fc}, Ribo-seq ${d.te.ribo_log2fc}.</p>` : `<p class="small muted">Not tested (too few counts).</p>`}
        <div class="grid g2"><div>${scatter(d.pairs.map((p, i) => ({ x: i + 1, y: p.log2_te, c: cc(p.condition), r: 6, t: `${p.pair}: log2 TE ${p.log2_te}` })),
            { xlab: "Pair", ylab: "log2 TE", h: 240, label: "log2 TE in each pair" })}
          ${legend(conds.map(c => [c, cc(c)]))}</div>
          <div><table class="small"><thead><tr><th>Pair</th><th class="num">Footprints</th><th class="num">mRNA reads</th></tr></thead><tbody>
          ${d.pairs.map(p => `<tr><td>${esc(p.pair)}</td><td class="num">${fmt(p.ribo)}</td><td class="num">${fmt(p.rna)}</td></tr>`).join("")}</tbody></table>
          ${d.orfs.length ? `<p class="small" style="margin-top:8px">ORFs: ${d.orfs.map(o => `${esc(o.class)} (${o.aa} aa)`).join(", ")}</p>` : ""}</div></div>`;
    };
    el.addEventListener("click", e => { const t = e.target.closest("[data-g]"); if (t) gene(t.dataset.g).catch(err => toast(err.message)); });
    $("#go", el).onclick = e => guarded(e.currentTarget, async () => {
      await E.call("te", { test: $("#test", el).value, reference: $("#ref", el).value, min_count: Number($("#min", el).value), alpha: Number($("#alpha", el).value) });
      await refresh(); await draw(); toast("Compared.", true);
    });
    if (prev.test) await draw();
  }

  // ---------------------------------------------------------------- export
  async function exportView(el) {
    el.innerHTML = lede("Save the tables for your own analysis or a paper's supplement. They go in the run's results/final folder.") +
      `<div class="card"><div class="label">What you get</div><ul class="small">
        <li><b>periodicity.csv</b>: each library's footprints by length, the share in each frame and the P-site offset.</li>
        <li><b>orfs.csv</b>: every predicted ORF with its gene, class and length.</li>
        <li><b>te_&lt;condition&gt;_vs_&lt;reference&gt;.csv</b>: RNA-seq, Ribo-seq and TE fold changes, P values and each gene's class (after Compare translation).</li></ul>
        <div class="row" style="margin-top:12px"><button class="btn primary" id="go">Export</button></div><div id="files"></div></div>`;
    $("#go", el).onclick = e => guarded(e.currentTarget, async () => { await E.call("export"); await filesTable($("#files", el)); toast("Tables saved.", true); });
    filesTable($("#files", el));
  }

  E.registerViews("rna.riboseq", { report, qc, orfs, te, export: exportView });
})();
