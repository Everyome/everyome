/* Playground for spatial transcriptomics: a simulated 2 mm tissue with a layer and a patch where one gene is on. Spots
   of a chosen size average the cells under them and are sequenced to a chosen depth. Compare what the spots record
   with the truth, and see how Moran's I separates a real pattern from noise. Runs in the browser; built with
   Everyome's shared playground builder. */
"use strict";
(() => {
  const E = window.Everyome, H = E.helpers, { fmt } = H;
  const SIZE = 2000, N = 200, UM = SIZE / N;                     // 2 mm of tissue as 200 × 200 cells of 10 µm

  function rng(seed) {
    let a = seed >>> 0;
    const r = () => { a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };
    r.poisson = lam => { if (lam > 40) { let u = 0, v = 0; while (!u) u = r(); while (!v) v = r(); return Math.max(0, Math.round(lam + Math.sqrt(lam) * Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v))); }
      const L = Math.exp(-lam); let k = 0, p = 1; do { k++; p *= r(); } while (p > L); return k - 1; };
    return r;
  }

  // The truth: expression of one gene in every cell (0–1): a layer across the tissue and a round patch (sizes in µm).
  function truth(S) {
    const r = rng(S.seed), t = new Float32Array(N * N), w = Math.max(0.3, S.edge) * UM;
    const step = d => 1 / (1 + Math.exp(-d / w));
    for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {
      const X = (x + .5) * UM, Y = (y + .5) * UM, dist = Math.hypot(X - 1400, Y - 1350);
      const on = Math.max(step(Y - 500) * step(800 - Y), step(250 - dist));
      t[y * N + x] = S.pattern === "yes" ? Math.min(1, on * (0.85 + 0.3 * r())) : (r() < 0.25 ? 1 : 0);
    }
    return t;
  }

  // Spots on a regular grid (Visium spots sit 1.8 diameters apart; Visium HD bins touch), each averaging the cells under it.
  function spots(S, t) {
    const r = rng(S.seed + 99), gap = S.spot >= 30 ? S.spot * 1.8 : S.spot, cols = Math.floor(SIZE / gap), list = [];
    const grid = new Int32Array(cols * cols).fill(-1);
    for (let j = 0; j < cols; j++) for (let i = 0; i < cols; i++) {
      const cx = (i + .5) * gap, cy = (j + .5) * gap, h = S.spot / 2;
      let s = 0, n = 0;
      for (let y = Math.max(0, Math.floor((cy - h) / UM)); y <= Math.min(N - 1, Math.floor((cy + h) / UM)); y++)
        for (let x = Math.max(0, Math.floor((cx - h) / UM)); x <= Math.min(N - 1, Math.floor((cx + h) / UM)); x++)
          if (S.spot < 30 || Math.hypot((x + .5) * UM - cx, (y + .5) * UM - cy) <= h + UM / 2) { s += t[y * N + x]; n++; }
      const mean = n ? s / n : 0, umis = S.depth * (S.spot / 55) ** 2, count = r.poisson(umis * 0.002 * (0.1 + 4 * mean));
      grid[j * cols + i] = list.length;
      list.push({ i, j, cx, cy, mean, count, value: Math.log1p(count / Math.max(umis, 1) * 1e4) });
    }
    return { list, grid, cols, gap };
  }

  // Moran's I with each spot's grid neighbours (left, right, up, down).
  function moran(sp) {
    const v = sp.list.map(s => s.value), m = v.reduce((a, b) => a + b, 0) / v.length, z = v.map(x => x - m);
    let num = 0, w = 0;
    sp.list.forEach((s, k) => [[1, 0], [-1, 0], [0, 1], [0, -1]].forEach(([di, dj]) => {
      const i = s.i + di, j = s.j + dj;
      if (i >= 0 && j >= 0 && i < sp.cols && j < sp.cols) { num += z[k] * z[sp.grid[j * sp.cols + i]]; w++; }
    }));
    const den = z.reduce((a, b) => a + b * b, 0) / v.length;
    return w && den ? (num / w) / den : 0;
  }

  function render(S, el) {
    const C = H.COL(), t = truth(S), sp = spots(S, t), I = moran(sp);
    const mixed = sp.list.filter(s => s.mean > 0.15 && s.mean < 0.85).length / sp.list.length;
    const zeros = sp.list.filter(s => s.count === 0).length / sp.list.length;
    const m = (k, v, n, warn) => `<div class="m ${warn ? "warn" : ""}"><span class="k">${k}</span><span class="v">${v}</span><span class="n">${n}</span></div>`;
    el.innerHTML = `<section class="pg-card"><div class="label">What the spots record</div><div class="metrics">
        ${m("Moran's I", I.toFixed(2), I > 0.3 ? "a clear spatial pattern" : I > 0.1 ? "a weak pattern" : "no pattern detected", S.pattern === "yes" && I < 0.1)}
        ${m("Spots", fmt(sp.list.length), `${S.spot} µm across, about ${fmt(Math.round(S.depth * (S.spot / 55) ** 2))} molecules each`)}
        ${m("Mixed spots", Math.round(100 * mixed) + "%", S.pattern === "yes" ? "partly on, partly off: they straddle a boundary" : "every spot mixes cells with and without the gene", S.pattern === "yes" && mixed > 0.3)}
        ${m("Spots with no molecule of the gene", Math.round(100 * zeros) + "%", "too few molecules to see it", zeros > 0.5)}</div></section>
      <section class="pg-card"><div class="label">The truth (each cell) and what the spots record (2 mm of tissue)</div>
        <div class="row" style="gap:18px;flex-wrap:wrap"><canvas id="pg-truth" width="300" height="300" style="max-width:300px;width:100%"></canvas>
        <canvas id="pg-spots" width="300" height="300" style="max-width:300px;width:100%"></canvas></div></section>`;
    const a = H.hexRgb(C.parch), b = H.hexRgb(C.ox), col = f => `rgb(${a.map((v, k) => Math.round(v + (b[k] - v) * Math.min(1, Math.max(0, f))))})`;
    const k = 300 / SIZE, ct = el.querySelector("#pg-truth").getContext("2d"), cs = el.querySelector("#pg-spots").getContext("2d");
    for (let i = 0; i < N * N; i++) { ct.fillStyle = col(t[i]); ct.fillRect((i % N) * UM * k, Math.floor(i / N) * UM * k, UM * k + .5, UM * k + .5); }
    cs.fillStyle = C.card; cs.fillRect(0, 0, 300, 300);
    const vmax = Math.max(...sp.list.map(s => s.value), 1e-6);
    sp.list.forEach(s => {
      cs.fillStyle = col(s.value / vmax);
      if (S.spot >= 30) { cs.beginPath(); cs.arc(s.cx * k, s.cy * k, S.spot / 2 * k, 0, 2 * Math.PI); cs.fill(); }
      else cs.fillRect((s.cx - S.spot / 2) * k, (s.cy - S.spot / 2) * k, S.spot * k + .3, S.spot * k + .3);
    });
  }

  window.SpatialPlayground = E.makePlayground({
    defaults: { seed: 1, spot: 55, depth: 5000, edge: 2, pattern: "yes" },
    controls: [
      { group: "Measurement", items: [
        { key: "spot", label: "Spot size (µm)", type: "range", min: 8, max: 100, step: 1, help: "Visium spots are 55 µm (centres 100 µm apart). Visium HD bins are 2–16 µm and touch." },
        { key: "depth", label: "Molecules per 55 µm spot", type: "range", min: 500, max: 20000, step: 500, help: "Sequencing depth. Smaller spots or bins get proportionally fewer." }] },
      { group: "Tissue", items: [
        { key: "edge", label: "Boundary softness (cells)", type: "range", min: 0.3, max: 10, step: 0.1, help: "How gradually the gene switches off at the edge of the layer and patch." },
        { key: "pattern", label: "Gene follows the tissue structure", type: "select", options: [["yes", "Yes"], ["no", "No: scattered cells"]] },
        { key: "seed", label: "Random seed", type: "range", min: 1, max: 20, step: 1 }] },
    ],
    presets: [
      ["Visium (the defaults)", {}, "55 µm spots each average several cells: the layer and patch are clear, and spots on their edges look half on."],
      ["Visium HD, 8 µm bins", { spot: 8 }, "Bins about the size of a cell show sharp edges, but each holds few molecules: most bins record none of the gene. Grouping bins (16 µm) trades detail for signal."],
      ["Shallow sequencing", { depth: 1000 }, "Fewer molecules make each spot noisier; Moran's I falls, though the pattern is still there."],
      ["No pattern", { pattern: "no" }, "The gene is on in scattered cells: spots differ only by chance and Moran's I is near zero."],
      ["Large spots", { spot: 100 }, "Big spots blur small structures: more spots straddle the boundaries."],
    ],
    render,
  });
})();
