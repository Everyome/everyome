/* Playground for bulk RNA-seq differential expression: a simulated experiment where the truth is known,
   so you can see how replicates, effect size, noise and depth change what a test finds.
   Runs in the browser; built with Everyome's shared playground builder. */
"use strict";
(() => {
  const E = window.Everyome, H = E.helpers, { esc, fmt } = H;

  // ---- seeded random numbers (mulberry32) with normal and Poisson draws ----
  function rng(seed) {
    let a = seed >>> 0;
    const r = () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };
    r.normal = () => { let u = 0, v = 0; while (!u) u = r(); while (!v) v = r(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); };
    r.poisson = lam => { if (lam > 30) return Math.max(0, Math.round(lam + Math.sqrt(lam) * r.normal())); const L = Math.exp(-lam); let k = 0, p = 1; do { k++; p *= r(); } while (p > L); return k - 1; };
    return r;
  }

  // ---- Student t two-sided P value, via the regularised incomplete beta function ----
  function lnGamma(x) {
    const c = [76.18009172947146, -86.50532032941677, 24.01409824083091, -1.231739572450155, 0.1208650973866179e-2, -0.5395239384953e-5];
    let y = x, tmp = x + 5.5; tmp -= (x + 0.5) * Math.log(tmp); let ser = 1.000000000190015;
    for (const k of c) ser += k / ++y;
    return -tmp + Math.log(2.5066282746310005 * ser / x);
  }
  function betacf(a, b, x) {
    let qab = a + b, qap = a + 1, qam = a - 1, c = 1, d = 1 - qab * x / qap;
    d = 1 / (Math.abs(d) < 1e-30 ? 1e-30 : d); let h = d;
    for (let m = 1; m <= 200; m++) {
      const m2 = 2 * m; let aa = m * (b - m) * x / ((qam + m2) * (a + m2));
      d = 1 + aa * d; d = 1 / (Math.abs(d) < 1e-30 ? 1e-30 : d); c = 1 + aa / c; c = Math.abs(c) < 1e-30 ? 1e-30 : c; h *= d * c;
      aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2));
      d = 1 + aa * d; d = 1 / (Math.abs(d) < 1e-30 ? 1e-30 : d); c = 1 + aa / c; c = Math.abs(c) < 1e-30 ? 1e-30 : c;
      const del = d * c; h *= del; if (Math.abs(del - 1) < 3e-7) break;
    }
    return h;
  }
  function ibeta(x, a, b) {
    if (x <= 0) return 0; if (x >= 1) return 1;
    const bt = Math.exp(lnGamma(a + b) - lnGamma(a) - lnGamma(b) + a * Math.log(x) + b * Math.log(1 - x));
    return x < (a + 1) / (a + b + 2) ? bt * betacf(a, b, x) / a : 1 - bt * betacf(b, a, 1 - x) / b;
  }
  const tP = (t, df) => ibeta(df / (df + t * t), df / 2, 0.5);

  function simulate(S) {
    const r = rng(S.seed), G = 2000, n = S.reps, changed = new Set();
    while (changed.size < Math.round(G * S.share / 100)) changed.add(Math.floor(r() * G));
    const genes = [];
    for (let g = 0; g < G; g++) {
      // Intent: typical genes get a few hundred reads, as in a standard 20–30 million read library; depth scales that.
      const base = Math.exp(r.normal() * 1.6 + 6) * S.depth, isUp = r() < 0.5, fc = changed.has(g) ? (isUp ? S.fold : 1 / S.fold) : 1;
      const a = [], b = [];
      for (let i = 0; i < n; i++) {
        a.push(Math.log2(r.poisson(base * Math.exp(r.normal() * S.noise)) + 1));
        b.push(Math.log2(r.poisson(base * fc * Math.exp(r.normal() * S.noise)) + 1));
      }
      const ma = a.reduce((x, y) => x + y) / n, mb = b.reduce((x, y) => x + y) / n;
      const v = (a.reduce((x, y) => x + (y - ma) ** 2, 0) + b.reduce((x, y) => x + (y - mb) ** 2, 0)) / (2 * n - 2);
      genes.push({ lfc: mb - ma, v, truth: changed.has(g), mean: (ma + mb) / 2 });
    }
    // Intent: like DESeq2 and limma, borrow strength across genes: shrink each gene's variance towards the typical one.
    const d = 2 * n - 2, d0 = 4, s0 = [...genes.map(x => x.v)].sort((x, y) => x - y)[Math.floor(G / 2)];
    genes.forEach(x => { const vm = (d0 * s0 + d * x.v) / (d0 + d), t = x.lfc / Math.sqrt(vm * 2 / n || 1e-12); x.p = Math.min(1, tP(t, d + d0)); });
    // Benjamini–Hochberg adjustment
    const order = genes.map((x, i) => i).sort((i, j) => genes[i].p - genes[j].p);
    let min = 1;
    for (let k = G - 1; k >= 0; k--) { const g = genes[order[k]]; min = Math.min(min, g.p * G / (k + 1)); g.padj = min; }
    genes.forEach(g => g.sig = g.padj < S.alpha && Math.abs(g.lfc) >= S.lfc);
    return genes;
  }

  function render(S, el) {
    const C = H.COL(), genes = simulate(S);
    const tp = genes.filter(g => g.sig && g.truth).length, fp = genes.filter(g => g.sig && !g.truth).length, fn = genes.filter(g => !g.sig && g.truth).length;
    const truth = tp + fn, found = tp + fp;
    const col = g => g.sig ? (g.truth ? C.ox : C.gold) : (g.truth ? C.plum : C.rule);
    const w = 560, h = 340, L = 46, B = 34, xs = genes.map(g => g.lfc), ys = genes.map(g => -Math.log10(Math.max(g.padj, 1e-12)));
    const xm = Math.max(3, ...xs.map(Math.abs)), ym = Math.max(3, ...ys);
    const X = v => L + (v + xm) / (2 * xm) * (w - L - 10), Y = v => h - B - v / ym * (h - B - 10);
    let svg = `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="Volcano plot of the simulated experiment">`;
    [...genes].sort((a, b) => (a.sig || a.truth) - (b.sig || b.truth)).forEach(g => svg += `<circle cx="${X(g.lfc).toFixed(1)}" cy="${Y(-Math.log10(Math.max(g.padj, 1e-12))).toFixed(1)}" r="${g.sig || g.truth ? 2.6 : 1.6}" fill="${col(g)}"/>`);
    svg += `<line x1="${L}" x2="${w - 10}" y1="${Y(-Math.log10(S.alpha))}" y2="${Y(-Math.log10(S.alpha))}" stroke="${C.ox}" stroke-dasharray="4 3"/>
      <line x1="${L}" x2="${w - 10}" y1="${h - B}" y2="${h - B}" stroke="${C.muted}"/><line x1="${X(0)}" x2="${X(0)}" y1="10" y2="${h - B}" stroke="${C.rule}"/>
      <text x="${(w + L) / 2}" y="${h - 6}" text-anchor="middle" class="ax">log2 fold change</text><text x="12" y="${h / 2}" transform="rotate(-90 12 ${h / 2})" text-anchor="middle" class="ax">−log10 adjusted P</text></svg>`;
    const m = (k, v, n, warn) => `<div class="m ${warn ? "warn" : ""}"><span class="k">${k}</span><span class="v">${v}</span><span class="n">${n}</span></div>`;
    el.innerHTML = `<section class="pg-card"><div class="label">What the test found</div><div class="metrics">
        ${m("Truly changed genes found", `${fmt(tp)} of ${fmt(truth)}`, `power ${truth ? Math.round(100 * tp / truth) : 0}%`)}
        ${m("False discoveries", fmt(fp), `${found ? Math.round(100 * fp / found) : 0}% of genes called changed`, found && fp / found > S.alpha * 1.5)}
        ${m("Missed", fmt(fn), "truly changed but not called")}</div></section>
      <section class="pg-card"><div class="label">Volcano plot of 2,000 simulated genes</div>${svg}
        <div class="legend"><span><i style="background:${C.ox}"></i>found, truly changed</span><span><i style="background:${C.gold}"></i>found, not changed (false)</span>
          <span><i style="background:${C.plum}"></i>missed</span><span><i style="background:${C.rule}"></i>unchanged</span></div></section>`;
  }

  window.DEPlayground = E.makePlayground({
    defaults: { seed: 3, reps: 3, fold: 2, share: 10, noise: 0.2, depth: 1, alpha: 0.05, lfc: 0 },
    controls: [
      { group: "Experiment", items: [
        { key: "reps", label: "Replicates per condition", type: "range", min: 2, max: 10, step: 1, help: "Biological replicates, not technical ones." },
        { key: "depth", label: "Sequencing depth", type: "range", min: 0.2, max: 3, step: 0.1, help: "1 is typical; lower means fewer reads per gene." },
        { key: "seed", label: "Random seed", type: "range", min: 1, max: 20, step: 1, help: "Draws a new experiment with the same design." }] },
      { group: "Biology", items: [
        { key: "fold", label: "True fold change", type: "range", min: 1.1, max: 4, step: 0.1, help: "How much the changed genes really change." },
        { key: "share", label: "Genes that truly change (%)", type: "range", min: 1, max: 30, step: 1 },
        { key: "noise", label: "Biological variability", type: "range", min: 0.05, max: 0.8, step: 0.05, help: "How much replicates differ from each other." }] },
      { group: "Calling a gene changed", items: [
        { key: "alpha", label: "Adjusted P below", type: "select", options: [["0.01", "0.01"], ["0.05", "0.05"], ["0.1", "0.1"], ["0.2", "0.2"]] },
        { key: "lfc", label: "and |log2 fold change| at least", type: "range", min: 0, max: 2, step: 0.25 }] },
    ],
    presets: [
      ["Three replicates (the defaults)", {}, "200 genes truly change twofold. Three replicates find about half of them, with very few false calls; the rest are real changes the test could not confirm."],
      ["Only two replicates", { reps: 2 }, "Variability is guessed from two samples: power drops sharply. Not finding a gene is not evidence it did not change."],
      ["Eight replicates", { reps: 8 }, "More replicates find almost every changed gene, even with the same sequencing depth."],
      ["Small changes (1.3-fold)", { fold: 1.3 }, "Subtle changes need many more replicates to detect."],
      ["Noisy biology", { noise: 0.6 }, "When replicates differ a lot, fewer genes reach significance."],
      ["Shallow sequencing", { depth: 0.2 }, "Low counts add sampling noise, hurting lowly expressed genes most."],
      ["Add a twofold cut-off", { lfc: 1 }, "Keeps only large changes, and drops some truly changed genes near the cut-off."],
      ["Loosen to adjusted P below 0.2", { alpha: "0.2" }, "More genes found, and more of them false. The threshold sets the share of false calls you accept."],
    ],
    render,
  });
})();
