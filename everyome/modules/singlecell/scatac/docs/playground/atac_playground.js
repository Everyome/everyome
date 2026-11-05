/* Playground for single-cell ATAC-seq: how a library's fragment sizes (the nucleosome ladder) and its TSS enrichment
   come from open chromatin, nucleosomes and background. One simulated cell; expected values, no sampling noise. */
"use strict";
(() => {
  const E = window.Everyome, H = E.helpers;
  const gauss = (x, m, s) => Math.exp(-0.5 * ((x - m) / s) ** 2);

  function profile(S) {
    // Fragment sizes: open chromatin gives short fragments; the rest span one or two nucleosomes (about 147 bp + linker).
    const open = S.open / 100, nuc = S.nuc / 100, sizes = [];
    for (let x = 0; x <= 800; x += 4) {
      const nfr = gauss(x, 60, 22), mono = gauss(x, 195, 28), di = gauss(x, 385, 38), tail = Math.exp(-x / 300) * 0.05;
      sizes.push(open * nfr + (1 - open) * ((1 - nuc) * mono + nuc * di) * 0.7 + (1 - open) * tail);
    }
    // Signal around gene starts: open chromatin piles up at the TSS; background is flat. TSS enrichment = centre / flanks.
    const tss = [];
    for (let x = -2000; x <= 2000; x += 40) tss.push(open * 6 * gauss(x, 0, 160) + (1 - open) * 0.25 + 0.05);
    const centre = tss[Math.floor(tss.length / 2)], flank = (tss[0] + tss[tss.length - 1]) / 2;
    return { sizes, tss, tsse: centre / flank };
  }

  function line(vals, { w = 540, h = 200, x0, x1, xlab, marks = [] }) {
    const C = H.COL(), L = 40, B = 30, max = Math.max(...vals), X = i => L + i / (vals.length - 1) * (w - L - 10), Y = v => h - B - v / max * (h - B - 10);
    let s = `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="${xlab}"><line x1="${L}" x2="${w - 10}" y1="${h - B}" y2="${h - B}" stroke="${C.muted}"/>`;
    marks.forEach(([v, t]) => { const x = L + (v - x0) / (x1 - x0) * (w - L - 10); s += `<line x1="${x}" x2="${x}" y1="10" y2="${h - B}" stroke="${C.muted}" stroke-dasharray="3 3"/><text x="${x + 3}" y="20" class="ax">${t}</text>`; });
    s += `<polyline fill="none" stroke="${C.ox}" stroke-width="2.2" points="${vals.map((v, i) => `${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join(" ")}"/>`;
    [x0, (x0 + x1) / 2, x1].forEach((v, i) => s += `<text x="${L + i / 2 * (w - L - 10)}" y="${h - B + 15}" text-anchor="middle" class="ax">${v}</text>`);
    return s + `<text x="${(w + L) / 2}" y="${h - 4}" text-anchor="middle" class="ax">${xlab}</text></svg>`;
  }

  function render(S, el) {
    const p = profile(S), frags = Math.round(S.depth * 1000), inTss = Math.round(frags * S.open / 100 * 0.6);
    const m = (k, v, n, warn) => `<div class="m ${warn ? "warn" : ""}"><span class="k">${k}</span><span class="v">${v}</span><span class="n">${n}</span></div>`;
    el.innerHTML = `<section class="pg-card"><div class="label">Fragment sizes</div>
        ${line(p.sizes, { x0: 0, x1: 800, xlab: "fragment length (bp)", marks: [[147, "1 nucleosome"], [294, "2"]] })}
        <p class="note">Short fragments come from open chromatin between nucleosomes; the bumps are DNA wrapped around one or two nucleosomes.</p></section>
      <section class="pg-card"><div class="label">Signal around gene starts</div>
        ${line(p.tss, { x0: -2000, x1: 2000, xlab: "distance from the gene start (bp)", marks: [[0, "TSS"]] })}
        <div class="metrics">${m("TSS enrichment", p.tsse.toFixed(1), p.tsse < 4 ? "below 4: mostly background; usually filtered out" : p.tsse < 7 ? "acceptable" : "a clean cell", p.tsse < 4)}
          ${m("Fragments in this cell", frags.toLocaleString(), `about ${inTss.toLocaleString()} near gene starts`, frags < 1000)}</div></section>`;
  }

  window.AtacPlayground = E.makePlayground({
    defaults: { open: 40, nuc: 30, depth: 5 },
    controls: [
      { group: "The cell's chromatin", items: [
        { key: "open", label: "Fragments from open chromatin (%)", type: "range", min: 2, max: 80, step: 1, help: "The rest come from closed chromatin and background." },
        { key: "nuc", label: "Of the rest, spanning two nucleosomes (%)", type: "range", min: 0, max: 80, step: 5 }] },
      { group: "Sequencing", items: [
        { key: "depth", label: "Fragments per cell (thousands)", type: "range", min: 0.2, max: 30, step: 0.2, help: "Depth changes the counts, not the shapes." }] },
    ],
    presets: [
      ["A good cell (the defaults)", {}, "A tall short-fragment peak, a clear ladder, and strong signal at gene starts."],
      ["A dying cell, mostly background", { open: 5 }, "Few fragments from open chromatin: the ladder flattens and TSS enrichment drops below 4."],
      ["Over-digested nuclei", { open: 70, nuc: 5 }, "Almost all fragments are short; enrichment looks high, but check the ladder too."],
      ["A shallow cell", { depth: 0.6 }, "The shapes are the same; there are just too few fragments to place this cell well."],
    ],
    render,
  });
})();
