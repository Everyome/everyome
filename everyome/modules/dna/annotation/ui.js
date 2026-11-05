/* Views for genome annotation: what the cluster stages made (Run page), then the gene models (counts, lengths, BUSCO),
   any gene's structure and protein, and export. */
"use strict";
(() => {
  const E = window.Everyome, H = E.helpers, { $, esc, fmt, toast, guarded, guide, lede, filesTable, barChart, histChart } = H;

  async function report(el, q) {
    el.innerHTML = `<h2>What the cluster stages made</h2><div class="card"><div class="label">Gene models</div>
      ${q.gff ? `<p class="small">${fmt(q.genes)} genes and ${fmt(q.proteins)} proteins: <code>${esc(q.gff)}</code>.</p>` : `<div class="notice warn">No gene models were found. Check the stage logs.</div>`}
      ${q.busco ? `<p class="small">BUSCO: <code>${esc(q.busco)}</code></p>` : ""}
      ${E.state().demo ? `<p class="small muted">On the demo cluster, quick stand-ins replace Helixer, gffread and BUSCO.</p>` : ""}${guide("run_report")}</div>`;
  }

  function buscoBar(b) {
    const C = H.COL(), parts = [["single", b.single, C.ok], ["duplicated", b.duplicated, C.gold], ["fragmented", b.fragmented, C.golddk], ["missing", b.missing, C.ox]];
    let x = 0, s = `<svg class="chart" viewBox="0 0 520 26" role="img" aria-label="BUSCO completeness">`;
    parts.forEach(([n, v, col]) => { if (v == null) return; const w = 520 * v / 100; s += `<rect x="${x}" y="2" width="${w}" height="22" fill="${col}"><title>${n}: ${v}%</title></rect>`; x += w; });
    return s + `</svg>` + H.legend(parts.filter(p => p[1] != null).map(([n, v, col]) => [`${n} ${v}%`, col]));
  }

  async function overview(el) {
    const o = await E.call("overview");
    el.innerHTML = lede("The predicted genes as a whole. Compare with a related genome: similar numbers of genes, exons per gene and protein lengths are a good sign.") +
      `<div class="grid g2"><div class="card"><div class="label">Counts</div>
          <div class="metric"><span>Genes</span><b>${fmt(o.genes)}</b></div><div class="metric"><span>Transcripts</span><b>${fmt(o.transcripts)}</b></div>
          <div class="metric"><span>Proteins</span><b>${fmt(o.proteins)}</b></div><div class="metric"><span>Median exons per gene</span><b>${o.median_exons}</b></div>
          <div class="metric"><span>Single-exon genes</span><b>${fmt(o.single_exon)} (${Math.round(100 * o.single_exon / Math.max(1, o.genes))}%)</b></div>
          <div class="metric"><span>Median gene length</span><b>${fmt(o.median_gene_length)} bp</b></div><div class="metric"><span>Median protein length</span><b>${fmt(o.median_protein_length)} aa</b></div>${guide("gene_models")}</div>
        <div class="card"><div class="label">Completeness (BUSCO)</div>${o.busco ? `<p class="small"><code>${esc(o.busco.line)}</code> against ${esc(o.busco.lineage)}</p>${buscoBar(o.busco)}` : `<p class="small muted">BUSCO was not run (no lineage dataset set).</p>`}${guide("busco")}</div></div>
      <div class="grid g2" style="margin-top:18px"><div class="card"><div class="label">Exons per gene</div>${histChart(o.exon_hist.edges, o.exon_hist.counts, { xlab: "exons", digits: 0 })}</div>
        <div class="card"><div class="label">Protein length</div>${histChart(o.protein_hist.edges, o.protein_hist.counts, { xlab: "amino acids", digits: 0 })}</div></div>
      <div class="card" style="margin-top:18px"><div class="label">Genes per sequence (largest first)</div>${barChart(Object.entries(o.per_seq), { w: 560, title: "Genes per sequence" })}</div>`;
  }

  // One gene: exons as boxes on its stretch of genome, introns as lines, the coding part filled.
  function model(g) {
    const C = H.COL(), w = 620, L = 10, X = v => L + (v - g.start) / Math.max(1, g.end - g.start) * (w - 2 * L), y = 30;
    let s = `<svg class="chart" viewBox="0 0 ${w} 70" role="img" aria-label="Gene structure of ${esc(g.id)}"><line x1="${X(g.start)}" x2="${X(g.end)}" y1="${y}" y2="${y}" stroke="${C.muted}"/>`;
    g.exons.forEach(([a, b]) => s += `<rect x="${X(a)}" y="${y - 9}" width="${Math.max(2, X(b) - X(a))}" height="18" fill="${C.card}" stroke="${C.ink}"/>`);
    g.cds.forEach(([a, b]) => s += `<rect x="${X(a)}" y="${y - 9}" width="${Math.max(2, X(b) - X(a))}" height="18" fill="${C.ox}"><title>coding ${a}–${b}</title></rect>`);
    s += `<text x="${L}" y="64" class="ax">${esc(g.seqid)}:${fmt(g.start)}</text><text x="${w - L}" y="64" text-anchor="end" class="ax">${fmt(g.end)} (${g.strand === "-" ? "reverse" : "forward"} strand)</text>`;
    return s + "</svg>";
  }

  async function genes(el) {
    el.innerHTML = lede("Find a gene by its name, then see its exons and its protein.") +
      `<div class="grid g-side"><div class="card"><div class="row"><input type="text" id="q" placeholder="Gene name…" style="flex:1"></div><div id="list" style="max-height:520px;overflow:auto;margin-top:10px"></div></div>
        <div class="card"><div class="label">Gene</div><div id="g"><p class="small muted">Click a gene.</p></div>${guide("gene")}</div></div>`;
    const show = async id => {
      const g = await E.call("gene", { id });
      $("#g", el).innerHTML = `<p class="small"><b>${esc(g.id)}</b> · ${g.exons.length} exon${g.exons.length === 1 ? "" : "s"} · ${g.transcripts} transcript${g.transcripts === 1 ? "" : "s"}</p>${model(g)}
        <div class="label" style="margin-top:8px">Protein (${fmt(g.protein.length)} aa)</div><p class="mono small" style="word-break:break-all">${esc(g.protein)}</p>`;
    };
    const load = async () => { const r = await E.call("genes", { q: $("#q", el).value, n: 300 });
      $("#list", el).innerHTML = `<table class="small"><thead><tr><th>Gene</th><th>Where</th><th class="num">Exons</th><th class="num">Protein</th></tr></thead><tbody>${r.map(g =>
        `<tr class="click" tabindex="0" data-g="${esc(g.id)}"><td class="mono">${esc(g.id)}</td><td>${esc(g.seqid)}:${fmt(g.start)}</td><td class="num">${g.exons}</td><td class="num">${fmt(g.protein)}</td></tr>`).join("")}</tbody></table>`;
      if (r.length) show(r[0].id); };
    let t; $("#q", el).oninput = () => { clearTimeout(t); t = setTimeout(load, 250); };
    $("#list", el).addEventListener("click", e => { const r = e.target.closest("[data-g]"); if (r) show(r.dataset.g); });
    load();
  }

  async function exportView(el) {
    el.innerHTML = lede("Save the annotation. proteins.faa is ready for Function annotation, to find domains and GO terms.") +
      `<div class="card"><div class="label">What you get</div><ul class="small"><li><b>annotation.gff3</b>: the gene models.</li>
        <li><b>proteins.faa</b>: one protein per transcript.</li><li><b>genes.csv</b>: each gene's place, exons and protein length.</li></ul>
        <div class="row" style="margin-top:12px"><button class="btn primary" id="go">Export</button></div><div id="files"></div></div>`;
    $("#go", el).onclick = e => guarded(e.currentTarget, async () => { await E.call("export"); await filesTable($("#files", el)); toast("Saved to results/final.", true); });
    filesTable($("#files", el));
  }

  E.registerViews("dna.annotation", { report, overview, genes, export: exportView });
})();
