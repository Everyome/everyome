/* Playground: k-mer spectrum of random sequence. */
"use strict";
(() => {
  const E = window.Everyome, H = E.helpers;
  function render(S, el) {
    let a = S.seed >>> 0; const r = () => (a = (a * 1664525 + 1013904223) >>> 0) / 4294967296;
    const seq = Array.from({ length: S.len }, () => "ACGT"[Math.floor(r() * 4)]).join(""), c = {};
    for (let i = 0; i + S.k <= seq.length; i++) c[seq.slice(i, i + S.k)] = (c[seq.slice(i, i + S.k)] || 0) + 1;
    const h = {}; Object.values(c).forEach(n => h[n] = (h[n] || 0) + 1);
    const xs = Object.keys(h).map(Number).sort((x, y) => x - y);
    el.innerHTML = `<section class="pg-card"><div class="label">K-mer spectrum</div>${H.barChart(xs.slice(0, 12).map(x => [`seen ${x}×`, h[x]]), { title: "Distinct k-mers by times seen" })}</section>`;
  }
  window.KmerPlayground = E.makePlayground({
    defaults: { seed: 1, len: 2000, k: 4 },
    controls: [{ group: "Sequence", items: [
      { key: "len", label: "Sequence length", type: "range", min: 200, max: 20000, step: 200 },
      { key: "k", label: "K-mer length", type: "range", min: 2, max: 10, step: 1 },
      { key: "seed", label: "Random seed", type: "range", min: 1, max: 20, step: 1 }] }],
    presets: [["Short k", { k: 3 }, "With only 64 possible 3-mers, each is seen many times."], ["Long k", { k: 9 }, "Almost every 9-mer is seen once."]],
    render,
  });
})();
