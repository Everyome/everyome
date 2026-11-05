/* Playground for variant calling: how a caller turns reads at one position into a genotype and a confidence (GQ),
   with the binomial model most callers start from, and how often a true one-copy variant is called right at a depth. */
"use strict";
(() => {
  const E = window.Everyome, H = E.helpers, { esc } = H;
  const NAMES = ["0/0 (not carried)", "0/1 (one copy)", "1/1 (two copies)"];

  // log of n choose k, for the binomial likelihood
  const lchoose = (n, k) => { let s = 0; for (let i = 1; i <= k; i++) s += Math.log((n - k + i) / i); return s; };

  // Posterior of each genotype from n reads with k showing the variant (equal priors), plus GQ and QUAL.
  function call(n, k, err) {
    const p = [err, 0.5, 1 - err];
    const ll = p.map(q => lchoose(n, k) + k * Math.log(q) + (n - k) * Math.log(1 - q));
    const m = Math.max(...ll), w = ll.map(l => Math.exp(l - m)), tot = w.reduce((a, b) => a + b, 0), post = w.map(x => x / tot);
    const best = post.indexOf(Math.max(...post));
    const phred = x => Math.min(99, Math.round(-10 * Math.log10(Math.max(x, 1e-10))));
    return { post, best, gq: phred(1 - post[best]), qual: phred(post[0]) };
  }

  function render(S, el) {
    const C = H.COL(), P = H.PALETTE(), n = S.depth, k = Math.min(S.alt, n), err = S.err / 100;
    const r = call(n, k, err);
    const w = 560, rowH = 34, h = 3 * rowH + 30, L = 150;
    let svg = `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="Probability of each genotype">`;
    r.post.forEach((v, i) => {
      const y = 8 + i * rowH, x = L + v * (w - L - 70);
      svg += `<text x="${L - 8}" y="${y + 17}" text-anchor="end" class="ax">${esc(NAMES[i])}</text>
        <rect x="${L}" y="${y + 4}" width="${Math.max(1, x - L)}" height="18" fill="${i === r.best ? C.ox : P[(i + 1) % P.length]}"/>
        <text x="${x + 6}" y="${y + 17}" class="ax">${(v * 100).toFixed(v > 0.999 || v < 0.001 ? 3 : 1)}%</text>`;
    });
    svg += `<text x="${L}" y="${h - 6}" class="ax">Probability of each genotype, given ${n} reads with ${k} showing the variant</text></svg>`;
    // How often a true one-copy variant at this depth is called 0/1 with GQ of at least 20 (summing over the reads it could get).
    let right = 0, missed = 0;
    for (let j = 0; j <= n; j++) {
      const pk = Math.exp(lchoose(n, j) + n * Math.log(0.5)), c = call(n, j, err);
      if (c.best === 1 && c.gq >= 20) right += pk;
      if (c.best === 0) missed += pk;
    }
    const m = (key, v, note, warn) => `<div class="m ${warn ? "warn" : ""}"><span class="k">${key}</span><span class="v">${v}</span><span class="n">${note}</span></div>`;
    el.innerHTML = `<section class="pg-card"><div class="label">What a caller would say</div>${svg}
        <div class="metrics">${m("Genotype called", esc(NAMES[r.best]), "the most likely one")}
          ${m("GQ", r.gq, "confidence in that genotype (20 = 1 in 100 wrong)", r.gq < 20)}
          ${m("QUAL", r.qual, "confidence the variant is there at all", r.qual < 30)}</div>
        <p class="note">Each read is a draw from one of the two chromosomes. One copy should give about half variant reads; two copies nearly all; none only the odd sequencing error.</p></section>
      <section class="pg-card"><div class="label">A true one-copy variant at ${n} reads</div>
        <div class="metrics">${m("Called 0/1 with GQ ≥ 20", (right * 100).toFixed(1) + "%", "of the time, over the reads it might get", right < 0.9)}
          ${m("Missed (called 0/0)", (missed * 100).toFixed(1) + "%", "the variant reads were too few by chance", missed > 0.02)}</div>
        <p class="note">At low depth, chance alone can give a one-copy variant almost no variant reads, or almost all of them, so it is missed or mistaken for two copies. That is why filters ask for a minimum depth.</p></section>`;
  }

  window.GenotypePlayground = E.makePlayground({
    defaults: { depth: 20, alt: 10, err: 1 },
    controls: [
      { group: "Reads at this position", items: [
        { key: "depth", label: "Reads covering it", type: "range", min: 1, max: 80, step: 1, help: "Germline whole-genome sequencing is usually 20–40 reads." },
        { key: "alt", label: "Reads showing the variant", type: "range", min: 0, max: 80, step: 1, help: "Can't be more than the reads covering it." }] },
      { group: "Sequencer", items: [
        { key: "err", label: "Error rate (%)", type: "range", min: 0.1, max: 5, step: 0.1, help: "Illumina base errors are around 0.1–1%." }] },
    ],
    presets: [
      ["20 reads, half show the variant (the defaults)", {}, "A clear one-copy variant: GQ is high."],
      ["4 reads, all show the variant", { depth: 4, alt: 4 }, "Two copies is most likely, but one copy could give this by chance: GQ is low."],
      ["30 reads, 3 show the variant", { depth: 30, alt: 3 }, "Too many to be errors at 1%, too few for one copy: neither fits well."],
      ["6 reads: how often is a one-copy variant called right?", { depth: 6, alt: 3 }, "Often missed or mistaken for two copies; compare with 30 reads."],
      ["A noisy run", { depth: 20, alt: 2, err: 5 }, "With 5% errors, two variant reads in twenty look like noise."],
    ],
    render: (S, el) => { S.alt = Math.min(Number(S.alt), Number(S.depth)); render({ depth: Number(S.depth), alt: Number(S.alt), err: Number(S.err) }, el); },
  });
})();
