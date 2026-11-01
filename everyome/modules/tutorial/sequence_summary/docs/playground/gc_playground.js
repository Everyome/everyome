/* Playground for the Sequence summary tutorial: why short sequences give noisy GC values,
   and what a second organism looks like in a GC histogram. Runs in the browser. */
"use strict";
(() => {
  const E = window.Everyome, H = E.helpers, { fmt } = H;

  function rng(seed) {
    let a = seed >>> 0;
    return () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };
  }

  function render(S, el) {
    const r = rng(S.seed), n = S.count, len = S.len, gcs = [];
    for (let i = 0; i < n; i++) {
      const p = r() * 100 < S.mix ? S.gc2 / 100 : S.gc1 / 100;
      let g = 0; for (let b = 0; b < len; b++) if (r() < p) g++;
      gcs.push(g / len);
    }
    const bins = 40, edges = Array.from({ length: bins + 1 }, (_, i) => i / bins), counts = Array(bins).fill(0);
    gcs.forEach(v => counts[Math.min(bins - 1, Math.floor(v * bins))]++);
    const mean = gcs.reduce((a, b) => a + b, 0) / n, sd = Math.sqrt(gcs.reduce((a, b) => a + (b - mean) ** 2, 0) / (n - 1));
    const p = S.gc1 / 100, expect = Math.sqrt(p * (1 - p) / len);
    const m = (k, v, note) => `<div class="m"><span class="k">${k}</span><span class="v">${v}</span><span class="n">${note}</span></div>`;
    el.innerHTML = `<section class="pg-card"><div class="label">GC content of ${fmt(n)} simulated sequences of ${fmt(len)} bases</div>
        ${H.histChart(edges, counts, { xlab: "GC fraction", digits: 2 })}</section>
      <section class="pg-card"><div class="label">The numbers</div><div class="metrics">
        ${m("Average GC", mean.toFixed(3), `true value ${S.mix ? "is a mixture" : (p).toFixed(2)}`)}
        ${m("Spread (standard deviation)", sd.toFixed(3), S.mix ? "includes the gap between the two organisms" : `chance alone gives about ${expect.toFixed(3)}`)}
        </div><p class="note">With L bases, chance alone spreads GC by about √(p(1−p)/L): four times the length halves the spread.</p></section>`;
  }

  window.GCPlayground = E.makePlayground({
    defaults: { seed: 1, count: 400, len: 300, gc1: 45, mix: 0, gc2: 65 },
    controls: [
      { group: "Sequences", items: [
        { key: "len", label: "Length (bases)", type: "range", min: 20, max: 2000, step: 10 },
        { key: "count", label: "How many", type: "range", min: 50, max: 2000, step: 50 },
        { key: "seed", label: "Random seed", type: "range", min: 1, max: 20, step: 1 }] },
      { group: "Organisms", items: [
        { key: "gc1", label: "First organism's GC (%)", type: "range", min: 20, max: 80, step: 1 },
        { key: "mix", label: "Share from a second organism (%)", type: "range", min: 0, max: 60, step: 5 },
        { key: "gc2", label: "Second organism's GC (%)", type: "range", min: 20, max: 80, step: 1 }] },
    ],
    presets: [
      ["Long sequences from one organism (the defaults)", {}, "One tight peak at the organism's GC content."],
      ["Very short sequences (30 bases)", { len: 30 }, "The same organism now gives a wide, ragged peak: short sequences cannot pin down GC."],
      ["A second organism in the mix", { mix: 30 }, "A second peak appears. In real data this can mean contamination or a symbiont."],
      ["A second organism, but short sequences", { mix: 30, len: 40 }, "The two peaks blur into one: the contamination is hidden. Filtering out short sequences helps."],
      ["Very long sequences (2,000 bases)", { len: 2000 }, "The peak becomes very narrow; small differences in GC become visible."],
    ],
    render,
  });
})();
