/* Views for ATAC-seq: pipeline report, library checks, where the peaks are, comparing groups (DESeq2), a region of
   the genome, export. Uses only Everyome's shared helpers, so every chart follows the active theme. */
"use strict";
(() => {
  const E = window.Everyome, H = E.helpers;
  const { $, esc, fmt, toast, guarded, followTask, barChart, guide, scatter, legend, lede, filesTable, fileButton } = H;
  const COL = () => H.COL(), PAL = () => H.PALETTE();
  const S = { an: null, padj: 0.05, lfc: 0, locus: "" };
  const refresh = async () => (S.an = await E.status());
  const groupColour = g => PAL()[S.an.groups.indexOf(g) % PAL().length];
  const chip = g => `<span class="chip" style="cursor:inherit"><i style="background:${groupColour(g)}"></i>${esc(g)}</span>`;
  const pct = v => v == null ? "–" : (v * 100).toFixed(1) + "%";

  // ---------------------------------------------------------------- pipeline report (Run page)
  async function report(el, q) {
    const st = E.state(), low = q.libraries.filter(l => l.frip != null && l.frip < 0.2);
    el.innerHTML = `<h2>What the pipeline made</h2>
      <div class="grid g2"><div class="card"><div class="label">Peaks in each library (${esc(q.kind.replace("_", " "))}s)</div>
        ${q.libraries.some(l => l.peaks != null) ? barChart(q.libraries.map(l => [l.library, l.peaks || 0]), { label: v => fmt(v), title: "Peaks called in each library" }) : `<p class="small muted">No peak counts found yet.</p>`}
        ${q.libraries.some(l => l.frip != null) ? `<table style="margin-top:10px"><thead><tr><th>Library</th><th class="num">Reads in peaks (FRiP)</th></tr></thead><tbody>
          ${q.libraries.map(l => `<tr><td>${esc(l.library)}</td><td class="num">${l.frip != null && l.frip < 0.2 ? `<b>${pct(l.frip)}</b> (low)` : pct(l.frip)}</td></tr>`).join("")}</tbody></table>` : ""}
        ${low.length ? `<div class="notice warn">Low fraction of reads in peaks (below 20%): ${low.map(l => esc(l.library)).join(", ")}. See the guide below.</div>` : ""}</div>
      <div class="card"><div class="label">Consensus peaks and quality report</div>
        ${q.consensus ? `<p class="small">${fmt(q.consensus_peaks)} consensus peaks, counted in every library: <code>${esc(q.consensus.split("/").slice(-2).join("/"))}</code>.</p>`
          : `<div class="notice warn">No consensus peak counts were found. Check the pipeline log; the live session needs this table. Peak calling is skipped when no effective genome size is set.</div>`}
        ${q.multiqc ? `<p class="small">nf-core/atacseq's MultiQC report has every check: read quality, alignment, duplicates, fragment sizes, FRiP and more.</p>${fileButton(q.multiqc, "Open the MultiQC report")}` : `<p class="small muted">No MultiQC report found.</p>`}
        ${st.demo ? `<p class="small muted" style="margin-top:10px">On the demo cluster this is a placeholder.</p>` : ""}</div></div>${guide("pipeline_report")}`;
  }

  // A small heatmap of library-to-library correlation, darker for more alike.
  function corrHeat(names, corr) {
    const c = COL(), n = names.length, cw = 34, left = 120, top = 110, lo = Math.min(...corr.flat()), hi = 1;
    const a = H.hexRgb(c.parch), b = H.hexRgb(c.ox), mix = t => `rgb(${a.map((v, i) => Math.round(v + (b[i] - v) * t))})`;
    let s = `<svg class="chart" style="min-width:${left + n * cw + 20}px;max-width:${left + n * cw + 20}px" viewBox="0 0 ${left + n * cw + 20} ${top + n * cw + 10}" role="img" aria-label="Library correlation heatmap">`;
    names.forEach((x, j) => s += `<text transform="translate(${left + j * cw + cw / 2 + 4},${top - 6}) rotate(-55)" class="ax">${esc(x)}</text>`);
    names.forEach((x, i) => { s += `<text x="${left - 6}" y="${top + i * cw + cw / 2 + 4}" text-anchor="end" class="ax">${esc(x)}</text>`;
      corr[i].forEach((v, j) => s += `<rect x="${left + j * cw}" y="${top + i * cw}" width="${cw - 1}" height="${cw - 1}" fill="${mix((v - lo) / ((hi - lo) || 1))}"><title>${esc(x)} · ${esc(names[j])}: ${v}</title></rect>`); });
    return s + "</svg>";
  }

  // ---------------------------------------------------------------- check libraries
  async function samples(el) {
    await refresh();
    const o = await E.call("overview"), p = await E.call("sample_qc");
    el.innerHTML = lede("First, check the libraries. A good library has most of its reads in peaks; replicates of one group should look alike.") +
      (o.missing.length ? `<div class="notice warn">These libraries are in your table but not in the consensus counts: ${o.missing.map(esc).join(", ")}.</div>` : "") +
      `<div class="grid g2"><div class="card"><div class="label">Libraries</div><div style="overflow:auto"><table><thead><tr><th>Library</th><th>Group</th><th class="num">Peaks</th><th class="num">FRiP</th><th class="num">Median width</th><th class="num">Reads counted</th></tr></thead><tbody>
        ${o.libraries.map(l => `<tr><td>${esc(l.library)}</td><td>${chip(l.group)}</td><td class="num">${l.peaks == null ? "–" : fmt(l.peaks)}</td><td class="num">${l.frip != null && l.frip < 0.2 ? `<b>${pct(l.frip)}</b> <span class="small">(low)</span>` : pct(l.frip)}</td><td class="num">${l.median_width == null ? "–" : fmt(l.median_width) + " bp"}</td><td class="num">${fmt(l.in_consensus)}</td></tr>`).join("")}</tbody></table></div>
        <p class="small muted" style="margin-top:8px">${fmt(o.consensus_peaks)} consensus peaks (${esc(o.kind.replace("_", " "))}s) in <code>${esc(o.counts_file.split("/").slice(-2).join("/"))}</code>.</p>${guide("frip", { open: true })}</div>
      <div class="card"><div class="label">Principal components (${fmt(p.n_peaks)} most variable peaks)</div>
        ${scatter(p.libraries.map((s, i) => ({ x: p.pc1[i], y: p.pc2[i], c: groupColour(p.groups[i]), r: 6, t: `${s} (${p.groups[i]})` })),
          { xlab: `PC1 (${p.var[0]}%)`, ylab: `PC2 (${p.var[1] ?? 0}%)`, h: 300, label: "Principal component plot of libraries" })}
        ${legend(S.an.groups.map(g => [g, groupColour(g)]))}${guide("pca")}</div></div>
      <div class="card" style="margin-top:18px"><div class="label">Library correlation</div><div style="overflow:auto">${corrHeat(p.libraries, p.corr)}</div>
        <p class="small muted">Correlation of normalised, log-scaled counts in the consensus peaks. Darker means more alike.</p>${guide("correlation")}</div>
      <div class="row" style="margin-top:18px"><button class="btn primary" data-go="step:peaks">Where the peaks are →</button></div>`;
  }

  // ---------------------------------------------------------------- where the peaks are
  async function peaks(el) {
    await refresh();
    const r = await E.call("peaks"), c = COL();
    el.innerHTML = lede("Where the open chromatin is: how wide the peaks are and how far they lie from genes.") +
      `<div class="grid g2"><div class="card"><div class="label">Peak widths (${fmt(r.consensus_peaks)} consensus peaks, median ${fmt(r.median_width)} bp)</div>
          ${barChart(r.widths.labels.map((l, i) => [l, r.widths.counts[i]]), { label: v => fmt(v), title: "Consensus peak widths" })}${guide("peak_widths")}</div>
        <div class="card"><div class="label">Distance to the nearest gene's start</div>
          ${r.tss ? `${barChart(r.tss.labels.map((l, i) => [l, r.tss.counts[i]]), { label: v => fmt(v), title: "Distance from peak centre to the nearest transcription start site", colors: r.tss.labels.map((_, i) => i < 2 ? c.ox : c.golddk) })}
            <div class="metric"><span>Peaks within 1 kb of a gene's start</span><b>${r.tss.promoter_share}%</b></div><p class="small muted">Using ${fmt(r.tss.genes)} genes from the run's GTF.</p>`
          : `<div class="notice">No GTF was found for this run, so peaks can't be placed relative to genes.</div>`}${guide("tss_distance")}</div></div>
      <div class="card" style="margin-top:18px"><div class="label">Peaks on each sequence</div>${barChart(Object.entries(r.per_chrom), { w: 1000, label: v => fmt(v), title: "Consensus peaks on each sequence" })}</div>
      <div class="row" style="margin-top:18px"><button class="btn primary" data-go="step:compare">Compare groups →</button></div>`;
  }

  // ---------------------------------------------------------------- compare groups
  async function compare(el) {
    await refresh();
    const groups = S.an.groups, prev = S.an.da || {};
    const ref = prev.reference || groups.find(g => /control|ctrl|wt|wild|untreated|mock/i.test(g)) || groups[0];
    const test = prev.test || groups.find(g => g !== ref) || groups[0];
    el.innerHTML = lede("Find regions that open or close between two groups. DESeq2 estimates each peak's variation from the replicates and tests whether its reads differ.") +
      (groups.length < 2 ? `<div class="notice warn">Only one group is in the libraries table, so there is nothing to compare.</div>` : "") +
      `<div class="grid g-side"><div class="card"><div class="label">Comparison</div><div class="grid g2">
          <label class="field"><span>Group to test</span><select id="test">${groups.map(g => `<option ${g === test ? "selected" : ""}>${esc(g)}</option>`).join("")}</select><small>Fold changes are this group relative to the reference.</small></label>
          <label class="field"><span>Reference</span><select id="ref">${groups.map(g => `<option ${g === ref ? "selected" : ""}>${esc(g)}</option>`).join("")}</select></label>
          <label class="field"><span>Significance threshold (adjusted P)</span><input type="number" id="alpha" step="0.01" min="0.001" max="0.5" value="${prev.alpha ?? 0.05}"></label>
          <label class="field"><span>Minimum total reads</span><input type="number" id="minc" min="0" value="${prev.min_count ?? 10}"><small>Peaks with fewer reads across the compared libraries are left out.</small></label></div>
        <div class="row" style="margin-top:6px"><button class="btn primary" id="run">${prev.test ? "Compare again" : "Compare"}</button></div><div id="prog"></div></div>
        <div class="card"><div class="label">Result</div><div id="sum">${prev.test ? summary(prev) : '<p class="small muted">Not compared yet.</p>'}</div>${guide("da_summary")}</div></div>
      <div id="res"></div>`;
    $("#run", el).onclick = e => guarded(e.currentTarget, async () => {
      await E.call("run_da", { test: $("#test", el).value, reference: $("#ref", el).value, alpha: Number($("#alpha", el).value), min_count: Number($("#minc", el).value) });
      await followTask($("#prog", el)); await refresh(); $("#sum", el).innerHTML = summary(S.an.da); await results($("#res", el)); toast("Comparison finished.", true);
    });
    if (prev.test) await results($("#res", el));
  }
  const summary = d => `<div class="metric"><span>More open in ${esc(d.test)}</span><b>${fmt(d.opening)}</b></div><div class="metric"><span>Less open in ${esc(d.test)}</span><b>${fmt(d.closing)}</b></div>
    <div class="metric"><span>Peaks tested</span><b>${fmt(d.peaks_tested)}</b></div><p class="small muted">At adjusted P below ${d.alpha}, ${esc(d.test)} against ${esc(d.reference)}.</p>`;

  async function results(el) {
    const d = S.an.da, c = COL();
    el.innerHTML = `<div class="card" style="margin-top:18px"><div class="row"><label class="small">Adjusted P below <input type="number" id="padj" step="0.01" min="0.0001" max="1" value="${S.padj}" style="width:90px"></label>
        <label class="small">and |log2 fold change| at least <input type="number" id="lfc" step="0.1" min="0" value="${S.lfc}" style="width:80px"></label><span id="n" class="small"></span></div></div>
      <div class="grid g2" style="margin-top:18px"><div class="card"><div class="label">Volcano plot</div><div id="vol"></div>${guide("volcano")}</div>
        <div class="card"><div class="row" style="justify-content:space-between"><div class="label">Peaks</div><input type="text" id="q" placeholder="Search a peak or gene…" style="width:200px" aria-label="Search a peak or gene"></div>
          <div id="tbl" style="max-height:440px;overflow:auto"></div><p class="small muted">Click a peak to see it in its region.</p></div></div>`;
    async function draw() {
      S.padj = Number($("#padj", el).value) || 0.05; S.lfc = Number($("#lfc", el).value) || 0;
      const v = await E.call("volcano", { padj: S.padj, lfc: S.lfc });
      const col = s => s > 0 ? c.ox : s < 0 ? c.plum : c.rule;
      $("#vol", el).innerHTML = scatter(v.x.map((x, i) => ({ x, y: v.y[i], c: col(v.sig[i]), t: v.sig[i] ? `${v.peak[i]}${v.gene[i] ? " near " + v.gene[i] : ""}` : "" })),
        { xlab: `log2 fold change (${d.test} vs ${d.reference})`, ylab: "−log10 adjusted P", lines: [{ y: -Math.log10(S.padj) }, ...(S.lfc ? [{ x: S.lfc }, { x: -S.lfc }] : [])], label: "Volcano plot" }) +
        legend([[`more open in ${d.test}`, c.ox], [`less open in ${d.test}`, c.plum], ["not significant", c.rule]]);
      await table();
    }
    async function table() {
      const r = await E.call("results", { padj: S.padj, lfc: S.lfc, q: $("#q", el).value.trim(), n: 200 });
      $("#n", el).innerHTML = ` → <b>${fmt(r.opening)}</b> more open, <b>${fmt(r.closing)}</b> less open`;
      $("#tbl", el).innerHTML = r.rows.length ? `<table><thead><tr><th>Peak</th><th>Position</th><th>Nearest gene</th><th class="num">log2 FC</th><th class="num">Adjusted P</th></tr></thead><tbody>
        ${r.rows.map(x => `<tr class="click" tabindex="0" data-peak="${esc(x.peak)}"><td class="mono small">${esc(x.peak)}</td><td class="small">${esc(x.chr)}:${fmt(x.start)}–${fmt(x.end)}</td><td>${esc(x.gene)}${x.distance != null ? ` <span class="small muted">(${x.distance > 0 ? "+" : ""}${fmt(x.distance)} bp)</span>` : ""}</td><td class="num">${x.lfc}</td><td class="num">${x.padj == null ? "–" : x.padj.toExponential(2)}</td></tr>`).join("")}</tbody></table>`
        : `<p class="small muted">No peaks pass these thresholds${$("#q", el).value ? " or match the search" : ""}.</p>`;
    }
    const open = t => { S.locus = t.dataset.peak; H.go("step:locus"); };
    el.addEventListener("click", e => { const t = e.target.closest("[data-peak]"); if (t) open(t); });
    el.addEventListener("keydown", e => { if (e.key === "Enter" && e.target.dataset?.peak) open(e.target); });
    ["#padj", "#lfc"].forEach(id => $(id, el).addEventListener("change", () => guarded(null, draw)));
    let tq; $("#q", el).addEventListener("input", () => { clearTimeout(tq); tq = setTimeout(() => guarded(null, table), 250); });
    await draw();
  }

  // ---------------------------------------------------------------- look at a region
  function locusSvg(r) {
    const c = COL(), w = 760, L = 120, R = 10, X = p => L + (p - r.start) / (r.end - r.start) * (w - L - R), trackH = 34;
    const maxSig = Math.max(1, ...r.tracks.flatMap(t => t.peaks.map(p => p.signal))), maxCov = Math.max(1e-9, ...r.tracks.flatMap(t => t.coverage || [0]));
    let y = 8, s = "";
    // Genes: a line with an arrow for the strand.
    s += `<text x="${L - 8}" y="${y + 14}" text-anchor="end" class="ax">genes</text>`;
    r.genes.forEach(g => { const a = X(Math.max(g.start, r.start)), b = X(Math.min(g.end, r.end));
      s += `<rect x="${a}" y="${y + 6}" width="${Math.max(1, b - a)}" height="10" fill="${c.ink}" opacity=".75"><title>${esc(g.gene)} (${g.strand})</title></rect>
        <text x="${(a + b) / 2}" y="${y + 30}" text-anchor="middle" class="ax">${esc(g.gene)} ${g.strand === "-" ? "←" : "→"}</text>`; });
    y += 40;
    s += `<text x="${L - 8}" y="${y + 14}" text-anchor="end" class="ax">consensus</text>`;
    r.consensus.forEach(p => { const a = X(Math.max(p.start, r.start)), b = X(Math.min(p.end, r.end));
      const sig = p.padj != null && p.padj < S.padj ? (p.lfc > 0 ? c.ox : c.plum) : c.rule;
      s += `<rect x="${a}" y="${y + 4}" width="${Math.max(2, b - a)}" height="14" fill="${sig}"><title>${esc(p.peak)}${p.lfc != null ? `: log2 FC ${p.lfc}, adjusted P ${p.padj == null ? "–" : p.padj.toExponential(2)}` : ""}</title></rect>`; });
    y += 30;
    r.tracks.forEach(t => {
      const col = groupColour(t.group), base = y + trackH;
      s += `<text x="${L - 8}" y="${y + trackH / 2 + 4}" text-anchor="end" class="ax">${esc(t.library)}</text><line x1="${L}" x2="${w - R}" y1="${base}" y2="${base}" stroke="${c.rule}"/>`;
      if (t.coverage) {
        const n = t.coverage.length, pts = t.coverage.map((v, i) => `${(L + (i + 0.5) / n * (w - L - R)).toFixed(1)},${(base - v / maxCov * (trackH - 4)).toFixed(1)}`);
        s += `<polygon points="${L},${base} ${pts.join(" ")} ${w - R},${base}" fill="${col}" opacity=".8"/>`;
      } else {
        t.peaks.forEach(p => { const a = X(Math.max(p.start, r.start)), b = X(Math.min(p.end, r.end)), h = p.signal / maxSig * (trackH - 4);
          s += `<rect x="${a}" y="${base - h}" width="${Math.max(2, b - a)}" height="${h}" fill="${col}"><title>${esc(t.library)}: signal ${p.signal}</title></rect>`; });
      }
      y += trackH + 6;
    });
    s += `<text x="${L}" y="${y + 14}" class="ax">${esc(r.chrom)}:${fmt(r.start)}</text><text x="${w - R}" y="${y + 14}" text-anchor="end" class="ax">${fmt(r.end)}</text>`;
    return `<svg class="chart" viewBox="0 0 ${w} ${y + 22}" role="img" aria-label="Peaks in ${esc(r.chrom)} from ${r.start} to ${r.end}">${s}</svg>`;
  }

  async function locus(el) {
    await refresh();
    el.innerHTML = lede("Look at any region: each library's peaks, the consensus peaks (coloured by the comparison, if you ran one) and the genes nearby.") +
      `<div class="card"><div class="row"><input type="text" id="q" placeholder="A peak (Interval_12) or a gene name" style="flex:1" value="${esc(S.locus)}" aria-label="Peak or gene">
          <label class="small">Show <input type="number" id="pad" min="0" step="1000" value="5000" style="width:90px"> bp either side</label><button class="btn primary" id="show">Show</button></div>
        <div id="view" style="margin-top:12px"><p class="small muted">Type a peak or gene, or click a peak in Compare groups.</p></div>${guide("locus")}</div>
      <div class="row" style="margin-top:18px"><button class="btn primary" data-go="step:export">Export →</button></div>`;
    const show = async () => {
      const q = $("#q", el).value.trim(); S.locus = q;
      const r = await E.call("locus", { q, pad: Number($("#pad", el).value) || 0 }), c = COL();
      $("#view", el).innerHTML = locusSvg(r) + legend([...S.an.groups.map(g => [g, groupColour(g)]), ...(S.an.da ? [[`more open in ${S.an.da.test}`, c.ox], [`less open in ${S.an.da.test}`, c.plum]] : [])]) +
        (r.tracks.some(t => t.coverage) ? `<p class="small muted">Tracks show read coverage from the pipeline's bigWig files.</p>` : `<p class="small muted">Bars are MACS2 peaks; their height is the peak's enrichment over background.</p>`);
    };
    $("#show", el).onclick = e => guarded(e.currentTarget, show);
    $("#q", el).onkeydown = e => { if (e.key === "Enter") $("#show", el).click(); };
    if (S.locus) await guarded(null, show);
  }

  // ---------------------------------------------------------------- export
  async function exportView(el) {
    await refresh();
    el.innerHTML = lede("Save the tables for other tools or a paper. Everything goes in the run's results/final folder.") +
      `<div class="card"><div class="label">What you get</div><ul class="small">
        <li><b>consensus_peaks_counts.csv</b>: every consensus peak, its nearest gene and its reads in each library.</li>
        <li><b>normalised_log2.csv</b>: the normalised, log-scaled counts the library checks use.</li>
        <li><b>libraries.csv</b>: each library's group.</li>
        <li><b>da_…_all_peaks.csv</b>, <b>da_…_significant.csv</b> and <b>.bed</b>: the comparison (after Compare groups); the BED opens in a genome browser.</li></ul>
        <div class="row" style="margin-top:12px"><label class="small">Significant means adjusted P below <input type="number" id="padj" step="0.01" value="${S.padj}" style="width:90px"></label>
          <label class="small">and |log2 fold change| at least <input type="number" id="lfc" step="0.1" min="0" value="${S.lfc}" style="width:80px"></label>
          <button class="btn primary" id="go">Export</button></div><div id="files"></div></div>
      <div class="row" style="margin-top:18px"><button class="btn" data-go="record">Record and write-up →</button></div>`;
    $("#go", el).onclick = e => guarded(e.currentTarget, async () => {
      S.padj = Number($("#padj", el).value); S.lfc = Number($("#lfc", el).value);
      await E.call("export", { padj: S.padj, lfc: S.lfc }); await filesTable($("#files", el)); toast("Tables saved.", true);
    });
    filesTable($("#files", el));
  }

  E.registerViews("dna.atac", { report, samples, peaks, compare, locus, export: exportView });
})();
