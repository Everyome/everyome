/* Playground for genome annotation: one made-up gene; its exons, introns and protein. Shows why the protein's length
   follows the exons only, and how a missed exon shortens the protein. */
"use strict";
(() => {
  const E = window.Everyome, H = E.helpers;

  function render(S, el) {
    const C = H.COL(), exons = Array.from({ length: S.exons }, (_, i) => i === S.missed - 1 && S.missed ? 0 : S.exon), intron = S.intron;
    const genomic = exons.reduce((a, e) => a + (e || S.exon), 0) + intron * (S.exons - 1), coding = exons.reduce((a, b) => a + b, 0), aa = Math.floor(coding / 3);
    const w = 600, X = v => 10 + v / genomic * (w - 20);
    let s = `<svg class="chart" viewBox="0 0 ${w} 110" role="img" aria-label="A gene, its transcript and protein"><line x1="10" x2="${w - 10}" y1="25" y2="25" stroke="${C.muted}"/>`;
    let pos = 0;
    exons.forEach((e, i) => { s += `<rect x="${X(pos)}" y="16" width="${X(pos + S.exon) - X(pos)}" height="18" fill="${e ? C.ox : C.card}" stroke="${C.ink}" ${e ? "" : 'stroke-dasharray="3 2"'}><title>exon ${i + 1}${e ? "" : " (missed)"}</title></rect>`; pos += S.exon + intron; });
    const tw = coding / genomic * (w - 20);
    s += `<rect x="10" y="62" width="${Math.max(2, tw)}" height="14" fill="${C.ox}"/><text x="10" y="56" class="ax">mature transcript (exons joined)</text>
      <text x="10" y="100" class="ax">protein: ${aa} amino acids</text></svg>`;
    const m = (k, v, n, warn) => `<div class="m ${warn ? "warn" : ""}"><span class="k">${k}</span><span class="v">${v}</span><span class="n">${n}</span></div>`;
    el.innerHTML = `<section class="pg-card"><div class="label">The gene</div>${s}</section>
      <section class="pg-card"><div class="label">Lengths</div><div class="metrics">${m("On the genome", `${genomic.toLocaleString()} bp`, "exons and introns")}
        ${m("Coding", `${coding.toLocaleString()} bp`, "exons only")}${m("Protein", `${aa} aa`, S.missed ? "shorter: one exon was missed by the prediction" : "a third of the coding length", !!S.missed)}</div>
        <p class="note">Introns can be far longer than exons; the protein depends only on the exons. A predictor that misses an exon gives a shorter, often broken, protein.</p></section>`;
  }

  window.GeneModelPlayground = E.makePlayground({
    defaults: { exons: 5, exon: 180, intron: 600, missed: 0 },
    controls: [
      { group: "The gene", items: [
        { key: "exons", label: "Exons", type: "range", min: 1, max: 12, step: 1 },
        { key: "exon", label: "Exon length (bp)", type: "range", min: 60, max: 600, step: 30 },
        { key: "intron", label: "Intron length (bp)", type: "range", min: 60, max: 5000, step: 60 }] },
      { group: "The prediction", items: [{ key: "missed", label: "Exon missed (0: none)", type: "range", min: 0, max: 12, step: 1 }] },
    ],
    presets: [
      ["A typical gene (the defaults)", {}, "Five exons of 180 bp: a 300-amino-acid protein."],
      ["Long introns", { intron: 5000 }, "The gene spans 20 kb on the genome, the protein is just as long."],
      ["A missed exon", { missed: 3 }, "The predicted protein loses 60 amino acids from its middle."],
    ],
    render: (S, el) => { S.missed = Math.min(S.missed, S.exons); render(S, el); },
  });
})();
